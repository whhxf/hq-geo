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

sys.path.insert(0, str(SYSTEM))
from project import MARKER  # noqa: E402


def resolve_project(raw: str) -> str:
    """把 --project 解析成绝对路径，在起任何子进程之前。

    测试固定以 `cwd=系统根` 运行，所以相对路径会在**系统根**解析，不是在你
    敲命令的地方。2026-09-28 踩过：在项目目录里用 `--project .` 跑全量，
    所有测试都因为找不到项目而退出非零——于是每一条都显示「✓ 变红」，
    **全是假红**，而末尾复跑同样失败，报的是「文件可能没恢复干净」。

    假红和假绿一样有害：你会以为断言在守着，其实它什么都没测。
    """
    return str(Path(raw).resolve())


def load_commands() -> dict:
    """测试 ID → 命令。复用门禁的清单，不另造第二套真源。"""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {item["id"]: item["command"] for item in manifest["tests"]}


def run_test(command: list, project: str) -> int:
    """跑一条测试，返回退出码。非零就是变红了——那正是我们要的。

    **不让这次运行写字节码。** 它跑的是被破坏过的源码，写下来的缓存
    一旦被之后的运行当成新鲜的，整个系统就在执行被破坏的代码。
    见 `invalidate_bytecode` 的长注释。
    """
    env = dict(os.environ, HQ_GEO_PROJECT=project, PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run(
        command,
        cwd=SYSTEM,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode


def invalidate_bytecode(relative: str) -> list:
    """删掉 `relative` 这个源码对应的字节码缓存，返回删掉的路径。

    **这是 2026-09-30 抓到的一个真 bug，两头都能骗人。**

    CPython 判断 `__pycache__` 里的 `.pyc` 还能不能用，只看两个数：
    源文件的 **mtime** 和 **字节数**。canary 的破坏方式恰好两头都能撞上：

    - 破坏常常**不改长度**（`MERGE_DELTA_E = 2.5` → `= 0.0`，都是 19 字节）；
    - 写回发生在同一个 mtime 秒内（文件系统的 mtime 精度就是秒）。

    于是还原之后，缓存里那份**被破坏的**字节码仍然被判为新鲜，
    `PYTHONDONTWRITEBYTECODE` 也拦不住——它是之前那次运行写下的。

    两个方向都害人：

    | 方向 | 表现 |
    |---|---|
    | 破坏时撞上旧缓存 | 破坏没生效，断言被误报成**空转**（假红） |
    | 还原后撞上坏缓存 | 之后的每次测试都在跑**被破坏的代码**，门禁绿得毫无意义 |

    第二种更糟：它把「这条断言守住了」变成一句谎话，而**没有任何信号**。
    实测就是它——一次 canary 之后 `test_palette.py` 持续报错，
    磁盘上 `MERGE_DELTA_E` 明明是 `2.5`，运行时读到的却是 `0.0`，
    `git status` 干干净净。**只有把 `__pycache__` 里那份记录（`src_mtime` / `src_size`）
    和源码对起来看，才知道它跑的是另一个文件。**

    所以破坏前后各清一次。两次各挡一种情况，不是重复：
    破坏前那次挡「旧缓存让破坏没生效」，还原后那次挡「被破坏的运行写下了坏缓存」。
    """
    # 两边都 resolve：macOS 上 `/tmp` 是 `/private/tmp` 的软链，
    # 只 resolve 一边的话 `relative_to` 会抛 ValueError（纯字符串比较，不看软链）。
    root = SYSTEM.resolve()
    source = (root / relative).resolve()
    cache = source.parent / "__pycache__"
    if not cache.is_dir():
        return []
    removed = []
    for candidate in sorted(cache.glob(f"{source.stem}.*.pyc")):
        candidate.unlink()
        removed.append(str(candidate.relative_to(root)))
    return removed


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
    args.project = resolve_project(args.project)

    if not (Path(args.project) / MARKER).is_file():
        print(f"这里不是 hq-geo 项目根（没有 {MARKER}）：{args.project}")
        print("路径给错时，测试会全部报错退出——而 canary 把非零退出当成「变红」，")
        print("于是你会看到一整片假红。先确认 --project 指向项目根，再跑。")
        return 1

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

        # 破坏之前先清一次：如果磁盘上躺着一份**原文**的字节码，
        # 而这次破坏又恰好没改长度、又落在同一 mtime 秒里，
        # CPython 会拿旧字节码跑——破坏根本没生效，于是报成「空转」。
        # 那是假红，和假绿一样害人。
        try:
            for name in originals:
                invalidate_bytecode(name)

            for name, content in apply_edits(originals, case["edits"]).items():
                (SYSTEM / name).write_text(content, encoding="utf-8")
            code = run_test(commands[case["test"]], args.project)
        finally:
            for name, content in originals.items():
                (SYSTEM / name).write_text(content, encoding="utf-8")
            # 再清一次：万一上面那道 `PYTHONDONTWRITEBYTECODE` 被削弱或去掉，
            # 被破坏的那次运行就会写下坏字节码；还原时源码通常长度不变、
            # 又落在同一秒内，那份坏缓存会被判为新鲜——只有这里能清掉它。
            for name in originals:
                invalidate_bytecode(name)

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
