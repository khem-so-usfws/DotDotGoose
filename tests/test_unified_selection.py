"""End-to-end unified selection, movement, deletion, and Compare controls."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PyQt6 import QtCore, QtGui, QtWidgets

from ddg.central_graphics_view import InteractionMode
from ddg.main_window import MainWindow
from test_workspace_controls import window  # noqa: F401


def test_compare_split_button(window: MainWindow, qtbot: Any) -> None:
    """Compare visibility and layout controls share the existing View actions.

    Args:
        window: Real application window.
        qtbot: Qt interaction fixture.
    """
    controls: Any = window.workspace_controls
    widget: Any = window.centralWidget()
    button: QtWidgets.QToolButton = controls.compare_button
    assert button.isChecked()
    assert button.defaultAction() is window.compare_action
    assert button.menu().actions() == [
        window.compare_1x2_action,
        window.compare_2x1_action,
    ]
    window.compare_2x1_action.trigger()
    assert widget.compare_layout() == "2x1"
    window.compare_action.trigger()
    assert not widget.compare_enabled()
    assert not button.isChecked()
    window.compare_action.trigger()
    assert widget.compare_enabled()
    assert widget.compare_layout() == "2x1"
    assert window.compare_2x1_action.isChecked()
    widget.set_compare_layout("1x2")
    qtbot.wait(10)


def test_batch_change_class_in_reference(window: MainWindow, qtbot: Any) -> None:
    """Reclassify a mixed selection in Reference and undo it as one edit.

    Args:
        window: Visible main window.
        qtbot: Qt interaction fixture.
    """
    widget: Any = window.centralWidget()
    controls: Any = window.workspace_controls
    canvas: Any = widget.reference_canvas
    widget.canvas.classes.extend(["Other", "Target"])
    widget.canvas.colors.update(
        Other=QtGui.QColor("blue"), Target=QtGui.QColor("green")
    )
    widget.point_widget.display_count_tree()
    canvas.add_point(QtCore.QPointF(300, 300))
    canvas.add_point(QtCore.QPointF(300, 300))
    canvas.set_current_class(1)
    canvas.add_point(QtCore.QPointF(600, 300))
    canvas.set_current_class(0)
    canvas.add_landmark_annotation(QtCore.QPointF(450, 450))
    points: dict[str, list[QtCore.QPointF]] = canvas.points[canvas.current_image_name]
    untouched: QtCore.QPointF = points["Bird"][0]
    first: QtCore.QPointF = points["Bird"][1]
    second: QtCore.QPointF = points["Other"][0]
    view: Any = widget.reference_graphics_view
    view.view_activated.emit()
    controls.select_tool(InteractionMode.SELECT)
    canvas.selection = [("Bird", first), ("Other", second)]
    canvas.select_external_annotation(0)
    editor: Any = controls.editors[view]
    editor.refresh_selection()
    assert editor.change_class_action in controls.dot_menus[1].actions()
    assert editor.change_class_action in editor.menu.actions()
    counts: list[tuple[str, str, int]] = []
    canvas.update_point_count.connect(
        lambda image, name, count: counts.append((image, name, count))
    )
    history_size: int = len(widget._global_undo_order)

    def apply_target() -> None:
        """Choose the target in the actual Change class dialog."""
        dialog: QtWidgets.QInputDialog = QtWidgets.QApplication.activeModalWidget()
        dialog.setTextValue("Target")
        dialog.accept()

    QtCore.QTimer.singleShot(0, apply_target)
    editor.change_class_action.trigger()
    assert len(widget._global_undo_order) == history_size + 1
    assert len(points["Bird"]) == 1 and points["Bird"][0] is untouched
    assert points["Target"] == [first, second]
    assert canvas.selection == [("Target", first), ("Target", second)]
    assert canvas.selected_annotation_indices == {0}
    assert widget.canvas.current_class_name == "Bird"
    assert widget.canvas.dirty
    assert set(counts) == {
        ("b.png", "Bird", 1),
        ("b.png", "Other", 0),
        ("b.png", "Target", 2),
    }
    widget.undo_global_history()
    assert points["Bird"][1] is first and points["Other"][0] is second
    assert not points["Target"]
    widget.redo_global_history()
    assert points["Target"] == [first, second]


def test_mixed_drag_delete_and_history(window: MainWindow, qtbot: Any) -> None:
    """Dots and annotations move/delete together, one history event per operation.

    Args:
        window: Real application window.
        qtbot: Qt interaction fixture.
    """
    widget: Any = window.centralWidget()
    for pane, canvas in widget.workspace_feedback.panes:
        canvas.add_point(QtCore.QPointF(400, 300))
        canvas.add_line_annotation([QtCore.QPointF(600, 300), QtCore.QPointF(800, 500)])
    window.workspace_controls.select_tool(InteractionMode.SELECT)
    for pane, canvas in widget.workspace_feedback.panes:
        view: Any = pane.graphics_view
        editor: Any = window.workspace_controls.editors[view]
        view.rotate_view(True)
        view.fit_image()
        qtbot.wait(10)
        dot: QtCore.QPointF = canvas.points[canvas.current_image_name]["Bird"][0]
        start: QtCore.QPoint = view.mapFromScene(dot)
        qtbot.mouseClick(view.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=start)
        assert len(canvas.selection) == 1
        line: QtCore.QPoint = view.mapFromScene(QtCore.QPointF(700, 400))
        qtbot.mouseClick(
            view.viewport(),
            QtCore.Qt.MouseButton.LeftButton,
            modifier=QtCore.Qt.KeyboardModifier.ShiftModifier,
            pos=line,
        )
        assert canvas.selected_annotation_indices == {0}
        assert not canvas.external_annotation_handle_items
        original: list[tuple[float, float]] = list(
            canvas.external_annotations[0].points
        )
        end: QtCore.QPoint = start + QtCore.QPoint(30, 24)
        delta: QtCore.QPointF = view.mapToScene(end) - view.mapToScene(start)
        history: int = len(widget._global_undo_order)
        qtbot.mousePress(view.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=start)
        qtbot.mouseMove(view.viewport(), end)
        qtbot.mouseRelease(view.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=end)
        assert QtCore.QLineF(dot, QtCore.QPointF(400, 300) + delta).length() < 0.01
        assert canvas.external_annotations[0].points == [
            (x + delta.x(), y + delta.y()) for x, y in original
        ]
        assert len(widget._global_undo_order) == history + 1
        assert len(canvas.selection) == 1
        assert canvas.selected_annotation_indices == {0}
        widget.undo_global_history()
        assert dot == QtCore.QPointF(400, 300)
        assert canvas.external_annotations[0].points == original
        widget.redo_global_history()
        assert QtCore.QLineF(dot, QtCore.QPointF(400, 300) + delta).length() < 0.01
        editor.select_box(view.viewport().rect())
        history = len(widget._global_undo_order)
        qtbot.keyClick(view, QtCore.Qt.Key.Key_Delete)
        assert canvas.points[canvas.current_image_name]["Bird"] == []
        assert canvas.external_annotations == []
        assert len(widget._global_undo_order) == history + 1
        widget.undo_global_history()
        assert len(canvas.points[canvas.current_image_name]["Bird"]) == 1
        assert len(canvas.external_annotations) == 1
        widget.redo_global_history()
        assert not canvas.external_annotations
        assert not canvas.points[canvas.current_image_name]["Bird"]


def test_first_drag_selects_then_shift_box_and_escape(
    window: MainWindow, qtbot: Any
) -> None:
    """First-click selection does not accidentally move, and Shift gestures add/toggle.

    Args:
        window: Real application window.
        qtbot: Qt interaction fixture.
    """
    widget: Any = window.centralWidget()
    canvas: Any = widget.canvas
    view: Any = widget.graphicsView
    canvas.add_point(QtCore.QPointF(400, 300))
    canvas.add_point(QtCore.QPointF(600, 400))
    window.workspace_controls.select_tool(InteractionMode.SELECT)
    start: QtCore.QPoint = view.mapFromScene(QtCore.QPointF(400, 300))
    qtbot.mousePress(view.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(view.viewport(), start + QtCore.QPoint(30, 20))
    qtbot.mouseRelease(
        view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        pos=start + QtCore.QPoint(30, 20),
    )
    assert canvas.points["a.png"]["Bird"][0] == QtCore.QPointF(400, 300)
    assert len(canvas.selection) == 1
    second: QtCore.QPoint = view.mapFromScene(QtCore.QPointF(600, 400))
    qtbot.mouseClick(
        view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        modifier=QtCore.Qt.KeyboardModifier.ShiftModifier,
        pos=second,
    )
    assert len(canvas.selection) == 2
    qtbot.mouseClick(
        view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        modifier=QtCore.Qt.KeyboardModifier.ShiftModifier,
        pos=start,
    )
    assert len(canvas.selection) == 1
    qtbot.keyClick(view, QtCore.Qt.Key.Key_Escape)
    assert not canvas.selection
    first_corner: QtCore.QPoint = view.mapFromScene(QtCore.QPointF(350, 250))
    last_corner: QtCore.QPoint = view.mapFromScene(QtCore.QPointF(650, 450))
    qtbot.mousePress(
        view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        modifier=QtCore.Qt.KeyboardModifier.ShiftModifier,
        pos=first_corner,
    )
    qtbot.mouseMove(view.viewport(), last_corner)
    qtbot.mouseRelease(
        view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        modifier=QtCore.Qt.KeyboardModifier.ShiftModifier,
        pos=last_corner,
    )
    assert len(canvas.selection) == 2
    assert view.interaction_mode is InteractionMode.SELECT


def test_locked_and_failed_write_are_atomic(
    window: MainWindow, monkeypatch: Any
) -> None:
    """Locked geometry and failed sidecar writes leave the entire group unchanged.

    Args:
        window: Real application window.
        monkeypatch: Attribute substitution fixture.
    """
    widget: Any = window.centralWidget()
    canvas: Any = widget.canvas
    canvas.add_point(QtCore.QPointF(400, 300))
    canvas.add_line_annotation([QtCore.QPointF(600, 300), QtCore.QPointF(800, 500)])
    window.workspace_controls.select_tool(InteractionMode.SELECT)
    editor: Any = window.workspace_controls.editors[widget.graphicsView]
    editor.select_box(widget.graphicsView.viewport().rect())
    original: list[tuple[float, float]] = list(canvas.external_annotations[0].points)
    canvas.external_annotations[0].set_locked(True)
    assert not editor.edit(offset=QtCore.QPointF(25, 10))
    assert "locked" in widget.workspace_feedback.notice
    assert canvas.points["a.png"]["Bird"][0] == QtCore.QPointF(400, 300)
    assert canvas.external_annotations[0].points == original
    canvas.external_annotations[0].set_locked(False)
    history: int = len(canvas.undo_queue)
    monkeypatch.setattr(
        canvas, "_apply_annotation_history_snapshot", lambda *_args: False
    )
    assert not editor.edit(offset=QtCore.QPointF(25, 10))
    assert canvas.points["a.png"]["Bird"][0] == QtCore.QPointF(400, 300)
    assert canvas.external_annotations[0].points == original
    assert len(canvas.undo_queue) == history


def test_vertex_drag_and_overlap_chooser(window: MainWindow, qtbot: Any) -> None:
    """Selected vertices edit independently, and coincident items offer a chooser.

    Args:
        window: Real application window.
        qtbot: Qt interaction fixture.
    """
    widget: Any = window.centralWidget()
    canvas: Any = widget.canvas
    view: Any = widget.graphicsView
    canvas.add_line_annotation([QtCore.QPointF(400, 300), QtCore.QPointF(700, 500)])
    window.workspace_controls.select_tool(InteractionMode.SELECT)
    midpoint: QtCore.QPoint = view.mapFromScene(QtCore.QPointF(550, 400))
    qtbot.mouseClick(view.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=midpoint)
    original: list[tuple[float, float]] = list(canvas.external_annotations[0].points)
    start: QtCore.QPoint = view.mapFromScene(QtCore.QPointF(*original[0]))
    end: QtCore.QPoint = start + QtCore.QPoint(20, 30)
    delta: QtCore.QPointF = view.mapToScene(end) - view.mapToScene(start)
    history: int = len(canvas.undo_queue)
    qtbot.mousePress(view.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(view.viewport(), end)
    qtbot.mouseRelease(view.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=end)
    assert canvas.external_annotations[0].points == [
        (original[0][0] + delta.x(), original[0][1] + delta.y()),
        original[1],
    ]
    assert len(canvas.undo_queue) == history + 1
    widget.undo_global_history()
    assert canvas.external_annotations[0].points == original
    editor: Any = window.workspace_controls.editors[view]
    editor.clear()
    canvas.add_point(QtCore.QPointF(550, 400))
    chosen: list[str] = []

    def choose_annotation() -> None:
        """Choose the annotation from the actual overlap popup."""
        popup: Any = QtWidgets.QApplication.activePopupWidget()
        assert isinstance(popup, QtWidgets.QMenu)
        actions: list[QtGui.QAction] = popup.actions()
        assert len(actions) == 2
        action: QtGui.QAction = next(
            action for action in actions if "annotation" in action.text()
        )
        chosen.append(action.text())
        popup.setActiveAction(action)
        qtbot.keyClick(popup, QtCore.Qt.Key.Key_Return)

    QtCore.QTimer.singleShot(20, choose_annotation)
    qtbot.mouseClick(view.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=midpoint)
    assert chosen
    assert canvas.selected_annotation_indices == {0}
    assert not canvas.selection


def test_native_metadata_and_other_image_history(
    window: MainWindow, qtbot: Any
) -> None:
    """Group edits preserve sidecar metadata and undo correctly after navigation.

    Args:
        window: Real application window.
        qtbot: Qt interaction fixture.
    """
    widget: Any = window.centralWidget()
    canvas: Any = widget.canvas
    canvas.add_point(QtCore.QPointF(400, 300))
    canvas.add_polygon_annotation(
        [QtCore.QPointF(600, 300), QtCore.QPointF(800, 300), QtCore.QPointF(700, 500)]
    )
    path: Path = Path(canvas.directory) / "a.json"
    raw: dict[str, Any] = json.loads(path.read_text())
    raw["custom_metadata"] = {"survey": "retain me"}
    raw["imageData"] = "opaque-existing-embedding"
    raw["shapes"][0]["description"] = "retain this too"
    path.write_text(json.dumps(raw))
    canvas.display_external_annotations(str(Path(canvas.directory) / "a.png"))
    window.workspace_controls.select_tool(InteractionMode.SELECT)
    editor: Any = window.workspace_controls.editors[widget.graphicsView]
    editor.select_box(widget.graphicsView.viewport().rect())
    assert editor.edit(offset=QtCore.QPointF(15, 25))
    after: dict[str, Any] = json.loads(path.read_text())
    assert after["custom_metadata"] == raw["custom_metadata"]
    assert after["imageData"] == raw["imageData"]
    assert after["shapes"][0]["description"] == raw["shapes"][0]["description"]
    widget.load_current_image("b.png")
    qtbot.wait(10)
    widget.undo_global_history()
    assert canvas.points["a.png"]["Bird"][0] == QtCore.QPointF(400, 300)
    assert (
        json.loads(path.read_text())["shapes"][0]["points"]
        == raw["shapes"][0]["points"]
    )
    widget.redo_global_history()
    assert canvas.points["a.png"]["Bird"][0] == QtCore.QPointF(415, 325)


def test_polygon_interior_and_existing_dot_selection(
    window: MainWindow, qtbot: Any
) -> None:
    """Polygon interiors are selectable and Count selections carry into editing.

    Args:
        window: Real application window.
        qtbot: Qt interaction fixture.
    """
    widget: Any = window.centralWidget()
    canvas: Any = widget.canvas
    view: Any = widget.graphicsView
    canvas.add_point(QtCore.QPointF(400, 300))
    canvas.add_polygon_annotation(
        [
            QtCore.QPointF(200, 100),
            QtCore.QPointF(1000, 100),
            QtCore.QPointF(1000, 700),
            QtCore.QPointF(200, 700),
        ]
    )
    canvas.select_points(QtCore.QRectF(390, 290, 20, 20))
    window.workspace_controls.select_tool(InteractionMode.SELECT)
    assert len(canvas.selection) == 1
    editor: Any = window.workspace_controls.editors[view]
    editor.clear()
    position: QtCore.QPoint = view.mapFromScene(QtCore.QPointF(700, 450))
    qtbot.mouseClick(view.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=position)
    assert canvas.selected_annotation_indices == {0}
    assert not canvas.selection
