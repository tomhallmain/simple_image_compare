"""
PySide6 port of utils/help_and_config.py -- HelpAndConfig window.

Displays keyboard shortcut reference tables (Main Window, Image Details,
Go To File) and editable config settings inside a scrollable dialog.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QGridLayout, QLabel, QLineEdit,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from lib.multi_display_qt import SmartDialog
from ui.app_style import AppStyle
from utils.config import config
from utils.translations import I18N

_ = I18N._


class HelpAndConfig(SmartDialog):
    """Help & Config dialog with keyboard shortcut tables and config settings."""

    has_run_import = False

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        position_parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(
            parent=parent,
            position_parent=position_parent or parent,
            title=_("Help and Config"),
            geometry="900x600",
        )
        self._help_labels: list[QLabel] = []

        # -- scrollable container ----------------------------------------
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet(
            f"QScrollArea {{ background: {AppStyle.BG_COLOR}; border: none; }}"
        )

        viewport = QWidget()
        viewport.setStyleSheet(f"background: {AppStyle.BG_COLOR};")
        self._grid = QGridLayout(viewport)
        self._grid.setAlignment(Qt.AlignTop)
        self._grid.setColumnStretch(0, 1)
        self._grid.setColumnStretch(1, 9)
        self._row = 0

        scroll_area.setWidget(viewport)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll_area)

        col_0_width = 250

        # ==============================================================
        # Main Window Shortcuts
        # ==============================================================
        self._add_section_title(_("Main Window Shortcuts"))

        main_help: dict[str, str] = {
            _("Command"): _("Description"),
            "Ctrl+A": _("Search current image in new window"),
            "Ctrl+B": _("Return to Browsing mode"),
            "Ctrl+C": _("Copy marks list"),
            "Ctrl+D": _("Set current marks from previous marks list"),
            "Ctrl+F": _("Open Favorites window"),
            "Ctrl+G": _("Open Go to file window"),
            "Ctrl+H": _("Hide/show sidebar"),
            "Ctrl+H*": _("Open hotkeys window (*when marks window open)"),
            "Ctrl+J": _("Open content filters window"),
            "Ctrl+K": _("Open marks window (no GUI)"),
            "Ctrl+M": _("Open marks window"),
            "Ctrl+N": _("Open marks action history window"),
            "Ctrl+Q": _("Quit"),
            "Ctrl+P": _("Open security configuration window"),
            "Ctrl+R": _("Run previous marks action"),
            "Ctrl+E": _("Run penultimate marks action"),
            "Ctrl+Shift+R": _("Run third-most-recent marks action"),
            "Ctrl+Return": _("Continue image generation"),
            "Ctrl+Shift+Return": _("Cancel image generation"),
            "Ctrl+S": _("Run next text embedding search preset"),
            "Ctrl+T": _("Run permanent marks action"),
            "Ctrl+V": _("Open type configuration window"),
            "Ctrl+W": _("Open new compare window"),
            "Ctrl+X": _("Move previous marks to a different directory"),
            "Ctrl+Z": _("Undo previous marks changes"),
            "Shift-F / F11": _("Toggle fullscreen"),
            "Home": _("Go to first sorted image"),
            "End": _("Go to last sorted image"),
            "Left/Right Arrow\nMouse Wheel Up/Down": _("Show previous/next image"),
            "Page Up/Down": _("Page through images"),
            "Shift-A": _("Search current image in current window"),
            "Shift+B": _("Clear all hidden images"),
            "Shift+C": _("Clear marks list"),
            "Shift+D": _("Show image details"),
            "Shift+Delete\nMouse Wheel Click": _("Delete image (or marked file group if marks window selected)"),
            "Ctrl+Shift+Delete": _("Delete current base directory and all contents"),
            "Shift+G": _("Go to next mark"),
            "Shift+H": _("Show help window"),
            "Shift+I": _("Run image generation"),
            "Right Click": _("Open context menu"),
            "Shift+J": _("Run content filters for all files in the current directory"),
            "Shift+K": _("View last moved image mark"),
            "Shift+L": _("Toggle content filters"),
            "Shift+M": _("Add or remove a mark for current image"),
            "Shift+N": _("Add all marks between most recently set and current selected inclusive, or all marks in current group"),
            "Shift+O": _("Open media location"),
            "Shift+P": _("Open image in GIMP"),
            "Shift+Q": _("Randomly modify image"),
            "Shift+R": _("View related image (controlnet, etc.)"),
            "Shift+S": _("Toggle slideshow"),
            "Shift+T": _("Find related images in open window"),
            "Shift+U": _("Run refacdir"),
            "Shift+V": _("Hide current image"),
            "Shift+Y": _("Set marks from downstream related images"),
            "Shift+Z": _("Undo previous marks changes"),
            "Shift+Left/Right Arrow": _("Show previous/next group"),
        }

        self._add_help_table(main_help, col_0_width)

        # ==============================================================
        # Image Details Shortcuts
        # ==============================================================
        self._add_divider()
        self._add_section_title(_("Image Details Shortcuts"))

        details_help: dict[str, str] = {
            _("Command"): _("Description"),
            "Shift+C": _("Crop Image (Smart Detect)"),
            "Shift+L": _("Rotate Image Left"),
            "Shift+R": _("Rotate Image Right"),
            "Shift+E": _("Enhance Image"),
            "Shift+A": _("Random Crop"),
            "Shift+Q": _("Randomly Modify Image"),
            "Shift+H": _("Flip Image Horizontally"),
            "Shift+V": _("Flip Image Vertically"),
            "Shift+X": _("Copy Without EXIF"),
            "Shift+J": _("Convert to JPG"),
            "Shift+D": _("Show Metadata"),
            "Shift+R": _("Open Related Image"),
            "Shift+I": _("Run Image Generation"),
            "Shift+Y": _("Redo Prompt"),
        }

        self._add_help_table(details_help, col_0_width)

        # Ctrl-behaviour note
        note = QLabel(
            _("Note: Using Ctrl instead of Shift marks the created file "
              "and opens the marks window without GUI."),
        )
        note.setWordWrap(True)
        note.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        note.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        note.setContentsMargins(10, 10, 10, 10)
        note.setStyleSheet(
            f"color: {AppStyle.FG_COLOR}; background: {AppStyle.BG_COLOR}; "
            "padding: 0;"
        )
        self._grid.addWidget(note, self._row, 0, 1, 2)
        note.setMinimumHeight(note.sizeHint().height())
        self._row += 1
        self._help_labels.append(note)

        # ==============================================================
        # Go To File Shortcuts
        # ==============================================================
        self._add_divider()
        self._add_section_title(_("Go To File Shortcuts"))

        gotofile_help: dict[str, str] = {
            _("Command"): _("Description"),
            "Ctrl+G": _("Go To Last Moved"),
            "Ctrl+B": _("Browse File"),
            "Ctrl+R": _("Current Media"),
            "Ctrl+F": _("Find Related Files"),
            "Ctrl+E": _("Extract Base ID"),
            "Ctrl+D": _("Browse Directory"),
        }

        self._add_help_table(gotofile_help, col_0_width)

        # ==============================================================
        # Config Settings
        # ==============================================================
        self._add_divider()
        self._add_section_title(_("Config Settings"))

        # -- boolean settings (checkboxes) --
        self._cb_show_toasts = self._add_checkbox_row(
            _("Show Toasts"), config.show_toasts,
        )
        self._le_slideshow_interval = self._add_entry_row(
            _("Slideshow Interval (sec)"), str(config.slideshow_interval_seconds),
        )
        self._le_file_check_interval = self._add_entry_row(
            _("File Check Interval (sec)"), str(config.file_check_interval_seconds),
        )
        self._le_max_search_results = self._add_entry_row(
            _("Max Search Results"), str(config.max_search_results),
        )

        # Sort By (read-only display)
        sort_label = self._make_label(_("Sort By"), col_0_width)
        sort_label.setFixedWidth(col_0_width)
        sort_value = self._make_label(str(config.sort_by))
        self._grid.addWidget(sort_label, self._row, 0, Qt.AlignLeft | Qt.AlignTop)
        self._grid.addWidget(sort_value, self._row, 1, Qt.AlignLeft | Qt.AlignTop)
        self._row += 1

        self._cb_enable_prevalidations = self._add_checkbox_row(
            _("Enable Prevalidations"), config.enable_prevalidations,
        )
        self._le_toasts_persist = self._add_entry_row(
            _("Toasts Persist (sec)"), str(config.toasts_persist_seconds),
        )
        self._le_title_notify_persist = self._add_entry_row(
            _("Title Notify Persist (sec)"), str(config.title_notify_persist_seconds),
        )
        self._cb_delete_instantly = self._add_checkbox_row(
            _("Delete Instantly"), config.delete_instantly,
        )
        self._le_trash_folder = self._add_entry_row(
            _("Trash Folder"), str(config.trash_folder),
        )
        self._cb_image_tagging = self._add_checkbox_row(
            _("Image Tagging Enabled"), config.image_tagging_enabled,
        )
        self._cb_escape_backslash = self._add_checkbox_row(
            _("Escape Backslash Filepaths"), config.escape_backslash_filepaths,
        )

        # -- Escape to close ---------------------------------------------
        shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
        shortcut.activated.connect(self.close)

    # ==================================================================
    # Helpers
    # ==================================================================
    def close_windows(self, event=None) -> None:  # noqa: D401
        self.close()

    # ------------------------------------------------------------------
    # Internal builders
    # ------------------------------------------------------------------
    def _add_section_title(self, text: str) -> None:
        title = QLabel(text)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            f"color: {AppStyle.FG_COLOR}; background: {AppStyle.BG_COLOR}; "
            f"font-weight: bold; padding-bottom: 6px;"
        )
        self._grid.addWidget(title, self._row, 0, 1, 2)
        self._row += 1

    def _add_divider(self) -> None:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(
            f"color: {AppStyle.FG_COLOR}; margin-top: 10px; margin-bottom: 6px;"
        )
        self._grid.addWidget(line, self._row, 0, 1, 2)
        self._row += 1

    def _add_help_table(self, items: dict[str, str], col_0_width: int) -> None:
        for key, value in items.items():
            key_label = self._make_label(key, col_0_width)
            # Keep command labels visually stable: no auto-wrap in column 0.
            # Explicit newlines in the shortcut text still render as intended.
            key_label.setFixedWidth(col_0_width)
            key_label.setWordWrap(False)
            val_label = self._make_label(value)
            self._grid.addWidget(key_label, self._row, 0, Qt.AlignLeft | Qt.AlignTop)
            self._grid.addWidget(val_label, self._row, 1, Qt.AlignTop)
            self._row += 1
            self._help_labels.extend([key_label, val_label])

    def _make_label(self, text: str, max_width: int | None = None) -> QLabel:
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        if max_width is not None:
            lbl.setMaximumWidth(max_width)
        lbl.setStyleSheet(
            f"color: {AppStyle.FG_COLOR}; background: {AppStyle.BG_COLOR};"
        )
        return lbl

    def _add_checkbox_row(self, label_text: str, initial: bool) -> QCheckBox:
        lbl = self._make_label(label_text, 250)
        lbl.setFixedWidth(250)
        cb = QCheckBox()
        cb.setChecked(initial)
        cb.setStyleSheet(
            f"QCheckBox {{ color: {AppStyle.FG_COLOR}; background: {AppStyle.BG_COLOR}; }}"
        )
        self._grid.addWidget(lbl, self._row, 0, Qt.AlignLeft | Qt.AlignTop)
        self._grid.addWidget(cb, self._row, 1, Qt.AlignLeft | Qt.AlignTop)
        self._row += 1
        return cb

    def _add_entry_row(self, label_text: str, initial: str) -> QLineEdit:
        lbl = self._make_label(label_text, 250)
        lbl.setFixedWidth(250)
        entry = QLineEdit(initial)
        entry.setFixedWidth(300)
        entry.setStyleSheet(
            f"QLineEdit {{ color: {AppStyle.FG_COLOR}; "
            f"background: {AppStyle.BG_INPUT}; "
            f"border: 1px solid {AppStyle.BORDER_COLOR}; "
            f"padding: 2px 4px; }}"
        )
        self._grid.addWidget(lbl, self._row, 0, Qt.AlignLeft | Qt.AlignTop)
        self._grid.addWidget(entry, self._row, 1, Qt.AlignLeft | Qt.AlignTop)
        self._row += 1
        return entry
