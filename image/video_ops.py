"""
Video file operations (ffmpeg), kept separate from :mod:`image.image_ops`.

Container metadata is format-specific (MP4 ``moov`` atoms, Matroska tags, etc.).
Remuxing with stream copy plus ``-map_metadata -1`` strips global/container tags
without re-encoding; use :func:`ffprobe_json` (or ``ffprobe`` in a shell) later
for a details UI and to verify strips.

Reading rich tags in Python often goes through **ffprobe** (same install as ffmpeg)
or ExifTool; see project notes on format coverage.

Use :meth:`VideoOps.merge_ffprobe_tag_dicts`, :meth:`VideoOps.ffprobe_video_mode_and_dims`,
and :meth:`VideoOps.ffprobe_prompt_fields_from_tags` to interpret :meth:`VideoOps.ffprobe_json` output.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any

from utils.logging_setup import get_logger
from utils.media_utils import is_video_file
from utils.translations import I18N

logger = get_logger("video_ops")
_ = I18N._


class VideoOps:
    """Static helpers for video processing."""

    @staticmethod
    def find_ffmpeg_executable() -> str | None:
        """Return the ``ffmpeg`` executable path if it is on PATH, else ``None``."""
        return shutil.which("ffmpeg")

    @staticmethod
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

    @staticmethod
    def default_output_path_copy_without_audio(video_path: str) -> str:
        """
        ``dir/foo.ext`` → ``dir/foo_noaudio.ext``, or ``foo_noaudio_N.ext`` if that exists.
        """
        dirname = os.path.dirname(os.path.abspath(video_path)) or "."
        stem, ext = os.path.splitext(os.path.basename(video_path))
        base = os.path.join(dirname, f"{stem}_noaudio")
        candidate = f"{base}{ext}"
        n = 1
        while os.path.exists(candidate):
            candidate = f"{base}_{n}{ext}"
            n += 1
        return candidate

    @staticmethod
    def copy_video_without_audio(
        video_path: str, output_path: str | None = None
    ) -> str:
        """
        Write a new file with audio streams removed (ffmpeg video stream copy, ``-an``).

        Does not modify *video_path*. Default output is a sibling like ``foo_noaudio.ext``
        (see :meth:`default_output_path_copy_without_audio`).

        Returns:
            Path to the written file on success.

        Raises:
            RuntimeError: If the file is not a video, ffmpeg is missing, or processing fails.
        """
        if not is_video_file(video_path):
            raise RuntimeError("Not a video file")
        ffmpeg = VideoOps.find_ffmpeg_executable()
        if not ffmpeg:
            raise RuntimeError("ffmpeg not found on PATH")

        out_path = output_path or VideoOps.default_output_path_copy_without_audio(
            video_path
        )
        if os.path.exists(out_path):
            try:
                os.unlink(out_path)
            except OSError as e:
                raise RuntimeError(f"Could not remove existing output file: {e}") from e

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
            out_path,
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
                if os.path.isfile(out_path):
                    os.unlink(out_path)
            except OSError:
                pass
            raise RuntimeError("ffmpeg timed out while stripping audio") from e
        except OSError as e:
            raise RuntimeError(f"Failed to run ffmpeg: {e}") from e

        if proc.returncode != 0:
            try:
                if os.path.isfile(out_path):
                    os.unlink(out_path)
            except OSError:
                pass
            err = (proc.stderr or proc.stdout or "").strip()
            detail = f": {err}" if err else ""
            raise RuntimeError(f"ffmpeg failed{detail}")

        logger.info("Wrote video without audio: %s", out_path)
        return out_path

    @staticmethod
    def copy_video_without_metadata(
        video_path: str,
        output_path: str | None = None,
    ) -> str:
        """
        Write a **new file** next to the source with container metadata stripped.

        Uses ffmpeg stream copy (no re-encode): ``-map_metadata -1`` removes global
        tags; ``-map_chapters -1`` drops chapters. Does not modify *video_path*.

        If *output_path* is omitted, uses :meth:`default_output_path_copy_without_metadata`.

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

        out = output_path or VideoOps.default_output_path_copy_without_metadata(
            video_path
        )
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

    @staticmethod
    def merge_ffprobe_tag_dicts(probe: dict[str, Any]) -> dict[str, str]:
        """Lowercased keys from format tags + first video stream tags."""
        merged: dict[str, str] = {}
        fmt_tags = (probe.get("format") or {}).get("tags") or {}
        for k, v in fmt_tags.items():
            merged[str(k).lower()] = str(v)
        for s in probe.get("streams") or []:
            if s.get("codec_type") != "video":
                continue
            for k, v in (s.get("tags") or {}).items():
                lk = str(k).lower()
                if lk not in merged:
                    merged[lk] = str(v)
            break
        return merged

    @staticmethod
    def ffprobe_video_mode_and_dims(probe: dict[str, Any]) -> tuple[str, str]:
        """Display strings for first video stream: label (translated) and ``WxH``."""
        vcodec = ""
        width = height = None
        for s in probe.get("streams") or []:
            if s.get("codec_type") == "video":
                vcodec = str(s.get("codec_name") or "")
                width = s.get("width")
                height = s.get("height")
                break
        mode = _("Video ({0})").format(vcodec) if vcodec else _("Video")
        dims = ""
        if width and height:
            dims = f"{int(width)}x{int(height)}"
        return mode, dims

    @staticmethod
    def ffprobe_prompt_fields_from_tags(
        probe: dict[str, Any],
    ) -> tuple[str, str, list[str], list[str], bool]:
        """
        Map container / stream tags to positive & negative prompt fields.

        Returns (positive, negative, models, loras, extraction_failed).
        """
        tags = VideoOps.merge_ffprobe_tag_dicts(probe)
        if not tags:
            return "", "", [], [], True

        positive = (
            tags.get("comment")
            or tags.get("description")
            or tags.get("title")
            or ""
        )
        negative = (
            tags.get("negative")
            or tags.get("negative prompt")
            or tags.get("com.apple.quicktime.description.negative")
            or ""
        )
        if not positive.strip():
            lines = [f"{k}: {v}" for k, v in sorted(tags.items())]
            positive = "\n".join(lines)
        return positive, negative, [], [], False
