"""
PySide6 port of files/marked_file_mover.py -- MarkedFiles.

Fully self-contained: all class-level state, persistence, action runners,
core file-operation logic, and the two-mode window UI (GUI with scrollable
directory list, and non-GUI translucent mode).

Key improvements over original:
  - Single-column scrollable list replaces the multi-column grid.
  - Per-directory **Remove** button for easy target removal.
  - No keystroke buffering needed (Qt constructor completes before show).

``Action`` data class is imported from the original module (non-UI reuse
policy).  ``FileActionsWindow`` is imported from the Qt port.
"""

from __future__ import annotations

import os
import re
import sys
from datetime import datetime
from typing import Callable, Optional, Tuple

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from files.file_actions_window import Action
from image.frame_cache import FrameCache
from image.image_ops import ImageOps
from lib.multi_display_qt import SmartDialog
from ui.app_style import AppStyle
from ui.auth.password_utils import require_password
from ui.files.file_actions_window_qt import FileActionsWindow
from utils.app_actions import AppActions
from utils.app_info_cache import app_info_cache
from utils.config import config
from utils.constants import Mode, ActionType, ProtectedActions
from utils.logging_setup import get_logger
from utils.translations import I18N
from utils.utils import Utils

_ = I18N._
logger = get_logger("marked_file_mover_qt")


class MarkedFiles(SmartDialog):
    """
    Move / copy / delete marked files to target directories.

    Two window modes:

    * **GUI** (``is_gui=True``, Ctrl+M): full action bar + scrollable
      directory list.
    * **Translucent** (``is_gui=False``, Ctrl+K): tiny semi-transparent
      dialog with no widgets; the user types to filter, presses Enter.
    """

    # ==================================================================
    # Class-level shared state
    # ==================================================================
    file_marks: list[str] = []
    mark_cursor: int = -1
    mark_target_dirs: list[str] = []
    previous_marks: list[str] = []
    last_moved_image: Optional[str] = None
    last_set_target_dir: Optional[str] = None
    file_browser = None  # FileBrowser for test_is_in_directory

    _current_window: Optional[MarkedFiles] = None

    is_performing_action: bool = False
    is_cancelled_action: bool = False
    delete_lock: bool = False
    gimp_opened_in_last_action: bool = False

    MAX_HEIGHT: int = 900
    COL_0_WIDTH: int = 600

    # ==================================================================
    # Static persistence
    # ==================================================================
    @staticmethod
    def load_target_dirs() -> None:
        MarkedFiles.set_target_dirs(
            app_info_cache.get_meta("marked_file_target_dirs", default_val=[])
        )

    @staticmethod
    def set_target_dirs(target_dirs: list[str]) -> None:
        MarkedFiles.mark_target_dirs = target_dirs
        for d in MarkedFiles.mark_target_dirs[:]:
            if not os.path.isdir(d):
                if sys.platform == "win32" and not d.startswith("C:\\"):
                    base_dir = d.split("\\")[0] + "\\"
                    if not os.path.isdir(base_dir):
                        continue
                MarkedFiles.mark_target_dirs.remove(d)
                logger.warning(f"Removed stale target directory reference: {d}")

    @staticmethod
    def store_target_dirs() -> None:
        app_info_cache.set_meta(
            "marked_file_target_dirs", MarkedFiles.mark_target_dirs
        )

    # ==================================================================
    # Static mark management
    # ==================================================================
    @staticmethod
    def add_mark_if_not_present(filepath: str) -> bool:
        if filepath not in MarkedFiles.file_marks:
            MarkedFiles.file_marks.append(filepath)
            return True
        return False

    @staticmethod
    def set_delete_lock(delete_lock: bool = True) -> None:
        MarkedFiles.delete_lock = delete_lock

    @staticmethod
    def clear_file_marks(toast_callback) -> None:
        MarkedFiles.file_marks = []
        toast_callback(_("Marks cleared."))

    @staticmethod
    def set_current_marks_from_previous(toast_callback) -> None:
        for f in MarkedFiles.previous_marks:
            if f not in MarkedFiles.file_marks and os.path.exists(f):
                MarkedFiles.file_marks.append(f)
        toast_callback(
            _("Set current marks from previous.")
            + "\n"
            + _("Total set: {0}").format(len(MarkedFiles.file_marks))
        )

    @staticmethod
    def handle_file_removal(filepath: str) -> None:
        if filepath in MarkedFiles.file_marks:
            filepath_index = MarkedFiles.file_marks.index(filepath)
            if filepath_index < MarkedFiles.mark_cursor:
                MarkedFiles.mark_cursor -= 1
            elif filepath_index == len(MarkedFiles.file_marks) - 1:
                MarkedFiles.mark_cursor = 0
            MarkedFiles.file_marks.remove(filepath)

    @staticmethod
    def remove_marks_for_base_dir(base_dir, app_actions) -> None:
        if len(MarkedFiles.file_marks) > 0 and base_dir and base_dir != "":
            removed_count = 0
            i = 0
            while i < len(MarkedFiles.file_marks):
                marked_file = MarkedFiles.file_marks[i]
                if os.path.dirname(marked_file) == base_dir:
                    MarkedFiles.file_marks.remove(marked_file)
                    removed_count += 1
                    if MarkedFiles.mark_cursor >= len(MarkedFiles.file_marks):
                        MarkedFiles.mark_cursor = 0
                    elif MarkedFiles.mark_cursor > i:
                        MarkedFiles.mark_cursor -= 1
                else:
                    i += 1
            if len(MarkedFiles.file_marks) == 0:
                app_actions.toast(_("Marks cleared."))
            elif removed_count > 0:
                app_actions.toast(
                    _("Removed {0} marks").format(removed_count)
                )

    # ==================================================================
    # Static action runners
    # ==================================================================
    @staticmethod
    def run_previous_action(app_actions, current_image=None):
        previous_action = FileActionsWindow.get_history_action(start_index=0)
        if previous_action is None:
            return False, False
        return MarkedFiles.move_marks_to_dir_static(
            app_actions,
            target_dir=previous_action.target,
            move_func=previous_action.action,
            single_image=(len(MarkedFiles.file_marks) == 1),
            current_image=current_image,
        )

    @staticmethod
    def run_penultimate_action(app_actions, current_image=None):
        penultimate_action = FileActionsWindow.get_history_action(start_index=1)
        if penultimate_action is None:
            return False, False
        return MarkedFiles.move_marks_to_dir_static(
            app_actions,
            target_dir=penultimate_action.target,
            move_func=penultimate_action.action,
            single_image=(len(MarkedFiles.file_marks) == 1),
            current_image=current_image,
        )

    @staticmethod
    def run_permanent_action(app_actions, current_image=None):
        if not FileActionsWindow.permanent_action:
            app_actions.toast(_("NO_MARK_TARGET_SET"))
            return False, False
        return MarkedFiles.move_marks_to_dir_static(
            app_actions,
            target_dir=FileActionsWindow.permanent_action.target,
            move_func=FileActionsWindow.permanent_action.action,
            single_image=(len(MarkedFiles.file_marks) == 1),
            current_image=current_image,
        )

    @staticmethod
    def run_hotkey_action(
        app_actions,
        current_image=None,
        number: int = -1,
        shift_key_pressed: bool = False,
    ):
        assert number in range(10)
        if number not in FileActionsWindow.hotkey_actions:
            app_actions.toast(
                _("NO_HOTKEY_ACTION_SET").format(number, number)
            )
            return False, False
        file_action = FileActionsWindow.hotkey_actions[number]
        return MarkedFiles.move_marks_to_dir_static(
            app_actions,
            target_dir=file_action.target,
            move_func=file_action.get_action(do_flip=shift_key_pressed),
            single_image=(len(MarkedFiles.file_marks) == 1),
            current_image=current_image,
        )

    # ==================================================================
    # Static target directory helper
    # ==================================================================
    @staticmethod
    def get_target_directory(
        target_dir, starting_target, app_actions, parent=None
    ):
        """Validate *target_dir* or ask the user to pick one."""
        if target_dir:
            if os.path.isdir(target_dir):
                return target_dir, True
            else:
                if target_dir in MarkedFiles.mark_target_dirs:
                    MarkedFiles.mark_target_dirs.remove(target_dir)
                app_actions.warn(
                    _("Invalid directory: {0}").format(target_dir)
                )
        target_dir = QFileDialog.getExistingDirectory(
            parent,
            _("Select target directory for marked files"),
            starting_target or "",
        )
        return target_dir, False

    # ==================================================================
    # Core file operations (static)
    # ==================================================================
    @staticmethod
    def move_marks_to_dir_static(
        app_actions,
        target_dir=None,
        move_func=None,
        files=None,
        single_image: bool = False,
        current_image=None,
    ) -> Tuple[bool, bool]:
        """Move or copy the marked files to *target_dir*."""
        if move_func is None:
            move_func = Utils.move_file

        MarkedFiles.is_performing_action = True
        some_files_already_present = False
        is_moving = move_func == Utils.move_file
        action_part1 = _("Moving") if is_moving else _("Copying")
        MarkedFiles.previous_marks.clear()
        files_to_move = MarkedFiles.file_marks if files is None else files
        action = Action(move_func, target_dir, MarkedFiles.file_marks)

        if len(files_to_move) > 1:
            logger.warning(
                f"{action_part1} {len(files_to_move)} files to directory: {target_dir}"
            )

        exceptions: dict[str, tuple] = {}
        invalid_files: list[str] = []
        set_last_moved_file = False

        for marked_file in files_to_move:
            if MarkedFiles.is_cancelled_action:
                break

            # Resolve source path for SVG
            source_path = marked_file
            moved_svg_as_png = False
            if config.enable_svgs and marked_file.lower().endswith(".svg"):
                cached_png = FrameCache.get_cached_path(marked_file)
                if cached_png and os.path.isfile(cached_png):
                    if config.marked_file_svg_move_type == "png":
                        if is_moving and current_image == marked_file and app_actions:
                            app_actions.release_media_canvas()
                        source_path = cached_png
                        moved_svg_as_png = True
                    elif is_moving:
                        if current_image == marked_file and app_actions:
                            app_actions.release_media_canvas()
                        FrameCache.remove_from_cache(
                            marked_file, delete_temp_file=True
                        )

            new_filename = os.path.join(
                target_dir, os.path.basename(source_path)
            )
            if not set_last_moved_file:
                MarkedFiles.last_moved_image = new_filename
                set_last_moved_file = True

            success, result = MarkedFiles._process_single_file_operation(
                marked_file,
                target_dir,
                move_func,
                new_filename,
                current_image,
                app_actions,
                overwrite_existing=config.move_marks_overwrite_existing_file,
                source_path=source_path,
            )

            if success:
                action.add_file(result)
                MarkedFiles.previous_marks.append(marked_file)
                if moved_svg_as_png and is_moving:
                    FrameCache.remove_from_cache(
                        marked_file, delete_temp_file=False
                    )
                    if app_actions:
                        try:
                            app_actions.delete(
                                marked_file, toast=False, manual_delete=False
                            )
                        except Exception as e:
                            logger.warning(
                                f"Failed to remove SVG after moving PNG: "
                                f"{marked_file} - {e}"
                            )
            else:
                exceptions[marked_file] = (result, new_filename)
                if not os.path.exists(marked_file):
                    invalid_files.append(marked_file)

        if MarkedFiles.is_cancelled_action:
            MarkedFiles.is_cancelled_action = False
            MarkedFiles.is_performing_action = False
            logger.warning(f"Cancelled {action_part1} to {target_dir}")
            if len(MarkedFiles.previous_marks) > 0:
                MarkedFiles.undo_move_marks(
                    app_actions.get_base_dir(), app_actions
                )
            return False, False

        if len(exceptions) < len(files_to_move):
            FileActionsWindow.update_history(action)
            action_type = (
                ActionType.MOVE_FILE if is_moving else ActionType.COPY_FILE
            )
            target_dir_name = Utils.get_relative_dirpath(target_dir, levels=2)
            if is_moving:
                message = _("Moved {0} files to {1}").format(
                    len(files_to_move) - len(exceptions), target_dir_name
                )
            else:
                message = _("Copied {0} files to {1}").format(
                    len(files_to_move) - len(exceptions), target_dir_name
                )
            logger.warning(message.replace("\n", " "))
            app_actions.title_notify(
                message, base_message=target_dir_name, action_type=action_type
            )
            MarkedFiles.delete_lock = False

        MarkedFiles.file_marks.clear()
        exceptions_present = len(exceptions) > 0

        if exceptions_present:
            action_part3 = "move" if is_moving else "copy"
            logger.error(f"Failed to {action_part3} some files:")
            names_are_short = False
            matching_files = False
            content_matching_files = False

            for marked_file, exc_tuple in exceptions.items():
                error_msg = exc_tuple[0]
                target_filepath = exc_tuple[1]
                logger.error(error_msg)

                if marked_file not in invalid_files:
                    if (
                        not config.clear_marks_with_errors_after_move
                        and not single_image
                    ):
                        MarkedFiles.file_marks.append(marked_file)

                    if error_msg.startswith("File already exists"):
                        if Utils.calculate_hash(marked_file) == Utils.calculate_hash(
                            target_filepath
                        ):
                            matching_files = True
                            logger.info(
                                f"File hashes match: {marked_file} <> {target_filepath}"
                            )
                            if is_moving and marked_file != target_filepath:
                                if MarkedFiles._check_delete_source_file(
                                    marked_file,
                                    target_dir,
                                    target_filepath,
                                    app_actions,
                                ):
                                    MarkedFiles._auto_delete_source_file(
                                        marked_file, current_image, app_actions
                                    )
                        elif ImageOps.compare_image_content_without_exif(
                            marked_file, target_filepath
                        ):
                            logger.info(
                                f"File hashes differ but image content matches: "
                                f"{marked_file} <> {target_filepath}"
                            )
                            logger.info(
                                "Replacing target file with source file "
                                "(source has more EXIF data)"
                            )
                            try:
                                success2, result2 = MarkedFiles._process_single_file_operation(
                                    marked_file,
                                    os.path.dirname(target_filepath),
                                    move_func,
                                    target_filepath,
                                    current_image,
                                    app_actions,
                                    overwrite_existing=True,
                                )
                                if success2:
                                    content_matching_files = True
                                    logger.info(
                                        "Replaced target file with source: "
                                        + marked_file
                                    )
                                    del exceptions[marked_file]
                                    action.add_file(target_filepath)
                                    MarkedFiles.previous_marks.append(
                                        marked_file
                                    )
                                else:
                                    error_text = (
                                        f"Failed to replace target file with "
                                        f"source: {marked_file} - {result2}"
                                    )
                                    logger.warning(error_text)
                                    app_actions.title_notify(error_text)
                            except Exception as e:
                                error_text = (
                                    f"Failed to replace target file with "
                                    f"source: {marked_file} - {e}"
                                )
                                logger.warning(error_text)
                                app_actions.title_notify(error_text)
                        elif (
                            len(os.path.basename(marked_file)) < 13
                            and not names_are_short
                        ):
                            names_are_short = True

                        if not some_files_already_present:
                            some_files_already_present = True
                            if not matching_files:
                                try:
                                    app_actions.copy_media_path(
                                        target_filepath
                                    )
                                    logger.info(
                                        f"Copied first target file path to "
                                        f"clipboard: {target_filepath}"
                                    )
                                except Exception as e:
                                    logger.warning(
                                        f"Failed to copy file path to "
                                        f"clipboard: {e}"
                                    )

            if some_files_already_present:
                if (
                    config.clear_marks_with_errors_after_move
                    and not single_image
                ):
                    logger.info("Cleared invalid marks by config option")
                warning = _("Existing filenames match!")
                if matching_files:
                    warning += "\n" + _("WARNING: Exact file match.")
                if content_matching_files:
                    warning += "\n" + _(
                        "INFO: Target files with different EXIF data replaced."
                    )
                if names_are_short:
                    warning += "\n" + _("WARNING: Short filenames.")
                app_actions.warn(warning)

        MarkedFiles.is_performing_action = False
        if len(MarkedFiles.previous_marks) > 0:
            MarkedFiles.last_set_target_dir = target_dir
            if is_moving:
                app_actions.refresh(
                    removed_files=list(MarkedFiles.previous_marks)
                )
            else:
                app_actions.refresh()
            if not exceptions_present:
                app_actions.refocus()
        return some_files_already_present, exceptions_present

    @staticmethod
    def undo_move_marks(base_dir, app_actions) -> None:
        """Undo the previous move/copy operation."""
        if MarkedFiles.is_performing_action:
            MarkedFiles.is_cancelled_action = True
            return
        if MarkedFiles.delete_lock:
            return

        is_moving_back = (
            FileActionsWindow.action_history[0].action == Utils.move_file
        )
        action_part1 = (
            _("Moving back") if is_moving_back else _("Removing")
        )
        action_part2 = _("Moved back") if is_moving_back else _("Removed")

        target_dir, target_was_valid = MarkedFiles.get_target_directory(
            MarkedFiles.last_set_target_dir, None, app_actions
        )
        if not target_was_valid:
            raise Exception(
                f"{action_part1} previously marked files failed, "
                f"somehow previous target directory invalid: {target_dir}"
            )

        if base_dir is None:
            base_dir = QFileDialog.getExistingDirectory(
                None,
                _("Where should the marked files have gone?"),
                target_dir or "",
            )
        if base_dir is None or base_dir == "" or not os.path.isdir(base_dir):
            raise Exception(
                "Failed to get valid base directory for undo move marked files."
            )

        logger.warning(
            f"Undoing action: {action_part1} {len(MarkedFiles.previous_marks)} "
            f"files from directory:\n{MarkedFiles.last_set_target_dir}"
        )

        exceptions: dict[str, str] = {}
        invalid_files: list[str] = []
        action = FileActionsWindow.action_history[0]

        for i, marked_file in enumerate(MarkedFiles.previous_marks):
            if i < len(action.new_files):
                expected_new_filepath = action.new_files[i]
            else:
                expected_new_filepath = os.path.join(
                    target_dir, os.path.basename(marked_file)
                )
            try:
                if is_moving_back:
                    Utils.move_file(
                        expected_new_filepath,
                        base_dir,
                        overwrite_existing=config.move_marks_overwrite_existing_file,
                    )
                else:
                    os.remove(expected_new_filepath)
                logger.info(
                    f"{action_part2} file from {target_dir}: "
                    f"{os.path.basename(expected_new_filepath)}"
                )
            except Exception as e:
                exceptions[marked_file] = str(e)
                if is_moving_back:
                    if not os.path.exists(marked_file):
                        invalid_files.append(expected_new_filepath)
                elif os.path.exists(expected_new_filepath):
                    invalid_files.append(expected_new_filepath)

        if len(exceptions) < len(MarkedFiles.previous_marks):
            if is_moving_back:
                message = _("Moved back {0} files from {1}").format(
                    len(MarkedFiles.previous_marks) - len(exceptions),
                    target_dir,
                )
            else:
                message = _("Removed {0} files from {1}").format(
                    len(MarkedFiles.previous_marks) - len(exceptions),
                    target_dir,
                )
            app_actions.toast(message)

        MarkedFiles.previous_marks.clear()
        if len(exceptions) > 0:
            for marked_file in exceptions:
                if marked_file not in invalid_files:
                    MarkedFiles.previous_marks.append(marked_file)
            action_part3 = "move" if is_moving_back else "copy"
            raise Exception(
                f"Failed to {action_part3} some files: {exceptions}"
            )
        app_actions.refresh()

    @staticmethod
    def test_in_directory_static(
        app_actions, target_dir=None, single_image: bool = False
    ) -> bool:
        """Check if the marked files already exist in *target_dir*."""
        MarkedFiles.is_performing_action = True
        if len(MarkedFiles.file_marks) > 1:
            logger.info(
                f"Checking if {len(MarkedFiles.file_marks)} files "
                f"are in directory: {target_dir}"
            )

        found_files: list[tuple[str, str]] = []
        for marked_file in MarkedFiles.file_marks:
            new_filename = os.path.join(
                target_dir, os.path.basename(marked_file)
            )
            if os.path.isfile(new_filename):
                logger.warning(
                    f"{marked_file} is already present in {target_dir}"
                )
                found_files.append((marked_file, new_filename))

        names_are_short = False
        matching_files = 0
        content_matching_files = 0
        for marked_file, new_filename in found_files:
            if Utils.calculate_hash(marked_file) == Utils.calculate_hash(
                new_filename
            ):
                matching_files += 1
                logger.info(
                    f"File hashes match: {marked_file} <> {new_filename}"
                )
            elif ImageOps.compare_image_content_without_exif(
                marked_file, new_filename
            ):
                content_matching_files += 1
                logger.info(
                    f"File hashes differ but image content matches: "
                    f"{marked_file} <> {new_filename}"
                )
            elif (
                len(os.path.basename(marked_file)) < 13
                and not names_are_short
            ):
                names_are_short = True

        if len(found_files) > 0:
            warning = _("Existing filenames found!")
            if matching_files == len(MarkedFiles.file_marks):
                warning += "\n" + _("WARNING: All file hashes match.")
            elif matching_files > 0:
                warning += "\n" + _(
                    "WARNING: %s of %s file hashes match."
                ).format(matching_files, len(MarkedFiles.file_marks))
            if content_matching_files > 0:
                warning += "\n" + _(
                    "INFO: %s files have identical content but different EXIF data."
                ).format(content_matching_files)
            if (matching_files + content_matching_files) == len(
                MarkedFiles.file_marks
            ):
                warning += "\n" + _(
                    "WARNING: All files are either identical or have "
                    "matching content."
                )
            if names_are_short:
                warning += "\n" + _("WARNING: Short filenames.")
            app_actions.warn(warning)
        else:
            app_actions.toast(_("No existing filenames found."))

        app_actions.refocus()
        return len(found_files) > 0

    @staticmethod
    def _check_delete_source_file(
        marked_file: str,
        target_dir: str,
        target_filepath: str,
        app_actions,
    ) -> bool:
        """Check if we should delete the source after a move (duplicate)."""
        if MarkedFiles.gimp_opened_in_last_action:
            MarkedFiles.gimp_opened_in_last_action = False
            return True

        should_check = False

        if len(FileActionsWindow.action_history) == 0:
            MarkedFiles.gimp_opened_in_last_action = False
            return True

        previous_action = FileActionsWindow.action_history[0]
        if previous_action.target == target_dir:
            if (
                marked_file in previous_action.original_marks
                or target_filepath in previous_action.new_files
            ):
                should_check = True

        if should_check:
            warning_message = _(
                "WARNING: You just copied this file to this directory, "
                "and now you're trying to move it here.\n\n"
                "This would delete the original file. If this was a mistake, "
                "please cancel this operation.\n\n"
                "File: {0}\n"
                "Target: {1}\n\n"
                "Do you want to continue and delete the source file?"
            ).format(os.path.basename(marked_file), target_dir)

            if app_actions.alert(
                _("Potential Mistake Detected"),
                warning_message,
                kind="askokcancel",
            ):
                logger.warning(
                    f"User confirmed deletion after copy-then-move "
                    f"detection for {marked_file}"
                )
                MarkedFiles.gimp_opened_in_last_action = False
                return True
            else:
                logger.warning(
                    f"User cancelled deletion after copy-then-move "
                    f"detection for {marked_file}"
                )
                MarkedFiles.gimp_opened_in_last_action = False
                return False

        MarkedFiles.gimp_opened_in_last_action = False
        return True

    @staticmethod
    def _auto_delete_source_file(
        marked_file: str,
        current_image: Optional[str] = None,
        app_actions=None,
    ) -> None:
        """Auto-delete source after move when target already exists."""
        try:
            if current_image is not None and current_image == marked_file:
                app_actions.release_media_canvas()
            app_actions.delete(marked_file)
            if marked_file in MarkedFiles.file_marks:
                MarkedFiles.file_marks.remove(marked_file)
            app_actions.warn(
                _("Removed marked file from source: {0}").format(marked_file)
            )
        except Exception as e:
            error_text = (
                f"Failed to remove marked file from source: "
                f"{marked_file} - {e}"
            )
            logger.warning(error_text)
            app_actions.title_notify(error_text)

    @staticmethod
    def _process_single_file_operation(
        marked_file: str,
        target_dir: str,
        move_func: Callable,
        new_filename: str,
        current_image: Optional[str] = None,
        app_actions=None,
        overwrite_existing: bool = False,
        source_path: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Process a single file move/copy with thread-safe lock."""
        actual_source = source_path if source_path is not None else marked_file
        new_filename = os.path.join(
            target_dir, os.path.basename(actual_source)
        )
        is_moving = move_func == Utils.move_file

        try:
            with Utils.file_operation_lock:
                if is_moving and current_image == marked_file:
                    if app_actions:
                        app_actions.release_media_canvas()
                move_func(
                    actual_source,
                    target_dir,
                    overwrite_existing=overwrite_existing,
                )
            action_part2 = _("Moved") if is_moving else _("Copied")
            logger.info(f"{action_part2} file to {new_filename}")
            return True, new_filename
        except Exception as e:
            return False, str(e)

    # ==================================================================
    # Factory
    # ==================================================================
    @staticmethod
    def show_window(
        master,
        is_gui: bool,
        single_image,
        current_image,
        app_mode,
        app_actions,
        base_dir: str = ".",
    ):
        """Create or focus the MarkedFiles dialog. Returns the instance."""
        if MarkedFiles._current_window is not None:
            try:
                if MarkedFiles._current_window.isVisible():
                    win = MarkedFiles._current_window
                    win.setWindowTitle(
                        _("Move {0} Marked File(s)").format(
                            len(MarkedFiles.file_marks)
                        )
                    )
                    win.setWindowOpacity(1.0)
                    win.raise_()
                    win.activateWindow()
                    return win
            except Exception:
                MarkedFiles._current_window = None

        window = MarkedFiles(
            master,
            is_gui,
            single_image,
            current_image,
            app_mode,
            app_actions,
            base_dir,
        )
        window.show()
        return window

    # ==================================================================
    # Construction
    # ==================================================================
    def __init__(
        self,
        master: QWidget,
        is_gui: bool,
        single_image,
        current_image,
        app_mode,
        app_actions: AppActions,
        base_dir: str = ".",
    ) -> None:
        geometry = "600x500" if is_gui else "300x100"
        super().__init__(
            parent=master,
            position_parent=master,
            title=_("Move {0} Marked File(s)").format(
                len(MarkedFiles.file_marks)
            ),
            geometry=geometry,
        )
        MarkedFiles._current_window = self

        self._is_gui = is_gui
        self._single_image = single_image
        self._current_image = current_image
        self._app_mode = app_mode
        self._app_actions = app_actions
        self._base_dir = os.path.normpath(base_dir)
        self._filter_text: str = ""
        self._filtered_target_dirs: list[str] = (
            MarkedFiles.mark_target_dirs[:]
        )
        self._is_sorted_by_embedding = False

        if MarkedFiles.last_set_target_dir and os.path.isdir(
            MarkedFiles.last_set_target_dir
        ):
            self._starting_target = MarkedFiles.last_set_target_dir
        else:
            self._starting_target = base_dir

        self._do_set_permanent_mark_target = False
        self._do_set_hotkey_action = -1

        if not is_gui:
            self.setWindowOpacity(0.3)
        else:
            self._build_gui()

        # -- keyboard shortcuts -------------------------------------------
        QShortcut(QKeySequence(Qt.Key_Escape), self).activated.connect(
            self.close_windows
        )
        QShortcut(QKeySequence("Shift+Delete"), self).activated.connect(
            self._delete_marked_files
        )
        QShortcut(QKeySequence("Shift+C"), self).activated.connect(
            self._clear_marks
        )
        QShortcut(QKeySequence("Ctrl+T"), self).activated.connect(
            self._set_permanent_mark_target
        )
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(
            self._sort_target_dirs_by_embedding
        )
        QShortcut(QKeySequence("Ctrl+H"), self).activated.connect(
            self._open_hotkey_actions_window
        )

        QTimer.singleShot(1, self.activateWindow)

    # ==================================================================
    # GUI building
    # ==================================================================
    def _build_gui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(6)

        # -- action bar ---------------------------------------------------
        bar = QHBoxLayout()
        bar.setSpacing(4)

        new_lbl = QLabel(_("New target:"))
        new_lbl.setStyleSheet(f"color: {AppStyle.FG_COLOR};")
        bar.addWidget(new_lbl)

        move_new_btn = QPushButton(_("MOVE"))
        move_new_btn.clicked.connect(
            lambda: self._handle_target_directory(move_func=Utils.move_file)
        )
        bar.addWidget(move_new_btn)

        copy_new_btn = QPushButton(_("COPY"))
        copy_new_btn.clicked.connect(
            lambda: self._handle_target_directory(move_func=Utils.copy_file)
        )
        bar.addWidget(copy_new_btn)

        del_btn = QPushButton(_("DELETE"))
        del_btn.clicked.connect(self._delete_marked_files)
        bar.addWidget(del_btn)

        add_parent_btn = QPushButton(_("Add from parent"))
        add_parent_btn.clicked.connect(self._set_target_dirs_from_dir)
        bar.addWidget(add_parent_btn)

        clear_btn = QPushButton(_("Clear targets"))
        clear_btn.clicked.connect(self._clear_target_dirs)
        bar.addWidget(clear_btn)

        pdf_btn = QPushButton(_("Create PDF"))
        pdf_btn.clicked.connect(self._create_pdf_from_marks)
        bar.addWidget(pdf_btn)

        root.addLayout(bar)

        # -- scroll area for directory rows -------------------------------
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

        # -- filter indicator ---------------------------------------------
        self._filter_label = QLabel("")
        self._filter_label.setStyleSheet("color: orange; font-style: italic;")
        self._filter_label.setVisible(False)
        root.addWidget(self._filter_label)

        self._rebuild_directory_rows()

    def _rebuild_directory_rows(self) -> None:
        """Clear and rebuild the scrollable directory list."""
        _clear_layout(self._scroll_layout)

        for target_dir in self._filtered_target_dirs:
            row = QHBoxLayout()

            dir_label = QLabel(target_dir)
            dir_label.setStyleSheet(f"color: {AppStyle.FG_COLOR};")
            dir_label.setWordWrap(True)
            row.addWidget(dir_label, 1)

            move_btn = QPushButton(_("Move"))
            move_btn.setFixedWidth(50)
            move_btn.clicked.connect(
                lambda _=False, d=target_dir: self._move_marks_to_dir(
                    target_dir=d
                )
            )
            row.addWidget(move_btn)

            copy_btn = QPushButton(_("Copy"))
            copy_btn.setFixedWidth(50)
            copy_btn.clicked.connect(
                lambda _=False, d=target_dir: self._move_marks_to_dir(
                    target_dir=d, move_func=Utils.copy_file
                )
            )
            row.addWidget(copy_btn)

            remove_btn = QPushButton("\u00d7")  # multiplication sign
            remove_btn.setFixedWidth(28)
            remove_btn.setToolTip(_("Remove this target directory"))
            remove_btn.clicked.connect(
                lambda _=False, d=target_dir: self._remove_single_target(d)
            )
            row.addWidget(remove_btn)

            self._scroll_layout.addLayout(row)

        self._scroll_layout.addStretch()

    # ==================================================================
    # Instance action methods
    # ==================================================================
    def _handle_target_directory(
        self, target_dir=None, move_func=Utils.move_file
    ) -> Optional[str]:
        """Validate/ask for target dir, add to list, trigger action."""
        target_dir, target_was_valid = MarkedFiles.get_target_directory(
            target_dir,
            self._starting_target,
            self._app_actions,
            parent=self,
        )
        if not target_dir or not os.path.isdir(target_dir):
            self.close_windows()
            return None

        if target_was_valid:
            return target_dir

        target_dir = os.path.normpath(target_dir)
        if target_dir not in MarkedFiles.mark_target_dirs:
            MarkedFiles.mark_target_dirs.append(target_dir)
            MarkedFiles.mark_target_dirs.sort()

        if move_func is not None:
            self._move_marks_to_dir(target_dir=target_dir, move_func=move_func)
        else:
            self._test_is_in_directory(target_dir=target_dir)
        return target_dir

    def _move_marks_to_dir(
        self, target_dir=None, move_func=Utils.move_file
    ) -> None:
        target_dir = self._handle_target_directory(
            target_dir=target_dir, move_func=None  # prevent recursion
        )
        if target_dir is None:
            return
        if (
            config.debug
            and self._filter_text
            and self._filter_text.strip() != ""
        ):
            logger.debug(f"Filtered by string: {self._filter_text}")

        if self._do_set_permanent_mark_target:
            FileActionsWindow.set_permanent_action(
                target_dir, move_func, self._app_actions.toast
            )
            self._do_set_permanent_mark_target = False

        if self._do_set_hotkey_action > -1:
            FileActionsWindow.set_hotkey_action(
                self._do_set_hotkey_action,
                target_dir,
                move_func,
                self._app_actions.toast,
            )
            self._do_set_hotkey_action = -1

        MarkedFiles.move_marks_to_dir_static(
            self._app_actions,
            target_dir=target_dir,
            move_func=move_func,
            single_image=self._single_image,
            current_image=self._current_image,
        )
        self.close_windows()

    def _delete_marked_files(self) -> None:
        severity = (
            "high" if len(MarkedFiles.file_marks) > 5 else "normal"
        )
        if not self._app_actions.alert(
            _("Confirm Delete"),
            _("Deleting {0} marked files - Are you sure you want to proceed?").format(
                len(MarkedFiles.file_marks)
            ),
            kind="askokcancel",
            severity=severity,
            master=self,
        ):
            return

        if (
            self._current_image
            and self._current_image in MarkedFiles.file_marks
        ):
            self._app_actions.release_media_canvas()

        removed_files: list[str] = []
        failed_to_delete: list[str] = []

        for filepath in MarkedFiles.file_marks:
            try:
                if config.enable_svgs and filepath.lower().endswith(".svg"):
                    FrameCache.remove_from_cache(
                        filepath, delete_temp_file=True
                    )
                self._app_actions.delete(filepath, manual_delete=False)
                removed_files.append(filepath)
            except Exception as e:
                logger.error(f"Failed to delete {filepath}: {e}")
                if os.path.exists(filepath):
                    failed_to_delete.append(filepath)

        MarkedFiles.file_marks.clear()
        if failed_to_delete:
            MarkedFiles.file_marks.extend(failed_to_delete)
            self._app_actions.alert(
                _("Delete Failed"),
                _("Failed to delete {0} files - check log for details.").format(
                    len(failed_to_delete)
                ),
                kind="warning",
                master=self,
            )
        else:
            self._app_actions.warn(
                _("Deleted {0} marked files.").format(len(removed_files))
            )

        self._app_actions.refresh(
            removed_files=(
                removed_files
                if self._app_mode != Mode.BROWSE
                else []
            )
        )
        self.close_windows()

    def _clear_marks(self) -> None:
        MarkedFiles.clear_file_marks(self._app_actions.toast)
        self.close_windows()

    def _remove_single_target(self, target_dir: str) -> None:
        """Remove a single directory from the target list."""
        if target_dir in MarkedFiles.mark_target_dirs:
            MarkedFiles.mark_target_dirs.remove(target_dir)
        if target_dir in self._filtered_target_dirs:
            self._filtered_target_dirs.remove(target_dir)
        if self._is_gui:
            self._rebuild_directory_rows()

    def _clear_target_dirs(self) -> None:
        MarkedFiles.mark_target_dirs.clear()
        self._filtered_target_dirs.clear()
        if self._is_gui:
            self._rebuild_directory_rows()

    def _set_target_dirs_from_dir(self) -> None:
        parent_dir = QFileDialog.getExistingDirectory(
            self,
            _("Select parent directory for target directories"),
            self._starting_target or "",
        )
        if not parent_dir or not os.path.isdir(parent_dir):
            return

        for name in os.listdir(parent_dir):
            dirpath = os.path.normpath(os.path.join(parent_dir, name))
            if os.path.isdir(dirpath) and dirpath != self._base_dir:
                if dirpath not in MarkedFiles.mark_target_dirs:
                    MarkedFiles.mark_target_dirs.append(dirpath)

        MarkedFiles.mark_target_dirs.sort()
        self._filtered_target_dirs = MarkedFiles.mark_target_dirs[:]
        self._filter_text = ""
        if self._is_gui:
            self._rebuild_directory_rows()
            self._filter_label.setVisible(False)

    @require_password(ProtectedActions.SET_HOTKEY_ACTIONS)
    def _open_hotkey_actions_window(self) -> None:
        try:
            from ui.files.hotkey_actions_window_qt import HotkeyActionsWindow

            win = HotkeyActionsWindow(
                self,
                self._app_actions,
                self._set_permanent_mark_target,
                self.set_hotkey_action,
            )
            win.show()
        except Exception as e:
            self._app_actions.alert(
                _("Error"),
                "Error opening hotkey actions window: " + str(e),
                master=self,
            )

    @require_password(
        ProtectedActions.SET_HOTKEY_ACTIONS,
        custom_text=_(
            "WARNING: This action sets hotkey actions that will be used "
            "for future file operations. You may have accidentally triggered "
            "this shortcut due to a sticky Control key. Please confirm you "
            "want to proceed."
        ),
        allow_unauthenticated=False,
    )
    def _set_permanent_mark_target(self) -> None:
        self._do_set_permanent_mark_target = True
        logger.debug("Setting permanent mark target hotkey action")
        self._app_actions.toast(_("Recording next mark target and action."))

    def set_hotkey_action(self, event=None, hotkey_override=None) -> None:
        assert event is not None or hotkey_override is not None
        self._do_set_hotkey_action = (
            int(hotkey_override) if hotkey_override is not None else -1
        )
        logger.debug(
            f"Doing set hotkey action: {self._do_set_hotkey_action}"
        )
        self._app_actions.toast(_("Recording next mark target and action."))

    def _sort_target_dirs_by_embedding(self) -> None:
        from compare.compare_embeddings_clip import CompareEmbeddingClip

        embedding_texts: dict[str, str] = {}
        for d in self._filtered_target_dirs:
            embedding_text = self._get_embedding_text_for_dirpath(d)
            if embedding_text is not None and embedding_text.strip() != "":
                embedding_texts[d] = embedding_text

        similarities = CompareEmbeddingClip.single_text_compare(
            self._single_image, embedding_texts
        )
        self._filtered_target_dirs = [
            dirpath
            for dirpath, _ in sorted(
                similarities.items(), key=lambda x: -x[1]
            )
        ]
        self._is_sorted_by_embedding = True
        if self._is_gui:
            self._rebuild_directory_rows()
        self._app_actions.toast(
            _("Sorted directories by embedding comparison.")
        )

    def _get_embedding_text_for_dirpath(self, dirpath: str) -> Optional[str]:
        basename = os.path.basename(dirpath)
        for text in config.text_embedding_search_presets:
            if basename == text or re.search(
                f"(^|_| ){text}($|_| )", basename
            ):
                logger.info(
                    f"Found embeddable directory for text {text}: {dirpath}"
                )
                return text
        return None

    def _create_pdf_from_marks(self, output_path=None) -> None:
        from files.pdf_creator import PDFCreator
        from ui.files.pdf_options_window_qt import PDFOptionsWindow

        def pdf_callback(options):
            PDFCreator.create_pdf_from_files(
                MarkedFiles.file_marks, self._app_actions, output_path, options
            )

        PDFOptionsWindow.show(self, self._app_actions, pdf_callback)

    def _test_is_in_directory(
        self, target_dir=None, shift: bool = False
    ) -> None:
        target_dir = self._handle_target_directory(
            target_dir=target_dir, move_func=None
        )
        if target_dir is None:
            return
        if (
            config.debug
            and self._filter_text
            and self._filter_text.strip() != ""
        ):
            logger.debug(f"Filtered by string: {self._filter_text}")

        if shift:
            self._find_is_downstream_related_image_in_directory(
                target_dir=target_dir
            )
        else:
            MarkedFiles.test_in_directory_static(
                self._app_actions,
                target_dir=target_dir,
                single_image=self._single_image,
            )
        self.close_windows()

    def _do_action_test_is_in_directory(
        self, *, ctrl: bool = False, alt: bool = False, shift: bool = False
    ) -> None:
        target_dir = None
        if alt:
            penultimate_action = FileActionsWindow.get_history_action(
                start_index=1
            )
            if penultimate_action is not None and os.path.isdir(
                penultimate_action.target
            ):
                target_dir = penultimate_action.target
        elif len(self._filtered_target_dirs) == 0 or ctrl:
            self._handle_target_directory(move_func=None)
            return
        else:
            if (
                len(self._filtered_target_dirs) == 1
                or self._filter_text.strip() != ""
                or self._is_sorted_by_embedding
            ):
                target_dir = self._filtered_target_dirs[0]
            else:
                target_dir = MarkedFiles.last_set_target_dir

        if target_dir is None:
            self._handle_target_directory(move_func=None)
        else:
            self._test_is_in_directory(target_dir=target_dir, shift=shift)

    def _find_is_downstream_related_image_in_directory(
        self, target_dir: str
    ) -> None:
        from files.file_browser import FileBrowser
        from image.image_data_extractor import image_data_extractor

        if (
            MarkedFiles.file_browser is None
            or MarkedFiles.file_browser.directory != target_dir
            or not MarkedFiles.file_browser.recursive
        ):
            MarkedFiles.file_browser = FileBrowser(
                directory=target_dir, recursive=True
            )
        MarkedFiles.file_browser._gather_files(files=None)

        marked_file_basenames = [
            os.path.basename(f) for f in MarkedFiles.file_marks
        ]
        downstream_related_images: list[str] = []
        for path in MarkedFiles.file_browser.filepaths:
            if path in MarkedFiles.file_marks:
                continue
            related_image_path = image_data_extractor.get_related_image_path(
                path
            )
            if related_image_path is not None:
                if related_image_path in MarkedFiles.file_marks:
                    downstream_related_images.append(path)
                else:
                    file_basename = os.path.basename(related_image_path)
                    if (
                        len(file_basename) > 10
                        and file_basename in marked_file_basenames
                    ):
                        downstream_related_images.append(path)

        if downstream_related_images:
            for image in downstream_related_images:
                logger.warning(f"Downstream related image found: {image}")
            self._app_actions.toast(
                _("Found {0} downstream related images").format(
                    len(downstream_related_images)
                )
            )
        else:
            self._app_actions.toast(
                _("No downstream related images found")
            )

    # ==================================================================
    # Paging
    # ==================================================================
    def _page_up(self) -> None:
        paging_len = max(1, len(self._filtered_target_dirs) // 10)
        idx = len(self._filtered_target_dirs) - paging_len
        self._filtered_target_dirs = (
            self._filtered_target_dirs[idx:]
            + self._filtered_target_dirs[:idx]
        )
        if self._is_gui:
            self._rebuild_directory_rows()

    def _page_down(self) -> None:
        paging_len = max(1, len(self._filtered_target_dirs) // 10)
        self._filtered_target_dirs = (
            self._filtered_target_dirs[paging_len:]
            + self._filtered_target_dirs[:paging_len]
        )
        if self._is_gui:
            self._rebuild_directory_rows()

    # ==================================================================
    # Filtering (4-pass ranked matching)
    # ==================================================================
    def _apply_filter(self) -> None:
        if self._filter_text:
            self._filter_label.setText(
                _("Filter: {}").format(self._filter_text)
            ) if self._is_gui else None
            if self._is_gui:
                self._filter_label.setVisible(True)
        else:
            if self._is_gui:
                self._filter_label.setVisible(False)

        ft = self._filter_text.strip().lower()
        if not ft:
            self._filtered_target_dirs = MarkedFiles.mark_target_dirs[:]
        else:
            temp: list[str] = []
            dirs = MarkedFiles.mark_target_dirs

            # Pass 1: exact basename match
            for d in dirs:
                basename = os.path.basename(os.path.normpath(d))
                if basename.lower() == ft:
                    temp.append(d)

            # Pass 2: basename starts-with
            for d in dirs:
                if d not in temp:
                    basename = os.path.basename(os.path.normpath(d))
                    if basename.lower().startswith(ft):
                        temp.append(d)

            # Pass 3: parent directory starts-with
            for d in dirs:
                if d not in temp:
                    dirname = os.path.basename(
                        os.path.dirname(os.path.normpath(d))
                    )
                    if dirname and dirname.lower().startswith(ft):
                        temp.append(d)

            # Pass 4: substring match in basename
            for d in dirs:
                if d not in temp:
                    basename = os.path.basename(os.path.normpath(d))
                    if basename and (
                        f" {ft}" in basename.lower()
                        or f"_{ft}" in basename.lower()
                    ):
                        temp.append(d)

            self._filtered_target_dirs = temp

        if self._is_gui:
            self._rebuild_directory_rows()

    # ==================================================================
    # Enter-key action dispatch
    # ==================================================================
    def _do_action(
        self, *, shift: bool = False, ctrl: bool = False, alt: bool = False
    ) -> None:
        move_func = Utils.copy_file if shift else Utils.move_file

        if alt:
            penultimate_action = FileActionsWindow.get_history_action(
                start_index=1
            )
            if penultimate_action is not None and os.path.isdir(
                penultimate_action.target
            ):
                self._move_marks_to_dir(
                    target_dir=penultimate_action.target, move_func=move_func
                )
        elif len(self._filtered_target_dirs) == 0 or ctrl:
            self._handle_target_directory(move_func=move_func)
        else:
            if (
                len(self._filtered_target_dirs) == 1
                or self._filter_text.strip() != ""
                or self._is_sorted_by_embedding
            ):
                target_dir = self._filtered_target_dirs[0]
            else:
                target_dir = MarkedFiles.last_set_target_dir
            self._move_marks_to_dir(target_dir=target_dir, move_func=move_func)

    # ==================================================================
    # Key / mouse event handling
    # ==================================================================
    def keyPressEvent(self, event) -> None:  # noqa: N802
        key = event.key()
        modifiers = event.modifiers()

        # Return / Enter -> do action
        if key in (Qt.Key_Return, Qt.Key_Enter):
            self._do_action(
                shift=bool(modifiers & Qt.ShiftModifier),
                ctrl=bool(modifiers & Qt.ControlModifier),
                alt=bool(modifiers & Qt.AltModifier),
            )
            return

        # Page Up / Down
        if key == Qt.Key_PageUp:
            self._page_up()
            return
        if key == Qt.Key_PageDown:
            self._page_down()
            return

        # Up / Down arrows -> roll list
        if key == Qt.Key_Down and self._filtered_target_dirs:
            self._filtered_target_dirs = (
                self._filtered_target_dirs[1:]
                + [self._filtered_target_dirs[0]]
            )
            if self._is_gui:
                self._rebuild_directory_rows()
            return
        if key == Qt.Key_Up and self._filtered_target_dirs:
            self._filtered_target_dirs = (
                [self._filtered_target_dirs[-1]]
                + self._filtered_target_dirs[:-1]
            )
            if self._is_gui:
                self._rebuild_directory_rows()
            return

        # Backspace -> trim filter
        if key == Qt.Key_Backspace:
            if self._filter_text:
                self._filter_text = self._filter_text[:-1]
                self._apply_filter()
            return

        # Ignore modifier-only or Ctrl/Alt combos (let shortcuts handle)
        if modifiers & (Qt.ControlModifier | Qt.AltModifier):
            super().keyPressEvent(event)
            return
        if key in (Qt.Key_Shift, Qt.Key_Control, Qt.Key_Alt, Qt.Key_Meta):
            super().keyPressEvent(event)
            return

        # Printable text -> filter
        text = event.text()
        if text and text.isprintable():
            self._filter_text += text
            self._apply_filter()
            return

        super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MiddleButton:
            self._delete_marked_files()
            return
        if event.button() == Qt.RightButton:
            mods = event.modifiers()
            self._do_action_test_is_in_directory(
                ctrl=bool(mods & Qt.ControlModifier),
                alt=bool(mods & Qt.AltModifier),
                shift=bool(mods & Qt.ShiftModifier),
            )
            return
        super().mousePressEvent(event)

    # ==================================================================
    # Lifecycle
    # ==================================================================
    def close_windows(self) -> None:
        self.close()

    def closeEvent(self, event) -> None:  # noqa: N802
        if MarkedFiles._current_window is self:
            MarkedFiles._current_window = None
        if (
            self._single_image is not None
            and len(MarkedFiles.file_marks) == 1
        ):
            MarkedFiles.file_marks.clear()
            self._app_actions.toast(_("Cleared marked file"))
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
