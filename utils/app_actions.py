from typing import Callable, Dict, Any

class AppActions:
    REQUIRED_ACTIONS = {
        "new_window", "get_window", "toast", "alert", "refresh",
        "refocus", "set_mode", "get_active_media_filepath",
        "create_image", "show_next_media", "get_media_details",
        "run_image_generation", "set_marks_from_downstream_related_images",
        "set_base_dir", "get_base_dir", "go_to_file", "delete",
        "hide_current_media", "copy_media_path", "open_move_marks_window",
        "open_password_admin_window", "release_media_canvas", "store_info_cache", 
        "_add_buttons_for_mode", "_set_label_state",
        "_set_toggled_view_matches", "refresh_all_compares",
    }
    
    def __init__(self, actions: Dict[str, Callable[..., Any]]):
        missing = self.REQUIRED_ACTIONS - set(actions.keys())
        if missing:
            raise ValueError(f"Missing required actions: {missing}")
        self._actions = actions
    
    def __getattr__(self, name):
        if name in self._actions:
            return self._actions[name]
        raise AttributeError(f"Action '{name}' not found")

    def image_details_window(self):
        return self._actions.get("_image_details_window")
    
    def set_image_details_window(self, image_details_window):
        self._actions["_image_details_window"] = image_details_window
