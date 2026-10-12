"""Monster Hunter Rise: Sunbreak blend-shape export for the unified RE Mesh exporter.

Layout of the 66 vanilla meshes with blendshapes (hairs, pl_face000, three
props; survey 2026-10-12):
- the pre-SF6 target record: LOD-local vertex start, vertex count, name
  index, channel count and a fourth u32 of unknown meaning (LOD0 mostly 255,
  higher LODs 0x7FFF);
- one body per LOD and one target per body, holding every channel (empty
  ones too, vanilla m_hair020) over one
  contiguous range of whole submeshes. Body 0: blendS (-1, 0, 0), blendSS all
  -1; higher bodies repeat the LOD0 channels in order with blendS (0, 0, 0),
  blendSS 0..n-1 and their own "_LOD<n>" names. Some meshes stop after LOD0;
- body typing selects the row: 0 = 4-byte packed 11/10/11 scaled by the
  symmetric target AABB (Wilds' code, zero 0x7FEFFBFF), 1 = 8-byte float16
  (x, y, z, 0). This exporter writes 0 unless its step would exceed
  PACKED_STEP_LIMIT;
- with normal recalculation the canonical tables sit at normalRecalcOffset in
  RE4's layout (LOD0 only); with normalRecalcOffset 0 each row is followed by
  the shape's int8 normal, as in Wilds' keep-normals layout;
- the payload follows the vertex elements, its start in the vertexElementSize
  / unkn1 shorts, bodies back to back, each shape-major.
"""

import numpy as np

from . import file_re_mesh as mesh_format
from . import mhwilds_blendshape as wilds


# The header qword differs per vanilla file (a stale pointer); this is
# pl_face000's.
BLEND_HEADER_HASH = 1385854529520
# Fourth target u32 as vanilla writes it most often.
LOD0_TARGET_TAG = 255
LOD_TARGET_TAG = 32767
# Largest packed-row step (metres) before the bodies switch to float16 rows.
PACKED_STEP_LIMIT = 0.0005


def _lod_submeshes(lod, parsed_to_mesh_info):
	"""(parsed, mesh_info, vertex_count) of every exported submesh, by start."""
	submeshes = [
		submesh
		for group in wilds._viscon_submeshes(lod, parsed_to_mesh_info)
		for submesh in group
	]
	return sorted(submeshes, key=lambda submesh: int(submesh[1].vertexStartIndex))


def _lod_channels(submeshes, names, keep_normals):
	"""Deltas (and normal words) of each channel over the LOD's vertex range."""
	lo = int(submeshes[0][1].vertexStartIndex)
	hi = max(int(info.vertexStartIndex) + count for _parsed, info, count in submeshes)
	base = None
	if keep_normals:
		base = np.zeros((hi - lo, 3), dtype=np.float32)
		for parsed_submesh, info, count in submeshes:
			start = int(info.vertexStartIndex) - lo
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
		channels.append((name, deltas, normals, mask))
	return lo, channels


def _build_body(lod, parsed_to_mesh_info, keep_normals, channel_order=None):
	"""One body: (body, rows, names) or None when the LOD has no usable keys.

	rows holds each channel's (deltas, normals or None) over the target range.
	LOD0 passes no order; higher LODs repeat LOD0's channels.
	"""
	submeshes = _lod_submeshes(lod, parsed_to_mesh_info)
	if not submeshes:
		return None
	names = wilds._shape_names(submeshes) if channel_order is None else list(channel_order)
	lo, channels = _lod_channels(submeshes, names, keep_normals)
	if not any(channel[3].any() for channel in channels):
		return None
	moving = np.zeros(len(channels[0][1]), dtype=bool)
	for channel in channels:
		moving |= channel[3]
	# The target covers whole submeshes, from the first to the last one that
	# moves (vanilla: the face submesh, or a hair's whole LOD).
	touched = [
		(int(info.vertexStartIndex) - lo, int(info.vertexStartIndex) - lo + count)
		for _parsed, info, count in submeshes
		if moving[int(info.vertexStartIndex) - lo:int(info.vertexStartIndex) - lo + count].any()
	]
	start = min(first for first, _end in touched)
	end = max(last for _first, last in touched)

	target = mesh_format.BlendTarget()
	# lo is the LOD's first vertex, so the start is already LOD-local.
	target.subMeshVertexStartIndex = start
	target.vertCount = end - start
	target.blendSSIndex = 0
	target.blendShapeNum = len(channels)

	body = mesh_format.BlendShapeData()
	body.targetCount = 1
	body.typing = 0
	body.unknFlag = 0
	body.padding1 = 0
	body.padding2 = 0
	body.blendTargetList = [target]
	aabb = wilds._symmetric_aabb([deltas[start:end] for _name, deltas, _normals, _mask in channels])
	body.aabbList = [aabb]

	rows = [
		(deltas[start:end], None if normals is None else normals[start:end])
		for _name, deltas, normals, _mask in channels
	]
	return body, rows, [channel[0] for channel in channels]


def _packed_step(aabb):
	"""Largest quantization step of the 11/10/11 rows under this AABB."""
	return max(
		abs(float(aabb.max.x)) / 1023.0,
		abs(float(aabb.max.y)) / 511.0,
		abs(float(aabb.max.z)) / 1023.0,
	)


def _pack_body(body, rows):
	"""Payload of one body: shape-major rows, each optionally + normal word."""
	payload = bytearray()
	for deltas, normals in rows:
		if body.typing == 1:
			words = np.zeros((len(deltas), 4), dtype="<f2")
			words[:, :3] = deltas
			words = words.reshape(-1).view("<u4").reshape((len(deltas), 2))
		else:
			words = np.frombuffer(
				wilds._pack_delta_rows(deltas, body.aabbList[0]), dtype="<u4"
			).reshape((-1, 1))
		if normals is not None:
			words = np.column_stack((words, wilds._pack_normal_rows(normals)))
		payload.extend(np.ascontiguousarray(words, dtype="<u4").tobytes())
	return bytes(payload)


def _lod_name(name, lod_index):
	"""Vanilla LOD names: blendShape1.front -> blendShape1_LOD1.front_LOD1."""
	prefix, dot, rest = name.partition(".")
	if dot:
		return f"{prefix}_LOD{lod_index}.{rest}_LOD{lod_index}"
	return f"{name}_LOD{lod_index}"


def build_mhrsb_blend_shape_plan(parsed_mesh, parsed_to_mesh_info):
	"""Build the blend bodies, their name list and the payload."""
	lods = wilds._list_or_empty(getattr(parsed_mesh, "mainMeshLODList", None))
	if not lods:
		return None
	keep_normals = wilds._keeps_normals(parsed_mesh=parsed_mesh)
	# Empty channels are kept (vanilla m_hair020 ships two): dropping one
	# would shift the index of every later channel.
	built = _build_body(lods[0], parsed_to_mesh_info, keep_normals)
	if built is None:
		return None
	bodies = [built]
	base_names = built[2]
	for lod_index, lod in enumerate(lods[1:], start=1):
		lod_names = set(wilds._shape_names(_lod_submeshes(lod, parsed_to_mesh_info)))
		if not lod_names:
			break
		if not lod_names <= set(base_names):
			print(
				f"MH Rise shape keys exported for LOD0-LOD{lod_index - 1} only; "
				f"LOD{lod_index} has shape keys LOD0 does not have: "
				+ ", ".join(sorted(lod_names - set(base_names)))
			)
			break
		built = _build_body(
			lod, parsed_to_mesh_info, keep_normals, channel_order=base_names
		)
		if built is None:
			break
		bodies.append(built)

	header = mesh_format.BlendShapeHeader()
	header.zero = 0
	header.hash = BLEND_HEADER_HASH
	header.blendShapeList = []
	remap_names = list(base_names)
	# float16 rows when the packed rows would lose more than PACKED_STEP_LIMIT
	# (vanilla uses them for long hair and the ice prop, deltas up to 1.9 m).
	typing = int(any(
		_packed_step(body.aabbList[0]) > PACKED_STEP_LIMIT
		for body, _rows, _names in bodies
	))
	payload = bytearray()
	for body_index, (body, rows, names) in enumerate(bodies):
		body.typing = typing
		target = body.blendTargetList[0]
		if body_index == 0:
			body.blendS = [-1, 0, 0]
			body.blendSSList = [-1] * len(names)
			target.deltaOffset = LOD0_TARGET_TAG
		else:
			# Higher LODs follow the LOD0 channel with the same index.
			body.blendS = [0, 0, 0]
			body.blendSSList = list(range(len(names)))
			target.deltaOffset = LOD_TARGET_TAG
			remap_names.extend(_lod_name(name, body_index) for name in names)
		payload.extend(_pack_body(body, rows))
		header.blendShapeList.append(body)
	header.count = len(header.blendShapeList)
	payload.extend(b"\x00" * mesh_format.getPaddingAmount(len(payload), 16))
	return {
		"header": header,
		"shapeRemapNames": remap_names,
		"payload": bytes(payload),
		"keepNormals": keep_normals,
		"lodBodies": len(bodies),
	}



def reserve_mhrsb_normal_recalc(re_mesh, current_offset, plan):
	"""Reserve RE4-layout tables unless the payload keeps normals."""
	if plan["keepNormals"]:
		re_mesh.fileHeader.normalRecalcOffset = 0
		return wilds._align16(current_offset)
	from .re4_blendshape import reserve_re4_normal_recalc
	return reserve_re4_normal_recalc(re_mesh, current_offset)


def finalize_mhrsb_export(re_mesh, plan):
	"""Write the payload start and, with recalculation, the canonical tables."""
	if plan["keepNormals"]:
		mesh_header = re_mesh.meshBufferHeader
		payload_start = int(re_mesh._re4BlendPayloadStart)
		mesh_header.vertexElementSize = wilds._signed_short(payload_start & 0xFFFF)
		mesh_header.unkn1 = wilds._signed_short((payload_start >> 16) & 0xFFFF)
		return
	from .re4_blendshape import finalize_re4_export
	finalize_re4_export(re_mesh)
