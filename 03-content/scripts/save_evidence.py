#!/usr/bin/env python3
"""
save_evidence.py
将证据 JSON 列表追加写入 data/evidence.csv
用法：python save_evidence.py '<JSON_ARRAY>'
"""

import csv
import json
import os
import sys
from datetime import date

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "lib"))
from hq_geo_lib import csv_append, get_next_id_sequential

EVIDENCE_CSV = os.path.join(ROOT, "data", "evidence.csv")

FIELDNAMES = [
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
]


def load_existing_keys():
    existing = set()
    if not os.path.exists(EVIDENCE_CSV):
        return existing
    with open(EVIDENCE_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = (row.get("claim", "").strip(), row.get("source_url", "").strip())
            if key != ("", ""):
                existing.add(key)
    return existing


def save_evidence(items: list) -> dict:
    existing = load_existing_keys()
    today = date.today().isoformat()
    added = 0
    skipped = 0

    for item in items:
        claim = item.get("claim", "").strip()
        source_url = item.get("source_url", "").strip()
        if not claim:
            continue
        key = (claim, source_url)
        if key in existing:
            skipped += 1
            continue

        row = {
            "id": get_next_id_sequential("ev", EVIDENCE_CSV),
            "keyword_id": item.get("keyword_id", ""),
            "evidence_type": item.get("evidence_type", "stat"),
            "claim": claim,
            "source_name": item.get("source_name", ""),
            "source_url": source_url,
            "published_at": item.get("published_at", ""),
            "verified_at": item.get("verified_at", today),
            "confidence": item.get("confidence", "medium"),
            "status": item.get("status", "verified"),
            "notes": item.get("notes", ""),
        }
        csv_append(EVIDENCE_CSV, FIELDNAMES, row)
        existing.add(key)
        added += 1

    return {"added": added, "skipped": skipped}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python save_evidence.py '<JSON_ARRAY>'")
        sys.exit(1)

    try:
        data = json.loads(sys.argv[1])
    except json.JSONDecodeError as e:
        print(f"JSON 解析失败: {e}")
        sys.exit(1)

    if not isinstance(data, list):
        data = [data]

    result = save_evidence(data)
    print(f"✅ 新增证据 {result['added']} 条，跳过重复 {result['skipped']} 条")
