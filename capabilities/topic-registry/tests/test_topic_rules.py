#!/usr/bin/env python3
"""选题记录校验器与迁移脚本的回归测试。

选题记录是「想法」和「生产」之间的那道闸。闸松了，后果不是报错——
是**没答过五问的想法被登记成选题，然后按选题去写稿**，
写出来的东西没人能判断对不对，也没人知道它当初凭什么被选中。

这些断言盯的就是那道闸还在不在。
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

SYSTEM = Path(__file__).resolve().parents[3]
SCRIPTS = SYSTEM / "capabilities" / "topic-registry" / "scripts"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


vt = _load("validate_topics", SCRIPTS / "validate_topics.py")
mv = _load("migrate_v1", SCRIPTS / "migrate_v1.py")


FIVE = {
    "audience_and_scene": "做外贸的中小企业老板，在展会上被同行用 AI 抢了询盘。",
    "failing_explanation": "现有文章都在讲「AI 很重要」，没讲清第一步该做什么。",
    "own_judgment": "我们服务过 30 家工厂，知道卡点不在技术，在没人定义岗位。",
    "content_promise": "看完能列出自己公司最该先交给 AI 的三个岗位。",
    "falsification": "如果读者照着做完，三个月内没有一个岗位跑起来，这条就是错的。",
}


def imported_topic(tid: str = "T-01") -> dict:
    return {
        "id": tid,
        "title": "AI 数字员工到底是什么",
        "source": {
            "kind": "imported",
            "imported_from": "topics.v1.json",
            "imported_at": "2026-09-29",
        },
        "state": "candidate",
    }


def research_topic(tid: str = "T-01", ref: str = "research/normalized/a.clusters.json") -> dict:
    topic = {
        "id": tid,
        "title": "AI 数字员工到底是什么",
        "source": {
            "kind": "research",
            "research_ref": ref,
            "cluster_ref": "concept-and-role-awareness",
        },
        "evidence_refs": ["research/normalized/a.clusters.json#concept-and-role-awareness"],
        "state": "candidate",
    }
    topic.update(FIVE)
    return topic


class RegistryCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.project = Path(self._tmp.name)
        (self.project / ".hq-geo.json").write_text("{}", encoding="utf-8")
        (self.project / "research" / "normalized").mkdir(parents=True)
        (self.project / "research/normalized/a.clusters.json").write_text("{}", encoding="utf-8")
        self.registry = {
            "schema_version": 2,
            "idea_id": "ai-employee",
            "selected_topic_id": None,
            "topics": [imported_topic()],
        }

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def run_validator(self) -> list[str]:
        path = self.project / "topics" / "ai-employee" / "topics.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.registry, ensure_ascii=False), encoding="utf-8")
        rep = vt.Report()
        vt.validate_project(self.project, rep)
        return rep.errors

    def assertRejected(self, needle: str) -> None:
        errors = self.run_validator()
        self.assertTrue(errors, "这份选题记录该被拦下，却通过了校验")
        joined = "\n".join(errors)
        self.assertIn(needle, joined, f"报错里没提到 {needle!r}：\n{joined}")

    def assertAccepted(self) -> None:
        errors = self.run_validator()
        self.assertEqual(errors, [], "合法记录被误拦：\n" + "\n".join(errors))


class TestFiveQuestions(RegistryCase):
    def test_valid_imported_candidate_passes(self):
        self.assertAccepted()

    def test_half_answered_rejected(self):
        """半答比不答更危险——看起来像验证过了。"""
        self.registry["topics"][0].update(
            {k: FIVE[k] for k in list(FIVE)[:2]}
        )
        self.assertRejected("五问答了一半")

    def test_selected_without_five_questions_rejected(self):
        """答不上第 5 问的不是选题，是想法。"""
        self.registry["topics"][0]["state"] = "selected"
        self.assertRejected("五问没答全就进了 selected")

    def test_selected_with_all_five_passes(self):
        topic = research_topic()
        topic["state"] = "selected"
        self.registry["topics"] = [topic]
        self.registry["selected_topic_id"] = "T-01"
        self.assertAccepted()


class TestSources(RegistryCase):
    def test_imported_with_answers_rejected(self):
        """答全五问说明它已经被讨论过，不该还挂着 imported 的标签。"""
        self.registry["topics"][0].update(FIVE)
        self.assertRejected("来源是 imported，却答了五问")

    def test_imported_cannot_be_selected(self):
        self.registry["topics"][0]["state"] = "selected"
        self.assertRejected("state 只能是 candidate")

    def test_imported_without_provenance_rejected(self):
        del self.registry["topics"][0]["source"]["imported_from"]
        self.assertRejected("source.imported_from 必填")

    def test_research_without_ref_rejected(self):
        topic = research_topic()
        del topic["source"]["research_ref"]
        self.registry["topics"] = [topic]
        self.assertRejected("source.research_ref 必填")

    def test_research_ref_pointing_nowhere_rejected(self):
        topic = research_topic(ref="research/normalized/不存在.json")
        self.registry["topics"] = [topic]
        self.assertRejected("指向的文件不存在")

    def test_research_without_cluster_ref_rejected(self):
        topic = research_topic()
        del topic["source"]["cluster_ref"]
        self.registry["topics"] = [topic]
        self.assertRejected("source.cluster_ref 必填")

    def test_research_without_evidence_refs_rejected(self):
        """没有出处的选题和拍脑袋没有区别。"""
        topic = research_topic()
        del topic["evidence_refs"]
        self.registry["topics"] = [topic]
        self.assertRejected("evidence_refs 不能为空")

    def test_direct_without_confirmed_at_rejected(self):
        topic = research_topic()
        topic["source"] = {"kind": "direct"}
        self.registry["topics"] = [topic]
        self.assertRejected("source.confirmed_at 必填")

    def test_direct_with_bad_date_rejected(self):
        topic = research_topic()
        topic["source"] = {"kind": "direct", "confirmed_at": "2026/09/29"}
        self.registry["topics"] = [topic]
        self.assertRejected("必须是 YYYY-MM-DD")


class TestLayerSeparation(RegistryCase):
    def test_progress_fields_rejected(self):
        """选题记录只管「做不做」，不管「做到哪了」。"""
        for field in vt.FORBIDDEN_FIELDS:
            with self.subTest(field=field):
                topic = imported_topic()
                topic[field] = "canonical"
                self.registry["topics"] = [topic]
                self.assertRejected(f"不该有 {field!r}")

    def test_v1_schema_version_rejected(self):
        self.registry["schema_version"] = 1
        self.assertRejected("schema_version 必须是 2")

    def test_dangling_selected_topic_id_rejected(self):
        self.registry["selected_topic_id"] = "T-99"
        self.assertRejected("指向不存在的选题")


class TestStructure(RegistryCase):
    def test_duplicate_id_rejected(self):
        self.registry["topics"] = [imported_topic("T-01"), imported_topic("T-01")]
        self.assertRejected("id 重复")

    def test_empty_title_rejected(self):
        self.registry["topics"][0]["title"] = ""
        self.assertRejected("title 不能为空")

    def test_backup_file_is_skipped(self):
        """迁移脚本写的备份不是现行数据，不该被当成选题校验。

        2026-09-29 踩过：备份被 glob 命中，产生 638 处假报错，
        全是 v1 的 stage/progress——**旧格式留在这里是为了回溯，不是为了被校验**。
        """
        backup = self.project / "topics" / "ai-employee" / "topics.v1.bak.json"
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "idea_id": "ai-employee",
                    "topics": [{"id": "T-01", "title": "旧", "stage": "canonical"}],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self.assertAccepted()

    def test_empty_project_passes(self):
        rep = vt.Report()
        vt.validate_project(self.project, rep)
        self.assertEqual(rep.errors, [])


class TestMigration(unittest.TestCase):
    V1 = {
        "schema_version": 1,
        "idea_id": "video-album",
        "imported_at": "2026-09-29T10:00:00",
        "topics": [
            {
                "id": "P1-06",
                "title": "画册做完了没人看",
                "stage": "canonical",
                "artifacts": ["母脚本", "渠道版本"],
                "source_status": "待验证",
                "platforms": ["三平台待适配"],
            },
            {
                "id": "G1-02",
                "title": "展会现场怎么用画册",
                "stage": "topic_ready",
                "platforms": ["小红书"],
            },
        ],
    }

    def test_all_topics_become_candidate(self):
        """推进得深不等于验证过——五问没答，就只能停在 candidate。"""
        out = mv.migrate_registry(copy.deepcopy(self.V1), ["topics.v1.json"])
        self.assertEqual([t["state"] for t in out["topics"]], ["candidate", "candidate"])
        self.assertEqual(out["selected_topic_id"], None)
        self.assertEqual(out["schema_version"], 2)

    def test_progress_fields_stripped(self):
        out = mv.migrate_registry(copy.deepcopy(self.V1), ["topics.v1.json"])
        for topic in out["topics"]:
            for field in mv.PROGRESS_FIELDS:
                self.assertNotIn(field, topic)

    def test_progress_recorded_in_note(self):
        """删掉不等于没发生——原值摘要进 note，将来能回溯。"""
        out = mv.migrate_registry(copy.deepcopy(self.V1), ["topics.v1.json"])
        note = out["topics"][0]["note"]
        self.assertIn("stage=canonical", note)
        self.assertIn("母脚本", note)
        self.assertIn("待验证", note)

    def test_placeholder_platforms_emptied(self):
        """「三平台待适配」不是平台名，是「还没判断」。"""
        out = mv.migrate_registry(copy.deepcopy(self.V1), ["topics.v1.json"])
        self.assertEqual(out["topics"][0]["platforms"], [])
        self.assertEqual(out["topics"][1]["platforms"], ["小红书"], "真实平台名要保留")

    def test_migrated_registry_passes_validator(self):
        """迁移的产物必须过得了校验器——迁移脚本不该产出违规数据。"""
        out = mv.migrate_registry(copy.deepcopy(self.V1), ["topics.v1.json"])
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / ".hq-geo.json").write_text("{}", encoding="utf-8")
            path = project / "topics" / "video-album" / "topics.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")

            rep = vt.Report()
            vt.validate_project(project, rep)
            self.assertEqual(rep.errors, [], "\n".join(rep.errors))
            self.assertEqual(rep.checked, 2)


if __name__ == "__main__":
    unittest.main()
