"""Active-image field binding, responsive overflow, and compact project controls."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PyQt6 import QtCore, QtGui, QtWidgets

from ddg.central_graphics_view import InteractionMode
from ddg.fields import BoxText, LineText
from ddg.main_window import MainWindow
from test_workspace_controls import window  # noqa: F401


def test_pending_fields_follow_original_image(
    window: MainWindow, qtbot: Any, tmp_path: Path
) -> None:
    """Pending text commits to its old image before activation and save/recovery.

    Args:
        window: Initialized main window.
        qtbot: Qt interaction fixture.
        tmp_path: Isolated project destination.
    """
    widget: Any = window.centralWidget()
    canvas: Any = widget.canvas
    canvas.add_custom_field(["Note", "line"])
    canvas.add_custom_field(["Details", "box"])
    qtbot.wait(1)
    line: LineText = widget.frameCustomFields.findChild(LineText)
    box: BoxText = widget.frameCustomFields.findChild(BoxText)
    qtbot.keyClicks(line, "Current text")
    assert line.timer.isActive()
    assert canvas.dirty
    widget._set_last_active_view("reference")
    assert canvas.custom_fields["data"]["Note"]["a.png"] == "Current text"
    assert not line.timer.isActive()
    assert line.text() == ""
    assert widget.groupBoxImageData.title() == "Image data — Reference"
    assert widget.groupBoxImageData.toolTip() == "b.png"
    qtbot.keyClicks(line, "Reference text")
    path: Path = tmp_path / "survey.pnt"
    assert canvas.save_points(str(path))
    data: dict[str, Any] = json.loads(path.read_text())
    assert data["custom_fields"]["data"]["Note"]["b.png"] == "Reference text"
    assert not line.timer.isActive()
    box.setPlainText("Reference notes\nsecond line")
    widget.workspace_feedback.write_recovery()
    recovery: dict[str, Any] = json.loads((tmp_path / ".ddg-recovery.pnt").read_text())
    assert (
        recovery["custom_fields"]["data"]["Details"]["b.png"]
        == "Reference notes\nsecond line"
    )
    widget._set_last_active_view("current")
    assert line.text() == "Current text"
    assert box.toPlainText() == ""
    qtbot.wait(1050)
    assert canvas.custom_fields["data"]["Note"]["a.png"] == "Current text"
    assert canvas.custom_fields["data"]["Note"]["b.png"] == "Reference text"


def test_coordinates_reference_and_project_survey(
    window: MainWindow, qtbot: Any
) -> None:
    """Image coordinates follow activation while Survey ID remains project-wide.

    Args:
        window: Initialized main window.
        qtbot: Qt interaction fixture.
    """
    widget: Any = window.centralWidget()
    widget._set_last_active_view("reference")
    qtbot.keyClicks(widget.lineEditX, "123")
    qtbot.keyClicks(widget.lineEditY, "456")
    assert widget.canvas.coordinates["b.png"] == {"x": "123", "y": "456"}
    assert "a.png" not in widget.canvas.coordinates
    assert widget.canvas.dirty
    assert widget.workspace_layout.bound_canvas is widget.reference_canvas
    qtbot.keyClicks(widget.lineEditSurveyId, "SURVEY")
    widget._set_last_active_view("current")
    assert widget.lineEditX.text() == ""
    assert widget.lineEditSurveyId.text() == "SURVEY"
    widget._set_last_active_view("reference")
    assert widget.lineEditX.text() == "123"
    assert widget.lineEditY.text() == "456"
    window.compare_action.setChecked(False)
    assert widget.workspace_layout.bound_canvas is widget.canvas
    assert widget.groupBoxImageData.title() == "Image data — Current"


def test_pane_overflow_and_restore(window: MainWindow, qtbot: Any) -> None:
    """Narrow headers expose hidden controls in More and restore them when widened.

    Args:
        window: Initialized main window.
        qtbot: Qt interaction fixture.
    """
    widget: Any = window.centralWidget()
    window.resize(900, 850)
    qtbot.wait(30)
    for overflow in widget.workspace_layout.pane_overflows:
        pane: Any = overflow.pane
        assert pane.layout().count() == 3
        assert pane.rect().contains(pane.overflow_button.geometry())
        assert pane.image_combo.width() >= pane.image_combo.minimumWidth()
        assert pane.actual_size_button.isHidden()
        action: QtGui.QAction = overflow.proxies[pane.actual_size_button]
        assert action.isVisible()
        action.trigger()
        assert abs(pane.graphics_view.transform().determinant() - 1.0) < 0.0001
        assert (
            pane.graphics_view.parentWidget()
            .rect()
            .contains(pane.graphics_view.geometry())
        )
        assert widget.frameCenter.rect().contains(
            pane.mapTo(widget.frameCenter, pane.rect().bottomRight())
        )
    window.resize(1900, 950)
    qtbot.wait(30)
    for overflow in widget.workspace_layout.pane_overflows:
        assert not overflow.pane.actual_size_button.isHidden()
        assert not overflow.proxies[overflow.pane.actual_size_button].isVisible()
        assert not overflow.enhance.isHidden()
        assert not overflow.pane.previous_button.isHidden()


def test_toolbar_compaction_preserves_actions(window: MainWindow, qtbot: Any) -> None:
    """Large text compacts tools without hiding menu commands or the active tool.

    Args:
        window: Initialized main window.
        qtbot: Qt interaction fixture.
    """
    controls: Any = window.workspace_controls
    layout: Any = window.centralWidget().workspace_layout
    font: QtGui.QFont = QtGui.QFont(window.font())
    font.setPointSize(16)
    window.setFont(font)
    window.left_sidebar_action.setChecked(False)
    window.right_sidebar_action.setChecked(False)
    window.resize(900, 850)
    qtbot.wait(50)
    controls.select_tool(InteractionMode.SELECT)
    qtbot.wait(10)
    tools: Any = layout.groups[1]
    assert tools.compact
    assert tools.selector.text() == "Select/Edit"
    assert not tools.selector.isHidden()
    assert controls.actions[InteractionMode.SELECT].isVisible()
    assert controls.actions[InteractionMode.SELECT].isChecked()
    assert set(tools.selector.menu().actions()) == set(controls.actions.values())
    for group in layout.groups:
        visible: list[QtWidgets.QToolButton] = (
            [group.selector] if group.compact else group.buttons
        )
        for button in visible:
            rect: QtCore.QRect = QtCore.QRect(
                button.mapTo(window, QtCore.QPoint()), button.size()
            )
            assert window.rect().contains(rect)
    assert layout.class_indicator.isVisible()
    assert "Bird" in layout.class_indicator.toolTip()


def test_sidebar_resize_export_and_path(window: MainWindow, monkeypatch: Any) -> None:
    """Sidebars resize independently and compact project actions retain behavior.

    Args:
        window: Initialized main window.
        monkeypatch: Attribute substitution fixture.
    """
    widget: Any = window.centralWidget()
    layout: Any = widget.workspace_layout
    assert layout.splitter.count() == 3
    assert widget.framePointWidget.minimumWidth() < 425
    assert not widget.framePointWidget.isHidden()
    assert not widget.frameCustomField.isHidden()
    old: list[int] = layout.splitter.sizes()
    layout.splitter.setSizes([old[0] + 50, old[1] - 100, old[2] + 50])
    assert layout.splitter.sizes() != old
    assert not widget.labelWorkingDirectory.isHidden()
    assert not widget.pushButtonFolder.isHidden()
    assert widget.labelWorkingDirectory.text() == widget.canvas.directory
    assert widget.labelWorkingDirectory.toolTip() == widget.canvas.directory
    assert layout.class_indicator.parentWidget() is layout.groups[1]
    layout.copy_path()
    assert QtWidgets.QApplication.clipboard().text() == widget.canvas.directory
    point: Any = widget.point_widget
    assert point.radioButtonCounts.isHidden()
    actions: list[QtGui.QAction] = point.pushButtonExport.menu().actions()
    assert [action.text() for action in actions] == [
        "Counts…",
        "Points…",
        "Chips…",
        "Overlay…",
    ]
    selected: list[bool] = []
    monkeypatch.setattr(
        point, "export", lambda: selected.append(point.radioButtonPoints.isChecked())
    )
    actions[1].trigger()
    assert selected == [True]


def test_header_activation_and_image_change_flush(
    window: MainWindow, qtbot: Any, tmp_path: Path
) -> None:
    """Header controls activate their pane and image changes retain pending text.

    Args:
        window: Initialized main window.
        qtbot: Qt interaction fixture.
        tmp_path: Source-image folder.
    """
    from PIL import Image

    widget: Any = window.centralWidget()
    widget.canvas.add_custom_field(["Note", "line"])
    qtbot.wait(1)
    line: LineText = widget.frameCustomFields.findChild(LineText)
    qtbot.mouseClick(widget.compare_pane.fit_button, QtCore.Qt.MouseButton.LeftButton)
    assert widget.workspace_layout.bound_canvas is widget.reference_canvas
    qtbot.keyClicks(line, "Before reference switch")
    Image.new("RGB", (600, 400)).save(tmp_path / "c.png")
    widget.canvas.points["c.png"] = {}
    widget.load_reference_image("c.png")
    assert (
        widget.canvas.custom_fields["data"]["Note"]["b.png"]
        == "Before reference switch"
    )
    assert widget.workspace_layout.image_name == "c.png"
    assert line.text() == ""
    qtbot.keyClicks(line, "New image")
    widget.canvas.load_image(str(tmp_path / "a.png"))
    assert widget.workspace_layout.image_name == "c.png"
    assert line.text() == "New image"
    assert widget.canvas.custom_fields["data"]["Note"]["c.png"] == "New image"


def test_reset_clears_pending_bindings(window: MainWindow, qtbot: Any) -> None:
    """Reset discards committed old-project values and disables image editors.

    Args:
        window: Initialized main window.
        qtbot: Qt interaction fixture.
    """
    widget: Any = window.centralWidget()
    widget.canvas.add_custom_field(["Note", "line"])
    qtbot.wait(1)
    widget._set_last_active_view("reference")
    edit: LineText = widget.frameCustomFields.findChild(LineText)
    qtbot.keyClicks(edit, "Discard with reset")
    widget.canvas.reset()
    qtbot.wait(20)
    assert widget.canvas.custom_fields == {"fields": [], "data": {}}
    assert widget.workspace_layout.image_name == ""
    assert not widget.lineEditX.isEnabled()
    assert not widget.frameCustomFields.isEnabled()
    assert widget.pushButtonAddField.isEnabled()
    qtbot.wait(1050)
    assert widget.canvas.custom_fields["data"] == {}


def test_many_fields_scroll_without_shrinking_editors(
    window: MainWindow, qtbot: Any
) -> None:
    """A small maximized-style workspace preserves editable field heights.

    Args:
        window: Initialized main window.
        qtbot: Qt interaction fixture.
    """
    widget: Any = window.centralWidget()
    for index in range(12):
        widget.canvas.add_custom_field([f"Field {index}", "box"])
    window.resize(900, 600)
    qtbot.wait(30)
    assert widget.scrollAreaCustomFields.verticalScrollBar().maximum() > 0
    for edit in widget.frameCustomFields.findChildren(BoxText):
        assert edit.height() >= edit.minimumHeight()
        assert edit.isEnabled()
        assert edit.minimumHeight() >= edit.fontMetrics().lineSpacing() * 3
