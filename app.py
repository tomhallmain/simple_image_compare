from enum import Enum
import os
import sys
import time

import pprint

try:
    from send2trash import send2trash
except Exception:
    print("Could not import trashing utility - all deleted images will be deleted instantly")

import tkinter as tk
from tkinter import Canvas, PhotoImage, filedialog, messagebox, HORIZONTAL, Label, Checkbutton
from tkinter.constants import W
import tkinter.font as fnt
from tkinter.ttk import Button, Entry, Frame, OptionMenu, Progressbar
from ttkthemes import ThemedTk
from PIL import ImageTk, Image

from compare import Compare, get_valid_file
from config import config
from file_browser import FileBrowser, SortBy
from image_details import ImageDetails # must import after config because of dynamic import
from style import Style
from utils import (
    _wrap_text_to_fit_length, get_user_dir, scale_dims, get_relative_dirpath_split, open_file_location, periodic, start_thread
)


### TODO image zoom feature
### TODO copy/cut image using hotkey (pywin32 ? win32com? IDataPobject?)
### TODO comfyui plugin for ipadapter/controlnet (maybe)
### TODO some type of plugin to filter the images using a filter function defined externally
### TODO compare option to restrict by matching image dimensions
### TODO compare option encoding size
### TODO add checkbox for include gif option
### TODO tkVideoPlayer or tkVideoUtils for playing videos
### TODO custom frame class for sidebar to hold all the buttons


class Mode(Enum):
    BROWSE = 1
    SEARCH = 2
    GROUP = 3
    DUPLICATES = 4

class ResizingCanvas(Canvas):
    '''
    Create a Tk Canvas that auto-resizes its components.
    '''

    def __init__(self, parent, **kwargs):
        Canvas.__init__(self, parent, **kwargs)
        self.bind("<Configure>", self.on_resize)
        self.parent = parent
        self.height = parent.winfo_height()
        self.width = parent.winfo_width() * 9/10

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
        return (self.width/2, (self.height)/2)

    def create_image_center(self, img):
        self.create_image(self.get_center_coordinates(), image=img, anchor="center", tags=("_"))

    def clear_image(self):
        self.delete("_")


class Sidebar(tk.Frame):
    def __init__(self, master=None, cnf={}, **kw):
        tk.Frame.__init__(self, master=master, cnf=cnf, **kw)


class GifImageUI:
    def __init__(self, filename):
        im = Image.open(filename)
        self.n_frames = im.n_frames
        self.frames = [PhotoImage(file=filename, format='gif -index %i' % (i))
                       for i in range(self.n_frames)]
        self.active = False
        self.canvas = None

    def display(self, canvas):
        self.active = True
        self.canvas = canvas
        self.update(0)

    def stop_display(self):
        self.active = False

    def update(self, ind):
        if self.active:
            frame = self.frames[ind]
            ind += 1
            if ind == self.n_frames:
                ind = 0
            # TODO inefficient to use canvas here, better to use Label.configure
            self.canvas.create_image_center(frame)
            root.after(100, self.update, ind)


class ProgressListener:
    def __init__(self, update_func):
        self.update_func = update_func

    def update(self, context, percent_complete):
        self.update_func(context, percent_complete)


class SlideshowConfig:
    slideshow_running = False
    show_new_images = False
    interval_seconds = config.slideshow_interval_seconds

    @staticmethod
    def toggle_slideshow():
        if SlideshowConfig.show_new_images:
            SlideshowConfig.show_new_images = False
        elif SlideshowConfig.slideshow_running:
            SlideshowConfig.show_new_images = True
            SlideshowConfig.slideshow_running = False
        else:
            SlideshowConfig.slideshow_running = True


class App():
    '''
    UI for comparing image files and making related file changes.
    '''

    compare = None
    file_browser = FileBrowser(recursive=config.image_browse_recursive, sort_by=config.sort_by)
    mode = Mode.BROWSE
    fill_canvas = config.fill_canvas
    fullscreen = False
    search_file_path = ""
    img = None
    img_path = None
    files_grouped = {}
    file_groups = {}
    files_matched = []
    search_image_full_path = None
    has_image_matches = False
    current_group = None
    current_group_index = 0
    match_index = 0
    group_indexes = []
    max_group_index = 0
    is_toggled_view_matches = True
    has_added_buttons_for_mode = {
        Mode.BROWSE: False,
        Mode.GROUP: False, 
        Mode.SEARCH: False, 
        Mode.DUPLICATES: False
    }

    def configure_style(self, theme):
        self.master.set_theme(theme, themebg="black")

    def toggle_theme(self):
        if Style.IS_DEFAULT_THEME:
            self.configure_style("breeze") # Changes the window to light theme
            Style.BG_COLOR = "gray"
            Style.FG_COLOR = "black"
        else:
            self.configure_style("black") # Changes the window to dark theme
            Style.BG_COLOR = "#26242f"
            Style.FG_COLOR = "white"
        Style.IS_DEFAULT_THEME = not Style.IS_DEFAULT_THEME
        self.master.config(bg=Style.BG_COLOR)
        self.sidebar.config(bg=Style.BG_COLOR)
        self.canvas.config(bg=Style.BG_COLOR)
        for name, attr in self.__dict__.items():
            if isinstance(attr, Label):
                attr.config(bg=Style.BG_COLOR, fg=Style.FG_COLOR)
            elif isinstance(attr, Checkbutton):
                attr.config(bg=Style.BG_COLOR, fg=Style.FG_COLOR, selectcolor=Style.BG_COLOR)
        self.master.update()
        self.toast("Theme switched to dark." if Style.IS_DEFAULT_THEME else "Theme switched to light.")


    def __init__(self, master):
        self.master = master
        self.config = config
        self.base_dir = get_user_dir()
        self.search_dir = get_user_dir()

        # Sidebar
        self.sidebar = Sidebar(self.master)
        self.sidebar.columnconfigure(0, weight=1)
        self.row_counter = 0
        self.sidebar.grid(column=0, row=self.row_counter)

        # The top part is a label with info
        self.label_mode = Label(self.sidebar)
        self.label_state = Label(self.sidebar)
        self.label1 = Label(self.sidebar)
        self.add_label(self.label_mode, "", sticky=tk.N)
        self.add_label(self.label_state, "Set a directory to run comparison.", pady=20)

        # Settings UI
        self.add_label(self.label1, "Controls & Settings", sticky=None, pady=30)
        self.set_base_dir_btn = None
        self.create_img_btn = None
        self.toggle_theme_btn = None
        self.add_button("toggle_theme_btn", "Toggle theme", self.toggle_theme)
        self.add_button("set_base_dir_btn", "Set directory", self.set_base_dir)
        self.set_base_dir_box = self.new_entry(None, text="Add dirpath...")
        self.apply_to_grid(self.set_base_dir_box)

        self.add_button("create_img_btn", "Set search file", self.set_search_image)
        self.search_image = tk.StringVar()
        self.create_img_path_box = self.new_entry(self.search_image)
        self.apply_to_grid(self.create_img_path_box, sticky=W)

        self.label_color_diff_threshold = Label(self.sidebar)
        self.add_label(self.label_color_diff_threshold, "Color diff threshold")
        self.color_diff_threshold = tk.StringVar(master)
        self.color_diff_threshold_choice = OptionMenu(self.sidebar, self.color_diff_threshold,
                                                      str(self.config.color_diff_threshold),
                                                      *[str(i) for i in list(range(31))])
        self.apply_to_grid(self.color_diff_threshold_choice, sticky=W)

        self.compare_faces = tk.BooleanVar(value=False)
        self.compare_faces_choice = Checkbutton(self.sidebar, text='Compare faces', variable=self.compare_faces)
        self.apply_to_grid(self.compare_faces_choice, sticky=W)

        self.overwrite = tk.BooleanVar(value=False)
        self.overwrite_choice = Checkbutton(self.sidebar, text='Overwrite cache', variable=self.overwrite)
        self.apply_to_grid(self.overwrite_choice, sticky=W)

        self.label_counter_limit = Label(self.sidebar)
        self.add_label(self.label_counter_limit, "Max # of files to compare")
        self.set_counter_limit = self.new_entry(None)
        self.set_counter_limit.insert(0, str(self.config.file_counter_limit))
        self.apply_to_grid(self.set_counter_limit, sticky=W)

        self.label_inclusion_pattern = Label(self.sidebar)
        self.add_label(self.label_inclusion_pattern, "Filter files by string in name")
        self.inclusion_pattern = tk.StringVar()
        self.set_inclusion_pattern = self.new_entry(self.inclusion_pattern)
        self.apply_to_grid(self.set_inclusion_pattern, sticky=W)

        self.label_sort_by = Label(self.sidebar)
        self.add_label(self.label_sort_by, "Sort for files in browsing mode")
        self.sort_by = tk.StringVar(master)
        self.sort_by_choice = OptionMenu(self.sidebar, self.sort_by, self.config.sort_by.name,
                                         *SortBy.__members__.keys(), command=self.set_sort_by)
        self.apply_to_grid(self.sort_by_choice, sticky=W)

        fill_canvas_var = tk.BooleanVar(value=App.fill_canvas)
        self.fill_canvas_choice = Checkbutton(self.sidebar, text='Image resize to full window',
                                              variable=fill_canvas_var, command=App.toggle_fill_canvas)
        self.apply_to_grid(self.fill_canvas_choice, sticky=W)

        image_browse_recurse_var = tk.BooleanVar(value=self.config.image_browse_recursive)
        self.image_browse_recurse = Checkbutton(self.sidebar, text='Image browsing recursive',
                                                variable=image_browse_recurse_var, command=self.toggle_image_browse_recursive)
        self.apply_to_grid(self.image_browse_recurse, sticky=W)


        # Run context-aware UI elements
        self.progress_bar = None
        self.run_compare_btn = None
        self.add_button("run_compare_btn", "Run image compare", self.run_compare)
        self.find_duplicates_btn = None
        self.add_button("find_duplicates_btn", "Find duplicates", self.find_duplicates)
        self.image_details_btn = None
        self.add_button("image_details_btn", "Image details", self.get_image_details)
        self.prev_image_match_btn = None
        self.next_image_match_btn = None
        self.prev_group_btn = None
        self.next_group_btn = None
        self.toggle_image_view_btn = None
        self.replace_current_image_btn = None
        self.search_current_image_btn = None
        self.label_current_image_name = None
        self.rename_image_btn = None
        self.delete_image_btn = None
        self.open_image_location_btn = None
        self.copy_image_path_btn = None
        self.add_button("search_current_image_btn", "Search current image", self.set_current_image_run_search)
        self.add_button("open_image_location_btn", "Open image location", self.open_image_location)
        self.add_button("copy_image_path_btn", "Copy image path", self.copy_image_path)
        self.add_button("delete_image_btn", "---- DELETE ----", self.delete_image)

        # Image panel and state management
        self.master.update()
        self.canvas = ResizingCanvas(self.master)
        self.canvas.grid(column=1, row=0)

        # Default mode is BROWSE - GROUP and SEARCH are only valid modes when a compare is run
        self.set_mode(Mode.BROWSE)

        # Key bindings
        self.master.bind('<Left>', self.show_prev_image_key)
        self.master.bind('<Right>', self.show_next_image_key)
        self.master.bind('<Shift-Left>', self.show_prev_group)
        self.master.bind('<Shift-Right>', self.show_next_group)
        self.master.bind('<Shift-Enter>', self.open_image_location)
        self.master.bind('<Shift-Delete>', self._delete_image)
        self.master.bind("<F11>", self.toggle_fullscreen)
        self.master.bind("<Shift-F>", self.toggle_fullscreen)
        self.master.bind("<Escape>", self.end_fullscreen)
        self.master.bind("<Shift-D>", self.get_image_details)
        self.master.bind("<Shift-S>", self.toggle_slideshow)
        self.master.bind("<MouseWheel>", self.handle_mousewheel)
        self.master.bind("<Button-2>", self._delete_image)

        # Start async threads
        start_thread(self.check_files)

        self.toggle_theme()
        self.master.update()

    def toggle_fullscreen(self, event=None):
        App.fullscreen = not App.fullscreen
        self.master.attributes("-fullscreen", App.fullscreen)
        if App.fullscreen:
            self.sidebar.grid_remove()
        else:
            self.sidebar.grid()
        return "break"

    def end_fullscreen(self, event=None):
        if App.fullscreen:
            self.toggle_fullscreen()
        return "break"

    def set_mode(self, mode, do_update=True):
        '''
        Change the current mode of the application.
        '''
        App.mode = mode
        self.label_mode['text'] = f"Mode: {mode}"

        if mode == Mode.GROUP:
            self.toggle_image_view_btn = None
            self.replace_current_image_btn = None
        if mode == Mode.SEARCH:
            self.prev_group_btn = None
            self.next_group_btn = None
        if mode == Mode.BROWSE:
            self.toggle_image_view_btn = None
            self.replace_current_image_btn = None
            self.prev_group_btn = None
            self.next_group_btn = None

        if do_update:
            self.master.update()

    def set_sort_by(self, event):
        App.file_browser.set_sort_by(SortBy[self.sort_by.get()])
        App.file_browser.refresh()
        if App.mode == Mode.BROWSE:
            self.show_next_image()

    @classmethod
    def toggle_fill_canvas(cls):
        cls.fill_canvas = not cls.fill_canvas

    def toggle_image_browse_recursive(self):
        self.file_browser.toggle_recursive()
        if App.mode == Mode.BROWSE and App.img:
            self.show_next_image()

    @periodic(config.file_check_interval_seconds)
    async def check_files(self, **kwargs):
        if App.file_browser.checking_files and App.mode == Mode.BROWSE:
            base_dir = self.set_base_dir_box.get()
            if base_dir and base_dir != "":
                App.file_browser.refresh(refresh_cursor=False, file_check=True)
                if App.file_browser.has_files():
                    if SlideshowConfig.show_new_images:
                        self.file_browser.update_cursor_to_new_images()
                    self.show_next_image()
                else:
                    self.clear_image()
                    self.alert("Warning", "No files found in direcftory after refresh.", kind="warning")
                print("Refreshed files")

    @periodic(SlideshowConfig, sleep_attr="interval_seconds", run_attr="slideshow_running")
    async def do_slideshow(self, **kwargs):
        if SlideshowConfig.slideshow_running and App.mode == Mode.BROWSE:
            print("Slideshow next image")
            base_dir = self.set_base_dir_box.get()
            if base_dir and base_dir != "":
                self.show_next_image()

    def toggle_slideshow(self, event=None):
        SlideshowConfig.toggle_slideshow()
        if SlideshowConfig.show_new_images:
            message = "Slideshow for new images started"
        elif SlideshowConfig.slideshow_running:
            message = "Slideshow started"
            start_thread(self.do_slideshow)
        else:
            message = "Slideshows ended"
        self.toast(message)

    def handle_mousewheel(self, event):
        if event.delta > 0:
            self.show_next_image()
        else:
            self.show_prev_image()

    def get_image_details(self, event=None):
        top_level = tk.Toplevel(self.master, bg=Style.BG_COLOR)
        top_level.title("Image Details")
        top_level.geometry("600x300")
        try:
            image_details = ImageDetails(top_level, App.img, App.img_path, self.config.sd_prompt_reader_loc)
        except Exception as e:
            self.alert("Image Details Error", str(e), kind="error")

    def set_base_dir(self) -> None:
        '''
        Change the base directory to the value provided in the UI.
        '''
        base_dir = self.set_base_dir_box.get()
        if base_dir == "" or base_dir == "Add dirpath..." or self.base_dir == base_dir:
            base_dir = filedialog.askdirectory(
                initialdir=self.get_base_dir(), title="Set image comparison directory")
        self.base_dir = get_valid_file(self.base_dir, base_dir)
        if self.base_dir is None:
            self.base_dir = filedialog.askdirectory(
                initialdir=self.get_base_dir(), title="Set image comparison directory")
        if App.compare is not None and self.base_dir != App.compare.base_dir:
            App.compare = None
            self.set_group_state_label(None, 0)
            self.remove_all_mode_buttons()
            if App.mode != Mode.SEARCH:
                self.clear_image()
            elif App.is_toggled_view_matches:
                self.toggle_image_view()
        self.set_base_dir_box.delete(0, "end")
        self.set_base_dir_box.insert(0, self.base_dir)
        App.file_browser.set_directory(self.base_dir)
        if App.compare is None and App.mode != Mode.SEARCH:
            self.set_mode(Mode.BROWSE)
            self.show_next_image()
        self.master.update()

    def get_base_dir(self) -> str:
        return "." if (self.base_dir is None
                       or self.base_dir == "") else self.base_dir

    def get_search_dir(self) -> str:
        return self.get_base_dir() if self.search_dir is None else self.search_dir

    def get_search_file_path(self) -> str | None:
        '''
        Get the search file path provided in the UI.
        '''
        image_path = self.search_image.get()
        if image_path is None or image_path == "":
            App.search_image_full_path = None
            return None

        search_file_str = App.search_image_full_path
        if search_file_str == "":
            return None

        search_file = get_valid_file(self.get_base_dir(), image_path)
        if search_file is None:
            search_file = get_valid_file(
                self.get_search_dir(), image_path)
            if image_path is None:
                self.alert("Invalid search file",
                           "Search file is not a valid file for base dir.",
                           kind="error")
                raise AssertionError(
                    "Search file is not a valid file for base dir.")

        return search_file

    def get_counter_limit(self) -> int | None:
        counter_limit_str = self.set_counter_limit.get()
        if counter_limit_str == "":
            return None
        try:
            return int(counter_limit_str)
        except Exception:
            self.alert("Invalid Setting",
                       "Counter limit must be an integer value.", kind="error")
            raise AssertionError("Counter limit must be an integer value.")

    def get_color_diff_threshold(self) -> int | None:
        color_diff_threshold_str = self.color_diff_threshold.get()
        if color_diff_threshold_str == "":
            return None
        try:
            return int(color_diff_threshold_str)
        except Exception:
            return self.config.color_diff_threshold

    def get_inclusion_pattern(self) -> str | None:
        inclusion_pattern = self.inclusion_pattern.get()
        if inclusion_pattern == "":
            return None
        else:
            return inclusion_pattern

    def get_image_to_fit(self, filename) -> ImageTk.PhotoImage:
        '''
        Get the object required to display the image in the UI.
        '''
        if filename.endswith(".gif"):
            return GifImageUI(filename)

        img = Image.open(filename)
        fit_dims = scale_dims((img.width, img.height), self.canvas.get_size(), maximize=App.fill_canvas)
        img = img.resize(fit_dims)
        return ImageTk.PhotoImage(img)

    def set_search_image(self) -> None:
        '''
        Set the search image using the provided UI value, or prompt the
        user for selection. Set the mode based on the result.
        '''
        image_path = self.get_search_file_path()

        if image_path is None or (App.search_image_full_path is not None
                                  and image_path == App.search_image_full_path):
            image_path = filedialog.askopenfilename(
                initialdir=self.get_search_dir(), title="Select image file",
                filetypes=[("Image files", "*.jpg *.jpeg *.png *.tiff *.gif")])

        if image_path is not None and image_path != "":
            self.search_image.set(os.path.basename(image_path))
            self.search_dir = os.path.dirname(image_path)
            App.search_image_full_path = image_path
            self.show_searched_image()

        if App.search_image_full_path is None or App.search_image_full_path == "":
            if self.mode != Mode.BROWSE:
                self.set_mode(Mode.GROUP)
        else:
            self.set_mode(Mode.SEARCH)

        self.master.update()

        if App.compare is not None:
           self.run_compare()

    def show_searched_image(self) -> None:
        if App.search_image_full_path is not None and App.search_image_full_path != "":
            if os.path.isfile(App.search_image_full_path):
                self.create_image(App.search_image_full_path, extra_text="(search image)")
            else:
                self.alert("Error", "Somehow, the search file is invalid", kind="error")

    def show_prev_image_key(self, event) -> None:
        self.show_prev_image(False)

    def show_prev_image(self, show_alert=True) -> None:
        '''
        If similar image results are present in any mode, display the previous
        in the list of matches.
        '''
        if App.mode == Mode.BROWSE:
            self.master.update()
            self.create_image(App.file_browser.previous_file())
            return
        if App.files_matched is None:
            return
        elif len(App.files_matched) == 0:
            if show_alert:
                self.alert("Search required",
                           "No matches found. Search again to find potential matches.",
                           kind="info")
            return

        App.is_toggled_view_matches = True
        
        if App.match_index > 0:
            App.match_index -= 1
        else:
            App.match_index = len(App.files_matched) - 1
        
        self.master.update()
        self.create_image(App.files_matched[App.match_index])

    def show_next_image_key(self, event) -> None:
        self.show_next_image(False)

    def show_next_image(self, show_alert=True) -> None:
        '''
        If similar image results are present in any mode, display the next
        in the list of matches.
        '''
        if App.mode == Mode.BROWSE:
            self.master.update()
            try:
                self.create_image(App.file_browser.next_file())
            except Exception as e:
                self.alert("Exception", str(e))
            return
        if App.files_matched is None:
            return
        elif len(App.files_matched) == 0:
            if show_alert:
                self.alert("Search required",
                           "No matches found. Search again to find potential matches.",
                           kind="info")
            return

        App.is_toggled_view_matches = True

        if len(App.files_matched) > App.match_index + 1:
            App.match_index += 1
        else:
            App.match_index = 0

        self.master.update()
        self.create_image(App.files_matched[App.match_index])

    def show_prev_group(self, event=None) -> None:
        '''
        While in group mode, navigate to the previous group.
        '''
        if (App.file_groups is None or len(App.group_indexes) == 0
                or App.current_group_index == max(App.group_indexes)):
            App.current_group_index = 0
        else:
            App.current_group_index -= 1

        self.set_current_group()

    def show_next_group(self, event=None) -> None:
        '''
        While in group mode, navigate to the next group.
        '''
        if (App.file_groups is None or len(App.group_indexes) == 0
                or App.current_group_index + 1 == len(App.group_indexes)):
            App.current_group_index = 0
        else:
            App.current_group_index += 1

        self.set_current_group()

    def set_current_group(self) -> None:
        '''
        While in group mode, navigate between the groups.
        '''
        if App.mode == Mode.SEARCH:
            self.alert("Error", "Invalid action, there should only be one group in search mode", kind="error")
            return
        if App.file_groups is None or len(App.file_groups) == 0:
            self.toast("No groups found")
            return

        actual_group_index = App.group_indexes[App.current_group_index]
        App.current_group = App.file_groups[actual_group_index]
        App.match_index = 0
        App.files_matched = []

        for f in sorted(App.current_group, key=lambda f: App.current_group[f]):
            App.files_matched.append(f)

        self.set_group_state_label(App.current_group_index, len(App.files_matched))
        self.master.update()
        self.create_image(App.files_matched[App.match_index])

    def set_current_image_run_search(self) -> None:
        '''
        Execute a new image search from the provided search image.
        '''
        if App.mode != Mode.BROWSE:
            if not App.has_image_matches:
                self.alert("Search required",
                    "No matches found. Search again to find potential matches.",
                    kind="info")
                return
            search_image_path = self.search_image.get()
            search_image_path = get_valid_file(
                self.get_base_dir(), search_image_path)
            if (App.files_matched is None or search_image_path == App.files_matched[App.match_index]):
                self.alert("Already set image",
                           "Current image is already the search image.",
                           kind="info")
        filepath = self.get_active_image_filepath()
        if filepath:
            self.search_image.set(os.path.basename(filepath))
            self.master.update()
            self.run_compare()
        else:
            self.alert("Error", "Failed to get active image filepath", kind="error")

    def create_image(self, image_path, extra_text=None) -> None:
        '''
        Show an image in the main content pane of the UI.
        '''
        if (isinstance(App.img, GifImageUI)):
            App.img.stop_display()
        try:
            App.img = self.get_image_to_fit(image_path)
        except Exception as e:
            if "truncated" in str(e):
                time.sleep(0.25) # If the image was just created in the directory, it's possible it's still being filled with data
                App.img = self.get_image_to_fit(image_path)
            else:
                raise e
        if (isinstance(App.img, GifImageUI)):
            App.img.display(self.canvas)
        else:
            self.canvas.create_image_center(App.img)
        if self.label_current_image_name is None:
            self.label_current_image_name = Label(self.sidebar)
            self.add_label(self.label_current_image_name, "", pady=30)
        self.label_current_image_name.config(bg=Style.BG_COLOR, fg=Style.FG_COLOR)
        relative_filepath, basename = get_relative_dirpath_split(self.base_dir, image_path)
        App.img_path = image_path
        text = basename if relative_filepath == "" else relative_filepath + "\n" + basename
        text = _wrap_text_to_fit_length(text, 30)
        if extra_text is not None:
            text += "\n" + extra_text
        self.label_current_image_name["text"] = text

    def clear_image(self) -> None:
        if App.img is not None and self.canvas is not None:
            if (isinstance(App.img, GifImageUI)):
                App.img.stop_display()
            self.destroy_grid_element("label_current_image_name")
            self.label_current_image_name = None
            self.canvas.clear_image()
            self.master.update()

    def toggle_image_view(self) -> None:
        '''
        While in search mode, toggle between the search image and the results.
        '''
        if App.mode != Mode.SEARCH:
            return

        if App.is_toggled_view_matches:
            self.show_searched_image()
        else:
            self.create_image(App.files_matched[App.match_index])

        App.is_toggled_view_matches = not App.is_toggled_view_matches

    def add_all_mode_buttons(self) -> None:
        self.add_button("prev_image_match_btn", "Previous image match", self.show_prev_image)
        self.add_button("next_image_match_btn", "Next image match", self.show_next_image)

    def remove_all_mode_buttons(self) -> None:
        self.destroy_grid_element("prev_group_btn")
        self.destroy_grid_element("next_group_btn")
        self.destroy_grid_element("prev_image_match_btn")
        self.destroy_grid_element("next_image_match_btn")
        # self.destroy_grid_element("search_current_image_btn")
        # self.destroy_grid_element("open_image_location_btn")
        # self.destroy_grid_element("copy_image_path")
        # self.destroy_grid_element("delete_image_btn")
        for mode in App.has_added_buttons_for_mode.keys():
            App.has_added_buttons_for_mode[mode] = False
        self.master.update()

    def add_buttons_for_mode(self) -> None:
        if not App.has_added_buttons_for_mode[App.mode]:
            if App.mode == Mode.SEARCH:
                self.add_button("toggle_image_view_btn", "Toggle image view", self.toggle_image_view)
                self.add_button("replace_current_image_btn", "Replace with search image",
                                self.replace_current_image_with_search_image)
                if not App.has_added_buttons_for_mode[Mode.GROUP]:
                    self.add_all_mode_buttons()
            elif App.mode == Mode.GROUP:
                self.add_button("prev_group_btn", "Previous group", self.show_prev_group)
                self.add_button("next_group_btn", "Next group", self.show_next_group)
                if not App.has_added_buttons_for_mode[Mode.SEARCH]:
                    self.add_all_mode_buttons()
            elif App.mode == Mode.DUPLICATES:
                pass

            App.has_added_buttons_for_mode[App.mode] = True

    def display_progress(self, context, percent_complete):
        self.label_state["text"] = _wrap_text_to_fit_length(
                f"{context}: {int(percent_complete)}% complete", 30)
        self.master.update()

    def validate_run(self):
        base_dir_selected = self.set_base_dir_box.get()
        if not base_dir_selected or base_dir_selected == "":
            res = self.alert("Confirm comparison",
                    "No base directory has been set, will use current base directory of " +
                    str(self.base_dir) + "\n\nAre you sure you want to proceed?",
                    kind="warning")
            return res == messagebox.YES
        return True

    def run_with_progress(self, exec_func, args=[]) -> None:
        if not self.validate_run():
            return

        def run_with_progress_async(self) -> None:
            self.progress_bar = Progressbar(self.sidebar, orient=HORIZONTAL, length=100, mode='indeterminate')
            self.apply_to_grid(self.progress_bar)
            self.progress_bar.start()
            exec_func(*args)
            self.progress_bar.stop()
            self.progress_bar.grid_forget()
            self.destroy_grid_element("progress_bar")

        start_thread(run_with_progress_async, use_asyncio=False, args=[self])

    def run_compare(self, find_duplicates=False) -> None:
        self.run_with_progress(self._run_compare, args=[find_duplicates])

    def _run_compare(self, find_duplicates=False) -> None:
        '''
        Execute operations on the Compare object in any mode. Create a new
        Compare object.
        '''
        search_file_path = self.get_search_file_path()
        counter_limit = self.get_counter_limit()
        compare_faces = self.compare_faces.get()
        overwrite = self.overwrite.get()
        color_diff_threshold = self.get_color_diff_threshold()
        inclusion_pattern = self.get_inclusion_pattern()
        get_new_data = True
        App.current_group_index = 0
        App.current_group = None
        App.max_group_index = 0
        App.group_indexes = []
        App.files_matched = []
        App.match_index = 0
        listener = ProgressListener(update_func=self.display_progress)

        if App.compare is None or App.compare.base_dir != self.get_base_dir():
            self.label_state["text"] = _wrap_text_to_fit_length(
                "Gathering image data..."
                + " setup may take a while depending on number"
                + " of files involved.", 30)
            App.compare = Compare(self.base_dir,
                                  search_file_path=search_file_path,
                                  counter_limit=counter_limit,
                                  use_thumb=True,
                                  compare_faces=compare_faces,
                                  color_diff_threshold=color_diff_threshold,
                                  inclusion_pattern=inclusion_pattern,
                                  overwrite=overwrite,
                                  verbose=True,
                                  progress_listener=listener)
        else:
            get_new_data = self.is_new_data_request_required(counter_limit,
                                                             color_diff_threshold,
                                                             inclusion_pattern,
                                                             overwrite)
            App.compare.set_search_file_path(search_file_path)
            App.compare.counter_limit = counter_limit
            App.compare.compare_faces = compare_faces
            App.compare.color_diff_threshold = color_diff_threshold
            App.compare.inclusion_pattern = inclusion_pattern
            App.compare.overwrite = overwrite
            App.compare.print_settings()
        
        if App.compare.is_run_search:
            self.set_mode(Mode.SEARCH, do_update=False)
            if not App.is_toggled_view_matches:
                App.is_toggled_view_matches = True
        else:
            if App.mode == Mode.SEARCH:
                res = self.alert("Confirm group run",
                                    "Search mode detected, please confirm switch to group mode before run. "
                                    + "Group mode will take longer as all images in the base directory are compared.",
                                    kind="warning")
                if res != messagebox.YES:
                    return
            self.set_mode(Mode.GROUP, do_update=False)

        if get_new_data:
            self.toast("Gathering image data for comparison")
            App.compare.get_files()
            App.compare.get_data()

        if App.compare.is_run_search:
            self.run_search()
        else:
            self.run_group(find_duplicates=find_duplicates)

    def is_new_data_request_required(self, counter_limit, color_diff_threshold,
                                     inclusion_pattern, overwrite):
        return (App.compare.counter_limit != counter_limit
                or App.compare.color_diff_threshold != color_diff_threshold
                or App.compare.inclusion_pattern != inclusion_pattern
                or (not App.compare.overwrite and overwrite))

    def run_group(self, find_duplicates=False) -> None:
        self.label_state["text"] = _wrap_text_to_fit_length(
            "Running image comparisons...", 30)
        App.files_grouped, App.file_groups = App.compare.run()
        
        if len(App.files_grouped) == 0:
            App.has_image_matches = False
            self.label_state["text"] = "Set a directory and search file."
            self.alert("No Groups Found",
                        "None of the files can be grouped with current settings.",
                        kind="info")
            return

        App.group_indexes = App.compare._sort_groups(App.file_groups)
        App.max_group_index = max(App.file_groups.keys())
        self.add_buttons_for_mode()
        App.current_group_index = 0

        if find_duplicates:
            App.file_groups = {}
            App.group_indexes = {}
            duplicates = App.compare.get_probable_duplicates()
            if len(duplicates) == 0:
                App.has_image_matches = False
                self.label_state["text"] = "Set a directory and search file."
                self.alert("No Duplicates Found",
                            "None of the files appear to be duplicates based on the current settings.",
                            kind="info")
                return
            self.set_mode(Mode.DUPLICATES, do_update=True)
            print("Probable duplicates:")
            pprint.pprint(duplicates, width=160)
            duplicate_group_count = 0
            for file1, file2 in duplicates:
                App.file_groups[duplicate_group_count] = {
                    file1: 0,
                    file2: 0
                }
                App.group_indexes[duplicate_group_count] = duplicate_group_count
                duplicate_group_count += 1
            App.max_group_index = duplicate_group_count
            self.set_current_group()
        else:
            has_found_stranded_group_members = False

            while len(App.file_groups[App.group_indexes[App.current_group_index]]) == 1:
                has_found_stranded_group_members = True
                App.current_group_index += 1

            self.set_current_group()
            if has_found_stranded_group_members:
                self.alert("Stranded Group Members Found",
                            "Some group members were left stranded by the grouping process.",
                            kind="info")

    def run_search(self) -> None:
        self.label_state["text"] = _wrap_text_to_fit_length(
            "Running image comparison with search file...", 30)
        App.files_grouped = App.compare.run_search()
        
        if len(App.files_grouped) == 0:
            App.has_image_matches = False
            self.label_state["text"] = "Set a directory and search file."
            self.alert("No Match Found",
                        "None of the files match the search file with current settings.",
                        kind="info")
            return

        for f in sorted(App.files_grouped, key=lambda f: App.files_grouped[f]):
            App.files_matched.append(f)

        App.match_index = 0
        App.has_image_matches = True
        self.label_state["text"] = _wrap_text_to_fit_length(
            str(len(App.files_matched)) + " possibly related images found.", 30)

        self.add_buttons_for_mode()
        self.create_image(App.files_matched[App.match_index])

    def find_duplicates(self):
        self.run_compare(find_duplicates=True)

    def set_group_state_label(self, group_number, size):
        if group_number is None:
            self.label_state["text"] = ""
        else:
            self.label_state["text"] = _wrap_text_to_fit_length(
                f"Group {group_number + 1} of {len(App.file_groups)}\nSize: {size}", 30)

    def is_toggled_search_image(self):
        return App.mode == Mode.SEARCH and not App.is_toggled_view_matches

    def get_active_image_filepath(self):
        if App.img is None:
            return None
        if App.mode == Mode.BROWSE:
            return App.file_browser.current_file()
        if self.is_toggled_search_image():
            filepath = App.search_image_full_path
        else:
            filepath = App.files_matched[App.match_index]
        return get_valid_file(self.get_base_dir(), filepath)

    def open_image_location_key(self, event):
        self.open_image_location()

    def open_image_location(self):
        filepath = self.get_active_image_filepath()

        if filepath is not None:
            self.toast("Opening file location: " + filepath)
            open_file_location(filepath)
        else:
            self.alert("Error", "Failed to open location of current file, unable to get valid filepath", kind="error")

    def copy_image_path(self):
        filepath = self.file_browser.current_file()
        if sys.platform=='win32':
            filepath = os.path.normpath(filepath)
            if self.config.escape_backslash_filepaths:
                filepath = filepath.replace("\\", "\\\\")
        self.master.clipboard_clear()
        self.master.clipboard_append(filepath)

    def _delete_image(self, event):
        self.delete_image()

    def delete_image(self):
        '''
        Delete the currently displayed image from the filesystem.
        '''
        if App.mode == Mode.BROWSE:
            App.file_browser.checking_files = False
            filepath = App.file_browser.current_file()
            if filepath:
                self._handle_delete(filepath)
                App.file_browser.refresh(refresh_cursor=False)
                self.show_next_image()
            return

        is_toggle_search_image = self.is_toggled_search_image()

        if len(App.files_matched) == 0 and not is_toggle_search_image:
            self.toast("Invalid action, the button should not be present if no files are available")
            return
        elif is_toggle_search_image and (App.search_image_full_path is None or App.search_image_full_path == ""):
            self.toast("Invalid action, search image not found")
            return

        filepath = self.get_active_image_filepath()

        if filepath is not None:
            self._handle_delete(filepath)
            self.update_groups_for_removed_file()
        else:
            self.alert("Error", "Failed to delete current file, unable to get valid filepath", kind="error")

    def _handle_delete(self, filepath):
        self.toast("Removing file: " + filepath)
        if self.config.delete_instantly:
            os.remove(filepath)
            return
        if self.config.trash_folder is not None: 
            filepath = os.path.normpath(filepath)
            sep = "\\" if "\\" in filepath else "/"
            new_filepath = filepath[filepath.rfind(sep)+1:len(filepath)]
            new_filepath = os.path.normpath(os.path.join(self.config.trash_folder, new_filepath))
            os.rename(filepath, new_filepath)
            return
        try:
            send2trash(os.path.normpath(filepath))
        except Exception as e:
            print(e)
            print("Failed to send file to the trash, so it will be deleted. Either pip install send2trash or set a specific trash folder in config.json.")
            os.remove(filepath)


    def replace_current_image_with_search_image(self):
        '''
        Overwrite the file at the path of the current image with the
        search image.
        '''
        if (App.mode != Mode.SEARCH
                or len(App.files_matched) == 0
                or not os.path.exists(App.search_image_full_path)):
            return

        _filepath = App.files_matched[App.match_index]
        filepath = get_valid_file(self.get_base_dir(), _filepath)

        if filepath is None:
            self.alert("Error", "Invalid target filepath for replacement: " + _filepath, kind="error")
            return

        os.rename(App.search_image_full_path, filepath)
        self.toast("Moved search image to " + filepath)

    def update_groups_for_removed_file(self):
        '''
        After a file has been removed, delete the cached image path for it and
        remove the group if only one file remains in that group.

        NOTE: This would be more complex if there was not a guarantee that
        groups are disjoint.
        '''
        if len(App.files_matched) < 3:
            if App.mode != Mode.GROUP:
                return

            # remove this group as it will only have one file
            App.files_grouped = {
                k: v for k, v in App.files_grouped.items() if v not in App.files_matched}
            actual_index = App.group_indexes[App.current_group_index]
            del App.file_groups[actual_index]
            del App.group_indexes[App.current_group_index]

            if len(App.file_groups) == 0:
                self.alert("No More Groups",
                           "There are no more image groups remaining for this directory and current filter settings.",
                           kind="info")
                App.current_group_index = 0
                App.files_grouped = {}
                App.file_groups = {}
                App.match_index = 0
                App.files_matched = []
                App.group_indexes = []
                self.set_mode(Mode.BROWSE)
                self.label_state["text"] = "Set a directory to run comparison."
                self.show_next_image()
                return
            elif App.current_group_index == len(App.file_groups):
                App.current_group_index = 0

            self.set_current_group()
        else:
            filepath = App.files_matched[App.match_index]
            App.files_grouped = {
                k: v for k, v in App.files_grouped.items() if v != filepath}
            del App.files_matched[App.match_index]

            if App.match_index == len(App.files_matched):
                App.match_index = 0

            self.master.update()
            self.create_image(App.files_matched[App.match_index])

    def alert(self, title, message, kind="info", hidemain=True) -> None:
        if kind not in ("error", "warning", "info"):
            raise ValueError("Unsupported alert kind.")

        print(f"Alert - Title: \"{title}\" Message: {message}")
        show_method = getattr(messagebox, "show{}".format(kind))
        return show_method(title, message)

    def toast(self, message):
        print("Toast message: " + message)
        if not self.config.show_toasts:
            return

        # Set the position of the toast on the screen (top right)
        width = 300
        height = 100
        x = self.master.winfo_screenwidth() - width
        y = 0

        # Create the toast on the top level
        toast = tk.Toplevel(self.master, bg=Style.BG_COLOR)
        toast.geometry(f'{width}x{height}+{int(x)}+{int(y)}')
        self.container = tk.Frame(toast)
        self.container.config(bg=Style.BG_COLOR)
        self.container.pack(fill=tk.BOTH, expand=tk.YES)
        label = tk.Label(
            self.container,
            text=message,
            anchor=tk.NW,
            bg=Style.BG_COLOR,
            fg=Style.FG_COLOR,
            font=('Helvetica', 12)
        )
        label.grid(row=1, column=1, sticky="NSEW", padx=10, pady=(0, 5))
        
        # Make the window invisible and bring it to front
        toast.attributes('-topmost', True)
#        toast.withdraw()

        # Start a new thread that will destroy the window after a few seconds
        def self_destruct_after(time_in_seconds):
            time.sleep(time_in_seconds)
            label.destroy()
            toast.destroy()
        start_thread(self_destruct_after, use_asyncio=False, args=[self.config.toasts_persist_seconds])

    def apply_to_grid(self, component, sticky=None, pady=0):
        if sticky is None:
            component.grid(column=0, row=self.row_counter, pady=pady)
        else:
            component.grid(column=0, row=self.row_counter, sticky=sticky, pady=pady)
        self.row_counter += 1

    def add_label(self, label_ref, text, sticky=W, pady=0):
        label_ref['text'] = text
        self.apply_to_grid(label_ref, sticky=sticky, pady=pady)

    def add_button(self, button_ref_name, text, command):
        if getattr(self, button_ref_name) is None:
            button = Button(master=self.sidebar, text=text, command=command)
            setattr(self, button_ref_name, button)
            button # for some reason this is necessary to maintain the reference?
            self.apply_to_grid(button)

    def new_entry(self, text_variable, text=""):
        return Entry(self.sidebar, text=text, textvariable=text_variable, width=30, font=fnt.Font(size=8))


    def destroy_grid_element(self, element_ref_name):
        element = getattr(self, element_ref_name)
        if element is not None:
            element.destroy()
            setattr(self, element_ref_name, None)
            self.row_counter -= 1


if __name__ == "__main__":
    assets = os.path.join(os.path.dirname(os.path.realpath(__file__)), "assets")
    root = ThemedTk(theme="black", themebg="black")
    root.title(" Simple Image Compare ")
    #root.iconbitmap(bitmap=r"icon.ico")
    icon = PhotoImage(file=os.path.join(assets, "icon.png"))
    root.iconphoto(False, icon)
    root.geometry("1400x950")
    # root.attributes('-fullscreen', True)
    root.resizable(1, 1)
    root.columnconfigure(0, weight=1)
    root.columnconfigure(1, weight=9)
    root.rowconfigure(0, weight=1)
    app = App(root)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
