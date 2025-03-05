import json
import os

from image.image_edit_configuration import ImageEditConfiguration
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
        self.file_actions_history_max = 200
        self.file_actions_window_rows_max = 300
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
        self.image_types = [".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp", ".heic", ".avif"]
        self.video_types = [".gif", ".mp4", ".mkv", ".avi", ".wmv", ".mov", ".flv"]
        self.image_classifier_h5_models = []
        self.enable_videos = True
        self.enable_pdfs = False
        self.directories_to_search_for_related_images = []
        self.font_size = 8
        self.threshold_potential_duplicate_color = 50
        self.threshold_potential_duplicate_embedding = 0.99
        self.use_file_paths_json = False # TODO update the JSON for this
        self.file_paths_json_path = "file_paths.json" # TODO update the JSON for this
        self.text_embedding_search_presets = []
        self.text_embedding_search_preset_index = -1
        self.text_embedding_search_presets_exclusive = False
        self.enable_prevalidations = True
        self.show_negative_prompt = True
        self.sd_runner_client_port = 6000
        self.sd_runner_client_password = "<PASSWORD>"
        self.refacdir_client_port = 6001
        self.refacdir_client_password = "<PASSWORD>"
        self.gimp_exe_loc = "gimp-2.10"
        self.image_edit_configuration = ImageEditConfiguration()

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

        # Handle old version config keys
        if "file_types" in self.dict:
            self.dict["image_types"] = list(self.dict["file_types"])

        if dict_set:
            self.set_values(None, "trash_folder")
            self.set_values(list,
                            "image_types",
                            "video_types",
                            "text_embedding_search_presets",
                            "directories_to_search_for_related_images",
                            "image_classifier_h5_models")
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
                            "refacdir_client_password",
                            "gimp_exe_loc")
            self.set_values(bool,
                            "image_browse_recursive",
                            "image_tagging_enabled",
                            "escape_backslash_filepaths",
                            "fill_canvas",
                            "enable_videos",
                            "enable_pdfs",
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
                            "always_open_new_windows",
                            "enable_prevalidations",
                            "show_negative_prompt")
            self.set_values(int,
                            "max_search_results",
                            "file_actions_history_max",
                            "file_actions_window_rows_max",
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

            self.file_types = list(self.image_types)
            if self.enable_videos:
                self.file_types.extend(list(self.video_types))


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
        self.set_directories_to_search_for_related_images()
        self.check_image_edit_configuration()
        self.remove_example_h5_model_details()

        if self.print_settings:
            self.print_config_settings()

        if self.locale is None or self.locale == "":
            print(f"No locale set for config file.")
            self.locale = Utils.get_default_user_language()
        os.environ["LANG"] = self.locale

    def set_directories_to_search_for_related_images(self):
        temp_list = self.directories_to_search_for_related_images[:]
        for _dir in temp_list:
            if not os.path.isdir(_dir):
                try_dir = None
                try:
                    try_dir = self.validate_and_set_directory(key=_dir, override=True)
                except Exception as e:
                    pass
                if try_dir is None:
                    print(f"Invalid directory to search for related images: {_dir}")
                    self.directories_to_search_for_related_images.remove(_dir)
                else:
                    self.directories_to_search_for_related_images[
                        self.directories_to_search_for_related_images.index(_dir)
                    ] = try_dir

    def check_image_edit_configuration(self):
        if not "image_edit_configuration" in self.dict or not type(self.dict["image_edit_configuration"] == dict):
            print("Image edit configuration not found or invalid, using default values.")
        else:   
            self.image_edit_configuration.set_from_dict(self.dict["image_edit_configuration"])

    def remove_example_h5_model_details(self):
        for i in range(len(self.image_classifier_h5_models)):
            model_details = self.image_classifier_h5_models[i]
            if "(be sure to change this)" in model_details["model_name"]:
                del self.image_classifier_h5_models[i]
                break

    def validate_and_set_directory(self, key, override=False):
        loc = key if override else self.dict[key]
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

    def toggle_video_mode(self):
        self.enable_videos = not self.enable_videos
        self.file_types = list(self.image_types)
        if self.enable_videos:
            self.file_types.extend(list(self.video_types))
        return self.enable_videos


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

