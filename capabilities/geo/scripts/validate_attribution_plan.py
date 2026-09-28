#!/usr/bin/env python3
"""Validate a GEO attribution plan using the project contract's hard rules."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path


REQUIRED_FIELDS = {
    "plan_id",
    "objective",
    "decision",
    "intent_clusters",
    "markers",
    "metrics",
    "observation_window",
    "economics",
    "deduplication",
    "decision_rules",
    "status",
}
OBJECTIVES = {
    "description_accuracy",
    "visibility",
    "qualified_leads",
    "orders",
    "revenue",
    "contribution_margin",
}
EVIDENCE_TIERS = {"direct", "corroborated", "experimental", "directional"}
VALUE_BASES = {"qualified_lead", "revenue", "contribution_margin", "ltv"}


def load_plan(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def parse_date(value: object, field: str, errors: list[str]) -> dt.date | None:
    if not isinstance(value, str):
        errors.append(f"{field} must be an ISO date")
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        errors.append(f"{field} must be an ISO date")
        return None


def validate_plan(plan: dict) -> list[str]:
    errors: list[str] = []
    missing = sorted(REQUIRED_FIELDS - set(plan))
    if missing:
        errors.append(f"missing required fields: {', '.join(missing)}")
        return errors

    if plan["objective"] not in OBJECTIVES:
        errors.append("objective is invalid")

    options = plan.get("decision", {}).get("options", [])
    if len(set(options)) < 2 or not set(options).issubset({"scale", "iterate", "stop"}):
        errors.append("decision.options must contain at least two valid unique options")

    clusters = plan.get("intent_clusters", [])
    if not 1 <= len(clusters) <= 5:
        errors.append("intent_clusters must contain 1 to 5 pilot clusters")
    cluster_ids = [item.get("id") for item in clusters if isinstance(item, dict)]
    if len(cluster_ids) != len(set(cluster_ids)) or any(not item for item in cluster_ids):
        errors.append("intent cluster ids must be present and unique")

    markers = plan.get("markers", [])
    if not markers:
        errors.append("at least one attribution marker is required")
    marker_ids = [item.get("id") for item in markers if isinstance(item, dict)]
    if len(marker_ids) != len(set(marker_ids)) or any(not item for item in marker_ids):
        errors.append("marker ids must be present and unique")
    for marker in markers:
        if marker.get("evidence_tier") not in EVIDENCE_TIERS:
            errors.append(f"marker {marker.get('id', '<unknown>')} has invalid evidence_tier")
        if "known_leakage" not in marker:
            errors.append(f"marker {marker.get('id', '<unknown>')} must declare known_leakage")

    window = plan.get("observation_window", {})
    baseline_start = parse_date(window.get("baseline_start"), "baseline_start", errors)
    baseline_end = parse_date(window.get("baseline_end"), "baseline_end", errors)
    treatment_start = parse_date(window.get("treatment_start"), "treatment_start", errors)
    treatment_end = parse_date(window.get("treatment_end"), "treatment_end", errors)
    if baseline_start and baseline_end and baseline_start > baseline_end:
        errors.append("baseline_start must not be after baseline_end")
    if baseline_end and treatment_start and baseline_end >= treatment_start:
        errors.append("baseline must end before treatment starts")
    if treatment_start and treatment_end and treatment_start > treatment_end:
        errors.append("treatment_start must not be after treatment_end")
    maturity_days = window.get("maturity_days")
    if not isinstance(maturity_days, int) or maturity_days < 0:
        errors.append("maturity_days must be a non-negative integer")

    economics = plan.get("economics", {})
    value_basis = economics.get("value_basis")
    if value_basis not in VALUE_BASES:
        errors.append("economics.value_basis is invalid")
    cost_scope = economics.get("cost_scope", [])
    if not cost_scope:
        errors.append("economics.cost_scope must not be empty")
    if plan["objective"] == "contribution_margin" and value_basis != "contribution_margin":
        errors.append("contribution_margin objective requires contribution_margin value_basis")

    deduplication = plan.get("deduplication", {})
    if not deduplication.get("entity_key"):
        errors.append("deduplication.entity_key is required")
    if deduplication.get("attribution_model") not in {
        "first_touch", "last_touch", "linear", "multi_touch", "incremental"
    }:
        errors.append("deduplication.attribution_model is invalid")

    rules = plan.get("decision_rules", {})
    for outcome in ("scale", "iterate", "stop"):
        if not isinstance(rules.get(outcome), str) or not rules[outcome].strip():
            errors.append(f"decision_rules.{outcome} is required")

    experiment = plan.get("experiment")
    experimental_markers = [m for m in markers if m.get("evidence_tier") == "experimental"]
    if experimental_markers and not experiment:
        errors.append("experimental evidence requires an experiment definition")
    if experiment and experiment.get("design") not in {None, "none"}:
        if not experiment.get("treatment_units") or not experiment.get("control_units"):
            errors.append("experiment requires treatment_units and control_units")
        if "contamination_risks" not in experiment:
            errors.append("experiment must declare contamination_risks")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a GEO attribution plan")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    try:
        plan = load_plan(args.path)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"GEO attribution plan validation failed:\n- {exc}")
        return 1
    errors = validate_plan(plan)
    if errors:
        print("GEO attribution plan validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"GEO attribution plan validation passed: {plan['plan_id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
