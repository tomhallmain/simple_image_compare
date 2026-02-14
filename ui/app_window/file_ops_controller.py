"""
FileOpsController -- delete, hide, copy, and file-manipulation operations.

Extracted from: delete_image, _handle_delete, delete_current_base_dir,
hide_current_media, clear_hidden_images, replace_current_image_with_search_image,
_handle_remove_files_from_groups, open_media_location, open_image_in_gimp,
copy_media_path, copy_media_basename, run_refacdir, check_files (periodic).

Also owns the periodic file-check timer, which monitors the file system
for changes and refreshes the file list when needed.
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from ui.auth.password_utils import require_password
from utils.config import config
from utils.constants import ActionType, Mode, ProtectedActions
from utils.logging_setup import get_logger
from utils.translations import I18N
from utils.utils import Utils

if TYPE_CHECKING:
    from compare.compare_manager import CompareManager
    from files.file_browser import FileBrowser
    from ui.app_window.app_window import AppWindow
    from ui.app_window.media_navigator import MediaNavigator

_ = I18N._
logger = get_logger("file_ops_controller")


class FileOpsController:
    """
    Owns delete, hide, copy, and file-manipulation operations
    on the currently viewed media. Also owns the periodic file-check timer.
    """

    def __init__(
        self,
        app_window: AppWindow,
        file_browser: FileBrowser,
        compare_manager: CompareManager,
        media_navigator: MediaNavigator,
    ):
        self._app = app_window
        self._fb = file_browser
        self._cm = compare_manager
        self._nav = media_navigator

        # Periodic file-check timer
        self._file_check_timer: Optional[QTimer] = None

    # ==================================================================
    # Periodic file check
    # ==================================================================
    def start_file_check_timer(self) -> None:
        """
        Start a periodic timer that refreshes the file list if files changed.

        Replaces the async ``check_files`` coroutine + ``@periodic`` decorator
        from the original App class.
        """
        interval_ms = int(self._app.file_check_config.interval_seconds * 1000)
        if interval_ms <= 0:
            return

        self._file_check_timer = QTimer()
        self._file_check_timer.timeout.connect(self._on_file_check)
        self._file_check_timer.start(interval_ms)

    def stop_file_check_timer(self) -> None:
        if self._file_check_timer is not None:
            self._file_check_timer.stop()
            self._file_check_timer = None

    def _on_file_check(self) -> None:
        """
        Called on the main thread by QTimer.

        Ported from App.check_files + App._check_files_main_thread.
        """
        try:
            if not self._fb.checking_files:
                return
            if self._app.mode != Mode.BROWSE:
                return
            base_dir = self._app.get_base_dir()
            if base_dir and base_dir != "":
                self._app.refresh(
                    show_new_images=self._app.slideshow_config.show_new_images,
                )
        except Exception as e:
            logger.debug(f"Error in file check: {e}")

    # ==================================================================
    # Delete operations
    # ==================================================================
    @require_password(ProtectedActions.DELETE_MEDIA)
    def delete_image(self, event=None) -> None:
        """
        Delete the currently displayed image from the filesystem.

        Ported from App.delete_image.
        """
        from files.marked_files import MarkedFiles

        if self._app.delete_lock:
            self._app.app_actions.warn(_("DELETE_LOCK"))
            return

        if self._app.mode == Mode.BROWSE:
            self._fb.checking_files = False
            filepath = self._fb.current_file()
            if filepath:
                self._app.media_frame.release_media()
                self._handle_delete(filepath)
                MarkedFiles.handle_file_removal(filepath)
                self._fb.refresh(
                    refresh_cursor=False,
                    removed_files=[filepath],
                    direction=self._app.direction,
                    file_check=True,
                )
                self._nav.last_chosen_direction_func()
            self._fb.checking_files = True
            return

        is_toggle_search_image = self._nav.is_toggled_search_image()

        if len(self._cm.files_matched) == 0 and not is_toggle_search_image:
            self._app.app_actions.warn(_("Invalid action, no files found to delete"))
            return
        elif is_toggle_search_image and (
            self._cm.search_image_full_path is None
            or self._cm.search_image_full_path == ""
        ):
            self._app.app_actions.warn(_("Invalid action, search image not found"))
            return

        filepath = self._nav.get_active_media_filepath()

        if filepath is not None:
            MarkedFiles.handle_file_removal(filepath)
            if filepath == self._cm.search_image_full_path:
                self._cm.search_image_full_path = None
            self._app.media_frame.release_media()
            self._handle_delete(filepath)
            if self._cm.has_compare():
                self._cm.compare().remove_from_groups([filepath])
            self._cm._update_groups_for_removed_file(
                self._app.mode,
                self._cm.current_group_index,
                self._cm.match_index,
                show_next_media=self._app.direction,
            )
        else:
            self._app.notification_ctrl.handle_error(
                _("Failed to delete current file, unable to get valid filepath")
            )

    def _handle_delete(
        self,
        filepath: str,
        toast: bool = True,
        manual_delete: bool = True,
        is_directory: bool = False,
    ) -> None:
        """
        Execute a delete operation on the given file or directory.

        Ported from App._handle_delete.
        """
        from files.marked_files import MarkedFiles

        MarkedFiles.set_delete_lock()  # Undo deleting action is not supported

        if toast and manual_delete:
            item_name = os.path.basename(filepath)
            if is_directory:
                self._app.notification_ctrl.title_notify(
                    _("Removing directory: {0}").format(item_name),
                    action_type=ActionType.REMOVE_FILE,
                )
            else:
                self._app.notification_ctrl.title_notify(
                    _("Removing file: {0}").format(item_name),
                    action_type=ActionType.REMOVE_FILE,
                )
        else:
            logger.info(f"Removing {'directory' if is_directory else 'file'}: {filepath}")

        try:
            Utils.remove_path(
                filepath,
                delete_instantly=config.delete_instantly,
                trash_folder=config.trash_folder,
                is_directory=is_directory,
            )
        except Exception as e:
            logger.error(e)
            alert = self._app.notification_ctrl.alert
            if config.delete_instantly:
                alert(_("Warning"), _("Failed to delete item: {0}").format(str(e)))
            elif config.trash_folder is not None:
                if is_directory:
                    msg = _("Failed to move directory to {0}. Double check the trash folder is set properly in config.json.").format(config.trash_folder)
                else:
                    msg = _("Failed to send file to {0}. Double check the trash folder is set properly in config.json.").format(config.trash_folder)
                alert(_("Warning"), msg)
            else:
                if is_directory:
                    alert(
                        _("Warning"),
                        _("Failed to move directory to the trash. Either pip install send2trash "
                          "or set a specific trash folder in config.json."),
                    )
                    return
                else:
                    alert(
                        _("Warning"),
                        _("Failed to send file to the trash, so it will be deleted. Either pip install "
                          "send2trash or set a specific trash folder in config.json."),
                    )
                try:
                    Utils.remove_path(filepath, delete_instantly=True, trash_folder=None, is_directory=is_directory)
                except Exception as e2:
                    logger.error(e2)
                    alert(_("Warning"), _("Failed to delete item: {0}").format(filepath))

    # Expose as the AppActions-compatible name
    handle_delete = _handle_delete

    def delete_current_base_dir(self, event=None) -> None:
        """
        Delete or trash the entire current base directory.

        Ported from App.delete_current_base_dir.
        """
        from files.marked_files import MarkedFiles
        from files.recent_directories import RecentDirectories
        from utils.app_info_cache import app_info_cache
        from ui.app_window.window_manager import WindowManager

        base_dir = self._app.get_base_dir()
        if not base_dir or base_dir == "." or base_dir.strip() == "" or not os.path.isdir(base_dir):
            self._app.notification_ctrl.alert(
                _("Invalid directory"), _("No valid base directory to delete"), kind="warning"
            )
            return

        open_window_dirs = [
            w.get_base_dir()
            for w in WindowManager.get_open_windows()
            if w.window_id != self._app.window_id and w.get_base_dir()
        ]

        try:
            replacement_dir = RecentDirectories.find_replacement_directory(base_dir, open_window_dirs)
        except ValueError as e:
            self._app.notification_ctrl.alert(_("Cannot Delete Directory"), str(e), kind="warning")
            return

        file_summary = self._fb.get_file_type_summary_for_directory(recursive=True)
        alert_message = (
            _("Are you sure you want to delete the directory and all contents?")
            + "\n\n" + str(base_dir) + "\n\n"
            + _("Contents to be deleted:") + "\n" + file_summary
        )

        ok = self._app.notification_ctrl.alert(
            _("Confirm Delete Directory"), alert_message, kind="askokcancel",
        )
        if not ok:
            return

        logger.info(f"Setting base directory to {replacement_dir} before deleting {base_dir}")
        self._app.sidebar_panel.update_base_dir_display(replacement_dir)
        self._app.set_base_dir(replacement_dir)

        # Close other windows using this base directory
        for win in WindowManager.get_open_windows()[:]:
            if win.window_id != self._app.window_id and win.base_dir == base_dir:
                try:
                    win.on_closing()
                except Exception as e:
                    logger.error(f"Error closing window for deleted directory: {e}")

        MarkedFiles.remove_marks_for_base_dir(base_dir, self._app.app_actions)

        try:
            RecentDirectories.remove_directory(base_dir)
            app_info_cache.clear_directory_cache(base_dir)
            app_info_cache.store()
            self._handle_delete(base_dir, toast=True, manual_delete=True, is_directory=True)
        except Exception as e:
            self._app.notification_ctrl.handle_error(str(e), title=_("Delete Directory Error"))

        self._app.notification_ctrl.toast(
            _("Directory {0} deleted.").format(base_dir), time_in_seconds=10
        )

    # ==================================================================
    # Hide operations
    # ==================================================================
    def hide_current_media(self, event=None, image_path: Optional[str] = None) -> None:
        """
        Hide the current media from the file list.

        Ported from App.hide_current_media.
        """
        filepath = self._nav.get_active_media_filepath() if image_path is None else image_path
        if filepath not in self._cm.hidden_images:
            self._cm.hidden_images.append(filepath)
        if image_path is None:
            self._app.notification_ctrl.toast(_("Hid current image.\nTo unhide, press Shift+B."))
        self._nav.show_next_media()

    def clear_hidden_images(self, event=None) -> None:
        """Clear the list of hidden images."""
        self._cm.hidden_images.clear()
        self._app.notification_ctrl.toast(_("Cleared all hidden images."))

    # ==================================================================
    # Copy operations
    # ==================================================================
    def copy_media_path(self, filepath: Optional[str] = None) -> None:
        """
        Copy the file path to the clipboard.

        Ported from App.copy_media_path.
        """
        if filepath is None:
            filepath = self._nav.get_active_media_filepath()
        if filepath is None:
            return
        if sys.platform == "win32":
            filepath = os.path.normpath(filepath)
            if config.escape_backslash_filepaths:
                filepath = filepath.replace("\\", "\\\\")
        clipboard = QApplication.clipboard()
        clipboard.setText(filepath)
        self._app.notification_ctrl.toast(_("Copied filepath to clipboard"))

    def copy_media_basename(self, filepath: Optional[str] = None) -> None:
        """
        Copy the file basename to the clipboard.

        Ported from App.copy_media_basename.
        """
        if filepath is None:
            filepath = self._nav.get_active_media_filepath()
        if filepath is None:
            return
        basename = os.path.basename(filepath)
        clipboard = QApplication.clipboard()
        clipboard.setText(basename)
        self._app.notification_ctrl.toast(_("Copied filename to clipboard"))

    # ==================================================================
    # Replace / group operations
    # ==================================================================
    def replace_current_image_with_search_image(self) -> None:
        """
        Overwrite the current image file with the search image.

        Ported from App.replace_current_image_with_search_image.
        """
        if (
            self._app.mode != Mode.SEARCH
            or len(self._cm.files_matched) == 0
            or not os.path.exists(str(self._cm.search_image_full_path))
        ):
            return

        _filepath = self._cm.current_match()
        filepath = Utils.get_valid_file(self._app.get_base_dir(), _filepath)

        if filepath is None:
            self._app.notification_ctrl.handle_error(
                _("Invalid target filepath for replacement: ") + _filepath
            )
            return

        os.rename(str(self._cm.search_image_full_path), filepath)
        self._app.notification_ctrl.toast(_("Moved search image to ") + filepath)

    def handle_remove_files_from_groups(self, files: list[str]) -> None:
        """
        Remove the given files from compare groups.

        Ported from App._handle_remove_files_from_groups.
        """
        current_image = self._cm.current_match()
        for filepath in files:
            if filepath == self._cm.search_image_full_path:
                self._cm.search_image_full_path = None
            show_next_media = self._app.direction if current_image == filepath else None
            file_group_map = self._cm._get_file_group_map(self._app.mode)
            try:
                group_indexes = file_group_map[filepath]
                self._cm._update_groups_for_removed_file(
                    self._app.mode,
                    group_indexes[0],
                    group_indexes[1],
                    set_group=False,
                    show_next_media=show_next_media,
                )
            except KeyError:
                pass

    # ==================================================================
    # External file operations
    # ==================================================================
    def open_media_location(self, event=None) -> None:
        """
        Open the file's directory in the system file manager.

        Ported from App.open_media_location.
        """
        filepath = self._nav.get_active_media_filepath()
        if filepath is not None:
            is_video = self._app.media_frame.pause_video_if_playing() if hasattr(self._app.media_frame, "pause_video_if_playing") else False
            self._app.notification_ctrl.toast(_("Opening media file: {0}").format(filepath))
            Utils.open_media_file(filepath, is_video=is_video)
        else:
            self._app.notification_ctrl.handle_error(
                _("Failed to open current media file, unable to get valid filepath")
            )

    def open_image_in_gimp(self, event=None) -> None:
        """
        Open the current image in GIMP.

        Ported from App.open_image_in_gimp.
        """
        config.validate_and_find_gimp()
        if not config.gimp_exe_loc:
            self._app.notification_ctrl.handle_error(
                _("GIMP integration is not configured. Please set 'gimp_exe_loc' in config.json."),
                title=_("GIMP Integration Error"),
            )
            return

        if self._app.delete_lock:
            filepath = self._app.prev_img_path
        else:
            filepath = self._nav.get_active_media_filepath()

        if filepath is not None:
            from extensions.gimp.gimp_wrapper import open_image_in_gimp_wrapper
            from files.marked_files import MarkedFiles
            open_image_in_gimp_wrapper(
                filepath,
                config.gimp_exe_loc,
                self._fb.is_slow_total_files,
                self._app.app_actions,
            )
            MarkedFiles.gimp_opened_in_last_action = True
        else:
            self._app.notification_ctrl.handle_error(
                _("Failed to open current file in GIMP, unable to get valid filepath")
            )

    def run_refacdir(self, event=None) -> None:
        """
        Run the RefacDir client on the current image.

        Ported from App.run_refacdir.
        """
        from extensions.refacdir_client import RefacDirClient

        refacdir_client = RefacDirClient()
        refacdir_client.run(self._app.img_path)
        self._app.notification_ctrl.toast(_("Running refacdir"))
