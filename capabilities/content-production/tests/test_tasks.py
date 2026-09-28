import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "scripts/validate_tasks.py"
SPEC = importlib.util.spec_from_file_location("tasks", MODULE)
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


GOOD = """---
id: sample-task
created: 2026-09-28
deliverables: [article]
stage: intake
status: needs_input
---

## 任务

写一篇讲广交会前该拍什么视频的文章。

## 待确认

## 交付

## 分发登记
"""


def write(name: str, text: str) -> Path:
    directory = Path(tempfile.mkdtemp())
    path = directory / name
    path.write_text(text, encoding="utf-8")
    return path


class TaskContractTest(unittest.TestCase):
    def test_valid_task_passes(self):
        self.assertEqual(VALIDATOR.validate(write("sample-task.md", GOOD)), [])

    def test_missing_frontmatter_is_rejected(self):
        path = write("sample-task.md", "## 任务\n\n写点什么。\n")
        self.assertIn("缺少 frontmatter", VALIDATOR.validate(path)[0])

    def test_missing_required_field_is_rejected(self):
        path = write("sample-task.md", GOOD.replace("stage: intake\n", ""))
        self.assertTrue(any("缺少 stage" in error for error in VALIDATOR.validate(path)))

    def test_id_must_match_filename(self):
        path = write("other-name.md", GOOD)
        self.assertTrue(any("与文件名不一致" in error for error in VALIDATOR.validate(path)))

    def test_unknown_stage_is_rejected(self):
        path = write("sample-task.md", GOOD.replace("stage: intake", "stage: whatever"))
        self.assertTrue(any("stage 非法值" in error for error in VALIDATOR.validate(path)))

    def test_unknown_status_is_rejected(self):
        path = write("sample-task.md", GOOD.replace("status: needs_input", "status: done"))
        self.assertEqual(VALIDATOR.validate(path), [])
        path = write("sample-task.md", GOOD.replace("status: needs_input", "status: finished"))
        self.assertTrue(any("status 非法值" in error for error in VALIDATOR.validate(path)))

    def test_unknown_deliverable_is_rejected(self):
        path = write("sample-task.md", GOOD.replace("[article]", "[podcast]"))
        self.assertTrue(any("deliverables 含非法值" in error for error in VALIDATOR.validate(path)))

    def test_multiple_deliverables_are_allowed(self):
        path = write("sample-task.md", GOOD.replace("[article]", "[article, video]"))
        self.assertEqual(VALIDATOR.validate(path), [])

    def test_missing_section_is_rejected(self):
        path = write("sample-task.md", GOOD.replace("## 交付\n", ""))
        self.assertTrue(any("## 交付" in error for error in VALIDATOR.validate(path)))

    def test_empty_task_section_is_rejected(self):
        path = write("sample-task.md", GOOD.replace(
            "写一篇讲广交会前该拍什么视频的文章。", ""))
        self.assertTrue(any("## 任务 区块是空的" in error for error in VALIDATOR.validate(path)))

    def test_template_and_readme_are_skipped(self):
        directory = Path(tempfile.mkdtemp())
        for name in ["README.md", "_template.md", "real-task.md"]:
            (directory / name).write_text(GOOD, encoding="utf-8")
        self.assertEqual([path.name for path in VALIDATOR.task_files(directory)], ["real-task.md"])

    def test_real_template_is_valid(self):
        """系统根里的模板必须自己先合法，否则用户复制出来就是错的。"""
        template = VALIDATOR.TASKS_TEMPLATE
        if not template.is_file():
            self.skipTest("模板不存在")
        text = template.read_text(encoding="utf-8")
        # 模板的 id 是占位符，校验时替换成文件名再检查
        patched = text.replace("id: replace-with-filename", "id: _template")
        path = write("_template.md", patched)
        self.assertEqual(VALIDATOR.validate(path), [])

    def test_parse_list_handles_empty_and_multiple(self):
        self.assertEqual(VALIDATOR.parse_list(""), [])
        self.assertEqual(VALIDATOR.parse_list("[article, video]"), ["article", "video"])

    def test_section_body_stops_at_next_heading(self):
        body = VALIDATOR.section_body(GOOD, "## 任务")
        self.assertIn("广交会", body)
        self.assertNotIn("## 待确认", body)


if __name__ == "__main__":
    unittest.main()
