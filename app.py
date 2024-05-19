import os
import signal
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
from tkinter.ttk import Button, Entry, Frame, OptionMenu, Progressbar, Style
from ttkthemes import ThemedTk
from PIL import ImageTk, Image

from compare.compare import Compare, get_valid_file
from compare.compare_embeddings import CompareEmbedding
from files.file_browser import FileBrowser, SortBy
from files.go_to_file import GoToFile
from files.marked_file_mover import MarkedFiles
from utils.app_info_cache import app_info_cache
from utils.app_style import AppStyle
from utils.config import config
from utils.constants import Mode, CompareMode
from utils.help_and_config import HelpAndConfig
from utils.utils import (
    _wrap_text_to_fit_length, get_user_dir, scale_dims, get_relative_dirpath_split, open_file_location, periodic, start_thread
)
from image.image_details import ImageDetails # must import after config because of dynamic import


### TODO image zoom feature
### TODO copy/cut image using hotkey (pywin32 ? win32com? IDataPobject?)
### TODO comfyui plugin for ipadapter/controlnet (maybe)
### TODO some type of plugin to filter the images using a filter function defined externally
### TODO recursive option for compare jobs
### TODO enable comparison jobs on user-defined file list
### TODO compare option to restrict by matching image dimensions
### TODO compare option encoding size
### TODO add checkbox for include gif option
### TODO tkVideoPlayer or tkVideoUtils for playing videos
### TODO custom frame class for sidebar to hold all the buttons
### TODO compare window (only compare a set of images from directory, sorted by some logic)
### TODO enable file mover in all modes


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
    compare_mode = config.compare_mode
    fill_canvas = config.fill_canvas
    fullscreen = False
    delete_lock = False
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
        if AppStyle.IS_DEFAULT_THEME:
            self.configure_style("breeze") # Changes the window to light theme
            AppStyle.BG_COLOR = "gray"
            AppStyle.FG_COLOR = "black"
        else:
            self.configure_style("black") # Changes the window to dark theme
            AppStyle.BG_COLOR = "#26242f"
            AppStyle.FG_COLOR = "white"
        AppStyle.IS_DEFAULT_THEME = not AppStyle.IS_DEFAULT_THEME
        self.master.config(bg=AppStyle.BG_COLOR)
        self.sidebar.config(bg=AppStyle.BG_COLOR)
        self.canvas.config(bg=AppStyle.BG_COLOR)
        for name, attr in self.__dict__.items():
            if isinstance(attr, Label):
                attr.config(bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR, font=fnt.Font(size=config.font_size))
            elif isinstance(attr, Checkbutton):
                attr.config(bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR, selectcolor=AppStyle.BG_COLOR, font=fnt.Font(size=config.font_size))
        self.master.update()
        self.toast("Theme switched to dark." if AppStyle.IS_DEFAULT_THEME else "Theme switched to light.")


    def __init__(self, master):
        self.master = master
        self.config = config
        Style().configure(".", font=('Helvetica', config.font_size))

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
        self.add_label(self.label_state, "Set a directory to run comparison.", pady=10)

        # Settings UI
        self.add_label(self.label1, "Controls & Settings", sticky=None, pady=10)
        self.toggle_theme_btn = None
        self.set_base_dir_btn = None
        self.set_search_btn = None
        self.search_text_btn = None
        self.add_button("toggle_theme_btn", "Toggle theme", self.toggle_theme)
        self.add_button("set_base_dir_btn", "Set directory", self.set_base_dir)
        self.set_base_dir_box = self.new_entry(text="Add dirpath...")
        self.apply_to_grid(self.set_base_dir_box)

        self.add_button("set_search_btn", "Set search file", self.set_search_image)
        self.search_image = tk.StringVar()
        self.search_img_path_box = self.new_entry(self.search_image)
        self.apply_to_grid(self.search_img_path_box, sticky=W)

        self.add_button("search_text_btn", "Search text (embedding mode)", self.search_text_embedding)
        self.search_text = tk.StringVar()
        self.search_text_box = self.new_entry(self.search_text)
        self.search_text_box.bind("<Return>", self.search_text_embedding)
        self.apply_to_grid(self.search_text_box, sticky=W)

        self.label_compare_mode = Label(self.sidebar)
        self.add_label(self.label_compare_mode, "Compare mode")
        self.compare_mode_var = tk.StringVar()
        self.compare_mode_choice = OptionMenu(self.sidebar, self.compare_mode_var, str(App.compare_mode),
                                              *CompareMode.members(), command=self.set_compare_mode)
        self.apply_to_grid(self.compare_mode_choice, sticky=W)

        self.label_compare_threshold = Label(self.sidebar)
        self.add_label(self.label_compare_threshold, App.compare_mode.threshold_str())
        self.compare_threshold = tk.StringVar()
        if App.compare_mode == CompareMode.COLOR_MATCHING:
            default_val = self.config.color_diff_threshold
        else:
            default_val = self.config.embedding_similarity_threshold
        self.compare_threshold_choice = OptionMenu(self.sidebar, self.compare_threshold,
                                                   str(default_val), *App.compare_mode.threshold_vals())
        self.apply_to_grid(self.compare_threshold_choice, sticky=W)

        self.compare_faces = tk.BooleanVar(value=False)
        self.compare_faces_choice = Checkbutton(self.sidebar, text='Compare faces', variable=self.compare_faces)
        self.apply_to_grid(self.compare_faces_choice, sticky=W)

        self.overwrite = tk.BooleanVar(value=False)
        self.overwrite_choice = Checkbutton(self.sidebar, text='Overwrite cache', variable=self.overwrite)
        self.apply_to_grid(self.overwrite_choice, sticky=W)

        self.label_counter_limit = Label(self.sidebar)
        self.add_label(self.label_counter_limit, "Max files to compare")
        self.set_counter_limit = self.new_entry()
        self.set_counter_limit.insert(0, str(self.config.file_counter_limit))
        self.apply_to_grid(self.set_counter_limit, sticky=W)

        self.label_inclusion_pattern = Label(self.sidebar)
        self.add_label(self.label_inclusion_pattern, "Filter files by glob pattern")
        self.inclusion_pattern = tk.StringVar()
        self.set_inclusion_pattern = self.new_entry(self.inclusion_pattern)
        self.apply_to_grid(self.set_inclusion_pattern, sticky=W)

        self.label_sort_by = Label(self.sidebar)
        self.add_label(self.label_sort_by, "Browsing mode - Sort by")
        self.sort_by = tk.StringVar()
        self.sort_by_choice = OptionMenu(self.sidebar, self.sort_by, str(self.config.sort_by),
                                         *SortBy.members(), command=self.set_sort_by)
        self.apply_to_grid(self.sort_by_choice, sticky=W)

        image_browse_recurse_var = tk.BooleanVar(value=self.config.image_browse_recursive)
        self.image_browse_recurse = Checkbutton(self.sidebar, text='Browsing mode - Recursive',
                                                variable=image_browse_recurse_var, command=self.toggle_image_browse_recursive)
        self.apply_to_grid(self.image_browse_recurse, sticky=W)

        fill_canvas_var = tk.BooleanVar(value=App.fill_canvas)
        self.fill_canvas_choice = Checkbutton(self.sidebar, text='Image resize to full window',
                                              variable=fill_canvas_var, command=App.toggle_fill_canvas)
        self.apply_to_grid(self.fill_canvas_choice, sticky=W)
        
        search_return_closest_var = tk.BooleanVar(value=CompareEmbedding.SEARCH_RETURN_CLOSEST)
        self.search_return_closest_choice = Checkbutton(self.sidebar, text='Embedding search return closest',
                                              variable=search_return_closest_var, command=self.toggle_search_return_closest)
        self.apply_to_grid(self.search_return_closest_choice, sticky=W)

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
        self.master.bind('<Left>', self.show_prev_image)
        self.master.bind('<Right>', self.show_next_image)
        self.master.bind('<Shift-Left>', self.show_prev_group)
        self.master.bind('<Shift-Right>', self.show_next_group)
        self.master.bind('<Shift-O>', self.open_image_location)
        self.master.bind('<Shift-Delete>', self.delete_image)
        self.master.bind("<F11>", self.toggle_fullscreen)
        self.master.bind("<Shift-F>", self.toggle_fullscreen)
        self.master.bind("<Escape>", self.end_fullscreen)
        self.master.bind("<Shift-D>", self.get_image_details)
        self.master.bind("<Shift-H>", self.get_help_and_config)
        self.master.bind("<Shift-S>", self.toggle_slideshow)
        self.master.bind("<MouseWheel>", self.handle_mousewheel)
        self.master.bind("<Button-2>", self.delete_image)
        self.master.bind("<Shift-M>", self.add_or_remove_mark_for_current_image)
        self.master.bind("<Shift-N>", self.add_all_marks_from_last)
        self.master.bind("<Shift-G>", self.go_to_mark)
        self.master.bind("<Control-g>", self.open_go_to_file_window)
        self.master.bind("<Shift-C>", self.copy_marks_list)
        self.master.bind("<Control-m>", self.open_move_marks_window)
        self.master.bind("<Control-z>", self.revert_last_marks_change)
        self.master.bind("<Control-x>", self.modify_last_marks_change)
        self.master.bind("<Home>", self.home)
        self.master.bind("<Prior>", self.page_up)
        self.master.bind("<Next>", self.page_down)

        # Start async threads
        start_thread(self.check_files)

        self.toggle_theme()
        self.master.update()

        if config.use_file_paths_json:
            self.set_file_paths()

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
        self.label_mode['text'] = str(mode)

        if mode == Mode.GROUP or mode == Mode.DUPLICATES:
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
        App.file_browser.set_sort_by(SortBy.get(self.sort_by.get()))
        App.file_browser.refresh()
        if App.mode == Mode.BROWSE:
            self.show_next_image()

    def set_compare_mode(self, event):
        App.compare_mode = CompareMode.get(self.compare_mode_var.get())
        self.label_compare_threshold["text"] = App.compare_mode.threshold_str()
        if App.compare_mode == CompareMode.COLOR_MATCHING:
            default_val = self.config.color_diff_threshold
        else:
            default_val = self.config.embedding_similarity_threshold
        self.compare_threshold.set(str(default_val))
        self.compare_threshold_choice = OptionMenu(self.sidebar, self.compare_threshold,
                                                   str(default_val), *App.compare_mode.threshold_vals())
        self.master.update()

    @classmethod
    def toggle_fill_canvas(cls):
        cls.fill_canvas = not cls.fill_canvas

    def toggle_image_browse_recursive(self):
        self.file_browser.toggle_recursive()
        if App.mode == Mode.BROWSE and App.img:
            self.show_next_image()

    def toggle_search_return_closest(self):
        if CompareMode.CLIP_EMBEDDING != App.compare_mode:
            self.alert("Invalid mode", "Compare mode must be set to Clip Embedding to make use of this option.")
        CompareEmbedding.SEARCH_RETURN_CLOSEST = not CompareEmbedding.SEARCH_RETURN_CLOSEST

    def refresh(self, show_new_images=False, refresh_cursor=False, file_check=True, removed_files=[]):
        App.file_browser.refresh(refresh_cursor=refresh_cursor, file_check=file_check, removed_files=removed_files)
        if App.file_browser.has_files():
            if show_new_images:
                has_new_images = self.file_browser.update_cursor_to_new_images()
            self.show_next_image()
            if show_new_images and has_new_images:
                App.delete_lock = True # User may have started delete just before the image changes, lock for a short period after to ensure no misdeletion
                time.sleep(1)
                App.delete_lock = False
        else:
            self.clear_image()
            self.alert("Warning", "No files found in direcftory after refresh.", kind="warning")
        print("Refreshed files")

    @periodic(config.file_check_interval_seconds)
    async def check_files(self, **kwargs):
        if App.file_browser.checking_files and App.mode == Mode.BROWSE:
            base_dir = self.set_base_dir_box.get()
            if base_dir and base_dir != "":
                self.refresh(show_new_images=SlideshowConfig.show_new_images)

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
        if App.img_path is None or App.img_path == "":
            return
        top_level = tk.Toplevel(self.master, bg=AppStyle.BG_COLOR)
        top_level.title("Image Details")
        top_level.geometry("600x300")
        if App.mode == Mode.BROWSE:
            index_text = App.file_browser.get_index_details()
        elif App.mode == Mode.GROUP:
            index_text = f"{App.match_index+1} of {len(App.files_matched)} (Group {App.current_group_index+1} of {len(App.file_groups)})"
        elif App.mode == Mode.SEARCH and not App.is_toggled_view_matches:
            index_text = f"{App.match_index+1} of {len(App.files_matched)}"
        else:
            index_text = ""
        try:
            image_details = ImageDetails(top_level, App.img_path, index_text)
        except Exception as e:
            self.alert("Image Details Error", str(e), kind="error")

    def get_help_and_config(self, event=None):
        top_level = tk.Toplevel(self.master, bg=AppStyle.BG_COLOR)
        top_level.title("Help and Config")
        top_level.geometry("600x600")
        try:
            help_and_config = HelpAndConfig(top_level)
        except Exception as e:
            self.alert("Image Details Error", str(e), kind="error")

    def set_file_paths(self):
        App.file_browser.refresh()
        self.label_state["text"] = f"{App.file_browser.count()} image files found."
        tries = 0
        while tries < 10:
            tries += 1
            try:
                if self.show_next_image():
                    return
            except Exception as e:
                pass

    def set_base_dir(self) -> None:
        '''
        Change the base directory to the value provided in the UI.
        '''
        self.store_info_cache()
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
            previous_file = app_info_cache.get(self.base_dir, "image_cursor")
            if previous_file and previous_file != "":
                if not self.go_to_file(None, previous_file, retry_with_delay=1):
                    self.show_next_image()
            else:
                self.show_next_image()
            self.label_state["text"] = f"{App.file_browser.count()} image files found."
        self.master.update()

    def get_base_dir(self) -> str:
        return "." if (self.base_dir is None or self.base_dir == "") else self.base_dir

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
            if search_file is None:
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

    def get_compare_threshold(self):
        compare_threshold_str = self.compare_threshold.get()
        if compare_threshold_str == "":
            return None
        try:
            return int(compare_threshold_str)
        except Exception:
            if App.compare_mode == CompareMode.CLIP_EMBEDDING:
                return self.config.embedding_similarity_threshold
            else:
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

    def show_prev_image(self, event=None, show_alert=True) -> bool:
        '''
        If similar image results are present in any mode, display the previous
        in the list of matches.
        '''
        if App.mode == Mode.BROWSE:
            self.master.update()
            try:
                self.create_image(App.file_browser.previous_file())
                return True
            except Exception as e:
                self.alert("Exception", str(e))
                return False
        if App.files_matched is None:
            return False
        elif len(App.files_matched) == 0:
            if show_alert:
                self.alert("Search required",
                           "No matches found. Search again to find potential matches.",
                           kind="info")
            return False

        App.is_toggled_view_matches = True
        
        if App.match_index > 0:
            App.match_index -= 1
        else:
            App.match_index = len(App.files_matched) - 1
        
        self.master.update()
        self.create_image(App.files_matched[App.match_index])
        return True

    def show_next_image(self, event=None, show_alert=True) -> bool:
        '''
        If similar image results are present in any mode, display the next
        in the list of matches.
        '''
        if App.mode == Mode.BROWSE:
            self.master.update()
            try:
                self.create_image(App.file_browser.next_file())
                return True
            except Exception as e:
                self.alert("Exception", str(e))
                return False
        if App.files_matched is None:
            return False
        elif len(App.files_matched) == 0:
            if show_alert:
                self.alert("Search required",
                           "No matches found. Search again to find potential matches.",
                           kind="info")
            return False

        App.is_toggled_view_matches = True

        if len(App.files_matched) > App.match_index + 1:
            App.match_index += 1
        else:
            App.match_index = 0

        self.master.update()
        self.create_image(App.files_matched[App.match_index])
        return True

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

    def set_current_group(self, start_match_index=0) -> None:
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
        App.match_index = start_match_index
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
        self.label_current_image_name.config(bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
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
                    f"{self.base_dir}\n\nAre you sure you want to proceed?",
                    kind="warning")
            return res == messagebox.OK
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

    def run_compare(self, find_duplicates=False, search_text=None) -> None:
        self.run_with_progress(self._run_compare, args=[find_duplicates, search_text])

    def _run_compare(self, find_duplicates=False, search_text=None) -> None:
        '''
        Execute operations on the Compare object in any mode. Create a new
        Compare object if needed.
        '''
        search_file_path = self.get_search_file_path()
        counter_limit = self.get_counter_limit()
        compare_faces = self.compare_faces.get()
        overwrite = self.overwrite.get()
        compare_threshold = self.get_compare_threshold()
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
                "Gathering image data... setup may take a while depending on number of files involved.", 30)
            if App.compare_mode == CompareMode.CLIP_EMBEDDING:
                App.compare = CompareEmbedding(
                    self.base_dir,
                    search_file_path=search_file_path,
                    counter_limit=counter_limit,
                    embedding_similarity_threshold=compare_threshold,
                    compare_faces=compare_faces,
                    inclusion_pattern=inclusion_pattern,
                    overwrite=overwrite,
                    verbose=True,
                    progress_listener=listener
                )
            elif App.compare_mode == CompareMode.COLOR_MATCHING:
                App.compare = Compare(
                    self.base_dir,
                    search_file_path=search_file_path,
                    counter_limit=counter_limit,
                    use_thumb=True,
                    compare_faces=compare_faces,
                    color_diff_threshold=compare_threshold,
                    inclusion_pattern=inclusion_pattern,
                    overwrite=overwrite,
                    verbose=True,
                    progress_listener=listener
                )
        else:
            get_new_data = self.is_new_data_request_required(counter_limit,
                                                             compare_threshold,
                                                             inclusion_pattern,
                                                             overwrite)
            App.compare.set_search_file_path(search_file_path)
            App.compare.counter_limit = counter_limit
            App.compare.compare_faces = compare_faces
            App.compare.inclusion_pattern = inclusion_pattern
            App.compare.overwrite = overwrite
            if App.compare_mode == CompareMode.COLOR_MATCHING:
                App.compare.color_diff_threshold = compare_threshold
            else:
                App.compare.embedding_similarity_threshold = compare_threshold
            App.compare.print_settings()
        
        if App.compare.is_run_search or search_text is not None:
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
        elif search_text is not None:
            self.run_search_text_embedding(search_text=search_text)
        else:
            self.run_group(find_duplicates=find_duplicates)

    def is_new_data_request_required(self, counter_limit, compare_threshold,
                                     inclusion_pattern, overwrite):
        if App.compare_mode == CompareMode.COLOR_MATCHING:
            if App.compare.color_diff_threshold != compare_threshold:
                return True
        elif App.compare.embedding_similarity_threshold != compare_threshold:
            return True
        return (App.compare.counter_limit != counter_limit
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

    def search_text_embedding(self, event=None):
        if App.compare_mode != CompareMode.CLIP_EMBEDDING:
            self.alert("Invalid action", "Compare mode must be set to Clip embedding to search text embeddings", kind="warning")
            return
        search_text = self.search_text.get()
        if search_text.strip() == "":
            self.alert("Invalid search text", "Search text must be set", kind="warning")
            return
        self.run_compare(search_text=search_text)

    def run_search_text_embedding(self, search_text=""):
        self.label_state["text"] = _wrap_text_to_fit_length(
            "Running image comparison with search text...", 30)
        App.files_grouped = App.compare.search_text(search_text)

        if len(App.files_grouped) == 0:
            App.has_image_matches = False
            self.label_state["text"] = "Set a directory and search file or search text."
            self.alert("No Match Found",
                        "None of the files match the search text with current settings.",
                        kind="info")
            return

        for f in App.files_grouped:
            App.files_matched.append(f)

        App.match_index = 0
        App.has_image_matches = True
        self.label_state["text"] = _wrap_text_to_fit_length(
            str(len(App.files_matched)) + " possibly related images found.", 30)

        self.add_buttons_for_mode()
        self.create_image(App.files_matched[App.match_index])

    def set_group_state_label(self, group_number, size):
        if group_number is None:
            self.label_state["text"] = ""
        else:
            self.label_state["text"] = _wrap_text_to_fit_length(
                f"Group {group_number + 1} of {len(App.file_groups)}\nSize: {size}", 30)

    def add_or_remove_mark_for_current_image(self, event=None):
        self._check_marks(min_mark_size=0)
        if App.img_path in MarkedFiles.file_marks:
            MarkedFiles.file_marks.remove(App.img_path)
            remaining_marks_count = len(MarkedFiles.file_marks)
            if MarkedFiles.mark_cursor >= remaining_marks_count:
                MarkedFiles.mark_cursor = -1
            self.toast(f"Mark removed. Remaining: {remaining_marks_count}")
        else:
            MarkedFiles.file_marks.append(App.img_path)
            self.toast(f"Mark added. Total set: {len(MarkedFiles.file_marks)}")

    def add_all_marks_from_last(self, event=None):
        self._check_marks()
        if App.img_path in MarkedFiles.file_marks:
            return
        files = App.file_browser.select_series(start_file=MarkedFiles.file_marks[-1], end_file=App.img_path)
        for _file in files:
            if not _file in MarkedFiles.file_marks:
                MarkedFiles.file_marks.append(_file)
        self.toast(f"Marks added. Total set: {len(MarkedFiles.file_marks)}")

    def go_to_mark(self, event=None):
        self._check_marks()
        MarkedFiles.mark_cursor += 1
        if MarkedFiles.mark_cursor >= len(MarkedFiles.file_marks):
            MarkedFiles.mark_cursor = 0
        marked_file = MarkedFiles.file_marks[MarkedFiles.mark_cursor]
        App.file_browser.go_to_file(marked_file)
        self.create_image(marked_file)
        self.master.update()

    def copy_marks_list(self, event=None):
        self.master.clipboard_clear()
        self.master.clipboard_append(MarkedFiles.file_marks)

    def open_move_marks_window(self, event=None):
        self._check_marks(min_mark_size=0)
        if len(MarkedFiles.file_marks) == 0:
            self.add_or_remove_mark_for_current_image()
        top_level = tk.Toplevel(self.master, bg=AppStyle.BG_COLOR)
        top_level.title("Move Marked Files")
        top_level.geometry(MarkedFiles.get_geometry())
        try:
            marked_file_mover = MarkedFiles(top_level, self.toast, self.alert, self.refresh, self._handle_delete, base_dir=self.get_base_dir())
        except Exception as e:
            self.alert("Marked Files Window Error", str(e), kind="error")

    def _check_marks(self, min_mark_size=1):
        if App.mode != Mode.BROWSE:
            self.alert("Invalid Action", "Marks currently only available in Browsing mode.")
            raise Exception("Marks currently only available in Browsing mode.")
        if len(MarkedFiles.file_marks) < min_mark_size:
            exception_text = f"{len(MarkedFiles.file_marks)} marks have been set (>={min_mark_size} expected).\nUse Shift+M to set a mark."
            self.toast(exception_text)
            raise Exception(exception_text)

    def revert_last_marks_change(self, event=None):
        if not config.use_file_paths_json:
            MarkedFiles.undo_move_marks(self.get_base_dir(), self.toast, self.refresh)

    def modify_last_marks_change(self, event=None):
        MarkedFiles.undo_move_marks(None, self.toast, self.refresh)

    def open_go_to_file_window(self, event=None):
        top_level = tk.Toplevel(self.master, bg=AppStyle.BG_COLOR)
        top_level.title("Go To File")
        top_level.geometry(GoToFile.get_geometry())
        try:
            go_to_file = GoToFile(top_level, self.go_to_file, self.toast)
        except Exception as e:
            self.alert("Go To File Window Error", str(e), kind="error")

    def go_to_file(self, event=None, search_text=".", retry_with_delay=0):
        if App.mode == Mode.BROWSE:
            image_path = App.file_browser.find(search_text=search_text, retry_with_delay=retry_with_delay)
        else:
            image_path, group_indexes = self.find_file_after_comparison(search_text)
            if group_indexes:
                App.current_group_index = group_indexes[0]
                self.set_current_group(start_match_index=group_indexes[1])
                return True
        if not image_path:
            self.alert("File not found", f"No file was found for the search text: \"{search_text}\"", kind="info")
            return False
        self.create_image(image_path)
        self.master.update()
        return True

    def find_file_after_comparison(self, search_text="", exact_match=False):
        if not search_text or search_text.strip() == "":
            return None, None
        file_group_map = self._get_file_group_map()
        for file, group_indexes in file_group_map.items():
            if search_text == file.lower():
                return file, group_indexes
        if exact_match:
            return None, None
        search_text = search_text.lower()
        for file, group_indexes in file_group_map.items():
            if file.lower().startswith(search_text):
                return file, group_indexes
        for file, group_indexes in file_group_map.items():
            if search_text in file.lower():
                return file, group_indexes
        return None, None

    def home(self, event=None):
        if not App.mode == Mode.BROWSE:
            raise Exception("Action currently only available in Browsing mode.")
        App.file_browser.refresh()
        self.create_image(App.file_browser.next_file())
        self.master.update()

    def page_up(self, event=None):
        if not App.mode == Mode.BROWSE:
            raise Exception("Page up/down currently only available in Browsing mode.")
        self.create_image(App.file_browser.page_up())
        self.master.update()

    def page_down(self, event=None):
        if not App.mode == Mode.BROWSE:
            raise Exception("Page up/down currently only available in Browsing mode.")
        self.create_image(App.file_browser.page_down())
        self.master.update()

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

    def open_image_location(self, event=None):
        filepath = self.get_active_image_filepath()

        if filepath is not None:
            self.toast("Opening file location: " + filepath)
            open_file_location(filepath)
        else:
            self.alert("Error", "Failed to open location of current file, unable to get valid filepath", kind="error")

    def copy_image_path(self):
        filepath = self.file_browser.current_file()
        if sys.platform == 'win32':
            filepath = os.path.normpath(filepath)
            if self.config.escape_backslash_filepaths:
                filepath = filepath.replace("\\", "\\\\")
        self.master.clipboard_clear()
        self.master.clipboard_append(filepath)

    def delete_image(self, event=None):
        '''
        Delete the currently displayed image from the filesystem.
        '''
        if App.delete_lock:
            self.toast("Delete lock after slideshow\ntransition prevented deletion")
            return

        if App.mode == Mode.BROWSE:
            App.file_browser.checking_files = False
            filepath = App.file_browser.current_file()
            if filepath:
                self._handle_delete(filepath)
                App.file_browser.refresh(refresh_cursor=False, removed_files=[filepath])
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

    def _handle_delete(self, filepath, toast=True):
        if toast:
            self.toast("Removing file: " + filepath)
        else:
            print("Removing file: " + filepath)
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
            if App.mode not in (Mode.GROUP, Mode.DUPLICATES):
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

    def _get_file_group_map(self):
        if App.mode == Mode.BROWSE:
            raise Exception("Cannot get file group map in BROWSE mode")
        group_map = {}
        for group_count in range(len(App.group_indexes)):
            group_index = App.group_indexes[group_count]
            group = App.file_groups[group_index]
            group_file_count = 0
            for f in sorted(group, key=lambda f: group[f]):                    
                group_map[f] = (group_count, group_file_count)
                group_file_count += 1
        return group_map

    def store_info_cache(self):
        base_dir = self.get_base_dir()
        if base_dir and base_dir != "" and App.img_path and App.img_path != "":
            app_info_cache.set(base_dir, "image_cursor", os.path.basename(App.img_path))
            app_info_cache.store()

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
        toast = tk.Toplevel(self.master, bg=AppStyle.BG_COLOR)
        toast.geometry(f'{width}x{height}+{int(x)}+{int(y)}')
        self.container = tk.Frame(toast)
        self.container.config(bg=AppStyle.BG_COLOR)
        self.container.pack(fill=tk.BOTH, expand=tk.YES)
        label = tk.Label(
            self.container,
            text=message.strip(),
            anchor=tk.NW,
            bg=AppStyle.BG_COLOR,
            fg=AppStyle.FG_COLOR,
            font=('Helvetica', 10)
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
        label_ref['font'] = fnt.Font(size=config.font_size)
        self.apply_to_grid(label_ref, sticky=sticky, pady=pady)

    def add_button(self, button_ref_name, text, command):
        if getattr(self, button_ref_name) is None:
            button = Button(master=self.sidebar, text=text, command=command)
            setattr(self, button_ref_name, button)
            button # for some reason this is necessary to maintain the reference?
            self.apply_to_grid(button)

    def new_entry(self, text_variable=None, text=""):
        return Entry(self.sidebar, text=text, textvariable=text_variable, width=30, font=fnt.Font(size=config.font_size))


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
    root.geometry(config.default_main_window_size)
    # root.attributes('-fullscreen', True)
    root.resizable(1, 1)
    root.columnconfigure(0, weight=1)
    root.columnconfigure(1, weight=9)
    root.rowconfigure(0, weight=1)
    app = App(root)

    def on_closing():
        app.store_info_cache()
        root.destroy()

    # Graceful shutdown handler
    def graceful_shutdown(signum, frame):
        print("Caught signal, shutting down gracefully...")
        on_closing()
        exit(0)

    # Register the signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)

    root.protocol("WM_DELETE_WINDOW", on_closing)

    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
