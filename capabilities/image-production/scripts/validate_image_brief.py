#!/usr/bin/env python3
"""校验项目里 content/briefs/ 下的图片简报。

简报住在项目根，这个脚本住在系统根——路径等到真要读目录时再解析，
所以 validate(path) 单独调用不需要存在任何项目。

**这个校验器守两件具体的事。**

**一、图不能冒充它没有的东西。** 文章写错一句话，读者能追问出处。图不行——
一张看起来像产品界面的生成图，读者没有任何办法知道那是模型编的。所以图片线的
事实纪律不能靠「写的时候注意」，必须靠字段强制：每张图都要说清自己是什么
（`subject_kind`）、是不是生成的（`synthetic`）、素材哪来的、权利干不干净
（`source_assets`）。

**二、图上两种文字要分开走，封面不许是空的。** 2026-10-07 查清的一件事：
`claims_on_image` 要求「图上每一句主张逐条挂事实」——本意是防假主张（这一半对），
但它没区分**事实主张**和**封面文案**。封面文案是这篇文章的题目，不是事实主张，
挂不上 `fact_ref`，于是**封面被迫无文字**。而风格库的 `sample` 里本来就定义了
`headline` / `kicker` / `meta` / `layout`——风格支持封面文字，是契约把路堵了。
现在两类文字各走各的路：事实主张挂 `fact_ref`，封面文案挂 `source_title`。

**三、复核的人不能是写的人。** 2026-10-08 的事故：写简报的 Agent 自己把四项吸引力
全填了 `pass`，十张图交付，Conan 看完说「比较素，让人没啥阅读兴趣」。复核登记了，
质量没守住。机器判不了「有没有人愿意看」，但机器**能**要求判的人不是写的人——
所以 `appeal_review.reviewed_by` 必须与顶层 `author` 不同，并且要写清实际看过什么。

**四、数值判据不在这里，在 image-appeal。** 这个校验器守**结构与登记**：字段在不在、
枚举对不对、该有人判的时候有没有登记、复核人是否独立。阈值类判据（封面标题长度、
视觉复杂度、风格漂移、序号、落点、文案机器化）住在
`capabilities/image-appeal/rules/appeal-rules.json`，由 `check_appeal.py` 执行。
这里只负责把它调起来，**不重写它的数字**——一个方法只保留一个真源。
"""

import json
import sys
from pathlib import Path

_SYSTEM = next((p for p in Path(__file__).resolve().parents if (p / "project.py").is_file()), None)
if _SYSTEM is None:
    raise SystemExit("这个脚本只能在 hq-geo 系统根里运行（向上找不到 project.py）")
sys.path.insert(0, str(_SYSTEM))
sys.path.insert(0, str(_SYSTEM / "capabilities/image-appeal/scripts"))
from project import find_project  # noqa: E402
import check_appeal  # noqa: E402

REQUIRED = {
    "schema_version", "id", "topic_id", "title", "status", "objective", "audience",
    "core_thesis", "fact_refs", "platform", "deliverables", "prohibited_claims",
    "acceptance_criteria", "author",
}

# 声称「真实存在」的题材。这些不能由模型生成——生成了就是冒充。
# 与 AGENTS.md「禁止用生成图、示意图或空占位冒充产品事实」是同一条线。
REALITY_BOUND = {"product_ui", "customer_case", "real_conversation", "real_person"}

STYLE_LIBRARY = _SYSTEM / "capabilities/image-production/styles/image-styles.json"

# 吸引力复核的九个维度。少一个都等于没复核——「好看」不是一个能登记的判断。
# 前四项是 2026-10-07 定的同向与可读；后五项是 2026-10-08 补的心理触发器，
# 每条对应 appeal-rules.json 里一条有来源的人判规则（AP-10 至 AP-14）。
APPEAL_DIMENSIONS = (
    "same_direction_as_title",
    "has_readable_hook",
    "has_conflict_or_tension",
    "scannable_in_feed",
    "information_gap",
    "unexpectedness",
    "emotional_arousal",
    "practical_value",
    "social_currency",
)

# deck 的四格。少一格就有一条判据算不出来。
DECK_FIELDS = ("style_id", "sequence_total", "cover_theme", "inner_theme")

# 封面那张图的 role 里出现其中之一，校验器才认得出它是封面。
COVER_ROLE_HINTS = ("cover", "封面")


def load_style_ids() -> set:
    library = json.loads(STYLE_LIBRARY.read_text(encoding="utf-8"))
    return {item["id"] for item in library["styles"]}


def load_layout_ids() -> set:
    """风格库里实际出现过的文案位置。

    不另立一份枚举——风格库的 `sample.layout` 就是真源。
    在这里再抄一遍，两边就会各自演化，然后有一边是错的。
    """
    library = json.loads(STYLE_LIBRARY.read_text(encoding="utf-8"))
    return {
        item["sample"]["layout"]
        for item in library["styles"]
        if isinstance(item.get("sample"), dict) and item["sample"].get("layout")
    }


def _is_cover(item: dict) -> bool:
    """role 里出现 cover / 封面 就认它是封面。

    这是个**触发条件，不是证据**：认错的后果是漏一次要求，不是冤枉一张图，
    所以宁可宽松。反过来（把封面判成配图）才是要防的——那等于封面文案
    这一格可以绕过去。
    """
    role = (item.get("role") or "").lower()
    return any(hint in role for hint in COVER_ROLE_HINTS)


def find_project_root(start: Path):
    """从简报路径往上找项目根（有 `.hq-geo.json` 的那一级）。找不到返回 None。"""
    for candidate in [start, *start.parents]:
        if (candidate / ".hq-geo.json").is_file():
            return candidate
    return None


def _check_references(item: dict, label: str, root) -> list:
    """参考图的三条拦截：要有说明、路径要在项目根内、文件要真的在。

    这三条都是**出图前**必须过的。出图是花钱的动作，
    路径拼错、文件没拷进来这类事必须在花钱之前就停下。
    """
    references = item.get("reference_images") or []
    if not references:
        # 没有参考图时 `reference_instruction` 是空话，不要求填（宪法 8：默认减法）。
        return []

    errors = []
    if not (item.get("reference_instruction") or "").strip():
        errors.append(
            f"{label}: 有 reference_images 就必须写 reference_instruction——"
            "万相 2.7 是多图参考的**生成+编辑**模型，不说清参考什么，"
            "它可能把参考图当成待编辑对象，你拿到的就是「改了一下的参考图」"
        )

    if root is None:
        return errors

    resolved_root = Path(root).resolve()
    for raw in references:
        candidate = (resolved_root / raw).resolve()
        if not candidate.is_relative_to(resolved_root):
            errors.append(
                f"{label}: 参考图 {raw!r} 指向项目根之外。"
                "参考图大概率不是自己拍的，越出项目根既无法登记来源和权利，也说不清用途"
            )
        elif not candidate.is_file():
            errors.append(f"{label}: 参考图不存在：{raw!r}（出图时才发现就白花了钱）")
    return errors


def _check_palette_ref(item: dict, label: str, root) -> list:
    """色板引用要真的存在、真的是 `measure_palette.py` 的输出。

    不查的话，格式不对时会**静默不出色板**——图和预期两样，但没有任何报错，
    只能靠人肉发现。那是这类 bug 里最难查的一种。
    """
    palette_ref = item.get("palette_ref")
    if not palette_ref:
        return []
    if root is None:
        return []

    resolved_root = Path(root).resolve()
    candidate = (resolved_root / palette_ref).resolve()
    if not candidate.is_relative_to(resolved_root):
        return [f"{label}: palette_ref {palette_ref!r} 指向项目根之外"]
    if not candidate.is_file():
        return [f"{label}: palette_ref 指向的文件不存在：{palette_ref!r}"]

    try:
        data = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"{label}: palette_ref 不是合法 JSON：{palette_ref!r}（{error}）"]

    if not isinstance(data, dict) or "per_image" not in data or "consensus" not in data:
        return [
            f"{label}: palette_ref 指向的不是 measure_palette.py 的输出"
            f"（缺 per_image / consensus 字段）：{palette_ref!r}"
        ]
    return []


def _check_base_image(item: dict, label: str, root) -> list:
    """封面底图的两条拦截：路径不许越界，出了图就必须真的在。

    这是 2026-10-08 补的。AP-02 要求封面有 `base_image`，但**写了不等于有**——
    路径拼错、忘了生成、文件被挪走，三种情况都会让封面渲染成一块空白底，
    而简报看上去是合规的。**那正好是「图比较素」这个缺陷换个方式回来。**

    存在性只在 `status == "generated"` 时要求：planned 的图还没出，
    底图当然还不在；出了图还说不在，就是简报在说谎。
    """
    raw = (item.get("base_image") or "").strip()
    if not raw:
        return []
    if root is None:
        return []

    resolved_root = Path(root).resolve()
    candidate = (resolved_root / raw).resolve()
    if not candidate.is_relative_to(resolved_root):
        return [
            f"{label}: base_image {raw!r} 指向项目根之外——"
            "越出项目根的图既无法登记来源和权利，也说不清用途"
        ]
    if item.get("status") == "generated" and not candidate.is_file():
        return [
            f"{label}: base_image 声明为已生成，但文件不在：{raw!r}——"
            "封面会渲染成一块空白底，而简报看上去是合规的"
        ]
    return []


def _check_cover_text(item: dict, label: str, layout_ids: set) -> list:
    """封面文案：结构上能判的那几格。

    **它和 `claims_on_image` 是两类文字**，这条边界必须由字段守住。
    混起来的后果只有两种，而且都真实发生过：封面要么被迫无字
    （事实挂不上），要么变成绕过事实纪律的后门（新编一句承诺但不挂任何东西）。

    机器判不了「这条文案有没有吸引力」，也判不了「它和标题同不同向」。
    这里只守结构：写没写、取自哪里、有没有风格来排版、有没有和事实主张重复。
    """
    cover_text = item.get("cover_text")
    if cover_text is None:
        return []
    if not isinstance(cover_text, dict):
        return [f"{label}: cover_text 必须是对象（现在是 {type(cover_text).__name__}）"]

    errors = []

    if not (cover_text.get("headline") or "").strip():
        errors.append(
            f"{label}: cover_text 有，但 headline 是空的——"
            "封面不写字，读者在信息流里扫到它，看不到自己"
        )

    if not (cover_text.get("source_title") or "").strip():
        errors.append(
            f"{label}: cover_text 缺 source_title——封面文案是文章或商品的题目，"
            "它不挂 fact_ref，但必须写清取自哪条标题；"
            "写不出取自哪里，它就是一句新编的、没人认领的承诺"
        )

    if not item.get("style_id"):
        errors.append(
            f"{label}: 有 cover_text 就必须有 style_id——"
            "文案要按风格排版，没有风格就没有排版规则，字会随便压"
        )

    layout = (cover_text.get("layout") or "").strip()
    if layout and layout_ids and layout not in layout_ids:
        errors.append(
            f"{label}: cover_text.layout {layout!r} 不在风格库出现过的位置里。"
            f"可选：{', '.join(sorted(layout_ids))}"
        )

    # 同一句话不能既当题目又当事实主张——那会让「挂没挂 fact_ref」这个信号失真。
    texts = {(cover_text.get("headline") or "").strip()}
    for key in ("kicker", "meta"):
        value = (cover_text.get(key) or "").strip()
        if value:
            texts.add(value)
    for claim in item.get("claims_on_image") or []:
        claim_text = (claim.get("text") or "").strip()
        if claim_text and claim_text in texts:
            errors.append(
                f"{label}: 「{claim_text}」同时出现在 cover_text 和 claims_on_image 里——"
                "同一句话只能走一条路：是题目就挂 source_title，是事实主张就挂 fact_ref"
            )

    return errors


def _check_appeal_review(data: dict, deliverables: list) -> list:
    """吸引力复核：人判，但必须登记，且判的人不能是写的人。

    这是图片线**求好**那条腿的判据。它没有机器判据——「这张封面能不能让人停下来」
    机器答不了。所以这里不假装能判，只守三件机器能守的事：
    **该有复核的时候有没有、有没有留下未决的判断、复核人是不是独立于写的人。**

    不登记就等于没做，而没做的封面照样能出图、照样能发——这正是
    2026-10-07 那张「线缆整齐排布、无文字、与标题反向」的封面能一路走到交付的原因。

    2026-10-08 又抓到一层：**登记了也不够。** 写简报的 Agent 自己把四项全填了 `pass`，
    十张图交付，Conan 看完说「比较素，让人没啥阅读兴趣」。所以加了第三条：
    `reviewed_by` 必须与 `author` 不同，并且要写清实际看过什么。
    同一个人写又同一个人判，等于没判。
    """
    with_cover_text = [
        item.get("id") or "(没有 id)"
        for item in deliverables
        if isinstance(item.get("cover_text"), dict)
    ]
    if not with_cover_text:
        return []

    review = data.get("appeal_review")
    if not isinstance(review, dict):
        return [
            "appeal_review 缺失：这份简报里 "
            + "、".join(with_cover_text)
            + " 有封面文案，却没有任何吸引力复核记录——"
            "封面和标题的吸引力没有机器判据，不登记就等于没做"
        ]

    errors = []
    for key in ("reviewed_by", "reviewed_at", "evidence"):
        if not (review.get(key) or "").strip():
            errors.append(
                f"appeal_review 缺 {key}——"
                + ("没有复核人和日期，就没有复核" if key != "evidence"
                   else "写不出实际看过什么，这份复核就是照着模板填的")
            )

    author = (data.get("author") or "").strip()
    reviewer = (review.get("reviewed_by") or "").strip()
    if author and reviewer and reviewer == author:
        errors.append(
            f"appeal_review.reviewed_by 和 author 都是 {reviewer!r}——"
            "写简报的人不能自己判「有没有人愿意看」。"
            "2026-10-08 的事故就是这样发生的：Agent 自填四项 pass，十张图交付，"
            "Conan 看完说「比较素」。换一个独立的人或独立的 agent 复核"
        )

    verdicts = review.get("verdicts")
    if not isinstance(verdicts, dict):
        return errors + ["appeal_review 缺 verdicts（九项判断一项都不能少）"]

    for key in APPEAL_DIMENSIONS:
        value = verdicts.get(key)
        if value is None:
            errors.append(f"appeal_review 缺 {key}")
        elif value == "unknown":
            errors.append(
                f"appeal_review 的 {key} 还是 unknown——"
                "ready 的简报不能带着未决的吸引力判断往下走"
            )
        elif value != "pass":
            errors.append(
                f"appeal_review 的 {key} 是 {value!r}——"
                "九项里有一项没过，封面就还不该进 ready：先改封面，再复核"
            )
    return errors


def _check_deck(data: dict, deliverables: list) -> list:
    """整组图的四格必须在，且取值合法。

    这一格是 2026-10-08 补的。之前简报只描述单张图，没有「组」的概念，
    于是四条判据无处落地：全套共用一个风格、封面从内页里隔离出来、
    序号与总数、末页落点。它们全是**组层面**的事，单张图看不出问题。

    阈值判据不在这里——这里只守结构与取值。数值比对在 check_appeal.py。
    """
    deck = data.get("deck")
    if not isinstance(deck, dict):
        if len(deliverables) >= 2:
            return [
                "deck 缺失：这份简报有 "
                f"{len(deliverables)} 张图，却没有 deck 块——"
                "序号、单一风格、封面隔离、末页落点四条判据都无处落地"
            ]
        return []

    errors = []
    for key in DECK_FIELDS:
        if deck.get(key) in (None, "", []):
            errors.append(f"deck 缺 {key}")

    for key in ("cover_theme", "inner_theme"):
        value = deck.get(key)
        if value and value not in {"dark", "light", "colored"}:
            errors.append(f"deck.{key} 取值非法：{value!r}（只允许 dark / light / colored）")

    total = deck.get("sequence_total")
    if total is not None and (not isinstance(total, int) or isinstance(total, bool) or total < 2):
        errors.append(f"deck.sequence_total 必须是 ≥2 的整数，现在是 {total!r}")

    return errors


def validate(path: Path, style_ids: set, project: Path = None, layout_ids: set = None) -> list:
    """校验一份图片简报。

    `project` 是项目根，用来判断参考图路径有没有越界、文件在不在。
    不给就**从简报路径往上找** `.hq-geo.json`——这样单测里传个临时文件
    也能跑，不必先造一个项目。

    `layout_ids` 是风格库里出现过的文案位置。不给就现读风格库。
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = [f"missing {key}" for key in sorted(REQUIRED - data.keys())]
    if errors:
        return errors

    if not data.get("fact_refs"):
        errors.append("fact_refs must not be empty")

    deliverables = data.get("deliverables") or []
    if not deliverables:
        errors.append("deliverables must not be empty")

    errors.extend(_check_deck(data, deliverables))

    root = project or find_project_root(path.parent)
    if layout_ids is None:
        layout_ids = load_layout_ids()

    blocked = []
    for item in deliverables:
        label = item.get("id") or "(没有 id)"
        kind = item.get("subject_kind")

        if kind not in REALITY_BOUND | {"concept"}:
            errors.append(f"{label}: subject_kind 必须是 concept / {' / '.join(sorted(REALITY_BOUND))} 之一，现在是 {kind!r}")
        elif kind in REALITY_BOUND and item.get("synthetic") is not False:
            errors.append(
                f"{label}: subject_kind={kind} 是声称真实存在的东西，synthetic 必须显式为 false"
                f"（现在是 {item.get('synthetic')!r}）——生成图冒充产品界面/客户案例/真实记录是硬线"
            )

        if not isinstance(item.get("synthetic"), bool):
            errors.append(f"{label}: synthetic 必须显式写 true 或 false，不能缺省——缺省就是没声明")

        if item.get("status") == "blocked":
            blocked.append(label)

        for asset in item.get("source_assets") or []:
            if not asset.get("rights"):
                errors.append(f"{label}: 素材 {asset.get('path')!r} 没写权利状态（rights）")

        for claim in item.get("claims_on_image") or []:
            if not claim.get("fact_ref"):
                errors.append(
                    f"{label}: 图上这句「{claim.get('text')}」没挂 fact_ref——"
                    "图上写的字和正文一样要能被追问出处"
                )

        style_id = item.get("style_id")
        if style_id and style_id not in style_ids:
            errors.append(
                f"{label}: style_id {style_id!r} 不在风格库里。"
                f"拼错不会报错，只会静默地出一张没有风格的图。可选：{', '.join(sorted(style_ids))}"
            )

        errors.extend(_check_references(item, label, root))
        errors.extend(_check_palette_ref(item, label, root))
        errors.extend(_check_cover_text(item, label, layout_ids))
        errors.extend(_check_base_image(item, label, root))

    ready = data.get("status") in {"ready_for_production", "ready_for_review"}

    # 封面不许是空的。这条是 2026-10-07 Conan 指出「封面怎么一个字都没有」的机器版本：
    # 允许封面无文字，等于允许它在一屏几十条的流里不被任何人看见。
    covers_without_text = [
        item.get("id") or "(没有 id)"
        for item in deliverables
        if _is_cover(item) and not isinstance(item.get("cover_text"), dict)
    ]
    if ready and covers_without_text:
        errors.append(
            "ready 的简报里，封面没有封面文案："
            + "、".join(covers_without_text)
            + "——封面不写字，读者在信息流里扫不到它。"
            "（role 含 cover / 封面 的图才算封面）"
        )

    if ready:
        errors.extend(_check_appeal_review(data, deliverables))

    if data.get("status") == "ready_for_production" and blocked:
        errors.append(f"ready brief 里还有 blocked 的图：{', '.join(blocked)}")

    # 数值判据交给 image-appeal 执行。**这里不重写它的阈值**——一个方法只保留一个真源。
    # 它判的是「有人愿意点」那半边：封面标题长度、视觉承载体、视觉复杂度、
    # 封面隔离、风格漂移、序号、落点、文案机器化。测不了的五项由上面的
    # _check_appeal_review 守登记与独立性。
    metrics = check_appeal.resolve_metrics(path, data, root)
    for item in check_appeal.failures(check_appeal.check(data, metrics=metrics)):
        errors.append(f"[{item['rule_id']} {item['rule_name']}] {item['message']}")

    return errors


def main() -> int:
    project = find_project()
    style_ids = load_style_ids()
    layout_ids = load_layout_ids()
    files = sorted((project / "content/briefs").glob("**/image-brief.json"))
    if not files:
        # 新项目一份简报都没有是正常的，不是错误。这个校验器的职责是
        # 「存在的简报都要合法」——空集合上没有反例。
        # 「本来有、现在没了」由产出基准抓，那是另一个信号，见 test/baseline.json。
        print(f"PASS image brief contract: {project.name} 还没有图片简报")
        return 0
    results = {
        str(path.relative_to(project)): validate(path, style_ids, layout_ids=layout_ids)
        for path in files
    }
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 1 if any(results.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
