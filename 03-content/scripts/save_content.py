#!/usr/bin/env python3
"""
save_content.py
保存生成的内容 .md 文件，并更新 data/content.csv 索引

用法：
  python save_content.py \
    --keyword-id kw_001 \
    --keyword "AI 搜索优化工具哪个好" \
    --format comparison \
    --title "标题" \
    --file "03-content/output/2026-04-08_ai-search-tool.md"
"""

import argparse
import csv
import os
import sys
from datetime import date
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# 添加 lib 到路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lib"))
from hq_geo_lib import get_next_id_sequential, csv_append, CsvFileLock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONTENT_CSV = os.path.join(ROOT, "data", "content.csv")
KEYWORDS_CSV = os.path.join(ROOT, "data", "keywords.csv")

FIELDNAMES = [
    "id", "keyword_id", "keyword", "content_format", "title",
    "file_path", "word_count", "poi_score", "schema_included",
    "published_url", "published_at", "created_at", "status"
]


def count_words(file_path: str) -> int:
    """粗略统计字数（中文按字符，英文按空格分词）"""
    if not os.path.exists(file_path):
        return 0
    with open(file_path, encoding="utf-8") as f:
        content = f.read()
    # 去除 Markdown 符号
    import re
    content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)
    content = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
    content = re.sub(r'[#\*\-\|`>]', '', content)
    return len(content.replace(' ', '').replace('\n', ''))


def has_schema(file_path: str) -> bool:
    if not os.path.exists(file_path):
        return False
    with open(file_path, encoding="utf-8") as f:
        content = f.read()
    return "SCHEMA_START" in content and "@context" in content


def update_keyword_status(keyword_id: str, new_status: str = "content_created"):
    """更新 keywords.csv 中对应关键词的状态（带文件锁）"""
    if not os.path.exists(KEYWORDS_CSV):
        return
    lock = CsvFileLock(KEYWORDS_CSV)
    with lock:
        rows = []
        with open(KEYWORDS_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for row in reader:
                if row["id"] == keyword_id:
                    row["status"] = new_status
                rows.append(row)
        with open(KEYWORDS_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)


def save_content_record(keyword_id: str, keyword: str, fmt: str,
                        title: str, file_path: str) -> dict:
    today = date.today().isoformat()
    # 转为相对路径
    rel_path = os.path.relpath(file_path, ROOT) if os.path.isabs(file_path) else file_path

    wc = count_words(os.path.join(ROOT, rel_path) if not os.path.isabs(file_path) else file_path)
    schema_ok = has_schema(os.path.join(ROOT, rel_path) if not os.path.isabs(file_path) else file_path)

    record_id = get_next_id_sequential("ct", CONTENT_CSV)

    csv_append(CONTENT_CSV, FIELDNAMES, {
        "id": record_id,
        "keyword_id": keyword_id,
        "keyword": keyword,
        "content_format": fmt,
        "title": title,
        "file_path": rel_path,
        "word_count": wc,
        "poi_score": "",  # 由 Claude 填写
        "schema_included": "yes" if schema_ok else "no",
        "published_url": "",
        "published_at": "",
        "created_at": today,
        "status": "draft",
    })

    # 同步更新关键词状态
    if keyword_id:
        update_keyword_status(keyword_id, "content_created")

    return {
        "id": record_id,
        "word_count": wc,
        "schema_included": schema_ok,
        "file_path": rel_path,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="保存内容记录到 content.csv")
    parser.add_argument("--keyword-id", default="", help="关键词 ID（kw_xxx）")
    parser.add_argument("--keyword", required=True, help="目标关键词")
    parser.add_argument("--format", required=True,
                        choices=["faq", "comparison", "definition", "howto"],
                        help="内容格式")
    parser.add_argument("--title", required=True, help="文章标题")
    parser.add_argument("--file", required=True, help="内容文件路径（.md）")
    args = parser.parse_args()

    result = save_content_record(
        keyword_id=args.keyword_id,
        keyword=args.keyword,
        fmt=args.format,
        title=args.title,
        file_path=args.file,
    )

    print(f"✅ 内容记录已保存")
    print(f"   ID: {result['id']}")
    print(f"   字数: {result['word_count']}")
    print(f"   Schema: {'✅ 已包含' if result['schema_included'] else '❌ 未包含'}")
    print(f"   路径: {result['file_path']}")
