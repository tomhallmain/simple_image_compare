import os
from tkinter import Label, LEFT, W, font
from tkinter.ttk import Button

from utils.app_info_cache import app_info_cache
from utils.app_style import AppStyle
from lib.tk_scroll_demo import ScrollFrame
from lib.multi_display import SmartToplevel
from utils.translations import I18N

_ = I18N._

class FavoritesWindow:
    COL_0_WIDTH = 600
    MAX_ROWS = 30
    has_any_favorites = False  # Class-level property to track if any favorites exist
    
    @staticmethod
    def store_favorites():
        for d in app_info_cache._get_directory_info().keys():
            favs = app_info_cache.get(d, "favorites", default_val=None)
            if favs is not None:
                app_info_cache.set(d, "favorites", favs)

    @staticmethod
    def load_favorites():
        any_favs = False
        for d in app_info_cache._get_directory_info().keys():
            favs = app_info_cache.get(d, "favorites", default_val=None)
            if favs is not None and len(favs) > 0:
                any_favs = True
            if favs is not None:
                app_info_cache.set(d, "favorites", favs)
        FavoritesWindow.has_any_favorites = any_favs

    @staticmethod
    def get_favorites(base_dir):
        return list(app_info_cache.get(base_dir, "favorites", default_val=[]))

    @staticmethod
    def add_favorite(base_dir, image_path, toast_callback=None):
        """
        Add the given image_path to the favorites for base_dir, persist, and optionally show a toast.
        """
        favs = app_info_cache.get(base_dir, "favorites", default_val=[])
        if image_path not in favs:
            favs.append(image_path)
            app_info_cache.set(base_dir, "favorites", favs)
            app_info_cache.store()
            if toast_callback:
                toast_callback(_("Added favorite: ") + image_path)

    def __init__(self, app_master, app_actions, geometry="700x800"):
        self.app_master = app_master
        self.app_actions = app_actions
        
        # Get parent window position to determine which display to use
        parent_x = app_master.winfo_x()
        parent_y = app_master.winfo_y()
        
        # For large windows, position at the top of the screen (Y=0) on the same display as parent
        # but slightly offset horizontally to avoid completely overlapping the parent window
        offset_x = 50  # Small horizontal offset from parent
        new_x = parent_x + offset_x
        new_y = 0  # Always position at the top of the screen
        
        # Create geometry string with custom positioning
        positioned_geometry = f"{geometry}+{new_x}+{new_y}"
        
        self.master = SmartToplevel(persistent_parent=app_master, title=_("Favorites"), geometry=positioned_geometry, auto_position=False)
        self.frame = ScrollFrame(self.master, bg_color=AppStyle.BG_COLOR)
        self.frame.pack(side="top", fill="both", expand=True)
        self.favorite_btns = []
        self.remove_btns = []
        self.header_labels = []
        self.favorite_labels = []
        self.favorites_by_dir = self._gather_favorites_by_dir()
        self._add_favorites_widgets()
        self.master.bind("<Escape>", self.close_window)
        self.frame.after(1, lambda: self.frame.focus_force())

    def _gather_favorites_by_dir(self):
        # Get open directories from app_actions, then recent directories, then all others
        open_dirs = []
        if hasattr(self.app_actions, "get_open_directories"):
            open_dirs = self.app_actions.get_open_directories()
        recent_dirs = []
        try:
            from files.recent_directory_window import RecentDirectories
            recent_dirs = RecentDirectories.directories[:]
        except Exception:
            pass
        # Get all directories with favorites
        all_dirs = set()
        for d in app_info_cache._get_directory_info().keys():
            favs = app_info_cache.get(d, "favorites", default_val=[])
            if favs:
                all_dirs.add(d)
        # Order: open_dirs, then recent_dirs, then others
        ordered_dirs = []
        seen = set()
        for d in open_dirs + recent_dirs:
            nd = os.path.normpath(os.path.abspath(d))
            if nd in all_dirs and nd not in seen:
                ordered_dirs.append(nd)
                seen.add(nd)
        for d in all_dirs:
            if d not in seen:
                ordered_dirs.append(d)
                seen.add(d)
        favorites_by_dir = {}
        total_favs = 0
        for d in ordered_dirs:
            favs = app_info_cache.get(d, "favorites", default_val=[])
            if favs:
                favorites_by_dir[d] = favs[:]
                total_favs += len(favs)
        FavoritesWindow.has_any_favorites = total_favs > 0
        return favorites_by_dir

    def _add_favorites_widgets(self):
        self.help_labels = []
        if not FavoritesWindow.has_any_favorites:
            help_label = Label(self.frame.viewPort)
            help_text = _("No favorites set.\n\nTo add a favorite, right-click an image and select 'Add to Favorites'.")
            self._add_label(help_label, help_text, row=0, column=0, wraplength=self.COL_0_WIDTH)
            self.help_labels.append(help_label)
            return
        row = 0
        for base_dir, favorites in self.favorites_by_dir.items():
            # Header row for directory
            header = Label(self.frame.viewPort)
            self.header_labels.append(header)
            dir_text = os.path.normpath(base_dir)
            self._add_label(header, f"{_('Directory')}: {dir_text}", row=row, column=0, wraplength=self.COL_0_WIDTH, header=True)
            row += 1
            for fav in favorites:
                fav_label = Label(self.frame.viewPort)
                self.favorite_labels.append(fav_label)
                fav_text = os.path.basename(fav)
                self._add_label(fav_label, fav_text, row=row, column=0, wraplength=self.COL_0_WIDTH)
                open_btn = Button(self.frame.viewPort, text=_('Open'))
                self.favorite_btns.append(open_btn)
                open_btn.grid(row=row, column=1)
                def open_handler(event, fav=fav, base_dir=base_dir):
                    return self.open_favorite(event, fav, base_dir)
                open_btn.bind("<Button-1>", open_handler)
                remove_btn = Button(self.frame.viewPort, text=_('Remove Favorite'))
                self.remove_btns.append(remove_btn)
                remove_btn.grid(row=row, column=2)
                def remove_handler(event, fav=fav, base_dir=base_dir):
                    return self.remove_favorite(event, fav, base_dir)
                remove_btn.bind("<Button-1>", remove_handler)
                row += 1

    def _add_label(self, label_ref, text, row=0, column=0, wraplength=500, header=False):
        label_ref['text'] = text
        label_ref.grid(column=column, row=row, sticky=W)
        # Set font: bold for header, normal otherwise
        base_font = font.nametofont(label_ref.cget("font"))
        if header:
            label_font = base_font.copy()
            label_font.configure(weight="bold")
            label_ref.config(font=label_font)
        label_ref.config(wraplength=wraplength, justify=LEFT, bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)

    def open_favorite(self, event, fav, base_dir):
        # Use app_actions to open the favorite in the appropriate window
        if hasattr(self.app_actions, "get_window"):
            window = self.app_actions.get_window(base_dir=base_dir)
            if window is not None:
                window.go_to_file(search_text=os.path.basename(fav), exact_match=True)
                window.media_canvas.focus()
                self.app_actions.toast(_("Opened favorite: ") + fav)
                return
        # Fallback: open new window
        if hasattr(self.app_actions, "new_window"):
            self.app_actions.new_window(base_dir=base_dir, image_path=fav)
            self.app_actions.toast(_("Opened favorite in new window: ") + fav)

    def remove_favorite(self, event, fav, base_dir):
        favs = app_info_cache.get(base_dir, "favorites", default_val=[])
        if fav in favs:
            favs.remove(fav)
            app_info_cache.set(base_dir, "favorites", favs)
            app_info_cache.store()
            self.app_actions.toast(_("Removed favorite: ") + fav)
            self._refresh_widgets()

    def _clear_widgets(self):
        for label in self.header_labels + self.favorite_labels + self.help_labels:
            label.destroy()
        for btn in self.favorite_btns + self.remove_btns:
            btn.destroy()
        self.header_labels = []
        self.favorite_labels = []
        self.favorite_btns = []
        self.remove_btns = []
        self.help_labels = []

    def _refresh_widgets(self):
        self._clear_widgets()
        self.favorites_by_dir = self._gather_favorites_by_dir()
        self._add_favorites_widgets()
        self.master.update()

    def close_window(self, event=None):
        self.master.destroy() 