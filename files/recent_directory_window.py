import os

from tkinter import Frame, Label, filedialog, messagebox, LEFT, W
from tkinter.ttk import Button

from utils.app_info_cache import app_info_cache
from utils.app_style import AppStyle
from utils.config import config
from utils.translations import I18N
from utils.utils import ModifierKey, Utils
from utils.logging_setup import get_logger

logger = get_logger("recent_directory_window")

_ = I18N._


class RecentDirectories:
    directories = []
    MAX_RECENT_DIRECTORIES = 100

    @staticmethod
    def store_recent_directories():
        app_info_cache.set_meta("recent_directories", RecentDirectories.directories)

    @staticmethod
    def load_recent_directories():
        dirs = app_info_cache.get_meta("recent_directories", default_val=[])
        if not isinstance(dirs, list):
            dirs = []
        # Filter out any paths that are no longer valid directories
        filtered_dirs = [os.path.normpath(d) for d in dirs if isinstance(d, str) and os.path.isdir(d)]
        RecentDirectories.directories = filtered_dirs
        # Persist the filtered list back into the cache so stale entries are removed
        if filtered_dirs != dirs:
            app_info_cache.set_meta("recent_directories", filtered_dirs)

    @staticmethod
    def set_recent_directories(directories):
        RecentDirectories.directories = list(directories)

    @staticmethod
    def set_recent_directory(_dir=dir):
        if len(RecentDirectories.directories) > 0:
            if RecentDirectories.directories[0] == _dir:
                return
            if _dir in RecentDirectories.directories:
                RecentDirectories.directories.remove(_dir)
        RecentDirectories.directories.insert(0, _dir)
        # Enforce the maximum limit by removing excess directories from the end
        if len(RecentDirectories.directories) > RecentDirectories.MAX_RECENT_DIRECTORIES:
            RecentDirectories.directories = RecentDirectories.directories[:RecentDirectories.MAX_RECENT_DIRECTORIES]

    @staticmethod
    def remove_directory(base_dir: str) -> None:
        """Remove a directory from all recent directory caches and persist the changes."""
        try:
            # Remove from main recent directories list
            if base_dir in RecentDirectories.directories:
                RecentDirectories.directories.remove(base_dir)
                app_info_cache.set_meta("recent_directories", RecentDirectories.directories)
            
            # Remove from in-memory history trackers
            try:
                RecentDirectoryWindow.directory_history = [d for d in RecentDirectoryWindow.directory_history if d != base_dir]
                if RecentDirectoryWindow.last_comparison_directory == base_dir:
                    RecentDirectoryWindow.last_comparison_directory = None
                if RecentDirectoryWindow.last_set_directory == base_dir:
                    RecentDirectoryWindow.last_set_directory = None
            except Exception:
                pass
                
        except Exception as e:
            logger.error(f"Error updating recent directories during delete: {e}")

    @staticmethod
    def find_replacement_directory(current_base_dir: str, open_window_directories: list[str]) -> str:
        """
        Find a valid replacement directory from recent directories that is not currently open.
        Returns the most recent valid directory, or home directory if none found.
        
        Args:
            current_base_dir: The directory being deleted (to exclude from consideration)
            open_window_directories: List of directories currently open in other windows
            
        Returns:
            A valid directory path to use as replacement
        """
        # Quick validation - check if current directory should be deletable
        if current_base_dir in open_window_directories:
            # This directory is open in another window, shouldn't delete
            raise ValueError(f"Directory {current_base_dir} is currently open in another window and cannot be deleted")
        
        # Look for a valid replacement from recent directories
        for directory in RecentDirectories.directories:
            if (directory != current_base_dir and 
                directory not in open_window_directories and 
                os.path.isdir(directory)):
                return directory
        
        # If no recent directory is suitable, fall back to home directory
        try:
            home_dir = Utils.get_home_directory()
            if os.path.isdir(home_dir):
                return home_dir
        except Exception as e:
            logger.error(f"Error getting home directory: {e}")
        
        # Final fallback - use current working directory
        try:
            cwd = os.getcwd()
            if os.path.isdir(cwd) and cwd != current_base_dir:
                return cwd
        except Exception as e:
            logger.error(f"Error getting current working directory: {e}")
        
        # If all else fails, raise an error
        raise ValueError("No suitable replacement directory found")


class RecentDirectoryWindow():
    recent_directories = []
    last_set_directory = None
    last_comparison_directory = None

    directory_history = []
    MAX_DIRECTORIES = 100

    MAX_HEIGHT = 900
    N_DIRECTORIES_CUTOFF = 30
    COL_0_WIDTH = 600

    @staticmethod
    def get_history_directory(start_index=0):
        # Get a previous directory.
        _dir = None
        for i in range(len(RecentDirectoryWindow.directory_history)):
            if i < start_index:
                continue
            _dir = RecentDirectoryWindow.directory_history[i]
            break
        return _dir

    @staticmethod
    def update_history(_dir):
        if len(RecentDirectoryWindow.directory_history) > 0 and \
                _dir == RecentDirectoryWindow.directory_history[0]:
            return
        RecentDirectoryWindow.directory_history.insert(0, _dir)
        if len(RecentDirectoryWindow.directory_history) > RecentDirectoryWindow.MAX_DIRECTORIES:
            del RecentDirectoryWindow.directory_history[-1]

    @staticmethod
    def get_geometry(is_gui=True):
        if is_gui:
            width = 600
            min_height = 300
            height = len(RecentDirectories.directories) * 22 + 20
            if height > RecentDirectoryWindow.MAX_HEIGHT:
                height = RecentDirectoryWindow.MAX_HEIGHT
                width *= 2 if len(RecentDirectories.directories) < RecentDirectoryWindow.N_DIRECTORIES_CUTOFF * 2 else 3
            else:
                height = max(height, min_height)
        else:
            width = 300
            height = 100
        return f"{width}x{height}"

    @staticmethod
    def add_columns():
        if len(RecentDirectories.directories) > RecentDirectoryWindow.N_DIRECTORIES_CUTOFF:
            if len(RecentDirectories.directories) > RecentDirectoryWindow.N_DIRECTORIES_CUTOFF * 2:
                return 2
            return 1
        return 0

    def __init__(self, master, app_master, is_gui, app_actions, base_dir=".", run_compare_image=None, extra_callback_args=(None, None)):
        self.is_gui = is_gui
        self.master = master
#        self.app_master = master
        self.run_compare_image = run_compare_image
        if extra_callback_args is None or extra_callback_args[0] is None:
            self.downstream_callback = None
            directories_to_add_and_sort_first = []
            self.callback_args = {}
        else:
            self.downstream_callback = extra_callback_args[0]
            directories_to_add_and_sort_first = extra_callback_args[1]
            self.callback_args = extra_callback_args[2] if len(extra_callback_args) > 2 else {}
        self.app_actions = app_actions
        self.base_dir = os.path.normpath(base_dir)
        self.filter_text = ""

        for _dir in directories_to_add_and_sort_first:
            if _dir in RecentDirectories.directories:
                RecentDirectories.directories.remove(_dir)
        for _dir in sorted(directories_to_add_and_sort_first, reverse=True):
            RecentDirectories.directories.insert(0, _dir)

        # Use the last set target directory as a base if any directories have been set
        if len(RecentDirectories.directories) > 0 and os.path.isdir(RecentDirectories.directories[0]):
            self.starting_target = RecentDirectories.directories[0]
        else:
            self.starting_target = base_dir

        self.filtered_recent_directories = RecentDirectories.directories[:]
        self.set_dir_btn_list = []
        self.label_list = []

        if self.is_gui:
            self.frame = Frame(self.master)
            self.frame.grid(column=0, row=0)
            self.frame.columnconfigure(0, weight=9)
            self.frame.columnconfigure(1, weight=1)

            add_columns = RecentDirectoryWindow.add_columns()

            if add_columns > 0:
                self.frame.columnconfigure(2, weight=9)
                self.frame.columnconfigure(3, weight=1)
                if add_columns > 1:
                    self.frame.columnconfigure(4, weight=9)
                    self.frame.columnconfigure(5, weight=1)

            self.frame.config(bg=AppStyle.BG_COLOR)

            self.add_dir_widgets()

            self._label_info = Label(self.frame)
            self.add_label(self._label_info, _("Set a new target directory"), row=0, wraplength=RecentDirectoryWindow.COL_0_WIDTH)
            self.add_directory_move_btn = None
            self.add_btn("add_directory_move_btn", _("Add directory"), self.handle_directory, column=1)
            self.set_recent_directories_from_dir_btn = None
            self.add_btn("set_recent_directories_from_dir_btn", _("Add directories from parent"), self.set_recent_directories_from_dir, column=2)
            self.clear_recent_directories_btn = None
            self.add_btn("clear_recent_directories_btn", _("Clear targets"), self.clear_recent_directories, column=3)
            self.frame.after(1, lambda: self.frame.focus_force())
        else:
            self.master.after(1, lambda: self.master.focus_force())

        self.master.bind("<Key>", self.filter_directories)
        self.master.bind("<Return>", self.do_action)
        self.master.bind("<Escape>", self.close_windows)
        self.master.protocol("WM_DELETE_WINDOW", self.close_windows)

    def add_dir_widgets(self):
        row = 0
        base_col = 0
        for i in range(len(self.filtered_recent_directories)):
            if i >= RecentDirectoryWindow.N_DIRECTORIES_CUTOFF * 2:
                row = i-RecentDirectoryWindow.N_DIRECTORIES_CUTOFF*2+1
                base_col = 4
            elif i >= RecentDirectoryWindow.N_DIRECTORIES_CUTOFF:
                row = i-RecentDirectoryWindow.N_DIRECTORIES_CUTOFF+1
                base_col = 2
            else:
                row = i+1
            _dir = self.filtered_recent_directories[i]
            self._label_info = Label(self.frame)
            self.label_list.append(self._label_info)
            self.add_label(self._label_info, _dir, row=row, column=base_col, wraplength=RecentDirectoryWindow.COL_0_WIDTH)
            set_dir_btn = Button(self.frame, text="Set")
            self.set_dir_btn_list.append(set_dir_btn)
            set_dir_btn.grid(row=row, column=base_col+1)
            def set_dir_handler(event, self=self, _dir=_dir):
                return self.set_directory(event, _dir)
            set_dir_btn.bind("<Button-1>", set_dir_handler)

    @staticmethod
    def get_directory(_dir, starting_target, toast_callback, parent=None):
        """
        If target dir given is not valid then ask user for a new one
        """
        if _dir:
            if os.path.isdir(_dir):
                return _dir, True
            else:
                if _dir in RecentDirectories.directories:
                    RecentDirectories.directories.remove(_dir)
                toast_callback(_("Invalid directory: %s").format(_dir))
        _dir = filedialog.askdirectory(
                parent=parent,
                initialdir=starting_target, title=_("Set image comparison directory"))
        return _dir, False

    def handle_directory(self, event=None, _dir=None):
        """
        Have to call this when user is setting a new directory as well, in which case _dir will be None.

        In this case we will need to add the new directory to the list of valid directories.

        Also in this case, this function will call itself by calling set_directory(),
        just this time with the directory set.
        """
        _dir, target_was_valid = RecentDirectoryWindow.get_directory(_dir, self.starting_target, self.app_actions.toast, parent=self.app_actions.get_master())
        if not os.path.isdir(_dir):
            self.close_windows()
            raise Exception("Failed to set target directory to receive marked files.")
        if target_was_valid and _dir is not None:
            RecentDirectories.set_recent_directory(_dir)
            return _dir

        _dir = os.path.normpath(_dir)
        # NOTE don't want to sort here, instead keep the most recent directories at the top
        RecentDirectories.set_recent_directory(_dir)
        self.set_directory(_dir=_dir)

    def set_directory(self, event=None, _dir=None):
        _dir = self.handle_directory(_dir=_dir)
        if config.debug and self.filter_text is not None and self.filter_text.strip() != "":
            print(f"Filtered by string: {self.filter_text}")
        RecentDirectoryWindow.update_history(_dir)
        if self.downstream_callback is not None:
            self.downstream_callback(base_dir=_dir, **self.callback_args)
            RecentDirectoryWindow.last_comparison_directory = _dir
        elif self.run_compare_image is None:
            self.app_actions.set_base_dir(base_dir_from_dir_window=_dir)
        elif self.run_compare_image == "":
            self.app_actions.new_window(base_dir=_dir)
        else:
            self.app_actions.new_window(base_dir=_dir, image_path=self.run_compare_image, do_search=True)
        RecentDirectoryWindow.last_set_directory = _dir
        self.close_windows()

    def set_recent_directories_from_dir(self, event=None):
        """
        Gather all first-level child directories from the selected directory and
        add them as directories, updating the window when complete.
        """
        parent_dir = filedialog.askdirectory(
                parent=self.master,
                initialdir=self.starting_target, title=_("Select parent directory for target directories"))
        if not os.path.isdir(parent_dir):
            raise Exception("Failed to set directory.")

        recent_directories_to_add = [name for name in os.listdir(parent_dir)
            if os.path.isdir(os.path.join(parent_dir, name))]
        recent_directories_to_add.sort(reverse=True)

        for _dir in recent_directories_to_add:
            dirpath = os.path.normpath(os.path.join(parent_dir, _dir))
            if dirpath in RecentDirectories.directories:
                RecentDirectories.directories.remove(dirpath)
            if dirpath != self.base_dir:
                RecentDirectories.directories.insert(0, dirpath)

        self.filtered_recent_directories = RecentDirectories.directories[:]
        self.filter_text = "" # Clear the filter to ensure all new directories are shown
        self.clear_widget_lists()
        self.add_dir_widgets()
        self.master.update()
        self.frame.after(1, lambda: self.frame.focus_force())

    def filter_directories(self, event):
        """
        Rebuild the filtered directories list based on the filter string and update the UI.
        """
        modifier_key_pressed = (event.state & 0x1) != 0 or (event.state & 0x4) != 0 # Do not filter if modifier key is down
        if modifier_key_pressed:
            return
        if len(event.keysym) > 1:
            # If the key is up/down arrow key, roll the list up/down
            if event.keysym == "Down" or event.keysym == "Up":
                if event.keysym == "Down":
                    self.filtered_recent_directories = self.filtered_recent_directories[1:] + [self.filtered_recent_directories[0]]
                else:  # keysym == "Up"
                    self.filtered_recent_directories = [self.filtered_recent_directories[-1]] + self.filtered_recent_directories[:-1]
                if self.is_gui:
                    self.clear_widget_lists()
                    self.add_dir_widgets()
                    self.master.update()
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
                print("Filter unset")
            # Restore the list of target directories to the full list
            self.filtered_recent_directories.clear()
            self.filtered_recent_directories = RecentDirectories.directories[:]
        else:
            temp = []
            # First pass try to match directory basename
            for _dir in RecentDirectories.directories:
                basename = os.path.basename(os.path.normpath(_dir))
                if basename.lower() == self.filter_text:
                    temp.append(_dir)
            for _dir in RecentDirectories.directories:
                basename = os.path.basename(os.path.normpath(_dir))
                if _dir not in temp:
                    if basename.lower().startswith(self.filter_text):
                        temp.append(_dir)
            # Second pass try to match parent directory name, so these will appear after
            for _dir in RecentDirectories.directories:
                if _dir not in temp:
                    dirname = os.path.basename(os.path.dirname(os.path.normpath(_dir)))
                    if dirname and dirname.lower().startswith(self.filter_text):
                        temp.append(_dir)
            # Third pass try to match part of the basename
            for _dir in RecentDirectories.directories:
                if _dir not in temp:
                    basename = os.path.basename(os.path.normpath(_dir))
                    if basename and (f" {self.filter_text}" in basename.lower() or f"_{self.filter_text}" in basename.lower()):
                        temp.append(_dir)
            self.filtered_recent_directories = temp[:]

        if self.is_gui:
            self.clear_widget_lists()
            self.add_dir_widgets()
            self.master.update()


    def do_action(self, event=None):
        """
        The user has requested to set a directory. Based on the context, figure out what to do.

        If no directories preset, call handle_directory() with _dir=None to set a new directory.

        If directories preset, call set_directory() to set the first directory.

        If control key pressed, ignore existing and add a new directory.

        If alt key pressed, use the penultimate directory.

        The idea is the user can filter the directories using keypresses, then press enter to
        do the action on the first filtered directory.
        """
        control_key_pressed, alt_key_pressed = Utils.modifier_key_pressed(
            event, keys_to_check=[ModifierKey.CTRL, ModifierKey.ALT])
        if alt_key_pressed:
            penultimate_dir = RecentDirectoryWindow.get_history_directory(start_index=1)
            if penultimate_dir is not None and os.path.isdir(penultimate_dir):
                self.set_directory(_dir=penultimate_dir)
        elif len(self.filtered_recent_directories) == 0 or control_key_pressed:
            self.handle_directory()
        else:
            if len(self.filtered_recent_directories) == 1 or self.filter_text.strip() != "":
                _dir = self.filtered_recent_directories[0]
            else:
                _dir = RecentDirectoryWindow.last_set_directory
            self.set_directory(_dir=_dir)

    def clear_recent_directories(self, event=None):
        self.clear_widget_lists()
        RecentDirectories.directories.clear()
        self.filtered_recent_directories.clear()
        self.add_dir_widgets()
        self.master.update()

    def clear_widget_lists(self):
        for btn in self.set_dir_btn_list:
            btn.destroy()
        for label in self.label_list:
            label.destroy()
        self.set_dir_btn_list = []
        self.label_list = []

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
