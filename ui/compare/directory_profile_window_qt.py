"""
PySide6 port of the DirectoryProfileWindow from compare/directory_profile.py.

Only the UI class is ported here. The non-UI ``DirectoryProfile`` data class
is imported from the original module per the reuse policy.

Non-UI imports:
  - DirectoryProfile from compare.directory_profile (reuse policy)
"""

from __future__ import annotations

import os
from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFileDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QPushButton, QVBoxLayout, QWidget,
)

from compare.directory_profile import DirectoryProfile
from lib.multi_display_qt import SmartDialog
from ui.app_style import AppStyle
from utils.config import config
from utils.translations import I18N
from utils.logging_setup import get_logger

_ = I18N._
logger = get_logger("directory_profile_window_qt")


class DirectoryProfileWindow(SmartDialog):
    """
    Create / edit dialog for a single DirectoryProfile.

    Fields:
      - Profile name (QLineEdit)
      - Directories list (QListWidget) with Add / Edit / Remove /
        Add subdirs / Clear all buttons
      - Done button
    """

    _instance: Optional[DirectoryProfileWindow] = None

    def __init__(
        self,
        parent: QWidget,
        app_actions,
        refresh_callback: Callable,
        profile: Optional[DirectoryProfile] = None,
        dimensions: str = "600x500",
    ) -> None:
        self._is_edit = profile is not None
        self._profile = profile if profile is not None else DirectoryProfile()
        self._original_name = self._profile.name if self._is_edit else None

        super().__init__(
            parent=parent,
            position_parent=parent,
            title=_("Edit Profile") if self._is_edit else _("Create Profile"),
            geometry=dimensions,
        )
        DirectoryProfileWindow._instance = self

        self._app_actions = app_actions
        self._refresh_callback = refresh_callback

        self._build_ui()

        QShortcut(QKeySequence(Qt.Key_Escape), self).activated.connect(self.close)
        QShortcut(QKeySequence(Qt.Key_Return), self).activated.connect(
            self._finalize_profile
        )

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # -- Profile name -------------------------------------------------
        name_row = QHBoxLayout()
        name_lbl = QLabel(_("Profile Name"))
        name_lbl.setStyleSheet(f"color: {AppStyle.FG_COLOR};")
        name_row.addWidget(name_lbl)

        self._name_edit = QLineEdit(self._profile.name)
        name_row.addWidget(self._name_edit, 1)
        root.addLayout(name_row)

        # -- Directories --------------------------------------------------
        dir_lbl = QLabel(_("Directories"))
        dir_lbl.setStyleSheet(f"color: {AppStyle.FG_COLOR};")
        root.addWidget(dir_lbl)

        dir_area = QHBoxLayout()

        self._dir_list = QListWidget()
        self._dir_list.setStyleSheet(
            f"QListWidget {{ background: {AppStyle.BG_COLOR}; "
            f"color: {AppStyle.FG_COLOR}; }}"
        )
        self._refresh_directory_list()
        dir_area.addWidget(self._dir_list, 1)

        btn_col = QVBoxLayout()
        btn_col.setSpacing(4)

        add_btn = QPushButton(_("Add"))
        add_btn.clicked.connect(self._add_directory)
        btn_col.addWidget(add_btn)

        edit_btn = QPushButton(_("Edit"))
        edit_btn.clicked.connect(self._edit_directory)
        btn_col.addWidget(edit_btn)

        remove_btn = QPushButton(_("Remove"))
        remove_btn.clicked.connect(self._remove_directory)
        btn_col.addWidget(remove_btn)

        add_subdirs_btn = QPushButton(_("Add dirs from subdirs"))
        add_subdirs_btn.clicked.connect(self._add_subdirectories)
        btn_col.addWidget(add_subdirs_btn)

        clear_btn = QPushButton(_("Clear all"))
        clear_btn.clicked.connect(self._clear_all_directories)
        btn_col.addWidget(clear_btn)

        btn_col.addStretch()
        dir_area.addLayout(btn_col)
        root.addLayout(dir_area, 1)

        # -- Done button --------------------------------------------------
        done_btn = QPushButton(_("Done"))
        done_btn.clicked.connect(self._finalize_profile)
        root.addWidget(done_btn, 0, Qt.AlignLeft)

    # ------------------------------------------------------------------
    # Directory list helpers
    # ------------------------------------------------------------------
    def _refresh_directory_list(self) -> None:
        self._dir_list.clear()
        for d in self._profile.directories:
            self._dir_list.addItem(d)

    def _browse_directory(
        self, title: str = _("Select directory"), initial_dir: Optional[str] = None
    ) -> Optional[str]:
        if initial_dir is None:
            initial_dir = (
                self._profile.directories[-1]
                if self._profile.directories
                else "."
            )
        if not os.path.isdir(initial_dir):
            initial_dir = "."

        directory = QFileDialog.getExistingDirectory(
            self, title, initial_dir
        )
        return directory if directory and directory.strip() else None

    def _add_directory(self) -> None:
        directory = self._browse_directory(_("Add Directory"))
        if directory:
            directory = directory.strip()
            if os.path.isdir(directory):
                if directory not in self._profile.directories:
                    self._profile.directories.append(directory)
                    self._refresh_directory_list()
                else:
                    logger.warning(f"Directory {directory} already in profile")
            else:
                logger.error(f"Invalid directory: {directory}")

    def _edit_directory(self) -> None:
        current = self._dir_list.currentItem()
        if current is None:
            logger.warning("No directory selected for editing")
            return
        idx = self._dir_list.currentRow()
        if idx >= len(self._profile.directories):
            return

        current_dir = self._profile.directories[idx]
        new_directory = self._browse_directory(
            _("Edit Directory"), initial_dir=current_dir
        )
        if new_directory:
            new_directory = new_directory.strip()
            if os.path.isdir(new_directory):
                if (
                    new_directory in self._profile.directories
                    and self._profile.directories.index(new_directory) != idx
                ):
                    logger.warning(
                        f"Directory {new_directory} already in profile"
                    )
                else:
                    self._profile.directories[idx] = new_directory
                    self._refresh_directory_list()
                    self._dir_list.setCurrentRow(idx)
            else:
                logger.error(f"Invalid directory: {new_directory}")

    def _remove_directory(self) -> None:
        idx = self._dir_list.currentRow()
        if idx < 0 or idx >= len(self._profile.directories):
            return
        del self._profile.directories[idx]
        self._refresh_directory_list()

    def _clear_all_directories(self) -> None:
        self._profile.directories.clear()
        self._refresh_directory_list()
        logger.info("Cleared all directories from profile")

    def _add_subdirectories(self) -> None:
        parent_dir = self._browse_directory(
            _("Select directory to add subdirectories from")
        )
        if not parent_dir:
            return
        parent_dir = parent_dir.strip()
        if not os.path.isdir(parent_dir):
            logger.error(f"Invalid directory: {parent_dir}")
            return

        subdirs_added = 0
        try:
            for item in os.listdir(parent_dir):
                subdir_path = os.path.join(parent_dir, item)
                if os.path.isdir(subdir_path):
                    if subdir_path not in self._profile.directories:
                        self._profile.directories.append(subdir_path)
                        subdirs_added += 1
                    else:
                        logger.debug(
                            f"Subdirectory {subdir_path} already in profile"
                        )
            if subdirs_added > 0:
                self._refresh_directory_list()
                logger.info(
                    f"Added {subdirs_added} subdirectories from {parent_dir}"
                )
            else:
                logger.info(f"No new subdirectories found in {parent_dir}")
        except Exception as e:
            logger.error(
                f"Error reading subdirectories from {parent_dir}: {e}"
            )

    # ------------------------------------------------------------------
    # Finalize
    # ------------------------------------------------------------------
    def _finalize_profile(self) -> None:
        name = self._name_edit.text().strip()

        if not name:
            logger.error("Profile name is required")
            return

        # Duplicate-name check
        if not self._is_edit:
            if DirectoryProfile.get_profile_by_name(name) is not None:
                logger.error(f"Profile with name {name} already exists")
                return
        else:
            if name != self._original_name:
                if DirectoryProfile.get_profile_by_name(name) is not None:
                    logger.error(f"Profile with name {name} already exists")
                    return

        self._profile.name = name

        if not self._is_edit:
            DirectoryProfile.add_profile(self._profile)
        else:
            DirectoryProfile.update_profile(self._original_name, self._profile)

        self.close()
        self._refresh_callback()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def closeEvent(self, event) -> None:  # noqa: N802
        DirectoryProfileWindow._instance = None
        super().closeEvent(event)
