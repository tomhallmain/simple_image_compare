"""
Video file operations (ffmpeg), kept separate from :mod:`image.image_ops`.
"""

from __future__ import annotations

import os
import shutil
import subprocess

from utils.logging_setup import get_logger
from utils.media_utils import is_video_file

logger = get_logger("video_ops")


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
