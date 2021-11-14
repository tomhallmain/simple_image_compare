
# Simple Image Compare Tool

Simple image comparison tool that detects color and face similarities.

## Usage

Clone this repository and ensure python 3 and the required packages are installed. Provide the location of the directory containing images for comparison to the script at runtime.

Useful for detecting duplicates or finding associations between large unstructured sets of image files.

Individual images can be passed to search against image data by passing flag `--search` with the path of the search file.

## Limitations

This is a very simple script and can only detect fairly similar images. While unmatched dimensions are not an issue, similar images with highly varying perspectives (for example, if images are the same but one is turned sideways) will likely not generate a similar result.

The face similarity measure is very crude, and only checks the number of faces in the image. At a future time more complex face matching may be added.

