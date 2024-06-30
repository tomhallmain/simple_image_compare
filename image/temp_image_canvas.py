import os

from PIL import Image, ImageTk
from tkinter import Toplevel, Frame, Canvas, Label

from utils.app_style import AppStyle
from utils.utils import scale_dims

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

    def __init__(self, master, title="Temp Image Canvas", dimensions="600x600", open_move_marks_window_callback=None):
        TempImageCanvas.top_level = Toplevel(master, bg=AppStyle.BG_COLOR)
        TempImageCanvas.top_level.geometry(dimensions)
        self.master = TempImageCanvas.top_level
        self.frame = Frame(master)
        self.label = Label(self.frame)
        self.master.rowconfigure(0, weight=1)
        self.master.columnconfigure(0, weight=1)
        self.master.config(bg=AppStyle.BG_COLOR)
        self.master.update()
        self.canvas = ResizingCanvas(self.master)
        self.canvas.grid(column=0, row=0)
        self.canvas.config(bg=AppStyle.BG_COLOR)
        self.image_path = None
        self.open_move_marks_window_callback = open_move_marks_window_callback

        self.master.bind("<Escape>", self.close_windows)
        self.master.bind("<Control-m>", self.open_move_marks_window)
        self.master.bind("<Control-k>", lambda event: self.open_move_marks_window(event=event, open_gui=False))
        self.master.update()
        self.master.after(1, lambda: self.master.focus_force())
    
    def close_windows(self, event=None):
        self.master.destroy()

    def create_image(self, image_path):
#        self.canvas.clear_image()
        self.image_path = image_path
        TempImageCanvas.image = self.get_image_to_fit(image_path)
        self.canvas.create_image_center(TempImageCanvas.image)
        TempImageCanvas.top_level.title(image_path)
        self.master.update()

    def get_image_to_fit(self, filename) -> ImageTk.PhotoImage:
        '''
        Get the object required to display the image in the UI.
        '''
        img = Image.open(filename)
        fit_dims = scale_dims((img.width, img.height), self.canvas.get_size(), maximize=True)
        img = img.resize(fit_dims)
        return ImageTk.PhotoImage(img)

    def open_move_marks_window(self, event=None, open_gui=True):
        assert self.open_move_marks_window_callback is not None, "No callback provided to open move marks window."
        if self.image_path is None or not os.path.isfile(self.image_path):
            raise ValueError("No image loaded.")
        self.open_move_marks_window_callback(open_gui=open_gui, override_marks=[self.image_path])
        self.close_windows()

