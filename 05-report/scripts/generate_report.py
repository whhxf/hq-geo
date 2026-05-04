#!/usr/bin/env python3
"""
generate_report.py
读取所有 CSV 数据，生成 Markdown 格式的 GEO 周报/月报

用法：
  python generate_report.py             # 默认最近 7 天
  python generate_report.py --days 30   # 最近 30 天
"""

import argparse
import csv
import os
import sys
from datetime import date
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "lib"))
from monitor_metrics import (
    mention_rate,
    split_period_logs,
    group_logs_by_keyword,
    group_logs_by_platform,
    competitor_counts,
)

MONITOR_LOG_CSV = os.path.join(ROOT, "data", "monitor_log.csv")
KEYWORDS_CSV = os.path.join(ROOT, "data", "keywords.csv")
CONTENT_CSV = os.path.join(ROOT, "data", "content.csv")
BRAND_CSV = os.path.join(ROOT, "data", "brand.csv")
SOURCE_POOL_CSV = os.path.join(ROOT, "data", "source_pool.csv")
PREPUBLISH_CSV = os.path.join(ROOT, "data", "prepublish_score.csv")
REPORT_OUTPUT_DIR = os.path.join(ROOT, "05-report", "output")


def load_csv(path: str) -> list:
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_brand() -> dict:
    rows = load_csv(BRAND_CSV)
    return {r["field"]: r["value"] for r in rows}


def generate_report(days: int = 7) -> str:
    brand = load_brand()
    brand_name = brand.get("brand_name", "（品牌名未填写）")
    platforms_str = brand.get("geo_target_platforms", "doubao,deepseek")

    keywords = load_csv(KEYWORDS_CSV)
    contents = load_csv(CONTENT_CSV)
    all_logs = load_csv(MONITOR_LOG_CSV)
    current_logs, prev_logs, period_start, period_end = split_period_logs(all_logs, days)

    today_str = date.today().strftime("%Y-%m-%d")
    period_label = "周报" if days <= 7 else ("月报" if days <= 31 else f"{days}天报告")

    kw_map = {kw["id"]: kw for kw in keywords}

    # ── 整体指标 ──────────────────────────────────
    total_queries = len(current_logs)
    overall_rate = mention_rate(current_logs)
    prev_rate = mention_rate(prev_logs)
    rate_change = overall_rate - prev_rate
    change_str = f"{'+' if rate_change >= 0 else ''}{rate_change:.1%}"
    change_icon = "↑" if rate_change > 0 else ("↓" if rate_change < 0 else "→")

    # ── 按关键词统计 ──────────────────────────────
    kw_logs = group_logs_by_keyword(current_logs)
    prev_kw_logs = group_logs_by_keyword(prev_logs)

    # ── 竞品统计 ──────────────────────────────────
    comp_counts = competitor_counts(current_logs)

    # ── 内容状态统计 ──────────────────────────────
    content_by_status = defaultdict(int)
    for c in contents:
        content_by_status[c.get("status", "draft")] += 1

    kw_by_status = defaultdict(int)
    for kw in keywords:
        kw_by_status[kw.get("status", "pending")] += 1

    # ── 平台分析 ──────────────────────────────────
    platform_stats = group_logs_by_platform(current_logs)

    # ── 需要关注的关键词 ──────────────────────────
    attention_kws = []
    for kid, logs in kw_logs.items():
        rate = mention_rate(logs)
        prev_r = mention_rate(prev_kw_logs.get(kid, []))
        kw_info = kw_map.get(kid, {})
        if rate < 0.3 or (prev_r > 0 and rate < prev_r - 0.2):
            attention_kws.append({
                "id": kid,
                "keyword": kw_info.get("keyword", kid),
                "rate": rate,
                "prev_rate": prev_r,
                "format": kw_info.get("content_format", ""),
            })

    # ── 无内容的高优先级关键词 ────────────────────
    uncovered_kws = [
        kw for kw in keywords
        if kw.get("status") == "pending" and int(kw.get("priority_score", 0)) >= 7
    ]
    uncovered_kws.sort(key=lambda x: -int(x.get("priority_score", 0)))

    # ══════════════════════════════════════════════
    # 生成 Markdown 报告
    # ══════════════════════════════════════════════
    lines = []

    lines.append(f"# GEO {period_label} · {today_str}")
    lines.append(f"\n**品牌：** {brand_name}  ")
    lines.append(f"**监控周期：** {period_start} ~ {period_end}  ")
    lines.append(f"**监控平台：** {platforms_str}  ")
    lines.append("")

    # 概览
    lines.append("---\n")
    lines.append("## 一、本期概览\n")
    lines.append(f"| 指标 | 本期 | 上期 | 变化 |")
    lines.append(f"|------|------|------|------|")
    lines.append(f"| 总查询次数 | {total_queries} | {len(prev_logs)} | — |")
    lines.append(f"| 品牌引用率 | {overall_rate:.1%} | {prev_rate:.1%} | {change_icon} {change_str} |")
    lines.append(f"| 覆盖关键词数 | {len(kw_logs)} | {len(prev_kw_logs)} | — |")
    lines.append(f"| 已生成内容 | {len(contents)} 篇 | — | — |")
    lines.append(f"| 已发布内容 | {content_by_status.get('published', 0)} 篇 | — | — |")
    lines.append("")

    # 关键词引用率明细
    lines.append("---\n")
    lines.append("## 二、关键词引用率明细\n")

    if kw_logs:
        # 表头：各平台列
        all_platforms = sorted(set(l.get("platform", "") for l in current_logs))
        header = "| 关键词 | " + " | ".join(all_platforms) + " | 本期均值 | 趋势 |"
        separator = "|--------|" + "|".join(["------"] * len(all_platforms)) + "|---------|------|"
        lines.append(header)
        lines.append(separator)

        for kid, logs in sorted(kw_logs.items(), key=lambda x: -mention_rate(x[1])):
            kw_info = kw_map.get(kid, {})
            kw_text = kw_info.get("keyword", kid)[:20]
            rate_this = mention_rate(logs)
            rate_prev = mention_rate(prev_kw_logs.get(kid, []))
            trend = "↑" if rate_this > rate_prev else ("↓" if rate_this < rate_prev else "→")

            platform_cells = []
            for p in all_platforms:
                p_logs = [l for l in logs if l.get("platform") == p]
                if p_logs:
                    pr = mention_rate(p_logs)
                    platform_cells.append(f"{pr:.0%}")
                else:
                    platform_cells.append("—")

            row = f"| {kw_text} | " + " | ".join(platform_cells) + f" | {rate_this:.0%} | {trend} |"
            lines.append(row)
    else:
        lines.append("_本期暂无监控数据_")

    lines.append("")

    # 平台表现
    lines.append("---\n")
    lines.append("## 三、平台表现\n")
    for platform, p_logs in sorted(platform_stats.items()):
        p_rate = mention_rate(p_logs)
        p_prev = mention_rate([l for l in prev_logs if l.get("platform") == platform])
        change = p_rate - p_prev
        icon = "↑" if change > 0 else ("↓" if change < 0 else "→")
        lines.append(f"- **{platform}**：引用率 {p_rate:.1%}（上期 {p_prev:.1%}，{icon} {change:+.1%}）")
    lines.append("")

    # 竞品动态
    lines.append("---\n")
    lines.append("## 四、竞品动态\n")
    if comp_counts:
        lines.append("| 竞品 | 被提及次数 |")
        lines.append("|------|-----------|")
        for comp, cnt in sorted(comp_counts.items(), key=lambda x: -x[1]):
            lines.append(f"| {comp} | {cnt} |")
    else:
        lines.append("_本期未检测到竞品被提及_")
    lines.append("")

    # 需要关注
    lines.append("---\n")
    lines.append("## 五、需要关注的关键词\n")
    if attention_kws:
        for kw in attention_kws:
            change = kw["rate"] - kw["prev_rate"]
            lines.append(f"- 🔴 **{kw['keyword']}** — 引用率 {kw['rate']:.0%}（变化 {change:+.0%}）")
            lines.append(f"  - 建议：更新内容，重点补强 Evidence 和 Semantic 信号")
    else:
        lines.append("_✅ 所有监控关键词表现正常_")
    lines.append("")

    # 内容缺口
    lines.append("---\n")
    lines.append("## 六、内容缺口（高优先级未覆盖关键词）\n")
    if uncovered_kws:
        lines.append("| 关键词 | 优先级 | 推荐格式 | 意图类型 |")
        lines.append("|--------|--------|---------|---------|")
        for kw in uncovered_kws[:5]:
            lines.append(
                f"| {kw['keyword']} | {kw.get('priority_score', '—')} | "
                f"{kw.get('content_format', '—')} | {kw.get('intent_type', '—')} |"
            )
    else:
        lines.append("_✅ 所有高优先级关键词均已有内容_")
    lines.append("")

    # ── 信源池状态 ──────────────────────────────
    lines.append("---\n")
    lines.append("## 八、信源池状态\n")
    sources = load_csv(SOURCE_POOL_CSV)
    if sources:
        total_src = len(sources)
        registered = sum(1 for s in sources if s.get("account_status") != "not_started")
        deployed = sum(1 for s in sources if s.get("deploy_status") == "live")
        pending = sum(1 for s in sources if s.get("deploy_status") == "pending_review")

        lines.append(f"| 状态 | 数量 |")
        lines.append(f"|------|------|")
        lines.append(f"| 总平台数 | {total_src} |")
        lines.append(f"| 已注册 | {registered} |")
        lines.append(f"| 已部署上线 | {deployed} |")
        lines.append(f"| 待审核 | {pending} |")
        lines.append("")

        if deployed > 0:
            lines.append("**已部署平台：**")
            for s in sources:
                if s.get("deploy_status") == "live":
                    url = s.get("deploy_url", "")
                    lines.append(f"- {s.get('platform_name', '')} ({s.get('platform_type', '')})" + (f" → {url}" if url else ""))
            lines.append("")
    else:
        lines.append("_信源池尚未初始化。建议运行「信源池」模块开始建设。_")
    lines.append("")

    # ── 预发布评分摘要 ──────────────────────────
    lines.append("---\n")
    lines.append("## 九、内容质量评分摘要\n")
    scores = load_csv(PREPUBLISH_CSV)
    if scores:
        total_scored = len(scores)
        passed = sum(1 for s in scores if s.get("status") == "pass")
        needs_rev = sum(1 for s in scores if s.get("status") == "needs_revision")
        failed = sum(1 for s in scores if s.get("status") == "fail")

        avg_score = 0.0
        valid_scores = [float(s.get("weighted_score", 0)) for s in scores if s.get("weighted_score", "")]
        if valid_scores:
            avg_score = sum(valid_scores) / len(valid_scores)

        lines.append(f"| 指标 | 数值 |")
        lines.append(f"|------|------|")
        lines.append(f"| 总评分次数 | {total_scored} |")
        lines.append(f"| 通过 (>=7.0) | {passed} |")
        lines.append(f"| 需修改 (5.0-6.9) | {needs_rev} |")
        lines.append(f"| 不通过 (<5.0) | {failed} |")
        lines.append(f"| 平均分 | {avg_score:.2f} |")
        lines.append("")
    else:
        lines.append("_尚无预发布评分记录。建议内容发布前先进行预发布质量评分。_")
    lines.append("")

    # 行动建议
    lines.append("---\n")
    lines.append("## 七、本期建议行动\n")
    action_num = 1
    if attention_kws:
        for kw in attention_kws[:2]:
            lines.append(f"{action_num}. 🔴 更新「{kw['keyword']}」的内容，补充近期数据和权威引用")
            action_num += 1
    if uncovered_kws:
        top_kw = uncovered_kws[0]
        lines.append(
            f"{action_num}. 🟡 为「{top_kw['keyword']}」创建 {top_kw.get('content_format', 'faq')} 格式内容"
            f"（优先级分：{top_kw.get('priority_score', '—')}）"
        )
        action_num += 1
    if overall_rate < 0.3:
        lines.append(
            f"{action_num}. 🟡 整体引用率偏低（{overall_rate:.0%}），"
            f"建议在豆包/知乎/微信公众号发布内容摘要，提升 Corroboration 信号"
        )
        action_num += 1
    if action_num == 1:
        lines.append("✅ 本期表现良好，保持现有策略，持续产出内容。")
    lines.append("")

    lines.append("---")
    lines.append(f"\n_报告生成时间：{today_str} | 由 HQ-GEO Engine 自动生成_")

    report_content = "\n".join(lines)

    # 保存报告文件
    os.makedirs(REPORT_OUTPUT_DIR, exist_ok=True)
    report_path = os.path.join(REPORT_OUTPUT_DIR, f"report_{today_str}.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None
    print(f"[OK] 报告已保存：{report_path}")
    print("\n" + "=" * 60 + "\n")
    print(report_content)
    return report_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="生成 GEO 监控报告")
    parser.add_argument("--days", type=int, default=7, help="报告周期天数（默认7天）")
    args = parser.parse_args()
    generate_report(days=args.days)
