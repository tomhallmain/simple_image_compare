import os

from tkinter import Frame, Label, StringVar, filedialog, LEFT, W
from tkinter.font import Font
from tkinter.ttk import Entry, Button

from config import config
from image_data_extractor import image_data_extractor
from app_style import AppStyle
from utils import move_file, copy_file


class MarkedFiles():
    file_marks = []
    mark_target_dirs = []
    last_set_target_dir = None
    mark_cursor = -1

    def __init__(self, master, toast_callback, refresh_callback, base_dir="."):
        self.master = master
        self.toast_callback = toast_callback
        self.refresh_callback = refresh_callback
        # Use the last set target directory as a base if any directories have been set
        if MarkedFiles.last_set_target_dir and os.path.isdir(MarkedFiles.last_set_target_dir):
            self.base_dir = MarkedFiles.last_set_target_dir
        else:
            self.base_dir = base_dir
        self.frame = Frame(self.master)
        self.frame.grid(column=0, row=0)
        self.frame.columnconfigure(0, weight=9)
        self.frame.columnconfigure(1, weight=1)
        self.frame.columnconfigure(2, weight=1)
        self.frame.config(bg=AppStyle.BG_COLOR)
        col_0_width = 600

        self.move_button_list = []
        self.copy_button_list = []
        self.label_list = []
        for i in range(len(MarkedFiles.mark_target_dirs)):
            target_dir = MarkedFiles.mark_target_dirs[i]
            self._label_info = Label(self.frame)
            self.add_label(self._label_info, target_dir, row=i+1, wraplength=col_0_width)

            move_button = Button(self.frame, text="Move")
            self.move_button_list.append(move_button)
            move_button.grid(row=i+1, column=1)
            def move_handler(event, self=self, target_dir=target_dir):
                return self.move_marks_to_dir(event, target_dir)
            move_button.bind("<Button-1>", move_handler)

            copy_button = Button(self.frame, text="Copy")
            self.copy_button_list.append(copy_button)
            copy_button.grid(row=i+1, column=2)
            def copy_handler(event, self=self, target_dir=target_dir):
                return self.move_marks_to_dir(event, target_dir, move_func=copy_file)
            copy_button.bind("<Button-1>", copy_handler)


        self._label_info = Label(self.frame)
        self.add_label(self._label_info, "Set a new target directory", row=0, wraplength=col_0_width)
        self.add_directory_move_button = None
        self.add_button("add_directory_move_button", "(move)", self.get_target_directory, column=1)
        def copy_handler_new_dir(event=None, self=self):
            self.get_target_directory(move_func=copy_file)
        self.add_directory_copy_button = None
        self.add_button("add_directory_copy_button", "(copy)", copy_handler_new_dir, column=2)

        self.master.bind("<Shift-W>", self.close_windows)
        self.frame.after(1, lambda: self.frame.focus_force())


    def get_target_directory(self, event=None, target_dir=None, move_func=move_file):
        if target_dir:
            if os.path.isdir(target_dir):
                return target_dir
            else:
                if target_dir in MarkedFiles.mark_target_dirs:
                    MarkedFiles.mark_target_dirs.remove(target_dir)
                self.toast_callback(f"Invalid directory: {target_dir}")
        target_dir = filedialog.askdirectory(
                initialdir=self.base_dir, title="Select target directory for marked files")
        if not os.path.isdir(target_dir):
            self.close_windows()
            raise Exception("Failed to set target directory to receive marked files.")

        MarkedFiles.mark_target_dirs.append(target_dir)
        self.move_marks_to_dir(target_dir=target_dir, move_func=move_func)


    def move_marks_to_dir(self, event=None, target_dir=None, move_func=move_file):
        target_dir = self.get_target_directory(target_dir=target_dir)
        is_moving = move_func == move_file
        action_part1 = "Moving" if is_moving else "Copying"
        action_part2 = "Moved" if is_moving else "Copied"
        print(f"{action_part1}ing {len(MarkedFiles.file_marks)} files to directory:\n{target_dir}")
        exceptions = {}
        invalid_files = []
        for marked_file in MarkedFiles.file_marks:
            try:
                move_func(marked_file, target_dir, overwrite_existing=config.move_marks_overwrite_existing_file)
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
        self.refresh_callback()
        self.close_windows()


    def close_windows(self, event=None):
        self.master.destroy()

    def add_label(self, label_ref, text, row=0, column=0, wraplength=500):
        label_ref['text'] = text
        label_ref.grid(column=column, row=row, sticky=W)
        label_ref.config(wraplength=wraplength, justify=LEFT, bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)

    def add_button(self, button_ref_name, text, command, row=0, column=0):
        if getattr(self, button_ref_name) is None:
            button = Button(master=self.frame, text=text, command=command)
            setattr(self, button_ref_name, button)
            button # for some reason this is necessary to maintain the reference?
            button.grid(row=row, column=column)

