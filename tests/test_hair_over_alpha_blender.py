"""Independent oracle of Wilds HairOver and hair edge/AO alpha vs Cycles/EEVEE pixels, plus importer wiring.
blender --background --factory-startup --python-exit-code 1 --python FILE -- [--report JSON]
"""
import argparse,importlib,json,math,sys,tempfile
from pathlib import Path
import addon_utils,bpy,numpy as np
parser=argparse.ArgumentParser();parser.add_argument('--report',type=Path)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
addon=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(addon.parent));addon_utils.enable(addon.name,default_set=True)
main=importlib.import_module(addon.name+'.modules.mdf.blender_re_mesh_mdf')
hair=importlib.import_module(addon.name+'.modules.mdf.blender_mhwilds_hair')
mdf=importlib.import_module(addon.name+'.modules.mdf.file_re_mdf')
results={'blender':bpy.app.version_string,'checks':[]}
def check(name,ok,detail=None):
    results['checks'].append({'name':name,'passed':bool(ok),'detail':detail});print(('PASS ' if ok else 'FAIL ')+name,flush=True)
    assert ok,(name,detail)
sat=lambda x:min(max(x,0.0),1.0)
smooth=lambda x:sat(x)**2*(3-2*sat(x))
#Oracles written from shader #64 / Base_Equip #65 text, not from the node builder
def over_oracle(c):
    if c['use']<=0:return np.ones(3)
    k=c['contrast'];t=sat(k-(k+1)*(1-c['shift'])+c['ho'][3]);t=sat(t/(1e-4 if k==0 else k))
    s=smooth(t);a,b=np.array(c['A'][:3]),np.array(c['B'][:3])
    return 2*(b+(a-b)*s)*np.array(c['ho'][:3])
def alpha_oracle(c,facing):
    a=c['alpha']
    if c['default']>0:return a
    boost=3*sat(2*a)-a-2*sat(2*a-1)
    a1=a+(1-sat(c['ao']))*c['aofade']*boost
    w=c['width'];e=sat(w-(1-c['fade'])*(w+1)+facing);e=sat(e/(1e-4 if w==0 else w))
    return smooth(e)*a1
overs=[dict(name='mask mid',use=1,contrast=2,shift=.5,A=(.9,.3,.2,1),B=(.1,.4,.8,1),ho=(.8,.7,.6,.55)),
       dict(name='low contrast',use=1,contrast=.3,shift=.2,A=(.2,.9,.4,1),B=(.7,.1,.5,1),ho=(.5,.9,.4,.3)),
       dict(name='zero contrast uses 1e-4',use=1,contrast=0,shift=.6,A=(.3,.3,.9,1),B=(.9,.6,.1,1),ho=(.6,.6,.6,.7)),
       dict(name='off gives 2 x 0.5',use=0,contrast=2,shift=.5,A=(.9,.3,.2,1),B=(.1,.4,.8,1),ho=(.8,.7,.6,.55))]
alphas=[dict(name='AO fade + edge',alpha=.6,ao=.4,aofade=.7,width=.5,fade=.6,default=0),
        dict(name='low alpha boost',alpha=.3,ao=.2,aofade=1,width=.2,fade=.9,default=0),
        dict(name='zero width',alpha=.8,ao=1,aofade=.5,width=0,fade=.3,default=0),
        dict(name='Use_DefaultAlpha keeps alpha',alpha=.45,ao=.1,aofade=1,width=.5,fade=.1,default=1)]
scratch=tempfile.TemporaryDirectory(prefix='reme_hairover_');root=Path(scratch.name)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_plane_add(size=2);plane=bpy.context.object;plane.data.uv_layers.active.name='UVMap0'
scene=bpy.context.scene;scene.cycles.device='CPU';scene.cycles.samples=1;scene.cycles.use_denoising=False
camdata=bpy.data.cameras.new('cam');cam=bpy.data.objects.new('cam',camdata);scene.collection.objects.link(cam);camdata.type='ORTHO';camdata.ortho_scale=.5;cam.location=(0,0,3);scene.camera=cam
scene.render.resolution_x=scene.render.resolution_y=8;scene.render.image_settings.file_format='OPEN_EXR';scene.render.image_settings.color_depth='32'
mat=bpy.data.materials.new('oracle');mat.use_nodes=True;plane.data.materials.append(mat);nt=mat.node_tree;nt.nodes.clear()
out=nt.nodes.new('ShaderNodeOutputMaterial');emit=nt.nodes.new('ShaderNodeEmission');nt.links.new(emit.outputs[0],out.inputs['Surface'])
og=nt.nodes.new('ShaderNodeGroup');og.node_tree=hair.hairOverNodeGroup()
ag=nt.nodes.new('ShaderNodeGroup');ag.node_tree=hair.hairAlphaNodeGroup()
grey=nt.nodes.new('ShaderNodeCombineColor')
nt.links.new(ag.outputs['Alpha'],grey.inputs[0]);nt.links.new(ag.outputs['Alpha'],grey.inputs[1]);nt.links.new(ag.outputs['Alpha'],grey.inputs[2])
def render(engine):
    scene.render.engine=engine;scene.render.filepath=str(root/'s.exr');bpy.ops.render.render(write_still=True)
    im=bpy.data.images.load(scene.render.filepath,check_existing=False);v=np.array(im.pixels[:]).reshape(8,8,4)[4,4,:3].copy();bpy.data.images.remove(im);return v
try:
    for engine,tol in (('CYCLES',2e-3),('BLENDER_EEVEE',4e-3)):
        nt.links.new(og.outputs['Factor'],emit.inputs['Color']);plane.rotation_euler=(0,0,0)
        for c in overs:
            og.inputs['Hair Over'].default_value=c['ho'];og.inputs['Hair Over Alpha'].default_value=c['ho'][3]
            og.inputs['UseHairOverMap'].default_value=c['use'];og.inputs['Color A'].default_value=c['A'];og.inputs['Color B'].default_value=c['B']
            og.inputs['Contrast'].default_value=c['contrast'];og.inputs['Shift'].default_value=c['shift']
            got,want=render(engine),over_oracle(c)
            check(f'{engine} HairOver {c["name"]}',np.abs(got-want).max()<tol,{'got':got.round(5).tolist(),'want':want.round(5).tolist()})
        nt.links.new(grey.outputs['Color'],emit.inputs['Color'])
        for c in alphas:
            for angle in (0,60,80):
                plane.rotation_euler=(math.radians(angle),0,0)
                for key,socket in (('alpha','Alpha'),('ao','AO'),('aofade','AO_Fade_Alpha'),('width','EdgeWidth'),('fade','EdgeFade'),('default','Use_DefaultAlpha')):
                    ag.inputs[socket].default_value=c[key]
                got,want=render(engine)[0],alpha_oracle(c,math.cos(math.radians(angle)))
                check(f'{engine} hair alpha {c["name"]} at {angle} deg',abs(got-want)<tol,{'got':round(float(got),5),'want':round(want,5)})
    check('oracle: edge-on cards fade out',alpha_oracle(alphas[0],math.cos(math.radians(80)))<alpha_oracle(alphas[0],1.0))

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
    def run(entries,game):
        f=mdf.MDFFile();f.fileVersion=45;f.materialList=entries
        mats={e.materialName:bpy.data.materials.new(e.materialName) for e in entries}
        main.importMDF(f,mats,False,False,False,False,chunkPath='',gameName=game);return mats
    over={'UseHairOverMap':[1],'PrimaryUV_OverMap':[0],'HairOverColorA':[.2,.2,.2,1],'HairOverColorB':[.4,.4,.4,1],'HairOverColorA_B_Contrast':[1],'HairOverColorA_B_Shift':[.5]}
    fade={'AO_Fade_Alpha':[.5],'EdgeWidth':[.3],'EdgeFade':[.4],'Use_DefaultAlpha':[0],'AlphaAdjust':[.5],'DeepShadowColor':[1,1,1,.6]}
    try:
        mats=run([entry('Wilds hair','Base_ATOS_VFX_Hair_NoPDO.mmtr',{**over,**fade},('BaseAlphaMap','NormalRoughnessOcclusionMap','HairOverMap')),
                  entry('Wilds equip','Base_Equip_NoMultiBlend.mmtr',over,('BaseDielectricMap','NormalRoughnessOcclusionMap','HairOverMap'))],'MHWILDS')
        for name in ('Wilds hair','Wilds equip'):
            t=mats[name].node_tree;node=t.nodes.get('MHWilds Hair Over')
            check(f'{name}: HairOver group multiplies the base color',node is not None and any(l.from_node==node for l in t.links))
            src=lambda s:node.inputs[s].links[0].from_node.name if node.inputs[s].is_linked else None
            check(f'{name}: HairOver parameters come through property nodes',src('Contrast')=='HairOverColorA_B_Contrast' and src('Shift')=='HairOverColorA_B_Shift' and src('UseHairOverMap')=='UseHairOverMap')
            vector=t.nodes['HairOverMap'].inputs['Vector']
            check(f'{name}: PrimaryUV_OverMap selects the HairOverMap UV',vector.is_linked and vector.links[0].from_node.bl_idname=='ShaderNodeMix')
        t=mats['Wilds hair'].node_tree;alpha=t.nodes.get('MHWilds Hair Alpha')
        check('hair alpha group feeds the alpha chain',alpha is not None and alpha.outputs['Alpha'].is_linked and all(alpha.inputs[s].is_linked for s in ('Use_DefaultAlpha','AO_Fade_Alpha','EdgeWidth','EdgeFade')))
        lift=t.nodes.get('MHWilds Hair AO Lift');occ=t.nodes.get('MHWildsOcclusion')
        check('hair lifts the AO that darkens the base color to lerp(AO, 1, DeepShadow.a)',lift is not None and lift.outputs['Result'].is_linked and lift.inputs['Factor'].links[0].from_node.name=='DeepShadowColor' and lift.inputs['Factor'].links[0].from_socket.name=='Alpha')
        check('hair alpha keeps the raw AO',alpha.inputs['AO'].links[0].from_node==occ)
        check('equipment AO is not lifted',mats['Wilds equip'].node_tree.nodes.get('MHWilds Hair AO Lift') is None)
        check('equipment without edge parameters gets no hair alpha',mats['Wilds equip'].node_tree.nodes.get('MHWilds Hair Alpha') is None)
        other=run([entry('RE4 hair over','Hair.mmtr',over,('BaseDielectricMap','HairOverMap'))],'RE4')['RE4 hair over'].node_tree
        check('other games keep the previous HairOver mix',other.nodes.get('MHWilds Hair Over') is None)
    finally:
        for n,v in saved.items():setattr(main,n,v)
finally:
    results['passed']=bool(results['checks']) and all(c['passed'] for c in results['checks'])
    if args.report:args.report.write_text(json.dumps(results,indent=2),encoding='utf-8')
print('HAIR_OVER_ALPHA_SUMMARY '+json.dumps({'passed':results['passed'],'checks':len(results['checks'])}),flush=True)
