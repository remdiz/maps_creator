import bpy      # type: ignore

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
        max=10.0,
        subtype='DISTANCE'
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
        description="Select the collection containing Low-Poly objects"
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