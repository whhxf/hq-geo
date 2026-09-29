#!/usr/bin/env python3
"""系统与项目的分根边界检查。

取代已归档的 `lib/smoke_check.py`。旧检查验证的是 CSV 表头和 01-08 编号脚本，
本项目已不再使用。这里验证分根之后真正要守的四件事：

1. 系统根有方法、契约、门禁；
2. 项目根有实例层的全套目录；
3. **系统根里不出现实例层目录**——实例数据长回系统根，第二个项目就又要
   跟第一个项目的数据挤在一起，分根就白分了；
4. **系统层文件里不出现当前项目的标识**——写死了名字，第二个项目无法复用
   同一套方法（宪法第 3 条）。

第 3 条是这次分根新加的不变量，也是唯一一条不依赖「知道项目叫什么」就能
成立的边界检查：哪怕系统里写死了某个我们没在测的项目名，它也能挡住
「把实例数据搬回系统」这一类退化。
"""

import ast
import json
import sys
from pathlib import Path


SYSTEM = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SYSTEM))
from project import MARKER, find_project  # noqa: E402

PROJECT = find_project()

# 系统根必须有的：方法、契约、校验器、门禁。
SYSTEM_REQUIRED = [
    "AGENTS.md",
    "PLAYBOOK.md",
    "project.py",
    "capabilities/geo/manifest.json",
    "capabilities/content-production/contracts/production-brief.schema.json",
    "capabilities/content-production/tasks/README.md",
    "capabilities/creative-handoff/contracts/creative-job.schema.json",
    "capabilities/fact-packs/scripts/validate_fact_pack.py",
    "capabilities/fact-packs/schemas/README.md",
    "capabilities/project-scaffold/scripts/init_project.py",
    "capabilities/sourcing/interview-method.md",
    "skills/content-orchestrator/SKILL.md",
    "skills/sourcing/SKILL.md",
    "test/run_quality_gate.py",
]

# 项目根必须有的：每个项目一套的实例层。
PROJECT_REQUIRED = [
    MARKER,
    "LEARNING.md",
    "tasks",
    "data/events",
    "data/ideas",
    "facts",
    "research/raw",
    "research/normalized",
    "content/briefs",
    "content/packages",
    "content/styles",
    "assets/generated",
]

# 实例层的目录名。出现在系统根就是分根被破坏。
INSTANCE_ONLY = ["tasks", "facts", "topics", "content", "assets", "research", "data", "LEARNING.md"]

# 系统层的目录名。出现在项目根就是把系统代码复制进了项目，
# 那份副本会和系统根各演化一遍——正是项目 CLAUDE.md 的第二条边界要挡的事。
SYSTEM_ONLY = ["capabilities", "skills", "test", "00-meta"]

# 系统层：跨项目复用的方法、契约与校验器。不得出现任何具体项目标识。
# 测试也算系统层：把某个项目的路径写成 fixture，第二个项目就无从复用。
#
# 根目录文档（AGENTS.md、PLAYBOOK.md、README.md、BACKLOG.md）**不在**这个清单里，
# 是有意的：手册要告诉用户「现在到哪一步了」，那本来就该点名当前项目。
# 方法、契约、校验器里出现项目名才是问题——那些要跨项目复用。
SYSTEM_LAYER = [
    "capabilities/geo",
    "capabilities/content-production",
    "capabilities/creative-handoff",
    "capabilities/fact-packs",
    "capabilities/project-scaffold",
    "capabilities/sourcing",
    "skills",
    "test",
]

SYSTEM_PYTHON_ROOTS = ["capabilities", "test"]

# 生成物不算源码。门禁报告按项目分目录存在 test/reports/<项目>/ 下，
# 里面本来就写着项目名和产出数字——那是运行结果，不是系统层写死了标识。
GENERATED = ["test/reports", "__pycache__"]

RETIRED_MODULES = [
    "01-intent", "02-compete", "03-content", "04-monitor",
    "05-report", "06-source-pool", "07-prepublish", "lib",
]


def project_slugs() -> set:
    """从项目根发现项目标识，而不是在测试里再写死一个。

    三个来源：标记文件里的 slug、`topics/` 与 `data/ideas/` 下的条目名。
    标记文件是权威，后两者兜住「slug 改过但目录名还是老的」这种情况。
    """
    slugs = set()
    descriptor = json.loads((PROJECT / MARKER).read_text(encoding="utf-8"))
    if descriptor.get("slug"):
        slugs.add(descriptor["slug"])
    for base in ["topics", "data/ideas"]:
        directory = PROJECT / base
        if not directory.is_dir():
            continue
        for entry in directory.iterdir():
            if entry.name.startswith("."):
                continue
            slugs.add(entry.stem if entry.is_file() else entry.name)
    return slugs


def check_required(errors: list) -> None:
    for relative in SYSTEM_REQUIRED:
        if not (SYSTEM / relative).exists():
            errors.append(f"系统根缺少必需路径: {relative}")
    for relative in PROJECT_REQUIRED:
        if not (PROJECT / relative).exists():
            errors.append(f"项目根缺少必需路径: {relative}（新建项目跑 capabilities/project-scaffold）")


def check_root_separation(errors: list) -> None:
    """两个根各自只能有自己的东西。这一条不需要知道任何项目名。"""
    for name in INSTANCE_ONLY:
        if (SYSTEM / name).exists():
            errors.append(f"系统根出现实例层路径: {name}（实例数据属于项目根，不属于系统根）")
    for name in SYSTEM_ONLY:
        if (PROJECT / name).exists():
            errors.append(f"项目根出现系统层路径: {name}（系统代码只有一份，在系统根）")


def check_syntax(errors: list) -> None:
    for root in SYSTEM_PYTHON_ROOTS:
        for path in sorted((SYSTEM / root).rglob("*.py")):
            try:
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except SyntaxError as exc:
                errors.append(f"语法错误 {path.relative_to(SYSTEM)}: {exc.msg}")


def is_generated(path: Path) -> bool:
    relative = path.relative_to(SYSTEM)
    if "__pycache__" in relative.parts:
        return True
    return any(str(relative).startswith(skip + "/") for skip in GENERATED)


def check_no_project_identifiers(errors: list) -> None:
    slugs = project_slugs()
    if not slugs:
        errors.append("项目根没有任何项目标识，无法验证分层边界")
        return
    for layer in SYSTEM_LAYER:
        directory = SYSTEM / layer
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or is_generated(path):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for slug in slugs:
                if slug in text:
                    errors.append(f"系统层写死了项目标识 {slug!r}: {path.relative_to(SYSTEM)}")


def main() -> int:
    errors = []

    check_required(errors)
    check_root_separation(errors)

    for name in RETIRED_MODULES:
        if (SYSTEM / name).exists():
            errors.append(f"已归档模块重新出现: {name}")

    check_syntax(errors)
    check_no_project_identifiers(errors)

    if errors:
        print("FAIL project structure")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"PASS project structure: 系统根与项目根分离，"
          f"{len(project_slugs())} 个项目标识未进入系统层")
    return 0


if __name__ == "__main__":
    sys.exit(main())
