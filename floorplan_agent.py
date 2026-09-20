#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from geometry import Point, box_corners, polygon_bounds, polygon_centroid, polygon_area, segments_from_polygon
from plan_checks import all_door_zones, opening_extent, resolve_door_conflicts


@dataclass
class Room:
    name: str
    room_type: str
    x: float
    y: float
    w: float
    h: float
    polygon: List[Point]


@dataclass
class Opening:
    kind: str
    offset: float
    width: float
    room_name: str
    wall: Optional[str] = None
    edge_index: Optional[int] = None
    sill_height: float = 0.0
    head_height: float = 7.0
    swing: str = "left"


@dataclass
class Furniture:
    name: str
    x: float
    y: float
    w: float
    h: float
    room_name: str
    z: float = 0.0
    # Items sharing a group name in the same room are moved as one unit by the
    # door-aware pass (desk + chair, washer + dryer). None means a lone item.
    group: Optional[str] = None


@dataclass
class FloorPlan:
    unit_name: str
    width_ft: float
    height_ft: float
    shell: List[Point] = field(default_factory=list)
    rooms: List[Room] = field(default_factory=list)
    openings: List[Opening] = field(default_factory=list)
    furniture: List[Furniture] = field(default_factory=list)
    # Result of the last door-aware pass: {"moves": [...], "unresolved": [...]}.
    door_pass: Dict = field(default_factory=lambda: {"moves": [], "unresolved": []})


def load_layout(path: Path) -> Dict:
    if not path.exists():
        raise FileNotFoundError(f"Layout file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        try:
            layout = json.load(handle)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Layout file is not valid JSON: {path} (line {exc.lineno}, column {exc.colno})") from exc
    if not isinstance(layout, dict):
        raise ValueError(f"Layout file must contain a JSON object: {path}")
    return layout


def rectangle_polygon(x: float, y: float, w: float, h: float) -> List[Point]:
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


def wall_name_from_edge(start: Point, end: Point) -> str:
    if abs(start[1] - end[1]) < 1e-6:
        return "north" if end[0] > start[0] else "south"
    return "east" if end[1] > start[1] else "west"


def room_from_polygon(name: str, room_type: str, polygon: List[Point]) -> Room:
    x, y, w, h = polygon_bounds(polygon)
    return Room(name=name, room_type=room_type, x=x, y=y, w=w, h=h, polygon=polygon)


def build_rooms(layout: Dict) -> Tuple[str, float, float, List[Point], List[Room], List[Opening]]:
    unit_name = layout["unit_name"]
    width_ft = float(layout["width_ft"])
    height_ft = float(layout["height_ft"])
    shell = [
        (float(point[0]), float(point[1]))
        for point in layout.get("shell", {}).get(
            "points", rectangle_polygon(0.0, 0.0, width_ft, height_ft)
        )
    ]

    rooms: List[Room] = []
    if "zones" in layout:
        for room in layout["zones"]:
            polygon = [(float(point[0]), float(point[1])) for point in room["polygon"]]
            rooms.append(room_from_polygon(room["name"], room["type"], polygon))
    else:
        for room in layout["rooms"]:
            polygon = rectangle_polygon(
                float(room["x"]),
                float(room["y"]),
                float(room["w"]),
                float(room["h"]),
            )
            rooms.append(room_from_polygon(room["name"], room["type"], polygon))

    openings = [
        Opening(
            kind=str(opening["kind"]),
            offset=float(opening["offset"]),
            width=float(opening["width"]),
            room_name=str(opening["room_name"]),
            wall=str(opening["wall"]) if "wall" in opening else None,
            edge_index=int(opening["edge_index"]) if "edge_index" in opening else None,
            sill_height=float(
                opening.get("sill_height", 3.0 if str(opening["kind"]) == "window" else 0.0)
            ),
            head_height=float(opening.get("head_height", 7.0)),
            swing=str(opening.get("swing", "left")),
        )
        for opening in layout.get("openings", [])
    ]
    return unit_name, width_ft, height_ft, shell, rooms, openings


def place_bedroom(room: Room) -> List[Furniture]:
    margin = 1.0
    bed_w, bed_h = 5.0, 6.7
    bed_x = room.x + (room.w - bed_w) / 2
    bed_y = room.y + room.h - bed_h - margin
    items = [
        Furniture("Queen Bed", bed_x, bed_y, bed_w, bed_h, room.name),
    ]
    ns_w, ns_h = 2.0, 2.0
    ns_y = bed_y + bed_h - ns_h
    ns_left_x = bed_x - ns_w - 0.5
    ns_right_x = bed_x + bed_w + 0.5
    if ns_left_x >= room.x + margin:
        items.append(
            Furniture("Nightstand", ns_left_x, ns_y, ns_w, ns_h, room.name)
        )
    if ns_right_x + ns_w <= room.x + room.w - margin:
        items.append(
            Furniture("Nightstand", ns_right_x, ns_y, ns_w, ns_h, room.name)
        )
    dresser_w, dresser_h = 5.0, 1.5
    dresser_x = room.x + (room.w - dresser_w) / 2
    dresser_y = room.y + margin
    if dresser_y + dresser_h <= bed_y - 0.5:
        items.append(
            Furniture("Dresser", dresser_x, dresser_y, dresser_w, dresser_h, room.name)
        )
    return items


def place_living(room: Room) -> List[Furniture]:
    margin = 1.0
    sofa_w, sofa_h = 7.0, 3.0
    sofa_x = room.x + margin
    sofa_y = room.y + room.h / 2 - sofa_h / 2
    coffee_w, coffee_h = 1.5, 2.0
    coffee_x = sofa_x + sofa_w + 0.8
    coffee_y = sofa_y - coffee_h - 0.8
    tv_w, tv_h = 5.0, 1.5
    tv_x = room.x + room.w - tv_w - margin - 2.5
    tv_y = room.y + room.h - tv_h - margin - 1.5
    chair_w, chair_h = 3.0, 3.0
    chair_x = room.x + room.w - chair_w - margin
    chair_y = room.y + margin
    return [
        Furniture("Sofa", sofa_x, sofa_y, sofa_w, sofa_h, room.name),
        Furniture("Coffee Table", coffee_x, coffee_y, coffee_w, coffee_h, room.name),
        Furniture("TV Console", tv_x, tv_y, tv_w, tv_h, room.name),
        Furniture("Accent Chair", chair_x, chair_y, chair_w, chair_h, room.name),
    ]


def place_dining(room: Room) -> List[Furniture]:
    table_w = table_h = 4.5
    table_x = room.x + room.w / 2 - table_w / 2
    table_y = room.y + room.h / 2 - table_h / 2
    return [Furniture("Dining Table", table_x, table_y, table_w, table_h, room.name)]


def place_kitchen(room: Room) -> List[Furniture]:
    island_w, island_h = 6.0, 2.5
    island_x = room.x + room.w / 2 - island_w / 2
    island_y = room.y + room.h / 2 - island_h / 2
    stool_w, stool_h = 1.5, 1.5
    stools = [
        Furniture(
            "Bar Stool",
            island_x + i * (stool_w + 0.5),
            island_y + island_h + 0.5,
            stool_w,
            stool_h,
            room.name,
        )
        for i in range(3)
    ]
    cabinets = [
        Furniture("Kitchen Cabinet Run", room.x + 0.8, room.y + room.h - 1.5, min(7.0, room.w - 5.2), 1.0, room.name),
        Furniture("Kitchen Cabinet Run", room.x + room.w - 1.4, room.y + 2.0, 1.0, 3.0, room.name),
        Furniture("Fridge", room.x + room.w - 5.0, room.y + 2.2, 2.0, 2.0, room.name),
        Furniture("Range", room.x + 2.0, room.y + room.h - 3.4, 1.8, 1.8, room.name),
        Furniture("Sink Base", room.x + 5.0, room.y + room.h - 3.1, 2.6, 1.6, room.name),
        Furniture("Upper Cabinets", room.x + 0.8, room.y + room.h - 1.0, min(6.0, room.w - 6.0), 0.7, room.name, 4.5),
        Furniture("Upper Cabinets", room.x + room.w - 1.1, room.y + 2.4, 0.7, 2.6, room.name, 4.5),
    ]
    return [Furniture("Island", island_x, island_y, island_w, island_h, room.name)] + stools + cabinets


def place_bath(room: Room) -> List[Furniture]:
    vanity = Furniture("Bathroom Vanity", room.x + 0.8, room.y + 0.8, 2.8, 1.6, room.name)
    toilet = Furniture("Toilet", room.x + 4.8, room.y + room.h - 3.0, 1.5, 2.0, room.name)
    shower = Furniture("Shower/Tub", room.x + 0.8, room.y + room.h - 5.0, 2.6, 4.0, room.name)
    mirror = Furniture("Mirror Panel", room.x + 1.0, room.y + 1.0, 2.4, 0.3, room.name, 4.2)
    linen = Furniture("Linen Tower", room.x + 4.8, room.y + 0.8, 1.0, 2.0, room.name)
    return [vanity, toilet, shower, mirror, linen]


def place_laundry(room: Room) -> List[Furniture]:
    washer = Furniture("Washer", room.x + 0.8, room.y + 0.8, 2.6, 2.6, room.name, group="laundry-pair")
    dryer = Furniture("Dryer", room.x + 3.8, room.y + 0.8, 2.6, 2.6, room.name, group="laundry-pair")
    shelf = Furniture("Laundry Shelf", room.x + 0.8, room.y + room.h - 1.4, room.w - 1.6, 0.8, room.name)
    upper = Furniture("Wall Shelf", room.x + 0.8, room.y + room.h - 1.2, room.w - 1.6, 0.5, room.name, 5.0)
    return [washer, dryer, shelf, upper]


def place_patio(room: Room) -> List[Furniture]:
    return [
        Furniture("Outdoor Rug", room.x + 4.0, room.y + 1.0, 8.0, 4.0, room.name),
        Furniture("Patio Table", room.x + room.w / 2 - 1.1, room.y + room.h / 2 - 1.1, 2.2, 2.2, room.name),
        Furniture("Patio Chair", room.x + room.w / 2 - 3.6, room.y + room.h / 2 - 0.9, 1.6, 1.6, room.name),
        Furniture("Patio Chair", room.x + room.w / 2 + 2.0, room.y + room.h / 2 - 0.9, 1.6, 1.6, room.name),
        Furniture("Planter", room.x + 1.2, room.y + 0.8, 1.2, 1.2, room.name),
    ]


def place_office(room: Room) -> List[Furniture]:
    margin = 1.0
    desk_w, desk_h = 4.0, 2.0
    desk_x = room.x + margin
    desk_y = room.y + margin
    chair_w, chair_h = 2.0, 2.0
    chair_x = desk_x + desk_w + 0.5
    chair_y = desk_y
    return [
        Furniture("Desk", desk_x, desk_y, desk_w, desk_h, room.name, group="desk-set"),
        Furniture("Desk Chair", chair_x, chair_y, chair_w, chair_h, room.name, group="desk-set"),
    ]


def place_furniture(rooms: List[Room]) -> List[Furniture]:
    items: List[Furniture] = []
    for room in rooms:
        if room.room_type == "bedroom":
            items.extend(place_bedroom(room))
        elif room.room_type == "living":
            items.extend(place_living(room))
        elif room.room_type == "dining":
            items.extend(place_dining(room))
        elif room.room_type == "kitchen":
            items.extend(place_kitchen(room))
        elif room.room_type == "office":
            items.extend(place_office(room))
        elif room.room_type == "bath":
            items.extend(place_bath(room))
        elif room.room_type == "utility":
            items.extend(place_laundry(room))
        elif room.room_type == "outdoor":
            items.extend(place_patio(room))
    return items


def svg_rect(x: float, y: float, w: float, h: float, fill: str, stroke: str) -> str:
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="1.5" />'
    )


def svg_text(
    x: float,
    y: float,
    text: str,
    size: int = 12,
    anchor: str = "start",
    weight: str = "normal",
    fill: str = "#222",
) -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}px" fill="{fill}" '
        f'text-anchor="{anchor}" font-weight="{weight}">{text}</text>'
    )


def svg_polygon(points: List[Point], fill: str, stroke: str, dashed: bool = False) -> str:
    path = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    dash = ' stroke-dasharray="4 3"' if dashed else ""
    width = 1.0 if dashed else 1.5
    return (
        f'<polygon points="{path}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"{dash} />'
    )


def svg_path(path: str, stroke: str = "#64748b", width: float = 1.0, fill: str = "none") -> str:
    return (
        f'<path d="{path}" stroke="{stroke}" stroke-width="{width:.1f}" fill="{fill}" />'
    )


def svg_circle(cx: float, cy: float, r: float, fill: str, stroke: str) -> str:
    return (
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="1.2" />'
    )


def opening_span(room: Room, opening: Opening) -> Tuple[Point, Point, Point]:
    """(origin, far, unit direction) of an opening along its wall edge; see plan_checks.opening_extent."""
    return opening_extent(room, opening)


def opening_segment(room: Room, opening: Opening) -> Tuple[Point, Point]:
    wall_thickness = 0.25
    origin, far, (ux, uy) = opening_span(room, opening)
    px = -uy * wall_thickness / 2
    py = ux * wall_thickness / 2
    return (
        (origin[0] + px, origin[1] + py),
        (far[0] + px, far[1] + py),
        (far[0] - px, far[1] - py),
        (origin[0] - px, origin[1] - py),
    )


def to_svg_points(plan: FloorPlan, points: List[Point], scale: float, margin: float) -> List[Point]:
    return [
        (
            margin + point[0] * scale,
            margin + (plan.height_ft - point[1]) * scale,
        )
        for point in points
    ]


def svg_line(x1: float, y1: float, x2: float, y2: float, stroke: str = "#64748b", width: float = 1.0) -> str:
    return (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
        f'stroke="{stroke}" stroke-width="{width:.1f}" />'
    )


def add_opening_annotations(lines: List[str], plan: FloorPlan, scale: float, margin: float) -> None:
    room_by_name = {room.name: room for room in plan.rooms}
    for opening in plan.openings:
        room = room_by_name.get(opening.room_name)
        if room is None:
            continue
        start, end, direction = opening_span(room, opening)
        start_svg, end_svg = to_svg_points(plan, [start, end], scale, margin)
        mid_x = (start_svg[0] + end_svg[0]) / 2
        mid_y = (start_svg[1] + end_svg[1]) / 2
        if opening.kind == "door":
            centroid = polygon_centroid(room.polygon)
            hinge = start
            free = end
            closed_dir = direction
            if opening.swing == "right":
                hinge = end
                free = start
                closed_dir = (-direction[0], -direction[1])
            perp = (-closed_dir[1], closed_dir[0])
            centroid_vec = (centroid[0] - hinge[0], centroid[1] - hinge[1])
            side = 1.0 if perp[0] * centroid_vec[0] + perp[1] * centroid_vec[1] > 0 else -1.0
            open_tip = (
                hinge[0] + (-closed_dir[1] * side) * opening.width,
                hinge[1] + (closed_dir[0] * side) * opening.width,
            )
            hinge_svg, free_svg, open_svg = to_svg_points(plan, [hinge, free, open_tip], scale, margin)
            radius = opening.width * scale
            sweep = 0 if side > 0 else 1
            lines.append(svg_line(hinge_svg[0], hinge_svg[1], open_svg[0], open_svg[1], "#b45309", 1.2))
            lines.append(
                svg_path(
                    f"M {free_svg[0]:.1f} {free_svg[1]:.1f} A {radius:.1f} {radius:.1f} 0 0 {sweep} {open_svg[0]:.1f} {open_svg[1]:.1f}",
                    stroke="#f59e0b",
                    width=1.0,
                )
            )
        else:
            lines.append(svg_line(start_svg[0], start_svg[1], end_svg[0], end_svg[1], "#2563eb", 2.2))
        lines.append(svg_text(mid_x - 16, mid_y - 6, f'{opening.width:.1f} ft', 9))


def add_tag_marker(lines: List[str], x: float, y: float, label: str, fill: str, stroke: str = "#1f2937") -> None:
    radius = 12.0 if len(label) <= 3 else 15.0
    font_size = 9 if len(label) <= 3 else 7
    lines.append(svg_circle(x, y, radius, fill, stroke))
    lines.append(svg_text(x, y + 3, label, font_size, anchor="middle"))


def wrap_svg_text(text: str, max_chars: int = 44) -> List[str]:
    words = text.split()
    if not words:
        return [""]
    lines: List[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def add_wrapped_svg_text(
    lines: List[str],
    x: float,
    y: float,
    text: str,
    size: int = 10,
    max_chars: int = 44,
    line_height: float = 14.0,
    prefix: str = "",
) -> float:
    wrapped = wrap_svg_text(text, max_chars=max_chars)
    for idx, part in enumerate(wrapped):
        leader = prefix if idx == 0 else " " * len(prefix)
        lines.append(svg_text(x, y + idx * line_height, f"{leader}{part}", size))
    return y + len(wrapped) * line_height


def add_title_block(
    lines: List[str],
    x: float,
    y: float,
    width: float,
    height: float,
    title_block: Optional[Dict[str, str]],
    sheet_number: str,
    sheet_title: str,
) -> None:
    block = title_block or {}
    lines.append(svg_rect(x, y, width, height, "#ffffff", "#334155"))
    lines.append(svg_line(x, y + 34, x + width, y + 34, "#cbd5e1", 1.0))
    lines.append(svg_line(x + width * 0.58, y + 34, x + width * 0.58, y + height, "#cbd5e1", 1.0))
    lines.append(svg_line(x + width * 0.78, y + 34, x + width * 0.78, y + height, "#cbd5e1", 1.0))
    lines.append(svg_text(x + 16, y + 22, block.get("project_name", "Concept Drawing Set"), 16, weight="bold"))
    lines.append(svg_text(x + 16, y + 54, block.get("project_location", ""), 10))
    lines.append(svg_text(x + 16, y + 72, f"Unit: {block.get('unit_name', '')}", 10))
    lines.append(svg_text(x + 16, y + 90, f"Phase: {block.get('package_phase', 'Concept package')}", 10))
    lines.append(svg_text(x + width * 0.58 + 14, y + 54, "Sheet Title", 10, weight="bold"))
    lines.append(svg_text(x + width * 0.58 + 14, y + 74, sheet_title, 12))
    lines.append(svg_text(x + width * 0.58 + 14, y + 98, f"Scale: {block.get('scale_note', 'Diagrammatic')}", 10))
    lines.append(svg_text(x + width * 0.78 + 14, y + 54, "Sheet No.", 10, weight="bold"))
    lines.append(svg_text(x + width * 0.78 + 14, y + 76, sheet_number, 18, weight="bold"))
    lines.append(svg_text(x + width * 0.78 + 14, y + 98, f"Issue: {block.get('issue_date', '')}", 10))


def add_sheet_frame(lines: List[str], width_px: float, height_px: float, margin: float) -> None:
    lines.append(svg_rect(12, 12, width_px - 24, height_px - 24, "#ffffff", "#0f172a"))
    lines.append(svg_rect(margin, margin, width_px - margin * 2, height_px - margin * 2, "#ffffff", "#334155"))


def add_lineweight_legend(lines: List[str], x: float, y: float) -> float:
    lines.append(svg_text(x, y, "Graphic Legend", 13, weight="bold"))
    y += 22
    samples = [
        ("Primary outline", "#334155", 2.8),
        ("Secondary partition", "#94a3b8", 1.6),
        ("Dimensions / refs", "#64748b", 1.0),
    ]
    for label, color, width in samples:
        lines.append(svg_line(x, y - 4, x + 44, y - 4, color, width))
        lines.append(svg_text(x + 58, y, label, 10))
        y += 20
    return y


def add_symbol_legend(
    lines: List[str],
    x: float,
    y: float,
    opening_fill: str = "#fef3c7",
    cabinet_fill: str = "#dbeafe",
    note_fill: str = "#dcfce7",
) -> float:
    lines.append(svg_text(x, y, "Tag Legend", 13, weight="bold"))
    y += 24
    add_tag_marker(lines, x + 12, y - 4, "O", opening_fill)
    lines.append(svg_text(x + 34, y, "Opening tag", 10))
    y += 22
    add_tag_marker(lines, x + 12, y - 4, "C", cabinet_fill)
    lines.append(svg_text(x + 34, y, "Cabinet / built-in tag", 10))
    y += 22
    add_tag_marker(lines, x + 12, y - 4, "N", note_fill, "#166534")
    lines.append(svg_text(x + 34, y, "Keyed note reference", 10))
    y += 22
    return y


def add_extended_symbol_legend(lines: List[str], x: float, y: float) -> float:
    y = add_symbol_legend(lines, x, y)
    add_tag_marker(lines, x + 12, y - 4, "W", "#f5d0fe", "#7e22ce")
    lines.append(svg_text(x + 34, y, "Wall schedule ID", 10))
    y += 22
    add_tag_marker(lines, x + 12, y - 4, "F", "#fecaca", "#b91c1c")
    lines.append(svg_text(x + 34, y, "Room finish tag", 10))
    y += 22
    add_tag_marker(lines, x + 12, y - 4, "E", "#fde68a", "#92400e")
    lines.append(svg_text(x + 34, y, "Cabinet elevation ref", 10))
    y += 22
    return y


def add_scale_bar(lines: List[str], x: float, y: float, scale: float, length_ft: float = 4.0) -> None:
    width = length_ft * scale
    lines.append(svg_text(x, y - 10, "Scale Bar", 10, weight="bold"))
    lines.append(svg_rect(x, y, width / 2, 10, "#1f2937", "#1f2937"))
    lines.append(svg_rect(x + width / 2, y, width / 2, 10, "#ffffff", "#1f2937"))
    lines.append(svg_text(x, y + 26, "0", 9))
    lines.append(svg_text(x + width / 2 - 6, y + 26, f"{length_ft / 2:.0f} ft", 9))
    lines.append(svg_text(x + width - 10, y + 26, f"{length_ft:.0f} ft", 9))


def to_cover_sheet_svg(
    out_path: Path,
    title: str,
    subtitle: str,
    title_block: Optional[Dict[str, str]],
    sheet_entries: List[Dict[str, str]],
    highlights: Optional[List[str]] = None,
) -> None:
    width_px = 1100.0
    height_px = 850.0
    margin = 36.0
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_px:.1f}" height="{height_px:.1f}">',
        svg_rect(0, 0, width_px, height_px, "#ffffff", "#ffffff"),
    ]
    add_sheet_frame(lines, width_px, height_px, margin)
    lines.append(svg_rect(margin, margin, width_px - margin * 2, 180, "#f8fafc", "#cbd5e1"))
    lines.append(svg_text(margin + 26, margin + 60, title, 28, weight="bold"))
    lines.append(svg_text(margin + 26, margin + 92, subtitle, 14, fill="#475569"))
    lines.append(svg_text(margin + 26, margin + 132, "Drawing Set Summary", 13, weight="bold"))
    highlight_y = margin + 156
    for item in highlights or []:
        lines.append(svg_text(margin + 32, highlight_y, f"- {item}", 10))
        highlight_y += 18

    lines.append(svg_text(margin, 280, "Sheet Index", 16, weight="bold"))
    table_y = 300.0
    lines.append(svg_rect(margin, table_y, width_px - margin * 2, 320, "#ffffff", "#cbd5e1"))
    lines.append(svg_line(margin, table_y + 34, width_px - margin, table_y + 34, "#cbd5e1", 1.0))
    col_1 = margin + 110
    col_2 = margin + 340
    lines.append(svg_line(col_1, table_y, col_1, table_y + 320, "#cbd5e1", 1.0))
    lines.append(svg_line(col_2, table_y, col_2, table_y + 320, "#cbd5e1", 1.0))
    lines.append(svg_text(margin + 16, table_y + 22, "Sheet", 11, weight="bold"))
    lines.append(svg_text(col_1 + 16, table_y + 22, "Title", 11, weight="bold"))
    lines.append(svg_text(col_2 + 16, table_y + 22, "Description", 11, weight="bold"))
    row_y = table_y + 58
    for entry in sheet_entries:
        lines.append(svg_text(margin + 16, row_y, entry.get("sheet_no", ""), 11, weight="bold"))
        lines.append(svg_text(col_1 + 16, row_y, entry.get("title", ""), 11))
        row_y = add_wrapped_svg_text(lines, col_2 + 16, row_y, entry.get("description", ""), 10, max_chars=54)
        row_y += 12

    legend_y = 660.0
    legend_y = add_lineweight_legend(lines, margin, legend_y)
    add_symbol_legend(lines, margin + 250, 660.0)

    add_title_block(
        lines,
        margin,
        height_px - 132,
        width_px - margin * 2,
        96,
        title_block,
        "G001",
        "Cover Sheet",
    )
    lines.append("</svg>")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def to_notes_sheet_svg(
    out_path: Path,
    title_block: Optional[Dict[str, str]],
    general_notes: List[str],
    wall_legend: List[str],
    keyed_notes: List[Dict[str, object]],
    schedule_refs: List[Dict[str, str]],
) -> None:
    width_px = 1100.0
    height_px = 950.0
    margin = 36.0
    mid_x = width_px / 2
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_px:.1f}" height="{height_px:.1f}">',
        svg_rect(0, 0, width_px, height_px, "#ffffff", "#ffffff"),
        svg_text(margin, margin + 18, "General Notes", 16, weight="bold"),
        svg_text(mid_x + 12, margin + 18, "Keyed Notes", 16, weight="bold"),
        svg_rect(margin, margin + 30, mid_x - margin - 18, 520, "#f8fafc", "#cbd5e1"),
        svg_rect(mid_x + 12, margin + 30, width_px - mid_x - margin - 12, 520, "#f8fafc", "#cbd5e1"),
    ]
    add_sheet_frame(lines, width_px, height_px, margin)

    left_y = margin + 56
    for idx, note in enumerate(general_notes, start=1):
        left_y = add_wrapped_svg_text(lines, margin + 16, left_y, note, 10, prefix=f"{idx}. ")
        left_y += 10

    left_y += 8
    lines.append(svg_text(margin + 16, left_y, "Wall Type Legend", 13, weight="bold"))
    left_y += 22
    for entry in wall_legend:
        left_y = add_wrapped_svg_text(lines, margin + 16, left_y, entry, 10, prefix="- ")
        left_y += 8

    right_y = margin + 56
    for note in keyed_notes:
        lines.append(svg_text(mid_x + 28, right_y, str(note.get("id", "")), 11, weight="bold"))
        right_y = add_wrapped_svg_text(
            lines,
            mid_x + 72,
            right_y,
            str(note.get("note", "")),
            10,
            max_chars=44,
        )
        room_name = str(note.get("room", ""))
        lines.append(svg_text(mid_x + 72, right_y, f"Room: {room_name}", 9, fill="#475569"))
        right_y += 24

    schedule_y = margin + 582
    lines.append(svg_text(margin, schedule_y, "Schedule References", 16, weight="bold"))
    lines.append(svg_rect(margin, schedule_y + 16, width_px - margin * 2, 180, "#ffffff", "#cbd5e1"))
    schedule_y += 46
    for entry in schedule_refs:
        lines.append(svg_text(margin + 16, schedule_y, entry.get("label", ""), 11, weight="bold"))
        lines.append(svg_text(margin + 200, schedule_y, entry.get("description", ""), 10))
        schedule_y += 22

    legend_y = schedule_y + 14
    legend_y = add_lineweight_legend(lines, margin, legend_y)
    add_symbol_legend(lines, mid_x + 12, legend_y - 72)

    add_title_block(
        lines,
        margin,
        height_px - 132,
        width_px - margin * 2,
        96,
        title_block,
        "A601",
        "Notes / Legend",
    )
    lines.append("</svg>")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def to_elevation_sheet_svg(
    out_path: Path,
    title_block: Optional[Dict[str, str]],
    elevations: List[Dict[str, object]],
    sheet_number: str = "A201",
    sheet_title: str = "Interior Elevations",
) -> None:
    width_px = 1180.0
    margin = 36.0
    title_block_h = 96.0
    cols = 2
    panel_w = 520.0
    panel_h = 280.0
    gutter = 28.0
    rows = max(1, (len(elevations) + cols - 1) // cols)
    height_px = margin * 2 + rows * panel_h + max(0, rows - 1) * gutter + title_block_h + 56.0

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_px:.1f}" height="{height_px:.1f}">',
        svg_rect(0, 0, width_px, height_px, "#ffffff", "#ffffff"),
    ]
    add_sheet_frame(lines, width_px, height_px, margin)
    lines.append(svg_text(margin, margin + 18, "Interior Elevations", 18, weight="bold"))
    lines.append(svg_text(margin, margin + 40, "Cabinet and built-in references generated from E### tags on the plan sheet.", 11, fill="#475569"))

    for idx, elevation in enumerate(elevations):
        col = idx % cols
        row = idx // cols
        x = margin + col * (panel_w + gutter)
        y = margin + 70 + row * (panel_h + gutter)
        lines.append(svg_rect(x, y, panel_w, panel_h, "#ffffff", "#cbd5e1"))
        lines.append(svg_line(x, y + 34, x + panel_w, y + 34, "#cbd5e1", 1.0))
        lines.append(svg_text(x + 16, y + 22, str(elevation.get("elevation_ref", "")), 13, weight="bold"))
        lines.append(svg_text(x + 88, y + 22, f"{elevation.get('room', '')} - {elevation.get('item', '')}", 11))
        lines.append(svg_text(x + panel_w - 16, y + 22, str(elevation.get("cabinet_id", "")), 10, anchor="end", fill="#475569"))

        draw_x = x + 36
        draw_y = y + 52
        draw_w = panel_w - 72
        draw_h = 172
        floor_y = draw_y + draw_h
        wall_h_ft = 9.0
        width_ft = max(float(elevation.get("width_ft", 1.0)), 0.5)
        height_ft = max(float(elevation.get("height_ft", 2.5)), 0.5)
        mount_ft = max(float(elevation.get("mounting_height_ft", 0.0)), 0.0)
        horiz_scale = min(draw_w / max(width_ft + 2.0, 3.0), 88.0)
        vert_scale = min(draw_h / wall_h_ft, 22.0)
        object_w = width_ft * horiz_scale
        object_h = height_ft * vert_scale
        obj_x = draw_x + (draw_w - object_w) / 2.0
        obj_y = floor_y - (mount_ft * vert_scale) - object_h

        lines.append(svg_line(draw_x, floor_y, draw_x + draw_w, floor_y, "#334155", 1.6))
        lines.append(svg_line(draw_x, draw_y, draw_x, floor_y, "#94a3b8", 1.0))
        lines.append(svg_text(draw_x - 6, draw_y + 4, f"{wall_h_ft:.0f}'-0\"", 9, anchor="end", fill="#475569"))

        if mount_ft > 0.05:
            counter_y = floor_y - 3.0 * vert_scale
            lines.append(svg_path(f"M {draw_x:.1f} {counter_y:.1f} L {draw_x + draw_w:.1f} {counter_y:.1f}", "#94a3b8", 1.0))
            lines.append(svg_text(draw_x + draw_w - 2, counter_y - 6, "counter datum", 8, anchor="end", fill="#64748b"))

        lines.append(svg_rect(obj_x, obj_y, object_w, object_h, "#dbeafe", "#1d4ed8"))
        lines.append(svg_text(obj_x + object_w / 2.0, obj_y + object_h / 2.0, str(elevation.get("item", "")), 9, anchor="middle"))

        dim_y = floor_y + 22
        lines.append(svg_line(obj_x, dim_y, obj_x + object_w, dim_y, "#64748b", 1.0))
        lines.append(svg_line(obj_x, floor_y + 4, obj_x, dim_y, "#64748b", 1.0))
        lines.append(svg_line(obj_x + object_w, floor_y + 4, obj_x + object_w, dim_y, "#64748b", 1.0))
        lines.append(svg_text(obj_x + object_w / 2.0, dim_y - 6, f"{width_ft:.1f} ft", 9, anchor="middle"))

        dim_x = obj_x - 16
        lines.append(svg_line(dim_x, obj_y, dim_x, obj_y + object_h, "#64748b", 1.0))
        lines.append(svg_line(dim_x, obj_y, obj_x - 2, obj_y, "#64748b", 1.0))
        lines.append(svg_line(dim_x, obj_y + object_h, obj_x - 2, obj_y + object_h, "#64748b", 1.0))
        lines.append(svg_text(dim_x - 4, obj_y + object_h / 2.0, f"{height_ft:.1f} ft", 9, anchor="end"))

        lines.append(svg_text(x + 16, y + panel_h - 34, f"Mounting height: {mount_ft:.1f} ft", 10))
        lines.append(svg_text(x + 16, y + panel_h - 18, f"Depth reference: {float(elevation.get('depth_ft', 0.0)):.1f} ft", 10))

    add_title_block(
        lines,
        margin,
        height_px - title_block_h - margin,
        width_px - margin * 2,
        title_block_h,
        title_block,
        sheet_number,
        sheet_title,
    )
    lines.append("</svg>")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def to_room_elevation_sheet_svg(
    out_path: Path,
    title_block: Optional[Dict[str, str]],
    room_views: List[Dict[str, object]],
    sheet_number: str = "A202",
    sheet_title: str = "Grouped Interior Elevations",
) -> None:
    width_px = 1180.0
    margin = 36.0
    title_block_h = 96.0
    cols = 1
    panel_w = 1108.0
    panel_h = 300.0
    gutter = 28.0
    rows = max(1, len(room_views))
    height_px = margin * 2 + rows * panel_h + max(0, rows - 1) * gutter + title_block_h + 56.0

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_px:.1f}" height="{height_px:.1f}">',
        svg_rect(0, 0, width_px, height_px, "#ffffff", "#ffffff"),
    ]
    add_sheet_frame(lines, width_px, height_px, margin)
    lines.append(svg_text(margin, margin + 18, "Grouped Interior Elevations", 18, weight="bold"))
    lines.append(
        svg_text(
            margin,
            margin + 40,
            "Room-based elevation compositions combining cabinetry, fixtures, and major appliances.",
            11,
            fill="#475569",
        )
    )

    for idx, room_view in enumerate(room_views):
        x = margin
        y = margin + 70 + idx * (panel_h + gutter)
        lines.append(svg_rect(x, y, panel_w, panel_h, "#ffffff", "#cbd5e1"))
        lines.append(svg_line(x, y + 34, x + panel_w, y + 34, "#cbd5e1", 1.0))
        lines.append(svg_text(x + 16, y + 22, str(room_view.get("room", "")), 13, weight="bold"))
        lines.append(svg_text(x + 180, y + 22, str(room_view.get("title", "")), 11))
        lines.append(svg_text(x + panel_w - 16, y + 22, str(room_view.get("refs", "")), 10, anchor="end", fill="#475569"))
        lines.append(svg_text(x + 16, y + 48, f"Selected wall: {room_view.get('wall_label', 'concept wall')}", 10, fill="#475569"))

        draw_x = x + 34
        draw_y = y + 70
        draw_w = panel_w - 390
        draw_h = 158.0
        floor_y = draw_y + draw_h
        wall_h_ft = 9.0
        vert_scale = min(draw_h / wall_h_ft, 22.0)
        items = room_view.get("items", [])
        total_width_ft = sum(float(item.get("width_ft", 0.0)) for item in items) + max(0, len(items) - 1) * 0.35
        horiz_scale = min(draw_w / max(total_width_ft + 1.5, 6.0), 66.0)
        cursor_x = draw_x + (draw_w - total_width_ft * horiz_scale) / 2.0

        lines.append(svg_line(draw_x, floor_y, draw_x + draw_w, floor_y, "#334155", 1.6))
        lines.append(svg_line(draw_x, draw_y, draw_x, floor_y, "#94a3b8", 1.0))
        lines.append(svg_text(draw_x - 6, draw_y + 4, f"{wall_h_ft:.0f}'-0\"", 9, anchor="end", fill="#475569"))

        counter_datum_drawn = False
        for item in items:
            width_ft = max(float(item.get("width_ft", 1.0)), 0.4)
            height_ft = max(float(item.get("height_ft", 2.5)), 0.4)
            mount_ft = max(float(item.get("mounting_height_ft", 0.0)), 0.0)
            item_w = width_ft * horiz_scale
            item_h = height_ft * vert_scale
            item_x = cursor_x
            item_y = floor_y - mount_ft * vert_scale - item_h
            fill = str(item.get("fill", "#dbeafe"))
            stroke = str(item.get("stroke", "#1d4ed8"))

            if mount_ft > 0.05 and not counter_datum_drawn:
                counter_y = floor_y - 3.0 * vert_scale
                lines.append(svg_path(f"M {draw_x:.1f} {counter_y:.1f} L {draw_x + draw_w:.1f} {counter_y:.1f}", "#94a3b8", 1.0))
                lines.append(svg_text(draw_x + draw_w - 2, counter_y - 6, "counter datum", 8, anchor="end", fill="#64748b"))
                counter_datum_drawn = True

            lines.append(svg_rect(item_x, item_y, item_w, item_h, fill, stroke))
            ref = str(item.get("ref", ""))
            label = str(item.get("label", item.get("item", "")))
            if ref:
                lines.append(svg_text(item_x + item_w / 2.0, item_y - 6, ref, 8, anchor="middle", weight="bold"))
            lines.append(svg_text(item_x + item_w / 2.0, item_y + item_h / 2.0, label, 8, anchor="middle"))

            cursor_x += item_w + 0.35 * horiz_scale

        finish_x = x + panel_w - 322
        finish_y = y + 68
        lines.append(svg_text(finish_x, finish_y, "Finish Callouts", 11, weight="bold"))
        finish_y += 20
        for finish in room_view.get("finish_callouts", []):
            lines.append(svg_rect(finish_x, finish_y - 10, 12, 12, str(finish.get("color", "#e5e7eb")), "#94a3b8"))
            label = f"{finish.get('tag', '')} {finish.get('category', '')}: {finish.get('name', '')}"
            finish_y = add_wrapped_svg_text(lines, finish_x + 20, finish_y, label, 9, max_chars=34)
            finish_y += 8

        detail_x = x + panel_w - 322
        detail_y = y + 190
        lines.append(svg_text(detail_x, detail_y, "Detail Bubbles", 11, weight="bold"))
        detail_y += 22
        bubble_x = draw_x + draw_w - 28
        bubble_y = draw_y + 20
        for detail in room_view.get("detail_bubbles", []):
            add_tag_marker(lines, bubble_x, bubble_y, str(detail.get("id", "")), "#f5f3ff", "#6d28d9")
            lines.append(svg_path(f"M {bubble_x - 14:.1f} {bubble_y + 12:.1f} L {bubble_x - 54:.1f} {bubble_y + 34:.1f}", "#6d28d9", 1.0))
            detail_y = add_wrapped_svg_text(
                lines,
                detail_x,
                detail_y,
                f"{detail.get('id', '')}: {detail.get('note', '')}",
                9,
                max_chars=36,
            )
            detail_y += 8
            bubble_y += 28

        note_y = y + panel_h - 38
        lines.append(svg_text(x + 16, note_y, f"Key references: {room_view.get('refs', 'n/a')} | Details: {room_view.get('detail_refs', '')}", 10))
        lines.append(svg_text(x + 16, note_y + 18, str(room_view.get('summary', '')), 10, fill="#475569"))

    add_title_block(
        lines,
        margin,
        height_px - title_block_h - margin,
        width_px - margin * 2,
        title_block_h,
        title_block,
        sheet_number,
        sheet_title,
    )
    lines.append("</svg>")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def add_dimension_annotations(lines: List[str], plan: FloorPlan, scale: float, margin: float) -> None:
    width_y = margin + plan.height_ft * scale + 28
    lines.append(svg_line(margin, width_y, margin + plan.width_ft * scale, width_y))
    lines.append(svg_text(margin + plan.width_ft * scale / 2 - 24, width_y - 6, f'{plan.width_ft:.1f} ft', 11))

    height_x = margin - 28
    lines.append(svg_line(height_x, margin, height_x, margin + plan.height_ft * scale))
    lines.append(svg_text(height_x - 8, margin + plan.height_ft * scale / 2, f'{plan.height_ft:.1f} ft', 11))

    for room in plan.rooms:
        cx, cy = polygon_centroid(room.polygon)
        label_x, label_y = to_svg_points(plan, [(cx, cy)], scale, margin)[0]
        room_area = polygon_area(room.polygon)
        lines.append(svg_text(label_x - 30, label_y + 14, f'{room.w:.1f} x {room.h:.1f} ft', 10))
        lines.append(svg_text(label_x - 22, label_y + 28, f'{room_area:.1f} sf', 10))


def to_svg(plan: FloorPlan, out_path: Path, scale: float = 20.0, show_dimensions: bool = False) -> None:
    margin = 20.0
    extra = 60.0 if show_dimensions else 0.0
    width_px = plan.width_ft * scale + margin * 2 + extra
    height_px = plan.height_ft * scale + margin * 2 + extra
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_px:.1f}" height="{height_px:.1f}">',
        svg_rect(0, 0, width_px, height_px, "#ffffff", "#ffffff"),
    ]

    if plan.shell:
        lines.append(svg_polygon(to_svg_points(plan, plan.shell, scale, margin), "#ffffff", "#475569"))

    for room in plan.rooms:
        svg_polygon_points = to_svg_points(plan, room.polygon, scale, margin)
        lines.append(svg_polygon(svg_polygon_points, "#f8fafc", "#94a3b8"))
        label_x, label_y = to_svg_points(plan, [polygon_centroid(room.polygon)], scale, margin)[0]
        lines.append(svg_text(label_x - 22, label_y, room.name, 12))

    room_by_name = {room.name: room for room in plan.rooms}
    for opening in plan.openings:
        room = room_by_name.get(opening.room_name)
        if room is None:
            continue
        opening_points = to_svg_points(
            plan, list(opening_segment(room, opening)), scale, margin
        )
        fill = "#93c5fd" if opening.kind == "window" else "#fde68a"
        stroke = "#1d4ed8" if opening.kind == "window" else "#b45309"
        lines.append(svg_polygon(opening_points, fill, stroke))

    for zone in all_door_zones(plan):
        zone_points = to_svg_points(plan, list(box_corners(zone["box"])), scale, margin)
        lines.append(svg_polygon(zone_points, "none", "#f59e0b", dashed=True))

    for item in plan.furniture:
        svg_x = margin + item.x * scale
        svg_y = margin + (plan.height_ft - (item.y + item.h)) * scale
        svg_w = item.w * scale
        svg_h = item.h * scale
        lines.append(svg_rect(svg_x, svg_y, svg_w, svg_h, "#dbeafe", "#1d4ed8"))
        lines.append(svg_text(svg_x + 4, svg_y + 14, item.name, 10))

    if show_dimensions:
        add_dimension_annotations(lines, plan, scale, margin)
        add_opening_annotations(lines, plan, scale, margin)

    lines.append("</svg>")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def to_sheet_svg(
    plan: FloorPlan,
    out_path: Path,
    title: str,
    subtitle: str,
    general_notes: List[str],
    wall_legend: List[str],
    opening_tags: Optional[List[str]] = None,
    cabinet_tags: Optional[List[Tuple[str, Furniture]]] = None,
    wall_tags: Optional[List[Dict[str, object]]] = None,
    finish_tags: Optional[List[Dict[str, object]]] = None,
    cabinet_elevation_tags: Optional[List[Dict[str, object]]] = None,
    keyed_notes: Optional[List[Dict[str, object]]] = None,
    title_block: Optional[Dict[str, str]] = None,
    sheet_number: str = "A101",
    sheet_title: str = "Concept Plan / Tags",
    scale: float = 14.0,
) -> None:
    margin = 28.0
    sidebar_w = 360.0
    title_block_h = 110.0
    width_px = plan.width_ft * scale + margin * 2 + sidebar_w
    height_px = max(plan.height_ft * scale + margin * 2 + title_block_h + 110.0, 920.0)
    plan_right = margin + plan.width_ft * scale
    sidebar_x = plan_right + 24.0

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_px:.1f}" height="{height_px:.1f}">',
        svg_rect(0, 0, width_px, height_px, "#ffffff", "#ffffff"),
        svg_rect(sidebar_x, margin, sidebar_w - margin, height_px - margin * 2, "#f8fafc", "#cbd5e1"),
    ]
    add_sheet_frame(lines, width_px, height_px, margin)

    if plan.shell:
        lines.append(svg_polygon(to_svg_points(plan, plan.shell, scale, margin), "#ffffff", "#334155"))

    for room in plan.rooms:
        svg_polygon_points = to_svg_points(plan, room.polygon, scale, margin)
        lines.append(svg_polygon(svg_polygon_points, "#f8fafc", "#94a3b8"))
        label_x, label_y = to_svg_points(plan, [polygon_centroid(room.polygon)], scale, margin)[0]
        lines.append(svg_text(label_x - 22, label_y, room.name, 11, weight="bold"))

    room_by_name = {room.name: room for room in plan.rooms}
    for opening_idx, opening in enumerate(plan.openings):
        room = room_by_name.get(opening.room_name)
        if room is None:
            continue
        opening_points = to_svg_points(plan, list(opening_segment(room, opening)), scale, margin)
        fill = "#bfdbfe" if opening.kind == "window" else "#fde68a"
        stroke = "#2563eb" if opening.kind == "window" else "#b45309"
        lines.append(svg_polygon(opening_points, fill, stroke))

    for zone in all_door_zones(plan):
        zone_points = to_svg_points(plan, list(box_corners(zone["box"])), scale, margin)
        lines.append(svg_polygon(zone_points, "none", "#f59e0b", dashed=True))

    for item in plan.furniture:
        svg_x = margin + item.x * scale
        svg_y = margin + (plan.height_ft - (item.y + item.h)) * scale
        svg_w = item.w * scale
        svg_h = item.h * scale
        lines.append(svg_rect(svg_x, svg_y, svg_w, svg_h, "#dbeafe", "#1d4ed8"))

    add_dimension_annotations(lines, plan, scale, margin)
    add_opening_annotations(lines, plan, scale, margin)

    if opening_tags:
        for opening, label in zip(plan.openings, opening_tags):
            room = room_by_name.get(opening.room_name)
            if room is None:
                continue
            start, end, _ = opening_span(room, opening)
            start_svg, end_svg = to_svg_points(plan, [start, end], scale, margin)
            mid_x = (start_svg[0] + end_svg[0]) / 2
            mid_y = (start_svg[1] + end_svg[1]) / 2 - 18
            add_tag_marker(lines, mid_x, mid_y, label, "#fef3c7")

    if cabinet_tags:
        for label, item in cabinet_tags:
            center = (item.x + item.w / 2, item.y + item.h / 2)
            cx, cy = to_svg_points(plan, [center], scale, margin)[0]
            add_tag_marker(lines, cx, cy, label, "#dbeafe")

    if wall_tags:
        for tag in wall_tags:
            point = tag.get("point")
            if not isinstance(point, (list, tuple)) or len(point) != 2:
                continue
            wx, wy = to_svg_points(plan, [(float(point[0]), float(point[1]))], scale, margin)[0]
            add_tag_marker(lines, wx, wy, str(tag.get("id", "")), "#f5d0fe", "#7e22ce")

    if finish_tags:
        for tag in finish_tags:
            point = tag.get("point")
            if not isinstance(point, (list, tuple)) or len(point) != 2:
                continue
            fx, fy = to_svg_points(plan, [(float(point[0]), float(point[1]))], scale, margin)[0]
            add_tag_marker(lines, fx, fy, str(tag.get("id", "")), "#fecaca", "#b91c1c")

    if cabinet_elevation_tags:
        for tag in cabinet_elevation_tags:
            point = tag.get("point")
            if not isinstance(point, (list, tuple)) or len(point) != 2:
                continue
            ex, ey = to_svg_points(plan, [(float(point[0]), float(point[1]))], scale, margin)[0]
            add_tag_marker(lines, ex, ey, str(tag.get("id", "")), "#fde68a", "#92400e")

    if keyed_notes:
        for note in keyed_notes:
            point = note.get("point")
            if not isinstance(point, (list, tuple)) or len(point) != 2:
                continue
            nx, ny = to_svg_points(plan, [(float(point[0]), float(point[1]))], scale, margin)[0]
            add_tag_marker(lines, nx, ny, str(note.get("id", "")), "#dcfce7", "#166534")

    lines.append(svg_text(sidebar_x + 18, margin + 28, title, 18, weight="bold"))
    lines.append(svg_text(sidebar_x + 18, margin + 50, subtitle, 11, fill="#475569"))
    note_y = margin + 84
    if keyed_notes:
        lines.append(svg_text(sidebar_x + 18, note_y, "Keyed Notes", 13, weight="bold"))
        note_y += 24
        for note in keyed_notes:
            lines.append(svg_text(sidebar_x + 24, note_y, str(note.get("id", "")), 10, weight="bold"))
            note_y = add_wrapped_svg_text(
                lines,
                sidebar_x + 58,
                note_y,
                str(note.get("note", "")),
                10,
                max_chars=32,
            )
            note_y += 10

    lines.append(svg_text(sidebar_x + 18, note_y, "General Notes", 13, weight="bold"))
    note_y += 24
    for note in general_notes:
        note_y = add_wrapped_svg_text(lines, sidebar_x + 24, note_y, note, 10, max_chars=34, prefix="- ")
        note_y += 8

    legend_y = note_y + 18
    lines.append(svg_text(sidebar_x + 18, legend_y, "Wall Type Legend", 13, weight="bold"))
    legend_y += 24
    for entry in wall_legend:
        legend_y = add_wrapped_svg_text(lines, sidebar_x + 24, legend_y, entry, 10, max_chars=34, prefix="- ")
        legend_y += 8

    symbol_y = legend_y + 18
    symbol_y = add_extended_symbol_legend(lines, sidebar_x + 18, symbol_y)
    add_lineweight_legend(lines, sidebar_x + 18, symbol_y + 10)
    add_scale_bar(lines, margin + 18, height_px - title_block_h - margin - 44, scale)

    add_title_block(
        lines,
        margin,
        height_px - title_block_h - margin,
        width_px - margin * 2,
        title_block_h,
        title_block,
        sheet_number,
        sheet_title,
    )

    lines.append("</svg>")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def build_plan(layout_path: Path) -> FloorPlan:
    layout = load_layout(layout_path)
    unit_name, width_ft, height_ft, shell, rooms, openings = build_rooms(layout)
    furniture = place_furniture(rooms)
    plan = FloorPlan(unit_name, width_ft, height_ft, shell, rooms, openings, furniture)
    # Rule-based placement ignores doors; slide anything that landed in a swing or
    # approach zone, groups as one unit. Unresolvable items/groups stay put and are
    # reported by analyze_plan.
    plan.door_pass = resolve_door_conflicts(plan)
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a furnished floor plan SVG using rule-based placement."
    )
    parser.add_argument(
        "--layout",
        default="mercer_layout.json",
        help="Path to layout JSON file.",
    )
    parser.add_argument(
        "--out",
        default="mercer_floorplan.svg",
        help="Output SVG path.",
    )
    args = parser.parse_args()

    layout_path = Path(args.layout)
    out_path = Path(args.out)
    plan = build_plan(layout_path)
    to_svg(plan, out_path)
    print(f"Wrote {out_path} for {plan.unit_name}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
