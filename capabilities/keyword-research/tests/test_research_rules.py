#!/usr/bin/env python3
"""关键词研究校验器的回归测试。

这些断言盯的不是「代码跑得通」，是**那六条拦截还在不在**。
校验器松一格，后果不是报错，是**编出来的词进了需求簇，然后被当成证据写进内容**——
一路静默，直到有人拿着那条内容去问客户，客户说「我们没这么说过」。

每条测试都是「故意造一份违规记录，看它会不会被拦下」。
它们全部为绿时才有意义；要证明它们不是空转的，跑 `test/tools/canary.py`。
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
VALIDATOR = SYSTEM / "capabilities" / "keyword-research" / "scripts" / "validate_research.py"


def _load_validator():
    spec = importlib.util.spec_from_file_location("validate_research", VALIDATOR)
    module = importlib.util.module_from_spec(spec)
    sys.modules["validate_research"] = module
    spec.loader.exec_module(module)
    return module


vr = _load_validator()


# --- 夹具：一份合法的记录 + 一份合法的需求簇 ---------------------------------

RECORD = {
    "schema_version": 1,
    "channel": "xhs-spotlight",
    "platform": "小红书",
    "captured_at": "2026-09-29",
    "core_keyword": "AI数字员工",
    "access": "login_required",
    "evidence_nature": "official_commercial",
    "surfaces": [
        {
            "surface": "词根拓词",
            "records": [
                {
                    "keyword": "AI数字员工",
                    "competition": "高",
                    "monthly_search_index": 370,
                    "bid_cny": 7.86,
                },
                {
                    "keyword": "数字员工",
                    "competition": "高",
                    "monthly_search_index": 3146,
                    "bid_cny": 2.43,
                },
            ],
        },
        {
            "surface": "用户路径拓词",
            "records": [
                {
                    "keyword": "数字员工",
                    "path": "企业数字化转型路径",
                    "path_share_percent": 100,
                },
            ],
        },
    ],
    "noise": [
        {"keyword": "geo", "why": "指数 56,839，量很大但与「AI 数字员工」不是同一个任务。"}
    ],
    "notes": ["搜索指数、竞争指数、市场出价分别保存，不做加总。"],
}

CLUSTERS = {
    "schema_version": 1,
    "core_keyword": "AI数字员工",
    "produced_at": "2026-09-29",
    "stage": "keyword_to_keyword",
    "source_records": ["research/raw/2026-09-29-xhs-spotlight-ai数字员工.json"],
    "clusters": [
        {
            "cluster_id": "concept-and-role-awareness",
            "priority": "P0",
            "name": "概念与岗位认知",
            "representative_keywords": ["AI数字员工", "数字员工"],
            "index_range": "<100–3,146",
            "user_task": "先弄懂它是什么",
            "judgment": "商业意图强但规模窄",
            "evidence_grade": "direct_platform",
            "evidence_refs": ["research/raw/2026-09-29-xhs-spotlight-ai数字员工.json#词根拓词"],
        }
    ],
    "excluded": [{"what": "数字人制作", "why": "与「能执行企业任务的数字员工」不是同一产品。"}],
    "inferred_keywords": [
        {
            "keyword": "AI客服数字员工",
            "why_inferred": "由「搭建与选型」簇推导的具体岗位词，平台上没有独立数据。",
            "needs_verification_at": ["xhs-spotlight"],
        }
    ],
    "gates": {
        "D_需求": {"score": 2, "grade": "direct_platform", "note": "至少三个长尾指向同一任务。"}
    },
    "evidence_ledger": [
        {
            "conclusion": "AI数字员工 370 / 高竞争 / 7.86 元",
            "grade": "direct_platform",
            "source": "小红书聚光词根拓词",
            "date": "2026-09-29",
        }
    ],
    "next_action": "把核心词换为一个明确业务结果词。",
}


class ProjectCase(unittest.TestCase):
    """在临时目录里造一个项目，把夹具写进去，跑校验器看结果。"""

    record: dict
    clusters: dict

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.project = Path(self._tmp.name)
        (self.project / ".hq-geo.json").write_text("{}", encoding="utf-8")
        (self.project / "research" / "raw").mkdir(parents=True)
        (self.project / "research" / "normalized").mkdir(parents=True)

        self.record = copy.deepcopy(RECORD)
        self.clusters = copy.deepcopy(CLUSTERS)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def run_validator(self) -> list[str]:
        """写盘 → 校验 → 返回错误列表。空列表就是通过。"""
        (self.project / "research/raw/2026-09-29-xhs-spotlight-ai数字员工.json").write_text(
            json.dumps(self.record, ensure_ascii=False), encoding="utf-8"
        )
        (self.project / "research/normalized/2026-09-29-ai数字员工.clusters.json").write_text(
            json.dumps(self.clusters, ensure_ascii=False), encoding="utf-8"
        )
        rep = vr.Report()
        vr.validate_project(self.project, rep)
        return rep.errors

    def assertRejected(self, needle: str) -> None:
        errors = self.run_validator()
        self.assertTrue(errors, "这份产物该被拦下，却通过了校验")
        joined = "\n".join(errors)
        self.assertIn(needle, joined, f"报错里没提到 {needle!r}：\n{joined}")

    def assertAccepted(self) -> None:
        errors = self.run_validator()
        self.assertEqual(errors, [], "合法产物被误拦：\n" + "\n".join(errors))


# --- 渠道定义 ---------------------------------------------------------------


class TestChannelDefinitions(unittest.TestCase):
    def test_channels_loaded_and_readme_skipped(self):
        channels = vr.load_channels()
        self.assertIn("xhs-spotlight", channels)
        self.assertNotIn("README", channels, "README.md 是接口说明，不是渠道")

    def test_front_matter_parsed(self):
        fm = vr._read_front_matter(
            SYSTEM / "capabilities/keyword-research/channels/xhs-spotlight.md"
        )
        self.assertEqual(fm.get("channel"), "xhs-spotlight")
        self.assertEqual(fm.get("access"), "login_required")
        self.assertEqual(fm.get("evidence_nature"), "official_commercial")
        self.assertEqual(fm.get("status"), "verified")

    def test_collect_keywords_includes_noise(self):
        """噪音词也算「出现过」——它被明确排除了，不是不存在。"""
        found = vr._collect_keywords(RECORD)
        self.assertIn("AI数字员工", found)
        self.assertIn("geo", found, "噪音词也要算进词面，否则代表词核对的基数是错的")


# --- 六条拦截 ---------------------------------------------------------------


class TestRecordRules(ProjectCase):
    def test_valid_fixture_passes(self):
        """夹具本身必须合法——否则后面每条断言都可能是被夹具带红的。"""
        self.assertAccepted()

    def test_unknown_channel_rejected(self):
        self.record["channel"] = "xhs-juguang"
        self.assertRejected("没有定义")

    def test_access_mismatch_rejected(self):
        self.record["access"] = "public"
        self.assertRejected("与渠道定义不一致")

    def test_evidence_nature_mismatch_rejected(self):
        self.record["evidence_nature"] = "native_content"
        self.assertRejected("与渠道定义不一致")

    def test_record_without_any_signal_rejected(self):
        """只有词没有数的是手打清单，不是采集结果。"""
        self.record["surfaces"][0]["records"] = [{"keyword": "AI数字员工"}]
        self.assertRejected("没有任何信号字段")

    def test_threshold_string_is_a_legitimate_value(self):
        """平台报「<100」时照抄。

        换算成 100 是编数，换成 null 是丢信息。谁把这里收紧成整数，
        就是在逼采集的人编一个数出来——这条断言守的是那个自由度。
        """
        self.record["surfaces"][0]["records"][0]["monthly_search_index"] = "<100"
        self.assertAccepted()

    def test_noise_without_why_rejected(self):
        self.record["noise"] = [{"keyword": "geo"}]
        self.assertRejected("必须写 why")

    def test_missing_required_field_rejected(self):
        del self.record["evidence_nature"]
        self.assertRejected("缺必填项 evidence_nature")


class TestClusterRules(ProjectCase):
    def test_fabricated_representative_keyword_rejected(self):
        """编词——本能力包最核心的一条拦截。"""
        self.clusters["clusters"][0]["representative_keywords"] = ["AI数字员工", "AI数字员工多少钱一个月"]
        self.assertRejected("在 source_records 里找不到")

    def test_inferred_keyword_used_as_representative_rejected(self):
        """推断冒充证据：推断词不能当代表词。"""
        self.clusters["clusters"][0]["representative_keywords"] = ["AI数字员工", "AI客服数字员工"]
        self.assertRejected("是推断词，不能当代表词")

    def test_inference_cluster_with_index_rejected(self):
        self.clusters["clusters"][0]["evidence_grade"] = "inference"
        self.assertRejected("推断出来的簇没有指数")

    def test_cluster_without_evidence_refs_rejected(self):
        del self.clusters["clusters"][0]["evidence_refs"]
        self.assertRejected("evidence_refs 不能为空")

    def test_missing_source_record_file_rejected(self):
        self.clusters["source_records"] = ["research/raw/不存在.json"]
        self.assertRejected("指向的文件不存在")

    def test_inferred_keyword_without_verification_target_rejected(self):
        del self.clusters["inferred_keywords"][0]["needs_verification_at"]
        self.assertRejected("去哪个渠道验证")

    def test_excluded_without_why_rejected(self):
        self.clusters["excluded"] = [{"what": "数字人制作"}]
        self.assertRejected("排除项必须写 why")

    def test_ledger_without_date_rejected(self):
        del self.clusters["evidence_ledger"][0]["date"]
        self.assertRejected("date 必须是 YYYY-MM-DD")

    def test_gate_without_note_rejected(self):
        """只给分不给理由，分数会被当成结论。"""
        del self.clusters["gates"]["D_需求"]["note"]
        self.assertRejected("闸门必须写 note")

    def test_duplicate_cluster_id_rejected(self):
        self.clusters["clusters"].append(copy.deepcopy(self.clusters["clusters"][0]))
        self.assertRejected("cluster_id 重复")


class TestEmptyProject(ProjectCase):
    def test_empty_project_passes(self):
        """空项目该是绿的——没有产物不是错误。"""
        rep = vr.Report()
        vr.validate_project(self.project, rep)
        self.assertEqual(rep.errors, [])
        self.assertEqual(rep.checked_records, 0)


if __name__ == "__main__":
    unittest.main()
