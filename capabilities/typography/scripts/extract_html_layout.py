#!/usr/bin/env python3
"""从 HTML 量出排版参数。

**它量的不是「作者说排成什么样」，是「CSS 实际写成什么样」。**
站 4 的候选 HTML 渲染前先过一遍这个：作者声明的参数和 CSS 量出来的参数对不上，
说明声明在撒谎，或者 CSS 抄错了。

量不出来的一律标 `null`，**不猜**。校验器把 `null` 判为「没填」而不是「合格」。

用法：
    python3 extract_html_layout.py <article.html>
    python3 extract_html_layout.py <article.html> --compare <layout.json>
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_layout import check, load_rules  # noqa: E402

STYLE_RE = re.compile(r"<style[^>]*>(.*?)</style>", re.S | re.I)
COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)
RULE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}")
DECL_RE = re.compile(r"([-\w]+)\s*:\s*([^;]+)")
NUM_RE = re.compile(r"^(-?[\d.]+)\s*([a-z%]*)$")
COLOR_TOKEN_RE = re.compile(r"(#[0-9a-fA-F]{3,6}|rgba?\([^)]*\)|[a-z]+)")

ROOT_PX = 16.0
HEADINGS = ("h1", "h2", "h3", "h4", "h5", "h6")
# max-width 优先看这几个选择器，都没找到才退而求其次看全部。
CONTAINER_HINTS = ("body", "main", "article", ".container", ".content", ".wrap", ".post")

# CSS 的 line-break 取值 → clreq 四级。**这是一张近似映射表**，
# 校验器只要求「级别显式声明且合法」，不要求 CSS 与 clreq 逐条对齐。
LINE_BREAK_MAP = {"strict": "strict", "normal": "gb", "loose": "basic"}


def _number(value):
    match = NUM_RE.match(str(value).strip().lower())
    if not match:
        return None
    return float(match.group(1)), match.group(2)


def to_px(value, base):
    parsed = _number(value)
    if not parsed:
        return None
    number, unit = parsed
    if unit in ("", "px"):
        return number
    if unit == "em":
        return number * base
    if unit == "rem":
        return number * ROOT_PX
    if unit == "%":
        return number / 100.0 * base
    return None


def to_em(value, base):
    parsed = _number(value)
    if not parsed:
        return None
    number, unit = parsed
    if unit == "em":
        return number
    if unit == "rem":
        return number * ROOT_PX / base
    if unit == "px":
        return number / base
    if unit == "":
        return number if number == 0 else None  # 裸数字只认 0，别的含义不明
    return None


def to_ratio(value, base):
    parsed = _number(value)
    if not parsed:
        return None
    number, unit = parsed
    if unit == "":
        return number
    if unit == "em":
        return number
    if unit == "%":
        return number / 100.0
    if unit == "px":
        return number / base
    return None


def _first_color(value):
    if not value:
        return None
    match = COLOR_TOKEN_RE.search(str(value).lower())
    return match.group(1) if match else None


def _box_bottom(value):
    """从 margin / padding 简写里取「下」那个值。1 值全向，2 值上下/左右，3 值上/左右/下，4 值上右下左。"""
    parts = str(value).split()
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return parts[0]
    return parts[2]


def parse_styles(html: str) -> dict:
    """把 <style> 里的简单选择器收成 {选择器: {属性: 值}}。后面的规则覆盖前面的。

    **先剥掉 CSS 注释**——注释里的中文说明会被并进选择器，
    表现是 `body` 的声明整段读不到，而脚本不报错，只是量出 null。
    """
    table: dict = {}
    for block in STYLE_RE.findall(html):
        for selectors, body in RULE_RE.findall(COMMENT_RE.sub("", block)):
            decls = {prop.strip().lower(): val.strip()
                     for prop, val in DECL_RE.findall(body)}
            if not decls:
                continue
            for selector in selectors.split(","):
                selector = selector.strip()
                if selector:
                    table.setdefault(selector, {}).update(decls)
    return table


def parse_inline(html: str) -> dict:
    """行内 style，按标签名收，取第一次出现。"""
    table: dict = {}
    for tag, attrs in re.findall(r"<(\w+)\b([^>]*)>", html, re.I):
        tag = tag.lower()
        match = re.search(r'style\s*=\s*"([^"]*)"', attrs, re.I)
        if match and tag not in table:
            table[tag] = {prop.strip().lower(): val.strip()
                          for prop, val in DECL_RE.findall(match.group(1))}
    return table


def tag_classes(html: str) -> dict:
    table: dict = {}
    for tag, attrs in re.findall(r"<(\w+)\b([^>]*)>", html, re.I):
        tag = tag.lower()
        match = re.search(r'class\s*=\s*"([^"]*)"', attrs, re.I)
        if match:
            table.setdefault(tag, set()).update(match.group(1).split())
    return table


def _decls_for(tag, styles, inline, classes):
    merged: dict = {}
    merged.update(styles.get("*", {}))
    merged.update(styles.get(tag, {}))
    for cls in classes.get(tag, ()):
        merged.update(styles.get("." + cls, {}))
    merged.update(inline.get(tag, {}))
    return merged


def extract(html: str) -> dict:
    """量出排版参数。量不出的填 None。"""
    styles, inline, classes = parse_styles(html), parse_inline(html), tag_classes(html)

    body = _decls_for("body", styles, inline, classes)
    para = _decls_for("p", styles, inline, classes)
    base_px = to_px(body.get("font-size"), ROOT_PX) or ROOT_PX
    body_px = to_px(para.get("font-size"), base_px) or base_px

    heading_decls = {}
    heading_sizes = []
    for tag in HEADINGS:
        decls = _decls_for(tag, styles, inline, classes)
        if "font-size" in decls:
            size = to_px(decls["font-size"], body_px)
            if size is not None:
                heading_sizes.append(size)
                heading_decls.setdefault("first", decls)

    # max-width：先看容器类选择器，再退到全部。
    max_width = None
    for selector, decls in styles.items():
        if "max-width" in decls and selector in CONTAINER_HINTS:
            max_width = to_px(decls["max-width"], body_px)
            if max_width is not None:
                break
    if max_width is None:
        for selector, decls in styles.items():
            if "max-width" in decls:
                max_width = to_px(decls["max-width"], body_px)
                if max_width is not None:
                    break

    head = heading_decls.get("first", {})
    level = None
    for candidate in (body.get("line-break"), para.get("line-break")):
        if candidate:
            level = LINE_BREAK_MAP.get(candidate.strip().lower(), "none")
            break

    text_color = _first_color(para.get("color") or body.get("color"))
    background = _first_color(
        body.get("background-color") or body.get("background")
        or _first_color(styles.get("html", {}).get("background-color"))
    )
    heading_color = _first_color(head.get("color"))

    # 行宽量的是**正文列**，不是容器。p 上有 max-width 就用它，
    # 否则退到容器宽度——容器宽度含内边距，量出来的行宽会偏大。
    para_width = to_px(para.get("max-width"), body_px)
    measure = None
    if para_width:
        measure = round(para_width / body_px, 2)
    elif max_width is not None and body_px:
        measure = round(max_width / body_px, 2)

    indent = to_em(para.get("text-indent", "0"), body_px)
    spacing = to_em(para.get("margin-bottom"), body_px)
    if spacing is None and para.get("margin") is not None:
        spacing = to_em(_box_bottom(para["margin"]), body_px)

    colors = {"text": text_color, "background": background}
    if heading_color:
        colors["heading"] = heading_color

    return {
        "schema_version": "article-layout/v1",
        "font_size_body_px": body_px,
        "line_height": {
            "body": to_ratio(para.get("line-height") or body.get("line-height"), body_px),
            "heading": to_ratio(head.get("line-height"), body_px),
        },
        "letter_spacing_em": {
            "body": to_em(para.get("letter-spacing") or body.get("letter-spacing") or "0",
                         body_px),
            "heading": to_em(head.get("letter-spacing", "0"), body_px),
        },
        "heading_sizes_px": heading_sizes,
        "measure_chars": measure,
        "max_width_px": max_width,
        "first_line_indent_em": indent if indent is not None else 0.0,
        "paragraph_spacing_em": spacing if spacing is not None else 0.0,
        "cjk_latin_spacing_em": to_em(
            body.get("--hq-cjk-latin-spacing", "0"), body_px) or 0.0,
        "line_break_level": level or "none",
        "colors": colors,
    }


def compare(measured: dict, declared: dict) -> list:
    """量出来的和声明的逐格比。差异按字段列出，忽略 None（量不出来不算差异）。"""
    diffs = []
    for key, value in declared.items():
        if key in ("schema_version", "human_review"):
            continue
        got = measured.get(key)
        if isinstance(value, dict) and isinstance(got, dict):
            for inner, want in value.items():
                if got.get(inner) != want:
                    diffs.append(f"{key}.{inner}: 声明 {want!r}，量出 {got.get(inner)!r}")
        elif got is not None and got != value:
            diffs.append(f"{key}: 声明 {value!r}，量出 {got!r}")
    return diffs


def main(argv: list) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    if not args:
        print("用法：python3 extract_html_layout.py <article.html> [--compare <layout.json>]")
        return 2
    path = Path(args[0])
    if not path.is_file():
        print(f"找不到 HTML：{path}")
        return 2

    measured = extract(path.read_text(encoding="utf-8"))
    print(json.dumps(measured, ensure_ascii=False, indent=2))

    if "--compare" in argv:
        index = argv.index("--compare")
        if index + 1 >= len(argv):
            print("--compare 后面要跟一个 layout.json 路径")
            return 2
        declared = json.loads(Path(argv[index + 1]).read_text(encoding="utf-8"))
        diffs = compare(measured, declared)
        if diffs:
            print("\nFAIL 声明与 CSS 对不上：")
            for line in diffs:
                print(f"- {line}")
            return 1
        print("\nPASS 声明与 CSS 一致")

    bad = [item for item in check(measured, load_rules()) if item["severity"] == "fail"]
    if bad:
        print("\n量出来的参数没过机器判据：")
        for item in bad:
            print(f"- [{item['rule_id']} {item['rule_name']}] {item['message']}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
