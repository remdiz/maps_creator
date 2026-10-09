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

# ============================TODO======================================
#   - Testing https://share.google/aimode/3KIwIqBOAgwVyvUNi
#   - Get rid of using names of objects and materials, use references instead
#   - Cursor change
# ==================================================================

import bpy
import bmesh
import os
import time


texture_res_items = [
    ('1024', "1K (1024x1024)", "Bake resolution 1024x1024"),
    ('2048', "2K (2048x2048)", "Bake resolution 2048x2048"),
    ('4096', "4K (4096x4096)", "Bake resolution 4096x4096"),
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

    # =======================================================================
    # CLASS VARIABLES (Global configuration for temporary assets)
    # =======================================================================
    MERGED_LP_NAME = "_Bake_Merged_LowPoly"
    MERGED_HP_NAME = "_Bake_Merged_HighPoly"
    MATERIAL_NAME = "M_SmartBake_Internal"
    TEX_SMOOTH_NAME = "T_Bake_Normal_Smooth"
    TEX_FLAT_NAME = "T_Bake_Normal_Flat"
    TEX_MASK_NAME = "T_Bake_Skew_Mask"


    @classmethod
    def delete_object(cls, target):
        """Completely remove target mesh object (assumes target exist)"""
        # if target.name in bpy.data.objects:
            # Unlink from all collections first
            # for col in list(target.users_collection):
            #     col.objects.unlink(target)
            # Remove object and mesh data blocks from memory
        target_mesh_data = target.data
        bpy.data.objects.remove(target, do_unlink=True)
        if target_mesh_data and target_mesh_data.users == 0:
                bpy.data.meshes.remove(target_mesh_data, do_unlink=True)
    
    @classmethod
    def cleanup_assets(cls, context, clean_geometry=True, clean_materials=True, clean_textures=True):
        """Safely removes temporary baking assets from Blender database"""
        scene = context.scene
        
        # 1. Clean up temporary meshes and objects
        if clean_geometry:
            # Safely extract references to memory blocks
            lp_obj = scene.smart_bake_merged_lp_obj
            hp_obj = scene.smart_bake_merged_hp_obj
            
            for obj in [lp_obj, hp_obj]:
                if obj:
                    cls.delete_object(obj)
            
            # Clear pointers from scene database to mark them empty
            scene.smart_bake_merged_lp_obj = None
            scene.smart_bake_merged_hp_obj = None
            # for name in [cls.MERGED_LP_NAME, cls.MERGED_HP_NAME]:
            #     obj = bpy.data.objects.get(name)
            #     if obj:
            #         cls.delete_object(obj)

        # 2. Clean up temporary material
        if clean_materials:
            mat = bpy.data.materials.get(cls.MATERIAL_NAME)
            if mat:
                bpy.data.materials.remove(mat, do_unlink=True)

        # 3. Clean up temporary images/textures
        if clean_textures:
            for name in [cls.TEX_SMOOTH_NAME, cls.TEX_FLAT_NAME, cls.TEX_MASK_NAME]:
                img = bpy.data.images.get(name)
                if img:
                    bpy.data.images.remove(img, do_unlink=True)
        

    
    @classmethod
    def poll(cls, context):
        # Button is active only in Object Mode
        # TODO: redundant maybe, check later
        if context.mode != 'OBJECT':
            return False

        # Check if LP collection exists and has objects
        # lp_col = bpy.data.collections.get("LP")
        # if not lp_col or not lp_col.objects:
        #     return False

        # Check if HP collection exists and has objects
        # hp_col = bpy.data.collections.get("HP")
        # if not hp_col or not hp_col.objects:
        #     return False

        scene = context.scene
        # FIXED: Access references directly from Scene data model
        lp_col = scene.smart_bake_lp_collection
        hp_col = scene.smart_bake_hp_collection
        
        if not lp_col or not lp_col.objects:
            return False
        if not hp_col or not hp_col.objects:
            return False

        return True


    @classmethod
    def _prepare_and_merge_collection(cls, context, collection, target_merged_name):
        """Duplicates mesh objects from a collection, applies modifiers, and merges them into one"""
        # collection = bpy.data.collections.get(collection_name)
        bm = bmesh.new()
        # Create a new empty mesh and object to join the selected objects into
        new_mesh = bpy.data.meshes.new(target_merged_name)
        new_object = bpy.data.objects.new(target_merged_name, new_mesh)

        # duplicates = []

        depsgraph = context.evaluated_depsgraph_get()

        # Duplicate and apply modifiers via bmesh
        for obj in collection.objects:
            if obj.type == 'MESH':
                # Duplicate object w/o using operators
                object_eval = obj.evaluated_get(depsgraph)
                mesh_from_eval = bpy.data.meshes.new_from_object(object_eval)
                matrix = obj.matrix_world

                # Apply the object's transform matrix to the mesh using a copy. this is just one way to do this,
                # you could also use bm.transform, etc.
                mesh_copy = mesh_from_eval.copy()
                mesh_copy.transform(matrix)

                # Add the transformed mesh to the bmesh
                bm.from_mesh(mesh_copy)

                # new_obj = bpy.data.objects.new(obj.name, mesh_from_eval)
                # context.scene.collection.objects.link(new_obj)
                # duplicates.append(new_obj)
                
                # obj_copy = obj.copy()
                # obj_copy.data = obj.data.copy()
                # context.scene.collection.objects.link(obj_copy)
                
                # # Make it active to apply modifiers via mesh conversion safely
                # context.view_layer.objects.active = obj_copy
                # obj_copy.select_set(True)
                # bpy.ops.object.convert(target='MESH')
                
                # # Refresh reference and save to list
                # obj_copy = context.view_layer.objects.active
                # duplicates.append(obj_copy)

        # Convert the bmesh to the new mesh
        bm.to_mesh(new_mesh)
        # Link the new object to the scene and select it
        context.scene.collection.objects.link(new_object)
  
        # # Merge duplicates together
        # context.view_layer.objects.active = duplicates[-1]
        # for d in duplicates:
        #     d.select_set(True)

        # bpy.ops.object.join()
        
        # merged_mesh = context.view_layer.objects.active
        # merged_mesh.name = target_merged_name
        
        # Deselect the output object to clear context for the next steps
        # bpy.ops.object.select_all(action='DESELECT')
        bm.free()
        return new_object


    def execute(self, context):
        start_time = time.time()
        scene = context.scene
        # Run pre-bake cleanup to wipe any leftovers from previous sessions
        self.report({'INFO'}, "Performing pre-bake cleanup...")
        self.cleanup_assets(context)
        self.report({'INFO'}, f"Cleanup complete in {time.time() - start_time:.2f}s.")
        
        # === Step 0: UV MAPS VALIDATION ON LOW-POLY ===
        lp_objects = scene.smart_bake_lp_collection.objects
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
        # TODO: maybe later?
        # original_active = context.view_layer.objects.active
        # original_selected = context.selected_objects

        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        # Clear selection
        bpy.ops.object.select_all(action='DESELECT')    

        # === Step 1: MERGING LOW-POLY (LP) ===
        self.report({'INFO'}, "Processing and merging Low-Poly collection...")
        merged_lp = self._prepare_and_merge_collection(context, scene.smart_bake_lp_collection, self.MERGED_LP_NAME)
        scene.smart_bake_merged_lp_obj = merged_lp


        # === STEP 2: MERGING HIGH-POLY (HP) ===
        self.report({'INFO'}, "Processing and merging High-Poly collection...")
        merged_hp = self._prepare_and_merge_collection(context, scene.smart_bake_hp_collection, self.MERGED_HP_NAME)
        scene.smart_bake_merged_hp_obj = merged_hp

        # === STEP 3: PREPARE SELECTED TO ACTIVE ===
        # Для запікання Selected to Active: High-Poly має бути ВИДІЛЕНИМ,
        # а Low-Poly має бути ВИДІЛЕНИМ ТА АКТИВНИМ.
        bpy.ops.object.select_all(action='DESELECT')
        
        merged_hp.select_set(True) # Selected (High)
        merged_lp.select_set(True) # Selected (Low)
        context.view_layer.objects.active = merged_lp # Active (Low)

        # === STEP 3.5: AUTOMATIC TEXTURES AND MATERIAL CREATION ===
        self.report({'INFO'}, "Texture generation...")

        # Получаем выбранное пользователем разрешение из настроек сцены
        res = int(context.scene.smart_bake_resolution)
        
        # Creating textures in Blender DB
        tex_smooth_name = self.TEX_SMOOTH_NAME # "T_Bake_Normal_Smooth"
        tex_flat_name = self.TEX_FLAT_NAME # "T_Bake_Normal_Flat"
        tex_mask_name = self.TEX_MASK_NAME # "T_Bake_Skew_Mask"

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

        def create_texture_node(nodes_obj, img, label, loc):
            t_node = nodes_obj.new(type='ShaderNodeTexImage')
            t_node.image = img
            t_node.label = label
            t_node.location = loc
            return t_node
        

        # Nodes links for future use
        # Normal texture nodes creation
        self.node_smooth_ref = create_texture_node(nodes, img_smooth, "Bake Target: SMOOTH", (-600, 400))
        self.node_flat_ref = create_texture_node(nodes, img_flat, "Bake Target: FLAT", (-600, 150))
        # Mask node creation
        self.node_mask_ref = create_texture_node(nodes, img_mask, "Paint Mask", (-600, -100))

        self.report({'INFO'}, f"Textures {res}x{res} ready. Nodes compiled.")    

        # === STEP 4: CYCLES CONFIGURATION ===
        self.report({'INFO'}, "Geometry ready. Preparing Cycles...")
        
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

        # === STEP 5: SEQUENTIAL DUAL BAKING ===
        
        # --- Pass 1: SMOOTH NORMAL (For bevels) ---
        self.report({'INFO'}, "Pass 1 Start: Smooth Normal Baking...")
        
        # bpy.ops.object.shade_smooth()
        # Low-level Python loop to force Smooth shading directly in memory
        for poly in merged_lp.data.polygons:
            poly.use_smooth = True
        merged_lp.data.update() # Flush data changes to database

        
        # Робимо активною ноду Smooth текстури
        bake_mat.node_tree.nodes.active = self.node_smooth_ref
        self.node_smooth_ref.select = True
        
        # Execute bake inside a safe context override wrapper
        with context.temp_override(active_object=merged_lp, selected_objects=[merged_hp, merged_lp]):
            bpy.ops.object.bake(type='NORMAL')
        
        
        # --- PASS 2: FLAT NORMAL (for normal correction) ---
        self.report({'INFO'}, "Pass 2 Start: Flat Normal Baking...")
        
        # Temporarily switch merged Low-Poly to Flat Shading
        # bpy.ops.object.shade_flat()
        # Low-level Python loop to force Flat shading directly in memory
        for poly in merged_lp.data.polygons:
            poly.use_smooth = False
        merged_lp.data.update()
        
        # Activate Flat texture node
        bake_mat.node_tree.nodes.active = self.node_flat_ref
        self.node_flat_ref.select = True
        
        # Execute second bake pass safely
        with context.temp_override(active_object=merged_lp, selected_objects=[merged_hp, merged_lp]):
            bpy.ops.object.bake(type='NORMAL')
        
        
        # Reset shading state back to smooth
        # bpy.ops.object.shade_smooth()
        # Restore default Smooth shading state back via low-level API
        for poly in merged_lp.data.polygons:
            poly.use_smooth = True
        merged_lp.data.update()
        
        # Робимо активною ноду маски, щоб користувач міг одразу малювати
        bake_mat.node_tree.nodes.active = self.node_mask_ref
        self.node_mask_ref.select = True

        self.delete_object(merged_hp)

        self.report({'INFO'}, "Batch baking finished! Both textures ready.")

        # === STEP 6: MIX SHADER COMPILATION ===
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

        # === STEP 7: POST-BAKE VIEWPORT SETUP ===
        
        # Activate mask node for future texture painting
        nodes.active = self.node_mask_ref
        self.node_mask_ref.select = True

        # Enable Material Preview in the viewport
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        space.shading.type = 'MATERIAL'

        # === STEP 7.5: DISABLE INPUT COLLECTIONS VISIBILITY ===
        self.report({'INFO'}, "Hiding input LP and HP collections...")
        
        # Get the root layer collection of the current view layer
        # root_layer_col = context.view_layer.layer_collection
        
        # Loop through all sub-collections in the view layer
        # for sub_layer_col in root_layer_col.children:
        #     # If the collection name matches LP or HP, exclude it from the view layer
        #     if sub_layer_col.name in {"LP", "HP"}:
        #         sub_layer_col.exclude = True   

        children = context.view_layer.layer_collection.children
        
        # Instantly access and exclude layer collections via their names from pointers
        if scene.smart_bake_lp_collection:
            children.get(scene.smart_bake_lp_collection.name).exclude = True
        if scene.smart_bake_hp_collection:
            children.get(scene.smart_bake_hp_collection.name).exclude = True

        self.report({'INFO'}, "Baking finished!")
        return {'FINISHED'}


class OBJECT_OT_activate_skew_paint(bpy.types.Operator):
    """Switch to Texture Paint mode and activate the Skew Mask for drawing"""
    bl_idname = "object.activate_skew_paint"
    bl_label = "Paint Skew Correction"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        # Active only if the temporary low-poly bake mesh exists in the scene
        # TODO: check for mask and Normal texture existance?
        if not context.mode == 'OBJECT':
            return False
        # return bpy.data.objects.get(OBJECT_OT_bake_normals.MERGED_LP_NAME) is not None
        return context.scene.smart_bake_merged_lp_obj is not None

    def execute(self, context):
        # merged_lp = bpy.data.objects.get(OBJECT_OT_bake_normals.MERGED_LP_NAME)
        merged_lp = context.scene.smart_bake_merged_lp_obj

        if not merged_lp:
            self.report({'WARNING'}, "Temporary bake mesh not found!")
            return {'CANCELLED'}

        # 1. Ensure we are in Object Mode before changing selection
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        # 2. Make the temporary low-poly mesh active and selected
        bpy.ops.object.select_all(action='DESELECT')
        merged_lp.select_set(True)
        context.view_layer.objects.active = merged_lp

        # 3. Find the internal material and activate the mask node
        if merged_lp.data.materials:
            bake_mat = merged_lp.data.materials.get(OBJECT_OT_bake_normals.MATERIAL_NAME)
            if bake_mat and bake_mat.use_nodes:
                nodes = bake_mat.node_tree.nodes
                node_mask = nodes.get("Paint Mask") # We used this label in step 3.5
                
                if node_mask:
                    # Make mask node active so Blender paints directly onto T_Bake_Skew_Mask
                    nodes.active = node_mask
                    node_mask.select = True

        # 4. Switch Viewport to Material Preview shading style
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        space.shading.type = 'MATERIAL'

        # 5. Finally, switch Blender to Texture Paint mode
        bpy.ops.object.mode_set(mode='TEXTURE_PAINT')
        # Force brush and global unified tool color to pure white
        ts = context.tool_settings
        
        if ts.image_paint.brush:
            ts.image_paint.brush.color = (1.0, 1.0, 1.0)
            
        if hasattr(ts, "unified_paint_settings"):
            ts.unified_paint_settings.color = (1.0, 1.0, 1.0)
        
        
        self.report({'INFO'}, "Texture Paint mode active. Draw to fix normal skewing!")
        return {'FINISHED'}


# TODO: remove operator?
# class OBJECT_OT_create_collection(bpy.types.Operator):
#     "Create collection from selected"
#     bl_idname = "object.create_collection"
#     bl_label = "Create Collection"
#     bl_options = {"REGISTER", "UNDO"}

#     col_name: bpy.props.StringProperty(default="LP")

#     @classmethod
#     def poll(cls, context): 
#         return context.mode == 'OBJECT'

#     def execute(self, context):
#         selected_objs = context.selected_objects

#         if not selected_objs:
#             self.report({'WARNING'}, "No selected objects!")
#             return {'CANCELLED'}
#         name = self.col_name

#         # Check if collection exist, else create new
#         if name in bpy.data.collections:
#             target_col = bpy.data.collections[name]
#         else:
#             target_col = bpy.data.collections.new(name)
#             context.scene.collection.children.link(target_col)
       
#         # Transfer each selected object
#         for obj in selected_objs:
#             # Check if object is not linked to target
#             if obj.name not in target_col.objects:
#                 target_col.objects.link(obj)
#                 # Safely delete from old collections
#                 for old_col in list(obj.users_collection):
#                     if old_col != target_col:
#                         old_col.objects.unlink(obj)
            
#         self.report({'INFO'}, f"Added {len(selected_objs)} objects to collection {self.col_name}")
#         return {'FINISHED'}
        
class OBJECT_OT_finalize_bake(bpy.types.Operator):
    """Merge maps based on paint mask, export final image to disk and clean up scene"""
    bl_idname = "object.finalize_bake"
    bl_label = "Finalize & Export Map"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        # Active only if the temporary low-poly bake mesh exists in the scene
        # return bpy.data.objects.get(OBJECT_OT_bake_normals.MERGED_LP_NAME) is not None
        return context.scene.smart_bake_merged_lp_obj is not None

    def execute(self, context):
        scene = context.scene
        filename = scene.smart_bake_filename
        res = int(scene.smart_bake_resolution)

        # Ensure the .blend project file is saved to resolve the disk path
        if not bpy.data.is_saved:
            self.report({'ERROR'}, "Save your .blend file first to export textures!")
            return {'CANCELLED'}
            
        # Get path of the current project directory and define final image path
        project_dir = bpy.path.abspath("//")
        final_filepath = os.path.join(project_dir, f"{filename}.png")
        
        self.report({'INFO'}, "Compiling and exporting final combined map...")

        # === 1. ACCESS THE INTERNAL MATERIAL AND CONNECT MIX TO EMISSION ===
        # merged_lp = bpy.data.objects.get(OBJECT_OT_bake_normals.MERGED_LP_NAME)
        merged_lp = scene.smart_bake_merged_lp_obj
        
        if not merged_lp or not merged_lp.data.materials:
            self.report({'ERROR'}, "Temporary bake mesh or material missing!")
            return {'CANCELLED'}
            
        bake_mat = merged_lp.data.materials.get(OBJECT_OT_bake_normals.MATERIAL_NAME)
        if not bake_mat or not bake_mat.use_nodes:
            self.report({'ERROR'}, "Bake material tree is broken!")
            return {'CANCELLED'}
            
        nodes = bake_mat.node_tree.nodes
        links = bake_mat.node_tree.links
        
        node_mix = None
        material_output = None
        
        for n in nodes:
            if n.type == 'MIX' and n.data_type == 'RGBA':
                node_mix = n
            elif n.type == 'OUTPUT_MATERIAL':
                material_output = n

        if not node_mix or not material_output:
            self.report({'ERROR'}, "Internal shader nodes logic missing!")
            return {'CANCELLED'}

        # Create a completely fresh, empty virtual image in memory for the final output
        # Keep alpha=False as originally intended to avoid transparency bugs
        final_img = bpy.data.images.new(name="T_SmartBake_Final_Render", width=res, height=res, alpha=False, float_buffer=False)
        final_img.colorspace_settings.name = 'Non-Color'

        # Create a temporary target texture node inside the material for Cycles to bake into
        node_final_target = nodes.new(type='ShaderNodeTexImage')
        node_final_target.image = final_img
        nodes.active = node_final_target
        node_final_target.select = True

        # Check if the DirectX normal map output format is requested by the artist
        if scene.smart_bake_directx:
            # Create math and vector nodes to dynamically invert the Green channel vector on the fly
            node_sep = nodes.new(type='ShaderNodeSeparateColor')
            node_comb = nodes.new(type='ShaderNodeCombineColor')
            node_inv_g = nodes.new(type='ShaderNodeMath')
            
            node_inv_g.operation = 'SUBTRACT'
            node_inv_g.inputs[0].default_value = 1.0 # 1.0 - Green channel = Inverted Green channel
            
            # Create a network of links to reconstruct the color channels with inverted Y axis
            links.new(node_mix.outputs['Result'], node_sep.inputs['Color'])
            
            # Pass Red and Blue channels directly untouched
            links.new(node_sep.outputs['Red'], node_comb.inputs['Red'])
            links.new(node_sep.outputs['Blue'], node_comb.inputs['Blue'])
            
            # Invert the Green channel vector mathematically
            links.new(node_sep.outputs['Green'], node_inv_g.inputs[1])
            links.new(node_inv_g.outputs['Value'], node_comb.inputs['Green'])
            
            # Connect the combined DirectX color stream to the material surface output socket
            links.new(node_comb.outputs['Color'], material_output.inputs['Surface'])
        else:
            # Route the Mix Node directly into the Material Output's Surface input
            links.new(node_mix.outputs['Result'], material_output.inputs['Surface'])

        # === 2. RUN ULTRA-FAST BACKGROUND EMIT BAKE WITH TANGENT COLOR CLEAR ===
        scene.render.engine = 'CYCLES'
        scene.cycles.bake_samples = 1 
        
        bake_settings = scene.render.bake
        bake_settings.use_selected_to_active = False 
        
        # Configure padding/margins for UV island edges
        bake_settings.margin = 16
        bake_settings.margin_type = 'EXTEND' 
        
        # FIXED: Disable image clearing before baking. 
        # This keeps our pre-filled purple pixels intact in empty background spaces.
        bake_settings.use_clear = False 

        # 100% BULLETPROOF PYTHON PIXEL FILL
        # This instantly floods the entire texture with the neutral normal purple color in RAM
        neutral_normal_pixel = [0.5, 0.5, 1.0, 1.0] # RGBA
        final_img.pixels = neutral_normal_pixel * (res * res)

        # Execute background texture color calculation pass onto the pre-filled purple image
        bpy.ops.object.bake(type='EMIT')

        # === 3. CONFIGURE IMAGE FORMAT AND SAVE DIRECTLY TO HARD DRIVE ===
        # Assign the path directly to the image object data block property
        final_img.filepath_raw = final_filepath
        
        # Setup output settings explicitly on the image itself
        final_img.file_format = 'PNG'
        
        # Use final_img.save() to write raw, untouched purple pixels directly to the disk.
        final_img.save()

        # Remove our temporary render image block from database memory
        bpy.data.images.remove(final_img, do_unlink=True)

        # === 4. SCENE CLEANUP AND RESET ===
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        # Run full asset wiping logic via bake operator class reference
        OBJECT_OT_bake_normals.cleanup_assets(context)

        # 5. RESTORE INPUT COLLECTIONS VISIBILITY
        # root_layer_col = context.view_layer.layer_collection
        # for sub_layer_col in root_layer_col.children:
        #     if sub_layer_col.name in {"LP", "HP"}:
        #         sub_layer_col.exclude = False

        children = context.view_layer.layer_collection.children
        
        # Instantly restore visibility for original artist collections
        if scene.smart_bake_lp_collection:
            children.get(scene.smart_bake_lp_collection.name).exclude = False
        if scene.smart_bake_hp_collection:
            children.get(scene.smart_bake_hp_collection.name).exclude = False
        
        
        self.report({'INFO'}, f"Successfully saved final map as: {filename}.png")
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
        # lp_col = bpy.data.collections.get("LP")
        # hp_col = bpy.data.collections.get("HP")
        
        # lp_count = len(lp_col.objects) if lp_col else 0
        # hp_count = len(hp_col.objects) if hp_col else 0
        layout.label(text="Models for Baking:")

        box_slots = layout.box()
        
        # FIXED: Draw interactive collection selectors with pipettes instead of old assignment buttons
        box_slots.prop(scene, "smart_bake_lp_collection", text="Low-Poly Collection", icon='MESH_ICOSPHERE')
        box_slots.prop(scene, "smart_bake_hp_collection", text="High-Poly Collection", icon='MESH_MONKEY')
        

        # Low-Poly button
        # row = layout.row(align=True)
        # op_lp = layout.operator(
        #     "object.create_collection", 
        #     text=f"Add to Low-Poly ({lp_count} pcs)", 
        #     icon='MESH_ICOSPHERE')
        # op_lp.col_name = "LP" 

        # High-Poly button
        # row = layout.row(align=True)
        # op_hp = layout.operator(
        #     "object.create_collection", 
        #     text=f"Add to High-Poly ({hp_count} pcs)", 
        #     icon='MESH_MONKEY')
        # op_hp.col_name = "HP"

        layout.separator()
        # Baking Button
        layout.label(text="Baking textures:")
        # col = layout.column(align=True)
        
        layout.operator("object.bake_normals", text="Bake Normals", icon='MESH_MONKEY')

        # Context warning when button is inactive
        # if lp_count == 0 or hp_count == 0:
        #     box = layout.box()
        #     box.scale_y = 0.8
        #     if lp_count == 0 and hp_count == 0:
        #         box.label(text="Add objects to LP and HP!", icon='ERROR')
        #     elif lp_count == 0:
        #         box.label(text="Low-Poly collection (LP) is empty!", icon='ERROR')
        #     elif hp_count == 0:
        #         box.label(text="High-Poly collection (HP) is empty!", icon='ERROR')

        # FIXED: Context warning checks now use the data pointers instead of hardcoded string searches
        lp_col = scene.smart_bake_lp_collection
        hp_col = scene.smart_bake_hp_collection
        
        if not lp_col or not hp_col or not lp_col.objects or not hp_col.objects:
            box_warn = layout.box()
            box_warn.scale_y = 0.8
            if not lp_col and not hp_col:
                box_warn.label(text="Assign LP and HP collections!", icon='ERROR')
            elif not lp_col or not lp_col.objects:
                box_warn.label(text="Low-Poly collection is empty or unassigned!", icon='ERROR')
            elif not hp_col or not hp_col.objects:
                box_warn.label(text="High-Poly collection is empty or unassigned!", icon='ERROR')
                
                
        # merged_lp_exists = bpy.data.objects.get(OBJECT_OT_bake_normals.MERGED_LP_NAME) is not None
        
        merged_lp_exists = scene.smart_bake_merged_lp_obj is not None
        if merged_lp_exists:
            layout.separator()
            # Highlights the button in blue/accent color to draw user's attention
            layout.operator("object.activate_skew_paint", text="Paint Skew Correction", icon='BRUSH_DATA')
            # Display the finalization button right under the brush tool
            layout.operator("object.finalize_bake", text="Finalize & Export Map", icon='DISK_DRIVE')
        layout.separator()
        layout.label(text="Texture settings:")
        # Add the text field property for user-defined texture name
        layout.prop(scene, "smart_bake_filename", text="Name")
        layout.prop(scene, "smart_bake_resolution", text="Resolution")
        # Expose the DirectX format checkbox toggler right in the settings sub-layout
        layout.prop(scene, "smart_bake_directx", text="DirectX")
        
        layout.prop(scene, "smart_bake_extrusion", text="Ray Height")




classes = [VIEW3D_PT_maps_panel, 
        #    OBJECT_OT_create_collection, 
           OBJECT_OT_bake_normals,
           OBJECT_OT_activate_skew_paint,
           OBJECT_OT_finalize_bake,]

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
    # Register custom text property for file naming
    bpy.types.Scene.smart_bake_filename = bpy.props.StringProperty(
        name="File Name",
        description="Base name for the generated baking textures",
        default="T_Model_Normal"
    )
    # Register the DirectX normal map format option flag
    bpy.types.Scene.smart_bake_directx = bpy.props.BoolProperty(
        name="DirectX (-Y)",
        description="Invert the Green channel to match DirectX normal map format standards",
        default=False
    )
    # Register safe data pointers for target collections instead of hardcoded strings
    bpy.types.Scene.smart_bake_lp_collection = bpy.props.PointerProperty(
        type=bpy.types.Collection,
        name="Low-Poly",
        description="Select the collection containing Low-Poly objects"
    )
    bpy.types.Scene.smart_bake_hp_collection = bpy.props.PointerProperty(
        type=bpy.types.Collection,
        name="High-Poly",
        description="Select the collection containing High-Poly objects"
    )
    # Register safe scene memory pointers for temporary baking meshes
    bpy.types.Scene.smart_bake_merged_lp_obj = bpy.props.PointerProperty(
        type=bpy.types.Object,
        name="Merged Low-Poly Object"
    )
    bpy.types.Scene.smart_bake_merged_hp_obj = bpy.props.PointerProperty(
        type=bpy.types.Object,
        name="Merged High-Poly Object"
    )  


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.smart_bake_resolution
    del bpy.types.Scene.smart_bake_extrusion
    del bpy.types.Scene.smart_bake_filename
    del bpy.types.Scene.smart_bake_directx
    del bpy.types.Scene.smart_bake_lp_collection
    del bpy.types.Scene.smart_bake_hp_collection