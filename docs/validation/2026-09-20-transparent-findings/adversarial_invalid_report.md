# Space Planning Report

Zero modelled violations means only that the modelled checks found nothing. It does not mean the layout is safe, code-compliant, accessible, or construction-ready.

## Checks

| Check | Status | Findings | Method |
| --- | --- | --- | --- |
| layout geometry | fail | 4 | zones inside shell polygon, no zone-zone interior overlap, openings within their wall edge |
| containment | fail | 6 | each furniture box inside its room polygon, edges tested against notches |
| overlap | fail | 1 | axis-aligned box intersection between items whose height ranges overlap; rugs exempt |
| door clearance | fail | 2 | floor-level items intersecting a door swing square or approach strip |
| walkable path | unmeasured | n/a | Not implemented. No claim is made about circulation between doors or around furniture. |

Modelled violations: 13. Unmeasured: walkable_path.

### layout geometry findings

- Annex zone extends outside the unit shell
- Room A and Room B zones overlap
- Room B and Annex zones overlap
- door (offset 9.0 ft, width 3.0 ft) runs 2.00 ft past its 10.0 ft wall edge

### containment findings

- Sofa extends beyond room bounds.
- Coffee Table extends beyond room bounds.
- TV Console extends beyond room bounds.
- Desk extends beyond room bounds.
- Desk Chair extends beyond room bounds.
- Floor Lamp extends beyond room bounds.

### overlap findings

- Queen Bed (Room A) overlaps Floor Lamp (Room B)

### door clearance findings

- Queen Bed (Room A) blocks the approach clearance of the Closet door
- TV Console (Room B) blocks the swing clearance of the Room B door

## Room Stats

| Room | Area sq ft | Free sq ft | Items | Containment | Overlap | Door | Heuristic clearance notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Room A | 80.0 | 44.5 | 2 | 0 | 0 | 1 | 3 |
| Closet | 16.0 | 16.0 | 0 | 0 | 0 | 0 | 0 |
| Room B | 84.0 | 42.1 | 5 | 4 | 0 | 1 | 7 |
| Annex | 16.0 | 4.0 | 2 | 2 | 0 | 0 | 3 |

## Assumptions

- All room, shell, and opening dimensions come from the layout file and are unverified assumptions; no field measurements exist.
- Furniture sizes are fixed typical residential dimensions hard-coded in the placement rules, not products the user owns.
- Door clearance = a swing square (depth = door width) inside the door's room plus an approach strip (depth = min(3 ft, door width)) on the far side when that side is another room; exterior doors get no approach zone; hinge side and in/out swing are not modelled.
- Items above 0.1 ft (upper cabinets, wall shelves, mirrors) and rugs never count as obstructions.
- Overlap uses axis-aligned boxes and the FURNITURE_HEIGHTS_FT table; rotated furniture is not modelled.
- Clearance notes use the FURNITURE_CLEARANCE_FT table on every side of an item, including sides against a wall, so built-ins always generate notes; treat them as heuristic prompts, not violations.
- Walkable path between doors is not implemented; the field is reported as unmeasured on purpose.
