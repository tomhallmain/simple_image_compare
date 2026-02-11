"""
WindowLauncher -- opens secondary windows and dialogs.

A thin class where each method creates the appropriate dialog/window.
Extracted from: all open_*_window methods, get_media_details,
get_help_and_config.

Note: many of these still create the *tkinter* versions of windows.
They will be updated incrementally as each window is ported to PySide6.
Until then they use the original tkinter window classes, which is
acceptable because the backend logic does not depend on the host
framework -- only the UI wrapper does.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Optional

from ui.auth.password_utils import require_password, check_session_expired
from utils.constants import Mode, ProtectedActions
from utils.logging_setup import get_logger
from utils.translations import I18N

if TYPE_CHECKING:
    from ui.app_window.app_window import AppWindow

_ = I18N._
logger = get_logger("window_launcher")


class WindowLauncher:
    """
    Opens every secondary window / dialog. Keeps the "which windows exist"
    knowledge in one place and makes window implementations easy to swap.
    """

    def __init__(self, app_window: AppWindow):
        self._app = app_window
        self._go_to_file_window = None
        self._directory_notes_window = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _handle_error(self, error: Exception, title: str = "Window Error") -> None:
        self._app.notification_ctrl.handle_error(str(error), title=title)

    # ------------------------------------------------------------------
    # Navigation windows
    # ------------------------------------------------------------------
    def open_go_to_file_window(self, event=None) -> None:
        """Open the go-to-file search window."""
        try:
            if self._go_to_file_window is not None:
                try:
                    if self._go_to_file_window.isVisible():
                        self._go_to_file_window.raise_()
                        self._go_to_file_window.activateWindow()
                        return
                except (RuntimeError, AttributeError):
                    self._go_to_file_window = None

            from files.go_to_file import GoToFile
            self._go_to_file_window = GoToFile(self._app, self._app.app_actions)
        except Exception as e:
            self._handle_error(e, "Go To File Window Error")

    def open_go_to_file_with_current_media(self, event=None) -> None:
        """Open go-to-file pre-populated with the current media name."""
        try:
            if self._go_to_file_window is not None:
                try:
                    if self._go_to_file_window.isVisible():
                        self._go_to_file_window.update_with_current_media()
                        return
                except (RuntimeError, AttributeError):
                    self._go_to_file_window = None

            from files.go_to_file import GoToFile
            self._go_to_file_window = GoToFile(self._app, self._app.app_actions)
            self._go_to_file_window.update_with_current_media(focus=True)
        except Exception as e:
            self._handle_error(e, "Go To File Window Error")

    # ------------------------------------------------------------------
    # Directory windows
    # ------------------------------------------------------------------
    def open_recent_directory_window(
        self,
        event=None,
        open_gui: bool = True,
        run_compare_image: Optional[str] = None,
        extra_callback_args: Optional[list[Any]] = None,
    ) -> None:
        """Open the recent directories window."""
        try:
            from files.recent_directory_window import RecentDirectoryWindow
            from lib.multi_display_qt import SmartWindow

            geometry = RecentDirectoryWindow.get_geometry(is_gui=open_gui)
            window = SmartWindow(
                persistent_parent=self._app,
                title=_("Set Image Comparison Directory"),
                geometry=geometry,
            )
            if not open_gui:
                window.setWindowOpacity(0.3)

            RecentDirectoryWindow(
                window,
                self._app,
                open_gui,
                self._app.app_actions,
                base_dir=self._app.get_base_dir(),
                run_compare_image=run_compare_image,
                extra_callback_args=extra_callback_args,
            )
            window.show()
        except Exception as e:
            self._handle_error(e, "Recent Directory Window Error")

    def open_favorites_window(self, event=None) -> None:
        """Open the favorites directory window."""
        try:
            from files.favorites_window import FavoritesWindow
            FavoritesWindow(self._app, self._app.app_actions)
        except Exception as e:
            self._handle_error(e, "Favorites Window Error")

    def open_directory_notes_window(self, event=None) -> None:
        """Open the directory notes window for the current base directory."""
        try:
            base_dir = self._app.get_base_dir()
            if not base_dir:
                self._app.notification_ctrl.toast(_("Please set a base directory first"))
                return

            # Re-use existing window if still open
            if self._directory_notes_window is not None:
                try:
                    if self._directory_notes_window.isVisible():
                        self._directory_notes_window.raise_()
                        self._directory_notes_window.activateWindow()
                        return
                except (RuntimeError, AttributeError):
                    self._directory_notes_window = None

            from files.directory_notes_window import DirectoryNotesWindow
            self._directory_notes_window = DirectoryNotesWindow(
                self._app, self._app.app_actions, base_dir
            )
        except Exception as e:
            self._handle_error(e, "Directory Notes Window Error")

    # ------------------------------------------------------------------
    # Settings / configuration windows
    # ------------------------------------------------------------------
    def open_compare_settings_window(self, event=None) -> None:
        """Open the compare settings window."""
        try:
            from compare.compare_settings_window import CompareSettingsWindow
            CompareSettingsWindow.show(parent=self._app, compare_manager=self._app.compare_manager)
        except Exception as e:
            self._handle_error(e, "Compare Settings Window Error")

    @require_password(ProtectedActions.CONFIGURE_MEDIA_TYPES)
    def open_type_configuration_window(self, event=None) -> None:
        """Open the file type configuration window."""
        from files.type_configuration_window import TypeConfigurationWindow
        TypeConfigurationWindow.show(master=self._app, app_actions=self._app.app_actions)

    @require_password(ProtectedActions.EDIT_PREVALIDATIONS)
    def open_prevalidations_window(self, event=None) -> None:
        """Open the prevalidations window (goes to the prevalidations tab)."""
        from utils.config import config as _config
        if not _config.enable_prevalidations:
            return
        try:
            from compare.classifier_management_window import ClassifierManagementWindow
            mgmt = ClassifierManagementWindow(self._app, self._app.app_actions)
            # Select prevalidations tab (index 1)
            if hasattr(mgmt, "notebook"):
                mgmt.notebook.setCurrentIndex(1)
        except Exception as e:
            self._handle_error(e, "Prevalidations Window Error")

    @require_password(ProtectedActions.EDIT_PREVALIDATIONS, ProtectedActions.RUN_PREVALIDATIONS)
    def open_classifier_actions_window(self, event=None) -> None:
        """Open the classifier management window (classifier actions tab)."""
        try:
            from compare.classifier_management_window import ClassifierManagementWindow
            mgmt = ClassifierManagementWindow(self._app, self._app.app_actions)
            if hasattr(mgmt, "notebook"):
                mgmt.notebook.setCurrentIndex(0)
        except Exception as e:
            self._handle_error(e, "Classifier Actions Window Error")

    # ------------------------------------------------------------------
    # File operations windows
    # ------------------------------------------------------------------
    def open_file_actions_window(self, event=None) -> None:
        """Open the file actions window."""
        try:
            from ui.files.file_actions_window_qt import FileActionsWindow
            from image.image_details import ImageDetails
            from ui.files.marked_file_mover_qt import MarkedFiles
            window = FileActionsWindow(
                self._app,
                self._app.app_actions,
                ImageDetails.open_temp_image_canvas,
                MarkedFiles.move_marks_to_dir_static,
            )
            window.show()
        except Exception as e:
            self._handle_error(e, "File Actions Window Error")

    # ------------------------------------------------------------------
    # Auth / admin windows
    # ------------------------------------------------------------------
    @require_password(ProtectedActions.ACCESS_ADMIN)
    def open_password_admin_window(self, event=None) -> None:
        """Open the password administration window."""
        try:
            from ui.auth.password_admin_window import PasswordAdminWindow
            PasswordAdminWindow(self._app, self._app.app_actions)
        except Exception as e:
            self._handle_error(e, "Password Admin Window Error")

    # ------------------------------------------------------------------
    # Info windows
    # ------------------------------------------------------------------
    def open_media_details(
        self,
        event=None,
        media_path: Optional[str] = None,
        manually_keyed: bool = True,
    ) -> None:
        """
        Open the media details / metadata inspector window.

        Ported from App.get_media_details. Manages the singleton
        ImageDetails window reference stored on AppActions.
        """
        from image.image_details import ImageDetails

        app_actions = self._app.app_actions

        # Close existing window if the session expired
        if app_actions.image_details_window() is not None:
            if check_session_expired(ProtectedActions.VIEW_MEDIA_DETAILS):
                app_actions.image_details_window().close_windows()
                app_actions.set_image_details_window(None)

        preset_image_path = True
        if media_path is None:
            media_path = self._app.img_path
            preset_image_path = False

        if not media_path:
            return

        # Build index text
        if preset_image_path:
            index_text = _("(Open this image as part of a directory to see index details.)")
        elif self._app.mode == Mode.BROWSE:
            index_text = self._app.file_browser.get_index_details()
        else:
            cm = self._app.compare_manager
            _index = cm.match_index + 1
            len_matched = len(cm.files_matched)
            if self._app.mode == Mode.GROUP:
                len_groups = len(cm.file_groups)
                group_idx = cm.current_group_index + 1
                index_text = f"{_index} of {len_matched} (Group {group_idx} of {len_groups})"
            elif self._app.mode == Mode.SEARCH and self._app.is_toggled_view_matches:
                index_text = f"{_index} of {len_matched} ({self._app.file_browser.get_index_details()})"
            else:
                index_text = ""

        existing = app_actions.image_details_window()
        if existing is not None and not existing.has_closed:
            if existing.do_refresh:
                existing.update_image_details(media_path, index_text)
            if manually_keyed:
                existing.focus()
        else:
            try:
                details_win = ImageDetails(
                    self._app, media_path, index_text,
                    app_actions, do_refresh=not preset_image_path,
                )
                app_actions.set_image_details_window(details_win)
            except Exception as e:
                self._handle_error(e, "Image Details Error")

    @require_password(ProtectedActions.VIEW_MEDIA_DETAILS)
    def copy_prompt(self, event=None) -> None:
        """Copy the AI prompt from the currently viewed image."""
        from image.image_details import ImageDetails
        ImageDetails.copy_prompt_no_break_static(
            self._app.media_navigator.get_active_media_filepath(),
            self._app,
            self._app.app_actions,
        )

    @require_password(ProtectedActions.VIEW_MEDIA_DETAILS)
    def show_related_image(self, event=None) -> None:
        """Show a related image to the current one."""
        from image.image_details import ImageDetails
        ImageDetails.show_related_image(
            master=self._app,
            image_path=self._app.img_path,
            app_actions=self._app.app_actions,
        )

    def get_help_and_config(self, event=None) -> None:
        """Open the help and configuration window."""
        try:
            from ui.help_and_config_qt import HelpAndConfig
            dialog = HelpAndConfig(parent=self._app, position_parent=self._app)
            dialog.show()
        except Exception as e:
            self._app.notification_ctrl.alert(
                "Help & Config Error", str(e), kind="error"
            )

    # ------------------------------------------------------------------
    # Secondary compare window
    # ------------------------------------------------------------------
    def open_secondary_compare_window(
        self, event=None, run_compare_image: Optional[str] = None
    ) -> None:
        """Open a new secondary window and optionally start a compare."""
        if run_compare_image is None:
            self.open_recent_directory_window(run_compare_image="")
        elif not os.path.isfile(run_compare_image):
            self._app.notification_ctrl.alert(
                _("No image selected"),
                _("No image was selected for comparison"),
            )
        else:
            self.open_recent_directory_window(run_compare_image=self._app.img_path)

    # ------------------------------------------------------------------
    # Prevalidations (action, not window)
    # ------------------------------------------------------------------
    @require_password(ProtectedActions.RUN_PREVALIDATIONS)
    def run_prevalidations_for_base_dir(self, event=None) -> None:
        """Run all prevalidations on every file in the current directory."""
        from compare.prevalidations_tab import PrevalidationsTab
        from ui.files.marked_file_mover_qt import MarkedFiles
        from PySide6.QtWidgets import QMessageBox

        fb = self._app.file_browser
        if fb.is_slow_total_files(threshold=100, use_sortable_files=True):
            ok = self._app.notification_ctrl.alert(
                _("Many Files"),
                _("Are you sure you want to run all prevalidations on directory {0} ? "
                  "This may take a while.").format(self._app.get_base_dir()),
                kind="askokcancel",
            )
            if not ok:
                logger.info("User canceled prevalidations task")
                return

        logger.warning("Running prevalidations for " + self._app.get_base_dir())
        PrevalidationsTab.clear_prevalidated_cache()
        for image_path in fb.get_files():
            try:
                PrevalidationsTab.prevalidate(
                    image_path,
                    self._app.get_base_dir,
                    self._app.file_ops_ctrl.hide_current_media,
                    self._app.notification_ctrl.title_notify,
                    MarkedFiles.add_mark_if_not_present,
                )
            except Exception as e:
                logger.error(e)

    @require_password(ProtectedActions.RUN_PREVALIDATIONS)
    def toggle_prevalidations(self, event=None) -> None:
        """Toggle prevalidations on or off."""
        from utils.config import config as _config
        _config.enable_prevalidations = not _config.enable_prevalidations
        self._app.notification_ctrl.toast(
            _("Prevalidations now running") if _config.enable_prevalidations
            else _("Prevalidations turned off")
        )

    def toggle_extra_debug_logging(self, event=None) -> None:
        """Toggle the extra-verbose debug logging flag."""
        from utils.config import config as _config
        _config.debug2 = not _config.debug2
        self._app.notification_ctrl.toast(
            _("Extra debug logging enabled") if _config.debug2
            else _("Extra debug logging disabled")
        )

    # ------------------------------------------------------------------
    # Directory note operations
    # ------------------------------------------------------------------
    def toggle_directory_note_mark(self, event=None) -> None:
        """Toggle a file's marked status in directory notes."""
        from files.directory_notes import DirectoryNotes

        image_path = self._app.media_navigator.get_active_media_filepath()
        if not image_path:
            return

        base_dir = self._app.get_base_dir()
        if DirectoryNotes.is_marked_file(base_dir, image_path):
            DirectoryNotes.remove_marked_file(base_dir, image_path)
            self._app.notification_ctrl.toast(
                _("Removed from directory notes: {0}").format(os.path.basename(image_path))
            )
        else:
            DirectoryNotes.add_marked_file(base_dir, image_path)
            self._app.notification_ctrl.toast(
                _("Added to directory notes: {0}").format(os.path.basename(image_path))
            )

        # Refresh the notes window if it is open
        if self._directory_notes_window is not None:
            try:
                if self._directory_notes_window.isVisible():
                    self._directory_notes_window._refresh_widgets()
            except (RuntimeError, AttributeError):
                pass

    def edit_file_note(self, event=None) -> None:
        """Open a dialog to edit the note for the current file."""
        from files.directory_notes import DirectoryNotes
        from PySide6.QtWidgets import (
            QDialog, QLabel, QPlainTextEdit, QPushButton,
            QHBoxLayout, QVBoxLayout,
        )
        from ui.app_style import AppStyle

        image_path = self._app.media_navigator.get_active_media_filepath()
        if not image_path:
            return

        base_dir = self._app.get_base_dir()
        current_note = DirectoryNotes.get_file_note(base_dir, image_path) or ""

        dialog = QDialog(self._app)
        dialog.setWindowTitle(_("Edit Note - {0}").format(os.path.basename(image_path)))
        dialog.resize(600, 400)

        layout = QVBoxLayout(dialog)
        path_label = QLabel(image_path, dialog)
        path_label.setWordWrap(True)
        layout.addWidget(path_label)

        note_edit = QPlainTextEdit(dialog)
        note_edit.setPlainText(current_note)
        layout.addWidget(note_edit)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton(_("Save"), dialog)
        cancel_btn = QPushButton(_("Cancel"), dialog)
        btn_layout.addStretch()
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        def save_note():
            new_note = note_edit.toPlainText().strip()
            DirectoryNotes.set_file_note(base_dir, image_path, new_note)
            self._app.notification_ctrl.toast(
                _("Note saved for: {0}").format(os.path.basename(image_path))
            )
            dialog.accept()
            if self._directory_notes_window is not None:
                try:
                    if self._directory_notes_window.isVisible():
                        self._directory_notes_window._refresh_widgets()
                except (RuntimeError, AttributeError):
                    pass

        save_btn.clicked.connect(save_note)
        cancel_btn.clicked.connect(dialog.reject)

        dialog.exec()

