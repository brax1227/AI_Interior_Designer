# Mapping note for Housing adapter (contract 0.1, INTERIOR-20260920-07)

For: PM and the Housing dashboard owner consuming
`scenarios/houseplans_430_40_offline.json` through their adapter (Housing task 09).
No Housing code is touched from this side.

## What changed in the file (provenance correction only)

| Field | Before (897a34c) | Now | Why |
| --- | --- | --- | --- |
| `producer.commit` | `cd9c190` | the commit that carries `scenario_tools.py` (897a34c or later) | cd9c190 predates the tool and schema; it was the checkout HEAD at generation |
| `producer.code_commit` | absent | same value as `commit` | states explicitly that `commit` means the producer **code** revision |
| `producer.code_commit_exact` | absent | boolean | false when producer files had uncommitted edits at generation |
| `producer.uncommitted_producer_files` | absent | list | which files, when not exact |
| `producer.data_revision` | absent | instruction text | the **data** revision is the commit containing the scenario file; read it with `git log -- scenarios/<file>`; it is never embedded because it is unknown at generation |
| `example` (top level) | absent | `true` | one gate for the importer |
| `property.data_status` | absent | `example_public_plan` | nuance behind the gate |
| `property.data_status_note` | absent | text | says what is fact and what is assumption |

Estimate items, totals, contingency, layouts, and checks are unchanged.

## How to read `example` and `data_status`

- `example: true` means never treat this as a real property. Do not surface it in
  any portfolio total, valuation, or profit view.
- `data_status = example_public_plan` means the room widths and depths are
  **published facts** (Houseplans.com plan 430-40, accessed 2026-09-21; PM confirmed
  12'2" x 14' and 15' x 15' independently). Openings, furniture, every cost and the
  resale block are **assumptions or unverified catalog values**. The label is not
  "synthetic" because the sizes are not invented; the `data_status_note` and the
  per-room `dimension_provenance: published` / `openings_provenance: assumed`
  fields carry that distinction.
- `synthetic` is reserved for invented layouts (the rectangle and adversarial samples).
- `real_property_unverified` / `real_property_verified` are for an actual property;
  `verified` additionally requires `dimension_provenance: owner_measured`. The
  validator enforces `example` agreeing with `data_status`.

## Field mapping suggestions (adapter side, read-only)

| Contract field | Suggested dashboard use | Must preserve |
| --- | --- | --- |
| `scenario_id` + `producer.commit` | scenario key | both, plus the data commit from git history |
| `renovation_estimate.items[]` low/base/high + `provenance.kind`/`verified` | itemized table with a provenance mix indicator | `verified: false` must remain visible; do not roll into a single number without the mix |
| `renovation_estimate.grand_total` | headline band only when the provenance mix is shown beside it | band, not a point |
| `transaction_costs.holding` / `selling` | inputs the Housing owner overwrites | keep `assumption` provenance until overwritten |
| `resale_scenario` | render "not evaluated"; no value, no profit | `status`, null values; no derived profit from nulls |
| `layouts.after.rooms[].checks` | show all five statuses | `walkable_path: unmeasured` must not be dropped or shown as pass |
| fields the adapter does not recognise | keep, do not discard | contract 0.x is additive |

## Not in scope of this correction

No Auburn-located source (future refinement), no owner measurements, no quotes, no
purchases, no deployment. Dec 17 target remains unmeasured.
