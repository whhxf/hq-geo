#!/usr/bin/env python3
"""选题记录的契约检查。

选题记录是「想法」和「生产」之间的闸门。它的判据被删掉，Agent 不会报错——
它会开始**把没答过五问的想法登记成选题**，然后按选题去写稿。
写出来的东西没人能判断对不对，也没人知道它当初凭什么被选中。

这里查三样：契约的字段还在不在、五问的门槛还在不在、分层边界还在不在。
"""

import json
import sys
from pathlib import Path

SYSTEM = Path(__file__).resolve().parents[2]

PACKAGE = "capabilities/topic-registry"
SCHEMA = f"{PACKAGE}/contracts/topic.schema.json"
README = f"{PACKAGE}/README.md"

FIVE_QUESTIONS = (
    "audience_and_scene",
    "failing_explanation",
    "own_judgment",
    "content_promise",
    "falsification",
)

# 这些字段属于生产进度，按 AGENTS.md 第 31 行「四层各自独立成文件」不该在选题契约里。
# 契约里出现它们，等于把任务表复制了一份——两边各说各话。
FORBIDDEN = ("stage", "progress", "next_action", "updated_at", "status")


def read(relative: str) -> str:
    return (SYSTEM / relative).read_text(encoding="utf-8")


def check_schema(errors: list) -> None:
    schema = json.loads(read(SCHEMA))

    if schema.get("properties", {}).get("schema_version", {}).get("const") != 2:
        errors.append("topic.schema.json 的 schema_version 必须是 2")

    for key in ("schema_version", "idea_id", "topics"):
        if key not in schema.get("required", []):
            errors.append(f"选题契约缺必填项 {key}")

    topic = schema.get("$defs", {}).get("topic", {})
    props = topic.get("properties", {})

    for key in ("id", "title", "source", "state"):
        if key not in topic.get("required", []):
            errors.append(f"选题缺必填项 {key}")

    # 五问必须都在，且都必须可空。
    # 做成非空 = 逼人填满才能登记，填出来的就是凑数的。
    for question in FIVE_QUESTIONS:
        if question not in props:
            errors.append(f"选题契约缺五问之一：{question}")
        elif "null" not in (props[question].get("type") or []):
            errors.append(f"{question} 必须允许为空——五问可以全空（那是想法），不能逼人填")

    kinds = props.get("source", {}).get("properties", {}).get("kind", {}).get("enum", [])
    for kind in ("research", "direct", "imported"):
        if kind not in kinds:
            errors.append(f"选题来源缺 {kind}")

    states = props.get("state", {}).get("enum", [])
    for state in ("candidate", "selected", "dropped"):
        if state not in states:
            errors.append(f"选题状态缺 {state}")

    # 分层边界：契约里不该出现生产进度字段
    for field in FORBIDDEN:
        if field in props:
            errors.append(
                f"选题契约里出现了 {field!r}——那是生产进度，属于 tasks/。"
                "契约里留着它，等于把任务表复制了一份"
            )


def check_readme(errors: list) -> None:
    readme = read(README)

    for needle, reason in [
        (
            "**答不上第 5 问的不是选题，是想法。**",
            "五问是准入门槛，第 5 问是唯一能证伪自己的一问",
        ),
        (
            "**五问要么全答、要么全空。**",
            "半答比不答更危险——看起来像验证过了",
        ),
        (
            "**只到这里。**",
            "选题记录只管「做不做」，不管「做到哪了」；不写这条会被当成任务表用",
        ),
        (
            "**五问必须全空，state 只能是 `candidate`**",
            "imported 是没经过调研和讨论的历史数据，不能直接选定",
        ),
        (
            "**已经产出母脚本的也一样**",
            "推进得深不等于验证过——这是迁移时最容易放过去的一条",
        ),
        (
            "**选定哪条是用户的决定**",
            "系统给证据和判断，不替用户选",
        ),
        (
            "**一个创意一个文件。**",
            "一个文件放多个创意，selected_topic_id 就没法表达「这个创意的哪一条定了」",
        ),
    ]:
        if needle not in readme:
            errors.append(f"选题记录 README 缺判据：{reason}")

    for question in FIVE_QUESTIONS:
        if question not in readme:
            errors.append(f"选题记录 README 缺五问字段 {question}")


def check_validator_wired(errors: list) -> None:
    """校验器和迁移脚本必须真的在，且校验器认识五问。"""
    validator = SYSTEM / PACKAGE / "scripts" / "validate_topics.py"
    if not validator.is_file():
        errors.append("选题记录没有校验器")
        return

    text = validator.read_text(encoding="utf-8")
    for question in FIVE_QUESTIONS:
        if question not in text:
            errors.append(f"校验器不认识五问字段 {question}")
    for field in FORBIDDEN:
        if field not in text:
            errors.append(f"校验器不再拦 {field!r}——混层的选题会静默通过")

    if not (SYSTEM / PACKAGE / "scripts" / "migrate_v1.py").is_file():
        errors.append("v1 选题记录没有迁移脚本——旧格式的项目会卡住")


def main() -> int:
    errors = []
    check_schema(errors)
    check_readme(errors)
    check_validator_wired(errors)

    if errors:
        print("FAIL topic-registry")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS topic-registry: 契约字段、五问门槛与分层边界齐全")
    return 0


if __name__ == "__main__":
    sys.exit(main())
