from enum import Enum
import os
from typing import Optional

from tkinter import Frame, Label, Scale, Checkbutton, BooleanVar, StringVar, LEFT, W, HORIZONTAL, Scrollbar, Listbox, BOTH, RIGHT, TOP, E
import tkinter.font as fnt
from tkinter.ttk import Entry, Button, Combobox

from compare.classification_actions_manager import ClassifierAction, ClassificationActionsManager
from compare.directory_profile import DirectoryProfile
from compare.embedding_prototype import EmbeddingPrototype
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



class ClassifierActionModifyWindow():
    top_level = None
    COL_0_WIDTH = 600

    def __init__(self, master, app_actions, refresh_callback, classifier_action, dimensions="600x600"):
        ClassifierActionModifyWindow.top_level = SmartToplevel(persistent_parent=master, geometry=dimensions)
        self.master = ClassifierActionModifyWindow.top_level
        self.app_actions = app_actions
        self.refresh_callback = refresh_callback
        self.classifier_action: Optional[ClassifierAction] = classifier_action if classifier_action is not None else ClassifierAction()
        ClassifierActionModifyWindow.top_level.title(_("Modify Classifier Action") + f": {self.classifier_action.name}")

        # Ensure image classifier is loaded for UI display
        self.classifier_action.ensure_image_classifier_loaded(app_actions.title_notify if app_actions is not None else None)

        self.frame = Frame(self.master)
        self.frame.grid(column=0, row=0)
        self.frame.columnconfigure(0, weight=9)
        self.frame.columnconfigure(1, weight=1)
        self.frame.config(bg=AppStyle.BG_COLOR)

        row = 0
        self._label_info = Label(self.frame)
        self.add_label(self._label_info, _("Classifier Action Name"), row=row, wraplength=ClassifierActionModifyWindow.COL_0_WIDTH)
        self.new_classifier_action_name = StringVar(self.master, value=_("New Classifier Action") if classifier_action is None else classifier_action.name)
        self.new_classifier_action_name_entry = Entry(self.frame, textvariable=self.new_classifier_action_name, width=50, font=fnt.Font(size=config.font_size))
        self.new_classifier_action_name_entry.grid(row=row, column=1, sticky=W)

        row += 1
        self.label_positives = Label(self.frame)
        self.add_label(self.label_positives, _("Positives"), row=row, wraplength=ClassifierActionModifyWindow.COL_0_WIDTH)
        self.positives_var = StringVar(self.master, value=self.classifier_action.get_positives_str())
        self.positives_entry = Entry(self.frame, textvariable=self.positives_var, width=50, font=fnt.Font(size=config.font_size))
        self.positives_entry.grid(row=row, column=1, sticky=W)

        row += 1
        self.label_negatives = Label(self.frame)
        self.add_label(self.label_negatives, _("Negatives"), row=row, wraplength=ClassifierActionModifyWindow.COL_0_WIDTH)
        self.negatives_var = StringVar(self.master, value=self.classifier_action.get_negatives_str())
        self.negatives_entry = Entry(self.frame, textvariable=self.negatives_var, width=50, font=fnt.Font(size=config.font_size))
        self.negatives_entry.grid(row=row, column=1, sticky=W)

        row += 1
        # Validation type checkboxes
        self.label_validation_types = Label(self.frame)
        self.add_label(self.label_validation_types, _("Validation Types"), row=row, wraplength=ClassifierActionModifyWindow.COL_0_WIDTH)
        
        self.use_embedding_var = BooleanVar(value=self.classifier_action.use_embedding)
        self.use_embedding_checkbox = Checkbutton(self.frame, text=_("Use Embedding"), variable=self.use_embedding_var, 
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
        self.use_prototype_var = BooleanVar(value=self.classifier_action.use_prototype)
        self.use_prototype_checkbox = Checkbutton(self.frame, text=_("Use Embedding Prototype"), variable=self.use_prototype_var,
                                                  command=self.update_ui_for_validation_types,
                                                  bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
        self.use_prototype_checkbox.grid(row=row, column=1, sticky=W)

        row += 1
        self.label_threshold = Label(self.frame)
        self.add_label(self.label_threshold, _("Threshold"), row=row, wraplength=ClassifierActionModifyWindow.COL_0_WIDTH)
        self.threshold_slider = Scale(self.frame, from_=0, to=100, orient=HORIZONTAL, command=self.set_threshold)
        self.threshold_slider.set(float(self.classifier_action.threshold) * 100)
        self.threshold_slider.grid(row=row, column=1, sticky=W)

        row += 1
        self.label_action = Label(self.frame)
        self.add_label(self.label_action, _("Action"), row=row, column=0)
        self.action_var = StringVar(self.master, value=self.classifier_action.action.get_translation())
        action_options = [k.get_translation() for k in ClassifierActionType]
        self.action_choice = Combobox(self.frame, textvariable=self.action_var, values=action_options)
        self.action_choice.current(action_options.index(self.classifier_action.action.get_translation()))
        self.action_choice.bind("<<ComboboxSelected>>", self.set_action)
        self.action_choice.grid(row=row, column=1, sticky=W)
        # Style the combobox
        self.action_choice.config(background=AppStyle.BG_COLOR, foreground=AppStyle.FG_COLOR)

        row += 1
        self.label_action_modifier = Label(self.frame)
        self.add_label(self.label_action_modifier, _("Action Modifier"), row=row, column=0)
        self.action_modifier_var = StringVar(self.master, value=self.classifier_action.action_modifier)
        self.action_modifier_entry = Entry(self.frame, textvariable=self.action_modifier_var, width=50, font=fnt.Font(size=config.font_size))
        self.action_modifier_entry.grid(row=row, column=1, sticky=W)

        row += 1
        self.label_image_classifier_name = Label(self.frame)
        self.add_label(self.label_image_classifier_name, _("Image Classifier Name"), row=row, column=0)
        self.image_classifier_name_var = StringVar(self.master, value=self.classifier_action.image_classifier_name)
        name_options = [""]
        name_options.extend(image_classifier_manager.get_model_names())
        self.image_classifier_name_choice = Combobox(self.frame, textvariable=self.image_classifier_name_var, values=name_options)
        self.image_classifier_name_choice.current(name_options.index(self.classifier_action.image_classifier_name))
        self.image_classifier_name_choice.bind("<<ComboboxSelected>>", self.set_image_classifier)
        self.image_classifier_name_choice.grid(row=row, column=1, sticky=W)
        self.image_classifier_name_choice.config(background=AppStyle.BG_COLOR, foreground=AppStyle.FG_COLOR)

        row += 1
        self.label_selected_category = Label(self.frame)
        self.add_label(self.label_selected_category, _("Image Classifier Selected Category"), row=row, column=0)
        self.selected_category_choice_row = row
        self.image_classifier_selected_categories = MultiSelectDropdown(self.frame, self.classifier_action.image_classifier_categories[:],
                                                                        row=self.selected_category_choice_row, sticky=W,
                                                                        select_text=_("Select Categories..."),
                                                                        selected=self.classifier_action.image_classifier_selected_categories[:],
                                                                        command=self.set_image_classifier_selected_categories)

        row += 1
        # Prototype directory selection
        self.label_prototype_directory = Label(self.frame)
        self.add_label(self.label_prototype_directory, _("Prototype Directory"), row=row, wraplength=ClassifierActionModifyWindow.COL_0_WIDTH)
        
        # Frame to hold entry and browse button
        self.prototype_dir_frame = Frame(self.frame, bg=AppStyle.BG_COLOR)
        self.prototype_dir_frame.grid(row=row, column=1, sticky=W+E)
        
        self.prototype_directory_var = StringVar(self.master, value=self.classifier_action.prototype_directory)
        self.prototype_directory_entry = Entry(self.prototype_dir_frame, textvariable=self.prototype_directory_var, width=47, font=fnt.Font(size=config.font_size))
        self.prototype_directory_entry.pack(side=LEFT, fill=BOTH, expand=True)
        
        # Browse button for prototype directory
        self.browse_prototype_btn = Button(self.prototype_dir_frame, text=_("Browse..."), command=self.browse_prototype_directory)
        self.browse_prototype_btn.pack(side=LEFT, padx=(2, 0))
        
        row += 1
        # Force recalculation button
        self.force_recalculate_prototype_btn = Button(self.frame, text=_("Force Recalculate Prototype"), command=self.force_recalculate_prototype)
        self.force_recalculate_prototype_btn.grid(row=row, column=1, sticky=W, pady=2)
        
        row += 1
        # Negative prototype directory selection
        self.label_negative_prototype_directory = Label(self.frame)
        self.add_label(self.label_negative_prototype_directory, _("Negative Prototype Directory (Optional)"), row=row, wraplength=ClassifierActionModifyWindow.COL_0_WIDTH)
        
        # Frame to hold entry and browse button
        self.negative_prototype_dir_frame = Frame(self.frame, bg=AppStyle.BG_COLOR)
        self.negative_prototype_dir_frame.grid(row=row, column=1, sticky=W+E)
        
        self.negative_prototype_directory_var = StringVar(self.master, value=self.classifier_action.negative_prototype_directory)
        self.negative_prototype_directory_entry = Entry(self.negative_prototype_dir_frame, textvariable=self.negative_prototype_directory_var, width=47, font=fnt.Font(size=config.font_size))
        self.negative_prototype_directory_entry.pack(side=LEFT, fill=BOTH, expand=True)
        
        # Browse button for negative prototype directory
        self.browse_negative_prototype_btn = Button(self.negative_prototype_dir_frame, text=_("Browse..."), command=self.browse_negative_prototype_directory)
        self.browse_negative_prototype_btn.pack(side=LEFT, padx=(2, 0))
        
        row += 1
        # Negative prototype lambda (weight) slider
        self.label_negative_prototype_lambda = Label(self.frame)
        self.add_label(self.label_negative_prototype_lambda, _("Negative Prototype Weight (λ)"), row=row, wraplength=ClassifierActionModifyWindow.COL_0_WIDTH)
        self.negative_prototype_lambda_slider = Scale(self.frame, from_=0, to=100, orient=HORIZONTAL, command=self.set_negative_prototype_lambda)
        self.negative_prototype_lambda_slider.set(float(self.classifier_action.negative_prototype_lambda) * 100)
        self.negative_prototype_lambda_slider.grid(row=row, column=1, sticky=W)
        
        row += 1
        # Should run checkbox
        self.label_should_run = Label(self.frame)
        self.add_label(self.label_should_run, _("Should Run"), row=row, wraplength=ClassifierActionModifyWindow.COL_0_WIDTH)
        self.is_active_var = BooleanVar(value=self.classifier_action.is_active)
        self.is_active_checkbox = Checkbutton(self.frame, text=_("Enable this classifier action"), variable=self.is_active_var,
                                               bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
        self.is_active_checkbox.grid(row=row, column=1, sticky=W)
        
        row += 1
        self.add_classifier_action_btn = None
        self.add_btn("add_classifier_action_btn", _("Done"), self.finalize_classifier_action, row=row, column=0)

        # Initialize UI based on current validation types
        self.update_ui_for_validation_types()

        self.master.update()

    def set_name(self):
        name = self.new_classifier_action_name.get().strip()
        self.classifier_action.name = name

    def set_positives(self):
        text = self.positives_entry.get().strip()
        if text != ClassifierAction.NO_POSITIVES_STR:
            self.classifier_action.set_positives(text)

    def set_negatives(self):
        text = self.negatives_entry.get().strip()
        if text != ClassifierAction.NO_NEGATIVES_STR:
            self.classifier_action.set_negatives(text)

    def set_threshold(self, event=None):
        self.classifier_action.threshold = float(self.threshold_slider.get()) / 100

    def set_validation_types(self):
        self.classifier_action.use_embedding = self.use_embedding_var.get()
        self.classifier_action.use_image_classifier = self.use_image_classifier_var.get()
        self.classifier_action.use_prompts = self.use_prompts_var.get()
        self.classifier_action.use_prototype = self.use_prototype_var.get()

    def update_ui_for_validation_types(self):
        """Update UI elements based on the selected validation types."""
        use_embedding = self.use_embedding_var.get()
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
        if use_embedding or use_prompts:
            self.positives_entry.grid()
            self.label_positives.grid()
            self.negatives_entry.grid()
            self.label_negatives.grid()
        else:
            self.positives_entry.grid_remove()
            self.label_positives.grid_remove()
            self.negatives_entry.grid_remove()
            self.label_negatives.grid_remove()
        
        # Show/hide prototype fields
        if use_prototype:
            if hasattr(self, 'prototype_dir_frame'):
                self.prototype_dir_frame.grid()  # Show the frame containing entry and button
                self.label_prototype_directory.grid()
                self.force_recalculate_prototype_btn.grid()
            if hasattr(self, 'negative_prototype_dir_frame'):
                self.negative_prototype_dir_frame.grid()
                self.label_negative_prototype_directory.grid()
                self.negative_prototype_lambda_slider.grid()
                self.label_negative_prototype_lambda.grid()
        else:
            if hasattr(self, 'prototype_dir_frame'):
                self.prototype_dir_frame.grid_remove()  # Hide the frame
                self.label_prototype_directory.grid_remove()
                self.force_recalculate_prototype_btn.grid_remove()
            if hasattr(self, 'negative_prototype_dir_frame'):
                self.negative_prototype_dir_frame.grid_remove()
                self.label_negative_prototype_directory.grid_remove()
                self.negative_prototype_lambda_slider.grid_remove()
                self.label_negative_prototype_lambda.grid_remove()

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
    
    def finalize_classifier_action(self, event=None):
        self.set_name()
        self.set_positives()
        self.set_negatives()
        self.set_threshold()
        self.set_validation_types()
        self.set_action()
        self.set_action_modifier()
        self.set_image_classifier_selected_categories()
        self.set_prototype_directory()
        self.set_negative_prototype_directory()
        self.set_negative_prototype_lambda()
        self.set_is_active()
        self.classifier_action.validate()
        self.close_windows()
        self.refresh_callback(self.classifier_action)

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


class ClassifierActionsWindow():
    top_level = None
    classifier_action_modify_window: Optional[ClassifierActionModifyWindow] = None
    # classifier_actions list is now managed by ClassificationActionsManager

    MAX_HEIGHT = 900
    COL_0_WIDTH = 600

    @staticmethod
    def run_classifier_action(classifier_action: ClassifierAction, directory_paths: list[str], hide_callback, notify_callback, add_mark_callback=None, profile_name_or_path: Optional[str] = None):
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
        classifier_action.run(directory_paths, hide_callback, notify_callback, add_mark_callback, profile_name_or_path)

    @staticmethod
    def set_classifier_actions():
        ClassificationActionsManager.load_classifier_actions()

    @staticmethod
    def store_classifier_actions():
        ClassificationActionsManager.store_classifier_actions()

    @staticmethod
    def get_geometry(is_gui=True):
        width = 1200
        height = 600
        return f"{width}x{height}"

    def __init__(self, master, app_actions):
        ClassifierActionsWindow.top_level = SmartToplevel(persistent_parent=master, title=_("Classifier Actions"), geometry=ClassifierActionsWindow.get_geometry())
        self.master = ClassifierActionsWindow.top_level
        self.app_actions = app_actions
        self.filter_text = ""
        self.filtered_classifier_actions = ClassificationActionsManager.classifier_actions[:]
        self.label_list = []
        self.label_list2 = []
        self.set_classifier_action_btn_list = []
        self.modify_classifier_action_btn_list = []
        self.delete_classifier_action_btn_list = []
        self.run_classifier_action_btn_list = []
        self.move_down_btn_list = []

        self.frame = Frame(self.master)
        self.frame.grid(column=0, row=0)
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
        self.profile_choice.config(background=AppStyle.BG_COLOR, foreground=AppStyle.FG_COLOR)

        self.add_classifier_action_widgets()

        self.master.bind("<Escape>", self.close_windows)
        self.master.protocol("WM_DELETE_WINDOW", self.close_windows)
        self.master.update()
        self.frame.after(1, lambda: self.frame.focus_force())

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
            self.add_label(label_name, str(classifier_action), row=row, column=base_col, wraplength=ClassifierActionsWindow.COL_0_WIDTH)

            label_action = Label(self.frame)
            self.label_list2.append(label_action)
            self.add_label(label_action, classifier_action.action.get_translation(), row=row, column=base_col + 1)
            
            active_text = _("Yes") if classifier_action.is_active else _("No")
            label_active = Label(self.frame)
            self.add_label(label_active, active_text, row=row, column=base_col + 2)

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
                return self.run_classifier_action(event, classifier_action)
            run_classifier_action_btn.bind("<Button-1>", run_classifier_action_handler)

            move_down_btn = Button(self.frame, text=_("Move down"))
            self.move_down_btn_list.append(move_down_btn)
            move_down_btn.grid(row=row, column=base_col+6)
            def move_down_handler(event, self=self, idx=i, classifier_action=classifier_action):
                classifier_action.move_index(idx, 1)
                self.refresh()
            move_down_btn.bind("<Button-1>", move_down_handler)

    def open_classifier_action_modify_window(self, event=None, classifier_action=None):
        if ClassifierActionsWindow.classifier_action_modify_window is not None:
            ClassifierActionsWindow.classifier_action_modify_window.master.destroy()
        ClassifierActionsWindow.classifier_action_modify_window = ClassifierActionModifyWindow(
            self.master, self.app_actions, self.refresh_classifier_actions, classifier_action)

    def refresh_classifier_actions(self, classifier_action):
        # Check if this is a new classifier action, if so, insert it at the start
        if classifier_action not in ClassificationActionsManager.classifier_actions:
            ClassificationActionsManager.classifier_actions.insert(0, classifier_action)
        self.filtered_classifier_actions = ClassificationActionsManager.classifier_actions[:]
        self.refresh()

    def delete_classifier_action(self, event=None, classifier_action=None):
        if classifier_action is not None and classifier_action in ClassificationActionsManager.classifier_actions:
            ClassificationActionsManager.classifier_actions.remove(classifier_action)
        self.refresh()

    def run_classifier_action(self, event=None, classifier_action=None):
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
        directory_list = "\n".join([f"  - {d}" for d in selected_profile.directories])
        res = messagebox.askokcancel(
            _("Run Classifier Action"),
            _("Run classifier action '{0}' on the following directories?\n\n{1}").format(classifier_action.name, directory_list)
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
            
            ClassifierActionsWindow.run_classifier_action(
                classifier_action,
                selected_profile.directories,
                hide_callback,
                notify_callback,
                add_mark_callback,
                selected_profile_name  # Pass profile name to store as last used
            )

    def clear_recent_classifier_actions(self, event=None):
        self.clear_widget_lists()
        ClassificationActionsManager.classifier_actions.clear()
        self.filtered_classifier_actions.clear()
        self.add_classifier_action_widgets()
        self.master.update()

    def clear_widget_lists(self):
        for label in self.label_list:
            label.destroy()
        for label in self.label_list2:
            label.destroy()
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
        
        self.filtered_classifier_actions = ClassificationActionsManager.classifier_actions[:]
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

