"""Verified SkinEdit tint/mask math with an explicitly approximate Blender skin profile."""
import json
import bpy


def isMHWildsSkinEdit(matInfo):
    #Do not reinterpret other games' albedo alpha or infer skin from a material's display name.
    if matInfo.get('gameName') != 'MHWILDS':
        return False
    master = matInfo.get('mmtrName', '').replace('\\', '/').rsplit('/', 1)[-1].lower()
    return master == 'base_atos_skinedit_vfx.mmtr'


def _group(nodeTree, name, build):
    group = bpy.data.node_groups.get(name)
    if group is None:
        group = bpy.data.node_groups.new(name, 'ShaderNodeTree')
        build(group)
    node = nodeTree.nodes.new('ShaderNodeGroup')
    node.node_tree = group
    return node


def skinUVNode(nodeTree):
    from .blender_nodes_re_mdf import ShaderGroupBuilder, newGroupSockets
    def build(group):
        newGroupSockets(group, [('U','NodeSocketFloat'), ('V','NodeSocketFloat')], 'INPUT')
        newGroupSockets(group, [('Vector','NodeSocketVector')], 'OUTPUT')
        b = ShaderGroupBuilder(group)
        i = b.nodes.new('NodeGroupInput').outputs
        o = b.nodes.new('NodeGroupOutput')
        b.links.new(b.combineXYZ(i['U'], b.math('SUBTRACT', 1, i['V']), 0), o.inputs['Vector'])
    return _group(nodeTree, 'MHWildsSkinUV_v1', build)


def skinTintNode(nodeTree):
    from .blender_nodes_re_mdf import ShaderGroupBuilder, newGroupSockets
    def build(group):
        newGroupSockets(group, [('Base Color','NodeSocketColor'), ('Palette Color','NodeSocketColor'), ('Base Alpha','NodeSocketFloat')], 'INPUT')
        newGroupSockets(group, [('Color','NodeSocketColor'), ('Tint Mask','NodeSocketFloat')], 'OUTPUT')
        b = ShaderGroupBuilder(group)
        i = b.nodes.new('NodeGroupInput').outputs
        o = b.nodes.new('NodeGroupOutput')
        base, palette = b.separate(i['Base Color']), b.separate(i['Palette Color'])
        mask = b.math('MULTIPLY', i['Base Alpha'], 1.0233999490737915, clamp=True)
        color = [b.lerp(base[c], b.math('MULTIPLY', b.math('MULTIPLY', base[c], palette[c]), 2), mask) for c in ('Red','Green','Blue')]
        b.links.new(b.combineColor(*color), o.inputs['Color'])
        b.links.new(mask, o.inputs['Tint Mask'])
    return _group(nodeTree, 'MHWildsSkinTint_v1', build)


def addMHWildsSkinTintNodes(nodeTree, matInfo):
    from .blender_nodes_re_mdf import hasLoadedImage, addPropertyNode, ShaderGroupBuilder
    if not isMHWildsSkinEdit(matInfo):
        return
    if 'AddColorUV' not in matInfo['mPropDict'] or not all(hasLoadedImage(matInfo, slot) for slot in ('SkinMap','BaseDielectricMap')):
        return
    base = matInfo['albedoNodeLayerGroup'].currentOutSocket
    if base is None:
        return
    palette = matInfo['textureNodeDict']['SkinMap']
    uv = skinUVNode(nodeTree)
    uv.name = 'MHWilds Skin Palette UV'
    prop = addPropertyNode(matInfo['mPropDict']['AddColorUV'], matInfo['currentPropPos'], nodeTree)
    #Existing property heuristics can display AddColorUV as COLOR. It is still a raw
    #float4: use R/G as x/y, not the Color-to-luminance conversion and Alpha output.
    if 'Color' in prop.outputs:
        xy = ShaderGroupBuilder(nodeTree).separate(prop.outputs['Color'])
        u, v = xy['Red'], xy['Green']
    else:
        u, v = prop.outputs[0], prop.outputs[1]
    nodeTree.links.new(u, uv.inputs['U'])
    nodeTree.links.new(v, uv.inputs['V'])
    nodeTree.links.new(uv.outputs['Vector'], palette.inputs['Vector'])
    #The SkinEdit program uses BilinearClamp, including AddColorUV outside [0,1].
    if palette.bl_idname == 'ShaderNodeTexImage':
        palette.extension = 'EXTEND'
    tint = skinTintNode(nodeTree)
    tint.name = 'MHWilds Skin Tint'
    nodeTree.links.new(base, tint.inputs['Base Color'])
    nodeTree.links.new(palette.outputs['Color'], tint.inputs['Palette Color'])
    nodeTree.links.new(matInfo['textureNodeDict']['BaseDielectricMap'].outputs['Alpha'], tint.inputs['Base Alpha'])
    matInfo['albedoNodeLayerGroup'].currentOutSocket = tint.outputs['Color']


def skinSSSNode(nodeTree):
    from .blender_nodes_re_mdf import ShaderGroupBuilder, newGroupSockets
    def build(group):
        newGroupSockets(group, [('SSS Mask','NodeSocketFloat'), ('SSSParam','NodeSocketFloat'), ('Scatter Scale','NodeSocketFloat'), ('Radius RGB','NodeSocketVector')], 'INPUT')
        newGroupSockets(group, [('Weight','NodeSocketFloat'), ('Scale','NodeSocketFloat'), ('Radius','NodeSocketVector')], 'OUTPUT')
        b = ShaderGroupBuilder(group)
        i = b.nodes.new('NodeGroupInput').outputs
        o = b.nodes.new('NodeGroupOutput')
        #SkinEdit PS stores saturate(ATOS.a * SSSParam) in the GBuffer.
        b.links.new(b.math('MULTIPLY', i['SSS Mask'], i['SSSParam'], clamp=True), o.inputs['Weight'])
        b.links.new(b.math('MAXIMUM', i['Scatter Scale'], 0), o.inputs['Scale'])
        b.links.new(i['Radius RGB'], o.inputs['Radius'])
    node = _group(nodeTree, 'MHWildsSkinSSS_v1', build)
    #Artistic preview defaults in Blender units, not recovered RE Engine profile constants.
    node.inputs['Scatter Scale'].default_value = 0.0015
    node.inputs['Radius RGB'].default_value = (1.0, 0.35, 0.2)
    return node


def addMHWildsSkinSSSNodes(nodeTree, matInfo, bsdf):
    from .blender_nodes_re_mdf import hasLoadedImage, linkMHWildsProp, mhWildsPropValue
    if not isMHWildsSkinEdit(matInfo):
        return
    profile = mhWildsPropValue(matInfo['mPropDict'], 'SSSProfile')
    status = {'schema':1, 'profile':profile, 'enabled':False, 'model':'Blender skin approximation', 'scatter_scale':0.0015, 'radius_rgb':[1.0,0.35,0.2]}
    if profile != 1:
        status['reason'] = 'SSSProfile 0 disabled; profiles other than 1 have no skin approximation'
    elif not hasLoadedImage(matInfo, 'AlphaTranslucentOcclusionSSSMap'):
        status['reason'] = 'No loaded ATOS SSS mask'
    else:
        node = skinSSSNode(nodeTree)
        node.name = 'MHWilds Skin SSS'
        node.label = 'Skin SSS - Blender approximation'
        #Use the actual base ATOS sample (ChangeUV), never the separate AO-only UV sample.
        nodeTree.links.new(matInfo['textureNodeDict']['AlphaTranslucentOcclusionSSSMap'].outputs['Alpha'], node.inputs['SSS Mask'])
        linkMHWildsProp(nodeTree, matInfo, 'SSSParam', node.inputs['SSSParam'], 1)
        methods = {item.identifier for item in bsdf.bl_rna.properties['subsurface_method'].enum_items}
        bsdf.subsurface_method = 'RANDOM_WALK_SKIN' if 'RANDOM_WALK_SKIN' in methods else 'BURLEY'
        weight = bsdf.inputs.get('Subsurface Weight') or bsdf.inputs.get('Subsurface')
        if weight is not None:
            nodeTree.links.new(node.outputs['Weight'], weight)
        if 'Subsurface Radius' in bsdf.inputs:
            if 'Subsurface Scale' in bsdf.inputs:
                nodeTree.links.new(node.outputs['Radius'], bsdf.inputs['Subsurface Radius'])
                nodeTree.links.new(node.outputs['Scale'], bsdf.inputs['Subsurface Scale'])
            else:
                #Before Principled v2 the radius itself carried the distance scale.
                scale = nodeTree.nodes.new('ShaderNodeVectorMath')
                scale.operation = 'SCALE'
                nodeTree.links.new(node.outputs['Radius'], scale.inputs[0])
                nodeTree.links.new(node.outputs['Scale'], scale.inputs['Scale'])
                nodeTree.links.new(scale.outputs['Vector'], bsdf.inputs['Subsurface Radius'])
        if 'Subsurface Color' in bsdf.inputs and matInfo['albedoNodeLayerGroup'].currentOutSocket is not None:
            nodeTree.links.new(matInfo['albedoNodeLayerGroup'].currentOutSocket, bsdf.inputs['Subsurface Color'])
        if 'Subsurface IOR' in bsdf.inputs:
            bsdf.inputs['Subsurface IOR'].default_value = 1.4
        status['enabled'] = weight is not None
        status['method'] = bsdf.subsurface_method
    matInfo['blenderMaterial']['re_mdf_skin_preview'] = json.dumps(status)
