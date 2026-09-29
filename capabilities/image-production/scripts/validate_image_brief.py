#!/usr/bin/env python3
"""校验项目里 content/briefs/ 下的图片简报。

简报住在项目根，这个脚本住在系统根——路径等到真要读目录时再解析，
所以 validate(path) 单独调用不需要存在任何项目。

**这个校验器守的是一件具体的事：图不能冒充它没有的东西。**

文章写错一句话，读者能追问出处。图不行——一张看起来像产品界面的生成图，
读者没有任何办法知道那是模型编的。所以图片线的事实纪律不能靠「写的时候注意」，
必须靠字段强制：每张图都要说清自己是什么（`subject_kind`）、
是不是生成的（`synthetic`）、素材哪来的、权利干不干净（`source_assets`）。
"""

import json
import sys
from pathlib import Path

_SYSTEM = next((p for p in Path(__file__).resolve().parents if (p / "project.py").is_file()), None)
if _SYSTEM is None:
    raise SystemExit("这个脚本只能在 hq-geo 系统根里运行（向上找不到 project.py）")
sys.path.insert(0, str(_SYSTEM))
from project import find_project  # noqa: E402

REQUIRED = {
    "schema_version", "id", "topic_id", "title", "status", "objective", "audience",
    "core_thesis", "fact_refs", "platform", "deliverables", "prohibited_claims",
    "acceptance_criteria",
}

# 声称「真实存在」的题材。这些不能由模型生成——生成了就是冒充。
# 与 AGENTS.md「禁止用生成图、示意图或空占位冒充产品事实」是同一条线。
REALITY_BOUND = {"product_ui", "customer_case", "real_conversation", "real_person"}

STYLE_LIBRARY = _SYSTEM / "capabilities/image-production/styles/image-styles.json"


def load_style_ids() -> set:
    library = json.loads(STYLE_LIBRARY.read_text(encoding="utf-8"))
    return {item["id"] for item in library["styles"]}


def validate(path: Path, style_ids: set) -> list:
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = [f"missing {key}" for key in sorted(REQUIRED - data.keys())]
    if errors:
        return errors

    if not data.get("fact_refs"):
        errors.append("fact_refs must not be empty")

    deliverables = data.get("deliverables") or []
    if not deliverables:
        errors.append("deliverables must not be empty")

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

    if data.get("status") == "ready_for_production" and blocked:
        errors.append(f"ready brief 里还有 blocked 的图：{', '.join(blocked)}")

    return errors


def main() -> int:
    project = find_project()
    style_ids = load_style_ids()
    files = sorted((project / "content/briefs").glob("**/image-brief.json"))
    if not files:
        # 新项目一份简报都没有是正常的，不是错误。这个校验器的职责是
        # 「存在的简报都要合法」——空集合上没有反例。
        # 「本来有、现在没了」由产出基准抓，那是另一个信号，见 test/baseline.json。
        print(f"PASS image brief contract: {project.name} 还没有图片简报")
        return 0
    results = {str(path.relative_to(project)): validate(path, style_ids) for path in files}
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 1 if any(results.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
