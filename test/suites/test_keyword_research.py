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
CHANNELS_DIR = f"{PACKAGE}/channels"
CHANNEL = f"{PACKAGE}/channels/xhs-spotlight.md"
GDT_CHANNEL = f"{PACKAGE}/channels/gdt-bidword.md"
XHS_SERP_CHANNEL = f"{PACKAGE}/channels/xhs-serp.md"
DY_CHANNEL = f"{PACKAGE}/channels/douyin-search.md"
SERP_METHOD = f"{PACKAGE}/methods/serp-overlap-clustering.md"
CROSS_EVIDENCE_METHOD = f"{PACKAGE}/methods/cross-evidence-validation.md"
LIBRARY_METHOD = f"{PACKAGE}/methods/research-library.md"
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

    record_props = record.get("$defs", {}).get("record", {}).get("properties", {})

    # 竞争程度不能是封闭枚举。聚光给「高/中/低」，广点通给数字——
    # 收紧成枚举等于逼采集的人做一次跨平台口径翻译，而那个翻译是编的。
    competition = record_props.get("competition", {})
    if competition.get("enum"):
        errors.append(
            "competition 是封闭枚举——两个平台的标度不同，"
            "枚举会逼人把数字翻译成「高」，那是编"
        )
    if "integer" not in (competition.get("type") or []):
        errors.append("competition 不接受数字——广点通的竞争程度就是数字标度")

    # 月均点击量：广点通有，聚光没有。契约缺了它，那个字段没地方放
    if "monthly_click_index" not in record_props:
        errors.append("采集记录契约缺 monthly_click_index——广点通的月均点击量没地方放")

    # 簇的定义内联在 clusters.items 里，**没有 $defs**。
    # 写成 $defs.cluster 会静默拿到 {}，所有检查都变成永远通过。
    cluster_def = cluster.get("properties", {}).get("clusters", {}).get("items", {})
    if not cluster_def:
        errors.append("找不到需求簇的定义（clusters.items）——契约结构变了，检查会全部静默失效")
        return

    # 推断词是单独一类，不能混进代表词
    if "inferred_keywords" not in cluster.get("properties", {}):
        errors.append("需求簇契约没有 inferred_keywords——推断词没有地方放，就会被混进代表词")

    # --- SERP 重叠聚类（2026-09-29 实测加入）---
    cluster_props = cluster_def.get("properties", {})
    cluster_required = set(cluster_def.get("required", []))


    if "clustering_basis" not in cluster_required:
        errors.append(
            "clustering_basis 不是必填——不写依据的簇是猜的，"
            "下游没法复核它是算出来的还是想出来的"
        )
    basis = cluster_props.get("clustering_basis", {})
    if set(basis.get("enum", [])) != {"surface_norm", "serp_overlap", "task_inference"}:
        errors.append(
            "clustering_basis 的取值不是「词面归一 / SERP 重叠 / 用户任务」三种——"
            "这三个对应三级判据，少了哪一级都会让 Agent 自己编一套"
        )
    if "serp_evidence" not in cluster_props:
        errors.append(
            "契约缺 serp_evidence——写了 serp_overlap 却没有证据，"
            "等于声称做了一个没做的测量"
        )
    bp = cluster_props.get("business_potential", {})
    if bp.get("minimum") != 0 or bp.get("maximum") != 3:
        errors.append(
            "business_potential 不是 0–3——它量的是「我们的产品能不能解决这个问题」，"
            "不是量大不大。两个维度合并成总分就废了"
        )
    if "cluster_index" in cluster_props:
        errors.append(
            "cluster_index 是 index_range 的重复字段——两个字段同一个含义，"
            "迟早会写出不一致的值"
        )

    # 原生内容渠道的记录字段。缺了它们，SERP 记录会因为
    # 「只有关键词、没有信号字段」被校验器拒掉——而它们确实是信号。
    for field in ("note_id", "title", "author", "likes", "rank", "raw", "related_tabs"):
        if field not in record_props:
            errors.append(f"采集记录契约缺 {field}——原生内容渠道的记录没地方放")


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


def check_all_channel_front_matter(errors: list) -> None:
    """每个渠道文件的 front matter 都要能被校验器读出来。

    加渠道就是加文件——所以这里不能只查一个写死的渠道名，
    否则新加的渠道文件写坏了 front matter，没有任何测试会红。
    """
    directory = SYSTEM / CHANNELS_DIR
    files = sorted(p for p in directory.glob("*.md") if p.name != "README.md")
    if len(files) < 2:
        errors.append(
            f"channels/ 下只找到 {len(files)} 个渠道文件——"
            "至少该有 xhs-spotlight 和 gdt-bidword"
        )

    for path in files:
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---"):
            errors.append(f"{path.name} 没有 front matter——校验器读不到 access / evidence_nature")
            continue

        front_matter = {}
        for line in text.splitlines()[1:]:
            if line.strip() == "---":
                break
            if ":" in line:
                key, _, value = line.partition(":")
                front_matter[key.strip()] = value.strip()

        missing = CHANNEL_FRONT_MATTER - set(front_matter)
        if missing:
            errors.append(f"{path.name} 的 front matter 缺字段：{sorted(missing)}")
        if front_matter.get("channel") != path.stem:
            errors.append(f"{path.name} 的 channel 与文件名对不上")
        # 跑通过的渠道必须写清是哪天跑通的——平台会改版，这个日期是过期判断的依据
        if front_matter.get("status") == "verified" and not front_matter.get("verified_at"):
            errors.append(f"{path.name} 标了 verified 却没写 verified_at")


def check_channel(errors: list) -> None:
    text = read(CHANNEL)

    if not text.startswith("---"):
        return  # 已在 check_all_channel_front_matter 里报过

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
            "**平台把大小写不同的写法当独立词条，各给各的指数。**",
            "AI数字员工 370 / ai数字员工 825 是两个条目两个数——照抄平台写法，归一交给系统做",
        ),
        (
            "**「在 A 的拓词结果里没看到 B」≠「B 没有量」。**",
            "拓词只围绕种子词长，跨簇的词不会出现——据此判「没量」得到的不是「没数据」，是「错数据」",
        ),
        (
            "**读到 .xlsx 先验格式再解析**",
            "导出后缀是 .xlsx 实际是 CSV——直接按 Excel 解析会失败",
        ),
        (
            "**每个节点一套词表，互不包含**",
            "用户路径拓词是路径+节点两层，只读默认状态就少收 80% 以上——"
            "这是「产出变少但不报错」的典型场景，不写明会以为一个页签就是一张表",
        ),
        (
            "**「共 N 个关键词」不代表 DOM 里有 N 行。**",
            "结果表是虚拟滚动，只读一次会拿到看似合理的子集——"
            "109 条里读到 50 条不报错，不写明会把少收当成采完了",
        ),
        (
            "**虚拟滚动会让采集静默少收。**",
            "数对不上就是信号：读完先核对「共 N 个」和实际行数——"
            "这条是上一条在「已知陷阱」里的落点，两处都要在",
        ),
        (
            "**切换页签会清空种子词**",
            "三个页签的输入控件形态不同，切完不重新输入就会空转——不写明每次都得重新试",
        ),
        (
            "**平台会改版。**",
            "渠道文件是易腐件，改版时改文件不改契约——不写明会被当成长期有效",
        ),
    ]:
        if needle not in text:
            errors.append(f"xhs-spotlight.md 缺判据：{reason}")


def check_gdt_channel(errors: list) -> None:
    text = read(GDT_CHANNEL)

    if not text.startswith("---"):
        return  # 已在 check_all_channel_front_matter 里报过

    for needle, reason in [
        (
            "**不做映射**",
            "两个平台的竞争度标度不同，不做映射是硬线——不写明会被「统一口径」的直觉改掉",
        ),
        (
            "**文件有效期 7 天**",
            "导出的下载链接会过期，不写明会有人攒着回头再下，然后发现下不了了",
        ),
        (
            "**196 条里 181 条（92%）是 `<5`。**",
            "词多不等于有量——这条不写明，下次看到「196 条」会以为拿到了 196 个需求",
        ),
        (
            "**大部分结果是词面穷举，不是需求拓展。**",
            "平台按字符变体穷举，当成需求拓展会把一个需求数成一百个",
        ),
        (
            "**不要用 `keyboard.paste` 填种子词。**",
            "在 ad.qq.com 上 paste 会粘用户剪贴板里的实际内容而不是实参，且不报错——"
            "这条不写明，下次跑还会用 paste，静默把用户剪贴板送进第三方页面",
        ),
        (
            "**平台会改版。**",
            "渠道文件是易腐件，改版时改文件不改契约——不写明会被当成长期有效",
        ),
    ]:
        if needle not in text:
            errors.append(f"gdt-bidword.md 缺判据：{reason}")

    # 账户 ID 是实例数据，不能写进系统层
    if "<账户ID>" not in text:
        errors.append("gdt-bidword.md 的入口没把账户 ID 参数化——账户号是实例数据，不进系统层")


def check_serp_method(errors: list) -> None:
    """SERP 重叠聚类——这套方法里唯一可测量的聚类判据。

    它的价值全在**方向性**和**失效边界**上。阈值本身（0.15）只是一个数，
    **方向抄反才是灾难**：把「低重叠」当成拆簇证据，会把本该合的词拆开，
    而拆完没有任何信号提示你拆错了——因为簇少了不会报错，页面就是空的。
    """
    if not (SYSTEM / SERP_METHOD).exists():
        errors.append(
            f"缺 SERP 重叠聚类方法卡（{SERP_METHOD}）——"
            "阈值和失效边界没有地方记，下一个人只能重新试一遍"
        )
        return
    method = read(SERP_METHOD)

    for needle, reason in [
        (
            "**高重叠是「该合簇」的证据。低重叠不是「该拆簇」的证据。**",
            "方向性用反会把该合的词拆开，而且拆完没有任何信号提示你拆错了",
        ),
        (
            "**所以数字之后必须读内容。这一步不能省，也不能自动化。**",
            "低重叠有两种原因（不同意图 / 内容稀缺），含义相反，只能读内容区分",
        ),
        (
            "内容稀缺",
            "Ahrefs 没讲这个失效边界——Google 索引足够大不会遇到，中文平台会",
        ),
        (
            "0.80",
            "噪声基线必须写出来——不知道同词重测只有 0.80–0.93，"
            "就会把测量抖动当成真实差异",
        ),
        (
            "0.15",
            "合簇阈值必须写出来，且必须说明它定在「显著高于无关基线」而不是「接近同词基线」",
        ),
        (
            "**指纹必须用平台的内容 ID，不能用标题。**",
            "标题会重复、会被改，用它当指纹会让重叠度虚高",
        ),
        (
            "**跨平台方向一致，数值不精确。**",
            "跨平台对照是支持性证据不是决定性证据——0.08 的差异和批间抖动同量级",
        ),
        (
            "**构造 A 和 B 之前，必须先按记录级的 `keyword` 字段过滤。**",
            "`research/raw/` 的文件名只标主词，一个文件可以装多个词"
            "（2026-09-29 实测：`xhs-serp-ai数字员工.json` 是 14 个词 378 条）。"
            "**不按 keyword 过滤就是把 378 条当成一个词的结果**——"
            "真值 0.46 会算成 0.07 上下，**低值恰好长得像「这个词没内容」，"
            "会被当成结论，而且和真值方向相反**",
        ),
    ]:
        if needle not in method:
            errors.append(f"SERP 重叠方法卡缺判据：{reason}")


def check_cross_evidence_method(errors: list) -> None:
    """跨证据交叉验证——商业工具和内容渠道怎么合起来用。

    **「交叉验证」这个词自带一个错误假设**：两边应该一致，不一致就是有问题。
    2026-09-29 实测证明这个假设是错的——两个证据性质测的不是同一件事。
    照错误假设做，会出现两种坏结果：
    一边说 A、一边说 B 时**以为发现了矛盾**，去追一个不存在的问题；
    或者一边没反对时**以为验证通过**，把「没测」当成「测了没问题」。
    """
    if not (SYSTEM / CROSS_EVIDENCE_METHOD).exists():
        errors.append(
            f"缺跨证据交叉验证方法卡（{CROSS_EVIDENCE_METHOD}）——"
            "两个证据性质各回答一半这件事没有地方记，下一个人还会去找「矛盾」"
        )
        return
    method = read(CROSS_EVIDENCE_METHOD)

    for needle, reason in [
        (
            "**所以「一致」不是验证通过的标准。**",
            "不纠正「两边应该一致」这个假设，就会去追不存在的矛盾",
        ),
        (
            "| **回答什么** | **这个词值不值得做** | **这两个词该不该合簇** |",
            "「各回答一半」必须写成能一眼看到的对照，否则又会拿量级去验聚类",
        ),
        (
            "**量级几乎一样，出价差 7.1 倍。**",
            "这是「SERP 不测量级」的铁证——高重叠的两个词可以量级相同但商业价值差 7 倍",
        ),
        (
            "**SERP 高重叠 + 商业三指标一致 → 合簇**",
            "这是整份方法卡唯一「能对答案」的判据：三项一致才是同一个市场",
        ),
        (
            "**SERP 高重叠 + 商业指标分化 → 内容可复用，但商业上是两件事**",
            "少了这条，高重叠就只能靠读内容判——而读内容不可复核",
        ),
        (
            "**「在 A 的拓词结果里没看到 B」≠「B 没有量」。**",
            "拓词结果围绕种子词长，跨簇的词不会出现——"
            "看错了地方得到的不是「没数据」，是「错数据」",
        ),
        (
            "**语义路径相关 ≠ 内容可复用。**",
            "平台给的上下游是意图路径，不是内容池重叠，两件事",
        ),
        (
            "**内容稀缺 = 现象；量级 = 这个现象值不值得行动。**",
            "「内容稀缺是机会」少了这道限定就会让人去填没人搜的坑——"
            "`AI同事` 确实稀缺，量级却只有 `<100`",
        ),
        (
            "**平台的「蓝海词」标记 ≠ 内容稀缺。**",
            "「蓝海」很可能只是「量小」——不是没人做内容，是没人搜。"
            "把平台推荐标记当结论，会做出没人看的内容",
        ),
        (
            "一次采集凭空多出三个「不同的词」",
            "`#` 缺口是「纯规则也要用真实数据验」的证据，删了就只剩一句空口号",
        ),
        (
            "规则的正确性来自「跑过真实输入」，不来自「看起来显然」。",
            "词面归一是最像「显然正确」的一级，恰恰是它漏了 `#`",
        ),
        (
            "**不要用「另一个渠道没反对」当成验证通过。**",
            "没测 ≠ 测了没问题。这条是整份方法卡的落点",
        ),
    ]:
        if needle not in method:
            errors.append(f"跨证据交叉验证方法卡缺判据：{reason}")


def check_serp_channels(errors: list) -> None:
    """两个原生内容渠道的口径硬线。

    商业工具的风险是「口径混淆」，内容渠道的风险是**「把采集失败当成数据」**——
    平台返回 0 条时，你分不清是「没人做内容」还是「自己被风控了」，
    而这两种情况的含义完全相反。渠道文件必须把区分方法写死。
    """
    for rel, needles in [
        (
            XHS_SERP_CHANNEL,
            [
                ("**连续快搜会掉登录态。**", "不写明速率限制，采集会一路撞风控还不知道"),
                ("**0 条不等于「这个词没有内容」。**", "把风控当成「无内容」是最容易犯的错"),
                ("**低重叠 ≠ 不同意图。**", "内容稀缺陷阱在渠道层的展开"),
                (
                    "**按卡片数采会把广告位写进记录。**",
                    "`section.note-item` 抓到 30 个但只有 27 条真笔记（2026-09-29 实测）——"
                    "多出来的 3 个是广告位。不写明会照卡片数采，把广告位当成笔记写进记录",
                ),
                (
                    "**没有 `/explore/` 链接的卡片直接丢掉。**",
                    "唯一的识别方法必须落在步骤里，只写在「能拿到什么」里采集时看不到",
                ),
                (
                    "**`likes` 不一定是个数。**",
                    "小红书会渲染成中文字面值 `赞`——不写明会把它当成 0 或丢掉这条",
                ),
                (
                    "**它不是 0，是「没读到」。**",
                    "把「没读到」记成 0 是编数，和把「<100」换算成 100 是同一个错",
                ),
                (
                    "**所以算重叠、做统计之前，必须先按记录级的 `keyword` 字段过滤。**",
                    "文件名只标主词，一个文件可以装多个词——"
                    "把「文件」当成「词的容器」，27 vs 378 的词对会把真值 0.46 算成 0.07，"
                    "**结论方向相反**",
                ),
            ],
        ),
        (
            DY_CHANNEL,
            [
                ("相关搜索", "抖音的「相关搜索」模块不是搜索结果，混进 records 会污染重叠计算"),
                (
                    "**所以抖音的重叠数只做交叉验证用，不作为唯一判据。**",
                    "抖音拿不到内容 ID，指纹只能用标题，重叠度会被低估",
                ),
                ("**用「倒扫第一个 `@` 开头的段」定位作者**", "标题含 | 会把字段错位"),
                (
                    "**必须轮询等元素出现，不要固定等待。**",
                    "2026-09-29 实测：睡 9 秒后 `.search-result-card` 仍是 0 个，"
                    "要等到约 15 秒才出满。**照固定等待做会采到一个空页面而且不报错**——"
                    "结果是一份语法完全合法的空 records，下游读成「这个词没内容」",
                ),
                (
                    "**它长得像「没有数据」，不像「出错」。**",
                    "这一类静默少收的共同形状，不写明下次还会按固定秒数采",
                ),
                (
                    "**两者共用 `related_tabs` 一个字段名，区分只能靠 `surface`。**",
                    "顶部话题标签和「相关搜索」模块都写进 related_tabs，"
                    "**按字段名过滤会把平台的分类词和相关的搜索词混成一堆**",
                ),
                (
                    "**「相关搜索模块」会在页面里渲染两次，内容完全相同。**",
                    "照条数数会凭空翻倍——和虚拟滚动少收是同一类陷阱的反面",
                ),
                (
                    "**算重叠前必须按记录级的 `keyword` 字段过滤。**",
                    "文件名只标主词，一个文件可以装多个词"
                    "（`douyin-search-ai数字员工.json` 里是两个词）。"
                    "**假低值的方向恰好是「这个词没内容」**，最容易被当成结论",
                ),
                (
                    "**页面常驻一个隐藏的 `iframe#nocaptcha-container`，那不是正在被风控。**",
                    "按「页面上有没有 captcha 元素」判风控会误报，"
                    "而误报的代价是白白中断一次采集",
                ),
            ],
        ),
    ]:
        if not (SYSTEM / rel).exists():
            errors.append(f"缺渠道文件 {rel}")
            continue
        text = read(rel)
        for needle, reason in needles:
            if needle not in text:
                errors.append(f"{rel} 缺口径硬线：{reason}")


def check_library_method(errors: list) -> None:
    """调研结论备查库——一轮调研做完，什么留得下来。

    这是整条链路**唯一一处给「以后」用的存储**。raw 不改写所以不带判断，
    normalized 绑定当轮所以换问题就作废，topics 是承诺不是发现。
    少了这一层，最贵的一步每轮重付一次——而且不报错，只是白花。

    三条硬线里最容易被省掉的是**口径**：库里一个裸数字看起来最干净，
    被引到内容里就成了跨平台加总（`AGENTS.md` 第 61 行）。
    """
    if not (SYSTEM / LIBRARY_METHOD).exists():
        errors.append(
            f"缺调研结论备查库方法卡（{LIBRARY_METHOD}）——"
            "结论留在哪、什么值得留没有地方记，下一轮会从零重采一遍"
        )
        return
    method = read(LIBRARY_METHOD)

    for needle, reason in [
        (
            "**没有口径的数字是错的，不是不完整的。**",
            "不写明口径是数字的一部分，库里的裸数字被引到内容里就变成跨平台加总",
        ),
        (
            "research/library/<主题>.md",
            "不写清落在哪，备查库就只是个概念，不会真的有人往里写",
        ),
        (
            "**两条都答「是」才进：**",
            "没有入档判断标准，库会退化成把 raw 重抄一遍——或者什么都不写",
        ),
        (
            "**「这个假设是错的」本身就是参考资料。**",
            "不写明推翻要留痕，被证伪的结论会被删掉，半年后的自己再踩一遍",
        ),
        (
            "**三样缺一不可，缺哪样这条结论就不该进库。**",
            "数字 / 口径 / 出处缺一样，这条结论就没法复核",
        ),
        (
            "**能不能直接写进一篇内容里？**",
            "不区分图和 LEARNING.md 的分工，发现和教训会混成一份流水账",
        ),
        (
            "**不进事实包。**",
            "平台信号不是事实——「结论」两个字容易让人以为它比原始记录硬",
        ),
    ]:
        if needle not in method:
            errors.append(f"备查库方法卡缺硬线：{reason}")


def check_library_index(errors: list) -> None:
    """索引机制——库**被找出来**的那一半。

    上面 `check_library_method` 查的是「什么值得留」；这里查的是**留下来的怎么被找到**。

    **这两件事必须分开查，因为它们的失效方式完全不同。**
    没有 method，Agent 不知道该记什么；没有索引，记了也找不到——
    而后者**更安静**：文件在磁盘上，看起来一切正常，只是下一轮没人翻开它。
    用户的原话就是这个问题：「后面录的数据比较多的时候，我也不知道它记录在哪里」。

    最容易被省掉的是**自动加载的那一半**。索引写进 `research/library/README.md`
    也算「有索引」，但那就要求有人先想到去翻这个目录——**而「想不起来翻」正是要解决的问题**。
    所以两处都要查，而且**必须由同一个生成器产出**：手写两处，迟早会各自漂移。
    """
    indexer = SYSTEM / "capabilities/keyword-research/scripts/library_index.py"
    if not indexer.exists():
        errors.append(
            "缺 library_index.py——索引没有生成器。手写索引一定会和库文件漂移，"
            "而漂移的索引比没有更糟：它会让人以为「库里就这些」"
        )
        return
    index = indexer.read_text(encoding="utf-8")

    for needle, reason in [
        (
            "CLAUDE.md",
            "生成器必须写进项目根 CLAUDE.md——那是 Claude Code 里**每次会话必定加载**的地方。"
            "只生成 README.md 就要求有人先想到去翻目录，而「想不起来翻」正是要解决的问题",
        ),
        (
            "covers",
            "索引必须带「覆盖的词」这一列。主题名和词的对应不是一对一的"
            "（`AI客服` 的结论住在 `AI数字员工.md` 里），没有这一列按词就搜不到",
        ),
        (
            "START",
            "索引块必须有起止标记才能被替换——没有标记就只能追加，每跑一次长一段",
        ),
    ]:
        if needle not in index:
            errors.append(f"library_index.py 缺要件：{reason}")

    # 校验器必须**按生成器重算一遍逐字比对**，不是「检查索引格式」。
    # 检查格式拦不住「改了库忘了重生成」——那种索引格式完全合法，只是内容是旧的。
    validator = read("capabilities/keyword-research/scripts/validate_research.py")
    for needle, reason in [
        (
            "build_readme",
            "校验器没有按生成器重算索引——只检查格式的话，"
            "「改了库忘了重生成」这种漂移会全绿通过，而它看起来完全合规",
        ),
        (
            "validate_library",
            "校验器没有核对库的那一节",
        ),
        (
            "core_keywords",
            "校验器没有核对「normalized 里出现过的核心词有没有库文件覆盖」——"
            "没有这条，「花钱采了但没留下」会静默发生，比不做还糟：不做会有人问，做了没留不会",
        ),
    ]:
        if needle not in validator:
            errors.append(f"validate_research.py 缺要件：{reason}")


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
            "选题讨论是分水岭：需求簇是机器聚的，「做不做」只有用户能定",
        ),
        (
            "「这几条里，哪一条你手上有别人没有的东西可说？」",
            "讨论选题只问这一个问题，问多了就变成系统替用户选",
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
        (
            "## 站 1：定种子词表",
            "站 1 必须定种子词表而不是单个核心词——聚类的前提是有多个词可聚，"
            "只定一个词等于先假设了自己知道这个词长什么样",
        ),
        (
            "### 必填：`clustering_basis`",
            "聚类依据必填，下游才知道这个簇是算出来的还是想出来的",
        ),
        (
            "**两条最容易用反的：**",
            "方向性和「跨簇高重叠两种含义」是这套方法最容易用错的地方，必须在 skill 层写明",
        ),
        (
            "**数字之后必须读内容。这一步不能省，也不能自动化。**",
            "数字只负责指出「这里值得看一眼」，下结论要靠读内容",
        ),
        (
            "**不要按「要不要登录」推工具**",
            "登录态在哪个浏览器里是实测出来的、各渠道不同（聚光在 ego-browser、"
            "小红书搜索页在 web-access）——按「要不要登录」推会推错，和渠道文件打架",
        ),
        (
            "**只有官方商业工具能给量。**",
            "内容平台和 AI 平台都不给搜索量。不写明会让 Agent 拿 SERP 的排名当量级用",
        ),
        (
            "**两个都要跑**",
            "只跑聚光不跑广点通，等于先假设了两个生态的需求一样——2026-09-29 实测就漏过这一条，"
            "而且是静默的：跑一个渠道读起来完全合规",
        ),
        (
            "### 闸门：交给用户确认",
            "词汇延展和 SERP 研究之间必须有一道人工闸门——没有它，系统会自己决定研究哪些词，"
            "而 SERP 是这套流程里最贵的一步",
        ),
        (
            "**没有用户确认就去做 SERP，等于替他决定了要研究哪些词。**",
            "闸门不可跳的理由，不写明会被当成可选的确认步骤",
        ),
        (
            "不在这里另建一套记录格式——复用 `geo-research` 的",
            "AI 平台的采集复用 geo 侧格式。同一件事有两套格式，下游不知道该信哪个",
        ),
        (
            "**不要在真实网站上用 `keyboard.paste` 往表单里填文本。**",
            "采集要填表单，这是采集纪律里唯一会泄露用户数据的一条——必须在 skill 层就能看到",
        ),
        (
            "### 入档：可复用的结论进 `research/library/`",
            "收尾必须入档。不写这一步，最贵的一步每轮重付一次，而且是静默的："
            "调研看起来做完了，只是什么都没留下",
        ),
        (
            "**这一轮花掉的 token、时间和采集成本，只有写进库里才留得下。**",
            "入档的理由。只写步骤不写为什么，这一站会被当成可省的收尾动作",
        ),
        (
            "**没有口径的数字是错的，不是不完整的**",
            "库里一个裸数字被引到内容里就成了跨平台加总（AGENTS.md 第 61 行）",
        ),
        (
            "**不把结论只留在对话里。**",
            "边界条款——不写明就只是收尾里的一步可选项",
        ),
        (
            "### 回填 `clustering_basis`",
            "站 3 落盘时 SERP 还没跑，簇只可能写 surface_norm / task_inference。"
            "站 4 跑完不回填，等于放弃了这一轮最贵的证据——而且校验器拦不住",
        ),
        (
            "**不补等于放弃了这一轮最贵的证据。**",
            "回填的理由，不写明会被当成可选的数据整理",
        ),
        (
            "**先读 `research/library/README.md`——这是第一件事，不是可选的。**",
            "不写成「第一件事」，读索引会被当成可省的准备动作——"
            "而重跑一遍调研是真金白银，省的不是时间",
        ),
        (
            "**按「覆盖的词」列搜你要研究的词，不要按主题名猜**",
            "主题名和词的对应不是一对一的。按主题名猜会漏掉已经采过的词，"
            "然后重采一遍——这正是索引要拦的事",
        ),
        (
            "python3 capabilities/keyword-research/scripts/library_index.py --project <项目根>",
            "入档后必须重建索引。不写明命令，索引会停在上一轮的状态，"
            "而**漂移的索引比没有更糟**——它让人以为「库里就这些」",
        ),
    ]:
        if needle not in skill:
            errors.append(f"关键词研究 skill 缺判据：{reason}")

    # 站 6 必须接上选题记录——断了的话，研究做完没有地方落
    if "capabilities/topic-registry/" not in skill:
        errors.append("skill 的站 6 没接上 topic-registry——研究做完没有地方落")


def check_pipeline_hook(errors: list) -> None:
    """文章流水线也要能看见调研结论库。

    **这个钩子单独查，因为它跨能力包。** 关键词研究里写了「入档」和「重建索引」，
    只解决了**采**和**存**——写稿时用不上，库还是只进不出的档案柜。

    用户的原话是「自然的就被加载进来」。CLAUDE.md 那块索引做到了「不用找」，
    但**知道有这张表**和**动手写稿时会去看它**是两件事：前者靠自动加载，
    后者得在流水线的入口处点名。

    **而且必须带「平台信号不是事实」这道限定。** 库里是「有人在搜这个、这么问」，
    不是「事情就是这样」。少了这句，写稿时会直接把需求信号当成事实写进正文——
    `AGENTS.md` 第 61 行的跨平台加总就是这么发生的。
    """
    pipeline = SYSTEM / "skills/article-pipeline/SKILL.md"
    if not pipeline.is_file():
        errors.append("找不到 skills/article-pipeline/SKILL.md")
        return
    text = pipeline.read_text(encoding="utf-8")

    for needle, reason in [
        (
            "research/library/README.md",
            "写稿入口没有查调研结论库——库里采过的东西用不上，就还是只进不出",
        ),
        (
            "**库里的是平台信号，不是事实**",
            "不写明这道限定，需求信号会被当成事实写进正文，"
            "或者被跨平台加总（`AGENTS.md` 第 61 行）",
        ),
        (
            "**按「覆盖的词」列搜，不要按主题名猜。**",
            "与关键词研究 skill 同一套找法——两处说法不一致，其中一处会失传",
        ),
    ]:
        if needle not in text:
            errors.append(f"文章流水线缺调研库钩子：{reason}")


def main() -> int:
    errors = []
    check_schemas(errors)
    check_channel_interface(errors)
    check_all_channel_front_matter(errors)
    check_channel(errors)
    check_gdt_channel(errors)
    check_serp_method(errors)
    check_cross_evidence_method(errors)
    check_library_method(errors)
    check_library_index(errors)
    check_serp_channels(errors)
    check_skill(errors)
    check_pipeline_hook(errors)

    if errors:
        print("FAIL keyword-research")
        for error in errors:
            print(f"- {error}")
        return 1
    print(
        "PASS keyword-research: 两份契约、渠道接口、四个渠道的口径硬线、"
        "SERP 重叠判据齐全、跨证据交叉验证与结论备查库的边界齐全、"
        "库索引能自动加载且写稿入口能查到"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
