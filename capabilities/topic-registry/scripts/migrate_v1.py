"""把 v1 的选题记录迁移到 v2。

v1 的问题：一个文件里混了选题本身和生产进度。
`stage`、`status`、`progress`、`next_action`、`updated_at`、`artifacts` 这六个字段
属于生产进度，按 `AGENTS.md` 第 31 行「四层各自独立成文件」不该在这里。

v2 只保留「做不做」，做到哪了去 `tasks/` 看。

## 迁移规则

| v1 | v2 |
|---|---|
| `stage` / `status` / `progress` / `next_action` / `updated_at` / `artifacts` | 删。原值摘要进 `note` |
| `source_status` | 删。`待验证` 的写进 `note` |
| `platforms` 里的 `三平台待适配` / `全平台` | 转成 `[]`，原值写进 `note` |
| 所有选题 | `state: candidate`、`source.kind: imported` |

**为什么全部是 `candidate`**：五问一条都没答。答不上「如何被证伪」的不是选题，是想法。
v1 里 `stage: canonical` 的那几条已经产出母脚本了，但同样没答过五问——
**按规则只能是 `candidate`**。要提升状态，得补答五问，不能靠迁移脚本替它升。

用法：

    python3 capabilities/topic-registry/scripts/migrate_v1.py --project <项目根>          # 只看
    python3 capabilities/topic-registry/scripts/migrate_v1.py --project <项目根> --yes    # 写
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

# 生产进度字段，v2 里不该有
PROGRESS_FIELDS = (
    "stage",
    "status",
    "progress",
    "next_action",
    "updated_at",
    "artifacts",
)

# 不是平台名、只是「还没判断」的占位值
PLACEHOLDER_PLATFORMS = {"三平台待适配", "全平台", "待适配"}


def migrate_registry(data: dict, source_files: list[str]) -> dict:
    topics_v1 = data.get("topics", [])
    imported_from = "；".join(source_files) if source_files else None
    imported_at = str(data.get("imported_at", ""))[:10] or None

    out: list[dict] = []
    for t in topics_v1:
        notes: list[str] = ["v1 迁移"]

        stage = t.get("stage")
        if stage and stage != "topic_ready":
            artifacts = t.get("artifacts") or []
            notes.append(
                f"v1 stage={stage}"
                + (f"，已产出：{'、'.join(artifacts)}" if artifacts else "")
            )

        source_status = t.get("source_status")
        if source_status and source_status != "待写":
            notes.append(f"v1 来源标注「{source_status}」")

        platforms = t.get("platforms") or []
        placeholders = [p for p in platforms if p in PLACEHOLDER_PLATFORMS]
        real_platforms = [p for p in platforms if p not in PLACEHOLDER_PLATFORMS]
        if placeholders:
            notes.append(f"v1 platforms={placeholders} → 转成空数组")

        note = "；".join(notes) + "。五问未答，state 只能是 candidate。"

        out.append(
            {
                "id": t["id"],
                "title": t["title"],
                "source": {
                    "kind": "imported",
                    "imported_from": imported_from,
                    "imported_at": imported_at,
                },
                "collection": t.get("collection"),
                "pillar": t.get("pillar"),
                "angle": t.get("angle"),
                "proof": t.get("proof"),
                "platforms": real_platforms,
                "state": "candidate",
                "note": note,
            }
        )

    return {
        "schema_version": 2,
        "idea_id": data.get("idea_id"),
        "selected_topic_id": None,
        "topics": out,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="把 v1 选题记录迁移到 v2")
    parser.add_argument("--project", required=True, help="项目根目录")
    parser.add_argument("--yes", action="store_true", help="真的写盘（默认只看）")
    args = parser.parse_args(argv)

    project = Path(args.project).expanduser().resolve()
    if not (project / ".hq-geo.json").is_file():
        print(f"FAIL  这里不是 hq-geo 项目根：{project}")
        return 1

    targets = sorted((project / "topics").rglob("*.json"))
    if not targets:
        print("PASS  没有需要迁移的选题记录")
        return 0

    for path in targets:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("schema_version") == 2:
            print(f"SKIP  {path.relative_to(project)} 已经是 v2")
            continue

        source_files = data.get("source_files") or []
        migrated = migrate_registry(data, source_files)
        rel = path.relative_to(project)

        kept = [f for f in PROGRESS_FIELDS if any(f in t for t in data.get("topics", []))]
        print(f"\n{'写盘' if args.yes else '预览'}  {rel}")
        print(f"  {len(data.get('topics', []))} 条 → state=candidate，source.kind=imported")
        print(f"  删掉的进度字段：{kept or '无'}")
        print(f"  selected_topic_id: {data.get('selected_topic_id')!r} → None")
        noted = sum(1 for t in migrated["topics"] if t["note"].count("；") >= 1)
        print(f"  带额外迁移说明的：{noted} 条")

        if args.yes:
            backup = path.with_suffix(".v1.bak.json")
            if not backup.exists():
                shutil.copy2(path, backup)
                print(f"  备份 → {backup.relative_to(project)}")
            path.write_text(
                json.dumps(migrated, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"  已写 {rel}")

    if not args.yes:
        print("\n这是预览。加 --yes 才写盘。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
