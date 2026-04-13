#!/usr/bin/env python3
"""
monitor.py
GEO 主监控脚本。读取关键词和平台配置，向各 AI 平台发送查询，
将结果追加写入 data/monitor_log.csv。

用法：
  python monitor.py                                    # 监控全部
  python monitor.py --keyword-ids kw_001,kw_002        # 指定关键词
  python monitor.py --platforms doubao                  # 指定平台
  python monitor.py --keyword-ids kw_001 --platforms doubao,deepseek
"""

import argparse
import csv
import json
import os
import sys
import time
import random
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import re
from datetime import date, datetime

# 添加上级目录到路径，复用 query_ai_platform 逻辑
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "02-compete", "scripts"))

# 添加 lib 到路径
sys.path.insert(0, os.path.join(ROOT, "lib"))
from hq_geo_lib import get_next_id_sequential, csv_append, ensure_dotenv, setup_logger

ensure_dotenv()
logger = setup_logger("monitor", log_dir=os.path.join(ROOT, "logs"))

MONITOR_LOG_CSV = os.path.join(ROOT, "data", "monitor_log.csv")
KEYWORDS_CSV = os.path.join(ROOT, "data", "keywords.csv")
BRAND_CSV = os.path.join(ROOT, "data", "brand.csv")

LOG_FIELDNAMES = [
    "id", "run_date", "platform", "prompt_used", "keyword_id",
    "brand_mentioned", "brand_position", "cited_url", "competitor_mentioned",
    "sentiment", "raw_response_snippet", "notes"
]


def load_brand() -> dict:
    info = {}
    if not os.path.exists(BRAND_CSV):
        return info
    with open(BRAND_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            info[row["field"]] = row["value"]
    return info


def load_keywords(keyword_ids: list = None) -> list:
    keywords = []
    if not os.path.exists(KEYWORDS_CSV):
        return keywords
    with open(KEYWORDS_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["status"] not in ("content_created", "published"):
                continue
            if keyword_ids and row["id"] not in keyword_ids:
                continue
            keywords.append(row)
    return keywords


def keyword_to_prompt(keyword: str, intent_type: str = "consideration") -> str:
    """将关键词转换为更自然的查询 prompt"""
    if keyword.endswith("\uff1f") or keyword.endswith("?"):
        return keyword
    if any(keyword.startswith(w) for w in ["\u4ec0\u4e48\u662f", "\u5982\u4f55", "\u600e\u4e48", "\u4e3a\u4ec0\u4e48", "\u54ea\u4e2a", "\u54ea\u4e9b", "\u6709\u6ca1\u6709"]):
        return keyword + "\uff1f"
    return keyword


def detect_brand_position(text: str, brand_name: str) -> str:
    """检测品牌在答案中的位置"""
    if not brand_name or brand_name not in text:
        return "none"
    total_len = len(text)
    pos = text.find(brand_name)
    ratio = pos / total_len
    if ratio < 0.25:
        return "first"
    elif ratio < 0.75:
        return "middle"
    else:
        return "last"


def detect_sentiment(text: str, brand_name: str) -> str:
    """简单情感检测"""
    if not brand_name or brand_name not in text:
        return "neutral"

    idx = text.find(brand_name)
    context = text[max(0, idx-100):idx+200]

    positive_words = ["\u63a8\u8350", "\u4f18\u79c0", "\u5f3a\u5927", "\u597d\u7528", "\u9886\u5148", "\u6700\u4f73", "\u9996\u9009", "\u51fa\u8272", "\u4e13\u4e1a"]
    negative_words = ["\u4e0d\u63a8\u8350", "\u8f83\u5dee", "\u95ee\u9898", "\u7f3a\u70b9", "\u5c40\u9650", "\u4e0d\u8db3", "\u843d\u540e", "\u6602\u8d35"]

    pos_count = sum(1 for w in positive_words if w in context)
    neg_count = sum(1 for w in negative_words if w in context)

    if pos_count > neg_count:
        return "positive"
    elif neg_count > pos_count:
        return "negative"
    return "neutral"


def run_monitor_playwright(keyword_text: str, platform: str,
                            brand_name: str, competitors: list) -> dict:
    """使用 Playwright 查询单个平台"""
    try:
        from query_ai_platform import query_platform
    except ImportError:
        spec_path = os.path.join(ROOT, "02-compete", "scripts", "query_ai_platform.py")
        import importlib.util
        spec = importlib.util.spec_from_file_location("query_ai_platform", spec_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        query_platform = mod.query_platform

    logger.debug("query_platform: keyword=%s platform=%s", keyword_text[:30], platform)
    result = query_platform(
        keyword=keyword_text,
        platform=platform,
        attempts=1,
        brand_name=brand_name,
        competitors=competitors,
    )

    if "error" in result:
        return {"error": result["error"], "raw_text": "", "mentioned_brands": [],
                "cited_urls": [], "answer_structure": "unknown"}

    responses = result.get("responses", [])
    if not responses:
        return {"error": "no_response", "raw_text": "", "mentioned_brands": [],
                "cited_urls": [], "answer_structure": "unknown"}

    resp = responses[0]
    return {
        "raw_text": resp.get("raw_text", ""),
        "mentioned_brands": resp.get("mentioned_brands", []),
        "cited_urls": resp.get("cited_urls", []),
        "answer_structure": resp.get("answer_structure", "paragraph"),
        "error": resp.get("error", ""),
    }


def _parse_env_int(key: str, default: int) -> int:
    """安全解析环境变量整数，无效值返回默认值"""
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        return default


def main():
    parser = argparse.ArgumentParser(description="GEO 监控脚本")
    parser.add_argument("--keyword-ids", default="",
                        help="指定关键词 ID，逗号分隔（默认全部已有内容的关键词）")
    parser.add_argument("--platforms", default="",
                        help="指定平台，逗号分隔（默认读取 brand.csv 配置）")
    args = parser.parse_args()

    brand = load_brand()
    brand_name = brand.get("brand_name", "")
    competitors_raw = brand.get("competitors", "")
    competitors = [c.strip() for c in competitors_raw.split(",") if c.strip()]

    if args.platforms:
        platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]
    else:
        platforms_raw = brand.get("geo_target_platforms", "doubao,deepseek")
        platforms = [p.strip() for p in platforms_raw.split(",") if p.strip()]

    keyword_ids = [k.strip() for k in args.keyword_ids.split(",") if k.strip()] if args.keyword_ids else None
    keywords = load_keywords(keyword_ids)

    if not keywords:
        logger.warning("没有找到 content_created/published 关键词")
        print("[WARN] 没有找到状态为 content_created 或 published 的关键词")
        print("   请先运行内容生成（03-content），或检查 keywords.csv 中的 status 字段")
        sys.exit(0)

    logger.info("监控启动 | 品牌=%s | 关键词=%d | 平台=%s", brand_name, len(keywords), platforms)
    print(f"[*] 开始监控")
    print(f"   品牌：{brand_name}")
    print(f"   关键词：{len(keywords)} 个")
    print(f"   平台：{', '.join(platforms)}")
    print(f"   时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 60)

    today = date.today().isoformat()
    records = []
    delay_min = _parse_env_int("MONITOR_DELAY_MIN", 3)
    delay_max = _parse_env_int("MONITOR_DELAY_MAX", 8)
    if delay_min > delay_max:
        delay_min, delay_max = delay_max, delay_min

    for kw in keywords:
        prompt_text = keyword_to_prompt(kw["keyword"], kw.get("intent_type", ""))
        print(f"\n[*] 关键词：{kw['keyword']}")
        logger.info("开始查询 | id=%s | keyword=%s", kw["id"], kw["keyword"])

        for platform in platforms:
            print(f"   -> {platform}... ", end="", flush=True)

            result = run_monitor_playwright(
                keyword_text=prompt_text,
                platform=platform,
                brand_name=brand_name,
                competitors=competitors,
            )

            if result.get("error"):
                notes = f"error: {result['error']}"
                brand_mentioned = "error"
                brand_position = "none"
                cited_url = ""
                competitor_mentioned = ""
                sentiment = "neutral"
                snippet = ""
                print(f"[ERR] {result['error']}")
                logger.error("查询失败 | %s/%s | %s", kw["id"], platform, result['error'])
            else:
                raw_text = result.get("raw_text", "")
                mentioned = result.get("mentioned_brands", [])
                brand_mentioned_bool = brand_name in mentioned if brand_name else False
                brand_mentioned = "true" if brand_mentioned_bool else "false"
                brand_position = detect_brand_position(raw_text, brand_name)
                cited_url = ",".join(result.get("cited_urls", [])[:3])
                competitor_mentioned = ",".join(
                    [b for b in mentioned if b != brand_name]
                )
                sentiment = detect_sentiment(raw_text, brand_name)
                snippet = raw_text[:300]
                notes = ""

                status_icon = "[OK]" if brand_mentioned_bool else "[--]"
                print(f"{status_icon} {'被引用' if brand_mentioned_bool else '未引用'} | 情感:{sentiment}")
                logger.info("查询成功 | %s/%s | brand=%s | sentiment=%s | pos=%s | competitors=%s",
                           kw["id"], platform, brand_mentioned, sentiment, brand_position, competitor_mentioned)

            ml_id = get_next_id_sequential("ml", MONITOR_LOG_CSV)
            records.append({
                "id": ml_id,
                "run_date": today,
                "platform": platform,
                "prompt_used": prompt_text,
                "keyword_id": kw["id"],
                "brand_mentioned": brand_mentioned,
                "brand_position": brand_position,
                "cited_url": cited_url,
                "competitor_mentioned": competitor_mentioned,
                "sentiment": sentiment,
                "raw_response_snippet": snippet,
                "notes": notes,
            })

            if platform != platforms[-1] or kw != keywords[-1]:
                sleep_sec = random.uniform(delay_min, delay_max)
                time.sleep(sleep_sec)

    for rec in records:
        csv_append(MONITOR_LOG_CSV, LOG_FIELDNAMES, rec)
    print("\n" + "=" * 60)
    logger.info("监控完成 | 记录数=%d", len(records))
    print(f"[OK] 监控完成，共记录 {len(records)} 条数据 -> data/monitor_log.csv")

    mentioned_count = sum(1 for r in records if r["brand_mentioned"] == "true")
    total = len(records)
    if total > 0:
        rate = mentioned_count / total * 100
        print(f"   品牌引用率：{mentioned_count}/{total} = {rate:.1f}%")


if __name__ == "__main__":
    main()
