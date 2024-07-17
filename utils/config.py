import json
import os

from utils.constants import CompareMode, SortBy
from utils.running_tasks_registry import running_tasks_registry
from utils.utils import Utils


class Config:
    CONFIGS_DIR_LOC = os.path.join(os.path.dirname(os.path.abspath(os.path.dirname(__file__))), "configs")

    def __init__(self):
        self.dict = {}
        self.locale = Utils.get_default_user_language()
        self.foreground_color = None
        self.background_color = None
        self.debug = False
        self.log_level = "info"
        self.clip_model = "ViT-B/32"
        self.compare_mode = CompareMode.CLIP_EMBEDDING
        self.max_search_results = 50
        self.search_only_return_closest = False
        self.store_checkpoints = False
        self.embedding_similarity_threshold = 0.9
        self.color_diff_threshold = 15
        self.escape_backslash_filepaths = False
        self.file_counter_limit = 40000
        self.fill_canvas = False
        self.image_browse_recursive = False
        self.sidebar_visible = True
        self.image_tagging_enabled = True
        self.print_settings = True
        self.show_toasts = True
        self.slideshow_interval_seconds = 7
        self.file_check_interval_seconds = 10
        self.file_check_skip_if_n_files_over = 5000
        self.default_main_window_size = "1400x950"
        self.default_secondary_window_size = "600x700"
        self.sort_by = SortBy.NAME
        self.toasts_persist_seconds = 2
        self.delete_instantly = False
        self.clear_marks_with_errors_after_move = False
        self.move_marks_overwrite_existing_file = False
        self.trash_folder = None
        self.sd_prompt_reader_loc = None
        self.always_open_new_windows = False
        self.file_types = [".jpg", ".jpeg", ".png", ".tiff", ".webp"]
        self.directories_to_search_for_related_images = []
        self.font_size = 8
        self.threshold_potential_duplicate_color = 50
        self.threshold_potential_duplicate_embedding = 0.99
        self.use_file_paths_json = False # TODO update the JSON for this
        self.file_paths_json_path = "file_paths.json" # TODO update the JSON for this
        self.text_embedding_search_presets = []
        self.text_embedding_search_preset_index = -1
        self.text_embedding_search_presets_exclusive = False
        self.sd_runner_client_port = 6000
        self.sd_runner_client_password = "<PASSWORD>"
        self.refacdir_client_port = 6001
        self.refacdir_client_password = "<PASSWORD>"

        dict_set = False
        configs =  [ f.path for f in os.scandir(Config.CONFIGS_DIR_LOC) if f.is_file() and f.path.endswith(".json") ]
        self.config_path = None

        for c in configs:
            if os.path.basename(c) == "config.json":
                self.config_path = c
                break
            elif os.path.basename(c) != "config_example.json":
                self.config_path = c

        if self.config_path is None:
            self.config_path = os.path.join(Config.CONFIGS_DIR_LOC, "config_example.json")

        try:
            self.dict = json.load(open(self.config_path, "r"))
            dict_set = True
        except Exception as e:
            print(e)
            print("Unable to load config. Ensure config.json file is located in the configs directory of simple-image-comare.")

        if dict_set:
            self.set_values(None, "trash_folder")
            self.set_values(list,
                            "file_types",
                            "text_embedding_search_presets",
                            "directories_to_search_for_related_images")
            self.set_values(str,
                            "foreground_color",
                            "background_color",
                            "locale",
                            "log_level",
                            "default_main_window_size",
                            "default_secondary_window_size",
                            "clip_model",
                            "file_paths_json_path",
                            "sd_runner_client_password",
                            "refacdir_client_password")
            self.set_values(bool,
                            "image_browse_recursive",
                            "image_tagging_enabled",
                            "escape_backslash_filepaths",
                            "fill_canvas",
                            "print_settings",
                            "show_toasts",
                            "delete_instantly",
                            "clear_marks_with_errors_after_move",
                            "move_marks_overwrite_existing_file",
                            "use_file_paths_json",
                            "text_embedding_search_presets_exclusive",
                            "store_checkpoints",
                            "search_only_return_closest",
                            "sidebar_visible",
                            "always_open_new_windows")
            self.set_values(int,
                            "max_search_results",
                            "color_diff_threshold",
                            "file_counter_limit",
                            "slideshow_interval_seconds",
                            "file_check_interval_seconds",
                            "file_check_skip_if_n_files_over",
                            "toasts_persist_seconds",
                            "font_size",
                            "threshold_potential_duplicate_color",
                            "sd_runner_client_port",
                            "refacdir_client_port")
            self.set_values(float,
                            "embedding_similarity_threshold",
                            "threshold_potential_duplicate_embedding")
            try:
                self.sd_prompt_reader_loc = self.validate_and_set_directory(key="sd_prompt_reader_loc")
            except Exception as e:
                print(e)

            try:
                self.compare_mode = CompareMode[self.dict["compare_mode"]]
            except Exception:
                raise AssertionError("Invalid compare mode for compare_mode config setting. Must be one of CLIP_EMBEDDING, COLOR_MATCHING")

            try:
                self.sort_by = SortBy[self.dict["sort_by"]]
            except Exception:
                raise AssertionError("Invalid sort type for sort_by config setting. Must be one of NAME, FULL_PATH, CREATION_TIME, TYPE")

        self.debug = self.log_level and self.log_level.lower() == "debug"

        if len(self.directories_to_search_for_related_images) > 0:
            temp = self.directories_to_search_for_related_images[:]
            for _dir in temp:
                if not os.path.isdir(_dir):
                    print(f"Invalid directory to search for related images: {_dir}")
                    self.directories_to_search_for_related_images.remove(_dir)

        if self.print_settings:
            self.print_config_settings()

        if self.locale is None or self.locale == "":
            print(f"No locale set for config file.")
            self.locale = Utils.get_default_user_language()
        os.environ["LANG"] = self.locale # TODO figure out a way to install the config lang despite the circular import reference

    def validate_and_set_directory(self, key):
        loc = self.dict[key]
        if loc and loc.strip() != "":
            if "{HOME}" in loc:
                loc = loc.strip().replace("{HOME}", os.path.expanduser("~"))
            if not os.path.isdir(loc):
                raise Exception(f"Invalid location provided for {key}: {loc}")
            return loc
        return None

    def set_values(self, type, *names):
        for name in names:
            if type:
                try:
                    setattr(self, name, type(self.dict[name]))
                except Exception as e:
                    print(e)
                    print(f"Failed to set {name} from config.json file. Ensure the value is set and of the correct type.")
            else:
                try:
                    setattr(self, name, self.dict[name])
                except Exception as e:
                    print(e)
                    print(f"Failed to set {name} from config.json file. Ensure the key is set.")

    def next_text_embedding_search_preset(self):
        self.text_embedding_search_preset_index += 1
        if self.text_embedding_search_preset_index >= len(self.text_embedding_search_presets):
            self.text_embedding_search_preset_index = 0
        if self.text_embedding_search_preset_index >= len(self.text_embedding_search_presets):
            return None
        else:
            return self.text_embedding_search_presets[self.text_embedding_search_preset_index]


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
        if self.sd_prompt_reader_loc is not None:
            print(f" - Using stable diffusion prompt reader path at {self.sd_prompt_reader_loc}")
        else:
            print(f" - Stable diffusion prompt reader location is not set or invalid.")
        print(f" - Max files per compare: {self.file_counter_limit}")

config = Config()


class FileCheckConfig:
    interval_seconds = config.file_check_interval_seconds

    def __init__(self, window_id):
        self.window_id = window_id
        self.registry_id = f"{window_id}_file_check"
        self.is_running = False
        running_tasks_registry.add(self.registry_id, FileCheckConfig.interval_seconds, f"File Check (window {self.window_id})")

    def toggle_filecheck(self):
        self.is_running = not self.is_running
        if self.is_running:
            running_tasks_registry.add(self.registry_id, FileCheckConfig.interval_seconds, f"File Check (window {self.window_id})")
        else:
            running_tasks_registry.remove(self.registry_id)

    def end_filecheck(self):
        self.is_running = False
        running_tasks_registry.remove(self.registry_id)


class SlideshowConfig:
    '''
    There are two modes, one is simple slideshow, the other is a slideshow that shows newly added images only.
    '''
    interval_seconds = config.slideshow_interval_seconds

    def __init__(self, window_id):
        self.window_id = window_id
        self.registry_id = f"{window_id}_slideshow"
        self.slideshow_running = False
        self.show_new_images = False

    def toggle_slideshow(self):
        if self.show_new_images:
            self.show_new_images = False
            running_tasks_registry.remove(self.registry_id)
        elif self.slideshow_running:
            self.show_new_images = True
            self.slideshow_running = False
        else:
            self.slideshow_running = True
            running_tasks_registry.add(self.registry_id, SlideshowConfig.interval_seconds, f"Slideshow (window {self.window_id})")

    def end_slideshows(self):
        if self.slideshow_running or self.show_new_images:
            self.slideshow_running = False
            self.show_new_images = False
            return True
        return False

