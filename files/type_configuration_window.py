from tkinter import Toplevel, Frame, Label, BooleanVar, LEFT, W, messagebox
from tkinter.ttk import Checkbutton, Button, Separator

from utils.app_style import AppStyle
from utils.config import config
from utils.constants import CompareMediaType
from utils.translations import I18N

_ = I18N._


class TypeConfigurationWindow:
    top_level = None
    COL_0_WIDTH = 600
    _pending_changes = {}  # Store pending changes until confirmed
    _original_config = {}  # Store original config state for comparison

    @staticmethod
    def get_geometry():
        width = 600
        height = 250  # Increased height for better spacing
        return f"{width}x{height}"

    @classmethod
    def show(cls, master=None, app_actions=None):
        if cls.top_level is not None:
            cls.top_level.lift()
            return
        if master is None:
            raise ValueError("Master window must be provided")
        if app_actions is None:
            raise ValueError("AppActions instance must be provided")
            
        # Store original config state
        cls._original_config = {
            CompareMediaType.VIDEO: config.enable_videos,
            CompareMediaType.GIF: config.enable_gifs,
            CompareMediaType.PDF: config.enable_pdfs
        }
            
        cls.top_level = Toplevel(master, bg=AppStyle.BG_COLOR)
        cls.top_level.title(_("Media Type Configuration"))
        cls.top_level.geometry(cls.get_geometry())
        cls.top_level.protocol("WM_DELETE_WINDOW", cls.on_closing)
        cls.top_level.bind("<Escape>", cls.on_closing)
        
        # Main container frame with padding
        main_frame = Frame(cls.top_level, bg=AppStyle.BG_COLOR)
        main_frame.grid(column=0, row=0, padx=20, pady=20, sticky='nsew')
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)  # Make the content area expandable

        # Title label with increased font size and padding
        title_label = Label(main_frame, font=('Helvetica', 12, 'bold'))
        title_label['text'] = _("Configure Media Types")
        title_label.grid(column=0, row=0, sticky=W, pady=(0, 15))
        title_label.config(wraplength=cls.COL_0_WIDTH, justify=LEFT, bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)

        # Content frame for checkboxes
        content_frame = Frame(main_frame, bg=AppStyle.BG_COLOR)
        content_frame.grid(column=0, row=1, sticky='nsew')
        content_frame.columnconfigure(0, weight=1)

        # Create checkboxes for each media type with consistent spacing
        row = 0
        for media_type in CompareMediaType:
            var = cls._get_media_type_var(media_type)
            check = Checkbutton(content_frame, text=media_type.get_translation(), variable=var)
            check.grid(column=0, row=row, sticky=W, pady=5)
            
            if media_type == CompareMediaType.IMAGE:
                check.state(['disabled'])  # Disable the checkbox
                var.set(True)  # Ensure it's always checked
            else:
                check.config(command=lambda m=media_type, v=var: cls._store_pending_change(m, v))
            
            row += 1

        # Separator line
        separator = Separator(main_frame, orient='horizontal')
        separator.grid(column=0, row=2, sticky='ew', pady=15)

        # Button frame for better alignment
        button_frame = Frame(main_frame, bg=AppStyle.BG_COLOR)
        button_frame.grid(column=0, row=3, sticky='e')
        
        # Add confirmation button with padding
        confirm_button = Button(button_frame, text=_("Apply Changes"), 
                              command=lambda: cls._confirm_changes(app_actions))
        confirm_button.grid(column=0, row=0, padx=5)

        main_frame.after(1, lambda: main_frame.focus_force())

    @classmethod
    def on_closing(cls, event=None):
        """Safely handle window closing."""
        if cls.top_level is not None:
            cls._pending_changes.clear()
            cls._original_config.clear()
            cls.top_level.destroy()
            cls.top_level = None

    @classmethod
    def _store_pending_change(cls, media_type: CompareMediaType, var: BooleanVar):
        """Store the pending change for a media type."""
        cls._pending_changes[media_type] = var.get()

    @classmethod
    def _has_changes(cls) -> bool:
        """Determine if any configuration changes have been made."""
        if not cls._pending_changes:
            return False
            
        for media_type, new_value in cls._pending_changes.items():
            if media_type in cls._original_config:
                if new_value != cls._original_config[media_type]:
                    return True
        return False

    @classmethod
    def _confirm_changes(cls, app_actions):
        """Show confirmation dialog and apply changes if confirmed."""
        if not cls._has_changes():
            cls.on_closing()
            return

        # Skip confirmation if no compares exist
        if app_actions.find_window_with_compare() is None:
            cls._apply_changes(app_actions)
            return

        res = app_actions.alert(_("Confirm Changes"), 
                                _("This will clear all existing compares in open windows. Continue?"),
                                kind="warning")
        not_ok = res != messagebox.OK and res != True
        if not_ok:
            return
        cls._apply_changes(app_actions)

    @classmethod
    def _apply_changes(cls, app_actions):
        """Apply all pending changes and refresh compares."""
        # Apply all pending changes
        for media_type, enabled in cls._pending_changes.items():
            if media_type == CompareMediaType.VIDEO:
                config.enable_videos = enabled
                # Handle video types in file_types
                if enabled:
                    # Add video types if not present
                    for ext in config.video_types:
                        if ext not in config.file_types:
                            config.file_types.append(ext)
                else:
                    # Remove video types
                    config.file_types = [ext for ext in config.file_types 
                                         if ext not in config.video_types]
            elif media_type == CompareMediaType.GIF:
                config.enable_gifs = enabled
                if enabled and ".gif" not in config.file_types:
                    config.file_types.append(".gif")
                elif not enabled and ".gif" in config.file_types:
                    config.file_types.remove(".gif")
            elif media_type == CompareMediaType.PDF:
                config.enable_pdfs = enabled
                if config.enable_pdfs and ".pdf" not in config.file_types:
                    config.file_types.append(".pdf")
                elif not config.enable_pdfs and ".pdf" in config.file_types:
                    config.file_types.remove(".pdf")
        
        app_actions.refresh_all_compares()
        app_actions.toast(_("Media type configuration updated"), time_in_seconds=5)
        cls.on_closing()

    @classmethod
    def _get_media_type_var(cls, media_type: CompareMediaType):
        """Get the current value for a media type from config."""
        var = BooleanVar()
        if media_type == CompareMediaType.IMAGE:
            var.set(True)  # Always True for IMAGE
        elif media_type == CompareMediaType.VIDEO:
            var.set(config.enable_videos)
        elif media_type == CompareMediaType.GIF:
            var.set(config.enable_gifs)
        elif media_type == CompareMediaType.PDF:
            var.set(config.enable_pdfs)
        return var 