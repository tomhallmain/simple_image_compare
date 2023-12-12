
# Simple Image Compare Tool

Simple image comparison tool that detects color and face similarities.

## Usage

Clone this repository and ensure python 3 and the required packages are installed from requirements.txt.

Run `app.py` to start the UI, or provide the location of the directory containing images for comparison to `compare.py` at runtime.

Useful for detecting duplicates or finding associations between large unstructured sets of image files. File management controls are available after the image analysis has completed.

Individual images can be passed to search against the full image data set by passing flag `--search` with the path of the search file, or selecting setting a search file in the UI before running comparison.

## Limitations

This is a very simple app and can only detect fairly similar images based on colors and positioning. There is no neural net involved in the main comparison at this time. While unmatched dimensions are not an issue, similar images with highly varying perspectives (for example, if images are the same but one is turned sideways) will likely not generate a similar result.

The face similarity measure is also very crude and only compares the number of faces in each image, so it is off by default. At a future time more complex comparison logic may be added. Even so, it can be fairly handy for quick comparison across large image sets.

