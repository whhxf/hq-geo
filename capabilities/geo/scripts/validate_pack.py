#!/usr/bin/env python3
"""Validate the project-local GEO capability manifest and skill entry points."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = PROJECT_ROOT / "capabilities/geo/manifest.json"
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
FIELD_RE = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_-]*):\s*(.+?)\s*$", re.MULTILINE)
GLOBAL_PATH_MARKERS = (
    "/Users/conan/.agents/skills",
    "/Users/conan/.codex/skills",
    "~/.agents/skills",
    "~/.codex/skills",
)


def load_manifest() -> dict:
    with MANIFEST_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.search(text)
    if not match:
        return {}
    return {key: value.strip('"\'') for key, value in FIELD_RE.findall(match.group(1))}


def validate_pack() -> list[str]:
    errors: list[str] = []
    manifest = load_manifest()

    positioning_contract = manifest.get("positioning_contract", "")
    try:
        contract = json.loads((PROJECT_ROOT / positioning_contract).read_text(encoding="utf-8"))
        if "positioning" not in contract.get("required", []):
            errors.append("positioning contract must require positioning")
    except (OSError, ValueError):
        errors.append("missing or invalid positioning contract")

    for relative_path in manifest.get("method_sources", []):
        if not (PROJECT_ROOT / relative_path).is_file():
            errors.append(f"missing method source: {relative_path}")

    contract_path = manifest.get("contract")
    if not contract_path or not (PROJECT_ROOT / contract_path).is_file():
        errors.append(f"missing contract: {contract_path}")

    attribution_contract_path = manifest.get("attribution_contract")
    if not attribution_contract_path or not (
        PROJECT_ROOT / attribution_contract_path
    ).is_file():
        errors.append(f"missing attribution contract: {attribution_contract_path}")

    declared_skills = list(manifest.get("skills", []))
    orchestrator = manifest.get("orchestrator")
    if orchestrator:
        declared_skills.append(orchestrator)

    names: set[str] = set()
    for skill in declared_skills:
        name = skill.get("name", "")
        relative_path = skill.get("path", "")
        path = PROJECT_ROOT / relative_path
        if name in names:
            errors.append(f"duplicate skill name: {name}")
        names.add(name)
        if not path.is_file():
            errors.append(f"missing skill: {relative_path}")
            continue
        metadata = parse_frontmatter(path)
        if metadata.get("name") != name:
            errors.append(
                f"frontmatter name mismatch in {relative_path}: "
                f"expected {name!r}, got {metadata.get('name')!r}"
            )
        if not metadata.get("description"):
            errors.append(f"missing description in {relative_path}")
        text = path.read_text(encoding="utf-8")
        for marker in GLOBAL_PATH_MARKERS:
            if marker in text:
                errors.append(f"global skill path leaked into {relative_path}: {marker}")

        evals_path = path.parent / "evals/evals.json"
        if not evals_path.is_file():
            errors.append(f"missing eval set: {evals_path.relative_to(PROJECT_ROOT)}")
        else:
            try:
                evals = json.loads(evals_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                errors.append(
                    f"invalid eval JSON in {evals_path.relative_to(PROJECT_ROOT)}: {exc}"
                )
            else:
                if evals.get("skill_name") != name:
                    errors.append(
                        f"eval skill_name mismatch in "
                        f"{evals_path.relative_to(PROJECT_ROOT)}"
                    )
                if len(evals.get("evals", [])) < 2:
                    errors.append(
                        f"eval set needs at least two cases: "
                        f"{evals_path.relative_to(PROJECT_ROOT)}"
                    )

    if manifest.get("scope") != "project":
        errors.append("manifest scope must be 'project'")
    if "guaranteed_ai_citation" not in manifest.get("never_global_defaults", []):
        errors.append("manifest must reject guaranteed AI citation")
    if "geo_attribution_or_roi" not in manifest.get("full_geo_routes", []):
        errors.append("manifest must route GEO attribution and ROI work")
    return errors


def main() -> int:
    errors = validate_pack()
    if errors:
        print("GEO capability pack validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    manifest = load_manifest()
    skill_count = len(manifest["skills"]) + 1
    print(f"GEO capability pack validation passed ({skill_count} skill entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
