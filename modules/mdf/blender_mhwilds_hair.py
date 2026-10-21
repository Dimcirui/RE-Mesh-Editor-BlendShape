"""Two-lobe hair highlight added to the base color, traced from MH Wilds Base_ATOS_VFX_Hair_NoPDO.

Source: .240906211 shader #64 (PS_GBuffer), DXIL %748..%909. The highlight uses the MDF LightDirection and
the view vector and is written into the base color before lighting, so it feeds Base Color here, not Emission.
Selected by texture slots (HairFlowMap + Hair_Height_SpecMask_Shift_Map) plus the lobe parameters, in any game.
"""
import bpy
from mathutils import Vector

#Wilds spelling first. Onimusha (V_Chara_*_Hair) renames the same parameters; its shader is not traced yet,
#so it runs the Wilds math with its own Secondary_Anisotropy in place of Primaly_Anisotropy for the second lobe.
HAIR_PARAM_ALIASES = {
	'Primary Anisotropy':('Primaly_Anisotropy','Primary_Anisotropy'),
	'Secondary Anisotropy':('Secondary_Anisotropy',),
	'Primary Shift Offset':('Specular_ShiftOffset','Primary_Specular_ShiftOffset'),
	'Secondary Shift Offset':('Secondary_ShiftOffset','Secondary_Specular_ShiftOffset'),
	'Primary Sharpness':('PrimalySpec_Sharpness','PrimarySpec_Sharpness'),
	'Secondary Sharpness':('SecondarySpec_Sharpness',),
	'Primary Specular Color':('PrimalySpecularColor','Primary_Specular_Color'),
	'Secondary Intensity':('Secondary_Specular_Intensity',),
	'Deep Shadow Color':('DeepShadowColor',),
	'Basecolor Fade':('Basecolor_Fade','BaseColor_Fade'),
	'Light Direction':('LightDirection',),
	'UseFlowMap':('UseFlowMap',),
	'UseVertexColor_mask':('UseVertexColor_mask',),
}
#Both hair vertex shaders (VS #56 PreTransformVfx, VS #75 StaticVfx) pass COLOR0.a through as the lobe mask;
#VS #75 rounds it to 8 bits first, which a byte color attribute already is.
VERTEX_COLOR_LAYER = "Col"
HAIR_LIVE_PROPS = {name for names in HAIR_PARAM_ALIASES.values() for name in names}
HAIR_OVER_PROPS = ('UseHairOverMap','PrimaryUV_OverMap','HairOverColorA','HairOverColorB','HairOverColorA_B_Contrast','HairOverColorA_B_Shift')
HAIR_ALPHA_PROPS = ('Use_DefaultAlpha','AO_Fade_Alpha','EdgeWidth','EdgeFade')
HAIR_LIVE_PROPS.update(HAIR_OVER_PROPS + HAIR_ALPHA_PROPS)
SAFE_DIVISOR = 1e-4#0x38D1B717: the shaders swap a zero Contrast/EdgeWidth for this
#Without these the lobes have no meaning; the rest fall back to neutral defaults.
REQUIRED_HAIR_PARAMS = ('Primary Sharpness','Secondary Sharpness','Light Direction')
HAIR_DECODE_OFFSET = 0.9960784316062927#2*x - 254/255, as in the shader (0xBF7EFEFF); not the 128/255 center of FurFlow

def hairParam(props,label):
	return next((name for name in HAIR_PARAM_ALIASES[label] if name in props),None)

def isHairMaterial(matInfo):
	from .blender_nodes_re_mdf import hasLoadedImage
	props = matInfo["mPropDict"]
	return (hasLoadedImage(matInfo,"HairFlowMap") and hasLoadedImage(matInfo,"Hair_Height_SpecMask_Shift_Map")
		and all(hairParam(props,label) != None for label in REQUIRED_HAIR_PARAMS))

class _Builder():
	def __init__(self,group):
		from .blender_nodes_re_mdf import ShaderGroupBuilder
		self.b = ShaderGroupBuilder(group)
		self.nodes,self.links = group.nodes,group.links
	def __getattr__(self,name):
		return getattr(self.b,name)
	def vec(self,operation,a,b = None,scale = None):
		node = self.nodes.new("ShaderNodeVectorMath")
		node.operation = operation
		self.b._set(node.inputs[0],a)
		if b != None:
			self.b._set(node.inputs[1],b)
		if scale != None:
			self.b._set(node.inputs["Scale"],scale)
		return node.outputs["Value" if operation in ("DOT_PRODUCT","LENGTH") else "Vector"]
	def madd(self,a,s,b):#a*s + b, vectors a/b, scalar s
		return self.vec("ADD",self.vec("SCALE",a,scale = s),b)
	def saturate(self,x):
		return self.b.math("ADD",x,0.0,clamp = True)

def _lobe(k,direction,q,exponent,gate):
	#S(gate) * S(saturate(u + 1)) * sinTheta^exponent, u = dot(direction, Q)
	u = k.vec("DOT_PRODUCT",direction,q)
	#max(.., 0) guards the sqrt against rounding past |u| = 1; the shader takes the root directly.
	sinTheta = k.math("SQRT",k.math("MAXIMUM",k.math("MULTIPLY_ADD",k.math("MULTIPLY",u,-1.0),u,1.0),0.0))
	return k.math("MULTIPLY",k.math("MULTIPLY",k.smoothstep01(gate),k.smoothstep01(k.math("ADD",u,1.0,clamp = True))),k.math("POWER",sinTheta,exponent))

def hairSpecularNodeGroup():
	name = "REHairSpecular_v1"
	group = bpy.data.node_groups.get(name)
	if group != None:
		return group
	from .blender_nodes_re_mdf import newGroupSockets
	group = bpy.data.node_groups.new(name,"ShaderNodeTree")
	newGroupSockets(group,[("Base Color","NodeSocketColor"),("Hair Flow","NodeSocketColor"),("Spec Mask Shift","NodeSocketColor"),("AO","NodeSocketFloat"),
		("UseFlowMap","NodeSocketFloat"),("Primary Anisotropy","NodeSocketFloat"),("Secondary Anisotropy","NodeSocketFloat"),
		("Primary Shift Offset","NodeSocketFloat"),("Secondary Shift Offset","NodeSocketFloat"),("Primary Sharpness","NodeSocketFloat"),("Secondary Sharpness","NodeSocketFloat"),
		("Primary Specular Color","NodeSocketColor"),("Primary Specular Alpha","NodeSocketFloat"),("Secondary Intensity","NodeSocketFloat"),
		("Deep Shadow Color","NodeSocketColor"),("Deep Shadow Alpha","NodeSocketFloat"),("Basecolor Fade","NodeSocketFloat"),
		("Light X","NodeSocketFloat"),("Light Y","NodeSocketFloat"),("Light Z","NodeSocketFloat"),("Vertex Mask","NodeSocketFloat")],"INPUT")
	newGroupSockets(group,[("Color","NodeSocketColor")],"OUTPUT")
	k = _Builder(group)
	i = k.nodes.new("NodeGroupInput").outputs
	geometry = k.nodes.new("ShaderNodeNewGeometry")
	#Facing normal of the interpolated mesh normal, as the shader's front-face select. Not the NRRO-mapped normal.
	n = geometry.outputs["Normal"]
	tangentNode = k.nodes.new("ShaderNodeTangent")
	tangentNode.direction_type = "UV_MAP"
	tangentNode.uv_map = "UVMap0"
	t = k.vec("NORMALIZE",tangentNode.outputs["Tangent"])
	#RE bitangent = w * cross(unflipped N, T). Imports flip V, so on front faces Blender's bitangent is the
	#opposite of the RE one. Blender builds its bitangent from the facing normal (Cycles and EEVEE, measured),
	#so on back faces the two agree. A normal map node on (0.5, 1, 0.5) supplies Blender's bitangent.
	bitangentNode = k.nodes.new("ShaderNodeNormalMap")
	bitangentNode.space = "TANGENT"
	bitangentNode.uv_map = "UVMap0"
	bitangentNode.inputs["Color"].default_value = (0.5,1.0,0.5,1.0)
	cross = k.vec("CROSS_PRODUCT",n,t)
	agrees = k.math("GREATER_THAN",k.vec("DOT_PRODUCT",bitangentNode.outputs["Normal"],cross),0.0)
	#+1 when the RE bitangent is +cross(N, T): agreement flipped on front faces
	sameAsCross = k.math("COMPARE",agrees,geometry.outputs["Backfacing"],0.5)
	bitangent = k.vec("NORMALIZE",k.vec("SCALE",cross,scale = k.math("MULTIPLY_ADD",sameAsCross,2.0,-1.0)))
	#Flow direction: tangent-space HairFlowMap or the mesh bitangent
	flow = k.separate(i["Hair Flow"])
	fx,fy,fz = (k.math("MULTIPLY_ADD",flow[c],2.0,-HAIR_DECODE_OFFSET) for c in ("Red","Green","Blue"))
	flowWorld = k.vec("NORMALIZE",k.madd(n,fz,k.madd(bitangent,fy,k.vec("SCALE",t,scale = fx))))
	direction = k.vec("ADD",k.vec("SCALE",flowWorld,scale = k.greater0(i["UseFlowMap"])),k.vec("SCALE",bitangent,scale = k.math("SUBTRACT",1.0,k.greater0(i["UseFlowMap"]))))
	hss = k.separate(i["Spec Mask Shift"])
	shiftTexture = k.math("MULTIPLY_ADD",hss["Blue"],2.0,-HAIR_DECODE_OFFSET)
	primaryShift = k.math("SUBTRACT",i["Primary Anisotropy"],k.math("MULTIPLY",i["Primary Shift Offset"],shiftTexture))
	secondaryShift = k.math("SUBTRACT",i["Secondary Anisotropy"],i["Secondary Shift Offset"])
	primaryDirection = k.vec("NORMALIZE",k.madd(n,primaryShift,direction))
	secondaryDirection = k.vec("NORMALIZE",k.madd(n,secondaryShift,direction))
	#LightDirection is an RE world vector (Y up): Blender = (x, -z, y). Used unnormalized, as the shader does.
	light = k.combineXYZ(i["Light X"],k.math("MULTIPLY",i["Light Z"],-1.0),i["Light Y"])
	#Shader: normalize(L - cameraToSurface); Incoming already points from the surface to the camera.
	q = k.vec("NORMALIZE",k.vec("ADD",light,geometry.outputs["Incoming"]))
	j = k.math("MINIMUM",k.math("MAXIMUM",k.vec("DOT_PRODUCT",n,light),1e-5),1.0)
	primary = _lobe(k,primaryDirection,q,i["Primary Sharpness"],k.saturate(j))
	secondary = _lobe(k,secondaryDirection,q,i["Secondary Sharpness"],k.math("MULTIPLY",k.math("ADD",j,1.0),0.5,clamp = True))
	#Deep shadow: C = lerp(C0, C0 * lerp(DeepShadow, 1, AO), DeepShadow.a)
	ao = k.saturate(i["AO"])
	base,shadow = k.separate(i["Base Color"]),k.separate(i["Deep Shadow Color"])
	channels = ("Red","Green","Blue")
	color = [k.lerp(base[c],k.math("MULTIPLY",base[c],k.lerp(shadow[c],1.0,ao)),i["Deep Shadow Alpha"]) for c in channels]
	#Mask: HSS.G * (2AO + (1 - 2AO) * PrimalySpecularColor.a)
	twoAO = k.math("MULTIPLY",ao,2.0)
	weight = k.math("MULTIPLY",k.math("MULTIPLY",hss["Green"],k.math("MULTIPLY_ADD",k.math("SUBTRACT",1.0,twoAO),i["Primary Specular Alpha"],twoAO)),i["Vertex Mask"])
	specular = k.separate(i["Primary Specular Color"])
	secondaryScale = k.math("MULTIPLY",i["Secondary Intensity"],secondary)
	out = [k.math("MULTIPLY_ADD",color[index],i["Basecolor Fade"],k.math("MULTIPLY",weight,
		k.math("MULTIPLY_ADD",primary,specular[c],k.math("MULTIPLY",color[index],secondaryScale)))) for index,c in enumerate(channels)]
	output = k.nodes.new("NodeGroupOutput")
	k.links.new(k.combineColor(*out),output.inputs["Color"])
	return group

def addHairSpecularNodes(nodeTree,matInfo):
	if not isHairMaterial(matInfo):
		return None
	from .blender_nodes_re_mdf import linkMHWildsProp,getMHWildsBaseAOUVNode
	props = matInfo["mPropDict"]
	flowNode = matInfo["textureNodeDict"]["HairFlowMap"]
	maskNode = matInfo["textureNodeDict"]["Hair_Height_SpecMask_Shift_Map"]
	for image in (flowNode,maskNode):
		if getattr(image,"image",None) != None:
			image.image.colorspace_settings.name = "Non-Color"
			image.image.alpha_mode = "CHANNEL_PACKED"
	node = nodeTree.nodes.new("ShaderNodeGroup")
	node.node_tree = hairSpecularNodeGroup()
	node.name = "RE Hair Specular"
	node.label = "Hair Specular"
	#HairFlowMap reads the primary UV; HSS follows ChangeUV like the other base slots.
	primaryUV = nodeTree.nodes.get("UVMap1Node")
	maskUV = getMHWildsBaseAOUVNode(nodeTree,matInfo).outputs["Base UV"] if matInfo["gameName"] == "MHWILDS" else (primaryUV.outputs["UV"] if primaryUV != None else None)
	for image,uv in ((flowNode,primaryUV.outputs["UV"] if primaryUV != None else None),(maskNode,maskUV)):
		if uv != None and "Vector" in image.inputs:
			nodeTree.links.new(uv,image.inputs["Vector"])
	nodeTree.links.new(flowNode.outputs["Color"],node.inputs["Hair Flow"])
	nodeTree.links.new(maskNode.outputs["Color"],node.inputs["Spec Mask Shift"])
	albedo = matInfo["albedoNodeLayerGroup"]
	node.inputs["Base Color"].default_value = (.5,.5,.5,1.0)
	if albedo.currentOutSocket != None:
		nodeTree.links.new(albedo.currentOutSocket,node.inputs["Base Color"])
	occlusion = nodeTree.nodes.get("MHWildsOcclusion")
	if occlusion != None:
		nodeTree.links.new(occlusion.outputs["Value"],node.inputs["AO"])
	else:
		node.inputs["AO"].default_value = 1.0
	def link(label,socket,default,output = None):
		name = hairParam(props,label)
		if name == None:
			socket.default_value = default
			return
		linkMHWildsProp(nodeTree,matInfo,name,socket,output = output)
	link("UseFlowMap",node.inputs["UseFlowMap"],0.0)
	link("Primary Anisotropy",node.inputs["Primary Anisotropy"],0.0)
	#Wilds has no separate secondary anisotropy: its second lobe also starts from Primaly_Anisotropy.
	if hairParam(props,"Secondary Anisotropy") != None:
		link("Secondary Anisotropy",node.inputs["Secondary Anisotropy"],0.0)
	else:
		link("Primary Anisotropy",node.inputs["Secondary Anisotropy"],0.0)
	link("Primary Shift Offset",node.inputs["Primary Shift Offset"],0.0)
	link("Secondary Shift Offset",node.inputs["Secondary Shift Offset"],0.0)
	link("Primary Sharpness",node.inputs["Primary Sharpness"],1.0)
	link("Secondary Sharpness",node.inputs["Secondary Sharpness"],1.0)
	link("Primary Specular Color",node.inputs["Primary Specular Color"],(0.0,0.0,0.0,1.0),"Color")
	link("Primary Specular Color",node.inputs["Primary Specular Alpha"],0.0,"Alpha")
	link("Secondary Intensity",node.inputs["Secondary Intensity"],0.0)
	link("Deep Shadow Color",node.inputs["Deep Shadow Color"],(1.0,1.0,1.0,1.0),"Color")
	link("Deep Shadow Color",node.inputs["Deep Shadow Alpha"],0.0,"Alpha")
	link("Basecolor Fade",node.inputs["Basecolor Fade"],1.0)
	for index,axis in enumerate(("X","Y","Z")):
		link("Light Direction",node.inputs["Light "+axis],(0.0,1.0,0.0)[index],index)
	addVertexMaskNodes(nodeTree,matInfo,node)
	albedo.currentOutSocket = node.outputs["Color"]
	return node

def _meshesHaveVertexColor(material):
	users = [o for o in bpy.data.objects if o.type == "MESH" and any(slot.material == material for slot in o.material_slots)]
	return bool(users) and all(VERTEX_COLOR_LAYER in o.data.color_attributes for o in users)

def addVertexMaskNodes(nodeTree,matInfo,node):
	#mask = UseVertexColor_mask > 0 ? COLOR0.a : 1
	node.inputs["Vertex Mask"].default_value = 1.0
	name = hairParam(matInfo["mPropDict"],"UseVertexColor_mask")
	#A missing attribute reads as 0 in Blender and would erase the lobes, so meshes without colors keep mask 1.
	if name == None or not _meshesHaveVertexColor(matInfo["blenderMaterial"]):
		return
	from .blender_nodes_re_mdf import linkMHWildsProp
	color = nodeTree.nodes.new("ShaderNodeVertexColor")
	color.layer_name = VERTEX_COLOR_LAYER
	color.location = node.location + Vector((-400,-600))
	enabled = nodeTree.nodes.new("ShaderNodeMath")
	enabled.operation = "GREATER_THAN"
	enabled.inputs[1].default_value = 0.0
	linkMHWildsProp(nodeTree,matInfo,name,enabled.inputs[0])
	mask = nodeTree.nodes.new("ShaderNodeMix")
	mask.data_type = "FLOAT"
	mask.inputs["A"].default_value = 1.0
	nodeTree.links.new(enabled.outputs["Value"],mask.inputs["Factor"])
	nodeTree.links.new(color.outputs["Alpha"],mask.inputs["B"])
	nodeTree.links.new(mask.outputs["Result"],node.inputs["Vertex Mask"])

def hairOverNodeGroup():
	#Wilds HairOver (hair #64 and Base_Equip #65, identical): with UseHairOverMap the base is
	#2 * albedo * lerp(B, A, smooth(t)) * HO.rgb, t = saturate(saturate(C - (C+1)(1-Shift) + HO.a) / C); without it 2 * 0.5.
	name = "MHWildsHairOver_v1"
	group = bpy.data.node_groups.get(name)
	if group != None:
		return group
	from .blender_nodes_re_mdf import newGroupSockets
	group = bpy.data.node_groups.new(name,"ShaderNodeTree")
	newGroupSockets(group,[("Hair Over","NodeSocketColor"),("Hair Over Alpha","NodeSocketFloat"),("UseHairOverMap","NodeSocketFloat"),
		("Color A","NodeSocketColor"),("Color B","NodeSocketColor"),("Contrast","NodeSocketFloat"),("Shift","NodeSocketFloat")],"INPUT")
	newGroupSockets(group,[("Factor","NodeSocketColor")],"OUTPUT")
	k = _Builder(group)
	i = k.nodes.new("NodeGroupInput").outputs
	contrast = i["Contrast"]
	t = k.math("ADD",k.math("SUBTRACT",contrast,k.math("MULTIPLY",k.math("ADD",contrast,1.0),k.math("SUBTRACT",1.0,i["Shift"]))),i["Hair Over Alpha"],clamp = True)
	divisor = k.select(k.math("COMPARE",contrast,0.0,0.0),SAFE_DIVISOR,contrast)
	smooth = k.smoothstep01(k.math("DIVIDE",t,divisor,clamp = True))
	a,b,over = k.separate(i["Color A"]),k.separate(i["Color B"]),k.separate(i["Hair Over"])
	enabled = k.greater0(i["UseHairOverMap"])
	factor = [k.select(enabled,k.math("MULTIPLY",k.math("MULTIPLY",k.lerp(b[c],a[c],smooth),over[c]),2.0),1.0) for c in ("Red","Green","Blue")]
	output = k.nodes.new("NodeGroupOutput")
	k.links.new(k.combineColor(*factor),output.inputs["Factor"])
	return group

def addHairOverNodes(nodeTree,matInfo,texture):
	"""Returns the color the albedo is multiplied by, or None when the material has no Wilds HairOver parameters."""
	props = matInfo["mPropDict"]
	if matInfo["gameName"] != "MHWILDS" or "HairOverColorA_B_Contrast" not in props:
		return None
	from .blender_nodes_re_mdf import linkMHWildsProp
	node = nodeTree.nodes.new("ShaderNodeGroup")
	node.node_tree = hairOverNodeGroup()
	node.name = "MHWilds Hair Over"
	node.location = texture.location + Vector((300,0))
	#PrimaryUV_OverMap picks UV0, otherwise the secondary UV
	primary,secondary = nodeTree.nodes.get("UVMap1Node"),nodeTree.nodes.get("UVMap2Node")
	if primary != None and secondary != None and "Vector" in texture.inputs:
		pick = nodeTree.nodes.new("ShaderNodeMix")
		pick.data_type = "VECTOR"
		pick.location = texture.location + Vector((-250,0))
		usePrimary = nodeTree.nodes.new("ShaderNodeMath")
		usePrimary.operation = "GREATER_THAN"
		usePrimary.inputs[1].default_value = 0.0
		linkMHWildsProp(nodeTree,matInfo,"PrimaryUV_OverMap",usePrimary.inputs[0],0.0)
		nodeTree.links.new(usePrimary.outputs["Value"],pick.inputs["Factor"])
		nodeTree.links.new(secondary.outputs["UV"],pick.inputs["A"])
		nodeTree.links.new(primary.outputs["UV"],pick.inputs["B"])
		nodeTree.links.new(pick.outputs["Result"],texture.inputs["Vector"])
	nodeTree.links.new(texture.outputs["Color"],node.inputs["Hair Over"])
	nodeTree.links.new(texture.outputs["Alpha"],node.inputs["Hair Over Alpha"])
	linkMHWildsProp(nodeTree,matInfo,"UseHairOverMap",node.inputs["UseHairOverMap"],0.0)
	linkMHWildsProp(nodeTree,matInfo,"HairOverColorA",node.inputs["Color A"],(1.0,1.0,1.0,1.0),"Color")
	linkMHWildsProp(nodeTree,matInfo,"HairOverColorB",node.inputs["Color B"],(1.0,1.0,1.0,1.0),"Color")
	linkMHWildsProp(nodeTree,matInfo,"HairOverColorA_B_Contrast",node.inputs["Contrast"],1.0)
	linkMHWildsProp(nodeTree,matInfo,"HairOverColorA_B_Shift",node.inputs["Shift"],0.5)
	return node.outputs["Factor"]

def hairAlphaNodeGroup():
	#Hair #64 (NoPDO and NoPDO_FadeAlpha, identical) when Use_DefaultAlpha is 0:
	#a1 = a + (1-AO)*AO_Fade_Alpha*(3*sat(2a) - a - 2*sat(2a-1)); alpha = smooth(e) * a1,
	#e = saturate(saturate(W - (1-EdgeFade)(W+1) + |N.V|) / W), W = EdgeWidth. a is the AlphaAdjust * ColorParam.w alpha.
	name = "MHWildsHairAlpha_v1"
	group = bpy.data.node_groups.get(name)
	if group != None:
		return group
	from .blender_nodes_re_mdf import newGroupSockets
	group = bpy.data.node_groups.new(name,"ShaderNodeTree")
	newGroupSockets(group,[("Alpha","NodeSocketFloat"),("AO","NodeSocketFloat"),("Use_DefaultAlpha","NodeSocketFloat"),
		("AO_Fade_Alpha","NodeSocketFloat"),("EdgeWidth","NodeSocketFloat"),("EdgeFade","NodeSocketFloat")],"INPUT")
	newGroupSockets(group,[("Alpha","NodeSocketFloat")],"OUTPUT")
	k = _Builder(group)
	i = k.nodes.new("NodeGroupInput").outputs
	alpha = i["Alpha"]
	twice = k.math("MULTIPLY",alpha,2.0)
	boost = k.math("SUBTRACT",k.math("SUBTRACT",k.math("MULTIPLY",k.saturate(twice),3.0),alpha),k.math("MULTIPLY",k.math("ADD",twice,-1.0,clamp = True),2.0))
	occlusion = k.math("SUBTRACT",1.0,k.saturate(i["AO"]))
	faded = k.math("MULTIPLY_ADD",k.math("MULTIPLY",occlusion,i["AO_Fade_Alpha"]),boost,alpha)
	geometry = k.nodes.new("ShaderNodeNewGeometry")
	facing = k.math("ABSOLUTE",k.vec("DOT_PRODUCT",geometry.outputs["Normal"],geometry.outputs["Incoming"]))
	width = i["EdgeWidth"]
	edge = k.math("ADD",k.math("SUBTRACT",width,k.math("MULTIPLY",k.math("SUBTRACT",1.0,i["EdgeFade"]),k.math("ADD",width,1.0))),facing,clamp = True)
	divisor = k.select(k.math("COMPARE",width,0.0,0.0),SAFE_DIVISOR,width)
	fadedEdge = k.math("MULTIPLY",k.smoothstep01(k.math("DIVIDE",edge,divisor,clamp = True)),faded)
	output = k.nodes.new("NodeGroupOutput")
	k.links.new(k.select(k.greater0(i["Use_DefaultAlpha"]),alpha,fadedEdge),output.inputs["Alpha"])
	return group

def addHairAlphaNodes(nodeTree,matInfo):
	props = matInfo["mPropDict"]
	if matInfo.get("alphaSocket") == None or not all(name in props for name in ("AO_Fade_Alpha","EdgeWidth","EdgeFade")):
		return None
	from .blender_nodes_re_mdf import linkMHWildsProp
	node = nodeTree.nodes.new("ShaderNodeGroup")
	node.node_tree = hairAlphaNodeGroup()
	node.name = "MHWilds Hair Alpha"
	nodeTree.links.new(matInfo["alphaSocket"],node.inputs["Alpha"])
	occlusion = nodeTree.nodes.get("MHWildsOcclusion")
	if occlusion != None:
		nodeTree.links.new(occlusion.outputs["Value"],node.inputs["AO"])
	else:
		node.inputs["AO"].default_value = 1.0
	for name in HAIR_ALPHA_PROPS:
		linkMHWildsProp(nodeTree,matInfo,name,node.inputs[name],0.0)
	matInfo["alphaSocket"] = node.outputs["Alpha"]
	return node

def addHairAOLiftNodes(nodeTree,matInfo):
	#Hair (#64 NoPDO and FadeAlpha only) writes lerp(AO, 1, DeepShadowColor.a) to the lighting AO (RT3.z), because
	#DeepShadow already darkens the base color with AO; every other Wilds master writes the plain AO there.
	#The preview multiplies that AO into the base color, so lift it the same way instead of darkening twice.
	aoLayer = matInfo["aoNodeLayerGroup"]
	occlusion = nodeTree.nodes.get("MHWildsOcclusion")
	if occlusion == None or aoLayer.currentOutSocket == None or "DeepShadowColor" not in matInfo["mPropDict"]:
		return None
	from .blender_nodes_re_mdf import linkMHWildsProp
	clamp = nodeTree.nodes.new("ShaderNodeMath")
	clamp.operation = "ADD"
	clamp.use_clamp = True
	lift = nodeTree.nodes.new("ShaderNodeMix")
	lift.data_type = "FLOAT"
	lift.name = "MHWilds Hair AO Lift"
	lift.location = occlusion.location + Vector((200,-150))
	lift.inputs["B"].default_value = 1.0
	#Replace the plain AO where it feeds the AO layer, keep every other consumer (DeepShadow, hair alpha) on the raw value
	for link in [l for l in occlusion.outputs["Value"].links if l.to_node != lift]:
		if link.to_node.bl_idname == "ShaderNodeGroup" and link.to_node.name.startswith(("RE Hair","MHWilds Hair")):
			continue
		nodeTree.links.new(lift.outputs["Result"],link.to_socket)
	nodeTree.links.new(occlusion.outputs["Value"],clamp.inputs[0])
	nodeTree.links.new(clamp.outputs["Value"],lift.inputs["A"])
	linkMHWildsProp(nodeTree,matInfo,"DeepShadowColor",lift.inputs["Factor"],output = "Alpha")
	if aoLayer.currentOutSocket == occlusion.outputs["Value"]:
		aoLayer.currentOutSocket = lift.outputs["Result"]
	return lift
