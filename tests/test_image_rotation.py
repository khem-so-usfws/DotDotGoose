"""Quarter-turn view rotation and coordinate regression coverage."""

from pathlib import Path
from typing import Any

from PIL import Image
from PyQt6 import QtCore, QtGui

from ddg.central_widget import CentralWidget


def test_rotation_controls_and_point_coordinates(qtbot: Any, tmp_path: Path) -> None:
    """Each quarter turn preserves click coordinates, selection, and view independence."""
    widget: CentralWidget = CentralWidget()
    qtbot.addWidget(widget)
    widget.resize(1400, 900)
    widget.show()
    for name in ("a.png", "b.png"):
        Image.new("RGB", (600, 400), "navy").save(tmp_path / name)
    widget.canvas.directory = str(tmp_path)
    widget.canvas.points = {"a.png": {}, "b.png": {}}
    widget.canvas.classes = ["Bird"]
    widget.canvas.colors = {"Bird": QtGui.QColor("red")}
    widget.canvas.set_current_class(0)
    widget.canvas.load_image(str(tmp_path / "a.png"))
    widget.set_compare_enabled(True)
    for pane, canvas in (
        (widget.current_pane, widget.canvas),
        (widget.compare_pane, widget.reference_canvas),
    ):
        widget.workspace_feedback.cancel_transfer()
        view: Any = pane.graphics_view
        view.set_navigator_enabled(True)
        for angle in (90, 180, 270, 0):
            pane.rotate_right_button.click()
            assert view.rotation_degrees == angle
            pane.fit_button.click()
            qtbot.wait(10)
            source_point: QtCore.QPointF = QtCore.QPointF(300, 200)
            position: QtCore.QPoint = view.mapFromScene(source_point)
            mapped: QtCore.QPointF = view.mapToScene(position)
            qtbot.mouseClick(
                view.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=position
            )
            point: QtCore.QPointF = canvas.points[canvas.current_image_name]["Bird"][-1]
            assert QtCore.QLineF(point, mapped).length() < 0.01
            canvas.select_points(QtCore.QRectF(290, 190, 20, 20))
            assert canvas.selection
            canvas.delete_selected_points()
            assert canvas.points[canvas.current_image_name]["Bird"] == []
            assert view.navigator_rect().contains(view.navigator_extent())
            assert not view.viewport().grab().isNull()
            pane.actual_size_button.click()
            assert abs(view.transform().determinant() - 1) < 0.0001
            assert view.rotation_degrees == angle
        pane.rotate_right_button.click()
        pane.fit_button.click()
        qtbot.wait(10)
        view.start_line_annotation()
        expected: list[QtCore.QPointF] = []
        for vertex in (QtCore.QPointF(250, 180), QtCore.QPointF(350, 220)):
            position = view.mapFromScene(vertex)
            expected.append(view.mapToScene(position))
            qtbot.mouseClick(
                view.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=position
            )
        view.finish_line_annotation()
        assert canvas.external_annotations
        assert canvas.external_annotations[-1].points == [
            (point.x(), point.y()) for point in expected
        ]
        pane.rotate_left_button.click()
        pane.rotate_left_button.click()
        assert view.rotation_degrees == 270
        pane.fit_button.click()
    assert widget.graphicsView.rotation_degrees == 270
    assert widget.reference_graphics_view.rotation_degrees == 270
    widget.current_pane.rotate_right_button.click()
    assert widget.reference_graphics_view.rotation_degrees == 270
    widget.canvas.load_image(str(tmp_path / "a.png"))
    assert widget.graphicsView.rotation_degrees == 0


def test_rotated_navigator_extent(qtbot: Any) -> None:
    """A source rectangle maps to the expected quarter-turned inset rectangle."""
    from ddg.central_graphics_view import CentralGraphicsView

    view: CentralGraphicsView = CentralGraphicsView()
    qtbot.addWidget(view)
    view.navigator_source_size = QtCore.QSize(600, 400)
    view.rotation_degrees = 90
    view.resize(500, 400)
    rect: QtCore.QRectF = view.navigator_rect()
    assert abs(rect.width() / rect.height() - 400 / 600) < 0.02
