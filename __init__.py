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

    checklist1_result: bpy.props.StringProperty(name="결과1", default="확인 버튼을 클릭하여 결과를 확인하세요.")
    checklist2_result: bpy.props.StringProperty(name="결과2", default="확인 버튼을 클릭하여 결과를 확인하세요.")
    checklist3_result: bpy.props.StringProperty(name="결과3", default="확인 버튼을 클릭하여 결과를 확인하세요.")

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
        print(list_of_target)
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
    bl_label = "확인"

    def execute(self, context):
        try:

            ifc_file = ifcopenshell.open(bpy.data.scenes["Scene"].BIMProperties.ifc_file)

            # IFC 파일 열기

            # Test
            for e in ifc_file.by_type("IfcElement"):
                psets = ifcopenshell.util.element.get_psets(e)
                if "cpted" in psets:
                    print(psets["cpted"])

            # 1. '객체구분'이 '주출입구'인 객체 필터링
            main_entrances = ifcopenshell.util.selector.filter_elements(ifc_file, "cpted.객체구분=\x08주출입구")
            print(main_entrances)
            if not main_entrances:
                context.scene.cnv_props.checklist1_result =main_entrances
                return {"FINISHED"}

            # 2. 각 객체의 '영역구분시설물포함여부'가 True인지 확인
            all_valid = True
            for e in main_entrances:
                result = ifcopenshell.util.selector.get_element_value(e, "cpted.영역구분시설물포함여부")
                print(result)
                if result is not True:
                    all_valid = False
                    break

            context.scene.cnv_props.checklist1_result = "적합" if all_valid else "부적합"

        except Exception as e:
            context.scene.cnv_props.checklist1_result = f"오류 발생: {str(e)}"

        return {"FINISHED"}



# --- 체크리스트2 Operator ---
class Operator_checklist2(bpy.types.Operator):
    bl_idname = "object.checklist2"
    bl_label = "확인"

    def execute(self, context):
        context.scene.cnv_props.checklist2_result = "체크리스트2 결과 OK"
        return {"FINISHED"}

# --- 체크리스트3 Operator ---
class Operator_checklist3(bpy.types.Operator):
    bl_idname = "object.checklist3"
    bl_label = "확인"

    def execute(self, context):
        context.scene.cnv_props.checklist3_result = "체크리스트3 결과 OK"
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
    bl_label = "공적영역-단지출입구-2"

    def draw(self, context):
        layout = self.layout
        layout.label(text="단지의 주출입구는 영역 구분을 위한 시설물을 계획한다.")

        layout.operator("object.checklist1")
        layout.label(text=f"결과: {context.scene.cnv_props.checklist1_result}")

# --- 체크리스트2 패널 ---
class Panel_checklist2(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "객체정보기반"
    bl_label = "공적영역-단지출입구-3"

    def draw(self, context):
        layout = self.layout
        layout.label(text="단지의 차량 출입구에는 감시와 출입 통제를 위한 시설물을 계획한다.")

        layout.operator("object.checklist2")
        layout.label(text=f"결과: {context.scene.cnv_props.checklist2_result}")

# --- 체크리스트3 패널 ---
class Panel_checklist3(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "객체정보기반"
    bl_label = "공적영역-단지출입구-4"

    def draw(self, context):
        layout = self.layout
        layout.label(text="단지의 보행자 출입구에는 영역 구분을 위한 시설물을 계획한다.")

        layout.operator("object.checklist3")
        layout.label(text=f"결과: {context.scene.cnv_props.checklist3_result}")

# --- 등록 클래스 목록 ---
classes = [
    CNVProperties,
    Operator_cnv_test,
    Operator_checklist1,
    Operator_checklist2,
    Operator_checklist3,    
    Panel_view3d_ui_cnv_test,
    Panel_checklist1,
    Panel_checklist2,
    Panel_checklist3,

]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.cnv_props = bpy.props.PointerProperty(type=CNVProperties)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.cnv_props
