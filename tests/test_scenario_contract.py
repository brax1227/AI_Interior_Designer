"""Scenario contract v0.1: validator, offline example, and public-plan sample layouts."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from check_layout import DEFAULT_ANSWERS, build_checked_plan  # noqa: E402
from design_agent import analyze_plan, run_design  # noqa: E402
from scenario_tools import CONTRACT_VERSION, build_scenario, validate_scenario  # noqa: E402

SCENARIO = ROOT / "scenarios" / "houseplans_430_40_offline.json"
SCHEMA = ROOT / "contracts" / "property_design_scenario.schema.json"
PLANS = [
    ROOT / "samples" / "public_plans" / "houseplans_430_40_master_bedroom.json",
    ROOT / "samples" / "public_plans" / "houseplans_430_40_great_room.json",
]


def load_scenario():
    return json.loads(SCENARIO.read_text(encoding="utf-8"))


class PublicPlanLayoutTests(unittest.TestCase):
    def test_layouts_carry_published_and_assumed_provenance(self):
        for path in PLANS:
            layout = json.loads(path.read_text(encoding="utf-8"))
            provenance = layout["provenance"]
            self.assertEqual(provenance["source"]["publisher"], "Houseplans.com")
            self.assertEqual(provenance["source"]["accessed"], "2026-09-21")
            self.assertTrue(provenance["published_dimensions"])
            self.assertTrue(provenance["assumed"])
            self.assertTrue(all(opening.get("assumed") is True for opening in layout["openings"]), path.name)

    def test_published_room_sizes_match_the_model(self):
        master = json.loads(PLANS[0].read_text(encoding="utf-8"))
        self.assertAlmostEqual(master["width_ft"], 12 + 2 / 12, places=3)  # 12'2"
        self.assertEqual(master["height_ft"], 14)
        great = json.loads(PLANS[1].read_text(encoding="utf-8"))
        self.assertEqual((great["width_ft"], great["height_ft"]), (15, 15))

    def test_both_rooms_pass_modelled_checks_with_walkable_path_unmeasured(self):
        for path in PLANS:
            plan, info = build_checked_plan(path, dict(DEFAULT_ANSWERS))
            report = analyze_plan(plan)
            self.assertEqual(report["modelled_violation_count"], 0, path.name)
            self.assertEqual(report["checks"]["walkable_path"]["status"], "unmeasured")
            self.assertEqual(info["door_pass_unresolved"], [])


class OfflineScenarioTests(unittest.TestCase):
    def test_offline_scenario_is_valid(self):
        scenario = load_scenario()
        self.assertEqual(validate_scenario(scenario), [])
        self.assertEqual(scenario["contract_version"], CONTRACT_VERSION)

    def test_offline_scenario_is_marked_example_with_published_facts_kept(self):
        scenario = load_scenario()
        self.assertTrue(scenario["example"])
        self.assertEqual(scenario["property"]["data_status"], "example_public_plan")
        self.assertIn("Not a real", scenario["property"]["data_status_note"])
        self.assertEqual(scenario["property"]["source"]["kind"], "public_stock_plan")
        names = {r["name"]: r for block in scenario["layouts"]["after"]["rooms"] for r in block["rooms"]}
        self.assertEqual(names["Master Bedroom"]["published_dimensions"], "12' 2\" x 14'")
        self.assertEqual(names["Great Room"]["published_dimensions"], "15' x 15'")

    def test_producer_pins_the_code_revision_that_has_the_tool(self):
        scenario = load_scenario()
        producer = scenario["producer"]
        self.assertEqual(producer["commit"], producer["code_commit"])
        self.assertNotEqual(producer["commit"], "cd9c190")  # that commit predates scenario_tools.py
        self.assertIsInstance(producer["code_commit_exact"], bool)
        self.assertIn("git log", producer["data_revision"])

    def test_offline_scenario_is_honest_about_what_it_does_not_know(self):
        scenario = load_scenario()
        self.assertIsNone(scenario["property"]["address"])
        self.assertEqual(scenario["resale_scenario"]["status"], "not_evaluated")
        self.assertEqual(scenario["resale_scenario"]["comps"], [])
        self.assertIsNone(scenario["resale_scenario"]["value_base"])
        self.assertIsNone(scenario["transaction_costs"]["selling"]["pct_of_sale_price"])
        for item in scenario["renovation_estimate"]["items"]:
            self.assertEqual(item["provenance"]["kind"], "internal_catalog")
            self.assertFalse(item["provenance"]["verified"])
        for block in scenario["layouts"]["after"]["rooms"]:
            self.assertEqual(block["checks"]["walkable_path"], "unmeasured")
            for room in block["rooms"]:
                self.assertEqual(room["dimension_provenance"], "published")
                self.assertEqual(room["openings_provenance"], "assumed")

    def test_schema_and_validator_agree_on_top_level_required_keys(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        scenario = load_scenario()
        for key in schema["required"]:
            self.assertIn(key, scenario, key)
        for key in schema["required"]:
            broken = copy.deepcopy(scenario)
            del broken[key]
            self.assertTrue(validate_scenario(broken), f"validator must reject a scenario missing {key}")
        self.assertEqual(schema["properties"]["contract_version"]["const"], CONTRACT_VERSION)


class ValidatorRejectsTests(unittest.TestCase):
    def setUp(self):
        self.scenario = load_scenario()

    def assert_rejected(self, mutate, fragment):
        broken = copy.deepcopy(self.scenario)
        mutate(broken)
        problems = validate_scenario(broken)
        self.assertTrue(any(fragment in problem for problem in problems), f"expected a problem mentioning {fragment!r}, got {problems}")

    def test_profit_fields_are_rejected(self):
        self.assert_rejected(lambda s: s["resale_scenario"].__setitem__("expected_profit", 25000), "expected_profit")
        self.assert_rejected(lambda s: s["resale_scenario"].__setitem__("roi", 0.2), "roi")

    def test_values_while_not_evaluated_are_rejected(self):
        self.assert_rejected(lambda s: s["resale_scenario"].__setitem__("value_base", 250000), "must be null")

    def test_draft_resale_needs_a_comp(self):
        self.assert_rejected(lambda s: s["resale_scenario"].__setitem__("status", "draft"), "at least one comp")

    def test_band_order_is_enforced(self):
        def mutate(s):
            s["renovation_estimate"]["items"][0]["low"] = s["renovation_estimate"]["items"][0]["high"] + 1
        self.assert_rejected(mutate, "low <= base <= high")

    def test_totals_must_match_items(self):
        self.assert_rejected(lambda s: s["renovation_estimate"]["totals"].__setitem__("base", 1.0), "sum of items")

    def test_provenance_is_required_and_typed(self):
        self.assert_rejected(lambda s: s["renovation_estimate"]["items"][0].pop("provenance"), "provenance")
        self.assert_rejected(lambda s: s["renovation_estimate"]["items"][0]["provenance"].__setitem__("kind", "vibes"), "not in")
        self.assert_rejected(lambda s: s["transaction_costs"]["holding"].pop("provenance"), "holding.provenance")

    def test_walkable_path_cannot_be_dropped(self):
        self.assert_rejected(lambda s: s["layouts"]["after"]["rooms"][0]["checks"].pop("walkable_path"), "walkable_path")

    def test_example_flag_must_agree_with_data_status(self):
        self.assert_rejected(lambda s: s.__setitem__("example", False), "contradicts")
        self.assert_rejected(lambda s: s["property"].__setitem__("data_status", "real_property_verified"), "contradicts")
        self.assert_rejected(lambda s: s["property"].pop("data_status"), "data_status")

    def test_real_verified_requires_owner_measured_dimensions(self):
        def mutate(s):
            s["example"] = False
            s["property"]["data_status"] = "real_property_verified"
        self.assert_rejected(mutate, "owner_measured")

    def test_wrong_contract_version(self):
        self.assert_rejected(lambda s: s.__setitem__("contract_version", "0.2"), "contract_version")


class BuildScenarioTests(unittest.TestCase):
    def test_build_from_fresh_pipeline_runs_reproduces_a_valid_scenario(self):
        with tempfile.TemporaryDirectory() as tmp:
            runs = []
            for path in PLANS:
                out = Path(tmp) / path.stem
                run_design(path, dict(DEFAULT_ANSWERS), [], out)
                runs.append((path, out))
            scenario = build_scenario(
                "test-001",
                "test",
                {"kind": "public_stock_plan", "name": "Houseplans.com plan 430-40", "accessed": "2026-09-21"},
                runs,
            )
        self.assertEqual(validate_scenario(scenario), [])
        committed = load_scenario()
        self.assertEqual(scenario["renovation_estimate"]["totals"], committed["renovation_estimate"]["totals"])
        self.assertEqual(
            [r["name"] for block in scenario["layouts"]["after"]["rooms"] for r in block["rooms"]],
            ["Master Bedroom", "Great Room"],
        )


if __name__ == "__main__":
    unittest.main()
