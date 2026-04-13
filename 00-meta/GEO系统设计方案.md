# GEO 全链路系统设计方案

> 作者：基于 Mike King（iPullRank）Relevance Engineering 框架 + Jack Boutchard（Exalt Growth）EGOS 方法论综合设计
> 日期：2026-04-08

---

## 一、可行性判断

### 1.1 市场现实：GEO 正在爆发

- Google 搜索点击率同比下降 **30%**，AI 搜索流量占转介流量已达 **10%** 并快速增长
- Google AI Overviews 覆盖 90% 的医疗/教育类查询、70% 的 B2B 技术查询
- ChatGPT、Perplexity、Gemini、Claude、Copilot 五大平台月活合计超 10 亿

### 1.2 现有产品的能力边界（竞品扫描）

| 产品 | 监控 | 关键词生成 | 内容生成 | 自动发布 | 竞争分析 | 迭代优化 |
|------|------|-----------|---------|---------|---------|---------|
| Otterly | ✅ | ❌ | ❌ | ❌ | 部分 | ❌ |
| Profound | ✅ | 部分 | ❌ | ❌ | ✅ | ❌ |
| Evertune | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ |
| AirOps | 部分 | ❌ | ✅ | ❌ | ❌ | ❌ |
| Quattr | ✅ | 部分 | 部分 | ❌ | 部分 | 部分 |
| WorkfxAI | 部分 | ❌ | ✅ | ✅ | ❌ | ❌ |

**结论：没有任何一款产品打通了「关键词生成 → 竞争分析 → 内容生成 → 自动发布 → 监控 → 迭代」完整链路。这是真实的市场空白。**

### 1.3 技术可行性：完全成立

| 模块 | 技术路径 | 成熟度 |
|------|---------|--------|
| GEO 关键词生成 | LLM prompt 模拟 + semantic clustering | 成熟 |
| AI 平台监控 | ChatGPT/Perplexity/Gemini API 轮询 | 成熟 |
| 内容生成 | LLM + RAG + chunk 优化 | 成熟 |
| 自动发布 | CMS API / Headless CMS / RSS | 成熟 |
| 竞争分析 | Citation tracking + entity mapping | 成熟 |
| 迭代优化 | A/B testing + signal feedback loop | 成熟 |

---

## 二、最适合构建这套系统的人

### 首选：Mike King（iPullRank）

**为什么是他？**

Mike King 是目前世界上将 **AI 检索机制理解最深** 同时具备 **工程化落地能力** 的 GEO 思想者。他创造了"Relevance Engineering（相关性工程）"这一概念，其核心主张：

> GEO 不是内容游戏，是 **信息检索工程**（Information Retrieval Engineering）。你要理解 AI 如何 chunk、embed、rank、cite，然后从系统层面去影响这个过程。

他构建了完整的 AI Search Manual（24 章），涵盖从 query fan-out 到 vector embeddings 到 measurement chasm 的全链路技术知识。

### 次选参考：Jack Boutchard（Exalt Growth）

提供了最完整的**作战系统（EGOS）**，特别是他的「Proof of Importance」框架，精确定义了 LLM 决定引用内容的 7 个信号，是系统设计的核心驱动力。

---

## 三、核心理论框架（驱动整个系统的底层逻辑）

### 3.1 Mike King 的 Relevance Engineering 模型

AI 检索系统工作原理（三层漏斗）：

```
用户 Query
    ↓ Query Fan-Out（AI 将查询展开为多个子意图）
文档 Retrieval（向量检索，256-512 token chunk 粒度）
    ↓ Reranking（语义相关性 + 权威性过滤）
Answer Generation（LLM 合成回答并选择引用源）
```

**对系统建设的启示：内容必须在 chunk 层面竞争，而非页面层面。**

### 3.2 Jack Boutchard 的 Proof of Importance (PoI) 框架

LLM 决定引用某内容的 7 个信号：

1. **Semantic Relevance** — 内容语义与 query 的对齐度
2. **Source Authority** — 域名权威性（E-E-A-T 信号）
3. **Entity Relationships** — 与知识图谱中实体的关联程度
4. **Evidence Density** — 数据、引用、可验证事实的密度
5. **Corroboration** — 同一事实在多个独立来源中的出现频率
6. **Recency** — 内容的时效性
7. **Structural Accessibility** — 内容被 AI 解析、切分、提取的容易程度

**这 7 个信号就是系统的优化目标，每一步生成和迭代都围绕它们展开。**

---

## 四、全链路系统架构（Full Stack GEO Engine）

### 系统总览

```
┌─────────────────────────────────────────────────────────┐
│                   GEO Engine Platform                    │
├──────────┬──────────┬──────────┬──────────┬─────────────┤
│  Module1 │ Module2  │ Module3  │ Module4  │  Module5    │
│  Intent  │ Compete  │ Content  │ Publish  │  Monitor    │
│  Engine  │ Engine   │ Engine   │ Engine   │  Engine     │
│  关键词   │ 竞争分析  │ 内容工厂  │ 发布引擎  │  监控中心   │
└──────────┴──────────┴──────────┴──────────┴─────────────┘
                            ↑↓
              ┌─────────────────────────┐
              │  Optimization Loop       │
              │  迭代优化 + 反馈系统      │
              └─────────────────────────┘
```

---

### Module 1：Intent Engine（意图 & 关键词生成）

**输入：** 用户提供的业务字段（产品名、行业、ICP、核心价值主张、竞品）

**处理流程：**

```
1. Entity Mapping
   - 将品牌解析为实体（Who you are, What you do, Who you serve）
   - 构建语义关系图谱

2. Query Fan-Out 模拟
   - 模拟 AI 引擎如何展开用户真实 Query
   - 生成 3 类查询：Awareness / Consideration / Decision

3. Prompt Mining
   - 调用 ChatGPT、Perplexity、Gemini API
   - 询问「[品类] 的最佳解决方案是什么？」等真实用户 prompt
   - 抓取 AI 实际响应中的引用模式

4. GEO Keyword Clustering
   - 按意图层级分组（问题型/比较型/品牌型/定义型）
   - 按 AI 平台差异化分组（ChatGPT 偏好 vs Perplexity 偏好）
   - 输出优先级打分（搜索频率 × 竞争难度 × 商业价值）
```

**输出：** GEO 关键词矩阵（含意图标签、平台标签、优先级分）

---

### Module 2：Compete Engine（竞争分析）

**处理流程：**

```
1. Citation Audit
   - 批量向各 AI 平台发送目标关键词 prompt
   - 记录当前被引用的品牌/内容/URL
   - 计算 Share of Voice（AI 平台上的品牌占比）

2. Gap Analysis
   - 分析竞品被引用的内容特征
   - 识别哪类 chunk 格式被高频引用（FAQ/对比表/数据列表/定义）
   - 找出当前尚未被任何品牌占领的答案空白

3. Entity Authority Map
   - 分析竞品在知识图谱中的实体关联强度
   - 评估 PoI 7 信号中我方 vs 竞品的得分对比

4. Volatility Tracking
   - AI 引用源变化极快（研究显示每月近 50% 的引用域名会更换）
   - 持续记录引用波动，捕捉进攻窗口
```

**输出：** 竞争态势看板 + 可进攻的内容机会列表

---

### Module 3：Content Engine（内容工厂）

**这是最核心的模块，基于 Mike King 的 chunk-level 优化 + PoI 框架**

**处理流程：**

```
1. Content Blueprint 生成
   - 根据目标关键词确定内容类型
     * Definition Pages（"什么是X"类）
     * Comparison Pages（"X vs Y"类）
     * How-to Pages（"如何做X"类）
     * Data/Stats Pages（统计证据页）
     * FAQ Clusters（问答簇）

2. Block Factory（内容块工厂）
   - 每个内容块控制在 256-512 token（LLM chunk 最优粒度）
   - 每块包含：核心答案句 + 证据支撑 + 实体锚定
   - 结构：H2 → 直接回答（2句）→ 证据/数据 → 实体关联

3. PoI 信号注入
   - Semantic Relevance：确保语义精确对齐 query
   - Evidence Density：每块至少包含1个数据点或引用
   - Structural Accessibility：使用 FAQ schema、HowTo schema
   - Corroboration：引用第三方权威来源（Wikipedia、研究报告）

4. Schema 生成
   - 自动生成 JSON-LD 结构化数据
   - FAQ schema / Article schema / Organization schema
   - Entity markup（与知识图谱锚定）

5. LLMs.txt 生成
   - 为 AI 爬虫提供机器可读的品牌权威信息页
   - 参考 Exalt Growth 的 llms-info 模式
```

**输出：** 完整的内容资产包（正文 + Schema + Meta + llms.txt 片段）

---

### Module 4：Publish Engine（发布引擎）

**处理流程：**

```
1. 平台适配器
   - WordPress / Webflow / Ghost → REST API
   - Notion / Contentful → Headless CMS API
   - Medium / Substack → 开放 API
   - Reddit / Quora → 社区发布（Corroboration 信号）
   - LinkedIn / Twitter → 社交验证（权威信号）

2. 发布策略执行
   - 根据竞争分析结果确定发布优先级
   - 按平台差异化分发（不同平台侧重不同 chunk）
   - 控制发布节奏（避免 AI Slop 被降权）

3. 索引加速
   - 提交 IndexNow（Bing 快速收录）
   - Sitemap 实时更新
   - 通知 AI 爬虫（Perplexity bot、GPTBot 等）

4. 发布记录
   - 记录每次发布的 URL、时间、目标关键词
   - 作为后续监控的 baseline
```

**输出：** 发布成功确认 + 发布记录（供监控模块使用）

---

### Module 5：Monitor Engine（监控中心）

**处理流程：**

```
1. AI 平台轮询
   目标平台：
   - ChatGPT（GPT-4o Browse）
   - Perplexity AI
   - Google AI Overviews
   - Google AI Mode
   - Gemini
   - Microsoft Copilot
   - Claude（Artifacts + Web）

   监控维度：
   - 品牌被提及次数（Mention Frequency）
   - 被引用 URL（Citation URLs）
   - 答案中的品牌情感（Sentiment）
   - 品牌在答案中的位置（Position in Response）
   - Share of Voice（相对于竞品）

2. 异常检测
   - 突然丢失引用：触发内容审查告警
   - 竞品突然获得引用：触发竞争分析任务
   - 新兴 prompt 模式出现：触发内容机会告警

3. 指标看板
   - AI Citation Rate（每100个相关 prompt 中被引用次数）
   - Platform Coverage（覆盖了几个 AI 平台）
   - Entity Recognition Score（AI 是否正确识别品牌实体）
   - Response Position Index（答案中品牌出现的位置）
```

**输出：** 实时监控看板 + 周报 / 月报

---

### Optimization Loop（迭代优化引擎）

**这是整个系统的飞轮，将监控结果反馈到内容和策略层：**

```
监控数据 → 信号分析 → 优化建议 → 内容更新 → 重新发布 → 继续监控

具体规则：
- Citation Rate < 基准：检查 PoI 7 信号哪个得分低，针对性补强
- 某 AI 平台表现差：分析该平台的引用偏好差异，调整 chunk 格式
- 竞品引用上升：分析竞品最新发布内容，补充差异化证据
- 新热点 query 出现：自动生成新内容块并发布
- 内容时效性下降：触发 Recency 信号，更新数据和日期
```

---

## 五、技术栈推荐

### 后端
```
语言：Python（AI/NLP 生态最成熟）
框架：FastAPI（高性能 API）
任务队列：Celery + Redis（异步监控任务）
数据库：
  - PostgreSQL（结构化数据：用户、内容、发布记录）
  - Pinecone / Weaviate（向量数据库：语义检索）
  - ClickHouse（监控时序数据）
```

### AI 层
```
LLM：OpenAI API（GPT-4o）+ Anthropic API（Claude）
Embedding：text-embedding-3-large
框架：LangChain / LlamaIndex（RAG 管道）
Schema 生成：自定义模板 + JSON-LD
```

### 前端
```
框架：Next.js 14（App Router）
UI：Shadcn/UI + Tailwind
图表：Recharts / Observable Plot
```

### 监控基础设施
```
AI 平台查询：Playwright（浏览器自动化）+ 官方 API
调度：APScheduler / Celery Beat
告警：Webhook → Slack / 邮件
```

### 发布集成
```
WordPress：REST API v2
Webflow：CMS API
Contentful：Content Management API
Ghost：Admin API
通用：Puppeteer（无 API 时的备选）
```

---

## 六、系统数据流

```
用户输入（品牌名/行业/竞品/价值主张）
         ↓
    [Intent Engine]
    Entity Graph + GEO Keyword Matrix
         ↓
    [Compete Engine]
    Citation Audit + Gap Map + SoV
         ↓
    [Content Engine]
    Content Blocks (chunk-optimized) + Schema + llms.txt
         ↓
    [Publish Engine]
    多平台发布 → URL 记录
         ↓
    [Monitor Engine]
    AI 平台轮询 → 引用率 / 情感 / 位置
         ↓
    [Optimization Loop]
    信号分析 → 优化指令 → 回到 Content Engine
```

---

## 七、MVP 设计（4 周快速启动版）

### MVP 核心原则
> **砍掉自动化，保留智能化。** MVP 不追求全自动，而是帮用户「想得更清楚、写得更准确、测得更科学」。

### MVP 包含的 3 个核心功能

#### MVP-1：GEO 关键词 & 内容策略生成器（第 1-2 周）

**输入字段：**
- 品牌名 / 产品名
- 行业品类
- 目标客户（ICP）
- 3-5 个核心竞品
- 核心价值主张（1-2句）

**输出：**
1. 30-50 个 GEO 目标关键词（按意图分类）
2. 每个关键词的「内容优先级分」
3. 推荐内容格式（FAQ / 对比页 / 定义页 / 数据页）
4. PoI 7 信号的当前诊断（哪几个需要优先补强）

**技术实现：**
- GPT-4o prompt engineering（3-4 个精心设计的 system prompt）
- 简单的 Python 后端 + FastAPI
- 输出为结构化 JSON → 前端表格展示

---

#### MVP-2：GEO 内容生成器（第 2-3 周）

**输入：** 选择一个目标关键词 + 内容格式

**输出：**
1. 完整的 chunk-optimized 文章（每块 256-512 token）
2. FAQ Schema（JSON-LD）
3. Meta description（针对 AI 摘要优化）
4. llms.txt 条目片段
5. PoI 得分预估（生成后自动打分）

**技术实现：**
- 结构化 prompt template（基于 PoI 框架设计）
- Markdown 编辑器（前端直接可编辑）
- 一键复制 Schema 代码

---

#### MVP-3：AI 平台引用监控（第 3-4 周）

**输入：** 添加要监控的关键词 prompt + 品牌名

**输出：**
1. 每日自动查询 ChatGPT + Perplexity（先做这两个）
2. 品牌是否被提及 ✅/❌
3. 被引用的 URL
4. 竞品被提及情况
5. 周趋势图

**技术实现：**
- Playwright 自动化查询（成本最低）
- PostgreSQL 存储查询结果
- 简单 cron job（每天凌晨跑）
- 前端折线图展示趋势

---

### MVP 技术栈（最简化）

```
后端：Python + FastAPI + PostgreSQL
AI：OpenAI API（GPT-4o）
爬虫：Playwright（监控用）
前端：Next.js + Tailwind + Shadcn
部署：Railway / Render（快速上线）
定时任务：Railway Cron Jobs
```

### MVP 不做的事（留到 v2）
- 自动发布（太多平台适配工作，先手动）
- 复杂竞争分析（先给用户基础洞察）
- 多平台监控（先做 ChatGPT + Perplexity）
- 迭代优化引擎（先有数据再谈优化）

---

## 八、MVP 开发路线图

```
Week 1: 搭建基础架构
- FastAPI 后端 skeleton
- OpenAI API 集成
- 核心 prompt 设计（Intent Engine + Content Engine）
- Next.js 前端基础

Week 2: MVP-1 完成
- 关键词生成功能上线
- PoI 诊断功能
- 基础用户认证

Week 3: MVP-2 完成
- 内容生成功能上线
- Schema 自动生成
- 内容编辑器

Week 4: MVP-3 完成 + 首批用户
- Playwright 监控系统
- 监控看板
- 招募 10 个 beta 用户测试
```

---

## 九、差异化护城河

当产品形态跑通后，真正的壁垒来自：

1. **PoI 信号的专有评分模型** — 用真实的 AI 引用数据训练内部评分器，比 GPT 自评更准
2. **跨平台引用关联数据库** — 你的监控数据会沉淀出「哪类内容在哪个 AI 平台最容易被引用」的独家规律
3. **行业垂直化** — 每个行业的 GEO 规律不同，深耕 2-3 个垂直行业可建立品类领先
4. **内容的 Corroboration 网络** — 帮用户在多个第三方平台同步发布，形成 AI 更倾向引用的"共识效应"

---

## 十、参考资源

- **Mike King AI Search Manual**: [ipullrank.com/ai-search-manual](https://ipullrank.com/ai-search-manual)（最完整的 GEO 技术文档，共 24 章）
- **Jack Boutchard EGOS + PoI**: [exaltgrowth.com/llms-info](https://www.exaltgrowth.com/llms-info)（Proof of Importance 7 信号框架）
- **Profound 平台**: [tryprofound.com](https://www.tryprofound.com)（企业级 GEO 监控参考）
- **Otterly**: [otterly.ai](https://otterly.ai)（监控功能参考，6 个平台）
- **Evertune**: [evertune.ai](https://evertune.ai)（竞争分析参考，已融资 \$19M）
