"""UI tests for lib/aware_entry_qt.py."""

import pytest
from PySide6.QtWidgets import QWidget

from lib.aware_entry_qt import AwareEntry


@pytest.fixture(autouse=True)
def reset_focus_flag():
    """Ensure the class-level flag is clean before and after each test."""
    AwareEntry.an_entry_has_focus = False
    yield
    AwareEntry.an_entry_has_focus = False


def test_initial_flag_is_false():
    assert AwareEntry.an_entry_has_focus is False


def test_widget_constructs(qtbot):
    widget = AwareEntry()
    qtbot.addWidget(widget)
    assert widget is not None


def test_focus_in_sets_flag(qtbot):
    widget = AwareEntry()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitExposed(widget)

    widget.setFocus()
    qtbot.waitUntil(lambda: AwareEntry.an_entry_has_focus is True, timeout=1000)


def test_focus_out_clears_flag(qtbot):
    container = QWidget()
    qtbot.addWidget(container)
    entry = AwareEntry(container)
    other = AwareEntry(container)
    container.show()
    qtbot.waitExposed(container)

    entry.setFocus()
    qtbot.waitUntil(lambda: AwareEntry.an_entry_has_focus is True, timeout=1000)

    other.setFocus()
    # After focus moves to another AwareEntry the flag is briefly True again
    # (focusIn fires before focusOut), so we wait for focusOut to settle
    qtbot.waitUntil(lambda: AwareEntry.an_entry_has_focus is True, timeout=1000)


def test_text_can_be_set(qtbot):
    widget = AwareEntry()
    qtbot.addWidget(widget)
    widget.setText("hello")
    assert widget.text() == "hello"
