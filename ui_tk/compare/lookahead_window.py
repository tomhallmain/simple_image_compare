import os

from tkinter import Frame, Label, Scale, Checkbutton, BooleanVar, StringVar, LEFT, W, HORIZONTAL, BOTH, E
import tkinter.font as fnt
from tkinter.ttk import Entry, Button, Combobox

from compare.lookahead import Lookahead
from lib.multi_display import SmartToplevel
from utils.app_style import AppStyle
from utils.config import config
from utils.logging_setup import get_logger
from utils.translations import I18N

_ = I18N._
logger = get_logger("lookahead_window")


class LookaheadWindow():
    top_level = None
    COL_0_WIDTH = 600

    def __init__(self, master, app_actions, refresh_callback, lookahead=None, dimensions="500x450"):
        LookaheadWindow.top_level = SmartToplevel(persistent_parent=master, geometry=dimensions)
        self.master = LookaheadWindow.top_level
        self.app_actions = app_actions
        self.refresh_callback = refresh_callback
        self.lookahead = lookahead if lookahead is not None else Lookahead()
        self.is_edit = lookahead is not None
        self.original_name = self.lookahead.name if self.is_edit else None
        LookaheadWindow.top_level.title(_("Edit Lookahead") if self.is_edit else _("Create Lookahead"))

        self.frame = Frame(self.master)
        self.frame.grid(column=0, row=0)
        self.frame.columnconfigure(0, weight=9)
        self.frame.columnconfigure(1, weight=1)
        self.frame.config(bg=AppStyle.BG_COLOR)

        row = 0
        
        # Lookahead name
        self.label_name = Label(self.frame)
        self.add_label(self.label_name, _("Lookahead Name"), row=row, wraplength=LookaheadWindow.COL_0_WIDTH)
        self.lookahead_name_var = StringVar(self.master, value=self.lookahead.name)
        self.lookahead_name_entry = Entry(self.frame, textvariable=self.lookahead_name_var, width=50, 
                                          font=fnt.Font(size=config.font_size))
        self.lookahead_name_entry.grid(row=row, column=1, sticky=W)

        row += 1
        
        # Checkbox to toggle between prevalidation name and custom text
        self.is_prevalidation_name_var = BooleanVar(value=self.lookahead.is_prevalidation_name)
        self.is_prevalidation_name_checkbox = Checkbutton(self.frame, 
                                                          text=_("Reference existing prevalidation name"), 
                                                          variable=self.is_prevalidation_name_var,
                                                          command=self.update_ui_for_type,
                                                          bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR,
                                                          activebackground=AppStyle.BG_COLOR,
                                                          activeforeground=AppStyle.FG_COLOR,
                                                          font=fnt.Font(size=config.font_size))
        self.is_prevalidation_name_checkbox.grid(row=row, column=1, sticky=W, pady=5)

        row += 1
        
        # Label for name_or_text field
        self.label_name_or_text = Label(self.frame)
        self.add_label(self.label_name_or_text, _("Prevalidation Name or Custom Text"), 
                      row=row, wraplength=LookaheadWindow.COL_0_WIDTH)
        
        # Frame to hold either combobox or entry
        self.name_or_text_frame = Frame(self.frame, bg=AppStyle.BG_COLOR)
        self.name_or_text_frame.grid(row=row, column=1, sticky=W+E)
        
        # Get list of existing prevalidation names
        from compare.classifier_actions_manager import ClassifierActionsManager
        self.existing_names = [pv.name for pv in ClassifierActionsManager.prevalidations]
        
        self.name_or_text_var = StringVar(self.master, value=self.lookahead.name_or_text)
        
        # Create both widgets but only show one based on checkbox
        self.name_or_text_combobox = Combobox(self.name_or_text_frame, textvariable=self.name_or_text_var, 
                                             values=self.existing_names, width=47,
                                             font=fnt.Font(size=config.font_size))
        self.name_or_text_combobox.config(background=AppStyle.BG_COLOR, foreground=AppStyle.FG_COLOR)
        
        self.name_or_text_entry = Entry(self.name_or_text_frame, textvariable=self.name_or_text_var, width=50,
                                        font=fnt.Font(size=config.font_size))
        
        # Initialize UI based on current type
        self.update_ui_for_type()

        row += 1
        
        # Threshold slider
        self.label_threshold = Label(self.frame)
        self.add_label(self.label_threshold, _("Threshold"), row=row, wraplength=LookaheadWindow.COL_0_WIDTH)
        self.threshold_slider = Scale(self.frame, from_=0, to=100, orient=HORIZONTAL, command=self.set_threshold)
        self.threshold_slider.set(float(self.lookahead.threshold) * 100)
        self.threshold_slider.grid(row=row, column=1, sticky=W)

        row += 1
        self.done_btn = None
        self.add_btn("done_btn", _("Done"), self.finalize_lookahead, row=row, column=0)

        self.master.update()

    def update_ui_for_type(self):
        """Update UI to show either combobox or entry based on checkbox state."""
        is_prevalidation = self.is_prevalidation_name_var.get()
        
        # Clear the frame
        for widget in self.name_or_text_frame.winfo_children():
            widget.destroy()
        
        if is_prevalidation:
            # Show combobox for selecting prevalidation name
            self.name_or_text_combobox = Combobox(self.name_or_text_frame, textvariable=self.name_or_text_var, 
                                                 values=self.existing_names, width=47,
                                                 font=fnt.Font(size=config.font_size))
            self.name_or_text_combobox.pack(fill=BOTH, expand=True)
            AppStyle.setup_combobox_style(self.name_or_text_combobox)
        else:
            # Show entry for custom text
            self.name_or_text_entry = Entry(self.name_or_text_frame, textvariable=self.name_or_text_var, width=50,
                                            font=fnt.Font(size=config.font_size))
            self.name_or_text_entry.pack(fill=BOTH, expand=True)

    def set_threshold(self, event=None):
        self.lookahead.threshold = float(self.threshold_slider.get()) / 100

    def finalize_lookahead(self, event=None):
        lookahead_name = self.lookahead_name_var.get().strip()
        name_or_text = self.name_or_text_var.get().strip()
        
        if not lookahead_name:
            logger.error("Lookahead name is required")
            return
        if not name_or_text:
            logger.error("Prevalidation name or custom text is required")
            return
        
        # Check if lookahead name already exists (for new lookaheads)
        if not self.is_edit:
            if Lookahead.get_lookahead_by_name(lookahead_name) is not None:
                logger.error(f"Lookahead with name {lookahead_name} already exists")
                return
        else:
            # For editing, check if name changed and conflicts
            old_lookahead = self.lookahead
            if lookahead_name != old_lookahead.name:
                if Lookahead.get_lookahead_by_name(lookahead_name) is not None:
                    logger.error(f"Lookahead with name {lookahead_name} already exists")
                    return
        
        threshold = self.lookahead.threshold
        is_prevalidation_name = self.is_prevalidation_name_var.get()
        
        # If it's a prevalidation name, verify it exists
        if is_prevalidation_name and name_or_text not in self.existing_names:
            logger.warning(f"Prevalidation '{name_or_text}' not found, treating as custom text")
            is_prevalidation_name = False
        
        self.lookahead.name = lookahead_name
        self.lookahead.name_or_text = name_or_text
        self.lookahead.threshold = threshold
        self.lookahead.is_prevalidation_name = is_prevalidation_name
        
        if not self.is_edit:
            Lookahead.lookaheads.append(self.lookahead)
        else:
            # Find and update the existing lookahead by matching the original name
            for idx, lh in enumerate(Lookahead.lookaheads):
                if lh.name == self.original_name:
                    Lookahead.lookaheads[idx] = self.lookahead
                    break
            
            # Update references if name changed
            if self.original_name != lookahead_name:
                from compare.classifier_actions_manager import ClassifierActionsManager
                for pv in ClassifierActionsManager.prevalidations:
                    if self.original_name in pv.lookahead_names:
                        idx_ref = pv.lookahead_names.index(self.original_name)
                        pv.lookahead_names[idx_ref] = lookahead_name
        
        self.close_windows()
        self.refresh_callback()

    def close_windows(self, event=None):
        self.master.destroy()

    def add_label(self, label_ref, text, row=0, column=0, wraplength=500):
        label_ref['text'] = text
        label_ref.grid(column=column, row=row, sticky=W)
        label_ref.config(wraplength=wraplength, justify=LEFT, bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR, font=fnt.Font(size=config.font_size))

    def add_btn(self, button_ref_name, text, command, row=0, column=0):
        if getattr(self, button_ref_name, None) is None:
            button = Button(master=self.frame, text=text, command=command)
            setattr(self, button_ref_name, button)
            button # for some reason this is necessary to maintain the reference?
            button.grid(row=row, column=column)
