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

sys.path.insert(0, str(SYSTEM))
sys.path.insert(0, str(SYSTEM / "capabilities/image-production/scripts"))
import validate_image_brief  # noqa: E402

SKILL = "skills/image-pipeline/SKILL.md"
SCHEMA = "capabilities/image-production/contracts/image-brief.schema.json"
LIBRARY = "capabilities/image-production/styles/image-styles.json"

# 一套风格缺任何一个字段，组装 prompt 时就会静默少一段。
# carrier 是 2026-10-08 补的：AP-02 靠它分流「封面要不要底图」，缺了不会报错，只会静默失效。
STYLE_FIELDS = {
    "id", "name", "summary", "platforms", "best_for",
    "tokens", "prompt", "image_style_enum", "anti_patterns", "sample",
    "carrier",
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
            "**图上有两种文字，分开走，别混。**",
            "两类文字的边界（事实主张挂 fact_ref / 封面文案挂 source_title）；"
            "不写这条，Agent 会把封面文案也拿去挂事实，封面又变回一张无字的图",
        ),
        (
            "**封面必须有 `cover_text`。**",
            "2026-10-07 的实例：封面无文字、与标题反向；不写这条，封面可以一路无字走到交付",
        ),
        (
            "**封面文案不挂事实，但它不是免责的。**",
            "封面文案不挂 fact_ref，就必须另有一条约束；不写这条，它就成了绕过事实纪律的后门",
        ),
        (
            "**文案怎么上封面：走 A 方案。**",
            "A/B 方案必须写清走哪条；不写这条，Agent 会让模型直接画字，中文糊字且改字要重出图",
        ),
        (
            "**九项全 `pass` 才允许简报进 `ready`。**",
            "吸引力复核的判否条件；不写这条，appeal_review 填了 fail 也照样能进 ready，等于没判",
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
        (
            "**示意图不走本线。**",
            "示意图要分流到信息图生产线；不写这条，Agent 会让模型去画流程图，画出来全是错的",
        ),
        (
            "**`role` 是猜的，`hex` 和 `coverage` 是量的。**",
            "不写这条，Agent 会把启发式 role 标签当成「这张图真有这六种角色」的证据",
        ),
        (
            "**一套参考图量一次，全套图共用。**",
            "逐张量会让同一组图各带各的色板，那是另一种风格漂移",
        ),
        (
            "**量出来的色板不写进 `image-styles.json`。**",
            "测量不是判断——不写这条，脚本会越长越像「自动加风格」，越权做宪法 7 归人的判断",
        ),
        (
            "`reference_instruction` 不是可选的",
            "万相 2.7 多图参考是生成+编辑模型，不说意图会把参考图当待编辑对象",
        ),
        (
            "**它只测颜色和面积，测不了「这张图配不配得上那句话」。**",
            "回测 PASS 不等于可发；不写这条，回测通过会被当成验收通过",
        ),
        (
            "**它按最近色匹配，不按 role 匹配。**",
            "逐 role 比会把「标签变了」误报成「颜色漂了」，假警报多了回测就白做",
        ),
        (
            "**阈值还没拿真实出图校准**",
            "校准状态是回测结论的一部分，不说清 PASS 会被当成「合格」",
        ),
        (
            "**不把参考图当素材用。**",
            "参考图多半不是自己拍的，拼进对外产物就是把别人的东西当自己的发出去",
        ),
    ]:
        if needle not in skill:
            errors.append(f"图片线判据缺失（{reason}）: {needle}")


def check_scripts(errors: list) -> None:
    """参考吸收的实现锚点。

    判据写在 skill 里，但真正执行的是脚本。脚本里少了这几个函数，
    skill 说的还算数，只是没人执行——那是最难发现的一类失效。
    """
    scripts = SYSTEM / "capabilities/image-production/scripts"
    for name, anchors in [
        (
            "measure_palette.py",
            ["def measure(", "def consensus(", "def dashscope_palette(", "def assign_roles("],
        ),
        ("verify_palette.py", ["def verify(", "def load_expected(", "DEFAULT_MAX_DELTA_E"]),
        ("color_math.py", ["def delta_e_2000(", "def format_oklch(", "def delta_e_76("]),
        ("png_io.py", ["def read_png(", "def _expand_fast(", "def iter_rgb("]),
        ("generate_image.py", ["def build_payload(", "def resolve_reference_images(",
                               "def load_color_palette("]),
        ("validate_image_brief.py", ["def _check_references(", "def _check_palette_ref(",
                                     "def _check_cover_text(", "def _check_appeal_review(",
                                     "def _check_deck(", "def load_layout_ids("]),
    ]:
        path = scripts / name
        if not path.is_file():
            errors.append(f"参考吸收的脚本不见了：{name}")
            continue
        text = path.read_text(encoding="utf-8")
        for anchor in anchors:
            if anchor not in text:
                errors.append(f"{name} 少了 {anchor}——skill 里的判据没有执行者")


def check_schema(errors: list) -> None:
    """契约文件必须存在，且必填项覆盖图片特有的那几格。"""
    schema = json.loads(read(SCHEMA))
    required = set(schema.get("required", []))

    for key in ("fact_refs", "deliverables", "platform", "prohibited_claims",
                "acceptance_criteria", "author"):
        if key not in required:
            errors.append(f"ImageBrief 必填项缺 {key}——不强制就会有人不写")

    # deck 是 2026-10-08 补的整组图层。四条组层面判据都挂在它上面。
    top = schema.get("properties", {})
    if "deck" not in top:
        errors.append(
            "ImageBrief 少了 deck——序号、单一风格、封面隔离、末页落点四条判据无处落地"
        )
    else:
        expected_deck = {"style_id", "sequence_total", "cover_theme", "inner_theme"}
        if set(top["deck"].get("required", [])) != expected_deck:
            errors.append(
                f"deck 必填项变了：{top['deck'].get('required')}——"
                "check_appeal 的 DECK_FIELDS 与 validate_image_brief 的 _check_deck 要跟着改"
            )

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

    # 参考吸收的三个可选字段。它们不是必填，但**必须还在 schema 里**——
    # 从 schema 里掉出去的表现是：简报写了也没人认，而校验器不会报错。
    properties = schema.get("properties", {}).get("deliverables_items", {}).get("properties", {})
    for key in ("reference_images", "reference_instruction", "palette_ref"):
        if key not in properties:
            errors.append(
                f"ImageBrief 交付物少了 {key}——参考吸收的字段从 schema 掉出去后，"
                "简报里写了也不认，而且不会报错"
            )

    # 吸引力判据的承载字段。同样不是必填，但掉出去就是静默失效。
    for key, why in [
        ("sequence", "AP-06 数不出序号"),
        ("base_image", "AP-02 没法要求封面承载体"),
        ("base_image_rights", "底图的权利状态无从登记"),
        ("points", "AP-07 数不出单页要点"),
        ("next_step", "AP-09 没法要求末页落点"),
    ]:
        if key not in properties:
            errors.append(f"ImageBrief 交付物少了 {key}——{why}")

    instruction = properties.get("reference_instruction", {})
    if "**reference_images 非空时必填**" not in instruction.get("description", ""):
        errors.append(
            "reference_instruction 的「非空时必填」约束从描述里掉了——"
            "那是校验器四条拦截里最容易被静默删掉的一条"
        )

    # 封面文字与吸引力复核。两个字段都不是必填，**但必须还在 schema 里**——
    # 从 schema 掉出去的表现和 palette_ref 一样：简报写了也没人认，而且不会报错。
    if "cover_text" not in properties:
        errors.append(
            "ImageBrief 交付物少了 cover_text——封面文案的承载字段掉出去后，"
            "封面只能是一张无字的图，而且校验器不会报错"
        )
    else:
        for key in ("headline", "source_title"):
            if key not in properties["cover_text"].get("required", []):
                errors.append(
                    f"cover_text 必填项缺 {key}——不强制，就会有人只写一句 hook、"
                    "不写它取自哪条标题"
                )

    if "appeal_review" not in top:
        errors.append(
            "ImageBrief 顶层少了 appeal_review——吸引力复核没有承载字段，"
            "复核做没做就无从查起"
        )
    else:
        review = top["appeal_review"]
        for key, why in [
            ("reviewed_by", "没有复核人就没有复核"),
            ("reviewed_at", "没有日期就没有复核"),
            ("evidence", "不强制 evidence，复核会退化成照模板填"),
            ("verdicts", "九项判断一项都不能少"),
        ]:
            if key not in review.get("required", []):
                errors.append(f"appeal_review 必填项缺 {key}——{why}")

        verdicts = review.get("properties", {}).get("verdicts", {})
        # 契约与校验器必须说同一件事。**从校验器读，不在这里再抄一份**——
        # 抄一份就是两个真源，然后有一边是错的。
        expected = set(validate_image_brief.APPEAL_DIMENSIONS)
        if set(verdicts.get("required", [])) != expected:
            errors.append(
                f"appeal_review.verdicts 与校验器的 APPEAL_DIMENSIONS 不一致："
                f"{sorted(set(verdicts.get('required', [])) ^ expected)}"
            )
        for key in sorted(expected):
            values = verdicts.get("properties", {}).get(key, {}).get("enum", [])
            if set(values) != {"pass", "fail", "unknown"}:
                errors.append(f"appeal_review.verdicts.{key} 的取值变了：{values}")

        described = review.get("properties", {}).get("reviewed_by", {}).get("description", "")
        if "author" not in described:
            errors.append(
                "reviewed_by 的描述里没有「必须与 author 不同」——"
                "2026-10-08 的事故就是写的人自己判了 pass"
            )


def check_library(errors: list) -> None:
    """风格库每套的字段必须齐全，缺一个组装 prompt 时就少一段。"""
    library = json.loads(read(LIBRARY))
    styles = library.get("styles", [])

    if len(styles) != 15:
        errors.append(f"风格库从 15 套变成了 {len(styles)} 套——少的那套会让对应的图出不来")

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
    check_scripts(errors)

    if errors:
        print("FAIL image-pipeline")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS image-pipeline: 五站判据、契约必填项与风格库完整性齐全")
    return 0


if __name__ == "__main__":
    sys.exit(main())
