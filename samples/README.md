# Sample layouts

All three layouts are synthetic. None is measured from a real space.

| File | Purpose | Expected behaviour |
| --- | --- | --- |
| `../mercer_layout.json` | Polygon shell with notches, irregular zones, edge-indexed openings | All modelled checks pass after the door-aware pass |
| `rect_two_room_layout.json` | Plain 20 x 14 ft rectangle split into a bedroom and an office | Rule placement puts the desk and chair in door zones; the pass slides them out; all modelled checks pass |
| `infeasible_group_layout.json` | 12 x 4.5 ft office whose desk + chair group cannot clear the door as a unit, although the chair alone could | The pass moves nothing, lists the group as unresolved, and the door_clearance check keeps failing; the chair is never split off on its own |
| `adversarial_invalid_layout.json` | Deliberately broken: opening overruns its wall, a zone lies outside the shell, two zones overlap, a sofa is wider than its room, a closet bench cannot escape its door swing | `validate_plan` rejects it; `check_layout.py` reports every finding without stopping |

Run the check-only report on any of them:

```bash
python3 check_layout.py --layout samples/adversarial_invalid_layout.json
python3 check_layout.py --layout samples/rect_two_room_layout.json --svg /tmp/rect.svg
```
