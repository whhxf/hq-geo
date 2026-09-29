#!/usr/bin/env python3
"""关键词研究的契约检查。

这一层是**组合技能**：一个渠道一个文件，加渠道就是加文件。
所以这里查的不是「代码对不对」，是**判据和接口还在不在**。

判据被删掉，Agent 不会报错——它会自己编一套做法。编出来的做法会：
把「搜索指数 + 竞争指数 + 出价」加起来算一个「机会分」（三者量纲不同，加起来没有含义），
或者把推断出来的词当成平台数据写进需求簇（**编数**）。

那比读不到更糟：读不到会问人，编出来不会。
"""

import json
import sys
from pathlib import Path

SYSTEM = Path(__file__).resolve().parents[2]

PACKAGE = "capabilities/keyword-research"
RECORD_SCHEMA = f"{PACKAGE}/contracts/research-record.schema.json"
CLUSTER_SCHEMA = f"{PACKAGE}/contracts/demand-cluster.schema.json"
CHANNELS_README = f"{PACKAGE}/channels/README.md"
CHANNEL = f"{PACKAGE}/channels/xhs-spotlight.md"
SKILL = "skills/keyword-research/SKILL.md"

RECORD_REQUIRED = {
    "schema_version",
    "channel",
    "platform",
    "captured_at",
    "core_keyword",
    "access",
    "evidence_nature",
    "surfaces",
}
CLUSTER_REQUIRED = {
    "schema_version",
    "core_keyword",
    "produced_at",
    "stage",
    "source_records",
    "clusters",
    "excluded",
    "evidence_ledger",
}
CHANNEL_FRONT_MATTER = {
    "channel",
    "name",
    "platform",
    "access",
    "evidence_nature",
    "status",
}


def read(relative: str) -> str:
    return (SYSTEM / relative).read_text(encoding="utf-8")


def load(relative: str) -> dict:
    return json.loads(read(relative))


def check_schemas(errors: list) -> None:
    record = load(RECORD_SCHEMA)
    missing = RECORD_REQUIRED - set(record.get("required", []))
    if missing:
        errors.append(f"采集记录契约缺必填项：{sorted(missing)}")

    cluster = load(CLUSTER_SCHEMA)
    missing = CLUSTER_REQUIRED - set(cluster.get("required", []))
    if missing:
        errors.append(f"需求簇契约缺必填项：{sorted(missing)}")

    # 「<100」这类阈值必须是合法值。
    # 收紧成 integer-only 就是在逼采集的人编一个数出来——那正是本能力包要拦的事。
    index_type = (
        record.get("$defs", {})
        .get("record", {})
        .get("properties", {})
        .get("monthly_search_index", {})
        .get("type")
    )
    if "string" not in (index_type or []):
        errors.append(
            "monthly_search_index 不允许字符串——平台报「<100」时照抄，"
            "换算成 100 是编数，换成 null 是丢信息"
        )

    # 渠道 id 必须能在 channels/ 找到定义，这是校验器的核心拦截之一
    channel_prop = record.get("properties", {}).get("channel", {})
    if not channel_prop.get("pattern"):
        errors.append("采集记录契约里 channel 没有格式约束，写错的渠道名会静默通过")

    # 推断词是单独一类，不能混进代表词
    cluster_def = cluster.get("$defs", {}).get("cluster", {})
    if "inferred_keywords" not in cluster.get("properties", {}):
        errors.append("需求簇契约没有 inferred_keywords——推断词没有地方放，就会被混进代表词")


def check_channel_interface(errors: list) -> None:
    readme = read(CHANNELS_README)

    for needle, reason in [
        (
            "**每个渠道一个文件，加渠道就是加文件，渠道改版就是改文件。**",
            "渠道适配器是这一层的形状；不写明会被当成一条固定流水线来扩",
        ),
        (
            "### 为什么 `status` 必须有",
            "没跑过的渠道不许写成跑过的——没有 status，设计文档里的渠道会被当成已有能力",
        ),
        (
            "**`proxy` 是硬线。**",
            "代理信号不是目标指标的替代品，不写明会被当成视频号搜索量用",
        ),
        (
            "**待建渠道不写文件。**",
            "空壳文件下次翻到会以为已经有了",
        ),
    ]:
        if needle not in readme:
            errors.append(f"渠道接口说明缺判据：{reason}")

    for level in ("official_commercial", "official_creative", "native_content", "proxy"):
        if level not in readme:
            errors.append(f"渠道接口说明缺证据性质：{level}")


def check_channel(errors: list) -> None:
    text = read(CHANNEL)

    if not text.startswith("---"):
        errors.append("xhs-spotlight.md 没有 front matter——校验器读不到 access / evidence_nature")
        return

    front_matter = {}
    for line in text.splitlines()[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, _, value = line.partition(":")
            front_matter[key.strip()] = value.strip()

    missing = CHANNEL_FRONT_MATTER - set(front_matter)
    if missing:
        errors.append(f"xhs-spotlight.md 的 front matter 缺字段：{sorted(missing)}")
    if front_matter.get("channel") != "xhs-spotlight":
        errors.append("渠道文件的 channel 与文件名对不上")
    if front_matter.get("status") != "verified":
        errors.append("xhs-spotlight 是唯一跑通过的渠道，status 该是 verified")

    for needle, reason in [
        (
            "**月搜索指数、竞争指数、市场出价分别保存，不做加总。**",
            "三者量纲不同，加总得到的数没有任何含义——这是最容易犯的错",
        ),
        (
            "**用户路径里的占比是路径内占比，不与月搜索指数混算。**",
            "路径占比和搜索指数是两套数据，混算会凭空造出量级",
        ),
        (
            "**指数是平台自有口径，不跨平台比较。**",
            "聚光的 370 和抖音的 370 不是一回事（AGENTS.md 第 61 行）",
        ),
        (
            "**出价高不等于自然内容一定受欢迎。**",
            "出价是竞价意愿，不是内容效果的证据",
        ),
        (
            "**这些要保留在 `noise` 里说明，不能默默丢掉**",
            "噪音词丢掉的话，下次看到同一个词还要重新判断一遍",
        ),
        (
            "**指数高不等于相关**",
            "geo 56,839 是本轮最大的陷阱：量最大的词和最相关的词不是一回事",
        ),
        (
            "**平台会改版。**",
            "渠道文件是易腐件，改版时改文件不改契约——不写明会被当成长期有效",
        ),
    ]:
        if needle not in text:
            errors.append(f"xhs-spotlight.md 缺判据：{reason}")


def check_skill(errors: list) -> None:
    skill = read(SKILL)

    for needle, reason in [
        (
            "**只选 verified 的。**",
            "unverified 的渠道进去是试错不是采集，不写明 Agent 会假装有把握",
        ),
        (
            "**每读一个页签，立刻落盘。**",
            "攒到最后会丢——这是采集现场的硬教训",
        ),
        (
            "**平台给什么记什么，不改写。**",
            "改写就是编数",
        ),
        (
            "**这一步最容易犯的错是编词。**",
            "代表词不是想出来的，是从记录里挑出来的",
        ),
        (
            "**推断词单独放。**",
            "混进代表词就是把推断当证据用",
        ),
        (
            "**这一站不能省。**",
            "站 5 是分水岭：需求簇是机器聚的，「做不做」只有用户能定",
        ),
        (
            "「这几条里，哪一条你手上有别人没有的东西可说？」",
            "站 5 只问这一个问题，问多了就变成系统替用户选",
        ),
        (
            "**答不上第 5 问的不是选题，是想法。**",
            "选题与想法的分界线",
        ),
        (
            "**选定哪条由用户说，不由系统推荐。**",
            "系统给证据和判断，选定是用户的决定",
        ),
        (
            "**不产出事实。**",
            "平台信号不是事实，不能进事实包",
        ),
        (
            "**不做跨平台加总。**",
            "AGENTS.md 第 61 行在 skill 层的展开",
        ),
    ]:
        if needle not in skill:
            errors.append(f"关键词研究 skill 缺判据：{reason}")

    # 站 6 必须接上选题记录——断了的话，研究做完没有地方落
    if "capabilities/topic-registry/" not in skill:
        errors.append("skill 的站 6 没接上 topic-registry——研究做完没有地方落")


def main() -> int:
    errors = []
    check_schemas(errors)
    check_channel_interface(errors)
    check_channel(errors)
    check_skill(errors)

    if errors:
        print("FAIL keyword-research")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS keyword-research: 两份契约、渠道接口与 xhs-spotlight 的口径硬线齐全")
    return 0


if __name__ == "__main__":
    sys.exit(main())
