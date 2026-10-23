# Scene interface for other tools

This page lists the custom properties RE Mesh Editor writes on the
collections and objects it creates, so that other add-ons can find mesh,
MDF and FBXSkel data in a scene without depending on this add-on's code.
The names below are a stable interface: renaming one or changing its
meaning is recorded in the change log at the end of this page.

RE Mesh Editor has no in-memory export API (no `wd_api` module). Tools that
need the skeleton read the Blender armature objects directly.

## Identification properties

| Property | Written on | Value |
|---|---|---|
| `~TYPE` | Mesh root collection | `RE_MESH_COLLECTION` |
| `~TYPE` | MDF root collection | `RE_MDF_COLLECTION` |
| `~TYPE` | Armature object from an FBXSkel import | `RE_FBXSKEL_ARMATURE` |
| `~ASSETPATH` | Mesh root collection, MDF root collection, FBXSkel armature object | Game path of the imported file (see below) |

`~TYPE` is written when the collection or object is created and is not
changed afterwards. It is written by every path that creates one:

- Mesh collection: mesh import (with Create Collections on), the
  Create Mesh Collection operator, and the Mod Workspace bake when it
  creates a new collection.
- MDF collection: MDF import (including the MDF loaded alongside a mesh),
  the Create MDF Collection operator, and the Mod Workspace bake when it
  creates a new collection.
- FBXSkel armature: FBXSkel import.

Mesh import with Create Collections off puts the objects straight into the
scene collection, so there is no root collection to tag.

Scenes made before these tags existed can be recognised by name: a mesh
collection name ends in `.mesh`, an MDF collection name ends in `.mdf2`,
and an FBXSkel armature has `~ASSETPATH` ending in `.fbxskel` (its object
name is the file name without the version number, e.g. `Perlica.fbxskel`).

### `~ASSETPATH`

The path of the imported file inside the game's `natives/<platform>/`
folder, with `/` separators and the version extension removed, e.g.
`Art/Model/Character/ch03/039/001/2/ch03_039_0012.mesh` or
`BoneSystem/Perlica.fbxskel`. It is written on import only, and only when
the file was imported from inside a `natives` folder. Collections made with
the Create operators, and files imported from anywhere else, have no
`~ASSETPATH`. Batch export uses it to pick the export path.

## Mesh collection layout

```
<name>.mesh                     collection, ~TYPE = RE_MESH_COLLECTION
├── <name> Armature             ARMATURE object (optional, at most one)
├── Main Mesh LOD0 - <name>.mesh  collection, one per LOD
│   └── LOD_<n>_Group_<g>_Sub_<s>__<material>   MESH objects
├── Main Mesh LOD1 - ...
└── <name>.mesh Bounding Boxes  collection, ~TYPE = RE_MESH_BOUNDING_BOX_COLLECTION
```

When the mesh is imported together with its MDF, both root collections sit
under a parent collection named after the file without `.mesh`.

**Finding the armature.** The armature of a mesh collection is the
ARMATURE object linked directly to the root collection (its `objects`, not
child collections). The exporter treats more than one as an error, so
there is either none or exactly one. When a mesh is imported with Merge
Armature onto an existing armature, no new armature is created and the
existing one stays in its own collection; in that case the root collection
has no armature of its own.

The mesh objects are deformed by an Armature modifier pointing at that
armature. Imported bones whose name was a hash keep the readable name in
the edit bone custom property `unhashedBoneName`.

Other properties on the mesh root collection (all written on import):

| Property | Meaning |
|---|---|
| `LODGroupNameHash` | `lodGroupNameHash` from the mesh file header, as a decimal string |
| `REOriginalMaterialTableV1` | JSON list of the file's material names in their original slot order |

LOD collections carry `LOD Distance` (the LOD switch distance from the
file). LOD collections and the `LOD_<n>_` name prefix exist only when all
LODs are imported; otherwise the mesh objects sit directly in the root
collection. Collect mesh objects with `all_objects` to cover both cases.

## MDF collection layout

```
<name>.mdf2                     collection, ~TYPE = RE_MDF_COLLECTION
└── Material NN (<name>)        EMPTY objects, ~TYPE = RE_MDF_MATERIAL
```

Each material object holds its data in the `re_mdf_material` property
group (`materialName`, `mmtrPath`, `shaderType`, `propertyList_items` for
parameters, `textureBindingList_items` for textures).

## FBXSkel armature

FBXSkel import creates one ARMATURE object named after the file without
its version extension (e.g. `Perlica.fbxskel`), linked to the scene
collection, with `~TYPE = RE_FBXSKEL_ARMATURE` and `~ASSETPATH`. It is not
placed inside a mesh collection.

Link Armature Bones (FBXSkel tools) adds a Copy Transforms constraint named
`BoneLinkage` to each same-named pose bone of the chosen armatures, with
the FBXSkel armature as the target, so mesh armatures follow its pose.

## Change log

- 2026-10-23: first version. Added `~TYPE = RE_FBXSKEL_ARMATURE` on FBXSkel
  import, and `~TYPE` on collections created by the Mod Workspace bake.
