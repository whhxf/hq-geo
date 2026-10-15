#!/usr/bin/env python3
"""排版能力的契约检查。

排版是「求好」那条腿的一部分。**求好的判据被删掉或改弱，Agent 不会报错**——
它会自己编一套排版做法，然后交出一份「挑不出错但没人读」的稿子。
所以这个检查盯的是**判据在不在、真源有没有来源、模板和声明还一致吗**。

三件事最重要：

1. 规则文件每条都有来源和采集日期——没有来源的数值就是审美，审美进不了判据；
2. 人判那一半必须有承载字段——机器判不了好不好看，就必须要求人判留下痕迹；
3. 金样本 HTML 和它的声明文件必须互相量得出来——两份一漂移，
   站 4 生成的稿子就会「声明一套、CSS 一套」，而门禁看不出来。
"""

import json
import sys
from pathlib import Path

SYSTEM = Path(__file__).resolve().parents[2]
CAP = "capabilities/typography"

SKILL = "skills/article-pipeline/SKILL.md"
SCHEMA = f"{CAP}/contracts/article-layout.schema.json"
RULES = f"{CAP}/rules/typography-rules.json"
TEMPLATE_HTML = f"{CAP}/templates/article.html"
TEMPLATE_LAYOUT = f"{CAP}/templates/article-layout.json"

RULE_IDS = [f"TY-{n:02d}" for n in range(1, 15)]


def read(relative: str) -> str:
    return (SYSTEM / relative).read_text(encoding="utf-8")


def load(relative: str) -> dict:
    return json.loads(read(relative))


def check_skill(errors: list) -> None:
    """站 4 的排版判据在不在。删掉一条，Agent 就会自己编做法。"""
    skill = read(SKILL)
    for needle, reason in [
        (
            "**排版不是装饰，是可核验的数值。**",
            "排版必须被写成数值判据；不写这条，Agent 会按「感觉」排",
        ),
        (
            "**参数定了才写 HTML，顺序不能反。**",
            "顺序反了就会变成「看着还行就发」；不写这条，排版没有前置门禁",
        ),
        (
            "**对不上就是有一份在撒谎**",
            "声明与 CSS 的比对是防漂移的唯一手段；不写这条，两份可以各说各话",
        ),
        (
            "**机器判不了好不好看。**",
            "人判登记的理由；不写这条，human_review 会被当成可选",
        ),
        (
            "**排版参数不过校验器，不得渲染 HTML。**",
            "边界必须是否定式；不写这条，「先渲染再补参数」会被当成可行路径",
        ),
        ("check_layout.py", "校验器入口不在 skill 里，判据就没有执行者"),
        ("extract_html_layout.py", "提取器入口不在 skill 里，防漂移就没人跑"),
        (
            "cover-type-spec.json",
            "封面金样本入口不在 skill 里，站 4 每次都要现场编一套封面参数",
        ),
        (
            "**这一站只定封面规格，不定封面文案。**",
            "顺序反了会写出一句和标题无关的封面文案——封面必须和标题同向",
        ),
        (
            "**底图不在这一站生成。**",
            "不写这条，Agent 会拿模型直接出带字的封面图，中文会糊且不可核验",
        ),
        (
            "**标题定稿后出封面。**",
            "封面渲染的触发点不在 skill 里，封面就永远不会被产出",
        ),
        (
            "**判的人不能是写封面文案的人**",
            "封面吸引力复核必须职责分离；不写这条，复核会退化成自评",
        ),
    ]:
        if needle not in skill:
            errors.append(f"文章线排版判据缺失（{reason}）: {needle}")


def check_schema(errors: list) -> None:
    """契约必填项与枚举。掉一格，简报写了也没人认，而且不会报错。"""
    schema = load(SCHEMA)
    required = set(schema.get("required", []))
    for key in (
        "font_size_body_px", "line_height", "letter_spacing_em", "heading_sizes_px",
        "measure_chars", "first_line_indent_em", "paragraph_spacing_em",
        "cjk_latin_spacing_em", "line_break_level", "colors",
    ):
        if key not in required:
            errors.append(f"ArticleLayout 必填项缺 {key}——不强制就会有人不写")

    level = schema.get("properties", {}).get("line_break_level", {}).get("enum", [])
    if set(level) != {"none", "basic", "gb", "strict"}:
        errors.append(f"line_break_level 枚举变了：{level}——clreq 是四级，校验器要跟着改")

    colors = schema.get("properties", {}).get("colors", {}).get("required", [])
    if set(colors) != {"text", "background"}:
        errors.append(f"colors 必填项变了：{colors}——对比度算不出来")

    review = schema.get("properties", {}).get("human_review")
    if not review:
        errors.append(
            "契约里没有 human_review——人判那一半没有承载字段，"
            "排版好不好看就无从查起，等于把求好这一半交回给运气"
        )
    else:
        verdicts = review.get("properties", {}).get("verdicts", {})
        expected = {"reads_comfortably", "hierarchy_is_clear", "style_matches_content"}
        if set(verdicts.get("required", [])) != expected:
            errors.append(f"human_review.verdicts 的维度变了：{verdicts.get('required')}")
        for key in sorted(expected):
            values = verdicts.get("properties", {}).get(key, {}).get("enum", [])
            if set(values) != {"pass", "fail", "unknown"}:
                errors.append(f"human_review.verdicts.{key} 的取值变了：{values}")


def check_rules(errors: list) -> None:
    """规则真源：十四条都在，每条有来源，来源有证据等级和采集日期。"""
    rules = load(RULES)
    entries = rules.get("rules", [])
    ids = [rule.get("id") for rule in entries]

    if ids != RULE_IDS:
        errors.append(f"排版规则从 {RULE_IDS} 变成了 {ids}——少一条就是少一道判据")

    sources = rules.get("sources", {})
    for key, source in sources.items():
        for field in ("title", "evidence", "collected_at"):
            if not source.get(field):
                errors.append(f"来源 {key} 缺 {field}——AGENTS.md 要求记录证据等级与采集日期")
        if source.get("evidence") not in {"官方规则", "直接证据", "强代理证据", "经验模式", "推断", "未知"}:
            errors.append(f"来源 {key} 的证据等级 {source.get('evidence')!r} 不在六档之内")

    for rule in entries:
        label = rule.get("id", "?")
        for field in ("name", "scope", "checkable", "source", "why", "value"):
            if field not in rule:
                errors.append(f"规则 {label} 缺字段 {field}")
        if rule.get("source") not in sources:
            errors.append(f"规则 {label} 引用了不存在的来源 {rule.get('source')!r}")
        if rule.get("checkable") not in {"machine", "human"}:
            errors.append(f"规则 {label} 的 checkable 取值非法：{rule.get('checkable')!r}")

    human = [rule["id"] for rule in entries if rule.get("checkable") == "human"]
    if not human:
        errors.append(
            "十四条规则里没有一条标 human——排版不可能全靠机器判；"
            "全标 machine 就是把「好不好看」谎报成机器能判"
        )


def check_scripts(errors: list) -> None:
    """判据写在规则文件里，执行的是脚本。脚本少了函数，判据就没人执行。"""
    scripts = SYSTEM / CAP / "scripts"
    for name, anchors in [
        ("check_layout.py", ["def load_rules(", "def contrast_ratio(",
                             "def check(", "def failures("]),
        ("extract_html_layout.py", ["def extract(", "def compare(", "def parse_styles(",
                                    "def to_px(", "def to_em("]),
    ]:
        path = scripts / name
        if not path.is_file():
            errors.append(f"排版脚本不见了：{name}")
            continue
        text = path.read_text(encoding="utf-8")
        for anchor in anchors:
            if anchor not in text:
                errors.append(f"{name} 少了 {anchor}——规则文件里的判据没有执行者")


def check_template_pair(errors: list) -> None:
    """金样本 HTML 和它的声明必须互相量得出来。

    两份一漂移，站 4 生成的稿子就会「声明一套、CSS 一套」，
    而 `check_layout.py` 只判声明、不判 CSS——门禁看不出来。
    """
    for relative in (TEMPLATE_HTML, TEMPLATE_LAYOUT):
        if not (SYSTEM / relative).is_file():
            errors.append(f"排版金样本不见了：{relative}")
            return

    sys.path.insert(0, str(SYSTEM / CAP / "scripts"))
    import check_layout
    import extract_html_layout

    declared = load(TEMPLATE_LAYOUT)
    measured = extract_html_layout.extract(read(TEMPLATE_HTML))

    diffs = extract_html_layout.compare(measured, declared)
    for line in diffs:
        errors.append(f"金样本声明与 CSS 对不上：{line}")

    bad = check_layout.failures(check_layout.check(declared))
    for item in bad:
        errors.append(f"金样本声明没过机器判据：[{item['rule_id']}] {item['message']}")


def main() -> int:
    errors = []
    check_skill(errors)
    check_schema(errors)
    check_rules(errors)
    check_scripts(errors)
    check_template_pair(errors)

    if errors:
        print("FAIL typography")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS typography: 站 4 判据、十四条规则真源、契约与人判承载、金样本一致性齐全")
    return 0


if __name__ == "__main__":
    sys.exit(main())
