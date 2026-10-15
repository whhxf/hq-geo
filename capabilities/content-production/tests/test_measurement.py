import contextlib
import importlib.util
import io
import re
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CompareHumanAiTest(unittest.TestCase):
    """句级倍率测量：compare_human_ai.py。"""

    def setUp(self):
        self.mod = load("compare_human_ai")

    def test_dash_is_measured(self):
        hits, _, _ = self.mod.measure(["这句话——有一个破折号。"])
        self.assertEqual(hits["破折号"][1], 1)

    def test_plain_sentence_has_no_dash(self):
        hits, _, _ = self.mod.measure(["这句话没有标点。"])
        self.assertEqual(hits["破折号"][1], 0)

    def test_measure_reports_document_count_and_all_rules(self):
        hits, _, count = self.mod.measure(["第一句。第二句。"])
        self.assertEqual(count, 1)
        self.assertIn("翻案腔", hits)
        self.assertIn("破折号", hits)

    def test_args_split_human_and_ai(self):
        human, ai = self.mod.parse_args(["--human", "/a", "/b", "--ai", "/c"])
        self.assertEqual(human, ["/a", "/b"])
        self.assertEqual(ai, ["/c"])


class StructureTest(unittest.TestCase):
    """段级结构测量：check_structure.py。"""

    def setUp(self):
        self.mod = load("check_structure")

    def test_paragraph_filter_drops_headings(self):
        found = self.mod.paragraphs("## 标题\n\n这一段足够长可以算作段落。")
        self.assertEqual(len(found), 1)

    def test_isomorphic_detects_same_skeleton(self):
        para = "用户反馈很好，团队效率提升了。开发方向定了，交付节奏稳了。"
        self.assertGreater(self.mod.isomorphic(para, 2), 0)

    def test_varied_sentences_are_not_isomorphic(self):
        para = "上线之后用户反馈非常好。接下来，团队把下一步的优化方向确定下来。"
        self.assertEqual(self.mod.isomorphic(para, 2), 0)

    def test_zero_subject_comment_is_measured(self):
        stats = self.mod.measure(["这是第一个段落，写得很具体。\n\n听起来像功能描述，其实换了更根本的东西。"])
        self.assertGreater(stats["段首零主语评论/非首段%"], 0)

    def test_comment_with_anaphor_is_not_counted(self):
        stats = self.mod.measure(["这是第一个段落，写得很具体。\n\n这听起来像功能描述，其实换了更根本的东西。"])
        self.assertEqual(stats["段首零主语评论/非首段%"], 0)


class TranslationeseTest(unittest.TestCase):
    """翻译腔频率测量：check_translationese.py。"""

    def setUp(self):
        self.mod = load("check_translationese")

    def test_all_markers_compile(self):
        for name, pattern in {**self.mod.MARKERS, **self.mod.BASELINE}.items():
            re.compile(pattern)
            self.assertTrue(name)

    def test_main_reads_markdown_corpus(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "sample.md").write_text(
                "当所有人都能用 AI 写文章时，内容不再是优势。", encoding="utf-8")
            argv = sys.argv
            sys.argv = ["check_translationese.py", tmp]
            buffer = io.StringIO()
            try:
                with contextlib.redirect_stdout(buffer):
                    self.mod.main()
            finally:
                sys.argv = argv
            self.assertIn("语料 1 篇", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
