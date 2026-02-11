"""
PySide6 port of compare/compare_settings_window.py -- CompareSettingsWindow.

Singleton dialog per CompareManager for configuring comparison modes,
filters, and composite search settings.

Non-UI imports:
  - CompareManager, CombinationLogic, SizeFilter, ModelFilter
    from compare.compare_manager (reuse policy)
"""

from __future__ import annotations

from typing import Dict

from PySide6.QtWidgets import QWidget

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


class CompareSettingsWindow(SmartDialog):
    """Window for configuring comparison modes, filters, and composite search settings."""

    _open_windows: Dict[object, CompareSettingsWindow] = {}

    def __init__(self, parent: QWidget, compare_manager: CompareManager) -> None:
        super().__init__(
            parent=parent,
            position_parent=parent,
            title=_("Compare Settings"),
            geometry="1000x700",
        )
        self._compare_manager = compare_manager
        # TODO: build full UI

    @classmethod
    def show_window(cls, parent: QWidget, compare_manager: CompareManager) -> None:
        if compare_manager in cls._open_windows:
            win = cls._open_windows[compare_manager]
            try:
                if win.isVisible():
                    win.raise_()
                    win.activateWindow()
                    return
            except Exception:
                pass
        win = cls(parent, compare_manager)
        cls._open_windows[compare_manager] = win
        win.show()

    def closeEvent(self, event) -> None:  # noqa: N802
        self._open_windows.pop(self._compare_manager, None)
        super().closeEvent(event)
