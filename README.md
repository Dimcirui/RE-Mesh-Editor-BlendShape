# RE-Mesh-Editor-BlendShape

A Blender add-on for importing and exporting RE Engine mesh and mdf2 files, focused on
**blendshape (shape key) support** for Monster Hunter Wilds, Monster Hunter Rise, Resident Evil and Onimusha: Way of the Sword.

> **AI-assisted project.** Most of the code and the file-format research in this fork were
> written with the help of an AI coding assistant (Anthropic's Claude), and reviewed, tested and
> directed by the maintainer. Format conclusions are checked against vanilla game files, but please
> report anything that looks wrong.

## Lineage

This repository is a fork of a fork:

1. **[RE Mesh Editor](https://github.com/NSACloud/RE-Mesh-Editor)** by **NSA Cloud**: the original
   add-on (mesh, mdf2, tex, chain and other RE Engine formats). Development there has ended.
2. **[RE-Mesh-Editor-MeshFixes](https://github.com/Ridog8/RE-Mesh-Editor-MeshFixes)** by **Ridog8**:
   the direct upstream. It improves custom weight precision, adds corner-attribute vertex splitting
   so exported normals are preserved, optional weight normalization, DD2 secondary weight and
   TU 3.2 fixes, extended weight packing (Wilds / Onimusha), and the first MH Wilds blendshape and
   Onimusha mesh support.
3. **RE-Mesh-Editor-BlendShape** (this repository), by **Dimcirui**.

All credit for the add-on itself goes to NSA Cloud and Ridog8; see their repositories for the full
feature list, documentation and credits.

## What this fork changes

**Blendshapes (shape keys)**

| Game | Import | Export | Notes |
|---|---|---|---|
| Monster Hunter Wilds | yes | yes |  |
| Monster Hunter Rise: Sunbreak | yes | yes | Not yet tested in game. |
| Resident Evil 4 Remake | yes | yes | Not yet tested in game. |
| Onimusha: Way of the Sword | yes | yes | Not yet tested in game. |
| Resident Evil Requiem (RE9) | yes | yes | Not yet tested in game. |

- Shape key names longer than Blender's 63-byte limit keep their full game name through import
  and export (game constraints bind channels by name).
- Which shape keys are exported:
  - **unchecked** (muted) keys are not exported;
  - **locked** keys are applied to the exported mesh at their current value and are not exported as
    shape keys;
  - keys whose name starts with `DUMMY_` are also not exported (use them for previews).
- Locked keys are baked with the authored normals turned by the surface's real turn. On meshes
  whose normals are not stylised this is what Blender shows; on stylised normals it avoids the
  swing Blender's custom normal decoding adds where a key shears the surface.
- Export modes for shape keys: *Recalculate Normals (in game)*, *Keep Normals (as in Blender)*
  (each key's normals as Blender shows them with the key applied) and *Keep Normals (surface turn)*,
  the default: the authored normals turn only with the real turn of the surface, so stylised
  normals keep their offset where a key shears the mesh. Both Keep Normals modes give the same
  result on meshes whose normals are not stylised (all vanilla meshes).
- **Static Normals** (Shape Keys panel, *RE Export: Static Normals* for the active key,
  *All* / *None* for every exported and locked key), for stylised faces whose shading is authored:
  - an exported key stores the authored normals instead of normals turned by its deformation
    (*Keep Normals* export), so the key does not change the shading;
  - a locked key is baked into the basis without changing its normals.

  Saved on the shape keys as `RE_StaticNormals` by key name; renaming a key in the UI keeps its
  flag. Off by default.

**Other changes**

- Triangulating quads and n-gons on export keeps custom normals as Blender shows them (stylised
  normals used to swing by up to ~90 degrees).
- Onimusha: Way of the Sword mdf2 / tex support.
- Faster export: vertex colors and UV layers are read in one pass instead of per corner
- Fixes ported from the [TrueShadow01](https://github.com/TrueShadow01/REME-RE-Engine-Blender-Addon)
  and [ZZtaii](https://github.com/ZZtaii/RE-Mesh-Editor) forks: atomic mesh writes and cleanup of
  temporary export objects, UV validation, a progress display, *Preserve Original Material Table*,
  and a test harness (`tests/`).
- Vertices without a usable bone weight are bound to the first weighted bone again (with a warning)
  instead of losing their skinning.
- `REME_FEATURES` in `__init__.py` lets other add-ons detect what this version supports.
- The built-in updater checks this repository.

## Installation

Download the repository as a zip (*Code > Download ZIP*) and install it in Blender via
*Edit > Preferences > Add-ons > Install from Disk*. Disable other RE Mesh Editor versions first:
they register the same operators.

## License

GPL, as the upstream projects (see `LICENSE.GPL`).
