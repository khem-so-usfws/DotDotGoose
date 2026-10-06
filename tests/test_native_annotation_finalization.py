"""Regression tests for native-annotation v1 user-facing behavior."""

from __future__ import annotations

from typing import Any

from ddg.main_window import MainWindow


def test_count_mode_status_uses_generic_point_wording(qtbot: Any) -> None:
    """The count-mode reminder should describe generic DDG points."""
    window: MainWindow = MainWindow()
    qtbot.addWidget(window)

    window.annotation_mode_changed("count")

    message: str = window.statusBar().currentMessage()
    assert "click adds a point" in message
    assert "Shift+drag selects points" in message
    assert "C+drag pans" in message
    assert "Z+drag zooms in" in message
    assert "X+drag zooms out" in message
    assert "bird" not in message.lower()
