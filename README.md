<div align="center">

  <h2 align="center">Blender Material JSON Texture Importer</h2>

</div>

## Overview

This is a Blender add-on created to help the process of applying textures specified in Unreal Engine material JSON files to imported objects. Given a directory, it will look for JSON files with names matching the object's materials and that contain texture paths. Then the add-on will apply textures found in the same directory as the JSON to any matched materials.

**The JSON does not need to originate from UE or a tool like FModel- textures will be applied as long as the JSON name matches the material and any texture files are correctly defined and in the same folder.**

## Features

- **Material Files Scan:** Looks for JSON files and colocated textures in a specified directory and its subdirectories. Recognized texture types: `jpg, jpeg, png, tga, bmp, tiff, exr, dds.`
- **Applied Texture Maps:** Extracts texture paths and applies the texture to matched materials, **currently supporting diffuse and normal maps only.**
- **Convenient UI:** Provides a side panel in Blender's 3D view to access add-on functionality.
- **Verbose Logging:** Outputs to Blender's system console for diagnosing import issues.

## Example

Asset Directory Structure

```
ChairModel/
├── ChairFancy.psk
├── BaseTexture/
│   ├── MI_ChairBase.json
│   ├── T_ChairBase_D.png
│   └── T_ChairBase_N.png
└── BackTexture/
    ├── MI_ChairBack.json
    ├── T_ChairBack_D.png
    └── T_ChairBack_N.png
```

`MI_ChairBase.json`

```json
{
	"Textures": {
		"PM_Diffuse": ".../T_ChairBase_D.T_Chairbase_D",
		"PM_Normals": "T_ChairBase_N"
	}
}
```

## Installation

1. Download the add-on from [releases](https://github.com/yuandere/blender_material_json_import/releases/latest)
2. In Blender, navigate `Edit -> Preferences -> Add-ons -> Install from disk` and open the downloaded file
3. Make sure the add-on is enabled

## Usage

1. Ensure any material JSONs are correctly formatted and associated textures are in the same folder
2. Open the Blender side panel interface and select an object
3. Paste in a path or use the file browser to select your JSON root directory
4. Click Apply Textures

## Planned Improvements

- Support for alpha maps and common channel packed textures

## Contributing

Contributions are welcome. Feel free to create a pull request or submit an issue for new features, fixing bugs, or improving documentation.
