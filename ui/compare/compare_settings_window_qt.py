"""
PySide6 port of compare/compare_settings_window.py -- CompareSettingsWindow.

Singleton dialog per CompareManager for configuring comparison modes,
filters, and composite search settings.

Non-UI imports:
  - CompareManager, CombinationLogic, SizeFilter, ModelFilter
    from compare.compare_manager (reuse policy)
"""

from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from compare.compare_manager import (
    CompareManager,
    CombinationLogic,
    SizeFilter,
    ModelFilter,
)
from lib.multi_display_qt import SmartDialog
from ui.app_style import AppStyle
from utils.config import config
from utils.constants import CompareMode
from utils.translations import I18N
from utils.logging_setup import get_logger

_ = I18N._
logger = get_logger("compare_settings_window_qt")


def _h_separator() -> QFrame:
    """Create a horizontal separator line."""
    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.HLine)
    sep.setFrameShadow(QFrame.Shadow.Sunken)
    return sep


class CompareSettingsWindow(SmartDialog):
    """Window for configuring comparison modes, filters, and composite search settings."""

    _open_windows: Dict[object, CompareSettingsWindow] = {}

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------
    @classmethod
    def open(cls, parent: QWidget, compare_manager: CompareManager) -> None:
        """Show or focus the settings window for *compare_manager*."""
        if compare_manager in cls._open_windows:
            win = cls._open_windows[compare_manager]
            try:
                if win.isVisible():
                    win.raise_()
                    win.activateWindow()
                    return
            except Exception:
                pass
        cls(parent, compare_manager)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def __init__(self, parent: QWidget, compare_manager: CompareManager) -> None:
        # Reuse check
        if compare_manager in CompareSettingsWindow._open_windows:
            existing = CompareSettingsWindow._open_windows[compare_manager]
            try:
                if existing.isVisible():
                    existing.raise_()
                    existing.activateWindow()
                    return
            except Exception:
                pass

        super().__init__(
            parent=parent,
            position_parent=parent,
            title=_("Compare Settings"),
            geometry="1000x700",
        )
        CompareSettingsWindow._open_windows[compare_manager] = self

        self._compare_manager = compare_manager
        self._mode_checkboxes: Dict[CompareMode, QCheckBox] = {}
        self._weight_vars: Dict[str, QLineEdit] = {}  # instance_id -> QLineEdit
        self._threshold_combo: Optional[QComboBox] = None

        self._build_ui()

        QShortcut(QKeySequence(Qt.Key_Escape), self).activated.connect(self.close)
        self.show()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(0)

        # Title
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_lbl = QLabel(_("Compare Settings"))
        title_lbl.setFont(title_font)
        title_lbl.setStyleSheet(f"color: {AppStyle.FG_COLOR};")
        outer.addWidget(title_lbl)
        outer.addSpacing(20)

        # Two-column body
        body = QHBoxLayout()
        body.setSpacing(20)

        # ---- LEFT COLUMN ------------------------------------------------
        left = QVBoxLayout()
        left.setSpacing(6)

        section_font = QFont()
        section_font.setPointSize(11)
        section_font.setBold(True)

        # -- Comparison Modes section --
        modes_title = QLabel(_("Comparison Modes"))
        modes_title.setFont(section_font)
        modes_title.setStyleSheet(f"color: {AppStyle.FG_COLOR};")
        left.addWidget(modes_title)

        active_modes = self._compare_manager.get_active_modes()
        primary_mode = self._compare_manager.compare_mode

        for mode in CompareMode:
            cb = QCheckBox(mode.get_text())
            cb.setChecked(mode in active_modes or mode == primary_mode)
            cb.stateChanged.connect(lambda _state, m=mode: self._on_mode_toggled(m))
            self._mode_checkboxes[mode] = cb
            left.addWidget(cb)

        add_instance_btn = QPushButton(_("Add Instance"))
        add_instance_btn.clicked.connect(self._on_add_instance)
        left.addWidget(add_instance_btn, 0, Qt.AlignLeft)

        left.addWidget(_h_separator())

        # -- Combination Logic section --
        logic_row = QHBoxLayout()
        logic_lbl = QLabel(_("Combination Logic:"))
        logic_lbl.setStyleSheet(f"color: {AppStyle.FG_COLOR};")
        logic_row.addWidget(logic_lbl)

        self._logic_combo = QComboBox()
        self._logic_combo.addItems([lg.value for lg in CombinationLogic])
        self._logic_combo.setCurrentText(
            self._compare_manager.get_combination_logic().value
        )
        self._logic_combo.currentTextChanged.connect(self._on_logic_changed)
        logic_row.addWidget(self._logic_combo)
        logic_row.addStretch()
        left.addLayout(logic_row)

        # -- Weight controls (dynamic container) --
        self._weight_container = QVBoxLayout()
        left.addLayout(self._weight_container)
        self._update_weight_controls_visibility()

        left.addStretch()
        body.addLayout(left, 1)

        # ---- RIGHT COLUMN -----------------------------------------------
        right = QVBoxLayout()
        right.setSpacing(6)

        # -- Compare Settings section --
        settings_title = QLabel(_("Compare Settings"))
        settings_title.setFont(section_font)
        settings_title.setStyleSheet(f"color: {AppStyle.FG_COLOR};")
        right.addWidget(settings_title)

        # Threshold
        current_args = self._compare_manager.get_args()
        primary_mode = self._compare_manager.compare_mode

        thresh_row = QHBoxLayout()
        thresh_lbl = QLabel(_("Threshold"))
        thresh_lbl.setStyleSheet(f"color: {AppStyle.FG_COLOR};")
        thresh_row.addWidget(thresh_lbl)

        self._threshold_combo = QComboBox()
        self._threshold_combo.setEditable(True)
        self._populate_threshold_combo(primary_mode, current_args)
        thresh_row.addWidget(self._threshold_combo)
        thresh_row.addStretch()
        right.addLayout(thresh_row)

        # Counter limit
        limit_row = QHBoxLayout()
        limit_lbl = QLabel(_("Max files to compare"))
        limit_lbl.setStyleSheet(f"color: {AppStyle.FG_COLOR};")
        limit_row.addWidget(limit_lbl)

        counter_limit_value = (
            current_args.counter_limit
            if hasattr(current_args, "counter_limit")
            else config.file_counter_limit
        )
        self._counter_limit_edit = QLineEdit(
            "" if counter_limit_value is None else str(counter_limit_value)
        )
        self._counter_limit_edit.setFixedWidth(100)
        limit_row.addWidget(self._counter_limit_edit)
        limit_row.addStretch()
        right.addLayout(limit_row)

        # Checkboxes
        self._compare_faces_cb = QCheckBox(_("Compare faces"))
        self._compare_faces_cb.setChecked(
            current_args.compare_faces
            if hasattr(current_args, "compare_faces")
            else False
        )
        right.addWidget(self._compare_faces_cb)

        self._overwrite_cb = QCheckBox(_("Overwrite cache"))
        self._overwrite_cb.setChecked(
            current_args.overwrite
            if hasattr(current_args, "overwrite")
            else False
        )
        right.addWidget(self._overwrite_cb)

        self._store_checkpoints_cb = QCheckBox(_("Store checkpoints"))
        self._store_checkpoints_cb.setChecked(
            current_args.store_checkpoints
            if hasattr(current_args, "store_checkpoints")
            else config.store_checkpoints
        )
        right.addWidget(self._store_checkpoints_cb)

        self._search_closest_cb = QCheckBox(_("Search only return closest"))
        self._search_closest_cb.setChecked(config.search_only_return_closest)
        right.addWidget(self._search_closest_cb)

        right.addWidget(_h_separator())

        # -- Filters section --
        filter_title = QLabel(_("Filters (Applied Before Comparison)"))
        filter_title.setFont(section_font)
        filter_title.setStyleSheet(f"color: {AppStyle.FG_COLOR};")
        right.addWidget(filter_title)

        size_row = QHBoxLayout()
        size_lbl = QLabel(_("Size Filter:"))
        size_lbl.setStyleSheet(f"color: {AppStyle.FG_COLOR};")
        size_row.addWidget(size_lbl)
        size_note = QLabel(_("(Size filtering UI to be implemented)"))
        size_note.setStyleSheet(f"color: {AppStyle.FG_COLOR}; font-size: 9pt;")
        size_row.addWidget(size_note)
        size_row.addStretch()
        right.addLayout(size_row)

        model_row = QHBoxLayout()
        model_lbl = QLabel(_("Model Filter:"))
        model_lbl.setStyleSheet(f"color: {AppStyle.FG_COLOR};")
        model_row.addWidget(model_lbl)
        model_note = QLabel(_("(Model filtering UI to be implemented)"))
        model_note.setStyleSheet(f"color: {AppStyle.FG_COLOR}; font-size: 9pt;")
        model_row.addWidget(model_note)
        model_row.addStretch()
        right.addLayout(model_row)

        right.addStretch()
        body.addLayout(right, 1)

        outer.addLayout(body, 1)

        # ---- Bottom bar -------------------------------------------------
        outer.addWidget(_h_separator())
        outer.addSpacing(10)

        btn_row = QHBoxLayout()
        apply_btn = QPushButton(_("Apply"))
        apply_btn.clicked.connect(self._on_apply)
        btn_row.addWidget(apply_btn)

        cancel_btn = QPushButton(_("Cancel"))
        cancel_btn.clicked.connect(self.close)
        btn_row.addWidget(cancel_btn)

        btn_row.addStretch()
        outer.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Threshold combo helpers
    # ------------------------------------------------------------------
    def _populate_threshold_combo(
        self,
        mode: Optional[CompareMode],
        current_args=None,
    ) -> None:
        self._threshold_combo.clear()
        threshold_vals = (
            mode.threshold_vals()
            if mode is not None
            else CompareMode.CLIP_EMBEDDING.threshold_vals()
        )
        if threshold_vals is None:
            threshold_vals = CompareMode.CLIP_EMBEDDING.threshold_vals()

        for v in threshold_vals:
            self._threshold_combo.addItem(str(v))

        # Determine current value
        if current_args is not None and hasattr(current_args, "threshold"):
            current_val = str(current_args.threshold)
        elif mode == CompareMode.COLOR_MATCHING:
            current_val = str(config.color_diff_threshold)
        else:
            current_val = str(config.embedding_similarity_threshold)

        self._threshold_combo.setCurrentText(current_val)

    def _update_threshold_menu(self, mode: Optional[CompareMode]) -> None:
        if mode is None:
            return
        threshold_vals = mode.threshold_vals()
        if threshold_vals is None:
            threshold_vals = CompareMode.CLIP_EMBEDDING.threshold_vals()

        current_val = self._threshold_combo.currentText()
        self._threshold_combo.clear()
        for v in threshold_vals:
            self._threshold_combo.addItem(str(v))

        if current_val not in [str(v) for v in threshold_vals]:
            if mode == CompareMode.COLOR_MATCHING:
                default_val = config.color_diff_threshold
            else:
                default_val = config.embedding_similarity_threshold
            self._threshold_combo.setCurrentText(str(default_val))
        else:
            self._threshold_combo.setCurrentText(current_val)

    # ------------------------------------------------------------------
    # Mode toggling
    # ------------------------------------------------------------------
    def _on_mode_toggled(self, mode: CompareMode) -> None:
        cb = self._mode_checkboxes[mode]
        if cb.isChecked():
            self._compare_manager.add_mode(mode)
            if self._compare_manager.compare_mode is None:
                self._compare_manager.set_primary_mode(mode)
        else:
            active_modes = self._compare_manager.get_active_modes()
            if len(active_modes) <= 1 and mode in active_modes:
                cb.setChecked(True)
                return
            self._compare_manager.remove_mode(mode)

        self._update_threshold_menu(self._compare_manager.compare_mode)
        self._update_weight_controls_visibility()

    # ------------------------------------------------------------------
    # Combination logic
    # ------------------------------------------------------------------
    def _on_logic_changed(self, logic_str: str) -> None:
        try:
            logic = CombinationLogic(logic_str)
            self._compare_manager.set_combination_logic(logic)
            self._update_weight_controls_visibility()
        except ValueError:
            logger.warning(f"Invalid combination logic: {logic_str}")

    # ------------------------------------------------------------------
    # Weight controls (dynamic)
    # ------------------------------------------------------------------
    def _update_weight_controls_visibility(self) -> None:
        _clear_layout(self._weight_container)
        self._weight_vars.clear()

        if (
            self._compare_manager.get_combination_logic()
            != CombinationLogic.WEIGHTED
        ):
            return

        mode_instances = self._compare_manager.get_mode_instances()

        header = QLabel(_("Instance Weights:"))
        header.setStyleSheet(f"color: {AppStyle.FG_COLOR};")
        self._weight_container.addWidget(header)

        for mode_cfg in mode_instances:
            if not mode_cfg.enabled:
                continue
            row = QHBoxLayout()
            lbl = QLabel(
                f"{mode_cfg.instance_id} ({mode_cfg.compare_mode.get_text()}):"
            )
            lbl.setStyleSheet(f"color: {AppStyle.FG_COLOR};")
            row.addWidget(lbl)

            weight_edit = QLineEdit(str(mode_cfg.weight))
            weight_edit.setFixedWidth(80)
            row.addWidget(weight_edit)
            row.addStretch()

            self._weight_vars[mode_cfg.instance_id] = weight_edit
            self._weight_container.addLayout(row)

    # ------------------------------------------------------------------
    # Add Instance (placeholder)
    # ------------------------------------------------------------------
    def _on_add_instance(self) -> None:
        # TODO: Show dialog to select mode and configure instance
        logger.info("Add instance feature - UI implementation needed")

    # ------------------------------------------------------------------
    # Apply
    # ------------------------------------------------------------------
    def _on_apply(self) -> None:
        # Weights
        if (
            self._compare_manager.get_combination_logic()
            == CombinationLogic.WEIGHTED
        ):
            for instance_id, weight_edit in self._weight_vars.items():
                try:
                    weight = float(weight_edit.text())
                    self._compare_manager.set_mode_weight(instance_id, weight)
                    logger.debug(
                        f"Setting weight for instance {instance_id} to {weight}"
                    )
                except ValueError:
                    logger.warning(
                        f"Invalid weight for instance {instance_id}: "
                        f"{weight_edit.text()}"
                    )

        # Threshold
        primary_mode = self._compare_manager.compare_mode
        if primary_mode:
            try:
                threshold_str = self._threshold_combo.currentText().strip()
                if primary_mode == CompareMode.COLOR_MATCHING:
                    threshold = int(threshold_str)
                else:
                    threshold = float(threshold_str)
                self._compare_manager.set_threshold(threshold)
            except ValueError:
                logger.warning(
                    f"Invalid threshold: {self._threshold_combo.currentText()}"
                )

        # Counter limit
        try:
            cl_str = self._counter_limit_edit.text().strip()
            if cl_str == "":
                self._compare_manager.set_counter_limit(None)
            else:
                self._compare_manager.set_counter_limit(int(cl_str))
        except ValueError:
            logger.warning(
                f"Invalid counter limit: {self._counter_limit_edit.text()}"
            )

        self._compare_manager.set_compare_faces(
            self._compare_faces_cb.isChecked()
        )
        self._compare_manager.set_overwrite(self._overwrite_cb.isChecked())
        self._compare_manager.set_store_checkpoints(
            self._store_checkpoints_cb.isChecked()
        )

        config.search_only_return_closest = (
            self._search_closest_cb.isChecked()
        )

        self.close()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def closeEvent(self, event) -> None:  # noqa: N802
        CompareSettingsWindow._open_windows.pop(self._compare_manager, None)
        super().closeEvent(event)


# ======================================================================
# Helpers
# ======================================================================
def _clear_layout(layout) -> None:
    """Recursively remove all items from a QLayout."""
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
        sub = item.layout()
        if sub is not None:
            _clear_layout(sub)
