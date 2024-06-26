import hashlib
import os
import re

from tkinter import Frame, Label, filedialog, messagebox, LEFT, W
from tkinter.ttk import Button

from compare.compare_embeddings import CompareEmbedding
from utils.app_info_cache import app_info_cache
from utils.app_style import AppStyle
from utils.config import config
from utils.constants import Mode
from utils.utils import move_file, copy_file

# TODO check hash of files in new directory instead of just filename, or even use a new compare instance to check for duplicates
# TODO preserve dictionary of all moved / copied files in a session along with their target directories.
# TODO enable the main app to access this dictionary as groups and remove files if needed
# TODO give statistics on how many files were moved / copied.

def _calculate_hash(filepath):
    with open(filepath, 'rb') as f:
        sha256 = hashlib.sha256()
        while True:
            data = f.read(65536)
            if not data: break
            sha256.update(f.read())
    return sha256.hexdigest()


class Action():
    def __init__(self, action, target):
        self.action = action
        self.target = target
        self.marks = []

    def __eq__(self, other):
        if not isinstance(other, Action):
            return False
        return self.action == other.action and self.target == other.target
    
    def __hash__(self):
        return hash((self.action, self.target))

    def __str__(self):
        return self.action.__name__ + " to " + self.target

def setup_permanent_action():
    permanent_mark_target = app_info_cache.get_meta("permanent_mark_target")
    permanent_action = app_info_cache.get_meta("permanent_action")
    if permanent_action == "move_file":
        return Action(move_file, permanent_mark_target)
    elif permanent_action == "copy_file":
        return Action(copy_file, permanent_mark_target)
    else:
        return None


class MarkedFiles():
    file_marks = []
    mark_target_dirs = []
    previous_marks = []
    last_set_target_dir = None
    is_performing_action = False
    is_cancelled_action = False

    permanent_action = setup_permanent_action()
    action_history = []
    MAX_ACTIONS = 50

    delete_lock = False
    mark_cursor = -1
    max_height = 900
    n_target_dirs_cutoff = 30
    col_0_width = 600

    @staticmethod
    def set_target_dirs(target_dirs):
        MarkedFiles.mark_target_dirs = target_dirs

    @staticmethod
    def set_delete_lock(delete_lock=True):
        MarkedFiles.delete_lock = delete_lock

    @staticmethod
    def clear_file_marks(toast_callback):
        MarkedFiles.file_marks = []
        toast_callback(f"Marks cleared.")

    @staticmethod
    def set_current_marks_from_previous(toast_callback):
        for f in MarkedFiles.previous_marks:
            if f not in MarkedFiles.file_marks and os.path.exists(f):
                MarkedFiles.file_marks.append(f)
        toast_callback(f"Set current marks from previous.\nTotal set: {len(MarkedFiles.file_marks)}")

    @staticmethod
    def get_history_action(start_index=0):
        # Get a previous action that is not equivalent to the permanent action if possible.
        action = None
        seen_actions = []
        for i in range(len(MarkedFiles.action_history)):
            action = MarkedFiles.action_history[i]
            is_returnable_action = action != MarkedFiles.permanent_action
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
    def run_previous_action(app_actions):
        previous_action = MarkedFiles.get_history_action(start_index=0)
        if previous_action is None:
            return False, False
        return MarkedFiles.move_marks_to_dir_static(app_actions,
                                             target_dir=previous_action.target,
                                             move_func=previous_action.action,
                                             single_image=(len(MarkedFiles.file_marks)==1))

    @staticmethod
    def run_penultimate_action(app_actions):
        penultimate_action = MarkedFiles.get_history_action(start_index=1)
        if penultimate_action is None:
            return False, False
        return MarkedFiles.move_marks_to_dir_static(app_actions,
                                             target_dir=penultimate_action.target,
                                             move_func=penultimate_action.action,
                                             single_image=(len(MarkedFiles.file_marks)==1))

    @staticmethod
    def run_permanent_action(app_actions):
        if not MarkedFiles.permanent_action:
            app_actions.toast(f"No permanent mark target set!\nSet with Ctrl+T on Marks window.")
            return False, False
        return MarkedFiles.move_marks_to_dir_static(app_actions,
                                             target_dir=MarkedFiles.permanent_action.target,
                                             move_func=MarkedFiles.permanent_action.action,
                                             single_image=(len(MarkedFiles.file_marks)==1))

    @staticmethod
    def set_permanent_action(target_dir, move_func, toast_callback):
        MarkedFiles.permanent_action = Action(move_func, target_dir)
        app_info_cache.set_meta("permanent_action", move_func.__name__)
        app_info_cache.set_meta("permanent_mark_target", target_dir)
        toast_callback(f"Set permanent action:\n{move_func.__name__} to {target_dir}")

    @staticmethod
    def update_history(target_dir, move_func):
        MarkedFiles.previous_marks.clear()
        latest_action = Action(move_func, target_dir)
        if len(MarkedFiles.action_history) > 0 and \
                latest_action == MarkedFiles.action_history[0]:
            return
        MarkedFiles.action_history.insert(0, latest_action)
        if len(MarkedFiles.action_history) > MarkedFiles.MAX_ACTIONS:
            del MarkedFiles.action_history[-1]

    @staticmethod
    def get_geometry(is_gui=True):
        if is_gui:
            width = 600
            min_height = 300
            height = len(MarkedFiles.mark_target_dirs) * 22 + 20
            if height > MarkedFiles.max_height:
                height = MarkedFiles.max_height
                width *= 2 if len(MarkedFiles.mark_target_dirs) < MarkedFiles.n_target_dirs_cutoff * 2 else 3
            else:
                height = max(height, min_height)
        else:
            width = 300
            height = 100
        return f"{width}x{height}"

    @staticmethod
    def add_columns():
        if len(MarkedFiles.mark_target_dirs) > MarkedFiles.n_target_dirs_cutoff:
            if len(MarkedFiles.mark_target_dirs) > MarkedFiles.n_target_dirs_cutoff * 2:
                return 2
            return 1
        return 0

    def __init__(self, master, is_gui, single_image, app_mode, app_actions, base_dir="."):
        self.is_gui = is_gui
        self.single_image = single_image
        self.master = master
        self.app_mode = app_mode
        self.compare = None
        self.is_sorted_by_embedding = False
        self.app_actions = app_actions
        self.base_dir = os.path.normpath(base_dir)
        self.filter_text = ""
        self.filtered_target_dirs = MarkedFiles.mark_target_dirs[:]

        # Use the last set target directory as a base if any directories have been set
        if MarkedFiles.last_set_target_dir and os.path.isdir(MarkedFiles.last_set_target_dir):
            self.starting_target = MarkedFiles.last_set_target_dir
        else:
            self.starting_target = base_dir

        self.do_set_permanent_mark_target = False
        self.move_btn_list = []
        self.copy_btn_list = []
        self.label_list = []

        if self.is_gui:
            self.frame = Frame(self.master)
            self.frame.grid(column=0, row=0)
            self.frame.columnconfigure(0, weight=9)
            self.frame.columnconfigure(1, weight=1)
            self.frame.columnconfigure(2, weight=1)

            add_columns = MarkedFiles.add_columns()

            if add_columns > 0:
                self.frame.columnconfigure(3, weight=9)
                self.frame.columnconfigure(4, weight=1)
                self.frame.columnconfigure(5, weight=1)
                if add_columns > 1:
                    self.frame.columnconfigure(6, weight=9)
                    self.frame.columnconfigure(7, weight=1)
                    self.frame.columnconfigure(8, weight=1)

            self.frame.config(bg=AppStyle.BG_COLOR)

            self.add_target_dir_widgets()

            self._label_info = Label(self.frame)
            self.add_label(self._label_info, "Set a new target directory", row=0, wraplength=MarkedFiles.col_0_width)
            self.add_directory_move_btn = None
            self.add_btn("add_directory_move_btn", "MOVE", self.handle_target_directory, column=1)
            def copy_handler_new_dir(event=None, self=self):
                self.handle_target_directory(move_func=copy_file)
            self.add_directory_copy_btn = None
            self.add_btn("add_directory_copy_btn", "COPY", copy_handler_new_dir, column=2)
            self.delete_btn = None
            self.add_btn("delete_btn", "DELETE", self.delete_marked_files, column=3)
            self.set_target_dirs_from_dir_btn = None
            self.add_btn("set_target_dirs_from_dir_btn", "Add directories from parent", self.set_target_dirs_From_dir, column=4)
            self.clear_target_dirs_btn = None
            self.add_btn("clear_target_dirs_btn", "Clear targets", self.clear_target_dirs, column=5)
            self.frame.after(1, lambda: self.frame.focus_force())
        else:
            self.master.after(1, lambda: self.master.focus_force())

        self.master.bind("<Key>", self.filter_targets)
        self.master.bind("<Return>", self.do_action)
        self.master.bind("<Escape>", self.close_windows)
        self.master.bind('<Shift-Delete>', self.delete_marked_files)
        self.master.bind("<Button-2>", self.delete_marked_files)
        self.master.bind("<Control-t>", self.set_permanent_mark_target)
        self.master.bind("<Control-s>", self.sort_target_dirs_by_embedding)

    def add_target_dir_widgets(self):
        row = 0
        base_col = 0
        for i in range(len(self.filtered_target_dirs)):
            if i >= MarkedFiles.n_target_dirs_cutoff * 2:
                row = i-MarkedFiles.n_target_dirs_cutoff*2+1
                base_col = 6
            elif i >= MarkedFiles.n_target_dirs_cutoff:
                row = i-MarkedFiles.n_target_dirs_cutoff+1
                base_col = 3
            else:
                row = i+1
            target_dir = self.filtered_target_dirs[i]
            self._label_info = Label(self.frame)
            self.label_list.append(self._label_info)
            self.add_label(self._label_info, target_dir, row=row, column=base_col, wraplength=MarkedFiles.col_0_width)

            move_btn = Button(self.frame, text="Move")
            self.move_btn_list.append(move_btn)
            move_btn.grid(row=row, column=base_col+1)
            def move_handler(event, self=self, target_dir=target_dir):
                return self.move_marks_to_dir(event, target_dir)
            move_btn.bind("<Button-1>", move_handler)

            copy_btn = Button(self.frame, text="Copy")
            self.copy_btn_list.append(copy_btn)
            copy_btn.grid(row=row, column=base_col+2)
            def copy_handler(event, self=self, target_dir=target_dir):
                return self.move_marks_to_dir(event, target_dir, move_func=copy_file)
            copy_btn.bind("<Button-1>", copy_handler)


    @staticmethod
    def get_target_directory(target_dir, starting_target, toast_callback):
        """
        If target dir given is not valid then ask user for a new one
        """
        if target_dir:
            if os.path.isdir(target_dir):
                return target_dir, True
            else:
                if target_dir in MarkedFiles.mark_target_dirs:
                    MarkedFiles.mark_target_dirs.remove(target_dir)
                toast_callback(f"Invalid directory: {target_dir}")
        target_dir = filedialog.askdirectory(
                initialdir=starting_target, title="Select target directory for marked files")
        return target_dir, False


    def handle_target_directory(self, event=None, target_dir=None, move_func=move_file):
        """
        Have to call this when user is setting a new target directory as well,
        in which case target_dir will be None.
        
        In this case we will need to add the new target dir to the list of valid directories.
        
        Also in this case, this function will call itself by calling
        move_marks_to_target_dir(), just this time with the directory set.
        """
        target_dir, target_was_valid = MarkedFiles.get_target_directory(target_dir, self.starting_target, self.app_actions.toast)
        if not os.path.isdir(target_dir):
            self.close_windows()
            raise Exception("Failed to set target directory to receive marked files.")
        if target_was_valid and target_dir is not None:
            return target_dir

        target_dir = os.path.normpath(target_dir)
        if not target_dir in MarkedFiles.mark_target_dirs:
            MarkedFiles.mark_target_dirs.append(target_dir)
            MarkedFiles.mark_target_dirs.sort()
        self.move_marks_to_dir(target_dir=target_dir, move_func=move_func)

    def move_marks_to_dir(self, event=None, target_dir=None, move_func=move_file):
        target_dir = self.handle_target_directory(target_dir=target_dir)
        if config.debug and self.filter_text is not None and self.filter_text.strip() != "":
            print(f"Filtered by string: {self.filter_text}")
        if self.do_set_permanent_mark_target:
            MarkedFiles.set_permanent_action(target_dir, move_func, self.app_actions.toast)
            self.do_set_permanent_mark_target = False
        some_files_already_present, exceptions_present = MarkedFiles.move_marks_to_dir_static(
            self.app_actions, target_dir=target_dir, move_func=move_func, single_image=self.single_image)
        self.close_windows()

    @staticmethod
    def move_marks_to_dir_static(app_actions, target_dir=None,
                                 move_func=move_file, single_image=False):
        """
        Move or copy the marked files to the target directory.
        """
        MarkedFiles.is_performing_action = True
        some_files_already_present = False
        is_moving = move_func == move_file
        action_part1 = "Moving" if is_moving else "Copying"
        action_part2 = "Moved" if is_moving else "Copied"
        MarkedFiles.update_history(target_dir, move_func)
        if len(MarkedFiles.file_marks) > 1:
            print(f"{action_part1} {len(MarkedFiles.file_marks)} files to directory: {target_dir}")
        exceptions = {}
        invalid_files = []
        for marked_file in MarkedFiles.file_marks:
            if MarkedFiles.is_cancelled_action:
                break
            new_filename = os.path.join(target_dir, os.path.basename(marked_file))
            try:
                move_func(marked_file, target_dir, overwrite_existing=config.move_marks_overwrite_existing_file)
                print(f"{action_part2} file to {new_filename}")
                MarkedFiles.previous_marks.append(marked_file)
                has_moved_one_file = True
            except Exception as e:
                exceptions[marked_file] = (str(e), new_filename)
                if not os.path.exists(marked_file):
                    invalid_files.append(marked_file)
        if MarkedFiles.is_cancelled_action:
            MarkedFiles.is_cancelled_action = False
            MarkedFiles.is_performing_action = False
            print(f"Cancelled {action_part1} to {target_dir}")
            if len(MarkedFiles.previous_marks) > 0:
                MarkedFiles.undo_move_marks(app_actions.get_base_dir(), app_actions)
            return False, False
        if len(exceptions) < len(MarkedFiles.file_marks):
            app_actions.toast(f"{action_part2} {len(MarkedFiles.file_marks) - len(exceptions)} files to\n{target_dir}")
            MarkedFiles.delete_lock = False
        MarkedFiles.file_marks.clear()
        exceptions_present = len(exceptions) > 0
        if exceptions_present:
            action_part3 = "move" if is_moving else "copy"
            print(f"Failed to {action_part3} some files:")
            names_are_short = False
            matching_files = False
            for marked_file, exc_tuple in exceptions.items():
                print(exc_tuple[0])
                if not marked_file in invalid_files:
                    if not config.clear_marks_with_errors_after_move and not single_image:
                        # Just in case some of them failed to move for whatever reason.
                        MarkedFiles.file_marks.append(marked_file)
                    if exc_tuple[0].startswith("File already exists"):
                        if _calculate_hash(marked_file) == _calculate_hash(exc_tuple[1]):
                            matching_files = True
                            print(f"File hashes match: {marked_file} <> {exc_tuple[1]}")
                        elif len(os.path.basename(marked_file)) < 13 and not names_are_short:
                            names_are_short = True
                        some_files_already_present = True
            if some_files_already_present:
                if config.clear_marks_with_errors_after_move and not single_image:
                    print("Cleared invalid marks by config option")
                warning = "Existing filenames match!"
                if matching_files:
                    warning += "\nWARNING: Exact file match."
                if names_are_short:
                    warning += "\nWARNING: Short filenames."
                app_actions.toast(warning)
        MarkedFiles.is_performing_action = False
        if len(MarkedFiles.previous_marks) > 0:
            MarkedFiles.last_set_target_dir = target_dir
            if is_moving:
                app_actions.refresh(removed_files=list(MarkedFiles.previous_marks))
            else:
                app_actions.refresh()
            if not exceptions_present:
                app_actions.refocus()
        return some_files_already_present, exceptions_present

    @staticmethod
    def undo_move_marks(base_dir, app_actions):
        """
        Undo the previous move/copy operation.
        """
        if MarkedFiles.is_performing_action:
            MarkedFiles.is_cancelled_action = True
            return
        if MarkedFiles.delete_lock:
            return
        is_moving_back = MarkedFiles.action_history[0].action == move_file
        action_part1 = "Moving back" if is_moving_back else "Removing"
        action_part2 = "Moved back" if is_moving_back else "Removed"
        target_dir, target_was_valid = MarkedFiles.get_target_directory(MarkedFiles.last_set_target_dir, None, app_actions.toast)
        if not target_was_valid:
            raise Exception(f"{action_part1} previously marked files failed, somehow previous target directory invalid:  {target_dir}")
        if base_dir is None:
            base_dir = filedialog.askdirectory(
                initialdir=target_dir, title="Where should the marked files have gone?")
        if base_dir is None or base_dir == "" or not os.path.isdir(base_dir):
            raise Exception("Failed to get valid base directory for undo move marked files.")
        print(f"Undoing action: {action_part1} {len(MarkedFiles.previous_marks)} files from directory:\n{MarkedFiles.last_set_target_dir}")
        exceptions = {}
        invalid_files = []
        for marked_file in MarkedFiles.previous_marks:
            expected_new_filepath = os.path.join(target_dir, os.path.basename(marked_file))
            try:
                if is_moving_back:
                    # Move the file back to its original place.
                    move_file(expected_new_filepath, base_dir, overwrite_existing=config.move_marks_overwrite_existing_file)
                else:
                    # Remove the file.
                    os.remove(expected_new_filepath)
                print(f"{action_part2} file from {target_dir}: {os.path.basename(marked_file)}")
            except Exception as e:
                exceptions[marked_file] = str(e)
                if is_moving_back:
                    if not os.path.exists(marked_file):
                        invalid_files.append(expected_new_filepath)
                elif os.path.exists(expected_new_filepath):
                    invalid_files.append(expected_new_filepath)
        if len(exceptions) < len(MarkedFiles.previous_marks):
            app_actions.toast(f"{action_part2} {len(MarkedFiles.previous_marks) - len(exceptions)} files from\n{target_dir}")
        MarkedFiles.previous_marks.clear()
        if len(exceptions) > 0:
            for marked_file in exceptions.keys():
                if not marked_file in invalid_files:
                    MarkedFiles.previous_marks.append(marked_file) # Just in case some of them failed to move for whatever reason.
            action_part3 = "move" if is_moving_back else "copy"
            raise Exception(f"Failed to {action_part3} some files: {exceptions}")
        app_actions.refresh()

    def set_target_dirs_From_dir(self, event=None):
        """
        Gather all first-level child directories from the selected directory and
        add them as target directories, updating the window when complete.
        """
        parent_dir = filedialog.askdirectory(
                initialdir=self.starting_target, title="Select parent directory for target directories")
        if not os.path.isdir(parent_dir):
            raise Exception("Failed to set target directory to receive marked files.")

        target_dirs_to_add = [name for name in os.listdir(parent_dir)
            if os.path.isdir(os.path.join(parent_dir, name))]

        for target_dir in target_dirs_to_add:
            if not target_dir in MarkedFiles.mark_target_dirs:
                dirpath = os.path.normpath(os.path.join(parent_dir, target_dir))
                if dirpath != self.base_dir:
                    MarkedFiles.mark_target_dirs.append(os.path.normpath(os.path.join(parent_dir, target_dir)))

        MarkedFiles.mark_target_dirs.sort()
        self.filtered_target_dirs = MarkedFiles.mark_target_dirs[:]
        self.filter_text = "" # Clear the filter to ensure all new directories are shown
        self.clear_widget_lists()
        self.add_target_dir_widgets()
        self.master.update()
        self.frame.after(1, lambda: self.frame.focus_force())


    def filter_targets(self, event):
        """
        Rebuild the filtered target directories list based on the filter string and update the UI.
        """
        modifier_key_pressed = (event.state & 0x1) != 0 or (event.state & 0x4) != 0 # Do not filter if modifier key is down
        if modifier_key_pressed:
            return
        if len(event.keysym) > 1:
            # If the key is up/down arrow key, roll the list up/down
            if event.keysym == "Down" or event.keysym == "Up":
                if event.keysym == "Down":
                    self.filtered_target_dirs = self.filtered_target_dirs[1:] + [self.filtered_target_dirs[0]]
                else:  # keysym == "Up"
                    self.filtered_target_dirs = [self.filtered_target_dirs[-1]] + self.filtered_target_dirs[:-1]
                if self.is_gui:
                    self.clear_widget_lists()
                    self.add_target_dir_widgets()
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
            self.filtered_target_dirs.clear()
            self.filtered_target_dirs = MarkedFiles.mark_target_dirs[:]
        else:
            temp = []
            # First pass try to match directory name
            for target_dir in MarkedFiles.mark_target_dirs:
                dirname = os.path.basename(os.path.normpath(target_dir))
                if dirname.lower() == self.filter_text:
                    temp.append(target_dir)
            for target_dir in MarkedFiles.mark_target_dirs:
                dirname = os.path.basename(os.path.normpath(target_dir))
                if not target_dir in temp:
                    if dirname.lower().startswith(self.filter_text):
                        temp.append(target_dir)
            # Second pass try to match parent directory name, so these will appear after
            for target_dir in MarkedFiles.mark_target_dirs:
                if not target_dir in temp:
                    dirname = os.path.basename(os.path.dirname(os.path.normpath(target_dir)))
                    if dirname and dirname.lower().startswith(self.filter_text):
                        temp.append(target_dir)
            # Third pass try to match part of file name
            for target_dir in MarkedFiles.mark_target_dirs:
                if not target_dir in temp:
                    dirname = os.path.basename(os.path.normpath(target_dir))
                    if dirname and (f" {self.filter_text}" in dirname.lower() or f"_{self.filter_text}" in dirname.lower()):
                        temp.append(target_dir)
            self.filtered_target_dirs = temp[:]

        if self.is_gui:
            self.clear_widget_lists()
            self.add_target_dir_widgets()
            self.master.update()


    def do_action(self, event=None):
        """
        The user has requested to do something with the marked files. Based on the context, figure out what to do.

        If no target directories set, call handle_target_directory() with target_dir=None to set a new directory.

        If target directories set, call move_marks_to_dir() to move the marked files to the first target directory.

        If shift key pressed, copy the files, but if not, just move them.

        If control key pressed, ignore any marked dirs and set a new target directory.

        If alt key pressed, use the penultimate mark target dir as target directory.

        The idea is the user can filter the directories using keypresses, then press enter to
        do the action on the first filtered directory.

        TODO: handle case of multiple filtered directories better, instead of just selecting the first
        """
        shift_key_pressed = (event.state & 0x1) != 0
        control_key_pressed = (event.state & 0x4) != 0
        alt_key_pressed = (event.state & 0x20000) != 0
        move_func = copy_file if shift_key_pressed else move_file
        if alt_key_pressed:
            penultimate_action = MarkedFiles.get_history_action(start_index=1)
            if penultimate_action is not None and os.path.isdir(penultimate_action.target):
                self.move_marks_to_dir(target_dir=penultimate_action.target, move_func=move_func)
        elif len(self.filtered_target_dirs) == 0 or control_key_pressed:
            self.handle_target_directory(move_func=move_func)
        else:
            # TODO maybe sort the last target dir first in the list instead of this
            # might be confusing otherwise
            if len(self.filtered_target_dirs) == 1 or self.filter_text.strip() != "" or self.is_sorted_by_embedding:
                target_dir = self.filtered_target_dirs[0]
            else:
                target_dir = MarkedFiles.last_set_target_dir
            self.move_marks_to_dir(target_dir=target_dir, move_func=move_func)

    def set_permanent_mark_target(self, event=None):
        self.do_set_permanent_mark_target = True
        self.app_actions.toast("Recording next mark target and action.")

    def clear_target_dirs(self, event=None):
        self.clear_widget_lists()
        MarkedFiles.mark_target_dirs.clear()
        self.filtered_target_dirs.clear()
        self.add_target_dir_widgets()
        self.master.update()

    def _get_embedding_text_for_dirpath(self, dirpath):
        basename = os.path.basename(dirpath)
        for text in config.text_embedding_search_presets:
            if basename == text or re.search(f"(^|_| ){text}($|_| )", basename):
                print(f"Found embeddable directory for text {text}: {dirpath}")
                return text
        return None

    def sort_target_dirs_by_embedding(self, event=None):
        embedding_texts = {}
        for d in self.filtered_target_dirs:
            embedding_text = self._get_embedding_text_for_dirpath(d)
            if embedding_text is not None and embedding_text.strip() != "":
                embedding_texts[d] = embedding_text
        similarities = CompareEmbedding.single_text_compare(self.single_image, embedding_texts)
        sorted_dirs = []
        for dirpath, similarity in sorted(similarities.items(), key=lambda x: -x[1]):
            sorted_dirs.append(dirpath)
        self.filtered_target_dirs = list(sorted_dirs)
        self.is_sorted_by_embedding = True
        if self.is_gui:
            self.clear_widget_lists()
            self.add_target_dir_widgets()
            self.master.update()
        self.app_actions.toast("Sorted directories by embedding comparison.")

    def clear_widget_lists(self):
        for btn in self.move_btn_list:
            btn.destroy()
        for btn in self.copy_btn_list:
            btn.destroy()
        for label in self.label_list:
            label.destroy()
        self.move_btn_list = []
        self.copy_btn_list = []
        self.label_list = []


    def delete_marked_files(self, event=None):
        """
        Delete the marked files.

        Unfortunately, since there are challenges with restoring files from trash folder
        an undo operation is not implemented.
        """
        res = self.app_actions.alert("Confirm Delete",
                f"Deleting {len(MarkedFiles.file_marks)} marked files - Are you sure you want to proceed?",
                kind="warning")
        if res != messagebox.OK:
            if config.debug:
                print(f"result was: {res}")
            return

        removed_files = []
        failed_to_delete = []
        for filepath in MarkedFiles.file_marks:
            try:
                # NOTE since undo delete is not supported, the delete callback handles setting a delete lock
                self.app_actions.delete(filepath, manual_delete=False)
                removed_files.append(filepath)
            except Exception as e:
                print(f"Failed to delete {filepath}: {e}")
                if os.path.exists(filepath):
                    failed_to_delete.append(filepath)

        MarkedFiles.file_marks.clear()
        if len(failed_to_delete) > 0:
            MarkedFiles.file_marks.extend(failed_to_delete)
            self.app_actions.alert("Delete Failed",
                    f"Failed to delete {len(failed_to_delete)} files - check log for details.",
                    kind="warning")
        else:
            self.app_actions.toast(f"Deleted {len(removed_files)} marked files.")

        # In the BROWSE case, the file removal should be recognized by the file browser
        ## TODO it will not be handled in case of using file JSON. need to handle this case separately.        
        self.app_actions.refresh(removed_files=(removed_files if self.app_mode != Mode.BROWSE else []))
        self.close_windows()

    def close_windows(self, event=None):
        self.master.destroy()
        if self.single_image is not None and len(MarkedFiles.file_marks) == 1:
            # This implies the user has opened the marks window directly from the current image
            # but did not take any action on this marked file. It's possible that the action 
            # the user requested was already taken, and an error was thrown preventing it from
            # being repeated and overwriting the file. If so the user likely doesn't want to 
            # take any more actions on this file so we can forget about it.
            MarkedFiles.file_marks.clear()
            self.app_actions.toast("Cleared marked file")

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

