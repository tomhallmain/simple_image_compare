from tkinter import Frame, Label, StringVar, filedialog, LEFT, W
from tkinter.ttk import Entry, Button

from utils.app_style import AppStyle
from utils.translations import I18N

_ = I18N._


class GoToFile:

    @staticmethod
    def get_geometry():
        width = 600
        height = 100
        return f"{width}x{height}"

    def __init__(self, master, app_actions):
        self.master = master
        self.app_actions = app_actions
        self.frame = Frame(self.master)
        self.frame.grid(column=0, row=0)
        self.frame.columnconfigure(0, weight=9)
        self.frame.columnconfigure(1, weight=1)
        self.frame.config(bg=AppStyle.BG_COLOR)

        self.search_text = StringVar()
        self.search_text_box = Entry(self.frame, textvariable=self.search_text, width=50)
        self.search_text_box.grid(row=0, column=0)
        self.search_text_box.bind("<Return>", self.go_to_file)
        self.search_files_btn = None
        self.add_btn("search_files_btn", "Go To", self.go_to_file, column=1)

        self.master.bind("<Escape>", self.close_windows)
        self.frame.after(1, lambda: self.frame.focus_force())
        self.search_text_box.after(1, lambda: self.search_text_box.focus_force())

    def go_to_file(self, event=None):
        search_text = self.search_text.get()
        if search_text.strip() == "":
            self.app_actions.toast(_("Invalid search string, please enter some text."))
            return
        self.app_actions.go_to_file(search_text=search_text)
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

