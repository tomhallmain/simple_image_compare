"""
PySide6 port of compare/prevalidations_tab.py.

Contains two classes:
  - PrevalidationModifyWindow  -- subclass of ClassifierActionModifyWindow
    adding lookahead and directory-profile fields.
  - PrevalidationsTab          -- tab-page QWidget listing prevalidations
    with add / modify / delete / copy / run controls.

Non-UI imports:
  - Prevalidation, ClassifierActionsManager
    from compare.classifier_actions_manager (reuse policy)
  - Lookahead from compare.lookahead (reuse policy)
  - DirectoryProfile from compare.directory_profile (reuse policy)
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QVBoxLayout, QWidget

from compare.classifier_actions_manager import (
    Prevalidation,
    ClassifierActionsManager,
)
from compare.directory_profile import DirectoryProfile
from compare.lookahead import Lookahead
from ui.compare.classifier_management_window_qt import ClassifierActionModifyWindow
from ui.app_style import AppStyle
from utils.config import config
from utils.logging_setup import get_logger
from utils.translations import I18N

_ = I18N._
logger = get_logger("prevalidations_tab_qt")


class PrevalidationModifyWindow(ClassifierActionModifyWindow):
    """Modify dialog for Prevalidation objects, adding lookahead/profile fields."""

    _instance: Optional[PrevalidationModifyWindow] = None

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
        # TODO: add prevalidation-specific fields (lookaheads, profile)

    def add_specific_fields(self, row: int) -> int:
        """Add prevalidation-specific lookahead and profile selectors."""
        # TODO: implement
        return row

    def closeEvent(self, event) -> None:  # noqa: N802
        PrevalidationModifyWindow._instance = None
        super().closeEvent(event)


class PrevalidationsTab(QWidget):
    """
    Tab content widget for managing prevalidations.

    Can be embedded inside a QTabWidget (ClassifierManagementWindow)
    or used standalone.
    """

    def __init__(
        self,
        parent: QWidget,
        app_actions,
        base_dir: str = ".",
    ) -> None:
        super().__init__(parent)
        self._app_actions = app_actions
        self._base_dir = base_dir
        # TODO: build prevalidation list + controls

    @staticmethod
    def prevalidate(
        app_actions,
        base_dir: str,
        add_mark_callback=None,
    ) -> bool:
        """Run prevalidations and return True if comparison should proceed."""
        # TODO: port logic from original
        return True
