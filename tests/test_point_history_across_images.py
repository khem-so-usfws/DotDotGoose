"""Regression tests for mixed point/annotation history across image changes."""

from __future__ import annotations

from PyQt6 import QtCore, QtGui

from ddg import Canvas


def test_point_undo_targets_original_image_after_navigation(qtbot, monkeypatch) -> None:
    """Undoing a point after switching images must modify its source image."""
    canvas: Canvas = Canvas()
    canvas.points = {"A.JPG": {}, "B.JPG": {}}
    canvas.colors = {"CLASS": QtGui.QColor("blue")}
    canvas.current_image_name = "A.JPG"
    canvas.current_class_name = "CLASS"
    monkeypatch.setattr(canvas, "display_points", lambda: None)
    monkeypatch.setattr(
        canvas, "warn_outside_count_region_point_enabled", lambda: False
    )
    point: QtCore.QPointF = QtCore.QPointF(10.0, 20.0)

    canvas.add_point(point)
    canvas.current_image_name = "B.JPG"
    canvas.undo()

    assert canvas.points["A.JPG"]["CLASS"] == []
    assert canvas.points["B.JPG"] == {}

    canvas.redo()
    assert canvas.points["A.JPG"]["CLASS"] == [point]
    assert canvas.points["B.JPG"] == {}
