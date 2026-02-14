from tkinter import Label, LEFT, W
from tkinter.ttk import Button

from lib.multi_display import SmartToplevel
from lib.tk_scroll_demo import ScrollFrame
from utils.app_style import AppStyle
from utils.translations import I18N

_ = I18N._


class MetadataViewerWindow:
    '''
    Window to hold raw metadata.
    '''
    MAX_ACTION_ROWS = 2000
    COL_0_WIDTH = 150
    top_level = None

    def __init__(self, master, app_actions, metadata_text, image_path, dimensions="600x600"):
        MetadataViewerWindow.top_level = SmartToplevel(persistent_parent=master, geometry=dimensions)
        MetadataViewerWindow.set_title(image_path)
        self.master = MetadataViewerWindow.top_level
        self.app_actions = app_actions
        self.metadata_text = metadata_text

        self.has_closed = False
        self.frame = ScrollFrame(self.master, bg_color=AppStyle.BG_COLOR)
        self.frame.pack(side="top", fill="both", expand=True)

        self._copy_btn = None
        self.add_btn("_copy_btn", _("Copy Metadata"), self.copy_metadata_to_clipboard, row=0, column=0)

        self._label_info = Label(self.frame.viewPort)
        self.add_label(self._label_info, _("Raw Image Metadata"), row=1, wraplength=MetadataViewerWindow.COL_0_WIDTH)

        self._metadata_label = Label(self.frame.viewPort)
        self.add_label(self._metadata_label, metadata_text, row=2)

        # self.master.bind("<Key>", self.filter_targets)
        # self.master.bind("<Return>", self.do_action)
        self.master.bind("<Escape>", self.close_windows)
        self.master.bind("<Control-c>", lambda e: self.copy_metadata_to_clipboard())
        self.master.protocol("WM_DELETE_WINDOW", self.close_windows)
        self.frame.after(1, lambda: self.frame.focus_force())

    def update_metadata(self, metadata_text, image_path):
        self.metadata_text = metadata_text
        self._metadata_label["text"] = metadata_text
        MetadataViewerWindow.set_title(image_path)
        self.master.update()

    def copy_metadata_to_clipboard(self):
        """Copy the raw metadata text to the clipboard."""
        try:
            self.master.clipboard_clear()
            self.master.clipboard_append(self.metadata_text)
            if self.app_actions:
                self.app_actions.success(_("Copied metadata to clipboard"))
        except Exception as e:
            if self.app_actions:
                self.app_actions.warn(_("Error copying metadata to clipboard: ") + str(e))

    @staticmethod
    def set_title(image_path):
        MetadataViewerWindow.top_level.title(_("Metadata Viewer") + " - " + image_path)

    def close_windows(self, event=None):
        self.master.destroy()
        self.has_closed = True

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

