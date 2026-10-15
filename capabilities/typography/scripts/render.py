#!/usr/bin/env python3
"""把排版规格（TypeSpec）和内容渲染成 HTML；`--png` 再光栅化成图。

**零 Python 第三方依赖。** 光栅化交给本机已装的 Chrome（`--headless --screenshot`），
所以系统根「只用标准库」的规矩不用破。

为什么是 HTML/CSS 而不是自己画：
中文排版规范（行首行尾禁则、标点挤压、中西文间距）**浏览器已经实现了**，
对应 `line-break` / `text-spacing-trim` / `text-autospace`。自己写一遍
等于重造一个更差的。而且一套规则同时服务图片和文章两种载体——
分成两套实现就会各自演化，然后有一边是错的。

用法：

    # 封面：TypeSpec + 文案 → HTML + PNG
    python3 render.py --spec 规格.json --content 文案.json \\
        --out 封面.html --png 封面.png

    # 文章：TypeSpec + 成稿 → HTML
    python3 render.py --spec 规格.json --markdown 成稿.md \\
        --out 文章.html --title "文章标题"

`--content` 是一个 JSON 对象，键名对应 TypeSpec 里 `roles` 的键名，
**顺序就是显示顺序**（`{"kicker": "…", "headline": "…", "meta": "…"}`）。
"""

import argparse
import html
import json
import re
import shutil
import subprocess
import sys
from urllib.parse import urlsplit
from pathlib import Path

_SYSTEM = next((p for p in Path(__file__).resolve().parents if (p / "project.py").is_file()), None)
if _SYSTEM is None:
    raise SystemExit("这个脚本只能在 hq-geo 系统根里运行（向上找不到 project.py）")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_type_spec as VALIDATOR  # noqa: E402

TEMPLATES = _SYSTEM / "capabilities/typography/templates"

# role 名会变成 CSS 类名，所以必须能当类名用。
ROLE_NAME = re.compile(r"^[a-z][a-z0-9-]*$")

# 模板里剩下的占位符一个都不许留——漏一个就是一张看着对、其实缺一块的页面。
PLACEHOLDER = re.compile(r"\{\{[A-Z_]+\}\}")

CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome",
    "chromium",
    "chromium-browser",
)

# 成稿里出现这些语法时**明确报错，不静默降级**——
# 表格被当成普通段落排出来，看着是对的，结构已经丢了。
UNSUPPORTED = (
    (re.compile(r"^\s*\|.*\|\s*$"), "表格"),
    (re.compile(r"^\s*<[a-zA-Z/]"), "内嵌 HTML"),
)


class RenderError(Exception):
    """输入不对时抛这个。"""


# --- TypeSpec → CSS --------------------------------------------------------

def build_role_css(roles: dict) -> str:
    """把每一格文字展开成一条 CSS 规则。

    类名用 `tp-<role>`。**行为由 `kind` 决定（判据），类名只决定谁套哪条规则（映射）。**
    """
    lines = []
    for name in sorted(roles):
        if not ROLE_NAME.match(name):
            raise RenderError(
                f"role 名 {name!r} 不能当 CSS 类名用（只允许小写字母、数字、连字符，且以字母开头）"
            )
        role = roles[name]
        lines.append(
            f"  .tp-{name}{{\n"
            f"    font-size:{role['size_px']}px;\n"
            f"    line-height:{role['line_height']};\n"
            f"    letter-spacing:{role['letter_spacing_em']}em;\n"
            f"    font-weight:{role['weight']};\n"
            f"    color:{role['color']};\n"
            f"    --tp-ls:{role['letter_spacing_em']}em;\n"
            f"  }}"
        )
    return "\n".join(lines)


def build_canvas_css(values: dict) -> str:
    """把画布参数写成一段覆盖块，插在模板 `</style>` 之前。

    **为什么不把占位符直接写进模板的 `:root`：** 模板要能单独双击打开看默认样子
    （见 `cover.html` 顶部注释）。占位符写进 `:root`，模板本身就不可读了。
    所以默认值留在模板里，真值在最后覆盖一次——**后写的 `:root` 规则赢**。

    覆盖的是画布这一层：尺寸、留白、底色、字体栈、底图、压暗层。
    每个文字层级（字号、行距、字距、颜色）走 `build_role_css`，两条路分开。
    """
    return "\n".join([
        "  /* 下面这段由 render.py 生成——画布真值，覆盖上面的模板默认值。 */",
        "  :root{",
        f"    --tp-bg:{values['BG']};",
        f"    --tp-font:{values['FONT_FAMILY']};",
        f"    --tp-w:{values['CANVAS_W']}px;",
        f"    --tp-h:{values['CANVAS_H']}px;",
        f"    --tp-mt:{values['MARGIN_TOP']}px; --tp-mr:{values['MARGIN_RIGHT']}px; "
        f"--tp-mb:{values['MARGIN_BOTTOM']}px; --tp-ml:{values['MARGIN_LEFT']}px;",
        f"    --tp-bg-image:{values['BG_IMAGE']};",
        f"    --tp-scrim:{values['SCRIM']};",
        "  }",
    ])


def _fill(template: str, values: dict) -> str:
    """把值填进模板的占位符，**两个方向都查**。

    只查「模板里的占位符填没填」，会漏掉更坏的一种：模板里**根本没有**这个占位符。
    那时 `replace` 什么都不做，也不留残余——**值被静默丢掉，输出看着正常，
    其实参数一个都没进去。** 2026-10-08 实测：`render_article()` 的输出与模板逐字节相同，
    输入的成稿一个字都没进 HTML，脚本照报「HTML 已写入」。
    所以填完之后还要反查一遍：每个传进来的键都得在模板里出现过。
    """
    original = template
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", str(value))
    leftover = PLACEHOLDER.findall(template)
    if leftover:
        raise RenderError(f"模板里有占位符没填上：{sorted(set(leftover))}")
    unused = sorted(key for key in values if "{{" + key + "}}" not in original)
    if unused:
        raise RenderError(
            f"这些值在模板里没有对应的占位符，填不进去：{unused}。\n"
            "  静默丢值比漏填更坏——输出看着正常，参数一个都没进去。\n"
            "  要么在模板里补上占位符，要么别传这个值。"
        )
    return template


def _load_spec(spec_path: Path) -> dict:
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RenderError(f"读不了排版规格：{error}") from error
    errors = VALIDATOR.validate(spec)
    if errors:
        raise RenderError("排版规格没通过校验：\n  - " + "\n  - ".join(errors))
    return spec


# --- 封面 ------------------------------------------------------------------

def render_cover(spec: dict, content: dict) -> str:
    """TypeSpec + 文案 → 封面 HTML。"""
    canvas = spec["canvas"]
    roles = spec["roles"]

    unknown = [key for key in content if key not in roles]
    if unknown:
        raise RenderError(
            f"文案里有规格没定义的层级：{unknown}。"
            f"规格里只有 {sorted(roles)}——没有字号行距，排不出来"
        )
    if not content:
        raise RenderError("文案是空的——封面不写字，读者在信息流里扫不到它")

    parts = []
    for name, value in content.items():
        text = html.escape(str(value), quote=False).replace("\n", "<br>")
        # display 用 h1，其余用 p：标题在语义上就该是标题。
        tag = "h1" if roles[name]["kind"] == "display" else "p"
        parts.append(f'    <{tag} class="tp-{name}">{text}</{tag}>')

    margin = canvas["margin"]
    background_image = canvas.get("background_image")
    # 两份值，各配各的消费者。**不要合成一份**——合成之后 `_fill` 会以为
    # 画布值该由模板直接接住，而它们其实是被 `build_canvas_css` 接住的。
    canvas_values = {
        "BG": spec["background"],
        "FONT_FAMILY": spec.get("font_family")
        or '"Songti SC","STSong","Source Han Serif SC","Noto Serif CJK SC",serif',
        "CANVAS_W": canvas["width"],
        "CANVAS_H": canvas["height"],
        "MARGIN_TOP": margin["top"],
        "MARGIN_RIGHT": margin["right"],
        "MARGIN_BOTTOM": margin["bottom"],
        "MARGIN_LEFT": margin["left"],
        "BG_IMAGE": f"url('{background_image}')" if background_image else "none",
        "SCRIM": canvas.get("scrim") or "none",
    }
    values = {
        "TEXT_LAYOUT": canvas.get("text_layout") or "bottom-left",
        "ROLE_CSS": build_role_css(roles),
        "COPY_HTML": "\n".join(parts),
        "CANVAS_CSS": build_canvas_css(canvas_values),
    }
    return _fill((TEMPLATES / "cover.html").read_text(encoding="utf-8"), values)


# --- 文章 ------------------------------------------------------------------

def inline_markup(text: str) -> str:
    """行内标记：粗体、斜体、行内代码。

    先转义再插标签——反过来的话正文里的 `<` 会变成标签。
    """
    text = html.escape(text, quote=False)
    def link(match):
        label, target = match.groups()
        raw = html.unescape(target).strip()
        if urlsplit(raw).scheme.lower() not in ('', 'http', 'https') or raw.startswith('//'):
            return match.group(0)
        return f'<a href="{html.escape(raw, quote=True)}">{label}</a>'
    text = re.sub(r'\[([^\]\n]+)\]\(([^\s)]+)\)', link, text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    return text


IMAGE_LINE = re.compile(r"^!\[(.*?)\]\((.+?)\)$")


def markdown_to_html(text: str) -> str:
    """成稿 → HTML。**支持一个明确的子集，不支持的直接报错。**

    支持的：`#`/`##`/`###` 标题、段落、`-`/`*` 无序列表、`1.` 有序列表、
    `>` 引用、`![alt](src)` 整行图片、``` 围栏代码块、行内粗体/斜体/代码。

    不支持的（表格、内嵌 HTML）**报错并给行号**。静默降级会产出
    「看着是对的、结构已经丢了」的页面，那比报错难查得多。
    """
    blocks = []
    lines = text.splitlines()
    index = 0

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if not stripped:
            index += 1
            continue

        for pattern, what in UNSUPPORTED:
            if pattern.match(line):
                raise RenderError(
                    f"成稿第 {index + 1} 行是{what}，这个渲染器不支持——"
                    "它被当成普通段落排出来会看着对、结构已经丢了。"
                    "要么改用支持的写法，要么另外处理这一篇"
                )

        if stripped.startswith("```"):
            index += 1
            code = []
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code.append(lines[index])
                index += 1
            if index >= len(lines):
                raise RenderError("代码块没有收尾的 ```")
            index += 1
            blocks.append("<pre><code>" + html.escape("\n".join(code)) + "</code></pre>")
            continue

        heading = re.match(r"^(#{1,3})\s+(.*)$", stripped)
        if heading:
            level = len(heading.group(1))
            blocks.append(f"<h{level} class=\"tp-h{level}\">{inline_markup(heading.group(2))}</h{level}>")
            index += 1
            continue

        image = IMAGE_LINE.match(stripped)
        if image:
            alt, src = image.group(1), image.group(2)
            caption = f"<figcaption class=\"tp-caption\">{inline_markup(alt)}</figcaption>" if alt else ""
            blocks.append(
                f'<figure><img src="{html.escape(src, quote=True)}" alt="{html.escape(alt, quote=True)}">'
                f"{caption}</figure>"
            )
            index += 1
            continue

        if stripped.startswith(">"):
            quote = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                quote.append(lines[index].strip().lstrip(">").strip())
                index += 1
            blocks.append(
                "<blockquote class=\"tp-quote\">"
                + "".join(f"<p>{inline_markup(item)}</p>" for item in quote if item)
                + "</blockquote>"
            )
            continue

        bullet = re.match(r"^[-*]\s+(.*)$", stripped)
        ordered = re.match(r"^\d+\.\s+(.*)$", stripped)
        if bullet or ordered:
            tag = "ul" if bullet else "ol"
            pattern = re.compile(r"^[-*]\s+(.*)$" if bullet else r"^\d+\.\s+(.*)$")
            items = []
            while index < len(lines):
                match = pattern.match(lines[index].strip())
                if not match:
                    break
                items.append(f"<li>{inline_markup(match.group(1))}</li>")
                index += 1
            blocks.append(f"<{tag}>" + "".join(items) + f"</{tag}>")
            continue

        paragraph = []
        while index < len(lines) and lines[index].strip():
            candidate = lines[index].strip()
            if re.match(r"^(#{1,3}\s|[-*]\s|\d+\.\s|>)", candidate) or candidate.startswith("```"):
                break
            paragraph.append(candidate)
            index += 1
        blocks.append(f"<p>{inline_markup(' '.join(paragraph))}</p>")

    return "\n".join(blocks)


def render_article(spec: dict, body_html: str, title: str = "") -> str:
    """TypeSpec + 正文 HTML → 文章 HTML。"""
    roles = spec["roles"]
    for required in ("h1", "h2", "h3", "body", "caption"):
        if required not in roles:
            raise RenderError(
                f"文章规格缺少 role `{required}`——页面的元素按名字映射到 role"
                "（h1/h2/h3/body/caption），缺一个就有元素没有版式"
            )

    chinese = spec["chinese"]
    body = roles["body"]
    values = {
        "BG": spec["background"],
        "FONT_FAMILY": spec.get("font_family")
        or '"Songti SC","STSong","Source Han Serif SC","Noto Serif CJK SC",serif',
        "MEASURE": spec["measure_chars"],
        "INDENT": f"{chinese['paragraph_indent_em']}em",
        "PARA_GAP": f"{chinese['paragraph_spacing_em']}em",
        "ROLE_CSS": build_role_css(roles),
        "BODY_HTML": re.sub(r'<(h[123])>', lambda m: f'<{m[1]} class="tp-{m[1]}">', body_html),
        "PAGE_WIDTH": spec.get('max_width_px', 700),
    }
    page = _fill((TEMPLATES / "article-render.html").read_text(encoding="utf-8"), values)
    if title:
        page = page.replace("<title>文章排版模板</title>", f"<title>{html.escape(title)}</title>")
    return page


# --- 光栅化 ----------------------------------------------------------------

def find_chrome() -> str:
    """找本机已装的 Chrome / Chromium。找不到返回 None。"""
    for candidate in CHROME_CANDIDATES:
        if "/" in candidate:
            if Path(candidate).is_file():
                return candidate
        else:
            found = shutil.which(candidate)
            if found:
                return found
    return None


def _chrome_command(chrome, html_path, png_path, width, height, scale, no_sandbox):
    command = [
        chrome,
        "--headless",
        "--disable-gpu",
        "--hide-scrollbars",
        "--no-first-run",
        f"--force-device-scale-factor={scale}",
        f"--window-size={width},{height}",
        "--virtual-time-budget=3000",
        f"--screenshot={png_path}",
    ]
    if no_sandbox:
        command.append("--no-sandbox")
    command.append(html_path.resolve().as_uri())
    return command


def render_png(html_path: Path, png_path: Path, width: int, height: int, scale: float = 1.0) -> None:
    """把 HTML 光栅化成 PNG。

    **这是整条排版链上唯一需要本机之外的东西的一步**，而它要的不是 Python 包，
    是一个已经装好的浏览器。找不到时明确报错并说清降级路径——不静默跳过。

    **沙箱里 Chrome 起不了自己的沙箱**（2026-10-07 实测：`sandbox initialization failed:
    Operation not permitted`，退出码 133）。所以先按默认跑一次，只有在错误里看到 sandbox
    才退一步加 `--no-sandbox` 重试。渲染的是**本机自己生成的 HTML，不是外部网页**，
    这个退让是可接受的；但也不该无条件下调低隔离级别，所以放在失败之后。

    **成功与否只看「这次跑有没有出新图」，不看「目标路径上有没有图」。**
    2026-10-08 实测：目标 PNG 已存在时，Chrome 就算没出图也被判成功，旧图原地不动，
    脚本一路报「全成功」；失败重试分支也因此永远进不去（旧图在，条件为假）。
    三次改规格重跑，输出始终是「10 张全成功，失败 0 张」，图一张没变。
    所以渲染前先删目标文件——删掉之后，`is_file()` 才真的表示「这次出的」。
    """
    chrome = find_chrome()
    if chrome is None:
        raise RenderError(
            "找不到 Chrome / Chromium。排版规则和 HTML 已经生成好了，"
            "只有光栅化这一步需要它。\n"
            "  装 Chrome 后重跑；或直接用浏览器打开 HTML 手动截图。"
        )

    if png_path.exists():
        png_path.unlink()

    result = subprocess.run(
        _chrome_command(chrome, html_path, png_path, width, height, scale, False),
        capture_output=True, text=True,
    )
    detail = f"{result.stderr}\n{result.stdout}"
    if not png_path.is_file() and "sandbox" in detail.lower():
        result = subprocess.run(
            _chrome_command(chrome, html_path, png_path, width, height, scale, True),
            capture_output=True, text=True,
        )
        detail = f"{result.stderr}\n{result.stdout}"

    if not png_path.is_file():
        raise RenderError(
            f"Chrome 没出图。退出码 {result.returncode}。\n{detail.strip()[:600]}"
        )


# --- CLI -------------------------------------------------------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="把排版规格和内容渲染成 HTML；--png 再光栅化成图。"
    )
    parser.add_argument("--spec", required=True, help="排版规格 JSON（TypeSpec）")
    parser.add_argument("--out", required=True, help="输出的 HTML 路径")
    parser.add_argument("--content", help="封面文案 JSON（键名对应 roles 的键名，顺序即显示顺序）")
    parser.add_argument("--markdown", help="文章成稿 markdown 路径")
    parser.add_argument("--title", default="", help="文章标题（写进 <title>）")
    parser.add_argument("--png", help="同时光栅化成 PNG（只有 image 载体能做）")
    parser.add_argument("--scale", type=float, default=1.0, help="PNG 的像素密度倍数，默认 1")
    args = parser.parse_args(argv)

    if bool(args.content) == bool(args.markdown):
        print("要么给 --content（封面），要么给 --markdown（文章），只给一个", file=sys.stderr)
        return 2

    try:
        spec = _load_spec(Path(args.spec))

        if args.content:
            if spec["surface"] != "image":
                raise RenderError(f"surface={spec['surface']} 的规格不能渲染封面")
            content = json.loads(Path(args.content).read_text(encoding="utf-8"))
            page = render_cover(spec, content)
        else:
            if spec["surface"] != "page":
                raise RenderError(f"surface={spec['surface']} 的规格不能渲染文章")
            markdown = Path(args.markdown).read_text(encoding="utf-8")
            page = render_article(spec, markdown_to_html(markdown), args.title)

        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page, encoding="utf-8")
        print(f"HTML 已写入 {out}")

        if args.png:
            if spec["surface"] != "image":
                raise RenderError("只有 image 载体能出 PNG——页面没有固定高度")
            canvas = spec["canvas"]
            render_png(out, Path(args.png), canvas["width"], canvas["height"], args.scale)
            print(f"PNG 已写入 {args.png}")
    except (RenderError, OSError, json.JSONDecodeError) as error:
        print(f"渲染失败：{error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
