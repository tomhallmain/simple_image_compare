
# Simple Image Compare Tool

Simple image comparison tool that detects color and face similarities.

## Usage

Clone this repository and ensure python 3 and the required packages are installed.

Run the app.py file to start the UI, or provide the location of the directory containing images for comparison to the compare.py file at runtime.

Useful for detecting duplicates or finding associations between large unstructured sets of image files. File management controls are availalbe after the image analysis has completed.

Individual images can be passed to search against the full image data set by passing flag `--search` with the path of the search file, or selecting setting a search file in the UI before running comparison.

## Limitations

This is a very simple ap and can only detect fairly similar images. While unmatched dimensions are not an issue, similar images with highly varying perspectives (for example, if images are the same but one is turned sideways) will likely not generate a similar result.

The face similarity measure is very crude, and only checks the number of faces in the image. At a future time more complex face matching may be added.

