#!/usr/bin/env python3
"""
save_questions.py
将问题 JSON 列表追加写入 data/questions.csv
用法：python save_questions.py '<JSON_ARRAY>'
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

QUESTIONS_CSV = os.path.join(ROOT, "data", "questions.csv")

FIELDNAMES = [
    "id",
    "keyword_id",
    "question",
    "intent",
    "platform",
    "answer_type",
    "priority",
    "status",
    "created_at",
]


def load_existing_questions():
    existing = set()
    if not os.path.exists(QUESTIONS_CSV):
        return existing
    with open(QUESTIONS_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            existing.add(row.get("question", "").strip())
    return existing


def save_questions(items: list) -> dict:
    existing = load_existing_questions()
    today = date.today().isoformat()
    added = []
    skipped = []

    for item in items:
        question = item.get("question", "").strip()
        if not question:
            continue
        if question in existing:
            skipped.append(question)
            continue

        row = {
            "id": get_next_id_sequential("q", QUESTIONS_CSV),
            "keyword_id": item.get("keyword_id", ""),
            "question": question,
            "intent": item.get("intent", "awareness"),
            "platform": item.get("platform", "all"),
            "answer_type": item.get("answer_type", "definition"),
            "priority": item.get("priority", 5),
            "status": item.get("status", "pending"),
            "created_at": today,
        }
        csv_append(QUESTIONS_CSV, FIELDNAMES, row)
        existing.add(question)
        added.append(question)

    return {"added": added, "skipped": skipped}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python save_questions.py '<JSON_ARRAY>'")
        sys.exit(1)

    try:
        data = json.loads(sys.argv[1])
    except json.JSONDecodeError as e:
        print(f"JSON 解析失败: {e}")
        sys.exit(1)

    if not isinstance(data, list):
        data = [data]

    result = save_questions(data)
    print(f"✅ 新增 {len(result['added'])} 个问题")
    for item in result["added"]:
        print(f"   + {item}")
    if result["skipped"]:
        print(f"⏭  跳过 {len(result['skipped'])} 个重复问题")
        for item in result["skipped"]:
            print(f"   ~ {item}")
