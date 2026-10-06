#!/usr/bin/env python3
"""canary 工具的回归测试。

canary 自己也会坏。它坏掉的方式很隐蔽：不再真的破坏被测对象，
于是每条断言都「通过」——而它本该报告的是「这条断言是空转的」。
一个坏掉的 canary 比没有 canary 更糟，它会给出虚假的信心。

2026-09-28 它真的坏过一次：只替换第一次出现，而关键词在被断言的
那一节里出现两次，9 条里 5 条被它误判为「不是空转的」。
下面第一条测试守的就是这个。
"""

import importlib.util
import os
import py_compile
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("canary", ROOT / "test/tools/canary.py")
CANARY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CANARY)


class ApplyEditsTests(unittest.TestCase):
    def test_replaces_every_occurrence_not_just_the_first(self):
        """同一个词在文件里出现两次时，两次都要换掉。

        只换第一次的话，第二次还在，断言照样绿——破坏不干净，
        canary 就会把空转的断言误报成健康的。
        """
        originals = {"doc.md": "受众坐标是产出。没有受众坐标就写不出核心判断。"}
        edits = [{"file": "doc.md", "find": "受众坐标", "replace": "读者对象"}]
        result = CANARY.apply_edits(originals, edits)
        self.assertNotIn("受众坐标", result["doc.md"])
        self.assertEqual(result["doc.md"], "读者对象是产出。没有读者对象就写不出核心判断。")

    def test_edits_across_multiple_files(self):
        """一条破坏点可以跨文件——去掉一个概念，要在它出现的每个地方都去掉。"""
        originals = {"a.md": "`dbs-jtbd`", "b.md": "`dbs-jtbd`"}
        edits = [
            {"file": "a.md", "find": "`dbs-jtbd`", "replace": "`dbs-hook`"},
            {"file": "b.md", "find": "`dbs-jtbd`", "replace": "`dbs-hook`"},
        ]
        result = CANARY.apply_edits(originals, edits)
        self.assertEqual(result["a.md"], "`dbs-hook`")
        self.assertEqual(result["b.md"], "`dbs-hook`")

    def test_does_not_mutate_the_originals(self):
        """原文必须原样保留——还原要靠它，改了就恢复不回去了。"""
        originals = {"doc.md": "受众坐标"}
        CANARY.apply_edits(originals, [{"file": "doc.md", "find": "受众坐标", "replace": "读者"}])
        self.assertEqual(originals["doc.md"], "受众坐标")


class StaleEditsTests(unittest.TestCase):
    def test_reports_edit_whose_text_is_gone(self):
        """文档改了、破坏点找不到时，必须报出来。

        不报的话这条 canary 会一直「通过」，而它其实什么都没破坏。
        """
        originals = {"doc.md": "这里没有那行字"}
        edits = [{"file": "doc.md", "find": "受众坐标", "replace": "读者"}]
        self.assertEqual(CANARY.stale_edits(originals, edits), ["doc.md"])

    def test_healthy_edit_is_not_stale(self):
        originals = {"doc.md": "受众坐标"}
        edits = [{"file": "doc.md", "find": "受众坐标", "replace": "读者"}]
        self.assertEqual(CANARY.stale_edits(originals, edits), [])


class ResolveProjectTests(unittest.TestCase):
    """守的是「假红」——canary 会把它造出来的失败当成断言有效。

    2026-09-28 踩过：在项目目录里用 `--project .` 跑全量，测试固定以
    cwd=系统根 运行，相对路径在系统根解析，找不到项目就全部报错退出。
    canary 看到非零退出码，报的是「✓ 变红」——46 条全是假的。
    """

    def test_relative_path_is_resolved_before_any_subprocess(self):
        """相对路径必须在这里就转成绝对，否则会在系统根解析。"""
        self.assertEqual(CANARY.resolve_project("."), str(Path.cwd()))
        self.assertTrue(Path(CANARY.resolve_project(".")).is_absolute())

    def test_absolute_path_is_unchanged(self):
        """已经是绝对的，原样返回——不能把它当成相对路径再拼一次。"""
        absolute = str(ROOT / "test")
        self.assertEqual(CANARY.resolve_project(absolute), absolute)


def _load(source: Path, name: str):
    """按源码路径加载模块——走的是 CPython 正常的那条路，会读字节码缓存。

    项目里的测试就是这么加载 `measure_palette.py` 这类脚本的
    （`spec_from_file_location` + `exec_module`），所以这条路必须原样复现：
    绕过它，被测的就不是真实链路。
    """
    spec = importlib.util.spec_from_file_location(name, source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_cache(source: Path):
    """显式把源码编译成 `__pycache__` 里的字节码。

    **不能靠「import 一下缓存就有了」这个办法。** 那是靠环境的：
    `PYTHONDONTWRITEBYTECODE=1` 一开，解释器就不写缓存了——
    而这些测试正是跑在 canary 里，canary 给子进程设的就有这个变量
    （它必须设，见 `run_test`）。

    于是会出现最难看的一种测试：手敲绿、在 canary 里红。
    你会去怀疑被测对象，而其实只是环境不同。

    `py_compile` 是显式的，不受那个变量影响，测试因此和环境无关。
    """
    py_compile.compile(str(source), cfile=str(_cache_path(source)), doraise=True)


def _cache_path(source: Path) -> Path:
    return Path(importlib.util.cache_from_source(str(source)))


class BytecodeInvalidationTests(unittest.TestCase):
    """守的是 2026-09-30 抓到的真 bug：canary 还原源码后，留下被破坏版本的字节码。

    CPython 判断 `__pycache__` 里的 `.pyc` 还能不能用，只看两个数：
    源文件的 **mtime** 和 **字节数**。canary 的破坏方式恰好两头都撞得上——
    破坏常常不改长度（`MERGE_DELTA_E = 2.5` → `= 0.0`，都是 19 字节），
    而写回发生在同一个 mtime 秒内。

    后果比「测试报错」严重得多：还原之后，之后每一次测试都在跑**被破坏的代码**，
    而磁盘上的源码完全正确，`git status` 干干净净。门禁绿得毫无意义。

    第一次撞见时的现场：`test_palette.py` 持续失败，磁盘上 `MERGE_DELTA_E`
    明明是 `2.5`，运行时却读到 `0.0`。清掉 `__pycache__` 立刻恢复。
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self._original_system = CANARY.SYSTEM
        CANARY.SYSTEM = self.root

        # **把环境变量摘掉再测。** 这个类里有两条测试是关于
        # 「子进程写不写字节码」的，而 `run_test` 拼 env 用的是 `dict(os.environ, ...)`
        # ——父进程有什么，子进程就继承什么。
        #
        # canary 给子进程设了这个变量（它必须设），子进程再往下 spawn 时
        # 就白捡一份。于是在 canary 里测「有没有设这个变量」永远测不出区别：
        # 把设置那一行删掉，孙子进程照样不写字节码——**假绿**。
        #
        # 测试自己声明环境，而不是随环境摇摆。
        self._original_flag = os.environ.pop("PYTHONDONTWRITEBYTECODE", None)

    def tearDown(self):
        if self._original_flag is not None:
            os.environ["PYTHONDONTWRITEBYTECODE"] = self._original_flag
        CANARY.SYSTEM = self._original_system
        self._tmp.cleanup()

    def _write_same_length(self, source: Path, text: str, stamp: int):
        """改掉源码内容，但长度不变、mtime 也按回原来那个整数秒。

        这两件事同时成立，CPython 就会认定缓存是新鲜的——
        所以这个辅助函数造出来的正是 bug 的触发条件。
        """
        source.write_text(text, encoding="utf-8")
        os.utime(source, (stamp, stamp))

    def test_stale_bytecode_really_does_survive_a_same_length_edit(self):
        """先证明危险是真的：不改长度、不换 mtime 秒，缓存会骗过解释器。

        这条断言红了不代表代码坏了——代表**Python 的缓存策略变了**，
        底下那条测试的前提没了，得回来重看整个修法。
        """
        source = self.root / "probe.py"
        source.write_text("VALUE = 2.5\n", encoding="utf-8")
        stamp = int(source.stat().st_mtime)
        _write_cache(source)

        self.assertEqual(_load(source, "probe_a").VALUE, 2.5)
        self.assertTrue(list((self.root / "__pycache__").glob("probe.*.pyc")))

        self._write_same_length(source, "VALUE = 0.0\n", stamp)

        self.assertEqual(
            _load(source, "probe_b").VALUE,
            2.5,
            "缓存没生效——如果 CPython 改了校验方式，这条和下面的修法都要重看",
        )

    def test_invalidate_bytecode_makes_the_edit_visible_again(self):
        """清掉缓存之后，运行时读到的必须是真的那份源码。"""
        source = self.root / "probe.py"
        source.write_text("VALUE = 2.5\n", encoding="utf-8")
        stamp = int(source.stat().st_mtime)
        _write_cache(source)

        self._write_same_length(source, "VALUE = 0.0\n", stamp)
        CANARY.invalidate_bytecode("probe.py")

        self.assertEqual(_load(source, "probe_d").VALUE, 0.0)

    def test_reports_what_it_removed(self):
        """返回删掉的路径——静默清理出了问题就查不出来了。"""
        source = self.root / "probe.py"
        source.write_text("VALUE = 1\n", encoding="utf-8")
        _write_cache(source)

        removed = CANARY.invalidate_bytecode("probe.py")

        self.assertEqual(len(removed), 1)
        self.assertIn("probe.", removed[0])
        self.assertFalse(list((self.root / "__pycache__").glob("probe.*.pyc")))

    def test_leaves_other_modules_alone(self):
        """只清这一个源码的缓存。

        整个 `__pycache__` 一起删会让 canary 跑得慢很多，
        而它要跑的条目有一百多条。
        """
        for name in ("probe.py", "other.py"):
            (self.root / name).write_text("VALUE = 1\n", encoding="utf-8")
            _write_cache(self.root / name)
        self.assertTrue(list((self.root / "__pycache__").glob("other.*.pyc")))

        CANARY.invalidate_bytecode("probe.py")

        self.assertTrue(list((self.root / "__pycache__").glob("other.*.pyc")))

    def test_no_cache_directory_is_not_an_error(self):
        """源码从没被 import 过时没有 `__pycache__`——那是正常情况，不是故障。"""
        (self.root / "probe.py").write_text("VALUE = 1\n", encoding="utf-8")
        self.assertEqual(CANARY.invalidate_bytecode("probe.py"), [])

    def test_the_broken_run_never_writes_bytecode(self):
        """跑被破坏的源码时，一个字节码文件都不许落到磁盘上。

        这是比「事后清缓存」更靠前的一道闸：坏字节码**根本没被写出来**，
        就不存在之后哪一次运行把它当成新鲜的机会。
        事后清是针对这次运行之前就已经躺在磁盘上的旧缓存。
        """
        (self.root / "probe.py").write_text("VALUE = 1\n", encoding="utf-8")
        program = "import sys; sys.path.insert(0, %r); import probe" % str(self.root)

        code = CANARY.run_test([sys.executable, "-c", program], str(self.root))

        self.assertEqual(code, 0)
        cache = self.root / "__pycache__"
        written = sorted(cache.glob("probe.*.pyc")) if cache.is_dir() else []
        self.assertEqual(written, [], "子进程把字节码写下来了——下次运行会把它当成新鲜的")


if __name__ == "__main__":
    unittest.main()
