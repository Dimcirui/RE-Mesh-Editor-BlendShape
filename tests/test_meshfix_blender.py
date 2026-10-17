"""Fixture-neutral Blender checks for imported normals, weight banks and seams.

Adapted from the ZZtaii fork (tests/test_meshfix_blender.py): ordinary exports
use the RE4 version instead of SF6, and Wilds checks cover this fork's
"Recalculate Normals" (1) and KEEPNORMALS (-1) shape key modes.

Run with Blender --background --factory-startup --python-exit-code 1 --python
tests/test_meshfix_blender.py. Uses synthetic meshes, never retail assets.
"""
import importlib
from pathlib import Path
import sys
import tempfile

import addon_utils
import bpy
from mathutils import Vector
import numpy as np


def main():
	repo = Path(__file__).resolve().parents[1]
	sys.path.insert(0, str(repo.parent))
	addon_utils.enable(repo.name, default_set=True)
	mesh_io = importlib.import_module(repo.name + ".modules.mesh.blender_re_mesh")
	parse = importlib.import_module(repo.name + ".modules.mesh.re_mesh_parse")
	codec = importlib.import_module(repo.name + ".modules.mesh.file_re_mesh")
	collection = bpy.data.collections.new("MeshFixChecks")
	bpy.context.scene.collection.children.link(collection)
	vertices = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
	faces = [(0, 1, 2)]
	imported = mesh_io.importMesh(
		"rotated_normal", vertexList=vertices, faceList=faces,
		vertexNormalList=[(0, 0, 1)] * 3, material=None,
		collection=collection, rotate90=True)
	expected_normal = mesh_io.rotate90Matrix.to_3x3() @ Vector((0, 0, 1))
	for normal in imported.data.corner_normals:
		assert (normal.vector - expected_normal).length < 1e-5, (normal.vector, expected_normal)
	print("PASS custom normals follow imported axis rotation", flush=True)

	primary = [[1, 0, 0, 0, 0, 0, 0, 0]] * 3
	secondary = [[0, 1, 0, 0, 0, 0, 0, 0]] * 3
	indices = [[0, 1, 0, 0, 0, 0, 0, 0]] * 3
	weighted = mesh_io.importMesh(
		"secondary_weight", vertexList=vertices, faceList=faces,
		boneNameList=["primary", "secondary"],
		vertexGroupWeightList=primary, vertexGroupBoneIndicesList=indices,
		vertexGroupWeightListSecondary=secondary,
		vertexGroupBoneIndicesListSecondary=indices,
		material=None, collection=collection, rotate90=False)
	for vertex in weighted.data.vertices:
		memberships = {weighted.vertex_groups[g.group].name: g.weight for g in vertex.groups}
		assert memberships == {"primary": 1.0, "SHAPEKEY_secondary": 1.0}, memberships
	print("PASS DD2 secondary bank imports independently of primary weights", flush=True)

	for index in range(10):
		for prefix in ("bank_", "SHAPEKEY_bank_"):
			group = weighted.vertex_groups.new(name=prefix + str(index))
			group.add([0], .01 * (index + 1), "REPLACE")
	mesh_io.limitTotalWeights(weighted, 8, separateShapeKeyWeights=True)
	banks = [0, 0]
	for assignment in weighted.data.vertices[0].groups:
		name = weighted.vertex_groups[assignment.group].name
		banks[name.startswith("SHAPEKEY_")] += 1
	assert banks == [8, 8], banks
	weighted.data.use_paint_mask = True
	weighted.data.use_paint_mask_vertex = True
	mesh_io.limitTotalWeights(weighted, 6)
	assert max(len(vertex.groups) for vertex in weighted.data.vertices) <= 6
	print("PASS Limit Total handles DD2 banks and active paint masks", flush=True)

	seam_collection = bpy.data.collections.new("SeamExportChecks")
	bpy.context.scene.collection.children.link(seam_collection)
	data = bpy.data.meshes.new("corner_seam")
	data.from_pydata([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)],
					 [], [(0, 1, 2), (0, 2, 3)])
	data.update()
	data.polygons.foreach_set("use_smooth", [True] * 2)
	for edge in data.edges:
		if set(edge.vertices) == {0, 2}:
			edge.use_edge_sharp = True
	data.normals_split_custom_set([(0, 0, 1)] * 3 + [(0, 1, 0)] * 3)
	uv = data.uv_layers.new(name="UVMap")
	for loop, coordinate in zip(uv.data, [(0, 0), (1, 0), (1, 1), (.25, .25), (.75, .75), (0, 1)]):
		loop.uv = coordinate
	material = bpy.data.materials.new("MeshFixMaterial")
	data.materials.append(material)
	obj = bpy.data.objects.new("LOD_0_Group_0_Sub_0__MeshFixMaterial", data)
	seam_collection.objects.link(obj)
	options = dict(
		targetCollection=seam_collection.name, selectedOnly=False, exportAllLODs=False,
		exportBlendShapes=False, rotate90=False, useBlenderMaterialName=True,
		preserveBoneMatrices=False, exportBoundingBoxes=False,
		autoSolveRepeatedUVs=False, preserveSharpEdges=False,
		splitLoopVertices=True, normalizeWeights=True)
	before = [tuple(vertex.co) for vertex in data.vertices]
	with tempfile.TemporaryDirectory(prefix="meshfix-seams-") as temporary:
		output = Path(temporary) / "seam.mesh.221108797"
		assert mesh_io.exportREMeshFile(str(output), options)
		parsed = parse.ParsedREMesh()
		parsed.ParseREMesh(codec.readREMesh(str(output)))
		submesh = parsed.mainMeshLODList[0].visconGroupList[0].subMeshList[0]
		assert len(submesh.vertexPosList) == 6, len(submesh.vertexPosList)
		assert np.allclose(submesh.uvList, [(0, 0), (1, 0), (1, 1), (.25, .25), (.75, .75), (0, 1)])
		assert np.allclose(submesh.normalList[:3], [(0, 0, 1)] * 3, atol=.01), submesh.normalList
		assert np.allclose(submesh.normalList[3:], [(0, 1, 0)] * 3, atol=.01)

		obj.shape_key_add(name="Basis")
		shape = obj.shape_key_add(name="Move")
		shape.data[0].co.z = .2
		shape.value = .7
		dummy = obj.shape_key_add(name="DUMMY_preview")
		dummy.data[1].co.z = 1
		dummy.value = .4
		expected_deltas = [(0, 0, .2), (0, 0, 0), (0, 0, 0),
						   (0, 0, .2), (0, 0, 0), (0, 0, 0)]
		# 1 = Recalculate Normals (normal-recalc tables), -1 = KEEPNORMALS (vanilla no-recalc layout)
		for mode in (1, -1):
			wilds_output = Path(temporary) / ("wilds-mode" + str(mode) + ".mesh.241111606")
			assert mesh_io.exportREMeshFile(str(wilds_output), dict(
				options, exportBlendShapes=True, blendShapeExportMode=mode))
			wilds = codec.readREMesh(str(wilds_output))
			assert bool(wilds.fileHeader.normalRecalcOffset) == (mode == 1), (mode, wilds.fileHeader.normalRecalcOffset)
			wilds_parsed = parse.ParsedREMesh()
			wilds_parsed.ParseREMesh(wilds, {"importBlendShapes": True})
			wilds_submesh = wilds_parsed.mainMeshLODList[0].visconGroupList[0].subMeshList[0]
			assert [key.blendShapeName for key in wilds_submesh.blendShapeList] == ["Move"]
			assert np.allclose(wilds_submesh.blendShapeList[0].deltas, expected_deltas, atol=.001)
			if mode == 1:
				assert len(wilds_submesh.normalGroupList) == 6
			assert abs(shape.value - .7) < 1e-6 and abs(dummy.value - .4) < 1e-6
		print("PASS Wilds modes 1/KEEPNORMALS retain split-vertex shapes and exclude DUMMY_ preview keys", flush=True)

		for mode in (1, -1):
			re4_output = Path(temporary) / ("re4-mode" + str(mode) + ".mesh.221108797")
			assert mesh_io.exportREMeshFile(str(re4_output), dict(
				options, exportBlendShapes=True, blendShapeExportMode=mode))
			re4 = codec.readREMesh(str(re4_output))
			body = re4.blendShapeHeader.blendShapeList[0]
			assert re4.blendShapeHeader.count == 1
			assert (body.targetCount, body.unknFlag, list(body.blendS)) == (1, int(mode == 1), [-1, 0, 0]), (
				mode, body.targetCount, body.unknFlag, list(body.blendS))
			# the key moves the only submesh, so no inactive target (vanilla chd500_01)
			assert body.typing == 0 and list(body.blendSSList) == [-1], body.typing
			active = body.blendTargetList[0]
			assert [(run.subMeshVertexStartIndex, run.vertCount) for run in active.subMeshEntryList] == [(0, 6)]
			header = re4.meshBufferHeader
			start = (header.vertexElementSize & 0xFFFF) | ((header.unkn1 & 0xFFFF) << 16)
			recalc = re4.fileHeader.normalRecalcOffset
			if mode == 1:
				# float16 rows (dx, dy, dz, 0) right after the vertex elements
				rows = np.frombuffer(bytes(header.vertexBuffer[start:start + 6 * 8]), "<f2").reshape(6, 4)
				assert np.allclose(rows[:, :3], expected_deltas, atol=.001) and not rows[:, 3].any()
				# LOD0 canonical tables (6 vertices, 6 indices, 16-byte padded) fill the
				# section up to the blend header
				count, = np.frombuffer(re4_output.read_bytes()[recalc:recalc + 8], "<u8")
				assert count == 1 and recalc + 48 + 32 + 32 == re4.fileHeader.blendShapesOffset
			else:
				# no-recalc layout of vanilla chd000_00: no tables, rows of
				# [packed 11/10/11 delta, int8 normal]; the normal of an unmoved
				# quad is non-zero
				assert recalc == 0, recalc
				rows = np.frombuffer(bytes(header.vertexBuffer[start:start + 6 * 8]), "<u4").reshape(6, 2)
				assert rows[:, 1].all(), rows
			re4_parsed = parse.ParsedREMesh()
			re4_parsed.ParseREMesh(re4, {"importBlendShapes": True})
			re4_submesh = re4_parsed.mainMeshLODList[0].visconGroupList[0].subMeshList[0]
			assert [key.blendShapeName for key in re4_submesh.blendShapeList] == ["Move"]
			assert np.allclose(re4_submesh.blendShapeList[0].deltas, expected_deltas, atol=.001), (
				mode, re4_submesh.blendShapeList[0].deltas)
		print("PASS RE4 shape keys export in modes 1 (float16 rows + LOD0 tables)/KEEPNORMALS (no-recalc rows) and reimport", flush=True)

		# Onimusha WotS: Wilds writer with the 16-byte later mesh-header fields
		for mode in (1, -1):
			oni_output = Path(temporary) / ("oniwots-mode" + str(mode) + ".mesh.260209350")
			assert mesh_io.exportREMeshFile(str(oni_output), dict(
				options, exportBlendShapes=True, blendShapeExportMode=mode))
			oni = codec.readREMesh(str(oni_output))
			oni_bytes = oni_output.read_bytes()
			header = oni.meshBufferHeader
			body = oni.blendShapeHeader.blendShapeList[0]
			assert (list(body.blendS), list(body.blendSSList), body.padding1) == ([-1, 0, 0], [-1], 0)
			boundary0 = (header.vertexElementSize & 0xFFFF) | ((header.unkn1 & 0xFFFF) << 16)
			if mode == 1:
				recalc = oni.fileHeader.normalRecalcOffset
				assert recalc + 16 == oni.fileHeader.blendShapesOffset
				assert np.frombuffer(oni_bytes[recalc:recalc + 4], "<u4")[0] == 1
			else:
				# no tables: both table boundaries point at file offset 0
				null = (-header.vertexBufferOffset) & 0xFFFFFFFF
				assert oni.fileHeader.normalRecalcOffset == 0
				assert boundary0 == null == header.sunbreakSecondUnknown & 0xFFFFFFFF
			oni_parsed = parse.ParsedREMesh()
			oni_parsed.ParseREMesh(oni, {"importBlendShapes": True})
			oni_submesh = oni_parsed.mainMeshLODList[0].visconGroupList[0].subMeshList[0]
			assert [key.blendShapeName for key in oni_submesh.blendShapeList] == ["Move"]
			assert np.allclose(oni_submesh.blendShapeList[0].deltas, expected_deltas, atol=.001)
		print("PASS Onimusha WotS modes 1/KEEPNORMALS export and reimport shape keys", flush=True)

		# RE9: Wilds writer with the shifted header and run words
		for mode in (1, -1):
			re9_output = Path(temporary) / ("re9-mode" + str(mode) + ".mesh.250925211")
			assert mesh_io.exportREMeshFile(str(re9_output), dict(
				options, exportBlendShapes=True, blendShapeExportMode=mode))
			re9 = codec.readREMesh(str(re9_output))
			header = re9.meshBufferHeader
			recalc = re9.fileHeader.normalRecalcOffset
			if mode == 1:
				assert recalc and recalc + 16 == re9.fileHeader.blendShapesOffset
				assert np.frombuffer(re9_output.read_bytes()[recalc:recalc + 4], "<u4")[0] == 1
			else:
				# no tables: every boundary is the payload start, as in vanilla
				# RE9 table-less buffers
				boundary0 = (header.vertexElementSize & 0xFFFF) | ((header.unkn1 & 0xFFFF) << 16)
				assert recalc == 0
				assert boundary0 == header.sunbreakSecondUnknown & 0xFFFFFFFF == header.sunbreakSecondUnknown >> 32
			body = re9.blendShapeHeader.blendShapeList[0]
			assert (list(body.blendS), list(body.blendSSList)) == ([0, 0, 0], [0])
			assert all(
				entry.paramUnkn3 == 0 for target in body.blendTargetList
				for entry in target.subMeshEntryList
			)
			re9_parsed = parse.ParsedREMesh()
			re9_parsed.ParseREMesh(re9, {"importBlendShapes": True})
			re9_submesh = re9_parsed.mainMeshLODList[0].visconGroupList[0].subMeshList[0]
			assert [key.blendShapeName for key in re9_submesh.blendShapeList] == ["Move"]
			assert np.allclose(re9_submesh.blendShapeList[0].deltas, expected_deltas, atol=.001)
		print("PASS RE9 modes 1/KEEPNORMALS export and reimport shape keys", flush=True)

		# MH Rise: pre-SF6 target over the whole submesh, every channel kept
		# (an empty one too), packed rows (+ normal words without recalculation)
		still = obj.shape_key_add(name="Still", from_mix=False)
		for mode in (1, -1):
			rise_output = Path(temporary) / ("rise-mode" + str(mode) + ".mesh.2109148288")
			assert mesh_io.exportREMeshFile(str(rise_output), dict(
				options, exportBlendShapes=True, blendShapeExportMode=mode))
			rise = codec.readREMesh(str(rise_output))
			body = rise.blendShapeHeader.blendShapeList[0]
			target = body.blendTargetList[0]
			assert (body.targetCount, body.typing, list(body.blendS), list(body.blendSSList)) == (1, 0, [-1, 0, 0], [-1, -1])
			assert (target.subMeshVertexStartIndex, target.vertCount, target.blendShapeNum) == (0, 6, 2)
			header = rise.meshBufferHeader
			start = (header.vertexElementSize & 0xFFFF) | ((header.unkn1 & 0xFFFF) << 16)
			row_words = 1 if mode == 1 else 2
			assert len(header.vertexBuffer) - start >= 2 * 6 * 4 * row_words
			words = np.frombuffer(bytes(header.vertexBuffer[start:start + 2 * 6 * 4 * row_words]), "<u4").reshape(2, 6, row_words)
			assert (words[1, :, 0] == 0x7FEFFBFF).all()
			if mode == 1:
				recalc = rise.fileHeader.normalRecalcOffset
				assert recalc + 48 + 32 + 32 == rise.fileHeader.blendShapesOffset
			else:
				assert rise.fileHeader.normalRecalcOffset == 0 and words[0, :, 1].any()
			rise_parsed = parse.ParsedREMesh()
			rise_parsed.ParseREMesh(rise, {"importBlendShapes": True})
			rise_submesh = rise_parsed.mainMeshLODList[0].visconGroupList[0].subMeshList[0]
			assert [key.blendShapeName for key in rise_submesh.blendShapeList] == ["Move", "Still"]
			assert np.allclose(rise_submesh.blendShapeList[0].deltas, expected_deltas, atol=.001)
		obj.shape_key_remove(still)
		print("PASS MH Rise modes 1/KEEPNORMALS export whole-submesh targets, keep empty channels and reimport", flush=True)
	assert [tuple(vertex.co) for vertex in data.vertices] == before
	assert len(data.vertices) == 4 and len(data.polygons) == 2
	print("PASS corner export retains UV and custom normal seams without modifying source mesh", flush=True)

	# Blender caps shape key names at 63 bytes; import keeps the full name and
	# export restores it (Onimusha faces ship 90-byte channel names).
	long_collection = bpy.data.collections.new("LongShapeKeyNames")
	bpy.context.scene.collection.children.link(long_collection)
	long_names = ["blendShape1503.jawOpen_lipCornerDepressor_lipCornerPuller_lipStretcher_" + side for side in "LR"]
	shapes = []
	for index, name in enumerate(long_names):
		shape = parse.BlendShape()
		shape.blendShapeName = name
		shape.deltas = [(0, 0, .1 * (index + 1)), (0, 0, 0), (0, 0, 0)]
		shapes.append(shape)
	long_obj = mesh_io.importMesh(
		"LOD_0_Group_0_Sub_0__LongNameMat", vertexList=vertices, faceList=faces,
		vertexNormalList=[(0, 0, 1)] * 3, material=None, collection=long_collection,
		rotate90=False, blendShapeList=shapes, importBlendShapes=True)
	long_obj.name = "LOD_0_Group_0_Sub_0__LongNameMat"
	long_obj.data.uv_layers.new(name="UVMap")
	long_obj.data.materials.append(bpy.data.materials.new("LongNameMat"))
	blender_names = [key.name for key in long_obj.data.shape_keys.key_blocks[1:]]
	assert all(len(name.encode()) <= 63 for name in blender_names) and blender_names[0] != blender_names[1]
	with tempfile.TemporaryDirectory(prefix="meshfix-longnames-") as temporary:
		long_output = Path(temporary) / "long-names.mesh.260209350"
		assert mesh_io.exportREMeshFile(str(long_output), dict(
			options, targetCollection=long_collection.name, exportBlendShapes=True,
			blendShapeExportMode=1))
		reread = codec.readREMesh(str(long_output))
		assert [reread.rawNameList[i] for i in reread.blendShapeNameRemapList] == long_names
	print("PASS shape key names longer than 63 bytes survive import and export", flush=True)

	# Blender caps bone and vertex group names at 63 bytes, not characters: a
	# CJK name reaches the limit at 22 characters and must be hashed on import
	# and restored on export.
	cjk_collection = bpy.data.collections.new("LongChineseBoneNames")
	bpy.context.scene.collection.children.link(cjk_collection)
	root_name = "根" * 21  # 63 bytes, still fits
	long_name = "左手食指第一关节辅助骨骼左手食指第一关节辅助骨骼"  # 24 characters, 72 bytes
	skeleton = parse.Skeleton()
	for index, (name, parent_index) in enumerate([(root_name, -1), (long_name, 0)]):
		bone = parse.ParsedBone()
		bone.boneName, bone.boneIndex, bone.parentIndex = name, index, parent_index
		bone.symmetryBoneIndex, bone.nextSiblingIndex, bone.nextChildIndex = index, -1, -1
		identity = [[float(row == column) for column in range(4)] for row in range(4)]
		bone.worldMatrix.matrix, bone.localMatrix.matrix, bone.inverseMatrix.matrix = identity, identity, identity
		skeleton.boneList.append(bone)
	cjk_armature = mesh_io.importSkeleton(skeleton, "CJKSkeleton", cjk_collection, False, "")
	hashed_name = "#HASHED_" + str(mesh_io.hashUTF8(long_name))
	assert root_name in cjk_armature.data.bones and hashed_name in cjk_armature.data.bones, list(cjk_armature.data.bones.keys())
	assert cjk_armature.data.bones[hashed_name].parent.name == root_name
	cjk_obj = mesh_io.importMesh(
		"LOD_0_Group_0_Sub_0__CJKMat", vertexList=vertices, faceList=faces,
		UV0List=[(0, 0), (1, 0), (0, 1)], boneNameList=[root_name, long_name],
		vertexGroupWeightList=[[.6, .4, 0, 0, 0, 0, 0, 0]] * 3,
		vertexGroupBoneIndicesList=indices,
		material=bpy.data.materials.new("CJKMat"), armature=cjk_armature,
		collection=cjk_collection, rotate90=False)
	assert {group.name for group in cjk_obj.vertex_groups} == {root_name, hashed_name}
	with tempfile.TemporaryDirectory(prefix="meshfix-cjkbones-") as temporary:
		cjk_output = Path(temporary) / "cjk-bones.mesh.221108797"
		assert mesh_io.exportREMeshFile(str(cjk_output), dict(
			options, targetCollection=cjk_collection.name))
		parsed = parse.ParsedREMesh()
		parsed.ParseREMesh(codec.readREMesh(str(cjk_output)))
		assert [bone.boneName for bone in parsed.skeleton.boneList] == [root_name, long_name]
		submesh = parsed.mainMeshLODList[0].visconGroupList[0].subMeshList[0]
		assert np.allclose(np.asarray(submesh.weightList)[:, :2], [[.6, .4]] * 3, atol=.004), submesh.weightList
	print("PASS Chinese bone names longer than 63 bytes are hashed on import and restored on export", flush=True)

	dd2_collection = bpy.data.collections.new("DD2WeightExportChecks")
	bpy.context.scene.collection.children.link(dd2_collection)
	armature_data = bpy.data.armatures.new("DD2CheckSkeleton")
	armature = bpy.data.objects.new("DD2CheckSkeleton", armature_data)
	dd2_collection.objects.link(armature)
	bpy.context.view_layer.objects.active = armature
	armature.select_set(True)
	bpy.ops.object.mode_set(mode="EDIT")
	parent = armature_data.edit_bones.new("primary")
	parent.head, parent.tail = (0, 0, 0), (0, 0, 1)
	child = armature_data.edit_bones.new("secondary")
	child.head, child.tail, child.parent = (0, 0, 1), (0, 0, 2), parent
	bpy.ops.object.mode_set(mode="OBJECT")
	dd2_obj = mesh_io.importMesh(
		"LOD_0_Group_0_Sub_0__MeshFixMaterial", vertexList=vertices, faceList=faces,
		UV0List=[(0, 0), (1, 0), (0, 1)], boneNameList=["primary", "secondary"],
		vertexGroupWeightList=[[.8, .2, 0, 0, 0, 0, 0, 0]] * 3,
		vertexGroupBoneIndicesList=indices,
		vertexGroupWeightListSecondary=[[.3, .7, 0, 0, 0, 0, 0, 0]] * 3,
		vertexGroupBoneIndicesListSecondary=indices,
		material=material, armature=armature, collection=dd2_collection,
		rotate90=False)
	with tempfile.TemporaryDirectory(prefix="meshfix-dd2-") as temporary:
		output = Path(temporary) / "dd2.mesh.260421070"
		assert mesh_io.exportREMeshFile(str(output), dict(
			options, targetCollection=dd2_collection.name))
		dd2 = codec.readREMesh(str(output))
		assert dd2.fileHeader.version == 251205828
		assert dd2.meshBufferHeader.shapeKeyWeightBufferSize == 3 * 16
		parsed = parse.ParsedREMesh()
		parsed.ParseREMesh(dd2)
		assert parsed.bufferHasSecondaryWeight
		submesh = parsed.mainMeshLODList[0].visconGroupList[0].subMeshList[0]
		assert np.allclose(np.asarray(submesh.weightList)[:, :2], [[.8, .2]] * 3, atol=.004)
		assert np.allclose(np.asarray(submesh.secondaryWeightList)[:, :2], [[.3, .7]] * 3, atol=.004)
		assert len(dd2_obj.data.vertices) == 3
	print("PASS current DD2 header exports and reparses independent eight-slot weight banks", flush=True)

	# Dominant paint/modifier masks must not consume skeletal influence slots.
	# Limit only the evaluated export copy; keep the artist's mask data intact.
	for name in ("PreviewMask", "SHAPEKEY_PreviewMask"):
		group = dd2_obj.vertex_groups.new(name=name)
		group.add(range(3), 1.0, "REPLACE")

	def memberships(obj):
		return [[(obj.vertex_groups[g.group].name, g.weight) for g in vertex.groups]
				for vertex in obj.data.vertices]

	original_memberships = memberships(dd2_obj)
	with tempfile.TemporaryDirectory(prefix="meshfix-masks-") as temporary:
		output = Path(temporary) / "limited-dd2.mesh.260421070"
		assert mesh_io.exportREMeshFile(str(output), dict(
			options, targetCollection=dd2_collection.name, limitTotal=True,
			limitTotalCount=2))
		parsed = parse.ParsedREMesh()
		parsed.ParseREMesh(codec.readREMesh(str(output)))
		submesh = parsed.mainMeshLODList[0].visconGroupList[0].subMeshList[0]
		assert np.allclose(np.asarray(submesh.weightList)[:, :2], [[.8, .2]] * 3, atol=.004), submesh.weightList
		assert np.allclose(np.asarray(submesh.secondaryWeightList)[:, :2], [[.3, .7]] * 3, atol=.004), submesh.secondaryWeightList
		assert np.array_equal(np.asarray(submesh.weightIndicesList)[:, :2], [[0, 1]] * 3)
		assert np.array_equal(np.asarray(submesh.secondaryWeightIndicesList)[:, :2], [[0, 1]] * 3)
		assert memberships(dd2_obj) == original_memberships

		normal_collection = bpy.data.collections.new("OrdinaryMaskedWeights")
		bpy.context.scene.collection.children.link(normal_collection)
		normal_collection.objects.link(armature)
		normal_obj = dd2_obj.copy()
		normal_obj.data = dd2_obj.data.copy()
		normal_collection.objects.link(normal_obj)
		for group in list(normal_obj.vertex_groups):
			if group.name.startswith("SHAPEKEY_"):
				normal_obj.vertex_groups.remove(group)
		normal_memberships = memberships(normal_obj)
		output = Path(temporary) / "limited-re4.mesh.221108797"
		assert mesh_io.exportREMeshFile(str(output), dict(
			options, targetCollection=normal_collection.name, limitTotal=True,
			limitTotalCount=2))
		parsed = parse.ParsedREMesh()
		parsed.ParseREMesh(codec.readREMesh(str(output)))
		submesh = parsed.mainMeshLODList[0].visconGroupList[0].subMeshList[0]
		assert np.allclose(np.asarray(submesh.weightList)[:, :2], [[.8, .2]] * 3, atol=.004), submesh.weightList
		assert np.array_equal(np.asarray(submesh.weightIndicesList)[:, :2], [[0, 1]] * 3)
		assert memberships(normal_obj) == normal_memberships
	print("PASS export Limit Total ignores non-bone masks and leaves source memberships intact", flush=True)


if __name__ == "__main__":
	main()
