import json

from file_browser import SortBy

class Config:
    def __init__(self):
        try:
            self.dict = json.load(open("config.json", "r"))
            self.color_diff_threshold = int(self.dict["color_diff_threshold"])
            self.escape_backslash_filepaths = self.dict["escape_backslash_filepaths"]
            self.file_counter_limit = int(self.dict["file_counter_limit"])
            self.fill_canvas = self.dict["fill_canvas"]
            self.image_browse_recursive = self.dict["image_browse_recursive"]
            self.print_settings = self.dict["print_settings"]
            self.show_toasts = self.dict["show_toasts"]
            self.slideshow_interval_seconds = int(self.dict["slideshow_interval_seconds"])
            self.file_check_interval_seconds = int(self.dict["file_check_interval_seconds"])
            self.toasts_persist_seconds = int(self.dict["toasts_persist_seconds"])
            self.delete_instantly = self.dict["delete_instantly"]
            self.trash_folder = self.dict["trash_folder"]
            try:
                self.sort_by = SortBy[self.dict["sort_by"]]
            except Exception:
                raise AssertionError("Invalid sort type for sort_by config setting. Must be one of NAME, FULL_PATH, CREATION_TIME, TYPE")
        except Exception as e:
            print(e)
            print("Unable to load config. Ensure config.json file is located in the base directory of simple-image-comare.")
            self.dict = {}
            self.color_diff_threshold = 15
            self.escape_backslash_filepaths = False
            self.file_counter_limit = 40000
            self.fill_canvas = False
            self.image_browse_recursive = False
            self.print_settings = True
            self.show_toasts = True
            self.slideshow_interval_seconds = 7
            self.file_check_interval_seconds = 10
            self.sort_by = SortBy.NAME
            self.toasts_persist_seconds = 2
            self.delete_instantly = False
            self.trash_folder = None

        if self.print_settings:
            self.print_config_settings()

    def print_config_settings(self):
        print("Settings active:")
        extra_text = ": False - NO toasts will be shown!" if not self.show_toasts else ""
        print(f" - Show toasts{extra_text}")
        if self.delete_instantly:
            print(f" - Files will be deleted instantly, not sent to trash")
        if self.trash_folder:
            print(f" - Trash folder: {self.trash_folder}")
        if self.escape_backslash_filepaths:
            print(f" - Escape backslashes in filepaths when copying")
        if self.fill_canvas:
            print(f" - Expand images to fill canvas")
        if self.image_browse_recursive:
            print(f" - Recursive file browsing")
        print(f" - Max files per compare: {self.file_counter_limit}")
