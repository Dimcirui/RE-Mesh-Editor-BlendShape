"""Exercise registered RNA callbacks, scoped rebuilds, resources and signed colors.
Optional --staged ROOT redirects patched sources before addon registration.
Optional --ui-timer verifies automatic timer dispatch in a separate factory GUI process.
"""
import argparse
import importlib
import importlib.abc
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import bpy
import addon_utils
import numpy as np

cli=argparse.ArgumentParser();cli.add_argument('--staged',type=Path);cli.add_argument('--report',type=Path);cli.add_argument('--ui-timer',action='store_true')
args=cli.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
addon=Path(r'C:\Users\Sheeran\AppData\Roaming\Blender Foundation\Blender\5.1\scripts\addons\RE-Mesh-Editor-MeshFixes') if args.staged else Path(__file__).resolve().parents[1]
if args.staged:
    class Loader(importlib.abc.Loader):
        def __init__(self,path,installed):self.path=path;self.installed=installed
        def create_module(self,spec):return None
        def exec_module(self,module):exec(compile(self.path.read_text(encoding='utf-8-sig'),str(self.installed),'exec'),module.__dict__)
    class Finder(importlib.abc.MetaPathFinder):
        def find_spec(self,fullname,path=None,target=None):
            if fullname==addon.name:relative=Path('__init__.py');package=True
            elif fullname.startswith(addon.name+'.'):relative=Path(*fullname.split('.')[1:]).with_suffix('.py');package=False
            else:return None
            staged=args.staged/relative
            if staged.is_file():return importlib.util.spec_from_file_location(fullname,addon/relative,loader=Loader(staged,addon/relative),submodule_search_locations=[str(addon)] if package else None)
    sys.meta_path.insert(0,Finder())
sys.path.insert(0,str(addon.parent));addon_utils.enable(addon.name,default_set=True)
main=importlib.import_module(addon.name+'.modules.mdf.blender_re_mesh_mdf')
live=importlib.import_module(addon.name+'.modules.mdf.re_mdf_live_preview')
nodes=importlib.import_module(addon.name+'.modules.mdf.blender_nodes_re_mdf')
data=importlib.import_module(addon.name+'.modules.mdf.blender_re_mdf')
mdf=importlib.import_module(addon.name+'.modules.mdf.file_re_mdf')
props=importlib.import_module(addon.name+'.modules.mdf.re_mdf_propertyGroups')
results={'blender':bpy.app.version_string,'staged':str(args.staged) if args.staged else None,'ui_timer':args.ui_timer,'checks':[]}
def check(name,ok,detail=None):
    results['checks'].append({'name':name,'passed':bool(ok),'detail':detail});print(('PASS ' if ok else 'FAIL ')+name,flush=True)
    assert ok,(name,detail)
def report():
    results['passed']=bool(results['checks']) and not results.get('error') and all(c['passed'] for c in results['checks'])
    if args.report:args.report.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')

textures={};texture_names={};payloads={};load_calls=[];rebuilds=[];import_contexts=[];errors=[]
for name,color in {'base':(.2,.3,.4,1),'nrro':(.5,.5,1,.5),'atos':(1,0,1,.5),'blend':(.8,.6,.3,.4),'fx':(.6,.7,.4,1),'pano':(.7,.6,.5,1),'emi':(.3,.2,.1,.5),'vector':(.5,.5,1,1),'detail_mask':(1,0,0,0),'detail':(.6,.2,.1,1),'detail_nrro':(.5,.5,.5,.5)}.items():
    image=bpy.data.images.new(name,2,2,alpha=True,float_buffer=True);image.generated_color=color
    textures[name]=image;texture_names[name]=image.name;payloads[name]=list(color)*4
originals={n:getattr(main,n) for n in ('Texconv','unload_texconv','getTexPath','loadTex','showErrorMessageBox','getChunkPathList','importMDF')}
main.Texconv=lambda:None;main.unload_texconv=lambda:None;main.getChunkPathList=lambda game:[];main.getTexPath=lambda base,*a,**k:base if base in textures else None;main.showErrorMessageBox=errors.append
def load(*a,**k):load_calls.append({'path':a[0],'reload':a[3]});return [bpy.data.images[texture_names[a[0]]]]
main.loadTex=load
def importing(*a,**k):
    rebuilds.append(list(a[1]));import_contexts.append(dict(k));return originals['importMDF'](*a,**k)
main.importMDF=importing

def fixture(label,overrides=None):
    values={'ColorParam':[1,1,1,1],'Film_Blend':[0],'FullFIlm':[0],'Film_Thickness':[.5],'Film_IOR':[.5],'UseBaseColorFilm':[0],
            'NormalBlendParam':[0],'UseDetail':[0],'ModulateColor':[0],'Use_R':[1],'DetailTile_R':[1],'Detail_Color_R':[.5,.5,.5,1],
            'FakeRefraction_Blend':[0],'Refraction_Index':[1], 'UseVectorEmit':[0],'UseParallaxEmit':[0],'VectorEmit_power':[6],'ParallaxEmit_Height':[.1],'ParallaxEmit_Blend':[.5],
            'Use_MoveEmit':[0],'MoveEmit':[0],'MoveEmit_Width':[.5],'Use_WaveMove':[0],'AnimEmit_Min':[1],'AnimEmit_Speed':[1],'UseWaveEmit':[0],'AnimEmitWave':[1],
            'SecondaryEmitColor':[0,0,0,1],'SecEmit_Anim_Min':[1],'SecEmit_Anim_Speed':[1],'SecEmit_Anim_UseWaveEmit':[0],'SecEmit_Anim_Wave':[1],
            'SSSProfile':[0],'SSSParam':[.7],'EmissiveIntensity':[1],'OcclusionParam':[1]}
    values.update(overrides or {})
    source=mdf.Material();source.materialName=label;source.mmtrPath='MaterialShader/Variation/Base_ATOS_SkinEdit_VFX.mmtr'
    for name,value in values.items():
        p=mdf.Property();p.propName=name;p.propValue=value;p.paramCount=len(value);source.propertyList.append(p)
    for slot,path in [('BaseDielectricMap','base'),('NormalRoughnessOcclusionMap','nrro'),('AlphaTranslucentOcclusionSSSMap','atos'),('BlendNormalMap','blend'),('FxMap','fx'),('PanoramaMap','pano'),('EmissiveMap','emi'),('VectorEmitMap','vector'),('DetailMaskMap','detail_mask'),('Detail_ALBD_R','detail'),('Detail_NRRH_R','detail_nrro')]:
        t=mdf.TextureBinding();t.textureType=slot;t.texturePath=path+'.tex';source.textureList.append(t)
    file=mdf.MDFFile();file.fileVersion=45;file.materialList=[source]
    mat=bpy.data.materials.new(label)
    main.importMDF(file,{label:mat},False,False,False,False,chunkPath='stored_chunk',gameName='MHWILDS')
    #Populate the MDF owner with real registered PropertyGroups before linking.
    owner=bpy.data.objects.new('MDF owner '+label,None);bpy.context.scene.collection.objects.link(owner);owner['~TYPE']='RE_MDF_MATERIAL'
    owner.re_mdf_material.gameName='MHWILDS';owner.re_mdf_material.materialName=label;owner.re_mdf_material.mmtrPath=source.mmtrPath
    data.addPropsToPropList(owner,source.propertyList);data.addTextureBindingsToBindingList(owner,source.textureList)
    owner.re_mdf_material.linkedMaterial=mat;live.clearPendingLivePreviews()
    return owner,mat
def find(owner,name):return next(p for p in owner.re_mdf_material.propertyList_items if p.prop_name==name)
def setvalue(owner,name,value):
    p=find(owner,name)
    if p.data_type=='BOOL':p.bool_value=bool(value)
    elif p.data_type=='COLOR':p.color_value=value
    elif p.data_type=='VEC4':p.float_vector_value=value
    else:p.float_value=float(value)
def group(mat,name):return next((n for n in mat.node_tree.nodes if n.type=='GROUP' and n.node_tree.name==name),None)
def flush():live.flushPendingLivePreviews(force=True);check('node rebuilding has no importer errors',not errors)

scratch=tempfile.TemporaryDirectory(prefix='reme_live_')
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_plane_add(size=4);plane=bpy.context.object
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=1;scene.cycles.use_denoising=False
camera_data=bpy.data.cameras.new('Live test');camera=bpy.data.objects.new('Live test',camera_data);scene.collection.objects.link(camera);camera.location=(0,0,2);camera_data.type='ORTHO';camera_data.ortho_scale=2;scene.camera=camera
scene.render.resolution_x=8;scene.render.resolution_y=8;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='OPEN_EXR';scene.render.image_settings.color_mode='RGBA';scene.render.image_settings.color_depth='32'
def render(mat,socket):
    for name,image in textures.items():image.pixels.foreach_set(payloads[name]);image.update()
    nt=mat.node_tree;out=next(n for n in nt.nodes if n.type=='OUTPUT_MATERIAL');old=out.inputs['Surface'].links[0].from_socket
    emission=nt.nodes.new('ShaderNodeEmission');nt.links.new(socket,emission.inputs['Color']);nt.links.new(emission.outputs[0],out.inputs['Surface'])
    plane.data.materials.clear();plane.data.materials.append(mat)
    scene.render.filepath=str(Path(scratch.name)/'sample.exr');bpy.ops.render.render(write_still=True)
    im=bpy.data.images.load(scene.render.filepath,check_existing=False);v=np.array(im.pixels[:]).reshape(8,8,4)[4,4,:3].copy();bpy.data.images.remove(im)
    nt.links.new(old,out.inputs['Surface']);nt.nodes.remove(emission)
    return v

def cleanup():
    live.clearPendingLivePreviews()
    for n,v in originals.items():setattr(main,n,v)
    scratch.cleanup()

try:
    owner,mat=fixture('Live A');other,othermat=fixture('Live B')
    check('fresh addon registration installs live lifecycle handlers',live.clearPendingLivePreviews in bpy.app.handlers.load_pre and live.syncLivePreviewsAfterUndo in bpy.app.handlers.undo_post)
    check('all structural property names participate in callbacks',live.STRUCTURAL_PROPS<=props.editablePropsSet)
    check('disabled film, normal and refraction branches are initially absent',all(group(mat,n) is None for n in ['MHWildsFilm','MHWildsBlendNormal','MHWildsPanoramaUV','MHWildsDetailLayer']))
    check('disabled gated textures are not loaded',all(n not in mat.node_tree.nodes for n in ['FxMap','BlendNormalMap','PanoramaMap','VectorEmitMap']))
    unrelated=othermat.node_tree.nodes.new('ShaderNodeValue');unrelated.name='User unrelated node';otherptr=unrelated.as_pointer()
    initial=len(rebuilds);setvalue(owner,'Film_Blend',.2);setvalue(owner,'Film_Blend',.4);setvalue(owner,'Film_Blend',.6)
    check('rapid property callbacks queue one material and register a timer',len(live._pending)==1 and bpy.app.timers.is_registered(live._runPending) and len(rebuilds)==initial)
    flush();film=group(mat,'MHWildsFilm')
    check('film enables from cold with its texture loaded',film is not None and mat.node_tree.nodes.get('FxMap') is not None)
    check('coalesced rebuild consumes the latest MDF property value',abs(mat.node_tree.nodes['Film_Blend'].outputs[0].default_value-.6)<1e-6 and len(rebuilds)==initial+1)
    check('rebuild affects only the linked material and preserves other graphs',othermat.node_tree.nodes['User unrelated node'].as_pointer()==otherptr and rebuilds[-1]==['Live A'])
    before=len(rebuilds);setvalue(owner,'Film_Blend',.7);setvalue(owner,'Film_Thickness',.8);flush()
    check('continuous sliders use existing nodes without reimport',len(rebuilds)==before and abs(mat.node_tree.nodes['Film_Thickness'].outputs[0].default_value-.8)<1e-6)
    setvalue(owner,'Film_Blend',0);flush();check('disabling film removes its branch and no-longer-needed texture',group(mat,'MHWildsFilm') is None and 'FxMap' not in mat.node_tree.nodes)
    before=len(rebuilds);setvalue(owner,'Film_Blend',1);setvalue(owner,'Film_Blend',0);flush();check('toggle returned to original state cancels rebuild',len(rebuilds)==before)

    setvalue(owner,'NormalBlendParam',.5);flush();check('blend normal enables from cold',group(mat,'MHWildsBlendNormal') is not None and 'BlendNormalMap' in mat.node_tree.nodes)
    positive_normal=render(mat,group(mat,'MHWildsBlendNormal').outputs['Color'])
    before=len(rebuilds);setvalue(owner,'NormalBlendParam',-.4);flush();check('positive to negative normal blend stays on the live node path',len(rebuilds)==before and abs(mat.node_tree.nodes['NormalBlendParam'].outputs[0].default_value+.4)<1e-6)
    negative_normal=render(mat,group(mat,'MHWildsBlendNormal').outputs['Color']);check('live normal slider changes actual shader output',float(np.max(np.abs(positive_normal-negative_normal)))>.01)
    setvalue(owner,'NormalBlendParam',0);flush();check('blend normal can be disabled again',group(mat,'MHWildsBlendNormal') is None)
    setvalue(owner,'UseDetail',1);flush();check('UseDetail enables the missing detail branch',group(mat,'MHWildsDetailLayer') is not None)
    setvalue(owner,'ModulateColor',1);flush();check('ModulateColor changes the construction signature',json.loads(mat[live.RECIPE_KEY])['signature'][3] is True)
    setvalue(owner,'FakeRefraction_Blend',.5);flush();check('fake refraction enables with Panorama and Fx dependencies',group(mat,'MHWildsPanoramaUV') is not None and 'PanoramaMap' in mat.node_tree.nodes and 'FxMap' in mat.node_tree.nodes)
    setvalue(owner,'FakeRefraction_Blend',0);flush();check('fake refraction disables and releases its sample branch',group(mat,'MHWildsPanoramaUV') is None and 'PanoramaMap' not in mat.node_tree.nodes)

    setvalue(owner,'UseVectorEmit',1);flush();check('existing vector emission branch can enable live',group(mat,'MHWildsVectorEmit') is not None and 'VectorEmitMap' in mat.node_tree.nodes)
    setvalue(owner,'UseParallaxEmit',1);flush();check('existing parallax emission branch can enable live','EmissiveMap_Parallax' in mat.node_tree.nodes)
    setvalue(owner,'Use_MoveEmit',1);flush();check('existing move emission branch can enable live',group(mat,'MHWildsMoveEmit') is not None)
    setvalue(owner,'Use_MoveEmit',0);setvalue(owner,'AnimEmit_Min',.3);setvalue(owner,'UseWaveEmit',1);flush();check('existing animated emission branch and Fx dependency rebuild',group(mat,'MHWildsAnimEmit') is not None and 'FxMap' in mat.node_tree.nodes)
    setvalue(owner,'SecondaryEmitColor',[.2,.3,.4,1]);setvalue(owner,'SecEmit_Anim_Min',.3);flush();check('secondary emission can start from zero color',any(n.label=='SecEmit' for n in mat.node_tree.nodes))
    setvalue(owner,'SSSProfile',1);flush();bsdf=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED');check('existing supported skin SSS profile can be enabled live',bsdf.inputs['Subsurface Weight'].is_linked)
    check('real-time rebuilds never force cached image conversion',all(not c['reload'] for c in load_calls))
    check('rebuild does not change MDF ownership, names, material pointer or bindings',owner.re_mdf_material.linkedMaterial==mat and owner.re_mdf_material.materialName=='Live A' and find(owner,'Film_Blend').float_value==0 and owner.re_mdf_material.textureBindingList_items[0].path=='base.tex')

    #Move from a color widget to a signed float4 without a whole material rebuild.
    before=len(rebuilds);color=find(owner,'ColorParam');color.data_type='VEC4';color.float_vector_value=(-.2,.3,.4,-.4)
    migrated=mat.node_tree.nodes['ColorParam'];check('negative RGBA migrates the one property node without clipping',migrated.node_tree.name=='Vec4ColorNodeGroup' and abs(migrated.inputs[0].default_value+.2)<1e-6 and abs(migrated.inputs[3].default_value+.4)<1e-6 and len(rebuilds)==before)
    check('signed migration retains Color and Alpha consumers',migrated.outputs['Color'].is_linked and migrated.outputs['Alpha'].is_linked)
    separate=mat.node_tree.nodes.new('ShaderNodeSeparateColor');mat.node_tree.links.new(migrated.outputs['Color'],separate.inputs['Color'])
    for socket,expected in [(separate.outputs['Red'],.8),(migrated.outputs['Alpha'],.6)]:
        add=mat.node_tree.nodes.new('ShaderNodeMath');add.operation='ADD';add.inputs[1].default_value=1;mat.node_tree.links.new(socket,add.inputs[0]);actual=render(mat,add.outputs[0]);check('signed shader value survives after adding one '+str(expected),np.max(np.abs(actual-expected))<5e-5,actual.tolist())
    color.float_vector_value=(.2,.3,.4,.7);check('signed node can return to positive values',abs(migrated.inputs[0].default_value-.2)<1e-6 and abs(migrated.inputs[3].default_value-.7)<1e-6)
    #The COLOR widget must also update a node previously migrated to raw float components.
    color.data_type='COLOR';color.color_value=(.7,.6,.5,.4);check('color widget updates a previously signed node',abs(migrated.inputs[0].default_value-.7)<1e-6 and abs(migrated.inputs[3].default_value-.4)<1e-6)

    old,oldmat=fixture('Older graph');del oldmat[live.RECIPE_KEY];setvalue(old,'Film_Blend',1);flush();check('unregistered older graphs are not destructively rebuilt',group(oldmat,'MHWildsFilm') is None)
    relink,relinkmat=fixture('Relink');setvalue(relink,'Film_Blend',1);relink.re_mdf_material.linkedMaterial=othermat;flush();check('queued rebuild is discarded if user relinks the material',group(relinkmat,'MHWildsFilm') is None);relink.re_mdf_material.linkedMaterial=None
    deleted,deletedmat=fixture('Deleted owner');setvalue(deleted,'Film_Blend',1);bpy.data.objects.remove(deleted,do_unlink=True);flush();check('deleted queued owner is skipped safely',group(deletedmat,'MHWildsFilm') is None)
    setvalue(owner,'Film_Blend',1);live.clearPendingLivePreviews();check('load/undo cancellation removes queued work and timer',not live._pending and not bpy.app.timers.is_registered(live._runPending))
    #Resync is the same persistent handler used for undo/redo, and repairs numeric nodes.
    setvalue(owner,'Film_Blend',0);mat.node_tree.nodes['OcclusionParam'].outputs[0].default_value=.01
    live.syncLivePreviewsAfterUndo();flush();check('undo/redo resync handler repairs numeric preview nodes',abs(mat.node_tree.nodes['OcclusionParam'].outputs[0].default_value-1)<1e-6)
    live.registerLivePreview();check('lifecycle registration is idempotent',bpy.app.handlers.undo_post.count(live.syncLivePreviewsAfterUndo)==1)
    bpy.context.scene.re_mdf_toolpanel.activeGame='RE4';bpy.context.scene.re_mdf_toolpanel.modDirectory='unrelated_directory'
    setvalue(owner,'UseDetail',0);flush();check('rebuild uses the material source context instead of unrelated active UI settings',import_contexts[-1]['gameName']=='MHWILDS' and import_contexts[-1]['chunkPath']=='stored_chunk')
    broken,brokenmat=fixture('Missing dependency')
    next(t for t in broken.re_mdf_material.textureBindingList_items if t.textureType=='BlendNormalMap').path='unavailable.tex'
    setvalue(broken,'NormalBlendParam',1);flush();check('enabling with a missing real dependency previews its slot null','RE Missing Texture Fallback' not in brokenmat.node_tree.nodes and {'slot':'BlendNormalMap','path':'unavailable.tex','fallback':'systems/rendering/nullnormal'} in json.loads(brokenmat.get('re_mdf_preview_null_fallbacks','[]')))
    setvalue(broken,'NormalBlendParam',0);flush();check('disabling the failed feature drops its slot null','re_mdf_preview_null_fallbacks' not in brokenmat and 'BaseDielectricMap' in brokenmat.node_tree.nodes)
    nullowner,nullmat=fixture('Null dependency')
    next(t for t in nullowner.re_mdf_material.textureBindingList_items if t.textureType=='FxMap').path='systems/rendering/NullWhite.tex'
    setvalue(nullowner,'Film_Blend',.5);flush();check('live enabling retains system-null substitution instead of blanking the material',group(nullmat,'MHWildsFilm') is not None and 're_mdf_preview_null_fallbacks' in nullmat and 'RE Missing Texture Fallback' not in nullmat.node_tree.nodes)
except Exception as error:
    results['error']=repr(error);report();cleanup();raise

if args.ui_timer:
    timerowner,timermat=fixture('Automatic timer');start=len(rebuilds);setvalue(timerowner,'Film_Blend',.8)
    undo_owner_name=''
    class WM_OT_live_test_set(bpy.types.Operator):
        bl_idname='wm.re_mdf_live_test_set'
        bl_label='Live test property change'
        bl_options={'UNDO'}
        def execute(self,context):
            setvalue(bpy.data.objects[undo_owner_name],'Film_Blend',1)
            return {'FINISHED'}
    class WM_OT_live_test_create(bpy.types.Operator):
        bl_idname='wm.re_mdf_live_test_create'
        bl_label='Live test fixture creation'
        bl_options={'REGISTER','UNDO'}
        def execute(self,context):
            global undo_owner_name
            undoowner,undomat=fixture('Undo test')
            undo_owner_name=undoowner.name
            context.view_layer.update()
            return {'FINISHED'}
    bpy.utils.register_class(WM_OT_live_test_set)
    bpy.utils.register_class(WM_OT_live_test_create)
    def ui_operator(operator):
        window=bpy.context.window_manager.windows[0]
        area=next(a for a in window.screen.areas if a.type=='VIEW_3D')
        region=next(r for r in area.regions if r.type=='WINDOW')
        with bpy.context.temp_override(window=window,area=area,region=region):
            return operator()
    def quit_test():
        report();cleanup();bpy.ops.wm.quit_blender()
    def redo_check():
        try:
            restored=bpy.data.objects[undo_owner_name];restoredmat=restored.re_mdf_material.linkedMaterial
            check('real Blender redo restores the MDF value and shader branch',find(restored,'Film_Blend').float_value==1 and group(restoredmat,'MHWildsFilm') is not None)
            live.unregisterLivePreview();check('unregister removes timers and lifecycle callbacks',not live._pending and live.syncLivePreviewsAfterUndo not in bpy.app.handlers.undo_post and live.clearPendingLivePreviews not in bpy.app.handlers.load_pre)
            live.registerLivePreview()
        except Exception as error:
            results['error']=repr(error);raise
        finally:
            quit_test()
        return None
    def undo_check():
        try:
            check('automatic rebuild completes before the undo snapshot',group(bpy.data.materials['Undo test'],'MHWildsFilm') is not None)
            results['undo_debug']={'global_undo':bpy.context.preferences.edit.use_global_undo,'undo_steps':bpy.context.preferences.edit.undo_steps,'owner_name':undo_owner_name}
            ui_operator(bpy.ops.ed.undo)
            restored=bpy.data.objects[undo_owner_name];restoredmat=restored.re_mdf_material.linkedMaterial
            check('real Blender undo restores the MDF value and shader branch',find(restored,'Film_Blend').float_value==0 and group(restoredmat,'MHWildsFilm') is None)
            ui_operator(bpy.ops.ed.redo)
            bpy.app.timers.register(redo_check,first_interval=.5)
        except Exception as error:
            results['error']=repr(error);quit_test();raise
        return None
    def change_undo_value():
        try:
            ui_operator(bpy.ops.wm.re_mdf_live_test_set)
            bpy.context.view_layer.update()
            ui_operator(lambda:bpy.ops.ed.undo_push(message='Live preview property edit'))
            bpy.app.timers.register(undo_check,first_interval=.5)
        except Exception as error:
            results['error']=repr(error);quit_test();raise
        return None
    def finish():
        global undo_owner_name
        try:
            check('automatic Blender UI timer dispatch rebuilds the material',group(timermat,'MHWildsFilm') is not None and len(rebuilds)==start+1)
            check('automatic timer clears its pending queue',not live._pending)
            bpy.context.preferences.edit.use_global_undo=True
            bpy.context.preferences.edit.undo_steps=32
            ui_operator(lambda:bpy.ops.ed.undo_push(message='Initialize live test undo'))
            ui_operator(bpy.ops.wm.re_mdf_live_test_create)
            ui_operator(lambda:bpy.ops.ed.undo_push(message='Live preview fixture baseline'))
            bpy.app.timers.register(change_undo_value,first_interval=.3)
        except Exception as error:
            results['error']=repr(error);quit_test();raise
        return None
    bpy.app.timers.register(finish,first_interval=.5)
else:
    report();cleanup();print('LIVE_PREVIEW_TEST_SUMMARY '+json.dumps({'passed':results['passed'],'checks':len(results['checks'])}),flush=True)
