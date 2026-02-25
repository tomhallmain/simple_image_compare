"""
Media frame (PySide6): album art and optional in-window video.
Port of ui/media_frame.py. Uses QGraphicsView for images (pan/zoom), VLC for video.
"""

import os
import platform
import time
import warnings

from PySide6.QtWidgets import (
    QFrame,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsPixmapItem,
    QVBoxLayout,
    QLabel,
    QSizePolicy,
    QApplication,
    QDialog,
)
from PySide6.QtCore import Qt, QRectF, QSize, QPoint, QRect, QEvent, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap, QImageReader, QPainter, QCursor

from ui.app_style import AppStyle
from ui.app_window.media_controls_overlay import MediaControlsOverlay, OVERLAY_HEIGHT
from utils.config import config
from utils.translations import I18N

_ = I18N._

# Optional: Pillow for formats Qt may not support (HEIC, AVIF, etc.)
try:
    from PIL import Image
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

try:
    import vlc
    _VLC_AVAILABLE = True
except ImportError:
    _VLC_AVAILABLE = False


# Default video extensions if config.video_types is not set
DEFAULT_VIDEO_TYPES = (".mp4", ".mkv", ".avi", ".webm", ".mov", ".m4v", ".ogv")


class VideoUI:
    """Placeholder for video state (path, active)."""

    def __init__(self, filepath):
        self.filepath = filepath
        self.active = False


def scale_dims(dims, max_dims, maximize=False):
    """Return (width, height) to fit dims inside max_dims. If maximize, fill when smaller."""
    x, y = dims[0], dims[1]
    max_x, max_y = max_dims[0], max_dims[1]
    if x <= max_x and y <= max_y:
        if maximize:
            if x < max_x:
                return (int(x * max_y / y), max_y)
            elif y < max_y:
                return (max_x, int(y * max_x / x))
        return (x, y)
    elif x <= max_x:
        return (int(x * max_y / y), max_y)
    elif y <= max_y:
        return (max_x, int(y * max_x / x))
    else:
        x_scale = max_x / x
        y_scale = max_y / y
        if x_scale < y_scale:
            return (int(x * x_scale), int(y * x_scale))
        return (int(x * y_scale), int(y * y_scale))


class MediaFrame(QFrame):
    """
    Display image (with pan/zoom via QGraphicsView) and optional in-window video via VLC.
    Provides winId() for VLC embedding (used by muse/playback.py).
    """
    seek_requested = Signal(int)
    play_pause_requested = Signal()
    volume_requested = Signal(int)
    mute_requested = Signal()

    def __init__(self, parent=None, fill_canvas=False):
        super().__init__(parent)
        self.setMinimumSize(320, 320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(f"background-color: {AppStyle.MEDIA_BG};")
        self.setMouseTracking(True)

        self.fill_canvas = fill_canvas
        self.path = "."
        self.imscale = 1.0
        self.imwidth = 0
        self.imheight = 0
        self.image_displayed = False

        self._image = None  # QImage or PIL Image when loaded
        self._video_ui = None  # VideoUI when showing video
        self._current_pixmap = None  # keep reference

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._graphics_view = QGraphicsView(self)
        self._graphics_view.setRenderHint(
            QPainter.RenderHint.SmoothPixmapTransform, True
        )
        self._graphics_view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self._graphics_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._graphics_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._graphics_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._graphics_view.setStyleSheet(f"background-color: {AppStyle.MEDIA_BG};")
        self._scene = QGraphicsScene(self)
        self._graphics_view.setScene(self._scene)
        self._pixmap_item = QGraphicsPixmapItem()
        self._scene.addItem(self._pixmap_item)
        layout.addWidget(self._graphics_view)

        self._placeholder_label = QLabel(_("Album art"), self)
        self._placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder_label.setStyleSheet(f"color: {AppStyle.FG_COLOR};")
        layout.addWidget(self._placeholder_label)
        self._placeholder_label.hide()

        if _VLC_AVAILABLE:
            self.vlc_instance = vlc.Instance()
            self.vlc_media_player = self.vlc_instance.media_player_new()
            self.vlc_media_player.video_set_mouse_input(False)
            self.vlc_media_player.video_set_key_input(False)
            self.vlc_media = None
        else:
            self.vlc_instance = None
            self.vlc_media_player = None
            self.vlc_media = None

        self._controls_overlay = MediaControlsOverlay(self)
        self._controls_overlay.seek_requested.connect(self.seek_requested.emit)
        self._controls_overlay.play_pause_requested.connect(self.play_pause_requested.emit)
        self._controls_overlay.volume_changed.connect(self.volume_requested.emit)
        self._controls_overlay.mute_toggled.connect(self.mute_requested.emit)
        self._window_filter_installed = False
        self._mouse_inside = False
        self._last_cursor_pos = None
        self._last_known_volume = 100
        self._last_known_muted = False

        self._mouse_poll_timer = QTimer(self)
        self._mouse_poll_timer.setInterval(100)
        self._mouse_poll_timer.timeout.connect(self._poll_mouse_position)
        self._mouse_poll_timer.start()

        self._playback_timer = QTimer(self)
        self._playback_timer.setInterval(250)
        self._playback_timer.timeout.connect(self._update_vlc_playback_progress)

    def set_background_color(self, background_color):
        color = background_color or AppStyle.MEDIA_BG
        self.setStyleSheet(f"background-color: {color};")
        self._graphics_view.setStyleSheet(f"background-color: {color};")

    def _video_types(self):
        return getattr(config, "video_types", DEFAULT_VIDEO_TYPES)

    def _is_video_path(self, path):
        if not path:
            return False
        path_lower = path.lower()
        return any(path_lower.endswith(ext) for ext in self._video_types())

    def _load_image_to_qimage(self, path):
        """Load path to QImage; use QImageReader first, fallback to Pillow if available."""
        reader = QImageReader(path)
        img = reader.read()
        if not img.isNull():
            return img
        if _PIL_AVAILABLE:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                try:
                    pil_img = Image.open(path)
                    pil_img = pil_img.convert("RGB")
                    data = pil_img.tobytes("raw", "RGB")
                    return QImage(data, pil_img.width, pil_img.height, QImage.Format.Format_RGB888)
                except Exception as e:
                    if "truncated" in str(e):
                        time.sleep(0.25)
                        pil_img = Image.open(path)
                        pil_img = pil_img.convert("RGB")
                        data = pil_img.tobytes("raw", "RGB")
                        return QImage(data, pil_img.width, pil_img.height, QImage.Format.Format_RGB888)
                    raise
        return QImage()

    def _show_image_in_view(self, path):
        """Load image from path, display at full resolution in QGraphicsView.

        The view's ``SmoothPixmapTransform`` render hint handles the
        down-scaling to screen size in a single pass, avoiding the
        quality loss of a double-scale (pre-scale then fitInView).
        """
        if not path or path == "." or not os.path.exists(path):
            return
        qimg = self._load_image_to_qimage(path)
        if qimg.isNull():
            return
        self._image = qimg
        self.imwidth = qimg.width()
        self.imheight = qimg.height()

        pix = QPixmap.fromImage(qimg)
        self._current_pixmap = pix
        self._pixmap_item.setPixmap(pix)
        self._scene.setSceneRect(QRectF(pix.rect()))
        self._graphics_view.fitInView(
            self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio
        )
        self._graphics_view.show()
        self._placeholder_label.hide()
        self.image_displayed = True

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_overlay()
        if self.image_displayed and self.path and self.path != "." and not isinstance(self._video_ui, VideoUI):
            self._show_image_in_view(self.path)

    def show_image(self, path):
        """Show image or video at path. Dispatches to show_video when appropriate."""
        if isinstance(self._video_ui, VideoUI):
            self.video_stop()
        self.path = path or "."
        if not path or path == "." or path.strip() == "" or not os.path.exists(path):
            self.clear()
            return
        # Video dispatch: use VLC if available, otherwise show placeholder
        if self._is_video_path(path):
            if _VLC_AVAILABLE and self.vlc_media_player:
                self.show_video(path)
            else:
                self._show_placeholder(_("Video: ") + os.path.basename(path))
            return
        self._video_ui = None
        self.imscale = 1.0
        self._show_image_in_view(self.path)

    def show_video(self, path):
        """Play video in this frame (VLC embeds via winId())."""
        if not _VLC_AVAILABLE or not self.vlc_media_player:
            return
        path_lower = (path or "").lower()
        if not any(path_lower.endswith(ext) for ext in self._video_types()):
            return
        self.clear()
        self._video_ui = VideoUI(path)
        self.path = path
        self.ensure_video_frame()
        self.vlc_media = self.vlc_instance.media_new(path)
        self.vlc_media_player.set_media(self.vlc_media)
        if self.vlc_media_player.play() == -1:
            raise Exception("Failed to play video")
        self._graphics_view.hide()
        self._placeholder_label.hide()
        self.on_track_changed()
        self._sync_overlay_volume_state(force=True)
        self._playback_timer.start()

    def ensure_video_frame(self):
        """Set the window id for VLC video output."""
        if not _VLC_AVAILABLE or not self.vlc_media_player:
            return
        wid = int(self.winId()) if self.winId() else 0
        if not wid:
            return
        if platform.system() == "Windows":
            self.vlc_media_player.set_hwnd(wid)
        elif platform.system() == "Darwin":
            self.vlc_media_player.set_nsobject(wid)
        else:
            self.vlc_media_player.set_xwindow(wid)

    def video_display(self):
        """Start video playback (after ensure_video_frame)."""
        if not _VLC_AVAILABLE or not self.vlc_media_player or not self.path:
            return
        self.ensure_video_frame()
        self.vlc_media = self.vlc_instance.media_new(self.path)
        self.vlc_media_player.set_media(self.vlc_media)
        if self.vlc_media_player.play() == -1:
            raise Exception("Failed to play video")
        self.on_track_changed()
        self._sync_overlay_volume_state(force=True)
        self._playback_timer.start()

    def close(self):
        self.video_stop()

    def video_stop(self):
        if _VLC_AVAILABLE and self.vlc_media_player:
            self.vlc_media_player.stop()
        self._video_ui = None
        self.on_playback_stopped()
        self._playback_timer.stop()

    def video_pause(self):
        if _VLC_AVAILABLE and self.vlc_media_player:
            self.vlc_media_player.set_pause(1)
            self.set_playback_paused(True)

    def video_play(self):
        if not _VLC_AVAILABLE or not self.vlc_media_player:
            return
        state = self.vlc_media_player.get_state()
        if state in (vlc.State.Stopped, vlc.State.Ended):
            self.video_display()
        else:
            self.vlc_media_player.set_pause(0)
        self.set_playback_paused(False)
        self._playback_timer.start()

    def video_toggle_pause(self):
        if not _VLC_AVAILABLE or not self.vlc_media_player:
            return
        if self.vlc_media_player.is_playing():
            self.video_pause()
        else:
            self.video_play()

    def video_take_screenshot(self):
        if _VLC_AVAILABLE and self.vlc_media_player:
            try:
                self.vlc_media_player.video_take_snapshot(0, "", 0, 0)
            except Exception:
                pass

    def video_seek(self, pos):
        if _VLC_AVAILABLE and self.vlc_media_player:
            self.vlc_media_player.set_position(pos)

    def video_seek_ms(self, position_ms: int):
        if not _VLC_AVAILABLE or not self.vlc_media_player:
            return
        duration_ms = self.vlc_media_player.get_length()
        if duration_ms <= 0:
            return
        bounded = max(0, min(int(position_ms), int(duration_ms)))
        self.vlc_media_player.set_time(bounded)

    def set_volume(self, volume: int):
        bounded = max(0, min(int(volume), 100))
        if _VLC_AVAILABLE and self.vlc_media_player:
            self.vlc_media_player.audio_set_volume(bounded)
            if bounded > 0 and self.vlc_media_player.audio_get_mute():
                self.vlc_media_player.audio_set_mute(False)
        self._last_known_volume = bounded
        self._last_known_muted = self.is_muted()
        self._sync_overlay_volume_state(force=True)

    def get_volume(self) -> int:
        if _VLC_AVAILABLE and self.vlc_media_player:
            volume = int(self.vlc_media_player.audio_get_volume() or 0)
            if volume >= 0:
                return volume
        return self._last_known_volume

    def set_mute(self, muted: bool):
        if _VLC_AVAILABLE and self.vlc_media_player:
            self.vlc_media_player.audio_set_mute(bool(muted))
        self._last_known_muted = bool(muted)
        self._sync_overlay_volume_state(force=True)

    def toggle_mute(self):
        if _VLC_AVAILABLE and self.vlc_media_player:
            self.vlc_media_player.audio_toggle_mute()
        else:
            self._last_known_muted = not self._last_known_muted
        self._sync_overlay_volume_state(force=True)

    def is_muted(self) -> bool:
        if _VLC_AVAILABLE and self.vlc_media_player:
            return bool(self.vlc_media_player.audio_get_mute())
        return self._last_known_muted

    def clear(self):
        if isinstance(self._video_ui, VideoUI):
            self.video_stop()
        self._video_ui = None
        self._scene.clear()
        self._pixmap_item = QGraphicsPixmapItem()
        self._scene.addItem(self._pixmap_item)
        self._current_pixmap = None
        self._image = None
        self.image_displayed = False
        self._graphics_view.show()
        self._placeholder_label.setText(_("Album art"))
        self._placeholder_label.show()
        self._controls_overlay.dismiss()

    def _show_placeholder(self, text: str) -> None:
        """Clear the view and show a text placeholder (e.g. for unsupported video)."""
        self.clear()
        self._placeholder_label.setText(text)

    def release_media(self):
        if isinstance(self._video_ui, VideoUI):
            self.video_stop()
        elif self._image is not None:
            self._image = None
        self._current_pixmap = None
        self._pixmap_item.setPixmap(QPixmap())
        self.image_displayed = False
        self._controls_overlay.dismiss()

    def focus(self, refresh_image=False):
        self.setFocus(Qt.FocusReason.OtherFocusReason)
        if refresh_image and self.path:
            self.show_image(self.path)

    def redraw_figures(self):
        """Dummy for compatibility with children that override."""
        pass

    def _position_overlay(self):
        """Place the controls overlay at the bottom of the frame in global coords."""
        h = OVERLAY_HEIGHT
        bottom_left = self.mapToGlobal(QPoint(0, self.height() - h))
        self._controls_overlay.setGeometry(bottom_left.x(), bottom_left.y(), self.width(), h)

    def _ensure_window_filter(self):
        if self._window_filter_installed:
            return
        top = self.window()
        if top and top is not self:
            top.installEventFilter(self)
            self._window_filter_installed = True

    def eventFilter(self, watched, event):
        etype = event.type()
        if etype in (QEvent.Type.Move, QEvent.Type.Resize, QEvent.Type.WindowStateChange):
            self._position_overlay()
        return super().eventFilter(watched, event)

    def moveEvent(self, event):
        super().moveEvent(event)
        self._position_overlay()

    def showEvent(self, event):
        super().showEvent(event)
        self._ensure_window_filter()
        self._position_overlay()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._mouse_inside = False
        self._controls_overlay.dismiss()

    def _poll_mouse_position(self):
        if not self.isVisible() or not isinstance(self._video_ui, VideoUI):
            return
        app = QApplication.instance()
        top_window = self.window()
        active_window = app.activeWindow() if app is not None else None

        if self._has_visible_child_dialog(top_window):
            self._mouse_inside = False
            self._controls_overlay.dismiss()
            self._last_cursor_pos = QCursor.pos()
            return

        # Hide controls whenever a different top-level window is active
        # (e.g. a dialog opened from this window), so the overlay never
        # obscures dialog content.
        if active_window is None or active_window is not top_window:
            self._mouse_inside = False
            self._controls_overlay.dismiss()
            self._last_cursor_pos = QCursor.pos()
            return

        cursor = QCursor.pos()
        frame_rect = QRect(self.mapToGlobal(QPoint(0, 0)), self.size())
        overlay_geo = self._controls_overlay.geometry()
        inside = frame_rect.contains(cursor) or overlay_geo.contains(cursor)
        moved = self._last_cursor_pos is None or cursor != self._last_cursor_pos

        if inside:
            self._mouse_inside = True
            # Movement within the media area is the activity signal.
            # If the cursor stays still, the overlay auto-hides.
            if moved:
                self._position_overlay()
                self._controls_overlay.show_overlay()
        elif not inside and self._mouse_inside:
            self._mouse_inside = False
            self._controls_overlay.hide_overlay()
        self._last_cursor_pos = cursor

    def _has_visible_child_dialog(self, top_window) -> bool:
        """Return True when any visible QDialog is owned by this window."""
        app = QApplication.instance()
        if app is None or top_window is None:
            return False
        for widget in app.topLevelWidgets():
            if widget is top_window or widget is self._controls_overlay:
                continue
            if not widget.isVisible() or not isinstance(widget, QDialog):
                continue
            parent = widget.parentWidget()
            while parent is not None:
                if parent is top_window:
                    return True
                parent = parent.parentWidget()
        return False

    def _update_vlc_playback_progress(self):
        """Poll VLC and feed progress/paused state to the overlay."""
        if not _VLC_AVAILABLE or not self.vlc_media_player or not isinstance(self._video_ui, VideoUI):
            return

        duration_ms = max(int(self.vlc_media_player.get_length() or 0), 0)
        current_ms = max(int(self.vlc_media_player.get_time() or 0), 0)
        if duration_ms > 0:
            self.update_playback_progress(current_ms, duration_ms)
        self.set_playback_paused(not bool(self.vlc_media_player.is_playing()))
        self._sync_overlay_volume_state()

    def _sync_overlay_volume_state(self, force: bool = False):
        """Keep overlay mute/volume controls in sync with VLC state."""
        volume = self.get_volume()
        muted = self.is_muted()
        if force or volume != self._last_known_volume or muted != self._last_known_muted:
            self._last_known_volume = volume
            self._last_known_muted = muted
            self._controls_overlay.set_volume_state(volume, muted)

    def get_media_frame_handle(self):
        """Return window id for VLC embedding (muse/playback.py)."""
        wid = self.winId()
        return int(wid) if wid else None

    # ------------------------------------------------------------------
    # Playback progress & overlay
    # ------------------------------------------------------------------
    def update_playback_progress(self, current_ms: int, duration_ms: int):
        self._controls_overlay.update_progress(current_ms, duration_ms)

    def set_playback_paused(self, paused: bool):
        self._controls_overlay.set_paused(paused)

    def on_track_changed(self):
        self._controls_overlay.on_track_changed()

    def on_playback_stopped(self):
        self._controls_overlay.on_playback_stopped()
