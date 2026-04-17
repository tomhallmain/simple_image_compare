"""
Tests for the MediaFrame VLC video-stop deadlock fix.

WEBM files without a Cues (seek-index) element cause libvlc_media_player_stop()
to block indefinitely on the UI thread because VLC performs a sequential linear
scan of the file and that decode loop never cleanly exits when interrupted.
The fix runs stop() in a daemon thread with a 3-second timeout and, if the
timeout fires, replaces the hung player with a fresh instance so the application
stays responsive.
"""

import os
import time

import pytest

from ui.app_window.media_frame import _VLC_AVAILABLE
from tests.test_utils import MALFORMED_WEBM, HangingVlcPlayer

pytestmark = pytest.mark.skipif(
    not _VLC_AVAILABLE, reason="python-vlc not installed"
)


class TestMalformedWebmVlcStop:
    """
    Regression tests for the libvlc_media_player_stop() deadlock with WEBM
    files that have no Cues element (example_malformed_absent_cues.webm).
    """

    def test_video_stop_completes_within_timeout(self, media_frame, qtbot):
        """video_stop() must return within a bounded time on the malformed WEBM.

        Before the fix this call would block the UI thread indefinitely.
        """
        assert os.path.isfile(MALFORMED_WEBM), (
            f"Test asset not found: {MALFORMED_WEBM}"
        )

        media_frame.show_video(MALFORMED_WEBM)
        # Give VLC a moment to enter its processing/scan state before stopping.
        qtbot.wait(500)

        start = time.monotonic()
        media_frame.video_stop()
        elapsed = time.monotonic() - start

        # Must complete within the 3-second thread timeout plus generous margin.
        assert elapsed < 5.0, (
            f"video_stop() blocked for {elapsed:.1f}s — deadlock fix may be broken"
        )

    def test_hanging_stop_triggers_player_replacement(self, media_frame):
        """When stop() exceeds the timeout the hung player must be replaced.

        Injects VideoUI state and swaps in HangingVlcPlayer directly, without
        loading real media.  Loading real media would leave a live VLC player
        in the background while the daemon thread's 30-second sleep outlasts
        fixture teardown, causing a use-after-free segfault when dispose_vlc()
        releases the VLC instance.  An idle player has no such interaction.
        """
        from ui.app_window.media_frame import VideoUI

        media_frame._video_ui = VideoUI("fake.webm")

        original_player = media_frame.vlc_media_player
        hanging = HangingVlcPlayer(original_player)
        media_frame.vlc_media_player = hanging

        media_frame.video_stop()

        assert hanging.stop_called.is_set(), "stop() was never called on the player"
        assert media_frame.vlc_media_player is not None, (
            "vlc_media_player was not replaced after stop() timed out"
        )
        assert media_frame.vlc_media_player is not hanging, (
            "hung player was not replaced — _replace_vlc_player() may not have run"
        )

    def test_replace_vlc_player_produces_a_new_player(self, media_frame):
        """_replace_vlc_player() must always set vlc_media_player to a fresh instance."""
        original = media_frame.vlc_media_player
        media_frame._replace_vlc_player()
        new_player = media_frame.vlc_media_player

        assert new_player is not None
        assert new_player is not original

    def test_frame_usable_after_malformed_webm_stop(self, media_frame, qtbot, tmp_path):
        """After the VLC hang+replace cycle, the frame must display the next file correctly.

        Simulates the state left by video_stop() timing out (VideoUI set, player
        replaced) without loading real WEBM media.  Loading the malformed WEBM here
        would leave a libvlc_media_player_stop() daemon thread that outlasts the
        fixture's vlc_instance lifetime; that crash scenario is instead handled by
        the _vlc_instances_pending_cleanup guard in dispose_vlc(), exercised
        implicitly by test_video_stop_completes_within_timeout.
        """
        from PIL import Image
        from ui.app_window.media_frame import VideoUI

        png_path = str(tmp_path / "next.png")
        Image.new("RGB", (10, 10), (128, 200, 50)).save(png_path, format="PNG")

        # Mirror exactly what video_stop() leaves behind after a stop() timeout:
        # _video_ui is set (frame thinks it's in video mode) and the player has
        # already been replaced with a fresh idle instance.
        media_frame._video_ui = VideoUI("fake.webm")
        media_frame._replace_vlc_player()

        # show_image internally calls video_stop() before switching to image mode.
        media_frame.show_image(png_path)

        qtbot.waitUntil(lambda: media_frame.image_displayed, timeout=3000)
        assert media_frame.image_displayed
