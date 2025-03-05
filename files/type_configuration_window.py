import tkinter as tk
from tkinter import ttk
from typing import Dict, Set

from utils.config import config
from utils.constants import CompareMediaType
from utils.translations import I18N
from utils.utils import Utils

_ = I18N._


class TypeConfigurationWindow:
    _window = None
    _checkboxes: Dict[CompareMediaType, tk.BooleanVar] = {}

    @classmethod
    def show(cls):
        if cls._window is None:
            cls._window = tk.Toplevel()
            cls._window.title(_("Media Type Configuration"))
            cls._window.geometry("300x200")
            cls._window.resizable(False, False)
            cls._window.transient(cls._window.master)
            cls._window.grab_set()

            # Create main frame
            main_frame = ttk.Frame(cls._window, padding="10")
            main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

            # Add title label
            title_label = ttk.Label(
                main_frame,
                text=_("Select media types to enable:")
            )
            title_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
            row = 1

            # Create checkboxes for each media type
            for media_type in CompareMediaType:
                var = tk.BooleanVar(value=cls._is_media_type_enabled(media_type))
                cls._checkboxes[media_type] = var
                
                cb = ttk.Checkbutton(
                    main_frame,
                    text=_(media_type.name.capitalize()),
                    variable=var
                )
                cb.grid(row=row, column=0, sticky=tk.W, pady=5)
                
                # Disable IMAGE checkbox and ensure it's always checked
                if media_type == CompareMediaType.IMAGE:
                    cb.state(['disabled'])
                    var.set(True)
                
                row += 1

            # Add buttons
            button_frame = ttk.Frame(main_frame)
            button_frame.grid(row=row, column=0, pady=20)

            ttk.Button(
                button_frame,
                text=_("Apply"),
                command=cls._apply_changes
            ).pack(side=tk.LEFT, padx=5)

            ttk.Button(
                button_frame,
                text=_("Cancel"),
                command=cls._window.destroy
            ).pack(side=tk.LEFT, padx=5)

            # Center the window
            cls._window.update_idletasks()
            width = cls._window.winfo_width()
            height = cls._window.winfo_height()
            x = (cls._window.winfo_screenwidth() // 2) - (width // 2)
            y = (cls._window.winfo_screenheight() // 2) - (height // 2)
            cls._window.geometry(f"{width}x{height}+{x}+{y}")

        cls._window.lift()
        cls._window.focus_force()

    @classmethod
    def _is_media_type_enabled(cls, media_type: CompareMediaType) -> bool:
        """Check if a media type is currently enabled in the config."""
        if media_type == CompareMediaType.IMAGE:
            return True  # Images are always enabled
        elif media_type == CompareMediaType.VIDEO:
            return config.enable_videos
        elif media_type == CompareMediaType.GIF:
            return ".gif" in config.video_types
        elif media_type == CompareMediaType.PDF:
            return config.enable_pdfs
        return False

    @classmethod
    def _apply_changes(cls):
        """Apply the changes to the config."""
        changes_made = False

        # Handle video types
        if cls._checkboxes[CompareMediaType.VIDEO].get() != config.enable_videos:
            config.enable_videos = cls._checkboxes[CompareMediaType.VIDEO].get()
            changes_made = True

        # Handle GIF
        if cls._checkboxes[CompareMediaType.GIF].get() != (".gif" in config.video_types):
            if cls._checkboxes[CompareMediaType.GIF].get():
                if ".gif" not in config.video_types:
                    config.video_types.append(".gif")
            else:
                if ".gif" in config.video_types:
                    config.video_types.remove(".gif")
            changes_made = True

        # Handle PDF
        if cls._checkboxes[CompareMediaType.PDF].get() != config.enable_pdfs:
            config.enable_pdfs = cls._checkboxes[CompareMediaType.PDF].get()
            if config.enable_pdfs and ".pdf" not in config.file_types:
                config.file_types.append(".pdf")
            elif not config.enable_pdfs and ".pdf" in config.file_types:
                config.file_types.remove(".pdf")
            changes_made = True

        if changes_made:
            # Update file_types list
            config.file_types = list(config.image_types)
            if config.enable_videos:
                config.file_types.extend(config.video_types)
            Utils.log(_("Media type configuration updated"))
            cls._window.destroy()
            cls._window = None 