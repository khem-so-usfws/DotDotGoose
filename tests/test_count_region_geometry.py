"""Tests for count-region geometry helpers."""

from __future__ import annotations

from ddg.annotations import (
    Annotation,
    AnnotationShape,
    count_region_polygons,
    point_in_count_regions,
    point_in_polygon,
)


def _count_region() -> Annotation:
    """Return one square count-region annotation for tests."""
    return Annotation(
        label="count_region",
        shape_type=AnnotationShape.POLYGON,
        points=[(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)],
    )


def test_point_in_polygon_includes_interior_and_boundary() -> None:
    """Interior points and exact boundary points should both be valid."""
    polygon: list[tuple[float, float]] = _count_region().points

    assert point_in_polygon((50.0, 50.0), polygon) is True
    assert point_in_polygon((0.0, 50.0), polygon) is True
    assert point_in_polygon((100.0, 100.0), polygon) is True
    assert point_in_polygon((101.0, 50.0), polygon) is False


def test_count_region_polygons_filters_by_label_and_shape() -> None:
    """Only polygon annotations labeled count_region define valid area."""
    annotations: list[Annotation] = [
        _count_region(),
        Annotation(
            label="other",
            shape_type=AnnotationShape.POLYGON,
            points=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
        ),
        Annotation(
            label="cutline",
            shape_type=AnnotationShape.LINE,
            points=[(0.0, 0.0), (1.0, 1.0)],
        ),
    ]

    regions: list[Annotation] = count_region_polygons(annotations)

    assert regions == [annotations[0]]


def test_point_in_count_regions_uses_union_semantics() -> None:
    """A point is valid when it falls in any count-region polygon."""
    annotations: list[Annotation] = [
        _count_region(),
        Annotation(
            label="count_region",
            shape_type=AnnotationShape.POLYGON,
            points=[(200.0, 0.0), (300.0, 0.0), (300.0, 100.0), (200.0, 100.0)],
        ),
    ]

    assert point_in_count_regions((50.0, 50.0), annotations) is True
    assert point_in_count_regions((250.0, 50.0), annotations) is True
    assert point_in_count_regions((150.0, 50.0), annotations) is False


def test_point_in_count_regions_is_false_without_regions() -> None:
    """No count-region annotation means no explicit valid area exists."""
    assert point_in_count_regions((10.0, 10.0), []) is False
