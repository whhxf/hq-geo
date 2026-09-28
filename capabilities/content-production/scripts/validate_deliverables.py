#!/usr/bin/env python3
"""校验项目里 content/briefs/ 下的制作简报。

简报住在项目根，这个脚本住在系统根——路径等到真要读目录时再解析，
所以 validate(path) 单独调用不需要存在任何项目。
"""

import json
import sys
from pathlib import Path

_SYSTEM = next((p for p in Path(__file__).resolve().parents if (p / "project.py").is_file()), None)
if _SYSTEM is None:
    raise SystemExit("这个脚本只能在 hq-geo 系统根里运行（向上找不到 project.py）")
sys.path.insert(0, str(_SYSTEM))
from project import find_project  # noqa: E402

REQUIRED = {"schema_version", "id", "topic_id", "title", "status", "objective", "audience", "formats", "core_thesis", "fact_refs", "script", "required_assets", "prohibited_claims", "acceptance_criteria", "handoff"}


def validate(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = [f"missing {key}" for key in sorted(REQUIRED - data.keys())]
    if not data.get("script"):
        errors.append("script must not be empty")
    if not data.get("fact_refs"):
        errors.append("fact_refs must not be empty")
    unresolved = [item for item in data.get("script", []) if item.get("status") == "blocked"]
    if data.get("status") == "ready_for_production" and unresolved:
        errors.append("ready brief contains blocked script sections")
    missing_assets = [item for item in data.get("required_assets", []) if item.get("status") == "missing"]
    if data.get("handoff", {}).get("ready") and (unresolved or missing_assets):
        errors.append("handoff ready while content or assets are missing")
    return errors


def main():
    project = find_project()
    files = sorted((project / "content/briefs").glob("**/production-brief.json"))
    if not files:
        # 新项目一份简报都没有是正常的，不是错误。这个校验器的职责是
        # 「存在的简报都要合法」——空集合上没有反例。
        # 「本来有、现在没了」由产出基准抓，那是另一个信号，见 test/baseline.json。
        print(f"PASS deliverable contract: {project.name} 还没有制作简报")
        return 0
    results = {str(path.relative_to(project)): validate(path) for path in files}
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 1 if any(results.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())

