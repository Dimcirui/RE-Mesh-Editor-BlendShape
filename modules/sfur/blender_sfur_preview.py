"""Reversible static shell preview, generated beside (never inside) export collections."""
import json
import math
import os
import time
from pathlib import Path
import bpy
import numpy as np
from bpy.app.handlers import persistent
from .sfur_preview_math import bilinear_repeat, generate_shells, normalize

TYPE = 'RE_SFUR_PREVIEW'
MAX_CORNERS = 2_000_000
_busy = False
_pending = {}
_image_pixels = {}


def configure_cycles(scene, count):
    cycles=getattr(scene,'cycles',None)
    if cycles is None:return
    required=min(1024,2*count+8)
    current=cycles.transparent_max_bounces
    owned=scene.get('re_sfur_cycles_auto')
    #Respect a manual edit made after the preview configured this value.
    if owned is not None and current != owned:return
    if current < required:
        if owned is None:scene['re_sfur_cycles_before']=current
        cycles.transparent_max_bounces=required
        scene['re_sfur_cycles_auto']=cycles.transparent_max_bounces


def restore_cycles():
    for scene in bpy.data.scenes:
        if 're_sfur_cycles_auto' not in scene:continue
        if any(o.get('~TYPE') == TYPE for o in scene.objects):continue
        if scene.cycles.transparent_max_bounces == scene['re_sfur_cycles_auto']:
            scene.cycles.transparent_max_bounces=scene['re_sfur_cycles_before']
        del scene['re_sfur_cycles_auto'];del scene['re_sfur_cycles_before']


def previews():
    return [o for o in bpy.data.objects if o.get('~TYPE') == TYPE]


def scalar(material, name, default=0.):
    node = material.node_tree.nodes.get(name) if material.node_tree else None
    return float(node.outputs['Value'].default_value) if node and 'Value' in node.outputs else default


def cleanup_materials():
    for material in list(bpy.data.materials):
        if material.get('re_sfur_material_source') and material.users == 0:bpy.data.materials.remove(material)


def preview_material(material, entry):
    clone=material.copy();clone.name=material.name+' SFUR Preview'
    clone['re_sfur_material_source']=material
    if entry.re_sfur_data.isForceTwoSide:clone.use_backface_culling=False
    if entry.re_sfur_data.isForceAlphaTest:
        #Only the preview copy gets a forced hard test; original MDF/graph is untouched.
        tree=clone.node_tree
        for bsdf in [n for n in tree.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled']:
            socket=bsdf.inputs['Alpha']
            if not socket.is_linked:continue
            value=socket.links[0].from_socket
            lt=tree.nodes.new('ShaderNodeMath');lt.operation='LESS_THAN'
            tree.links.new(value,lt.inputs[0])
            ref=tree.nodes.get('AlphaTest_Ref')
            if ref and 'Value' in ref.outputs:tree.links.new(ref.outputs['Value'],lt.inputs[1])
            else:lt.inputs[1].default_value=.5
            inv=tree.nodes.new('ShaderNodeMath');inv.operation='SUBTRACT';inv.inputs[0].default_value=1
            tree.links.new(lt.outputs[0],inv.inputs[1]);tree.links.new(inv.outputs[0],socket)
    return clone


def sync_material_property(material,name,values):
    from ..mdf.re_mdf_live_preview import updatePropertyNode
    for clone in bpy.data.materials:
        if clone.get('re_sfur_material_source') == material and clone.node_tree:
            updatePropertyNode(clone.node_tree,name,values)


FUR_NOISE_MISSING='re_mdf_preview_fur_noise_missing'


def fur_noise_message(material):
    return f'FurNoiseMap not found for {material.name}: {material[FUR_NOISE_MISSING]}. Add the chunk path that contains it, then Apply Active MDF'


def matching_material(material, name):
    if material is None:return False
    if material.name == name:return True
    if material.name.rsplit('.',1)[-1].isdigit() and material.name.rsplit('.',1)[0] == name:return True
    return any(o.get('~TYPE') == 'RE_MDF_MATERIAL' and o.re_mdf_material.materialName == name
               and o.re_mdf_material.linkedMaterial == material for o in bpy.data.objects)


def pixels(image):
    if image is None or image.name.startswith('Missing '):
        raise ValueError('Fur texture has no usable pixels; Apply Active MDF first')
    w,h=image.size
    if w*h == 0:raise ValueError('Empty fur texture: '+image.name)
    if len(image.pixels) != w*h*4:raise ValueError('Fur texture pixels could not be read: '+image.name)
    key=(image.as_pointer(),w,h)
    #Clear this cache on explicit Apply/Refresh and image changes, not on each shell.
    if key not in _image_pixels:
        array=np.empty(w*h*4,dtype=np.float32)
        image.pixels.foreach_get(array)
        _image_pixels[key]=array.reshape(h,w,4)
    return _image_pixels[key]


def data_image(image):
    if image.colorspace_settings.name != 'Non-Color':
        #Never change an image also used by a color texture in another material.
        image=image.copy();image.name+=' SFUR data'
        image.colorspace_settings.name='Non-Color'
    image.alpha_mode='CHANNEL_PACKED'
    return image


def load_groom(entry, material, context):
    from ..mdf import blender_re_mesh_mdf as mdf
    logical=entry.re_sfur_data.groomingTexturePath.strip().replace('\\','/')
    if not logical:raise ValueError('Set Grooming Texture Path on the SFur entry')
    #Explicit ordinary image paths are useful for custom assets and avoid TEX conversion.
    full=bpy.path.abspath(logical)
    if os.path.isfile(full) and Path(full).suffix.lower() in ('.png','.dds','.tga','.exr','.tif','.tiff'):
        return data_image(bpy.data.images.load(full,check_existing=True))
    cachekey='MHWILDS:'+logical.lower()
    old=next((im for im in bpy.data.images if im.get('re_sfur_groom_path') == cachekey and im.has_data),None)
    if old:return old
    prefs=context.preferences.addons[mdf.ADDON_NAME].preferences
    recipe=json.loads(material.get('re_mdf_live_recipe_v1','{}'))
    roots=[recipe.get('chunk','')]+mdf.getChunkPathList('MHWILDS')
    mod=bpy.path.abspath(context.scene.re_mdf_toolpanel.modDirectory)
    if mod:roots=[os.path.join(mod,'natives','STM'),mod]+roots
    relative=logical.replace('@','').split('.tex',1)[0]
    if os.path.isabs(relative) or '..' in relative.split('/'):
        raise ValueError('Grooming TEX must be a logical path inside a resource root')
    output=os.path.join(bpy.path.abspath(prefs.textureCachePath),*relative.split('/'))+'.png'
    path=mdf.getTexPath(relative.replace('/',os.sep),roots,45,'MHWILDS')
    images=None
    if path:
        conv=mdf.Texconv()
        #Native DDS loading avoids a redundant WIC PNG conversion for these data maps.
        try:images=mdf.loadTex(path,output,conv,False,bpy.app.version >= (4,2,0))
        finally:mdf.unload_texconv()
    if not images or not mdf.textureImagesUsable(images):
        images=mdf.getSystemNullTextureImages(logical,'FurFlowMap',output,'MHWILDS')
    if not images or not mdf.textureImagesUsable(images):raise FileNotFoundError('Grooming texture not found: '+logical)
    image=data_image(images[0]);image['re_sfur_groom_path']=cachekey
    return image


def _uv(mesh, index):
    name='UVMap'+str(index)
    layer=mesh.uv_layers.get(name)
    if layer is None and index < len(mesh.uv_layers):layer=mesh.uv_layers[index]
    if layer is None:raise ValueError('Missing '+('secondary' if index else 'primary')+' UV map')
    array=np.empty(len(mesh.loops)*2,dtype=np.float32)
    layer.data.foreach_get('uv',array)
    return layer,array.reshape(-1,2)


def build_mesh(source, entry, context):
    """Read an evaluated snapshot, keep UV seams as distinct corners, return an owned mesh."""
    settings=entry.re_sfur_data
    count=int(settings.shellCount)
    if count < 0 or count > 256:raise ValueError('Preview supports Shell Count 0..256')
    depsgraph=context.evaluated_depsgraph_get()
    evaluated=source.evaluated_get(depsgraph)
    mesh=evaluated.to_mesh(preserve_all_data_layers=True,depsgraph=depsgraph)
    new=None
    try:
        slot_ids=[i for i,slot in enumerate(source.material_slots) if matching_material(slot.material,settings.materialName)]
        faces=[p for p in mesh.polygons if p.material_index in slot_ids]
        if not faces:return None
        corner_count=sum(p.loop_total for p in faces)
        if corner_count*count > MAX_CORNERS:
            raise ValueError(f'SFUR preview would create {corner_count*count:,} corners (limit {MAX_CORNERS:,}); lower Shell Count')
        materials={p.material_index:source.material_slots[p.material_index].material for p in faces}
        for mat in materials.values():
            if mat.node_tree is None or mat.node_tree.nodes.get('MHWilds SFUR Surface') is None:
                if mat.get(FUR_NOISE_MISSING):
                    raise FileNotFoundError(fur_noise_message(mat))
                raise ValueError('Apply Active MDF to build the Wilds Fur material first: '+mat.name)
        primary,uv0=_uv(mesh,0)
        _,guv=_uv(mesh,int(settings.groomingTexCoordType))
        mesh.calc_tangents(uvmap=primary.name)
        loop_ids=np.array([li for p in faces for li in p.loop_indices],dtype=np.int32)
        vertex_ids=np.array([mesh.loops[li].vertex_index for li in loop_ids],dtype=np.int32)
        pos=np.array([mesh.vertices[i].co[:] for i in vertex_ids],dtype=np.float64)
        norm=np.array([mesh.corner_normals[i].vector[:] for i in loop_ids],dtype=np.float64)
        tangent=np.array([mesh.loops[i].tangent[:] for i in loop_ids],dtype=np.float64)
        sign=np.array([mesh.loops[i].bitangent_sign for i in loop_ids])[:,None]
        #Imported V is flipped: use the D3D basis for geometric Grooming/FurFlow.
        bitangent=-normalize(np.cross(norm,tangent))*sign
        positions=[np.empty_like(pos) for _ in range(count)]
        normals=[np.empty_like(norm) for _ in range(count)]
        tangents=[np.empty_like(tangent) for _ in range(count)]
        bitangents=[np.empty_like(bitangent) for _ in range(count)]
        hvalues=[.9*(k+1)/count for k in range(count)]
        cursor=0
        for slot,material in materials.items():
            mask=np.array([p.material_index == slot for p in faces for _ in p.loop_indices])
            groom_image=load_groom(entry,material,context)
            groom=bilinear_repeat(pixels(groom_image),guv[loop_ids[mask]])
            flow_node=material.node_tree.nodes.get('FurFlowMap')
            if flow_node is None or getattr(flow_node,'image',None) is None:
                raise ValueError('FurFlowMap is not loaded: '+material.name)
            flow=bilinear_repeat(pixels(flow_node.image),uv0[loop_ids[mask]])
            ps,ns,ts,bs,hs=generate_shells(pos[mask],norm[mask],tangent[mask],bitangent[mask],groom,flow,count,
                settings.shellHeight,settings.bendRootRate,settings.bendRate,settings.normalTransformRate,
                scalar(material,'Fur_Push'),scalar(material,'Fur_Stand'))
            for k in range(count):
                positions[k][mask]=ps[k];normals[k][mask]=ns[k]
                tangents[k][mask]=ts[k];bitangents[k][mask]=bs[k]
        vertex_data=np.concatenate(positions) if count else np.empty((0,3))
        if not np.isfinite(vertex_data).all():raise ValueError('Nonfinite fur geometry; check textures and parameters')
        face_indices=[];material_ids=[]
        for k in range(count):
            cursor=k*corner_count
            for face in faces:
                face_indices.append(tuple(range(cursor,cursor+face.loop_total)))
                material_ids.append(face.material_index);cursor+=face.loop_total
        new=bpy.data.meshes.new('RE SFUR Preview Geometry')
        new.from_pydata(vertex_data.tolist(),[],face_indices)
        for slot in source.material_slots:
            material=slot.material
            new.materials.append(preview_material(material,entry) if material in materials.values() else material)
        if material_ids:new.polygons.foreach_set('material_index',material_ids)
        if len(new.polygons):new.polygons.foreach_set('use_smooth',[True]*len(new.polygons))
        for layer in mesh.uv_layers:
            uv=np.empty(len(mesh.loops)*2,dtype=np.float32);layer.data.foreach_get('uv',uv)
            target=new.uv_layers.new(name=layer.name)
            target.data.foreach_set('uv',np.tile(uv.reshape(-1,2)[loop_ids],(count,1)).ravel())
        for attr in mesh.color_attributes:
            if attr.domain not in ('POINT','CORNER'):continue
            ids=vertex_ids if attr.domain == 'POINT' else loop_ids
            color=np.empty(len(attr.data)*4,dtype=np.float32);attr.data.foreach_get('color',color)
            target=new.color_attributes.new(name=attr.name,type=attr.data_type,domain='CORNER')
            target.data.foreach_set('color',np.tile(color.reshape(-1,4)[ids],(count,1)).ravel())
        h=new.attributes.new('re_sfur_height','FLOAT','POINT')
        h.data.foreach_set('value',np.repeat(hvalues,corner_count))
        flag=new.attributes.new('re_sfur_shell','FLOAT','POINT');flag.data.foreach_set('value',np.ones(len(new.vertices)))
        for name,values in [('re_sfur_normal',normals),('re_sfur_tangent',tangents),('re_sfur_bitangent',bitangents)]:
            attr=new.attributes.new(name,'FLOAT_VECTOR','POINT')
            if count:attr.data.foreach_set('vector',np.concatenate(values).ravel())
        if count:new.normals_split_custom_set(np.concatenate(normals).tolist())
        new.update()
        return new
    except Exception:
        if new and new.users == 0:bpy.data.meshes.remove(new)
        cleanup_materials()
        raise
    finally:evaluated.to_mesh_clear()


def _collection(scene):
    #A separate direct scene child plus MeshExportExclude protects both export traversals.
    col=next((c for c in scene.collection.children if c.get('~TYPE') == TYPE),None)
    if col is None:
        col=bpy.data.collections.new('RE SFUR Preview');col['~TYPE']=TYPE;scene.collection.children.link(col)
    return col


def _discard(obj):
    mesh=obj.data if obj.type == 'MESH' else None
    bpy.data.objects.remove(obj,do_unlink=True)
    if mesh and mesh.users == 0:bpy.data.meshes.remove(mesh)
    cleanup_materials()
    restore_cycles()


def sync_visibility(obj, source):
    if obj.hide_render != source.hide_render:obj.hide_render=source.hide_render
    hidden=not source.visible_get()
    if obj.hide_get() != hidden:obj.hide_set(hidden)


def rebuild_preview(obj, context):
    source,entry=obj.get('re_sfur_source'),obj.get('re_sfur_entry')
    if source is None or entry is None:
        _discard(obj);return False
    new=build_mesh(source,entry,context)
    if new is None:
        _discard(obj);return False
    old=obj.data;obj.data=new
    if old.users == 0:bpy.data.meshes.remove(old)
    cleanup_materials()
    obj['MeshExportExclude']=True
    sync_visibility(obj,source)
    configure_cycles(context.scene,int(entry.re_sfur_data.shellCount))
    if obj.get('re_sfur_error'):del obj['re_sfur_error']
    return True


def apply_preview(context):
    global _busy
    panel=context.scene.re_mdf_toolpanel
    root,fur=panel.meshCollection,panel.sFurCollection
    if root is None or fur is None:raise ValueError('Choose Mesh Collection and Active SFur Collection')
    if panel.activeGame != 'MHWILDS':raise ValueError('This SFUR preview supports Monster Hunter Wilds')
    entries=[o for o in fur.all_objects if o.get('~TYPE') == 'RE_SFUR_ENTRY']
    names=[o.re_sfur_data.materialName for o in entries]
    if len(names) != len(set(names)):raise ValueError('Multiple SFur entries target the same material; resolve the duplicate names')
    prepared=[]
    _image_pixels.clear();_busy=True
    try:
        #Prepare all candidates first. A missing texture leaves the previous preview intact.
        for entry in entries:
            for source in root.all_objects:
                if source.type != 'MESH' or source.get('MeshExportExclude') or source.get('~TYPE') == TYPE:continue
                if not any(matching_material(s.material,entry.re_sfur_data.materialName) for s in source.material_slots):continue
                new=build_mesh(source,entry,context)
                if new is not None:
                    if sum(len(m.vertices) for _,_,m in prepared)+len(new.vertices) > MAX_CORNERS*2:
                        bpy.data.meshes.remove(new)
                        raise ValueError('Combined SFUR preview exceeds 4,000,000 corners; reduce Shell Count or preview a smaller collection')
                    prepared.append((source,entry,new))
        if not prepared:raise ValueError('No matching fur faces; check material names and mesh collection')
        col=_collection(context.scene)
        for old in previews():
            if old.get('re_sfur_mesh_collection') == root:_discard(old)
        for source,entry,new in prepared:
            obj=bpy.data.objects.new('SFUR Preview | '+source.name,new)
            col.objects.link(obj);obj['~TYPE']=TYPE;obj['MeshExportExclude']=True
            obj['re_sfur_source']=source;obj['re_sfur_entry']=entry;obj['re_sfur_mesh_collection']=root
            obj.hide_select=True;sync_visibility(obj,source)
            constraint=obj.constraints.new('COPY_TRANSFORMS');constraint.target=source
            obj['re_sfur_note']='Static Wilds Instancing preview; no shellThinType/LOD or physics simulation'
        configure_cycles(context.scene,max(int(entry.re_sfur_data.shellCount) for _,entry,_ in prepared))
        return len(prepared)
    except Exception:
        for _,_,mesh in prepared:
            if mesh.users == 0:bpy.data.meshes.remove(mesh)
        cleanup_materials()
        raise
    finally:_busy=False


def remove_preview(context):
    root=context.scene.re_mdf_toolpanel.meshCollection
    for obj in previews():
        if obj.get('re_sfur_mesh_collection') == root:_discard(obj)
    _image_pixels.clear()


def request_update(owner=None):
    if _busy:return
    for obj in previews():
        if owner is None or owner == obj.get('re_sfur_entry') or owner == obj.get('re_sfur_source') or isinstance(owner,bpy.types.Material) and any(m == owner or m and m.get('re_sfur_material_source') == owner for m in obj.data.materials):
            _pending[obj.as_pointer()]=(time.monotonic()+.15,obj)
    if _pending and not bpy.app.timers.is_registered(flush_updates):bpy.app.timers.register(flush_updates,first_interval=.15)


def flush_updates(force=False):
    global _busy
    if _busy:return .15
    _busy=True
    try:
        for key,(deadline,obj) in list(_pending.items()):
            if not force and deadline > time.monotonic():continue
            _pending.pop(key,None)
            try:
                if bpy.data.objects.get(obj.name) != obj:continue
                rebuild_preview(obj,bpy.context)
            except ReferenceError:pass
            except Exception as error:
                try:obj['re_sfur_error']=str(error)
                except ReferenceError:pass
                print('RE SFUR preview: '+str(error))
    finally:_busy=False
    return .15 if _pending else None


@persistent
def on_depsgraph(scene, depsgraph):
    if _busy:return
    active=previews()
    if not active:return
    for update in depsgraph.updates:
        item=update.id.original
        if isinstance(item,bpy.types.Image):
            _image_pixels.clear();request_update()
        for obj in active:
            source=obj.get('re_sfur_source')
            if source is None or obj.get('re_sfur_entry') is None:request_update()
            if source:sync_visibility(obj,source)
            if source and update.is_updated_geometry and (item == source or item == source.data):request_update(source)


@persistent
def clear_updates(*args):
    _pending.clear();_image_pixels.clear()
    if bpy.app.timers.is_registered(flush_updates):bpy.app.timers.unregister(flush_updates)


@persistent
def restore_updates(*args):
    request_update()


def register_preview():
    for handlers,fn in ((bpy.app.handlers.depsgraph_update_post,on_depsgraph),
                        (bpy.app.handlers.load_pre,clear_updates),(bpy.app.handlers.load_post,restore_updates),
                        (bpy.app.handlers.undo_pre,clear_updates),(bpy.app.handlers.redo_pre,clear_updates),
                        (bpy.app.handlers.undo_post,restore_updates),(bpy.app.handlers.redo_post,restore_updates)):
        if fn not in handlers:handlers.append(fn)


def unregister_preview():
    clear_updates()
    for handlers,fn in ((bpy.app.handlers.depsgraph_update_post,on_depsgraph),
                        (bpy.app.handlers.load_pre,clear_updates),(bpy.app.handlers.load_post,restore_updates),
                        (bpy.app.handlers.undo_pre,clear_updates),(bpy.app.handlers.redo_pre,clear_updates),
                        (bpy.app.handlers.undo_post,restore_updates),(bpy.app.handlers.redo_post,restore_updates)):
        if fn in handlers:handlers.remove(fn)


class WM_OT_RemoveSFurPreview(bpy.types.Operator):
    bl_idname='re_sfur.remove_preview'
    bl_label='Remove SFur Preview'
    bl_options={'UNDO'}
    def execute(self,context):
        remove_preview(context);return {'FINISHED'}


def draw_controls(layout,context,choose_collection=False):
    panel=context.scene.re_mdf_toolpanel
    box=layout.box()
    box.label(text='Static Shell Fur Preview')
    if choose_collection:
        box.prop_search(panel,'sFurCollection',bpy.data,'collections',text='SFur Collection')
    row=box.row(align=True)
    row.enabled=panel.sFurCollection is not None and panel.meshCollection is not None and panel.activeGame == 'MHWILDS'
    row.operator('re_sfur.apply_sfur',text='Build / Refresh',icon='CURVES_DATA')
    row.operator('re_sfur.remove_preview',text='Remove',icon='X')
    if panel.sFurCollection is not None:
        names={o.re_sfur_data.materialName for o in panel.sFurCollection.all_objects if o.get('~TYPE') == 'RE_SFUR_ENTRY'}
        missing=[m for m in bpy.data.materials if m.get(FUR_NOISE_MISSING) and m.name.split('.',1)[0] in names]
        if missing:
            box.label(text='FurNoiseMap not found; fur strands cannot be previewed.',icon='ERROR')
            box.label(text=str(missing[0][FUR_NOISE_MISSING])[:110])
            box.label(text='Add its chunk path, then Apply Active MDF.')
    errors=[o.get('re_sfur_error') for o in previews() if o.get('re_sfur_mesh_collection') == panel.meshCollection and o.get('re_sfur_error')]
    if errors:
        box.label(text='Preview update failed; use Build / Refresh.',icon='ERROR')
        box.label(text=str(errors[0])[:110])
