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
import colorsys
from ifcopenshell.api import run
# 올바른 코드
from ifcopenshell.util.element import get_psets
# 맨 위 import 구역에 추가



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

    # ---체크리스트1---(type : 객체로부터 시작된 방사형 ray객체와 간섭 객체 검사 (개방율파악))
    checklist1_ray_count_input: bpy.props.IntProperty(name="RAY 개수")
    checklist1_ray_length_input: bpy.props.FloatProperty(name="RAY 거리(m)")
    checklist1_ray_angle_input: bpy.props.FloatProperty(name="RAY 각도(도)", default=0.0)
    checklist1_result_lines: bpy.props.StringProperty(name="개방율 결과 목록", default="")

    # ---체크리스트2---(type : 데이터 기반 검사)
    checklist2_result: bpy.props.StringProperty(name="결과2", default="확인 버튼을 클릭하여 결과를 확인하세요.")
    checklist2_valid_ids: bpy.props.StringProperty(default="")
    checklist2_invalid_ids: bpy.props.StringProperty(default="")

    # ---전처리1---(type : 간섭기반 데이터입력 자동화)
    preprocess1_target_name: bpy.props.StringProperty(name="대상객체 이름")
    preprocess1_blocker_name: bpy.props.StringProperty(name="간섭판단객체 이름")
    preprocess1_attribute_name: bpy.props.StringProperty(name="속성이름")


    # ---전처리2---(type : Geometry 기반 높이정보 데이터입력 자동화)




# ---체크리스트1---(type : 객체로부터 시작된 방사형 ray객체와 간섭 객체 검사 (개방율파악))
## --- 체크리스트1 UI 추가 ---
class Panel_checklist1(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CPTED 체크리스트"
    bl_label = "(샘플)방사형ray기반검토)"

    def draw(self, context):
        layout = self.layout
        cnv_props = context.scene.cnv_props

        layout.label(text="단지의 출입구는 주변에서 감시가 가능하도록 계획한다.")

        row = layout.row(align=True)
        row.prop(cnv_props, "checklist1_ray_count_input")
        row.prop(cnv_props, "checklist1_ray_length_input")
        row.prop(cnv_props, "checklist1_ray_angle_input")

        layout.operator("object.checklist1")


        layout.separator()
        layout.label(text="출입구별 개방율:")
        box = layout.box()
        for line in cnv_props.checklist1_result_lines.split("\n"):
            box.label(text=line)
        layout.operator("object.checklist1_reset")

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
        ray_count_input_value = context.scene.cnv_props.checklist1_ray_count_input        # 사용자가 지정한 ray 수
        ray_length_input_value = context.scene.cnv_props.checklist1_ray_length_input      # ray 길이(m)
        ray_angle_input_value = context.scene.cnv_props.checklist1_ray_angle_input        # ray의 Z축 방향 각도(도))

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


        element_count = len(list_of_target)
        # 각 출입구 객체에 대해 반복
        for element in list_of_target:

            # 레이색상설정
            hue = i / max(1, element_count)   # 0.0 ~ 1.0 분포
            r, g, b = colorsys.hsv_to_rgb(hue, 0.7, 1.0)  # 채도와 명도 고정
            color_rgba = (r, g, b, 1.0)

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

                # 자기 자신 제외
                filtered_results = [
                    r for r in results if r.instance and r.instance.id() != element.id()
                ]

                # 교차 결과가 있을 경우
                if filtered_results:
                    # 교차된 객체 중 하나라도 시야간섭객체제외 != True 라면 → 간섭으로 처리
                    obstructing_found = False
                    for r in filtered_results:
                        hit_element = ifc_file.by_id(r.instance.id())
                        psets = ifcopenshell.util.element.get_psets(hit_element)
                        cpted = psets.get("cpted", {})
                        flag = cpted.get("시야간섭객체제외여부")
                        print(f"▶ Hit {hit_element.Name} | 시야간섭객체제외여부: {flag}")
                        if flag is not True:
                            obstructing_found = True
                            break

                    if obstructing_found:
                        cross_count += 1
                        cross_list.append(1)
                    else:
                        cross_list.append(0)
                        create_ray_line(location, direction, ray_length, f'checklist1_rayline_{i}', color=color_rgba)
                else:
                    # 교차 자체가 없을 경우 → 비간섭 처리 및 시각화
                    cross_list.append(0)
                    create_ray_line(location, direction, ray_length, f'checklist1_rayline_{i}', color=color_rgba)

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


        return {"FINISHED"}
    
## --- 체크리스트1 리셋 Operator ---
class Operator_checklist1_reset(bpy.types.Operator):
    bl_idname = "object.checklist1_reset"
    bl_label = "가시성 정리"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        # 사용자 입력값을 속성(CNVProperty)에서 가져옴
        for obj in bpy.data.objects:
            if "checklist1" in obj.name:
                # 객체가 컬렉션에 연결되어 있다면 제거 후 삭제
                bpy.data.objects.remove(obj, do_unlink=True)


        return {"FINISHED"}



# --- 체크리스트2 --- (Type : 데이터 기반 검사)
## --- 체크리스트2 UI 추가 ---
class Panel_checklist2(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CPTED 체크리스트"
    bl_label = "(샘플)속성기반검토"

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


# ---전처리1---(type : 간섭기반 데이터입력 자동화)
## --- 전처리1 UI 추가 ---
class Panel_preprocess1(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CPTED 전처리"
    bl_label = "간섭 판별 속성 설정"

    def draw(self, context):
        layout = self.layout
        props = context.scene.cnv_props

        layout.prop(props, "preprocess1_target_name")
        layout.prop(props, "preprocess1_blocker_name")
        layout.prop(props, "preprocess1_attribute_name")
        layout.operator("object.preprocess1")


## --- 전처리1 Operator ---

class Operator_preprocess1(bpy.types.Operator):
    bl_idname = "object.preprocess1"
    bl_label = "간섭 여부 판별 및 속성 설정"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.cnv_props
        ifc_file = ifcopenshell.open(bpy.data.scenes["Scene"].BIMProperties.ifc_file)

        target_name = props.preprocess1_target_name.strip()
        blocker_name = props.preprocess1_blocker_name.strip()
        attribute_name = props.preprocess1_attribute_name.strip()

        if not target_name or not blocker_name or not attribute_name:
            self.report({'ERROR'}, "모든 입력 항목을 입력하세요.")
            return {'CANCELLED'}

        settings = ifcopenshell.geom.settings()
        settings.set(settings.USE_WORLD_COORDS, True)

        # 1. 대상 객체 필터링 (IfcSpace + 이름 필터)
        target_elements = [
            e for e in ifc_file.by_type("IfcSpace")
            if target_name in (e.Name or "")
        ]
        print("대상 객체:", target_elements)
        # 2. 간섭 판단 객체 필터링 (Pset 내 'cpted.객체구분' 값 기준)
        blocker_elements = [
            e for e in ifc_file.by_type("IfcElement")
            if get_psets(e).get("cpted", {}).get("객체구분") == blocker_name
        ]
        print("간섭 판단 객체:", blocker_elements)

        # 3. Geometry Tree 구성 (BVH)
        tree = ifcopenshell.geom.tree()
        iterator = ifcopenshell.geom.iterator(settings, ifc_file, multiprocessing.cpu_count())
        if iterator.initialize():
            while True:
                tree.add_element(iterator.get())  # Triangulated mesh로 BVH 생성
                if not iterator.next():
                    break
        # 4. 충돌(간섭) 검사
        clashes = tree.clash_intersection_many(
            target_elements,
            blocker_elements,
            tolerance=0.002,
            check_all=True,
        )
        print("충돌 검사 결과:", clashes)
        print("충돌된 객체 수:", len(clashes))
        
        for clash in clashes:
            print(clash.b.get_argument("GlobalId"), clash.b.get_argument("Name"))
            a_element = ifc_file.by_id(clash.a.get_argument("GlobalId"))
            b_element = ifc_file.by_id(clash.b.get_argument("GlobalId"))
            psets_a_element = ifcopenshell.util.element.get_psets(a_element)
            psets_b_element = ifcopenshell.util.element.get_psets(b_element)
            cpted_a = psets_a_element.get("cpted", {})
            cpted_b = psets_b_element.get("cpted", {})
            print(cpted_a)
            print(cpted_b)
            # cpted 속성 추가
                        
            if attribute_name not in cpted_b:
                print('속성이름없음')

                # Pset이 없으면 먼저 Pset을 생성
                run("pset.add_pset", ifc_file, product=b_element, name="cpted")

            pset_entity = None
            for rel in ifc_file.get_inverse(b_element):
                if rel.is_a("IfcRelDefinesByProperties"):
                    if rel.RelatingPropertyDefinition.is_a("IfcPropertySet"):
                        if rel.RelatingPropertyDefinition.Name == "cpted":
                            pset_entity = rel.RelatingPropertyDefinition
                            break

            if pset_entity:
                # Pset에 속성 추가
                run("pset.edit_pset", ifc_file, pset=pset_entity, properties={
                    attribute_name: True
                })
            else:
                print("⚠️ Pset을 찾을 수 없음")        
        ifc_file.write(bpy.data.scenes["Scene"].BIMProperties.ifc_file)
        bpy.ops.bim.revert_project()

        return {'FINISHED'}



# ---전처리2---(type : Geometry 기반 높이정보 데이터입력 자동화)
class Panel_preprocess2(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CPTED 전처리"
    bl_label = "형상 기반 높이 계산"

    def draw(self, context):
        layout = self.layout
        layout.label(text="객체구분이 '나무'인 객체의 높이를 계산하여 속성에 저장합니다.")
        layout.operator("object.preprocess2")


class Operator_preprocess2(bpy.types.Operator):
    bl_idname = "object.preprocess2"
    bl_label = "높이 계산 및 속성 입력"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        ifc_file = ifcopenshell.open(bpy.data.scenes["Scene"].BIMProperties.ifc_file)
        settings = ifcopenshell.geom.settings()
        settings.set(settings.USE_WORLD_COORDS, True)
        print('시작')
        # 'cpted.객체구분' == '나무' 필터링
        tree_elements = [
            e for e in ifc_file.by_type("IfcElement")
            if get_psets(e).get("cpted", {}).get("객체구분") == "나무"
        ]
        print(f"🎋 '나무' 객체 수: {len(tree_elements)}")

        for element in tree_elements:
            try:
                shape = ifcopenshell.geom.create_shape(settings, element)
                verts = np.array(shape.geometry.verts).reshape(-1, 3)

                z_min = verts[:, 2].min()
                z_max = verts[:, 2].max()
                height = round(float(z_max - z_min), 2)
                print(f"{element.Name} 높이: {height}m")

                # Pset이 없으면 생성
                run("pset.add_pset", ifc_file, product=element, name="cpted")

                # Pset 엔티티 가져오기
                pset_entity = None
                for rel in ifc_file.get_inverse(element):
                    if rel.is_a("IfcRelDefinesByProperties") and rel.RelatingPropertyDefinition.Name == "cpted":
                        pset_entity = rel.RelatingPropertyDefinition
                        break

                if pset_entity:
                    run("pset.edit_pset", ifc_file, pset=pset_entity, properties={
                        "높이": height
                    })
            except Exception as e:
                print(f"⚠️ {element.Name} 처리 중 오류 발생: {str(e)}")

        # 저장 및 리로드
        ifc_file.write(bpy.data.scenes["Scene"].BIMProperties.ifc_file)
        bpy.ops.bim.revert_project()
        self.report({'INFO'}, "전처리2 완료: 높이 속성 입력 완료")
        return {'FINISHED'}






# --- 등록 클래스 목록 ---
classes = [
    CNVProperties,
    # --- 체크리스트1 ---
    Operator_checklist1,
    Operator_checklist1_reset,
    Panel_checklist1,

    # -- 체크리스트2 ---
    Operator_checklist2,
    Operator_checklist2_reset,
    Panel_checklist2,

    # --- 전처리1 ---
    Panel_preprocess1,
    Operator_preprocess1,

    # --- 전처리2 ---
    Panel_preprocess2,
    Operator_preprocess2,


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
def create_ray_line(location, direction, ray_length, rayline_name, color=(1.0, 0.0, 0.0, 1.0), radius=0.02):
    """
    Blender 내에 ray 방향으로 실린더(튜브)를 생성하여 색상 적용 가능한 선 오브젝트로 만듭니다.

    Parameters:
    - location: 시작점 좌표 (tuple)
    - direction: 방향 벡터 (정규화된 튜플)
    - ray_length: 길이 (float)
    - rayline_name: 오브젝트 이름 (str)
    - color: RGBA 색상 튜플 (예: (1.0, 0.0, 0.0, 1.0))
    - radius: 실린더의 반지름
    """
    import mathutils

    # 중심점과 회전 계산
    start = mathutils.Vector(location)
    end = start + mathutils.Vector(direction) * ray_length
    center = (start + end) / 2

    # 기본 실린더 생성 (Z축 방향)
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=ray_length, location=center)
    obj = bpy.context.active_object
    obj.name = rayline_name

    # 실린더 회전 방향 설정
    up = mathutils.Vector((0, 0, 1))  # 기본 생성 방향
    dir_vec = (end - start).normalized()
    rotation_quat = up.rotation_difference(dir_vec)
    obj.rotation_mode = 'QUATERNION'
    obj.rotation_quaternion = rotation_quat

    # 머티리얼 생성 및 색상 적용
    mat_name = f"{rayline_name}_Mat"
    mat = bpy.data.materials.get(mat_name)
    if not mat:
        mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = False
    mat.diffuse_color = color
    obj.data.materials.append(mat)

    return obj


