#!/usr/bin/env python3
"""Validate folder-based fact packs and optionally write their gate reports.

事实包住在**项目根**的 `facts/`，这个脚本住在系统根。所以路径按需解析：
validate_pack() 只认传进来的路径，发现默认目录时才需要知道项目在哪。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

_SYSTEM = next((p for p in Path(__file__).resolve().parents if (p / "project.py").is_file()), None)
if _SYSTEM is None:
    raise SystemExit("这个脚本只能在 hq-geo 系统根里运行（向上找不到 project.py）")
sys.path.insert(0, str(_SYSTEM))
from project import find_project  # noqa: E402

ENTITY_TYPES = {"company", "product", "feature", "method", "scenario", "claim"}
FACT_STATUSES = {"verified", "needs_confirmation", "conflict", "expired", "prohibited_claim"}
EVIDENCE_TYPES = {"official_source", "direct_evidence", "owner_statement", "company_claim", "customer_report", "internal_definition", "inference", "unknown"}
SLOT_STATUSES = {"present", "partial", "missing"}
REQUIRED_DIRS = ("text", "media/images", "media/videos", "reviews")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def display_path(path: Path) -> str:
    """能相对项目根显示就相对显示，否则给绝对路径。没有项目也不该报错。"""
    try:
        return str(path.relative_to(find_project()))
    except (ValueError, SystemExit):
        return str(path)


def validate_pack(pack: Path) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    required_files = ("manifest.json", "SOURCE_OF_TRUTH.md", "facts.jsonl")
    for name in required_files:
        if not (pack / name).is_file():
            errors.append(f"missing required file: {name}")
    for name in REQUIRED_DIRS:
        if not (pack / name).is_dir():
            errors.append(f"missing required directory: {name}")
    if errors:
        return {"pack": display_path(pack), "verdict": "FAIL", "errors": errors, "warnings": warnings}

    try:
        manifest = load_json(pack / "manifest.json")
        facts = load_jsonl(pack / "facts.jsonl")
    except (json.JSONDecodeError, OSError) as exc:
        return {"pack": display_path(pack), "verdict": "FAIL", "errors": [f"invalid data: {exc}"], "warnings": []}

    for field in ("schema_version", "id", "entity_type", "slug", "name", "required_slots", "protected_fact_ids", "sources", "media_assets"):
        if field not in manifest:
            errors.append(f"manifest missing field: {field}")
    if manifest.get("entity_type") not in ENTITY_TYPES:
        errors.append(f"invalid entity_type: {manifest.get('entity_type')}")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", str(manifest.get("slug", ""))):
        errors.append("slug must use lowercase kebab-case")
    expected_name = f"{manifest.get('slug')}--{manifest.get('id')}"
    if pack.name != expected_name:
        errors.append(f"folder must be named {expected_name}")

    sources = {item.get("id"): item for item in manifest.get("sources", [])}
    ids: set[str] = set()
    for index, fact in enumerate(facts, 1):
        fact_id = fact.get("id")
        if not fact_id:
            errors.append(f"fact line {index} missing id")
            continue
        if fact_id in ids:
            errors.append(f"duplicate fact id: {fact_id}")
        ids.add(fact_id)
        for field in ("claim", "category", "evidence_type", "status", "source_id", "source_locator", "scope"):
            if not fact.get(field):
                errors.append(f"{fact_id} missing {field}")
        if fact.get("status") not in FACT_STATUSES:
            errors.append(f"{fact_id} has invalid status")
        if fact.get("evidence_type") not in EVIDENCE_TYPES:
            errors.append(f"{fact_id} has invalid evidence_type")
        if fact.get("source_id") not in sources:
            errors.append(f"{fact_id} references unknown source_id")
        if fact.get("status") == "verified":
            if fact.get("evidence_type") not in {"official_source", "direct_evidence", "owner_statement", "company_claim", "customer_report", "internal_definition"}:
                errors.append(f"{fact_id} cannot be verified from {fact.get('evidence_type')}")
            if fact.get("evidence_type") == "owner_statement" and fact.get("category") not in {"founder_viewpoint", "firsthand_experience", "internal_process", "product_intent"}:
                errors.append(f"{fact_id} owner_statement cannot verify external category {fact.get('category')}")
            if not fact.get("verified_at"):
                errors.append(f"{fact_id} verified without verified_at")

    for protected_id in manifest.get("protected_fact_ids", []):
        if protected_id not in ids:
            errors.append(f"protected fact missing: {protected_id}")

    question_ids: set[str] = set()
    for question in manifest.get("pending_questions", []):
        question_id = question.get("id")
        if not question_id or question_id in question_ids:
            errors.append(f"invalid or duplicate pending question: {question_id}")
            continue
        question_ids.add(question_id)
        for field in ("question", "reason", "target_category", "answer_policy", "status", "priority", "blocks"):
            if field not in question or question[field] in (None, "", []):
                errors.append(f"{question_id} missing {field}")
        if question.get("status") not in {"pending", "resolved", "dismissed"}:
            errors.append(f"{question_id} has invalid status")
        if question.get("status") == "resolved" and not (question.get("result_fact_ids") or question.get("result_asset_ids")):
            errors.append(f"{question_id} resolved without a result")

    slots = manifest.get("required_slots", [])
    slot_ids: set[str] = set()
    for slot in slots:
        slot_id = slot.get("id")
        if not slot_id:
            errors.append("required slot missing id")
            continue
        if slot_id in slot_ids:
            errors.append(f"duplicate required slot: {slot_id}")
        slot_ids.add(slot_id)
        if slot.get("status") not in SLOT_STATUSES:
            errors.append(f"{slot_id} has invalid slot status")
        for fact_id in slot.get("fact_ids", []):
            if fact_id not in ids:
                errors.append(f"{slot_id} references missing fact: {fact_id}")
        linked_path = slot.get("path")
        if linked_path and not (pack / linked_path).is_file():
            errors.append(f"{slot_id} references missing file: {linked_path}")
        if slot.get("status") == "missing":
            warnings.append(f"required slot missing: {slot.get('label', slot_id)}")
        elif slot.get("status") == "partial":
            warnings.append(f"required slot partial: {slot.get('label', slot_id)}")

    assets = {asset.get("id"): asset for asset in manifest.get("media_assets", [])}
    for slot in slots:
        for asset_id in slot.get("asset_ids", []):
            if asset_id not in assets:
                errors.append(f"{slot.get('id')} references missing asset: {asset_id}")
    for asset_id, asset in assets.items():
        status = asset.get("status")
        if status not in SLOT_STATUSES:
            errors.append(f"{asset_id} has invalid asset status")
        if status == "present":
            for field in ("mime_type", "source_id", "purpose", "rights_status", "review_status"):
                if not asset.get(field):
                    errors.append(f"present asset {asset_id} missing {field}")
            if asset.get("source_id") not in sources:
                errors.append(f"present asset {asset_id} references unknown source")
            local_path = asset.get("path")
            url = asset.get("url")
            if not local_path and not url:
                errors.append(f"present asset {asset_id} has no path or url")
            if local_path:
                file_path = (pack / local_path).resolve()
                if pack.resolve() not in file_path.parents or not file_path.is_file():
                    errors.append(f"present asset {asset_id} local file is missing or unsafe")
                elif not asset.get("sha256"):
                    errors.append(f"present asset {asset_id} missing sha256")
                elif sha256(file_path) != asset.get("sha256"):
                    errors.append(f"present asset {asset_id} sha256 mismatch")
        elif asset.get("path") or asset.get("url"):
            errors.append(f"non-present asset {asset_id} must not expose a usable path or url")

    completeness = round(sum(slot.get("status") == "present" for slot in slots) / len(slots) * 100) if slots else 0
    return {
        "schema_version": 1,
        "generated_at": date.today().isoformat(),
        "pack": display_path(pack),
        "id": manifest.get("id"),
        "name": manifest.get("name"),
        "verdict": "FAIL" if errors else "PASS",
        "creation_ready": not errors and all(slot.get("status") == "present" for slot in slots),
        "completeness": completeness,
        "slot_counts": {
            status: sum(slot.get("status") == status for slot in slots) for status in ("present", "partial", "missing")
        },
        "errors": errors,
        "warnings": warnings,
    }


def discover(root: Path) -> list[Path]:
    return sorted(path.parent for path in root.glob("*/*/manifest.json"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", type=Path, help="fact pack path relative to project root or absolute")
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()
    project = find_project()
    packs = [args.pack if args.pack.is_absolute() else project / args.pack] if args.pack else discover(project / "facts")
    if not packs:
        # 新项目还没有事实包是正常的，不是错误。职责是「存在的事实包都要合法」。
        # 「本来有、现在没了」由产出基准抓，那是另一个信号。
        print(f"PASS fact pack contract: {project.name} 还没有事实包")
        return 0
    reports = [validate_pack(pack.resolve()) for pack in packs]
    if args.write_report:
        for pack, report in zip(packs, reports):
            target = pack / "reviews" / "gate-report.json"
            target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(reports, ensure_ascii=False, indent=2))
    return 1 if any(report["verdict"] == "FAIL" for report in reports) else 0


if __name__ == "__main__":
    raise SystemExit(main())
