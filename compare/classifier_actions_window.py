from enum import Enum
import os
from typing import Optional

from tkinter import Frame, Label, Scale, Checkbutton, BooleanVar, StringVar, LEFT, W, HORIZONTAL, Scrollbar, Listbox, BOTH, RIGHT, TOP, E
import tkinter.font as fnt
from tkinter.ttk import Entry, Button, Combobox

from compare.classifier_actions_manager import ClassifierAction, ClassifierActionsManager
from compare.classifier_management_window import ClassifierActionModifyWindow
from compare.directory_profile import DirectoryProfile
from image.classifier_action_type import ClassifierActionType
from image.image_classifier_manager import image_classifier_manager
from lib.multiselect_dropdown import MultiSelectDropdown
from lib.multi_display import SmartToplevel
from utils.app_style import AppStyle
from utils.config import config
from utils.logging_setup import get_logger
from utils.translations import I18N

_ = I18N._
logger = get_logger("classifier_actions_window")


class ClassifierActionsTab:
    """
    Tab content class for managing classifier actions.
    Can be used either standalone (as ClassifierActionsWindow) or as a tab in a notebook.
    """
    classifier_action_modify_window: Optional[ClassifierActionModifyWindow] = None
    # classifier_actions list is now managed by ClassifierActionsManager

    MAX_HEIGHT = 900
    COL_0_WIDTH = 600
    BATCH_VALIDATION_MAX_IMAGES = 40000  # Maximum number of images to process in batch prototype validation

    @staticmethod
    def _is_modify_window_valid() -> bool:
        """Check if the classifier action modify window still exists and is valid."""
        if ClassifierActionsTab.classifier_action_modify_window is None:
            return False
        try:
            return (hasattr(ClassifierActionsTab.classifier_action_modify_window, 'top_level') and
                    ClassifierActionsTab.classifier_action_modify_window.top_level is not None and
                    ClassifierActionsTab.classifier_action_modify_window.top_level.winfo_exists())
        except Exception:
            # Window was destroyed, clear the reference
            ClassifierActionsTab.classifier_action_modify_window = None
            return False

    @staticmethod
    def run_classifier_action(classifier_action: ClassifierAction, directory_paths: list[str],
                              hide_callback, notify_callback, add_mark_callback=None,
                              profile_name_or_path: Optional[str] = None):
        """
        Run a classifier action on all images in the specified directories.
        
        Args:
            classifier_action: The ClassifierAction to run
            directory_paths: List of directory paths to process
            hide_callback: Callback for hiding images
            notify_callback: Callback for notifications
            add_mark_callback: Optional callback for marking images
            profile_name_or_path: Optional profile name or directory path to store as last used
        """
        classifier_action.run(directory_paths, hide_callback, notify_callback, add_mark_callback, profile_name_or_path, ClassifierActionsTab.BATCH_VALIDATION_MAX_IMAGES)

    def __init__(self, parent_frame, app_actions):
        """
        Initialize the classifier actions tab.
        
        Args:
            parent_frame: Parent frame (can be a Toplevel or a Frame in a notebook)
            app_actions: Application actions object
        """
        self.app_actions = app_actions
        self.filter_text = ""
        self.filtered_classifier_actions = ClassifierActionsManager.classifier_actions[:]
        self.label_list = []
        self.label_list2 = []
        self.is_active_list = []
        self.is_active_var_list = []
        self.set_classifier_action_btn_list = []
        self.modify_classifier_action_btn_list = []
        self.delete_classifier_action_btn_list = []
        self.run_classifier_action_btn_list = []
        self.move_down_btn_list = []

        # Use parent_frame directly (works for both standalone and tab usage)
        self.frame = parent_frame
        self.master = parent_frame.winfo_toplevel()  # Get the top-level window for StringVar
        
        self.frame.columnconfigure(0, weight=9)
        self.frame.columnconfigure(1, weight=1)
        self.frame.columnconfigure(2, weight=1)
        self.frame.columnconfigure(3, weight=1)
        self.frame.columnconfigure(4, weight=1)
        self.frame.columnconfigure(5, weight=1)
        self.frame.columnconfigure(6, weight=1)
        self.frame.config(bg=AppStyle.BG_COLOR)
        
        # Classifier Actions section title
        self.classifier_actions_title = Label(self.frame, text=_("Classifier Actions"), 
                                         bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR, 
                                         font=fnt.Font(size=config.font_size + 2, weight="bold"))
        self.classifier_actions_title.grid(row=0, column=0, columnspan=4, sticky=W, pady=(20, 10))
        
        self.add_classifier_action_btn = None
        self.add_btn("add_classifier_action_btn", _("Add Classifier Action"), self.open_classifier_action_modify_window, row=0, column=1)
        self.clear_recent_classifier_actions_btn = None
        self.add_btn("clear_recent_classifier_actions_btn", _("Clear Classifier Actions"), self.clear_recent_classifier_actions, row=0, column=2)
        
        # Profile selection at window level
        row = 1
        self.label_profile = Label(self.frame, text=_("Run on Profile:"), 
                                  bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR, 
                                  font=fnt.Font(size=config.font_size))
        self.label_profile.grid(row=row, column=0, sticky=W, padx=2, pady=5)
        
        profile_options = [profile.name for profile in DirectoryProfile.directory_profiles]
        self.selected_profile_var = StringVar(self.master, value=profile_options[0] if profile_options else "")
        self.profile_choice = Combobox(self.frame, textvariable=self.selected_profile_var, values=profile_options, width=47,
                                       font=fnt.Font(size=config.font_size))
        if profile_options:
            self.profile_choice.current(0)
        else:
            self.profile_choice.config(state="disabled")
        self.profile_choice.grid(row=row, column=1, sticky=W, padx=2, pady=5)
        AppStyle.setup_combobox_style(self.profile_choice)

        self.add_classifier_action_widgets()

        self.frame.update()



    def add_classifier_action_widgets(self):
        # Start at row 2: after title row (0) and profile selection (1)
        row = 2
        base_col = 0
        
        # Add header row
        header_font = fnt.Font(size=config.font_size, weight="bold")
        header_name = Label(self.frame, text=_("Name"), bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR, font=header_font)
        header_name.grid(row=row, column=base_col, sticky=W, padx=2, pady=2)
        
        header_action = Label(self.frame, text=_("Action"), bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR, font=header_font)
        header_action.grid(row=row, column=base_col + 1, sticky=W, padx=2, pady=2)
        
        header_active = Label(self.frame, text=_("Active"), bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR, font=header_font)
        header_active.grid(row=row, column=base_col + 2, sticky=W, padx=2, pady=2)
        
        row += 1  # Move to first data row
        
        for i, classifier_action in enumerate(self.filtered_classifier_actions):
            row = 3 + i  # Start data rows at row 3 (after header at row 2)
            label_name = Label(self.frame)
            self.label_list.append(label_name)
            self.add_label(label_name, str(classifier_action), row=row, column=base_col, wraplength=ClassifierActionsTab.COL_0_WIDTH)

            label_action = Label(self.frame)
            self.label_list2.append(label_action)
            self.add_label(label_action, classifier_action.action.get_translation(), row=row, column=base_col + 1)
            
            is_active_var = BooleanVar(value=classifier_action.is_active)
            def set_is_active_handler(classifier_action=classifier_action, var=is_active_var):
                classifier_action.is_active = var.get()
                logger.info(f"Set {classifier_action} to active: {classifier_action.is_active}")
            is_active_box = Checkbutton(self.frame, variable=is_active_var, font=fnt.Font(size=config.font_size), command=set_is_active_handler)
            is_active_box.grid(row=row, column=base_col + 2, sticky=(W))
            self.is_active_list.append(is_active_box)
            self.is_active_var_list.append(is_active_var)

            modify_classifier_action_btn = Button(self.frame, text=_("Modify"))
            self.modify_classifier_action_btn_list.append(modify_classifier_action_btn)
            modify_classifier_action_btn.grid(row=row, column=base_col+3)
            def modify_classifier_action_handler(event, self=self, classifier_action=classifier_action):
                return self.open_classifier_action_modify_window(event, classifier_action)
            modify_classifier_action_btn.bind("<Button-1>", modify_classifier_action_handler)

            delete_classifier_action_btn = Button(self.frame, text=_("Delete"))
            self.delete_classifier_action_btn_list.append(delete_classifier_action_btn)
            delete_classifier_action_btn.grid(row=row, column=base_col+4)
            def delete_classifier_action_handler(event, self=self, classifier_action=classifier_action):
                return self.delete_classifier_action(event, classifier_action)
            delete_classifier_action_btn.bind("<Button-1>", delete_classifier_action_handler)

            run_classifier_action_btn = Button(self.frame, text=_("Run"))
            self.run_classifier_action_btn_list.append(run_classifier_action_btn)
            run_classifier_action_btn.grid(row=row, column=base_col+5)
            def run_classifier_action_handler(event, self=self, classifier_action=classifier_action):
                return self.run_classifier_action_event(event, classifier_action)
            run_classifier_action_btn.bind("<Button-1>", run_classifier_action_handler)

            move_down_btn = Button(self.frame, text=_("Move down"))
            self.move_down_btn_list.append(move_down_btn)
            move_down_btn.grid(row=row, column=base_col+6)
            def move_down_handler(event, self=self, idx=i, classifier_action=classifier_action):
                classifier_action.move_index(idx, 1)
                self.refresh()
            move_down_btn.bind("<Button-1>", move_down_handler)

    def open_classifier_action_modify_window(self, event=None, classifier_action=None):
        # Check if existing window is still valid before trying to destroy it
        if ClassifierActionsTab._is_modify_window_valid():
            try:
                ClassifierActionsTab.classifier_action_modify_window.master.destroy()
            except Exception:
                # Window was already destroyed, clear the reference
                ClassifierActionsTab.classifier_action_modify_window = None
        ClassifierActionsTab.classifier_action_modify_window = ClassifierActionModifyWindow(
            self.master, self.app_actions, self.refresh_classifier_actions, classifier_action)

    def refresh_classifier_actions(self, classifier_action):
        # Check if this is a new classifier action, if so, insert it at the start
        if classifier_action not in ClassifierActionsManager.classifier_actions:
            ClassifierActionsManager.classifier_actions.insert(0, classifier_action)
        self.filtered_classifier_actions = ClassifierActionsManager.classifier_actions[:]
        self.refresh()

    def delete_classifier_action(self, event=None, classifier_action=None):
        if classifier_action is not None and classifier_action in ClassifierActionsManager.classifier_actions:
            ClassifierActionsManager.classifier_actions.remove(classifier_action)
        self.refresh()

    def run_classifier_action_event(self, event=None, classifier_action=None):
        """Run the specified classifier action on the selected profile directories."""
        if classifier_action is None:
            return
        
        # Get selected profile
        selected_profile_name = self.selected_profile_var.get().strip()
        if not selected_profile_name:
            logger.error("No profile selected")
            return
        
        selected_profile = DirectoryProfile.get_profile_by_name(selected_profile_name)
        if selected_profile is None:
            logger.error(f"Profile {selected_profile_name} not found")
            return
        
        # Confirm with user
        from tkinter import messagebox
        from collections import defaultdict
        
        directories = selected_profile.directories
        if len(directories) > 10:
            # Group directories by parent directory
            parent_counts = defaultdict(int)
            for directory in directories:
                parent_dir = os.path.dirname(directory)
                parent_counts[parent_dir] += 1
            
            # Format parent directory counts
            directory_list = "\n".join([f"{parent} - {count} " + _("directories") for parent, count in sorted(parent_counts.items())])
        else:
            # List all directories individually
            directory_list = "\n".join([f"  - {d}" for d in directories])
        
        # Separate translatable message from directory list
        message = _("Run classifier action '{0}' on the following directories?").format(classifier_action.name)
        full_message = f"{message}\n\n{directory_list}"
        
        res = messagebox.askokcancel(
            _("Run Classifier Action"),
            full_message
        )
        
        if res:
            # Import callbacks from app_actions
            hide_callback = self.app_actions.hide_current_media if hasattr(self.app_actions, 'hide_current_media') else None
            notify_callback = self.app_actions.title_notify if hasattr(self.app_actions, 'title_notify') else None
            add_mark_callback = None
            try:
                from files.marked_file_mover import MarkedFiles
                add_mark_callback = MarkedFiles.add_mark_if_not_present
            except ImportError:
                pass
            
            ClassifierActionsTab.run_classifier_action(
                classifier_action,
                selected_profile.directories,
                hide_callback,
                notify_callback,
                add_mark_callback,
                selected_profile_name  # Pass profile name to store as last used
            )

    def clear_recent_classifier_actions(self, event=None):
        self.clear_widget_lists()
        ClassifierActionsManager.classifier_actions.clear()
        self.filtered_classifier_actions.clear()
        self.add_classifier_action_widgets()
        self.master.update()

    def clear_widget_lists(self):
        for label in self.label_list:
            label.destroy()
        for label in self.label_list2:
            label.destroy()
        for chkbtn in self.is_active_list:
            chkbtn.destroy()
        for btn in self.modify_classifier_action_btn_list:
            btn.destroy()
        for btn in self.delete_classifier_action_btn_list:
            btn.destroy()
        for btn in self.run_classifier_action_btn_list:
            btn.destroy()
        for btn in self.move_down_btn_list:
            btn.destroy()
        # Note: Don't destroy classifier_actions_title, label_profile, or profile_choice as they're persistent UI elements
        self.label_list = []
        self.label_list2 = []
        self.is_active_list = []
        self.is_active_var_list = []
        self.modify_classifier_action_btn_list = []
        self.delete_classifier_action_btn_list = []
        self.run_classifier_action_btn_list = []
        self.move_down_btn_list = []

    def refresh(self, refresh_list=True):
        # Update profile dropdown
        if hasattr(self, 'profile_choice'):
            profile_options = [profile.name for profile in DirectoryProfile.directory_profiles]
            current_value = self.selected_profile_var.get()
            self.profile_choice['values'] = profile_options
            if profile_options:
                self.profile_choice.config(state="normal")
                if current_value in profile_options:
                    self.profile_choice.current(profile_options.index(current_value))
                else:
                    self.profile_choice.current(0)
                    self.selected_profile_var.set(profile_options[0])
            else:
                self.profile_choice.config(state="disabled")
                self.selected_profile_var.set("")
        
        self.filtered_classifier_actions = ClassifierActionsManager.classifier_actions[:]
        self.clear_widget_lists()
        self.add_classifier_action_widgets()
        self.master.update()

    def close_windows(self, event=None):
        self.master.destroy()

    def add_label(self, label_ref, text, row=0, column=0, wraplength=500):
        label_ref['text'] = text
        label_ref.grid(column=column, row=row, sticky=W)
        label_ref.config(wraplength=wraplength, justify=LEFT, bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR, font=fnt.Font(size=config.font_size))

    def add_btn(self, button_ref_name, text, command, row=0, column=0):
        if getattr(self, button_ref_name) is None:
            button = Button(master=self.frame, text=text, command=command)
            setattr(self, button_ref_name, button)
            button # for some reason this is necessary to maintain the reference?
            button.grid(row=row, column=column)

