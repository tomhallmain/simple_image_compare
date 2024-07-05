
class AppActions:
    def __init__(self, actions={}):
        self.new_window = actions["new_window"]
        self.toast = actions["toast"]
        self.alert = actions["alert"]
        self.refresh = actions["refresh"]
        self.refocus = actions["refocus"]
        self.set_mode = actions["set_mode"]
        self.create_image = actions["create_image"]
        self.show_next_image = actions["show_next_image"]
        self.set_base_dir = actions["set_base_dir"]
        self.get_base_dir = actions["get_base_dir"]
        self.go_to_file = actions["go_to_file"]
        self.delete = actions["delete"]
        self.open_move_marks_window = actions["open_move_marks_window"]
        self._add_buttons_for_mode = actions["_add_buttons_for_mode"]
        self._set_label_state = actions["_set_label_state"]
        self._set_toggled_view_matches = actions["_set_toggled_view_matches"]
        self.image_details_window = None