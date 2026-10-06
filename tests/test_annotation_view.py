"""Tests for interactive native point and line annotation modes."""

from __future__ import annotations

from typing import Any

from PyQt6 import QtCore, QtWidgets

from ddg.central_graphics_view import CentralGraphicsView, InteractionMode


def test_finish_line_emits_completed_points(qtbot: Any) -> None:
    """Finishing a valid line should emit its source-image vertices."""
    view: CentralGraphicsView = CentralGraphicsView()
    scene: QtWidgets.QGraphicsScene = QtWidgets.QGraphicsScene()
    view.setScene(scene)
    qtbot.addWidget(view)
    view.start_line_annotation()
    view._add_line_vertex(QtCore.QPointF(10.0, 20.0))
    view._add_line_vertex(QtCore.QPointF(30.0, 40.0))

    with qtbot.waitSignal(view.line_completed) as blocker:
        view.finish_line_annotation()

    points: list[QtCore.QPointF] = blocker.args[0]
    assert [(point.x(), point.y()) for point in points] == [
        (10.0, 20.0),
        (30.0, 40.0),
    ]
    assert view.interaction_mode is InteractionMode.COUNT
    assert view.line_points == []


def test_cancel_line_discards_transient_vertices(qtbot: Any) -> None:
    """Canceling line mode should discard unsaved transient geometry."""
    view: CentralGraphicsView = CentralGraphicsView()
    scene: QtWidgets.QGraphicsScene = QtWidgets.QGraphicsScene()
    view.setScene(scene)
    qtbot.addWidget(view)
    view.start_line_annotation()
    view._add_line_vertex(QtCore.QPointF(10.0, 20.0))

    view.cancel_annotation()

    assert view.interaction_mode is InteractionMode.COUNT
    assert view.line_points == []
    assert view.line_preview_item is None


def test_landmark_click_emits_point_and_returns_to_count(qtbot: Any) -> None:
    """One landmark click should emit one point and leave annotation mode."""
    view: CentralGraphicsView = CentralGraphicsView()
    scene: QtWidgets.QGraphicsScene = QtWidgets.QGraphicsScene()
    scene.setSceneRect(0.0, 0.0, 100.0, 100.0)
    view.setScene(scene)
    view.resize(200, 200)
    view.show()
    qtbot.addWidget(view)
    view.start_landmark_annotation()

    with qtbot.waitSignal(view.annotation_point_completed) as blocker:
        qtbot.mouseClick(
            view.viewport(),
            QtCore.Qt.MouseButton.LeftButton,
            pos=QtCore.QPoint(100, 100),
        )

    point: QtCore.QPointF = blocker.args[0]
    assert 0.0 <= point.x() <= 100.0
    assert 0.0 <= point.y() <= 100.0
    assert view.interaction_mode is InteractionMode.COUNT


def test_selection_mode_delete_requests_annotation_delete(qtbot: Any) -> None:
    """Delete should target native annotations while annotation edit mode is active."""
    view: CentralGraphicsView = CentralGraphicsView()
    scene: QtWidgets.QGraphicsScene = QtWidgets.QGraphicsScene()
    view.setScene(scene)
    qtbot.addWidget(view)
    view.start_annotation_selection()

    with qtbot.waitSignal(view.external_annotation_delete_requested):
        qtbot.keyClick(view, QtCore.Qt.Key.Key_Delete)

    assert view.interaction_mode is InteractionMode.SELECT


def test_escape_leaves_selection_mode(qtbot: Any) -> None:
    """Escape should clear annotation selection mode and return to counting."""
    view: CentralGraphicsView = CentralGraphicsView()
    scene: QtWidgets.QGraphicsScene = QtWidgets.QGraphicsScene()
    view.setScene(scene)
    qtbot.addWidget(view)
    view.start_annotation_selection()

    with qtbot.waitSignal(view.external_annotation_selection_cleared):
        qtbot.keyClick(view, QtCore.Qt.Key.Key_Escape)

    assert view.interaction_mode is InteractionMode.COUNT


def test_annotation_preview_pen_is_cosmetic(qtbot: Any) -> None:
    """Annotation preview weight should remain constant in screen pixels."""
    view: CentralGraphicsView = CentralGraphicsView()
    scene: QtWidgets.QGraphicsScene = QtWidgets.QGraphicsScene()
    view.setScene(scene)
    qtbot.addWidget(view)
    view.start_line_annotation()
    view._add_line_vertex(QtCore.QPointF(10.0, 10.0))
    view._update_line_preview(QtCore.QPointF(20.0, 20.0))

    assert view.line_preview_item is not None
    assert view.line_preview_item.pen().isCosmetic() is True


def test_click_without_drag_does_not_emit_annotation_move_finished(qtbot: Any) -> None:
    """Selecting a shape without moving it should not trigger a disk save."""
    view: CentralGraphicsView = CentralGraphicsView()
    scene: QtWidgets.QGraphicsScene = QtWidgets.QGraphicsScene()
    scene.setSceneRect(0.0, 0.0, 100.0, 100.0)
    item: QtWidgets.QGraphicsRectItem = scene.addRect(20.0, 20.0, 40.0, 40.0)
    item.setData(0, "ddg_external_annotation")
    item.setData(1, 0)
    item.setData(3, "polygon")
    item.setData(4, False)
    view.setScene(scene)
    view.resize(200, 200)
    view.show()
    qtbot.addWidget(view)
    view.start_annotation_selection()
    finished: list[int] = []
    view.external_annotation_move_finished.connect(finished.append)
    viewport_point: QtCore.QPoint = view.mapFromScene(QtCore.QPointF(30.0, 30.0))

    qtbot.mouseClick(
        view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        pos=viewport_point,
    )

    assert finished == []


def test_annotation_draw_mode_does_not_emit_count_point_delete(qtbot: Any) -> None:
    """Delete during polygon drawing must not delete selected DDG count points."""
    view: CentralGraphicsView = CentralGraphicsView()
    scene: QtWidgets.QGraphicsScene = QtWidgets.QGraphicsScene()
    view.setScene(scene)
    qtbot.addWidget(view)
    view.start_polygon_annotation()
    delete_requests: list[bool] = []
    view.delete_selection.connect(lambda: delete_requests.append(True))

    qtbot.keyClick(view, QtCore.Qt.Key.Key_Delete)

    assert delete_requests == []
