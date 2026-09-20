# Sample layouts

All three layouts are synthetic. None is measured from a real space.

| File | Purpose | Expected behaviour |
| --- | --- | --- |
| `../mercer_layout.json` | Polygon shell with notches, irregular zones, edge-indexed openings | All modelled checks pass after the door-aware pass |
| `rect_two_room_layout.json` | Plain 20 x 14 ft rectangle split into a bedroom and an office | Rule placement puts the desk and chair in door zones; the pass slides them out; all modelled checks pass |
| `adversarial_invalid_layout.json` | Deliberately broken: opening overruns its wall, a zone lies outside the shell, two zones overlap, a sofa is wider than its room, a closet bench cannot escape its door swing | `validate_plan` rejects it; `check_layout.py` reports every finding without stopping |

Run the check-only report on any of them:

```bash
python3 check_layout.py --layout samples/adversarial_invalid_layout.json
python3 check_layout.py --layout samples/rect_two_room_layout.json --svg /tmp/rect.svg
```
