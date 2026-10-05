"""Read LabelMe annotation sidecars into DDG-native annotation models."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .model import Annotation, AnnotationShape, Point


@dataclass(slots=True)
class LabelMeDocument:
    """A loaded LabelMe document and its supported DDG annotations.

    The original JSON object is retained so a later writer can preserve fields
    and unsupported shapes that DDG does not intentionally edit.

    Args:
        path: Path to the LabelMe JSON sidecar.
        raw_data: Complete parsed LabelMe JSON object.
        annotations: Supported point, line, and polygon annotations.
        warnings: Non-fatal parsing warnings for unsupported or invalid shapes.
    """

    path: Path
    raw_data: dict[str, Any]
    annotations: list[Annotation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def labelme_path_for_image(image_path: str | Path) -> Path:
    """Return the conventional LabelMe sidecar path for an image.

    Args:
        image_path: Source image path.

    Returns:
        Path with the image suffix replaced by ``.json``.
    """
    return Path(image_path).with_suffix(".json")


def append_labelme_annotation(
    image_path: str | Path,
    annotation: Annotation,
    image_width: int | None = None,
    image_height: int | None = None,
) -> Path:
    """Append one DDG annotation to an image's LabelMe sidecar.

    Existing LabelMe content is preserved verbatim except for the addition of
    one new object to the ``shapes`` list. If no sidecar exists, a minimal
    LabelMe-compatible document is created.

    Args:
        image_path: Source image associated with the annotation.
        annotation: Native DDG annotation to append.
        image_width: Optional source-image width in pixels.
        image_height: Optional source-image height in pixels.

    Returns:
        Path to the written LabelMe JSON sidecar.

    Raises:
        json.JSONDecodeError: If an existing sidecar contains malformed JSON.
        OSError: If the sidecar cannot be read or written.
        ValueError: If an existing JSON root or ``shapes`` value is invalid.
    """
    json_path: Path = labelme_path_for_image(image_path)
    raw_data: dict[str, Any]

    if json_path.exists():
        with json_path.open("r", encoding="utf-8") as file:
            loaded_data: Any = json.load(file)
        if not isinstance(loaded_data, dict):
            raise ValueError("LabelMe JSON root must be an object.")
        raw_data = loaded_data
    else:
        raw_data = _new_labelme_document(
            image_path=image_path,
            image_width=image_width,
            image_height=image_height,
        )

    raw_shapes: Any = raw_data.setdefault("shapes", [])
    if not isinstance(raw_shapes, list):
        raise ValueError("LabelMe 'shapes' value must be a list before saving.")

    annotation.source_shape_index = len(raw_shapes)
    raw_shapes.append(annotation_to_labelme_shape(annotation))

    with json_path.open("w", encoding="utf-8") as file:
        json.dump(raw_data, file, indent=2, ensure_ascii=False)
        file.write("\n")

    return json_path


def update_labelme_annotation(
    image_path: str | Path,
    annotation: Annotation,
) -> Path:
    """Update one existing LabelMe shape from a native annotation.

    Only fields managed by DDG are updated; unrelated shape fields and
    top-level LabelMe metadata are preserved.

    Args:
        image_path: Source image associated with the annotation.
        annotation: Annotation with a valid ``source_shape_index``.

    Returns:
        Path to the updated LabelMe JSON sidecar.

    Raises:
        FileNotFoundError: If the sidecar does not exist.
        IndexError: If the annotation's source index is out of range.
        ValueError: If the LabelMe document structure is invalid or the
            annotation does not identify a source shape.
    """
    json_path: Path = labelme_path_for_image(image_path)
    raw_data: dict[str, Any] = _load_labelme_root(json_path)
    raw_shapes: list[Any] = _require_shape_list(raw_data)
    source_index: int | None = annotation.source_shape_index
    if source_index is None:
        raise ValueError("Annotation has no LabelMe source shape index.")
    if source_index < 0 or source_index >= len(raw_shapes):
        raise IndexError("Annotation source shape index is out of range.")

    raw_shape: Any = raw_shapes[source_index]
    if not isinstance(raw_shape, dict):
        raise ValueError("LabelMe source shape must be an object.")

    raw_shape["label"] = annotation.label
    raw_shape["points"] = [[x, y] for x, y in annotation.points]
    raw_shape["group_id"] = annotation.group_id
    raw_shape["flags"] = dict(annotation.flags)
    raw_shape["shape_type"] = (
        annotation.source_shape_type or annotation.shape_type.value
    )
    _write_labelme_root(json_path, raw_data)
    return json_path


def delete_labelme_annotation(
    image_path: str | Path,
    source_shape_index: int,
) -> Path:
    """Delete one shape from an image's LabelMe sidecar.

    Args:
        image_path: Source image associated with the annotation.
        source_shape_index: Zero-based shape index in the LabelMe ``shapes``
            list.

    Returns:
        Path to the updated LabelMe JSON sidecar.

    Raises:
        FileNotFoundError: If the sidecar does not exist.
        IndexError: If ``source_shape_index`` is out of range.
        ValueError: If the LabelMe document structure is invalid.
    """
    json_path: Path = labelme_path_for_image(image_path)
    raw_data: dict[str, Any] = _load_labelme_root(json_path)
    raw_shapes: list[Any] = _require_shape_list(raw_data)
    if source_shape_index < 0 or source_shape_index >= len(raw_shapes):
        raise IndexError("Annotation source shape index is out of range.")

    raw_shapes.pop(source_shape_index)
    _write_labelme_root(json_path, raw_data)
    return json_path


def _load_labelme_root(json_path: Path) -> dict[str, Any]:
    """Load and validate a LabelMe root object.

    Args:
        json_path: LabelMe JSON path.

    Returns:
        Parsed LabelMe root object.
    """
    with json_path.open("r", encoding="utf-8") as file:
        raw_data: Any = json.load(file)
    if not isinstance(raw_data, dict):
        raise ValueError("LabelMe JSON root must be an object.")
    return raw_data


def _require_shape_list(raw_data: dict[str, Any]) -> list[Any]:
    """Return the validated LabelMe shapes list.

    Args:
        raw_data: Parsed LabelMe root object.

    Returns:
        Mutable shape list.
    """
    raw_shapes: Any = raw_data.get("shapes")
    if not isinstance(raw_shapes, list):
        raise ValueError("LabelMe 'shapes' value must be a list.")
    return raw_shapes


def _write_labelme_root(json_path: Path, raw_data: dict[str, Any]) -> None:
    """Write one LabelMe document with stable formatting.

    Args:
        json_path: Destination LabelMe JSON path.
        raw_data: LabelMe root object to write.
    """
    with json_path.open("w", encoding="utf-8") as file:
        json.dump(raw_data, file, indent=2, ensure_ascii=False)
        file.write("\n")



def load_labelme_raw_document(image_path: str | Path) -> dict[str, Any] | None:
    """Load the complete raw LabelMe sidecar for history snapshots.

    Args:
        image_path: Source image path whose sibling JSON file should be read.

    Returns:
        Parsed LabelMe root object, or ``None`` when no sidecar exists.
    """
    json_path: Path = labelme_path_for_image(image_path)
    if not json_path.exists():
        return None
    return _load_labelme_root(json_path)


def write_labelme_raw_document(
    image_path: str | Path,
    raw_data: dict[str, Any] | None,
) -> Path:
    """Restore one complete LabelMe document from a history snapshot.

    Args:
        image_path: Source image associated with the sidecar.
        raw_data: Complete LabelMe root object. ``None`` removes the sidecar,
            which is needed when undoing creation of the first annotation.

    Returns:
        Conventional LabelMe sidecar path.
    """
    json_path: Path = labelme_path_for_image(image_path)
    if raw_data is None:
        if json_path.exists():
            json_path.unlink()
        return json_path

    _write_labelme_root(json_path, raw_data)
    return json_path

def annotation_to_labelme_shape(annotation: Annotation) -> dict[str, Any]:
    """Convert a native annotation to a LabelMe shape dictionary.

    Args:
        annotation: Native DDG annotation.

    Returns:
        LabelMe-compatible shape dictionary.
    """
    shape_type: str = annotation.shape_type.value
    return {
        "label": annotation.label,
        "points": [[x, y] for x, y in annotation.points],
        "group_id": annotation.group_id,
        "description": "",
        "shape_type": shape_type,
        "flags": dict(annotation.flags),
    }


def _new_labelme_document(
    image_path: str | Path,
    image_width: int | None,
    image_height: int | None,
) -> dict[str, Any]:
    """Create a minimal LabelMe-compatible document.

    Args:
        image_path: Source image path.
        image_width: Optional image width in pixels.
        image_height: Optional image height in pixels.

    Returns:
        New LabelMe-compatible JSON object.
    """
    return {
        "version": "5.0.1",
        "flags": {},
        "shapes": [],
        "imagePath": Path(image_path).name,
        "imageData": None,
        "imageHeight": image_height,
        "imageWidth": image_width,
    }


def load_labelme_document(image_path: str | Path) -> LabelMeDocument | None:
    """Load supported annotations from an image's LabelMe JSON sidecar.

    Unsupported shapes are preserved in ``raw_data`` and reported in
    ``warnings`` but are not converted to DDG annotations.

    Args:
        image_path: Source image path whose sibling JSON file should be read.

    Returns:
        A loaded document, or ``None`` when no sidecar exists.

    Raises:
        json.JSONDecodeError: If the sidecar contains malformed JSON.
        OSError: If the sidecar exists but cannot be read.
        ValueError: If the JSON root is not an object.
    """
    json_path: Path = labelme_path_for_image(image_path)
    if not json_path.exists():
        return None

    with json_path.open("r", encoding="utf-8") as file:
        raw_data: Any = json.load(file)

    if not isinstance(raw_data, dict):
        raise ValueError("LabelMe JSON root must be an object.")

    document: LabelMeDocument = LabelMeDocument(
        path=json_path,
        raw_data=raw_data,
    )
    raw_shapes: Any = raw_data.get("shapes", [])
    if not isinstance(raw_shapes, list):
        document.warnings.append("LabelMe 'shapes' value is not a list.")
        return document

    for index, raw_shape in enumerate(raw_shapes):
        if not isinstance(raw_shape, dict):
            document.warnings.append(f"Shape {index} is not an object.")
            continue

        try:
            annotation: Annotation | None = _annotation_from_shape(
                raw_shape, source_shape_index=index
            )
        except (TypeError, ValueError) as error:
            document.warnings.append(f"Shape {index} was not loaded: {error}")
            continue

        if annotation is None:
            shape_type: Any = raw_shape.get("shape_type")
            document.warnings.append(
                f"Shape {index} uses unsupported shape_type {shape_type!r}."
            )
            continue

        document.annotations.append(annotation)

    return document


def _annotation_from_shape(
    raw_shape: dict[str, Any],
    source_shape_index: int | None = None,
) -> Annotation | None:
    """Convert one LabelMe shape object to a normalized annotation.

    Args:
        raw_shape: LabelMe shape dictionary.
        source_shape_index: Optional source position in the LabelMe shapes list.

    Returns:
        A normalized annotation, or ``None`` for unsupported shape types.

    Raises:
        TypeError: If the points collection is malformed.
        ValueError: If geometry does not meet minimum vertex requirements.
    """
    source_shape_type: str = str(raw_shape.get("shape_type", ""))
    shape_type: AnnotationShape | None = _normalize_shape_type(source_shape_type)
    if shape_type is None:
        return None

    raw_points: Any = raw_shape.get("points", [])
    if not isinstance(raw_points, list):
        raise TypeError("'points' must be a list.")

    points: list[Point] = []
    for raw_point in raw_points:
        if not isinstance(raw_point, (list, tuple)) or len(raw_point) < 2:
            raise TypeError("Each point must contain x and y values.")
        x: float = float(raw_point[0])
        y: float = float(raw_point[1])
        points.append((x, y))

    raw_flags: Any = raw_shape.get("flags", {})
    flags: dict[str, Any] = dict(raw_flags) if isinstance(raw_flags, dict) else {}

    raw_group_id: Any = raw_shape.get("group_id")
    group_id: int | str | None
    if isinstance(raw_group_id, (int, str)) or raw_group_id is None:
        group_id = raw_group_id
    else:
        group_id = str(raw_group_id)

    raw_annotation_id: Any = raw_shape.get("annotation_id")
    annotation_id: str | None = (
        str(raw_annotation_id) if raw_annotation_id is not None else None
    )

    return Annotation(
        label=str(raw_shape.get("label", "")),
        shape_type=shape_type,
        points=points,
        group_id=group_id,
        flags=flags,
        source_shape_type=source_shape_type,
        annotation_id=annotation_id,
        source_shape_index=source_shape_index,
    )


def _normalize_shape_type(shape_type: str) -> AnnotationShape | None:
    """Normalize LabelMe geometry names to DDG annotation types.

    Args:
        shape_type: LabelMe ``shape_type`` string.

    Returns:
        Normalized geometry type, or ``None`` when unsupported.
    """
    normalized: str = shape_type.lower().strip()
    if normalized == "point":
        return AnnotationShape.POINT
    if normalized in {"line", "linestrip"}:
        return AnnotationShape.LINE
    if normalized == "polygon":
        return AnnotationShape.POLYGON
    return None
