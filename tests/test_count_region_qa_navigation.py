"""Tests for final count-region QA navigation behavior."""

from __future__ import annotations

from PyQt6 import QtCore

from ddg import Canvas
from ddg.annotations import Annotation, AnnotationShape
from ddg.count_region_qa_dialog import CountRegionQADialog


def _count_region() -> Annotation:
    """Return a square count region for QA tests."""
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


def test_outside_count_region_points_returns_only_outside_points(qtbot) -> None:
    """Outside-point enumeration should retain class and source coordinates."""
    canvas: Canvas = Canvas()
    canvas.current_image_name = "IMG_9000.JPG"
    canvas.external_annotations = [_count_region()]
    canvas.points = {
        "IMG_9000.JPG": {
            "COMU": [QtCore.QPointF(10.0, 10.0), QtCore.QPointF(150.0, 20.0)],
            "WEGU": [QtCore.QPointF(200.0, 30.0)],
        }
    }

    outside: list[tuple[str, QtCore.QPointF]] = canvas.outside_count_region_points()

    assert [(class_name, point.x(), point.y()) for class_name, point in outside] == [
        ("COMU", 150.0, 20.0),
        ("WEGU", 200.0, 30.0),
    ]


def test_outside_count_region_points_empty_without_explicit_region(qtbot) -> None:
    """Images without a count region should have no QA outside-point list."""
    canvas: Canvas = Canvas()
    canvas.current_image_name = "IMG_9001.JPG"
    canvas.points = {
        "IMG_9001.JPG": {"COMU": [QtCore.QPointF(150.0, 20.0)]}
    }

    assert canvas.outside_count_region_points() == []


def test_qa_dialog_navigates_outside_points(qtbot) -> None:
    """Next/previous controls should emit the corresponding source point."""
    dialog: CountRegionQADialog = CountRegionQADialog(
        summary_lines=["Outside count region: 2"],
        outside_points=[
            ("COMU", QtCore.QPointF(150.0, 20.0)),
            ("WEGU", QtCore.QPointF(200.0, 30.0)),
        ],
    )
    qtbot.addWidget(dialog)
    requested: list[QtCore.QPointF] = []
    dialog.point_requested.connect(
        lambda point: requested.append(QtCore.QPointF(point))
    )

    dialog.focus_current_point()
    dialog.next_point()
    dialog.previous_point()

    assert [(point.x(), point.y()) for point in requested] == [
        (150.0, 20.0),
        (200.0, 30.0),
        (150.0, 20.0),
    ]
