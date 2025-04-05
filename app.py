import os
import random
import signal
import sys
import time
import traceback

from tkinter import Frame, Toplevel, PhotoImage, Label, Checkbutton, BooleanVar, StringVar, filedialog, messagebox
from tkinter import BOTH, END, N, NW, YES, HORIZONTAL, W
import tkinter.font as fnt
from tkinter.ttk import Button, Entry, OptionMenu, Progressbar, Style
from ttkthemes import ThemedTk

from compare.compare_args import CompareArgs
from compare.compare_wrapper import CompareWrapper
from compare.prevalidations_window import PrevalidationsWindow
from extensions.refacdir_client import RefacDirClient
from extensions.sd_runner_client import SDRunnerClient
from files.file_actions_window import FileActionsWindow
from files.file_browser import FileBrowser, SortBy
from files.go_to_file import GoToFile
from files.marked_file_mover import MarkedFiles
from files.recent_directory_window import RecentDirectories, RecentDirectoryWindow
from files.type_configuration_window import TypeConfigurationWindow
from image.media_frame import MediaFrame
from lib.aware_entry import AwareEntry
from utils.app_actions import AppActions
from utils.app_info_cache import app_info_cache
from utils.app_style import AppStyle
from utils.config import config, FileCheckConfig, SlideshowConfig
from utils.constants import Mode, CompareMode, Direction
from utils.help_and_config import HelpAndConfig
from utils.running_tasks_registry import periodic, start_thread
from utils.translations import I18N
from utils.utils import Utils, ModifierKey
# must import after config because of dynamic import
from image.image_details import ImageDetails

_ = I18N._

try:
    from send2trash import send2trash
except Exception:
    Utils.log_red("Could not import trashing utility - all deleted images will be deleted instantly")



class Sidebar(Frame):
    def __init__(self, master=None, cnf={}, **kw):
        Frame.__init__(self, master=master, cnf=cnf, **kw)


class ProgressListener:
    def __init__(self, update_func):
        self.update_func = update_func

    def update(self, context, percent_complete):
        self.update_func(context, percent_complete)


class App():
    '''
    UI for comparing image files and making related file changes.
    '''
    secondary_top_levels = {}
    open_windows = []
    window_index = 0
    true_master = None

    @staticmethod
    def add_secondary_window(base_dir, image_path=None, do_search=False, master=None):
        if not config.always_open_new_windows:
            for window in App.open_windows:
                if window.base_dir == base_dir:
                    if image_path is not None and image_path != "":
                        if do_search:
                            # print("Doing search: " + str(image_path))
                            window.search_img_path_box.delete(0, "end")
                            window.search_img_path_box.insert(0, image_path)
                            window.set_search()
                        else:
                            window.go_to_file(search_text=image_path)
                    window.media_canvas.focus()
                    return
                # print(f"app base dir \"{_app.base_dir}\" was not base dir: {base_dir}")
        if master is None:
            # Usually want to do this because if a secondary window is the source of another secondary window and that initial secondary window
            # is closed, the second secondary window will also be closed because its master has been destroyed.
            master = App.true_master
        top_level = Toplevel(master)
        top_level.title(_(" Simple Image Compare "))
        top_level.geometry(config.default_secondary_window_size)
        window_id = random.randint(1000000000, 9999999999)
        App.secondary_top_levels[window_id] = top_level  # Keep reference to avoid gc
        if do_search and (image_path is None or image_path == ""):
            do_search = False
        window = App(top_level, base_dir=base_dir, image_path=image_path,
                   grid_sidebar=False, do_search=do_search, window_id=window_id)

    @staticmethod
    def get_window(window_id=None, base_dir=None, img_path=None, refocus=False):
        for window in App.open_windows:
            if window.window_id == window_id or \
                    (base_dir is not None and window.base_dir == base_dir) or \
                    (img_path is not None and window.img_path == img_path):
                if img_path is not None:
                    window.go_to_file(search_text=os.path.basename(img_path), exact_match=True)
                if refocus:
                    window.refocus()
                return window
        return None  # raise Exception(f"No window found for window id {window_id} or base dir {base_dir}")

    @staticmethod
    def find_window_with_compare(default_window=None):
        for _app in App.open_windows:
            if _app.compare_wrapper.has_compare():
                return _app
        return default_window

    @staticmethod
    def refresh_all_compares():
        for _app in App.open_windows:
            _app.refresh_compare()

    def toggle_theme(self, to_theme=None, do_toast=True):
        if (to_theme is None and AppStyle.IS_DEFAULT_THEME) or to_theme == AppStyle.LIGHT_THEME:
            if to_theme is None:
                self.master.set_theme("breeze", themebg="black")  # Changes the window to light theme
            AppStyle.BG_COLOR = "gray"
            AppStyle.FG_COLOR = "black"
        else:
            if to_theme is None:
                self.master.set_theme("black", themebg="black")  # Changes the window to dark theme
            AppStyle.BG_COLOR = config.background_color if config.background_color and config.background_color != "" else "#26242f"
            AppStyle.FG_COLOR = config.foreground_color if config.foreground_color and config.foreground_color != "" else "white"
        AppStyle.IS_DEFAULT_THEME = (not AppStyle.IS_DEFAULT_THEME or to_theme
                                     == AppStyle.DARK_THEME) and to_theme != AppStyle.LIGHT_THEME
        self.master.config(bg=AppStyle.BG_COLOR)
        self.sidebar.config(bg=AppStyle.BG_COLOR)
        self.media_canvas.set_background_color(AppStyle.BG_COLOR)
        for name, attr in self.__dict__.items():
            if isinstance(attr, Label):
                attr.config(bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR,
                            font=fnt.Font(size=config.font_size))
            elif isinstance(attr, Checkbutton):
                attr.config(bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR,
                            selectcolor=AppStyle.BG_COLOR, font=fnt.Font(size=config.font_size))
        self.master.update()
        if do_toast:
            self.toast(_("Theme switched to {0}.").format(AppStyle.get_theme_name()))

    def __init__(self, master, base_dir=None, image_path=None, grid_sidebar=config.sidebar_visible, do_search=False, window_id=0):
        self.master = master
        if window_id == 0:
            App.true_master = master
        self.master.resizable(1, 1)
        self.master.columnconfigure(0, weight=1)
        self.master.columnconfigure(1, weight=9)
        self.master.rowconfigure(0, weight=1)
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.window_id = window_id

        if not self.is_secondary():
            TypeConfigurationWindow.load_pending_changes() # cannot be in load_info_cache because it is called before file_browser initialization
            TypeConfigurationWindow.apply_changes()

        self.file_browser = FileBrowser(recursive=config.image_browse_recursive, sort_by=config.sort_by)
        self.file_check_config = FileCheckConfig(self.window_id)
        self.slideshow_config = SlideshowConfig(self.window_id)
        self.mode = Mode.BROWSE
        self.fullscreen = False
        self.delete_lock = False
        self.img_path = None
        self.prev_img_path = None
        self.is_toggled_view_matches = True
        self.direction = Direction.FORWARD
        self.has_added_buttons_for_mode = {
            Mode.BROWSE: False,
            Mode.GROUP: False,
            Mode.SEARCH: False,
            Mode.DUPLICATES: False
        }

        Style().configure(".", font=('Helvetica', config.font_size))

        app_actions = {
            "new_window": App.add_secondary_window,
            "get_window": App.get_window,
            "refresh_all_compares": App.refresh_all_compares,
            "find_window_with_compare": App.find_window_with_compare,
            "toast": self.toast,
            "alert": self.alert,
            "refresh": self.refresh,
            "refocus": self.refocus,
            "set_mode": self.set_mode,
            "get_active_media_filepath": self.get_active_media_filepath,
            "create_image": self.create_image,
            "show_next_media": self.show_next_media,
            "get_media_details": self.get_media_details,
            "run_image_generation": self.run_image_generation,
            "set_marks_from_downstream_related_images": self.set_marks_from_downstream_related_images,
            "go_to_file": self.go_to_file,
            "set_base_dir": self.set_base_dir,
            "get_base_dir": self.get_base_dir,
            "delete": self._handle_delete,
            "open_move_marks_window": self.open_move_marks_window,
            "release_media_canvas": lambda: self.media_canvas.release_media(),
            "hide_current_media": self.hide_current_media,
            "store_info_cache": self.store_info_cache,
            "_set_toggled_view_matches": self._set_toggled_view_matches,
            "_set_label_state": self._set_label_state,
            "_add_buttons_for_mode": self._add_buttons_for_mode,
        }
        self.app_actions = AppActions(actions=app_actions)

        self.base_dir = Utils.get_user_dir() if base_dir is None else base_dir
        self.search_dir = Utils.get_user_dir()

        self.compare_wrapper = CompareWrapper(master, config.compare_mode, self.app_actions)
        self.sd_runner_client = SDRunnerClient()
        self.refacdir_client = RefacDirClient()

        # Sidebar
        self.sidebar = Sidebar(self.master)
        self.sidebar.columnconfigure(0, weight=1)
        self.row_counter = 0
        self.sidebar.grid(column=0, row=self.row_counter)

        # The top part is a label with info
        self.label_mode = Label(self.sidebar)
        self.label_state = Label(self.sidebar)
        self.add_label(self.label_mode, "", sticky=N)
        self.add_label(self.label_state, _("Set a directory to run comparison."), pady=10)

        #################################### Settings UI
        self.toggle_theme_btn = None
        self.set_base_dir_btn = None
        self.set_search_btn = None
        self.search_text_btn = None
        self.add_button("toggle_theme_btn", _("Toggle theme"), self.toggle_theme)
        self.add_button("set_base_dir_btn", _("Set directory"), self.set_base_dir)
        self.set_base_dir_box = self.new_entry(text=_("Add dirpath..."))
        self.apply_to_grid(self.set_base_dir_box, sticky=W)

        self.add_button("set_search_btn", _("Set search file"), self.set_search_for_image)
        self.search_image = StringVar()
        self.search_img_path_box = self.new_entry(self.search_image)
        if do_search and image_path is not None:
            self.search_img_path_box.insert(0, image_path)
        self.search_img_path_box.bind("<Return>", self.set_search_for_image)
        self.apply_to_grid(self.search_img_path_box, sticky=W)

        self.add_button("search_text_btn", _("Search text (embedding mode)"), self.set_search_for_text)
        self.search_text = StringVar()
        self.search_text_box = self.new_entry(self.search_text)
        self.search_text_box.bind("<Return>", self.set_search_for_text)
        self.apply_to_grid(self.search_text_box, sticky=W)
        self.search_text_negative = StringVar()
        self.search_text_negative_box = self.new_entry(self.search_text_negative)
        self.search_text_negative_box.bind("<Return>", self.set_search_for_text)
        self.apply_to_grid(self.search_text_negative_box, sticky=W)

        self.label_compare_mode = Label(self.sidebar)
        self.add_label(self.label_compare_mode, _("Compare mode"))
        self.compare_mode_var = StringVar()
        self.compare_mode_choice = OptionMenu(self.sidebar, self.compare_mode_var, self.compare_wrapper.compare_mode.get_text(),
                                              *CompareMode.members(), command=self.set_compare_mode)
        self.apply_to_grid(self.compare_mode_choice, sticky=W)

        self.label_compare_threshold = Label(self.sidebar)
        self.add_label(self.label_compare_threshold, self.compare_wrapper.compare_mode.threshold_str())
        self.compare_threshold = StringVar()
        if self.compare_wrapper.compare_mode == CompareMode.COLOR_MATCHING:
            default_val = config.color_diff_threshold
        else:
            default_val = config.embedding_similarity_threshold
        self.compare_threshold_choice = OptionMenu(self.sidebar, self.compare_threshold,
                                                   str(default_val), *self.compare_wrapper.compare_mode.threshold_vals())
        self.apply_to_grid(self.compare_threshold_choice, sticky=W)

        self.compare_faces = BooleanVar(value=False)
        self.compare_faces_choice = Checkbutton(self.sidebar, text=_('Compare faces'), variable=self.compare_faces)
        self.apply_to_grid(self.compare_faces_choice, sticky=W)

        self.overwrite = BooleanVar(value=False)
        self.overwrite_choice = Checkbutton(self.sidebar, text=_('Overwrite cache'), variable=self.overwrite)
        self.apply_to_grid(self.overwrite_choice, sticky=W)

        self.store_checkpoints = BooleanVar(value=config.store_checkpoints)
        self.store_checkpoints_choice = Checkbutton(self.sidebar, text=_('Store checkpoints'), variable=self.store_checkpoints)
        self.apply_to_grid(self.store_checkpoints_choice, sticky=W)

        self.label_counter_limit = Label(self.sidebar)
        self.add_label(self.label_counter_limit, _("Max files to compare"))
        self.set_counter_limit = self.new_entry()
        self.set_counter_limit.insert(0, str(config.file_counter_limit))
        self.apply_to_grid(self.set_counter_limit, sticky=W)

        self.label_inclusion_pattern = Label(self.sidebar)
        self.add_label(self.label_inclusion_pattern, _("Filter files by glob pattern"))
        self.inclusion_pattern = StringVar()
        self.set_inclusion_pattern = self.new_entry(self.inclusion_pattern)
        self.set_inclusion_pattern.bind("<Return>", self.set_file_filter)
        self.apply_to_grid(self.set_inclusion_pattern, sticky=W)

        self.label_sort_by = Label(self.sidebar)
        self.add_label(self.label_sort_by, _("Browsing mode - Sort by"))
        self.sort_by = StringVar()
        self.sort_by_choice = OptionMenu(self.sidebar, self.sort_by, config.sort_by.get_text(),
                                         *SortBy.members(), command=self.set_sort_by)
        self.apply_to_grid(self.sort_by_choice, sticky=W)

        self.image_browse_recurse_var = BooleanVar(value=config.image_browse_recursive)
        self.image_browse_recurse = Checkbutton(self.sidebar, text=_('Recurse subdirectories'),
                                                variable=self.image_browse_recurse_var, command=self.toggle_image_browse_recursive)
        self.apply_to_grid(self.image_browse_recurse, sticky=W)

        fill_canvas_var = BooleanVar(value=config.fill_canvas)
        self.fill_canvas_choice = Checkbutton(self.sidebar, text=_('Image resize to full window'), variable=fill_canvas_var, command=self.toggle_fill_canvas)
        self.apply_to_grid(self.fill_canvas_choice, sticky=W)

        search_return_closest_var = BooleanVar(value=config.search_only_return_closest)
        self.search_return_closest_choice = Checkbutton(self.sidebar, text=_('Search only return closest'),
                                                        variable=search_return_closest_var, command=self.compare_wrapper.toggle_search_only_return_closest)
        self.apply_to_grid(self.search_return_closest_choice, sticky=W)

        ################################ Run context-aware UI elements
        self.progress_bar = None
        self.run_compare_btn = None
        self.add_button("run_compare_btn", _("Run image compare"), self.run_compare)
        self.find_duplicates_btn = None
        self.add_button("find_duplicates_btn", _("Find duplicates"), lambda: self.run_compare(find_duplicates=True))
        self.image_details_btn = None
        self.add_button("image_details_btn", _("Image details"), self.get_media_details)
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
        self.add_button("search_current_image_btn", _("Search current image"), self.set_current_image_run_search)
        self.add_button("open_image_location_btn", _("Open image location"), self.open_image_location)
        self.add_button("copy_image_path_btn", _("Copy image path"), self.copy_image_path)
        self.add_button("delete_image_btn", _("---- DELETE ----"), self.delete_image)

        # Image panel and state management
        self.master.update()
        self.media_canvas = MediaFrame(self.master, config.fill_canvas)

        # Default mode is BROWSE - GROUP and SEARCH are only valid modes when a compare is run
        self.set_mode(Mode.BROWSE)

        ################################ Key bindings
        self.master.bind('<Left>', lambda e: self.check_focus(e, self.show_prev_media))
        self.master.bind('<Right>', lambda e: self.check_focus(e, self.show_next_media))
        self.master.bind('<Shift-BackSpace>', lambda e: self.check_focus(e, self.go_to_previous_image))
        self.master.bind('<Shift-Left>', lambda event: self.compare_wrapper.show_prev_group(file_browser=(self.file_browser if self.mode == Mode.BROWSE else None)))
        self.master.bind('<Shift-Right>', lambda event: self.compare_wrapper.show_next_group(file_browser=(self.file_browser if self.mode == Mode.BROWSE else None)))
        self.master.bind('<Shift-O>', lambda e: self.check_focus(e, self.open_image_location))
        self.master.bind('<Shift-P>', lambda e: self.check_focus(e, self.open_image_in_gimp))
        self.master.bind('<Shift-Delete>', lambda e: self.check_focus(e, self.delete_image))
        self.master.bind("<F11>", self.toggle_fullscreen)
        self.master.bind("<Shift-F>", lambda e: self.check_focus(e, self.toggle_fullscreen))
        self.master.bind("<Escape>", lambda e: self.end_fullscreen() and self.refocus())
        self.master.bind("<Shift-D>", lambda e: self.check_focus(e, self.get_media_details))
        self.master.bind("<Shift-R>", lambda e: self.check_focus(e, self.show_related_image))
        self.master.bind("<Shift-T>", lambda e: self.check_focus(e, self.find_related_images_in_open_window))
        self.master.bind("<Shift-Y>", lambda e: self.check_focus(e, self.set_marks_from_downstream_related_images))
        self.master.bind("<Shift-V>", lambda e: self.check_focus(e, self.hide_current_media))
        self.master.bind("<Shift-B>", lambda e: self.check_focus(e, self.clear_hidden_images))
        self.master.bind("<Shift-J>", lambda e: self.check_focus(e, self.run_prevalidations_for_base_dir))
        self.master.bind("<Shift-H>", lambda e: self.check_focus(e, self.get_help_and_config))
        self.master.bind("<Shift-S>", lambda e: self.check_focus(e, self.toggle_slideshow))
        self.master.bind("<MouseWheel>", lambda event: None if (event.state & 0x1) != 0 else (self.show_next_media() if event.delta > 0 else self.show_prev_media()))
        self.master.bind("<Button-2>", self.delete_image)
        self.master.bind("<Button-3>", self.trigger_image_generation)
        self.master.bind("<Shift-M>", lambda e: self.check_focus(e, self.add_or_remove_mark_for_current_image))
        self.master.bind("<Shift-N>", lambda e: self.check_focus(e, self._add_all_marks_from_last_or_current_group))
        self.master.bind("<Shift-G>", lambda e: self.check_focus(e, self.go_to_mark))
        self.master.bind("<Shift-K>", lambda e: self.check_focus(e, lambda: ImageDetails.open_temp_image_canvas(self.master, MarkedFiles.last_moved_image, self.app_actions)))
        self.master.bind("<Shift-A>", lambda e: self.check_focus(e, self.set_current_image_run_search))
        self.master.bind("<Shift-Z>", lambda e: self.check_focus(e, self.add_current_image_to_negative_search))
        self.master.bind("<Shift-U>", lambda e: self.check_focus(e, self.run_refacdir))
        self.master.bind("<Shift-I>", lambda e: self.check_focus(e, lambda: ImageDetails.run_image_generation_static(self.app_actions)))
        self.master.bind("<Shift-Q>", lambda e: self.check_focus(e, lambda: ImageDetails.randomly_modify_image(self.get_active_media_filepath(), self.app_actions)))
        self.master.bind("<Shift-L>", lambda e: self.check_focus(e, self.toggle_prevalidations))
        self.master.bind("<Shift-E>", lambda e: self.check_focus(e, lambda: ImageDetails.copy_prompt_no_break_static(self.get_active_media_filepath(), self.master, self.app_actions)))
        self.master.bind("<Control-Return>", lambda event: ImageDetails.run_image_generation_static(self.app_actions, event=event))
        self.master.bind("<Shift-C>", lambda e: self.check_focus(e, lambda: MarkedFiles.clear_file_marks(self.toast)))
        self.master.bind("<Control-Tab>", self.cycle_windows)
        self.master.bind("<Shift-Escape>", lambda event: self.on_closing() if self.is_secondary() else None)
        self.master.bind("<Control-q>", self.quit)
        self.master.bind("<Control-w>", self.open_secondary_compare_window)
        self.master.bind("<Control-a>", lambda event: self.open_secondary_compare_window(run_compare_image=self.img_path))
        self.master.bind("<Control-g>", self.open_go_to_file_window)
        self.master.bind("<Control-h>", self.toggle_sidebar)
        self.master.bind("<Control-C>", self.copy_marks_list)
        self.master.bind("<Control-n>", self.open_file_actions_window)
        self.master.bind("<Control-m>", self.open_move_marks_window)
        self.master.bind("<Control-k>", lambda event: self.open_move_marks_window(event=event, open_gui=False))
        self.master.bind("<Control-j>", self.open_prevalidations_window)
        self.master.bind("<Control-r>", self.run_previous_marks_action)
        self.master.bind("<Control-e>", self.run_penultimate_marks_action)
        self.master.bind("<Control-t>", self.run_permanent_marks_action)
        self.master.bind("<Control-d>", lambda event: MarkedFiles.set_current_marks_from_previous(self.toast))
        self.master.bind("<Control-z>", self.revert_last_marks_change)
        self.master.bind("<Control-x>", lambda event: MarkedFiles.undo_move_marks(None, self.app_actions))
        self.master.bind("<Control-s>", self.next_text_embedding_preset)
        self.master.bind("<Control-b>", self.return_to_browsing_mode)
        self.master.bind("<Control-v>", self.open_type_configuration_window)
        self.master.bind("<Control-L>", lambda event: Utils.open_log_file())
        self.master.bind("<Home>", self.home)
        self.master.bind("<End>", lambda event: self.home(last_file=True))
        self.master.bind("<Prior>", self.page_up)
        self.master.bind("<Next>", self.page_down)

        for i in range(10):
            self.master.bind(str(i), self.run_hotkey_marks_action)

        # Start async threads
        start_thread(self.check_files)

        self.toggle_theme(to_theme=(AppStyle.get_theme_name() if self.is_secondary() else None), do_toast=False)
        self.master.update()

        if config.use_file_paths_json:
            self.set_file_paths()

        if not grid_sidebar:
            self.toggle_sidebar()

        if base_dir:
            RecentDirectories.set_recent_directory(base_dir)
        else:
            base_dir = self.load_info_cache()

        App.open_windows.append(self)

        if base_dir is not None and base_dir != "" and base_dir != "." and os.path.isdir(base_dir):
            # print(f"Setting base dir to {base_dir} on window ID {self.window_id} before self.set_base_dir")
            self.set_base_dir_box.insert(0, base_dir)
            self.set_base_dir(base_dir_from_dir_window=base_dir)

        if not self.is_secondary():
            for _dir in app_info_cache.get_meta("secondary_base_dirs", default_val=[]):
                App.add_secondary_window(_dir)

        self.media_canvas.focus()

        if image_path is not None:
            if do_search:
                # Search image should be set above in search image box in this case.
                # Search for matches to given image immediately upon opening.
                self.set_search()
            else:
                self.go_to_file(search_text=image_path)

        if self.is_secondary():
            self.store_info_cache()

    def is_secondary(self):
        return self.window_id > 0

    def on_closing(self):
        self.store_info_cache(store_window_state=not self.is_secondary())
        if self.is_secondary():
            MarkedFiles.remove_marks_for_base_dir(self.base_dir, self.app_actions)
            for i in range(len(App.open_windows)):
                if App.open_windows[i].window_id == self.window_id:
                    del App.open_windows[i]
                    break
            del App.secondary_top_levels[self.window_id]
            self.file_check_config.end_filecheck()
            self.slideshow_config.end_slideshows()
        else:
            for _app in App.open_windows:
                _app.store_info_cache()
        self.master.destroy()

    def quit(self, event=None):
        res = self.alert(_("Confirm Quit"), _("Would you like to quit the application?"), kind="askokcancel")
        if res == messagebox.OK or res == True:
            Utils.log_yellow("Exiting application")
            for window in App.open_windows:
                if window.window_id == 0:
                    window.on_closing()

    def load_info_cache(self):
        try:
            MarkedFiles.load_target_dirs()
            RecentDirectories.load_recent_directories()
            FileActionsWindow.load_action_history()
            ImageDetails.load_image_generation_mode()
            PrevalidationsWindow.set_prevalidations()
            return app_info_cache.get_meta("base_dir")
        except Exception as e:
            Utils.log_red(e)

    def store_info_cache(self, store_window_state=False):
        base_dir = self.get_base_dir()
        Utils.log(f"Storing app info cache")
        if base_dir and base_dir != "":
            if not self.is_secondary():
                app_info_cache.set_meta("base_dir", base_dir)
            if self.img_path and self.img_path != "":
                app_info_cache.set(base_dir, "image_cursor", os.path.basename(self.img_path))
            app_info_cache.set(base_dir, "recursive", self.file_browser.is_recursive())
            app_info_cache.set(base_dir, "sort_by", self.file_browser.get_sort_by().get_text())
            app_info_cache.set(base_dir, "compare_mode", CompareMode.get(self.compare_mode_var.get()).get_text())
        if store_window_state:
            secondary_base_dirs = []
            for _app in App.open_windows:
                if _app.is_secondary() and _app.base_dir not in secondary_base_dirs:
                    secondary_base_dirs.append(_app.base_dir)
            app_info_cache.set_meta("secondary_base_dirs", secondary_base_dirs)
        RecentDirectories.store_recent_directories()
        MarkedFiles.store_target_dirs()
        FileActionsWindow.store_action_history()
        ImageDetails.store_image_generation_mode()
        PrevalidationsWindow.store_prevalidations()
        app_info_cache.store()

    def toggle_fullscreen(self, event=None):
        self.fullscreen = not self.fullscreen
        self.master.attributes("-fullscreen", self.fullscreen)
        self.sidebar.grid_remove() if self.fullscreen and self.sidebar.winfo_ismapped() else self.sidebar.grid()

    def toggle_sidebar(self, event=None):
        self.sidebar.grid_remove() if self.sidebar.winfo_ismapped() else self.sidebar.grid()

    def end_fullscreen(self, event=None):
        if self.fullscreen:
            self.toggle_fullscreen()
        return True

    def set_mode(self, mode, do_update=True):
        '''
        Change the current mode of the application.
        '''
        self.mode = mode
        self.label_mode['text'] = mode.get_text()
        if mode != Mode.SEARCH:
            self.destroy_grid_element("toggle_image_view_btn")
            self.destroy_grid_element("replace_current_image_btn")
        if mode != Mode.GROUP and mode != Mode.DUPLICATES:
            self.destroy_grid_element("prev_group_btn")
            self.destroy_grid_element("next_group_btn")
        if do_update:
            self.master.update()

    def set_sort_by(self, event):
        self.file_browser.set_sort_by(SortBy.get(self.sort_by.get()))
        self.file_browser.refresh()
        if self.mode == Mode.BROWSE:
            self.show_next_media()

    def set_compare_mode(self, event):
        self.compare_wrapper.compare_mode = CompareMode.get(self.compare_mode_var.get())
        self.label_compare_threshold["text"] = self.compare_wrapper.compare_mode.threshold_str()
        if self.compare_wrapper.compare_mode == CompareMode.COLOR_MATCHING:
            default_val = config.color_diff_threshold
        else:
            default_val = config.embedding_similarity_threshold
        self.compare_threshold.set(str(default_val))
        self.destroy_grid_element("compare_threshold_choice", decrement_row_counter=False)
        self.compare_threshold_choice = OptionMenu(self.sidebar, self.compare_threshold,
                                                   str(default_val), *self.compare_wrapper.compare_mode.threshold_vals())
        self.apply_to_grid(self.compare_threshold_choice, sticky=W, specific_row=13)
        self.store_info_cache()
        self.master.update()

    def set_file_filter(self, event=None):
        if self.slideshow_config.end_slideshows():
            self.toast(_("Ended slideshows"))
        self.file_browser.set_filter(self.inclusion_pattern.get())
        self.refresh(file_check=False)

    def toggle_fill_canvas(self):
        self.media_canvas.fill_canvas = not self.media_canvas.fill_canvas

    def toggle_image_browse_recursive(self):
        self.file_browser.set_recursive(self.image_browse_recurse_var.get())
        if self.mode == Mode.BROWSE and self.media_canvas.canvas.imagetk:
            self.show_next_media()

    def refresh_compare(self):
        self.compare_wrapper.clear_compare()
        self.return_to_browsing_mode(suppress_toast=True)

    def refocus(self, event=None):
        shift_key_pressed = Utils.modifier_key_pressed(event, keys_to_check=[ModifierKey.SHIFT])
        self.media_canvas.focus(refresh_image=shift_key_pressed)
        if config.debug:
            Utils.log_debug("Refocused main window")

    def refresh(self, show_new_images=False, refresh_cursor=False, file_check=True, removed_files=[]):
        active_media_filepath_in_removed_files = self.get_active_media_filepath() in removed_files
        # print(f"File cursor before: {self.file_browser.get_cursor()}")
        self.file_browser.refresh(
            refresh_cursor=refresh_cursor, file_check=file_check, removed_files=removed_files, direction=self.direction)
        # print(f"File cursor after: {self.file_browser.get_cursor()}")
        if len(removed_files) > 0:
            if self.mode == Mode.BROWSE:
                self._set_label_state()
            else:
                self._handle_remove_files_from_groups(removed_files)
            if self.compare_wrapper.has_compare():
                self.compare_wrapper.compare().remove_from_groups(removed_files)
        if self.file_browser.has_files():
            if self.mode != Mode.BROWSE:
                return
            if show_new_images:
                has_new_images = self.file_browser.update_cursor_to_new_images()
                if has_new_images:
                    self.show_next_media()
            if active_media_filepath_in_removed_files:
                self.last_chosen_direction_func()
            self._set_label_state()
            if show_new_images and has_new_images:
                # User may have started delete just before the image changes, lock for a short period after to ensure no misdeletion
                self.delete_lock = True
                time.sleep(1)
                self.delete_lock = False
        else:
            self.clear_image()
            self._set_label_state()
            self.alert(_("Warning"), _("No files found in directory after refresh."), kind="warning")
        if config.debug:
            Utils.log_debug("Refreshed files")

    @periodic(registry_attr_name="file_check_config")
    async def check_files(self, **kwargs):
        if self.file_browser.checking_files and self.mode == Mode.BROWSE:
            base_dir = self.set_base_dir_box.get()
            if base_dir and base_dir != "":
                self.refresh(show_new_images=self.slideshow_config.show_new_images)

    @periodic(registry_attr_name="slideshow_config")
    async def do_slideshow(self, **kwargs):
        if self.slideshow_config.slideshow_running:
            if config.debug:
                Utils.log_debug("Slideshow next image")
            base_dir = self.set_base_dir_box.get()
            if base_dir and base_dir != "":
                self.show_next_media()

    def toggle_slideshow(self, event=None):
        self.slideshow_config.toggle_slideshow()
        if self.slideshow_config.show_new_images:
            message = _("Slideshow for new images started")
        elif self.slideshow_config.slideshow_running:
            message = _("Slideshow started")
            start_thread(self.do_slideshow)
        else:
            message = _("Slideshows ended")
        self.toast(message)

    def return_to_browsing_mode(self, event=None, suppress_toast=False):
        # TODO instead of simply returning, make this method toggle between browsing mode and the last compare mode if a compare has been run
        self.set_mode(Mode.BROWSE)
        self.file_browser.refresh()
        self._set_label_state()
        assert self.img_path is not None
        if not self.go_to_file(None, self.img_path, retry_with_delay=1):
            self.home()
        self.store_info_cache()
        if not suppress_toast:
            self.toast(_("Browsing mode set."))

    def get_other_window_or_self_dir(self, allow_current_window=False, prefer_compare_window=False):
        if prefer_compare_window:
            window = App.find_window_with_compare()
            if window is not None:
                return window, [window.base_dir]
        if RecentDirectoryWindow.last_comparison_directory is not None \
                and os.path.isdir(RecentDirectoryWindow.last_comparison_directory):
            window = App.get_window(base_dir=RecentDirectoryWindow.last_comparison_directory)
            if window is not None:
                return window, [window.base_dir]
            else:
                RecentDirectoryWindow.last_comparison_directory = None
        if len(App.secondary_top_levels) == 0:
            return self, [self.base_dir]  # should be main window in this case
        window = None
        other_dirs = []
        for _app in App.open_windows:
            if _app is not None and (allow_current_window or _app.window_id != self.window_id) and os.path.isdir(_app.base_dir):
                window = _app
                other_dirs.append(_app.base_dir)
        if len(other_dirs) == 1:
            return window, other_dirs
        return None, other_dirs

    def get_media_details(self, event=None, media_path=None, manually_keyed=True):
        preset_image_path = True
        if media_path is None:
            media_path = self.img_path
            preset_image_path = False
        if media_path is None or media_path == "":
            return
        if preset_image_path:
            index_text = _("(Open this image as part of a directory to see index details.)")
        elif self.mode == Mode.BROWSE:
            index_text = self.file_browser.get_index_details()
        else:
            _index = self.compare_wrapper.match_index + 1
            len_files_matched = len(self.compare_wrapper.files_matched)
            if self.mode == Mode.GROUP:
                len_file_groups = len(self.compare_wrapper.file_groups)
                group_index = self.compare_wrapper.current_group_index + 1
                index_text = f"{_index} of {len_files_matched} (Group {group_index} of {len_file_groups})"
            elif self.mode == Mode.SEARCH and self.is_toggled_view_matches:
                index_text = f"{_index} of {len_files_matched} ({self.file_browser.get_index_details()})"
            else:
                index_text = ""  # shouldn't happen
        if self.app_actions.image_details_window() is not None:
            if self.app_actions.image_details_window().do_refresh:
                self.app_actions.image_details_window().update_image_details(media_path, index_text)
            if manually_keyed:
                self.app_actions.image_details_window().focus()
        else:
            top_level = Toplevel(self.master, bg=AppStyle.BG_COLOR)
            try:
                image_details_window = ImageDetails(self.master, top_level, media_path, index_text,
                                                    self.app_actions, do_refresh=not preset_image_path)
                self.app_actions.set_image_details_window(image_details_window)
            except Exception as e:
                self.handle_error(str(e), title="Image Details Error")

    def show_related_image(self, event=None):
        ImageDetails.show_related_image(master=self.master, image_path=self.img_path, app_actions=self.app_actions)

    def check_many_files(self, window, action="do this action", threshold=2000):
        if not window.file_browser.has_confirmed_dir() and window.file_browser.is_slow_total_files(threshold=threshold):
            res = self.alert(_("Many Files"), f"There are a lot of files in {window.base_dir} and it may take a while"  # TODO i18n
                             + f" to {action}.\n\nWould you like to proceed?", kind="askokcancel")
            not_ok = res != messagebox.OK and res != True
            if not_ok:
                return True
            window.file_browser.set_dir_confirmed()
        return False

    def find_related_images_in_open_window(self, event=None, base_dir=None):
        if base_dir is None:
            window, dirs = self.get_other_window_or_self_dir()
            if window is None:
                self.open_recent_directory_window(extra_callback_args=(
                    self.find_related_images_in_open_window, dirs))
                return
            base_dir = dirs[0]
        else:
            window = App.get_window(base_dir=base_dir)
        image_to_use = self.img_path if len(MarkedFiles.file_marks) != 1 else MarkedFiles.file_marks[0]
        if self.check_many_files(window, action="find related images"):
            return
        next_related_image = ImageDetails.next_downstream_related_image(image_to_use, base_dir, self.app_actions)
        if next_related_image is not None:
            window.go_to_file(search_text=next_related_image)
            window.media_canvas.focus()
        else:
            self.toast(_("No downstream related image(s) found in {0}").format(base_dir))

    def set_marks_from_downstream_related_images(self, event=None, base_dir=None, image_to_use=None):
        # TODO some way to tell if the current mark is invalid based on whether the window has been switched, and if so clear it and use the current image instead
        if base_dir is None:
            window, dirs = self.get_other_window_or_self_dir(allow_current_window=True)
            if window is None:
                self.open_recent_directory_window(extra_callback_args=(
                    self.set_marks_from_downstream_related_images, dirs))
                return
            base_dir = dirs[0]
        else:
            window = App.get_window(base_dir=base_dir)
        if image_to_use is None:
            image_to_use = self.img_path if len(MarkedFiles.file_marks) != 1 else MarkedFiles.file_marks[0]
        if self.check_many_files(window, action="find related images"):
            return
        downstream_related_images = ImageDetails.get_downstream_related_images(
            image_to_use, base_dir, self.app_actions, force_refresh=True)
        if downstream_related_images is not None:
            MarkedFiles.file_marks = downstream_related_images
            self.toast(_("{0} file marks set").format(len(downstream_related_images)))
            window.go_to_mark()
            window.media_canvas.focus()

    def get_help_and_config(self, event=None):
        top_level = Toplevel(self.master, bg=AppStyle.BG_COLOR)
        top_level.title(_("Help and Config"))
        top_level.geometry("900x600")
        try:
            help_and_config = HelpAndConfig(top_level)
        except Exception as e:
            self.alert("Image Details Error", str(e), kind="error")

    def set_file_paths(self):
        self.file_browser.refresh()
        self._set_label_state()
        tries = 0
        while tries < 10:
            tries += 1
            try:
                if self.show_next_media():
                    return
            except Exception:
                pass

    def set_base_dir(self, base_dir_from_dir_window=None) -> None:
        '''
        Change the base directory to the value provided in the UI.
        '''
        self.store_info_cache()
        base_dir = self.set_base_dir_box.get()
#        print(f"Got base dir: {base_dir}")
        if base_dir_from_dir_window is not None:
            self.base_dir = base_dir_from_dir_window  # assume this directory is valid
        elif (base_dir == "" or base_dir == "Add dirpath..." or self.base_dir == base_dir) and len(RecentDirectories.directories) == 0:
            base_dir = filedialog.askdirectory(
                initialdir=self.get_base_dir(), title="Set image comparison directory")
            self.base_dir = Utils.get_valid_file(self.base_dir, base_dir)
            if self.base_dir is None:
                raise Exception("Failed to set image comparison directory")
            RecentDirectories.directories.append(self.base_dir)
        else:
            self.open_recent_directory_window()
            return
        if self.compare_wrapper.has_compare() and self.base_dir != self.compare_wrapper.compare().base_dir:
            self.compare_wrapper._compare = None
            self._set_label_state(group_number=None, size=0)
            self._remove_all_mode_buttons()
#        print(f"Setting base dir to {self.base_dir} on window ID {self.window_id} in self.set_base_dir")
        self.set_base_dir_box.delete(0, "end")
        self.set_base_dir_box.insert(0, self.base_dir)
        self.file_browser.set_directory(self.base_dir)
        # Update settings to those last set for this directory, if found
        recursive = app_info_cache.get(self.base_dir, "recursive", default_val=False)
        sort_by = app_info_cache.get(self.base_dir, "sort_by", default_val=self.sort_by.get())
        compare_mode = app_info_cache.get(self.base_dir, "compare_mode", default_val=self.compare_wrapper.compare_mode.get_text())
        if recursive != self.image_browse_recurse_var.get():
            self.image_browse_recurse_var.set(recursive)
            self.file_browser.set_recursive(recursive)
        try:
            if compare_mode != self.compare_wrapper.compare_mode.get_text():
                self.compare_mode_var.set(compare_mode)
                self.compare_wrapper.compare_mode = CompareMode.get(compare_mode)
        except Exception as e:
            Utils.log_red("Error setting stored compare mode: " + str(e))
        try:
            if sort_by != self.sort_by.get():
                self.sort_by.set(sort_by)
                self.file_browser.set_sort_by(SortBy.get(sort_by))
        except Exception as e:
            Utils.log_red("Error setting stored sort by: " + str(e))
        if not self.compare_wrapper.has_compare():
            self.set_mode(Mode.BROWSE)
            previous_file = app_info_cache.get(self.base_dir, "image_cursor")
            if previous_file and previous_file != "":
                if not self.go_to_file(None, previous_file, retry_with_delay=1):
                    self.show_next_media()
            else:
                self.show_next_media()
            self._set_label_state()
        relative_dirpath = Utils.get_relative_dirpath(self.base_dir, levels=2)
        self.master.title(_(" Simple Image Compare ") + "- " + relative_dirpath)
        self.master.update()

    def open_recent_directory_window(self, event=None, open_gui=True, run_compare_image=None, extra_callback_args=None):
        top_level = Toplevel(self.master, bg=AppStyle.BG_COLOR)
        top_level.title(_("Set Image Comparison Directory"))
        top_level.geometry(RecentDirectoryWindow.get_geometry(is_gui=open_gui))
        if not open_gui:
            top_level.attributes('-alpha', 0.3)
        try:
            recent_directory_window = RecentDirectoryWindow(
                top_level, self.master, open_gui, self.app_actions, base_dir=self.get_base_dir(),
                run_compare_image=run_compare_image, extra_callback_args=extra_callback_args)
        except Exception as e:
            self.handle_error(str(e), title="Recent Directory Window Error")

    def get_base_dir(self) -> str:
        return "." if (self.base_dir is None or self.base_dir == "") else self.base_dir

    def get_search_dir(self) -> str:
        return self.get_base_dir() if self.search_dir is None else self.search_dir

    def get_search_file_path(self) -> str | None:
        '''
        Get the search file path provided in the UI.
        '''
        image_path = self.search_image.get().strip()
        if image_path is None or image_path == "":
            self.compare_wrapper.search_image_full_path = None
            return None
        search_file = Utils.get_valid_file(self.get_base_dir(), image_path)
        if search_file is None:
            search_file = Utils.get_valid_file(self.get_search_dir(), image_path)
            if search_file is None:
                self.handle_error("Search file is not a valid file for base dir.", title="Invalid search file")
                raise AssertionError("Search file is not a valid file.")
        return search_file

    def get_counter_limit(self) -> int | None:
        counter_limit_str = self.set_counter_limit.get().strip()
        try:
            return None if counter_limit_str == "" else int(counter_limit_str)
        except Exception:
            self.handle_error(_("Counter limit must be an integer value."), title=_("Invalid Setting"))
            raise AssertionError("Counter limit must be an integer value.")

    def get_compare_threshold(self):
        compare_threshold_str = self.compare_threshold.get().strip()
        return int(compare_threshold_str) if self.compare_wrapper.compare_mode == CompareMode.COLOR_MATCHING else float(compare_threshold_str)

    def get_inclusion_pattern(self) -> str | None:
        inclusion_pattern = self.inclusion_pattern.get().strip()
        return None if inclusion_pattern.strip() == "" else inclusion_pattern

    def set_search_for_image(self, event=None) -> None:
        image_path = self.get_search_file_path()
        if image_path is None or image_path == "":
            if self.img_path is None:
                self.handle_error(_("No image selected."), title=_("Invalid Setting"))
            self.search_img_path_box.delete(0, END)
            self.search_img_path_box.insert(0, str(self.img_path))
        self.set_search()

    def set_search_for_text(self, event=None):
        search_text = self.search_text.get()
        search_text_negative = self.search_text_negative.get()
        if search_text.strip() == "" and search_text_negative.strip() == "":
            self.search_text.set("cat")
        self.set_search()

    def set_search(self, event=None) -> None:
        '''
        Set the search image or text using the provided UI values, or prompt the
        user for selection. Set the mode based on the result.
        '''
        args = CompareArgs()
        image_path = self.get_search_file_path()
        search_text = self.search_text.get()
        search_text_negative = self.search_text_negative.get()
        if search_text.strip() == "":
            search_text = None
        if search_text_negative.strip() == "":
            search_text_negative = None
        args.search_text = search_text

        # TODO eventually will need a separate box for the negative search file
        # path so that it is not exclusive with negative search file text
        if search_text_negative and os.path.isfile(search_text_negative.strip()):
            args.negative_search_file_path = search_text_negative.strip()
            args.search_text_negative = None
        else:
            args.search_text_negative = search_text_negative
            args.negative_search_file_path = None

        if args.search_text is not None or args.search_text_negative is not None:
            self.compare_wrapper.validate_compare_mode(CompareMode.embedding_modes(), _(
                "Compare mode must be set to an embedding mode to search text embeddings"))

        if image_path is not None and not os.path.isfile(image_path):
            image_path = filedialog.askopenfilename(
                initialdir=self.get_search_dir(), title=_("Select image file"),
                filetypes=[("Image files", "*.jpg *.jpeg *.png *.tiff *.gif")])

        if image_path is not None and image_path.strip() != "":
            if image_path.startswith(self.get_base_dir()):
                self.search_image.set(os.path.basename(image_path))
            self.search_dir = os.path.dirname(image_path)
            args.search_file_path = image_path
            self.compare_wrapper.search_image_full_path = image_path
            self.show_searched_image()

        if args.not_searching():
            if self.mode != Mode.BROWSE:
                self.set_mode(Mode.GROUP)
        else:
            self.set_mode(Mode.SEARCH)

        self.master.update()
        self.master.focus()
        self.run_compare(compare_args=args)

    def show_searched_image(self) -> None:
        if config.debug:
            Utils.log_debug(f"Search image full path: {self.compare_wrapper.search_image_full_path}")
        if self.compare_wrapper.search_image_full_path is not None and self.compare_wrapper.search_image_full_path.strip() != "":
            if os.path.isfile(self.compare_wrapper.search_image_full_path):
                self.create_image(self.compare_wrapper.search_image_full_path, extra_text="(search image)")
            else:
                Utils.log_yellow(self.compare_wrapper.search_image_full_path)
                self.handle_error(_("Somehow, the search file is invalid"))

    def show_prev_media(self, event=None, show_alert=True) -> bool:
        '''
        If similar image results are present in any mode, display the previous
        in the list of matches.
        '''
        self.direction = Direction.BACKWARD
        if self.mode == Mode.BROWSE:
            start_file = self.file_browser.current_file()
            previous_file = self.file_browser.previous_file()
            if self.img_path == previous_file:
                return True  # NOTE self.refresh() is calling this method in this case
            while self.compare_wrapper.skip_image(previous_file) and previous_file != start_file:
                previous_file = self.file_browser.previous_file()
            self.master.update()
            try:
                self.create_image(previous_file)
                return True
            except Exception as e:
                self.handle_error(str(e), title="Exception")
                return False
        return self.compare_wrapper.show_prev_media(show_alert=show_alert)

    def show_next_media(self, event=None, show_alert=True) -> bool:
        '''
        If similar image results are present in any mode, display the next
        in the list of matches.
        '''
        self.direction = Direction.FORWARD
        if self.mode == Mode.BROWSE:
            start_file = self.file_browser.current_file()
            next_file = self.file_browser.next_file()
            if self.img_path == next_file:
                return True  # NOTE self.refresh() is calling this method in this case
            while self.compare_wrapper.skip_image(next_file) and next_file != start_file:
                next_file = self.file_browser.next_file()
            self.master.update()
            try:
                self.create_image(next_file)
                return True
            except Exception as e:
                traceback.print_exc()
                self.handle_error(str(e), title="Exception")
                return False
        return self.compare_wrapper.show_next_media(show_alert=show_alert)

    def last_chosen_direction_func(self):
        """
        This will be next or previous based on the user's last chosen direction.
        """
        if self.direction == Direction.BACKWARD:
            self.show_prev_media()
        elif self.direction == Direction.FORWARD:
            self.show_next_media()
        else:
            raise Exception(f"Direction was improperly set. Direction was {self.direction}")

    def set_current_image_run_search(self, event=None, base_dir=None) -> None:
        '''
        Execute a new image search from the provided search image.
        '''
        if base_dir is None:
            window, dirs = self.get_other_window_or_self_dir(
                allow_current_window=True, prefer_compare_window=True)
            if window is None:
                self.open_recent_directory_window(extra_callback_args=(
                    self.set_current_image_run_search, dirs))
                return
            base_dir = dirs[0]
        else:
            window = App.get_window(base_dir=base_dir)
        if self.mode == Mode.BROWSE:
            if Utils.modifier_key_pressed(event, keys_to_check=[ModifierKey.ALT]):
                random_image = self.file_browser.random_file()
                counter = 0
                while random_image in self.compare_wrapper.hidden_images and counter < 50:
                    random_image = self.file_browser.random_file()
                    counter += 1
                if os.path.isfile(random_image):
                    self.create_image(random_image)  # sets current image first
        filepath = self.get_active_media_filepath()
        if filepath:
            window._set_image_run_search(filepath)
        else:
            self.handle_error(_("Failed to get active image filepath"))

    def _set_image_run_search(self, filepath):
        base_dir = self.get_base_dir()
        if filepath.startswith(base_dir):
            filepath = filepath[len(base_dir)+1:]
        self.search_image.set(filepath)
        self.set_search()

    def add_current_image_to_negative_search(self, event=None, base_dir=None):
        filepath = self.get_active_media_filepath()
        if filepath:
            if base_dir is None:
                window, dirs = self.get_other_window_or_self_dir(
                    allow_current_window=True, prefer_compare_window=True)
                if window is None:
                    self.open_recent_directory_window(extra_callback_args=(
                        self.add_current_image_to_negative_search, dirs))
                    return
                base_dir = dirs[0]
            else:
                window = App.get_window(base_dir=base_dir)
            window.negative_image_search(filepath)
        else:
            self.handle_error(_("Failed to get active image filepath"))

    def negative_image_search(self, filepath):
        args = self.compare_wrapper.get_args()
        args.negative_search_file_path = filepath
        self.search_text_negative_box.delete(0, "end")
        self.search_text_negative_box.insert(0, filepath)
        self.set_search()

    def create_image(self, image_path, extra_text=None) -> None:
        '''
        Show an image in the main content pane of the UI.
        '''
        self.media_canvas.show_image(image_path)
        if self.label_current_image_name is None:
            self.label_current_image_name = Label(self.sidebar)
            self.add_label(self.label_current_image_name, "", pady=30)
        self.label_current_image_name.config(bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
        relative_filepath, basename = Utils.get_relative_dirpath_split(self.base_dir, image_path)
        self.prev_img_path = self.img_path
        self.img_path = image_path
        text = basename if relative_filepath == "" else relative_filepath + "\n" + basename
        text = Utils._wrap_text_to_fit_length(text, 30)
        if extra_text is not None:
            text += "\n" + extra_text
        self.label_current_image_name["text"] = text
        if self.app_actions.image_details_window() is not None:
            self.get_media_details(manually_keyed=False)
    
    def clear_image(self):
        self.media_canvas.clear()
        self.destroy_grid_element("label_current_image_name")
        self.label_current_image_name = None

    def toggle_image_view(self) -> None:
        '''
        While in search mode, toggle between the search image and the results.
        '''
        if self.mode != Mode.SEARCH:
            return

        if self.is_toggled_view_matches:
            self.show_searched_image()
        else:
            self.create_image(self.compare_wrapper.current_match())

        self.is_toggled_view_matches = not self.is_toggled_view_matches

    def _remove_all_mode_buttons(self) -> None:
        self.destroy_grid_element("prev_group_btn")
        self.destroy_grid_element("next_group_btn")
        # self.destroy_grid_element("search_current_image_btn")
        # self.destroy_grid_element("open_image_location_btn")
        # self.destroy_grid_element("copy_image_path")
        # self.destroy_grid_element("delete_image_btn")
        for mode in self.has_added_buttons_for_mode.keys():
            self.has_added_buttons_for_mode[mode] = False
        self.master.update()

    def _add_buttons_for_mode(self) -> None:
        if not self.has_added_buttons_for_mode[self.mode]:
            if self.mode == Mode.SEARCH:
                if self.compare_wrapper.search_image_full_path != None \
                        and self.compare_wrapper.search_image_full_path.strip() != "" \
                        and self.toggle_image_view_btn is None:
                    self.add_button("toggle_image_view_btn", "Toggle image view", self.toggle_image_view)
                    self.add_button("replace_current_image_btn", "Replace with search image",
                                    self.replace_current_image_with_search_image)
#                if not self.has_added_buttons_for_mode[Mode.GROUP]:
#                    self.add_all_mode_buttons()
            elif self.mode == Mode.GROUP:
                self.add_button("prev_group_btn", "Previous group", self.compare_wrapper.show_prev_group)
                self.add_button("next_group_btn", "Next group", self.compare_wrapper.show_next_group)
#                if not self.has_added_buttons_for_mode[Mode.SEARCH]:
#                    self.add_all_mode_buttons()
            elif self.mode == Mode.DUPLICATES:
                pass

            self.has_added_buttons_for_mode[self.mode] = True

    def display_progress(self, context, percent_complete):
        self._set_label_state(Utils._wrap_text_to_fit_length(
                _("{0}: {1}% complete").format(context, int(percent_complete)), 30))
        self.master.update()

    def _validate_run(self):
        base_dir_selected = self.set_base_dir_box.get()
        if not base_dir_selected or base_dir_selected == "":
            res = self.alert(_("Confirm comparison"),
                             _("No base directory has been set, will use current base directory of ")
                             + f"{self.base_dir}\n\n" + _("Are you sure you want to proceed?"),
                             kind="askokcancel")
            return res == messagebox.OK or res == True
        return True

    def run_compare(self, compare_args=CompareArgs(), find_duplicates=False) -> None:
        if not self._validate_run():
            return
        compare_args.find_duplicates = find_duplicates
        self._run_with_progress(self._run_compare, args=[compare_args])

    def _run_with_progress(self, exec_func, args=[]) -> None:
        def run_with_progress_async(self) -> None:
            self.progress_bar = Progressbar(self.sidebar, orient=HORIZONTAL, length=100, mode='indeterminate')
            self.apply_to_grid(self.progress_bar)
            self.progress_bar.start()
            try:
                exec_func(*args)
            except Exception as e:
                traceback.print_exc()
                self.alert(_("Error running compare"), str(e), kind="error")
            self.progress_bar.stop()
            self.progress_bar.grid_forget()
            self.destroy_grid_element("progress_bar")

        start_thread(run_with_progress_async, use_asyncio=False, args=[self])

    def _run_compare(self, args=CompareArgs()) -> None:
        '''
        Execute operations on the Compare object in any mode. Create a new Compare object if needed.
        '''
        args.base_dir = self.get_base_dir()
        args.mode = self.mode
        args.recursive = self.file_browser.recursive
        args.counter_limit = self.get_counter_limit()
        args.compare_faces = self.compare_faces.get()
        args.overwrite = self.overwrite.get()
        args.threshold = self.get_compare_threshold()
        args.inclusion_pattern = self.get_inclusion_pattern()
        args.store_checkpoints = self.store_checkpoints.get()
        args.include_videos = config.enable_videos
        args.include_gifs = config.enable_gifs
        args.include_pdfs = config.enable_pdfs
        args.use_matrix_comparison = False # TODO enable UI option for this
        args.listener = ProgressListener(update_func=self.display_progress)
        self.compare_wrapper.run(args)

    def _set_toggled_view_matches(self):
        self.is_toggled_view_matches = True

    def add_or_remove_mark_for_current_image(self, event=None, show_toast=True):
        if self.delete_lock:
            warning = _("DELETE_LOCK_MARK_STOP")
            self.toast(warning)
            raise Exception(warning)
            # NOTE Have to raise exception to in some cases prevent downstream events from happening with no marks
        self._check_marks(min_mark_size=0)
        if self.img_path in MarkedFiles.file_marks:
            MarkedFiles.file_marks.remove(self.img_path)
            remaining_marks_count = len(MarkedFiles.file_marks)
            if MarkedFiles.mark_cursor >= remaining_marks_count:
                MarkedFiles.mark_cursor = -1
            if show_toast:
                self.toast(_("Mark removed. Remaining: {0}").format(remaining_marks_count))
        else:
            MarkedFiles.file_marks.append(self.img_path)
            if show_toast:
                self.toast(_("Mark added. Total set: {0}").format(len(MarkedFiles.file_marks)))

    def _add_all_marks_from_last_or_current_group(self, event=None):
        if self.mode == Mode.BROWSE:
            if self.img_path in MarkedFiles.file_marks:
                return
            self._check_marks()
            files = self.file_browser.select_series(start_file=MarkedFiles.file_marks[-1], end_file=self.img_path)
        else:
            if Utils.modifier_key_pressed(event, keys_to_check=[ModifierKey.ALT]):
                # Select all file matches
                files = list(self.compare_wrapper.files_matched)
            else:
                files = self.compare_wrapper.select_series(start_file=MarkedFiles.file_marks[-1], end_file=self.img_path)
        for _file in files:
            if _file not in MarkedFiles.file_marks:
                MarkedFiles.file_marks.append(_file)
        self.toast(_("Marks added. Total set: {0}").format(len(MarkedFiles.file_marks)))

    def go_to_mark(self, event=None):
        self._check_marks()
        alt_key_pressed = Utils.modifier_key_pressed(event, keys_to_check=[ModifierKey.ALT])
        MarkedFiles.mark_cursor += -1 if alt_key_pressed else 1
        if MarkedFiles.mark_cursor >= len(MarkedFiles.file_marks):
            MarkedFiles.mark_cursor = 0
            if len(MarkedFiles.file_marks) > 1:
                self.toast(_("First sorted mark"))
        marked_file = MarkedFiles.file_marks[MarkedFiles.mark_cursor]
        if self.mode == Mode.BROWSE:
            self.file_browser.go_to_file(marked_file)
            self.create_image(marked_file)
            self.master.update()
            if len(MarkedFiles.file_marks) == 1:
                self.toast(_("Only one marked file set."))
        else:
            self.go_to_file(search_text=os.path.basename(marked_file), exact_match=True)

    def copy_marks_list(self, event=None):
        self.master.clipboard_clear()
        self.master.clipboard_append(MarkedFiles.file_marks)

    def open_move_marks_window(self, event=None, open_gui=True, override_marks=[]):
        self._check_marks(min_mark_size=0)
        if len(override_marks) > 0:
            Utils.log(_("Including marks: {0}").format(override_marks))
            MarkedFiles.file_marks.extend(override_marks)
        current_image = self.get_active_media_filepath()
        single_image = False
        if len(MarkedFiles.file_marks) == 0:
            self.add_or_remove_mark_for_current_image()
            single_image = True
        top_level = Toplevel(self.master, bg=AppStyle.BG_COLOR)
        top_level.title(_("Move {0} Marked File(s)").format(len(MarkedFiles.file_marks)))
        top_level.geometry(MarkedFiles.get_geometry(is_gui=open_gui))
        if not open_gui:
            top_level.attributes('-alpha', 0.3)
        try:
            marked_file_mover = MarkedFiles(top_level, open_gui, single_image, current_image, self.mode,
                                            self.app_actions, base_dir=self.get_base_dir())
        except Exception as e:
            self.handle_error(str(e), title="Marked Files Window Error")

    def run_previous_marks_action(self, event=None):
        if len(MarkedFiles.file_marks) == 0:
            self.add_or_remove_mark_for_current_image(show_toast=False)
        MarkedFiles.run_previous_action(self.app_actions, self.get_active_media_filepath())

    def run_penultimate_marks_action(self, event=None):
        if len(MarkedFiles.file_marks) == 0:
            self.add_or_remove_mark_for_current_image(show_toast=False)
        MarkedFiles.run_penultimate_action(self.app_actions, self.get_active_media_filepath())

    def run_permanent_marks_action(self, event=None):
        if len(MarkedFiles.file_marks) == 0:
            self.add_or_remove_mark_for_current_image(show_toast=False)
        MarkedFiles.run_permanent_action(self.app_actions, self.get_active_media_filepath())

    def run_hotkey_marks_action(self, event=None):
        assert event is not None
        shift_key_pressed = Utils.modifier_key_pressed(event, keys_to_check=[ModifierKey.SHIFT])
        if len(MarkedFiles.file_marks) == 0:
            self.add_or_remove_mark_for_current_image(show_toast=False)
        number = int(event.keysym)
        MarkedFiles.run_hotkey_action(self.app_actions, self.get_active_media_filepath(), number, bool(shift_key_pressed))

    def _check_marks(self, min_mark_size=1):
        if len(MarkedFiles.file_marks) < min_mark_size:
            exception_text = _("NO_MARKS_SET").format(len(MarkedFiles.file_marks), min_mark_size)
            self.toast(exception_text)
            raise Exception(exception_text)

    def revert_last_marks_change(self, event=None):
        if not config.use_file_paths_json:
            MarkedFiles.undo_move_marks(self.get_base_dir(), self.app_actions)

    def open_file_actions_window(self, event=None):
        try:
            file_actions_window = FileActionsWindow(self.master, self.app_actions,
                                                    ImageDetails.open_temp_image_canvas,
                                                    MarkedFiles.move_marks_to_dir_static)
        except Exception as e:
            self.handle_error(str(e), title="File Actions Window Error")

    def open_prevalidations_window(self, event=None):
        if config.enable_prevalidations:
            try:
                prevalidation_window = PrevalidationsWindow(self.master, self.app_actions)
            except Exception as e:
                self.handle_error(str(e), title="Prevalidations Window Error")

    def run_prevalidations_for_base_dir(self, event=None):
        PrevalidationsWindow.prevalidated_cache.clear()
        for image_path in self.file_browser.get_files():
            try:
                prevalidation_action = PrevalidationsWindow.prevalidate(image_path, self.get_base_dir, self.hide_current_media, self.toast)
            except Exception as e:
                print(e)

    def toggle_prevalidations(self, event=None):
        config.enable_prevalidations = not config.enable_prevalidations
        self.toast(_("Prevalidations now running") if config.enable_prevalidations else _("Prevalidations turned off"))

    def open_type_configuration_window(self, event=None):
        TypeConfigurationWindow.show(master=self.master, app_actions=self.app_actions)

    def open_go_to_file_window(self, event=None):
        try:
            go_to_file = GoToFile(self.master, self.app_actions)
        except Exception as e:
            self.handle_error(str(e), title="Go To File Window Error")

    def go_to_file(self, event=None, search_text="", retry_with_delay=0, exact_match=False):
        # TODO if file is not in current directory, search in another window.
        # If it is not in any open window but is a valid filepath, open a new
        # window with that file's directory and go to the file in the new window.
        if self.mode == Mode.BROWSE:
            image_path = self.file_browser.find(
                search_text=search_text, retry_with_delay=retry_with_delay, exact_match=exact_match)
        else:
            image_path, group_indexes = self.compare_wrapper.find_file_after_comparison(search_text, exact_match=exact_match)
            if group_indexes:
                self.compare_wrapper.current_group_index = group_indexes[0]
                self.compare_wrapper.set_current_group(start_match_index=group_indexes[1])
                return True
        if not image_path:
            self.alert(_("File not found"), _("No file was found for the search text: \"{0}\"").format(search_text))
            return False
        self.create_image(image_path)
        self.master.update()
        return True

    def go_to_previous_image(self, event=None):
        if self.prev_img_path is not None:
            self.go_to_file(event=event, search_text=self.prev_img_path, exact_match=True)

    def open_secondary_compare_window(self, event=None, run_compare_image=None):
        if run_compare_image is None:
            self.open_recent_directory_window(run_compare_image="")
        elif not os.path.isfile(run_compare_image):
            self.alert(_("No image selected"), _("No image was selected for comparison"))
        else:
            # TODO enable this function to target already open windows with existing compares if available
            self.open_recent_directory_window(run_compare_image=self.img_path)

    def next_text_embedding_preset(self, event=None):
        # TODO enable this function to also accept a directory, and if this is
        # the case find the next file in the directory and search that against
        # the current base directory. This way typing in the name of the file
        # or selecting it is avoided. Probably want to use another file_browser
        # object to accomplish this.
        next_text_embedding_search_preset = config.next_text_embedding_search_preset()
        if next_text_embedding_search_preset is None:
            self.alert(_("No Text Search Presets Found"), _(
                "No text embedding search presets found. Set them in the config.json file."))
        else:
            self.search_image.set("")
            self.search_text_box.delete(0, "end")
            self.search_text_negative_box.delete(0, "end")

            if isinstance(next_text_embedding_search_preset, dict):
                if "negative" in next_text_embedding_search_preset:
                    self.search_text_negative_box.insert(0, next_text_embedding_search_preset["negative"])
                if "positive" in next_text_embedding_search_preset:
                    self.search_text_box.insert(0, next_text_embedding_search_preset["positive"])
            elif isinstance(next_text_embedding_search_preset, str):
                self.search_text_box.insert(0, next_text_embedding_search_preset)

            self.master.update()
            self.set_search()

    def cycle_windows(self, event=None):
        if App.window_index >= len(App.open_windows):
            App.window_index = 0
        window = App.open_windows[App.window_index]
        if window.window_id == self.window_id:
            App.window_index += 1
        if App.window_index >= len(App.open_windows):
            App.window_index = 0
        window.media_canvas.focus()
        App.window_index += 1

    def home(self, event=None, last_file=False):
        if self.mode == Mode.BROWSE:
            self.file_browser.refresh()
            current_file = self.get_active_media_filepath()
            if current_file is None:
                raise Exception("No active image file.")
            if last_file:
                last_image = self.file_browser.last_file()
                while self.compare_wrapper.skip_image(last_image) and last_image != current_file:
                    last_image = self.file_browser.previous_file()
                self.create_image(self.file_browser.last_file())
                if len(MarkedFiles.file_marks) == 1 and self.file_browser.has_file(MarkedFiles.file_marks[0]):
                    self._add_all_marks_from_last_or_current_group()
                self.direction = Direction.BACKWARD
            elif Utils.modifier_key_pressed(event, keys_to_check=[ModifierKey.SHIFT]):
                self.home(last_file=not last_file)
                return
            else:
                first_image = self.file_browser.next_file()
                while self.compare_wrapper.skip_image(first_image) and first_image != current_file:
                    first_image = self.file_browser.next_file()
                self.create_image(first_image)
            self.master.update()
        elif self.compare_wrapper.has_compare():
            self.direction = Direction.FORWARD
            # TODO map last_file logic for compare case
            self.compare_wrapper.current_group_index = 0
            self.compare_wrapper.match_index = 0
            self.compare_wrapper.set_current_group()

    def page_up(self, event=None):
        shift_key_pressed = Utils.modifier_key_pressed(event, keys_to_check=[ModifierKey.SHIFT])
        current_image = self.get_active_media_filepath()
        prev_file = self.file_browser.page_up(half_length=shift_key_pressed) if self.mode == Mode.BROWSE else self.compare_wrapper.page_up(half_length=shift_key_pressed)
        while self.compare_wrapper.skip_image(prev_file) and prev_file != current_image:
            prev_file = self.file_browser.previous_file() if self.mode == Mode.BROWSE else self.compare_wrapper._get_prev_image()
        self.create_image(prev_file)
        self.master.update()
        self.direction = Direction.BACKWARD

    def page_down(self, event=None):
        shift_key_pressed = Utils.modifier_key_pressed(event, keys_to_check=[ModifierKey.SHIFT])
        current_image = self.get_active_media_filepath()
        next_file = self.file_browser.page_down(half_length=shift_key_pressed) if self.mode == Mode.BROWSE else self.compare_wrapper.page_down(half_length=shift_key_pressed)
        while self.compare_wrapper.skip_image(next_file) and next_file != current_image:
            next_file = self.file_browser.next_file() if self.mode == Mode.BROWSE else self.compare_wrapper._get_next_image()
        self.create_image(next_file)
        self.master.update()
        self.direction = Direction.FORWARD

    def is_toggled_search_image(self):
        return self.mode == Mode.SEARCH and not self.is_toggled_view_matches

    def get_active_media_filepath(self):
        if self.media_canvas.canvas.imagetk is None:
            return None
        if self.mode == Mode.BROWSE:
            return self.file_browser.current_file()
        if self.is_toggled_search_image():
            filepath = self.compare_wrapper.search_image_full_path
        else:
            filepath = self.compare_wrapper.current_match()
        return Utils.get_valid_file(self.get_base_dir(), filepath)

    def open_image_location(self, event=None):
        filepath = self.get_active_media_filepath()

        if filepath is not None:
            self.toast("Opening file location: " + filepath)
            Utils.open_file_location(filepath)
        else:
            self.handle_error(_("Failed to open location of current file, unable to get valid filepath"))

    def open_image_in_gimp(self, event=None):
        if self.delete_lock:
            filepath = self.prev_img_path
        else:
            filepath = self.get_active_media_filepath()
        if filepath is not None:
            self.toast("Opening file in GIMP: " + filepath)
            Utils.open_file_in_gimp(filepath, config.gimp_exe_loc)
        else:
            self.handle_error(_("Failed to open current file in GIMP, unable to get valid filepath"))

    def copy_image_path(self):
        filepath = self.get_active_media_filepath()
        if sys.platform == 'win32':
            filepath = os.path.normpath(filepath)
            if config.escape_backslash_filepaths:
                filepath = filepath.replace("\\", "\\\\")
        self.master.clipboard_clear()
        self.master.clipboard_append(filepath)

    def hide_current_media(self, event=None, image_path=None):
        filepath = self.get_active_media_filepath() if image_path is None else image_path
        if filepath not in self.compare_wrapper.hidden_images:
            self.compare_wrapper.hidden_images.append(filepath)
        if image_path is None:
            self.toast(_("Hid current image.\nTo unhide, press Shift+B."))
        self.show_next_media()

    def clear_hidden_images(self, event=None):
        self.compare_wrapper.hidden_images.clear()
        self.toast(_("Cleared all hidden images."))

    def delete_image(self, event=None):
        '''
        Delete the currently displayed image from the filesystem.
        '''
        if self.delete_lock:
            self.toast(_("DELETE_LOCK"))
            return

        if self.mode == Mode.BROWSE:
            self.file_browser.checking_files = False
            filepath = self.file_browser.current_file()
            if filepath:
                self.media_canvas.release_media()
                self._handle_delete(filepath)
                MarkedFiles.handle_file_removal(filepath)
                self.file_browser.refresh(refresh_cursor=False, removed_files=[filepath], direction=self.direction)
                self.last_chosen_direction_func()
            self.file_browser.checking_files = True
            return

        is_toggle_search_image = self.is_toggled_search_image()

        if len(self.compare_wrapper.files_matched) == 0 and not is_toggle_search_image:
            self.toast(_("Invalid action, no files found to delete"))
            return
        elif is_toggle_search_image and (self.compare_wrapper.search_image_full_path is None or self.compare_wrapper.search_image_full_path == ""):
            self.toast(_("Invalid action, search image not found"))
            return

        filepath = self.get_active_media_filepath()

        if filepath is not None:
            MarkedFiles.handle_file_removal(filepath)
            if filepath == self.compare_wrapper.search_image_full_path:
                self.compare_wrapper.search_image_full_path = None
            self.media_canvas.release_media()
            self._handle_delete(filepath)
            if self.compare_wrapper._compare:
                self.compare_wrapper.compare().remove_from_groups([filepath])
            self.compare_wrapper._update_groups_for_removed_file(self.mode, self.compare_wrapper.current_group_index, self.compare_wrapper.match_index, show_next_media=self.direction)
        else:
            self.handle_error(_("Failed to delete current file, unable to get valid filepath"))

    def _handle_delete(self, filepath, toast=True, manual_delete=True):
        MarkedFiles.set_delete_lock()  # Undo deleting action is not supported
        if toast and manual_delete:
            self.toast(_("Removing file: {0}").format(filepath))
        else:
            Utils.log("Removing file: " + filepath)
        if config.delete_instantly:
            os.remove(filepath)
        elif config.trash_folder is not None:
            filepath = os.path.normpath(filepath)
            sep = "\\" if "\\" in filepath else "/"
            new_filepath = filepath[filepath.rfind(sep)+1:len(filepath)]
            new_filepath = os.path.normpath(os.path.join(config.trash_folder, new_filepath))
            os.rename(filepath, new_filepath)
        else:
            try:
                send2trash(os.path.normpath(filepath))
            except Exception as e:
                Utils.log_red(e)
                self.alert(_("Warning"),
                           _("Failed to send file to the trash, so it will be deleted. Either pip install send2trash or set a specific trash folder in config.json."))
                os.remove(filepath)

    def replace_current_image_with_search_image(self):
        '''
        Overwrite the file at the path of the current image with the
        search image.
        '''
        if (self.mode != Mode.SEARCH
                or len(self.compare_wrapper.files_matched) == 0
                or not os.path.exists(str(self.compare_wrapper.search_image_full_path))):
            return

        _filepath = self.compare_wrapper.current_match()
        filepath = Utils.get_valid_file(self.get_base_dir(), _filepath)

        if filepath is None:
            self.handle_error(_("Invalid target filepath for replacement: ") + _filepath)
            return

        os.rename(str(self.compare_wrapper.search_image_full_path), filepath)
        self.toast(_("Moved search image to ") + filepath)

    def _handle_remove_files_from_groups(self, files):
        '''
        Remove the files from the groups.
        '''
        # NOTE cannot use get_active_media_filepath here because file should have been removed by this point.
        current_image = self.compare_wrapper.current_match()
        for filepath in files:
            if filepath == self.compare_wrapper.search_image_full_path:
                self.compare_wrapper.search_image_full_path = None
            show_next_media = self.direction if current_image == filepath else None
            file_group_map = self.compare_wrapper._get_file_group_map(self.mode)
            try:
                group_indexes = file_group_map[filepath]
                self.compare_wrapper._update_groups_for_removed_file(self.mode,
                    group_indexes[0], group_indexes[1], set_group=False, show_next_media=show_next_media)
            except KeyError:
                pass  # The group may have been removed before update_groups_for_removed_file was called on the last file in it

    def trigger_image_generation(self, event=None):
        shift_key_pressed = event and Utils.modifier_key_pressed(event, keys_to_check=[ModifierKey.SHIFT])
        ImageDetails.run_image_generation_static(self.app_actions, modify_call=bool(shift_key_pressed))

    def run_image_generation(self, event=None, _type=None, image_path=None, modify_call=False):
        self.sd_runner_client.start()
        if image_path is None:
            if self.delete_lock:
                image_path = self.prev_img_path
            else:
                image_path = self.get_active_media_filepath()
        _type = ImageDetails.get_image_specific_generation_mode() if _type is None else _type
        try:
            self.sd_runner_client.run(_type, image_path, append=modify_call)
            ImageDetails.previous_image_generation_image = image_path
            self.toast(_("Running image gen: ") + str(_type))
        except Exception as e:
            self.handle_error(_("Error running image generation:") + "\n" + str(e), title=_("Warning"))

    def run_refacdir(self, event=None):
        self.refacdir_client.start()
        self.refacdir_client.run(self.img_path)
        self.toast(_("Running refacdir"))

    def handle_error(self, error_text, title=None, kind="error"):
        traceback.print_exc()
        if title is None:
            title = _("Error")
        self.alert(title, error_text, kind=kind)

    def alert(self, title, message, kind="info", hidemain=True) -> None:
        if kind not in ("error", "warning", "info", "askokcancel"):
            raise ValueError("Unsupported alert kind.")

        Utils.log_yellow(f"Alert - Title: \"{title}\" Message: {message}")
        if kind == "askokcancel":
            alert_method = getattr(messagebox, kind)
        else:
            alert_method = getattr(messagebox, f"show{kind}")
        return alert_method(title, message)

    def toast(self, message, time_in_seconds=config.toasts_persist_seconds):
        Utils.log("Toast message: " + message.replace("\n", " "))
        if not config.show_toasts:
            return

        # Set the position of the toast on the screen (top right)
        width = 300
        height = 100
        x = self.master.winfo_screenwidth() - width
        y = 0

        # Create the toast on the top level
        toast = Toplevel(self.master, bg=AppStyle.BG_COLOR)
        toast.geometry(f'{width}x{height}+{int(x)}+{int(y)}')
        self.container = Frame(toast)
        self.container.config(bg=AppStyle.BG_COLOR)
        self.container.pack(fill=BOTH, expand=YES)
        label = Label(
            self.container,
            text=message.strip(),
            anchor=NW,
            bg=AppStyle.BG_COLOR,
            fg=AppStyle.FG_COLOR,
            font=('Helvetica', 10)
        )
        label.grid(row=1, column=1, sticky="NSEW", padx=10, pady=(0, 5))

        # Make the window invisible and bring it to front
        toast.attributes('-topmost', True)
        # toast.withdraw()

        # Start a new thread that will destroy the window after a few seconds
        def self_destruct_after(time_in_seconds):
            time.sleep(time_in_seconds)
            label.destroy()
            toast.destroy()
        start_thread(self_destruct_after, use_asyncio=False, args=[time_in_seconds])
        if sys.platform == "darwin":
            self.media_canvas.focus()

    def _set_label_state(self, text=None, group_number=None, size=-1):
        if text is not None:
            self.label_state["text"] = text
        elif size > -1:
            if group_number is None:
                self.label_state["text"] = ""
            else:
                args = (group_number + 1, len(self.compare_wrapper.file_groups), size)
                self.label_state["text"] = Utils._wrap_text_to_fit_length(
                    _("GROUP_DETAILS").format(*args), 30)
        else:  # Set based on file count
            file_count = self.file_browser.count()
            if file_count == 0:
                text = _("No image files found")
            else:
                text = _("1 image file found") if file_count == 1 else _(
                    "{0} image files found").format(file_count)
            if self.inclusion_pattern.get() != "":
                text += "\n" + _("(filtered)")
            self.label_state["text"] = text

    def apply_to_grid(self, component, sticky=None, pady=0, specific_row=None):
        row = self.row_counter if specific_row is None else specific_row
        if sticky is None:
            component.grid(column=0, row=row, pady=pady)
        else:
            component.grid(column=0, row=row, sticky=sticky, pady=pady)
        if specific_row is None:
            self.row_counter += 1

    def add_label(self, label_ref, text, sticky=W, pady=0):
        label_ref['text'] = text
        label_ref['font'] = fnt.Font(size=config.font_size)
        self.apply_to_grid(label_ref, sticky=sticky, pady=pady)

    def add_button(self, button_ref_name, text, command):
        if getattr(self, button_ref_name) is None:
            button = Button(master=self.sidebar, text=text, command=command)
            setattr(self, button_ref_name, button)
            button  # for some reason this is necessary to maintain the reference?
            self.apply_to_grid(button)

    def new_entry(self, text_variable=None, text="", aware_entry=True):
        if aware_entry:
            return AwareEntry(self.sidebar, text=text, textvariable=text_variable, width=30, font=fnt.Font(size=config.font_size))
        else:

            return Entry(self.sidebar, text=text, textvariable=text_variable, width=30, font=fnt.Font(size=config.font_size))

    def check_focus(self, event, func):
        # Skip key binding that might be triggered by a text entry
        if event is not None and AwareEntry.an_entry_has_focus:
            return
        if func:
            func()

    def destroy_grid_element(self, element_ref_name, decrement_row_counter=True):
        element = getattr(self, element_ref_name)
        if element is not None:
            element.destroy()
            setattr(self, element_ref_name, None)
            if decrement_row_counter:
                self.row_counter -= 1


if __name__ == "__main__":
    I18N.install_locale(config.locale, verbose=config.print_settings)
    root = ThemedTk(theme="black", themebg="black")
    root.title(_(" Simple Image Compare "))
    assets = os.path.join(os.path.dirname(os.path.realpath(__file__)), "assets")
    icon = PhotoImage(file=os.path.join(assets, "icon.png"))
    root.iconphoto(False, icon)
    root.geometry(config.default_main_window_size)
    # root.attributes('-fullscreen', True)
    app = App(root)

    # sys.settrace(Utils.trace)

    # Graceful shutdown handler
    def graceful_shutdown(signum, frame):
        Utils.log("Caught signal, shutting down gracefully...")
        app.on_closing()
        exit(0)

    # Register the signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)

    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
