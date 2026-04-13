#!/usr/bin/env python3
"""
analyze_trend.py
读取 monitor_log.csv，计算引用率趋势，输出 JSON 供 Claude 分析

用法：
  python analyze_trend.py             # 默认分析最近 7 天
  python analyze_trend.py --days 30   # 最近 30 天
  python analyze_trend.py --days 7 --compare 7  # 本期7天 vs 上期7天
"""

import argparse
import csv
import json
import os
from datetime import date, timedelta
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MONITOR_LOG_CSV = os.path.join(ROOT, "data", "monitor_log.csv")
KEYWORDS_CSV = os.path.join(ROOT, "data", "keywords.csv")


def load_keywords_map() -> dict:
    """读取关键词 ID → 文本的映射"""
    mapping = {}
    if not os.path.exists(KEYWORDS_CSV):
        return mapping
    with open(KEYWORDS_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            mapping[row["id"]] = row["keyword"]
    return mapping


def load_logs(start_date: str, end_date: str) -> list:
    """读取指定日期范围的监控日志"""
    logs = []
    if not os.path.exists(MONITOR_LOG_CSV):
        return logs
    with open(MONITOR_LOG_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            run_date = row.get("run_date", "")
            if start_date <= run_date <= end_date:
                logs.append(row)
    return logs


def calc_mention_rate(logs: list) -> float:
    if not logs:
        return 0.0
    mentioned = sum(1 for r in logs if r.get("brand_mentioned") == "true")
    return round(mentioned / len(logs), 4)


def analyze(days: int = 7, compare_days: int = 7) -> dict:
    today = date.today()
    period_end = today.isoformat()
    period_start = (today - timedelta(days=days - 1)).isoformat()
    prev_end = (today - timedelta(days=days)).isoformat()
    prev_start = (today - timedelta(days=days + compare_days - 1)).isoformat()

    kw_map = load_keywords_map()
    current_logs = load_logs(period_start, period_end)
    prev_logs = load_logs(prev_start, prev_end)

    if not current_logs:
        return {
            "error": "no_data",
            "message": f"在 {period_start} ~ {period_end} 之间没有监控数据",
            "suggestion": "请先运行 monitor.py 收集数据"
        }

    # 整体统计
    overall_rate = calc_mention_rate(current_logs)
    prev_overall_rate = calc_mention_rate(prev_logs)
    change = round(overall_rate - prev_overall_rate, 4)

    # 按关键词统计
    by_keyword = defaultdict(lambda: defaultdict(list))
    for log in current_logs:
        kid = log.get("keyword_id", "unknown")
        platform = log.get("platform", "unknown")
        by_keyword[kid][platform].append(log)

    prev_by_keyword = defaultdict(list)
    for log in prev_logs:
        kid = log.get("keyword_id", "unknown")
        prev_by_keyword[kid].append(log)

    keyword_stats = []
    keywords_needing_attention = []

    for kid, platforms_data in by_keyword.items():
        kw_text = kw_map.get(kid, kid)
        all_logs = [log for logs in platforms_data.values() for log in logs]
        current_rate = calc_mention_rate(all_logs)
        prev_rate = calc_mention_rate(prev_by_keyword[kid])
        kw_change = round(current_rate - prev_rate, 4)

        platform_breakdown = {}
        for platform, plogs in platforms_data.items():
            prate = calc_mention_rate(plogs)
            if prev_by_keyword[kid]:
                prev_plogs = [l for l in prev_by_keyword[kid] if l.get("platform") == platform]
                prev_prate = calc_mention_rate(prev_plogs)
                trend = "up" if prate > prev_prate else ("down" if prate < prev_prate else "stable")
            else:
                trend = "new"
            platform_breakdown[platform] = {"rate": prate, "trend": trend, "count": len(plogs)}

        stat = {
            "keyword_id": kid,
            "keyword": kw_text,
            "mention_rate_this_period": current_rate,
            "mention_rate_last_period": prev_rate,
            "change": f"{'+' if kw_change >= 0 else ''}{kw_change:.1%}",
            "platforms": platform_breakdown,
        }
        keyword_stats.append(stat)

        # 需要关注的关键词：引用率 < 30% 或下降超过 20%
        if current_rate < 0.3 or kw_change < -0.2:
            keywords_needing_attention.append(kid)

    # 竞品统计
    competitor_counts = defaultdict(int)
    for log in current_logs:
        if log.get("competitor_mentioned"):
            for comp in log["competitor_mentioned"].split(","):
                comp = comp.strip()
                if comp:
                    competitor_counts[comp] += 1

    top_competitors = sorted(competitor_counts.items(), key=lambda x: -x[1])[:5]

    # 按日期的引用率趋势
    daily_trend = defaultdict(list)
    for log in current_logs:
        daily_trend[log.get("run_date", "")].append(log)
    daily_rates = {
        d: calc_mention_rate(logs)
        for d, logs in sorted(daily_trend.items())
    }

    return {
        "period": f"{period_start} ~ {period_end}",
        "total_queries": len(current_logs),
        "brand_mention_rate": overall_rate,
        "brand_mention_rate_prev": prev_overall_rate,
        "overall_change": f"{'+' if change >= 0 else ''}{change:.1%}",
        "by_keyword": sorted(keyword_stats, key=lambda x: -x["mention_rate_this_period"]),
        "top_cited_competitors": [{"name": c, "count": n} for c, n in top_competitors],
        "keywords_needing_attention": keywords_needing_attention,
        "daily_trend": daily_rates,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="分析 GEO 监控趋势")
    parser.add_argument("--days", type=int, default=7, help="分析最近 N 天（默认7天）")
    parser.add_argument("--compare", type=int, default=7, help="对比前 N 天（默认7天）")
    args = parser.parse_args()

    result = analyze(days=args.days, compare_days=args.compare)
    print(json.dumps(result, ensure_ascii=False, indent=2))
