# Property/design scenario contract (v0.1) and Housing dashboard feasibility

Status: draft interface plus one offline example. The Housing investment dashboard
owner implements their side; this repository never writes to that repository.

## What the contract is for

One JSON file per scenario that lets the Housing dashboard show a design concept next
to its money, without either side trusting the other's hidden assumptions. Every number
carries a `provenance` block (`kind`, `source`, `date`, `verified`). Profit is never a
field: the dashboard derives whatever it derives from the inputs and owns that logic.

## Shape (compact)

```
contract_version "0.1"
scenario_id, created, producer{repo, commit, tool}
property{label, address|null, source{kind,name,url,accessed,license_note}, dimension_provenance}
layouts{
  before{description, evidence[]}
  after{description, rooms[{layout_file, rooms[{name, modelled_*_ft, published_dimensions|null,
         dimension_provenance, openings_provenance, assumptions[]}],
         checks{layout_geometry,containment,overlap,door_clearance,walkable_path},
         modelled_violation_count, unmeasured_checks[], door_pass{moves,unresolved}}]}
}
renovation_estimate{currency, basis_date|null, scope_note,
  items[{item, room, category, quantity, unit, low, base, high, provenance}],
  totals{low,base,high}, contingency{pct,low,base,high,provenance}, grand_total{low,base,high}}
transaction_costs{holding{months, monthly{low,base,high}, total{...}, provenance},
                  selling{pct_of_sale_price|null, provenance}}
resale_scenario{status: not_evaluated|draft|reviewed, comps[{...provenance}],
                value_low|null, value_base|null, value_high|null, note}
disclaimers[]
```

Machine-readable version: `contracts/property_design_scenario.schema.json`.
Validator without dependencies: `python3 scenario_tools.py scenarios/<file>.json`.

## Rules the validator enforces

- `low <= base <= high` on every item, on totals, contingency and grand total; totals
  must equal the sum of items.
- Every money block and every comp has provenance with a known `kind`
  (`published`, `assumption`, `internal_catalog`, `vendor_quote`, `invoice`, `comp`,
  `owner_measured`) and an explicit `verified` boolean.
- `walkable_path` must be present in each room block's checks, so "unmeasured" travels
  with the layout instead of being dropped.
- `resale_scenario.status = not_evaluated` forces the value fields to null; `draft`
  or `reviewed` requires at least one comp with provenance.
- Fields named `guaranteed_value`, `expected_profit` or `roi` are rejected.
- Disclaimers must say the resale block is not a valuation or guarantee.

## Feasibility for the Housing dashboard (read-only integration)

| Concern | Assessment |
| --- | --- |
| Transport | A JSON file committed here or exported per run. No API, no shared database, no cross-repo write. The dashboard reads by path or URL. |
| Identity | `scenario_id` plus `producer.commit` make a scenario reproducible; the dashboard should key on both. |
| Money semantics | Low/base/high are estimate bands, not distributions. The dashboard may sum them but should show provenance mix (how much is `assumption` vs `vendor_quote`) next to any total. |
| What this repo can fill today | Layout evidence and checks; furnishing items from the internal catalog (unverified). It cannot fill labor, finishes, permits, holding, selling, or comps. Those are null or zero with `assumption` provenance until the Housing owner supplies them. |
| Versioning | `contract_version` is required; breaking changes bump it. Additive fields are allowed within 0.x. |
| Risk of misuse | The biggest risk is a dashboard rendering `grand_total` and `value_base` as if they were facts. The contract mitigates by forcing null values while not evaluated and by rejecting profit fields; the dashboard must render provenance. |

## Offline example

`scenarios/houseplans_430_40_offline.json`: two rooms from Houseplans.com plan 430-40
(published room dimensions, assumed openings), furnishing items from the pipeline's
internal catalog with `verified: false`, 15 percent contingency labelled as a
placeholder assumption, holding months 0 and selling percent null with assumption
provenance, resale `not_evaluated` with no comps. It validates; it is not a business
case.

## What would make it useful (next, in order)

1. Housing owner reads the example and lists the fields their dashboard needs that are
   missing or mis-shaped.
2. Replace `internal_catalog` furnishing ranges with at least one `vendor_quote` or
   `invoice` item to prove the provenance path end to end.
3. Add one `comp` with a real source and date to move resale from `not_evaluated` to
   `draft`, done by the Housing side, not here.
