"""Regression coverage for shared dots and cross-pane history."""

from pathlib import Path
from typing import Any

from PIL import Image
from PyQt6 import QtCore, QtGui

from ddg.central_widget import CentralWidget


def test_reference_dots_and_history(qtbot: Any, tmp_path: Path) -> None:
    """Reference edits update shared counts and survive promotion and undo."""
    widget: CentralWidget = CentralWidget()
    qtbot.addWidget(widget)
    for name in ("a.png", "b.png"):
        Image.new("RGB", (100, 100)).save(tmp_path / name)
    widget.canvas.directory = str(tmp_path)
    widget.canvas.points = {"a.png": {}, "b.png": {}}
    widget.canvas.classes = ["Bird"]
    widget.canvas.colors = {"Bird": QtGui.QColor("red")}
    widget.canvas.set_current_class(0)
    widget.canvas.load_image(str(tmp_path / "a.png"))
    widget.set_compare_enabled(True)
    assert widget.reference_canvas.points is widget.canvas.points
    widget.reference_graphics_view.add_point.emit(QtCore.QPointF(20, 20))
    assert len(widget.canvas.points["b.png"]["Bird"]) == 1
    assert widget.canvas.dirty
    item: Any = widget.point_widget.model.findItems("b.png")[0]
    assert item.child(0, 1).text() == "1"
    widget.reference_canvas.select_points(QtCore.QRectF(10, 10, 20, 20))
    widget.reference_canvas.move_selected_points(QtCore.QPointF(5, 6))
    assert widget.canvas.points["b.png"]["Bird"][0] == QtCore.QPointF(25, 26)
    widget.undo_global_history()
    assert widget.canvas.points["b.png"]["Bird"][0] == QtCore.QPointF(20, 20)
    widget.redo_global_history()
    widget.make_reference_current()
    assert widget.canvas.current_image_name == "b.png"
    widget.undo_global_history()
    assert widget.canvas.points["b.png"]["Bird"][0] == QtCore.QPointF(20, 20)
    widget.undo_global_history()
    assert widget.canvas.points["b.png"]["Bird"] == []
    widget.redo_global_history()
    widget.canvas.select_points(QtCore.QRectF(10, 10, 20, 20))
    widget.canvas.delete_selected_points()
    assert widget.canvas.points["b.png"]["Bird"] == []
    widget.undo_global_history()
    assert len(widget.canvas.points["b.png"]["Bird"]) == 1
