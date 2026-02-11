"""
PySide6 port of compare/classifier_management_window.py.

Contains two classes:
  - ClassifierActionModifyWindow  -- base modify dialog for classifier
    actions and prevalidations (shared fields, prototype support).
  - ClassifierManagementWindow    -- tabbed management window hosting
    ClassifierActionsTab and PrevalidationsTab.

Non-UI imports:
  - ClassifierAction, ClassifierActionsManager
    from compare.classifier_actions_manager (reuse policy)
  - image_classifier_manager
    from image.image_classifier_manager (reuse policy)
"""

from __future__ import annotations

import os
from typing import Callable, Optional

from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from compare.classifier_actions_manager import (
    ClassifierAction,
    ClassifierActionsManager,
)
from image.image_classifier_manager import image_classifier_manager
from lib.multi_display_qt import SmartDialog
from ui.app_style import AppStyle
from utils.config import config
from utils.translations import I18N

_ = I18N._


class ClassifierActionModifyWindow(SmartDialog):
    """
    Base modify dialog for classifier actions and prevalidations.

    Contains all shared UI elements: name, classifier model selector,
    action type, threshold, prototype management, etc.

    Subclassed by PrevalidationModifyWindow (adds lookahead / profile
    specific fields).
    """

    _instance: Optional[ClassifierActionModifyWindow] = None

    def __init__(
        self,
        parent: QWidget,
        app_actions,
        refresh_callback: Callable,
        classifier_action: ClassifierAction,
        window_title: Optional[str] = None,
        name_label_text: Optional[str] = None,
        new_name_default: Optional[str] = None,
        dimensions: str = "600x600",
    ) -> None:
        super().__init__(
            parent=parent,
            position_parent=parent,
            title=window_title or _("Modify Classifier Action"),
            geometry=dimensions,
        )
        self._app_actions = app_actions
        self._refresh_callback = refresh_callback
        self._classifier_action = classifier_action
        # TODO: build shared fields UI

    def add_specific_fields(self, row: int) -> int:
        """Override in subclasses to add type-specific fields. Returns next row."""
        return row

    def closeEvent(self, event) -> None:  # noqa: N802
        ClassifierActionModifyWindow._instance = None
        super().closeEvent(event)


class ClassifierManagementWindow(SmartDialog):
    """
    Tabbed management window hosting ClassifierActionsTab and
    PrevalidationsTab via QTabWidget.
    """

    _instance: Optional[ClassifierManagementWindow] = None

    def __init__(self, parent: QWidget, app_actions, base_dir: str = ".") -> None:
        super().__init__(
            parent=parent,
            position_parent=parent,
            title=_("Classifier Management"),
            geometry="800x700",
        )
        self._app_actions = app_actions
        self._base_dir = base_dir

        root = QVBoxLayout(self)
        self._tabs = QTabWidget()
        root.addWidget(self._tabs)
        # TODO: add ClassifierActionsTab and PrevalidationsTab pages

    @classmethod
    def show_window(cls, parent: QWidget, app_actions, base_dir: str = ".") -> None:
        if cls._instance is not None:
            try:
                if cls._instance.isVisible():
                    cls._instance.raise_()
                    cls._instance.activateWindow()
                    return
            except Exception:
                pass
        cls._instance = cls(parent, app_actions, base_dir)
        cls._instance.show()

    def closeEvent(self, event) -> None:  # noqa: N802
        ClassifierManagementWindow._instance = None
        super().closeEvent(event)
