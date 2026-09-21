#!/usr/bin/env python3
"""Property/design scenario contract: build an offline scenario from pipeline runs and validate it.

The contract is the hand-off format between this repo (design side) and the Housing
investment dashboard (finance side). It carries before/after layout evidence, an
itemized renovation estimate with low/base/high and per-item provenance, separate
contingency/holding/selling cost blocks, and a resale/comps block that is a scenario,
never a promise. Everything that is an assumption says so in a `provenance` field.

No third-party dependency: `validate_scenario` is a small structural checker aligned
with contracts/property_design_scenario.schema.json (kept in sync by tests).
"""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

CONTRACT_VERSION = "0.1"
ROOT = Path(__file__).resolve().parent

PROVENANCE_KINDS = {"published", "assumption", "internal_catalog", "vendor_quote", "invoice", "comp", "owner_measured"}
# What the scenario as a whole is. Importers gate on this before treating anything as a real property.
DATA_STATUSES = {"example_public_plan", "synthetic", "real_property_unverified", "real_property_verified"}
EXAMPLE_STATUSES = {"example_public_plan", "synthetic"}
PRODUCER_FILES = ("scenario_tools.py", "contracts/property_design_scenario.schema.json", "design_agent.py", "floorplan_agent.py", "plan_checks.py")
RESALE_STATUSES = {"not_evaluated", "draft", "reviewed"}
DIMENSION_PROVENANCE = {"published", "assumed", "mixed", "owner_measured"}

DISCLAIMERS = [
    "Layouts are concept-level; passing the modelled checks is not a safety, code, egress, or construction-readiness statement.",
    "Renovation figures are estimates with stated provenance; none is a quote unless its provenance says vendor_quote or invoice.",
    "The resale block is a scenario for discussion. It is not a valuation, an appraisal, or a guarantee of value or profit.",
    "Nothing in this file is financial advice.",
]


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def _uncommitted_producer_files() -> List[str]:
    """Producer files with uncommitted changes at generation time; empty when the code commit is exact."""
    try:
        status = subprocess.check_output(["git", "status", "--porcelain", "--", *PRODUCER_FILES], cwd=ROOT, text=True)
    except Exception:
        return ["unknown"]
    return sorted(line[3:].strip() for line in status.splitlines() if line.strip())


def producer_block() -> Dict:
    """Code revision that produced the numbers. The data revision is the commit that contains the scenario
    file itself, which cannot be known at generation time; importers read it from git history of the file."""
    commit = _git_commit()
    dirty = _uncommitted_producer_files()
    return {
        "repo": "brax1227/AI_Interior_Designer",
        "commit": commit,
        "code_commit": commit,
        "code_commit_exact": not dirty,
        "uncommitted_producer_files": dirty,
        "tool": "scenario_tools.py",
        "data_revision": "the git commit that contains this scenario file (git log -- scenarios/<file>); not knowable at generation time",
    }


def _price_range(text: str) -> Optional[tuple]:
    try:
        low, high = text.split("-")
        return float(low), float(high)
    except Exception:
        return None


def room_block(layout_path: Path, run_dir: Path) -> Dict:
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    provenance = layout.get("provenance", {})
    published = provenance.get("published_dimensions", {})
    schedule = json.loads((run_dir / "room_schedule.json").read_text(encoding="utf-8"))
    report = json.loads((run_dir / "space_plan_report.json").read_text(encoding="utf-8"))
    rooms = []
    for row in schedule:
        rooms.append(
            {
                "name": row["room"],
                "room_type": row["room_type"],
                "modelled_width_ft": row["width_ft"],
                "modelled_depth_ft": row["depth_ft"],
                "modelled_area_sqft": row["area_sqft"],
                "published_dimensions": published.get(row["room"]),
                "dimension_provenance": "published" if published.get(row["room"]) else "assumed",
                "openings_provenance": "assumed" if any(o.get("assumed") for o in layout.get("openings", [])) else "published",
                "assumptions": list(provenance.get("assumed", [])),
            }
        )
    return {
        "layout_file": str(layout_path.relative_to(ROOT)) if layout_path.is_absolute() else str(layout_path),
        "rooms": rooms,
        "checks": {name: check["status"] for name, check in report["checks"].items()},
        "modelled_violation_count": report["modelled_violation_count"],
        "unmeasured_checks": report["unmeasured_checks"],
        "door_pass": {"moves": len(report["door_pass"]["moves"]), "unresolved": len(report["door_pass"]["unresolved"])},
    }


def renovation_items_from_run(run_dir: Path) -> List[Dict]:
    """Itemize from the run's shopping list. Base = midpoint of the catalog range.

    Provenance is `internal_catalog`: the ranges are hard-coded in design_agent.py and
    have never been checked against a vendor. That is stated per item, not hidden.
    """
    items = []
    for row in json.loads((run_dir / "shopping_list.json").read_text(encoding="utf-8")):
        parsed = _price_range(row.get("price_range_usd", ""))
        if parsed is None:
            continue
        low, high = parsed
        items.append(
            {
                "item": row["item"],
                "room": row["room"],
                "category": row.get("category", "furnishing"),
                "quantity": 1,
                "unit": "ea",
                "low": round(low, 2),
                "base": round((low + high) / 2, 2),
                "high": round(high, 2),
                "provenance": {
                    "kind": "internal_catalog",
                    "source": "design_agent.py FURNITURE_CATALOG price_range_usd, budget tier " + str(row.get("budget_tier", "mid")),
                    "date": None,
                    "verified": False,
                },
            }
        )
    return items


def totals(items: List[Dict]) -> Dict[str, float]:
    return {
        "low": round(sum(i["low"] * i["quantity"] for i in items), 2),
        "base": round(sum(i["base"] * i["quantity"] for i in items), 2),
        "high": round(sum(i["high"] * i["quantity"] for i in items), 2),
    }


def build_scenario(
    scenario_id: str,
    property_label: str,
    source: Dict,
    layouts: List[tuple],
    contingency_pct: float = 15.0,
    holding_months: int = 0,
    holding_monthly: Optional[Dict[str, float]] = None,
    selling_pct: Optional[float] = None,
    data_status: str = "example_public_plan",
    data_status_note: Optional[str] = None,
) -> Dict:
    """Assemble a scenario from (layout_path, run_dir) pairs. All money fields are assumptions unless overridden."""
    before_after = [room_block(Path(layout), Path(run)) for layout, run in layouts]
    items: List[Dict] = []
    for _layout, run in layouts:
        items.extend(renovation_items_from_run(Path(run)))
    item_totals = totals(items)
    contingency = {
        "pct": contingency_pct,
        "low": round(item_totals["low"] * contingency_pct / 100, 2),
        "base": round(item_totals["base"] * contingency_pct / 100, 2),
        "high": round(item_totals["high"] * contingency_pct / 100, 2),
        "provenance": {"kind": "assumption", "source": "placeholder percentage chosen for the contract example", "date": None, "verified": False},
    }
    holding_monthly = holding_monthly or {"low": 0.0, "base": 0.0, "high": 0.0}
    holding = {
        "months": holding_months,
        "monthly": holding_monthly,
        "total": {k: round(v * holding_months, 2) for k, v in holding_monthly.items()},
        "provenance": {"kind": "assumption", "source": "not estimated; Housing owner supplies taxes, insurance, utilities, financing", "date": None, "verified": False},
    }
    selling = {
        "pct_of_sale_price": selling_pct,
        "provenance": {"kind": "assumption", "source": "not estimated; commission/closing costs are market- and deal-specific", "date": None, "verified": False},
    }
    if data_status not in DATA_STATUSES:
        raise ValueError(f"data_status must be one of {sorted(DATA_STATUSES)}")
    return {
        "contract_version": CONTRACT_VERSION,
        "scenario_id": scenario_id,
        "created": date.today().isoformat(),
        "example": data_status in EXAMPLE_STATUSES,
        "producer": producer_block(),
        "property": {
            "label": property_label,
            "address": None,
            "source": source,
            "data_status": data_status,
            "data_status_note": data_status_note
            or "Not a real, located, or measured property. Room widths/depths are published facts from the named source; "
            "openings, furnishings, and every cost figure are assumptions or unverified catalog values (see per-item provenance).",
            "dimension_provenance": "mixed",
        },
        "layouts": {
            "before": {"description": "Empty rooms at published dimensions; openings assumed.", "evidence": [b["layout_file"] for b in before_after]},
            "after": {"description": "Rule-based furnishing after the door-aware pass.", "rooms": before_after},
        },
        "renovation_estimate": {
            "currency": "USD",
            "basis_date": None,
            "scope_note": "Furnishing-only itemization from the pipeline's shopping list. No labor, finishes, MEP, permits, or structural items are estimated.",
            "items": items,
            "totals": item_totals,
            "contingency": contingency,
            "grand_total": {k: round(item_totals[k] + contingency[k], 2) for k in ("low", "base", "high")},
        },
        "transaction_costs": {"holding": holding, "selling": selling},
        "resale_scenario": {
            "status": "not_evaluated",
            "comps": [],
            "value_low": None,
            "value_base": None,
            "value_high": None,
            "note": "No comparable sales were collected. Any value here would be a scenario input from the Housing owner, not an output of this repo.",
        },
        "disclaimers": list(DISCLAIMERS),
    }


# ---------------------------------------------------------------- validation
def _require(obj: Dict, key: str, path: str, errors: List[str], types=None) -> object:
    if key not in obj:
        errors.append(f"{path}.{key}: missing")
        return None
    value = obj[key]
    if types is not None and not isinstance(value, types):
        errors.append(f"{path}.{key}: expected {types}, got {type(value).__name__}")
    return value


def _check_provenance(prov: object, path: str, errors: List[str]) -> None:
    if not isinstance(prov, dict):
        errors.append(f"{path}: provenance must be an object")
        return
    kind = _require(prov, "kind", path, errors, str)
    if kind is not None and kind not in PROVENANCE_KINDS:
        errors.append(f"{path}.kind: {kind!r} not in {sorted(PROVENANCE_KINDS)}")
    _require(prov, "source", path, errors, str)
    _require(prov, "verified", path, errors, bool)
    if "date" not in prov:
        errors.append(f"{path}.date: missing (use null when unknown)")


def _check_lbh(block: Dict, path: str, errors: List[str]) -> None:
    for key in ("low", "base", "high"):
        value = _require(block, key, path, errors, (int, float))
        if isinstance(value, bool):
            errors.append(f"{path}.{key}: boolean is not a number")
    if all(isinstance(block.get(k), (int, float)) for k in ("low", "base", "high")):
        if not (block["low"] <= block["base"] <= block["high"]):
            errors.append(f"{path}: expected low <= base <= high, got {block['low']}, {block['base']}, {block['high']}")


def validate_scenario(scenario: Dict) -> List[str]:
    """Return a list of problems; empty means the scenario satisfies contract 0.1."""
    errors: List[str] = []
    if not isinstance(scenario, dict):
        return ["scenario must be an object"]
    version = _require(scenario, "contract_version", "$", errors, str)
    if version is not None and version != CONTRACT_VERSION:
        errors.append(f"$.contract_version: {version!r} != {CONTRACT_VERSION!r}")
    for key in ("scenario_id", "created"):
        _require(scenario, key, "$", errors, str)
    example = _require(scenario, "example", "$", errors, bool)
    producer = _require(scenario, "producer", "$", errors, dict)
    if isinstance(producer, dict):
        for key in ("repo", "commit"):
            _require(producer, key, "$.producer", errors, str)
        if "code_commit" in producer and producer.get("code_commit") != producer.get("commit"):
            errors.append("$.producer.code_commit: must equal producer.commit (commit is the code revision)")
        if "code_commit_exact" in producer and not isinstance(producer["code_commit_exact"], bool):
            errors.append("$.producer.code_commit_exact: must be boolean")

    prop = _require(scenario, "property", "$", errors, dict)
    if isinstance(prop, dict):
        _require(prop, "label", "$.property", errors, str)
        if "address" not in prop:
            errors.append("$.property.address: missing (use null when withheld)")
        source = _require(prop, "source", "$.property", errors, dict)
        if isinstance(source, dict):
            for key in ("kind", "name", "accessed"):
                _require(source, key, "$.property.source", errors, str)
        dim = _require(prop, "dimension_provenance", "$.property", errors, str)
        if dim is not None and dim not in DIMENSION_PROVENANCE:
            errors.append(f"$.property.dimension_provenance: {dim!r} not in {sorted(DIMENSION_PROVENANCE)}")
        status = _require(prop, "data_status", "$.property", errors, str)
        _require(prop, "data_status_note", "$.property", errors, str)
        if status is not None and status not in DATA_STATUSES:
            errors.append(f"$.property.data_status: {status!r} not in {sorted(DATA_STATUSES)}")
        elif status is not None and isinstance(example, bool):
            if example != (status in EXAMPLE_STATUSES):
                errors.append(f"$.example: {example} contradicts property.data_status {status!r}")
        if status == "real_property_verified" and dim != "owner_measured":
            errors.append("$.property.data_status: real_property_verified requires dimension_provenance owner_measured")

    layouts = _require(scenario, "layouts", "$", errors, dict)
    if isinstance(layouts, dict):
        before = _require(layouts, "before", "$.layouts", errors, dict)
        after = _require(layouts, "after", "$.layouts", errors, dict)
        if isinstance(before, dict):
            _require(before, "description", "$.layouts.before", errors, str)
        if isinstance(after, dict):
            rooms = _require(after, "rooms", "$.layouts.after", errors, list)
            for index, block in enumerate(rooms or []):
                path = f"$.layouts.after.rooms[{index}]"
                checks = _require(block, "checks", path, errors, dict)
                if isinstance(checks, dict):
                    if checks.get("walkable_path") not in {"unmeasured", "pass", "fail"}:
                        errors.append(f"{path}.checks.walkable_path: must be present (unmeasured/pass/fail)")
                _require(block, "modelled_violation_count", path, errors, int)
                for r_index, room in enumerate(_require(block, "rooms", path, errors, list) or []):
                    r_path = f"{path}.rooms[{r_index}]"
                    _require(room, "name", r_path, errors, str)
                    dim = _require(room, "dimension_provenance", r_path, errors, str)
                    if dim is not None and dim not in DIMENSION_PROVENANCE:
                        errors.append(f"{r_path}.dimension_provenance: {dim!r} invalid")
                    if "published_dimensions" not in room:
                        errors.append(f"{r_path}.published_dimensions: missing (use null when none)")

    estimate = _require(scenario, "renovation_estimate", "$", errors, dict)
    if isinstance(estimate, dict):
        _require(estimate, "currency", "$.renovation_estimate", errors, str)
        if "basis_date" not in estimate:
            errors.append("$.renovation_estimate.basis_date: missing (use null when unknown)")
        items = _require(estimate, "items", "$.renovation_estimate", errors, list)
        for index, item in enumerate(items or []):
            path = f"$.renovation_estimate.items[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{path}: must be an object")
                continue
            _require(item, "item", path, errors, str)
            _require(item, "quantity", path, errors, (int, float))
            _check_lbh(item, path, errors)
            _check_provenance(item.get("provenance"), path + ".provenance", errors)
        for key in ("totals", "grand_total"):
            block = _require(estimate, key, "$.renovation_estimate", errors, dict)
            if isinstance(block, dict):
                _check_lbh(block, f"$.renovation_estimate.{key}", errors)
        contingency = _require(estimate, "contingency", "$.renovation_estimate", errors, dict)
        if isinstance(contingency, dict):
            _require(contingency, "pct", "$.renovation_estimate.contingency", errors, (int, float))
            _check_lbh(contingency, "$.renovation_estimate.contingency", errors)
            _check_provenance(contingency.get("provenance"), "$.renovation_estimate.contingency.provenance", errors)
        if isinstance(items, list) and isinstance(estimate.get("totals"), dict):
            recomputed = totals([i for i in items if isinstance(i, dict) and all(k in i for k in ("low", "base", "high", "quantity"))])
            for key in ("low", "base", "high"):
                if isinstance(estimate["totals"].get(key), (int, float)) and abs(estimate["totals"][key] - recomputed[key]) > 0.01:
                    errors.append(f"$.renovation_estimate.totals.{key}: {estimate['totals'][key]} != sum of items {recomputed[key]}")

    costs = _require(scenario, "transaction_costs", "$", errors, dict)
    if isinstance(costs, dict):
        holding = _require(costs, "holding", "$.transaction_costs", errors, dict)
        if isinstance(holding, dict):
            _require(holding, "months", "$.transaction_costs.holding", errors, int)
            _check_provenance(holding.get("provenance"), "$.transaction_costs.holding.provenance", errors)
        selling = _require(costs, "selling", "$.transaction_costs", errors, dict)
        if isinstance(selling, dict):
            if "pct_of_sale_price" not in selling:
                errors.append("$.transaction_costs.selling.pct_of_sale_price: missing (use null when unknown)")
            _check_provenance(selling.get("provenance"), "$.transaction_costs.selling.provenance", errors)

    resale = _require(scenario, "resale_scenario", "$", errors, dict)
    if isinstance(resale, dict):
        status = _require(resale, "status", "$.resale_scenario", errors, str)
        if status is not None and status not in RESALE_STATUSES:
            errors.append(f"$.resale_scenario.status: {status!r} not in {sorted(RESALE_STATUSES)}")
        comps = _require(resale, "comps", "$.resale_scenario", errors, list)
        for key in ("value_low", "value_base", "value_high"):
            if key not in resale:
                errors.append(f"$.resale_scenario.{key}: missing (use null when not evaluated)")
        if status == "not_evaluated" and any(resale.get(k) is not None for k in ("value_low", "value_base", "value_high")):
            errors.append("$.resale_scenario: values must be null while status is not_evaluated")
        if status in {"draft", "reviewed"} and not comps:
            errors.append("$.resale_scenario.comps: a draft/reviewed resale scenario needs at least one comp with provenance")
        for index, comp in enumerate(comps or []):
            _check_provenance(comp.get("provenance") if isinstance(comp, dict) else None, f"$.resale_scenario.comps[{index}].provenance", errors)
        for banned in ("guaranteed_value", "expected_profit", "roi"):
            if banned in resale:
                errors.append(f"$.resale_scenario.{banned}: not allowed by the contract; profit is the dashboard's derived scenario, not a field here")

    disclaimers = _require(scenario, "disclaimers", "$", errors, list)
    if isinstance(disclaimers, list) and not any("not a valuation" in d or "guarantee" in d for d in disclaimers):
        errors.append("$.disclaimers: must state that the resale block is not a valuation or guarantee")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a property/design scenario file against contract 0.1.")
    parser.add_argument("scenario")
    args = parser.parse_args()
    scenario = json.loads(Path(args.scenario).read_text(encoding="utf-8"))
    problems = validate_scenario(scenario)
    if problems:
        print(f"INVALID ({len(problems)} problem(s)):")
        for problem in problems:
            print("  -", problem)
        return 1
    print(f"valid: contract {scenario['contract_version']}, {len(scenario['renovation_estimate']['items'])} estimate items, resale {scenario['resale_scenario']['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
