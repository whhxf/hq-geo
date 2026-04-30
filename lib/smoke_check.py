#!/usr/bin/env python3
"""
smoke_check.py
轻量稳定性体检：只做最小必要检查，不引入额外框架。

用法：
  python3 lib/smoke_check.py
"""

import csv
import os
import py_compile
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REQUIRED_CSV_HEADERS = {
    "data/brand.csv": ["field", "value"],
    "data/keywords.csv": [
        "id",
        "keyword",
        "intent_type",
        "platform_affinity",
        "priority_score",
        "content_format",
        "poi_semantic",
        "poi_authority",
        "poi_entity",
        "poi_evidence",
        "poi_corroboration",
        "poi_recency",
        "poi_structure",
        "status",
        "created_at",
    ],
}

OPTIONAL_CSV_HEADERS = {
    "data/questions.csv": [
        "id",
        "keyword_id",
        "question",
        "intent",
        "platform",
        "answer_type",
        "priority",
        "status",
        "created_at",
    ],
    "data/evidence.csv": [
        "id",
        "keyword_id",
        "evidence_type",
        "claim",
        "source_name",
        "source_url",
        "published_at",
        "verified_at",
        "confidence",
        "status",
        "notes",
    ],
}

SUPPORTED_PLATFORMS = {"doubao", "deepseek", "chatgpt", "perplexity"}

COMPILE_TARGETS = [
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
]


def read_csv_header(path: str):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        return next(reader, [])


def check_csv_headers(required_headers: dict, errors: list, missing_optional: list = None):
    for rel_path, required_cols in required_headers.items():
        abs_path = os.path.join(ROOT, rel_path)
        if not os.path.exists(abs_path):
            if missing_optional is not None:
                missing_optional.append(rel_path)
            else:
                errors.append(f"缺少文件: {rel_path}")
            continue
        header = read_csv_header(abs_path)
        missing = [c for c in required_cols if c not in header]
        if missing:
            errors.append(f"{rel_path} 缺少字段: {missing}")


def check_brand_platforms(errors: list):
    path = os.path.join(ROOT, "data/brand.csv")
    if not os.path.exists(path):
        return
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    kv = {row.get("field", ""): row.get("value", "") for row in rows}
    raw = kv.get("geo_target_platforms", "")
    if not raw:
        return
    # 模板占位值（包含方括号）不参与白名单校验。
    if "[" in raw or "]" in raw:
        return
    values = [x.strip() for x in raw.split(",") if x.strip()]
    unsupported = [v for v in values if v not in SUPPORTED_PLATFORMS]
    if unsupported:
        errors.append(f"brand.csv 包含未支持平台: {unsupported}")


def check_compile(errors: list):
    for rel_path in COMPILE_TARGETS:
        abs_path = os.path.join(ROOT, rel_path)
        if not os.path.exists(abs_path):
            errors.append(f"缺少脚本: {rel_path}")
            continue
        try:
            py_compile.compile(abs_path, doraise=True)
        except py_compile.PyCompileError as exc:
            errors.append(f"语法错误 {rel_path}: {exc.msg}")


def main():
    errors = []
    missing_optional = []
    check_csv_headers(REQUIRED_CSV_HEADERS, errors)
    check_csv_headers(OPTIONAL_CSV_HEADERS, errors, missing_optional)
    check_brand_platforms(errors)
    check_compile(errors)

    if errors:
        print("❌ SMOKE CHECK FAILED")
        for idx, item in enumerate(errors, 1):
            print(f"{idx}. {item}")
        sys.exit(1)

    print("✅ SMOKE CHECK PASSED")
    print("- 基础层 CSV 头字段通过")
    print("- 增强层 CSV（若存在）头字段通过")
    print("- brand 平台配置通过")
    print("- 关键脚本语法通过")
    if missing_optional:
        print(f"- 未检测到可选 CSV: {', '.join(missing_optional)}")
    sys.exit(0)


if __name__ == "__main__":
    main()
