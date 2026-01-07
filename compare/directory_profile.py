"""
Directory Profile module for managing groups of directories.

DirectoryProfile represents a profile that groups multiple directories together,
allowing operations to be run on multiple directories at once.
"""

import os
from typing import List, Optional

from tkinter import Frame, Label, StringVar, LEFT, W, Scrollbar, Listbox, BOTH, RIGHT, TOP, E
import tkinter.font as fnt
from tkinter.ttk import Entry, Button

from lib.multi_display import SmartToplevel
from utils.app_style import AppStyle
from utils.config import config
from utils.logging_setup import get_logger
from utils.translations import I18N

_ = I18N._
logger = get_logger("directory_profile")


class DirectoryProfile:
    """Represents a profile that groups multiple directories together."""

    directory_profiles: List['DirectoryProfile'] = []
    
    def __init__(self, name="", directories=None):
        self.name = name  # Unique name to identify this profile
        self.directories = directories if directories is not None else []  # List of directory paths
    
    def __eq__(self, other):
        """Check equality based on name and directories (order-insensitive, duplicate-insensitive)."""
        if not isinstance(other, DirectoryProfile):
            return False
        return self.name == other.name and set(self.directories) == set(other.directories)
    
    def __hash__(self):
        """Hash based on name and sorted directories tuple."""
        return hash((self.name, tuple(sorted(set(self.directories)))))
    
    def to_dict(self):
        """Serialize to dictionary for caching."""
        return {
            "name": self.name,
            "directories": self.directories,
        }
    
    @staticmethod
    def from_dict(d):
        """Deserialize from dictionary."""
        return DirectoryProfile(
            name=d.get("name", ""),
            directories=d.get("directories", [])
        )
    
    @staticmethod
    def add_profile(profile: 'DirectoryProfile') -> bool:
        """
        Add a profile to the list.
        
        Args:
            profile: The DirectoryProfile to add
            
        Returns:
            True if added successfully, False if profile with same name already exists
        """
        # Check for duplicate name
        existing = DirectoryProfile.get_profile_by_name(profile.name)
        if existing is not None:
            logger.error(f"Profile with name {profile.name} already exists")
            return False
        
        DirectoryProfile.directory_profiles.append(profile)
        logger.info(f"Added profile: {profile.name}")
        return True
    
    @staticmethod
    def update_profile(old_name: str, new_profile: 'DirectoryProfile') -> bool:
        """
        Update an existing profile.
        
        Args:
            old_name: The old name of the profile
            new_profile: The updated profile
            
        Returns:
            True if updated successfully, False if new name conflicts with existing profile
        """
        # Find the old profile
        old_profile = DirectoryProfile.get_profile_by_name(old_name)
        if old_profile is None:
            logger.error(f"Profile {old_name} not found")
            return False
        
        # Check if new name conflicts (unless it's the same profile)
        if new_profile.name != old_name:
            existing = DirectoryProfile.get_profile_by_name(new_profile.name)
            if existing is not None and existing != old_profile:
                logger.error(f"Profile with name {new_profile.name} already exists")
                return False
        
        # Update the profile in place
        old_profile.name = new_profile.name
        old_profile.directories = new_profile.directories
        
        logger.info(f"Updated profile: {old_name} -> {new_profile.name}")
        return True

    @staticmethod
    def get_profile_by_name(name: str) -> Optional['DirectoryProfile']:
        """Get a profile by name. Returns None if not found."""
        for profile in DirectoryProfile.directory_profiles:
            if name == profile.name:
                return profile
        return None


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
        
        self.remove_dir_btn = Button(dir_buttons_frame, text=_("Remove"), command=self.remove_directory)
        self.remove_dir_btn.pack(side=TOP, pady=2)
        
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

    def add_directory(self):
        """Add a directory to the profile."""
        # Simple text entry dialog - could be enhanced with file browser
        from tkinter import simpledialog
        directory = simpledialog.askstring(_("Add Directory"), _("Enter directory path:"))
        if directory and directory.strip():
            directory = directory.strip()
            if os.path.isdir(directory):
                if directory not in self.profile.directories:
                    self.profile.directories.append(directory)
                    self.refresh_directories_listbox()
                else:
                    logger.warning(f"Directory {directory} already in profile")
            else:
                logger.error(f"Invalid directory: {directory}")

    def remove_directory(self):
        """Remove the selected directory from the profile."""
        selection = self.directories_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        if idx < len(self.profile.directories):
            del self.profile.directories[idx]
            self.refresh_directories_listbox()

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
