from tkinter import Frame, Label, BooleanVar, StringVar, LEFT, W, E, Checkbutton
from tkinter.ttk import Entry

from lib.tk_scroll_demo import ScrollFrame
from utils.config import config
from utils.app_style import AppStyle
from utils.translations import I18N

_ = I18N._


# TODO config setting update fields and functions


class HelpAndConfig():
    has_run_import = False 

    def __init__(self, master):
        self.master = master
        self.help_label_list = []

        self.scroll_frame = ScrollFrame(self.master, bg_color=AppStyle.BG_COLOR)
        self.scroll_frame.pack(side="top", fill="both", expand=True)
        self.frame = Frame(self.scroll_frame.viewPort)
        self.frame.grid(column=0, row=0)
        self.frame.columnconfigure(0, weight=1)
        self.frame.columnconfigure(0, weight=9)
        self.frame.config(bg=AppStyle.BG_COLOR)
        self.row_counter0 = 0
        self.row_counter1 = 0
        col_0_width = 250

        help_details = {
            _("Command"): _("Description"),
            "Ctrl+A": _("Search current image in new window"),
            "Ctrl+B": _("Return to Browsing mode"),
            "Ctrl+C": _("Copy marks list"),
            "Ctrl+D": _("Set current marks from previous marks list"),
            "Ctrl+E": _("Run penultimate marks action"),
            "Ctrl+G": _("Open Go to file window"),
            "Ctrl+H": _("Hide/show sidebar"),
            "Ctrl+H*": _("Open hotkeys window (*when marks window open)"),
            "Ctrl+J": _("Open content filters window"),
            "Ctrl+K": _("Open marks window (no GUI)"),
            "Ctrl+M": _("Open marks window"),
            "Ctrl+N": _("Open marks action history window"),
            "Ctrl+Q": _("Quit"),
            "Ctrl+R": _("Run previous marks action"),
            "Ctrl+Return": _("Continue image generation"),
            "Ctrl+Shift+Return": _("Cancel image generation"),
            "Ctrl+S": _("Run next text embedding search preset"),
            "Ctrl+T": _("Run permanent marks action"),
            "Ctrl+V":  _("Open type configuration window"),
            "Ctrl+W": _("Open new compare window"),
            "Ctrl+X": _("Move previous marks to a different directory"),
            "Ctrl+Z": _("Undo previous marks changes"),
            "Shift-F / F11": _("Toggle fullscreen"),
            "Home": _("Go to first sorted image"),
            "End":   _("Go to last sorted image"),
            "Left/Right Arrow\nMouse Wheel Up/Down": _("Show previous/next image"),
            "Page Up/Down": _("Page through images"),
            "Shift-A": _("Search current image in current window"),
            "Shift+B": _("Clear all hidden images"),
            "Shift+C": _("Clear marks list"),
            "Shift+D": _("Show image details"),
            "Shift+Delete\nMouse Wheel Click": _("Delete image (or marked file group if marks window selected)"),
            "Shift+G": _("Go to next mark"),
            "Shift+H": _("Show help window"),
            "Shift+I\nRight Click": _("Run image generation"),
            "Shift+J": _("Run content filters for all files in the current directory"),
            "Shift+K": _("View last moved image mark"),
            "Shift+L": _("Toggle content filters"),
            "Shift+M": _("Add or remove a mark for current image"),
            "Shift+N": _("Add all marks between most recently set and current selected inclusive, or all marks in current group"),
            "Shift+O": _("Open image location"),
            "Shift+P": _("Open image in GIMP"),
            "Shift+Q": _("Randomly modify image"),
            "Shift+R": _("View related image (controlnet, etc.)"),
            "Shift+S": _("Toggle slideshow"),
            "Shift+T": _("Find related images in open window"),
            "Shift+U": _("Run refacdir"),
            "Shift+V": _("Hide current image"),
            "Shift+Y": _("Set marks from downstream related images"),
            "Shift+Z": _("Undo previous marks changes"),
            "Shift+Left/Right Arrow": _("Show previous/next group"),
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

        self.add_label(self.label_show_toasts, _("Show Toasts"), wraplength=col_0_width)
        self.add_checkbox(self.checkbox_show_toasts)
        self.add_label(self.label_slideshow_interval_seconds, _("Slideshow Interval (sec)"), wraplength=col_0_width)
        self.apply_to_grid(self.entry_slideshow_interval_seconds, sticky=W, column=1)
        self.add_label(self.label_file_check_interval_seconds, _("File Check Interval (sec)"), wraplength=col_0_width)
        self.apply_to_grid(self.entry_file_check_interval_seconds, sticky=W, column=1)
        self.add_label(self.label_max_search_results, _("Max Search Results"), wraplength=col_0_width)
        self.apply_to_grid(self.entry_max_search_results, sticky=W, column=1)
        self.add_label(self.label_sort_by, _("Sort By"), wraplength=col_0_width)
        self.add_label(self.sort_by, str(config.sort_by), column=1)
        self.add_label(self.label_toasts_persist_seconds, _("Toasts Persist (sec)"), wraplength=col_0_width)
        self.apply_to_grid(self.entry_toasts_persist_seconds, sticky=W, column=1)
        self.add_label(self.label_delete_instantly, _("Delete Instantly"), wraplength=col_0_width)
        self.add_checkbox(self.checkbox_delete_instantly)
        self.add_label(self.label_trash_folder, _("Trash Folder"), wraplength=col_0_width)
        self.apply_to_grid(self.entry_trash_folder, sticky=W, column=1)
        self.add_label(self.label_image_tagging_enabled, _("Image Tagging Enabled"), wraplength=col_0_width)
        self.add_checkbox(self.checkbox_image_tagging_enabled)
        self.add_label(self.label_escape_backslash_filepaths, _("Escape Backslash Filepaths"), wraplength=col_0_width)
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
