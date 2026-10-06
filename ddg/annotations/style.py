"""Application-level display styles for native DDG annotations."""

from __future__ import annotations

from dataclasses import dataclass
import math

from PyQt6 import QtCore, QtGui

from .model import AnnotationShape


@dataclass(frozen=True, slots=True)
class AnnotationStyle:
    """Display style for one annotation geometry type.

    Args:
        color: Qt-compatible color string, normally ``#RRGGBB``.
        width: Stroke weight in pixels.
    """

    color: str
    width: float

    def __post_init__(self) -> None:
        """Validate the style values."""
        if not QtGui.QColor(self.color).isValid():
            raise ValueError(f"Invalid annotation color: {self.color!r}")
        if not math.isfinite(self.width) or self.width <= 0:
            raise ValueError(
                "Annotation stroke width must be a finite number greater than zero."
            )


DEFAULT_ANNOTATION_STYLES: dict[AnnotationShape, AnnotationStyle] = {
    AnnotationShape.POINT: AnnotationStyle(color="#ff00ff", width=4.0),
    AnnotationShape.LINE: AnnotationStyle(color="#ff00ff", width=4.0),
    AnnotationShape.POLYGON: AnnotationStyle(color="#ff00ff", width=4.0),
}


def load_annotation_style(
    shape_type: AnnotationShape,
    settings: QtCore.QSettings | None = None,
) -> AnnotationStyle:
    """Load the configured style for an annotation geometry type.

    Args:
        shape_type: Annotation geometry whose style should be loaded.
        settings: Optional settings object, primarily for tests. When omitted,
            the normal DDG application settings are used.

    Returns:
        Configured annotation style, falling back to DDG defaults when needed.
    """
    active_settings: QtCore.QSettings = settings or QtCore.QSettings(
        "AMNH", "DotDotGoose"
    )
    default_style: AnnotationStyle = DEFAULT_ANNOTATION_STYLES[shape_type]
    key_prefix: str = f"annotations/symbology/{shape_type.value}"

    color_value: object = active_settings.value(
        f"{key_prefix}/color", default_style.color
    )
    width_value: object = active_settings.value(
        f"{key_prefix}/width", default_style.width
    )

    color: str = str(color_value)
    try:
        width: float = float(width_value)
    except (TypeError, ValueError):
        width = default_style.width

    if not QtGui.QColor(color).isValid():
        color = default_style.color
    if not math.isfinite(width) or width <= 0:
        width = default_style.width

    return AnnotationStyle(color=color, width=width)


def save_annotation_style(
    shape_type: AnnotationShape,
    style: AnnotationStyle,
    settings: QtCore.QSettings | None = None,
) -> None:
    """Persist the display style for an annotation geometry type.

    Args:
        shape_type: Annotation geometry whose style should be saved.
        style: Color and stroke weight to persist.
        settings: Optional settings object, primarily for tests. When omitted,
            the normal DDG application settings are used.
    """
    active_settings: QtCore.QSettings = settings or QtCore.QSettings(
        "AMNH", "DotDotGoose"
    )
    key_prefix: str = f"annotations/symbology/{shape_type.value}"
    active_settings.setValue(f"{key_prefix}/color", style.color)
    active_settings.setValue(f"{key_prefix}/width", style.width)


def annotation_visibility_enabled(
    shape_type: AnnotationShape,
    settings: QtCore.QSettings | None = None,
) -> bool:
    """Return whether one annotation geometry type should be displayed.

    Args:
        shape_type: Annotation geometry whose visibility should be checked.
        settings: Optional settings object, primarily for tests.

    Returns:
        Persisted visibility state, defaulting to visible.
    """
    active_settings: QtCore.QSettings = settings or QtCore.QSettings(
        "AMNH", "DotDotGoose"
    )
    value: object = active_settings.value(
        f"annotations/visibility/{shape_type.value}", True
    )
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "no", "off"}


def save_annotation_visibility(
    shape_type: AnnotationShape,
    visible: bool,
    settings: QtCore.QSettings | None = None,
) -> None:
    """Persist display visibility for one annotation geometry type.

    Args:
        shape_type: Annotation geometry whose visibility should be saved.
        visible: Whether annotations of this type should be rendered.
        settings: Optional settings object, primarily for tests.
    """
    active_settings: QtCore.QSettings = settings or QtCore.QSettings(
        "AMNH", "DotDotGoose"
    )
    active_settings.setValue(
        f"annotations/visibility/{shape_type.value}", visible
    )
