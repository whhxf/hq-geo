#!/usr/bin/env python3
"""
check_claim_risk.py
轻量声明风险扫描：识别绝对化承诺与高风险领域确定性建议。

用法：
  python check_claim_risk.py <markdown_file>
"""

import argparse
import re
import sys


ABSOLUTE_PATTERNS = [
    r"100%\s*(有效|提升|保证)",
    r"(保证|确保|必然|一定会)",
    r"(永久|永远)\s*(有效|可用|排名)",
    r"(第一名|绝对领先|唯一正确)",
]

SENSITIVE_DOMAIN_PATTERNS = [
    r"(医疗|治愈|药物|处方).*(保证|必然|一定)",
    r"(法律|诉讼|合规).*(保证|必然|一定)",
    r"(投资|理财|金融|收益).*(保证|稳赚|无风险)",
]


def scan_text(text: str):
    issues = []

    for pattern in ABSOLUTE_PATTERNS:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            issues.append({
                "type": "absolute_claim",
                "match": match.group(0),
                "start": match.start(),
            })

    for pattern in SENSITIVE_DOMAIN_PATTERNS:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            issues.append({
                "type": "sensitive_domain_claim",
                "match": match.group(0),
                "start": match.start(),
            })

    issues.sort(key=lambda x: x["start"])
    return issues


def main():
    parser = argparse.ArgumentParser(description="检查内容声明风险")
    parser.add_argument("file", help="待检查的 Markdown 文件")
    args = parser.parse_args()

    try:
        with open(args.file, "r", encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        print(f"❌ 文件不存在: {args.file}")
        sys.exit(1)

    issues = scan_text(text)
    if not issues:
        print("✅ 未检测到高风险声明")
        sys.exit(0)

    print("⚠️ 检测到潜在高风险声明：")
    for idx, issue in enumerate(issues, 1):
        print(f"{idx}. [{issue['type']}] {issue['match']}")

    sys.exit(1)


if __name__ == "__main__":
    main()
