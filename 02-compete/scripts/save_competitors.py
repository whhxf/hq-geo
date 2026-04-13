#!/usr/bin/env python3
"""
save_competitors.py
将竞品分析结果追加写入 data/competitors.csv

用法：python save_competitors.py '<JSON_ARRAY>'
"""

import sys
import json
import csv
import os
from datetime import date
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# 添加 lib 到路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))
from hq_geo_lib import get_next_id_sequential, csv_append

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COMPETITORS_CSV = os.path.join(ROOT, "data", "competitors.csv")

FIELDNAMES = [
    "id", "run_date", "platform", "keyword_id", "keyword",
    "competitor_name", "mention_count", "cited_urls",
    "content_format_observed", "answer_position", "notes"
]


def save_competitors(records: list) -> dict:
    today = date.today().isoformat()
    added = 0

    for rec in records:
        cp_id = get_next_id_sequential("cp", COMPETITORS_CSV)
        row = {
            "id": cp_id,
            "run_date": rec.get("run_date", today),
            "platform": rec.get("platform", ""),
            "keyword_id": rec.get("keyword_id", ""),
            "keyword": rec.get("keyword", ""),
            "competitor_name": rec.get("competitor_name", ""),
            "mention_count": rec.get("mention_count", 0),
            "cited_urls": rec.get("cited_urls", ""),
            "content_format_observed": rec.get("content_format_observed", ""),
            "answer_position": rec.get("answer_position", ""),
            "notes": rec.get("notes", ""),
        }
        csv_append(COMPETITORS_CSV, FIELDNAMES, row)
        added += 1

    return {"added": added}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python save_competitors.py '<JSON_ARRAY>'")
        sys.exit(1)

    try:
        data = json.loads(sys.argv[1])
    except json.JSONDecodeError as e:
        print(f"JSON 解析失败: {e}")
        sys.exit(1)

    if not isinstance(data, list):
        data = [data]

    result = save_competitors(data)
    print(f"✅ 写入 {result['added']} 条竞品分析记录")
