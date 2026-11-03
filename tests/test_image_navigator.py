"""Image overview geometry and lifecycle regression tests."""

from pathlib import Path
from typing import Any

from PIL import Image
from PyQt6 import QtCore

from ddg.main_window import MainWindow


def test_navigators_follow_views(qtbot: Any, tmp_path: Path) -> None:
    """Both insets track their own views and clear when images are released."""
    window: MainWindow = MainWindow()
    qtbot.addWidget(window)
    window.resize(1400, 800)
    window.show()
    widget: Any = window.centralWidget()
    for name in ("a.png", "b.png"):
        Image.new("RGB", (1000, 600), "navy").save(tmp_path / name)
    widget.canvas.directory = str(tmp_path)
    widget.canvas.points = {"a.png": {}, "b.png": {}}
    widget.canvas.load_image(str(tmp_path / "a.png"))
    widget.set_compare_enabled(True)
    window.navigator_action.setChecked(True)
    qtbot.wait(20)
    for view in (widget.graphicsView, widget.reference_graphics_view):
        assert view.navigator_enabled
        assert not view.navigator_image.isNull()
        assert view.navigator_source_size == QtCore.QSize(1000, 600)
        assert view.navigator_rect().contains(view.navigator_extent())
        assert view.navigator_rect().bottom() == view.viewport().height() - 12
        assert view.navigator_rect().right() == view.viewport().width() - 12
        view.scale(4, 4)
        view.centerOn(500, 300)
        qtbot.wait(10)
        assert view.navigator_extent().width() < view.navigator_rect().width()
        before: QtCore.QRectF = view.navigator_extent()
        view.centerOn(700, 300)
        qtbot.wait(10)
        assert view.navigator_extent().x() > before.x()
        assert not view.viewport().grab().isNull()
    window.resize(1100, 650)
    qtbot.wait(10)
    assert (
        widget.graphicsView.navigator_rect().right()
        < widget.graphicsView.viewport().width()
    )
    widget.set_compare_enabled(False)
    assert widget.reference_graphics_view.navigator_image.isNull()
    widget.set_compare_enabled(True)
    assert not widget.reference_graphics_view.navigator_image.isNull()
    window.navigator_action.setChecked(False)
    assert not widget.graphicsView.navigator_enabled
    assert not widget.reference_graphics_view.navigator_enabled
