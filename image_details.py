import sys

from tkinter import Frame, Label, LEFT, W

from config import config
from style import Style

has_run_import = False
try:
    if config.sd_prompt_reader_loc:
        sys.path.insert(0, config.sd_prompt_reader_loc)
        from sd_prompt_reader.image_data_reader import ImageDataReader
        has_run_import = True
except Exception as e:
    print(e)


class ImageDetails():
    has_run_import = False

    def __init__(self, master, image, image_path, config_path):
        self.master = master
        self.image = image
        self.image_path = image_path
        self.frame = Frame(self.master)
        self.frame.grid(column=0, row=0)
        self.frame.columnconfigure(0, weight=1)
        self.frame.columnconfigure(0, weight=9)
        self.frame.config(bg=Style.BG_COLOR)

        self._label_path = Label(self.frame)
        self._label_mode = Label(self.frame)
        self._label_size = Label(self.frame)
        self._label_positive = Label(self.frame)
        self._label_negative = Label(self.frame)

        self.add_label(self._label_path, "Image Path", row=0, wraplength=100)
        self.add_label(self._label_mode, "Color Mode", row=1, wraplength=100)
        self.add_label(self._label_size, "Dimensions", row=2, wraplength=100)
        self.add_label(self._label_positive, "Positive", row=3, wraplength=100)
        self.add_label(self._label_negative, "Negative", row=4, wraplength=100)

        self.label_path = Label(self.frame)
        self.label_mode = Label(self.frame)
        self.label_size = Label(self.frame)

        positive = "(Unable to parse image prompt information for this file.)"
        negative = ""

        if has_run_import:
            try:
                positive, negative = self.get_image_data()
            except Exception as e:
                raise e
    #            print()

        self.label_positive = Label(self.frame)
        self.label_negative = Label(self.frame)

        self.add_label(self.label_path, self.image_path, row=0, column=1)
        self.add_label(self.label_mode, str(self.image._PhotoImage__mode), row=1, column=1)
        self.add_label(self.label_size, str(self.image._PhotoImage__size), row=2, column=1)
        self.add_label(self.label_positive, positive, row=3, column=1)
        self.add_label(self.label_negative, negative, row=4, column=1)
        self.master.bind("<Shift-W>", self.close_windows)

    def get_image_data(self):
        image_data = ImageDataReader(self.image_path)
        if not image_data.tool:
            raise Exception("SD Prompt Reader was unable to parse image file data: " + self.image_path)
        if image_data.is_sdxl:
            positive = image_data.positive_sdxl
            negative = image_data.negative_sdxl
        else:
            positive = image_data.positive
            negative = image_data.negative
        return positive, negative

    def close_windows(self, event=None):
        self.master.destroy()

    def add_label(self, label_ref, text, row=0, column=0, wraplength=500):
        label_ref['text'] = text
        label_ref.grid(column=column, row=row, sticky=W)
        label_ref.config(wraplength=wraplength, justify=LEFT, bg=Style.BG_COLOR, fg=Style.FG_COLOR)

