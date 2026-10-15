#!/usr/bin/env python3
import importlib.util
import json
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


def make_marker(project: Path, baseline: dict, note=None) -> None:
    """写一个项目标记。note 为 None 时不写 output_baseline_note。"""
    descriptor = {"schema_version": 1, "slug": "tmp", "output_baseline": baseline}
    if note is not None:
        descriptor["output_baseline_note"] = note
    (project / ".hq-geo.json").write_text(
        json.dumps(descriptor, ensure_ascii=False), encoding="utf-8")


def zero_metrics() -> dict:
    return {key: 0 for key in QUALITY_GATE.LABELS}


def compare(project: Path, metrics: dict) -> tuple:
    return QUALITY_GATE.compare_baseline(
        metrics, {"passed": 0, "total": 0, "coverage": {"coverage_percent": 100.0}}, project)


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

    def test_canary_data_and_reports_do_not_force_full_run(self):
        """改一条破坏点、或报告重新生成，不该把门禁拖成全量。

        2026-10-11 实测：`--changed --list` 永远列出全部 26 条。
        规则是「`test/` 下一律全量」，而 `test/canary.json` 与
        `test/reports/` 都在 `test/` 下——快通道等于没有。
        这两个都不是门禁的输入：前者只被 canary 工具读，后者是产物。
        """
        base = {"project-structure", "feature-registry-contract"}
        # 路径不写真实项目 slug——`project-structure` 会扫 test/ 下有没有项目标识。
        for path in ("test/canary.json", "test/reports/_system/latest.json"):
            selected, _ = QUALITY_GATE.select_by_changes(self.tests, self.registry, [path])
            self.assertEqual({item["id"] for item in selected}, base, path)

    def test_gate_own_input_still_runs_everything(self):
        """门禁自己的输入一改，仍然全量——这一边保守优先。

        宁可多跑，也不让一个新加的测试文件悄悄不被跑。
        """
        everything = {item["id"] for item in self.tests}
        for path in ("test/test_manifest.json", "test/feature_registry.json",
                     "test/suites/test_canary.py", "test/tools/canary.py"):
            selected, _ = QUALITY_GATE.select_by_changes(self.tests, self.registry, [path])
            self.assertEqual({item["id"] for item in selected}, everything, path)

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

    def test_topic_packages_without_idea_directory_are_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            package = project / "content/packages/wechat/topic"
            package.mkdir(parents=True)
            (package / "article.md").write_text("real draft", encoding="utf-8")
            brief = project / "content/briefs/topic"
            brief.mkdir(parents=True)
            (brief / "production-brief.json").write_text("{}", encoding="utf-8")
            metrics = QUALITY_GATE.output_metrics(project)
            self.assertEqual(metrics["articles"], 1)
            self.assertEqual(metrics["channel_packages"], 1)
            self.assertEqual(metrics["production_briefs"], 1)

    def test_all_zero_baseline_without_note_blocks(self):
        """空实例层不许 PASS。

        回归：一个刚建的项目，产出基准六项全是 0，实际产出也是 0——门禁报
        「产出 6 项与基准一致」，然后 PASS。零等于零不是合规，是漏记：
        它让一个什么都没产出的目录看起来通过了流程。
        要么写真值，要么在 note 里说明为什么是 0。
        """
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            make_marker(project, zero_metrics())
            lines, regressed, unexplained = compare(project, zero_metrics())
            self.assertTrue(unexplained)
            self.assertFalse(regressed)
            self.assertTrue(any("output_baseline_note" in line for line in lines))

    def test_all_zero_baseline_with_note_passes(self):
        """写明原因的全零基线可以过——新项目还没有产物是正常的，漏记才不正常。"""
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            make_marker(project, zero_metrics(), note="新项目，还没有产物。")
            lines, regressed, unexplained = compare(project, zero_metrics())
            self.assertFalse(unexplained)
            self.assertFalse(regressed)
            self.assertFalse(any("output_baseline_note" in line for line in lines))

    def test_blank_note_does_not_count(self):
        """note 是空白字符串不算说明。空格不等于写了原因。"""
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            make_marker(project, zero_metrics(), note="   \n")
            _, _, unexplained = compare(project, zero_metrics())
            self.assertTrue(unexplained)

    def test_non_zero_baseline_needs_no_note(self):
        """只有全零基线才要求说明。有产出的项目不用解释。"""
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            baseline = zero_metrics()
            baseline["tasks"] = 3
            make_marker(project, baseline)
            _, regressed, unexplained = compare(project, baseline)
            self.assertFalse(unexplained)
            self.assertFalse(regressed)


if __name__ == "__main__":
    unittest.main()
