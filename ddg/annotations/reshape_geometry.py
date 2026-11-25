"""Source-pixel geometry for reshaping, tracing, and editing annotations."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from math import dist

from .model import Point

EPSILON: float = 1e-7


@dataclass(frozen=True)
class Location:
    """Point on a path and its order (edge index plus fractional progress)."""

    point: Point
    order: float


@dataclass
class ReshapeResult:
    """A replacement path and the original portion it removes."""

    points: list[Point]
    removed: list[Point]


def distinct(points: Sequence[Point], closed: bool = False) -> list[Point]:
    """Remove consecutive duplicate vertices and an optional closing vertex."""
    path: list[Point] = []
    for point in points:
        if not path or dist(path[-1], point) > EPSILON:
            path.append(point)
    if closed and len(path) > 1 and dist(path[0], path[-1]) <= EPSILON:
        path.pop()
    return path


def project(point: Point, start: Point, end: Point) -> tuple[Point, float]:
    """Return the nearest point on a segment and its fractional progress."""
    dx: float = end[0] - start[0]
    dy: float = end[1] - start[1]
    length: float = dx * dx + dy * dy
    fraction: float = (
        min(
            1.0,
            max(
                0.0, ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length
            ),
        )
        if length
        else 0.0
    )
    return (start[0] + fraction * dx, start[1] + fraction * dy), fraction


def section(points: Sequence[Point], start: Location, end: Location) -> list[Point]:
    """Copy a path between ordered locations, reversing it when necessary."""
    if start.order > end.order:
        return list(reversed(section(points, end, start)))
    return distinct(
        [
            start.point,
            *(
                point
                for index, point in enumerate(points)
                if start.order < index < end.order
            ),
            end.point,
        ]
    )


def _crossings(
    a: Point, b: Point, c: Point, d: Point
) -> Iterator[tuple[float, float, Point]]:
    """Yield intersections with progress on both segments, including touches."""
    if any(
        max(min(a[axis], b[axis]), min(c[axis], d[axis]))
        > min(max(a[axis], b[axis]), max(c[axis], d[axis])) + EPSILON
        for axis in (0, 1)
    ):
        return
    rx, ry = b[0] - a[0], b[1] - a[1]
    sx, sy = d[0] - c[0], d[1] - c[1]
    qx, qy = c[0] - a[0], c[1] - a[1]
    determinant: float = rx * sy - ry * sx
    if abs(determinant) > EPSILON:
        t: float = (qx * sy - qy * sx) / determinant
        u: float = (qx * ry - qy * rx) / determinant
        if -EPSILON <= t <= 1 + EPSILON and -EPSILON <= u <= 1 + EPSILON:
            t = min(1.0, max(0.0, t))
            u = min(1.0, max(0.0, u))
            yield t, u, (a[0] + t * rx, a[1] + t * ry)
        return
    # A collinear overlap has endpoints on both paths. Report those anchors
    # so a longer overlap or a loop cannot masquerade as one crossing.
    for point in (a, b, c, d):
        first, t = project(point, a, b)
        second, u = project(point, c, d)
        if dist(first, point) <= EPSILON and dist(second, point) <= EPSILON:
            yield t, u, point


def valid_shape(points: Sequence[Point], closed: bool) -> bool:
    """Check minimum geometry and reject collapsed or self-crossing polygons."""
    if len(points) < (3 if closed else 2) or len(distinct(points, closed)) != len(
        points
    ):
        return False
    if not closed:
        return True
    edges: list[tuple[Point, Point]] = list(zip(points, (*points[1:], points[0])))
    if abs(polygon_area(points)) <= EPSILON:
        return False
    for index, (a, b) in enumerate(edges):
        for other in range(index + 1, len(edges)):
            c, d = edges[other]
            shared: Point | None = (
                b
                if other == index + 1
                else a if index == 0 and other == len(edges) - 1 else None
            )
            if any(
                shared is None or dist(point, shared) > EPSILON
                for _, _, point in _crossings(a, b, c, d)
            ):
                return False
    return True


def polygon_area(points: Sequence[Point]) -> float:
    """Return signed polygon area in source pixels squared."""
    return (
        sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(points, (*points[1:], points[0])))
        / 2
        if points
        else 0.0
    )


def reshape(
    points: Sequence[Point], sketch: Sequence[Point], closed: bool
) -> list[ReshapeResult]:
    """Replace the portion between two distinct, unambiguous sketch joins.

    Args:
        points: Source line or polygon vertices.
        sketch: User sketch, optionally extending beyond either join.
        closed: Whether the target is a polygon.

    Returns:
        One line alternative or the valid polygon alternatives.

    Raises:
        ValueError: If the sketch has ambiguous joins or yields invalid geometry.
    """
    path: list[Point] = distinct(points, closed)
    if closed and path:
        path.append(path[0])
    stroke: list[Point] = distinct(sketch)
    joins: list[tuple[Location, Location]] = []
    for j, (a, b) in enumerate(zip(stroke, stroke[1:])):
        for i, (c, d) in enumerate(zip(path, path[1:])):
            for t, u, point in _crossings(a, b, c, d):
                order: float = i + u
                if closed and abs(order - (len(path) - 1)) <= EPSILON:
                    order = 0.0
                if any(
                    abs(source.order - order) <= EPSILON
                    and abs(draft.order - (j + t)) <= EPSILON
                    for source, draft in joins
                ):
                    continue
                joins.append((Location(point, order), Location(point, j + t)))
    if len(joins) != 2 or dist(joins[0][0].point, joins[1][0].point) <= EPSILON:
        raise ValueError(
            "Sketch across the boundary twice or snap to two distinct joins."
        )

    first, last = sorted(joins, key=lambda join: join[0].order)
    start, end = first[0], last[0]
    replacement: list[Point] = section(stroke, first[1], last[1])
    head: list[Point] = section(path, Location(path[0], 0), start)
    tail: list[Point] = section(path, end, Location(path[-1], len(path) - 1))
    between: list[Point] = section(path, start, end)
    outer: list[Point] = distinct(tail + head)
    alternatives: list[ReshapeResult] = [
        ReshapeResult(distinct(head + replacement + tail, closed), between)
    ]
    if closed:
        alternatives.append(
            ReshapeResult(distinct(replacement + list(reversed(between)), True), outer)
        )
    valid: list[ReshapeResult] = [
        result for result in alternatives if valid_shape(result.points, closed)
    ]
    if not valid:
        raise ValueError(
            "The sketch would produce invalid geometry. Revise the sketch."
        )
    return valid
