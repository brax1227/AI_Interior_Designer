"""Transparent-findings report and non-Mercer sample behaviour. Run: python3 -m unittest discover -s tests -v"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from check_layout import DEFAULT_ANSWERS, build_checked_plan  # noqa: E402
from design_agent import analyze_plan, validate_plan  # noqa: E402
from floorplan_agent import build_plan  # noqa: E402
from plan_checks import find_door_conflicts  # noqa: E402

MERCER = ROOT / "mercer_layout.json"
RECT = ROOT / "samples" / "rect_two_room_layout.json"
INFEASIBLE = ROOT / "samples" / "infeasible_group_layout.json"
ADVERSARIAL = ROOT / "samples" / "adversarial_invalid_layout.json"
HARD_CHECKS = ("layout_geometry", "containment", "overlap", "door_clearance")


class ReportShapeTests(unittest.TestCase):
    def setUp(self):
        self.report = analyze_plan(build_plan(MERCER))

    def test_no_aggregate_score(self):
        self.assertNotIn("score", self.report)
        self.assertNotIn("issues", self.report)
        self.assertEqual(self.report["schema_version"], 2)

    def test_each_hard_check_is_reported_separately(self):
        for name in HARD_CHECKS:
            check = self.report["checks"][name]
            self.assertIn(check["status"], {"pass", "fail"})
            self.assertEqual(check["finding_count"], len(check["findings"]))
            self.assertTrue(check["method"])

    def test_walkable_path_is_explicitly_unmeasured(self):
        walkable = self.report["checks"]["walkable_path"]
        self.assertEqual(walkable["status"], "unmeasured")
        self.assertIsNone(walkable["finding_count"])
        self.assertIn("walkable_path", self.report["unmeasured_checks"])

    def test_disclaimer_and_assumptions_travel_with_report(self):
        self.assertIn("does not mean the layout is safe", self.report["disclaimer"])
        self.assertTrue(any("unverified assumptions" in line for line in self.report["assumptions"]))
        self.assertTrue(any("Door clearance" in line for line in self.report["assumptions"]))

    def test_room_stats_use_polygon_area(self):
        kitchen = next(row for row in self.report["rooms"] if row["room"] == "Kitchen")
        self.assertEqual(kitchen["room_area_sqft"], 146.0)  # bounding box would say 189


class RectangularSampleTests(unittest.TestCase):
    def test_rules_and_door_pass_are_not_mercer_specific(self):
        plan, info = build_checked_plan(RECT, dict(DEFAULT_ANSWERS))
        self.assertEqual(info["raw_door_conflicts"], 2)
        self.assertEqual(sorted(move["item"] for move in info["door_pass_moves"]), ["Desk", "Desk Chair"])
        report = analyze_plan(plan)
        for name in HARD_CHECKS:
            self.assertEqual(report["checks"][name]["status"], "pass", name)
        self.assertEqual(report["modelled_violation_count"], 0)
        validate_plan(plan)

    def test_rect_without_door_pass_still_reports_conflicts(self):
        plan, _info = build_checked_plan(RECT, dict(DEFAULT_ANSWERS), resolve=False)
        report = analyze_plan(plan)
        self.assertEqual(report["checks"]["door_clearance"]["status"], "fail")
        self.assertEqual(len(find_door_conflicts(plan)), 2)


class AdversarialSampleTests(unittest.TestCase):
    def setUp(self):
        self.plan, self.info = build_checked_plan(ADVERSARIAL, dict(DEFAULT_ANSWERS))
        self.report = analyze_plan(self.plan)

    def test_validate_plan_rejects_it(self):
        with self.assertRaises(ValueError):
            validate_plan(self.plan)

    def test_every_planted_defect_is_found(self):
        kinds = sorted(f["kind"] for f in self.report["checks"]["layout_geometry"]["findings"])
        self.assertEqual(kinds, ["opening_overrun", "zone_outside_shell", "zone_overlap", "zone_overlap"])
        self.assertEqual(self.report["checks"]["containment"]["status"], "fail")
        self.assertIn("Sofa", [f["item"] for f in self.report["checks"]["containment"]["findings"]])
        self.assertEqual(self.report["checks"]["overlap"]["status"], "fail")
        self.assertEqual(self.report["checks"]["door_clearance"]["status"], "fail")
        self.assertGreater(self.report["modelled_violation_count"], 0)

    def test_unresolvable_conflicts_are_left_visible(self):
        self.assertEqual(self.info["raw_door_conflicts"], 2)
        self.assertEqual(self.info["door_pass_moves"], [])
        self.assertEqual(len(self.info["door_pass_unresolved"]), 2)
        self.assertEqual(self.report["checks"]["door_clearance"]["finding_count"], 2)
        self.assertEqual(len(self.report["door_pass"]["unresolved"]), 2)


def _gap_between(a, b) -> float:
    gap_x = max(b.x - (a.x + a.w), a.x - (b.x + b.w), 0.0)
    gap_y = max(b.y - (a.y + a.h), a.y - (b.y + b.h), 0.0)
    return max(gap_x, gap_y)


class FurnitureGroupOnSamplesTests(unittest.TestCase):
    """Formerly expectedFailure: groups now move as one unit on the real samples."""

    def test_desk_chair_stays_at_the_desk_on_mercer_and_door_is_clear(self):
        plan = build_plan(MERCER)
        desk = next(item for item in plan.furniture if item.name == "Desk")
        chair = next(item for item in plan.furniture if item.name == "Desk Chair")
        self.assertEqual(_gap_between(desk, chair), 0.5)  # the rule's original spacing, preserved
        self.assertEqual(chair.y, desk.y)
        moved = {move["item"]: move for move in plan.door_pass["moves"]}
        self.assertEqual(moved["Desk"]["group"], "desk-set")
        self.assertEqual(moved["Desk"]["to"][1], moved["Desk Chair"]["to"][1])
        self.assertEqual(find_door_conflicts(plan), [])
        self.assertEqual(plan.door_pass["unresolved"], [])

    def test_washer_and_dryer_stay_aligned_on_mercer_and_door_is_clear(self):
        plan = build_plan(MERCER)
        washer = next(item for item in plan.furniture if item.name == "Washer")
        dryer = next(item for item in plan.furniture if item.name == "Dryer")
        self.assertAlmostEqual(washer.y, dryer.y)
        self.assertAlmostEqual(dryer.x - (washer.x + washer.w), 0.4)  # original spacing preserved
        self.assertIn("Washer", [move["item"] for move in plan.door_pass["moves"]])
        self.assertEqual(find_door_conflicts(plan), [])

    def test_rect_sample_moves_desk_set_as_a_unit(self):
        plan, info = build_checked_plan(RECT, dict(DEFAULT_ANSWERS))
        desk = next(item for item in plan.furniture if item.name == "Desk")
        chair = next(item for item in plan.furniture if item.name == "Desk Chair")
        self.assertEqual(_gap_between(desk, chair), 0.5)
        self.assertEqual(chair.y, desk.y)
        self.assertEqual(info["door_pass_unresolved"], [])
        self.assertEqual(analyze_plan(plan)["checks"]["door_clearance"]["status"], "pass")

    def test_infeasible_sample_reports_group_and_never_splits_it(self):
        plan, info = build_checked_plan(INFEASIBLE, dict(DEFAULT_ANSWERS))
        self.assertEqual(info["door_pass_moves"], [])
        self.assertEqual([entry["members"] for entry in info["door_pass_unresolved"]], [["Desk", "Desk Chair"]])
        desk = next(item for item in plan.furniture if item.name == "Desk")
        chair = next(item for item in plan.furniture if item.name == "Desk Chair")
        self.assertEqual((desk.x, desk.y, chair.x, chair.y), (1.0, 1.0, 5.5, 1.0))
        report = analyze_plan(plan)
        self.assertEqual(report["checks"]["door_clearance"]["status"], "fail")
        self.assertEqual(len(report["door_pass"]["unresolved"]), 1)
        self.assertEqual(report["modelled_violation_count"], 1)


if __name__ == "__main__":
    unittest.main()
