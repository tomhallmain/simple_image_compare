"""
PySide6 port of files/directory_notes_window.py -- DirectoryNotesWindow.

Displays per-directory marked files and file notes with
Open / Remove / Edit buttons, plus export and import support.
The ``DirectoryNotes`` data class is imported from the original module.
"""

from __future__ import annotations

import os
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from files.directory_notes import DirectoryNotes
from lib.multi_display_qt import SmartDialog
from ui.app_style import AppStyle
from utils.app_actions import AppActions
from utils.translations import I18N

_ = I18N._


class DirectoryNotesWindow(SmartDialog):
    """
    Dialog showing marked files and their notes for a given directory,
    with edit, export-to-file, and import-from-file capabilities.
    """

    COL_0_WIDTH = 600
    MAX_ROWS = 30

    def __init__(
        self,
        app_master: QWidget,
        app_actions: AppActions,
        base_dir: str,
        geometry: str = "900x800",
    ) -> None:
        super().__init__(
            parent=app_master,
            position_parent=app_master,
            title=_("Directory Notes - {0}").format(
                os.path.basename(base_dir) or base_dir
            ),
            geometry=geometry,
        )
        self._app_actions = app_actions
        self._base_dir = base_dir

        # Scroll area
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet(
            f"QScrollArea {{ background: {AppStyle.BG_COLOR}; border: none; }}"
        )

        self._viewport = QWidget()
        self._viewport.setStyleSheet(f"background: {AppStyle.BG_COLOR};")
        self._grid = QGridLayout(self._viewport)
        self._grid.setAlignment(Qt.AlignTop)
        self._grid.setColumnStretch(0, 6)
        self._grid.setColumnStretch(1, 1)
        self._grid.setColumnStretch(2, 1)
        self._row = 0

        self._scroll.setWidget(self._viewport)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._scroll)

        self._build_widgets()

        QShortcut(QKeySequence(Qt.Key_Escape), self).activated.connect(self.close)

    # ==================================================================
    # Widget builders
    # ==================================================================
    def _build_widgets(self) -> None:
        self._row = 0

        # Header
        self._add_header(_("Directory: {0}").format(self._base_dir))

        # Button bar
        btn_row = QHBoxLayout()
        for label, handler in [
            (_("Export to Text File"), self.export_to_file),
            (_("Import from Text File"), self.import_from_text_file),
            (_("Import from JSON File"), self.import_from_json_file),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(handler)
            btn_row.addWidget(btn)
        btn_row.addStretch()

        btn_container = QWidget()
        btn_container.setLayout(btn_row)
        self._grid.addWidget(btn_container, self._row, 0, 1, 3, Qt.AlignLeft)
        self._row += 1

        self._add_separator()

        # ------ Marked files section ------
        self._add_header(_("MARKED FILES"))

        marked_files = DirectoryNotes.get_marked_files(self._base_dir)
        if marked_files:
            for filepath in marked_files:
                self._add_marked_file_row(filepath)
        else:
            self._add_text_label(_("(No marked files)"))

        self._add_separator()

        # ------ File notes section ------
        self._add_header(_("FILE NOTES"))

        file_notes = DirectoryNotes.get_all_file_notes(self._base_dir)
        if file_notes:
            for filepath, note in sorted(file_notes.items()):
                self._add_note_row(filepath, note)
        else:
            self._add_text_label(_("(No file notes)"))

    # ------------------------------------------------------------------
    # Marked-file row
    # ------------------------------------------------------------------
    def _add_marked_file_row(self, filepath: str) -> None:
        basename = os.path.basename(filepath)

        name_lbl = QLabel(basename)
        name_lbl.setWordWrap(True)
        name_lbl.setMaximumWidth(self.COL_0_WIDTH)
        name_lbl.setStyleSheet(
            f"color: {AppStyle.FG_COLOR}; background: {AppStyle.BG_COLOR};"
        )
        self._grid.addWidget(name_lbl, self._row, 0, Qt.AlignLeft | Qt.AlignTop)

        rm_btn = QPushButton(_("Remove"))
        rm_btn.clicked.connect(lambda _c=False, fp=filepath: self._remove_marked(fp))
        self._grid.addWidget(rm_btn, self._row, 1)

        open_btn = QPushButton(_("Open"))
        open_btn.clicked.connect(lambda _c=False, fp=filepath: self._open_file(fp))
        self._grid.addWidget(open_btn, self._row, 2)
        self._row += 1

        # Subdued path line
        path_lbl = QLabel(filepath)
        path_lbl.setWordWrap(True)
        path_lbl.setMaximumWidth(self.COL_0_WIDTH - 20)
        path_lbl.setStyleSheet(
            f"color: gray; background: {AppStyle.BG_COLOR}; "
            f"font-size: 9pt; padding-left: 20px;"
        )
        self._grid.addWidget(path_lbl, self._row, 0, 1, 3, Qt.AlignLeft)
        self._row += 1

    # ------------------------------------------------------------------
    # Note row
    # ------------------------------------------------------------------
    def _add_note_row(self, filepath: str, note: str) -> None:
        basename = os.path.basename(filepath)

        name_lbl = QLabel(basename)
        name_lbl.setWordWrap(True)
        name_lbl.setMaximumWidth(self.COL_0_WIDTH)
        name_lbl.setStyleSheet(
            f"color: {AppStyle.FG_COLOR}; background: {AppStyle.BG_COLOR};"
        )
        self._grid.addWidget(name_lbl, self._row, 0, Qt.AlignLeft | Qt.AlignTop)

        edit_btn = QPushButton(_("Edit Note"))
        edit_btn.clicked.connect(
            lambda _c=False, fp=filepath, n=note: self._edit_note_dialog(fp, n)
        )
        self._grid.addWidget(edit_btn, self._row, 1)

        rm_btn = QPushButton(_("Remove Note"))
        rm_btn.clicked.connect(lambda _c=False, fp=filepath: self._remove_note(fp))
        self._grid.addWidget(rm_btn, self._row, 2)
        self._row += 1

        # Path line
        path_lbl = QLabel(filepath)
        path_lbl.setWordWrap(True)
        path_lbl.setMaximumWidth(self.COL_0_WIDTH - 20)
        path_lbl.setStyleSheet(
            f"color: gray; background: {AppStyle.BG_COLOR}; "
            f"font-size: 9pt; padding-left: 20px;"
        )
        self._grid.addWidget(path_lbl, self._row, 0, Qt.AlignLeft)

        open_btn = QPushButton(_("Open"))
        open_btn.clicked.connect(lambda _c=False, fp=filepath: self._open_file(fp))
        self._grid.addWidget(open_btn, self._row, 1)
        self._row += 1

        # Read-only note preview
        preview = QPlainTextEdit(note)
        preview.setReadOnly(True)
        preview.setMaximumHeight(70)
        preview.setStyleSheet(
            f"color: {AppStyle.FG_COLOR}; background: {AppStyle.BG_INPUT}; "
            f"border: 1px solid {AppStyle.BORDER_COLOR}; padding: 2px;"
        )
        self._grid.addWidget(preview, self._row, 0, 1, 3)
        self._row += 1

    # ==================================================================
    # Actions
    # ==================================================================
    def _remove_marked(self, filepath: str) -> None:
        DirectoryNotes.remove_marked_file(self._base_dir, filepath)
        self._app_actions.toast(
            _("Removed marked file: {0}").format(os.path.basename(filepath))
        )
        self._refresh()

    def _remove_note(self, filepath: str) -> None:
        DirectoryNotes.remove_file_note(self._base_dir, filepath)
        self._app_actions.toast(
            _("Removed note for: {0}").format(os.path.basename(filepath))
        )
        self._refresh()

    def _open_file(self, filepath: str) -> None:
        basename = os.path.basename(filepath)
        if hasattr(self._app_actions, "get_window"):
            window = self._app_actions.get_window(base_dir=self._base_dir)
            if window is not None:
                window.go_to_file(search_text=basename, exact_match=True)
                window.media_canvas.focus()
                self._app_actions.toast(_("Opened file: {0}").format(basename))
                return
        if hasattr(self._app_actions, "new_window"):
            self._app_actions.new_window(base_dir=self._base_dir, image_path=filepath)
            self._app_actions.toast(
                _("Opened file in new window: {0}").format(basename)
            )

    # ------------------------------------------------------------------
    # Edit note dialog
    # ------------------------------------------------------------------
    def _edit_note_dialog(self, filepath: str, current_note: str) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle(
            _("Edit Note - {0}").format(os.path.basename(filepath))
        )
        dlg.resize(600, 400)
        dlg.setStyleSheet(f"background: {AppStyle.BG_COLOR};")

        vbox = QVBoxLayout(dlg)
        vbox.setContentsMargins(10, 10, 10, 10)

        path_lbl = QLabel(filepath)
        path_lbl.setWordWrap(True)
        path_lbl.setStyleSheet(f"color: {AppStyle.FG_COLOR};")
        vbox.addWidget(path_lbl)

        editor = QPlainTextEdit(current_note)
        editor.setStyleSheet(
            f"color: {AppStyle.FG_COLOR}; background: {AppStyle.BG_INPUT}; "
            f"border: 1px solid {AppStyle.BORDER_COLOR};"
        )
        vbox.addWidget(editor, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        save_btn = QPushButton(_("Save"))
        cancel_btn = QPushButton(_("Cancel"))

        def do_save():
            new_note = editor.toPlainText().strip()
            DirectoryNotes.set_file_note(self._base_dir, filepath, new_note)
            self._app_actions.toast(
                _("Note saved for: {0}").format(os.path.basename(filepath))
            )
            dlg.accept()
            self._refresh()

        save_btn.clicked.connect(do_save)
        cancel_btn.clicked.connect(dlg.reject)

        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        vbox.addLayout(btn_row)

        # Ctrl+Enter saves
        QShortcut(QKeySequence("Ctrl+Return"), dlg).activated.connect(do_save)
        QShortcut(QKeySequence(Qt.Key_Escape), dlg).activated.connect(dlg.reject)

        dlg.exec()

    # ==================================================================
    # Export / Import
    # ==================================================================
    def export_to_file(self) -> None:
        default_name = f"{os.path.basename(self._base_dir) or 'root'}_notes.txt"
        path, _ = QFileDialog.getSaveFileName(
            self,
            _("Export Directory Notes"),
            os.path.join(self._base_dir, default_name),
            _("Text files (*.txt);;All files (*)"),
        )
        if path:
            try:
                exported = DirectoryNotes.export_to_text(self._base_dir, path)
                self._app_actions.toast(_("Exported notes to: {0}").format(exported))
            except Exception as e:
                QMessageBox.critical(self, _("Export Error"),
                                     _("Failed to export notes: {0}").format(str(e)))

    def import_from_text_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            _("Import Marked Files from Text File"),
            self._base_dir,
            _("Text files (*.txt);;All files (*)"),
        )
        if not path:
            return
        try:
            from lib.qt_alert import qt_alert
            recursive = qt_alert(
                self,
                _("Import Options"),
                _("Search recursively in subdirectories for matching filenames?"),
                kind="askyesno",
            )

            added, not_found_count, not_found = DirectoryNotes.import_from_text_file(
                self._base_dir, path, recursive=recursive,
            )

            msg = _("Imported {0} files.").format(added)
            if not_found_count > 0:
                msg += "\n\n" + _("{0} filenames not found:").format(not_found_count)
                msg += "\n" + "\n".join(not_found[:10])
                if len(not_found) > 10:
                    msg += "\n" + _("... and {0} more").format(len(not_found) - 10)

            QMessageBox.information(self, _("Import Complete"), msg)
            self._app_actions.toast(_("Imported {0} marked files").format(added))
            self._refresh()
        except Exception as e:
            QMessageBox.critical(
                self, _("Import Error"),
                _("Failed to import from text file: {0}").format(str(e)),
            )

    def import_from_json_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            _("Import Marked Files from JSON File"),
            self._base_dir,
            _("JSON files (*.json);;All files (*)"),
        )
        if not path:
            return
        try:
            added, invalid_count, invalid_paths = DirectoryNotes.import_from_json_file(
                self._base_dir, path,
            )

            msg = _("Imported {0} files.").format(added)
            if invalid_count > 0:
                msg += "\n\n" + _("{0} invalid or missing file paths:").format(invalid_count)
                msg += "\n" + "\n".join(invalid_paths[:10])
                if len(invalid_paths) > 10:
                    msg += "\n" + _("... and {0} more").format(len(invalid_paths) - 10)

            QMessageBox.information(self, _("Import Complete"), msg)
            self._app_actions.toast(_("Imported {0} marked files").format(added))
            self._refresh()
        except Exception as e:
            QMessageBox.critical(
                self, _("Import Error"),
                _("Failed to import from JSON file: {0}").format(str(e)),
            )

    # ==================================================================
    # Helpers
    # ==================================================================
    def _add_header(self, text: str) -> None:
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            f"color: {AppStyle.FG_COLOR}; background: {AppStyle.BG_COLOR}; "
            f"font-weight: bold; padding: 4px 0;"
        )
        self._grid.addWidget(lbl, self._row, 0, 1, 3, Qt.AlignLeft)
        self._row += 1

    def _add_text_label(self, text: str) -> None:
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            f"color: {AppStyle.FG_COLOR}; background: {AppStyle.BG_COLOR};"
        )
        self._grid.addWidget(lbl, self._row, 0, 1, 3, Qt.AlignLeft)
        self._row += 1

    def _add_separator(self) -> None:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet(f"color: {AppStyle.FG_COLOR};")
        self._grid.addWidget(line, self._row, 0, 1, 3)
        self._row += 1

    def _clear_widgets(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _refresh(self) -> None:
        self._clear_widgets()
        self._build_widgets()

    def close_window(self, event=None) -> None:
        self.close()
