#!/usr/bin/env python3
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load_json(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    manifest = load_json(ROOT / "test/test_manifest.json")
    registry = load_json(ROOT / "test/feature_registry.json")
    test_ids = {item["id"] for item in manifest["tests"]}
    errors = []

    declared_tiers = set(manifest.get("tiers", []))
    if not declared_tiers:
        errors.append("test_manifest.json 未声明测试层级")

    if len(test_ids) != len(manifest["tests"]):
        errors.append("test_manifest.json 中存在重复测试 ID")

    for item in manifest["tests"]:
        if not item.get("command") or not isinstance(item["command"], list):
            errors.append(f"测试 {item.get('id', '<unknown>')} 缺少参数数组形式的 command")
        if item.get("timeout_seconds", 0) <= 0:
            errors.append(f"测试 {item.get('id', '<unknown>')} timeout_seconds 无效")
        if item.get("tier") not in declared_tiers:
            errors.append(f"测试 {item.get('id', '<unknown>')} 使用了未声明的层级 {item.get('tier')!r}")

    feature_ids = [item["id"] for item in registry["features"]]
    if len(set(feature_ids)) != len(feature_ids):
        errors.append("feature_registry.json 中存在重复功能 ID")

    for feature in registry["features"]:
        label = f"{feature['id']} ({feature['status']})"
        if feature["status"] in {"implemented", "partial"} and not feature["test_ids"]:
            errors.append(f"{label} 没有绑定测试")
        unknown = sorted(set(feature["test_ids"]) - test_ids)
        if unknown:
            errors.append(f"{label} 引用了不存在的测试: {', '.join(unknown)}")
        for owner_path in feature["owner_paths"]:
            if not (ROOT / owner_path).exists():
                errors.append(f"{label} 的责任路径不存在: {owner_path}")

    frozen = registry.get("frozen", [])
    for item in frozen:
        if item["id"] in feature_ids:
            errors.append(f"冻结条目 {item['id']} 不得同时登记为现有能力")
        if not (ROOT / item["path"]).exists():
            errors.append(f"冻结条目 {item['id']} 的路径不存在: {item['path']}")
        if not item.get("note"):
            errors.append(f"冻结条目 {item['id']} 缺少冻结原因与恢复条件")

    if errors:
        print("FAIL feature registry contract")
        for error in errors:
            print(f"- {error}")
        return 1

    covered = sum(1 for item in registry["features"] if item["status"] != "planned")
    planned = sum(1 for item in registry["features"] if item["status"] == "planned")
    print(
        f"PASS feature registry contract: {covered} 个现有能力均有测试，"
        f"{planned} 个规划能力未冒充已实现，{len(frozen)} 项已冻结"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
