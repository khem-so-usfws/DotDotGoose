"""Tests for count-region point highlighting and placement assistance."""

from __future__ import annotations

from PyQt6 import QtCore, QtGui, QtWidgets

from ddg import Canvas
from ddg.annotations import Annotation, AnnotationShape


def _count_region() -> Annotation:
    """Return a simple square count-region annotation."""
    return Annotation(
        label="count_region",
        shape_type=AnnotationShape.POLYGON,
        points=[
            (0.0, 0.0),
            (100.0, 0.0),
            (100.0, 100.0),
            (0.0, 100.0),
        ],
    )


def test_point_outside_count_region_requires_explicit_region(qtbot) -> None:
    """Images without a count region should not flag ordinary bird points."""
    canvas: Canvas = Canvas()

    assert canvas.point_is_outside_count_region(QtCore.QPointF(500.0, 500.0)) is False

    canvas.external_annotations = [_count_region()]

    assert canvas.point_is_outside_count_region(QtCore.QPointF(50.0, 50.0)) is False
    assert canvas.point_is_outside_count_region(QtCore.QPointF(150.0, 50.0)) is True


def test_display_points_marks_only_outside_points(qtbot, monkeypatch) -> None:
    """Outside bird points should receive a distinct warning-ring graphic."""
    canvas: Canvas = Canvas()
    canvas.current_image_name = "IMG_8000.JPG"
    canvas.current_class_name = "COMU"
    canvas.colors = {"COMU": QtGui.QColor("blue")}
    canvas.points = {
        "IMG_8000.JPG": {
            "COMU": [
                QtCore.QPointF(50.0, 50.0),
                QtCore.QPointF(150.0, 50.0),
            ]
        }
    }
    canvas.external_annotations = [_count_region()]
    monkeypatch.setattr(
        canvas,
        "highlight_outside_count_region_points_enabled",
        lambda: True,
    )

    canvas.display_points()

    item_kinds: list[object] = [item.data(0) for item in canvas.items()]
    assert item_kinds.count("ddg_bird_point") == 2
    assert item_kinds.count("ddg_count_region_warning") == 1


def test_outside_point_warning_can_reject_placement(qtbot, monkeypatch) -> None:
    """Rejecting the warning dialog should leave DDG point data unchanged."""
    canvas: Canvas = Canvas()
    canvas.current_image_name = "IMG_8001.JPG"
    canvas.current_class_name = "COMU"
    canvas.points = {"IMG_8001.JPG": {}}
    canvas.external_annotations = [_count_region()]
    monkeypatch.setattr(
        canvas,
        "warn_outside_count_region_point_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "question",
        lambda *args, **kwargs: QtWidgets.QMessageBox.StandardButton.No,
    )

    canvas.add_point(QtCore.QPointF(150.0, 50.0))

    assert canvas.points["IMG_8001.JPG"] == {}
    assert canvas.dirty is False


def test_outside_point_warning_can_be_disabled(qtbot, monkeypatch) -> None:
    """Disabling the warning should allow outside points without prompting."""
    canvas: Canvas = Canvas()
    canvas.current_image_name = "IMG_8002.JPG"
    canvas.current_class_name = "COMU"
    canvas.colors = {"COMU": QtGui.QColor("blue")}
    canvas.points = {"IMG_8002.JPG": {}}
    canvas.external_annotations = [_count_region()]
    monkeypatch.setattr(
        canvas,
        "warn_outside_count_region_point_enabled",
        lambda: False,
    )
    monkeypatch.setattr(
        canvas,
        "highlight_outside_count_region_points_enabled",
        lambda: False,
    )

    canvas.add_point(QtCore.QPointF(150.0, 50.0))

    assert canvas.points["IMG_8002.JPG"]["COMU"] == [
        QtCore.QPointF(150.0, 50.0)
    ]
    assert canvas.dirty is True
