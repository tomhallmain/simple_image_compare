
# Simple Image Compare Tool

Simple image comparison tool that detects color and face similarities using CLIP embeddings (default) and color matching (separate optional mode).

## Usage

Clone this repository and ensure Python 3 and the required packages are installed from requirements.txt.

Run `app.py` to start the UI, or provide the location of the directory containing images for comparison to `compare_embeddings.py` or `compare.py` at runtime.

Useful for detecting duplicates or finding associations between large unstructured sets of image files. File management controls are available after the image analysis has completed.

Individual images can be passed to search against the full image data set by passing flag `--search` with the path of the search file, or setting a search file in the UI before running comparison.

The color matching compare mode is faster than CLIP embedding but less robust. In the group comparison case, since every image must be compared to every other image the time complexity is $\mathcal{O}(n^2)$. To remedy this issue for large image sets, set the `store_checkpoints` config setting to enable process caching to close and pick up where you left off previously, but ensure no files are added or removed from the comparison directory before restarting a compare.

When using CLIP embedding compare mode, you can search your images by text - both positive and negative. Commas will break the texts to search into multiple parts, to be combined in a final set of results. If there is a good CLIP signal for the search texts it will likely return the images you are looking for. It will take a while to load the first time as embeddings need to be generated. If a list of preset text searches is defined in your config JSON, you can cycle between them with the dedicated shortcut found below.

If a search image is set simultaneously with search text, its embedding will be factored into the search at a weight equal to a single search text part.

## Image Browser

The UI can be used as an image file browser. This is especially useful on Windows as the following features are available that the default Windows Photo Viewer application either does not support or makes hard to quickly reconfigure:
- Auto-resize images to fill the screen
- Auto-refresh directory files
- Slideshow (customizable)
- Quicker and smoother transitions between images
- Faster load time for directories with many images in some cases
- Faster load times when switching between sort types
- Go to file by string search
- Mark groups of files to enable quick transitions and comparisons
- Move, copy, and delete marked file groups
- Revert and modify file action changes
- Quickly find directories via recent directory picker window
- Stores session info about seen directories (useful for directories with many images)
- Can be set up to run on user-defined list of files in place of a directory
- Extension with [sd-runner](https://github.com/tomhallmain/sd-runner) for image generation
- Extension with [refacdir](https://github.com/tomhallmain/refacdir) for file operations
- Find related images and prompts from embedded Stable Diffusion workflows
- Sort files by related images and prompts
- View raw image metadata
- Content filtering of images based on their text CLIP similarity (automatically hide, move to dir, delete etc)

Zoom and drag functionality is available in both browsing mode, as well as when viewing grouped images after a comparison has been run.

## Configuration

`clip_model` defines the CLIP model to use for generating embeddings.

`file_types` defines the allowed file extensions for gathering image files.

`file_check_interval_seconds` defines the interval between auto-updates to identify recent file changes.

`slideshow_interval_seconds` defines the interval between slideshow transitions.

`sort_by` defines the default image browsing sort setting upon starting the application.

`trash_folder` defines the target folder for image deletion. If not set, deletion will send the image to your system's default trash folder.

If the `sd_prompt_reader_loc` config setting is pointing to your local copy of [stable-diffusion-prompt-reader](https://github.com/receyuki/stable-diffusion-prompt-reader) then opening image details for an image with a stable diffusion prompt will give prompt information found in the image.

`tag_suggestions_file` should point to a JSON list that provides suggested tags for images for easy access in adding tags, if desired.

`file_path_json_path` should be set to the path for the file path JSON, if setting `use_file_path_json` is set to true.

`text_embedding_search_presets_exclusive` enables the search results returned by preset search texts to be exclusive of eachother to more accurately categorize. Note that since some text embeddings have a much stronger signal than others clustering on those searches can occur.

`store_checkpoints` will cache a group comparison process at certain checkpoints for later restart.

## Key and Mouse Bindings

While the UI elements support normal usage in most cases, there are many bindings that enable extended functionality, mostly to minimize UI content unrelated to image viewers.

Press Shift+H to open up a help window with all key bindings. A directory with images must be set before most of the bindings will have any effect. The group bindings are only functional in GROUP mode after a comparison has been run.

## Move Marks Window Behavior

When the move marks window is open -- with or without GUI -- marks can be moved to a target directory by pressing the Enter key, or with the GUI elements if visible. After pressing the Enter key, a number of things can occur:

- If no target directories have been set, a folder picker window will open to set a new directory.

- If a marks action has been run previously, simply pressing Enter without a filter set will use the directory last used for the move or copy action.

- If target directories have been set and a filter is set, the move or copy operation will use the first target directory in the filtered list.

- If shift key is pressed along with Enter, the files will be copied instead of moved.

- If control key is pressed, any previously marked directories will be ignored and a folder picker window will open to set a new target directory.

- If alt key is pressed, the penultimate mark target dir will be used as target directory. This is useful when you want to successively copy files to one directory and then move them to another, without having to re-filter each time.

Simply typing letters while the mark window is open will filter the list of mark target directories, even if the GUI is not present. The backspace key will delete letters from the filter. You can scroll through the list of saved target directories using arrow keys.

To bypass the move marks window, use the Ctrl+R or Ctrl+E shortcuts to immediately run the previous and penultimate actions respectively on the current selection. You can also use number keys or Ctrl+T as hotkeys for persistent marks actions. To set a number key while in the marks window, use Shift+{desired number key}.

Ctrl+Z will undo the previous file marks move or copy action. If an earlier action needs to be reversed or modified, open the marks history window to verify the action in the history list and reverse it via the UI.

## File Actions Window Behavior

The file actions window displays a certain number of completed actions, as defined in the config JSON. Similar to the move marks window, typing will add to a text filter that filters the actions by the target directory basenames.

On this window the previous file action images can be viewed and reversed or modified if desired.

## Limitations

**NOTE** - It is not currently possible to undo a delete action, however unless the delete folder is explicitly set to null in the config it is likely the deleted items will be saved in a trash folder before being fully removed.

This is a simple app primarily meant for personal use but could be adapted for more intensive use cases.

The face similarity measure in particular is very crude and only compares the number of faces in each image, so it is off by default. At a future time more complex face comparison logic may be added, but for now the embedding comparison is helpful in matching faces.

GIFs are not currently supported, but may be at a future date.
