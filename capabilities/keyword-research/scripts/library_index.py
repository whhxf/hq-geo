#!/usr/bin/env python3
"""重建调研结论库的索引。

**要解决的问题**：库建了，但「知道该翻哪一个」依赖记忆。数据一多，记忆失效——
于是花了钱采的结论躺在那里没人用，下一轮从零开始。

**做法**：索引不进人脑，进「每次必定加载」的那一层。Claude Code 里只有两处：

| 位置 | 什么时候进上下文 |
|---|---|
| 项目根 `CLAUDE.md` | **会话启动即注入**，不用谁想起来去读 |
| `research/library/README.md` | 有人翻这个目录时 |

**关键：两处索引都是从这里生成的，不是手写的。** 手写的索引一定会漂移——
漂移之后它比没有更糟，因为它会让人以为「库里就这些」。

索引的内容来自每个库文件自己的 front matter：

    ---
    topic: AI 数字员工
    covers: [AI数字员工, AI客服, 智能体搭建]
    summary: 一句话说清这个文件里最值钱的判断
    updated: 2026-09-29
    ---

`covers` 是**覆盖的词**，不是主题名。主题名和词的对应关系不是一对一的——
`AI客服` 的结论住在 `AI数字员工.md` 里，因为它们是同一门生意。
**没有这一列，按词就搜不到。**

用法：

    python3 capabilities/keyword-research/scripts/library_index.py --project <项目根>
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

START = "<!-- library-index:start -->"
END = "<!-- library-index:end -->"

SKIP_FILES = {"README.md"}

CLAUDE_HEADING = "## 调研结论库"

CLAUDE_INTRO = (
    "**动手前先看这张表。** 开工前先看这里的第一行——"
    "已经调研过的主题不要重跑一遍。\n\n"
    "调研结论在 `research/library/`，一个主题一个文件。每条结论带**数字 / 口径 / 出处**。\n"
)


def parse_covers(raw: str) -> list[str]:
    """解析 `[a, b, c]` 形式的内联列表。不引 yaml 依赖。"""
    text = raw.strip()
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    if not text.strip():
        return []
    return [item.strip().strip("'\"") for item in text.split(",") if item.strip()]


def read_front_matter(path: Path) -> dict[str, str]:
    """读 markdown 的 front matter。只支持 `key: value`，和校验器同一套规则。"""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    out: dict[str, str] = {}
    for line in text.splitlines()[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, _, value = line.partition(":")
            out[key.strip()] = value.strip()
    return out


def collect_entries(library_dir: Path) -> list[dict]:
    """库里每个主题文件一条。按主题名排序——**顺序必须稳定，否则每次生成都不一样。**"""
    entries = []
    if not library_dir.is_dir():
        return entries
    for path in sorted(library_dir.glob("*.md")):
        if path.name in SKIP_FILES:
            continue
        front = read_front_matter(path)
        entries.append(
            {
                "topic": front.get("topic") or path.stem,
                "file": path.name,
                "covers": parse_covers(front.get("covers", "")),
                "summary": front.get("summary", ""),
                "updated": front.get("updated", ""),
            }
        )
    entries.sort(key=lambda e: e["topic"])
    return entries


def _table(entries: list[dict]) -> str:
    lines = ["| 主题 | 文件 | 覆盖的词 | 一句话 | 更新 |", "|---|---|---|---|---|"]
    if not entries:
        lines.append("| *(还没有)* | | | 第一次调研收尾后会出现第一行 | |")
        return "\n".join(lines)
    for entry in entries:
        covers = "、".join(entry["covers"]) or "**缺 covers**"
        summary = entry["summary"] or "**缺 summary**"
        lines.append(
            f"| {entry['topic']} | [{entry['file']}]({entry['file']}) | "
            f"{covers} | {summary} | {entry['updated']} |"
        )
    return "\n".join(lines)


def build_claude_block(entries: list[dict], script_path: str) -> str:
    """写进项目 CLAUDE.md 的那一段。带标记，好替换。"""
    return (
        f"{START}\n"
        f"{CLAUDE_HEADING}\n\n"
        f"{CLAUDE_INTRO}\n"
        f"{_table(entries)}\n\n"
        f"**这张表是生成的，不要手改。** 改完库文件跑：\n\n"
        f"```bash\n"
        f"python3 {script_path} --project .\n"
        f"```\n"
        f"{END}"
    )


def build_readme(entries: list[dict], script_path: str) -> str:
    return (
        "# 调研结论库\n\n"
        "**一个主题一个文件，文件名不带日期。** 每条结论必须带三样，缺一不可——\n"
        "**数字 / 口径 / 出处**（指到 `research/raw/` 的具体文件 + 采集日期）。\n"
        "约定和理由见 `capabilities/keyword-research/methods/research-library.md`。\n\n"
        "## 找不到？先搜「覆盖的词」\n\n"
        "**主题名和词的对应关系不是一对一的。** `AI客服` 的结论可能住在\n"
        "`AI数字员工.md` 里——因为它们是同一门生意，放一起才看得见彼此印证或矛盾。\n\n"
        "所以按词找，不要按主题名猜。**先在下面这张表的「覆盖的词」列里搜你的词。**\n\n"
        "## 索引\n\n"
        f"{_table(entries)}\n\n"
        f"**这张表是生成的，不要手改。** 改完库文件跑：\n\n"
        f"```bash\n"
        f"python3 {script_path} --project .\n"
        f"```\n"
    )


def replace_block(text: str, block: str) -> str | None:
    """把 CLAUDE.md 里的索引块换掉。没有标记就返回 None，由调用方决定怎么办。"""
    start = text.find(START)
    end = text.find(END)
    if start == -1 or end == -1 or end < start:
        return None
    return text[:start] + block + text[end + len(END) :]


def sync(project: Path, script_path: str) -> dict:
    library_dir = project / "research" / "library"
    entries = collect_entries(library_dir)

    claude = project / "CLAUDE.md"
    claude_status = "跳过（没有 CLAUDE.md）"
    if claude.is_file():
        text = claude.read_text(encoding="utf-8")
        block = build_claude_block(entries, script_path)
        replaced = replace_block(text, block)
        if replaced is None:
            # 标记被删了（新项目、或有人清理过）。补回去，不报错——
            # 索引块丢了本身就是这里要修的东西。
            text = text.rstrip() + "\n\n" + block + "\n"
            claude_status = "补写（原来没有标记块）"
        elif replaced == text:
            claude_status = "已是最新"
        else:
            text = replaced
            claude_status = "更新"
        claude.write_text(text, encoding="utf-8")

    readme = library_dir / "README.md"
    wanted = build_readme(entries, script_path)
    if readme.is_file() and readme.read_text(encoding="utf-8") == wanted:
        readme_status = "已是最新"
    else:
        library_dir.mkdir(parents=True, exist_ok=True)
        readme.write_text(wanted, encoding="utf-8")
        readme_status = "更新"

    # 脚手架建空目录时会放 .gitkeep；有了 README.md 它就是多余的。
    stale = library_dir / ".gitkeep"
    if stale.is_file():
        stale.unlink()

    return {
        "entries": entries,
        "claude": claude_status,
        "readme": readme_status,
        "library_dir": library_dir,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="重建调研结论库的索引")
    parser.add_argument("--project", required=True, help="项目根目录")
    args = parser.parse_args(argv)

    project = Path(args.project).expanduser().resolve()
    if not project.is_dir():
        print(f"FAIL  目录不存在：{project}")
        return 1

    script_path = str(Path(__file__).resolve())
    result = sync(project, script_path)

    print(f"调研结论库：{result['library_dir']}")
    for entry in result["entries"]:
        if not entry["covers"]:
            print(f"  ⚠ {entry['file']} 没写 covers——按词搜不到这个文件")
    print(f"  README.md    {result['readme']}")
    print(f"  CLAUDE.md    {result['claude']}")
    print(f"  {len(result['entries'])} 个主题")
    return 0


if __name__ == "__main__":
    sys.exit(main())
