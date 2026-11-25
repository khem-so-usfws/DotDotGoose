"""Integration coverage for the four-pane dock and editing lifecycle."""

from pathlib import Path
from typing import Any

from PIL import Image
from PyQt6 import QtCore, QtGui, QtWidgets

from ddg.central_graphics_view import InteractionMode
from ddg.image_workspace import ImageWorkspace
from ddg.main_window import MainWindow
from test_workspace_controls import window  # noqa: F401


def add_photos(window: MainWindow, directory: Path) -> None:
    """Give the workspace a four-photo sequence with distinguishable filenames.

    Args:
        window: Initialized application window.
        directory: Working directory for the fixture.
    """
    widget: Any = window.centralWidget()
    for name in ("c.png", "d.png"):
        Image.new("RGB", (1200, 800), (90, 100, 110)).save(directory / name)
        widget.canvas.points[name] = {}


def test_four_docks_edit_independently(
    window: MainWindow, qtbot: Any, tmp_path: Path
) -> None:
    """All four panes show editable photos and share counts and history.

    Args:
        window: Initialized application window.
        qtbot: Qt interaction fixture.
        tmp_path: Working directory for the fixture.
    """
    add_photos(window, tmp_path)
    widget: Any = window.centralWidget()
    workspace: ImageWorkspace = widget.image_workspace
    window.resize(1920, 1000)
    workspace.set_count(4)
    qtbot.wait(40)
    assert [
        canvas.current_image_name for _pane, canvas in widget.image_panes.values()
    ] == ["a.png", "b.png", "c.png", "d.png"]
    first: QtCore.QRect = workspace.docks["current"].geometry()
    second: QtCore.QRect = workspace.docks["reference"].geometry()
    third: QtCore.QRect = workspace.docks["pane3"].geometry()
    fourth: QtCore.QRect = workspace.docks["pane4"].geometry()
    assert first.top() == second.top()
    assert first.bottom() < third.top()
    assert second.bottom() < fourth.top()
    assert first.right() < second.left()
    for pane, canvas in widget.image_panes.values():
        view = pane.graphics_view
        qtbot.mouseClick(
            view.viewport(),
            QtCore.Qt.MouseButton.LeftButton,
            pos=view.viewport().rect().center(),
        )
        assert len(widget.canvas.points[canvas.current_image_name]["Bird"]) == 1
        assert widget.workspace_layout.bound_canvas is canvas

    pane, canvas = widget.image_panes["pane3"]
    view = pane.graphics_view
    window.workspace_controls.select_tool(InteractionMode.LINE)
    qtbot.mouseClick(
        view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        pos=view.viewport().rect().center(),
    )
    assert view.line_points
    widget._set_last_active_view("pane4")
    assert widget.workspace_layout.bound_canvas is canvas
    other = widget.image_panes["pane4"][0].graphics_view
    qtbot.mouseClick(
        other.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        QtCore.Qt.KeyboardModifier.ShiftModifier,
        pos=other.viewport().rect().center(),
    )
    assert not other.line_points
    assert not workspace.docks["pane3"].close()
    qtbot.keyClick(view, QtCore.Qt.Key.Key_Escape)
    widget.undo_global_history()
    assert not widget.canvas.points["d.png"]["Bird"]

    # Opening an existing photo in a second pane preserves independent browsing.
    widget.load_pane_image("pane3", "a.png")
    assert widget.reference_canvas.current_image_name == "b.png"
    canvas.add_landmark_annotation(QtCore.QPointF(500, 400))
    assert len(widget.canvas.external_annotations) == 1
    widget.undo_global_history()
    assert not widget.canvas.external_annotations


def test_float_close_and_restore(
    window: MainWindow, qtbot: Any, tmp_path: Path
) -> None:
    """Reopen a closed float docked and restore remaining open floats on restart.

    Args:
        window: Initialized application window.
        qtbot: Qt interaction fixture.
        tmp_path: Working directory for the fixture.
    """
    add_photos(window, tmp_path)
    widget: Any = window.centralWidget()
    workspace: ImageWorkspace = widget.image_workspace
    workspace.set_count(4)
    pane, canvas = widget.image_panes["pane3"]
    view = pane.graphics_view
    view.rotate_view(True)
    view.scale(4, 4)
    view.centerOn(500, 400)
    transform: QtGui.QTransform = QtGui.QTransform(view.transform())
    canvas.enhancements[str(tmp_path / "c.png")] = (-30, 20)
    workspace.float_actions["pane3"].trigger()
    workspace.float_actions["pane4"].trigger()
    qtbot.wait(30)
    assert workspace.docks["pane3"].isFloating()
    assert workspace.docks["pane4"].isFloating()
    # The offscreen platform has one small virtual display.
    screen: QtGui.QScreen = QtWidgets.QApplication.primaryScreen()
    workspace.docks["pane4"].move(
        screen.availableGeometry().topLeft() + QtCore.QPoint(20, 20)
    )
    assert workspace.docks["pane3"].close()
    assert "pane3" not in workspace.opened
    assert canvas.current_image_name is None
    workspace.reopen("pane3")
    qtbot.wait(30)
    assert not workspace.docks["pane3"].isFloating()
    assert workspace.docks["pane4"].isFloating()
    assert canvas.current_image_name == "c.png"
    assert view.rotation_degrees == 90
    assert view.transform() == transform

    workspace.toggle_float("pane3")
    assert workspace.docks["pane3"].close()
    workspace.save()
    restored: MainWindow = MainWindow()
    qtbot.addWidget(restored)
    restored.resize(1500, 900)
    restored_widget: Any = restored.centralWidget()
    restored_widget.canvas.directory = str(tmp_path)
    restored_widget.canvas.points.update({name: {} for name in widget.canvas.points})
    restored.show()
    restored_widget.load_current_image("a.png")
    qtbot.wait(40)
    restored_workspace: ImageWorkspace = restored_widget.image_workspace
    assert restored_workspace.opened == workspace.opened
    assert restored_workspace.docks["pane4"].isFloating()
    restored_workspace.reopen("pane3")
    qtbot.wait(20)
    assert not restored_workspace.docks["pane3"].isFloating()
    restored_pane, restored_canvas = restored_widget.image_panes["pane3"]
    assert restored_canvas.current_image_name == "c.png"
    assert restored_pane.graphics_view.rotation_degrees == 90
    assert restored_canvas.enhancements[str(tmp_path / "c.png")] == (-30, 20)
