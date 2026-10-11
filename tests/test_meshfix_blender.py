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
	assert [tuple(vertex.co) for vertex in data.vertices] == before
	assert len(data.vertices) == 4 and len(data.polygons) == 2
	print("PASS corner export retains UV and custom normal seams without modifying source mesh", flush=True)

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
