"""Wilds shell surface math. Geometry-owned attributes leave ordinary meshes unchanged."""
import bpy

FUR_PROPS = {'Fur_Push', 'Fur_Stand', 'Fur_Density', 'FurNormal_Blend',
             'FurNoise_Blend', 'FurAlpha_Contrast', 'FurAlpha_Fade', 'FurKink'}
HEIGHT_ATTRIBUTE = 're_sfur_height'
SHELL_ATTRIBUTE = 're_sfur_shell'


def surface_group(tree):
    from .blender_nodes_re_mdf import ShaderGroupBuilder, newGroupSockets
    name = 'MHWildsSFurSurface_v1'
    group = bpy.data.node_groups.get(name)
    if group is None:
        group = bpy.data.node_groups.new(name, 'ShaderNodeTree')
        newGroupSockets(group, [(n, 'NodeSocketColor') for n in ('Color', 'Normal Color', 'Noise', 'Flow')]
                        + [(n, 'NodeSocketFloat') for n in ('Alpha', 'Height', 'Shell', 'FurNoise_Blend', 'FurNormal_Blend', 'FurAlpha_Contrast', 'FurAlpha_Fade')], 'INPUT')
        newGroupSockets(group, [('Color', 'NodeSocketColor'), ('Normal Color', 'NodeSocketColor'), ('Alpha', 'NodeSocketFloat'), ('Mask', 'NodeSocketFloat')], 'OUTPUT')
        b = ShaderGroupBuilder(group)
        i = b.nodes.new('NodeGroupInput').outputs
        o = b.nodes.new('NodeGroupOutput')
        noise, flow = b.separate(i['Noise']), b.separate(i['Flow'])
        normal, color = b.separate(i['Normal Color']), b.separate(i['Color'])
        h = i['Height']
        cubic = b.math('MULTIPLY', b.math('MULTIPLY', h, h), h)
        shape = b.math('ADD', h, b.math('MULTIPLY', b.math('MULTIPLY', i['FurAlpha_Fade'], 4), b.math('SUBTRACT', cubic, h)), clamp=True)
        numerator = b.math('MULTIPLY_ADD', b.math('MULTIPLY', noise['Blue'], 2), b.math('SUBTRACT', 1, shape), -.5)
        mask = b.math('ADD', b.math('DIVIDE', numerator, b.math('MAXIMUM', b.math('SUBTRACT', 1, i['FurAlpha_Contrast']), 1e-4)), .5, clamp=True)
        mask = b.select(b.math('MULTIPLY', b.greater0(h), b.greater0(i['Shell'])), mask, 1.)
        b.links.new(mask, o.inputs['Mask'])
        b.links.new(b.math('MULTIPLY', i['Alpha'], mask), o.inputs['Alpha'])
        strength = b.math('MULTIPLY', b.math('MULTIPLY', flow['Blue'], i['FurNormal_Blend']), 10)
        xyz = [b.math('MULTIPLY_ADD', normal[c], 2, -1) for c in ('Red','Green','Blue')]
        xy = [b.math('ADD', xyz[k], b.math('MULTIPLY', strength, b.math('SUBTRACT', noise[c], 128/255))) for k,c in enumerate(('Red','Green'))]
        x,y,z = b.normalize3(*xy, xyz[2])
        outnormal = b.combineColor(*[b.math('MULTIPLY_ADD', v,.5,.5) for v in (x,y,z)])
        #A graph shared with the base mesh must not perturb unrelated surfaces.
        mixed = b.nodes.new('ShaderNodeMixRGB')
        b.links.new(i['Shell'],mixed.inputs[0]);b.links.new(i['Normal Color'],mixed.inputs[1]);b.links.new(outnormal,mixed.inputs[2])
        b.links.new(mixed.outputs[0],o.inputs['Normal Color'])
        w = b.math('MULTIPLY', b.math('MULTIPLY', i['FurNoise_Blend'], flow['Blue']), i['Shell'])
        scale = b.lerp(1., b.math('MULTIPLY', noise['Blue'], 2), w)
        b.links.new(b.combineColor(*[b.math('MULTIPLY', color[c], scale) for c in ('Red','Green','Blue')]),o.inputs['Color'])
    node = tree.nodes.new('ShaderNodeGroup');node.node_tree = group;node.name = 'MHWilds SFUR Surface'
    return node


def noise_uv_group(tree):
    from .blender_nodes_re_mdf import ShaderGroupBuilder, newGroupSockets
    name = 'MHWildsSFurNoiseUV_v1'
    group = bpy.data.node_groups.get(name)
    if group is None:
        group = bpy.data.node_groups.new(name,'ShaderNodeTree')
        newGroupSockets(group,[('UV','NodeSocketVector')]+[(n,'NodeSocketFloat') for n in ('Height','FurKink','Fur_Density')],'INPUT')
        newGroupSockets(group,[('Vector','NodeSocketVector')],'OUTPUT')
        b=ShaderGroupBuilder(group);i=b.nodes.new('NodeGroupInput').outputs;o=b.nodes.new('NodeGroupOutput')
        uv=b.separateXYZ(i['UV']);h=i['Height'];k=i['FurKink']
        angle=b.math('MULTIPLY',b.math('MULTIPLY',k,h),1.5707963267948966)
        sine,cosine=b.math('SINE',angle),b.math('COSINE',angle)
        amp=b.math('MULTIPLY',b.math('MULTIPLY',h,.01),b.math('MULTIPLY',k,1,clamp=True))
        du=b.math('MULTIPLY',amp,b.math('ADD',sine,cosine))
        dv=b.math('MULTIPLY',amp,b.math('SUBTRACT',cosine,sine))
        #Apply scale/kink in D3D V-down UV space, then return to Blender V-up.
        u=b.math('MULTIPLY',b.math('ADD',uv['X'],du),i['Fur_Density'])
        v=b.math('SUBTRACT',1,b.math('MULTIPLY',b.math('ADD',b.math('SUBTRACT',1,uv['Y']),dv),i['Fur_Density']))
        b.links.new(b.combineXYZ(u,v,0),o.inputs['Vector'])
    node=tree.nodes.new('ShaderNodeGroup');node.node_tree=group;node.name='MHWilds SFUR Noise UV'
    return node


def add_fur_surface(tree, info):
    from .blender_nodes_re_mdf import hasLoadedImage, linkMHWildsProp, getMHWildsBaseAOUVNode
    if info['gameName'] != 'MHWILDS' or not FUR_PROPS.issubset(info['mPropDict']):
        return
    if not hasLoadedImage(info,'FurNoiseMap'):
        return
    noise=info['textureNodeDict']['FurNoiseMap']
    flow=info['textureNodeDict'].get('FurFlowMap')
    for texture in (noise,flow):
        if texture is not None and getattr(texture,'image',None):
            texture.image.colorspace_settings.name='Non-Color'
            texture.image.alpha_mode='CHANNEL_PACKED'
            texture.extension='REPEAT';texture.interpolation='Linear'
    h=tree.nodes.new('ShaderNodeAttribute');h.attribute_name=HEIGHT_ATTRIBUTE
    flag=tree.nodes.new('ShaderNodeAttribute');flag.attribute_name=SHELL_ATTRIBUTE
    node=surface_group(tree);uv=noise_uv_group(tree)
    baseuv=getMHWildsBaseAOUVNode(tree,info).outputs['Base UV']
    tree.links.new(baseuv,uv.inputs['UV']);tree.links.new(h.outputs['Fac'],uv.inputs['Height'])
    tree.links.new(uv.outputs['Vector'],noise.inputs['Vector'])
    tree.links.new(noise.outputs['Color'],node.inputs['Noise'])
    if flow is not None:
        tree.links.new(baseuv,flow.inputs['Vector']);tree.links.new(flow.outputs['Color'],node.inputs['Flow'])
    tree.links.new(h.outputs['Fac'],node.inputs['Height']);tree.links.new(flag.outputs['Fac'],node.inputs['Shell'])
    for name in ('Fur_Density','FurKink'):
        linkMHWildsProp(tree,info,name,uv.inputs[name])
    for name in ('FurNoise_Blend','FurNormal_Blend','FurAlpha_Contrast','FurAlpha_Fade'):
        linkMHWildsProp(tree,info,name,node.inputs[name])
    for key,slot,default in [('albedoNodeLayerGroup','Color',(.5,.5,.5,1)),('normalNodeLayerGroup','Normal Color',(.5,.5,1,1))]:
        layer=info[key]
        node.inputs[slot].default_value=default
        if layer.currentOutSocket is not None:tree.links.new(layer.currentOutSocket,node.inputs[slot])
        layer.currentOutSocket=node.outputs[slot]
    if info.get('alphaSocket') is not None:tree.links.new(info['alphaSocket'],node.inputs['Alpha'])
    else:node.inputs['Alpha'].default_value=1.
    info['alphaSocket']=node.outputs['Alpha']
    #Keep geometry-only sliders editable and readable by the geometry refresh.
    for name in ('Fur_Push','Fur_Stand'):
        from .blender_nodes_re_mdf import addPropertyNode
        addPropertyNode(info['mPropDict'][name],info['currentPropPos'],tree)


def fur_world_normal(tree, info, fallback):
    """Use the transported RE TBN exactly once, after the existing NRRO decode."""
    if tree.nodes.get('MHWilds SFUR Surface') is None:return fallback
    from .blender_nodes_re_mdf import ShaderGroupBuilder
    b=ShaderGroupBuilder(tree)
    rgb=b.separate(info['normalNodeLayerGroup'].currentOutSocket)
    vectors=[]
    for name,channel,kind in [('re_sfur_tangent','Red','VECTOR'),('re_sfur_bitangent','Green','VECTOR'),('re_sfur_normal','Blue','NORMAL')]:
        attr=tree.nodes.new('ShaderNodeAttribute');attr.attribute_name=name
        transform=tree.nodes.new('ShaderNodeVectorTransform');transform.vector_type=kind;transform.convert_from='OBJECT';transform.convert_to='WORLD'
        tree.links.new(attr.outputs['Vector'],transform.inputs['Vector'])
        unit=tree.nodes.new('ShaderNodeVectorMath');unit.operation='NORMALIZE';tree.links.new(transform.outputs[0],unit.inputs[0])
        scaled=tree.nodes.new('ShaderNodeVectorMath');scaled.operation='SCALE'
        tree.links.new(unit.outputs[0],scaled.inputs[0]);tree.links.new(b.math('MULTIPLY_ADD',rgb[channel],2,-1),scaled.inputs['Scale'])
        vectors.append(scaled.outputs[0])
    total=vectors[0]
    for v in vectors[1:]:
        add=tree.nodes.new('ShaderNodeVectorMath');add.operation='ADD';tree.links.new(total,add.inputs[0]);tree.links.new(v,add.inputs[1]);total=add.outputs[0]
    normal=tree.nodes.new('ShaderNodeVectorMath');normal.operation='NORMALIZE';tree.links.new(total,normal.inputs[0])
    flag=tree.nodes.new('ShaderNodeAttribute');flag.attribute_name=SHELL_ATTRIBUTE
    mix=tree.nodes.new('ShaderNodeMixRGB');tree.links.new(flag.outputs['Fac'],mix.inputs[0]);tree.links.new(normal.outputs[0],mix.inputs[2])
    if fallback is not None:tree.links.new(fallback,mix.inputs[1])
    else:
        geometry=tree.nodes.new('ShaderNodeNewGeometry');tree.links.new(geometry.outputs['Normal'],mix.inputs[1])
    return mix.outputs[0]
