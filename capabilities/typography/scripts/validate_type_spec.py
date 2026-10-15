#!/usr/bin/env python3
"""校验排版规格（TypeSpec）。

规格住在项目根，这个脚本住在系统根——路径等到真要读目录时再解析。

**这个校验器守的是一件具体的事：排出来的东西能不能读。**

之前这件事系统里完全没有。2026-10-07 查清：文章成稿是 `.md`，没有任何版式规范；
图片线的封面文字是临时排的，做法只活在对话里。两个问题的根是同一个——
**没有一份「排版规格」**。所以每次排版都靠现场发挥，不可复现、不可验收、不可积累。

现在排版是一组数字，这里判这组数字自不自洽。判据的数值和来源见
`capabilities/typography/README.md`：官方规范（WCAG 2.1、W3C 中文排版需求）
与经验模式（行距 1.5–1.8、字距 0.05–0.15em、行宽 25–35 汉字）**分开标注**，
经验模式只作校验区间的起点。

**它判不了「好不好看」。** 排得好看不好看、字体选得对不对、文字压没压住主体，
都归人。这里只判那些机器能判否的。
"""

import json
import sys
from pathlib import Path

_SYSTEM = next((p for p in Path(__file__).resolve().parents if (p / "project.py").is_file()), None)
if _SYSTEM is None:
    raise SystemExit("这个脚本只能在 hq-geo 系统根里运行（向上找不到 project.py）")
sys.path.insert(0, str(_SYSTEM))

# 颜色换算只有一个真源，在图片线。对比度和色差用的是同一套 sRGB 线性化，
# 在这里再抄一份，两边就会各自演化——然后有一边是错的。
sys.path.insert(0, str(_SYSTEM / "capabilities/image-production/scripts"))
from color_math import hex_to_rgb, srgb_channel_to_linear  # noqa: E402

from project import find_project  # noqa: E402

REQUIRED = {"schema_version", "id", "surface", "background", "roles", "chinese"}

BODY_KINDS = {"body", "caption"}
HEADING_KINDS = {"display", "heading"}
KINDS = BODY_KINDS | HEADING_KINDS

# --- 判据数值 --------------------------------------------------------------
# 经验模式给的是区间，不是规范。要改只有这一处。

# WCAG 2.1 · 1.4.12 Text Spacing 给了阅读文字的行高下限 1.5。
BODY_LINE_HEIGHT = (1.5, 2.0)
# 字号越大行距比例越小；上限 1.4 是「标题散成两段」的界线（经验模式）。
HEADING_LINE_HEIGHT = (1.0, 1.4)

# 中文大标题要拉开才舒展；正文拉大了会一个字一个字往外蹦（经验模式）。
HEADING_LETTER_SPACING_MIN = 0.05
BODY_LETTER_SPACING_MAX = 0.05

# 相邻标题层级差异要看得出来（专业共识）。
HEADING_SIZE_RATIO_MIN = 1.2

# 中文最佳行宽 25–35 汉字；放行到 20–45 是给短句和长句留余地（经验模式）。
MEASURE_CHARS_RANGE = (20, 45)

# 文字贴边，一裁切就没了（防裁切，不是审美）。
CANVAS_MARGIN_MIN_RATIO = 0.04

# --- WCAG 2.1 · 1.4.3 Contrast (Minimum) -----------------------------------

CONTRAST_BODY = 4.5
CONTRAST_LARGE = 3.0
# WCAG 对 large text 的定义：18pt，或 14pt 且粗体。96dpi 下 1pt = 4/3 px。
LARGE_TEXT_PX = 24.0
LARGE_TEXT_BOLD_PX = 18.66
BOLD_WEIGHT = 700

CHINESE_LINE_BREAK = {"strict", "normal"}

# 与 ImageBrief.cover_text.layout 同一套取值——同一个决定不要在两个契约里各写一套。
TEXT_LAYOUTS = {"top-left", "top-center", "bottom-left", "bottom-center", "center"}


def relative_luminance(color: str) -> float:
    """WCAG 2.1 的相对亮度。必须先做 sRGB 线性化。"""
    r, g, b = (srgb_channel_to_linear(channel / 255) for channel in hex_to_rgb(color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(foreground: str, background: str) -> float:
    """WCAG 2.1 的对比度：(亮 + 0.05) / (暗 + 0.05)。"""
    first = relative_luminance(foreground)
    second = relative_luminance(background)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


def is_large_text(role: dict) -> bool:
    """WCAG 对 large text 的定义。

    **用规范的定义，不用 `kind`。** kind 是我们自己的分组（管行距和字距），
    对比度门槛归 WCAG——一个 20px 的标题不算大字，仍然要 4.5:1。
    """
    size = role.get("size_px") or 0
    weight = role.get("weight") or 400
    if size >= LARGE_TEXT_PX:
        return True
    return weight >= BOLD_WEIGHT and size >= LARGE_TEXT_BOLD_PX


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _check_roles(data: dict) -> list:
    """每一格文字：行距、字距、对比度。"""
    errors = []
    roles = data.get("roles")
    if not isinstance(roles, dict) or not roles:
        return ["roles 必须是至少有一个层级的对象"]

    background = data.get("background")
    sizes = {}

    for name in sorted(roles):
        role = roles[name]
        if not isinstance(role, dict):
            errors.append(f"roles.{name} 必须是对象")
            continue

        kind = role.get("kind")
        if kind not in KINDS:
            errors.append(
                f"roles.{name}: kind 必须是 {' / '.join(sorted(KINDS))} 之一，现在是 {kind!r}"
                "——行距和字距的判据按它分组，不认识就判不了"
            )
            continue

        for key in ("size_px", "line_height", "letter_spacing_em"):
            if not _number(role.get(key)):
                errors.append(f"roles.{name}: {key} 必须是数字，现在是 {role.get(key)!r}")
        if not isinstance(role.get("weight"), int) or isinstance(role.get("weight"), bool):
            errors.append(f"roles.{name}: weight 必须是整数（100 的倍数）")

        size = role.get("size_px")
        if _number(size):
            sizes[name] = size

        line_height = role.get("line_height")
        if _number(line_height):
            low, high = HEADING_LINE_HEIGHT if kind in HEADING_KINDS else BODY_LINE_HEIGHT
            if not low <= line_height <= high:
                why = (
                    "中文是方块字，行距不足换行会串行（WCAG 2.1 · 1.4.12 给的下限是 1.5）"
                    if kind in BODY_KINDS
                    else "字号越大行距比例越小，再大标题就散成两段"
                )
                errors.append(
                    f"roles.{name}: {kind} 的行距 {line_height} 不在 {low}–{high} 之间——{why}"
                )

        spacing = role.get("letter_spacing_em")
        if _number(spacing):
            if kind in HEADING_KINDS and spacing < HEADING_LETTER_SPACING_MIN:
                errors.append(
                    f"roles.{name}: {kind} 的字距 {spacing}em 小于 {HEADING_LETTER_SPACING_MIN}em"
                    "——中文大标题要拉开才舒展，挤在一起没有呼吸"
                )
            if kind in BODY_KINDS and spacing > BODY_LETTER_SPACING_MAX:
                errors.append(
                    f"roles.{name}: {kind} 的字距 {spacing}em 大于 {BODY_LETTER_SPACING_MAX}em"
                    "——中文正文拉大字距会一个字一个字往外蹦"
                )

        color = role.get("color")
        if isinstance(color, str) and isinstance(background, str):
            try:
                ratio = contrast_ratio(color, background)
            except ValueError as error:
                errors.append(f"roles.{name}: 颜色读不出来（{error}）")
            else:
                required = CONTRAST_LARGE if is_large_text(role) else CONTRAST_BODY
                if ratio < required:
                    label = "大字" if required == CONTRAST_LARGE else "阅读文字"
                    errors.append(
                        f"roles.{name}: {color} 压在 {background} 上对比度只有 {ratio:.2f}:1，"
                        f"低于 WCAG 2.1 AA 对{label}的 {required}:1"
                    )
        elif not isinstance(color, str):
            errors.append(f"roles.{name}: color 必须是 hex 字符串")

    # 相邻标题层级必须分得开——两级标题一样大，读者分不出结构。
    headings = sorted(
        ((name, sizes[name]) for name in sizes if roles[name].get("kind") in HEADING_KINDS),
        key=lambda item: (-item[1], item[0]),
    )
    for (upper_name, upper), (lower_name, lower) in zip(headings, headings[1:]):
        if lower <= 0:
            continue
        ratio = upper / lower
        if ratio < HEADING_SIZE_RATIO_MIN:
            errors.append(
                f"标题层级 {upper_name}({upper}) 与 {lower_name}({lower}) 只差 {ratio:.2f} 倍，"
                f"小于 {HEADING_SIZE_RATIO_MIN}——两级标题看起来一样大，读者分不出结构"
            )

    # 图注/注释必须比正文小，否则层级糊掉。
    captions = [size for name, size in sizes.items() if roles[name].get("kind") == "caption"]
    bodies = [size for name, size in sizes.items() if roles[name].get("kind") == "body"]
    if captions and bodies and min(captions) >= max(bodies):
        errors.append(
            f"注释字号 {min(captions)} 不小于正文字号 {max(bodies)}"
            "——图注和正文一样大，层级就糊了"
        )

    return errors


def _check_chinese(data: dict) -> list:
    """中文排版规范。"""
    errors = []
    chinese = data.get("chinese")
    if not isinstance(chinese, dict):
        return ["chinese 必须是对象（中文排版规范不能省）"]

    line_break = chinese.get("line_break")
    if line_break not in CHINESE_LINE_BREAK:
        errors.append(
            f"chinese.line_break 必须是 strict 或 normal，现在是 {line_break!r}"
            "——取到 anywhere 之类，中文的避头尾整个失效，标点会跑到行首行尾"
        )

    indent = chinese.get("paragraph_indent_em")
    spacing = chinese.get("paragraph_spacing_em")
    for key, value in (("paragraph_indent_em", indent), ("paragraph_spacing_em", spacing)):
        if not _number(value) or value < 0:
            errors.append(f"chinese.{key} 必须是非负数字，现在是 {value!r}")

    if _number(indent) and _number(spacing) and indent > 0 and spacing > 0:
        errors.append(
            f"chinese: 首行缩进 {indent}em 与段间距 {spacing}em 同时大于 0"
            "——两者选一个。都上会让段落之间空一大块，版面松散"
        )

    return errors


def _check_surface(data: dict) -> list:
    """载体决定的必填项。"""
    errors = []
    surface = data.get("surface")
    if surface not in {"image", "page"}:
        return [f"surface 必须是 image 或 page，现在是 {surface!r}"]

    if surface == "image":
        canvas = data.get("canvas")
        if not isinstance(canvas, dict):
            errors.append("surface=image 时必须有 canvas（尺寸 + 四边留白）")
            return errors

        width, height = canvas.get("width"), canvas.get("height")
        for key, value in (("width", width), ("height", height)):
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                errors.append(f"canvas.{key} 必须是正整数，现在是 {value!r}")
        if not isinstance(width, int) or not isinstance(height, int) or width < 1 or height < 1:
            return errors

        margin = canvas.get("margin")
        if not isinstance(margin, dict):
            errors.append("canvas.margin 必须有 top / right / bottom / left")
            return errors

        floor = min(width, height) * CANVAS_MARGIN_MIN_RATIO
        for side in ("top", "right", "bottom", "left"):
            value = margin.get(side)
            if not _number(value):
                errors.append(f"canvas.margin.{side} 必须是数字，现在是 {value!r}")
            elif value < floor:
                errors.append(
                    f"canvas.margin.{side} 是 {value}px，小于短边的 "
                    f"{CANVAS_MARGIN_MIN_RATIO:.0%}（{floor:.1f}px）"
                    "——文字贴边，一裁切就没了"
                )

        layout = canvas.get("text_layout")
        if layout is not None and layout not in TEXT_LAYOUTS:
            errors.append(
                f"canvas.text_layout 必须是 {' / '.join(sorted(TEXT_LAYOUTS))} 之一，"
                f"现在是 {layout!r}——它和 ImageBrief.cover_text.layout 是同一个决定"
            )

    else:
        measure = data.get("measure_chars")
        if not isinstance(measure, int) or isinstance(measure, bool):
            errors.append("surface=page 时必须有 measure_chars（每行汉字数）")
        else:
            low, high = MEASURE_CHARS_RANGE
            if not low <= measure <= high:
                errors.append(
                    f"measure_chars 是 {measure}，不在 {low}–{high} 之间"
                    "——超过 40 字换行找不着头，少于 15 字阅读节奏被切碎"
                )

    return errors


def validate(data: dict) -> list:
    """校验一份排版规格。返回错误列表，空列表就是通过。"""
    errors = [f"missing {key}" for key in sorted(REQUIRED - data.keys())]
    if errors:
        return errors

    if data.get("schema_version") != 1:
        errors.append(f"schema_version 必须是 1，现在是 {data.get('schema_version')!r}")

    background = data.get("background")
    if not isinstance(background, str):
        errors.append("background 必须是 hex 字符串")
    else:
        try:
            hex_to_rgb(background)
        except ValueError as error:
            errors.append(f"background 读不出来（{error}）")

    errors.extend(_check_surface(data))
    errors.extend(_check_roles(data))
    errors.extend(_check_chinese(data))
    return errors


def validate_file(path: Path) -> list:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"读不了：{error}"]
    if not isinstance(data, dict):
        return ["排版规格必须是 JSON 对象"]
    return validate(data)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if argv:
        paths = [Path(item) for item in argv]
    else:
        project = find_project()
        paths = sorted((project / "content" / "typespecs").glob("**/type-spec.json"))
        if not paths:
            # 新项目一份规格都没有是正常的，不是错误。这个校验器的职责是
            # 「存在的规格都要合法」——空集合上没有反例。
            print(f"PASS type spec contract: {project.name} 还没有排版规格")
            return 0

    results = {str(path): validate_file(path) for path in paths}
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 1 if any(results.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
