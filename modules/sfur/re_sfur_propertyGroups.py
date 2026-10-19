#Author: NSA Cloud
import bpy
from bpy.props import (StringProperty,
					   BoolProperty,
					   IntProperty,
					   FloatProperty,
					   FloatVectorProperty,
					   EnumProperty,
					   PointerProperty,
					   CollectionProperty,
					   )


def update_preview(self, context):
	from .blender_sfur_preview import request_update
	request_update(self.id_data)


def update_materialName(self, context):
	update_preview(self, context)
	parentObj = self.id_data
	try:
		#print(parentObj)
		if parentObj != None:
			split = parentObj.name.split("(",1)
			if len(split) == 2:
				parentObj.name = f"{split[0]}({self.materialName})"
			else:
				parentObj.name =f"Shell Fur 00 ({self.materialName})"
	except:
		pass

class SFurEntryPropertyGroup(bpy.types.PropertyGroup):
	materialName: StringProperty(
		name = "Material Name",
		description = "MDF Material to assign shell fur to.\nNote that the material must be a shell fur material. (Check if the mmtr path has shell fur in it)",
		default = "ShellFurMat00",
		update=update_materialName
		)
	groomingTexturePath: StringProperty(
		name = "Grooming Texture Path",
		description = "Texture used to determine the direction that the fur will point.\nTip: If you don't have a grooming texture, you can use a standard normal map for a somewhat decent result.",
		default = "systems/rendering/NullNormal.tex",
		update=update_preview,
		)
	shellCount: IntProperty(
		name = "Shell Count",
		description = "",
		default = 12,
		soft_min = 0,
		soft_max = 100,
		update=update_preview,
		)

	shellThinType: EnumProperty(
		name = "Shell Thin Type",
		description = "",
		items=[ ("0", "Ascending", ""),
				("1", "Descending", ""),
				("2", "Intermediate", ""),
			  ],
		default = "0",
		)

	groomingTexCoordType: EnumProperty(
		name = "Grooming Tex Coord Type",
		description = "",
		items=[ ("0", "UV Primary", ""),
				("1", "UV Secondary", ""),
			  ],
		default = "0",
		update=update_preview,
		)

	shellHeight: FloatProperty(
		name = "Shell Height",
		description = "",
		default = 0.03,
		soft_min = 0.0,
		soft_max = 0.3,
		update=update_preview,
		)

	bendRate: FloatProperty(
		name = "Bend Rate",
		description = "",
		default = 1.0,
		soft_min = 0.0,
		soft_max = 1.0,
		update=update_preview,
		)

	bendRootRate: FloatProperty(
		name = "Bend Root Rate",
		description = "",
		default = 0.0,
		soft_min = 0.0,
		soft_max = 1.0,
		update=update_preview,
		)

	normalTransformRate: FloatProperty(
		name = "Normal Transform Rate",
		description = "",
		default = 0.0,
		soft_min = 0.0,
		soft_max = 1.0,
		update=update_preview,
		)
	
	stiffness: FloatProperty(
		name = "Stiffness",
		description = "",
		default = 1.0,
		soft_min = 0.0,
		soft_max = 1.0,
		)

	stiffnessDistribution: FloatProperty(
		name = "Stiffness Distribution",
		description = "",
		default = 0.0,
		soft_min = 0.0,
		soft_max = 1.0,
		)

	springCoefficient: FloatProperty(
		name = "Spring Coefficient",
		description = "",
		default = 0.0,
		soft_min = 0.0,
		soft_max = 1.0,
		)

	damping: FloatProperty(
		name = "Damping",
		description = "",
		default = 0.0,
		soft_min = 0.0,
		soft_max = 1.0,
		)

	gravityForceScale: FloatProperty(
		name = "Gravity Force Scale",
		description = "",
		default = 1.0,
		soft_min = 0.0,
		soft_max = 1.0,
		)

	directWindForceScale: FloatProperty(
		name = "Direct Wind Force Scale",
		description = "",
		default = 1.0,
		soft_min = 0.0,
		soft_max = 1.0,
		)
	isForceTwoSide: BoolProperty(
		name = "Is Force Two Side",
		description = "",
		default = False,
		update=update_preview,
		)
	isForceAlphaTest: BoolProperty(
		name = "Is Force Alpha Test",
		description = "",
		default = False,
		update=update_preview,
		)
	unknownFlag: IntProperty(
		name = "Unknown Flags",
		description = "",
		default = 0,
		min = 0,
		max = 65536,
		)
	