#!/usr/bin/env python3
from __future__ import annotations

from typing import Iterable, List, Sequence, Tuple


Point = Tuple[float, float]
Segment = Tuple[Point, Point]


def polygon_bounds(points: Sequence[Point]) -> Tuple[float, float, float, float]:
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    min_x = min(xs)
    min_y = min(ys)
    max_x = max(xs)
    max_y = max(ys)
    return min_x, min_y, max_x - min_x, max_y - min_y


def polygon_centroid(points: Sequence[Point]) -> Point:
    if not points:
        return (0.0, 0.0)
    area = 0.0
    cx = 0.0
    cy = 0.0
    count = len(points)
    for idx in range(count):
        x1, y1 = points[idx]
        x2, y2 = points[(idx + 1) % count]
        cross = x1 * y2 - x2 * y1
        area += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    if abs(area) < 1e-6:
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        return (sum(xs) / len(xs), sum(ys) / len(ys))
    area *= 0.5
    return (cx / (6.0 * area), cy / (6.0 * area))


def polygon_area(points: Sequence[Point]) -> float:
    if len(points) < 3:
        return 0.0
    area = 0.0
    count = len(points)
    for idx in range(count):
        x1, y1 = points[idx]
        x2, y2 = points[(idx + 1) % count]
        area += x1 * y2 - x2 * y1
    return abs(area) * 0.5


def segments_from_polygon(points: Sequence[Point]) -> List[Segment]:
    return [
        (points[idx], points[(idx + 1) % len(points)])
        for idx in range(len(points))
    ]


def point_in_polygon(point: Point, polygon: Sequence[Point]) -> bool:
    x, y = point
    inside = False
    count = len(polygon)
    if count < 3:
        return False
    for idx in range(count):
        x1, y1 = polygon[idx]
        x2, y2 = polygon[(idx + 1) % count]
        crosses = (y1 > y) != (y2 > y)
        if crosses:
            slope_x = (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-9) + x1
            if x < slope_x:
                inside = not inside
    return inside


def canonical_segment(start: Point, end: Point, precision: int = 3) -> Tuple[float, float, float, float]:
    sx, sy = round(start[0], precision), round(start[1], precision)
    ex, ey = round(end[0], precision), round(end[1], precision)
    if (ex, ey) < (sx, sy):
        sx, sy, ex, ey = ex, ey, sx, sy
    return (sx, sy, ex, ey)


def segment_length(start: Point, end: Point) -> float:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    return (dx * dx + dy * dy) ** 0.5


def all_points(polygons: Iterable[Sequence[Point]]) -> List[Point]:
    points: List[Point] = []
    for polygon in polygons:
        points.extend(list(polygon))
    return points


Box = Tuple[float, float, float, float]


def boxes_intersect(a: Box, b: Box) -> bool:
    """True when two axis-aligned boxes (x1, y1, x2, y2) share interior area."""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    return ax1 < bx2 and ax2 > bx1 and ay1 < by2 and ay2 > by1


def _orient(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def point_on_segment(point: Point, start: Point, end: Point, eps: float = 1e-6) -> bool:
    if abs(_orient(start, end, point)) > eps:
        return False
    return (
        min(start[0], end[0]) - eps <= point[0] <= max(start[0], end[0]) + eps
        and min(start[1], end[1]) - eps <= point[1] <= max(start[1], end[1]) + eps
    )


def point_on_polygon_boundary(point: Point, polygon: Sequence[Point], eps: float = 1e-6) -> bool:
    return any(point_on_segment(point, start, end, eps) for start, end in segments_from_polygon(polygon))


def point_strictly_in_polygon(point: Point, polygon: Sequence[Point], eps: float = 1e-6) -> bool:
    """Inside test that treats boundary points as outside (unlike point_in_polygon)."""
    if point_on_polygon_boundary(point, polygon, eps):
        return False
    return point_in_polygon(point, polygon)


def segments_properly_intersect(a: Point, b: Point, c: Point, d: Point, eps: float = 1e-9) -> bool:
    """True only when segments cross at an interior point of both (touching endpoints do not count)."""
    d1 = _orient(c, d, a)
    d2 = _orient(c, d, b)
    d3 = _orient(a, b, c)
    d4 = _orient(a, b, d)
    return ((d1 > eps and d2 < -eps) or (d1 < -eps and d2 > eps)) and (
        (d3 > eps and d4 < -eps) or (d3 < -eps and d4 > eps)
    )


def box_corners(box: Box) -> List[Point]:
    x1, y1, x2, y2 = box
    return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]


def polygon_within_polygon(inner: Sequence[Point], outer: Sequence[Point], eps: float = 1e-6) -> bool:
    """True when `inner` lies inside `outer`; shared edges and vertices are allowed."""
    if len(inner) < 3 or len(outer) < 3:
        return False
    outer_edges = segments_from_polygon(outer)
    inner_edges = segments_from_polygon(inner)
    for start, end in inner_edges:
        for o_start, o_end in outer_edges:
            if segments_properly_intersect(start, end, o_start, o_end):
                return False
    for vertex in inner:
        if not (point_in_polygon(vertex, outer) or point_on_polygon_boundary(vertex, outer, eps)):
            return False
    # Vertices may all sit on the boundary while an edge runs outside (e.g. across a notch),
    # so also test each edge midpoint.
    for start, end in inner_edges:
        mid = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
        if not (point_in_polygon(mid, outer) or point_on_polygon_boundary(mid, outer, eps)):
            return False
    return True


def box_within_polygon(box: Box, polygon: Sequence[Point], eps: float = 1e-6) -> bool:
    return polygon_within_polygon(box_corners(box), polygon, eps)


def polygons_overlap(first: Sequence[Point], second: Sequence[Point], eps: float = 1e-6) -> bool:
    """True when two polygons share interior area (touching along an edge is not overlap)."""
    if len(first) < 3 or len(second) < 3:
        return False
    first_edges = segments_from_polygon(first)
    second_edges = segments_from_polygon(second)
    for a, b in first_edges:
        for c, d in second_edges:
            if segments_properly_intersect(a, b, c, d):
                return True
    for polygon, other in ((first, second), (second, first)):
        for vertex in polygon:
            if point_strictly_in_polygon(vertex, other, eps):
                return True
        for start, end in segments_from_polygon(polygon):
            mid = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
            if point_strictly_in_polygon(mid, other, eps):
                return True
        if point_strictly_in_polygon(polygon_centroid(polygon), other, eps):
            return True
    return False
