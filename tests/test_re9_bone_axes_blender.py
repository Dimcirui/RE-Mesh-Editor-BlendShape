"""RE9 bone axis remap on a synthetic RE9-style skeleton.
Body bones zero to the standard basis, coaxial helpers follow their parent, physics
roots show upright, and file matrices survive import -> rest edit -> export.
A skeleton in the other games' axes (Pragmata shares .fbxskel.8 with RE9) is left alone.
"""
import importlib
import math
import os
from pathlib import Path
import sys

import addon_utils
import bpy
from mathutils import Matrix, Quaternion, Vector

addon = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(addon.parent))
addon_utils.enable(addon.name, default_set=True)
axes = importlib.import_module(addon.name + ".modules.mesh.re9_bone_axes")
meshMod = importlib.import_module(addon.name + ".modules.mesh.blender_re_mesh")
parse = importlib.import_module(addon.name + ".modules.mesh.re_mesh_parse")

def check(name, ok, detail=None):
	print(("PASS " if ok else "FAIL ") + name, detail if detail is not None else "", flush=True)
	assert ok, (name, detail)

def rowMatrix(rotation, translation):
	# RE file layout: axes in rows, translation in the last row
	m = rotation.to_4x4()
	m.translation = translation
	return [list(row) for row in m.transposed()]

def makeBone(name, parent, rotation, translation):
	bone = parse.ParsedBone()
	bone.boneName = name
	bone.parentIndex = parent
	bone.worldMatrix.matrix = rowMatrix(rotation, translation)
	bone.localMatrix.matrix = rowMatrix(Matrix.Identity(3), Vector())
	bone.inverseMatrix.matrix = rowMatrix(Matrix.Identity(3), Vector())
	bone.boundingBox = None
	return bone

# RE9 T-pose frames: Hip is the torso basis, a hair root yawed 30 deg about Y, its link
# coaxial, a twist helper coaxial with the arm.
torso = axes.RE9_BODY_CORRECTION["Hip"]
arm = axes.RE9_BODY_CORRECTION["R_Arm_Upper"]
hairYaw = Quaternion((0, 1, 0), math.radians(30)).to_matrix()
skeleton = parse.Skeleton()
skeleton.boneList = [
	makeBone("root", -1, Matrix.Identity(3), Vector()),
	makeBone("Hip", 0, torso, Vector((0, 1, 0))),
	makeBone("R_Arm_Upper", 1, arm, Vector((-0.2, 1.4, 0))),
	makeBone("R_Arm_Upper_Twist_0", 2, arm, Vector((-0.3, 1.4, 0))),
	makeBone("HairA_00", 1, hairYaw, Vector((0, 1.6, 0.05))),
	makeBone("HairA_01", 4, hairYaw, Vector((0, 1.55, 0.05))),
]
names, parents, rotations = axes.parsedSkeletonRotations(skeleton)
check("RE9 torso detected", axes.usesRE9Axes(names, rotations))
check("standard-axis torso not detected", not axes.usesRE9Axes(["Hip", "Spine_0", "Head_0"], [Matrix.Identity(3)] * 3))
check("skeleton without torso not detected", not axes.usesRE9Axes(["HairA_00"], [hairYaw]))
corrections = axes.computeCorrections(names, parents, rotations)
def angle(a, b):
	q = (a.transposed() @ b).to_quaternion()
	return min(math.degrees(q.angle), 360 - math.degrees(q.angle))
check("body bone takes the table", angle(corrections[1], torso) < 1e-4)
check("twist helper inherits the arm", angle(corrections[3], corrections[2]) < 1e-4)
check("hair root uses its own rotation", angle(corrections[4], hairYaw) < 1e-4)
check("hair link inherits the root", angle(corrections[5], corrections[4]) < 1e-4)

bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable(addon.name, default_set=True)
armatureObj = meshMod.importSkeleton(skeleton, "RE9 Test Armature", bpy.context.scene.collection, True, "", True)
bones = armatureObj.data.bones
check("armature flag", armatureObj.data.get(axes.ARMATURE_AXIS_FLAG) == axes.ARMATURE_AXIS_FLAG_RE9)
zeroBasis = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))  # bone Y up in Blender Z-up space
for name in ("Hip", "R_Arm_Upper", "HairA_00", "HairA_01"):
	check(f"{name} shows the standard basis", angle(bones[name].matrix_local.to_3x3().normalized(), zeroBasis) < 1e-3)
check("twist helper coaxial with arm", angle(bones["R_Arm_Upper_Twist_0"].matrix_local.to_3x3(), bones["R_Arm_Upper"].matrix_local.to_3x3()) < 1e-3)

def exportWorlds(obj, copyParent = False):
	data = obj.data.copy()
	data.transform(meshMod.rotateNeg90Matrix @ obj.matrix_world)
	worlds = axes.fileWorldMatrices(data, copyParent)
	bpy.data.armatures.remove(data)
	return worlds

def maxDiff(a, b):
	return max(abs(a[i][j] - b[i][j]) for i in range(4) for j in range(4))

original = {bone.boneName: Matrix(bone.worldMatrix.matrix).transposed() for bone in skeleton.boneList}
worlds = exportWorlds(armatureObj)
check("export restores file matrices", max(maxDiff(worlds[n], original[n]) for n in original) < 1e-5,
	max(maxDiff(worlds[n], original[n]) for n in original))

# A rest edit in Blender (whole rig turned) must turn the file matrices the same way.
bpy.context.view_layer.objects.active = armatureObj
bpy.ops.object.mode_set(mode='EDIT')
turn = Matrix.Rotation(math.radians(40), 4, "Z")
for editBone in armatureObj.data.edit_bones:
	editBone.matrix = turn @ editBone.matrix
newBone = armatureObj.data.edit_bones.new("HairA_02")
newBone.head = armatureObj.data.edit_bones["HairA_01"].head
newBone.tail = newBone.head + Vector((0, 0, 0.05))
newBone.parent = armatureObj.data.edit_bones["HairA_01"]
bpy.ops.object.mode_set(mode='OBJECT')
turnRE = meshMod.rotateNeg90Matrix @ turn @ meshMod.rotate90Matrix
worlds = exportWorlds(armatureObj)
check("rest edit carries through the correction", max(maxDiff(worlds[n], turnRE @ original[n]) for n in original) < 1e-5,
	max(maxDiff(worlds[n], turnRE @ original[n]) for n in original))
check("new bone keeps its Blender rotation by default", angle(worlds["HairA_02"].to_3x3(), Matrix.Identity(3)) < 1e-3)
worlds = exportWorlds(armatureObj, True)
check("new bone copies the parent with the option", angle(worlds["HairA_02"].to_3x3(), worlds["HairA_01"].to_3x3()) < 1e-4)
print("ALL PASSED")
