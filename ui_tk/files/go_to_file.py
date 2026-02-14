import os
import re
from enum import Enum
from tkinter import Frame, StringVar, BooleanVar, LEFT, W, filedialog, Label, Listbox, Scrollbar
from tkinter.ttk import Entry, Button, Checkbutton, OptionMenu, Progressbar

from files.file_action import FileAction
from lib.multi_display import SmartToplevel
from ui_tk.files.marked_file_mover import MarkedFiles
from ui_tk.files.target_directory_window import TargetDirectoryWindow
from utils.app_info_cache import app_info_cache
from utils.app_style import AppStyle
from utils.config import config
from utils.constants import SortBy
from utils.translations import I18N
from utils.utils import Utils

_ = I18N._


class CharCategory(Enum):
    """Character category types for base ID matching."""
    ALPHA = "alpha"
    DIGIT = "digit"
    OTHER = "other"


class GoToFile:
    top_level = None
    last_search_text = ""
    last_use_closest = False
    last_use_index = False
    last_closest_sort_by = SortBy.NAME
    last_target_directory = Utils.get_pictures_dir()
    last_base_id = ""  # Last base ID that was successfully searched
    confirmed_directories = []  # Most-recent-first list of confirmed directories for large operations

    TARGET_DIRECTORY_KEY = "go_to_file.target_directory"
    BASE_ID_KEY = "go_to_file.base_id"
    CONFIRMED_DIRECTORIES_KEY = "go_to_file.confirmed_directories"
    MAX_CONFIRMED_DIRECTORIES = 20
    
    @staticmethod
    def load_persisted_data():
        persisted_target_dir = app_info_cache.get_meta(GoToFile.TARGET_DIRECTORY_KEY)
        if persisted_target_dir and os.path.isdir(persisted_target_dir):
            GoToFile.last_target_directory = persisted_target_dir
        persisted_base_id = app_info_cache.get_meta(GoToFile.BASE_ID_KEY)
        if persisted_base_id:
            GoToFile.last_base_id = persisted_base_id
        # Load, filter invalid, dedupe while preserving order, and cap size
        persisted_confirmed = app_info_cache.get_meta(GoToFile.CONFIRMED_DIRECTORIES_KEY, default_val=[])
        cleaned: list[str] = []
        seen = set()
        for d in persisted_confirmed:
            try:
                norm = os.path.normpath(os.path.abspath(d))
                if norm in seen:
                    continue
                if os.path.isdir(norm):
                    cleaned.append(norm)
                    seen.add(norm)
            except Exception:
                continue
        if len(cleaned) > GoToFile.MAX_CONFIRMED_DIRECTORIES:
            cleaned = cleaned[:GoToFile.MAX_CONFIRMED_DIRECTORIES]
        GoToFile.confirmed_directories = cleaned
    
    @staticmethod
    def save_persisted_data():
        app_info_cache.set_meta(GoToFile.TARGET_DIRECTORY_KEY, GoToFile.last_target_directory)
        app_info_cache.set_meta(GoToFile.BASE_ID_KEY, GoToFile.last_base_id)
        app_info_cache.set_meta(GoToFile.CONFIRMED_DIRECTORIES_KEY, GoToFile.confirmed_directories[:GoToFile.MAX_CONFIRMED_DIRECTORIES])

    @staticmethod
    def _add_confirmed_directory(directory: str) -> None:
        """Add directory to confirmed list as most recent, dedupe, and cap size."""
        try:
            norm = os.path.normpath(os.path.abspath(directory))
        except Exception:
            return
        # Remove any existing occurrences
        GoToFile.confirmed_directories = [d for d in GoToFile.confirmed_directories if d != norm]
        # Insert as most recent
        GoToFile.confirmed_directories.insert(0, norm)
        # Cap size
        if len(GoToFile.confirmed_directories) > GoToFile.MAX_CONFIRMED_DIRECTORIES:
            GoToFile.confirmed_directories = GoToFile.confirmed_directories[:GoToFile.MAX_CONFIRMED_DIRECTORIES]

    @staticmethod
    def get_geometry():
        width = 700
        height = 500
        return f"{width}x{height}"

    def __init__(self, master, app_actions):
        # Ensure persisted data is loaded each time a window is opened
        GoToFile.load_persisted_data()
        GoToFile.top_level = SmartToplevel(persistent_parent=master, title=_("Go To File"), geometry=GoToFile.get_geometry())
        self.master = GoToFile.top_level
        self.app_actions = app_actions
        self.loading_bar = None
        
        # Main frame for the entire window
        self.main_frame = Frame(self.master)
        self.main_frame.grid(column=0, row=0, sticky='nsew')
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.rowconfigure(0, weight=1)
        self.main_frame.config(bg=AppStyle.BG_COLOR)
        
        # Top frame for search functionality
        self.frame = Frame(self.main_frame)
        self.frame.grid(column=0, row=0, sticky='ew', padx=10, pady=10)
        self.frame.columnconfigure(0, weight=1)
        self.frame.config(bg=AppStyle.BG_COLOR)
        
        # Title for Go To File section
        go_to_title = Label(self.frame, text=_("Go To File"), 
                           font=('Helvetica', 12, 'bold'), bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
        go_to_title.grid(row=0, column=0, sticky=W, pady=(0, 10))

        self.search_text = StringVar()
        self.search_text.set(GoToFile.last_search_text)
        self.search_text.trace_add('write', self.on_filename_changed)  # Auto-extract base ID when filename changes
        self.search_text_box = Entry(self.frame, textvariable=self.search_text, width=40)
        self.search_text_box.grid(row=1, column=0, sticky='ew', pady=(0, 10))
        self.search_text_box.bind("<Return>", self.go_to_file)
        
        # Action buttons frame
        self.buttons_frame = Frame(self.frame, bg=AppStyle.BG_COLOR)
        self.buttons_frame.grid(row=2, column=0, sticky='ew', pady=(0, 10))
        
        self.search_files_btn = None
        self.add_btn("search_files_btn", _("Go To"), self.go_to_file, row=0, column=0, master=self.buttons_frame)
        
        self.file_picker_btn = None
        self.add_btn("file_picker_btn", _("Browse..."), self.pick_file, row=0, column=1, master=self.buttons_frame)
        
        # Button to go to last moved image basename with closest search
        self.last_moved_btn = None
        self.add_btn("last_moved_btn", _("Go To Last Moved"), self.go_to_last_moved, row=0, column=2, master=self.buttons_frame)
        
        # Add closest file checkbox
        self.use_closest = BooleanVar()
        self.use_closest.set(GoToFile.last_use_closest)
        self.closest_checkbox = Checkbutton(
            self.frame, 
            text=_("Go to closest file if exact match not found"), 
            variable=self.use_closest,
            command=self.toggle_closest_options
        )
        self.closest_checkbox.grid(row=3, column=0, sticky=W, pady=(5, 0))
        
        # Add index navigation checkbox
        self.use_index = BooleanVar()
        self.use_index.set(GoToFile.last_use_index)
        self.index_checkbox = Checkbutton(
            self.frame,
            text=_("Go to file by index (1-based)"),
            variable=self.use_index
        )
        self.index_checkbox.grid(row=4, column=0, sticky=W, pady=(5, 0))
        
        # Add SortBy selector for closest file search
        self.closest_sort_by = StringVar()
        self.closest_sort_by.set(GoToFile.last_closest_sort_by.get_text())
        self.sort_by_label = None
        self.sort_by_choice = None
        self.add_sort_by_selector()

        # Related files section
        self.setup_related_files_section()

        self.master.bind("<Escape>", self.close_windows)
        # self.master.bind("<Control-g>", lambda e: self.go_to_file())         # Go To File
        self.master.bind("<Control-b>", lambda e: self.pick_file())          # Browse File
        self.master.bind("<Control-g>", lambda e: self.go_to_last_moved())   # Go To Last Moved
        self.master.bind("<Control-r>", lambda e: self.get_current_media_filename())  # Current Media
        self.master.bind("<Control-f>", lambda e: self.find_related_files()) # Find Related Files
        self.master.bind("<Control-e>", lambda e: self.extract_and_set_base_id())  # Extract base ID
        self.master.bind("<Control-d>", lambda e: self.browse_target_directory())  # Browse Directory
        self.frame.after(1, lambda: self.frame.focus_force())
        self.search_text_box.after(1, lambda: self.search_text_box.focus_force())

    def go_to_file(self, event=None):
        search_text = self.search_text.get().strip()
        if search_text == "":
            self.app_actions.warn(_("Invalid search string, please enter some text."))
            return
        
        GoToFile.last_search_text = search_text
        GoToFile.last_use_closest = self.use_closest.get()
        GoToFile.last_use_index = self.use_index.get()
        GoToFile.last_closest_sort_by = SortBy.get(self.closest_sort_by.get())
        
        # Check if index navigation is enabled
        if self.use_index.get():
            try:
                index = int(search_text)
                if self.app_actions.go_to_file_by_index(index):
                    self.close_windows()
                return
            except ValueError:
                self.app_actions.warn(_("Index navigation enabled but input is not a valid number."))
                return
        
        # Normal file search
        # Pass closest_sort_by only if the checkbox is checked
        closest_sort_by = GoToFile.last_closest_sort_by if GoToFile.last_use_closest else None
        self.app_actions.go_to_file(
            search_text=search_text, 
            exact_match=False, 
            closest_sort_by=closest_sort_by
        )
        self.close_windows()

    def pick_file(self, event=None):
        """Open file picker dialog and go to selected file."""
        # Create file type filter from config
        file_types = []
        if config.file_types:
            # Group extensions by type for better organization
            extensions = " ".join([f"*{ext}" for ext in config.file_types])
            file_types.append((_("Supported files"), extensions))
            # Also add individual file type groups for better organization
            if config.image_types:
                img_extensions = " ".join([f"*{ext}" for ext in config.image_types])
                file_types.append((_("Image files"), img_extensions))
            if config.enable_videos and config.video_types:
                vid_extensions = " ".join([f"*{ext}" for ext in config.video_types])
                file_types.append((_("Video files"), vid_extensions))
            if config.enable_gifs:
                file_types.append((_("GIF files"), "*.gif"))
            if config.enable_pdfs:
                file_types.append((_("PDF files"), "*.pdf"))
            if config.enable_svgs:
                file_types.append((_("SVG files"), "*.svg"))
            if config.enable_html:
                file_types.append((_("HTML files"), "*.html *.htm"))
        
        # Add "All files" option
        file_types.append((_("All files"), "*.*"))
        
        selected_file = filedialog.askopenfilename(
            parent=self.app_actions.get_master(),
            title=_("Select file to go to"),
            filetypes=file_types,
            initialdir=self.app_actions.get_base_dir() if hasattr(self.app_actions, 'get_base_dir') else "."
        )
        
        if selected_file:
            # Set the selected file path in the search box
            self.search_text.set(selected_file)
            # Go to the selected file
            self.go_to_file()

    def go_to_last_moved(self, event=None):
        """Set closest search, populate with full path of last moved image, and go."""
        last_moved = MarkedFiles.last_moved_image
        if not last_moved:
            action = FileAction.get_history_action(start_index=0, exclude_auto=True)
            if action and getattr(action, "new_files", None) and len(action.new_files) > 0:
                last_moved = action.new_files[0]
            else:
                self.app_actions.toast(_("No last moved image found."))
                return
        # Ensure closest search is enabled
        GoToFile.last_use_closest = True
        self.use_closest.set(True)
        self.toggle_closest_options()
        # Populate with full path (not just basename) so methods like _find_closest_by_time can access file properties
        self.search_text.set(last_moved)
        self.master.update()
        self.go_to_file()

    def close_windows(self, event=None):
        self.master.destroy()

    def add_label(self, label_ref, text, row=0, column=0, wraplength=500):
        label_ref['text'] = text
        label_ref.grid(column=column, row=row, sticky=W)
        label_ref.config(wraplength=wraplength, justify=LEFT, bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)

    def add_btn(self, button_ref_name, text, command, row=0, column=0, master=None):
        if getattr(self, button_ref_name) is None:
            # Use provided master frame, or default to self.frame
            master = master or self.frame
            button = Button(master=master, text=text, command=command)
            setattr(self, button_ref_name, button)
            button # for some reason this is necessary to maintain the reference?
            button.grid(row=row, column=column)

    def add_sort_by_selector(self):
        """Add the SortBy selector for closest file search."""
        from tkinter import Label
        
        # Create a frame to contain the sort by elements
        self.sort_by_frame = Frame(self.frame, bg=AppStyle.BG_COLOR)
        
        self.sort_by_label = Label(self.sort_by_frame, text=_("Sort by for closest search:"), bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
        self.sort_by_label.grid(row=0, column=0, sticky=W, padx=(0, 10))
        
        self.sort_by_choice = OptionMenu(
            self.sort_by_frame, 
            self.closest_sort_by, 
            GoToFile.last_closest_sort_by.get_text(),
            *SortBy.members()
        )
        self.sort_by_choice.grid(row=0, column=1, sticky=W)
        
        # Don't grid the frame initially - it'll be positioned by toggle_closest_options
        self.toggle_closest_options()

    def toggle_closest_options(self):
        """Show/hide the SortBy selector based on closest file checkbox state."""
        if hasattr(self, 'sort_by_frame'):
            if self.use_closest.get():
                self.sort_by_frame.grid(row=5, column=0, sticky=W, pady=(10, 0))
            else:
                self.sort_by_frame.grid_remove()

    def setup_related_files_section(self):
        """Setup the related files section with directory picker and results list."""
        # Separator line
        separator = Label(self.main_frame, text="─" * 50, bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
        separator.grid(row=1, column=0, sticky='ew', padx=10, pady=(10, 5))
        
        # Related files frame
        self.related_frame = Frame(self.main_frame, bg=AppStyle.BG_COLOR)
        self.related_frame.grid(row=2, column=0, sticky='nsew', padx=10, pady=5)
        self.related_frame.columnconfigure(0, weight=1)
        self.related_frame.rowconfigure(1, weight=1)
        
        # Title
        title_label = Label(self.related_frame, text=_("Find Related Filenames"), 
                           font=('Helvetica', 12, 'bold'), bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
        title_label.grid(row=0, column=0, columnspan=3, sticky=W, pady=(0, 10))
        
        # Status label
        initial_text = _("Enter a base ID manually or click 'Extract from filename' to auto-extract from the filename above.")
        self.status_label = Label(self.related_frame, text=initial_text, 
                                 bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR, wraplength=600, justify=LEFT)
        self.status_label.grid(row=1, column=0, sticky=W, pady=(0, 8))
        
        # Base ID selection
        base_id_frame = Frame(self.related_frame, bg=AppStyle.BG_COLOR)
        base_id_frame.grid(row=2, column=0, sticky='ew', pady=(6, 10))
        # Don't configure column weight to prevent expansion
        
        base_id_label = Label(base_id_frame, text=_("Base ID:"), bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
        base_id_label.grid(row=0, column=0, sticky=W, padx=(0, 10))
        
        self.base_id_var = StringVar()
        # Initialize with last base ID that was searched, or extract from current search text if available
        initial_base_id = GoToFile.last_base_id
        if not initial_base_id and hasattr(self, 'search_text') and self.search_text.get().strip():
            initial_base_id = self.extract_base_id(self.search_text.get()) or ""
        self.base_id_var.set(initial_base_id)
        self.base_id_entry = Entry(base_id_frame, textvariable=self.base_id_var, width=25)
        self.base_id_entry.grid(row=0, column=1, padx=(0, 10))
        
        self.extract_base_id_btn = Button(base_id_frame, text=_("Extract from filename"), command=self.extract_and_set_base_id)
        self.extract_base_id_btn.grid(row=0, column=2)
        
        # Directory selection
        dir_frame = Frame(self.related_frame, bg=AppStyle.BG_COLOR)
        dir_frame.grid(row=3, column=0, sticky='ew', pady=(0, 10))
        # Don't configure column weight to prevent expansion
        
        dir_label = Label(dir_frame, text=_("Target Directory:"), bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
        dir_label.grid(row=0, column=0, sticky=W, padx=(0, 10))
        
        self.target_dir_var = StringVar()
        self.target_dir_var.set(GoToFile.last_target_directory)
        self.target_dir_entry = Entry(dir_frame, textvariable=self.target_dir_var, width=35)
        self.target_dir_entry.grid(row=0, column=1, padx=(0, 10))
        
        self.browse_dir_btn = Button(dir_frame, text=_("Browse..."), command=self.browse_target_directory)
        self.browse_dir_btn.grid(row=0, column=2)
        
        # Action buttons for related files
        action_frame = Frame(self.related_frame, bg=AppStyle.BG_COLOR)
        action_frame.grid(row=4, column=0, sticky='ew', pady=(0, 10))
        
        self.current_media_btn = Button(action_frame, text=_("Current Media"), command=self.get_current_media_filename)
        self.current_media_btn.grid(row=0, column=0, padx=(0, 10))
        
        self.related_files_btn = Button(action_frame, text=_("Find Related"), command=self.find_related_files)
        self.related_files_btn.grid(row=0, column=1)

        # Placeholder for loading indicator (positioned above results)
        self.loading_container = Frame(self.related_frame, bg=AppStyle.BG_COLOR)
        self.loading_container.grid(row=5, column=0, sticky=W, pady=(0, 4))
        
        # Results listbox with scrollbar
        results_frame = Frame(self.related_frame, bg=AppStyle.BG_COLOR)
        results_frame.grid(row=6, column=0, sticky='nsew', pady=(0, 10))
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        
        self.results_listbox = Listbox(results_frame, height=8, bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
        self.results_listbox.grid(row=0, column=0, sticky='nsew')
        self.results_listbox.bind('<Double-Button-1>', self.on_result_double_click)
        
        scrollbar = Scrollbar(results_frame, orient='vertical', command=self.results_listbox.yview)
        scrollbar.grid(row=0, column=1, sticky='ns')
        self.results_listbox.config(yscrollcommand=scrollbar.set)

    def update_status_label(self, text, fg_color=None):
        """Update the status label with wrapped text."""
        if fg_color is None:
            fg_color = AppStyle.FG_COLOR
        
        # Use Utils method to wrap text to fit the label width
        wrapped_text = Utils._wrap_text_to_fit_length(text, 600)
        self.status_label.config(text=wrapped_text, fg=fg_color, justify=LEFT)

    def browse_target_directory(self):
        """Open target directory selection window."""
        def on_directory_selected(directory):
            """Callback when a directory is selected."""
            self.target_dir_var.set(directory)
            GoToFile.last_target_directory = directory
            GoToFile.save_persisted_data()
            # Add to recent directories for future use
            TargetDirectoryWindow.add_recent_directory(directory)
            
            # Check if we can run the search automatically
            base_id = self.base_id_var.get().strip()
            if base_id and os.path.isdir(directory):
                # All elements are in place, run the search
                self.find_related_files()
            else:
                # Elements not ready, lift and focus the go_to_file window
                self.master.lift()
                self.master.focus_force()
        
        # Open the target directory window
        TargetDirectoryWindow(
            master=self.master,
            callback=on_directory_selected,
            initial_dir=self.app_actions.get_base_dir() if hasattr(self.app_actions, 'get_base_dir') else "."
        )

    def get_current_media_filename(self, event=None):
        """Get the current media filename from the active window and set it in the search field."""
        try:
            self.start_loading(_("Loading current media and searching..."))
            current_filepath = self.app_actions.get_active_media_filepath()
            if current_filepath:
                # Set the full filepath in the search field
                self.search_text.set(current_filepath)
                # The base ID will be auto-extracted via the trace callback
                
                # If target directory is already set, automatically search for related files
                target_dir = self.target_dir_var.get().strip()
                if target_dir and os.path.isdir(target_dir):
                    self.find_related_files()
                else:
                    self.app_actions.toast(_("Current media filename loaded. Select a target directory to find related filenames."))
            else:
                self.app_actions.warn(_("No active media file found in the current window."))
        except Exception as e:
            self.app_actions.warn(_("Error getting current media filename: {}").format(str(e)))
        finally:
            self.stop_loading()

    def start_loading(self, message: str | None = None):
        """Show an indeterminate loading bar and optionally update the status text."""
        try:
            if message is not None:
                self.update_status_label(message, AppStyle.FG_COLOR)
            if self.loading_bar is None:
                self.loading_bar = Progressbar(self.loading_container, orient='horizontal', mode='indeterminate', length=160)
                self.loading_bar.grid(row=0, column=0, padx=(10, 0))
            self.loading_bar.start(10)
            self.master.update_idletasks()
        except Exception:
            # Fail-safe: ignore UI errors
            pass

    def stop_loading(self, final_message: str | None = None, warn: bool = False):
        """Hide the loading bar and optionally set a final message with appropriate color."""
        try:
            if self.loading_bar is not None:
                self.loading_bar.stop()
                self.loading_bar.grid_forget()
                self.loading_bar.destroy()
                self.loading_bar = None
            if final_message is not None:
                fg_color = "orange" if warn else AppStyle.FG_COLOR
                self.update_status_label(final_message, fg_color)
            self.master.update_idletasks()
        except Exception:
            pass

    def update_with_current_media(self, focus=False):
        """Update the window with current media filename (for reusing existing window)."""
        # Focus the window first
        self.master.lift()
        if focus:
            self.master.focus_force()
        # Schedule the media loading so the window shows first
        self.master.after(50, self.get_current_media_filename)

    def on_filename_changed(self, *args):
        """Called when the filename changes - auto-extract base ID."""
        search_text = self.search_text.get().strip()
        if search_text and hasattr(self, 'base_id_var'):
            base_id = self.extract_base_id(search_text)
            if base_id:
                self.base_id_var.set(base_id)

    def extract_and_set_base_id(self):
        """Extract base ID from the current filename and set it in the base ID field."""
        search_text = self.search_text.get().strip()
        if not search_text:
            self.app_actions.toast(_("Please enter a filename first."))
            return
        
        base_id = self.extract_base_id(search_text)
        if base_id:
            self.base_id_var.set(base_id)
            self.update_status_label(_("Base ID extracted: {}").format(base_id), AppStyle.FG_COLOR)
        else:
            self.app_actions.warn(_("Could not extract base ID from filename. Please enter it manually."))
            self.update_status_label(_("Could not extract base ID. Please enter it manually."), "orange")

    def find_related_files(self, event=None):
        """Find files with related filenames in the target directory."""
        base_id = self.base_id_var.get().strip()
        target_dir = self.target_dir_var.get().strip()
        
        if not base_id:
            self.app_actions.toast(_("Please enter a base ID or extract it from a filename."))
            return
            
        if not target_dir:
            self.app_actions.toast(_("Please select a target directory to search in."))
            return
            
        if not os.path.isdir(target_dir):
            self.app_actions.warn(_("Target directory does not exist."))
            return
        
        # Save the target directory and base ID for next time
        GoToFile.last_target_directory = target_dir
        GoToFile.last_base_id = base_id
        GoToFile.save_persisted_data()
        
        # Add to recent directories for the target directory window
        TargetDirectoryWindow.add_recent_directory(target_dir)
        
        # Find matching files (includes large directory confirmation)
        matching_files = self.find_matching_files(target_dir, base_id)
        
        # Update results
        self.results_listbox.delete(0, 'end')
        if matching_files:
            for file_path in matching_files:
                self.results_listbox.insert('end', file_path)
            # Restore normal font color when results are found
            self.update_status_label(_("Found {} related filenames").format(len(matching_files)), AppStyle.FG_COLOR)
        else:
            # Use a warning color when no results are found
            self.update_status_label(_("No related filenames found with base ID \"{0}\" in {1}").format(base_id, target_dir), "orange")

    def extract_base_id(self, filename):
        """
        Extract base ID from filename using common delimiters.
        For example: "SDWebUI_17602175357792320_0_s.png" -> "SDWebUI_17602175357792320"
        Preserves original delimiters when possible.
        """
        # Get only the basename (filename without directory path), remove the file extension
        basename = os.path.splitext(os.path.basename(filename))[0]
        
        # Split by common delimiters (space, underscore, dash, dot) while preserving delimiters
        delimiter_pattern = r'([_\s\-\.]+)'
        parts = re.split(delimiter_pattern, basename)
        
        if len(parts) == 0:
            return basename
        
        # If only one part (no delimiters), check if it's sufficiently long to be a base ID
        if len(parts) == 1:
            single_part = parts[0]
            if len(single_part) >= 8 and any(c.isalnum() for c in single_part):
                return single_part
            return basename
        
        # Reconstruct base ID preserving original delimiters
        # Strategy: Always include at least two parts (one delimiter) unless the first part
        # is sufficiently long (>= 30 chars) and unique-looking
        base_id = parts[0]
        first_part_len = len(parts[0])
        
        # If first part is already quite long (>= 30 chars), it's likely a complete base ID
        # Only return single part if it's long enough to be unique
        if first_part_len >= 30:
            return base_id
        
        # Always include at least the first delimiter + second part (two parts total)
        # This ensures we have at least one delimiter in the base ID
        if len(parts) < 3:  # Need at least: [part1, delimiter, part2, ...]
            # Not enough parts, return what we have if valid
            if len(base_id) >= 3 and any(c.isalnum() for c in base_id):
                return base_id
            return basename
        
        delimiter = parts[1]
        second_part = parts[2]
        
        # If second part is empty (filename ends with delimiter) or <= 4 characters (likely a suffix), return just the first part if it's valid
        if not second_part or len(second_part) <= 4:
            if len(base_id) >= 3 and any(c.isalnum() for c in base_id):
                return base_id
            return basename
        
        base_id = base_id + delimiter + second_part
        
        # Check if the first two parts are sufficient (long enough and unique enough)
        # If they are, stop here. Only add more parts if the first two are too short.
        base_id_len = len(base_id)
        if base_id_len >= 10:  # First two parts are long enough, they should be unique
            return base_id
        
        # First two parts are too short, continue adding parts until we have something reasonable
        # But stop when we encounter suffixes (parts <= 4 characters) or empty strings
        for i in range(3, len(parts), 2):  # Start from index 3 (after first two parts)
            if i + 1 < len(parts):
                delimiter = parts[i]
                next_part = parts[i + 1]
                
                # Stop if next part is empty (filename ends with delimiter) or <= 4 characters (likely a suffix)
                if not next_part or len(next_part) <= 4:
                    break
                
                # Add this part to make the base ID longer/more unique
                candidate = base_id + delimiter + next_part
                if len(candidate) >= 3 and any(c.isalnum() for c in candidate):
                    base_id = candidate
                    # If we've reached a reasonable length (>= 10), we can stop
                    if len(base_id) >= 10:
                        break
                else:
                    break
            else:
                break
        
        # Final validation
        if len(base_id) >= 3 and any(c.isalnum() for c in base_id):
            return base_id
        
        return basename

    @staticmethod
    def _get_char_category(char):
        """Determine the category of a character: alpha, digit, or other."""
        if char.isalpha():
            return CharCategory.ALPHA
        elif char.isdigit():
            return CharCategory.DIGIT
        else:
            return CharCategory.OTHER

    def find_matching_files(self, target_dir, base_id, threshold=400000):
        """Find files in target directory that start with the base ID."""
        matching_files = []
        normalized_dir = os.path.normpath(os.path.abspath(target_dir))
        
        # Check if directory needs confirmation
        needs_confirmation = normalized_dir not in GoToFile.confirmed_directories
        last_category = GoToFile._get_char_category(base_id[-1]) if base_id else CharCategory.OTHER
        
        try:
            file_count = 0
            for root, dirs, files in os.walk(target_dir):
                for file in files:
                    file_count += 1
                    
                    # Check for large directory confirmation if needed
                    if needs_confirmation and file_count > threshold:
                        message = _("The directory '{0}' contains many files ({1} files found so far). Searching may take a while. Do you want to proceed?").format(target_dir, file_count)
                        result = self.app_actions.alert(_("Large Directory"), message, kind="askyesno")
                        
                        if result:
                            # User confirmed, add to confirmed directories (MRU)
                            GoToFile._add_confirmed_directory(normalized_dir)
                            GoToFile.save_persisted_data()
                            needs_confirmation = False
                        else:
                            # User cancelled, return empty results
                            self.app_actions.toast(_("Search cancelled by user."))
                            return []
                    
                    file_path = os.path.join(root, file)
                    filename = os.path.basename(file_path)
                    filename_without_ext = os.path.splitext(filename)[0]
                    
                    # Check if filename starts with base ID followed by a delimiter or equals the base ID
                    # Support all common delimiters: underscore, space, dash, dot
                    # Also match if character category changes (e.g., letter to digit, digit to letter)
                    if filename_without_ext.startswith(base_id):
                        # Check if it's an exact match or followed by an allowed delimiter
                        if len(filename_without_ext) == len(base_id):
                            # Exact match
                            matching_files.append(file_path)
                        else:
                            # Check if the next character is an allowed delimiter or if character category changes
                            next_char = filename_without_ext[len(base_id)]
                            
                            # Check for delimiter match
                            if next_char in ('_', ' ', '-', '.'):
                                matching_files.append(file_path)
                            # Check if character category changes between last char of base_id and next_char
                            # If categories are different, it's a match
                            elif last_category != GoToFile._get_char_category(next_char):
                                matching_files.append(file_path)
            
            # If we completed the search without hitting the threshold, consider it confirmed (MRU)
            if needs_confirmation:
                GoToFile._add_confirmed_directory(normalized_dir)
                GoToFile.save_persisted_data()
            
            # Sort by filename
            matching_files.sort(key=lambda x: os.path.basename(x).lower())
            
        except Exception as e:
            self.app_actions.warn(_("Error searching directory: {}").format(str(e)))
        
        return matching_files

    def on_result_double_click(self, event):
        """Handle double-click on a result file to open it."""
        selection = self.results_listbox.curselection()
        if selection:
            file_path = self.results_listbox.get(selection[0])
            # Set the file path in the search box and go to it
            self.search_text.set(file_path)
            # Update status to indicate we're opening the file
            self.update_status_label(_("Opening file: {}").format(os.path.basename(file_path)), AppStyle.FG_COLOR)
            self.go_to_file()

