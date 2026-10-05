"""Tests for native annotation selection and geometry editing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from PyQt6 import QtCore

from ddg import Canvas
from ddg.annotations import AnnotationShape


def _write_polygon_sidecar(image_path: Path) -> None:
    """Write one editable polygon sidecar for a test image.

    Args:
        image_path: Image path whose sibling JSON should be created.
    """
    raw_data: dict[str, Any] = {
        "shapes": [
            {
                "label": "count_region",
                "points": [[10, 10], [50, 10], [50, 50]],
                "group_id": None,
                "shape_type": "polygon",
                "flags": {},
            }
        ]
    }
    image_path.with_suffix(".json").write_text(
        json.dumps(raw_data), encoding="utf-8"
    )


def test_vertex_move_updates_labelme_geometry(qtbot, tmp_path: Path) -> None:
    """Finishing a vertex drag should persist new source-image coordinates."""
    image_path: Path = tmp_path / "IMG_5000.JPG"
    image_path.write_bytes(b"")
    _write_polygon_sidecar(image_path)
    canvas: Canvas = Canvas()
    canvas.directory = str(tmp_path)
    canvas.current_image_name = image_path.name
    canvas.display_external_annotations(str(image_path))

    canvas.select_external_annotation(0)
    canvas.move_external_annotation_vertex(0, 1, QtCore.QPointF(75.0, 25.0))
    canvas.finish_external_annotation_vertex_move(0, 1)

    raw_data: dict[str, object] = json.loads(
        image_path.with_suffix(".json").read_text(encoding="utf-8")
    )
    shapes: list[dict[str, object]] = cast(
        list[dict[str, object]], raw_data["shapes"]
    )
    assert shapes[0]["points"] == [[10.0, 10.0], [75.0, 25.0], [50.0, 50.0]]
    assert canvas.external_annotations[0].shape_type is AnnotationShape.POLYGON
    assert canvas.selected_external_annotation_index == 0


def test_delete_selected_annotation_updates_sidecar(qtbot, tmp_path: Path) -> None:
    """Deleting a selected native annotation should remove its LabelMe shape."""
    image_path: Path = tmp_path / "IMG_5001.JPG"
    image_path.write_bytes(b"")
    _write_polygon_sidecar(image_path)
    canvas: Canvas = Canvas()
    canvas.directory = str(tmp_path)
    canvas.current_image_name = image_path.name
    canvas.display_external_annotations(str(image_path))
    canvas.select_external_annotation(0)

    deleted: bool = canvas.delete_selected_external_annotation()

    assert deleted is True
    raw_data: dict[str, object] = json.loads(
        image_path.with_suffix(".json").read_text(encoding="utf-8")
    )
    shapes: list[object] = cast(list[object], raw_data["shapes"])
    assert shapes == []
    assert canvas.external_annotations == []
    assert canvas.selected_external_annotation_index is None


def _write_four_vertex_polygon_sidecar(image_path: Path) -> None:
    """Write a four-vertex polygon suitable for vertex deletion tests.

    Args:
        image_path: Image path whose sibling JSON should be created.
    """
    raw_data: dict[str, Any] = {
        "shapes": [
            {
                "label": "count_region",
                "points": [[10, 10], [50, 10], [50, 50], [10, 50]],
                "group_id": None,
                "shape_type": "polygon",
                "flags": {},
            }
        ]
    }
    image_path.with_suffix(".json").write_text(
        json.dumps(raw_data), encoding="utf-8"
    )


def test_whole_annotation_move_updates_labelme_geometry(qtbot, tmp_path: Path) -> None:
    """Dragging an annotation body should translate every stored vertex."""
    image_path: Path = tmp_path / "IMG_5002.JPG"
    image_path.write_bytes(b"")
    _write_polygon_sidecar(image_path)
    canvas: Canvas = Canvas()
    canvas.directory = str(tmp_path)
    canvas.current_image_name = image_path.name
    canvas.display_external_annotations(str(image_path))

    canvas.select_external_annotation(0)
    canvas.move_external_annotation(0, QtCore.QPointF(5.0, 10.0))
    canvas.finish_external_annotation_move(0)

    raw_data: dict[str, object] = json.loads(
        image_path.with_suffix(".json").read_text(encoding="utf-8")
    )
    shapes: list[dict[str, object]] = cast(
        list[dict[str, object]], raw_data["shapes"]
    )
    assert shapes[0]["points"] == [
        [15.0, 20.0],
        [55.0, 20.0],
        [55.0, 60.0],
    ]


def test_insert_vertex_projects_to_nearest_polygon_edge(qtbot, tmp_path: Path) -> None:
    """Inserted vertices should land on the nearest existing edge."""
    image_path: Path = tmp_path / "IMG_5003.JPG"
    image_path.write_bytes(b"")
    _write_polygon_sidecar(image_path)
    canvas: Canvas = Canvas()
    canvas.directory = str(tmp_path)
    canvas.current_image_name = image_path.name
    canvas.display_external_annotations(str(image_path))

    inserted: bool = canvas.insert_external_annotation_vertex(
        0, QtCore.QPointF(30.0, 14.0)
    )

    assert inserted is True
    raw_data: dict[str, object] = json.loads(
        image_path.with_suffix(".json").read_text(encoding="utf-8")
    )
    shapes: list[dict[str, object]] = cast(
        list[dict[str, object]], raw_data["shapes"]
    )
    assert shapes[0]["points"] == [
        [10.0, 10.0],
        [30.0, 10.0],
        [50.0, 10.0],
        [50.0, 50.0],
    ]


def test_delete_vertex_preserves_valid_polygon(qtbot, tmp_path: Path) -> None:
    """A polygon vertex may be deleted while at least three remain."""
    image_path: Path = tmp_path / "IMG_5004.JPG"
    image_path.write_bytes(b"")
    _write_four_vertex_polygon_sidecar(image_path)
    canvas: Canvas = Canvas()
    canvas.directory = str(tmp_path)
    canvas.current_image_name = image_path.name
    canvas.display_external_annotations(str(image_path))

    deleted: bool = canvas.delete_external_annotation_vertex(0, 1)

    assert deleted is True
    raw_data: dict[str, object] = json.loads(
        image_path.with_suffix(".json").read_text(encoding="utf-8")
    )
    shapes: list[dict[str, object]] = cast(
        list[dict[str, object]], raw_data["shapes"]
    )
    assert shapes[0]["points"] == [
        [10.0, 10.0],
        [50.0, 50.0],
        [10.0, 50.0],
    ]


def test_delete_vertex_refuses_invalid_polygon(qtbot, tmp_path: Path) -> None:
    """A triangle must retain all three vertices."""
    image_path: Path = tmp_path / "IMG_5005.JPG"
    image_path.write_bytes(b"")
    _write_polygon_sidecar(image_path)
    canvas: Canvas = Canvas()
    canvas.directory = str(tmp_path)
    canvas.current_image_name = image_path.name
    canvas.display_external_annotations(str(image_path))

    deleted: bool = canvas.delete_external_annotation_vertex(0, 1)

    assert deleted is False
    assert canvas.external_annotations[0].points == [
        (10.0, 10.0),
        (50.0, 10.0),
        (50.0, 50.0),
    ]


def test_annotation_edit_undo_and_redo_restore_sidecar(qtbot, tmp_path: Path) -> None:
    """DDG's existing undo/redo shortcuts should restore annotation documents."""
    image_path: Path = tmp_path / "IMG_5006.JPG"
    image_path.write_bytes(b"")
    _write_polygon_sidecar(image_path)
    canvas: Canvas = Canvas()
    canvas.directory = str(tmp_path)
    canvas.current_image_name = image_path.name
    canvas.display_external_annotations(str(image_path))

    canvas.move_external_annotation(0, QtCore.QPointF(10.0, 0.0))
    canvas.finish_external_annotation_move(0)
    assert canvas.external_annotations[0].points[0] == (20.0, 10.0)

    canvas.undo()
    assert canvas.external_annotations[0].points[0] == (10.0, 10.0)

    canvas.redo()
    assert canvas.external_annotations[0].points[0] == (20.0, 10.0)


def test_annotation_creation_can_be_undone_and_redone(qtbot, tmp_path: Path) -> None:
    """Creating the first sidecar annotation should be reversible."""
    image_path: Path = tmp_path / "IMG_5007.JPG"
    image_path.write_bytes(b"")
    canvas: Canvas = Canvas()
    canvas.directory = str(tmp_path)
    canvas.current_image_name = image_path.name

    canvas.add_landmark_annotation(QtCore.QPointF(12.0, 34.0))
    assert image_path.with_suffix(".json").exists()

    canvas.undo()
    assert not image_path.with_suffix(".json").exists()
    assert canvas.external_annotations == []

    canvas.redo()
    assert image_path.with_suffix(".json").exists()
    assert len(canvas.external_annotations) == 1
    assert canvas.external_annotations[0].points == [(12.0, 34.0)]


def test_locked_annotation_refuses_geometry_edit(qtbot, tmp_path: Path) -> None:
    """Locked annotations should not move or delete until explicitly unlocked."""
    image_path: Path = tmp_path / "IMG_5008.JPG"
    image_path.write_bytes(b"")
    raw_data: dict[str, Any] = {
        "shapes": [
            {
                "label": "count_region",
                "points": [[10, 10], [50, 10], [50, 50]],
                "group_id": None,
                "shape_type": "polygon",
                "flags": {"ddg_locked": True},
            }
        ]
    }
    image_path.with_suffix(".json").write_text(
        json.dumps(raw_data), encoding="utf-8"
    )
    canvas: Canvas = Canvas()
    canvas.directory = str(tmp_path)
    canvas.current_image_name = image_path.name
    canvas.display_external_annotations(str(image_path))
    canvas.select_external_annotation(0)

    canvas.move_external_annotation(0, QtCore.QPointF(10.0, 0.0))
    deleted: bool = canvas.delete_selected_external_annotation()

    assert canvas.external_annotations[0].points[0] == (10.0, 10.0)
    assert deleted is False
    assert canvas.external_annotation_handle_items == []


def test_annotation_properties_persist_label_and_lock(qtbot, tmp_path: Path) -> None:
    """Changing annotation properties should update the same LabelMe shape."""
    image_path: Path = tmp_path / "IMG_5009.JPG"
    image_path.write_bytes(b"")
    _write_polygon_sidecar(image_path)
    canvas: Canvas = Canvas()
    canvas.directory = str(tmp_path)
    canvas.current_image_name = image_path.name
    canvas.display_external_annotations(str(image_path))
    canvas.select_external_annotation(0)

    updated: bool = canvas.update_selected_external_annotation_properties(
        "review_boundary", True
    )

    assert updated is True
    raw_data: dict[str, object] = json.loads(
        image_path.with_suffix(".json").read_text(encoding="utf-8")
    )
    shapes: list[dict[str, object]] = cast(
        list[dict[str, object]], raw_data["shapes"]
    )
    assert shapes[0]["label"] == "review_boundary"
    flags: dict[str, object] = cast(dict[str, object], shapes[0]["flags"])
    assert flags["ddg_locked"] is True
    assert canvas.external_annotations[0].locked is True
