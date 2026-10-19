"""Render synthetic NRRO data and compare the installed decoder to the Wilds formula.

blender --background --factory-startup --python-exit-code 1 --python tests/test_mhwilds_nrro_blender.py
Optional -- --source PATH tests a staged node module without loading the addon.
No retail textures or user scenes are read or saved.
"""
import argparse
import ast
import importlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

import bpy
import numpy as np

parser=argparse.ArgumentParser()
parser.add_argument('--source',type=Path)
parser.add_argument('--report',type=Path)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
if args.source:
    source=ast.parse(args.source.read_text(encoding='utf-8-sig'))
    source.body=[n for n in source.body if not (isinstance(n,ast.ImportFrom) and n.level)]
    env={'__file__':str(args.source),'colorPropertySet':set(),'albedoTypeSet':set()}
    exec(compile(source,str(args.source),'exec'),env)
    nodes=SimpleNamespace(**env)
else:
    repo=Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(repo.parent))
    import addon_utils
    addon_utils.enable(repo.name,default_set=False)
    nodes=importlib.import_module(repo.name+'.modules.mdf.blender_nodes_re_mdf')

results={'blender':bpy.app.version_string,'staged_source':str(args.source) if args.source else None,'checks':[]}
def check(name,ok,detail=None):
    results['checks'].append({'name':name,'passed':bool(ok),'detail':detail})
    print(('PASS ' if ok else 'FAIL ')+name+(' '+str(detail) if detail is not None else ''),flush=True)

def new_tree():
    mat=bpy.data.materials.new('NRRO decoder test');mat.use_nodes=True
    mat.node_tree.nodes.clear()
    return mat,mat.node_tree

def routing(game,texture_type):
    mat,nt=new_tree()
    image=nt.nodes.new('ShaderNodeTexImage');image.name=texture_type
    info={'gameName':game,'mPropDict':{},'normalNodeLayerGroup':nodes.dynamicColorMixLayerNodeGroup(nt),'roughnessNodeLayerGroup':nodes.dynamicColorMixLayerNodeGroup(nt),
          'aoNodeLayerGroup':nodes.dynamicColorMixLayerNodeGroup(nt),'cavityNodeLayerGroup':nodes.dynamicColorMixLayerNodeGroup(nt)}
    nodes.newNRRTNode(nt,texture_type,info)
    decode=info['normalNodeLayerGroup'].currentOutSocket.node
    return decode.node_tree.name,decode.inputs['Color'].links[0].from_node==image and decode.inputs['Alpha'].links[0].from_node==image

for game,slot,expected in [('MHWILDS','NormalRoughnessOcclusionMap','MHWildsNRRODecode_v1'),('RE4','NormalRoughnessOcclusionMap','BentNormalNodeGroup'),
                           ('RE2','NormalRoughnessOcclusionMap','BentNormalNodeGroup'),('MHWILDS','NormalRoughnessTranslucencyMap','BentNormalNodeGroup')]:
    group,direct=routing(game,slot)
    check(game+' '+slot+' decoder routing',group==expected,group)
    check(game+' '+slot+' decodes raw image once',direct)
mat,nt=new_tree()
decode1=nodes.getMHWildsNRRONodeGroup(nt);decode2=nodes.getMHWildsNRRONodeGroup(nt)
check('new decoder shares a separate group without modifying the legacy group',decode1.node_tree==decode2.node_tree and decode1.node_tree.name!='BentNormalNodeGroup' and 'BentNormalNodeGroup' in bpy.data.node_groups)

# Independent numerical reference from the compiled SkinEdit shader's G/A decode.
samples=np.array([0.0,0.1,0.25,0.5,0.6,0.75,0.9,1.0],dtype=np.float64)
g,alpha=np.meshgrid(samples,samples)
u=2*g-1;v=2*alpha-1
u=u*np.abs(u);v=v*np.abs(v)
x=(u+v)*0.5;y=(u-v)*0.5;z=1-np.abs(x)-np.abs(y)
reference=np.stack([x,y,z],axis=-1)
reference/=np.linalg.norm(reference,axis=-1,keepdims=True)
expected_color=reference*0.5+0.5
rows,cols=np.indices(g.shape)
roughness=0.15+0.7*((rows+cols)%8)/7
ao=0.2+0.6*rows/7
rgba=np.stack([roughness,g,ao,alpha],axis=-1).astype(np.float32)

bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene
scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=1;scene.cycles.use_denoising=False
scene.render.resolution_x=64;scene.render.resolution_y=64;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='OPEN_EXR';scene.render.image_settings.color_mode='RGBA';scene.render.image_settings.color_depth='32'
scene.render.film_transparent=False
camera_data=bpy.data.cameras.new('NRRO test camera');camera=bpy.data.objects.new('NRRO test camera',camera_data)
scene.collection.objects.link(camera);camera.location=(0,0,2);camera_data.type='ORTHO';camera_data.ortho_scale=2;scene.camera=camera
bpy.ops.mesh.primitive_plane_add(size=2)
plane=bpy.context.object;plane.data.uv_layers.active.name='UVMap0'
mat,nt=new_tree();plane.data.materials.append(mat)
raw=bpy.data.images.new('Synthetic packed NRRO',8,8,alpha=True,float_buffer=True)
raw.colorspace_settings.name='Non-Color';raw.alpha_mode='CHANNEL_PACKED';raw.pixels.foreach_set(rgba.ravel());raw.update()
tex=nt.nodes.new('ShaderNodeTexImage');tex.image=raw;tex.interpolation='Closest'
decode=nodes.getMHWildsNRRONodeGroup(nt)
nt.links.new(tex.outputs['Color'],decode.inputs['Color']);nt.links.new(tex.outputs['Alpha'],decode.inputs['Alpha'])
emit=nt.nodes.new('ShaderNodeEmission');out=nt.nodes.new('ShaderNodeOutputMaterial');nt.links.new(emit.outputs[0],out.inputs['Surface'])

def render_samples(scratch,name,socket):
    nt.links.new(socket,emit.inputs['Color'])
    path=Path(scratch)/(name+'.exr');scene.render.filepath=str(path)
    bpy.ops.render.render(write_still=True)
    image=bpy.data.images.load(str(path),check_existing=False);image.colorspace_settings.name='Non-Color'
    pixels=np.empty(len(image.pixels),dtype=np.float32);image.pixels.foreach_get(pixels)
    image_pixels=pixels.reshape(64,64,4)
    centers=np.arange(8)*8+4
    values=image_pixels[centers[:,None],centers[None,:],:3].copy()
    bpy.data.images.remove(image)
    return values

with tempfile.TemporaryDirectory(prefix='reme_nrro_') as scratch:
    decoded=render_samples(scratch,'decoded',decode.outputs['Color'])
    error=float(np.max(np.abs(decoded-expected_color)))
    check('rendered 64 G/A pairs match the original shader decode',error<5e-5,{'max_rgb_error':error})
    rgb=nt.nodes.new('ShaderNodeCombineColor')
    nt.links.new(decode.outputs['Roughness'],rgb.inputs[0]);nt.links.new(decode.outputs['BlueChannel'],rgb.inputs[1]);rgb.inputs[2].default_value=0.25
    channels=render_samples(scratch,'channels',rgb.outputs['Color'])
    channel_error=float(np.max(np.abs(channels-np.stack([roughness,ao,np.full_like(ao,0.25)],axis=-1))))
    check('roughness R and AO B pass through without alteration',channel_error<5e-5,{'max_channel_error':channel_error})
    normal=nt.nodes.new('ShaderNodeNormalMap');normal.space='TANGENT';normal.uv_map='UVMap0'
    nt.links.new(decode.outputs['Color'],normal.inputs['Color'])
    scale=nt.nodes.new('ShaderNodeVectorMath');scale.operation='SCALE';scale.inputs['Scale'].default_value=0.5
    nt.links.new(normal.outputs['Normal'],scale.inputs[0])
    offset=nt.nodes.new('ShaderNodeVectorMath');offset.operation='ADD';offset.inputs[1].default_value=(0.5,0.5,0.5)
    nt.links.new(scale.outputs[0],offset.inputs[0])
    roundtrip=render_samples(scratch,'normal_map_roundtrip',offset.outputs[0])
    roundtrip_error=float(np.max(np.abs(roundtrip-expected_color)))
    check('existing Normal Map converts RGB normally instead of repeating the NRRO decode',roundtrip_error<5e-5,{'max_rgb_error':roundtrip_error})
results['passed']=all(c['passed'] for c in results['checks'])
if args.report:
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
assert results['passed'],'NRRO regression checks failed'
print('NRRO_TEST_SUMMARY '+json.dumps(results,ensure_ascii=False),flush=True)
