#!/usr/bin/env python3
"""Deterministic layout validity checks and a door-aware furniture resolution pass.

Everything here works on the plain plan objects from floorplan_agent (rooms with a
polygon, openings on polygon edges, axis-aligned furniture boxes) and reports
practical space-planning conflicts. It is a concept-plan sanity layer, not a
building-code or structural check.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from geometry import (
    Box,
    Point,
    box_within_polygon,
    boxes_intersect,
    point_in_polygon,
    polygon_within_polygon,
    polygons_overlap,
    segments_from_polygon,
)

FLOOR_LEVEL_MAX_Z = 0.1
SOFT_SURFACE_NAMES = {"Outdoor Rug"}
# Clear depth required on the non-swing side of a door so it can be approached.
DOOR_APPROACH_DEPTH_FT = 3.0
_EPS = 1e-6


def is_floor_item(item) -> bool:
    return item.z <= FLOOR_LEVEL_MAX_Z and item.name not in SOFT_SURFACE_NAMES


def furniture_box(item) -> Box:
    return (item.x, item.y, item.x + item.w, item.y + item.h)


def opening_line(room, opening) -> Tuple[Point, Point, Point, float]:
    """Return (start, end, unit_direction, wall_length) for the opening's wall edge.

    Prefers `edge_index` on the room polygon; falls back to the bounding-box wall name.
    """
    edges = segments_from_polygon(room.polygon)
    if opening.edge_index is not None and 0 <= opening.edge_index < len(edges):
        start, end = edges[opening.edge_index]
    elif opening.wall == "north":
        start, end = (room.x, room.y + room.h), (room.x + room.w, room.y + room.h)
    elif opening.wall == "south":
        start, end = (room.x, room.y), (room.x + room.w, room.y)
    elif opening.wall == "east":
        start, end = (room.x + room.w, room.y), (room.x + room.w, room.y + room.h)
    else:
        start, end = (room.x, room.y + room.h), (room.x, room.y)
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = (dx * dx + dy * dy) ** 0.5
    if length < _EPS:
        return start, end, (1.0, 0.0), 0.0
    return start, end, (dx / length, dy / length), length


def opening_extent(room, opening) -> Tuple[Point, Point, Point]:
    """Return (origin, far, unit_direction) of the opening along its wall edge (unclamped)."""
    start, _end, (ux, uy), _length = opening_line(room, opening)
    origin = (start[0] + ux * opening.offset, start[1] + uy * opening.offset)
    far = (origin[0] + ux * opening.width, origin[1] + uy * opening.width)
    return origin, far, (ux, uy)


def opening_overrun(room, opening) -> float:
    """Feet by which the opening runs past either end of its wall edge (0.0 when it fits)."""
    _start, _end, _direction, length = opening_line(room, opening)
    before = max(0.0, -opening.offset)
    after = max(0.0, opening.offset + opening.width - length)
    return round(before + after, 6)


def find_opening_overruns(plan) -> List[Dict[str, object]]:
    room_by_name = {room.name: room for room in plan.rooms}
    problems: List[Dict[str, object]] = []
    for index, opening in enumerate(plan.openings):
        room = room_by_name.get(opening.room_name)
        if room is None:
            problems.append({"index": index, "room": opening.room_name, "kind": opening.kind, "message": "references an unknown room"})
            continue
        overrun = opening_overrun(room, opening)
        if overrun > _EPS:
            _s, _e, _d, length = opening_line(room, opening)
            problems.append(
                {
                    "index": index,
                    "room": room.name,
                    "kind": opening.kind,
                    "overrun_ft": overrun,
                    "wall_length_ft": round(length, 3),
                    "message": (
                        f"{opening.kind} (offset {opening.offset} ft, width {opening.width} ft) runs "
                        f"{overrun:.2f} ft past its {length:.1f} ft wall edge"
                    ),
                }
            )
    return problems


def _room_containing(point: Point, rooms: Sequence) -> Optional[object]:
    for room in rooms:
        if point_in_polygon(point, room.polygon):
            return room
    return None


def door_clearance_zones(room, opening, rooms: Sequence) -> List[Dict[str, object]]:
    """Clearance boxes a door needs: a swing square inside its room and an approach strip beyond.

    Both are axis-aligned bounding boxes of the actual zone so diagonal walls are
    handled conservatively. Zones that fall outside every room (exterior side of an
    entry door) are dropped.
    """
    if opening.kind != "door":
        return []
    origin, far, (ux, uy) = opening_extent(room, opening)
    mid = ((origin[0] + far[0]) / 2, (origin[1] + far[1]) / 2)
    zones: List[Dict[str, object]] = []
    for sign in (1.0, -1.0):
        nx, ny = -uy * sign, ux * sign
        probe = (mid[0] + nx * 0.3, mid[1] + ny * 0.3)
        inside_owner = point_in_polygon(probe, room.polygon)
        if inside_owner:
            depth = opening.width
            side = "swing"
            zone_room = room
        else:
            zone_room = _room_containing(probe, [other for other in rooms if other is not room])
            if zone_room is None:
                continue
            depth = min(DOOR_APPROACH_DEPTH_FT, opening.width)
            side = "approach"
        corners = [origin, far, (far[0] + nx * depth, far[1] + ny * depth), (origin[0] + nx * depth, origin[1] + ny * depth)]
        xs = [corner[0] for corner in corners]
        ys = [corner[1] for corner in corners]
        zones.append(
            {
                "box": (min(xs), min(ys), max(xs), max(ys)),
                "side": side,
                "room": zone_room.name,
                "normal": (nx, ny),
                "tangent": (ux, uy),
            }
        )
    return zones


def all_door_zones(plan) -> List[Dict[str, object]]:
    room_by_name = {room.name: room for room in plan.rooms}
    zones: List[Dict[str, object]] = []
    for index, opening in enumerate(plan.openings):
        room = room_by_name.get(opening.room_name)
        if room is None:
            continue
        for zone in door_clearance_zones(room, opening, plan.rooms):
            zone = dict(zone)
            zone["opening_index"] = index
            zone["door_room"] = room.name
            zone["width"] = opening.width
            zones.append(zone)
    return zones


def find_door_conflicts(plan) -> List[Dict[str, object]]:
    """Floor-level furniture that sits in a door's swing or approach clearance."""
    conflicts: List[Dict[str, object]] = []
    for zone in all_door_zones(plan):
        for item in plan.furniture:
            if not is_floor_item(item):
                continue
            if boxes_intersect(zone["box"], furniture_box(item)):
                conflicts.append(
                    {
                        "opening_index": zone["opening_index"],
                        "door_room": zone["door_room"],
                        "side": zone["side"],
                        "zone_room": zone["room"],
                        "item": item.name,
                        "item_room": item.room_name,
                        "message": (
                            f"{item.name} ({item.room_name}) blocks the {zone['side']} clearance of the "
                            f"{zone['door_room']} door"
                        ),
                    }
                )
    return conflicts


def find_zone_shell_violations(plan) -> List[Dict[str, object]]:
    if not plan.shell:
        return []
    return [
        {"room": room.name, "message": f"{room.name} zone extends outside the unit shell"}
        for room in plan.rooms
        if not polygon_within_polygon(room.polygon, plan.shell)
    ]


def find_zone_overlaps(plan) -> List[Dict[str, object]]:
    overlaps: List[Dict[str, object]] = []
    rooms = list(plan.rooms)
    for index, first in enumerate(rooms):
        for second in rooms[index + 1 :]:
            if polygons_overlap(first.polygon, second.polygon):
                overlaps.append(
                    {"rooms": [first.name, second.name], "message": f"{first.name} and {second.name} zones overlap"}
                )
    return overlaps


def find_furniture_outside_room(plan) -> List[Dict[str, object]]:
    room_by_name = {room.name: room for room in plan.rooms}
    problems: List[Dict[str, object]] = []
    for item in plan.furniture:
        room = room_by_name.get(item.room_name)
        if room is None or not box_within_polygon(furniture_box(item), room.polygon):
            problems.append({"room": item.room_name, "item": item.name, "message": f"{item.name} extends beyond room bounds."})
    return problems


def _placement_is_valid(candidate: Box, item, plan, room, zones: Sequence[Dict[str, object]]) -> bool:
    if not box_within_polygon(candidate, room.polygon):
        return False
    for zone in zones:
        if boxes_intersect(zone["box"], candidate):
            return False
    for other in plan.furniture:
        if other is item or not is_floor_item(other):
            continue
        if boxes_intersect(candidate, furniture_box(other)):
            return False
    return True


def resolve_door_conflicts(plan, step: float = 0.25, max_shift: float = 4.0) -> List[Dict[str, object]]:
    """Slide floor-level furniture out of door clearance zones.

    For each conflicting item, try the door's normal and both tangent directions and
    keep the shortest shift that lands inside the room polygon, clear of every door
    zone and of every other floor-level item. Items that cannot be resolved are left
    in place and returned so the analysis report can flag them. Deterministic: order
    follows plan.openings then plan.furniture.
    """
    room_by_name = {room.name: room for room in plan.rooms}
    zones = all_door_zones(plan)
    moves: List[Dict[str, object]] = []
    for zone in zones:
        for item in plan.furniture:
            if not is_floor_item(item) or not boxes_intersect(zone["box"], furniture_box(item)):
                continue
            room = room_by_name.get(item.room_name)
            if room is None:
                continue
            nx, ny = zone["normal"]
            ux, uy = zone["tangent"]
            best: Optional[Tuple[float, float, float]] = None
            for dx, dy in ((nx, ny), (ux, uy), (-ux, -uy)):
                distance = step
                while distance <= max_shift + _EPS:
                    candidate = (
                        item.x + dx * distance,
                        item.y + dy * distance,
                        item.x + item.w + dx * distance,
                        item.y + item.h + dy * distance,
                    )
                    if _placement_is_valid(candidate, item, plan, room, zones):
                        if best is None or distance < best[0]:
                            best = (distance, dx * distance, dy * distance)
                        break
                    distance += step
            if best is None:
                continue
            _distance, shift_x, shift_y = best
            moves.append(
                {
                    "item": item.name,
                    "room": item.room_name,
                    "from": (round(item.x, 3), round(item.y, 3)),
                    "to": (round(item.x + shift_x, 3), round(item.y + shift_y, 3)),
                    "door_room": zone["door_room"],
                }
            )
            item.x = round(item.x + shift_x, 6)
            item.y = round(item.y + shift_y, 6)
    return moves
