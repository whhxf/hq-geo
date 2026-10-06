#!/usr/bin/env python3
"""在指定目录建立一个 hq-geo 项目根。

系统和项目是两个根。这个脚本只建项目根，并把它指回系统。

**已存在的文件一律不动。** 覆盖是不可逆的，而跳过是可恢复的——
跳过时明确报出来，需要覆盖就自己删掉再跑。
"""

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path


SYSTEM_ROOT = Path(__file__).resolve().parents[3]
MARKER = ".hq-geo.json"
SCHEMA_VERSION = 1

# 实例层目录。系统层的代码不在这里——它在系统根。
DIRECTORIES = [
    "tasks",
    "data/ideas",
    "data/events",
    "facts",
    "topics",
    "research/raw",
    "research/normalized",
    "research/library",
    "content/briefs",
    "content/packages",
    "content/styles",
    "assets/generated",
]

PROJECT_CLAUDE = """# {name}

这是一个 hq-geo 内容项目。**系统不在这里**，在：

    {system_root}

## 先读系统的三份

| 文件 | 讲什么 |
|---|---|
| `{system_root}/AGENTS.md` | 宪法、分层规则、事实规则 |
| `{system_root}/PLAYBOOK.md` | 怎么用这个系统 |
| `{system_root}/skills/article-pipeline/SKILL.md` | 文章流水线八站 |

## 动手前先看调研结论库

**这个项目已经调研过什么，在文件末尾那块「调研结论库」里**——它是每次会话自动加载的，
不用去翻目录。库里按「覆盖的词」列找，**不要按主题名猜**：主题名和词的对应不是一对一的。

**已经调研过的主题不要重跑一遍。** 一次 SERP 研究是 每个词 × 每个平台 各采一次——
重跑就是重付一次。

## 这个目录里有什么

**实例层**——只有这个项目的事实、选题和产物：

- `tasks/` 任务单据，一次生产请求一个文件，是这里的入口
- `facts/` 事实包，创作上下文的唯一事实真源
- `topics/` 选题假设与测试状态
- `content/` 制作简报、渠道发布包、风格示例
- `data/` 创意对象与状态事件
- `research/raw/` 平台原始采集，只追加不覆盖；`research/normalized/` 清洗与聚类结果，一轮一份
- `research/library/` 长期累积的调研结论，一个主题一个文件，带着数字、口径和出处
- `assets/generated/` 外部制作系统回传的成品

## 三条边界

- **不在这里改系统。** 系统层（`capabilities/`、`skills/`、`test/`）在系统根。要改去那边改，跑那边的门禁。
- **不在这里放系统代码。** 这里的脚本只能是这个项目的一次性工具；能复用的必须回系统根——否则第二个项目无法复用。
- **系统层不得知道这个项目的名字。** 反向引用会让这套方法锁死在这一个项目上。

## 跑门禁

```bash
python3 {system_root}/test/run_quality_gate.py --project .
```
"""

LEARNING = """# 学习记录

每次生产交付后追加一条。格式：

### <日期> · <task-id>

- **这次**：发生了什么
- **下次**：怎么做
- **去向**：BACKLOG / 策略库 / 只是记着

**「去向」是动作，不是分类。** 写 `BACKLOG` 就真的去系统根的 `BACKLOG.md` 加一条，
写策略库就真的去改对应条目。只记不做，这条记录白写。

完整约定（记什么、什么时候写、什么时候该动手）见系统根：
`{system_root}/capabilities/content-production/learning-loop.md`

**为什么记这个项目自己的，不记系统里：** 学的是「这个项目的内容怎么做」，
不是「系统怎么改」。两个项目混在一个学习库里，三次重复的规律会被稀释成六次。

（还没有记录。第一次生产交付后，这里会有第一条。）
"""

STYLES = """# 风格示例

这里是**产物目录**，不是约定目录。约定在系统根的
`{system_root}/capabilities/content-production/styles/README.md`。

文章流水线站 4 会往这里写 `<task-id>.html`，一个任务一份，里面是 3 个风格候选，
用当前任务的真实素材渲染。你用浏览器打开，看哪个顺眼就选哪个。

## 为什么是 HTML 不是文字描述

「简洁有力」这四个字，你说出来和我理解到的，多半不是一回事。但把同一段内容
用三种节奏排出来放在一起，你一眼就知道要哪个。

文字描述风格是低带宽的，示例是高带宽的。

## 边界

- 这些文件**只给你看**，不进入任何对外产物。
- 候选之间不标注哪个是「推荐」——推荐会污染判断。
- 任务交付后文件保留，下次同类任务可以翻出来比对。
- 从外部样本吸收来的风格存进风格库，不存这里。
"""


def write_new(path: Path, content: str, created: list, skipped: list) -> None:
    """只在文件不存在时写入。已存在就记下来，不动它。"""
    if path.exists():
        skipped.append(path)
        return
    path.write_text(content, encoding="utf-8")
    created.append(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="建立一个 hq-geo 项目根")
    parser.add_argument("target", help="项目目录，不存在会自动创建")
    parser.add_argument("--slug", help="项目标识，默认取目录名")
    parser.add_argument("--name", help="项目显示名，默认同 slug")
    parser.add_argument("--no-git", action="store_true", help="不执行 git init")
    args = parser.parse_args()

    root = Path(args.target).expanduser().resolve()
    slug = args.slug or root.name
    name = args.name or slug

    if root == SYSTEM_ROOT:
        print("FAIL 系统根不能同时是项目根——这正是这次分离要去掉的东西")
        return 1

    if (root / MARKER).is_file():
        print(f"FAIL 这里已经是项目根了：{root}")
        print(f"     要重建先删掉 {MARKER}")
        return 1

    root.mkdir(parents=True, exist_ok=True)
    created: list = []
    skipped: list = []

    for relative in DIRECTORIES:
        directory = root / relative
        directory.mkdir(parents=True, exist_ok=True)
        keep = directory / ".gitkeep"
        if not keep.exists() and not any(directory.iterdir()):
            keep.touch()

    descriptor = {
        "schema_version": SCHEMA_VERSION,
        "slug": slug,
        "name": name,
        "system_root": str(SYSTEM_ROOT),
        "created": dt.date.today().isoformat(),
    }
    write_new(root / MARKER, json.dumps(descriptor, ensure_ascii=False, indent=2) + "\n", created, skipped)
    write_new(root / "CLAUDE.md", PROJECT_CLAUDE.format(name=name, system_root=SYSTEM_ROOT), created, skipped)
    write_new(root / "LEARNING.md", LEARNING.format(system_root=SYSTEM_ROOT), created, skipped)
    write_new(root / "content/styles/README.md", STYLES.format(system_root=SYSTEM_ROOT), created, skipped)

    # 调研结论库的索引：往 CLAUDE.md 里插一块（会话启动即加载），并生成 library/README.md。
    # 由生成器写、不由这里写死的文本——两处保持一致的办法是只有一处来源。
    subprocess.run(
        [
            sys.executable,
            str(SYSTEM_ROOT / "capabilities/keyword-research/scripts/library_index.py"),
            "--project",
            str(root),
        ],
        check=False,
    )

    if not args.no_git and not (root / ".git").is_dir():
        subprocess.run(["git", "init", "-q"], cwd=root, check=False)

    print(f"项目根：{root}")
    print(f"系统根：{SYSTEM_ROOT}")
    print()
    for path in created:
        print(f"  新建  {path.relative_to(root)}")
    if skipped:
        print()
        for path in skipped:
            print(f"  跳过  {path.relative_to(root)}（已存在，没动）")
    print()
    print("下一步：")
    print(f"  1. 读 {SYSTEM_ROOT}/PLAYBOOK.md，从「入口 1 · 发布任务」开始")
    print(f"  2. 跑门禁：python3 {SYSTEM_ROOT}/test/run_quality_gate.py --project {root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
