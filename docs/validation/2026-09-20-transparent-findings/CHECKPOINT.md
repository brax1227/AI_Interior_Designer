# Checkpoint INTERIOR-20260920-02: transparent findings, second and adversarial layouts

Date: 2026-09-20. Writer: Claude Code (sole primary). Builds on 97b275f (accepted
for its geometry checks and 18 tests, not for its 14/100 score).

North Star reference: `docs/NORTH_STAR.md` (mirror of the PM record). This checkpoint
is prototype-quality evidence toward Target A; it says nothing about paying customers
and nothing about construction readiness.

## What changed

1. **Aggregate score removed.** `analyze_plan` now reports five checks separately:
   `layout_geometry`, `containment`, `overlap`, `door_clearance` (each pass/fail with
   the findings and the method used) and `walkable_path`, which is reported as
   `unmeasured` with `finding_count: null` because it is not implemented. The report
   carries a fixed disclaimer and the list of heuristic assumptions. The cover sheet
   and manifest print check statuses instead of a number.
2. **Heuristic clearance notes kept but labelled.** The per-room count from the fixed
   clearance table stays, renamed `heuristic_clearance_notes`, never aggregated, and
   documented as a prompt rather than a violation. (It flags built-ins for touching
   walls, which is what made the old score meaningless.)
3. **Check-only CLI** `check_layout.py`: runs every check on any layout without
   raising, prints findings, exit 1 on a modelled failure, optional SVG/MD/JSON.
4. **Two synthetic layouts** in `samples/`: a plain 20 x 14 ft rectangle split into
   bedroom and office, and a deliberately invalid layout that plants one defect per
   check.
5. **Tests**: 30 total (18 prior + 12 new), of which 2 are `expectedFailure` cases
   that document the grouping gap below. `python3 -m unittest discover -s tests`.
6. North Star mirrored into `docs/NORTH_STAR.md`; README and AGENTS point to it.

## Before / after on the Mercer sample

| | Before (97b275f) | After |
| --- | --- | --- |
| Headline | "Overall score: 14/100" with "No major issues" underneath | Five named checks: 4 pass, 1 unmeasured |
| What a reader learns | Nothing usable; the number contradicts the issue list | Which checks ran, what method, what was not measured |
| Files | `mercer_before_report.md` / `.json` | `mercer_after_report.md` / `.json` |

## Behaviour on layouts that are not Mercer

**Rectangle (`rect_two_room_layout.json`)** — `rect_two_room_report.md`, console in
`rect_two_room_console.txt`, plan before and after the door pass as PNG/SVG.

- Rule placement put the desk in the bedroom door's approach strip and the desk chair
  in the office exterior door's swing square: 2 raw conflicts.
- The door pass moved both; all four modelled checks pass; `validate_plan` accepts it.
- Same code path, no Mercer-specific data touched.

**Adversarial (`adversarial_invalid_layout.json`)** — `adversarial_invalid_report.md`,
console in `adversarial_invalid_console.txt`, plan PNG/SVG.

| Planted defect | Found as |
| --- | --- |
| Door offset 9 ft, width 3 ft on a 10 ft wall | layout_geometry: opening_overrun, 2.00 ft |
| "Annex" zone outside the 16 x 12 shell | layout_geometry: zone_outside_shell |
| Room A and Room B share a 1 ft band; Annex overlaps Room B | layout_geometry: 2 zone_overlap findings |
| Living-room rules in a 7 ft wide room | containment: sofa, coffee table, TV console outside room; office desk and chair outside the 4 x 4 annex |
| Bed in Room A vs floor lamp placed by Room B rules | overlap: 1 |
| Closet door approach strip under the bed; TV console in Room B door swing | door_clearance: 2, and the pass could not move either (0 moves), so both stay reported |

`validate_plan` raises on this file; `check_layout.py` reports all 13 modelled
violations and exits 1. The unmeasured walkable-path field is unchanged in every case.

## Known issues kept visible (not fixed here)

- **Grouping.** The door pass moves items one at a time. On Mercer the desk chair ends
  3 ft from the desk and the dryer sits 1.75 ft above the washer; on the rectangle the
  chair ends beside, not under, the desk. Encoded as two `expectedFailure` tests in
  `tests/test_report_and_samples.py` so they show in every run until grouping exists.
- **Bounding-box placement.** Rules place furniture relative to a room's bounding box,
  which is why the adversarial living room and annex overflow instead of adapting.
- **Heuristic clearance notes** still count wall-side clearance for built-ins.
- **No walkable-path model.** Reported as unmeasured; do not read "0 violations" as
  "you can walk through it".
- **Unknown measurements.** Every dimension in every layout is an assumption. The
  Mercer layout is traced from a marketing render; the other two are invented.

## Checks run

- `python3 -m unittest discover -s tests -v`: 30 tests, OK, 2 expected failures.
- `python3 design_agent.py --layout mercer_layout.json --answers sample_answers.json`
  (answers file in the 2026-09-19 folder): full output set generated, no exceptions.
- `check_layout.py` on both samples: exit 0 (rectangle), exit 1 (adversarial).
- Not run: the local web server end to end (import only); no browser test of the
  3D viewer.

## Suggested next bounded step

Implement grouping for the door pass (move a desk with its chair, a washer with its
dryer) as explicit furniture groups in the placement rules, then flip the two
expected-failure tests to real assertions. After that, the honest next question is not
another check but which personal space Braxton will model, since every layout here
is synthetic.
