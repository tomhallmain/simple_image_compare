import json
import os
import shutil
import subprocess
import sys

from image.image_edit_configuration import ImageEditConfiguration
from utils.constants import CompareMode, SortBy
from utils.logging_setup import get_logger
from utils.running_tasks_registry import running_tasks_registry
from utils.utils import Utils

logger = get_logger("config")


class Config:
    CONFIGS_DIR_LOC = os.path.join(os.path.dirname(os.path.abspath(os.path.dirname(__file__))), "configs")

    def __init__(self):
        self.dict = {}
        self.locale = Utils.get_default_user_language()
        self.foreground_color = None
        self.background_color = None
        self.debug = True
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
        self.title_notify_persist_seconds = 5
        self.delete_instantly = False
        self.clear_marks_with_errors_after_move = False
        self.move_marks_overwrite_existing_file = False
        self.trash_folder = None
        self.sd_prompt_reader_loc = None
        self.siglip_enable_large_model = False
        self.xvlm_loc = None
        self.xvlm_model_loc = None
        self.xvlm_model_size = "4m"
        self.laion_enable_half_precision = False
        self.always_open_new_windows = False
        self.image_types = [".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp", ".heic", ".avif"]
        self.video_types = [".mp4", ".mkv", ".avi", ".wmv", ".mov", ".flv"]
        self.image_classifier_h5_models = []
        self.enable_videos = True
        self.enable_gifs = True
        self.enable_pdfs = False
        self.enable_svgs = False  # SVG support is disabled by default
        self.enable_html = True
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
        self._gimp_validated = False  # Cache for GIMP validation result
        self.gimp_gegl_enabled = True  # Will be overridden if GIMP 3 not available
        self.gimp_gegl_timeout = 60  # Timeout for GIMP operations in seconds
        self.gimp_gegl_temp_dir = None  # Custom temp directory for GIMP operations
        self.gimp_gegl_auto_cleanup = True  # Automatically clean up temporary files
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
            logger.error(e)
            logger.error("Unable to load config. Ensure config.json file is located in the configs directory of simple-image-comare.")

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
                            "xvlm_loc",
                            "xvlm_model_loc",
                            "xvlm_model_size",
                            "gimp_exe_loc")
            self.set_values(bool,
                            "image_browse_recursive",
                            "image_tagging_enabled",
                            "escape_backslash_filepaths",
                            "fill_canvas",
                            "enable_videos",
                            "enable_gifs",
                            "enable_pdfs",
                            "enable_svgs",
                            "enable_html",
                            "print_settings",
                            "show_toasts",
                            "delete_instantly",
                            "clear_marks_with_errors_after_move",
                            "move_marks_overwrite_existing_file",
                            "siglip_enable_large_model",
                            "laion_enable_half_precision",
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
                            "title_notify_persist_seconds",
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
            if self.enable_gifs:
                self.file_types.append(".gif")
            if self.enable_pdfs:
                self.file_types.append(".pdf")
            if self.enable_svgs:
                self.file_types.append(".svg")
            if self.enable_html:
                self.file_types.extend([".html", ".htm"])

            try:
                self.sd_prompt_reader_loc = self.validate_and_set_directory(key="sd_prompt_reader_loc")
            except Exception as e:
                logger.error(e)

            try:
                self.compare_mode = CompareMode[self.dict["compare_mode"]]
            except Exception:
                raise AssertionError("Invalid compare mode for compare_mode config setting. Must be one of CLIP_EMBEDDING, COLOR_MATCHING")

            try:
                self.sort_by = SortBy[self.dict["sort_by"]]
            except Exception:
                raise AssertionError("Invalid sort type for sort_by config setting. Must be one of NAME, FULL_PATH, CREATION_TIME, TYPE")

        self.set_directories_to_search_for_related_images()
        self.check_image_edit_configuration()
        self.remove_example_h5_model_details()
        
        # GIMP and GEGL availability will be checked lazily when first needed

        if self.print_settings:
            self.print_config_settings()

        if self.locale is None or self.locale == "":
            logger.info(f"No locale set for config file.")
            self.locale = Utils.get_default_user_language()
        os.environ["LANG"] = self.locale

    def validate_and_find_gimp(self):
        """Validate the configured GIMP installation and auto-detect if needed."""
        if self._gimp_validated:
            return  # Already validated in this session
        
        if self.gimp_exe_loc and self.gimp_exe_loc.strip():
            # Check if the configured GIMP path is valid
            if self._is_valid_gimp_installation(self.gimp_exe_loc):
                logger.info(f"Using configured GIMP installation: {self.gimp_exe_loc}")
                # Check if it's GIMP 3+ for GEGL support
                self._check_gimp_version_for_gegl()
                self._gimp_validated = True
                return
        
        # If no valid GIMP found in config, try to auto-detect
        detected_gimp = self._find_gimp_installation()
        self.gimp_exe_loc = detected_gimp # Will be None if no valid GIMP installation is found
        if detected_gimp:
            logger.info(f"Auto-detected GIMP installation: {self.gimp_exe_loc}")
            # Check if it's GIMP 3+ for GEGL support
            self._check_gimp_version_for_gegl()
            self._gimp_validated = True
        else:
            logger.warning("No valid GIMP installation found. GIMP integration will not be available.")
            logger.info("To enable GIMP integration, set 'gimp_exe_loc' in your config.json file.")
            # No GIMP found, disable GEGL
            self.gimp_gegl_enabled = False
            self._gimp_validated = True

    def _is_valid_gimp_installation(self, gimp_path):
        """Check if a GIMP installation is valid and executable."""
        try:
            # Handle both full paths and executable names
            if os.path.isfile(gimp_path):
                # Full path provided
                executable_path = gimp_path
            else:
                # Just executable name, check if it's in PATH
                executable_path = shutil.which(gimp_path)
                if not executable_path:
                    return False
            
            # Test if the executable can be run (version check)
            result = subprocess.run([executable_path, "--version"], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and "GNU Image Manipulation Program" in result.stdout:
                logger.debug("GIMP validation successful")
                return True
            else:
                logger.debug("GIMP validation failed - return code or output check failed")
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
            logger.debug(f"GIMP validation exception: {type(e).__name__}: {e}")
        return False

    def _find_gimp_installation(self):
        """Auto-detect GIMP installation on the current platform."""
        if sys.platform == 'win32':
            return self._find_gimp_windows()
        else:
            return self._find_gimp_unix()

    def _find_gimp_windows(self):
        """Find GIMP installation on Windows."""
        possible_paths = []
        program_dirs = [r"C:\Program Files", r"C:\Program Files (x86)"]
        # GIMP major versions to check (prioritize newer versions)
        gimp_major_versions = ["3", "2"]  # GIMP 3.x first, then 2.x
        # GIMP minor versions to check (in order of preference)
        gimp_minor_versions = {
            "2": ["10", "9", "8", "7", "6", "5", "4", "3", "2", "1", "0"],  # GIMP 2.x versions
            "3": ["2", "1", "0"]    # GIMP 3.x versions
        }
        
        for program_dir in program_dirs:
            if not os.path.exists(program_dir):
                continue
            for major_ver in gimp_major_versions:
                for minor_ver in gimp_minor_versions[major_ver]:
                    gimp_dir = f"GIMP {major_ver}"
                    bin_path = os.path.join(program_dir, gimp_dir, "bin", f"gimp-{major_ver}.{minor_ver}.exe")
                    if os.path.exists(bin_path):
                        possible_paths.append(bin_path)
                    else:
                        logger.debug(f"GIMP executable not found: {bin_path}")

        if possible_paths:
            logger.debug(f"Found {len(possible_paths)} possible GIMP paths: {possible_paths}")
        else:
            logger.debug("No possible GIMP paths found")
            
        for path in possible_paths:
            if self._is_valid_gimp_installation(path):
                logger.debug(f"Valid GIMP installation found: {path}")
                return path
            else:
                logger.debug(f"Invalid GIMP installation: {path}")
        return None

    def _find_gimp_unix(self):
        """Find GIMP installation on Unix-like systems."""
        # Common GIMP executable names
        gimp_names = ["gimp-2.10", "gimp-2.8", "gimp-3.0", "gimp-3.2", "gimp"]
        
        for name in gimp_names:
            if self._is_valid_gimp_installation(name):
                return name
        
        return None

    def _check_gimp_version_for_gegl(self):
        """Check if the current GIMP installation supports GEGL (requires GIMP 3+)."""
        try:
            if self._is_gimp_3_or_later(self.gimp_exe_loc):
                logger.debug("GIMP 3+ detected, GEGL operations enabled")
                # GEGL is already enabled by default, no need to change
            else:
                logger.warning("GIMP 2.x or lower detected, disabling GEGL operations (requires GIMP 3+)")
                self.gimp_gegl_enabled = False
        except Exception as e:
            logger.warning(f"Error checking GIMP version: {e}")
            logger.info("Disabling GEGL operations due to error")
            self.gimp_gegl_enabled = False

    def _is_gimp_3_or_later(self, gimp_path):
        """Check if the GIMP installation is version 3.0 or later."""
        try:
            # Handle both full paths and executable names
            if os.path.isfile(gimp_path):
                executable_path = gimp_path
            else:
                executable_path = shutil.which(gimp_path)
                if not executable_path:
                    return False
            
            # Test if the executable can be run (version check)
            result = subprocess.run([executable_path, "--version"], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                return False
            
            # Check version in output
            version_output = result.stdout
            if "GNU Image Manipulation Program" not in version_output:
                return False
            
            # Look for version 3.x or later
            import re
            # Try multiple patterns to handle different GIMP version output formats
            patterns = [
                r'GIMP\s+(\d+)\.(\d+)',  # "GIMP 3.0.4"
                r'Version\s+(\d+)\.(\d+)',  # "Version 3.0.4"
                r'GNU Image Manipulation Program.*?(\d+)\.(\d+)',  # "GNU Image Manipulation Program Version 3.0.4"
            ]
            
            version_match = None
            for pattern in patterns:
                version_match = re.search(pattern, version_output)
                if version_match:
                    break
            
            if version_match:
                major_version = int(version_match.group(1))
                minor_version = int(version_match.group(2))
                logger.debug(f"Parsed GIMP version: {major_version}.{minor_version}")
                if major_version >= 3:
                    return True
                elif major_version == 2 and minor_version >= 99:  # GIMP 2.99 is development version of 3.0
                    return True
            else:
                logger.debug(f"No version match found in GIMP output: {repr(version_output)}")
            
            return False
            
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError, OSError, ValueError):
            return False

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
                    logger.info(f"Invalid directory to search for related images: {_dir}")
                    self.directories_to_search_for_related_images.remove(_dir)
                else:
                    self.directories_to_search_for_related_images[
                        self.directories_to_search_for_related_images.index(_dir)
                    ] = try_dir

    def check_image_edit_configuration(self):
        if not "image_edit_configuration" in self.dict or not type(self.dict["image_edit_configuration"] == dict):
            logger.info("Image edit configuration not found or invalid, using default values.")
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
                    if self.dict[name] is not None:
                        setattr(self, name, type(self.dict[name]))
                except Exception as e:
                    logger.error(e)
                    logger.warning(f"Failed to set {name} from config.json file. Ensure the value is set and of the correct type.")
            else:
                try:
                    setattr(self, name, self.dict[name])
                except Exception as e:
                    logger.error(e)
                    logger.warning(f"Failed to set {name} from config.json file. Ensure the key is set.")

    def next_text_embedding_search_preset(self):
        self.text_embedding_search_preset_index += 1
        if self.text_embedding_search_preset_index >= len(self.text_embedding_search_presets):
            self.text_embedding_search_preset_index = 0
        if self.text_embedding_search_preset_index >= len(self.text_embedding_search_presets):
            return None
        else:
            return self.text_embedding_search_presets[self.text_embedding_search_preset_index]


    def print_config_settings(self):
        logger.info("Settings active:")
        extra_text = ": False - NO toasts will be shown!" if not self.show_toasts else ""
        logger.info(f" - Show toasts{extra_text}")
        if self.delete_instantly:
            logger.info(f" - Files will be deleted instantly, not sent to trash")
        if self.trash_folder:
            logger.info(f" - Trash folder: {self.trash_folder}")
        if self.escape_backslash_filepaths:
            logger.info(f" - Escape backslashes in filepaths when copying")
        if self.fill_canvas:
            logger.info(f" - Expand images to fill canvas")
        if self.image_browse_recursive:
            logger.info(f" - Recursive file browsing")
        if self.sd_prompt_reader_loc is not None:
            logger.info(f" - Using stable diffusion prompt reader path at {self.sd_prompt_reader_loc}")
        else:
            logger.info(f" - Stable diffusion prompt reader location is not set or invalid.")
        if self.gimp_exe_loc:
            logger.info(f" - Using GIMP installation: {self.gimp_exe_loc}")
        else:
            logger.info(f" - GIMP integration: Not found")
        logger.info(f" - Max files per compare: {self.file_counter_limit}")

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

