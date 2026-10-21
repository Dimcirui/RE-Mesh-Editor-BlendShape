import bpy
import os
from math import pi
from .blender_re_mdf import colorPropertySet
from .blender_re_mesh_mdf import albedoTypeSet

from mathutils import Vector
#Hair meshes use ambient occlusion with the second UV map
legacyUV2HairOcclusionList = set(["RE2","RE2RT","RE3","RE3RT","RE7RT","DMC5"])

def addLoc(node,delta):#Just to shorten what would otherwise be a long line
	return (node.location[0] + delta[0],node.location[1] + delta[1])

def getColorNodeGroup(nodeTree):#No RGBA node in shader editor so a custom group is needed
	if "ColorNodeGroup" in bpy.data.node_groups:
		nodeGroup = bpy.data.node_groups["ColorNodeGroup"]
	else:
		nodeGroup = bpy.data.node_groups.new(type="ShaderNodeTree", name="ColorNodeGroup")
	
		if bpy.app.version < (4,0,0):
			nodeGroup.inputs.new("NodeSocketColor","Color")
			nodeGroup.inputs.new("NodeSocketFloat","Alpha")
		else:
			nodeGroup.interface.new_socket(name="Color",description="",in_out ="INPUT", socket_type="NodeSocketColor")
			nodeGroup.interface.new_socket(name="Alpha",description="",in_out ="INPUT", socket_type="NodeSocketFloat")
		
		inNode = nodeGroup.nodes.new('NodeGroupInput')
		
		outNode = nodeGroup.nodes.new('NodeGroupOutput')
		if bpy.app.version < (4,0,0):
			nodeGroup.outputs.new('NodeSocketColor', 'Color')
			nodeGroup.outputs.new('NodeSocketFloat', 'Alpha')
		else:
			nodeGroup.interface.new_socket(name="Color",description="",in_out ="OUTPUT", socket_type="NodeSocketColor")
			nodeGroup.interface.new_socket(name="Alpha",description="",in_out ="OUTPUT", socket_type="NodeSocketFloat")
		nodeGroup.links.new(inNode.outputs["Color"],outNode.inputs["Color"])
		nodeGroup.links.new(inNode.outputs["Alpha"],outNode.inputs["Alpha"])
	
	nodeGroupNode = nodeTree.nodes.new("ShaderNodeGroup")
	nodeGroupNode.node_tree = nodeGroup
	
	return nodeGroupNode

def getImagePassThroughNodeGroup(nodeTree):#Same as color node group but with vector input/output, used for texture array selection
	if "ImagePassThroughNodeGroup" in bpy.data.node_groups:
		nodeGroup = bpy.data.node_groups["ImagePassThroughNodeGroup"]
	else:
		nodeGroup = bpy.data.node_groups.new(type="ShaderNodeTree", name="ImagePassThroughNodeGroup")
	
		if bpy.app.version < (4,0,0):
			nodeGroup.inputs.new("NodeSocketColor","Color")
			nodeGroup.inputs.new("NodeSocketFloat","Alpha")
			nodeGroup.inputs.new("NodeSocketVector","Vector")
		else:
			nodeGroup.interface.new_socket(name="Color",description="",in_out ="INPUT", socket_type="NodeSocketColor")
			nodeGroup.interface.new_socket(name="Alpha",description="",in_out ="INPUT", socket_type="NodeSocketFloat")
			nodeGroup.interface.new_socket(name="Vector",description="",in_out ="INPUT", socket_type="NodeSocketVector")
		
		inNode = nodeGroup.nodes.new('NodeGroupInput')
		
		outNode = nodeGroup.nodes.new('NodeGroupOutput')
		if bpy.app.version < (4,0,0):
			nodeGroup.outputs.new('NodeSocketColor', 'Color')
			nodeGroup.outputs.new('NodeSocketFloat', 'Alpha')
			nodeGroup.outputs.new('NodeSocketVector', 'Vector')
		else:
			nodeGroup.interface.new_socket(name="Color",description="",in_out ="OUTPUT", socket_type="NodeSocketColor")
			nodeGroup.interface.new_socket(name="Alpha",description="",in_out ="OUTPUT", socket_type="NodeSocketFloat")
			nodeGroup.interface.new_socket(name="Vector",description="",in_out ="OUTPUT", socket_type="NodeSocketVector")
		nodeGroup.links.new(inNode.outputs["Color"],outNode.inputs["Color"])
		nodeGroup.links.new(inNode.outputs["Alpha"],outNode.inputs["Alpha"])
		nodeGroup.links.new(inNode.outputs["Vector"],outNode.inputs["Vector"])
	
	nodeGroupNode = nodeTree.nodes.new("ShaderNodeGroup")
	nodeGroupNode.node_tree = nodeGroup
	
	return nodeGroupNode

def getVec4NodeGroup(nodeTree):
	if "Vec4NodeGroup" in bpy.data.node_groups:
		nodeGroup = bpy.data.node_groups["Vec4NodeGroup"]
	else:
		nodeGroup = bpy.data.node_groups.new(type="ShaderNodeTree", name="Vec4NodeGroup")
	
		if bpy.app.version < (4,0,0):
			nodeGroup.inputs.new("NodeSocketFloat","X")
			nodeGroup.inputs.new("NodeSocketFloat","Y")
			nodeGroup.inputs.new("NodeSocketFloat","Z")
			nodeGroup.inputs.new("NodeSocketFloat","W")
		else:
			nodeGroup.interface.new_socket(name="X",description="",in_out ="INPUT", socket_type="NodeSocketFloat")
			nodeGroup.interface.new_socket(name="Y",description="",in_out ="INPUT", socket_type="NodeSocketFloat")
			nodeGroup.interface.new_socket(name="Z",description="",in_out ="INPUT", socket_type="NodeSocketFloat")
			nodeGroup.interface.new_socket(name="W",description="",in_out ="INPUT", socket_type="NodeSocketFloat")
		inNode = nodeGroup.nodes.new('NodeGroupInput')
		
		outNode = nodeGroup.nodes.new('NodeGroupOutput')
		if bpy.app.version < (4,0,0):
			nodeGroup.outputs.new('NodeSocketFloat', "X")
			nodeGroup.outputs.new('NodeSocketFloat', "Y")
			nodeGroup.outputs.new('NodeSocketFloat', "Z")
			nodeGroup.outputs.new('NodeSocketFloat', "W")
		else:
			nodeGroup.interface.new_socket(name="X",description="",in_out ="OUTPUT", socket_type="NodeSocketFloat")
			nodeGroup.interface.new_socket(name="Y",description="",in_out ="OUTPUT", socket_type="NodeSocketFloat")
			nodeGroup.interface.new_socket(name="Z",description="",in_out ="OUTPUT", socket_type="NodeSocketFloat")
			nodeGroup.interface.new_socket(name="W",description="",in_out ="OUTPUT", socket_type="NodeSocketFloat")
		
		nodeGroup.links.new(inNode.outputs["X"],outNode.inputs["X"])
		nodeGroup.links.new(inNode.outputs["Y"],outNode.inputs["Y"])
		nodeGroup.links.new(inNode.outputs["Z"],outNode.inputs["Z"])
		nodeGroup.links.new(inNode.outputs["W"],outNode.inputs["W"])
	
	nodeGroupNode = nodeTree.nodes.new("ShaderNodeGroup")
	nodeGroupNode.node_tree = nodeGroup
	
	return nodeGroupNode

def getVec4ColorNodeGroup(nodeTree):#Color property with negative components, linked values are not clamped like socket defaults
	if "Vec4ColorNodeGroup" in bpy.data.node_groups:
		nodeGroup = bpy.data.node_groups["Vec4ColorNodeGroup"]
	else:
		nodeGroup = bpy.data.node_groups.new(type="ShaderNodeTree", name="Vec4ColorNodeGroup")
		for name in ("X","Y","Z","W"):
			if bpy.app.version < (4,0,0):
				nodeGroup.inputs.new("NodeSocketFloat",name)
			else:
				nodeGroup.interface.new_socket(name=name,description="",in_out ="INPUT", socket_type="NodeSocketFloat")
		if bpy.app.version < (4,0,0):
			nodeGroup.outputs.new('NodeSocketColor', 'Color')
			nodeGroup.outputs.new('NodeSocketFloat', 'Alpha')
		else:
			nodeGroup.interface.new_socket(name="Color",description="",in_out ="OUTPUT", socket_type="NodeSocketColor")
			nodeGroup.interface.new_socket(name="Alpha",description="",in_out ="OUTPUT", socket_type="NodeSocketFloat")
		inNode = nodeGroup.nodes.new('NodeGroupInput')
		combineNode = nodeGroup.nodes.new('ShaderNodeCombineXYZ')
		combineNode.location = (200,0)
		outNode = nodeGroup.nodes.new('NodeGroupOutput')
		outNode.location = (400,0)
		for name in ("X","Y","Z"):
			nodeGroup.links.new(inNode.outputs[name],combineNode.inputs[name])
		nodeGroup.links.new(combineNode.outputs["Vector"],outNode.inputs["Color"])
		nodeGroup.links.new(inNode.outputs["W"],outNode.inputs["Alpha"])

	nodeGroupNode = nodeTree.nodes.new("ShaderNodeGroup")
	nodeGroupNode.node_tree = nodeGroup

	return nodeGroupNode

def getBentNormalNodeGroup(nodeTree):
	if "BentNormalNodeGroup" in bpy.data.node_groups:
		nodeGroup = bpy.data.node_groups["BentNormalNodeGroup"]
	else:
		nodeGroup = bpy.data.node_groups.new(type="ShaderNodeTree", name="BentNormalNodeGroup")
		nodes = nodeGroup.nodes
		links = nodeGroup.links
		if bpy.app.version < (4,0,0):
			nodeGroup.inputs.new("NodeSocketFloat","Color")
			nodeGroup.inputs.new("NodeSocketFloat","Alpha")
		else:
			nodeGroup.interface.new_socket(name="Color",description="",in_out ="INPUT", socket_type="NodeSocketColor")
			nodeGroup.interface.new_socket(name="Alpha",description="",in_out ="INPUT", socket_type="NodeSocketFloat")
		inNode = nodeGroup.nodes.new('NodeGroupInput')
		currentLoc = [300,0]
		separateRGBNode = nodes.new("ShaderNodeSeparateColor")
		separateRGBNode.location = currentLoc
		currentLoc[0] += 300
		links.new(inNode.outputs["Color"],separateRGBNode.inputs["Color"])
		
		mapRangeYNode = nodes.new("ShaderNodeMapRange")
		mapRangeYNode.location = currentLoc
		mapRangeYNode.inputs["From Min"].default_value = 0.0
		mapRangeYNode.inputs["From Max"].default_value = 1.0
		mapRangeYNode.inputs["To Min"].default_value = -1.0
		mapRangeYNode.inputs["To Max"].default_value = 1.0
		
		links.new(separateRGBNode.outputs["Green"],mapRangeYNode.inputs["Value"])
		
		currentLoc[0] += 300
		
		multNode0Y = nodes.new("ShaderNodeMath")
		multNode0Y.location = currentLoc
		multNode0Y.operation = "MULTIPLY"
		
		links.new(mapRangeYNode.outputs["Result"],multNode0Y.inputs[0])
		links.new(mapRangeYNode.outputs["Result"],multNode0Y.inputs[1])
		
		signNodeY = nodes.new("ShaderNodeMath")
		signNodeY.location = (currentLoc[0],currentLoc[1] - 300)
		signNodeY.operation = "SIGN"
		links.new(mapRangeYNode.outputs["Result"],signNodeY.inputs[0])
		
		currentLoc[0] += 300
		
		multNode1Y = nodes.new("ShaderNodeMath")
		multNode1Y.location = currentLoc
		multNode1Y.operation = "MULTIPLY"
		
		links.new(multNode0Y.outputs["Value"],multNode1Y.inputs[0])
		links.new(signNodeY.outputs["Value"],multNode1Y.inputs[1])
		
		currentLoc[0] += 300
		
		multNode2Y = nodes.new("ShaderNodeMath")
		multNode2Y.location = currentLoc
		multNode2Y.operation = "MULTIPLY"
		
		links.new(multNode1Y.outputs["Value"],multNode2Y.inputs[0])
		links.new(multNode1Y.outputs["Value"],multNode2Y.inputs[1])
		
		
		currentLoc[0] += 300
		
		addXYNode = nodes.new("ShaderNodeMath")
		addXYNode.location = currentLoc
		addXYNode.operation = "ADD"
		
		links.new(multNode2Y.outputs["Value"],addXYNode.inputs[0])
		
		currentLoc[0] += 300
		
		subNode = nodes.new("ShaderNodeMath")
		subNode.location = currentLoc
		subNode.operation = "SUBTRACT"
		subNode.inputs[0].default_value = 1.0
		links.new(addXYNode.outputs["Value"],subNode.inputs[1])
		
		currentLoc[0] += 300
		
		sqrRootNode = nodes.new("ShaderNodeMath")
		sqrRootNode.location = currentLoc
		sqrRootNode.operation = "SQRT"
		links.new(subNode.outputs["Value"],sqrRootNode.inputs[0])
		
		currentLoc[0] += 300
		
		combineXYZNode = nodes.new("ShaderNodeCombineXYZ")
		combineXYZNode.location = currentLoc
		links.new(multNode1Y.outputs["Value"],combineXYZNode.inputs["X"])
		links.new(sqrRootNode.outputs["Value"],combineXYZNode.inputs["Z"])
		
		currentLoc[0] += 300
		
		vectorRotateNode = nodes.new("ShaderNodeVectorRotate")
		vectorRotateNode.location = currentLoc
		vectorRotateNode.inputs["Angle"].default_value = 0.785398#45 degrees
		links.new(combineXYZNode.outputs["Vector"],vectorRotateNode.inputs["Vector"])
		
		currentLoc[0] += 300
		
		mapRangeVectorNode = nodes.new("ShaderNodeMapRange")
		mapRangeVectorNode.location = currentLoc
		mapRangeVectorNode.data_type = "FLOAT_VECTOR"
		mapRangeVectorNode.clamp = False
		mapRangeVectorNode.inputs[7].default_value = Vector((-1.0,-1.0,-1.0))
		mapRangeVectorNode.inputs[8].default_value =  Vector((1.0,1.0,1.0))
		mapRangeVectorNode.inputs[9].default_value =  Vector((0.0,0.0,0.0))
		mapRangeVectorNode.inputs[10].default_value =  Vector((1.0,1.0,1.0))
		
		links.new(vectorRotateNode.outputs["Vector"],mapRangeVectorNode.inputs["Vector"])
		
		
		currentLoc = [600,-400]
		
		mapRangeXNode = nodes.new("ShaderNodeMapRange")
		mapRangeXNode.location = currentLoc
		mapRangeXNode.inputs["From Min"].default_value = 0.0
		mapRangeXNode.inputs["From Max"].default_value = 1.0
		mapRangeXNode.inputs["To Min"].default_value = 1.0
		mapRangeXNode.inputs["To Max"].default_value = -1.0
		
		links.new(inNode.outputs["Alpha"],mapRangeXNode.inputs["Value"])
		
		currentLoc[0] += 300
		
		multNode0X = nodes.new("ShaderNodeMath")
		multNode0X.location = currentLoc
		multNode0X.operation = "MULTIPLY"
		
		links.new(mapRangeXNode.outputs["Result"],multNode0X.inputs[0])
		links.new(mapRangeXNode.outputs["Result"],multNode0X.inputs[1])
		
		signNodeX = nodes.new("ShaderNodeMath")
		signNodeX.location = (currentLoc[0],currentLoc[1] - 300)
		signNodeX.operation = "SIGN"
		links.new(mapRangeXNode.outputs["Result"],signNodeX.inputs[0])
		
		currentLoc[0] += 300
		
		multNode1X = nodes.new("ShaderNodeMath")
		multNode1X.location = currentLoc
		multNode1X.operation = "MULTIPLY"
		
		links.new(multNode0X.outputs["Value"],multNode1X.inputs[0])
		links.new(signNodeX.outputs["Value"],multNode1X.inputs[1])
		
		links.new(multNode1X.outputs["Value"],combineXYZNode.inputs["Y"])
		
		currentLoc[0] += 300
		
		multNode2X = nodes.new("ShaderNodeMath")
		multNode2X.location = currentLoc
		multNode2X.operation = "MULTIPLY"
		
		links.new(multNode1X.outputs["Value"],multNode2X.inputs[0])
		links.new(multNode1X.outputs["Value"],multNode2X.inputs[1])
		links.new(multNode2X.outputs["Value"],addXYNode.inputs[1])
		
		currentLoc[0] += 300
		
		outNode = nodeGroup.nodes.new('NodeGroupOutput')
		if bpy.app.version < (4,0,0):
			nodeGroup.outputs.new('NodeSocketColor', "Color")
			nodeGroup.outputs.new('NodeSocketFloat', "Roughness")
			nodeGroup.outputs.new('NodeSocketFloat', "BlueChannel")
			
		else:
			nodeGroup.interface.new_socket(name="Color",description="",in_out ="OUTPUT", socket_type="NodeSocketColor")
			nodeGroup.interface.new_socket(name="Roughness",description="",in_out ="OUTPUT", socket_type="NodeSocketFloat")
			nodeGroup.interface.new_socket(name="BlueChannel",description="",in_out ="OUTPUT", socket_type="NodeSocketFloat")
		
		links.new(mapRangeVectorNode.outputs["Vector"],outNode.inputs["Color"])
		links.new(separateRGBNode.outputs["Red"],outNode.inputs["Roughness"])
		links.new(separateRGBNode.outputs["Blue"],outNode.inputs["BlueChannel"])

	nodeGroupNode = nodeTree.nodes.new("ShaderNodeGroup")
	nodeGroupNode.node_tree = nodeGroup
	
	return nodeGroupNode

def getMHWildsNRRONodeGroup(nodeTree):
	#Wilds SkinEdit PS: signed-square G/A, half-octahedral Z, then normalize.
	#Emit ordinary RGB normal-map colors for the existing Normal Map node;
	#this replaces the legacy decoder, it must not be stacked after that group.
	groupName = "MHWildsNRRODecode_v1"
	if groupName in bpy.data.node_groups:
		nodeGroup = bpy.data.node_groups[groupName]
	else:
		nodeGroup = bpy.data.node_groups.new(type="ShaderNodeTree", name=groupName)
		newGroupSockets(nodeGroup,[("Color","NodeSocketColor"),("Alpha","NodeSocketFloat")],"INPUT")
		newGroupSockets(nodeGroup,[("Color","NodeSocketColor"),("Roughness","NodeSocketFloat"),("BlueChannel","NodeSocketFloat")],"OUTPUT")
		b = ShaderGroupBuilder(nodeGroup)
		i = b.nodes.new('NodeGroupInput').outputs
		channels = b.separate(i["Color"])
		g = b.math("MULTIPLY_ADD",channels["Green"],2.0,-1.0)
		a = b.math("MULTIPLY_ADD",i["Alpha"],2.0,-1.0)
		g = b.math("MULTIPLY",g,b.math("ABSOLUTE",g))
		a = b.math("MULTIPLY",a,b.math("ABSOLUTE",a))
		x = b.math("MULTIPLY",b.math("ADD",g,a),0.5)
		y = b.math("MULTIPLY",b.math("SUBTRACT",g,a),0.5)
		z = b.math("SUBTRACT",b.math("SUBTRACT",1.0,b.math("ABSOLUTE",x)),b.math("ABSOLUTE",y))
		x,y,z = b.normalize3(x,y,z)
		color = b.combineColor(b.math("MULTIPLY_ADD",x,0.5,0.5),b.math("MULTIPLY_ADD",y,0.5,0.5),b.math("MULTIPLY_ADD",z,0.5,0.5))
		outNode = b.nodes.new('NodeGroupOutput')
		outNode.location = (b.x + 200,0)
		b.links.new(color,outNode.inputs["Color"])
		b.links.new(channels["Red"],outNode.inputs["Roughness"])
		b.links.new(channels["Blue"],outNode.inputs["BlueChannel"])
	nodeGroupNode = nodeTree.nodes.new("ShaderNodeGroup")
	nodeGroupNode.node_tree = nodeGroup
	return nodeGroupNode

def getDualUVMappingNodeGroup(nodeTree):
	if "DualUVMappingNodeGroupV2" in bpy.data.node_groups:
		nodeGroup = bpy.data.node_groups["DualUVMappingNodeGroupV2"]
	else:
		nodeGroup = bpy.data.node_groups.new(type="ShaderNodeTree", name="DualUVMappingNodeGroupV2")
		nodes = nodeGroup.nodes
		links = nodeGroup.links
		if bpy.app.version < (4,0,0):
			nodeGroup.inputs.new("NodeSocketVector","UV1")
			nodeGroup.inputs.new("NodeSocketVector","UV2")
			nodeGroup.inputs.new("NodeSocketFloat","UseSecondaryUV")
			nodeGroup.inputs.new("NodeSocketFloat","OffsetX")
			nodeGroup.inputs.new("NodeSocketFloat","OffsetY")
			nodeGroup.inputs.new("NodeSocketFloat","Rotation")
			nodeGroup.inputs.new("NodeSocketFloat","Tiling")
		else:
			nodeGroup.interface.new_socket(name="UV1",description="",in_out ="INPUT", socket_type="NodeSocketVector")
			nodeGroup.interface.new_socket(name="UV2",description="",in_out ="INPUT", socket_type="NodeSocketVector")
			nodeGroup.interface.new_socket(name="UseSecondaryUV",description="",in_out ="INPUT", socket_type="NodeSocketFloat")
			nodeGroup.interface.new_socket(name="OffsetX",description="",in_out ="INPUT", socket_type="NodeSocketFloat")
			nodeGroup.interface.new_socket(name="OffsetY",description="",in_out ="INPUT", socket_type="NodeSocketFloat")
			nodeGroup.interface.new_socket(name="Rotation",description="",in_out ="INPUT", socket_type="NodeSocketFloat")
			nodeGroup.interface.new_socket(name="Tiling",description="",in_out ="INPUT", socket_type="NodeSocketVector")
		inNode = nodeGroup.nodes.new('NodeGroupInput')
		#inNode.outputs["UseSecondaryUV"].default_value = 0.0
		#inNode.outputs["Tiling"].default_value = 1.0
		#Setting defaults here doesn't work
		currentLoc = [300,0]
		secondaryUVClampNode = nodes.new("ShaderNodeClamp")
		secondaryUVClampNode.location = currentLoc
		links.new(inNode.outputs["UseSecondaryUV"],secondaryUVClampNode.inputs["Value"])
		
		currentLoc[0] += 300
		
		vectorMixNode = nodes.new("ShaderNodeMixRGB")
		vectorMixNode.location = currentLoc
		links.new(secondaryUVClampNode.outputs["Result"],vectorMixNode.inputs["Fac"])
		links.new(inNode.outputs["UV1"],vectorMixNode.inputs["Color1"])
		links.new(inNode.outputs["UV2"],vectorMixNode.inputs["Color2"])
		currentLoc[0] += 300
		
		locCombineNode = nodes.new("ShaderNodeCombineXYZ")
		locCombineNode.location = currentLoc
		links.new(inNode.outputs["OffsetX"],locCombineNode.inputs["X"])
		links.new(inNode.outputs["OffsetY"],locCombineNode.inputs["Y"])
		currentLoc[0] += 300
		
		rotCombineNode = nodes.new("ShaderNodeCombineXYZ")
		rotCombineNode.location = (currentLoc[0],currentLoc[1] + 300)
		links.new(inNode.outputs["Rotation"],rotCombineNode.inputs["X"])
		currentLoc[0] += 300
		
		
		mappingNode = nodes.new("ShaderNodeMapping")
		mappingNode.location = currentLoc
		links.new(vectorMixNode.outputs["Color"],mappingNode.inputs["Vector"])
		links.new(locCombineNode.outputs["Vector"],mappingNode.inputs["Location"])
		links.new(rotCombineNode.outputs["Vector"],mappingNode.inputs["Rotation"])
		links.new(inNode.outputs["Tiling"],mappingNode.inputs["Scale"])
		currentLoc[0] += 300
		
		
		outNode = nodeGroup.nodes.new('NodeGroupOutput')
		if bpy.app.version < (4,0,0):
			nodeGroup.outputs.new('NodeSocketVector', "Vector")
			
		else:
			nodeGroup.interface.new_socket(name="Vector",description="",in_out ="OUTPUT", socket_type="NodeSocketVector")
		
		links.new(mappingNode.outputs["Vector"],outNode.inputs["Vector"])
	
	nodeGroupNode = nodeTree.nodes.new("ShaderNodeGroup")
	nodeGroupNode.node_tree = nodeGroup
	
	#Set defaults
	try:
		nodeGroupNode.inputs["Tiling"].default_value = (1.0,1.0,1.0)
	except:
		try:
			nodeGroupNode.inputs["Tiling"].default_value = 1.0
		except:
			pass
	return nodeGroupNode
	

def getMHWildsSkinMappingNodeGroup(nodeTree):
	if "MHWildsSkinMappingV2" in bpy.data.node_groups:
		nodeGroup = bpy.data.node_groups["MHWildsSkinMappingV2"]
	else:
		nodeGroup = bpy.data.node_groups.new(type="ShaderNodeTree", name="MHWildsSkinMappingV2")
	
		if bpy.app.version < (4,0,0):
			nodeGroup.inputs.new("NodeSocketFloat","X")
			nodeGroup.inputs.new("NodeSocketFloat","Y")
			
		else:
			nodeGroup.interface.new_socket(name="X",description="",in_out ="INPUT", socket_type="NodeSocketFloat")
			nodeGroup.interface.new_socket(name="Y",description="",in_out ="INPUT", socket_type="NodeSocketFloat")
		
		nodes = nodeGroup.nodes
		links = nodeGroup.links
		
		inNode = nodeGroup.nodes.new('NodeGroupInput')

		currentLoc = [300,0]
		#Multiply node input values to give finer control since min and max inputs can't be set any more.
		multXNode = nodes.new("ShaderNodeMath")
		multXNode.location = [currentLoc[0],currentLoc[1]+300]
		multXNode.operation = "MULTIPLY"
		links.new(inNode.outputs["X"],multXNode.inputs[0])
		multXNode.inputs[1].default_value = 0.01
		
		multYNode = nodes.new("ShaderNodeMath")
		multYNode.location = [currentLoc[0],currentLoc[1]-300]
		multYNode.operation = "MULTIPLY"
		links.new(inNode.outputs["Y"],multYNode.inputs[0])
		multYNode.inputs[1].default_value = 0.01
		
		currentLoc[0] += 300
		
		combineXYZNode = nodes.new("ShaderNodeCombineXYZ")
		combineXYZNode.location = currentLoc
		links.new(multXNode.outputs["Value"],combineXYZNode.inputs["X"])
		links.new(multYNode.outputs["Value"],combineXYZNode.inputs["Y"])
		
		currentLoc[0] += 300
		
		mappingNode = nodes.new("ShaderNodeMapping")
		mappingNode.location = currentLoc
		links.new(combineXYZNode.outputs["Vector"],mappingNode.inputs["Location"])
		mappingNode.inputs["Scale"].default_value = (0.01,0.01,1.0)
		
		
		
		outNode = nodeGroup.nodes.new('NodeGroupOutput')
		if bpy.app.version < (4,0,0):
			nodeGroup.outputs.new('NodeSocketVector', "Vector")
			
		else:
			nodeGroup.interface.new_socket(name="Vector",description="",in_out ="OUTPUT", socket_type="NodeSocketVector")
		
		links.new(mappingNode.outputs["Vector"],outNode.inputs["Vector"])
	
	
	
	
	
	nodeGroupNode = nodeTree.nodes.new("ShaderNodeGroup")
	nodeGroupNode.node_tree = nodeGroup
	
	#Set defaults
	
	#Set skin tone closer to MHW default
	nodeGroupNode.inputs["X"].default_value = 10.0
	#nodeGroupNode.inputs["X"].min_value = 0.001
	#nodeGroupNode.inputs["X"].max_value = 0.999
	
	nodeGroupNode.inputs["Y"].default_value = 75.0
	
	#nodeGroupNode.inputs["Y"].min_value = 0.001
	#nodeGroupNode.inputs["Y"].max_value = 0.999
	
	return nodeGroupNode

def getMHWildsFakeSphereUVNodeGroup(nodeTree):
	#View space normal XY lookup used by the MH Wilds FakeSphere / ToonFakeSphere slots (matcap style, clamp sampler)
	#From the compiled shaders: BaseAlpha_MatCap_FX PS #75, Base_eyeRefract_Emit PS #63, Base_GOLD_Push PS #65 (gold has no ScaleOffset/Position, defaults below give the same UV)
	#M = max(Position.rgb), m = min(Position.rgb)
	#shiftX = M != 0 ? 1 - 2*((M + 1e-6 - m)/M) : 1, shiftY = 2*M - 1
	#q = (normalVS.xy + ScaleOffset.zw + (shiftX,-shiftY)) / max(ScaleOffset.xy,1e-5)
	#uv = (0.5 + 0.5*q.x, 0.5 - 0.5*q.y) in D3D texture space, so V is flipped back for Blender
	if "MHWildsFakeSphereUV" in bpy.data.node_groups:
		nodeGroup = bpy.data.node_groups["MHWildsFakeSphereUV"]
	else:
		nodeGroup = bpy.data.node_groups.new(type="ShaderNodeTree", name="MHWildsFakeSphereUV")

		if bpy.app.version < (4,0,0):
			nodeGroup.inputs.new("NodeSocketVector","Normal")
			nodeGroup.inputs.new("NodeSocketColor","Position")
			nodeGroup.inputs.new("NodeSocketFloat","ScaleX")
			nodeGroup.inputs.new("NodeSocketFloat","ScaleY")
			nodeGroup.inputs.new("NodeSocketFloat","OffsetX")
			nodeGroup.inputs.new("NodeSocketFloat","OffsetY")
			nodeGroup.outputs.new("NodeSocketVector","Vector")
		else:
			nodeGroup.interface.new_socket(name="Normal",description="",in_out ="INPUT", socket_type="NodeSocketVector")
			nodeGroup.interface.new_socket(name="Position",description="",in_out ="INPUT", socket_type="NodeSocketColor")
			nodeGroup.interface.new_socket(name="ScaleX",description="",in_out ="INPUT", socket_type="NodeSocketFloat")
			nodeGroup.interface.new_socket(name="ScaleY",description="",in_out ="INPUT", socket_type="NodeSocketFloat")
			nodeGroup.interface.new_socket(name="OffsetX",description="",in_out ="INPUT", socket_type="NodeSocketFloat")
			nodeGroup.interface.new_socket(name="OffsetY",description="",in_out ="INPUT", socket_type="NodeSocketFloat")
			nodeGroup.interface.new_socket(name="Vector",description="",in_out ="OUTPUT", socket_type="NodeSocketVector")

		nodes = nodeGroup.nodes
		links = nodeGroup.links

		def mathNode(operation,a,b,loc,c = None):
			node = nodes.new("ShaderNodeMath")
			node.operation = operation
			node.location = loc
			for index,value in enumerate((a,b) if c == None else (a,b,c)):
				if isinstance(value,(int,float)):
					node.inputs[index].default_value = value
				else:
					links.new(value,node.inputs[index])
			return node.outputs["Value"]

		inNode = nodes.new('NodeGroupInput')
		inNode.location = (-200,0)

		#Camera space in Blender is X right, Y up, same as the first two rows of the view matrix
		transformNode = nodes.new("ShaderNodeVectorTransform")
		transformNode.location = (0,300)
		transformNode.vector_type = "NORMAL"
		transformNode.convert_from = "WORLD"
		transformNode.convert_to = "CAMERA"
		links.new(inNode.outputs["Normal"],transformNode.inputs["Vector"])

		normalSepNode = nodes.new("ShaderNodeSeparateXYZ")
		normalSepNode.location = (200,300)
		links.new(transformNode.outputs["Vector"],normalSepNode.inputs["Vector"])

		posSepNode = nodes.new("ShaderNodeSeparateColor")
		posSepNode.location = (0,-200)
		links.new(inNode.outputs["Position"],posSepNode.inputs["Color"])

		posMax = mathNode("MAXIMUM",posSepNode.outputs["Red"],mathNode("MAXIMUM",posSepNode.outputs["Green"],posSepNode.outputs["Blue"],(200,-100)),(400,-100))
		posMin = mathNode("MINIMUM",posSepNode.outputs["Red"],mathNode("MINIMUM",posSepNode.outputs["Green"],posSepNode.outputs["Blue"],(200,-300)),(400,-300))
		#Blender's divide returns 0 when M is 0, which gives shiftX = 1 like the shader's branch
		ratio = mathNode("DIVIDE",mathNode("SUBTRACT",mathNode("ADD",posMax,1.0e-6,(600,-100)),posMin,(800,-100)),posMax,(1000,-100))
		shiftX = mathNode("SUBTRACT",1.0,mathNode("MULTIPLY",ratio,2.0,(1200,-100)),(1400,-100))
		shiftY = mathNode("SUBTRACT",mathNode("MULTIPLY",posMax,2.0,(600,-300)),1.0,(800,-300))

		qX = mathNode("DIVIDE",
			mathNode("ADD",mathNode("ADD",normalSepNode.outputs["X"],inNode.outputs["OffsetX"],(1400,300)),shiftX,(1600,300)),
			mathNode("MAXIMUM",inNode.outputs["ScaleX"],1.0e-5,(1600,500)),(1800,300))
		qY = mathNode("DIVIDE",
			mathNode("SUBTRACT",mathNode("ADD",normalSepNode.outputs["Y"],inNode.outputs["OffsetY"],(1400,100)),shiftY,(1600,100)),
			mathNode("MAXIMUM",inNode.outputs["ScaleY"],1.0e-5,(1600,-500)),(1800,100))

		#Blender V = 1 - D3D V = 0.5 + 0.5*q.y
		combineNode = nodes.new("ShaderNodeCombineXYZ")
		combineNode.location = (2200,200)
		links.new(mathNode("MULTIPLY_ADD",qX,0.5,(2000,300),0.5),combineNode.inputs["X"])
		links.new(mathNode("MULTIPLY_ADD",qY,0.5,(2000,100),0.5),combineNode.inputs["Y"])

		outNode = nodes.new('NodeGroupOutput')
		outNode.location = (2400,200)
		links.new(combineNode.outputs["Vector"],outNode.inputs["Vector"])

	nodeGroupNode = nodeTree.nodes.new("ShaderNodeGroup")
	nodeGroupNode.node_tree = nodeGroup
	#Defaults give zero shift and no scaling, which is the Base_GOLD_Push lookup
	nodeGroupNode.inputs["Position"].default_value = (0.5,0.25,0.25,1.0)
	nodeGroupNode.inputs["ScaleX"].default_value = 1.0
	nodeGroupNode.inputs["ScaleY"].default_value = 1.0
	return nodeGroupNode

def getMHWildsColorLayerNodeGroup(nodeTree):
	#ColorLayer_MaskMap tinting, from Base_Equip PS #63 (DXIL %1747..%1866)
	#Per channel c: x = saturate(saturate(Mask.c + Width.c - (Width.c+1)*(1 - Fade.c/2)) / Width.c), m = x*x*(3-2x)
	#layer = UseOverRay ? 0.5 : base, then for R,G,B,A: layer = lerp(layer, ColorLayer_c.rgb, m*ColorLayer_c.a)
	#color = UseOverRay ? 2*base*layer : layer, so the 0.502 defaults leave the base color unchanged
	#roughness multiplier: r = 1, then r = lerp(r, ColorLayer_Roughness.c, m*ColorLayer_c.a) for R,G,B,A
	if "MHWildsColorLayer" in bpy.data.node_groups:
		nodeGroup = bpy.data.node_groups["MHWildsColorLayer"]
	else:
		nodeGroup = bpy.data.node_groups.new(type="ShaderNodeTree", name="MHWildsColorLayer")
		channels = ("R","G","B","A")
		socketList = [("Base","NodeSocketColor"),("Mask","NodeSocketColor"),("MaskAlpha","NodeSocketFloat")]
		for channel in channels:
			socketList.append((f"ColorLayer_{channel}","NodeSocketColor"))
			socketList.append((f"ColorLayer_{channel}_Alpha","NodeSocketFloat"))
		socketList += [("Width","NodeSocketColor"),("WidthA","NodeSocketFloat"),("Fade","NodeSocketColor"),("FadeA","NodeSocketFloat"),
			("Roughness","NodeSocketColor"),("RoughnessA","NodeSocketFloat"),("UseOverRay","NodeSocketFloat"),
			("Detail Mask","NodeSocketColor"),("Detail Mask Alpha","NodeSocketFloat"),("ColorLayer_DetailMask_Blend","NodeSocketFloat")]
		for name,socketType in socketList:
			if bpy.app.version < (4,0,0):
				nodeGroup.inputs.new(socketType,name)
			else:
				nodeGroup.interface.new_socket(name=name,description="",in_out ="INPUT", socket_type=socketType)
		for name,socketType in (("Color","NodeSocketColor"),("Roughness","NodeSocketFloat")):
			if bpy.app.version < (4,0,0):
				nodeGroup.outputs.new(socketType,name)
			else:
				nodeGroup.interface.new_socket(name=name,description="",in_out ="OUTPUT", socket_type=socketType)

		nodes = nodeGroup.nodes
		links = nodeGroup.links
		def mathNode(operation,a,b,loc,c = None,clamp = False):
			node = nodes.new("ShaderNodeMath")
			node.operation = operation
			node.location = loc
			node.use_clamp = clamp
			for index,value in enumerate((a,b) if c == None else (a,b,c)):
				if isinstance(value,(int,float)):
					node.inputs[index].default_value = value
				else:
					links.new(value,node.inputs[index])
			return node.outputs["Value"]
		def separate(socket,loc):
			node = nodes.new("ShaderNodeSeparateColor")
			node.location = loc
			links.new(socket,node.inputs["Color"])
			return node.outputs
		def mixColor(blendType,fac,colorA,colorB,loc):
			node = nodes.new("ShaderNodeMixRGB")
			node.blend_type = blendType
			node.location = loc
			if isinstance(fac,(int,float)):
				node.inputs["Fac"].default_value = fac
			else:
				links.new(fac,node.inputs["Fac"])
			links.new(colorA,node.inputs["Color1"])
			if isinstance(colorB,tuple):
				node.inputs["Color2"].default_value = colorB
			else:
				links.new(colorB,node.inputs["Color2"])
			return node.outputs["Color"]

		inNode = nodes.new('NodeGroupInput')
		inNode.location = (-400,0)
		maskSep = separate(inNode.outputs["Mask"],(-200,600))
		widthSep = separate(inNode.outputs["Width"],(-200,300))
		fadeSep = separate(inNode.outputs["Fade"],(-200,0))
		roughSep = separate(inNode.outputs["Roughness"],(-200,-300))
		detailSep = separate(inNode.outputs["Detail Mask"],(-200,-600))

		useOverRay = mathNode("GREATER_THAN",inNode.outputs["UseOverRay"],0.0,(0,-600))
		layer = mixColor("MIX",useOverRay,inNode.outputs["Base"],(0.5,0.5,0.5,1.0),(200,-600))
		roughness = 1.0
		for index,channel in enumerate(channels):
			y = 900 - index * 500
			if channel == "A":
				maskValue,width,fade,roughValue = inNode.outputs["MaskAlpha"],inNode.outputs["WidthA"],inNode.outputs["FadeA"],inNode.outputs["RoughnessA"]
			else:
				socketName = ("Red","Green","Blue")[index]
				maskValue,width,fade,roughValue = maskSep[socketName],widthSep[socketName],fadeSep[socketName],roughSep[socketName]
			#ColorLayer_DetailMaskMap: mask *= (2*detail - 1)*ColorLayer_DetailMask_Blend + 1, not saturated (MultiBlend PS #61 %1843..%1862)
			detailValue = inNode.outputs["Detail Mask Alpha"] if channel == "A" else detailSep[socketName]
			maskValue = mathNode("MULTIPLY",maskValue,mathNode("MULTIPLY_ADD",mathNode("MULTIPLY_ADD",detailValue,2.0,(0,y-300),-1.0),inNode.outputs["ColorLayer_DetailMask_Blend"],(100,y-300),1.0),(150,y-300))
			fadeTerm = mathNode("MULTIPLY",mathNode("ADD",width,1.0,(200,y-100)),mathNode("MULTIPLY_ADD",fade,-0.5,(200,y-200),1.0),(400,y-100))
			x = mathNode("SUBTRACT",mathNode("ADD",maskValue,width,(200,y)),fadeTerm,(600,y),clamp = True)
			#Blender's divide returns 0 for a zero width, the shader gets NaN which saturate also turns into 0
			x = mathNode("DIVIDE",x,width,(800,y),clamp = True)
			smooth = mathNode("MULTIPLY",mathNode("MULTIPLY",x,x,(1000,y)),mathNode("MULTIPLY_ADD",x,-2.0,(1000,y-100),3.0),(1200,y))
			weight = mathNode("MULTIPLY",smooth,inNode.outputs[f"ColorLayer_{channel}_Alpha"],(1400,y))
			layer = mixColor("MIX",weight,layer,inNode.outputs[f"ColorLayer_{channel}"],(1600,y))
			if isinstance(roughness,float):
				roughness = mathNode("MULTIPLY_ADD",mathNode("SUBTRACT",roughValue,1.0,(1600,y-200)),weight,(1800,y-200),1.0)
			else:
				roughness = mathNode("MULTIPLY_ADD",mathNode("SUBTRACT",roughValue,roughness,(1600,y-200)),weight,(1800,y-200),roughness)

		overRayNode = nodes.new("ShaderNodeVectorMath")
		overRayNode.operation = "MULTIPLY"
		overRayNode.location = (2000,0)
		links.new(inNode.outputs["Base"],overRayNode.inputs[0])
		links.new(layer,overRayNode.inputs[1])
		scaleNode = nodes.new("ShaderNodeVectorMath")
		scaleNode.operation = "SCALE"
		scaleNode.location = (2200,0)
		links.new(overRayNode.outputs["Vector"],scaleNode.inputs[0])
		scaleNode.inputs["Scale"].default_value = 2.0
		finalColor = mixColor("MIX",useOverRay,layer,scaleNode.outputs["Vector"],(2400,0))

		outNode = nodes.new('NodeGroupOutput')
		outNode.location = (2600,0)
		links.new(finalColor,outNode.inputs["Color"])
		links.new(roughness,outNode.inputs["Roughness"])

	nodeGroupNode = nodeTree.nodes.new("ShaderNodeGroup")
	nodeGroupNode.node_tree = nodeGroup
	for channel in ("R","G","B","A"):
		nodeGroupNode.inputs[f"ColorLayer_{channel}"].default_value = (0.5,0.5,0.5,1.0)
	for name in ("Width","Fade","Roughness"):
		nodeGroupNode.inputs[name].default_value = (1.0,1.0,1.0,1.0)
		nodeGroupNode.inputs[name+"A"].default_value = 1.0
	nodeGroupNode.inputs["UseOverRay"].default_value = 1.0
	nodeGroupNode.inputs["Detail Mask"].default_value = (0.5,0.5,0.5,1.0)
	nodeGroupNode.inputs["Detail Mask Alpha"].default_value = 0.5
	return nodeGroupNode

def getMHWildsDetailMapNodeGroup(nodeTree):#Unfinished
	if "MHWildsDetailMapNodeGroup" in bpy.data.node_groups:
		nodeGroup = bpy.data.node_groups["MHWildsDetailMapNodeGroup"]
	else:
		nodeGroup = bpy.data.node_groups.new(type="ShaderNodeTree", name="MHWildsDetailMapNodeGroup")
		nodes = nodeGroup.nodes
		links = nodeGroup.links
		if bpy.app.version < (4,0,0):
			nodeGroup.inputs.new("NodeSocketColor","DetailMaskMap")
			nodeGroup.inputs.new("NodeSocketFloat","DetailMaskMapAlpha")
			
			nodeGroup.inputs.new("NodeSocketColor","ColorLayer_R")
			nodeGroup.inputs.new("NodeSocketColor","ColorParam_R")
			nodeGroup.inputs.new("NodeSocketColor","NormalLayer_R")
			nodeGroup.inputs.new("NodeSocketFloat","NormalParam_R")
			nodeGroup.inputs.new("NodeSocketFloat","RoughnessLayer_R")
			nodeGroup.inputs.new("NodeSocketFloat","RoughnessParam_R")
			nodeGroup.inputs.new("NodeSocketFloat","MetallicLayer_R")
			nodeGroup.inputs.new("NodeSocketFloat","MetallicParam_R")
			
			nodeGroup.inputs.new("NodeSocketColor","ColorLayer_G")
			nodeGroup.inputs.new("NodeSocketColor","ColorParam_G")
			nodeGroup.inputs.new("NodeSocketColor","NormalLayer_G")
			nodeGroup.inputs.new("NodeSocketFloat","NormalParam_G")
			nodeGroup.inputs.new("NodeSocketFloat","RoughnessLayer_G")
			nodeGroup.inputs.new("NodeSocketFloat","RoughnessParam_G")
			nodeGroup.inputs.new("NodeSocketFloat","MetallicLayer_G")
			nodeGroup.inputs.new("NodeSocketFloat","MetallicParam_G")
			
			nodeGroup.inputs.new("NodeSocketColor","ColorLayer_B")
			nodeGroup.inputs.new("NodeSocketColor","ColorParam_B")
			nodeGroup.inputs.new("NodeSocketColor","NormalLayer_B")
			nodeGroup.inputs.new("NodeSocketFloat","NormalParam_B")
			nodeGroup.inputs.new("NodeSocketFloat","RoughnessLayer_B")
			nodeGroup.inputs.new("NodeSocketFloat","RoughnessParam_B")
			nodeGroup.inputs.new("NodeSocketFloat","MetallicLayer_B")
			nodeGroup.inputs.new("NodeSocketFloat","MetallicParam_B")
			
			nodeGroup.inputs.new("NodeSocketColor","ColorLayer_A")
			nodeGroup.inputs.new("NodeSocketColor","ColorParam_A")
			nodeGroup.inputs.new("NodeSocketColor","NormalLayer_A")
			nodeGroup.inputs.new("NodeSocketFloat","NormalParam_A")
			nodeGroup.inputs.new("NodeSocketFloat","RoughnessLayer_A")
			nodeGroup.inputs.new("NodeSocketFloat","RoughnessParam_A")
			nodeGroup.inputs.new("NodeSocketFloat","MetallicLayer_A")
			nodeGroup.inputs.new("NodeSocketFloat","MetallicParam_A")
			
			nodeGroup.inputs.new("NodeSocketFloat","UseDetail")
			nodeGroup.inputs.new("NodeSocketVector","TexCoordNormal")

		else:
			nodeGroup.interface.new_socket(name="DetailMaskMap",description="",in_out ="INPUT", socket_type="NodeSocketColor")
			nodeGroup.interface.new_socket(name="DetailMaskMapAlpha",description="",in_out ="INPUT", socket_type="NodeSocketFloat")
			
			nodeGroup.interface.new_socket(name="ColorLayer_R",description="",in_out ="INPUT", socket_type="NodeSocketColor")
			nodeGroup.interface.new_socket(name="ColorParam_R",description="",in_out ="INPUT", socket_type="NodeSocketColor")
			nodeGroup.interface.new_socket(name="NormalLayer_R",description="",in_out ="INPUT", socket_type="NodeSocketColor")
			nodeGroup.interface.new_socket(name="NormalParam_R",description="",in_out ="INPUT", socket_type="NodeSocketFloat")
			nodeGroup.interface.new_socket(name="RoughnessLayer_R",description="",in_out ="INPUT", socket_type="NodeSocketFloat")
			nodeGroup.interface.new_socket(name="RoughnessParam_R",description="",in_out ="INPUT", socket_type="NodeSocketFloat")
			nodeGroup.interface.new_socket(name="MetallicLayer_R",description="",in_out ="INPUT", socket_type="NodeSocketFloat")
			nodeGroup.interface.new_socket(name="MetallicParam_R",description="",in_out ="INPUT", socket_type="NodeSocketFloat")
			
			nodeGroup.interface.new_socket(name="ColorLayer_G",description="",in_out ="INPUT", socket_type="NodeSocketColor")
			nodeGroup.interface.new_socket(name="ColorParam_G",description="",in_out ="INPUT", socket_type="NodeSocketColor")
			nodeGroup.interface.new_socket(name="NormalLayer_G",description="",in_out ="INPUT", socket_type="NodeSocketColor")
			nodeGroup.interface.new_socket(name="NormalParam_G",description="",in_out ="INPUT", socket_type="NodeSocketFloat")
			nodeGroup.interface.new_socket(name="RoughnessLayer_G",description="",in_out ="INPUT", socket_type="NodeSocketFloat")
			nodeGroup.interface.new_socket(name="RoughnessParam_G",description="",in_out ="INPUT", socket_type="NodeSocketFloat")
			nodeGroup.interface.new_socket(name="MetallicLayer_G",description="",in_out ="INPUT", socket_type="NodeSocketFloat")
			nodeGroup.interface.new_socket(name="MetallicParam_G",description="",in_out ="INPUT", socket_type="NodeSocketFloat")
			
			nodeGroup.interface.new_socket(name="ColorLayer_B",description="",in_out ="INPUT", socket_type="NodeSocketColor")
			nodeGroup.interface.new_socket(name="ColorParam_B",description="",in_out ="INPUT", socket_type="NodeSocketColor")
			nodeGroup.interface.new_socket(name="NormalLayer_B",description="",in_out ="INPUT", socket_type="NodeSocketColor")
			nodeGroup.interface.new_socket(name="NormalParam_B",description="",in_out ="INPUT", socket_type="NodeSocketFloat")
			nodeGroup.interface.new_socket(name="RoughnessLayer_B",description="",in_out ="INPUT", socket_type="NodeSocketFloat")
			nodeGroup.interface.new_socket(name="RoughnessParam_B",description="",in_out ="INPUT", socket_type="NodeSocketFloat")
			nodeGroup.interface.new_socket(name="MetallicLayer_B",description="",in_out ="INPUT", socket_type="NodeSocketFloat")
			nodeGroup.interface.new_socket(name="MetallicParam_B",description="",in_out ="INPUT", socket_type="NodeSocketFloat")
			
			nodeGroup.interface.new_socket(name="ColorLayer_A",description="",in_out ="INPUT", socket_type="NodeSocketColor")
			nodeGroup.interface.new_socket(name="ColorParam_A",description="",in_out ="INPUT", socket_type="NodeSocketColor")
			nodeGroup.interface.new_socket(name="NormalLayer_A",description="",in_out ="INPUT", socket_type="NodeSocketColor")
			nodeGroup.interface.new_socket(name="NormalParam_A",description="",in_out ="INPUT", socket_type="NodeSocketFloat")
			nodeGroup.interface.new_socket(name="RoughnessLayer_A",description="",in_out ="INPUT", socket_type="NodeSocketFloat")
			nodeGroup.interface.new_socket(name="RoughnessParam_A",description="",in_out ="INPUT", socket_type="NodeSocketFloat")
			nodeGroup.interface.new_socket(name="MetallicLayer_A",description="",in_out ="INPUT", socket_type="NodeSocketFloat")
			nodeGroup.interface.new_socket(name="MetallicParam_A",description="",in_out ="INPUT", socket_type="NodeSocketFloat")
			
			nodeGroup.interface.new_socket(name="UseDetail",description="",in_out ="INPUT", socket_type="NodeSocketFloat")
			nodeGroup.interface.new_socket(name="TexCoordNormal",description="",in_out ="INPUT", socket_type="NodeSocketVector")
			
		inNode = nodeGroup.nodes.new('NodeGroupInput')
	
		currentLoc = [300,0]
		
		#TODO
		
		outNode = nodeGroup.nodes.new('NodeGroupOutput')
		if bpy.app.version < (4,0,0):
			nodeGroup.outputs.new('NodeSocketColor', "Color")
			nodeGroup.outputs.new('NodeSocketVector', "Normal")
			nodeGroup.outputs.new('NodeSocketFloat', "Roughness")
			nodeGroup.outputs.new('NodeSocketFloat', "Metallic")
			
		else:
			nodeGroup.interface.new_socket(name="Color",description="",in_out ="OUTPUT", socket_type="NodeSocketColor")
			nodeGroup.interface.new_socket(name="Normal",description="",in_out ="OUTPUT", socket_type="NodeSocketVector")
			nodeGroup.interface.new_socket(name="Roughness",description="",in_out ="OUTPUT", socket_type="NodeSocketFloat")
			nodeGroup.interface.new_socket(name="Metallic",description="",in_out ="OUTPUT", socket_type="NodeSocketFloat")
		
		#links.new(mappingNode.outputs["Vector"],outNode.inputs["Vector"])
	
	nodeGroupNode = nodeTree.nodes.new("ShaderNodeGroup")
	nodeGroupNode.node_tree = nodeGroup
	
	
	return nodeGroupNode
	


def addPropertyNode(prop,currentPos,node_tree):
	if prop.propName in node_tree.nodes:
		propNode = node_tree.nodes[prop.propName]
	else:
		lowerPropName = prop.propName.lower()
		isColor = prop.propName in colorPropertySet or (prop.paramCount == 4 and ("color" in lowerPropName or "_col_" in lowerPropName) and "rate" not in lowerPropName)
		if isColor and min(prop.propValue[:4]) < 0.0:
			#Color sockets clamp negative default values to 0 but the shader gets the raw float4, so take the components as floats
			#Same X/Y/Z/W inputs as the MDF panel's VEC4 entry, same Color/Alpha outputs as a color property node
			nodeGroup = getVec4ColorNodeGroup(node_tree)
			for index in range(4):
				nodeGroup.inputs[index].default_value = prop.propValue[index]
			propNode = nodeGroup
		elif isColor:
			#RGBA Color
			nodeGroup = getColorNodeGroup(node_tree)
			nodeGroup.inputs["Color"].default_value = prop.propValue
			nodeGroup.inputs["Alpha"].default_value = prop.propValue[3]
			propNode = nodeGroup
		elif prop.paramCount > 1:
			#Vec4
			nodeGroup = getVec4NodeGroup(node_tree)
			nodeGroup.inputs[0].default_value = prop.propValue[0]
			nodeGroup.inputs[1].default_value = prop.propValue[1]
			nodeGroup.inputs[2].default_value = prop.propValue[2]
			nodeGroup.inputs[3].default_value = prop.propValue[3]
			propNode = nodeGroup
		else:
			propNode = node_tree.nodes.new("ShaderNodeValue")
			propNode.outputs["Value"].default_value = float(prop.propValue[0])
	
		propNode.name = prop.propName
		propNode.label = prop.propName
		propNode.location = currentPos
		currentPos[1] -= int(propNode.height*2.5)
	return propNode
class dynamicColorMixLayerNodeGroup():
	def __init__(self,nodeTree):
		self._currentOutSocket = None
		self.nodeLoc = (0,0)
		self.node_tree = nodeTree
		
	@property
	def currentOutSocket(self):
		return self._currentOutSocket
	
	@currentOutSocket.setter
	def currentOutSocket(self,value):
		self._currentOutSocket = value
		if value != None:
			self.nodeLoc = value.node.location
	
	def addMixLayer(self,colorOutSocket,factorOutSocket = None,mixType = "MIX",mixFactor = 0.5,swapInputs = False):
		
		
		if self.currentOutSocket == None:#For the first layer added, just store the out socket since it's not being mixed with anything
			self.currentOutSocket = colorOutSocket
		else:
			mixNode = self.node_tree.nodes.new('ShaderNodeMixRGB')
			mixNode.location = (self.nodeLoc[0]+(self.currentOutSocket.node.width+100),self.nodeLoc[1])
			mixNode.blend_type = mixType
			mixNode.inputs["Fac"].default_value = mixFactor
			
			if swapInputs:
				self.node_tree.links.new(self.currentOutSocket,mixNode.inputs["Color2"])
				self.node_tree.links.new(colorOutSocket,mixNode.inputs["Color1"])
			else:
				self.node_tree.links.new(self.currentOutSocket,mixNode.inputs["Color1"])
				self.node_tree.links.new(colorOutSocket,mixNode.inputs["Color2"])
			if factorOutSocket != None:
				self.node_tree.links.new(factorOutSocket,mixNode.inputs["Fac"])
			self.currentOutSocket = mixNode.outputs["Color"]

class dynamicArrayTextureSelectorNodeGroup():
	def __init__(self,nodeTree):
		self._currentOutSocket = None
		self.currentOutAlphaSocket = None
		self.nodeLoc = (0,0)
		self.node_tree = nodeTree
		self.selectorNode = None
		
	@property
	def currentOutSocket(self):
		return self._currentOutSocket
	
	@currentOutSocket.setter
	def currentOutSocket(self,value):
		self._currentOutSocket = value
		self.nodeLoc = value.node.location
	
	def addMixLayer(self,colorOutSocket,alphaOutSocket,index):
		
		outNodeLoc = colorOutSocket.node.location
		if self.currentOutSocket == None:#For the first layer added, just store the out socket since it's not being mixed with anything
			self.currentOutSocket = colorOutSocket
			self.currentOutAlphaSocket = alphaOutSocket
			selectorNode = self.node_tree.nodes.new('ShaderNodeMath')
			selectorNode.operation = "ROUND"
			selectorNode.inputs[0].default_value = 0.0
			selectorNode.name = colorOutSocket.node.name.rsplit("_",1)[0]+"_SELECTOR"
			selectorNode.label = selectorNode.name
			selectorNode.location = (outNodeLoc[0]+600,outNodeLoc[1])
			self.selectorNode = selectorNode
		else:
			
			compareNode = self.node_tree.nodes.new('ShaderNodeMath')
			compareNode.operation = "COMPARE"
			
			self.node_tree.links.new(self.selectorNode.outputs["Value"],compareNode.inputs[0])
			compareNode.inputs[1].default_value = index#Compare value	
			compareNode.inputs[2].default_value = 0.5#Epsilon
			
			
			compareNode.location = (outNodeLoc[0],outNodeLoc[1]+300)
			
			mixNode = self.node_tree.nodes.new('ShaderNodeMixRGB')
			mixNode.location = (outNodeLoc[0],outNodeLoc[1]+600)
			
			self.node_tree.links.new(self.currentOutSocket,mixNode.inputs["Color1"])
			self.node_tree.links.new(colorOutSocket,mixNode.inputs["Color2"])
			self.node_tree.links.new(compareNode.outputs["Value"],mixNode.inputs["Fac"])
			self.currentOutSocket = mixNode.outputs["Color"]
			
			mixAlphaNode = self.node_tree.nodes.new('ShaderNodeMixRGB')
			mixAlphaNode.location = (outNodeLoc[0],outNodeLoc[1]+900)
			
			self.node_tree.links.new(self.currentOutAlphaSocket,mixAlphaNode.inputs["Color1"])
			self.node_tree.links.new(alphaOutSocket,mixAlphaNode.inputs["Color2"])
			self.node_tree.links.new(compareNode.outputs["Value"],mixAlphaNode.inputs["Fac"])
			self.currentOutAlphaSocket = mixAlphaNode.outputs["Color"]

missingTexTypeDict = {
	"ALBD":(1.0,0.0,0.0,1.0),
	"ALBM":(1.0,0.0,0.0,0.0),
	"ALB":(1.0,0.0,0.0,1.0),
	"ALP":(1.0,1.0,1.0,1.0),
	"ALBA":(1.0,0.0,0.0,1.0),
	"NRMR":(.502,.502,1.0,1.0),
	"NRRT":(.502,.502,1.0,.502),
	"NRRA":(.502,.502,1.0,.502),
	"NRRC":(.502,.502,1.0,.502),
	"NRRO":(.502,.502,1.0,.502),
	"NRRH":(.502,.502,1.0,.502),
	"ATOS":(1.0,0.0,1.0,1.0),
	"NULLATOS":(1.0,0.0,1.0,1.0),
	"NULLWHITE":(1.0,1.0,1.0,1.0),
	"NULLBLACK":(0.0,0.0,0.0,1.0),
	"ATOC":(1.0,0.0,1.0,1.0),
	"OCMA":(1.0,1.0,1.0,1.0),
	}
MHWILDS_MULTIBLEND_LIVE_PROPS = {"Blend_num","use_overlay","sRGB_Overlay","Use_MultiBlend_NRRO","Blend_Contrast","Blend_Alpha_Threshold","Use_EmitMask"} | {"Blend_"+channel for channel in "ABCDEFGH"}

MAX_ARRAY_IMPORT_SIZE = 16#Blender can't handle much more than 16 mix nodes into a color node, so it gets treated as a single image node if it exceeds 16
def addImageNode(nodeTree,textureType,imageList,texturePath,currentPos):
	#print(f"Loading {texturePath}")
	#print(len(imageList))
	colorSpace = "sRGB" if textureType in albedoTypeSet or textureType == "MultiBlend_ALBDMap" or "alb" in texturePath.rsplit("_",1)[-1].lower() else "Non-Color"
	
	if len(imageList) == 1 or len(imageList) > MAX_ARRAY_IMPORT_SIZE:
		imageNode = nodeTree.nodes.new('ShaderNodeTexImage')
		imageNode.name = textureType
		imageNode.label = textureType
		imageNode.location = currentPos
		
		if imageList[0] != None:
			imageNode.image = imageList[0]
			#print(f"image node {textureType} path:{imageList[0].filepath}")
			
		else:
			split = os.path.splitext(os.path.split(texturePath)[1])[0].rsplit("_",1)
			texType = split[1].upper() if len(split) > 1 else split[0].upper()
	
			if f"Missing {texType}" in bpy.data.images:
				imageNode.image = bpy.data.images[f"Missing {texType}"]
			else:
				
				imageNode.image = bpy.data.images.new(
					name = f"Missing {texType}",
					width = 1,
					height = 1,
					)
				#imageNode.image.pixels = missingTexTypeDict.get(texType,(0.0,0.0,0.0,1.0))
				imageNode.image.generated_color = missingTexTypeDict.get(texType,(1.0,1.0,1.0,1.0))
	
				imageNode.image.update()
				#print(f"Created \"Missing {textureType}\" texture.")
		imageNode.image.alpha_mode = "CHANNEL_PACKED"
		imageNode.image.colorspace_settings.name = colorSpace
			
	else:
		#Create image array selector
		imageNode = getImagePassThroughNodeGroup(nodeTree)
		imageNode.name = textureType
		imageNode.label = textureType
		imageNode.location = currentPos
		currentXPos = currentPos[0] - 300
		
		if "UVMap1Node" in nodeTree.nodes:
			UVMap1Node = nodeTree.nodes["UVMap1Node"]
			nodeTree.links.new(UVMap1Node.outputs["UV"],imageNode.inputs["Vector"])
		arrayGroup = dynamicArrayTextureSelectorNodeGroup(nodeTree)
		for index,image in enumerate(imageList):
			arrayImageNode = nodeTree.nodes.new('ShaderNodeTexImage')
			arrayImageNode.name = f"ARRAY_{textureType}_{index}"
			arrayImageNode.label = f"ARRAY_{textureType}_{index}"
			arrayImageNode.location = (currentXPos,currentPos[1])
			
			arrayImageNode.image = image
			arrayImageNode.image.colorspace_settings.name = colorSpace
			nodeTree.links.new(imageNode.outputs["Vector"],arrayImageNode.inputs["Vector"])
			arrayGroup.addMixLayer(arrayImageNode.outputs["Color"],arrayImageNode.outputs["Alpha"],index)
			currentXPos -= 300
		if arrayGroup.currentOutSocket != None:
			nodeTree.links.new(arrayGroup.currentOutSocket,imageNode.inputs["Color"])
			nodeTree.links.new(arrayGroup.currentOutAlphaSocket,imageNode.inputs["Alpha"])
		del arrayGroup
	return imageNode

def newALBDNode (nodeTree,textureType,matInfo):
	imageNode = nodeTree.nodes[textureType]
	currentPos = [imageNode.location[0]+300,imageNode.location[1]]
	
	
	#matInfo["albedoNodeLayerGroup"].addMixLayer(imageNode.outputs["Color"],factorOutSocket = None,mixType = "MIX",mixFactor = 0.0)
	matInfo["albedoNodeLayerGroup"].addMixLayer(imageNode.outputs["Color"])
	from .blender_mhwilds_skin import isMHWildsSkinEdit
	#SkinEdit uses BaseDielectric.A only for palette tint; its static base is nonmetallic.
	if not isMHWildsSkinEdit(matInfo):
		matInfo["metallicNodeLayerGroup"].addMixLayer(imageNode.outputs["Alpha"])
	matInfo["isDielectric"] = True
	
	return imageNode



def newALBMNode (nodeTree,textureType,matInfo):
	imageNode = nodeTree.nodes[textureType]
	currentPos = [imageNode.location[0]+300,imageNode.location[1]]
	matInfo["albedoNodeLayerGroup"].addMixLayer(imageNode.outputs["Color"])
	matInfo["metallicNodeLayerGroup"].addMixLayer(imageNode.outputs["Alpha"])
	
	return imageNode
def newALBANode (nodeTree,textureType,matInfo):
	imageNode = nodeTree.nodes[textureType]
	currentPos = [imageNode.location[0]+300,imageNode.location[1]]
	
	matInfo["albedoNodeLayerGroup"].addMixLayer(imageNode.outputs["Color"],factorOutSocket = None,mixType = "MIX",mixFactor = 0.5)

	matInfo["alphaSocket"] = imageNode.outputs["Alpha"]
	if matInfo["gameName"] == "MHWILDS":
		matInfo["mhWildsRawAlphaSource"] = imageNode.outputs["Alpha"]
	return imageNode
def newALBNode (nodeTree,textureType,matInfo):
	imageNode = nodeTree.nodes[textureType]
	currentPos = [imageNode.location[0]+300,imageNode.location[1]]
	
	matInfo["albedoNodeLayerGroup"].addMixLayer(imageNode.outputs["Color"])
	
	return imageNode
def newNRMRNode (nodeTree,textureType,matInfo):
	imageNode = nodeTree.nodes[textureType]
	currentPos = [imageNode.location[0]+300,imageNode.location[1]]
	
	matInfo["normalNodeLayerGroup"].addMixLayer(imageNode.outputs["Color"])
	matInfo["roughnessNodeLayerGroup"].addMixLayer(imageNode.outputs["Alpha"])
	return imageNode
def newNRMNode (nodeTree,textureType,matInfo):
	imageNode = nodeTree.nodes[textureType]
	currentPos = [imageNode.location[0]+300,imageNode.location[1]]
	
	matInfo["normalNodeLayerGroup"].addMixLayer(imageNode.outputs["Color"])
	return imageNode
def newNAMNode (nodeTree,textureType,matInfo):
	imageNode = nodeTree.nodes[textureType]
	currentPos = [imageNode.location[0]-300,imageNode.location[1]]
	
	separateRGBNode = nodeTree.nodes.new("ShaderNodeSeparateColor")
	separateRGBNode.location = currentPos
	nodeTree.links.new(imageNode.outputs["Color"],separateRGBNode.inputs["Color"])
	
	currentPos[0] += 300
	
	combineRGBNode = nodeTree.nodes.new("ShaderNodeCombineColor")
	combineRGBNode.location = currentPos
	nodeTree.links.new(separateRGBNode.outputs["Red"],combineRGBNode.inputs["Red"])
	nodeTree.links.new(separateRGBNode.outputs["Green"],combineRGBNode.inputs["Green"])
	
	
	
	combineRGBNode.inputs["Blue"].default_value = 1.0
	matInfo["normalNodeLayerGroup"].addMixLayer(combineRGBNode.outputs["Color"])
	
	if textureType == "StitchMap":
		if matInfo["gameName"] != "SF6":
			matInfo["alphaSocket"] = separateRGBNode.outputs["Blue"]
			matInfo["isAlphaBlend"] = True
	else:
		matInfo["alphaSocket"] = imageNode.outputs["Alpha"]
	if bpy.app.version < (4,2,0):
		matInfo["blenderMaterial"].shadow_method = "NONE"
	
	if "Stitch_Color" in matInfo["mPropDict"]:
		stitchColorNode = addPropertyNode(matInfo["mPropDict"]["Stitch_Color"], matInfo["currentPropPos"], nodeTree)
		
		matInfo["albedoNodeLayerGroup"].addMixLayer(stitchColorNode.outputs["Color"])
	
	if "Stitch_Scale" in matInfo["mPropDict"]:
		stitchScaleNode = addPropertyNode(matInfo["mPropDict"]["Stitch_Scale"], matInfo["currentPropPos"], nodeTree)
		if "UVMap1Node" in nodeTree.nodes:
			UVMap0Node = nodeTree.nodes["UVMap1Node"]
		else:
			UVMap0Node = nodeTree.nodes.new("ShaderNodeUVMap")
			UVMap0Node.name = "UVMap1Node"
			UVMap0Node.location = (currentPos[0]-300,currentPos[1]+300)
			UVMap0Node.uv_map = "UVMap0"
		
		mappingNode = nodeTree.nodes.new("ShaderNodeMapping")
		mappingNode.location = currentPos
		nodeTree.links.new(stitchScaleNode.outputs["Value"],mappingNode.inputs["Scale"])
		nodeTree.links.new(UVMap0Node.outputs["UV"],mappingNode.inputs["Vector"])
		
		combineNode = nodeTree.nodes.new("ShaderNodeCombineXYZ")
		combineNode.location = (currentPos[0]-300,currentPos[1])
		if "Stitch_U_offset" in matInfo["mPropDict"]:
			u_offsetNode = addPropertyNode(matInfo["mPropDict"]["Stitch_U_offset"], matInfo["currentPropPos"], nodeTree)
			
			nodeTree.links.new(u_offsetNode.outputs["Value"],combineNode.inputs["X"])
		
		if "Stitch_V_offset" in matInfo["mPropDict"]:
			v_offsetNode = addPropertyNode(matInfo["mPropDict"]["Stitch_V_offset"], matInfo["currentPropPos"], nodeTree)
			
			nodeTree.links.new(v_offsetNode.outputs["Value"],combineNode.inputs["Y"])
		
		nodeTree.links.new(combineNode.outputs["Vector"],mappingNode.inputs["Location"])
		nodeTree.links.new(mappingNode.outputs["Vector"],imageNode.inputs["Vector"])
	
	if "Stitch_Brightness" in matInfo["mPropDict"]:#TODO Fix, the brightness and contrast node isn't right
		brightConstrastNode = nodeTree.nodes.new("ShaderNodeBrightContrast")
		brightConstrastNode.location = (matInfo["albedoNodeLayerGroup"].nodeLoc[0]+200,matInfo["albedoNodeLayerGroup"].nodeLoc[1] - 200)
		stitchBrightnessNode = addPropertyNode(matInfo["mPropDict"]["Stitch_Brightness"], matInfo["currentPropPos"], nodeTree)
		brightnessAdjustNode = nodeTree.nodes.new("ShaderNodeMath")
		brightnessAdjustNode.location = addLoc(stitchBrightnessNode,(300,0))
		brightnessAdjustNode.operation = "ADD"
		nodeTree.links.new(stitchBrightnessNode.outputs["Value"],brightnessAdjustNode.inputs[0])
		brightnessAdjustNode.inputs[1].default_value = 0.0
		stitchConstrastNode = addPropertyNode(matInfo["mPropDict"]["Stitch_Contrast"], matInfo["currentPropPos"], nodeTree)
		contrastAdjustNode = nodeTree.nodes.new("ShaderNodeMath")
		contrastAdjustNode.location = addLoc(stitchConstrastNode,(300,0))
		contrastAdjustNode.operation = "ADD"
		nodeTree.links.new(stitchConstrastNode.outputs["Value"],contrastAdjustNode.inputs[0])
		brightnessAdjustNode.inputs[1].default_value = 0.0
		
		
		nodeTree.links.new(brightnessAdjustNode.outputs["Value"],brightConstrastNode.inputs["Bright"])
		nodeTree.links.new(contrastAdjustNode.outputs["Value"],brightConstrastNode.inputs["Contrast"])
		nodeTree.links.new(separateRGBNode.outputs["Blue"],brightConstrastNode.inputs["Color"])
		matInfo["albedoNodeLayerGroup"].addMixLayer(brightConstrastNode.outputs["Color"],mixType = "MULTIPLY",mixFactor = 1.0)
		#matInfo["albedoNodeLayerGroup"].currentOutSocket = brightConstrastNode.outputs["Color"]
	if "Stitch_Normal_Rate" in matInfo["mPropDict"]:
		stitchNormalRateNode = addPropertyNode(matInfo["mPropDict"]["Stitch_Normal_Rate"], matInfo["currentPropPos"], nodeTree)
		matInfo["normalNodeLayerGroup"].addMixLayer(stitchNormalRateNode.outputs["Value"],mixType = "MULTIPLY",mixFactor = 1.0)
	return imageNode
def newNRRTNode (nodeTree,textureType,matInfo):
	imageNode = nodeTree.nodes[textureType]
	currentPos = [imageNode.location[0]+300,imageNode.location[1]]
	
	if matInfo["gameName"] == "MHWILDS" and textureType == "NormalRoughnessOcclusionMap":
		nodeGroupNode = getMHWildsNRRONodeGroup(nodeTree)
	else:
		nodeGroupNode = getBentNormalNodeGroup(nodeTree)
	nodeGroupNode.location = currentPos
	nodeTree.links.new(imageNode.outputs["Color"],nodeGroupNode.inputs["Color"])
	nodeTree.links.new(imageNode.outputs["Alpha"],nodeGroupNode.inputs["Alpha"])
	matInfo["normalNodeLayerGroup"].addMixLayer(nodeGroupNode.outputs["Color"])
	matInfo["roughnessNodeLayerGroup"].addMixLayer(nodeGroupNode.outputs["Roughness"])
	
	
	if textureType == "NormalRoughnessCavityMap":
		matInfo["cavityNodeLayerGroup"].addMixLayer(nodeGroupNode.outputs["BlueChannel"])
		
	elif textureType == "NormalRoughnessOcclusionMap":
		if matInfo["gameName"] == "MHWILDS":
			addMHWildsAOTextureNodes(nodeTree,matInfo,textureType)
		else:
			matInfo["aoNodeLayerGroup"].addMixLayer(nodeGroupNode.outputs["BlueChannel"])
	elif textureType == "NormalRoughnessAlphaMap":
		matInfo["alphaSocket"] = nodeGroupNode.outputs["BlueChannel"]
	elif textureType == "NormalRoughnessHeightMap":
		pass
		#TODO Add height map support
	else:
		matInfo["translucentSocket"] = nodeGroupNode.outputs["BlueChannel"]
		
	return imageNode
	
def newALPNode (nodeTree,textureType,matInfo):
	imageNode = nodeTree.nodes[textureType]
	currentPos = [imageNode.location[0]+300,imageNode.location[1]]
	
	
	bwNode = nodeTree.nodes.new('ShaderNodeRGBToBW')
	bwNode.location = currentPos
	nodeTree.links.new(imageNode.outputs["Color"],bwNode.inputs["Color"])
	matInfo["alphaSocket"] = bwNode.outputs["Val"]
	return imageNode

EMISSION_MULTIPLIER = 0.1#Multiply strength by this value,way too bright by default

def hasLoadedImage(matInfo,textureType):#Missing textures get a white placeholder, which would wash the whole surface out
	node = matInfo["textureNodeDict"].get(textureType)
	if node == None:
		return False
	return not (hasattr(node,"image") and (node.image == None or node.image.name.startswith("Missing ")))

def linkMHWildsProp(nodeTree,matInfo,propName,socket,default = None,output = None):
	#Feeds an MDF property into socket through a property node named after it, so editing the property in the MDF material panel updates the preview live
	#output: None = first output, "Color"/"Alpha" for color properties, an index for Vec4 components
	props = matInfo["mPropDict"]
	if propName not in props:
		if default != None:
			socket.default_value = default
		return None
	propNode = addPropertyNode(props[propName], matInfo["currentPropPos"], nodeTree)
	if output == None:
		outSocket = propNode.outputs[0]
	elif isinstance(output,int):
		outSocket = propNode.outputs[output] if len(propNode.outputs) > output else propNode.outputs[0]
	else:
		outSocket = propNode.outputs[output] if output in propNode.outputs else propNode.outputs[0]
	nodeTree.links.new(outSocket,socket)
	return propNode

#MDF properties the MH Wilds preview feeds through property nodes, editing them in the MDF material panel updates the nodes live
MHWILDS_LIVE_PROPS = set(["ChangeUV","UseAOSecondaryUV","OcclusionParam","AlphaAdjust","AlphaTest_Ref","UseTempDither","useOPM","ModulateColor","ColorLayer_DetailMask_Tile","ColorLayer_DetailMask_Blend","Film_Thickness","Film_IOR","Film_Blend",
	"UseBaseColorFilm","FullFIlm","NormalBlendParam","VectorEmit_power","ParallaxEmit_Height","ParallaxEmit_Blend","MoveEmit","MoveEmit_Width","Use_WaveMove",
	"AnimEmit_Min","AnimEmit_Speed","UseWaveEmit","AnimEmitWave","SecEmit_Anim_Min","SecEmit_Anim_Speed","SecEmit_Anim_UseWaveEmit","SecEmit_Anim_Wave",
	"SecondaryEmitColor","AddColorUV","ToonEmissiveIntensity","FakeHighLight_Position","FakeHighLight_ScaleOffset","FakeHighLight_Color",
	"FakeRefraction_Blend","Refraction_Index","UseOverRay_ColorLayer","ColorLayer_Mask_Width","ColorLayer_Mask_Fade","ColorLayer_Roughness"])
MHWILDS_LIVE_PROPS.update(MHWILDS_MULTIBLEND_LIVE_PROPS)
from .blender_mhwilds_fur import FUR_PROPS
MHWILDS_LIVE_PROPS.update(FUR_PROPS)
from .blender_mhwilds_hair import HAIR_LIVE_PROPS
MHWILDS_LIVE_PROPS.update(HAIR_LIVE_PROPS)
MHWILDS_LIVE_PROPS.update({"ParallaxEmit_Blur","UV_Secondary_Blend","Use_SecodaryUV_DetailMask","UseAOSecondaryUV",
	"Use_Basecolor_to_Emissive","Use_Basecolor_Mask","Basecolor_Mask_Min","Basecolor_Mask_Max","UV_Tile","UV_Tile_Offset","RoughTransparent_Color",
	"Use_AntiTranslucent_Diffuse","TranslucentParam","Use_RimTranslucent","RimTranslucent_NormalBlend","RimTrasnlucent_Power"})
MHWILDS_LIVE_PROPS.update({"AddColorUV","SSSParam","SSSProfile"})
for _channel in ("R","G","B","A"):
	MHWILDS_LIVE_PROPS.update([f"ColorLayer_{_channel}",f"Use_{_channel}",f"UseOpacity_{_channel}",f"PrevHeight_{_channel}",f"UseThrough_Normal_{_channel}",
		f"DetailAlphaRef_{_channel}",f"DetailAlphaWidth_{_channel}",f"Detail_Roughness_{_channel}",f"Detail_Metal_{_channel}",f"DetailNormal_{_channel}",
		f"Detail_Roughness_Blend_{_channel}",f"UseFlip_{_channel}",f"Detail_Color_{_channel}",f"DetailTile_{_channel}",f"UseUV_ScaleOffset_{_channel}",
		f"UV_ScaleOffset_{_channel}",f"BaseNormal_Blend_{_channel}"])

def getMHWildsPanoramaUVNodeGroup(nodeTree):
	#PanoramaMap fake refraction lookup, from BaseAlpha_MatCap_FX PS #75 (DXIL %437..501), same code in Base_Equip #63/#65
	#dir = normalize(cameraToSurface - Refraction_Index * N), u = frac(atan2(dir.z,dir.x)/(2*PI) + 0.5), v = acos(dir.y)/PI
	#dir is in RE space (Y up), meshes are imported rotated 90 on X so RE = (x, z, -y) of Blender
	if "MHWildsPanoramaUV" in bpy.data.node_groups:
		nodeGroup = bpy.data.node_groups["MHWildsPanoramaUV"]
	else:
		nodeGroup = bpy.data.node_groups.new(type="ShaderNodeTree", name="MHWildsPanoramaUV")
		for name,socketType,inOut in (("Normal","NodeSocketVector","INPUT"),("Refraction_Index","NodeSocketFloat","INPUT"),("Vector","NodeSocketVector","OUTPUT")):
			if bpy.app.version < (4,0,0):
				(nodeGroup.inputs if inOut == "INPUT" else nodeGroup.outputs).new(socketType,name)
			else:
				nodeGroup.interface.new_socket(name=name,description="",in_out = inOut, socket_type=socketType)
		nodes = nodeGroup.nodes
		links = nodeGroup.links
		def mathNode(operation,a,b,loc,c = None):
			node = nodes.new("ShaderNodeMath")
			node.operation = operation
			node.location = loc
			for index,value in enumerate((a,b) if c == None else (a,b,c)):
				if isinstance(value,(int,float)):
					node.inputs[index].default_value = value
				else:
					links.new(value,node.inputs[index])
			return node.outputs["Value"]
		def vectorNode(operation,a,b,loc):
			node = nodes.new("ShaderNodeVectorMath")
			node.operation = operation
			node.location = loc
			links.new(a,node.inputs[0])
			if b != None:
				target = node.inputs["Scale"] if operation == "SCALE" else node.inputs[1]
				if isinstance(b,(int,float)):
					target.default_value = b
				else:
					links.new(b,target)
			return node.outputs["Vector"]

		inNode = nodes.new('NodeGroupInput')
		inNode.location = (-400,0)
		geometryNode = nodes.new("ShaderNodeNewGeometry")
		geometryNode.location = (-400,300)
		#Incoming points from the surface to the camera
		cameraToSurface = vectorNode("SCALE",geometryNode.outputs["Incoming"],-1.0,(-200,300))
		normalOffset = vectorNode("SCALE",inNode.outputs["Normal"],mathNode("MULTIPLY",inNode.outputs["Refraction_Index"],-1.0,(-200,0)),(0,0))
		direction = vectorNode("NORMALIZE",vectorNode("ADD",cameraToSurface,normalOffset,(200,200)),None,(400,200))
		sepNode = nodes.new("ShaderNodeSeparateXYZ")
		sepNode.location = (600,200)
		links.new(direction,sepNode.inputs["Vector"])
		#RE x = X, RE y = Z, RE z = -Y
		reZ = mathNode("MULTIPLY",sepNode.outputs["Y"],-1.0,(800,300))
		angle = mathNode("ARCTAN2",reZ,sepNode.outputs["X"],(1000,300))
		u = mathNode("FRACT",mathNode("MULTIPLY_ADD",angle,1.0/(2.0*pi),(1200,300),0.5),0.0,(1400,300))
		v = mathNode("DIVIDE",mathNode("ARCCOSINE",sepNode.outputs["Z"],0.0,(1000,100)),pi,(1200,100))
		#D3D V to Blender V
		v = mathNode("SUBTRACT",1.0,v,(1400,100))
		combineNode = nodes.new("ShaderNodeCombineXYZ")
		combineNode.location = (1600,200)
		links.new(u,combineNode.inputs["X"])
		links.new(v,combineNode.inputs["Y"])
		outNode = nodes.new('NodeGroupOutput')
		outNode.location = (1800,200)
		links.new(combineNode.outputs["Vector"],outNode.inputs["Vector"])
	nodeGroupNode = nodeTree.nodes.new("ShaderNodeGroup")
	nodeGroupNode.node_tree = nodeGroup
	return nodeGroupNode

class ShaderGroupBuilder():
	#Small helper for building math heavy node groups
	def __init__(self,nodeGroup):
		self.nodes = nodeGroup.nodes
		self.links = nodeGroup.links
		self.x = 0
	def _set(self,socket,value):
		if isinstance(value,(int,float)):
			socket.default_value = value
		elif isinstance(value,tuple):
			socket.default_value = value
		else:
			self.links.new(value,socket)
	def math(self,operation,a,b = 0.0,c = None,clamp = False):
		node = self.nodes.new("ShaderNodeMath")
		node.operation = operation
		node.use_clamp = clamp
		node.location = (self.x,0)
		self.x += 20
		for index,value in enumerate((a,b) if c == None else (a,b,c)):
			self._set(node.inputs[index],value)
		return node.outputs["Value"]
	def lerp(self,a,b,t):#a + (b-a)*t
		return self.math("MULTIPLY_ADD",self.math("SUBTRACT",b,a),t,a)
	def smoothstep01(self,x):#x*x*(3-2x)
		return self.math("MULTIPLY",self.math("MULTIPLY",x,x),self.math("MULTIPLY_ADD",x,-2.0,3.0))
	def select(self,condition,ifTrue,ifFalse):#condition is 0 or 1
		return self.lerp(ifFalse,ifTrue,condition)
	def greater0(self,value):
		return self.math("GREATER_THAN",value,0.0)
	def separate(self,socket):
		node = self.nodes.new("ShaderNodeSeparateColor")
		node.location = (self.x,0)
		self._set(node.inputs["Color"],socket)
		return node.outputs
	def separateXYZ(self,socket):
		node = self.nodes.new("ShaderNodeSeparateXYZ")
		node.location = (self.x,0)
		self._set(node.inputs["Vector"],socket)
		return node.outputs
	def combineXYZ(self,x,y,z):
		node = self.nodes.new("ShaderNodeCombineXYZ")
		node.location = (self.x,0)
		for socket,value in zip(node.inputs,(x,y,z)):
			self._set(socket,value)
		return node.outputs["Vector"]
	def combineColor(self,r,g,b):
		node = self.nodes.new("ShaderNodeCombineColor")
		node.location = (self.x,0)
		for socket,value in zip(node.inputs,(r,g,b)):
			self._set(socket,value)
		return node.outputs["Color"]
	def normalize3(self,x,y,z):
		inv = self.math("INVERSE_SQRT",self.math("MULTIPLY_ADD",x,x,self.math("MULTIPLY_ADD",y,y,self.math("MULTIPLY",z,z))))
		return self.math("MULTIPLY",x,inv),self.math("MULTIPLY",y,inv),self.math("MULTIPLY",z,inv)

def newGroupSockets(nodeGroup,socketList,inOut):
	for name,socketType in socketList:
		if bpy.app.version < (4,0,0):
			(nodeGroup.inputs if inOut == "INPUT" else nodeGroup.outputs).new(socketType,name)
		else:
			nodeGroup.interface.new_socket(name=name,description="",in_out = inOut, socket_type=socketType)

def getMHWildsBaseAOUVNodeGroup(nodeTree):
	groupName = "MHWildsBaseAOUV_v1"
	if groupName in bpy.data.node_groups:
		nodeGroup = bpy.data.node_groups[groupName]
	else:
		nodeGroup = bpy.data.node_groups.new(type="ShaderNodeTree", name=groupName)
		newGroupSockets(nodeGroup,[("Primary UV","NodeSocketVector"),("Secondary UV","NodeSocketVector"),("ChangeUV","NodeSocketFloat"),("UseAOSecondaryUV","NodeSocketFloat")],"INPUT")
		newGroupSockets(nodeGroup,[("Base UV","NodeSocketVector"),("AO UV","NodeSocketVector")],"OUTPUT")
		b = ShaderGroupBuilder(nodeGroup)
		i = b.nodes.new('NodeGroupInput').outputs
		primary,secondary = b.separateXYZ(i["Primary UV"]),b.separateXYZ(i["Secondary UV"])
		change,aoSecondary = b.greater0(i["ChangeUV"]),b.greater0(i["UseAOSecondaryUV"])
		base = [b.select(change,secondary[c],primary[c]) for c in ("X","Y","Z")]
		ao = [b.select(aoSecondary,secondary[c],base[index]) for index,c in enumerate(("X","Y","Z"))]
		out = b.nodes.new('NodeGroupOutput')
		b.links.new(b.combineXYZ(*base),out.inputs["Base UV"])
		b.links.new(b.combineXYZ(*ao),out.inputs["AO UV"])
	node = nodeTree.nodes.new("ShaderNodeGroup")
	node.node_tree = nodeGroup
	return node

def getMHWildsBaseAOUVNode(nodeTree,matInfo):
	if "MHWildsBaseAOUV" in nodeTree.nodes:
		return nodeTree.nodes["MHWildsBaseAOUV"]
	node = getMHWildsBaseAOUVNodeGroup(nodeTree)
	node.name = "MHWildsBaseAOUV"
	node.location = (-1300,1000)
	primary = nodeTree.nodes.get("UVMap1Node")
	secondary = nodeTree.nodes.get("UVMap2Node") or primary
	if primary != None:
		nodeTree.links.new(primary.outputs["UV"],node.inputs["Primary UV"])
	if secondary != None:
		nodeTree.links.new(secondary.outputs["UV"],node.inputs["Secondary UV"])
	for name in ("ChangeUV","UseAOSecondaryUV"):
		linkMHWildsProp(nodeTree,matInfo,name,node.inputs[name],0.0)
	return node

def addMHWildsBaseUVNodes(nodeTree,matInfo):
	if matInfo["gameName"] != "MHWILDS":
		return
	uv = getMHWildsBaseAOUVNode(nodeTree,matInfo)
	#These standard slots share ChangeUV in the traced Wilds shaders.
	#Detail, SkinMap, BlendNormal, eye height and effect UVs have separate policies.
	for name in ("BaseDielectricMap","BaseAlphaMap","NormalRoughnessOcclusionMap","AlphaTranslucentOcclusionSSSMap"):
		image = matInfo["textureNodeDict"].get(name)
		if image != None:
			nodeTree.links.new(uv.outputs["Base UV"],image.inputs["Vector"])

def addMHWildsAOTextureNodes(nodeTree,matInfo,textureType):
	#Only AO gets the alternate UV. Never rewire the normal/roughness/alpha sample.
	source = matInfo.get("textureNodeDict",{}).get(textureType) or nodeTree.nodes[textureType]
	uv = getMHWildsBaseAOUVNode(nodeTree,matInfo)
	nodeTree.links.new(uv.outputs["Base UV"],source.inputs["Vector"])
	def sample(image,name):
		copy = nodeTree.nodes.new("ShaderNodeTexImage")
		copy.name = name
		copy.image = image.image
		for attr in ("extension","interpolation","projection","projection_blend"):
			setattr(copy,attr,getattr(image,attr))
		copy.location = image.location + Vector((0,-350))
		nodeTree.links.new(uv.outputs["AO UV"],copy.inputs["Vector"])
		return copy
	if source.bl_idname == "ShaderNodeTexImage":
		aoImage = sample(source,"AO_"+textureType)
		color = aoImage.outputs["Color"]
	else:
		#Array sources are pass-through groups; duplicate only their image samples.
		prefix = "ARRAY_"+textureType+"_"
		images = sorted((n for n in nodeTree.nodes if n.bl_idname == "ShaderNodeTexImage" and n.name.startswith(prefix) and n.name[len(prefix):].isdigit()),key = lambda n:int(n.name[len(prefix):]))
		if not images:
			return
		array = dynamicArrayTextureSelectorNodeGroup(nodeTree)
		for image in images:
			index = int(image.name[len(prefix):])
			copy = sample(image,"AO_"+image.name)
			array.addMixLayer(copy.outputs["Color"],copy.outputs["Alpha"],index)
		selector = nodeTree.nodes.get(prefix+"SELECTOR")
		if selector != None:
			nodeTree.links.new(selector.outputs["Value"],array.selectorNode.inputs[0])
		color = array.currentOutSocket
	separate = nodeTree.nodes.new("ShaderNodeSeparateColor")
	nodeTree.links.new(color,separate.inputs["Color"])
	matInfo.setdefault("mhWildsAOSockets",[]).append(separate.outputs["Blue"])

def addMHWildsAONodes(nodeTree,matInfo):
	sources = matInfo.get("mhWildsAOSockets",[])
	if matInfo["gameName"] != "MHWILDS" or not sources:
		return
	ao = sources[0]
	for source in sources[1:]:
		minimum = nodeTree.nodes.new("ShaderNodeMath")
		minimum.operation = "MINIMUM"
		nodeTree.links.new(ao,minimum.inputs[0])
		nodeTree.links.new(source,minimum.inputs[1])
		ao = minimum.outputs["Value"]
	#Wilds: 1 - OcclusionParam * (1 - min(NRRO.B, ATOS.B)). No extra clamp.
	invert = nodeTree.nodes.new("ShaderNodeMath")
	invert.operation = "SUBTRACT"
	invert.inputs[0].default_value = 1.0
	nodeTree.links.new(ao,invert.inputs[1])
	strength = nodeTree.nodes.new("ShaderNodeMath")
	strength.operation = "MULTIPLY"
	nodeTree.links.new(invert.outputs["Value"],strength.inputs[0])
	linkMHWildsProp(nodeTree,matInfo,"OcclusionParam",strength.inputs[1],1.0)
	result = nodeTree.nodes.new("ShaderNodeMath")
	result.name = "MHWildsOcclusion"
	result.operation = "SUBTRACT"
	result.inputs[0].default_value = 1.0
	nodeTree.links.new(strength.outputs["Value"],result.inputs[1])
	matInfo["aoNodeLayerGroup"].addMixLayer(result.outputs["Value"],mixType = "MULTIPLY",mixFactor = 1.0)

def getMHWildsAlphaAdjustNodeGroup(nodeTree):
	groupName = "MHWildsAlphaAdjust_v1"
	if groupName in bpy.data.node_groups:
		nodeGroup = bpy.data.node_groups[groupName]
	else:
		nodeGroup = bpy.data.node_groups.new(type="ShaderNodeTree", name=groupName)
		newGroupSockets(nodeGroup,[("Alpha","NodeSocketFloat"),("AlphaAdjust","NodeSocketFloat")],"INPUT")
		newGroupSockets(nodeGroup,[("Value","NodeSocketFloat")],"OUTPUT")
		b = ShaderGroupBuilder(nodeGroup)
		i = b.nodes.new('NodeGroupInput').outputs
		low = b.math("MULTIPLY_ADD",i["Alpha"],2.0,-1.0,clamp = True)
		high = b.math("MULTIPLY",i["Alpha"],2.0,clamp = True)
		out = b.nodes.new('NodeGroupOutput')
		b.links.new(b.lerp(low,high,i["AlphaAdjust"]),out.inputs["Value"])
	node = nodeTree.nodes.new("ShaderNodeGroup")
	node.node_tree = nodeGroup
	return node

#Masters whose pixel shaders declare AlphaAdjust but never read it (.240906211 #64/#65)
MHWILDS_ALPHA_ADJUST_UNUSED = {"base_eye_emit.mmtr","base_eyerefract_emit.mmtr","base_gold_push.mmtr"}

def addMHWildsAlphaAdjustNodes(nodeTree,matInfo):
	if matInfo["gameName"] != "MHWILDS" or "AlphaAdjust" not in matInfo["mPropDict"] or matInfo["mmtrName"] in MHWILDS_ALPHA_ADJUST_UNUSED:
		return
	alpha = matInfo.get("mhWildsRawAlphaSource")
	if alpha == None or matInfo["alphaSocket"] != alpha:
		return
	node = getMHWildsAlphaAdjustNodeGroup(nodeTree)
	node.name = "MHWildsAlphaAdjust"
	nodeTree.links.new(alpha,node.inputs["Alpha"])
	linkMHWildsProp(nodeTree,matInfo,"AlphaAdjust",node.inputs["AlphaAdjust"],0.0)
	matInfo["alphaSocket"] = node.outputs["Value"]

def getMHWildsAlphaCoverageNodeGroup(nodeTree):
	groupName = "MHWildsAlphaCoverage_v1"
	if groupName in bpy.data.node_groups:
		nodeGroup = bpy.data.node_groups[groupName]
	else:
		nodeGroup = bpy.data.node_groups.new(type="ShaderNodeTree", name=groupName)
		newGroupSockets(nodeGroup,[("Alpha","NodeSocketFloat"),("AlphaTest_Ref","NodeSocketFloat"),("UseTempDither","NodeSocketFloat")],"INPUT")
		newGroupSockets(nodeGroup,[("Value","NodeSocketFloat")],"OUTPUT")
		b = ShaderGroupBuilder(nodeGroup)
		i = b.nodes.new('NodeGroupInput').outputs
		#The shader rejects alpha < ref, so equality must remain visible.
		cutout = b.math("SUBTRACT",1.0,b.math("LESS_THAN",i["Alpha"],i["AlphaTest_Ref"]))
		#Continuous coverage is a preview approximation of REE noise/TAA, not its history.
		coverage = b.math("MULTIPLY",i["Alpha"],1.0,clamp = True)
		out = b.nodes.new('NodeGroupOutput')
		b.links.new(b.select(b.greater0(i["UseTempDither"]),coverage,cutout),out.inputs["Value"])
	node = nodeTree.nodes.new("ShaderNodeGroup")
	node.node_tree = nodeGroup
	return node

def addMHWildsAlphaCoverageNodes(nodeTree,matInfo):
	if matInfo["gameName"] != "MHWILDS" or "AlphaTest_Ref" not in matInfo["mPropDict"] or matInfo["isAlphaBlend"]:
		return None
	#Preserve existing continuous/forward profiles; their forward shaders need not test alpha.
	if any(name in matInfo["mmtrName"] for name in ("reflectivetransparent","roughtransparent","alphadissolve","decal_basealpha","basealpha_matcap_fx")):
		return None
	node = getMHWildsAlphaCoverageNodeGroup(nodeTree)
	node.name = "MHWildsAlphaCoverage"
	node.label = "Alpha test / temporal coverage approximation"
	nodeTree.links.new(matInfo["alphaSocket"],node.inputs["Alpha"])
	for name in ("AlphaTest_Ref","UseTempDither"):
		linkMHWildsProp(nodeTree,matInfo,name,node.inputs[name],0.0)
	return node


def getMHWildsDetailUVNodeGroup(nodeTree):
	#Detail layer UV, from Base_Equip / VFXwe PS #63: uv = (UseFlip ? uv0.yx : uv0) * DetailTile, then * UV_ScaleOffset.xy + .zw when UseUV_ScaleOffset
	#Done in D3D UV space (V down), Blender V = 1 - D3D V
	if "MHWildsDetailUV" in bpy.data.node_groups:
		nodeGroup = bpy.data.node_groups["MHWildsDetailUV"]
	else:
		nodeGroup = bpy.data.node_groups.new(type="ShaderNodeTree", name="MHWildsDetailUV")
		newGroupSockets(nodeGroup,[("UV","NodeSocketVector"),("DetailTile","NodeSocketFloat"),("UseFlip","NodeSocketFloat"),("UseUV_ScaleOffset","NodeSocketFloat"),
			("ScaleX","NodeSocketFloat"),("ScaleY","NodeSocketFloat"),("OffsetX","NodeSocketFloat"),("OffsetY","NodeSocketFloat")],"INPUT")
		newGroupSockets(nodeGroup,[("Vector","NodeSocketVector")],"OUTPUT")
		b = ShaderGroupBuilder(nodeGroup)
		inNode = b.nodes.new('NodeGroupInput')
		i = inNode.outputs
		uv = b.separateXYZ(i["UV"])
		u = uv["X"]
		v = b.math("SUBTRACT",1.0,uv["Y"])
		flip = b.greater0(i["UseFlip"])
		u,v = b.select(flip,v,u),b.select(flip,u,v)
		u = b.math("MULTIPLY",u,i["DetailTile"])
		v = b.math("MULTIPLY",v,i["DetailTile"])
		useScaleOffset = b.greater0(i["UseUV_ScaleOffset"])
		u = b.select(useScaleOffset,b.math("MULTIPLY_ADD",u,i["ScaleX"],i["OffsetX"]),u)
		v = b.select(useScaleOffset,b.math("MULTIPLY_ADD",v,i["ScaleY"],i["OffsetY"]),v)
		outNode = b.nodes.new('NodeGroupOutput')
		outNode.location = (b.x + 200,0)
		b.links.new(b.combineXYZ(u,b.math("SUBTRACT",1.0,v),0.0),outNode.inputs["Vector"])
	nodeGroupNode = nodeTree.nodes.new("ShaderNodeGroup")
	nodeGroupNode.node_tree = nodeGroup
	return nodeGroupNode

def getMHWildsDetailLayerNodeGroup(nodeTree):
	#One Detail_ALBD/NRRH layer, from VFXwe PS #63 (DXIL %565..%687 for R, %764..%956 for G), same code in Base_Equip PS #63
	#mask = Use ? DetailMaskMap.c : 0
	#heightOpacity = PrevHeight > 0 ? saturate(NRRH.B - saturate(prevAccHeight - 1 + 2*PrevHeight)) : NRRH.B, opacity = UseOpacity ? heightOpacity : 1
	#t = AlphaWidth - (AlphaWidth+1)*(1-AlphaRef), w = AlphaWidth == 0 ? 1e-4 : AlphaWidth
	#m = useOPM ? smoothstep(saturate(saturate(t + opacity*mask)/w)) : smoothstep(saturate(saturate(t + opacity)/w)) * mask
	#color = lerp(prev, (2*Detail_Color.rgb*sqrt(ALBD.rgb))^2, Detail_Color.a*m)
	#roughness = lerp(prev, 2*NRRH.R*Detail_Roughness, Detail_Roughness_Blend*m), metal = lerp(prev, 2*(1-ALBD.A)*Detail_Metal, m)
	#normal: octahedral NRRH.GA, UseFlip maps xy to (-y,-x), n = normalize(start.xy + 2*DetailNormal*xy, start.z) with start = UseThrough_Normal ? prev : (0,0,1), normal = lerp(prev, n, m)
	#accumulated height = lerp(prevAccHeight, NRRH.B, m)
	if "MHWildsDetailLayer" in bpy.data.node_groups:
		nodeGroup = bpy.data.node_groups["MHWildsDetailLayer"]
	else:
		nodeGroup = bpy.data.node_groups.new(type="ShaderNodeTree", name="MHWildsDetailLayer")
		floatInputs = ["Prev Roughness","Prev Metal","Prev Height","ALBD Alpha","NRRH Alpha","Mask","Use","UseOpacity","PrevHeight","UseThrough_Normal","useOPM",
			"DetailAlphaRef","DetailAlphaWidth","Detail_Color Alpha","Detail_Roughness","Detail_Metal","DetailNormal","Detail_Roughness_Blend","UseFlip"]
		newGroupSockets(nodeGroup,[("Prev Color","NodeSocketColor"),("Prev Normal","NodeSocketVector"),("ALBD","NodeSocketColor"),("NRRH","NodeSocketColor"),("Detail_Color","NodeSocketColor")]
			+ [(name,"NodeSocketFloat") for name in floatInputs],"INPUT")
		newGroupSockets(nodeGroup,[("Color","NodeSocketColor"),("Roughness","NodeSocketFloat"),("Metal","NodeSocketFloat"),("Normal","NodeSocketVector"),
			("Height","NodeSocketFloat"),("Weight","NodeSocketFloat")],"OUTPUT")
		b = ShaderGroupBuilder(nodeGroup)
		inNode = b.nodes.new('NodeGroupInput')
		i = inNode.outputs
		nrrh = b.separate(i["NRRH"])
		height = nrrh["Blue"]
		mask = b.math("MULTIPLY",b.greater0(i["Use"]),i["Mask"])
		prevTerm = b.math("SUBTRACT",b.math("MULTIPLY_ADD",i["PrevHeight"],2.0,i["Prev Height"]),1.0,clamp = True)
		heightOpacity = b.select(b.greater0(i["PrevHeight"]),b.math("SUBTRACT",height,prevTerm,clamp = True),height)
		opacity = b.select(b.greater0(i["UseOpacity"]),heightOpacity,1.0)
		width = i["DetailAlphaWidth"]
		threshold = b.math("SUBTRACT",width,b.math("MULTIPLY",b.math("ADD",width,1.0),b.math("SUBTRACT",1.0,i["DetailAlphaRef"])))
		safeWidth = b.select(b.math("COMPARE",width,0.0,0.0),1.0e-4,width)
		opmWeight = b.smoothstep01(b.math("DIVIDE",b.math("MULTIPLY_ADD",opacity,mask,threshold,clamp = True),safeWidth,clamp = True))
		plainWeight = b.math("MULTIPLY",b.smoothstep01(b.math("DIVIDE",b.math("ADD",threshold,opacity,clamp = True),safeWidth,clamp = True)),mask)
		weight = b.select(b.greater0(i["useOPM"]),opmWeight,plainWeight)

		albd = b.separate(i["ALBD"])
		tint = b.separate(i["Detail_Color"])
		layerColor = []
		for channel in ("Red","Green","Blue"):
			value = b.math("MULTIPLY",b.math("MULTIPLY",tint[channel],2.0),b.math("SQRT",albd[channel]))
			layerColor.append(b.math("MULTIPLY",value,value))
		colorNode = b.nodes.new("ShaderNodeMixRGB")
		colorNode.location = (b.x,200)
		b.links.new(i["Prev Color"],colorNode.inputs["Color1"])
		b.links.new(b.combineColor(*layerColor),colorNode.inputs["Color2"])
		b.links.new(b.math("MULTIPLY",i["Detail_Color Alpha"],weight),colorNode.inputs["Fac"])
		roughness = b.lerp(i["Prev Roughness"],b.math("MULTIPLY",b.math("MULTIPLY",nrrh["Red"],2.0),i["Detail_Roughness"]),b.math("MULTIPLY",i["Detail_Roughness_Blend"],weight))
		metal = b.lerp(i["Prev Metal"],b.math("MULTIPLY",b.math("MULTIPLY",b.math("SUBTRACT",1.0,i["ALBD Alpha"]),2.0),i["Detail_Metal"]),weight)

		#Octahedral decode, a|a| style
		a = b.math("MULTIPLY_ADD",nrrh["Green"],2.0,-1.0)
		c = b.math("MULTIPLY_ADD",i["NRRH Alpha"],2.0,-1.0)
		a = b.math("MULTIPLY",a,b.math("ABSOLUTE",a))
		c = b.math("MULTIPLY",c,b.math("ABSOLUTE",c))
		x = b.math("MULTIPLY",b.math("ADD",a,c),0.5)
		y = b.math("MULTIPLY",b.math("SUBTRACT",a,c),0.5)
		z = b.math("SUBTRACT",b.math("SUBTRACT",1.0,b.math("ABSOLUTE",x)),b.math("ABSOLUTE",y))
		x,y,z = b.normalize3(x,y,z)
		flip = b.greater0(i["UseFlip"])
		x,y = b.select(flip,b.math("MULTIPLY",y,-1.0),x),b.select(flip,b.math("MULTIPLY",x,-1.0),y)
		strength = b.math("MULTIPLY",i["DetailNormal"],2.0)
		prev = b.separateXYZ(i["Prev Normal"])
		through = b.greater0(i["UseThrough_Normal"])
		nx,ny,nz = b.normalize3(b.math("MULTIPLY_ADD",x,strength,b.math("MULTIPLY",prev["X"],through)),
			b.math("MULTIPLY_ADD",y,strength,b.math("MULTIPLY",prev["Y"],through)),
			b.select(through,prev["Z"],1.0))
		normal = b.combineXYZ(b.lerp(prev["X"],nx,weight),b.lerp(prev["Y"],ny,weight),b.lerp(prev["Z"],nz,weight))
		accHeight = b.lerp(i["Prev Height"],height,weight)

		outNode = b.nodes.new('NodeGroupOutput')
		outNode.location = (b.x + 200,0)
		for name,socket in (("Color",colorNode.outputs["Color"]),("Roughness",roughness),("Metal",metal),("Normal",normal),("Height",accHeight),("Weight",weight)):
			b.links.new(socket,outNode.inputs[name])
	nodeGroupNode = nodeTree.nodes.new("ShaderNodeGroup")
	nodeGroupNode.node_tree = nodeGroup
	nodeGroupNode.inputs["Prev Normal"].default_value = (0.0,0.0,1.0)
	return nodeGroupNode

def getMHWildsDetailMergeNodeGroup(nodeTree):
	#After the R,G,B layers (VFXwe PS #63 %1232..%1288): w = max(mR,mG,mB,0)
	#ModulateColor: the R,G,B chain starts at 0.5 (color, roughness) and is applied as 2*base*result, metal starts at the base metal and gets the same 2*base* treatment
	#value = lerp(base, ModulateColor ? 2*base*layered : layered, w), the A layer then lerps on top of this without modulation
	if "MHWildsDetailMerge" in bpy.data.node_groups:
		nodeGroup = bpy.data.node_groups["MHWildsDetailMerge"]
	else:
		nodeGroup = bpy.data.node_groups.new(type="ShaderNodeTree", name="MHWildsDetailMerge")
		newGroupSockets(nodeGroup,[("Base Color","NodeSocketColor"),("Layer Color","NodeSocketColor"),("Base Roughness","NodeSocketFloat"),("Layer Roughness","NodeSocketFloat"),
			("Base Metal","NodeSocketFloat"),("Layer Metal","NodeSocketFloat"),("Weight R","NodeSocketFloat"),("Weight G","NodeSocketFloat"),("Weight B","NodeSocketFloat"),("ModulateColor","NodeSocketFloat")],"INPUT")
		newGroupSockets(nodeGroup,[("Color","NodeSocketColor"),("Roughness","NodeSocketFloat"),("Metal","NodeSocketFloat")],"OUTPUT")
		b = ShaderGroupBuilder(nodeGroup)
		inNode = b.nodes.new('NodeGroupInput')
		i = inNode.outputs
		weight = b.math("MAXIMUM",b.math("MAXIMUM",i["Weight R"],i["Weight G"]),b.math("MAXIMUM",i["Weight B"],0.0))
		modulate = b.greater0(i["ModulateColor"])
		base = b.separate(i["Base Color"])
		layer = b.separate(i["Layer Color"])
		color = [b.lerp(base[channel],b.select(modulate,b.math("MULTIPLY",b.math("MULTIPLY",base[channel],2.0),layer[channel]),layer[channel]),weight) for channel in ("Red","Green","Blue")]
		roughness = b.lerp(i["Base Roughness"],b.select(modulate,b.math("MULTIPLY",b.math("MULTIPLY",i["Base Roughness"],2.0),i["Layer Roughness"]),i["Layer Roughness"]),weight)
		metal = b.lerp(i["Base Metal"],b.select(modulate,b.math("MULTIPLY",b.math("MULTIPLY",i["Base Metal"],2.0),i["Layer Metal"]),i["Layer Metal"]),weight)
		outNode = b.nodes.new('NodeGroupOutput')
		outNode.location = (b.x + 200,0)
		b.links.new(b.combineColor(*color),outNode.inputs["Color"])
		b.links.new(roughness,outNode.inputs["Roughness"])
		b.links.new(metal,outNode.inputs["Metal"])
	nodeGroupNode = nodeTree.nodes.new("ShaderNodeGroup")
	nodeGroupNode.node_tree = nodeGroup
	return nodeGroupNode

def getMHWildsDetailNormalNodeGroup(nodeTree):
	#Detail normal on top of the base normal (VFXwe PS #63 %1612..%1675)
	#baseWeight = 1, then for R,G,B,A: baseWeight = lerp(baseWeight, max(BaseNormal_Blend_c, 1-Use_c), m_c)
	#b = normalize(baseWeight*base.xy, baseWeight*(base.z-1)+1), result = normalize(detail.xy + b.xy, b.z)
	#Tangent space normals come in and out as normal map colors
	if "MHWildsDetailNormal" in bpy.data.node_groups:
		nodeGroup = bpy.data.node_groups["MHWildsDetailNormal"]
	else:
		nodeGroup = bpy.data.node_groups.new(type="ShaderNodeTree", name="MHWildsDetailNormal")
		socketList = [("Base Normal Color","NodeSocketColor"),("Detail Normal","NodeSocketVector")]
		for channel in ("R","G","B","A"):
			socketList += [(f"BaseNormal_Blend_{channel}","NodeSocketFloat"),(f"Use_{channel}","NodeSocketFloat"),(f"Weight {channel}","NodeSocketFloat")]
		newGroupSockets(nodeGroup,socketList,"INPUT")
		newGroupSockets(nodeGroup,[("Color","NodeSocketColor")],"OUTPUT")
		b = ShaderGroupBuilder(nodeGroup)
		inNode = b.nodes.new('NodeGroupInput')
		i = inNode.outputs
		baseWeight = 1.0
		for channel in ("R","G","B","A"):
			target = b.math("MAXIMUM",i[f"BaseNormal_Blend_{channel}"],b.math("SUBTRACT",1.0,i[f"Use_{channel}"]))
			baseWeight = b.lerp(baseWeight,target,i[f"Weight {channel}"]) if not isinstance(baseWeight,float) else b.math("MULTIPLY_ADD",b.math("SUBTRACT",target,1.0),i[f"Weight {channel}"],1.0)
		base = b.separate(i["Base Normal Color"])
		bx = b.math("MULTIPLY_ADD",base["Red"],2.0,-1.0)
		by = b.math("MULTIPLY_ADD",base["Green"],2.0,-1.0)
		bz = b.math("MULTIPLY_ADD",base["Blue"],2.0,-1.0)
		bx,by,bz = b.normalize3(b.math("MULTIPLY",bx,baseWeight),b.math("MULTIPLY",by,baseWeight),b.math("MULTIPLY_ADD",b.math("SUBTRACT",bz,1.0),baseWeight,1.0))
		detail = b.separateXYZ(i["Detail Normal"])
		nx,ny,nz = b.normalize3(b.math("ADD",detail["X"],bx),b.math("ADD",detail["Y"],by),bz)
		outNode = b.nodes.new('NodeGroupOutput')
		outNode.location = (b.x + 200,0)
		b.links.new(b.combineColor(b.math("MULTIPLY_ADD",nx,0.5,0.5),b.math("MULTIPLY_ADD",ny,0.5,0.5),b.math("MULTIPLY_ADD",nz,0.5,0.5)),outNode.inputs["Color"])
	nodeGroupNode = nodeTree.nodes.new("ShaderNodeGroup")
	nodeGroupNode.node_tree = nodeGroup
	return nodeGroupNode

def addMHWildsDetailLayerNodes(nodeTree,matInfo):
	#Detail_ALBD/NRRH R,G,B,A layers masked by DetailMaskMap, applied on the finished base (ColorParam included) before ColorLayer
	props = matInfo["mPropDict"]
	textureNodes = matInfo["textureNodeDict"]
	if not hasLoadedImage(matInfo,"DetailMaskMap") or matInfo["albedoNodeLayerGroup"].currentOutSocket == None:
		return
	if "UseDetail" in props and props["UseDetail"].propValue[0] <= 0.0:
		return
	channels = [channel for channel in ("R","G","B","A") if hasLoadedImage(matInfo,f"Detail_ALBD_{channel}") and hasLoadedImage(matInfo,f"Detail_NRRH_{channel}")]
	if not channels:
		return
	nodes = nodeTree.nodes
	links = nodeTree.links
	def propValue(name,default,index = 0):
		return float(props[name].propValue[index]) if name in props else default
	maskNode = textureNodes["DetailMaskMap"]
	#MultiBlend #57 %885..%887: Use_SecodaryUV_DetailMask > 0 ? UV1 : base (ChangeUV) UV
	if "Use_SecodaryUV_DetailMask" in props and "UVMap2Node" in nodeTree.nodes and "Vector" in maskNode.inputs:
		uv = getMHWildsBaseAOUVNode(nodeTree,matInfo)
		nodeTree.links.new(mhWildsUVSelect(nodeTree,matInfo,"Use_SecodaryUV_DetailMask",uv.outputs["Base UV"],nodeTree.nodes["UVMap2Node"].outputs["UV"]),maskNode.inputs["Vector"])
	maskSep = nodes.new("ShaderNodeSeparateColor")
	maskSep.location = maskNode.location + Vector((300,0))
	links.new(maskNode.outputs["Color"],maskSep.inputs["Color"])
	maskSockets = {"R":maskSep.outputs["Red"],"G":maskSep.outputs["Green"],"B":maskSep.outputs["Blue"],"A":maskNode.outputs["Alpha"]}

	baseColor = matInfo["albedoNodeLayerGroup"].currentOutSocket
	baseRoughness = matInfo["roughnessNodeLayerGroup"].currentOutSocket
	metallicSocket = matInfo["metallicNodeLayerGroup"].currentOutSocket
	baseMetal = None
	if metallicSocket != None:
		if matInfo["isDielectric"]:#The metallic stack holds the dielectric value until the end
			invertNode = nodes.new("ShaderNodeMath")
			invertNode.operation = "SUBTRACT"
			invertNode.inputs[0].default_value = 1.0
			links.new(metallicSocket,invertNode.inputs[1])
			baseMetal = invertNode.outputs["Value"]
		else:
			baseMetal = metallicSocket
	modulate = propValue("ModulateColor",1.0)

	layerNodes = {}
	weights = {}
	prevNode = None
	mergeNode = None
	location = maskNode.location + Vector((600,0))
	for channel in ("R","G","B","A"):
		if channel not in channels:
			continue
		layerNode = getMHWildsDetailLayerNodeGroup(nodeTree)
		layerNode.label = f"Detail Layer {channel}"
		layerNode.location = location
		location = location + Vector((300,-150))
		uvNode = getMHWildsDetailUVNodeGroup(nodeTree)
		uvNode.location = textureNodes[f"Detail_ALBD_{channel}"].location + Vector((-300,0))
		if "UVMap1Node" in nodes:
			links.new(nodes["UVMap1Node"].outputs["UV"],uvNode.inputs["UV"])
		linkMHWildsProp(nodeTree,matInfo,f"DetailTile_{channel}",uvNode.inputs["DetailTile"],1.0)
		linkMHWildsProp(nodeTree,matInfo,f"UseFlip_{channel}",uvNode.inputs["UseFlip"],0.0)
		linkMHWildsProp(nodeTree,matInfo,f"UseUV_ScaleOffset_{channel}",uvNode.inputs["UseUV_ScaleOffset"],0.0)
		for index,socketName in enumerate(("ScaleX","ScaleY","OffsetX","OffsetY")):
			linkMHWildsProp(nodeTree,matInfo,f"UV_ScaleOffset_{channel}",uvNode.inputs[socketName],(1.0,1.0,0.0,0.0)[index],output = index)
		for textureType in (f"Detail_ALBD_{channel}",f"Detail_NRRH_{channel}"):
			links.new(uvNode.outputs["Vector"],textureNodes[textureType].inputs["Vector"])
		links.new(textureNodes[f"Detail_ALBD_{channel}"].outputs["Color"],layerNode.inputs["ALBD"])
		links.new(textureNodes[f"Detail_ALBD_{channel}"].outputs["Alpha"],layerNode.inputs["ALBD Alpha"])
		links.new(textureNodes[f"Detail_NRRH_{channel}"].outputs["Color"],layerNode.inputs["NRRH"])
		links.new(textureNodes[f"Detail_NRRH_{channel}"].outputs["Alpha"],layerNode.inputs["NRRH Alpha"])
		links.new(maskSockets[channel],layerNode.inputs["Mask"])
		for socketName,propName,default in (("Use",f"Use_{channel}",0.0),("UseOpacity",f"UseOpacity_{channel}",0.0),("PrevHeight",f"PrevHeight_{channel}",0.0),
				("UseThrough_Normal",f"UseThrough_Normal_{channel}",0.0),("useOPM","useOPM",0.0),("DetailAlphaRef",f"DetailAlphaRef_{channel}",0.5),
				("DetailAlphaWidth",f"DetailAlphaWidth_{channel}",0.0),("Detail_Roughness",f"Detail_Roughness_{channel}",0.5),("Detail_Metal",f"Detail_Metal_{channel}",0.5),
				("DetailNormal",f"DetailNormal_{channel}",0.5),("Detail_Roughness_Blend",f"Detail_Roughness_Blend_{channel}",1.0),("UseFlip",f"UseFlip_{channel}",0.0)):
			linkMHWildsProp(nodeTree,matInfo,propName,layerNode.inputs[socketName],default)
		linkMHWildsProp(nodeTree,matInfo,f"Detail_Color_{channel}",layerNode.inputs["Detail_Color"],(0.5,0.5,0.5,1.0),output = "Color")
		linkMHWildsProp(nodeTree,matInfo,f"Detail_Color_{channel}",layerNode.inputs["Detail_Color Alpha"],1.0,output = "Alpha")

		if channel == "A":
			#The A layer works on the merged result without modulation
			if prevNode != None:
				mergeNode = getMHWildsDetailMergeNodeGroup(nodeTree)
				mergeNode.location = location + Vector((0,300))
				links.new(baseColor,mergeNode.inputs["Base Color"])
				links.new(prevNode.outputs["Color"],mergeNode.inputs["Layer Color"])
				links.new(prevNode.outputs["Roughness"],mergeNode.inputs["Layer Roughness"])
				links.new(prevNode.outputs["Metal"],mergeNode.inputs["Layer Metal"])
				for weightChannel in ("R","G","B"):
					if weightChannel in weights:
						links.new(weights[weightChannel],mergeNode.inputs[f"Weight {weightChannel}"])
				linkMHWildsProp(nodeTree,matInfo,"ModulateColor",mergeNode.inputs["ModulateColor"],1.0)
				if baseRoughness != None:
					links.new(baseRoughness,mergeNode.inputs["Base Roughness"])
				else:
					mergeNode.inputs["Base Roughness"].default_value = 1.0
				if baseMetal != None:
					links.new(baseMetal,mergeNode.inputs["Base Metal"])
				links.new(mergeNode.outputs["Color"],layerNode.inputs["Prev Color"])
				links.new(mergeNode.outputs["Roughness"],layerNode.inputs["Prev Roughness"])
				links.new(mergeNode.outputs["Metal"],layerNode.inputs["Prev Metal"])
				links.new(prevNode.outputs["Normal"],layerNode.inputs["Prev Normal"])
				links.new(prevNode.outputs["Height"],layerNode.inputs["Prev Height"])
			else:
				links.new(baseColor,layerNode.inputs["Prev Color"])
				if baseRoughness != None:
					links.new(baseRoughness,layerNode.inputs["Prev Roughness"])
				else:
					layerNode.inputs["Prev Roughness"].default_value = 1.0
				if baseMetal != None:
					links.new(baseMetal,layerNode.inputs["Prev Metal"])
		elif prevNode == None:
			#First of R,G,B: color and roughness start at 0.5 with ModulateColor, metal at the base metal
			if modulate > 0.0:
				layerNode.inputs["Prev Color"].default_value = (0.5,0.5,0.5,1.0)
				layerNode.inputs["Prev Roughness"].default_value = 0.5
			else:
				links.new(baseColor,layerNode.inputs["Prev Color"])
				if baseRoughness != None:
					links.new(baseRoughness,layerNode.inputs["Prev Roughness"])
			if baseMetal != None:
				links.new(baseMetal,layerNode.inputs["Prev Metal"])
		else:
			for socketName in ("Color","Roughness","Metal","Normal","Height"):
				links.new(prevNode.outputs[socketName],layerNode.inputs["Prev " + socketName])
		weights[channel] = layerNode.outputs["Weight"]
		layerNodes[channel] = layerNode
		prevNode = layerNode

	if "A" not in layerNodes:
		#No A layer, merge the R,G,B chain directly
		mergeNode = getMHWildsDetailMergeNodeGroup(nodeTree)
		mergeNode.location = location
		links.new(baseColor,mergeNode.inputs["Base Color"])
		links.new(prevNode.outputs["Color"],mergeNode.inputs["Layer Color"])
		links.new(prevNode.outputs["Roughness"],mergeNode.inputs["Layer Roughness"])
		links.new(prevNode.outputs["Metal"],mergeNode.inputs["Layer Metal"])
		for weightChannel in ("R","G","B"):
			if weightChannel in weights:
				links.new(weights[weightChannel],mergeNode.inputs[f"Weight {weightChannel}"])
		linkMHWildsProp(nodeTree,matInfo,"ModulateColor",mergeNode.inputs["ModulateColor"],1.0)
		if baseRoughness != None:
			links.new(baseRoughness,mergeNode.inputs["Base Roughness"])
		else:
			mergeNode.inputs["Base Roughness"].default_value = 1.0
		if baseMetal != None:
			links.new(baseMetal,mergeNode.inputs["Base Metal"])
		resultNode = mergeNode
	else:
		resultNode = layerNodes["A"]

	matInfo["albedoNodeLayerGroup"].currentOutSocket = resultNode.outputs["Color"]
	matInfo["roughnessNodeLayerGroup"].currentOutSocket = resultNode.outputs["Roughness"]
	metalOut = resultNode.outputs["Metal"]
	if metallicSocket != None and matInfo["isDielectric"]:
		invertBackNode = nodes.new("ShaderNodeMath")
		invertBackNode.operation = "SUBTRACT"
		invertBackNode.inputs[0].default_value = 1.0
		invertBackNode.location = resultNode.location + Vector((300,-200))
		links.new(metalOut,invertBackNode.inputs[1])
		metalOut = invertBackNode.outputs["Value"]
	if metallicSocket != None:
		matInfo["metallicNodeLayerGroup"].currentOutSocket = metalOut

	if matInfo["normalNodeLayerGroup"].currentOutSocket != None:
		normalNode = getMHWildsDetailNormalNodeGroup(nodeTree)
		normalNode.location = resultNode.location + Vector((300,-400))
		links.new(matInfo["normalNodeLayerGroup"].currentOutSocket,normalNode.inputs["Base Normal Color"])
		links.new(layerNodes[channels[-1]].outputs["Normal"],normalNode.inputs["Detail Normal"])
		for channel in ("R","G","B","A"):
			linkMHWildsProp(nodeTree,matInfo,f"BaseNormal_Blend_{channel}",normalNode.inputs[f"BaseNormal_Blend_{channel}"],1.0)
			if channel in layerNodes:
				linkMHWildsProp(nodeTree,matInfo,f"Use_{channel}",normalNode.inputs[f"Use_{channel}"],0.0)
			else:
				normalNode.inputs[f"Use_{channel}"].default_value = 0.0
			if channel in weights:
				links.new(weights[channel],normalNode.inputs[f"Weight {channel}"])
		matInfo["normalNodeLayerGroup"].currentOutSocket = normalNode.outputs["Color"]

def getMHWildsFilmNodeGroup(nodeTree):
	#Thin film on the base color, from Base_Equip_ch02_042_0000 PS #63 (lines 2796-2952), identical in VFXwe PS #63
	#Runs after Detail and ColorLayer, before the PanoramaMap fake refraction
	#NoV = |dot(V,N)|, d = NoV * saturate(Film_Thickness * FxMap.R)
	#ior = Film_IOR, with UseBaseColorFilm: Film_IOR - 0.008 + ((0.045 - 0.123*saturate(|1-3h|)) * saturate(|3h-2|) + 0.078) * s (h, s = hue and saturation of the color)
	#k = 0.5 - 0.5*cos((d - 0.5 + ior) * (24.85, 30.45, 35.0)) * (1 - d), filmFull = 4*color*k*k
	#FullFIlm: color = filmFull
	#else UseBaseColorFilm: color = lerp(color, k*max(color.rgb), Film_Blend > 0 ? (1-NoV^3)*FxMap.R*|Film_Blend| : |Film_Blend|*NoV)
	#else: color = lerp(color, filmFull, FxMap.R*Film_Blend)
	if "MHWildsFilm" in bpy.data.node_groups:
		nodeGroup = bpy.data.node_groups["MHWildsFilm"]
	else:
		nodeGroup = bpy.data.node_groups.new(type="ShaderNodeTree", name="MHWildsFilm")
		newGroupSockets(nodeGroup,[("Color","NodeSocketColor"),("Normal","NodeSocketVector"),("FxMap R","NodeSocketFloat"),("Film_Thickness","NodeSocketFloat"),
			("Film_IOR","NodeSocketFloat"),("Film_Blend","NodeSocketFloat"),("UseBaseColorFilm","NodeSocketFloat"),("FullFIlm","NodeSocketFloat")],"INPUT")
		newGroupSockets(nodeGroup,[("Color","NodeSocketColor")],"OUTPUT")
		b = ShaderGroupBuilder(nodeGroup)
		inNode = b.nodes.new('NodeGroupInput')
		i = inNode.outputs
		geometryNode = b.nodes.new("ShaderNodeNewGeometry")
		dotNode = b.nodes.new("ShaderNodeVectorMath")
		dotNode.operation = "DOT_PRODUCT"
		b.links.new(geometryNode.outputs["Incoming"],dotNode.inputs[0])
		b.links.new(i["Normal"],dotNode.inputs[1])
		nov = b.math("ABSOLUTE",dotNode.outputs["Value"])
		fxR = i["FxMap R"]
		d = b.math("MULTIPLY",nov,b.math("MULTIPLY",i["Film_Thickness"],fxR,clamp = True))

		hsvNode = b.nodes.new("ShaderNodeSeparateColor")
		hsvNode.mode = "HSV"
		b.links.new(i["Color"],hsvNode.inputs["Color"])
		hue = hsvNode.outputs[0]
		saturation = hsvNode.outputs[1]
		hueOffset = b.math("MULTIPLY",b.math("MULTIPLY_ADD",
			b.math("MULTIPLY_ADD",b.math("ABSOLUTE",b.math("MULTIPLY_ADD",hue,-3.0,1.0),clamp = True),-0.123,0.045),
			b.math("ABSOLUTE",b.math("MULTIPLY_ADD",hue,3.0,-2.0),clamp = True),0.078),saturation)
		useBaseFilm = b.greater0(i["UseBaseColorFilm"])
		ior = b.select(useBaseFilm,b.math("ADD",b.math("SUBTRACT",i["Film_IOR"],0.008),hueOffset),i["Film_IOR"])
		phase = b.math("ADD",b.math("SUBTRACT",d,0.5),ior)
		oneMinusD = b.math("SUBTRACT",1.0,d)
		color = b.separate(i["Color"])
		maxColor = b.math("MAXIMUM",color["Red"],b.math("MAXIMUM",color["Green"],color["Blue"]))
		blend = i["Film_Blend"]
		absBlend = b.math("ABSOLUTE",blend)
		baseFilmWeight = b.select(b.greater0(blend),
			b.math("MULTIPLY",b.math("MULTIPLY",b.math("SUBTRACT",1.0,b.math("POWER",nov,3.0)),fxR),absBlend),
			b.math("MULTIPLY",absBlend,nov))
		plainWeight = b.math("MULTIPLY",fxR,blend)
		fullFilm = b.greater0(i["FullFIlm"])
		result = []
		for channel,frequency in (("Red",24.85),("Green",30.45),("Blue",35.0)):
			k = b.math("MULTIPLY_ADD",b.math("MULTIPLY",b.math("COSINE",b.math("MULTIPLY",phase,frequency)),oneMinusD),-0.5,0.5)
			filmFull = b.math("MULTIPLY",b.math("MULTIPLY",color[channel],4.0),b.math("MULTIPLY",k,k))
			value = b.select(useBaseFilm,b.lerp(color[channel],b.math("MULTIPLY",k,maxColor),baseFilmWeight),b.lerp(color[channel],filmFull,plainWeight))
			result.append(b.select(fullFilm,filmFull,value))
		outNode = b.nodes.new('NodeGroupOutput')
		outNode.location = (b.x + 200,0)
		b.links.new(b.combineColor(*result),outNode.inputs["Color"])
	nodeGroupNode = nodeTree.nodes.new("ShaderNodeGroup")
	nodeGroupNode.node_tree = nodeGroup
	return nodeGroupNode

def mhWildsFilmActive(props):
	def value(name):
		return props[name].propValue[0] if name in props else 0.0
	return value("FullFIlm") > 0.0 or value("Film_Blend") != 0.0

def addMHWildsFilmNodes(nodeTree,matInfo,mappedNormalSocket = None):
	props = matInfo["mPropDict"]
	if not mhWildsFilmActive(props) or matInfo["albedoNodeLayerGroup"].currentOutSocket == None or not hasLoadedImage(matInfo,"FxMap"):
		return
	nodes = nodeTree.nodes
	links = nodeTree.links
	fxNode = matInfo["textureNodeDict"]["FxMap"]
	filmNode = getMHWildsFilmNodeGroup(nodeTree)
	filmNode.location = fxNode.location + Vector((600,200))
	if "FxMapSepNode" in nodes:
		fxSepNode = nodes["FxMapSepNode"]
	else:
		fxSepNode = nodes.new("ShaderNodeSeparateColor")
		fxSepNode.name = "FxMapSepNode"
		fxSepNode.location = fxNode.location + Vector((300,0))
		links.new(fxNode.outputs["Color"],fxSepNode.inputs["Color"])
	links.new(fxSepNode.outputs["Red"],filmNode.inputs["FxMap R"])
	if mappedNormalSocket != None:
		links.new(mappedNormalSocket,filmNode.inputs["Normal"])
	else:
		if "geometryNode" not in nodes:
			geometryNode = nodes.new("ShaderNodeNewGeometry")
			geometryNode.name = "geometryNode"
			geometryNode.location = (-800,400)
		links.new(nodes["geometryNode"].outputs["Normal"],filmNode.inputs["Normal"])
	for name,default in (("Film_Thickness",0.0),("Film_IOR",0.5),("Film_Blend",0.0),("UseBaseColorFilm",0.0),("FullFIlm",0.0)):
		linkMHWildsProp(nodeTree,matInfo,name,filmNode.inputs[name],default)
	links.new(matInfo["albedoNodeLayerGroup"].currentOutSocket,filmNode.inputs["Color"])
	matInfo["albedoNodeLayerGroup"].currentOutSocket = filmNode.outputs["Color"]

def addMHWildsFixedAlphaNodes(nodeTree,matInfo):
	#Base_Equip_ch02_042_0000 fur: alpha = saturate(ColorParam.a * 2 * alphaSource * Fixed_AlphaMap.R), Fixed_AlphaMap on the plain first UV
	#The ColorParam.a * alphaSource part is already in alphaSocket for MH Wilds
	if not hasLoadedImage(matInfo,"Fixed_AlphaMap") or matInfo["alphaSocket"] == None:
		return
	nodes = nodeTree.nodes
	links = nodeTree.links
	fixedNode = matInfo["textureNodeDict"]["Fixed_AlphaMap"]
	if "UVMap1Node" in nodes:
		links.new(nodes["UVMap1Node"].outputs["UV"],fixedNode.inputs["Vector"])
	fixedSepNode = nodes.new("ShaderNodeSeparateColor")
	fixedSepNode.location = fixedNode.location + Vector((300,0))
	links.new(fixedNode.outputs["Color"],fixedSepNode.inputs["Color"])
	multNode = nodes.new("ShaderNodeMath")
	multNode.operation = "MULTIPLY"
	multNode.location = fixedNode.location + Vector((600,0))
	links.new(matInfo["alphaSocket"],multNode.inputs[0])
	links.new(fixedSepNode.outputs["Red"],multNode.inputs[1])
	doubleNode = nodes.new("ShaderNodeMath")
	doubleNode.operation = "MULTIPLY"
	doubleNode.use_clamp = True
	doubleNode.location = fixedNode.location + Vector((800,0))
	links.new(multNode.outputs["Value"],doubleNode.inputs[0])
	doubleNode.inputs[1].default_value = 2.0
	matInfo["alphaSocket"] = doubleNode.outputs["Value"]

MHWILDS_TIME_GROUP = "MHWildsTime"

def getMHWildsTimeNodeGroup(nodeTree):
	#Shared clock for animated MH Wilds material effects
	#Seconds = (frame - frame_start) / fps, driven by the scene frame so it lines up with baked animation and renders
	#Animate = 0 keeps every material at its t = 0 state (static preview), 1 plays along with the timeline
	if MHWILDS_TIME_GROUP in bpy.data.node_groups:
		nodeGroup = bpy.data.node_groups[MHWILDS_TIME_GROUP]
	else:
		nodeGroup = bpy.data.node_groups.new(type="ShaderNodeTree", name=MHWILDS_TIME_GROUP)
		newGroupSockets(nodeGroup,[("Seconds","NodeSocketFloat")],"OUTPUT")
		nodes = nodeGroup.nodes
		secondsNode = nodes.new("ShaderNodeValue")
		secondsNode.name = "Seconds"
		secondsNode.label = "Seconds (driven by frame)"
		animateNode = nodes.new("ShaderNodeValue")
		animateNode.name = "Animate"
		animateNode.label = "Animate (0 = static)"
		animateNode.location = (0,-200)
		animateNode.outputs[0].default_value = 0.0
		multNode = nodes.new("ShaderNodeMath")
		multNode.operation = "MULTIPLY"
		multNode.location = (200,0)
		nodeGroup.links.new(secondsNode.outputs[0],multNode.inputs[0])
		nodeGroup.links.new(animateNode.outputs[0],multNode.inputs[1])
		outNode = nodes.new("NodeGroupOutput")
		outNode.location = (400,0)
		nodeGroup.links.new(multNode.outputs[0],outNode.inputs["Seconds"])
		scene = bpy.context.scene
		try:
			fcurve = nodeGroup.driver_add('nodes["Seconds"].outputs[0].default_value')
			driver = fcurve.driver
			driver.type = "SCRIPTED"
			for name,path in (("fps","render.fps"),("fps_base","render.fps_base"),("start","frame_start")):
				variable = driver.variables.new()
				variable.name = name
				variable.type = "SINGLE_PROP"
				variable.targets[0].id_type = "SCENE"
				variable.targets[0].id = scene
				variable.targets[0].data_path = path
			#Simple expression, runs without Python auto run
			driver.expression = "(frame - start) * fps_base / fps"
		except Exception as err:
			print(f"Unable to create the material animation driver: {err}")
	nodeGroupNode = nodeTree.nodes.new("ShaderNodeGroup")
	nodeGroupNode.node_tree = nodeGroup
	nodeGroupNode.label = "MH Wilds Material Time"
	return nodeGroupNode

def getMHWildsAnimEmitNodeGroup(nodeTree):
	#AnimEmit / WaveEmit and SecEmit animation, VFXwe PS #63 %1949..%1970 and %1987..%2004, same code in Base_Equip_ch02_042_0000
	#t = seconds * Speed (the game clock is userGlobalParams[0].x * 0.001, Use_InstanceID adds the instance id, taken as 0 here)
	#phase = UseWave ? Wave * (t + FxMap.B) : t, factor = max(0, lerp(1, Min, 0.5 + 0.5*sin(phase))), Min == 1 means off
	if "MHWildsAnimEmit" in bpy.data.node_groups:
		nodeGroup = bpy.data.node_groups["MHWildsAnimEmit"]
	else:
		nodeGroup = bpy.data.node_groups.new(type="ShaderNodeTree", name="MHWildsAnimEmit")
		newGroupSockets(nodeGroup,[("Seconds","NodeSocketFloat"),("Min","NodeSocketFloat"),("Speed","NodeSocketFloat"),("UseWave","NodeSocketFloat"),
			("Wave","NodeSocketFloat"),("FxMap B","NodeSocketFloat")],"INPUT")
		newGroupSockets(nodeGroup,[("Factor","NodeSocketFloat")],"OUTPUT")
		b = ShaderGroupBuilder(nodeGroup)
		i = b.nodes.new('NodeGroupInput').outputs
		t = b.math("MULTIPLY",i["Seconds"],i["Speed"])
		phase = b.select(b.math("COMPARE",i["UseWave"],0.0,0.0),t,b.math("MULTIPLY",i["Wave"],b.math("ADD",t,i["FxMap B"])))
		wave = b.math("MULTIPLY_ADD",b.math("SINE",phase),0.5,0.5)
		factor = b.math("MAXIMUM",b.lerp(1.0,i["Min"],wave),0.0)
		outNode = b.nodes.new('NodeGroupOutput')
		outNode.location = (b.x + 200,0)
		b.links.new(factor,outNode.inputs["Factor"])
	nodeGroupNode = nodeTree.nodes.new("ShaderNodeGroup")
	nodeGroupNode.node_tree = nodeGroup
	return nodeGroupNode

def getMHWildsMoveEmitNodeGroup(nodeTree):
	#MoveEmit (static, VFXwe PS #63 lines 2606-2643), replaces AnimEmit when Use_MoveEmit > 0
	#Use_WaveMove: (0.5 + 0.5*cos((MoveEmit + FxMap.B) / max(Width,1e-4)))^3
	#else: s = smoothstep(saturate(saturate(Width + FxMap.B - (1-MoveEmit)*(Width+1)) / Width)), factor = 4*s*(1-s)
	if "MHWildsMoveEmit" in bpy.data.node_groups:
		nodeGroup = bpy.data.node_groups["MHWildsMoveEmit"]
	else:
		nodeGroup = bpy.data.node_groups.new(type="ShaderNodeTree", name="MHWildsMoveEmit")
		newGroupSockets(nodeGroup,[("MoveEmit","NodeSocketFloat"),("MoveEmit_Width","NodeSocketFloat"),("Use_WaveMove","NodeSocketFloat"),("FxMap B","NodeSocketFloat")],"INPUT")
		newGroupSockets(nodeGroup,[("Factor","NodeSocketFloat")],"OUTPUT")
		b = ShaderGroupBuilder(nodeGroup)
		i = b.nodes.new('NodeGroupInput').outputs
		width = i["MoveEmit_Width"]
		waveValue = b.math("MULTIPLY_ADD",b.math("COSINE",b.math("DIVIDE",b.math("ADD",i["MoveEmit"],i["FxMap B"]),b.math("MAXIMUM",width,1.0e-4))),0.5,0.5)
		waveFactor = b.math("POWER",waveValue,3.0)
		x = b.math("SUBTRACT",b.math("ADD",width,i["FxMap B"]),b.math("MULTIPLY",b.math("SUBTRACT",1.0,i["MoveEmit"]),b.math("ADD",width,1.0)),clamp = True)
		s = b.smoothstep01(b.math("DIVIDE",x,width,clamp = True))
		bandFactor = b.math("MULTIPLY",b.math("MULTIPLY",s,4.0),b.math("SUBTRACT",1.0,s))
		factor = b.select(b.math("COMPARE",i["Use_WaveMove"],0.0,0.0),bandFactor,waveFactor)
		outNode = b.nodes.new('NodeGroupOutput')
		outNode.location = (b.x + 200,0)
		b.links.new(factor,outNode.inputs["Factor"])
	nodeGroupNode = nodeTree.nodes.new("ShaderNodeGroup")
	nodeGroupNode.node_tree = nodeGroup
	return nodeGroupNode

def getMHWildsVectorEmitNodeGroup(nodeTree):
	#VectorEmit, VFXwe PS #63 lines 823-830, %372..%411: VectorEmitMap.RG = octahedral tangent space direction, .B = strength
	#s = saturate(dot(V, n))*0.5 + 0.5, factor = VectorEmitMap.B * (power+6)/6 * s^power
	#Also outputs the world direction and bitangent, ParallaxEmit uses them
	if "MHWildsVectorEmit" in bpy.data.node_groups:
		nodeGroup = bpy.data.node_groups["MHWildsVectorEmit"]
	else:
		nodeGroup = bpy.data.node_groups.new(type="ShaderNodeTree", name="MHWildsVectorEmit")
		newGroupSockets(nodeGroup,[("VectorEmitMap","NodeSocketColor"),("VectorEmit_power","NodeSocketFloat")],"INPUT")
		newGroupSockets(nodeGroup,[("Factor","NodeSocketFloat"),("Direction","NodeSocketVector"),("Bitangent","NodeSocketVector")],"OUTPUT")
		b = ShaderGroupBuilder(nodeGroup)
		i = b.nodes.new('NodeGroupInput').outputs
		vem = b.separate(i["VectorEmitMap"])
		ex = b.math("MULTIPLY_ADD",vem["Red"],2.0,-1.0)
		ey = b.math("MULTIPLY_ADD",vem["Green"],2.0,-1.0)
		z = b.math("SUBTRACT",b.math("SUBTRACT",1.0,b.math("ABSOLUTE",ex)),b.math("ABSOLUTE",ey))
		folded = b.math("LESS_THAN",z,0.0)
		fx = b.math("MULTIPLY",b.math("SUBTRACT",1.0,b.math("ABSOLUTE",ey)),b.math("SIGN",ex))
		fy = b.math("MULTIPLY",b.math("SUBTRACT",1.0,b.math("ABSOLUTE",ex)),b.math("SIGN",ey))
		ex,ey = b.select(folded,fx,ex),b.select(folded,fy,ey)
		nx,ny,nz = b.normalize3(ex,ey,z)
		#Tangent to world through a normal map node on the first UV
		normalMapNode = b.nodes.new("ShaderNodeNormalMap")
		normalMapNode.space = "TANGENT"
		normalMapNode.uv_map = "UVMap0"
		b.links.new(b.combineColor(b.math("MULTIPLY_ADD",nx,0.5,0.5),b.math("MULTIPLY_ADD",ny,0.5,0.5),b.math("MULTIPLY_ADD",nz,0.5,0.5)),normalMapNode.inputs["Color"])
		bitangentNode = b.nodes.new("ShaderNodeNormalMap")
		bitangentNode.space = "TANGENT"
		bitangentNode.uv_map = "UVMap0"
		bitangentNode.inputs["Color"].default_value = (0.5,1.0,0.5,1.0)
		geometryNode = b.nodes.new("ShaderNodeNewGeometry")
		dotNode = b.nodes.new("ShaderNodeVectorMath")
		dotNode.operation = "DOT_PRODUCT"
		b.links.new(geometryNode.outputs["Incoming"],dotNode.inputs[0])
		b.links.new(normalMapNode.outputs["Normal"],dotNode.inputs[1])
		s = b.math("MULTIPLY_ADD",b.math("MULTIPLY",dotNode.outputs["Value"],1.0,clamp = True),0.5,0.5)
		power = i["VectorEmit_power"]
		factor = b.math("MULTIPLY",b.math("MULTIPLY",vem["Blue"],b.math("DIVIDE",b.math("ADD",power,6.0),6.0)),b.math("POWER",s,power))
		outNode = b.nodes.new('NodeGroupOutput')
		outNode.location = (b.x + 200,0)
		b.links.new(factor,outNode.inputs["Factor"])
		b.links.new(normalMapNode.outputs["Normal"],outNode.inputs["Direction"])
		b.links.new(bitangentNode.outputs["Normal"],outNode.inputs["Bitangent"])
	nodeGroupNode = nodeTree.nodes.new("ShaderNodeGroup")
	nodeGroupNode.node_tree = nodeGroup
	return nodeGroupNode

PARALLAX_BLUR_TAPS = 4

def getAverageNodeGroup(count):
	#Mean of count color/alpha pairs
	name = f"REAverage{count}_v1"
	group = bpy.data.node_groups.get(name)
	if group != None:
		return group
	group = bpy.data.node_groups.new(name,"ShaderNodeTree")
	newGroupSockets(group,[s for k in range(count) for s in ((f"Color{k}","NodeSocketColor"),(f"Alpha{k}","NodeSocketFloat"))],"INPUT")
	newGroupSockets(group,[("Color","NodeSocketColor"),("Alpha","NodeSocketFloat")],"OUTPUT")
	b = ShaderGroupBuilder(group)
	i = b.nodes.new("NodeGroupInput").outputs
	color = i["Color0"];alpha = i["Alpha0"]
	for k in range(1,count):
		add = b.nodes.new("ShaderNodeVectorMath");add.operation = "ADD"
		b.links.new(color,add.inputs[0]);b.links.new(i[f"Color{k}"],add.inputs[1]);color = add.outputs["Vector"]
		alpha = b.math("ADD",alpha,i[f"Alpha{k}"])
	scale = b.nodes.new("ShaderNodeVectorMath");scale.operation = "SCALE";scale.inputs["Scale"].default_value = 1.0/count
	b.links.new(color,scale.inputs[0])
	out = b.nodes.new("NodeGroupOutput")
	b.links.new(scale.outputs["Vector"],out.inputs["Color"]);b.links.new(b.math("MULTIPLY",alpha,1.0/count),out.inputs["Alpha"])
	return group

def mhWildsUVSelect(nodeTree,matInfo,propName,a,b,blend = False):
	#Vector a when the property is 0, b when it is on (> 0), or lerp(a, b, value) with blend
	mix = nodeTree.nodes.new("ShaderNodeMix")
	mix.data_type = "VECTOR"
	nodeTree.links.new(a,mix.inputs["A"]);nodeTree.links.new(b,mix.inputs["B"])
	if blend:
		linkMHWildsProp(nodeTree,matInfo,propName,mix.inputs["Factor"],0.0)
	else:
		on = nodeTree.nodes.new("ShaderNodeMath");on.operation = "GREATER_THAN";on.inputs[1].default_value = 0.0
		linkMHWildsProp(nodeTree,matInfo,propName,on.inputs[0],0.0)
		nodeTree.links.new(on.outputs["Value"],mix.inputs["Factor"])
	return mix.outputs["Result"]

def addMHWildsSecondaryUVBlendNodes(nodeTree,matInfo):
	#Base_eye_Emit #59: uv = lerp(ChangeUV ? UV1 : UV0, UV1, UV_Secondary_Blend) for NRRO, albedo, VectorEmitMap and the
	#non-parallax EmissiveMap; the AO sample stays on UV1 when UseAOSecondaryUV is on.
	props = matInfo["mPropDict"]
	secondary = nodeTree.nodes.get("UVMap2Node")
	if matInfo["gameName"] != "MHWILDS" or "UV_Secondary_Blend" not in props or secondary == None:
		return
	uv = getMHWildsBaseAOUVNode(nodeTree,matInfo)
	blended = mhWildsUVSelect(nodeTree,matInfo,"UV_Secondary_Blend",uv.outputs["Base UV"],secondary.outputs["UV"],blend = True)
	slots = ["BaseDielectricMap","BaseAlphaMap","NormalRoughnessOcclusionMap","AlphaTranslucentOcclusionSSSMap","VectorEmitMap"]
	if mhWildsPropValue(props,"UseParallaxEmit") <= 0.0:
		slots.append("EmissiveMap")
	for name in slots:
		image = matInfo["textureNodeDict"].get(name)
		if image != None and "Vector" in image.inputs:
			nodeTree.links.new(blended,image.inputs["Vector"])
	aoUV = mhWildsUVSelect(nodeTree,matInfo,"UseAOSecondaryUV",blended,secondary.outputs["UV"])
	for node in nodeTree.nodes:
		if node.bl_idname == "ShaderNodeTexImage" and node.name.startswith("AO_"):
			nodeTree.links.new(aoUV,node.inputs["Vector"])

def getMHWildsBasecolorToEmissiveNodeGroup():
	#Use_Basecolor_to_Emissive != 0 (MultiBlend #61, RoughTransparent #80, eye #57, Fur #111; same block in all):
	#r = max3(EmissiveMap*Emissive_Color), or (max3(EmissiveMap) < Emissive_Color.a ? 0 : 1) when that alpha < 1;
	#RoughTransparent's Use_Basecolor_Mask scales r by smoothstep((max3(base) - Min) / (Max - Min)).
	#Emission becomes base*r (Intensity*2^Power stay on the strength side), base becomes base*(1 - saturate(r)).
	#.240906211 Fix_BaseColor_to_Emissive kept the base; .250206176 always darkens it, so Fix is ignored.
	name = "MHWildsBasecolorToEmissive_v1"
	group = bpy.data.node_groups.get(name)
	if group != None:
		return group
	group = bpy.data.node_groups.new(name,"ShaderNodeTree")
	newGroupSockets(group,[("Base","NodeSocketColor"),("Emission","NodeSocketColor"),("EmissiveMap","NodeSocketColor"),("Emissive Alpha","NodeSocketFloat"),
		("Use_Basecolor_to_Emissive","NodeSocketFloat"),("Use_Basecolor_Mask","NodeSocketFloat"),("Basecolor_Mask_Min","NodeSocketFloat"),("Basecolor_Mask_Max","NodeSocketFloat")],"INPUT")
	newGroupSockets(group,[("Base","NodeSocketColor"),("Emission","NodeSocketColor")],"OUTPUT")
	b = ShaderGroupBuilder(group)
	i = b.nodes.new("NodeGroupInput").outputs
	def max3(socket):
		c = b.separate(socket)
		return b.math("MAXIMUM",b.math("MAXIMUM",c["Red"],c["Green"]),c["Blue"])
	hard = b.math("SUBTRACT",1.0,b.math("LESS_THAN",max3(i["EmissiveMap"]),i["Emissive Alpha"]))
	r = b.select(b.math("LESS_THAN",i["Emissive Alpha"],1.0),hard,max3(i["Emission"]))
	base = b.separate(i["Base"])
	brightness = max3(i["Base"])
	span = b.math("SUBTRACT",i["Basecolor_Mask_Max"],i["Basecolor_Mask_Min"])
	mask = b.smoothstep01(b.math("DIVIDE",b.math("SUBTRACT",brightness,i["Basecolor_Mask_Min"]),span,clamp = True))
	r = b.math("MULTIPLY",r,b.select(b.math("COMPARE",i["Use_Basecolor_Mask"],0.0,0.0),1.0,mask))
	keep = b.math("SUBTRACT",1.0,b.math("ADD",r,0.0,clamp = True))
	on = b.math("SUBTRACT",1.0,b.math("COMPARE",i["Use_Basecolor_to_Emissive"],0.0,0.0))
	emission = b.separate(i["Emission"])
	channels = ("Red","Green","Blue")
	out = b.nodes.new("NodeGroupOutput")
	b.links.new(b.combineColor(*[b.select(on,b.math("MULTIPLY",base[c],keep),base[c]) for c in channels]),out.inputs["Base"])
	b.links.new(b.combineColor(*[b.select(on,b.math("MULTIPLY",base[c],r),emission[c]) for c in channels]),out.inputs["Emission"])
	return group

def addMHWildsBasecolorToEmissiveNodes(nodeTree,matInfo):
	props = matInfo["mPropDict"]
	albedo,emission = matInfo["albedoNodeLayerGroup"],matInfo["emissionColorNodeLayerGroup"]
	if matInfo["gameName"] != "MHWILDS" or "Use_Basecolor_to_Emissive" not in props or not hasLoadedImage(matInfo,"EmissiveMap"):
		return None
	if albedo.currentOutSocket == None or emission.currentOutSocket == None:
		return None
	colorName = next((n for n in ("Emissive_color","Emissive_Color","EmissiveColor","Emissive_Color1") if n in props),None)
	node = nodeTree.nodes.new("ShaderNodeGroup")
	node.node_tree = getMHWildsBasecolorToEmissiveNodeGroup()
	node.name = "MHWilds Basecolor To Emissive"
	links = nodeTree.links
	links.new(albedo.currentOutSocket,node.inputs["Base"])
	links.new(emission.currentOutSocket,node.inputs["Emission"])
	links.new(matInfo["textureNodeDict"]["EmissiveMap"].outputs["Color"],node.inputs["EmissiveMap"])
	if colorName != None:
		linkMHWildsProp(nodeTree,matInfo,colorName,node.inputs["Emissive Alpha"],output = "Alpha")
	else:
		node.inputs["Emissive Alpha"].default_value = 1.0
	for name,default in (("Use_Basecolor_to_Emissive",0.0),("Use_Basecolor_Mask",0.0),("Basecolor_Mask_Min",0.0),("Basecolor_Mask_Max",1.0)):
		linkMHWildsProp(nodeTree,matInfo,name,node.inputs[name],default)
	albedo.currentOutSocket = node.outputs["Base"]
	emission.currentOutSocket = node.outputs["Emission"]
	return node

def getMHWildsUVTileNodeGroup():
	#BaseAlpha_Emit_RoughTransparent #80 l.911-927: uv'' = (uv*UV_Tile)*UV_Tile_Offset.xy + UV_Tile_Offset.zw in D3D UV space
	name = "MHWildsUVTile_v1"
	group = bpy.data.node_groups.get(name)
	if group != None:
		return group
	group = bpy.data.node_groups.new(name,"ShaderNodeTree")
	newGroupSockets(group,[("UV","NodeSocketVector"),("UV_Tile","NodeSocketFloat"),("Scale X","NodeSocketFloat"),("Scale Y","NodeSocketFloat"),("Offset X","NodeSocketFloat"),("Offset Y","NodeSocketFloat")],"INPUT")
	newGroupSockets(group,[("UV","NodeSocketVector")],"OUTPUT")
	b = ShaderGroupBuilder(group)
	i = b.nodes.new("NodeGroupInput").outputs
	uv = b.separateXYZ(i["UV"])
	u = b.math("MULTIPLY_ADD",b.math("MULTIPLY",uv["X"],i["UV_Tile"]),i["Scale X"],i["Offset X"])
	#Imported V is 1 - D3D V
	v = b.math("SUBTRACT",1.0,b.math("MULTIPLY_ADD",b.math("MULTIPLY",b.math("SUBTRACT",1.0,uv["Y"]),i["UV_Tile"]),i["Scale Y"],i["Offset Y"]))
	out = b.nodes.new("NodeGroupOutput")
	b.links.new(b.combineXYZ(u,v,0.0),out.inputs["UV"])
	return group

def addMHWildsUVTileNodes(nodeTree,matInfo):
	props = matInfo["mPropDict"]
	if matInfo["gameName"] != "MHWILDS" or "UV_Tile" not in props or "UV_Tile_Offset" not in props:
		return None
	uv = getMHWildsBaseAOUVNode(nodeTree,matInfo)
	node = nodeTree.nodes.new("ShaderNodeGroup")
	node.node_tree = getMHWildsUVTileNodeGroup()
	node.name = "MHWilds UV Tile"
	node.location = uv.location + Vector((250,-200))
	nodeTree.links.new(uv.outputs["Base UV"],node.inputs["UV"])
	linkMHWildsProp(nodeTree,matInfo,"UV_Tile",node.inputs["UV_Tile"],1.0)
	for index,socket in enumerate(("Scale X","Scale Y","Offset X","Offset Y")):
		linkMHWildsProp(nodeTree,matInfo,"UV_Tile_Offset",node.inputs[socket],(1.0,1.0,0.0,0.0)[index],index)
	#The noise map and the secondary-UV AO read are not tiled
	for name in ("NormalRoughnessOcclusionMap","BaseAlphaMap","EmissiveMap","FxMap"):
		image = matInfo["textureNodeDict"].get(name)
		if image != None and "Vector" in image.inputs:
			nodeTree.links.new(node.outputs["UV"],image.inputs["Vector"])
	return node

def addMHWildsRoughTransparentTintNodes(nodeTree,matInfo,bsdf):
	#RoughTransparent #80 output: lerp(RoughTransparent_Color * background, lit, alpha) + specular (l.2341-2346, 3361-3365, 7440-7499).
	#The background read itself (blur by Tranparent_Roughness, refraction, depth fade) needs scene colour and is not reproduced:
	#a transparent BSDF tinted by RoughTransparent_Color stands in for it. Specular is weighted by alpha here, unlike the game.
	#The colour also gets Albedo/1024 (negligible) and a runtime stain term, both left out.
	props = matInfo["mPropDict"]
	if matInfo["gameName"] != "MHWILDS" or "RoughTransparent_Color" not in props or "roughtransparent" not in matInfo["mmtrName"]:
		return None
	alphaInput = bsdf.inputs["Alpha"]
	transparent = nodeTree.nodes.new("ShaderNodeBsdfTransparent")
	transparent.name = "MHWilds RoughTransparent Tint"
	linkMHWildsProp(nodeTree,matInfo,"RoughTransparent_Color",transparent.inputs["Color"],output = "Color")
	mix = nodeTree.nodes.new("ShaderNodeMixShader")
	if alphaInput.is_linked:
		source = alphaInput.links[0].from_socket
		nodeTree.links.remove(alphaInput.links[0])
		nodeTree.links.new(source,mix.inputs["Fac"])
	else:
		mix.inputs["Fac"].default_value = alphaInput.default_value
	alphaInput.default_value = 1.0
	nodeTree.links.new(transparent.outputs["BSDF"],mix.inputs[1])
	nodeTree.links.new(matInfo["currentShaderOutput"],mix.inputs[2])
	matInfo["currentShaderOutput"] = mix.outputs["Shader"]
	return mix

def getMHWildsAntiTranslucentNodeGroup():
	#Use_AntiTranslucent_Diffuse != 0 (hair #64, Equip #61, VFXwe #61, VFX_Hair #59, MultiBlend #61; identical):
	#albedo' = albedo + (albedo / (0.78 - 0.23*roughness) - albedo) * trans, on the final albedo and roughness.
	#trans = 2*dither*lerp(T, T*(1-|N'.V|)^RimTrasnlucent_Power, Use_RimTranslucent), T = TranslucentParam*ATOS.G,
	#N' = normalize(lerp(geometry normal, shading normal, RimTranslucent_NormalBlend)); the dither averages 0.5, so 2*dither -> 1.
	name = "MHWildsAntiTranslucent_v1"
	group = bpy.data.node_groups.get(name)
	if group != None:
		return group
	group = bpy.data.node_groups.new(name,"ShaderNodeTree")
	newGroupSockets(group,[("Albedo","NodeSocketColor"),("Roughness","NodeSocketFloat"),("Shading Normal","NodeSocketVector"),("ATOS G","NodeSocketFloat"),
		("TranslucentParam","NodeSocketFloat"),("Use_RimTranslucent","NodeSocketFloat"),("RimTranslucent_NormalBlend","NodeSocketFloat"),
		("RimTrasnlucent_Power","NodeSocketFloat"),("Use_AntiTranslucent_Diffuse","NodeSocketFloat")],"INPUT")
	newGroupSockets(group,[("Albedo","NodeSocketColor")],"OUTPUT")
	b = ShaderGroupBuilder(group)
	i = b.nodes.new("NodeGroupInput").outputs
	geometry = b.nodes.new("ShaderNodeNewGeometry")
	def vec(operation,x,y = None,scale = None):
		node = b.nodes.new("ShaderNodeVectorMath");node.operation = operation
		b._set(node.inputs[0],x)
		if y != None:b._set(node.inputs[1],y)
		if scale != None:b._set(node.inputs["Scale"],scale)
		return node.outputs["Value" if operation == "DOT_PRODUCT" else "Vector"]
	n = geometry.outputs["Normal"]
	blended = vec("NORMALIZE",vec("ADD",n,vec("SCALE",vec("SUBTRACT",i["Shading Normal"],n),scale = i["RimTranslucent_NormalBlend"])))
	t = b.math("MULTIPLY",i["TranslucentParam"],i["ATOS G"])
	rim = b.math("MULTIPLY",t,b.math("POWER",b.math("SUBTRACT",1.0,b.math("ABSOLUTE",vec("DOT_PRODUCT",blended,geometry.outputs["Incoming"]))),i["RimTrasnlucent_Power"]))
	trans = b.lerp(t,rim,i["Use_RimTranslucent"])
	divisor = b.math("MULTIPLY_ADD",i["Roughness"],-0.23,0.78)
	on = b.math("SUBTRACT",1.0,b.math("COMPARE",i["Use_AntiTranslucent_Diffuse"],0.0,0.0))
	albedo = b.separate(i["Albedo"])
	channels = []
	for c in ("Red","Green","Blue"):
		boosted = b.math("MULTIPLY_ADD",b.math("SUBTRACT",b.math("DIVIDE",albedo[c],divisor),albedo[c]),trans,albedo[c])
		channels.append(b.select(on,boosted,albedo[c]))
	out = b.nodes.new("NodeGroupOutput")
	b.links.new(b.combineColor(*channels),out.inputs["Albedo"])
	return group

def addMHWildsAntiTranslucentNodes(nodeTree,matInfo,bsdf):
	props = matInfo["mPropDict"]
	albedo,roughness = matInfo["albedoNodeLayerGroup"],matInfo["roughnessNodeLayerGroup"]
	if matInfo["gameName"] != "MHWILDS" or "Use_AntiTranslucent_Diffuse" not in props or albedo.currentOutSocket == None:
		return None
	if not hasLoadedImage(matInfo,"AlphaTranslucentOcclusionSSSMap"):
		return None
	node = nodeTree.nodes.new("ShaderNodeGroup")
	node.node_tree = getMHWildsAntiTranslucentNodeGroup()
	node.name = "MHWilds AntiTranslucent Diffuse"
	links = nodeTree.links
	links.new(albedo.currentOutSocket,node.inputs["Albedo"])
	if roughness.currentOutSocket != None:
		links.new(roughness.currentOutSocket,node.inputs["Roughness"])
	else:
		node.inputs["Roughness"].default_value = bsdf.inputs["Roughness"].default_value
	if bsdf.inputs["Normal"].is_linked:
		links.new(bsdf.inputs["Normal"].links[0].from_socket,node.inputs["Shading Normal"])
	else:
		links.new(nodeTree.nodes.new("ShaderNodeNewGeometry").outputs["Normal"],node.inputs["Shading Normal"])
	atos = matInfo["textureNodeDict"]["AlphaTranslucentOcclusionSSSMap"]
	separate = nodeTree.nodes.new("ShaderNodeSeparateColor")
	links.new(atos.outputs["Color"],separate.inputs["Color"])
	links.new(separate.outputs["Green"],node.inputs["ATOS G"])
	for name,default in (("TranslucentParam",0.0),("Use_RimTranslucent",0.0),("RimTranslucent_NormalBlend",0.0),("RimTrasnlucent_Power",1.0),("Use_AntiTranslucent_Diffuse",0.0)):
		linkMHWildsProp(nodeTree,matInfo,name,node.inputs[name],default)
	albedo.currentOutSocket = node.outputs["Albedo"]
	return node

def getMHWildsParallaxEmitUVNodeGroup(nodeTree):
	#ParallaxEmit UV, VFXwe PS #63 %412..%443: Tp = cross(n, B), Bp = cross(n, Tp), h = -ParallaxEmit_Height (the per frame dither around it averages out)
	#uv = (uv0.x + h*dot(I,Tp), uv0.y - h*dot(I,Bp)) in D3D space with I = camera to surface, so Blender V gets + h*dot(I,Bp)
	if "MHWildsParallaxEmitUV" in bpy.data.node_groups:
		nodeGroup = bpy.data.node_groups["MHWildsParallaxEmitUV"]
	else:
		nodeGroup = bpy.data.node_groups.new(type="ShaderNodeTree", name="MHWildsParallaxEmitUV")
		newGroupSockets(nodeGroup,[("UV","NodeSocketVector"),("Direction","NodeSocketVector"),("Bitangent","NodeSocketVector"),("ParallaxEmit_Height","NodeSocketFloat")],"INPUT")
		newGroupSockets(nodeGroup,[("Vector","NodeSocketVector")],"OUTPUT")
		b = ShaderGroupBuilder(nodeGroup)
		i = b.nodes.new('NodeGroupInput').outputs
		def vector(operation,a,c):
			node = b.nodes.new("ShaderNodeVectorMath")
			node.operation = operation
			b.links.new(a,node.inputs[0])
			b.links.new(c,node.inputs[1])
			return node.outputs["Value" if operation == "DOT_PRODUCT" else "Vector"]
		geometryNode = b.nodes.new("ShaderNodeNewGeometry")
		scaleNode = b.nodes.new("ShaderNodeVectorMath")
		scaleNode.operation = "SCALE"
		scaleNode.inputs["Scale"].default_value = -1.0
		b.links.new(geometryNode.outputs["Incoming"],scaleNode.inputs[0])
		cameraToSurface = scaleNode.outputs["Vector"]
		tangentP = vector("CROSS_PRODUCT",i["Direction"],i["Bitangent"])
		bitangentP = vector("CROSS_PRODUCT",i["Direction"],tangentP)
		h = b.math("MULTIPLY",i["ParallaxEmit_Height"],-1.0)
		uv = b.separateXYZ(i["UV"])
		u = b.math("MULTIPLY_ADD",h,vector("DOT_PRODUCT",cameraToSurface,tangentP),uv["X"])
		v = b.math("MULTIPLY_ADD",h,vector("DOT_PRODUCT",cameraToSurface,bitangentP),uv["Y"])
		outNode = b.nodes.new('NodeGroupOutput')
		outNode.location = (b.x + 200,0)
		b.links.new(b.combineXYZ(u,v,0.0),outNode.inputs["Vector"])
	nodeGroupNode = nodeTree.nodes.new("ShaderNodeGroup")
	nodeGroupNode.node_tree = nodeGroup
	return nodeGroupNode

def getMHWildsBlendNormalNodeGroup(nodeTree):
	#SkinEdit BlendNormalMap, Base_ATOS_SkinEdit_VFX PS #61 %431..%464
	#P = NormalBlendParam, P > 0: n.xy += 2P*(BlendNormalMap.RG - 128/255), P < 0: n.xy -= 2P*(BlendNormalMap.BA - 128/255), then normalize with the base z
	if "MHWildsBlendNormal" in bpy.data.node_groups:
		nodeGroup = bpy.data.node_groups["MHWildsBlendNormal"]
	else:
		nodeGroup = bpy.data.node_groups.new(type="ShaderNodeTree", name="MHWildsBlendNormal")
		newGroupSockets(nodeGroup,[("Base Normal Color","NodeSocketColor"),("BlendNormalMap","NodeSocketColor"),("BlendNormalMap Alpha","NodeSocketFloat"),("NormalBlendParam","NodeSocketFloat")],"INPUT")
		newGroupSockets(nodeGroup,[("Color","NodeSocketColor")],"OUTPUT")
		b = ShaderGroupBuilder(nodeGroup)
		i = b.nodes.new('NodeGroupInput').outputs
		base = b.separate(i["Base Normal Color"])
		bx,by,bz = b.normalize3(b.math("MULTIPLY_ADD",base["Red"],2.0,-1.0),b.math("MULTIPLY_ADD",base["Green"],2.0,-1.0),b.math("MULTIPLY_ADD",base["Blue"],2.0,-1.0))
		blend = b.separate(i["BlendNormalMap"])
		param = i["NormalBlendParam"]
		positive = b.math("GREATER_THAN",param,0.0)
		offsetX = b.select(positive,blend["Red"],blend["Blue"])
		offsetY = b.select(positive,blend["Green"],i["BlendNormalMap Alpha"])
		scale = b.math("MULTIPLY",b.math("ABSOLUTE",param),2.0)
		nx,ny,nz = b.normalize3(b.math("MULTIPLY_ADD",b.math("SUBTRACT",offsetX,128.0/255.0),scale,bx),b.math("MULTIPLY_ADD",b.math("SUBTRACT",offsetY,128.0/255.0),scale,by),bz)
		outNode = b.nodes.new('NodeGroupOutput')
		outNode.location = (b.x + 200,0)
		b.links.new(b.combineColor(b.math("MULTIPLY_ADD",nx,0.5,0.5),b.math("MULTIPLY_ADD",ny,0.5,0.5),b.math("MULTIPLY_ADD",nz,0.5,0.5)),outNode.inputs["Color"])
	nodeGroupNode = nodeTree.nodes.new("ShaderNodeGroup")
	nodeGroupNode.node_tree = nodeGroup
	return nodeGroupNode

def mhWildsPropValue(props,name,default = 0.0,index = 0):
	return float(props[name].propValue[index]) if name in props else default

def mhWildsMultiBlendIndices(props):
	count = mhWildsPropValue(props,"Blend_num")
	indices = []
	for index in range(32):
		name = "Blend_"+chr(65+index//4)
		if index < count and name in props and len(props[name].propValue) > index%4 and props[name].propValue[index%4] != 0.0:
			indices.append(index)
	return indices

def mhWildsTextureNeeded(textureType,props):
	#Textures that only matter when the material turns the matching feature on, None means no special rule
	value = lambda name,default = 0.0: mhWildsPropValue(props,name,default)
	if textureType in ("MultiBlend_ALBDMap","MultiBlend_NRMMap"):
		return bool(mhWildsMultiBlendIndices(props))
	fakeRefraction = value("FakeRefraction_Blend") != 0.0
	if textureType == "PanoramaMap":
		return fakeRefraction
	if textureType == "FxMap":
		animWave = value("AnimEmit_Min",1.0) != 1.0 and value("UseWaveEmit") != 0.0
		secWave = value("SecEmit_Anim_Min",1.0) != 1.0 and value("SecEmit_Anim_UseWaveEmit") != 0.0
		return fakeRefraction or mhWildsFilmActive(props) or value("Use_MoveEmit") > 0.0 or animWave or secWave
	if textureType == "VectorEmitMap":
		return value("UseVectorEmit") > 0.0 or value("UseParallaxEmit") > 0.0
	if textureType == "BlendNormalMap":
		return value("NormalBlendParam") != 0.0
	return None

def addMHWildsBlendNormalNodes(nodeTree,matInfo):
	props = matInfo["mPropDict"]
	param = mhWildsPropValue(props,"NormalBlendParam")
	if param == 0.0 or not hasLoadedImage(matInfo,"BlendNormalMap") or matInfo["normalNodeLayerGroup"].currentOutSocket == None:
		return
	nodes = nodeTree.nodes
	links = nodeTree.links
	blendNode = matInfo["textureNodeDict"]["BlendNormalMap"]
	if "UVMap1Node" in nodes:#Always the first UV
		links.new(nodes["UVMap1Node"].outputs["UV"],blendNode.inputs["Vector"])
	groupNode = getMHWildsBlendNormalNodeGroup(nodeTree)
	groupNode.location = blendNode.location + Vector((300,0))
	links.new(matInfo["normalNodeLayerGroup"].currentOutSocket,groupNode.inputs["Base Normal Color"])
	links.new(blendNode.outputs["Color"],groupNode.inputs["BlendNormalMap"])
	links.new(blendNode.outputs["Alpha"],groupNode.inputs["BlendNormalMap Alpha"])
	linkMHWildsProp(nodeTree,matInfo,"NormalBlendParam",groupNode.inputs["NormalBlendParam"],param)
	matInfo["normalNodeLayerGroup"].currentOutSocket = groupNode.outputs["Color"]

def getMHWildsFxMapSeparateNode(nodeTree,matInfo):
	nodes = nodeTree.nodes
	if "FxMapSepNode" in nodes:
		return nodes["FxMapSepNode"]
	fxNode = matInfo["textureNodeDict"]["FxMap"]
	fxSepNode = nodes.new("ShaderNodeSeparateColor")
	fxSepNode.name = "FxMapSepNode"
	fxSepNode.location = fxNode.location + Vector((300,0))
	nodeTree.links.new(fxNode.outputs["Color"],fxSepNode.inputs["Color"])
	return fxSepNode

def addMHWildsEmissiveNodes(nodeTree,matInfo):
	#VectorEmit, ParallaxEmit, MoveEmit, AnimEmit/WaveEmit and SecEmit on top of the EmissiveMap setup from newEMINode
	props = matInfo["mPropDict"]
	if not hasLoadedImage(matInfo,"EmissiveMap"):
		return
	nodes = nodeTree.nodes
	links = nodeTree.links
	value = lambda name,default = 0.0: mhWildsPropValue(props,name,default)
	emissiveNode = matInfo["textureNodeDict"]["EmissiveMap"]
	location = emissiveNode.location + Vector((0,-700))
	fxB = None
	if hasLoadedImage(matInfo,"FxMap"):
		fxB = getMHWildsFxMapSeparateNode(nodeTree,matInfo).outputs["Blue"]

	#VectorEmit direction is computed whenever the map is loaded, ParallaxEmit reuses it
	vectorEmitNode = None
	if hasLoadedImage(matInfo,"VectorEmitMap") and (value("UseVectorEmit") > 0.0 or value("UseParallaxEmit") > 0.0):
		vectorEmitMapNode = matInfo["textureNodeDict"]["VectorEmitMap"]
		vectorEmitMapNode.image.colorspace_settings.name = "Non-Color"
		vectorEmitNode = getMHWildsVectorEmitNodeGroup(nodeTree)
		vectorEmitNode.location = vectorEmitMapNode.location + Vector((300,0))
		links.new(vectorEmitMapNode.outputs["Color"],vectorEmitNode.inputs["VectorEmitMap"])
		linkMHWildsProp(nodeTree,matInfo,"VectorEmit_power",vectorEmitNode.inputs["VectorEmit_power"],6.0)

	#ParallaxEmit: a second EmissiveMap sample at the shifted UV, blended by ParallaxEmit_Blend (fraction of dithered pixels that use the shift)
	emissiveColor = emissiveNode.outputs["Color"]
	emissiveAlpha = emissiveNode.outputs["Alpha"]
	if vectorEmitNode != None and value("UseParallaxEmit") > 0.0 and "UVMap1Node" in nodes and emissiveNode.bl_idname == "ShaderNodeTexImage":
		blendClampNode = nodes.new("ShaderNodeClamp")#Fraction of dithered pixels that take the shifted sample
		blendClampNode.location = location + Vector((450,200))
		linkMHWildsProp(nodeTree,matInfo,"ParallaxEmit_Blend",blendClampNode.inputs["Value"],0.0)
		#Shifted pixels (dither d <= Blend) use h = Blur*(d - 0.5) - Height (MultiBlend #57 %714..%719, eye #59 same).
		#TAA averages d, so the shifted sample is the mean over d in [0, Blend]: PARALLAX_BLUR_TAPS midpoint taps.
		taps = PARALLAX_BLUR_TAPS if "ParallaxEmit_Blur" in props else 1
		parallaxNodes = []
		for tap in range(taps):
			parallaxUVNode = getMHWildsParallaxEmitUVNodeGroup(nodeTree)
			parallaxUVNode.location = location + Vector((0,-250*tap))
			links.new(nodes["UVMap1Node"].outputs["UV"],parallaxUVNode.inputs["UV"])
			links.new(vectorEmitNode.outputs["Direction"],parallaxUVNode.inputs["Direction"])
			links.new(vectorEmitNode.outputs["Bitangent"],parallaxUVNode.inputs["Bitangent"])
			if taps == 1:
				linkMHWildsProp(nodeTree,matInfo,"ParallaxEmit_Height",parallaxUVNode.inputs["ParallaxEmit_Height"],0.0)
			else:
				#The UV group applies h = -height, so height = Height - Blur*(d - 0.5) with d = Blend*(tap + 0.5)/taps
				d = nodes.new("ShaderNodeMath");d.operation = "MULTIPLY";d.inputs[1].default_value = (tap+0.5)/taps
				links.new(blendClampNode.outputs["Result"],d.inputs[0])
				jitter = nodes.new("ShaderNodeMath");jitter.operation = "MULTIPLY"
				centered = nodes.new("ShaderNodeMath");centered.operation = "SUBTRACT";centered.inputs[1].default_value = 0.5
				links.new(d.outputs["Value"],centered.inputs[0]);links.new(centered.outputs["Value"],jitter.inputs[0])
				linkMHWildsProp(nodeTree,matInfo,"ParallaxEmit_Blur",jitter.inputs[1],0.0)
				height = nodes.new("ShaderNodeMath");height.operation = "SUBTRACT"
				linkMHWildsProp(nodeTree,matInfo,"ParallaxEmit_Height",height.inputs[0],0.0)
				links.new(jitter.outputs["Value"],height.inputs[1])
				links.new(height.outputs["Value"],parallaxUVNode.inputs["ParallaxEmit_Height"])
			tapNode = nodes.new("ShaderNodeTexImage")
			tapNode.name = "EmissiveMap_Parallax" if tap == 0 else f"EmissiveMap_Parallax{tap}"
			tapNode.label = "EmissiveMap (ParallaxEmit)"
			tapNode.image = emissiveNode.image
			tapNode.location = location + Vector((300,-250*tap))
			links.new(parallaxUVNode.outputs["Vector"],tapNode.inputs["Vector"])
			parallaxNodes.append(tapNode)
		parallaxColor,parallaxAlpha = parallaxNodes[0].outputs["Color"],parallaxNodes[0].outputs["Alpha"]
		if taps > 1:
			colorSum = nodes.new("ShaderNodeGroup");colorSum.node_tree = getAverageNodeGroup(taps);colorSum.location = location + Vector((450,-100))
			for tap,tapNode in enumerate(parallaxNodes):
				links.new(tapNode.outputs["Color"],colorSum.inputs[2*tap]);links.new(tapNode.outputs["Alpha"],colorSum.inputs[2*tap+1])
			parallaxColor,parallaxAlpha = colorSum.outputs["Color"],colorSum.outputs["Alpha"]
		mixColorNode = nodes.new("ShaderNodeMixRGB")
		mixColorNode.location = location + Vector((600,0))
		links.new(blendClampNode.outputs["Result"],mixColorNode.inputs["Fac"])
		links.new(emissiveNode.outputs["Color"],mixColorNode.inputs["Color1"])
		links.new(parallaxColor,mixColorNode.inputs["Color2"])
		mixAlphaNode = nodes.new("ShaderNodeMath")
		mixAlphaNode.operation = "MULTIPLY_ADD"
		mixAlphaNode.location = location + Vector((600,-200))
		subNode = nodes.new("ShaderNodeMath")
		subNode.operation = "SUBTRACT"
		subNode.location = location + Vector((450,-200))
		links.new(parallaxAlpha,subNode.inputs[0])
		links.new(emissiveNode.outputs["Alpha"],subNode.inputs[1])
		links.new(subNode.outputs["Value"],mixAlphaNode.inputs[0])
		links.new(blendClampNode.outputs["Result"],mixAlphaNode.inputs[1])
		links.new(emissiveNode.outputs["Alpha"],mixAlphaNode.inputs[2])
		#Everything that read the plain sample now reads the blended one
		for link in list(emissiveNode.outputs["Color"].links):
			if link.to_node != mixColorNode:
				links.new(mixColorNode.outputs["Color"],link.to_socket)
		emissiveColor = mixColorNode.outputs["Color"]
		emissiveAlpha = mixAlphaNode.outputs["Value"]
		location = location + Vector((0,-400))

	strengthFactors = []
	vectorEmitFactor = None
	if vectorEmitNode != None and value("UseVectorEmit") > 0.0:
		vectorEmitFactor = vectorEmitNode.outputs["Factor"]
		strengthFactors.append(vectorEmitFactor)

	timeNode = None
	if value("Use_MoveEmit") > 0.0:
		moveNode = getMHWildsMoveEmitNodeGroup(nodeTree)
		moveNode.location = location
		for name,default in (("MoveEmit",0.0),("MoveEmit_Width",0.5),("Use_WaveMove",0.0)):
			linkMHWildsProp(nodeTree,matInfo,name,moveNode.inputs[name],default)
		if fxB != None:
			links.new(fxB,moveNode.inputs["FxMap B"])
		strengthFactors.append(moveNode.outputs["Factor"])
	elif value("AnimEmit_Min",1.0) != 1.0:
		timeNode = getMHWildsTimeNodeGroup(nodeTree)
		timeNode.location = location + Vector((-300,0))
		animNode = getMHWildsAnimEmitNodeGroup(nodeTree)
		animNode.label = "AnimEmit"
		animNode.location = location
		links.new(timeNode.outputs["Seconds"],animNode.inputs["Seconds"])
		for socketName,propName,default in (("Min","AnimEmit_Min",1.0),("Speed","AnimEmit_Speed",1.0),("UseWave","UseWaveEmit",0.0),("Wave","AnimEmitWave",1.0)):
			linkMHWildsProp(nodeTree,matInfo,propName,animNode.inputs[socketName],default)
		if fxB != None:
			links.new(fxB,animNode.inputs["FxMap B"])
		strengthFactors.append(animNode.outputs["Factor"])

	targetGroup = matInfo["emissionStrengthNodeLayerGroup"] if matInfo["emissionStrengthNodeLayerGroup"].currentOutSocket != None else matInfo["emissionColorNodeLayerGroup"]
	if targetGroup.currentOutSocket != None:
		for factor in strengthFactors:
			targetGroup.addMixLayer(factor,factorOutSocket = None,mixType = "MULTIPLY",mixFactor = 1.0)

	#SecEmit: + 2 * EmissiveMap.A * SecondaryEmitColor (after VectorEmit), not scaled by the main emissive params, so it gets its own emission shader
	secondaryColor = [mhWildsPropValue(props,"SecondaryEmitColor",0.0,index) for index in range(3)] if "SecondaryEmitColor" in props else [0.0,0.0,0.0]
	if max(secondaryColor) > 0.0:
		secLocation = location + Vector((0,-400))
		maskSocket = emissiveAlpha
		if vectorEmitFactor != None:
			maskMultNode = nodes.new("ShaderNodeMath")
			maskMultNode.operation = "MULTIPLY"
			maskMultNode.location = secLocation
			links.new(emissiveAlpha,maskMultNode.inputs[0])
			links.new(vectorEmitFactor,maskMultNode.inputs[1])
			maskSocket = maskMultNode.outputs["Value"]
		strengthNode = nodes.new("ShaderNodeMath")
		strengthNode.operation = "MULTIPLY"
		strengthNode.location = secLocation + Vector((200,0))
		links.new(maskSocket,strengthNode.inputs[0])
		strengthNode.inputs[1].default_value = 2.0 * EMISSION_MULTIPLIER
		strengthSocket = strengthNode.outputs["Value"]
		if value("SecEmit_Anim_Min",1.0) != 1.0:
			if timeNode == None:
				timeNode = getMHWildsTimeNodeGroup(nodeTree)
				timeNode.location = secLocation + Vector((-300,-200))
			secAnimNode = getMHWildsAnimEmitNodeGroup(nodeTree)
			secAnimNode.label = "SecEmit Anim"
			secAnimNode.location = secLocation + Vector((0,-200))
			links.new(timeNode.outputs["Seconds"],secAnimNode.inputs["Seconds"])
			for socketName,propName,default in (("Min","SecEmit_Anim_Min",1.0),("Speed","SecEmit_Anim_Speed",1.0),("UseWave","SecEmit_Anim_UseWaveEmit",0.0),("Wave","SecEmit_Anim_Wave",1.0)):
				linkMHWildsProp(nodeTree,matInfo,propName,secAnimNode.inputs[socketName],default)
			if fxB != None:
				links.new(fxB,secAnimNode.inputs["FxMap B"])
			secMultNode = nodes.new("ShaderNodeMath")
			secMultNode.operation = "MULTIPLY"
			secMultNode.location = secLocation + Vector((400,0))
			links.new(strengthSocket,secMultNode.inputs[0])
			links.new(secAnimNode.outputs["Factor"],secMultNode.inputs[1])
			strengthSocket = secMultNode.outputs["Value"]
		secEmissionNode = nodes.new("ShaderNodeEmission")
		secEmissionNode.label = "SecEmit"
		secEmissionNode.location = secLocation + Vector((600,0))
		linkMHWildsProp(nodeTree,matInfo,"SecondaryEmitColor",secEmissionNode.inputs["Color"],(secondaryColor[0],secondaryColor[1],secondaryColor[2],1.0),output = "Color")
		links.new(strengthSocket,secEmissionNode.inputs["Strength"])
		addShaderNode = nodes.new("ShaderNodeAddShader")
		addShaderNode.location = (600,-400)
		links.new(matInfo["currentShaderOutput"],addShaderNode.inputs[0])
		links.new(secEmissionNode.outputs["Emission"],addShaderNode.inputs[1])
		matInfo["currentShaderOutput"] = addShaderNode.outputs["Shader"]

def setMHWildsMaterialAnimation(enabled):
	if MHWILDS_TIME_GROUP not in bpy.data.node_groups:
		return False
	nodeGroup = bpy.data.node_groups[MHWILDS_TIME_GROUP]
	nodeGroup.nodes["Animate"].outputs[0].default_value = 1.0 if enabled else 0.0
	nodeGroup.update_tag()
	return True

def getMHWildsMaterialAnimation():
	if MHWILDS_TIME_GROUP not in bpy.data.node_groups or "Animate" not in bpy.data.node_groups[MHWILDS_TIME_GROUP].nodes:
		return None
	return bpy.data.node_groups[MHWILDS_TIME_GROUP].nodes["Animate"].outputs[0].default_value > 0.0

def addMHWildsColorLayerNodes(nodeTree,matInfo):
	#Runs after all texture nodes exist, the shader applies it on top of the finished base color
	props = matInfo["mPropDict"]
	if not hasLoadedImage(matInfo,"ColorLayer_MaskMap") or matInfo["albedoNodeLayerGroup"].currentOutSocket == None:
		return
	if not all(f"ColorLayer_{channel}" in props for channel in ("R","G","B","A")):
		return
	links = nodeTree.links
	maskNode = matInfo["textureNodeDict"]["ColorLayer_MaskMap"]
	groupNode = getMHWildsColorLayerNodeGroup(nodeTree)
	groupNode.location = maskNode.location + Vector((600,0))
	links.new(maskNode.outputs["Color"],groupNode.inputs["Mask"])
	links.new(maskNode.outputs["Alpha"],groupNode.inputs["MaskAlpha"])
	for channel in ("R","G","B","A"):
		propNode = addPropertyNode(props[f"ColorLayer_{channel}"], matInfo["currentPropPos"], nodeTree)
		links.new(propNode.outputs[0],groupNode.inputs[f"ColorLayer_{channel}"])
		links.new(propNode.outputs["Alpha"] if "Alpha" in propNode.outputs else propNode.outputs[3],groupNode.inputs[f"ColorLayer_{channel}_Alpha"])
	for propName,socketName in (("ColorLayer_Mask_Width","Width"),("ColorLayer_Mask_Fade","Fade"),("ColorLayer_Roughness","Roughness")):
		if propName in props:
			propNode = addPropertyNode(props[propName], matInfo["currentPropPos"], nodeTree)
			if "Color" in propNode.outputs:
				links.new(propNode.outputs["Color"],groupNode.inputs[socketName])
				links.new(propNode.outputs["Alpha"],groupNode.inputs[socketName+"A"])
			else:#Vec4
				combineNode = nodeTree.nodes.new("ShaderNodeCombineColor")
				combineNode.location = propNode.location + Vector((300,0))
				for index in range(3):
					links.new(propNode.outputs[index],combineNode.inputs[index])
				links.new(combineNode.outputs["Color"],groupNode.inputs[socketName])
				links.new(propNode.outputs[3],groupNode.inputs[socketName+"A"])
	if hasLoadedImage(matInfo,"ColorLayer_DetailMaskMap") and "ColorLayer_DetailMask_Blend" in props:
		#Sampled on the plain first UV times ColorLayer_DetailMask_Tile
		detailMaskNode = matInfo["textureNodeDict"]["ColorLayer_DetailMaskMap"]
		detailMaskNode.image.colorspace_settings.name = "Non-Color"
		detailUVNode = getMHWildsDetailUVNodeGroup(nodeTree)
		detailUVNode.location = detailMaskNode.location + Vector((-300,0))
		if "UVMap1Node" in nodeTree.nodes:
			links.new(nodeTree.nodes["UVMap1Node"].outputs["UV"],detailUVNode.inputs["UV"])
		linkMHWildsProp(nodeTree,matInfo,"ColorLayer_DetailMask_Tile",detailUVNode.inputs["DetailTile"],1.0)
		links.new(detailUVNode.outputs["Vector"],detailMaskNode.inputs["Vector"])
		links.new(detailMaskNode.outputs["Color"],groupNode.inputs["Detail Mask"])
		links.new(detailMaskNode.outputs["Alpha"],groupNode.inputs["Detail Mask Alpha"])
		linkMHWildsProp(nodeTree,matInfo,"ColorLayer_DetailMask_Blend",groupNode.inputs["ColorLayer_DetailMask_Blend"],0.0)
	if "UseOverRay_ColorLayer" in props:
		links.new(addPropertyNode(props["UseOverRay_ColorLayer"], matInfo["currentPropPos"], nodeTree).outputs["Value"],groupNode.inputs["UseOverRay"])
	links.new(matInfo["albedoNodeLayerGroup"].currentOutSocket,groupNode.inputs["Base"])
	matInfo["albedoNodeLayerGroup"].currentOutSocket = groupNode.outputs["Color"]
	matInfo["roughnessNodeLayerGroup"].addMixLayer(groupNode.outputs["Roughness"],factorOutSocket = None,mixType = "MULTIPLY",mixFactor = 1.0)

def addMHWildsPanoramaNodes(nodeTree,matInfo,mappedNormalSocket = None):
	#color = lerp(color, 2*color*Panorama.rgb, FakeRefraction_Blend * FxMap.G), before lighting
	props = matInfo["mPropDict"]
	if not hasLoadedImage(matInfo,"PanoramaMap") or "FakeRefraction_Blend" not in props or props["FakeRefraction_Blend"].propValue[0] == 0.0:
		return
	if matInfo["albedoNodeLayerGroup"].currentOutSocket == None:
		return
	nodes = nodeTree.nodes
	links = nodeTree.links
	panoramaNode = matInfo["textureNodeDict"]["PanoramaMap"]
	if hasattr(panoramaNode,"image") and panoramaNode.image != None:
		panoramaNode.image.colorspace_settings.name = "sRGB"
	uvGroupNode = getMHWildsPanoramaUVNodeGroup(nodeTree)
	uvGroupNode.location = panoramaNode.location + Vector((-300,0))
	if mappedNormalSocket != None:
		links.new(mappedNormalSocket,uvGroupNode.inputs["Normal"])
	else:
		if "geometryNode" not in nodes:
			geometryNode = nodes.new("ShaderNodeNewGeometry")
			geometryNode.name = "geometryNode"
			geometryNode.location = (-800,400)
		links.new(nodes["geometryNode"].outputs["Normal"],uvGroupNode.inputs["Normal"])
	if "Refraction_Index" in props:
		links.new(addPropertyNode(props["Refraction_Index"], matInfo["currentPropPos"], nodeTree).outputs["Value"],uvGroupNode.inputs["Refraction_Index"])
	links.new(uvGroupNode.outputs["Vector"],panoramaNode.inputs["Vector"])

	weightNode = nodes.new("ShaderNodeMath")
	weightNode.operation = "MULTIPLY"
	weightNode.location = panoramaNode.location + Vector((300,-250))
	links.new(addPropertyNode(props["FakeRefraction_Blend"], matInfo["currentPropPos"], nodeTree).outputs["Value"],weightNode.inputs[0])
	if "FxMap" in matInfo["textureNodeDict"]:
		fxSepNode = nodes.new("ShaderNodeSeparateColor")
		fxSepNode.location = matInfo["textureNodeDict"]["FxMap"].location + Vector((300,0))
		links.new(matInfo["textureNodeDict"]["FxMap"].outputs["Color"],fxSepNode.inputs["Color"])
		links.new(fxSepNode.outputs["Green"],weightNode.inputs[1])
	else:
		weightNode.inputs[1].default_value = 1.0

	multNode = nodes.new("ShaderNodeVectorMath")
	multNode.operation = "MULTIPLY"
	multNode.location = panoramaNode.location + Vector((300,0))
	links.new(matInfo["albedoNodeLayerGroup"].currentOutSocket,multNode.inputs[0])
	links.new(panoramaNode.outputs["Color"],multNode.inputs[1])
	scaleNode = nodes.new("ShaderNodeVectorMath")
	scaleNode.operation = "SCALE"
	scaleNode.location = panoramaNode.location + Vector((500,0))
	links.new(multNode.outputs["Vector"],scaleNode.inputs[0])
	scaleNode.inputs["Scale"].default_value = 2.0
	matInfo["albedoNodeLayerGroup"].addMixLayer(scaleNode.outputs["Vector"],factorOutSocket = weightNode.outputs["Value"],mixType = "MIX")

def addMHWildsFakeSphereNodes(nodeTree,matInfo,mappedNormalSocket = None):
	#MH Wilds view space normal lookups (matcap style), added before AO and lighting like the shaders do
	nodes = nodeTree.nodes
	links = nodeTree.links
	if "geometryNode" in nodes:
		geometryNode = nodes["geometryNode"]
	else:
		geometryNode = nodes.new("ShaderNodeNewGeometry")
		geometryNode.name = "geometryNode"
		geometryNode.location = (-800,400)

	#FakeSphere_ALBAMap: color += sphere.rgb * FakeHighLight_Color.rgb
	#BaseAlpha_MatCap_FX also adds sphere.a * FakeHighLight_Color.a to alpha and uses the normal mapped normal
	#Base_eyeRefract_Emit uses the geometric normal and only RGB
	#BaseAlpha_Emit_RoughTransparent binds the same slot and params but its shader was not traced, it gets the eye variant
	if hasLoadedImage(matInfo,"FakeSphere_ALBAMap"):
		sphereNode = matInfo["textureNodeDict"]["FakeSphere_ALBAMap"]
		isMatCap = matInfo["mmtrName"].startswith("basealpha_matcap_fx")
		if hasattr(sphereNode,"image") and sphereNode.image != None:
			sphereNode.image.colorspace_settings.name = "sRGB"
			sphereNode.extension = "EXTEND"#AutomaticClamp sampler

		uvGroupNode = getMHWildsFakeSphereUVNodeGroup(nodeTree)
		uvGroupNode.location = sphereNode.location + Vector((-300,0))
		links.new(mappedNormalSocket if isMatCap and mappedNormalSocket != None else geometryNode.outputs["Normal"],uvGroupNode.inputs["Normal"])
		if "FakeHighLight_Position" in matInfo["mPropDict"]:
			positionNode = addPropertyNode(matInfo["mPropDict"]["FakeHighLight_Position"], matInfo["currentPropPos"], nodeTree)
			if "Color" in positionNode.outputs:
				links.new(positionNode.outputs["Color"],uvGroupNode.inputs["Position"])
			else:#Vec4
				positionCombineNode = nodes.new("ShaderNodeCombineColor")
				positionCombineNode.location = uvGroupNode.location + Vector((-300,0))
				for index in range(3):
					links.new(positionNode.outputs[index],positionCombineNode.inputs[index])
				links.new(positionCombineNode.outputs["Color"],uvGroupNode.inputs["Position"])
		if "FakeHighLight_ScaleOffset" in matInfo["mPropDict"]:
			scaleOffsetNode = addPropertyNode(matInfo["mPropDict"]["FakeHighLight_ScaleOffset"], matInfo["currentPropPos"], nodeTree)
			for index,socketName in enumerate(("ScaleX","ScaleY","OffsetX","OffsetY")):
				links.new(scaleOffsetNode.outputs[index],uvGroupNode.inputs[socketName])
		links.new(uvGroupNode.outputs["Vector"],sphereNode.inputs["Vector"])

		sphereColorSocket = sphereNode.outputs["Color"]
		sphereAlphaSocket = sphereNode.outputs["Alpha"]
		if "FakeHighLight_Color" in matInfo["mPropDict"]:
			tintNode = addPropertyNode(matInfo["mPropDict"]["FakeHighLight_Color"], matInfo["currentPropPos"], nodeTree)
			tintMultNode = nodes.new("ShaderNodeMixRGB")
			tintMultNode.location = sphereNode.location + Vector((300,0))
			tintMultNode.blend_type = "MULTIPLY"
			tintMultNode.inputs["Fac"].default_value = 1.0
			links.new(sphereColorSocket,tintMultNode.inputs["Color1"])
			links.new(tintNode.outputs["Color"],tintMultNode.inputs["Color2"])
			sphereColorSocket = tintMultNode.outputs["Color"]

			alphaMultNode = nodes.new("ShaderNodeMath")
			alphaMultNode.location = sphereNode.location + Vector((300,-200))
			alphaMultNode.operation = "MULTIPLY"
			links.new(sphereAlphaSocket,alphaMultNode.inputs[0])
			links.new(tintNode.outputs["Alpha"],alphaMultNode.inputs[1])
			sphereAlphaSocket = alphaMultNode.outputs["Value"]
		matInfo["albedoNodeLayerGroup"].addMixLayer(sphereColorSocket,factorOutSocket = None,mixType = "ADD",mixFactor = 1.0)

		if isMatCap and matInfo["alphaSocket"] != None:
			alphaAddNode = nodes.new("ShaderNodeMath")
			alphaAddNode.location = sphereNode.location + Vector((600,-200))
			alphaAddNode.operation = "ADD"
			alphaAddNode.use_clamp = True
			links.new(matInfo["alphaSocket"],alphaAddNode.inputs[0])
			links.new(sphereAlphaSocket,alphaAddNode.inputs[1])
			matInfo["alphaSocket"] = alphaAddNode.outputs["Value"]

	#ToonFakeSphereMap: emissive = 2 * color * sphere.rgb * ToonEmissiveIntensity, geometric normal, no ScaleOffset/Position
	#Traced on Base_GOLD_Push only, Base_otomo_equip_GOLD and DU_Weapon_Gold(_Wave) bind the same slot and param
	#In game the color input is the shaded color entering that branch, the albedo layer stack is used here instead
	if hasLoadedImage(matInfo,"ToonFakeSphereMap") and matInfo["albedoNodeLayerGroup"].currentOutSocket != None:
		sphereNode = matInfo["textureNodeDict"]["ToonFakeSphereMap"]
		if hasattr(sphereNode,"image") and sphereNode.image != None:
			sphereNode.image.colorspace_settings.name = "sRGB"
			sphereNode.extension = "EXTEND"

		uvGroupNode = getMHWildsFakeSphereUVNodeGroup(nodeTree)
		uvGroupNode.location = sphereNode.location + Vector((-300,0))
		links.new(geometryNode.outputs["Normal"],uvGroupNode.inputs["Normal"])
		links.new(uvGroupNode.outputs["Vector"],sphereNode.inputs["Vector"])

		colorMultNode = nodes.new("ShaderNodeMixRGB")
		colorMultNode.location = sphereNode.location + Vector((300,0))
		colorMultNode.blend_type = "MULTIPLY"
		colorMultNode.inputs["Fac"].default_value = 1.0
		links.new(matInfo["albedoNodeLayerGroup"].currentOutSocket,colorMultNode.inputs["Color1"])
		links.new(sphereNode.outputs["Color"],colorMultNode.inputs["Color2"])

		strengthNode = nodes.new("ShaderNodeMath")
		strengthNode.location = sphereNode.location + Vector((300,-250))
		strengthNode.operation = "MULTIPLY"
		strengthNode.inputs[0].default_value = 1.0
		strengthNode.inputs[1].default_value = 2.0#Vanilla ToonEmissiveIntensity is small (0.1 on ch05_071), so EMISSION_MULTIPLIER is not applied here
		if "ToonEmissiveIntensity" in matInfo["mPropDict"]:
			intensityNode = addPropertyNode(matInfo["mPropDict"]["ToonEmissiveIntensity"], matInfo["currentPropPos"], nodeTree)
			links.new(intensityNode.outputs["Value"],strengthNode.inputs[0])

		#Separate emission shader so it stacks with EmissiveMap instead of sharing its strength
		emissionNode = nodes.new("ShaderNodeEmission")
		emissionNode.location = sphereNode.location + Vector((600,0))
		links.new(colorMultNode.outputs["Color"],emissionNode.inputs["Color"])
		links.new(strengthNode.outputs["Value"],emissionNode.inputs["Strength"])

		addShaderNode = nodes.new("ShaderNodeAddShader")
		addShaderNode.location = (600,-200)
		links.new(matInfo["currentShaderOutput"],addShaderNode.inputs[0])
		links.new(emissionNode.outputs["Emission"],addShaderNode.inputs[1])
		matInfo["currentShaderOutput"] = addShaderNode.outputs["Shader"]
def newEMINode (nodeTree,textureType,matInfo):
	imageNode = nodeTree.nodes[textureType]
	currentPos = [imageNode.location[0]+300,imageNode.location[1]]
	
	matInfo["emissionColorNodeLayerGroup"].addMixLayer(imageNode.outputs["Color"])
	
	
	if "Emissive_color" in matInfo["mPropDict"]:
		emiColorNode = addPropertyNode(matInfo["mPropDict"]["Emissive_color"], matInfo["currentPropPos"], nodeTree)
		matInfo["emissionColorNodeLayerGroup"].addMixLayer(emiColorNode.outputs["Color"],mixType = "MULTIPLY",mixFactor = 1.0)
	elif "Emissive_Color" in matInfo["mPropDict"]:
		emiColorNode = addPropertyNode(matInfo["mPropDict"]["Emissive_Color"], matInfo["currentPropPos"], nodeTree)
		matInfo["emissionColorNodeLayerGroup"].addMixLayer(emiColorNode.outputs["Color"],mixType = "MULTIPLY",mixFactor = 1.0)
	elif "EmissiveColor" in matInfo["mPropDict"]:
		emiColorNode = addPropertyNode(matInfo["mPropDict"]["EmissiveColor"], matInfo["currentPropPos"], nodeTree)
		matInfo["emissionColorNodeLayerGroup"].addMixLayer(emiColorNode.outputs["Color"],mixType = "MULTIPLY",mixFactor = 1.0)
	elif "Emissive_Color1" in matInfo["mPropDict"]:
		emiColorNode = addPropertyNode(matInfo["mPropDict"]["Emissive_Color1"], matInfo["currentPropPos"], nodeTree)
		matInfo["emissionColorNodeLayerGroup"].addMixLayer(emiColorNode.outputs["Color"],mixType = "MULTIPLY",mixFactor = 1.0)
	emiIntensityNode = None
	if "Emissive_intensity" in matInfo["mPropDict"]:
		emiIntensityNode = addPropertyNode(matInfo["mPropDict"]["Emissive_intensity"], matInfo["currentPropPos"], nodeTree)
	elif "Emissive_Intensity" in matInfo["mPropDict"]:#I should have lower cased the prop dict
		emiIntensityNode = addPropertyNode(matInfo["mPropDict"]["Emissive_Intensity"], matInfo["currentPropPos"], nodeTree)
	elif "EmissiveIntensity" in matInfo["mPropDict"]:#I should have lower cased the prop dict
		emiIntensityNode = addPropertyNode(matInfo["mPropDict"]["EmissiveIntensity"], matInfo["currentPropPos"], nodeTree)
	elif "Emissive_Power" in matInfo["mPropDict"]:
		emiIntensityNode = addPropertyNode(matInfo["mPropDict"]["Emissive_Power"], matInfo["currentPropPos"], nodeTree)
	if emiIntensityNode != None:
		bwNode = nodeTree.nodes.new('ShaderNodeRGBToBW')
		bwNode.location = currentPos
		bwNode.name = "BWEMINode"
		
		currentPos[0]+=300
		
		reduceEMIMultNode = nodeTree.nodes.new('ShaderNodeMath')
		reduceEMIMultNode.location = currentPos
		reduceEMIMultNode.operation = "MULTIPLY"
		nodeTree.links.new(emiIntensityNode.outputs["Value"],reduceEMIMultNode.inputs[0])
		reduceEMIMultNode.inputs[1].default_value = EMISSION_MULTIPLIER
		if matInfo["gameName"] == "MHWILDS" and "Emissive_Intensity" in matInfo["mPropDict"] and "Emissive_Power" in matInfo["mPropDict"]:
			#Wilds DXIL unary opcode 21 is exp2: Intensity * 2^Power, before exposure compensation.
			powerProp = addPropertyNode(matInfo["mPropDict"]["Emissive_Power"], matInfo["currentPropPos"], nodeTree)
			powerNode = nodeTree.nodes.new("ShaderNodeMath")
			powerNode.name = "MHWilds Emissive Power"
			powerNode.operation = "POWER"
			powerNode.inputs[0].default_value = 2.0
			nodeTree.links.new(powerProp.outputs["Value"],powerNode.inputs[1])
			scaleNode = nodeTree.nodes.new("ShaderNodeMath")
			scaleNode.operation = "MULTIPLY"
			scaleNode.inputs[1].default_value = EMISSION_MULTIPLIER
			nodeTree.links.new(powerNode.outputs["Value"],scaleNode.inputs[0])
			nodeTree.links.new(scaleNode.outputs["Value"],reduceEMIMultNode.inputs[1])
		
		currentPos[0]+=300
		nodeTree.links.new(imageNode.outputs["Color"],bwNode.inputs[0])
		
		
		
		baseEMIMultNode = nodeTree.nodes.new('ShaderNodeMath')
		baseEMIMultNode.location = currentPos
		baseEMIMultNode.operation = "MULTIPLY"
		nodeTree.links.new(bwNode.outputs[0],baseEMIMultNode.inputs[0])
		nodeTree.links.new(reduceEMIMultNode.outputs["Value"],baseEMIMultNode.inputs[1])
		
		matInfo["emissionStrengthNodeLayerGroup"].addMixLayer(baseEMIMultNode.outputs["Value"],mixType = "MULTIPLY",mixFactor = 1.0)
	if "S_col_R" in matInfo["mPropDict"] and "S_col_G" in matInfo["mPropDict"] and "S_col_R_Emissive_intensity" in matInfo["mPropDict"] and "S_col_G_Emissive_intensity" in matInfo["mPropDict"]:
		RColorNode = addPropertyNode(matInfo["mPropDict"]["S_col_R"], matInfo["currentPropPos"], nodeTree)
		GColorNode = addPropertyNode(matInfo["mPropDict"]["S_col_G"], matInfo["currentPropPos"], nodeTree)
		
		RColorEmiIntensityNode = addPropertyNode(matInfo["mPropDict"]["S_col_R_Emissive_intensity"], matInfo["currentPropPos"], nodeTree)
		GColorEmiIntensityNode = addPropertyNode(matInfo["mPropDict"]["S_col_G_Emissive_intensity"], matInfo["currentPropPos"], nodeTree)
		
		if "CMMSepNode" in nodeTree.nodes:
			CMMSeparateNode = nodeTree.nodes["CMMSepNode"]
		else:
			CMMSeparateNode = nodeTree.nodes.new('ShaderNodeSeparateColor')
			CMMSeparateNode.location = currentPos
			CMMSeparateNode.name = "CMMSepNode"
			
		RMultNode = nodeTree.nodes.new("ShaderNodeMath")
		RMultNode.operation = "MULTIPLY"
		
		nodeTree.links.new(RColorEmiIntensityNode.outputs["Value"],RMultNode.inputs[0])
		nodeTree.links.new(CMMSeparateNode.outputs["Red"],RMultNode.inputs[1])
		
		GMultNode = nodeTree.nodes.new("ShaderNodeMath")
		GMultNode.operation = "MULTIPLY"
		
		StrengthAddNode = nodeTree.nodes.new("ShaderNodeMath")
		StrengthAddNode.operation = "ADD"
		
		nodeTree.links.new(RMultNode.outputs["Value"],StrengthAddNode.inputs[0])
		nodeTree.links.new(GMultNode.outputs["Value"],StrengthAddNode.inputs[1])
		
		matInfo["emissionStrengthNodeLayerGroup"].addMixLayer(StrengthAddNode.outputs["Value"],factorOutSocket = None,mixType = "ADD",mixFactor = 1.0)
		
		nodeTree.links.new(GColorEmiIntensityNode.outputs["Value"],GMultNode.inputs[0])
		nodeTree.links.new(CMMSeparateNode.outputs["Green"],GMultNode.inputs[1])
		
		matInfo["emissionColorNodeLayerGroup"].addMixLayer(RColorNode.outputs["Color"],factorOutSocket = CMMSeparateNode.outputs["Red"],mixType = "ADD")
		matInfo["emissionColorNodeLayerGroup"].addMixLayer(GColorNode.outputs["Color"],factorOutSocket = CMMSeparateNode.outputs["Green"],mixType = "ADD")
		
		
		
	return imageNode

def newCMMNode (nodeTree,textureType,matInfo):
	imageNode = nodeTree.nodes[textureType]
	currentPos = [imageNode.location[0]+300,imageNode.location[1]]
	
	if "UseSecondaryUV_ColorLayer_MaskMap" in matInfo["mPropDict"]:
		UVMap1Node = None
		UVMap2Node = None
		if "UVMap1Node" in nodeTree.nodes:
			UVMap1Node = nodeTree.nodes["UVMap1Node"]
		if "UVMap2Node" in nodeTree.nodes:
			UVMap2Node = nodeTree.nodes["UVMap2Node"]
		if UVMap1Node != None and UVMap2Node != None:
			useSecondaryUVNode = addPropertyNode(matInfo["mPropDict"]["UseSecondaryUV_ColorLayer_MaskMap"], matInfo["currentPropPos"], nodeTree)
			
			uvMappingGroupNode = getDualUVMappingNodeGroup(nodeTree)
			uvMappingGroupNode.location = useSecondaryUVNode.location + Vector((300,0))
			nodeTree.links.new(UVMap1Node.outputs["UV"],uvMappingGroupNode.inputs["UV1"])
			nodeTree.links.new(UVMap2Node.outputs["UV"],uvMappingGroupNode.inputs["UV2"])
			nodeTree.links.new(useSecondaryUVNode.outputs["Value"],uvMappingGroupNode.inputs["UseSecondaryUV"])
			nodeTree.links.new(uvMappingGroupNode.outputs["Vector"],imageNode.inputs["Vector"])
	if "CMMSepNode" in nodeTree.nodes:
		CMMSeparateNode = nodeTree.nodes["CMMSepNode"]
	else:
		CMMSeparateNode = nodeTree.nodes.new('ShaderNodeSeparateColor')
		CMMSeparateNode.location = currentPos
		CMMSeparateNode.name = "CMMSepNode"
	
	nodeTree.links.new(imageNode.outputs["Color"],CMMSeparateNode.inputs["Color"])
	if "S_col_R" in matInfo["mPropDict"] and "S_col_G" in matInfo["mPropDict"]:
		RColorNode = addPropertyNode(matInfo["mPropDict"]["S_col_R"], matInfo["currentPropPos"], nodeTree)
		GColorNode = addPropertyNode(matInfo["mPropDict"]["S_col_G"], matInfo["currentPropPos"], nodeTree)
		if matInfo["albedoNodeLayerGroup"] != None:
			matInfo["albedoNodeLayerGroup"].addMixLayer(RColorNode.outputs["Color"],CMMSeparateNode.outputs["Red"],mixType = "MULTIPLY")
			matInfo["albedoNodeLayerGroup"].addMixLayer(GColorNode.outputs["Color"],CMMSeparateNode.outputs["Green"],mixType = "MULTIPLY")
			
	elif "ColorLayer_R" in matInfo["mPropDict"] and "ColorLayer_G" in matInfo["mPropDict"] and "ColorLayer_B" in matInfo["mPropDict"] and "ColorLayer_A" in matInfo["mPropDict"] and matInfo["gameName"] != "MHWILDS":#MH Wilds is done after all texture nodes by addMHWildsColorLayerNodes
		RColorNode = addPropertyNode(matInfo["mPropDict"]["ColorLayer_R"], matInfo["currentPropPos"], nodeTree)
		
		
		if "Use_R" in matInfo["mPropDict"]:
			useRNode = addPropertyNode(matInfo["mPropDict"]["Use_R"], matInfo["currentPropPos"], nodeTree)
			multRNode = nodeTree.nodes.new("ShaderNodeMath")
			multRNode.location = useRNode.location + Vector((300,0))
			multRNode.operation = "MULTIPLY"
			nodeTree.links.new(useRNode.outputs["Value"],multRNode.inputs[0])
			nodeTree.links.new(CMMSeparateNode.outputs["Red"],multRNode.inputs[1])
			RColorFactorSocket = multRNode.outputs["Value"]
		else:
			RColorFactorSocket = CMMSeparateNode.outputs["Red"]
		
		GColorNode = addPropertyNode(matInfo["mPropDict"]["ColorLayer_G"], matInfo["currentPropPos"], nodeTree)
		
		if "Use_G" in matInfo["mPropDict"]:
			useGNode = addPropertyNode(matInfo["mPropDict"]["Use_G"], matInfo["currentPropPos"], nodeTree)
			multGNode = nodeTree.nodes.new("ShaderNodeMath")
			multGNode.location = useGNode.location + Vector((300,0))
			multGNode.operation = "MULTIPLY"
			nodeTree.links.new(useGNode.outputs["Value"],multGNode.inputs[0])
			nodeTree.links.new(CMMSeparateNode.outputs["Green"],multGNode.inputs[1])
			GColorFactorSocket = multGNode.outputs["Value"]
		else:
			GColorFactorSocket = CMMSeparateNode.outputs["Green"]
		
		BColorNode = addPropertyNode(matInfo["mPropDict"]["ColorLayer_B"], matInfo["currentPropPos"], nodeTree)
		
		if "Use_B" in matInfo["mPropDict"]:
			useBNode = addPropertyNode(matInfo["mPropDict"]["Use_B"], matInfo["currentPropPos"], nodeTree)
			multBNode = nodeTree.nodes.new("ShaderNodeMath")
			multBNode.location = useBNode.location + Vector((300,0))
			multBNode.operation = "MULTIPLY"
			nodeTree.links.new(useBNode.outputs["Value"],multBNode.inputs[0])
			nodeTree.links.new(CMMSeparateNode.outputs["Blue"],multBNode.inputs[1])
			BColorFactorSocket = multBNode.outputs["Value"]
		else:
			BColorFactorSocket = CMMSeparateNode.outputs["Blue"]
		
		AColorNode = addPropertyNode(matInfo["mPropDict"]["ColorLayer_A"], matInfo["currentPropPos"], nodeTree)
		
		if "Use_A" in matInfo["mPropDict"]:
			useANode = addPropertyNode(matInfo["mPropDict"]["Use_A"], matInfo["currentPropPos"], nodeTree)
			multANode = nodeTree.nodes.new("ShaderNodeMath")
			multANode.location = useANode.location + Vector((300,0))
			multANode.operation = "MULTIPLY"
			nodeTree.links.new(useANode.outputs["Value"],multANode.inputs[0])
			nodeTree.links.new(imageNode.outputs["Alpha"],multANode.inputs[1])
			AColorFactorSocket = multANode.outputs["Value"]
		else:
			AColorFactorSocket = imageNode.outputs["Alpha"]
			
		if matInfo["albedoNodeLayerGroup"] != None:
			matInfo["albedoNodeLayerGroup"].addMixLayer(RColorNode.outputs["Color"],RColorFactorSocket,mixType = "MULTIPLY")
			matInfo["albedoNodeLayerGroup"].addMixLayer(GColorNode.outputs["Color"],GColorFactorSocket,mixType = "MULTIPLY")
			matInfo["albedoNodeLayerGroup"].addMixLayer(BColorNode.outputs["Color"],BColorFactorSocket,mixType = "MULTIPLY")
			matInfo["albedoNodeLayerGroup"].addMixLayer(AColorNode.outputs["Color"],AColorFactorSocket,mixType = "MULTIPLY")
	return imageNode
def newCMASKNode (nodeTree,textureType,matInfo):
	imageNode = nodeTree.nodes[textureType]
	currentPos = [imageNode.location[0]+300,imageNode.location[1]]
	
	
	
	CMaskSeparateNode = nodeTree.nodes.new('ShaderNodeSeparateColor')
	CMaskSeparateNode.location = currentPos
	
	nodeTree.links.new(imageNode.outputs["Color"],CMaskSeparateNode.inputs["Color"])
	
	#Fix for imported SF6 materials, this shouldn't matter in game since it gets overriden by the cmd files
	for prop in matInfo["mPropDict"].values():
		if "CustomizeRoughness" in prop.propName or "CustomizeMetal" in prop.propName:
			if prop.propValue[0] == 0.0:
				prop.propValue = [1.0]
		elif "CustomizeColor"  in prop.propName:
			if prop.propValue == [0.501960813999176, 0.501960813999176, 0.501960813999176, 1.0]:
				prop.propValue = [1.0,1.0,1.0,1.0]
	if "CustomizeColor_0" in matInfo["mPropDict"]:
		if "CustomizeColor_0" not in nodeTree.nodes:
			color0Node = addPropertyNode(matInfo["mPropDict"]["CustomizeColor_0"], matInfo["currentPropPos"], nodeTree)
			color1Node = addPropertyNode(matInfo["mPropDict"]["CustomizeColor_1"], matInfo["currentPropPos"], nodeTree)
			color2Node = addPropertyNode(matInfo["mPropDict"]["CustomizeColor_2"], matInfo["currentPropPos"], nodeTree)
			color3Node = addPropertyNode(matInfo["mPropDict"]["CustomizeColor_3"], matInfo["currentPropPos"], nodeTree)
			
			matInfo["albedoNodeLayerGroup"].addMixLayer(color0Node.outputs["Color"],CMaskSeparateNode.outputs["Red"],mixType = "MULTIPLY")
			matInfo["albedoNodeLayerGroup"].addMixLayer(color1Node.outputs["Color"],CMaskSeparateNode.outputs["Green"],mixType = "MULTIPLY")
			matInfo["albedoNodeLayerGroup"].addMixLayer(color2Node.outputs["Color"],CMaskSeparateNode.outputs["Blue"],mixType = "MULTIPLY")
			matInfo["albedoNodeLayerGroup"].addMixLayer(color3Node.outputs["Color"],imageNode.outputs["Alpha"],mixType = "MULTIPLY")
		else:#Is cmask2
			color4Node = addPropertyNode(matInfo["mPropDict"]["CustomizeColor_4"], matInfo["currentPropPos"], nodeTree)
			color5Node = addPropertyNode(matInfo["mPropDict"]["CustomizeColor_5"], matInfo["currentPropPos"], nodeTree)
			color6Node = addPropertyNode(matInfo["mPropDict"]["CustomizeColor_6"], matInfo["currentPropPos"], nodeTree)
			color7Node = addPropertyNode(matInfo["mPropDict"]["CustomizeColor_7"], matInfo["currentPropPos"], nodeTree)
			
			matInfo["albedoNodeLayerGroup"].addMixLayer(color4Node.outputs["Color"],CMaskSeparateNode.outputs["Red"],mixType = "MULTIPLY")
			matInfo["albedoNodeLayerGroup"].addMixLayer(color5Node.outputs["Color"],CMaskSeparateNode.outputs["Green"],mixType = "MULTIPLY")
			matInfo["albedoNodeLayerGroup"].addMixLayer(color6Node.outputs["Color"],CMaskSeparateNode.outputs["Blue"],mixType = "MULTIPLY")
			matInfo["albedoNodeLayerGroup"].addMixLayer(color7Node.outputs["Color"],imageNode.outputs["Alpha"],mixType = "MULTIPLY")
	
	if "CustomizeMetal_0" in matInfo["mPropDict"]:
		if "CustomizeMetal_0" not in nodeTree.nodes:
			rough0Node = addPropertyNode(matInfo["mPropDict"]["CustomizeRoughness_0"], matInfo["currentPropPos"], nodeTree)
			rough1Node = addPropertyNode(matInfo["mPropDict"]["CustomizeRoughness_1"], matInfo["currentPropPos"], nodeTree)
			rough2Node = addPropertyNode(matInfo["mPropDict"]["CustomizeRoughness_2"], matInfo["currentPropPos"], nodeTree)
			rough3Node = addPropertyNode(matInfo["mPropDict"]["CustomizeRoughness_3"], matInfo["currentPropPos"], nodeTree)
			
			matInfo["roughnessNodeLayerGroup"].addMixLayer(rough0Node.outputs["Value"],CMaskSeparateNode.outputs["Red"],mixType = "MULTIPLY")
			matInfo["roughnessNodeLayerGroup"].addMixLayer(rough1Node.outputs["Value"],CMaskSeparateNode.outputs["Green"],mixType = "MULTIPLY")
			matInfo["roughnessNodeLayerGroup"].addMixLayer(rough2Node.outputs["Value"],CMaskSeparateNode.outputs["Blue"],mixType = "MULTIPLY")
			matInfo["roughnessNodeLayerGroup"].addMixLayer(rough3Node.outputs["Value"],imageNode.outputs["Alpha"],mixType = "MULTIPLY")
		else:
			rough4Node = addPropertyNode(matInfo["mPropDict"]["CustomizeRoughness_4"], matInfo["currentPropPos"], nodeTree)
			rough5Node = addPropertyNode(matInfo["mPropDict"]["CustomizeRoughness_5"], matInfo["currentPropPos"], nodeTree)
			rough6Node = addPropertyNode(matInfo["mPropDict"]["CustomizeRoughness_6"], matInfo["currentPropPos"], nodeTree)
			rough7Node = addPropertyNode(matInfo["mPropDict"]["CustomizeRoughness_7"], matInfo["currentPropPos"], nodeTree)
			
			matInfo["roughnessNodeLayerGroup"].addMixLayer(rough4Node.outputs["Value"],CMaskSeparateNode.outputs["Red"],mixType = "MULTIPLY")
			matInfo["roughnessNodeLayerGroup"].addMixLayer(rough5Node.outputs["Value"],CMaskSeparateNode.outputs["Green"],mixType = "MULTIPLY")
			matInfo["roughnessNodeLayerGroup"].addMixLayer(rough6Node.outputs["Value"],CMaskSeparateNode.outputs["Blue"],mixType = "MULTIPLY")
			matInfo["roughnessNodeLayerGroup"].addMixLayer(rough7Node.outputs["Value"],imageNode.outputs["Alpha"],mixType = "MULTIPLY")
		
	if "CustomizeMetal_0" in matInfo["mPropDict"]:
		if "CustomizeMetal_0" not in nodeTree.nodes:
			
			metal0Node = addPropertyNode(matInfo["mPropDict"]["CustomizeMetal_0"], matInfo["currentPropPos"], nodeTree)
			metal1Node = addPropertyNode(matInfo["mPropDict"]["CustomizeMetal_1"], matInfo["currentPropPos"], nodeTree)
			metal2Node = addPropertyNode(matInfo["mPropDict"]["CustomizeMetal_2"], matInfo["currentPropPos"], nodeTree)
			metal3Node = addPropertyNode(matInfo["mPropDict"]["CustomizeMetal_3"], matInfo["currentPropPos"], nodeTree)
			
			matInfo["metallicNodeLayerGroup"].addMixLayer(metal0Node.outputs["Value"],CMaskSeparateNode.outputs["Red"],mixType = "MULTIPLY")
			matInfo["metallicNodeLayerGroup"].addMixLayer(metal1Node.outputs["Value"],CMaskSeparateNode.outputs["Green"],mixType = "MULTIPLY")
			matInfo["metallicNodeLayerGroup"].addMixLayer(metal2Node.outputs["Value"],CMaskSeparateNode.outputs["Blue"],mixType = "MULTIPLY")
			matInfo["metallicNodeLayerGroup"].addMixLayer(metal3Node.outputs["Value"],imageNode.outputs["Alpha"],mixType = "MULTIPLY")
		else:
			metal4Node = addPropertyNode(matInfo["mPropDict"]["CustomizeMetal_4"], matInfo["currentPropPos"], nodeTree)
			metal5Node = addPropertyNode(matInfo["mPropDict"]["CustomizeMetal_5"], matInfo["currentPropPos"], nodeTree)
			metal6Node = addPropertyNode(matInfo["mPropDict"]["CustomizeMetal_6"], matInfo["currentPropPos"], nodeTree)
			metal7Node = addPropertyNode(matInfo["mPropDict"]["CustomizeMetal_7"], matInfo["currentPropPos"], nodeTree)
			
			matInfo["metallicNodeLayerGroup"].addMixLayer(metal4Node.outputs["Value"],CMaskSeparateNode.outputs["Red"],mixType = "MULTIPLY")
			matInfo["metallicNodeLayerGroup"].addMixLayer(metal5Node.outputs["Value"],CMaskSeparateNode.outputs["Green"],mixType = "MULTIPLY")
			matInfo["metallicNodeLayerGroup"].addMixLayer(metal6Node.outputs["Value"],CMaskSeparateNode.outputs["Blue"],mixType = "MULTIPLY")
			matInfo["metallicNodeLayerGroup"].addMixLayer(metal7Node.outputs["Value"],imageNode.outputs["Alpha"],mixType = "MULTIPLY")
				
		
	return imageNode
def newATOSNode (nodeTree,textureType,matInfo):
	imageNode = nodeTree.nodes[textureType]
	currentPos = [imageNode.location[0]+300,imageNode.location[1]]
	
	
	separateNode = nodeTree.nodes.new('ShaderNodeSeparateColor')
	separateNode.location = currentPos
	useLegacyHairUV2Occlusion = (matInfo["gameName"] in legacyUV2HairOcclusionList and "hair" in matInfo["mmtrName"])
	
	#RE2 puts other masks in the alpha channel sometimes
	#Check for nullblack to avoid issues with SF6
	isMTOS = hasattr(imageNode, "image") and imageNode.image != None and "_mtos" in imageNode.image.filepath.lower() or "BaseAlphaMap" in matInfo["textureNodeDict"] or (hasattr(imageNode, "image") and "nullblack" in imageNode.image.filepath.lower())
	isMaskAlpha = matInfo["isMaskAlphaMMTR"]
	
	#Have to do this hack since there's no good way of telling whether the alpha channel is actually alpha with this game
	if (matInfo["gameName"] == "PRAG" and ("Use_STOC" in matInfo["mPropDict"] and matInfo["mPropDict"]["Use_STOC"].propValue[0] == 1.0)) or (matInfo["gameName"] == "DMC5" and (("Emissive_Intensity" in matInfo["mPropDict"] and matInfo["mPropDict"]["Emissive_Intensity"].propValue[0] != 0.0) or ("EmissiveIntensity" in matInfo["mPropDict"] and matInfo["mPropDict"]["EmissiveIntensity"].propValue[0] != 0.0) or ("Use_Emissive" in matInfo["mPropDict"] and matInfo["mPropDict"]["Use_Emissive"].propValue[0] == 1.0))):
		#TODO Set up DMC5 emission
		isMaskAlpha = True
	
	
	alphaUV2Node = None
	occlusionUV2Node = None
	cavityUV2Node = None
	makeUV2Node = False
	
	
	if "Alpha_UseSecondaryUV" in matInfo["mPropDict"]:
		makeUV2Node = True
		alphaUV2Node = addPropertyNode(matInfo["mPropDict"]["Alpha_UseSecondaryUV"], matInfo["currentPropPos"], nodeTree)
		
	if "Occlusion_UseSecondaryUV" in matInfo["mPropDict"]:
		makeUV2Node = True
		occlusionUV2Node = addPropertyNode(matInfo["mPropDict"]["Occlusion_UseSecondaryUV"], matInfo["currentPropPos"], nodeTree)
	elif "OcclusionMap_UseSecondaryUV" in matInfo["mPropDict"]:
		makeUV2Node = True
		occlusionUV2Node = addPropertyNode(matInfo["mPropDict"]["OcclusionMap_UseSecondaryUV"], matInfo["currentPropPos"], nodeTree)
	if "Cavity_UseSecondaryUV" in matInfo["mPropDict"]:
		makeUV2Node = True
		cavityUV2Node = addPropertyNode(matInfo["mPropDict"]["Cavity_UseSecondaryUV"], matInfo["currentPropPos"], nodeTree)
	currentPos[0] += 300
	nodeTree.links.new(imageNode.outputs["Color"],separateNode.inputs["Color"])
	if makeUV2Node or useLegacyHairUV2Occlusion:
		mappingNode = nodeTree.nodes.new('ShaderNodeMapping')
		mappingNode.location = currentPos
		uv2Node = nodeTree.nodes["UVMap2Node"]
		nodeTree.links.new(uv2Node.outputs["UV"],mappingNode.inputs["Vector"])
		currentPos[0] += 300
		imageNodeUV2 = nodeTree.nodes.new('ShaderNodeTexImage')
		imageNodeUV2.name = "UV2_"+textureType
		imageNodeUV2.label = "UV2_"+textureType
		imageNodeUV2.location = currentPos
		imageNodeUV2.image = imageNode.image
		nodeTree.links.new(mappingNode.outputs["Vector"],imageNodeUV2.inputs["Vector"])
		currentPos[0] += 300
		
		separateNodeUV2 = nodeTree.nodes.new('ShaderNodeSeparateColor')
		separateNodeUV2.location = currentPos
		nodeTree.links.new(imageNodeUV2.outputs["Color"],separateNodeUV2.inputs["Color"])
		currentPos[0] += 300
		
		matInfo["translucentSocket"] = separateNode.outputs["Green"]
			
		if alphaUV2Node != None:
			mixUVAlphaNode = nodeTree.nodes.new('ShaderNodeMixRGB')
			mixUVAlphaNode.location = currentPos
			nodeTree.links.new(separateNode.outputs["Red"],mixUVAlphaNode.inputs["Color1"])
			nodeTree.links.new(separateNodeUV2.outputs["Red"],mixUVAlphaNode.inputs["Color2"])
			nodeTree.links.new(alphaUV2Node.outputs["Value"],mixUVAlphaNode.inputs["Fac"])
			currentPos[0] += 300
			if not isMTOS and not isMaskAlpha:
				matInfo["alphaSocket"] = mixUVAlphaNode.outputs["Color"]
		else:
			if not isMTOS and not isMaskAlpha:
				matInfo["alphaSocket"] = separateNode.outputs["Red"]
		
		if matInfo["gameName"] == "MHWILDS" and textureType == "AlphaTranslucentOcclusionSSSMap":
			addMHWildsAOTextureNodes(nodeTree,matInfo,textureType)
		elif occlusionUV2Node != None or useLegacyHairUV2Occlusion:
			mixUVOCCNode = nodeTree.nodes.new('ShaderNodeMixRGB')
			mixUVOCCNode.location = currentPos
			nodeTree.links.new(separateNode.outputs["Blue"],mixUVOCCNode.inputs["Color1"])
			nodeTree.links.new(separateNodeUV2.outputs["Blue"],mixUVOCCNode.inputs["Color2"])
			if occlusionUV2Node != None:
				nodeTree.links.new(occlusionUV2Node.outputs["Value"],mixUVOCCNode.inputs["Fac"])
			else:
				if useLegacyHairUV2Occlusion:
					mixUVOCCNode.inputs["Fac"].default_value = 1.0
			currentPos[0] += 300
			matInfo["aoNodeLayerGroup"].addMixLayer( mixUVOCCNode.outputs["Color"])
		else:
			if matInfo["gameName"] != "SF6":#SF6 uses occlusion channel for something else
				matInfo["aoNodeLayerGroup"].addMixLayer(separateNode.outputs["Blue"])
		
		if cavityUV2Node != None:
			mixUVCavityNode = nodeTree.nodes.new('ShaderNodeMixRGB')
			mixUVCavityNode.location = currentPos
			nodeTree.links.new(imageNode.outputs["Alpha"],mixUVCavityNode.inputs["Color1"])
			nodeTree.links.new(imageNodeUV2.outputs["Alpha"],mixUVCavityNode.inputs["Color2"])
			nodeTree.links.new(cavityUV2Node.outputs["Value"],mixUVCavityNode.inputs["Fac"])
			currentPos[0] += 300
			matInfo["cavityNodeLayerGroup"].addMixLayer(mixUVCavityNode.outputs["Color"])
		else:
			if textureType == "AlphaTranslucentOcclusionCavityMap":
				matInfo["cavityNodeLayerGroup"].addMixLayer(imageNode.outputs["Alpha"])
	else:
		if not isMTOS and not isMaskAlpha and not "StitchMap" in matInfo["textureNodeDict"]:
			matInfo["alphaSocket"] = separateNode.outputs["Red"]
		matInfo["translucentSocket"] = separateNode.outputs["Green"]
		if matInfo["gameName"] == "MHWILDS" and textureType == "AlphaTranslucentOcclusionSSSMap":
			addMHWildsAOTextureNodes(nodeTree,matInfo,textureType)
		elif matInfo["gameName"] != "SF6" and not useLegacyHairUV2Occlusion:#SF6 uses occlusion channel for something else
			matInfo["aoNodeLayerGroup"].addMixLayer(separateNode.outputs["Blue"])
		
		if textureType == "AlphaTranslucentOcclusionCavityMap":
			matInfo["cavityNodeLayerGroup"].addMixLayer(imageNode.outputs["Alpha"])
		
		elif textureType == "AlphaCavityOcclusionTranslucentMap":
			matInfo["cavityNodeLayerGroup"].addMixLayer(separateNode.outputs["Green"])
			matInfo["translucentSocket"] = imageNode.outputs["Alpha"]
		
		else:
			matInfo["subsurfaceSocket"] = imageNode.outputs["Alpha"]
	
	if matInfo["gameName"] == "MHWILDS" and textureType == "AlphaTranslucentOcclusionSSSMap" and matInfo["alphaSocket"] == separateNode.outputs["Red"]:
		matInfo["mhWildsRawAlphaSource"] = separateNode.outputs["Red"]
	return imageNode

def newOCTDNode (nodeTree,textureType,matInfo):
	imageNode = nodeTree.nodes[textureType]
	currentPos = [imageNode.location[0]+300,imageNode.location[1]]
	
	
	separateNode = nodeTree.nodes.new('ShaderNodeSeparateColor')
	separateNode.location = currentPos
	currentPos[0] += 300
	nodeTree.links.new(imageNode.outputs["Color"],separateNode.inputs["Color"])
	
	
	if textureType == "OcclusionCavityTranslucentDetailMap":
		matInfo["translucentSocket"] = separateNode.outputs["Blue"]
	
	elif textureType == "OcclusionCavitySSSDetailMap":
		matInfo["subsurfaceSocket"] = separateNode.outputs["Blue"]
	elif textureType == "OcclusionCavityMaskAnisoMap":
		matInfo["anisoSocket"] = imageNode.outputs["Alpha"]
		if "Emissive_MaskStrength" in matInfo["mPropDict"]:
			maskStrengthNode = addPropertyNode(matInfo["mPropDict"]["Emissive_MaskStrength"], matInfo["currentPropPos"], nodeTree)
			matInfo["emissionStrengthNodeLayerGroup"].addMixLayer(separateNode.outputs["Blue"],mixType = "MULTIPLY",mixFactor = 1.0,factorOutSocket = maskStrengthNode.outputs["Value"])
	matInfo["aoNodeLayerGroup"].addMixLayer(separateNode.outputs["Red"])
	matInfo["cavityNodeLayerGroup"].addMixLayer(separateNode.outputs["Green"])
	
	return imageNode

def newSCOTNode (nodeTree,textureType,matInfo):
	imageNode = nodeTree.nodes[textureType]
	currentPos = [imageNode.location[0]+300,imageNode.location[1]]
	
	
	separateNode = nodeTree.nodes.new('ShaderNodeSeparateColor')
	separateNode.location = currentPos
	currentPos[0] += 300
	nodeTree.links.new(imageNode.outputs["Color"],separateNode.inputs["Color"])
	
	
	matInfo["subsurfaceSocket"] = separateNode.outputs["Red"]
	matInfo["cavityNodeLayerGroup"].addMixLayer(separateNode.outputs["Green"])
	matInfo["aoNodeLayerGroup"].addMixLayer(separateNode.outputs["Blue"])
	matInfo["translucentSocket"] = imageNode.outputs["Alpha"]
	
	return imageNode

def newSRMNode (nodeTree,textureType,matInfo):
	imageNode = nodeTree.nodes[textureType]
	currentPos = [imageNode.location[0]-300,imageNode.location[1]]
	
	separateRGBNode = nodeTree.nodes.new("ShaderNodeSeparateColor")
	separateRGBNode.location = currentPos
	nodeTree.links.new(imageNode.outputs["Color"],separateRGBNode.inputs["Color"])
	matInfo["roughnessNodeLayerGroup"].addMixLayer(separateRGBNode.outputs["Green"])
	matInfo["metallicNodeLayerGroup"].addMixLayer(separateRGBNode.outputs["Blue"])
	return imageNode
"""
def newUNKNNode (nodeTree,textureType,matInfo):
	imageNode = nodeTree.nodes.new('ShaderNodeTexImage')
	imageNode.label = textureType
	texture = bpy.data.images.get(os.path.split(texturePath)[1],None)
	if texture == None:
		imageNode.image = bpy.data.images.load(texturePath)
	else:
		imageNode.image = texture
	if "_alb" in texturePath.lower():
		imageNode.image.colorspace_settings.name = "sRGB"
	else:
		imageNode.image.colorspace_settings.name = "Non-Color"
	imageNode.image.alpha_mode = "CHANNEL_PACKED"
	imageNode.location = currentPos
	return imageNode
"""
nodeDict = {
	"ALBD":newALBDNode,
	"ALBM":newALBMNode,
	"ALBA":newALBANode,
	"ALB":newALBNode,
	"NRMR":newNRMRNode,
	"NRRT":newNRRTNode,
	"ALP":newALPNode,
	"CMM":newCMMNode,
	"CMASK":newCMASKNode,
	"EMI":newEMINode,
	"ATOS":newATOSNode,
	"OCTD":newOCTDNode,
	"SCOT":newSCOTNode,
	"NAM":newNAMNode,
	"SRM":newSRMNode,
	"NRM":newNRMNode,
	#"UNKN":newUNKNNode,
	
	}
def addTextureNode(nodeTree,nodeType,textureType,matInfo):
	#print(nodeType)
	#print(textureType)
	#print(texturePath)
	return nodeDict[nodeType](nodeTree,textureType,matInfo)
	