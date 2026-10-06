"""Geometry helpers for DDG native annotations."""

from __future__ import annotations

from .model import Annotation, AnnotationShape, Point

_COUNT_REGION_LABEL: str = "count_region"
_EPSILON: float = 1e-9


def count_region_polygons(annotations: list[Annotation]) -> list[Annotation]:
    """Return polygon annotations that define valid count regions.

    Args:
        annotations: Native annotations for one source image.

    Returns:
        Polygon annotations labeled ``count_region``.
    """
    return [
        annotation
        for annotation in annotations
        if annotation.shape_type is AnnotationShape.POLYGON
        and annotation.label == _COUNT_REGION_LABEL
    ]


def point_on_segment(point: Point, start: Point, end: Point) -> bool:
    """Return whether a point lies on a line segment, including endpoints.

    Args:
        point: Candidate point.
        start: Segment start point.
        end: Segment end point.

    Returns:
        ``True`` when ``point`` lies on the segment.
    """
    px, py = point
    x1, y1 = start
    x2, y2 = end

    cross: float = (px - x1) * (y2 - y1) - (py - y1) * (x2 - x1)
    if abs(cross) > _EPSILON:
        return False

    min_x: float = min(x1, x2) - _EPSILON
    max_x: float = max(x1, x2) + _EPSILON
    min_y: float = min(y1, y2) - _EPSILON
    max_y: float = max(y1, y2) + _EPSILON
    return min_x <= px <= max_x and min_y <= py <= max_y


def point_in_polygon(point: Point, polygon: list[Point]) -> bool:
    """Return whether a point is inside or on the edge of a polygon.

    The implementation uses an even/odd ray crossing test and treats polygon
    edges as inside so points exactly on a count boundary are not
    unexpectedly excluded.

    Args:
        point: Candidate source-image pixel coordinate.
        polygon: Ordered polygon vertices.

    Returns:
        ``True`` when the point is inside or on the polygon boundary.
    """
    if len(polygon) < 3:
        return False

    px, py = point
    inside: bool = False
    previous_index: int = len(polygon) - 1

    for current_index, current in enumerate(polygon):
        previous: Point = polygon[previous_index]
        if point_on_segment(point, previous, current):
            return True

        x1, y1 = previous
        x2, y2 = current
        crosses_y: bool = (y1 > py) != (y2 > py)
        if crosses_y:
            intersection_x: float = (x2 - x1) * (py - y1) / (y2 - y1) + x1
            if px < intersection_x:
                inside = not inside
        previous_index = current_index

    return inside


def point_in_count_regions(point: Point, annotations: list[Annotation]) -> bool:
    """Return whether a point falls within any valid count-region polygon.

    Args:
        point: Source-image pixel coordinate.
        annotations: Native annotations for one image.

    Returns:
        ``True`` if the point lies inside or on at least one ``count_region``.
        Returns ``False`` when no count regions are defined.
    """
    return any(
        point_in_polygon(point, annotation.points)
        for annotation in count_region_polygons(annotations)
    )
