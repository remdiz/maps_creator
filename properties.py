import bpy      # type: ignore


def _update_extrusion_preview(settings, context):
    from .operators import OBJECT_OT_bake_normals

    # if not settings.show_extrusion:
    #     preview = settings.extrusion_preview_obj
    #     if preview:
    #         OBJECT_OT_bake_normals.delete_object(preview)
    #         settings.extrusion_preview_obj = None
    #     return

    # collection = settings.lp_collection
    # if not collection or not any(obj.type == 'MESH' for obj in collection.objects):
    #     settings.show_extrusion = False
    #     return

    # preview = OBJECT_OT_bake_normals._prepare_and_merge_collection(
    #     context,
    #     collection,
    #     OBJECT_OT_bake_normals.EXTRUSION_PREVIEW_NAME
    # )
    # preview.display_type = 'WIRE'
    # preview.hide_render = True

    # old_preview = settings.extrusion_preview_obj
    # settings.extrusion_preview_obj = preview
    # if old_preview:
    #     OBJECT_OT_bake_normals.delete_object(old_preview)
    OBJECT_OT_bake_normals.update_extrusion(context, settings)


def _update_extrusion_value(settings, context):
    if not settings.show_extrusion:
        return

    from .operators import OBJECT_OT_bake_normals
    OBJECT_OT_bake_normals.change_extrusion(settings, context)

    # preview = settings.extrusion_preview_obj
    # if not preview:
    #     preview = bpy.data.objects.get(OBJECT_OT_bake_normals.EXTRUSION_PREVIEW_NAME)
    #     if preview:
    #         settings.extrusion_preview_obj = preview

    # if not preview:
    #     OBJECT_OT_bake_normals.update_extrusion(context, settings)
    #     return

    # displace = next(
    #     (
    #         modifier
    #         for modifier in preview.modifiers
    #         if modifier.type == 'DISPLACE' and modifier.name.startswith("Extrusion")
    #     ),
    #     None,
    # )
    # if not displace:
    #     displace = preview.modifiers.new(name="Extrusion", type='DISPLACE')
    #     displace.direction = 'NORMAL'
    #     displace.mid_level = 0.0

    # displace.strength = settings.extrusion


def _update_lp_collection(settings, context):
    if settings.show_extrusion:
        _update_extrusion_preview(settings, context)


texture_res_items = [
    ('1024', "1K (1024x1024)", "Bake resolution 1024x1024"),
    ('2048', "2K (2048x2048)", "Bake resolution 2048x2048"),
    ('4096', "4K (4096x4096)", "Bake resolution 4096x4096"),
]
# =======================================================================
#  CENTRALIZED PROPERTY DATA CONTAINER (PropertyGroup)
# =======================================================================
class SmartBakerSettings(bpy.types.PropertyGroup):
    """Holds all properties for the baking tool in a single scene property container"""

    # Посилання на внутрішній матеріал
    internal_material: bpy.props.PointerProperty(
        type=bpy.types.Material,
        name="Internal Material"
    )
    
    # Посилання на текстури
    texture_normal_smooth: bpy.props.PointerProperty(
        type=bpy.types.Image,
        name="Normal Smooth Texture"
    )
    
    texture_normal_flat: bpy.props.PointerProperty(
        type=bpy.types.Image,
        name="Normal Flat Texture"
    )
    
    texture_skew_mask: bpy.props.PointerProperty(
        type=bpy.types.Image,
        name="Skew Mask Texture"
    )
    
    resolution: bpy.props.EnumProperty(
        items=texture_res_items,
        name="Resolution",
        default='2048'
    )
    extrusion: bpy.props.FloatProperty(
        name="Ray Offset (Extrusion)",
        description="Ray Height for selected to active baking",
        default=0.05,  
        min=0.0,
        max=20.0,
        subtype='DISTANCE',
        update=_update_extrusion_value
    )
    filename: bpy.props.StringProperty(
        name="File Name",
        description="Base name for the generated baking textures",
        default="T_Model_Normal"
    )
    directx: bpy.props.BoolProperty(
        name="DirectX (-Y)",
        description="Invert the Green channel to match DirectX normal map format standards",
        default=False
    )
    lp_collection: bpy.props.PointerProperty(
        type=bpy.types.Collection,
        name="Low-Poly",
        description="Select the collection containing Low-Poly objects",
        update=_update_lp_collection
    )
    show_extrusion: bpy.props.BoolProperty(
        name="Show Extrusion",
        description="Show a wireframe preview merged from the Low-Poly collection",
        default=False,
        update=_update_extrusion_preview
    )
    extrusion_preview_obj: bpy.props.PointerProperty(
        type=bpy.types.Object,
        name="Extrusion Preview Object"
    )
    hp_collection: bpy.props.PointerProperty(
        type=bpy.types.Collection,
        name="High-Poly",
        description="Select the collection containing High-Poly objects"
    )
    merged_lp_obj: bpy.props.PointerProperty(
        type=bpy.types.Object,
        name="Merged Low-Poly Object"
    )
    merged_hp_obj: bpy.props.PointerProperty(
        type=bpy.types.Object,
        name="Merged High-Poly Object"
    )