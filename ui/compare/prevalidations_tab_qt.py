"""
PySide6 port of compare/prevalidations_tab.py.

Contains two classes:
  - PrevalidationModifyWindow  -- subclass of ClassifierActionModifyWindow
    adding lookahead and directory-profile fields.
  - PrevalidationsTab          -- tab-page QWidget listing prevalidations
    with add / modify / delete / copy / run controls, plus lookahead and
    directory-profile management sections.

Non-UI imports:
  - Prevalidation, ClassifierActionsManager
    from compare.classifier_actions_manager (reuse policy)
  - Lookahead from compare.lookahead (reuse policy)
  - DirectoryProfile from compare.directory_profile (reuse policy)
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QGridLayout, QHBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

from compare.classifier_actions_manager import (
    Prevalidation,
    ClassifierActionsManager,
)
from files.directory_profile import DirectoryProfile
from compare.lookahead import Lookahead
from ui.compare.classifier_management_window_qt import ClassifierActionModifyWindow
from ui.app_style import AppStyle
from utils.config import config
from utils.logging_setup import get_logger
from utils.translations import I18N

_ = I18N._
logger = get_logger("prevalidations_tab_qt")


# ======================================================================
# PrevalidationModifyWindow
# ======================================================================
class PrevalidationModifyWindow(ClassifierActionModifyWindow):
    """Modify dialog for Prevalidation objects, adding lookahead/profile fields."""

    _pv_instance: Optional[PrevalidationModifyWindow] = None

    def __init__(
        self,
        parent: QWidget,
        app_actions,
        refresh_callback,
        prevalidation: Optional[Prevalidation] = None,
        dimensions: str = "600x600",
    ) -> None:
        prevalidation = prevalidation if prevalidation is not None else Prevalidation()
        super().__init__(
            parent,
            app_actions,
            refresh_callback,
            prevalidation,
            _("Modify Prevalidation"),
            _("Prevalidation Name"),
            _("New Prevalidation"),
            dimensions,
        )
        PrevalidationModifyWindow._pv_instance = self

    # ------------------------------------------------------------------
    # Subclass hook: add lookahead + profile fields
    # ------------------------------------------------------------------
    def add_specific_fields(self, grid: QGridLayout, row: int) -> int:
        pv = self._classifier_action  # actually a Prevalidation

        # -- Lookaheads multi-select --------------------------------------
        row += 1
        grid.addWidget(
            self._lbl(_("Lookaheads (select from shared list)")),
            row, 0, Qt.AlignLeft | Qt.AlignTop,
        )
        self._lookahead_list = QListWidget()
        self._lookahead_list.setSelectionMode(
            QAbstractItemView.SelectionMode.MultiSelection
        )
        self._lookahead_list.setMaximumHeight(80)
        self._populate_lookahead_list()
        grid.addWidget(self._lookahead_list, row, 1)

        # -- Profile dropdown ---------------------------------------------
        row += 1
        grid.addWidget(
            self._lbl(_("Directory Profile")), row, 0, Qt.AlignLeft
        )
        self._profile_combo = QComboBox()
        profile_options = [""]
        profile_options.extend(
            p.name for p in DirectoryProfile.directory_profiles
        )
        self._profile_combo.addItems(profile_options)
        current_profile = pv.profile_name if pv.profile_name else ""
        if current_profile in profile_options:
            self._profile_combo.setCurrentText(current_profile)
        else:
            self._profile_combo.setCurrentIndex(0)
        grid.addWidget(self._profile_combo, row, 1)

        return row

    def _populate_lookahead_list(self) -> None:
        pv = self._classifier_action
        self._lookahead_list.clear()
        for lh in Lookahead.lookaheads:
            item = QListWidgetItem(lh.name)
            self._lookahead_list.addItem(item)
            if lh.name in pv.lookahead_names:
                item.setSelected(True)

    def refresh_lookahead_options(self) -> None:
        self._populate_lookahead_list()

    def refresh_profile_options(self) -> None:
        current = self._profile_combo.currentText()
        self._profile_combo.clear()
        options = [""]
        options.extend(p.name for p in DirectoryProfile.directory_profiles)
        self._profile_combo.addItems(options)
        if current in options:
            self._profile_combo.setCurrentText(current)
        else:
            self._profile_combo.setCurrentIndex(0)

    def _finalize_specific(self) -> None:
        pv = self._classifier_action
        pv.lookahead_names = [
            item.text() for item in self._lookahead_list.selectedItems()
        ]
        selected_profile = self._profile_combo.currentText().strip()
        profile_name = selected_profile if selected_profile else None
        pv.update_profile_instance(profile_name=profile_name)

    def closeEvent(self, event) -> None:  # noqa: N802
        PrevalidationModifyWindow._pv_instance = None
        super().closeEvent(event)


# ======================================================================
# PrevalidationsTab
# ======================================================================
class PrevalidationsTab(QWidget):
    """
    Tab content widget for managing prevalidations.

    Sections (top-to-bottom):
      1. Lookahead management (QListWidget + Add/Edit/Remove)
      2. Directory profile management (QListWidget + Add/Edit/Remove)
      3. Prevalidation list (scrollable rows with action buttons)
    """

    _modify_window: Optional[PrevalidationModifyWindow] = None
    _lookahead_window = None
    _profile_window = None

    @staticmethod
    def _is_modify_window_valid() -> bool:
        win = PrevalidationsTab._modify_window
        if win is None:
            return False
        try:
            return win.isVisible()
        except Exception:
            PrevalidationsTab._modify_window = None
            return False

    @staticmethod
    def clear_prevalidated_cache() -> None:
        ClassifierActionsManager.prevalidated_cache.clear()

    @staticmethod
    def prevalidate(
        image_path,
        get_base_dir_func,
        hide_callback,
        notify_callback,
        add_mark_callback,
    ):
        """Run prevalidations and return action type or None."""
        return ClassifierActionsManager.prevalidate(
            image_path,
            get_base_dir_func,
            hide_callback,
            notify_callback,
            add_mark_callback,
        )

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def __init__(self, parent: QWidget, app_actions) -> None:
        super().__init__(parent)
        self._app_actions = app_actions
        self._filtered = ClassifierActionsManager.prevalidations[:]

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(6)

        # ---- Lookahead management section --------------------------------
        root.addWidget(self._section_label(_("Lookaheads")))
        lh_area = QHBoxLayout()

        self._lh_listbox = QListWidget()
        self._lh_listbox.setMaximumHeight(100)
        self._lh_listbox.setStyleSheet(
            f"QListWidget {{ background: {AppStyle.BG_COLOR}; color: {AppStyle.FG_COLOR}; }}"
        )
        self._lh_listbox.doubleClicked.connect(self._edit_lookahead)
        lh_area.addWidget(self._lh_listbox, 1)

        lh_btns = QVBoxLayout()
        lh_btns.setSpacing(2)
        add_lh = QPushButton(_("Add Lookahead"))
        add_lh.clicked.connect(self._add_lookahead)
        lh_btns.addWidget(add_lh)
        edit_lh = QPushButton(_("Edit Lookahead"))
        edit_lh.clicked.connect(self._edit_lookahead)
        lh_btns.addWidget(edit_lh)
        rm_lh = QPushButton(_("Remove Lookahead"))
        rm_lh.clicked.connect(self._remove_lookahead)
        lh_btns.addWidget(rm_lh)
        lh_btns.addStretch()
        lh_area.addLayout(lh_btns)
        root.addLayout(lh_area)

        # ---- Directory profile management section ------------------------
        root.addWidget(self._section_label(_("Directory Profiles")))
        prof_area = QHBoxLayout()

        self._prof_listbox = QListWidget()
        self._prof_listbox.setMaximumHeight(100)
        self._prof_listbox.setStyleSheet(
            f"QListWidget {{ background: {AppStyle.BG_COLOR}; color: {AppStyle.FG_COLOR}; }}"
        )
        self._prof_listbox.doubleClicked.connect(self._edit_profile)
        prof_area.addWidget(self._prof_listbox, 1)

        prof_btns = QVBoxLayout()
        prof_btns.setSpacing(2)
        add_prof = QPushButton(_("Add Profile"))
        add_prof.clicked.connect(self._add_profile)
        prof_btns.addWidget(add_prof)
        edit_prof = QPushButton(_("Edit Profile"))
        edit_prof.clicked.connect(self._edit_profile)
        prof_btns.addWidget(edit_prof)
        rm_prof = QPushButton(_("Remove Profile"))
        rm_prof.clicked.connect(self._remove_profile)
        prof_btns.addWidget(rm_prof)
        prof_btns.addStretch()
        prof_area.addLayout(prof_btns)
        root.addLayout(prof_area)

        # ---- Prevalidations title + buttons ------------------------------
        pv_title_row = QHBoxLayout()
        pv_title_row.addWidget(self._section_label(_("Prevalidations")))
        add_pv = QPushButton(_("Add prevalidation"))
        add_pv.clicked.connect(lambda: self._open_modify_window())
        pv_title_row.addWidget(add_pv)
        clear_pv = QPushButton(_("Clear prevalidations"))
        clear_pv.clicked.connect(self._clear_all)
        pv_title_row.addWidget(clear_pv)
        pv_title_row.addStretch()
        root.addLayout(pv_title_row)

        # -- Enable prevalidations checkbox --------------------------------
        self._enable_pv_cb = QCheckBox(_("Enable Prevalidations"))
        self._enable_pv_cb.setChecked(config.enable_prevalidations)
        self._enable_pv_cb.stateChanged.connect(
            lambda state: setattr(config, "enable_prevalidations", bool(state))
        )
        root.addWidget(self._enable_pv_cb)

        # -- Scrollable prevalidation rows ---------------------------------
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet(
            f"QScrollArea {{ border: none; background: {AppStyle.BG_COLOR}; }}"
        )
        self._scroll_content = QWidget()
        self._scroll_layout = QVBoxLayout(self._scroll_content)
        self._scroll_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll_layout.setSpacing(2)
        self._scroll.setWidget(self._scroll_content)
        root.addWidget(self._scroll, 1)

        # Populate
        self._refresh_lh_listbox()
        self._refresh_prof_listbox()
        self._rebuild_pv_rows()

    # ------------------------------------------------------------------
    # Lookahead management
    # ------------------------------------------------------------------
    def _refresh_lh_listbox(self) -> None:
        self._lh_listbox.clear()
        for lh in Lookahead.lookaheads:
            text = _("{name} ({name_or_text}, threshold: {threshold:.2f})").format(
                name=lh.name,
                name_or_text=lh.name_or_text,
                threshold=lh.threshold,
            )
            self._lh_listbox.addItem(text)

    def _add_lookahead(self) -> None:
        from ui.compare.lookahead_window_qt import LookaheadWindow

        if PrevalidationsTab._lookahead_window is not None:
            try:
                PrevalidationsTab._lookahead_window.close()
            except Exception:
                pass
        PrevalidationsTab._lookahead_window = LookaheadWindow(
            self.window(), self._app_actions, self._refresh_lh_listbox
        )
        PrevalidationsTab._lookahead_window.show()

    def _edit_lookahead(self) -> None:
        from ui.compare.lookahead_window_qt import LookaheadWindow

        idx = self._lh_listbox.currentRow()
        if idx < 0 or idx >= len(Lookahead.lookaheads):
            return
        if PrevalidationsTab._lookahead_window is not None:
            try:
                PrevalidationsTab._lookahead_window.close()
            except Exception:
                pass
        PrevalidationsTab._lookahead_window = LookaheadWindow(
            self.window(),
            self._app_actions,
            self._refresh_lh_listbox,
            Lookahead.lookaheads[idx],
        )
        PrevalidationsTab._lookahead_window.show()

    def _remove_lookahead(self) -> None:
        idx = self._lh_listbox.currentRow()
        if idx < 0 or idx >= len(Lookahead.lookaheads):
            return
        lh = Lookahead.lookaheads[idx]
        used_by = [
            pv.name
            for pv in ClassifierActionsManager.prevalidations
            if lh.name in pv.lookahead_names
        ]
        if used_by:
            logger.warning(
                f"Lookahead {lh.name} is used by prevalidations: "
                f"{', '.join(used_by)}"
            )
        del Lookahead.lookaheads[idx]
        self._refresh_lh_listbox()
        if self._is_modify_window_valid():
            try:
                PrevalidationsTab._modify_window.refresh_lookahead_options()
            except Exception:
                PrevalidationsTab._modify_window = None

    # ------------------------------------------------------------------
    # Profile management
    # ------------------------------------------------------------------
    def _refresh_prof_listbox(self) -> None:
        self._prof_listbox.clear()
        for profile in DirectoryProfile.directory_profiles:
            n = len(profile.directories)
            word = _("directory") if n == 1 else _("directories")
            self._prof_listbox.addItem(f"{profile.name} ({n} {word})")

        if self._is_modify_window_valid():
            try:
                PrevalidationsTab._modify_window.refresh_profile_options()
            except Exception:
                PrevalidationsTab._modify_window = None

    def _add_profile(self) -> None:
        from ui.compare.directory_profile_window_qt import (
            DirectoryProfileWindow,
        )

        if PrevalidationsTab._profile_window is not None:
            try:
                PrevalidationsTab._profile_window.close()
            except Exception:
                pass
        PrevalidationsTab._profile_window = DirectoryProfileWindow(
            self.window(),
            self._app_actions,
            self._refresh_prof_listbox,
        )
        PrevalidationsTab._profile_window.show()

    def _edit_profile(self) -> None:
        from ui.compare.directory_profile_window_qt import (
            DirectoryProfileWindow,
        )

        idx = self._prof_listbox.currentRow()
        if idx < 0 or idx >= len(DirectoryProfile.directory_profiles):
            return
        if PrevalidationsTab._profile_window is not None:
            try:
                PrevalidationsTab._profile_window.close()
            except Exception:
                pass
        PrevalidationsTab._profile_window = DirectoryProfileWindow(
            self.window(),
            self._app_actions,
            self._refresh_prof_listbox,
            DirectoryProfile.directory_profiles[idx],
        )
        PrevalidationsTab._profile_window.show()

    def _remove_profile(self) -> None:
        idx = self._prof_listbox.currentRow()
        if idx < 0 or idx >= len(DirectoryProfile.directory_profiles):
            return
        profile = DirectoryProfile.directory_profiles[idx]
        DirectoryProfile.remove_profile(profile.name)
        self._refresh_prof_listbox()
        if self._is_modify_window_valid():
            try:
                PrevalidationsTab._modify_window.refresh_profile_options()
            except Exception:
                PrevalidationsTab._modify_window = None

    # ------------------------------------------------------------------
    # Prevalidation rows
    # ------------------------------------------------------------------
    def _rebuild_pv_rows(self) -> None:
        _clear_layout(self._scroll_layout)

        # Header
        hdr = QHBoxLayout()
        for text, stretch in [
            (_("Name"), 1), (_("Action"), 0), (_("Profile"), 0),
            (_("Active"), 0), ("", 0), ("", 0), ("", 0), ("", 0),
        ]:
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color: {AppStyle.FG_COLOR}; font-weight: bold;")
            hdr.addWidget(lbl, stretch)
        self._scroll_layout.addLayout(hdr)

        for idx, pv in enumerate(self._filtered):
            row = QHBoxLayout()

            name_lbl = QLabel(str(pv))
            name_lbl.setStyleSheet(f"color: {AppStyle.FG_COLOR};")
            name_lbl.setWordWrap(True)
            row.addWidget(name_lbl, 1)

            action_lbl = QLabel(pv.action.get_translation())
            action_lbl.setStyleSheet(f"color: {AppStyle.FG_COLOR};")
            row.addWidget(action_lbl)

            # Profile column
            if pv.profile_name:
                prof_text = pv.profile_name
            elif pv.profile:
                prof_text = pv.profile.name
            else:
                prof_text = _("(Global)")
            prof_lbl = QLabel(prof_text)
            prof_lbl.setStyleSheet(f"color: {AppStyle.FG_COLOR};")
            row.addWidget(prof_lbl)

            active_cb = QCheckBox()
            active_cb.setChecked(pv.is_active)
            active_cb.stateChanged.connect(
                lambda state, p=pv: setattr(p, "is_active", bool(state))
            )
            row.addWidget(active_cb)

            mod_btn = QPushButton(_("Modify"))
            mod_btn.setFixedWidth(55)
            mod_btn.clicked.connect(
                lambda _=False, p=pv: self._open_modify_window(p)
            )
            row.addWidget(mod_btn)

            copy_btn = QPushButton(_("Copy"))
            copy_btn.setFixedWidth(45)
            copy_btn.clicked.connect(
                lambda _=False, p=pv: self._open_copy_window(p)
            )
            row.addWidget(copy_btn)

            del_btn = QPushButton(_("Delete"))
            del_btn.setFixedWidth(52)
            del_btn.clicked.connect(
                lambda _=False, p=pv: self._delete(p)
            )
            row.addWidget(del_btn)

            down_btn = QPushButton(_("Move down"))
            down_btn.setFixedWidth(75)
            down_btn.clicked.connect(
                lambda _=False, i=idx, p=pv: self._move_down(i, p)
            )
            row.addWidget(down_btn)

            self._scroll_layout.addLayout(row)

        self._scroll_layout.addStretch()

    # ------------------------------------------------------------------
    # Prevalidation actions
    # ------------------------------------------------------------------
    def _open_modify_window(self, prevalidation=None) -> None:
        if PrevalidationsTab._modify_window is not None:
            try:
                PrevalidationsTab._modify_window.close()
            except Exception:
                pass
        PrevalidationsTab._modify_window = PrevalidationModifyWindow(
            self.window(),
            self._app_actions,
            self.refresh_prevalidations,
            prevalidation,
        )
        PrevalidationsTab._modify_window.show()

    def _open_copy_window(self, prevalidation) -> None:
        from ui.compare.classifier_action_copy_window_qt import (
            ClassifierActionCopyWindow,
        )

        ClassifierActionCopyWindow(
            self.window(),
            self._app_actions,
            prevalidation,
            source_type="prevalidation",
            refresh_classifier_actions_callback=None,
            refresh_prevalidations_callback=self.refresh_prevalidations,
        ).show()

    def refresh_prevalidations(self, prevalidation=None) -> None:
        if (
            prevalidation is not None
            and prevalidation not in ClassifierActionsManager.prevalidations
        ):
            ClassifierActionsManager.prevalidations.insert(0, prevalidation)
        self._filtered = ClassifierActionsManager.prevalidations[:]
        ClassifierActionsManager.prevalidated_cache.clear()
        ClassifierActionsManager.directories_to_exclude.clear()
        for pv in ClassifierActionsManager.prevalidations:
            if pv.is_move_action():
                ClassifierActionsManager.directories_to_exclude.append(
                    pv.action_modifier
                )
        self.refresh()

    def _delete(self, prevalidation) -> None:
        if (
            prevalidation is not None
            and prevalidation in ClassifierActionsManager.prevalidations
        ):
            ClassifierActionsManager.prevalidations.remove(prevalidation)
            ClassifierActionsManager._initialized_prevalidations.discard(
                prevalidation
            )
        self.refresh()

    def _move_down(self, idx: int, prevalidation) -> None:
        prevalidation.move_index(idx, 1)
        self.refresh()

    def _clear_all(self) -> None:
        ClassifierActionsManager.prevalidations.clear()
        self._filtered.clear()
        self.refresh()

    def refresh(self) -> None:
        self._filtered = ClassifierActionsManager.prevalidations[:]
        self._refresh_lh_listbox()
        self._refresh_prof_listbox()
        self._rebuild_pv_rows()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _section_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {AppStyle.FG_COLOR}; font-weight: bold; font-size: 13pt;"
        )
        return lbl


# ======================================================================
# Layout helper
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
