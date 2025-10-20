import os

from tkinter import Frame, Label, filedialog, messagebox, LEFT, W
from tkinter.ttk import Button

from lib.multi_display import SmartToplevel
from utils.app_info_cache import app_info_cache
from utils.app_style import AppStyle
from utils.config import config
from utils.translations import I18N
from utils.utils import ModifierKey, Utils
from utils.logging_setup import get_logger

logger = get_logger("target_directory_window")

_ = I18N._


class TargetDirectoryWindow:
    """Window for selecting target directories for related file searches."""
    
    # Static class variables for managing recent directories
    recent_directories = []
    MAX_RECENT_DIRECTORIES = 50
    RECENT_DIRECTORIES_KEY = "target_directory_window.recent_directories"
    
    @staticmethod
    def load_recent_directories():
        """Load recent directories from app cache."""
        dirs = app_info_cache.get_meta(TargetDirectoryWindow.RECENT_DIRECTORIES_KEY, default_val=[])
        if not isinstance(dirs, list):
            dirs = []
        # Filter out any paths that are no longer valid directories
        filtered_dirs = [os.path.normpath(d) for d in dirs if isinstance(d, str) and os.path.isdir(d)]
        TargetDirectoryWindow.recent_directories = filtered_dirs
        # Persist the filtered list back into the cache so stale entries are removed
        if filtered_dirs != dirs:
            app_info_cache.set_meta(TargetDirectoryWindow.RECENT_DIRECTORIES_KEY, filtered_dirs)
    
    @staticmethod
    def save_recent_directories():
        """Save recent directories to app cache."""
        app_info_cache.set_meta(TargetDirectoryWindow.RECENT_DIRECTORIES_KEY, TargetDirectoryWindow.recent_directories)
    
    @staticmethod
    def add_recent_directory(directory):
        """Add a directory to the recent list (most recent first)."""
        if not directory or not os.path.isdir(directory):
            return
        
        normalized_dir = os.path.normpath(os.path.abspath(directory))
        
        # Remove if already exists
        if normalized_dir in TargetDirectoryWindow.recent_directories:
            TargetDirectoryWindow.recent_directories.remove(normalized_dir)
        
        # Add to beginning
        TargetDirectoryWindow.recent_directories.insert(0, normalized_dir)
        
        # Enforce maximum limit
        if len(TargetDirectoryWindow.recent_directories) > TargetDirectoryWindow.MAX_RECENT_DIRECTORIES:
            TargetDirectoryWindow.recent_directories = TargetDirectoryWindow.recent_directories[:TargetDirectoryWindow.MAX_RECENT_DIRECTORIES]
        
        TargetDirectoryWindow.save_recent_directories()
    
    @staticmethod
    def get_geometry():
        """Get window geometry based on number of directories."""
        width = 600
        min_height = 300
        height = len(TargetDirectoryWindow.recent_directories) * 22 + 100
        max_height = 600
        if height > max_height:
            height = max_height
        else:
            height = max(height, min_height)
        return f"{width}x{height}"
    
    def __init__(self, master, callback=None, initial_dir=None):
        """
        Initialize the target directory window.
        
        Args:
            master: Parent window
            callback: Function to call when a directory is selected (receives directory path)
            initial_dir: Initial directory to highlight or use as starting point
        """
        # Load recent directories
        TargetDirectoryWindow.load_recent_directories()
        
        self.master = SmartToplevel(
            persistent_parent=master, 
            title=_("Select Target Directory"), 
            geometry=TargetDirectoryWindow.get_geometry()
        )
        self.callback = callback
        self.initial_dir = initial_dir
        
        # Main frame
        self.frame = Frame(self.master)
        self.frame.grid(column=0, row=0, sticky='nsew', padx=10, pady=10)
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(1, weight=1)
        self.frame.config(bg=AppStyle.BG_COLOR)
        
        # Title
        title_label = Label(self.frame, text=_("Select Target Directory for Related Files Search"), 
                           font=('Helvetica', 12, 'bold'), bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
        title_label.grid(row=0, column=0, sticky=W, pady=(0, 10))
        
        # Directory list frame
        self.dirs_frame = Frame(self.frame, bg=AppStyle.BG_COLOR)
        self.dirs_frame.grid(row=1, column=0, sticky='nsew', pady=(0, 10))
        self.dirs_frame.columnconfigure(0, weight=1)
        
        # Action buttons frame
        self.buttons_frame = Frame(self.frame, bg=AppStyle.BG_COLOR)
        self.buttons_frame.grid(row=2, column=0, sticky='ew', pady=(0, 10))
        
        # Initialize UI
        self.set_dir_btn_list = []
        self.label_list = []
        self.filtered_directories = TargetDirectoryWindow.recent_directories[:]
        self.filter_text = ""
        
        self.add_directory_widgets()
        self.add_action_buttons()
        
        # Bind events
        self.master.bind("<Key>", self.filter_directories)
        self.master.bind("<Return>", self.select_directory)
        self.master.bind("<Escape>", self.close_window)
        self.master.protocol("WM_DELETE_WINDOW", self.close_window)
        
        # Focus
        self.frame.after(1, lambda: self.frame.focus_force())
    
    def add_directory_widgets(self):
        """Add directory widgets to the frame."""
        # Clear existing widgets
        self.clear_widget_lists()
        
        # Add directories
        for i, directory in enumerate(self.filtered_directories):
            # Directory label
            label = Label(self.dirs_frame, text=directory, bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
            label.grid(row=i, column=0, sticky=W, padx=(0, 10), pady=2)
            self.label_list.append(label)
            
            # Select button
            select_btn = Button(self.dirs_frame, text=_("Select"))
            select_btn.grid(row=i, column=1, padx=(0, 10), pady=2)
            self.set_dir_btn_list.append(select_btn)
            
            # Bind click handler
            def make_handler(directory):
                def handler(event=None):
                    self.select_directory(directory=directory)
                return handler
            
            select_btn.bind("<Button-1>", make_handler(directory))
    
    def add_action_buttons(self):
        """Add action buttons."""
        # Browse for new directory
        self.browse_btn = Button(self.buttons_frame, text=_("Browse for Directory..."), 
                                command=self.browse_new_directory)
        self.browse_btn.grid(row=0, column=0, padx=(0, 10))
        
        # Clear recent directories
        self.clear_btn = Button(self.buttons_frame, text=_("Clear Recent"), 
                               command=self.clear_recent_directories)
        self.clear_btn.grid(row=0, column=1, padx=(0, 10))
        
        # Cancel
        self.cancel_btn = Button(self.buttons_frame, text=_("Cancel"), 
                                command=self.close_window)
        self.cancel_btn.grid(row=0, column=2)
    
    def browse_new_directory(self):
        """Open directory picker for a new directory."""
        initial_dir = self.initial_dir or (self.app_actions.get_base_dir() if hasattr(self, 'app_actions') and hasattr(self.app_actions, 'get_base_dir') else ".")
        
        target_dir = filedialog.askdirectory(
            title=_("Select directory to search for related files"),
            initialdir=initial_dir
        )
        
        if target_dir:
            TargetDirectoryWindow.add_recent_directory(target_dir)
            self.select_directory(directory=target_dir)
    
    def clear_recent_directories(self):
        """Clear all recent directories."""
        TargetDirectoryWindow.recent_directories.clear()
        TargetDirectoryWindow.save_recent_directories()
        self.filtered_directories.clear()
        self.add_directory_widgets()
        self.master.update()
    
    def filter_directories(self, event):
        """Filter directories based on keyboard input."""
        modifier_key_pressed = (event.state & 0x1) != 0 or (event.state & 0x4) != 0
        if modifier_key_pressed:
            return
        
        if len(event.keysym) > 1:
            if event.keysym == "Down" or event.keysym == "Up":
                if event.keysym == "Down":
                    self.filtered_directories = self.filtered_directories[1:] + [self.filtered_directories[0]]
                else:  # keysym == "Up"
                    self.filtered_directories = [self.filtered_directories[-1]] + self.filtered_directories[:-1]
                self.add_directory_widgets()
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
            # Restore full list
            self.filtered_directories = TargetDirectoryWindow.recent_directories[:]
        else:
            # Filter directories
            temp = []
            filter_lower = self.filter_text.lower()
            
            # First pass: exact basename match
            for directory in TargetDirectoryWindow.recent_directories:
                basename = os.path.basename(os.path.normpath(directory))
                if basename.lower() == filter_lower:
                    temp.append(directory)
            
            # Second pass: basename starts with filter
            for directory in TargetDirectoryWindow.recent_directories:
                basename = os.path.basename(os.path.normpath(directory))
                if directory not in temp and basename.lower().startswith(filter_lower):
                    temp.append(directory)
            
            # Third pass: parent directory name starts with filter
            for directory in TargetDirectoryWindow.recent_directories:
                if directory not in temp:
                    parent_dir = os.path.basename(os.path.dirname(os.path.normpath(directory)))
                    if parent_dir and parent_dir.lower().startswith(filter_lower):
                        temp.append(directory)
            
            # Fourth pass: partial match in basename
            for directory in TargetDirectoryWindow.recent_directories:
                if directory not in temp:
                    basename = os.path.basename(os.path.normpath(directory))
                    if basename and (f" {filter_lower}" in basename.lower() or f"_{filter_lower}" in basename.lower()):
                        temp.append(directory)
            
            self.filtered_directories = temp[:]
        
        self.add_directory_widgets()
        self.master.update()
    
    def select_directory(self, event=None, directory=None):
        """Select a directory and call the callback."""
        if directory is None:
            # Use first filtered directory or last set directory
            if len(self.filtered_directories) > 0:
                directory = self.filtered_directories[0]
            else:
                return
        
        # Add to recent directories
        TargetDirectoryWindow.add_recent_directory(directory)
        
        # Call callback if provided
        if self.callback:
            self.callback(directory)
        
        # Close window
        self.close_window()
    
    def clear_widget_lists(self):
        """Clear all widget lists."""
        for btn in self.set_dir_btn_list:
            btn.destroy()
        for label in self.label_list:
            label.destroy()
        self.set_dir_btn_list = []
        self.label_list = []
    
    def close_window(self, event=None):
        """Close the window."""
        self.master.destroy()
