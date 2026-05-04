#!/usr/bin/env python3
"""
score_quality.py
预发布内容质量评分：6 维度加权评估。

用法：
  python score_quality.py --file "03-content/output/2026-05-04_xxx.md" --threshold 7.0
  python score_quality.py --file "..." --content-id "ct_001"
"""

import argparse
import csv
import json
import os
import re
import sys
from datetime import date

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "lib"))
from hq_geo_lib import get_next_id_sequential, csv_append

SCORE_CSV = os.path.join(ROOT, "data", "prepublish_score.csv")
KEYWORDS_CSV = os.path.join(ROOT, "data", "keywords.csv")
QUESTIONS_CSV = os.path.join(ROOT, "data", "questions.csv")
BRAND_CSV = os.path.join(ROOT, "data", "brand.csv")
EVIDENCE_CSV = os.path.join(ROOT, "data", "evidence.csv")

FIELDNAMES = [
    "id", "content_id", "content_title",
    "intent_coverage", "scene_matching", "structure_clarity",
    "keyword_coverage", "verifiability", "language_naturalness",
    "weighted_score", "pass_threshold", "status", "scored_at", "reviewer", "notes"
]

# AI Slop patterns (shared with audit_content.py)
AI_SLOP_PATTERNS = [
    r'当然，', r'当然可以', r'当然啦',
    r'总之，', r'总而言之', r'综上所述',
    r'值得注意的是', r'值得一提的是',
    r'不可否认', r'不可否认的是',
    r'随着科技的不断发展', r'在当今社会',
    r'作为一个.*的.*',
    r'首先.*其次.*最后.*总结',
]

# 权威数据来源白名单
AUTHORITATIVE_SOURCES = {
    'baymard', 'baymard institute', 'brightedge', 'hubspot',
    'google doubleclick', 'thinkwithgoogle', 'forrester', 'gartner',
    'mckinsey', 'statista', 'similarweb', 'wyzowl',
    'shopify', 'google', 'google pagespeed', 'google search console',
    'meta', 'facebook', 'instagram', 'tiktok', 'klaviyo',
    'ahrefs', 'semrush', 'moz', 'search engine land',
    'search engine journal', 'backlinko', 'campaign monitor',
    'statcounter',
}

# 权重配置
WEIGHTS = {
    "intent_coverage": 0.25,
    "scene_matching": 0.15,
    "structure_clarity": 0.15,
    "keyword_coverage": 0.15,
    "verifiability": 0.20,
    "language_naturalness": 0.10,
}


def load_csv(path):
    """安全加载 CSV"""
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_brand_info():
    """加载品牌信息"""
    rows = load_csv(BRAND_CSV)
    return {r.get("field", ""): r.get("value", "") for r in rows}


def score_dimension(name, content, brand_info, keywords=None, questions=None):
    """
    单个维度评分，返回 (score, reason)。
    所有维度统一返回 1-10 整数分和理由字符串。
    """
    scorers = {
        "intent_coverage": _score_intent,
        "scene_matching": _score_scene,
        "structure_clarity": _score_structure,
        "keyword_coverage": _score_keyword,
        "verifiability": _score_verifiability,
        "language_naturalness": _score_naturalness,
    }
    fn = scorers.get(name, lambda *a: (5, "未实现"))
    return fn(content, brand_info, keywords, questions)


def _score_intent(content, brand, keywords, questions):
    """意图覆盖评分"""
    score = 5
    reasons = []

    # 检查 FAQ 数量
    faq_count = len(re.findall(r'\*\*Q[:：]', content))
    if faq_count >= 3:
        score += 1
        reasons.append("FAQ >= 3 条")
    elif faq_count > 0:
        reasons.append(f"FAQ 仅 {faq_count} 条")
    else:
        score -= 1
        reasons.append("缺少 FAQ")

    # 检查是否覆盖问题层子问题
    if questions:
        matched = sum(1 for q in questions if q.get("question", "") in content)
        total = len(questions)
        if total > 0:
            ratio = matched / total
            if ratio >= 0.8:
                score += 2
                reasons.append(f"子问题覆盖 {matched}/{total}")
            elif ratio >= 0.5:
                score += 1
                reasons.append(f"子问题覆盖 {matched}/{total}")
            else:
                score -= 1
                reasons.append(f"子问题覆盖不足 {matched}/{total}")

    return max(1, min(10, score)), "; ".join(reasons) if reasons else "默认评分"


def _score_scene(content, brand, keywords, questions):
    """场景匹配评分"""
    score = 5
    reasons = []

    # 检查场景关键词
    scene_patterns = [r'当[^\s]{1,10}时', r'如果[^\s]{1,10}', r'在[^\s]{1,10}场景',
                       r'[^\s]{1,5}用户', r'[^\s]{1,5}客户', r'使用场景']
    scene_hits = sum(len(re.findall(p, content)) for p in scene_patterns)

    if scene_hits >= 5:
        score += 2
        reasons.append(f"场景描述丰富 ({scene_hits} 处)")
    elif scene_hits >= 2:
        score += 1
        reasons.append(f"场景描述适中 ({scene_hits} 处)")
    else:
        score -= 1
        reasons.append("场景描述不足")

    # 检查是否提到目标客户
    target = brand.get("target_customer", "")
    if target and any(kw in content for kw in [target[:10]] if target[:10]):
        score += 1
        reasons.append("匹配目标客户描述")

    return max(1, min(10, score)), "; ".join(reasons) if reasons else "默认评分"


def _score_structure(content, brand, keywords, questions):
    """结构清晰评分"""
    score = 5
    reasons = []

    # CHUNK 配对
    starts = len(re.findall(r'<!-- CHUNK_START: (chunk_\d+) -->', content))
    ends = len(re.findall(r'<!-- CHUNK_END: chunk_\d+ -->', content))

    if starts == ends and starts > 0:
        score += 2
        reasons.append(f"CHUNK 配对正确 ({starts} 对)")
    elif starts > 0:
        score -= 1
        reasons.append(f"CHUNK 不匹配: {starts} START, {ends} END")
    else:
        score -= 2
        reasons.append("无 CHUNK 标记")

    # H2 标题数量
    h2_count = len(re.findall(r'^## .+', content, re.MULTILINE))
    if h2_count >= 3:
        score += 1
        reasons.append(f"H2 标题 {h2_count} 个")
    elif h2_count > 0:
        reasons.append(f"H2 标题仅 {h2_count} 个")
    else:
        score -= 1
        reasons.append("无 H2 标题")

    # 检查段落是否以直接回答开头（不铺垫）
    return max(1, min(10, score)), "; ".join(reasons) if reasons else "默认评分"


def _score_keyword(content, brand, keywords, questions):
    """关键词覆盖评分"""
    score = 5
    reasons = []

    if not keywords:
        reasons.append("无 keywords.csv 数据，无法评估关键词覆盖")
        return score, "; ".join(reasons)

    # 检查关键词在内容中的出现
    matched = 0
    for kw in keywords:
        kw_text = kw.get("keyword", "")
        if kw_text and kw_text in content:
            matched += 1

    total = len(keywords)
    if total > 0:
        ratio = matched / total
        if ratio >= 0.6:
            score += 2
            reasons.append(f"关键词覆盖 {matched}/{total}")
        elif ratio >= 0.3:
            score += 1
            reasons.append(f"关键词覆盖 {matched}/{total}")
        else:
            score -= 1
            reasons.append(f"关键词覆盖不足 {matched}/{total}")

    return max(1, min(10, score)), "; ".join(reasons) if reasons else "默认评分"


def _score_verifiability(content, brand, keywords, questions):
    """可验证性评分"""
    score = 5
    reasons = []

    # 检查数据验证日志
    verif_match = re.search(
        r'<!-- DATA_VERIFICATION_LOG -->(.*?)<!-- END_VERIFICATION_LOG -->',
        content, re.DOTALL
    )

    if verif_match:
        log_text = verif_match.group(1)
        verified = len(re.findall(r'\u2705', log_text))  # checkmark
        if verified >= 3:
            score += 3
            reasons.append(f"{verified} 条数据已验证")
        elif verified > 0:
            score += 1
            reasons.append(f"仅 {verified} 条数据已验证")
        else:
            score -= 1
            reasons.append("有验证日志但无已验证记录")
    else:
        score -= 2
        reasons.append("缺少数据验证日志")

    # 检查证据库是否有记录
    evidence = load_csv(EVIDENCE_CSV)
    if evidence:
        score += 1
        reasons.append(f"evidence.csv 有 {len(evidence)} 条记录")

    # 检查是否有百分比数据但未验证
    pct_count = len(re.findall(r'\d+%', content))
    if pct_count > 0 and not verif_match:
        score -= 1
        reasons.append(f"{pct_count} 个百分比数据未验证")

    return max(1, min(10, score)), "; ".join(reasons) if reasons else "默认评分"


def _score_naturalness(content, brand, keywords, questions):
    """语言自然评分"""
    score = 8  # 默认较高
    reasons = []

    # AI Slop 检测
    slop_count = 0
    for pattern in AI_SLOP_PATTERNS:
        matches = re.findall(pattern, content)
        slop_count += len(matches)

    if slop_count == 0:
        score += 1
        reasons.append("无 AI Slop 模式")
    elif slop_count <= 2:
        score -= 1
        reasons.append(f"检测到 {slop_count} 处 AI Slop")
    else:
        score -= 3
        reasons.append(f"检测到 {slop_count} 处 AI Slop")

    return max(1, min(10, score)), "; ".join(reasons) if reasons else "默认评分"


def calculate_weighted_score(scores):
    """计算加权总分"""
    total = 0.0
    for dim, weight in WEIGHTS.items():
        total += scores.get(dim, 5) * weight
    return round(total, 2)


def determine_status(weighted_score, threshold):
    """确定状态"""
    if weighted_score >= threshold:
        return "pass"
    elif weighted_score >= threshold * 0.71:  # ~5.0 when threshold=7.0
        return "needs_revision"
    else:
        return "fail"


def score_file(filepath, content_id="", threshold=7.0):
    """对文件进行完整评分"""
    if not os.path.exists(filepath):
        print(f"文件不存在: {filepath}", file=sys.stderr)
        sys.exit(1)

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    brand = load_brand_info()
    keywords = load_csv(KEYWORDS_CSV)
    questions = load_csv(QUESTIONS_CSV)

    # 提取标题
    title_match = re.search(r'^title:\s*(.+)$', content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else os.path.basename(filepath)

    # 各维度评分
    dimensions = [
        "intent_coverage", "scene_matching", "structure_clarity",
        "keyword_coverage", "verifiability", "language_naturalness"
    ]

    scores = {}
    notes_parts = []
    for dim in dimensions:
        score, reason = score_dimension(dim, content, brand, keywords, questions)
        scores[dim] = score
        notes_parts.append(f"{dim}={score}({reason})")

    weighted = calculate_weighted_score(scores)
    status = determine_status(weighted, threshold)

    # 保存记录
    record = {
        "id": get_next_id_sequential("ps", SCORE_CSV),
        "content_id": content_id or "",
        "content_title": title,
        "intent_coverage": scores["intent_coverage"],
        "scene_matching": scores["scene_matching"],
        "structure_clarity": scores["structure_clarity"],
        "keyword_coverage": scores["keyword_coverage"],
        "verifiability": scores["verifiability"],
        "language_naturalness": scores["language_naturalness"],
        "weighted_score": weighted,
        "pass_threshold": threshold,
        "status": status,
        "scored_at": date.today().isoformat(),
        "reviewer": "auto",
        "notes": "; ".join(notes_parts),
    }
    csv_append(SCORE_CSV, FIELDNAMES, record)

    # 输出结果
    print(f"\n{'='*50}")
    print(f"预发布质量评分: {title}")
    print(f"{'='*50}")

    dim_labels = {
        "intent_coverage": "意图覆盖",
        "scene_matching": "场景匹配",
        "structure_clarity": "结构清晰",
        "keyword_coverage": "关键词覆盖",
        "verifiability": "可验证性",
        "language_naturalness": "语言自然",
    }

    for dim in dimensions:
        bar = "\u2588" * scores[dim] + "\u2591" * (10 - scores[dim])
        label = dim_labels.get(dim, dim)
        print(f"  {label:8s}  [{bar}]  {scores[dim]}/10  (权重 {int(WEIGHTS[dim]*100)}%)")

    status_label = {"pass": "PASS", "needs_revision": "NEEDS_REVISION", "fail": "FAIL"}
    print(f"\n  加权总分: {weighted} / 10.0")
    print(f"  阈值: {threshold}")
    print(f"  评级: {status_label[status]}")

    if status != "pass":
        print(f"\n  薄弱维度:")
        for dim in dimensions:
            if scores[dim] <= 5:
                label = dim_labels.get(dim, dim)
                print(f"    - {label} ({scores[dim]}/10)")

    return scores, weighted, status


def main():
    parser = argparse.ArgumentParser(description="预发布质量评分")
    parser.add_argument("--file", required=True, help="内容文件路径")
    parser.add_argument("--content-id", default="", help="内容 ID")
    parser.add_argument("--threshold", type=float, default=7.0, help="通过阈值 (默认 7.0)")
    args = parser.parse_args()

    score_file(args.file, args.content_id, args.threshold)


if __name__ == "__main__":
    main()
