#!/usr/bin/env python3
"""图文吸引力的契约检查。

**这条腿守的是「有人愿意看」。** 在此之前，图片线五站全是事实纪律——
每一站都在回答「这张图有没有骗人」，没有一站回答「有没有人愿意看」。
判据被删掉或改弱，Agent 不会报错：它会照旧出一组合规但没人点的图，
然后交付，然后没人看。**那比读不到更糟，因为它看起来是成功的。**

所以这个检查盯的是**判据在不在、来源有没有证据等级、人判那一半有没有承载字段**。

三件事最重要：

1. **规则文件每条都有来源和采集日期**——没有来源的数值是审美，审美进不了判据；
2. **人判那一半必须有承载字段，且复核人必须独立**——机器判不了好不好看，
   但能要求判的人不是写的人。2026-10-08 的事故就是写的人自己判了 `pass`；
3. **风格库每套都要有 `carrier`**——AP-02 靠它分流。少了这一格，
   判据不会报错，只是静默失效。
"""

import json
import sys
from pathlib import Path

SYSTEM = Path(__file__).resolve().parents[2]

SKILL = "skills/image-pipeline/SKILL.md"
SCHEMA = "capabilities/image-production/contracts/image-brief.schema.json"
VALIDATOR = "capabilities/image-production/scripts/validate_image_brief.py"
LIBRARY = "capabilities/image-production/styles/image-styles.json"
RULES = "capabilities/image-appeal/rules/appeal-rules.json"
PLAYBOOK = "capabilities/image-appeal/methods/expert-playbook.md"

RULE_IDS = [f"AP-{n:02d}" for n in range(1, 15)]

# 五条人判规则各自对应的登记维度。缺一个，判了也没地方写。
HUMAN_VERDICTS = {
    "information_gap", "unexpectedness", "emotional_arousal",
    "practical_value", "social_currency",
}

# 2026-10-07 定的四项。它们不能被后来的五项挤掉。
LEGACY_VERDICTS = {
    "same_direction_as_title", "has_readable_hook",
    "has_conflict_or_tension", "scannable_in_feed",
}


def read(relative: str) -> str:
    return (SYSTEM / relative).read_text(encoding="utf-8")


def load(relative: str) -> dict:
    return json.loads(read(relative))


def check_skill(errors: list) -> None:
    """站 2 / 站 3 / 站 5 的吸引力判据在不在。删掉一条，Agent 就会自己编做法。"""
    skill = read(SKILL)
    for needle, reason in [
        (
            "**吸引力分成两半：机器判的数值，人判的登记。**",
            "两半的分工是这套判据的骨架；不写这条，Agent 会把两者混为一谈",
        ),
        (
            "**「素」是可测的。**",
            "不写这条，「图比较素」永远只是审美意见，进不了判据",
        ),
        (
            "**阈值还没校准。**",
            "不写这条，未校准的阈值会被当成合格线引用出去",
        ),
        (
            "**复核的人不能是写的人。**",
            "2026-10-08 的事故：写简报的 Agent 自填四项 pass；不写这条，它会再发生",
        ),
        (
            "**测不了的不假装能测。**",
            "不写这条，五条心理判据会被硬塞一个假阈值",
        ),
        (
            "**`carrier` 决定封面要不要底图。**",
            "AP-02 靠 carrier 分流；不写这条，Agent 会按风格名选然后排纯文字图",
        ),
        (
            "**一组图是一个整体，不是十张单图。**",
            "组层面的四条判据（风格/隔离/序号/落点）单张图看不出问题",
        ),
        (
            "**九项全 `pass` 才允许简报进 `ready`。**",
            "判否条件；不写这条，appeal_review 填了 fail 也照样能进 ready",
        ),
        (
            "**不做风格自动选择。**",
            "风格靠看，不靠读（宪法 7）；不写这条，脚本会长成自动选风格",
        ),
        (
            "**不把吸引力复核交给写简报的人。**",
            "边界必须是否定式；否则「写的人自己判」会被当成可行路径",
        ),
        (
            "**不把未校准的阈值当合格线。**",
            "边界必须是否定式；否则 AP-03 会被当成已校准的标准",
        ),
        ("check_appeal.py", "校验器入口不在 skill 里，判据就没有执行者"),
        ("measure_card.py", "测量器入口不在 skill 里，「素」就没人量"),
        ("appeal-rules.json", "判据真源不在 skill 里，阈值就没有出处"),
        ("expert-playbook.md", "方法论不在 skill 里，判据会被当成仪式照做"),
    ]:
        if needle not in skill:
            errors.append(f"图文吸引力判据缺失（{reason}）: {needle}")


def check_rules(errors: list) -> None:
    """规则真源：十四条都在，每条有来源，来源有证据等级和采集日期。"""
    rules = load(RULES)
    entries = rules.get("rules", [])
    ids = [rule.get("id") for rule in entries]

    if ids != RULE_IDS:
        errors.append(f"吸引力规则从 {RULE_IDS} 变成了 {ids}——少一条就是少一道判据")

    sources = rules.get("sources", {})
    for key, source in sources.items():
        for field in ("title", "evidence", "collected_at"):
            if not source.get(field):
                errors.append(f"来源 {key} 缺 {field}——AGENTS.md 要求记录证据等级与采集日期")
        if source.get("evidence") not in {
            "官方规则", "直接证据", "强代理证据", "经验模式", "推断", "未知"
        }:
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
        if rule.get("scope") not in {"cover", "page", "deck", "copy"}:
            errors.append(f"规则 {label} 的 scope 取值非法：{rule.get('scope')!r}")

    human = [rule["id"] for rule in entries if rule.get("checkable") == "human"]
    machine = [rule["id"] for rule in entries if rule.get("checkable") == "machine"]
    if not human:
        errors.append(
            "十四条规则里没有一条标 human——「有没有人愿意看」不可能全靠机器判；"
            "全标 machine 就是把它谎报成机器能判"
        )
    if not machine:
        errors.append("十四条规则里没有一条标 machine——那这份文件就只是散文")

    # 未校准的阈值必须自己说清状态。不说，它会被当成合格线。
    ap03 = next((rule for rule in entries if rule.get("id") == "AP-03"), {})
    if ap03.get("value", {}).get("calibrated") is not False:
        errors.append(
            "AP-03 的 calibrated 不是显式的 false——样本只有 10 比 1，"
            "不说清状态，这个阈值会被当成已校准的标准引用"
        )


def check_playbook(errors: list) -> None:
    """方法论里每个来源都要带链接和采集日期。引用别人的框架要能追溯。"""
    text = read(PLAYBOOK)
    for needle in ("Loewenstein", "Berger & Milkman", "Von Restorff", "SUCCESs", "STEPPS"):
        if needle not in text:
            errors.append(f"方法论里找不到 {needle}——五条判据的道理缺一条")

    if "强代理证据" not in text or "经验模式" not in text:
        errors.append(
            "方法论没有区分证据等级——代理证据会被当成直接证据，"
            "机制存在被读成效果承诺"
        )

    if "采集 2026-10-08" not in text:
        errors.append("方法论里的来源没有采集日期——AGENTS.md 要求记录采集日期")


def check_schema(errors: list) -> None:
    """契约必填项与枚举。掉一格，简报写了也没人认，而且不会报错。"""
    schema = load(SCHEMA)
    top_required = set(schema.get("required", []))
    if "author" not in top_required:
        errors.append(
            "ImageBrief 必填项缺 author——没有它就没法要求复核人独立于写的人"
        )

    properties = schema.get("properties", {})

    deck = properties.get("deck")
    if not deck:
        errors.append(
            "ImageBrief 少了 deck——序号、单一风格、封面隔离、末页落点四条判据无处落地"
        )
    else:
        expected = {"style_id", "sequence_total", "cover_theme", "inner_theme"}
        if set(deck.get("required", [])) != expected:
            errors.append(f"deck 必填项变了：{deck.get('required')}——check_appeal 的 DECK_FIELDS 要跟着改")
        for key in ("cover_theme", "inner_theme"):
            values = deck.get("properties", {}).get(key, {}).get("enum", [])
            if set(values) != {"dark", "light", "colored"}:
                errors.append(f"deck.{key} 的枚举变了：{values}")

    item = properties.get("deliverables_items", {}).get("properties", {})
    for key, why in [
        ("sequence", "没有序号，读者不知道还剩多少（AP-06）"),
        ("base_image", "没有这一格，封面就没法要求承载体（AP-02）"),
        ("base_image_rights", "没有这一格，底图的权利状态无从登记"),
        ("points", "没有这一格，单页要点上限数不出来（AP-07）"),
        ("next_step", "没有这一格，末页落点无从要求（AP-09）"),
    ]:
        if key not in item:
            errors.append(f"ImageBrief 交付物少了 {key}——{why}")

    review = properties.get("appeal_review")
    if not review:
        errors.append("ImageBrief 顶层少了 appeal_review——人判那一半没有承载字段")
        return

    for key in ("reviewed_by", "reviewed_at", "evidence", "verdicts"):
        if key not in review.get("required", []):
            errors.append(
                f"appeal_review 必填项缺 {key}——"
                + ("不强制 evidence，复核就退化成照模板填" if key == "evidence"
                   else "不强制就会有人不写")
            )

    verdicts = review.get("properties", {}).get("verdicts", {})
    required = set(verdicts.get("required", []))
    if not LEGACY_VERDICTS.issubset(required):
        errors.append(
            f"appeal_review.verdicts 少了 2026-10-07 定的四项：{sorted(LEGACY_VERDICTS - required)}"
        )
    if not HUMAN_VERDICTS.issubset(required):
        errors.append(
            f"appeal_review.verdicts 少了心理触发器那五项：{sorted(HUMAN_VERDICTS - required)}——"
            "人判规则没有承载字段，判了也没地方写"
        )
    for key in sorted(required):
        values = verdicts.get("properties", {}).get(key, {}).get("enum", [])
        if set(values) != {"pass", "fail", "unknown"}:
            errors.append(f"appeal_review.verdicts.{key} 的取值变了：{values}")

    if "reviewed_by" in review.get("properties", {}):
        described = review["properties"]["reviewed_by"].get("description", "")
        if "author" not in described:
            errors.append(
                "reviewed_by 的描述里没有「必须与 author 不同」——"
                "那是校验器里最容易被静默删掉的一条拦截"
            )


def check_validator(errors: list) -> None:
    """校验器的结构与登记拦截。判据写在规则文件里，执行的是它。"""
    text = read(VALIDATOR)
    for anchor in ("def _check_deck(", "def _check_appeal_review(", "APPEAL_DIMENSIONS",
                   "check_appeal.failures("):
        if anchor not in text:
            errors.append(f"validate_image_brief.py 少了 {anchor}——判据没有执行者")

    for verdict in sorted(HUMAN_VERDICTS | LEGACY_VERDICTS):
        if verdict not in text:
            errors.append(f"校验器的 APPEAL_DIMENSIONS 少了 {verdict}")

    if "reviewed_by 和 author 都是" not in text:
        errors.append(
            "校验器没有拦「写的人和判的人是同一个」——2026-10-08 的事故就是这样发生的"
        )


def check_scripts(errors: list) -> None:
    """判据写在规则文件里，执行的是脚本。脚本少了函数，判据就没人执行。"""
    scripts = SYSTEM / "capabilities/image-appeal/scripts"
    for name, anchors in [
        ("measure_card.py", ["def measure(", "def distinct_colors(", "def edge_density(",
                             "def luma(", "def luma_profile("]),
        ("check_appeal.py", ["def load_rules(", "def rules_by_id(", "def check_deck(",
                             "def check_cover(", "def check_points(", "def check_complexity(",
                             "def check_copy(", "def check(", "def failures(",
                             "def resolve_metrics("]),
    ]:
        path = scripts / name
        if not path.is_file():
            errors.append(f"吸引力脚本不见了：{name}")
            continue
        text = path.read_text(encoding="utf-8")
        for anchor in anchors:
            if anchor not in text:
                errors.append(f"{name} 少了 {anchor}——规则文件里的判据没有执行者")


def check_style_carrier(errors: list) -> None:
    """风格库每套都要有 carrier。少了这一格，AP-02 静默失效。"""
    library = load(LIBRARY)
    styles = library.get("styles", [])
    for style in styles:
        carrier = style.get("carrier")
        if carrier not in {"base_image", "typography"}:
            errors.append(
                f"风格 {style.get('id', '?')} 的 carrier 缺失或非法：{carrier!r}——"
                "AP-02 靠它分流，缺了不会报错，只会静默失效"
            )
    kinds = {style.get("carrier") for style in styles}
    if kinds != {"base_image", "typography"}:
        errors.append(
            f"风格库的 carrier 取值只有 {sorted(kinds)}——"
            "两种都要有实例，否则 check_appeal 的分支从未被走到"
        )


def main() -> int:
    errors = []
    check_skill(errors)
    check_rules(errors)
    check_playbook(errors)
    check_schema(errors)
    check_validator(errors)
    check_scripts(errors)
    check_style_carrier(errors)

    if errors:
        print("FAIL image-appeal")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS image-appeal: 十四条判据真源、两半分工、复核独立性、风格 carrier 齐全")
    return 0


if __name__ == "__main__":
    sys.exit(main())
