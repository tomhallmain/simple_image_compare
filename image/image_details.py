from datetime import datetime
import glob
import os
import re

from PIL import Image
from tkinter import Frame, Label, OptionMenu, StringVar, LEFT, W
from tkinter.font import Font
from tkinter.ttk import Entry, Button

from files.file_browser import FileBrowser
from image.frame_cache import FrameCache
from image.image_data_extractor import image_data_extractor
from image.image_ops import ImageOps
from image.metadata_viewer_window import MetadataViewerWindow
from image.smart_crop import Cropper
from image.temp_image_canvas import TempImageCanvas
from lib.multi_display import SmartToplevel
from utils.app_info_cache import app_info_cache
from utils.app_style import AppStyle
from utils.config import config
from utils.constants import ImageGenerationType
from utils.logging_setup import get_logger
from utils.translations import I18N
from utils.utils import Utils, ModifierKey

_ = I18N._

logger = get_logger("image_details")

# TODO: fix image generation mode selection widget
# TODO: rename file


def get_readable_file_size(path):
    size = os.path.getsize(path)
    if size < 1024:
        return str(size) + " bytes"
    elif size < 1024*1024:
        return str(round(size/1024, 1)) + " KB"
    else:
        return str(round(size/(1024*1024), 1)) + " MB"


class ImageDetails():
    temp_media_canvas = None
    related_image_saved_node_id = "LoadImage"
    downstream_related_image_index = 0
    downstream_related_images_cache = {}
    downstream_related_image_browser = FileBrowser()
    image_generation_mode = ImageGenerationType.CONTROL_NET
    previous_image_generation_image = None
    metatdata_viewer_window = None

    @staticmethod
    def load_image_generation_mode():
        try:
            ImageDetails.image_generation_mode = ImageGenerationType.get(app_info_cache.get_meta("image_generation_mode", default_val="CONTROL_NET"))
        except Exception as e:
            logger.error(f"Error loading image generation mode: {e}")

    @staticmethod
    def store_image_generation_mode():
        app_info_cache.set_meta("image_generation_mode", ImageDetails.image_generation_mode.name)

    def __init__(self, parent_master, media_path, index_text, app_actions, do_refresh=True):
        self.parent_master = parent_master
        self.master = SmartToplevel(persistent_parent=parent_master)
        self.master.title(_("Image details"))
        
        # Set the size while preserving the position set by SmartToplevel
        self.master.set_geometry_preserving_position("700x600")
        self.image_path = FrameCache.get_image_path(media_path)
        self.app_actions = app_actions
        self.frame = Frame(self.master)
        self.frame.grid(column=0, row=0)
        self.frame.columnconfigure(0, weight=1)
        self.frame.columnconfigure(0, weight=9)
        self.frame.config(bg=AppStyle.BG_COLOR)
        self.do_refresh = do_refresh
        self.has_closed = False
        col_0_width = 100
        self.row_count0 = 0
        self.row_count1 = 0

        self._label_path = Label(self.frame)
        self.label_path = Label(self.frame)
        self._label_index = Label(self.frame)
        self.label_index = Label(self.frame)
        self._label_mode = Label(self.frame)
        self.label_mode = Label(self.frame)
        self._label_dims = Label(self.frame)
        self.label_dims = Label(self.frame)
        self._label_size = Label(self.frame)
        self.label_size = Label(self.frame)
        self._label_mtime = Label(self.frame)
        self.label_mtime = Label(self.frame)
        self._label_positive = Label(self.frame)
        self.label_positive = Label(self.frame)
        self._label_negative = Label(self.frame)
        self.label_negative = Label(self.frame)
        self._label_models = Label(self.frame)
        self.label_models = Label(self.frame)
        self._label_loras = Label(self.frame)
        self.label_loras = Label(self.frame)
        self._label_tags = Label(self.frame)

        if any([self.image_path.lower().endswith(ext) for ext in config.video_types]):
            self.is_image = False
            image_mode = ""
            image_dims = ""
            positive = ""
            negative = ""
            models = ""
            loras = ""
            related_image_text = ""
        else:
            self.is_image = True
            image_mode, image_dims = self._get_image_info()
            positive, negative, models, loras = image_data_extractor.get_image_prompts_and_models(self.image_path)
            related_image_text = self.get_related_image_text()

        mod_time, file_size = self._get_file_info()

        self.add_label(self._label_path, _("Image Path"), wraplength=col_0_width)
        self.add_label(self.label_path, self.image_path, column=1)
        self.add_label(self._label_index, _("File Index"), wraplength=col_0_width)
        self.add_label(self.label_index, index_text, column=1)
        self.add_label(self._label_mode, _("Color Mode"), wraplength=col_0_width)
        self.add_label(self.label_mode, image_mode, column=1)
        self.add_label(self._label_dims, _("Dimensions"), wraplength=col_0_width)
        self.add_label(self.label_dims, image_dims, column=1)
        self.add_label(self._label_size, _("Size"), wraplength=col_0_width)
        self.add_label(self.label_size, file_size, column=1)
        self.add_label(self._label_mtime, _("Modification Time"), wraplength=col_0_width)
        self.add_label(self.label_mtime, mod_time, column=1)
        self.add_label(self._label_positive, _("Positive"), wraplength=col_0_width)
        self.add_label(self.label_positive, positive, column=1)
        self.add_label(self._label_negative, _("Negative"), wraplength=col_0_width)
        self.add_label(self.label_negative, negative if config.show_negative_prompt and negative != "" else _("(negative prompt not shown by config setting)"), column=1)
        self.add_label(self._label_models, _("Models"), wraplength=col_0_width)
        self.add_label(self.label_models, ", ".join(models), column=1)
        self.add_label(self._label_loras, _("LoRAs"), wraplength=col_0_width)
        self.add_label(self.label_loras, ", ".join(loras), column=1)

        self.copy_prompt_btn = None
        self.copy_prompt_no_break_btn = None
        self.add_button("copy_prompt_btn", _("Copy Prompt"), self.copy_prompt, column=0)
        self.add_button("copy_prompt_no_break_btn", _("Copy Prompt No BREAK"), self.copy_prompt_no_break, column=1)

        self.rotate_left_btn = None
        self.rotate_right_btn = None
        self.add_button("rotate_left_btn", _("Rotate Image Left"), lambda: self.rotate_image(right=False), column=0)
        self.add_button("rotate_right_btn", _("Rotate Image Right"), lambda: self.rotate_image(right=True), column=1)

        self.crop_image_btn = None
        self.enhance_image_btn = None
        self.add_button("crop_image_btn", _("Crop Image (Smart Detect)"), lambda: self.crop_image(), column=0)
        self.add_button("enhance_image_btn", _("Enhance Image"), lambda: self.enhance_image(), column=1)

        self.random_crop_btn = None
        self.randomly_modify_btn = None
        self.add_button("random_crop_btn", _("Random Crop"), lambda: self.random_crop(), column=0)
        self.add_button("randomly_modify_btn", _("Randomly Modify"), lambda: self.random_modification(), column=1)
        
        self.flip_image_btn = None
        self.flip_vertical_btn = None
        self.add_button("flip_image_btn",  _("Flip Image Horizontally"), lambda: self.flip_image(), column=0)
        self.add_button("flip_vertical_btn", _("Flip Image Vertically"), lambda: self.flip_image(top_bottom=True), column=1)

        self.copy_without_exif_btn = None
        self.add_button("copy_without_exif_btn", _("Copy Without EXIF"), lambda: self.copy_without_exif(), column=0)
        self.convert_to_jpg_btn = None
        self.add_button("convert_to_jpg_btn", _("Convert to JPG"), lambda: self.convert_to_jpg(), column=1)

        self.metadata_btn = None
        self.add_button("metadata_btn",  _("Show Metadata"), lambda: self.show_metadata(), column=0)
        self.row_count1 += 1

        self.open_related_image_btn = None
        self.add_button("open_related_image_btn", _("Open Related Image"), self.open_related_image)
        # self.related_image_node_id = StringVar(self.master, value=ImageDetails.related_image_saved_node_id)
        # self.related_image_node_id_entry = Entry(self.frame, textvariable=self.related_image_node_id, width=30, font=Font(size=8))
        # self.related_image_node_id_entry.bind("<Return>", self.open_related_image)
        # self.related_image_node_id_entry.grid(row=self.row_count1, column=1, sticky="w")
        self.label_related_image = Label(self.frame)
        self.add_label(self.label_related_image, related_image_text, column=1)

        self.label_image_generation = Label(self.frame)
        self.add_label(self.label_image_generation, _("Image Generation"))
        self.image_generation_mode_var = StringVar()
        self.image_generation_mode_choice = OptionMenu(self.frame, self.image_generation_mode_var, ImageDetails.image_generation_mode.name,
                                                       *ImageGenerationType.members(), command=self.set_image_generation_mode)
        self.image_generation_mode_choice.grid(row=self.row_count1, column=1, sticky="W")
        self.row_count1 += 1

        self.run_image_generation_button = None
        self.add_button("run_image_generation_button", _("Run Image Generation"), self.run_image_generation, column=0)
        self.label_help = Label(self.frame)
        self.add_label(self.label_help, _("Press Shift+I on a main app window to run this"), column=1)

        self.run_redo_prompt_button = None
        self.add_button("run_redo_prompt_button", _("Redo Prompt"), self.run_redo_prompt, column=0)
        self.row_count1 += 1

        if config.image_tagging_enabled and self.is_image:
            self.add_label(self._label_tags, _("Tags"), wraplength=col_0_width)

            self.tags = image_data_extractor.extract_tags(self.image_path)
            tags_str = ", ".join(self.tags) if self.tags else ""
            self.tags_str = StringVar(self.master, value=tags_str)
            self.tags_entry = Entry(self.frame, textvariable=self.tags_str, width=30, font=Font(size=8))
            self.tags_entry.grid(row=self.row_count1, column=1)
            self.row_count1 += 1

            self.update_tags_btn = None
            self.add_button("update_tags_btn", _("Update Tags"), self.update_tags)
            self.row_count1 += 1

        self.master.bind("<Escape>", self.close_windows)
        self.master.bind("<Shift-C>", self.crop_image)  # Crop Image
        self.master.bind("<Shift-L>", lambda e: self.rotate_image(right=False))  # Rotate Left
        self.master.bind("<Shift-R>", lambda e: self.rotate_image(right=True))   # Rotate Right
        self.master.bind("<Shift-E>", lambda e: self.enhance_image())            # Enhance Image
        self.master.bind("<Shift-A>", lambda e: self.random_crop())              # rAndom Crop
        self.master.bind("<Shift-Q>", lambda e: self.random_modification())      # Randomly Modify
        self.master.bind("<Shift-H>", lambda e: self.flip_image())               # Flip Horizontal
        self.master.bind("<Shift-V>", lambda e: self.flip_image(top_bottom=True))# Flip Vertical
        self.master.bind("<Shift-X>", lambda e: self.copy_without_exif())        # Copy w/o EXIF
        self.master.bind("<Shift-J>", lambda e: self.convert_to_jpg())           # Convert to JPG
        self.master.bind("<Shift-K>", lambda e: self.convert_to_jpg())           # Convert to JPG
        self.master.bind("<Shift-D>", self.show_metadata)                        # Show Metadata (metaData)
        self.master.bind("<Shift-R>", self.open_related_image)                   # Open Related Image
        self.master.bind("<Shift-I>", self.run_image_generation)                 # Run image Generation
        self.master.bind("<Shift-Y>", self.run_redo_prompt)                      # Redo prompt (like redo)
        # Ctrl+key combinations mark the file and open marks window without GUI
        self.master.bind("<Control-c>", lambda e: self._crop_image_and_mark())                # Crop Image and Mark
        self.master.bind("<Control-l>", lambda e: self._rotate_image_and_mark(right=False))  # Rotate Left and Mark
        self.master.bind("<Control-r>", lambda e: self._rotate_image_and_mark(right=True))   # Rotate Right and Mark
        self.master.bind("<Control-e>", lambda e: self._enhance_image_and_mark())            # Enhance Image and Mark
        self.master.bind("<Control-a>", lambda e: self._random_crop_and_mark())              # Random Crop and Mark
        self.master.bind("<Control-q>", lambda e: self._random_modification_and_mark())      # Randomly Modify and Mark
        self.master.bind("<Control-h>", lambda e: self._flip_image_and_mark())               # Flip Horizontal and Mark
        self.master.bind("<Control-v>", lambda e: self._flip_image_and_mark(top_bottom=True))# Flip Vertical and Mark
        self.master.bind("<Control-x>", lambda e: self._copy_without_exif_and_mark())        # Copy w/o EXIF and Mark
        self.master.bind("<Control-j>", lambda e: self._convert_to_jpg_and_mark())           # Convert to JPG and Mark
        self.master.bind("<Control-k>", lambda e: self._convert_to_jpg_and_mark())           # Convert to JPG and Mark
        self.master.protocol("WM_DELETE_WINDOW", self.close_windows)
        self.focus()

    def focus(self):
        self.frame.after(1, lambda: self.frame.focus_force())

    def _get_image_info(self):
        image = Image.open(self.image_path)
        image_mode = str(image.mode)
        image_dims = f"{image.size[0]}x{image.size[1]}"
        image.close()
        return image_mode, image_dims
    
    def _get_file_info(self):
        mod_time = datetime.fromtimestamp(os.path.getmtime(self.image_path)).strftime("%Y-%m-%d %H:%M")
        file_size = get_readable_file_size(self.image_path)
        return mod_time, file_size

    def update_image_details(self, image_path, index_text):
        self.image_path = image_path
        self.is_image = not any([self.image_path.lower().endswith(ext) for ext in config.video_types])
        if self.is_image:
            image_mode, image_dims = self._get_image_info()
            positive, negative, models, loras = image_data_extractor.get_image_prompts_and_models(self.image_path)
            related_image_text = self.get_related_image_text()
        else:
            image_mode = ""
            image_dims = ""
            positive = ""
            negative = ""
            models = ""
            loras = ""
            related_image_text = ""

        mod_time, file_size = self._get_file_info()
        self.label_path["text"] = image_path
        self.label_index["text"] = index_text
        self.label_mode["text"] = image_mode
        self.label_dims["text"] = image_dims
        self.label_mtime["text"] = mod_time
        self.label_size["text"] = file_size
        self.label_positive["text"] = positive
        if config.show_negative_prompt:
            self.label_negative["text"] = negative
        self.label_models["text"] = ", ".join(models)
        self.label_loras["text"] = ", ".join(loras)
        self.label_related_image["text"] = related_image_text
        if ImageDetails.metatdata_viewer_window is not None:
            if ImageDetails.metatdata_viewer_window.has_closed:
                ImageDetails.metatdata_viewer_window = None
            else:
                self.show_metadata()
        self.master.update()

    def copy_prompt(self):
        positive = self.label_positive["text"]
        self.master.clipboard_clear()
        self.master.clipboard_append(positive)
        self.app_actions.toast(_("Copied prompt"))

    def copy_prompt_no_break(self):
        positive = self.label_positive["text"]
        if "BREAK" in positive:
            positive = positive[positive.index("BREAK")+6:]
        positive = ImageDetails.remove_emphases(positive)
        self.master.clipboard_clear()
        self.master.clipboard_append(positive)
        self.app_actions.toast(_("Copied prompt without BREAK"))

    @staticmethod
    def copy_prompt_no_break_static(image_path, master, app_actions):
        positive, negative, models, loras = image_data_extractor.get_image_prompts_and_models(image_path)
        if "BREAK" in positive:
            positive  = positive[positive.index("BREAK")+6:]
        positive = ImageDetails.remove_emphases(positive)
        master.clipboard_clear()
        master.clipboard_append(positive)
        app_actions.toast(_("Copied prompt without BREAK"))

    @staticmethod
    def remove_emphases(prompt):
        prompt = prompt.replace("(", "").replace(")", "")
        prompt = prompt.replace("[", "").replace("]", "")
        if ":" in prompt:
            prompt = re.sub(r":[0-9]*\.[0-9]+", "", prompt)
        if "<" in prompt:
            prompt = re.sub(r"<[^>]*>", "", prompt)
        return prompt

    def rotate_image(self, right=False):
        new_filepath = ImageOps.rotate_image(self.image_path, right)
        self.close_windows()
        self.app_actions.refresh()
        rotation_text = _("Rotated image right") if right else _("Rotated image left")
        self.app_actions.toast(rotation_text)
        if os.path.exists(new_filepath):
            ImageDetails.open_temp_image_canvas(master=self.parent_master, image_path=new_filepath, app_actions=self.app_actions)

    def crop_image(self, event=None):
        saved_files = Cropper.smart_crop_multi_detect(self.image_path, "")
        if len(saved_files) > 0:
            self.close_windows()
            self.app_actions.refresh()
            # TODO actually go to the new file. In this case we don't want to replace the original because there may be errors in some cases.
            self.app_actions.toast(_("Cropped image"))
            if len(saved_files) > 0:
                ImageDetails.open_temp_image_canvas(master=self.parent_master, image_path=saved_files[0], app_actions=self.app_actions)
        else:
            self.app_actions.toast(_("No crops found"))

    def enhance_image(self):
        new_filepath = ImageOps.enhance_image(self.image_path)
        self.close_windows()
        self.app_actions.refresh()
        # TODO actually go to the new file. In this case we don't want to replace the original because there may be errors in some cases.
        self.app_actions.toast(_("Enhanced image"))
        if os.path.exists(new_filepath):
            ImageDetails.open_temp_image_canvas(master=self.parent_master, image_path=new_filepath, app_actions=self.app_actions)

    def random_crop(self):
        new_filepath = ImageOps.random_crop_and_upscale(self.image_path)
        self.close_windows()
        self.app_actions.refresh()
        self.app_actions.toast(_("Randomly cropped image"))
        if os.path.exists(new_filepath):
            ImageDetails.open_temp_image_canvas(master=self.parent_master, image_path=new_filepath, app_actions=self.app_actions)

    def random_modification(self):
        ImageDetails.randomly_modify_image(self.image_path, self.app_actions, self.parent_master)

    @staticmethod
    def randomly_modify_image(image_path, app_actions, master=None):
        new_filepath = ImageOps.randomly_modify_image(image_path)
        app_actions.refresh()
        if os.path.exists(new_filepath):
            app_actions.toast(_("Randomly modified image"))
            # Open the newly created image in temp canvas if master is provided
            if master is not None:
                ImageDetails.open_temp_image_canvas(master=master, image_path=new_filepath, app_actions=app_actions)
        else:
            app_actions.toast(_("No new image created"))

    def flip_image(self, top_bottom=False):
        # Add confirmation dialog for vertical flip (top_bottom=True) as it's uncommon
        if top_bottom:
            result = self.app_actions.alert(
                _("Confirm Vertical Flip"), 
                _("Are you sure you want to flip this image vertically? This is an uncommon operation and may have been clicked by accident."),
                kind="askokcancel",
                master=self.master
            )
            if not result:
                return  # User cancelled the operation
        
        new_filepath = ImageOps.flip_image(self.image_path, top_bottom=top_bottom)
        self.close_windows()
        self.app_actions.refresh()
        self.app_actions.toast(_("Flipped image"))
        if os.path.exists(new_filepath):
            ImageDetails.open_temp_image_canvas(master=self.parent_master, image_path=new_filepath, app_actions=self.app_actions)

    def copy_without_exif(self):
        try:
            new_filepath = image_data_extractor.copy_without_exif(self.image_path)
            self.app_actions.refresh()
            self.app_actions.toast(_("Copied image without EXIF data"))
            if os.path.exists(new_filepath):
                ImageDetails.open_temp_image_canvas(master=self.parent_master, image_path=new_filepath, app_actions=self.app_actions)
        except Exception as e:
            logger.error(f"Error copying image without EXIF: {e}")
            self.app_actions.toast(_("Error copying image without EXIF"))

    def convert_to_jpg(self):
        try:
            new_filepath = ImageOps.convert_to_jpg(self.image_path)
            self.close_windows()
            self.app_actions.refresh()
            self.app_actions.toast(_("Converted image to JPG"))
            if os.path.exists(new_filepath):
                ImageDetails.open_temp_image_canvas(master=self.parent_master, image_path=new_filepath, app_actions=self.app_actions)
        except Exception as e:
            logger.error(f"Error converting image to JPG: {e}")
            self.app_actions.toast(_("Error converting image to JPG"))

    def _rotate_image_and_mark(self, right=False):
        """Rotate image and mark it, opening the marks window without GUI."""
        new_filepath = ImageOps.rotate_image(self.image_path, right)
        self.close_windows()
        self.app_actions.refresh()
        rotation_text = _("Rotated image right") if right else _("Rotated image left")
        self.app_actions.toast(rotation_text)
        if os.path.exists(new_filepath):
            self.app_actions.open_move_marks_window(filepath=new_filepath, open_gui=False)

    def _crop_image_and_mark(self, event=None):
        """Crop image and mark it, opening the marks window without GUI."""
        saved_files = Cropper.smart_crop_multi_detect(self.image_path, "")
        if len(saved_files) > 0:
            self.close_windows()
            self.app_actions.refresh()
            self.app_actions.toast(_("Cropped image"))
            if len(saved_files) > 0:
                self.app_actions.open_move_marks_window(filepath=saved_files[0], open_gui=False)
        else:
            self.app_actions.toast(_("No crops found"))

    def _enhance_image_and_mark(self):
        """Enhance image and mark it, opening the marks window without GUI."""
        new_filepath = ImageOps.enhance_image(self.image_path)
        self.close_windows()
        self.app_actions.refresh()
        self.app_actions.toast(_("Enhanced image"))
        if os.path.exists(new_filepath):
            self.app_actions.open_move_marks_window(filepath=new_filepath, open_gui=False)

    def _random_crop_and_mark(self):
        """Random crop image and mark it, opening the marks window without GUI."""
        new_filepath = ImageOps.random_crop_and_upscale(self.image_path)
        self.close_windows()
        self.app_actions.refresh()
        self.app_actions.toast(_("Randomly cropped image"))
        if os.path.exists(new_filepath):
            self.app_actions.open_move_marks_window(filepath=new_filepath, open_gui=False)

    def _random_modification_and_mark(self):
        """Randomly modify image and mark it, opening the marks window without GUI."""
        new_filepath = ImageOps.randomly_modify_image(self.image_path)
        self.close_windows()
        self.app_actions.refresh()
        if os.path.exists(new_filepath):
            self.app_actions.toast(_("Randomly modified image"))
            self.app_actions.open_move_marks_window(filepath=new_filepath, open_gui=False)
        else:
            self.app_actions.toast(_("No new image created"))

    def _flip_image_and_mark(self, top_bottom=False):
        """Flip image and mark it, opening the marks window without GUI."""
        new_filepath = ImageOps.flip_image(self.image_path, top_bottom=top_bottom)
        self.close_windows()
        self.app_actions.refresh()
        self.app_actions.toast(_("Flipped image"))
        if os.path.exists(new_filepath):
            self.app_actions.open_move_marks_window(filepath=new_filepath, open_gui=False)

    def _copy_without_exif_and_mark(self):
        """Copy image without EXIF and mark it, opening the marks window without GUI."""
        try:
            new_filepath = image_data_extractor.copy_without_exif(self.image_path)
            self.app_actions.refresh()
            self.app_actions.toast(_("Copied image without EXIF data"))
            if os.path.exists(new_filepath):
                self.app_actions.open_move_marks_window(filepath=new_filepath, open_gui=False)
        except Exception as e:
            logger.error(f"Error copying image without EXIF: {e}")
            self.app_actions.toast(_("Error copying image without EXIF"))

    def _convert_to_jpg_and_mark(self):
        """Convert image to JPG and mark it, opening the marks window without GUI."""
        try:
            new_filepath = ImageOps.convert_to_jpg(self.image_path)
            self.close_windows()
            self.app_actions.refresh()
            self.app_actions.toast(_("Converted image to JPG"))
            if os.path.exists(new_filepath):
                self.app_actions.open_move_marks_window(filepath=new_filepath, open_gui=False)
        except Exception as e:
            logger.error(f"Error converting image to JPG: {e}")
            self.app_actions.toast(_("Error converting image to JPG"))

    def show_metadata(self, event=None):
        metadata_text = image_data_extractor.get_raw_metadata_text(self.image_path)
        if metadata_text is None:
            self.app_actions.toast(_("No metadata found"))
        else:
            self._show_metadata_window(metadata_text)

    def _show_metadata_window(self, metadata_text):
        if ImageDetails.metatdata_viewer_window is None or ImageDetails.metatdata_viewer_window.has_closed:
            ImageDetails.metatdata_viewer_window = MetadataViewerWindow(self.master, self.app_actions, metadata_text, self.image_path)
        else:
            ImageDetails.metatdata_viewer_window.update_metadata(metadata_text, self.image_path)

    def get_related_image_text(self):
        node_id = ImageDetails.related_image_saved_node_id
        related_image_path, exact_match = ImageDetails.get_related_image_path(self.image_path, node_id, check_extra_directories=False)
        if related_image_path is not None:
            related_image_text = related_image_path if exact_match else (related_image_path + _(" (Exact Match Not Found)"))
        else:
            related_image_text = _("(No related image found)")
        return related_image_text

    def open_related_image(self, event=None):
        # TODO either remove the node id specification field or add it back somewhere else
        # node_id = self.related_image_node_id.get().strip()
        # if node_id == "":
        #     raise Exception("No node id given")
        # else:
        #     ImageDetails.related_image_saved_node_id = node_id
        ImageDetails.show_related_image(self.parent_master, None, self.image_path, self.app_actions)

    @staticmethod
    def get_related_image_path(image_path, node_id=None, check_extra_directories=True):
        if node_id is None or node_id == "":
            node_id = ImageDetails.related_image_saved_node_id
        related_image_path = image_data_extractor.get_related_image_path(image_path, node_id)
        if related_image_path is None or related_image_path == "":
            # logger.info(f"{image_path} - No related image found for node id {node_id}")
            return None, False
        elif check_extra_directories is None:
            return related_image_path, False
        elif not os.path.isfile(related_image_path):
            if not check_extra_directories:
                return related_image_path, False
            logger.info(f"{image_path} - Related image {related_image_path} not found")
            if len(config.directories_to_search_for_related_images) > 0:
                basename = os.path.basename(related_image_path)
                related_image_path_found = False
                for directory in config.directories_to_search_for_related_images:
                    dir_filepaths = glob.glob(os.path.join(directory, "**/*"), recursive=True)
                    for file_path in dir_filepaths:
                        if file_path == image_path:
                            continue
                        if file_path.endswith(basename):
                            file_basename = os.path.basename(file_path)
                            if basename == file_basename:
                                related_image_path = file_path
                                related_image_path_found = True
                                break
                    if related_image_path_found:
                        break
            if not related_image_path_found or not os.path.isfile(related_image_path):
                return related_image_path, False
            logger.info(f"{image_path} - Possibly related image {related_image_path} found")
        return related_image_path, True

    @staticmethod
    def show_related_image(master=None, node_id=None, image_path="", app_actions=None):
        if master is None or image_path == "":
            raise Exception("No master or image path given")
        related_image_path, exact_match = ImageDetails.get_related_image_path(image_path, node_id)
        if related_image_path is None or related_image_path == "":
            app_actions.toast(_("(No related image found)"))
            return
        elif not exact_match:
            app_actions.toast(_(" (Exact Match Not Found)"))
            return
        ImageDetails.open_temp_image_canvas(master=master, image_path=related_image_path, app_actions=app_actions)

    @staticmethod
    def open_temp_image_canvas(master=None, image_path=None, app_actions=None, skip_get_window_check=False):
        if image_path is None:
            return
        base_dir = os.path.dirname(image_path)
        if not skip_get_window_check:
            if app_actions.get_window(base_dir=base_dir, img_path=image_path, refocus=True,
                                      disallow_if_compare_state=True, new_image=True) is not None:
                return
        if ImageDetails.temp_media_canvas is None:
            ImageDetails.set_temp_media_canvas(master, image_path, app_actions)
        try:
            ImageDetails.temp_media_canvas.create_image(image_path)
        except Exception as e:
            if "invalid command name" in str(e):
                ImageDetails.set_temp_media_canvas(master, image_path, app_actions)
                ImageDetails.temp_media_canvas.create_image(image_path)
            else:
                raise e

    @staticmethod
    def set_temp_media_canvas(master, media_path, app_actions):
        with Image.open(media_path) as image:
            width = min(700, image.size[0])
            height = int(image.size[1] * width / image.size[0])
        ImageDetails.temp_media_canvas = TempImageCanvas(master, title=media_path,
                dimensions=f"{width}x{height}", app_actions=app_actions)

    @staticmethod
    def refresh_downstream_related_image_cache(key, image_path, other_base_dir):
        downstream_related_images = []
        image_basename = os.path.basename(image_path)
        if ImageDetails.downstream_related_image_browser.directory != other_base_dir:
            ImageDetails.downstream_related_image_browser = FileBrowser(directory=other_base_dir)
        ImageDetails.downstream_related_image_browser._gather_files()
        for path in ImageDetails.downstream_related_image_browser.filepaths:
            if path == image_path:
                continue
            related_image_path, exact_match = ImageDetails.get_related_image_path(path, check_extra_directories=None)
            if related_image_path is not None:
                if related_image_path == image_path:
                    downstream_related_images.append(path)
                else:
                    file_basename = os.path.basename(related_image_path)
                    if len(file_basename) > 10 and image_basename == file_basename:
                        # NOTE this relation criteria is flimsy but it's better to have false positives than
                        # potentially miss valid files that have been moved since this search is happening
                        downstream_related_images.append(path)
        ImageDetails.downstream_related_images_cache[key] = downstream_related_images

    @staticmethod
    def get_downstream_related_images(image_path, other_base_dir, app_actions, force_refresh=False):
        key = image_path + "/" + other_base_dir
        if force_refresh or key not in ImageDetails.downstream_related_images_cache:
            ImageDetails.refresh_downstream_related_image_cache(key, image_path, other_base_dir)
            downstream_related_images = ImageDetails.downstream_related_images_cache[key]
            toast_text = _("%s downstream image(s) found.").format(len(downstream_related_images))
        else:
            downstream_related_images = ImageDetails.downstream_related_images_cache[key]
            toast_text = _("%s (cached) downstream image(s) found.").format(len(downstream_related_images))
            if ImageDetails.downstream_related_image_index >= len(downstream_related_images):
                ImageDetails.refresh_downstream_related_image_cache(key, image_path, other_base_dir)
                downstream_related_images = ImageDetails.downstream_related_images_cache[key]
                toast_text = _("%s downstream image(s) found.").format(len(downstream_related_images))
        if len(downstream_related_images) == 0:
            app_actions.toast(_("No downstream related images found in") + f"\n{other_base_dir}")
            return None
        app_actions.toast(toast_text)
        return downstream_related_images

    @staticmethod
    def next_downstream_related_image(image_path, other_base_dir, app_actions):
        '''
        In this case, find the next image that has been created from the given image.
        '''
        downstream_related_images = ImageDetails.get_downstream_related_images(image_path, other_base_dir, app_actions)
        if downstream_related_images is None:
            return None
        if ImageDetails.downstream_related_image_index >= len(downstream_related_images):
            ImageDetails.downstream_related_image_index = 0
        downstream_related_image_path = downstream_related_images[ImageDetails.downstream_related_image_index]
        ImageDetails.downstream_related_image_index += 1
        return downstream_related_image_path

    def set_image_generation_mode(self, event=None):
        ImageDetails.image_generation_mode = ImageGenerationType.get(self.image_generation_mode_var.get())

    def run_image_generation(self, event=None):
        ImageDetails.run_image_generation_static(self.app_actions)

    def run_redo_prompt(self, event=None):
        ImageDetails.run_image_generation_static(self.app_actions, _type=ImageGenerationType.REDO_PROMPT)

    @staticmethod
    def run_image_generation_static(app_actions,  _type=None, modify_call=False, event=None):
        if event is not None:
            if Utils.modifier_key_pressed(event, [ModifierKey.SHIFT]):
                _type = ImageGenerationType.CANCEL
            elif Utils.modifier_key_pressed(event, [ModifierKey.ALT]):
                _type = ImageGenerationType.REVERT_TO_SIMPLE_GEN
            else:
                _type = ImageGenerationType.LAST_SETTINGS
            app_actions.run_image_generation(_type=_type, image_path=ImageDetails.previous_image_generation_image, modify_call=modify_call)
        else:
            if _type is None:
                _type = ImageDetails.image_generation_mode
            app_actions.run_image_generation(_type=_type, modify_call=modify_call)

    @staticmethod
    def get_image_specific_generation_mode():
        if ImageDetails.image_generation_mode in [ImageGenerationType.REDO_PROMPT, ImageGenerationType.CONTROL_NET, ImageGenerationType.IP_ADAPTER]:
            return ImageDetails.image_generation_mode
        return ImageGenerationType.CONTROL_NET

    def update_tags(self):
        logger.info(f"Updating tags for {self.image_path}")
        tags_str = self.tags_str.get()
        if tags_str == "":
            self.tags = []
        else:
            self.tags = tags_str.split(", ")
            for i in range(len(self.tags)):
                self.tags[i] = self.tags[i].strip()
        image_data_extractor.set_tags(self.image_path, self.tags)
        logger.info("Updated tags for " + self.image_path)
        self.app_actions.toast(_("Updated tags for %s").format(self.image_path))

    def close_windows(self, event=None):
        self.app_actions.set_image_details_window(None)
        self.master.destroy()
        self.has_closed = True

    def add_label(self, label_ref, text, row=None, column=0, wraplength=500):
        increment_row_counter = row == None
        if increment_row_counter:
            row = self.row_count0 if column == 0 else self.row_count1
        label_ref['text'] = text
        label_ref.grid(column=column, row=row, sticky=W)
        label_ref.config(wraplength=wraplength, justify=LEFT, bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
        if increment_row_counter:
            if column == 0:
                self.row_count0 += 1
            else:
                self.row_count1 += 1

    def add_button(self, button_ref_name, text, command, row=None, column=0):
        increment_row_counter = row == None
        if increment_row_counter:
            row = self.row_count0 if column == 0 else self.row_count1
        if getattr(self, button_ref_name) is None:
            button = Button(master=self.frame, text=text, command=command)
            setattr(self, button_ref_name, button)
            button  # for some reason this is necessary to maintain the reference?
            button.grid(row=row, column=column)
        if increment_row_counter:
            if column == 0:
                self.row_count0 += 1
            else:
                self.row_count1 += 1
