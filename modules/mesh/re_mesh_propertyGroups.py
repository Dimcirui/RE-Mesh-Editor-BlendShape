#Author: NSA Cloud
import bpy
import os
from bpy.props import (StringProperty,
					   BoolProperty,
					   IntProperty,
					   FloatProperty,
					   FloatVectorProperty,
					   EnumProperty,
					   PointerProperty,
					   CollectionProperty,
					   )


def getBatchMeshWeightLimitDefault(path):
	"""Use the destination game's total weight slots, or eight for an unknown path."""
	from .blender_re_mesh import getMeshWeightLimits
	from .file_re_mesh import meshFileVersionToGameNameDict
	try:
		version = int(os.path.splitext(path)[1].lstrip("."))
	except (TypeError, ValueError):
		return 8
	game = meshFileVersionToGameNameDict.get(version)
	return getMeshWeightLimits(game)[1] if game is not None else 8


def setBatchMeshWeightLimit(item, value, explicit=False):
	"""Distinguish an automatically chosen default from a saved/user choice."""
	item.limitTotalCount = value
	if isinstance(item, bpy.types.PropertyGroup):
		item.batchWeightLimitExplicit = bool(explicit)


def getBatchMeshWeightLimit(item):
	# Fresh items may be supplied with only a destination path.
	if hasattr(item, "is_property_set") and not item.is_property_set("limitTotalCount"):
		return getBatchMeshWeightLimitDefault(item.path)
	return getattr(item, "limitTotalCount", getBatchMeshWeightLimitDefault(item.path))


def update_batchWeightLimit(self, _context):
	self.batchWeightLimitExplicit = True


def update_relPathToAbs(self,context):
	try:
		if "//" in self.path:
			#print("updated path")
			self.path = os.path.realpath(bpy.path.abspath(self.path))
	except:
		pass
	if self.path == "" or self.path.count(".") < 2:#Check if path is empty or if number extension is missing
		self.invalid = True
	else:
		self.invalid = False
	if self.exportType == "MESH" and not self.batchWeightLimitExplicit:
		setBatchMeshWeightLimit(self, getBatchMeshWeightLimitDefault(self.path))
class ExporterNodePropertyGroup(bpy.types.PropertyGroup):
	name: StringProperty(
        name="",
		description = "",
	)
	icon: StringProperty(
        name="",
		description = "",
	)
	enabled: BoolProperty(
		name="",
		description = "",
		default = True,

	)
	show: BoolProperty(
		name="",
		description = "",
		default = True
	)
	hasChild: BoolProperty(
		name="",
		description = "",
		default = False
	)
	expand: BoolProperty(
		name="",
		description = "",
		default = True
	)
	
	parentName: StringProperty(
		name="",
		description = "",
		default = ""
	)
	hierarchyLevel: IntProperty(
		name="",
		description = "",
		default = 0
	)
	exportType: StringProperty(
        name="",
		description = "",
		default = ""
	)
	batchWeightLimitExplicit: BoolProperty(
		name="Weight Limit Explicit",
		description="Internal marker for a saved or manually edited batch weight limit",
		default=False,
		options={'HIDDEN', 'SKIP_SAVE'},
	)
	path: StringProperty(
        name="",
		subtype="FILE_PATH",
		description = "Path to where to export the file to",
		update = update_relPathToAbs
	)
	invalid: BoolProperty(
		name="",
		description = "",
		default = False
	)

	#mesh operator arguments
	
	exportAllLODs : BoolProperty(
	   name = "Export All LODs",
	   description = "Export all LODs. If disabled, only LOD0 will be exported. Note that LODs meshes must be grouped inside a collection for each level and that collection must be contained in another collection. See a mesh with LODs imported for reference on how it should look. A target collection must also be set",
	   default = True)
	exportBlendShapes : BoolProperty(
	   name = "Export Blend Shapes",
	   description = "Exports blend shapes from mesh if present",
	   default = True)
	rotate90 : BoolProperty(
	   name = "Convert Z Up To Y Up",
	   description = "Rotates objects 90 degrees for export. Leaving this option enabled is recommended",
	   default = True)
	autoSolveRepeatedUVs : BoolProperty(
	   name = "Auto Solve Repeated UVs",
	   description = "Splits connected UV islands if present. The mesh format does not allow for multiple uvs assigned to a vertex.\nNOTE: This will modify the object and may slightly increase time taken to export",
	   default = True)
	preserveSharpEdges : BoolProperty(
	   name = "Split Sharp Edges",
	   description = "Edge splits all edges marked as sharp to preserve them on the exported mesh.\nNOTE: This will modify the exported mesh",
	   default = True)
	splitLoopVertices : BoolProperty(
	   name = "Split Vertices For Corner Attributes",
	   description = "Creates extra exported vertices when loop/corner normals, tangents, UVs, or colors differ. Enable this to preserve hard normals and other data. Disable it to keep 1:1 vertex per Blender vertex.",
	   default = True)
	limitTotal : BoolProperty(
	   name = "Limit Total",
	   description = "Keep in mind, you will probably want to enable the setting for normalize weights if you enable this setting. Otherwise, limit total manually/without this setting to preserve unnormalized weights.",
	   default = False)
	limitTotalCount : IntProperty(
	   name = "Max Weights",
	   description = "The game's max supported weight is default here.",
	   default = 8,
	   min = 1,
	   max = 32,
	   update = update_batchWeightLimit)
	normalizeWeights : BoolProperty(
	   name = "Normalize Weights",
	   description = "Normalize each set of vertex weights to 1.0 automatically/on export.",
	   default = True)
	preserveMaterialTable : BoolProperty(
	   name = "Preserve Original Material Table",
	   description = "Keep the original material slot order of the imported mesh, including unused slots. New materials are appended at the end with a warning. Requires a mesh imported with this version of the addon",
	   default = False)
	# Mirrors ExportREMesh.shapeKeyExportMode in __init__.py; keep the two in sync.
	shapeKeyExportMode : EnumProperty(
		name = "Export Shapekeys?",
		description = "Choose whether and how Blender shape keys are exported as blendshapes",
		items = [
			(
				"NO",
				"No",
				"Do not export Blender shape keys or Wilds blendshape data. Alternatevly, if exporting shapekeys, you can use the prefix 'DUMMY_' for shapekey names, or untick (mute) them, to exclude export of them"
			),
			(
				"MODE1",
				"Recalculate Normals (in game)",
				"Writes normal-recalc tables, as vanilla faces and armor do. The game recalculates normals from the deformed geometry at runtime, so authored custom normals are replaced by recalculated ones"
			),
			(
				"KEEPNORMALS",
				"Keep Normals (as in Blender)",
				"Vanilla no-recalc layout (as on the Seikret): no normal-recalc marker, no recalc tables, 8-byte delta rows. The game keeps the authored custom normals while shape keys deform the geometry"
			),
			(
				"KEEPNORMALS_SURFACE",
				"Keep Normals (surface turn)",
				"Same layout as Keep Normals (as in Blender). Each key's normals turn only with the real turn of the surface, so stylised custom normals keep their offset where a key shears or squashes the mesh (eyelids, lips) instead of following Blender's re-decoded normals. On meshes whose normals are not stylised the result is the same"
			),
		],
		default = "KEEPNORMALS_SURFACE"
	)
	useBlenderMaterialName : BoolProperty(
	   name = "Use Blender Material Names",
	   description = "If left unchecked, the exporter will get the material names to be used from the end of each object name. For example, if a mesh is named LOD_0_Group_0_Sub_0__Shirts_Mat, the material name is Shirts_Mat. If this option is enabled, the material name will instead be taken from the first material assigned to the object",
	   default = False)
	preserveBoneMatrices : BoolProperty(
	   name = "Preserve Bone Matrices",
	   description = "Export using the original matrices of the imported bones. Note that this option only applies armatures imported with this addon. Any newly added bones will have new matrices calculated",
	   default = False)
	exportBoundingBoxes : BoolProperty(
	   name = "Export Bounding Boxes",
	   description = "Exports the original bounding boxes from the \"Import Bounding Boxes\" import option. New bounding boxes will be generated for any bones that do not have them",
	   default = False)
	
	
class MESH_UL_REExporterList(bpy.types.UIList):
	
	def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
				
			row = layout.row()
			if not item.hasChild and item.invalid:
				row.alert = True
			col1 = row.column()
			#col1.prop(item,"expand")
			col1.alignment = "RIGHT"
			col1.label(text="      |    "*item.hierarchyLevel if item.hierarchyLevel != 0 else " ")
			if not item.hasChild:
				col2 = row.column()
				col2.prop(item,"enabled")
			col3 = row.column()
			col3.label(icon = item.icon,text=item.name)
			col4 = row.column()
			
	# Disable double-click to rename
	def invoke(self, context, event):
		return {'PASS_THROUGH'}
