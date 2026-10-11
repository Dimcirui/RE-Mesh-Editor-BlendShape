"""Blender background checks for export reliability, UV validation, progress
tracking and the original material table option.

Run with:
"<path to>/blender.exe" --background --factory-startup --python-exit-code 1 --python tests/test_export_reliability_blender.py

Uses synthetic meshes only (no retail game files). Everything is written to a
temporary directory that is removed afterwards.
"""
import importlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import traceback

import addon_utils
import bpy

REPO = Path(__file__).resolve().parents[1]
MODULE = REPO.name

results = []


def check(name, condition, detail=""):
	results.append((name, bool(condition), detail))
	print(("PASS " if condition else "FAIL ") + name + ((" :: " + str(detail)) if detail else ""), flush=True)


def raises(function, *args, **kwargs):
	try:
		function(*args, **kwargs)
	except Exception as error:
		return error
	return None


def leftovers():
	return (
		[o.name for o in bpy.data.objects if o.name.startswith("CLN_")],
		[c.name for c in bpy.data.collections if c.name.startswith("clonedMeshes")],
	)


def no_leftovers():
	cln, cm = leftovers()
	return not cln and not cm, (cln, cm)


def orphan_meshes():
	return sorted(m.name for m in bpy.data.meshes if m.users == 0)


def build_scene(name, materials=("Mat",)):
	"""Armature + one quad submesh per material, each in its own viscon group."""
	collection = bpy.data.collections.new(name + ".mesh")
	collection["~TYPE"] = "RE_MESH_COLLECTION"
	bpy.context.scene.collection.children.link(collection)
	lod = bpy.data.collections.new("Main Mesh LOD0 " + name)
	collection.children.link(lod)

	armData = bpy.data.armatures.new(name + " Armature")
	arm = bpy.data.objects.new(name + " Armature", armData)
	collection.objects.link(arm)
	bpy.context.view_layer.objects.active = arm
	arm.select_set(True)
	bpy.ops.object.mode_set(mode="EDIT")
	b0 = armData.edit_bones.new("bone0")
	b0.head, b0.tail = (0, 0, 0), (0, 0, 1)
	b1 = armData.edit_bones.new("bone1")
	b1.head, b1.tail, b1.parent = (0, 0, 1), (0, 0, 2), b0
	bpy.ops.object.mode_set(mode="OBJECT")
	arm.select_set(False)

	objects = []
	for index, materialSuffix in enumerate(materials):
		data = bpy.data.meshes.new(f"{name}_{index}_data")
		offset = index * 2
		data.from_pydata([(offset, 0, 0), (offset + 1, 0, 0), (offset + 1, 1, 0), (offset, 1, 0)], [], [(0, 1, 2), (0, 2, 3)])
		data.update()
		uv = data.uv_layers.new(name="UVMap")
		for loop, co in zip(uv.data, [(0, 0), (1, 0), (1, 1), (0, 0), (1, 1), (0, 1)]):
			loop.uv = co
		material = bpy.data.materials.new(name + materialSuffix)
		data.materials.append(material)
		obj = bpy.data.objects.new(f"LOD_0_Group_{index}_Sub_0__{name}{materialSuffix}", data)
		lod.objects.link(obj)
		obj.parent = arm
		mod = obj.modifiers.new("Armature", "ARMATURE")
		mod.object = arm
		g0 = obj.vertex_groups.new(name="bone0")
		g1 = obj.vertex_groups.new(name="bone1")
		mask = obj.vertex_groups.new(name="PaintMask")
		g0.add([0, 1, 2, 3], 0.7, "REPLACE")
		g1.add([0, 1, 2, 3], 0.3, "REPLACE")
		mask.add([0, 1, 2, 3], 1.0, "REPLACE")
		objects.append(obj)
	return collection, lod, arm, objects[0] if len(objects) == 1 else objects


def select_only(obj):
	bpy.ops.object.select_all(action="DESELECT")
	obj.select_set(True)
	bpy.context.view_layer.objects.active = obj


def main(scratch):
	sys.path.insert(0, str(REPO.parent))
	addon_utils.enable(MODULE, default_set=True, handle_error=lambda e: traceback.print_exc())
	addon = importlib.import_module(MODULE)
	mesh_io = importlib.import_module(MODULE + ".modules.mesh.blender_re_mesh")
	codec = importlib.import_module(MODULE + ".modules.mesh.file_re_mesh")
	parse = importlib.import_module(MODULE + ".modules.mesh.re_mesh_parse")
	progress = importlib.import_module(MODULE + ".modules.mesh.operation_progress")
	materialTable = importlib.import_module(MODULE + ".modules.mesh.material_table")
	preferences = bpy.context.preferences.addons[MODULE].preferences
	preferences.textureCachePath = os.path.join(scratch, "TextureCache")
	preferences.showConsole = True  # Must still be a no-op in background mode
	check("addon enabled", MODULE in bpy.context.preferences.addons)

	def reparse(path, blendShapes=False):
		parsed = parse.ParsedREMesh()
		parsed.ParseREMesh(codec.readREMesh(path), {"importBlendShapes": blendShapes})
		return parsed

	warnings = []
	realRaiseWarning = mesh_io.raiseWarning

	def captureWarning(message):
		warnings.append(message)
		realRaiseWarning(message)
	mesh_io.raiseWarning = captureWarning

	for o in list(bpy.data.objects):
		bpy.data.objects.remove(o, do_unlink=True)

	# ================= Export reliability (resource scope, Limit Total, atomic writes)
	col, lod, arm, obj = build_scene("wilds")
	obj.shape_key_add(name="Basis")
	key = obj.shape_key_add(name="Move")
	key.data[0].co.z = 0.2
	key.value = 0.6
	keyValueBefore = key.value
	select_only(arm)
	orphansBefore = orphan_meshes()
	wildsPath = os.path.join(scratch, "wilds.mesh.241111606")
	options = dict(
		targetCollection=col.name, selectedOnly=False, exportAllLODs=True,
		exportBlendShapes=True, blendShapeExportMode=-1, rotate90=True,
		useBlenderMaterialName=False, preserveBoneMatrices=False, exportBoundingBoxes=False,
		autoSolveRepeatedUVs=True, preserveSharpEdges=True, splitLoopVertices=True,
		limitTotal=True, limitTotalCount=12, normalizeWeights=True)
	masksBefore = [[(obj.vertex_groups[g.group].name, round(g.weight, 4)) for g in v.groups] for v in obj.data.vertices]
	ok = mesh_io.exportREMeshFile(wildsPath, dict(options))
	check("wilds export returns True", ok is True, ok)
	check("wilds file written", os.path.isfile(wildsPath))
	check("no temp files left in out dir", not [f for f in os.listdir(scratch) if f.startswith(".re-mesh-")], os.listdir(scratch))
	check("wilds: no CLN_ objects / clonedMeshes after success", *no_leftovers())
	check("wilds: no new orphan meshes", orphan_meshes() == orphansBefore, (orphansBefore, orphan_meshes()))
	check("wilds: no leftover armature copies", len(bpy.data.armatures) == 1, [a.name for a in bpy.data.armatures])
	check("selection/active restored", bpy.context.view_layer.objects.active == arm and [o.name for o in bpy.context.selected_objects] == [arm.name])
	check("LOD Distance not written to LOD collection", "LOD Distance" not in lod, list(lod.keys()))
	masksAfter = [[(obj.vertex_groups[g.group].name, round(g.weight, 4)) for g in v.groups] for v in obj.data.vertices]
	check("source vertex groups untouched by limit total", masksBefore == masksAfter)
	check("shape key value restored", abs(key.value - keyValueBefore) < 1e-6, (key.value, keyValueBefore))
	parsed = reparse(wildsPath, True)
	sub = parsed.mainMeshLODList[0].visconGroupList[0].subMeshList[0]
	check("wilds reparse: blend shape present", [b.blendShapeName for b in sub.blendShapeList] == ["Move"], [b.blendShapeName for b in sub.blendShapeList])
	weights = [[round(w, 2) for w in row[:3]] for row in sub.weightList]
	check("wilds reparse: PaintMask did not occupy a weight slot", all(w[:2] == [0.7, 0.3] and w[2] == 0 for w in weights), weights)
	check("wilds reparse: weighted bones only real bones", list(parsed.skeleton.weightedBones) == ["bone0", "bone1"], parsed.skeleton.weightedBones)
	check("progress stack empty after export", progress._stack == [], progress._stack)

	# DD2 SHAPEKEY_ groups stay allowed by Limit Total
	col2, lod2, arm2, obj2 = build_scene("dd2")
	sk = obj2.vertex_groups.new(name="SHAPEKEY_bone1")
	sk.add([0, 1, 2, 3], 0.5, "REPLACE")
	dd2Path = os.path.join(scratch, "dd2.mesh.260421070")
	ok = mesh_io.exportREMeshFile(dd2Path, dict(options, targetCollection=col2.name, exportBlendShapes=False, limitTotalCount=16))
	check("dd2 export ok", ok is True)
	parsed = reparse(dd2Path)
	sub = parsed.mainMeshLODList[0].visconGroupList[0].subMeshList[0]
	check("dd2 secondary (SHAPEKEY_) weights kept", parsed.bufferHasSecondaryWeight and len(sub.secondaryWeightList) == 4, parsed.bufferHasSecondaryWeight)
	check("dd2 primary weights without mask", [round(w, 2) for w in sub.weightList[0][:3]] == [0.7, 0.3, 0.0], sub.weightList[0][:3])
	check("dd2: no leftovers", *no_leftovers())

	# Atomic write: serializer crash, read-only target, missing directory
	original = open(wildsPath, "rb").read()
	realDirect = codec._writeREMeshDirect

	def failingDirect(reMeshFile, filepath):
		with open(filepath, "wb") as f:
			f.write(b"PARTIAL")
		raise RuntimeError("simulated serializer crash")
	select_only(arm)
	codec._writeREMeshDirect = failingDirect
	try:
		raised = raises(mesh_io.exportREMeshFile, wildsPath, dict(options))
	finally:
		codec._writeREMeshDirect = realDirect
	check("serializer crash propagates", isinstance(raised, RuntimeError), raised)
	check("existing target untouched after serializer crash", open(wildsPath, "rb").read() == original)
	check("temp file cleaned after crash", not [f for f in os.listdir(scratch) if f.startswith(".re-mesh-")], os.listdir(scratch))
	check("crash: no CLN_/clonedMeshes left", *no_leftovers())
	check("crash: no new orphan meshes", orphan_meshes() == orphansBefore, orphan_meshes())
	check("crash: selection/active restored", bpy.context.view_layer.objects.active == arm and [o.name for o in bpy.context.selected_objects] == [arm.name])
	check("crash: progress stack empty", progress._stack == [], progress._stack)

	os.chmod(wildsPath, stat.S_IREAD)
	raised = raises(mesh_io.exportREMeshFile, wildsPath, dict(options))
	os.chmod(wildsPath, stat.S_IWRITE | stat.S_IREAD)
	check("read-only target refused", isinstance(raised, PermissionError), repr(raised))
	check("read-only target untouched", open(wildsPath, "rb").read() == original)
	check("read-only: no leftovers", *no_leftovers())

	missing = os.path.join(scratch, "does_not_exist", "x.mesh.241111606")
	raised = raises(mesh_io.exportREMeshFile, missing, dict(options))
	check("nonexistent dir raises", raised is not None and not os.path.exists(missing), repr(raised))
	check("nonexistent dir: no leftovers", *no_leftovers())

	# ================= Operator failure handling
	bpy.context.scene["REMeshDefaultExportSettingsLoaded"] = 1
	raised = raises(bpy.ops.re_mesh.exportfile, filepath=missing, targetCollection=col.name, shapeKeyExportMode="KEEPNORMALS")
	check("ExportREMesh operator reports ERROR on failure", raised is not None and "RE Mesh export failed" in str(raised), repr(raised))
	check("operator failure: no leftovers", *no_leftovers())
	# Mesh with bone weights but no armature -> error dict -> False -> CANCELLED
	col3 = bpy.data.collections.new("noarm.mesh")
	col3["~TYPE"] = "RE_MESH_COLLECTION"
	bpy.context.scene.collection.children.link(col3)
	orphan = obj.copy()
	orphan.data = obj.data.copy()
	orphan.parent = None
	orphan.modifiers.clear()
	col3.objects.link(orphan)
	noarmPath = os.path.join(scratch, "noarm.mesh.241111606")
	with open(noarmPath, "wb") as f:
		f.write(b"KEEPME")
	raised = raises(bpy.ops.re_mesh.exportfile, filepath=noarmPath, targetCollection=col3.name, shapeKeyExportMode="NO")
	check("no-armature export fails with ERROR report", raised is not None, repr(raised))
	check("no-armature: existing target untouched", open(noarmPath, "rb").read() == b"KEEPME")
	check("no-armature: no leftovers", *no_leftovers())
	opPath = os.path.join(scratch, "op.mesh.241111606")
	res = bpy.ops.re_mesh.exportfile(filepath=opPath, targetCollection=col.name, shapeKeyExportMode="KEEPNORMALS", limitTotal=True, limitTotalCount=12)
	check("ExportREMesh operator FINISHED", res == {"FINISHED"} and os.path.isfile(opPath), res)
	check("BatchExport_shapeKeyExportMode saved", col.get("BatchExport_shapeKeyExportMode") == "KEEPNORMALS", col.get("BatchExport_shapeKeyExportMode"))
	check("BatchExport_preserveMaterialTable saved", col.get("BatchExport_preserveMaterialTable") == False, col.get("BatchExport_preserveMaterialTable"))

	# ================= Import back + multi-file partial failure
	badPath = os.path.join(scratch, "bad.mesh.241111606")
	with open(badPath, "wb") as f:
		f.write(b"not a mesh")
	bpy.context.scene["REMeshDefaultImportSettingsLoaded"] = 1
	res = bpy.ops.re_mesh.importfile(filepath=wildsPath, directory=scratch, files=[{"name": "wilds.mesh.241111606"}], clearScene=False, loadMaterials=False, loadMDFData=False, loadShellFur=False)
	check("single import FINISHED", res == {"FINISHED"}, res)
	imported = [c for c in bpy.data.collections if c.name.startswith("wilds.mesh") and c != col]
	check("imported collection created", bool(imported), [c.name for c in imported])
	if imported:
		stored = imported[0].get(materialTable.KEY)
		check("import stores original material table JSON", stored is not None and json.loads(stored) == ["wildsMat"], stored)
	res = bpy.ops.re_mesh.importfile(directory=scratch, files=[{"name": "bad.mesh.241111606"}, {"name": "dd2.mesh.260421070"}], clearScene=False, loadMaterials=False, loadMDFData=False, loadShellFur=False)
	check("multi import partial success -> FINISHED", res == {"FINISHED"}, res)
	check("multi import: progress stack empty", progress._stack == [], progress._stack)
	raised = raises(bpy.ops.re_mesh.importfile, filepath=badPath, directory=scratch, files=[{"name": "bad.mesh.241111606"}], clearScene=True, loadMaterials=False, loadMDFData=False, loadShellFur=False)
	check("single bad import -> ERROR report (raise) / CANCELLED", raised is not None, repr(raised))
	check("clearScene did not wipe scene on bad import", col.name in bpy.data.collections and obj.name in bpy.data.objects)

	# ================= Progress tracking (background mode: log only, no console, no progress bar)
	calls = []

	@progress.tracked_operation("Export")
	def fakeOperation(filePath, opts):
		calls.append(len(progress._stack))
		progress.stage("halfway", 50)
		if opts.get("fail"):
			raise ValueError("boom")
		return opts.get("result", True)
	check("tracked op returns result", fakeOperation("x.mesh.1", {"result": True}) is True and calls == [1])
	check("tracked op re-raises", isinstance(raises(fakeOperation, "x.mesh.1", {"fail": True}), ValueError))
	check("tracked op stack empty after raise", progress._stack == [], progress._stack)
	with progress.operation_scope("outer") as scope:
		outer = progress._stack[-1]
		fakeOperation("y.mesh.1", {})
		scope["success"] = True
	check("operation_scope nests: inner not root", calls[-1] == 2 and outer.root)
	check("background: console never opened", outer.console.handle is None and not outer.console.opened)
	check("background: no progress bar", outer.wm is None)
	check("module-level stage() with empty stack is a no-op", raises(progress.stage, "nothing", 10) is None)

	# ================= B2 UV handling
	uvCol, uvLod, uvArm, uvObj = build_scene("uvcheck")
	uvData = uvObj.data
	uv1 = uvData.uv_layers.new(name="UV1")
	# UV1 has a seam at vertex 0 (two different coordinates) while UV0 does not.
	for loop, co in zip(uv1.data, [(0, 0), (1, 0), (1, 1), (0.5, 0.5), (1, 1), (0, 1)]):
		loop.uv = co
	check("UV doubling detected on UV1", mesh_io.checkObjForUVDoubling(uvObj) is True)
	check("UV doubling ignores maps beyond uvLimit", mesh_io.checkObjForUVDoubling(uvObj, 1) is False)
	for loop, co in zip(uv1.data, [(0, 0), (1, 0), (1, 1), (0, 0), (1, 1), (0, 1)]):
		loop.uv = co
	ref = uvData.uv_layers.new(name="Reference")
	for loop, co in zip(ref.data, [(0, 0), (1, 0), (1, 1), (0.3, 0.3), (1, 1), (0, 1)]):
		loop.uv = co
	check("split only on a reference map (3rd UV) is not exported doubling", mesh_io.checkObjForUVDoubling(uvObj, 2) is False)
	check("...but is seen without a limit", mesh_io.checkObjForUVDoubling(uvObj) is True)

	uvOptions = dict(options, targetCollection=uvCol.name, exportBlendShapes=False, limitTotal=False)
	uvPath = os.path.join(scratch, "uv.mesh.241111606")
	warnings.clear()
	uvData.uv_layers.active_index = 0
	ok = mesh_io.exportREMeshFile(uvPath, dict(uvOptions))
	check("export with 3 UV maps succeeds", ok is True, ok)
	check("extra reference UV map warns", any("additional reference UV map" in w for w in warnings), warnings)
	parsed = reparse(uvPath)
	sub = parsed.mainMeshLODList[0].visconGroupList[0].subMeshList[0]
	check("3rd map does not split exported vertices", len(sub.vertexPosList) == 4, len(sub.vertexPosList))
	check("UV0/UV1 written", len(sub.uvList) == 4 and len(sub.uv2List) == 4, (len(sub.uvList), len(sub.uv2List)))
	activeZero = open(uvPath, "rb").read()
	uvData.uv_layers.active_index = 2
	ok = mesh_io.exportREMeshFile(uvPath, dict(uvOptions))
	check("active omitted reference map: tangents still from UV0 (identical output)", ok is True and open(uvPath, "rb").read() == activeZero)
	check("active UV map restored on source", uvData.uv_layers.active_index == 2)
	uvData.uv_layers.active_index = 0

	# Auto Solve Repeated UVs must also split vertices for a UV1 seam (corner splitting off)
	for loop, co in zip(uv1.data, [(0, 0), (1, 0), (1, 1), (0.5, 0.5), (1, 1), (0, 1)]):
		loop.uv = co
	ok = mesh_io.exportREMeshFile(uvPath, dict(uvOptions, splitLoopVertices=False))
	check("UV1 seam solved by Auto Solve Repeated UVs", ok is True, ok)
	if ok is True:
		sub = reparse(uvPath).mainMeshLODList[0].visconGroupList[0].subMeshList[0]
		check("UV1 seam produced a split vertex", len(sub.vertexPosList) == 5, len(sub.vertexPosList))
	check("UV1 auto solve: no leftovers", *no_leftovers())
	check("UV1 auto solve: source mesh unchanged", len(uvData.vertices) == 4)

	before = open(uvPath, "rb").read()
	for badValue, label in ((float("nan"), "non-finite"), (70000.0, "out-of-range")):
		saved = tuple(uv1.data[0].uv)
		uv1.data[0].uv = (badValue, 0.0)
		raised = raises(mesh_io.exportREMeshFile, uvPath, dict(uvOptions))
		uv1.data[0].uv = saved
		check(f"{label} UV fails export clearly", isinstance(raised, ValueError) and "UV1" in str(raised), repr(raised))
		check(f"{label} UV: target untouched", open(uvPath, "rb").read() == before)
		check(f"{label} UV: no leftovers", *no_leftovers())
	badRef = tuple(ref.data[0].uv)
	ref.data[0].uv = (float("inf"), 0.0)
	ok = mesh_io.exportREMeshFile(uvPath, dict(uvOptions))
	ref.data[0].uv = badRef
	check("non-finite values on an omitted reference map are ignored", ok is True, ok)

	remesh = uvObj.modifiers.new("Remesh", "REMESH")
	remesh.mode = "BLOCKS"
	dg = bpy.context.evaluated_depsgraph_get()
	evaluatedUVCount = len(uvObj.evaluated_get(dg).data.uv_layers)
	if evaluatedUVCount < 2:
		raised = raises(mesh_io.exportREMeshFile, uvPath, dict(uvOptions))
		check("modifier stack removing UV maps fails export", isinstance(raised, ValueError) and "removed UV maps" in str(raised), repr(raised))
		check("UV-removing modifier: no leftovers", *no_leftovers())
	else:
		check("Remesh modifier removes UV maps (test precondition)", False, evaluatedUVCount)
	uvObj.modifiers.remove(remesh)

	# ================= B4 Preserve Original Material Table
	matCol, matLod, matArm, matObjs = build_scene("mats", materials=("A", "B"))
	matPath = os.path.join(scratch, "mats.mesh.241111606")
	matOptions = dict(options, targetCollection=matCol.name, exportBlendShapes=False, limitTotal=False)
	check("two-material export", mesh_io.exportREMeshFile(matPath, dict(matOptions)) is True)
	check("two-material order", reparse(matPath).materialNameList == ["matsA", "matsB"], reparse(matPath).materialNameList)
	res = bpy.ops.re_mesh.importfile(filepath=matPath, directory=scratch, files=[{"name": "mats.mesh.241111606"}], clearScene=False, loadMaterials=False, loadMDFData=False, loadShellFur=False)
	importedMats = [c for c in bpy.data.collections if c.name.startswith("mats.mesh") and c != matCol]
	check("material mesh imported", res == {"FINISHED"} and bool(importedMats), res)
	impCol = importedMats[0]
	check("stored material table", json.loads(impCol.get(materialTable.KEY, "null") or "null") == ["matsA", "matsB"], impCol.get(materialTable.KEY))
	# Remove the submesh using the first material
	for o in list(impCol.all_objects):
		if o.type == "MESH" and o.name.endswith("matsA"):
			bpy.data.objects.remove(o, do_unlink=True)
	impOptions = dict(matOptions, targetCollection=impCol.name)
	outPath = os.path.join(scratch, "mats_out.mesh.241111606")
	check("export without preserve", mesh_io.exportREMeshFile(outPath, dict(impOptions)) is True)
	parsed = reparse(outPath)
	check("default (off): unused slot dropped", parsed.materialNameList == ["matsB"], parsed.materialNameList)
	check("export with preserve", mesh_io.exportREMeshFile(outPath, dict(impOptions, preserveMaterialTable=True)) is True)
	parsed = reparse(outPath)
	sub = parsed.mainMeshLODList[0].visconGroupList[0].subMeshList[0]
	check("preserve: original order incl. unused slot", parsed.materialNameList == ["matsA", "matsB"], parsed.materialNameList)
	check("preserve: submesh points at its original slot", sub.materialIndex == 1, sub.materialIndex)
	# New material is appended with a warning
	newObj = [o for o in impCol.all_objects if o.type == "MESH"][0]
	newObj.name = newObj.name.rsplit("__", 1)[0] + "__matsC"
	warnings.clear()
	check("export with new material", mesh_io.exportREMeshFile(outPath, dict(impOptions, preserveMaterialTable=True)) is True)
	parsed = reparse(outPath)
	check("preserve: new material appended", parsed.materialNameList == ["matsA", "matsB", "matsC"], parsed.materialNameList)
	check("preserve: new material warns", any("New material slots appended" in w for w in warnings), warnings)
	# Wilds shape keys still written correctly with a preserved table (names list = materials + bones + shapes)
	newObj.shape_key_add(name="Basis")
	shape = newObj.shape_key_add(name="Smile")
	shape.data[0].co.z += 0.1
	check("preserve + Wilds blendshapes export", mesh_io.exportREMeshFile(outPath, dict(impOptions, preserveMaterialTable=True, exportBlendShapes=True, blendShapeExportMode=-1)) is True)
	parsed = reparse(outPath, True)
	sub = parsed.mainMeshLODList[0].visconGroupList[0].subMeshList[0]
	check("preserve + blendshapes: materials", parsed.materialNameList == ["matsA", "matsB", "matsC"], parsed.materialNameList)
	check("preserve + blendshapes: shape name", [b.blendShapeName for b in sub.blendShapeList] == ["Smile"], [b.blendShapeName for b in sub.blendShapeList])
	check("preserve + blendshapes: bones", [b.boneName for b in parsed.skeleton.boneList] == ["bone0", "bone1"], [b.boneName for b in parsed.skeleton.boneList])
	# Collections without metadata fail clearly when the option is on
	raised = raises(mesh_io.exportREMeshFile, outPath, dict(matOptions, preserveMaterialTable=True))
	check("preserve without import metadata fails clearly", isinstance(raised, ValueError) and "fresh import" in str(raised), repr(raised))
	check("material table: no leftovers", *no_leftovers())
	# Pure helper checks
	check("decode rejects duplicates", isinstance(raises(materialTable.decode_table, json.dumps(["a", "a"])), ValueError))
	check("decode rejects invalid JSON", isinstance(raises(materialTable.decode_table, "{"), ValueError))

	# ================= Batch export
	for c in bpy.data.collections:
		if "BatchExport_enabled" in c or c.get("~TYPE") in ("RE_MESH_COLLECTION", "RE_MDF_COLLECTION"):
			c["BatchExport_enabled"] = False
	for k in list(col.keys()):
		if k.startswith("BatchExport_"):
			del col[k]
	batchPath = os.path.join(scratch, "batch", "wilds.mesh.241111606")
	col["BatchExport_path"] = batchPath
	col["BatchExport_enabled"] = True
	captured = []
	realExport = addon.exportREMeshFile

	def capture(filePath, opts):
		captured.append((filePath, dict(opts)))
		return realExport(filePath, opts)

	def runBatch():
		captured.clear()
		addon.exportREMeshFile = capture
		try:
			return bpy.ops.re_mesh.quick_batch_export()
		finally:
			addon.exportREMeshFile = realExport
	res = runBatch()
	check("quick batch export FINISHED", res == {"FINISHED"}, res)
	check("quick batch wrote file (makedirs)", os.path.isfile(batchPath))
	o = captured[0][1] if captured else {}
	check("legacy item: KEEPNORMALS default -> blendShapeExportMode -1", o.get("exportBlendShapes") is True and o.get("blendShapeExportMode") == -1, (o.get("exportBlendShapes"), o.get("blendShapeExportMode")))
	check("legacy item: limitTotalCount auto = 12 for Wilds", o.get("limitTotalCount") == 12, o.get("limitTotalCount"))
	check("legacy item: split/normalize/limit/material-table defaults", o.get("splitLoopVertices") is True and o.get("normalizeWeights") is True and o.get("limitTotal") is False and o.get("preserveMaterialTable") is False, o)
	check("batch: progress stack empty", progress._stack == [], progress._stack)
	col["BatchExport_shapeKeyExportMode"] = "MODE1"
	col["BatchExport_limitTotal"] = True
	col["BatchExport_limitTotalCount"] = 4
	col["BatchExport_splitLoopVertices"] = False
	col["BatchExport_normalizeWeights"] = False
	res = runBatch()
	o = captured[0][1] if captured else {}
	check("saved item options passed", res == {"FINISHED"} and o.get("blendShapeExportMode") == 1 and o.get("limitTotal") is True and o.get("limitTotalCount") == 4 and o.get("splitLoopVertices") is False and o.get("normalizeWeights") is False, (res, o))
	col["BatchExport_shapeKeyExportMode"] = "BOGUS"
	res = runBatch()
	o = captured[0][1] if captured else {}
	check("invalid saved enum -> KEEPNORMALS", o.get("blendShapeExportMode") == -1, o.get("blendShapeExportMode"))
	col["BatchExport_shapeKeyExportMode"] = "KEEPNORMALS"
	# Per-item Preserve Original Material Table is passed through
	for c in bpy.data.collections:
		if "BatchExport_enabled" in c:
			c["BatchExport_enabled"] = False
	impCol["BatchExport_enabled"] = True
	impCol["BatchExport_path"] = os.path.join(scratch, "batch", "mats.mesh.241111606")
	impCol["BatchExport_preserveMaterialTable"] = True
	res = runBatch()
	o = captured[0][1] if captured else {}
	check("batch item preserveMaterialTable passed", res == {"FINISHED"} and o.get("preserveMaterialTable") is True, (res, o.get("preserveMaterialTable")))
	impCol["BatchExport_enabled"] = False
	col["BatchExport_enabled"] = True
	# Failing item -> CANCELLED
	col["BatchExport_path"] = os.path.join(scratch, "noarm_batch.mesh.241111606")
	col3["BatchExport_enabled"] = True
	col3["BatchExport_path"] = noarmPath
	res = bpy.ops.re_mesh.quick_batch_export()
	check("batch with a failing item -> CANCELLED", res == {"CANCELLED"}, res)
	check("batch failure: noarm target untouched", open(noarmPath, "rb").read() == b"KEEPME")
	for c in bpy.data.collections:
		if "BatchExport_enabled" in c:
			c["BatchExport_enabled"] = False
	res = bpy.ops.re_mesh.quick_batch_export()
	check("empty batch list -> CANCELLED", res == {"CANCELLED"}, res)
	check("end: no leftovers", *no_leftovers())
	check("end: progress stack empty", progress._stack == [], progress._stack)

	mesh_io.raiseWarning = realRaiseWarning
	failed = [r for r in results if not r[1]]
	print(f"\nSUMMARY: {len(results) - len(failed)}/{len(results)} passed", flush=True)
	if failed:
		raise SystemExit("FAILED: " + ", ".join(r[0] for r in failed))


if __name__ == "__main__":
	scratch = tempfile.mkdtemp(prefix="remesh-export-tests-")
	try:
		main(scratch)
	finally:
		shutil.rmtree(scratch, onerror=lambda f, p, e: (os.chmod(p, stat.S_IWRITE), f(p)))
