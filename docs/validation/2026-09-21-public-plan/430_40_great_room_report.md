# Space Planning Report

Zero modelled violations means only that the modelled checks found nothing. It does not mean the layout is safe, code-compliant, accessible, or construction-ready.

## Checks

| Check | Status | Findings | Method |
| --- | --- | --- | --- |
| layout geometry | pass | 0 | zones inside shell polygon, no zone-zone interior overlap, openings within their wall edge |
| containment | pass | 0 | each furniture box inside its room polygon, edges tested against notches |
| overlap | pass | 0 | axis-aligned box intersection between items whose height ranges overlap; rugs exempt |
| door clearance | pass | 0 | floor-level items intersecting a door swing square or approach strip |
| walkable path | unmeasured | n/a | Not implemented. No claim is made about circulation between doors or around furniture. |

Modelled violations: 0. Unmeasured: walkable_path.

## Door-aware placement pass

Items moved: 0. Unresolved items/groups: 0.

## Room Stats

| Room | Area sq ft | Free sq ft | Items | Containment | Overlap | Door | Heuristic clearance notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Great Room | 225.0 | 183.1 | 5 | 0 | 0 | 0 | 4 |

## Assumptions

- All room, shell, and opening dimensions come from the layout file and are unverified assumptions; no field measurements exist.
- Furniture sizes are fixed typical residential dimensions hard-coded in the placement rules, not products the user owns.
- Door clearance = a swing square (depth = door width) inside the door's room plus an approach strip (depth = min(3 ft, door width)) on the far side when that side is another room; exterior doors get no approach zone; hinge side and in/out swing are not modelled.
- Items above 0.1 ft (upper cabinets, wall shelves, mirrors) and rugs never count as obstructions.
- Overlap uses axis-aligned boxes and the FURNITURE_HEIGHTS_FT table; rotated furniture is not modelled.
- Clearance notes use the FURNITURE_CLEARANCE_FT table on every side of an item, including sides against a wall, so built-ins always generate notes; treat them as heuristic prompts, not violations.
- Walkable path between doors is not implemented; the field is reported as unmeasured on purpose.
