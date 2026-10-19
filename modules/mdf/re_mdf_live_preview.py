"""Live preview for MDF-owned materials. Rebuild only when construction gates change."""
import json
import time
import bpy
from bpy.app.handlers import persistent
from .file_re_mdf import MDFFile,Material,Property,TextureBinding,GPBFEntry

STRUCTURAL_PROPS = {
    'Film_Blend','FullFIlm','NormalBlendParam','UseDetail','ModulateColor',
    'FakeRefraction_Blend','UseVectorEmit','UseParallaxEmit','Use_MoveEmit',
    'AnimEmit_Min','UseWaveEmit','SecondaryEmitColor','SecEmit_Anim_Min',
    'SecEmit_Anim_UseWaveEmit','SSSProfile',
}
STRUCTURAL_PROPS.update({'Blend_num'} | {'Blend_'+channel for channel in 'ABCDEFGH'})
RECIPE_KEY = 're_mdf_live_recipe_v1'
DEBOUNCE_SECONDS = 0.12
_pending = {}
_rebuilding = False

def propertyValues(prop):
    if prop.data_type == 'VEC4':
        return list(prop.float_vector_value)
    if prop.data_type == 'COLOR':
        return list(prop.color_value)
    if prop.data_type == 'BOOL':
        return [float(prop.bool_value)]
    return [float(prop.float_value)]

def structureSignature(props):
    from .blender_nodes_re_mdf import mhWildsTextureNeeded,mhWildsMultiBlendIndices
    value = lambda name,default=0.0: float(props[name].propValue[0]) if name in props else default
    secondary = 'SecondaryEmitColor' in props and max(props['SecondaryEmitColor'].propValue[:3]) > 0.0
    move = value('Use_MoveEmit') > 0.0
    #Match import-time Python branches, not a hash of continuously changing sliders.
    return [value('FullFIlm') > 0.0 or value('Film_Blend') != 0.0,
            value('NormalBlendParam') != 0.0,value('UseDetail',1.0) > 0.0,
            value('ModulateColor',1.0) > 0.0,value('FakeRefraction_Blend') != 0.0,
            value('UseVectorEmit') > 0.0,value('UseParallaxEmit') > 0.0,move,
            not move and value('AnimEmit_Min',1.0) != 1.0,
            bool(secondary),bool(secondary) and value('SecEmit_Anim_Min',1.0) != 1.0,
            value('SSSProfile') == 1.0,
            bool(mhWildsTextureNeeded('FxMap',props)),mhWildsMultiBlendIndices(props)]

def rememberMaterialPreview(blenderMaterial,source,version,gameName,chunkPath,loadUnusedTextures,loadUnusedProps,useBackfaceCulling,arrangeNodes):
    if gameName != 'MHWILDS':
        if RECIPE_KEY in blenderMaterial:
            del blenderMaterial[RECIPE_KEY]
        return
    recipe = {'schema':1,'version':int(version),'game':gameName,'chunk':chunkPath,
              'unused_textures':bool(loadUnusedTextures),'unused_props':bool(loadUnusedProps),
              'culling':bool(useBackfaceCulling),'arrange':bool(arrangeNodes),
              'signature':structureSignature(source.getPropertyDict())}
    blenderMaterial[RECIPE_KEY] = json.dumps(recipe)

def updatePropertyNode(nodeTree,name,values):
    node = nodeTree.nodes.get(name)
    if node == None:
        return False
    if len(values) == 1:
        if 'Value' in node.outputs:
            node.outputs['Value'].default_value = values[0]
            return True
        return False
    if 'Color' in node.inputs and min(values[:4]) < 0.0:
        from .blender_nodes_re_mdf import getVec4ColorNodeGroup
        #Replace only this property node, retaining all Color/Alpha consumers.
        replacement = getVec4ColorNodeGroup(nodeTree)
        replacement.parent = node.parent
        replacement.location = node.location
        replacement.label = node.label
        replacement.width = node.width
        for output in node.outputs:
            if output.name in replacement.outputs:
                for link in list(output.links):
                    nodeTree.links.new(replacement.outputs[output.name],link.to_socket)
        if node.inputs['Color'].is_linked:
            separate = nodeTree.nodes.new('ShaderNodeSeparateXYZ')
            nodeTree.links.new(node.inputs['Color'].links[0].from_socket,separate.inputs['Vector'])
            for index in range(3):
                nodeTree.links.new(separate.outputs[index],replacement.inputs[index])
        if 'Alpha' in node.inputs and node.inputs['Alpha'].is_linked:
            nodeTree.links.new(node.inputs['Alpha'].links[0].from_socket,replacement.inputs[3])
        nodeTree.nodes.remove(node)
        replacement.name = name
        node = replacement
    if 'Color' in node.inputs:
        node.inputs['Color'].default_value = values
        if 'Alpha' in node.inputs:
            node.inputs['Alpha'].default_value = values[3]
    else:
        for index,value in enumerate(values):
            if index < len(node.inputs):
                node.inputs[index].default_value = value
    return True

def _snapshot(owner,recipe):
    data = owner.re_mdf_material
    source = Material()
    source.materialName = data.materialName
    source.mmtrPath = data.mmtrPath
    source.shaderType = int(data.shaderType)
    source.flags.asInt32 = data.flags.flagIntValue
    source.flagsB.asInt32 = data.flags.flagIntValueB
    source.bakeTextureArraySize = data.flags.bakeTextureArraySize
    source.shaderLODNum = data.flags.shaderLODNum
    #Do not invoke the exporter: it reindexes collections and applies export-only conversions.
    for item in data.propertyList_items:
        prop = Property()
        prop.propName = item.prop_name
        prop.propValue = propertyValues(item)
        prop.paramCount = len(prop.propValue)
        source.propertyList.append(prop)
    from .blender_re_mdf import fixTexPath
    for item in data.textureBindingList_items:
        texture = TextureBinding()
        texture.textureType = item.textureType
        texture.texturePath = fixTexPath(item.path)
        source.textureList.append(texture)
    for item in data.gpbfData_items:
        fields = item.gpbfDataString.split(',')
        if len(fields) >= 2:
            name,path = GPBFEntry(),GPBFEntry()
            name.name,path.name = fields[0].strip(),fields[1].strip()
            source.gpbfBufferNameList.append(name)
            source.gpbfBufferPathList.append(path)
    file = MDFFile()
    file.fileVersion = recipe['version']
    file.materialList = [source]
    return file,source

def _recipe(material):
    raw = material.get(RECIPE_KEY)
    if not raw:
        return None
    recipe = json.loads(raw)
    return recipe if recipe.get('schema') == 1 and recipe.get('game') == 'MHWILDS' else None

def requestLivePreviewUpdate(owner,propName):
    if _rebuilding or propName not in STRUCTURAL_PROPS or not isinstance(owner,bpy.types.Object):
        return False
    material = owner.re_mdf_material.linkedMaterial
    if material == None or material.node_tree == None:
        return False
    recipe = _recipe(material)
    if recipe == None:
        return False #Older graphs acquire their construction context on Apply Active MDF.
    if owner.re_mdf_material.gameName not in ('',recipe['game']):
        return False
    _,source = _snapshot(owner,recipe)
    key = material.as_pointer()
    if structureSignature(source.getPropertyDict()) == recipe['signature']:
        _pending.pop(key,None)
        return False
    _pending[key] = (time.monotonic()+DEBOUNCE_SECONDS,owner,material)
    if not bpy.app.timers.is_registered(_runPending):
        bpy.app.timers.register(_runPending,first_interval=DEBOUNCE_SECONDS)
    return True

def flushPendingLivePreviews(force=False):
    global _rebuilding
    now = time.monotonic()
    for key,(deadline,owner,material) in list(_pending.items()):
        if not force and deadline > now:
            continue
        _pending.pop(key,None)
        try:
            #Undo/deletion/relinking can invalidate queued RNA references.
            if bpy.data.objects.get(owner.name) != owner or bpy.data.materials.get(material.name) != material or owner.re_mdf_material.linkedMaterial != material:
                continue
            recipe = _recipe(material)
            if recipe == None:
                continue
            file,source = _snapshot(owner,recipe)
            if structureSignature(source.getPropertyDict()) == recipe['signature']:
                continue
            _rebuilding = True
            from .blender_re_mesh_mdf import importMDF
            #Cached images are reused. A slider never forces disk conversion on every step.
            success = importMDF(file,{source.materialName:material},recipe['unused_textures'],recipe['unused_props'],recipe['culling'],False,chunkPath=recipe['chunk'],gameName=recipe['game'],arrangeNodes=recipe['arrange'])
            from ..sfur.blender_sfur_preview import request_update
            request_update(material)
            if success is False:
                raise RuntimeError('Material node construction failed; see the Blender system console')
            if 're_mdf_live_error' in material:
                del material['re_mdf_live_error']
        except ReferenceError:
            pass
        except Exception as error:
            try:
                material['re_mdf_live_error'] = str(error)
            except ReferenceError:
                pass
            print(f'RE MDF live preview: {error}')
        finally:
            _rebuilding = False
    if not _pending:
        return None
    return max(0.01,min(deadline for deadline,_,_ in _pending.values())-time.monotonic())

def _runPending():
    return flushPendingLivePreviews()

@persistent
def clearPendingLivePreviews(*args):
    _pending.clear()
    if bpy.app.timers.is_registered(_runPending):
        bpy.app.timers.unregister(_runPending)

@persistent
def syncLivePreviewsAfterUndo(*args):
    from .re_mdf_propertyGroups import editablePropsSet
    for owner in bpy.data.objects:
        if owner.get('~TYPE') != 'RE_MDF_MATERIAL':
            continue
        material = owner.re_mdf_material.linkedMaterial
        if material == None or material.node_tree == None or _recipe(material) == None:
            continue
        for prop in owner.re_mdf_material.propertyList_items:
            if prop.prop_name in editablePropsSet:
                updatePropertyNode(material.node_tree,prop.prop_name,propertyValues(prop))
        #Any structural name requests a comparison of the complete current state.
        requestLivePreviewUpdate(owner,'UseDetail')

def registerLivePreview():
    for handlers,callback in ((bpy.app.handlers.load_pre,clearPendingLivePreviews),
                              (bpy.app.handlers.undo_pre,clearPendingLivePreviews),
                              (bpy.app.handlers.redo_pre,clearPendingLivePreviews),
                              (bpy.app.handlers.undo_post,syncLivePreviewsAfterUndo),
                              (bpy.app.handlers.redo_post,syncLivePreviewsAfterUndo)):
        if callback not in handlers:
            handlers.append(callback)

def unregisterLivePreview():
    clearPendingLivePreviews()
    for handlers,callback in ((bpy.app.handlers.load_pre,clearPendingLivePreviews),
                              (bpy.app.handlers.undo_pre,clearPendingLivePreviews),
                              (bpy.app.handlers.redo_pre,clearPendingLivePreviews),
                              (bpy.app.handlers.undo_post,syncLivePreviewsAfterUndo),
                              (bpy.app.handlers.redo_post,syncLivePreviewsAfterUndo)):
        if callback in handlers:
            handlers.remove(callback)
