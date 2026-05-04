#!/usr/bin/env python3
"""
generate_schema.py
根据内容格式和元数据生成 JSON-LD 结构化数据

用法：
  python generate_schema.py --format faq --title "标题" --keyword "关键词" \
    --url "https://example.com/page" --brand "品牌名" \
    [--faqs '[{"q":"问题","a":"答案"}]']
"""

import argparse
import json
import sys
from datetime import date


def normalize_faqs(keyword: str, faqs: list) -> list:
    """确保 FAQ 至少 3 条，且结构统一。"""
    normalized = [
        {"q": item.get("q", "").strip(), "a": item.get("a", "").strip()}
        for item in (faqs or [])
        if item.get("q", "").strip() and item.get("a", "").strip()
    ]
    if normalized:
        return normalized
    return [
        {"q": f"什么是{keyword}？", "a": f"{keyword}是指..."},
        {"q": f"{keyword}有哪些应用场景？", "a": "主要应用场景包括..."},
        {"q": f"如何开始使用{keyword}？", "a": "第一步是明确目标和场景。"},
    ]


def make_faq_page(faqs: list) -> dict:
    return {
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": faq["q"],
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": faq["a"]
                }
            }
            for faq in faqs
        ]
    }


def make_howto_schema(title: str, url: str, brand: str, steps: list) -> dict:
    schema = {
        "@context": "https://schema.org",
        "@type": "HowTo",
        "name": title,
        "url": url,
        "author": {"@type": "Organization", "name": brand},
        "datePublished": date.today().isoformat(),
        "step": [
            {
                "@type": "HowToStep",
                "name": step.get("name", f"步骤 {i+1}"),
                "text": step.get("text", ""),
                "position": i + 1
            }
            for i, step in enumerate(steps)
        ]
    }
    return schema


def make_article_schema(title: str, keyword: str, url: str, brand: str) -> dict:
    return {
        "@type": "Article",
        "headline": title,
        "keywords": keyword,
        "url": url,
        "author": {"@type": "Organization", "name": brand},
        "publisher": {
            "@type": "Organization",
            "name": brand,
        },
        "datePublished": date.today().isoformat(),
        "dateModified": date.today().isoformat(),
        "inLanguage": "zh-CN",
    }


def make_comparison_schema(title: str, keyword: str, url: str, brand: str) -> dict:
    """对比页当前使用 Article 主体。"""
    return make_article_schema(title, keyword, url, brand)


def generate_schema(fmt: str, title: str, keyword: str, url: str,
                    brand: str, faqs: list = None, steps: list = None) -> str:
    faqs = normalize_faqs(keyword, faqs)
    steps = steps or []
    graph = []

    if fmt == "faq":
        graph.append(make_article_schema(title, keyword, url, brand))
        graph.append(make_faq_page(faqs))
    elif fmt == "howto":
        if not steps:
            steps = [{"name": "第一步", "text": "..."}, {"name": "第二步", "text": "..."}]
        graph.append(make_howto_schema(title, url, brand, steps))
        graph.append(make_article_schema(title, keyword, url, brand))
        graph.append(make_faq_page(faqs))
    elif fmt in ("comparison", "scenario", "region", "decision"):
        graph.append(make_article_schema(title, keyword, url, brand))
        graph.append(make_faq_page(faqs))
    else:  # definition, default
        graph.append(make_article_schema(title, keyword, url, brand))
        graph.append(make_faq_page(faqs))

    schema = {
        "@context": "https://schema.org",
        "@graph": graph,
    }

    return json.dumps(schema, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="生成 JSON-LD 结构化数据")
    parser.add_argument("--format", required=True,
                        choices=["faq", "howto", "comparison", "definition", "scenario", "region", "decision"],
                        help="内容格式")
    parser.add_argument("--title", required=True, help="文章标题")
    parser.add_argument("--keyword", default="", help="目标关键词")
    parser.add_argument("--url", default="", help="发布 URL")
    parser.add_argument("--brand", default="", help="品牌名称")
    parser.add_argument("--faqs", default="[]", help="FAQ 列表 JSON")
    parser.add_argument("--steps", default="[]", help="步骤列表 JSON")
    args = parser.parse_args()

    try:
        faqs = json.loads(args.faqs)
        steps = json.loads(args.steps)
    except json.JSONDecodeError:
        faqs, steps = [], []

    result = generate_schema(
        fmt=args.format,
        title=args.title,
        keyword=args.keyword,
        url=args.url,
        brand=args.brand,
        faqs=faqs,
        steps=steps,
    )
    print(result)
