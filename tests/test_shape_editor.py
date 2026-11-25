"""Regression coverage for 1.9.1 annotation shape tools."""

from __future__ import annotations

from typing import cast

import pytest
from PyQt6 import QtCore, QtWidgets
from pytestqt.qtbot import QtBot

from ddg.annotations.model import Point
from ddg.annotations.reshape_geometry import polygon_area, reshape, valid_shape
from ddg.central_graphics_view import CentralGraphicsView, InteractionMode
from ddg.central_widget import CentralWidget
from ddg.image_workspace import ImageWorkspace
from ddg.main_window import MainWindow
from ddg.shape_editor import ShapeTool
from test_workspace_controls import window  # noqa: F401


def click(qtbot: QtBot, view: CentralGraphicsView, x: float, y: float) -> None:
    """Click the view at a position expressed in source-image pixels."""
    qtbot.mouseClick(
        view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        pos=view.mapFromScene(QtCore.QPointF(x, y)),
    )


def test_crossings_closing_edge_and_result_validity() -> None:
    """Retain both line tails and offer both sides of a polygon cut."""
    line: list[Point] = [(0, 10), (10, 10), (25, 10), (30, 10)]
    sketch: list[Point] = [(25, 15), (25, 5), (10, 5), (10, 15)]
    result = reshape(line, sketch, False)[0]
    assert result.points == [(0, 10), (10, 10), (10, 5), (25, 5), (25, 10), (30, 10)]
    assert result.removed == [(10, 10), (25, 10)]
    ring: list[Point] = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
    split = reshape(ring, [(-1, 4), (11, 4)], True)
    assert sorted(abs(polygon_area(choice.points)) for choice in split) == [40, 60]
    bow: list[Point] = [(0, 0), (10, 10), (0, 10), (10, 0)]
    assert not valid_shape(bow, True)
    with pytest.raises(ValueError, match="two distinct joins"):
        reshape(line, [(5, 0), (5, 20), (15, 0), (25, 20)], False)


def test_reshape_in_rotated_float_keeps_selection_and_history(
    window: MainWindow, qtbot: QtBot
) -> None:
    """Apply a replacement through the toolbar and guard a floating pane draft."""
    widget: CentralWidget = cast(CentralWidget, window.centralWidget())
    workspace: ImageWorkspace = cast(ImageWorkspace, widget.image_workspace)
    dock = workspace.docks["reference"]
    dock.setFloating(True)
    dock.resize(950, 760)
    qtbot.wait(30)
    view: CentralGraphicsView = widget.reference_graphics_view
    view.rotate_view(True)
    qtbot.wait(20)
    canvas = widget.reference_canvas
    original: list[Point] = [(200, 400), (400, 400), (800, 400), (1000, 400)]
    canvas.add_line_annotation([QtCore.QPointF(*point) for point in original])
    controls = window.workspace_controls
    controls.select_tool(InteractionMode.SELECT)
    click(qtbot, view, 600, 400)
    assert canvas.selected_annotation_indices == {0}
    assert controls.shape_button.isEnabled()
    controls.shape_button.click()
    assert controls.shape_button.text() == "Reshape"
    assert not controls.snap_action.isChecked()
    history: int = len(widget._global_undo_order)
    for x, y in [(350, 470), (350, 330), (850, 330), (850, 470)]:
        click(qtbot, view, x, y)
    assert canvas.external_annotations[0].points == original
    assert not widget._set_last_active_view("current")
    assert not dock.close()
    qtbot.keyClick(view, QtCore.Qt.Key.Key_Return)
    changed: list[Point] = canvas.external_annotations[0].points
    assert changed[0] == original[0] and changed[-1] == original[-1]
    assert len(changed) == 6
    assert changed[2][1] == pytest.approx(330, abs=4)
    assert canvas.external_annotations[0].label == "cutline"
    assert len(widget._global_undo_order) == history + 1
    assert controls.active_shape_editor().tool is ShapeTool.RESHAPE
    assert canvas.selected_annotation_indices == {0}
    widget.undo_global_history()
    assert canvas.external_annotations[0].points == original
    widget.redo_global_history()
    assert canvas.external_annotations[0].points == changed


def test_trim_extend_and_vertex_insert_delete(window: MainWindow, qtbot: QtBot) -> None:
    """Change one endpoint at a time and edit vertices independently of Select."""
    widget: CentralWidget = cast(CentralWidget, window.centralWidget())
    canvas = widget.canvas
    view: CentralGraphicsView = widget.graphicsView
    controls = window.workspace_controls
    canvas.add_line_annotation(
        [QtCore.QPointF(250, 400), QtCore.QPointF(550, 400), QtCore.QPointF(950, 400)]
    )
    controls.select_tool(InteractionMode.SELECT)
    click(qtbot, view, 400, 400)
    controls.shape_actions[ShapeTool.LINE_END].trigger()
    click(qtbot, view, 250, 400)
    click(qtbot, view, 400, 400)
    qtbot.keyClick(view, QtCore.Qt.Key.Key_Return)
    assert canvas.external_annotations[0].points[0] == pytest.approx((400, 400), abs=4)
    click(qtbot, view, 950, 400)
    click(qtbot, view, 1010, 450)
    click(qtbot, view, 1050, 500)
    qtbot.keyClick(view, QtCore.Qt.Key.Key_Return)
    assert canvas.external_annotations[0].points[-1] == pytest.approx(
        (1050, 500), abs=4
    )
    assert len(canvas.external_annotations[0].points) == 5
    controls.shape_actions[ShapeTool.VERTICES].trigger()
    click(qtbot, view, 740, 400)
    assert len(canvas.external_annotations[0].points) == 6
    qtbot.mouseClick(
        view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.ShiftModifier,
        pos=view.mapFromScene(QtCore.QPointF(550, 400)),
    )
    qtbot.keyClick(view, QtCore.Qt.Key.Key_Delete)
    assert len(canvas.external_annotations[0].points) == 4


def test_polygon_reshape_snaps_and_asks_which_area_to_keep(
    window: MainWindow, qtbot: QtBot
) -> None:
    """Use optional snapped joins, choose a polygon, and confirm with Enter."""
    widget: CentralWidget = cast(CentralWidget, window.centralWidget())
    canvas = widget.canvas
    view: CentralGraphicsView = widget.graphicsView
    controls = window.workspace_controls
    corners: list[Point] = [(200, 200), (900, 200), (900, 650), (200, 650)]
    canvas.add_polygon_annotation([QtCore.QPointF(*point) for point in corners])
    controls.select_tool(InteractionMode.SELECT)
    click(qtbot, view, 600, 375)
    controls.shape_actions[ShapeTool.RESHAPE].trigger()
    controls.snap_action.trigger()
    assert controls.snap_action.isChecked()
    click(qtbot, view, 205, 390)
    click(qtbot, view, 895, 390)
    editor = controls.active_shape_editor()
    assert len(editor.results) == 2 and editor.choice is None
    qtbot.keyClick(view, QtCore.Qt.Key.Key_Return)
    assert canvas.external_annotations[0].points == corners
    click(qtbot, view, 600, 520)
    qtbot.keyClick(view, QtCore.Qt.Key.Key_Return)
    chosen: list[Point] = canvas.external_annotations[0].points
    assert min(y for _, y in chosen) == pytest.approx(390, abs=4)
    assert max(y for _, y in chosen) == 650
    assert canvas.external_annotations[0].label == "count_region"


def test_trace_in_overflow_uses_the_same_cutline_without_snap(
    window: MainWindow, qtbot: QtBot
) -> None:
    """Find Trace at narrow widths and append the cutline's exact vertices."""
    widget: CentralWidget = cast(CentralWidget, window.centralWidget())
    canvas = widget.canvas
    view: CentralGraphicsView = widget.graphicsView
    controls = window.workspace_controls
    window.resize(900, 850)
    qtbot.wait(40)
    tools = widget.workspace_layout.groups[1]
    assert all(button.isHidden() for button in tools.option_buttons)
    menus: list[QtWidgets.QMenu] = [
        menu
        for action in tools.selector.menu().actions()
        if (menu := action.menu()) is not None
    ]
    assert controls.shape_menu in menus
    assert controls.trace_action in controls.shape_menu.actions()
    cutline: list[Point] = [(240, 300), (560, 425), (860, 300)]
    canvas.add_line_annotation([QtCore.QPointF(*point) for point in cutline])
    controls.select_tool(InteractionMode.POLYGON)
    assert not controls.snap_action.isChecked()
    assert controls.trace_action.isEnabled()
    assert not controls.shape_actions[ShapeTool.RESHAPE].isEnabled()
    controls.trace_action.trigger()
    click(qtbot, view, 840, 308)
    click(qtbot, view, 255, 307)
    assert len(view.polygon_points) == 3
    assert view.polygon_points[1] == QtCore.QPointF(*cutline[1])
    click(qtbot, view, 550, 680)
    qtbot.keyClick(view, QtCore.Qt.Key.Key_Return)
    assert canvas.external_annotations[0].points == cutline
    assert canvas.external_annotations[1].points[1] == cutline[1]


def test_trace_reshapes_a_boundary_and_protects_its_draft(
    window: MainWindow, qtbot: QtBot
) -> None:
    """Trace between crossings, then keep one count area and save its geometry."""
    widget: CentralWidget = cast(CentralWidget, window.centralWidget())
    canvas = widget.canvas
    view: CentralGraphicsView = widget.graphicsView
    controls = window.workspace_controls
    line: list[Point] = [(190, 315), (570, 400), (1020, 320)]
    corners: list[Point] = [(300, 200), (900, 200), (900, 650), (300, 650)]
    canvas.add_line_annotation([QtCore.QPointF(*point) for point in line])
    canvas.add_polygon_annotation([QtCore.QPointF(*point) for point in corners])
    controls.select_tool(InteractionMode.SELECT)
    click(qtbot, view, 600, 500)
    controls.shape_actions[ShapeTool.RESHAPE].trigger()
    controls.trace_action.trigger()
    click(qtbot, view, 210, 320)
    assert view.has_annotation_draft()
    widget.workspace_feedback.adjust_image(widget.current_pane, canvas, (-20, 0))
    assert controls.active_shape_editor().tracing
    click(qtbot, view, 990, 326)
    assert len(controls.active_shape_editor().results) == 2
    click(qtbot, view, 620, 520)
    qtbot.keyClick(view, QtCore.Qt.Key.Key_Return)
    assert canvas.external_annotations[0].points == line
    assert line[1] in canvas.external_annotations[1].points
    assert canvas.external_annotations[1].points != corners
    assert not view.has_annotation_draft()
