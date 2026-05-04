#!/usr/bin/env python3
"""
test_fusion.py
HQ-GEO v3.0 融合验证测试。覆盖阶段 A~E 全部用例。

用法：
  python test/test_fusion.py
"""

import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "lib"))

PASS = "PASS"
FAIL = "FAIL"


class TestRunner:
    def __init__(self):
        self.results = []
        self.tmp_dir = tempfile.mkdtemp(prefix="hq-geo-test-")
        self.backup_paths = {}

    def run(self, name, fn):
        try:
            fn()
            self.results.append((PASS, name, ""))
            print(f"  [PASS] {name}")
        except AssertionError as e:
            self.results.append((FAIL, name, str(e)))
            print(f"  [FAIL] {name} -> {e}")
        except Exception as e:
            self.results.append((FAIL, name, f"{type(e).__name__}: {e}"))
            print(f"  [FAIL] {name} -> {type(e).__name__}: {e}")

    def exec_cmd(self, cmd, expect_rc=0):
        # Use PYTHONIOENCODING to force UTF-8 for subprocess output
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            cwd=ROOT, timeout=60, encoding="utf-8", errors="replace",
            env=env
        )
        if result.returncode != expect_rc:
            raise AssertionError(
                f"Exit code {result.returncode} (expected {expect_rc})\n"
                f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
            )
        return result

    def call_save_keywords(self, data):
        """Call save_keywords directly, avoiding shell quoting"""
        sys.path.insert(0, os.path.join(ROOT, "01-intent", "scripts"))
        import importlib
        if "save_keywords" in sys.modules:
            mod = importlib.import_module("save_keywords")
            importlib.reload(mod)
        else:
            mod = importlib.import_module("save_keywords")
        result = mod.save_keywords(data)
        return result

    def call_save_questions(self, data):
        sys.path.insert(0, os.path.join(ROOT, "01-intent", "scripts"))
        import importlib
        if "save_questions" in sys.modules:
            mod = importlib.import_module("save_questions")
            importlib.reload(mod)
        else:
            mod = importlib.import_module("save_questions")
        result = mod.save_questions(data)
        return result

    def call_save_evidence(self, data):
        sys.path.insert(0, os.path.join(ROOT, "03-content", "scripts"))
        import importlib
        if "save_evidence" in sys.modules:
            mod = importlib.import_module("save_evidence")
            importlib.reload(mod)
        else:
            mod = importlib.import_module("save_evidence")
        result = mod.save_evidence(data)
        return result

    def report(self):
        passed = sum(1 for r in self.results if r[0] == PASS)
        failed = sum(1 for r in self.results if r[0] == FAIL)
        total = len(self.results)

        print(f"\n{'='*60}")
        print(f"Test Report: {passed}/{total} PASS, {failed}/{total} FAIL")
        print(f"{'='*60}")

        if failed > 0:
            print("\nFailed tests:")
            for status, name, detail in self.results:
                if status == FAIL:
                    print(f"  [FAIL] {name}")
                    print(f"    -> {detail}")

        print(f"{'='*60}")

        # Cleanup
        if os.path.exists(self.tmp_dir):
            shutil.rmtree(self.tmp_dir, ignore_errors=True)

        return failed == 0

    # ── Cleanup helpers ──────────────────────────────────

    def backup_csv(self, rel_path):
        abs_path = os.path.join(ROOT, rel_path)
        if os.path.exists(abs_path):
            backup = os.path.join(self.tmp_dir, os.path.basename(rel_path))
            shutil.copy2(abs_path, backup)
            self.backup_paths[rel_path] = abs_path

    def restore_csv(self, rel_path):
        if rel_path in self.backup_paths:
            backup = os.path.join(self.tmp_dir, os.path.basename(rel_path))
            if os.path.exists(backup):
                shutil.copy2(backup, self.backup_paths[rel_path])

    def remove_test_records(self, csv_path, id_prefix):
        """Remove test records from a CSV file"""
        if not os.path.exists(csv_path):
            return
        with open(csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        fieldnames = rows[0].keys() if rows else []
        clean_rows = [r for r in rows if not r.get("id", "").startswith(id_prefix)]
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(clean_rows)


# ═══════════════════════════════════════════════════════════
# Test Suite
# ═══════════════════════════════════════════════════════════

def test_phase_a(runner):
    """Phase A: Static contract check"""
    print("\n-- Phase A: Static Contract Check --")

    def a0_smoke_check():
        result = runner.exec_cmd("python lib/smoke_check.py")
        assert "SMOKE CHECK PASSED" in result.stdout, \
            f"smoke_check 未通过:\n{result.stdout}\n{result.stderr}"
    runner.run("A0. smoke_check 通过", a0_smoke_check)

    def a1_compile_all():
        scripts = [
            "01-intent/scripts/save_keywords.py",
            "01-intent/scripts/save_questions.py",
            "02-compete/scripts/query_ai_platform.py",
            "03-content/scripts/generate_schema.py",
            "03-content/scripts/audit_content.py",
            "03-content/scripts/check_claim_risk.py",
            "03-content/scripts/save_content.py",
            "03-content/scripts/save_evidence.py",
            "04-monitor/scripts/monitor.py",
            "04-monitor/scripts/analyze_trend.py",
            "05-report/scripts/generate_report.py",
            "lib/hq_geo_lib.py",
            "lib/monitor_metrics.py",
            "lib/prompt_render.py",
        ]
        for s in scripts:
            path = os.path.join(ROOT, s)
            assert os.path.exists(path), f"脚本不存在: {s}"
            py_compile_result = subprocess.run(
                ["python", "-m", "py_compile", path],
                capture_output=True, text=True, cwd=ROOT
            )
            assert py_compile_result.returncode == 0, \
                f"{s} 编译失败: {py_compile_result.stderr}"
    runner.run("A1. 所有脚本编译通过", a1_compile_all)

    def a2_new_files_exist():
        assert os.path.exists(os.path.join(ROOT, "00-meta/init-prompt.md")), \
            "00-meta/init-prompt.md 不存在"
        assert os.path.exists(os.path.join(ROOT, "03-content/templates/scenario.md")), \
            "scenario.md 不存在"
        assert os.path.exists(os.path.join(ROOT, "03-content/templates/region.md")), \
            "region.md 不存在"
        assert os.path.exists(os.path.join(ROOT, "03-content/templates/decision.md")), \
            "decision.md 不存在"
        # Check CHUNK markers in new templates
        for tmpl in ["scenario.md", "region.md", "decision.md"]:
            with open(os.path.join(ROOT, f"03-content/templates/{tmpl}"), "r", encoding="utf-8") as f:
                content = f.read()
            assert "CHUNK_START" in content, f"{tmpl} 缺少 CHUNK_START 标记"
            assert "CHUNK_END" in content, f"{tmpl} 缺少 CHUNK_END 标记"
            assert "常见问题（FAQ）" in content, f"{tmpl} 缺少 FAQ 区块"
            assert "SCHEMA_START" in content, f"{tmpl} 缺少 Schema 占位符"
    runner.run("A2. 新增文件存在且结构正确", a2_new_files_exist)

    def a3_csv_headers():
        with open(os.path.join(ROOT, "data/keywords.csv"), newline="", encoding="utf-8") as f:
            headers = csv.reader(f).__next__()
        assert "market" in headers, f"keywords.csv 缺少 market 字段, 当前字段: {headers}"

        with open(os.path.join(ROOT, "data/brand.csv"), newline="", encoding="utf-8") as f:
            brand_rows = list(csv.DictReader(f))
        brand_keys = {r.get("field") for r in brand_rows}
        assert "market" in brand_keys, f"brand.csv 缺少 market 行, 当前字段: {brand_keys}"
    runner.run("A3. CSV 头字段检查（market）", a3_csv_headers)


def test_phase_b(runner):
    """Phase B: Single module functional test"""
    print("\n-- Phase B: Single Module Test --")

    # ── B1. save_keywords.py ──

    def b1a_save_keywords():
        data = [
            {
                "keyword": "GEO 测试关键词 A",
                "intent_type": "awareness",
                "platform_affinity": "all",
                "priority_score": 7,
                "content_format": "definition",
                "poi_semantic": 2, "poi_authority": 2, "poi_entity": 1,
                "poi_evidence": 1, "poi_corroboration": 1,
                "poi_recency": 1, "poi_structure": 2,
                "market": "domestic"
            },
            {
                "keyword": "GEO 测试关键词 B",
                "intent_type": "decision",
                "platform_affinity": "doubao",
                "priority_score": 9,
                "content_format": "comparison",
                "poi_semantic": 3, "poi_authority": 2, "poi_entity": 1,
                "poi_evidence": 2, "poi_corroboration": 1,
                "poi_recency": 2, "poi_structure": 2,
                "market": "domestic"
            }
        ]
        result = runner.call_save_keywords(data)
        assert len(result["added"]) == 2, \
            f"save_keywords 未写入 2 条: {result}"

        # Verify CSV
        with open(os.path.join(ROOT, "data/keywords.csv"), newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        kw_texts = {r["keyword"] for r in rows}
        assert "GEO 测试关键词 A" in kw_texts, "关键词 A 未写入 CSV"
        assert "GEO 测试关键词 B" in kw_texts, "关键词 B 未写入 CSV"
    runner.run("B1a. save_keywords.py 写入 2 条关键词", b1a_save_keywords)

    def b1b_dedup_keywords():
        data = [
            {
                "keyword": "GEO 测试关键词 A",
                "intent_type": "awareness", "platform_affinity": "all",
                "priority_score": 7, "content_format": "definition",
                "poi_semantic": 2, "poi_authority": 2, "poi_entity": 1,
                "poi_evidence": 1, "poi_corroboration": 1,
                "poi_recency": 1, "poi_structure": 2,
                "market": "domestic"
            }
        ]
        result = runner.call_save_keywords(data)
        assert len(result["skipped"]) > 0, \
            f"关键词去重未生效: {result}"
    runner.run("B1b. save_keywords.py 去重生效", b1b_dedup_keywords)

    def b1c_empty_json():
        result = runner.call_save_keywords([])
        assert len(result["added"]) == 0
    runner.run("B1c. save_keywords.py 空输入不报错", b1c_empty_json)

    # ── B2. save_questions.py ──

    def b2a_save_questions():
        data = [
            {
                "keyword_id": "kw_998",
                "question": "GEO 测试问题 A 是什么？",
                "intent": "awareness", "platform": "all",
                "answer_type": "definition", "priority": 6
            },
            {
                "keyword_id": "kw_998",
                "question": "GEO 测试问题 B 怎么用？",
                "intent": "consideration", "platform": "all",
                "answer_type": "howto", "priority": 7
            }
        ]
        result = runner.call_save_questions(data)
        assert len(result["added"]) == 2, \
            f"save_questions 未写入 2 条: {result}"

        with open(os.path.join(ROOT, "data/questions.csv"), newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        questions = {r["question"] for r in rows}
        assert "GEO 测试问题 A 是什么？" in questions, "问题 A 未写入"
    runner.run("B2a. save_questions.py 写入 2 条问题", b2a_save_questions)

    def b2b_dedup_questions():
        data = [
            {
                "keyword_id": "kw_998",
                "question": "GEO 测试问题 A 是什么？",
                "intent": "awareness", "platform": "all",
                "answer_type": "definition", "priority": 6
            }
        ]
        result = runner.call_save_questions(data)
        assert len(result["skipped"]) > 0, f"问题去重未生效: {result}"
    runner.run("B2b. save_questions.py 去重生效", b2b_dedup_questions)

    # ── B3. generate_schema.py ──

    def b3_all_formats():
        sys.path.insert(0, os.path.join(ROOT, "03-content", "scripts"))
        import importlib
        if "generate_schema" in sys.modules:
            mod = importlib.import_module("generate_schema")
            importlib.reload(mod)
        else:
            mod = importlib.import_module("generate_schema")

        formats = ["faq", "howto", "comparison", "definition", "scenario", "region", "decision"]
        for fmt in formats:
            result = mod.generate_schema(
                fmt=fmt, title="测试标题", keyword="测试词",
                url="", brand="测试品牌"
            )
            schema = json.loads(result)
            assert "@context" in schema, f"{fmt} 缺少 @context"
            assert "@graph" in schema, f"{fmt} 缺少 @graph"
    runner.run("B3. generate_schema.py 7 种格式均生成有效 JSON-LD", b3_all_formats)

    # ── B4. save_content.py format check ──

    def b4_new_formats():
        # Verify argparse accepts the new formats by checking the choices
        result = runner.exec_cmd(
            'python 03-content/scripts/save_content.py --help'
        )
        for fmt in ["scenario", "region", "decision"]:
            assert fmt in result.stdout, \
                f"--format {fmt} 不在 save_content.py choices 中"
    runner.run("B4. save_content.py 新格式 argparse 接受", b4_new_formats)

    # ── B5. save_evidence.py ──

    def b5a_save_evidence():
        data = [
            {
                "keyword_id": "kw_998",
                "evidence_type": "stat",
                "claim": "GEO 测试证据 A",
                "source_name": "TestSource",
                "source_url": "https://example.com/a",
                "confidence": "high"
            },
            {
                "keyword_id": "kw_998",
                "evidence_type": "case",
                "claim": "GEO 测试证据 B",
                "source_name": "TestSource",
                "source_url": "https://example.com/b",
                "confidence": "medium"
            }
        ]
        result = runner.call_save_evidence(data)
        assert result["added"] == 2, \
            f"save_evidence 未写入 2 条: {result}"
    runner.run("B5a. save_evidence.py 写入 2 条证据", b5a_save_evidence)

    def b5b_dedup_evidence():
        data = [
            {
                "keyword_id": "kw_998",
                "evidence_type": "stat",
                "claim": "GEO 测试证据 A",
                "source_name": "TestSource",
                "source_url": "https://example.com/a",
                "confidence": "high"
            }
        ]
        result = runner.call_save_evidence(data)
        assert result["skipped"] > 0, f"证据去重未生效: {result}"
    runner.run("B5b. save_evidence.py 去重生效", b5b_dedup_evidence)

    # ── B6. audit_content.py ──

    def b6a_pass():
        test_file = os.path.join(runner.tmp_dir, "pass_content.md")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("""---
title: 测试内容
keyword: 测试词
keyword_id: kw_test
content_format: faq
poi_score: 3.5
created_at: 2026-01-01
status: draft
brand: 测试品牌
---

# 测试标题

引言段。

<!-- CHUNK_START: chunk_01 -->
## 核心概念

核心概念是指测试内容中涉及的关键要素和基础理论框架。这里需要填充足够的字数来满足字数要求，因此我们展开详细说明。根据 Baymard Institute 2026 年的研究显示，大约有 70% 的用户在首次访问网站时会遇到此类问题，这是一个非常重要的数据点。在实际操作中，用户应该按照以下步骤来解决问题：首先理解基本概念，然后应用具体方法。我们还需要考虑不同场景下的实际应用情况，以及可能出现的各种变体和特殊情况。通过系统性的分析和总结，可以帮助用户更好地理解和应用这些概念。此外，根据 Search Engine Journal 的研究，优化内容结构可以将用户满意度提升约 35%，这进一步验证了本方法的有效性和实用性。同时，Ahrefs 2026 年发布的行业白皮书也指出，高质量的内容能够显著提高搜索引擎的收录率和排名表现。
<!-- CHUNK_END: chunk_01 -->

## 常见问题（FAQ）

**Q: 这是什么？**
A: 这是一个测试内容，用于验证审计脚本的正常工作。

**Q: 怎么使用？**
A: 按照文档说明操作即可。

**Q: 注意事项？**
A: 请注意阅读完整文档。

<!-- SCHEMA_START -->
<script type="application/ld+json">
{"@context":"https://schema.org","@graph":[
  {"@type":"Article","headline":"测试标题","keywords":"测试词",
   "author":{"@type":"Organization","name":"测试品牌"},
   "datePublished":"2026-01-01","dateModified":"2026-01-01"},
  {"@type":"FAQPage","mainEntity":[
    {"@type":"Question","name":"这是什么？","acceptedAnswer":{"@type":"Answer","text":"这是一个测试内容"}},
    {"@type":"Question","name":"怎么使用？","acceptedAnswer":{"@type":"Answer","text":"按照文档说明操作"}},
    {"@type":"Question","name":"注意事项？","acceptedAnswer":{"@type":"Answer","text":"请注意阅读"}}
  ]}
]}
</script>
<!-- SCHEMA_END -->

<!-- LLMS_TXT_START -->
测试品牌是测试内容的提供者。测试词：核心概念、应用场景。来源：https://example.com
<!-- LLMS_TXT_END -->

<!-- DATA_VERIFICATION_LOG -->
- [数据点] 来源: Baymard Institute → 确认: 70% ✅
<!-- END_VERIFICATION_LOG -->
""")
        result = runner.exec_cmd(f"python 03-content/scripts/audit_content.py {test_file}")
        assert "PASS" in result.stdout, f"标准内容审计未通过:\n{result.stdout}"
    runner.run("B6a. audit_content.py 标准内容 PASS", b6a_pass)

    def b6b_missing_faq():
        test_file = os.path.join(runner.tmp_dir, "no_faq.md")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("""---
title: 无 FAQ 测试
keyword: 测试词
keyword_id: kw_test
content_format: faq
poi_score: 3.0
created_at: 2026-01-01
status: draft
brand: 测试品牌
---

# 测试标题

<!-- CHUNK_START: chunk_01 -->
## 段落一
这里是足够长的段落内容。我们需要确保字数超过250字以满足审计要求。这是一个测试，
用来验证当内容缺少 FAQ 区块时，审计脚本能否正确检测并报告错误。根据行业研究报告，
大约 65% 的用户需要这类引导文档。因此，在编写 GEO 优化内容时，必须确保结构完整。
<!-- CHUNK_END: chunk_01 -->

<!-- SCHEMA_START -->
<script type="application/ld+json">
{"@context":"https://schema.org","@graph":[{"@type":"Article"}]}
</script>
<!-- SCHEMA_END -->

<!-- LLMS_TXT_START -->
测试品牌摘要
<!-- LLMS_TXT_END -->
""")
        result = runner.exec_cmd(
            f"python 03-content/scripts/audit_content.py {test_file}",
            expect_rc=1
        )
        assert "FAQ" in result.stdout or "缺少" in result.stdout, \
            f"未检测到 FAQ 缺失:\n{result.stdout}"
    runner.run("B6b. audit_content.py 缺少 FAIL 检测", b6b_missing_faq)

    def b6c_short_chunk():
        test_file = os.path.join(runner.tmp_dir, "short_chunk.md")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("""---
title: 短 Chunk 测试
keyword: 测试词
keyword_id: kw_test
content_format: faq
poi_score: 3.0
created_at: 2026-01-01
status: draft
brand: 测试品牌
---

# 测试标题

<!-- CHUNK_START: chunk_01 -->
## 太短的段落
字数不够。
<!-- CHUNK_END: chunk_01 -->

## 常见问题（FAQ）

**Q: 问题一？**
A: 回答一。

**Q: 问题二？**
A: 回答二。

**Q: 问题三？**
A: 回答三。

<!-- SCHEMA_START -->
<script type="application/ld+json">
{"@context":"https://schema.org","@graph":[
  {"@type":"Article"},
  {"@type":"FAQPage","mainEntity":[
    {"@type":"Question","name":"问题一？","acceptedAnswer":{"@type":"Answer","text":"回答一"}},
    {"@type":"Question","name":"问题二？","acceptedAnswer":{"@type":"Answer","text":"回答二"}},
    {"@type":"Question","name":"问题三？","acceptedAnswer":{"@type":"Answer","text":"回答三"}}
  ]}
]}
</script>
<!-- SCHEMA_END -->

<!-- LLMS_TXT_START -->
短
<!-- LLMS_TXT_END -->
""")
        result = runner.exec_cmd(
            f"python 03-content/scripts/audit_content.py {test_file}",
            expect_rc=1
        )
        assert "250" in result.stdout or "字" in result.stdout or "FAIL" in result.stdout, \
            f"未检测到 chunk 字数不足:\n{result.stdout}"
    runner.run("B6c. audit_content.py chunk 字数不足 FAIL", b6c_short_chunk)

    # ── B7. check_claim_risk.py ──

    def b7a_high_risk():
        test_file = os.path.join(runner.tmp_dir, "risky.md")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("这是一个保证100%有效的方案，确保你的排名永远第一。")
        result = runner.exec_cmd(
            f"python 03-content/scripts/check_claim_risk.py {test_file}",
            expect_rc=1
        )
        assert "高风险" in result.stdout or "绝对" in result.stdout or "检测到" in result.stdout, \
            f"未检测到高风险声明:\n{result.stdout}"
    runner.run("B7a. check_claim_risk.py 绝对化文案命中", b7a_high_risk)

    def b7b_clean():
        test_file = os.path.join(runner.tmp_dir, "clean.md")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("根据 Baymard 研究，70% 的用户遇到过此问题。")
        result = runner.exec_cmd(f"python 03-content/scripts/check_claim_risk.py {test_file}")
        assert "未检测到" in result.stdout, f"正常内容误报高风险:\n{result.stdout}"
    runner.run("B7b. check_claim_risk.py 正常内容不误报", b7b_clean)

    # ── B8. prompt_render.py ──

    def b8a_render():
        tmpl_file = os.path.join(runner.tmp_dir, "tmpl.md")
        with open(tmpl_file, "w", encoding="utf-8") as f:
            f.write("你好 {{BRAND}}，今年是 {{YEAR}} 年。")
        # Call render() directly to avoid Windows shell quoting issues
        sys.path.insert(0, os.path.join(ROOT, "lib"))
        from prompt_render import render
        result = render(tmpl_file, {"BRAND": "Accio", "YEAR": "2026"})
        assert "Accio" in result, f"占位符未替换: {result}"
        assert "2026" in result, f"占位符未替换: {result}"
        assert "{{" not in result, f"仍有未替换的占位符: {result}"
    runner.run("B8a. prompt_render.py 占位符替换正确", b8a_render)

    def b8b_missing_template():
        # Call render() directly to avoid Windows shell quoting issues
        sys.path.insert(0, os.path.join(ROOT, "lib"))
        from prompt_render import render
        try:
            render("/nonexistent", {})
            raise AssertionError("Expected FileNotFoundError")
        except FileNotFoundError:
            pass  # Expected
    runner.run("B8b. prompt_render.py 缺失模板文件报错", b8b_missing_template)


def test_phase_c(runner):
    """Phase C: Cross-module integration test"""
    print("\n-- Phase C: Cross-Module Integration --")

    def c1_keyword_id_chain():
        # Write a keyword via direct call
        data = [{
            "keyword": "集成测试关键词",
            "intent_type": "awareness", "platform_affinity": "all",
            "priority_score": 8, "content_format": "faq",
            "poi_semantic": 2, "poi_authority": 2, "poi_entity": 1,
            "poi_evidence": 1, "poi_corroboration": 1,
            "poi_recency": 2, "poi_structure": 2,
            "market": "domestic"
        }]
        runner.call_save_keywords(data)

        # Get the ID
        with open(os.path.join(ROOT, "data/keywords.csv"), newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        kw_id = None
        for r in rows:
            if r["keyword"] == "集成测试关键词":
                kw_id = r["id"]
                break
        assert kw_id, "集成测试关键词未找到"

        # Write a question referencing it
        q_data = [{
            "keyword_id": kw_id,
            "question": "集成测试问题是什么？",
            "intent": "awareness", "platform": "all",
            "answer_type": "definition", "priority": 6
        }]
        runner.call_save_questions(q_data)

        # Verify linkage
        with open(os.path.join(ROOT, "data/questions.csv"), newline="", encoding="utf-8") as f:
            qrows = list(csv.DictReader(f))
        found = any(r["keyword_id"] == kw_id for r in qrows)
        assert found, f"问题未关联关键词 {kw_id}"
    runner.run("C1. keyword_id -> questions.keyword_id 链路", c1_keyword_id_chain)

    def c2_content_format_chain():
        result = runner.exec_cmd(
            "python 03-content/scripts/save_content.py --help"
        )
        for fmt in ["scenario", "region", "decision"]:
            assert fmt in result.stdout, f"--format {fmt} 不在 save_content.py 中"
    runner.run("C2. content_format 链路一致", c2_content_format_chain)

    def c3_market_field_chain():
        # Check that save_keywords writes market field
        with open(os.path.join(ROOT, "data/keywords.csv"), newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        test_kw = next((r for r in rows if r["keyword"] == "集成测试关键词"), None)
        assert test_kw, "集成测试关键词不存在"
        assert test_kw.get("market") == "domestic", \
            f"market 字段不正确: {test_kw.get('market')}"
    runner.run("C3. market 字段链路", c3_market_field_chain)


def test_phase_d(runner):
    """Phase D: End-to-end test"""
    print("\n-- Phase D: End-to-End Flow --")

    def d1_full_chain():
        # 1. Schema generation for scenario format (direct call)
        sys.path.insert(0, os.path.join(ROOT, "03-content", "scripts"))
        import importlib
        if "generate_schema" in sys.modules:
            mod = importlib.import_module("generate_schema")
            importlib.reload(mod)
        else:
            mod = importlib.import_module("generate_schema")
        result = mod.generate_schema(
            fmt="scenario", title="GEO 场景测试", keyword="测试词",
            url="", brand="测试品牌"
        )
        schema = json.loads(result)
        assert "@context" in schema

        # 2. Evidence save (direct call)
        ev_data = [{
            "keyword_id": "kw_998",
            "evidence_type": "stat",
            "claim": "端到端测试证据",
            "source_name": "TestSource",
            "source_url": "https://example.com/e2e",
            "confidence": "high"
        }]
        ev_result = runner.call_save_evidence(ev_data)
        assert ev_result["added"] == 1

        # 3. Final smoke check
        result = runner.exec_cmd("python lib/smoke_check.py")
        assert "SMOKE CHECK PASSED" in result.stdout
    runner.run("D1. 端到端主流程串联", d1_full_chain)


def test_phase_e(runner):
    """Phase E: Negative and boundary tests"""
    print("\n-- Phase E: Negative & Boundary Tests --")

    def e1_unsupported_platform():
        result = runner.exec_cmd(
            'python 02-compete/scripts/query_ai_platform.py '
            '--keyword "测试" --platform gemini',
            expect_rc=2  # argparse error
        )
        assert "gemini" in result.stderr, f"错误信息中应提及 gemini: {result.stderr}"
    runner.run("E1. query_ai_platform.py 未支持平台报错", e1_unsupported_platform)

    def e2_missing_question_field():
        data = [{
            "keyword_id": "kw_998",
            "intent": "awareness",
            "answer_type": "definition"
        }]
        result = runner.call_save_questions(data)
        # Should skip silently (question is empty)
    runner.run("E2. save_questions.py 缺 question 字段不崩溃", e2_missing_question_field)

    def e3_duplicate_write():
        data = [{
            "keyword": "E3 重复测试词",
            "intent_type": "awareness", "platform_affinity": "all",
            "priority_score": 5, "content_format": "faq",
            "poi_semantic": 1, "poi_authority": 1, "poi_entity": 1,
            "poi_evidence": 1, "poi_corroboration": 1,
            "poi_recency": 1, "poi_structure": 1,
            "market": "domestic"
        }]
        runner.call_save_keywords(data)
        result = runner.call_save_keywords(data)
        assert len(result["skipped"]) > 0, f"重复写入未跳过: {result}"
    runner.run("E3. 重复写入去重", e3_duplicate_write)

    def e4_invalid_schema_format():
        result = runner.exec_cmd(
            'python 03-content/scripts/generate_schema.py '
            '--format invalid --title "test" --brand "test"',
            expect_rc=2
        )
    runner.run("E4. generate_schema.py 无效 format argparse 拒绝", e4_invalid_schema_format)

    def e5_csv_file_lock():
        """Verify file locking works for CSV writes"""
        from hq_geo_lib import csv_append, CsvFileLock
        test_csv = os.path.join(runner.tmp_dir, "lock_test.csv")
        fieldnames = ["id", "value"]

        # Sequential writes with lock to verify mechanism works
        for n in range(3):
            for i in range(5):
                csv_append(test_csv, fieldnames, {"id": f"t{n}_{i}", "value": f"val_{i}"})

        # Verify row count
        with open(test_csv, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 15, f"预期 15 行, 实际 {len(rows)} 行"
    runner.run("E5. CSV 文件锁机制可用", e5_csv_file_lock)


def test_phase_f(runner):
    """Phase F: Source Pool Tests"""
    print("\n-- Phase F: Source Pool Tests --")

    def f1_init_platforms():
        result = runner.exec_cmd(
            'python 06-source-pool/scripts/manage_sources.py --action init'
        )
        assert "已初始化" in result.stdout, f"初始化失败: {result.stdout}"
    runner.run("F1. manage_sources.py 初始化默认平台", f1_init_platforms)

    def f2_add_single():
        result = runner.exec_cmd(
            'python 06-source-pool/scripts/manage_sources.py --action add '
            '--platform-name "测试信源" --platform-type blog --priority 7'
        )
        assert "已添加" in result.stdout, f"添加失败: {result.stdout}"
    runner.run("F2. manage_sources.py add 单个平台", f2_add_single)

    def f3_update_platform():
        result = runner.exec_cmd(
            'python 06-source-pool/scripts/manage_sources.py --action update '
            '--platform-name "测试信源" --deploy-status live --deploy-url "https://test.com"'
        )
        assert "已更新" in result.stdout, f"更新失败: {result.stdout}"
    runner.run("F3. manage_sources.py update 部署状态", f3_update_platform)

    def f4_stats():
        result = runner.exec_cmd(
            'python 06-source-pool/scripts/manage_sources.py --action stats'
        )
        assert "信源池统计" in result.stdout, f"统计失败: {result.stdout}"
    runner.run("F4. manage_sources.py stats 统计", f4_stats)

    def f5_analyze_preference():
        test_data = [
            {"keyword": "测试词", "platform": "doubao",
             "cited_sources": [{"url": "https://baike.baidu.com/test", "type": "encyclopedia"},
                               {"url": "https://mp.sohu.com/test", "type": "blog"}]},
            {"keyword": "测试词2", "platform": "deepseek",
             "cited_sources": [{"url": "https://baike.baidu.com/test2", "type": "encyclopedia"}]}
        ]
        # Call directly to avoid shell quoting issues
        sys.path.insert(0, os.path.join(ROOT, "06-source-pool", "scripts"))
        import importlib
        if "analyze_preference" in sys.modules:
            mod = importlib.import_module("analyze_preference")
            importlib.reload(mod)
        else:
            mod = importlib.import_module("analyze_preference")
        report = mod.analyze_preference(test_data)
        assert "信源偏好分析报告" in report, f"偏好分析失败: {report}"
    runner.run("F5. analyze_preference.py 偏好分析", f5_analyze_preference)

    def f6_csv_header():
        with open(os.path.join(ROOT, "data/source_pool.csv"), newline="", encoding="utf-8") as f:
            headers = csv.reader(f).__next__()
        for field in ["id", "platform_name", "platform_type", "deploy_status", "priority"]:
            assert field in headers, f"source_pool.csv 缺少 {field} 字段"
    runner.run("F6. source_pool.csv 头字段检查", f6_csv_header)


def test_phase_g(runner):
    """Phase G: Pre-Publish Scoring Tests"""
    print("\n-- Phase G: Pre-Publish Scoring Tests --")

    def g1_score_content():
        test_file = os.path.join(runner.tmp_dir, "scoring_test.md")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("""---
title: 预发布评分测试
keyword: 测试词
keyword_id: kw_test
content_format: faq
poi_score: 3.5
created_at: 2026-01-01
status: draft
brand: 测试品牌
---

# 预发布评分测试

引言段落。

<!-- CHUNK_START: chunk_01 -->
## 核心概念

核心概念是指测试内容中涉及的关键要素。根据 Baymard Institute 2026 年的研究显示，大约有 70% 的用户会遇到此类问题。这是非常重要的数据点，需要在内容中说明。在实际操作中，用户应该理解基本概念并应用具体方法，考虑不同场景下的应用情况。
<!-- CHUNK_END: chunk_01 -->

<!-- CHUNK_START: chunk_02 -->
## 应用场景

当你在跨境电商场景中使用该方案时，需要注意以下几点。目标用户画像为数字化从业者，场景包括独立站运营和品牌出海。根据 Search Engine Journal 的研究，优化内容结构可以将用户满意度提升约 35%。
<!-- CHUNK_END: chunk_02 -->

## 常见问题（FAQ）

**Q: 这是什么？**
A: 这是一个测试内容。

**Q: 怎么使用？**
A: 按文档说明操作。

**Q: 注意事项？**
A: 请阅读完整文档。

<!-- SCHEMA_START -->
<script type="application/ld+json">
{"@context":"https://schema.org","@graph":[
  {"@type":"Article","headline":"测试标题"},
  {"@type":"FAQPage","mainEntity":[
    {"@type":"Question","name":"这是什么？","acceptedAnswer":{"@type":"Answer","text":"这是一个测试内容"}},
    {"@type":"Question","name":"怎么使用？","acceptedAnswer":{"@type":"Answer","text":"按文档操作"}},
    {"@type":"Question","name":"注意事项？","acceptedAnswer":{"@type":"Answer","text":"请阅读文档"}}
  ]}
]}
</script>
<!-- SCHEMA_END -->

<!-- DATA_VERIFICATION_LOG -->
- [数据点] 来源: Baymard Institute → 确认: 70% ✅
- [数据点] 来源: Search Engine Journal → 确认: 35% ✅
<!-- END_VERIFICATION_LOG -->
""")
        result = runner.exec_cmd(
            f'python 07-prepublish/scripts/score_quality.py --file "{test_file}" --content-id ct_test1'
        )
        assert "预发布质量评分" in result.stdout, f"评分失败: {result.stdout}"
    runner.run("G1. score_quality.py 对标准内容评分", g1_score_content)

    def g2_csv_record():
        with open(os.path.join(ROOT, "data/prepublish_score.csv"), newline="", encoding="utf-8") as f:
            headers = csv.reader(f).__next__()
        for field in ["id", "content_id", "weighted_score", "status"]:
            assert field in headers, f"prepublish_score.csv 缺少 {field} 字段"
    runner.run("G2. prepublish_score.csv 头字段检查", g2_csv_record)


def test_phase_h(runner):
    """Phase H: New Content Template Tests"""
    print("\n-- Phase H: New Content Templates --")

    def h1_templates_exist():
        for tmpl in ["company_profile.md", "product_announce.md", "ranking.md"]:
            path = os.path.join(ROOT, f"03-content/templates/{tmpl}")
            assert os.path.exists(path), f"{tmpl} 不存在"
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            assert "CHUNK_START" in content, f"{tmpl} 缺少 CHUNK_START"
            assert "常见问题（FAQ）" in content, f"{tmpl} 缺少 FAQ"
            assert "SCHEMA_START" in content, f"{tmpl} 缺少 Schema"
    runner.run("H1. 新模板文件存在且结构正确", h1_templates_exist)

    def h2_save_content_new_formats():
        result = runner.exec_cmd(
            'python 03-content/scripts/save_content.py --help'
        )
        for fmt in ["company_profile", "product_announce", "ranking"]:
            assert fmt in result.stdout, f"--format {fmt} 不在 save_content.py 中"
    runner.run("H2. save_content.py 新格式 argparse 接受", h2_save_content_new_formats)

    def h3_company_profile_chunks():
        with open(os.path.join(ROOT, "03-content/templates/company_profile.md"), "r", encoding="utf-8") as f:
            content = f.read()
        chunk_count = len(re.findall(r'CHUNK_START', content))
        assert chunk_count >= 6, f"company_profile.md 只有 {chunk_count} 个 CHUNK"
    runner.run("H3. company_profile.md 7 层结构", h3_company_profile_chunks)

    def h4_product_announce_chunks():
        with open(os.path.join(ROOT, "03-content/templates/product_announce.md"), "r", encoding="utf-8") as f:
            content = f.read()
        chunk_count = len(re.findall(r'CHUNK_START', content))
        assert chunk_count == 6, f"product_announce.md 应有 6 个 CHUNK, 实际 {chunk_count}"
    runner.run("H4. product_announce.md 6 维结构", h4_product_announce_chunks)

    def h5_ranking_chunks():
        with open(os.path.join(ROOT, "03-content/templates/ranking.md"), "r", encoding="utf-8") as f:
            content = f.read()
        chunk_count = len(re.findall(r'CHUNK_START', content))
        assert chunk_count >= 5, f"ranking.md 只有 {chunk_count} 个 CHUNK"
    runner.run("H5. ranking.md 排名文章结构", h5_ranking_chunks)


def test_phase_i(runner):
    """Phase I: Integration Tests"""
    print("\n-- Phase I: Integration Tests --")

    def i1_smoke_check_new_modules():
        result = runner.exec_cmd("python lib/smoke_check.py")
        assert "SMOKE CHECK PASSED" in result.stdout
    runner.run("I1. smoke_check.py 含新模块通过", i1_smoke_check_new_modules)

    def i2_source_pool_in_report():
        runner.exec_cmd(
            'python 06-source-pool/scripts/manage_sources.py --action init'
        )
        result = runner.exec_cmd("python 05-report/scripts/generate_report.py --days 1")
        assert "信源池状态" in result.stdout, f"报告中无信源池章节: {result.stdout}"
    runner.run("I2. 报告中包含信源池状态章节", i2_source_pool_in_report)


def cleanup_test_data(runner):
    """Clean up test-injected CSV records"""
    print("\n-- Cleanup Test Data --")
    runner.remove_test_records(os.path.join(ROOT, "data/keywords.csv"), "kw_")
    runner.remove_test_records(os.path.join(ROOT, "data/questions.csv"), "q_")
    runner.remove_test_records(os.path.join(ROOT, "data/evidence.csv"), "ev_")
    runner.remove_test_records(os.path.join(ROOT, "data/competitors.csv"), "cp_")
    runner.remove_test_records(os.path.join(ROOT, "data/content.csv"), "ct_")
    runner.remove_test_records(os.path.join(ROOT, "data/monitor_log.csv"), "ml_")
    runner.remove_test_records(os.path.join(ROOT, "data/source_pool.csv"), "sp_")
    runner.remove_test_records(os.path.join(ROOT, "data/prepublish_score.csv"), "ps_")
    print("  Test data cleaned")


def main():
    print("=" * 60)
    print("HQ-GEO v3.0 Fusion Verification Test")
    print("=" * 60)

    runner = TestRunner()

    # Backup original CSV files
    for f in ["data/keywords.csv", "data/questions.csv", "data/evidence.csv",
              "data/competitors.csv", "data/content.csv", "data/monitor_log.csv",
              "data/source_pool.csv", "data/prepublish_score.csv"]:
        runner.backup_csv(f)

    try:
        test_phase_a(runner)
        test_phase_b(runner)
        test_phase_c(runner)
        test_phase_d(runner)
        test_phase_e(runner)
        test_phase_f(runner)  # Source pool tests
        test_phase_g(runner)  # Pre-publish scoring tests
        test_phase_h(runner)  # New template tests
        test_phase_i(runner)  # Integration tests

        cleanup_test_data(runner)
    finally:
        # Restore original CSV files
        for f in ["data/keywords.csv", "data/questions.csv", "data/evidence.csv",
                  "data/competitors.csv", "data/content.csv", "data/monitor_log.csv",
                  "data/source_pool.csv", "data/prepublish_score.csv"]:
            runner.restore_csv(f)

    all_passed = runner.report()

    if all_passed:
        print("\nAll tests passed! Fusion verification complete.")
    else:
        failed_count = sum(1 for r in runner.results if r[0] == FAIL)
        print(f"\n{failed_count} test(s) failed, need to fix.")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
