from tkinter import Frame, Label, BooleanVar, StringVar, LEFT, W, E, Checkbutton
from tkinter.ttk import Entry

from utils.config import config
from utils.app_style import AppStyle


# TODO config setting update fields and functions


class HelpAndConfig():
    has_run_import = False

    def __init__(self, master):
        self.master = master
        self.frame = Frame(self.master)
        self.frame.grid(column=0, row=0)
        self.frame.columnconfigure(0, weight=1)
        self.frame.columnconfigure(0, weight=9)
        self.frame.config(bg=AppStyle.BG_COLOR)
        self.row_counter0 = 0
        self.row_counter1 = 0
        col_0_width = 250

        self.help_label_list = []

        help_details = {
            "Command": "Description",
            "Shift+D": "Show image details",
            "Ctrl+G": "Open Go to file window",
            "Home": "Reset image browser",
            "Page Up/Down": "Page through images",
            "Shift+M": "Add or remove a mark for current image",
            "Shift+N": "Add all marks between most recently set and current file, or all marks in current group",
            "Shift+G": "Go to next mark",
            "Shift+C": "Clear marks list",
            "Ctrl+C": "Copy marks list",
            "Ctrl+D": "Set current marks from previous marks list",
            "Ctrl+M": "Open marks window",
            "Ctrl+K": "Open marks window (no GUI)",
            "Ctrl+Z": "Undo previous marks changes",
            "Ctrl+X": "Move previous marks to a different directory",
            "Ctrl+B": "Return to Browsing mode",
            "Ctrl+S": "Run next text embedding search preset",
            "Left/Right Arrow": "Show previous/next image",
            "Mouse Wheel Up/Down": "Show previous/next image",
            "Shift+Left/Right Arrow":  "Show previous/next group",
            "Shift+O": "Open image location",
            "Shift+Delete / Mouse Wheel Click": "Delete image (or marked file group if marks window selected)",
            "F11": "Toggle fullscreen",
        }

        for key, value in help_details.items():
            _label = Label(self.frame)
            label = Label(self.frame)
            self.add_label(_label, key, wraplength=col_0_width)
            self.add_label(label, value, column=1)
            self.help_label_list.append(_label)
            self.help_label_list.append(label)

        self.label_config_title = Label(self.frame)
        self.label_config_title['text'] = "Config Settings"
        self.label_config_title.grid(row=self.row_counter0, columnspan=2)
        self.label_config_title.config(bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
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
        self.label_max_search_results = Label(self.frame)
        self.max_search_results = StringVar(value=str(config.max_search_results))
        self.entry_max_search_results = self.new_entry(self.max_search_results)
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
        self.add_label(self.label_max_search_results, "Max Search Results", wraplength=col_0_width)
        self.apply_to_grid(self.max_search_results, sticky=W, column=1)
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

        self.master.bind("<Escape>", self.close_windows)
        self.frame.after(1, lambda: self.frame.focus_force())

    def close_windows(self, event=None):
        self.master.destroy()

    def add_label(self, label_ref, text, column=0, wraplength=500):
        label_ref['text'] = text
        label_ref.config(wraplength=wraplength, justify=LEFT, bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
        self.apply_to_grid(label_ref, column=column)

    def add_checkbox(self, checkbox_ref):
        checkbox_ref.config(bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR, selectcolor=AppStyle.BG_COLOR)
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
