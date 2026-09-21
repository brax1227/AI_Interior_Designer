# INTERIOR-20260920-06 checkpoint: public floor-plan source shortlist

Date: 2026-09-21. Goal: one legitimately accessible, publicly documented house plan
with room dimensions published as **text** (not read off an image), preferably Auburn,
AL, to run two rooms through the existing pipeline without own-room inputs.

Rule applied: a source counts only if the room dimensions are stated as text on a page
this environment could actually retrieve. Dimensions visible only inside a floor-plan
image were not transcribed, because that is inference from an image.

## Candidates checked (all on 2026-09-21)

| # | Source | Auburn? | Room dimensions as text? | Access | Verdict |
| --- | --- | --- | --- | --- | --- |
| 1 | Holland Homes, Auburn Farms lot pages (e.g. Lot 21 Hayes A, 1393 Copper Meadows Dr, $546,852, 2,739 sq ft) | Yes | No, floor plans are images only | OK | Rejected: no text dims |
| 2 | Holland Homes plan pages (The Chartres B) | Yes | Page 404 | 404 | Rejected |
| 3 | Harris Doyle Homes, Auburn plans | Yes | "No Available Communities Found" | OK | Rejected: nothing listed |
| 4 | Hughston Homes plan pages (Maple, 41 plans; builds in Auburn/Opelika) | Builder serves Auburn | No, "dimensions" promised but only in elevation/plan images; © 2026 Hughston Homes | OK | Rejected: image-only |
| 5 | Stone Martin Builders (Alexandria, Cannongate, Opelika) via NewHomeSource | Opelika | Unknown, page blocked | 403 | Rejected: not accessible |
| 6 | Grayhawk Homes, Parc at AU Club (Auburn) | Yes | Unknown, DNS failure from this environment | error | Not verifiable |
| 7 | The Arbors (Michael Allen Homes / Hooper Homes) home designs | Yes | Page 404 | 404 | Rejected |
| 8 | Creekside of Auburn (rental cottages, 20+ unit types) | Yes | No, images only; © 2026 | OK | Rejected: image-only |
| 9 | Redfin / Zillow / Homes.com / Realtor.com listings (MLS room dimensions are often text) | Yes | Unknown | 403 / 405 / blocked | Rejected: automated access refused; also a private seller's home and MLS reuse terms |
| 10 | Auburn University Rural Studio 20K / Front Porch product-line houses (Hale County, AL) | AU program, not Auburn city | Page returns a bot-challenge stub (202, 200 bytes); GSF only in search snippets (504 GSF, 536 GSF) | blocked | Rejected for now: no text room dims retrievable |
| 11 | Auburn University residence hall room details | Yes (campus) | Redirected; dimensions not on the landing page; third-party aggregators quote "16.5 × 11.7 ft" but are not the publisher | partial | Fallback only: dorm rooms, not a house |
| 12 | **Houseplans.com stock plan 430-40** (cottage, 1,300 sq ft, 3 bed / 2 bath, 28'8" x 60'2", 9' ceilings, 2x4 walls) | No (national stock plan, buildable in AL) | **Yes**: Master Bedroom 12'2" x 14', Great Room 15' x 15', Kitchen 13'10" x 11'8", Dining 11'10" x 11'10", Bedrooms 2/3 11' x 10', Master Bath 8'6" x 8'4", Screened Porch 18'6" x 8', Utility 7'10" x 6' | OK | **Selected** |
| 13 | Houseplans.com stock plan 536-3 (1,025 sq ft, designer Bruce B. Tolar) | No | No, image only | OK | Rejected: image-only |

## Selection and its limits

Selected: Houseplans.com plan 430-40, accessed 2026-09-21. It is the only source found
whose room dimensions are published as text and were retrievable here. It is not an
Auburn house; it is a stock plan any Alabama builder could build. No Auburn-located
house with text room dimensions was accessible without either scraping a blocked
portal or reading dimensions off an image, and both were ruled out.

What is published (used): room widths and depths, overall footprint, ceiling height,
wall framing, square footage. What is **not** published as text and is therefore an
assumption in the sample layouts: every door and window position and width, swing
direction, which walls are exterior, fireplace location, wall thickness, and room
adjacency. Each layout file carries a `provenance` block naming these.

Designer credit is not stated as text on the plan page; the plan is the designer's
copyrighted work. Only the published numeric facts are reused, with attribution. No
plan drawing was copied into this repository.

## Two rooms demonstrated

| Room | Published | Assumed | Layout file | Result |
| --- | --- | --- | --- | --- |
| Master Bedroom | 12'2" x 14' | door on a 14 ft wall, window opposite | `samples/public_plans/houseplans_430_40_master_bedroom.json` | 4 modelled checks pass; walkable path unmeasured; 1 door conflict resolved by the pass |
| Great Room | 15' x 15' | entry opening, 4 ft opening to kitchen/dining, one window | `samples/public_plans/houseplans_430_40_great_room.json` | 4 modelled checks pass; walkable path unmeasured; 0 conflicts |

Artifacts in this folder: `430_40_*_plan.svg/.png`, `430_40_*_report.md`. The rooms are
modelled independently; their real adjacency is not asserted.

## If an Auburn-located source is still wanted

The realistic legitimate routes are manual, not automated: (a) a builder's printed plan
sheet obtained from a sales office, (b) an MLS listing viewed by a person and used only
for its numeric facts with the listing date recorded, or (c) Rural Studio drawings
requested from the program. None was pursued here because the brief forbids outreach.
