"""AlphaAdjust only where the shader reads it, Use_Basecolor_to_Emissive (oracle vs Cycles/EEVEE), and the
Use_SecodaryUV_DetailMask / UV_Secondary_Blend / ParallaxEmit_Blur UV wiring.
blender --background --factory-startup --python-exit-code 1 --python FILE -- [--report JSON]
"""
import argparse,importlib,json,sys,tempfile
from pathlib import Path
import addon_utils,bpy,numpy as np
parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
addon=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(addon.parent));addon_utils.enable(addon.name,default_set=True)
main=importlib.import_module(addon.name+'.modules.mdf.blender_re_mesh_mdf')
nodes=importlib.import_module(addon.name+'.modules.mdf.blender_nodes_re_mdf')
mdf=importlib.import_module(addon.name+'.modules.mdf.file_re_mdf')
results={'blender':bpy.app.version_string,'checks':[]}
def check(name,ok,detail=None):
    results['checks'].append({'name':name,'passed':bool(ok),'detail':detail});print(('PASS ' if ok else 'FAIL ')+name,flush=True)
    assert ok,(name,detail)
sat=lambda x:min(max(x,0.0),1.0)
#Oracle written from the traced shader block, not from the node builder
def b2e_oracle(c):
    base,em,emap=np.array(c['base'][:3]),np.array(c['emission'][:3]),np.array(c['emap'][:3])
    if c['use']==0:return base,em
    r=(0.0 if emap.max()<c['ecA'] else 1.0) if c['ecA']<1 else em.max()
    if c['useMask']!=0:
        x=sat((base.max()-c['min'])/(c['max']-c['min']));r*=x*x*(3-2*x)
    return base*(1-sat(r)),base*r
cases=[dict(name='max channel ratio',use=1,base=(.6,.4,.2,1),emission=(.3,.7,.5,1),emap=(.3,.7,.5,1),ecA=1,useMask=0,min=0,max=1),
       dict(name='ratio above one',use=1,base=(.5,.5,.5,1),emission=(1.6,.2,.1,1),emap=(.8,.1,.05,1),ecA=1,useMask=0,min=0,max=1),
       dict(name='hard mask on',use=1,base=(.6,.3,.1,1),emission=(.2,.2,.2,1),emap=(.7,.1,.1,1),ecA=.5,useMask=0,min=0,max=1),
       dict(name='hard mask off',use=1,base=(.6,.3,.1,1),emission=(.2,.2,.2,1),emap=(.3,.1,.1,1),ecA=.5,useMask=0,min=0,max=1),
       dict(name='base brightness mask',use=1,base=(.5,.3,.2,1),emission=(.6,.6,.6,1),emap=(.6,.6,.6,1),ecA=1,useMask=1,min=.2,max=.8),
       dict(name='switch off',use=0,base=(.6,.4,.2,1),emission=(.3,.7,.5,1),emap=(.3,.7,.5,1),ecA=1,useMask=0,min=0,max=1)]
scratch=tempfile.TemporaryDirectory(prefix='reme_shadingfix_');root=Path(scratch.name)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_plane_add(size=2);plane=bpy.context.object;plane.data.uv_layers.active.name='UVMap0'
scene=bpy.context.scene;scene.cycles.device='CPU';scene.cycles.samples=1;scene.cycles.use_denoising=False
camdata=bpy.data.cameras.new('cam');cam=bpy.data.objects.new('cam',camdata);scene.collection.objects.link(cam);camdata.type='ORTHO';camdata.ortho_scale=.5;cam.location=(0,0,3);scene.camera=cam
scene.render.resolution_x=scene.render.resolution_y=8;scene.render.image_settings.file_format='OPEN_EXR';scene.render.image_settings.color_depth='32'
mat=bpy.data.materials.new('oracle');mat.use_nodes=True;plane.data.materials.append(mat);nt=mat.node_tree;nt.nodes.clear()
out=nt.nodes.new('ShaderNodeOutputMaterial');emit=nt.nodes.new('ShaderNodeEmission');nt.links.new(emit.outputs[0],out.inputs['Surface'])
g=nt.nodes.new('ShaderNodeGroup');g.node_tree=nodes.getMHWildsBasecolorToEmissiveNodeGroup()
def render(engine):
    scene.render.engine=engine;scene.render.filepath=str(root/'s.exr');bpy.ops.render.render(write_still=True)
    im=bpy.data.images.load(scene.render.filepath,check_existing=False);v=np.array(im.pixels[:]).reshape(8,8,4)[4,4,:3].copy();bpy.data.images.remove(im);return v
try:
    for engine,tol in (('CYCLES',2e-3),('BLENDER_EEVEE',4e-3)):
        for c in cases:
            g.inputs['Base'].default_value=c['base'];g.inputs['Emission'].default_value=c['emission'];g.inputs['EmissiveMap'].default_value=c['emap']
            for key,socket in (('ecA','Emissive Alpha'),('use','Use_Basecolor_to_Emissive'),('useMask','Use_Basecolor_Mask'),('min','Basecolor_Mask_Min'),('max','Basecolor_Mask_Max')):
                g.inputs[socket].default_value=c[key]
            wantBase,wantEmission=b2e_oracle(c)
            for output,want in (('Base',wantBase),('Emission',wantEmission)):
                nt.links.new(g.outputs[output],emit.inputs['Color'])
                got=render(engine)
                check(f'{engine} Basecolor_to_Emissive {c["name"]}: {output}',np.abs(got-want).max()<tol,{'got':got.round(5).tolist(),'want':want.round(5).tolist()})

    #AntiTranslucent and UV tile groups vs independent oracles
    def anti_oracle(c):
        n=np.array([0,0,1.0]);ns=np.array(c['ns'])/np.linalg.norm(c['ns']);i=n
        nb=n+(ns-n)*c['blend'];nb/=np.linalg.norm(nb)
        t=c['tp']*c['g'];rim=t*(1-abs(float(nb@i)))**c['power'];trans=t+(rim-t)*c['userim']
        a=np.array(c['albedo'][:3])
        return a+(a/(0.78-0.23*c['rough'])-a)*trans if c['use']!=0 else a
    antis=[dict(name='plain translucency',use=1,albedo=(.5,.4,.3,1),rough=.6,ns=(0,0,1),g=.8,tp=.5,userim=0,blend=0,power=2),
           dict(name='rim with tilted shading normal',use=1,albedo=(.3,.5,.2,1),rough=.3,ns=(.9,0,.44),g=1,tp=.9,userim=1,blend=1,power=.5),
           dict(name='switch off',use=0,albedo=(.3,.5,.2,1),rough=.3,ns=(.6,0,.8),g=1,tp=.9,userim=1,blend=.7,power=1.5)]
    ag=nt.nodes.new('ShaderNodeGroup');ag.node_tree=nodes.getMHWildsAntiTranslucentNodeGroup()
    vecnode=nt.nodes.new('ShaderNodeCombineXYZ');nt.links.new(vecnode.outputs[0],ag.inputs['Shading Normal'])
    tg=nt.nodes.new('ShaderNodeGroup');tg.node_tree=nodes.getMHWildsUVTileNodeGroup();uvsrc=nt.nodes.new('ShaderNodeCombineXYZ');nt.links.new(uvsrc.outputs[0],tg.inputs['UV'])
    tiles=[dict(name='tile and offset',uv=(.3,.6),tile=2,sx=.5,sy=.5,ox=.1,oy=.2),dict(name='identity',uv=(.7,.2),tile=1,sx=1,sy=1,ox=0,oy=0)]
    for engine,tol in (('CYCLES',2e-3),('BLENDER_EEVEE',4e-3)):
        nt.links.new(ag.outputs['Albedo'],emit.inputs['Color'])
        for c in antis:
            ag.inputs['Albedo'].default_value=c['albedo'];ag.inputs['Roughness'].default_value=c['rough'];ag.inputs['ATOS G'].default_value=c['g']
            for k,v in zip('XYZ',c['ns']):vecnode.inputs[k].default_value=v
            for key,socket in (('tp','TranslucentParam'),('userim','Use_RimTranslucent'),('blend','RimTranslucent_NormalBlend'),('power','RimTrasnlucent_Power'),('use','Use_AntiTranslucent_Diffuse')):
                ag.inputs[socket].default_value=c[key]
            got,want=render(engine),anti_oracle(c)
            check(f'{engine} AntiTranslucent {c["name"]}',np.abs(got-want).max()<tol,{'got':got.round(5).tolist(),'want':want.round(5).tolist()})
        nt.links.new(tg.outputs['UV'],emit.inputs['Color'])
        for c in tiles:
            uvsrc.inputs['X'].default_value,uvsrc.inputs['Y'].default_value=c['uv']
            for key,socket in (('tile','UV_Tile'),('sx','Scale X'),('sy','Scale Y'),('ox','Offset X'),('oy','Offset Y')):tg.inputs[socket].default_value=c[key]
            u,v=c['uv'];want=np.array([u*c['tile']*c['sx']+c['ox'],1-((1-v)*c['tile']*c['sy']+c['oy']),0.0])
            got=render(engine)
            check(f'{engine} UV_Tile {c["name"]} (D3D V)',np.abs(got[:2]-want[:2]).max()<tol,{'got':got.round(5).tolist(),'want':want.round(5).tolist()})

    #Backface culling: back faces turn transparent only while the material checkbox is on (Cycles has no culling of its own)
    cull=bpy.data.materials.new('cull');cull.use_nodes=True;cnt=cull.node_tree;cnt.nodes.clear()
    cout=cnt.nodes.new('ShaderNodeOutputMaterial');cemit=cnt.nodes.new('ShaderNodeEmission');cemit.inputs['Color'].default_value=(.8,.1,.1,1)
    cnt.links.new(nodes.addBackfaceCullingNodes(cnt,cull,cemit.outputs[0]),cout.inputs['Surface'])
    plane.data.materials[0]=cull;scene.render.film_transparent=True
    def renderRGBA(engine):
        scene.frame_set(scene.frame_current);scene.render.engine=engine;scene.render.filepath=str(root/'c.exr');bpy.ops.render.render(write_still=True)
        im=bpy.data.images.load(scene.render.filepath,check_existing=False);v=np.array(im.pixels[:]).reshape(8,8,4)[4,4].copy();bpy.data.images.remove(im);return v
    try:
        for engine in ('CYCLES','BLENDER_EEVEE'):
            for flipped,culling,visible in ((True,False,True),(True,True,False),(False,True,True)):
                plane.rotation_euler[0]=np.pi if flipped else 0.0;cull.use_backface_culling=culling
                got=renderRGBA(engine);ok=(abs(got[3]-1)<1e-3 and abs(got[0]-.8)<4e-3) if visible else got[3]<1e-3
                check(f'{engine} {"back" if flipped else "front"} face with culling {"on" if culling else "off"} is {"visible" if visible else "hidden"}',ok,got.round(4).tolist())
    finally:
        plane.rotation_euler[0]=0.0;plane.data.materials[0]=mat;scene.render.film_transparent=False

    #Importer wiring
    good=bpy.data.images.new('good',1,1,alpha=True);good.generated_color=(.5,.5,.5,1)
    names=('Texconv','unload_texconv','getTexPath','loadTex','getChunkPathList');saved={n:getattr(main,n) for n in names}
    main.Texconv=lambda:None;main.unload_texconv=lambda:None;main.getChunkPathList=lambda game:[];main.getTexPath=lambda base,*a,**k:base;main.loadTex=lambda *a,**k:[good]
    def entry(name,mmtr,props,slots):
        m=mdf.Material();m.materialName=name;m.mmtrPath='MaterialShader/Variation/'+mmtr;m.shaderType=0;m.textureList=[];m.propertyList=[]
        for s in slots:
            t=mdf.TextureBinding();t.textureType=s;t.texturePath=s+'.tex';m.textureList.append(t)
        for k,v in props.items():
            p=mdf.Property();p.propName=k;p.paramCount=len(v);p.propValue=list(v);m.propertyList.append(p)
        return m
    def run(entries):
        f=mdf.MDFFile();f.fileVersion=45;f.materialList=entries
        mats={e.materialName:bpy.data.materials.new(e.materialName) for e in entries}
        main.importMDF(f,mats,False,False,False,False,chunkPath='',gameName='MHWILDS');return {k:v.node_tree for k,v in mats.items()}
    def source(socket):
        return socket.links[0].from_node if socket.is_linked else None
    try:
        base=('BaseAlphaMap','NormalRoughnessOcclusionMap','AlphaTranslucentOcclusionSSSMap')
        t=run([entry('Eye','Base_eye_Emit.mmtr',{'AlphaAdjust':[.5]},base),entry('Skin','Base_ATOS_SkinEdit_VFX.mmtr',{'AlphaAdjust':[.5]},base),
               entry('Gold','Base_GOLD_Push.mmtr',{'AlphaAdjust':[.5]},base)])
        check('eye and GOLD masters do not apply AlphaAdjust (their shaders never read it)','MHWildsAlphaAdjust' not in t['Eye'].nodes and 'MHWildsAlphaAdjust' not in t['Gold'].nodes)
        check('masters that read AlphaAdjust still apply it','MHWildsAlphaAdjust' in t['Skin'].nodes)

        emissive={'Use_Basecolor_to_Emissive':[1],'Emissive_Color':[1,1,1,1],'Emissive_Intensity':[1],'Emissive_Power':[0]}
        t=run([entry('B2E','Base_ATOS_Emit_FX_Detail_DetailColLayer_MultiBlend.mmtr',emissive,('BaseDielectricMap','NormalRoughnessOcclusionMap','EmissiveMap'))])['B2E']
        node=t.nodes.get('MHWilds Basecolor To Emissive');bsdf=next(n for n in t.nodes if n.bl_idname=='ShaderNodeBsdfPrincipled')
        def upstream(socket,target,depth=0):
            n=source(socket)
            return n==target or (n is not None and depth<12 and any(upstream(i,target,depth+1) for i in n.inputs if i.is_linked))
        check('Use_Basecolor_to_Emissive feeds both the BSDF base color and emission',node is not None and upstream(bsdf.inputs['Base Color'],node) and upstream(bsdf.inputs['Emission Color'],node))
        check('the switch arrives through its property node',source(node.inputs['Use_Basecolor_to_Emissive']).name=='Use_Basecolor_to_Emissive' and source(node.inputs['Emissive Alpha']).name=='Emissive_Color')

        detail={'UseDetail':[1],'Use_R':[1],'Use_SecodaryUV_DetailMask':[1]}
        t=run([entry('Detail','Base_ATOS_Emit_FX_Detail_DetailColLayer_MultiBlend.mmtr',detail,('BaseDielectricMap','NormalRoughnessOcclusionMap','DetailMaskMap','Detail_ALBD_R','Detail_NRRH_R'))])['Detail']
        pick=source(t.nodes['DetailMaskMap'].inputs['Vector'])
        check('Use_SecodaryUV_DetailMask switches the detail mask UV',pick is not None and pick.bl_idname=='ShaderNodeMix' and source(pick.inputs['B']).name=='UVMap2Node' and source(pick.inputs['A']).name=='MHWildsBaseAOUV')

        eye={'UV_Secondary_Blend':[.3],'UseAOSecondaryUV':[0],'UseParallaxEmit':[1],'ParallaxEmit_Height':[.1],'ParallaxEmit_Blend':[.6],'ParallaxEmit_Blur':[.4],'Emissive_Color':[1,1,1,1]}
        t=run([entry('EyeUV','Base_eye_Emit.mmtr',eye,('BaseAlphaMap','NormalRoughnessOcclusionMap','VectorEmitMap','EmissiveMap'))])['EyeUV']
        blend=source(t.nodes['NormalRoughnessOcclusionMap'].inputs['Vector'])
        check('UV_Secondary_Blend lerps base UV toward UV1 for the base slots',blend is not None and blend.bl_idname=='ShaderNodeMix' and source(blend.inputs['Factor']).name=='UV_Secondary_Blend' and source(blend.inputs['B']).name=='UVMap2Node')
        check('VectorEmitMap follows the blended UV',source(t.nodes['VectorEmitMap'].inputs['Vector'])==blend)
        emiUV=source(t.nodes['EmissiveMap'].inputs['Vector']);check('with ParallaxEmit on, the unshifted EmissiveMap keeps UV0 (unlinked = active UV0)',emiUV is None or emiUV.name=='UVMap1Node')
        ao=[n for n in t.nodes if n.name.startswith('AO_')]
        check('AO samples use UseAOSecondaryUV ? UV1 : blended UV',ao and all(source(n.inputs['Vector']).bl_idname=='ShaderNodeMix' and source(source(n.inputs['Vector']).inputs['A'])==blend for n in ao))
        taps=[n for n in t.nodes if n.name.startswith('EmissiveMap_Parallax')]
        check('ParallaxEmit_Blur averages four jitter taps',len(taps)==nodes.PARALLAX_BLUR_TAPS and any(n.bl_idname=='ShaderNodeGroup' and n.node_tree.name=='REAverage4_v1' for n in t.nodes))
        mult=sorted(round(n.inputs[1].default_value,4) for n in t.nodes if n.bl_idname=='ShaderNodeMath' and n.operation=='MULTIPLY' and n.inputs[0].is_linked and source(n.inputs[0]).bl_idname=='ShaderNodeClamp')
        check('tap dithers sit at Blend*(k+0.5)/4',mult==[.125,.375,.625,.875],mult)
        rt={'UV_Tile':[2],'UV_Tile_Offset':[1,1,0,0],'RoughTransparent_Color':[.2,.5,.8,1],'AlphaAdjust':[.5]}
        t=run([entry('RT','BaseAlpha_Emit_RoughTransparent.mmtr',rt,('BaseAlphaMap','NormalRoughnessOcclusionMap','EmissiveMap','FxMap'))])['RT']
        tile=t.nodes.get('MHWilds UV Tile')
        check('UV_Tile feeds NRRO, BaseAlphaMap, EmissiveMap and FxMap',tile is not None and all(source(t.nodes[n].inputs['Vector'])==tile for n in ('NormalRoughnessOcclusionMap','BaseAlphaMap','EmissiveMap','FxMap') if n in t.nodes))
        tint=t.nodes.get('MHWilds RoughTransparent Tint');out=next(n for n in t.nodes if n.bl_idname=='ShaderNodeOutputMaterial')
        bsdf=next(n for n in t.nodes if n.bl_idname=='ShaderNodeBsdfPrincipled')
        def reaches(socket,target,depth=0):
            n=source(socket)
            return n==target or (n is not None and depth<10 and any(reaches(i,target,depth+1) for i in n.inputs if i.is_linked))
        check('RoughTransparent_Color tints the transparent part through a shader mix',tint is not None and source(tint.inputs['Color']).name=='RoughTransparent_Color' and reaches(out.inputs['Surface'],tint) and not bsdf.inputs['Alpha'].is_linked)
        anti={'Use_AntiTranslucent_Diffuse':[1],'TranslucentParam':[.5],'Use_RimTranslucent':[1],'RimTranslucent_NormalBlend':[.5],'RimTrasnlucent_Power':[2]}
        t=run([entry('Anti','Base_Equip_NoMultiBlend.mmtr',anti,('BaseDielectricMap','NormalRoughnessOcclusionMap','AlphaTranslucentOcclusionSSSMap'))])['Anti']
        node=t.nodes.get('MHWilds AntiTranslucent Diffuse');bsdf=next(n for n in t.nodes if n.bl_idname=='ShaderNodeBsdfPrincipled')
        check('Use_AntiTranslucent_Diffuse adjusts the albedo that reaches the BSDF',node is not None and reaches(bsdf.inputs['Base Color'],node) and source(node.inputs['TranslucentParam']).name=='TranslucentParam')
        check('AntiTranslucent reads the shading normal and roughness',node.inputs['Shading Normal'].is_linked and node.inputs['Roughness'].is_linked)
        out=next(n for n in t.nodes if n.bl_idname=='ShaderNodeOutputMaterial');material=bpy.data.materials['Anti']
        drivers=[d for d in (t.animation_data.drivers if t.animation_data else []) if d.data_path=='nodes["Backface Culling"].inputs[1].default_value']
        target=drivers[0].driver.variables[0].targets[0] if drivers else None
        check('the surface goes through the backface culling mix, driven by the material checkbox',source(out.inputs['Surface']).name=='Backface Culling Mix' and target is not None and target.id==material and target.data_path=='use_backface_culling')
    finally:
        for n,v in saved.items():setattr(main,n,v)
finally:
    results['passed']=bool(results['checks']) and all(c['passed'] for c in results['checks'])
    if args.report:args.report.write_text(json.dumps(results,indent=2),encoding='utf-8')
print('SHADING_FIXES_SUMMARY '+json.dumps({'passed':results['passed'],'checks':len(results['checks'])}),flush=True)
