"""Synthetic render + actual MDF importer checks. No game textures or saved scenes.
blender --background --factory-startup --python-exit-code 1 --python tests/test_mhwilds_ao_alpha_blender.py
Optional -- --staged ROOT --report JSON tests staged modules before installation.
"""
import argparse,importlib,json,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
import bpy
import numpy as np
import addon_utils

cli=argparse.ArgumentParser();cli.add_argument('--staged',type=Path);cli.add_argument('--report',type=Path)
args=cli.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
installed=Path(r'C:\Users\Sheeran\AppData\Roaming\Blender Foundation\Blender\5.1\scripts\addons\RE-Mesh-Editor-MeshFixes') if args.staged else Path(__file__).resolve().parents[1]
sys.path.insert(0,str(installed.parent));addon_utils.enable(installed.name,default_set=True)
nodes=importlib.import_module(installed.name+'.modules.mdf.blender_nodes_re_mdf')
main=importlib.import_module(installed.name+'.modules.mdf.blender_re_mesh_mdf')
mdf=importlib.import_module(installed.name+'.modules.mdf.file_re_mdf')
props=importlib.import_module(installed.name+'.modules.mdf.re_mdf_propertyGroups')
if args.staged:
    for module,relative in [(nodes,'modules/mdf/blender_nodes_re_mdf.py'),(main,'modules/mdf/blender_re_mesh_mdf.py')]:
        exec(compile((args.staged/relative).read_text(encoding='utf8'),str(args.staged/relative),'exec'),module.__dict__)
    props.editablePropsSet.update(nodes.MHWILDS_LIVE_PROPS)
results={'blender':bpy.app.version_string,'staged':str(args.staged) if args.staged else None,'checks':[]}
def check(name,ok,detail=None):
    results['checks'].append({'name':name,'passed':bool(ok),'detail':detail});print(('PASS ' if ok else 'FAIL ')+name+(' '+str(detail) if detail is not None else ''),flush=True)

bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=1;scene.cycles.use_denoising=False
scene.render.resolution_x=16;scene.render.resolution_y=16;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='OPEN_EXR';scene.render.image_settings.color_mode='RGBA';scene.render.image_settings.color_depth='32'
data=bpy.data.cameras.new('AO test');camera=bpy.data.objects.new('AO test',data);scene.collection.objects.link(camera);camera.location=(0,0,2);data.type='ORTHO';data.ortho_scale=2;scene.camera=camera
bpy.ops.mesh.primitive_plane_add(size=2);plane=bpy.context.object
uv0=plane.data.uv_layers.active;uv0.name='UVMap0';uv1=plane.data.uv_layers.new(name='UVMap1')
for d in uv0.data:d.uv=(0.25,0.5)
for d in uv1.data:d.uv=(0.75,0.5)
plane.data.uv_layers.active=uv0
scratch=tempfile.TemporaryDirectory(prefix='reme_ao_alpha_')
def render(mat,socket):
    nt=mat.node_tree;output=next(n for n in nt.nodes if n.type=='OUTPUT_MATERIAL')
    emit=nt.nodes.get('TEST_EMIT')
    if emit is None:emit=nt.nodes.new('ShaderNodeEmission');emit.name='TEST_EMIT'
    nt.links.new(socket,emit.inputs['Color']);nt.links.new(emit.outputs[0],output.inputs['Surface'])
    plane.data.materials.clear();plane.data.materials.append(mat)
    path=Path(scratch.name)/'probe.exr';scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)
    image=bpy.data.images.load(str(path),check_existing=False);image.colorspace_settings.name='Non-Color'
    a=np.empty(len(image.pixels),dtype=np.float32);image.pixels.foreach_get(a);value=a.reshape(16,16,4)[8,8,:3].copy();bpy.data.images.remove(image)
    return value
def pack(nt,*sockets):
    n=nt.nodes.new('ShaderNodeCombineColor')
    for i,s in enumerate(sockets):
        if isinstance(s,(int,float)):n.inputs[i].default_value=s
        else:nt.links.new(s,n.inputs[i])
    return n.outputs[0]
pixel_payloads={}
def image(name,left,right):
    im=bpy.data.images.new(name,2,1,alpha=True,float_buffer=True);im.colorspace_settings.name='Non-Color';im.alpha_mode='CHANNEL_PACKED';pixel_payloads[im.name]=[*left,*right];im.pixels.foreach_set(pixel_payloads[im.name]);im.update();return im
images={
    'base':[image('base',[.7,.6,.5,1],[.4,.3,.2,1])],
    'nrro':[image('nrro',[.25,.6,.8,.5],[.85,.9,.3,.6])],
    'atos':[image('atos',[.2,0,.4,1],[.8,0,.7,1])],
    'alba':[image('alba',[.7,.6,.5,.25],[.4,.3,.2,.75])],
    'array':[image('array0',[.25,.6,.8,.5],[.85,.9,.3,.6]),image('array1',[.45,.5,.6,.5],[.65,.7,.1,.5])],
}
originals=(main.Texconv,main.unload_texconv,main.getTexPath,main.loadTex,main.showErrorMessageBox)
main.Texconv=lambda:None;main.unload_texconv=lambda:None;main.getTexPath=lambda base,*a,**k:base
main.loadTex=lambda path,*a,**k:images[path]
def error(message):raise AssertionError(message)
main.showErrorMessageBox=error
def fixture(game='MHWILDS',alba=False,array=False,blend=False,matcap=False,legacy_uv=False):
    file=mdf.MDFFile();file.fileVersion=45
    material=mdf.Material();material.materialName='Fixture';material.shaderType=4 if blend else 0
    material.mmtrPath='MaterialShader/Variation/'+('BaseAlpha_MatCap_FX.mmtr' if matcap else 'Base_ATOS_VFX_Hair_NoPDO.mmtr' if alba else 'Base_ATOS_SkinEdit_VFX.mmtr')
    material.flags.flagValues.AlphaTestEnable=1
    values={'ColorParam':[1,1,1,.8],'ChangeUV':[0],'UseAOSecondaryUV':[0],'OcclusionParam':[.75],'AlphaAdjust':[.25],'AlphaTest_Ref':[.5],'UseTempDither':[0]}
    if legacy_uv:values['Alpha_UseSecondaryUV']=[1]
    material.propertyList=[]
    for name,value in values.items():
        p=mdf.Property();p.propName=name;p.paramCount=len(value);p.propValue=value;material.propertyList.append(p)
    material.textureList=[]
    for slot,path in [('BaseAlphaMap' if alba else 'BaseDielectricMap','alba' if alba else 'base'),('NormalRoughnessOcclusionMap','array' if array else 'nrro'),('AlphaTranslucentOcclusionSSSMap','atos')]:
        t=mdf.TextureBinding();t.textureType=slot;t.texturePath=path+'.tex';material.textureList.append(t)
    file.materialList=[material]
    mat=bpy.data.materials.new('Fixture');mat.use_nodes=True
    main.importMDF(file,{'Fixture':mat},False,False,False,True,chunkPath='',gameName=game)
    #Generated images have no source file to restore from when image color settings
    #are refreshed by the importer. Restore their synthetic pixels after that refresh.
    for group in images.values():
        for im in group:im.pixels.foreach_set(pixel_payloads[im.name]);im.update()
    for n in mat.node_tree.nodes:
        if n.type=='TEX_IMAGE':n.interpolation='Closest'
    return mat
def update(mat,name,value):
    check(name+' registered for live preview',name in props.editablePropsSet)
    fake=SimpleNamespace(id_data=SimpleNamespace(re_mdf_material=SimpleNamespace(linkedMaterial=mat)),prop_name=name,data_type='FLOAT',float_value=float(value))
    props.update_materialNodes(fake,None)
def diagnostics(mat):
    nt=mat.node_tree;decode=next(n for n in nt.nodes if n.type=='GROUP' and n.node_tree.name=='MHWildsNRRODecode_v1')
    coverage=nt.nodes['MHWildsAlphaCoverage']
    return pack(nt,decode.outputs['Roughness'],nt.nodes['MHWildsOcclusion'].outputs[0],coverage.inputs['Alpha'].links[0].from_socket)
try:
    mat=fixture();nt=mat.node_tree
    source=nt.nodes['NormalRoughnessOcclusionMap'];secondary=nt.nodes['AO_NormalRoughnessOcclusionMap']
    check('normal/roughness and AO have distinct UV sockets',source.inputs['Vector'].links[0].from_socket!=secondary.inputs['Vector'].links[0].from_socket)
    check('ATOS AO has an independent sample',nt.nodes.get('AO_AlphaTranslucentOcclusionSSSMap') is not None)
    bsdf=next(n for n in nt.nodes if n.type=='BSDF_PRINCIPLED')
    check('coverage is wired into the material surface alpha',bsdf.inputs['Alpha'].links[0].from_node==nt.nodes['MHWildsAlphaCoverage'])
    for change,ao_switch,expected in [(0,0,[.25,.55,.08]),(0,1,[.25,.475,.08]),(1,0,[.85,.475,.56]),(1,1,[.85,.475,.56]),(0,.2,[.25,.475,.08]),(-1,-1,[.25,.55,.08])]:
        update(mat,'ChangeUV',change);update(mat,'UseAOSecondaryUV',ao_switch)
        actual=render(mat,diagnostics(mat));e=float(np.max(np.abs(actual-np.array(expected))))
        check('render UV/AO/alpha '+str((change,ao_switch)),e<5e-5,{'actual':actual.tolist(),'max_error':e})
    update(mat,'ChangeUV',0);update(mat,'UseAOSecondaryUV',0)
    decode=next(n for n in nt.nodes if n.type=='GROUP' and n.node_tree.name=='MHWildsNRRODecode_v1')
    normal_before=render(mat,decode.outputs['Color']);update(mat,'UseAOSecondaryUV',1)
    normal_after=render(mat,decode.outputs['Color']);check('rendered decoded normal is unchanged when only AO switches UV',np.max(np.abs(normal_after-normal_before))<5e-5)
    update(mat,'UseAOSecondaryUV',0)
    update(mat,'OcclusionParam',0);actual=render(mat,nt.nodes['MHWildsOcclusion'].outputs[0]);check('OcclusionParam 0 disables texture occlusion',np.max(np.abs(actual-1))<5e-5)
    update(mat,'OcclusionParam',1);actual=render(mat,nt.nodes['MHWildsOcclusion'].outputs[0]);check('OcclusionParam 1 uses min(NRRO.B, ATOS.B)',np.max(np.abs(actual-.4))<5e-5)
    update(mat,'AlphaAdjust',1);actual=render(mat,nt.nodes['MHWildsAlphaCoverage'].inputs['Alpha'].links[0].from_socket);check('AlphaAdjust live update before one ColorParam alpha multiply',np.max(np.abs(actual-.32))<5e-5,actual.tolist())
    coverage=nt.nodes['MHWildsAlphaCoverage'];nt.links.remove(coverage.inputs['Alpha'].links[0]);coverage.inputs['Alpha'].default_value=.5
    for threshold,expected in [(.25,1),(.5,1),(.75,0)]:
        update(mat,'AlphaTest_Ref',threshold);actual=render(mat,coverage.outputs[0]);check('alpha test inclusive boundary '+str(threshold),np.max(np.abs(actual-expected))<5e-5,actual.tolist())
    update(mat,'UseTempDither',1);actual=render(mat,coverage.outputs[0]);check('temporal preview uses continuous coverage rather than hard cutout',np.max(np.abs(actual-.5))<5e-5)
    alba=fixture(alba=True);actual=render(alba,alba.node_tree.nodes['MHWildsAlphaCoverage'].inputs['Alpha'].links[0].from_socket);check('ALBA alpha takes priority over ATOS R and is shaped once',np.max(np.abs(actual-.1))<5e-5,actual.tolist())
    for options in [dict(blend=True),dict(alba=True,matcap=True)]:
        m=fixture(**options);n=m.node_tree.nodes;check('continuous forward/blended profile is not forced through cutout '+str(options),'MHWildsAlphaCoverage' not in n)
    array=fixture(array=True);n=array.node_tree.nodes;n['ARRAY_NormalRoughnessOcclusionMap_SELECTOR'].inputs[0].default_value=1
    update(array,'UseAOSecondaryUV',1);actual=render(array,diagnostics(array));check('array AO sample follows the same layer selector',np.max(np.abs(actual-np.array([.45,.325,.08])))<5e-5,actual.tolist())
    old=fixture(game='RE4');check('other game importer does not construct Wilds UV/alpha groups',not any(n in old.node_tree.nodes for n in ['MHWildsBaseAOUV','MHWildsAlphaAdjust','MHWildsAlphaCoverage','MHWildsOcclusion']))
    check('other game retains its legacy decoder',any(n.type=='GROUP' and n.node_tree.name=='BentNormalNodeGroup' for n in old.node_tree.nodes))
    old_uv=fixture(game='RE4',legacy_uv=True);check('legacy alpha secondary UV setup is retained','UV2_AlphaTranslucentOcclusionSSSMap' in old_uv.node_tree.nodes)
finally:
    main.Texconv,main.unload_texconv,main.getTexPath,main.loadTex,main.showErrorMessageBox=originals
    scratch.cleanup()
results['passed']=all(r['passed'] for r in results['checks'])
if args.report:args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
assert results['passed'],'AO/alpha regression failed'
print('AO_ALPHA_TEST_SUMMARY '+json.dumps({'passed':results['passed'],'checks':len(results['checks'])}),flush=True)
