"""Blender background checks for Static Normals (Shape Keys panel).

Run with:
"<path to>/blender.exe" --background --factory-startup --python-exit-code 1 --python tests/test_static_normals_blender.py

Synthetic spheres only (no retail game files), exported as MH Wilds with Keep
Normals into a temporary directory that is removed afterwards.
"""
import importlib
import io
import contextlib
from math import radians
import os
from pathlib import Path
import shutil
import sys
import tempfile
import traceback

import addon_utils
import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

REPO = Path(__file__).resolve().parents[1]
MODULE = REPO.name

results = []


def check(name, condition, detail=""):
	results.append((name, bool(condition), detail))
	print(("PASS " if condition else "FAIL ") + name + ((" :: " + str(detail)) if detail else ""), flush=True)


def unit(v):
	return v / (np.linalg.norm(v, axis=-1, keepdims=True) + 1e-12)


def build_sphere(name, stylised):
	"""Armature + one smooth UV sphere with keys: squash and squash_static
	(exported, same deltas), lockA (locked bulge along x), lockS (locked bulge
	along y, Static Normals) and muted / DUMMY_ keys."""
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
		return key
	squash = lambda co: Vector((co.x * 1.4, co.y * 1.4, 0.02 + (co.z - 0.02) * 0.15)) if co.z > 0.02 else co
	add_key("squash", squash)
	add_key("squash_static", squash)
	add_key("lockA", lambda co: Vector((co.x * 1.6, co.y, co.z)) if co.x > 0.03 else co)
	add_key("lockS", lambda co: Vector((co.x, co.y * 1.6, co.z)) if co.y > 0.03 else co)
	add_key("muted", lambda co: co * 1.1).mute = True
	add_key("DUMMY_preview", lambda co: co * 1.1)
	for keyName in ("lockA", "lockS"):
		key = me.shape_keys.key_blocks[keyName]
		key.value = 1.0
		key.lock_shape = True

	vertexNormals = np.array([tuple(v.normal) for v in me.vertices])
	if stylised:
		custom = unit(vertexNormals * 0.5 + np.array([0.0, 0.6, 0.8]))
	else:
		custom = vertexNormals
	me.normals_split_custom_set_from_vertices([tuple(n) for n in custom])
	return collection, obj, custom


def key_positions(obj, values):
	"""Vertex positions with the given key values (others 0), no modifiers."""
	keyBlocks = obj.data.shape_keys.key_blocks
	basis = np.array([tuple(p.co) for p in keyBlocks[0].data])
	pos = basis.copy()
	for keyName, value in values.items():
		pos += value * (np.array([tuple(p.co) for p in keyBlocks[keyName].data]) - basis)
	return pos


def vertex_normals_at(obj, pos):
	"""Smooth geometric vertex normals of obj's topology at positions pos."""
	me = obj.data.copy()
	try:
		me.vertices.foreach_set("co", pos.astype(np.float32).ravel())
		me.update()
		n = np.empty(len(me.vertices) * 3, np.float32)
		me.vertex_normals.foreach_get("vector", n)
		return n.reshape(-1, 3).astype(np.float64)
	finally:
		bpy.data.meshes.remove(me)


def rotate(v, a, b):
	c = (a * b).sum(1)
	w = np.cross(a, b)
	out = v * c[:, None] + np.cross(w, v) + w * ((w * v).sum(1) / np.maximum(1 + c, 1e-9))[:, None]
	return unit(out)


def read_export(frm, path):
	"""(positions, base normals, {channel: {row: second-row int8}}) of a keep-normals export."""
	with contextlib.redirect_stdout(io.StringIO()):
		mesh = frm.readREMesh(str(path))
	header = mesh.meshBufferHeader
	vb = bytes(header.vertexBuffer)
	elements = {int(e.typing): e for e in header.vertexElementList}
	V = sum(g.vertexCount for g in mesh.lodHeader.lodGroupList[0].meshGroupList)
	P = np.frombuffer(vb[elements[0].posStartOffset:elements[0].posStartOffset + 12 * V], np.float32).reshape(V, 3).astype(np.float64)
	N = np.frombuffer(vb[elements[1].posStartOffset:elements[1].posStartOffset + V * int(elements[1].stride)], np.int8).reshape(V, -1)[:, :3].astype(np.float64)
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
				raw = np.frombuffer(vb[start + 8 * r0:start + 8 * (r0 + s.vertCount)], np.int8).reshape(-1, 8)
				for i in range(s.vertCount):
					rows[s.subMeshVertexStartIndex + i] = raw[i, 4:7].astype(np.float64)
	return P, N, channels


def export(brm, collection, path, surface=False):
	options = {"targetCollection": collection.name, "selectedOnly": False, "exportAllLODs": False,
		"exportBlendShapes": True, "blendShapeExportMode": -1, "rotate90": True,
		"useBlenderMaterialName": False, "preserveBoneMatrices": False, "exportBoundingBoxes": False,
		"autoSolveRepeatedUVs": False, "preserveSharpEdges": False, "splitLoopVertices": True,
		"limitTotal": False, "limitTotalCount": 6, "normalizeWeights": False,
		"shapeKeyNormalTurn": "SURFACE" if surface else "BLENDER"}
	return brm.exportREMeshFile(str(path), options)


def rows_to_vertices(P, positions):
	"""Blender vertex index of each exported row (export space = rotate -90 X)."""
	rotated = positions @ np.array(Matrix.Rotation(radians(-90.0), 3, "X")).T
	return np.array([int(np.argmin(np.linalg.norm(rotated - p, axis=1))) for p in P])


def main(scratch):
	addon_utils.enable(MODULE, default_set=True)
	brm = importlib.import_module(MODULE + ".modules.mesh.blender_re_mesh")
	frm = importlib.import_module(MODULE + ".modules.mesh.file_re_mesh")
	ops = importlib.import_module(MODULE + ".modules.mesh.re_mesh_operators")
	R = np.array(Matrix.Rotation(radians(-90.0), 3, "X"))

	# Operators and storage
	collection, obj, custom = build_sphere("static_ops", stylised=True)
	bpy.context.view_layer.objects.active = obj
	keys = obj.data.shape_keys
	obj.active_shape_key_index = list(keys.key_blocks).index(keys.key_blocks["squash_static"])
	check("toggle on", bpy.ops.re_mesh.toggle_static_normals() == {"FINISHED"} and brm.hasStaticNormals(obj.data, keys.key_blocks["squash_static"]))
	bpy.ops.re_mesh.toggle_static_normals()
	check("toggle off", not brm.hasStaticNormals(obj.data, keys.key_blocks["squash_static"]))
	obj.active_shape_key_index = 0
	check("toggle polls false on Basis", not bpy.ops.re_mesh.toggle_static_normals.poll())
	bpy.ops.re_mesh.set_static_normals(static=True)
	flagged = set(keys[brm.STATIC_NORMALS_PROPERTY].keys())
	check("All flags exported and locked keys, skips muted / DUMMY_", flagged == {"squash", "squash_static", "lockA", "lockS"}, sorted(flagged))
	bpy.ops.re_mesh.set_static_normals(static=False)
	check("None clears every flag", keys.get(brm.STATIC_NORMALS_PROPERTY) is None)

	# Rename migration (msgbus does not fire in background mode; call its handler)
	brm.setStaticNormals(obj.data, "lockS", True)
	ops.snapshotShapeKeyNames()
	keys.key_blocks["lockS"].name = "lockS_renamed"
	ops.migrateRenamedStaticNormals()
	flagged = set(keys[brm.STATIC_NORMALS_PROPERTY].keys())
	check("rename moves the flag", flagged == {"lockS_renamed"}, sorted(flagged))
	keys.key_blocks["lockS_renamed"].name = "lockS"
	ops.migrateRenamedStaticNormals()
	obj.shape_key_add(name="added_later")
	ops.migrateRenamedStaticNormals()
	flagged = set(keys[brm.STATIC_NORMALS_PROPERTY].keys())
	check("adding a key does not move flags", flagged == {"lockS"}, sorted(flagged))
	obj.shape_key_remove(keys.key_blocks["added_later"])
	bpy.data.collections.remove(collection)

	# Stylised sphere: per-key Static rows and locked baking
	collection, obj, custom = build_sphere("static_face", stylised=True)
	brm.setStaticNormals(obj.data, "squash_static", True)
	brm.setStaticNormals(obj.data, "lockS", True)
	path = Path(scratch) / "static_face.mesh.241111606"
	check("stylised export", export(brm, collection, path) is True)
	P, N, channels = read_export(frm, path)
	exportedPositions = key_positions(obj, {"lockA": 1.0, "lockS": 1.0})
	rowVertex = rows_to_vertices(P, exportedPositions)

	staticRows = channels.get("squash_static", {})
	equal = [np.array_equal(sec, N[row]) for row, sec in staticRows.items()]
	check("Static key rows store the base normal", staticRows and all(equal), f"{sum(equal)}/{len(equal)}")
	turnedRows = channels.get("squash", {})
	differing = sum(not np.array_equal(sec, N[row]) for row, sec in turnedRows.items())
	check("same deltas without Static turn the normals", differing > len(turnedRows) // 4, f"{differing}/{len(turnedRows)}")
	check("same rows stored for both keys", set(staticRows) == set(turnedRows), (len(staticRows), len(turnedRows)))

	basis = key_positions(obj, {})
	turnedOnly = key_positions(obj, {"lockA": 1.0})
	expected = rotate(custom, unit(vertex_normals_at(obj, basis)), unit(vertex_normals_at(obj, turnedOnly))) @ R.T
	cosine = (unit(N) * expected[rowVertex]).sum(1)
	check("locked keys: authored normals turned by the surface, Static lock adds none", cosine.min() > 0.995, f"min cos {cosine.min():.4f}")
	lockSOnly = (basis[rowVertex, 1] > 0.045) & (basis[rowVertex, 0] < 0.0)
	cosAuthored = (unit(N[lockSOnly]) * (custom @ R.T)[rowVertex[lockSOnly]]).sum(1)
	check("rows moved only by the Static lock keep the authored normal", lockSOnly.any() and cosAuthored.min() > 0.995, f"{lockSOnly.sum()} rows, min cos {cosAuthored.min():.4f}")
	lockARegion = basis[rowVertex, 0] > 0.06
	cosLockA = (unit(N[lockARegion]) * (custom @ R.T)[rowVertex[lockARegion]]).sum(1)
	check("rows moved by the plain lock are turned", lockARegion.any() and cosLockA.min() < 0.99, f"min cos {cosLockA.min():.4f}")
	bpy.data.collections.remove(collection)

	# Non-stylised sphere (custom normals = automatic): same result as Blender's own
	collection, obj, custom = build_sphere("plain_body", stylised=False)
	path = Path(scratch) / "plain_body.mesh.241111606"
	check("plain export", export(brm, collection, path) is True)
	P, N, channels = read_export(frm, path)
	baked = key_positions(obj, {"lockA": 1.0, "lockS": 1.0})
	rowVertex = rows_to_vertices(P, baked)
	geometric = unit(vertex_normals_at(obj, baked)) @ R.T
	cosine = (unit(N) * geometric[rowVertex]).sum(1)
	check("non-stylised: baked normals follow the baked shape", cosine.min() > 0.995, f"min cos {cosine.min():.4f}")
	surfacePath = Path(scratch) / "plain_body_surface.mesh.241111606"
	check("plain export, surface turn", export(brm, collection, surfacePath, surface=True) is True)
	_, _, surfaceChannels = read_export(frm, surfacePath)
	same = all(set(channels[n]) == set(surfaceChannels[n]) and all(np.abs(channels[n][r] - surfaceChannels[n][r]).max() <= 1 for r in channels[n]) for n in channels)
	check("non-stylised: surface turn rows equal Keep Normals (as in Blender) within 1 step", same)
	bpy.data.collections.remove(collection)

	# Stylised sphere, surface turn: key rows = authored x geometric turn of the key
	collection, obj, custom = build_sphere("surface_face", stylised=True)
	for keyName in ("lockA", "lockS"):
		key = obj.data.shape_keys.key_blocks[keyName]
		key.lock_shape = False
		key.value = 0.0
	path = Path(scratch) / "surface_face.mesh.241111606"
	check("stylised export, surface turn", export(brm, collection, path, surface=True) is True)
	P, N, channels = read_export(frm, path)
	basis = key_positions(obj, {})
	rowVertex = rows_to_vertices(P, basis)
	expected = rotate(custom, unit(vertex_normals_at(obj, basis)), unit(vertex_normals_at(obj, key_positions(obj, {"squash": 1.0})))) @ R.T
	rows = channels.get("squash", {})
	cos = np.array([(unit(sec) * expected[rowVertex[r]]).sum() for r, sec in rows.items()])
	check("surface turn: key rows are authored normals turned by the surface", len(cos) and cos.min() > 0.99, f"{len(cos)} rows, min cos {cos.min():.4f}")
	bpy.data.collections.remove(collection)


if __name__ == "__main__":
	scratch = tempfile.mkdtemp(prefix="reme_static_normals_")
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
