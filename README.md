# House Designer - Mercer Agent (MVP)

Project intent and targets: see [docs/NORTH_STAR.md](docs/NORTH_STAR.md) (mirror of the
PM-owned record). Validation checkpoints live under `docs/validation/`.

This is a rule-based interior design and documentation agent for the Mercer
apartment layout. It generates a furnished plan, a 3D model, design guidance,
shopping outputs, renovation concepts, and starter construction-style documents.

The current version supports a more advanced polygon-based Mercer approximation with
an explicit outer shell, irregular room zones, patio geometry, and edge-based
openings for windows and doors.

## Assumptions used

- Overall unit modeled inside a 42 ft x 32 ft bounding box; the shell polygon in
  `mercer_layout.json` encloses about 1,105 sq ft, of which about 1,020 sq ft is
  assigned to named zones (the rest is circulation that no zone claims).
- Room zones are approximated from the source plan image and preserve the visible
  adjacency relationships in the Mercer layout.
- Door and window placements are conceptual and should be field-verified.
- Furniture, cabinetry, and renovation components are placed with rule-based logic
  using typical residential dimensions.

## Run

```bash
python3 floorplan_agent.py --layout mercer_layout.json --out mercer_floorplan.svg
```

Open `mercer_floorplan.svg` to view the output. Dashed amber boxes are door swing
and approach clearances; rule-based furniture is slid out of them after placement.
Furniture groups (desk + chair, washer + dryer) move as one unit. A group that
cannot clear a door as a unit is left where it is and listed as unresolved in the
report; it is never split apart to force a pass.

## Layout validity checks

`plan_checks.py` holds deterministic geometry checks used by both agents:

- openings must fit on their wall edge (`validate_plan` rejects overruns);
- zones must lie inside the shell and must not overlap each other;
- furniture must sit inside its room polygon (notches included);
- floor-level furniture must not overlap or block a door's swing/approach zone.

`outputs/space_plan_report.md` reports each check separately (pass / fail with the
findings) and lists `walkable_path` as **unmeasured** because it is not implemented.
There is deliberately no aggregate score. Zero modelled violations means only that
the modelled checks found nothing; it is not a safety, code-compliance, egress, or
construction-readiness statement. Per-room "heuristic clearance notes" are prompts
from a fixed clearance table, not violations.

Check-only report for any layout, including deliberately broken ones (never raises;
exit code 1 when a modelled check fails):

```bash
python3 check_layout.py --layout samples/adversarial_invalid_layout.json
python3 check_layout.py --layout samples/rect_two_room_layout.json --svg rect.svg --md rect_report.md
```

Synthetic sample layouts and what each is for: [samples/README.md](samples/README.md).
Two rooms from a publicly documented stock plan (published room dimensions, assumed
openings) live in `samples/public_plans/`; the source search and its limits are in
`docs/validation/2026-09-21-public-plan/SOURCE_SHORTLIST.md`.

## Housing dashboard hand-off (scenario contract v0.1)

`contracts/property_design_scenario.schema.json` defines a compact JSON contract:
before/after layout evidence with checks, an itemized renovation estimate with
low/base/high and per-item provenance, separate contingency/holding/selling blocks,
and a resale/comps block that is a scenario, never a valuation or profit claim.
`scenarios/houseplans_430_40_offline.json` is the offline example. See
[docs/integration/HOUSING_SCENARIO_CONTRACT.md](docs/integration/HOUSING_SCENARIO_CONTRACT.md).

```bash
python3 scenario_tools.py scenarios/houseplans_430_40_offline.json
```

```bash
python3 -m unittest discover -s tests -v
```

See `docs/validation/` for a before/after sample of the checks on the Mercer layout.

## Customize

Edit `mercer_layout.json` to adjust room dimensions or rename rooms, then re-run.
Polygon-based layouts can use `shell.points`, `zones[].polygon`, and `openings[].edge_index`.

## 3D model + shopping list

This agent can generate a basic 3D OBJ model and a shopping list. It will prompt
you with design questions and optionally analyze style images (requires Pillow).

```bash
python3 design_agent.py --layout mercer_layout.json --out-dir outputs
```

Optional style images (Pillow required):

```bash
python3 design_agent.py --layout mercer_layout.json --style-images /path/to/img1.jpg /path/to/img2.jpg
```

Outputs are written to `outputs/`:
- `dimensioned_plan.svg`
- `construction_sheet.svg`
- `sheets/G001_cover_sheet.svg`
- `sheets/A101_plan_sheet.svg`
- `sheets/A201_elevations_sheet.svg`
- `sheets/A202_room_elevations_sheet.svg`
- `sheets/A601_notes_sheet.svg`
- `sheet_index.json` + `sheet_index.md`
- `drawing_set_print.html`
- `mercer_model.obj` + `mercer_model.mtl`
- `shopping_list.json` + `shopping_list.csv`
- `space_plan_report.json` + `space_plan_report.md`
- `design_brief.json` + `design_brief.md`
- `renovation_package.json` + `renovation_package.md`
- `renovation_schedule.json` + `renovation_schedule.csv` + `renovation_schedule.md`
- `finish_schedule.json` + `finish_schedule.csv` + `finish_schedule.md`
- `room_schedule.json` + `room_schedule.csv` + `room_schedule.md`
- `wall_schedule.json` + `wall_schedule.csv` + `wall_schedule.md`
- `opening_schedule.json` + `opening_schedule.csv` + `opening_schedule.md`
- `cabinet_schedule.json` + `cabinet_schedule.csv` + `cabinet_schedule.md`
- `spec_package.json` + `spec_package.md`
- `manifest.json`

## Local web app

Start a local server with a simple form UI (binds to loopback only by default;
set `HOST`/`PORT` to change):

```bash
python3 local_server.py
```

Open `http://127.0.0.1:8000` and submit the form. Each run writes to a unique
`outputs/run_YYYYMMDD_HHMMSS_xxxxxx/` folder. The success page summarises the
space-plan checks (including unresolved furniture groups and the unmeasured
walkable-path field) before you open any download. Invalid layouts return HTTP 400
with the reason and leave no run folder. The layout field is a path inside this
workspace, not an upload.

End-to-end test of the web flow on an ephemeral loopback port (cleans up after itself):

```bash
python3 -m unittest tests.test_local_server_e2e -v
```

After generation, click the **3D viewer** link to open an in-browser preview
powered by Three.js.

The web app also links to the generated schedules, the concept construction sheet,
the multi-sheet drawing set, and a lightweight spec package with assumptions,
keyed notes, notes/legend content, wall type definitions, and a browser-friendly
print package for the whole drawing set.

The plan sheet now also carries direct schedule-linked tags for walls, room
finish references, cabinet IDs, and cabinet elevation references so the plan and
documentation read more like a coordinated drawing package.

The drawing set also includes an elevation sheet keyed to the `E###` references
shown on plan, giving the cabinetry and built-ins an actual vertical view rather
than just a tag.

It now also includes a grouped room-elevation sheet that composes kitchen,
bathroom, and laundry wall views with cabinetry, fixtures, and appliances in the
same elevation context.

Those grouped elevations now include selected wall labels, finish/material
callouts derived from the finish schedule, and simple detail-bubble references
for likely build-critical conditions.

The sample Mercer layout now also includes approximate `openings` for doors and
windows, which are used for SVG/3D wall gaps and space-planning analysis.
