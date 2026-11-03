"""Dual-pane navigation and display-setting regressions."""

from pathlib import Path
from typing import Any

from PIL import Image
from PyQt6 import QtCore, QtGui, QtWidgets

from ddg.central_widget import CentralWidget


def test_dual_controls_and_display(qtbot: Any, tmp_path: Path) -> None:
    """Navigation stays independent while display changes preserve selection."""
    widget: CentralWidget = CentralWidget()
    qtbot.addWidget(widget)
    for name in ("a.png", "b.png", "c.png"):
        Image.new("RGB", (600, 400)).save(tmp_path / name)
    widget.canvas.directory = str(tmp_path)
    widget.canvas.points = {
        name: {"Bird": [QtCore.QPointF(50, 50)]} for name in ("a.png", "b.png", "c.png")
    }
    widget.canvas.classes = ["Bird"]
    widget.canvas.colors = {"Bird": QtGui.QColor("red")}
    widget.canvas.set_current_class(0)
    widget.canvas.load_image(str(tmp_path / "a.png"))
    widget.set_compare_enabled(True)
    widget.current_pane.image_combo.setCurrentText("c.png")
    assert widget.canvas.current_image_name == "c.png"
    assert widget.reference_canvas.current_image_name == "b.png"
    widget.reference_graphics_view.scale(2, 2)
    reference_transform: QtGui.QTransform = widget.reference_graphics_view.transform()
    widget.current_pane.actual_size_button.click()
    assert widget.graphicsView.transform().m11() == 1
    assert widget.reference_graphics_view.transform() == reference_transform
    widget.current_pane.previous_button.click()
    assert widget.canvas.current_image_name == "b.png"
    assert widget.reference_canvas.current_image_name == "c.png"
    widget.compare_pane.previous_button.click()
    assert widget.canvas.current_image_name == "b.png"
    assert widget.reference_canvas.current_image_name == "a.png"
    for canvas in (widget.canvas, widget.reference_canvas):
        canvas.select_points(QtCore.QRectF(0, 0, 100, 100))
    widget.canvas.set_grid_size(50)
    widget.canvas.set_grid_color(QtGui.QColor("cyan"))
    widget.canvas.toggle_grid(True)
    widget.canvas.set_point_radius(40)
    for canvas in (widget.canvas, widget.reference_canvas):
        assert len(canvas.selection) == 1
        assert canvas.ui["point"]["radius"] == 40
        assert canvas.ui["grid"]["size"] == 50
        lines: list[Any] = [
            item
            for item in canvas.items()
            if isinstance(item, QtWidgets.QGraphicsLineItem)
        ]
        assert lines
        assert all(item.pen().color().name() == "#00ffff" for item in lines)
        assert (
            sum(item.data(0) == "ddg_selected_bird_point" for item in canvas.items())
            == 2
        )
    widget.canvas.toggle_points(False)
    widget.canvas.toggle_grid(False)
    for canvas in (widget.canvas, widget.reference_canvas):
        assert len(canvas.selection) == 1
        assert not any(
            item.data(0) in {"ddg_bird_point", "ddg_selected_bird_point"}
            for item in canvas.items()
        )
        assert not any(
            isinstance(item, QtWidgets.QGraphicsLineItem) for item in canvas.items()
        )
    widget.canvas.toggle_points(True)
    widget.reference_canvas.delete_selected_points()
    assert widget.canvas.points["a.png"]["Bird"] == []
    widget.undo_global_history()
    assert len(widget.canvas.points["a.png"]["Bird"]) == 1
    widget.set_compare_enabled(False)
    widget.current_pane.next_button.click()
    assert widget.canvas.current_image_name == "c.png"
    (tmp_path / "a.png").unlink()
    widget.refresh_compare_images()
    assert widget.current_pane.image_combo.findText("a.png") == -1
    widget.load_current_image("missing.png")
    assert widget.canvas.current_image_name == "c.png"
