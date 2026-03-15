# House Designer - Mercer Agent (MVP)

This is a rule-based interior design and documentation agent for the Mercer
apartment layout. It generates a furnished plan, a 3D model, design guidance,
shopping outputs, renovation concepts, and starter construction-style documents.

The current version supports a more advanced polygon-based Mercer approximation with
an explicit outer shell, irregular room zones, patio geometry, and edge-based
openings for windows and doors.

## Assumptions used

- Overall unit modeled as 42 ft x 26 ft (1,092 sq ft).
- Room zones are approximated from the source plan image and preserve the visible
  adjacency relationships in the Mercer layout.
- Door and window placements are conceptual and should be field-verified.
- Furniture, cabinetry, and renovation components are placed with rule-based logic
  using typical residential dimensions.

## Run

```bash
python3 floorplan_agent.py --layout mercer_layout.json --out mercer_floorplan.svg
```

Open `mercer_floorplan.svg` to view the output.

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

Start a local server with a simple form UI:

```bash
python3 local_server.py
```

Open `http://127.0.0.1:8000` and submit the form. Each run writes to
`outputs/run_YYYYMMDD_HHMMSS/`.

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
