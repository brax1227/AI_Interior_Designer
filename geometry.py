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
