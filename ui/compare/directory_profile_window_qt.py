"""
PySide6 port of the DirectoryProfileWindow from compare/directory_profile.py.

Only the UI class is ported here. The non-UI ``DirectoryProfile`` data class
is imported from the original module per the reuse policy.

Non-UI imports:
  - DirectoryProfile from compare.directory_profile (reuse policy)
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtWidgets import QFileDialog, QVBoxLayout, QWidget

from compare.directory_profile import DirectoryProfile
from lib.multi_display_qt import SmartDialog
from ui.app_style import AppStyle
from utils.config import config
from utils.translations import I18N
from utils.logging_setup import get_logger

_ = I18N._
logger = get_logger("directory_profile_window_qt")


class DirectoryProfileWindow(SmartDialog):
    """
    Dialog for managing a DirectoryProfile (list of directories).

    Provides a list view of directories in the profile, with controls
    to add (via QFileDialog), remove, and rename.
    """

    _instance: Optional[DirectoryProfileWindow] = None

    def __init__(
        self,
        parent: QWidget,
        app_actions,
        directory_profile: Optional[DirectoryProfile] = None,
        refresh_callback: Optional[Callable] = None,
    ) -> None:
        profile_name = directory_profile.name if directory_profile else _("New Profile")
        super().__init__(
            parent=parent,
            position_parent=parent,
            title=_("Directory Profile: {0}").format(profile_name),
            geometry="600x500",
        )
        self._app_actions = app_actions
        self._directory_profile = directory_profile or DirectoryProfile()
        self._refresh_callback = refresh_callback
        # TODO: build directory list + add/remove/rename controls

    @classmethod
    def show_window(
        cls,
        parent: QWidget,
        app_actions,
        directory_profile=None,
        refresh_callback=None,
    ) -> None:
        if cls._instance is not None:
            try:
                if cls._instance.isVisible():
                    cls._instance.raise_()
                    cls._instance.activateWindow()
                    return
            except Exception:
                pass
        cls._instance = cls(parent, app_actions, directory_profile, refresh_callback)
        cls._instance.show()

    def closeEvent(self, event) -> None:  # noqa: N802
        DirectoryProfileWindow._instance = None
        super().closeEvent(event)
