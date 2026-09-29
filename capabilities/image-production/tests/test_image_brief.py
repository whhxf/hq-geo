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


def valid_brief() -> dict:
    """最小合法图片简报。"""
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
                "status": "planned",
            }
        ],
    }


def run(brief: dict) -> list:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "image-brief.json"
        path.write_text(json.dumps(brief, ensure_ascii=False), encoding="utf-8")
        return BRIEF.validate(path, STYLE_IDS)


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
        brief = valid_brief()
        brief["status"] = "ready_for_production"
        brief["deliverables"][0]["status"] = "blocked"
        self.assertTrue(any("blocked" in error for error in run(brief)))

    def test_empty_deliverables_is_rejected(self):
        brief = valid_brief()
        brief["deliverables"] = []
        self.assertTrue(any("deliverables" in error for error in run(brief)))


class AssemblePromptTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
