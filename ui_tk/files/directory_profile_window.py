"""
Directory Profile module for managing groups of directories.

DirectoryProfile represents a profile that groups multiple directories together,
allowing operations to be run on multiple directories at once.
"""

import os

from tkinter import Frame, Label, StringVar, LEFT, W, Scrollbar, Listbox, BOTH, RIGHT, TOP, E
import tkinter.font as fnt
from tkinter.ttk import Entry, Button

from files.directory_profile import DirectoryProfile
from lib.multi_display import SmartToplevel
from utils.app_style import AppStyle
from utils.config import config
from utils.logging_setup import get_logger
from utils.translations import I18N

_ = I18N._
logger = get_logger("directory_profile_window")


class DirectoryProfileWindow():
    top_level = None
    COL_0_WIDTH = 600

    def __init__(self, master, app_actions, refresh_callback, profile=None, dimensions="600x500"):
        DirectoryProfileWindow.top_level = SmartToplevel(persistent_parent=master, geometry=dimensions)
        self.master = DirectoryProfileWindow.top_level
        self.app_actions = app_actions
        self.refresh_callback = refresh_callback
        self.profile = profile if profile is not None else DirectoryProfile()
        self.is_edit = profile is not None
        self.original_name = self.profile.name if self.is_edit else None
        DirectoryProfileWindow.top_level.title(_("Edit Profile") if self.is_edit else _("Create Profile"))

        self.frame = Frame(self.master)
        self.frame.grid(column=0, row=0)
        self.frame.columnconfigure(0, weight=9)
        self.frame.columnconfigure(1, weight=1)
        self.frame.config(bg=AppStyle.BG_COLOR)

        row = 0
        
        # Profile name
        self.label_name = Label(self.frame)
        self.add_label(self.label_name, _("Profile Name"), row=row, wraplength=DirectoryProfileWindow.COL_0_WIDTH)
        self.profile_name_var = StringVar(self.master, value=self.profile.name)
        self.profile_name_entry = Entry(self.frame, textvariable=self.profile_name_var, width=50, 
                                        font=fnt.Font(size=config.font_size))
        self.profile_name_entry.grid(row=row, column=1, sticky=W)

        row += 1
        
        # Directories listbox with scrollbar
        self.label_directories = Label(self.frame)
        self.add_label(self.label_directories, _("Directories"), row=row, wraplength=DirectoryProfileWindow.COL_0_WIDTH)
        
        directories_frame = Frame(self.frame, bg=AppStyle.BG_COLOR)
        directories_frame.grid(row=row, column=1, sticky=W+E)
        
        listbox_frame = Frame(directories_frame, bg=AppStyle.BG_COLOR)
        listbox_frame.pack(side=LEFT, fill=BOTH, expand=True)
        
        scrollbar = Scrollbar(listbox_frame)
        scrollbar.pack(side=RIGHT, fill="y")
        
        self.directories_listbox = Listbox(listbox_frame, height=6, width=50, yscrollcommand=scrollbar.set,
                                           font=fnt.Font(size=config.font_size), bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
        self.directories_listbox.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.config(command=self.directories_listbox.yview)
        
        # Buttons for directories
        dir_buttons_frame = Frame(directories_frame, bg=AppStyle.BG_COLOR)
        dir_buttons_frame.pack(side=LEFT, padx=(5, 0))
        
        self.add_dir_btn = Button(dir_buttons_frame, text=_("Add"), command=self.add_directory)
        self.add_dir_btn.pack(side=TOP, pady=2)
        
        self.edit_dir_btn = Button(dir_buttons_frame, text=_("Edit"), command=self.edit_directory)
        self.edit_dir_btn.pack(side=TOP, pady=2)
        
        self.remove_dir_btn = Button(dir_buttons_frame, text=_("Remove"), command=self.remove_directory)
        self.remove_dir_btn.pack(side=TOP, pady=2)
        
        self.add_subdirs_btn = Button(dir_buttons_frame, text=_("Add dirs from subdirs"), command=self.add_subdirectories)
        self.add_subdirs_btn.pack(side=TOP, pady=2)
        
        self.clear_all_btn = Button(dir_buttons_frame, text=_("Clear all"), command=self.clear_all_directories)
        self.clear_all_btn.pack(side=TOP, pady=2)
        
        # Initialize directories listbox
        self.refresh_directories_listbox()

        row += 1
        self.done_btn = None
        self.add_btn("done_btn", _("Done"), self.finalize_profile, row=row, column=0)

        self.master.update()

    def refresh_directories_listbox(self):
        """Refresh the directories listbox."""
        if hasattr(self, 'directories_listbox'):
            self.directories_listbox.delete(0, "end")
            for directory in self.profile.directories:
                self.directories_listbox.insert("end", directory)

    def _browse_directory(self, title=_("Select directory"), initialdir=None):
        """
        Internal method to open a directory browser dialog.
        
        Args:
            title: Title for the dialog
            initialdir: Initial directory to show in the dialog (defaults to current directory or last selected)
            
        Returns:
            Selected directory path, or None if cancelled
        """
        from tkinter import filedialog
        
        if initialdir is None:
            # Try to use the last directory in the profile, or current directory
            if self.profile.directories:
                initialdir = self.profile.directories[-1]
            else:
                initialdir = "."
        
        directory = filedialog.askdirectory(
            parent=self.master,
            title=title,
            initialdir=initialdir if os.path.isdir(initialdir) else "."
        )
        
        return directory if directory and directory.strip() else None
    
    def add_directory(self):
        """Add a directory to the profile."""
        directory = self._browse_directory(_("Add Directory"))
        if directory:
            directory = directory.strip()
            if os.path.isdir(directory):
                if directory not in self.profile.directories:
                    self.profile.directories.append(directory)
                    self.refresh_directories_listbox()
                else:
                    logger.warning(f"Directory {directory} already in profile")
            else:
                logger.error(f"Invalid directory: {directory}")

    def edit_directory(self):
        """Edit the selected directory path."""
        selection = self.directories_listbox.curselection()
        if not selection:
            logger.warning("No directory selected for editing")
            return
        idx = selection[0]
        if idx >= len(self.profile.directories):
            return
        
        current_dir = self.profile.directories[idx]
        
        # Use file dialog to select a new directory
        new_directory = self._browse_directory(_("Edit Directory"), initialdir=current_dir)
        
        if new_directory:
            new_directory = new_directory.strip()
            if os.path.isdir(new_directory):
                # Check if the new directory is already in the list (excluding the current one)
                if new_directory in self.profile.directories and self.profile.directories.index(new_directory) != idx:
                    logger.warning(f"Directory {new_directory} already in profile")
                else:
                    self.profile.directories[idx] = new_directory
                    self.refresh_directories_listbox()
                    # Keep the same item selected
                    self.directories_listbox.selection_set(idx)
            else:
                logger.error(f"Invalid directory: {new_directory}")

    def remove_directory(self):
        """Remove the selected directory from the profile."""
        selection = self.directories_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        if idx < len(self.profile.directories):
            del self.profile.directories[idx]
            self.refresh_directories_listbox()
    
    def clear_all_directories(self):
        """Remove all directories from the profile."""
        self.profile.directories.clear()
        self.refresh_directories_listbox()
        logger.info("Cleared all directories from profile")
    
    def add_subdirectories(self):
        """Add all immediate subdirectories of a user-selected directory."""
        parent_dir = self._browse_directory(_("Select directory to add subdirectories from"))
        if not parent_dir:
            return
        
        parent_dir = parent_dir.strip()
        if not os.path.isdir(parent_dir):
            logger.error(f"Invalid directory: {parent_dir}")
            return
        
        # Get all immediate subdirectories
        subdirs_added = 0
        try:
            for item in os.listdir(parent_dir):
                subdir_path = os.path.join(parent_dir, item)
                if os.path.isdir(subdir_path):
                    # Add if not already in the list
                    if subdir_path not in self.profile.directories:
                        self.profile.directories.append(subdir_path)
                        subdirs_added += 1
                    else:
                        logger.debug(f"Subdirectory {subdir_path} already in profile")
            
            if subdirs_added > 0:
                self.refresh_directories_listbox()
                logger.info(f"Added {subdirs_added} subdirectories from {parent_dir}")
            else:
                logger.info(f"No new subdirectories found in {parent_dir}")
        except Exception as e:
            logger.error(f"Error reading subdirectories from {parent_dir}: {e}")

    def finalize_profile(self, event=None):
        profile_name = self.profile_name_var.get().strip()
        
        if not profile_name:
            logger.error("Profile name is required")
            return
        
        # Check if profile name already exists (for new profiles)
        if not self.is_edit:
            if DirectoryProfile.get_profile_by_name(profile_name) is not None:
                logger.error(f"Profile with name {profile_name} already exists")
                return
        else:
            # For editing, check if name changed and conflicts
            if profile_name != self.original_name:
                if DirectoryProfile.get_profile_by_name(profile_name) is not None:
                    logger.error(f"Profile with name {profile_name} already exists")
                    return
        
        self.profile.name = profile_name
        
        if not self.is_edit:
            DirectoryProfile.add_profile(self.profile)
        else:
            DirectoryProfile.update_profile(self.original_name, self.profile)
        
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
