"""
monitor_metrics.py
monitor/report 共用指标逻辑，避免口径漂移。
"""

from collections import defaultdict
from datetime import date, timedelta
import re


def mention_rate(logs: list) -> float:
    """品牌提及率：brand_mentioned == true 的占比。"""
    if not logs:
        return 0.0
    mentioned = sum(1 for item in logs if str(item.get("brand_mentioned", "")).lower() == "true")
    return round(mentioned / len(logs), 4)


def split_period_logs(all_logs: list, days: int):
    """
    拆分本期和上期日志（窗口长度一致）。
    返回：current_logs, prev_logs, period_start, period_end
    """
    today = date.today()
    period_end = today.isoformat()
    period_start = (today - timedelta(days=days - 1)).isoformat()
    prev_end = (today - timedelta(days=days)).isoformat()
    prev_start = (today - timedelta(days=days * 2 - 1)).isoformat()

    current = [row for row in all_logs if period_start <= row.get("run_date", "") <= period_end]
    prev = [row for row in all_logs if prev_start <= row.get("run_date", "") <= prev_end]
    return current, prev, period_start, period_end


def group_logs_by_keyword(logs: list):
    grouped = defaultdict(list)
    for row in logs:
        grouped[row.get("keyword_id", "")].append(row)
    return grouped


def group_logs_by_platform(logs: list):
    grouped = defaultdict(list)
    for row in logs:
        grouped[row.get("platform", "")].append(row)
    return grouped


def competitor_counts(logs: list):
    counts = defaultdict(int)
    for row in logs:
        raw = row.get("competitor_mentioned", "")
        # 兼容历史逗号分隔与建议中的分号分隔，避免统计口径漂移。
        for comp in re.split(r"[,;]", raw):
            comp = comp.strip()
            if comp:
                counts[comp] += 1
    return counts
