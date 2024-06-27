from datetime import datetime
import os

from PIL import Image
from tkinter import Frame, Label, StringVar, LEFT, W
from tkinter.font import Font
from tkinter.ttk import Entry, Button

from image.image_data_extractor import image_data_extractor
from image.rotation import rotate_image
from image.smart_crop import Cropper
from utils.config import config
from utils.app_style import AppStyle


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
    def __init__(self, master, image_path, index_text, refresh_callback, go_to_file_callback):
        self.master = master
        self.image_path = image_path
        self.refresh_callback = refresh_callback
        self.go_to_file_callback = go_to_file_callback
        self.frame = Frame(self.master)
        self.frame.grid(column=0, row=0)
        self.frame.columnconfigure(0, weight=1)
        self.frame.columnconfigure(0, weight=9)
        self.frame.config(bg=AppStyle.BG_COLOR)
        col_0_width = 100

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

        image = Image.open(self.image_path)
        image_mode = str(image.mode)
        image_dims = f"{image.size[0]}x{image.size[1]}"
        creation_time = datetime.fromtimestamp(os.path.getmtime(self.image_path)).strftime("%Y-%m-%d %H:%M")
        image.close()
        positive, negative = image_data_extractor.get_image_prompts(self.image_path)

        self.add_label(self._label_path, "Image Path", row=0, wraplength=col_0_width)
        self.add_label(self.label_path, self.image_path, row=0, column=1)
        self.add_label(self._label_index, "File Index", row=1, wraplength=col_0_width)
        self.add_label(self.label_index, index_text, row=1, column=1)
        self.add_label(self._label_mode, "Color Mode", row=2, wraplength=col_0_width)
        self.add_label(self.label_mode, image_mode, row=2, column=1)
        self.add_label(self._label_dims, "Dimensions", row=3, wraplength=col_0_width)
        self.add_label(self.label_dims, image_dims, row=3, column=1)
        self.add_label(self._label_size, "Size", row=4, wraplength=col_0_width)
        self.add_label(self.label_size, get_readable_file_size(self.image_path), row=4, column=1)
        self.add_label(self._label_mtime, "Modification Time", row=5, wraplength=col_0_width)
        self.add_label(self.label_mtime, creation_time, row=5, column=1)
        self.add_label(self._label_positive, "Positive", row=6, wraplength=col_0_width)
        self.add_label(self.label_positive, positive, row=6, column=1)
        self.add_label(self._label_negative, "Negative", row=7, wraplength=col_0_width)
        self.add_label(self.label_negative, negative, row=7, column=1)

        self.copy_prompt_btn = None
        self.copy_prompt_no_break_btn = None
        self.add_button("copy_prompt_btn", "Copy Prompt", self.copy_prompt, row=8)
        self.add_button("copy_prompt_no_break_btn", "Copy Prompt No BREAK", self.copy_prompt_no_break, row=8, column=1)

        self.rotate_left_btn = None
        self.rotate_right_btn = None
        self.add_button("rotate_left_btn", "Rotate Image Left", lambda: self.rotate_image(right=False), row=9, column=0)
        self.add_button("rotate_right_btn", "Rotate Image Right", lambda: self.rotate_image(right=True), row=9, column=1)

        self.crop_image_btn = None
        self.add_button("crop_image_btn", "Crop Image", lambda: self.crop_image(), row=10, column=0)


        if config.image_tagging_enabled:
            self.add_label(self._label_tags, "Tags", row=9, wraplength=col_0_width)

            self.tags = image_data_extractor.extract_tags(self.image_path)
            tags_str = ", ".join(self.tags) if self.tags else ""
            self.tags_str = StringVar(self.master, value=tags_str)
            self.tags_entry = Entry(self.frame, textvariable=self.tags_str, width=30, font=Font(size=8))
            self.tags_entry.grid(row=11, column=1)

            self.update_tags_btn = None
            self.add_button("update_tags_btn", "Update Tags", self.update_tags, row=11)

        self.master.bind("<Escape>", self.close_windows)
        self.frame.after(1, lambda: self.frame.focus_force())

    def copy_prompt(self):
        positive = self.label_positive["text"]
        self.master.clipboard_clear()
        self.master.clipboard_append(positive)

    # Remove pony prompt massaging
    def copy_prompt_no_break(self):
        positive = self.label_positive["text"]
        if "BREAK" in positive:
            positive = positive[positive.index("BREAK")+6:]
        self.master.clipboard_clear()
        self.master.clipboard_append(positive)

    def rotate_image(self, right=False):
        rotate_image(self.image_path, right)
        self.close_windows()
        self.refresh_callback()
        # TODO properly set the file info on the rotated file instead of having to use this callback
        self.go_to_file_callback(search_text=os.path.basename(self.image_path), exact_match=True)

    def crop_image(self):
        Cropper.smart_crop_multi_detect(self.image_path, "")
        self.close_windows()
        self.refresh_callback()
        # TODO actually go to the cropped file. In this case we don't want to replace the original because there may be errors in some cases.

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
        print("Updated tags for " + self.image_path) # TODO toast

    def close_windows(self, event=None):
        self.master.destroy()

    def add_label(self, label_ref, text, row=0, column=0, wraplength=500):
        label_ref['text'] = text
        label_ref.grid(column=column, row=row, sticky=W)
        label_ref.config(wraplength=wraplength, justify=LEFT, bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)

    def add_button(self, button_ref_name, text, command, row=0, column=0):
        if getattr(self, button_ref_name) is None:
            button = Button(master=self.frame, text=text, command=command)
            setattr(self, button_ref_name, button)
            button # for some reason this is necessary to maintain the reference?
            button.grid(row=row, column=column)

