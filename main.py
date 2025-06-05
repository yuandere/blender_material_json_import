import bpy
import json
import os
from bpy.props import StringProperty, BoolProperty, EnumProperty, CollectionProperty, PointerProperty
from bpy.types import Panel, Operator, PropertyGroup, UIList


COLORSPACE_ITEMS = [
    ('sRGB', 'sRGB', ''),
    ('Non-Color', 'Non-Color', '')
]

TEXTURE_SLOTS_DEFAULTS = [
    dict(
        slot_name="diffuse",
        json_keys=["PM_Diffuse", "Diffuse", "BaseColor"],
        input_name="Base Color",
        color_space="sRGB",
        invert=False,
        use_alpha=False
    ),
    dict(
        slot_name="normal",
        json_keys=["PM_Normals", "Normal", "NormalMap"],
        input_name="Normal",
        color_space="Non-Color",
        invert=False,
        use_alpha=False
    ),
    dict(
        slot_name="alpha",
        json_keys=["PM_Alpha", "Alpha", "Opacity"],
        input_name="Alpha",
        color_space="Non-Color",
        invert=False,
        use_alpha=True
    ),
]


class TextureSlotKey(PropertyGroup):
    name: StringProperty(name="JSON Key")


class TextureSlotProperty(PropertyGroup):
    slot_name: StringProperty(name="Slot Name")
    input_name: StringProperty(name="BSDF Input")
    color_space: EnumProperty(
        name="Color Space", items=COLORSPACE_ITEMS, default='sRGB')
    invert: BoolProperty(name="Invert", default=False)
    use_alpha: BoolProperty(name="Use Alpha", default=False)
    json_keys: CollectionProperty(type=TextureSlotKey)
    json_keys_index: bpy.props.IntProperty(default=0)

    def get_json_keys(self):
        return [k.name for k in self.json_keys]


class MaterialTextureProperties(PropertyGroup):
    json_root_directory: StringProperty(
        name="JSON Root Directory",
        description="Root directory to search for JSON files (searches subdirectories)",
        default="",
        maxlen=1024,
        subtype='DIR_PATH'
    )
    texture_slots: CollectionProperty(type=TextureSlotProperty)
    texture_slots_index: bpy.props.IntProperty(default=0)
    show_materials_list: BoolProperty(
        name="Show Materials List",
        description="Show/hide the list of materials on the selected object",
        default=False
    )


class MATERIAL_OT_apply_textures(Operator):
    """Apply textures from JSON files to selected object materials"""
    bl_idname = "material.apply_textures"
    bl_label = "Apply Textures"
    bl_options = {'REGISTER', 'UNDO'}

    def find_json_files(self, root_directory):
        """Recursively find all JSON files and return dict with filename (without .json) as key"""
        json_files = {}

        for root, dirs, files in os.walk(root_directory):
            for file in files:
                if file.lower().endswith('.json'):
                    full_path = os.path.join(root, file)
                    # Use filename without extension as key
                    filename_key = os.path.splitext(file)[0]
                    json_files[filename_key] = {
                        'path': full_path,
                        'directory': root
                    }

        return json_files

    def normalize_material_name(self, material_name):
        """Normalize material name for comparison by removing common prefixes"""
        name = material_name

        # Remove common prefixes (case-sensitive check first, then remove)
        prefixes = ['MI_', 'M_', 'MAT_', 'MATERIAL_',
                    'mi_', 'm_', 'mat_', 'material_']
        for prefix in prefixes:
            if name.startswith(prefix):
                name = name[len(prefix):]
                break

        return name

    def extract_texture_filename(self, texture_path):
        """Extract the actual filename from the texture path and clean it up"""
        if not texture_path:
            return None

        # Split by forward slashes and take the last part
        parts = texture_path.split('/')
        filename = parts[-1]

        # If there's a dot followed by the same filename, take the first part
        if '.' in filename:
            base_name = filename.split('.')[0]
            # Check if the part after the dot matches the base name
            after_dot = '.'.join(filename.split('.')[1:])
            if after_dot == base_name:
                filename = base_name

        return filename

    def find_texture_files(self, root_directory):
        """Recursively find all texture files and return dict with base filename (case-insensitive, no extension) as key"""
        texture_files = {}
        extensions = ['.png', '.jpg', '.jpeg',
                      '.tga', '.exr', '.tiff', '.bmp', '.dds']
        for root, dirs, files in os.walk(root_directory):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in extensions:
                    base = os.path.splitext(file)[0].lower()
                    texture_files[base] = os.path.join(root, file)
        return texture_files

    def get_texture_file_path(self, texture_path_from_json, texture_files_dict):
        """Get the actual texture file path from the global texture dict, trying different extensions and variants"""
        if not texture_path_from_json:
            return None
        # Extract base filename
        filename = self.extract_texture_filename(texture_path_from_json)
        if not filename:
            return None
        base = os.path.splitext(filename)[0].lower()
        # Try direct match
        if base in texture_files_dict:
            return texture_files_dict[base]
        # Try more variants (e.g., original filename with extension, or base part before dot)
        original_parts = texture_path_from_json.split('/')
        original_filename = original_parts[-1]
        original_base = os.path.splitext(original_filename)[0].lower()
        if original_base in texture_files_dict:
            return texture_files_dict[original_base]
        # Try with just the first part before a dot
        if '.' in original_filename:
            first_part = original_filename.split('.')[0].lower()
            if first_part in texture_files_dict:
                return texture_files_dict[first_part]
        # Not found
        return None

    def execute(self, context):
        props = context.scene.material_texture_props

        # Validate inputs
        if not props.json_root_directory:
            self.report({'ERROR'}, "Please specify JSON root directory")
            return {'CANCELLED'}

        # Fix Blender's directory picker path issues
        json_root = props.json_root_directory
        if json_root.startswith('//'):
            # Convert Blender relative path to absolute
            json_root = bpy.path.abspath(json_root)

        # Normalize path separators
        json_root = os.path.normpath(json_root)

        if not os.path.isdir(json_root):
            self.report(
                {'ERROR'}, f"JSON root directory not found: {json_root}")
            return {'CANCELLED'}

        # Check if an object is selected
        if not context.active_object:
            self.report({'ERROR'}, "No object selected")
            return {'CANCELLED'}

        obj = context.active_object
        if not obj.material_slots:
            self.report({'WARNING'}, "Selected object has no materials")
            return {'CANCELLED'}

        # Find all JSON files
        print("Scanning for JSON files...")
        json_files = self.find_json_files(json_root)

        # Find all texture files
        print("Scanning for texture files...")
        texture_files_dict = self.find_texture_files(json_root)
        print(f"Found {len(texture_files_dict)} texture files")

        if not json_files:
            self.report({'ERROR'}, "No JSON files found in directory tree")
            return {'CANCELLED'}

        print(f"Found {len(json_files)} JSON files")

        applied_count = 0
        skipped_count = 0
        matched_materials = 0

        # Process each material on the selected object
        for slot in obj.material_slots:
            if not slot.material:
                continue

            material = slot.material
            material_name = material.name
            normalized_name = self.normalize_material_name(material_name)

            print(
                f"Processing material: {material_name} (normalized: {normalized_name})")

            # Look for matching JSON file
            json_info = None
            matched_key = None

            # Try exact match with original name first
            if material_name in json_files:
                json_info = json_files[material_name]
                matched_key = material_name
            else:
                # Try case-insensitive match with original name
                for key in json_files.keys():
                    if key.lower() == material_name.lower():
                        json_info = json_files[key]
                        matched_key = key
                        break

                # If still no match, try with normalized name
                if not json_info:
                    if normalized_name in json_files:
                        json_info = json_files[normalized_name]
                        matched_key = normalized_name
                    else:
                        # Try case-insensitive match with normalized name
                        for key in json_files.keys():
                            if key.lower() == normalized_name.lower():
                                json_info = json_files[key]
                                matched_key = key
                                break

            if not json_info:
                print(f"No matching JSON file for material: {material_name}")
                continue

            print(f"Found matching JSON: {matched_key} at {json_info['path']}")
            matched_materials += 1

            # Load JSON data
            try:
                with open(json_info['path'], 'r') as f:
                    material_data = json.load(f)
            except Exception as e:
                print(f"Error reading JSON file {json_info['path']}: {str(e)}")
                continue

            # Ensure material uses nodes
            if not material.use_nodes:
                material.use_nodes = True

            nodes = material.node_tree.nodes
            links = material.node_tree.links

            # Find or create Principled BSDF node
            principled = None
            for node in nodes:
                if node.type == 'BSDF_PRINCIPLED':
                    principled = node
                    break

            if not principled:
                principled = nodes.new(type='ShaderNodeBsdfPrincipled')
                # Connect to material output if it exists
                material_output = None
                for node in nodes:
                    if node.type == 'OUTPUT_MATERIAL':
                        material_output = node
                        break
            # Main texture-application loop
            for tex_slot in props.texture_slots:
                # Only use the active JSON key
                tex_path_from_json = None
                if not material_data or 'Textures' not in material_data:
                    print(
                        f"Material data missing or malformed for {material_name}")
                    continue
                keys = tex_slot.get_json_keys()
                json_key = keys[tex_slot.json_keys_index] if keys and 0 <= tex_slot.json_keys_index < len(
                    keys) else None
                if json_key and json_key in material_data['Textures']:
                    tex_path_from_json = material_data['Textures'][json_key]
                if not tex_path_from_json:
                    print(
                        f"No matching JSON key for slot '{tex_slot.slot_name}' in material '{material_name}' (active key: {json_key if keys else 'None'})")
                    continue
                # Extract just the filename for lookup
                tex_filename = self.extract_texture_filename(
                    tex_path_from_json)
                if not tex_filename:
                    print(
                        f"Could not extract filename from path '{tex_path_from_json}' for slot '{tex_slot.slot_name}'")
                    continue
                tex_file_path = self.get_texture_file_path(
                    tex_filename, texture_files_dict)
                if not tex_file_path:
                    print(
                        f"{tex_slot.slot_name.title()} texture not found: {tex_filename}")
                    continue
                # Avoid duplicate connections
                input_socket = principled.inputs.get(tex_slot.input_name)
                if not input_socket or input_socket.is_linked:
                    skipped_count += 1
                    print(
                        f"Skipped {tex_slot.slot_name} for {material_name} (already connected or missing input)")
                    continue
                # Create image texture node
                tex_node = nodes.new(type='ShaderNodeTexImage')
                tex_node.image = bpy.data.images.load(tex_file_path)
                tex_node.location = (-600, 600 - 300 *
                                     list(props.texture_slots).index(tex_slot))
                tex_node.image.colorspace_settings.name = tex_slot.color_space
                # Special handling for normal maps
                if tex_slot.slot_name == "normal":
                    normal_map = nodes.new(type='ShaderNodeNormalMap')
                    normal_map.location = (-300, 600 - 300 *
                                           list(props.texture_slots).index(tex_slot))
                    links.new(tex_node.outputs['Color'],
                              normal_map.inputs['Color'])
                    links.new(
                        normal_map.outputs['Normal'], principled.inputs['Normal'])
                    applied_count += 1
                    print(f"Applied normal texture: {tex_file_path}")
                else:
                    links.new(
                        tex_node.outputs['Color'], principled.inputs[tex_slot.input_name])
                    applied_count += 1
                    print(
                        f"Applied {tex_slot.slot_name} texture: {tex_file_path}")
                    if tex_slot.use_alpha:
                        links.new(
                            tex_node.outputs['Alpha'], principled.inputs['Alpha'])
                        applied_count += 1
                        print(f"Applied alpha texture: {tex_file_path}")

            # Reporting
            if matched_materials == 0:
                self.report({'WARNING'}, "No materials matched any JSON files")
            elif applied_count > 0:
                message = f"Matched {matched_materials} material(s), applied {applied_count} texture(s)"
                if skipped_count > 0:
                    message += f", skipped {skipped_count} existing texture(s)"
                self.report({'INFO'}, message)
            elif skipped_count > 0:
                self.report(
                    {'INFO'}, f"Matched {matched_materials} material(s), all textures already present")
            else:
                self.report(
                    {'WARNING'}, f"Matched {matched_materials} material(s), but no textures were found or applied")

        return {'FINISHED'}


# Add-on UI Panel
class TEXTURE_UL_json_keys(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.prop(item, "name", text="", emboss=False, icon='TEXT')
            if index == data.json_keys_index:
                layout.label(text="(Active)", icon='CHECKMARK')
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text="{}".format(item.name))


class MATERIAL_PT_texture_applier(Panel):
    """Creates a Panel in the 3D Viewport N-Panel"""
    bl_label = "Material Texture Applier"
    bl_idname = "MATERIAL_PT_texture_applier"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Material Textures"

    def draw(self, context):
        layout = self.layout
        props = context.scene.material_texture_props

        if len(props.texture_slots) == 0:
            layout.operator("material.init_slots", icon='ADD')
            return
        else:
            layout.prop(props, "json_root_directory")
            layout.separator()

            layout.label(text="Texture Slot Configuration:")
            for idx, slot in enumerate(props.texture_slots):
                box = layout.box()
                row = box.row()
                row.prop(slot, "slot_name", text="Slot")
                row.prop(slot, "input_name", text="BSDF Input")
                row = box.row()
                row.prop(slot, "color_space", text="Color Space")
                # row.prop(slot, "invert", text="Invert")
                row.prop(slot, "use_alpha", text="Use Alpha")
                row.operator("material.reset_slot",
                             text="Reset").slot_index = idx
                # JSON Keys UIList
                row = box.row()
                row.label(text="JSON Keys:")
                row = box.row(align=True)
                row.template_list("TEXTURE_UL_json_keys", "", slot,
                                  "json_keys", slot, "json_keys_index", rows=2)
                col = row.column(align=True)
                col.operator("material.add_json_key", icon='ADD',
                             text="").slot_index = idx
                col.operator("material.remove_json_key",
                             icon='REMOVE', text="").slot_index = idx
                col.separator()
                col.operator("material.move_json_key_up",
                             icon='TRIA_UP', text="").slot_index = idx
                col.operator("material.move_json_key_down",
                             icon='TRIA_DOWN', text="").slot_index = idx
            layout.separator()

        # Show selected object info (collapsible)
        layout.prop(props, "show_materials_list", text="Show Materials List",
                    icon="TRIA_DOWN" if props.show_materials_list else "TRIA_RIGHT", emboss=False)
        if props.show_materials_list:
            if context.active_object:
                layout.label(text=f"Selected: {context.active_object.name}")
                if context.active_object.material_slots:
                    layout.label(
                        text=f"Materials: {len(context.active_object.material_slots)}")
                    box = layout.box()
                    box.label(text="Materials on object:")
                    for i, slot in enumerate(context.active_object.material_slots):
                        if slot.material:
                            row = box.row()
                            row.scale_y = 0.8
                            row.label(
                                text=f"• {slot.material.name}", icon='MATERIAL')
                else:
                    layout.label(text="No materials", icon='ERROR')
            else:
                layout.label(text="No object selected", icon='ERROR')
        layout.separator()
        layout.operator("material.apply_textures",
                        text="Apply Textures", icon='MATERIAL')


class MATERIAL_OT_add_json_key(bpy.types.Operator):
    bl_idname = "material.add_json_key"
    bl_label = "Add JSON Key"
    slot_index: bpy.props.IntProperty()

    def execute(self, context):
        props = context.scene.material_texture_props
        slot = props.texture_slots[self.slot_index]
        slot.json_keys.add().name = "NewKey"
        slot.json_keys_index = len(slot.json_keys) - 1
        return {'FINISHED'}


class MATERIAL_OT_remove_json_key(bpy.types.Operator):
    bl_idname = "material.remove_json_key"
    bl_label = "Remove JSON Key"
    slot_index: bpy.props.IntProperty()

    def execute(self, context):
        props = context.scene.material_texture_props
        slot = props.texture_slots[self.slot_index]
        if slot.json_keys and slot.json_keys_index >= 0:
            slot.json_keys.remove(slot.json_keys_index)
            slot.json_keys_index = max(0, slot.json_keys_index - 1)
        return {'FINISHED'}


class MATERIAL_OT_move_json_key_up(bpy.types.Operator):
    bl_idname = "material.move_json_key_up"
    bl_label = "Move JSON Key Up"
    slot_index: bpy.props.IntProperty()

    def execute(self, context):
        props = context.scene.material_texture_props
        slot = props.texture_slots[self.slot_index]
        idx = slot.json_keys_index
        if idx > 0:
            slot.json_keys.move(idx, idx - 1)
            slot.json_keys_index -= 1
        return {'FINISHED'}


class MATERIAL_OT_move_json_key_down(bpy.types.Operator):
    bl_idname = "material.move_json_key_down"
    bl_label = "Move JSON Key Down"
    slot_index: bpy.props.IntProperty()

    def execute(self, context):
        props = context.scene.material_texture_props
        slot = props.texture_slots[self.slot_index]
        idx = slot.json_keys_index
        if idx < len(slot.json_keys) - 1:
            slot.json_keys.move(idx, idx + 1)
            slot.json_keys_index += 1
        return {'FINISHED'}


class MATERIAL_OT_init_slots(bpy.types.Operator):
    bl_idname = "material.init_slots"
    bl_label = "Initialize Texture Slots"

    def execute(self, context):
        ensure_slots_initialized(context)
        self.report({'INFO'}, "Texture slots initialized.")
        return {'FINISHED'}


class MATERIAL_OT_reset_slot(bpy.types.Operator):
    bl_idname = "material.reset_slot"
    bl_label = "Reset Slot Settings"
    slot_index: bpy.props.IntProperty()

    def execute(self, context):
        props = context.scene.material_texture_props
        slot = props.texture_slots[self.slot_index]
        defaults = next(
            (s for s in TEXTURE_SLOTS_DEFAULTS if s['slot_name'] == slot.slot_name), None)
        if defaults:
            slot.input_name = defaults['input_name']
            slot.color_space = defaults['color_space']
            slot.invert = defaults['invert']
            slot.use_alpha = defaults['use_alpha']
            slot.json_keys.clear()
            for key in defaults['json_keys']:
                slot.json_keys.add().name = key
        return {'FINISHED'}


def ensure_slots_initialized(context):
    props = context.scene.material_texture_props
    if len(props.texture_slots) == 0:
        for slot_def in TEXTURE_SLOTS_DEFAULTS:
            slot = props.texture_slots.add()
            slot.slot_name = slot_def['slot_name']
            slot.input_name = slot_def['input_name']
            slot.color_space = slot_def['color_space']
            slot.invert = slot_def['invert']
            slot.use_alpha = slot_def['use_alpha']
            for key in slot_def['json_keys']:
                slot.json_keys.add().name = key


def register():
    bpy.utils.register_class(TextureSlotKey)
    bpy.utils.register_class(TextureSlotProperty)
    bpy.utils.register_class(TEXTURE_UL_json_keys)
    bpy.utils.register_class(MATERIAL_OT_add_json_key)
    bpy.utils.register_class(MATERIAL_OT_remove_json_key)
    bpy.utils.register_class(MATERIAL_OT_reset_slot)
    bpy.utils.register_class(MaterialTextureProperties)
    bpy.utils.register_class(MATERIAL_OT_apply_textures)
    bpy.utils.register_class(MATERIAL_PT_texture_applier)
    bpy.utils.register_class(MATERIAL_OT_init_slots)
    bpy.utils.register_class(MATERIAL_OT_move_json_key_up)
    bpy.utils.register_class(MATERIAL_OT_move_json_key_down)

    bpy.types.Scene.material_texture_props = PointerProperty(
        type=MaterialTextureProperties)


def unregister():
    bpy.utils.unregister_class(TextureSlotKey)
    bpy.utils.unregister_class(TextureSlotProperty)
    bpy.utils.unregister_class(TEXTURE_UL_json_keys)
    bpy.utils.unregister_class(MATERIAL_OT_add_json_key)
    bpy.utils.unregister_class(MATERIAL_OT_remove_json_key)
    bpy.utils.unregister_class(MATERIAL_OT_reset_slot)
    bpy.utils.unregister_class(MaterialTextureProperties)
    bpy.utils.unregister_class(MATERIAL_OT_apply_textures)
    bpy.utils.unregister_class(MATERIAL_PT_texture_applier)
    bpy.utils.unregister_class(MATERIAL_OT_init_slots)
    bpy.utils.unregister_class(MATERIAL_OT_move_json_key_up)
    bpy.utils.unregister_class(MATERIAL_OT_move_json_key_down)
    del bpy.types.Scene.material_texture_props


if __name__ == "__main__":
    register()
