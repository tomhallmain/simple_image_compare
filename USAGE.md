# simple_image_compare - Usage

Clone this repository and ensure Python 3 and the required packages are installed from requirements.txt.

Run `python app.py` to start the Tkinter UI, or `python app_qt.py` to start the PySide6 (Qt) UI. Both versions share the same backend and configuration; the Qt version is under active development.

You can also run comparison from the command line. The compare logic lives in the `compare` package. From the project root:

```
python -m compare.compare_embeddings_clip --dir /path/to/media
python -m compare.compare_colors --dir /path/to/media
```

Supported command line options (embedding and color modules): `--dir`, `--counter`, `--faces`, `--include`, `--search`, `-o`/`--overwrite`, `--threshold`, `-v` (verbose), `-h`/`--help`. Embedding modules use `--threshold=float` (similarity, default 0.9); color uses `--threshold=int` (color diff) and `--use_thumb`. Multiple embedding modes exist (e.g. `compare_embeddings_clip`, `compare_embeddings_siglip`, `compare_embeddings_laion`); each shares the same CLI.

<details>
<summary>View Usage Details</summary>

Useful for detecting duplicates or finding associations between large unstructured sets of media files. File management controls are available after the analysis has completed.

Individual media files can be passed to search against the full data set by passing flag `--search` with the path of the search file, or setting a search file in the UI before running comparison.

The color matching compare mode is faster than embedding comparison but less robust. In the group comparison case, since every image must be compared to every other image the time complexity is $\mathcal{O}(n^2)$. To remedy this issue for large media sets, set the `store_checkpoints` config setting to enable process caching to close and pick up where you left off previously, but ensure no files are added or removed from the comparison directory before restarting a compare job.

When using embedding compare modes, you can search your image-based media files by text - both positive and negative. Commas will break the texts to search into multiple parts, to be combined in a final set of results. If there is a good embedding signal for the search texts it will likely return the media files you are looking for. It will take a while to load the first time as embeddings need to be generated. If a list of preset text searches is defined in your config JSON, you can cycle between them with the dedicated shortcut found below.

If a search image is set simultaneously with search text, its embedding will be factored into the search at a weight equal to a single search text part.
</details>

---

## Configuration

<details>
<summary>View Configuration Details</summary>

`locale` supports any of the following locales:

- en (English)
- de (Deutsh)
- fr (Français)
- es (Español)
- it (Italiano)
- pt (Português)
- ru (Русский)
- ja (日本語)
- ko (한국어)
- zh (中文)

`clip_model` defines the CLIP model to use for generating CLIP embeddings.

`image_types` defines the allowed file extensions for gathering image files, while `video_types` defines the allowed file extensions for gathering video files - there are only valid if the `enable_videos` setting is enabled.

`file_check_interval_seconds` defines the interval between auto-updates to identify recent file changes.

`slideshow_interval_seconds` defines the interval between slideshow transitions.

`sort_by` defines the default media browsing sort setting upon starting the application.

`trash_folder` defines the target folder for media deletion. If not set, deletion will send the file to your system's default trash folder.

`enable_prevalidations` enables the prevalidation system. When enabled, prevalidation rules will be applied to media before they are shown.

`image_classifier_models` defines a list of image classifier models (H5 or PyTorch) that can be used for prevalidation rules. Each model should specify:

- `model_name`: A unique name for the model
- `model_location`: Path to the model file (.h5 for TensorFlow/Keras, or .pth/.pt/.safetensors/.bin for PyTorch)
- `model_categories`: List of categories the model can classify
- `backend`: "auto" (detected from file extension), "hdf5"/"tensorflow" for H5 models, or "pytorch" for PyTorch models
- `use_hub_keras_layers`: Whether to use Keras hub layers (H5 models only)
- Additional PyTorch-specific parameters: `architecture_module_name`, `weights_only`, `device`, `input_shape`, etc.

**Note:** For `.safetensors` models, you must provide the model architecture configuration. See `config_example.json` for the required format. Only the `architecture_module_name` is required if the model architecture file is located in the same directory as the model.

If the `sd_prompt_reader_loc` config setting is pointing to your local copy of [stable-diffusion-prompt-reader](https://github.com/receyuki/stable-diffusion-prompt-reader) then opening image details for an image with a stable diffusion prompt will give prompt information found in the image.

`tag_suggestions_file` should point to a JSON list that provides suggested tags for images for easy access in adding tags, if desired.

`file_path_json_path` should be set to the path for the file path JSON, if setting `use_file_path_json` is set to true.

`text_embedding_search_presets_exclusive` enables the search results returned by preset search texts to be exclusive of eachother to more accurately categorize. Note that since some text embeddings have a much stronger signal than others clustering on those searches can occur.

`store_checkpoints` will cache a group comparison process at certain checkpoints for later restart.
</details>

---

## Key and Mouse Bindings

While the UI elements support normal usage in most cases, there are many bindings that enable extended functionality, mostly to minimize UI content unrelated to image viewers.

Press Shift+H to open up a help window with all key bindings. A directory with media files must be set before most of the bindings will have any effect. The group bindings are only functional in GROUP mode after a comparison has been run.

---

## Move Marks Window

This window helps with efficient filing of file marks.

<details>
<summary>View File Marks Details</summary>
<p>When the move marks window is open -- with or without GUI -- marks can be moved to a target directory by pressing the Enter key, or with the GUI elements if visible. After pressing the Enter key, a number of things can occur:</p>

<ul>
<li>If no target directories have been set, a folder picker window will open to set a new directory.</li>
<li>If a marks action has been run previously, simply pressing Enter without a filter set will use the directory last used for the move or copy action.</li>
<li>If target directories have been set and a filter is set, the move or copy operation will use the first target directory in the filtered list.</li>
<li>If shift key is pressed along with Enter, the files will be copied instead of moved.</li>
<li>If control key is pressed, any previously marked directories will be ignored and a folder picker window will open to set a new target directory.</li>
<li>If alt key is pressed, the penultimate mark target dir will be used as target directory. This is useful when you want to successively copy files to one directory and then move them to another, without having to re-filter each time.</li>
</ul>
<p>Simply typing letters while the mark window is open will filter the list of mark target directories, even if the GUI is not present. The backspace key will delete letters from the filter. You can scroll through the list of saved target directories using arrow keys.</p>
<p>To bypass the move marks window, use the Ctrl+R or Ctrl+E shortcuts to immediately run the previous and penultimate actions respectively on the current selection. You can also use number keys or Ctrl+T as hotkeys for persistent marks actions. To see the full list of file action hotkeys and their current settings open the hotkey actions window by pressing Ctrl+H on the marks window.</p>
<p>Ctrl+Z will undo the previous file marks move or copy action. If an earlier action needs to be reversed or modified, open the file actions window to verify the action in the history list and reverse it via the UI.</p>
</details>

---

## File Actions Window

The file actions window displays a certain number of completed actions, as defined in the config JSON. Similar to the move marks window, typing will add to a text filter that filters the actions by the target directory basenames.

On this window the previous file action media can be viewed and reversed or the action can be modified if desired.