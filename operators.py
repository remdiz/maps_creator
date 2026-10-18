import bpy                                  # type: ignore
import bmesh                                # type: ignore
import numpy as np
from mathutils import Vector                # type: ignore
from mathutils.bvhtree import BVHTree       # type: ignore

import os
import time

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
    EXTRUSION_PREVIEW_NAME = "_Extrusion_Preview_LowPoly"
    MATERIAL_NAME = "M_SmartBake_Internal"
    TEX_SMOOTH_NAME = "T_Bake_Normal_Smooth"
    TEX_FLAT_NAME = "T_Bake_Normal_Flat"
    TEX_MASK_NAME = "T_Bake_Skew_Mask"


    @classmethod
    def delete_object(cls, target):
        """Completely remove target mesh object (assumes target exist)"""
        if target and target.name in bpy.data.objects:
            target_mesh_data = target.data
            # preview_textures = [
            #     modifier.texture
            #     for modifier in target.modifiers
            #     if modifier.type == 'DISPLACE'
            #     and modifier.texture
            #     and modifier.texture.get("smart_baker_extrusion_preview")
            # ]
            bpy.data.objects.remove(target, do_unlink=True)
            if target_mesh_data and target_mesh_data.users == 0:
                bpy.data.meshes.remove(target_mesh_data, do_unlink=True)
            # for texture in preview_textures:
            #     image = texture.image
            #     if texture.users == 0:
            #         bpy.data.textures.remove(texture, do_unlink=True)
            #     if image and image.get("smart_baker_extrusion_preview") and image.users == 0:
            #         bpy.data.images.remove(image, do_unlink=True)
    
    @classmethod
    def cleanup_assets(cls, context, clean_geometry=True, clean_materials=True, clean_textures=True):
        """Safely removes temporary baking assets from Blender database"""
        scene = context.scene
        settings = scene.smart_bake_settings
        
        # 1. Clean up temporary meshes and objects
        if clean_geometry:
            # Safely extract references to memory blocks
            lp_obj = settings.merged_lp_obj
            hp_obj = settings.merged_hp_obj
            
            for obj in [lp_obj, hp_obj]:
                if obj:
                    cls.delete_object(obj)
            
            # Clear pointers from scene database to mark them empty
            settings.merged_lp_obj = None
            settings.merged_hp_obj = None
            # for name in [cls.MERGED_LP_NAME, cls.MERGED_HP_NAME]:
            #     obj = bpy.data.objects.get(name)
            #     if obj:
            #         cls.delete_object(obj)

        # 2. Clean up temporary material
        if clean_materials:
            # mat = bpy.data.materials.get(cls.MATERIAL_NAME)
            mat = settings.internal_material
            if mat:
                bpy.data.materials.remove(mat, do_unlink=True)
            settings.internal_material = None    

        # 3. Clean up temporary images/textures
        if clean_textures:
            if settings.texture_normal_smooth:
                bpy.data.images.remove(settings.texture_normal_smooth, do_unlink=True)
                settings.texture_normal_smooth = None
                
            if settings.texture_normal_flat:
                bpy.data.images.remove(settings.texture_normal_flat, do_unlink=True)
                settings.texture_normal_flat = None
                
            if settings.texture_skew_mask:
                bpy.data.images.remove(settings.texture_skew_mask, do_unlink=True)
                settings.texture_skew_mask = None


            # for name in [cls.TEX_SMOOTH_NAME, cls.TEX_FLAT_NAME, cls.TEX_MASK_NAME]:
            #     img = bpy.data.images.get(name)
            #     if img:
            #         bpy.data.images.remove(img, do_unlink=True)
        

    
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
        if not hasattr(scene, "smart_bake_settings"):
            return False
        settings = scene.smart_bake_settings
        # FIXED: Access references directly from Scene data model
        lp_col = settings.lp_collection
        hp_col = settings.hp_collection

        if not lp_col or not lp_col.objects:
            return False
        if not hp_col or not hp_col.objects:
            return False
        if lp_col == hp_col:
            return False

        return True


    @classmethod
    def change_extrusion(cls, settings, context):
        preview = settings.extrusion_preview_obj
        if not preview:
            preview = bpy.data.objects.get(OBJECT_OT_bake_normals.EXTRUSION_PREVIEW_NAME)
            if preview:
                settings.extrusion_preview_obj = preview
    
        if not preview:
            OBJECT_OT_bake_normals.update_extrusion(context, settings)
            return
    
        displace = next(
            (
                modifier
                for modifier in preview.modifiers
                if modifier.type == 'DISPLACE' and modifier.name.startswith("Extrusion")
            ),
            None,
        )
        if not displace:
            displace = preview.modifiers.new(name="Extrusion", type='DISPLACE')
            displace.direction = 'NORMAL'
            displace.mid_level = 0.0
    
        displace.strength = settings.extrusion
    
    
    @classmethod
    def update_extrusion(cls, context, settings):
        if not settings.show_extrusion:
            preview = settings.extrusion_preview_obj
            if preview:
                cls.delete_object(preview)
                settings.extrusion_preview_obj = None
            return
        
        collection = settings.lp_collection
        if not collection or not any(obj.type == 'MESH' for obj in collection.objects):
            settings.show_extrusion = False
            return

        preview = cls._prepare_and_merge_collection(
            context,
            collection,
            cls.EXTRUSION_PREVIEW_NAME
        )
        displace = preview.modifiers.new(name="Extrusion", type='DISPLACE')
        # texture_image = bpy.data.images.new(
        #     name="T_Extrusion_Preview",
        #     width=1,
        #     height=1,
        #     alpha=True,
        # )
        # texture_image.generated_color = (1.0, 1.0, 1.0, 1.0)
        # texture_image["smart_baker_extrusion_preview"] = True
        # texture = bpy.data.textures.new(name="T_Extrusion_Preview", type='IMAGE')
        # texture.image = texture_image
        # texture["smart_baker_extrusion_preview"] = True
        # displace.texture = texture
        # displace.texture_coords = 'LOCAL'
        displace.direction = 'NORMAL'
        displace.mid_level = 0.0
        displace.strength = settings.extrusion

        preview.display_type = 'WIRE'
        preview.hide_render = True

        old_preview = settings.extrusion_preview_obj
        settings.extrusion_preview_obj = preview
        if old_preview:
            cls.delete_object(old_preview)
    
    
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
        if collection:
            for obj in collection.objects:
                if obj.type == 'MESH' and not obj.hide_get():
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

                    # ВИПРАВЛЕНО: Негайно видаляємо копію з бази Blender, 
                    # щоб вона не висіла «мертвим вантажем» у пам'яті
                    bpy.data.meshes.remove(mesh_copy, do_unlink=True)
                    bpy.data.meshes.remove(mesh_from_eval, do_unlink=True)

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


    @classmethod
    def check_uv_maps(cls, collection):
        """Checks if all mesh objects in the collection have UV maps"""
        missing_uv_objects = []
        for obj in collection.objects:
            if obj.type == 'MESH':
                if not obj.data.uv_layers:
                    missing_uv_objects.append(obj.name)
        return missing_uv_objects
    
    
    def render_config(self, scene, settings):
        render_settings = scene.render
        cycles_settings = scene.cycles
        
        # 1. Примусово перемикаємо на Cycles (запікання нормалей працює тільки в ньому)
        render_settings.engine = 'CYCLES'
        
        # 3. Оптимізуємо Samples (для запікання карт нормалей 16-32 семплів більш ніж достатньо, 
        # великі значення лише марнують час і не впливають на якість векторів)
        cycles_settings.samples = 1
        cycles_settings.device = 'GPU'
        render_settings.use_persistent_data = True
        
        # 4. Налаштовуємо параметри запікання в Cycles
        bake_settings = scene.render.bake
        
        # Виставляємо тип запікання — Тільки Карта Нормалей
        bake_settings.use_selected_to_active = True
        
        # Отримуємо значення Extrusion з повзунка нашої панелі (створимо його на наступному кроці)
        bake_settings.margin = 16  # Падінг текстури (Margin) за замовчуванням 16 пікселів
        bake_settings.cage_extrusion = settings.extrusion
        
        # Залишаємо Max Ray Distance в 0 (нескінченність), щоб Cycles сам знаходив хай-полі
        bake_settings.max_ray_distance = 0.0
        
    
    def create_texture_image(self, name, width, height, is_color=False, is_black=False):
        """ Creates image with the given name and resolution """    
        # If a texture with that name already exists, we delete it to avoid creating duplicates
        if name in bpy.data.images:
            bpy.data.images.remove(bpy.data.images[name])
        img = bpy.data.images.new(name=name, width=width, height=height, alpha=False, float_buffer=False)
        if not is_color:
            img.colorspace_settings.name = 'Non-Color'
        if is_black:
            img.generated_color = (0.0, 0.0, 0.0, 1.0)    
        return img
    
    
    def create_texture_node(self, nodes_obj, img, label, loc):
        """ Creates image texture node in the nodes_obj material node tree """
        t_node = nodes_obj.new(type='ShaderNodeTexImage')
        t_node.image = img
        t_node.label = label
        t_node.name = label
        t_node.location = loc
        return t_node

    
    def create_textures(self, context):
        settings = context.scene.smart_bake_settings
        lp_obj = settings.merged_lp_obj
        # Получаем выбранное пользователем разрешение из настроек сцены
        res = int(settings.resolution)
        
        # Creating textures in Blender DB
        tex_smooth_name = self.TEX_SMOOTH_NAME # "T_Bake_Normal_Smooth"
        tex_flat_name = self.TEX_FLAT_NAME # "T_Bake_Normal_Flat"
        tex_mask_name = self.TEX_MASK_NAME # "T_Bake_Skew_Mask"

        # 1. Створюємо карти нормалей (Non-Color) та маску (можна sRGB, але заливаємо чорним)
        img_smooth = self.create_texture_image(tex_smooth_name, res, res)
        img_flat = self.create_texture_image(tex_flat_name, res, res)

        # Маску ініціалізуємо повністю чорним кольором (щоб спочатку показувало суто Smooth normal)
        img_mask = self.create_texture_image(tex_mask_name, res, res, is_color=True, is_black=True)
        # img_mask.generated_color = (0.0, 0.0, 0.0, 1.0)

        # Create normal (Non-Color) and mask (sRGB, black) maps
        settings.texture_normal_smooth = img_smooth
        settings.texture_normal_flat = img_flat
        settings.texture_skew_mask = img_mask

        # 2. Очищаем все старые материалы с объединенного Low-Poly объекта
        lp_obj.data.materials.clear()
        
        # 3. Создаем один единственный чистый материал для запекания
        bake_mat = bpy.data.materials.new(name="M_SmartBake_Internal")
        settings.internal_material = bake_mat
        bake_mat.use_nodes = True
        lp_obj.data.materials.append(bake_mat)

        nodes = bake_mat.node_tree.nodes

        # Nodes links for future use
        # Normal texture nodes creation
        self.node_smooth_ref = self.create_texture_node(nodes, img_smooth, "Bake Target: SMOOTH", (-600, 400))
        self.node_flat_ref = self.create_texture_node(nodes, img_flat, "Bake Target: FLAT", (-600, 150))
        # Mask node creation
        self.node_mask_ref = self.create_texture_node(nodes, img_mask, "Paint Mask", (-600, -100))
        self.report({'INFO'}, f"Textures {res}x{res} ready. Nodes compiled.")
        return bake_mat
        
    
    def bake_normal_map(self, context, smoothness, texture_node):
        settings = context.scene.smart_bake_settings
        bake_mat = settings.internal_material
        merged_lp = settings.merged_lp_obj
        merged_hp = settings.merged_hp_obj
        for poly in merged_lp.data.polygons:
            poly.use_smooth = smoothness
            merged_lp.data.update() # Flush data changes to database
    
            
            # Робимо активною ноду Smooth текстури
            bake_mat.node_tree.nodes.active = texture_node
            texture_node.select = True
            
            # Execute bake inside a safe context override wrapper
            # TODO: if bake fails, scene becomes corrupted -> restore previous state
            with context.temp_override(active_object=merged_lp, selected_objects=[merged_hp, merged_lp]):
                bpy.ops.object.bake(type='NORMAL')

    
    def create_mix_shader(self, context):
        settings = context.scene.smart_bake_settings
        bake_mat = settings.internal_material
        nodes = bake_mat.node_tree.nodes
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
        
    
    
    def postprocess(self, context):
        settings = context.scene.smart_bake_settings
        bake_mat = settings.internal_material
        nodes = bake_mat.node_tree.nodes
        # Activate mask node for future texture painting
        nodes.active = self.node_mask_ref
        self.node_mask_ref.select = True

        # Enable Material Preview in the viewport
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        space.shading.type = 'MATERIAL'

        children = context.view_layer.layer_collection.children
                
        # Instantly access and exclude layer collections via their names from pointers
        if settings.lp_collection:
            children.get(settings.lp_collection.name).exclude = True
        if settings.hp_collection:
            children.get(settings.hp_collection.name).exclude = True
    
    
    def execute(self, context):
        start_time = time.time()
        scene = context.scene
        settings = scene.smart_bake_settings
        # Run pre-bake cleanup to wipe any leftovers from previous sessions
        self.report({'INFO'}, "Performing pre-bake cleanup...")
        self.cleanup_assets(context)
        self.report({'INFO'}, f"Cleanup complete in {time.time() - start_time:.2f}s.")
        
        # === Step 0: UV MAPS VALIDATION ON LOW-POLY ===
        # lp_objects = settings.lp_collection.objects
        missing_uv_objects = self.check_uv_maps(settings.lp_collection)

        # for obj in lp_objects:
        #     # Проверяем только объекты типа MESH (игнорируем пустышки, камеры и т.д.)
        #     if obj.type == 'MESH':
        #         # Если список слоев UV пуст, добавляем имя объекта в список ошибок
        #         if not obj.data.uv_layers:
        #             missing_uv_objects.append(obj.name)

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
        merged_lp = self._prepare_and_merge_collection(context, settings.lp_collection, self.MERGED_LP_NAME)
        settings.merged_lp_obj = merged_lp


        # === STEP 2: MERGING HIGH-POLY (HP) ===
        self.report({'INFO'}, "Processing and merging High-Poly collection...")
        merged_hp = self._prepare_and_merge_collection(context, settings.hp_collection, self.MERGED_HP_NAME)
        settings.merged_hp_obj = merged_hp

        # === STEP 3: PREPARE SELECTED TO ACTIVE ===
        # Для запікання Selected to Active: High-Poly має бути ВИДІЛЕНИМ,
        # а Low-Poly має бути ВИДІЛЕНИМ ТА АКТИВНИМ.
        bpy.ops.object.select_all(action='DESELECT')
        
        merged_hp.select_set(True) # Selected (High)
        merged_lp.select_set(True) # Selected (Low)
        context.view_layer.objects.active = merged_lp # Active (Low)

        # === STEP 3.5: AUTOMATIC TEXTURES AND MATERIAL CREATION ===
        self.report({'INFO'}, "Texture generation...")

        # # Получаем выбранное пользователем разрешение из настроек сцены
        # res = int(settings.resolution)
        
        # # Creating textures in Blender DB
        # tex_smooth_name = self.TEX_SMOOTH_NAME # "T_Bake_Normal_Smooth"
        # tex_flat_name = self.TEX_FLAT_NAME # "T_Bake_Normal_Flat"
        # tex_mask_name = self.TEX_MASK_NAME # "T_Bake_Skew_Mask"

        # # 1. Створюємо карти нормалей (Non-Color) та маску (можна sRGB, але заливаємо чорним)
        # img_smooth = self.create_texture_image(tex_smooth_name, res, res)
        # img_flat = self.create_texture_image(tex_flat_name, res, res)

        # # Маску ініціалізуємо повністю чорним кольором (щоб спочатку показувало суто Smooth normal)
        # img_mask = self.create_texture_image(tex_mask_name, res, res, is_color=True, is_black=True)
        # # img_mask.generated_color = (0.0, 0.0, 0.0, 1.0)

        # # Create normal (Non-Color) and mask (sRGB, black) maps
        # settings.texture_normal_smooth = img_smooth
        # settings.texture_normal_flat = img_flat
        # settings.texture_skew_mask = img_mask

        # # 2. Очищаем все старые материалы с объединенного Low-Poly объекта
        # merged_lp.data.materials.clear()
        
        # # 3. Создаем один единственный чистый материал для запекания
        # bake_mat = bpy.data.materials.new(name="M_SmartBake_Internal")
        # settings.internal_material = bake_mat
        # bake_mat.use_nodes = True
        # merged_lp.data.materials.append(bake_mat)

        # nodes = bake_mat.node_tree.nodes

        # # Nodes links for future use
        # # Normal texture nodes creation
        # self.node_smooth_ref = self.create_texture_node(nodes, img_smooth, "Bake Target: SMOOTH", (-600, 400))
        # self.node_flat_ref = self.create_texture_node(nodes, img_flat, "Bake Target: FLAT", (-600, 150))
        # # Mask node creation
        # self.node_mask_ref = self.create_texture_node(nodes, img_mask, "Paint Mask", (-600, -100))

        # self.report({'INFO'}, f"Textures {res}x{res} ready. Nodes compiled.")
        bake_mat = self.create_textures(context)
        nodes = bake_mat.node_tree.nodes

        # === STEP 4: CYCLES CONFIGURATION ===
        self.report({'INFO'}, "Geometry ready. Preparing Cycles...")
        
        self.render_config(scene, settings)

        # === STEP 5: SEQUENTIAL DUAL BAKING ===
        
        # --- Pass 1: SMOOTH NORMAL (For bevels) ---
        self.report({'INFO'}, "Pass 1 Start: Smooth Normal Baking...")
        
        # bpy.ops.object.shade_smooth()
        # Low-level Python loop to force Smooth shading directly in memory
        # for poly in merged_lp.data.polygons:
        #     poly.use_smooth = True
        # merged_lp.data.update() # Flush data changes to database

        
        # # Робимо активною ноду Smooth текстури
        # bake_mat.node_tree.nodes.active = self.node_smooth_ref
        # self.node_smooth_ref.select = True
        
        # # Execute bake inside a safe context override wrapper
        # # TODO: if bake fails, scene becomes corrupted -> restore previous state
        # with context.temp_override(active_object=merged_lp, selected_objects=[merged_hp, merged_lp]):
        #     bpy.ops.object.bake(type='NORMAL')
        start_time = time.time()
        
        # self.bake_normal_map(context, smoothness=True, texture_node=self.node_smooth_ref)
        
        
        # --- PASS 2: FLAT NORMAL (for normal correction) ---
        # self.report({'INFO'}, "Pass 2 Start: Flat Normal Baking...")
        
        # Temporarily switch merged Low-Poly to Flat Shading
        # bpy.ops.object.shade_flat()
        # Low-level Python loop to force Flat shading directly in memory
        # for poly in merged_lp.data.polygons:
        #     poly.use_smooth = False
        # merged_lp.data.update()
        
        # # Activate Flat texture node
        # bake_mat.node_tree.nodes.active = self.node_flat_ref
        # self.node_flat_ref.select = True
        
        # # Execute second bake pass safely
        # with context.temp_override(active_object=merged_lp, selected_objects=[merged_hp, merged_lp]):
        #     bpy.ops.object.bake(type='NORMAL')
        # self.bake_normal_map(context, smoothness=False, texture_node=self.node_flat_ref)
        
        buf_smooth, buf_flat = self.bake_normal_bvhtree(context, settings)
        self.finalize_and_flush_buffers(settings, buf_smooth, buf_flat)
        
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
        settings.merged_hp_obj = None

        preview = settings.extrusion_preview_obj
        if preview:
            self.delete_object(preview)
            settings.extrusion_preview_obj = None
        settings.show_extrusion = False    

        self.report({'INFO'}, f"Batch baking finished in {time.time() - start_time:.2f}s.")

        # === STEP 6: MIX SHADER COMPILATION ===
        self.report({'INFO'}, "Final shader creation...")
        
        # # 1. Mix node
        # node_mix = nodes.new(type='ShaderNodeMix')
        # node_mix.data_type = 'RGBA' 
        # node_mix.blend_type = 'MIX'
        # node_mix.location = (-200, 250)

        # # 2. Normal Map node
        # node_normal_map = nodes.new(type='ShaderNodeNormalMap')
        # node_normal_map.location = (50, 250)

        # # 3. Looking for Principled BSDF
        # principled_node = None
        # for n in nodes:
        #     if n.type == 'BSDF_PRINCIPLED':
        #         principled_node = n
        #         break
        
        # # If Principled BSDF is absent, lets simply use Material Output
        # if not principled_node:
        #     for n in nodes:
        #         if n.type == 'OUTPUT_MATERIAL':
        #             bake_mat.node_tree.links.new(node_mix.outputs['Result'], n.inputs['Surface'])
        #             break
        
        # # 4. Linking nodes
        # links = bake_mat.node_tree.links
        
        # # Smooth Normal -> slot A
        # links.new(self.node_smooth_ref.outputs['Color'], node_mix.inputs['A'])
        
        # # Flat Normal -> slot B
        # links.new(self.node_flat_ref.outputs['Color'], node_mix.inputs['B'])
        
        # # Connecting mask to Mix node Factor slot
        # links.new(self.node_mask_ref.outputs['Color'], node_mix.inputs['Factor'])
        
        # # If we have Principled BSDF, using Normal Map through Normal slot
        # if principled_node:
        #     links.new(node_mix.outputs['Result'], node_normal_map.inputs['Color'])
        #     links.new(node_normal_map.outputs['Normal'], principled_node.inputs['Normal'])
        self.create_mix_shader(context)

        # === STEP 7: POST-BAKE VIEWPORT SETUP ===
        
        # Activate mask node for future texture painting
        # nodes.active = self.node_mask_ref
        # self.node_mask_ref.select = True

        # # Enable Material Preview in the viewport
        # for area in context.screen.areas:
        #     if area.type == 'VIEW_3D':
        #         for space in area.spaces:
        #             if space.type == 'VIEW_3D':
        #                 space.shading.type = 'MATERIAL'

        # === STEP 7.5: DISABLE INPUT COLLECTIONS VISIBILITY ===
        self.report({'INFO'}, "Hiding input LP and HP collections...")
        
        # Get the root layer collection of the current view layer
        # root_layer_col = context.view_layer.layer_collection
        
        # Loop through all sub-collections in the view layer
        # for sub_layer_col in root_layer_col.children:
        #     # If the collection name matches LP or HP, exclude it from the view layer
        #     if sub_layer_col.name in {"LP", "HP"}:
        #         sub_layer_col.exclude = True   

        # children = context.view_layer.layer_collection.children
        
        # # Instantly access and exclude layer collections via their names from pointers
        # if settings.lp_collection:
        #     children.get(settings.lp_collection.name).exclude = True
        # if settings.hp_collection:
        #     children.get(settings.hp_collection.name).exclude = True
        self.postprocess(context)

        self.report({'INFO'}, "Baking finished!")
        return {'FINISHED'}


    def finalize_and_flush_buffers(self, settings, buffer_smooth, buffer_flat):
        """
        Приймає 2D NumPy масиви нормалей, обробляє координатні простори (DirectX/OpenGL),
        i вимиває дані в RAM-структури Blender через foreach_set().
        """
        width = int(settings.resolution)
        height = int(settings.resolution)
        is_directx = settings.directx
        # 1. Обробка прапорця координатного простору (DirectX Y-Flip)
        # У DirectX зелений канал (Y) інвертований. На чистій математиці NumPy це робиться миттєво.
        if is_directx:
            # buffer[:, :, 1] відповідає за зелений канал (G) у форматі RGBA
            buffer_smooth[:, :, 1] = 1.0 - buffer_smooth[:, :, 1]
            buffer_flat[:, :, 1] = 1.0 - buffer_flat[:, :, 1]

        # 2. Випрямлення масивів (Flattening) для C-буфера Blender
        # Blender очікує одновимірний масив float32 довжиною width * height * 4
        flat_smooth = buffer_smooth.ravel().astype(np.float32)
        flat_flat = buffer_flat.ravel().astype(np.float32)

        # 3. Підготовка та запис текстури Smooth Pass
        tex_smooth = settings.texture_normal_smooth
        if tex_smooth:
            # Гарантуємо правильний розмір текстурного блоку
            if tex_smooth.size[0] != width or tex_smooth.size[1] != height:
                tex_smooth.scale(width, height)
                
            # Важливо: вимикаємо будь-яке колірне керування (для нормалей потрібні чисті дані)
            tex_smooth.colorspace_settings.name = 'Non-Color'
            
            # Миттєвий запис у C-Buffer
            tex_smooth.pixels.foreach_set(flat_smooth)
            tex_smooth.update() # Оновлюємо текстуру у в'юпорті

        # 4. Підготовка та запис текстури Flat Pass
        tex_flat = settings.texture_normal_flat
        if tex_flat:
            if tex_flat.size[0] != width or tex_flat.size[1] != height:
                tex_flat.scale(width, height)
                
            tex_flat.colorspace_settings.name = 'Non-Color'
            
            tex_flat.pixels.foreach_set(flat_flat)
            tex_flat.update()

        # 5. Ініціалізація порожньої Paint маски (T_Bake_Skew_Mask)
        # Створюємо чистий чорний колірний простір для ручного малювання
        tex_mask = settings.texture_skew_mask
        if tex_mask:
            if tex_mask.size[0] != width or tex_mask.size[1] != height:
                tex_mask.scale(width, height)
                
            tex_mask.colorspace_settings.name = 'Non-Color'
            
            # Ініціалізуємо маску чорним кольором (0.0, 0.0, 0.0, 1.0)
            mask_data = np.array([0.0, 0.0, 0.0, 1.0] * (width * height), dtype=np.float32)
            tex_mask.pixels.foreach_set(mask_data)
            tex_mask.update()
    
    
    def bake_normal_bvhtree(self, context, settings):
        """Bakes normal map using BVH tree raycasting for high-poly to low-poly transfer"""
        width = int(settings.resolution)
        height = int(settings.resolution)
        # TODO: this is wrong! we should use mesh extrusion from the Displace modifier, not the user input
        ray_max_dist = settings.extrusion
        is_directx = settings.directx
        
        depsgraph = context.evaluated_depsgraph_get()
        lp_obj = settings.merged_lp_obj.evaluated_get(depsgraph)
        hp_obj = settings.merged_hp_obj
        
        lp_mesh = bpy.data.meshes.new_from_object(lp_obj)
        # hp_mesh = hp_obj.to_mesh()
        bm = bmesh.new()
        bm.from_mesh(lp_mesh)
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        bm.to_mesh(lp_mesh)
        bm.free() # Звільняємо пам'ять bmesh

        lp_mesh.calc_tangents()
        
        # Створення BVH-дерева High-Poly
        hp_bvh = BVHTree.FromObject(hp_obj, depsgraph, epsilon=0.0001)
        
        # Трансформаційні матриці
        lp_world_mat = np.array(lp_obj.matrix_world)
        hp_world_inv = np.array(hp_obj.matrix_world.inverted())
        hp_world_mat = np.array(hp_obj.matrix_world)
        
        # Матриця нормалей LP (Inverse Transpose 3x3)
        lp_norm_mat = np.linalg.inv(lp_world_mat[:3, :3]).T

        # 1. СТВОРЕННЯ СІТКИ ПІКСЕЛІВ (Pixel Grid)
        # Створюємо масив координат центрів усіх пікселів у UV-просторі
        u = np.linspace(0.5 / width, 1.0 - 0.5 / width, width)
        v = np.linspace(0.5 / height, 1.0 - 0.5 / height, height)
        uu, vv = np.meshgrid(u, v)
        pixel_uvs = np.stack([uu, vv], axis=-1).reshape(-1, 2) # Форма: (N_pixels, 2)

        # Вихідні буфери текстур
        buffer_smooth = np.array([0.5, 0.5, 1.0, 1.0] * (width * height), dtype=np.float32).reshape(-1, 4)
        buffer_flat = np.array([0.5, 0.5, 1.0, 1.0] * (width * height), dtype=np.float32).reshape(-1, 4)

        # 2. ЕКСТРАКЦІЯ ДАНИХ ГЕОМЕТРІЇ
        uv_layer = lp_mesh.uv_layers.active.data
        
        # Швидке витягування масивів через foreach_get
        num_loops = len(lp_mesh.loops)
        loop_uvs = np.zeros(num_loops * 2, dtype=np.float32)
        uv_layer.foreach_get("uv", loop_uvs)
        loop_uvs = loop_uvs.reshape(-1, 2)
        
        # Переводимо полігони в індекси циклів (масив трикутників)
        tri_loop_indices = np.array([poly.loop_indices for poly in lp_mesh.polygons], dtype=np.int32)
        
        # Отримуємо UV-координати для кожної вершини кожного трикутника
        # Форма: (N_triangles, 3, 2)
        tri_uvs = loop_uvs[tri_loop_indices]

        # Витягуємо 3D позиції вершин, нормалей, тангенсів
        num_verts = len(lp_mesh.vertices)
        vert_cos = np.zeros(num_verts * 3, dtype=np.float32)
        lp_mesh.vertices.foreach_get("co", vert_cos)
        vert_cos = vert_cos.reshape(-1, 3)

        # Для швидкості ітеруємо лише трикутники, але обчислення всередині них — векторні
        for tri_idx, poly in enumerate(lp_mesh.polygons):
            # Обмежувальний прямокутник трикутника в пікселях
            t_uv = tri_uvs[tri_idx]
            p_min = np.floor(np.min(t_uv, axis=0) * [width, height]).astype(int)
            p_max = np.ceil(np.max(t_uv, axis=0) * [width, height]).astype(int)
            
            x_min, y_min = max(0, p_min[0]), max(0, p_min[1])
            x_max, y_max = min(width - 1, p_max[0]), min(height - 1, p_max[1])
            
            if x_max < x_min or y_max < y_min:
                continue
                
            # Вирізаємо маску пікселів, що потрапляють у Bounding Box трикутника
            x_range = np.arange(x_min, x_max + 1)
            y_range = np.arange(y_min, y_max + 1)
            yy, xx = np.meshgrid(y_range, x_range, indexing='ij')
            pixel_indices = yy * width + xx
            
            # UV координати обраних пікселів
            p_uv = pixel_uvs[pixel_indices].reshape(-1, 2)
            
            # 3. ВЕКТОРНА БАРИЦЕНТРИКА ДЛЯ МАСИВУ ПІКСЕЛІВ
            A, B, C = t_uv[0], t_uv[1], t_uv[2]
            v0 = B - A
            v1 = C - A
            v2 = p_uv - A

            d00 = np.dot(v0, v0)
            d01 = np.dot(v0, v1)
            d11 = np.dot(v1, v1)
            d20 = np.einsum('ij,j->i', v2, v0)
            d21 = np.einsum('ij,j->i', v2, v1)
            
            denom = d00 * d11 - d01 * d01
            if abs(denom) < 1e-6:
                continue
                
            v = (d11 * d20 - d01 * d21) / denom
            w = (d00 * d21 - d01 * d20) / denom
            u = 1.0 - v - w
            
            # Фільтр: залишаємо лише ті пікселі, які реально всередині трикутника
            inside = (u >= 0) & (v >= 0) & (w >= 0)
            if not np.any(inside):
                continue
                
            valid_pixels = pixel_indices.flatten()[inside]
            u, v, w = u[inside], v[inside], w[inside]
            weights = np.stack([u, v, w], axis=-1) # Форма: (M_valid_pixels, 3)

            # 4. ВЕКТОРНЕ ОБЧИСЛЕННЯ ПОЗИЦІЙ ТА TBN
            # Збираємо 3D-локальні координати вершин трикутника
            v_idx = poly.vertices
            tri_cos = vert_cos[v_idx] # (3, 3)
            
            # Інтерполяція 3D-координат для всіх валідних пікселів одразу
            lp_local_pos = np.dot(weights, tri_cos) # (M, 3)
            # Перевід у Світовий простір (додаємо 1 для гомогенних координат)
            lp_world_pos = np.dot(np.hstack([lp_local_pos, np.ones((len(lp_local_pos), 1))]), lp_world_mat.T)[:, :3]

            # Збір та інтерполяція TBN даних з циклів полігону
            l_idx = poly.loop_indices
            ns_vert = np.array([lp_mesh.vertices[lp_mesh.loops[li].vertex_index].normal for li in l_idx])
            ts_vert = np.array([lp_mesh.loops[li].tangent for li in l_idx])
            bts_vert = np.array([lp_mesh.loops[li].bitangent * lp_mesh.loops[li].bitangent_sign for li in l_idx])

            N_smooth_local = np.dot(weights, ns_vert)
            T_local = np.dot(weights, ts_vert)
            B_local = np.dot(weights, bts_vert)
            
            # Нормалізація векторів
            N_smooth_local /= np.linalg.norm(N_smooth_local, axis=1, keepdims=True)
            T_local /= np.linalg.norm(T_local, axis=1, keepdims=True)
            B_local /= np.linalg.norm(B_local, axis=1, keepdims=True)

            # Трансформація TBN у світовий простір
            T_world = np.dot(T_local, lp_world_mat[:3, :3].T)
            B_world = np.dot(B_local, lp_world_mat[:3, :3].T)
            N_smooth_world = np.dot(N_smooth_local, lp_norm_mat)
            
            # Для Flat Pass використовується єдина нормаль полігону
            N_flat_world = np.dot(poly.normal, lp_norm_mat)
            N_flat_world /= np.linalg.norm(N_flat_world)

            # 5. ТРАСУВАННЯ ПРОМЕНІВ (Оскільки BVHTree не підтримує масиви, тут ми вимушено викликаємо C++ ray_cast)
            hp_local_ray_starts = np.dot(np.hstack([lp_world_pos, np.ones((len(lp_world_pos), 1))]), hp_world_inv.T)[:, :3]
            # Напрямки променів для Smooth Pass (інтерполовані для кожного пікселя)
            hp_local_dirs_smooth = np.dot(N_smooth_world, hp_world_inv[:3, :3].T)
            # Напрямок променя для Flat Pass (однаковий для ВСІХ пікселів у межах цього полігону)
            # N_flat_world має форму (3,), тому ми трансформуємо його один раз і дублюємо під розмір масиву пікселів
            N_flat_world_local = np.dot(N_flat_world, hp_world_inv[:3, :3].T)
            hp_local_dirs_flat = np.repeat(N_flat_world_local[np.newaxis, :], len(valid_pixels), axis=0)
        
            for i, pixel_idx in enumerate(valid_pixels):
                start = Vector(hp_local_ray_starts[i])
                
                # --- ЧАСТИНА 1: SMOOTH PASS ---
                dir_smooth = Vector(hp_local_dirs_smooth[i])
                # ray_cast повертає: (location, normal, index, distance) або (None, None, None, None)
                hit_loc, hit_norm, hit_idx, hit_dist = hp_bvh.ray_cast(start, dir_smooth, ray_max_dist)
                
                # Якщо промах — стріляємо у зворотний бік (Bake Cage Inside)
                if hit_loc is None:
                    hit_loc, hit_norm, hit_idx, hit_dist = hp_bvh.ray_cast(start, -dir_smooth, ray_max_dist)
                    
                # Перевіряємо, чи ми дійсно знайшли геометрію High-Poly
                if hit_norm is not None:
                    # Конвертуємо mathutils Vector у масив NumPy для векторизованого множення
                    hp_local_norm = np.array(hit_norm)
                    
                    # Переводимо нормаль з локального простору HP у світовий простір
                    hit_normal_world = np.dot(hp_local_norm, np.linalg.inv(hp_world_mat[:3, :3]).T)
                    hit_normal_world /= np.linalg.norm(hit_normal_world)
                    
                    # Проекція на TBN простір
                    tx = np.dot(hit_normal_world, T_world[i])
                    ty = np.dot(hit_normal_world, B_world[i])
                    tz = np.dot(hit_normal_world, N_smooth_world[i])
                    
                    buffer_smooth[pixel_idx] = [tx * 0.5 + 0.5, ty * 0.5 + 0.5, tz * 0.5 + 0.5, 1.0]

                # --- ЧАСТИНА 2: FLAT PASS ---
                dir_flat = Vector(hp_local_dirs_flat[i])
                hit_loc_f, hit_norm_f, hit_idx_f, hit_dist_f = hp_bvh.ray_cast(start, dir_flat, ray_max_dist)
                
                if hit_loc_f is None:
                    hit_loc_f, hit_norm_f, hit_idx_f, hit_dist_f = hp_bvh.ray_cast(start, -dir_flat, ray_max_dist)
                    
                if hit_norm_f is not None:
                    hp_local_norm_f = np.array(hit_norm_f)
                    
                    hit_normal_world_flat = np.dot(hp_local_norm_f, np.linalg.inv(hp_world_mat[:3, :3]).T)
                    hit_normal_world_flat /= np.linalg.norm(hit_normal_world_flat)
                    
                    # Для Flat Pass використовуємо геометричну нормаль полігону (N_flat_world)
                    tx_f = np.dot(hit_normal_world_flat, T_world[i])
                    ty_f = np.dot(hit_normal_world_flat, B_world[i])
                    tz_f = np.dot(hit_normal_world_flat, N_flat_world)
                    
                    buffer_flat[pixel_idx] = [tx_f * 0.5 + 0.5, ty_f * 0.5 + 0.5, tz_f * 0.5 + 0.5, 1.0]

                
        # Повертаємо фінальні масиви, готові до foreach_set
        return buffer_smooth.reshape(height, width, 4), buffer_flat.reshape(height, width, 4)



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
        return context.scene.smart_bake_settings.merged_lp_obj is not None

    def execute(self, context):
        # merged_lp = bpy.data.objects.get(OBJECT_OT_bake_normals.MERGED_LP_NAME)
        merged_lp = context.scene.smart_bake_settings.merged_lp_obj

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
            # bake_mat = merged_lp.data.materials.get(OBJECT_OT_bake_normals.MATERIAL_NAME)
            bake_mat = context.scene.smart_bake_settings.internal_material
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
    """Merge maps based on paint mask via RAM arrays, export final image and clean up scene"""
    bl_idname = "object.finalize_bake"
    bl_label = "Finalize & Export Map"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.scene.smart_bake_settings.merged_lp_obj is not None

    def execute(self, context):
        start_time = time.time()
        props = context.scene.smart_bake_settings
        filename = props.filename
        res = int(props.resolution)

        if not bpy.data.is_saved:
            self.report({'ERROR'}, "Save your .blend file first to export textures!")
            return {'CANCELLED'}
            
        project_dir = bpy.path.abspath("//")
        final_filepath = os.path.join(project_dir, f"{filename}.png")
        
        self.report({'INFO'}, "Blending textures directly in RAM...")

                # 1. Retrieve the baked texture maps from the Blender database
        img_smooth = props.texture_normal_smooth
        img_flat = props.texture_normal_flat
        img_mask = props.texture_skew_mask

        if not img_smooth or not img_flat or not img_mask:
            self.report({'ERROR'}, "Baking source textures missing from database!")
            return {'CANCELLED'}

        import numpy as np

        # 2. Fast block-read pixels into 1D float32 numpy arrays directly from C-buffer
        arr_smooth = np.empty(res * res * 4, dtype=np.float32)
        img_smooth.pixels.foreach_get(arr_smooth)

        arr_flat = np.empty(res * res * 4, dtype=np.float32)
        img_flat.pixels.foreach_get(arr_flat)

        arr_mask = np.empty(res * res * 4, dtype=np.float32)
        img_mask.pixels.foreach_get(arr_mask)

        # 3. Reshape flat arrays to (Pixel_Count, Channels) to decouple components
        # This gives us instant access to individual channels without heavy loops
        smooth_rgb = arr_smooth.reshape(-1, 4)[:, :3]
        flat_rgb = arr_flat.reshape(-1, 4)[:, :3]
        
        # Extract the factor from the Red channel of the paint mask texture
        factor = arr_mask.reshape(-1, 4)[:, 0:1]  # Shape: (Pixel_Count, 1) for automated broadcasting

        # 4. Perform instantaneous C-level vectorized linear interpolation (Lerp)
        # Formula: Smooth * (1.0 - Factor) + Flat * Factor
        final_rgb = smooth_rgb * (1.0 - factor) + flat_rgb * factor

        # 5. Handle DirectX format axis inversion (-Y standard) in a single vectorized pass
        if props.directx:
            # Invert only the Green channel (index 1) across all pixels instantly
            final_rgb[:, 1] = 1.0 - final_rgb[:, 1]

        # 6. Reconstruct the flat 1D RGBA float32 array required by Blender API
        arr_final = np.empty(res * res * 4, dtype=np.float32)
        final_rgba = arr_final.reshape(-1, 4)
        
        final_rgba[:, :3] = final_rgb
        final_rgba[:, 3] = 1.0  # Force absolute opacity, eliminating world backdrop alpha leaks

        # 7. Create target asset and flush data blocks back via fast memory transfer
        final_img = bpy.data.images.new(name="T_SmartBake_Final", width=res, height=res, alpha=False)
        final_img.colorspace_settings.name = 'Non-Color'
        final_img.pixels.foreach_set(arr_final)

        # 8. Export directly to disk bypassing scene color profiles
        final_img.filepath_raw = final_filepath
        final_img.file_format = 'PNG'
        try:
            final_img.save()
        except (RuntimeError, OSError) as exc:
            bpy.data.images.remove(final_img, do_unlink=True)
            OBJECT_OT_bake_normals.cleanup_assets(context)
            self.report({'ERROR'}, f"Can not save texture to '{final_filepath}': {exc}")
            return {'CANCELLED'}

        # Database and garbage collection house-keeping
        bpy.data.images.remove(final_img, do_unlink=True)

        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        OBJECT_OT_bake_normals.cleanup_assets(context)

        # Restore visibility settings for user's source target arrays
        children = context.view_layer.layer_collection.children
        if props.lp_collection:
            # children.get(props.lp_collection.name).exclude = False
            low_col = children.get(props.lp_collection.name)
            if low_col:
                low_col.exclude = False
        if props.hp_collection:
            # children.get(props.hp_collection.name).exclude = False
            high_col = children.get(props.hp_collection.name)
            if high_col:
                high_col.exclude = False
        
        self.report({'INFO'}, f"Successfully exported combined map in {time.time() - start_time:.2f}s")
        return {'FINISHED'}