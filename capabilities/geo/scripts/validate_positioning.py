#!/usr/bin/env python3
"""Check positioning references and review gates, not semantic truth."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

SYSTEM = Path(__file__).resolve().parents[3]

DIMENSIONS = {"region", "customer", "group", "price", "scenario"}
FACETS = ("identity", "audience", "scenario", "problem", "advantage")
EVIDENCE_TYPES = {"official_source", "direct_evidence", "owner_statement", "company_claim", "customer_report", "internal_definition"}
OWNER_CATEGORIES = {"founder_viewpoint", "firsthand_experience", "internal_process", "product_intent"}


def validate_positioning(data: object, root: Path | str) -> dict:
    errors: list[str] = []
    warnings: list[str] = ["Semantic correctness requires an accountable review; this validator checks structure and evidence references only."]
    unresolved: list[str] = []

    def text(value: object) -> bool:
        return isinstance(value, str) and bool(value.strip())

    def report() -> dict:
        if isinstance(data, dict) and data.get("status") == "ready":
            errors.extend(unresolved)
        else:
            warnings.extend(unresolved)
        return {"verdict": "FAIL" if errors else "PASS", "creation_ready": not errors and not unresolved and isinstance(data, dict) and data.get("status") == "ready", "errors": errors, "warnings": warnings}

    if not isinstance(data, dict):
        errors.append("positioning must be an object")
        return report()
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        errors.append("schema_version must be 1")
    if not text(data.get("id")):
        errors.append("id is required")
    revision = data.get("revision")
    if type(revision) is not int or revision < 1:
        errors.append("revision must be a positive integer")
    if data.get("status") not in ("draft", "ready"):
        errors.append("status must be draft or ready")
    if "statement" in data and not isinstance(data["statement"], str):
        errors.append("statement must be a string")
    if not text(data.get("statement")):
        unresolved.append("statement is required")

    facts: dict[str, dict] = {}
    sources: set[str] = set()
    located_sources: set[str] = set()
    root = Path(root).resolve()
    pack_value = data.get("fact_pack")
    try:
        if not text(pack_value) or Path(pack_value).is_absolute():
            raise ValueError("fact_pack must be a relative path under facts/")
        pack = (root / pack_value).resolve()
        pack.relative_to(root / "facts")
        manifest = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
        if not isinstance(manifest, dict) or not isinstance(manifest.get("sources"), list):
            raise ValueError("manifest.sources must be a list")
        for source in manifest["sources"]:
            if not isinstance(source, dict) or not text(source.get("id")):
                raise ValueError("invalid manifest source")
            if source["id"] in sources:
                errors.append(f"duplicate source ID: {source['id']}")
            sources.add(source["id"])
            if text(source.get("locator")):
                located_sources.add(source["id"])
        for number, line in enumerate((pack / "facts.jsonl").read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            fact = json.loads(line)
            if not isinstance(fact, dict) or not text(fact.get("id")):
                raise ValueError(f"invalid fact at line {number}")
            if fact["id"] in facts:
                errors.append(f"duplicate fact ID: {fact['id']}")
            facts[fact["id"]] = fact
    except (OSError, ValueError, TypeError) as exc:
        errors.append(f"fact_pack: {exc}")

    def references(value: object, field: str, required: bool = True, boundary: bool = False) -> None:
        if not isinstance(value, list) or any(not text(item) for item in value):
            errors.append(f"{field} must be a list of fact IDs")
            return
        if len(value) != len(set(value)):
            errors.append(f"{field} contains duplicate fact IDs")
        if required and not value:
            unresolved.append(f"{field} requires evidence")
        for fact_id in value:
            fact = facts.get(fact_id)
            if fact is None:
                errors.append(f"{field}: missing fact {fact_id}")
                continue
            prohibited = fact.get("category") == "prohibited_claim" or fact.get("status") == "prohibited_claim"
            if prohibited and not boundary:
                errors.append(f"{field}: prohibited_claim cannot support positive positioning: {fact_id}")
            if ((fact.get("status") != "verified" and not (boundary and prohibited)) or not text(fact.get("source_id"))
                    or fact.get("source_id") not in located_sources or not text(fact.get("source_locator"))
                    or not text(fact.get("verified_at")) or not text(fact.get("evidence_type"))
                    or fact.get("evidence_type") not in EVIDENCE_TYPES
                    or not text(fact.get("claim"))
                    or (fact.get("evidence_type") == "owner_statement" and fact.get("category") not in tuple(OWNER_CATEGORIES))):
                unresolved.append(f"{field}: fact {fact_id} is not usable verified evidence")

    positioning = data.get("positioning")
    if not isinstance(positioning, dict):
        errors.append("positioning must be an object")
    else:
        for name in FACETS:
            facet = positioning.get(name)
            if not isinstance(facet, dict):
                errors.append(f"positioning.{name} must be an object")
                continue
            if "text" in facet and not isinstance(facet["text"], str):
                errors.append(f"positioning.{name}.text must be a string")
            if not text(facet.get("text")):
                unresolved.append(f"positioning.{name}.text is required")
            references(facet.get("fact_ids"), f"positioning.{name}.fact_ids")
    tags = data.get("tags")
    dimensions = []
    if not isinstance(tags, list):
        errors.append("tags must be a list")
    else:
        for tag in tags:
            if not isinstance(tag, dict):
                errors.append("each tag must be an object")
                continue
            dimension = tag.get("dimension")
            if not isinstance(dimension, str):
                errors.append("tag dimension must be a string")
                continue
            dimensions.append(dimension)
            for field in ("text", "reason"):
                if not isinstance(tag.get(field), str):
                    errors.append(f"tag {dimension}: {field} must be a string")
            status = tag.get("status")
            if status not in ("known", "unknown", "not_applicable"):
                errors.append(f"tag {dimension}: invalid status")
            if status == "known" and not text(tag.get("text")):
                unresolved.append(f"tag {dimension}: text is required")
            if status in ("unknown", "not_applicable") and not text(tag.get("reason")):
                errors.append(f"tag {dimension}: reason is required")
            references(tag.get("fact_ids"), f"tags.{dimension}.fact_ids", required=status == "known")
        if len(dimensions) != 5 or set(dimensions) != DIMENSIONS:
            errors.append("tags must contain exactly the five unique dimensions")
    references(data.get("boundaries"), "boundaries", required=False, boundary=True)
    applications = data.get("applications")
    if not isinstance(applications, list) or not applications:
        errors.append("applications must contain at least one application")
    else:
        artifact_paths = set()
        for index, application in enumerate(applications):
            label = f"applications[{index}]"
            if not isinstance(application, dict):
                errors.append(f"{label} must be an object")
                continue
            for field in ("channel", "audience", "scenario", "problem"):
                if not text(application.get(field)):
                    unresolved.append(f"{label}.{field} is required")
            artifact = application.get("artifact_path")
            artifact_hash = None
            if not text(artifact):
                unresolved.append(f"{label}.artifact_path is required")
            else:
                try:
                    if Path(artifact).is_absolute():
                        raise ValueError("artifact_path must be project-relative")
                    resolved = (root / artifact).resolve()
                    resolved.relative_to(root)
                    if resolved in artifact_paths:
                        errors.append(f"duplicate application artifact_path: {artifact}")
                    artifact_paths.add(resolved)
                    if not resolved.is_file():
                        raise ValueError("artifact_path must be an existing regular file")
                    artifact_hash = hashlib.sha256(resolved.read_bytes()).hexdigest()
                except (OSError, ValueError) as exc:
                    unresolved.append(f"{label}.artifact_path: {exc}")
            if type(application.get("positioning_revision")) is not int or application["positioning_revision"] != revision:
                unresolved.append(f"{label}: stale positioning_revision")
            references(application.get("used_fact_ids"), f"{label}.used_fact_ids")
            review = application.get("review")
            if not isinstance(review, dict) or review.get("status") not in ("pending", "pass", "fail"):
                errors.append(f"{label}.review is invalid")
            elif review["status"] != "pass" or not text(review.get("reviewer")) or not text(review.get("note")):
                unresolved.append(f"{label}: semantic review must pass with reviewer and note")
            if isinstance(review, dict) and (artifact_hash is None or review.get("artifact_sha256") != artifact_hash):
                unresolved.append(f"{label}: review artifact_sha256 does not match current artifact")
    return report()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="项目根。默认按 .hq-geo.json 找——定位卡和它引用的事实包都在项目里，不在系统里",
    )
    parser.add_argument("--require-ready", action="store_true", help="Fail unless creation_ready is true")
    args = parser.parse_args()

    # 运行时才找项目根，不在 import 时找：单测 import 这个模块时不该要求存在一个项目。
    root = args.root
    if root is None:
        sys.path.insert(0, str(SYSTEM))
        from project import find_project

        root = find_project()

    try:
        result = validate_positioning(json.loads(args.path.read_text(encoding="utf-8")), root)
    except (OSError, ValueError) as exc:
        result = {"verdict": "FAIL", "creation_ready": False, "errors": [str(exc)], "warnings": []}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["verdict"] == "PASS" and (not args.require_ready or result["creation_ready"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
