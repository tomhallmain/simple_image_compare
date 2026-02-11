"""
PySide6 port of compare/classifier_action_copy_window.py --
ClassifierActionCopyWindow.

Intermediary dialog for copying ClassifierAction and Prevalidation objects
into new instances of either type.

Non-UI imports:
  - ClassifierAction, Prevalidation, ClassifierActionsManager
    from compare.classifier_actions_manager (reuse policy)
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtWidgets import QVBoxLayout, QWidget

from compare.classifier_actions_manager import (
    ClassifierAction,
    Prevalidation,
    ClassifierActionsManager,
)
from ui.compare.classifier_management_window_qt import (
    ClassifierActionModifyWindow,
    ClassifierManagementWindow,
)
from lib.multi_display_qt import SmartDialog
from ui.app_style import AppStyle
from utils.constants import ClassifierActionClass
from utils.config import config
from utils.translations import I18N

_ = I18N._


class ClassifierActionCopyWindow(SmartDialog):
    """
    Intermediary dialog for copying ClassifierAction / Prevalidation objects.

    Allows:
      - ClassifierAction  -> new ClassifierAction
      - Prevalidation     -> new Prevalidation
      - ClassifierAction  -> new Prevalidation
      - Prevalidation     -> new ClassifierAction
    """

    _instance: Optional[ClassifierActionCopyWindow] = None

    def __init__(
        self,
        parent: QWidget,
        app_actions,
        source_item,
        source_type: str = "auto",
        refresh_classifier_actions_callback: Optional[Callable] = None,
        refresh_prevalidations_callback: Optional[Callable] = None,
    ) -> None:
        super().__init__(
            parent=parent,
            position_parent=parent,
            title=_("Copy Classifier Action"),
            geometry="500x400",
        )
        self._app_actions = app_actions
        self._source_item = source_item
        self._source_type = source_type
        self._refresh_ca_cb = refresh_classifier_actions_callback
        self._refresh_pv_cb = refresh_prevalidations_callback
        # TODO: build copy UI (name field, target type selector, confirm button)

    def closeEvent(self, event) -> None:  # noqa: N802
        ClassifierActionCopyWindow._instance = None
        super().closeEvent(event)
