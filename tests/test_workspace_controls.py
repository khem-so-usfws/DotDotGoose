"""Integration coverage for the shared toolbars and compact workspace."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from PyQt6 import QtCore, QtGui, QtWidgets

from ddg.central_graphics_view import InteractionMode
from ddg.main_window import MainWindow


@pytest.fixture
def window(qtbot: Any, tmp_path: Path) -> MainWindow:
    """Open a real main window with two images and one count class.

    Args:
        qtbot: Qt interaction fixture.
        tmp_path: Isolated project folder.

    Returns:
        Fully initialized main window.
    """
    result: MainWindow = MainWindow()
    qtbot.addWidget(
        result,
        before_close_func=lambda item: setattr(
            item.centralWidget().canvas, "dirty", False
        ),
    )
    result.resize(1500, 900)
    widget: Any = result.centralWidget()
    for name in ("a.png", "b.png"):
        Image.new("RGB", (1200, 800), (60, 80, 100)).save(tmp_path / name)
    widget.canvas.directory = str(tmp_path)
    widget.canvas.points = {"a.png": {}, "b.png": {}}
    widget.canvas.classes = ["Bird"]
    widget.canvas.colors = {"Bird": QtGui.QColor("red")}
    widget.canvas.set_current_class(0)
    widget.canvas.load_image(str(tmp_path / "a.png"))
    widget.set_compare_layout("1x2")
    widget.set_compare_enabled(True)
    result.show()
    qtbot.wait(30)
    return result


def test_edit_mode_is_shared_and_escape_keeps_tool(
    window: MainWindow, qtbot: Any
) -> None:
    """Either pane's first click edits annotations and Escape only deselects.

    Args:
        window: Visible main window.
        qtbot: Qt interaction fixture.
    """
    widget: Any = window.centralWidget()
    for canvas in (widget.canvas, widget.reference_canvas):
        canvas.add_line_annotation([QtCore.QPointF(300, 300), QtCore.QPointF(700, 500)])
    window.workspace_controls.actions[InteractionMode.SELECT].trigger()
    for pane, canvas in widget.workspace_feedback.panes:
        view: Any = pane.graphics_view
        assert view.interaction_mode is InteractionMode.SELECT
        pos: QtCore.QPoint = view.mapFromScene(QtCore.QPointF(500, 400))
        qtbot.mouseClick(view.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=pos)
        assert canvas.selected_external_annotation() is not None
        other: Any = (
            widget.reference_canvas if canvas is widget.canvas else widget.canvas
        )
        assert other.selected_external_annotation() is None
        widget.workspace_feedback.refresh()
        index: int = 0 if canvas is widget.canvas else 1
        assert (
            widget.workspace_feedback.selection_buttons[index].text() == "1 annotation"
        )
        qtbot.keyClick(view, QtCore.Qt.Key.Key_Escape)
        assert canvas.selected_external_annotation() is None
        assert view.interaction_mode is InteractionMode.SELECT
        assert window.workspace_controls.actions[InteractionMode.SELECT].isChecked()
    window.workspace_controls.actions[InteractionMode.COUNT].trigger()
    assert all(
        p.graphics_view.interaction_mode is InteractionMode.COUNT
        for p, _c in widget.workspace_feedback.panes
    )


def test_sticky_drawing_and_unfinished_guard(window: MainWindow, qtbot: Any) -> None:
    """Finished drawings retain the tool and unfinished drawings block tool changes.

    Args:
        window: Visible main window.
        qtbot: Qt interaction fixture.
    """
    widget: Any = window.centralWidget()
    controls: Any = window.workspace_controls
    controls.actions[InteractionMode.LINE].trigger()
    current: Any = widget.graphicsView
    reference: Any = widget.reference_graphics_view
    current._add_line_vertex(QtCore.QPointF(300, 300))
    controls.actions[InteractionMode.LINE].trigger()
    assert len(current.line_points) == 1
    controls.actions[InteractionMode.SELECT].trigger()
    assert controls.mode is InteractionMode.LINE
    assert controls.actions[InteractionMode.LINE].isChecked()
    assert len(current.line_points) == 1
    widget.load_current_image("b.png")
    qtbot.wait(1)
    assert widget.canvas.current_image_name == "a.png"
    assert widget.current_pane.selected_image() == "a.png"
    assert len(current.line_points) == 1
    pos: QtCore.QPoint = reference.mapFromScene(QtCore.QPointF(500, 400))
    qtbot.mouseClick(reference.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=pos)
    assert not reference.line_points
    assert len(current.line_points) == 1
    current._add_line_vertex(QtCore.QPointF(600, 400))
    qtbot.keyClick(current, QtCore.Qt.Key.Key_Return)
    assert current.interaction_mode is InteractionMode.LINE
    assert len(widget.canvas.external_annotations) == 1
    qtbot.mouseClick(reference.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=pos)
    assert len(reference.line_points) == 1
    window.compare_action.setChecked(False)
    assert widget.compare_enabled()
    assert window.compare_action.isChecked()
    assert len(reference.line_points) == 1
    qtbot.keyClick(reference, QtCore.Qt.Key.Key_Escape)
    assert not reference.line_points
    assert reference.interaction_mode is InteractionMode.LINE
    controls.actions[InteractionMode.POINT].trigger()
    for pane, canvas in widget.workspace_feedback.panes:
        view: Any = pane.graphics_view
        for point in (QtCore.QPointF(450, 350), QtCore.QPointF(650, 450)):
            qtbot.mouseClick(
                view.viewport(),
                QtCore.Qt.MouseButton.LeftButton,
                pos=view.mapFromScene(point),
            )
            assert view.interaction_mode is InteractionMode.POINT
        assert (
            len(
                [
                    a
                    for a in canvas.external_annotations
                    if a.shape_type.value == "point"
                ]
            )
            == 2
        )


def test_layout_and_shared_display(window: MainWindow) -> None:
    """Two header rows remain, with recovery and status outside the image area.

    Args:
        window: Visible main window.
    """
    widget: Any = window.centralWidget()
    for pane, _canvas in widget.workspace_feedback.panes:
        assert pane.layout().count() == 3
        assert pane.layout().itemAt(0).layout() is not None
        assert pane.layout().itemAt(1).layout() is not None
        assert pane.layout().itemAt(2).widget() is pane.graphics_view
        assert pane.previous_button.parentWidget() is pane
        assert pane.close_button.isHidden()
        assert pane.make_current_button.isHidden()
        assert "Reset view" in [
            action.text() for action in pane.overflow_menu.actions()
        ]
    feedback: Any = widget.workspace_feedback
    assert widget.point_widget.isAncestorOf(feedback.recover_button)
    assert feedback.save_label.parentWidget() is window.statusBar()
    assert widget.point_widget.checkBoxDisplayPoints.isHidden()
    assert widget.point_widget.checkBoxDisplayGrid.isHidden()
    for name in ("Dots", "Grid"):
        action: QtGui.QAction = window.workspace_controls.display_actions[name]
        action.setChecked(False)
        assert (
            not widget.canvas.show_points
            if name == "Dots"
            else not widget.canvas.show_grid
        )
        assert (
            not widget.reference_canvas.show_points
            if name == "Dots"
            else not widget.reference_canvas.show_grid
        )
    widget.point_widget.checkBoxDisplayPoints.setChecked(True)
    assert window.workspace_controls.display_actions["Dots"].isChecked()


def test_count_escape_and_click_alignment(window: MainWindow, qtbot: Any) -> None:
    """Changing active panes does not shift the source coordinate under a click.

    Args:
        window: Visible main window.
        qtbot: Qt interaction fixture.
    """
    widget: Any = window.centralWidget()
    for pane, canvas in widget.workspace_feedback.panes:
        view: Any = pane.graphics_view
        pos: QtCore.QPoint = view.mapFromScene(QtCore.QPointF(600, 400))
        expected: QtCore.QPointF = view.mapToScene(pos)
        qtbot.mouseClick(view.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=pos)
        actual: QtCore.QPointF = canvas.points[canvas.current_image_name]["Bird"][-1]
        assert QtCore.QLineF(expected, actual).length() < 0.01
        canvas.select_points(QtCore.QRectF(580, 380, 40, 40))
        qtbot.keyClick(view, QtCore.Qt.Key.Key_Escape)
        assert not canvas.selection
        assert view.interaction_mode is InteractionMode.COUNT
