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


def test_annotation_lock_state_uses_flags() -> None:
    """Lock state should round-trip through the LabelMe-compatible flags dict."""
    annotation: Annotation = Annotation(
        label="landmark",
        shape_type=AnnotationShape.POINT,
        points=[(1.0, 2.0)],
    )

    assert annotation.locked is False
    annotation.set_locked(True)
    assert annotation.locked is True
    assert annotation.flags["ddg_locked"] is True
    annotation.set_locked(False)
    assert annotation.locked is False
    assert "ddg_locked" not in annotation.flags


def test_annotation_rejects_nonfinite_coordinates() -> None:
    """Annotations should reject NaN and infinite image coordinates."""
    with pytest.raises(ValueError, match="finite"):
        Annotation(
            label="landmark",
            shape_type=AnnotationShape.POINT,
            points=[(float("nan"), 2.0)],
        )

    with pytest.raises(ValueError, match="finite"):
        Annotation(
            label="cutline",
            shape_type=AnnotationShape.LINE,
            points=[(1.0, 2.0), (float("inf"), 4.0)],
        )
