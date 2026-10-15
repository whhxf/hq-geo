#!/usr/bin/env python3
"""图文吸引力的机器判据执行者。阈值全部从 `rules/appeal-rules.json` 读。

**这个脚本守的是「有人愿意点」那条腿里机器能守的部分。**

2026-10-08 之前，图片线五站全是事实纪律——每一站都在回答「这张图有没有骗人」，
没有一站回答「有没有人愿意看」。`appeal_review` 补上了登记，但它只守
「该复核的时候有没有复核」。于是出现了一件事：Agent 把四个维度全填了 `pass`，
十张图交付，Conan 看完说「比较素，没啥阅读兴趣」。**复核登记了，质量没守住。**

这里补的是那一半：把能测的测出来。测不了的（信息缺口、情绪唤醒、信息价值、社交货币）
不在这里假装能判——它们由 `appeal_review` 登记，并且复核人必须独立于简报作者。

**严重度约定与排版线一致**：硬边界外是 `fail`，目标范围外是 `warn`。
`failures()` 只取 `fail`。

**它不判「好不好看」。** 它判的是「画面里有没有东西」「风格有没有漂」「文案有没有机器残留」
这类能被数出来的事。剩下的归人。
"""

import argparse
import json
import re
import sys
from pathlib import Path

_SYSTEM = next((p for p in Path(__file__).resolve().parents if (p / "project.py").is_file()), None)
if _SYSTEM is None:
    raise SystemExit("这个脚本只能在 hq-geo 系统根里运行（向上找不到 project.py）")

# 复用两处已有实现，不另写一份：
# - png_io：PNG 解码（图片线）
# - check_authorial：机器化模式的词表与正则（文章线）
sys.path.insert(0, str(_SYSTEM / "capabilities/image-production/scripts"))
sys.path.insert(0, str(_SYSTEM / "capabilities/content-production/scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import png_io  # noqa: E402,F401
import check_authorial  # noqa: E402
import measure_card  # noqa: E402

RULES = _SYSTEM / "capabilities/image-appeal/rules/appeal-rules.json"
STYLE_LIBRARY = _SYSTEM / "capabilities/image-production/styles/image-styles.json"

# 封面那张图的 role 里出现其中之一，才被认成封面。与 validate_image_brief.py 同一条约定。
COVER_ROLE_HINTS = ("cover", "封面")

# 序号格式：NN/NN。前一个 NN 是第几张，后一个是总数。
SEQUENCE = re.compile(r"^(\d{1,3})\s*/\s*(\d{1,3})$")


def load_rules(path=None) -> dict:
    return json.loads(Path(path or RULES).read_text(encoding="utf-8"))


def rules_by_id(rules: dict) -> dict:
    return {rule["id"]: rule for rule in rules.get("rules", [])}


def load_styles() -> dict:
    """风格 id → 整套风格。carrier 字段在这里读，不在判据文件里另存一份。"""
    library = json.loads(STYLE_LIBRARY.read_text(encoding="utf-8"))
    return {item["id"]: item for item in library.get("styles", [])}


def _violation(rule_id, rule_name, severity, message) -> dict:
    return {"rule_id": rule_id, "rule_name": rule_name, "severity": severity, "message": message}


def _range(value, spec, unit):
    """返回 (严重度, 说明) 或 None。硬边界外是 fail，目标范围外是 warn。

    与 typography 的 check_layout._range 同一套约定——两边的严重度含义必须一致，
    否则同一个词在两个校验器里是两个意思。
    """
    if value is None:
        return "fail", f"没填（{unit}）"
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return "fail", f"不是数字：{value!r}"
    for key, mark in (("hard_min", "fail"), ("hard_max", "fail"),
                      ("target_min", "warn"), ("target_max", "warn")):
        if key not in spec:
            continue
        if key.endswith("_min") and value < spec[key]:
            return mark, f"{value}{unit} 低于{'硬' if mark == 'fail' else '目标'}下限 {spec[key]}{unit}"
        if key.endswith("_max") and value > spec[key]:
            return mark, f"{value}{unit} 高于{'硬' if mark == 'fail' else '目标'}上限 {spec[key]}{unit}"
    return None


def is_cover(item: dict) -> bool:
    role = (item.get("role") or "").lower()
    return any(hint in role for hint in COVER_ROLE_HINTS)


def find_project_root(start: Path):
    for candidate in [start, *start.parents]:
        if (candidate / ".hq-geo.json").is_file():
            return candidate
    return None


def sort_key(item: dict, index: int):
    """按序号排。没有序号的排到最后，并保持原有顺序。"""
    match = SEQUENCE.match((item.get("sequence") or "").strip())
    return (0, int(match.group(1)), index) if match else (1, index, index)


def _copy_texts(deliverables: list) -> list:
    """图上会出现的全部文字。机器化模式扫描的输入。

    三种来源都算：封面文案、并列要点、事实主张。
    事实主张也要扫——「图上写的字和正文一样要能被追问出处」，
    它当然也不该带机器味。
    """
    texts = []
    for item in deliverables:
        cover = item.get("cover_text")
        if isinstance(cover, dict):
            for key in ("headline", "kicker", "meta"):
                value = (cover.get(key) or "").strip()
                if value:
                    texts.append(value)
        for point in item.get("points") or []:
            if str(point).strip():
                texts.append(str(point).strip())
        for claim in item.get("claims_on_image") or []:
            if (claim.get("text") or "").strip():
                texts.append(claim["text"].strip())
        if (item.get("next_step") or "").strip():
            texts.append(item["next_step"].strip())
    return texts


def check_deck(data: dict, rules: dict, styles: dict) -> list:
    """AP-04 / AP-05 / AP-06 / AP-09：整组图层面的判据。"""
    items = []
    by_id = rules_by_id(rules)
    deliverables = data.get("deliverables") or []
    deck = data.get("deck")

    if not isinstance(deck, dict):
        if len(deliverables) >= 2:
            return [_violation("DECK", "图集", "fail",
                               "多张图却没有 deck 块——序号、单一风格、封面隔离、末页落点都无处登记")]
        return []

    # AP-05 · 全套共用一个风格
    rule = by_id.get("AP-05")
    if rule:
        deck_style = deck.get("style_id")
        if not deck_style:
            items.append(_violation("AP-05", rule["name"], "fail", "deck 缺 style_id"))
        else:
            strays = [
                item.get("id") or "(没有 id)"
                for item in deliverables
                if item.get("style_id") != deck_style
            ]
            if strays:
                items.append(_violation(
                    "AP-05", rule["name"], "fail",
                    f"这些图的 style_id 不等于 deck.style_id {deck_style!r}：{', '.join(strays)}——"
                    "风格漂移是成套图最明显的破绽"))
        if deck_style and deck_style not in styles:
            items.append(_violation("AP-05", rule["name"], "fail",
                                    f"deck.style_id {deck_style!r} 不在风格库里"))
        elif deck_style:
            carrier = styles[deck_style].get("carrier")
            if carrier not in {"base_image", "typography"}:
                items.append(_violation(
                    "AP-05", rule["name"], "fail",
                    f"风格 {deck_style!r} 的 carrier 取值非法：{carrier!r}"
                    "（只允许 base_image / typography）——风格库改了，判据要跟着改"))

    # AP-04 · 封面与内页的视觉隔离
    rule = by_id.get("AP-04")
    if rule:
        cover_theme = deck.get("cover_theme")
        inner_theme = deck.get("inner_theme")
        if not cover_theme or not inner_theme:
            items.append(_violation("AP-04", rule["name"], "fail",
                                    "deck 缺 cover_theme 或 inner_theme——隔离判据无从计算"))
        elif cover_theme == inner_theme:
            items.append(_violation(
                "AP-04", rule["name"], "fail",
                f"封面与内页同为主题 {cover_theme!r}——封面没有从内页里隔离出来，"
                "读者在信息流里认不出它是入口"))

    # AP-06 · 序号与总数
    rule = by_id.get("AP-06")
    if rule:
        total = deck.get("sequence_total")
        if not isinstance(total, int) or isinstance(total, bool) or total < 2:
            items.append(_violation("AP-06", rule["name"], "fail",
                                    f"deck.sequence_total 必须是 ≥2 的整数，现在是 {total!r}"))
        else:
            if total != len(deliverables):
                items.append(_violation(
                    "AP-06", rule["name"], "fail",
                    f"sequence_total={total} 但交付物有 {len(deliverables)} 张——"
                    "总数对不上，读者看到的进度就是假的"))
            for item in deliverables:
                label = item.get("id") or "(没有 id)"
                match = SEQUENCE.match((item.get("sequence") or "").strip())
                if not match:
                    items.append(_violation(
                        "AP-06", rule["name"], "fail",
                        f"{label}: 缺序号或格式不对（要 NN/NN）——没有进度，读者不知道还剩多少"))
                elif int(match.group(2)) != total:
                    items.append(_violation(
                        "AP-06", rule["name"], "fail",
                        f"{label}: 序号 {item.get('sequence')!r} 的总数和 deck 的 {total} 不一致"))

    # AP-09 · 末页落点
    #
    # **这一条在 ready 时才要求。** 落点是内容决策，而且常常依赖还没做出来的产品——
    # 一个 blocked 的简报不该被迫编一句落点出来。这与 validate_image_brief 里
    # `appeal_review` 和 `covers_without_text` 的门槛一致：交付类要求在 ready 时绑。
    #
    # 其余八条任何时候都要：它们判的是**做法对不对**（封面有没有承载体、风格有没有漂、
    # 序号对不对得上），不是**料齐没齐**。做法错了不是缺料，缺料停机不豁免它。
    rule = by_id.get("AP-09")
    ready = data.get("status") in {"ready_for_production", "ready_for_review"}
    if rule and deliverables and ready:
        ordered = sorted(enumerate(deliverables), key=lambda pair: sort_key(pair[1], pair[0]))
        last = ordered[-1][1]
        label = last.get("id") or "(没有 id)"
        if not (last.get("next_step") or "").strip():
            items.append(_violation(
                "AP-09", rule["name"], "fail",
                f"末页 {label} 没有 next_step——看完七张图的人是最热的一批，"
                "末页不给具体动作，这批人就散掉了（「欢迎咨询」不是落点）"))

    return items


def check_cover(data: dict, rules: dict, styles: dict) -> list:
    """AP-01 / AP-02 / AP-03：封面层面的判据。"""
    items = []
    by_id = rules_by_id(rules)
    deliverables = data.get("deliverables") or []
    deck = data.get("deck") if isinstance(data.get("deck"), dict) else {}
    covers = [item for item in deliverables if is_cover(item)]

    if not covers:
        return items

    # AP-01 · 封面标题长度
    rule = by_id.get("AP-01")
    if rule:
        for item in covers:
            label = item.get("id") or "(没有 id)"
            headline = ((item.get("cover_text") or {}).get("headline") or "").strip()
            if not headline:
                continue  # 缺 headline 由 validate_image_brief.py 拦，这里不重复报
            length = len(re.sub(r"\s+", "", headline))
            verdict = _range(length, rule["value"], rule["value"]["unit"])
            if verdict:
                severity, message = verdict
                items.append(_violation("AP-01", rule["name"], severity,
                                        f"{label}: 标题「{headline}」{message}"))

    # AP-02 / AP-03 · 视觉承载体
    carrier_rule = by_id.get("AP-02")
    complexity_rule = by_id.get("AP-03")
    style_id = deck.get("style_id") or (covers[0].get("style_id") if covers else None)
    carrier = (styles.get(style_id) or {}).get("carrier") if style_id else None

    for item in covers:
        label = item.get("id") or "(没有 id)"
        base_image = (item.get("base_image") or "").strip()

        if carrier == "base_image" and not base_image and carrier_rule:
            items.append(_violation(
                "AP-02", carrier_rule["name"], "fail",
                f"{label}: 风格 {style_id!r} 的 carrier 是 base_image，但封面没有 base_image——"
                "一张只有底色的封面，在信息流里和一块空白没有区别"))

        if base_image and not item.get("base_image_rights"):
            items.append(_violation(
                "AP-02", carrier_rule["name"] if carrier_rule else "AP-02", "fail",
                f"{label}: base_image 没写权利状态（base_image_rights）——"
                "底图大概率不是自己拍的，进产物就要登记来源"))

    return items


def check_complexity(metrics: dict, rules: dict) -> list:
    """AP-03：拿实测数字比阈值。只有渲染出来的封面才跑这一条。"""
    rule = rules_by_id(rules).get("AP-03")
    if not rule or not metrics:
        return []

    items = []
    spec = rule["value"]
    for name, key in (("色数", "distinct_colors"), ("边缘密度", "edge_density")):
        value = metrics.get(key)
        if value is None:
            continue
        narrowed = {
            "hard_min": spec.get(f"{key}_hard_min"),
            "target_min": spec.get(f"{key}_target_min"),
        }
        narrowed = {k: v for k, v in narrowed.items() if v is not None}
        verdict = _range(value, narrowed, "")
        if verdict:
            severity, message = verdict
            items.append(_violation(
                "AP-03", rule["name"], severity,
                f"{Path(metrics.get('path', '?')).name}: {name} {message}"
                f"（实测阈值未经校准，见 appeal-rules.json 的 calibrated: false）"))
    return items


def check_copy(data: dict, rules: dict) -> list:
    """AP-08 · 文案机器化模式。复用文章线的词表，不另写一份。"""
    rule = rules_by_id(rules).get("AP-08")
    if not rule:
        return []

    texts = _copy_texts(data.get("deliverables") or [])
    hits = []
    for text in texts:
        for finding in check_authorial.scan_gate_d([text]):
            for hit in finding["hits"]:
                # 只拦高置信度。中等置信度的（模糊权威）可能是作者的真实转述。
                if hit.get("confidence") == "high":
                    hits.append(hit)

    if hits:
        shown = "；".join(f"{hit['pattern']}「{hit['excerpt']}」" for hit in hits[:5])
        return [_violation(
            "AP-08", rule["name"], "fail",
            f"文案里有 {len(hits)} 处机器化模式：{shown}"
            "——「无 AI 味」不是感觉，这四类是无歧义的机器残留")]
    return []


def check_points(data: dict, rules: dict) -> list:
    """AP-07 · 单页并列要点上限。

    只数不判内容。要点写得好不好，机器答不了；「一页放了几条」它答得了。
    超过三条，读者一眼扫不完，就变成「要读」——而读者不读。
    """
    rule = rules_by_id(rules).get("AP-07")
    if not rule:
        return []

    limit = rule["value"]["max"]
    items = []
    for item in data.get("deliverables") or []:
        points = item.get("points") or []
        if len(points) > limit:
            label = item.get("id") or "(没有 id)"
            items.append(_violation(
                "AP-07", rule["name"], "fail",
                f"{label}: 一页并列 {len(points)} 条要点，超过上限 {limit} 条——"
                "一眼扫不完就变成「要读」，而读者不会读"))
    return items


def check(data: dict, rules: dict = None, styles: dict = None, metrics: dict = None) -> list:
    """跑全部机器判据，返回带严重度的条目。不过滤——过滤交给 `failures()`。"""
    rules = rules or load_rules()
    styles = styles if styles is not None else load_styles()
    items = []
    items.extend(check_deck(data, rules, styles))
    items.extend(check_cover(data, rules, styles))
    items.extend(check_points(data, rules))
    items.extend(check_copy(data, rules))
    items.extend(check_complexity(metrics or {}, rules))
    return items


def failures(items: list) -> list:
    return [item for item in items if item["severity"] == "fail"]


def resolve_metrics(brief_path: Path, data: dict, project: Path):
    """找出封面的底图并量它。没有底图或文件不在，返回 None。

    **量的是底图，不是合成后的成品卡。** 理由有两条：
    一、AP-03 问的是「这张底图够不够实」，量底图才问对了对象；
    二、成品卡上叠了文字，文字的边缘会把数字抬上去，
        于是「底图是一块纯色」这个事实被自己的标题掩盖了。

    没有底图时返回 None 而不是报错——底图还没生成是正常状态，
    那种情况的缺陷由 AP-02 报（缺承载体），不在这里重复。
    """
    if project is None:
        return None
    covers = [item for item in data.get("deliverables") or [] if is_cover(item)]
    for item in covers:
        raw = (item.get("base_image") or "").strip()
        if not raw:
            continue
        root = Path(project).resolve()
        candidate = (root / raw).resolve()
        if not candidate.is_relative_to(root) or not candidate.is_file():
            continue
        return measure_card.measure(candidate)
    return None


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(description="图文吸引力的机器判据")
    parser.add_argument("brief", type=Path, help="image-brief.json")
    parser.add_argument("--json", action="store_true", help="输出机器可读结果")
    parser.add_argument("--quiet", action="store_true", help="只打印 fail")
    args = parser.parse_args(argv[1:])

    if not args.brief.is_file():
        print(f"找不到简报：{args.brief}", file=sys.stderr)
        return 2

    data = json.loads(args.brief.read_text(encoding="utf-8"))
    project = find_project_root(args.brief.parent)
    metrics = resolve_metrics(args.brief, data, project)
    items = check(data, metrics=metrics)
    bad = failures(items)

    if args.json:
        print(json.dumps({"items": items, "metrics": metrics}, ensure_ascii=False, indent=2))
    else:
        for item in items:
            if args.quiet and item["severity"] != "fail":
                continue
            mark = "FAIL" if item["severity"] == "fail" else "WARN"
            print(f"{mark} [{item['rule_id']} {item['rule_name']}] {item['message']}")
        if metrics:
            print(f"\n封面实测：色数 {metrics['distinct_colors']}、"
                  f"边缘密度 {metrics['edge_density']}、"
                  f"主色占比 {metrics['dominant_luma_ratio']}")
        if not items:
            print("机器判据全部通过。这不等于封面有吸引力——"
                  "信息缺口、意外点、情绪唤醒、信息价值、社交货币五项仍须人判并登记，"
                  "且复核人必须独立于简报作者。")

    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
