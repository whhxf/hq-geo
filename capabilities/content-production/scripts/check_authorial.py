#!/usr/bin/env python3
"""作者化检查：Gate C（模糊修饰语）与 Gate D（机器化模式）的确定性部分。

只报告可解释的文本特征，不输出「人类概率」，不判定成败，不自动改写。
理由见 00-meta/content-engine/07-authorial-quality-system.md：
AI 检测器会对非母语写作者明显误判，也容易通过改写规避。

每个命中只问三个问题：删掉后含义是否变化；能否换成具体动作；能否补事实或条件。
否定词、时间词、范围词和真实的不确定性不得为了降低密度而删除。

Gate E（作者语料校准）需要 Conan 本人的语料，尚未建立，固定报告为 blocked。
"""

import argparse
import json
import re
import statistics
import sys
from pathlib import Path


# Gate C —— 模糊修饰语
DEGREE_WORDS = ["非常", "极其", "十分", "尤其", "真正", "更加", "尤为", "格外"]
EFFECT_WORDS = ["显著", "有效", "全面", "充分", "精准", "高效", "强大", "完善"]
CLICHE_PHRASES = ["持续提升", "深度赋能", "全面覆盖", "有效解决", "充分发挥",
                  "不断优化", "助力企业", "赋能行业", "打造闭环", "降本增效"]
HEDGE_WORDS = ["可能", "通常", "相对", "一定程度上", "或许", "大概", "往往"]

# Gate D —— 机器化模式
CHAT_RESIDUE = ["值得注意的是", "在当今时代", "希望对你有帮助", "总而言之",
                "综上所述", "不难发现", "众所周知", "让我们来看看", "接下来我们将"]
ABSTRACT_UPGRADE = ["本质上", "归根结底", "说到底", "从某种意义上", "深层次来看"]
VAGUE_AUTHORITY = ["研究表明", "数据显示", "业内认为", "有专家指出", "据统计", "实践证明"]
RHETORICAL_QUESTION = ["你有没有想过", "你是否曾经", "你有没有发现", "你有没有遇到过"]

NOT_X_BUT_Y = re.compile(r"不是[^。！？\n]{1,24}?(?:，|,)?\s*(?:而是|就是)[^。！？\n]{1,24}")
NEGATION_OPENING = re.compile(
    r"不是[^。！？\n]{1,24}?[。！？]\s*[^。！？\n]{0,24}?(?:是|应该|问题|关键|重点|核心)")

FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
CODE_BLOCK = re.compile(r"```.*?```", re.DOTALL)
# 换行也是句子边界，否则 markdown 列表和短行会被并成一个超长句
SENTENCE_SPLIT = re.compile(r"(?<=[。！？；])|\n")


def strip_markup(text: str) -> str:
    text = FRONTMATTER.sub("", text)
    text = CODE_BLOCK.sub("", text)
    return text


def paragraphs(text: str) -> list:
    """返回正文段落。跳过标题行和空行。"""
    result = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block or block.startswith("#"):
            continue
        result.append(block)
    return result


def find_words(text: str, words: list) -> list:
    return [word for word in words if word in text]


def excerpt(text: str, word: str, width: int = 16) -> str:
    index = text.find(word)
    if index < 0:
        return text[:width * 2].strip()
    start = max(0, index - width)
    end = min(len(text), index + len(word) + width)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{text[start:end].strip()}{suffix}"


def scan_gate_c(body: list) -> list:
    findings = []
    for number, block in enumerate(body, start=1):
        hits = []
        for word in find_words(block, DEGREE_WORDS):
            hits.append({"word": word, "category": "程度堆叠", "excerpt": excerpt(block, word)})
        for word in find_words(block, EFFECT_WORDS):
            hits.append({"word": word, "category": "无证据效果词", "excerpt": excerpt(block, word)})
        for phrase in find_words(block, CLICHE_PHRASES):
            hits.append({"word": phrase, "category": "套话组合", "excerpt": excerpt(block, phrase)})
        # 重复限定：同一段落里出现 2 个以上模糊限定词
        hedges = find_words(block, HEDGE_WORDS)
        if len(hedges) >= 2:
            hits.append({"word": "、".join(hedges), "category": "重复限定",
                         "excerpt": excerpt(block, hedges[0])})
        if hits:
            findings.append({"paragraph": number, "hits": hits})
    return findings


def scan_gate_d(body: list) -> list:
    findings = []
    for number, block in enumerate(body, start=1):
        hits = []
        for pattern in NOT_X_BUT_Y.finditer(block):
            hits.append({"pattern": "不是 X 而是 Y", "confidence": "high",
                         "excerpt": pattern.group(0)})
        if NEGATION_OPENING.search(block):
            hits.append({"pattern": "先否定再转折", "confidence": "medium",
                         "excerpt": excerpt(block, "不是")})
        for word in find_words(block, CHAT_RESIDUE):
            hits.append({"pattern": "聊天残留", "confidence": "high",
                         "excerpt": excerpt(block, word)})
        for word in find_words(block, ABSTRACT_UPGRADE):
            hits.append({"pattern": "无依据升维", "confidence": "high",
                         "excerpt": excerpt(block, word)})
        for word in find_words(block, VAGUE_AUTHORITY):
            hits.append({"pattern": "模糊权威", "confidence": "medium",
                         "excerpt": excerpt(block, word)})
        for word in find_words(block, RHETORICAL_QUESTION):
            hits.append({"pattern": "替读者提问", "confidence": "high",
                         "excerpt": excerpt(block, word)})
        if hits:
            findings.append({"paragraph": number, "hits": hits})
    return findings


def rhythm(body: list) -> dict:
    """节奏统计。只报告，不判定。"""
    text = "\n".join(body)
    sentences = [item.strip() for item in SENTENCE_SPLIT.split(text) if item.strip()]
    lengths = [len(item) for item in sentences]
    paragraph_lengths = [len(block) for block in body]
    if len(lengths) < 2:
        return {"sentences": len(lengths), "note": "句子太少，不做节奏统计"}
    mean = statistics.mean(lengths)
    deviation = statistics.pstdev(lengths)
    return {
        "sentences": len(lengths),
        "mean_length": round(mean, 1),
        "variation_coefficient": round(deviation / mean, 2) if mean else 0.0,
        "longest": max(lengths),
        "shortest": min(lengths),
        "paragraphs": len(body),
        "paragraph_range": [min(paragraph_lengths), max(paragraph_lengths)],
    }


def check(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    body = paragraphs(strip_markup(raw))
    return {
        "path": str(path),
        "gate_c": scan_gate_c(body),
        "gate_d": scan_gate_d(body),
        "rhythm": rhythm(body),
        "gate_e": "blocked: 作者语料未建立，不虚构 Conan 风格",
    }


def render(report: dict) -> str:
    lines = [f"作者化检查：{report['path']}", ""]
    gate_c = report["gate_c"]
    lines.append(f"Gate C · 模糊修饰语（{sum(len(item['hits']) for item in gate_c)} 处）")
    if not gate_c:
        lines.append("  没有命中。没有命中不代表通过。")
    for item in gate_c:
        lines.append(f"  第 {item['paragraph']} 段")
        for hit in item["hits"]:
            lines.append(f"    {hit['word']} — {hit['category']}")
            lines.append(f"      {hit['excerpt']}")
    lines.append("")

    gate_d = report["gate_d"]
    lines.append(f"Gate D · 机器化模式（{sum(len(item['hits']) for item in gate_d)} 处）")
    if not gate_d:
        lines.append("  没有命中。没有命中不代表通过。")
    for item in gate_d:
        lines.append(f"  第 {item['paragraph']} 段")
        for hit in item["hits"]:
            lines.append(f"    {hit['pattern']}（置信度 {hit['confidence']}）")
            lines.append(f"      {hit['excerpt']}")
    lines.append("")

    stats = report["rhythm"]
    lines.append("节奏")
    if "note" in stats:
        lines.append(f"  {stats['note']}")
    else:
        lines.append(f"  句长：{stats['sentences']} 句，均值 {stats['mean_length']} 字，"
                     f"变异系数 {stats['variation_coefficient']}"
                     f"（越低越均匀），范围 {stats['shortest']}—{stats['longest']}")
        lines.append(f"  段落：{stats['paragraphs']} 段，"
                     f"{stats['paragraph_range'][0]}—{stats['paragraph_range'][1]} 字")
    lines.append("")

    lines.append("Gate E · 作者语料校准")
    lines.append(f"  {report['gate_e']}")
    lines.append("")
    lines.append("每个命中只问三个问题：删掉后含义是否变化；能否换成具体动作；能否补事实或条件。")
    lines.append("这个脚本不判定成败，也不自动改写。")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="作者化检查（只诊断，不改写）")
    parser.add_argument("path", type=Path)
    parser.add_argument("--json", action="store_true", help="输出机器可读结果")
    args = parser.parse_args()
    if not args.path.is_file():
        print(f"找不到文件：{args.path}", file=sys.stderr)
        return 2
    report = check(args.path)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
