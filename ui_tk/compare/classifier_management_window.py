"""
Main window for managing classifier actions and prevalidations with tabbed interface.

This module provides a unified window with notebook tabs for switching between
classifier actions and prevalidations management.
"""

import os
from tkinter import Frame, Label, Scale, Checkbutton, BooleanVar, StringVar, LEFT, W, HORIZONTAL, BOTH, E
from tkinter.ttk import Notebook, Entry, Button, Combobox
import tkinter.font as fnt

from compare.classifier_actions_manager import ClassifierAction, ClassifierActionsManager
from image.image_classifier_manager import image_classifier_manager
from lib.multiselect_dropdown import MultiSelectDropdown
from lib.multi_display import SmartToplevel
from lib.tooltip import create_tooltip
from utils.app_style import AppStyle
from utils.config import config
from utils.constants import ClassifierActionType
from utils.translations import I18N

_ = I18N._


class ClassifierActionModifyWindow:
    """
    Base class for classifier action and prevalidation modify windows.
    Contains all common UI elements and functionality including prototype support.
    """
    top_level = None
    COL_0_WIDTH = 600
    
    def __init__(self, master, app_actions, refresh_callback, classifier_action, 
                 window_title=None, name_label_text=None, new_name_default=None, dimensions="600x600"):
        """
        Initialize the base modify window.
        
        Args:
            master: Parent window
            app_actions: Application actions object
            refresh_callback: Callback to refresh parent window
            classifier_action: ClassifierAction or Prevalidation instance
            window_title: Window title string (optional, defaults based on classifier_action type)
            name_label_text: Label text for the name field (optional, defaults based on classifier_action type)
            new_name_default: Default name for new items (optional, defaults based on classifier_action type)
            dimensions: Window dimensions string
        """
        # Set defaults if not provided (for backward compatibility)
        if window_title is None:
            from compare.classifier_actions_manager import Prevalidation
            if isinstance(classifier_action, Prevalidation):
                window_title = _("Modify Prevalidation")
                name_label_text = _("Prevalidation Name")
                new_name_default = _("New Prevalidation")
            else:
                window_title = _("Modify Classifier Action")
                name_label_text = _("Classifier Action Name")
                new_name_default = _("New Classifier Action")
        
        self.top_level = SmartToplevel(persistent_parent=master, geometry=dimensions)
        ClassifierActionModifyWindow.top_level = self.top_level
        self.master = self.top_level
        self.app_actions = app_actions
        self.refresh_callback = refresh_callback
        self.classifier_action = classifier_action
        self.top_level.title(window_title + f": {self.classifier_action.name}")

        # Ensure image classifier is loaded for UI display
        if hasattr(self.classifier_action, 'ensure_image_classifier_loaded'):
            self.classifier_action.ensure_image_classifier_loaded(
                app_actions.title_notify if app_actions is not None else None
            )
        elif hasattr(self.classifier_action, '_ensure_image_classifier_loaded'):
            self.classifier_action._ensure_image_classifier_loaded(
                app_actions.title_notify if app_actions is not None else None
            )

        self.frame = Frame(self.master)
        self.frame.grid(column=0, row=0)
        self.frame.columnconfigure(0, weight=9)
        self.frame.columnconfigure(1, weight=1)
        self.frame.config(bg=AppStyle.BG_COLOR)

        row = 0
        # Name field
        self._label_info = Label(self.frame)
        self.add_label(self._label_info, name_label_text, row=row, wraplength=self.COL_0_WIDTH)
        self.name_var = StringVar(self.master, value=new_name_default if classifier_action is None else classifier_action.name)
        self.name_entry = Entry(self.frame, textvariable=self.name_var, width=50, font=fnt.Font(size=config.font_size))
        self.name_entry.grid(row=row, column=1, sticky=W)

        row += 1
        # Positives field
        self.label_positives = Label(self.frame)
        self.add_label(self.label_positives, _("Positives"), row=row, wraplength=self.COL_0_WIDTH)
        self.positives_var = StringVar(self.master, value=self.classifier_action.get_positives_str())
        self.positives_entry = Entry(self.frame, textvariable=self.positives_var, width=50, font=fnt.Font(size=config.font_size))
        self.positives_entry.grid(row=row, column=1, sticky=W)

        row += 1
        # Negatives field
        self.label_negatives = Label(self.frame)
        self.add_label(self.label_negatives, _("Negatives"), row=row, wraplength=self.COL_0_WIDTH)
        self.negatives_var = StringVar(self.master, value=self.classifier_action.get_negatives_str())
        self.negatives_entry = Entry(self.frame, textvariable=self.negatives_var, width=50, font=fnt.Font(size=config.font_size))
        self.negatives_entry.grid(row=row, column=1, sticky=W)

        row += 1
        # Validation type checkboxes
        self.label_validation_types = Label(self.frame)
        self.add_label(self.label_validation_types, _("Validation Types"), row=row, wraplength=self.COL_0_WIDTH)
        
        self.use_test_embedding_var = BooleanVar(value=self.classifier_action.use_embedding)
        self.use_embedding_checkbox = Checkbutton(self.frame, text=_("Use Text Embeddings"), variable=self.use_test_embedding_var, 
                                                command=self.update_ui_for_validation_types,
                                                bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
        self.use_embedding_checkbox.grid(row=row, column=1, sticky=W)
        
        row += 1
        self.use_image_classifier_var = BooleanVar(value=self.classifier_action.use_image_classifier)
        self.use_image_classifier_checkbox = Checkbutton(self.frame, text=_("Use Image Classifier"), variable=self.use_image_classifier_var,
                                                        command=self.update_ui_for_validation_types,
                                                        bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
        self.use_image_classifier_checkbox.grid(row=row, column=1, sticky=W)
        
        row += 1
        self.use_prompts_var = BooleanVar(value=self.classifier_action.use_prompts)
        self.use_prompts_checkbox = Checkbutton(self.frame, text=_("Use Prompts"), variable=self.use_prompts_var,
                                               command=self.update_ui_for_validation_types,
                                               bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
        self.use_prompts_checkbox.grid(row=row, column=1, sticky=W)
        
        row += 1
        # Use prototype checkbox
        self.use_prototype_var = BooleanVar(self.master, value=self.classifier_action.use_prototype)
        self.use_prototype_checkbox = Checkbutton(
            self.frame, text=_("Use Embedding Prototype"), variable=self.use_prototype_var,
            command=self.update_ui_for_validation_types,
            bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR
        )
        self.use_prototype_checkbox.grid(row=row, column=1, sticky=W)

        row += 1
        # Text Embedding Threshold slider
        self.label_text_embedding_threshold = Label(self.frame)
        self.add_label(self.label_text_embedding_threshold, _("Text Embedding Threshold"), row=row, wraplength=self.COL_0_WIDTH)
        self.text_embedding_threshold_slider = Scale(self.frame, from_=0, to=100, orient=HORIZONTAL, command=self.set_text_embedding_threshold)
        self.text_embedding_threshold_slider.set(float(self.classifier_action.text_embedding_threshold) * 100)
        self.text_embedding_threshold_slider.grid(row=row, column=1, sticky=W)
        
        row += 1
        # Embedding Prototype Threshold slider
        self.label_prototype_threshold = Label(self.frame)
        self.add_label(self.label_prototype_threshold, _("Embedding Prototype Threshold"), row=row, wraplength=self.COL_0_WIDTH)
        self.prototype_threshold_slider = Scale(self.frame, from_=0, to=100, orient=HORIZONTAL, command=self.set_prototype_threshold)
        self.prototype_threshold_slider.set(float(self.classifier_action.prototype_threshold) * 100)
        self.prototype_threshold_slider.grid(row=row, column=1, sticky=W)

        row += 1
        # Action dropdown
        self.label_action = Label(self.frame)
        self.add_label(self.label_action, _("Action"), row=row, column=0)
        self.action_var = StringVar(self.master, value=self.classifier_action.action.get_translation())
        action_options = [k.get_translation() for k in ClassifierActionType]
        self.action_choice = Combobox(self.frame, textvariable=self.action_var, values=action_options)
        self.action_choice.current(action_options.index(self.classifier_action.action.get_translation()))
        self.action_choice.bind("<<ComboboxSelected>>", self.set_action)
        self.action_choice.grid(row=row, column=1, sticky=W)
        AppStyle.setup_combobox_style(self.action_choice)

        row += 1
        # Action modifier
        self.label_action_modifier = Label(self.frame)
        self.add_label(self.label_action_modifier, _("Action Modifier"), row=row, column=0)
        self.action_modifier_var = StringVar(self.master, value=self.classifier_action.action_modifier)
        self.action_modifier_entry = Entry(self.frame, textvariable=self.action_modifier_var, width=50, font=fnt.Font(size=config.font_size))
        self.action_modifier_entry.grid(row=row, column=1, sticky=W)

        row += 1
        # Image classifier name
        self.label_image_classifier_name = Label(self.frame)
        self.add_label(self.label_image_classifier_name, _("Image Classifier Name"), row=row, column=0)
        self.image_classifier_name_var = StringVar(self.master, value=self.classifier_action.image_classifier_name)
        name_options = [""]
        name_options.extend(image_classifier_manager.get_model_names())
        self.image_classifier_name_choice = Combobox(self.frame, textvariable=self.image_classifier_name_var, values=name_options)
        self.image_classifier_name_choice.current(name_options.index(self.classifier_action.image_classifier_name))
        self.image_classifier_name_choice.bind("<<ComboboxSelected>>", self.set_image_classifier)
        self.image_classifier_name_choice.grid(row=row, column=1, sticky=W)
        AppStyle.setup_combobox_style(self.image_classifier_name_choice)

        row += 1
        # Image classifier selected categories
        self.label_selected_category = Label(self.frame)
        self.add_label(self.label_selected_category, _("Image Classifier Selected Category"), row=row, column=0)
        self.selected_category_choice_row = row
        self.image_classifier_selected_categories = MultiSelectDropdown(
            self.frame, self.classifier_action.image_classifier_categories[:],
            row=self.selected_category_choice_row, sticky=W,
            select_text=_("Select Categories..."),
            selected=self.classifier_action.image_classifier_selected_categories[:],
            command=self.set_image_classifier_selected_categories
        )

        # Add prototype fields (common to both classifier actions and prevalidations)
        row = self.add_prototype_fields(row)
        
        # Let subclasses add their specific fields
        row = self.add_specific_fields(row)
        
        # Add is_active checkbox (common to both)
        row += 1
        self.label_should_run = Label(self.frame)
        self.add_label(self.label_should_run, _("Should Run"), row=row, wraplength=self.COL_0_WIDTH)
        self.is_active_var = BooleanVar(self.master, value=self.classifier_action.is_active)
        self.is_active_checkbox = Checkbutton(
            self.frame, text=_("Enable this classifier action"),
            variable=self.is_active_var,
            bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR
        )
        self.is_active_checkbox.grid(row=row, column=1, sticky=W)
        
        # Done button
        row += 1
        self.done_btn = None
        self.add_btn("done_btn", _("Done"), self.finalize, row=row, column=0)

        # Initialize UI based on current validation types
        self.update_ui_for_validation_types()

        self.master.update()

    def add_prototype_fields(self, row):
        """
        Add prototype-related fields (prototype directory, negative prototype, etc.).
        Returns the next row number to use.
        """
        row += 1
        # Prototype directory selection
        self.label_prototype_directory = Label(self.frame)
        self.add_label(self.label_prototype_directory, _("Prototype Directory"), row=row, wraplength=self.COL_0_WIDTH)
        
        # Frame to hold entry and browse button
        self.prototype_dir_frame = Frame(self.frame, bg=AppStyle.BG_COLOR)
        self.prototype_dir_frame.grid(row=row, column=1, sticky=W+E)
        
        self.prototype_directory_var = StringVar(self.master, value=self.classifier_action.prototype_directory)
        self.prototype_directory_entry = Entry(
            self.prototype_dir_frame, textvariable=self.prototype_directory_var,
            width=47, font=fnt.Font(size=config.font_size)
        )
        self.prototype_directory_entry.pack(side=LEFT, fill=BOTH, expand=True)
        
        # Browse button for prototype directory
        self.browse_prototype_btn = Button(
            self.prototype_dir_frame, text=_("Browse..."),
            command=self.browse_prototype_directory
        )
        self.browse_prototype_btn.pack(side=LEFT, padx=(2, 0))
        
        row += 1
        # Force recalculation button
        self.force_recalculate_prototype_btn = Button(
            self.frame, text=_("Force Recalculate Prototype"),
            command=self.force_recalculate_prototype
        )
        self.force_recalculate_prototype_btn.grid(row=row, column=1, sticky=W, pady=2)
        
        row += 1
        # Negative prototype directory selection
        self.label_negative_prototype_directory = Label(self.frame)
        self.add_label(
            self.label_negative_prototype_directory,
            _("Negative Prototype Directory (Optional)"),
            row=row, wraplength=self.COL_0_WIDTH
        )
        
        # Frame to hold entry and browse button
        self.negative_prototype_dir_frame = Frame(self.frame, bg=AppStyle.BG_COLOR)
        self.negative_prototype_dir_frame.grid(row=row, column=1, sticky=W+E)
        
        self.negative_prototype_directory_var = StringVar(
            self.master, value=self.classifier_action.negative_prototype_directory
        )
        self.negative_prototype_directory_entry = Entry(
            self.negative_prototype_dir_frame,
            textvariable=self.negative_prototype_directory_var,
            width=47, font=fnt.Font(size=config.font_size)
        )
        self.negative_prototype_directory_entry.pack(side=LEFT, fill=BOTH, expand=True)
        
        # Browse button for negative prototype directory
        self.browse_negative_prototype_btn = Button(
            self.negative_prototype_dir_frame, text=_("Browse..."),
            command=self.browse_negative_prototype_directory
        )
        self.browse_negative_prototype_btn.pack(side=LEFT, padx=(2, 0))
        
        row += 1
        # Negative prototype lambda (weight) slider
        self.label_negative_prototype_lambda = Label(self.frame)
        self.add_label(
            self.label_negative_prototype_lambda,
            _("Negative Prototype Weight (λ)"),
            row=row, wraplength=self.COL_0_WIDTH
        )
        self.negative_prototype_lambda_slider = Scale(
            self.frame, from_=0, to=100, orient=HORIZONTAL,
            command=self.set_negative_prototype_lambda
        )
        self.negative_prototype_lambda_slider.set(float(self.classifier_action.negative_prototype_lambda) * 100)
        self.negative_prototype_lambda_slider.grid(row=row, column=1, sticky=W)
        
        return row

    def add_specific_fields(self, row):
        """
        Override in subclasses to add specific fields.
        Returns the next row number to use.
        """
        return row

    def set_name(self):
        name = self.name_var.get().strip()
        self.classifier_action.name = name

    def set_positives(self):
        text = self.positives_entry.get().strip()
        if text != ClassifierAction.NO_POSITIVES_STR:
            self.classifier_action.set_positives(text)

    def set_negatives(self):
        text = self.negatives_entry.get().strip()
        if text != ClassifierAction.NO_NEGATIVES_STR:
            self.classifier_action.set_negatives(text)

    def set_text_embedding_threshold(self, event=None):
        self.classifier_action.text_embedding_threshold = float(self.text_embedding_threshold_slider.get()) / 100
        # Keep threshold for backward compatibility
        self.classifier_action.threshold = self.classifier_action.text_embedding_threshold
    
    def set_prototype_threshold(self, event=None):
        self.classifier_action.prototype_threshold = float(self.prototype_threshold_slider.get()) / 100

    def set_validation_types(self):
        self.classifier_action.use_embedding = self.use_test_embedding_var.get()
        self.classifier_action.use_image_classifier = self.use_image_classifier_var.get()
        self.classifier_action.use_prompts = self.use_prompts_var.get()
        self.classifier_action.use_prototype = self.use_prototype_var.get()

    def update_ui_for_validation_types(self):
        """Update UI elements based on the selected validation types."""
        use_text_embedding = self.use_test_embedding_var.get()
        use_image_classifier = self.use_image_classifier_var.get()
        use_prompts = self.use_prompts_var.get()
        use_prototype = self.use_prototype_var.get()
        
        # Show/hide image classifier fields
        if use_image_classifier:
            self.image_classifier_name_choice.grid()
            self.label_image_classifier_name.grid()
            self.image_classifier_selected_categories.button.grid()
            self.label_selected_category.grid()
        else:
            self.image_classifier_name_choice.grid_remove()
            self.label_image_classifier_name.grid_remove()
            self.image_classifier_selected_categories.button.grid_remove()
            self.label_selected_category.grid_remove()
        
        # Show/hide positive/negative fields based on type
        if use_text_embedding or use_prompts:
            self.positives_entry.grid()
            self.label_positives.grid()
            self.negatives_entry.grid()
            self.label_negatives.grid()
        else:
            self.positives_entry.grid_remove()
            self.label_positives.grid_remove()
            self.negatives_entry.grid_remove()
            self.label_negatives.grid_remove()
        
        # Show/hide text embedding threshold based on use_embedding
        if use_text_embedding:
            self.text_embedding_threshold_slider.grid()
            self.label_text_embedding_threshold.grid()
        else:
            self.text_embedding_threshold_slider.grid_remove()
            self.label_text_embedding_threshold.grid_remove()
        
        # Show/hide prototype fields and prototype threshold
        if use_prototype:
            if hasattr(self, 'prototype_dir_frame'):
                self.prototype_dir_frame.grid()
                self.label_prototype_directory.grid()
                self.force_recalculate_prototype_btn.grid()
            if hasattr(self, 'negative_prototype_dir_frame'):
                self.negative_prototype_dir_frame.grid()
                self.label_negative_prototype_directory.grid()
                self.negative_prototype_lambda_slider.grid()
                self.label_negative_prototype_lambda.grid()
            # Show prototype threshold
            self.prototype_threshold_slider.grid()
            self.label_prototype_threshold.grid()
        else:
            if hasattr(self, 'prototype_dir_frame'):
                self.prototype_dir_frame.grid_remove()
                self.label_prototype_directory.grid_remove()
                self.force_recalculate_prototype_btn.grid_remove()
            if hasattr(self, 'negative_prototype_dir_frame'):
                self.negative_prototype_dir_frame.grid_remove()
                self.label_negative_prototype_directory.grid_remove()
                self.negative_prototype_lambda_slider.grid_remove()
                self.label_negative_prototype_lambda.grid_remove()
            # Hide prototype threshold
            self.prototype_threshold_slider.grid_remove()
            self.label_prototype_threshold.grid_remove()
        
        # Let subclasses handle their specific UI updates
        self.update_specific_ui_for_validation_types()

    def update_specific_ui_for_validation_types(self):
        """Override in subclasses to handle specific UI updates."""
        pass

    def set_action(self, event=None):
        self.classifier_action.action = ClassifierActionType.get_action(self.action_var.get())

    def set_action_modifier(self):
        self.classifier_action.action_modifier = self.action_modifier_var.get()

    def set_image_classifier(self, event=None):
        self.classifier_action.set_image_classifier(self.image_classifier_name_var.get())
        set_category_value = self.classifier_action.image_classifier_categories[0] \
                if self.classifier_action.is_selected_category_unset() else self.classifier_action.image_classifier_selected_categories
        self.image_classifier_selected_categories.set_options_and_selection(
                self.classifier_action.image_classifier_categories[:], set_category_value[:])
        self.master.update()

    def set_image_classifier_selected_categories(self, event=None):
        self.classifier_action.image_classifier_selected_categories = list(self.image_classifier_selected_categories.get_selected())

    def finalize(self, event=None):
        """Finalize and save changes. Override in subclasses to add specific finalization."""
        self.set_name()
        self.set_positives()
        self.set_negatives()
        self.set_text_embedding_threshold()
        self.set_prototype_threshold()
        self.set_validation_types()
        self.set_action()
        self.set_action_modifier()
        self.set_image_classifier_selected_categories()
        self.set_prototype_directory()
        self.set_negative_prototype_directory()
        self.set_negative_prototype_lambda()
        self.set_is_active()
        self.finalize_specific()
        self.classifier_action.validate()
        self.close_windows()
        self.refresh_callback(self.classifier_action)

    def finalize_specific(self):
        """Override in subclasses to add specific finalization steps."""
        pass

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
            button  # for some reason this is necessary to maintain the reference?
            button.grid(row=row, column=column)

    def set_prototype_directory(self):
        self.classifier_action.prototype_directory = self.prototype_directory_var.get().strip()
    
    def browse_prototype_directory(self):
        """Open a directory browser to select prototype directory."""
        from tkinter import filedialog
        directory = filedialog.askdirectory(title=_("Select Prototype Directory"))
        if directory:
            self.prototype_directory_var.set(directory)
            self.set_prototype_directory()
    
    def set_negative_prototype_directory(self):
        self.classifier_action.negative_prototype_directory = self.negative_prototype_directory_var.get().strip()
    
    def browse_negative_prototype_directory(self):
        """Open a directory browser to select negative prototype directory."""
        from tkinter import filedialog
        directory = filedialog.askdirectory(title=_("Select Negative Prototype Directory"))
        if directory:
            self.negative_prototype_directory_var.set(directory)
            self.set_negative_prototype_directory()
    
    def set_negative_prototype_lambda(self, event=None):
        self.classifier_action.negative_prototype_lambda = float(self.negative_prototype_lambda_slider.get()) / 100
    
    def force_recalculate_prototype(self):
        """Force recalculation of the prototype embeddings (both positive and negative if set)."""
        from compare.embedding_prototype import EmbeddingPrototype
        from utils.logging_setup import get_logger
        
        logger = get_logger("classifier_management_window")
        notify_callback = self.app_actions.title_notify if self.app_actions is not None else None
        success_count = 0
        
        # Recalculate positive prototype
        directory = self.prototype_directory_var.get().strip()
        if directory:
            if not os.path.isdir(directory):
                logger.error(f"Prototype directory does not exist: {directory}")
            else:
                try:
                    prototype = EmbeddingPrototype.calculate_prototype_from_directory(
                        directory,
                        force_recalculate=True,
                        notify_callback=notify_callback
                    )
                    if prototype is not None:
                        self.classifier_action.prototype_directory = directory
                        self.classifier_action._cached_prototype = prototype
                        success_count += 1
                    else:
                        logger.error("Failed to recalculate positive prototype")
                except Exception as e:
                    logger.error(f"Error recalculating positive prototype: {e}")
        
        # Recalculate negative prototype if set
        negative_directory = self.negative_prototype_directory_var.get().strip()
        if negative_directory:
            if not os.path.isdir(negative_directory):
                logger.error(f"Negative prototype directory does not exist: {negative_directory}")
            else:
                try:
                    negative_prototype = EmbeddingPrototype.calculate_prototype_from_directory(
                        negative_directory,
                        force_recalculate=True,
                        notify_callback=notify_callback
                    )
                    if negative_prototype is not None:
                        self.classifier_action.negative_prototype_directory = negative_directory
                        self.classifier_action._cached_negative_prototype = negative_prototype
                        success_count += 1
                    else:
                        logger.error("Failed to recalculate negative prototype")
                except Exception as e:
                    logger.error(f"Error recalculating negative prototype: {e}")
        
        # Single notification after all recalculations
        if notify_callback and success_count > 0:
            notify_callback(_("Prototypes recalculated successfully"))
    
    def set_is_active(self):
        self.classifier_action.is_active = self.is_active_var.get()


class ClassifierManagementWindow:
    """
    Main window that contains notebook tabs for classifier actions and prevalidations.
    
    This window acts as a container, delegating the actual UI to tab content classes.
    """
    top_level = None
    instance = None  # Store the instance for access from other windows

    @staticmethod
    def get_geometry(is_gui=True):
        """Get the window geometry string."""
        width = 1200
        height = 700
        return f"{width}x{height}"

    def __init__(self, master, app_actions):
        """
        Initialize the classifier management window with tabs.
        
        Args:
            master: Parent window
            app_actions: Application actions object
        """
        ClassifierManagementWindow.top_level = SmartToplevel(
            persistent_parent=master,
            title=_("Classifier Management"),
            geometry=ClassifierManagementWindow.get_geometry()
        )
        self.master = ClassifierManagementWindow.top_level
        ClassifierManagementWindow.instance = self  # Store instance for access from other windows
        self.app_actions = app_actions

        # Main frame
        self.frame = Frame(self.master)
        self.frame.grid(column=0, row=0, sticky="nsew")
        self.frame.config(bg=AppStyle.BG_COLOR)
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(0, weight=1)

        # Create notebook for tabs
        self.notebook = Notebook(self.frame)
        self.notebook.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(0, weight=1)

        # Create tab content frames
        self.classifier_actions_frame = Frame(self.notebook, bg=AppStyle.BG_COLOR)
        self.prevalidations_frame = Frame(self.notebook, bg=AppStyle.BG_COLOR)

        # Add tabs to notebook
        self.notebook.add(self.classifier_actions_frame, text=_("Classifier Actions"))
        self.notebook.add(self.prevalidations_frame, text=_("Prevalidations"))

        # Create tab content classes (import here to avoid circular import)
        from ui_tk.compare.classifier_actions_tab import ClassifierActionsTab
        from ui_tk.compare.prevalidations_tab import PrevalidationsTab
        
        self.classifier_actions_tab = ClassifierActionsTab(self.classifier_actions_frame, app_actions)
        self.prevalidations_tab = PrevalidationsTab(self.prevalidations_frame, app_actions)

        # Disable prevalidations tab if prevalidations are disabled
        if not config.enable_prevalidations:
            self.notebook.tab(1, state='disabled')
            # Create tooltip for disabled tab
            # Note: ttk.Notebook doesn't support tooltips directly on tabs, so we bind to the notebook widget
            # The tooltip will show when hovering anywhere over the notebook, which is acceptable
            tooltip_text = _("Prevalidations are disabled. Enable them in the Prevalidations tab settings.")
            create_tooltip(self.notebook, tooltip_text)

        # Bind window events
        self.master.bind("<Escape>", self.close_windows)
        self.master.protocol("WM_DELETE_WINDOW", self.close_windows)
        self.master.update()
        self.frame.after(1, lambda: self.frame.focus_force())

    @staticmethod
    def set_prevalidations():
        ClassifierActionsManager.load_prevalidations()

    @staticmethod
    def store_prevalidations():
        ClassifierActionsManager.store_prevalidations()

    @staticmethod
    def set_classifier_actions():
        ClassifierActionsManager.load_classifier_actions()

    @staticmethod
    def store_classifier_actions():
        ClassifierActionsManager.store_classifier_actions()

    def close_windows(self, event=None):
        """Close the window."""
        ClassifierManagementWindow.instance = None  # Clear instance reference
        self.master.destroy()
