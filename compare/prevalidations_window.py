import os
from typing import Optional

from tkinter import Frame, Label, Scale, Checkbutton, BooleanVar, StringVar, LEFT, W, HORIZONTAL, Scrollbar, Listbox, BOTH, RIGHT, TOP, E
import tkinter.font as fnt
from tkinter.ttk import Entry, Button, Combobox

from compare.classification_actions_manager import Prevalidation, ClassifierActionsManager
from compare.directory_profile import DirectoryProfile, DirectoryProfileWindow
from compare.lookahead import Lookahead, LookaheadWindow
from image.classifier_action_type import ClassifierActionType
from image.image_classifier_manager import image_classifier_manager
from lib.multiselect_dropdown import MultiSelectDropdown
from lib.multi_display import SmartToplevel
from utils.app_style import AppStyle
from utils.config import config
from utils.logging_setup import get_logger
from utils.translations import I18N

_ = I18N._
logger = get_logger("prevalidations_window")



class PrevalidationModifyWindow():
    top_level = None
    COL_0_WIDTH = 600

    def __init__(self, master, app_actions, refresh_callback, prevalidation, dimensions="600x600"):
        PrevalidationModifyWindow.top_level = SmartToplevel(persistent_parent=master, geometry=dimensions)
        self.master = PrevalidationModifyWindow.top_level
        self.app_actions = app_actions
        self.refresh_callback = refresh_callback
        self.prevalidation = prevalidation if prevalidation is not None else Prevalidation()
        PrevalidationModifyWindow.top_level.title(_("Modify Prevalidation") + f": {self.prevalidation.name}")

        # Ensure image classifier is loaded for UI display
        self.prevalidation._ensure_image_classifier_loaded(app_actions.title_notify if app_actions is not None else None)

        self.frame = Frame(self.master)
        self.frame.grid(column=0, row=0)
        self.frame.columnconfigure(0, weight=9)
        self.frame.columnconfigure(1, weight=1)
        self.frame.config(bg=AppStyle.BG_COLOR)

        row = 0
        self._label_info = Label(self.frame)
        self.add_label(self._label_info, _("Prevalidation Name"), row=row, wraplength=PrevalidationModifyWindow.COL_0_WIDTH)
        self.new_prevalidation_name = StringVar(self.master, value=_("New Prevalidation") if prevalidation is None else prevalidation.name)
        self.new_prevalidation_name_entry = Entry(self.frame, textvariable=self.new_prevalidation_name, width=50, font=fnt.Font(size=config.font_size))
        self.new_prevalidation_name_entry.grid(row=row, column=1, sticky=W)

        row += 1
        self.label_positives = Label(self.frame)
        self.add_label(self.label_positives, _("Positives"), row=row, wraplength=PrevalidationModifyWindow.COL_0_WIDTH)
        self.positives_var = StringVar(self.master, value=self.prevalidation.get_positives_str())
        self.positives_entry = Entry(self.frame, textvariable=self.positives_var, width=50, font=fnt.Font(size=config.font_size))
        self.positives_entry.grid(row=row, column=1, sticky=W)

        row += 1
        self.label_negatives = Label(self.frame)
        self.add_label(self.label_negatives, _("Negatives"), row=row, wraplength=PrevalidationModifyWindow.COL_0_WIDTH)
        self.negatives_var = StringVar(self.master, value=self.prevalidation.get_negatives_str())
        self.negatives_entry = Entry(self.frame, textvariable=self.negatives_var, width=50, font=fnt.Font(size=config.font_size))
        self.negatives_entry.grid(row=row, column=1, sticky=W)

        row += 1
        # Validation type checkboxes
        self.label_validation_types = Label(self.frame)
        self.add_label(self.label_validation_types, _("Validation Types"), row=row, wraplength=PrevalidationModifyWindow.COL_0_WIDTH)
        
        self.use_embedding_var = BooleanVar(value=self.prevalidation.use_embedding)
        self.use_embedding_checkbox = Checkbutton(self.frame, text=_("Use Embedding"), variable=self.use_embedding_var, 
                                                command=self.update_ui_for_validation_types,
                                                bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
        self.use_embedding_checkbox.grid(row=row, column=1, sticky=W)
        
        row += 1
        self.use_image_classifier_var = BooleanVar(value=self.prevalidation.use_image_classifier)
        self.use_image_classifier_checkbox = Checkbutton(self.frame, text=_("Use Image Classifier"), variable=self.use_image_classifier_var,
                                                        command=self.update_ui_for_validation_types,
                                                        bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
        self.use_image_classifier_checkbox.grid(row=row, column=1, sticky=W)
        
        row += 1
        self.use_prompts_var = BooleanVar(value=self.prevalidation.use_prompts)
        self.use_prompts_checkbox = Checkbutton(self.frame, text=_("Use Prompts"), variable=self.use_prompts_var,
                                               command=self.update_ui_for_validation_types,
                                               bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
        self.use_prompts_checkbox.grid(row=row, column=1, sticky=W)

        row += 1
        self.label_threshold = Label(self.frame)
        self.add_label(self.label_threshold, _("Threshold"), row=row, wraplength=PrevalidationModifyWindow.COL_0_WIDTH)
        self.threshold_slider = Scale(self.frame, from_=0, to=100, orient=HORIZONTAL, command=self.set_threshold)
        self.threshold_slider.set(float(self.prevalidation.threshold) * 100)
        self.threshold_slider.grid(row=row, column=1, sticky=W)

        row += 1
        self.label_action = Label(self.frame)
        self.add_label(self.label_action, _("Action"), row=row, column=0)
        self.action_var = StringVar(self.master, value=self.prevalidation.action.get_translation())
        action_options = [k.get_translation() for k in ClassifierActionType]
        self.action_choice = Combobox(self.frame, textvariable=self.action_var, values=action_options)
        self.action_choice.current(action_options.index(self.prevalidation.action.get_translation()))
        self.action_choice.bind("<<ComboboxSelected>>", self.set_action)
        self.action_choice.grid(row=row, column=1, sticky=W)
        # Style the combobox
        self.action_choice.config(background=AppStyle.BG_COLOR, foreground=AppStyle.FG_COLOR)

        row += 1
        self.label_action_modifier = Label(self.frame)
        self.add_label(self.label_action_modifier, _("Action Modifier"), row=row, column=0)
        self.action_modifier_var = StringVar(self.master, value=self.prevalidation.action_modifier)
        self.action_modifier_entry = Entry(self.frame, textvariable=self.action_modifier_var, width=50, font=fnt.Font(size=config.font_size))
        self.action_modifier_entry.grid(row=row, column=1, sticky=W)

        row += 1
        self.label_image_classifier_name = Label(self.frame)
        self.add_label(self.label_image_classifier_name, _("Image Classifier Name"), row=row, column=0)
        self.image_classifier_name_var = StringVar(self.master, value=self.prevalidation.image_classifier_name)
        name_options = [""]
        name_options.extend(image_classifier_manager.get_model_names())
        self.image_classifier_name_choice = Combobox(self.frame, textvariable=self.image_classifier_name_var, values=name_options)
        self.image_classifier_name_choice.current(name_options.index(self.prevalidation.image_classifier_name))
        self.image_classifier_name_choice.bind("<<ComboboxSelected>>", self.set_image_classifier)
        self.image_classifier_name_choice.grid(row=row, column=1, sticky=W)
        self.image_classifier_name_choice.config(background=AppStyle.BG_COLOR, foreground=AppStyle.FG_COLOR)

        row += 1
        self.label_selected_category = Label(self.frame)
        self.add_label(self.label_selected_category, _("Image Classifier Selected Category"), row=row, column=0)
        self.selected_category_choice_row = row
        self.image_classifier_selected_categories = MultiSelectDropdown(self.frame, self.prevalidation.image_classifier_categories[:],
                                                                        row=self.selected_category_choice_row, sticky=W,
                                                                        select_text=_("Select Categories..."),
                                                                        selected=self.prevalidation.image_classifier_selected_categories[:],
                                                                        command=self.set_image_classifier_selected_categories)

        row += 1
        # Prevalidation Lookaheads section - just select which lookaheads to use
        self.label_lookaheads = Label(self.frame)
        self.add_label(self.label_lookaheads, _("Lookaheads (select from shared list)"), row=row, wraplength=PrevalidationModifyWindow.COL_0_WIDTH)
        
        # Multi-select dropdown for lookaheads
        lookahead_options = [lookahead.name for lookahead in Lookahead.lookaheads]
        self.lookaheads_multiselect = MultiSelectDropdown(self.frame, lookahead_options[:],
                                                          row=row, column=1, sticky=W,
                                                          select_text=_("Select Lookaheads..."),
                                                          selected=self.prevalidation.lookahead_names[:],
                                                          command=self.set_lookahead_names)
        
        row += 1
        # Profile selection
        self.label_profile = Label(self.frame)
        self.add_label(self.label_profile, _("Directory Profile"), row=row, wraplength=PrevalidationModifyWindow.COL_0_WIDTH)
        
        # Profile dropdown - include "(Global)" option for no profile
        profile_options = [""]  # Empty string = Global
        profile_options.extend([profile.name for profile in DirectoryProfile.directory_profiles])
        
        current_profile_name = self.prevalidation.profile_name if self.prevalidation.profile_name else ""
        self.profile_var = StringVar(self.master, value=current_profile_name)
        self.profile_choice = Combobox(self.frame, textvariable=self.profile_var, values=profile_options, width=47,
                                       font=fnt.Font(size=config.font_size))
        # Set current selection
        if current_profile_name in profile_options:
            self.profile_choice.current(profile_options.index(current_profile_name))
        else:
            self.profile_choice.current(0)  # Default to Global
        self.profile_choice.bind("<<ComboboxSelected>>", self.set_profile_name)
        self.profile_choice.grid(row=row, column=1, sticky=W)
        self.profile_choice.config(background=AppStyle.BG_COLOR, foreground=AppStyle.FG_COLOR)
        
        row += 1
        self.add_prevalidation_btn = None
        self.add_btn("add_prevalidation_btn", _("Done"), self.finalize_prevalidation, row=row, column=0)

        # Initialize UI based on current validation types
        self.update_ui_for_validation_types()

        self.master.update()

    def set_name(self):
        name = self.new_prevalidation_name.get().strip()
        self.prevalidation.name = name

    def set_positives(self):
        text = self.positives_entry.get().strip()
        if text != Prevalidation.NO_POSITIVES_STR:
            self.prevalidation.set_positives(text)

    def set_negatives(self):
        text = self.negatives_entry.get().strip()
        if text != Prevalidation.NO_NEGATIVES_STR:
            self.prevalidation.set_negatives(text)

    def set_threshold(self, event=None):
        self.prevalidation.threshold = float(self.threshold_slider.get()) / 100

    def set_validation_types(self):
        self.prevalidation.use_embedding = self.use_embedding_var.get()
        self.prevalidation.use_image_classifier = self.use_image_classifier_var.get()
        self.prevalidation.use_prompts = self.use_prompts_var.get()

    def update_ui_for_validation_types(self):
        """Update UI elements based on the selected validation types."""
        use_embedding = self.use_embedding_var.get()
        use_image_classifier = self.use_image_classifier_var.get()
        use_prompts = self.use_prompts_var.get()
        
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

    def set_action(self, event=None):
        self.prevalidation.action = ClassifierActionType.get_action(self.action_var.get())

    def set_action_modifier(self):
        self.prevalidation.action_modifier = self.action_modifier_var.get()

    def set_image_classifier(self, event=None):
        self.prevalidation.set_image_classifier(self.image_classifier_name_var.get())
        set_category_value = self.prevalidation.image_classifier_categories[0] \
                if self.prevalidation.is_selected_category_unset() else self.prevalidation.image_classifier_selected_categories
        self.image_classifier_selected_categories.set_options_and_selection(
                self.prevalidation.image_classifier_categories[:], set_category_value[:])
        # self.image_classifier_selected_category_choice = OptionMenu(self.frame, self.image_classifier_selected_category_var,
        #                                                             *self.prevalidation.image_classifier_categories[:],
        #                                                             command=self.set_image_classifier_selected_category)
        self.master.update()

    def set_image_classifier_selected_categories(self, event=None):
        self.prevalidation.image_classifier_selected_categories = list(self.image_classifier_selected_categories.get_selected())

    def set_lookahead_names(self, event=None):
        """Set the selected lookahead names for this prevalidation."""
        self.prevalidation.lookahead_names = list(self.lookaheads_multiselect.get_selected())
    
    def set_profile_name(self, event=None):
        """Set the profile name for this prevalidation."""
        selected_profile_name = self.profile_var.get().strip()
        # Empty string means Global (no profile)
        profile_name = selected_profile_name if selected_profile_name else None
        self.prevalidation.update_profile_instance(profile_name=profile_name)
    
    def refresh_profile_options(self):
        """Refresh the profile dropdown options."""
        if hasattr(self, 'profile_choice'):
            profile_options = [""]  # Empty string = Global
            profile_options.extend([profile.name for profile in DirectoryProfile.directory_profiles])
            
            current_value = self.profile_var.get()
            self.profile_choice['values'] = profile_options
            
            # Update current selection if still valid, otherwise default to Global
            if current_value in profile_options:
                self.profile_choice.current(profile_options.index(current_value))
            else:
                self.profile_choice.current(0)
                self.profile_var.set("")
    
    def refresh_lookahead_options(self):
        """Refresh the lookahead multiselect dropdown options."""
        lookahead_options = [lookahead.name for lookahead in Lookahead.lookaheads]
        self.lookaheads_multiselect.set_options_and_selection(
            lookahead_options[:], 
            self.prevalidation.lookahead_names[:]
        )
    
    def finalize_prevalidation(self, event=None):
        self.set_name()
        self.set_positives()
        self.set_negatives()
        self.set_threshold()
        self.set_validation_types()
        self.set_action()
        self.set_action_modifier()
        # self.set_image_classifier()
        self.set_image_classifier_selected_categories()
        self.set_lookahead_names()  # Save lookahead selections
        self.set_profile_name()  # Save profile selection
        self.prevalidation.validate()
        self.close_windows()
        self.refresh_callback(self.prevalidation)

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



class PrevalidationsWindow():
    top_level = None
    prevalidation_modify_window: Optional[PrevalidationModifyWindow] = None
    lookahead_window: Optional[LookaheadWindow] = None
    profile_window: Optional[DirectoryProfileWindow] = None

    MAX_PRESETS = 50

    MAX_HEIGHT = 900
    N_TAGS_CUTOFF = 30
    COL_0_WIDTH = 600

    @staticmethod
    def set_prevalidations():
        ClassifierActionsManager.load_prevalidations()

    @staticmethod
    def store_prevalidations():
        ClassifierActionsManager.store_prevalidations()

    @staticmethod
    def clear_prevalidated_cache():
        ClassifierActionsManager.prevalidated_cache.clear()

    @staticmethod
    def get_geometry(is_gui=True):
        width = 1200
        height = 600
        return f"{width}x{height}"

    def __init__(self, master, app_actions):
        PrevalidationsWindow.top_level = SmartToplevel(persistent_parent=master, title=_("Prevalidations"), geometry=PrevalidationsWindow.get_geometry())
        self.master = PrevalidationsWindow.top_level
        self.app_actions = app_actions
        self.filter_text = ""
        self.filtered_prevalidations = ClassifierActionsManager.prevalidations[:]
        self.label_list = []
        self.label_list2 = []
        self.is_active_var_list = []
        self.is_active_list = []
        self.set_prevalidation_btn_list = []
        self.modify_prevalidation_btn_list = []
        self.delete_prevalidation_btn_list = []
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
        self.frame.columnconfigure(7, weight=1)
        self.frame.config(bg=AppStyle.BG_COLOR)
        
        self.add_lookahead_management_section()
        self.add_profile_management_section()

        # Prevalidations section title (row 4: after lookaheads 0-1, profiles 2-3)
        self.prevalidations_title = Label(self.frame, text=_("Prevalidations"), 
                                         bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR, 
                                         font=fnt.Font(size=config.font_size + 2, weight="bold"))
        self.prevalidations_title.grid(row=4, column=0, columnspan=4, sticky=W, pady=(5, 10))
        
        self.add_prevalidation_btn = None
        self.add_btn("add_prevalidation_btn", _("Add prevalidation"), self.open_prevalidation_modify_window, row=4, column=1)
        self.clear_recent_prevalidations_btn = None
        self.add_btn("clear_recent_prevalidations_btn", _("Clear prevalidations"), self.clear_recent_prevalidations, row=4, column=2)

        # Add enable prevalidations checkbox (row 5)
        self.label_enable_prevalidations = Label(self.frame)
        self.enable_prevalidations = BooleanVar(value=config.enable_prevalidations)
        self.checkbox_enable_prevalidations = Checkbutton(self.frame, variable=self.enable_prevalidations, 
                                                        command=self.toggle_prevalidations)
        self.add_label(self.label_enable_prevalidations, _("Enable Prevalidations"), row=5, wraplength=PrevalidationsWindow.COL_0_WIDTH)
        self.checkbox_enable_prevalidations.grid(row=5, column=1, sticky=W)

        self.add_prevalidation_widgets()

        # self.master.bind("<Key>", self.filter_prevalidations)
        # self.master.bind("<Return>", self.do_action)
        self.master.bind("<Escape>", self.close_windows)
        self.master.protocol("WM_DELETE_WINDOW", self.close_windows)
        self.master.update()
        self.frame.after(1, lambda: self.frame.focus_force())

    def add_lookahead_management_section(self):
        """Add a section for managing lookaheads."""
        
        # Lookaheads section title
        self.lookaheads_title = Label(self.frame, text=_("Lookaheads"), 
                                     bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR, 
                                     font=fnt.Font(size=config.font_size + 2, weight="bold"))
        self.lookaheads_title.grid(row=0, column=0, columnspan=4, sticky=W, pady=(20, 10))
        
        # Create a separate frame for lookaheads
        self.lookahead_frame = Frame(self.frame, bg=AppStyle.BG_COLOR)
        self.lookahead_frame.grid(row=1, column=0, columnspan=4, sticky=W+E, padx=5, pady=5)
        
        # Listbox with scrollbar for lookaheads
        listbox_frame = Frame(self.lookahead_frame, bg=AppStyle.BG_COLOR)
        listbox_frame.grid(row=1, column=0, sticky=W+E)
        
        scrollbar = Scrollbar(listbox_frame)
        scrollbar.pack(side=RIGHT, fill="y")
        
        self.lookaheads_listbox = Listbox(listbox_frame, height=4, width=60, yscrollcommand=scrollbar.set,
                                          font=fnt.Font(size=config.font_size), bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
        self.lookaheads_listbox.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.config(command=self.lookaheads_listbox.yview)
        
        # Buttons frame
        buttons_frame = Frame(self.lookahead_frame, bg=AppStyle.BG_COLOR)
        buttons_frame.grid(row=1, column=1, sticky=W, padx=(5, 0))
        
        self.add_lookahead_btn = Button(buttons_frame, text=_("Add Lookahead"), command=self.add_lookahead)
        self.add_lookahead_btn.pack(side=TOP, pady=2)
        
        self.edit_lookahead_btn = Button(buttons_frame, text=_("Edit Lookahead"), command=self.edit_lookahead)
        self.edit_lookahead_btn.pack(side=TOP, pady=2)
        
        self.remove_lookahead_btn = Button(buttons_frame, text=_("Remove Lookahead"), command=self.remove_lookahead)
        self.remove_lookahead_btn.pack(side=TOP, pady=2)
        
        # Initialize lookaheads listbox
        self.refresh_lookaheads_listbox()
        
        self.lookahead_frame.columnconfigure(0, weight=1)

    def refresh_lookaheads_listbox(self):
        """Refresh the lookaheads listbox with current lookaheads."""
        if hasattr(self, 'lookaheads_listbox'):
            self.lookaheads_listbox.delete(0, "end")
            for lookahead in Lookahead.lookaheads:
                display_text = f"{lookahead.name} ({lookahead.name_or_text}, threshold: {lookahead.threshold:.2f})"
                self.lookaheads_listbox.insert("end", display_text)
    
    def add_lookahead(self):
        """Open dialog to add a new lookahead."""
        if PrevalidationsWindow.lookahead_window is not None:
            PrevalidationsWindow.lookahead_window.master.destroy()
        PrevalidationsWindow.lookahead_window = LookaheadWindow(
            self.master, self.app_actions, self.refresh_lookaheads_listbox)
    
    def edit_lookahead(self):
        """Open dialog to edit the selected lookahead."""
        selection = self.lookaheads_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        if idx < len(Lookahead.lookaheads):
            if PrevalidationsWindow.lookahead_window is not None:
                PrevalidationsWindow.lookahead_window.master.destroy()
            PrevalidationsWindow.lookahead_window = LookaheadWindow(
                self.master, self.app_actions, self.refresh_lookaheads_listbox, 
                Lookahead.lookaheads[idx])
    
    def remove_lookahead(self):
        """Remove the selected lookahead."""
        selection = self.lookaheads_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        if idx < len(Lookahead.lookaheads):
            lookahead = Lookahead.lookaheads[idx]
            # Check if any prevalidation is using this lookahead
            used_by = [pv.name for pv in ClassifierActionsManager.prevalidations if lookahead.name in pv.lookahead_names]
            if used_by:
                logger.warning(f"Lookahead {lookahead.name} is used by prevalidations: {', '.join(used_by)}")
            del Lookahead.lookaheads[idx]
            self.refresh_lookaheads_listbox()
            # Refresh modify window if open
            if PrevalidationsWindow.prevalidation_modify_window:
                PrevalidationsWindow.prevalidation_modify_window.refresh_lookahead_options()
    
    def add_profile_management_section(self):
        """Add a section for managing directory profiles."""
        
        # Profiles section title
        self.profiles_title = Label(self.frame, text=_("Directory Profiles"), 
                                   bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR, 
                                   font=fnt.Font(size=config.font_size + 2, weight="bold"))
        self.profiles_title.grid(row=2, column=0, columnspan=4, sticky=W, pady=(20, 10))
        
        # Create a separate frame for profiles
        self.profile_frame = Frame(self.frame, bg=AppStyle.BG_COLOR)
        self.profile_frame.grid(row=3, column=0, columnspan=4, sticky=W+E, padx=5, pady=5)
        
        # Listbox with scrollbar for profiles
        listbox_frame = Frame(self.profile_frame, bg=AppStyle.BG_COLOR)
        listbox_frame.grid(row=1, column=0, sticky=W+E)
        
        scrollbar = Scrollbar(listbox_frame)
        scrollbar.pack(side=RIGHT, fill="y")
        
        self.profiles_listbox = Listbox(listbox_frame, height=4, width=60, yscrollcommand=scrollbar.set,
                                        font=fnt.Font(size=config.font_size), bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
        self.profiles_listbox.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.config(command=self.profiles_listbox.yview)
        
        # Buttons frame
        buttons_frame = Frame(self.profile_frame, bg=AppStyle.BG_COLOR)
        buttons_frame.grid(row=1, column=1, sticky=W, padx=(5, 0))
        
        self.add_profile_btn = Button(buttons_frame, text=_("Add Profile"), command=self.add_profile)
        self.add_profile_btn.pack(side=TOP, pady=2)
        
        self.edit_profile_btn = Button(buttons_frame, text=_("Edit Profile"), command=self.edit_profile)
        self.edit_profile_btn.pack(side=TOP, pady=2)
        
        self.remove_profile_btn = Button(buttons_frame, text=_("Remove Profile"), command=self.remove_profile)
        self.remove_profile_btn.pack(side=TOP, pady=2)
        
        # Initialize profiles listbox
        self.refresh_profiles_listbox()
        
        self.profile_frame.columnconfigure(0, weight=1)

    def refresh_profiles_listbox(self):
        """Refresh the profiles listbox with current profiles."""
        if hasattr(self, 'profiles_listbox'):
            self.profiles_listbox.delete(0, "end")
            for profile in DirectoryProfile.directory_profiles:
                dir_count = len(profile.directories)
                dir_or_dirs = 'directory' if dir_count == 1 else 'directories'
                display_text = f"{profile.name} ({dir_count} {dir_or_dirs})"
                self.profiles_listbox.insert("end", display_text)
        
        # Refresh profile options in modify window if open
        if PrevalidationsWindow.prevalidation_modify_window:
            PrevalidationsWindow.prevalidation_modify_window.refresh_profile_options()
    
    def add_profile(self):
        """Open dialog to add a new profile."""
        if PrevalidationsWindow.profile_window is not None:
            PrevalidationsWindow.profile_window.master.destroy()
        PrevalidationsWindow.profile_window = DirectoryProfileWindow(
            self.master, self.app_actions, self.refresh_profiles_listbox)
    
    def edit_profile(self):
        """Open dialog to edit the selected profile."""
        selection = self.profiles_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        if idx < len(DirectoryProfile.directory_profiles):
            if PrevalidationsWindow.profile_window is not None:
                PrevalidationsWindow.profile_window.master.destroy()
            PrevalidationsWindow.profile_window = DirectoryProfileWindow(
                self.master, self.app_actions, self.refresh_profiles_listbox, 
                DirectoryProfile.directory_profiles[idx])
    
    def remove_profile(self):
        """Remove the selected profile."""
        selection = self.profiles_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        if idx < len(DirectoryProfile.directory_profiles):
            profile = DirectoryProfile.directory_profiles[idx]
            # Use ClassifierActionsManager to remove profile (checks usage and logs warnings)
            DirectoryProfile.remove_profile(profile.name)
            self.refresh_profiles_listbox()
            # Refresh modify window if open
            if PrevalidationsWindow.prevalidation_modify_window:
                PrevalidationsWindow.prevalidation_modify_window.refresh_profile_options()
    
    def add_prevalidation_widgets(self):
        # Start at row 6: after lookaheads (0-1), profiles (2-3), prevalidations title (4), enable checkbox (5)
        row = 6
        base_col = 0
        
        # Add header row
        header_font = fnt.Font(size=config.font_size, weight="bold")
        header_name = Label(self.frame, text=_("Name"), bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR, font=header_font)
        header_name.grid(row=row, column=base_col, sticky=W, padx=2, pady=2)
        
        header_action = Label(self.frame, text=_("Action"), bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR, font=header_font)
        header_action.grid(row=row, column=base_col + 1, sticky=W, padx=2, pady=2)
        
        header_profile = Label(self.frame, text=_("Profile"), bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR, font=header_font)
        header_profile.grid(row=row, column=base_col + 2, sticky=W, padx=2, pady=2)
        
        header_active = Label(self.frame, text=_("Active"), bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR, font=header_font)
        header_active.grid(row=row, column=base_col + 3, sticky=W, padx=2, pady=2)
        
        row += 1  # Move to first data row
        
        for i, prevalidation in enumerate(self.filtered_prevalidations):
            row = 7 + i  # Start data rows at row 7 (after header at row 6)
            label_name = Label(self.frame)
            self.label_list.append(label_name)
            self.add_label(label_name, str(prevalidation), row=row, column=base_col, wraplength=PrevalidationsWindow.COL_0_WIDTH)

            label_action = Label(self.frame)
            self.label_list2.append(label_action)
            self.add_label(label_action, prevalidation.action.get_translation(), row=row, column=base_col + 1)
            
            # Add profile column
            profile_text = ""
            if prevalidation.profile_name:
                profile_text = prevalidation.profile_name
            elif prevalidation.profile:
                profile_text = prevalidation.profile.name
            else:
                profile_text = _("(Global)")
            
            label_profile = Label(self.frame)
            self.add_label(label_profile, profile_text, row=row, column=base_col + 2)

            is_active_var = BooleanVar(value=prevalidation.is_active)
            def set_is_active_handler(prevalidation=prevalidation, var=is_active_var):
                prevalidation.is_active = var.get()
                logger.info(f"Set {prevalidation} to active: {prevalidation.is_active}")
            is_active_box = Checkbutton(self.frame, variable=is_active_var, font=fnt.Font(size=config.font_size), command=set_is_active_handler)
            is_active_box.grid(row=row, column=base_col + 3, sticky=(W))
            self.is_active_list.append(is_active_box)
            self.is_active_var_list.append(is_active_var)

            activate_prevalidation_var = BooleanVar(value=prevalidation.is_active)
            self.activate_prevalidation_choice = Checkbutton(self.frame, variable=activate_prevalidation_var, bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR, font=fnt.Font(size=config.font_size))
            set_prevalidation_btn = Button(self.frame, text=_("Set"))
            self.set_prevalidation_btn_list.append(set_prevalidation_btn)
            set_prevalidation_btn.grid(row=row, column=base_col+4)
            def set_prevalidation_handler(event, prevalidation=prevalidation, var=activate_prevalidation_var):
                prevalidation.is_active = var.get()
                logger.info(f"Set {prevalidation} to active: {prevalidation.is_active}")
            set_prevalidation_btn.bind("<Button-1>", set_prevalidation_handler)

            modify_prevalidation_btn = Button(self.frame, text=_("Modify"))
            self.set_prevalidation_btn_list.append(modify_prevalidation_btn)
            modify_prevalidation_btn.grid(row=row, column=base_col+5)
            def modify_prevalidation_handler(event, self=self, prevalidation=prevalidation):
                return self.open_prevalidation_modify_window(event, prevalidation)
            modify_prevalidation_btn.bind("<Button-1>", modify_prevalidation_handler)

            delete_prevalidation_btn = Button(self.frame, text=_("Delete"))
            self.delete_prevalidation_btn_list.append(delete_prevalidation_btn)
            delete_prevalidation_btn.grid(row=row, column=base_col+6)
            def delete_prevalidation_handler(event, self=self, prevalidation=prevalidation):
                return self.delete_prevalidation(event, prevalidation)
            delete_prevalidation_btn.bind("<Button-1>", delete_prevalidation_handler)

            move_down_btn = Button(self.frame, text=_("Move down"))
            self.move_down_btn_list.append(move_down_btn)
            move_down_btn.grid(row=row, column=base_col+7)
            def move_down_handler(event, self=self, idx=i, prevalidation=prevalidation):
                prevalidation.move_index(idx, 1)
                self.refresh()
            move_down_btn.bind("<Button-1>", move_down_handler)

    def open_prevalidation_modify_window(self, event=None, prevalidation=None):
        if PrevalidationsWindow.prevalidation_modify_window is not None:
            PrevalidationsWindow.prevalidation_modify_window.master.destroy()
        PrevalidationsWindow.prevalidation_modify_window = PrevalidationModifyWindow(
            self.master, self.app_actions, self.refresh_prevalidations, prevalidation)

    def refresh_prevalidations(self, prevalidation):
        # Check if this is a new prevalidation, if so, insert it at the start
        if prevalidation not in ClassifierActionsManager.prevalidations:
            ClassifierActionsManager.prevalidations.insert(0, prevalidation)
        self.filtered_prevalidations = ClassifierActionsManager.prevalidations[:]
        ClassifierActionsManager.prevalidated_cache.clear()
        # TODO only clear the actions that have been tested by the changed prevalidation.
        # Note that this includes the actions that have been tested by the prevalidations after the one changed
        # as well as any cached "None" values as this implies all prevalidations were tested for those images.
        # Perhaps better said, the actions that have not been tested by the prevalidation that was changed can be preserved.
        ClassifierActionsManager.directories_to_exclude.clear()
        for prevalidation in ClassifierActionsManager.prevalidations:
            if prevalidation.is_move_action():
                ClassifierActionsManager.directories_to_exclude.append(prevalidation.action_modifier)
        self.refresh()

    def delete_prevalidation(self, event=None, prevalidation=None):
        if prevalidation is not None and prevalidation in ClassifierActionsManager.prevalidations:
            ClassifierActionsManager.prevalidations.remove(prevalidation)
        self.refresh()

    def filter_prevalidations(self, event):
        """
        TODO

        Rebuild the filtered prevalidations list based on the filter string and update the UI.
        """
        modifier_key_pressed = (event.state & 0x1) != 0 or (event.state & 0x4) != 0 # Do not filter if modifier key is down
        if modifier_key_pressed:
            return
        if len(event.keysym) > 1:
            # If the key is up/down arrow key, roll the list up/down
            if event.keysym == "Down" or event.keysym == "Up":
                if event.keysym == "Down":
                    self.filtered_prevalidations = self.filtered_prevalidations[1:] + [self.filtered_prevalidations[0]]
                else:  # keysym == "Up"
                    self.filtered_prevalidations = [self.filtered_prevalidations[-1]] + self.filtered_prevalidations[:-1]
                self.clear_widget_lists()
                self.add_prevalidation_widgets()
                self.master.update()
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
            logger.info("Filter unset")
            # Restore the list of target directories to the full list
            self.filtered_prevalidations.clear()
            self.filtered_prevalidations = ClassifierActionsManager.prevalidations[:]
        else:
            temp = []
            return # TODO
            for prevalidation in ClassifierActionsManager.prevalidations:
                if prevalidation not in temp:
                    if prevalidation and (f" {self.filter_text}" in prevalidation.lower() or f"_{self.filter_text}" in prevalidation.lower()):
                        temp.append(prevalidation)
            self.filtered_prevalidations = temp[:]

        self.refresh()


    def do_action(self, event=None):
        """
        The user has requested to set a prevalidation. Based on the context, figure out what to do.

        If no prevalidations exist, call handle_prevalidation() with prevalidation=None to set a new prevalidation.

        If prevalidations exist, call set_prevalidation() to set the first prevalidation.

        If control key pressed, ignore existing and add a new prevalidation.

        If alt key pressed, use the penultimate prevalidation.

        The idea is the user can filter the directories using keypresses, then press enter to
        do the action on the first filtered tag.
        """
#        shift_key_pressed = (event.state & 0x1) != 0
        control_key_pressed = (event.state & 0x4) != 0
        alt_key_pressed = (event.state & 0x20000) != 0
        if alt_key_pressed:
            penultimate_prevalidation = PrevalidationsWindow.get_history_prevalidation(start_index=1)
            if penultimate_prevalidation is not None and os.path.isdir(penultimate_prevalidation):
                self.set_prevalidation(prevalidation=penultimate_prevalidation)
        elif len(self.filtered_prevalidations) == 0 or control_key_pressed:
            self.open_prevalidation_modify_window()
        else:
            if len(self.filtered_prevalidations) == 1 or self.filter_text.strip() != "":
                prevalidation = self.filtered_prevalidations[0]
            else:
                prevalidation = PrevalidationsWindow.last_set_prevalidation
            self.set_prevalidation(prevalidation=prevalidation)

    def toggle_prevalidations(self):
        config.enable_prevalidations = self.enable_prevalidations.get()

    def clear_recent_prevalidations(self, event=None):
        self.clear_widget_lists()
        ClassifierActionsManager.prevalidations.clear()
        self.filtered_prevalidations.clear()
        self.add_prevalidation_widgets()
        self.master.update()

    def clear_widget_lists(self):
        for label in self.label_list:
            label.destroy()
        for label in self.label_list2:
            label.destroy()
        for chkbtn in self.is_active_list:
            chkbtn.destroy()
        for btn in self.set_prevalidation_btn_list:
            btn.destroy()
        for btn in self.modify_prevalidation_btn_list:
            btn.destroy()
        for btn in self.delete_prevalidation_btn_list:
            btn.destroy()
        for btn in self.move_down_btn_list:
            btn.destroy()
        # Clear lookahead section widgets
        if hasattr(self, 'lookaheads_title'):
            self.lookaheads_title.destroy()
        if hasattr(self, 'lookahead_frame'):
            self.lookahead_frame.destroy()
        self.label_list = []
        self.label_list2 = []
        self.is_active_list = []
        self.set_prevalidation_btn_list = []
        self.modify_prevalidation_btn_list = []
        self.delete_prevalidation_btn_list = []
        self.move_down_btn_list = []

    def refresh(self, refresh_list=True):
        self.filtered_prevalidations = ClassifierActionsManager.prevalidations[:]
        self.clear_widget_lists()
        self.add_prevalidation_widgets()
        # Re-add lookahead section after prevalidations
        self.add_lookahead_management_section()
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


