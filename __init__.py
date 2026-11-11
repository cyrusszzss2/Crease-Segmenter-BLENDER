bl_info = {
    "name": "Crease Segmenter",
    "author": "Cyrleen",
    "version": (0, 3, 3),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > Segment",
    "description": "Split a mesh into geometric regions",
    "category": "Mesh",
}

import bpy
import math
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from mathutils import Vector


def build_face_adjacency(mesh):
    edge_faces = {}
    for polygon in mesh.polygons:
        for edge_key in polygon.edge_keys:
            key = tuple(sorted(edge_key))
            edge_faces.setdefault(key, []).append(polygon.index)

    adjacency = [set() for _ in mesh.polygons]
    for linked_faces in edge_faces.values():
        if len(linked_faces) < 2:
            continue
        for i, face_a in enumerate(linked_faces):
            for face_b in linked_faces[i + 1:]:
                adjacency[face_a].add(face_b)
                adjacency[face_b].add(face_a)
    return adjacency, edge_faces


def analyze_mesh(mesh):
    adjacency, edge_faces = build_face_adjacency(mesh)
    angles = []
    for linked_faces in edge_faces.values():
        if len(linked_faces) != 2:
            continue
        face_a, face_b = (mesh.polygons[index] for index in linked_faces)
        try:
            angles.append(math.degrees(face_a.normal.angle(face_b.normal)))
        except (ValueError, ZeroDivisionError):
            angles.append(0.0)

    visited = set()
    shell_count = 0
    for start in range(len(mesh.polygons)):
        if start in visited:
            continue
        shell_count += 1
        visited.add(start)
        stack = [start]
        while stack:
            current = stack.pop()
            for neighbor in adjacency[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)

    sorted_angles = sorted(angles)
    if sorted_angles:
        p50 = sorted_angles[int((len(sorted_angles) - 1) * 0.50)]
        p85 = sorted_angles[int((len(sorted_angles) - 1) * 0.85)]
        recommended = max(22.0, min(65.0, p85 * 0.78))
    else:
        p50 = 0.0
        p85 = 0.0
        recommended = 35.0

    recommended_min_faces = max(5, min(250, round(len(mesh.polygons) * 0.005)))

    if shell_count > 1:
        kind = "multi-shell"
        hint = f"{shell_count} bağlı olmayan parça bulundu; her biri ayrı bölge olacak."
    elif p85 >= 50.0:
        kind = "hard-surface"
        hint = "Keskin yüzey geçişleri yoğun; daha küçük bir açı önerildi."
    elif p50 >= 18.0:
        kind = "faceted"
        hint = "Yüzey belirgin biçimde köşeli; öneri küçük ayrıntıları birleştirmeye çalışır."
    else:
        kind = "smooth"
        hint = "Yüzey çoğunlukla yumuşak; aşırı parçalanmayı azaltmak için daha geniş eşik seçildi."

    dimensions = mesh.vertices
    if dimensions:
        xs = [vertex.co.x for vertex in dimensions]
        ys = [vertex.co.y for vertex in dimensions]
        zs = [vertex.co.z for vertex in dimensions]
        extent = Vector((max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)))
        size_text = f"{extent.x:.2f} × {extent.y:.2f} × {extent.z:.2f}"
    else:
        size_text = "0 × 0 × 0"

    return {
        "faces": len(mesh.polygons),
        "shells": shell_count,
        "p85_angle": p85,
        "recommended_angle": recommended,
        "recommended_min_faces": recommended_min_faces,
        "kind": kind,
        "hint": hint,
        "size": size_text,
    }


def find_regions(mesh, threshold_degrees, minimum_faces):
    adjacency, _edge_faces = build_face_adjacency(mesh)
    if not mesh.polygons:
        return []

    limit = math.radians(threshold_degrees)
    visited = set()
    raw_regions = []
    for start in range(len(mesh.polygons)):
        if start in visited:
            continue
        visited.add(start)
        stack = [start]
        region = []
        while stack:
            face_index = stack.pop()
            region.append(face_index)
            face = mesh.polygons[face_index]
            for neighbor_index in adjacency[face_index]:
                if neighbor_index in visited:
                    continue
                neighbor = mesh.polygons[neighbor_index]
                try:
                    angle = face.normal.angle(neighbor.normal)
                except (ValueError, ZeroDivisionError):
                    angle = 0.0
                if angle <= limit:
                    visited.add(neighbor_index)
                    stack.append(neighbor_index)
        raw_regions.append(set(region))

    groups = {index: faces for index, faces in enumerate(raw_regions)}
    face_group = {}
    for group_id, faces in groups.items():
        for face_index in faces:
            face_group[face_index] = group_id

    for group_id in sorted(list(groups), key=lambda item: len(groups[item])):
        if group_id not in groups or len(groups[group_id]) >= minimum_faces:
            continue
        boundary_counts = {}
        for face_index in groups[group_id]:
            for neighbor_index in adjacency[face_index]:
                neighbor_group = face_group[neighbor_index]
                if neighbor_group != group_id and neighbor_group in groups:
                    boundary_counts[neighbor_group] = boundary_counts.get(neighbor_group, 0) + 1
        if not boundary_counts:
            continue
        target = max(
            boundary_counts,
            key=lambda candidate: (boundary_counts[candidate], len(groups[candidate])),
        )
        for face_index in groups[group_id]:
            face_group[face_index] = target
        groups[target].update(groups[group_id])
        del groups[group_id]

    final_groups = sorted(groups.values(), key=lambda faces: min(faces))
    return [sorted(faces) for faces in final_groups]


def make_region_object(source_obj, source_mesh, region_faces, region_index, collection):
    used_vertices = sorted({vertex for face_index in region_faces
                            for vertex in source_mesh.polygons[face_index].vertices})
    vertex_map = {source_index: target_index
                  for target_index, source_index in enumerate(used_vertices)}
    source_coordinates = [Vector(source_mesh.vertices[index].co) for index in used_vertices]
    bounds_min = Vector((
        min(co.x for co in source_coordinates),
        min(co.y for co in source_coordinates),
        min(co.z for co in source_coordinates),
    ))
    bounds_max = Vector((
        max(co.x for co in source_coordinates),
        max(co.y for co in source_coordinates),
        max(co.z for co in source_coordinates),
    ))
    region_center = (bounds_min + bounds_max) * 0.5
    vertices = [(co - region_center)[:] for co in source_coordinates]
    source_polygons = [source_mesh.polygons[index] for index in region_faces]
    faces = [[vertex_map[index] for index in polygon.vertices]
             for polygon in source_polygons]

    new_mesh = bpy.data.meshes.new(f"{source_obj.data.name}_Region_{region_index:03d}")
    new_mesh.from_pydata(vertices, [], faces)
    new_mesh.update()

    source_slots = source_obj.material_slots
    slot_count = max(len(source_mesh.materials), len(source_slots))
    used_material_indices = sorted({
        min(max(polygon.material_index, 0), slot_count - 1)
        for polygon in source_polygons
    }) if slot_count else []
    material_index_map = {}
    for source_index in used_material_indices:
        material_index_map[source_index] = len(new_mesh.materials)
        if source_index < len(source_slots):
            material = source_slots[source_index].material
        else:
            material = source_mesh.materials[source_index]
        new_mesh.materials.append(material)

    for target_polygon, source_polygon in zip(new_mesh.polygons, source_polygons):
        if used_material_indices:
            source_index = min(max(source_polygon.material_index, 0), slot_count - 1)
            target_polygon.material_index = material_index_map[source_index]
        target_polygon.use_smooth = source_polygon.use_smooth

    for source_uv in source_mesh.uv_layers:
        target_uv = new_mesh.uv_layers.new(name=source_uv.name)
        target_loop_index = 0
        for source_polygon in source_polygons:
            for source_loop_index in source_polygon.loop_indices:
                target_uv.data[target_loop_index].uv = source_uv.data[source_loop_index].uv
                target_loop_index += 1

    source_loop_indices = [
        loop_index
        for source_polygon in source_polygons
        for loop_index in source_polygon.loop_indices
    ]
    for source_color in source_mesh.color_attributes:
        if source_color.domain not in {"POINT", "CORNER"}:
            continue
        target_color = new_mesh.color_attributes.new(
            name=source_color.name,
            type=source_color.data_type,
            domain=source_color.domain,
        )
        if source_color.domain == "POINT":
            for target_index, source_index in enumerate(used_vertices):
                target_color.data[target_index].color = source_color.data[source_index].color
        else:
            for target_index, source_index in enumerate(source_loop_indices):
                target_color.data[target_index].color = source_color.data[source_index].color

    segment_attribute = new_mesh.attributes.new(
        name="crease_segment_id", type="INT", domain="FACE"
    )
    for item in segment_attribute.data:
        item.value = region_index

    new_obj = bpy.data.objects.new(
        f"{source_obj.name}_Segment_{region_index:03d}", new_mesh
    )
    collection.objects.link(new_obj)
    new_obj.matrix_world = source_obj.matrix_world.copy()
    new_obj.matrix_world.translation = source_obj.matrix_world @ region_center
    new_obj.color = (
        0.25 + ((region_index * 37) % 70) / 100.0,
        0.25 + ((region_index * 59) % 70) / 100.0,
        0.25 + ((region_index * 83) % 70) / 100.0,
        1.0,
    )
    new_obj["crease_segment_id"] = region_index
    return new_obj


def analysis_text(info):
    return (
        f"Tahmin: {info['kind']} mesh · {info['faces']:,} yüz · "
        f"{info['shells']} bağlı bölge · Boyut {info['size']}\n"
        f"Öneri: {info['recommended_angle']:.0f}° açı, "
        f"{info['recommended_min_faces']} yüz minimum · {info['hint']}"
    )


class MESH_OT_cs_analyze(bpy.types.Operator):
    bl_idname = "mesh.cs_analyze"
    bl_label = "Analyze Model"
    bl_description = "Analyze geometry locally; no model data is uploaded"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == "MESH"

    def execute(self, context):
        obj = context.active_object
        depsgraph = context.evaluated_depsgraph_get()
        evaluated_obj = obj.evaluated_get(depsgraph)
        evaluated_mesh = evaluated_obj.to_mesh(
            preserve_all_data_layers=True, depsgraph=depsgraph
        )
        try:
            info = analyze_mesh(evaluated_mesh)
        finally:
            evaluated_obj.to_mesh_clear()
        scene = context.scene
        scene.cs_analysis_text = analysis_text(info)
        scene.cs_analysis_object = obj.name
        scene.cs_crease_angle = math.radians(info["recommended_angle"])
        scene.cs_min_faces = info["recommended_min_faces"]
        scene.cs_analysis_ready = True
        self.report({"INFO"}, f"Local analysis: {info['kind']}; suggested {info['recommended_angle']:.0f}°")
        return {"FINISHED"}


class MESH_OT_crease_segment(bpy.types.Operator):
    bl_idname = "mesh.crease_segment"
    bl_label = "Segment Model"
    bl_description = "Split the evaluated mesh into geometry-based regions"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == "MESH"

    def execute(self, context):
        source_obj = context.active_object
        scene = context.scene
        if not scene.cs_analysis_ready or scene.cs_analysis_object != source_obj.name:
            self.report({"WARNING"}, "Analyze the selected model before segmenting")
            return {"CANCELLED"}

        depsgraph = context.evaluated_depsgraph_get()
        evaluated_obj = source_obj.evaluated_get(depsgraph)
        evaluated_mesh = evaluated_obj.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
        created = []
        output_collection = None
        replace_source = scene.cs_output_mode == "REPLACE"
        succeeded = False
        try:
            info = analyze_mesh(evaluated_mesh)
            if scene.cs_segmentation_mode == "SMART":
                angle = info["recommended_angle"]
            elif scene.cs_segmentation_mode == "CREASES":
                angle = math.degrees(scene.cs_crease_angle)
            else:
                angle = 180.0

            regions = find_regions(evaluated_mesh, angle, scene.cs_min_faces)
            if not regions:
                self.report({"WARNING"}, "The selected mesh has no faces")
                return {"CANCELLED"}

            output_collection = bpy.data.collections.new(f"{source_obj.name}_Segments")
            output_collection["crease_segment_source"] = source_obj.name
            scene.collection.children.link(output_collection)
            for region_index, region in enumerate(regions, start=1):
                created.append(
                    make_region_object(
                        source_obj, evaluated_mesh, region, region_index, output_collection
                    )
                )

            if scene.cs_output_mode == "NEW_BESIDE":
                corners = [source_obj.matrix_world @ Vector(corner) for corner in source_obj.bound_box]
                x_min = min(point.x for point in corners)
                x_max = max(point.x for point in corners)
                width = max(x_max - x_min, max(source_obj.dimensions) * 0.25, 0.25)
                offset = width * 1.15
                for obj in created:
                    obj.matrix_world.translation += Vector((offset, 0.0, 0.0))

            bpy.ops.object.select_all(action="DESELECT")
            for obj in created:
                obj.select_set(True)
            context.view_layer.objects.active = created[0]
            scene.cs_analysis_ready = False
            output = "beside the original" if scene.cs_output_mode == "NEW_BESIDE" else "replaced the original"
            self.report({"INFO"}, f"Created {len(created)} segments; {output}")
            succeeded = True
            return {"FINISHED"}
        except Exception as error:
            for obj in created:
                mesh = obj.data
                bpy.data.objects.remove(obj, do_unlink=True)
                if mesh.users == 0:
                    bpy.data.meshes.remove(mesh)
            if output_collection is not None:
                bpy.data.collections.remove(output_collection, do_unlink=True)
            self.report({"ERROR"}, f"Could not create segments: {error}")
            return {"CANCELLED"}
        finally:
            evaluated_obj.to_mesh_clear()
            if succeeded and replace_source:
                bpy.data.objects.remove(source_obj, do_unlink=True)


class VIEW3D_PT_crease_segmenter(bpy.types.Panel):
    bl_label = "Crease Segmenter"
    bl_idname = "VIEW3D_PT_crease_segmenter"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Segment"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        active = context.active_object
        is_mesh = active is not None and active.type == "MESH"

        layout.label(text="Local geometry analysis", icon="OUTLINER_OB_MESH")
        analyze_row = layout.row()
        analyze_row.enabled = is_mesh
        analyze_row.operator(
            "mesh.cs_analyze",
            text="Analyze Selected Model" if is_mesh else "Analyze Model",
            icon="VIEWZOOM",
        )

        analyzed = (
            is_mesh
            and scene.cs_analysis_ready
            and scene.cs_analysis_object == active.name
        )
        if not is_mesh:
            warning = layout.box()
            warning.alert = True
            warning.label(text="Select a mesh object first.", icon="ERROR")
        elif analyzed and scene.cs_analysis_text:
            box = layout.box()
            for line in scene.cs_analysis_text.split("\n"):
                box.label(text=line)
        else:
            layout.label(text="Analyze the selected model to refresh its recommendations.", icon="INFO")

        layout.separator()
        layout.label(text="Segmentation strategy")
        layout.prop(scene, "cs_segmentation_mode", text="")
        if scene.cs_segmentation_mode == "CREASES":
            layout.prop(scene, "cs_crease_angle")
        elif scene.cs_segmentation_mode == "SMART":
            layout.label(text="Uses the locally suggested crease angle.", icon="INFO")
        else:
            layout.label(text="Only splits already disconnected shells.", icon="INFO")
        layout.prop(scene, "cs_min_faces")

        layout.separator()
        layout.label(text="Output")
        layout.prop(scene, "cs_output_mode", text="")
        if scene.cs_output_mode == "NEW_BESIDE":
            layout.label(text="Creates the result to the right of the source.")
        else:
            layout.label(text="Removes the source after creating its segments.", icon="ERROR")

        row = layout.row()
        row.enabled = analyzed
        row.operator("mesh.crease_segment", icon="MOD_EXPLODE")
        if not analyzed:
            layout.label(text="Analyze the selected mesh first.", icon="INFO")


CLASSES = (
    MESH_OT_cs_analyze,
    MESH_OT_crease_segment,
    VIEW3D_PT_crease_segmenter,
)


def register():
    bpy.types.Scene.cs_crease_angle = FloatProperty(
        name="Crease Angle",
        description="Faces with a larger normal change become different regions",
        min=math.radians(1.0),
        max=math.radians(179.0),
        default=math.radians(35.0),
        subtype="ANGLE",
        unit="ROTATION",
    )
    bpy.types.Scene.cs_min_faces = IntProperty(
        name="Minimum Region Faces",
        description="Merge smaller regions into the neighbor with the longest shared boundary",
        min=1,
        max=1000000,
        default=20,
    )
    bpy.types.Scene.cs_segmentation_mode = EnumProperty(
        name="Segmentation Strategy",
        items=(
            ("SMART", "Smart Analyze", "Use the angle recommended by local geometry analysis"),
            ("CREASES", "Crease Angle", "Use the manually selected face-normal threshold"),
            ("LOOSE", "Disconnected Parts", "Split only shells already disconnected in the mesh"),
        ),
        default="SMART",
    )
    bpy.types.Scene.cs_output_mode = EnumProperty(
        name="Output",
        items=(
            ("NEW_BESIDE", "New Model Beside Original", "Keep the source and place result to its right"),
            ("REPLACE", "Replace Original", "Remove the source after the segmented result is created"),
        ),
        default="NEW_BESIDE",
    )
    bpy.types.Scene.cs_analysis_text = StringProperty(name="Analysis", default="")
    bpy.types.Scene.cs_analysis_object = StringProperty(name="Analyzed Object", default="")
    bpy.types.Scene.cs_analysis_ready = BoolProperty(name="Analysis Ready", default=False)
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.cs_analysis_ready
    del bpy.types.Scene.cs_analysis_object
    del bpy.types.Scene.cs_analysis_text
    del bpy.types.Scene.cs_output_mode
    del bpy.types.Scene.cs_segmentation_mode
    del bpy.types.Scene.cs_crease_angle
    del bpy.types.Scene.cs_min_faces


if __name__ == "__main__":
    register()
