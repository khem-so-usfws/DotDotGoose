"""Core models for non-count image annotations."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Any, TypeAlias

Point: TypeAlias = tuple[float, float]
LOCK_FLAG_KEY: str = "ddg_locked"


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
        for x, y in self.points:
            if not math.isfinite(float(x)) or not math.isfinite(float(y)):
                raise ValueError("Annotation coordinates must be finite numbers.")
        if self.shape_type is AnnotationShape.POINT and point_count != 1:
            raise ValueError("Point annotations require exactly one vertex.")
        if self.shape_type is AnnotationShape.LINE and point_count < 2:
            raise ValueError("Line annotations require at least two vertices.")
        if self.shape_type is AnnotationShape.POLYGON and point_count < 3:
            raise ValueError("Polygon annotations require at least three vertices.")

    @property
    def locked(self) -> bool:
        """Return whether DDG editing is locked for this annotation.

        The state is stored in the LabelMe-compatible ``flags`` dictionary so
        external tools can preserve it without needing a DDG-specific schema.

        Returns:
            ``True`` when the annotation should be protected from geometry or
            deletion edits.
        """
        value: Any = self.flags.get(LOCK_FLAG_KEY, False)
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def set_locked(self, locked: bool) -> None:
        """Set the persistent DDG edit-lock state.

        Args:
            locked: Whether geometry/deletion editing should be disabled.
        """
        if locked:
            self.flags[LOCK_FLAG_KEY] = True
        else:
            self.flags.pop(LOCK_FLAG_KEY, None)
