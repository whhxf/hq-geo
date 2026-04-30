# GEO Engine · 需求说明书 PRD

**版本：** v0.1 草稿，待确认  
**形态：** 本地文件夹应用（无 Web UI，Claude Code + Python + CSV）  
**目标用户：** 先自用，跑出效果后再考虑产品化  
**日期：** 2026-04-08

---

## 0. 一句话定义

> 一个住在本地文件夹里的 GEO 作战系统。  
> 你对 Claude 说话，它调用各子模块的 Python 脚本和 Skill，  
> 帮你完成从「关键词发现」到「内容生产」到「AI 平台监控与报告」的闭环，  
> 所有数据存在 CSV 里，所有内容存在 Markdown 文件里，没有数据库，没有后端服务。

> 实现说明：当前仓库为本地模板形态，发布环节默认手动执行；自动发布与自动调度不在当前实现范围。

---

## 1. 核心设计原则

| 原则 | 具体含义 |
|------|----------|
| **文件夹即应用** | 每个子模块是独立文件夹，可以单独使用，也可以串联 |
| **对话即操作** | 所有功能通过和 Claude 对话触发，不需要记命令行参数 |
| **文本即数据** | CSV 是数据库，Markdown 是内容仓库，无需安装任何数据库 |
| **Python 即引擎** | 所有需要确定性执行的逻辑（监控、写文件、读数据）用 Python 脚本实现 |
| **Skill 即封装** | 每个子模块的「怎么做」封装在 SKILL.md 里，Claude 读到即会执行 |
| **渐进式复杂度** | 每个模块可以单独跑，不依赖前一个模块的完成 |

---

## 2. 整体文件夹结构

```
hq-geo/
│
├── 00-meta/PRD.md                ← 本文件
├── README.md                     ← 使用说明 & 快速开始
│
├── data/                         ← 统一数据层（所有模块共享）
│   ├── brand.csv                 ← 品牌档案（一次填写，全局使用）
│   ├── keywords.csv              ← GEO 关键词库（模块1输出，其他模块读取）
│   ├── content.csv               ← 内容记录索引（模块3输出）
│   ├── monitor_log.csv           ← 监控原始日志（模块4输出）
│   └── competitors.csv           ← 竞品信息（模块2输出）
│
├── 01-intent/                    ← 意图分析 & 关键词生成
│   ├── SKILL.md
│   └── scripts/
│       └── save_keywords.py      ← 将生成结果写入 keywords.csv
│
├── 02-compete/                   ← 竞争分析
│   ├── SKILL.md
│   └── scripts/
│       ├── query_ai_platform.py  ← 向 AI 平台发送查询，抓取引用
│       └── save_competitors.py   ← 写入 competitors.csv
│
├── 03-content/                   ← 内容生成工厂
│   ├── SKILL.md
│   ├── templates/
│   │   ├── definition.md         ← 「什么是X」模板
│   │   ├── comparison.md         ← 「X vs Y」模板
│   │   ├── howto.md              ← 「如何做X」模板
│   │   └── faq.md                ← FAQ 集群模板
│   ├── scripts/
│   │   ├── generate_schema.py    ← 生成 JSON-LD Schema
│   │   └── save_content.py       ← 保存内容 & 更新 content.csv
│   └── output/                   ← 生成的内容文件存放于此
│       └── .gitkeep
│
├── 04-monitor/                   ← AI 平台引用监控
│   ├── SKILL.md
│   └── scripts/
│       ├── monitor.py            ← 主监控脚本（每日运行）
│       └── analyze_trend.py      ← 读取 monitor_log.csv，计算趋势
│
└── 05-report/                    ← 报告生成
    ├── SKILL.md
    └── scripts/
        └── generate_report.py    ← 生成 Markdown 报告
```

---

## 3. 数据模型（CSV Schema）

### 3.1 brand.csv（品牌档案）

一次填写，全局读取。所有模块都从这里获取品牌基础信息。
当前实现使用键值对模式（`field,value`），不是宽表多列模式。

| 字段 | 说明 | 示例 |
|------|------|------|
| brand_name | 品牌/产品名称 | Accio |
| industry | 所属行业 | AI 办公助手 |
| product_description | 产品描述（1-3句） | 一个能帮你完成日常工作的 AI 助手 |
| target_customer | 目标客户（ICP） | 中小企业主、独立开发者 |
| core_value_prop | 核心价值主张 | 无需开发即可完成复杂工作流 |
| website_url | 官网地址 | https://example.com |
| competitors | 主要竞品（逗号分隔） | Notion AI, Copilot, Gemini |
| geo_target_platforms | 监控的 AI 平台 | ChatGPT,Perplexity,Gemini |
| language | 内容语言 | zh 或 en |

---

### 3.2 keywords.csv（GEO 关键词库）

由模块1生成，模块2/3/4消费。

| 字段 | 说明 | 示例 |
|------|------|------|
| id | 唯一标识 | kw_001 |
| keyword | 关键词文本 | AI 办公助手哪个好 |
| intent_type | 意图类型 | awareness / consideration / decision |
| platform_affinity | 哪个平台更易触发 | chatgpt / perplexity / all |
| priority_score | 优先级分（1-10） | 8 |
| content_format | 推荐内容格式 | faq / comparison / definition / howto |
| poi_semantic | PoI 语义得分（1-5） | 4 |
| poi_authority | PoI 权威得分（1-5） | 3 |
| poi_entity | PoI 实体得分（1-5） | 2 |
| poi_evidence | PoI 证据得分（1-5） | 3 |
| poi_corroboration | PoI 印证得分（1-5） | 2 |
| poi_recency | PoI 时效得分（1-5） | 4 |
| poi_structure | PoI 结构得分（1-5） | 3 |
| status | 状态 | pending / content_created / published |
| created_at | 创建时间 | 2026-04-08 |

---

### 3.3 content.csv（内容记录索引）

由模块3生成，是内容文件的索引（实际内容存为 .md 文件）。

| 字段 | 说明 |
|------|------|
| id | 唯一标识 |
| keyword_id | 对应关键词 ID |
| keyword | 目标关键词 |
| content_format | 内容格式 |
| title | 文章标题 |
| file_path | Markdown 文件路径 |
| word_count | 字数 |
| poi_score | PoI 综合得分 |
| schema_included | 是否包含 Schema |
| published_url | 发布后的 URL |
| published_at | 发布时间 |
| created_at | 创建时间 |
| status | draft / published / needs_update |

---

### 3.4 monitor_log.csv（监控原始日志）

由模块4写入，每次监控产生一条或多条记录。

| 字段 | 说明 |
|------|------|
| id | 唯一标识 |
| run_date | 监控日期 |
| platform | 平台（chatgpt / perplexity / gemini） |
| prompt_used | 实际发送的 prompt |
| keyword_id | 对应关键词 |
| brand_mentioned | 品牌是否被提及（true/false） |
| brand_position | 品牌在答案中的位置（first/middle/last/none） |
| cited_url | 被引用的 URL（如有） |
| competitor_mentioned | 提到了哪些竞品（逗号分隔） |
| sentiment | 情感倾向（positive/neutral/negative） |
| raw_response_snippet | 响应片段（前300字）|
| notes | 备注 |

---

## 4. 五大模块详细需求

---

### 模块 1：Intent Engine（意图 & 关键词生成）

**触发方式（示例说法）：**
- "帮我生成 GEO 关键词"
- "我想做 GEO，先分析一下我的品牌该瞄准哪些词"
- "基于 brand.csv 里的信息，帮我规划关键词矩阵"

**Claude 的执行流程：**

1. 读取 `data/brand.csv` 获取品牌信息
2. 按以下逻辑生成关键词：
   - **Awareness 层**（用户还不知道解决方案）：「[行业问题] 怎么解决」「[痛点] 有什么方法」
   - **Consideration 层**（用户在比较方案）：「[品类] 哪个好」「[品类] 推荐」「[品类] 对比」
   - **Decision 层**（用户准备选择）：「[品牌名] 怎么样」「[品牌名] 和 [竞品] 哪个更好」
   - **Definition 层**（概念解释型）：「什么是 [品类]」「[品类] 的定义」
3. 为每个关键词评估 PoI 7 个信号的当前状态（基于品牌已有信息推断）
4. 调用 `scripts/save_keywords.py` 将结果追加写入 `data/keywords.csv`
5. 在对话中用表格展示关键词矩阵，并给出优先级建议

**输出：**
- 20-40 个关键词写入 `keywords.csv`
- 对话中展示关键词矩阵（按优先级排序）
- 给出「从哪3个关键词开始做内容」的建议

**不做的事：**
- 不实时调用 AI 平台验证（那是模块2的事）
- 不生成内容（那是模块3的事）

---

### 模块 2：Compete Engine（竞争分析）

**触发方式（示例说法）：**
- "分析一下我们在 ChatGPT 上的竞争情况"
- "看看「AI 办公助手哪个好」这个问题，各 AI 平台现在引用了谁"
- "做竞品引用分析"

**Claude 的执行流程：**

1. 读取 `data/keywords.csv`，取 priority_score 最高的 5-10 个关键词（或用户指定的词）
2. 调用 `scripts/query_ai_platform.py`，对每个关键词向目标平台发送查询
   - 查询方式：通过 Playwright 驱动浏览器，向 ChatGPT / Perplexity Web 发送 prompt
   - 每个关键词发送 3 次（降低随机性影响）
3. Claude 分析返回结果：
   - 哪些竞品被引用、被引用几次
   - 引用了哪些 URL 格式（博客/文档/论坛/Wiki）
   - 答案结构是什么（列表/段落/FAQ）
   - 哪个「意图位置」是空白的（没有品牌占领）
4. 将分析结果写入 `data/competitors.csv`
5. 给出「内容机会列表」：哪些词最容易切入、应该用什么格式

**输出：**
- competitors.csv 更新
- 对话中展示竞争态势：Share of Voice 表格 + 可进攻空白
- 内容机会排序：「建议先做这3篇内容」

**依赖：**
- 本机需安装 Python + Playwright
- 需要登录态（Playwright 复用本地浏览器 profile）

**不做的事：**
- 不做 SEMrush 级别的搜索量数据（GEO 不以搜索量为核心指标）
- 不自动登录账号（用现有登录态）

---

### 模块 3：Content Engine（内容生成工厂）

**触发方式（示例说法）：**
- "针对「AI 办公助手哪个好」写一篇 GEO 优化内容"
- "帮我写一篇 FAQ 格式的 GEO 文章，关键词是 XXX"
- "给 kw_003 这个关键词生成内容"

**Claude 的执行流程：**

1. 读取目标关键词信息（从 `keywords.csv` 或用户直接指定）
2. 读取对应格式的模板（`templates/` 目录下）
3. 生成内容，严格遵守 chunk 优化原则：
   - 每个内容块约 300 token
   - 结构：H2 标题 → 直接回答句（2句内）→ 证据/数据 → 实体关联
   - 每块至少嵌入 1 个数据点或权威来源引用
4. 调用 `scripts/generate_schema.py` 生成配套 JSON-LD Schema
5. 生成 llms.txt 片段（该内容的机器可读摘要）
6. 调用 `scripts/save_content.py`：
   - 将完整内容保存为 `output/YYYY-MM-DD_[关键词slug].md`
   - 更新 `data/content.csv`
7. 对话中展示内容预览 + PoI 得分诊断

**Markdown 文件格式（output/ 目录）：**

```markdown
---
title: 文章标题
keyword: 目标关键词
keyword_id: kw_001
content_format: faq
poi_score: 3.8
created_at: 2026-04-08
status: draft
---

# 文章标题

<!-- CHUNK_START: chunk_01 -->
## [子标题]
[直接回答，2句话以内]
[支撑证据/数据]
<!-- CHUNK_END: chunk_01 -->

<!-- SCHEMA_START -->
<script type="application/ld+json">
{ ... JSON-LD ... }
</script>
<!-- SCHEMA_END -->

<!-- LLMS_TXT_START -->
[机器可读摘要，200字以内]
<!-- LLMS_TXT_END -->
```

**输出：**
- 一个完整的 .md 文件（含正文 + Schema + llms.txt 片段）
- content.csv 新增一行记录
- PoI 各信号得分诊断（哪里还可以加强）

**不做的事（MVP）：**
- 不自动发布（需要用户手动复制内容到目标平台）
- 不做图片/视频内容

---

### 模块 4：Monitor Engine（AI 平台引用监控）

**触发方式（示例说法）：**
- "运行今天的监控"
- "监控一下我们在 Perplexity 上的表现"
- "跑一次全量监控"

**Claude 的执行流程：**

1. 读取 `data/keywords.csv`（取所有 status != 'pending' 的词，即已有内容的词）
2. 读取 `data/brand.csv` 获取品牌名和监控平台配置
3. 调用 `scripts/monitor.py`：
   - 对每个关键词 × 每个平台，发送查询
   - 解析响应，判断品牌是否被提及
   - 记录：提及位置、引用 URL、竞品提及情况、情感倾向
   - 将每条结果 append 到 `monitor_log.csv`
4. 调用 `scripts/analyze_trend.py` 计算本次vs上次变化
5. Claude 汇总并在对话中呈现：
   - 本次总体引用率
   - 哪些词有改善/退步
   - 竞品变化情况
   - 建议下一步行动（哪篇内容需要更新）

**监控逻辑（monitor.py 核心行为）：**
- 用 Playwright 打开对应平台网页
- 发送 prompt（从关键词派生，模拟真实用户提问）
- 等待响应完成，截取文本
- 用字符串匹配判断品牌提及
- 用正则提取 URL 引用（如有）
- 写入 CSV

**输出：**
- monitor_log.csv 新增 N 行（N = 关键词数 × 平台数）
- 对话中展示本次监控摘要报告

**运行频率：**
- 手动触发（对 Claude 说「运行监控」）
- MVP 阶段不做自动定时，后续可配 cron

**当前脚本支持的平台（以代码为准）：**
- doubao
- deepseek
- chatgpt
- perplexity

---

### 模块 5：Report Engine（报告生成）

**触发方式（示例说法）：**
- "给我生成本周的 GEO 监控报告"
- "出一份过去 30 天的引用趋势报告"
- "现在的整体 GEO 状态怎么样"

**Claude 的执行流程：**

1. 读取 `monitor_log.csv`（按时间筛选）
2. 读取 `content.csv` & `keywords.csv`（关联内容覆盖情况）
3. 调用 `scripts/generate_report.py` 生成 Markdown 报告
4. 在对话中直接呈现报告摘要

**报告结构：**

```markdown
# GEO 周报 · 2026-04-08

## 本周概览
- 监控关键词数：XX 个
- 覆盖平台数：XX 个
- 总体引用率：XX%（上周 XX%，变化 +/-XX%）

## 引用率趋势（表格）
| 关键词 | ChatGPT | Perplexity | 上周均值 | 本周均值 | 变化 |
| ...    | ...     | ...        | ...      | ...      | ...  |

## 本周亮点
- [品牌名] 在「XXX」这个问题上首次被 Perplexity 引用

## 竞品动态
- [竞品A] 在「XXX」的引用从 2 次升至 5 次，需关注

## 内容缺口
- 以下关键词尚无内容，建议本周创作：
  - kw_005: 「XXX」（priority_score: 9）

## 建议行动
1. 更新 [内容标题]，补充近期数据（Recency 信号偏弱）
2. 为 kw_007 创建 FAQ 格式内容（Perplexity 偏好此格式）
3. 在 Reddit 的 [相关板块] 发布摘要（Corroboration 信号）
```

---

## 5. 各模块的 Skill 触发关键词

下表说明 Claude 在什么情况下应该调用对应 Skill：

| 用户说了什么 | 调用哪个 Skill |
|-------------|--------------|
| 生成关键词 / 分析意图 / 规划 GEO 词库 | 01-intent |
| 竞争分析 / 看竞品 / 谁被引用了 | 02-compete |
| 写内容 / 生成文章 / 内容生成 | 03-content |
| 运行监控 / 监控结果 / 今天被引用了吗 | 04-monitor |
| 报告 / 周报 / GEO 状态 / 数据汇总 | 05-report |

---

## 6. Python 脚本清单 & 职责

| 脚本 | 所在模块 | 职责 | 输入 | 输出 |
|------|---------|------|------|------|
| `save_keywords.py` | 01-intent | 将关键词列表写入 CSV | JSON（关键词列表） | keywords.csv（追加） |
| `query_ai_platform.py` | 02-compete | 向 AI 平台发查询，返回响应文本 | 关键词、平台名 | 响应文本（stdout） |
| `save_competitors.py` | 02-compete | 将竞品分析结果写入 CSV | JSON（竞品数据） | competitors.csv（追加） |
| `generate_schema.py` | 03-content | 根据内容格式生成 JSON-LD | 内容类型、标题、FAQ列表等 | JSON-LD 字符串（stdout） |
| `save_content.py` | 03-content | 保存 .md 文件 & 更新内容索引 | Markdown 文本、元数据 | output/xxx.md + content.csv |
| `monitor.py` | 04-monitor | 主监控脚本 | 无（读 CSV 配置） | monitor_log.csv（追加） |
| `analyze_trend.py` | 04-monitor | 计算引用率趋势 | 时间范围 | JSON（趋势数据） |
| `generate_report.py` | 05-report | 生成 Markdown 报告 | 时间范围 | report_YYYY-MM-DD.md |

---

## 7. 依赖 & 环境要求

| 依赖 | 用途 | 安装方式 |
|------|------|---------|
| Python 3.10+ | 运行所有脚本 | 系统自带或 brew/apt |
| playwright | AI 平台监控（浏览器自动化） | `pip install playwright` + `playwright install chromium` |
| pandas | CSV 读写 | `pip install pandas` |
| openai | 调用 OpenAI API（辅助分析）| `pip install openai` |

**环境变量（存 .env 文件）：**
```
OPENAI_API_KEY=sk-...
```

**无需安装的东西：**
- 任何数据库
- 任何 Web 框架
- Docker

---

## 8. 待确认事项（请你判断）

以下是我需要你明确的几个决策点，每项都有两个选项：

### Q1：关键词生成要不要实时查询 AI 平台？

- **选项 A（轻量）：** 只用 Claude 基于品牌信息推理生成关键词，不实时查询。快，但不知道 AI 平台实际上在回答什么。
- **选项 B（重量）：** 关键词生成阶段就去查一遍 AI 平台，看看「真实用户在问什么」。慢 10 倍，但更准。

> 建议：**MVP 选 A**，模块2再做真实查询。你同意吗？

---

### Q2：监控用 Playwright 操控浏览器，还是用官方 API？

- **选项 A（Playwright）：** 模拟浏览器操作，和真实用户体验一致，但有被反爬风险，且需要保持登录态。
- **选项 B（API）：** ChatGPT 有 API 但不包含 Web Search 行为，Perplexity 有 API 但响应和 Web 端有差异。两者都不完全等同于用户实际看到的答案。

> 建议：**Playwright**，因为我们监控的是「真实用户会看到什么」，而不是「模型本身知道什么」。你同意吗？

---

### Q3：内容存 Markdown 还是 Word/HTML？

- **选项 A（Markdown）：** 纯文本，Claude 直接生成，方便读取和修改，但发布到网站需要转换。
- **选项 B（HTML）：** 直接可用于网站，Schema 天然嵌入，但 Claude 修改 HTML 不如 Markdown 自然。

> 建议：**Markdown + 附带 Schema 片段**，发布时手动处理转换。你同意吗？

---

### Q4：品牌信息怎么录入？

- **选项 A（对话录入）：** Claude 提问，你回答，Claude 自动写入 brand.csv。对话体验好，但需要先跑一次引导流程。
- **选项 B（直接编辑 CSV）：** 用你习惯的编辑器直接改 brand.csv，简单直接。

> 建议：**两者都支持**——你想快就直接改 CSV，你想被引导就对 Claude 说「帮我填写品牌档案」。你同意吗？

---

### Q5：MVP 阶段监控哪些 AI 平台？

- **最小集合（建议）：** ChatGPT + Perplexity（覆盖最主流，技术相对简单）
- **扩展集合：** + Gemini + Google AI Overviews（更完整，但 Google 反爬严格）

> 建议：**先做 ChatGPT + Perplexity**，跑通闭环后再加。你同意吗？

---

## 9. 不在本期范围内的功能

以下功能明确排除在当前模板实现之外，留待后续：

| 功能 | 原因 |
|------|------|
| 自动发布到网站/CMS | 当前仓库默认手动发布 |
| 定时自动监控（cron） | 当前仓库默认手动触发 |
| 多品牌 / 多用户 | 先自用，单品牌 |
| Web UI 看板 | 本期全部在 Claude 对话 + Markdown 报告里看 |
| 竞品内容抓取（爬竞品网站）| 法律风险，不做 |
| 邮件/Slack 通知 | 先在对话里看 |
| Gemini / Copilot 监控 | 反爬风险，留 v2 |

---

## 10. 验收标准（Definition of Done）

当以下 5 件事全部能跑通，视为 v1 完成：

1. **[ ]** 对 Claude 说「帮我初始化 GEO 系统，我的产品是 XXX」，能完成品牌档案录入 & 生成初始关键词矩阵，写入 CSV
2. **[ ]** 对 Claude 说「针对关键词 XXX 生成内容」，能生成一篇带 Schema 的 Markdown 文件，存入 output/ 目录
3. **[ ]** 对 Claude 说「运行监控」，`monitor.py` 能打开 ChatGPT 和 Perplexity，发送查询，把结果写入 monitor_log.csv
4. **[ ]** 对 Claude 说「生成本周报告」，能读取 monitor_log.csv 并输出一份 Markdown 格式的周报
5. **[ ]** 以上 4 步能串联执行：初始化 → 生成内容 → 监控 → 看报告，中间不需要手动处理文件

---

*本文件版本 v0.1，等待确认后开始开发。*
