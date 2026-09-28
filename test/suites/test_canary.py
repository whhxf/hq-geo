#!/usr/bin/env python3
"""canary 工具的回归测试。

canary 自己也会坏。它坏掉的方式很隐蔽：不再真的破坏被测对象，
于是每条断言都「通过」——而它本该报告的是「这条断言是空转的」。
一个坏掉的 canary 比没有 canary 更糟，它会给出虚假的信心。

2026-09-28 它真的坏过一次：只替换第一次出现，而关键词在被断言的
那一节里出现两次，9 条里 5 条被它误判为「不是空转的」。
下面第一条测试守的就是这个。
"""

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("canary", ROOT / "test/tools/canary.py")
CANARY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CANARY)


class ApplyEditsTests(unittest.TestCase):
    def test_replaces_every_occurrence_not_just_the_first(self):
        """同一个词在文件里出现两次时，两次都要换掉。

        只换第一次的话，第二次还在，断言照样绿——破坏不干净，
        canary 就会把空转的断言误报成健康的。
        """
        originals = {"doc.md": "受众坐标是产出。没有受众坐标就写不出核心判断。"}
        edits = [{"file": "doc.md", "find": "受众坐标", "replace": "读者对象"}]
        result = CANARY.apply_edits(originals, edits)
        self.assertNotIn("受众坐标", result["doc.md"])
        self.assertEqual(result["doc.md"], "读者对象是产出。没有读者对象就写不出核心判断。")

    def test_edits_across_multiple_files(self):
        """一条破坏点可以跨文件——去掉一个概念，要在它出现的每个地方都去掉。"""
        originals = {"a.md": "`dbs-jtbd`", "b.md": "`dbs-jtbd`"}
        edits = [
            {"file": "a.md", "find": "`dbs-jtbd`", "replace": "`dbs-hook`"},
            {"file": "b.md", "find": "`dbs-jtbd`", "replace": "`dbs-hook`"},
        ]
        result = CANARY.apply_edits(originals, edits)
        self.assertEqual(result["a.md"], "`dbs-hook`")
        self.assertEqual(result["b.md"], "`dbs-hook`")

    def test_does_not_mutate_the_originals(self):
        """原文必须原样保留——还原要靠它，改了就恢复不回去了。"""
        originals = {"doc.md": "受众坐标"}
        CANARY.apply_edits(originals, [{"file": "doc.md", "find": "受众坐标", "replace": "读者"}])
        self.assertEqual(originals["doc.md"], "受众坐标")


class StaleEditsTests(unittest.TestCase):
    def test_reports_edit_whose_text_is_gone(self):
        """文档改了、破坏点找不到时，必须报出来。

        不报的话这条 canary 会一直「通过」，而它其实什么都没破坏。
        """
        originals = {"doc.md": "这里没有那行字"}
        edits = [{"file": "doc.md", "find": "受众坐标", "replace": "读者"}]
        self.assertEqual(CANARY.stale_edits(originals, edits), ["doc.md"])

    def test_healthy_edit_is_not_stale(self):
        originals = {"doc.md": "受众坐标"}
        edits = [{"file": "doc.md", "find": "受众坐标", "replace": "读者"}]
        self.assertEqual(CANARY.stale_edits(originals, edits), [])


if __name__ == "__main__":
    unittest.main()
