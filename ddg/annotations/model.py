"""Core models for non-count image annotations."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeAlias

Point: TypeAlias = tuple[float, float]


class AnnotationShape(str, Enum):
    """Supported native annotation geometry types."""

    POINT = "point"
    LINE = "line"
    POLYGON = "polygon"


@dataclass(slots=True)
class Annotation:
    """A non-count annotation tied to original image pixel coordinates.

    Args:
        label: Semantic label such as ``landmark`` or ``count_region``.
        shape_type: Geometry type for the annotation.
        points: Ordered vertices in original image pixel coordinates.
        group_id: Optional LabelMe group identifier.
        flags: Optional LabelMe-compatible shape flags.
        source_shape_type: Original LabelMe shape type, when it differs from
            the normalized native geometry type (for example ``linestrip``).
        annotation_id: Optional stable identifier for future DDG-native
            relationships such as linked landmarks.
        source_shape_index: Zero-based index of the corresponding shape in the
            LabelMe ``shapes`` list, when loaded or saved from a sidecar.
    """

    label: str
    shape_type: AnnotationShape
    points: list[Point]
    group_id: int | str | None = None
    flags: dict[str, Any] = field(default_factory=dict)
    source_shape_type: str | None = None
    annotation_id: str | None = None
    source_shape_index: int | None = None

    def __post_init__(self) -> None:
        """Validate geometry immediately after construction."""
        self.validate()

    def validate(self) -> None:
        """Validate the minimum vertex count for the geometry.

        Raises:
            ValueError: If the annotation has an invalid number of vertices.
        """
        point_count: int = len(self.points)
        if self.shape_type is AnnotationShape.POINT and point_count != 1:
            raise ValueError("Point annotations require exactly one vertex.")
        if self.shape_type is AnnotationShape.LINE and point_count < 2:
            raise ValueError("Line annotations require at least two vertices.")
        if self.shape_type is AnnotationShape.POLYGON and point_count < 3:
            raise ValueError("Polygon annotations require at least three vertices.")
