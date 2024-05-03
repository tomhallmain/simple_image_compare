
# Simple Image Compare Tool

Simple image comparison tool that detects color and face similarities using CLIP embeddings (default) and color matching (separate optional mode).

## Usage

Clone this repository and ensure Python 3 and the required packages are installed from requirements.txt.

Run `app.py` to start the UI, or provide the location of the directory containing images for comparison to `compare_embeddings.py` or `compare.py` at runtime.

Useful for detecting duplicates or finding associations between large unstructured sets of image files. File management controls are available after the image analysis has completed.

Individual images can be passed to search against the full image data set by passing flag `--search` with the path of the search file, or setting a search file in the UI before running comparison.

## Image Browser

The UI can be used as an image file browser. This is especially useful on Windows 11 as there is an option to auto-resize images to fill the screen as well as to auto-refresh the directory files, which the default Windows Photo Viewer application does not support. In addition, tests indicate that it supports quicker and smoother transitions between images as well as a faster load time for directories with many images in some cases. You can also use this mode to mark groups of files and move them to various target directories.

It is not implemented yet, but there will ultimately be zoom and drag functionality in browsing mode, as well as when viewing grouped images after a comparison has been run.

## Configuration

Setting `clip_model` defines the CLIP model to use for generating embeddings.

Setting `file_types` defines the allowed file extensions for gathering image files.

Setting `file_check_interval_seconds` defines the interval between auto-updates to identify recent file changes.

Setting `sort_by` defines the default image browsing sort setting upon starting the application.

Setting `trash_folder` defines the target folder for image deletion. If not set, deletion will send the image to your system's default trash folder.

If the `sd_prompt_reader_loc` config setting is pointing to your local copy of [stable-diffusion-prompt-reader](https://github.com/receyuki/stable-diffusion-prompt-reader) then opening image details for an image with a stable diffusion prompt will give prompt information found in the image.

Setting `tag_suggestions_file` should point to a JSON list that provides suggested tags for images for easy access in adding tags, if desired.

## UI Bindings

A directory with images must be set before most of the below bindings will have any effect. The group bindings are only functional in GROUP mode after a comparison has been run.

| Keys             | Mouse            | Effect               |
|------------------|------------------|----------------------|
| Shift-H          |                  | Show help window     |
| Shift-D          |                  | Show image details   |
| Home             |                  | Reset image browser  |
| Page Up          |                  | Page through images  |
| Page Down        |                  | Page through images  |
| Shift-M          |                  | Add/remove a mark    |
| Shift-N          |                  | Add marks from last  |
| Shift-G          |                  | Go to next mark      |
| Shift-C          |                  | Copy marks list      |
| Ctrl-M           |                  | Move marks to dir    |
| Left Arrow       | Mouse Wheel Up   | Show previous image  |
| Right Arrow      | Mouse Wheel Down | Show next image      |
| Shift-Left       |                  | Show previous group  |
| Shift-Right      |                  | Show next group      |
| Shift-Enter      |                  | Open image location  |
| Shift-Delete     | Mouse Wheel Click| Delete image         |
| F11              |                  | Toggle fullscreen    |

## Limitations

This is a very simple app. It is primarily meant for personal use but could be adapted for more intensive use cases.

The face similarity measure in particular is very crude and only compares the number of faces in each image, so it is off by default. At a future time more complex face comparison logic may be added, but for now the embedding comparison is helpful in matching faces.

GIFs are not currently supported, but may be at a future date.
