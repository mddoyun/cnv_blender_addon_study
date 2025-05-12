import bpy
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.shape
import ifcopenshell.util.selector
import numpy as np
import multiprocessing
import math

bl_info = {
    "name": "cnv_blender_addon_study",
    "author": "mddoyun",
    "description": "This is the test of mine",
    "blender": (4, 0, 0),
    "version": (1, 0, 0),
    "location": "View3D > Sidebar > CNV Test Tab",
}

# --- 프로퍼티 정의 ---
class CNVProperties(bpy.types.PropertyGroup):
    ray_count_input: bpy.props.IntProperty(name="RAY 개수")
    ray_length_input: bpy.props.FloatProperty(name="RAY 거리(m)")
    last_cross_count: bpy.props.IntProperty(name="간섭 수", default=0)

    checklist1_result: bpy.props.StringProperty(name="결과1", default="대기 중")
    checklist2_result: bpy.props.StringProperty(name="결과2", default="대기 중")

# --- 기존 Operator ---
class Operator_cnv_test(bpy.types.Operator):
    bl_idname = "object.add_cube"
    bl_label = "Add Cube"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT"

    def execute(self, context):
        ray_count_input_value = context.scene.cnv_props.ray_count_input
        ray_length_input_value = context.scene.cnv_props.ray_length_input
        ifc_file = ifcopenshell.open(bpy.data.scenes["Scene"].BIMProperties.ifc_file)
        list_of_target = ifcopenshell.util.selector.filter_elements(
            ifc_file, "My_Data.cnv_class=target"
        )

        RAY_COUNT = ray_count_input_value
        RAY_LENGTH = ray_length_input_value

        settings = ifcopenshell.geom.settings()
        settings.set(settings.USE_WORLD_COORDS, True)

        tree = ifcopenshell.geom.tree()
        iterator = ifcopenshell.geom.iterator(
            settings, ifc_file, multiprocessing.cpu_count()
        )
        if iterator.initialize():
            while True:
                tree.add_element(iterator.get_native())
                if not iterator.next():
                    break

        i = 1
        for element in list_of_target:
            shape = ifcopenshell.geom.create_shape(settings, element)
            geometry = shape.geometry
            matrix = ifcopenshell.util.shape.get_shape_matrix(shape)
            location = matrix[:, 3][0:3]
            location_tuple = tuple(map(float, location))

            cross_count = 0
            for j in range(RAY_COUNT):
                angle_rad = math.radians(j * (360 / RAY_COUNT))
                direction = (math.cos(angle_rad), math.sin(angle_rad), 0.1)
                norm = math.sqrt(direction[0] ** 2 + direction[1] ** 2)
                direction = (direction[0] / norm, direction[1] / norm, 0.1)
                results = tree.select_ray(location_tuple, direction, length=RAY_LENGTH)
                if results:
                    cross_count += 1

            context.scene.cnv_props.last_cross_count = cross_count
        return {"FINISHED"}

# --- 체크리스트1 Operator ---
class Operator_checklist1(bpy.types.Operator):
    bl_idname = "object.checklist1"
    bl_label = "확인 (체크리스트1)"

    def execute(self, context):
        context.scene.cnv_props.checklist1_result = "체크리스트1 결과 OK"
        return {"FINISHED"}

# --- 체크리스트2 Operator ---
class Operator_checklist2(bpy.types.Operator):
    bl_idname = "object.checklist2"
    bl_label = "확인 (체크리스트2)"

    def execute(self, context):
        context.scene.cnv_props.checklist2_result = "체크리스트2 결과 OK"
        return {"FINISHED"}

# --- 기존 CNV UI 패널 ---
class Panel_view3d_ui_cnv_test(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CNV Test"
    bl_label = "CNV Test"

    def draw(self, context):
        layout = self.layout
        cnv_props = context.scene.cnv_props

        row = layout.row(align=True)
        row.prop(cnv_props, "ray_count_input")
        row.prop(cnv_props, "ray_length_input")

        layout.operator("object.add_cube")
        layout.label(text=f"간섭 수: {cnv_props.last_cross_count}")

# --- 체크리스트1 패널 ---
class Panel_checklist1(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "객체정보기반"
    bl_label = "체크리스트1"

    def draw(self, context):
        layout = self.layout
        layout.operator("object.checklist1")
        layout.label(text=f"결과: {context.scene.cnv_props.checklist1_result}")

# --- 체크리스트2 패널 ---
class Panel_checklist2(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "객체정보기반"
    bl_label = "체크리스트2"

    def draw(self, context):
        layout = self.layout
        layout.operator("object.checklist2")
        layout.label(text=f"결과: {context.scene.cnv_props.checklist2_result}")

# --- 등록 클래스 목록 ---
classes = [
    CNVProperties,
    Operator_cnv_test,
    Operator_checklist1,
    Operator_checklist2,
    Panel_view3d_ui_cnv_test,
    Panel_checklist1,
    Panel_checklist2,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.cnv_props = bpy.props.PointerProperty(type=CNVProperties)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.cnv_props
