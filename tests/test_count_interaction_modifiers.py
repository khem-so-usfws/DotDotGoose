"""Regression tests for DDG count-mode and temporary navigation gestures."""

from __future__ import annotations

from PyQt6 import QtCore, QtWidgets

from ddg.central_graphics_view import CentralGraphicsView, NavigationOverride


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
    view.setFocus()
    return view


def test_plain_left_click_adds_point(qtbot) -> None:
    """A normal left click should add a point in count mode."""
    view: CentralGraphicsView = _view(qtbot)

    with qtbot.waitSignal(view.add_point):
        qtbot.mouseClick(
            view.viewport(),
            QtCore.Qt.MouseButton.LeftButton,
            modifier=QtCore.Qt.KeyboardModifier.NoModifier,
            pos=QtCore.QPoint(150, 150),
        )


def test_ctrl_left_click_remains_compatibility_alias(qtbot) -> None:
    """Legacy Ctrl+click should still add a point without changing semantics."""
    view: CentralGraphicsView = _view(qtbot)

    with qtbot.waitSignal(view.add_point):
        qtbot.mouseClick(
            view.viewport(),
            QtCore.Qt.MouseButton.LeftButton,
            modifier=QtCore.Qt.KeyboardModifier.ControlModifier,
            pos=QtCore.QPoint(150, 150),
        )


def test_plain_drag_neither_pans_nor_adds_point(qtbot) -> None:
    """A drag without C should not pan and should not become an accidental point."""
    view: CentralGraphicsView = _view(qtbot)
    emitted: list[QtCore.QPointF] = []
    view.add_point.connect(emitted.append)

    qtbot.mousePress(
        view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        modifier=QtCore.Qt.KeyboardModifier.NoModifier,
        pos=QtCore.QPoint(160, 160),
    )

    assert view.dragMode() is QtWidgets.QGraphicsView.DragMode.NoDrag

    qtbot.mouseRelease(
        view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        modifier=QtCore.Qt.KeyboardModifier.NoModifier,
        pos=QtCore.QPoint(130, 130),
    )

    assert emitted == []
    assert view.dragMode() is QtWidgets.QGraphicsView.DragMode.NoDrag


def test_shift_drag_still_uses_rubber_band_selection(qtbot) -> None:
    """Shift+drag should retain DDG's point-selection gesture."""
    view: CentralGraphicsView = _view(qtbot)

    qtbot.mousePress(
        view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        modifier=QtCore.Qt.KeyboardModifier.ShiftModifier,
        pos=QtCore.QPoint(80, 80),
    )

    assert view.dragMode() is QtWidgets.QGraphicsView.DragMode.RubberBandDrag

    qtbot.mouseRelease(
        view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        modifier=QtCore.Qt.KeyboardModifier.ShiftModifier,
        pos=QtCore.QPoint(180, 180),
    )
    assert view.dragMode() is QtWidgets.QGraphicsView.DragMode.NoDrag


def test_c_drag_temporarily_pans_without_adding_point(qtbot) -> None:
    """Holding C should temporarily replace the current tool with panning."""
    view: CentralGraphicsView = _view(qtbot)
    emitted: list[QtCore.QPointF] = []
    view.add_point.connect(emitted.append)

    qtbot.keyPress(view, QtCore.Qt.Key.Key_C)
    assert view._active_navigation_override() is NavigationOverride.PAN

    qtbot.mousePress(
        view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        pos=QtCore.QPoint(160, 160),
    )
    assert view.dragMode() is QtWidgets.QGraphicsView.DragMode.ScrollHandDrag

    qtbot.mouseRelease(
        view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        pos=QtCore.QPoint(130, 130),
    )
    qtbot.keyRelease(view, QtCore.Qt.Key.Key_C)

    assert emitted == []
    assert view.dragMode() is QtWidgets.QGraphicsView.DragMode.NoDrag
    assert view._active_navigation_override() is None


def test_z_drag_rectangle_zooms_in(qtbot) -> None:
    """Z+drag should zoom in to the dragged viewport rectangle."""
    view: CentralGraphicsView = _view(qtbot)
    before: float = view.transform().m11()

    qtbot.keyPress(view, QtCore.Qt.Key.Key_Z)
    qtbot.mousePress(
        view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        pos=QtCore.QPoint(75, 75),
    )
    qtbot.mouseRelease(
        view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        pos=QtCore.QPoint(175, 175),
    )
    qtbot.keyRelease(view, QtCore.Qt.Key.Key_Z)

    assert view.transform().m11() > before


def test_x_drag_rectangle_zooms_out(qtbot) -> None:
    """X+drag should proportionally zoom out around the dragged rectangle."""
    view: CentralGraphicsView = _view(qtbot)
    before: float = view.transform().m11()

    qtbot.keyPress(view, QtCore.Qt.Key.Key_X)
    qtbot.mousePress(
        view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        pos=QtCore.QPoint(75, 75),
    )
    qtbot.mouseRelease(
        view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        pos=QtCore.QPoint(175, 175),
    )
    qtbot.keyRelease(view, QtCore.Qt.Key.Key_X)

    assert view.transform().m11() < before


def test_navigation_override_works_during_polygon_drawing(qtbot) -> None:
    """Temporary pan must not cancel or add vertices to an unfinished polygon."""
    view: CentralGraphicsView = _view(qtbot)
    view.start_polygon_annotation()

    qtbot.mouseClick(
        view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        pos=QtCore.QPoint(100, 100),
    )
    assert len(view.polygon_points) == 1

    qtbot.keyPress(view, QtCore.Qt.Key.Key_C)
    qtbot.mousePress(
        view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        pos=QtCore.QPoint(150, 150),
    )
    qtbot.mouseRelease(
        view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        pos=QtCore.QPoint(130, 130),
    )
    qtbot.keyRelease(view, QtCore.Qt.Key.Key_C)

    assert len(view.polygon_points) == 1
    assert view.interaction_mode.value == "polygon"


def test_modified_z_does_not_activate_navigation_override(qtbot) -> None:
    """Ctrl+Z must remain available to the existing undo shortcut."""
    view: CentralGraphicsView = _view(qtbot)

    qtbot.keyPress(
        view,
        QtCore.Qt.Key.Key_Z,
        modifier=QtCore.Qt.KeyboardModifier.ControlModifier,
    )

    assert view._active_navigation_override() is None

    qtbot.keyRelease(
        view,
        QtCore.Qt.Key.Key_Z,
        modifier=QtCore.Qt.KeyboardModifier.ControlModifier,
    )


def test_escape_cancels_pending_count_click(qtbot) -> None:
    """Esc before mouse release must prevent an unintended count point."""
    view: CentralGraphicsView = _view(qtbot)
    emitted: list[QtCore.QPointF] = []
    view.add_point.connect(emitted.append)

    qtbot.mousePress(
        view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        pos=QtCore.QPoint(150, 150),
    )
    assert view.count_click_press_position is not None

    qtbot.keyClick(view, QtCore.Qt.Key.Key_Escape)
    assert view.count_click_press_position is None

    qtbot.mouseRelease(
        view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        pos=QtCore.QPoint(150, 150),
    )

    assert emitted == []


def test_escape_cancels_navigation_before_unfinished_polygon(qtbot) -> None:
    """Esc should cancel temporary navigation before cancelling annotation work."""
    view: CentralGraphicsView = _view(qtbot)
    view.start_polygon_annotation()

    qtbot.mouseClick(
        view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        pos=QtCore.QPoint(100, 100),
    )
    assert len(view.polygon_points) == 1

    qtbot.keyPress(view, QtCore.Qt.Key.Key_Z)
    qtbot.mousePress(
        view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        pos=QtCore.QPoint(80, 80),
    )
    assert view.navigation_gesture is NavigationOverride.ZOOM_IN

    qtbot.keyClick(view, QtCore.Qt.Key.Key_Escape)

    assert view.navigation_gesture is None
    assert view._active_navigation_override() is NavigationOverride.ZOOM_IN
    assert view.interaction_mode.value == "polygon"
    assert len(view.polygon_points) == 1

    qtbot.keyRelease(view, QtCore.Qt.Key.Key_Z)
    assert view._active_navigation_override() is None
    qtbot.keyClick(view, QtCore.Qt.Key.Key_Escape)

    assert view.interaction_mode.value == "count"
    assert view.polygon_points == []


def test_starting_annotation_mode_cancels_pending_count_click(qtbot) -> None:
    """Changing tools while the mouse is down must not add a stale point."""
    view: CentralGraphicsView = _view(qtbot)
    emitted: list[QtCore.QPointF] = []
    view.add_point.connect(emitted.append)

    qtbot.mousePress(
        view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        pos=QtCore.QPoint(150, 150),
    )
    assert view.count_click_press_position is not None

    view.start_polygon_annotation()
    assert view.count_click_press_position is None

    qtbot.mouseRelease(
        view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        pos=QtCore.QPoint(150, 150),
    )

    assert emitted == []
    assert view.interaction_mode.value == "polygon"
