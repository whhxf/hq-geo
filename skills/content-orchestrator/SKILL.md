---
name: content-orchestrator
description: HQ Content Engine 的自然对话总入口。用户只要表达一个想法、要开一个新项目、希望调研选题、生成文章/视频/图片内容、投向视频号/抖音/小红书/博客/新闻媒体，或要求从想法一路准备到发布前，就应使用本 Skill 自动判断内容流程、完整 GEO 流程或混合流程；不要要求用户先选择或记住具体 Skill 名。
---

# Content Orchestrator

## 目的

让用户只讨论想法、选题和最终发布决定，系统承担 Skill 选择、研究、内容转换和状态管理。编排器不复制专业方法，只按项目真源路由。

## 开始前

完整读取：

- `00-meta/content-engine/README.md`
- `00-meta/content-engine/02-research-and-topic-system.md`
- `00-meta/content-engine/03-platform-hard-rules.md`
- `00-meta/content-engine/05-architecture-and-roadmap.md`
- `capabilities/geo/manifest.json`
- `capabilities/geo/contracts/geo-context.schema.json`

按任务阶段读取创作策略库和对应专业 Skill。不要一次加载所有 Skill 正文。

## 路由判断

### 从零开始（还没有项目）

用户说「我有个新项目」「帮我开一个新项目」「这个想法单独做一个项目」时，**不要直接开始创作**。
实例层必须先有一个项目根，否则产物无处可放，而且会落进系统根——那正是分根要去掉的东西。

1. **确认目录。** 用户给了就用；没给就按内容提议一个（`~/project/<slug>`，slug 用英文 kebab-case），让他改。
2. **跑脚手架。** 在系统根执行 `python3 capabilities/project-scaffold/scripts/init_project.py <目录>`。
   已存在的文件一律不动，只报告跳过，所以在非空目录里跑也安全。
3. **切换过去。** 让用户 `cd` 到新项目根，或本次会话所有命令显式带 `--project <目录>`。
   系统根不是项目根，在这里建任务、事实包或稿子会立刻让门禁变红。
4. **继续下面的路由。** 新项目的第一次门禁应该是 `PASS`——没有产物不是错误，产出基准会在第一次跑时自动建立。

### 从任务进入

用户说「看下 tasks 里的新任务」「推进这个任务」「把这个写成文章」时，先读 `tasks/<id>.md`，再按任务的 `deliverables` 字段路由：

| deliverables | 走哪条线 |
|---|---|
| `article` | `skills/article-pipeline/SKILL.md` |
| `video` | 视频流水线尚未建立，当前用 `ProductionBrief` 契约（`capabilities/content-production/contracts/`） |
| `image` | `skills/image-pipeline/SKILL.md` 五站（强依赖 AI 生成，不做图片编辑） |

视频线还没有命名流程，只有产物契约——生成交给外部的 Vidmix，hq-geo 只出 `CreativeJob`。
用户要视频交付时，说明当前状态，不要假装有完整流水线。

### 核心写作逻辑（先于渠道路由）

所有创作先明确受众、场景、问题和证据。涉及品牌/产品推广时完整读取 `capabilities/geo/methods/positioning-and-audience.md`，读取对应事实包 `positioning.json`；缺失则按 `capabilities/geo/contracts/positioning.schema.json` 形成草案。先复用已有定位，再为本篇选择人群与场景。纯社交也执行此写作逻辑，但不因此进入完整 GEO；普通知识文章不强制品牌卡。

生成前登记渠道 application；完成后阅读实际正文/脚本，记录 artifact_path、review.artifact_sha256 和语义复核，再运行 `python3 capabilities/geo/scripts/validate_positioning.py <定位卡路径> --require-ready`。只有 creation_ready=true 才能把品牌创作标为可交付；草案和缺口可以继续展示。历史作品在重新编辑或交付时补检。

### 完整 GEO

出现任一目标时设置 `geo_mode=full`：

- 用户明确说 GEO、AI 搜索、AI 引用或品牌在 AI 回答中的可见性；
- 目标产物是官网文章、产品页、比较页、定义页、FAQ 或品牌知识页；
- 要建设权威信源或监控 AI 平台回答。

根据阶段调用：`geo-research → geo-content-brief → geo-website-renderer → geo-prepublish-core`；可见度监控调用 `geo-monitor`；预算、线索、成交、增量或 ROI 问题调用 `geo-attribution`。后两者可以共享样本，但不得把可见度直接当成商业归因。

### 纯社交内容

目标只有视频号、抖音或小红书时设置 `geo_mode=lightweight`：

- 执行三平台调研、选题、母内容、平台渲染和平台规则预检；
- 只继承事实可验证、实体一致、观点可准确复述；
- 不加载 FAQ、Schema、llms.txt、关键词密度或 GEO 总分。

### 混合内容

用户同时要社交发布和官网沉淀时：

1. 共享同一个 `IdeaBrief`、证据层和 `CanonicalContent`；
2. 三个平台分别渲染；
3. 网站分支调用 `geo-content-brief → geo-website-renderer → geo-prepublish-core`；
4. 各分支不互相复制平台格式。

### 自有博客与媒体稿

- 自有博客属于 owned channel：生成完整文章、摘要、标题、引用、图片简报、SEO/GEO 元数据和站点发布包。
- 新闻网站属于 earned/syndicated channel：先确定具体媒体或栏目，再生成符合其受众、选题口径、署名、来源披露和投稿规则的媒体稿与 pitch；不得使用一个“新闻网站通用发布器”伪装覆盖所有媒体。
- 同一选题可共享母内容和事实引用，但博客原文、媒体稿和社交平台版本分别建包，不机械截短。

### 交易渠道（闲鱼）

目标是**把商品发布到闲鱼这类交易平台**时，走交易渠道，不加载完整 GEO，也不套内容平台的做法：

1. 先读 `capabilities/content-production/channels/xianyu.md`（渠道契约与规则状态），
   渠道分类见 `capabilities/content-production/channels/README.md`。
2. 产出**商品发布包**到 `content/packages/xianyu/<idea-id>/<topic-id>/`：`copy.md`
   （标题、真实卖点、适用对象、内容清单、文件格式、软件版本、交付方式与期限、售后范围）
   + 封面/内页 `ImageBrief` + 发布复核记录。
3. **类目准入、账号资质、图片规格等规则未核验前，发布包只能标 `prepared`，
   不得标 `ready_to_publish`**——未知项阻止发布就绪，不以猜测补齐。
4. 不虚构销量、评价、收益或版权授权；买家与订单只用匿名编号；不自动发布、不自动改价。

交易渠道与内容渠道的边界：内容渠道回答「怎么让人看到并相信」，交易渠道回答
「怎么把商品描述准确并促成交易」。**不把内容平台的做法套到商品页上。**

## 对话流程

1. 有任务文件时先读任务，从 `## 任务` 区块提取观点、受众、场景、目标平台和可用素材；没有任务文件时从用户原话提取。
2. 读取当前事实包的 `manifest.json`、`facts.jsonl` 与 `reviews/gate-report.json`。只有缺失信息会改变研究对象、内容承诺、合规或发布结果时追问一个最小问题；优先选择与当前选题直接相关、回答后能解除最多阻塞的问题。
3. 提问前把问题登记进事实包 `pending_questions`。用户回答后，调用 `python3 capabilities/fact-packs/scripts/capture_fact.py` 补录原回答、结构化事实与变更日志，再运行事实包校验；不得只把答案留在对话记忆或选题稿中。
4. 区分答案性质：企业内部事实、创始人观点与亲历经验可用 `owner_statement`；外部市场效果、客户评价、行业数据仍需独立来源。答案与保护事实冲突时登记冲突并暂停，不静默覆盖。
5. 自动选择研究路径。采集器尚未实现时，明确说明本轮使用手动/半自动研究，不伪装成已自动采集。
6. 第一屏返回最多 3—5 个可判断选题，说明证据、平台适配和风险。
7. 用户自然回复后更新同一个任务状态，不要求重来。
8. 锁定选题后生成平台无关母内容，再选择创作策略和渠道 renderer。
9. 根据目标载体生成实际交付物：文章走 `skills/article-pipeline/SKILL.md` 的八站流程；图片走 `skills/image-pipeline/SKILL.md` 的五站；视频生成交给外部制作系统的 `ProductionBrief`。不得停在选题或一句内容建议。
10. 为视频号、抖音、小红书、自有博客和已指定媒体分别生成渠道包；未知媒体规则会阻止媒体包进入发布就绪。
11. 发布前加载当前渠道硬规则、内容风险、版权和 AI 标识要求。
12. 可以准备草稿、上传和预览；公开发布、删除、修改已发布内容或产生广告费用前，必须获得明确授权。

## 进度反馈

只告诉用户当前发生了什么和下一次需要他做什么，例如：

- “正在核验三个平台里的真实问法”；
- “找到三个方向，其中一个跨平台共振最强”；
- “三套物料已准备，抖音上传规格仍需登录后确认”；
- “只差发布，等待你的授权”。

避免输出内部 Skill 调用日志和大段中间关键词。

## 完成标准

每个输出都能回溯到 `idea → research → evidence → topic → canonical → platform/website package`。未知规则和未核实核心声明会阻止 `ready_to_publish`，模型不得自行降低门槛。
