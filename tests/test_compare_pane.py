"""Regression tests for the lightweight two-image comparison pane."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image
from PyQt6 import QtCore, QtWidgets

from ddg.central_graphics_view import CentralGraphicsView
from ddg.central_widget import CentralWidget


def _write_image(path: Path) -> None:
    """Write a tiny RGB image suitable for Canvas loading."""
    Image.new("RGB", (40, 30), (128, 128, 128)).save(path)


def test_reference_view_disables_count_point_placement(qtbot) -> None:
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


def test_compare_toggle_loads_one_reference_image(qtbot, tmp_path: Path) -> None:
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


def test_compare_supports_horizontal_and_vertical_layouts(qtbot) -> None:
    """The splitter should support both agreed two-image layouts."""
    widget: CentralWidget = CentralWidget()
    qtbot.addWidget(widget)

    widget.set_compare_layout("1x2")
    assert widget.compare_splitter.orientation() == QtCore.Qt.Orientation.Horizontal
    assert widget.compare_layout() == "1x2"

    widget.set_compare_layout("2x1")
    assert widget.compare_splitter.orientation() == QtCore.Qt.Orientation.Vertical
    assert widget.compare_layout() == "2x1"


def test_make_reference_current_swaps_images(qtbot, tmp_path: Path) -> None:
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


def test_hiding_compare_releases_reference_image_memory(qtbot, tmp_path: Path) -> None:
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

    widget.set_compare_enabled(False)

    assert widget.reference_canvas.current_image_name is None
    assert widget.reference_canvas.image_cache["data"] is None
    assert widget._last_reference_image_name == second.name

    widget.set_compare_enabled(True)
    assert widget.reference_canvas.current_image_name == second.name


def test_compare_splitter_can_shrink_either_image_pane(qtbot) -> None:
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


def test_annotation_target_is_last_clicked_not_last_focused(qtbot, tmp_path: Path) -> None:
    """Hover/focus changes must not retarget Reference annotation commands."""
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
    # Simulate the Current pane receiving focus while the pointer travels to
    # the application menu. Focus alone must not steal the annotation target.
    widget.graphicsView.view_focused.emit()

    assert widget.start_landmark_point() is True
    assert widget.reference_graphics_view.interaction_mode.value == "point"
    assert widget.graphicsView.interaction_mode.value == "count"


def test_reference_pane_can_create_native_annotation(qtbot, tmp_path: Path) -> None:
    """A clicked Reference pane must save native annotations from mouse input."""
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

    qtbot.mouseClick(
        widget.reference_graphics_view.viewport(),
        QtCore.Qt.MouseButton.LeftButton,
        pos=QtCore.QPoint(20, 20),
    )
    assert widget.start_landmark_point() is True
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
