# Simple Image Compare Tool

Simple visual media comparison tool that detects color and face similarities using embeddings (default) and color matching (separate optional mode). The tool supports multiple embedding models:

<details>
<summary>View Embedding Models</summary>
- CLIP (default): 512D embeddings, high zero-shot performance
- SigLIP: 768D or 1024D embeddings, excellent retrieval performance
- ALIGN: 640D embeddings, high accuracy for retrieval
- FLAVA: 768D embeddings, good for complex reasoning
- X-VLM: 256D embeddings, efficient for region-text tasks - requires local copy of [X-VLM](https://github.com/zengyan-97/X-VLM)
- LAION: 1024D embeddings, high-quality visual-language understanding - based on CLIP ViT-H/14 architecture

Each model offers different tradeoffs between accuracy, speed, and resource usage. The default CLIP model provides a good balance for most use cases.
</details>

---

## Usage

Clone this repository and ensure Python 3 and the required packages are installed from requirements.txt. Optionally, run `pip install -r requirements-optional.txt` for platform-specific extras (e.g. keychain integration, EXIF tools). Note: some dependencies in requirements.txt (e.g. **torch**) may need to be installed from the provider’s site (e.g. [pytorch.org](https://pytorch.org)) for GPU support specific to your system.

Run `app.py` to start the Tkinter UI, or `app_qt.py` for the PySide6 (Qt) UI. Both share the same backend and configuration. For more details, see [USAGE.md](https://www.github.com/tomhallmain/simple_image_compare/blob/master/USAGE.md).

---

## Image and Video Browser

The UI can be used as a media file browser. The following features are available that your OS default photo viewer application may not have:
<details>
<summary>View Features</summary>
<ul>
    <li>Auto-resize images to fill the screen</li>
    <li>Auto-refresh directory files</li>
    <li>Slideshow (customizable)</li>
    <li>Optionally play and compare video files and other media - typically will use the first image found for the comparison.</li>
    <li>Quicker and smoother transitions between media files</li>
    <li>Faster load time for directories with many media files in some cases</li>
    <li>Faster load times when switching between sort types</li>
    <li>Go to file by string search or by index (1-based)</li>
    <li>Mark groups of files to enable quick transitions and comparisons</li>
    <li>Mark favorite media and access them quickly via the Favorites window</li>
    <li>Move, copy, and delete marked file groups without overwriting system clipboard</li>
    <li>Revert and modify historical file action changes</li>
    <li>Quickly find directories via recent directory picker window</li>
    <li>Stores session info about seen directories (useful for directories with many media files)</li>
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

---

### Favorites Window

You can mark any media file (image, video, etc.) as a favorite and access all favorites quickly using the Favorites window (Ctrl+F). This is especially useful when working with directories containing many files, as it allows you to keep persistent preferred items easily accessible for future searches and actions.

### Directory Notes

The Directory Notes feature allows you to maintain persistent notes and marked files for individual directories. You can add notes to specific files, mark files for later reference, and export or import your notes and marked files as text or JSON files. This is separate from the runtime marked files used for moving files, making it useful for long-term organization and documentation of your media collections.

---

## Prevalidation Rules and Classifier Actions

The tool includes a flexible prevalidation system that can automatically process media before they're shown to the user, as well as classifier actions that can be run ad-hoc on selected directories. Both are managed through a unified window. This is useful for:

<details>
<summary>View Use Cases</summary>
<ul>
<li>Automatically skipping, hiding, or deleting unwanted media</li>
<li>Moving or copying media to specific directories based on content</li>
<li>Filtering media using CLIP embeddings, embedding prototypes, H5 image classifiers, PyTorch image classifiers, prompt string detection</li>
<li>Setting up rules that apply to specific directories</li>
<li>Running one-off classification actions on selected directories</li>
</ul>
</details>

Prevalidation rules and classifier actions can be configured with:

<details>
<summary>View Rule Options</summary>
<ul>
<li>Multiple validation types enabled simultaneously (OR logic - any type can trigger the action)</li>
<li>Positive and negative text prompts shared across embedding and prompt validation</li>
<li><strong>Embedding prototypes</strong>: Create prototype embeddings from directories of sample images, then compare images against these prototypes. Supports both positive and negative prototypes with configurable weighting (lambda) for fine-tuning similarity matching</li>
<li>Custom thresholds for embedding-based matching</li>
<li>Different actions (skip, hide, notify, move, copy, delete, add mark)</li>
<li>Directory-specific rules</li>
<li>H5 model-based classification rules</li>
<li>PyTorch model-based classification rules (supports .pth, .pt, .safetensors, and .bin formats)</li>
</ul>
</details>

---

Prevalidations automatically run on media as you browse, while classifier actions can be executed manually on selected media directories when needed. These features are particularly useful for maintaining clean media collections and automating local content filtering, but can be disabled at any time if desired. The classifier action management window allows copying between types of classifier action to reduce the burden of action configuration.

You can find example classifier models that are known to work here:
- [Coherence Detection](https://huggingface.co/reddesert/coherence_detection) - A PyTorch ResNet-34 model for classifying AI-generated images into coherent, incoherent, or semi-incoherent categories
- [NSFW Model](https://github.com/FurkanGozukara/nsfw_model) - An H5 classifier model for filtering out some types of NSFW content

---

## Limitations

**NOTE** - It is not currently possible to undo or modify a delete action, however unless the delete folder is explicitly set to null in the config it is likely the deleted items will be saved in a trash folder before being fully removed.

This is a simple app primarily meant for personal use but could be adapted for more intensive use cases.

The face similarity measure in particular is very crude and only compares the number of faces in each image, so it is off by default. At a future time more complex face comparison logic may be added, but for now the embedding comparison is helpful in matching faces.
