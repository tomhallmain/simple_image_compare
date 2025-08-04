from tkinter import Toplevel, Frame, StringVar, LEFT, W, filedialog
from tkinter.ttk import Entry, Button

from utils.app_style import AppStyle
from utils.config import config
from utils.translations import I18N

_ = I18N._


class GoToFile:
    top_level = None
    last_search_text = ""

    @staticmethod
    def get_geometry():
        width = 700
        height = 100
        return f"{width}x{height}"

    def __init__(self, master, app_actions):
        GoToFile.top_level = Toplevel(master, bg=AppStyle.BG_COLOR)
        GoToFile.top_level.title(_("Go To File"))
        GoToFile.top_level.geometry(GoToFile.get_geometry())
        self.master = GoToFile.top_level
        self.app_actions = app_actions
        self.frame = Frame(self.master)
        self.frame.grid(column=0, row=0)
        self.frame.columnconfigure(0, weight=9)
        self.frame.columnconfigure(1, weight=1)
        self.frame.columnconfigure(2, weight=1)  # column for file picker button
        self.frame.config(bg=AppStyle.BG_COLOR)

        self.search_text = StringVar()
        self.search_text.set(GoToFile.last_search_text)
        self.search_text_box = Entry(self.frame, textvariable=self.search_text, width=50)
        self.search_text_box.grid(row=0, column=0)
        self.search_text_box.bind("<Return>", self.go_to_file)
        self.search_files_btn = None
        self.add_btn("search_files_btn", _("Go To"), self.go_to_file, column=1)
        
        self.file_picker_btn = None
        self.add_btn("file_picker_btn", _("Browse..."), self.pick_file, column=2)

        self.master.bind("<Escape>", self.close_windows)
        self.frame.after(1, lambda: self.frame.focus_force())
        self.search_text_box.after(1, lambda: self.search_text_box.focus_force())

    def go_to_file(self, event=None):
        search_text = self.search_text.get()
        if search_text.strip() == "":
            self.app_actions.toast(_("Invalid search string, please enter some text."))
            return
        GoToFile.last_search_text = search_text
        self.app_actions.go_to_file(search_text=search_text)
        self.close_windows()

    def pick_file(self, event=None):
        """Open file picker dialog and go to selected file."""
        # Create file type filter from config
        file_types = []
        if config.file_types:
            # Group extensions by type for better organization
            extensions = " ".join([f"*{ext}" for ext in config.file_types])
            file_types.append((_("Supported files"), extensions))
            # Also add individual file type groups for better organization
            if config.image_types:
                img_extensions = " ".join([f"*{ext}" for ext in config.image_types])
                file_types.append((_("Image files"), img_extensions))
            if config.enable_videos and config.video_types:
                vid_extensions = " ".join([f"*{ext}" for ext in config.video_types])
                file_types.append((_("Video files"), vid_extensions))
            if config.enable_gifs:
                file_types.append((_("GIF files"), "*.gif"))
            if config.enable_pdfs:
                file_types.append((_("PDF files"), "*.pdf"))
            if config.enable_svgs:
                file_types.append((_("SVG files"), "*.svg"))
            if config.enable_html:
                file_types.append((_("HTML files"), "*.html *.htm"))
        
        # Add "All files" option
        file_types.append((_("All files"), "*.*"))
        
        selected_file = filedialog.askopenfilename(
            title=_("Select file to go to"),
            filetypes=file_types,
            initialdir=self.app_actions.get_base_dir() if hasattr(self.app_actions, 'get_base_dir') else "."
        )
        
        if selected_file:
            # Set the selected file path in the search box
            self.search_text.set(selected_file)
            # Go to the selected file
            self.go_to_file()

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

