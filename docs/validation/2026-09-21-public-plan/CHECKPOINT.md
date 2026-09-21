# Checkpoint INTERIOR-20260920-06: public plan rooms + Housing scenario contract

Date: 2026-09-21. Writer: Claude Code (sole primary). Builds on cd9c190. Part 1 (source
shortlist and integration feasibility) is `SOURCE_SHORTLIST.md` and
`docs/integration/HOUSING_SCENARIO_CONTRACT.md`. This file records the scoped
implementation.

## Delivered

1. Two rooms from Houseplans.com plan 430-40 modelled from **text-published** dimensions
   (Master Bedroom 12'2" x 14', Great Room 15' x 15'). Every opening is flagged
   `"assumed": true` and the layout `provenance` block separates published from assumed.
   Both run through the unchanged pipeline: 4 modelled checks pass, walkable path
   unmeasured, 1 door conflict resolved (bedroom), 0 unresolved. Plans and reports in
   this folder. The rooms are independent; adjacency is not asserted.
2. Scenario contract v0.1: `contracts/property_design_scenario.schema.json` plus a
   dependency-free reference validator and exporter in `scenario_tools.py`.
3. Offline example `scenarios/houseplans_430_40_offline.json`, built from the two runs:
   10 furnishing items from the internal catalog (`verified: false`), low/base/high
   totals 2,130 / 5,235 / 8,340 USD, 15 percent contingency labelled a placeholder
   assumption, holding 0 months and selling percent null with assumption provenance,
   resale `not_evaluated` with no comps and null values.
4. Tests: `tests/test_scenario_contract.py`, 15 cases (provenance flags, published sizes
   match the model, checks pass, validator accepts the example and rejects profit
   fields, values while not evaluated, out-of-order bands, mismatched totals, missing
   provenance, dropped walkable-path, wrong version; fresh pipeline runs rebuild an
   identical estimate). Whole suite: 61 tests.

## Not done, on purpose

- No Auburn-located house: none with text dimensions was legitimately retrievable
  (see shortlist). No dimension was inferred from any image.
- No labor, finishes, permits, holding, selling, or comps figures: they are null/zero
  with `assumption` provenance for the Housing owner to fill.
- No cross-repo write. The Housing dashboard consumes the JSON by path or URL.
- No claim of real-user acceptance, valuation, or profit anywhere in the files; the
  validator rejects `expected_profit`, `roi`, `guaranteed_value`.

## Readiness note

For a real property the contract needs: measured room polygons and openings
(`owner_measured` provenance), at least one `vendor_quote` or `invoice` item, holding
cost inputs from the Housing side, and one dated `comp` to move resale to `draft`.
Until then the scenario is an interface proof. Dec 17 target (one usable own-space
design, 3 paying customers) remains unmeasured; 0 users / 0 paying since Sep 18.

## Follow-up INTERIOR-20260920-07: provenance correction (narrow)

- `producer.commit` was `cd9c190`, the checkout HEAD when the file was generated, which
  predates `scenario_tools.py` and the schema. It now records the code revision that
  contains the tool, with `code_commit`, `code_commit_exact` and
  `uncommitted_producer_files` so a regeneration from a dirty tree is visible. The
  data revision is the commit containing the file; the tool never embeds it.
- Added top-level `example: true` and `property.data_status = example_public_plan`
  with a note that keeps the published room sizes as facts and marks openings, costs
  and resale as assumptions. Not labelled `synthetic`, because the sizes are not invented.
- Estimate items, totals, layouts and checks are byte-identical to 897a34c (asserted
  during regeneration). Validator and schema gained the matching rules; 5 new tests.
- Mapping note for the Housing adapter: `docs/integration/HOUSING_MAPPING_NOTE_0.1.md`.
