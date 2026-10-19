"""Real MDF importer failure/recovery tests in a disposable factory scene.
blender --background --factory-startup --python-exit-code 1 --python FILE -- --report JSON
Optional --staged ROOT replaces only the importer module before installation.
Texture path resolution/conversion are fault-injected; Blender nodes and renders are real.
"""
import argparse
from collections import Counter
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

import addon_utils
import bpy
import numpy as np

cli = argparse.ArgumentParser()
cli.add_argument('--staged', type=Path)
cli.add_argument('--report', type=Path)
args = cli.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
installed = Path(r'C:\Users\Sheeran\AppData\Roaming\Blender Foundation\Blender\5.1\scripts\addons\RE-Mesh-Editor-MeshFixes') if args.staged else Path(__file__).resolve().parents[1]
sys.path.insert(0, str(installed.parent))
addon_utils.enable(installed.name, default_set=True)
main = importlib.import_module(installed.name+'.modules.mdf.blender_re_mesh_mdf')
mdf = importlib.import_module(installed.name+'.modules.mdf.file_re_mdf')
if args.staged:
    path = args.staged/'modules/mdf/blender_re_mesh_mdf.py'
    exec(compile(path.read_text(encoding='utf-8-sig'), str(path), 'exec'), main.__dict__)
results = {'blender':bpy.app.version_string, 'staged':str(args.staged) if args.staged else None, 'checks':[]}

def check(name, ok, detail=None):
    results['checks'].append({'name':name, 'passed':bool(ok), 'detail':detail})
    print(('PASS ' if ok else 'FAIL ')+name, flush=True)
    assert ok, name

good = bpy.data.images.new('Valid imported texture', 2, 2, alpha=True)
good.generated_color = (.2,.4,.6,1)
calls = Counter()
unresolved = {'missing', 'autodetect_ALB'}
warnings = []
messages = []

def load(path, *a, **k):
    calls[path] += 1
    if path == 'throws':
        raise RuntimeError('Injected texture conversion failure')
    return {'empty':[], 'none':None, 'null':[None], 'partial':[good,None],
            'zero':[SimpleNamespace(size=(0,0),has_data=False)],
            'unloaded':[SimpleNamespace(size=(2,2),has_data=False)]}.get(path, [good])

names = ('Texconv','unload_texconv','getTexPath','loadTex','showErrorMessageBox','raiseWarning','getChunkPathList','MHWILDS_SLOT_NULL_TEXTURES')
originals = {name:getattr(main,name) for name in names}
main.Texconv = lambda:None
main.unload_texconv = lambda:None
main.getTexPath = lambda base,*a,**k:None if base in unresolved else base
main.loadTex = load
main.showErrorMessageBox = messages.append
main.raiseWarning = warnings.append
main.getChunkPathList = lambda game:[]
slotNulls = main.MHWILDS_SLOT_NULL_TEXTURES
#The neutral-material checks below cover slots without a vanilla null; slot nulls are tested after them.
main.MHWILDS_SLOT_NULL_TEXTURES = {}

def entry(name, bindings, values=None):
    material = mdf.Material()
    material.materialName = name
    material.mmtrPath = 'MaterialShader/Variation/Base_ATOS_SkinEdit_VFX.mmtr'
    material.shaderType = 0
    material.textureList = []
    material.propertyList = []
    for slot,path in bindings:
        tex = mdf.TextureBinding();tex.textureType=slot;tex.texturePath=path+'.tex'
        material.textureList.append(tex)
    for name,value in (values or {}).items():
        prop=mdf.Property();prop.propName=name;prop.paramCount=len(value);prop.propValue=value
        material.propertyList.append(prop)
    return material

def run(entries, unused=False, existing=None, game='MHWILDS'):
    file=mdf.MDFFile();file.fileVersion=45;file.materialList=entries
    mats=existing or {e.materialName:bpy.data.materials.new(e.materialName) for e in entries}
    main.importMDF(file,mats,unused,False,False,True,chunkPath='',gameName=game)
    check('import has no material construction error '+','.join(mats),not messages)
    return mats

def fallback(mat):
    return mat.node_tree.nodes.get('RE Missing Texture Fallback')

try:
    #A valid binding between repeated missing paths used to leak into the later one.
    first_entry=entry('Missing first',[('BaseDielectricMap','missing')],{'ColorParam':[5,0,0,0]})
    mats=run([first_entry,
              entry('Valid middle',[('BaseDielectricMap','good')]),
              entry('Missing repeated',[('BaseDielectricMap','missing')])])
    check('first and repeated unresolved bindings both use a neutral material',fallback(mats['Missing first']) is not None and fallback(mats['Missing repeated']) is not None)
    check('valid material between missing bindings keeps its actual texture',fallback(mats['Valid middle']) is None and mats['Valid middle'].node_tree.nodes['BaseDielectricMap'].image==good)
    detail=json.loads(mats['Missing repeated']['re_mdf_preview_missing_textures'])
    check('diagnostics preserve the original missing slot and path',detail==[{'slot':'BaseDielectricMap','path':'missing.tex','resolved_path':None}])
    check('fallback contains only a shader and output, no image substitutions',len(mats['Missing first'].node_tree.nodes)==2)
    shader=fallback(mats['Missing first'])
    check('fallback is neutral grey opaque nonmetal',tuple(shader.inputs['Base Color'].default_value)==(.5,.5,.5,1) and shader.inputs['Alpha'].default_value==1 and shader.inputs['Metallic'].default_value==0)

    for path in ['throws','empty','none','null','partial','zero','unloaded']:
        mat=run([entry('Failure '+path,[('BaseDielectricMap',path)])])['Failure '+path]
        check('failed conversion/data uses neutral material: '+path,fallback(mat) is not None)
    before=calls['throws']
    shared=run([entry('Shared bad A',[('BaseDielectricMap','throws')]),entry('Shared good',[('BaseDielectricMap','good')]),entry('Shared bad B',[('BaseDielectricMap','throws')])])
    check('failed conversion cached once without leaking the good image',calls['throws']-before==1 and fallback(shared['Shared bad B']) is not None)

    mat=run([entry('Missing normal',[('BaseDielectricMap','good'),('NormalRoughnessOcclusionMap','missing')])])['Missing normal']
    check('failure in a non-base used slot also yields an empty material',fallback(mat) is not None)
    mat=run([entry('Missing unused',[('BaseDielectricMap','good'),('UnknownReference','missing')])],unused=True)['Missing unused']
    check('unused missing texture does not blank an otherwise valid preview',fallback(mat) is None and 're_mdf_preview_missing_textures' not in mat)
    mat=run([entry('Disabled feature',[('BaseDielectricMap','good'),('BlendNormalMap','missing')],{'NormalBlendParam':[0]})],unused=True)['Disabled feature']
    check('disabled feature loaded for inspection does not trigger fallback',fallback(mat) is None)
    mat=run([entry('Enabled feature',[('BaseDielectricMap','good'),('BlendNormalMap','missing')],{'NormalBlendParam':[1]})])['Enabled feature']
    check('enabled feature with missing dependency triggers fallback',fallback(mat) is not None)
    mat=run([entry('Detected albedo',[('CustomColor','autodetect_ALB')])])['Detected albedo']
    check('autodetected albedo failure also triggers fallback',fallback(mat) is not None)
    mat=run([entry('Other game',[('BaseDielectricMap','missing')])],game='RE4')['Other game']
    check('neutral fallback also applies to other games',fallback(mat) is not None)

    recovered=mats['Missing first']
    run([entry('Missing first',[('BaseDielectricMap','good')])],existing={'Missing first':recovered})
    check('reapplying after texture recovery rebuilds the normal material and clears diagnostics',fallback(recovered) is None and 're_mdf_preview_missing_textures' not in recovered and recovered.node_tree.nodes['BaseDielectricMap'].image==good)
    check('fallback has not modified MDF bindings or parameter values',first_entry.textureList[0].texturePath=='missing.tex' and first_entry.getPropertyDict()['ColorParam'].propValue==[5,0,0,0])

    #Unresolved Wilds slots preview their vanilla null instead of blanking the material.
    main.MHWILDS_SLOT_NULL_TEXTURES = slotNulls
    def nullKey(mat,node):
        image = mat.node_tree.nodes[node].image
        return image.get('re_mdf_null_fallback_key') if image else None
    unresolved.update({'missing_ALBD','missing_NRRH'})
    mat=run([entry('Slot null detail',[('BaseDielectricMap','good'),('Detail_ALBD_R','missing_ALBD'),('Detail_NRRH_R','missing_NRRH')],{'UseDetail':[1]})])['Slot null detail']
    check('missing detail textures keep the material',fallback(mat) is None and 're_mdf_preview_missing_textures' not in mat)
    nulls=json.loads(mat['re_mdf_preview_null_fallbacks'])
    check('diagnostics name the missing path and the slot null used',{'slot':'Detail_ALBD_R','path':'missing_ALBD.tex','fallback':'systems/rendering/nullgray'} in nulls and {'slot':'Detail_NRRH_R','path':'missing_NRRH.tex','fallback':'systems/rendering/nullnormalroughnessocclusion'} in nulls,nulls)
    mat=run([entry('Slot null base',[('BaseDielectricMap','missing'),('NormalRoughnessOcclusionMap','missing')])])['Slot null base']
    check('missing base slots use NullGray/NullNRRO, not the neutral material',fallback(mat) is None and nullKey(mat,'BaseDielectricMap')=='MHWILDS:systems/rendering/nullgray:sRGB:0' and nullKey(mat,'NormalRoughnessOcclusionMap')=='MHWILDS:systems/rendering/nullnormalroughnessocclusion:Non-Color:0')
    mat=run([entry('Slot null unknown',[('CustomColor','autodetect_ALB')])])['Slot null unknown']
    check('a slot without a vanilla null still uses the neutral material',fallback(mat) is not None)
    mat=run([entry('Slot null other game',[('BaseDielectricMap','missing')])],game='RE4')['Slot null other game']
    check('slot nulls are Wilds only',fallback(mat) is not None)
    furProps={name:[v] for name,v in (('Fur_Push',.02),('Fur_Stand',0),('Fur_Density',20),('FurNormal_Blend',0),('FurNoise_Blend',0),('FurAlpha_Contrast',1),('FurAlpha_Fade',.5),('FurKink',0))}
    mat=run([entry('Fur noise missing',[('BaseDielectricMap','good'),('FurNoiseMap','missing'),('FurFlowMap','good')],furProps)])['Fur noise missing']
    check('missing FurNoiseMap is never replaced by a flat null',fallback(mat) is None and 'MHWilds SFUR Surface' not in mat.node_tree.nodes and 're_mdf_preview_null_fallbacks' not in mat)
    check('missing FurNoiseMap is reported for the fur preview',mat.get('re_mdf_preview_fur_noise_missing')=='missing.tex')
    run([entry('Fur noise missing',[('BaseDielectricMap','good'),('FurNoiseMap','good'),('FurFlowMap','good')],furProps)],existing={'Fur noise missing':mat})
    check('resolving FurNoiseMap builds the fur surface and clears the report','MHWilds SFUR Surface' in mat.node_tree.nodes and 're_mdf_preview_fur_noise_missing' not in mat)
    unresolved.add(os.sep.join(('systems','rendering','NullNormalRoughness')))
    mat=run([entry('Measured NullNormalRoughness',[('BaseDielectricMap','good'),('NormalRoughnessOcclusionMap','systems/rendering/NullNormalRoughness')])])['Measured NullNormalRoughness']
    image=mat.node_tree.nodes['NormalRoughnessOcclusionMap'].image
    check('NullNormalRoughness path uses its measured value',image.get('re_mdf_null_fallback_key')=='MHWILDS:systems/rendering/nullnormalroughness:Non-Color:0' and [round(v*255) for v in image.generated_color]==[128,128,255,128])

    #Render the actual fallback surface, including alpha, in a neutral world.
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    bpy.ops.mesh.primitive_plane_add(size=4);plane=bpy.context.object
    plane.data.materials.append(mats['Missing repeated'])
    camera_data=bpy.data.cameras.new('Fallback test');camera=bpy.data.objects.new('Fallback test',camera_data)
    bpy.context.scene.collection.objects.link(camera);camera.location=(0,0,2);camera_data.type='ORTHO';camera_data.ortho_scale=2
    scene=bpy.context.scene;scene.camera=camera;scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=4;scene.cycles.use_denoising=False
    scene.render.resolution_x=16;scene.render.resolution_y=16;scene.render.resolution_percentage=100
    scene.render.film_transparent=True
    world=bpy.data.worlds.new('Neutral test world');world.use_nodes=True;world.node_tree.nodes['Background'].inputs['Color'].default_value=(1,1,1,1);scene.world=world
    scene.render.image_settings.file_format='OPEN_EXR';scene.render.image_settings.color_mode='RGBA';scene.render.image_settings.color_depth='32'
    with tempfile.TemporaryDirectory(prefix='reme_missing_') as scratch:
        scene.render.filepath=str(Path(scratch)/'fallback.exr');bpy.ops.render.render(write_still=True)
        image=bpy.data.images.load(scene.render.filepath,check_existing=False)
        pixels=np.array(image.pixels[:],dtype=float).reshape(16,16,4);rgba=pixels[8,8].tolist()
        check('rendered fallback is visible opaque grey, without red tint',max(rgba[:3])-min(rgba[:3])<1e-5 and rgba[0]>.01 and abs(rgba[3]-1)<1e-5,rgba)
        bpy.data.images.remove(image)
finally:
    for name,value in originals.items():setattr(main,name,value)
    results['passed']=bool(results['checks']) and all(c['passed'] for c in results['checks'])
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print('MISSING_TEXTURE_TEST_SUMMARY '+json.dumps({'passed':results['passed'],'checks':len(results['checks'])}),flush=True)
