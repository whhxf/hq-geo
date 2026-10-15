#!/usr/bin/env python3
"""排版校验器：判一份排版参数。

**它判的是参数，不是 HTML。** 参数是判据的真源，HTML 是参数的可视化。
先定参数、再过校验、最后渲染——顺序反了就会变成「看着还行就发」。

阈值全部从 `rules/typography-rules.json` 读，代码里不另写数字。
代码里的数字改了没人知道，规则文件改了有契约测试盯着。

机器判不了的那几条（TY-14 西文行长）标 `checkable: human`，这里不判，
但会检查人判有没有登记——**不登记就等于没做**。

用法：
    python3 check_layout.py <layout.json>
    python3 check_layout.py <layout.json> --quiet
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RULES_PATH = HERE.parent / "rules" / "typography-rules.json"

# 契约要求的字段。缺了就直接说缺什么，不让 KeyError 冒出来让人猜。
REQUIRED = (
    "schema_version", "font_size_body_px", "line_height", "letter_spacing_em",
    "heading_sizes_px", "measure_chars", "first_line_indent_em",
    "paragraph_spacing_em", "cjk_latin_spacing_em", "line_break_level", "colors",
)

HEX_RE = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
RGB_RE = re.compile(r"^rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)")

NAMED = {
    "white": (255, 255, 255),
    "black": (0, 0, 0),
    "red": (255, 0, 0),
    "green": (0, 128, 0),
    "blue": (0, 0, 255),
    "gray": (128, 128, 128),
    "grey": (128, 128, 128),
    "silver": (192, 192, 192),
}


# ---------- 规则真源 ----------

def load_rules(path: Path | None = None) -> dict:
    return json.loads(Path(path or RULES_PATH).read_text(encoding="utf-8"))


def rules_by_id(rules: dict) -> dict:
    return {rule["id"]: rule for rule in rules["rules"]}


# ---------- 对比度（WCAG 2.1 相对亮度） ----------

def parse_color(value) -> tuple | None:
    """把 #rgb / #rrggbb / rgb() / 少量颜色名 变成 (r, g, b)。认不出返回 None。"""
    if isinstance(value, (list, tuple)) and len(value) == 3:
        return tuple(int(v) for v in value)
    if not isinstance(value, str):
        return None
    text = value.strip().lower()
    if text in NAMED:
        return NAMED[text]
    match = HEX_RE.match(text)
    if match:
        digits = match.group(1)
        if len(digits) == 3:
            digits = "".join(ch * 2 for ch in digits)
        return tuple(int(digits[i:i + 2], 16) for i in (0, 2, 4))
    match = RGB_RE.match(text)
    if match:
        return tuple(int(round(float(match.group(i)))) for i in (1, 2, 3))
    return None


def _linear(channel: int) -> float:
    ratio = channel / 255.0
    return ratio / 12.92 if ratio <= 0.03928 else ((ratio + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb: tuple) -> float:
    r, g, b = (_linear(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(foreground, background) -> float | None:
    """WCAG 对比度。任一颜色认不出就返回 None——**认不出不等于合格**。"""
    fg, bg = parse_color(foreground), parse_color(background)
    if fg is None or bg is None:
        return None
    a, b = relative_luminance(fg), relative_luminance(bg)
    high, low = max(a, b), min(a, b)
    return (high + 0.05) / (low + 0.05)


# ---------- 判据 ----------

def _violation(rule_id, rule_name, severity, message) -> dict:
    return {"rule_id": rule_id, "rule_name": rule_name, "severity": severity, "message": message}


def _range(value, spec, unit):
    """返回 (严重度, 说明) 或 None。硬边界外是 fail，目标范围外是 warn。"""
    if value is None:
        return "fail", f"没填（{unit}）"
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return "fail", f"不是数字：{value!r}"
    if "hard_min" in spec and value < spec["hard_min"]:
        return "fail", f"{value}{unit} 低于硬下限 {spec['hard_min']}{unit}"
    if "hard_max" in spec and value > spec["hard_max"]:
        return "fail", f"{value}{unit} 高于硬上限 {spec['hard_max']}{unit}"
    if "target_min" in spec and value < spec["target_min"]:
        return "warn", f"{value}{unit} 低于目标下限 {spec['target_min']}–{spec['target_max']}{unit}"
    if "target_max" in spec and value > spec["target_max"]:
        return "warn", f"{value}{unit} 高于目标上限 {spec['target_min']}–{spec['target_max']}{unit}"
    return None


def check(spec: dict, rules: dict | None = None) -> list:
    """判一份排版参数。返回违规与提示，每条形如 {rule_id, rule_name, severity, message}。

    severity 为 `fail` 的必须修；`warn` 是偏离专家目标值，可以带理由保留。
    """
    rules = rules or load_rules()
    by_id = rules_by_id(rules)
    out: list = []

    def add(rule_id, severity, message):
        rule = by_id.get(rule_id)
        out.append(_violation(rule_id, rule["name"] if rule else "结构", severity, message))

    # 结构先过一遍。缺字段时后面的判断全无意义。
    for key in REQUIRED:
        if key not in spec:
            add("TY-00", "fail", f"排版参数缺字段 {key}")
    if any(item["rule_id"] == "TY-00" for item in out):
        return out

    def sub(key, inner):
        node = spec.get(key)
        if not isinstance(node, dict) or inner not in node:
            add("TY-00", "fail", f"排版参数 {key}.{inner} 缺失或不是对象")
            return None
        return node[inner]

    # TY-01 行宽
    result = _range(spec.get("measure_chars"), by_id["TY-01"]["value"], "汉字/行")
    if result:
        add("TY-01", *result)

    # TY-02 正文行距
    body_lh = sub("line_height", "body")
    if body_lh is not None:
        result = _range(body_lh, by_id["TY-02"]["value"], "倍")
        if result:
            add("TY-02", *result)

    # TY-03 标题行距
    head_lh = sub("line_height", "heading")
    if head_lh is not None:
        result = _range(head_lh, by_id["TY-03"]["value"], "倍")
        if result:
            add("TY-03", *result)

    # TY-04 正文字距
    body_ls = sub("letter_spacing_em", "body")
    if body_ls is not None:
        result = _range(body_ls, by_id["TY-04"]["value"], "em")
        if result:
            add("TY-04", *result)

    # TY-05 标题字距
    head_ls = sub("letter_spacing_em", "heading")
    if head_ls is not None:
        result = _range(head_ls, by_id["TY-05"]["value"], "em")
        if result:
            add("TY-05", *result)

    # TY-06 首行缩进与段距互斥
    indent, spacing = spec.get("first_line_indent_em"), spec.get("paragraph_spacing_em")
    if isinstance(indent, (int, float)) and isinstance(spacing, (int, float)):
        if indent > 0 and spacing > 0:
            add("TY-06", "fail",
                f"首行缩进 {indent}em 与段距 {spacing}em 同时大于 0——二选一，"
                "两者都用会产生过多空白")

    # TY-07 字号阶梯
    sizes = spec.get("heading_sizes_px")
    if isinstance(sizes, list):
        bad = [i for i in range(1, len(sizes))
               if not (isinstance(sizes[i], (int, float))
                       and isinstance(sizes[i - 1], (int, float))
                       and sizes[i] < sizes[i - 1])]
        if bad:
            add("TY-07", "fail", f"标题字号没有逐级递减：{sizes}——不递减就没有层次")

    # TY-08 正文字号
    result = _range(spec.get("font_size_body_px"), by_id["TY-08"]["value"], "px")
    if result:
        add("TY-08", *result)

    # TY-09 / TY-10 对比度
    colors = spec.get("colors")
    if isinstance(colors, dict):
        ratio = contrast_ratio(colors.get("text"), colors.get("background"))
        if ratio is None:
            add("TY-09", "fail",
                f"对比度算不出来（text={colors.get('text')!r} background={colors.get('background')!r}）"
                "——认不出颜色不等于合格")
        elif ratio < by_id["TY-09"]["value"]["min"]:
            add("TY-09", "fail",
                f"正文对比度 {ratio:.2f}:1 低于 {by_id['TY-09']['value']['min']}:1")
        head_color = colors.get("heading") or colors.get("text")
        ratio_head = contrast_ratio(head_color, colors.get("background"))
        if ratio_head is not None and ratio_head < by_id["TY-10"]["value"]["min"]:
            add("TY-10", "fail",
                f"标题对比度 {ratio_head:.2f}:1 低于 {by_id['TY-10']['value']['min']}:1")

    # TY-11 避头尾级别
    level = spec.get("line_break_level")
    allowed = by_id["TY-11"]["value"]["allowed"]
    if level not in allowed:
        add("TY-11", "fail", f"避头尾级别 {level!r} 不在 {allowed}——不声明等于不做")

    # TY-12 中西文混排间距
    spacing = spec.get("cjk_latin_spacing_em")
    if isinstance(spacing, (int, float)) and spacing > by_id["TY-12"]["value"]["max"]:
        add("TY-12", "fail",
            f"中西文间距 {spacing}em 超过上限 {by_id['TY-12']['value']['max']}em（clreq §2.1.3）")

    # TY-13 正文区最大宽度
    if "max_width_px" in spec:
        result = _range(spec.get("max_width_px"), by_id["TY-13"]["value"], "px")
        if result:
            add("TY-13", *result)
    else:
        add("TY-13", "fail", "没填 max_width_px——宽屏铺满是最高频的排版错误")

    # 人判那一半。机器判不了 TY-14，但必须有人判过并登记。
    review = spec.get("human_review")
    if not isinstance(review, dict):
        add("TY-14", "warn", "没有人判登记（human_review）——机器判不了好不好看，不登记就等于没做")
    else:
        verdicts = review.get("verdicts") or {}
        failed = [k for k, v in verdicts.items() if v != "pass"]
        if failed:
            add("TY-14", "fail", f"人判未全过：{failed}")

    return out


def failures(items: list) -> list:
    return [item for item in items if item["severity"] == "fail"]


# ---------- 命令行 ----------

def main(argv: list) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    quiet = "--quiet" in argv[1:]
    if not args:
        print("用法：python3 check_layout.py <layout.json> [--quiet]")
        return 2
    path = Path(args[0])
    if not path.is_file():
        print(f"找不到排版参数文件：{path}")
        return 2

    spec = json.loads(path.read_text(encoding="utf-8"))
    items = check(spec)
    bad = failures(items)

    if not quiet:
        for item in items:
            mark = "FAIL" if item["severity"] == "fail" else "WARN"
            print(f"{mark} [{item['rule_id']} {item['rule_name']}] {item['message']}")

    if bad:
        print(f"FAIL typography: {len(bad)} 条判据没过（{path.name}）")
        return 1
    warns = len(items) - len(bad)
    tail = f"，{warns} 条提示" if warns else ""
    print(f"PASS typography: 机器判据全过（{path.name}）{tail}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
