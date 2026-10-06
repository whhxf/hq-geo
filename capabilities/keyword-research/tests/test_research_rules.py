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
SCRIPTS = SYSTEM / "capabilities" / "keyword-research" / "scripts"
VALIDATOR = SCRIPTS / "validate_research.py"
INDEXER = SCRIPTS / "library_index.py"

# 校验器在 `from library_index import ...` 里找同目录的生成器——
# 脚本直跑时 sys.path[0] 就是 scripts/，但被 importlib 加载时不是。
# 不补这一行，校验器会走进「读不到 library_index.py」的分支：
# **所有库相关检查全部静默跳过，测试还是绿的。**
sys.path.insert(0, str(SCRIPTS))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


vr = _load("validate_research", VALIDATOR)
indexer = _load("library_index", INDEXER)


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
            "clustering_basis": "task_inference",
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


LIBRARY = """---
topic: AI数字员工
covers: [AI数字员工, 数字员工]
summary: 夹具结论：聚光有量，广点通的量几乎全空
created: 2026-09-29
updated: 2026-09-29
---

### 夹具结论

- **数字**：370
- **口径**：聚光月搜索指数，不跨平台比较
- **出处**：`research/raw/2026-09-29-xhs-spotlight-ai数字员工.json`，采集于 2026-09-29
"""


class ProjectCase(unittest.TestCase):
    """在临时目录里造一个项目，把夹具写进去，跑校验器看结果。

    **夹具必须是一份完整、合法的项目**，每条测试只破坏一处。否则报错里会混进
    和这条测试无关的问题，`assertRejected` 照样通过，而它证明的是别的东西。
    """

    record: dict
    clusters: dict

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.project = Path(self._tmp.name)
        (self.project / ".hq-geo.json").write_text("{}", encoding="utf-8")
        (self.project / "research" / "raw").mkdir(parents=True)
        (self.project / "research" / "normalized").mkdir(parents=True)
        (self.project / "research" / "library").mkdir(parents=True)
        (self.project / "CLAUDE.md").write_text("# 夹具项目\n", encoding="utf-8")

        self.record = copy.deepcopy(RECORD)
        self.clusters = copy.deepcopy(CLUSTERS)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def write_library(self) -> None:
        """写一份覆盖夹具核心词的库文件，并用**真的生成器**重建索引。"""
        (self.project / "research/library/AI数字员工.md").write_text(
            LIBRARY, encoding="utf-8"
        )
        indexer.sync(self.project, str(INDEXER))

    def break_library(self) -> None:
        """库相关测试的破坏点。默认不破坏。"""

    def run_validator(self) -> list[str]:
        """写盘 → 校验 → 返回错误列表。空列表就是通过。"""
        (self.project / "research/raw/2026-09-29-xhs-spotlight-ai数字员工.json").write_text(
            json.dumps(self.record, ensure_ascii=False), encoding="utf-8"
        )
        (self.project / "research/normalized/2026-09-29-ai数字员工.clusters.json").write_text(
            json.dumps(self.clusters, ensure_ascii=False), encoding="utf-8"
        )
        self.write_library()
        self.break_library()
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


class TestClusteringBasisRules(ProjectCase):
    """聚类依据（2026-09-29 加）。

    这组断言守的是「这个簇是算出来的，还是想出来的」这个区别。
    没有它，一个靠印象分的簇和一个靠 SERP 重叠算出来的簇长得一模一样，
    下游没法判断该信到什么程度——**而两者错起来的代价完全不同**：
    算出来的错了可以重采复算，想出来的错了只能重想。
    """

    def test_cluster_without_clustering_basis_rejected(self):
        """不写依据的簇是猜的。"""
        del self.clusters["clusters"][0]["clustering_basis"]
        self.assertRejected("clustering_basis 取值非法")

    def test_unknown_clustering_basis_rejected(self):
        self.clusters["clusters"][0]["clustering_basis"] = "看起来像"
        self.assertRejected("clustering_basis 取值非法")

    def test_surface_norm_with_unrelated_keywords_rejected(self):
        """写了「词面归一」就得真是词面变体。

        这条拦的是**用最便宜的依据给自己的判断背书**——
        词面归一是纯规则、零成本、可复核，所以它听起来最硬；
        但如果拿它去背一个靠印象分的簇，就是把没做的判断伪装成做了的规则。
        """
        self.clusters["clusters"][0]["clustering_basis"] = "surface_norm"
        self.clusters["clusters"][0]["representative_keywords"] = ["AI数字员工", "数字员工"]
        self.assertRejected("词面归一只能合大小写和空格变体")

    def test_surface_norm_with_case_variants_accepted(self):
        """真的大小写变体该通过——不然这条规则就没法用了。

        注意夹具要同时给出记录里的两个变体：代表词必须在原始记录里找得到，
        所以「造一个变体词来测」是测不成的，得真采到过。
        """
        self.record["surfaces"][0]["records"].append(
            {"keyword": "ai数字员工", "monthly_search_index": 370}
        )
        self.clusters["clusters"][0]["clustering_basis"] = "surface_norm"
        self.clusters["clusters"][0]["representative_keywords"] = ["AI数字员工", "ai数字员工"]
        self.assertAccepted()

    def test_surface_norm_with_hashtag_variant_accepted(self):
        """话题标记 `#` 是书写符号，不是词的一部分。

        2026-09-29 广点通实测：以 `AI数字员工` 为种子拓出的 132 条里，
        平台把 `#AI数字员工` / `#Ai数字员工` / `#ai数字员工` 当成三个独立词返回。
        不合并的话，一次采集会凭空多出三个「不同的词」——
        **而它们和主词要的是同一件事。**
        """
        self.record["surfaces"][0]["records"].append(
            {"keyword": "#AI数字员工", "monthly_search_index": 10}
        )
        self.clusters["clusters"][0]["clustering_basis"] = "surface_norm"
        self.clusters["clusters"][0]["representative_keywords"] = ["AI数字员工", "#AI数字员工"]
        self.assertAccepted()

    def test_surface_norm_does_not_merge_by_prefix(self):
        """去 `#` 不等于去前缀——`ai智能数字员工` 不能被并进 `ai数字员工`。

        这是上一条的对照组。放宽归一规则的诱惑是把「像的」都合掉，
        这条守住边界：**加了一个字符，不代表可以把别的字符也当噪音。**
        """
        self.record["surfaces"][0]["records"].append(
            {"keyword": "ai智能数字员工", "monthly_search_index": 40}
        )
        self.clusters["clusters"][0]["clustering_basis"] = "surface_norm"
        self.clusters["clusters"][0]["representative_keywords"] = [
            "AI数字员工",
            "ai智能数字员工",
        ]
        self.assertRejected("词面归一只能合大小写和空格变体")

    def test_serp_overlap_without_evidence_rejected(self):
        """声称做了一个没做的测量，比不做更糟——不做会问人，声称了不会。"""
        self.clusters["clusters"][0]["clustering_basis"] = "serp_overlap"
        self.assertRejected("却没有 serp_evidence")

    def test_serp_overlap_without_channels_rejected(self):
        self.clusters["clusters"][0]["clustering_basis"] = "serp_overlap"
        self.clusters["clusters"][0]["serp_evidence"] = {
            "sampled_at": "2026-09-29",
            "min_jaccard": 0.20,
        }
        self.assertRejected("channels 必须是非空数组")

    def test_serp_overlap_below_threshold_without_note_rejected(self):
        """低于阈值的重叠必须解释为什么仍然合簇。

        低重叠**不是**拆簇证据（一篇内容能被多个 SERP 召回），
        所以低重叠合簇可以是正确的——但必须说明理由，
        否则就是把「内容稀缺」和「不同意图」混成了一件事。
        """
        self.clusters["clusters"][0]["clustering_basis"] = "serp_overlap"
        self.clusters["clusters"][0]["serp_evidence"] = {
            "channels": ["xhs-serp"],
            "sampled_at": "2026-09-29",
            "min_jaccard": 0.04,
        }
        self.assertRejected("却没写 note 说明为什么仍然合簇")

    def test_serp_overlap_below_threshold_with_note_accepted(self):
        """带说明的低重叠合簇是合法的——这是「内容稀缺」那条路径。"""
        self.clusters["clusters"][0]["clustering_basis"] = "serp_overlap"
        self.clusters["clusters"][0]["serp_evidence"] = {
            "channels": ["xhs-serp"],
            "sampled_at": "2026-09-29",
            "min_jaccard": 0.04,
            "note": "低重叠是内容稀缺不是不同意图：前排全是同一主题的泛化结果，平台在这个词下没有专门内容。",
        }
        self.assertAccepted()

    def test_business_potential_out_of_range_rejected(self):
        """0–3 量的是「我们的产品能不能解决这个问题」，不是量大不大。"""
        self.clusters["clusters"][0]["business_potential"] = 5
        self.assertRejected("business_potential 必须是 0–3")

    def test_business_potential_in_range_accepted(self):
        self.clusters["clusters"][0]["business_potential"] = 3
        self.assertAccepted()

    def test_boolean_business_potential_rejected(self):
        """Python 里 True == 1，不特判的话布尔值会冒充合法评分。"""
        self.clusters["clusters"][0]["business_potential"] = True
        self.assertRejected("business_potential 必须是 0–3")


class TestLibraryRules(ProjectCase):
    """调研结论库——**建了但找不到，等于没建**。

    这一组盯的不是「库文件格式对不对」，是**库能不能被找出来、结论有没有真的留下**。
    它们的失效方式全是安静的：文件都在磁盘上，一切看起来正常，
    只是下一轮没人翻开它，于是最贵的一步重付一次。
    """

    def test_missing_covers_rejected(self):
        """没有「覆盖的词」这一列，按词就搜不到——主题名和词的对应不是一对一的。"""

        def break_it() -> None:
            path = self.project / "research/library/AI数字员工.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "covers: [AI数字员工, 数字员工]\n", ""
                ),
                encoding="utf-8",
            )
            indexer.sync(self.project, str(INDEXER))

        self.break_library = break_it
        self.assertRejected("没写 covers")

    def test_index_drift_rejected(self):
        """改了库文件却没重建索引。

        **这是整组测试里最重要的一条。** 校验器如果只「检查索引格式」，
        这种漂移会全绿通过——索引格式完全合法，只是内容是旧的。
        所以它必须**按生成器重算一遍逐字比对**。
        """

        def break_it() -> None:
            path = self.project / "research/library/AI数字员工.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "夹具结论：聚光有量，广点通的量几乎全空", "改过的说明"
                ),
                encoding="utf-8",
            )
            # 故意不重建索引——那正是要拦的动作

        self.break_library = break_it
        self.assertRejected("索引和库文件不一致")

    def test_deleted_claude_block_rejected(self):
        """CLAUDE.md 里的索引块被删掉。

        块没了，库就退回成「等人想起来去翻目录」——**而想不起来翻，正是要解决的问题**。
        """

        def break_it() -> None:
            claude = self.project / "CLAUDE.md"
            text = claude.read_text(encoding="utf-8")
            start = text.index(indexer.START)
            end = text.index(indexer.END) + len(indexer.END)
            claude.write_text(text[:start] + text[end:], encoding="utf-8")

        self.break_library = break_it
        self.assertRejected("索引块和库文件不一致")

    def test_research_not_archived_rejected(self):
        """调研做完了但没入档。

        夹具的 normalized 里核心词是 `AI数字员工`；把库文件的 covers 换成不相干的词，
        模拟「采了却没留下」。**这一条比不做还糟**：不做会有人问，做了没留不会。
        """

        def break_it() -> None:
            path = self.project / "research/library/AI数字员工.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace(
                    "covers: [AI数字员工, 数字员工]", "covers: [视频画册, 产品视频]"
                ),
                encoding="utf-8",
            )
            indexer.sync(self.project, str(INDEXER))

        self.break_library = break_it
        self.assertRejected("没有任何库文件覆盖它")

    def test_library_without_research_is_accepted(self):
        """库里先攒了结论、这一轮还没做调研——不该被拦。

        **入档和采集是两件事。** 库是长期累积的，`normalized/` 是一轮一份。
        用「有没有 normalized」去要求「能不能有 library」，等于把两个生命周期绑死。
        """
        def break_it() -> None:
            # 这一轮还没落簇——库里有存量结论，新的调研还没开始
            (self.project / "research/normalized/2026-09-29-ai数字员工.clusters.json").unlink()

        self.break_library = break_it
        self.assertAccepted()


class TestEmptyProject(ProjectCase):
    def test_empty_project_passes(self):
        """空项目该是绿的——没有产物不是错误。

        建了目录但还没有任何产物时，索引没得可漂，此时判红是误报。
        """
        rep = vr.Report()
        vr.validate_project(self.project, rep)
        self.assertEqual(rep.errors, [])
        self.assertEqual(rep.checked_records, 0)


if __name__ == "__main__":
    unittest.main()
