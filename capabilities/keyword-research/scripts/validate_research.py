"""校验关键词研究的产物。

两类对象：

- `research/raw/**/*.json` —— 原始采集记录（ResearchRecord）
- `research/normalized/**/*.clusters.json` —— 需求簇（DemandCluster）

这个校验器拦的六件事：

1. **渠道名写错** —— 记录里的 `channel` 找不到对应的渠道定义
2. **记录与渠道对不上** —— `access` / `evidence_nature` 和渠道定义不一致
3. **只有词没有数** —— 一条记录除了关键词什么都没有
4. **编词** —— 需求簇的代表词在原始记录里根本不存在
5. **推断冒充证据** —— 推断词混进了代表词，或者推断簇带了指数
6. **没有出处的判断** —— 簇没有 evidence_refs、账本缺来源或日期

用法：

    python3 capabilities/keyword-research/scripts/validate_research.py --project <项目根>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SYSTEM_ROOT = Path(__file__).resolve().parents[3]
CHANNELS_DIR = SYSTEM_ROOT / "capabilities" / "keyword-research" / "channels"

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CHANNEL_ID_RE = re.compile(r"^[a-z0-9-]+$")
CLUSTER_ID_RE = re.compile(r"^[a-z0-9-]+$")

ACCESS_VALUES = {"public", "login_required", "commercial_account"}
EVIDENCE_NATURES = {
    "official_commercial",
    "official_creative",
    "native_content",
    "proxy",
}
EVIDENCE_GRADES = {
    "direct_platform",
    "official_aggregate",
    "proxy",
    "inference",
    "unknown",
}
PRIORITIES = {"P0", "P1", "P2"}
STAGES = {"keyword_to_keyword", "keyword_to_site", "complete"}
CLUSTERING_BASES = {"surface_norm", "serp_overlap", "task_inference"}

# SERP 重叠的合簇阈值。2026-09-29 实测：同词重测 0.80–0.93（这是噪声上界），
# 无关词 0.00–0.06。阈值定在「显著高于无关基线」，不是「接近同词基线」——
# 聚类的目的恰恰是把不同的词合起来，要求接近同词基线等于取消聚类。
SERP_MIN_OVERLAP = 0.15

# 一条记录里，除了 keyword 之外至少要有一个信号字段非空。
# 只有词没有数的记录不是采集结果，是手打的清单。
#
# 不同渠道的「信号」不是同一种东西：官方商业工具给指数和出价，
# 原生内容渠道给的是内容指纹（note_id）和互动量。两者都是信号，
# 都能证明「这条记录是真的采回来的」。
SIGNAL_FIELDS = (
    "monthly_search_index",
    "monthly_click_index",
    "competition",
    "bid_cny",
    "reason",
    "upstream_downstream",
    "path_share_percent",
    "note_id",
    "likes",
    "related_tabs",
)


def has_signal(rec: dict) -> bool:
    """这条记录除了 keyword 之外，有没有采到真东西。

    **空数组、空对象不算信号。** `[]` 既不等于 None 也不等于 ""，
    直接比较会把它当成有信号——那等于「我采了一个空列表」也能过。
    """
    for field in SIGNAL_FIELDS:
        value = rec.get(field)
        if value is None or value == "":
            continue
        if isinstance(value, (list, dict)) and not value:
            continue
        return True
    return False


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.checked_records = 0
        self.checked_clusters = 0

    def err(self, where: str, msg: str) -> None:
        self.errors.append(f"{where}: {msg}")

    @property
    def ok(self) -> bool:
        return not self.errors


def _read_front_matter(path: Path) -> dict[str, str]:
    """读 markdown 的 front matter。只支持 `key: value`，不引 yaml 依赖。"""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    lines = text.splitlines()
    out: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip()
    return out


def load_channels() -> dict[str, dict[str, str]]:
    """系统层的渠道定义。渠道是系统层的，不属于任何一个项目。"""
    channels: dict[str, dict[str, str]] = {}
    if not CHANNELS_DIR.is_dir():
        return channels
    for path in sorted(CHANNELS_DIR.glob("*.md")):
        if path.name == "README.md":
            continue
        fm = _read_front_matter(path)
        cid = fm.get("channel") or path.stem
        channels[cid] = fm
    return channels


def _normalize_surface(keyword: str) -> str:
    """词面归一：小写、去空白、去分隔符、去话题标记。

    **只做这些，不做同义替换。** `AI数字员工` 和 `ai数字员工` 归一后是同一个词形；
    `AI数字员工` 和 `数字员工` 归一后不是——后者要合簇得靠 SERP 重叠或任务判断，
    不能靠「看起来像」。

    `#` 算标记不算词。2026-09-29 广点通实测拓出 `#AI数字员工` / `#Ai数字员工` /
    `#ai数字员工`——同一个人搜「#ai数字员工」和搜「ai数字员工」要的是同一件事，
    平台把话题写法当成一个独立词返回而已。不合并会凭空多出三个「不同的词」。
    """
    text = keyword.lower()
    return re.sub(r"[\s\-_·、，,。.／/#]+", "", text)


def _collect_keywords(records: list[dict]) -> set[str]:
    """一份原始记录里出现过的全部词面——包括噪音词。

    噪音词也算「出现过」：它被明确排除了，不是不存在。
    """
    found: set[str] = set()
    for surface in records.get("surfaces", []):
        for rec in surface.get("records", []):
            kw = rec.get("keyword")
            if isinstance(kw, str) and kw:
                found.add(kw)
    for item in records.get("noise", []):
        kw = item.get("keyword")
        if isinstance(kw, str) and kw:
            found.add(kw)
    return found


def validate_record(path: Path, rel: str, channels: dict, rep: Report) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        rep.err(rel, f"不是合法 JSON：{exc}")
        return

    required = [
        "schema_version",
        "channel",
        "platform",
        "captured_at",
        "core_keyword",
        "access",
        "evidence_nature",
        "surfaces",
    ]
    for key in required:
        if key not in data:
            rep.err(rel, f"缺必填项 {key}")
    if rep.errors and rep.errors[-1].startswith(rel):
        # 必填项不全时后面的检查没有意义，直接返回
        return

    channel_id = data.get("channel")
    if not isinstance(channel_id, str) or not CHANNEL_ID_RE.match(channel_id):
        rep.err(rel, f"channel 不是合法的 kebab-case id：{channel_id!r}")
    elif channel_id not in channels:
        rep.err(
            rel,
            f"渠道 {channel_id!r} 没有定义。"
            f"在 capabilities/keyword-research/channels/ 建 {channel_id}.md，"
            f"或修正 channel 名——写错的渠道名不会静默通过",
        )
    else:
        definition = channels[channel_id]
        for field in ("access", "evidence_nature"):
            declared = definition.get(field)
            actual = data.get(field)
            if declared and declared != actual:
                rep.err(
                    rel,
                    f"{field} 与渠道定义不一致：记录写 {actual!r}，"
                    f"{channel_id}.md 写 {declared!r}。两处必须一致",
                )

    captured = data.get("captured_at")
    if not isinstance(captured, str) or not DATE_RE.match(captured):
        rep.err(rel, f"captured_at 必须是 YYYY-MM-DD：{captured!r}")

    if data.get("access") not in ACCESS_VALUES:
        rep.err(rel, f"access 取值非法：{data.get('access')!r}")
    if data.get("evidence_nature") not in EVIDENCE_NATURES:
        rep.err(rel, f"evidence_nature 取值非法：{data.get('evidence_nature')!r}")

    surfaces = data.get("surfaces")
    if not isinstance(surfaces, list) or not surfaces:
        rep.err(rel, "surfaces 必须是非空数组——一次采集至少要读到一个页签")
    else:
        for i, surface in enumerate(surfaces):
            recs = surface.get("records") if isinstance(surface, dict) else None
            if not isinstance(recs, list) or not recs:
                rep.err(rel, f"surfaces[{i}] 的 records 必须是非空数组")
                continue
            for j, rec in enumerate(recs):
                where = f"{rel} surfaces[{i}].records[{j}]"
                if not isinstance(rec, dict):
                    rep.err(where, "记录必须是对象")
                    continue
                kw = rec.get("keyword")
                if not isinstance(kw, str) or not kw.strip():
                    rep.err(where, "keyword 不能为空")
                if not has_signal(rec):
                    rep.err(
                        where,
                        f"记录 {kw!r} 只有关键词、没有任何信号字段。"
                        "只有词没有数的是手打清单，不是采集结果",
                    )
                rep.checked_records += 1

    for k, item in enumerate(data.get("noise", [])):
        if not isinstance(item, dict) or not item.get("why"):
            rep.err(
                f"{rel} noise[{k}]",
                "噪音词必须写 why——不写理由的排除，下次看到同一个词还要重新判断",
            )


def validate_cluster(path: Path, rel: str, rep: Report) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        rep.err(rel, f"不是合法 JSON：{exc}")
        return

    required = [
        "schema_version",
        "core_keyword",
        "produced_at",
        "stage",
        "source_records",
        "clusters",
        "excluded",
        "evidence_ledger",
    ]
    for key in required:
        if key not in data:
            rep.err(rel, f"缺必填项 {key}")
    if rep.errors and rep.errors[-1].startswith(rel):
        return

    if data.get("stage") not in STAGES:
        rep.err(rel, f"stage 取值非法：{data.get('stage')!r}")

    produced = data.get("produced_at")
    if not isinstance(produced, str) or not DATE_RE.match(produced):
        rep.err(rel, f"produced_at 必须是 YYYY-MM-DD：{produced!r}")

    # 原始记录必须真的存在，并建索引用于核对代表词
    project_root = path.parents[2] if len(path.parents) > 2 else None
    available: set[str] = set()
    source_records = data.get("source_records")
    if not isinstance(source_records, list) or not source_records:
        rep.err(rel, "source_records 必须是非空数组——没有出处的需求簇是猜的")
        source_records = []
    for src in source_records:
        if not isinstance(src, str):
            rep.err(rel, f"source_records 里的路径必须是字符串：{src!r}")
            continue
        src_path = (project_root / src) if project_root else Path(src)
        if not src_path.is_file():
            rep.err(rel, f"source_records 指向的文件不存在：{src}")
            continue
        try:
            available |= _collect_keywords(json.loads(src_path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            rep.err(rel, f"source_records 指向的文件不是合法 JSON：{src}")

    clusters = data.get("clusters")
    if not isinstance(clusters, list) or not clusters:
        rep.err(rel, "clusters 必须是非空数组")
        clusters = []

    inferred = {
        item.get("keyword")
        for item in data.get("inferred_keywords", [])
        if isinstance(item, dict)
    }

    seen_ids: set[str] = set()
    for i, cluster in enumerate(clusters):
        where = f"{rel} clusters[{i}]"
        if not isinstance(cluster, dict):
            rep.err(where, "簇必须是对象")
            continue
        cid = cluster.get("cluster_id")
        if not isinstance(cid, str) or not CLUSTER_ID_RE.match(cid):
            rep.err(where, f"cluster_id 不是合法的 kebab-case id：{cid!r}")
        elif cid in seen_ids:
            rep.err(where, f"cluster_id 重复：{cid!r}")
        else:
            seen_ids.add(cid)

        if cluster.get("priority") not in PRIORITIES:
            rep.err(where, f"priority 取值非法：{cluster.get('priority')!r}")

        grade = cluster.get("evidence_grade")
        if grade not in EVIDENCE_GRADES:
            rep.err(where, f"evidence_grade 取值非法：{grade!r}")

        for field in ("user_task", "judgment"):
            if not isinstance(cluster.get(field), str) or not cluster[field].strip():
                rep.err(where, f"{field} 不能为空——簇的定义和判断都要写出来")

        refs = cluster.get("evidence_refs")
        if not isinstance(refs, list) or not refs:
            rep.err(where, "evidence_refs 不能为空——没有引用的判断是猜的")

        keywords = cluster.get("representative_keywords")
        if not isinstance(keywords, list) or not keywords:
            rep.err(where, "representative_keywords 必须是非空数组")
            continue
        for kw in keywords:
            if kw in inferred:
                rep.err(
                    where,
                    f"{kw!r} 是推断词，不能当代表词。"
                    "推断词要单独放在 inferred_keywords 里——"
                    "混进代表词就是把推断当证据用",
                )
            elif available and kw not in available:
                rep.err(
                    where,
                    f"代表词 {kw!r} 在 source_records 里找不到。"
                    "代表词必须有原始记录支撑，不能凭空写",
                )

        basis = cluster.get("clustering_basis")
        if basis not in CLUSTERING_BASES:
            rep.err(
                where,
                f"clustering_basis 取值非法：{basis!r}。"
                "每个簇都要写清凭什么聚出来的——不写依据的簇是猜的",
            )

        # 词面归一只能合大小写/空格变体。把「数字员工」和「智能体搭建」
        # 说成词面变体，是把一个没做的判断伪装成一条规则。
        if basis == "surface_norm":
            normed = {_normalize_surface(k) for k in keywords if isinstance(k, str)}
            if len(normed) > 1:
                rep.err(
                    where,
                    f"clustering_basis 写了 surface_norm，但代表词归一到 {len(normed)} 个不同词形："
                    f"{sorted(normed)}。词面归一只能合大小写和空格变体；"
                    "不同的词要合簇，得用 serp_overlap 或 task_inference",
                )

        if basis == "serp_overlap":
            ev = cluster.get("serp_evidence")
            if not isinstance(ev, dict):
                rep.err(
                    where,
                    "clustering_basis 写了 serp_overlap，却没有 serp_evidence。"
                    "声称做了 SERP 重叠测量却不给采样范围，等于编了一个没做的测量",
                )
            else:
                chans = ev.get("channels")
                if not isinstance(chans, list) or not chans:
                    rep.err(where, "serp_evidence.channels 必须是非空数组——写清在哪个渠道采的")
                sampled = ev.get("sampled_at")
                if not isinstance(sampled, str) or not DATE_RE.match(sampled):
                    rep.err(where, f"serp_evidence.sampled_at 必须是 YYYY-MM-DD：{sampled!r}")
                mj = ev.get("min_jaccard")
                if isinstance(mj, bool) or not isinstance(mj, (int, float)) or not (0 <= mj <= 1):
                    rep.err(where, f"serp_evidence.min_jaccard 必须是 0–1 之间的数：{mj!r}")
                elif mj < SERP_MIN_OVERLAP and not ev.get("note"):
                    rep.err(
                        where,
                        f"serp_evidence.min_jaccard={mj} 低于阈值 {SERP_MIN_OVERLAP}，"
                        "却没写 note 说明为什么仍然合簇。"
                        "低重叠有两种原因——不同意图、或内容稀缺——不说明就是没区分",
                    )

        bp = cluster.get("business_potential")
        if bp is not None and (
            isinstance(bp, bool) or not isinstance(bp, int) or not (0 <= bp <= 3)
        ):
            rep.err(where, f"business_potential 必须是 0–3 的整数或 null：{bp!r}")

        # 推断出来的簇不可能有指数——没有数据就没有数
        if grade == "inference" and cluster.get("index_range"):
            rep.err(
                where,
                f"evidence_grade 是 inference，却带了 index_range={cluster['index_range']!r}。"
                "推断出来的簇没有指数",
            )
        rep.checked_clusters += 1

    for k, item in enumerate(data.get("inferred_keywords", [])):
        where = f"{rel} inferred_keywords[{k}]"
        if not isinstance(item, dict):
            rep.err(where, "推断词必须是对象")
            continue
        if not item.get("why_inferred"):
            rep.err(where, "推断词必须写 why_inferred——凭什么推出来的")
        targets = item.get("needs_verification_at")
        if not isinstance(targets, list) or not targets:
            rep.err(where, "推断词必须写 needs_verification_at——去哪个渠道验证")

    for k, item in enumerate(data.get("excluded", [])):
        if not isinstance(item, dict) or not item.get("why"):
            rep.err(
                f"{rel} excluded[{k}]",
                "排除项必须写 why——排除是判断的一部分，不写理由等于没看过",
            )

    for k, entry in enumerate(data.get("evidence_ledger", [])):
        where = f"{rel} evidence_ledger[{k}]"
        if not isinstance(entry, dict):
            rep.err(where, "账本条目必须是对象")
            continue
        for field in ("conclusion", "source"):
            if not isinstance(entry.get(field), str) or not entry[field].strip():
                rep.err(where, f"{field} 不能为空")
        if entry.get("grade") not in EVIDENCE_GRADES:
            rep.err(where, f"grade 取值非法：{entry.get('grade')!r}")
        date = entry.get("date")
        if not isinstance(date, str) or not DATE_RE.match(date):
            rep.err(where, f"date 必须是 YYYY-MM-DD：{date!r}")

    gates = data.get("gates")
    if isinstance(gates, dict):
        for name, gate in gates.items():
            where = f"{rel} gates.{name}"
            if not isinstance(gate, dict):
                rep.err(where, "闸门必须是对象")
                continue
            if gate.get("grade") not in EVIDENCE_GRADES:
                rep.err(where, f"grade 取值非法：{gate.get('grade')!r}")
            if not gate.get("note"):
                rep.err(where, "闸门必须写 note——只给分不给理由，分数会被当成结论")


def _covers_of(entry: dict) -> set[str]:
    return {_normalize_surface(k) for k in entry["covers"]}


def validate_library(project: Path, rep: Report, core_keywords: list[str]) -> None:
    """调研结论库——**建了但找不到，等于没建**。

    这一节拦三件事，都发生在「库长得很好、但没人用得上」这条路径上：

    1. **索引和库文件漂移** —— 有人手改了索引，或者改了库忘了重生成。
       漂移的索引**比没有更糟**：它会让人以为「库里就这些」。
       所以这里不是「检查索引格式」，是**按生成器重算一遍，逐字比对**。
    2. **库文件没写 `covers`** —— 没有「覆盖的词」这一列，按词就搜不到。
       主题名和词的对应关系不是一对一的，靠主题名猜一定会漏。
    3. **调研做完了但没入档** —— `normalized/` 里出现过的核心词，
       没有任何一个库文件覆盖它。**这一条直接对应「花钱采了但没留下」。**
    """
    library_dir = project / "research" / "library"
    if not library_dir.is_dir():
        # **空项目该是绿的。** 还没有东西要入档时，缺库目录不是错误——
        # 「没有产物不是错误」是项目层的一条硬原则，这里不能破。
        # 只有**已经有调研、却没有地方入档**时，缺目录才是真问题。
        if core_keywords:
            rep.err(
                "research/library/",
                f"做过调研（research/normalized/ 里有 {'、'.join(core_keywords)}）"
                "但没有调研结论库目录——结论没有地方放，下一轮会从零重采。"
                "新建项目跑 capabilities/project-scaffold",
            )
        return

    try:
        from library_index import (  # noqa: PLC0415
            build_claude_block,
            build_readme,
            collect_entries,
        )
    except ImportError:  # pragma: no cover - 同目录导入失败只可能是文件被删了
        rep.err("scripts/", "读不到 library_index.py，无法核对索引是否和库一致")
        return

    script_path = str((SYSTEM_ROOT / "capabilities/keyword-research/scripts/library_index.py"))
    entries = collect_entries(library_dir)

    for entry in entries:
        where = f"research/library/{entry['file']}"
        if not entry["covers"]:
            rep.err(
                where,
                "没写 covers（覆盖的词）。**没有这一列，按词就搜不到这个文件**——"
                "主题名和词的对应关系不是一对一的，靠主题名猜一定会漏。"
                "front matter 里写 `covers: [词1, 词2]`",
            )
        if not entry["summary"]:
            rep.err(
                where,
                "没写 summary。索引里只有主题名的话，看的人没法判断要不要翻——"
                "一句话说清这个文件里最值钱的判断",
            )
        if not DATE_RE.match(entry["updated"] or ""):
            rep.err(where, f"updated 必须是 YYYY-MM-DD：{entry['updated']!r}")

    # 逐字比对，不是「检查格式」——重算一遍就知道有没有人忘了重新生成
    # 索引**有东西可索引时才要求**。库里一条都没有的时候，索引没得可漂——
    # 此时判红是拿脚手架的要求去罚一个还没开工的项目，那是误报。
    # 第一条主题写进来之后，这一节立刻生效。
    if entries:
        readme = library_dir / "README.md"
        wanted_readme = build_readme(entries, script_path)
        if not readme.is_file():
            rep.err(
                "research/library/README.md",
                "没有索引文件。库文件存在但没人知道该翻哪一个——"
                "跑 capabilities/keyword-research/scripts/library_index.py 生成它",
            )
        elif readme.read_text(encoding="utf-8") != wanted_readme:
            rep.err(
                "research/library/README.md",
                "索引和库文件不一致（改了库没重新生成，或者手改了索引）。"
                "**漂移的索引比没有更糟**——它会让人以为「库里就这些」。"
                "跑 capabilities/keyword-research/scripts/library_index.py 重建",
            )

        claude = project / "CLAUDE.md"
        if not claude.is_file():
            rep.err("CLAUDE.md", "项目根没有 CLAUDE.md，调研结论库进不了会话上下文")
        else:
            text = claude.read_text(encoding="utf-8")
            wanted_block = build_claude_block(entries, script_path)
            if wanted_block not in text:
                rep.err(
                    "CLAUDE.md",
                    "索引块和库文件不一致（或标记块被删了）。这一块是**每次会话自动加载**的那一层，"
                    "它一旦和库脱节，调研过的主题就会被重跑一遍。"
                    "跑 capabilities/keyword-research/scripts/library_index.py 重建",
                )

    # 调研做完了但没入档——花钱采了却没留下
    covered: set[str] = set()
    for entry in entries:
        covered |= _covers_of(entry)
    for keyword in core_keywords:
        if _normalize_surface(keyword) not in covered:
            rep.err(
                "research/library/",
                f"`{keyword}` 做过调研（见 research/normalized/），但没有任何库文件覆盖它。"
                "**调研花掉的钱和 token 只有写进库里才留得下**——"
                "在对应主题的 front matter 的 covers 里补上，或者新建一个主题文件。"
                "见 capabilities/keyword-research/methods/research-library.md",
            )


def validate_project(project: Path, rep: Report) -> None:
    channels = load_channels()
    if not channels:
        rep.err(
            "channels/",
            "系统层没有加载到任何渠道定义——"
            "capabilities/keyword-research/channels/ 下应有 <channel>.md",
        )

    raw_dir = project / "research" / "raw"
    for path in sorted(raw_dir.rglob("*.json")):
        validate_record(path, str(path.relative_to(project)), channels, rep)

    norm_dir = project / "research" / "normalized"
    core_keywords: list[str] = []
    for path in sorted(norm_dir.rglob("*.clusters.json")):
        validate_cluster(path, str(path.relative_to(project)), rep)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        keyword = data.get("core_keyword")
        if isinstance(keyword, str) and keyword and keyword not in core_keywords:
            core_keywords.append(keyword)

    validate_library(project, rep, core_keywords)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验关键词研究产物")
    parser.add_argument("--project", required=True, help="项目根目录")
    args = parser.parse_args(argv)

    project = Path(args.project).expanduser().resolve()
    if not (project / ".hq-geo.json").is_file():
        print(f"FAIL  这里不是 hq-geo 项目根（没有 .hq-geo.json）：{project}")
        return 1

    rep = Report()
    validate_project(project, rep)

    if rep.ok:
        print(
            f"PASS  关键词研究校验通过"
            f"（{rep.checked_records} 条记录、{rep.checked_clusters} 个需求簇）"
        )
        return 0

    print(f"FAIL  关键词研究校验未通过，{len(rep.errors)} 处问题：")
    for line in rep.errors:
        print(f"  - {line}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
