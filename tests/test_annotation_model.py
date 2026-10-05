"""Tests for native annotation models."""

from __future__ import annotations

import pytest

from ddg.annotations import Annotation, AnnotationShape


def test_point_requires_exactly_one_vertex() -> None:
    """Point annotations reject zero or multiple vertices."""
    with pytest.raises(ValueError):
        Annotation(label="landmark", shape_type=AnnotationShape.POINT, points=[])

    with pytest.raises(ValueError):
        Annotation(
            label="landmark",
            shape_type=AnnotationShape.POINT,
            points=[(1.0, 2.0), (3.0, 4.0)],
        )


def test_line_requires_at_least_two_vertices() -> None:
    """Line annotations require at least two vertices."""
    with pytest.raises(ValueError):
        Annotation(
            label="cutline",
            shape_type=AnnotationShape.LINE,
            points=[(1.0, 2.0)],
        )


def test_polygon_requires_at_least_three_vertices() -> None:
    """Polygon annotations require at least three vertices."""
    with pytest.raises(ValueError):
        Annotation(
            label="count_region",
            shape_type=AnnotationShape.POLYGON,
            points=[(1.0, 2.0), (3.0, 4.0)],
        )
