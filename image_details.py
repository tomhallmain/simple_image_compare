from tkinter import Frame, Label, StringVar, LEFT, W
from tkinter.font import Font
from tkinter.ttk import Entry, Button

from config import config
from image_data_extractor import image_data_extractor
from app_style import AppStyle


class ImageDetails():
    def __init__(self, master, image, image_path):
        self.master = master
        self.image = image
        self.image_path = image_path
        self.frame = Frame(self.master)
        self.frame.grid(column=0, row=0)
        self.frame.columnconfigure(0, weight=1)
        self.frame.columnconfigure(0, weight=9)
        self.frame.config(bg=AppStyle.BG_COLOR)
        col_0_width = 100

        self._label_path = Label(self.frame)
        self._label_mode = Label(self.frame)
        self._label_size = Label(self.frame)
        self._label_positive = Label(self.frame)
        self._label_negative = Label(self.frame)
        self._label_tags = Label(self.frame)

        self.add_label(self._label_path, "Image Path", row=0, wraplength=col_0_width)
        self.add_label(self._label_mode, "Color Mode", row=1, wraplength=col_0_width)
        self.add_label(self._label_size, "Dimensions", row=2, wraplength=col_0_width)
        self.add_label(self._label_positive, "Positive", row=3, wraplength=col_0_width)
        self.add_label(self._label_negative, "Negative", row=4, wraplength=col_0_width)

        self.label_path = Label(self.frame)
        self.label_mode = Label(self.frame)
        self.label_size = Label(self.frame)

        positive, negative = image_data_extractor.get_image_prompts(self.image_path)

        self.label_positive = Label(self.frame)
        self.label_negative = Label(self.frame)

        self.add_label(self.label_path, self.image_path, row=0, column=1)
        self.add_label(self.label_mode, str(self.image._PhotoImage__mode), row=1, column=1)
        self.add_label(self.label_size, str(self.image._PhotoImage__size), row=2, column=1)
        self.add_label(self.label_positive, positive, row=3, column=1)
        self.add_label(self.label_negative, negative, row=4, column=1)

        self.copy_prompt_btn = None
        self.copy_prompt_no_break_btn = None
        self.add_button("copy_prompt_btn", "Copy Prompt", self.copy_prompt, row=5)
        self.add_button("copy_prompt_no_break_btn", "Copy Prompt No BREAK", self.copy_prompt_no_break, row=5, column=1)


        if config.image_tagging_enabled:
            self.add_label(self._label_tags, "Tags", row=6, wraplength=col_0_width)

            self.tags = image_data_extractor.extract_tags(self.image_path)
            tags_str = ", ".join(self.tags) if self.tags else ""
            self.tags_str = StringVar(self.master, value=tags_str)
            self.tags_entry = Entry(self.frame, textvariable=self.tags_str, width=30, font=Font(size=8))
            self.tags_entry.grid(row=6, column=1)

            self.update_tags_btn = None
            self.add_button("update_tags_btn", "Update Tags", self.update_tags, row=7)

        self.master.bind("<Shift-W>", self.close_windows)
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
