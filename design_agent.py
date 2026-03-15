#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import date
from pathlib import Path
import re
from typing import Dict, Iterable, List, Optional, Tuple

from floorplan_agent import (
    FloorPlan,
    Furniture,
    Opening,
    Room,
    build_plan,
    to_cover_sheet_svg,
    to_elevation_sheet_svg,
    to_notes_sheet_svg,
    to_room_elevation_sheet_svg,
    to_sheet_svg,
    to_svg,
)
from geometry import canonical_segment, point_in_polygon, polygon_area, polygon_centroid, segment_length, segments_from_polygon


FURNITURE_HEIGHTS_FT = {
    "Queen Bed": 2.0,
    "Nightstand": 2.0,
    "Dresser": 3.0,
    "Sofa": 3.0,
    "Coffee Table": 1.5,
    "TV Console": 2.0,
    "Accent Chair": 3.0,
    "Dining Table": 2.5,
    "Island": 3.0,
    "Bar Stool": 2.5,
    "Desk": 2.5,
    "Desk Chair": 3.0,
    "Kitchen Cabinet Run": 3.0,
    "Fridge": 6.0,
    "Range": 3.0,
    "Bathroom Vanity": 3.0,
    "Toilet": 2.5,
    "Shower/Tub": 4.5,
    "Washer": 3.2,
    "Dryer": 3.2,
    "Laundry Shelf": 1.2,
    "Outdoor Rug": 0.1,
    "Patio Table": 2.5,
    "Patio Chair": 2.8,
    "Sink Base": 3.0,
    "Upper Cabinets": 2.2,
    "Mirror Panel": 2.5,
    "Linen Tower": 6.0,
    "Wall Shelf": 0.6,
    "Planter": 2.0,
}

DEFAULT_PALETTE = ["#f5f1ea", "#e5e7eb", "#1f2937", "#0ea5e9"]
PALETTES_BY_PREFERENCE = {
    "warm neutrals": ["#f5efe6", "#ddd2c1", "#8d6e63", "#c08457"],
    "earthy": ["#efe7dc", "#c9b79c", "#556b2f", "#8c5a3c"],
    "bold": ["#f5f5f5", "#d1d5db", "#111827", "#c1121f"],
    "moody": ["#1f2937", "#374151", "#d1d5db", "#7c3aed"],
    "coastal": ["#f0f9ff", "#bae6fd", "#0f766e", "#38bdf8"],
    "dark neutrals": ["#e8dfd2", "#b6ab9f", "#2f3a34", "#6b4f3a"],
    "forest": ["#ece7dd", "#c8beb0", "#31473a", "#72553d"],
}
PRICE_MULTIPLIERS = {"low": 0.75, "mid": 1.0, "high": 1.45}

SHOPPING_DEFAULTS = {
    "Queen Bed": ("Bedroom", "bed", (500, 1800)),
    "Nightstand": ("Bedroom", "side_table", (80, 300)),
    "Dresser": ("Bedroom", "dresser", (250, 900)),
    "Sofa": ("Living Room", "sofa", (700, 2500)),
    "Coffee Table": ("Living Room", "coffee_table", (120, 600)),
    "TV Console": ("Living Room", "tv_console", (150, 700)),
    "Accent Chair": ("Living Room", "accent_chair", (150, 800)),
    "Dining Table": ("Dining", "dining_table", (300, 1400)),
    "Island": ("Kitchen", "kitchen_island", (0, 0)),
    "Bar Stool": ("Kitchen", "bar_stool", (60, 250)),
    "Desk": ("Office/Den", "desk", (150, 800)),
    "Desk Chair": ("Office/Den", "desk_chair", (120, 500)),
    "Bookcase": ("Office/Den", "storage", (120, 650)),
    "Storage Bench": ("Closet/Hall", "storage", (140, 500)),
    "Floor Lamp": ("Living Room", "lighting", (60, 260)),
    "Table Lamp": ("Bedroom", "lighting", (40, 180)),
    "Dog Bed": ("Living Room", "pet", (50, 180)),
    "Cat Tree": ("Living Room", "pet", (70, 220)),
    "Reading Chair": ("Office/Den", "accent_chair", (180, 900)),
    "Side Table": ("Office/Den", "side_table", (60, 220)),
    "Kitchen Cabinet Run": ("Kitchen", "cabinetry", (1200, 4500)),
    "Fridge": ("Kitchen", "appliance", (900, 2600)),
    "Range": ("Kitchen", "appliance", (700, 2200)),
    "Bathroom Vanity": ("Bathroom", "vanity", (500, 2200)),
    "Toilet": ("Bathroom", "plumbing_fixture", (200, 700)),
    "Shower/Tub": ("Bathroom", "plumbing_fixture", (900, 3200)),
    "Washer": ("Laundry", "appliance", (500, 1400)),
    "Dryer": ("Laundry", "appliance", (500, 1400)),
    "Laundry Shelf": ("Laundry", "storage", (80, 300)),
    "Outdoor Rug": ("Patio", "outdoor", (120, 400)),
    "Patio Table": ("Patio", "outdoor", (180, 700)),
    "Patio Chair": ("Patio", "outdoor", (90, 300)),
    "Sink Base": ("Kitchen", "cabinetry", (600, 1800)),
    "Upper Cabinets": ("Kitchen", "cabinetry", (500, 2200)),
    "Mirror Panel": ("Bathroom", "mirror", (180, 700)),
    "Linen Tower": ("Bathroom", "storage", (350, 1400)),
    "Wall Shelf": ("Laundry", "storage", (80, 260)),
    "Planter": ("Patio", "outdoor", (60, 180)),
}
FURNITURE_CLEARANCE_FT = {
    "Queen Bed": 2.5,
    "Nightstand": 1.0,
    "Dresser": 2.5,
    "Sofa": 2.5,
    "Coffee Table": 1.8,
    "TV Console": 2.0,
    "Accent Chair": 2.0,
    "Dining Table": 3.0,
    "Island": 3.0,
    "Bar Stool": 1.8,
    "Desk": 2.5,
    "Desk Chair": 2.5,
    "Bookcase": 2.0,
    "Storage Bench": 2.0,
    "Floor Lamp": 1.0,
    "Table Lamp": 1.0,
    "Dog Bed": 1.5,
    "Cat Tree": 1.5,
    "Reading Chair": 2.0,
    "Side Table": 1.0,
    "Kitchen Cabinet Run": 2.5,
    "Fridge": 3.0,
    "Range": 3.0,
    "Bathroom Vanity": 2.5,
    "Toilet": 2.0,
    "Shower/Tub": 2.0,
    "Washer": 2.0,
    "Dryer": 2.0,
    "Laundry Shelf": 1.0,
    "Outdoor Rug": 0.5,
    "Patio Table": 2.5,
    "Patio Chair": 1.5,
    "Sink Base": 2.5,
    "Upper Cabinets": 0.5,
    "Mirror Panel": 0.2,
    "Linen Tower": 1.5,
    "Wall Shelf": 0.2,
    "Planter": 0.8,
}

SPEC_LIBRARY = {
    "Kitchen Cabinet Run": {"trade": "millwork", "finish": "painted shaker cabinetry", "unit": "lf", "budget_low": 180, "budget_high": 420},
    "Upper Cabinets": {"trade": "millwork", "finish": "painted upper cabinetry", "unit": "lf", "budget_low": 140, "budget_high": 320},
    "Island": {"trade": "millwork", "finish": "island cabinetry with quartz top", "unit": "ea", "budget_low": 2200, "budget_high": 6500},
    "Sink Base": {"trade": "plumbing/millwork", "finish": "sink base cabinet with quartz top", "unit": "ea", "budget_low": 900, "budget_high": 2600},
    "Fridge": {"trade": "appliance", "finish": "panel-ready or stainless refrigerator", "unit": "ea", "budget_low": 900, "budget_high": 2600},
    "Range": {"trade": "appliance", "finish": "slide-in range", "unit": "ea", "budget_low": 700, "budget_high": 2200},
    "Bathroom Vanity": {"trade": "plumbing/millwork", "finish": "custom or semi-custom vanity", "unit": "ea", "budget_low": 900, "budget_high": 3200},
    "Mirror Panel": {"trade": "finish carpentry", "finish": "framed vanity mirror", "unit": "ea", "budget_low": 180, "budget_high": 700},
    "Shower/Tub": {"trade": "tile/plumbing", "finish": "tiled tub-shower surround", "unit": "ea", "budget_low": 1800, "budget_high": 6400},
    "Toilet": {"trade": "plumbing", "finish": "elongated comfort-height toilet", "unit": "ea", "budget_low": 220, "budget_high": 800},
    "Linen Tower": {"trade": "millwork", "finish": "tall linen storage", "unit": "ea", "budget_low": 350, "budget_high": 1400},
    "Washer": {"trade": "appliance", "finish": "front-load washer", "unit": "ea", "budget_low": 500, "budget_high": 1400},
    "Dryer": {"trade": "appliance", "finish": "front-load dryer", "unit": "ea", "budget_low": 500, "budget_high": 1400},
    "Laundry Shelf": {"trade": "millwork", "finish": "painted utility shelf", "unit": "ea", "budget_low": 80, "budget_high": 300},
    "Wall Shelf": {"trade": "millwork", "finish": "wall-mounted storage shelf", "unit": "ea", "budget_low": 80, "budget_high": 260},
}

ARCHITECTURAL_FINISH_LIBRARY = {
    "walls": "eggshell paint finish",
    "trim": "semi-gloss painted trim and baseboard",
    "frame": "painted window and door frame package",
    "glass": "clear insulated glazing",
    "stone": "quartz or stone-look slab",
}


def prompt_questions() -> Dict:
    print("Answer a few design questions (press Enter to accept defaults).")
    answers = {}
    answers["style_keywords"] = input(
        "Style keywords (e.g., modern, cozy, japandi) [modern cozy]: "
    ).strip() or "modern cozy"
    answers["palette_preference"] = input(
        "Color vibe (e.g., warm neutrals, bold, earthy) [warm neutrals]: "
    ).strip() or "warm neutrals"
    answers["budget_level"] = input("Budget (low, mid, high) [mid]: ").strip() or "mid"
    answers["work_from_home"] = (
        input("Need dedicated work-from-home space? (yes/no) [yes]: ").strip() or "yes"
    )
    answers["pets"] = input("Pets? (none/cat/dog) [none]: ").strip() or "none"
    answers["lighting_pref"] = input(
        "Lighting vibe (bright, soft, mixed) [mixed]: "
    ).strip() or "mixed"
    answers["storage_priority"] = input(
        "Storage priority (low/medium/high) [medium]: "
    ).strip() or "medium"
    answers["must_have"] = input(
        "Must-have items (comma separated) [none]: "
    ).strip() or "none"
    return answers


def load_answers(path: Optional[Path]) -> Dict:
    if not path:
        return prompt_questions()
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _average_rgb(pixels: Iterable[Tuple[int, int, int]]) -> Tuple[int, int, int]:
    total = [0, 0, 0]
    count = 0
    for r, g, b in pixels:
        total[0] += r
        total[1] += g
        total[2] += b
        count += 1
    if count == 0:
        return (245, 241, 234)
    return (total[0] // count, total[1] // count, total[2] // count)


def infer_palette_from_images(paths: List[Path]) -> Optional[List[str]]:
    if not paths:
        return None
    try:
        from PIL import Image  # type: ignore
    except Exception:
        print("Pillow not installed; skipping style image analysis.")
        return None

    palette = []
    for path in paths:
        try:
            with Image.open(path) as img:
                img = img.convert("RGB").resize((64, 64))
                avg = _average_rgb(list(img.getdata()))
                palette.append("#%02x%02x%02x" % avg)
        except Exception:
            continue
    return palette or None


def normalize_answers(answers: Dict) -> Dict[str, str]:
    normalized = {
        "style_keywords": str(answers.get("style_keywords", "modern cozy")).strip()
        or "modern cozy",
        "palette_preference": str(
            answers.get("palette_preference", "warm neutrals")
        ).strip()
        or "warm neutrals",
        "budget_level": str(answers.get("budget_level", "mid")).strip().lower() or "mid",
        "work_from_home": str(answers.get("work_from_home", "yes")).strip().lower()
        or "yes",
        "pets": str(answers.get("pets", "none")).strip().lower() or "none",
        "lighting_pref": str(answers.get("lighting_pref", "mixed")).strip().lower()
        or "mixed",
        "storage_priority": str(
            answers.get("storage_priority", "medium")
        ).strip().lower()
        or "medium",
        "must_have": str(answers.get("must_have", "none")).strip() or "none",
    }
    if normalized["budget_level"] not in PRICE_MULTIPLIERS:
        normalized["budget_level"] = "mid"
    if normalized["work_from_home"] not in {"yes", "no"}:
        normalized["work_from_home"] = "yes"
    if normalized["pets"] not in {"none", "cat", "dog"}:
        normalized["pets"] = "none"
    if normalized["lighting_pref"] not in {"bright", "soft", "mixed"}:
        normalized["lighting_pref"] = "mixed"
    if normalized["storage_priority"] not in {"low", "medium", "high"}:
        normalized["storage_priority"] = "medium"
    return normalized


def ensure_palette(colors: Optional[List[str]], preference: str) -> List[str]:
    matched = None
    pref = preference.lower().strip()
    for key, palette in PALETTES_BY_PREFERENCE.items():
        if pref == key or key in pref or pref in key:
            matched = palette
            break
    base = list(colors or matched or DEFAULT_PALETTE)
    fallback = matched or DEFAULT_PALETTE
    while len(base) < 4:
        base.append(fallback[len(base) % len(fallback)])
    return base[:4]


def validate_plan(plan: FloorPlan) -> None:
    if plan.width_ft <= 0 or plan.height_ft <= 0:
        raise ValueError("Layout width and height must be positive.")
    if not plan.rooms:
        raise ValueError("Layout must contain at least one room.")
    for room in plan.rooms:
        if room.w <= 0 or room.h <= 0:
            raise ValueError(f"Room '{room.name}' must have positive dimensions.")
        if room.x < 0 or room.y < 0:
            raise ValueError(f"Room '{room.name}' cannot start at a negative position.")
        if room.x + room.w > plan.width_ft or room.y + room.h > plan.height_ft:
            raise ValueError(
                f"Room '{room.name}' extends beyond the unit bounds."
            )


def hex_to_rgb(hex_color: str) -> Tuple[float, float, float]:
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0
    return r, g, b


def tint_color(hex_color: str, factor: float) -> str:
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    r = int(r + (255 - r) * factor)
    g = int(g + (255 - g) * factor)
    b = int(b + (255 - b) * factor)
    return f"#{r:02x}{g:02x}{b:02x}"


def darken_color(hex_color: str, factor: float) -> str:
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    r = int(r * (1 - factor))
    g = int(g * (1 - factor))
    b = int(b * (1 - factor))
    return f"#{r:02x}{g:02x}{b:02x}"


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def room_floor_color(room_type: str, palette: List[str]) -> str:
    if room_type in {"kitchen", "bath", "utility"}:
        return tint_color(palette[1], 0.35)
    if room_type == "outdoor":
        return tint_color(palette[3], 0.25)
    return tint_color(palette[3], 0.15)


def furniture_material_name(item_name: str) -> str:
    if item_name in {"Kitchen Cabinet Run", "Island", "Bathroom Vanity", "Laundry Shelf", "Sink Base", "Upper Cabinets", "Linen Tower", "Wall Shelf"}:
        return "cabinetry"
    if item_name in {"Fridge", "Range", "Washer", "Dryer"}:
        return "appliance"
    if item_name in {"Toilet", "Shower/Tub", "Mirror Panel"}:
        return "plumbing"
    if item_name in {"Sofa", "Accent Chair", "Reading Chair", "Patio Chair"}:
        return "upholstery"
    if item_name in {"Outdoor Rug", "Patio Table", "Planter"}:
        return "outdoor"
    if item_name in {
        "Queen Bed",
        "Nightstand",
        "Dresser",
        "Desk",
        "TV Console",
        "Coffee Table",
        "Dining Table",
        "Bookcase",
        "Storage Bench",
        "Side Table",
    }:
        return "wood"
    return "accent"


def find_room(plan: FloorPlan, room_type: str) -> Optional[object]:
    for room in plan.rooms:
        if room.room_type == room_type:
            return room
    return None


def furniture_exists(plan: FloorPlan, name: str, room_name: Optional[str] = None) -> bool:
    return any(
        item.name == name and (room_name is None or item.room_name == room_name)
        for item in plan.furniture
    )


def add_centered_piece(
    plan: FloorPlan,
    room_type: str,
    name: str,
    width: float,
    height: float,
    anchor: str = "bottom",
    x_offset: float = 0.0,
    y_offset: float = 0.0,
) -> None:
    room = find_room(plan, room_type)
    if room is None:
        return
    x = room.x + (room.w - width) / 2 + x_offset
    if anchor == "bottom":
        y = room.y + 1.0 + y_offset
    elif anchor == "top":
        y = room.y + room.h - height - 1.0 + y_offset
    else:
        y = room.y + (room.h - height) / 2 + y_offset
    plan.furniture.append(Furniture(name, x, y, width, height, room.name))


def apply_design_preferences(plan: FloorPlan, answers: Dict[str, str]) -> None:
    if answers["work_from_home"] == "no":
        plan.furniture = [
            item for item in plan.furniture if item.name not in {"Desk", "Desk Chair"}
        ]
        if not furniture_exists(plan, "Reading Chair"):
            add_centered_piece(plan, "office", "Reading Chair", 3.2, 3.0, "center", -2.0)
        if not furniture_exists(plan, "Side Table"):
            add_centered_piece(plan, "office", "Side Table", 1.8, 1.8, "center", 1.8)

    if answers["storage_priority"] == "high":
        if not furniture_exists(plan, "Bookcase"):
            add_centered_piece(plan, "office", "Bookcase", 3.0, 1.2, "top")
        if not furniture_exists(plan, "Storage Bench"):
            add_centered_piece(plan, "closet", "Storage Bench", 2.4, 1.4, "center")

    if answers["lighting_pref"] in {"bright", "mixed"} and not furniture_exists(
        plan, "Floor Lamp"
    ):
        add_centered_piece(plan, "living", "Floor Lamp", 1.2, 1.2, "bottom", -4.5)
    if answers["lighting_pref"] in {"soft", "mixed"} and not furniture_exists(
        plan, "Table Lamp"
    ):
        add_centered_piece(plan, "bedroom", "Table Lamp", 1.4, 1.4, "bottom", -4.0)

    if answers["pets"] == "dog" and not furniture_exists(plan, "Dog Bed"):
        add_centered_piece(plan, "living", "Dog Bed", 3.0, 2.2, "bottom", -4.0)
    if answers["pets"] == "cat" and not furniture_exists(plan, "Cat Tree"):
        add_centered_piece(plan, "living", "Cat Tree", 2.0, 2.0, "bottom", 4.5)


def add_box(
    vertices: List[Tuple[float, float, float]],
    faces: List[Tuple[int, ...]],
    face_materials: List[str],
    material: str,
    x: float,
    y: float,
    z: float,
    w: float,
    d: float,
    h: float,
) -> None:
    vx = [
        (x, y, z),
        (x + w, y, z),
        (x + w, y + d, z),
        (x, y + d, z),
        (x, y, z + h),
        (x + w, y, z + h),
        (x + w, y + d, z + h),
        (x, y + d, z + h),
    ]
    start = len(vertices) + 1
    vertices.extend(vx)
    faces.extend(
        [
            (start, start + 1, start + 2, start + 3),
            (start + 4, start + 5, start + 6, start + 7),
            (start, start + 1, start + 5, start + 4),
            (start + 1, start + 2, start + 6, start + 5),
            (start + 2, start + 3, start + 7, start + 6),
            (start + 3, start, start + 4, start + 7),
        ]
    )
    face_materials.extend([material] * 6)


def add_polygon_prism(
    vertices: List[Tuple[float, float, float]],
    faces: List[Tuple[int, ...]],
    face_materials: List[str],
    material: str,
    points: List[Tuple[float, float]],
    height: float,
) -> None:
    if len(points) < 3:
        return
    start = len(vertices) + 1
    for x, y in points:
        vertices.append((x, y, 0.0))
    for x, y in points:
        vertices.append((x, y, height))
    count = len(points)
    for idx in range(1, count - 1):
        faces.append((start, start + idx + 1, start + idx))
        face_materials.append(material)
        faces.append((start + count, start + count + idx, start + count + idx + 1))
        face_materials.append(material)
    for idx in range(count):
        next_idx = (idx + 1) % count
        faces.append(
            (
                start + idx,
                start + next_idx,
                start + count + next_idx,
                start + count + idx,
            )
        )
        face_materials.append(material)


def add_wall_segment(
    vertices: List[Tuple[float, float, float]],
    faces: List[Tuple[int, ...]],
    face_materials: List[str],
    material: str,
    start: Tuple[float, float],
    end: Tuple[float, float],
    thickness: float,
    height: float,
    z_base: float = 0.0,
) -> None:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = (dx * dx + dy * dy) ** 0.5
    if length < 1e-6:
        return
    ux = dx / length
    uy = dy / length
    px = -uy * thickness / 2
    py = ux * thickness / 2
    corners = [
        (start[0] + px, start[1] + py),
        (end[0] + px, end[1] + py),
        (end[0] - px, end[1] - py),
        (start[0] - px, start[1] - py),
    ]
    start_index = len(vertices) + 1
    for x, y in corners:
        vertices.append((x, y, z_base))
    for x, y in corners:
        vertices.append((x, y, z_base + height))
    wall_faces = [
        (start_index, start_index + 1, start_index + 2, start_index + 3),
        (start_index + 4, start_index + 5, start_index + 6, start_index + 7),
        (start_index, start_index + 1, start_index + 5, start_index + 4),
        (start_index + 1, start_index + 2, start_index + 6, start_index + 5),
        (start_index + 2, start_index + 3, start_index + 7, start_index + 6),
        (start_index + 3, start_index, start_index + 4, start_index + 7),
    ]
    faces.extend(wall_faces)
    face_materials.extend([material] * len(wall_faces))


def interpolate_segment(start: Tuple[float, float], end: Tuple[float, float], offset: float) -> Tuple[float, float]:
    length = segment_length(start, end)
    if length < 1e-6:
        return start
    ratio = offset / length
    return (
        start[0] + (end[0] - start[0]) * ratio,
        start[1] + (end[1] - start[1]) * ratio,
    )


def opening_span(room: Room, opening: Opening) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    wall_start, wall_end, offset = room_wall_reference(room, opening)
    length = segment_length(wall_start, wall_end)
    start = interpolate_segment(wall_start, wall_end, max(0.0, offset))
    end = interpolate_segment(wall_start, wall_end, min(length, offset + opening.width))
    return start, end


def room_wall_reference(room: Room, opening: Opening) -> Tuple[Tuple[float, float], Tuple[float, float], float]:
    edges = segments_from_polygon(room.polygon)
    if opening.edge_index is not None and 0 <= opening.edge_index < len(edges):
        start, end = edges[opening.edge_index]
        return start, end, opening.offset
    if opening.wall == "north":
        return (room.x, room.y + room.h), (room.x + room.w, room.y + room.h), opening.offset
    if opening.wall == "south":
        return (room.x, room.y), (room.x + room.w, room.y), opening.offset
    if opening.wall == "east":
        return (room.x + room.w, room.y), (room.x + room.w, room.y + room.h), opening.offset
    return (room.x, room.y + room.h), (room.x, room.y), opening.offset


def collect_wall_graph(plan: FloorPlan) -> Dict[Tuple[float, float, float, float], Dict]:
    graph: Dict[Tuple[float, float, float, float], Dict] = {}
    room_by_name = {room.name: room for room in plan.rooms}
    room_by_name = {room.name: room for room in plan.rooms}
    for room in plan.rooms:
        for edge_index, (start, end) in enumerate(segments_from_polygon(room.polygon)):
            key = canonical_segment(start, end)
            graph.setdefault(
                key,
                {"start": start, "end": end, "rooms": [], "openings": []},
            )
            graph[key]["rooms"].append((room.name, edge_index))
    for opening in plan.openings:
        room = room_by_name.get(opening.room_name)
        if room is None:
            continue
        start, end, raw_offset = room_wall_reference(room, opening)
        key = canonical_segment(start, end)
        if key not in graph:
            continue
        canon_start = (graph[key]["start"][0], graph[key]["start"][1])
        canon_end = (graph[key]["end"][0], graph[key]["end"][1])
        wall_len = segment_length(canon_start, canon_end)
        if wall_len < 1e-6:
            continue
        same_direction = (
            abs(canon_start[0] - start[0]) < 1e-6
            and abs(canon_start[1] - start[1]) < 1e-6
            and abs(canon_end[0] - end[0]) < 1e-6
            and abs(canon_end[1] - end[1]) < 1e-6
        )
        offset = raw_offset if same_direction else wall_len - raw_offset - opening.width
        graph[key]["openings"].append((max(offset, 0.0), min(offset + opening.width, wall_len)))
    for value in graph.values():
        value["openings"].sort()
    return graph


def add_opening_features(
    vertices: List[Tuple[float, float, float]],
    faces: List[Tuple[int, ...]],
    face_materials: List[str],
    plan: FloorPlan,
) -> None:
    room_by_name = {room.name: room for room in plan.rooms}
    for opening in plan.openings:
        room = room_by_name.get(opening.room_name)
        if room is None:
            continue
        start, end = opening_span(room, opening)
        total_length = segment_length(start, end)
        if total_length < 0.2:
            continue
        jamb = min(0.15, total_length / 4)
        left_inner = interpolate_segment(start, end, jamb)
        right_inner = interpolate_segment(start, end, total_length - jamb)

        if opening.kind == "door":
            add_wall_segment(vertices, faces, face_materials, "frame", start, left_inner, 0.08, 7.0)
            add_wall_segment(vertices, faces, face_materials, "frame", right_inner, end, 0.08, 7.0)
            add_wall_segment(vertices, faces, face_materials, "frame", left_inner, right_inner, 0.08, 0.2, 6.8)
            door_end = interpolate_segment(start, end, total_length * 0.92)
            add_wall_segment(vertices, faces, face_materials, "wood", start, door_end, 0.05, 7.0)
        elif opening.kind == "window":
            add_wall_segment(vertices, faces, face_materials, "frame", start, left_inner, 0.06, 4.4, 2.8)
            add_wall_segment(vertices, faces, face_materials, "frame", right_inner, end, 0.06, 4.4, 2.8)
            add_wall_segment(vertices, faces, face_materials, "frame", left_inner, right_inner, 0.06, 0.15, 2.8)
            add_wall_segment(vertices, faces, face_materials, "frame", left_inner, right_inner, 0.06, 0.15, 7.05)
            add_wall_segment(vertices, faces, face_materials, "glass", left_inner, right_inner, 0.03, 4.1, 2.95)


def add_finish_assemblies(
    vertices: List[Tuple[float, float, float]],
    faces: List[Tuple[int, ...]],
    face_materials: List[str],
    plan: FloorPlan,
) -> None:
    wall_thickness = 0.05
    for wall in collect_wall_graph(plan).values():
        start = (wall["start"][0], wall["start"][1])
        end = (wall["end"][0], wall["end"][1])
        total_length = segment_length(start, end)
        if total_length < 1e-6:
            continue
        holes = wall["openings"]
        dx = (end[0] - start[0]) / total_length
        dy = (end[1] - start[1]) / total_length
        for hole_start, hole_end in subtract_ranges(0.0, total_length, holes):
            seg_start = (start[0] + dx * hole_start, start[1] + dy * hole_start)
            seg_end = (start[0] + dx * hole_end, start[1] + dy * hole_end)
            add_wall_segment(vertices, faces, face_materials, "trim", seg_start, seg_end, wall_thickness, 0.45, 0.0)

    for item in plan.furniture:
        if item.name in {"Kitchen Cabinet Run", "Sink Base", "Island", "Bathroom Vanity"}:
            top_height = item.z + FURNITURE_HEIGHTS_FT.get(item.name, 3.0) - 0.08
            add_box(
                vertices,
                faces,
                face_materials,
                "stone",
                item.x - 0.05,
                item.y - 0.05,
                top_height,
                item.w + 0.1,
                item.h + 0.1,
                0.12,
            )


def subtract_ranges(full_start: float, full_end: float, holes: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    cursor = full_start
    result: List[Tuple[float, float]] = []
    for start, end in holes:
        start = max(start, full_start)
        end = min(end, full_end)
        if start > cursor:
            result.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < full_end:
        result.append((cursor, full_end))
    return [(start, end) for start, end in result if end - start > 0.05]


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


def intersects(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> bool:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    return ax1 < bx2 and ax2 > bx1 and ay1 < by2 and ay2 > by1


def room_for_furniture(plan: FloorPlan, item: Furniture) -> Optional[Room]:
    for room in plan.rooms:
        if room.name == item.room_name:
            return room
    return None


def clearance_box(item: Furniture) -> Tuple[float, float, float, float]:
    clearance = FURNITURE_CLEARANCE_FT.get(item.name, 2.0)
    return (
        item.x - clearance / 2,
        item.y - clearance / 2,
        item.x + item.w + clearance / 2,
        item.y + item.h + clearance / 2,
    )


def furniture_box(item: Furniture) -> Tuple[float, float, float, float]:
    return (item.x, item.y, item.x + item.w, item.y + item.h)


def is_soft_surface(item: Furniture) -> bool:
    return item.name in {"Outdoor Rug"}


def material_cost_range(spec: Dict[str, object], budget_level: str) -> Tuple[int, int]:
    multiplier = PRICE_MULTIPLIERS.get(budget_level, 1.0)
    low = int(int(spec["budget_low"]) * multiplier)
    high = int(int(spec["budget_high"]) * multiplier)
    return low, high


def z_range(item: Furniture) -> Tuple[float, float]:
    return (item.z, item.z + FURNITURE_HEIGHTS_FT.get(item.name, 2.5))


def z_ranges_overlap(first: Furniture, second: Furniture, tolerance: float = 0.15) -> bool:
    first_low, first_high = z_range(first)
    second_low, second_high = z_range(second)
    return first_low < second_high - tolerance and second_low < first_high - tolerance


def analyze_plan(plan: FloorPlan) -> Dict:
    issues: List[Dict[str, str]] = []
    room_stats: List[Dict[str, object]] = []

    for room in plan.rooms:
        room_items = [item for item in plan.furniture if item.room_name == room.name]
        room_box = (room.x, room.y, room.x + room.w, room.y + room.h)
        clearance_violations = 0
        overlap_violations = 0

        for item in room_items:
            item_box = furniture_box(item)
            corners = [
                (item_box[0], item_box[1]),
                (item_box[2], item_box[1]),
                (item_box[2], item_box[3]),
                (item_box[0], item_box[3]),
                (item.x + item.w / 2, item.y + item.h / 2),
            ]
            if not all(point_in_polygon(corner, room.polygon) for corner in corners):
                issues.append(
                    {
                        "severity": "high",
                        "room": room.name,
                        "message": f"{item.name} extends beyond room bounds.",
                    }
                )
            clearance = clearance_box(item)
            if item.z <= 0.1 and (
                clearance[0] < room_box[0]
                or clearance[1] < room_box[1]
                or clearance[2] > room_box[2]
                or clearance[3] > room_box[3]
            ):
                clearance_violations += 1

        for idx, first in enumerate(room_items):
            for second in room_items[idx + 1 :]:
                if is_soft_surface(first) or is_soft_surface(second):
                    continue
                if not z_ranges_overlap(first, second):
                    continue
                if intersects(furniture_box(first), furniture_box(second)):
                    overlap_violations += 1
                    issues.append(
                        {
                            "severity": "high",
                            "room": room.name,
                            "message": f"{first.name} overlaps {second.name}.",
                        }
                    )
                elif intersects(clearance_box(first), clearance_box(second)):
                    clearance_violations += 1

        room_area = room.w * room.h
        furniture_area = sum(item.w * item.h for item in room_items)
        free_area = max(room_area - furniture_area, 0.0)
        room_stats.append(
            {
                "room": room.name,
                "room_type": room.room_type,
                "room_area_sqft": round(room_area, 1),
                "furniture_area_sqft": round(furniture_area, 1),
                "estimated_free_area_sqft": round(free_area, 1),
                "item_count": len(room_items),
                "clearance_warnings": clearance_violations,
                "overlap_warnings": overlap_violations,
            }
        )

    score = max(0, 100 - len([issue for issue in issues if issue["severity"] == "high"]) * 25)
    score -= sum(stat["clearance_warnings"] for stat in room_stats if isinstance(stat["clearance_warnings"], int)) * 2
    score = clamp(score, 0, 100)
    return {
        "score": round(score, 1),
        "issues": issues,
        "rooms": room_stats,
    }


def write_obj(
    out_obj: Path,
    out_mtl: Path,
    plan: FloorPlan,
    palette: List[str],
) -> None:
    vertices: List[Tuple[float, float, float]] = []
    faces: List[Tuple[int, ...]] = []
    face_materials: List[str] = []
    materials = {
        "walls": tint_color(palette[0], 0.82),
        "wood": darken_color(palette[3], 0.08),
        "cabinetry": tint_color(palette[1], 0.42),
        "appliance": "#b8c0c7",
        "plumbing": "#f8fafc",
        "upholstery": tint_color(palette[2], 0.15),
        "accent": palette[3],
        "outdoor": tint_color(palette[3], 0.05),
        "trim": tint_color(palette[1], 0.62),
        "frame": tint_color(palette[0], 0.52),
        "glass": "#a8d8f0",
        "stone": tint_color(palette[1], 0.2),
    }

    floor_height = 0.08
    for room in plan.rooms:
        room_material = f"floor_{slugify(room.name)}"
        materials[room_material] = room_floor_color(room.room_type, palette)
        add_polygon_prism(
            vertices,
            faces,
            face_materials,
            room_material,
            room.polygon,
            floor_height,
        )

    wall_height = 9.0
    wall_thickness = 0.3
    for wall in collect_wall_graph(plan).values():
        start = (wall["start"][0], wall["start"][1])
        end = (wall["end"][0], wall["end"][1])
        total_length = segment_length(start, end)
        if total_length < 1e-6:
            continue
        holes = wall["openings"]
        dx = (end[0] - start[0]) / total_length
        dy = (end[1] - start[1]) / total_length
        for hole_start, hole_end in subtract_ranges(0.0, total_length, holes):
            seg_start = (start[0] + dx * hole_start, start[1] + dy * hole_start)
            seg_end = (start[0] + dx * hole_end, start[1] + dy * hole_end)
            add_wall_segment(
                vertices,
                faces,
                face_materials,
                "walls",
                seg_start,
                seg_end,
                wall_thickness,
                wall_height,
            )

    add_opening_features(vertices, faces, face_materials, plan)
    add_finish_assemblies(vertices, faces, face_materials, plan)

    for item in plan.furniture:
        height = FURNITURE_HEIGHTS_FT.get(item.name, 2.5)
        material_name = furniture_material_name(item.name)
        add_box(
            vertices,
            faces,
            face_materials,
            material_name,
            item.x,
            item.y,
            item.z,
            item.w,
            item.h,
            height,
        )

    with out_obj.open("w", encoding="utf-8") as handle:
        handle.write(f"mtllib {out_mtl.name}\n")
        for v in vertices:
            handle.write(f"v {v[0]:.3f} {v[2]:.3f} {v[1]:.3f}\n")
        current = None
        for face, material in zip(faces, face_materials):
            if material != current:
                handle.write(f"usemtl {material}\n")
                current = material
            handle.write("f " + " ".join(str(part) for part in face) + "\n")

    with out_mtl.open("w", encoding="utf-8") as handle:
        for name, color in materials.items():
            r, g, b = hex_to_rgb(color)
            handle.write(f"newmtl {name}\n")
            handle.write(f"Kd {r:.3f} {g:.3f} {b:.3f}\n")
            handle.write("Ka 0.1 0.1 0.1\n")
            handle.write("Ks 0.05 0.05 0.05\n")
            if name == "glass":
                handle.write("d 0.45\n")
            handle.write("\n")


def build_shopping_list(
    plan: FloorPlan, answers: Dict, palette: List[str]
) -> List[Dict]:
    style_tags = [tag.strip() for tag in answers.get("style_keywords", "").split(",")]
    budget_multiplier = PRICE_MULTIPLIERS.get(answers.get("budget_level", "mid"), 1.0)
    items = []
    for item in plan.furniture:
        room, category, price = SHOPPING_DEFAULTS.get(
            item.name, (item.room_name, "furniture", (100, 400))
        )
        adjusted_min = int(price[0] * budget_multiplier)
        adjusted_max = int(price[1] * budget_multiplier)
        items.append(
            {
                "item": item.name,
                "room": item.room_name or room,
                "category": category,
                "dimensions_ft": f"{item.w:.1f}x{item.h:.1f}",
                "style_tags": style_tags,
                "palette_hex": palette,
                "budget_tier": answers.get("budget_level", "mid"),
                "price_range_usd": f"{adjusted_min}-{adjusted_max}",
            }
        )
    must_have = answers.get("must_have", "none")
    if must_have and must_have.lower() != "none":
        for entry in [x.strip() for x in must_have.split(",") if x.strip()]:
            items.append(
                {
                    "item": entry,
                    "room": "TBD",
                    "category": "must_have",
                    "dimensions_ft": "TBD",
                    "style_tags": style_tags,
                    "palette_hex": palette,
                    "price_range_usd": "TBD",
                }
            )
    return items


def write_shopping_list(items: List[Dict], out_json: Path, out_csv: Path) -> None:
    out_json.write_text(json.dumps(items, indent=2), encoding="utf-8")
    if items:
        fieldnames = list(items[0].keys())
    else:
        fieldnames = [
            "item",
            "room",
            "category",
            "dimensions_ft",
            "style_tags",
            "palette_hex",
            "budget_tier",
            "price_range_usd",
        ]
    with out_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        if items:
            writer.writerows(items)


def write_analysis_report(report: Dict, out_json: Path, out_md: Path) -> None:
    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = [
        "# Space Planning Report",
        "",
        f"Overall score: {report['score']}/100",
        "",
        "## Issues",
        "",
    ]
    if report["issues"]:
        for issue in report["issues"]:
            lines.append(f"- [{issue['severity']}] {issue['room']}: {issue['message']}")
    else:
        lines.append("- No major overlap or out-of-bounds issues detected.")
    lines.extend(["", "## Room Stats", ""])
    for room in report["rooms"]:
        lines.append(
            f"- {room['room']}: free area {room['estimated_free_area_sqft']} sq ft, "
            f"{room['item_count']} items, clearance warnings {room['clearance_warnings']}"
        )
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_renovation_package(plan: FloorPlan, answers: Dict[str, str], palette: List[str]) -> Dict:
    room_scopes = []
    for room in plan.rooms:
        scope = {
            "room": room.name,
            "room_type": room.room_type,
            "finish_palette": {
                "walls": tint_color(palette[0], 0.78),
                "floor": room_floor_color(room.room_type, palette),
                "trim": tint_color(palette[1], 0.65),
                "accent": palette[3],
            },
            "renovation_scope": [],
        }
        if room.room_type == "kitchen":
            scope["renovation_scope"] = [
                "Install full-height painted cabinetry",
                "Replace counters with quartz or stone-look slab",
                "Upgrade appliance package",
                "Add under-cabinet and pendant lighting",
            ]
        elif room.room_type == "bath":
            scope["renovation_scope"] = [
                "Replace vanity and mirror package",
                "Retile the wet zone and bath floor",
                "Upgrade plumbing fixtures in a cohesive finish",
            ]
        elif room.room_type == "living":
            scope["renovation_scope"] = [
                "Create styled media wall zone",
                "Refinish or replace flooring finish",
                "Introduce layered lighting and textiles",
            ]
        elif room.room_type == "bedroom":
            scope["renovation_scope"] = [
                "Add drapery, layered bedding, and bedside lighting",
                "Introduce warm accent paint or wallpaper treatment",
            ]
        elif room.room_type == "office":
            scope["renovation_scope"] = [
                "Build a dedicated work zone with integrated storage",
                "Add accent paint or millwork backing",
            ]
        elif room.room_type == "utility":
            scope["renovation_scope"] = [
                "Add laundry storage and shelf system",
                "Conceal utility clutter with built-in organization",
            ]
        elif room.room_type == "outdoor":
            scope["renovation_scope"] = [
                "Add outdoor seating set and rug",
                "Introduce planters and exterior ambient lighting",
            ]
        else:
            scope["renovation_scope"] = ["Refine finishes and storage as needed"]
        room_scopes.append(scope)

    return {
        "concept_name": f"{answers['style_keywords'].title()} Ready-to-Build Concept",
        "renovation_summary": (
            f"This package translates the {answers['style_keywords']} direction into a renovation-aware concept "
            f"for the Mercer layout, including finish guidance, fixture upgrades, and styled furnishing intent."
        ),
        "room_scopes": room_scopes,
    }


def write_renovation_package(package: Dict, out_json: Path, out_md: Path) -> None:
    out_json.write_text(json.dumps(package, indent=2), encoding="utf-8")
    lines = [
        f"# {package['concept_name']}",
        "",
        package["renovation_summary"],
        "",
        "## Room Scopes",
        "",
    ]
    for room in package["room_scopes"]:
        lines.append(f"### {room['room']}")
        lines.append(f"- Walls: {room['finish_palette']['walls']}")
        lines.append(f"- Floor: {room['finish_palette']['floor']}")
        lines.append(f"- Trim: {room['finish_palette']['trim']}")
        lines.append(f"- Accent: {room['finish_palette']['accent']}")
        for item in room["renovation_scope"]:
            lines.append(f"- {item}")
        lines.append("")
    out_md.write_text("\n".join(lines), encoding="utf-8")


def build_renovation_schedule(plan: FloorPlan, answers: Dict[str, str]) -> List[Dict]:
    schedule: List[Dict] = []
    counts: Dict[Tuple[str, str], int] = {}
    for item in plan.furniture:
        key = (item.room_name, item.name)
        counts[key] = counts.get(key, 0) + 1

    for (room_name, item_name), quantity in sorted(counts.items()):
        spec = SPEC_LIBRARY.get(item_name)
        if spec is None:
            continue
        low, high = material_cost_range(spec, answers["budget_level"])
        schedule.append(
            {
                "room": room_name,
                "item": item_name,
                "trade": spec["trade"],
                "finish": spec["finish"],
                "unit": spec["unit"],
                "quantity": quantity,
                "budget_tier": answers["budget_level"],
                "installed_cost_range_usd": f"{low}-{high}",
            }
        )
    return schedule


def write_renovation_schedule(schedule: List[Dict], out_json: Path, out_csv: Path, out_md: Path) -> None:
    out_json.write_text(json.dumps(schedule, indent=2), encoding="utf-8")
    if schedule:
        fieldnames = list(schedule[0].keys())
    else:
        fieldnames = ["room", "item", "trade", "finish", "unit", "quantity", "budget_tier", "installed_cost_range_usd"]
    with out_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        if schedule:
            writer.writerows(schedule)

    lines = [
        "# Renovation Schedule",
        "",
        "This schedule summarizes modeled renovation components and indicative installed cost ranges.",
        "",
    ]
    for row in schedule:
        lines.append(
            f"- {row['room']}: {row['item']} ({row['trade']}, qty {row['quantity']}, {row['installed_cost_range_usd']} USD)"
        )
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_finish_schedule(plan: FloorPlan, palette: List[str]) -> List[Dict]:
    schedule: List[Dict] = []
    finish_tags = {room.name: f"F{idx:02d}" for idx, room in enumerate(plan.rooms, start=1)}
    for room in plan.rooms:
        schedule.extend(
            [
                {
                    "finish_tag": finish_tags[room.name],
                    "room": room.name,
                    "category": "walls",
                    "finish_name": ARCHITECTURAL_FINISH_LIBRARY["walls"],
                    "finish_color": tint_color(palette[0], 0.78),
                    "application": "full wall finish",
                },
                {
                    "finish_tag": finish_tags[room.name],
                    "room": room.name,
                    "category": "floor",
                    "finish_name": "room floor finish",
                    "finish_color": room_floor_color(room.room_type, palette),
                    "application": room.room_type,
                },
                {
                    "finish_tag": finish_tags[room.name],
                    "room": room.name,
                    "category": "trim",
                    "finish_name": ARCHITECTURAL_FINISH_LIBRARY["trim"],
                    "finish_color": tint_color(palette[1], 0.65),
                    "application": "baseboard and casing",
                },
            ]
        )
        if room.room_type in {"kitchen", "bath"}:
            schedule.append(
                {
                    "finish_tag": finish_tags[room.name],
                    "room": room.name,
                    "category": "countertop",
                    "finish_name": ARCHITECTURAL_FINISH_LIBRARY["stone"],
                    "finish_color": tint_color(palette[1], 0.2),
                    "application": "countertop slab",
                }
            )
    return schedule


def write_finish_schedule(schedule: List[Dict], out_json: Path, out_csv: Path, out_md: Path) -> None:
    out_json.write_text(json.dumps(schedule, indent=2), encoding="utf-8")
    fieldnames = ["finish_tag", "room", "category", "finish_name", "finish_color", "application"]
    with out_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        if schedule:
            writer.writerows(schedule)

    lines = [
        "# Finish Schedule",
        "",
        "This schedule summarizes major room finish systems for the current concept.",
        "",
    ]
    for row in schedule:
        lines.append(
            f"- {row['finish_tag']} {row['room']}: {row['category']} -> {row['finish_name']} ({row['finish_color']})"
        )
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def room_center_by_type(plan: FloorPlan, room_types: Iterable[str]) -> Tuple[str, Tuple[float, float]]:
    wanted = {room_type.lower() for room_type in room_types}
    for room in plan.rooms:
        if room.room_type.lower() in wanted or room.name.lower() in wanted:
            return room.name, polygon_centroid(room.polygon)
    fallback = plan.rooms[0]
    return fallback.name, polygon_centroid(fallback.polygon)


def build_title_block(plan: FloorPlan, issue_date: str) -> Dict[str, str]:
    return {
        "project_name": f"{plan.unit_name} Ready-to-Build Concept",
        "project_location": "The Glenn at Polo Park, Bentonville, AR",
        "unit_name": plan.unit_name,
        "package_phase": "Sheet + spec package",
        "scale_note": "Diagrammatic / not for permit",
        "issue_date": issue_date,
    }


def build_keyed_notes(plan: FloorPlan, answers: Dict) -> List[Dict]:
    notes: List[Dict] = []
    room_name, point = room_center_by_type(plan, ["kitchen"])
    notes.append(
        {
            "id": "N1",
            "room": room_name,
            "point": [round(point[0], 2), round(point[1], 2)],
            "note": "Field verify appliance rough-ins, cabinet run length, and countertop seams before fabrication.",
        }
    )
    room_name, point = room_center_by_type(plan, ["bath"])
    notes.append(
        {
            "id": "N2",
            "room": room_name,
            "point": [round(point[0], 2), round(point[1], 2)],
            "note": "Coordinate vanity width, mirror panel, and plumbing fixture clearances with existing services.",
        }
    )
    room_name, point = room_center_by_type(plan, ["living"])
    notes.append(
        {
            "id": "N3",
            "room": room_name,
            "point": [round(point[0], 2), round(point[1], 2)],
            "note": "Maintain circulation around the seating group and confirm media wall power and low-voltage locations.",
        }
    )
    if answers.get("work_from_home") == "yes":
        room_name, point = room_center_by_type(plan, ["office", "den"])
        notes.append(
            {
                "id": "N4",
                "room": room_name,
                "point": [round(point[0], 2), round(point[1], 2)],
                "note": "Provide dedicated task lighting, data/power access, and storage coordination for work-from-home use.",
            }
        )
    room_name, point = room_center_by_type(plan, ["bedroom"])
    notes.append(
        {
            "id": "N5",
            "room": room_name,
            "point": [round(point[0], 2), round(point[1], 2)],
            "note": "Verify bed wall clearances, outlet placement, and dresser fit before procurement and installation.",
        }
    )
    return notes


def build_schedule_references() -> List[Dict[str, str]]:
    return [
        {"label": "Room Schedule", "description": "Reference room sizes, room types, and approximate areas."},
        {"label": "Wall Schedule", "description": "Reference wall IDs shown on plan for wall types, thickness assumptions, and opening counts."},
        {"label": "Opening Schedule", "description": "Reference tagged doors and windows for widths, sill heights, and swing assumptions."},
        {"label": "Cabinet Schedule", "description": "Reference cabinet tags and elevation refs shown on plan for built-ins and millwork."},
        {"label": "Finish Schedule", "description": "Reference room finish tags shown on plan for floor, wall, trim, and countertop intent."},
        {"label": "Elevation Sheet", "description": "Reference E### interior elevation views for cabinetry and built-in vertical coordination."},
        {"label": "Grouped Elevation Sheet", "description": "Reference room-based elevation compositions combining millwork, fixtures, and appliances."},
    ]


def build_drawing_set() -> List[Dict[str, str]]:
    return [
        {
            "sheet_no": "G001",
            "title": "Cover Sheet",
            "filename": "sheets/G001_cover_sheet.svg",
            "description": "Project metadata, concept summary, and drawing index for the package.",
        },
        {
            "sheet_no": "A101",
            "title": "Plan / Tags",
            "filename": "sheets/A101_plan_sheet.svg",
            "description": "Dimensioned concept plan with opening, cabinetry, and keyed note callouts.",
        },
        {
            "sheet_no": "A601",
            "title": "Notes / Legend",
            "filename": "sheets/A601_notes_sheet.svg",
            "description": "General notes, wall type legend, keyed note log, and schedule references.",
        },
        {
            "sheet_no": "A201",
            "title": "Interior Elevations",
            "filename": "sheets/A201_elevations_sheet.svg",
            "description": "Cabinet and built-in elevations keyed to E### references shown on plan.",
        },
        {
            "sheet_no": "A202",
            "title": "Grouped Interior Elevations",
            "filename": "sheets/A202_room_elevations_sheet.svg",
            "description": "Room-based elevation compositions for kitchen, bath, and utility zones.",
        },
    ]


def build_spec_package(
    plan: FloorPlan,
    title_block: Dict[str, str],
    keyed_notes: List[Dict],
    drawing_set: List[Dict[str, str]],
    schedule_refs: List[Dict[str, str]],
    wall_tags: List[Dict[str, object]],
    finish_tags: List[Dict[str, object]],
    cabinet_elevation_tags: List[Dict[str, object]],
) -> Dict:
    return {
        "title": f"{plan.unit_name} Concept Spec Package",
        "title_block": title_block,
        "general_notes": [
            "All dimensions are approximate and should be field-verified before construction.",
            "Concept assumes a typical apartment renovation scope without structural changes.",
            "Door and window sizes shown are inferred from the concept geometry.",
            "Cabinetry and finish selections are schematic and require shop drawing coordination.",
            "Mechanical, electrical, and plumbing coordination is not included in this package.",
        ],
        "wall_legend": [
            "Exterior_6in: assumed apartment perimeter wall build-up",
            "Interior_4in: assumed non-structural interior partition",
            "Glazing: conceptual insulated window assembly",
            "Trim: conceptual baseboard and casing package",
        ],
        "keyed_notes": keyed_notes,
        "drawing_set": drawing_set,
        "schedule_references": schedule_refs,
        "wall_tags": wall_tags,
        "finish_tags": finish_tags,
        "cabinet_elevation_tags": cabinet_elevation_tags,
    }


def build_wall_tags(plan: FloorPlan) -> List[Dict[str, object]]:
    tags: List[Dict[str, object]] = []
    for idx, wall in enumerate(collect_wall_graph(plan).values(), start=1):
        start = (float(wall["start"][0]), float(wall["start"][1]))
        end = (float(wall["end"][0]), float(wall["end"][1]))
        midpoint = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        length = max(segment_length(start, end), 1e-6)
        offset = 0.45
        point = (
            round(midpoint[0] + (-dy / length) * offset, 2),
            round(midpoint[1] + (dx / length) * offset, 2),
        )
        tags.append({"id": f"W{idx:03d}", "point": list(point)})
    return tags


def build_finish_tags(plan: FloorPlan) -> List[Dict[str, object]]:
    tags: List[Dict[str, object]] = []
    for idx, room in enumerate(plan.rooms, start=1):
        cx, cy = polygon_centroid(room.polygon)
        point = [round(cx, 2), round(cy - min(room.h * 0.18, 1.1), 2)]
        tags.append(
            {
                "id": f"F{idx:02d}",
                "room": room.name,
                "point": point,
            }
        )
    return tags


def build_cabinet_elevation_tags(plan: FloorPlan, cabinet_schedule: List[Dict]) -> List[Dict[str, object]]:
    cabinet_items = [
        item
        for item in plan.furniture
        if item.name
        in {
            "Kitchen Cabinet Run",
            "Upper Cabinets",
            "Island",
            "Sink Base",
            "Bathroom Vanity",
            "Linen Tower",
            "Laundry Shelf",
            "Wall Shelf",
        }
    ]
    tags: List[Dict[str, object]] = []
    for row, item in zip(cabinet_schedule, cabinet_items):
        point = [round(item.x + item.w + 0.45, 2), round(item.y + item.h / 2.0, 2)]
        tags.append(
            {
                "id": row["elevation_ref"],
                "cabinet_id": row["cabinet_id"],
                "point": point,
            }
        )
    return tags


def build_elevation_views(plan: FloorPlan, cabinet_schedule: List[Dict]) -> List[Dict[str, object]]:
    cabinet_items = [
        item
        for item in plan.furniture
        if item.name
        in {
            "Kitchen Cabinet Run",
            "Upper Cabinets",
            "Island",
            "Sink Base",
            "Bathroom Vanity",
            "Linen Tower",
            "Laundry Shelf",
            "Wall Shelf",
        }
    ]
    views: List[Dict[str, object]] = []
    for row, item in zip(cabinet_schedule, cabinet_items):
        views.append(
            {
                "elevation_ref": row["elevation_ref"],
                "cabinet_id": row["cabinet_id"],
                "room": row["room"],
                "item": row["item"],
                "width_ft": row["width_ft"],
                "depth_ft": row["depth_ft"],
                "mounting_height_ft": row["mounting_height_ft"],
                "height_ft": round(FURNITURE_HEIGHTS_FT.get(item.name, 2.5), 2),
            }
        )
    return views


def build_room_elevation_views(
    plan: FloorPlan,
    cabinet_schedule: List[Dict],
    finish_schedule: List[Dict],
) -> List[Dict[str, object]]:
    cabinet_ref_by_item: Dict[int, Dict[str, str]] = {}
    cabinet_items = [
        item
        for item in plan.furniture
        if item.name
        in {
            "Kitchen Cabinet Run",
            "Upper Cabinets",
            "Island",
            "Sink Base",
            "Bathroom Vanity",
            "Linen Tower",
            "Laundry Shelf",
            "Wall Shelf",
        }
    ]
    for row, item in zip(cabinet_schedule, cabinet_items):
        cabinet_ref_by_item[id(item)] = {
            "cabinet_id": row["cabinet_id"],
            "elevation_ref": row["elevation_ref"],
        }

    finish_by_room: Dict[str, List[Dict]] = {}
    for row in finish_schedule:
        finish_by_room.setdefault(str(row["room"]), []).append(row)

    grouped_specs = [
        (
            "Kitchen",
            {"kitchen"},
            {"Kitchen Cabinet Run", "Upper Cabinets", "Sink Base", "Fridge", "Range"},
            "North appliance / millwork wall",
            [("D1", "counter-to-splash transition"), ("D2", "upper cabinet anchorage")],
        ),
        (
            "Bathroom",
            {"bath"},
            {"Bathroom Vanity", "Linen Tower", "Mirror Panel", "Toilet", "Shower/Tub"},
            "Vanity and wet-wall elevation",
            [("D3", "vanity backsplash seal"), ("D4", "tub / wall edge condition")],
        ),
        (
            "Laundry",
            {"utility"},
            {"Laundry Shelf", "Wall Shelf", "Washer", "Dryer"},
            "Equipment and storage wall",
            [("D5", "shelf support and blocking"), ("D6", "appliance service clearances")],
        ),
    ]
    views: List[Dict[str, object]] = []
    for title, room_types, allowed_items, wall_label, detail_bubbles in grouped_specs:
        room = next((room for room in plan.rooms if room.room_type in room_types), None)
        if room is None:
            continue
        room_items = [item for item in plan.furniture if item.room_name == room.name and item.name in allowed_items]
        if not room_items:
            continue
        if room.w >= room.h:
            room_items = sorted(room_items, key=lambda item: (item.x, item.y, item.name))
        else:
            room_items = sorted(room_items, key=lambda item: (item.y, item.x, item.name))

        items: List[Dict[str, object]] = []
        refs: List[str] = []
        detail_refs = [bubble[0] for bubble in detail_bubbles]
        for item in room_items:
            ref_meta = cabinet_ref_by_item.get(id(item), {})
            if ref_meta.get("elevation_ref"):
                refs.append(ref_meta["elevation_ref"])
            fill = "#dbeafe"
            stroke = "#1d4ed8"
            if item.name in {"Fridge", "Range", "Washer", "Dryer"}:
                fill = "#e5e7eb"
                stroke = "#64748b"
            elif item.name in {"Toilet", "Shower/Tub", "Mirror Panel"}:
                fill = "#f8fafc"
                stroke = "#94a3b8"
            elif item.name in {"Upper Cabinets", "Wall Shelf"}:
                fill = "#fef3c7"
                stroke = "#b45309"
            items.append(
                {
                    "item": item.name,
                    "label": item.name,
                    "ref": ref_meta.get("elevation_ref", ""),
                    "width_ft": round(item.w, 2),
                    "height_ft": round(FURNITURE_HEIGHTS_FT.get(item.name, 2.5), 2),
                    "mounting_height_ft": round(item.z, 2),
                    "fill": fill,
                    "stroke": stroke,
                }
            )
        finish_callouts = []
        for finish in finish_by_room.get(room.name, []):
            category = str(finish.get("category", ""))
            if category not in {"walls", "trim", "countertop", "floor"}:
                continue
            finish_callouts.append(
                {
                    "tag": str(finish.get("finish_tag", "")),
                    "category": category,
                    "name": str(finish.get("finish_name", "")),
                    "color": str(finish.get("finish_color", "")),
                }
            )
        views.append(
            {
                "room": room.name,
                "title": title,
                "refs": ", ".join(refs) if refs else "Fixture coordination",
                "summary": f"Approximate {title.lower()} wall composition generated from modeled room content.",
                "wall_label": wall_label,
                "detail_refs": ", ".join(detail_refs),
                "detail_bubbles": [{"id": bubble[0], "note": bubble[1]} for bubble in detail_bubbles],
                "finish_callouts": finish_callouts,
                "items": items,
            }
        )
    return views


def write_spec_package(package: Dict, out_json: Path, out_md: Path) -> None:
    out_json.write_text(json.dumps(package, indent=2), encoding="utf-8")
    title_block = package.get("title_block", {})
    lines = [f"# {package['title']}", "", "## Title Block", ""]
    for key in ["project_name", "project_location", "unit_name", "package_phase", "scale_note", "issue_date"]:
        value = title_block.get(key)
        if value:
            lines.append(f"- {key}: {value}")
    lines.extend(["", "## Drawing Set", ""])
    for entry in package.get("drawing_set", []):
        lines.append(f"- {entry['sheet_no']} {entry['title']}: {entry['description']}")
    lines.extend(["", "## General Notes", ""])
    for note in package["general_notes"]:
        lines.append(f"- {note}")
    lines.extend(["", "## Wall Type Legend", ""])
    for entry in package["wall_legend"]:
        lines.append(f"- {entry}")
    lines.extend(["", "## Keyed Notes", ""])
    for note in package.get("keyed_notes", []):
        lines.append(f"- {note['id']} ({note['room']}): {note['note']}")
    lines.extend(["", "## Plan Tags", ""])
    for tag in package.get("wall_tags", []):
        lines.append(f"- {tag['id']}: wall schedule identifier shown on plan")
    for tag in package.get("finish_tags", []):
        lines.append(f"- {tag['id']} ({tag['room']}): room finish tag shown on plan")
    for tag in package.get("cabinet_elevation_tags", []):
        lines.append(f"- {tag['id']}: cabinet elevation reference for {tag['cabinet_id']}")
    lines.extend(["", "## Schedule References", ""])
    for entry in package.get("schedule_references", []):
        lines.append(f"- {entry['label']}: {entry['description']}")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_sheet_index(sheet_entries: List[Dict[str, str]], out_json: Path, out_md: Path) -> None:
    out_json.write_text(json.dumps(sheet_entries, indent=2), encoding="utf-8")
    lines = ["# Drawing Set Index", ""]
    for entry in sheet_entries:
        lines.append(
            f"- {entry['sheet_no']} {entry['title']}: {entry['description']} ({entry['filename']})"
        )
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_print_package(
    out_path: Path,
    title_block: Dict[str, str],
    sheet_entries: List[Dict[str, str]],
    out_dir: Path,
) -> None:
    sections: List[str] = []
    for entry in sheet_entries:
        svg_path = out_dir / entry["filename"]
        svg_rel = svg_path.relative_to(out_dir)
        sections.append(
            f"""
      <section class="sheet-page">
        <div class="sheet-meta">
          <div class="sheet-no">{entry['sheet_no']}</div>
          <div>
            <h2>{entry['title']}</h2>
            <p>{entry['description']}</p>
          </div>
        </div>
        <object data="{svg_rel.as_posix()}" type="image/svg+xml" class="sheet-frame"></object>
      </section>
"""
        )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title_block.get('project_name', 'Drawing Set')} Print Package</title>
  <style>
    :root {{
      --bg: #e5e7eb;
      --paper: #ffffff;
      --ink: #111827;
      --muted: #475569;
      --line: #cbd5e1;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, sans-serif;
      background: var(--bg);
      color: var(--ink);
    }}
    .page {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 24px;
    }}
    .hero {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 24px;
      margin-bottom: 24px;
    }}
    .hero h1 {{
      margin: 0 0 10px;
      font-size: 2rem;
    }}
    .hero p {{
      margin: 0;
      color: var(--muted);
      line-height: 1.6;
    }}
    .sheet-page {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 20px;
      margin-bottom: 24px;
      box-shadow: 0 10px 35px rgba(15, 23, 42, 0.08);
      break-after: page;
      page-break-after: always;
    }}
    .sheet-page:last-child {{
      break-after: auto;
      page-break-after: auto;
    }}
    .sheet-meta {{
      display: flex;
      gap: 16px;
      align-items: flex-start;
      margin-bottom: 16px;
    }}
    .sheet-no {{
      min-width: 72px;
      padding: 10px 12px;
      border-radius: 14px;
      background: #f8fafc;
      border: 1px solid var(--line);
      font-weight: 700;
      text-align: center;
    }}
    .sheet-meta h2 {{
      margin: 0 0 6px;
      font-size: 1.2rem;
    }}
    .sheet-meta p {{
      margin: 0;
      color: var(--muted);
      line-height: 1.5;
    }}
    .sheet-frame {{
      width: 100%;
      min-height: 920px;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: #fff;
    }}
    @media print {{
      body {{
        background: #fff;
      }}
      .page {{
        max-width: none;
        padding: 0;
      }}
      .hero {{
        border: none;
        padding: 0 0 12px;
      }}
      .sheet-page {{
        border: none;
        border-radius: 0;
        box-shadow: none;
        margin: 0;
        padding: 0;
      }}
      .sheet-frame {{
        border: none;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <div class="hero">
      <h1>{title_block.get('project_name', 'Drawing Set Print Package')}</h1>
      <p>{title_block.get('project_location', '')} | Issue {title_block.get('issue_date', '')} | {title_block.get('package_phase', '')}</p>
    </div>
    {''.join(sections)}
  </div>
</body>
</html>
"""
    out_path.write_text(html, encoding="utf-8")


def build_room_schedule(plan: FloorPlan) -> List[Dict]:
    schedule = []
    for room in plan.rooms:
        schedule.append(
            {
                "room": room.name,
                "room_type": room.room_type,
                "width_ft": round(room.w, 2),
                "depth_ft": round(room.h, 2),
                "area_sqft": round(polygon_area(room.polygon), 2),
            }
        )
    return schedule


def build_wall_schedule(plan: FloorPlan) -> List[Dict]:
    schedule = []
    for idx, wall in enumerate(collect_wall_graph(plan).values(), start=1):
        start = (wall["start"][0], wall["start"][1])
        end = (wall["end"][0], wall["end"][1])
        wall_type = "exterior_6in" if len(wall["rooms"]) == 1 else "interior_4in"
        schedule.append(
            {
                "wall_id": f"W{idx:03d}",
                "length_ft": round(segment_length(start, end), 2),
                "wall_type": wall_type,
                "thickness_in": 6.0 if len(wall["rooms"]) == 1 else 4.0,
                "adjacent_rooms": ", ".join(sorted({room_name for room_name, _ in wall["rooms"]})),
                "opening_count": len(wall["openings"]),
            }
        )
    return schedule


def build_opening_schedule(plan: FloorPlan) -> List[Dict]:
    room_by_name = {room.name: room for room in plan.rooms}
    schedule = []
    for idx, opening in enumerate(plan.openings, start=1):
        room = room_by_name.get(opening.room_name)
        if room is None:
            continue
        start, end = opening_span(room, opening)
        schedule.append(
            {
                "opening_id": f"O{idx:03d}",
                "room": room.name,
                "kind": opening.kind,
                "width_ft": round(segment_length(start, end), 2),
                "edge_reference": opening.edge_index if opening.edge_index is not None else opening.wall,
                "sill_height_ft": opening.sill_height,
                "head_height_ft": opening.head_height,
                "swing": opening.swing if opening.kind == "door" else "n/a",
            }
        )
    return schedule


def build_cabinet_schedule(plan: FloorPlan) -> List[Dict]:
    cabinet_items = {
        "Kitchen Cabinet Run",
        "Upper Cabinets",
        "Island",
        "Sink Base",
        "Bathroom Vanity",
        "Linen Tower",
        "Laundry Shelf",
        "Wall Shelf",
    }
    schedule = []
    tagged_items = [item for item in plan.furniture if item.name in cabinet_items]
    for idx, item in enumerate(tagged_items, start=1):
        schedule.append(
            {
                "cabinet_id": f"C{idx:03d}",
                "elevation_ref": f"E{idx:03d}",
                "room": item.room_name,
                "item": item.name,
                "width_ft": round(item.w, 2),
                "depth_ft": round(item.h, 2),
                "mounting_height_ft": round(item.z, 2),
                "quantity": 1,
            }
        )
    return schedule


def write_schedule(schedule: List[Dict], title: str, intro: str, out_json: Path, out_csv: Path, out_md: Path) -> None:
    out_json.write_text(json.dumps(schedule, indent=2), encoding="utf-8")
    fieldnames = list(schedule[0].keys()) if schedule else []
    with out_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if fieldnames:
            writer.writeheader()
            writer.writerows(schedule)

    lines = [f"# {title}", "", intro, ""]
    for row in schedule:
        parts = [f"{key}: {value}" for key, value in row.items()]
        lines.append("- " + ", ".join(parts))
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_design_brief(plan: FloorPlan, answers: Dict[str, str], palette: List[str]) -> Dict:
    style_line = answers["style_keywords"]
    work_mode = (
        "with a dedicated work-from-home zone"
        if answers["work_from_home"] == "yes"
        else "with the den softened into a lounge flex space"
    )
    pet_line = (
        f"Pet-friendly choices are included for a {answers['pets']}."
        if answers["pets"] != "none"
        else "The layout is optimized for a non-pet household."
    )
    room_notes = []
    for room in plan.rooms:
        pieces = [item.name for item in plan.furniture if item.room_name == room.name]
        room_notes.append(
            {
                "room": room.name,
                "purpose": room.room_type,
                "recommended_items": pieces,
                "rationale": f"Keep {room.name.lower()} aligned with a {style_line} direction.",
            }
        )
    return {
        "concept_name": f"{style_line.title()} Mercer Concept",
        "summary": (
            f"A {style_line} concept for the Mercer apartment, {work_mode}. "
            f"Palette preference leans {answers['palette_preference']} with "
            f"{answers['lighting_pref']} lighting and {answers['storage_priority']} storage. "
            f"{pet_line}"
        ),
        "palette_hex": palette,
        "room_recommendations": room_notes,
    }


def write_design_brief(brief: Dict, out_json: Path, out_md: Path) -> None:
    out_json.write_text(json.dumps(brief, indent=2), encoding="utf-8")
    lines = [
        f"# {brief['concept_name']}",
        "",
        brief["summary"],
        "",
        "## Palette",
        "",
        ", ".join(brief["palette_hex"]),
        "",
        "## Room Recommendations",
        "",
    ]
    for room in brief["room_recommendations"]:
        lines.append(f"- {room['room']}: {room['rationale']}")
        lines.append(f"  Items: {', '.join(room['recommended_items']) or 'None'}")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_design(
    layout_path: Path,
    answers: Dict,
    style_images: Optional[List[Path]],
    out_dir: Path,
) -> Dict:
    answers = normalize_answers(answers)
    if not layout_path.exists():
        raise FileNotFoundError(f"Layout file not found: {layout_path}")

    plan = build_plan(layout_path)
    validate_plan(plan)
    apply_design_preferences(plan, answers)

    style_palette = infer_palette_from_images(style_images or [])
    palette = ensure_palette(style_palette, answers["palette_preference"])

    out_dir.mkdir(parents=True, exist_ok=True)
    sheets_dir = out_dir / "sheets"
    sheets_dir.mkdir(parents=True, exist_ok=True)

    obj_path = out_dir / "mercer_model.obj"
    mtl_path = out_dir / "mercer_model.mtl"
    dimensioned_plan_path = out_dir / "dimensioned_plan.svg"
    construction_sheet_path = out_dir / "construction_sheet.svg"
    cover_sheet_path = sheets_dir / "G001_cover_sheet.svg"
    plan_sheet_path = sheets_dir / "A101_plan_sheet.svg"
    elevations_sheet_path = sheets_dir / "A201_elevations_sheet.svg"
    room_elevations_sheet_path = sheets_dir / "A202_room_elevations_sheet.svg"
    notes_sheet_path = sheets_dir / "A601_notes_sheet.svg"
    sheet_index_json_path = out_dir / "sheet_index.json"
    sheet_index_md_path = out_dir / "sheet_index.md"
    print_package_path = out_dir / "drawing_set_print.html"
    to_svg(plan, dimensioned_plan_path, show_dimensions=True)
    write_obj(obj_path, mtl_path, plan, palette)

    shopping_items = build_shopping_list(plan, answers, palette)
    write_shopping_list(
        shopping_items, out_dir / "shopping_list.json", out_dir / "shopping_list.csv"
    )
    analysis_report = analyze_plan(plan)
    write_analysis_report(
        analysis_report,
        out_dir / "space_plan_report.json",
        out_dir / "space_plan_report.md",
    )
    design_brief = build_design_brief(plan, answers, palette)
    write_design_brief(
        design_brief,
        out_dir / "design_brief.json",
        out_dir / "design_brief.md",
    )
    renovation_package = build_renovation_package(plan, answers, palette)
    write_renovation_package(
        renovation_package,
        out_dir / "renovation_package.json",
        out_dir / "renovation_package.md",
    )
    renovation_schedule = build_renovation_schedule(plan, answers)
    write_renovation_schedule(
        renovation_schedule,
        out_dir / "renovation_schedule.json",
        out_dir / "renovation_schedule.csv",
        out_dir / "renovation_schedule.md",
    )
    finish_schedule = build_finish_schedule(plan, palette)
    write_finish_schedule(
        finish_schedule,
        out_dir / "finish_schedule.json",
        out_dir / "finish_schedule.csv",
        out_dir / "finish_schedule.md",
    )
    room_schedule = build_room_schedule(plan)
    write_schedule(
        room_schedule,
        "Room Schedule",
        "This schedule summarizes room sizes and approximate areas.",
        out_dir / "room_schedule.json",
        out_dir / "room_schedule.csv",
        out_dir / "room_schedule.md",
    )
    wall_schedule = build_wall_schedule(plan)
    write_schedule(
        wall_schedule,
        "Wall Schedule",
        "This schedule summarizes wall lengths, wall types, and openings.",
        out_dir / "wall_schedule.json",
        out_dir / "wall_schedule.csv",
        out_dir / "wall_schedule.md",
    )
    opening_schedule = build_opening_schedule(plan)
    write_schedule(
        opening_schedule,
        "Opening Schedule",
        "This schedule summarizes windows and doors in the current concept.",
        out_dir / "opening_schedule.json",
        out_dir / "opening_schedule.csv",
        out_dir / "opening_schedule.md",
    )
    cabinet_schedule = build_cabinet_schedule(plan)
    write_schedule(
        cabinet_schedule,
        "Cabinet Schedule",
        "This schedule summarizes modeled cabinetry and built-in storage components.",
        out_dir / "cabinet_schedule.json",
        out_dir / "cabinet_schedule.csv",
        out_dir / "cabinet_schedule.md",
    )
    issue_date = date.today().isoformat()
    title_block = build_title_block(plan, issue_date)
    keyed_notes = build_keyed_notes(plan, answers)
    drawing_set = build_drawing_set()
    schedule_refs = build_schedule_references()
    wall_tags = build_wall_tags(plan)
    finish_tags = build_finish_tags(plan)
    cabinet_elevation_tags = build_cabinet_elevation_tags(plan, cabinet_schedule)
    elevation_views = build_elevation_views(plan, cabinet_schedule)
    room_elevation_views = build_room_elevation_views(plan, cabinet_schedule, finish_schedule)
    spec_package = build_spec_package(
        plan,
        title_block,
        keyed_notes,
        drawing_set,
        schedule_refs,
        wall_tags,
        finish_tags,
        cabinet_elevation_tags,
    )
    write_spec_package(
        spec_package,
        out_dir / "spec_package.json",
        out_dir / "spec_package.md",
    )
    write_sheet_index(drawing_set, sheet_index_json_path, sheet_index_md_path)
    cabinet_items = [
        item
        for item in plan.furniture
        if item.name
        in {
            "Kitchen Cabinet Run",
            "Upper Cabinets",
            "Island",
            "Sink Base",
            "Bathroom Vanity",
            "Linen Tower",
            "Laundry Shelf",
            "Wall Shelf",
        }
    ]
    to_sheet_svg(
        plan,
        construction_sheet_path,
        title=f"{plan.unit_name} Concept Sheet",
        subtitle="Plan tags for openings, walls, finishes, cabinetry, and keyed notes",
        general_notes=spec_package["general_notes"],
        wall_legend=spec_package["wall_legend"],
        opening_tags=[row["opening_id"] for row in opening_schedule],
        cabinet_tags=list(zip([row["cabinet_id"] for row in cabinet_schedule], cabinet_items)),
        wall_tags=wall_tags,
        finish_tags=finish_tags,
        cabinet_elevation_tags=cabinet_elevation_tags,
        keyed_notes=keyed_notes,
        title_block=title_block,
        sheet_number="A101",
        sheet_title="Concept Plan / Tags",
    )
    to_sheet_svg(
        plan,
        plan_sheet_path,
        title=f"{plan.unit_name} Plan / Tags",
        subtitle="Dimensioned concept plan with wall, finish, cabinet, and note tags",
        general_notes=spec_package["general_notes"],
        wall_legend=spec_package["wall_legend"],
        opening_tags=[row["opening_id"] for row in opening_schedule],
        cabinet_tags=list(zip([row["cabinet_id"] for row in cabinet_schedule], cabinet_items)),
        wall_tags=wall_tags,
        finish_tags=finish_tags,
        cabinet_elevation_tags=cabinet_elevation_tags,
        keyed_notes=keyed_notes,
        title_block=title_block,
        sheet_number="A101",
        sheet_title="Plan / Tags",
    )
    to_cover_sheet_svg(
        cover_sheet_path,
        title=f"{plan.unit_name} Drawing Set",
        subtitle="Concept-level interior design documentation package",
        title_block=title_block,
        sheet_entries=drawing_set,
        highlights=[
            f"Concept direction: {design_brief['concept_name']}",
            f"Space plan score: {analysis_report['score']}",
            "Includes 3D model, schedules, renovation package, and starter sheet set.",
        ],
    )
    to_elevation_sheet_svg(
        elevations_sheet_path,
        title_block=title_block,
        elevations=elevation_views,
        sheet_number="A201",
        sheet_title="Interior Elevations",
    )
    to_room_elevation_sheet_svg(
        room_elevations_sheet_path,
        title_block=title_block,
        room_views=room_elevation_views,
        sheet_number="A202",
        sheet_title="Grouped Interior Elevations",
    )
    to_notes_sheet_svg(
        notes_sheet_path,
        title_block=title_block,
        general_notes=spec_package["general_notes"],
        wall_legend=spec_package["wall_legend"],
        keyed_notes=keyed_notes,
        schedule_refs=schedule_refs,
    )
    write_print_package(print_package_path, title_block, drawing_set, out_dir)

    manifest = {
        "unit": plan.unit_name,
        "palette": palette,
        "answers": answers,
        "space_plan_score": analysis_report["score"],
        "outputs": {
            "dimensioned_plan_svg": str(dimensioned_plan_path),
            "construction_sheet_svg": str(construction_sheet_path),
            "cover_sheet_svg": str(cover_sheet_path),
            "plan_sheet_svg": str(plan_sheet_path),
            "elevations_sheet_svg": str(elevations_sheet_path),
            "room_elevations_sheet_svg": str(room_elevations_sheet_path),
            "notes_sheet_svg": str(notes_sheet_path),
            "sheet_index_json": str(sheet_index_json_path),
            "sheet_index_md": str(sheet_index_md_path),
            "drawing_set_print_html": str(print_package_path),
            "obj": str(obj_path),
            "mtl": str(mtl_path),
            "shopping_list_json": str(out_dir / "shopping_list.json"),
            "shopping_list_csv": str(out_dir / "shopping_list.csv"),
            "space_plan_report_json": str(out_dir / "space_plan_report.json"),
            "space_plan_report_md": str(out_dir / "space_plan_report.md"),
            "design_brief_json": str(out_dir / "design_brief.json"),
            "design_brief_md": str(out_dir / "design_brief.md"),
            "renovation_package_json": str(out_dir / "renovation_package.json"),
            "renovation_package_md": str(out_dir / "renovation_package.md"),
            "renovation_schedule_json": str(out_dir / "renovation_schedule.json"),
            "renovation_schedule_csv": str(out_dir / "renovation_schedule.csv"),
            "renovation_schedule_md": str(out_dir / "renovation_schedule.md"),
            "finish_schedule_json": str(out_dir / "finish_schedule.json"),
            "finish_schedule_csv": str(out_dir / "finish_schedule.csv"),
            "finish_schedule_md": str(out_dir / "finish_schedule.md"),
            "room_schedule_json": str(out_dir / "room_schedule.json"),
            "room_schedule_csv": str(out_dir / "room_schedule.csv"),
            "room_schedule_md": str(out_dir / "room_schedule.md"),
            "wall_schedule_json": str(out_dir / "wall_schedule.json"),
            "wall_schedule_csv": str(out_dir / "wall_schedule.csv"),
            "wall_schedule_md": str(out_dir / "wall_schedule.md"),
            "opening_schedule_json": str(out_dir / "opening_schedule.json"),
            "opening_schedule_csv": str(out_dir / "opening_schedule.csv"),
            "opening_schedule_md": str(out_dir / "opening_schedule.md"),
            "cabinet_schedule_json": str(out_dir / "cabinet_schedule.json"),
            "cabinet_schedule_csv": str(out_dir / "cabinet_schedule.csv"),
            "cabinet_schedule_md": str(out_dir / "cabinet_schedule.md"),
            "spec_package_json": str(out_dir / "spec_package.json"),
            "spec_package_md": str(out_dir / "spec_package.md"),
        },
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a 3D model (OBJ) and shopping list from a floor plan."
    )
    parser.add_argument("--layout", default="mercer_layout.json")
    parser.add_argument("--answers", help="Path to answers JSON file.")
    parser.add_argument(
        "--style-images",
        nargs="*",
        default=[],
        help="Paths to style inspiration images.",
    )
    parser.add_argument("--out-dir", default="outputs")
    args = parser.parse_args()

    answers = load_answers(Path(args.answers)) if args.answers else prompt_questions()
    out_dir = Path(args.out_dir)
    run_design(
        Path(args.layout),
        answers,
        [Path(p) for p in args.style_images],
        out_dir,
    )
    print(f"Wrote outputs to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
