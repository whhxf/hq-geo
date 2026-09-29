"""校验选题记录。

这个校验器拦的四件事：

1. **想法冒充选题** —— 五问没答全的选题，不许进 `selected`
2. **半答** —— 五问答了一半。半答比不答更危险：看起来像验证过了
3. **没有出处的选题** —— research / direct 来源的选题必须挂证据
4. **混层** —— 把生产进度（`stage`、`progress`）写进选题记录

五问（`capabilities/content-production/../../00-meta/content-engine/02-research-and-topic-system.md` 第 5 节）：

1. `audience_and_scene` —— 谁在什么场景下遇到什么问题？
2. `failing_explanation` —— 现有解释或做法哪里失效？
3. `own_judgment` —— 你有什么不同判断或可展示证据？
4. `content_promise` —— 内容承诺是什么，看完能得到什么？
5. `falsification` —— 这个承诺如何被证伪？

**五问要么全答、要么全空。** 答全了才可能进 `selected`；全空的只能停在 `candidate`。
这是「选题」和「想法」的分界线。

用法：

    python3 capabilities/topic-registry/scripts/validate_topics.py --project <项目根>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

FIVE_QUESTIONS = (
    "audience_and_scene",
    "failing_explanation",
    "own_judgment",
    "content_promise",
    "falsification",
)

SOURCE_KINDS = {"research", "direct", "imported"}
STATES = {"candidate", "selected", "dropped"}
TOPIC_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# 这些字段属于生产进度，按 AGENTS.md 第 31 行「四层各自独立成文件」不该出现在选题记录里。
# 留在这里是为了给旧格式一个明确的报错，而不是让它静默通过。
FORBIDDEN_FIELDS = ("stage", "progress", "next_action", "updated_at", "status")


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.checked = 0

    def err(self, where: str, msg: str) -> None:
        self.errors.append(f"{where}: {msg}")

    @property
    def ok(self) -> bool:
        return not self.errors


def _answered(topic: dict) -> list[str]:
    return [q for q in FIVE_QUESTIONS if isinstance(topic.get(q), str) and topic[q].strip()]


def validate_registry(path: Path, rel: str, project: Path, rep: Report) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        rep.err(rel, f"不是合法 JSON：{exc}")
        return

    for key in ("schema_version", "idea_id", "topics"):
        if key not in data:
            rep.err(rel, f"缺必填项 {key}")
    if rep.errors and rep.errors[-1].startswith(rel):
        return

    if data.get("schema_version") != 2:
        rep.err(
            rel,
            f"schema_version 必须是 2，当前是 {data.get('schema_version')!r}。"
            "v1 的选题记录混了生产进度字段，按 README 的迁移说明转换",
        )

    topics = data.get("topics")
    if not isinstance(topics, list):
        rep.err(rel, "topics 必须是数组")
        return

    seen: set[str] = set()
    for i, topic in enumerate(topics):
        where = f"{rel} topics[{i}]"
        if not isinstance(topic, dict):
            rep.err(where, "选题必须是对象")
            continue

        tid = topic.get("id")
        if not isinstance(tid, str) or not TOPIC_ID_RE.match(tid):
            rep.err(where, f"id 非法：{tid!r}")
            label = where
        elif tid in seen:
            rep.err(where, f"id 重复：{tid!r}")
            label = where
        else:
            seen.add(tid)
            label = f"{rel} 选题 {tid}"

        if not isinstance(topic.get("title"), str) or not topic["title"].strip():
            rep.err(label, "title 不能为空")

        for field in FORBIDDEN_FIELDS:
            if field in topic:
                rep.err(
                    label,
                    f"不该有 {field!r}。生产进度来自 tasks/，"
                    "选题记录只管「做不做」，不管「做到哪了」（AGENTS.md 第 31 行）",
                )

        state = topic.get("state")
        if state not in STATES:
            rep.err(label, f"state 取值非法：{state!r}")

        source = topic.get("source")
        if not isinstance(source, dict):
            rep.err(label, "source 必须是对象")
            continue
        kind = source.get("kind")
        if kind not in SOURCE_KINDS:
            rep.err(label, f"source.kind 取值非法：{kind!r}")
            continue

        answered = _answered(topic)

        if kind == "imported":
            if answered:
                rep.err(
                    label,
                    "来源是 imported，却答了五问。"
                    "答全五问说明它已经被讨论过——把 source.kind 改成 direct 或 research",
                )
            if state != "candidate":
                rep.err(
                    label,
                    f"来源是 imported，state 只能是 candidate，当前是 {state!r}。"
                    "导入的选题没经过调研和讨论，不能直接选定",
                )
            for field in ("imported_from", "imported_at"):
                if not source.get(field):
                    rep.err(label, f"来源是 imported，source.{field} 必填")
            imported_at = source.get("imported_at")
            if imported_at and not DATE_RE.match(str(imported_at)):
                rep.err(label, f"imported_at 必须是 YYYY-MM-DD：{imported_at!r}")

        elif kind == "research":
            ref = source.get("research_ref")
            if not ref:
                rep.err(label, "来源是 research，source.research_ref 必填")
            elif not (project / ref).is_file():
                rep.err(label, f"research_ref 指向的文件不存在：{ref}")
            if not source.get("cluster_ref"):
                rep.err(label, "来源是 research，source.cluster_ref 必填——指回哪个需求簇")

        elif kind == "direct":
            confirmed = source.get("confirmed_at")
            if not confirmed:
                rep.err(label, "来源是 direct，source.confirmed_at 必填")
            elif not DATE_RE.match(str(confirmed)):
                rep.err(label, f"confirmed_at 必须是 YYYY-MM-DD：{confirmed!r}")

        # 五问：要么全答，要么全空
        if answered and len(answered) != len(FIVE_QUESTIONS):
            missing = [q for q in FIVE_QUESTIONS if q not in answered]
            rep.err(
                label,
                f"五问答了一半，缺 {missing}。"
                "半答比不答更危险——看起来像验证过了",
            )

        if state == "selected" and len(answered) != len(FIVE_QUESTIONS):
            rep.err(
                label,
                "五问没答全就进了 selected。"
                "答不上「如何被证伪」的不是选题，是想法——它该留在 candidate",
            )

        if kind in ("research", "direct"):
            refs = topic.get("evidence_refs")
            if not isinstance(refs, list) or not refs:
                rep.err(
                    label,
                    f"来源是 {kind}，evidence_refs 不能为空——"
                    "没有出处的选题和拍脑袋没有区别",
                )

        rep.checked += 1

    selected = data.get("selected_topic_id")
    if selected and selected not in seen:
        rep.err(rel, f"selected_topic_id 指向不存在的选题：{selected!r}")


def validate_project(project: Path, rep: Report) -> None:
    for path in sorted((project / "topics").rglob("*.json")):
        # 迁移脚本写的备份不是选题记录，跳过。旧格式的文件留在那里是为了可回溯，
        # 不是为了被当成现行数据校验。
        if path.name.endswith(".bak.json"):
            continue
        validate_registry(path, str(path.relative_to(project)), project, rep)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验选题记录")
    parser.add_argument("--project", required=True, help="项目根目录")
    args = parser.parse_args(argv)

    project = Path(args.project).expanduser().resolve()
    if not (project / ".hq-geo.json").is_file():
        print(f"FAIL  这里不是 hq-geo 项目根（没有 .hq-geo.json）：{project}")
        return 1

    rep = Report()
    validate_project(project, rep)

    if rep.ok:
        print(f"PASS  选题记录校验通过（{rep.checked} 条选题）")
        return 0

    print(f"FAIL  选题记录校验未通过，{len(rep.errors)} 处问题：")
    for line in rep.errors:
        print(f"  - {line}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
