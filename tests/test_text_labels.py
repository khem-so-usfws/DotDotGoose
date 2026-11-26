"""Cover native text label placement, editing, and sidecar compatibility."""

import json
from pathlib import Path
from typing import Any, cast

import pytest
from PyQt6 import QtCore, QtGui, QtWidgets
from pytestqt.qtbot import QtBot

from ddg.annotation_properties_dialog import AnnotationPropertiesDialog
from ddg.annotations import Annotation, AnnotationShape, LabelMeDocument
from ddg.annotations import load_labelme_document, update_labelme_annotation
from ddg.canvas import Canvas
from ddg.central_graphics_view import CentralGraphicsView, InteractionMode
from ddg.central_widget import CentralWidget
from ddg.image_workspace import ImageWorkspace
from ddg.main_window import MainWindow
from ddg.selection_editor import SelectionEditor
from test_workspace_controls import window  # noqa: F401


def test_text_label_in_floating_pane(
    window: MainWindow,
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Place and edit a caption in a rotated floating pane and undo changes.

    Args:
        window: Initialized counting workspace.
        qtbot: Qt interaction fixture.
        tmp_path: Project image directory.
        monkeypatch: Text prompt substitution fixture.
    """
    widget: CentralWidget = cast(CentralWidget, window.centralWidget())
    workspace: ImageWorkspace | None = widget.image_workspace
    assert workspace is not None
    workspace.set_count(3)
    workspace.float_actions["pane3"].trigger()
    widget.load_pane_image("pane3", "a.png")
    canvas: Canvas = widget.image_panes["pane3"][1]
    view: CentralGraphicsView = widget.image_panes["pane3"][0].graphics_view
    view.rotate_view(True)
    assert workspace.docks["pane3"].isFloating()
    action: QtGui.QAction = window.workspace_controls.actions[
        InteractionMode.TEXT_LABEL
    ]
    action.trigger()
    assert action.isChecked()
    assert view.interaction_mode is InteractionMode.TEXT_LABEL
    anchor: QtCore.QPoint = view.viewport().rect().center()
    pixel: QtCore.QPointF = view.mapToScene(anchor)
    sidecar: Path = tmp_path / "a.json"
    monkeypatch.setattr(QtWidgets.QInputDialog, "getText", lambda *_: ("", False))
    qtbot.mouseClick(view.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=anchor)
    assert not sidecar.exists()
    monkeypatch.setattr(QtWidgets.QInputDialog, "getText", lambda *_: ("   ", True))
    qtbot.mouseClick(view.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=anchor)
    assert not sidecar.exists()
    caption: str = "Start count \N{RIGHTWARDS ARROW} north"
    monkeypatch.setattr(QtWidgets.QInputDialog, "getText", lambda *_: (caption, True))
    qtbot.mouseClick(view.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=anchor)
    assert widget.canvas.points["a.png"] == {}
    assert view.interaction_mode is InteractionMode.TEXT_LABEL
    assert canvas.external_annotations[0].points == [(pixel.x(), pixel.y())]
    assert widget.canvas.external_annotations[0].description == caption
    item: QtWidgets.QGraphicsItem = canvas.external_annotation_items[0]
    original: QtCore.QRectF = item.deviceTransform(view.viewportTransform()).mapRect(
        item.boundingRect()
    )
    view.scale(2, 2)
    view.centerOn(pixel)
    bounds: QtCore.QRectF = item.deviceTransform(view.viewportTransform()).mapRect(
        item.boundingRect()
    )
    assert bounds.size() == original.size()

    # Select the rendered text away from its point anchor, then edit its caption.
    window.workspace_controls.select_tool(InteractionMode.SELECT)
    text_position: QtCore.QPoint = bounds.center().toPoint()
    qtbot.mouseClick(
        view.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=text_position
    )
    assert canvas.selected_annotation_indices == {0}

    def edit_dialog(dialog: AnnotationPropertiesDialog) -> int:
        """Enter a replacement caption through the annotation properties field.

        Args:
            dialog: Properties editor for the selected label.

        Returns:
            Dialog result after saving the edited caption.
        """
        assert dialog.label_edit.text() == caption
        dialog.label_edit.selectAll()
        qtbot.keyClicks(dialog.label_edit, "North sector")
        dialog.accept()
        return dialog.result()

    monkeypatch.setattr(AnnotationPropertiesDialog, "exec", edit_dialog)
    window.workspace_controls.editors[view].properties()
    shape: dict[str, Any] = json.loads(sidecar.read_text(encoding="utf-8"))["shapes"][0]
    assert shape["shape_type"] == "point"
    assert shape["label"] == "text_label"
    assert shape["description"] == "North sector"
    assert widget.canvas.external_annotations[0].description == "North sector"

    # The regular selection editor moves and deletes the complete label.
    editor: SelectionEditor = window.workspace_controls.editors[view]
    assert editor.edit(offset=QtCore.QPointF(20, 10))
    assert canvas.external_annotations[0].points == [(pixel.x() + 20, pixel.y() + 10)]
    editor.delete_selection()
    assert canvas.external_annotations == widget.canvas.external_annotations == []
    widget.undo_global_history()
    assert canvas.external_annotations[0].description == "North sector"
    widget.undo_global_history()
    assert canvas.external_annotations[0].points == [(pixel.x(), pixel.y())]
    widget.undo_global_history()
    assert canvas.external_annotations[0].description == caption
    widget.redo_global_history()
    assert canvas.external_annotations[0].description == "North sector"


def test_text_labels_have_independent_visibility(window: MainWindow) -> None:
    """Keep landmarks and text labels independently visible across open panes.

    Args:
        window: Initialized workspace with two open images.
    """
    widget: CentralWidget = cast(CentralWidget, window.centralWidget())
    annotations_menu: QtWidgets.QMenu = next(
        menu
        for menu in window.menuBar().findChildren(QtWidgets.QMenu)
        if menu.title() == "Annotations"
    )
    actions: dict[str, QtGui.QAction] = {
        action.text(): action for action in annotations_menu.actions()
    }
    canvases: tuple[Canvas, Canvas] = (widget.canvas, widget.reference_canvas)
    for canvas in canvases:
        canvas.add_landmark_annotation(QtCore.QPointF(400, 300))
        canvas.add_text_label_annotation(QtCore.QPointF(600, 400), "Boundary")
        canvas.select_external_annotation(1)

    actions["Show Text Labels"].trigger()
    for canvas in canvases:
        assert {item.data(1) for item in canvas.external_annotation_items} == {0}
        assert canvas.selected_external_annotation() is None

    display: QtGui.QAction = window.workspace_controls.display_actions["Annotations"]
    display.trigger()
    assert all(not canvas.external_annotation_items for canvas in canvases)
    display.trigger()
    for canvas in canvases:
        assert {item.data(1) for item in canvas.external_annotation_items} == {0}

    actions["Show Point Annotations"].trigger()
    actions["Show Text Labels"].trigger()
    for canvas in canvases:
        assert {item.data(1) for item in canvas.external_annotation_items} == {1}


def test_labelme_description_round_trip(tmp_path: Path) -> None:
    """Round-trip Unicode text, ordinary descriptions, and unknown shape fields.

    Args:
        tmp_path: Directory for the fixture sidecar.
    """
    image: Path = tmp_path / "photo.jpg"
    sidecar: Path = image.with_suffix(".json")
    point: dict[str, Any] = {"shape_type": "point", "points": [[10, 20]], "flags": {}}
    caption: str = "Rep\N{LATIN SMALL LETTER E WITH GRAVE}re <Ouest>"
    sidecar.write_text(
        json.dumps(
            {
                "shapes": [
                    {**point, "label": "landmark", "description": "metadata"},
                    {**point, "label": "text_label", "description": caption, "id": 3},
                    {**point, "label": "text_label", "description": None},
                ],
            }
        ),
        encoding="utf-8",
    )
    document: LabelMeDocument | None = load_labelme_document(image)
    assert document is not None
    landmark: Annotation
    label: Annotation
    empty: Annotation
    landmark, label, empty = document.annotations
    assert not landmark.is_text_label
    assert label.is_text_label and label.shape_type is AnnotationShape.POINT
    assert label.description == caption
    assert empty.is_text_label and empty.description is None

    landmark.points = [(15, 25)]
    update_labelme_annotation(image, landmark)
    label.description = "Rep\N{LATIN SMALL LETTER E WITH GRAVE}re A"
    update_labelme_annotation(image, label)
    shapes: list[dict[str, Any]] = json.loads(sidecar.read_text(encoding="utf-8"))[
        "shapes"
    ]
    assert shapes[0]["description"] == "metadata"
    assert shapes[1]["description"] == label.description
    assert shapes[1]["id"] == 3
    assert shapes[2]["description"] is None
