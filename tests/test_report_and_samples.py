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
        self.assertEqual(self.report["checks"]["door_clearance"]["finding_count"], 2)


class KnownGroupingGapTests(unittest.TestCase):
    """The door pass moves items one at a time; furniture groups can separate.

    These are recorded as expected failures so the gap stays visible in the test
    output until grouping is implemented.
    """

    @unittest.expectedFailure
    def test_desk_chair_stays_at_the_desk_on_mercer(self):
        plan = build_plan(MERCER)
        desk = next(item for item in plan.furniture if item.name == "Desk")
        chair = next(item for item in plan.furniture if item.name == "Desk Chair")
        gap_x = max(chair.x - (desk.x + desk.w), desk.x - (chair.x + chair.w), 0.0)
        gap_y = max(chair.y - (desk.y + desk.h), desk.y - (chair.y + chair.h), 0.0)
        self.assertLessEqual(max(gap_x, gap_y), 1.0)

    @unittest.expectedFailure
    def test_washer_and_dryer_stay_aligned_on_mercer(self):
        plan = build_plan(MERCER)
        washer = next(item for item in plan.furniture if item.name == "Washer")
        dryer = next(item for item in plan.furniture if item.name == "Dryer")
        self.assertAlmostEqual(washer.y, dryer.y)


if __name__ == "__main__":
    unittest.main()
