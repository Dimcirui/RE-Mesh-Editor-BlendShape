"""Fixture-neutral regressions for the Ridog8 weight and normal format fixes.

Ported from the ZZtaii fork (tests/test_meshfix_weight_codec.py).

Run with Python + NumPy; no Blender process or retail meshes are needed.
"""
import importlib
from io import BytesIO
from pathlib import Path
import sys
import types
import unittest

import numpy as np


REPO = Path(__file__).resolve().parents[1]
PACKAGE = "re_mesh_codec_tests"
# Load the format modules without running the Blender addon's registration.
package = types.ModuleType(PACKAGE)
package.__path__ = [str(REPO)]
sys.modules[PACKAGE] = package
codec = importlib.import_module(PACKAGE + ".modules.mesh.file_re_mesh")
parse = importlib.import_module(PACKAGE + ".modules.mesh.re_mesh_parse")


class WeightCodecChecks(unittest.TestCase):
	def test_six_weight_indices_roundtrip_at_ten_bit_boundaries(self):
		indices = np.array([[0, 1, 255, 256, 511, 1023, 0, 0],
							[1023, 512, 12, 35, 1000, 999, 0, 0]], dtype="<H")
		weights = np.array([[.5, .2, .1, .1, .05, .05, 0, 0]] * 2)
		output = BytesIO()
		codec.WriteToWeightBuffer(output, weights, indices, True)
		decoded_indices, decoded_weights = parse.ReadWeightBuffer(
			output.getvalue(), {"SixWeightCompressed"})
		np.testing.assert_array_equal(decoded_indices, indices)
		self.assertTrue(np.all(np.rint(np.asarray(decoded_weights) * 255).sum(axis=1) == 255))
		packed = np.frombuffer(codec.PackSixWeightIndices(indices).tobytes(), dtype="<u8")
		self.assertTrue(np.all((packed >> np.uint64(30)) & 3 == 0))
		self.assertTrue(np.all((packed >> np.uint64(62)) & 3 == 0))

	def test_normalization_is_explicit_and_zero_rows_stay_zero(self):
		weights = [[.25, .25, 0, 0, 0, 0, 0, 0], [0] * 8]
		normalized = codec.QuantizeWeightArrayToBytes(weights, True)
		raw = codec.QuantizeWeightArrayToBytes(weights, False)
		np.testing.assert_array_equal(normalized[0], [128, 127, 0, 0, 0, 0, 0, 0])
		np.testing.assert_array_equal(raw[0], [64, 64, 0, 0, 0, 0, 0, 0])
		self.assertEqual(normalized[1].sum(), 0)
		self.assertEqual(raw[1].sum(), 0)

	def test_weight_writer_binds_empty_rows_to_slot_zero(self):
		# NSA behavior: an unweighted vertex gets 100% on slot 0 instead of an all-zero row
		weights = np.array([[.25, .25, 0, 0, 0, 0, 0, 0], [0] * 8])
		indices = np.array([[3, 4, 0, 0, 0, 0, 0, 0], [0] * 8], dtype="<H")
		for normalizeWeights in (True, False):
			with self.subTest(normalizeWeights=normalizeWeights):
				output = BytesIO()
				codec.WriteToWeightBuffer(output, weights, indices, False, normalizeWeights)
				rows = np.frombuffer(output.getvalue(), dtype=np.uint8).reshape((2, 16))
				np.testing.assert_array_equal(rows[1, 8:], [255, 0, 0, 0, 0, 0, 0, 0])
		output = BytesIO()
		codec.WriteToWeightBuffer(output, weights, indices, False, True, fillEmptyRows=False)
		rows = np.frombuffer(output.getvalue(), dtype=np.uint8).reshape((2, 16))
		self.assertEqual(int(rows[1, 8:].sum()), 0)

	def test_wilds_and_onimusha_extended_eight_four_layout(self):
		primary_indices = np.array([[1, 2, 3, 4, 5, 6, 0, 0]], dtype="<H")
		extra_indices = np.array([[7, 8, 9, 10, 11, 12, 0, 0]], dtype="<H")
		primary_weights = np.array([[.01, .02, .03, .04, .05, .06, 0, 0]])
		extra_weights = np.array([[.07, .08, .09, .10, .11, .12, 0, 0]])
		semantic = np.hstack((primary_weights[:, :6], extra_weights[:, :6]))
		expected = np.rint(semantic * 255).astype(np.uint8)
		for version in (codec.VERSION_MHWILDS, codec.VERSION_ONIWOTS):
			with self.subTest(version=version):
				primary, extra = BytesIO(), BytesIO()
				codec.WriteToWeightBufferExtended(
					primary, primary_weights, primary_indices, extra,
					extra_weights, extra_indices, True, False, version)
				physical_primary = np.frombuffer(primary.getvalue(), dtype=np.uint8).reshape(-1, 8)
				physical_extra = np.frombuffer(extra.getvalue(), dtype=np.uint8).reshape(-1, 8)
				np.testing.assert_array_equal(physical_primary[1], expected[0, :8])
				np.testing.assert_array_equal(physical_extra[1], list(expected[0, 8:12]) + [0] * 4)
				packed = int.from_bytes(primary.getvalue()[:8], "little")
				self.assertEqual((packed >> 30) & 3, 3)
				self.assertEqual((packed >> 62) & 3, 3)

				elements = []
				position = codec.VertexElementStruct()
				position.typing, position.stride, position.posStartOffset = 0, 12, 0
				elements.append(position)
				for kind, offset in ((4, 12), (7, 28)):
					element = codec.VertexElementStruct()
					element.typing, element.stride, element.posStartOffset = kind, 16, offset
					elements.append(element)
				vertex_buffer = np.zeros((1, 3), dtype="<f4").tobytes() + primary.getvalue() + extra.getvalue()
				decoded = parse.ReadVertexElementBuffers(
					elements, vertex_buffer, {"SixWeightCompressed", "EightFourExtendedWeight"})
				np.testing.assert_array_equal(decoded["Weight"][0], primary_indices)
				np.testing.assert_array_equal(decoded["ExtraWeight"][0], extra_indices)
				np.testing.assert_array_equal(np.rint(np.asarray(decoded["Weight"][1]) * 255),
											  [list(expected[0, :6]) + [0, 0]])
				np.testing.assert_array_equal(np.rint(np.asarray(decoded["ExtraWeight"][1]) * 255),
											  [list(expected[0, 6:12]) + [0, 0]])

	def test_wilds_normal_group_byte_mapping_and_other_games(self):
		groups = [0, 1, 127, 128, 129, 255]
		packed = bytes(value for group in groups for value in (0, 0, 127, group, 127, 0, 0, 127))
		normals, tangents, decoded = parse.ReadNorTanBuffer(packed, {"MHWILDS"})
		self.assertEqual(decoded, [0, 1, 127, 0, 128, 254])
		self.assertEqual(normals, [[0.0, 0.0, 1.0]] * len(groups))
		self.assertEqual(tangents, [[1.0, 0.0, 0.0]] * len(groups))
		self.assertEqual(parse.ReadNorTanBuffer(packed, set()), (normals, tangents))

	def test_new_game_versions_and_blendshape_dispatch(self):
		self.assertEqual(codec.meshFileVersionToGameNameDict[260209350], "ONIWOTS")
		self.assertEqual(codec.meshFileVersionToGameNameDict[260421070], "DD2")
		self.assertEqual(codec.meshFileVersionToInternalVersionDict[260421070], 251205828)
		self.assertTrue(parse._mesh_supports_blend_shapes(types.SimpleNamespace(meshVersion=241111606)))
		self.assertFalse(parse._mesh_supports_blend_shapes(types.SimpleNamespace(meshVersion=230110883)))


if __name__ == "__main__":
	unittest.main()
