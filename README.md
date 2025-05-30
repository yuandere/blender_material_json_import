<div align="center">

  <h2 align="center">Blender Material JSON Texture Importer</h2>

</div>



<!-- ABOUT THE PROJECT -->
## Overview

This is a Blender add-on created to help with the process of applying textures from Unreal Engine material JSON files to imported objects. Given a directory, it will look for JSON files with names matching the object's materials and that contain texture paths. Then the add-on will apply textures found in the same directory as the JSON to matched materials.

The JSON does not need to originate from UE or a tool like FModel, it can handle texture imports from any JSON as long as the filename matches the material name and the file structure matches the example below.


## Features
* **Material Files Scan:** Looks for JSON files in a specified directory and its subdirectories, applying textures to matched materials found in the selected Blender object.
* **Texture Maps:** Automatically detects and handles texture maps, **currently supporting diffuse and normal maps only.** 
* **Convenient UI:** Provides a side panel in 3D view to access texture importing functionality.
* **Verbose Logging:** Outputs to Blender's system console for diagnosing import issues.



## Example JSON
```json
// MI_Chair.json
{
  "Textures": {
    "PM_Diffuse": "T_Chair_D",
    "PM_Normals": "T_Chair_N",
    ...
  }, 
  ...
}
```

<!-- GETTING STARTED -->
## Installation

1. Download the repository from [releases](https://github.com/yuandere/blender_material_json_import/releases/latest)
2. In Blender, navigate `Edit -> Preferences -> Add-ons -> Install from disk` and open the downloaded file
3. Make sure the add-on is enabled

## Usage
1. Open the side panel interface and select an object
2. Paste in or use Blender's file browser to select your JSON root directory
3. Click Apply Textures


## Planned Improvements
* Support for alpha maps and common channel packed textures


<!-- CONTRIBUTING -->
## Contributing

Contributions are welcome. Feel free to create a pull request or submit an issue for new features, fixing bugs, or improving documentation. 

