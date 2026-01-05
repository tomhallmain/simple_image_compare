from tkinter import Frame, Label, BooleanVar, StringVar, Entry, W, E, N, S
from tkinter.ttk import Checkbutton, Button, OptionMenu, Separator
from typing import Optional, Dict

from lib.multi_display import SmartToplevel
from compare.compare_manager import CompareManager, CombinationLogic, SizeFilter, ModelFilter
from utils.app_style import AppStyle
from utils.config import config
from utils.constants import CompareMode
from utils.translations import I18N
from utils.logging_setup import get_logger

_ = I18N._
logger = get_logger("compare_settings_window")


class CompareSettingsWindow:
    """Window for configuring comparison modes, filters, and composite search settings"""
    
    _open_windows: Dict[object, 'CompareSettingsWindow'] = {}  # Track open windows per compare_manager
    
    def __init__(self, parent, compare_manager: CompareManager):
        self.parent = parent
        self.compare_manager = compare_manager
        
        # Check if window already exists for this manager
        if compare_manager in CompareSettingsWindow._open_windows:
            existing_window = CompareSettingsWindow._open_windows[compare_manager]
            existing_window.window.lift()
            return
        
        # Store reference
        CompareSettingsWindow._open_windows[compare_manager] = self
        
        # Create window
        self.window = SmartToplevel(
            persistent_parent=parent,
            title=_("Compare Settings"),
            geometry="1000x700"
        )
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.window.bind("<Escape>", lambda e: self.on_closing())
        
        # Main frame
        self.frame = Frame(self.window, bg=AppStyle.BG_COLOR)
        self.frame.pack(fill='both', expand=True, padx=20, pady=20)
        self.frame.columnconfigure(0, weight=1)
        self.frame.columnconfigure(1, weight=1)
        
        # Title
        title_label = Label(
            self.frame,
            text=_("Compare Settings"),
            font=('Helvetica', 14, 'bold'),
            bg=AppStyle.BG_COLOR,
            fg=AppStyle.FG_COLOR
        )
        title_label.grid(row=0, column=0, columnspan=2, sticky=W, pady=(0, 20))
        
        row = 1
        
        # Mode selection section
        mode_frame = Frame(self.frame, bg=AppStyle.BG_COLOR)
        mode_frame.grid(row=row, column=0, sticky='ew', pady=(0, 10))
        mode_frame.columnconfigure(0, weight=1)
        row += 1
        
        mode_title = Label(
            mode_frame,
            text=_("Comparison Modes"),
            font=('Helvetica', 11, 'bold'),
            bg=AppStyle.BG_COLOR,
            fg=AppStyle.FG_COLOR
        )
        mode_title.grid(row=0, column=0, sticky=W, pady=(0, 10))
        
        # Mode instance management
        # For now, show checkboxes for modes (backward compatibility)
        # TODO: Replace with instance list UI that allows multiple instances per mode
        self.mode_vars: Dict[CompareMode, BooleanVar] = {}
        self.mode_checkboxes: Dict[CompareMode, Checkbutton] = {}
        
        active_modes = compare_manager.get_active_modes()
        primary_mode = compare_manager.compare_mode
        
        for i, mode in enumerate(CompareMode):
            var = BooleanVar(value=(mode in active_modes or mode == primary_mode))
            self.mode_vars[mode] = var
            
            check = Checkbutton(
                mode_frame,
                text=mode.get_text(),
                variable=var,
                command=lambda m=mode: self._on_mode_toggled(m)
            )
            check.grid(row=i+1, column=0, sticky=W, pady=2)
            self.mode_checkboxes[mode] = check
        
        # Add button to add instance of selected mode
        self.add_instance_btn = Button(
            mode_frame,
            text=_("Add Instance"),
            command=self._on_add_instance
        )
        self.add_instance_btn.grid(row=len(CompareMode)+1, column=0, sticky=W, pady=5)
        
        row += 1
        
        # Separator
        sep1 = Separator(self.frame, orient='horizontal')
        sep1.grid(row=row, column=0, sticky='ew', pady=10)
        row += 1
        
        # Combination logic section
        logic_frame = Frame(self.frame, bg=AppStyle.BG_COLOR)
        logic_frame.grid(row=row, column=0, sticky='ew', pady=(0, 10))
        logic_frame.columnconfigure(1, weight=1)
        row += 1
        
        logic_label = Label(
            logic_frame,
            text=_("Combination Logic:"),
            bg=AppStyle.BG_COLOR,
            fg=AppStyle.FG_COLOR
        )
        logic_label.grid(row=0, column=0, sticky=W, padx=(0, 10))
        
        self.logic_var = StringVar(value=compare_manager.get_combination_logic().value)
        logic_options = [logic.value for logic in CombinationLogic]
        logic_menu = OptionMenu(
            logic_frame,
            self.logic_var,
            *logic_options,
            command=self._on_logic_changed
        )
        logic_menu.grid(row=0, column=1, sticky=W)
        
        # Weight controls (for weighted mode)
        self.weight_frame = Frame(self.frame, bg=AppStyle.BG_COLOR)
        self.weight_frame.grid(row=row, column=0, sticky='ew', pady=(0, 10))
        self.weight_frame.columnconfigure(1, weight=1)
        row += 1
        
        self.weight_vars: Dict[CompareMode, StringVar] = {}
        self.weight_entries: Dict[CompareMode, Entry] = {}
        
        self._update_weight_controls_visibility()
        
        row += 1
        
        # Track row for column 1 (right column) - start aligned with Comparison Modes
        row_col1 = 1
        
        # Compare Settings section (Column 1) - wrap in frame to match left column structure
        settings_frame = Frame(self.frame, bg=AppStyle.BG_COLOR)
        settings_frame.grid(row=row_col1, column=1, sticky='new', pady=(0, 10), padx=(20, 0))
        settings_frame.columnconfigure(0, weight=1)
        
        settings_title = Label(
            settings_frame,
            text=_("Compare Settings"),
            font=('Helvetica', 11, 'bold'),
            bg=AppStyle.BG_COLOR,
            fg=AppStyle.FG_COLOR
        )
        settings_title.grid(row=0, column=0, sticky=W, pady=(0, 10))
        
        # Start tracking rows within settings_frame (starting at row 1, after title)
        row_col1_inner = 1
        
        # Get current values from compare_manager's primary wrapper args
        current_args = compare_manager.get_args()
        primary_mode = compare_manager.compare_mode
        
        # Threshold setting
        self.threshold_frame = Frame(settings_frame, bg=AppStyle.BG_COLOR)
        self.threshold_frame.grid(row=row_col1_inner, column=0, sticky='ew', pady=(0, 10))
        self.threshold_frame.columnconfigure(1, weight=1)
        row_col1_inner += 1
        
        threshold_label = Label(
            self.threshold_frame,
            text=_("Threshold"),
            bg=AppStyle.BG_COLOR,
            fg=AppStyle.FG_COLOR
        )
        threshold_label.grid(row=0, column=0, sticky=W, padx=(0, 10))
        
        self.threshold_var = StringVar()
        if primary_mode:
            if primary_mode == CompareMode.COLOR_MATCHING:
                default_val = config.color_diff_threshold
            else:
                default_val = config.embedding_similarity_threshold
            self.threshold_var.set(str(current_args.threshold if hasattr(current_args, 'threshold') else default_val))
        else:
            self.threshold_var.set(str(config.embedding_similarity_threshold))
        
        # Initialize threshold_menu to None before creating it
        self.threshold_menu = None
        
        # Create threshold menu
        threshold_vals = primary_mode.threshold_vals() if primary_mode else CompareMode.CLIP_EMBEDDING.threshold_vals()
        if threshold_vals is None:
            # Fallback to embedding threshold values if mode doesn't return values
            threshold_vals = CompareMode.CLIP_EMBEDDING.threshold_vals()
        self.threshold_menu = OptionMenu(
            self.threshold_frame,
            self.threshold_var,
            self.threshold_var.get(),
            *threshold_vals
        )
        self.threshold_menu.grid(row=0, column=1, sticky=W)
        
        # Counter limit setting
        self.counter_limit_frame = Frame(settings_frame, bg=AppStyle.BG_COLOR)
        self.counter_limit_frame.grid(row=row_col1_inner, column=0, sticky='ew', pady=(0, 10))
        self.counter_limit_frame.columnconfigure(1, weight=1)
        row_col1_inner += 1
        
        counter_limit_label = Label(
            self.counter_limit_frame,
            text=_("Max files to compare"),
            bg=AppStyle.BG_COLOR,
            fg=AppStyle.FG_COLOR
        )
        counter_limit_label.grid(row=0, column=0, sticky=W, padx=(0, 10))
        
        self.counter_limit_var = StringVar()
        counter_limit_value = current_args.counter_limit if hasattr(current_args, 'counter_limit') else config.file_counter_limit
        if counter_limit_value is None:
            self.counter_limit_var.set("")
        else:
            self.counter_limit_var.set(str(counter_limit_value))
        
        self.counter_limit_entry = Entry(
            self.counter_limit_frame,
            textvariable=self.counter_limit_var,
            width=15
        )
        self.counter_limit_entry.grid(row=0, column=1, sticky=W)
        
        # Compare faces checkbox
        self.compare_faces_var = BooleanVar(value=current_args.compare_faces if hasattr(current_args, 'compare_faces') else False)
        compare_faces_check = Checkbutton(
            settings_frame,
            text=_('Compare faces'),
            variable=self.compare_faces_var
        )
        compare_faces_check.grid(row=row_col1_inner, column=0, sticky=W, pady=2)
        row_col1_inner += 1
        
        # Overwrite cache checkbox
        self.overwrite_var = BooleanVar(value=current_args.overwrite if hasattr(current_args, 'overwrite') else False)
        overwrite_check = Checkbutton(
            settings_frame,
            text=_('Overwrite cache'),
            variable=self.overwrite_var
        )
        overwrite_check.grid(row=row_col1_inner, column=0, sticky=W, pady=2)
        row_col1_inner += 1
        
        # Store checkpoints checkbox
        self.store_checkpoints_var = BooleanVar(value=current_args.store_checkpoints if hasattr(current_args, 'store_checkpoints') else config.store_checkpoints)
        store_checkpoints_check = Checkbutton(
            settings_frame,
            text=_('Store checkpoints'),
            variable=self.store_checkpoints_var
        )
        store_checkpoints_check.grid(row=row_col1_inner, column=0, sticky=W, pady=2)
        row_col1_inner += 1
        
        # Search only return closest checkbox
        self.search_only_return_closest_var = BooleanVar(value=config.search_only_return_closest)
        search_only_return_closest_check = Checkbutton(
            settings_frame,
            text=_('Search only return closest'),
            variable=self.search_only_return_closest_var
        )
        search_only_return_closest_check.grid(row=row_col1_inner, column=0, sticky=W, pady=2)
        row_col1_inner += 1
        
        # Separator for Filters section - place after settings_frame content
        # Find where the left column's separator is to align
        sep_filter = Separator(self.frame, orient='horizontal')
        sep_filter.grid(row=row, column=1, sticky='ew', pady=10, padx=(20, 0))
        
        # Filtering section (Column 1) - wrap in frame to match structure
        # Place it right after the separator, before the bottom separator
        filter_frame = Frame(self.frame, bg=AppStyle.BG_COLOR)
        filter_frame.grid(row=row+1, column=1, sticky='new', pady=(0, 10), padx=(20, 0))
        filter_frame.columnconfigure(0, weight=1)
        
        filter_title = Label(
            filter_frame,
            text=_("Filters (Applied Before Comparison)"),
            font=('Helvetica', 11, 'bold'),
            bg=AppStyle.BG_COLOR,
            fg=AppStyle.FG_COLOR
        )
        filter_title.grid(row=0, column=0, sticky=W, pady=(0, 10))
        
        # Size filter
        size_filter_frame = Frame(filter_frame, bg=AppStyle.BG_COLOR)
        size_filter_frame.grid(row=1, column=0, sticky='ew', pady=(0, 10))
        size_filter_frame.columnconfigure(1, weight=1)
        
        size_filter_label = Label(
            size_filter_frame,
            text=_("Size Filter:"),
            bg=AppStyle.BG_COLOR,
            fg=AppStyle.FG_COLOR
        )
        size_filter_label.grid(row=0, column=0, sticky=W, padx=(0, 10))
        
        # Size filter inputs (simplified - full UI can be expanded later)
        size_note = Label(
            size_filter_frame,
            text=_("(Size filtering UI to be implemented)"),
            font=('Helvetica', 9),
            bg=AppStyle.BG_COLOR,
            fg=AppStyle.FG_COLOR
        )
        size_note.grid(row=0, column=1, sticky=W)
        
        # Model filter
        model_filter_frame = Frame(filter_frame, bg=AppStyle.BG_COLOR)
        model_filter_frame.grid(row=2, column=0, sticky='ew', pady=(0, 10))
        model_filter_frame.columnconfigure(1, weight=1)
        
        model_filter_label = Label(
            model_filter_frame,
            text=_("Model Filter:"),
            bg=AppStyle.BG_COLOR,
            fg=AppStyle.FG_COLOR
        )
        model_filter_label.grid(row=0, column=0, sticky=W, padx=(0, 10))
        
        # Model filter inputs (simplified - full UI can be expanded later)
        model_note = Label(
            model_filter_frame,
            text=_("(Model filtering UI to be implemented)"),
            font=('Helvetica', 9),
            bg=AppStyle.BG_COLOR,
            fg=AppStyle.FG_COLOR
        )
        model_note.grid(row=0, column=1, sticky=W)
        
        # Bottom separator - place after Filters section
        # Filters section is at row+1, and contains title + 2 filter items
        # Place separator at row+4 to give enough space for Filters content
        bottom_sep_row = row + 4
        
        # Separator
        sep3 = Separator(self.frame, orient='horizontal')
        sep3.grid(row=bottom_sep_row, column=0, columnspan=2, sticky='ew', pady=10)
        row = bottom_sep_row + 1
        
        # Buttons
        button_frame = Frame(self.frame, bg=AppStyle.BG_COLOR)
        button_frame.grid(row=row, column=0, columnspan=2, sticky='ew', pady=(10, 0))
        row += 1
        
        self.apply_btn = Button(
            button_frame,
            text=_("Apply"),
            command=self._on_apply
        )
        self.apply_btn.pack(side='left', padx=(0, 10))
        
        self.cancel_btn = Button(
            button_frame,
            text=_("Cancel"),
            command=self.on_closing
        )
        self.cancel_btn.pack(side='left')
        
        # Focus
        self.window.after(1, lambda: self.frame.focus_force())
    
    def _update_threshold_menu(self, mode: Optional[CompareMode]):
        """Update threshold menu based on current primary mode."""
        # Destroy existing menu if it exists
        if self.threshold_menu is not None:
            self.threshold_menu.destroy()
            self.threshold_menu = None
        
        if mode is None:
            return
        
        # Get threshold values for this mode
        threshold_vals = mode.threshold_vals()
        
        # Fallback to embedding threshold values if mode doesn't return values
        if threshold_vals is None:
            threshold_vals = CompareMode.CLIP_EMBEDDING.threshold_vals()
        
        # Find threshold frame by searching for the label
        threshold_frame = None
        for widget in self.frame.winfo_children():
            if isinstance(widget, Frame):
                for child in widget.winfo_children():
                    if isinstance(child, Label) and child.cget('text') == _("Threshold:"):
                        threshold_frame = widget
                        break
                if threshold_frame:
                    break
        
        if self.threshold_frame:
            # Update threshold value if current value not in new list
            current_val = self.threshold_var.get()
            if threshold_vals and current_val not in threshold_vals:
                # Set to default for this mode
                if mode == CompareMode.COLOR_MATCHING:
                    default_val = config.color_diff_threshold
                else:
                    default_val = config.embedding_similarity_threshold
                self.threshold_var.set(str(default_val))
            
            # Create new menu
            if threshold_vals:
                self.threshold_menu = OptionMenu(
                    self.threshold_frame,
                    self.threshold_var,
                    self.threshold_var.get(),
                    *threshold_vals
                )
                self.threshold_menu.grid(row=0, column=1, sticky=W)
    
    def _on_mode_toggled(self, mode: CompareMode):
        """Handle mode checkbox toggle."""
        var = self.mode_vars[mode]
        if var.get():
            self.compare_manager.add_mode(mode)
            # Update primary mode if it's the first one
            if self.compare_manager.compare_mode is None:
                self.compare_manager.set_primary_mode(mode)
        else:
            # Don't allow removing the last mode
            active_modes = self.compare_manager.get_active_modes()
            if len(active_modes) <= 1 and mode in active_modes:
                var.set(True)  # Re-check it
                return
            self.compare_manager.remove_mode(mode)
        
        # Update threshold menu when primary mode changes
        primary_mode = self.compare_manager.compare_mode
        self._update_threshold_menu(primary_mode)
        
        self._update_weight_controls_visibility()
    
    def _on_logic_changed(self, logic_str: str):
        """Handle combination logic change."""
        try:
            logic = CombinationLogic(logic_str)
            self.compare_manager.set_combination_logic(logic)
            self._update_weight_controls_visibility()
        except ValueError:
            logger.warning(f"Invalid combination logic: {logic_str}")
    
    def _update_weight_controls_visibility(self):
        """Show/hide weight controls based on combination logic."""
        # Clear existing weight controls
        for widget in self.weight_frame.winfo_children():
            widget.destroy()
        
        # Only show weights for WEIGHTED mode
        if self.compare_manager.get_combination_logic() == CombinationLogic.WEIGHTED:
            mode_instances = self.compare_manager.get_mode_instances()
            
            weight_label = Label(
                self.weight_frame,
                text=_("Instance Weights:"),
                bg=AppStyle.BG_COLOR,
                fg=AppStyle.FG_COLOR
            )
            weight_label.grid(row=0, column=0, sticky=W, pady=(0, 5))
            
            for i, config in enumerate(mode_instances):
                if not config.enabled:
                    continue
                
                instance_label = Label(
                    self.weight_frame,
                    text=f"{config.instance_id} ({config.compare_mode.get_text()}):",
                    bg=AppStyle.BG_COLOR,
                    fg=AppStyle.FG_COLOR
                )
                instance_label.grid(row=i+1, column=0, sticky=W, padx=(20, 10), pady=2)
                
                weight = config.weight
                weight_var = StringVar(value=str(weight))
                self.weight_vars[config.instance_id] = weight_var
                
                weight_entry = Entry(
                    self.weight_frame,
                    textvariable=weight_var,
                    width=10
                )
                weight_entry.grid(row=i+1, column=1, sticky=W, pady=2)
                self.weight_entries[config.instance_id] = weight_entry
    
    def _on_add_instance(self):
        """Add a new instance of a mode."""
        # TODO: Show dialog to select mode and configure instance
        # For now, just log that this feature needs UI implementation
        logger.info("Add instance feature - UI implementation needed")
    
    def _on_apply(self):
        """Apply settings and close window."""
        # Update weights if in weighted mode
        if self.compare_manager.get_combination_logic() == CombinationLogic.WEIGHTED:
            for instance_id, weight_var in self.weight_vars.items():
                try:
                    weight = float(weight_var.get())
                    self.compare_manager.set_mode_weight(instance_id, weight)
                    logger.debug(f"Setting weight for instance {instance_id} to {weight}")
                except ValueError:
                    logger.warning(f"Invalid weight for instance {instance_id}: {weight_var.get()}")
        
        # Update compare settings
        primary_mode = self.compare_manager.compare_mode
        if primary_mode:
            try:
                threshold_str = self.threshold_var.get().strip()
                if primary_mode == CompareMode.COLOR_MATCHING:
                    threshold = int(threshold_str)
                else:
                    threshold = float(threshold_str)
                self.compare_manager.set_threshold(threshold)
            except ValueError:
                logger.warning(f"Invalid threshold: {self.threshold_var.get()}")
        
        # Update counter limit
        try:
            counter_limit_str = self.counter_limit_var.get().strip()
            if counter_limit_str == "":
                self.compare_manager.set_counter_limit(None)
            else:
                counter_limit = int(counter_limit_str)
                self.compare_manager.set_counter_limit(counter_limit)
        except ValueError:
            logger.warning(f"Invalid counter limit: {self.counter_limit_var.get()}")
        
        self.compare_manager.set_compare_faces(self.compare_faces_var.get())
        self.compare_manager.set_overwrite(self.overwrite_var.get())
        self.compare_manager.set_store_checkpoints(self.store_checkpoints_var.get())
        
        # Update search_only_return_closest config
        config.search_only_return_closest = self.search_only_return_closest_var.get()
        
        self.on_closing()
    
    def on_closing(self, event=None):
        """Close the window."""
        if self.compare_manager in CompareSettingsWindow._open_windows:
            del CompareSettingsWindow._open_windows[self.compare_manager]
        self.window.destroy()
    
    @classmethod
    def show(cls, parent, compare_manager: CompareManager):
        """Show or focus the settings window for a compare manager."""
        if compare_manager in cls._open_windows:
            cls._open_windows[compare_manager].window.lift()
        else:
            cls(parent, compare_manager)

