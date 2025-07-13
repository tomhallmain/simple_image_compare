# Simple Image Compare Tool

Simple image comparison tool that detects color and face similarities using CLIP embeddings (default) and color matching (separate optional mode). The tool now supports multiple embedding models:

- CLIP (default): 512D embeddings, high zero-shot performance
- SigLIP: 768D or 1024D embeddings, excellent retrieval performance
- ALIGN: 640D embeddings, high accuracy for retrieval
- FLAVA: 768D embeddings, good for complex reasoning
- X-VLM: 256D embeddings, efficient for region-text tasks - requires local copy of [X-VLM](https://github.com/zengyan-97/X-VLM)

Each model offers different tradeoffs between accuracy, speed, and resource usage. The default CLIP model provides a good balance for most use cases.

## Image and Video Browser

The UI can be used as a media file browser. The following features are available that your OS default photo application may not have:
<details>
<summary>Expand Features</summary>
<ul>
    <li>Auto-resize images to fill the screen</li>
    <li>Auto-refresh directory files</li>
    <li>Slideshow (customizable)</li>
    <li>Optionally play and compare video files and other media - typically will use the first image found for the comparison.</li>
    <li>Quicker and smoother transitions between images</li>
    <li>Faster load time for directories with many images in some cases</li>
    <li>Faster load times when switching between sort types</li>
    <li>Go to file by string search</li>
    <li>Mark groups of files to enable quick transitions and comparisons</li>
    <li>Move, copy, and delete marked file groups without overwriting system clipboard</li>
    <li>Revert and modify historical file action changes</li>
    <li>Quickly find directories via recent directory picker window</li>
    <li>Stores session info about seen directories (useful for directories with many images)</li>
    <li>Can be set up to run on user-defined list of files in place of a directory</li>
    <li>Extension with <a href="https://github.com/tomhallmain/sd-runner" target="_blank">sd-runner</a> for image generation</li>
    <li>Extension with <a href="https://github.com/tomhallmain/refacdir" target="_blank">refacdir</a> for file operations</li>
    <li>Find related images and prompts from embedded Stable Diffusion workflows</li>
    <li>Sort files by related images and prompts</li>
    <li>View raw image metadata</li>
    <li>Content filtering of images and videos based on their text encoding similarity (automatically hide, move to dir, delete etc)</li>
    <li>Create PDFs from marked files with customizable quality and compression options</li>
    <li>Password protection system for sensitive operations with configurable session timeouts</li>
</ul>
</details>

For image files, zoom and drag functionality is available in both browsing mode as well as when viewing grouped media after a comparison has been run.

Note that depending on your configuration videos, GIFs, PDFs, SVGs and HTMLs may not be included, you may need to open the filetype configuration window with Ctrl+J and turn them on.

## Prevalidation Rules

The tool includes a flexible prevalidation system that can automatically process media before they're shown to the user. This is useful for:

- Automatically skipping, hiding, or deleting unwanted media
- Moving or copying media to specific directories based on content
- Filtering media using CLIP embeddings, H5 image classifiers, prompt string detection
- Setting up rules that apply to specific directories

Prevalidation rules can be configured with:
- Multiple validation types enabled simultaneously (OR logic - any type can trigger the action)
- Positive and negative text prompts shared across embedding and prompt validation
- Custom thresholds for embedding-based matching
- Different actions (skip, hide, notify, move, copy, delete, add mark)
- Directory-specific rules
- H5 model-based classification rules

This feature is particularly useful for maintaining clean media collections and automating local content filtering, but it can be disabled at any time if desired. You can find an example H5 classifier that is known to work [here](https://github.com/FurkanGozukara/nsfw_model).

## Usage

Clone this repository and ensure Python 3 and the required packages are installed from requirements.txt.

Run `app.py` to start the UI, or provide the location of the directory containing images for comparison to `compare_embeddings.py` or `compare.py` at runtime.

<details>
<summary>Expand Details</summary>
Useful for detecting duplicates or finding associations between large unstructured sets of image files. File management controls are available after the image analysis has completed.

Individual images can be passed to search against the full image data set by passing flag `--search` with the path of the search file, or setting a search file in the UI before running comparison.

The color matching compare mode is faster than embedding comparison but less robust. In the group comparison case, since every image must be compared to every other image the time complexity is $\mathcal{O}(n^2)$. To remedy this issue for large image sets, set the `store_checkpoints` config setting to enable process caching to close and pick up where you left off previously, but ensure no files are added or removed from the comparison directory before restarting a compare.

When using embedding compare modes, you can search your images by text - both positive and negative. Commas will break the texts to search into multiple parts, to be combined in a final set of results. If there is a good embedding signal for the search texts it will likely return the images you are looking for. It will take a while to load the first time as embeddings need to be generated. If a list of preset text searches is defined in your config JSON, you can cycle between them with the dedicated shortcut found below.

If a search image is set simultaneously with search text, its embedding will be factored into the search at a weight equal to a single search text part.
</details>

### Configuration

<details>
<summary>Expand Details</summary>

`locale` supports any of the following locales:
- en (English)
- de (Deutsh)
- fr (Français)
- es (Español)
- it (Italiano)
- ja (日本語)
- ko (한국어)
- zh (中文)

`clip_model` defines the CLIP model to use for generating CLIP embeddings.

`image_types` defines the allowed file extensions for gathering image files, while `video_types` defines the allowed file extensions for gathering video files - there are only valid if the `enable_videos` setting is enabled.

`file_check_interval_seconds` defines the interval between auto-updates to identify recent file changes.

`slideshow_interval_seconds` defines the interval between slideshow transitions.

`sort_by` defines the default image browsing sort setting upon starting the application.

`trash_folder` defines the target folder for image deletion. If not set, deletion will send the image to your system's default trash folder.

`enable_prevalidations` enables the prevalidation system. When enabled, prevalidation rules will be applied to media before they are shown.

`image_classifier_h5_models` defines a list of H5 models that can be used for prevalidation rules. Each model should specify:
- `model_name`: A unique name for the model
- `model_location`: Path to the .h5 model file
- `model_categories`: List of categories the model can classify
- `use_hub_keras_layers`: Whether to use Keras hub layers

If the `sd_prompt_reader_loc` config setting is pointing to your local copy of [stable-diffusion-prompt-reader](https://github.com/receyuki/stable-diffusion-prompt-reader) then opening image details for an image with a stable diffusion prompt will give prompt information found in the image.

`tag_suggestions_file` should point to a JSON list that provides suggested tags for images for easy access in adding tags, if desired.

`file_path_json_path` should be set to the path for the file path JSON, if setting `use_file_path_json` is set to true.

`text_embedding_search_presets_exclusive` enables the search results returned by preset search texts to be exclusive of eachother to more accurately categorize. Note that since some text embeddings have a much stronger signal than others clustering on those searches can occur.

`store_checkpoints` will cache a group comparison process at certain checkpoints for later restart.
</details>

### Key and Mouse Bindings

While the UI elements support normal usage in most cases, there are many bindings that enable extended functionality, mostly to minimize UI content unrelated to image viewers.

Press Shift+H to open up a help window with all key bindings. A directory with images must be set before most of the bindings will have any effect. The group bindings are only functional in GROUP mode after a comparison has been run.

### Move Marks Window

This window helps with efficient filing of file marks.

<details>
<summary>Expand Details</summary>
<p>When the move marks window is open -- with or without GUI -- marks can be moved to a target directory by pressing the Enter key, or with the GUI elements if visible. After pressing the Enter key, a number of things can occur:</p>
<li>If no target directories have been set, a folder picker window will open to set a new directory.</li>
<li>If a marks action has been run previously, simply pressing Enter without a filter set will use the directory last used for the move or copy action.</li>
<li>If target directories have been set and a filter is set, the move or copy operation will use the first target directory in the filtered list.</li>
<li>If shift key is pressed along with Enter, the files will be copied instead of moved.</li>
<li>If control key is pressed, any previously marked directories will be ignored and a folder picker window will open to set a new target directory.</li>
<li>If alt key is pressed, the penultimate mark target dir will be used as target directory. This is useful when you want to successively copy files to one directory and then move them to another, without having to re-filter each time.</li>
<br>
<p>Simply typing letters while the mark window is open will filter the list of mark target directories, even if the GUI is not present. The backspace key will delete letters from the filter. You can scroll through the list of saved target directories using arrow keys.</p>
<p>To bypass the move marks window, use the Ctrl+R or Ctrl+E shortcuts to immediately run the previous and penultimate actions respectively on the current selection. You can also use number keys or Ctrl+T as hotkeys for persistent marks actions. To see the full list of file action hotkeys and their current settings open the hotkey actions window by pressing Ctrl+H on the marks window.</p>
<p>Ctrl+Z will undo the previous file marks move or copy action. If an earlier action needs to be reversed or modified, open the file actions window to verify the action in the history list and reverse it via the UI.</p>
</details>

### File Actions Window

The file actions window displays a certain number of completed actions, as defined in the config JSON. Similar to the move marks window, typing will add to a text filter that filters the actions by the target directory basenames.

On this window the previous file action media can be viewed and reversed or the action can be modified if desired.

## Limitations

**NOTE** - It is not currently possible to undo or modify a delete action, however unless the delete folder is explicitly set to null in the config it is likely the deleted items will be saved in a trash folder before being fully removed.

This is a simple app primarily meant for personal use but could be adapted for more intensive use cases.

The face similarity measure in particular is very crude and only compares the number of faces in each image, so it is off by default. At a future time more complex face comparison logic may be added, but for now the embedding comparison is helpful in matching faces.
