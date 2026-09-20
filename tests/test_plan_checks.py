"""Deterministic geometry and layout-validity tests. Run: python3 -m unittest discover -s tests -v"""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from floorplan_agent import FloorPlan, Furniture, Opening, build_plan, build_rooms, place_furniture, room_from_polygon  # noqa: E402
from geometry import (  # noqa: E402
    box_within_polygon,
    polygon_within_polygon,
    polygons_overlap,
    segments_properly_intersect,
)
from plan_checks import (  # noqa: E402
    door_clearance_zones,
    find_door_conflicts,
    find_opening_overruns,
    find_zone_overlaps,
    find_zone_shell_violations,
    opening_overrun,
    resolve_door_conflicts,
)

SAMPLE_LAYOUT = ROOT / "mercer_layout.json"
SQUARE = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
# L-shape: 10x10 with the top-right 5x5 quadrant removed.
L_SHAPE = [(0.0, 0.0), (10.0, 0.0), (10.0, 5.0), (5.0, 5.0), (5.0, 10.0), (0.0, 10.0)]


def make_plan(rooms, openings=(), furniture=(), shell=None):
    return FloorPlan("test", 20.0, 20.0, shell or [], list(rooms), list(openings), list(furniture))


class GeometryTests(unittest.TestCase):
    def test_proper_intersection_ignores_touching_endpoints(self):
        self.assertTrue(segments_properly_intersect((0, 0), (2, 2), (0, 2), (2, 0)))
        self.assertFalse(segments_properly_intersect((0, 0), (2, 0), (2, 0), (2, 2)))
        self.assertFalse(segments_properly_intersect((0, 0), (2, 0), (0, 1), (2, 1)))

    def test_box_within_polygon_rejects_notch(self):
        self.assertTrue(box_within_polygon((1, 1, 4, 4), L_SHAPE))
        self.assertTrue(box_within_polygon((0, 0, 5, 10), L_SHAPE))  # shares edges
        # Corners all inside/on boundary, but the box crosses the notch.
        self.assertFalse(box_within_polygon((4, 4, 6, 6), L_SHAPE))
        self.assertFalse(box_within_polygon((3, 6, 8, 8), L_SHAPE))

    def test_polygon_within_polygon_shared_edges_ok(self):
        self.assertTrue(polygon_within_polygon([(0, 0), (5, 0), (5, 5), (0, 5)], SQUARE))
        self.assertFalse(polygon_within_polygon([(8, 8), (12, 8), (12, 12), (8, 12)], SQUARE))
        self.assertFalse(polygon_within_polygon([(4, 4), (6, 4), (6, 6), (4, 6)], L_SHAPE))

    def test_polygons_overlap_distinguishes_touching_from_overlap(self):
        left = [(0, 0), (5, 0), (5, 10), (0, 10)]
        right = [(5, 0), (10, 0), (10, 10), (5, 10)]
        self.assertFalse(polygons_overlap(left, right))
        band = [(4, 3), (8, 3), (8, 4), (4, 4)]
        self.assertTrue(polygons_overlap(left, band))
        self.assertTrue(polygons_overlap(SQUARE, SQUARE))


class OpeningTests(unittest.TestCase):
    def setUp(self):
        self.room = room_from_polygon("Room", "office", SQUARE)

    def test_opening_fits(self):
        door = Opening("door", 3.0, 3.0, "Room", edge_index=0)
        self.assertEqual(opening_overrun(self.room, door), 0.0)

    def test_opening_overrun_is_measured(self):
        door = Opening("door", 8.5, 3.0, "Room", edge_index=0)
        self.assertAlmostEqual(opening_overrun(self.room, door), 1.5)
        negative = Opening("door", -0.5, 3.0, "Room", edge_index=0)
        self.assertAlmostEqual(opening_overrun(self.room, negative), 0.5)
        plan = make_plan([self.room], [door])
        self.assertEqual(len(find_opening_overruns(plan)), 1)

    def test_interior_door_gets_swing_and_approach_zones(self):
        left = room_from_polygon("Left", "office", [(0, 0), (10, 0), (10, 10), (0, 10)])
        right = room_from_polygon("Right", "living", [(10, 0), (20, 0), (20, 10), (10, 10)])
        # Left room's east edge (10,0)->(10,10), door 2..5 ft along it.
        door = Opening("door", 2.0, 3.0, "Left", edge_index=1)
        zones = door_clearance_zones(left, door, [left, right])
        by_side = {zone["side"]: zone for zone in zones}
        self.assertEqual(set(by_side), {"swing", "approach"})
        self.assertEqual(by_side["swing"]["room"], "Left")
        self.assertEqual(by_side["swing"]["box"], (7.0, 2.0, 10.0, 5.0))
        self.assertEqual(by_side["approach"]["room"], "Right")
        self.assertEqual(by_side["approach"]["box"], (10.0, 2.0, 13.0, 5.0))

    def test_exterior_door_only_has_swing_zone(self):
        door = Opening("door", 2.0, 3.0, "Room", edge_index=0)
        zones = door_clearance_zones(self.room, door, [self.room])
        self.assertEqual([zone["side"] for zone in zones], ["swing"])

    def test_windows_have_no_zones(self):
        window = Opening("window", 2.0, 3.0, "Room", edge_index=0)
        self.assertEqual(door_clearance_zones(self.room, window, [self.room]), [])


class DoorConflictTests(unittest.TestCase):
    def setUp(self):
        self.room = room_from_polygon("Room", "office", SQUARE)
        self.door = Opening("door", 2.0, 3.0, "Room", edge_index=0)  # bottom wall, x 2..5, swing y 0..3

    def test_detects_floor_item_in_swing_zone(self):
        chair = Furniture("Chair", 3.0, 1.0, 2.0, 2.0, "Room")
        plan = make_plan([self.room], [self.door], [chair])
        conflicts = find_door_conflicts(plan)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["item"], "Chair")

    def test_ignores_wall_mounted_and_soft_items(self):
        upper = Furniture("Upper Cabinets", 3.0, 1.0, 2.0, 1.0, "Room", z=4.5)
        rug = Furniture("Outdoor Rug", 1.0, 0.5, 6.0, 4.0, "Room")
        plan = make_plan([self.room], [self.door], [upper, rug])
        self.assertEqual(find_door_conflicts(plan), [])

    def test_resolver_moves_item_out_and_is_deterministic(self):
        chair = Furniture("Chair", 3.0, 1.0, 2.0, 2.0, "Room")
        plan = make_plan([self.room], [self.door], [chair])
        result = resolve_door_conflicts(plan)
        self.assertEqual(len(result["moves"]), 1)
        self.assertEqual(result["unresolved"], [])
        self.assertEqual((chair.x, chair.y), (3.0, 3.0))  # slid straight off the swing zone
        self.assertTrue(box_within_polygon((chair.x, chair.y, chair.x + chair.w, chair.y + chair.h), SQUARE))
        self.assertEqual(find_door_conflicts(plan), [])
        again = make_plan([self.room], [self.door], [Furniture("Chair", 3.0, 1.0, 2.0, 2.0, "Room")])
        self.assertEqual(resolve_door_conflicts(again), result)

    def test_resolver_never_creates_overlap_or_leaves_room(self):
        chair = Furniture("Chair", 3.0, 1.0, 2.0, 2.0, "Room")
        blocker = Furniture("Table", 2.0, 3.0, 4.0, 2.0, "Room")  # directly above the swing zone
        plan = make_plan([self.room], [self.door], [chair, blocker])
        resolve_door_conflicts(plan)
        boxes = [(item.x, item.y, item.x + item.w, item.y + item.h) for item in plan.furniture]
        self.assertFalse(boxes[0][0] < boxes[1][2] and boxes[0][2] > boxes[1][0] and boxes[0][1] < boxes[1][3] and boxes[0][3] > boxes[1][1])
        self.assertTrue(box_within_polygon(boxes[0], SQUARE))
        self.assertEqual(find_door_conflicts(plan), [])

    def test_unresolvable_item_is_left_and_reported(self):
        tiny = room_from_polygon("Tiny", "closet", [(0, 0), (4, 0), (4, 4), (0, 4)])
        door = Opening("door", 0.5, 3.0, "Tiny", edge_index=0)
        bench = Furniture("Storage Bench", 0.2, 0.2, 3.6, 3.6, "Tiny")
        plan = make_plan([tiny], [door], [bench])
        result = resolve_door_conflicts(plan)
        self.assertEqual(result["moves"], [])
        self.assertEqual([entry["members"] for entry in result["unresolved"]], [["Storage Bench"]])
        self.assertEqual((bench.x, bench.y), (0.2, 0.2))
        self.assertEqual(len(find_door_conflicts(plan)), 1)


class FurnitureGroupTests(unittest.TestCase):
    """Groups move as one unit; a group that cannot move as a unit is reported, never split."""

    def desk_set(self, room_name="Office"):
        desk = Furniture("Desk", 1.0, 1.0, 4.0, 2.0, room_name, group="desk-set")
        chair = Furniture("Desk Chair", 5.5, 1.0, 2.0, 2.0, room_name, group="desk-set")
        return desk, chair

    def test_group_moves_together_and_stays_adjacent(self):
        room = room_from_polygon("Office", "office", [(0, 0), (12, 0), (12, 10), (0, 10)])
        door = Opening("door", 5.0, 3.0, "Office", edge_index=0)  # zone x 5..8, y 0..3: hits the chair only
        desk, chair = self.desk_set()
        plan = make_plan([room], [door], [desk, chair])
        result = resolve_door_conflicts(plan)
        self.assertEqual(sorted(move["item"] for move in result["moves"]), ["Desk", "Desk Chair"])
        self.assertEqual(result["unresolved"], [])
        # Same shift applied to both, so the relative position is unchanged.
        self.assertEqual((chair.x - desk.x, chair.y - desk.y), (4.5, 0.0))
        self.assertEqual((desk.x, desk.y, chair.x, chair.y), (1.0, 3.0, 5.5, 3.0))
        self.assertEqual(find_door_conflicts(plan), [])

    def test_group_is_reported_not_split_when_only_a_member_could_escape(self):
        # 12 x 4.5 room: the chair alone could slide +x out of the zone, but the desk
        # cannot follow (the desk would need 7 ft, pushing the chair through the wall),
        # and nothing can move +y. Expect: no move at all, group listed as unresolved.
        room = room_from_polygon("Office", "office", [(0, 0), (12, 0), (12, 4.5), (0, 4.5)])
        door = Opening("door", 5.0, 3.0, "Office", edge_index=0)
        desk, chair = self.desk_set()
        plan = make_plan([room], [door], [desk, chair])
        # Sanity: a lone chair with no group would have been movable.
        lone = make_plan([room], [door], [Furniture("Desk", 1.0, 1.0, 4.0, 2.0, "Office"), Furniture("Desk Chair", 5.5, 1.0, 2.0, 2.0, "Office")])
        self.assertEqual([m["item"] for m in resolve_door_conflicts(lone)["moves"]], ["Desk Chair"])
        result = resolve_door_conflicts(plan)
        self.assertEqual(result["moves"], [])
        self.assertEqual(len(result["unresolved"]), 1)
        self.assertEqual(result["unresolved"][0]["group"], "desk-set")
        self.assertEqual(result["unresolved"][0]["members"], ["Desk", "Desk Chair"])
        self.assertEqual((desk.x, desk.y, chair.x, chair.y), (1.0, 1.0, 5.5, 1.0))
        self.assertEqual(len(find_door_conflicts(plan)), 1)

    def test_groups_are_scoped_to_a_room(self):
        left = room_from_polygon("Left", "office", [(0, 0), (12, 0), (12, 10), (0, 10)])
        right = room_from_polygon("Right", "office", [(12, 0), (24, 0), (24, 10), (12, 10)])
        door = Opening("door", 5.0, 3.0, "Left", edge_index=0)
        desk, chair = self.desk_set("Left")
        other = Furniture("Desk", 13.0, 1.0, 4.0, 2.0, "Right", group="desk-set")
        plan = make_plan([left, right], [door], [desk, chair, other])
        result = resolve_door_conflicts(plan)
        self.assertEqual(sorted(move["item"] for move in result["moves"]), ["Desk", "Desk Chair"])
        self.assertEqual((other.x, other.y), (13.0, 1.0))


class ZoneTests(unittest.TestCase):
    def test_zone_outside_shell_and_zone_overlap(self):
        shell = L_SHAPE
        good = room_from_polygon("Good", "office", [(0, 0), (5, 0), (5, 5), (0, 5)])
        bad = room_from_polygon("Bad", "closet", [(4, 4), (8, 4), (8, 8), (4, 8)])
        plan = make_plan([good, bad], shell=shell)
        self.assertEqual([p["room"] for p in find_zone_shell_violations(plan)], ["Bad"])
        self.assertEqual([p["rooms"] for p in find_zone_overlaps(plan)], [["Good", "Bad"]])


class SampleLayoutTests(unittest.TestCase):
    def test_sample_layout_is_geometrically_valid(self):
        from design_agent import validate_plan

        plan = build_plan(SAMPLE_LAYOUT)
        validate_plan(plan)
        self.assertEqual(find_opening_overruns(plan), [])
        self.assertEqual(find_zone_shell_violations(plan), [])
        self.assertEqual(find_zone_overlaps(plan), [])
        self.assertEqual(find_door_conflicts(plan), [])
        for item in plan.furniture:
            room = next(room for room in plan.rooms if room.name == item.room_name)
            self.assertTrue(
                box_within_polygon((item.x, item.y, item.x + item.w, item.y + item.h), room.polygon),
                f"{item.name} leaves {room.name}",
            )

    def test_sample_layout_rules_need_the_door_pass(self):
        layout = json.loads(SAMPLE_LAYOUT.read_text(encoding="utf-8"))
        unit, width, height, shell, rooms, openings = build_rooms(layout)
        raw = FloorPlan(unit, width, height, shell, rooms, openings, place_furniture(rooms))
        self.assertGreater(len(find_door_conflicts(raw)), 0)
        result = resolve_door_conflicts(raw)
        self.assertGreater(len(result["moves"]), 0)
        self.assertEqual(result["unresolved"], [])
        self.assertEqual(find_door_conflicts(raw), [])

    def test_validate_plan_rejects_overrunning_opening(self):
        from design_agent import validate_plan

        layout = json.loads(SAMPLE_LAYOUT.read_text(encoding="utf-8"))
        broken = copy.deepcopy(layout)
        broken["openings"][1]["offset"] = 10.5  # the original sample value: 2.5 ft door starting 10.5 ft along a 12 ft wall
        unit, width, height, shell, rooms, openings = build_rooms(broken)
        plan = FloorPlan(unit, width, height, shell, rooms, openings, [])
        with self.assertRaises(ValueError):
            validate_plan(plan)


if __name__ == "__main__":
    unittest.main()
