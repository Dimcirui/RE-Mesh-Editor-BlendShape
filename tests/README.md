# Tests

All tests use synthetic data only; no retail game files are needed. Run them
from the addon folder.

## Pure Python (needs NumPy, no Blender)

```
python tests/test_meshfix_weight_codec.py
```

Weight buffer packing (six-weight, Wilds/Onimusha 8+4 extended), weight
normalization, the Wilds normal-group byte mapping and game version tables.

## Blender (background mode)

```
"<path to>/blender.exe" --background --factory-startup --python-exit-code 1 --python tests/test_meshfix_blender.py
"<path to>/blender.exe" --background --factory-startup --python-exit-code 1 --python tests/test_export_reliability_blender.py
```

- `test_meshfix_blender.py`: rotated custom normals on import, DD2 secondary
  weight bank import/export, Limit Total with DD2 banks and paint masks, UV
  and custom-normal seams kept by corner splitting, Wilds shape key export
  (Recalculate Normals and KEEPNORMALS modes, `DUMMY_` keys skipped), RE4
  shape key export (float16 rows, LOD0 normal-recalc tables, reimport),
  Onimusha WotS shape key export (Recalculate Normals and KEEPNORMALS), shape
  key names longer than Blender's 63 bytes kept through import and export.
- `test_export_reliability_blender.py`: export cleanup on success and failure,
  atomic writes, operator failure reports, multi-file import, batch export
  per-item options, UV validation (exported maps only, reference maps,
  non-finite/out-of-range UVs, UV-removing modifiers, Auto Solve on UV1),
  progress tracking in background mode and Preserve Original Material Table.

`--factory-startup` keeps your own preferences and add-ons out of the run, and
nothing is saved. The tests enable the add-on from this folder, so run them
with the folder still named as installed. A non-zero exit code means a check
failed; the console output lists each `PASS`/`FAIL`.

The `tests` folder is not a Python package and is never imported by the
add-on, so it does not affect loading or the updater.
