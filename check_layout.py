#!/usr/bin/env python3
"""Check-only report for a layout file: runs every modelled check and prints findings.

Unlike design_agent.py this never raises on an invalid layout, so it can be used to
inspect deliberately broken inputs. Exit code is 1 when any modelled check fails.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from design_agent import analyze_plan, apply_design_preferences, normalize_answers, write_analysis_report
from floorplan_agent import FloorPlan, build_rooms, load_layout, place_furniture, to_svg
from plan_checks import find_door_conflicts, resolve_door_conflicts

DEFAULT_ANSWERS = {
    "style_keywords": "modern cozy",
    "palette_preference": "warm neutrals",
    "budget_level": "mid",
    "work_from_home": "yes",
    "pets": "none",
    "lighting_pref": "mixed",
    "storage_priority": "medium",
    "must_have": "none",
}


def build_checked_plan(layout_path: Path, answers: dict, resolve: bool = True) -> tuple[FloorPlan, dict]:
    layout = load_layout(layout_path)
    unit_name, width_ft, height_ft, shell, rooms, openings = build_rooms(layout)
    plan = FloorPlan(unit_name, width_ft, height_ft, shell, rooms, openings, place_furniture(rooms))
    apply_design_preferences(plan, normalize_answers(answers))
    raw_door_conflicts = len(find_door_conflicts(plan))
    moves = resolve_door_conflicts(plan) if resolve else []
    return plan, {"raw_door_conflicts": raw_door_conflicts, "door_pass_moves": moves}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layout", required=True)
    parser.add_argument("--answers", help="Answers JSON; defaults mirror the CLI prompts")
    parser.add_argument("--no-resolve", action="store_true", help="Skip the door-aware placement pass")
    parser.add_argument("--json", dest="json_out", help="Write the full report JSON here")
    parser.add_argument("--md", dest="md_out", help="Write the Markdown report here")
    parser.add_argument("--svg", dest="svg_out", help="Write the furnished plan SVG here")
    args = parser.parse_args()

    answers = json.loads(Path(args.answers).read_text(encoding="utf-8")) if args.answers else dict(DEFAULT_ANSWERS)
    plan, pass_info = build_checked_plan(Path(args.layout), answers, resolve=not args.no_resolve)
    report = analyze_plan(plan)
    report["door_pass"] = pass_info

    print(f"{plan.unit_name}")
    for name, check in report["checks"].items():
        count = "n/a" if check["finding_count"] is None else check["finding_count"]
        print(f"  {name:16s} {check['status']:10s} findings={count}")
        for finding in check["findings"]:
            print(f"    - {finding['message']}")
    print(f"  door pass: {pass_info['raw_door_conflicts']} raw conflicts, {len(pass_info['door_pass_moves'])} items moved")
    print(f"  {report['disclaimer']}")

    if args.json_out or args.md_out:
        json_path = Path(args.json_out) if args.json_out else Path(args.md_out).with_suffix(".json")
        md_path = Path(args.md_out) if args.md_out else Path(args.json_out).with_suffix(".md")
        write_analysis_report(report, json_path, md_path)
    if args.svg_out:
        to_svg(plan, Path(args.svg_out))
    return 1 if report["modelled_violation_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
