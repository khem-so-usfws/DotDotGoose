"""Selection markers remain legible at overview zoom."""

from typing import Any

from PyQt6 import QtCore, QtGui, QtWidgets

from ddg.canvas import Canvas


def test_selection_markers(qtbot: Any) -> None:
    """Selection uses fixed-size contrasting outlines and cleans up on delete."""
    canvas: Canvas = Canvas()
    view: QtWidgets.QGraphicsView = QtWidgets.QGraphicsView(canvas)
    qtbot.addWidget(view)
    canvas.current_image_name = "image.png"
    canvas.current_class_name = "Bird"
    canvas.classes = ["Bird"]
    canvas.colors = {"Bird": QtGui.QColor("red")}
    canvas.points = {"image.png": {"Bird": [QtCore.QPointF(30, 40)]}}
    canvas.select_points(QtCore.QRectF(0, 0, 100, 100))
    markers: list[Any] = [
        item for item in canvas.items() if item.data(0) == "ddg_selected_bird_point"
    ]
    assert len(markers) == 2
    assert {item.pen().color().name() for item in markers} == {"#000000", "#ffff00"}
    for scale in (0.05, 1.0, 5.0):
        view.resetTransform()
        view.scale(scale, scale)
        for item in markers:
            bounds: QtCore.QRectF = item.deviceTransform(
                view.viewportTransform()
            ).mapRect(item.rect())
            assert abs(bounds.width() - 24) < 0.01
            assert item.acceptedMouseButtons() == QtCore.Qt.MouseButton.NoButton
    canvas.delete_selected_points()
    assert canvas.points["image.png"]["Bird"] == []
    assert not any(item.data(0) == "ddg_selected_bird_point" for item in canvas.items())
