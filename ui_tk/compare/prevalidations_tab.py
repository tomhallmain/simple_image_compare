from typing import Optional

from tkinter import Frame, Label, Checkbutton, BooleanVar, StringVar, LEFT, W, Scrollbar, Listbox, BOTH, RIGHT, TOP, E
import tkinter.font as fnt
from tkinter.ttk import Button, Combobox

from compare.classifier_actions_manager import Prevalidation, ClassifierActionsManager
from compare.lookahead import Lookahead
from lib.multiselect_dropdown import MultiSelectDropdown
from ui_tk.compare.classifier_action_copy_window import ClassifierActionCopyWindow
from ui_tk.compare.classifier_management_window import ClassifierActionModifyWindow
from ui_tk.compare.lookahead_window import LookaheadWindow
from ui_tk.files.directory_profile_window import DirectoryProfileWindow
from utils.app_style import AppStyle
from utils.config import config
from utils.logging_setup import get_logger
from utils.translations import I18N

_ = I18N._
logger = get_logger("prevalidations_tab")


class PrevalidationModifyWindow(ClassifierActionModifyWindow):
    top_level = None

    def __init__(self, master, app_actions, refresh_callback, prevalidation, dimensions="600x600"):
        prevalidation = prevalidation if prevalidation is not None else Prevalidation()
        super().__init__(
            master, app_actions, refresh_callback, prevalidation,
            _("Modify Prevalidation"), _("Prevalidation Name"),
            _("New Prevalidation"), dimensions
        )
        PrevalidationModifyWindow.top_level = self.top_level

    def add_specific_fields(self, row):
        """Add prevalidation-specific fields (lookaheads and profile)."""
        row += 1
        # Prevalidation Lookaheads section
        self.label_lookaheads = Label(self.frame)
        self.add_label(
            self.label_lookaheads,
            _("Lookaheads (select from shared list)"),
            row=row, wraplength=self.COL_0_WIDTH
        )
        
        # Multi-select dropdown for lookaheads
        lookahead_options = [lookahead.name for lookahead in Lookahead.lookaheads]
        self.lookaheads_multiselect = MultiSelectDropdown(
            self.frame, lookahead_options[:],
            row=row, column=1, sticky=W,
            select_text=_("Select Lookaheads..."),
            selected=self.classifier_action.lookahead_names[:],
            command=self.set_lookahead_names
        )
        
        row += 1
        # Profile selection
        self.label_profile = Label(self.frame)
        self.add_label(
            self.label_profile,
            _("Directory Profile"),
            row=row, wraplength=self.COL_0_WIDTH
        )
        
        # Profile dropdown - include "(Global)" option for no profile
        profile_options = [""]  # Empty string = Global
        profile_options.extend([profile.name for profile in DirectoryProfile.directory_profiles])
        
        current_profile_name = self.classifier_action.profile_name if self.classifier_action.profile_name else ""
        self.profile_var = StringVar(self.master, value=current_profile_name)
        self.profile_choice = Combobox(
            self.frame, textvariable=self.profile_var,
            values=profile_options, width=47,
            font=fnt.Font(size=config.font_size)
        )
        # Set current selection
        if current_profile_name in profile_options:
            self.profile_choice.current(profile_options.index(current_profile_name))
        else:
            self.profile_choice.current(0)  # Default to Global
        self.profile_choice.bind("<<ComboboxSelected>>", self.set_profile_name)
        self.profile_choice.grid(row=row, column=1, sticky=W)
        AppStyle.setup_combobox_style(self.profile_choice)
        
        return row

    def set_lookahead_names(self, event=None):
        """Set the selected lookahead names for this prevalidation."""
        self.classifier_action.lookahead_names = list(self.lookaheads_multiselect.get_selected())
    
    def set_profile_name(self, event=None):
        """Set the profile name for this prevalidation."""
        selected_profile_name = self.profile_var.get().strip()
        # Empty string means Global (no profile)
        profile_name = selected_profile_name if selected_profile_name else None
        self.classifier_action.update_profile_instance(profile_name=profile_name)
    
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
            self.classifier_action.lookahead_names[:]
        )
    
    def finalize_specific(self):
        """Add prevalidation-specific finalization."""
        self.set_lookahead_names()
        self.set_profile_name()



class PrevalidationsTab:
    """
    Tab content class for managing prevalidations.
    Can be used either standalone (as PrevalidationsWindow) or as a tab in a notebook.
    """
    prevalidation_modify_window: Optional[PrevalidationModifyWindow] = None
    lookahead_window: Optional[LookaheadWindow] = None
    profile_window: Optional[DirectoryProfileWindow] = None

    MAX_PRESETS = 50

    MAX_HEIGHT = 900
    N_TAGS_CUTOFF = 30
    COL_0_WIDTH = 600

    @staticmethod
    def _is_modify_window_valid() -> bool:
        """Check if the prevalidation modify window still exists and is valid."""
        if PrevalidationsTab.prevalidation_modify_window is None:
            return False
        try:
            return (hasattr(PrevalidationsTab.prevalidation_modify_window, 'top_level') and
                    PrevalidationsTab.prevalidation_modify_window.top_level is not None and
                    PrevalidationsTab.prevalidation_modify_window.top_level.winfo_exists())
        except Exception:
            # Window was destroyed, clear the reference
            PrevalidationsTab.prevalidation_modify_window = None
            return False

    @staticmethod
    def clear_prevalidated_cache():
        ClassifierActionsManager.prevalidated_cache.clear()

    @staticmethod
    def prevalidate(image_path, get_base_dir_func, hide_callback, notify_callback, add_mark_callback):
        """
        Prevalidate an image using active prevalidations.
        
        Args:
            image_path: Path to the image to prevalidate
            get_base_dir_func: Function to get the base directory
            hide_callback: Callback for hiding images
            notify_callback: Callback for notifications
            add_mark_callback: Callback for marking images
            
        Returns:
            Optional[ClassifierActionType]: The action type if prevalidation matched, None otherwise
        """
        return ClassifierActionsManager.prevalidate(
            image_path, get_base_dir_func, hide_callback, notify_callback, add_mark_callback
        )

    def __init__(self, parent_frame, app_actions):
        """
        Initialize the prevalidations tab.
        
        Args:
            parent_frame: Parent frame (can be a Toplevel or a Frame in a notebook)
            app_actions: Application actions object
        """
        self.app_actions = app_actions
        self.filter_text = ""
        self.filtered_prevalidations = ClassifierActionsManager.prevalidations[:]
        self.label_list = []
        self.label_list2 = []
        self.is_active_var_list = []
        self.is_active_list = []
        self.set_prevalidation_btn_list = []
        self.modify_prevalidation_btn_list = []
        self.copy_prevalidation_btn_list = []
        self.delete_prevalidation_btn_list = []
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
        self.frame.columnconfigure(7, weight=1)
        self.frame.columnconfigure(8, weight=1)
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
        self.enable_prevalidations = BooleanVar(self.master, value=config.enable_prevalidations)
        self.checkbox_enable_prevalidations = Checkbutton(self.frame, variable=self.enable_prevalidations, 
                                                        command=self.toggle_prevalidations)
        self.add_label(self.label_enable_prevalidations, _("Enable Prevalidations"), row=5, wraplength=PrevalidationsTab.COL_0_WIDTH)
        self.checkbox_enable_prevalidations.grid(row=5, column=1, sticky=W)

        self.add_prevalidation_widgets()

        self.frame.update()



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
        # Bind double-click to edit lookahead
        self.lookaheads_listbox.bind("<Double-Button-1>", lambda event: self.edit_lookahead())
        
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
                display_text = _("{name} ({name_or_text}, threshold: {threshold:.2f})").format(name=lookahead.name, name_or_text=lookahead.name_or_text, threshold=lookahead.threshold)
                self.lookaheads_listbox.insert("end", display_text)
    
    def add_lookahead(self):
        """Open dialog to add a new lookahead."""
        if PrevalidationsTab.lookahead_window is not None:
            PrevalidationsTab.lookahead_window.master.destroy()
        PrevalidationsTab.lookahead_window = LookaheadWindow(
            self.master, self.app_actions, self.refresh_lookaheads_listbox)
    
    def edit_lookahead(self):
        """Open dialog to edit the selected lookahead."""
        selection = self.lookaheads_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        if idx < len(Lookahead.lookaheads):
            if PrevalidationsTab.lookahead_window is not None:
                PrevalidationsTab.lookahead_window.master.destroy()
            PrevalidationsTab.lookahead_window = LookaheadWindow(
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
            if PrevalidationsTab._is_modify_window_valid():
                try:
                    PrevalidationsTab.prevalidation_modify_window.refresh_lookahead_options()
                except Exception:
                    # Window was destroyed during refresh, clear the reference
                    PrevalidationsTab.prevalidation_modify_window = None
    
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
        # Bind double-click to edit profile
        self.profiles_listbox.bind("<Double-Button-1>", lambda event: self.edit_profile())
        
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
                dir_or_dirs = _('directory') if dir_count == 1 else _('directories')
                display_text = f"{profile.name} ({dir_count} {dir_or_dirs})"
                self.profiles_listbox.insert("end", display_text)
        
        # Refresh profile options in modify window if open and still exists
        if PrevalidationsTab._is_modify_window_valid():
            try:
                PrevalidationsTab.prevalidation_modify_window.refresh_profile_options()
            except Exception:
                # Window was destroyed during refresh, clear the reference
                PrevalidationsTab.prevalidation_modify_window = None
    
    def add_profile(self):
        """Open dialog to add a new profile."""
        if PrevalidationsTab.profile_window is not None:
            PrevalidationsTab.profile_window.master.destroy()
        PrevalidationsTab.profile_window = DirectoryProfileWindow(
            self.master, self.app_actions, self.refresh_profiles_listbox)
    
    def edit_profile(self):
        """Open dialog to edit the selected profile."""
        selection = self.profiles_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        if idx < len(DirectoryProfile.directory_profiles):
            if PrevalidationsTab.profile_window is not None:
                PrevalidationsTab.profile_window.master.destroy()
            PrevalidationsTab.profile_window = DirectoryProfileWindow(
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
            if PrevalidationsTab._is_modify_window_valid():
                try:
                    PrevalidationsTab.prevalidation_modify_window.refresh_profile_options()
                except Exception:
                    # Window was destroyed during refresh, clear the reference
                    PrevalidationsTab.prevalidation_modify_window = None
    
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
            self.add_label(label_name, str(prevalidation), row=row, column=base_col, wraplength=PrevalidationsTab.COL_0_WIDTH)

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
            self.modify_prevalidation_btn_list.append(modify_prevalidation_btn)
            modify_prevalidation_btn.grid(row=row, column=base_col+5)
            def modify_prevalidation_handler(event, self=self, prevalidation=prevalidation):
                return self.open_prevalidation_modify_window(event, prevalidation)
            modify_prevalidation_btn.bind("<Button-1>", modify_prevalidation_handler)

            copy_prevalidation_btn = Button(self.frame, text=_("Copy"))
            self.copy_prevalidation_btn_list.append(copy_prevalidation_btn)
            copy_prevalidation_btn.grid(row=row, column=base_col+6)
            def copy_prevalidation_handler(event, self=self, prevalidation=prevalidation):
                return self.open_prevalidation_copy_window(event, prevalidation)
            copy_prevalidation_btn.bind("<Button-1>", copy_prevalidation_handler)

            delete_prevalidation_btn = Button(self.frame, text=_("Delete"))
            self.delete_prevalidation_btn_list.append(delete_prevalidation_btn)
            delete_prevalidation_btn.grid(row=row, column=base_col+7)
            def delete_prevalidation_handler(event, self=self, prevalidation=prevalidation):
                return self.delete_prevalidation(event, prevalidation)
            delete_prevalidation_btn.bind("<Button-1>", delete_prevalidation_handler)

            move_down_btn = Button(self.frame, text=_("Move down"))
            self.move_down_btn_list.append(move_down_btn)
            move_down_btn.grid(row=row, column=base_col+8)
            def move_down_handler(event, self=self, idx=i, prevalidation=prevalidation):
                prevalidation.move_index(idx, 1)
                self.refresh()
            move_down_btn.bind("<Button-1>", move_down_handler)

    def open_prevalidation_modify_window(self, event=None, prevalidation=None):
        if PrevalidationsTab.prevalidation_modify_window is not None:
            PrevalidationsTab.prevalidation_modify_window.master.destroy()
        PrevalidationsTab.prevalidation_modify_window = PrevalidationModifyWindow(
            self.master, self.app_actions, self.refresh_prevalidations, prevalidation)

    def open_prevalidation_copy_window(self, event=None, prevalidation=None):
        """Open the copy window for a prevalidation."""
        ClassifierActionCopyWindow(
            self.master, self.app_actions, prevalidation, 
            source_type="prevalidation",
            refresh_classifier_actions_callback=self.refresh_classifier_actions if hasattr(self, 'refresh_classifier_actions') else None,
            refresh_prevalidations_callback=self.refresh_prevalidations
        )

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
            # Remove from initialized set if present
            ClassifierActionsManager._initialized_prevalidations.discard(prevalidation)
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
        # Note: This method appears to be incomplete/dead code
        # The referenced methods (get_history_prevalidation, last_set_prevalidation, set_prevalidation) don't exist
        # Keeping the structure but commenting out broken references
        if alt_key_pressed:
            # penultimate_prevalidation = PrevalidationsTab.get_history_prevalidation(start_index=1)
            # if penultimate_prevalidation is not None and os.path.isdir(penultimate_prevalidation):
            #     self.set_prevalidation(prevalidation=penultimate_prevalidation)
            pass
        elif len(self.filtered_prevalidations) == 0 or control_key_pressed:
            self.open_prevalidation_modify_window()
        else:
            if len(self.filtered_prevalidations) == 1 or self.filter_text.strip() != "":
                prevalidation = self.filtered_prevalidations[0]
                # self.set_prevalidation(prevalidation=prevalidation)
            # else:
            #     prevalidation = PrevalidationsTab.last_set_prevalidation
            #     self.set_prevalidation(prevalidation=prevalidation)

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
        for btn in self.copy_prevalidation_btn_list:
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
        self.copy_prevalidation_btn_list = []
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


