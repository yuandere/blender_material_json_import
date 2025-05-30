import bpy
from .main import register as main_register, unregister as main_unregister

bl_info = {
    "name": "Material Texture Applier",
    "author": "yuandere",
    "version": (1, 0),
    "blender": (2, 80, 0),
    "location": "3D Viewport > Sidebar > Material Textures",
    "description": "Apply textures from JSON files to selected object materials",
    "category": "Material",
}


def register():
    main_register()


def unregister():
    main_unregister()


if __name__ == "__main__":
    register()
