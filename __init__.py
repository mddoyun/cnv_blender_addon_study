# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import bpy
import ifcopenshell
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


# --- 프로퍼티 추가를 위해 새 클래스를 생성 ---
class CNVProperties(bpy.types.PropertyGroup):
    ray_count_input: bpy.props.IntProperty(name="RAY 개수")
    ray_length_input: bpy.props.FloatProperty(name="RAY 거리(m)")

    last_cross_count: bpy.props.IntProperty(
        name="간섭 수", default=0
    )  # ✅ 추가: 간섭 수 표시용 프로퍼티


class Operator_cnv_test(bpy.types.Operator):
    "Adds a cube for sure"

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
        print("ifc_file : ", ifc_file)
        list_of_target = ifcopenshell.util.selector.filter_elements(
            ifc_file, "My_Data.cnv_class=target"
        )
        print(list_of_target)
        # 변수 설정
        RAY_COUNT = ray_count_input_value
        RAY_LENGTH = ray_length_input_value  # (m기준)

        # geom 세팅 생성
        settings = ifcopenshell.geom.settings()
        settings.set(settings.USE_WORLD_COORDS, True)

        # geom tree (ray) 세팅
        tree = ifcopenshell.geom.tree()
        settings = ifcopenshell.geom.settings()
        iterator = ifcopenshell.geom.iterator(
            settings, ifc_file, multiprocessing.cpu_count()
        )
        if iterator.initialize():
            while True:
                # Use triangulation to build a BVH tree
                # tree.add_element(iterator.get())

                # Alternatively, use this code to build an unbalanced binary tree
                tree.add_element(iterator.get_native())

                if not iterator.next():
                    break

        # Target 객체 반복
        i = 1
        cross_list_list = []
        for element in list_of_target:
            print("---------", i, "번째 Target객체 ---------")
            print("Name : ", element.Name)
            # shape 가져오기
            shape = ifcopenshell.geom.create_shape(settings, element)
            geometry = shape.geometry
            matrix = ifcopenshell.util.shape.get_shape_matrix(shape)
            location = matrix[:, 3][0:3]
            verts = np.array(geometry.verts).reshape(-1, 3)

            # 튜플 형태로 변환 (예: (0., 0., 0.))
            location_tuple = tuple(map(float, location))
            print("Location:", location_tuple)

            # ray 반복
            cross_count = 0

            cross_list = []
            for j in range(RAY_COUNT):
                angle_deg = j * (360 / RAY_COUNT)
                angle_rad = math.radians(angle_deg)

                # direction 벡터 계산 (XY 평면에서 Z는 0)
                direction = (math.cos(angle_rad), math.sin(angle_rad), 0.1)
                print(tuple(round(x, 3) for x in direction))
                # 정규화 (단위 벡터 보장)
                norm = math.sqrt(direction[0] ** 2 + direction[1] ** 2)
                direction = (direction[0] / norm, direction[1] / norm, 0.1)

                # ray 쏘기
                results = tree.select_ray(location_tuple, direction, length=RAY_LENGTH)
                if len(results) > 0:
                    cross_list.append(1)
                    cross_count += 1
                else:
                    cross_list.append(0)
            cross_list_list.append(cross_list)
            print("간섭 수:", cross_count)
            context.scene.cnv_props.last_cross_count = cross_count
            # for result in results:
            #     print(ifc_file.by_id(result.instance.id())) # The element the ray intersects with
            #     # print(list(result.position)) # The XYZ intersection point
            #     print(result.distance) # The distance between the ray origin and the intersection
            #     # print(list(result.normal)) # The normal of the face being intersected
            #     print(result.dot_product) # The dot product of the face being intersected with the ray

        return {"FINISHED"}


class Panel_view3d_ui_cnv_test(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CNV Test"
    bl_label = "CNV Test"

    def draw(self, context):
        layout = self.layout
        cnv_props = context.scene.cnv_props

        row = layout.row(align=True)
        # 텍스트 입력창 추가
        row.prop(cnv_props, "ray_count_input")
        row.prop(cnv_props, "ray_length_input")

        # 버튼 추가
        layout.operator("object.add_cube")
        # ✅ 간섭 수 출력 라벨
        layout.label(text=f"간섭 수: {cnv_props.last_cross_count}")


# 등록할 클래스 모음
classes = [
    CNVProperties,
    Operator_cnv_test,
    Panel_view3d_ui_cnv_test,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.cnv_props = bpy.props.PointerProperty(type=CNVProperties)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.cnv_props
