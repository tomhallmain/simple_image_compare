"""
MediaNavigator -- media browsing logic controller.

Owns the "what to show" without "how to show it" (that's MediaFrame).
Extracted from: show_prev_media, show_next_media, last_chosen_direction_func,
create_image, clear_image, go_to_file, go_to_file_by_index,
go_to_previous_image, home, page_up, page_down, show_searched_image,
toggle_image_view, get_active_media_filepath, toggle_slideshow.
"""

from __future__ import annotations

import os
import traceback
from typing import TYPE_CHECKING, Optional

from utils.config import config
from utils.constants import Direction, Mode
from utils.logging_setup import get_logger
from utils.translations import I18N
from utils.utils import Utils

if TYPE_CHECKING:
    from compare.compare_manager import CompareManager
    from files.file_browser import FileBrowser, SortBy
    from ui.app_window.app_window import AppWindow
    from ui.app_window.media_frame import MediaFrame

_ = I18N._
logger = get_logger("media_navigator")


class MediaNavigator:
    """
    Controls which media file is displayed and provides navigation
    (prev, next, home, page up/down, go-to-file, etc.).
    """

    def __init__(
        self,
        app_window: AppWindow,
        file_browser: FileBrowser,
        compare_manager: CompareManager,
        media_frame: MediaFrame,
    ):
        self._app = app_window
        self._fb = file_browser
        self._cm = compare_manager
        self._mf = media_frame

    # ==================================================================
    # Navigation
    # ==================================================================
    def show_prev_media(self, event=None, show_alert: bool = True) -> bool:
        """
        Navigate to the previous media file.

        In BROWSE mode, walks backward through the file browser, skipping
        images the compare manager says to skip. In compare modes, delegates
        to ``CompareManager.show_prev_media``.

        Ported from App.show_prev_media.
        """
        self._app.direction = Direction.BACKWARD

        if self._app.mode == Mode.BROWSE:
            start_file = self._fb.current_file()
            previous_file = self._fb.previous_file()
            if self._app.img_path == previous_file:
                return True  # already at this file (refresh case)
            while self._cm.skip_image(previous_file) and previous_file != start_file:
                previous_file = self._fb.previous_file()
            try:
                self.create_image(previous_file)
                return True
            except Exception as e:
                self._app.notification_ctrl.handle_error(str(e), title="Exception")
                return False

        return self._cm.show_prev_media(show_alert=show_alert)

    def show_next_media(self, event=None, show_alert: bool = True) -> bool:
        """
        Navigate to the next media file.

        Ported from App.show_next_media.
        """
        self._app.direction = Direction.FORWARD

        if self._app.mode == Mode.BROWSE:
            start_file = self._fb.current_file()
            next_file = self._fb.next_file()
            if self._app.img_path == next_file:
                return True  # already at this file (refresh case)
            while self._cm.skip_image(next_file) and next_file != start_file:
                next_file = self._fb.next_file()
            try:
                self.create_image(next_file)
                return True
            except Exception as e:
                traceback.print_exc()
                self._app.notification_ctrl.handle_error(str(e), title="Exception")
                return False

        return self._cm.show_next_media(show_alert=show_alert)

    def last_chosen_direction_func(self) -> None:
        """
        Repeat the last navigation direction.

        Ported from App.last_chosen_direction_func.
        """
        if self._app.direction == Direction.BACKWARD:
            self.show_prev_media()
        elif self._app.direction == Direction.FORWARD:
            self.show_next_media()
        else:
            raise Exception(f"Direction was improperly set. Direction was {self._app.direction}")

    def home(self, event=None, last_file: bool = False) -> None:
        """
        Jump to the first or last file.

        Ported from App.home.
        """
        from ui.files.marked_file_mover_qt import MarkedFiles

        if self._app.mode == Mode.BROWSE:
            current_file = self.get_active_media_filepath()
            self._fb.refresh()
            if current_file is None:
                raise Exception("No active image file.")

            if last_file:
                target = self._fb.last_file()
                while self._cm.skip_image(target) and target != current_file:
                    target = self._fb.previous_file()
                self.create_image(target)
                if (len(MarkedFiles.file_marks) == 1
                        and self._fb.has_file(MarkedFiles.file_marks[0])):
                    self._app.file_marks_ctrl.add_all_marks_from_last_or_current_group()
                self._app.direction = Direction.BACKWARD
            else:
                target = self._fb.next_file()
                while self._cm.skip_image(target) and target != current_file:
                    target = self._fb.next_file()
                self.create_image(target)

        elif self._cm.has_compare():
            self._app.direction = Direction.FORWARD
            self._cm.current_group_index = 0
            self._cm.match_index = 0
            self._cm.set_current_group()

    def page_up(self, event=None) -> None:
        """
        Jump backward by a page of files.

        Ported from App.page_up.
        """
        current_image = self.get_active_media_filepath()
        if self._app.mode == Mode.BROWSE:
            prev_file = self._fb.page_up()
        else:
            prev_file = self._cm.page_up()

        while self._cm.skip_image(prev_file) and prev_file != current_image:
            if self._app.mode == Mode.BROWSE:
                prev_file = self._fb.previous_file()
            else:
                prev_file = self._cm._get_prev_image()

        self.create_image(prev_file)
        self._app.direction = Direction.BACKWARD

    def page_down(self, event=None) -> None:
        """
        Jump forward by a page of files.

        Ported from App.page_down.
        """
        current_image = self.get_active_media_filepath()
        if self._app.mode == Mode.BROWSE:
            next_file = self._fb.page_down()
        else:
            next_file = self._cm.page_down()

        while self._cm.skip_image(next_file) and next_file != current_image:
            if self._app.mode == Mode.BROWSE:
                next_file = self._fb.next_file()
            else:
                next_file = self._cm._get_next_image()

        self.create_image(next_file)
        self._app.direction = Direction.FORWARD

    # ==================================================================
    # Go-to-file
    # ==================================================================
    def go_to_file(
        self,
        event=None,
        search_text: str = "",
        retry_with_delay: int = 0,
        exact_match: bool = True,
        closest_sort_by: Optional[SortBy] = None,
    ) -> bool:
        """
        Navigate to a specific file by name or path.

        Searches the current window first, then other open windows. If the
        file is not found anywhere and ``search_text`` is a valid file path,
        opens it in a temporary canvas.

        Ported from App.go_to_file.
        """
        from ui.image.image_details_qt import ImageDetails
        from ui.app_window.window_manager import WindowManager

        original_search_text = search_text
        resolved_path = Utils.get_valid_file(self._app.get_base_dir(), original_search_text)
        original_search_text_is_file = resolved_path and os.path.isfile(resolved_path)
        exact_match = exact_match or original_search_text_is_file
        if not exact_match:
            search_text = os.path.basename(search_text)

        # --- Search in current window ---
        if self._app.mode == Mode.BROWSE:
            self._fb.refresh()
            if config.debug:
                logger.debug(f"Finding file in current window: {search_text}, closest sort by: {closest_sort_by}")
            image_path = self._fb.find(
                search_text=search_text,
                retry_with_delay=retry_with_delay,
                exact_match=exact_match,
                closest_sort_by=closest_sort_by,
            )
            if image_path:
                self.create_image(image_path)
                return True
        else:
            image_path, group_indexes = self._cm.find_file_after_comparison(
                search_text, exact_match=exact_match
            )
            if group_indexes:
                self._cm.current_group_index = group_indexes[0]
                self._cm.set_current_group(start_match_index=group_indexes[1])
                return True

        # --- Search in other open windows ---
        for window in WindowManager.get_open_windows():
            if window.window_id == self._app.window_id:
                continue

            if window.mode == Mode.BROWSE:
                window.file_browser.refresh()
                found_path = window.file_browser.find(
                    search_text=search_text,
                    retry_with_delay=retry_with_delay,
                    exact_match=exact_match,
                    closest_sort_by=closest_sort_by,
                )
                if found_path:
                    window.raise_()
                    window.activateWindow()
                    window.media_navigator.create_image(found_path)
                    return True
            else:
                found_path, group_indexes = window.compare_manager.find_file_after_comparison(
                    search_text, exact_match=exact_match
                )
                if found_path and group_indexes:
                    window.compare_manager.current_group_index = group_indexes[0]
                    window.compare_manager.set_current_group(start_match_index=group_indexes[1])
                    window.raise_()
                    window.activateWindow()
                    return True
                # If not found in compare results, search the full directory
                window.file_browser.refresh()
                found_path = window.file_browser.find(
                    search_text=search_text,
                    retry_with_delay=retry_with_delay,
                    exact_match=exact_match,
                    closest_sort_by=closest_sort_by,
                )
                if found_path:
                    ImageDetails.open_temp_image_canvas(
                        master=self._app, image_path=found_path,
                        app_actions=self._app.app_actions, skip_get_window_check=True,
                    )
                    return True

        # --- File is a valid path on disk → open in temp canvas ---
        if original_search_text_is_file:
            ImageDetails.open_temp_image_canvas(
                master=self._app, image_path=original_search_text,
                app_actions=self._app.app_actions, skip_get_window_check=True,
            )
            return True

        # --- Not found anywhere ---
        self._app.notification_ctrl.alert(
            _("File not found"),
            _('No file was found for the search text: "{0}"').format(search_text),
        )
        return False

    def go_to_file_by_index(self, index: int) -> bool:
        """
        Navigate to a file by its index (1-based) in the file browser.

        Ported from App.go_to_file_by_index.
        """
        if self._app.mode != Mode.BROWSE:
            self._app.notification_ctrl.alert(
                _("Index navigation not available"),
                _("Index navigation is only available in BROWSE mode."),
            )
            return False

        try:
            self._fb.refresh()
            file_path = self._fb.go_to_index(index)
            if file_path:
                self.create_image(file_path)
                return True
        except ValueError as e:
            self._app.notification_ctrl.alert(_("Invalid index"), str(e))
            return False
        except Exception as e:
            self._app.notification_ctrl.handle_error(str(e), title="Go To Index Error")
            return False

        return False

    def go_to_previous_image(self, event=None) -> None:
        """Navigate back to the previously viewed image."""
        if self._app.prev_img_path is not None:
            self.go_to_file(event=event, search_text=self._app.prev_img_path)

    # ==================================================================
    # Display
    # ==================================================================
    def create_image(self, image_path: str, extra_text: Optional[str] = None) -> None:
        """
        Show an image in the main content pane of the UI.

        Ported from App.create_image. Updates the sidebar label, the
        internal path state, and refreshes the image-details window if open.
        """
        if not image_path:
            return
        self._mf.show_image(image_path)

        relative_filepath, basename = Utils.get_relative_dirpath_split(
            self._app.base_dir, image_path
        )
        self._app.prev_img_path = self._app.img_path
        self._app.img_path = image_path

        text = basename if relative_filepath == "" else relative_filepath + "\n" + basename
        text = Utils._wrap_text_to_fit_length(text, 30)
        if extra_text is not None:
            text += "\n" + extra_text
        self._app.sidebar_panel.update_current_image_label(text)

        # Auto-refresh the image details window if it is open
        if self._app.app_actions.image_details_window() is not None:
            self._app.window_launcher.open_media_details(manually_keyed=False)

    def clear_image(self) -> None:
        """
        Clear the currently displayed media.

        Ported from App.clear_image.
        """
        self._mf.clear()
        self._app.sidebar_panel.update_current_image_label("")
        self._app.img_path = None

    def show_searched_image(self) -> None:
        """
        Display the image found by the last search.

        Ported from App.show_searched_image.
        """
        search_path = self._cm.search_image_full_path
        if config.debug:
            logger.debug(f"Search image full path: {search_path}")
        if search_path is not None and search_path.strip() != "":
            if os.path.isfile(search_path):
                self.create_image(search_path, extra_text="(search image)")
            else:
                logger.warning(search_path)
                self._app.notification_ctrl.handle_error(
                    _("Somehow, the search file is invalid")
                )

    def toggle_image_view(self) -> None:
        """
        While in search mode, toggle between the search image and the results.

        Ported from App.toggle_image_view.
        """
        if self._app.mode != Mode.SEARCH:
            return

        if self._app.is_toggled_view_matches:
            self.show_searched_image()
        else:
            self.create_image(self._cm.current_match())

        self._app.is_toggled_view_matches = not self._app.is_toggled_view_matches

    def set_toggled_view_matches(self) -> None:
        """Set the toggled view to show matches."""
        self._app.is_toggled_view_matches = True

    # ==================================================================
    # Slideshow
    # ==================================================================
    def toggle_slideshow(self, event=None) -> None:
        """
        Toggle the slideshow on or off.

        Ported from App.toggle_slideshow. Uses QTimer via the cache
        controller's file-check timer rather than a dedicated async thread.
        """
        from utils.running_tasks_registry import start_thread

        self._app.slideshow_config.toggle_slideshow()
        if self._app.slideshow_config.show_new_images:
            message = _("Slideshow for new images started")
        elif self._app.slideshow_config.slideshow_running:
            message = _("Slideshow started")
            # The do_slideshow periodic is driven by the slideshow_config
            # which is already checked inside the file-check timer.
            # For a dedicated slideshow timer we would need a separate QTimer,
            # but the original code just starts a thread. For now, keep the
            # same pattern by delegating to the existing periodic mechanism.
        else:
            message = _("Slideshows ended")
        self._app.notification_ctrl.toast(message)

    # ==================================================================
    # Queries
    # ==================================================================
    def get_active_media_filepath(self) -> Optional[str]:
        """
        Return the path of the currently displayed media file.

        Ported from App.get_active_media_filepath.
        """
        # In browse mode, prefer the file_browser cursor
        if self._app.mode == Mode.BROWSE:
            return self._fb.current_file()

        if self.is_toggled_search_image():
            filepath = self._cm.search_image_full_path
        else:
            filepath = self._cm.current_match()

        return Utils.get_valid_file(self._app.get_base_dir(), filepath)

    def is_toggled_search_image(self) -> bool:
        """Return True if the toggled view is showing the search image."""
        return self._app.mode == Mode.SEARCH and not self._app.is_toggled_view_matches
