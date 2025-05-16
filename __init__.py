import bpy
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.shape
import ifcopenshell.util.selector
import numpy as np
import multiprocessing
import math
import sys
import os
import subprocess

# 현재 애드온 폴더 기준 상대 경로로 open3d 경로 추가
addon_dir = os.path.dirname(__file__)
open3d_path = os.path.join(addon_dir, ".mddoyun", "lib", "python3.11", "site-packages")

if open3d_path not in sys.path:
    sys.path.append(open3d_path)




import open3d as o3d



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

    # checklist1
    ray_count_input: bpy.props.IntProperty(name="RAY 개수")
    ray_length_input: bpy.props.FloatProperty(name="RAY 거리(m)")
    ray_angle_input: bpy.props.FloatProperty(name="RAY 각도(도)", default=0.0)
    last_cross_count: bpy.props.IntProperty(name="간섭 수", default=0)
    last_not_cross_count: bpy.props.IntProperty(name="비간섭 수", default=0)
    last_not_cross_ratio: bpy.props.FloatProperty(name="개방율", default=0.0)
    checklist1_result_lines: bpy.props.StringProperty(name="개방율 결과 목록", default="")

    # ---checklist2---
    checklist2_result: bpy.props.StringProperty(name="결과2", default="확인 버튼을 클릭하여 결과를 확인하세요.")
    checklist2_valid_ids: bpy.props.StringProperty(default="")
    checklist2_invalid_ids: bpy.props.StringProperty(default="")

    # ---checklist3---
    checklist3_result: bpy.props.StringProperty(name="결과3", default="확인 버튼을 클릭하여 결과를 확인하세요.")
    checklist3_valid_ids: bpy.props.StringProperty(default="")
    checklist3_invalid_ids: bpy.props.StringProperty(default="")

    # ---checklist4---
    checklist3_result: bpy.props.StringProperty(name="결과4", default="확인 버튼을 클릭하여 결과를 확인하세요.")
    checklist3_valid_ids: bpy.props.StringProperty(default="")
    checklist3_invalid_ids: bpy.props.StringProperty(default="")


# --- 공통도구 정의 ---
## --- 정리도구 ---
class Operator_clean(bpy.types.Operator):
    bl_idname = "object.clean"
    bl_label = "가시성 정리"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        # 사용자 입력값을 속성(CNVProperty)에서 가져옴
        for obj in bpy.data.objects:
            if "Ray_Line" in obj.name:
                # 객체가 컬렉션에 연결되어 있다면 제거 후 삭제
                bpy.data.objects.remove(obj, do_unlink=True)


        return {"FINISHED"}

# --- 체크리스트1 --- 과업 중 2단계 항목 중 전체 기능 포함(1/1)
## --- 체크리스트1 UI 추가 ---
class Panel_checklist1(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CPTED 검토"
    bl_label = "공적영역-단지출입구-1"

    def draw(self, context):
        layout = self.layout
        cnv_props = context.scene.cnv_props

        layout.label(text="단지의 출입구는 주변에서 감시가 가능하도록 계획한다.")

        row = layout.row(align=True)
        row.prop(cnv_props, "ray_count_input")
        row.prop(cnv_props, "ray_length_input")
        row.prop(cnv_props, "ray_angle_input")

        layout.operator("object.checklist1")


        layout.separator()
        layout.label(text="출입구별 개방율:")
        box = layout.box()
        for line in cnv_props.checklist1_result_lines.split("\n"):
            box.label(text=line)
        layout.operator("object.clean")

## --- 체크리스트1 확인 Operator ---

class Operator_checklist1(bpy.types.Operator):
    bl_idname = "object.checklist1"
    bl_label = "확인"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT"
    def execute(self, context):
        # 사용자 입력값을 속성(CNVProperty)에서 가져옴
        ray_count_input_value = context.scene.cnv_props.ray_count_input        # 사용자가 지정한 ray 수
        ray_length_input_value = context.scene.cnv_props.ray_length_input      # ray 길이(m)
        ray_angle_input_value = context.scene.cnv_props.ray_angle_input        # ray의 Z축 방향 각도(도))

        # 현재 씬의 IFC 파일 경로를 통해 IFC 파일 열기
        ifc_file = ifcopenshell.open(bpy.data.scenes["Scene"].BIMProperties.ifc_file)

        # 'cpted.객체구분' 속성이 '출입구'를 포함하는 객체만 필터링
        list_of_target = ifcopenshell.util.selector.filter_elements(
            ifc_file, "cpted.객체구분*=출입구"
        )
        print(list_of_target)

        # IFC 형상 설정 (월드 좌표계 기준)
        settings = ifcopenshell.geom.settings()
        settings.set(settings.USE_WORLD_COORDS, True)

        # 전체 간섭 및 비간섭 ray 개수 집계용
        total_cross = 0
        total_not_cross = 0
        results_text = []          # UI에 출력할 결과 문자열 저장용
        all_hit_points = []        # 전체 ray 충돌 지점 좌표 저장용

        print("=== 출입구 객체별 개방율 결과 ===")

        # Target 객체 반복
        i = 1
        cross_list_list =[]
        results_text = []
        # 각 출입구 객체에 대해 반복
        for element in list_of_target:

            # geom tree (ray) 세팅
            tree = ifcopenshell.geom.tree()
            settings = ifcopenshell.geom.settings()
            iterator = ifcopenshell.geom.iterator(settings, ifc_file, multiprocessing.cpu_count())
            if iterator.initialize():
                while True:
                    # Use triangulation to build a BVH tree
                    # tree.add_element(iterator.get())

                    # Alternatively, use this code to build an unbalanced binary tree
                    tree.add_element(iterator.get_native())

                    if not iterator.next():
                        break


            print("---------",i,"번째 Target객체 ---------")
            print("Name : ", element.Name)
           
            # shape 가져오기
            shape = ifcopenshell.geom.create_shape(settings, element)
            geometry = shape.geometry
            matrix = ifcopenshell.util.shape.get_shape_matrix(shape)
            location = matrix[:,3][0:3]    
            verts = np.array(geometry.verts).reshape(-1,3)
          
            # ✅ 튜플 형태로 변환 (예: (0., 0., 0.))
            location_tuple = tuple(map(float, location))
            print("Location:", location_tuple)

            # ray 반복
            ray_count = ray_count_input_value
            cross_count = 0
            ray_length = ray_length_input_value
            ray_angle = ray_angle_input_value
            cross_list = []
            for j in range(ray_count):
                angle_deg = j * (360 / ray_count)
                angle_rad = math.radians(angle_deg)
                angle_rad_z = math.radians(ray_angle)

                # direction 벡터 계산 (XY 평면에서 Z는 0)
                direction = (math.cos(angle_rad), math.sin(angle_rad), math.tan(angle_rad_z))
                print(tuple(round(x, 3) for x in direction))
                # 정규화 (단위 벡터 보장)
                norm = math.sqrt(direction[0]**2 + direction[1]**2)
                direction = (direction[0]/norm, direction[1]/norm, math.tan(angle_rad_z))

                # ray 쏘기
                results = tree.select_ray(location_tuple, direction, length=ray_length)
                # element와 같은 ID를 가지는 result 제외
                filtered_results = [
                    r for r in results if r.instance and r.instance.id() != element.id()
                ]

                if filtered_results:
                    
                    print('results:')
                    # 가장 가까운 교차 결과 추출
                    closest_result = min(results, key=lambda r: r.distance)
                    print(closest_result)

                    # 실제 교차된 IFC 요소 가져오기
                    hit_element = ifc_file.by_id(closest_result.instance.id())
                    print(hit_element)
                    # 해당 요소의 속성 가져오기
                    psets = ifcopenshell.util.element.get_psets(hit_element)
                    cpted = psets.get("cpted", {})
                    print(cpted)
                    if cpted.get("감시객체여부") is True:
                        cross_list.append(0)
                        create_ray_line(location, direction, ray_length)
                    else:
                        cross_count += 1
                        cross_list.append(1)

                else:
                    cross_list.append(0)
                    create_ray_line(location, direction, ray_length)
            cross_list_list.append(cross_list)
            i+=1


            total_rays = ray_count
            not_cross_count = total_rays - cross_count

            if total_rays > 0:
                openness_ratio = (not_cross_count / total_rays) * 100
            else:
                openness_ratio = 0.0  # ray_count 자체가 0일 경우

            # ... 결과 텍스트 생성 반복문 ...
            result_line = f"GlobalId : {element.GlobalId} | Name : {element.Name} | 개방율 : {round(openness_ratio, 2)}%"
            results_text.append(result_line)

            # 리스트를 문자열로 변환하여 저장
            context.scene.cnv_props.checklist1_result_lines = "\n".join(results_text)
        # context.scene.cnv_props.checklist1_result_lines = results_text


        return {"FINISHED"}
    


# --- 체크리스트2 --- 과업 중 1단계 항목 중 1(1/10)
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
        row.operator("object.checklist2_reset", text="리셋")

## --- 체크리스트2 확인 Operator ---
class Operator_checklist2(bpy.types.Operator):
    bl_idname = "object.checklist2"
    bl_label = "확인"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            # 모든 기존 객체에서 이전 태그 제거
            for obj in bpy.data.objects:
                if "was_hidden_by_checklist2" in obj:
                    del obj["was_hidden_by_checklist2"]

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

            settings = ifcopenshell.geom.settings()
            settings.set(settings.USE_WORLD_COORDS, True)

            def get_or_create_material(name, color):
                mat = bpy.data.materials.get(name)
                if not mat:
                    mat = bpy.data.materials.new(name=name)
                    mat.use_nodes = False
                    mat.diffuse_color = color
                return mat

            blue_mat = get_or_create_material("ValidMaterial", (0.0, 0.4, 1.0, 1.0))    # 파란색
            red_mat = get_or_create_material("InvalidMaterial", (1.0, 0.1, 0.1, 1.0))   # 빨간색

            def create_and_link_object(gid, color_mat, label):
                element = ifc_file.by_guid(gid)
                if not element:
                    return None
                shape = ifcopenshell.geom.create_shape(settings, element)
                geometry = shape.geometry
                verts = np.array(geometry.verts).reshape(-1, 3)
                faces = np.array(geometry.faces).reshape(-1, 3)

                mesh_data = bpy.data.meshes.new(name=f"{label}_{gid}")
                mesh_data.from_pydata(verts.tolist(), [], faces.tolist())
                mesh_data.update()

                obj = bpy.data.objects.new(f"{label}_{gid}", mesh_data)
                obj.data.materials.append(color_mat)
                bpy.context.collection.objects.link(obj)

                return obj

            def vertices_match(obj1, obj2, epsilon=1e-6):
                if obj1.type != 'MESH' or obj2.type != 'MESH':
                    return False

                verts1 = [tuple((obj1.matrix_world @ v.co)[:]) for v in obj1.data.vertices]
                verts2 = [tuple((obj2.matrix_world @ v.co)[:]) for v in obj2.data.vertices]

                if len(verts1) != len(verts2):
                    return False

                verts1_sorted = sorted(verts1)
                verts2_sorted = sorted(verts2)

                for v1, v2 in zip(verts1_sorted, verts2_sorted):
                    if any(abs(a - b) > epsilon for a, b in zip(v1, v2)):
                        return False

                return True

            new_objects = []

            for gid in valid_ids:
                obj = create_and_link_object(gid, blue_mat, "Valid")
                if obj:
                    new_objects.append(obj)

            for gid in invalid_ids:
                obj = create_and_link_object(gid, red_mat, "Invalid")
                if obj:
                    new_objects.append(obj)

            # 기존 객체 중 geometry가 완전히 같은 경우 숨기기
            for new_obj in new_objects:
                for obj in bpy.data.objects:
                    if obj == new_obj or obj.hide_get():
                        continue
                    if obj.type != 'MESH':
                        continue

                    if vertices_match(obj, new_obj):
                        obj.hide_set(True)
                        obj["was_hidden_by_checklist2"] = True  # 🔷 리셋 시 복원용 태그
        except Exception as e:
            context.scene.cnv_props.checklist2_result = f"오류 발생: {str(e)}"

        return {"FINISHED"}

## --- 체크리스트2 리셋 Operator ---
class Operator_checklist2_reset(bpy.types.Operator):
    bl_idname = "object.checklist2_reset"
    bl_label = "리셋"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        # 숨긴 객체 다시 보이게
        for obj in bpy.data.objects:
            if obj.get("was_hidden_by_checklist2"):
                obj.hide_set(False)
                del obj["was_hidden_by_checklist2"]

        # 생성된 Valid, Invalid 객체 삭제
        for obj in list(bpy.data.objects):
            if obj.name.startswith("Valid_") or obj.name.startswith("Invalid_"):
                bpy.data.objects.remove(obj, do_unlink=True)

        self.report({'INFO'}, "체크리스트2 상태 초기화 완료")
        return {"FINISHED"}



# --- 체크리스트3 --- 과업 중 1단계 항목 중 1(1/10)
## --- 체크리스트3 UI 추가 ---
class Panel_checklist3(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CPTED 검토"
    bl_label = "공적영역-단지출입구-3"

    def draw(self, context):
        layout = self.layout
        layout.label(text="단지의 차량 출입구에는 감시와 출입 통제를 위한 시설물을 계획한다.")
        layout.operator("object.checklist3")
        layout.label(text=f"결과: {context.scene.cnv_props.checklist3_result}")
        layout.separator()
        row = layout.row(align=True)
        row.operator("object.checklist3_reset", text="리셋")

## --- 체크리스트3 확인 Operator ---
class Operator_checklist3(bpy.types.Operator):
    bl_idname = "object.checklist3"
    bl_label = "확인"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            # 모든 기존 객체에서 이전 태그 제거
            for obj in bpy.data.objects:
                if "was_hidden_by_checklist3" in obj:
                    del obj["was_hidden_by_checklist3"]

            ifc_file = ifcopenshell.open(bpy.data.scenes["Scene"].BIMProperties.ifc_file)
            valid_ids = []
            invalid_ids = []

            for e in ifc_file.by_type("IfcElement"):
                psets = ifcopenshell.util.element.get_psets(e)
                cpted = psets.get("cpted", {})
                obj_type = cpted.get("객체구분", "")
                if "출입구" in obj_type:
                    if cpted.get("영역구분시설물포함여부") is True:
                        valid_ids.append(e.GlobalId)
                    else:
                        invalid_ids.append(e.GlobalId)

            context.scene.cnv_props.checklist3_valid_ids = ",".join(valid_ids)
            context.scene.cnv_props.checklist3_invalid_ids = ",".join(invalid_ids)

            if not (valid_ids or invalid_ids):
                context.scene.cnv_props.checklist3_result = "부적합 (주출입구 없음)"
            elif invalid_ids:
                context.scene.cnv_props.checklist3_result = "부적합"
            else:
                context.scene.cnv_props.checklist3_result = "적합"

            settings = ifcopenshell.geom.settings()
            settings.set(settings.USE_WORLD_COORDS, True)

            def get_or_create_material(name, color):
                mat = bpy.data.materials.get(name)
                if not mat:
                    mat = bpy.data.materials.new(name=name)
                    mat.use_nodes = False
                    mat.diffuse_color = color
                return mat

            blue_mat = get_or_create_material("ValidMaterial", (0.0, 0.4, 1.0, 1.0))    # 파란색
            red_mat = get_or_create_material("InvalidMaterial", (1.0, 0.1, 0.1, 1.0))   # 빨간색

            def create_and_link_object(gid, color_mat, label):
                element = ifc_file.by_guid(gid)
                if not element:
                    return None
                shape = ifcopenshell.geom.create_shape(settings, element)
                geometry = shape.geometry
                verts = np.array(geometry.verts).reshape(-1, 3)
                faces = np.array(geometry.faces).reshape(-1, 3)

                mesh_data = bpy.data.meshes.new(name=f"{label}_{gid}")
                mesh_data.from_pydata(verts.tolist(), [], faces.tolist())
                mesh_data.update()

                obj = bpy.data.objects.new(f"{label}_{gid}", mesh_data)
                obj.data.materials.append(color_mat)
                bpy.context.collection.objects.link(obj)

                return obj

            def vertices_match(obj1, obj2, epsilon=1e-6):
                if obj1.type != 'MESH' or obj2.type != 'MESH':
                    return False

                verts1 = [tuple((obj1.matrix_world @ v.co)[:]) for v in obj1.data.vertices]
                verts2 = [tuple((obj2.matrix_world @ v.co)[:]) for v in obj2.data.vertices]

                if len(verts1) != len(verts2):
                    return False

                verts1_sorted = sorted(verts1)
                verts2_sorted = sorted(verts2)

                for v1, v2 in zip(verts1_sorted, verts2_sorted):
                    if any(abs(a - b) > epsilon for a, b in zip(v1, v2)):
                        return False

                return True

            new_objects = []

            for gid in valid_ids:
                obj = create_and_link_object(gid, blue_mat, "Valid")
                if obj:
                    new_objects.append(obj)

            for gid in invalid_ids:
                obj = create_and_link_object(gid, red_mat, "Invalid")
                if obj:
                    new_objects.append(obj)

            # 기존 객체 중 geometry가 완전히 같은 경우 숨기기
            for new_obj in new_objects:
                for obj in bpy.data.objects:
                    if obj == new_obj or obj.hide_get():
                        continue
                    if obj.type != 'MESH':
                        continue

                    if vertices_match(obj, new_obj):
                        obj.hide_set(True)
                        obj["was_hidden_by_checklist3"] = True  # 🔷 리셋 시 복원용 태그
        except Exception as e:
            context.scene.cnv_props.checklist3_result = f"오류 발생: {str(e)}"

        return {"FINISHED"}

## --- 체크리스트3 리셋 Operator ---
class Operator_checklist3_reset(bpy.types.Operator):
    bl_idname = "object.checklist3_reset"
    bl_label = "리셋"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        # 숨긴 객체 다시 보이게
        for obj in bpy.data.objects:
            if obj.get("was_hidden_by_checklist3"):
                obj.hide_set(False)
                del obj["was_hidden_by_checklist3"]

        # 생성된 Valid, Invalid 객체 삭제
        for obj in list(bpy.data.objects):
            if obj.name.startswith("Valid_") or obj.name.startswith("Invalid_"):
                bpy.data.objects.remove(obj, do_unlink=True)

        self.report({'INFO'}, "체크리스트3 상태 초기화 완료")
        return {"FINISHED"}



# --- 체크리스트3 --- 과업 중 1단계 항목 중 1(1/10)
## --- 체크리스트3 UI 추가 ---
class Panel_checklist3(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CPTED 검토"
    bl_label = "공적영역-단지출입구-3"

    def draw(self, context):
        layout = self.layout
        layout.label(text="단지의 차량 출입구에는 감시와 출입 통제를 위한 시설물을 계획한다.")
        layout.operator("object.checklist3")
        layout.label(text=f"결과: {context.scene.cnv_props.checklist3_result}")
        layout.separator()
        row = layout.row(align=True)
        row.operator("object.checklist3_reset", text="리셋")

## --- 체크리스트3 확인 Operator ---
class Operator_checklist3(bpy.types.Operator):
    bl_idname = "object.checklist3"
    bl_label = "확인"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            # 모든 기존 객체에서 이전 태그 제거
            for obj in bpy.data.objects:
                if "was_hidden_by_checklist3" in obj:
                    del obj["was_hidden_by_checklist3"]

            ifc_file = ifcopenshell.open(bpy.data.scenes["Scene"].BIMProperties.ifc_file)
            valid_ids = []
            invalid_ids = []

            for e in ifc_file.by_type("IfcElement"):
                psets = ifcopenshell.util.element.get_psets(e)
                cpted = psets.get("cpted", {})
                obj_type = cpted.get("객체구분", "")
                if "출입구" in obj_type:
                    if cpted.get("영역구분시설물포함여부") is True:
                        valid_ids.append(e.GlobalId)
                    else:
                        invalid_ids.append(e.GlobalId)

            context.scene.cnv_props.checklist3_valid_ids = ",".join(valid_ids)
            context.scene.cnv_props.checklist3_invalid_ids = ",".join(invalid_ids)

            if not (valid_ids or invalid_ids):
                context.scene.cnv_props.checklist3_result = "부적합 (주출입구 없음)"
            elif invalid_ids:
                context.scene.cnv_props.checklist3_result = "부적합"
            else:
                context.scene.cnv_props.checklist3_result = "적합"

            settings = ifcopenshell.geom.settings()
            settings.set(settings.USE_WORLD_COORDS, True)

            def get_or_create_material(name, color):
                mat = bpy.data.materials.get(name)
                if not mat:
                    mat = bpy.data.materials.new(name=name)
                    mat.use_nodes = False
                    mat.diffuse_color = color
                return mat

            blue_mat = get_or_create_material("ValidMaterial", (0.0, 0.4, 1.0, 1.0))    # 파란색
            red_mat = get_or_create_material("InvalidMaterial", (1.0, 0.1, 0.1, 1.0))   # 빨간색

            def create_and_link_object(gid, color_mat, label):
                element = ifc_file.by_guid(gid)
                if not element:
                    return None
                shape = ifcopenshell.geom.create_shape(settings, element)
                geometry = shape.geometry
                verts = np.array(geometry.verts).reshape(-1, 3)
                faces = np.array(geometry.faces).reshape(-1, 3)

                mesh_data = bpy.data.meshes.new(name=f"{label}_{gid}")
                mesh_data.from_pydata(verts.tolist(), [], faces.tolist())
                mesh_data.update()

                obj = bpy.data.objects.new(f"{label}_{gid}", mesh_data)
                obj.data.materials.append(color_mat)
                bpy.context.collection.objects.link(obj)

                return obj

            def vertices_match(obj1, obj2, epsilon=1e-6):
                if obj1.type != 'MESH' or obj2.type != 'MESH':
                    return False

                verts1 = [tuple((obj1.matrix_world @ v.co)[:]) for v in obj1.data.vertices]
                verts2 = [tuple((obj2.matrix_world @ v.co)[:]) for v in obj2.data.vertices]

                if len(verts1) != len(verts2):
                    return False

                verts1_sorted = sorted(verts1)
                verts2_sorted = sorted(verts2)

                for v1, v2 in zip(verts1_sorted, verts2_sorted):
                    if any(abs(a - b) > epsilon for a, b in zip(v1, v2)):
                        return False

                return True

            new_objects = []

            for gid in valid_ids:
                obj = create_and_link_object(gid, blue_mat, "Valid")
                if obj:
                    new_objects.append(obj)

            for gid in invalid_ids:
                obj = create_and_link_object(gid, red_mat, "Invalid")
                if obj:
                    new_objects.append(obj)

            # 기존 객체 중 geometry가 완전히 같은 경우 숨기기
            for new_obj in new_objects:
                for obj in bpy.data.objects:
                    if obj == new_obj or obj.hide_get():
                        continue
                    if obj.type != 'MESH':
                        continue

                    if vertices_match(obj, new_obj):
                        obj.hide_set(True)
                        obj["was_hidden_by_checklist3"] = True  # 🔷 리셋 시 복원용 태그
        except Exception as e:
            context.scene.cnv_props.checklist3_result = f"오류 발생: {str(e)}"

        return {"FINISHED"}

## --- 체크리스트4 리셋 Operator ---
class Operator_checklist3_reset(bpy.types.Operator):
    bl_idname = "object.checklist3_reset"
    bl_label = "리셋"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        # 숨긴 객체 다시 보이게
        for obj in bpy.data.objects:
            if obj.get("was_hidden_by_checklist3"):
                obj.hide_set(False)
                del obj["was_hidden_by_checklist3"]

        # 생성된 Valid, Invalid 객체 삭제
        for obj in list(bpy.data.objects):
            if obj.name.startswith("Valid_") or obj.name.startswith("Invalid_"):
                bpy.data.objects.remove(obj, do_unlink=True)

        self.report({'INFO'}, "체크리스트3 상태 초기화 완료")
        return {"FINISHED"}





# --- 등록 클래스 목록 ---
classes = [
    CNVProperties,
    Operator_clean,
    # --- 체크리스트1 ---
    Operator_checklist1,
    Panel_checklist1,

    # -- 체크리스트2 ---
    Operator_checklist2,
    Operator_checklist2_reset,
    Panel_checklist2,

    # -- 체크리스트3 ---
    Operator_checklist3,
    Operator_checklist3_reset,
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


# 참고함수
def create_ray_line(location, direction, ray_length):
    """
    Blender 내에 선 오브젝트(Line Object)를 생성하는 함수

    Parameters:
    - location: 시작점 좌표 (튜플, 예: (0.0, 0.0, 0.0))
    - direction: 정규화된 방향 벡터 (튜플, 예: (1.0, 0.0, 0.0))
    - ray_length: 선의 길이 (float)
    """
    # 끝점 계산: 시작점 + 방향 * 길이
    end = (
        location[0] + direction[0] * ray_length,
        location[1] + direction[1] * ray_length,
        location[2] + direction[2] * ray_length
    )

    # 점과 엣지 정의
    verts = [location, end]
    edges = [(0, 1)]
    faces = []

    # 메쉬 생성
    mesh_data = bpy.data.meshes.new("Ray_Line_Mesh")
    mesh_data.from_pydata(verts, edges, faces)
    mesh_data.update()

    # 오브젝트 생성 및 컬렉션에 추가
    obj = bpy.data.objects.new("Ray_Line", mesh_data)
    bpy.context.collection.objects.link(obj)

    return obj
