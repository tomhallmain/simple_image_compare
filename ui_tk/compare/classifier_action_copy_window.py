"""
Window for copying ClassifierAction and Prevalidation objects.

This module provides an intermediary window that allows users to copy
ClassifierAction and Prevalidation objects into new instances of either type.
"""

from tkinter import Frame, Label, StringVar, LEFT, W
from tkinter.ttk import Button, Combobox, Entry
import tkinter.font as fnt

from compare.classifier_actions_manager import ClassifierAction, Prevalidation, ClassifierActionsManager
from lib.multi_display import SmartToplevel
from ui_tk.compare.classifier_management_window import ClassifierActionModifyWindow, ClassifierManagementWindow
from utils.constants import ClassifierActionClass
from utils.app_style import AppStyle
from utils.config import config
from utils.translations import I18N

_ = I18N._


class ClassifierActionCopyWindow:
    """
    Intermediary window for copying ClassifierAction and Prevalidation objects.
    
    Allows users to:
    - Copy ClassifierAction -> new ClassifierAction
    - Copy Prevalidation -> new Prevalidation
    - Copy ClassifierAction -> new Prevalidation
    - Copy Prevalidation -> new ClassifierAction
    """
    top_level = None
    COL_0_WIDTH = 400

    def __init__(self, master, app_actions, source_item, source_type="auto", 
                 refresh_classifier_actions_callback=None, refresh_prevalidations_callback=None):
        """
        Initialize the copy window.
        
        Args:
            master: Parent window
            app_actions: Application actions object
            source_item: The ClassifierAction or Prevalidation to copy from
            source_type: "auto" (detect from instance), "classifier_action", or "prevalidation"
            refresh_classifier_actions_callback: Optional callback to refresh classifier actions tab
            refresh_prevalidations_callback: Optional callback to refresh prevalidations tab
        """
        self.top_level = SmartToplevel(
            persistent_parent=master,
            title=_("Copy Classifier Action / Prevalidation"),
            geometry="500x300"
        )
        ClassifierActionCopyWindow.top_level = self.top_level
        self.master = self.top_level
        self.app_actions = app_actions
        self.source_item = source_item
        self.refresh_classifier_actions_callback = refresh_classifier_actions_callback
        self.refresh_prevalidations_callback = refresh_prevalidations_callback
        
        # Detect source type if auto
        if source_type == "auto":
            if isinstance(source_item, Prevalidation):
                self.source_type = ClassifierActionClass.PREVALIDATION
            elif isinstance(source_item, ClassifierAction):
                self.source_type = ClassifierActionClass.CLASSIFIER_ACTION
            else:
                raise ValueError(f"Unknown source item type: {type(source_item)}")
        else:
            self.source_type = ClassifierActionClass.from_key(source_type)

        self.frame = Frame(self.master)
        self.frame.grid(column=0, row=0, padx=10, pady=10)
        self.frame.config(bg=AppStyle.BG_COLOR)
        self.frame.columnconfigure(0, weight=1)
        self.frame.columnconfigure(1, weight=1)

        self.row = 0

        # Source information
        self._source_header = Label(self.frame, bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
        self.add_label(self._source_header, _("Copying from:"), row=self.row, column=0, wraplength=self.COL_0_WIDTH)
        self._source_header.config(font=fnt.Font(size=config.font_size, weight="bold"))
        self.frame.rowconfigure(self.row, minsize=8)
        self.row += 1

        self._source_name_label = Label(self.frame, bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
        self.add_label(
            self._source_name_label,
            f"{_('Name')}: {self.source_item.name}",
            row=self.row, column=0, wraplength=self.COL_0_WIDTH
        )
        self.row += 1

        self._source_type_label = Label(self.frame, bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
        self.add_label(
            self._source_type_label,
            f"{_('Type')}: {self.source_type.get_display_value()}",
            row=self.row, column=0, wraplength=self.COL_0_WIDTH
        )
        self.row += 1

        # Spacer
        Label(self.frame, bg=AppStyle.BG_COLOR).grid(row=self.row, column=0, pady=10)
        self.row += 1

        # Target type selection
        self._target_header = Label(self.frame, bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
        self.add_label(self._target_header, _("Copy to:"), row=self.row, column=0, wraplength=self.COL_0_WIDTH)
        self._target_header.config(font=fnt.Font(size=config.font_size, weight="bold"))
        self.row += 1

        self._target_type_label = Label(self.frame, bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
        self.add_label(self._target_type_label, _("Target Type:"), row=self.row, column=0, wraplength=self.COL_0_WIDTH)

        target_type_options = [
            ClassifierActionClass.CLASSIFIER_ACTION.get_display_value(),
            ClassifierActionClass.PREVALIDATION.get_display_value(),
        ]
        self.target_type_var = StringVar(self.master)
        self.target_type_var.set(self.source_type.get_display_value())

        self.target_type_combobox = Combobox(
            self.frame,
            textvariable=self.target_type_var,
            values=target_type_options,
            state="readonly",
            width=30,
            font=fnt.Font(size=config.font_size)
        )
        self.target_type_combobox.grid(row=self.row, column=1, sticky=W, padx=2, pady=2)
        AppStyle.setup_combobox_style(self.target_type_combobox)
        self.row += 1

        # New name
        self._new_name_label = Label(self.frame, bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
        self.add_label(self._new_name_label, _("New Name:"), row=self.row, column=0, wraplength=self.COL_0_WIDTH)

        default_name = self._generate_default_name()
        self.new_name_var = StringVar(self.master, value=default_name)
        self.new_name_entry = Entry(
            self.frame,
            textvariable=self.new_name_var,
            width=30,
            font=fnt.Font(size=config.font_size)
        )
        self.new_name_entry.grid(row=self.row, column=1, sticky=W, padx=2, pady=2)
        self.row += 1

        # Spacer
        Label(self.frame, bg=AppStyle.BG_COLOR).grid(row=self.row, column=0, pady=10)
        self.row += 1

        # Buttons (grid, not pack)
        self.copy_btn = None
        self.add_btn("copy_btn", _("Copy"), self.copy_item, row=self.row, column=0)
        self.cancel_btn = None
        self.add_btn("cancel_btn", _("Cancel"), self.close_window, row=self.row, column=1)

        # Bind Enter key to copy
        self.master.bind("<Return>", lambda e: self.copy_item())
        self.master.bind("<Escape>", lambda e: self.close_window())
        
        # Focus on name entry
        self.new_name_entry.focus()
        self.new_name_entry.select_range(0, "end")

        self.master.update()

    def add_label(self, label_ref, text, row=0, column=0, wraplength=500):
        """Add a label to the frame."""
        label_ref['text'] = text
        label_ref.grid(column=column, row=row, sticky=W)
        label_ref.config(wraplength=wraplength, justify=LEFT, bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR, font=fnt.Font(size=config.font_size))

    def add_btn(self, button_ref_name, text, command, row=0, column=0):
        """Add a button to the frame."""
        if getattr(self, button_ref_name) is None:
            button = Button(master=self.frame, text=text, command=command)
            setattr(self, button_ref_name, button)
            button.grid(row=row, column=column, padx=2, pady=2)

    def _generate_default_name(self):
        """Generate a default name for the copied item."""
        source_name = self.source_item.name
        # Try to append " Copy" or " Copy 2", etc.
        if " Copy" in source_name:
            # Already has " Copy", try to increment
            base_name = source_name.rsplit(" Copy", 1)[0]
            copy_num = 2
            while True:
                new_name = f"{base_name} Copy {copy_num}"
                # Check if name exists in target type
                target_class = ClassifierActionClass.from_display_value(self.target_type_var.get())
                existing_names = (
                    [pv.name for pv in ClassifierActionsManager.prevalidations]
                    if target_class == ClassifierActionClass.PREVALIDATION
                    else [ca.name for ca in ClassifierActionsManager.classifier_actions]
                )
                if new_name not in existing_names:
                    return new_name
                copy_num += 1
        else:
            # Add " Copy"
            new_name = f"{source_name} Copy"
            target_class = ClassifierActionClass.from_display_value(self.target_type_var.get())
            existing_names = (
                [pv.name for pv in ClassifierActionsManager.prevalidations]
                if target_class == ClassifierActionClass.PREVALIDATION
                else [ca.name for ca in ClassifierActionsManager.classifier_actions]
            )
            if new_name not in existing_names:
                return new_name

            copy_num = 2
            while True:
                new_name = f"{source_name} Copy {copy_num}"
                if new_name not in existing_names:
                    return new_name
                copy_num += 1

    def copy_item(self):
        """Copy the source item to a new item of the selected type."""
        new_name = self.new_name_var.get().strip()
        if not new_name:
            from tkinter import messagebox
            messagebox.showerror(_("Error"), _("Name cannot be empty"))
            return

        target_class = ClassifierActionClass.from_display_value(self.target_type_var.get())

        # Check if name already exists
        existing_names = (
            [pv.name for pv in ClassifierActionsManager.prevalidations]
            if target_class == ClassifierActionClass.PREVALIDATION
            else [ca.name for ca in ClassifierActionsManager.classifier_actions]
        )
        if new_name in existing_names:
            from tkinter import messagebox
            messagebox.showerror(
                _("Error"),
                _("A {0} with this name already exists").format(target_class.get_display_value().lower())
            )
            return
        
        # Create copy based on source item's dictionary representation
        source_dict = self.source_item.to_dict()
        source_dict["name"] = new_name
        
        # Create new item based on target type
        if target_class == ClassifierActionClass.PREVALIDATION:
            # Copying to Prevalidation
            if isinstance(self.source_item, Prevalidation):
                # Prevalidation -> Prevalidation: use from_dict
                new_item = Prevalidation.from_dict(source_dict)
            else:
                # ClassifierAction -> Prevalidation: need to add prevalidation-specific fields
                if "profile_name" not in source_dict:
                    source_dict["profile_name"] = None
                new_item = Prevalidation.from_dict(source_dict)
        else:
            # Copying to ClassifierAction
            if isinstance(self.source_item, Prevalidation):
                # Prevalidation -> ClassifierAction: remove prevalidation-specific fields
                source_dict.pop("profile_name", None)
                new_item = ClassifierAction.from_dict(source_dict)
            else:
                # ClassifierAction -> ClassifierAction: use from_dict
                new_item = ClassifierAction.from_dict(source_dict)

        # Add the new item to the appropriate list
        if target_class == ClassifierActionClass.PREVALIDATION:
            # Add to prevalidations list
            if new_item not in ClassifierActionsManager.prevalidations:
                ClassifierActionsManager.prevalidations.insert(0, new_item)
            
            # Close copy window
            self.close_window()
            
            # Lazy import to avoid circular import
            from compare.prevalidations_tab import PrevalidationModifyWindow, PrevalidationsTab
            
            # Open prevalidation modify window
            if PrevalidationsTab.prevalidation_modify_window is not None:
                try:
                    PrevalidationsTab.prevalidation_modify_window.master.destroy()
                except:
                    pass
            
            # Use provided callback or try to get from management window
            refresh_callback = self.refresh_prevalidations_callback or self._get_prevalidations_refresh_callback()
            PrevalidationsTab.prevalidation_modify_window = PrevalidationModifyWindow(
                self.master, self.app_actions, refresh_callback, new_item
            )
        else:
            # Add to classifier actions list
            if new_item not in ClassifierActionsManager.classifier_actions:
                ClassifierActionsManager.classifier_actions.insert(0, new_item)
            
            # Close copy window
            self.close_window()
            
            # Lazy import to avoid circular import
            from compare.classifier_actions_tab import ClassifierActionsTab
            
            # Open classifier action modify window
            if ClassifierActionsTab.classifier_action_modify_window is not None:
                try:
                    ClassifierActionsTab.classifier_action_modify_window.master.destroy()
                except:
                    pass
            
            # Use provided callback or try to get from management window
            refresh_callback = self.refresh_classifier_actions_callback or self._get_classifier_actions_refresh_callback()
            ClassifierActionsTab.classifier_action_modify_window = ClassifierActionModifyWindow(
                self.master, self.app_actions, refresh_callback, new_item
            )

    def _get_prevalidations_refresh_callback(self):
        """Get refresh callback for prevalidations tab from management window if available."""
        def refresh_callback(prevalidation):
            # Check if this is a new prevalidation, if so, insert it at the start
            if prevalidation not in ClassifierActionsManager.prevalidations:
                ClassifierActionsManager.prevalidations.insert(0, prevalidation)
            
            # Try to refresh the prevalidations tab if management window exists
            try:
                if (ClassifierManagementWindow.instance is not None and
                    hasattr(ClassifierManagementWindow.instance, 'prevalidations_tab')):
                    ClassifierManagementWindow.instance.prevalidations_tab.refresh_prevalidations(prevalidation)
            except Exception:
                pass
        
        return refresh_callback
    
    def _get_classifier_actions_refresh_callback(self):
        """Get refresh callback for classifier actions tab from management window if available."""
        def refresh_callback(classifier_action):
            # Check if this is a new classifier action, if so, insert it at the start
            if classifier_action not in ClassifierActionsManager.classifier_actions:
                ClassifierActionsManager.classifier_actions.insert(0, classifier_action)
            
            # Try to refresh the classifier actions tab if management window exists
            try:
                if (ClassifierManagementWindow.instance is not None and
                    hasattr(ClassifierManagementWindow.instance, 'classifier_actions_tab')):
                    ClassifierManagementWindow.instance.classifier_actions_tab.refresh_classifier_actions(classifier_action)
            except Exception:
                pass
        
        return refresh_callback

    def close_window(self):
        """Close the copy window."""
        self.master.destroy()
