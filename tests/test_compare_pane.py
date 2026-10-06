"""Regression tests for the lightweight two-image comparison pane."""

from __future__ import annotations

from typing import Any

import json
from pathlib import Path
from unittest.mock import Mock

from PIL import Image
from PyQt6 import QtCore, QtGui, QtWidgets

from ddg.central_graphics_view import CentralGraphicsView
from ddg.central_widget import CentralWidget


def _write_image(path: Path) -> None:
    """Write a tiny RGB image suitable for Canvas loading."""
    Image.new("RGB", (40, 30), (128, 128, 128)).save(path)


def test_reference_view_disables_count_point_placement(qtbot: Any) -> None:
    """Plain clicks in a reference view must never emit DDG count points."""
    view: CentralGraphicsView = CentralGraphicsView()
    scene: QtWidgets.QGraphicsScene = QtWidgets.QGraphicsScene()
    scene.addRect(0.0, 0.0, 100.0, 100.0)
    view.setScene(scene)
    view.set_count_point_placement_enabled(False)
    view.resize(200, 200)
    qtbot.addWidget(view)
    view.show()

    emitted: list[QtCore.QPointF] = []
    view.add_point.connect(emitted.append)
    qtbot.mouseClick(
        view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        pos=QtCore.QPoint(100, 100),
    )

    assert emitted == []


def test_compare_toggle_loads_one_reference_image(qtbot: Any, tmp_path: Path) -> None:
    """Compare should add exactly one non-counting reference image."""
    first: Path = tmp_path / "IMG_1001.JPG"
    second: Path = tmp_path / "IMG_1002.JPG"
    _write_image(first)
    _write_image(second)

    widget: CentralWidget = CentralWidget()
    qtbot.addWidget(widget)
    widget.canvas.directory = str(tmp_path)
    widget.canvas.points = {first.name: {}, second.name: {}}
    widget.canvas.load_image(str(first))

    widget.set_compare_enabled(True)

    assert widget.compare_enabled() is True
    assert widget.compare_pane.isHidden() is False
    assert widget.reference_canvas.current_image_name == second.name
    assert widget.reference_graphics_view.count_point_placement_enabled is False
    assert widget.current_compare_label.text().endswith(first.name)


def test_compare_supports_horizontal_and_vertical_layouts(qtbot: Any) -> None:
    """The splitter should support both agreed two-image layouts."""
    widget: CentralWidget = CentralWidget()
    qtbot.addWidget(widget)

    widget.set_compare_layout("1x2")
    assert widget.compare_splitter.orientation() == QtCore.Qt.Orientation.Horizontal
    assert widget.compare_layout() == "1x2"

    widget.set_compare_layout("2x1")
    assert widget.compare_splitter.orientation() == QtCore.Qt.Orientation.Vertical
    assert widget.compare_layout() == "2x1"


def test_compare_defaults_to_1x2_when_no_preference_exists(qtbot: Any) -> None:
    """A fresh Compare configuration should start side by side."""
    settings: QtCore.QSettings = QtCore.QSettings("AMNH", "DotDotGoose")
    setting_key: str = "compare/layout"
    had_previous_value: bool = settings.contains(setting_key)
    previous_value: object | None = settings.value(setting_key)
    settings.remove(setting_key)
    settings.sync()

    try:
        widget: CentralWidget = CentralWidget()
        qtbot.addWidget(widget)
        assert widget.compare_layout() == "1x2"
        assert (
            widget.compare_splitter.orientation()
            == QtCore.Qt.Orientation.Horizontal
        )
    finally:
        if had_previous_value:
            settings.setValue(setting_key, previous_value)
        else:
            settings.remove(setting_key)
        settings.sync()


def test_make_reference_current_swaps_images(qtbot: Any, tmp_path: Path) -> None:
    """Promoting Reference should preserve the former Current as Reference."""
    first: Path = tmp_path / "IMG_2001.JPG"
    second: Path = tmp_path / "IMG_2002.JPG"
    _write_image(first)
    _write_image(second)

    widget: CentralWidget = CentralWidget()
    qtbot.addWidget(widget)
    widget.canvas.directory = str(tmp_path)
    widget.canvas.points = {first.name: {}, second.name: {}}
    widget.canvas.load_image(str(first))
    widget.set_compare_enabled(True)

    assert widget.reference_canvas.current_image_name == second.name
    widget.make_reference_current()

    assert widget.canvas.current_image_name == second.name
    assert widget.reference_canvas.current_image_name == first.name
    assert widget.compare_pane.selected_image() == first.name


def test_hiding_compare_releases_reference_image_memory(
    qtbot: Any, tmp_path: Path
) -> None:
    """Compare OFF should retain selection but release the decoded second image."""
    first: Path = tmp_path / "IMG_3001.JPG"
    second: Path = tmp_path / "IMG_3002.JPG"
    _write_image(first)
    _write_image(second)

    widget: CentralWidget = CentralWidget()
    qtbot.addWidget(widget)
    widget.canvas.directory = str(tmp_path)
    widget.canvas.points = {first.name: {}, second.name: {}}
    widget.canvas.load_image(str(first))
    widget.set_compare_enabled(True)
    assert widget.reference_canvas.image_cache["data"] is not None
    assert not hasattr(widget.reference_canvas, "pixmap")

    widget.set_compare_enabled(False)

    assert widget.reference_canvas.current_image_name is None
    assert widget.reference_canvas.image_cache["data"] is None
    assert widget._last_reference_image_name == second.name

    widget.set_compare_enabled(True)
    assert widget.reference_canvas.current_image_name == second.name


def test_compare_splitter_can_shrink_either_image_pane(qtbot: Any) -> None:
    """Compare headers must not impose a large splitter minimum size."""
    widget: CentralWidget = CentralWidget()
    widget.resize(1400, 700)
    qtbot.addWidget(widget)
    widget.show()

    ignored: QtWidgets.QSizePolicy.Policy = QtWidgets.QSizePolicy.Policy.Ignored
    assert widget.current_pane.sizePolicy().horizontalPolicy() == ignored
    assert widget.current_pane.sizePolicy().verticalPolicy() == ignored
    assert widget.compare_pane.sizePolicy().horizontalPolicy() == ignored
    assert widget.compare_pane.sizePolicy().verticalPolicy() == ignored


def test_selection_target_is_last_clicked_not_last_focused(
    qtbot: Any, tmp_path: Path
) -> None:
    """Focus changes must not retarget pane-specific selection commands."""
    first: Path = tmp_path / "IMG_4001.JPG"
    second: Path = tmp_path / "IMG_4002.JPG"
    _write_image(first)
    _write_image(second)

    widget: CentralWidget = CentralWidget()
    qtbot.addWidget(widget)
    widget.canvas.directory = str(tmp_path)
    widget.canvas.points = {first.name: {}, second.name: {}}
    widget.canvas.load_image(str(first))
    widget.set_compare_enabled(True)

    widget.reference_graphics_view.view_activated.emit()
    # Simulate Current receiving focus while the pointer travels to the menu.
    # Focus alone must not steal a pane-specific edit command.
    widget.graphicsView.view_focused.emit()

    assert widget.start_annotation_selection() is True
    assert widget.reference_graphics_view.interaction_mode.value == "select"
    assert widget.graphicsView.interaction_mode.value == "count"


def test_reference_pane_can_create_native_annotation_without_preclick(
    qtbot: Any, tmp_path: Path
) -> None:
    """The first drawing click should choose Reference and place the point."""
    first: Path = tmp_path / "IMG_5001.JPG"
    second: Path = tmp_path / "IMG_5002.JPG"
    _write_image(first)
    _write_image(second)

    widget: CentralWidget = CentralWidget()
    widget.resize(1400, 700)
    qtbot.addWidget(widget)
    widget.canvas.directory = str(tmp_path)
    widget.canvas.points = {first.name: {}, second.name: {}}
    widget.canvas.load_image(str(first))
    widget.set_compare_enabled(True)
    widget.show()

    assert widget.start_landmark_point() is True
    assert widget._pending_compare_annotation_mode is not None
    qtbot.mouseClick(
        widget.reference_graphics_view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        pos=QtCore.QPoint(30, 30),
    )

    sidecar: Path = second.with_suffix(".json")
    assert sidecar.exists()
    document: dict[str, object] = json.loads(sidecar.read_text(encoding="utf-8"))
    shapes: list[dict[str, object]] = document["shapes"]  # type: ignore[assignment]
    assert len(shapes) == 1
    assert shapes[0]["label"] == "landmark"
    assert shapes[0]["shape_type"] == "point"
    assert widget._last_active_view_name == "reference"
    assert widget._pending_compare_annotation_mode is None


def test_first_cutline_click_claims_pane_and_handoff_needs_no_preactivation(
    qtbot: Any, tmp_path: Path
) -> None:
    """The first vertex click should choose the pane and own the cutline tool."""
    first: Path = tmp_path / "IMG_6001.JPG"
    second: Path = tmp_path / "IMG_6002.JPG"
    _write_image(first)
    _write_image(second)

    widget: CentralWidget = CentralWidget()
    widget.resize(1200, 700)
    qtbot.addWidget(widget)
    widget.canvas.directory = str(tmp_path)
    widget.canvas.points = {first.name: {}, second.name: {}}
    widget.canvas.load_image(str(first))
    widget.set_compare_enabled(True)
    widget.show()

    assert widget.start_cutline() is True
    assert widget.graphicsView.interaction_mode.value == "count"
    assert widget.reference_graphics_view.interaction_mode.value == "count"
    qtbot.mouseClick(
        widget.graphicsView.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        pos=QtCore.QPoint(20, 20),
    )
    assert widget.graphicsView.interaction_mode.value == "line"
    assert len(widget.graphicsView.line_points) == 1

    # Choosing a new cutline explicitly supersedes the unfinished Current line,
    # then the first Reference click both claims Reference and adds a vertex.
    assert widget.start_cutline() is True
    assert widget.graphicsView.interaction_mode.value == "count"
    qtbot.mouseClick(
        widget.reference_graphics_view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        pos=QtCore.QPoint(25, 25),
    )
    assert widget.reference_graphics_view.interaction_mode.value == "line"
    assert len(widget.reference_graphics_view.line_points) == 1
    assert widget.graphicsView.line_points == []


def test_drawing_tool_can_claim_current_after_reference_without_preactivation(
    qtbot: Any, tmp_path: Path
) -> None:
    """A newly armed tool should be claimable by either pane's first click."""
    first: Path = tmp_path / "IMG_7001.JPG"
    second: Path = tmp_path / "IMG_7002.JPG"
    _write_image(first)
    _write_image(second)

    widget: CentralWidget = CentralWidget()
    widget.resize(1200, 700)
    qtbot.addWidget(widget)
    widget.canvas.directory = str(tmp_path)
    widget.canvas.points = {first.name: {}, second.name: {}}
    widget.canvas.load_image(str(first))
    widget.set_compare_enabled(True)
    widget.show()

    assert widget.start_count_region_polygon() is True
    qtbot.mouseClick(
        widget.reference_graphics_view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        pos=QtCore.QPoint(20, 20),
    )
    assert widget.reference_graphics_view.interaction_mode.value == "polygon"
    assert len(widget.reference_graphics_view.polygon_points) == 1

    assert widget.start_count_region_polygon() is True
    qtbot.mouseClick(
        widget.graphicsView.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        pos=QtCore.QPoint(30, 30),
    )
    assert widget.reference_graphics_view.interaction_mode.value == "count"
    assert widget.reference_graphics_view.polygon_points == []
    assert widget.graphicsView.interaction_mode.value == "polygon"
    assert len(widget.graphicsView.polygon_points) == 1


def test_undo_redo_is_global_across_compare_panes(qtbot: Any, tmp_path: Path) -> None:
    """Ctrl+Z/Y history should follow edit chronology, not active pane."""
    first: Path = tmp_path / "IMG_8001.JPG"
    second: Path = tmp_path / "IMG_8002.JPG"
    _write_image(first)
    _write_image(second)

    widget: CentralWidget = CentralWidget()
    qtbot.addWidget(widget)
    widget.canvas.directory = str(tmp_path)
    widget.canvas.points = {first.name: {}, second.name: {}}
    widget.canvas.load_image(str(first))
    widget.set_compare_enabled(True)

    widget.canvas.add_landmark_annotation(QtCore.QPointF(10.0, 10.0))
    widget.reference_canvas.add_landmark_annotation(QtCore.QPointF(20.0, 20.0))
    first_sidecar: Path = first.with_suffix(".json")
    second_sidecar: Path = second.with_suffix(".json")
    assert first_sidecar.exists()
    assert second_sidecar.exists()

    # Deliberately mark Current active. The latest edit still belongs to
    # Reference and must be the first operation undone.
    widget._set_last_active_view("current")
    widget.undo_global_history()
    assert first_sidecar.exists()
    assert not second_sidecar.exists()

    widget.undo_global_history()
    assert not first_sidecar.exists()

    widget.redo_global_history()
    assert first_sidecar.exists()
    assert not second_sidecar.exists()

    widget.redo_global_history()
    assert second_sidecar.exists()


def test_new_edit_invalidates_redo_across_compare_panes(
    qtbot: Any, tmp_path: Path
) -> None:
    """A new edit in either pane should invalidate global redo history."""
    first: Path = tmp_path / "IMG_8101.JPG"
    second: Path = tmp_path / "IMG_8102.JPG"
    _write_image(first)
    _write_image(second)

    widget: CentralWidget = CentralWidget()
    qtbot.addWidget(widget)
    widget.canvas.directory = str(tmp_path)
    widget.canvas.points = {first.name: {}, second.name: {}}
    widget.canvas.load_image(str(first))
    widget.set_compare_enabled(True)

    widget.canvas.add_landmark_annotation(QtCore.QPointF(10.0, 10.0))
    widget.reference_canvas.add_landmark_annotation(QtCore.QPointF(20.0, 20.0))
    widget.undo_global_history()
    assert len(widget._global_redo_order) == 1

    widget.canvas.add_landmark_annotation(QtCore.QPointF(30.0, 30.0))
    assert widget._global_redo_order == []
    assert widget.reference_canvas.redo_queue == []


def test_completed_annotations_start_directly_in_other_pane(
    qtbot: Any, tmp_path: Path
) -> None:
    """Completed geometry should allow direct first-click drawing in the other pane."""
    first: Path = tmp_path / "IMG_8201.JPG"
    second: Path = tmp_path / "IMG_8202.JPG"
    _write_image(first)
    _write_image(second)

    widget: CentralWidget = CentralWidget()
    widget.resize(1200, 700)
    qtbot.addWidget(widget)
    widget.canvas.directory = str(tmp_path)
    widget.canvas.points = {first.name: {}, second.name: {}}
    widget.canvas.load_image(str(first))
    widget.set_compare_enabled(True)
    widget.show()

    assert widget.start_landmark_point() is True
    qtbot.mouseClick(
        widget.graphicsView.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        pos=QtCore.QPoint(30, 30),
    )
    assert widget.graphicsView.interaction_mode.value == "count"

    assert widget.start_landmark_point() is True
    qtbot.mouseClick(
        widget.reference_graphics_view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        pos=QtCore.QPoint(35, 35),
    )
    assert widget.reference_graphics_view.interaction_mode.value == "count"

    assert widget.start_cutline() is True
    qtbot.mouseClick(
        widget.graphicsView.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        pos=QtCore.QPoint(20, 20),
    )
    widget.graphicsView.line_points.append(QtCore.QPointF(15.0, 15.0))
    qtbot.mouseDClick(
        widget.graphicsView.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        pos=QtCore.QPoint(40, 40),
    )
    assert widget.graphicsView.interaction_mode.value == "count"

    assert widget.start_cutline() is True
    qtbot.mouseClick(
        widget.reference_graphics_view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        pos=QtCore.QPoint(25, 25),
    )
    assert widget.reference_graphics_view.interaction_mode.value == "line"
    assert len(widget.reference_graphics_view.line_points) == 1
    widget.reference_graphics_view.cancel_annotation()

    assert widget.start_count_region_polygon() is True
    qtbot.mouseClick(
        widget.graphicsView.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        pos=QtCore.QPoint(20, 20),
    )
    widget.graphicsView.polygon_points.extend(
        [QtCore.QPointF(20.0, 5.0), QtCore.QPointF(20.0, 20.0)]
    )
    qtbot.mouseDClick(
        widget.graphicsView.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        pos=QtCore.QPoint(40, 40),
    )
    assert widget.graphicsView.interaction_mode.value == "count"

    assert widget.start_count_region_polygon() is True
    qtbot.mouseClick(
        widget.reference_graphics_view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        pos=QtCore.QPoint(25, 25),
    )
    assert widget.reference_graphics_view.interaction_mode.value == "polygon"
    assert len(widget.reference_graphics_view.polygon_points) == 1


def test_global_history_interleaves_current_point_and_reference_annotation(
    qtbot: Any, tmp_path: Path
) -> None:
    """Global undo should interleave Current count and Reference annotation edits."""
    first: Path = tmp_path / "IMG_8301.JPG"
    second: Path = tmp_path / "IMG_8302.JPG"
    _write_image(first)
    _write_image(second)

    widget: CentralWidget = CentralWidget()
    qtbot.addWidget(widget)
    widget.canvas.directory = str(tmp_path)
    widget.canvas.points = {first.name: {}, second.name: {}}
    widget.canvas.colors = {"TEST": QtGui.QColor(QtCore.Qt.GlobalColor.red)}
    widget.canvas.classes = ["TEST"]
    widget.canvas.current_class_name = "TEST"
    widget.canvas.load_image(str(first))
    widget.set_compare_enabled(True)

    count_point: QtCore.QPointF = QtCore.QPointF(10.0, 10.0)
    widget.canvas.add_point(count_point)
    widget.reference_canvas.add_landmark_annotation(QtCore.QPointF(20.0, 20.0))
    second_sidecar: Path = second.with_suffix(".json")
    assert second_sidecar.exists()
    assert widget.canvas.points[first.name]["TEST"] == [count_point]

    widget.undo_global_history()
    assert not second_sidecar.exists()
    assert widget.canvas.points[first.name]["TEST"] == [count_point]

    widget.undo_global_history()
    assert widget.canvas.points[first.name]["TEST"] == []

    widget.redo_global_history()
    assert widget.canvas.points[first.name]["TEST"] == [count_point]
    widget.redo_global_history()
    assert second_sidecar.exists()


def test_failed_global_history_operation_preserves_chronology(
    qtbot: Any, monkeypatch: Any
) -> None:
    """Failed persistence must not skip to an older cross-pane history event."""
    widget: CentralWidget = CentralWidget()
    qtbot.addWidget(widget)

    widget._global_undo_order = [widget.canvas]
    undo_mock: Mock = Mock(return_value=False)
    monkeypatch.setattr(widget.canvas, "undo", undo_mock)
    widget.undo_global_history()
    assert widget._global_undo_order == [widget.canvas]

    widget._global_redo_order = [widget.reference_canvas]
    redo_mock: Mock = Mock(return_value=False)
    monkeypatch.setattr(widget.reference_canvas, "redo", redo_mock)
    widget.redo_global_history()
    assert widget._global_redo_order == [widget.reference_canvas]

def test_escape_cancels_unclaimed_compare_drawing_tool(
    qtbot: Any, tmp_path: Path
) -> None:
    """Escape should disarm a drawing tool before any pane claims it."""
    first: Path = tmp_path / "IMG_8401.JPG"
    second: Path = tmp_path / "IMG_8402.JPG"
    _write_image(first)
    _write_image(second)

    widget: CentralWidget = CentralWidget()
    qtbot.addWidget(widget)
    widget.canvas.directory = str(tmp_path)
    widget.canvas.points = {first.name: {}, second.name: {}}
    widget.canvas.load_image(str(first))
    widget.set_compare_enabled(True)

    assert widget.start_cutline() is True
    assert widget._pending_compare_annotation_mode is not None
    qtbot.keyClick(widget.graphicsView, QtCore.Qt.Key.Key_Escape)

    assert widget._pending_compare_annotation_mode is None
    assert widget.graphicsView.interaction_mode.value == "count"
    assert widget.reference_graphics_view.interaction_mode.value == "count"


def test_navigation_does_not_claim_an_armed_compare_drawing_tool(
    qtbot: Any, tmp_path: Path
) -> None:
    """C+drag should navigate without choosing the pending drawing pane."""
    first: Path = tmp_path / "IMG_8501.JPG"
    second: Path = tmp_path / "IMG_8502.JPG"
    _write_image(first)
    _write_image(second)

    widget: CentralWidget = CentralWidget()
    widget.resize(1200, 700)
    qtbot.addWidget(widget)
    widget.canvas.directory = str(tmp_path)
    widget.canvas.points = {first.name: {}, second.name: {}}
    widget.canvas.load_image(str(first))
    widget.set_compare_enabled(True)
    widget.show()

    assert widget.start_cutline() is True
    pending_mode: object = widget._pending_compare_annotation_mode
    assert pending_mode is not None

    qtbot.keyPress(widget.reference_graphics_view, QtCore.Qt.Key.Key_C)
    qtbot.mousePress(
        widget.reference_graphics_view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        pos=QtCore.QPoint(40, 40),
    )
    qtbot.mouseRelease(
        widget.reference_graphics_view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        pos=QtCore.QPoint(60, 60),
    )
    qtbot.keyRelease(widget.reference_graphics_view, QtCore.Qt.Key.Key_C)

    assert widget._pending_compare_annotation_mode is pending_mode
    assert widget.reference_graphics_view.interaction_mode.value == "count"

    qtbot.mouseClick(
        widget.reference_graphics_view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        pos=QtCore.QPoint(30, 30),
    )
    assert widget._pending_compare_annotation_mode is None
    assert widget.reference_graphics_view.interaction_mode.value == "line"
    assert len(widget.reference_graphics_view.line_points) == 1
