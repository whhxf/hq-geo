#!/usr/bin/env python3
"""创作资产的契约检查。

策略库、风格约定和任务约定都是 Agent 要读的文件。格式坏了，
Agent 不会报错，它会自己编一套——那比读不到更糟。

系统和项目是两个根，这个文件横跨两边：**约定**（策略库、风格、任务格式、
外部顾问）在系统根，**记录**（学习库）在项目根。所以两个路径分开取，
不混成一个 ROOT。
"""

import re
import sys
from pathlib import Path

SYSTEM = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SYSTEM))
from project import find_project  # noqa: E402

PROJECT = find_project()

STRATEGIES = "capabilities/content-production/strategies/creative-strategies.md"
STYLES = "capabilities/content-production/styles/README.md"
TASKS = "capabilities/content-production/tasks/README.md"
LEARNING = "LEARNING.md"
PIPELINE = "skills/article-pipeline/SKILL.md"
ADVISORS = "capabilities/content-production/external-advisors.md"
READER_AUDIT = "capabilities/content-production/reader-audit.md"
POSITIONING = "capabilities/geo/methods/positioning-and-audience.md"
PLAYBOOK = "PLAYBOOK.md"

STRATEGY_IDS = [f"P{index:02d}" for index in range(1, 11)]
STRATEGY_FIELDS = ["适用", "平台", "需要的素材", "结构", "机制", "禁用"]

PATTERN_HEADING = re.compile(r"^## (P\d{2}) (.+)$", re.MULTILINE)


def read(relative: str) -> str:
    """读系统根的文件。系统层的约定都在这里。"""
    return (SYSTEM / relative).read_text(encoding="utf-8")


def read_project(relative: str) -> str:
    """读项目根的文件。实例层的记录都在这里。"""
    return (PROJECT / relative).read_text(encoding="utf-8")


def strategy_blocks(text: str) -> dict:
    """把每个模式切出来：{P01: (标题, 正文)}。"""
    matches = list(PATTERN_HEADING.finditer(text))
    blocks = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        blocks[match.group(1)] = (match.group(2), text[match.end():end])
    return blocks


def check_strategies(errors: list) -> int:
    path = SYSTEM / STRATEGIES
    if not path.is_file():
        errors.append(f"策略库不存在: {STRATEGIES}")
        return 0
    text = read(STRATEGIES)
    blocks = strategy_blocks(text)

    missing = [item for item in STRATEGY_IDS if item not in blocks]
    if missing:
        errors.append(f"策略库缺少模式: {', '.join(missing)}")
    extra = [item for item in blocks if item not in STRATEGY_IDS]
    if extra:
        errors.append(f"策略库出现未登记的编号: {', '.join(sorted(extra))}")

    for key, (name, body) in sorted(blocks.items()):
        for field in STRATEGY_FIELDS:
            if f"**{field}：" not in body:
                errors.append(f"{key} {name} 缺少字段「{field}」")

    if "这不是平台硬规则" not in text:
        errors.append("策略库必须写明它不是平台硬规则")
    return len(blocks)


def check_styles(errors: list) -> None:
    path = SYSTEM / STYLES
    if not path.is_file():
        errors.append(f"风格约定不存在: {STYLES}")
        return
    text = read(STYLES)
    expectations = [
        ("风格靠看", "必须写明风格靠看示例而不是靠文字描述"),
        ("吸的是特征，不是文本", "必须写明吸收风格的版权边界"),
        ("不进入任何对外产物", "必须写明样本不进入产物"),
        ("不许标注哪个是「推荐」", "必须禁止在候选里标注推荐"),
        ("必须用当前任务的真实素材", "必须禁止用占位文本充样例"),
    ]
    for needle, reason in expectations:
        if needle not in text:
            errors.append(reason)


def check_tasks_readme(errors: list) -> None:
    path = SYSTEM / TASKS
    if not path.is_file():
        errors.append(f"任务约定不存在: {TASKS}")
        return
    text = read(TASKS)
    for heading in ["## 任务", "## 待确认", "## 交付", "## 分发登记"]:
        if heading not in text:
            errors.append(f"任务约定缺少区块说明 {heading}")
    if "Agent 不得改写" not in text:
        errors.append("任务约定必须写明区块归属是硬规则")


def section_body(text: str, heading: str) -> str:
    """取某个标题到下一个标题之间的内容。"""
    start = text.find(heading)
    if start < 0:
        return ""
    rest = text[start + len(heading):]
    stops = [index for index in (rest.find("\n### "), rest.find("\n## ")) if index >= 0]
    return rest[:min(stops)] if stops else rest


def check_learning_loop(errors: list) -> None:
    """下半圈：分发登记 → 学习 → 改进。任何一段断了，生产就不会产生积累。"""
    tasks = read(TASKS)
    for needle, reason in [
        ("分发登记怎么填", "任务约定必须写明分发登记填什么"),
        ("「没效果」也要写", "分发登记必须要求记录失败，否则只留下成功样本"),
    ]:
        if needle not in tasks:
            errors.append(reason)

    if not (PROJECT / LEARNING).is_file():
        errors.append(f"学习库不存在: {LEARNING}")
    else:
        learning = read_project(LEARNING)
        # 断言格式定义整行，不是关键词是否出现——关键词在别处也有，那种断言删掉定义行也不会红
        for line, reason in [
            ("- **这次**：发生了什么", "学习记录必须写明「这次」记什么"),
            ("- **下次**：怎么做", "学习记录必须写明「下次」记什么"),
            ("- **去向**：BACKLOG / 策略库 / 只是记着", "「去向」的三个出口缺一不可"),
        ]:
            if line not in learning:
                errors.append(f"学习库格式定义缺失（{reason}）: {line}")

    pipeline = read(PIPELINE)
    for index in range(1, 9):
        if f"### 站 {index} ·" not in pipeline:
            errors.append(f"文章流水线缺少站 {index}")
    station8 = section_body(pipeline, "### 站 8 ·")
    if station8:
        if LEARNING not in station8:
            errors.append("站 8 必须指向学习库真源")
        if "去向" not in station8:
            errors.append("站 8 必须要求写出「去向」")


def check_opening_convention(errors: list) -> None:
    """开头约定：站 3 定，站 5 核。

    没有它，「读者走不到正文」这件事在流程里永远不会被问起，
    也就永远不会作为卡点进入学习记录。
    """
    pipeline = read(PIPELINE)

    station3 = section_body(pipeline, "### 站 3 ·")
    if "开头约定" not in station3:
        errors.append("站 3 必须写明开头约定")
    if "只读开头，读者以为这篇文章要讲什么" not in station3:
        errors.append("站 3 的开头约定必须给出判断标准")

    station5 = section_body(pipeline, "### 站 5 ·")
    if "开头约定" not in station5:
        errors.append("站 5 必须回头核对站 3 的开头约定")


ADVISOR_ROW = re.compile(r"^\|\s*(站 \d)\s*\|[^|]*\|([^|]*)\|", re.MULTILINE)
DBS_NAME = re.compile(r"`(dbs-[a-z-]+)`")


def advisor_map(text: str) -> dict:
    """抽出「站 N → 借谁」的映射。

    一个站可以借多个（站 5 同时借 dbs-spread 和 dbs-resonate），所以值是列表。
    只取第三列里反引号包住的 dbs 名字，避免把「什么时候问」那列的描述也算进来。
    """
    result = {}
    for match in ADVISOR_ROW.finditer(text):
        names = DBS_NAME.findall(match.group(2))
        if names:
            result[match.group(1)] = names
    return result


def check_audience_coordinate(errors: list) -> None:
    """受众坐标：站 1 定，站 3 用，站 5 出标题，站 6 复核。

    2026-09-28 的真实生产暴露的偏差：八站里没有一站问过「写给谁看」。
    受众只在站 5 的一句话里出现，没有产物、没有检查、没有停机点。
    结果是所有门都是「不许犯错」的门——事实包防说错、站 3 防跑偏、
    站 6 防像 AI——没有一扇门问「有人愿意读完吗」。

    这个检查盯的是四件事分别在不在，而不是措辞好不好。
    """
    pipeline = read(PIPELINE)

    # 断言整行定义，不是关键词是否出现——「受众坐标」在一节里出现两次，
    # 查关键词的话删掉定义行也不会红。2026-09-28 的 canary 抓到过这个错。
    station1 = section_body(pipeline, "### 站 1 ·")
    for needle, reason in [
        ("**定受众坐标。**", "站 1 必须把受众坐标作为产出，不能只是「读一下」"),
        ("先看事实包里有没有 `positioning.json`", "站 1 必须复用已有的定位卡，不得另造第二套事实"),
        ("python3 capabilities/geo/scripts/validate_positioning.py", "站 1 必须要求跑定位校验器"),
        ("一篇内容只能对准一个人写。", "站 1 必须写明一篇只选一个主要读者"),
    ]:
        if needle not in station1:
            errors.append(f"站 1 受众坐标缺失（{reason}）: {needle}")

    station3 = section_body(pipeline, "### 站 3 ·")
    for needle, reason in [
        ("**三半都从站 1 的受众坐标来，不是临时想的**", "站 3 的核心判断必须从受众坐标来，不能临时想"),
        (
            "**二、核心判断里的关键词，读者理解的和你说的是不是一回事？**",
            "站 3 必须检查关键词歧义——只问「判断有没有传出去」拦不住「传出去的不是那个意思」",
        ),
        (
            "每个关键词写一句「读者会怎么理解它」",
            "关键词检查必须有产出物，否则又是自己说自己过关",
        ),
    ]:
        if needle not in station3:
            errors.append(f"站 3 缺失（{reason}）: {needle}")

    station5 = section_body(pipeline, "### 站 5 ·")
    for needle, reason in [
        ("**标题。** 正文写完后生成**至少 3 个**候选", "站 5 必须产出标题候选，且不得少于 3 个"),
        ("关键词原文照抄不算做标题", "必须禁止把搜索词直接当标题"),
        ("**事实纪律要求的是「不夸大」，不是「写免责声明」。**", "站 5 必须写明事实纪律不等于堆免责声明"),
        (
            "**写完正文，逐节（按 `##`）写一句「读者获得」",
            "站 5 必须产出逐节读者获得声明，否则「每段都要能回答」没有产出物，是自己说自己过关",
        ),
        (
            "写不出「到什么状态」的节就是凑数",
            "站 5 必须写明读者获得声明的判据，否则表格可以随便填",
        ),
        (
            "content/packages/<channel>/<idea>/<topic>/article.md",
            "主稿路径必须按渠道参数化——硬编码 blog 会让稿子住在占位目录里，系统查不到它是给哪个渠道的",
        ),
    ]:
        if needle not in station5:
            errors.append(f"站 5 缺失（{reason}）: {needle}")

    station6 = section_body(pipeline, "### 站 6 ·")
    for needle, reason in [
        ("#### 二、受众复核", "站 6 必须有正向检查，不能只有 AI 味检查"),
        ("读者能否认出自己的问题？", "受众复核必须复用定位方法的复核清单"),
        ("`artifact_sha256` 用 `shasum -a 256 <成稿路径>` 取", "受众复核结果必须登记进定位卡，否则复核不留痕"),
        ("#### 三、读者审计", "站 6 必须有读者审计——前两道全是否定式的，只能防错不能求好"),
        (
            "**必须用 Agent 工具起一个独立 agent 执行，不能用写稿的自己审。**",
            "读者审计必须由独立 agent 执行——写稿的人审不出自己的盲区，这是实测结论",
        ),
        ("capabilities/content-production/reader-audit.md", "站 6 必须指向提问脚本，不能每次现编问法"),
        (
            "**逐节对照站 5 的「读者获得」声明。对不上的地方就是要改的地方**",
            "读者审计必须与站 5 的声明对照，否则两边各说各话，审计没有牙齿",
        ),
        ("**判红标准**（任一条成立就不得进站 7）", "读者审计必须有判红标准，否则审计结论无法阻断交付"),
    ]:
        if needle not in station6:
            errors.append(f"站 6 缺失（{reason}）: {needle}")

    # 提问脚本是读者审计能不能真的问出东西的地方。问法一软，agent 会还你一篇
    # 合格的摘要，你会误以为审计通过了——2026-09-28 的实测里，问法具体才抓到问题。
    audit = read(READER_AUDIT)
    for needle, reason in [
        ("不要抄原文", "必须禁止 agent 复述原文——抄原文说明没经过读者转化，等于没审"),
        ("不要客气，不要夸", "必须要求 agent 说真话，否则会得到一篇礼貌的评论"),
        ("逐节回答", "必须逐节问——只问整体会得到「还行」，逐节才会暴露「这一节我拿不走东西」"),
        ("**不要给它**：写作背景", "必须写明不给写作背景——它知道得越少，越像真读者"),
        ("## 判红标准", "必须写明判红标准，否则审计结论无法阻断交付"),
        ("读者读完说不出「打算做什么」", "「读者读完打算做什么」是判红的核心一条，不能只留在问题里"),
        (
            "**判红四条**是硬标准，触发就必须改",
            "必须写明判红项必须改——否则审计变成一篇读后感",
        ),
        (
            "**不阻塞交付**",
            "必须写明改进项不阻塞交付——否则读者每提一条就要改，审计变成无限循环",
        ),
        (
            "读者说的是体验，不是指令",
            "必须写明读者的话不是指令——官方号内容有些问题改稿子解决不了，是渠道策略问题",
        ),
        (
            "退回站 5 重写，不要在上面继续糊",
            "必须写明什么时候该重写而不是打补丁——打补丁改的是句子，底子的问题是问题错了",
        ),
        (
            "## 论证层的问题，读者审计在替受众复核补位",
            "读者审计抓到的论证层问题必须回写受众复核，否则受众复核会一直停在形式上的四条",
        ),
        (
            "**改稿优先删，不优先加。**",
            "必须写明改稿优先删——两轮实测的「重复」都是上一轮加段造成的，读者会因此想跳过",
        ),
        (
            "给每个新增段落找出「它和哪一段说的是同一件事」",
            "「优先删」必须给判据，否则只是一句态度，拦不住下一次加出重复",
        ),
        (
            "**补「照顾某类人」的句子，要给那类人认得出的落点。**",
            "必须写明补某类读者的内容要给落点——第十三轮实测：方向对了但停在抽象层，"
            "读者（正是被照顾的那类人）说「一个例子都不给，这是全文最大的空档」",
        ),
        (
            "把新加的那句读给那类人听，他能说出「那我明天做什么」吗？",
            "「给落点」必须给判据，否则只是一句态度，拦不住下一次补出抽象句",
        ),
        (
            "**判红第 2 条要区分「真退出」和「相对最想跳过」。**",
            "必须区分真退出和相对最想跳过——十六轮实测里一半返工源于把「最想跳过」当判红",
        ),
        (
            "**卡了不等于走了**",
            "「区分真退出」必须给判据，否则下次还是会把读者卡顿当成判红",
        ),
        (
            "**最多两轮。**",
            "必须有轮次上限——十六轮实测证明，措辞层的「可以更好」永远挑得完",
        ),
        (
            "第一轮审 → 改 → 第二轮审 → 改 → **交付**",
            "轮次上限必须写清具体怎么走，否则「最多两轮」会被读成「两轮后再看看」",
        ),
    ]:
        if needle not in audit:
            errors.append(f"读者审计脚本缺失（{reason}）: {needle}")

    # 受众复核清单是站 6 第二道的判据。它少一条，就有一类问题没人问。
    positioning = read(POSITIONING)
    for needle, reason in [
        (
            "**给的动作，读者现在做得了吗？**",
            "受众复核必须问「给的动作读者做得了吗」——同一身份下有视频和没视频是两种状态，"
            "文章承诺「今天就能做」的动作可能对其中一种不成立",
        ),
    ]:
        if needle not in positioning:
            errors.append(f"受众复核清单缺失（{reason}）: {needle}")

    # 清单要同时覆盖防错和求好两类。只有防错类，流水线会退化成
    # 「挑不出错但没人读」——这正是这次要修的偏差。
    advisors = advisor_map(read(ADVISORS))
    if not any("dbs-jtbd" in names for names in advisors.values()):
        errors.append("外部顾问清单缺少受众视角（dbs-jtbd）")
    if not any(
        "dbs-spread" in names or "dbs-resonate" in names
        for names in advisors.values()
    ):
        errors.append("外部顾问清单缺少传播与共鸣视角（dbs-spread / dbs-resonate）")


def check_external_advisors(errors: list) -> None:
    """外部顾问是可选能力，不是依赖。三条铁律缺一条，它就从顾问变成隐患。"""
    path = SYSTEM / ADVISORS
    if not path.is_file():
        errors.append(f"外部顾问登记表不存在: {ADVISORS}")
        return

    text = read(ADVISORS)
    for line, reason in [
        ("**1. 不依赖。**", "必须写明调不到 dbs 也不停机"),
        ("**2. 输出是线索，不是依据。**", "必须写明它的结论不进产物"),
        ("**3. 不搬文本。**", "必须写明授权边界"),
        ("`dbs-content-system` 不得在 hq-geo 目录下运行", "必须写明会覆盖宪法文件的禁令"),
        ("AGENTS.md` 和 `CLAUDE.md`", "禁令必须说明覆盖的是哪两个文件"),
    ]:
        if line not in text:
            errors.append(f"外部顾问登记表缺失（{reason}）: {line}")

    if ADVISORS not in read(PIPELINE):
        errors.append("文章流水线必须指向外部顾问登记表真源")

    # 借用清单在三个文件里各写了一份（登记表给全貌、八站给操作、手册给用户）。
    # 任一处漏了或改了，就成了两个真源——所以比对映射，不是比对有没有提到。
    expected = advisor_map(text)
    if not expected:
        errors.append("外部顾问登记表没有可解析的借用清单")
        return
    for label, relative in [("文章流水线", PIPELINE), ("使用手册", PLAYBOOK)]:
        found = advisor_map(read(relative))
        if found != expected:
            errors.append(f"{label}的借用清单与登记表不一致：期望 {expected}，实际 {found}")

    # 手册是用户入口。触发条件答的是「什么时候能借」，禁令防的是唯一不可逆的后果
    # ——真跑了那个 init，这个仓库的两份宪法文件就没了。
    playbook = read(PLAYBOOK)
    for line, reason in [
        ("**触发条件是「你拿不准」，不是「流程要求」。**", "手册必须写明触发条件是判断而非流程要求"),
        ("**`dbs-content-system` 不得在 hq-geo 目录下运行。**", "手册必须写明禁令"),
    ]:
        if line not in playbook:
            errors.append(f"使用手册缺失（{reason}）: {line}")


def main() -> int:
    errors = []
    count = check_strategies(errors)
    check_styles(errors)
    check_tasks_readme(errors)
    check_learning_loop(errors)
    check_opening_convention(errors)
    check_audience_coordinate(errors)
    check_external_advisors(errors)

    if errors:
        print("FAIL content assets")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"PASS content assets: {count} 个创作模式，风格、任务、学习闭环、受众坐标与外部顾问约定完整")
    return 0


if __name__ == "__main__":
    sys.exit(main())
