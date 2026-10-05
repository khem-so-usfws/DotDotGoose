"""Application-level display styles for native DDG annotations."""

from __future__ import annotations

from dataclasses import dataclass

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
        if self.width <= 0:
            raise ValueError("Annotation stroke width must be greater than zero.")


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
    if width <= 0:
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
