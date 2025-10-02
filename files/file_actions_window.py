from datetime import datetime
import os

from tkinter import Toplevel, Frame, Label, W, CENTER, LEFT, RIGHT
from tkinter.ttk import Button, Style

from utils.config import config
from lib.tk_scroll_demo import ScrollFrame
from utils.app_info_cache import app_info_cache
from utils.app_style import AppStyle
from utils.logging_setup import get_logger
from utils.utils import Utils, ModifierKey
from utils.translations import I18N

_ = I18N._

logger = get_logger("file_actions_window")


class Action():
    def __init__(self, action, target, original_marks=[], new_files=[], auto=False, timestamp=None):
        self.action = action
        self.target = target
        self.original_marks = original_marks[:]
        self.new_files = new_files[:]
        self.auto = auto
        self.timestamp = timestamp or datetime.now()

    def add_file(self, file):
        self.new_files.append(file)

    def get_original_directory(self):
        if len(self.original_marks) == 0:
            raise Exception("No original marks")
        return os.path.dirname(os.path.abspath(self.original_marks[-1]))

    def is_move_action(self):
        return self.action.__name__.startswith("move")

    def is_today(self):
        """Check if this action was performed today or within 24 hours if it's early morning."""
        if not self.timestamp:
            return False
        
        now = datetime.now()
        today = now.date()
        action_date = self.timestamp.date()
        
        # If it's the same date, it's definitely today
        if action_date == today:
            return True
        
        # If it's early morning (before 5 AM), include actions from the past 24 hours
        if now.hour < 5:
            # Check if the action was within the last 24 hours
            time_diff = now - self.timestamp
            return time_diff.total_seconds() <= 24 * 3600  # 24 hours in seconds
        
        return False

    def any_new_files_exist(self):
        for file in self.new_files:
            if os.path.exists(file):
                return True
        return False

    def remove_new_files(self):
        for f in self.new_files[:]:
            try:
                os.remove(f)
            except Exception as e:
                logger.error(e)

    def get_action(self, do_flip=False):
        action = self.action
        if do_flip:
            if action == Utils.move_file:
                action = Utils.copy_file
            elif action == Utils.copy_file:
                action = Utils.move_file
        return self.action
    
    def to_dict(self):
        return {
            "action": Action.convert_action_to_text(self.action),
            "target": self.target,
            "original_marks": self.original_marks[:],
            "new_files": self.new_files[:],
            "auto": self.auto,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
            }

    @staticmethod
    def from_dict(dct):
        timestamp = None
        if "timestamp" in dct and dct["timestamp"]:
            try:
                timestamp = datetime.fromisoformat(dct["timestamp"])
            except ValueError:
                # Fallback for old format or invalid timestamps
                timestamp = None
        
        return Action(Action.convert_action_from_text(dct["action"]),
                      dct["target"], dct["original_marks"][:], dct["new_files"][:],
                      dct["auto"] if "auto" in dct else False, timestamp)

    def __eq__(self, other):
        if not isinstance(other, Action):
            return False
        return self.action == other.action and self.target == other.target
    
    def __hash__(self):
        return hash((self.action, self.target))

    def __str__(self):
        return self.action.__name__ + " to " + self.target

    @staticmethod
    def convert_action_from_text(action_text):
        if action_text == "move_file":
            return Utils.move_file
        elif action_text == "copy_file":
            return Utils.copy_file
        else:
            return None

    @staticmethod
    def convert_action_to_text(action_func):
        if action_func == Utils.move_file:
            return "move_file"
        elif action_func == Utils.copy_file:
            return "copy_file"
        else:
            return None

    @staticmethod
    def _is_matching_action_in_list(action_list, action):
        for _action in action_list:
            if action == _action:
                if len(action.new_files) != len(_action.new_files):
                    continue
                if tuple(action.new_files) == tuple(_action.new_files):
                    return True
        return False

def setup_permanent_action():
    permanent_mark_target = app_info_cache.get_meta("permanent_mark_target")
    permanent_action = app_info_cache.get_meta("permanent_action")
    return Action(Action.convert_action_from_text(permanent_action), permanent_mark_target)

def setup_hotkey_actions():
    hotkey_actions_dict = app_info_cache.get_meta("hotkey_actions", default_val={})
    assert type(hotkey_actions_dict) == dict
    hotkey_actions = {}
    for number, action in hotkey_actions_dict.items():
        hotkey_actions[int(number)] = Action(Action.convert_action_from_text(action["action"]), action["target"])
    return hotkey_actions


class FileActionsWindow:
    '''
    Window to hold info about completed file actions.
    '''
    top_level = None
    permanent_action = setup_permanent_action()
    hotkey_actions = setup_hotkey_actions()
    action_history = []
    MAX_ACTIONS = config.file_actions_history_max
    MAX_ACTION_ROWS = config.file_actions_window_rows_max
    COL_0_WIDTH = 600

    @staticmethod
    def store_action_history():
        action_dicts = []
        for action in FileActionsWindow.action_history:
            action_dicts.append(action.to_dict())
        app_info_cache.set_meta("file_actions", action_dicts)
    
    @staticmethod
    def load_action_history():
        action_history_dicts = app_info_cache.get_meta("file_actions", default_val=[])
        for action_dict in action_history_dicts:
            FileActionsWindow.action_history.append(Action.from_dict(action_dict))

    @staticmethod
    def get_history_action(start_index=0, exclude_auto=True):
        # Get a previous action that is not equivalent to the permanent action if possible.
        action = None
        seen_actions = []
        for i in range(len(FileActionsWindow.action_history)):
            action = FileActionsWindow.action_history[i]
            is_returnable_action = action != FileActionsWindow.permanent_action and not (exclude_auto and action.auto)
            if not is_returnable_action or action in seen_actions:
                start_index += 1
            seen_actions.append(action)
#            logger.debug(f"i={i}, start_index={start_index}, action={action}")
            if i < start_index:
                continue
            if is_returnable_action:
                break
        return action


    @staticmethod
    def set_permanent_action(target_dir, move_func, toast_callback):
        FileActionsWindow.permanent_action = Action(move_func, target_dir, timestamp=datetime.now())
        app_info_cache.set_meta("permanent_action", move_func.__name__)
        app_info_cache.set_meta("permanent_mark_target", target_dir)
        toast_callback(f"Set permanent action:\n{move_func.__name__} to {target_dir}")


    @staticmethod
    def set_hotkey_action(number, target_dir, move_func, toast_callback):
        FileActionsWindow.hotkey_actions[number] = Action(move_func, target_dir, timestamp=datetime.now())
        hotkey_actions = app_info_cache.get_meta("hotkey_actions", default_val={})
        assert type(hotkey_actions) == dict
        hotkey_actions[number] = {"action": move_func.__name__, "target": target_dir}
        app_info_cache.set_meta("hotkey_actions", hotkey_actions)


    @staticmethod
    def update_history(latest_action):
        FileActionsWindow.action_history.insert(0, latest_action)
        if len(FileActionsWindow.action_history) > FileActionsWindow.MAX_ACTIONS:
            del FileActionsWindow.action_history[-1]

    @staticmethod
    def add_file_action(action, source, target, auto=True, overwrite_existing=False):
        # Use lock to ensure thread-safe file operations
        with Utils.file_operation_lock:
            new_filepath = str(action(source, target, overwrite_existing=overwrite_existing))
        logger.info("Moved file to " + new_filepath)
        new_action = Action(action, target, [source], [new_filepath], auto)
        FileActionsWindow.update_history(new_action)

    @staticmethod
    def get_action_statistics(today_only=False):
        """
        Calculate statistics from the action history.
        Args:
            today_only: If True, only include actions performed today
        Returns a dictionary mapping target directories to their move/copy counts.
        """
        stats = {}
        for action in FileActionsWindow.action_history:
            # Skip if filtering for today and action is not from today
            if action.auto or (today_only and not action.is_today()):
                continue
                
            target_dir = action.target
            if target_dir not in stats:
                stats[target_dir] = {"moved": 0, "copied": 0}
            
            if action.is_move_action():
                stats[target_dir]["moved"] += len(action.new_files)
            else:
                stats[target_dir]["copied"] += len(action.new_files)
        
        # Add total count for each directory
        for target_dir in stats:
            stats[target_dir]["total"] = stats[target_dir]["moved"] + stats[target_dir]["copied"]
        
        return stats

    def __init__(self, app_master, app_actions, view_image_callback, move_marks_callback, geometry="700x1200"):
        FileActionsWindow.top_level = Toplevel(app_master, bg=AppStyle.BG_COLOR)
        FileActionsWindow.top_level.title(_("File Actions"))
        FileActionsWindow.top_level.geometry(geometry)
        self.master = FileActionsWindow.top_level
        self.app_master = app_master
        self.is_sorted_by_embedding = False
        self.app_actions = app_actions
        self.view_image_callback = view_image_callback
        self.move_marks_callback = move_marks_callback
        self.filter_text = ""
        self.filtered_action_history = FileActionsWindow.action_history[:]
        self.button_index = -1
        self.show_today_only = False  # Track whether to show today's stats only

        self.label_filename_list = []
        self.label_action_list = []
        self.view_btn_list = []
        self.undo_btn_list = []
        self.modify_btn_list = []
        self.copy_filename_btn_list = []
        self.statistics_widgets = []

        self.frame = ScrollFrame(self.master, bg_color=AppStyle.BG_COLOR)
        self.frame.pack(side="top", fill="both", expand=True)

        # Setup custom button styles
        self.style = Style()
        AppStyle.setup_custom_button_styles(self.style)

        self._label_info = Label(self.frame.viewPort)
        self.add_label(self._label_info, _("File Action History"), row=0, wraplength=FileActionsWindow.COL_0_WIDTH)
        self.search_for_active_image_btn = None
        self.add_btn("search_for_active_image_btn", _("Search Image"), self.search_for_active_image, column=1)
        self.clear_action_history_btn = None
        self.add_btn("clear_action_history_btn", _("Clear History"), self.clear_action_history, column=2)
        # Note: toggle_stats_btn will be created in add_statistics_section() to be on the same row as the title

        self.add_statistics_section()
        self.add_action_history_widgets()

        self.master.bind("<Key>", self.filter_targets)
        self.master.bind("<Return>", self.do_action)
        self.master.bind("<Escape>", self.close_windows)
        self.master.bind("<Shift-A>", self.search_for_active_image)
        self.master.protocol("WM_DELETE_WINDOW", self.close_windows)
        self.frame.after(1, lambda: self.frame.focus_force())

    def add_statistics_section(self):
        """Add a statistics section at the top of the window showing move/copy counts by target directory."""
        stats = self.get_action_statistics(today_only=self.show_today_only)
        
        if not stats:
            return
        
        # Sort directories by total activity (moved + copied) in descending order
        sorted_stats = sorted(stats.items(), key=lambda x: x[1]["total"], reverse=True)
        
        # Limit to top 6 directories, with "etc." for the rest
        MAX_DISPLAY_DIRS = 6
        display_stats = sorted_stats[:MAX_DISPLAY_DIRS]
        remaining_stats = sorted_stats[MAX_DISPLAY_DIRS:]
        
        # Create statistics frame
        stats_frame = Frame(self.frame.viewPort, bg=AppStyle.BG_COLOR, relief="flat", bd=1)
        stats_frame.grid(row=1, column=0, columnspan=5, sticky="ew", padx=5, pady=(10, 5))
        self.statistics_widgets.append(stats_frame)
        
        # Statistics title and toggle button on the same row
        title_text = _("Today's File Actions") if self.show_today_only else _("File Action Statistics")
        stats_title = Label(stats_frame)
        self.add_label(stats_title, title_text, row=0, column=0, 
                       columnspan=3, sticky="nsew", justify=CENTER)
        self.statistics_widgets.append(stats_title)
        
        # Add toggle button on the same row as the title
        self.toggle_stats_btn = Button(stats_frame, text=_("All Time") if self.show_today_only else _("Today Only"), 
                                      command=self.toggle_statistics_view)
        self.toggle_stats_btn.grid(row=0, column=3, sticky="e", padx=5, pady=2)
        self.statistics_widgets.append(self.toggle_stats_btn)
        
        # Headers
        target_header = Label(stats_frame)
        self.add_label(target_header, _("Target Directory"), row=1, column=0, 
                      wraplength=150, justify=LEFT)
        target_header.grid(sticky="ew", padx=1, pady=1)
        self.statistics_widgets.append(target_header)
        
        moved_header = Label(stats_frame)
        self.add_label(moved_header, _("Moved"), row=1, column=1, 
                      wraplength=80, justify=RIGHT)
        moved_header.grid(sticky="ew", padx=1, pady=1)
        self.statistics_widgets.append(moved_header)
        
        copied_header = Label(stats_frame)
        self.add_label(copied_header, _("Copied"), row=1, column=2, 
                      wraplength=80, justify=RIGHT)
        copied_header.grid(sticky="ew", padx=1, pady=1)
        self.statistics_widgets.append(copied_header)
        
        total_header = Label(stats_frame)
        self.add_label(total_header, _("Total"), row=1, column=3, 
                      wraplength=80, justify=RIGHT)
        total_header.grid(sticky="ew", padx=1, pady=1)
        self.statistics_widgets.append(total_header)
        
        # Data rows
        for i, (target_dir, counts) in enumerate(display_stats):
            row = i + 2
            
            # Target directory (truncated for display)
            target_display = Utils.get_relative_dirpath(target_dir, levels=2)
            if len(target_display) > 30:
                target_display = Utils.get_centrally_truncated_string(target_display, 30)
            
            target_label = Label(stats_frame)
            self.add_label(target_label, target_display, row=row, column=0, 
                          wraplength=150, justify=LEFT)
            target_label.grid(padx=1, pady=1)
            self.statistics_widgets.append(target_label)
            
            # Move count
            moved_label = Label(stats_frame)
            self.add_label(moved_label, str(counts["moved"]), row=row, column=1, 
                          wraplength=80, justify=RIGHT)
            moved_label.grid(sticky="e", padx=1, pady=1)
            self.statistics_widgets.append(moved_label)
            
            # Copy count
            copied_label = Label(stats_frame)
            self.add_label(copied_label, str(counts["copied"]), row=row, column=2, 
                          wraplength=80, justify=RIGHT)
            copied_label.grid(sticky="e", padx=1, pady=1)
            self.statistics_widgets.append(copied_label)
            
            # Total count
            total_label = Label(stats_frame)
            self.add_label(total_label, str(counts["total"]), row=row, column=3, 
                          wraplength=80, justify=RIGHT)
            total_label.grid(sticky="e", padx=1, pady=1)
            self.statistics_widgets.append(total_label)
        
        # Add "etc." row if there are remaining directories
        if remaining_stats:
            row = len(display_stats) + 2
            
            # Calculate totals for remaining directories
            remaining_moved = sum(counts["moved"] for _, counts in remaining_stats)
            remaining_copied = sum(counts["copied"] for _, counts in remaining_stats)
            remaining_total = sum(counts["total"] for _, counts in remaining_stats)
            
            etc_label = Label(stats_frame)
            self.add_label(etc_label, _("... and {0} more").format(len(remaining_stats)), row=row, column=0, 
                          wraplength=150, justify=LEFT)
            etc_label.grid(padx=1, pady=1)
            self.statistics_widgets.append(etc_label)
            
            etc_moved_label = Label(stats_frame)
            self.add_label(etc_moved_label, str(remaining_moved), row=row, column=1, 
                          wraplength=80, justify=RIGHT)
            etc_moved_label.grid(sticky="e", padx=1, pady=1)
            self.statistics_widgets.append(etc_moved_label)
            
            etc_copied_label = Label(stats_frame)
            self.add_label(etc_copied_label, str(remaining_copied), row=row, column=2, 
                          wraplength=80, justify=RIGHT)
            etc_copied_label.grid(sticky="e", padx=1, pady=1)
            self.statistics_widgets.append(etc_copied_label)
            
            etc_total_label = Label(stats_frame)
            self.add_label(etc_total_label, str(remaining_total), row=row, column=3, 
                          wraplength=80, justify=RIGHT)
            etc_total_label.grid(sticky="e", padx=1, pady=1)
            self.statistics_widgets.append(etc_total_label)
        
        # Configure column weights for proper sizing
        stats_frame.columnconfigure(0, weight=3)  # Target directory gets more space
        stats_frame.columnconfigure(1, weight=1)  # Move count
        stats_frame.columnconfigure(2, weight=1)  # Copy count
        stats_frame.columnconfigure(3, weight=1)  # Total count
        
        # Add visual divider below statistics section
        divider_frame = Frame(self.frame.viewPort, bg=AppStyle.FG_COLOR, height=2)
        divider_frame.grid(row=2, column=0, columnspan=5, sticky="ew", padx=5, pady=(10, 5))
        divider_frame.grid_propagate(False)  # Maintain the height
        self.statistics_widgets.append(divider_frame)

    def add_action_history_widgets(self):
        row = 3  # Start after statistics section (rows 0-2)
        base_col = 0
        last_action = None
        for i in range(len(self.filtered_action_history)):
            row += 1
            if row > FileActionsWindow.MAX_ACTION_ROWS:
                break
            action = self.filtered_action_history[i]
            if action != last_action or len(action.new_files) != 1 or \
                    (last_action is not None and len(last_action.new_files) != 1):
                _label_target_dir = Label(self.frame.viewPort)
                self.label_filename_list.append(_label_target_dir)
                action_text = Utils.get_relative_dirpath(action.target, levels=2)
                if len(action.new_files) > 1:
                    action_text += _(" ({0} files)").format(len(action.new_files))
                if action.auto:
                    action_text += (" " + _("(auto)"))
                self.add_label(_label_target_dir, action_text, row=row, column=base_col, wraplength=FileActionsWindow.COL_0_WIDTH)

                _label_action = Label(self.frame.viewPort)
                self.label_action_list.append(_label_action)
                action_text = _("Move") if action.is_move_action() else _("Copy")
                self.add_label(_label_action, action_text, row=row, column=base_col+1, wraplength=FileActionsWindow.COL_0_WIDTH)

                undo_btn = Button(self.frame.viewPort, text=_("Undo"), style=AppStyle.HEADER_BUTTON_STYLE)
                self.undo_btn_list.append(undo_btn)
                undo_btn.grid(row=row, column=base_col+3)
                def undo_handler(event, self=self, action=action):
                    return self.undo(event, action)
                undo_btn.bind("<Button-1>", undo_handler)
                undo_btn.bind("<Return>", undo_handler)

                modify_btn = Button(self.frame.viewPort, text=_("Modify"), style=AppStyle.HEADER_BUTTON_STYLE)
                self.modify_btn_list.append(modify_btn)
                modify_btn.grid(row=row, column=base_col+4)
                def modify_handler(event, self=self, action=action):
                    return self.modify(event, action)
                modify_btn.bind("<Button-1>", modify_handler)
                modify_btn.bind("<Return>", modify_handler)
            else:
                row -= 1

            last_action = action

            for filename in action.new_files:
                row += 1
                if row > FileActionsWindow.MAX_ACTION_ROWS:
                    break
                _label_filename = Label(self.frame.viewPort)
                self.label_filename_list.append(_label_filename)
                filename_text = os.path.basename(filename)
                if len(filename_text) > 50:
                    filename_text = Utils.get_centrally_truncated_string(filename_text, 50)
                self.add_label(_label_filename, filename_text, row=row, column=base_col, wraplength=FileActionsWindow.COL_0_WIDTH)

                # _label_action = Label(self.frame.viewPort)
                # self.label_action_list.append(_label_action)
                # self.add_label(_label_action, action.action.__name__, row=row, column=base_col+1, wraplength=FileActionsWindow.COL_0_WIDTH)

                view_btn = Button(self.frame.viewPort, text=_("View"))
                self.view_btn_list.append(view_btn)
                view_btn.grid(row=row, column=base_col+1)
                def view_handler(event, self=self, image_path=filename):
                    return self.view(event, image_path)
                view_btn.bind("<Button-1>", view_handler)
                view_btn.bind("<Return>", view_handler)

                copy_filename_btn = Button(self.frame.viewPort, text=_("Copy Filename"))
                self.copy_filename_btn_list.append(copy_filename_btn)
                copy_filename_btn.grid(row=row, column=base_col+2)
                def copy_filename_handler(event, self=self, filename=filename):
                    return self.copy_filename_to_clipboard(filename)
                copy_filename_btn.bind("<Button-1>", copy_filename_handler)
                copy_filename_btn.bind("<Return>", copy_filename_handler)

                undo_btn = Button(self.frame.viewPort, text=_("Undo"))
                self.undo_btn_list.append(undo_btn)
                undo_btn.grid(row=row, column=base_col+3)
                def undo_handler1(event, self=self, image_path=filename, action=action):
                    return self.undo(event, action, specific_image=image_path)
                undo_btn.bind("<Button-1>", undo_handler1)
                undo_btn.bind("<Return>", undo_handler1)

                modify_btn = Button(self.frame.viewPort, text=_("Modify"))
                self.modify_btn_list.append(modify_btn)
                modify_btn.grid(row=row, column=base_col+4)
                def modify_handler1(event, self=self, image_path=filename):
                    return self.modify(event, image_path)
                modify_btn.bind("<Button-1>", modify_handler1)
                modify_btn.bind("<Return>", modify_handler1)

    def close_windows(self, event=None):
        self.master.destroy()

    def view(self, event, image_path):
        self.view_image_callback(master=self.app_master, image_path=image_path, app_actions=self.app_actions)

    def undo(self, event, action, specific_image=None):
        if specific_image is not None:
            if not os.path.isfile(specific_image):
                error_text = _("Image does not exist: ") + specific_image
                self.app_actions.alert(_("File Action Error"), error_text)
                raise Exception(error_text)
            if action.is_move_action():
                original_directory = action.get_original_directory()
                self.move_marks_callback(self.app_actions, target_dir=original_directory,
                                         move_func=Utils.move_file, files=[specific_image], single_image=True)
            else:
                os.remove(specific_image)
        else:
            if not action.any_new_files_exist():
                error_text = _("Images not found")
                self.app_actions.alert(_("File Action Error"), error_text)
                raise Exception(error_text)
            if action.is_move_action():
                original_directory = action.get_original_directory()
                self.move_marks_callback(self.app_actions, target_dir=original_directory,
                                         move_func=Utils.move_file, files=action.new_files,
                                         single_image=(len(action.new_files) == 1))
            else:
                action.remove_new_files()


    def modify(self, event, image_path_or_action):
        # TODO implement this
        if isinstance(image_path_or_action, str):
            pass
        else:
#            MarkedFileMover.undo_move_marks()
            pass

    def copy_filename_to_clipboard(self, filepath):
        """Copy the filename to the clipboard."""
        if not filepath:
            return
        
        filename = os.path.basename(filepath)
        self.master.clipboard_clear()
        self.master.clipboard_append(filename)
        # Optional: Show a brief notification that filename was copied
        if hasattr(self.app_actions, 'toast'):
            self.app_actions.toast(f"Copied filename: {filename}")

    def _refresh_widgets(self):
        self.clear_widget_lists()
        self.add_action_history_widgets()
        self.add_statistics_section()
        self.master.update()

    def clear_widget_lists(self):
        for label in self.label_filename_list:
            label.destroy()
        for label in self.label_action_list:
            label.destroy()
        for btn in self.view_btn_list:
            btn.destroy()
        for btn in self.undo_btn_list:
            btn.destroy()
        for btn in self.modify_btn_list:
            btn.destroy()
        for btn in self.copy_filename_btn_list:
            btn.destroy()
        for widget in self.statistics_widgets:
            widget.destroy()
        self.label_filename_list = []
        self.label_action_list = []
        self.view_btn_list = []
        self.undo_btn_list = []
        self.modify_btn_list = []
        self.copy_filename_btn_list = []
        self.statistics_widgets = []

    def _get_paging_length(self):
        return max(1, int(len(self.filtered_action_history) / 10))

    def page_up(self, event=None):
        paging_len = self._get_paging_length()
        idx = len(self.filtered_action_history) - paging_len
        self.filtered_action_history = self.filtered_action_history[idx:] + self.filtered_action_history[:idx]
        self._refresh_widgets()

    def page_down(self, event=None):
        paging_len = self._get_paging_length()
        self.filtered_action_history = self.filtered_action_history[paging_len:] + self.filtered_action_history[:paging_len]
        self._refresh_widgets()

    def filter_targets(self, event):
        """
        Rebuild the filtered target directories list based on the filter string and update the UI.
        """
        modifier_key_pressed = (event.state & 0x1) != 0 or (event.state & 0x4) != 0 # Do not filter if modifier key is down
        if modifier_key_pressed:
            return
        if len(event.keysym) > 1:
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
                logger.info("Filter unset")
            # Restore the list of target directories to the full list
            if self.show_today_only:
                self.filtered_action_history = [action for action in FileActionsWindow.action_history if action.is_today()]
            else:
                self.filtered_action_history = FileActionsWindow.action_history[:]
        else:
            if self.show_today_only:
                actions = [action for action in FileActionsWindow.action_history if action.is_today()]
            else:
                actions = FileActionsWindow.action_history[:]
            temp = []
            # First pass try to match directory basename
            for action in actions:
                basename = os.path.basename(os.path.normpath(action.target))
                if basename.lower() == self.filter_text:
                    temp.append(action)
            for action in actions:
                if not Action._is_matching_action_in_list(temp, action):
                    basename = os.path.basename(os.path.normpath(action.target))
                    if basename.lower().startswith(self.filter_text):
                        temp.append(action)
            # Second pass try to match parent directory name, so these will appear after
            for action in actions:
                if not Action._is_matching_action_in_list(temp, action):
                    dirname = os.path.basename(os.path.dirname(os.path.normpath(action.target)))
                    if dirname and dirname.lower().startswith(self.filter_text):
                        temp.append(action)
            # Third pass try to match part of the basename
            for action in actions:
                if not Action._is_matching_action_in_list(temp, action):
                    basename = os.path.basename(os.path.normpath(action.target))
                    if basename and (f" {self.filter_text}" in basename.lower() or f"_{self.filter_text}" in basename.lower()):
                        temp.append(action)
            self.filtered_action_history = temp[:]

        self._refresh_widgets()

    def do_action(self, event):
        """
        The user has requested to do something with the saved file actions. Based on the context, figure out what to do.

        If no actions present, do nothing.

        If actions set, open the image of the first action.

        If shift key pressed, undo the first action.

        If control key pressed, modify the first action.

        If alt key pressed, use the penultimate mark target dir as target directory.

        The idea is the user can filter the actions using keypresses, then press enter to
        do the action on the first filtered action.
        """
        shift_key_pressed, control_key_pressed, alt_key_pressed = Utils.modifier_key_pressed(
            event, keys_to_check=[ModifierKey.SHIFT, ModifierKey.CTRL, ModifierKey.ALT])
        move_func = Utils.copy_file if shift_key_pressed else Utils.move_file
        if len(self.filtered_action_history) == 0:
            return
        if len(self.filtered_action_history) != 1 and self.filter_text.strip() == "":
            return
        action = self.filtered_action_history[0]
        if alt_key_pressed:
            self.undo(event=None, action=action)
        elif control_key_pressed:
            self.modify(event=None, image_path_or_action=action)
        else:
            self.view(event=None, image_path=action.new_files[0])

    def search_for_active_image(self, event=None):
        self._search_for_image(event=event)

    def _search_for_image(self, event=None, image_path=None):
        if image_path is None:
            image_path = self.app_actions.get_active_media_filepath()
            if image_path is None:
                raise Exception("No active image")
        image_path = os.path.normpath(image_path)
        search_basename = os.path.basename(image_path).lower()
        basename_no_ext = os.path.splitext(search_basename)[0].lower()
        temp = []
        for action in FileActionsWindow.action_history:
            for f in action.new_files:
                if f == image_path:
                    temp.append(action)
                    break
        for action in FileActionsWindow.action_history:
            if action not in temp:
                for f in action.new_files:
                    basename = os.path.basename(os.path.normpath(f))
                    if basename.lower() == search_basename:
                        temp.append(action)
                        break
        for action in FileActionsWindow.action_history:
            if action not in temp:
                for f in action.new_files:
                    basename = os.path.basename(os.path.normpath(f))
                    if basename.lower().startswith(basename_no_ext):
                        temp.append(action)
                        break
        self.filtered_action_history = temp[:]
        self._refresh_widgets()

    def clear_action_history(self):
        FileActionsWindow.action_history = []
        self.filtered_action_history = []
        self._refresh_widgets()

    def toggle_statistics_view(self):
        """Toggle between showing all-time statistics and today's statistics only."""
        self.show_today_only = not self.show_today_only
        
        # Update button text
        if self.show_today_only:
            self.toggle_stats_btn.config(text=_("All Time"))
        else:
            self.toggle_stats_btn.config(text=_("Today Only"))
        
        # Refresh the statistics section
        self._refresh_widgets()

    def add_label(self, label_ref, text, row=0, column=0, columnspan=1, wraplength=500, sticky=W, justify=LEFT):
        label_ref['text'] = text
        label_ref.grid(column=column, row=row, columnspan=columnspan, sticky=sticky)
        label_ref.config(wraplength=wraplength, justify=justify, bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)

    def add_btn(self, button_ref_name, text, command, row=0, column=0):
        if getattr(self, button_ref_name) is None:
            button = Button(master=self.frame.viewPort, text=text, command=command)
            setattr(self, button_ref_name, button)
            button # for some reason this is necessary to maintain the reference?
            button.grid(row=row, column=column)
