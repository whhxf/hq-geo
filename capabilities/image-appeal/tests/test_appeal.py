#!/usr/bin/env python3
"""图文吸引力判据的单元测试。

三组：

1. **测量器**：把「素」变成数字的那三个数，行为对不对。
   最关键的一条是**判别力**——一张「纯底色加一小块字」的图必须低于阈值，
   一张有内容层次的图必须高于阈值。测不出这个差别，判据就是装饰。
2. **判据**：十四条规则各自的正反例。每条都要有一个**通过**的例子，
   只测反面会把「永远报错」当成「守住了」。
3. **规则真源**：十四条都在、每条有来源、来源有证据等级和采集日期、
   机器判与人判两边都不为空。来源丢了，判据就退化成审美。

全部用标准库。测试自己造 PNG，不依赖任何外部素材。
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

SYSTEM = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(SYSTEM))
sys.path.insert(0, str(SYSTEM / "capabilities/image-production/scripts"))
sys.path.insert(0, str(SYSTEM / "capabilities/image-appeal/scripts"))

import png_io  # noqa: E402
import measure_card  # noqa: E402
import check_appeal  # noqa: E402

RULES_PATH = SYSTEM / "capabilities/image-appeal/rules/appeal-rules.json"

# 四条 AP-0x 判据的 id。少一条就是少一道拦截。
RULE_IDS = [f"AP-{n:02d}" for n in range(1, 15)]

WHITE = (250, 248, 243)
DARK = (43, 41, 38)
ORANGE = (226, 96, 58)


# ---------- 造图 ----------

def write_pixels(path, width, height, sampler):
    """`sampler(x, y)` 返回 (r, g, b)。逐像素，只给测试用。"""
    pixels = bytearray()
    for y in range(height):
        for x in range(width):
            pixels += bytes(sampler(x, y))
    png_io.write_png(path, width, height, pixels)


def flat_png(path, width=200, height=200, color=WHITE):
    write_pixels(path, width, height, lambda x, y: color)


def text_like_png(path, width=200, height=200):
    """纯底色加一小块字。这就是被否的那十张卡的形状。"""
    def sampler(x, y):
        if 60 <= x < 140 and 90 <= y < 110:
            return DARK
        return WHITE
    write_pixels(path, width, height, sampler)


def noisy_png(path, width=200, height=200):
    """确定性伪随机噪声，代表「有内容层次」的画面。不用 random，保证可复算。"""
    state = {"seed": 12345}

    def sampler(x, y):
        state["seed"] = (state["seed"] * 1103515245 + 12345) & 0x7FFFFFFF
        value = (state["seed"] >> 16) & 0xFF
        return (value, (value * 7) % 256, (value * 13) % 256)
    write_pixels(path, width, height, sampler)


def striped_png(path, width=200, height=200):
    write_pixels(path, width, height,
                 lambda x, y: DARK if (x // 2) % 2 == 0 else WHITE)


# ---------- 简报骨架 ----------

def base_brief(**overrides):
    """一份全部合规的简报。各测试从它出发，只改要测的那一格。"""
    brief = {
        "schema_version": 1,
        "id": "demo",
        "topic_id": "demo-topic",
        "title": "示例",
        "status": "draft",
        "objective": "示例",
        "audience": "示例",
        "core_thesis": "示例",
        "fact_refs": ["fact-1"],
        "platform": "xhs",
        "prohibited_claims": [],
        "acceptance_criteria": ["示例"],
        "author": "写简报的人",
        "deck": {
            "style_id": "editorial-minimal",
            "sequence_total": 3,
            "cover_theme": "dark",
            "inner_theme": "light",
        },
        "deliverables": [
            {
                "id": "01-cover",
                "role": "cover 封面",
                "size": "1080x1440",
                "subject": "示例",
                "subject_kind": "concept",
                "synthetic": True,
                "source_assets": [],
                "style_id": "editorial-minimal",
                "sequence": "01/03",
                "base_image": "assets/generated/demo/cover.png",
                "base_image_rights": "ai_generated：本项目生成",
                "cover_text": {"headline": "先问他这七个问题", "source_title": "示例"},
                "status": "generated",
            },
            {
                "id": "02-inner",
                "role": "内页",
                "size": "1080x1440",
                "subject": "示例",
                "subject_kind": "concept",
                "synthetic": True,
                "source_assets": [],
                "style_id": "editorial-minimal",
                "sequence": "02/03",
                "status": "generated",
            },
            {
                "id": "03-last",
                "role": "内页",
                "size": "1080x1440",
                "subject": "示例",
                "subject_kind": "concept",
                "synthetic": True,
                "source_assets": [],
                "style_id": "editorial-minimal",
                "sequence": "03/03",
                "next_step": "把这七条存下来，下次比价时逐条对",
                "status": "generated",
            },
        ],
    }
    brief.update(overrides)
    return brief


def failures_of(brief, metrics=None):
    return check_appeal.failures(check_appeal.check(brief, metrics=metrics))


def rule_ids_of(items):
    return {item["rule_id"] for item in items}


# ---------- 1. 测量器 ----------

class TestMeasure(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def path(self, name):
        return self.dir / name

    def test_flat_image_has_no_visual_event(self):
        """一块纯色：一个颜色、零边缘。这是「素」的极限。"""
        path = self.path("flat.png")
        flat_png(path)
        report = measure_card.measure(path)
        self.assertEqual(report["distinct_colors"], 1)
        self.assertEqual(report["edge_density"], 0.0)
        self.assertEqual(report["dominant_luma_ratio"], 1.0)
        self.assertEqual(report["luma_bands"], 1)

    def test_text_like_card_is_below_the_floor(self):
        """纯底色加一小块字 —— 必须低于 AP-03 的硬下限。

        这一条是整套判据的判别力所在。它要是红了，说明阈值把被否的那类图
        判成了合格，判据就变成了装饰。
        """
        path = self.path("text.png")
        text_like_png(path)
        report = measure_card.measure(path)
        spec = check_appeal.rules_by_id(check_appeal.load_rules())["AP-03"]["value"]
        self.assertLess(report["edge_density"], spec["edge_density_hard_min"],
                        "纯文字卡被判成合格——AP-03 失去判别力")
        self.assertLess(report["distinct_colors"], spec["distinct_colors_hard_min"],
                        "纯文字卡的色数被判成合格——AP-03 失去判别力")

    def test_noisy_image_is_above_the_floor(self):
        """有内容层次的画面 —— 必须高于硬下限。反面也要测，否则阈值可以随便定。"""
        path = self.path("noisy.png")
        noisy_png(path)
        report = measure_card.measure(path)
        spec = check_appeal.rules_by_id(check_appeal.load_rules())["AP-03"]["value"]
        self.assertGreater(report["edge_density"], spec["edge_density_hard_min"])
        self.assertGreater(report["distinct_colors"], spec["distinct_colors_hard_min"])

    def test_striped_image_has_high_edge_density(self):
        path = self.path("stripes.png")
        striped_png(path)
        self.assertGreater(measure_card.measure(path)["edge_density"], 0.4)

    def test_measurement_is_deterministic(self):
        """同输入同输出。判据拿这个数比阈值，它必须能被复算。"""
        path = self.path("noisy.png")
        noisy_png(path)
        self.assertEqual(measure_card.measure(path), measure_card.measure(path))

    def test_quantization_merges_antialiasing_noise(self):
        """相邻两级灰在 4 位量化后是同一个色 —— 抗锯齿不算视觉事件。

        这是 4 位量化的理由：不压掉它，一张纯文字图的色数会被渲染噪声撑到上千，
        阈值就没有意义了。

        **条纹周期必须是 2 而不是 1。** 测量器以 2 像素为步长抽样，
        周期 1 的条纹在采样点上永远取到同一个值——那条断言会一直绿，
        而它什么都没测。（canary 在 2026-10-08 抓到过这个。）
        """
        path = self.path("near.png")
        write_pixels(path, 200, 200, lambda x, y: (128 + ((x // 2) % 2), 128, 128))
        self.assertEqual(measure_card.measure(path)["distinct_colors"], 1)


# ---------- 2. 判据 ----------

class TestRules(unittest.TestCase):

    def setUp(self):
        self.rules = check_appeal.load_rules()
        self.styles = check_appeal.load_styles()

    def check(self, brief, metrics=None):
        return check_appeal.check(brief, rules=self.rules, styles=self.styles, metrics=metrics)

    def test_compliant_brief_passes(self):
        """正例。没有这一条，一套「永远报错」的判据也会显得在工作。"""
        self.assertEqual(failures_of(base_brief()), [])

    def test_ap01_headline_too_long_fails(self):
        brief = base_brief()
        brief["deliverables"][0]["cover_text"]["headline"] = "关于选择外贸AI服务商你必须先搞清楚的七个关键问题"
        self.assertIn("AP-01", rule_ids_of(failures_of(brief)))

    def test_ap01_headline_over_target_only_warns(self):
        """超过目标但没超硬上限 —— warn，不是 fail。"""
        brief = base_brief()
        # 16 字：在 target_max 15 之上、hard_max 23 之下。
        brief["deliverables"][0]["cover_text"]["headline"] = "先问完这七个问题再决定要不要下单"
        items = failures_of(brief)
        self.assertNotIn("AP-01", rule_ids_of(items))
        self.assertIn("AP-01", rule_ids_of(self.check(brief)))

    def test_ap01_ignores_whitespace(self):
        brief = base_brief()
        brief["deliverables"][0]["cover_text"]["headline"] = "先 问 他 这 七 个 问 题"
        self.assertNotIn("AP-01", rule_ids_of(failures_of(brief)))

    def test_ap02_base_image_carrier_needs_base_image(self):
        brief = base_brief()
        del brief["deliverables"][0]["base_image"]
        del brief["deliverables"][0]["base_image_rights"]
        self.assertIn("AP-02", rule_ids_of(failures_of(brief)))

    def test_ap02_base_image_needs_rights(self):
        brief = base_brief()
        del brief["deliverables"][0]["base_image_rights"]
        self.assertIn("AP-02", rule_ids_of(failures_of(brief)))

    def test_ap02_exempts_typography_carrier(self):
        """carrier=typography 的风格不走 AP-02 —— 否则会误伤一个合法风格。"""
        brief = base_brief()
        brief["deck"]["style_id"] = "black-gold-manifesto"
        for item in brief["deliverables"]:
            item["style_id"] = "black-gold-manifesto"
            item.pop("base_image", None)
            item.pop("base_image_rights", None)
        self.assertNotIn("AP-02", rule_ids_of(failures_of(brief)))

    def test_ap03_uses_measured_numbers(self):
        """AP-03 只吃实测数字，不吃声明。"""
        brief = base_brief()
        items = self.check(brief, metrics={
            "path": "cover.png", "distinct_colors": 40, "edge_density": 0.02})
        self.assertIn("AP-03", rule_ids_of(check_appeal.failures(items)))
        items = self.check(brief, metrics={
            "path": "cover.png", "distinct_colors": 400, "edge_density": 0.09})
        self.assertNotIn("AP-03", rule_ids_of(check_appeal.failures(items)))

    def test_ap04_cover_must_differ_from_inner(self):
        brief = base_brief()
        brief["deck"]["inner_theme"] = "dark"
        self.assertIn("AP-04", rule_ids_of(failures_of(brief)))

    def test_ap05_style_drift_fails(self):
        brief = base_brief()
        brief["deliverables"][1]["style_id"] = "dark-tech"
        self.assertIn("AP-05", rule_ids_of(failures_of(brief)))

    def test_ap05_rejects_unknown_style(self):
        brief = base_brief()
        brief["deck"]["style_id"] = "no-such-style"
        for item in brief["deliverables"]:
            item["style_id"] = "no-such-style"
        self.assertIn("AP-05", rule_ids_of(failures_of(brief)))

    def test_ap06_sequence_total_must_match(self):
        brief = base_brief()
        brief["deck"]["sequence_total"] = 7
        self.assertIn("AP-06", rule_ids_of(failures_of(brief)))

    def test_ap06_sequence_format(self):
        brief = base_brief()
        brief["deliverables"][1]["sequence"] = "第二张"
        self.assertIn("AP-06", rule_ids_of(failures_of(brief)))

    def test_ap07_too_many_points(self):
        brief = base_brief()
        brief["deliverables"][1]["points"] = ["一", "二", "三", "四"]
        self.assertIn("AP-07", rule_ids_of(failures_of(brief)))

    def test_ap07_three_points_is_fine(self):
        brief = base_brief()
        brief["deliverables"][1]["points"] = ["一", "二", "三"]
        self.assertNotIn("AP-07", rule_ids_of(failures_of(brief)))

    def test_ap08_machine_residue_in_copy(self):
        """「值得注意的是」是无歧义的机器残留 —— 必须拦。"""
        brief = base_brief()
        brief["deliverables"][1]["points"] = ["值得注意的是，报价里通常不含运费"]
        self.assertIn("AP-08", rule_ids_of(failures_of(brief)))

    def test_ap08_scans_cover_text_too(self):
        brief = base_brief()
        brief["deliverables"][0]["cover_text"]["kicker"] = "综上所述，选型要看这几点"
        self.assertIn("AP-08", rule_ids_of(failures_of(brief)))

    def test_ap08_ignores_medium_confidence(self):
        """模糊权威是中等置信度 —— 它可能是作者的真实转述，不拦。"""
        brief = base_brief()
        brief["deliverables"][1]["points"] = ["研究表明，中小外贸企业普遍缺跟进人手"]
        self.assertNotIn("AP-08", rule_ids_of(failures_of(brief)))

    def test_ap09_last_card_needs_next_step(self):
        """末页落点在 ready 时才要求——它是内容决策，不是结构。"""
        brief = base_brief(status="ready_for_review")
        del brief["deliverables"][2]["next_step"]
        self.assertIn("AP-09", rule_ids_of(failures_of(brief)))

    def test_ap09_does_not_fire_before_ready(self):
        """draft 的简报不被迫编一句落点——料还没齐，落点无从定。"""
        brief = base_brief()
        del brief["deliverables"][2]["next_step"]
        self.assertNotIn("AP-09", rule_ids_of(failures_of(brief)))

    def test_ap09_reads_the_last_card_by_sequence_not_by_order(self):
        """末页由序号决定，不由数组顺序决定。顺序错了也要抓得住。"""
        brief = base_brief(status="ready_for_review")
        brief["deliverables"][2]["next_step"] = "落点"
        brief["deliverables"].insert(0, brief["deliverables"].pop(1))
        self.assertNotIn("AP-09", rule_ids_of(failures_of(brief)))

    def test_structural_rules_fire_even_on_draft(self):
        """结构类判据任何时候都要：做法错了不是缺料，缺料停机不豁免它。"""
        brief = base_brief()
        del brief["deliverables"][0]["base_image"]
        del brief["deliverables"][0]["base_image_rights"]
        self.assertIn("AP-02", rule_ids_of(failures_of(brief)))

    def test_missing_deck_is_reported_not_skipped(self):
        """没有 deck 时必须报出来，不能静默跳过四条判据。"""
        brief = base_brief()
        del brief["deck"]
        self.assertIn("DECK", rule_ids_of(failures_of(brief)))

    def test_single_image_needs_no_deck(self):
        brief = base_brief()
        del brief["deck"]
        brief["deliverables"] = brief["deliverables"][:1]
        del brief["deliverables"][0]["sequence"]
        self.assertNotIn("DECK", rule_ids_of(failures_of(brief)))

    def test_failures_filters_warn(self):
        items = [{"rule_id": "X", "rule_name": "x", "severity": "warn", "message": ""},
                 {"rule_id": "Y", "rule_name": "y", "severity": "fail", "message": ""}]
        self.assertEqual([item["rule_id"] for item in check_appeal.failures(items)], ["Y"])

    def test_range_hard_beats_target(self):
        spec = {"hard_min": 100, "target_min": 200}
        self.assertEqual(check_appeal._range(50, spec, "")[0], "fail")
        self.assertEqual(check_appeal._range(150, spec, "")[0], "warn")
        self.assertIsNone(check_appeal._range(250, spec, ""))


# ---------- 3. 规则真源 ----------

class TestRuleSource(unittest.TestCase):

    def setUp(self):
        self.rules = check_appeal.load_rules()
        self.entries = self.rules["rules"]

    def test_all_fourteen_rules_present_in_order(self):
        self.assertEqual([rule["id"] for rule in self.entries], RULE_IDS)

    def test_every_source_has_evidence_tier_and_date(self):
        allowed = {"官方规则", "直接证据", "强代理证据", "经验模式", "推断", "未知"}
        for key, source in self.rules["sources"].items():
            for field in ("title", "evidence", "collected_at"):
                self.assertTrue(source.get(field), f"来源 {key} 缺 {field}")
            self.assertIn(source["evidence"], allowed, f"来源 {key} 的证据等级不在六档内")

    def test_every_rule_cites_an_existing_source(self):
        for rule in self.entries:
            self.assertIn(rule["source"], self.rules["sources"],
                          f"规则 {rule['id']} 引用了不存在的来源")

    def test_every_rule_has_the_required_fields(self):
        for rule in self.entries:
            for field in ("name", "scope", "checkable", "source", "why", "value"):
                self.assertIn(field, rule, f"规则 {rule['id']} 缺 {field}")
            self.assertIn(rule["checkable"], {"machine", "human"})
            self.assertIn(rule["scope"], {"cover", "page", "deck", "copy"})

    def test_both_machine_and_human_rules_exist(self):
        """全标 machine 就是把「有没有人愿意看」谎报成机器能判。"""
        kinds = {rule["checkable"] for rule in self.entries}
        self.assertEqual(kinds, {"machine", "human"})

    def test_human_rules_map_to_registered_verdicts(self):
        """每条人判规则都必须有承载字段 —— 否则判了也没地方写。"""
        schema = json.loads(
            (SYSTEM / "capabilities/image-production/contracts/image-brief.schema.json")
            .read_text(encoding="utf-8"))
        registered = set(
            schema["properties"]["appeal_review"]["properties"]["verdicts"]["required"])
        expected = {
            "information_gap", "unexpectedness", "emotional_arousal",
            "practical_value", "social_currency",
        }
        self.assertTrue(expected.issubset(registered),
                        f"人判规则没有承载字段：{sorted(expected - registered)}")

    def test_provisional_thresholds_are_marked_uncalibrated(self):
        """AP-03 的样本是 10 比 1。它必须自己说清这一点，否则会被当成合格线。"""
        self.assertIs(check_appeal.rules_by_id(self.rules)["AP-03"]["value"]["calibrated"], False)

    def test_style_library_declares_carrier(self):
        """AP-02 靠 carrier 分流。风格库少了这一格，判据就静默失效。"""
        styles = check_appeal.load_styles()
        self.assertEqual(len(styles), 15)
        for style_id, style in styles.items():
            self.assertIn(style.get("carrier"), {"base_image", "typography"},
                          f"风格 {style_id} 的 carrier 缺失或非法")
        carriers = {style["carrier"] for style in styles.values()}
        self.assertEqual(carriers, {"base_image", "typography"},
                         "两种 carrier 都要有实例，否则分流逻辑从未被走到")


if __name__ == "__main__":
    unittest.main(verbosity=2)
