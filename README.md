# Crease Segmenter 0.3.3

Crease Segmenter splits Blender meshes along surface creases or separates mesh parts that are already disconnected. Analysis and segmentation run locally; no external AI model is used.

## Features

- **Smart Analyze:** Examines the mesh and suggests a segmentation angle and minimum region size.
- **Crease Angle:** Separates sharp surface transitions using the selected angle.
- **Disconnected Parts:** Separates mesh parts that are already disconnected from one another.
- Creates the results in a `<Model>_Segments` collection, separate from the source object.
- Moves each segment's origin to its own center while keeping the geometry in place in the scene.
- Can place the results beside the source model or replace the source object.

## Installation

1. Download `CreaseSegmenter-0.3.3.zip`.
2. In Blender, select **Edit → Preferences → Get Extensions → ⋁ → Install from Disk**.
3. Choose the ZIP file and enable the add-on.
4. In the 3D Viewport, press `N` and open the **Segment** tab.

## Usage

1. Select a mesh and click **Analyze Selected Model**.
2. Review the suggestion and choose a segmentation mode.
3. Choose **New Model Beside Original** or **Replace Original** as the output option.
4. Click **Segment Model**.

Run the analysis again after selecting a different mesh. If no mesh is selected, the add-on will ask you to select one.

## Analysis and Settings

Smart Analyze measures the angles between adjacent face normals and suggests an angle based on the 85th percentile. The minimum region size is set to 0.5% of the mesh's face count, clamped to a range of 5–250 faces. These are local geometry heuristics; they are not a learned AI system that recognizes an object's meaning.

Higher cut angles generally produce fewer regions. The minimum region size determines when small regions are merged into neighboring ones.

## Limitations

UVs, color attributes, and used materials are transferred. Shape keys, vertex groups, armature connections, and modifiers are not transferred to the segments. Results depend on the mesh topology and the selected angle.
