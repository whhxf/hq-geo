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

# 一条记录里，除了 keyword 之外至少要有一个信号字段非空。
# 只有词没有数的记录不是采集结果，是手打的清单。
SIGNAL_FIELDS = (
    "monthly_search_index",
    "competition",
    "bid_cny",
    "reason",
    "upstream_downstream",
    "path_share_percent",
)


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
                has_signal = any(
                    rec.get(f) not in (None, "") for f in SIGNAL_FIELDS
                )
                if not has_signal:
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
    for path in sorted(norm_dir.rglob("*.clusters.json")):
        validate_cluster(path, str(path.relative_to(project)), rep)


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
