import os

from tkinter import Frame, Label, filedialog, messagebox, LEFT, W
from tkinter.ttk import Button

from utils.config import config
from utils.app_style import AppStyle
from utils.utils import move_file, copy_file


# TODO preserve dictionary of all moved / copied files in a session along with their target directories.
# TODO enable the main app to access this dictionary as groups and remove files if needed
# TODO give statistics on how many files were moved / copied.

class MarkedFiles():
    file_marks = []
    previous_marks = []
    previous_action = None
    mark_target_dirs = []
    last_set_target_dir = None
    mark_cursor = -1
    max_height = 900
    n_target_dirs_cutoff = 30
    col_0_width = 600

    @staticmethod
    def get_geometry():
        width = 600
        min_height = 300
        height = len(MarkedFiles.mark_target_dirs) * 22 + 20
        if height > MarkedFiles.max_height:
            height = MarkedFiles.max_height
            width *= 2 if len(MarkedFiles.mark_target_dirs) < MarkedFiles.n_target_dirs_cutoff * 2 else 3
        else:
            height = max(height, min_height)
        return f"{width}x{height}"

    @staticmethod
    def add_columns():
        if len(MarkedFiles.mark_target_dirs) > MarkedFiles.n_target_dirs_cutoff:
            if len(MarkedFiles.mark_target_dirs) > MarkedFiles.n_target_dirs_cutoff * 2:
                return 2
            return 1
        return 0

    def __init__(self, master, toast_callback, alert_callback, refresh_callback, delete_callback, base_dir="."):
        self.master = master
        self.toast_callback = toast_callback
        self.alert_callback = alert_callback
        self.refresh_callback = refresh_callback
        self.delete_callback = delete_callback
        self.base_dir = os.path.normpath(base_dir)
        self.filter_text = ""
        self.filtered_target_dirs = MarkedFiles.mark_target_dirs[:]

        # Use the last set target directory as a base if any directories have been set
        if MarkedFiles.last_set_target_dir and os.path.isdir(MarkedFiles.last_set_target_dir):
            self.starting_target = MarkedFiles.last_set_target_dir
        else:
            self.starting_target = base_dir
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

        self.move_btn_list = []
        self.copy_btn_list = []
        self.label_list = []
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

        self.master.bind("<Key>", self.filter_targets)
        self.master.bind("<Return>", self.do_action)
        self.master.bind("<Shift-W>", self.close_windows)
        self.master.bind('<Shift-Delete>', self.delete_marked_files)
        self.master.bind("<Button-2>", self.delete_marked_files)
        self.frame.after(1, lambda: self.frame.focus_force())



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
        target_dir, target_was_valid = MarkedFiles.get_target_directory(target_dir, self.starting_target, self.toast_callback)
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
        """
        Move or copy the marked files to the target directory.
        """
        target_dir = self.handle_target_directory(target_dir=target_dir)
        is_moving = move_func == move_file
        action_part1 = "Moving" if is_moving else "Copying"
        action_part2 = "Moved" if is_moving else "Copied"
        MarkedFiles.previous_marks.clear()
        MarkedFiles.previous_action = move_func
        print(f"{action_part1} {len(MarkedFiles.file_marks)} files to directory: {target_dir}")
        exceptions = {}
        invalid_files = []
        for marked_file in MarkedFiles.file_marks:
            try:
                move_func(marked_file, target_dir, overwrite_existing=config.move_marks_overwrite_existing_file)
                print(f"{action_part2} file to {target_dir}: {os.path.basename(marked_file)}")
                MarkedFiles.previous_marks.append(marked_file)
            except Exception as e:
                exceptions[marked_file] = str(e)
                if not os.path.exists(marked_file):
                    invalid_files.append(marked_file)
        if len(exceptions) < len(MarkedFiles.file_marks):
            self.toast_callback(f"{action_part2} {len(MarkedFiles.file_marks) - len(exceptions)} files to\n{target_dir}")
        MarkedFiles.file_marks.clear()
        if len(exceptions) > 0:
            for marked_file in exceptions.keys():
                if not marked_file in invalid_files:
                    MarkedFiles.file_marks.append(marked_file) # Just in case some of them failed to move for whatever reason.
            action_part3 = "move" if is_moving else "copy"
            raise Exception(f"Failed to {action_part3} some files: {exceptions}")
        MarkedFiles.last_set_target_dir = target_dir
        if is_moving:
            self.refresh_callback(removed_files=list(MarkedFiles.previous_marks))
        else:
            self.refresh_callback()
        self.close_windows()

    @staticmethod
    def undo_move_marks(base_dir, toast_callback, refresh_callback):
        """
        Undo the previous move/copy operation.
        """
        if MarkedFiles.previous_action is None:
            return
        is_moving_back = MarkedFiles.previous_action == move_file
        action_part1 = "Moving back" if is_moving_back else "Removing"
        action_part2 = "Moved back" if is_moving_back else "Removed"
        target_dir, target_was_valid = MarkedFiles.get_target_directory(MarkedFiles.last_set_target_dir, None, toast_callback)
        if not target_was_valid:
            raise Exception(f"{action_part1} previously marked files failed, somehow previous target directory invalid:  {target_dir}")
        if base_dir is None:
            base_dir = filedialog.askdirectory(
                initialdir=target_dir, title="Where should the marked files have gone?")
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
            toast_callback(f"{action_part2} {len(MarkedFiles.previous_marks) - len(exceptions)} files from\n{target_dir}")
        MarkedFiles.previous_marks.clear()
        if len(exceptions) > 0:
            for marked_file in exceptions.keys():
                if not marked_file in invalid_files:
                    MarkedFiles.previous_marks.append(marked_file) # Just in case some of them failed to move for whatever reason.
            action_part3 = "move" if is_moving_back else "copy"
            raise Exception(f"Failed to {action_part3} some files: {exceptions}")
        refresh_callback()

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
            print("Filter unset")
            # Restore the list of target directories to the full list
            self.filtered_target_dirs.clear()
            self.filtered_target_dirs = MarkedFiles.mark_target_dirs[:]
        else:
            print(f"Filtering by string: {self.filter_text}")
            temp = []
            # First pass try to match directory name
            for target_dir in MarkedFiles.mark_target_dirs:
                dirname = os.path.basename(os.path.normpath(target_dir))
                if dirname.lower().startswith(self.filter_text):
                    temp.append(target_dir)
            # Second pass try to match parent directory name, so these will appear after
            for target_dir in MarkedFiles.mark_target_dirs:
                if not target_dir in temp:
                    dirname = os.path.basename(os.path.dirname(os.path.normpath(target_dir)))
                    if dirname and dirname.lower().startswith(self.filter_text):
                        temp.append(target_dir)
            self.filtered_target_dirs = temp[:]

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

        The idea is the user can filter the directories using keypresses, then press enter to
        do the action on the first filtered directory.

        TODO: handle case of multiple filtered directories better, instead of just selecting the first
        """
        shift_key_pressed = (event.state & 0x1) != 0
        control_key_pressed = (event.state & 0x4) != 0
        move_func = copy_file if shift_key_pressed else move_file
        if len(self.filtered_target_dirs) == 0 or control_key_pressed:
            self.handle_target_directory(move_func=move_func)
        else:
            # TODO maybe sort the last target dir first in the list instead of this
            # might be confusing otherwise
            if len(self.filtered_target_dirs) == 1 or self.filter_text.strip() != "":
                target_dir = self.filtered_target_dirs[0]
            else:
                target_dir = MarkedFiles.last_set_target_dir
            self.move_marks_to_dir(target_dir=target_dir, move_func=move_func)


    def clear_target_dirs(self, event=None):
        self.clear_widget_lists()
        MarkedFiles.mark_target_dirs.clear()
        self.filtered_target_dirs.clear()
        self.add_target_dir_widgets()
        self.master.update()


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
        res = self.alert_callback("Confirm Delete",
                f"Deleting {len(MarkedFiles.file_marks)} marked files - Are you sure you want to proceed?",
                kind="warning")
        if res != messagebox.OK:
            print(f"result was: {res}")
            return

        failed_to_delete = []
        for filepath in MarkedFiles.file_marks:
            try:
                self.delete_callback(filepath)
            except Exception as e:
                if os.path.exists(filepath):
                    failed_to_delete.append(filepath)

        MarkedFiles.file_marks.clear()
        if len(failed_to_delete) > 0:
            MarkedFiles.file_marks.extend(failed_to_delete)
            self.alert_callback("Delete Failed",
                    f"Failed to delete {len(failed_to_delete)} files - check log for details.",
                    kind="warning")

        self.refresh_callback()
        self.close_windows()

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

