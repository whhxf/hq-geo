#!/usr/bin/env python3
import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("quality_gate", ROOT / "test/run_quality_gate.py")
QUALITY_GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(QUALITY_GATE)


def make_package(project: Path, channel: str, idea: str, topic: str, filename: str) -> Path:
    """在临时项目里造一个渠道包目录，放进一个稿件文件。"""
    directory = project / "content/packages" / channel / idea / topic
    directory.mkdir(parents=True, exist_ok=True)
    (directory / filename).write_text("x", encoding="utf-8")
    return directory


class QualityGateTests(unittest.TestCase):
    def setUp(self):
        self.tests = [
            {"id": "project-structure", "tier": "static"},
            {"id": "feature-registry-contract", "tier": "contract"},
            {"id": "feature-test", "tier": "unit"},
        ]
        self.registry = {
            "features": [
                {"id": "alpha", "status": "implemented", "owner_paths": ["src/alpha"], "test_ids": ["feature-test"]},
                {"id": "future", "status": "planned", "owner_paths": ["src/future"], "test_ids": []},
            ],
            "frozen": [{"id": "beta", "path": "frozen/beta", "note": "n=1，恢复条件：并行创意 ≥3。"}],
        }

    def test_change_selection_keeps_base_and_impacted_tests(self):
        selected, impacted = QUALITY_GATE.select_by_changes(self.tests, self.registry, ["src/alpha/main.py"])
        self.assertEqual({item["id"] for item in selected},
                         {"project-structure", "feature-registry-contract", "feature-test"})
        self.assertEqual(impacted, ["alpha"])

    def test_unrelated_change_only_runs_base_gate(self):
        selected, impacted = QUALITY_GATE.select_by_changes(self.tests, self.registry, ["notes/private.md"])
        self.assertEqual({item["id"] for item in selected}, {"project-structure", "feature-registry-contract"})
        self.assertEqual(impacted, [])

    def test_rule_doc_change_runs_everything(self):
        selected, _ = QUALITY_GATE.select_by_changes(self.tests, self.registry, ["AGENTS.md"])
        self.assertEqual({item["id"] for item in selected}, {item["id"] for item in self.tests})

    def test_coverage_does_not_count_planned_as_implemented(self):
        coverage = QUALITY_GATE.coverage_summary(self.registry)
        self.assertEqual(coverage["implemented_or_partial"], 1)
        self.assertEqual(coverage["covered"], 1)
        self.assertEqual(coverage["planned"], 1)
        self.assertEqual(coverage["frozen"], 1)
        self.assertEqual(coverage["coverage_percent"], 100.0)

    def test_channel_package_counts_directory_not_filename(self):
        """渠道包按目录数，不按文件名。

        回归：这里曾经只数 `copy.md`——那个口径建立在「主稿固定住 blog/」的旧假设上，
        数的是「派生了几个其他渠道版本」。站 5 把主稿路径改成按渠道参数化之后，
        主稿住进目标渠道目录，这个口径就数不到它了：项目里明明有一个 `toutiao` 渠道包，
        门禁却报「渠道包: 1 → 0」。

        所以三种包都要能数到：只有主稿的、只有派生版本的、两者都有的。
        """
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            make_package(project, "toutiao", "idea-a", "does-video-help", "article.md")
            make_package(project, "xhs", "idea-a", "does-video-help", "copy.md")
            make_package(project, "douyin", "idea-a", "does-video-help", "article.md")
            (project / "content/packages/douyin/idea-a/does-video-help/copy.md").write_text(
                "x", encoding="utf-8")
            # 空目录不是渠道包——没有稿件就没有产出
            (project / "content/packages/blog/empty-idea/empty-topic").mkdir(parents=True)

            metrics = QUALITY_GATE.output_metrics(project)
            self.assertEqual(metrics["channel_packages"], 3)
            self.assertEqual(metrics["articles"], 2)

    def test_channel_package_drops_when_removed(self):
        """删掉一个渠道包，数字必须跟着掉——否则「产出变少判 FAIL」这条信号是空的。"""
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            directory = make_package(
                project, "toutiao", "idea-a", "does-video-help", "article.md")
            self.assertEqual(QUALITY_GATE.output_metrics(project)["channel_packages"], 1)

            (directory / "article.md").unlink()
            self.assertEqual(QUALITY_GATE.output_metrics(project)["channel_packages"], 0)


if __name__ == "__main__":
    unittest.main()
