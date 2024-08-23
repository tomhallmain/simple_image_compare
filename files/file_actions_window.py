from tkinter import Frame, Label, filedialog, messagebox, LEFT, W
from tkinter.ttk import Button

from utils.app_info_cache import app_info_cache
from utils.app_style import AppStyle
from utils.utils import Utils



class Action():
    def __init__(self, action, target, marks=[]):
        self.action = action
        self.target = target
        self.marks = marks[:]

    def get_action(self, do_flip=False):
        action = self.action
        if do_flip:
            if action == Utils.move_file:
                action = Utils.copy_file
            elif action == Utils.copy_file:
                action = Utils.move_file
        return self.action

    def set_marks(self, marks):
        self.marks = marks

    def __eq__(self, other):
        if not isinstance(other, Action):
            return False
        return self.action == other.action and self.target == other.target
    
    def __hash__(self):
        return hash((self.action, self.target))

    def __str__(self):
        return self.action.__name__ + " to " + self.target

def convert_action_from_text(action_text):
    if action_text == "move_file":
        return Utils.move_file
    elif action_text == "copy_file":
        return Utils.copy_file
    else:
        return None
#        raise Exception("Unknown action: " + action_text)

def setup_permanent_action():
    permanent_mark_target = app_info_cache.get_meta("permanent_mark_target")
    permanent_action = app_info_cache.get_meta("permanent_action")
    return Action(convert_action_from_text(permanent_action), permanent_mark_target)

def setup_hotkey_actions():
    hotkey_actions_dict = app_info_cache.get_meta("hotkey_actions", default_val={})
    assert type(hotkey_actions_dict) == dict
    hotkey_actions = {}
    for number, action in hotkey_actions_dict.items():
        hotkey_actions[int(number)] = Action(convert_action_from_text(action["action"]), action["target"])
    return hotkey_actions


class FileActionsWindow:
    '''
    Window to hold info about completed file actions.
    '''
    permanent_action = setup_permanent_action()
    hotkey_actions = setup_hotkey_actions()
    action_history = []
    MAX_ACTIONS = 50
    N_ACTIONS_CUTOFF = 30
    COL_0_WIDTH = 600

    @staticmethod
    def get_history_action(start_index=0):
        # Get a previous action that is not equivalent to the permanent action if possible.
        action = None
        seen_actions = []
        for i in range(len(FileActionsWindow.action_history)):
            action = FileActionsWindow.action_history[i]
            is_returnable_action = action != FileActionsWindow.permanent_action
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
        hotkey_actions[number] = {"action": move_func.__name__, "target": target_dir}
        app_info_cache.set_meta("hotkey_actions", hotkey_actions)


    @staticmethod
    def update_history(target_dir, move_func, marks):
        latest_action = Action(move_func, target_dir, marks)
        if len(FileActionsWindow.action_history) > 0 and \
                latest_action == FileActionsWindow.action_history[0]:
            return
        FileActionsWindow.action_history.insert(0, latest_action)
        if len(FileActionsWindow.action_history) > FileActionsWindow.MAX_ACTIONS:
            del FileActionsWindow.action_history[-1]


    def __init__(self, master, app_actions, base_dir="."):
        self.master = master
        self.is_sorted_by_embedding = False
        self.app_actions = app_actions
#        self.filter_text = ""
#        self.filtered_target_dirs = MarkedFiles.mark_target_dirs[:]

        self.label_filename_list = []
        self.label_action_list = []
        self.view_button_list = []
        self.undo_button_list = []
        self.modify_button_list = []

        self.frame = Frame(self.master)
        self.frame.grid(column=0, row=0)
        self.frame.columnconfigure(0, weight=9)
        self.frame.columnconfigure(1, weight=1)
        self.frame.columnconfigure(2, weight=1)
        self.frame.columnconfigure(3, weight=1)
        self.frame.columnconfigure(4, weight=1)

        self.frame.config(bg=AppStyle.BG_COLOR)

        self.add_action_history_widgets()

        self._label_info = Label(self.frame)
        self.add_label(self._label_info, "File Action History", row=0, wraplength=FileActionsWindow.COL_0_WIDTH)
        self.frame.after(1, lambda: self.frame.focus_force())

        # self.master.bind("<Key>", self.filter_targets)
        # self.master.bind("<Return>", self.do_action)
        self.master.bind("<Escape>", self.close_windows)
        self.master.protocol("WM_DELETE_WINDOW", self.close_windows)

    def add_action_history_widgets(self):
        row = 0
        base_col = 0
        for i in range(len(FileActionsWindow.action_history)):
            row = i+1
            action = FileActionsWindow.action_history[i]
            self._label_info = Label(self.frame)
            self.label_list.append(self._label_info)
            self.add_label(self._label_info, action.target, row=row, column=base_col, wraplength=FileActionsWindow.COL_0_WIDTH)

            move_btn = Button(self.frame, text="Move")
            self.move_btn_list.append(move_btn)
            move_btn.grid(row=row, column=base_col+1)
            def move_handler(event, self=self, target_dir=action):
                return self.move_marks_to_dir(event, target_dir)
            move_btn.bind("<Button-1>", move_handler)

            copy_btn = Button(self.frame, text="Copy")
            self.copy_btn_list.append(copy_btn)
            copy_btn.grid(row=row, column=base_col+2)
            def copy_handler(event, self=self, target_dir=action):
                return self.move_marks_to_dir(event, target_dir, move_func=Utils.copy_file)
            copy_btn.bind("<Button-1>", copy_handler)


    def close_windows(self, event=None):
        self.master.destroy()

    def add_label(self, label_ref, text, row=0, column=0, wraplength=500):
        label_ref['text'] = text
        label_ref.grid(column=column, row=row, sticky=W)
        label_ref.config(wraplength=wraplength, justify=LEFT, bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)

    def add_btn(self, button_ref_name, text, command, row=0, column=0):
        if getattr(self, button_ref_name) is None:
            button = Button(master=self.frame, text=text, command=command)
            setattr(self, button_ref_name, button)
            button # for some reason this is necessary to maintain the reference?
            button.grid(row=row, column=column)
