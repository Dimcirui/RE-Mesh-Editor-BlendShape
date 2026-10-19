"""MHWILDS atlas MultiBlend: explicit GPBF rectangles and the common DXIL blend loop."""
import json
import math
import os
import struct
import bpy

def readMultiBlendGPBF(path):
    with open(path,'rb') as file:
        data=file.read(1024*1024+1)
    if len(data)>1024*1024:
        raise ValueError('MultiBlend GPBF exceeds the supported size')
    if len(data)==9 and not any(data):
        return [] #The stock systems/rendering/Empty.gpbf placeholder.
    if len(data)<5 or data[0]!=0 or struct.unpack_from('<I',data,1)[0]!=3:
        raise ValueError('Unsupported GPBF encoding/version; expected raw kind 0, version 3')
    if (len(data)-5)%32:
        raise ValueError('Incomplete MultiBlend transform/bounds pair')
    values=struct.unpack('<'+'f'*((len(data)-5)//4),data[5:])
    if not all(math.isfinite(value) for value in values):
        raise ValueError('Nonfinite MultiBlend atlas coordinates')
    return [(values[i:i+4],values[i+4:i+8]) for i in range(0,len(values),8)]

def findMultiBlendGPBF(source,chunkPaths):
    logical=next((path.name for name,path in zip(source.gpbfBufferNameList,source.gpbfBufferPathList) if name.name=='MultiBlend_BAB'),None)
    if not logical:
        raise ValueError('MDF has no MultiBlend_BAB binding')
    relative=logical.replace('\\','/').replace('@','')
    relative=relative.split('.gpbf',1)[0]+'.gpbf'
    if os.path.isabs(relative) or os.path.splitdrive(relative)[0] or any(part=='..' for part in relative.split('/')):
        raise ValueError('MultiBlend_BAB must use a logical path inside a resource root')
    for root in chunkPaths:
        for prefix in ('streaming',''):
            base=os.path.join(root,prefix,*relative.split('/'))
            #Version 3 is the measured raw layout; do not silently choose another version.
            path=base+'.3'
            if os.path.isfile(path):
                return path,readMultiBlendGPBF(path)
    raise FileNotFoundError('Could not find '+logical)

def _group(nodeTree,name,build):
    group=bpy.data.node_groups.get(name)
    if group is None:
        group=bpy.data.node_groups.new(name,'ShaderNodeTree')
        build(group)
    node=nodeTree.nodes.new('ShaderNodeGroup');node.node_tree=group
    return node

def multiBlendUVNode(nodeTree):
    from .blender_nodes_re_mdf import ShaderGroupBuilder,newGroupSockets
    def build(group):
        newGroupSockets(group,[('UV','NodeSocketVector')]+[(name,'NodeSocketFloat') for name in ('ScaleU','ScaleV','OffsetU','OffsetV','MinU','MaxU','MinV','MaxV')],'INPUT')
        newGroupSockets(group,[('Vector','NodeSocketVector'),('Inside','NodeSocketFloat')],'OUTPUT')
        b=ShaderGroupBuilder(group);i=b.nodes.new('NodeGroupInput').outputs;o=b.nodes.new('NodeGroupOutput')
        uv=b.separateXYZ(i['UV']);u=uv['X'];v=b.math('SUBTRACT',1,uv['Y'])
        fu=b.math('FRACT',u);fv=b.math('FRACT',v)
        tile=b.math('SUBTRACT',1,b.math('ABSOLUTE',b.math('SUBTRACT',b.math('FLOOR',i['MinU']),b.math('FLOOR',u)),clamp=True))
        inside=tile
        for outside in (b.math('LESS_THAN',fu,b.math('FRACT',i['MinU'])),b.math('GREATER_THAN',fu,i['MaxU']),b.math('LESS_THAN',fv,b.math('FRACT',i['MinV'])),b.math('GREATER_THAN',fv,i['MaxV'])):
            inside=b.math('MULTIPLY',inside,b.math('SUBTRACT',1,outside))
        nonempty=0
        for name in ('MinU','MaxU','MinV','MaxV'):
            nonempty=b.math('MAXIMUM',nonempty,b.math('ABSOLUTE',i[name]))
        inside=b.math('MULTIPLY',inside,b.greater0(nonempty))
        x=b.math('MULTIPLY_ADD',fu,i['ScaleU'],i['OffsetU'])
        y=b.math('SUBTRACT',1,b.math('MULTIPLY_ADD',fv,i['ScaleV'],i['OffsetV']))
        b.links.new(b.combineXYZ(x,y,0),o.inputs['Vector']);b.links.new(inside,o.inputs['Inside'])
    return _group(nodeTree,'MHWildsMultiBlendUV_v1',build)

def multiBlendLayerNode(nodeTree):
    from .blender_nodes_re_mdf import ShaderGroupBuilder,newGroupSockets
    def build(group):
        newGroupSockets(group,[(n,'NodeSocketColor') for n in ('Base Color','Atlas Color','Normal Map')]+[('Base Normal','NodeSocketVector')]+[(n,'NodeSocketFloat') for n in ('Base Roughness','Base Alpha','Atlas Alpha','Normal Alpha','Weight','Inside','Use NRRO','Overlay','sRGB Overlay','Contrast','Alpha Threshold','Emit Mask')],'INPUT')
        newGroupSockets(group,[('Color','NodeSocketColor'),('Normal','NodeSocketVector')]+[(n,'NodeSocketFloat') for n in ('Roughness','Alpha','Emission Visibility','Weight')],'OUTPUT')
        b=ShaderGroupBuilder(group);i=b.nodes.new('NodeGroupInput').outputs;o=b.nodes.new('NodeGroupOutput')
        c=b.separate(i['Base Color']);a=b.separate(i['Atlas Color']);n=b.separateXYZ(i['Base Normal']);t=b.separate(i['Normal Map'])
        raw=b.math('MULTIPLY',i['Weight'],i['Inside'])
        #DXIL: saturate(alpha/contrast), then smoothstep polynomial, multiplied by |signed weight|.
        #For contrast==0 use the positive-alpha limiting result; 0/0 is not defined by the source.
        ratio=b.select(b.math('COMPARE',i['Contrast'],0,0),b.greater0(i['Atlas Alpha']),b.math('DIVIDE',i['Atlas Alpha'],i['Contrast']))
        q=b.math('MULTIPLY',ratio,1,clamp=True)
        w=b.math('MULTIPLY',b.math('ABSOLUTE',raw),b.math('MULTIPLY',b.math('MULTIPLY',q,q),b.math('MULTIPLY_ADD',q,-2,3)))
        useNRRO=b.math('GREATER_THAN',b.math('ABSOLUTE',i['Use NRRO']),0)
        ga=[b.math('MULTIPLY_ADD',component,2,-1) for component in (t['Green'],i['Normal Alpha'])]
        squared=[b.math('MULTIPLY',value,b.math('ABSOLUTE',value)) for value in ga]
        nx=b.math('MULTIPLY',b.math('ADD',*squared),.5);ny=b.math('MULTIPLY',b.math('SUBTRACT',*squared),.5)
        nz=b.math('SUBTRACT',b.math('SUBTRACT',1,b.math('ABSOLUTE',nx)),b.math('ABSOLUTE',ny))
        nx,ny,nz=b.normalize3(nx,ny,nz)
        decoded=[b.select(useNRRO,x,b.math('MULTIPLY_ADD',t[channel],2,-1)) for x,channel in zip((nx,ny,nz),('Red','Green','Blue'))]
        overlay=b.math('MAXIMUM',b.math('MULTIPLY',b.greater0(i['Overlay']),b.greater0(raw)),b.math('MULTIPLY',b.math('COMPARE',i['Overlay'],0,0),b.math('LESS_THAN',raw,0)))
        gamma=b.greater0(i['sRGB Overlay'])
        result=[]
        for channel in ('Red','Green','Blue'):
            base=b.select(gamma,b.math('POWER',c[channel],0.44999998807907104),c[channel])
            atlas=b.select(gamma,b.math('POWER',a[channel],0.44999998807907104),a[channel])
            multiplied=b.lerp(base,b.math('MULTIPLY',b.math('MULTIPLY',base,atlas),2),w)
            multiplied=b.select(gamma,b.math('POWER',multiplied,2.200000047683716),multiplied)
            result.append(b.select(overlay,multiplied,b.lerp(c[channel],a[channel],w)))
        added=b.normalize3(b.math('MULTIPLY_ADD',w,decoded[0],n['X']),b.math('MULTIPLY_ADD',w,decoded[1],n['Y']),n['Z'])
        normal=[b.select(overlay,component,b.lerp(n[channel],decoded[index],w)) for index,(component,channel) in enumerate(zip(added,('X','Y','Z')))]
        replaced=b.lerp(i['Base Roughness'],t['Red'],w)
        multiplied=b.lerp(i['Base Roughness'],b.math('MULTIPLY',b.math('MULTIPLY',i['Base Roughness'],t['Red']),2),w)
        rough=b.select(useNRRO,b.select(overlay,multiplied,replaced),i['Base Roughness'])
        alpha=b.math('MULTIPLY',i['Base Alpha'],b.math('SUBTRACT',1,b.math('MULTIPLY',raw,b.math('GREATER_THAN',i['Atlas Alpha'],i['Alpha Threshold']))))
        emission=b.select(b.greater0(b.math('ABSOLUTE',i['Emit Mask'])),b.math('SUBTRACT',1,w),1)
        #The source skips the entire iteration outside the rectangle, including normalization/gamma.
        active=b.math('MULTIPLY',b.greater0(b.math('ABSOLUTE',i['Weight'])),i['Inside'])
        b.links.new(b.combineColor(*[b.select(active,x,c[ch]) for x,ch in zip(result,('Red','Green','Blue'))]),o.inputs['Color'])
        b.links.new(b.combineXYZ(*[b.select(active,x,n[ch]) for x,ch in zip(normal,('X','Y','Z'))]),o.inputs['Normal'])
        for name,value,default in [('Roughness',rough,i['Base Roughness']),('Alpha',alpha,i['Base Alpha']),('Emission Visibility',emission,1),('Weight',w,0)]:
            b.links.new(b.select(active,value,default),o.inputs[name])
    return _group(nodeTree,'MHWildsMultiBlendLayer_v1',build)

def addMHWildsMultiBlendNodes(nodeTree,matInfo):
    from .blender_nodes_re_mdf import ShaderGroupBuilder,hasLoadedImage,linkMHWildsProp,mhWildsMultiBlendIndices
    if matInfo['gameName']!='MHWILDS':return
    material=matInfo['blenderMaterial']
    if 're_mdf_multiblend_status' in material:del material['re_mdf_multiblend_status']
    indices=mhWildsMultiBlendIndices(matInfo['mPropDict'])
    if not indices:return
    if not hasLoadedImage(matInfo,'MultiBlend_ALBDMap') or not hasLoadedImage(matInfo,'MultiBlend_NRMMap') or matInfo['albedoNodeLayerGroup'].currentOutSocket is None:return
    try:
        path,entries=findMultiBlendGPBF(matInfo['mdfMaterial'],matInfo['chunkPathList'])
    except (OSError,ValueError,struct.error) as error:
        material['re_mdf_multiblend_status']=str(error)
        print('RE MultiBlend preview: '+str(error));return
    b=ShaderGroupBuilder(nodeTree)
    baseColor=matInfo['albedoNodeLayerGroup'].currentOutSocket
    baseRough=matInfo['roughnessNodeLayerGroup'].currentOutSocket or .5
    baseAlpha=matInfo['alphaSocket'] if matInfo['alphaSocket'] is not None else 1
    baseNormal=(0,0,1)
    encoded=matInfo['normalNodeLayerGroup'].currentOutSocket
    if encoded is not None:
        split=b.separate(encoded);baseNormal=b.combineXYZ(*[b.math('MULTIPLY_ADD',split[c],2,-1) for c in ('Red','Green','Blue')])
    visibility=1;built=[]
    for index in indices:
        if index>=len(entries):continue #D3D zero-filled out-of-range reads cannot yield a nonempty rectangle.
        transform,bounds=entries[index]
        if not any(bounds):continue
        uv=multiBlendUVNode(nodeTree);uv.name=f'MultiBlend_UV_{index:02}'
        nodeTree.links.new(nodeTree.nodes['UVMap1Node'].outputs['UV'],uv.inputs['UV'])
        for name,value in zip(('ScaleU','ScaleV','OffsetU','OffsetV','MinU','MaxU','MinV','MaxV'),(*transform,*bounds)):uv.inputs[name].default_value=value
        samples=[]
        for slot in ('MultiBlend_ALBDMap','MultiBlend_NRMMap'):
            source=matInfo['textureNodeDict'][slot]
            if source.bl_idname!='ShaderNodeTexImage':
                material['re_mdf_multiblend_status']='MultiBlend expects a 2D atlas, not a texture array';return
            sample=nodeTree.nodes.new('ShaderNodeTexImage');sample.name=f'MultiBlend_{index:02}_{slot}';sample.image=source.image;sample.extension=source.extension;sample.interpolation=source.interpolation
            nodeTree.links.new(uv.outputs['Vector'],sample.inputs['Vector']);samples.append(sample)
        layer=multiBlendLayerNode(nodeTree);layer.name=f'MultiBlend_Layer_{index:02}';layer.label=f'MultiBlend {index+1}'
        for name,value in [('Base Color',baseColor),('Base Normal',baseNormal),('Base Roughness',baseRough),('Base Alpha',baseAlpha),('Atlas Color',samples[0].outputs['Color']),('Atlas Alpha',samples[0].outputs['Alpha']),('Normal Map',samples[1].outputs['Color']),('Normal Alpha',samples[1].outputs['Alpha']),('Inside',uv.outputs['Inside'])]:b._set(layer.inputs[name],value)
        linkMHWildsProp(nodeTree,matInfo,'Blend_'+chr(65+index//4),layer.inputs['Weight'],0,output=index%4)
        for prop,socket,default in [('Use_MultiBlend_NRRO','Use NRRO',0),('use_overlay','Overlay',1),('sRGB_Overlay','sRGB Overlay',0),('Blend_Contrast','Contrast',1),('Blend_Alpha_Threshold','Alpha Threshold',1),('Use_EmitMask','Emit Mask',0)]:linkMHWildsProp(nodeTree,matInfo,prop,layer.inputs[socket],default)
        baseColor=layer.outputs['Color'];baseNormal=layer.outputs['Normal'];baseRough=layer.outputs['Roughness'];baseAlpha=layer.outputs['Alpha']
        visibility=b.math('MULTIPLY',visibility,layer.outputs['Emission Visibility']);built.append(index)
    if built:
        matInfo['albedoNodeLayerGroup'].currentOutSocket=baseColor
        matInfo['roughnessNodeLayerGroup'].currentOutSocket=baseRough
        normal=b.separateXYZ(baseNormal)
        matInfo['normalNodeLayerGroup'].currentOutSocket=b.combineColor(*[b.math('MULTIPLY_ADD',normal[c],.5,.5) for c in ('X','Y','Z')])
        matInfo['alphaSocket']=baseAlpha;matInfo['multiBlendEmissionVisibility']=visibility
    material['re_mdf_multiblend_status']=json.dumps({'buffer':path,'entries':len(entries),'active_layers':built,'unavailable_indices':[i for i in indices if i>=len(entries)]})

def addMHWildsMultiBlendEmissionMask(nodeTree,matInfo):
    visibility=matInfo.get('multiBlendEmissionVisibility')
    if visibility is None:return
    from .blender_nodes_re_mdf import ShaderGroupBuilder
    if matInfo['emissionColorNodeLayerGroup'].currentOutSocket is not None:
        matInfo['emissionColorNodeLayerGroup'].addMixLayer(visibility,mixType='MULTIPLY',mixFactor=1)
    b=ShaderGroupBuilder(nodeTree)
    for node in list(nodeTree.nodes):
        if node.bl_idname=='ShaderNodeEmission' and node.label=='SecEmit':
            strength=node.inputs['Strength'];previous=strength.links[0].from_socket if strength.is_linked else strength.default_value
            b.links.new(b.math('MULTIPLY',previous,visibility),strength)
