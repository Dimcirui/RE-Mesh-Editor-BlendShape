"""Resident Evil 4 (2023) blend-shape export for the unified RE Mesh exporter.

RE4 shares Wilds' target records (active targets with BlendSubMesh runs, then
`typing` inactive targets) and its canonical normal-recalc tables, so those
parts reuse mhwilds_blendshape. Layout of the six vanilla faces surveyed
(cha000/005/006/102/800 _10, 2026-10-12) and four modded heads:
- one active target per body holding every channel; its runs are whole
  submeshes (vanilla: the face submesh). One inactive target per viscon group
  covers the remaining vertices, an empty one when nothing is left;
- each payload row is 8 bytes, float16 (dx, dy, dz, 0) in mesh units; the
  target AABB is the symmetric max |delta| and is not used to decode;
- the payload follows the vertex elements, its start in the two shorts at
  MeshBufferHeader + 44; vertOffset is the run's absolute payload row;
- body 0 (LOD0): unknFlag 1, blendS (-1, 0, 0), every blendSS -1. Higher LOD
  bodies (cha800 only) repeat the LOD0 channels in order with blendSSIndex 0,
  blendS (0, 0, 0) and blendSS 0..n-1, plus their own "_LOD<n>" names;
- the canonical tables cover LOD0 only and live in their own section at
  normalRecalcOffset: count 1, pointer array, {vertex table, face table}.
  Wilds' generator rebuilds them from vanilla geometry byte for byte except
  on cha006, where vanilla keeps twins within 1 degree apart (99.4%); only
  exact-normal merging reproduces that, but Blender exports add 1-4 units of
  normal noise to vanilla's identical twins, so the 1 degree rule is kept.

Keep Normals writes the no-recalc layout of vanilla chd000_00 (seen by the
Funnyguysmz fork, not in our extract): unknFlag 0, normalRecalcOffset 0, no
tables, and each 8-byte row is [Wilds packed 11/10/11 delta scaled by the
target AABB, the shape's int8 normal]. The fork's in-game test repeated the
base normal on every key; per-key normals are untested in game.

LOD0 is split into region targets as in Wilds (_region_targets): channels
that move a common row share a target, and each target stores only the rows
its channels move or turn. Vanilla has one active target per body in all 26
RE4 meshes with blend shapes (2026-11-03 survey of all 7164 meshes), but runs
that cut through submeshes are vanilla (chd000_00, sm61_344_00), and a
5-target Leon body (cha000_00, 51 keys, 65.3 -> 18.0 MiB) worked in game on
2026-11-03. A body with several targets gets no higher LOD bodies, so when
higher LODs carry shape keys LOD0 keeps the vanilla layout and is split only
past PAYLOAD_ROW_LIMIT, with the smallest target cap that fits; the game
applies no shape key of a mesh whose payload rows pass that limit.
"""

import struct

import numpy as np

from . import file_re_mesh as mesh_format
from . import mhwilds_blendshape as wilds


# The header qword differs per vanilla file (it looks like a stale pointer);
# this is cha000_10's, which the known working mods also carry.
BLEND_HEADER_HASH = 2615081718160
NORMAL_RECALC_HEADER_BYTES = 48
# Both row layouts are 8 bytes.
ROW_BYTES = 8
# In game (Leon body cha000_00, 2026-11-03, Keep Normals) a body whose rows
# ended at 8555148 applied none of its 51 keys, the same file cut to 49 keys
# (8219652 rows) applied all. The payload started 7.9 MB into the vertex
# buffer, so the limit counts rows from the payload start: 2^23 rows (64 MiB).
PAYLOAD_ROW_LIMIT = 1 << 23
# Target caps tried in turn when a vanilla-layout LOD0 has to be split to fit.
SPLIT_TARGET_CAPS = (1, 2, 4, 8, 16, 32, 64)
# Active targets per LOD0 body when it is split by default (Wilds' cap).
MAX_ACTIVE_TARGETS = wilds.MAX_ACTIVE_TARGETS_PER_BODY


def _pack_rows(deltas):
	deltas = np.asarray(deltas, dtype=np.float32).reshape((-1, 3))
	rows = np.zeros((len(deltas), 4), dtype="<f2")
	rows[:, :3] = deltas
	return rows.tobytes()


def _pack_keep_normal_rows(deltas, normal_rows, aabb):
	"""Keep-normals rows: packed delta word, then the shape's int8 normal word."""
	words = np.frombuffer(wilds._pack_delta_rows(deltas, aabb), dtype="<u4")
	return np.column_stack((words, normal_rows)).astype("<u4").tobytes()


def _new_target(channel_count, runs, lo):
	target = mesh_format.BlendTarget()
	target.blendSSIndex = 0
	target.blendShapeNum = int(channel_count)
	target.unkn0 = 0
	target.unkn2 = 1 if channel_count else 0
	target.subMeshEntryList = wilds._run_entries(runs, lo)
	target.subMeshEntryCount = len(target.subMeshEntryList)
	return target


def _group_deltas(submeshes, names, keep_normals=False):
	"""(name, deltas, mask, normal rows) of the given channels over one viscon
	group's global range; the packed normal rows only with keep_normals."""
	lo = min(int(info.vertexStartIndex) for _parsed, info, _count in submeshes)
	hi = max(int(info.vertexStartIndex) + count for _parsed, info, count in submeshes)
	valid = np.zeros(hi - lo, dtype=bool)
	ranges = []
	base = np.zeros((hi - lo, 3), dtype=np.float32) if keep_normals else None
	for parsed_submesh, info, count in submeshes:
		start = int(info.vertexStartIndex) - lo
		valid[start:start + count] = True
		ranges.append((start, start + count))
		if keep_normals:
			base[start:start + count] = wilds._base_normals(parsed_submesh, count)
	channels = []
	for name in names:
		deltas = np.zeros((hi - lo, 3), dtype=np.float32)
		normals = None if base is None else base.copy()
		for parsed_submesh, info, count in submeshes:
			start = int(info.vertexStartIndex) - lo
			deltas[start:start + count] = wilds._normalized_deltas(
				parsed_submesh, name, count
			)
			if normals is not None:
				normals[start:start + count] = wilds._shape_normals(
					parsed_submesh, name, base[start:start + count]
				)
		mask = np.any(np.abs(deltas) > wilds.EDIT_DELTA_THRESHOLD, axis=1)
		rows = None if normals is None else wilds._pack_normal_rows(normals)
		channels.append((name, deltas, mask, rows))
	return lo, valid, ranges, channels


def _submesh_runs(mask, ranges):
	"""Runs made of every whole submesh that has a moving vertex."""
	marked = np.zeros(len(mask), dtype=bool)
	for start, end in ranges:
		if mask[start:end].any():
			marked[start:end] = True
	return wilds._mask_runs(marked)


def _whole_submesh_targets(submeshes, keep_normals, channel_order):
	"""Vanilla layout: one target holding every channel over whole submeshes.

	Returns (lo, valid, [(runs, channels)]).
	"""
	if channel_order is None:
		lo, valid, ranges, channels = _group_deltas(
			submeshes, wilds._shape_names(submeshes), keep_normals
		)
		channels = [channel for channel in channels if channel[2].any()]
	else:
		lo, valid, ranges, channels = _group_deltas(
			submeshes, channel_order, keep_normals
		)
		if not any(channel[2].any() for channel in channels):
			channels = []
	if not channels:
		return lo, valid, []
	mask = np.zeros(len(valid), dtype=bool)
	for channel in channels:
		mask |= channel[2]
	runs = _submesh_runs(mask, ranges)
	if len(runs) > wilds.MAX_TARGET_ENTRIES:
		raise RuntimeError(
			f"RE4 blend target needs {len(runs)} vertex runs, "
			f"more than {wilds.MAX_TARGET_ENTRIES}"
		)
	return lo, valid, [(runs, channels)]


def _split_channels(submeshes, keep_normals):
	"""Wilds' group channels, masks reduced to rows that move or turn.

	With keep_normals a channel's mask holds the rows whose normal it turns,
	so those rows stay in its target. Wilds also keeps every row an imported
	key stored; a reimported RE4 export stored base-normal rows over whole
	submeshes, which would tie every key to them, so those rows are dropped.
	"""
	lo, valid, channels = wilds._group_channels(submeshes, with_normals=keep_normals)
	if not keep_normals:
		return lo, valid, channels
	base = np.zeros((len(valid), 3), dtype=np.float32)
	for parsed_submesh, info, count in submeshes:
		start = int(info.vertexStartIndex) - lo
		base[start:start + count] = wilds._base_normals(parsed_submesh, count)
	base_rows = wilds._pack_normal_rows(base)
	result = []
	for name, deltas, _mask, rows in channels:
		mask = np.any(np.abs(deltas) > wilds.EDIT_DELTA_THRESHOLD, axis=1)
		mask |= valid & wilds._normal_rows_changed(rows, base_rows)
		if mask.any():
			result.append((name, deltas, mask, rows))
	return lo, valid, result


def _region_split_targets(groups, keep_normals, max_targets):
	"""Wilds region targets over each group, max_targets shared by the body.

	Returns one (lo, valid, [(runs, channels)]) per group.
	"""
	grouped = [_split_channels(submeshes, keep_normals) for submeshes in groups]
	counts = [len(channels) for _lo, _valid, channels in grouped]
	# Every group with channels needs a target of its own.
	caps = wilds._split_target_cap(
		counts, max(int(max_targets), sum(1 for count in counts if count))
	)
	planned = []
	for (lo, valid, channels), cap in zip(grouped, caps):
		targets = [
			(runs, [channels[index] for index in cluster])
			for cluster, runs in wilds._region_targets(
				[channel[2] for channel in channels], valid, cap, ROW_BYTES
			)
		]
		planned.append((lo, valid, targets))
	return planned


def _build_body(
	lod, parsed_to_mesh_info, keep_normals, channel_order=None, max_targets=None
):
	"""One blend body. LOD0 passes no order; higher LODs repeat LOD0's channels.
	max_targets None keeps the vanilla layout, a number splits into region
	targets (LOD0 only).

	Returns (body, [(target, [(deltas, normal rows, runs)])], names) or None
	when the LOD has no usable shape keys. normal rows is None without
	keep_normals.
	"""
	groups = wilds._viscon_submeshes(lod, parsed_to_mesh_info)
	if not groups:
		return None
	body = mesh_format.BlendShapeData()
	body.padding1 = 0
	body.padding2 = 0
	body.unknFlag = 0 if keep_normals else 1
	body.aabbList = []
	active = []
	inactive = []
	names = []
	if max_targets is None:
		planned = [
			_whole_submesh_targets(submeshes, keep_normals, channel_order)
			for submeshes in groups
		]
	else:
		planned = _region_split_targets(groups, keep_normals, max_targets)
	for lo, valid, targets in planned:
		covered = np.zeros(len(valid), dtype=bool)
		for runs, channels in targets:
			target = _new_target(len(channels), runs, lo)
			target.unkn0 = len(active)
			for start, end in runs:
				covered[start:end] = True
			# Per target, so one far-moving key does not coarsen the others.
			body.aabbList.append(wilds._symmetric_aabb([
				deltas[mask] for _name, deltas, mask, _rows in channels
			]))
			active.append((
				target,
				[(deltas, rows, runs) for _name, deltas, _mask, rows in channels],
			))
			names.extend(channel[0] for channel in channels)
		rest = wilds._mask_runs(valid & ~covered)
		for chunk_start in range(0, len(rest), wilds.MAX_TARGET_ENTRIES):
			inactive.append(_new_target(
				0, rest[chunk_start:chunk_start + wilds.MAX_TARGET_ENTRIES], lo
			))
	if not active:
		return None
	# A group the active runs cover whole gets no inactive target (vanilla
	# chd500_01: typing 0).
	body.targetCount = len(active)
	body.typing = len(inactive)
	body.blendTargetList = [target for target, _rows in active] + inactive
	return body, active, names


def _target_rows(target):
	return sum(int(entry.vertCount) for entry in target.subMeshEntryList)


def _body_rows(active):
	return sum(_target_rows(target) * int(target.blendShapeNum) for target, _rows in active)


def _row_limit_report(active, names):
	lines = []
	channel = 0
	for index, (target, _rows) in enumerate(active):
		count = int(target.blendShapeNum)
		rows = _target_rows(target) * count
		keys = names[channel:channel + count]
		channel += count
		shown = ", ".join(keys[:6]) + (", ..." if len(keys) > 6 else "")
		lines.append(
			f"  target {index}: {count} keys x {_target_rows(target)} rows = "
			f"{rows * ROW_BYTES / 2**20:.1f} MiB ({shown})"
		)
	return "\n".join(lines)


def _lod_shape_names(lod, parsed_to_mesh_info):
	return {
		name
		for submeshes in wilds._viscon_submeshes(lod, parsed_to_mesh_info)
		for name in wilds._shape_names(submeshes)
	}


def _raise_row_limit(built):
	mesh_format.raiseError(
		f"RE4 shape keys need {_body_rows(built[1])} payload rows even split "
		f"into {len(built[1])} targets; the game applies no shape key past "
		f"{PAYLOAD_ROW_LIMIT} rows ({PAYLOAD_ROW_LIMIT * ROW_BYTES // 2**20} MiB). "
		"Remove shape keys or the vertices they move:\n"
		+ _row_limit_report(built[1], built[2])
	)


def _build_lod0(lod, parsed_to_mesh_info, keep_normals, keep_lods):
	"""LOD0 split into region targets. With keep_lods (higher LODs carry shape
	keys) the vanilla layout, split only past the row limit."""
	if not keep_lods:
		built = _build_body(
			lod, parsed_to_mesh_info, keep_normals, max_targets=MAX_ACTIVE_TARGETS
		)
		if built is not None and _body_rows(built[1]) > PAYLOAD_ROW_LIMIT:
			_raise_row_limit(built)
		return built
	built = _build_body(lod, parsed_to_mesh_info, keep_normals)
	if built is None:
		return None
	whole_rows = _body_rows(built[1])
	if whole_rows <= PAYLOAD_ROW_LIMIT:
		return built
	for cap in SPLIT_TARGET_CAPS:
		built = _build_body(lod, parsed_to_mesh_info, keep_normals, max_targets=cap)
		if _body_rows(built[1]) <= PAYLOAD_ROW_LIMIT:
			break
	else:
		_raise_row_limit(built)
	mesh_format.raiseWarning(
		f"RE4 shape keys over whole submeshes need {whole_rows} payload rows, "
		f"more than the game's {PAYLOAD_ROW_LIMIT}; LOD0 was split into "
		f"{len(built[1])} targets ({_body_rows(built[1])} rows):\n"
		+ _row_limit_report(built[1], built[2])
	)
	return built


def build_re4_blend_shape_plan(parsed_mesh, parsed_to_mesh_info):
	"""Build the blend bodies, their name list and the payload."""
	lods = wilds._list_or_empty(getattr(parsed_mesh, "mainMeshLODList", None))
	if not lods:
		return None
	keep_normals = wilds._keeps_normals(parsed_mesh=parsed_mesh)
	wilds._drop_empty_shapes(lods)
	keep_lods = len(lods) > 1 and bool(_lod_shape_names(lods[1], parsed_to_mesh_info))
	built = _build_lod0(lods[0], parsed_to_mesh_info, keep_normals, keep_lods)
	if built is None:
		return None
	bodies = [built]
	base_names = built[2]
	total_rows = _body_rows(built[1])
	for lod_index, lod in enumerate(lods[1:], start=1):
		lod_names = _lod_shape_names(lod, parsed_to_mesh_info)
		if not lod_names:
			break
		reason = None
		if len(bodies[0][1]) != 1:
			reason = (
				"LOD0 has more than one blend target (shape keys in several "
				"viscon groups, or split to fit the payload row limit)"
			)
		elif not lod_names <= set(base_names):
			reason = "it has shape keys LOD0 does not have: " + ", ".join(
				sorted(lod_names - set(base_names))
			)
		else:
			built = _build_body(
				lod, parsed_to_mesh_info, keep_normals, channel_order=base_names
			)
			if built is None:
				break
			if len(built[1]) != 1:
				reason = "its shape keys move more than one viscon group"
			elif total_rows + _body_rows(built[1]) > PAYLOAD_ROW_LIMIT:
				reason = (
					f"the payload would pass the game's {PAYLOAD_ROW_LIMIT} rows"
				)
		if reason:
			mesh_format.raiseWarning(
				f"RE4 shape keys exported for LOD0-LOD{lod_index - 1} only; "
				f"LOD{lod_index} skipped because {reason}"
			)
			break
		bodies.append(built)
		total_rows += _body_rows(built[1])

	header = mesh_format.BlendShapeHeader()
	header.zero = 0
	header.hash = BLEND_HEADER_HASH
	header.blendShapeList = []
	remap_names = list(base_names)
	payload = bytearray()
	row = 0
	for body_index, (body, active, names) in enumerate(bodies):
		if body_index == 0:
			body.blendS = [-1, 0, 0]
			body.blendSSList = [-1] * len(names)
		else:
			# Higher LODs follow the LOD0 channel with the same index.
			body.blendS = [0, 0, 0]
			body.blendSSList = list(range(len(names)))
			remap_names.extend(f"{name}_LOD{body_index}" for name in names)
		channel_base = 0
		for target_index, (target, rows) in enumerate(active):
			target.blendSSIndex = channel_base if body_index == 0 else 0
			channel_base += int(target.blendShapeNum)
			target_rows = sum(int(entry.vertCount) for entry in target.subMeshEntryList)
			prefix = 0
			for entry in target.subMeshEntryList:
				entry.vertOffset = row + prefix
				prefix += int(entry.vertCount)
			aabb = body.aabbList[target_index]
			for deltas, normal_rows, runs in rows:
				for start, end in runs:
					if keep_normals:
						payload.extend(_pack_keep_normal_rows(
							deltas[start:end], normal_rows[start:end], aabb
						))
					else:
						payload.extend(_pack_rows(deltas[start:end]))
			row += target_rows * int(target.blendShapeNum)
		header.blendShapeList.append(body)
	header.count = len(header.blendShapeList)
	payload.extend(b"\x00" * mesh_format.getPaddingAmount(len(payload), 16))
	return {
		"header": header,
		"shapeRemapNames": remap_names,
		"payload": bytes(payload),
		"keepNormals": keep_normals,
	}


def _lod0_range(re_mesh):
	lod = re_mesh.lodHeader.lodGroupList[0]
	vertex_count = sum(int(group.vertexCount) for group in lod.meshGroupList)
	index_count = max(
		(
			int(entry.faceStartIndex) + int(entry.faceCount)
			for group in lod.meshGroupList
			for entry in group.vertexInfoList
			if int(entry.faceCount)
		),
		default=0,
	)
	return lod, vertex_count, index_count


def reserve_re4_normal_recalc(re_mesh, current_offset, keep_normals=False):
	"""Reserve the LOD0 canonical-table section; returns the offset after it.

	The keep-normals layout has no section: normalRecalcOffset stays 0.
	"""
	re_mesh._re4KeepNormals = bool(keep_normals)
	if keep_normals:
		re_mesh.fileHeader.normalRecalcOffset = 0
		return wilds._align16(current_offset)
	_lod, vertex_count, index_count = _lod0_range(re_mesh)
	offset = wilds._align16(current_offset)
	size = (
		NORMAL_RECALC_HEADER_BYTES
		+ wilds._align16(vertex_count * 4)
		+ wilds._align16(index_count * 4)
	)
	re_mesh.fileHeader.normalRecalcOffset = offset
	re_mesh._re4NormalRecalcSize = size
	return offset + size


def _warn_lane_overflow(face_table, lod_range):
	"""Face-table lanes are 10 bits: one 1536-index block holds 1024 vertices.

	Vanilla blocks stay at or below 968; a triangle soup can exceed it, and the
	lanes of those blocks then wrap.
	"""
	canonical = np.frombuffer(face_table, dtype="<u4") & 0x3FFFFF
	starts = []
	for start, end, vertex_start in wilds._face_intervals(lod_range):
		for block in range(start, end, 1536):
			if len(np.unique(canonical[block:min(end, block + 1536)])) > 1024:
				starts.append(vertex_start)
				break
	if starts:
		mesh_format.raiseWarning(
			"RE4 normal recalculation: LOD0 submeshes starting at vertex "
			+ ", ".join(str(value) for value in starts)
			+ " have more than 1024 distinct vertices in one 512-triangle block "
			"(unconnected triangles). Their recalculated normals may be wrong "
			"while shape keys are active."
		)


def finalize_re4_export(re_mesh):
	"""Write the payload start and generate the canonical normal-recalc tables."""
	mesh_header = re_mesh.meshBufferHeader
	payload_start = int(re_mesh._re4BlendPayloadStart)
	mesh_header.vertexElementSize = wilds._signed_short(payload_start & 0xFFFF)
	mesh_header.unkn1 = wilds._signed_short((payload_start >> 16) & 0xFFFF)
	if getattr(re_mesh, "_re4KeepNormals", False):
		re_mesh._re4NormalRecalcBlob = None
		return

	lod, vertex_count, _index_count = _lod0_range(re_mesh)
	lod_range = {"lod": lod, "baseVertex": 0, "vertexCount": vertex_count, "baseFace": 0}
	# Twins are rows with the same position and normals within 1 degree.
	# Blender vertex identity is not used: imported UV-seam twins are separate
	# Blender vertices, and keeping them apart would show as normal seams.
	face_table, vertex_table = wilds._canonical_tables(
		re_mesh,
		0,
		bytes(mesh_header.faceBuffer),
		bytes(mesh_header.vertexBuffer),
		mesh_header.vertexElementList,
		lod_range,
	)
	_warn_lane_overflow(face_table, lod_range)
	offset = int(re_mesh.fileHeader.normalRecalcOffset)
	vertex_table_offset = offset + NORMAL_RECALC_HEADER_BYTES
	face_table_offset = vertex_table_offset + len(vertex_table)
	blob = (
		struct.pack("<QQ", 1, offset + 16)
		+ struct.pack("<QQ", offset + 32, 0)
		+ struct.pack("<QQ", vertex_table_offset, face_table_offset)
		+ vertex_table
		+ face_table
	)
	if len(blob) != int(re_mesh._re4NormalRecalcSize):
		raise RuntimeError(
			"RE4 normal-recalc tables differ from their reservation: "
			f"{len(blob)}/{int(re_mesh._re4NormalRecalcSize)} bytes"
		)
	if offset + len(blob) != int(re_mesh.fileHeader.blendShapesOffset):
		raise RuntimeError("RE4 normal-recalc tables must end at blendShapesOffset")
	re_mesh._re4NormalRecalcBlob = blob
