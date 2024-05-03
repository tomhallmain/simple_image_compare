import os

from tkinter import Frame, Label, StringVar, filedialog, LEFT, W
from tkinter.font import Font
from tkinter.ttk import Entry, Button

from config import config
from image_data_extractor import image_data_extractor
from app_style import AppStyle
from utils import move_file


class MarkedFiles():
    file_marks = []
    mark_target_dirs = []
    mark_cursor = -1

    def __init__(self, master, toast_callback, refresh_callback, base_dir="."):
        self.master = master
        self.toast_callback = toast_callback
        self.refresh_callback = refresh_callback
        self.base_dir = base_dir
        self.frame = Frame(self.master)
        self.frame.grid(column=0, row=0)
        self.frame.columnconfigure(0, weight=1)
        self.frame.columnconfigure(0, weight=9)
        self.frame.config(bg=AppStyle.BG_COLOR)
        col_0_width = 600

        self.button_list = []  # Create the checkbutton list
        self.label_list = []
        for i in range(len(MarkedFiles.mark_target_dirs)):
            target_dir = MarkedFiles.mark_target_dirs[i]
            self._label_info = Label(self.frame)
            self.add_label(self._label_info, target_dir, row=i+1, wraplength=col_0_width)
            button = Button(self.frame, text="Move")
            self.button_list.append(button)
            button.grid(row=i+1, column=1)
            def handler(event, self=self, target_dir=target_dir):  # [1]
                return self.move_marks_to_dir(event, target_dir)
            button.bind("<Button-1>", handler)

        self._label_info = Label(self.frame)
        self.add_label(self._label_info, "Mark Target Directories", row=0, wraplength=col_0_width)
        self.add_directory_button = None
        self.add_button("add_directory_button", "Set new target directory", self.get_target_directory, column=1)

        self.master.bind("<Shift-W>", self.close_windows)
        self.frame.after(1, lambda: self.frame.focus_force())


    def get_target_directory(self, event=None, target_dir=None):
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
        self.move_marks_to_dir(target_dir=target_dir)
#        return target_dir # NOTE technically don't need to return anything here, as it will be unused in this case


    def move_marks_to_dir(self, event=None, target_dir=None):
        target_dir = self.get_target_directory(target_dir=target_dir)
        print(f"Moving {len(MarkedFiles.file_marks)} files to directory:\n{target_dir}")
        exceptions = {}
        for marked_file in MarkedFiles.file_marks:
            try:
                move_file(marked_file, target_dir, overwrite_existing=config.move_marks_overwrite_existing_file)
            except Exception as e:
                exceptions[marked_file] = str(e)
        if len(exceptions) < len(MarkedFiles.file_marks):
            self.toast_callback(f"Moved {len(MarkedFiles.file_marks) - len(exceptions)} files to\n{target_dir}")
        MarkedFiles.file_marks.clear()
        MarkedFiles.file_marks.extend(exceptions.keys()) # Just in case some of them failed to move for whatever reason.
        if len(exceptions) > 0:
            raise Exception(f"Failed to move some files: {exceptions}")
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

