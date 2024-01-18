from enum import Enum
import os
import threading

import tkinter as tk
from tkinter import Canvas, PhotoImage, filedialog, messagebox, HORIZONTAL
from tkinter.constants import W
import tkinter.font as fnt
from tkinter.ttk import Button, Entry, Frame, Label, OptionMenu, Progressbar
from ttkthemes import ThemedTk
from PIL import ImageTk, Image

from compare import Compare, get_valid_file
from file_browser import FileBrowser
from utils import (
    _wrap_text_to_fit_length, basename, get_user_dir, scale_dims, trace, open_file_location
)


### TODO simple image browsing mode
### TODO remove duplicates mode
### TODO progress listener for compare class
### TODO add checkbox for include gif option
### TODO add checkbox for fill canvas option
### TODO custom frame class for sidebar to hold all the button crap


class Mode(Enum):
    BROWSE = 1
    SEARCH = 2
    GROUP = 3
    REM_DUP = 4


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


class App():
    '''
    UI for comparing image files and making related file changes.
    '''

    IS_DEFAULT_THEME = False

    def configure_style(self, theme):
        self.master.set_theme(theme, themebg="black")

    def toggle_theme(self):
        if App.IS_DEFAULT_THEME:
            # Changes the window to light theme 
            self.configure_style("breeze")
            self.master.config(bg="gray")
            self.sidebar.config(bg="gray")
            self.canvas.config(bg="gray")
            App.IS_DEFAULT_THEME = False
            print("Theme switched to light.")
        else:
            # Changes the window to dark theme 
            self.configure_style("black")
            self.master.config(bg="#26242f")
            self.sidebar.config(bg="#26242f")
            self.canvas.config(bg="#26242f")
            App.IS_DEFAULT_THEME = True
            print("Theme switched to dark.")
        self.master.update()

    def __init__(self, master):
        self.master = master
        self.file_browser = FileBrowser()
        self.mode = Mode.BROWSE
        self.fill_canvas = True
        self.base_dir = get_user_dir()
        self.search_dir = get_user_dir()

        # Sidebar
        self.sidebar = tk.Frame(self.master)
        self.sidebar.columnconfigure(0, weight=1)
        self.row_counter = 0
        self.sidebar.grid(column=0, row=self.row_counter)

        # The top part is a label with info
        self.label_mode = Label(self.sidebar)
        self.label_state = Label(self.sidebar)
        self.label1 = Label(self.sidebar)
        self.add_label(self.label_mode, "", sticky=None)
        self.add_label(self.label_state, "Set a directory to run comparison.", pady=20)

        # Settings UI
        self.add_label(self.label1, "Controls & Settings", sticky=None, pady=30)
        self.set_base_dir_btn = None
        self.create_img_btn = None
        self.toggle_theme_btn = None
        self.add_button("toggle_theme_btn", "Toggle theme", self.toggle_theme)
        self.add_button("set_base_dir_btn", "Set directory", self.set_base_dir)
        self.set_base_dir_box = Entry(self.sidebar,
                                      text="Add dirpath...",
                                      width=30,
                                      font=fnt.Font(size=8))
        self.apply_to_grid(self.set_base_dir_box)
        self.add_button("create_img_btn", "Set search file", self.set_search_image)
        self.search_image = tk.StringVar()
        self.create_img_path_box = Entry(self.sidebar,
                                         textvariable=self.search_image,
                                         width=30,
                                         font=fnt.Font(size=8))
        self.apply_to_grid(self.create_img_path_box, sticky=W)
        self.label_color_diff_threshold = Label(self.sidebar)
        self.add_label(self.label_color_diff_threshold, "Color diff threshold")
        self.color_diff_threshold = tk.StringVar(master)
        self.color_diff_threshold_choice = OptionMenu(
            self.sidebar, self.color_diff_threshold,
            *[str(i) for i in list(range(31))])
        self.color_diff_threshold.set("15")  # default value
        self.apply_to_grid(self.color_diff_threshold_choice, sticky=W)
        self.label_compare_faces = Label(self.sidebar)
        self.add_label(self.label_compare_faces, "Compare faces")
        self.compare_faces = tk.StringVar(master)
        self.compare_faces_choice = OptionMenu(
            self.sidebar, self.compare_faces, "Yes", "No")
        self.compare_faces.set("No")  # default value
        self.apply_to_grid(self.compare_faces_choice, sticky=W)
        self.label_overwrite = Label(self.sidebar)
        self.add_label(self.label_overwrite, "Overwrite cache")
        self.overwrite = tk.StringVar(master)
        self.overwrite_choice = OptionMenu(
            self.sidebar, self.overwrite, "No", "Yes")
        self.overwrite.set("No")  # default value
        self.apply_to_grid(self.overwrite_choice, sticky=W)
        self.label_counter_limit = Label(self.sidebar)
        self.add_label(self.label_counter_limit, "Max # of files to compare")
        self.set_counter_limit = Entry(self.sidebar,
                                       text="Add file path...",
                                       width=30,
                                       font=fnt.Font(size=8))
        self.set_counter_limit.insert(0, "40000") # default value
        self.apply_to_grid(self.set_counter_limit, sticky=W)
        self.label_inclusion_pattern = Label(self.sidebar)
        self.add_label(self.label_inclusion_pattern,
                       "Filter files by string in name")
        self.inclusion_pattern = tk.StringVar()
        self.set_inclusion_pattern = Entry(self.sidebar,
                                           textvariable=self.inclusion_pattern,
                                           width=30,
                                           font=fnt.Font(size=8))
        self.apply_to_grid(self.set_inclusion_pattern, sticky=W)

        # Run context-aware UI elements
        self.progress_bar = None
        self.run_compare_btn = None
        self.add_button("run_compare_btn", "Run image compare", self.run_compare)
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
        self.rem_dups_btn = None

        # Image panel and state management
        self.match_index = 0
        self.master.update()
        self.canvas = ResizingCanvas(self.master)
        self.canvas.grid(column=1, row=0)
        self.img = None
        self.files_grouped = None
        self.file_groups = None
        self.files_matched = None
        self.compare = None
        self.has_image_matches = False
        self.current_group = None
        self.current_group_index = 0
        self.group_indexes = []
        self.max_group_index = 0
        self.is_toggled_view_matches = True
        self.has_added_buttons_for_mode = {
            Mode.BROWSE: False,
            Mode.GROUP: False, 
            Mode.SEARCH: False, 
            Mode.REM_DUP: False
        }

        # Default mode is GROUP
        self.set_mode(Mode.BROWSE)

        # Key bindings
        self.master.bind('<Left>', self.show_prev_image_key)
        self.master.bind('<Right>', self.show_next_image_key)
        self.master.bind('<Shift-Left>', self.show_prev_group)
        self.master.bind('<Shift-Right>', self.show_next_group)
        self.master.bind('<Shift-Home>', self.open_image_location)
        self.master.bind('<Shift-Delete>', self._delete_image)
        self.toggle_theme()
        self.master.update()


    def set_mode(self, mode, do_update=True):
        '''
        Change the current mode of the application.
        '''
        self.mode = mode
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
        if self.compare is not None and self.base_dir != self.compare.base_dir:
            self.compare = None
            self.set_group_state_label(None, 0)
            self.remove_all_mode_buttons()
            if self.mode != Mode.SEARCH:
                self.clear_image()
            elif self.is_toggled_view_matches:
                self.toggle_image_view()
        self.set_base_dir_box.delete(0, "end")
        self.set_base_dir_box.insert(0, self.base_dir)
        self.file_browser.set_directory(self.base_dir)
        if self.compare is None and self.mode != Mode.SEARCH:
            self.set_mode(Mode.BROWSE)
            self.show_next_image()
        self.master.update()

    def get_base_dir(self) -> str:
        return "." if (self.base_dir is None
                       or self.base_dir == "") else self.base_dir

    def get_search_dir(self) -> str:
        return self.get_base_dir() if self.search_dir is None else self.search_dir

    def get_search_file_path(self) -> str:
        '''
        Get the search file path provided in the UI.
        '''
        image_path = self.search_image.get()
        if image_path is None or image_path == "":
            self.search_image_full_path = None
            return None

        search_file_str = self.search_image_full_path
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

    def get_counter_limit(self) -> int:
        counter_limit_str = self.set_counter_limit.get()
        if counter_limit_str == "":
            return None
        try:
            return int(counter_limit_str)
        except Exception:
            self.alert("Invalid Setting",
                       "Counter limit must be an integer value.", kind="error")
            raise AssertionError("Counter limit must be an integer value.")

    def get_compare_faces(self) -> bool:
        compare_faces_str = self.compare_faces.get()
        return compare_faces_str == "" or compare_faces_str == "Yes"

    def get_overwrite(self) -> bool:
        overwrite_str = self.overwrite.get()
        return overwrite_str == "" or overwrite_str == "Yes"

    def get_color_diff_threshold(self) -> int:
        color_diff_threshold_str = self.color_diff_threshold.get()
        if color_diff_threshold_str == "":
            return None
        try:
            return int(color_diff_threshold_str)
        except Exception:
            return 20

    def get_inclusion_pattern(self) -> str:
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
        fit_dims = scale_dims((img.width, img.height), self.canvas.get_size(), maximize=self.fill_canvas)
        img = img.resize(fit_dims)
        return ImageTk.PhotoImage(img)

    def set_search_image(self) -> None:
        '''
        Set the search image using the provided UI value, or prompt the
        user for selection. Set the mode based on the result.
        '''
        image_path = self.get_search_file_path()

        if image_path is None or (self.search_image_full_path is not None
                                  and image_path == self.search_image_full_path):
            image_path = filedialog.askopenfilename(
                initialdir=self.get_search_dir(), title="Select image file",
                filetypes=(("jpg files", "*.jpg"),
                           ("jpeg files", "*.jpeg"),
                           ("png files", "*.png"),
                           ("tiff files", "*.tiff"),
                           ("gif files", "*.gif")
                           ))

        if image_path is not None and image_path != "":
            self.search_image.set(basename(image_path))
            self.search_dir = os.path.dirname(image_path)
            self.search_image_full_path = image_path
            self.show_searched_image()

        if self.search_image_full_path is None or self.search_image_full_path == "":
            self.set_mode(Mode.GROUP)
        else:
            self.set_mode(Mode.SEARCH)

        self.master.update()

        if self.compare is not None:
           self.run_compare()

    def show_searched_image(self) -> None:
        if self.search_image_full_path is not None:
            self.create_image(self.search_image_full_path, extra_text="(search image)")

    def show_prev_image_key(self, event) -> None:
        self.show_prev_image(False)

    def show_prev_image(self, show_alert=True) -> None:
        '''
        If similar image results are present in any mode, display the previous
        in the list of matches.
        '''
        if self.mode == Mode.BROWSE:
            self.master.update()
            self.create_image(self.file_browser.previous_file())
            return
        if self.files_matched is None:
            return
        elif len(self.files_matched) == 0:
            if show_alert:
                self.alert("Search required",
                           "No matches found. Search again to find potential matches.",
                           kind="info")
            return

        self.is_toggled_view_matches = True
        
        if self.match_index > 0:
            self.match_index -= 1
        else:
            self.match_index = len(self.files_matched) - 1
        
        self.master.update()
        self.create_image(self.files_matched[self.match_index])

    def show_next_image_key(self, event) -> None:
        self.show_next_image(False)

    def show_next_image(self, show_alert=True) -> None:
        '''
        If similar image results are present in any mode, display the next
        in the list of matches.
        '''
        if self.mode == Mode.BROWSE:
            self.master.update()
            self.create_image(self.file_browser.next_file())
            return
        if self.files_matched is None:
            return
        elif len(self.files_matched) == 0:
            if show_alert:
                self.alert("Search required",
                           "No matches found. Search again to find potential matches.",
                           kind="info")
            return

        self.is_toggled_view_matches = True

        if len(self.files_matched) > self.match_index + 1:
            self.match_index += 1
        else:
            self.match_index = 0

        self.master.update()
        self.create_image(self.files_matched[self.match_index])

    def show_prev_group(self, event=None) -> None:
        '''
        While in group mode, navigate to the previous group.
        '''
        if (self.file_groups is None or len(self.group_indexes) == 0
                or self.current_group_index == max(self.group_indexes)):
            self.current_group_index = 0
        else:
            self.current_group_index -= 1

        self.set_current_group()

    def show_next_group(self, event=None) -> None:
        '''
        While in group mode, navigate to the next group.
        '''
        if (self.file_groups is None or len(self.group_indexes) == 0
                or self.current_group_index + 1 == len(self.group_indexes)):
            self.current_group_index = 0
        else:
            self.current_group_index += 1

        self.set_current_group()

    def set_current_group(self) -> None:
        '''
        While in group mode, navigate between the groups.
        '''
        if self.mode == Mode.SEARCH:
            print("Invalid action, there should only be one group in search mode")
            return
        elif self.file_groups is None or len(self.file_groups) == 0:
            print("No groups found")
            return

        actual_group_index = self.group_indexes[self.current_group_index]
        self.current_group = self.file_groups[actual_group_index]
        self.match_index = 0
        self.files_matched = []

        for f in sorted(self.current_group, key=lambda f: self.current_group[f]):
            self.files_matched.append(f)

        self.set_group_state_label(self.current_group_index, len(self.files_matched))
        self.master.update()
        self.create_image(self.files_matched[self.match_index])

    def set_current_image_run_search(self) -> None:
        '''
        Execute a new image search from the provided search image.
        '''
        if not self.has_image_matches:
            self.alert("Search required",
                       "No matches found. Search again to find potential matches.",
                       kind="info")
        search_image_path = self.search_image.get()
        search_image_path = get_valid_file(
            self.get_base_dir(), search_image_path)
        if (self.files_matched is None
                or search_image_path == self.files_matched[self.match_index]):
            self.alert("Already set image",
                       "Current image is already the search image.",
                       kind="info")
        self.search_image.set(basename(self.files_matched[self.match_index]))
        self.master.update()
        self.run_compare()

    def create_image(self, image_path, extra_text=None) -> None:
        '''
        Show an image in the main content pane of the UI.
        '''
        if (isinstance(self.img, GifImageUI)):
            self.img.stop_display()
        self.img = self.get_image_to_fit(image_path)
        if (isinstance(self.img, GifImageUI)):
            self.img.display(self.canvas)
        else:
            self.canvas.create_image_center(self.img)
        if self.label_current_image_name is None:
            self.label_current_image_name = Label(self.sidebar)
            self.add_label(self.label_current_image_name, "", pady=30)
        text = _wrap_text_to_fit_length(basename(image_path), 30)
        if extra_text is not None:
            text += "\n" + extra_text
        self.label_current_image_name["text"] = text

    def clear_image(self) -> None:
        if self.img is not None and self.canvas is not None:
            if (isinstance(self.img, GifImageUI)):
                self.img.stop_display()
            self.destroy_grid_element("label_current_image_name")
            self.label_current_image_name = None
            self.canvas.clear_image()
            self.master.update()

    def toggle_image_view(self) -> None:
        '''
        While in search mode, toggle between the search image and the results.
        '''
        if self.mode != Mode.SEARCH:
            return

        if self.is_toggled_view_matches:
            self.show_searched_image()
        else:
            self.create_image(self.files_matched[self.match_index])

        self.is_toggled_view_matches = not self.is_toggled_view_matches

    def add_all_mode_buttons(self) -> None:
        self.add_button("prev_image_match_btn", "Previous image match", self.show_prev_image)
        self.add_button("next_image_match_btn", "Next image match", self.show_next_image)
        self.add_button("search_current_image_btn", "Search current image", self.set_current_image_run_search)
        self.add_button("open_image_location_btn", "Open image location", self.open_image_location)
        self.add_button("delete_image_btn", "---- DELETE ----", self.delete_image)

    def remove_all_mode_buttons(self) -> None:
        self.destroy_grid_element("prev_group_btn")
        self.destroy_grid_element("next_group_btn")
        self.destroy_grid_element("prev_image_match_btn")
        self.destroy_grid_element("next_image_match_btn")
        self.destroy_grid_element("search_current_image_btn")
        self.destroy_grid_element("delete_image_btn")
        self.destroy_grid_element("open_image_location_btn")
        for mode in self.has_added_buttons_for_mode.keys():
            self.has_added_buttons_for_mode[mode] = False
        self.master.update()

    def add_buttons_for_mode(self) -> None:
        if not self.has_added_buttons_for_mode[self.mode]:
            if self.mode == Mode.SEARCH:
                self.add_button("toggle_image_view_btn", "Toggle image view", self.toggle_image_view)
                self.add_button("replace_current_image_btn", "Replace with search image",
                                self.replace_current_image_with_search_image)
                if not self.has_added_buttons_for_mode[Mode.GROUP]:
                    self.add_all_mode_buttons()
            elif self.mode == Mode.GROUP:
                self.add_button("prev_group_btn", "Previous group", self.show_prev_group)
                self.add_button("next_group_btn", "Next group", self.show_next_group)
                if not self.has_added_buttons_for_mode[Mode.SEARCH]:
                    self.add_all_mode_buttons()
            elif self.mode == Mode.REM_DUP:
                self.add_button("rem_dups_btn", "Remove duplicates", self.rem_dups)

            self.has_added_buttons_for_mode[self.mode] = True

    def run_with_progress(self, exec_func, args=None) -> None:
        def run_with_progress_async(self) -> None:
            self.progress_bar = Progressbar(self.sidebar, orient=HORIZONTAL, length=100, mode='indeterminate')
            self.apply_to_grid(self.progress_bar)
            self.progress_bar.start()
            if args is None:
                exec_func()
            else:
                exec_func(args)
            self.progress_bar.stop()
            self.progress_bar.grid_forget()
            self.destroy_grid_element("progress_bar")

        thread = threading.Thread(target=run_with_progress_async, args=[self])
        thread.start()

    def run_compare(self) -> None:
        self.run_with_progress(self._run_compare)

    def _run_compare(self) -> None:
        '''
        Execute operations on the Compare object in any mode. Create a new
        Compare object.
        '''
        search_file_path = self.get_search_file_path()
        counter_limit = self.get_counter_limit()
        compare_faces = self.get_compare_faces()
        overwrite = self.get_overwrite()
        color_diff_threshold = self.get_color_diff_threshold()
        inclusion_pattern = self.get_inclusion_pattern()
        get_new_data = True
        self.current_group_index = 0
        self.current_group = None
        self.max_group_index = 0
        self.group_indexes = []
        self.files_matched = []
        self.match_index = 0

        if self.compare is None or self.compare.base_dir != self.get_base_dir():
            self.label_state["text"] = _wrap_text_to_fit_length(
                "Gathering image data..."
                + " setup may take a while depending on number"
                + " of files involved.", 30)
            self.compare = Compare(self.base_dir,
                                   search_file_path=search_file_path,
                                   counter_limit=counter_limit,
                                   use_thumb=True,
                                   compare_faces=compare_faces,
                                   color_diff_threshold=color_diff_threshold,
                                   inclusion_pattern=inclusion_pattern,
                                   overwrite=overwrite,
                                   verbose=True)
        else:
            get_new_data = self.is_new_data_request_required(counter_limit,
                                                             color_diff_threshold,
                                                             inclusion_pattern,
                                                             overwrite)
            self.compare.set_search_file_path(search_file_path)
            self.compare.counter_limit = counter_limit
            self.compare.compare_faces = compare_faces
            self.compare.color_diff_threshold = color_diff_threshold
            self.compare.inclusion_pattern = inclusion_pattern
            self.compare.overwrite = overwrite
            self.compare.print_settings()
        
        if self.compare.is_run_search:
            self.set_mode(Mode.SEARCH, do_update=False)
            if not self.is_toggled_view_matches:
                self.is_toggled_view_matches = True
        else:
            if self.mode == Mode.SEARCH:
                res = self.alert("Confirm group run",
                                    "Search mode detected, please confirm switch to group mode before run. "
                                    + "Group mode will take longer as all images in the base directory are compared.",
                                    kind="warning")
                if res != messagebox.YES:
                    return
            self.set_mode(Mode.GROUP, do_update=False)

        if get_new_data:
            print("Gathering files for compare")
            self.compare.get_files()
            print("Gathering image data for compare")
            self.compare.get_data()

        if self.compare.is_run_search:
            self.run_search()
        else:
            self.run_group()

    def is_new_data_request_required(self, counter_limit, color_diff_threshold,
                                     inclusion_pattern, overwrite):
        return (self.compare.counter_limit != counter_limit
                or self.compare.color_diff_threshold != color_diff_threshold
                or self.compare.inclusion_pattern != inclusion_pattern
                or (not self.compare.overwrite and overwrite))

    def run_group(self) -> None:
        self.label_state["text"] = _wrap_text_to_fit_length(
            "Running image comparisons...", 30)
        self.files_grouped, self.file_groups = self.compare.run()
        
        if len(self.files_grouped) == 0:
            self.has_image_matches = False
            self.label_state["text"] = "Set a directory and search file."
            self.alert("No Groups Found",
                        "None of the files can be grouped with current settings.",
                        kind="info")
            return

        self.group_indexes = self.compare.sort_groups(self.file_groups)
        self.max_group_index = max(self.file_groups.keys())
        self.add_buttons_for_mode()
        self.current_group_index = 0
        has_found_stranded_group_members = False

        while len(self.file_groups[self.group_indexes[self.current_group_index]]) == 1:
            has_found_stranded_group_members = True
            self.current_group_index += 1

        self.set_current_group()
        if has_found_stranded_group_members:
            self.alert("Stranded Group Members Found",
                        "Some group members were left stranded by the grouping process.",
                        kind="info")

    def run_search(self) -> None:
        self.label_state["text"] = _wrap_text_to_fit_length(
            "Running image comparison with search file...", 30)
        self.files_grouped = self.compare.run_search()
        
        if len(self.files_grouped) == 0:
            self.has_image_matches = False
            self.label_state["text"] = "Set a directory and search file."
            self.alert("No Match Found",
                        "None of the files match the search file with current settings.",
                        kind="info")
            return

        for f in sorted(self.files_grouped, key=lambda f: self.files_grouped[f]):
            self.files_matched.append(f)

        self.match_index = 0
        self.has_image_matches = True
        self.label_state["text"] = _wrap_text_to_fit_length(
            str(len(self.files_matched)) + " possibly related images found.", 30)

        self.add_buttons_for_mode()
        self.create_image(self.files_matched[self.match_index])
        
    def set_group_state_label(self, group_number, size):
        if group_number is None:
            self.label_state["text"] = ""
        else:
            self.label_state["text"] = _wrap_text_to_fit_length(
                f"Group {group_number + 1} of {len(self.file_groups)}\nSize: {size}", 30)

    def is_toggled_search_image(self):
        return self.mode == Mode.SEARCH and not self.is_toggled_view_matches

    def get_active_image_filepath(self):
        if self.is_toggled_search_image():
            filepath = self.search_image_full_path
        else:
            filepath = self.files_matched[self.match_index]
        return get_valid_file(self.get_base_dir(), filepath)

    def open_image_location(self, event):
        filepath = self.get_active_image_filepath()

        if filepath is not None:
            print("Opening file location: " + filepath)
            open_file_location(filepath)
        else:
            print("Failed to open location of current file, unable to get valid filepath")

    def _delete_image(self, event):
        self.delete_image()

    def delete_image(self):
        '''
        Delete the currently displayed image from the filesystem.
        '''
        is_toggle_search_image = self.is_toggled_search_image()

        if len(self.files_matched) == 0 and not is_toggle_search_image:
            print(
                "Invalid action, the button should not be present if no files are available")
            return
        elif is_toggle_search_image and (self.search_image_full_path is None or self.search_image_full_path == ""):
            print("Invalid action, search image not found")
            return

        filepath = self.get_active_image_filepath()

        if filepath is not None:
            print("Removing file: " + filepath)
            os.remove(filepath)
            self.update_groups_for_removed_file()
        else:
            print("Failed to delete current file, unable to get valid filepath")

    def replace_current_image_with_search_image(self):
        '''
        Overwrite the file at the path of the current image with the
        search image.
        '''
        if (self.mode != Mode.SEARCH
                or len(self.files_matched) == 0
                or not os.path.exists(self.search_image_full_path)):
            return

        _filepath = self.files_matched[self.match_index]
        filepath = get_valid_file(self.get_base_dir(), _filepath)

        if filepath is None:
            print("Invalid target filepath for replacement: " + _filepath)
            return

        os.rename(self.search_image_full_path, filepath)
        print("Moved search image to " + filepath)

    def update_groups_for_removed_file(self):
        '''
        After a file has been removed, delete the cached image path for it and
        remove the group if only one file remains in it.

        NOTE: This would be more complicated if there was not a guarantee that
        groups are disjoint.
        '''
        if len(self.files_matched) < 3:
            if self.mode != Mode.GROUP:
                return

            # remove this group as it will only have one file
            self.files_grouped = {
                k: v for k, v in self.files_grouped.items() if v not in self.files_matched}
            actual_index = self.group_indexes[self.current_group_index]
            del self.file_groups[actual_index]
            del self.group_indexes[self.current_group_index]

            if len(self.file_groups) == 0:
                self.alert("No More Groups",
                           "There are no more image groups remaining for this directory and current filter settings.",
                           kind="info")
                self.current_group_index = 0
                self.files_grouped = None
                self.file_groups = None
                self.match_index = 0
                self.files_matched = []
                self.group_indexes = []
                return
            elif self.current_group_index == len(self.file_groups):
                self.current_group_index = 0

            self.set_current_group()
        else:
            filepath = self.files_matched[self.match_index]
            self.files_grouped = {
                k: v for k, v in self.files_grouped.items() if v != filepath}
            del self.files_matched[self.match_index]

            if self.match_index == len(self.files_matched):
                self.match_index = 0

            self.master.update()
            self.create_image(self.files_matched[self.match_index])

    def alert(self, title, message, kind="info", hidemain=True) -> None:
        if kind not in ("error", "warning", "info"):
            raise ValueError("Unsupported alert kind.")

        show_method = getattr(messagebox, "show{}".format(kind))
        return show_method(title, message)

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
            button
            self.apply_to_grid(button)

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
    root.mainloop()
    exit()
