#!/usr/bin/env python3
"""取材能力的契约检查。

取材是创作链路的第一环：把想法或主题变成 production-brief。
两条路径（访谈 / 检索）各有判据文档，入口 skill 负责分派。

这些文件是 Agent 要读的。判据被删掉或被改弱，Agent 不会报错——
它会自己编一套问法，然后拿着编出来的问法去问用户，用户答不出来，
两边都以为「这个主题没材料」。那比读不到更糟。

所以这个检查盯的是**判据在不在**，不是措辞好不好。
"""

import sys
from pathlib import Path

SYSTEM = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SYSTEM))

READ_ME = "capabilities/sourcing/README.md"
INTERVIEW = "capabilities/sourcing/interview-method.md"
RESEARCH = "capabilities/sourcing/research-method.md"
SKILL = "skills/sourcing/SKILL.md"

# 事实包校验器里 owner_statement 允许的四类。访谈挖到的必须落进这四类，
# 落不进去的（外部效果、客户评价）不能变成 verified 事实。
OWNER_CATEGORIES = ["founder_viewpoint", "firsthand_experience", "internal_process", "product_intent"]


def read(relative: str) -> str:
    return (SYSTEM / relative).read_text(encoding="utf-8")


def check_entry(errors: list) -> None:
    """入口 skill：什么时候启动、先问什么、怎么分派。"""
    skill = read(SKILL)

    for needle, reason in [
        (
            "**启动时问一次，不替用户选**",
            "取材是可选的（2026-09-28 Conan 定），入口必须先问走哪条路，不能替用户决定",
        ),
        (
            "你手上有独家经验或判断要讲（访谈），还是让我去找线上资料和第三方证据（检索）？",
            "分派问题必须写死原话——措辞松了会问成「你想聊还是想搜」，那是两种完全不同的东西",
        ),
        (
            "**写盘前先把要写的东西给用户看一遍**",
            "事实包是 protected 的，落盘前必须给用户过目，否则一次追问就把未确认的判断写成了事实",
        ),
        (
            "**先建 pending question**",
            "capture_fact.py 要求问题先存在，不写明这条，Agent 会直接调用然后失败",
        ),
        (
            "**brief 的 `status` 按实际情况写**",
            "必须禁止为了让流程往下走就标 ready_for_production——G1-02 卡在 blocked 就是对的",
        ),
        (
            "**不写成稿。**",
            "取材只管立 brief，正文是下游的事；不写明会一路写到成稿，绕过八站",
        ),
    ]:
        if needle not in skill:
            errors.append(f"取材入口缺失（{reason}）: {needle}")


def check_interview(errors: list) -> None:
    """访谈路径：怎么问。这是整个能力最容易被写弱的部分。"""
    method = read(INTERVIEW)

    for needle, reason in [
        (
            "**这个回答会填上哪一格？**",
            "必须写明每一问的判据是「填哪一格」——不写这条，追问会退化成闲聊",
        ),
        (
            "填不上的不问。",
            "「填哪一格」必须给否定的用法，否则只是一句口号",
        ),
        (
            "**一次问三个，用户只会回答最容易的那个**",
            "「一次只问一个」必须写清理由——只说结论，下一版会被人当成风格偏好删掉",
        ),
        (
            "五件事任一不清楚就不发送。",
            "五要素锁定必须有硬判据，否则是「想一想再问」这种没有约束力的建议",
        ),
        (
            "**用户说没看懂时，上一问作废。**",
            "用户没看懂是提问失败的信号，不是用户理解力的问题——必须写明撤回重问，不得解释原问题",
        ),
        (
            "**还不出来就保留为未知，不要提供候选答案让用户认领。**",
            "换四个入口都不行时必须保留未知——给候选答案会让用户顺着说，拿到的事实是假的",
        ),
        (
            "**问题里除了用户已经说过的词，还有没有你新加的词？**",
            "「不许诱导」必须给可执行的判据，否则每个人对诱导的理解不一样",
        ),
        (
            "**外部效果那一条要特别小心**",
            "用户口述的外部效果不能进 verified——这是 owner_statement 只能验证四类 owner 事实的对话版",
        ),
        (
            "**逐字保存，不改写。**",
            "原话是事实条目的原始证据，改写过就回指不了任何东西",
        ),
        (
            "**两问，分两轮问，不能合并**",
            "收束两问合并成一问，用户只会回答其中一个，另一个永远拿不到",
        ),
    ]:
        if needle not in method:
            errors.append(f"访谈判据缺失（{reason}）: {needle}")

    # 四个换法必须齐全，缺一个就少一条退路
    for entry, reason in [
        ("**还原事件**", "说不清时的第一个换法：从具体事件问起"),
        ("**追问信号与动作**", "第二个换法：问当时看见什么、做了什么、排除了什么"),
        ("**比正反案例**", "第三个换法：用亲历的成功/失败对照"),
        ("**问失效边界**", "第四个换法：问什么条件下判断不成立"),
    ]:
        if entry not in method:
            errors.append(f"访谈换法缺失（{reason}）: {entry}")

    # 四类 owner 事实必须和 capture_fact.py 的枚举一致
    for category in OWNER_CATEGORIES:
        if category not in method:
            errors.append(
                f"访谈落盘缺失 owner 事实类型（必须与 capture_fact.py 的 ALLOWED_OWNER_CATEGORIES 一致）: {category}"
            )


def check_research(errors: list) -> None:
    """检索路径：找什么、从哪找、怎么落。"""
    method = read(RESEARCH)

    for needle, reason in [
        (
            "**这次找的东西，会填上哪一格？**",
            "检索同样从空格出发——不写这条会变成漫无目的地搜，耗尽上下文还填不满 brief",
        ),
        (
            "## 一手来源才算证据",
            "必须写明一手优先，否则二手转述会被当成事实落进包",
        ),
        (
            "**搜索引擎和聚合平台是发现入口，不是证据本身。**",
            "这是用户环境的既有规则（一手信息优于二手），检索路径必须继承",
        ),
        (
            "**多篇媒体报道引用同一个错误会造成「循环印证」的假象**",
            "必须写明循环印证的陷阱——不写，五个媒体说同一件事就会被当成五个证据",
        ),
        (
            "**最后一行是硬线**",
            "三级定级必须点明 inference/unknown 不能 verified，这是校验器会拒绝的硬规则",
        ),
        (
            "**回指不了的不要落。**",
            "「我记得看到过」不是来源——必须写明，否则事实包会积累无法追溯的条目",
        ),
    ]:
        if needle not in method:
            errors.append(f"检索判据缺失（{reason}）: {needle}")

    for level, reason in [
        ("**直接证据**", "三级定级的第一级"),
        ("**代理信号**", "三级定级的第二级"),
        ("**未知**", "三级定级的第三级"),
    ]:
        if level not in method:
            errors.append(f"检索分级缺失（{reason}）: {level}")


def check_division(errors: list) -> None:
    """两条路径的分工必须写清，否则会互相重复或互相漏。"""
    readme = read(READ_ME)

    for needle, reason in [
        (
            "**「并不是每一次都要访谈，这是可以选的。」**",
            "取材可选是 2026-09-28 Conan 定的前提，README 必须记原话",
        ),
        (
            "`owner_statement`（只能验证四类 owner 事实）",
            "README 必须写明访谈路径落成什么证据类型",
        ),
        (
            "`official_source` / `direct_evidence`",
            "README 必须写明检索路径落成什么证据类型",
        ),
        (
            "**同一个 brief，两路填不同的格**",
            "两条路径可以并用，不写明会被当成二选一",
        ),
        (
            "**`inference` 和 `unknown` 不能是 `verified`**",
            "宪法第 5 条的机器执行版本，取材文档必须继承，不能另立一套",
        ),
    ]:
        if needle not in readme:
            errors.append(f"取材分工缺失（{reason}）: {needle}")


def main() -> int:
    errors = []
    check_entry(errors)
    check_interview(errors)
    check_research(errors)
    check_division(errors)

    if errors:
        print("FAIL sourcing")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS sourcing: 两条路径的判据、分派规则与落盘接口完整")
    return 0


if __name__ == "__main__":
    sys.exit(main())
