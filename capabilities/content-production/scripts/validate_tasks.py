#!/usr/bin/env python3
"""校验项目里 tasks/ 下的任务单据格式。格式约定见
capabilities/content-production/tasks/README.md。

任务是实例层的入口单据。格式坏了，Agent 就读不到用户原话，
或者会把状态写进用户负责的区块——那是四层混装的开始。

任务单据住在**项目根**，这个脚本住在**系统根**。所以路径不能在 import 时算，
要等到真的去读目录时再问 project.py。
"""

import re
import sys
from pathlib import Path

_SYSTEM = next((p for p in Path(__file__).resolve().parents if (p / "project.py").is_file()), None)
if _SYSTEM is None:
    raise SystemExit("这个脚本只能在 hq-geo 系统根里运行（向上找不到 project.py）")
sys.path.insert(0, str(_SYSTEM))
from project import find_project  # noqa: E402

TASKS_CONVENTION = _SYSTEM / "capabilities/content-production/tasks/README.md"
TASKS_TEMPLATE = _SYSTEM / "capabilities/content-production/tasks/_template.md"

SKIP = {"README.md", "_template.md"}
SECTIONS = ["## 任务", "## 待确认", "## 交付", "## 分发登记"]
STAGES = {"intake", "research", "drafting", "review", "delivered", "distributed"}
STATUSES = {"needs_input", "in_progress", "blocked", "done"}
DELIVERABLES = {"article", "video", "image"}

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def parse_frontmatter(text: str):
    match = FRONTMATTER.match(text)
    if not match:
        return None, text
    data = {}
    for line in match.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, separator, value = line.partition(":")
        if not separator:
            continue
        data[key.strip()] = value.strip()
    return data, text[match.end():]


def parse_list(value: str) -> list:
    return [item.strip() for item in value.strip("[]").split(",") if item.strip()]


def section_body(text: str, heading: str) -> str:
    """取某个二级标题到下一个二级标题之间的内容。"""
    start = text.find(heading)
    if start < 0:
        return ""
    start += len(heading)
    rest = text[start:]
    end = rest.find("\n## ")
    return (rest if end < 0 else rest[:end]).strip()


def tasks_dir() -> Path:
    """项目根下的 tasks/。到这里才需要知道项目在哪。"""
    return find_project() / "tasks"


def task_files(directory: Path) -> list:
    """目录要传进来，不自己去问项目在哪——这样测试能拿临时目录验，不用造一个项目。"""
    if not directory.is_dir():
        return []
    return sorted(path for path in directory.glob("*.md") if path.name not in SKIP)


def validate(path: Path) -> list:
    errors = []
    text = path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)

    if meta is None:
        return [f"{path.name}: 缺少 frontmatter"]

    for key in ["id", "created", "stage", "status"]:
        if not meta.get(key):
            errors.append(f"{path.name}: frontmatter 缺少 {key}")

    if meta.get("id") and meta["id"] != path.stem:
        errors.append(f"{path.name}: id ({meta['id']}) 与文件名不一致")

    if meta.get("stage") and meta["stage"] not in STAGES:
        errors.append(f"{path.name}: stage 非法值 {meta['stage']!r}，允许 {sorted(STAGES)}")

    if meta.get("status") and meta["status"] not in STATUSES:
        errors.append(f"{path.name}: status 非法值 {meta['status']!r}，允许 {sorted(STATUSES)}")

    for item in parse_list(meta.get("deliverables", "")):
        if item not in DELIVERABLES:
            errors.append(f"{path.name}: deliverables 含非法值 {item!r}，允许 {sorted(DELIVERABLES)}")

    for heading in SECTIONS:
        if heading not in body:
            errors.append(f"{path.name}: 缺少区块 {heading}")

    if not section_body(body, "## 任务"):
        errors.append(f"{path.name}: ## 任务 区块是空的，用户还没写要什么")

    return errors


def main() -> int:
    directory = tasks_dir()
    files = task_files(directory)
    if not files:
        print(f"PASS task contract: {directory} 下还没有任务")
        return 0
    errors = [error for path in files for error in validate(path)]
    if errors:
        print("FAIL task contract")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"PASS task contract: {len(files)} 个任务格式合法")
    return 0


if __name__ == "__main__":
    sys.exit(main())
