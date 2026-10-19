"""Independent numpy oracle of the traced hair lobes vs real Cycles/EEVEE pixels, plus importer gating and aliases.
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
hair=importlib.import_module(addon.name+'.modules.mdf.blender_mhwilds_hair')
mdf=importlib.import_module(addon.name+'.modules.mdf.file_re_mdf')
results={'blender':bpy.app.version_string,'checks':[]}
def check(name,ok,detail=None):
    results['checks'].append({'name':name,'passed':bool(ok),'detail':detail});print(('PASS ' if ok else 'FAIL ')+name,flush=True)
    assert ok,(name,detail)

#Oracle written from the shader text (DXIL %748..%909), not from the node builder.
def oracle(c,side,mirror):
    n=np.array([0,0,1.0]) if side=='front' else np.array([0,0,-1.0])
    incoming=n.copy()#orthographic camera looking straight at the face
    t=np.array([-1.0 if mirror else 1.0,0,0])
    b=np.array([0,-1.0,0])#RE bitangent: +V in D3D UV space is -Y on this plane, on both faces
    norm=lambda v:v/np.linalg.norm(v)
    sat=lambda x:min(max(x,0.0),1.0)
    S=lambda x:sat(x)**2*(3-2*sat(x))
    f=2*np.array(c['flow'][:3])-0.9960784316062927
    d=norm(t*f[0]+b*f[1]+n*f[2]) if c['UseFlowMap']>0 else b
    shift=2*c['hss'][2]-0.9960784316062927
    d1=norm(d+(c['PA']-c['PS']*shift)*n);d2=norm(d+(c['SA']-c['SS'])*n)
    L=np.array([c['L'][0],-c['L'][2],c['L'][1]])
    q=norm(L+incoming)
    j=min(max(float(n@L),1e-5),1.0)
    def lobe(di,e,g):
        u=float(di@q);return S(g)*S(u+1)*max(1-u*u,0)**(e/2)
    p1=lobe(d1,c['PSharp'],sat(j));p2=lobe(d2,c['SSharp'],sat((j+1)*.5))
    ao=sat(c['AO']);c0=np.array(c['base'][:3]);ds=np.array(c['ds'][:3])
    col=c0+(c0*(ds+(1-ds)*ao)-c0)*c['ds'][3]
    w=c['hss'][1]*(2*ao+(1-2*ao)*c['spec'][3])
    return col*c['fade']+w*c.get('mask',1.0)*(p1*np.array(c['spec'][:3])+col*c['SI']*p2)

cases=[
 dict(name='flow off, default bitangent',UseFlowMap=0,flow=(.5,.5,1,1),hss=(0,1,.5,1),PA=.1,SA=.1,PS=.3,SS=-.2,PSharp=40,SSharp=12,spec=(1,.9,.8,.5),SI=.6,ds=(.3,.2,.1,.5),AO=.8,fade=1,base=(.4,.3,.2,1),L=(.3,.6,.4)),
 dict(name='flow on, oblique strands',UseFlowMap=1,flow=(.8,.3,.6,1),hss=(0,.7,.2,1),PA=-.2,SA=-.2,PS=.5,SS=.3,PSharp=80,SSharp=20,spec=(.9,1,1,.2),SI=1.4,ds=(.5,.4,.6,1),AO=.4,fade=.7,base=(.6,.5,.4,1),L=(-.5,.4,.2)),
 dict(name='HSS green zero removes both lobes',UseFlowMap=1,flow=(.6,.6,.7,1),hss=(0,0,.8,1),PA=.1,SA=.1,PS=.2,SS=.1,PSharp=30,SSharp=10,spec=(1,1,1,1),SI=2,ds=(1,1,1,0),AO=1,fade=1,base=(.3,.3,.3,1),L=(.2,.9,.1)),
 dict(name='vertex alpha mask 0.4',mask=.4,UseFlowMap=1,flow=(.8,.3,.6,1),hss=(0,.7,.2,1),PA=-.2,SA=-.2,PS=.5,SS=.3,PSharp=80,SSharp=20,spec=(.9,1,1,.2),SI=1.4,ds=(.5,.4,.6,1),AO=.4,fade=.7,base=(.6,.5,.4,1),L=(-.5,.4,.2)),
 dict(name='separate secondary anisotropy',UseFlowMap=0,flow=(.5,.5,1,1),hss=(0,1,.6,1),PA=.3,SA=-.4,PS=.1,SS=.2,PSharp=20,SSharp=6,spec=(.7,.8,.9,.8),SI=.9,ds=(.2,.2,.2,.3),AO=.6,fade=.9,base=(.5,.4,.3,1),L=(.1,.3,.9)),
]
inputs={'UseFlowMap':'UseFlowMap','PA':'Primary Anisotropy','SA':'Secondary Anisotropy','PS':'Primary Shift Offset','SS':'Secondary Shift Offset',
        'PSharp':'Primary Sharpness','SSharp':'Secondary Sharpness','SI':'Secondary Intensity','AO':'AO','fade':'Basecolor Fade'}

scratch=tempfile.TemporaryDirectory(prefix='reme_hair_');root=Path(scratch.name)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_plane_add(size=2);plane=bpy.context.object;uv=plane.data.uv_layers.active;uv.name='UVMap0'
original_uv=[tuple(p.uv) for p in uv.data]
scene=bpy.context.scene;scene.cycles.device='CPU';scene.cycles.samples=1;scene.cycles.use_denoising=False
camdata=bpy.data.cameras.new('Hair test');cam=bpy.data.objects.new('Hair test',camdata);scene.collection.objects.link(cam);camdata.type='ORTHO';camdata.ortho_scale=1;scene.camera=cam
scene.render.resolution_x=scene.render.resolution_y=8;scene.render.image_settings.file_format='OPEN_EXR';scene.render.image_settings.color_depth='32'
mat=bpy.data.materials.new('Hair oracle');mat.use_nodes=True;plane.data.materials.append(mat);nt=mat.node_tree;nt.nodes.clear()
out=nt.nodes.new('ShaderNodeOutputMaterial');emit=nt.nodes.new('ShaderNodeEmission');nt.links.new(emit.outputs[0],out.inputs['Surface'])
group=nt.nodes.new('ShaderNodeGroup');group.node_tree=hair.hairSpecularNodeGroup();nt.links.new(group.outputs['Color'],emit.inputs['Color'])
def image(name):
    im=bpy.data.images.new(name,1,1,alpha=True,float_buffer=True);im.colorspace_settings.name='Non-Color';im.alpha_mode='CHANNEL_PACKED'
    node=nt.nodes.new('ShaderNodeTexImage');node.image=im;return im,node
flowImage,flowNode=image('HF');hssImage,hssNode=image('HSS')
nt.links.new(flowNode.outputs['Color'],group.inputs['Hair Flow']);nt.links.new(hssNode.outputs['Color'],group.inputs['Spec Mask Shift'])
def render(c,side,mirror,engine):
    flowImage.pixels=list(c['flow']);hssImage.pixels=list(c['hss'])
    for key,socket in inputs.items():group.inputs[socket].default_value=c[key]
    group.inputs['Primary Specular Color'].default_value=c['spec'];group.inputs['Primary Specular Alpha'].default_value=c['spec'][3]
    group.inputs['Deep Shadow Color'].default_value=c['ds'];group.inputs['Deep Shadow Alpha'].default_value=c['ds'][3]
    group.inputs['Base Color'].default_value=c['base'];group.inputs['Vertex Mask'].default_value=c.get('mask',1.0)
    for axis,value in zip('XYZ',c['L']):group.inputs['Light '+axis].default_value=value
    for p,(u,v) in zip(uv.data,original_uv):p.uv=(1-u if mirror else u,v)
    cam.location=(0,0,2 if side=='front' else -2);cam.rotation_euler=(0,0,0) if side=='front' else (3.141592653589793,0,0)
    scene.render.engine=engine;scene.render.filepath=str(root/'hair.exr');bpy.ops.render.render(write_still=True)
    im=bpy.data.images.load(scene.render.filepath,check_existing=False);v=np.array(im.pixels[:]).reshape(8,8,4)[4,4,:3].copy();bpy.data.images.remove(im);return v

try:
    for engine,tolerance in (('CYCLES',2e-3),('BLENDER_EEVEE',4e-3)):
        for c in cases:
            for side,mirror in (('front',False),('back',False),('front',True)):
                got=render(c,side,mirror,engine);want=oracle(c,side,mirror)
                check(f'{engine} {c["name"]} {side}{" mirrored UV" if mirror else ""}',np.abs(got-want).max()<tolerance,{'got':got.round(5).tolist(),'want':want.round(5).tolist()})
    zero=oracle(cases[2],'front',False);check('oracle: HSS.G = 0 leaves only the faded base color',np.allclose(zero,np.array(cases[2]['base'][:3])*cases[2]['fade']))
    moved=dict(cases[0]);moved['hss']=(0,1,.9,1);a,b=oracle(cases[0],'front',False),oracle(moved,'front',False)
    check('oracle: HSS.B moves the primary lobe only',not np.allclose(a,b))

    #Importer: slot + parameter gating, aliases, live property nodes
    good=bpy.data.images.new('good',1,1,alpha=True);good.generated_color=(.5,.5,1,1)
    names=('Texconv','unload_texconv','getTexPath','loadTex','getChunkPathList')
    saved={n:getattr(main,n) for n in names}
    main.Texconv=lambda:None;main.unload_texconv=lambda:None;main.getChunkPathList=lambda game:[]
    main.getTexPath=lambda base,*a,**k:base;main.loadTex=lambda *a,**k:[good]
    def entry(name,props,slots=('BaseDielectricMap','HairFlowMap','Hair_Height_SpecMask_Shift_Map')):
        m=mdf.Material();m.materialName=name;m.mmtrPath='MaterialShader/Variation/Base_ATOS_VFX_Hair_NoPDO.mmtr';m.shaderType=0;m.textureList=[];m.propertyList=[]
        for s in slots:
            t=mdf.TextureBinding();t.textureType=s;t.texturePath=s+'.tex';m.textureList.append(t)
        for k,v in props.items():
            p=mdf.Property();p.propName=k;p.paramCount=len(v);p.propValue=list(v);m.propertyList.append(p)
        return m
    def run(entries,game,existing=None):
        f=mdf.MDFFile();f.fileVersion=45;f.materialList=entries
        mats=existing or {e.materialName:bpy.data.materials.new(e.materialName) for e in entries}
        main.importMDF(f,mats,False,False,False,False,chunkPath='',gameName=game);return mats
    wilds={'PrimalySpec_Sharpness':[40],'SecondarySpec_Sharpness':[10],'LightDirection':[.3,.6,.4,0],'Primaly_Anisotropy':[.1],'Specular_ShiftOffset':[.3],
           'Secondary_ShiftOffset':[-.2],'PrimalySpecularColor':[1,.9,.8,.5],'Secondary_Specular_Intensity':[.6],'DeepShadowColor':[.3,.2,.1,.5],'Basecolor_Fade':[1],'UseFlowMap':[1]}
    oni={'PrimarySpec_Sharpness':[40],'SecondarySpec_Sharpness':[10],'LightDirection':[.3,.6,.4,0],'Primary_Anisotropy':[.1],'Secondary_Anisotropy':[-.3],
         'Primary_Specular_ShiftOffset':[.3],'Secondary_Specular_ShiftOffset':[-.2],'Primary_Specular_Color':[1,.9,.8,.5],'BaseColor_Fade':[1],'UseFlowMap':[1]}
    try:
        mats=run([entry('Wilds hair',wilds),entry('No lobe params',{}),entry('Only HSS',wilds,('BaseDielectricMap','Hair_Height_SpecMask_Shift_Map'))],'MHWILDS')
        w=mats['Wilds hair'].node_tree;node=w.nodes.get('RE Hair Specular')
        check('slots + lobe parameters build the hair node',node is not None)
        src=lambda socket:node.inputs[socket].links[0].from_node.name if node.inputs[socket].is_linked else None
        check('Wilds second lobe starts from Primaly_Anisotropy',src('Secondary Anisotropy')=='Primaly_Anisotropy' and src('Primary Sharpness')=='PrimalySpec_Sharpness')
        check('parameters arrive through named property nodes (live editing)',all(src(s) for s in ('Light X','Light Z','Primary Specular Color','Deep Shadow Alpha','Basecolor Fade')))
        check('hair color replaces the base color going to the BSDF',any(l.from_node==node for l in w.links))
        check('slots without lobe parameters stay ordinary',mats['No lobe params'].node_tree.nodes.get('RE Hair Specular') is None)
        check('HSS without HairFlowMap stays ordinary',mats['Only HSS'].node_tree.nodes.get('RE Hair Specular') is None)
        masked=dict(wilds,UseVertexColor_mask=[1])
        def mesh_with(name,colors):
            me=bpy.data.meshes.new(name);me.from_pydata([(0,0,0),(1,0,0),(0,1,0)],[],[(0,1,2)])
            if colors:me.color_attributes.new('Col','BYTE_COLOR','CORNER')
            mat=bpy.data.materials.new(name);me.materials.append(mat);ob=bpy.data.objects.new(name,me);scene.collection.objects.link(ob);return mat
        withCol=run([entry('Masked hair',masked)],'MHWILDS',{'Masked hair':mesh_with('Masked hair',True)})['Masked hair'].node_tree
        node=withCol.nodes['RE Hair Specular']
        chain=node.inputs['Vertex Mask'].links[0].from_node if node.inputs['Vertex Mask'].is_linked else None
        check('UseVertexColor_mask feeds Col alpha into the lobe mask',chain is not None and any(l.from_node.bl_idname=='ShaderNodeVertexColor' and l.from_node.layer_name=='Col' and l.from_socket.name=='Alpha' for l in chain.inputs['B'].links) and any(n.name=='UseVertexColor_mask' for n in withCol.nodes))
        noCol=run([entry('Masked no colors',masked)],'MHWILDS',{'Masked no colors':mesh_with('Masked no colors',False)})['Masked no colors'].node_tree
        check('meshes without a Col layer keep mask 1 instead of erasing the lobes',not noCol.nodes['RE Hair Specular'].inputs['Vertex Mask'].is_linked)
        o=run([entry('Onimusha hair',oni)],'ONI')['Onimusha hair'].node_tree;node=o.nodes.get('RE Hair Specular')
        check('Onimusha spelling builds the same node in another game',node is not None and src('Primary Anisotropy')=='Primary_Anisotropy' and src('Secondary Anisotropy')=='Secondary_Anisotropy' and src('Basecolor Fade')=='BaseColor_Fade')
    finally:
        for n,v in saved.items():setattr(main,n,v)
finally:
    results['passed']=bool(results['checks']) and all(c['passed'] for c in results['checks'])
    if args.report:args.report.write_text(json.dumps(results,indent=2),encoding='utf-8')
print('HAIR_TEST_SUMMARY '+json.dumps({'passed':results['passed'],'checks':len(results['checks'])}),flush=True)
