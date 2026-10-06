"""Tests for LabelMe annotation loading."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from ddg.annotations import (
    Annotation,
    AnnotationShape,
    LabelMeDocument,
    labelme_path_for_image,
    append_labelme_annotation,
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


def test_append_annotation_creates_labelme_sidecar(tmp_path: Path) -> None:
    """A new count region should create a readable LabelMe sidecar."""
    image_path: Path = tmp_path / "IMG_0001.JPG"
    image_path.write_bytes(b"")
    annotation: Annotation = Annotation(
        label="count_region",
        shape_type=AnnotationShape.POLYGON,
        points=[(10.0, 20.0), (30.0, 20.0), (30.0, 40.0)],
    )

    json_path: Path = append_labelme_annotation(
        image_path=image_path,
        annotation=annotation,
        image_width=6000,
        image_height=4000,
    )

    raw_data: dict[str, object] = json.loads(json_path.read_text(encoding="utf-8"))
    assert raw_data["imagePath"] == "IMG_0001.JPG"
    assert raw_data["imageWidth"] == 6000
    assert raw_data["imageHeight"] == 4000
    shapes: list[dict[str, object]] = cast(
        list[dict[str, object]], raw_data["shapes"]
    )
    assert len(shapes) == 1
    assert shapes[0]["label"] == "count_region"
    assert shapes[0]["shape_type"] == "polygon"


def test_append_annotation_preserves_existing_labelme_content(tmp_path: Path) -> None:
    """Appending a polygon must preserve unrelated metadata and shapes."""
    image_path: Path = tmp_path / "IMG_0002.JPG"
    image_path.write_bytes(b"")
    json_path: Path = image_path.with_suffix(".json")
    original: dict[str, object] = {
        "version": "5.8.0",
        "flags": {"reviewed": True},
        "customMetadata": {"observer": "example"},
        "shapes": [
            {
                "label": "keep_me",
                "points": [[1, 2], [3, 4]],
                "group_id": None,
                "shape_type": "rectangle",
                "flags": {},
            }
        ],
        "imagePath": image_path.name,
        "imageData": None,
        "imageHeight": 100,
        "imageWidth": 200,
    }
    json_path.write_text(json.dumps(original), encoding="utf-8")
    annotation: Annotation = Annotation(
        label="count_region",
        shape_type=AnnotationShape.POLYGON,
        points=[(10.0, 10.0), (20.0, 10.0), (20.0, 20.0)],
    )

    append_labelme_annotation(image_path=image_path, annotation=annotation)

    saved: dict[str, object] = json.loads(json_path.read_text(encoding="utf-8"))
    assert saved["flags"] == {"reviewed": True}
    assert saved["customMetadata"] == {"observer": "example"}
    shapes: list[dict[str, object]] = cast(
        list[dict[str, object]], saved["shapes"]
    )
    assert shapes[0]["shape_type"] == "rectangle"
    assert shapes[1]["label"] == "count_region"
    assert shapes[1]["shape_type"] == "polygon"


def test_append_line_and_point_annotations(tmp_path) -> None:
    """Line and point annotations should serialize with LabelMe shape types."""
    image_path = tmp_path / "IMG_2000.JPG"
    image_path.write_bytes(b"")

    line = Annotation(
        label="cutline",
        shape_type=AnnotationShape.LINE,
        points=[(1.0, 2.0), (3.0, 4.0)],
    )
    point = Annotation(
        label="landmark",
        shape_type=AnnotationShape.POINT,
        points=[(5.0, 6.0)],
    )
    append_labelme_annotation(image_path, line)
    append_labelme_annotation(image_path, point)

    document = load_labelme_document(image_path)
    assert document is not None
    assert [annotation.shape_type for annotation in document.annotations] == [
        AnnotationShape.LINE,
        AnnotationShape.POINT,
    ]
    assert [annotation.label for annotation in document.annotations] == [
        "cutline",
        "landmark",
    ]


def test_loaded_annotations_track_original_shape_indexes(tmp_path: Path) -> None:
    """Supported annotations should retain their original LabelMe shape indexes."""
    image_path: Path = tmp_path / "IMG_3000.JPG"
    json_path: Path = image_path.with_suffix(".json")
    raw_data: dict[str, object] = {
        "shapes": [
            {
                "label": "unsupported",
                "points": [[0, 0], [10, 10]],
                "shape_type": "rectangle",
            },
            {
                "label": "landmark",
                "points": [[25, 30]],
                "shape_type": "point",
            },
            {
                "label": "cutline",
                "points": [[1, 2], [3, 4]],
                "shape_type": "line",
            },
        ]
    }
    json_path.write_text(json.dumps(raw_data), encoding="utf-8")

    document: LabelMeDocument | None = load_labelme_document(image_path)

    assert document is not None
    assert [annotation.source_shape_index for annotation in document.annotations] == [
        1,
        2,
    ]


def test_update_annotation_preserves_unmanaged_shape_fields(tmp_path: Path) -> None:
    """Editing geometry should retain unrelated LabelMe shape fields."""
    from ddg.annotations import update_labelme_annotation

    image_path: Path = tmp_path / "IMG_3001.JPG"
    json_path: Path = image_path.with_suffix(".json")
    raw_data: dict[str, object] = {
        "flags": {"reviewed": True},
        "shapes": [
            {
                "label": "cutline",
                "points": [[1, 2], [3, 4]],
                "shape_type": "linestrip",
                "group_id": None,
                "flags": {},
                "description": "retain this",
                "customShapeField": 42,
            }
        ],
    }
    json_path.write_text(json.dumps(raw_data), encoding="utf-8")
    document: LabelMeDocument | None = load_labelme_document(image_path)
    assert document is not None
    annotation: Annotation = document.annotations[0]
    annotation.points[1] = (30.0, 40.0)

    update_labelme_annotation(image_path, annotation)

    saved: dict[str, object] = json.loads(json_path.read_text(encoding="utf-8"))
    shapes: list[dict[str, object]] = cast(
        list[dict[str, object]], saved["shapes"]
    )
    assert shapes[0]["points"] == [[1.0, 2.0], [30.0, 40.0]]
    assert shapes[0]["shape_type"] == "linestrip"
    assert shapes[0]["description"] == "retain this"
    assert shapes[0]["customShapeField"] == 42
    assert saved["flags"] == {"reviewed": True}


def test_delete_annotation_removes_only_selected_shape(tmp_path: Path) -> None:
    """Deleting one annotation should leave all other LabelMe shapes intact."""
    from ddg.annotations import delete_labelme_annotation

    image_path: Path = tmp_path / "IMG_3002.JPG"
    json_path: Path = image_path.with_suffix(".json")
    raw_data: dict[str, object] = {
        "customMetadata": "retain",
        "shapes": [
            {
                "label": "keep_before",
                "points": [[0, 0], [5, 5]],
                "shape_type": "rectangle",
            },
            {
                "label": "delete_me",
                "points": [[10, 10]],
                "shape_type": "point",
            },
            {
                "label": "keep_after",
                "points": [[20, 20], [30, 30]],
                "shape_type": "line",
            },
        ],
    }
    json_path.write_text(json.dumps(raw_data), encoding="utf-8")

    delete_labelme_annotation(image_path, 1)

    saved: dict[str, object] = json.loads(json_path.read_text(encoding="utf-8"))
    shapes: list[dict[str, object]] = cast(
        list[dict[str, object]], saved["shapes"]
    )
    assert [shape["label"] for shape in shapes] == ["keep_before", "keep_after"]
    assert saved["customMetadata"] == "retain"


def test_raw_document_history_round_trip(tmp_path: Path) -> None:
    """Raw LabelMe snapshots should support restore and sidecar removal."""
    from ddg.annotations import (
        load_labelme_raw_document,
        write_labelme_raw_document,
    )

    image_path: Path = tmp_path / "IMG_6000.JPG"
    image_path.write_bytes(b"")
    raw_data: dict[str, object] = {
        "customMetadata": {"observer": "example"},
        "shapes": [],
    }

    write_labelme_raw_document(image_path, raw_data)
    assert load_labelme_raw_document(image_path) == raw_data

    write_labelme_raw_document(image_path, None)
    assert load_labelme_raw_document(image_path) is None


def test_replace_annotations_by_label_preserves_other_shapes(tmp_path: Path) -> None:
    """Replacing count regions should preserve unrelated LabelMe shapes."""
    from ddg.annotations import (
        Annotation,
        AnnotationShape,
        replace_labelme_annotations_by_label,
    )

    image_path: Path = tmp_path / "IMG_6000.JPG"
    image_path.write_bytes(b"")
    raw_data: dict[str, object] = {
        "version": "5.0.1",
        "flags": {"keep": True},
        "shapes": [
            {
                "label": "landmark",
                "points": [[5, 5]],
                "group_id": None,
                "shape_type": "point",
                "flags": {"keep": True},
            },
            {
                "label": "count_region",
                "points": [[0, 0], [10, 0], [10, 10]],
                "group_id": None,
                "shape_type": "polygon",
                "flags": {},
            },
        ],
        "imagePath": image_path.name,
        "imageData": None,
        "imageHeight": 100,
        "imageWidth": 200,
    }
    image_path.with_suffix(".json").write_text(
        json.dumps(raw_data), encoding="utf-8"
    )
    replacement = Annotation(
        label="count_region",
        shape_type=AnnotationShape.POLYGON,
        points=[(0.0, 0.0), (200.0, 0.0), (200.0, 100.0), (0.0, 100.0)],
    )

    replace_labelme_annotations_by_label(
        image_path=image_path,
        label="count_region",
        annotations=[replacement],
    )

    saved: dict[str, object] = json.loads(
        image_path.with_suffix(".json").read_text(encoding="utf-8")
    )
    shapes = cast(list[dict[str, object]], saved["shapes"])
    assert [shape["label"] for shape in shapes] == ["landmark", "count_region"]
    assert shapes[0]["flags"] == {"keep": True}
    assert saved["flags"] == {"keep": True}
    assert replacement.source_shape_index == 1


def test_annotation_update_creates_rolling_backup(tmp_path: Path) -> None:
    """Saving over an existing sidecar should preserve the prior JSON."""
    from ddg.annotations import update_labelme_annotation

    image_path: Path = tmp_path / "IMG_7000.JPG"
    json_path: Path = image_path.with_suffix(".json")
    original: dict[str, object] = {
        "customMetadata": {"version": 1},
        "shapes": [
            {
                "label": "landmark",
                "points": [[10, 20]],
                "group_id": None,
                "shape_type": "point",
                "flags": {},
            }
        ],
    }
    json_path.write_text(json.dumps(original), encoding="utf-8")
    document: LabelMeDocument | None = load_labelme_document(image_path)
    assert document is not None
    annotation: Annotation = document.annotations[0]
    annotation.points[0] = (30.0, 40.0)

    update_labelme_annotation(image_path, annotation)

    backup_path: Path = json_path.with_name(f"{json_path.name}.bak")
    assert backup_path.exists()
    assert json.loads(backup_path.read_text(encoding="utf-8")) == original
    saved: dict[str, object] = json.loads(json_path.read_text(encoding="utf-8"))
    shapes: list[dict[str, object]] = cast(
        list[dict[str, object]], saved["shapes"]
    )
    assert shapes[0]["points"] == [[30.0, 40.0]]


def test_atomic_replace_failure_preserves_live_sidecar(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed final replace must leave the live LabelMe file untouched."""
    import ddg.annotations.labelme_io as labelme_io
    from ddg.annotations import update_labelme_annotation

    image_path: Path = tmp_path / "IMG_7001.JPG"
    json_path: Path = image_path.with_suffix(".json")
    original_text: str = json.dumps(
        {
            "customMetadata": "original",
            "shapes": [
                {
                    "label": "landmark",
                    "points": [[1, 2]],
                    "group_id": None,
                    "shape_type": "point",
                    "flags": {},
                }
            ],
        },
        indent=2,
    )
    json_path.write_text(original_text, encoding="utf-8")
    document: LabelMeDocument | None = load_labelme_document(image_path)
    assert document is not None
    annotation: Annotation = document.annotations[0]
    annotation.points[0] = (99.0, 100.0)

    def fail_replace(source: object, destination: object) -> None:
        """Simulate a filesystem failure during the atomic swap."""
        raise OSError("simulated replace failure")

    monkeypatch.setattr(labelme_io.os, "replace", fail_replace)

    with pytest.raises(OSError, match="simulated replace failure"):
        update_labelme_annotation(image_path, annotation)

    assert json_path.read_text(encoding="utf-8") == original_text
    backup_path: Path = json_path.with_name(f"{json_path.name}.bak")
    assert backup_path.exists()
    assert backup_path.read_text(encoding="utf-8") == original_text
    temporary_files: list[Path] = list(tmp_path.glob(f".{json_path.name}.*.tmp"))
    assert temporary_files == []


def test_malformed_sidecar_is_not_overwritten_when_appending(tmp_path: Path) -> None:
    """Malformed existing JSON should fail safely without modifying the file."""
    image_path: Path = tmp_path / "IMG_7002.JPG"
    json_path: Path = image_path.with_suffix(".json")
    malformed_text: str = '{"shapes": ['
    json_path.write_text(malformed_text, encoding="utf-8")
    annotation: Annotation = Annotation(
        label="count_region",
        shape_type=AnnotationShape.POLYGON,
        points=[(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)],
    )

    with pytest.raises(json.JSONDecodeError):
        append_labelme_annotation(image_path, annotation)

    assert json_path.read_text(encoding="utf-8") == malformed_text
    assert not json_path.with_name(f"{json_path.name}.bak").exists()


def test_removing_sidecar_keeps_last_live_copy_as_backup(tmp_path: Path) -> None:
    """History removal should preserve the deleted sidecar as a backup."""
    from ddg.annotations import write_labelme_raw_document

    image_path: Path = tmp_path / "IMG_7003.JPG"
    raw_data: dict[str, object] = {
        "customMetadata": {"observer": "example"},
        "shapes": [],
    }
    write_labelme_raw_document(image_path, raw_data)
    json_path: Path = image_path.with_suffix(".json")
    assert json_path.exists()

    write_labelme_raw_document(image_path, None)

    backup_path: Path = json_path.with_name(f"{json_path.name}.bak")
    assert not json_path.exists()
    assert json.loads(backup_path.read_text(encoding="utf-8")) == raw_data


def test_multivertex_cutline_serializes_as_linestrip(tmp_path: Path) -> None:
    """LabelMe multi-vertex cutlines must use linestrip, not line."""
    image_path: Path = tmp_path / "IMG_8000.JPG"
    image_path.write_bytes(b"")
    annotation: Annotation = Annotation(
        label="cutline",
        shape_type=AnnotationShape.LINE,
        points=[(1.0, 2.0), (3.0, 4.0), (5.0, 6.0)],
    )

    json_path: Path = append_labelme_annotation(image_path, annotation)

    raw_data: dict[str, object] = json.loads(json_path.read_text(encoding="utf-8"))
    shapes: list[dict[str, object]] = cast(
        list[dict[str, object]], raw_data["shapes"]
    )
    assert shapes[0]["shape_type"] == "linestrip"


def test_two_vertex_cutline_serializes_as_line(tmp_path: Path) -> None:
    """A two-vertex cutline remains a valid LabelMe line."""
    image_path: Path = tmp_path / "IMG_8001.JPG"
    image_path.write_bytes(b"")
    annotation: Annotation = Annotation(
        label="cutline",
        shape_type=AnnotationShape.LINE,
        points=[(1.0, 2.0), (3.0, 4.0)],
    )

    json_path: Path = append_labelme_annotation(image_path, annotation)

    raw_data: dict[str, object] = json.loads(json_path.read_text(encoding="utf-8"))
    shapes: list[dict[str, object]] = cast(
        list[dict[str, object]], raw_data["shapes"]
    )
    assert shapes[0]["shape_type"] == "line"


def test_adding_vertex_converts_existing_line_to_linestrip(tmp_path: Path) -> None:
    """Editing a two-point LabelMe line to three points should stay compatible."""
    from ddg.annotations import update_labelme_annotation

    image_path: Path = tmp_path / "IMG_8002.JPG"
    json_path: Path = image_path.with_suffix(".json")
    json_path.write_text(
        json.dumps(
            {
                "shapes": [
                    {
                        "label": "cutline",
                        "points": [[1, 2], [3, 4]],
                        "shape_type": "line",
                        "group_id": None,
                        "flags": {},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    document: LabelMeDocument | None = load_labelme_document(image_path)
    assert document is not None
    annotation: Annotation = document.annotations[0]
    annotation.points.append((5.0, 6.0))

    update_labelme_annotation(image_path, annotation)

    saved: dict[str, object] = json.loads(json_path.read_text(encoding="utf-8"))
    shapes: list[dict[str, object]] = cast(
        list[dict[str, object]], saved["shapes"]
    )
    assert shapes[0]["shape_type"] == "linestrip"


def test_replace_count_regions_preserves_same_label_nonpolygon(tmp_path: Path) -> None:
    """Whole-image replacement should only replace polygon count regions."""
    from ddg.annotations import replace_labelme_annotations_by_label

    image_path: Path = tmp_path / "IMG_8003.JPG"
    json_path: Path = image_path.with_suffix(".json")
    json_path.write_text(
        json.dumps(
            {
                "shapes": [
                    {
                        "label": "count_region",
                        "points": [[1, 2], [3, 4]],
                        "shape_type": "line",
                    },
                    {
                        "label": "count_region",
                        "points": [[0, 0], [10, 0], [10, 10]],
                        "shape_type": "polygon",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    replacement: Annotation = Annotation(
        label="count_region",
        shape_type=AnnotationShape.POLYGON,
        points=[(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)],
    )

    replace_labelme_annotations_by_label(
        image_path=image_path,
        label="count_region",
        annotations=[replacement],
        shape_type=AnnotationShape.POLYGON,
    )

    saved: dict[str, object] = json.loads(json_path.read_text(encoding="utf-8"))
    shapes: list[dict[str, object]] = cast(
        list[dict[str, object]], saved["shapes"]
    )
    assert len(shapes) == 2
    assert shapes[0]["shape_type"] == "line"
    assert shapes[1]["shape_type"] == "polygon"


def test_missing_shape_type_loads_as_legacy_polygon(tmp_path: Path) -> None:
    """Legacy LabelMe shapes without shape_type should default to polygon."""
    image_path: Path = tmp_path / "IMG_8004.JPG"
    image_path.with_suffix(".json").write_text(
        json.dumps(
            {
                "shapes": [
                    {
                        "label": "count_region",
                        "points": [[0, 0], [10, 0], [10, 10]],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    document: LabelMeDocument | None = load_labelme_document(image_path)

    assert document is not None
    assert len(document.annotations) == 1
    assert document.annotations[0].shape_type is AnnotationShape.POLYGON
