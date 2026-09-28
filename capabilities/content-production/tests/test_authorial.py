import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "scripts/check_authorial.py"
SPEC = importlib.util.spec_from_file_location("authorial", MODULE)
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


def scan(text: str) -> dict:
    """跑一遍完整检查，不落盘。"""
    with tempfile.NamedTemporaryFile("w", suffix=".md", encoding="utf-8", delete=False) as handle:
        handle.write(text)
        path = Path(handle.name)
    try:
        return CHECKER.check(path)
    finally:
        path.unlink()


def patterns(report: dict) -> list:
    return [hit["pattern"] for item in report["gate_d"] for hit in item["hits"]]


def words(report: dict) -> list:
    return [hit["word"] for item in report["gate_c"] for hit in item["hits"]]


class GateCTest(unittest.TestCase):
    def test_degree_word_is_reported(self):
        self.assertIn("非常", words(scan("这个方案非常值得推进，我们先做一版看看。")))

    def test_effect_word_without_evidence_is_reported(self):
        self.assertIn("全面", words(scan("系统全面提升客户的沟通效率。")))

    def test_cliche_phrase_is_reported(self):
        self.assertIn("深度赋能", words(scan("我们深度赋能外贸企业的内容生产。")))

    def test_repeated_hedges_in_one_paragraph_are_reported(self):
        found = [hit for hit in scan("这个结果可能通常相对稳定，但不一定。")["gate_c"]
                 for hit in hit["hits"] if hit["category"] == "重复限定"]
        self.assertTrue(found)

    def test_single_hedge_is_not_reported(self):
        categories = [hit["category"] for hit in
                      [h for item in scan("这个结果可能稳定。")["gate_c"] for h in item["hits"]]]
        self.assertNotIn("重复限定", categories)

    def test_plain_sentence_has_no_findings(self):
        report = scan("采购商先看产线，再看检测报告。两样都没有时，报价单没有意义。")
        self.assertEqual(report["gate_c"], [])


class GateDTest(unittest.TestCase):
    def test_not_x_but_y_is_reported_with_high_confidence(self):
        report = scan("这不是成本问题，而是流程问题。")
        hits = [hit for item in report["gate_d"] for hit in item["hits"]]
        self.assertTrue(any(hit["pattern"] == "不是 X 而是 Y" and hit["confidence"] == "high"
                            for hit in hits))

    def test_negation_then_turn_is_reported(self):
        self.assertIn("先否定再转折", patterns(scan("优势不是形容词。优势应该是一段能复述的证据。")))

    def test_chat_residue_is_reported(self):
        self.assertIn("聊天残留", patterns(scan("值得注意的是，这个结论有前提。")))
        self.assertIn("聊天残留", patterns(scan("希望对你有帮助。")))
        self.assertIn("聊天残留", patterns(scan("综上所述，我们先做最小版本。")))

    def test_abstract_upgrade_is_reported(self):
        self.assertIn("无依据升维", patterns(scan("本质上，这是一次渠道迁移。")))

    def test_vague_authority_is_reported(self):
        self.assertIn("模糊权威", patterns(scan("研究表明，采购商更关注交期。")))
        self.assertIn("模糊权威", patterns(scan("数据显示，这个品类的需求在上升。")))

    def test_rhetorical_question_is_reported(self):
        self.assertIn("替读者提问", patterns(scan("你有没有想过，客户为什么不回复？")))

    def test_plain_sentence_has_no_pattern_findings(self):
        self.assertEqual(scan("采购商先看产线，再看检测报告。")["gate_d"], [])

    def test_negation_without_turn_is_not_reported(self):
        # 真实的否定句不该被误判为机器化模式
        self.assertEqual(scan("视频画册不是新的流量渠道。")["gate_d"], [])


class StructureTest(unittest.TestCase):
    def test_frontmatter_is_stripped(self):
        report = scan("---\ntitle: 非常测试\n---\n\n正文写得很具体。")
        self.assertEqual(report["gate_c"], [])

    def test_code_block_is_stripped(self):
        report = scan("正文。\n\n```\n非常 显著 深度赋能\n```\n")
        self.assertEqual(report["gate_c"], [])

    def test_headings_are_not_scanned(self):
        report = scan("## 全面提升客户效率\n\n这一段说的是具体动作。")
        self.assertEqual(report["gate_c"], [])

    def test_paragraph_numbers_skip_headings(self):
        report = scan("## 标题\n\n第一段非常具体。")
        self.assertEqual(report["gate_c"][0]["paragraph"], 1)

    def test_rhythm_counts_sentences_and_paragraphs(self):
        stats = scan("第一句。第二句。\n\n第二段只有一句。")["rhythm"]
        self.assertEqual(stats["sentences"], 3)
        self.assertEqual(stats["paragraphs"], 2)

    def test_rhythm_handles_single_sentence(self):
        self.assertIn("note", scan("只有一句话。")["rhythm"])


class ContractTest(unittest.TestCase):
    def test_gate_e_is_reported_as_blocked(self):
        self.assertTrue(scan("正文。")["gate_e"].startswith("blocked"))

    def test_report_is_json_serialisable(self):
        import json
        json.dumps(scan("非常 显著 本质上。"), ensure_ascii=False)

    def test_render_does_not_claim_pass_or_fail(self):
        text = CHECKER.render(scan("非常。"))
        self.assertNotIn("通过", text.replace("没有命中不代表通过", ""))
        self.assertIn("不判定成败", text)


if __name__ == "__main__":
    unittest.main()
