import bpy      # type: ignore

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
        box_slots.prop(scene.smart_bake_settings, "lp_collection", text="Low-Poly Collection", icon='MESH_ICOSPHERE')
        show_extrusion = box_slots.row()
        lp_collection = scene.smart_bake_settings.lp_collection
        show_extrusion.enabled = bool(
            lp_collection and any(obj.type == 'MESH' for obj in lp_collection.objects)
        )
        show_extrusion.prop(scene.smart_bake_settings, "show_extrusion", text="Show Extrusion")
        box_slots.prop(scene.smart_bake_settings, "hp_collection", text="High-Poly Collection", icon='MESH_MONKEY')
        

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
        lp_col = scene.smart_bake_settings.lp_collection
        hp_col = scene.smart_bake_settings.hp_collection
        
        if not lp_col or not hp_col or not lp_col.objects or not hp_col.objects:
            box_warn = layout.box()
            box_warn.scale_y = 0.8
            if not lp_col and not hp_col:
                box_warn.label(text="Assign LP and HP collections!", icon='ERROR')
            elif not lp_col or not lp_col.objects:
                box_warn.label(text="Low-Poly collection is empty or unassigned!", icon='ERROR')
            elif not hp_col or not hp_col.objects:
                box_warn.label(text="High-Poly collection is empty or unassigned!", icon='ERROR')
                
        if lp_col and hp_col and lp_col == hp_col:
            box_warn = layout.box()
            box_warn.scale_y = 0.8        
            box_warn.label(text="LP and HP collections are the same!", icon='ERROR')

        # merged_lp_exists = bpy.data.objects.get(OBJECT_OT_bake_normals.MERGED_LP_NAME) is not None
        
        merged_lp = scene.smart_bake_settings.merged_lp_obj
        # merged_lp_exists = merged_lp and scene.objects.get(merged_lp.name)
        if merged_lp and scene.objects.get(merged_lp.name):
            layout.separator()
            # Highlights the button in blue/accent color to draw user's attention
            layout.operator("object.activate_skew_paint", text="Paint Skew Correction", icon='BRUSH_DATA')
            # Display the finalization button right under the brush tool
            layout.operator("object.finalize_bake", text="Finalize & Export Map", icon='DISK_DRIVE')
        layout.separator()
        layout.label(text="Texture settings:")
        # Add the text field property for user-defined texture name
        layout.prop(scene.smart_bake_settings, "filename", text="Name")
        layout.prop(scene.smart_bake_settings, "resolution", text="Resolution")
        # Expose the DirectX format checkbox toggler right in the settings sub-layout
        layout.prop(scene.smart_bake_settings, "directx", text="DirectX")
        
        layout.prop(scene.smart_bake_settings, "extrusion", text="Ray Height")