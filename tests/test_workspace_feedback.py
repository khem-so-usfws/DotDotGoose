"""Regression coverage for pane workflow, display memory, and recovery."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from PyQt6 import QtCore, QtGui, QtWidgets

from ddg.central_graphics_view import InteractionMode
from ddg.central_widget import CentralWidget
from ddg.workspace_feedback import EnhancementDialog


@pytest.fixture
def workspace(qtbot: Any, tmp_path: Path) -> CentralWidget:
    """Create a visible two-image workspace with a shared counting class.

    Args:
        qtbot: Qt interaction fixture.
        tmp_path: Isolated image directory.

    Returns:
        Initialized dual-pane workspace.
    """
    widget: CentralWidget = CentralWidget()
    qtbot.addWidget(widget)
    widget.resize(1600, 950)
    for name in ("a.png", "b.png", "c.png"):
        Image.new("RGB", (1200, 800), (60, 70, 80)).save(tmp_path / name)
    widget.canvas.directory = str(tmp_path)
    widget.canvas.points = {name: {} for name in ("a.png", "b.png", "c.png")}
    widget.canvas.classes = ["Bird"]
    widget.canvas.colors = {"Bird": QtGui.QColor("red")}
    widget.canvas.set_current_class(0)
    widget.canvas.load_image(str(tmp_path / "a.png"))
    widget.set_compare_enabled(True)
    widget.show()
    qtbot.wait(20)
    return widget


def test_enhancement_is_independent_and_preserves_edits(
    workspace: CentralWidget,
) -> None:
    """Reference enhancement keeps image pixels, selection, rotation, and zoom aligned.

    Args:
        workspace: Visible test workspace.
    """
    widget: CentralWidget = workspace
    canvas: Any = widget.reference_canvas
    view: Any = widget.reference_graphics_view
    view.set_navigator_enabled(True)
    point: QtCore.QPointF = QtCore.QPointF(600, 400)
    canvas.add_point(point)
    canvas.select_points(QtCore.QRectF(590, 390, 20, 20))
    view.rotate_view(True)
    view.scale(2, 2)
    before: QtGui.QTransform = QtGui.QTransform(view.transform())
    dialog: EnhancementDialog = EnhancementDialog(
        widget.workspace_feedback, widget.compare_pane, canvas
    )
    dialog.brightness.setValue(40)
    dialog.apply()
    assert canvas.LUT[60] == 100
    assert not view.navigator_image.isNull()
    assert view.navigator_path.endswith("b.png")
    assert widget.canvas.LUT[60] == 60
    assert canvas.selection == [("Bird", point)]
    assert view.rotation_degrees == 90
    assert view.transform() == before
    dialog.original.setChecked(True)
    assert canvas.LUT[60] == 60
    dialog.original.setChecked(False)
    assert canvas.LUT[60] == 100
    dialog.reset()
    assert canvas.LUT[60] == 60
    dialog.close()


def test_view_and_enhancement_memory(workspace: CentralWidget, qtbot: Any) -> None:
    """Returning to an image restores its pane-local view and enhancement.

    Args:
        workspace: Visible test workspace.
        qtbot: Qt interaction fixture.
    """
    widget: CentralWidget = workspace
    view: Any = widget.graphicsView
    view.rotate_view(True)
    view.actual_size()
    view.scale(1.5, 1.5)
    view.centerOn(650, 450)
    before: QtGui.QTransform = QtGui.QTransform(view.transform())
    center: QtCore.QPointF = view.mapToScene(view.viewport().rect().center())
    path: str = str(Path(widget.canvas.directory) / "a.png")
    widget.canvas.enhancements[path] = (30, 0)
    widget.load_current_image("c.png")
    qtbot.wait(10)
    widget.load_current_image("a.png")
    qtbot.wait(10)
    assert view.rotation_degrees == 90
    assert view.transform() == before
    assert (
        QtCore.QLineF(center, view.mapToScene(view.viewport().rect().center())).length()
        < 2
    )
    assert widget.canvas.LUT[60] == 90
    widget.workspace_feedback.reset_view(view)
    assert view.rotation_degrees == 0


def test_drawing_handoff_and_unfinished_guard(
    workspace: CentralWidget, qtbot: Any
) -> None:
    """A pane's first click transfers completed tools but preserves unfinished shapes.

    Args:
        workspace: Visible test workspace.
        qtbot: Qt interaction fixture.
    """
    widget: CentralWidget = workspace
    current: Any = widget.graphicsView
    reference: Any = widget.reference_graphics_view
    current.start_line_annotation()
    current._add_line_vertex(QtCore.QPointF(300, 300))
    position: QtCore.QPoint = reference.mapFromScene(QtCore.QPointF(500, 400))
    qtbot.mouseClick(
        reference.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=position
    )
    assert len(current.line_points) == 1
    assert not reference.line_points
    assert widget.reference_canvas.points["b.png"] == {}
    assert "Unfinished" in widget.workspace_feedback.notice
    current._add_line_vertex(QtCore.QPointF(400, 300))
    current.finish_line_annotation()
    qtbot.mouseClick(
        reference.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=position
    )
    assert reference.interaction_mode is InteractionMode.LINE
    assert len(reference.line_points) == 1
    assert not widget.reference_canvas.points["b.png"]
    qtbot.keyClick(reference, QtCore.Qt.Key.Key_Escape)
    assert widget.workspace_feedback.transfer_mode is None


def test_recovery_and_confirmed_save(workspace: CentralWidget, tmp_path: Path) -> None:
    """Snapshots preserve unsaved cross-pane edits without touching the chosen save.

    Args:
        workspace: Visible test workspace.
        tmp_path: Isolated destination folder.
    """
    widget: CentralWidget = workspace
    project: Path = tmp_path / "survey.pnt"
    assert widget.canvas.save_points(str(project))
    widget.canvas.previous_file_name = str(project)
    previous: bytes = project.read_bytes()
    widget.reference_canvas.add_point(QtCore.QPointF(500, 400))
    widget.workspace_feedback.write_recovery()
    recovery: Path = tmp_path / ".survey.ddg-recovery.pnt"
    data: dict[str, Any] = json.loads(recovery.read_text())
    assert data["points"]["b.png"]["Bird"] == [{"x": 500, "y": 400}]
    assert project.read_bytes() == previous
    assert widget.canvas.dirty
    assert widget.canvas.previous_file_name == str(project)
    widget.reference_canvas.add_point(QtCore.QPointF(600, 400))
    widget.workspace_feedback.write_recovery()
    assert (tmp_path / ".survey.ddg-recovery-previous.pnt").exists()
    assert not widget.canvas.save_points(str(tmp_path / "missing" / "bad.pnt"))
    assert widget.canvas.dirty
    assert "Save failed" in widget.workspace_feedback.save_label.text()
    assert widget.canvas.save_points(str(project))
    assert not widget.canvas.dirty
    assert not widget.reference_canvas.dirty
    assert "Last saved survey.pnt" in widget.workspace_feedback.save_label.text()


def test_selection_feedback_and_clear(workspace: CentralWidget) -> None:
    """Selection controls report class counts and clear without deleting dots.

    Args:
        workspace: Visible test workspace.
    """
    canvas: Any = workspace.reference_canvas
    canvas.add_point(QtCore.QPointF(500, 400))
    canvas.select_points(QtCore.QRectF(490, 390, 20, 20))
    workspace.workspace_feedback.refresh()
    button: QtWidgets.QToolButton = workspace.workspace_feedback.selection_buttons[1]
    assert button.text() == "1 selected"
    assert button.toolTip() == "Bird: 1"
    button.menu().actions()[2].trigger()
    assert not canvas.selection
    assert len(canvas.points["b.png"]["Bird"]) == 1


def test_recover_snapshot_uses_save_as(
    workspace: CentralWidget, tmp_path: Path, monkeypatch: Any
) -> None:
    """Recovery restores points and requires a deliberate project save destination.

    Args:
        workspace: Visible test workspace.
        tmp_path: Isolated image folder.
        monkeypatch: Attribute substitution fixture.
    """
    canvas: Any = workspace.canvas
    canvas.add_point(QtCore.QPointF(400, 300))
    workspace.workspace_feedback.write_recovery()
    snapshot: Path = tmp_path / ".ddg-recovery.pnt"
    canvas.add_point(QtCore.QPointF(500, 300))
    monkeypatch.setattr(canvas, "dirty_data_check", lambda: True)
    monkeypatch.setattr(
        QtWidgets.QFileDialog,
        "getOpenFileName",
        lambda *_args, **_kwargs: (str(snapshot), ""),
    )
    workspace.workspace_feedback.recover()
    assert len(canvas.points["a.png"]["Bird"]) == 1
    assert canvas.previous_file_name is None
    assert canvas.dirty
    assert "Recovery loaded" in workspace.workspace_feedback.notice


def test_grayscale_enhancement(workspace: CentralWidget, tmp_path: Path) -> None:
    """Grayscale display pixels receive the same lookup table as RGB images.

    Args:
        workspace: Visible test workspace.
        tmp_path: Image destination folder.
    """
    path: Path = tmp_path / "gray.png"
    Image.new("L", (100, 100), 60).save(path)
    canvas: Any = workspace.canvas
    canvas.load_image(str(path))
    workspace.workspace_feedback.adjust_image(workspace.current_pane, canvas, (40, 0))
    items: list[QtWidgets.QGraphicsPixmapItem] = [
        item
        for item in canvas.items()
        if isinstance(item, QtWidgets.QGraphicsPixmapItem)
    ]
    assert items[0].pixmap().toImage().pixelColor(50, 50).red() == 100
