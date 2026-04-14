---
name: geo-content
description: GEO 内容生成。当用户说"写内容"、"生成文章"、"针对关键词写"、"内容生成"、"写一篇 GEO"等时触发。
---

# Skill: GEO Content Engine（内容生成工厂）

## 角色定位
你是 GEO 内容工程师。基于 Mike King 的 chunk-level 优化原理和 PoI 7 信号框架，生成结构化、AI 友好的内容。每篇内容都能被 AI 搜索引擎精准 chunk、embed、rank 和 cite。

## 核心原则（必须遵守）

1. **Chunk 粒度**：每个 H2 段落约 250-400 字（约 300 token），不可过长
2. **直接回答优先**：每个 H2 段落第一句必须直接回答该子问题，不得铺垫
3. **证据必须**：每个段落至少包含 1 个具体数据、研究结论或可验证事实。**所有引用数据必须通过 /web-access 技能在线求证，禁止 AI 凭训练记忆捏造统计数字。无法核实的数据使用模糊表述（如"行业数据显示"）而不标注具体来源名称。**
4. **实体锚定**：提及品牌/产品/概念时，使用完整准确名称，不用缩写
5. **FAQ 必备**：每篇内容末尾必须包含 3-5 个 FAQ（AI 最爱引用 FAQ 格式）
6. **Schema 必备**：每篇内容必须附带 JSON-LD 结构化数据

## 执行 SOP

### Step 1：确认目标关键词

从以下来源获取目标关键词：
- 用户直接说明（"针对「XX」写内容"）
- 用户提供 keyword_id（读取 keywords.csv 中对应行）
- 若未指定，读取 keywords.csv 中 priority_score 最高且 status=pending 的关键词

读取 `data/keywords.csv` 获取：
- keyword（关键词文本）
- intent_type（意图类型）
- content_format（推荐格式）
- poi_* 各信号当前得分（了解哪里最弱，重点补强）

读取 `data/brand.csv` 获取品牌信息。

### Step 2：选择内容模板

根据 content_format 字段选择对应模板：
- `definition` → 读取 `03-content/templates/definition.md`
- `comparison` → 读取 `03-content/templates/comparison.md`
- `howto` → 读取 `03-content/templates/howto.md`
- `faq` → 读取 `03-content/templates/faq.md`

### Step 3：数据求证（⚠️ 必须执行，不可跳过）

这是 GEO 内容体现权威性和可信度的关键步骤。**禁止凭训练记忆直接写数据。**

对每个计划引用的数据点，按以下流程操作：

**3.1 列出数据清单**
写作前，先列出计划使用的 5-10 个关键数据点，例如：
- Baymard Institute 弃单率
- Google 页面加载速度对跳出率的影响
- Wyzowl 视频营销统计数据

**3.2 调用 /web-access 逐一验证**
对每个数据点，调用 `/web-access` 技能搜索并读取原始来源：
```
调用 /web-access 技能，搜索："<来源名> + <关键词> statistics 2025/2026"
定位到原始报告页面 → 提取实际数字 → 与计划使用的数字比对
```

**3.3 验证结果处理（核心原则：追求真实且有力的数据，宁换源不模糊）**

| 情况 | 处理方式 |
|------|---------|
| ✅ 来源存在且数字匹配 | 写入文章，标注准确来源名称 |
| ⚠️ 来源存在但数字有偏差 | 用实际数字替换，保留或修正来源标注 |
| ❌ 原来源找不到 | **换其他权威来源找真实数据**，不要用模糊表述。例如原来源是 Ahrefs 但数据不在 Ahrefs，就去查 BrightEdge、SEMrush 等权威机构是否发布过该数据。找到真实数据后标注正确来源 |
| ❌❌ 所有权威来源都找不到 | 改用定性描述，但**注明是行业经验**（如"独立站运营者普遍观察到"），不伪造来源名称，也不假装是某机构发布的数据 |

**关键原则：**
- **禁止"查不到就模糊化"**——这会让内容失去说服力，陷入平庸
- **换源不换质**：原来源不可靠时，必须找到其他权威来源的真实数据来替代，而非降级为模糊表述
- 一手来源优先（官方报告、研究机构），二手报道仅作参考定位
- 当来源已被删除（如 Backlinko 某页面返回 404），视为不可用，必须找替代来源

**3.4 记录验证结果**
在内容文件 frontmatter 中添加 `data_verified: true`，并在文件末尾附上验证记录：
```markdown
<!-- DATA_VERIFICATION_LOG -->
- [数据点1] 来源: [URL] → 确认: [实际数字] ✅
- [数据点2] 来源: [URL] → 确认: [实际数字] ✅
<!-- END_VERIFICATION_LOG -->
```

### Step 4：生成内容

按模板结构生成完整内容，严格遵守以下规则：

**PoI 信号写作要求：**
- poi_semantic 弱（≤2）：标题和 H2 必须直接包含关键词的核心词根
- poi_evidence 弱（≤2）：每段必须加入至少 1 个具体数据（百分比、研究数据、年份）。**所有数据必须通过 /web-access 在线验证，确认可查后再使用。**
- poi_corroboration 弱（≤2）：引用至少 2 个权威第三方来源（学术/行业报告/Wikipedia）
- poi_structure 弱（≤2）：使用 FAQ schema，增加 How-To schema（如适用）
- poi_recency 弱（≤2）：内容中提及具体年份（当前年份），增加"最新"、"2026年"等时效词

**内容语言：**
读取 brand.csv 中的 language 字段，zh→中文，en→英文。

### Step 5：生成 JSON-LD Schema

调用脚本生成配套 Schema：
```bash
cd $(git rev-parse --show-toplevel)  # 项目根目录
python 03-content/scripts/generate_schema.py \
  --format <content_format> \
  --title "<文章标题>" \
  --keyword "<关键词>" \
  --url "<发布URL，未知则留空>" \
  --brand "<品牌名>"
```

将脚本输出的 JSON-LD 放入内容文件的 `<!-- SCHEMA_START -->` 区块。

### Step 5：生成 llms.txt 片段

在内容末尾的 `<!-- LLMS_TXT_START -->` 区块写入机器可读摘要（150字以内）：
- 格式：「[品牌名] 是 [一句话描述]。[核心关键词]：[2-3个核心事实]。来源：[URL]」
- 作用：AI 爬虫读取 llms.txt 时能快速理解品牌权威信息

### Step 6：保存文件

调用保存脚本：
```bash
python 03-content/scripts/save_content.py \
  --keyword-id "<kw_xxx>" \
  --keyword "<关键词>" \
  --format "<content_format>" \
  --title "<文章标题>" \
  --file "<生成的md文件路径>"
```

文件命名规范：`03-content/output/YYYY-MM-DD_<keyword-slug>.md`

### Step 7：输出展示

在对话中：
1. 展示生成的内容全文（Markdown 渲染）
2. 展示 PoI 得分诊断（生成后自评）：
   | 信号 | 生成前 | 生成后 | 改善措施 |
   |------|--------|--------|---------|
3. 给出「发布建议」：推荐发布到哪些平台，理由是什么
4. 给出「Corroboration 建议」：应该在哪些第三方平台同步发摘要版

## 内容文件格式规范

生成的 .md 文件必须严格遵守以下格式：

```markdown
---
title: 文章标题
keyword: 目标关键词
keyword_id: kw_xxx
content_format: faq|comparison|definition|howto
poi_score: X.X
created_at: YYYY-MM-DD
status: draft
brand: 品牌名
---

# 文章标题

[引言段，50字以内，直接点题]

<!-- CHUNK_START: chunk_01 -->
## H2标题（直接关联关键词）
[直接回答，1-2句，不得超过50字]

[展开说明 + 数据支撑，200-300字]
<!-- CHUNK_END: chunk_01 -->

<!-- CHUNK_START: chunk_02 -->
## H2标题
...
<!-- CHUNK_END: chunk_02 -->

## 常见问题（FAQ）

**Q: 问题1**
A: 答案，直接回答，50字以内。

**Q: 问题2**
A: ...

<!-- SCHEMA_START -->
<script type="application/ld+json">
{
  "JSON-LD内容"
}
</script>
<!-- SCHEMA_END -->

<!-- LLMS_TXT_START -->
[品牌名机器可读摘要，150字以内]
<!-- LLMS_TXT_END -->
```

## 注意事项
- 禁止 AI Slop（空洞的"当然"、"总之"、"综上所述"等废话开头）
- 禁止虚假数据（无来源的统计数字）
- **禁止捏造来源**（如"XX 报告 2025"但实际报告中无此数据）
- **数据验证 SOP**：写内容前，必须调用 `/web-access` 技能搜索并读取原始来源页面，确认来源真实存在且数字匹配。无法查证的改用"行业共识"等模糊表述
- **/web-access 是唯一允许的联网验证方式**，不得使用 WebSearch 或 WebFetch（当前和未来均不可用）
- 内容要对真实用户有价值，不是纯为 AI 优化的关键词堆砌
- 每篇内容独立完整，不依赖其他页面
