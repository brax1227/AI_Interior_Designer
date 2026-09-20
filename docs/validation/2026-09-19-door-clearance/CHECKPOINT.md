# Checkpoint INTERIOR-20260919-01: layout validity of the Mercer rule-based prototype

Date: 2026-09-19. Writer: Claude Code (sole primary). Layout: `mercer_layout.json`
(synthetic sample approximated from a marketing floor-plan render; every dimension is
an assumption, nothing is field-measured).

Scope of this proof: does the generator produce a *practically valid* concept plan
(rooms inside the shell, no furniture overlaps, doors usable)? It is not a
build-ready, structural, egress, or code-compliance check and must not be read as one.

## What the baseline actually produced

Run: `python3 design_agent.py --layout mercer_layout.json --answers sample_answers.json`
on commit 943ceb1. The generator's own report said "No major overlap or
out-of-bounds issues detected" while an independent geometry audit found:

| Check | Baseline result |
| --- | --- |
| Furniture inside its room polygon | pass (0 items outside) |
| Furniture-furniture overlap (floor level) | pass (0) |
| Door swing/approach obstructed | **7 conflicts across 6 of 8 doors**, not detected |
| Opening fits on its wall edge | **3 overruns** (bedroom door ran past the patio corner; bathroom door was 2.4 ft on a 1.5 ft edge; entry door 0.4 ft too long), not detected |
| Zone inside shell | **Closet/Hall stuck 12 sq ft outside the shell notch**, not detected |
| Zone-zone overlap | **Kitchen and Living Room overlapped ~4 sq ft**, not detected |
| Room area basis | bounding box, so L-shaped rooms over-reported (Kitchen 189 vs 146 sq ft) |
| Documentation | README said 42 x 26 ft / 1,092 sq ft; layout is a 42 x 32 ft box, shell ~1,105 sq ft |

Artifacts: `before_floorplan.svg` / `.png`, `before_space_plan_report.md`.

## Fix delivered (highest-impact reproducible issue: doors)

1. `plan_checks.py`: deterministic checks for opening overrun, zone-in-shell, zone
   overlap, furniture-in-polygon, and door clearance (swing square inside the door's
   room plus a 3 ft approach strip on the far side when that side is another room).
2. `resolve_door_conflicts`: after rule-based placement, slides floor-level items out
   of door zones along the door normal or tangent, shortest valid move wins, never
   leaving the room polygon or overlapping another floor item. Unresolvable items stay
   and are reported.
3. `validate_plan` now rejects overrunning openings and zones outside the shell;
   `analyze_plan` reports door conflicts, zone overlaps, and uses polygon area.
4. `geometry.py`: proper segment intersection, box/polygon containment that respects
   notches, polygon overlap that ignores shared edges.
5. Sample data corrected (see `git diff 943ceb1 -- mercer_layout.json`): three
   openings, closet polygon, living-room/kitchen boundary, laundry door moved to the
   south wall beside the entry as shown in the source render.
6. Tests: `tests/test_plan_checks.py`, 18 cases, `python3 -m unittest discover -s tests`.

Result on the corrected sample: raw placement still produces 10 door conflicts; the
pass resolves all 10 with these moves (feet, plan coordinates, y up):

| Item | Room | From | To | Cleared |
| --- | --- | --- | --- | --- |
| Nightstand | Bedroom | (10.0, 15.0) | (9.5, 15.0) | Bedroom door |
| Queen Bed | Bedroom | (4.5, 10.3) | (4.5, 8.8) | Bathroom door |
| Dining Table | Dining | (17.5, 20.25) | (17.5, 19.75) | Dining door |
| Kitchen Cabinet Run | Kitchen | (37.6, 20.0) | (37.6, 21.0) | Kitchen door |
| TV Console | Living Room | (33.5, 14.0) | (33.5, 13.5) | Kitchen door |
| Dryer | Laundry | (39.3, 24.8) | (39.3, 26.55) | Laundry door |
| Patio Table | Patio | (20.9, 1.9) | (20.9, 0.65) | Office/Den patio door |
| Patio Chair | Patio | (18.4, 2.1) | (18.4, 1.35) | Office/Den patio door |
| Desk | Office/Den | (15.0, 7.0) | (14.25, 7.0) | Office/Den patio door |
| Desk Chair | Office/Den | (19.5, 7.0) | (19.5, 10.0) | Office/Den patio door |

After state: 0 door conflicts, 0 overlaps, 0 items outside rooms, 0 overruns, zones
valid. Artifacts: `after_floorplan.svg` / `.png`, `after_space_plan_report.md`.
Dashed amber boxes in the SVG are the door zones.

## Capability / gap table

| Area | Works today | Gap (honest) |
| --- | --- | --- |
| Geometry model | Polygon shell, polygon zones, edge-indexed openings, y-up feet | No wall thickness in geometry (0.25 ft drawn only); no units other than feet |
| Room/shell containment | Checked and enforced at validation | ~100 sq ft of shell is unassigned circulation; fine conceptually, never labelled |
| Furniture containment | Polygon-aware, notch-safe | Placement rules position items relative to the bounding box, so L-shaped rooms get odd layouts (kitchen items drift) |
| Furniture overlap | Detected for floor-level items with height ranges | Rule placement can still generate overlaps on other layouts; only doors are auto-resolved |
| Door clearance | Detected, drawn, auto-resolved; unresolved cases reported | Resolver moves items one at a time, so groups separate (desk chair ends 1 ft from desk; dryer offset from washer); no hinge-side or in/out swing logic; approach depth 3 ft is a fixed assumption |
| Windows | Drawn, in schedules | No check for furniture blocking windows or sills |
| Score | Reports issues and per-room counts | "Overall score" is dominated by a clearance model that penalises built-ins for touching walls (14/100 with zero issues). Misleading; needs redesign, not tuning |
| Sheets / 3D / schedules | Generated from the same plan | Downstream documents inherit any geometry error; none of them are construction documents |
| Web app | Form -> outputs | Not exercised in this checkpoint beyond import; invalid layouts now raise ValueError which the server already catches |

## Assumptions introduced or changed in this checkpoint

- Door zones: swing depth = door width inside the owning room; approach depth =
  min(3 ft, door width) on the far side. Exterior doors get no approach zone.
- Items with z > 0.1 ft (upper cabinets, wall shelves, mirrors) and rugs never block doors.
- Sample layout edits are drawn from the render, not measurements: bedroom door at
  the closet end of the bedroom/office wall; bathroom door on the bedroom wall;
  laundry door on its south wall beside the entry; living room stops at y = 18.

## Next practical validation step (recommendation)

Replace the scoring model before anyone sees a number: drop the wall-touch penalty for
built-ins and appliances, and score on the four hard checks (containment, overlap,
door clearance, walkable path between doors). Then run the same audit on one
*different* synthetic layout (a plain 12 x 14 ft rectangle with one door) to prove
the placement rules are not Mercer-specific. Both are small, deterministic, and
testable; neither needs photos, paid APIs, or user homework.
