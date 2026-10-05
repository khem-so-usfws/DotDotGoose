"""Tests for LabelMe annotation loading."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ddg.annotations import (
    AnnotationShape,
    LabelMeDocument,
    labelme_path_for_image,
    load_labelme_document,
)


def test_labelme_path_for_image_replaces_image_suffix(tmp_path: Path) -> None:
    """The LabelMe path should be adjacent to the image with a JSON suffix."""
    image_path: Path = tmp_path / "IMG_4103.JPG"
    assert labelme_path_for_image(image_path) == tmp_path / "IMG_4103.json"


def test_missing_sidecar_returns_none(tmp_path: Path) -> None:
    """Images without LabelMe sidecars should load without annotations."""
    image_path: Path = tmp_path / "IMG_4103.JPG"
    assert load_labelme_document(image_path) is None


def test_loads_supported_shapes_and_preserves_raw_document(tmp_path: Path) -> None:
    """Point, line, linestrip, and polygon shapes should load correctly."""
    image_path: Path = tmp_path / "IMG_4103.JPG"
    json_path: Path = tmp_path / "IMG_4103.json"
    raw_data: dict[str, Any] = {
        "version": "5.0.0",
        "flags": {"reviewed": True},
        "shapes": [
            {
                "label": "landmark",
                "points": [[10, 20]],
                "group_id": None,
                "shape_type": "point",
                "flags": {},
            },
            {
                "label": "cutline",
                "points": [[1, 2], [3, 4]],
                "group_id": 2,
                "shape_type": "line",
                "flags": {},
            },
            {
                "label": "cutline",
                "points": [[5, 6], [7, 8], [9, 10]],
                "group_id": None,
                "shape_type": "linestrip",
                "flags": {},
            },
            {
                "label": "count_region",
                "points": [[0, 0], [100, 0], [100, 100]],
                "group_id": None,
                "shape_type": "polygon",
                "flags": {"locked": False},
            },
            {
                "label": "box",
                "points": [[0, 0], [100, 100]],
                "group_id": None,
                "shape_type": "rectangle",
                "flags": {},
            },
        ],
        "imagePath": image_path.name,
        "customTopLevelField": "keep me",
    }
    json_path.write_text(json.dumps(raw_data), encoding="utf-8")

    document: LabelMeDocument | None = load_labelme_document(image_path)

    assert document is not None
    assert document.raw_data["customTopLevelField"] == "keep me"
    assert [annotation.shape_type for annotation in document.annotations] == [
        AnnotationShape.POINT,
        AnnotationShape.LINE,
        AnnotationShape.LINE,
        AnnotationShape.POLYGON,
    ]
    assert document.annotations[2].source_shape_type == "linestrip"
    assert len(document.warnings) == 1
    assert "rectangle" in document.warnings[0]


def test_invalid_supported_shape_is_skipped_with_warning(tmp_path: Path) -> None:
    """Malformed supported shapes should not prevent valid shapes from loading."""
    image_path: Path = tmp_path / "IMG_4103.JPG"
    json_path: Path = tmp_path / "IMG_4103.json"
    raw_data: dict[str, Any] = {
        "shapes": [
            {
                "label": "bad_polygon",
                "points": [[0, 0], [100, 0]],
                "shape_type": "polygon",
            },
            {
                "label": "landmark",
                "points": [[25, 30]],
                "shape_type": "point",
            },
        ]
    }
    json_path.write_text(json.dumps(raw_data), encoding="utf-8")

    document: LabelMeDocument | None = load_labelme_document(image_path)

    assert document is not None
    assert len(document.annotations) == 1
    assert document.annotations[0].label == "landmark"
    assert len(document.warnings) == 1
    assert "Polygon annotations require at least three vertices" in document.warnings[0]
