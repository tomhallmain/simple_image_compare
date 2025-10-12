from tkinter import Frame, Label, BooleanVar, LEFT, W, messagebox
from tkinter.ttk import Checkbutton, Button, Separator

from lib.multi_display import SmartToplevel
from utils.app_style import AppStyle
from utils.app_info_cache import app_info_cache
from utils.config import config
from utils.constants import CompareMediaType
from utils.translations import I18N
from image.frame_cache import (
    has_imported_pypdfium2,
    has_imported_cairosvg,
    has_imported_pyppeteer
)

_ = I18N._


class TypeConfigurationWindow:
    top_level = None
    COL_0_WIDTH = 600
    _pending_changes = {}  # Store pending changes until confirmed
    _original_config = {}  # Store original config state for comparison

    # Media type descriptions
    MEDIA_TYPE_DESCRIPTIONS = {
        CompareMediaType.IMAGE: _("Basic image files (PNG, JPG, etc.)"),
        CompareMediaType.VIDEO: _("Video files (MP4, AVI, etc.) - First frame will be extracted"),
        CompareMediaType.GIF: _("Animated GIF files - First frame will be extracted"),
        CompareMediaType.PDF: _("PDF documents - First page will be extracted"),
        CompareMediaType.SVG: _("Vector graphics - Will be converted to raster image"),
        CompareMediaType.HTML: _("HTML files - Will be rendered and converted to image")
    }

    # Dependency information
    DEPENDENCY_INFO = {
        CompareMediaType.PDF: {
            'available': has_imported_pypdfium2,
            'package': 'pypdfium2',
            'description': _("PDF support requires pypdfium2 package")
        },
        CompareMediaType.SVG: {
            'available': has_imported_cairosvg,
            'package': 'cairosvg',
            'description': _("SVG support requires cairosvg package")
        },
        CompareMediaType.HTML: {
            'available': has_imported_pyppeteer,
            'package': 'pyppeteer',
            'description': _("HTML support requires pyppeteer package")
        }
    }

    @classmethod
    def load_pending_changes(cls):
        pending_changes = app_info_cache.get_meta("file_type_configuration", default_val={})
        assert isinstance(pending_changes, dict)
        for media_type, enabled in pending_changes.items():
            cls._pending_changes[CompareMediaType[media_type]] = enabled

    @classmethod
    def save_pending_changes(cls):
        pending_changes = {}
        for media_type, enabled in cls._original_config.items():
            if media_type in cls._pending_changes:
                pending_changes[media_type.name] = cls._pending_changes[media_type]
            else:
                pending_changes[media_type.name] = enabled
        app_info_cache.set_meta("file_type_configuration", pending_changes)

    @staticmethod
    def get_geometry():
        width = 700  # Increased width for better readability
        height = 450  # Increased height for dependency info
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
            CompareMediaType.PDF: config.enable_pdfs,
            CompareMediaType.SVG: config.enable_svgs,
            CompareMediaType.HTML: config.enable_html,
        }
            
        cls.top_level = SmartToplevel(persistent_parent=master, title=_("Media Type Configuration"), geometry=cls.get_geometry())
        cls.top_level.protocol("WM_DELETE_WINDOW", cls.on_closing)
        cls.top_level.bind("<Escape>", cls.on_closing)
        
        # Main container frame with padding
        main_frame = Frame(cls.top_level, bg=AppStyle.BG_COLOR)
        main_frame.grid(column=0, row=0, padx=20, pady=20, sticky='nsew')
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)  # Make the content area expandable

        # Title and description
        title_frame = Frame(main_frame, bg=AppStyle.BG_COLOR)
        title_frame.grid(column=0, row=0, sticky='ew', pady=(0, 15))
        title_frame.columnconfigure(0, weight=1)

        title_label = Label(title_frame, font=('Helvetica', 14, 'bold'))
        title_label['text'] = _("Configure Media Types")
        title_label.grid(column=0, row=0, sticky=W)
        title_label.config(bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)

        description_label = Label(title_frame, font=('Helvetica', 10))
        description_label['text'] = _("Select which types of media files you want to compare. "
                                    "Changes will require a refresh of open comparisons but "
                                    "files in browsing mode should update automatically.")
        description_label.grid(column=0, row=1, sticky=W, pady=(5, 0))
        description_label.config(wraplength=cls.COL_0_WIDTH, justify=LEFT, bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)

        # Content frame for checkboxes
        content_frame = Frame(main_frame, bg=AppStyle.BG_COLOR)
        content_frame.grid(column=0, row=1, sticky='nsew')
        content_frame.columnconfigure(0, weight=1)

        # Create checkboxes for each media type with descriptions
        row = 0
        for media_type in CompareMediaType:
            # Container for each media type
            media_frame = Frame(content_frame, bg=AppStyle.BG_COLOR)
            media_frame.grid(column=0, row=row, sticky='ew', pady=5)
            media_frame.columnconfigure(1, weight=1)

            # Checkbox
            var = cls._get_media_type_var(media_type)
            check = Checkbutton(media_frame, text=media_type.get_translation(), variable=var)
            check.grid(column=0, row=0, sticky=W)
            
            # Description and dependency info
            desc_frame = Frame(media_frame, bg=AppStyle.BG_COLOR)
            desc_frame.grid(column=1, row=0, sticky='w', padx=(5, 0))
            desc_frame.columnconfigure(0, weight=1)
            
            # Description
            desc_label = Label(desc_frame, text=cls.MEDIA_TYPE_DESCRIPTIONS[media_type],
                             font=('Helvetica', 9), fg=AppStyle.FG_COLOR, bg=AppStyle.BG_COLOR)
            desc_label.grid(column=0, row=0, sticky=W)
            
            # Dependency info if applicable
            if media_type in cls.DEPENDENCY_INFO:
                dep_info = cls.DEPENDENCY_INFO[media_type]
                if not dep_info['available']:
                    dep_label = Label(desc_frame, 
                                    text=f"⚠️ {dep_info['description']} (pip install {dep_info['package']})",
                                    font=('Helvetica', 9), fg='#FFA500', bg=AppStyle.BG_COLOR)
                    dep_label.grid(column=0, row=1, sticky=W, pady=(2, 0))
                    check.state(['disabled'])
            
            if media_type == CompareMediaType.IMAGE:
                check.state(['disabled'])  # Disable the checkbox
                var.set(True)  # Ensure it's always checked
            else:
                check.config(command=lambda m=media_type, v=var: cls._store_pending_change(m, v))
            
            row += 1

        # Separator line
        separator = Separator(main_frame, orient='horizontal')
        separator.grid(column=0, row=2, sticky='ew', pady=15)

        # Button frame
        button_frame = Frame(main_frame, bg=AppStyle.BG_COLOR)
        button_frame.grid(column=0, row=3, sticky='e')
        
        # Cancel button
        cancel_button = Button(button_frame, text=_("Cancel"), 
                             command=cls.on_closing)
        cancel_button.grid(column=0, row=0, padx=5)
        
        # Apply button
        confirm_button = Button(button_frame, text=_("Apply Changes"), 
                              command=lambda: cls._confirm_changes(app_actions))
        confirm_button.grid(column=1, row=0, padx=5)

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
            if media_type not in cls._original_config or new_value != cls._original_config[media_type]:
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
            cls.apply_changes(app_actions)
            return

        res = app_actions.alert(_("Confirm Changes"), 
                                _("This will clear all existing compares in open windows. Continue?"),
                                kind="warning")
        not_ok = res != messagebox.OK and res != True
        if not_ok:
            return
        cls.apply_changes(app_actions)

    @classmethod
    def apply_changes(cls, app_actions = None):
        """Apply all pending changes and refresh compares."""
        if cls._has_changes():
            cls.save_pending_changes()
        elif app_actions is None:
            return

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
            elif media_type == CompareMediaType.SVG:
                config.enable_svgs = enabled
                if config.enable_svgs and ".svg" not in config.file_types:
                    config.file_types.append(".svg")
                elif not config.enable_svgs and ".svg" in config.file_types:
                    config.file_types.remove(".svg")
            elif media_type == CompareMediaType.HTML:
                config.enable_html = enabled
                if config.enable_html:
                    for ext in ['.html', '.htm']:
                        if ext not in config.file_types:
                            config.file_types.append(ext)
                else:
                    config.file_types = [ext for ext in config.file_types 
                                       if ext not in ['.html', '.htm']]

        if app_actions is not None:
            app_actions.refresh_all_compares()
            app_actions.toast(_("Media type configuration updated"), time_in_seconds=5)
            cls.on_closing()
        else:
            cls._pending_changes.clear()

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
        elif media_type == CompareMediaType.SVG:
            var.set(config.enable_svgs)
        elif media_type == CompareMediaType.HTML:
            var.set(config.enable_html)
        return var 