# Checkpoint INTERIOR-20260920-03: furniture groups in the door-aware pass

Date: 2026-09-20. Writer: Claude Code (sole primary). Builds on e1bcf70 (accepted
with limits: 28 pass + 2 expected failures, adversarial exits 1 with 13 findings,
walkability unmeasured).

Scope is geometry only. Nothing here is evidence of real-user acceptance or of
construction readiness. All layouts are synthetic; all dimensions are assumptions.

## What changed

1. `Furniture.group` (optional name). Placement rules now tag desk + chair as
   `desk-set` and washer + dryer as `laundry-pair`. Groups are scoped to a room.
2. `resolve_door_conflicts` moves a whole group as one unit: the same shift is applied
   to every member, and the shift is accepted only if every member ends inside the
   room polygon, clear of every door zone, and clear of every other floor-level item.
   Shortest valid shift wins across the door normal and both tangents.
3. A group that cannot move as a unit is left exactly where it was and returned under
   `unresolved` with the members and the reason. Members are never split off and moved
   alone, even when a lone member could have escaped. The `door_clearance` check keeps
   failing for it, so nothing is hidden.
4. The pass result now travels with the plan (`FloorPlan.door_pass`) and is printed in
   `space_plan_report.md` as a move table plus any `UNRESOLVED` lines.
5. Tests: 35 total, all pass, 0 expected failures. The two former expected failures are
   now positive checks that assert the original desk/chair spacing (0.5 ft) and
   washer/dryer spacing (0.4 ft) are preserved, the members share a y coordinate, and
   the door is clear. They pass because the behaviour changed, not because a tolerance
   was loosened. New: a case where the chair alone could escape but the group cannot
   (asserts zero moves, group reported, positions untouched), a room-scoping case, and
   the sample file below.
6. North Star doc corrected: `$0` is development spend, not a selling price; product is
   intended to be paid; price undecided; revenue not independently measured.

## Before / after

| Layout | Before (e1bcf70) | After |
| --- | --- | --- |
| Mercer office | Desk moved 0.75 ft west, chair moved 3 ft north: chair 3 ft from desk | Desk and chair both moved 3 ft north together; 0.5 ft spacing kept; patio door clear |
| Mercer laundry | Dryer moved 1.75 ft north alone; washer stayed: misaligned pair | Washer and dryer both moved 1.75 ft north; aligned; laundry door clear |
| Rectangle office | Desk moved north, chair moved west: separated | Desk and chair moved 3 ft north together; both doors clear |
| Infeasible sample (new) | n/a | 0 moves, group `Desk + Desk Chair` listed as unresolved, door_clearance fails, exit 1 |

Files: `mercer_before_groups.png` vs `mercer_after_groups.png` (+ `.svg`, reports),
`rect_before_groups.png` vs `rect_after_groups.png`, `infeasible_group_plan.png` with
`infeasible_group_report.md` and console output.

Mercer move table after the change (feet, y up): 11 items moved in 9 moves, 0
unresolved; see `mercer_after_groups_report.md`.

## Limits that remain

- Only two groups are defined. Bed + nightstands, sofa + coffee table, island +
  stools still move independently. Adding them is a one-line tag each but changes the
  Mercer output, so it was left for a decision.
- A group move is a pure translation; no rotation, no re-flowing a chair to the other
  side of a desk.
- Unresolved groups are reported, not designed around. A human still has to decide
  whether to shrink the desk, move the door in the data, or accept the conflict.
- Walkable path remains unmeasured. Heuristic clearance notes remain heuristic.
- The web server was not exercised end to end.

## Readiness note: minimum real-space input needed later

Not homework now. When Braxton picks a space, this is the smallest input the current
code can consume without guessing:

1. Room outline as a closed polygon in feet, one vertex per wall corner (a tape
   measure along each wall is enough; diagonals confirm squareness).
2. For every door: which wall, distance from the wall's start corner, clear width, and
   which room it swings into.
3. For every window: which wall, offset, width (sill and head height optional).
4. Fixed items that cannot move (radiator, closet, built-in) as boxes in the same
   coordinates.
5. Ceiling height and anything to keep (existing bed size, desk size) as plain
   dimensions.

No photos are needed for the geometry checks. Photos only matter for style/palette
work, which is out of scope for this line of checkpoints.
