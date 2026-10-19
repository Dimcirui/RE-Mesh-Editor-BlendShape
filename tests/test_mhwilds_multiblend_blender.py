"""Independent scalar oracle + real Cycles node/importer/live-edit tests for atlas MultiBlend."""
import argparse,importlib,importlib.abc,importlib.util,json,math,struct,sys,tempfile
from pathlib import Path
import addon_utils,bpy,numpy as np
parser=argparse.ArgumentParser();parser.add_argument('--staged',type=Path);parser.add_argument('--report',type=Path);parser.add_argument('--survey',type=Path);parser.add_argument('--real-assets',action='store_true')
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
addon=Path(r'C:\Users\Sheeran\AppData\Roaming\Blender Foundation\Blender\5.1\scripts\addons\RE-Mesh-Editor-MeshFixes') if args.staged else Path(__file__).resolve().parents[1]
if args.staged:
    class Loader(importlib.abc.Loader):
        def __init__(self,p):self.p=p
        def create_module(self,spec):return None
        def exec_module(self,module):exec(compile(self.p.read_text(encoding='utf-8-sig'),module.__file__,'exec'),module.__dict__)
    class Finder(importlib.abc.MetaPathFinder):
        def find_spec(self,name,path=None,target=None):
            if not name.startswith(addon.name+'.'):return None
            rel=Path(*name.split('.')[1:]).with_suffix('.py');p=args.staged/rel
            if p.is_file():return importlib.util.spec_from_file_location(name,addon/rel,loader=Loader(p))
    sys.meta_path.insert(0,Finder())
sys.path.insert(0,str(addon.parent));addon_utils.enable(addon.name,default_set=True)
main=importlib.import_module(addon.name+'.modules.mdf.blender_re_mesh_mdf')
nodes=importlib.import_module(addon.name+'.modules.mdf.blender_nodes_re_mdf')
mb=importlib.import_module(addon.name+'.modules.mdf.blender_mhwilds_multiblend')
mdf=importlib.import_module(addon.name+'.modules.mdf.file_re_mdf')
data=importlib.import_module(addon.name+'.modules.mdf.blender_re_mdf')
live=importlib.import_module(addon.name+'.modules.mdf.re_mdf_live_preview')
props=importlib.import_module(addon.name+'.modules.mdf.re_mdf_propertyGroups')
results={'blender':bpy.app.version_string,'staged':str(args.staged) if args.staged else None,'checks':[]}
def check(name,ok,detail=None):
    results['checks'].append({'name':name,'passed':bool(ok),'detail':detail});print(('PASS ' if ok else 'FAIL ')+name,flush=True)
    assert ok,(name,detail)

scratch=tempfile.TemporaryDirectory(prefix='reme_multiblend_');root=Path(scratch.name)
atlas_entries=[((.5,1,0,0),(0,.5,0,1)),((.5,1,.5,0),(.5,1,0,1)),((1,1,0,0),(0,0,0,0))]
(root/'Atlas.gpbf.3').write_bytes(struct.pack('<BI',0,3)+b''.join(struct.pack('<8f',*t,*r) for t,r in atlas_entries))
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_plane_add(size=4);plane=bpy.context.object;uv0=plane.data.uv_layers.active;uv0.name='UVMap0';uv1=plane.data.uv_layers.new(name='UVMap1')
def setuv(x=.25,y=.5):
    for p in uv0.data:p.uv=(x,y)
    for p in uv1.data:p.uv=(.75,.5)
setuv()
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=1;scene.cycles.use_denoising=False
camdata=bpy.data.cameras.new('MultiBlend test');cam=bpy.data.objects.new('MultiBlend test',camdata);scene.collection.objects.link(cam);cam.location=(0,0,2);camdata.type='ORTHO';camdata.ortho_scale=2;scene.camera=cam
scene.render.resolution_x=8;scene.render.resolution_y=8;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='OPEN_EXR';scene.render.image_settings.color_mode='RGBA';scene.render.image_settings.color_depth='32'
images={};payloads={}
for name,pixels in {'base':[(.2,.3,.4,1),(.4,.3,.2,1)],'nrro':[(.4,.5,.8,.5)]*2,'atos':[(.6,0,1,.2)]*2,'atlas':[(.7,.4,.2,.5),(.2,.6,.4,.8)],'normal':[(.3,.8,.6,.7),(.8,.6,.4,.4)],'detail_mask':[(1,0,0,0)]*2,'detail':[(.6,.3,.1,1)]*2,'detail_nrro':[(.5,.5,.5,.5)]*2,'color_mask':[(1,0,0,0)]*2,'emi':[(.2,.3,.4,.5)]*2}.items():
    image=bpy.data.images.new(name,2,1,alpha=True,float_buffer=True);image.alpha_mode='CHANNEL_PACKED';image.colorspace_settings.name='Non-Color'
    images[name]=image;payloads[name]=[v for p in pixels for v in p];image.pixels.foreach_set(payloads[name]);image.update()
originals={n:getattr(main,n) for n in ('Texconv','unload_texconv','getTexPath','loadTex','getChunkPathList','showErrorMessageBox','importMDF')};errors=[];imports=[]
main.Texconv=lambda:None;main.unload_texconv=lambda:None;main.getChunkPathList=lambda game:[];main.getTexPath=lambda base,*a,**k:base if base in images else None;main.loadTex=lambda path,*a,**k:[images[path]];main.showErrorMessageBox=errors.append
def importing(*a,**k):imports.append(list(a[1]));return originals['importMDF'](*a,**k)
main.importMDF=importing
def render(mat,socket):
    for key,image in images.items():image.pixels.foreach_set(payloads[key]);image.update()
    nt=mat.node_tree;output=next(n for n in nt.nodes if n.type=='OUTPUT_MATERIAL');old=output.inputs['Surface'].links[0].from_socket
    emit=nt.nodes.new('ShaderNodeEmission');nt.links.new(socket,emit.inputs['Color']);nt.links.new(emit.outputs[0],output.inputs['Surface'])
    plane.data.materials.clear();plane.data.materials.append(mat);scene.render.filepath=str(root/'sample.exr');bpy.ops.render.render(write_still=True)
    im=bpy.data.images.load(scene.render.filepath,check_existing=False);v=np.array(im.pixels[:]).reshape(8,8,4)[4,4,:3].copy();bpy.data.images.remove(im)
    nt.links.new(old,output.inputs['Surface']);nt.nodes.remove(emit);return v
def pack(nt,*sockets):
    n=nt.nodes.new('ShaderNodeCombineColor')
    for index,value in enumerate(sockets):
        if isinstance(value,(int,float)):n.inputs[index].default_value=value
        else:nt.links.new(value,n.inputs[index])
    return n.outputs[0]
def normalcolor(nt,vector):
    b=nodes.ShaderGroupBuilder(nt);n=b.separateXYZ(vector);return b.combineColor(*[b.math('MULTIPLY_ADD',n[c],.5,.5) for c in ('X','Y','Z')])
def oracle(c,n,r,alpha,atlas,normal,weight,inside,nrro,overlay,gamma,contrast,threshold,emit):
    c=np.array(c,float);n=np.array(n,float);a=np.array(atlas[:3]);t=np.array(normal)
    if not weight or not inside:return c,n,r,alpha,1,0
    raw=weight*inside;q=np.clip(atlas[3]/contrast if contrast else float(atlas[3]>0),0,1);w=abs(raw)*q*q*(3-2*q)
    if nrro:
        ga=2*t[[1,3]]-1;ga=ga*np.abs(ga);dec=np.array([sum(ga)*.5,(ga[0]-ga[1])*.5,0]);dec[2]=1-abs(dec[0])-abs(dec[1]);dec/=np.linalg.norm(dec)
    else:dec=2*t[:3]-1
    mul=(overlay>0 and raw>0) or (overlay==0 and raw<0)
    if mul:
        cc=c**.44999998807907104 if gamma else c;aa=a**.44999998807907104 if gamma else a
        color=cc+(2*cc*aa-cc)*w
        if gamma:color=color**2.200000047683716
        nn=n.copy();nn[:2]+=w*dec[:2];nn/=np.linalg.norm(nn)
        rough=r+(2*r*t[0]-r)*w if nrro else r
    else:color=c+(a-c)*w;nn=n+(dec-n)*w;rough=r+(t[0]-r)*w if nrro else r
    return color,nn,rough,alpha*(1-raw*(atlas[3]>threshold)),1-w if emit else 1,w

def fixture(name='Clothing',weights=(.6,-.4,0,0),count=2,stack=False,emission=False,game='MHWILDS'):
    source=mdf.Material();source.materialName=name;source.mmtrPath='MaterialShader/Variation/Base_ATOS_Emit_FX_Detail_DetailColLayer_MultiBlend.mmtr'
    values={'ColorParam':[1,1,1,.8],'Blend_A':list(weights),'Blend_num':[count],'use_overlay':[1],'sRGB_Overlay':[0],'Use_MultiBlend_NRRO':[1],'Blend_Contrast':[1],'Blend_Alpha_Threshold':[1],'Use_EmitMask':[0],'ChangeUV':[0],'UseDetail':[1 if stack else 0],'Use_R':[1],'ModulateColor':[0],'Detail_Color_R':[.5,.5,.5,1]}
    if stack:values.update({'ColorLayer_'+c:[.4,.6,.8,.5] for c in 'RGBA'});values.update({'ColorLayer_Mask_Width':[1,1,1,1],'ColorLayer_Mask_Fade':[1,1,1,1]})
    if emission:values['EmissiveIntensity']=[1];values['SecondaryEmitColor']=[.3,.2,.1,1]
    for name0,value in values.items():
        p=mdf.Property();p.propName=name0;p.propValue=value;p.paramCount=len(value);source.propertyList.append(p)
    bindings=[('BaseDielectricMap','base'),('NormalRoughnessOcclusionMap','nrro'),('AlphaTranslucentOcclusionSSSMap','atos'),('MultiBlend_ALBDMap','atlas'),('MultiBlend_NRMMap','normal')]
    if stack:bindings += [('DetailMaskMap','detail_mask'),('Detail_ALBD_R','detail'),('Detail_NRRH_R','detail_nrro'),('ColorLayer_MaskMap','color_mask')]
    if emission:bindings += [('EmissiveMap','emi')]
    for slot,path in bindings:
        t=mdf.TextureBinding();t.textureType=slot;t.texturePath=path+'.tex';source.textureList.append(t)
    namebuf=mdf.GPBFEntry();namebuf.name='MultiBlend_BAB';pathbuf=mdf.GPBFEntry();pathbuf.name='Atlas.gpbf';source.gpbfBufferNameList=[namebuf];source.gpbfBufferPathList=[pathbuf]
    file=mdf.MDFFile();file.fileVersion=45;file.materialList=[source];mat=bpy.data.materials.new(name)
    main.importMDF(file,{name:mat},False,False,False,False,chunkPath=str(root),gameName=game)
    owner=bpy.data.objects.new('Material ('+name+')',None);scene.collection.objects.link(owner);owner['~TYPE']='RE_MDF_MATERIAL';owner.re_mdf_material.materialName=name;owner.re_mdf_material.gameName=game;owner.re_mdf_material.mmtrPath=source.mmtrPath
    data.addPropsToPropList(owner,source.propertyList);data.addTextureBindingsToBindingList(owner,source.textureList);data.addGPBFDataToList(owner,source.gpbfBufferNameList,source.gpbfBufferPathList);owner.re_mdf_material.linkedMaterial=mat;live.clearPendingLivePreviews()
    for n in mat.node_tree.nodes:
        if n.type=='TEX_IMAGE':n.interpolation='Closest'
    return owner,mat
def setvalue(owner,name,value):
    p=next(p for p in owner.re_mdf_material.propertyList_items if p.prop_name==name)
    if p.data_type=='BOOL':p.bool_value=bool(value)
    elif p.data_type=='VEC4':p.float_vector_value=value
    elif p.data_type=='COLOR':p.color_value=value
    else:p.float_value=value
def flush():live.flushPendingLivePreviews(force=True);check('actual importer completed without material errors',not errors)

try:
    check('raw version 3 GPBF decodes exact transform/bounds pairs',mb.readMultiBlendGPBF(root/'Atlas.gpbf.3')==atlas_entries)
    bad=root/'invalid.gpbf.3'
    for content in [b'bad',struct.pack('<BI',1,3)+b'\0'*32,struct.pack('<BI',0,2)+b'\0'*32,struct.pack('<BI',0,3)+b'\0'*31,struct.pack('<BI',0,3)+struct.pack('<8f',float('nan'),0,0,0,0,0,0,0)]:
        bad.write_bytes(content)
        try:mb.readMultiBlendGPBF(bad);rejected=False
        except ValueError:rejected=True
        check('unsupported or malformed GPBF rejected '+content[:5].hex(),rejected)
    if args.survey:
        survey=json.loads(args.survey.read_text(encoding='utf-8'))
        for logical,entry in survey['buffers'].items():
            decoded=mb.readMultiBlendGPBF(entry['file']);expected=[(tuple(t),tuple(r)) for t,r in entry['payload_float4_pairs']]
            check('original game buffer parsed '+logical,decoded==expected)

    testmat=bpy.data.materials.new('Layer arithmetic');testmat.use_nodes=True;nt=testmat.node_tree
    layer=mb.multiBlendLayerNode(nt)
    for name,value in {'Base Color':(.2,.4,.6,1),'Base Normal':(.1,.2,.97),'Base Roughness':.4,'Base Alpha':.6,'Atlas Color':(.7,.3,.5,1),'Atlas Alpha':.8,'Normal Map':(.3,.8,.6,1),'Normal Alpha':.7,'Inside':1,'Contrast':1,'Alpha Threshold':.5}.items():layer.inputs[name].default_value=value
    for nrro,overlay,weight,gamma,inside in [(1,1,.7,0,1),(1,0,.7,0,1),(0,1,.7,0,1),(0,0,-.7,0,1),(1,1,-.7,0,1),(1,1,.7,1,1),(1,-1,-.7,0,1),(1,1,.7,1,0),(1,1,1.5,0,1)]:
        for name,value in [('Use NRRO',nrro),('Overlay',overlay),('Weight',weight),('sRGB Overlay',gamma),('Inside',inside),('Emit Mask',1)]:layer.inputs[name].default_value=value
        ref=oracle([.2,.4,.6],[.1,.2,.97],.4,.6,[.7,.3,.5,.8],[.3,.8,.6,.7],weight,inside,nrro,overlay,gamma,1,.5,1)
        color=render(testmat,layer.outputs['Color']);normal=render(testmat,normalcolor(nt,layer.outputs['Normal']));scalar=render(testmat,pack(nt,layer.outputs['Roughness'],layer.outputs['Alpha'],layer.outputs['Weight']))
        error=max(np.max(np.abs(color-ref[0])),np.max(np.abs(normal-(ref[1]*.5+.5))),np.max(np.abs(scalar-np.array([ref[2],ref[3],ref[5]]))))
        check('rendered layer matches independent DXIL formula '+str((nrro,overlay,weight,gamma,inside)),error<3e-5,{'max_error':float(error)})
    layer.inputs['Weight'].default_value=.5;layer.inputs['Inside'].default_value=1;layer.inputs['Atlas Alpha'].default_value=.8
    for threshold in [.79,.8,.81]:
        layer.inputs['Alpha Threshold'].default_value=threshold;actual=render(testmat,layer.outputs['Alpha']);expected=.6*(.5 if .8>threshold else 1)
        check('strict alpha threshold '+str(threshold),np.max(np.abs(actual-expected))<3e-5)
    layer.inputs['Contrast'].default_value=0;actual=render(testmat,layer.outputs['Weight']);check('zero contrast uses positive-alpha limiting coverage',np.max(np.abs(actual-.5))<3e-5)
    layer.inputs['Contrast'].default_value=1;layer.inputs['Emit Mask'].default_value=1;actual=render(testmat,layer.outputs['Emission Visibility']);expected=1-.5*.8*.8*(3-2*.8);check('emission visibility follows the independent layer formula',np.max(np.abs(actual-expected))<3e-5)

    uv=mb.multiBlendUVNode(nt)
    for name,value in zip(('ScaleU','ScaleV','OffsetU','OffsetV','MinU','MaxU','MinV','MaxV'),(.5,.25,.1,.2,1.25,.5,.25,.5)):uv.inputs[name].default_value=value
    b=nodes.ShaderGroupBuilder(nt);coord=b.separateXYZ(uv.outputs['Vector'])
    for value,mask in [((1.25,.75,0),1),((1.5,.5,0),1),((.25,.75,0),0),((1.125,.75,0),0),((1.25,.875,0),0)]:
        uv.inputs['UV'].default_value=value;actual=render(testmat,pack(nt,coord['X'],coord['Y'],uv.outputs['Inside']));fu=value[0]%1;fv=(1-value[1])%1;expected=[fu*.5+.1,1-(fv*.25+.2),mask]
        check('atlas UV/tile and inclusive bounds '+str(value),np.max(np.abs(actual-expected))<3e-5,actual.tolist())

    owner,mat=fixture();nt=mat.node_tree
    check('actual MDF importer loads and constructs both atlas slots',all(x in nt.nodes for x in ['MultiBlend_ALBDMap','MultiBlend_NRMMap','MultiBlend_Layer_00','MultiBlend_Layer_01']))
    check('atlas slot color spaces distinguish color from data',nt.nodes['MultiBlend_ALBDMap'].image.colorspace_settings.name=='sRGB' and nt.nodes['MultiBlend_NRMMap'].image.colorspace_settings.name=='Non-Color')
    last=nt.nodes['MultiBlend_Layer_01'];actual=render(mat,last.outputs['Color']);reference=oracle([.2,.3,.4],[0,0,1],.4,.48,[.7,.4,.2,.5],[.3,.8,.6,.7],.6,1,1,1,0,1,1,0)
    check('left region uses first atlas patch and skips second region',np.max(np.abs(actual-reference[0]))<3e-5,actual.tolist())
    setuv(.75,.5);actual=render(mat,last.outputs['Color']);reference=oracle([.4,.3,.2],[0,0,1],.4,.48,[.2,.6,.4,.8],[.8,.6,.4,.4],-.4,1,1,1,0,1,1,0)
    check('right region uses its separate atlas patch',np.max(np.abs(actual-reference[0]))<3e-5,actual.tolist())
    setuv();setvalue(owner,'ChangeUV',1);actual=render(mat,last.outputs['Color']);reference=oracle([.4,.3,.2],[0,0,1],.4,.48,[.7,.4,.2,.5],[.3,.8,.6,.7],.6,1,1,1,0,1,1,0)
    check('MultiBlend retains primary UV while base ChangeUV selects secondary',np.max(np.abs(actual-reference[0]))<3e-5)
    check('no emission texture does not gain a spurious emissive branch',not next(n for n in nt.nodes if n.type=='BSDF_PRINCIPLED').inputs['Emission Color'].is_linked)
    layered,layeredmat=fixture('Existing layers',stack=True);first=layeredmat.node_tree.nodes['MultiBlend_Layer_00']
    check('MultiBlend follows the existing Detail and ColorLayer chain',first.inputs['Base Color'].links[0].from_node.node_tree.name=='MHWildsColorLayer')
    emitowner,emitmat=fixture('Emission mask',emission=True);setvalue(emitowner,'Use_EmitMask',1)
    check('main emission and secondary emission retain mask wiring',any(n.label=='SecEmit' and n.inputs['Strength'].is_linked for n in emitmat.node_tree.nodes))

    idle,idlemat=fixture('Initially disabled',weights=(0,0,0,0));check('zero weights skip atlas loading and branch construction','MultiBlend_ALBDMap' not in idlemat.node_tree.nodes and 'MultiBlend_Layer_00' not in idlemat.node_tree.nodes)
    setvalue(idle,'Blend_A',(.7,0,0,0));flush();check('live weight activation reloads GPBF binding and constructs a layer','MultiBlend_Layer_00' in idlemat.node_tree.nodes and 're_mdf_multiblend_status' in idlemat)
    count=len(imports);setvalue(idle,'Blend_A',(-.3,0,0,0));flush();check('nonzero signed weight changes do not rebuild',len(imports)==count)
    setvalue(idle,'Blend_A',(0,0,0,0));flush();check('returning weights to zero removes atlas dependency','MultiBlend_ALBDMap' not in idlemat.node_tree.nodes)
    setvalue(idle,'Blend_A',(.4,.5,0,0));setvalue(idle,'Blend_num',0);flush();check('Blend_num zero keeps layers disabled','MultiBlend_Layer_00' not in idlemat.node_tree.nodes)
    setvalue(idle,'Blend_num',1.1);flush();check('fractional Blend_num follows source loop comparison and includes index 1','MultiBlend_Layer_01' in idlemat.node_tree.nodes)
    old,oldmat=fixture('Other game',game='RE4');check('other games do not acquire Wilds MultiBlend dependencies or groups','MultiBlend_ALBDMap' not in oldmat.node_tree.nodes and not any(n.name.startswith('MultiBlend_Layer_') for n in oldmat.node_tree.nodes))
    check('new MultiBlend properties participate in live callbacks',nodes.MHWILDS_MULTIBLEND_LIVE_PROPS<=props.editablePropsSet)
    saved=(root/'Atlas.gpbf.3').read_bytes()
    (root/'Atlas.gpbf.3').write_bytes(struct.pack('<BI',0,3)+struct.pack('<8f',1,1,0,0,0,1,0,1)*32)
    highest,highestmat=fixture('Last weight',weights=(0,0,0,0),count=32)
    h=highest.re_mdf_material.propertyList_items.add();h.prop_name='Blend_H';h.data_type='VEC4';h.float_vector_value=(0,0,0,.9);flush();check('Blend_H.w addresses the 32nd GPBF entry','MultiBlend_Layer_31' in highestmat.node_tree.nodes)
    (root/'Atlas.gpbf.3').write_bytes(saved)
    missing,missingmat=fixture('Missing GPBF',weights=(0,0,0,0));missing.re_mdf_material.gpbfData_items[0].gpbfDataString='MultiBlend_BAB,missing.gpbf,0,0';setvalue(missing,'Blend_A',(.5,0,0,0));flush();check('missing GPBF keeps the base material and records the unsupported dependency','MultiBlend_Layer_00' not in missingmat.node_tree.nodes and 'Could not find' in missingmat.get('re_mdf_multiblend_status','') and 'RE Missing Texture Fallback' not in missingmat.node_tree.nodes)
    overflow,overflowmat=fixture('Unavailable rectangle',weights=(0,0,0,0),count=4);setvalue(overflow,'Blend_A',(0,0,0,.5));flush();check('unavailable rectangle is diagnosed instead of invented',json.loads(overflowmat['re_mdf_multiblend_status'])['unavailable_indices']==[3])
    if args.real_assets:
        import hashlib
        check('real asset probe has a survey source',args.survey is not None)
        survey=json.loads(args.survey.read_text(encoding='utf-8'))
        record=next(r for r in survey['materials'] if 'ch02_002_0002.mdf' in r['file'])
        source_path=Path(record['file']);before=hashlib.sha256(source_path.read_bytes()).hexdigest()
        original_file=mdf.readMDF(str(source_path));source=original_file.materialList[record['index']]
        source.getPropertyDict()['Blend_A'].propValue[0]=.8 #In memory only; never write MDF or game textures.
        original_file.materialList=[source]
        for name,value in originals.items():setattr(main,name,value)
        main.showErrorMessageBox=errors.append
        preferences=bpy.context.preferences.addons[addon.name].preferences
        preferences.useDDS=True;preferences.textureCachePath=str(args.report.parent/'real_asset_cache' if args.report else root/'real_asset_cache')
        realmat=bpy.data.materials.new(source.materialName)
        chunk=r'E:\Program\Steam\steamapps\common\MonsterHunterWilds\MHWILDS_EXTRACT'
        main.importMDF(original_file,{source.materialName:realmat},False,False,False,False,chunkPath=chunk,gameName='MHWILDS')
        check('original clothing MDF and real TEX/GPBF build the first MultiBlend layer','MultiBlend_Layer_00' in realmat.node_tree.nodes and 'RE Missing Texture Fallback' not in realmat.node_tree.nodes)
        status=json.loads(realmat['re_mdf_multiblend_status']);transform,bounds=mb.readMultiBlendGPBF(status['buffer'])[0]
        setuv(math.floor(bounds[0])+((bounds[0]%1)+bounds[1])*.5,1-((bounds[2]%1)+bounds[3])*.5)
        actual=render(realmat,realmat.node_tree.nodes['MultiBlend_Layer_00'].outputs['Color'])
        check('original clothing atlas renders finite nonblack color',np.all(np.isfinite(actual)) and float(max(actual))>0,actual.tolist())
        check('real atlas samples retain file-backed DDS images',realmat.node_tree.nodes['MultiBlend_00_MultiBlend_ALBDMap'].image.source=='FILE' and realmat.node_tree.nodes['MultiBlend_00_MultiBlend_NRMMap'].image.source=='FILE')
        check('original MDF bytes remain unchanged',hashlib.sha256(source_path.read_bytes()).hexdigest()==before)
        results['real_asset_probe']={'mdf':str(source_path),'sha256':before,'buffer':status['buffer'],'active_layers':status['active_layers'],'in_memory_weight_override':{'Blend_A.x':.8},'color':actual.tolist()}
    check('all importer runs completed without graph errors',not errors)
except Exception as error:
    results['error']=repr(error);raise
finally:
    live.clearPendingLivePreviews()
    for name,value in originals.items():setattr(main,name,value)
    scratch.cleanup()
    results['passed']=not results.get('error') and bool(results['checks']) and all(c['passed'] for c in results['checks'])
    if args.report:args.report.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print('MULTIBLEND_TEST_SUMMARY '+json.dumps({'passed':results['passed'],'checks':len(results['checks'])}),flush=True)
