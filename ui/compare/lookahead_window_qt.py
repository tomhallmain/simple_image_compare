"""
PySide6 port of the LookaheadWindow from compare/lookahead.py.

Only the UI class is ported here. The non-UI ``Lookahead`` data class
is imported from the original module per the reuse policy.

Non-UI imports:
  - Lookahead from compare.lookahead (reuse policy)
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtWidgets import QVBoxLayout, QWidget

from compare.lookahead import Lookahead
from lib.multi_display_qt import SmartDialog
from ui.app_style import AppStyle
from utils.config import config
from utils.translations import I18N
from utils.logging_setup import get_logger

_ = I18N._
logger = get_logger("lookahead_window_qt")


class LookaheadWindow(SmartDialog):
    """
    Dialog for managing the shared list of Lookahead objects.

    Provides a list view of all ``Lookahead.lookaheads``, with controls
    to add, modify, and remove entries.
    """

    _instance: Optional[LookaheadWindow] = None

    def __init__(
        self,
        parent: QWidget,
        app_actions,
        refresh_callback: Optional[Callable] = None,
    ) -> None:
        super().__init__(
            parent=parent,
            position_parent=parent,
            title=_("Manage Lookaheads"),
            geometry="600x500",
        )
        self._app_actions = app_actions
        self._refresh_callback = refresh_callback
        # TODO: build lookahead list + add/modify/remove controls

    @classmethod
    def show_window(cls, parent: QWidget, app_actions, refresh_callback=None) -> None:
        if cls._instance is not None:
            try:
                if cls._instance.isVisible():
                    cls._instance.raise_()
                    cls._instance.activateWindow()
                    return
            except Exception:
                pass
        cls._instance = cls(parent, app_actions, refresh_callback)
        cls._instance.show()

    def closeEvent(self, event) -> None:  # noqa: N802
        LookaheadWindow._instance = None
        super().closeEvent(event)
