"""
Qt media widget fixtures.
"""

import pytest


@pytest.fixture
def media_frame(qtbot):
    """A visible MediaFrame, cleaned up via dispose_vlc after each test."""
    from ui.app_window.media_frame import MediaFrame
    frame = MediaFrame()
    qtbot.addWidget(frame)
    frame.show()
    qtbot.waitExposed(frame)
    # The mouse-poll timer fires every 100 ms and calls show_overlay() on the
    # controls overlay, which calls show() on a top-level positioned widget.
    # In a headless offscreen environment that segfaults accessing screen
    # geometry, so stop the timer for all media frame tests.
    frame._mouse_poll_timer.stop()
    yield frame
    try:
        frame.dispose_vlc()
    except Exception:
        pass
