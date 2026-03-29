"""
Video file operations (ffmpeg), kept separate from :mod:`image.image_ops`.

Container metadata is format-specific (MP4 ``moov`` atoms, Matroska tags, etc.).
Remuxing with stream copy plus ``-map_metadata -1`` strips global/container tags
without re-encoding; use :func:`ffprobe_json` (or ``ffprobe`` in a shell) later
for a details UI and to verify strips.

Reading rich tags in Python often goes through **ffprobe** (same install as ffmpeg)
or ExifTool; see project notes on format coverage.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any

from utils.logging_setup import get_logger
from utils.media_utils import is_video_file

logger = get_logger("video_ops")


def default_output_path_copy_without_metadata(video_path: str) -> str:
    """
    ``dir/foo.ext`` → ``dir/foo_nometa.ext``, or ``foo_nometa_N.ext`` if that exists.
    """
    dirname = os.path.dirname(os.path.abspath(video_path)) or "."
    stem, ext = os.path.splitext(os.path.basename(video_path))
    base = os.path.join(dirname, f"{stem}_nometa")
    candidate = f"{base}{ext}"
    n = 1
    while os.path.exists(candidate):
        candidate = f"{base}_{n}{ext}"
        n += 1
    return candidate


class VideoOps:
    """Static helpers for video processing."""

    @staticmethod
    def find_ffmpeg_executable() -> str | None:
        """Return the ``ffmpeg`` executable path if it is on PATH, else ``None``."""
        return shutil.which("ffmpeg")

    @staticmethod
    def strip_video_audio(video_path: str) -> str:
        """
        Remove audio streams from *video_path* in place using ffmpeg (video stream copy).

        Requires ffmpeg on PATH. Writes a temporary file next to the source, then replaces
        the original atomically where the OS allows it.

        Returns:
            *video_path* on success.

        Raises:
            RuntimeError: If the file is not a video, ffmpeg is missing, or processing fails.
        """
        if not is_video_file(video_path):
            raise RuntimeError("Not a video file")
        ffmpeg = VideoOps.find_ffmpeg_executable()
        if not ffmpeg:
            raise RuntimeError("ffmpeg not found on PATH")

        src_dir = os.path.dirname(os.path.abspath(video_path)) or "."
        tmp_path = os.path.join(
            src_dir,
            os.path.basename(video_path) + ".weidr_strip_audio.tmp",
        )
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError as e:
                raise RuntimeError(f"Could not remove stale temp file: {e}") from e

        cmd = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-y",
            "-i",
            video_path,
            "-c:v",
            "copy",
            "-an",
            tmp_path,
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                timeout=3600,
            )
        except subprocess.TimeoutExpired as e:
            try:
                if os.path.isfile(tmp_path):
                    os.unlink(tmp_path)
            except OSError:
                pass
            raise RuntimeError("ffmpeg timed out while stripping audio") from e
        except OSError as e:
            raise RuntimeError(f"Failed to run ffmpeg: {e}") from e

        if proc.returncode != 0:
            try:
                if os.path.isfile(tmp_path):
                    os.unlink(tmp_path)
            except OSError:
                pass
            err = (proc.stderr or proc.stdout or "").strip()
            detail = f": {err}" if err else ""
            raise RuntimeError(f"ffmpeg failed{detail}")

        try:
            os.replace(tmp_path, video_path)
        except OSError as e:
            try:
                if os.path.isfile(tmp_path):
                    os.unlink(tmp_path)
            except OSError:
                pass
            raise RuntimeError(f"Could not replace video file: {e}") from e

        logger.info("Stripped audio: %s", video_path)
        return video_path

    @staticmethod
    def copy_video_without_metadata(
        video_path: str,
        output_path: str | None = None,
    ) -> str:
        """
        Write a **new file** next to the source with container metadata stripped.

        Uses ffmpeg stream copy (no re-encode): ``-map_metadata -1`` removes global
        tags; ``-map_chapters -1`` drops chapters. Does not modify *video_path*.

        If *output_path* is omitted, uses :func:`default_output_path_copy_without_metadata`.

        Returns:
            Path to the written file.

        Raises:
            RuntimeError: If validation fails, ffmpeg is missing, or ffmpeg errors.
        """
        if not is_video_file(video_path):
            raise RuntimeError("Not a video file")
        ffmpeg = VideoOps.find_ffmpeg_executable()
        if not ffmpeg:
            raise RuntimeError("ffmpeg not found on PATH")

        out = output_path or default_output_path_copy_without_metadata(video_path)
        out = os.path.abspath(out)
        if os.path.abspath(video_path) == out:
            raise RuntimeError("Output path must differ from the source file")
        if os.path.exists(out):
            raise RuntimeError(f"Output file already exists: {out}")

        out_dir = os.path.dirname(out)
        if out_dir and not os.path.isdir(out_dir):
            raise RuntimeError(f"Output directory does not exist: {out_dir}")

        cmd = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-y",
            "-i",
            video_path,
            "-map_metadata",
            "-1",
            "-map_chapters",
            "-1",
            "-c",
            "copy",
            out,
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                timeout=3600,
            )
        except subprocess.TimeoutExpired:
            try:
                if os.path.isfile(out):
                    os.unlink(out)
            except OSError:
                pass
            raise RuntimeError("ffmpeg timed out while copying video") from None
        except OSError as e:
            raise RuntimeError(f"Failed to run ffmpeg: {e}") from e

        if proc.returncode != 0:
            try:
                if os.path.isfile(out):
                    os.unlink(out)
            except OSError:
                pass
            err = (proc.stderr or proc.stdout or "").strip()
            detail = f": {err}" if err else ""
            raise RuntimeError(f"ffmpeg failed{detail}")

        logger.info("Wrote video without metadata: %s -> %s", video_path, out)
        return out

    @staticmethod
    def find_ffprobe_executable() -> str | None:
        """Return ``ffprobe`` on PATH if present (pairs with ffmpeg installs)."""
        return shutil.which("ffprobe")

    @staticmethod
    def ffprobe_json(video_path: str) -> dict[str, Any]:
        """
        Run ffprobe and return parsed JSON (format + streams). For future details UI.

        Raises:
            RuntimeError: If ffprobe is missing, the path is invalid, or JSON parse fails.
        """
        if not video_path or not os.path.isfile(video_path):
            raise RuntimeError("Not a file")
        ffprobe = VideoOps.find_ffprobe_executable()
        if not ffprobe:
            raise RuntimeError("ffprobe not found on PATH")

        cmd = [
            ffprobe,
            "-hide_banner",
            "-loglevel",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            video_path,
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                timeout=120,
            )
        except (subprocess.TimeoutExpired, OSError) as e:
            raise RuntimeError(f"ffprobe failed: {e}") from e

        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip()
            detail = f": {err}" if err else ""
            raise RuntimeError(f"ffprobe failed{detail}")

        try:
            data = json.loads(proc.stdout or "{}")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid ffprobe JSON: {e}") from e
        return data if isinstance(data, dict) else {}
