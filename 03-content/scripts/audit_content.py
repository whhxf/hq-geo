#!/usr/bin/env python3
"""
Content Quality Auditor - 内容质量自动审计脚本

在内容生成完成后自动运行，检查以下项目：
1. Chunk 字数（250-400 字）
2. llms.txt 长度（≤150 字符）
3. Schema FAQ 与正文 FAQ 数量匹配
4. Chunk 编号连续性
5. CHUNK_START/END 配对
6. 必要元素检查（H2、FAQ、Schema、验证日志）
7. 数据有效性审计（所有引用数据必须有来源标记）
8. 权威性检查（数据来源是否为权威机构/官方来源）

用法：
    python audit_content.py <file_path>           # 审计单文件
    python audit_content.py <file_path> --fix      # 审计并尝试自动修复
    python audit_content.py 03-content/output/*.md # 审计多文件
"""

import re
import sys
import json
import argparse


def count_zi(text):
    """估算中文字数：中文字符数 + 英文单词数"""
    chinese = len(re.findall(r'[\u4e00-\u9fff]', text))
    english = len(re.findall(r'[a-zA-Z]+', text))
    return chinese + english


# 权威数据来源白名单
AUTHORITATIVE_SOURCES = {
    # 研究机构
    'baymard', 'baymard institute',
    'brightedge',
    'hubspot',
    'google doubleclick', 'thinkwithgoogle',
    'forrester', 'gartner', 'mckinsey',
    'statista',
    'similarweb',
    'wyzowl',
    # 平台官方
    'shopify',
    'google', 'google pageSpeed', 'google search console',
    'meta', 'facebook', 'instagram', 'tiktok',
    'klaviyo',
    # 技术事实
    '技术事实',
    # SEO 工具
    'ahrefs', 'semrush', 'moz',
    'search engine land', 'search engine journal', 'searchengineland',
    # 其他
    'backlinko',
    'Campaign Monitor',
    'StatCounter',
}

# AI Slop 模式（不应出现在内容中）
AI_SLOP_PATTERNS = [
    r'当然，', r'当然可以', r'当然啦',
    r'总之，', r'总而言之', r'综上所述',
    r'值得注意的是', r'值得一提的是',
    r'不可否认', r'不可否认的是',
    r'随着科技的不断发展', r'在当今社会',
    r'作为一个.*的.*',  # "作为一个AI助手"
    r'首先.*其次.*最后.*总结',  # 过度模板化
]


def audit_file(filepath, auto_fix=False):
    """审计单个文件，返回问题列表和修复建议"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    issues = []
    warnings = []

    # === 1. CHUNK_START/END 配对检查 ===
    starts = re.findall(r'<!-- CHUNK_START: (chunk_\d+) -->', content)
    ends = re.findall(r'<!-- CHUNK_END: (chunk_\d+) -->', content)

    if len(starts) != len(ends):
        issues.append(f"CHUNK 标记不匹配: {len(starts)} 个 START, {len(ends)} 个 END")

    # === 2. Chunk 编号连续性 ===
    expected = [f'chunk_{i:02d}' for i in range(1, len(starts) + 1)]
    if starts != expected:
        issues.append(f"Chunk 编号不连续: 实际 {starts}, 期望 {expected}")

    # === 3. Chunk 字数检查 ===
    chunks = re.findall(
        r'<!-- CHUNK_START: (chunk_\d+) -->(.*?)<!-- CHUNK_END: \1 -->',
        content, re.DOTALL
    )

    for chunk_id, chunk_text in chunks:
        zi = count_zi(chunk_text.strip())
        if zi < 250:
            issues.append(f"{chunk_id}: {zi} 字（低于 250 下限，差 {250 - zi} 字）")
        elif zi > 400:
            issues.append(f"{chunk_id}: {zi} 字（超过 400 上限，超 {zi - 400} 字）")

    # === 4. llms.txt 长度检查 ===
    llms_match = re.search(
        r'<!-- LLMS_TXT_START -->(.*?)<!-- LLMS_TXT_END -->',
        content, re.DOTALL
    )
    if llms_match:
        llms_text = llms_match.group(1).strip()
        llms_len = len(llms_text)
        if llms_len > 150:
            issues.append(f"llms.txt 超长: {llms_len} 字符（上限 150，超 {llms_len - 150}）")
    else:
        issues.append("缺少 LLMS_TXT_START/END 标记")

    # === 5. Schema FAQ 与正文 FAQ 匹配 ===
    faq_section = re.search(
        r'## 常见问题.*?(?=<!-- SCHEMA|<!-- LLMS_TXT)',
        content, re.DOTALL
    )
    if faq_section:
        faq_q = re.findall(r'\*\*Q[:：]', faq_section.group(0))
        faq_count = len(faq_q)
    else:
        faq_count = 0

    # Schema FAQ 数量
    schema_match = re.search(
        r'<script type="application/ld\+json">(.*?)</script>',
        content, re.DOTALL
    )
    if schema_match:
        try:
            schema_data = json.loads(schema_match.group(1))
            schema_faq_count = 0
            for graph_item in schema_data.get('@graph', []):
                if graph_item.get('@type') == 'FAQPage':
                    schema_faq_count = len(graph_item.get('mainEntity', []))
                    break

            if faq_count != schema_faq_count:
                issues.append(
                    f"FAQ 数量不匹配: 正文 {faq_count} 条, Schema {schema_faq_count} 条"
                )
            elif faq_count < 3:
                issues.append(f"FAQ 数量不足: 仅 {faq_count} 条（至少 3 条）")
        except json.JSONDecodeError:
            issues.append("Schema JSON 解析失败")
    else:
        issues.append("缺少 JSON-LD Schema")

    # === 6. 数据有效性审计 ===
    # 6a. 检查是否有数据验证日志
    verif_log = re.search(
        r'<!-- DATA_VERIFICATION_LOG -->(.*?)<!-- END_VERIFICATION_LOG -->',
        content, re.DOTALL
    )
    if not verif_log:
        issues.append("缺少数据验证日志（DATA_VERIFICATION_LOG）")
    else:
        log_text = verif_log.group(1)
        # 检查每条数据是否有来源标记
        data_lines = [l.strip() for l in log_text.split('\n') if l.strip() and not l.strip().startswith(('数据求证记录', '- [数据'))]

        # 检查是否有 ✅ 标记（表示已验证）
        verified_count = len(re.findall(r'✅', log_text))
        unverified = re.findall(r'^[-•]\s+(?!.*✅)(.+)$', log_text, re.MULTILINE)
        if unverified:
            for u in unverified:
                if u.strip():
                    issues.append(f"数据未验证: {u.strip()[:60]}")

        # 检查是否有来源标注
        source_lines = re.findall(r'^[-•]\s+.*?来源[：:]\s*(\S+)', log_text, re.MULTILINE)

    # 6b. 检查正文中的数据声明是否有来源标注
    # 查找包含百分比、数字统计的句子
    stat_patterns = [
        r'[\d]+%',           # 百分比
        r'约\s*[\d]+',       # 约XX
        r'提升\s*[\d]+%',    # 提升XX%
        r'增加\s*[\d]+%',    # 增加XX%
        r'减少\s*[\d]+%',    # 减少XX%
    ]

    # 提取 chunk 正文（不含 FAQ 和 schema）
    body_content = re.sub(r'<!-- SCHEMA_START -->.*', '', content, flags=re.DOTALL)
    body_content = re.sub(r'<!-- DATA_VERIFICATION_LOG -->.*', '', body_content, flags=re.DOTALL)

    # 检查是否有年份标记（时效性）
    current_year = '2026'
    if current_year not in body_content:
        warnings.append(f"内容中未提及当前年份（{current_year}），可能影响时效性评分")

    # 6c. 权威性检查 - 数据来源是否在白名单中
    if verif_log:
        log_text = verif_log.group(1)
        # 提取来源名称第一个词
        sources_mentioned = re.findall(r'来源\s+([^\s:：/]+)', log_text)
        for src in sources_mentioned:
            src_lower = src.lower().rstrip('。')
            is_authoritative = any(
                auth in src_lower for auth in AUTHORITATIVE_SOURCES
            )
            if not is_authoritative and src not in ('技术事实',):
                warnings.append(f"数据来源权威性待确认: {src}")

    # === 7. AI Slop 检查 ===
    slop_found = []
    for pattern in AI_SLOP_PATTERNS:
        matches = re.findall(pattern, body_content)
        if matches:
            slop_found.extend(matches)

    if slop_found:
        warnings.append(f"检测到 AI Slop 模式: {slop_found[:3]}")

    # === 8. 必要元素检查 ===
    if not re.findall(r'^## .+', content, re.MULTILINE):
        issues.append("缺少 H2 标题")

    if 'SCHEMA_START' not in content:
        issues.append("缺少 Schema 标记")

    # === 9. 品牌提及检查 ===
    brand_match = re.search(r'^brand:\s*(.+)$', content, re.MULTILINE)
    if brand_match:
        brand = brand_match.group(1).strip()
        if brand and brand not in ('', 'None'):
            if brand not in body_content:
                warnings.append(f"品牌 {brand} 在正文中未提及")

    # === 输出结果 ===
    fname = filepath.split('/')[-1]
    status = "❌ FAIL" if issues else ("⚠️ WARN" if warnings else "✅ PASS")
    print(f"\n{'='*60}")
    print(f"{status} | {fname}")
    print(f"{'='*60}")

    if issues:
        print("  【错误】")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. ❌  {issue}")

    if warnings:
        print("  【警告】")
        for i, warn in enumerate(warnings, 1):
            print(f"  {i}. ⚠️  {warn}")

    if not issues and not warnings:
        print("  所有检查通过")

    data_count = len(re.findall(r'✅', verif_log.group(1))) if verif_log else 0
    print(f"  Chunks: {len(chunks)} | FAQ: {faq_count} | "
          f"llms.txt: {llms_len if llms_match else 'N/A'} chars | "
          f"已验证数据: {data_count} 条")

    return len(issues) == 0


def main():
    parser = argparse.ArgumentParser(description='Content Quality Auditor')
    parser.add_argument('files', nargs='+', help='Content markdown files to audit')
    parser.add_argument('--fix', action='store_true', help='Auto-fix issues (not yet implemented)')
    args = parser.parse_args()

    total = len(args.files)
    passed = 0

    for f in args.files:
        if audit_file(f, auto_fix=args.fix):
            passed += 1

    print(f"\n{'='*60}")
    print(f"总计: {passed}/{total} 通过")
    if passed == total:
        print("🎉 全部通过")
    else:
        print(f"⚠️  {total - passed} 篇需要修复")
    print(f"{'='*60}")

    sys.exit(0 if passed == total else 1)


if __name__ == '__main__':
    main()
