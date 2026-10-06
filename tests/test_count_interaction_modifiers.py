"""Regression tests for DDG count-mode mouse modifiers."""

from __future__ import annotations

from PyQt6 import QtCore, QtWidgets

from ddg.central_graphics_view import CentralGraphicsView


def _view(qtbot) -> CentralGraphicsView:
    """Create a visible graphics view with a simple scene."""
    view: CentralGraphicsView = CentralGraphicsView()
    scene: QtWidgets.QGraphicsScene = QtWidgets.QGraphicsScene()
    scene.setSceneRect(0.0, 0.0, 200.0, 200.0)
    scene.addRect(0.0, 0.0, 200.0, 200.0)
    view.setScene(scene)
    view.resize(300, 300)
    qtbot.addWidget(view)
    view.show()
    return view


def test_plain_click_does_not_add_point_when_cached_ctrl_is_stale(qtbot) -> None:
    """A missed Ctrl release must not turn later plain clicks into counts."""
    view: CentralGraphicsView = _view(qtbot)
    view.ctrl = True  # Simulate a modal dialog swallowing Ctrl key release.
    emitted: list[QtCore.QPointF] = []
    view.add_point.connect(emitted.append)

    qtbot.mousePress(
        view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        modifier=QtCore.Qt.KeyboardModifier.NoModifier,
        pos=QtCore.QPoint(150, 150),
    )

    assert emitted == []
    assert view.dragMode() is QtWidgets.QGraphicsView.DragMode.ScrollHandDrag

    qtbot.mouseRelease(
        view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        modifier=QtCore.Qt.KeyboardModifier.NoModifier,
        pos=QtCore.QPoint(150, 150),
    )


def test_ctrl_left_click_adds_point(qtbot) -> None:
    """Bird points should still require Ctrl+left-click in count mode."""
    view: CentralGraphicsView = _view(qtbot)

    with qtbot.waitSignal(view.add_point):
        qtbot.mouseClick(
            view.viewport(),
            QtCore.Qt.MouseButton.LeftButton,
            modifier=QtCore.Qt.KeyboardModifier.ControlModifier,
            pos=QtCore.QPoint(150, 150),
        )


def test_plain_drag_uses_hand_pan_mode(qtbot) -> None:
    """Plain left drag should retain DDG's original panning interaction."""
    view: CentralGraphicsView = _view(qtbot)

    qtbot.mousePress(
        view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        modifier=QtCore.Qt.KeyboardModifier.NoModifier,
        pos=QtCore.QPoint(160, 160),
    )

    assert view.dragMode() is QtWidgets.QGraphicsView.DragMode.ScrollHandDrag

    qtbot.mouseRelease(
        view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        modifier=QtCore.Qt.KeyboardModifier.NoModifier,
        pos=QtCore.QPoint(140, 140),
    )
    assert view.dragMode() is QtWidgets.QGraphicsView.DragMode.NoDrag
