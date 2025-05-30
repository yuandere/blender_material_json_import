import bpy
import json
import os
from bpy.props import StringProperty, PointerProperty
from bpy.types import Panel, Operator, PropertyGroup


class MaterialTextureProperties(PropertyGroup):
    json_root_directory: StringProperty(
        name="JSON Root Directory",
        description="Root directory to search for JSON files (searches subdirectories)",
        default="",
        maxlen=1024,
        subtype='DIR_PATH'
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

        # Remove T_ prefix if present
        if filename.startswith('T_'):
            filename = filename[2:]

        return filename

    def get_texture_file_path(self, texture_path_from_json, texture_directory):
        """Get the actual texture file path, trying different extensions"""
        if not texture_path_from_json:
            return None

        print(
            f"Looking for texture: {texture_path_from_json} in directory: {texture_directory}")

        # Extract base filename
        filename = self.extract_texture_filename(texture_path_from_json)
        print(f"Extracted filename: {filename}")

        if not filename:
            return None

        # Try common texture extensions
        extensions = ['.png', '.jpg', '.jpeg',
                      '.tga', '.exr', '.tiff', '.bmp', '.dds']

        for ext in extensions:
            full_path = os.path.join(texture_directory, filename + ext)
            print(f"Trying: {full_path}")
            if os.path.exists(full_path):
                print(f"Found texture at: {full_path}")
                return full_path

        # Also try the original filename structure in case it exists
        original_parts = texture_path_from_json.split('/')
        original_filename = original_parts[-1]
        print(f"Trying original filename: {original_filename}")

        for ext in extensions:
            # Try with original filename
            full_path = os.path.join(
                texture_directory, original_filename + ext)
            print(f"Trying original: {full_path}")
            if os.path.exists(full_path):
                print(f"Found texture at: {full_path}")
                return full_path

            # Try with first part before the dot if it exists
            if '.' in original_filename:
                base_part = original_filename.split('.')[0]
                full_path = os.path.join(texture_directory, base_part + ext)
                print(f"Trying base part: {full_path}")
                if os.path.exists(full_path):
                    print(f"Found texture at: {full_path}")
                    return full_path

        print(f"No texture file found for: {texture_path_from_json}")
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
                print(f"JSON content: {material_data}")
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
                if material_output:
                    links.new(principled.outputs['BSDF'],
                              material_output.inputs['Surface'])

            # Apply diffuse texture
            if 'PM_Diffuse' in material_data['Textures'] and material_data['Textures']['PM_Diffuse']:
                diffuse_path = self.get_texture_file_path(
                    material_data['Textures']['PM_Diffuse'], json_info['directory'])

                if diffuse_path:
                    # Check if diffuse is already connected
                    if not principled.inputs['Base Color'].is_linked:
                        # Create image texture node
                        diffuse_tex = nodes.new(type='ShaderNodeTexImage')
                        diffuse_tex.image = bpy.data.images.load(diffuse_path)
                        diffuse_tex.location = (-600, 600)

                        # Connect to Base Color
                        links.new(
                            diffuse_tex.outputs['Color'], principled.inputs['Base Color'])
                        applied_count += 1
                        print(f"Applied diffuse texture: {diffuse_path}")
                    else:
                        skipped_count += 1
                        print(
                            f"Skipped diffuse for {material_name} (already connected)")
                else:
                    print(
                        f"Diffuse texture not found: {material_data['Textures']['PM_Diffuse']}")

            # # Apply specular mask texture
            # if 'PM_SpecularMasks' in material_data['Textures'] and material_data['Textures']['PM_SpecularMasks']:
            #     specular_path = self.get_texture_file_path(material_data['Textures']['PM_SpecularMasks'], json_info['directory'])

            #     if specular_path:
            #         # Check if specular is already connected
            #         if not principled.inputs['Specular'].is_linked:
            #             # Create image texture node for specular mask
            #             specular_tex = nodes.new(type='ShaderNodeTexImage')
            #             specular_tex.image = bpy.data.images.load(specular_path)
            #             specular_tex.image.colorspace_settings.name = 'Non-Color'
            #             specular_tex.location = (-600, -600)

            #             # Connect to Specular input
            #             links.new(specular_tex.outputs['Color'], principled.inputs['Specular'])
            #             applied_count += 1
            #             print(f"Applied specular mask: {specular_path}")
            #         else:
            #             skipped_count += 1
            #             print(f"Skipped specular for {material_name} (already connected)")
            #     else:
            #         print(f"Specular mask not found: {material_data['Textures']['PM_SpecularMasks']}")

            # Apply normal texture
            if 'PM_Normals' in material_data['Textures'] and material_data['Textures']['PM_Normals']:
                normal_path = self.get_texture_file_path(
                    material_data['Textures']['PM_Normals'], json_info['directory'])

                if normal_path:
                    # Check if normal is already connected
                    if not principled.inputs['Normal'].is_linked:
                        # Create image texture node for normal
                        normal_tex = nodes.new(type='ShaderNodeTexImage')
                        normal_tex.image = bpy.data.images.load(normal_path)
                        normal_tex.image.colorspace_settings.name = 'Non-Color'
                        normal_tex.location = (-600, 0)

                        # Create normal map node
                        normal_map = nodes.new(type='ShaderNodeNormalMap')
                        normal_map.location = (-300, 0)

                        # Connect normal texture to normal map, then to principled
                        links.new(
                            normal_tex.outputs['Color'], normal_map.inputs['Color'])
                        links.new(
                            normal_map.outputs['Normal'], principled.inputs['Normal'])
                        applied_count += 1
                        print(f"Applied normal texture: {normal_path}")
                    else:
                        skipped_count += 1
                        print(
                            f"Skipped normal for {material_name} (already connected)")
                else:
                    print(
                        f"Normal texture not found: {material_data['Textures']['PM_Normals']}")

        # Report results
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

        layout.prop(props, "json_root_directory")

        layout.separator()

        # Show selected object info
        if context.active_object:
            layout.label(text=f"Selected: {context.active_object.name}")
            if context.active_object.material_slots:
                layout.label(
                    text=f"Materials: {len(context.active_object.material_slots)}")

                # Show material names for reference
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

        # Apply button
        layout.operator("material.apply_textures",
                        text="Apply Textures", icon='MATERIAL')


def register():
    bpy.utils.register_class(MaterialTextureProperties)
    bpy.utils.register_class(MATERIAL_OT_apply_textures)
    bpy.utils.register_class(MATERIAL_PT_texture_applier)

    bpy.types.Scene.material_texture_props = PointerProperty(
        type=MaterialTextureProperties)


def unregister():
    bpy.utils.unregister_class(MaterialTextureProperties)
    bpy.utils.unregister_class(MATERIAL_OT_apply_textures)
    bpy.utils.unregister_class(MATERIAL_PT_texture_applier)

    del bpy.types.Scene.material_texture_props


if __name__ == "__main__":
    register()
