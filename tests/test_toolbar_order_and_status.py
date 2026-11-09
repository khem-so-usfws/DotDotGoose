"""Toolbar grouping, path visibility, legacy sidebar allocation, and quiet status."""

from pathlib import Path
from typing import Any

from PyQt6 import QtCore, QtWidgets

from ddg.central_graphics_view import InteractionMode
from ddg.main_window import MainWindow
from test_workspace_controls import window  # noqa: F401


def test_toolbar_order_pipes_and_one_active_tool(
    window: MainWindow, qtbot: Any
) -> None:
    """Panels/Display/Tools use two pipes and one exclusive interaction group.

    Args:
        window: Initialized application window.
        qtbot: Qt interaction fixture.
    """
    window.resize(1900, 950)
    qtbot.wait(30)
    layout: Any = window.centralWidget().workspace_layout
    controls: Any = window.workspace_controls
    panels: QtWidgets.QToolBar = window.findChild(QtWidgets.QToolBar, "sidebarToolbar")
    assert panels.x() < controls.display_toolbar.x() < controls.tools_toolbar.x()
    assert len(layout.toolbar_pipes) == 2
    assert all(pipe.text() == "|" and pipe.isVisible() for pipe in layout.toolbar_pipes)
    tools: Any = layout.groups[1]
    order: list[InteractionMode] = [
        InteractionMode.POINT,
        InteractionMode.LINE,
        InteractionMode.POLYGON,
        InteractionMode.SELECT,
        InteractionMode.COUNT,
    ]
    assert [button.defaultAction() for button in tools.buttons] == [
        controls.actions[mode] for mode in order
    ]
    assert [action for action in tools.selector.menu().actions()] == [
        controls.actions[mode] for mode in order
    ]
    assert len(tools.gaps) == 2
    for mode in order:
        controls.actions[mode].trigger()
        assert [action.isChecked() for action in controls.actions.values()].count(
            True
        ) == 1
        assert controls.mode is mode
        assert all(
            pane.graphics_view.interaction_mode is mode
            for pane, _canvas in layout.widget.workspace_feedback.panes
        )
    window.resize(900, 850)
    qtbot.wait(30)
    assert tools.compact
    assert all(not action.text() == "|" for action in tools.selector.menu().actions())
    assert tools.selector.text() == "Count dots"
    assert layout.class_indicator.isVisible()


def test_working_directory_has_visible_space(window: MainWindow, qtbot: Any) -> None:
    """The path has real visible width and safely abbreviates long directories.

    Args:
        window: Initialized application window.
        qtbot: Qt interaction fixture.
    """
    widget: Any = window.centralWidget()
    label: Any = widget.labelWorkingDirectory
    assert label.width() > 50
    assert label.text()
    assert label.full_path == widget.canvas.directory
    assert label.toolTip() == widget.canvas.directory
    assert widget.horizontalLayout.stretch(widget.horizontalLayout.indexOf(label)) == 1
    available_width: int = label.contentsRect().width()
    segment: str = "long-project-name/"
    segment_width: int = label.fontMetrics().horizontalAdvance(segment)
    # Force overflow regardless of the window width or platform font.
    repetitions: int = available_width // segment_width + 2
    long_path: str = f"C:/Users/observer/{segment * repetitions}DotDotGoose"
    assert label.fontMetrics().horizontalAdvance(long_path) > available_width
    label.setText(long_path)
    displayed_path: str = label.text()
    assert label.full_path == long_path
    assert label.toolTip() == long_path
    # Check middle elision without relying on Qt's choice of ellipsis glyph.
    assert displayed_path != long_path
    assert displayed_path.startswith("C:/")
    assert displayed_path.endswith("DotDotGoose")
    assert label.fontMetrics().horizontalAdvance(displayed_path) <= available_width
    label.setText(widget.canvas.directory)
    window.resize(900, 850)
    qtbot.wait(30)
    assert label.width() > 30
    assert label.text()


def test_legacy_right_proportion_and_manual_sizes(
    window: MainWindow, qtbot: Any
) -> None:
    """Right starts at one quarter of post-left space and respects manual adjustment.

    Args:
        window: Initialized application window.
        qtbot: Qt interaction fixture.
    """
    layout: Any = window.centralWidget().workspace_layout
    window.resize(1800, 950)
    qtbot.wait(30)
    sizes: list[int] = layout.splitter.sizes()
    assert abs(sizes[0] - 425) <= 2
    assert abs(sizes[2] / (sizes[1] + sizes[2]) - 0.25) < 0.005
    layout.splitter.setSizes([350, sizes[1] + 75, sizes[2]])
    layout.splitter.splitterMoved.emit(350, 1)
    chosen: list[int] = layout.splitter.sizes()
    window.resize(1900, 950)
    qtbot.wait(30)
    assert abs(layout.splitter.sizes()[0] - chosen[0]) <= 2
    assert abs(layout.splitter.sizes()[2] - chosen[2]) <= 2


def test_save_status_blank_confirmation_and_failures(
    window: MainWindow, tmp_path: Path, monkeypatch: Any
) -> None:
    """Clean idle is quiet; Saved expires while unsaved/error messages persist.

    Args:
        window: Initialized application window.
        tmp_path: Isolated save destination.
        monkeypatch: Clock substitution fixture.
    """
    now: list[float] = [100.0]
    monkeypatch.setattr("ddg.workspace_controls.monotonic", lambda: now[0])
    monkeypatch.setattr("ddg.workspace_feedback.monotonic", lambda: now[0])
    widget: Any = window.centralWidget()
    controls: Any = window.workspace_controls
    widget.canvas.dirty = False
    controls.refresh()
    assert controls.save_indicator.text() == ""
    widget.canvas.add_point(QtCore.QPointF(300, 300))
    controls.refresh()
    assert controls.save_indicator.text() == "Unsaved changes"
    assert widget.canvas.save_points(str(tmp_path / "survey.pnt"))
    assert controls.save_indicator.text() == "Saved"
    now[0] = 106.0
    controls.refresh()
    assert controls.save_indicator.text() == ""
    assert "survey.pnt" in controls.save_indicator.toolTip()
    widget.canvas.add_point(QtCore.QPointF(350, 300))
    assert not widget.canvas.save_points(str(tmp_path / "missing" / "survey.pnt"))
    now[0] = 1000.0
    controls.refresh()
    assert controls.save_indicator.text() == "Save failed"
    assert widget.canvas.dirty
    assert widget.canvas.save_points(str(tmp_path / "survey.pnt"))
    widget.workspace_feedback.recovery_text = "Recovery failed: test failure"
    controls.refresh()
    assert controls.save_indicator.text() == "Recovery failed"
