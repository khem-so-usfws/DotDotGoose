"""Restored sidebar/folder layout and consistent project menu buttons."""

from pathlib import Path
from typing import Any

import pytest
from PyQt6 import QtCore, QtWidgets

from ddg.central_graphics_view import InteractionMode
from ddg.main_window import MainWindow
from test_workspace_controls import window  # noqa: F401


@pytest.fixture(autouse=True)
def resource_paths() -> None:
    """Register the same icon search path used by the application launcher."""
    QtCore.QDir.addSearchPath("icons", str(Path(__file__).parents[1] / "icons"))


def test_starting_width_and_resizing(window: MainWindow, qtbot: Any) -> None:
    """A wide starting window reserves 425 pixels but allows manual resizing.

    Args:
        window: Initialized main window.
        qtbot: Qt interaction fixture.
    """
    layout: Any = window.centralWidget().workspace_layout
    window.resize(1700, 900)
    qtbot.wait(20)
    assert abs(layout.splitter.sizes()[0] - 425) <= 2
    old: list[int] = layout.splitter.sizes()
    layout.splitter.setSizes([350, old[1] + 75, old[2]])
    assert abs(layout.splitter.sizes()[0] - 350) <= 2
    assert window.centralWidget().framePointWidget.minimumWidth() < 425


def test_class_beside_count_and_compact_tool(window: MainWindow, qtbot: Any) -> None:
    """The class stays with Tools in expanded/compact layouts, outside the status bar.

    Args:
        window: Initialized main window.
        qtbot: Qt interaction fixture.
    """
    widget: Any = window.centralWidget()
    layout: Any = widget.workspace_layout
    window.resize(1700, 900)
    qtbot.wait(20)
    group: Any = layout.groups[1]
    assert (
        group.buttons[-1].defaultAction()
        is window.workspace_controls.actions[InteractionMode.COUNT]
    )
    assert group.layout().itemAt(group.class_slot).widget() is layout.class_indicator
    assert layout.class_indicator.parentWidget() is group
    assert not window.statusBar().isAncestorOf(layout.class_indicator)
    assert "Bird" in layout.class_indicator.text()
    group.set_compact(True)
    assert group.layout().itemAt(group.layout().count() - 2).widget() is group.selector
    assert (
        group.layout().itemAt(group.layout().count() - 1).widget()
        is layout.class_indicator
    )
    assert layout.class_indicator.isVisible()
    group.set_compact(False)
    assert group.layout().itemAt(group.class_slot).widget() is layout.class_indicator


def test_restored_folder_and_matching_menus(window: MainWindow) -> None:
    """The original folder row is visible; Recover/Export share icon/menu styling.

    Args:
        window: Initialized main window.
    """
    widget: Any = window.centralWidget()
    assert widget.pushButtonFolder.isVisible()
    assert widget.label_3.text() == "Working Directory:"
    assert widget.label_3.isVisible()
    assert widget.labelWorkingDirectory.text() == widget.canvas.directory
    recover: QtWidgets.QPushButton = widget.workspace_feedback.recover_button
    export: QtWidgets.QPushButton = widget.point_widget.pushButtonExport
    assert type(recover) is type(export)
    assert recover.menu() is not None
    assert export.menu() is not None
    assert not recover.icon().isNull()
    assert recover.iconSize() == export.iconSize()
    for button in (
        widget.point_widget.pushButtonLoadPoints,
        widget.point_widget.pushButtonImport,
        widget.point_widget.pushButtonSave,
        widget.point_widget.pushButtonReset,
        recover,
        export,
    ):
        assert "text-align: left" in button.styleSheet()
        assert button.height() == widget.point_widget.pushButtonSave.height()
