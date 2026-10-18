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
#   - Bakes for different objects with different materials
#   - Progress bar
# ==================================================================

import bpy      # type: ignore
# import bmesh    # type: ignore
# import os
# import time

from .properties import SmartBakerSettings
from .operators import (
    OBJECT_OT_bake_normals,
    OBJECT_OT_activate_skew_paint,
    OBJECT_OT_finalize_bake,
)
from .ui import VIEW3D_PT_maps_panel

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

                
classes = [SmartBakerSettings,
           VIEW3D_PT_maps_panel, 
           OBJECT_OT_bake_normals,
           OBJECT_OT_activate_skew_paint,
           OBJECT_OT_finalize_bake,]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.smart_bake_settings = bpy.props.PointerProperty(type=SmartBakerSettings) 


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.smart_bake_settings