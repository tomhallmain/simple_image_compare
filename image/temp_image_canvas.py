import os
import sys

from PIL import Image, ImageTk
from tkinter import Toplevel, Frame, Canvas, Label

from files.marked_file_mover import MarkedFiles
from image.frame_cache import FrameCache
from utils.config import config
from utils.app_style import AppStyle
from utils.utils import Utils
from utils.translations import I18N

_ = I18N._

class ResizingCanvas(Canvas):
    '''
    Create a Tk Canvas that auto-resizes its components.
    '''

    def __init__(self, parent, **kwargs):
        Canvas.__init__(self, parent, **kwargs)
        self.bind("<Configure>", self.on_resize)
        self.parent = parent
        self.height = parent.winfo_height()
        self.width = parent.winfo_width()

    def on_resize(self, event):
        # determine the ratio of old width/height to new width/height
        wscale = float(event.width)/self.width
        hscale = float(event.height)/self.height
        self.width = event.width
        self.height = event.height
        # resize the canvas
        self.config(width=self.width, height=self.height)
        # rescale all the objects tagged with the "all" tag
        self.scale("all", 0, 0, wscale, hscale)

    def get_size(self):
        return (self.width, self.height)

    def get_center_coordinates(self):
        return (self.width/2, self.height/2)

    def create_image_center(self, img):
        self.create_image(self.get_center_coordinates(), image=img, anchor="center", tags=("_"))

    def clear_image(self):
        self.delete("_")

class TempImageCanvas:
    top_level = None
    image = None

    def __init__(self, master, title="Temp Image Canvas", dimensions="600x600", app_actions=None):
        TempImageCanvas.top_level = Toplevel(master, bg=AppStyle.BG_COLOR)
        TempImageCanvas.top_level.geometry(dimensions)
        self.master = TempImageCanvas.top_level
#        self.app_master = master
        self.frame = Frame(self.master)
        self.label = Label(self.frame)
        self.master.rowconfigure(0, weight=1)
        self.master.columnconfigure(0, weight=1)
        self.master.config(bg=AppStyle.BG_COLOR)
        self.master.update()
        self.canvas = ResizingCanvas(self.master)
        self.canvas.grid(column=0, row=0)
        self.canvas.config(bg=AppStyle.BG_COLOR)
        self.image_path = None
        self.app_actions = app_actions
        assert self.app_actions is not None

        self.master.bind("<Escape>", self.app_actions.refocus)
        self.master.bind("<Shift-Escape>", self.close_windows)
        self.master.bind("<Shift-D>", lambda event: self.app_actions.get_media_details(media_path=self.image_path))
        self.master.bind("<Shift-I>", lambda event: self.app_actions.run_image_generation(_type=None, image_path=self.image_path))
        self.master.bind("<Button-3>", lambda event: self.app_actions.run_image_generation(_type=None, image_path=self.image_path))
        self.master.bind("<Shift-Y>", lambda event: self.app_actions.set_marks_from_downstream_related_images(image_to_use=self.image_path))
        self.master.bind("<Control-m>", self.open_move_marks_window)
        self.master.bind("<Control-k>", lambda event: self.open_move_marks_window(event=event, open_gui=False))
        self.master.bind("<Control-r>", self.run_previous_marks_action)
        self.master.bind("<Control-e>", self.run_penultimate_marks_action)
        self.master.bind("<Shift-C>", self.copy_file_to_base_dir)
        self.master.bind("<Control-c>", self.copy_image_path) # TODO replace this with copy data instead of just path
        self.master.bind("<Control-t>", self.run_permanent_marks_action)
        self.master.bind("<Control-w>", self.new_full_window_with_image)
        self.master.update()

    def close_windows(self, event=None):
        self.master.destroy()

    def create_image(self, media_path, extra_text=None):
        self.image_path = FrameCache.get_image_path(media_path)
        TempImageCanvas.image = self.get_image_to_fit(media_path)
        self.canvas.create_image_center(TempImageCanvas.image)
        title = media_path if extra_text is None else media_path + " - " + extra_text
        TempImageCanvas.top_level.title(title)
        self.master.update()
        self.master.after(1, lambda: self.master.focus_force())

    def clear_image(self):
        self.canvas.clear_image()
        self.image_path = None
        TempImageCanvas.top_level.title(_("Open a new related image with Shift+R on main window"))

    def get_image_to_fit(self, filename) -> ImageTk.PhotoImage:
        '''
        Get the object required to display the image in the UI.
        '''
        img = Image.open(filename)
        fit_dims = Utils.scale_dims((img.width, img.height), self.canvas.get_size(), maximize=True)
        img = img.resize(fit_dims)
        return ImageTk.PhotoImage(img)

    def open_move_marks_window(self, event=None, open_gui=True):
        if self.image_path is None or not os.path.isfile(self.image_path):
            raise ValueError("No image loaded.")
        self.app_actions.open_move_marks_window(open_gui=open_gui, override_marks=[self.image_path])
        self.clear_image()

    def run_previous_marks_action(self, event=None):
        if self.image_path is None or not os.path.isfile(self.image_path):
            raise ValueError("No image loaded.")
        MarkedFiles.file_marks.append(self.image_path)
        some_files_already_present, exceptions_present = MarkedFiles.run_previous_action(self.app_actions)
        if not exceptions_present:
            self.clear_image()

    def run_penultimate_marks_action(self, event=None):
        if self.image_path is None or not os.path.isfile(self.image_path):
            raise ValueError("No image loaded.")
        MarkedFiles.file_marks.append(self.image_path)
        some_files_already_present, exceptions_present = MarkedFiles.run_penultimate_action(self.app_actions)
        if not exceptions_present:
            self.clear_image()

    def run_permanent_marks_action(self, event=None):
        if self.image_path is None or not os.path.isfile(self.image_path):
            raise ValueError("No image loaded.")
        MarkedFiles.file_marks.append(self.image_path)
        some_files_already_present, exceptions_present = MarkedFiles.run_permanent_action(self.app_actions)
        if not exceptions_present:
            self.clear_image()

    def copy_image_path(self, event=None):
        if self.image_path is None or not os.path.isfile(self.image_path):
            raise ValueError("No image loaded.")
        filepath = str(self.image_path)
        if sys.platform == 'win32':
            filepath = os.path.normpath(filepath)
            if config.escape_backslash_filepaths:
                filepath = filepath.replace("\\", "\\\\")
        self.master.clipboard_clear()
        self.master.clipboard_append(filepath)

    def copy_file_to_base_dir(self, event=None):
        if self.image_path is None or not os.path.isfile(self.image_path):
            raise ValueError("No image loaded.")
        base_dir = self.app_actions.get_base_dir()
        current_image_dir = os.path.dirname(self.image_path)
        if base_dir is not None and base_dir != "" and os.path.normpath(base_dir) != os.path.normpath(current_image_dir):
            filepath = str(self.image_path)
            new_file = os.path.join(base_dir, os.path.basename(filepath))
            Utils.copy_file(filepath, new_file, overwrite_existing=config.move_marks_overwrite_existing_file)

    def new_full_window_with_image(self, event=None):
        if self.image_path is None or not os.path.isfile(self.image_path):
            raise ValueError("No image loaded.")
        base_dir = os.path.dirname(self.image_path)
        self.app_actions.new_window(base_dir=base_dir, image_path=self.image_path)
        self.close_windows()

