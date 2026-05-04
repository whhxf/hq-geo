#!/usr/bin/env python3
"""
analyze_preference.py
信源偏好分析：分析各 AI 平台对不同信源类型的引用偏好。

用法：
  python analyze_preference.py --input '<JSON_TEST_RESULTS>'
  python analyze_preference.py --report

JSON 输入格式（每条测试记录）：
[
  {
    "keyword": "关键词",
    "platform": "doubao",
    "cited_sources": [
      {"url": "https://baike.baidu.com/xxx", "type": "encyclopedia"},
      {"url": "https://mp.sohu.com/xxx", "type": "blog"}
    ]
  }
]
"""

import argparse
import csv
import json
import os
import sys
from datetime import date
from collections import defaultdict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SOURCE_CSV = os.path.join(ROOT, "data", "source_pool.csv")
OUTPUT_DIR = os.path.join(ROOT, "06-source-pool", "output")

# 信源类型到中文名称的映射
TYPE_LABELS = {
    "encyclopedia": "百科",
    "enterprise_db": "企业数据库",
    "blog": "博客",
    "map": "地图",
    "recruiting": "招聘平台",
    "social": "社交平台",
    "webmaster": "站长平台",
    "official_site": "官网",
    "forum": "论坛",
    "news": "新闻媒体",
    "video": "视频平台",
    "other": "其他",
}


def analyze_preference(test_results):
    """分析信源偏好矩阵"""
    # AI 平台 × 信源类型 → 引用次数
    matrix = defaultdict(lambda: defaultdict(int))
    # AI 平台 × 信源类型 → 引用 URL 列表
    urls = defaultdict(lambda: defaultdict(list))
    total_by_ai = defaultdict(int)

    for record in test_results:
        ai_platform = record.get("platform", "unknown")
        cited = record.get("cited_sources", [])
        total_by_ai[ai_platform] += 1

        for source in cited:
            source_type = source.get("type", "other")
            source_url = source.get("url", "")
            matrix[ai_platform][source_type] += 1
            if source_url:
                urls[ai_platform][source_type].append(source_url)

    # 生成报告
    return _build_report(matrix, urls, total_by_ai)


def _build_report(matrix, urls, total_by_ai):
    """构建偏好分析报告"""
    lines = []
    lines.append("# 信源偏好分析报告")
    lines.append(f"分析日期: {date.today().isoformat()}")
    lines.append(f"测试总数: {sum(total_by_ai.values())}")
    lines.append("")

    ai_platforms = sorted(matrix.keys())
    source_types = sorted(set(
        t for types in matrix.values() for t in types
    ))

    if not ai_platforms:
        lines.append("暂无测试数据。")
        return "\n".join(lines)

    # 全局统计
    global_type_count = defaultdict(int)
    for ai in ai_platforms:
        for st in source_types:
            global_type_count[st] += matrix[ai].get(st, 0)

    # 每个 AI 平台的信源偏好排名
    for ai in ai_platforms:
        lines.append(f"## {ai} 信源偏好")
        lines.append(f"总查询次数: {total_by_ai.get(ai, 0)}")
        lines.append("")

        type_scores = [(st, matrix[ai].get(st, 0)) for st in source_types]
        type_scores.sort(key=lambda x: x[1], reverse=True)

        lines.append("| 排名 | 信源类型 | 引用次数 | 占比 |")
        lines.append("|------|---------|---------|------|")
        total_refs = sum(v for _, v in type_scores)
        for rank, (st, count) in enumerate(type_scores, 1):
            label = TYPE_LABELS.get(st, st)
            pct = f"{count / total_refs * 100:.1f}%" if total_refs > 0 else "0%"
            lines.append(f"| {rank} | {label} | {count} | {pct} |")
        lines.append("")

        # Top 引用 URL
        for st, url_list in urls[ai].items():
            if url_list:
                label = TYPE_LABELS.get(st, st)
                unique_urls = list(set(url_list))[:5]
                lines.append(f"**{label} 引用 URL（Top 5）:**")
                for u in unique_urls:
                    lines.append(f"- {u}")
                lines.append("")

    # 跨平台对比热力图
    lines.append("## 跨平台信源引用热力图")
    lines.append("")

    header = "| AI 平台 | " + " | ".join(TYPE_LABELS.get(st, st) for st in source_types) + " |"
    lines.append(header)
    sep = "|" + "|".join("---" for _ in range(len(source_types) + 1)) + "|"
    lines.append(sep)

    for ai in ai_platforms:
        cells = []
        for st in source_types:
            cells.append(str(matrix[ai].get(st, 0)))
        lines.append(f"| {ai} | " + " | ".join(cells) + " |")

    lines.append("")

    # 建议
    lines.append("## 建议")
    lines.append("")

    for ai in ai_platforms:
        type_scores = [(st, matrix[ai].get(st, 0)) for st in source_types]
        type_scores.sort(key=lambda x: x[1], reverse=True)
        top_type = type_scores[0][0] if type_scores else "none"
        top_label = TYPE_LABELS.get(top_type, top_type)

        lines.append(f"- **{ai}**: 最偏好 {top_label} 类信源，建议在信源池建设时优先保障该类平台的覆盖")

    lines.append("")

    return "\n".join(lines)


def save_report(content):
    """保存报告到 output 目录"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filepath = os.path.join(OUTPUT_DIR, f"{date.today().isoformat()}_preference_analysis.md")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"报告已保存: {filepath}")


def load_test_results(json_input):
    """加载并验证 JSON 测试结果"""
    try:
        data = json.loads(json_input)
    except json.JSONDecodeError as e:
        print(f"JSON 解析失败: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(data, list):
        data = [data]

    validated = []
    for record in data:
        if not isinstance(record, dict):
            continue
        if "platform" not in record:
            continue
        validated.append(record)

    return validated


def main():
    parser = argparse.ArgumentParser(description="信源偏好分析")
    parser.add_argument("--input", default="", help="JSON 格式测试结果")
    args = parser.parse_args()

    if not args.input:
        print("用法: python analyze_preference.py --input '<JSON>'", file=sys.stderr)
        sys.exit(1)

    results = load_test_results(args.input)
    if not results:
        print("无有效测试数据", file=sys.stderr)
        sys.exit(1)

    report = analyze_preference(results)
    print(report)
    save_report(report)


if __name__ == "__main__":
    main()
