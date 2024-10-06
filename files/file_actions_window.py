from enum import Enum
import os

from tkinter import Toplevel, Label, LEFT, W
from tkinter.ttk import Button

from utils.config import config
from lib.tk_scroll_demo import ScrollFrame
from utils.app_info_cache import app_info_cache
from utils.app_style import AppStyle
from utils.utils import Utils, ModifierKey
from utils.translations import I18N

_ = I18N._


class Action():
    def __init__(self, action, target, original_marks=[], new_files=[], auto=False):
        self.action = action
        self.target = target
        self.original_marks = original_marks[:]
        self.new_files = new_files[:]
        self.auto = auto

    def add_file(self, file):
        self.new_files.append(file)

    def get_original_directory(self):
        if len(self.original_marks) == 0:
            raise Exception("No original marks")
        return os.path.dirname(os.path.abspath(self.original_marks[-1]))

    def is_move_action(self):
        return self.action.__name__.startswith("move")

    def any_new_files_exist(self):
        for file in self.new_files:
            if os.path.exists(file):
                return True
        return False

    def remove_new_files(self):
        for f in self.new_files[:]:
            try:
                os.remove(f)
            except Exception as e:
                print(e)

    def get_action(self, do_flip=False):
        action = self.action
        if do_flip:
            if action == Utils.move_file:
                action = Utils.copy_file
            elif action == Utils.copy_file:
                action = Utils.move_file
        return self.action
    
    def to_dict(self):
        return {
            "action": Action.convert_action_to_text(self.action),
            "target": self.target,
            "original_marks": self.original_marks[:],
            "new_files": self.new_files[:]
            }

    @staticmethod
    def from_dict(dct):
        return Action(Action.convert_action_from_text(dct["action"]),
                      dct["target"], dct["original_marks"][:], dct["new_files"][:],
                      dct["auto"] if "auto" in dct else False)

    def __eq__(self, other):
        if not isinstance(other, Action):
            return False
        return self.action == other.action and self.target == other.target
    
    def __hash__(self):
        return hash((self.action, self.target))

    def __str__(self):
        return self.action.__name__ + " to " + self.target

    @staticmethod
    def convert_action_from_text(action_text):
        if action_text == "move_file":
            return Utils.move_file
        elif action_text == "copy_file":
            return Utils.copy_file
        else:
            return None

    @staticmethod
    def convert_action_to_text(action_func):
        if action_func == Utils.move_file:
            return "move_file"
        elif action_func == Utils.copy_file:
            return "copy_file"
        else:
            return None

    @staticmethod
    def _is_matching_action_in_list(action_list, action):
        for _action in action_list:
            if action == _action:
                if len(action.new_files) != len(_action.new_files):
                    continue
                if tuple(action.new_files) == tuple(_action.new_files):
                    return True
        return False

def setup_permanent_action():
    permanent_mark_target = app_info_cache.get_meta("permanent_mark_target")
    permanent_action = app_info_cache.get_meta("permanent_action")
    return Action(Action.convert_action_from_text(permanent_action), permanent_mark_target)

def setup_hotkey_actions():
    hotkey_actions_dict = app_info_cache.get_meta("hotkey_actions", default_val={})
    assert type(hotkey_actions_dict) == dict
    hotkey_actions = {}
    for number, action in hotkey_actions_dict.items():
        hotkey_actions[int(number)] = Action(Action.convert_action_from_text(action["action"]), action["target"])
    return hotkey_actions


class FileActionsWindow:
    '''
    Window to hold info about completed file actions.
    '''
    top_level = None
    permanent_action = setup_permanent_action()
    hotkey_actions = setup_hotkey_actions()
    action_history = []
    MAX_ACTIONS = config.file_actions_history_max
    MAX_ACTION_ROWS = config.file_actions_window_rows_max
    COL_0_WIDTH = 600

    @staticmethod
    def store_action_history():
        action_dicts = []
        for action in FileActionsWindow.action_history:
            action_dicts.append(action.to_dict())
        app_info_cache.set_meta("file_actions", action_dicts)
    
    @staticmethod
    def load_action_history():
        action_history_dicts = app_info_cache.get_meta("file_actions", default_val=[])
        for action_dict in action_history_dicts:
            FileActionsWindow.action_history.append(Action.from_dict(action_dict))

    @staticmethod
    def get_history_action(start_index=0, exclude_auto=True):
        # Get a previous action that is not equivalent to the permanent action if possible.
        action = None
        seen_actions = []
        for i in range(len(FileActionsWindow.action_history)):
            action = FileActionsWindow.action_history[i]
            is_returnable_action = action != FileActionsWindow.permanent_action and not (exclude_auto and action.auto)
            if not is_returnable_action or action in seen_actions:
                start_index += 1
            seen_actions.append(action)
#            print(f"i={i}, start_index={start_index}, action={action}")
            if i < start_index:
                continue
            if is_returnable_action:
                break
        return action


    @staticmethod
    def set_permanent_action(target_dir, move_func, toast_callback):
        FileActionsWindow.permanent_action = Action(move_func, target_dir)
        app_info_cache.set_meta("permanent_action", move_func.__name__)
        app_info_cache.set_meta("permanent_mark_target", target_dir)
        toast_callback(f"Set permanent action:\n{move_func.__name__} to {target_dir}")


    @staticmethod
    def set_hotkey_action(number, target_dir, move_func, toast_callback):
        FileActionsWindow.hotkey_actions[number] = Action(move_func, target_dir)
        hotkey_actions = app_info_cache.get_meta("hotkey_actions", default_val={})
        assert type(hotkey_actions) == dict
        hotkey_actions[number] = {"action": move_func.__name__, "target": target_dir}
        app_info_cache.set_meta("hotkey_actions", hotkey_actions)


    @staticmethod
    def update_history(latest_action):
        FileActionsWindow.action_history.insert(0, latest_action)
        if len(FileActionsWindow.action_history) > FileActionsWindow.MAX_ACTIONS:
            del FileActionsWindow.action_history[-1]

    @staticmethod
    def add_file_action(action, source, target, auto=True):
        new_filepath = str(action(source, target))
        print("Moved file to " + new_filepath)
        new_action = Action(action, target, [source], [new_filepath], auto)
        FileActionsWindow.update_history(new_action)

    def __init__(self, app_master, app_actions, view_image_callback, move_marks_callback, geometry="700x1200"):
        FileActionsWindow.top_level = Toplevel(app_master, bg=AppStyle.BG_COLOR)
        FileActionsWindow.top_level.title(_("File Actions"))
        FileActionsWindow.top_level.geometry(geometry)
        self.master = FileActionsWindow.top_level
        self.app_master = app_master
        self.is_sorted_by_embedding = False
        self.app_actions = app_actions
        self.view_image_callback = view_image_callback
        self.move_marks_callback = move_marks_callback
        self.filter_text = ""
        self.filtered_action_history = FileActionsWindow.action_history[:]
        self.button_index = -1

        self.label_filename_list = []
        self.label_action_list = []
        self.view_btn_list = []
        self.undo_btn_list = []
        self.modify_btn_list = []

        self.frame = ScrollFrame(self.master, bg_color=AppStyle.BG_COLOR)
        self.frame.pack(side="top", fill="both", expand=True)

        self._label_info = Label(self.frame.viewPort)
        self.add_label(self._label_info, _("File Action History"), row=0, wraplength=FileActionsWindow.COL_0_WIDTH)
        self.search_for_active_image_btn = None
        self.add_btn("search_for_active_image_btn", _("Search Image"), self.search_for_active_image, column=1)
        self.clear_action_history_btn = None
        self.add_btn("clear_action_history_btn", _("Clear History"), self.clear_action_history, column=2)

        self.add_action_history_widgets()

        self.master.bind("<Key>", self.filter_targets)
        self.master.bind("<Return>", self.do_action)
        self.master.bind("<Escape>", self.close_windows)
        self.master.bind("<Shift-A>", self.search_for_active_image)
        self.master.protocol("WM_DELETE_WINDOW", self.close_windows)
        self.frame.after(1, lambda: self.frame.focus_force())

    def add_action_history_widgets(self):
        row = 0
        base_col = 0
        last_action = None
        for i in range(len(self.filtered_action_history)):
            row += 1
            if row > FileActionsWindow.MAX_ACTION_ROWS:
                break
            action = self.filtered_action_history[i]
            if action != last_action or len(action.new_files) != 1 or \
                    (last_action is not None and len(last_action.new_files) != 1):
                _label_target_dir = Label(self.frame.viewPort)
                self.label_filename_list.append(_label_target_dir)
                action_text = Utils.get_relative_dirpath(action.target, levels=2)
                if len(action.new_files) > 1:
                    action_text += _(" ({0} files)").format(len(action.new_files))
                self.add_label(_label_target_dir, action_text, row=row, column=base_col, wraplength=FileActionsWindow.COL_0_WIDTH)

                _label_action = Label(self.frame.viewPort)
                self.label_action_list.append(_label_action)
                action_text = _("Move") if action.is_move_action() else _("Copy")
                self.add_label(_label_action, action_text, row=row, column=base_col+1, wraplength=FileActionsWindow.COL_0_WIDTH)

                undo_btn = Button(self.frame.viewPort, text=_("Undo"))
                self.undo_btn_list.append(undo_btn)
                undo_btn.grid(row=row, column=base_col+3)
                def undo_handler(event, self=self, action=action):
                    return self.undo(event, action)
                undo_btn.bind("<Button-1>", undo_handler)
                undo_btn.bind("<Return>", undo_handler)

                modify_btn = Button(self.frame.viewPort, text=_("Modify"))
                self.modify_btn_list.append(modify_btn)
                modify_btn.grid(row=row, column=base_col+4)
                def modify_handler(event, self=self, action=action):
                    return self.modify(event, action)
                modify_btn.bind("<Button-1>", modify_handler)
                modify_btn.bind("<Return>", modify_handler)
            else:
                row -= 1

            last_action = action

            for filename in action.new_files:
                row += 1
                if row > FileActionsWindow.MAX_ACTION_ROWS:
                    break
                _label_filename = Label(self.frame.viewPort)
                self.label_filename_list.append(_label_filename)
                filename_text = os.path.basename(filename)
                if len(filename_text) > 50:
                    filename_text = Utils.get_centrally_truncated_string(filename_text, 50)
                self.add_label(_label_filename, filename_text, row=row, column=base_col, wraplength=FileActionsWindow.COL_0_WIDTH)

                # _label_action = Label(self.frame.viewPort)
                # self.label_action_list.append(_label_action)
                # self.add_label(_label_action, action.action.__name__, row=row, column=base_col+1, wraplength=FileActionsWindow.COL_0_WIDTH)

                view_btn = Button(self.frame.viewPort, text=_("View"))
                self.view_btn_list.append(view_btn)
                view_btn.grid(row=row, column=base_col+2)
                def view_handler(event, self=self, image_path=filename):
                    return self.view(event, image_path)
                view_btn.bind("<Button-1>", view_handler)
                view_btn.bind("<Return>", view_handler)

                undo_btn = Button(self.frame.viewPort, text=_("Undo"))
                self.undo_btn_list.append(undo_btn)
                undo_btn.grid(row=row, column=base_col+3)
                def undo_handler1(event, self=self, image_path=filename, action=action):
                    return self.undo(event, action, specific_image=image_path)
                undo_btn.bind("<Button-1>", undo_handler1)
                undo_btn.bind("<Return>", undo_handler1)

                modify_btn = Button(self.frame.viewPort, text=_("Modify"))
                self.modify_btn_list.append(modify_btn)
                modify_btn.grid(row=row, column=base_col+4)
                def modify_handler1(event, self=self, image_path=filename):
                    return self.modify(event, image_path)
                modify_btn.bind("<Button-1>", modify_handler1)
                modify_btn.bind("<Return>", modify_handler1)

    def close_windows(self, event=None):
        self.master.destroy()

    def view(self, event, image_path):
        self.view_image_callback(master=self.app_master, image_path=image_path, app_actions=self.app_actions)

    def undo(self, event, action, specific_image=None):
        if specific_image is not None:
            if not os.path.isfile(specific_image):
                error_text = _("Image does not exist: ") + specific_image
                self.app_actions.alert(_("File Action Error"), error_text)
                raise Exception(error_text)
            if action.is_move_action():
                original_directory = action.get_original_directory()
                self.move_marks_callback(self.app_actions, target_dir=original_directory,
                                         move_func=Utils.move_file, files=[specific_image], single_image=True)
            else:
                os.remove(specific_image)
        else:
            if not action.any_new_files_exist():
                error_text = _("Images not found")
                self.app_actions.alert(_("File Action Error"), error_text)
                raise Exception(error_text)
            if action.is_move_action():
                original_directory = action.get_original_directory()
                self.move_marks_callback(self.app_actions, target_dir=original_directory,
                                         move_func=Utils.move_file, files=action.new_files,
                                         single_image=(len(action.new_files) == 1))
            else:
                action.remove_new_files()


    def modify(self, event, image_path_or_action):
        # TODO implement this
        if isinstance(image_path_or_action, str):
            pass
        else:
#            MarkedFileMover.undo_move_marks()
            pass

    def _refresh_widgets(self):
        self.clear_widget_lists()
        self.add_action_history_widgets()
        self.master.update()

    def clear_widget_lists(self):
        for label in self.label_filename_list:
            label.destroy()
        for label in self.label_action_list:
            label.destroy()
        for btn in self.view_btn_list:
            btn.destroy()
        for btn in self.undo_btn_list:
            btn.destroy()
        for btn in self.modify_btn_list:
            btn.destroy()
        self.label_filename_list = []
        self.label_action_list = []
        self.view_btn_list = []
        self.undo_btn_list = []
        self.modify_btn_list = []

    def _get_paging_length(self):
        return max(1, int(len(self.filtered_action_history) / 10))

    def page_up(self, event=None):
        paging_len = self._get_paging_length()
        idx = len(self.filtered_action_history) - paging_len
        self.filtered_action_history = self.filtered_action_history[idx:] + self.filtered_action_history[:idx]
        self._refresh_widgets()

    def page_down(self, event=None):
        paging_len = self._get_paging_length()
        self.filtered_action_history = self.filtered_action_history[paging_len:] + self.filtered_action_history[:paging_len]
        self._refresh_widgets()

    def filter_targets(self, event):
        """
        Rebuild the filtered target directories list based on the filter string and update the UI.
        """
        modifier_key_pressed = (event.state & 0x1) != 0 or (event.state & 0x4) != 0 # Do not filter if modifier key is down
        if modifier_key_pressed:
            return
        if len(event.keysym) > 1:
            if event.keysym != "BackSpace":
                return
        if event.keysym == "BackSpace":
            if len(self.filter_text) > 0:
                self.filter_text = self.filter_text[:-1]
        elif event.char:
            self.filter_text += event.char
        else:
            return
        if self.filter_text.strip() == "":
            if config.debug:
                Utils.log_debug("Filter unset")
            # Restore the list of target directories to the full list
            self.filtered_action_history.clear()
            self.filtered_action_history = FileActionsWindow.action_history[:]
        else:
            temp = []
            # First pass try to match directory basename
            for action in FileActionsWindow.action_history:
                basename = os.path.basename(os.path.normpath(action.target))
                if basename.lower() == self.filter_text:
                    temp.append(action)
            for action in FileActionsWindow.action_history:
                if not Action._is_matching_action_in_list(temp, action):
                    basename = os.path.basename(os.path.normpath(action.target))
                    if basename.lower().startswith(self.filter_text):
                        temp.append(action)
            # Second pass try to match parent directory name, so these will appear after
            for action in FileActionsWindow.action_history:
                if not Action._is_matching_action_in_list(temp, action):
                    dirname = os.path.basename(os.path.dirname(os.path.normpath(action.target)))
                    if dirname and dirname.lower().startswith(self.filter_text):
                        temp.append(action)
            # Third pass try to match part of the basename
            for action in FileActionsWindow.action_history:
                if not Action._is_matching_action_in_list(temp, action):
                    basename = os.path.basename(os.path.normpath(action.target))
                    if basename and (f" {self.filter_text}" in basename.lower() or f"_{self.filter_text}" in basename.lower()):
                        temp.append(action)
            self.filtered_action_history = temp[:]

        self._refresh_widgets()

    def do_action(self, event):
        """
        The user has requested to do something with the saved file actions. Based on the context, figure out what to do.

        If no actions present, do nothing.

        If actions set, open the image of the first action.

        If shift key pressed, undo the first action.

        If control key pressed, modify the first action.

        If alt key pressed, use the penultimate mark target dir as target directory.

        The idea is the user can filter the actions using keypresses, then press enter to
        do the action on the first filtered action.
        """
        shift_key_pressed, control_key_pressed, alt_key_pressed = Utils.modifier_key_pressed(
            event, keys_to_check=[ModifierKey.SHIFT, ModifierKey.CTRL, ModifierKey.ALT])
        move_func = Utils.copy_file if shift_key_pressed else Utils.move_file
        if len(self.filtered_action_history) == 0:
            return
        if len(self.filtered_action_history) != 1 and self.filter_text.strip() == "":
            return
        action = self.filtered_action_history[0]
        if alt_key_pressed:
            self.undo(event=None, action=action)
        elif control_key_pressed:
            self.modify(event=None, image_path_or_action=action)
        else:
            self.view(event=None, image_path=action.new_files[0])

    def search_for_active_image(self, event=None):
        self._search_for_image(event=event)

    def _search_for_image(self, event=None, image_path=None):
        if image_path is None:
            image_path = self.app_actions.get_active_image_filepath()
            if image_path is None:
                raise Exception("No active image")
        image_path = os.path.normpath(image_path)
        search_basename = os.path.basename(image_path).lower()
        basename_no_ext = os.path.splitext(search_basename)[0].lower()
        temp = []
        for action in FileActionsWindow.action_history:
            for f in action.new_files:
                if f == image_path:
                    temp.append(action)
                    break
        for action in FileActionsWindow.action_history:
            if action not in temp:
                for f in action.new_files:
                    basename = os.path.basename(os.path.normpath(f))
                    if basename.lower() == search_basename:
                        temp.append(action)
                        break
        for action in FileActionsWindow.action_history:
            if action not in temp:
                for f in action.new_files:
                    basename = os.path.basename(os.path.normpath(f))
                    if basename.lower().startswith(basename_no_ext):
                        temp.append(action)
                        break
        self.filtered_action_history = temp[:]
        self._refresh_widgets()

    def clear_action_history(self):
        FileActionsWindow.action_history = []
        self.filtered_action_history = []
        self._refresh_widgets()

    def add_label(self, label_ref, text, row=0, column=0, wraplength=500):
        label_ref['text'] = text
        label_ref.grid(column=column, row=row, sticky=W)
        label_ref.config(wraplength=wraplength, justify=LEFT, bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)

    def add_btn(self, button_ref_name, text, command, row=0, column=0):
        if getattr(self, button_ref_name) is None:
            button = Button(master=self.frame.viewPort, text=text, command=command)
            setattr(self, button_ref_name, button)
            button # for some reason this is necessary to maintain the reference?
            button.grid(row=row, column=column)
