"""Tests for operational count-region behavior in the DDG canvas."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import numpy as np
from PyQt6 import QtCore

from ddg import Canvas
from ddg.annotations import Annotation, AnnotationShape


def test_whole_image_count_region_replaces_only_count_regions(
    qtbot, tmp_path: Path
) -> None:
    """Whole-image mode should preserve unrelated annotations and metadata."""
    image_path: Path = tmp_path / "IMG_7000.JPG"
    image_path.write_bytes(b"")
    raw_data: dict[str, Any] = {
        "customMetadata": "keep",
        "shapes": [
            {
                "label": "landmark",
                "points": [[10, 20]],
                "group_id": None,
                "shape_type": "point",
                "flags": {},
            },
            {
                "label": "count_region",
                "points": [[0, 0], [20, 0], [20, 20]],
                "group_id": None,
                "shape_type": "polygon",
                "flags": {},
            },
        ],
    }
    image_path.with_suffix(".json").write_text(
        json.dumps(raw_data), encoding="utf-8"
    )
    canvas: Canvas = Canvas()
    canvas.directory = str(tmp_path)
    canvas.current_image_name = image_path.name
    canvas.image_cache["data"] = np.zeros((100, 200, 3), dtype=np.uint8)
    canvas.display_external_annotations(str(image_path))

    saved: bool = canvas.set_whole_image_count_region()

    assert saved is True
    updated: dict[str, object] = json.loads(
        image_path.with_suffix(".json").read_text(encoding="utf-8")
    )
    shapes = cast(list[dict[str, object]], updated["shapes"])
    assert [shape["label"] for shape in shapes] == ["landmark", "count_region"]
    assert shapes[1]["points"] == [
        [0.0, 0.0],
        [200.0, 0.0],
        [200.0, 100.0],
        [0.0, 100.0],
    ]
    assert updated["customMetadata"] == "keep"


def test_count_region_qa_reports_inside_and_outside_by_class(qtbot) -> None:
    """QA should classify bird points against the union of count regions."""
    canvas: Canvas = Canvas()
    canvas.current_image_name = "IMG_7001.JPG"
    canvas.external_annotations = [
        Annotation(
            label="count_region",
            shape_type=AnnotationShape.POLYGON,
            points=[(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)],
        )
    ]
    canvas.points = {
        "IMG_7001.JPG": {
            "COMU": [QtCore.QPointF(10.0, 10.0), QtCore.QPointF(150.0, 10.0)],
            "WEGU": [QtCore.QPointF(50.0, 50.0)],
        }
    }

    qa: dict[str, object] = canvas.count_region_qa()

    assert qa["has_regions"] is True
    assert qa["inside"] == 2
    assert qa["outside"] == 1
    by_class = cast(dict[str, dict[str, int]], qa["by_class"])
    assert by_class["COMU"] == {"inside": 1, "outside": 1}
    assert by_class["WEGU"] == {"inside": 1, "outside": 0}


def test_count_region_qa_reports_missing_region(qtbot) -> None:
    """QA should distinguish no explicit count region from zero bird points."""
    canvas: Canvas = Canvas()
    canvas.current_image_name = "IMG_7002.JPG"
    canvas.points = {"IMG_7002.JPG": {"COMU": [QtCore.QPointF(10.0, 10.0)]}}

    qa: dict[str, object] = canvas.count_region_qa()

    assert qa["has_regions"] is False
    assert qa["inside"] == 0
    assert qa["outside"] == 0


def test_refresh_count_region_mask_creates_noninteractive_overlay(
    qtbot, monkeypatch
) -> None:
    """Dimming should create a mask above imagery but below DDG annotations."""
    canvas: Canvas = Canvas()
    canvas.image_cache["data"] = np.zeros((100, 200, 3), dtype=np.uint8)
    canvas.external_annotations = [
        Annotation(
            label="count_region",
            shape_type=AnnotationShape.POLYGON,
            points=[(20.0, 20.0), (180.0, 20.0), (180.0, 80.0), (20.0, 80.0)],
        )
    ]
    monkeypatch.setattr(canvas, "dim_outside_count_region_enabled", lambda: True)

    canvas.refresh_count_region_mask()

    assert canvas.count_region_mask_item is not None
    assert canvas.count_region_mask_item.zValue() == -5.0
    assert (
        canvas.count_region_mask_item.acceptedMouseButtons()
        == QtCore.Qt.MouseButton.NoButton
    )
