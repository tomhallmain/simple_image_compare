from tkinter import Frame, Label, BooleanVar, StringVar, LEFT, W, E, Checkbutton
from tkinter.font import Font
from tkinter.ttk import Entry

from config import config
from style import Style


# TODO config setting update fields and functions


class HelpAndConfig():
    has_run_import = False

    def __init__(self, master):
        self.master = master
        self.frame = Frame(self.master)
        self.frame.grid(column=0, row=0)
        self.frame.columnconfigure(0, weight=1)
        self.frame.columnconfigure(0, weight=9)
        self.frame.config(bg=Style.BG_COLOR)
        self.row_counter0 = 0
        self.row_counter1 = 0
        col_0_width = 250

        self._label_1 = Label(self.frame)
        self.label_1 = Label(self.frame)
        self._label_2 = Label(self.frame)
        self.label_2 = Label(self.frame)
        self._label_3 = Label(self.frame)
        self.label_3 = Label(self.frame)
        self._label_4 = Label(self.frame)
        self.label_4 = Label(self.frame)
        self._label_5 = Label(self.frame)
        self.label_5 = Label(self.frame)
        self._label_6 = Label(self.frame)
        self.label_6 = Label(self.frame)
        self._label_7 = Label(self.frame)
        self.label_7 = Label(self.frame)
        self._label_8 = Label(self.frame)
        self.label_8 = Label(self.frame)
        self._label_9 = Label(self.frame)
        self.label_9 = Label(self.frame)
        self._label_10 = Label(self.frame)
        self.label_10 = Label(self.frame)
        self._label_11 = Label(self.frame)
        self.label_11 = Label(self.frame)
        self._label_12 = Label(self.frame)
        self.label_12 = Label(self.frame)
        self._label_13 = Label(self.frame)
        self.label_13 = Label(self.frame)
        self._label_14 = Label(self.frame)
        self.label_14 = Label(self.frame)
        self._label_15 = Label(self.frame)
        self.label_15 = Label(self.frame)

        self.add_label(self._label_1, "Command", wraplength=col_0_width)
        self.add_label(self.label_1, "Description", column=1)
        self.add_label(self._label_2, "Shift+D", wraplength=col_0_width)
        self.add_label(self.label_2, "Show image details", column=1)
        self.add_label(self._label_3, "Home", wraplength=col_0_width)
        self.add_label(self.label_3, "Reset image browser", column=1)
        self.add_label(self._label_4, "Page Up/Page Down", wraplength=col_0_width)
        self.add_label(self.label_4, "Page through images", column=1)
        self.add_label(self._label_5, "Shift+M", wraplength=col_0_width)
        self.add_label(self.label_5, "Add or remove a mark for current image", column=1)
        self.add_label(self._label_6, "Shift+N", wraplength=col_0_width)
        self.add_label(self.label_6, "Add all marks between most recently set and current file", column=1)
        self.add_label(self._label_7, "Shift-G", wraplength=col_0_width)
        self.add_label(self.label_7, "Go to next mark", column=1)
        self.add_label(self._label_14, "Shift+C", wraplength=col_0_width)
        self.add_label(self.label_14, "Copy marks list", column=1)
        self.add_label(self._label_15, "Ctrl+M", wraplength=col_0_width)
        self.add_label(self.label_15, "Move marks to directory", column=1)
        self.add_label(self._label_8, "Left/Right Arrow", wraplength=col_0_width)
        self.add_label(self.label_8, "Show previous/next image", column=1)
        self.add_label(self._label_9, "Mouse Wheel Up/Down", wraplength=col_0_width)
        self.add_label(self.label_9, "Show previous/next image", column=1)
        self.add_label(self._label_10, "Shift-Left/Right Arrow", wraplength=col_0_width)
        self.add_label(self.label_10, "Show previous/next group", column=1)
        self.add_label(self._label_11, "Shift-Enter", wraplength=col_0_width)
        self.add_label(self.label_11, "Open image location", column=1)
        self.add_label(self._label_12, "Shift-Delete / Mouse Wheel Click", wraplength=col_0_width)
        self.add_label(self.label_12, "Delete image", column=1)
        self.add_label(self._label_13, "F11", wraplength=col_0_width)
        self.add_label(self.label_13, "Toggle fullscreen", column=1)
        self.add_label(self._label_14, "", wraplength=col_0_width)
        self.add_label(self.label_14, "", column=1)

        self.label_config_title = Label(self.frame)
        self.label_config_title['text'] = "Config Settings"
        self.label_config_title.grid(row=self.row_counter0, columnspan=2)
        self.label_config_title.config(bg=Style.BG_COLOR, fg=Style.FG_COLOR)
        self.row_counter0 += 1
        self.row_counter1 += 1

        self.label_show_toasts = Label(self.frame)
        self.show_toasts = BooleanVar(value=config.show_toasts)
        self.checkbox_show_toasts = Checkbutton(self.frame, variable=self.show_toasts)
        self.label_slideshow_interval_seconds = Label(self.frame)
        self.slideshow_interval_seconds = StringVar(value=str(config.slideshow_interval_seconds))
        self.entry_slideshow_interval_seconds = self.new_entry(self.slideshow_interval_seconds)
        self.label_file_check_interval_seconds = Label(self.frame)
        self.file_check_interval_seconds = StringVar(value=str(config.file_check_interval_seconds))
        self.entry_file_check_interval_seconds =  self.new_entry(self.file_check_interval_seconds)
        self.label_sort_by = Label(self.frame)
        self.sort_by = Label(self.frame)
        self.label_toasts_persist_seconds = Label(self.frame)
        self.toasts_persist_seconds = StringVar(value=str(config.toasts_persist_seconds))
        self.entry_toasts_persist_seconds = self.new_entry(self.toasts_persist_seconds)
        self.label_delete_instantly = Label(self.frame)
        self.delete_instantly = BooleanVar(value=config.delete_instantly)
        self.checkbox_delete_instantly = Checkbutton(self.frame, variable=self.delete_instantly)
        self.label_trash_folder = Label(self.frame)
        self.trash_folder = StringVar(value=str(config.trash_folder))
        self.entry_trash_folder = self.new_entry(self.trash_folder)
        self.label_image_tagging_enabled = Label(self.frame)
        self.image_tagging_enabled = BooleanVar(value=config.image_tagging_enabled)
        self.checkbox_image_tagging_enabled = Checkbutton(self.frame, variable=self.image_tagging_enabled)
        self.label_escape_backslash_filepaths = Label(self.frame)
        self.escape_backslash_filepaths = BooleanVar(value=config.escape_backslash_filepaths)
        self.checkbox_escape_backslash_filepaths = Checkbutton(self.frame, variable=self.escape_backslash_filepaths)

        self.add_label(self.label_show_toasts, "Show Toasts", wraplength=col_0_width)
        self.add_checkbox(self.checkbox_show_toasts)
        self.add_label(self.label_slideshow_interval_seconds, "Slideshow Interval (sec)", wraplength=col_0_width)
        self.apply_to_grid(self.entry_slideshow_interval_seconds, sticky=W, column=1)
        self.add_label(self.label_file_check_interval_seconds, "File Check Interval (sec)", wraplength=col_0_width)
        self.apply_to_grid(self.entry_file_check_interval_seconds, sticky=W, column=1)
        self.add_label(self.label_sort_by, "Sort By", wraplength=col_0_width)
        self.add_label(self.sort_by, str(config.sort_by), column=1)
        self.add_label(self.label_toasts_persist_seconds, "Toasts Persist (sec)", wraplength=col_0_width)
        self.apply_to_grid(self.entry_toasts_persist_seconds, sticky=W, column=1)
        self.add_label(self.label_delete_instantly, "Delete Instantly", wraplength=col_0_width)
        self.add_checkbox(self.checkbox_delete_instantly)
        self.add_label(self.label_trash_folder, "Trash Folder", wraplength=col_0_width)
        self.apply_to_grid(self.entry_trash_folder, sticky=W, column=1)
        self.add_label(self.label_image_tagging_enabled, "Image Tagging Enabled", wraplength=col_0_width)
        self.add_checkbox(self.checkbox_image_tagging_enabled)
        self.add_label(self.label_escape_backslash_filepaths, "Escape Backslash Filepaths", wraplength=col_0_width)
        self.add_checkbox(self.checkbox_escape_backslash_filepaths)

        self.master.bind("<Shift-W>", self.close_windows)
        self.frame.after(1, lambda: self.frame.focus_force())

    def close_windows(self, event=None):
        self.master.destroy()

    def add_label(self, label_ref, text, column=0, wraplength=500):
        label_ref['text'] = text
        label_ref.config(wraplength=wraplength, justify=LEFT, bg=Style.BG_COLOR, fg=Style.FG_COLOR)
        self.apply_to_grid(label_ref, column=column)

    def add_checkbox(self, checkbox_ref):
        checkbox_ref.config(bg=Style.BG_COLOR, fg=Style.FG_COLOR, selectcolor=Style.BG_COLOR)
        self.apply_to_grid(checkbox_ref, column=1)

    def new_entry(self, text_variable):
        return Entry(self.frame, textvariable=text_variable, width=50)
#        return Entry(self.frame, text=text, textvariable=text_variable, font=Font(size=8))

    def apply_to_grid(self, component, sticky=W, pady=0, column=0):
        row = self.row_counter0 if column == 0 else self.row_counter1
        if sticky is None:
            component.grid(column=column, row=row, pady=pady)
        else:
            component.grid(column=column, row=row, sticky=sticky, pady=pady)
        if column == 0:
            self.row_counter0 += 1
        else:
            self.row_counter1 += 1
