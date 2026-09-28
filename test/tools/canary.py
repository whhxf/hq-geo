#!/usr/bin/env python3
"""Canary：故意破坏被测对象，确认测试真的会红。

「永远为绿的测试等于没测」——但一条断言是不是空转的，光读代码看不出来。
唯一可靠的办法是把它依赖的那行删掉，跑一遍，看它红不红。

**空转的断言比没有断言更糟**：门禁一直绿着，而你以为那件事被守住了。
2026-09-28 第一次跑 canary，9 条里 5 条是空转的——全是「查关键词是否出现」，
而那个关键词在被断言的那一节里出现了两次，删掉定义行还剩一次。
所以这个工具**替换所有出现**，不是第一次：破坏一个概念，要破坏干净。

用法：

    python3 test/tools/canary.py --project <项目根>
    python3 test/tools/canary.py --project <项目根> --only 站6

破坏点写在 `test/canary.json`。**改了断言就加一条**，否则新断言可能一出生就是空转的。

这不是门禁的一部分——它故意把文件改坏再还原，不该在每次提交时跑。
它是「写断言的人」的工具，用在写完之后、提交之前。
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SYSTEM = Path(__file__).resolve().parents[2]
MANIFEST = SYSTEM / "test" / "test_manifest.json"
CASES = SYSTEM / "test" / "canary.json"


def load_commands() -> dict:
    """测试 ID → 命令。复用门禁的清单，不另造第二套真源。"""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {item["id"]: item["command"] for item in manifest["tests"]}


def run_test(command: list, project: str) -> int:
    """跑一条测试，返回退出码。非零就是变红了——那正是我们要的。"""
    env = dict(os.environ, HQ_GEO_PROJECT=project)
    result = subprocess.run(
        command,
        cwd=SYSTEM,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode


def stale_edits(originals: dict, edits: list) -> list:
    """找出原文里已经找不到的破坏点。

    破坏点失效不是错误，是信号：断言或文档改了，这条 canary 该更新了。
    不报出来的话，它会一直「通过」——而它其实什么都没破坏。
    """
    return [
        edit["file"]
        for edit in edits
        if edit["find"] not in originals[edit["file"]]
    ]


def apply_edits(originals: dict, edits: list) -> dict:
    """把破坏点应用到原文上，返回新内容。

    **替换所有出现，不是第一次。** 2026-09-28 的 bug 就出在这：
    同一个词在被断言的那一节里出现了两次，只换第一次的话第二次还在，
    断言照样绿——9 条 canary 里 5 条是这么被骗过去的。
    破坏一个概念，要破坏干净。
    """
    updated = dict(originals)
    for edit in edits:
        name = edit["file"]
        updated[name] = updated[name].replace(edit["find"], edit["replace"])
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description="破坏被测对象，确认断言真的会红")
    parser.add_argument("--project", required=True, help="项目根，测试要用它找实例层")
    parser.add_argument("--only", default="", help="只跑名字里含这个词的破坏点")
    args = parser.parse_args()

    commands = load_commands()
    config = json.loads(CASES.read_text(encoding="utf-8"))
    cases = [item for item in config["cases"] if args.only in item["name"]]

    if not cases:
        print(f"没有匹配的破坏点：--only {args.only}" if args.only else "破坏点清单是空的")
        return 1

    print("=== Canary：逐条破坏，确认测试真的会红\n")

    dead = []
    for case in cases:
        originals = {
            edit["file"]: (SYSTEM / edit["file"]).read_text(encoding="utf-8")
            for edit in case["edits"]
        }

        stale = stale_edits(originals, case["edits"])
        if stale:
            print(f"  ? {case['name']}")
            for item in stale:
                print(f"      破坏点已失效：{item} 里找不到要替换的文本")
            print("      断言或文档改了，去 test/canary.json 更新这一条")
            dead.append(case["name"])
            continue

        try:
            for name, content in apply_edits(originals, case["edits"]).items():
                (SYSTEM / name).write_text(content, encoding="utf-8")
            code = run_test(commands[case["test"]], args.project)
        finally:
            for name, content in originals.items():
                (SYSTEM / name).write_text(content, encoding="utf-8")

        if code != 0:
            print(f"  ✓ {case['name']} —— 变红")
        else:
            print(f"  ✗ {case['name']} —— 破坏后仍然 PASS，这条断言是空转的")
            dead.append(case["name"])

    # 还原后复跑一次，确认没把文件改坏。
    print("\n=== 还原后复跑")
    tests = sorted({case["test"] for case in cases})
    restored = all(run_test(commands[item], args.project) == 0 for item in tests)

    if not restored:
        print("还原后测试没通过——文件可能没恢复干净，去 git status 看一眼")
        return 1

    if dead:
        print(f"\n{len(cases)} 条里 {len(dead)} 条空转：")
        for name in dead:
            print(f"  - {name}")
        print("\n空转的断言要么收紧成整行定义，要么删掉。留着它比没有更糟。")
        return 1

    print(f"\n{len(cases)} 条全部变红。断言不是空转的。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
