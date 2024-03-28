
# Simple Image Compare Tool

Simple image comparison tool that detects color and face similarities.

## Usage

Clone this repository and ensure Python 3 and the required packages are installed from requirements.txt.

Run `app.py` to start the UI, or provide the location of the directory containing images for comparison to `compare.py` at runtime.

Useful for detecting duplicates or finding associations between large unstructured sets of image files. File management controls are available after the image analysis has completed.

Individual images can be passed to search against the full image data set by passing flag `--search` with the path of the search file, or selecting setting a search file in the UI before running comparison.

## Image Browser

After setting a directory before a comparison is run, the UI can be used as an image file browser. This is especially useful on Windows 11 as there is an option to auto-resize images to fill the screen as well as to auto-refresh the directory files, which the default Windows Photo Viewer application does not support.

It is not implemented yet, but there will ultimately be zoom and drag functionality on this image browser, as well as when viewing grouped images after a comparison has been run.

## Configuration

Setting `file_check_interval_seconds` defines the interval between auto-updates to identify recent file changes.

Setting `sort_by` defines the default image browsing sort setting upon starting the application.

Setting `trash_folder` defines the target folder for image deletion. If not set, deletion will send the image to your system's default trash folder.

If the `sd_prompt_reader_loc` config setting is pointing to your local copy of [stable-diffusion-prompt-reader](https://github.com/receyuki/stable-diffusion-prompt-reader) then opening image details for an image with an stable diffusion prompt will give prompt information found in the image.

## UI Bindings

A directory must be set and/or a comparison must be run for the below bindings to work.

| Keys             | Mouse            | Effect               |
|------------------|------------------|----------------------|
| Shift-D          |                  | Show image details   |
| Left Arrow       | Mouse Wheel Up   | Show previous image  |
| Right Arrow      | Mouse Wheel Down | Show next image      |
| Shift-Left       |                  | Show prev group      |
| Shift-Right      |                  | Show next group      |
| Shift-Enter      |                  | Open image location  |
| Shift-Delete     | Mouse Wheel Click| Delete image         |
| F11              |                  | Toggle fullscreen    |

## Limitations

This is a very simple app and can only detect fairly similar images based on colors and positioning. There is no neural net involved in the main comparison at this time. While unmatched dimensions are not an issue, similar images with highly varying perspectives (for example, if images are the same but one is turned sideways) will likely not generate a similar result.

The face similarity measure is also very crude and only compares the number of faces in each image, so it is off by default. At a future time more complex comparison logic may be added. Even so, it can be fairly handy for quick comparison across large image sets.

