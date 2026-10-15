#!/usr/bin/env python3
"""图片简报校验器和 prompt 组装的单元测试。

测试用合成对象，不依赖任何具体项目，也不联网。

这里守的核心是一条：**图不能冒充它没有的东西。**
一张看起来像产品界面的生成图，读者没有任何办法知道那是模型编的——
文章写错一句话能被追问出处，图不能。所以这条必须由字段强制，不能靠自觉。
"""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def _load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BRIEF = _load("validate_image_brief", "capabilities/image-production/scripts/validate_image_brief.py")
GEN = _load("generate_image", "capabilities/image-production/scripts/generate_image.py")

STYLE_IDS = {"editorial-minimal", "japanese-fresh"}
# 风格库里出现过的文案位置。测试里写死，是为了不跟着风格库一起漂。
LAYOUTS = {"bottom-left", "top-left"}


def valid_brief() -> dict:
    """最小合法图片简报。

    `author` 与 `base_image` 是 2026-10-08 起的最低要求：前者用于要求
    复核人独立（写的人不能自己判吸引力），后者用于要求封面有视觉承载体
    （只有底色的封面在信息流里和一块空白没有区别）。
    """
    return {
        "schema_version": 1,
        "id": "img-001",
        "topic_id": "topic-001",
        "title": "示例",
        "status": "draft",
        "objective": "让读者看懂这件事",
        "audience": "运营负责人",
        "core_thesis": "AI 数字员工不是替代人",
        "fact_refs": ["F-001"],
        "platform": "xhs",
        "prohibited_claims": ["不承诺具体增效数字"],
        "acceptance_criteria": ["图上文字无错别字"],
        "author": "写简报的人",
        "deliverables": [
            {
                "id": "d1",
                "role": "封面",
                "size": "1024*1024",
                "subject": "米白色桌面上一本摊开的笔记本",
                "subject_kind": "concept",
                "synthetic": True,
                "source_assets": [{"kind": "ai_generated", "path": "-", "rights": "模型生成，无第三方权利"}],
                "style_id": "editorial-minimal",
                "base_image": "assets/generated/img-001/cover.png",
                "base_image_rights": "ai_generated：本项目生成",
                "status": "planned",
            }
        ],
    }


def cover_text(**overrides) -> dict:
    text = {
        "headline": "把线收进一个盒子",
        "source_title": "把线收进一个盒子",
        "layout": "bottom-left",
    }
    text.update(overrides)
    return {key: value for key, value in text.items() if value is not None}


def appeal_review(**verdict_overrides) -> dict:
    verdicts = {key: "pass" for key in BRIEF.APPEAL_DIMENSIONS}
    verdicts.update(verdict_overrides)
    return {
        "reviewed_by": "Conan",
        "reviewed_at": "2026-10-08",
        "evidence": "把封面缩到 240px 宽，和信息流前 20 条并排看了一遍",
        "verdicts": verdicts,
    }


def ready_brief() -> dict:
    """进了 ready 的简报：封面有文案，吸引力复核九项全过。"""
    brief = valid_brief()
    brief["status"] = "ready_for_production"
    brief["deliverables"][0]["cover_text"] = cover_text()
    brief["appeal_review"] = appeal_review()
    return brief


def two_card_brief() -> dict:
    """两张图的组。四格 deck、序号、封面隔离、末页落点全部合规。

    它存在的理由是：组层面的四条判据（风格 / 隔离 / 序号 / 落点）
    单张图一条都测不出来。
    """
    brief = valid_brief()
    brief["deck"] = {
        "style_id": "editorial-minimal",
        "sequence_total": 2,
        "cover_theme": "dark",
        "inner_theme": "light",
    }
    brief["deliverables"][0]["sequence"] = "01/02"
    inner = dict(brief["deliverables"][0])
    inner.update({
        "id": "d2",
        "role": "内页",
        "sequence": "02/02",
        "next_step": "把这七条存下来，下次比价时逐条对",
        "status": "planned",
    })
    inner.pop("cover_text", None)
    brief["deliverables"].append(inner)
    return brief


def run(brief: dict) -> list:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "image-brief.json"
        path.write_text(json.dumps(brief, ensure_ascii=False), encoding="utf-8")
        return BRIEF.validate(path, STYLE_IDS, layout_ids=LAYOUTS)


class ValidateTests(unittest.TestCase):
    def test_valid_brief_passes(self):
        self.assertEqual(run(valid_brief()), [])

    def test_missing_fact_refs_is_rejected(self):
        """没有事实引用的图片简报不能成立——那等于允许凭空画。"""
        brief = valid_brief()
        brief["fact_refs"] = []
        self.assertTrue(any("fact_refs" in error for error in run(brief)))

    def test_generated_image_claiming_to_be_product_ui_is_rejected(self):
        """声称是产品界面的图，不允许是模型生成的。

        这是 AGENTS.md「禁止用生成图冒充产品事实」的机器执行版本。
        模型画出来的界面是幻觉——按钮位置、字段名全是编的，
        而看图的人会以为那是真的产品。
        """
        brief = valid_brief()
        brief["deliverables"][0]["subject_kind"] = "product_ui"
        brief["deliverables"][0]["synthetic"] = True
        errors = run(brief)
        self.assertTrue(any("synthetic 必须显式为 false" in error for error in errors), errors)

    def test_real_screenshot_with_real_kind_is_accepted(self):
        """真实的截图配真实题材，合法——红线拦的是冒充，不是生成。"""
        brief = valid_brief()
        item = brief["deliverables"][0]
        item["subject_kind"] = "product_ui"
        item["synthetic"] = False
        item["source_assets"] = [
            {"kind": "real_screenshot", "path": "assets/shot.png", "rights": "自有产品截图"}
        ]
        self.assertEqual(run(brief), [])

    def test_missing_synthetic_flag_is_rejected(self):
        """synthetic 缺省就是没声明——不声明不算数。"""
        brief = valid_brief()
        del brief["deliverables"][0]["synthetic"]
        self.assertTrue(any("synthetic 必须显式写" in error for error in run(brief)))

    def test_claim_on_image_without_fact_ref_is_rejected(self):
        """图上写的字和正文一样要能被追问出处。"""
        brief = valid_brief()
        brief["deliverables"][0]["claims_on_image"] = [{"text": "效率提升 300%"}]
        errors = run(brief)
        self.assertTrue(any("没挂 fact_ref" in error for error in errors), errors)

    def test_asset_without_rights_is_rejected(self):
        """素材权利状态不能空——出事了要能说清这张图哪来的。"""
        brief = valid_brief()
        brief["deliverables"][0]["source_assets"] = [
            {"kind": "real_photo", "path": "assets/p.jpg", "rights": ""}
        ]
        self.assertTrue(any("没写权利状态" in error for error in run(brief)))

    def test_unknown_style_id_is_rejected(self):
        """风格 id 拼错不会报错，只会静默出一张没有风格的图。

        这条是 2026-09-28「数据在库里但页面是空的」那类静默失败的图片版。
        """
        brief = valid_brief()
        brief["deliverables"][0]["style_id"] = "editorial-minmal"
        errors = run(brief)
        self.assertTrue(any("不在风格库里" in error for error in errors), errors)

    def test_ready_brief_with_blocked_deliverable_is_rejected(self):
        brief = ready_brief()
        brief["deliverables"][0]["status"] = "blocked"
        self.assertTrue(any("blocked" in error for error in run(brief)))

    def test_empty_deliverables_is_rejected(self):
        brief = valid_brief()
        brief["deliverables"] = []
        self.assertTrue(any("deliverables" in error for error in run(brief)))


class CoverTextTests(unittest.TestCase):
    """封面文字：两类文字分开走，封面不许是空的。

    2026-10-07 Conan 问「封面怎么一个字都没有」。查清是三重封锁——契约要求
    图上每句话都挂 `fact_ref`，而封面标题是文章的题目、挂不上，于是封面被迫无字。
    这组测试守的是：**那道被打开的门不许变成后门。**
    """

    def test_cover_without_cover_text_at_ready_is_rejected(self):
        brief = valid_brief()
        brief["status"] = "ready_for_production"
        errors = run(brief)
        self.assertTrue(any("封面没有封面文案" in error for error in errors), errors)

    def test_cover_without_cover_text_on_draft_is_fine(self):
        """草案阶段还没有文案是正常的——缺料停机不是一开始就拦。"""
        self.assertEqual(run(valid_brief()), [])

    def test_cover_text_without_source_title_is_rejected(self):
        """封面文案不挂事实，但必须写清取自哪条标题——否则它没人认领。"""
        brief = valid_brief()
        brief["deliverables"][0]["cover_text"] = {"headline": "把线收进一个盒子"}
        self.assertTrue(any("缺 source_title" in error for error in run(brief)))

    def test_cover_text_with_blank_headline_is_rejected(self):
        brief = valid_brief()
        brief["deliverables"][0]["cover_text"] = cover_text(headline="   ")
        self.assertTrue(any("headline 是空的" in error for error in run(brief)))

    def test_cover_text_without_style_is_rejected(self):
        """文案要按风格排版，没有风格就没有排版规则，字会随便压。"""
        brief = valid_brief()
        brief["deliverables"][0]["cover_text"] = cover_text()
        del brief["deliverables"][0]["style_id"]
        self.assertTrue(any("必须有 style_id" in error for error in run(brief)))

    def test_cover_text_layout_outside_style_library_is_rejected(self):
        """文案压住主体，是封面最常见的废掉方式。"""
        brief = valid_brief()
        brief["deliverables"][0]["cover_text"] = cover_text(layout="middle-right")
        errors = run(brief)
        self.assertTrue(any("不在风格库出现过的位置里" in error for error in errors), errors)

    def test_same_sentence_as_cover_text_and_claim_is_rejected(self):
        """同一句话只能走一条路——否则「挂没挂 fact_ref」这个信号就失真了。"""
        brief = valid_brief()
        brief["deliverables"][0]["cover_text"] = cover_text(headline="台词截图拼接")
        brief["deliverables"][0]["claims_on_image"] = [
            {"text": "台词截图拼接", "fact_ref": "F-001"}
        ]
        errors = run(brief)
        self.assertTrue(any("同时出现在" in error for error in errors), errors)


class AppealReviewTests(unittest.TestCase):
    """吸引力复核：人判，但必须登记，判的人还不能是写的人，九项全过才许进 ready。

    这一格是图片线**求好**那条腿的判据。它没有机器判据，所以校验器不假装能判，
    只守三件机器能守的事：该有复核的时候有没有、有没有留下未决的判断、
    复核人是不是独立于写的人。
    """

    def test_ready_with_cover_text_but_no_review_is_rejected(self):
        brief = ready_brief()
        del brief["appeal_review"]
        errors = run(brief)
        self.assertTrue(any("appeal_review 缺失" in error for error in errors), errors)

    def test_review_without_reviewer_is_rejected(self):
        """没有复核人和日期，就没有复核。"""
        brief = ready_brief()
        brief["appeal_review"]["reviewed_by"] = ""
        self.assertTrue(any("缺 reviewed_by" in error for error in run(brief)))

    def test_review_with_unknown_dimension_is_rejected(self):
        """unknown 等于没复核。"""
        brief = ready_brief()
        brief["appeal_review"]["verdicts"]["scannable_in_feed"] = "unknown"
        self.assertTrue(any("还是 unknown" in error for error in run(brief)))

    def test_review_with_failed_dimension_is_rejected(self):
        """有一项没过，封面就还不该进 ready——先改封面，再复核。"""
        brief = ready_brief()
        brief["appeal_review"]["verdicts"]["same_direction_as_title"] = "fail"
        errors = run(brief)
        self.assertTrue(any("还不该进 ready" in error for error in errors), errors)

    def test_full_pass_review_is_accepted(self):
        """正例：封面有文案、复核九项全过——这才叫 ready。

        只有反例的测试，把「永远红」的实现也能测绿。
        """
        self.assertEqual(run(ready_brief()), [])

    def test_draft_with_cover_text_does_not_require_review(self):
        """复核是交付前的动作，不是写作前的。"""
        brief = valid_brief()
        brief["deliverables"][0]["cover_text"] = cover_text()
        self.assertEqual(run(brief), [])

    def test_all_nine_dimensions_are_required(self):
        """九项缺一不可。缺的那项必须被点名，不能被静默放过。"""
        for key in BRIEF.APPEAL_DIMENSIONS:
            brief = ready_brief()
            del brief["appeal_review"]["verdicts"][key]
            self.assertTrue(any(f"缺 {key}" in error for error in run(brief)),
                            f"缺 {key} 没被拦下")

    def test_psychological_dimensions_are_covered(self):
        """2026-10-08 补的五项必须在 APPEAL_DIMENSIONS 里。

        少一项，对应的那条人判规则就没有承载字段——判了也没地方写。
        """
        expected = {
            "information_gap", "unexpectedness", "emotional_arousal",
            "practical_value", "social_currency",
        }
        self.assertTrue(expected.issubset(set(BRIEF.APPEAL_DIMENSIONS)),
                        f"少了：{sorted(expected - set(BRIEF.APPEAL_DIMENSIONS))}")


class ReviewerIndependenceTests(unittest.TestCase):
    """写简报的人不能自己判吸引力。

    2026-10-08 的事故：写简报的 Agent 自己把四项全填了 pass，十张图交付，
    Conan 看完说「比较素，让人没啥阅读兴趣」。**复核登记了，质量没守住。**
    机器判不了「有没有人愿意看」，但它能要求判的人不是写的人。
    """

    def test_reviewer_equal_to_author_is_rejected(self):
        brief = ready_brief()
        brief["appeal_review"]["reviewed_by"] = brief["author"]
        errors = run(brief)
        self.assertTrue(any("写简报的人不能自己判" in error for error in errors), errors)

    def test_independent_reviewer_is_accepted(self):
        """正例：复核人不是作者，且写清了实际看过什么。"""
        brief = ready_brief()
        brief["author"] = "Agent"
        brief["appeal_review"]["reviewed_by"] = "Conan"
        self.assertEqual(run(brief), [])

    def test_missing_evidence_is_rejected(self):
        """写不出实际看过什么，这份复核就是照着模板填的。"""
        brief = ready_brief()
        del brief["appeal_review"]["evidence"]
        self.assertTrue(any("缺 evidence" in error for error in run(brief)))

    def test_blank_evidence_is_rejected(self):
        brief = ready_brief()
        brief["appeal_review"]["evidence"] = "   "
        self.assertTrue(any("缺 evidence" in error for error in run(brief)))


class DeckTests(unittest.TestCase):
    """整组图的四格。四条组层面判据都挂在它上面。

    这一格是 2026-10-08 补的。之前简报只描述单张图，没有「组」的概念——
    全套共用一个风格、封面从内页里隔离出来、序号与总数、末页落点，
    这四条单看任何一张都看不出问题。
    """

    def test_multi_image_brief_without_deck_is_rejected(self):
        brief = two_card_brief()
        del brief["deck"]
        errors = run(brief)
        self.assertTrue(any("deck 缺失" in error for error in errors), errors)

    def test_single_image_brief_needs_no_deck(self):
        """单张图没有「组」可言——不强制，宪法 8：默认减法。"""
        self.assertEqual(run(valid_brief()), [])

    def test_each_deck_field_is_required(self):
        for key in ("style_id", "sequence_total", "cover_theme", "inner_theme"):
            brief = two_card_brief()
            del brief["deck"][key]
            self.assertTrue(any(f"deck 缺 {key}" in error for error in run(brief)),
                            f"deck 缺 {key} 没被拦下")

    def test_theme_enum_is_closed(self):
        brief = two_card_brief()
        brief["deck"]["cover_theme"] = "米白"
        self.assertTrue(any("cover_theme 取值非法" in error for error in run(brief)))

    def test_sequence_total_must_be_at_least_two(self):
        brief = two_card_brief()
        brief["deck"]["sequence_total"] = 1
        self.assertTrue(any("≥2 的整数" in error for error in run(brief)))

    def test_compliant_two_card_deck_passes(self):
        """正例：两卡的组，四格齐全、序号对得上、末页有落点。"""
        self.assertEqual(run(two_card_brief()), [])


class BaseImageTests(unittest.TestCase):
    """封面底图的路径与存在性。

    AP-02 要求封面有 `base_image`，但**写了不等于有**：路径拼错、忘了生成、
    文件被挪走，三种情况都会让封面渲染成一块空白底——**那正好是
    「图比较素」这个缺陷换个方式回来。**
    """

    def test_base_image_without_rights_is_rejected(self):
        brief = valid_brief()
        del brief["deliverables"][0]["base_image_rights"]
        self.assertTrue(any("base_image_rights" in error for error in run(brief)))

    def test_base_image_outside_project_root_is_rejected(self):
        """单测里没有项目根，所以只测「越界」这一条在真实项目根下的表现。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".hq-geo.json").write_text("{}")
            brief_dir = root / "content" / "briefs" / "b1"
            brief_dir.mkdir(parents=True)
            brief = valid_brief()
            brief["deliverables"][0]["base_image"] = "../../../etc/passwd"
            path = brief_dir / "image-brief.json"
            path.write_text(json.dumps(brief, ensure_ascii=False), encoding="utf-8")
            errors = BRIEF.validate(path, STYLE_IDS, root, layout_ids=LAYOUTS)
            self.assertTrue(any("指向项目根之外" in error for error in errors), errors)

    def test_generated_deliverable_with_missing_base_image_is_rejected(self):
        """声明已生成，文件却不在——封面会渲染成一块空白底，而简报看上去是合规的。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".hq-geo.json").write_text("{}")
            brief_dir = root / "content" / "briefs" / "b1"
            brief_dir.mkdir(parents=True)
            brief = valid_brief()
            brief["deliverables"][0]["status"] = "generated"
            path = brief_dir / "image-brief.json"
            path.write_text(json.dumps(brief, ensure_ascii=False), encoding="utf-8")
            errors = BRIEF.validate(path, STYLE_IDS, root, layout_ids=LAYOUTS)
            self.assertTrue(any("声明为已生成，但文件不在" in error for error in errors), errors)

    def test_planned_deliverable_may_lack_the_base_image_file(self):
        """正例：planned 的图还没出，底图当然还不在。"""
        self.assertEqual(run(valid_brief()), [])


class AssemblePromptTests(unittest.TestCase):
    def test_base_image_prefix_overrides_title_generation_instruction(self):
        style = {'prompt': {'prefix': '大号中文标题', 'base_image_prefix': '米白纸底与几何卡片', 'negative': ''}}
        result = GEN.assemble_prompt({'subject': '五张空白纸卡'}, style)
        self.assertNotIn('大号中文标题', result['prompt'])
        self.assertIn('米白纸底', result['prompt'])
        self.assertIn('任何文字', result['negative_prompt'])

    STYLE = {
        "prompt": {"prefix": "极简杂志编辑排版风格", "negative": "复杂背景"},
        "image_style_enum": "flat-illustration",
    }

    def test_style_comes_first(self):
        """风格必须在最前面。放后面会被画面描述盖过去，一套图就漂成十四种样子。"""
        prompt = GEN.assemble_prompt(
            {"subject": "米白色桌面", "intent": "标题居左"}, self.STYLE
        )
        self.assertTrue(prompt["prompt"].startswith("极简杂志编辑排版风格"))
        self.assertLess(prompt["prompt"].index("米白色桌面"), prompt["prompt"].index("标题居左"))

    def test_avoid_is_appended_to_negative(self):
        prompt = GEN.assemble_prompt({"subject": "桌面", "avoid": "不要出现真人"}, self.STYLE)
        self.assertIn("复杂背景", prompt["negative_prompt"])
        self.assertIn("不要出现真人", prompt["negative_prompt"])

    def test_missing_intent_does_not_leave_blank_line(self):
        prompt = GEN.assemble_prompt({"subject": "桌面"}, self.STYLE)
        self.assertNotIn("\n\n", prompt["prompt"])


class ImageUrlsTests(unittest.TestCase):
    """新旧两种响应格式都要认。

    只认新格式的话，DashScope 换响应结构时会静默返回空列表——
    然后你会以为「模型没出图」，其实是解析没跟上。
    """

    def test_new_format(self):
        payload = {"output": {"choices": [{"message": {"content": [{"image": "https://a/1.png"}]}}]}}
        self.assertEqual(GEN.image_urls(payload), ["https://a/1.png"])

    def test_legacy_format(self):
        payload = {"output": {"results": [{"url": "https://a/2.png"}]}}
        self.assertEqual(GEN.image_urls(payload), ["https://a/2.png"])

    def test_empty_output_is_empty_list(self):
        self.assertEqual(GEN.image_urls({"output": {}}), [])


class GenerationEntrySafetyTest(unittest.TestCase):
    def test_real_screenshot_cannot_be_sent_to_model(self):
        with self.assertRaisesRegex(ValueError, '真实'):
            GEN.check_generation_target({'subject_kind': 'product_ui', 'synthetic': False, 'status': 'planned'})

    def test_blocked_and_untyped_targets_fail(self):
        for item in ({}, {'subject_kind': 'concept', 'synthetic': True, 'status': 'blocked'}):
            with self.assertRaises(ValueError):
                GEN.check_generation_target(item)

    def test_concept_generation_is_allowed(self):
        GEN.check_generation_target({'subject_kind': 'concept', 'synthetic': True, 'status': 'planned'})

if __name__ == "__main__":
    unittest.main()
