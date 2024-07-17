from datetime import datetime
import glob
import os

from PIL import Image
from tkinter import Frame, Label, OptionMenu, StringVar, LEFT, W
from tkinter.font import Font
from tkinter.ttk import Entry, Button

from files.file_browser import FileBrowser
from image.image_data_extractor import image_data_extractor
from image.image_enhancer import enhance_image
from image.rotation import rotate_image
from image.smart_crop import Cropper
from image.temp_image_canvas import TempImageCanvas
from utils.config import config
from utils.constants import ImageGenerationType
from utils.app_style import AppStyle
from utils.translations import I18N

_ = I18N._

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
    related_image_canvas = None
    related_image_saved_node_id = "LoadImage"
    downstream_related_image_index = 0
    downstream_related_images_cache = {}
    downstream_related_image_browser = FileBrowser()
    image_generation_mode = ImageGenerationType.CONTROL_NET

    def __init__(self, parent_master, master, image_path, index_text, app_actions, do_refresh=True):
        self.parent_master = parent_master
        self.master = master
        self.image_path = image_path
        self.app_actions = app_actions
        self.frame = Frame(self.master)
        self.frame.grid(column=0, row=0)
        self.frame.columnconfigure(0, weight=1)
        self.frame.columnconfigure(0, weight=9)
        self.frame.config(bg=AppStyle.BG_COLOR)
        self.do_refresh = do_refresh
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
        self._label_tags = Label(self.frame)

        image_mode, image_dims, mod_time, file_size = self._get_image_info()
        positive, negative = image_data_extractor.get_image_prompts(self.image_path)

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
        self.add_label(self.label_negative, negative, column=1)

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

        self.open_related_image_btn = None
        self.add_button("open_related_image_btn", _("Open Related Image"), self.open_related_image)
        self.related_image_node_id = StringVar(self.master, value=ImageDetails.related_image_saved_node_id)
        self.related_image_node_id_entry = Entry(self.frame, textvariable=self.related_image_node_id, width=30, font=Font(size=8))
        self.related_image_node_id_entry.bind("<Return>", self.open_related_image)
        self.related_image_node_id_entry.grid(row=self.row_count1, column=1, sticky="w")
        self.row_count1 += 1

        self.label_image_generation = Label(self.frame)
        self.add_label(self.label_image_generation, _("Image Generation"))
        self.image_generation_mode_var = StringVar()
        self.image_generation_mode_choice = OptionMenu(self.frame, self.image_generation_mode_var,
                                                   *ImageGenerationType.members(), command=self.set_image_generation_mode)
        self.image_generation_mode_choice.grid(row=self.row_count1, column=1, sticky="W")
        self.row_count1 += 1

        self.run_image_generation_button = None
        self.add_button("run_image_generation_button", _("Run Image Generation"), self.run_image_generation, column=0)
        self.label_help = Label(self.frame)
        self.add_label(self.label_help, _("Press Shift+I on a main app window to run this"), column=1)

        if config.image_tagging_enabled:
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
        self.master.bind("<Shift-C>", self.crop_image)
        self.master.protocol("WM_DELETE_WINDOW", self.close_windows)
        self.frame.after(1, lambda: self.frame.focus_force())

    def _get_image_info(self):
        image = Image.open(self.image_path)
        image_mode = str(image.mode)
        image_dims = f"{image.size[0]}x{image.size[1]}"
        mod_time = datetime.fromtimestamp(os.path.getmtime(self.image_path)).strftime("%Y-%m-%d %H:%M")
        image.close()
        file_size = get_readable_file_size(self.image_path)
        return image_mode, image_dims, mod_time, file_size

    def update_image_details(self, image_path, index_text):
        self.image_path = image_path
        image_mode, image_dims, mod_time, file_size = self._get_image_info()
        positive, negative = image_data_extractor.get_image_prompts(self.image_path)
        self.label_path["text"] = image_path
        self.label_index["text"] = index_text
        self.label_mode["text"] = image_mode
        self.label_dims["text"] = image_dims
        self.label_mtime["text"] = mod_time
        self.label_size["text"] = file_size
        self.label_positive["text"] = positive
        self.label_negative["text"] = negative
        self.master.update()

    def copy_prompt(self):
        positive = self.label_positive["text"]
        self.master.clipboard_clear()
        self.master.clipboard_append(positive)
        self.app_actions.toast(_("Copied prompt"))

    # Remove pony prompt massaging
    def copy_prompt_no_break(self):
        positive = self.label_positive["text"]
        if "BREAK" in positive:
            positive = positive[positive.index("BREAK")+6:]
        self.master.clipboard_clear()
        self.master.clipboard_append(positive)
        self.app_actions.toast(_("Copied prompt without BREAK"))

    def rotate_image(self, right=False):
        rotate_image(self.image_path, right)
        self.close_windows()
        self.app_actions.refresh()
        # TODO properly set the file info on the rotated file instead of having to use this callback
        self.app_actions.go_to_file(search_text=os.path.basename(self.image_path), exact_match=True)
        rotation_text = _("Rotated image right") if right else _("Rotated image left")
        self.app_actions.toast(rotation_text)

    def crop_image(self, event=None):
        saved_files = Cropper.smart_crop_multi_detect(self.image_path, "")
        if len(saved_files) > 0:
            self.close_windows()
            self.app_actions.refresh()
            # TODO actually go to the new file. In this case we don't want to replace the original because there may be errors in some cases.
            self.app_actions.toast(_("Cropped image"))
        else:
            self.app_actions.toast(_("No crops found"))

    def enhance_image(self):
        enhance_image(self.image_path)
        self.close_windows()
        self.app_actions.refresh()
        # TODO actually go to the new file. In this case we don't want to replace the original because there may be errors in some cases.
        self.app_actions.toast(_("Enhanced image"))

    def open_related_image(self, event=None):
        node_id = self.related_image_node_id.get().strip()
        if node_id == "":
            print("No node id given")
        else:
            ImageDetails.related_image_saved_node_id = node_id
            ImageDetails.show_related_image(self.parent_master, node_id, self.image_path, self.app_actions)

    @staticmethod
    def get_related_image_path(image_path, node_id=None):
        if node_id is None or node_id == "":
            node_id = ImageDetails.related_image_saved_node_id
        return image_data_extractor.get_related_image_path(image_path, node_id)

    @staticmethod
    def show_related_image(master=None, node_id=None, image_path="", app_actions=None):
        if master is None or image_path == "":
            raise Exception("No master or image path given")
        related_image_path = ImageDetails.get_related_image_path(image_path, node_id)
        if related_image_path is None or related_image_path == "":
            print(f"{image_path} - No related image found for node id {node_id}")
            return
        elif not os.path.isfile(related_image_path):
            print(f"{image_path} - Related image {related_image_path} not found")
            basename = os.path.basename(related_image_path)
            if len(config.directories_to_search_for_related_images) > 0:
                related_image_path_found = False
                for directory in config.directories_to_search_for_related_images:
                    dir_files = glob.glob(os.path.join(directory, "**/*"), recursive=True)
                    for _file in dir_files:
                        if _file == related_image_path:
                            continue
                        if _file.endswith(basename):
                            file_basename = os.path.basename(_file)
                            if basename == file_basename:
                                related_image_path = _file
                                related_image_path_found = True
                                break
                    if related_image_path_found:
                        break
            if not related_image_path_found or not os.path.isfile(related_image_path):
                return
            print(f"{image_path} - Possibly related image {related_image_path} found")
        base_dir = os.path.dirname(related_image_path)
        if app_actions.get_window(base_dir=base_dir, img_path=related_image_path, refocus=True) is not None:
            return
        if ImageDetails.related_image_canvas is None:
            ImageDetails.set_related_image_canvas(master, related_image_path, app_actions)
        try:
            ImageDetails.related_image_canvas.create_image(related_image_path)
            print(f"Related image: {related_image_path}")
        except Exception as e:
            if "invalid command name" in str(e):
                ImageDetails.set_related_image_canvas(master, related_image_path, app_actions)
                ImageDetails.related_image_canvas.create_image(related_image_path)
            else:
                raise e

    @staticmethod
    def set_related_image_canvas(master, related_image_path, app_actions):
        image = Image.open(related_image_path)
        width = min(700, image.size[0])
        height = int(image.size[1] * width / image.size[0])
        ImageDetails.related_image_canvas = TempImageCanvas(master, title=related_image_path,
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
            related_image_path = ImageDetails.get_related_image_path(path)
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
        if force_refresh or not key in ImageDetails.downstream_related_images_cache:
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

    @staticmethod
    def run_image_generation_static(app_actions):
        app_actions.run_image_generation(_type=ImageDetails.image_generation_mode)


    def update_tags(self):
        print(f"Updating tags for {self.image_path}")
        tags_str = self.tags_str.get()
        if tags_str == "":
            self.tags = []
        else:
            self.tags = tags_str.split(", ")
            for i in range(len(self.tags)):
                self.tags[i] = self.tags[i].strip()
        image_data_extractor.set_tags(self.image_path, self.tags)
        print("Updated tags for " + self.image_path)
        self.app_actions.toast(_("Updated tags for %s").format(self.image_path))

    def close_windows(self, event=None):
        self.app_actions.image_details_window = None
        self.master.destroy()

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
            button # for some reason this is necessary to maintain the reference?
            button.grid(row=row, column=column)
        if increment_row_counter:
            if column == 0:
                self.row_count0 += 1
            else:
                self.row_count1 += 1

