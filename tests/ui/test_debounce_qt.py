"""UI tests for lib/debounce_qt.py — QtDebouncer."""

import pytest
from PySide6.QtWidgets import QWidget

from lib.debounce_qt import QtDebouncer


def test_callback_fires_after_delay(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    calls = []

    debouncer = QtDebouncer(parent, delay_seconds=0.05, callback=lambda: calls.append(1))
    debouncer.schedule()

    qtbot.waitUntil(lambda: len(calls) == 1, timeout=500)
    assert calls == [1]


def test_rapid_schedules_coalesce_to_one_call(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    calls = []

    debouncer = QtDebouncer(parent, delay_seconds=0.05, callback=lambda: calls.append(1))
    for _ in range(5):
        debouncer.schedule()

    qtbot.waitUntil(lambda: len(calls) >= 1, timeout=500)
    qtbot.wait(150)  # allow any extra firings to land
    assert calls == [1]


def test_cancel_prevents_callback(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    calls = []

    debouncer = QtDebouncer(parent, delay_seconds=0.1, callback=lambda: calls.append(1))
    debouncer.schedule()
    debouncer.cancel()

    qtbot.wait(200)
    assert calls == []


def test_callback_receives_args(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    received = []

    debouncer = QtDebouncer(parent, delay_seconds=0.05, callback=lambda x, y: received.append((x, y)))
    debouncer.schedule("a", "b")

    qtbot.waitUntil(lambda: len(received) == 1, timeout=500)
    assert received[0] == ("a", "b")


def test_last_args_win_on_coalesce(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    received = []

    debouncer = QtDebouncer(parent, delay_seconds=0.05, callback=lambda v: received.append(v))
    debouncer.schedule("first")
    debouncer.schedule("last")

    qtbot.waitUntil(lambda: len(received) == 1, timeout=500)
    assert received[0] == "last"


def test_reschedule_after_cancel_fires(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    calls = []

    debouncer = QtDebouncer(parent, delay_seconds=0.05, callback=lambda: calls.append(1))
    debouncer.schedule()
    debouncer.cancel()
    debouncer.schedule()

    qtbot.waitUntil(lambda: len(calls) == 1, timeout=500)
    assert calls == [1]
