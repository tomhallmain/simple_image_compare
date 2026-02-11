"""
PySide6 port of compare/classifier_actions_tab.py -- ClassifierActionsTab.

Tab-page QWidget listing classifier actions with buttons for add / modify /
delete / copy / run, plus batch validation controls.

Non-UI imports:
  - ClassifierAction, ClassifierActionsManager
    from compare.classifier_actions_manager (reuse policy)
  - DirectoryProfile from compare.directory_profile (reuse policy)
"""

from __future__ import annotations

import os
from typing import Callable, Optional

from PySide6.QtWidgets import QVBoxLayout, QWidget

from compare.classifier_actions_manager import (
    ClassifierAction,
    ClassifierActionsManager,
)
from compare.directory_profile import DirectoryProfile
from ui.app_style import AppStyle
from utils.config import config
from utils.logging_setup import get_logger
from utils.translations import I18N

_ = I18N._
logger = get_logger("classifier_actions_tab_qt")


class ClassifierActionsTab(QWidget):
    """
    Tab content widget for managing classifier actions.

    Can be embedded inside a QTabWidget (ClassifierManagementWindow)
    or used standalone.
    """

    BATCH_VALIDATION_MAX_IMAGES = 40000

    def __init__(
        self,
        parent: QWidget,
        app_actions,
        base_dir: str = ".",
    ) -> None:
        super().__init__(parent)
        self._app_actions = app_actions
        self._base_dir = base_dir
        # TODO: build action list + controls

    # ------------------------------------------------------------------
    # Static action runner (non-UI logic, kept here for API compat)
    # ------------------------------------------------------------------
    @staticmethod
    def run_classifier_action(
        classifier_action: ClassifierAction,
        directory_paths: list[str],
        hide_callback: Callable,
        notify_callback: Callable,
        add_mark_callback: Optional[Callable] = None,
        profile_name_or_path: Optional[str] = None,
    ) -> None:
        """Run a classifier action across *directory_paths*."""
        # TODO: port logic from original
        pass
