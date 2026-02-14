"""
PySide6 port of image/temp_image_canvas.py -- TempImageWindow.

Lightweight image viewer window used to display temporary/generated images
(rotated, cropped, enhanced, related, etc.).  Replaces the Tkinter
``TempImageCanvas`` + ``ResizingCanvas``.

Extracted from ui/image/image_details_qt.py for clarity.
"""

from __future__ import annotations

import os
import sys
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import QLabel, QMenu, QSizePolicy, QVBoxLayout, QWidget

from image.frame_cache import FrameCache
from lib.multi_display_qt import SmartDialog
from ui.app_style import AppStyle
from ui.files.marked_file_mover_qt import MarkedFiles
from utils.config import config
from utils.translations import I18N
from utils.utils import Utils

_ = I18N._


class TempImageWindow(SmartDialog):
    """Lightweight image viewer window.  Qt replacement for TempImageCanvas."""

    _instance: Optional[TempImageWindow] = None
    _current_pixmap: Optional[QPixmap] = None

    def __init__(
        self,
        parent: QWidget,
        title: str,
        dimensions: str,
        app_actions,
    ) -> None:
        # Position at top of screen, offset slightly from parent
        parent_x = parent.pos().x() if parent is not None else 0
        geo = f"{dimensions}+{parent_x + 50}+0"
        super().__init__(
            parent=parent,
            position_parent=parent,
            title=title,
            geometry=geo,
            auto_position=False,
            respect_title_bar=True,
        )
        TempImageWindow._instance = self
        self._app_actions = app_actions
        self._image_path: Optional[str] = None

        # Debounce timer for smooth scaling after resize settles
        self._smooth_timer = QTimer(self)
        self._smooth_timer.setSingleShot(True)
        self._smooth_timer.setInterval(120)
        self._smooth_timer.timeout.connect(self._apply_smooth_scale)

        # -- layout --
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setStyleSheet(f"background: {AppStyle.BG_COLOR};")
        self._image_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        layout.addWidget(self._image_label)
        self.setLayout(layout)

        self._bind_shortcuts()

    # -- shortcuts -------------------------------------------------
    def _bind_shortcuts(self) -> None:
        def sc(key: str, fn) -> None:
            s = QShortcut(QKeySequence(key), self)
            s.activated.connect(fn)

        sc("Escape", lambda: self._app_actions.refocus())
        sc("Shift+Escape", self.close)
        sc(
            "Shift+D",
            lambda: self._app_actions.get_media_details(
                media_path=self._image_path
            ),
        )
        sc(
            "Shift+I",
            lambda: self._app_actions.run_image_generation(
                _type=None, image_path=self._image_path
            ),
        )
        sc(
            "Shift+Y",
            lambda: self._app_actions.set_marks_from_downstream_related_images(
                image_to_use=self._image_path
            ),
        )
        sc("Ctrl+M", lambda: self._open_move_marks_window())
        sc("Ctrl+K", lambda: self._open_move_marks_window(open_gui=False))
        sc("Ctrl+R", self._run_previous_marks_action)
        sc("Ctrl+E", self._run_penultimate_marks_action)
        sc("Shift+C", self._copy_file_to_base_dir)
        sc("Ctrl+C", self._copy_image_path)
        sc("Ctrl+T", self._run_permanent_marks_action)
        sc("Ctrl+W", self._new_full_window_with_image)

    # -- image display ---------------------------------------------
    def create_image(
        self, media_path: str, extra_text: str | None = None
    ) -> None:
        self._image_path = FrameCache.get_image_path(media_path)
        TempImageWindow._current_pixmap = QPixmap(self._image_path)
        self._update_scaled_image()
        title = (
            media_path
            if extra_text is None
            else f"{media_path} - {extra_text}"
        )
        self.setWindowTitle(title)
        self.show()
        self.raise_()
        self.activateWindow()

    def clear_image(self) -> None:
        self._image_label.clear()
        self._image_path = None
        TempImageWindow._current_pixmap = None
        self.setWindowTitle(
            _("Open a new related image with Shift+R on main window")
        )

    def _update_scaled_image(self, smooth: bool = True) -> None:
        pm = TempImageWindow._current_pixmap
        if pm and not pm.isNull():
            mode = (
                Qt.TransformationMode.SmoothTransformation
                if smooth
                else Qt.TransformationMode.FastTransformation
            )
            scaled = pm.scaled(
                self._image_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                mode,
            )
            self._image_label.setPixmap(scaled)

    def _apply_smooth_scale(self) -> None:
        """Called after resize events settle to apply high-quality scaling."""
        self._update_scaled_image(smooth=True)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        # Fast scale for immediate feedback during resize
        self._update_scaled_image(smooth=False)
        # Schedule a smooth re-scale once resizing stops
        self._smooth_timer.start()

    # -- guards ----------------------------------------------------
    def _require_image(self) -> bool:
        return (
            self._image_path is not None
            and os.path.isfile(self._image_path)
        )

    # -- mark actions ----------------------------------------------
    def _open_move_marks_window(self, open_gui: bool = True) -> None:
        if not self._require_image():
            return
        self._app_actions.open_move_marks_window(
            open_gui=open_gui, override_marks=[self._image_path]
        )
        self.clear_image()

    def _run_previous_marks_action(self) -> None:
        if not self._require_image():
            return
        MarkedFiles.file_marks.append(self._image_path)
        _, exceptions_present = MarkedFiles.run_previous_action(
            self._app_actions
        )
        if not exceptions_present:
            self.clear_image()

    def _run_penultimate_marks_action(self) -> None:
        if not self._require_image():
            return
        MarkedFiles.file_marks.append(self._image_path)
        _, exceptions_present = MarkedFiles.run_penultimate_action(
            self._app_actions
        )
        if not exceptions_present:
            self.clear_image()

    def _run_permanent_marks_action(self) -> None:
        if not self._require_image():
            return
        MarkedFiles.file_marks.append(self._image_path)
        _, exceptions_present = MarkedFiles.run_permanent_action(
            self._app_actions
        )
        if not exceptions_present:
            self.clear_image()

    # -- clipboard / file actions ----------------------------------
    def _copy_image_path(self) -> None:
        if not self._require_image():
            return
        filepath = str(self._image_path)
        if sys.platform == "win32":
            filepath = os.path.normpath(filepath)
            if config.escape_backslash_filepaths:
                filepath = filepath.replace("\\", "\\\\")
        QGuiApplication.clipboard().setText(filepath)
        self._app_actions.toast(_("Copied filepath to clipboard"))

    def _copy_file_to_base_dir(self) -> None:
        if not self._require_image():
            return
        base_dir = self._app_actions.get_base_dir()
        current_image_dir = os.path.dirname(self._image_path)
        if (
            base_dir
            and base_dir != ""
            and os.path.normpath(base_dir)
            != os.path.normpath(current_image_dir)
        ):
            new_file = os.path.join(
                base_dir, os.path.basename(self._image_path)
            )
            Utils.copy_file(
                self._image_path,
                new_file,
                overwrite_existing=config.move_marks_overwrite_existing_file,
            )

    def _new_full_window_with_image(self) -> None:
        if not self._require_image():
            return
        base_dir = os.path.dirname(self._image_path)
        self._app_actions.new_window(
            base_dir=base_dir, image_path=self._image_path
        )
        self.close()

    # -- right-click context menu ------------------------------------
    def contextMenuEvent(self, event) -> None:  # noqa: N802
        if not self._image_path:
            return
        menu = QMenu(self)
        menu.addAction(
            _("Open in Full Window"),
            self._new_full_window_with_image,
        )
        menu.addAction(
            _("Run Image Generation"),
            lambda: self._app_actions.run_image_generation(
                _type=None, image_path=self._image_path
            ),
        )
        menu.addSeparator()
        menu.addAction(
            _("Copy File Path"),
            self._copy_image_path,
        )
        menu.exec(event.globalPos())
