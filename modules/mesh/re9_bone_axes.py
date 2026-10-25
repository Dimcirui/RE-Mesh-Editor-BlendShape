"""RE9 bone axis remap: show RE9 bones in Blender with the axes every other RE
Engine game uses, while the mesh file keeps RE9's own joint-orient axes.

RE9 bones aim local X down the bone and give each limb chain its own 90-degree
base frame, so zeroing rotations does not give a T-pose there. Each bone gets a
correction C with  file rotation = Blender rotation @ C.  Blender rest is
F @ C^-1 on import and the exporter multiplies C back. C is bone-local (right
multiplied), so any world-space edit of the rest pose commutes with it and the
round trip stays exact.

C per bone:
  * body bones: the table below, so zero rotation = T-pose like RE4/Wilds.
    Values are the RE9 reference T-pose frames (refskel ch02: spine/legs 0.0
    deg, arm/finger residuals = refskel anatomy). Same table as Modding-Toolkit
    core/pose_ops.py (_build_re9_correction + _build_re9_c_supplement).
  * bones whose rest rotation equals their parent's (twist/offset helpers,
    chain links): the parent's C, so they stay coaxial with the parent.
  * everything else (physics chain roots, props): their own rest rotation, so
    they show upright (identity) in Blender.
C is stored per bone and never recomputed on export.
"""

from math import cos, radians

from mathutils import Matrix

AXIS_CORRECTION_PROP = "reAxisCorrection"
# Armature data flag read by other tools (see REME_FEATURES "re9_bone_axes").
ARMATURE_AXIS_FLAG = "REMeshBoneAxes"
ARMATURE_AXIS_FLAG_RE9 = "RE9"

# Cosine of the angle (0.5 deg) under which a bone counts as coaxial with its parent.
COAXIAL_COS = cos(radians(0.5))

_C_IDENTITY = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
_C_FLIP_X = ((1, 0, 0), (0, -1, 0), (0, 0, -1))
_C_LEG_L = ((0, 1, 0), (-1, 0, 0), (0, 0, 1))
_C_LEG_R = ((0, 1, 0), (1, 0, 0), (0, 0, -1))
_C_TOE_L = ((0, 1, 0), (0, 0, 1), (1, 0, 0))
_C_TOE_R = ((0, 1, 0), (0, 0, -1), (-1, 0, 0))
_C_TORSO = ((0, -1, 0), (1, 0, 0), (0, 0, 1))
# Thumbs are not axis aligned; measured matrices from a hand-made RE9 rig.
_C_THUMB = {
	"L_Hand_ThumbF_1": (( 0.77393, -0.44248, -0.45304),
						(-0.25685,  0.43458, -0.86323),
						( 0.57884,  0.78445,  0.22268)),
	"L_Hand_ThumbF_2": (( 0.99539, -0.08890, -0.03592),
						(-0.00840,  0.29229, -0.95630),
						( 0.09551,  0.95219,  0.29019)),
	"L_Hand_ThumbF_3": (( 0.98800, -0.10028, -0.11746),
						(-0.08358,  0.29236, -0.95265),
						( 0.12987,  0.95103,  0.28047)),
	"R_Hand_ThumbF_1": (( 0.77393, -0.44248, -0.45304),
						( 0.25685, -0.43458,  0.86323),
						(-0.57884, -0.78445, -0.22268)),
	"R_Hand_ThumbF_2": (( 0.99539, -0.08890, -0.03592),
						( 0.00840, -0.29229,  0.95629),
						(-0.09551, -0.95219, -0.29019)),
	"R_Hand_ThumbF_3": (( 0.98800, -0.10028, -0.11745),
						( 0.08357, -0.29236,  0.95265),
						(-0.12987, -0.95103, -0.28048)),
}

def _build_body_table():
	fingers = tuple(f"Hand_{finger}_{i}"
					for finger in ("IndexF", "MiddleF", "RingF", "PinkyF")
					for i in (1, 2, 3))
	table = {}
	for suffix in ("Arm_Clavicle", "Arm_Upper", "Arm_Lower", "Arm_Hand", "Hand_Palm") + fingers:
		table["L_" + suffix] = _C_IDENTITY
		table["R_" + suffix] = _C_FLIP_X
	for suffix in ("Leg_Upper", "Leg_Lower", "Leg_Ankle"):
		table["L_" + suffix] = _C_LEG_L
		table["R_" + suffix] = _C_LEG_R
	table["L_Leg_Toes"] = _C_TOE_L
	table["R_Leg_Toes"] = _C_TOE_R
	for name in ("Hip", "Spine_0", "Spine_1", "Spine_2", "Neck_0", "Neck_1", "Head_0"):
		table[name] = _C_TORSO
	for name, value in _C_THUMB.items():
		table[name] = value
	return table

RE9_BODY_CORRECTION = {name: Matrix(value).normalized() for name, value in _build_body_table().items()}

def _file_rotation(rowMatrix):
	# RE matrices are row-major with axes in rows; Blender wants axes in columns.
	return Matrix(rowMatrix).transposed().to_3x3().normalized()

def parsedSkeletonRotations(parsedSkeleton):
	"""(names, parent indices, file world rotations) of a parsed mesh skeleton."""
	boneList = parsedSkeleton.boneList
	return ([bone.boneName for bone in boneList], [bone.parentIndex for bone in boneList],
		[_file_rotation(bone.worldMatrix.matrix) for bone in boneList])

def _angleCos(a, b):
	local = a.transposed() @ b
	return (local[0][0] + local[1][1] + local[2][2] - 1.0) * 0.5

# Torso bones sit on _C_TORSO (bone X up) in RE9, about 90 degrees from it in the other
# convention. .fbxskel.8 is shared with Pragmata, which uses the other convention.
_TORSO_NAMES = ("Hip", "Spine_0", "Spine_1", "Spine_2", "Neck_0", "Neck_1", "Head_0")
_TORSO_MATCH_COS = cos(radians(45.0))

def usesRE9Axes(names, rotations):
	"""True if the skeleton's torso bones are in RE9's joint-orient axes."""
	torso = RE9_BODY_CORRECTION["Hip"]
	found = [rotations[index] for index, name in enumerate(names) if name in _TORSO_NAMES]
	matched = sum(1 for rotation in found if _angleCos(torso, rotation) > _TORSO_MATCH_COS)
	return bool(found) and matched * 2 >= len(found)

def computeCorrections(names, parentIndices, rotations):
	"""Returns {bone index: 3x3 Matrix C}."""
	corrections = {}
	def resolve(index):
		correction = corrections.get(index)
		if correction is not None:
			return correction
		table = RE9_BODY_CORRECTION.get(names[index])
		parentIndex = parentIndices[index]
		if table is not None:
			correction = table.copy()
		elif (parentIndex is not None and 0 <= parentIndex < len(rotations) and parentIndex != index
				and _angleCos(rotations[parentIndex], rotations[index]) > COAXIAL_COS):
			correction = resolve(parentIndex).copy()
		else:
			correction = rotations[index].copy()
		corrections[index] = correction
		return correction
	for index in range(len(names)):
		resolve(index)
	return corrections

def correctionToProp(correction):
	return [value for row in correction for value in row]

def correctionFromProp(value):
	if value is None:
		return None
	values = list(value)
	if len(values) != 9:
		return None
	return Matrix((values[0:3], values[3:6], values[6:9]))

def blenderRestMatrix(rowWorldMatrix, correction):
	"""Blender edit-bone matrix for a file world matrix and its correction."""
	return Matrix(rowWorldMatrix).transposed() @ correction.inverted().to_4x4()

def fileWorldMatrices(armatureData, copyParentForNewBones = False):
	"""File-space world matrices (Blender column form) for the bones of an
	armature already transformed into RE space. Bones with a stored correction
	get it multiplied back. Bones without one keep their Blender rotation, or
	take the parent's file rotation when copyParentForNewBones is set (RE9 rule
	for hand-added bones)."""
	result = {}
	def resolve(bone):
		matrix = result.get(bone.name)
		if matrix is not None:
			return matrix
		correction = correctionFromProp(bone.get(AXIS_CORRECTION_PROP))
		local = bone.matrix_local.to_4x4()
		if correction is not None:
			matrix = local @ correction.to_4x4()
		elif copyParentForNewBones and bone.parent is not None:
			parentMatrix = resolve(bone.parent)
			matrix = parentMatrix.to_3x3().normalized().to_4x4()
			matrix.translation = local.translation
		else:
			matrix = local
		result[bone.name] = matrix
		return matrix
	for bone in armatureData.bones:
		resolve(bone)
	return result
