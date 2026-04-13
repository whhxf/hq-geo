#!/usr/bin/env python3
"""
save_keywords.py
将关键词 JSON 列表追加写入 data/keywords.csv
用法：python save_keywords.py '<JSON_ARRAY>'
"""

import sys
import json
import csv
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import os
from datetime import date

# 添加 lib 到路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))
from hq_geo_lib import get_next_id_sequential, csv_append

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KEYWORDS_CSV = os.path.join(ROOT, "data", "keywords.csv")

FIELDNAMES = [
    "id", "keyword", "intent_type", "platform_affinity", "priority_score",
    "content_format", "poi_semantic", "poi_authority", "poi_entity",
    "poi_evidence", "poi_corroboration", "poi_recency", "poi_structure",
    "status", "created_at"
]


def load_existing_keywords():
    """读取现有关键词，用于去重"""
    existing = set()
    if not os.path.exists(KEYWORDS_CSV):
        return existing
    with open(KEYWORDS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            existing.add(row["keyword"].strip())
    return existing


def save_keywords(keywords: list) -> dict:
    existing = load_existing_keywords()
    today = date.today().isoformat()

    added = []
    skipped = []

    for kw in keywords:
        keyword_text = kw.get("keyword", "").strip()
        if not keyword_text:
            continue
        if keyword_text in existing:
            skipped.append(keyword_text)
            continue

        kw_id = get_next_id_sequential("kw", KEYWORDS_CSV)
        row = {
            "id": kw_id,
            "keyword": keyword_text,
            "intent_type": kw.get("intent_type", "awareness"),
            "platform_affinity": kw.get("platform_affinity", "all"),
            "priority_score": kw.get("priority_score", 5),
            "content_format": kw.get("content_format", "faq"),
            "poi_semantic": kw.get("poi_semantic", 1),
            "poi_authority": kw.get("poi_authority", 1),
            "poi_entity": kw.get("poi_entity", 1),
            "poi_evidence": kw.get("poi_evidence", 1),
            "poi_corroboration": kw.get("poi_corroboration", 1),
            "poi_recency": kw.get("poi_recency", 1),
            "poi_structure": kw.get("poi_structure", 1),
            "status": "pending",
            "created_at": today,
        }
        csv_append(KEYWORDS_CSV, FIELDNAMES, row)
        added.append(keyword_text)
        existing.add(keyword_text)

    return {"added": added, "skipped": skipped}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python save_keywords.py '<JSON_ARRAY>'")
        sys.exit(1)

    try:
        data = json.loads(sys.argv[1])
    except json.JSONDecodeError as e:
        print(f"JSON 解析失败: {e}")
        sys.exit(1)

    if not isinstance(data, list):
        data = [data]

    result = save_keywords(data)
    print(f"✅ 新增 {len(result['added'])} 个关键词")
    for kw in result["added"]:
        print(f"   + {kw}")
    if result["skipped"]:
        print(f"⏭  跳过 {len(result['skipped'])} 个重复关键词")
        for kw in result["skipped"]:
            print(f"   ~ {kw}")
