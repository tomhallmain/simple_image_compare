"""
AppWindow -- main application window orchestrator (PySide6).

This is the thin shell described in APP_DECOMPOSITION.md. It owns the
top-level SmartMainWindow, instantiates all controller objects, assembles
the AppActions dict, and handles top-level lifecycle events.

All substantial logic lives in the controller modules:
    SidebarPanel, MediaNavigator, SearchController, FileMarksController,
    FileOpsController, WindowLauncher, KeyBindingManager, ContextMenuBuilder,
    NotificationController, WindowManager, CacheController.
"""

import os
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QSplitter, QWidget, QVBoxLayout, QFrame

from files.file_browser import FileBrowser
from compare.compare_manager import CompareManager
from ui.files.marked_file_mover_qt import MarkedFiles
from lib.multi_display_qt import SmartMainWindow
from ui.app_style import AppStyle
from ui.custom_title_bar import FramelessWindowMixin, WindowResizeHandler
from ui.app_window.cache_controller import CacheController
from ui.app_window.context_menu_builder import ContextMenuBuilder
from ui.app_window.file_marks_controller import FileMarksController
from ui.app_window.file_ops_controller import FileOpsController
from ui.app_window.key_binding_manager import KeyBindingManager
from ui.app_window.media_frame import MediaFrame
from ui.app_window.media_navigator import MediaNavigator
from ui.app_window.notification_controller import NotificationController
from ui.app_window.search_controller import SearchController
from ui.app_window.sidebar_panel import SidebarPanel
from ui.app_window.window_launcher import WindowLauncher
from ui.app_window.window_manager import WindowManager
from utils.app_actions import AppActions
from utils.config import config, FileCheckConfig, SlideshowConfig, StoreCacheConfig
from utils.constants import Mode, Direction
from utils.logging_setup import get_logger
from utils.translations import I18N
from utils.utils import Utils

_ = I18N._
logger = get_logger("app_window")


class AppWindow(FramelessWindowMixin, SmartMainWindow):
    """
    Main application window.

    Orchestrates controllers via composition. Each controller receives the
    dependencies it needs at construction time; the AppWindow itself keeps
    only cross-cutting state (mode, fullscreen flag, direction).

    Inherits FramelessWindowMixin for a custom draggable title bar, and
    SmartMainWindow for automatic geometry persistence.
    """

    # Signal for thread-safe title updates.
    # notification_manager fires threading.Timer callbacks that call
    # app_actions.title() from a background thread.  Using a Signal
    # ensures setWindowTitle always runs on the main / GUI thread.
    _sig_set_title = Signal(str)

    def __init__(
        self,
        base_dir: Optional[str] = None,
        image_path: Optional[str] = None,
        sidebar_visible: bool = config.sidebar_visible,
        do_search: bool = False,
        window_id: int = 0,
    ):
        super().__init__(restore_geometry=(window_id == 0))

        # Set up frameless window with custom title bar
        self.setup_frameless_window(
            title=_(" Simple Image Compare "), corner_radius=10
        )

        # Thread-safe title update signal → slot
        self._sig_set_title.connect(self._on_set_title)

        self.window_id = window_id
        self.base_title = ""

        # ------------------------------------------------------------------
        # Core state
        # ------------------------------------------------------------------
        self.mode = Mode.BROWSE
        self.fullscreen = False
        self.delete_lock = False
        self.img_path: Optional[str] = None
        self.prev_img_path: Optional[str] = None
        self.search_dir: Optional[str] = None
        self.is_toggled_view_matches = True
        self.direction = Direction.FORWARD
        self.has_added_buttons_for_mode = {
            Mode.BROWSE: False,
            Mode.GROUP: False,
            Mode.SEARCH: False,
            Mode.DUPLICATES: False,
        }

        # ------------------------------------------------------------------
        # Backend (non-UI) objects -- shared across controllers
        # ------------------------------------------------------------------
        self.file_browser = FileBrowser(
            recursive=config.image_browse_recursive, sort_by=config.sort_by
        )
        self.compare_manager = CompareManager(master=self)
        self.file_check_config = FileCheckConfig(self.window_id)
        self.slideshow_config = SlideshowConfig(self.window_id)
        self.store_cache_config = StoreCacheConfig(self.window_id)

        # ------------------------------------------------------------------
        # Window title
        # ------------------------------------------------------------------
        self.setWindowTitle(_(" Simple Image Compare "))

        # ------------------------------------------------------------------
        # Central widget: frameless structure with custom title bar
        # ------------------------------------------------------------------
        grip_size = getattr(self, '_frameless_grip_size', 8)

        # Outer widget for translucent background (needed for rounded corners)
        outer_widget = QWidget()
        outer_widget.setObjectName("transparentOuter")
        outer_widget.setAttribute(Qt.WA_TranslucentBackground)
        self.setCentralWidget(outer_widget)
        outer_layout = QVBoxLayout(outer_widget)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Main container frame with rounded corners
        self._main_frame = QFrame()
        self._main_frame.setObjectName("mainFrame")
        outer_layout.addWidget(self._main_frame)

        root_layout = QVBoxLayout(self._main_frame)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Custom title bar at the top
        title_bar = self.get_title_bar()
        if title_bar:
            root_layout.addWidget(title_bar)

        # Content area below title bar
        content_widget = QWidget()
        content_widget.setObjectName("contentArea")
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        root_layout.addWidget(content_widget)

        # Splitter inside content: sidebar | media frame
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        content_layout.addWidget(self.splitter)

        # Sidebar panel (left)
        self.sidebar_panel = SidebarPanel(parent=self, app_window=self)
        self.splitter.addWidget(self.sidebar_panel)

        # Media frame (right)
        self.media_frame = MediaFrame(parent=self)
        self.splitter.addWidget(self.media_frame)

        # Give most space to the media frame
        self.splitter.setStretchFactor(0, 1)  # sidebar
        self.splitter.setStretchFactor(1, 9)  # media

        if not sidebar_visible:
            self.sidebar_panel.setVisible(False)

        # Install resize handler for frameless edge resizing
        self._resize_handler = WindowResizeHandler(self, grip_size)

        # Apply combined stylesheet (base + frameless)
        self._apply_theme()

        # ------------------------------------------------------------------
        # Controllers
        # ------------------------------------------------------------------
        self.notification_ctrl = NotificationController(app_window=self)

        self.cache_ctrl = CacheController(
            app_window=self,
            file_browser=self.file_browser,
        )

        self.media_navigator = MediaNavigator(
            app_window=self,
            file_browser=self.file_browser,
            compare_manager=self.compare_manager,
            media_frame=self.media_frame,
        )

        self.search_ctrl = SearchController(
            app_window=self,
            file_browser=self.file_browser,
            compare_manager=self.compare_manager,
            sidebar_panel=self.sidebar_panel,
        )

        self.file_marks_ctrl = FileMarksController(
            app_window=self,
            file_browser=self.file_browser,
            compare_manager=self.compare_manager,
            media_navigator=self.media_navigator,
        )

        self.file_ops_ctrl = FileOpsController(
            app_window=self,
            file_browser=self.file_browser,
            compare_manager=self.compare_manager,
            media_navigator=self.media_navigator,
        )

        self.window_launcher = WindowLauncher(
            app_window=self,
        )

        # ------------------------------------------------------------------
        # Assemble AppActions dict
        # ------------------------------------------------------------------
        self.app_actions = self._build_app_actions()

        # CompareManager was created early (without app_actions) so
        # controllers could receive it.  Now wire in the real values.
        self.compare_manager.set_app_actions(self, self.app_actions)

        # ------------------------------------------------------------------
        # Key bindings & context menu (need app_actions / controllers ready)
        # ------------------------------------------------------------------
        self.key_binding_mgr = KeyBindingManager(app_window=self)
        self.context_menu_builder = ContextMenuBuilder(app_window=self)

        # ------------------------------------------------------------------
        # Register with WindowManager
        # ------------------------------------------------------------------
        if window_id == 0:
            WindowManager.set_primary(self)
        WindowManager.register(self)

        # ------------------------------------------------------------------
        # Notification manager callback
        # ------------------------------------------------------------------
        from utils.notification_manager import notification_manager
        notification_manager.set_app_actions(self.app_actions, self.window_id)

        # ------------------------------------------------------------------
        # Load cache, apply initial base directory
        # ------------------------------------------------------------------
        if not self.is_secondary():
            initial_base_dir = self.cache_ctrl.load_info_cache()
            if base_dir:
                initial_base_dir = base_dir
            if initial_base_dir:
                QTimer.singleShot(0, lambda bd=initial_base_dir: self.set_base_dir(bd))
        elif base_dir:
            QTimer.singleShot(0, lambda bd=base_dir: self.set_base_dir(bd))

        # Restore window geometry (SmartMainWindow feature)
        self.restore_window_geometry()

        # ------------------------------------------------------------------
        # Start periodic timers (replaces start_thread + async)
        # ------------------------------------------------------------------
        self.file_ops_ctrl.start_file_check_timer()
        if not self.is_secondary():
            self.cache_ctrl.start_periodic_store()
            # Re-open secondary windows that were open last session
            QTimer.singleShot(100, self._restore_secondary_windows)

        # Handle initial image_path / do_search
        if image_path is not None:
            if do_search:
                QTimer.singleShot(200, lambda: self.search_ctrl.set_search())
            else:
                QTimer.singleShot(200, lambda ip=image_path: self.media_navigator.go_to_file(search_text=ip))

        if self.is_secondary():
            QTimer.singleShot(300, lambda: self.cache_ctrl.store_info_cache())

        logger.info(f"AppWindow created (id={window_id})")

    def _restore_secondary_windows(self) -> None:
        """Re-open secondary windows that were open in the previous session."""
        from utils.app_info_cache_qt import app_info_cache
        for _dir in app_info_cache.get_meta("secondary_base_dirs", default_val=[]):
            WindowManager.add_secondary_window(_dir)
        # Re-focus the primary after all secondaries have been opened
        QTimer.singleShot(50, self._refocus_primary)

    def _refocus_primary(self) -> None:
        """Raise and focus the primary window."""
        self.raise_()
        self.activateWindow()

    # ------------------------------------------------------------------
    # AppActions assembly
    # ------------------------------------------------------------------
    def _build_app_actions(self) -> AppActions:
        """Wire the AppActions dict, mapping action names to controller methods."""
        actions = {
            # Window title -- thread-safe via Signal so that
            # notification_manager's Timer thread never touches Qt directly
            "title": self._sig_set_title.emit,
            # Window management (static)
            "new_window": WindowManager.add_secondary_window,
            "get_window": WindowManager.get_window,
            "get_open_windows": WindowManager.get_open_windows,
            "refresh_all_compares": WindowManager.refresh_all_compares,
            "find_window_with_compare": WindowManager.find_window_with_compare,
            # Notifications
            "toast": self.notification_ctrl.toast,
            "title_notify": self.notification_ctrl.title_notify,
            "_alert": self.notification_ctrl.alert,
            # Navigation / display
            "refresh": self.refresh,
            "refocus": self.refocus,
            "set_mode": self.set_mode,
            "is_fullscreen": lambda: self.fullscreen,
            "get_active_media_filepath": self.media_navigator.get_active_media_filepath,
            "create_image": self.media_navigator.create_image,
            "show_next_media": self.media_navigator.show_next_media,
            # Window launchers
            "get_media_details": self.window_launcher.open_media_details,
            "open_move_marks_window": self.file_marks_ctrl.open_move_marks_window,
            "open_password_admin_window": self.window_launcher.open_password_admin_window,
            # Search / compare
            "run_image_generation": self.search_ctrl.run_image_generation,
            "set_marks_from_downstream_related_images": self.file_marks_ctrl.set_marks_from_downstream_related_images,
            # File navigation
            "go_to_file": self.media_navigator.go_to_file,
            "go_to_file_by_index": self.media_navigator.go_to_file_by_index,
            "set_base_dir": self.set_base_dir,
            "get_base_dir": self.get_base_dir,
            # File operations
            "delete": self.file_ops_ctrl.handle_delete,
            "hide_current_media": self.file_ops_ctrl.hide_current_media,
            "copy_media_path": self.file_ops_ctrl.copy_media_path,
            "release_media_canvas": lambda: self.media_frame.release_media(),
            # Persistence
            "store_info_cache": self.cache_ctrl.store_info_cache,
            # Internal (prefixed with _)
            "_set_toggled_view_matches": self.media_navigator.set_toggled_view_matches,
            "_set_label_state": self.notification_ctrl.set_label_state,
            "_add_buttons_for_mode": self.sidebar_panel.add_buttons_for_mode,
        }
        return AppActions(actions=actions, master=self)

    # ------------------------------------------------------------------
    # Title bar / theme helpers
    # ------------------------------------------------------------------
    def setWindowTitle(self, title: str) -> None:
        """Override to keep the custom title bar text in sync."""
        super().setWindowTitle(title)
        title_bar = self.get_title_bar()
        if title_bar:
            title_bar.set_title(title)

    def _on_set_title(self, title: str) -> None:
        """Slot for :pyattr:`_sig_set_title` -- always runs on the GUI thread.

        Calls processEvents() so that the title-bar repaint happens
        immediately, even when the main thread is about to block on a
        long-running operation (e.g. TensorFlow model loading).
        """
        self.setWindowTitle(title)
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()

    def _apply_theme(self) -> None:
        """Apply the combined base + frameless stylesheet and title bar theme."""
        is_dark = AppStyle.IS_DEFAULT_THEME
        stylesheet = AppStyle.get_stylesheet() + AppStyle.get_frameless_stylesheet(is_dark)
        self.setStyleSheet(stylesheet)
        self.media_frame.set_background_color(
            AppStyle.MEDIA_BG if is_dark else AppStyle.LIGHT_MEDIA_BG
        )
        self.apply_frameless_theme(is_dark)

    # ------------------------------------------------------------------
    # Properties / simple accessors
    # ------------------------------------------------------------------
    def is_secondary(self) -> bool:
        return self.window_id != 0

    @property
    def base_dir(self) -> str:
        return self.file_browser.directory if self.file_browser else ""

    def get_base_dir(self) -> str:
        return self.base_dir

    def get_search_dir(self) -> str:
        """Return the search directory, falling back to base_dir."""
        return self.get_base_dir() if self.search_dir is None else self.search_dir

    # ------------------------------------------------------------------
    # Top-level actions (kept on AppWindow per decomposition doc)
    # ------------------------------------------------------------------
    def set_base_dir(self, base_dir_from_dir_window: Optional[str] = None) -> None:
        """
        Set the base directory and reload files.

        Ported from App.set_base_dir. If *base_dir_from_dir_window* is provided
        it is used directly; otherwise the sidebar entry is read, and if it is
        empty the recent-directory window is opened.
        """
        from files.recent_directory_window import RecentDirectories
        from utils.app_info_cache import app_info_cache as base_cache
        from utils.constants import CompareMode

        self.cache_ctrl.store_info_cache()

        if base_dir_from_dir_window is not None:
            new_dir = base_dir_from_dir_window
        else:
            entry_text = self.sidebar_panel.set_base_dir_box.text().strip()
            if not entry_text or entry_text == _("Enter base directory...") or entry_text == self.base_dir:
                if len(RecentDirectories.directories) == 0:
                    from PySide6.QtWidgets import QFileDialog
                    chosen = QFileDialog.getExistingDirectory(
                        self, _("Set image comparison directory"), self.get_base_dir()
                    )
                    if not chosen:
                        return
                    new_dir = chosen
                    RecentDirectories.directories.append(new_dir)
                else:
                    self.window_launcher.open_recent_directory_window()
                    return
            else:
                new_dir = entry_text

        if not new_dir or not os.path.isdir(new_dir):
            return

        # Check for large directory before loading
        if self._check_large_directory_before_load(new_dir):
            return  # user cancelled

        # Clear stale compare if the directory changed
        if self.compare_manager.has_compare() and new_dir != self.compare_manager.compare().base_dir:
            self.compare_manager.clear_compare()
            self.notification_ctrl.set_label_state(group_number=None, size=0)
            self.sidebar_panel.remove_all_mode_buttons()

        # Apply directory to file browser
        self.sidebar_panel.update_base_dir_display(new_dir)
        self.file_browser.set_directory(new_dir)

        # Restore per-directory settings from cache
        recursive = base_cache.get(new_dir, "recursive", default_val=False)
        sort_by_text = base_cache.get(new_dir, "sort_by", default_val=None)
        compare_mode_text = base_cache.get(new_dir, "compare_mode", default_val=None)

        if recursive != self.file_browser.recursive:
            self.file_browser.set_recursive(recursive)
            self.sidebar_panel.recursive_check.setChecked(recursive)

        if compare_mode_text:
            try:
                mode_to_set = CompareMode.get(compare_mode_text) if isinstance(compare_mode_text, str) else compare_mode_text
                if mode_to_set != self.compare_manager.compare_mode:
                    self.compare_manager.set_compare_mode(mode_to_set)
            except Exception as e:
                logger.error(f"Error setting stored compare mode: {e}")

        if self.compare_manager.compare_mode is None:
            self.compare_manager.set_compare_mode(CompareMode.CLIP_EMBEDDING)

        if sort_by_text:
            try:
                from files.file_browser import SortBy
                sb = SortBy.get(sort_by_text) if isinstance(sort_by_text, str) else sort_by_text
                self.file_browser.set_sort_by(sb)
                self.sidebar_panel.set_sort_by_value(sb.get_text())
            except Exception as e:
                logger.error(f"Error setting stored sort by: {e}")

        # Navigate to the previously-viewed file, or show the first
        if not self.compare_manager.has_compare():
            self.set_mode(Mode.BROWSE)
            previous_file = base_cache.get(new_dir, "image_cursor")
            if previous_file and previous_file != "":
                if not self.media_navigator.go_to_file(search_text=previous_file, retry_with_delay=1):
                    self.media_navigator.show_next_media()
            else:
                self.media_navigator.show_next_media()
            self.notification_ctrl.set_label_state()

        self.setWindowTitle(self.get_title_from_base_dir(overwrite=True))
        RecentDirectories.set_recent_directory(new_dir)

    def get_title_from_base_dir(self, overwrite: bool = False) -> str:
        """Generate the window title from the current base directory."""
        if overwrite:
            relative_dirpath = Utils.get_relative_dirpath(self.base_dir, levels=2)
            self.base_title = _(" Simple Image Compare ") + "- " + relative_dirpath
        return self.base_title

    def _check_large_directory_before_load(self, base_dir: str, threshold: int = 5000) -> bool:
        """
        Check if a directory has many files before loading.
        Returns True if the user cancels, False to proceed.
        """
        original_directory = self.file_browser.directory
        original_files = self.file_browser._files.copy()
        try:
            self.file_browser.directory = base_dir
            if self.file_browser.has_confirmed_dir():
                return False
            self.file_browser._gather_files()
            if self.file_browser.is_slow_total_files(threshold=threshold):
                ok = self.notification_ctrl.alert(
                    _("Large Directory Detected: {0}").format(base_dir),
                    _("A directory with a large number of files or a directory with a fair-sized number "
                      "of files on external storage was detected, which may result in a slow load time. "
                      "Please confirm you want to load the full directory."),
                    kind="askokcancel",
                )
                if not ok:
                    logger.info(f"User canceled loading large directory: {base_dir}")
                    return True
                self.file_browser.set_dir_confirmed()
        finally:
            self.file_browser.directory = original_directory
            self.file_browser._files = original_files
        return False

    def set_mode(self, mode: Mode, do_update: bool = True) -> None:
        """Change the current application mode."""
        self.mode = mode
        self.sidebar_panel.set_mode_label(mode.get_text())
        if mode != Mode.SEARCH:
            self.sidebar_panel.remove_search_mode_buttons()
        if mode not in (Mode.GROUP, Mode.DUPLICATES):
            self.sidebar_panel.remove_group_mode_buttons()

    def return_to_browsing_mode(self, event=None, suppress_toast: bool = False) -> None:
        """
        Return to browsing mode, clearing compare state.

        Ported from App.return_to_browsing_mode.
        """
        self.set_mode(Mode.BROWSE)
        self.file_browser.refresh()
        self.notification_ctrl.set_label_state()
        if self.img_path is not None:
            if not self.media_navigator.go_to_file(search_text=self.img_path, retry_with_delay=1):
                self.media_navigator.home()
        self.cache_ctrl.store_info_cache()
        if not suppress_toast:
            self.notification_ctrl.toast(_("Browsing mode set."))

    def check_many_files(
        self,
        window: "AppWindow",
        action: str = "do this action",
        threshold: int = 2000,
    ) -> bool:
        """
        Check if a window has too many files and prompt the user.

        Returns True if user cancels, False if user wants to proceed.
        Ported from App.check_many_files.
        """
        if not window.file_browser.has_confirmed_dir() and window.file_browser.is_slow_total_files(threshold=threshold):
            ok = self.notification_ctrl.alert(
                _("Many Files"),
                f"There are a lot of files in {window.base_dir} and it may take a while"
                f" to {action}.\n\nWould you like to proceed?",
                kind="askokcancel",
            )
            if not ok:
                return True
            window.file_browser.set_dir_confirmed()
        return False

    def refresh(
        self,
        show_new_images: bool = False,
        refresh_cursor: bool = False,
        file_check: bool = True,
        removed_files: Optional[list] = None,
    ) -> None:
        """
        Refresh the file list and update the display.

        Ported from App.refresh.
        """
        import time

        if removed_files is None:
            removed_files = []

        active_media_in_removed = (
            self.media_navigator.get_active_media_filepath() in removed_files
        )

        self.file_browser.refresh(
            refresh_cursor=refresh_cursor,
            file_check=file_check,
            removed_files=removed_files,
            direction=self.direction,
        )

        if len(removed_files) > 0:
            if self.mode == Mode.BROWSE:
                self.notification_ctrl.set_label_state()
            else:
                self.file_ops_ctrl.handle_remove_files_from_groups(removed_files)
            if self.compare_manager.has_compare():
                self.compare_manager.compare().remove_from_groups(removed_files)

        if self.file_browser.has_files():
            if self.mode != Mode.BROWSE:
                return
            has_new_images = False
            if show_new_images:
                has_new_images = self.file_browser.update_cursor_to_new_images()
                if has_new_images:
                    self.media_navigator.show_next_media()
            if active_media_in_removed:
                self.media_navigator.last_chosen_direction_func()
            self.notification_ctrl.set_label_state()
            if show_new_images and has_new_images:
                # Brief delete-lock to prevent misdeletion after automatic image change
                self.delete_lock = True
                time.sleep(1)
                self.delete_lock = False
        else:
            self.media_navigator.clear_image()
            self.notification_ctrl.set_label_state()
            self.notification_ctrl.alert(
                _("Warning"), _("No files found in directory after refresh."), kind="warning"
            )

        if config.debug:
            logger.debug("Refreshed files")

    def refocus(self, event=None) -> None:
        """Return keyboard focus to the main window."""
        self.activateWindow()
        self.media_frame.setFocus()

    # ------------------------------------------------------------------
    # View toggles (kept on AppWindow -- they touch the top-level layout)
    # ------------------------------------------------------------------
    def toggle_fullscreen(self, event=None) -> None:
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self.sidebar_panel.setVisible(False)
            self.set_title_bar_visible(False)
            self.showFullScreen()
        else:
            self.sidebar_panel.setVisible(True)
            self.set_title_bar_visible(True)
            self.showNormal()

    def end_fullscreen(self, event=None) -> bool:
        if self.fullscreen:
            self.toggle_fullscreen()
        return True

    def toggle_sidebar(self, event=None) -> None:
        self.sidebar_panel.setVisible(not self.sidebar_panel.isVisible())

    def toggle_theme(self, to_theme: Optional[str] = None, do_toast: bool = True) -> None:
        """Switch between dark and light themes."""
        AppStyle.toggle_theme(to_theme)
        self._apply_theme()
        if do_toast:
            self.notification_ctrl.toast(
                _("Theme switched to {0}.").format(AppStyle.get_theme_name())
            )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    _closing = False  # guard against recursive closeEvent

    def on_closing(self) -> None:
        """
        Clean up and close this window.

        Mirrors App.on_closing: secondary windows clean up their own
        resources; the primary window stores all caches, then destroys
        the application (Qt equivalent of ``self.master.destroy()``).
        """
        # Stop periodic timers
        self.file_ops_ctrl.stop_file_check_timer()
        self.cache_ctrl.stop_periodic_store()

        self.cache_ctrl.store_info_cache(store_window_state=not self.is_secondary())

        if self.is_secondary():
            try:
                if self.compare_manager.has_compare():
                    self.compare_manager.cancel()
            except Exception as e:
                logger.error(f"Error signalling compare cancellation: {e}")

            MarkedFiles.remove_marks_for_base_dir(self.base_dir, self.app_actions)
            WindowManager.unregister(self)
            self.file_check_config.end_filecheck()
            self.slideshow_config.end_slideshows()
        else:
            # Primary window: clean up global resources and store all caches
            from utils.notification_manager import notification_manager
            notification_manager.cleanup_threads()
            self.store_cache_config.end_store_cache()
            for win in list(WindowManager.get_open_windows()):
                if win is not self:
                    win.cache_ctrl.store_info_cache()

    def closeEvent(self, event):
        """Qt close event handler."""
        if self._closing:
            event.accept()
            return
        self._closing = True
        self.on_closing()
        event.accept()

    def quit(self, event=None) -> None:
        """
        Prompt the user and quit the entire application.

        Mirrors App.quit: finds the primary window, calls on_closing
        on it (which stores all caches), then terminates the app.
        In Tkinter this was ``self.master.destroy()``; in Qt the
        equivalent is ``QApplication.quit()``.
        """
        from PySide6.QtWidgets import QApplication
        from lib.qt_alert import qt_alert

        if qt_alert(self, _("Confirm Quit"), _("Would you like to quit the application?"), kind="askokcancel"):
            logger.warning("Exiting application")
            primary = WindowManager.get_primary()
            if primary:
                primary.on_closing()
            # Equivalent of self.master.destroy() — kills all windows and
            # exits the event loop, matching the original Tkinter behaviour.
            QApplication.instance().quit()

