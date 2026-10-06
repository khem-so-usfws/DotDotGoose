"""Tests for interactive native polygon annotation mode."""

from __future__ import annotations

from PyQt6 import QtCore, QtWidgets

from ddg.central_graphics_view import CentralGraphicsView, InteractionMode


def test_finish_polygon_emits_completed_points(qtbot) -> None:
    """Finishing a valid polygon should emit its source-image vertices."""
    view: CentralGraphicsView = CentralGraphicsView()
    scene: QtWidgets.QGraphicsScene = QtWidgets.QGraphicsScene()
    view.setScene(scene)
    qtbot.addWidget(view)
    view.start_polygon_annotation()
    view._add_polygon_vertex(QtCore.QPointF(10.0, 20.0))
    view._add_polygon_vertex(QtCore.QPointF(30.0, 20.0))
    view._add_polygon_vertex(QtCore.QPointF(30.0, 40.0))

    with qtbot.waitSignal(view.polygon_completed) as blocker:
        view.finish_polygon_annotation()

    points: list[QtCore.QPointF] = blocker.args[0]
    assert [(point.x(), point.y()) for point in points] == [
        (10.0, 20.0),
        (30.0, 20.0),
        (30.0, 40.0),
    ]
    assert view.interaction_mode is InteractionMode.COUNT
    assert view.polygon_points == []


def test_cancel_polygon_discards_transient_vertices(qtbot) -> None:
    """Canceling polygon mode should discard unsaved transient geometry."""
    view: CentralGraphicsView = CentralGraphicsView()
    scene: QtWidgets.QGraphicsScene = QtWidgets.QGraphicsScene()
    view.setScene(scene)
    qtbot.addWidget(view)
    view.start_polygon_annotation()
    view._add_polygon_vertex(QtCore.QPointF(10.0, 20.0))

    view.cancel_annotation()

    assert view.interaction_mode is InteractionMode.COUNT
    assert view.polygon_points == []
    assert view.polygon_preview_item is None
