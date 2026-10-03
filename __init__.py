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

# Определяем варианты разрешения текстур
texture_res_items = [
    ('1024', "1K (1024x1024)", "Запекать в разрешении 1024x1024"),
    ('2048', "2K (2048x2048)", "Запекать в разрешении 2048x2048"),
    ('4096', "4K (4096x4096)", "Запекать в разрешении 4096x4096"),
]

bl_info = {
    "name": "Maps creator",
    "author": "Vitaly Kotsur",
    "description": "Maps baker",
    "blender": (2, 80, 0),
    "version": (0, 0, 1),
    "location": "",
    "warning": "",
    "category": "Generic",
}


class OBJECT_OT_bake_normals(bpy.types.Operator):
    """Bake normals for all objects from LP and HP collections"""
    bl_idname = "object.bake_normals"
    bl_label = "Bake normal Map"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        # Button is active only in Object Mode
        if context.mode != 'OBJECT':
            return False

        # Check if LP collection exists and has objects
        lp_col = bpy.data.collections.get("LP")
        if not lp_col or not lp_col.objects:
            return False

        # Check if HP collection exists and has objects
        hp_col = bpy.data.collections.get("HP")
        if not hp_col or not hp_col.objects:
            return False

        return True

    def execute(self, context):
        # === ШАГ 0: ВАЛИДАЦИЯ UV-КАРТ НА LOW-POLY ===
        lp_objects = list(bpy.data.collections["LP"].objects)
        missing_uv_objects = []

        for obj in lp_objects:
            # Проверяем только объекты типа MESH (игнорируем пустышки, камеры и т.д.)
            if obj.type == 'MESH':
                # Если список слоев UV пуст, добавляем имя объекта в список ошибок
                if not obj.data.uv_layers:
                    missing_uv_objects.append(obj.name)

        # Если нашли хотя бы один объект без UV, останавливаем процесс и выводим ошибку
        if missing_uv_objects:
            error_msg = f"Error: objects missing UV-maps: {', '.join(missing_uv_objects)}"
            self.report({'ERROR'}, error_msg)
            return {'CANCELLED'}
            
        self.report({'INFO'}, "Geometry proccessing...")
        # Save links to originally active and selected objects
        original_active = context.view_layer.objects.active
        original_selected = list(context.selected_objects)

        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        # Clear selection
        bpy.ops.object.select_all(action='DESELECT')    

        # === КРОК 1: ОБ'ЄДНАННЯ LOW-POLY (LP) ===
        lp_objects = list(bpy.data.collections["LP"].objects)
        lp_duplicates = []

        for obj in lp_objects:
            # Дублюємо об'єкт
            obj_copy = obj.copy()
            obj_copy.data = obj.data.copy() # Копіюємо сам меш
            context.scene.collection.objects.link(obj_copy) # Лінкуємо в сцену
            obj_copy.select_set(True) # Виділяємо копію
            lp_duplicates.append(obj_copy)

        # Робимо останню копію активною для об'єднання
        context.view_layer.objects.active = lp_duplicates[-1]

        # Об'єднуємо всі виділені копії LP в один меш
        bpy.ops.object.join()
        merged_lp = context.view_layer.objects.active
        merged_lp.name = "_Bake_Merged_LowPoly"

        # Знімаємо виділення з об'єднаного LP
        bpy.ops.object.select_all(action='DESELECT')

        # === КРОК 2: ОБ'ЄДНАННЯ HIGH-POLY (HP) ===
        hp_objects = list(bpy.data.collections["HP"].objects)
        hp_duplicates = []

        for obj in hp_objects:
            obj_copy = obj.copy()
            obj_copy.data = obj.data.copy()
            context.scene.collection.objects.link(obj_copy)
            obj_copy.select_set(True)
            hp_duplicates.append(obj_copy)

        context.view_layer.objects.active = hp_duplicates[-1]
        
        # Об'єднуємо всі копії HP в один меш
        bpy.ops.object.join()
        merged_hp = context.view_layer.objects.active
        merged_hp.name = "_Bake_Merged_HighPoly"

        # === КРОК 3: ПІДГОТОВКА ДО SELECTED TO ACTIVE ===
        # Для запікання Selected to Active: High-Poly має бути ВИДІЛЕНИМ,
        # а Low-Poly має бути ВИДІЛЕНИМ ТА АКТИВНИМ.
        bpy.ops.object.select_all(action='DESELECT')
        
        merged_hp.select_set(True) # Selected (High)
        merged_lp.select_set(True) # Selected (Low)
        context.view_layer.objects.active = merged_lp # Active (Low)

        # === ШАГ 3.5: АВТОМАТИЧЕСКОЕ СОЗДАНИЕ ТЕКСТУРЫ И МАТЕРИАЛА ===
        self.report({'INFO'}, "Texture generation...")

        # Получаем выбранное пользователем разрешение из настроек сцены
        res = int(context.scene.smart_bake_resolution)
        
        # Creating textures in Blender DB
        tex_smooth_name = "T_Bake_Normal_Smooth"
        tex_flat_name = "T_Bake_Normal_Flat"
        tex_mask_name = "T_Bake_Skew_Mask"

        # Функція-помічник для безпечного перестворення текстур (щоб не плодити дублікати)
        def get_or_create_image(name, width, height, is_color=False):
            # Если текстура с таким именем уже была, удаляем ее, чтобы не плодить дубликаты
            if name in bpy.data.images:
                bpy.data.images.remove(bpy.data.images[name])
            img = bpy.data.images.new(name=name, width=width, height=height, alpha=False, float_buffer=False)
            if not is_color:
                img.colorspace_settings.name = 'Non-Color'
            return img

        # 1. Створюємо карти нормалей (Non-Color) та маску (можна sRGB, але заливаємо чорним)
        img_smooth = get_or_create_image(tex_smooth_name, res, res, is_color=False)
        img_flat = get_or_create_image(tex_flat_name, res, res, is_color=False)
        
        # Маску ініціалізуємо повністю чорним кольором (щоб спочатку показувало суто Smooth normal)
        img_mask = get_or_create_image(tex_mask_name, res, res, is_color=True)
        img_mask.generated_color = (0.0, 0.0, 0.0, 1.0)

        # 2. Очищаем все старые материалы с объединенного Low-Poly объекта
        merged_lp.data.materials.clear()
        
        # 3. Создаем один единственный чистый материал для запекания
        bake_mat = bpy.data.materials.new(name="M_SmartBake_Internal")
        bake_mat.use_nodes = True
        merged_lp.data.materials.append(bake_mat)

        nodes = bake_mat.node_tree.nodes
        
        # Создаем ноды текстур нормалей
        node_smooth = nodes.new(type='ShaderNodeTexImage')
        node_smooth.image = img_smooth
        node_smooth.label = "Bake Target: SMOOTH"
        node_smooth.location = (-600, 400)
        
        node_flat = nodes.new(type='ShaderNodeTexImage')
        node_flat.image = img_flat
        node_flat.label = "Bake Target: FLAT"
        node_flat.location = (-600, 150)
               
        # Создаем ноду маски
        node_mask = nodes.new(type='ShaderNodeTexImage')
        node_mask.image = img_mask
        node_mask.label = "Paint Mask"
        node_mask.location = (-600, -100)
                
        # Nodes links for future use
        self.node_smooth_ref = node_smooth
        self.node_flat_ref = node_flat
        self.node_mask_ref = node_mask

        self.report({'INFO'}, f"Textures {res}x{res} ready. Nodes compiled.")    

        # === ШАГ 4: НАЛАШТУВАННЯ CYCLES ПЕРЕД ЗАПІКАННЯМ ===
        self.report({'INFO'}, "Geometry ready. Preparing Cycles...")
        scene = context.scene
        render_settings = scene.render
        cycles_settings = scene.cycles
        
        # 1. Примусово перемикаємо на Cycles (запікання нормалей працює тільки в ньому)
        render_settings.engine = 'CYCLES'
     
        # 3. Оптимізуємо Samples (для запікання карт нормалей 16-32 семплів більш ніж достатньо, 
        # великі значення лише марнують час і не впливають на якість векторів)
        cycles_settings.bake_samples = 16
        
        # 4. Налаштовуємо параметри запікання в Cycles
        bake_settings = scene.render.bake
        
        # Виставляємо тип запікання — Тільки Карта Нормалей
        bake_settings.use_selected_to_active = True
        
        # Отримуємо значення Extrusion з повзунка нашої панелі (створимо його на наступному кроці)
        bake_settings.margin = 16  # Падінг текстури (Margin) за замовчуванням 16 пікселів
        bake_settings.cage_extrusion = scene.smart_bake_extrusion
        
        # Залишаємо Max Ray Distance в 0 (нескінченність), щоб Cycles сам знаходив хай-полі
        bake_settings.max_ray_distance = 0.0

        # === ШАГ 5: ЗАПУСК ПОСЛІДОВНОГО ПОДВІЙНОГО ЗАПІКАННЯ ===
        
        # --- ПРОХІД 1: SMOOTH NORMAL (Для бевелів) ---
        self.report({'INFO'}, "Pass 1 Start: Smooth Normal Baking...")
        
        # Переконуємося, що Low-Poly меш має Smooth затінення
        bpy.ops.object.shade_smooth()
        
        # Робимо активною ноду Smooth текстури
        bake_mat.node_tree.nodes.active = self.node_smooth_ref
        self.node_smooth_ref.select = True
        
        # Викликаємо вбудований бейк Блендера (код засинає, поки Cycles рендерить)
        bpy.ops.object.bake(type='NORMAL')
        
        
        # --- ПРОХІД 2: FLAT NORMAL (Для болтів) ---
        self.report({'INFO'}, "Pass 2 Start: Flat Normal Baking...")
        
        # Тимчасово перемикаємо об'єднаний Low-Poly у Flat Shading
        bpy.ops.object.shade_flat()
        
        # Перемикаємо активність на ноду Flat текстури
        bake_mat.node_tree.nodes.active = self.node_flat_ref
        self.node_flat_ref.select = True
        
        # Запускаємо другий бейк
        bpy.ops.object.bake(type='NORMAL')
        
        
        # Повертаємо початковий Smooth шейдінг назад
        bpy.ops.object.shade_smooth()
        
        # Робимо активною ноду маски, щоб користувач міг одразу малювати
        bake_mat.node_tree.nodes.active = self.node_mask_ref
        self.node_mask_ref.select = True

        self.report({'INFO'}, "Batch baking finished! Both textures ready.")

        # === Step 6: Mix shader ===
        self.report({'INFO'}, "Final shader creation...")
        
        # 1. Mix node
        node_mix = nodes.new(type='ShaderNodeMix')
        node_mix.data_type = 'RGBA' 
        node_mix.blend_type = 'MIX'
        node_mix.location = (-200, 250)

        # 2. Normal Map node
        node_normal_map = nodes.new(type='ShaderNodeNormalMap')
        node_normal_map.location = (50, 250)

        # 3. Looking for Principled BSDF
        principled_node = None
        for n in nodes:
            if n.type == 'BSDF_PRINCIPLED':
                principled_node = n
                break
        
        # If Principled BSDF is absent, lets simply use Material Output
        if not principled_node:
            for n in nodes:
                if n.type == 'OUTPUT_MATERIAL':
                    bake_mat.node_tree.links.new(node_mix.outputs['Result'], n.inputs['Surface'])
                    break
        
        # 4. Linking nodes
        links = bake_mat.node_tree.links
        
        # Smooth Normal -> slot A
        links.new(self.node_smooth_ref.outputs['Color'], node_mix.inputs['A'])
        
        # Flat Normal -> slot B
        links.new(self.node_flat_ref.outputs['Color'], node_mix.inputs['B'])
        
        # Connecting mask to Mix node Factor slot
        links.new(self.node_mask_ref.outputs['Color'], node_mix.inputs['Factor'])
        
        # If we have Principled BSDF, using Normal Map through Normal slot
        if principled_node:
            links.new(node_mix.outputs['Result'], node_normal_map.inputs['Color'])
            links.new(node_normal_map.outputs['Normal'], principled_node.inputs['Normal'])

        # === ШАГ 7: ПОДГОТОВКА ИНТЕРФЕЙСА К РИСОВАНИЮ ===
        
        # Activate mask node for future texture painting
        nodes.active = self.node_mask_ref
        self.node_mask_ref.select = True

        # Enable Material Preview in the viewport
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        space.shading.type = 'MATERIAL'

        self.report({'INFO'}, "Baking finished!")
        return {'FINISHED'}



class OBJECT_OT_create_collection(bpy.types.Operator):
    "Create collection from selected"
    bl_idname = "object.create_collection"
    bl_label = "Create Collection"
    bl_options = {"REGISTER", "UNDO"}

    col_name: bpy.props.StringProperty(default="LP")

    @classmethod
    def poll(cls, context): 
        return context.mode == 'OBJECT'

    def execute(self, context):
        selected_objs = context.selected_objects

        if not selected_objs:
            self.report({'WARNING'}, "No selected objects!")
            return {'CANCELLED'}
        name = self.col_name

        # Check if collection exist, else create new
        if name in bpy.data.collections:
            target_col = bpy.data.collections[name]
        else:
            target_col = bpy.data.collections.new(name)
            context.scene.collection.children.link(target_col)
       
        # Transfer each selected object
        for obj in selected_objs:
            # Check if object is not linked to target
            if obj.name not in target_col.objects:
                target_col.objects.link(obj)
                # Safely delete from old collections
                for old_col in list(obj.users_collection):
                    if old_col != target_col:
                        old_col.objects.unlink(obj)
            
        self.report({'INFO'}, f"Added {len(selected_objs)} objects to collection {self.col_name}")
        return {'FINISHED'}
        

class VIEW3D_PT_maps_panel(bpy.types.Panel):

    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Maps creator"
    bl_label = "Maps creator"

    def draw(self, context):

        layout = self.layout
        scene = context.scene
        # Get collections data to print statistics
        lp_col = bpy.data.collections.get("LP")
        hp_col = bpy.data.collections.get("HP")
        
        lp_count = len(lp_col.objects) if lp_col else 0
        hp_count = len(hp_col.objects) if hp_col else 0
        layout.label(text="Models for Baking")
        
        # Low-Poly button
        row = layout.row(align=True)
        op_lp = row.operator("object.create_collection", text=f"Add to Low-Poly ({lp_count} pcs)", icon='MESH_ICOSPHERE')
        op_lp.col_name = "LP" 

        # High-Poly button
        row = layout.row(align=True)
        op_hp = row.operator("object.create_collection", text=f"Add to High-Poly ({hp_count} pcs)", icon='MESH_MONKEY')
        op_hp.col_name = "HP"
        layout.separator()
        # Baking Button
        layout.label(text="Baking textures:")
        col = layout.column(align=True)
        
        col.operator("object.bake_normals", text="Bake Normals", icon='MESH_MONKEY')
        # Context warning when button is inactive
        if lp_count == 0 or hp_count == 0:
            box = col.box()
            box.scale_y = 0.8
            if lp_count == 0 and hp_count == 0:
                box.label(text="Add objects to LP and HP!", icon='ERROR')
            elif lp_count == 0:
                box.label(text="Low-Poly collection (LP) is empty!", icon='ERROR')
            elif hp_count == 0:
                box.label(text="High-Poly collection (HP) is empty!", icon='ERROR')
        layout.separator()
        layout.label(text="Texture settings:")
        layout.prop(scene, "smart_bake_resolution", text="Resolution")
        layout.prop(scene, "smart_bake_extrusion", text="Ray Height")




classes = [VIEW3D_PT_maps_panel, OBJECT_OT_create_collection, OBJECT_OT_bake_normals,]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.smart_bake_resolution = bpy.props.EnumProperty(
        items=texture_res_items,
        name="Resolution",
        default='2048'
    )
    bpy.types.Scene.smart_bake_extrusion = bpy.props.FloatProperty(
        name="Ray Offset (Extrusion)",
        description="Ray Height",
        default=0.05,  
        min=0.0,
        max=10.0,
        subtype='DISTANCE' # Show units of measurement
    )
        


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.smart_bake_resolution
    del bpy.types.Scene.smart_bake_extrusion