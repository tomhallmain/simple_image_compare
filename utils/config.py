import json
import os

from utils.constants import CompareMode, SortBy


class Config:
    CONFIGS_DIR_LOC = os.path.join(os.path.dirname(os.path.abspath(os.path.dirname(__file__))), "configs")

    def __init__(self):
        self.dict = {}
        self.clip_model = "ViT-B/32"
        self.compare_mode = CompareMode.CLIP_EMBEDDING
        self.max_search_results = 50
        self.embedding_similarity_threshold = 0.9
        self.color_diff_threshold = 15
        self.escape_backslash_filepaths = False
        self.file_counter_limit = 40000
        self.fill_canvas = False
        self.image_browse_recursive = False
        self.image_tagging_enabled = True
        self.print_settings = True
        self.show_toasts = True
        self.slideshow_interval_seconds = 7
        self.file_check_interval_seconds = 10
        self.file_check_skip_if_n_files_over = 5000
        self.default_main_window_size = "1400x950"
        self.sort_by = SortBy.NAME
        self.toasts_persist_seconds = 2
        self.delete_instantly = False
        self.move_marks_overwrite_existing_file = False
        self.trash_folder = None
        self.sd_prompt_reader_loc = None
        self.file_types = [".jpg", ".jpeg", ".png", ".tiff", ".webp"]
        self.font_size = 8
        self.threshold_potential_duplicate_color = 50
        self.threshold_potential_duplicate_embedding = 0.99
        self.use_file_paths_json = False # TODO update the JSON for this
        self.file_paths_json_path = "file_paths.json" # TODO update the JSON for this
        self.text_embedding_search_presets = []
        self.text_embedding_search_preset_index = -1
        self.text_embedding_search_presets_exclusive = False

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
            self.set_values(list, "file_types", "text_embedding_search_presets")
            self.set_values(str,
                            "default_main_window_size",
                            "clip_model",
                            "file_paths_json_path")
            self.set_values(bool,
                            "image_browse_recursive",
                            "image_tagging_enabled",
                            "escape_backslash_filepaths",
                            "fill_canvas",
                            "print_settings",
                            "show_toasts",
                            "delete_instantly",
                            "move_marks_overwrite_existing_file",
                            "use_file_paths_json",
                            "text_embedding_search_presets_exclusive")
            self.set_values(int,
                            "max_search_results",
                            "color_diff_threshold",
                            "file_counter_limit",
                            "slideshow_interval_seconds",
                            "file_check_interval_seconds",
                            "file_check_skip_if_n_files_over",
                            "toasts_persist_seconds",
                            "font_size",
                            "threshold_potential_duplicate_color")
            self.set_values(float,
                            "embedding_similarity_threshold",
                            "threshold_potential_duplicate_embedding")
            self.sd_prompt_reader_loc = self.validate_and_set_directory(key="sd_prompt_reader_loc")

            try:
                self.compare_mode = CompareMode[self.dict["compare_mode"]]
            except Exception:
                raise AssertionError("Invalid compare mode for compare_mode config setting. Must be one of CLIP_EMBEDDING, COLOR_MATCHING")

            try:
                self.sort_by = SortBy[self.dict["sort_by"]]
            except Exception:
                raise AssertionError("Invalid sort type for sort_by config setting. Must be one of NAME, FULL_PATH, CREATION_TIME, TYPE")

        if self.print_settings:
            self.print_config_settings()

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
