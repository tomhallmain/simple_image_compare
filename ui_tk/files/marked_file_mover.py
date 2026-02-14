import os
import re

from tkinter import Frame, Label, filedialog, LEFT, W
from tkinter.ttk import Button

from compare.compare_embeddings_clip import CompareEmbeddingClip
from files.file_action import FileAction
from files.file_browser import FileBrowser
from files.marked_files import MarkedFiles
from files.pdf_creator import PDFCreator
from image.frame_cache import FrameCache
from image.image_data_extractor import image_data_extractor
from lib.multi_display import SmartToplevel
from ui_tk.auth.password_utils import require_password
from ui_tk.files.hotkey_actions_window import HotkeyActionsWindow
from ui_tk.files.pdf_options_window import PDFOptionsWindow
from utils.app_style import AppStyle
from utils.config import config
from utils.constants import Mode, ProtectedActions
from utils.logging_setup import get_logger
from utils.translations import I18N
from utils.utils import Utils, ModifierKey

_ = I18N._
logger = get_logger("marked_file_mover")



class MarkedFileMover():
    _current_window = None  # Track the current window instance

    MAX_HEIGHT = 900
    N_TARGET_DIRS_CUTOFF = 30
    COL_0_WIDTH = 600

    @staticmethod
    def get_geometry(is_gui=True):
        if is_gui:
            width = 600
            min_height = 300
            height = len(MarkedFiles.mark_target_dirs) * 22 + 20
            if height > MarkedFiles.MAX_HEIGHT:
                height = MarkedFiles.MAX_HEIGHT
                width *= 2 if len(MarkedFiles.mark_target_dirs) < MarkedFileMover.N_TARGET_DIRS_CUTOFF * 2 else 3
            else:
                height = max(height, min_height)
        else:
            width = 300
            height = 100
        return f"{width}x{height}"

    @staticmethod
    def add_columns():
        if len(MarkedFiles.mark_target_dirs) > MarkedFileMover.N_TARGET_DIRS_CUTOFF:
            if len(MarkedFiles.mark_target_dirs) > MarkedFileMover.N_TARGET_DIRS_CUTOFF * 2:
                return 2
            return 1
        return 0

    @staticmethod
    def show_window(master, is_gui, single_image, current_image, app_mode, app_actions, base_dir="."):
        """
        Show the marked files window. If a window is already open, focus it instead of creating a new one.
        Returns the window instance.
        """
        # Check if a window already exists and is still valid
        if MarkedFileMover._current_window is not None:
            try:
                # Check if the window still exists
                if MarkedFileMover._current_window.master.winfo_exists():
                    # Window exists, update title in case marks changed, set full opacity, then focus it
                    MarkedFileMover._current_window.master.title(_("Move {0} Marked File(s)").format(len(MarkedFiles.file_marks)))
                    MarkedFileMover._current_window.master.attributes('-alpha', 1.0)  # Set full opacity
                    MarkedFileMover._current_window.master.lift()
                    MarkedFileMover._current_window.master.focus_force()
                    return MarkedFileMover._current_window
            except:
                # Window was destroyed, clear the reference
                MarkedFileMover._current_window = None
        
        # No existing window, create a new one
        top_level = SmartToplevel(persistent_parent=master, geometry=MarkedFileMover.get_geometry(is_gui=is_gui))
        top_level.title(_("Move {0} Marked File(s)").format(len(MarkedFiles.file_marks)))
        if not is_gui:
            top_level.attributes('-alpha', 0.3)
        
        window_instance = MarkedFileMover(top_level, is_gui, single_image, current_image, app_mode, app_actions, base_dir)
        MarkedFileMover._current_window = window_instance
        return window_instance

    def __init__(self, master, is_gui, single_image, current_image, app_mode, app_actions, base_dir="."):
        # If there's already a window instance, don't create a new one
        # (This should be prevented by show_window, but adding as a safeguard)
        if MarkedFileMover._current_window is not None:
            try:
                if MarkedFileMover._current_window.master.winfo_exists():
                    # Existing window found, this shouldn't happen if show_window is used correctly
                    logger.warning("Attempted to create MarkedFileMover window when one already exists")
            except:
                MarkedFileMover._current_window = None
        
        self.is_gui = is_gui
        self.single_image = single_image
        self.current_image = current_image
        self.master = master
        self.app_mode = app_mode
        self.is_sorted_by_embedding = False
        self.app_actions = app_actions
        self.base_dir = os.path.normpath(base_dir)
        self.filter_text = ""
        self.filtered_target_dirs = MarkedFiles.mark_target_dirs[:]

        # Use the last set target directory as a base if any directories have been set
        if MarkedFiles.last_set_target_dir and os.path.isdir(MarkedFiles.last_set_target_dir):
            self.starting_target = MarkedFiles.last_set_target_dir
        else:
            self.starting_target = base_dir

        self.do_set_permanent_mark_target = False
        self.do_set_hotkey_action = -1
        self.move_btn_list = []
        self.copy_btn_list = []
        self.label_list = []
        
        # Keystroke buffering to handle rapid input during window initialization
        self.keystroke_buffer = []
        self.widgets_ready = False

        if self.is_gui:
            self.frame = Frame(self.master)
            self.frame.grid(column=0, row=0)
            self.frame.columnconfigure(0, weight=9)
            self.frame.columnconfigure(1, weight=1)
            self.frame.columnconfigure(2, weight=1)

            add_columns = MarkedFiles.add_columns()

            if add_columns > 0:
                self.frame.columnconfigure(3, weight=9)
                self.frame.columnconfigure(4, weight=1)
                self.frame.columnconfigure(5, weight=1)
                if add_columns > 1:
                    self.frame.columnconfigure(6, weight=9)
                    self.frame.columnconfigure(7, weight=1)
                    self.frame.columnconfigure(8, weight=1)

            self.frame.config(bg=AppStyle.BG_COLOR)

            self.add_target_dir_widgets()

            self._label_info = Label(self.frame)
            self.add_label(self._label_info, _("Set a new target directory"), row=0, wraplength=MarkedFileMover.COL_0_WIDTH)
            self.add_directory_move_btn = None
            self.add_btn("add_directory_move_btn", _("MOVE"), self.handle_target_directory, column=1)
            def copy_handler_new_dir(event=None, self=self):
                self.handle_target_directory(move_func=Utils.copy_file)
            self.add_directory_copy_btn = None
            self.add_btn("add_directory_copy_btn", _("COPY"), copy_handler_new_dir, column=2)
            self.delete_btn = None
            self.add_btn("delete_btn", _("DELETE"), self.delete_marked_files, column=3)
            self.set_target_dirs_from_dir_btn = None
            add_dirs_text = Utils._wrap_text_to_fit_length(_("Add directories from parent"), 30)
            self.add_btn("set_target_dirs_from_dir_btn", add_dirs_text, self.set_target_dirs_from_dir, column=4)
            self.clear_target_dirs_btn = None
            self.add_btn("clear_target_dirs_btn", _("Clear targets"), self.clear_target_dirs, column=5)
            self.create_pdf_btn = None
            self.add_btn("create_pdf_btn", _("Create PDF"), self.create_pdf_from_marks, column=6)
            self.frame.after(1, lambda: self.frame.focus_force())
        else:
            self.master.after(1, lambda: self.master.focus_force())

        self.master.bind("<Key>", self.filter_targets)
        self.master.bind("<Return>", self.do_action)
        self.master.bind("<Escape>", self.close_windows)
        self.master.protocol("WM_DELETE_WINDOW", self.close_windows)
        self.master.bind('<Shift-Delete>', self.delete_marked_files)
        self.master.bind('<Shift-C>', self.clear_marks)
        self.master.bind("<Button-2>", self.delete_marked_files)
        self.master.bind("<Button-3>", self.do_action_test_is_in_directory)
        self.master.bind("<Control-t>", self.set_permanent_mark_target)
        self.master.bind("<Control-s>", self.sort_target_dirs_by_embedding)
        self.master.bind("<Control-h>", self.open_hotkey_actions_window)
        self.master.bind("<Prior>", self.page_up)
        self.master.bind("<Next>", self.page_down)
        
        # Mark widgets as ready and process any buffered keystrokes
        self.master.after_idle(self._mark_widgets_ready_and_process_buffer)


    def add_target_dir_widgets(self):
        row = 0
        base_col = 0
        for i in range(len(self.filtered_target_dirs)):
            if i >= MarkedFileMover.N_TARGET_DIRS_CUTOFF * 2:
                row = i-MarkedFileMover.N_TARGET_DIRS_CUTOFF*2+1
                base_col = 6
            elif i >= MarkedFileMover.N_TARGET_DIRS_CUTOFF:
                row = i-MarkedFileMover.N_TARGET_DIRS_CUTOFF+1
                base_col = 3
            else:
                row = i+1
            target_dir = self.filtered_target_dirs[i]
            _label_info = Label(self.frame)
            self.label_list.append(_label_info)
            self.add_label(_label_info, target_dir, row=row, column=base_col, wraplength=MarkedFileMover.COL_0_WIDTH)

            move_btn = Button(self.frame, text=_("Move"))
            self.move_btn_list.append(move_btn)
            move_btn.grid(row=row, column=base_col+1)
            def move_handler(event, self=self, target_dir=target_dir):
                return self.move_marks_to_dir(event, target_dir)
            move_btn.bind("<Button-1>", move_handler)

            copy_btn = Button(self.frame, text=_("Copy"))
            self.copy_btn_list.append(copy_btn)
            copy_btn.grid(row=row, column=base_col+2)
            def copy_handler(event, self=self, target_dir=target_dir):
                return self.move_marks_to_dir(event, target_dir, move_func=Utils.copy_file)
            copy_btn.bind("<Button-1>", copy_handler)

    def clear_marks(self):
        MarkedFiles.clear_file_marks(self.app_actions.toast)
        self.close_windows()
    
    @require_password(ProtectedActions.SET_HOTKEY_ACTIONS)
    def open_hotkey_actions_window(self, event):
        try:
            hotkey_actions_window = HotkeyActionsWindow(self.master, self.app_actions, self.set_permanent_mark_target, self.set_hotkey_action)
        except Exception as e:
            self.app_actions.alert("Error opening hotkey actions window: " + str(e), master=self.master)

    @require_password(
        ProtectedActions.SET_HOTKEY_ACTIONS,
        custom_text=_("WARNING: This action sets hotkey actions that will be used for future file operations. You may have accidentally triggered this shortcut due to a sticky Control key. Please confirm you want to proceed."),
        allow_unauthenticated=False
    )
    def set_permanent_mark_target(self, event=None):
        self.do_set_permanent_mark_target = True
        logger.debug(f"Setting permanent mark target hotkey action")
        self.app_actions.toast(_("Recording next mark target and action."))

    def set_hotkey_action(self, event=None, hotkey_override=None):
        assert event is not None or hotkey_override is not None
        self.do_set_hotkey_action = int(event.keysym) if hotkey_override is None else int(hotkey_override)
        logger.debug(f"Doing set hotkey action: {self.do_set_hotkey_action}")
        self.app_actions.toast(_("Recording next mark target and action."))

    @staticmethod
    def get_target_directory(target_dir, starting_target, app_actions):
        """
        If target dir given is not valid then ask user for a new one
        """
        if target_dir:
            if os.path.isdir(target_dir):
                return target_dir, True
            else:
                if target_dir in MarkedFiles.mark_target_dirs:
                    MarkedFiles.mark_target_dirs.remove(target_dir)
                app_actions.warn(_("Invalid directory: %s").format(target_dir))
        target_dir = filedialog.askdirectory(
                parent=app_actions.get_master(),
                initialdir=starting_target, title=_("Select target directory for marked files"))
        #app_actions.store_info_cache() # save new target directory
        return target_dir, False

    def handle_target_directory(self, event=None, target_dir=None, move_func=Utils.move_file):
        """
        Have to call this when user is setting a new target directory as well,
        in which case target_dir will be None.

        In this case we will need to add the new target dir to the list of valid directories.

        Also in this case, this function will call itself by calling
        move_marks_to_target_dir(), just this time with the directory set.
        """
        target_dir, target_was_valid = MarkedFileMover.get_target_directory(
            target_dir, self.starting_target, self.app_actions
        )
        if not os.path.isdir(target_dir):
            self.close_windows()
            raise Exception("Failed to set target directory to receive marked files.")
        if target_was_valid and target_dir is not None:
            return target_dir

        target_dir = os.path.normpath(target_dir)
        if target_dir not in MarkedFiles.mark_target_dirs:
            MarkedFiles.mark_target_dirs.append(target_dir)
            MarkedFiles.mark_target_dirs.sort()
        if move_func is not None:
            self.move_marks_to_dir(target_dir=target_dir, move_func=move_func)
        else:
            self.test_is_in_directory(event=event, target_dir=target_dir)

    def move_marks_to_dir(self, event=None, target_dir=None, move_func=Utils.move_file):
        target_dir = self.handle_target_directory(target_dir=target_dir)
        if config.debug and self.filter_text is not None and self.filter_text.strip() != "":
            logger.debug(f"Filtered by string: {self.filter_text}")
        if self.do_set_permanent_mark_target:
            FileAction.set_permanent_action(target_dir, move_func, self.app_actions.toast)
            self.do_set_permanent_mark_target = False
        if self.do_set_hotkey_action > -1:
            FileAction.set_hotkey_action(self.do_set_hotkey_action, target_dir, move_func, self.app_actions.toast)
            self.do_set_hotkey_action = -1
        some_files_already_present, exceptions_present = MarkedFiles.move_marks_to_dir_static(
            self.app_actions, target_dir=target_dir, move_func=move_func,
            single_image=self.single_image, current_image=self.current_image)
        self.close_windows()

    @staticmethod
    def undo_move_marks(target_dir, app_actions):
        def get_base_dir_callback():
            from tkinter import filedialog
            base_dir = filedialog.askdirectory(
                parent=app_actions.get_master(),
                initialdir=target_dir, title=_("Where should the marked files have gone?"))
            return base_dir
        return MarkedFiles.undo_move_marks(
            target_dir, app_actions,
            get_base_dir_callback=get_base_dir_callback,
            get_target_dir_callback=MarkedFileMover.get_target_directory
        )

    def set_target_dirs_from_dir(self, event=None):
        """
        Gather all first-level child directories from the selected directory and
        add them as target directories, updating the window when complete.
        """
        parent_dir = filedialog.askdirectory(
                parent=self.master,
                initialdir=self.starting_target, title=_("Select parent directory for target directories"))
        if not os.path.isdir(parent_dir):
            raise Exception("Failed to set target directory to receive marked files.")

        target_dirs_to_add = [name for name in os.listdir(parent_dir)
            if os.path.isdir(os.path.join(parent_dir, name))]

        for target_dir in target_dirs_to_add:
            dirpath = os.path.normpath(os.path.join(parent_dir, target_dir))
            if dirpath not in MarkedFiles.mark_target_dirs:
                if dirpath != self.base_dir:
                    MarkedFiles.mark_target_dirs.append(dirpath)

        MarkedFiles.mark_target_dirs.sort()
        self.filtered_target_dirs = MarkedFiles.mark_target_dirs[:]
        self.filter_text = ""  # Clear the filter to ensure all new directories are shown
        self._refresh_widgets()
        self.frame.after(1, lambda: self.frame.focus_force())

    def _refresh_widgets(self):
        if self.is_gui:
            self.clear_widget_lists()
            self.add_target_dir_widgets()
            self.master.update()

    def _get_paging_length(self):
        return max(1, int(len(self.filtered_target_dirs) / 10))

    def page_up(self, event=None):
        paging_len = self._get_paging_length()
        idx = len(self.filtered_target_dirs) - paging_len
        self.filtered_target_dirs = self.filtered_target_dirs[idx:] + self.filtered_target_dirs[:idx]
        self._refresh_widgets()

    def page_down(self, event=None):
        paging_len = self._get_paging_length()
        self.filtered_target_dirs = self.filtered_target_dirs[paging_len:] + self.filtered_target_dirs[:paging_len]
        self._refresh_widgets()

    def _mark_widgets_ready_and_process_buffer(self):
        """
        Mark widgets as ready and process any buffered keystrokes.
        """
        self.widgets_ready = True
        # Process buffered keystrokes in order
        for buffered_event in self.keystroke_buffer:
            self._process_filter_keystroke(buffered_event)
        self.keystroke_buffer.clear()
        # If there's a buffered Return key, process it after filter keystrokes are applied
        if hasattr(self, '_buffered_return_event'):
            # Use after_idle to ensure filter processing is complete
            self.master.after_idle(lambda: self.do_action(self._buffered_return_event))
            delattr(self, '_buffered_return_event')

    def filter_targets(self, event):
        """
        Rebuild the filtered target directories list based on the filter string and update the UI.
        Buffers keystrokes if widgets are not ready yet.
        """
        # Buffer keystrokes if widgets aren't ready yet
        if not self.widgets_ready:
            self.keystroke_buffer.append(event)
            return
        
        self._process_filter_keystroke(event)

    def _process_filter_keystroke(self, event):
        """
        Process a single filter keystroke event.
        """
        modifier_key_pressed = (event.state & 0x1) != 0 or (event.state & 0x4) != 0 # Do not filter if modifier key is down
        if modifier_key_pressed:
            return
        if len(event.keysym) > 1:
            # If the key is up/down arrow key, roll the list up/down
            if event.keysym == "Down" or event.keysym == "Up":
                if event.keysym == "Down":
                    self.filtered_target_dirs = self.filtered_target_dirs[1:] + [self.filtered_target_dirs[0]]
                else:  # keysym == "Up"
                    self.filtered_target_dirs = [self.filtered_target_dirs[-1]] + self.filtered_target_dirs[:-1]
                self._refresh_widgets()
            if event.keysym != "BackSpace":
                return
        if event.keysym == "BackSpace":
            if len(self.filter_text) > 0:
                self.filter_text = self.filter_text[:-1]
        elif event.char:
            self.filter_text += event.char
        else:
            return
        if self.filter_text.strip() == "":
            if config.debug:
                logger.debug("Filter unset")
            # Restore the list of target directories to the full list
            self.filtered_target_dirs.clear()
            self.filtered_target_dirs = MarkedFiles.mark_target_dirs[:]
        else:
            temp = []
            # First pass try to match directory basename
            for target_dir in MarkedFiles.mark_target_dirs:
                basename = os.path.basename(os.path.normpath(target_dir))
                if basename.lower() == self.filter_text:
                    temp.append(target_dir)
            for target_dir in MarkedFiles.mark_target_dirs:
                if target_dir not in temp:
                    basename = os.path.basename(os.path.normpath(target_dir))
                    if basename.lower().startswith(self.filter_text):
                        temp.append(target_dir)
            # Second pass try to match parent directory name, so these will appear after
            for target_dir in MarkedFiles.mark_target_dirs:
                if target_dir not in temp:
                    dirname = os.path.basename(os.path.dirname(os.path.normpath(target_dir)))
                    if dirname and dirname.lower().startswith(self.filter_text):
                        temp.append(target_dir)
            # Third pass try to match part of the basename
            for target_dir in MarkedFiles.mark_target_dirs:
                if target_dir not in temp:
                    basename = os.path.basename(os.path.normpath(target_dir))
                    if basename and (f" {self.filter_text}" in basename.lower() or f"_{self.filter_text}" in basename.lower()):
                        temp.append(target_dir)
            self.filtered_target_dirs = temp[:]

        self._refresh_widgets()

    def do_action(self, event):
        """
        The user has requested to do something with the marked files. Based on the context, figure out what to do.

        If no target directories set, call handle_target_directory() with target_dir=None to set a new directory.

        If target directories set, call move_marks_to_dir() to move the marked files to the first target directory.

        If shift key pressed, copy the files, but if not, just move them.

        If control key pressed, ignore any marked dirs and set a new target directory.

        If alt key pressed, use the penultimate mark target dir as target directory.

        The idea is the user can filter the directories using keypresses, then press enter to
        do the action on the first filtered directory.

        TODO: handle case of multiple filtered directories better, instead of just selecting the first
        """
        # Buffer Return key if widgets aren't ready yet - process filter keystrokes first
        if not self.widgets_ready:
            self._buffered_return_event = event
            return
        
        shift_key_pressed, control_key_pressed, alt_key_pressed = Utils.modifier_key_pressed(
            event, keys_to_check=[ModifierKey.SHIFT, ModifierKey.CTRL, ModifierKey.ALT])
        move_func = Utils.copy_file if shift_key_pressed else Utils.move_file
        if alt_key_pressed:
            penultimate_action = FileAction.get_history_action(start_index=1)
            if penultimate_action is not None and os.path.isdir(penultimate_action.target):
                self.move_marks_to_dir(target_dir=penultimate_action.target, move_func=move_func)
        elif len(self.filtered_target_dirs) == 0 or control_key_pressed:
            self.handle_target_directory(move_func=move_func)
        else:
            # TODO maybe sort the last target dir first in the list instead of this
            # might be confusing otherwise
            if len(self.filtered_target_dirs) == 1 or self.filter_text.strip() != "" or self.is_sorted_by_embedding:
                target_dir = self.filtered_target_dirs[0]
            else:
                target_dir = MarkedFiles.last_set_target_dir
            self.move_marks_to_dir(target_dir=target_dir, move_func=move_func)

    def clear_target_dirs(self, event=None):
        MarkedFiles.mark_target_dirs.clear()
        self.filtered_target_dirs.clear()
        self._refresh_widgets()

    def _get_embedding_text_for_dirpath(self, dirpath):
        basename = os.path.basename(dirpath)
        for text in config.text_embedding_search_presets:
            if basename == text or re.search(f"(^|_| ){text}($|_| )", basename):
                logger.info(f"Found embeddable directory for text {text}: {dirpath}")
                return text
        return None

    def sort_target_dirs_by_embedding(self, event=None):
        embedding_texts = {}
        for d in self.filtered_target_dirs:
            embedding_text = self._get_embedding_text_for_dirpath(d)
            if embedding_text is not None and embedding_text.strip() != "":
                embedding_texts[d] = embedding_text
        similarities = CompareEmbeddingClip.single_text_compare(self.single_image, embedding_texts)
        sorted_dirs = []
        for dirpath, similarity in sorted(similarities.items(), key=lambda x: -x[1]):
            sorted_dirs.append(dirpath)
        self.filtered_target_dirs = list(sorted_dirs)
        self.is_sorted_by_embedding = True
        self._refresh_widgets()
        self.app_actions.toast(_("Sorted directories by embedding comparison."))

    def clear_widget_lists(self):
        for btn in self.move_btn_list:
            btn.destroy()
        for btn in self.copy_btn_list:
            btn.destroy()
        for label in self.label_list:
            label.destroy()
        self.move_btn_list = []
        self.copy_btn_list = []
        self.label_list = []

    def delete_marked_files(self, event=None):
        """
        Delete the marked files.

        Unfortunately, since there are challenges with restoring files from trash folder
        an undo operation is not implemented.
        """
        # Use high severity alert for dangerous operations (more than 5 files)
        severity = "high" if len(MarkedFiles.file_marks) > 5 else "normal"
        res = self.app_actions.alert(_("Confirm Delete"),
                _("Deleting %s marked files - Are you sure you want to proceed?").format(len(MarkedFiles.file_marks)),
                kind="askokcancel", severity=severity, master=self.master)
        from tkinter import messagebox
        if res != messagebox.OK and res != True:
            return

        # Release media if current image is among marked files (e.g. SVG with open temp PNG)
        if self.current_image and self.current_image in MarkedFiles.file_marks:
            self.app_actions.release_media_canvas()
        removed_files = []
        failed_to_delete = []
        for filepath in MarkedFiles.file_marks:
            try:
                # For SVG (and other cached types), clear frame cache and temp file so no handles are held
                if config.enable_svgs and filepath.lower().endswith(".svg"):
                    FrameCache.remove_from_cache(filepath, delete_temp_file=True)
                # NOTE since undo delete is not supported, the delete callback handles setting a delete lock
                self.app_actions.delete(filepath, manual_delete=False)
                removed_files.append(filepath)
            except Exception as e:
                logger.error(f"Failed to delete {filepath}: {e}")
                if os.path.exists(filepath):
                    failed_to_delete.append(filepath)

        MarkedFiles.file_marks.clear()
        if len(failed_to_delete) > 0:
            MarkedFiles.file_marks.extend(failed_to_delete)
            self.app_actions.alert(_("Delete Failed"),
                    _("Failed to delete %s files - check log for details.").format(len(failed_to_delete)),
                    kind="warning", master=self.master)
        else:
            self.app_actions.warn(_("Deleted %s marked files.").format(len(removed_files)))

        # In the BROWSE case, the file removal should be recognized by the file browser
        ## TODO it will not be handled in case of using file JSON. need to handle this case separately.
        self.app_actions.refresh(removed_files=(removed_files if self.app_mode != Mode.BROWSE else []))
        self.close_windows()

    def do_action_test_is_in_directory(self, event):
        control_key_pressed, alt_key_pressed = Utils.modifier_key_pressed(
            event, keys_to_check=[ModifierKey.CTRL, ModifierKey.ALT])
        target_dir = None
        if alt_key_pressed:
            penultimate_action = FileAction.get_history_action(start_index=1)
            if penultimate_action is not None and os.path.isdir(penultimate_action.target):
                target_dir = penultimate_action.target
        elif len(self.filtered_target_dirs) == 0 or control_key_pressed:
            self.handle_target_directory(event=event, move_func=None)
            return
        else:
            if len(self.filtered_target_dirs) == 1 or self.filter_text.strip() != "" or self.is_sorted_by_embedding:
                target_dir = self.filtered_target_dirs[0]
            else:
                target_dir = MarkedFiles.last_set_target_dir

        if target_dir is None:
            self.handle_target_directory(event=event, move_func=None)
        else:
            self.test_is_in_directory(event=event, target_dir=target_dir)

    def test_is_in_directory(self, event=None, target_dir=None):
        target_dir = self.handle_target_directory(target_dir=target_dir)
        if config.debug and self.filter_text is not None and self.filter_text.strip() != "":
            logger.debug(f"Filtered by string: {self.filter_text}")
        if Utils.modifier_key_pressed(event, keys_to_check=[ModifierKey.SHIFT]):
            self.find_is_downstream_related_image_in_directory(target_dir=target_dir)
        else:
            some_files_already_present = MarkedFiles.test_in_directory_static(self.app_actions, target_dir=target_dir, single_image=self.single_image)
        self.close_windows()

    def find_is_downstream_related_image_in_directory(self, target_dir):
        if MarkedFiles.file_browser is None or MarkedFiles.file_browser.directory != target_dir or not MarkedFiles.file_browser.recursive:
            MarkedFiles.file_browser = FileBrowser(directory=target_dir, recursive=True)
        MarkedFiles.file_browser._gather_files(files=None)
        marked_file_basenames = []
        for marked_file in MarkedFiles.file_marks:
            marked_file_basenames.append(os.path.basename(marked_file))
        downstream_related_images = []
        for path in MarkedFiles.file_browser.filepaths:
            if path in MarkedFiles.file_marks:
                continue
            related_image_path = image_data_extractor.get_related_image_path(path)
            if related_image_path is not None:
                if related_image_path in MarkedFiles.file_marks:
                    downstream_related_images.append(path)
                else:
                    file_basename = os.path.basename(related_image_path)
                    if len(file_basename) > 10 and file_basename in marked_file_basenames:
                        # NOTE this relation criteria is flimsy but it's better to have false positives than
                        # potentially miss valid files that have been moved since this search is happening
                        downstream_related_images.append(path)
        if len(downstream_related_images) > 0:
            for image in downstream_related_images:
                logger.warning(f"Downstream related image found: {image}")
            self.app_actions.toast(_("Found %s downstream related images").format(len(downstream_related_images)))
        else:
            self.app_actions.toast(_("No downstream related images found"))

    def close_windows(self, event=None):
        # Clear the instance reference before destroying
        if MarkedFileMover._current_window is self:
            MarkedFileMover._current_window = None
        self.master.destroy()
        if self.single_image is not None and len(MarkedFiles.file_marks) == 1:
            # This implies the user has opened the marks window directly from the current image
            # but did not take any action on this marked file. It's possible that the action
            # the user requested was already taken, and an error was thrown preventing it from
            # being repeated and overwriting the file. If so the user likely doesn't want to
            # take any more actions on this file so we can forget about it.
            MarkedFiles.file_marks.clear()
            self.app_actions.toast(_("Cleared marked file"))

    def add_label(self, label_ref, text, row=0, column=0, wraplength=500):
        label_ref['text'] = text
        label_ref.grid(column=column, row=row, sticky=W)
        label_ref.config(wraplength=wraplength, justify=LEFT, bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)

    def add_btn(self, button_ref_name, text, command, row=0, column=0):
        if getattr(self, button_ref_name) is None:
            button = Button(master=self.frame, text=text, command=command)
            setattr(self, button_ref_name, button)
            button  # for some reason this is necessary to maintain the reference?
            button.grid(row=row, column=column)

    def create_pdf_from_marks(self, event=None, output_path=None):
        """
        Create a PDF from marked files using the PDFCreator class.
        Opens options window first to let user choose quality settings.
        """
        def _save_file_dialog(default_dir, default_name):
            from tkinter import filedialog
            return filedialog.asksaveasfilename(
                parent=self.app_actions.get_master(),
                defaultextension=".pdf",
                initialdir=default_dir,
                initialfile=default_name,
                filetypes=[("PDF files", "*.pdf")],
                title=_("Save PDF as"),
            )

        def pdf_callback(options):
            PDFCreator.create_pdf_from_files(
                MarkedFiles.file_marks, self.app_actions, output_path, options,
                save_file_callback=_save_file_dialog,
            )

        PDFOptionsWindow.show(self.master, self.app_actions, pdf_callback)


