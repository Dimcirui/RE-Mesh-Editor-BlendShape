"""Blender background checks for imported keep-normals rows (second rows).

Run with:
"<path to>/blender.exe" --background --factory-startup --python-exit-code 1 --python tests/test_imported_key_normals_blender.py

A synthetic sphere is exported as MH Wilds with Keep Normals; the second rows
of one channel are then overwritten in the file with a marker normal, so a
re-export can only reproduce them by reading them on import. Everything is
written to a temporary directory that is removed afterwards.
"""
import importlib
import io
import contextlib
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import traceback

import addon_utils
import bmesh
import bpy
import numpy as np
from mathutils import Vector

REPO = Path(__file__).resolve().parents[1]
MODULE = REPO.name

# int8 (0, 0, 127): a normal no key of the sphere produces.
MARKER_WORD = 127 << 16
# int8 (127, 0, 0) for the second channel.
MARKER2_WORD = 127

results = []


def check(name, condition, detail=""):
	results.append((name, bool(condition), detail))
	print(("PASS " if condition else "FAIL ") + name + ((" :: " + str(detail)) if detail else ""), flush=True)


def build_sphere(name):
	"""Armature + one smooth UV sphere with keys squash (top) and bulge (+x)."""
	collection = bpy.data.collections.new(name + ".mesh")
	bpy.context.scene.collection.children.link(collection)
	armData = bpy.data.armatures.new(name + " Armature")
	arm = bpy.data.objects.new(name + " Armature", armData)
	collection.objects.link(arm)
	bpy.context.view_layer.objects.active = arm
	bpy.ops.object.mode_set(mode="EDIT")
	bone = armData.edit_bones.new("Hip")
	bone.head, bone.tail = (0, 0, 0), (0, 0, 0.1)
	bpy.ops.object.mode_set(mode="OBJECT")

	me = bpy.data.meshes.new(name)
	bm = bmesh.new()
	bm.loops.layers.uv.new()
	bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=0.1, calc_uvs=True)
	bm.to_mesh(me)
	bm.free()
	for polygon in me.polygons:
		polygon.use_smooth = True
	obj = bpy.data.objects.new("Group_0_Sub_0__" + name, me)
	collection.objects.link(obj)
	obj.parent = arm
	group = obj.vertex_groups.new(name="Hip")
	group.add(list(range(len(me.vertices))), 1.0, "REPLACE")
	obj.modifiers.new("Armature", "ARMATURE").object = arm

	obj.shape_key_add(name="Basis")
	def add_key(keyName, move):
		key = obj.shape_key_add(name=keyName)
		for i, vertex in enumerate(me.vertices):
			key.data[i].co = move(vertex.co.copy())
	add_key("squash", lambda co: Vector((co.x * 1.4, co.y * 1.4, 0.02 + (co.z - 0.02) * 0.15)) if co.z > 0.02 else co)
	add_key("bulge", lambda co: Vector((co.x * 1.6, co.y, co.z)) if co.x > 0.03 else co)
	return collection


def export(brm, collection, path):
	options = {"targetCollection": collection.name, "selectedOnly": False, "exportAllLODs": False,
		"exportBlendShapes": True, "blendShapeExportMode": -1, "rotate90": True,
		"useBlenderMaterialName": False, "preserveBoneMatrices": False, "exportBoundingBoxes": False,
		"autoSolveRepeatedUVs": False, "preserveSharpEdges": False, "splitLoopVertices": True,
		"limitTotal": False, "limitTotalCount": 6, "normalizeWeights": False,
		"shapeKeyNormalTurn": "SURFACE"}
	return brm.exportREMeshFile(str(path), options)


def second_rows(frm, path):
	"""{channel: {vertex: (file offset, second-row word)}} of a keep-normals export."""
	with contextlib.redirect_stdout(io.StringIO()):
		mesh = frm.readREMesh(str(path))
	header = mesh.meshBufferHeader
	vb = bytes(header.vertexBuffer)
	start = (int(header.sunbreakSecondUnknown) >> 32) & 0xFFFFFFFF
	data = mesh.blendShapeHeader.blendShapeList[0]
	channels = {}
	for target in data.blendTargetList[:data.targetCount]:
		rowCount = sum(s.vertCount for s in target.subMeshEntryList)
		for ch in range(target.blendShapeNum):
			name = mesh.rawNameList[mesh.blendShapeNameRemapList[int(target.blendSSIndex) + ch]]
			rows = channels.setdefault(name, {})
			for s in target.subMeshEntryList:
				r0 = s.vertOffset + ch * rowCount
				for i in range(s.vertCount):
					offset = start + 8 * (r0 + i) + 4
					rows[s.subMeshVertexStartIndex + i] = (offset, struct.unpack_from("<I", vb, offset)[0])
	return channels, int(header.vertexBufferOffset) if hasattr(header, "vertexBufferOffset") else None


def vertex_buffer_file_offset(path, frm):
	"""File offset of the vertex buffer: find its bytes in the file."""
	with contextlib.redirect_stdout(io.StringIO()):
		mesh = frm.readREMesh(str(path))
	vb = bytes(mesh.meshBufferHeader.vertexBuffer)
	data = Path(path).read_bytes()
	index = data.find(vb[:256])
	return index


def import_mesh(path):
	for obj in list(bpy.data.objects):
		bpy.data.objects.remove(obj)
	for collection in list(bpy.data.collections):
		bpy.data.collections.remove(collection)
	with contextlib.redirect_stdout(io.StringIO()):
		result = bpy.ops.re_mesh.importfile(filepath=str(path), directory=str(Path(path).parent),
			files=[{"name": Path(path).name}], clearScene=False, loadMaterials=False,
			loadMDFData=False, loadShellFur=False, importBlendShapes=True)
	collection = next((c for c in bpy.data.collections if c.name.endswith(".mesh")), None)
	objects = [o for o in collection.all_objects if o.type == "MESH" and o.data.shape_keys is not None] if collection else []
	return result, (objects[0] if objects else None), collection


def main(scratch):
	addon_utils.enable(MODULE, default_set=True)
	brm = importlib.import_module(MODULE + ".modules.mesh.blender_re_mesh")
	frm = importlib.import_module(MODULE + ".modules.mesh.file_re_mesh")
	ops = importlib.import_module(MODULE + ".modules.mesh.re_mesh_operators")

	# A: plain keep-normals export
	collection = build_sphere("knorm")
	pathA = Path(scratch) / "knorm.mesh.241111606"
	check("export A", export(brm, collection, pathA) is True)
	rowsA, _ = second_rows(frm, pathA)
	check("A has squash and bulge rows", {"squash", "bulge"} <= set(rowsA), sorted(rowsA))

	# B: A with every squash second row replaced by the marker normal
	vbOffset = vertex_buffer_file_offset(pathA, frm)
	check("vertex buffer located in file", vbOffset > 0, vbOffset)
	data = bytearray(pathA.read_bytes())
	for offset, _word in rowsA["squash"].values():
		struct.pack_into("<I", data, vbOffset + offset, MARKER_WORD)
	for offset, _word in rowsA["bulge"].values():
		struct.pack_into("<I", data, vbOffset + offset, MARKER2_WORD)
	pathB = Path(scratch) / "knorm_marked.mesh.241111606"
	pathB.write_bytes(bytes(data))
	rowsB, _ = second_rows(frm, pathB)
	check("B carries the marker rows", all(word == MARKER_WORD for _o, word in rowsB["squash"].values())
		and all(word == MARKER2_WORD for _o, word in rowsB["bulge"].values()))

	# Import B: rows stored per key
	result, obj, collection = import_mesh(pathB)
	check("import B", result == {"FINISHED"} and obj is not None, result)
	keys = obj.data.shape_keys
	stored = keys.get(brm.IMPORTED_KEY_NORMALS_PROPERTY)
	check("imported rows stored for both keys", stored is not None and {"squash", "bulge"} <= set(stored.keys()),
		None if stored is None else sorted(stored.keys()))
	squashWords = brm.importedKeyNormalWords(obj.data, keys.key_blocks["squash"])
	check("unedited key returns its rows", squashWords is not None)
	check("stored squash rows are the marker", squashWords is not None and set(squashWords[squashWords != 0].tolist()) == {MARKER_WORD})

	# C: unedited re-export writes the imported rows back
	pathC = Path(scratch) / "knorm_reexport.mesh.241111606"
	check("export C", export(brm, collection, pathC) is True)
	rowsC, _ = second_rows(frm, pathC)
	squashC = [word for _o, word in rowsC.get("squash", {}).values()]
	check("C: squash rows are the imported marker", squashC and all(word == MARKER_WORD for word in squashC),
		f"{sum(word == MARKER_WORD for word in squashC)}/{len(squashC)}")
	bulgeB = sorted(word for _o, word in rowsB["bulge"].values())
	bulgeC = sorted(word for _o, word in rowsC.get("bulge", {}).values())
	check("C: bulge rows are the imported marker", bulgeC and bulgeB == bulgeC, (len(bulgeB), len(bulgeC)))

	# Rename keeps the rows (msgbus does not fire in background mode; call its handler)
	ops.snapshotShapeKeyNames()
	keys.key_blocks["squash"].name = "squash_renamed"
	ops.migrateRenamedStaticNormals()
	check("rename moves the stored rows", "squash_renamed" in keys[brm.IMPORTED_KEY_NORMALS_PROPERTY]
		and brm.importedKeyNormalWords(obj.data, keys.key_blocks["squash_renamed"]) is not None)
	keys.key_blocks["squash_renamed"].name = "squash"
	ops.migrateRenamedStaticNormals()

	# Static Normals wins over imported rows
	brm.setStaticNormals(obj.data, "squash", True)
	pathS = Path(scratch) / "knorm_static.mesh.241111606"
	check("export with Static Normals", export(brm, collection, pathS) is True)
	rowsS, _ = second_rows(frm, pathS)
	check("Static key does not write the marker", rowsS.get("squash") and not any(word == MARKER_WORD for _o, word in rowsS["squash"].values()))
	brm.setStaticNormals(obj.data, "squash", False)

	# D: editing the key falls back to computed rows; the other key keeps its rows
	squashKey = keys.key_blocks["squash"]
	top = max(range(len(squashKey.data)), key=lambda i: squashKey.data[i].co.z)
	squashKey.data[top].co.z += 0.005
	check("edited key returns no rows", brm.importedKeyNormalWords(obj.data, squashKey) is None)
	pathD = Path(scratch) / "knorm_edited.mesh.241111606"
	check("export D", export(brm, collection, pathD) is True)
	rowsD, _ = second_rows(frm, pathD)
	check("D: edited key rows are computed, not the marker", rowsD.get("squash") and not any(word == MARKER_WORD for _o, word in rowsD["squash"].values()))
	bulgeD = sorted(word for _o, word in rowsD.get("bulge", {}).values())
	check("D: unedited bulge rows still the imported marker", bulgeD and bulgeD == bulgeB, (len(bulgeB), len(bulgeD)))

	# Editing the basis invalidates every key
	keys.reference_key.data[top].co.z += 0.001
	check("basis edit invalidates the other key", brm.importedKeyNormalWords(obj.data, keys.key_blocks["bulge"]) is None)


if __name__ == "__main__":
	scratch = tempfile.mkdtemp(prefix="reme_imported_key_normals_")
	try:
		main(scratch)
	except Exception:
		traceback.print_exc()
		results.append(("exception", False, ""))
	finally:
		shutil.rmtree(scratch, ignore_errors=True)
	failed = [r for r in results if not r[1]]
	print(f"{len(results) - len(failed)}/{len(results)} passed", flush=True)
	sys.exit(1 if failed else 0)
