#!/usr/bin/env python3
"""图片线的契约检查。

图片线是强依赖 AI 生成的一条线——不是图片编辑。它的判据写在
`skills/image-pipeline/SKILL.md` 里，Agent 每次出图都要读它。

判据被删掉或被改弱，Agent 不会报错——它会自己编一套做法，
然后拿着编出来的做法去调模型，钱花了，图出来了，**而图上写着没人能证实的东西**。
那比读不到更糟。所以这个检查盯的是**判据在不在**，不是措辞好不好。
"""

import json
import sys
from pathlib import Path

SYSTEM = Path(__file__).resolve().parents[2]

SKILL = "skills/image-pipeline/SKILL.md"
SCHEMA = "capabilities/image-production/contracts/image-brief.schema.json"
LIBRARY = "capabilities/image-production/styles/image-styles.json"

# 一套风格缺任何一个字段，组装 prompt 时就会静默少一段。
STYLE_FIELDS = {
    "id", "name", "summary", "platforms", "best_for",
    "tokens", "prompt", "image_style_enum", "anti_patterns", "sample",
}


def read(relative: str) -> str:
    return (SYSTEM / relative).read_text(encoding="utf-8")


def check_skill(errors: list) -> None:
    """入口 skill：什么时候触发、五站的判据在不在。"""
    skill = read(SKILL)

    for needle, reason in [
        (
            "**这条线强依赖 AI 生成，不做图片编辑。**",
            "图片线是生成不是编辑（2026-09-29 Conan 定），不写明会被用户要求改图，然后做不了",
        ),
        (
            "**`subject_kind` 是这份简报最重要的一格。**",
            "题材决定能不能生成——不写明，Agent 会直接给「产品界面」出生成图",
        ),
        (
            "**图上不要写字，除非它能挂上事实。**",
            "图上文字的事实纪律，和文章线同源；不写这条，图上会出现正文里没有的承诺",
        ),
        (
            "**风格靠看，不靠读。**",
            "风格必须看样选，不写明 Agent 会凭风格名推荐，用户拿到的东西和预期不符",
        ),
        (
            "**一套图共用一个 `style_id`。**",
            "风格漂移是成套图最明显的破绽，必须有硬判据",
        ),
        (
            "**把 prompt 念给用户听一遍再出图。**",
            "出图要花钱，prompt 错一个词四张图一起错——先审后做比先做后改便宜",
        ),
        (
            "**机器检查 + 人看，两道都要，不能互相替代。**",
            "机器查不了「这张图配不配得上那句话」；只跑校验器会交付好看但无关的图",
        ),
        (
            "**不做图片编辑。**",
            "边界必须有否定的用法，否则只是一句介绍",
        ),
    ]:
        if needle not in skill:
            errors.append(f"图片线判据缺失（{reason}）: {needle}")


def check_schema(errors: list) -> None:
    """契约文件必须存在，且必填项覆盖图片特有的那几格。"""
    schema = json.loads(read(SCHEMA))
    required = set(schema.get("required", []))

    for key in ("fact_refs", "deliverables", "platform", "prohibited_claims", "acceptance_criteria"):
        if key not in required:
            errors.append(f"ImageBrief 必填项缺 {key}——不强制就会有人不写")

    item = schema.get("properties", {}).get("deliverables_items", {}).get("required", [])
    for key in ("subject_kind", "synthetic", "source_assets"):
        if key not in item:
            errors.append(f"ImageBrief 交付物必填项缺 {key}——这三格是「图不能冒充」的执行点")

    kinds = (
        schema.get("properties", {})
        .get("deliverables_items", {})
        .get("properties", {})
        .get("subject_kind", {})
        .get("enum", [])
    )
    if set(kinds) != {"concept", "product_ui", "customer_case", "real_conversation", "real_person"}:
        errors.append(f"ImageBrief 的 subject_kind 枚举变了：{kinds}——校验器的 REALITY_BOUND 要跟着改")


def check_library(errors: list) -> None:
    """风格库每套的字段必须齐全，缺一个组装 prompt 时就少一段。"""
    library = json.loads(read(LIBRARY))
    styles = library.get("styles", [])

    if len(styles) != 14:
        errors.append(f"风格库从 14 套变成了 {len(styles)} 套——少的那套会让对应的图出不来")

    if not library.get("origin", {}).get("moved_from"):
        errors.append("风格库缺来源记录——搬来的资产要写清从哪搬的、什么时候")

    for style in styles:
        missing = STYLE_FIELDS - set(style)
        if missing:
            errors.append(f"风格 {style.get('id', '?')} 缺字段：{sorted(missing)}")

    ids = [style.get("id") for style in styles]
    if len(ids) != len(set(ids)):
        errors.append("风格 id 有重复——按 id 取风格会取到错的那套")


def main() -> int:
    errors = []
    check_skill(errors)
    check_schema(errors)
    check_library(errors)

    if errors:
        print("FAIL image-pipeline")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS image-pipeline: 五站判据、契约必填项与风格库完整性齐全")
    return 0


if __name__ == "__main__":
    sys.exit(main())
