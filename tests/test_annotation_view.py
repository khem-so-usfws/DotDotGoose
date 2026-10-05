"""Tests for interactive native point and line annotation modes."""

from __future__ import annotations

from PyQt6 import QtCore, QtWidgets

from ddg.central_graphics_view import CentralGraphicsView, InteractionMode


def test_finish_line_emits_completed_points(qtbot) -> None:
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


def test_cancel_line_discards_transient_vertices(qtbot) -> None:
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


def test_landmark_click_emits_point_and_returns_to_count(qtbot) -> None:
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


def test_selection_mode_delete_requests_annotation_delete(qtbot) -> None:
    """Delete should target native annotations while annotation edit mode is active."""
    view: CentralGraphicsView = CentralGraphicsView()
    scene: QtWidgets.QGraphicsScene = QtWidgets.QGraphicsScene()
    view.setScene(scene)
    qtbot.addWidget(view)
    view.start_annotation_selection()

    with qtbot.waitSignal(view.external_annotation_delete_requested):
        qtbot.keyClick(view, QtCore.Qt.Key.Key_Delete)

    assert view.interaction_mode is InteractionMode.SELECT


def test_escape_leaves_selection_mode(qtbot) -> None:
    """Escape should clear annotation selection mode and return to counting."""
    view: CentralGraphicsView = CentralGraphicsView()
    scene: QtWidgets.QGraphicsScene = QtWidgets.QGraphicsScene()
    view.setScene(scene)
    qtbot.addWidget(view)
    view.start_annotation_selection()

    with qtbot.waitSignal(view.external_annotation_selection_cleared):
        qtbot.keyClick(view, QtCore.Qt.Key.Key_Escape)

    assert view.interaction_mode is InteractionMode.COUNT
