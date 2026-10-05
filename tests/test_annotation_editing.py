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
