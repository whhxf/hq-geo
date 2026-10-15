#!/usr/bin/env python3
"""系统根自检：分层、语法与必需路径。

取代已归档的 `lib/smoke_check.py`。旧检查验证的是 CSV 表头和 01-08 编号脚本，
本项目已不再使用。这里验证系统根自己要守的四件事：

1. 系统根有方法、契约、门禁；
2. **系统根里不出现实例层目录**——实例数据长回系统根，第二个项目就又要
   跟第一个项目的数据挤在一起，分根就白分了；
3. **系统层文件里不出现项目标识**——写死了名字，第二个项目无法复用
   同一套方法（宪法第 3 条）；
4. 脚手架建出的目录，与 `PROJECT_REQUIRED` 清单一致。

**这个文件只测系统根。** 项目根那半（必需路径、不许出现系统层目录）在
2026-10-10 移出门禁：门禁不再依赖任何项目根，那是「系统只测自身」的要求。

第 2 条是分根新加的不变量，也是唯一一条不依赖「知道项目叫什么」就能
成立的边界检查：哪怕系统里写死了某个我们没在测的项目名，它也能挡住
「把实例数据搬回系统」这一类退化。
"""

import ast
import json
import os
import sys
from pathlib import Path


SYSTEM = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SYSTEM))
from project import MARKER  # noqa: E402

REPORT_ROOT = SYSTEM / "test/reports"

# 系统根必须有的：方法、契约、校验器、门禁。
SYSTEM_REQUIRED = [
    "AGENTS.md",
    "PLAYBOOK.md",
    "project.py",
    "capabilities/geo/manifest.json",
    "capabilities/content-production/contracts/production-brief.schema.json",
    "capabilities/content-production/tasks/README.md",
    "capabilities/fact-packs/scripts/validate_fact_pack.py",
    "capabilities/fact-packs/schemas/README.md",
    "capabilities/project-scaffold/scripts/init_project.py",
    "capabilities/sourcing/interview-method.md",
    "skills/content-orchestrator/SKILL.md",
    "skills/sourcing/SKILL.md",
    "test/run_quality_gate.py",
]

# 项目根应该有的目录。**这里不再检查项目根**，只用来核对脚手架建不建得出来。
PROJECT_REQUIRED = [
    MARKER,
    "LEARNING.md",
    "tasks",
    "data/events",
    "data/ideas",
    "facts",
    "research/raw",
    "research/normalized",
    "research/library",
    "content/briefs",
    "content/packages",
    "content/styles",
    "assets/generated",
]

# 实例层的目录名。出现在系统根就是分根被破坏。
INSTANCE_ONLY = ["tasks", "facts", "topics", "content", "assets", "research", "data", "LEARNING.md"]

# 系统层：跨项目复用的方法、契约与校验器。不得出现任何具体项目标识。
# 测试也算系统层：把某个项目的路径写成 fixture，第二个项目就无从复用。
#
# 根目录文档（AGENTS.md、PLAYBOOK.md、README.md、BACKLOG.md）**不在**这个清单里，
# 是有意的：手册要告诉用户「现在到哪一步了」，那本来就该点名当前项目。
# 方法、契约、校验器里出现项目名才是问题——那些要跨项目复用。
SYSTEM_LAYER = [
    "capabilities/geo",
    "capabilities/content-production",
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
    """已知的项目标识。

    2026-10-10 起系统门禁不再依赖项目根，标识清单也不来自项目根。
    两个来源，都在系统根里：

    - `test/reports/<slug>/`：跑过门禁的项目各留一个目录，门禁自己生成的；
    - 环境变量 `HQ_GEO_PROJECT` 指的那个项目（带 `--project` 跑时才有）。

    两个来源都空时清单为空——`check_no_project_identifiers` 会明确报
    「未执行」，不静默通过。
    """
    slugs = set()
    if REPORT_ROOT.is_dir():
        slugs.update(entry.name for entry in REPORT_ROOT.iterdir()
                     if entry.is_dir() and not entry.name.startswith((".", "_")))
    raw = os.environ.get("HQ_GEO_PROJECT")
    if raw:
        descriptor = Path(raw) / MARKER
        if descriptor.is_file():
            try:
                slug = json.loads(descriptor.read_text(encoding="utf-8")).get("slug")
            except (OSError, ValueError):
                slug = None
            if slug:
                slugs.add(slug)
    return slugs


def check_required(errors: list) -> None:
    for relative in SYSTEM_REQUIRED:
        if not (SYSTEM / relative).exists():
            errors.append(f"系统根缺少必需路径: {relative}")


def check_root_separation(errors: list) -> None:
    """实例层数据不许长回系统根。这一条不需要知道任何项目名。"""
    for name in INSTANCE_ONLY:
        if (SYSTEM / name).exists():
            errors.append(f"系统根出现实例层路径: {name}（实例数据属于项目根，不属于系统根）")


# 脚手架用 write_new 写的文件，不走 DIRECTORIES 那条目录清单。
SCAFFOLD_FILES = {MARKER, "LEARNING.md"}


def check_scaffold_coverage(errors: list) -> None:
    """脚手架必须建出「项目根应该有的」每一条目录。

    这两份清单会各自漂移：往 `PROJECT_REQUIRED` 加一行而忘了加脚手架，
    **当时所有测试都是绿的**——因为已存在的项目早就手工建好了那份目录。
    症状要等到下一个新项目才出现，而那时它看起来像「新项目建错了」，
    不像「清单漏了一行」。

    这条不碰项目根：比对的是清单和脚手架源码，两边都在系统根里。
    """
    scaffold = SYSTEM / "capabilities/project-scaffold/scripts/init_project.py"
    if not scaffold.is_file():
        errors.append("找不到项目脚手架，无法核对它与 PROJECT_REQUIRED 是否一致")
        return

    # 用 AST 取那份清单，不执行脚手架——它 import subprocess、会 git init。
    created: set = set()
    for node in ast.parse(scaffold.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(
            getattr(target, "id", None) == "DIRECTORIES" for target in node.targets
        ):
            created = {ast.literal_eval(element) for element in node.value.elts}
            break
    if not created:
        errors.append("没能从脚手架里读出 DIRECTORIES——清单名字改了就在这里同步")
        return

    for relative in PROJECT_REQUIRED:
        if relative in SCAFFOLD_FILES or relative in created:
            continue
        errors.append(
            f"PROJECT_REQUIRED 要求 {relative}，但脚手架不建它——"
            "新项目一建出来就过不了门禁，而现有项目不会暴露这个问题"
        )


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


def check_no_project_identifiers(errors: list, notes: list) -> None:
    slugs = project_slugs()
    if not slugs:
        notes.append(
            "系统层项目标识扫描未执行：没有已知的项目标识。"
            "跑一次带 --project 的门禁，或在 test/reports/ 下建一个以项目 slug 命名的目录。"
        )
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
    errors: list = []
    notes: list = []

    check_required(errors)
    check_root_separation(errors)
    check_scaffold_coverage(errors)

    for name in RETIRED_MODULES:
        if (SYSTEM / name).exists():
            errors.append(f"已归档模块重新出现: {name}")

    check_syntax(errors)
    check_no_project_identifiers(errors, notes)

    if errors:
        print("FAIL project structure")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS project structure: 系统根完整，未混入实例层，"
          f"脚手架与 PROJECT_REQUIRED 一致，{len(project_slugs())} 个项目标识未进入系统层")
    for note in notes:
        print(f"NOTE {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
