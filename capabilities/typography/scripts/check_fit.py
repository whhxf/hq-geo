#!/usr/bin/env python3
"""规格 × 文案 的合身检查。

**这一条补的是排版线的漏洞。** `validate_type_spec.py` 只校验规格本身：
字号阶梯、字距范围、对比度、避头尾级别。它不知道你要写什么字。
于是「规格合法 + 文案太长 = 标题折成孤字」这条路一直没人拦。

实测（2026-10-10，视频线）：1080 宽、左右留白各 108 → 可用 864px，
108px 大标题每字约 114px → 一行最多 7 个汉字。
9 个字的「或者遇到敏感问题，」被折成「或者遇到敏感问」+「题，」，
多出来的那半行只有一个字，很难看，而且机器不报错。

判据不是审美：**它量的是「这一行放不放得下」。** 放不下就得改文案或改字号，
这是执行者的决定，不是检查器的决定。检查器只负责把这件事说出来。

用法：
    python check_fit.py --spec spec.json --content cover.json
    python check_fit.py --script script.json --spec spec.json
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path


# 字宽估算的系数。中西文混排时一个字不等于一个 em。
# 这些数字来自实测：PingFang SC 下 ASCII 小写字母约占 0.55em。
# 宁可估宽一点——估窄了会漏报，估宽了只会多提醒一次。
ASCII_NARROW = 0.30   # 空格、标点
ASCII_WIDE = 0.58     # 字母、数字
CJK = 1.0             # 汉字、全角标点

# 折行后剩下的这一行少于这么多字，读起来就是一个孤字。判为问题。
ORPHAN_CHARS = 2

GAP_EM = 0.6  # 模板里 .tp-copy 的 gap，相对根字号（16px）


def char_width(ch: str) -> float:
    if ch.isspace():
        return ASCII_NARROW
    if unicodedata.east_asian_width(ch) in ("W", "F"):
        return CJK
    if unicodedata.east_asian_width(ch) in ("A",):
        # 模糊宽度：中文环境按全角排。
        return CJK
    if ch.isascii():
        return ASCII_NARROW if not (ch.isalnum()) else ASCII_WIDE
    return CJK


def line_em(line: str) -> float:
    return sum(char_width(ch) for ch in line)


def available(spec: dict) -> tuple:
    canvas = spec["canvas"]
    margin = canvas["margin"]
    return (
        canvas["width"] - margin["left"] - margin["right"],
        canvas["height"] - margin["top"] - margin["bottom"],
    )


def check_content(spec: dict, content: dict, where: str = "") -> list:
    """返回问题列表。空列表表示放得下。"""
    roles = spec["roles"]
    width, height = available(spec)
    prefix = f"{where} " if where else ""
    problems = []

    total_height = 0.0
    for index, (name, value) in enumerate(content.items()):
        role = roles.get(name)
        if role is None:
            problems.append(
                f"{prefix}文案里有规格没定义的层级：{name}。规格里只有 {sorted(roles)}——没有字号行距，排不出来"
            )
            continue
        size = role["size_px"]
        spacing = 1 + role.get("letter_spacing_em", 0)
        lines = str(value).split("\n")
        total_height += len(lines) * size * role["line_height"]
        if index:
            total_height += GAP_EM * 16

        for line_no, line in enumerate(lines, 1):
            if not line:
                continue
            em = line_em(line)
            px = em * size * spacing
            if px > width:
                room = width / (size * spacing)
                problems.append(
                    f"{prefix}{name} 第 {line_no} 行放不下："
                    f"「{line}」约 {px:.0f}px，可用 {width}px。"
                    f"这一行最多约 {room:.1f} 个字宽——改短这一行，或调小 {name} 的字号"
                )
            elif px > width * 0.97:
                problems.append(
                    f"{prefix}{name} 第 {line_no} 行顶到边："
                    f"「{line}」约 {px:.0f}px，可用 {width}px。"
                    f"再宽一点就会折行，折出来的是孤字"
                )

    if total_height > height:
        problems.append(
            f"{prefix}整块文案放不下：约 {total_height:.0f}px，可用 {height}px。"
            f"少写一行，或调小字号，或加大画布"
        )
    return problems


def load(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="检查规格和文案合不合身")
    parser.add_argument("--spec", required=True, help="排版规格 JSON（TypeSpec）")
    parser.add_argument("--content", help="单张文案 JSON")
    parser.add_argument("--script", help="视频脚本 JSON（逐幕检查 content）")
    args = parser.parse_args(argv)

    if bool(args.content) == bool(args.script):
        print("只给 --content 或 --script 其中之一", file=sys.stderr)
        return 2

    spec = load(args.spec)
    problems = []
    if args.content:
        problems += check_content(spec, load(args.content))
    else:
        script = load(args.script)
        for scene in script.get("scenes", []):
            problems += check_content(spec, scene.get("content") or {}, f"[{scene.get('id')}]")

    if problems:
        print("合身检查不通过：")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("合身检查通过：每一行都放得下")
    return 0


if __name__ == "__main__":
    sys.exit(main())
