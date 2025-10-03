

from tkinter import Toplevel, Frame, Label, filedialog, messagebox, LEFT, W
from tkinter.ttk import Button

from auth.password_utils import require_password
from files.file_actions_window import FileActionsWindow
from utils.app_style import AppStyle
from utils.constants import ProtectedActions
from utils.translations import I18N

_ = I18N._

class HotkeyActionsWindow():
    top_level = None
    MAX_HEIGHT = 900
    COL_1_WIDTH = 600

    @staticmethod
    def get_geometry():
        width = 600
        height = 400
        return f"{width}x{height}"

    def __init__(self, master, app_actions, set_permanent_action_callback, set_hotkey_action_callback):
        HotkeyActionsWindow.top_level = Toplevel(master, bg=AppStyle.BG_COLOR)
        HotkeyActionsWindow.top_level.title(_("Hotkey Actions"))
        HotkeyActionsWindow.top_level.geometry(HotkeyActionsWindow.get_geometry())
        self.master = HotkeyActionsWindow.top_level
        self.app_actions = app_actions
        self.set_permanent_action_callback = set_permanent_action_callback
        self.set_hotkey_action_callback = set_hotkey_action_callback

        self.do_set_permanent_mark_target = False
        self.do_set_hotkey_action = -1
        self.label_list = []
        self.dir_label_list = []
        self.manual_set_btn_list = []

        self.frame = Frame(self.master)
        self.frame.grid(column=0, row=0)
        self.frame.columnconfigure(0, weight=1)
        self.frame.columnconfigure(1, weight=8)
        self.frame.columnconfigure(2, weight=1)

        self.frame.config(bg=AppStyle.BG_COLOR)

        row = 0
        self.label_key_name = Label(self.frame)
        self.label_list.append(self.label_key_name)
        self.add_label(self.label_key_name, _("Key name"), row=row, column=0, wraplength=200)

        self.label_target_dir = Label(self.frame)
        self.dir_label_list.append(self.label_target_dir)
        self.add_label(self.label_target_dir, _("Target directory"), row=row, column=1, wraplength=HotkeyActionsWindow.COL_1_WIDTH)

        self.add_hotkey_action_widget("T", is_index=False, override_row=2)

        for i in range(1, 10, 1):
            self.add_hotkey_action_widget(i)

        self.add_hotkey_action_widget(0, override_row=12) 

        self.frame.after(1, lambda: self.frame.focus_force())

        self.master.bind("<Escape>", lambda e: self.close_windows)
        self.master.bind(f"Shift-T", self.set_hotkey_action)
        for i in range(10):
            self.master.bind(f"{i}", self.set_hotkey_action)

    def add_hotkey_action_widget(self, key=-1, is_index=True, override_row=-1):
        key_index = key
        if is_index:
            key_index = int(key)
        row = 0
        base_col = 0
        row = key + 2 if is_index and override_row == -1 else override_row
        hotkey_name = f"Shift-{key_index}"
        _label_info = Label(self.frame)
        self.label_list.append(_label_info)
        self.add_label(_label_info, hotkey_name, row=row, column=base_col, wraplength=200)

        if is_index:
            if key_index in FileActionsWindow.hotkey_actions:
                action = FileActionsWindow.hotkey_actions[key_index]
            else:
                action = _("(unset)")
        else:
            if FileActionsWindow.permanent_action is not None:
                action  = FileActionsWindow.permanent_action
            else:
                action  = _("(unset)")
        _label_target_dir = Label(self.frame)
        self.dir_label_list.append(_label_target_dir)
        self.add_label(_label_target_dir, action, row=row, column=base_col+1, wraplength=HotkeyActionsWindow.COL_1_WIDTH)

        set_btn = Button(self.frame, text=_("Set"))
        self.manual_set_btn_list.append(set_btn)
        set_btn.grid(row=row, column=base_col+2)
        def set_handler(event, self=self, hotkey=key):
            self._protected_set_hotkey_action(hotkey, key_index)
        set_btn.bind("<Button-1>", set_handler)

    @require_password(ProtectedActions.SET_HOTKEY_ACTIONS)
    def _protected_set_hotkey_action(self, hotkey, key_index):
        if hotkey == "T":
            self.set_permanent_action_callback()
        else:
            self.set_hotkey_action_callback(hotkey_override=key_index)

    @require_password(ProtectedActions.SET_HOTKEY_ACTIONS)
    def set_hotkey_action(self, event):
        if event.keysym == "T":
            self.set_permanent_action_callback()
        else:
            self.set_hotkey_action_callback(event)

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
            button  # for some reason this is necessary to maintain the reference?
            button.grid(row=row, column=column)
