"""Measured null resource substitution checks; real importer/nodes and Cycles renders.
Optional --evidence DIR compares fallback samples to DDS decoded from real game TEX.
No user scene is opened or saved; texture loading errors are injected in this factory process.
"""
import argparse
import importlib
import json
from pathlib import Path
import sys
import tempfile
import addon_utils
import bpy
import numpy as np

parser=argparse.ArgumentParser();parser.add_argument('--staged',type=Path);parser.add_argument('--report',type=Path);parser.add_argument('--evidence',type=Path)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
addon=Path(r'C:\Users\Sheeran\AppData\Roaming\Blender Foundation\Blender\5.1\scripts\addons\RE-Mesh-Editor-MeshFixes') if args.staged else Path(__file__).resolve().parents[1]
sys.path.insert(0,str(addon.parent));addon_utils.enable(addon.name,default_set=True)
main=importlib.import_module(addon.name+'.modules.mdf.blender_re_mesh_mdf')
nodes=importlib.import_module(addon.name+'.modules.mdf.blender_nodes_re_mdf')
mdf=importlib.import_module(addon.name+'.modules.mdf.file_re_mdf')
if args.staged:
    path=args.staged/'modules/mdf/blender_re_mesh_mdf.py';exec(compile(path.read_text(encoding='utf-8-sig'),str(path),'exec'),main.__dict__)
results={'blender':bpy.app.version_string,'staged':str(args.staged) if args.staged else None,'checks':[]}
def check(name,ok,detail=None):
    results['checks'].append({'name':name,'passed':bool(ok),'detail':detail});print(('PASS ' if ok else 'FAIL ')+name,flush=True)
    assert ok,(name,detail)

bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_plane_add(size=4);plane=bpy.context.object
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=1;scene.cycles.use_denoising=False
data=bpy.data.cameras.new('Null test');camera=bpy.data.objects.new('Null test',data);scene.collection.objects.link(camera);camera.location=(0,0,2);data.type='ORTHO';data.ortho_scale=2;scene.camera=camera
scene.render.resolution_x=8;scene.render.resolution_y=8;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='OPEN_EXR';scene.render.image_settings.color_mode='RGBA';scene.render.image_settings.color_depth='32'
scratch=tempfile.TemporaryDirectory(prefix='reme_null_')
def render(image,slot,path,alpha=False):
    mat=bpy.data.materials.new('Null sample');mat.use_nodes=True;nt=mat.node_tree;nt.nodes.clear()
    source=nodes.addImageNode(nt,slot,[image],path,(0,0));emission=nt.nodes.new('ShaderNodeEmission');out=nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(source.outputs['Alpha' if alpha else 'Color'],emission.inputs['Color']);nt.links.new(emission.outputs[0],out.inputs['Surface'])
    plane.data.materials.clear();plane.data.materials.append(mat)
    scene.render.filepath=str(Path(scratch.name)/'sample.exr');bpy.ops.render.render(write_still=True)
    result=bpy.data.images.load(scene.render.filepath,check_existing=False);pixels=np.array(result.pixels[:]).reshape(8,8,4);value=pixels[4,4,:3].copy();bpy.data.images.remove(result)
    return value

names=('Texconv','unload_texconv','getTexPath','loadTex','showErrorMessageBox','getChunkPathList')
originals={name:getattr(main,name) for name in names}
good=bpy.data.images.new('Real working image',2,2,alpha=True);good.generated_color=(.2,.4,.6,1)
errors=[]
main.Texconv=lambda:None;main.unload_texconv=lambda:None;main.getChunkPathList=lambda game:[];main.showErrorMessageBox=errors.append
main.getTexPath=lambda base,*a,**k:base if base in ('good','throws') else None
def load(path,*a,**k):
    if path=='throws':raise RuntimeError('Injected failure')
    return [good]
main.loadTex=load
def entry(name,bindings):
    mat=mdf.Material();mat.materialName=name;mat.shaderType=0;mat.mmtrPath='MaterialShader/Variation/Base_ATOS_SkinEdit_VFX.mmtr';mat.textureList=[];mat.propertyList=[]
    for slot,path in bindings:
        tex=mdf.TextureBinding();tex.textureType=slot;tex.texturePath=path;mat.textureList.append(tex)
    return mat
def run(entries,existing=None):
    file=mdf.MDFFile();file.fileVersion=45;file.materialList=entries
    mats=existing or {e.materialName:bpy.data.materials.new(e.materialName) for e in entries}
    main.importMDF(file,mats,False,False,False,True,gameName='MHWILDS')
    check('import completes: '+','.join(mats),not errors)
    return mats
def is_grey(mat):return 'RE Missing Texture Fallback' in mat.node_tree.nodes

try:
    #The constant catalog must reproduce decoded source pixels, including alpha and array layers.
    if args.evidence:
        evidence=json.loads((args.evidence/'null_texture_evidence.json').read_text(encoding='utf-8'))
        check('all 12 independently decoded resources are represented',len(evidence)==12 and len(main.MHWILDS_NULL_TEXTURES)==12)
        for e in evidence:
            rgba,count=main.MHWILDS_NULL_TEXTURES[e['path'].rsplit('.tex.',1)[0].lower()]
            check('constant catalog matches original TEX: '+e['path'],count==len(e['layers']) and all(np.max(np.abs(np.array(rgba)/255-np.array(layer['first_rgba'])))<1e-7 for layer in e['layers']))
            #Check actual shader color and alpha after addImageNode refreshes image settings.
            for slot in ['NormalRoughnessOcclusionMap','BaseDielectricMap']:
                output=e['path'].rsplit('.tex.',1)[0]+'.png'
                generated=main.getSystemNullTextureImages(e['path'],slot,output,'MHWILDS')
                realpath=args.evidence/'decoded'/Path(e['path']).with_suffix('.dds')
                if count>1:realpath=realpath.with_name(realpath.stem+' #ARRAY_00.dds')
                real=bpy.data.images.load(str(realpath),check_existing=False)
                color_error=float(np.max(np.abs(render(real,slot,output)-render(generated[0],slot,output))))
                alpha_error=float(np.max(np.abs(render(real,slot,output,True)-render(generated[0],slot,output,True))))
                check('rendered null matches real color/alpha '+slot+': '+e['path'],max(color_error,alpha_error)<2e-5,{'max_color_error':color_error,'max_alpha_error':alpha_error})
                bpy.data.images.remove(real)

    for path in main.MHWILDS_NULL_TEXTURES:
        mat=run([entry('Known null',[('BaseDielectricMap',path+'.tex')])])['Known null']
        check('known null does not replace the whole material: '+path,not is_grey(mat) and 're_mdf_preview_missing_textures' not in mat and len(json.loads(mat['re_mdf_preview_null_fallbacks']))==1)

    cases=[entry('Normal nulls',[('BaseDielectricMap','good.tex'),('NormalRoughnessOcclusionMap','systems/rendering/NullNormalRoughnessOcclusion.tex'),('AlphaTranslucentOcclusionSSSMap','systems/rendering/NullATOS.tex')]),entry('Repeat nulls',[('BaseDielectricMap','good.tex'),('NormalRoughnessOcclusionMap','systems/rendering/NullNormalRoughnessOcclusion.tex')])]
    mats=run(cases)
    check('NRRO/ATOS default maps retain the actual base texture',not is_grey(mats['Normal nulls']) and mats['Normal nulls'].node_tree.nodes['BaseDielectricMap'].image==good)
    check('NRRO default still uses the existing one-pass decode',any(n.type=='GROUP' and n.node_tree.name=='MHWildsNRRODecode_v1' for n in mats['Normal nulls'].node_tree.nodes))
    check('AO combines default full occlusion visibility',mats['Normal nulls'].node_tree.nodes.get('MHWildsOcclusion') is not None)
    #An unresolved binding previews as its slot's vanilla null; the path itself is never matched by filename.
    mat=run([entry('True missing',[('BaseDielectricMap','Art/Model/nullwhite.tex')])])['True missing'];check('unregistered null filename is a missing texture shown as the slot null',not is_grey(mat) and {'slot':'BaseDielectricMap','path':'Art/Model/nullwhite.tex','fallback':'systems/rendering/nullgray'} in json.loads(mat['re_mdf_preview_null_fallbacks']))
    mat=run([entry('Mixed errors',[('BaseDielectricMap','throws.tex'),('NormalRoughnessOcclusionMap','systems/rendering/NullNormalRoughnessOcclusion.tex')])])['Mixed errors'];nulls=json.loads(mat['re_mdf_preview_null_fallbacks']);check('a known null and a genuine failure stay separately recorded',[n.get('fallback') for n in nulls]==['systems/rendering/nullgray',None],nulls)

    alias=main.getSystemNullTextureImages(r'SYSTEMS\RENDERING\@NullWhite.TEX.241106027','BaseDielectricMap','white.png','MHWILDS')
    check('logical path normalization handles case, slashes, marker and version',alias is not None)
    check('same basename in another directory is not whitelisted',main.getSystemNullTextureImages('Art/Character/NullWhite.tex','BaseDielectricMap','white.png','MHWILDS') is None)
    check('unknown null variant is not guessed',main.getSystemNullTextureImages('systems/rendering/NullCustom.tex','BaseDielectricMap','white.png','MHWILDS') is None)
    check('measured Wilds packed defaults are not applied to another game',main.getSystemNullTextureImages('systems/rendering/NullNormal.tex','NormalMap','normal.png','RE4') is None)
    a=main.getSystemNullTextureImages('systems/rendering/NullGray.tex','BaseDielectricMap','gray.png','MHWILDS')
    b=main.getSystemNullTextureImages('systems/rendering/NullGray.tex','NormalMap','gray.png','MHWILDS')
    check('color and data use different Image datablocks',a[0]!=b[0] and a[0].colorspace_settings.name=='sRGB' and b[0].colorspace_settings.name=='Non-Color')
    check('repeat requests reuse their generated image',main.getSystemNullTextureImages('systems/rendering/NullGray.tex','BaseDielectricMap','gray.png','MHWILDS')[0]==a[0])
    array=main.getSystemNullTextureImages('MasterMaterial/Textures/TextureArray/nullWhite_Array.tex','BaseDielectricMap','white.png','MHWILDS')
    check('null array preserves its two layers',len(array)==2 and array[0]!=array[1])

    #A real successfully loaded system null always wins over the substitute.
    main.getTexPath=lambda base,*a,**k:base
    mat=run([entry('Real null available',[('BaseDielectricMap','systems/rendering/NullWhite.tex')])])['Real null available']
    check('real successful image is retained instead of substituting',mat.node_tree.nodes['BaseDielectricMap'].image==good and 're_mdf_preview_null_fallbacks' not in mat)
    main.loadTex=lambda *a,**k:[]
    mat=run([entry('Invalid real null',[('BaseDielectricMap','systems/rendering/NullWhite.tex')])])['Invalid real null']
    check('conversion producing invalid image data also gets a null substitute',not is_grey(mat) and 're_mdf_preview_null_fallbacks' in mat)
    main.loadTex=lambda *a,**k:[good]
    run([entry('Invalid real null',[('BaseDielectricMap','systems/rendering/NullWhite.tex')])],existing={'Invalid real null':mat})
    check('reapplying after original null recovery clears substitute diagnostics','re_mdf_preview_null_fallbacks' not in mat and mat.node_tree.nodes['BaseDielectricMap'].image==good)
finally:
    for name,value in originals.items():setattr(main,name,value)
    scratch.cleanup()
    results['passed']=bool(results['checks']) and all(c['passed'] for c in results['checks'])
    if args.report:args.report.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print('NULL_TEXTURE_TEST_SUMMARY '+json.dumps({'passed':results['passed'],'checks':len(results['checks'])}),flush=True)
