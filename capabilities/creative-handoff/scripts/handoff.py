#!/usr/bin/env python3
"""创意交接：校验 CreativeJob 与制作回执，并把回执同步进项目根。

回执落盘的 `assets/generated/` 在**项目根**，这个脚本在系统根——
所以目标路径在 sync_receipt 里才解析，其余校验与项目无关。
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

_SYSTEM = next((p for p in Path(__file__).resolve().parents if (p / "project.py").is_file()), None)
if _SYSTEM is None:
    raise SystemExit("这个脚本只能在 hq-geo 系统根里运行（向上找不到 project.py）")
sys.path.insert(0, str(_SYSTEM))
from project import find_project  # noqa: E402

JOB_REQUIRED = {"schema_version", "job_id", "revision", "source", "title", "objective", "audience", "target", "strategy", "inputs", "scenes", "constraints", "deliverables", "production_units", "decision_policy", "handoff"}
RECEIPT_REQUIRED = {"schema_version", "job_id", "revision", "content_id", "status", "strategy", "project_path", "outputs", "checks", "created_at"}


def load(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("document must be a JSON object")
    return value


def require_keys(value: dict, keys: set[str], label: str) -> None:
    missing = sorted(keys - value.keys())
    if missing:
        raise ValueError(f"{label} missing fields: {', '.join(missing)}")


def validate_job(value: dict) -> None:
    require_keys(value, JOB_REQUIRED, "CreativeJob")
    if value["schema_version"] != 1 or not isinstance(value["revision"], int) or value["revision"] < 1:
        raise ValueError("CreativeJob schema_version must be 1 and revision must be >= 1")
    require_keys(value["source"], {"idea_id", "topic_id", "content_id", "production_brief_path"}, "CreativeJob.source")
    if not Path(value["source"]["production_brief_path"]).is_absolute():
        raise ValueError("CreativeJob.source.production_brief_path must be absolute")
    if not value["scenes"] or not value["production_units"]:
        raise ValueError("CreativeJob requires at least one scene and production unit")
    require_keys(value["deliverables"], {"shared", "channels"}, "CreativeJob.deliverables")
    if not value["deliverables"]["shared"] or not value["deliverables"]["channels"]:
        raise ValueError("CreativeJob requires shared and channel deliverables")


def validate_receipt(value: dict, verify_files: bool = True) -> None:
    require_keys(value, RECEIPT_REQUIRED, "ProductionReceipt")
    if value["schema_version"] != 1:
        raise ValueError("ProductionReceipt schema_version must be 1")
    project = Path(value["project_path"]).resolve()
    if not project.is_absolute():
        raise ValueError("ProductionReceipt.project_path must be absolute")
    for output in value["outputs"]:
        require_keys(output, {"id", "type", "path", "sha256", "synthetic", "status"}, "ProductionReceipt.output")
        media = Path(output["path"]).resolve()
        if project != media and project not in media.parents:
            raise ValueError(f"output escapes project path: {media}")
        if verify_files and output["status"] == "completed":
            if not media.is_file():
                raise ValueError(f"completed output missing: {media}")
            digest = hashlib.sha256(media.read_bytes()).hexdigest()
            if digest != output["sha256"]:
                raise ValueError(f"checksum mismatch: {media}")


def sync_receipt(path: Path) -> Path:
    receipt = load(path)
    validate_receipt(receipt)
    target = find_project() / "assets" / "generated" / receipt["content_id"] / "manifest.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        existing = load(target)
        if existing.get("job_id") == receipt["job_id"] and existing.get("revision") == receipt["revision"]:
            raise ValueError("receipt revision already synced; create a new revision")
    manifest = {"schema_version": 1, "source_receipt": str(path.resolve()), **receipt}
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["validate-job", "validate-receipt", "sync-receipt"])
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    try:
        value = load(args.path)
        if args.command == "validate-job": validate_job(value)
        elif args.command == "validate-receipt": validate_receipt(value)
        else:
            print(sync_receipt(args.path))
            return 0
        print("PASS")
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
