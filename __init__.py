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
# --- 메인 프로퍼티 정의 ---
class CNVProperties(bpy.types.PropertyGroup):

    # ---checklist1---
    ray_count_input: bpy.props.IntProperty(name="RAY 개수")
    ray_length_input: bpy.props.FloatProperty(name="RAY 거리(m)")
    last_cross_count: bpy.props.IntProperty(name="간섭 수", default=0)

    # ---checklist2---
    checklist2_result: bpy.props.StringProperty(name="결과2", default="확인 버튼을 클릭하여 결과를 확인하세요.")
    checklist2_valid_ids: bpy.props.StringProperty(default="")
    checklist2_invalid_ids: bpy.props.StringProperty(default="")

    # ---checklist3---
    checklist3_result: bpy.props.StringProperty(name="결과3", default="확인 버튼을 클릭하여 결과를 확인하세요.")
    checklist3_valid_ids: bpy.props.StringProperty(default="")
    checklist3_invalid_ids: bpy.props.StringProperty(default="")

# --- 체크리스트1 ---
## --- 체크리스트1 확인 Operator ---
class Operator_checklist1(bpy.types.Operator):
    bl_idname = "object.checklist1"
    bl_label = "확인"
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

## --- 체크리스트1 UI 추가 ---
class Panel_checklist1(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CPTED 검토"
    bl_label = "공적영역-단지출입구-1"


    def draw(self, context):
        layout = self.layout
        cnv_props = context.scene.cnv_props

        row = layout.row(align=True)
        row.prop(cnv_props, "ray_count_input")
        row.prop(cnv_props, "ray_length_input")
        layout.operator("object.checklist1")
        layout.label(text=f"간섭 수: {cnv_props.last_cross_count}")


# --- 체크리스트2 ---
## --- 체크리스트2 확인 Operator ---
class Operator_checklist2(bpy.types.Operator):
    bl_idname = "object.checklist2"
    bl_label = "확인"

    def execute(self, context):
        try:
            ifc_file = ifcopenshell.open(bpy.data.scenes["Scene"].BIMProperties.ifc_file)
            valid_ids = []
            invalid_ids = []

            for e in ifc_file.by_type("IfcElement"):
                psets = ifcopenshell.util.element.get_psets(e)
                cpted = psets.get("cpted", {})
                obj_type = cpted.get("객체구분", "")
                if "주출입구" in obj_type:
                    if cpted.get("영역구분시설물포함여부") is True:
                        valid_ids.append(e.GlobalId)
                    else:
                        invalid_ids.append(e.GlobalId)

            context.scene.cnv_props.checklist2_valid_ids = ",".join(valid_ids)
            context.scene.cnv_props.checklist2_invalid_ids = ",".join(invalid_ids)

            if not (valid_ids or invalid_ids):
                context.scene.cnv_props.checklist2_result = "부적합 (주출입구 없음)"
            elif invalid_ids:
                context.scene.cnv_props.checklist2_result = "부적합"
            else:
                context.scene.cnv_props.checklist2_result = "적합"

        except Exception as e:
            context.scene.cnv_props.checklist2_result = f"오류 발생: {str(e)}"

        return {"FINISHED"}

## --- 체크리스트2 적합 객체 출력 ---
class Operator_checklist2_show_valid(bpy.types.Operator):
    bl_idname = "object.checklist1_valid"
    bl_label = "적합한 객체 확인"

    def execute(self, context):
        valid_ids = context.scene.cnv_props.checklist2_valid_ids.split(",")
        bpy.ops.object.select_all(action='DESELECT')  # 선택 초기화

        selected = 0
        for gid in valid_ids:
            bpy.ops.bim.select_similar(key=gid, calculated_sum=0)
            selected += 1



        if selected == 0:
            self.report({'WARNING'}, "선택할 적합 객체가 없습니다.")
        else:
            self.report({'INFO'}, f"{selected}개 적합 객체 선택 완료")
        return {"FINISHED"}

## --- 체크리스트2 부적합 객체 출력 ---
class Operator_checklist2_show_invalid(bpy.types.Operator):
    bl_idname = "object.checklist1_invalid"
    bl_label = "부적합한 객체 확인"

    def execute(self, context):
        invalid_ids = context.scene.cnv_props.checklist2_invalid_ids.split(",")
        bpy.ops.object.select_all(action='DESELECT')  # 선택 초기화

        selected = 0
        for gid in invalid_ids:
            if gid in bpy.data.objects:
                obj = bpy.data.objects[gid]
                obj.select_set(True)
                selected += 1

        if selected == 0:
            self.report({'WARNING'}, "선택할 부적합 객체가 없습니다.")
        else:
            self.report({'INFO'}, f"{selected}개 부적합 객체 선택 완료")
        return {"FINISHED"}

## --- 체크리스트2 UI 추가 ---
class Panel_checklist2(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CPTED 검토"
    bl_label = "공적영역-단지출입구-2"

    def draw(self, context):
        layout = self.layout
        layout.label(text="단지의 주출입구는 영역 구분을 위한 시설물을 계획한다.")
        layout.operator("object.checklist2")
        layout.label(text=f"결과: {context.scene.cnv_props.checklist2_result}")
        layout.separator()
        row = layout.row(align=True)
        row.operator("object.checklist2_valid", text="적합한 객체 확인")
        row.operator("object.checklist2_invalid", text="부적합한 객체 확인")


# --- 체크리스트3 ---
## --- 체크리스트3 확인 Operator ---
class Operator_checklist3(bpy.types.Operator):
    bl_idname = "object.checklist2"
    bl_label = "확인"

    def execute(self, context):
        try:
            ifc_file = ifcopenshell.open(bpy.data.scenes["Scene"].BIMProperties.ifc_file)
            valid_ids = []
            invalid_ids = []

            for e in ifc_file.by_type("IfcElement"):
                psets = ifcopenshell.util.element.get_psets(e)
                cpted = psets.get("cpted", {})
                obj_type = cpted.get("객체구분", "")
                if "주출입구" in obj_type:
                    if cpted.get("영역구분시설물포함여부") is True:
                        valid_ids.append(e.GlobalId)
                    else:
                        invalid_ids.append(e.GlobalId)

            context.scene.cnv_props.checklist2_valid_ids = ",".join(valid_ids)
            context.scene.cnv_props.checklist2_invalid_ids = ",".join(invalid_ids)

            if not (valid_ids or invalid_ids):
                context.scene.cnv_props.checklist2_result = "부적합 (주출입구 없음)"
            elif invalid_ids:
                context.scene.cnv_props.checklist2_result = "부적합"
            else:
                context.scene.cnv_props.checklist2_result = "적합"

        except Exception as e:
            context.scene.cnv_props.checklist2_result = f"오류 발생: {str(e)}"

        return {"FINISHED"}

## --- 체크리스트2 적합 객체 출력 ---
class Operator_checklist2_show_valid(bpy.types.Operator):
    bl_idname = "object.checklist1_valid"
    bl_label = "적합한 객체 확인"

    def execute(self, context):
        valid_ids = context.scene.cnv_props.checklist2_valid_ids.split(",")
        bpy.ops.object.select_all(action='DESELECT')  # 선택 초기화

        selected = 0
        for gid in valid_ids:
            bpy.ops.bim.select_similar(key=gid, calculated_sum=0)
            selected += 1



        if selected == 0:
            self.report({'WARNING'}, "선택할 적합 객체가 없습니다.")
        else:
            self.report({'INFO'}, f"{selected}개 적합 객체 선택 완료")
        return {"FINISHED"}

## --- 체크리스트2 부적합 객체 출력 ---
class Operator_checklist2_show_invalid(bpy.types.Operator):
    bl_idname = "object.checklist1_invalid"
    bl_label = "부적합한 객체 확인"

    def execute(self, context):
        invalid_ids = context.scene.cnv_props.checklist2_invalid_ids.split(",")
        bpy.ops.object.select_all(action='DESELECT')  # 선택 초기화

        selected = 0
        for gid in invalid_ids:
            if gid in bpy.data.objects:
                obj = bpy.data.objects[gid]
                obj.select_set(True)
                selected += 1

        if selected == 0:
            self.report({'WARNING'}, "선택할 부적합 객체가 없습니다.")
        else:
            self.report({'INFO'}, f"{selected}개 부적합 객체 선택 완료")
        return {"FINISHED"}

## --- 체크리스트2 UI 추가 ---
class Panel_checklist2(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CPTED 검토"
    bl_label = "공적영역-단지출입구-2"

    def draw(self, context):
        layout = self.layout
        layout.label(text="단지의 주출입구는 영역 구분을 위한 시설물을 계획한다.")
        layout.operator("object.checklist2")
        layout.label(text=f"결과: {context.scene.cnv_props.checklist2_result}")
        layout.separator()
        row = layout.row(align=True)
        row.operator("object.checklist2_valid", text="적합한 객체 확인")
        row.operator("object.checklist2_invalid", text="부적합한 객체 확인")









# --- 등록 클래스 목록 ---
classes = [
    CNVProperties,
    # --- 체크리스트1 ---
    Operator_checklist1,
    Panel_checklist1,

    # -- 체크리스트2 ---
    Operator_checklist2,
    Operator_checklist2_show_valid,
    Operator_checklist2_show_invalid,
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
