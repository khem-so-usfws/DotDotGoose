"""Regression tests for annotation graphics cleanup during image switching."""

from __future__ import annotations

from typing import Any

from PyQt6 import QtCore, QtGui, QtWidgets

from ddg.central_graphics_view import CentralGraphicsView, InteractionMode


def test_prepare_for_image_change_removes_line_preview(
    qtbot: Any,
) -> None:
    """An in-progress cutline must release its scene item before scene.clear."""
    scene: QtWidgets.QGraphicsScene = QtWidgets.QGraphicsScene()
    view: CentralGraphicsView = CentralGraphicsView()
    qtbot.addWidget(view)
    view.setScene(scene)

    view.start_line_annotation()
    view.line_points = [QtCore.QPointF(10.0, 10.0)]
    view._update_line_preview(QtCore.QPointF(20.0, 20.0))
    assert view.line_preview_item is not None

    view.prepare_for_image_change()
    scene.clear()

    assert view.line_preview_item is None
    assert view.line_points == []
    assert view.interaction_mode is InteractionMode.COUNT


def test_prepare_for_image_change_removes_polygon_preview(
    qtbot: Any,
) -> None:
    """An in-progress polygon must release its scene item before scene.clear."""
    scene: QtWidgets.QGraphicsScene = QtWidgets.QGraphicsScene()
    view: CentralGraphicsView = CentralGraphicsView()
    qtbot.addWidget(view)
    view.setScene(scene)

    view.start_polygon_annotation()
    view.polygon_points = [
        QtCore.QPointF(10.0, 10.0),
        QtCore.QPointF(20.0, 10.0),
    ]
    view._update_polygon_preview(QtCore.QPointF(20.0, 20.0))
    assert view.polygon_preview_item is not None

    view.prepare_for_image_change()
    scene.clear()

    assert view.polygon_preview_item is None
    assert view.polygon_points == []
    assert view.interaction_mode is InteractionMode.COUNT


def test_preview_cleanup_tolerates_item_already_deleted(
    qtbot: Any,
) -> None:
    """Cleanup must tolerate a Qt item that a scene has already destroyed."""
    scene: QtWidgets.QGraphicsScene = QtWidgets.QGraphicsScene()
    view: CentralGraphicsView = CentralGraphicsView()
    qtbot.addWidget(view)
    view.setScene(scene)

    item: QtWidgets.QGraphicsPathItem = scene.addPath(
        QtGui.QPainterPath(QtCore.QPointF(0.0, 0.0))
    )
    view.line_preview_item = item
    scene.clear()

    view._clear_line_preview()
    assert view.line_preview_item is None
