# 系统架构与实施路线

**设计目标：** 后端允许复杂，用户交互保持为“说想法—选选题—看成品—授权发布”。  
**实现原则：** 延续本地优先、文件可审计、Python 做确定性工作、Skill 做专业推理；先打通一条真实闭环，再扩展自动化。

## 1. 目标架构

```text
Conversation Orchestrator
  ├─ Idea Interpreter
  ├─ Research Planner
  │    ├─ XHS Collector
  │    │    ├─ Spotlight Keyword Planner
  │    │    ├─ Creator Inspiration
  │    │    └─ Search / Notes / Comments
  │    ├─ Douyin Collector
  │    │    ├─ Douyin Index
  │    │    ├─ Creator Inspiration
  │    │    └─ Search / Videos / Comments
  │    └─ Channels Collector
  │         ├─ Channels Search / Topics / Comments
  │         ├─ Creator Analytics
  │         └─ WeChat Index (proxy)
  ├─ Evidence Normalizer
  ├─ GEO Measurement & Attribution
  │    ├─ Visibility baseline
  │    ├─ Direct / corroborated markers
  │    ├─ Incrementality experiments
  │    └─ Cost / value decision gates
  ├─ Topic Lab
  ├─ Canonical Content Studio
  │    ├─ dbs-standard-answer / benchmark
  │    ├─ content / spread / resonate
  │    └─ Strategy Registry
  ├─ Platform Renderers
│    ├─ Channels Package
│    ├─ Douyin Package
│    ├─ XHS Package
│    ├─ Owned Blog Package
│    └─ Named Media Package
  ├─ Production Briefs
│    ├─ Article Draft
│    ├─ Video Production Brief → External Video System
│    └─ Image Production Brief → Image System
  ├─ Asset Factory
  ├─ Rule & Risk Preflight
  └─ Publish Handoff
```

编排器只负责状态和路由，不把所有研究、创作和合规指令塞进一个巨型 Skill。

## 2. 核心实体

| 实体 | 作用 | 推荐存储 |
|---|---|---|
| `IdeaBrief` | 用户原话、暂定观点、受众、场景、约束 | Markdown + YAML front matter |
| `ResearchRun` | 本次研究范围、查询、假设、采样状态 | Markdown 索引 |
| `RawSample` | 平台原始作品、评论、话题、指标 | JSONL，追加写入 |
| `KeywordSignal` | 词、来源、平台内指标、意图 | CSV/Parquet；第一版 CSV |
| `EvidenceRecord` | 事实、来源、证据等级和适用范围 | CSV + 引用文件 |
| `TopicCandidate` | 用户问题、观点、承诺、证据、反例、平台适配 | Markdown |
| `CanonicalContent` | 平台无关的事实、论证、故事和素材计划 | Markdown |
| `ArticleDraft` | 可直接编辑和审阅的完整文章 | Markdown + manifest |
| `ProductionBrief` | 外部视频系统可执行的脚本、镜头、素材和验收契约 | JSON + Markdown |
| `ImageBrief` | 图片系统可执行的文案、构图、尺寸和素材契约 | JSON + Markdown |
| `StrategyRecord` | 可加载创作模式 | YAML |
| `PlatformPackage` | 每个平台的文本、镜头、封面、字幕、素材和字段 | 独立目录 + manifest.yaml |
| `PublishJob` | 账号、规则快照、检查结果和授权状态 | YAML + 审计日志 |
| `AttributionPlan` | 业务目标、标记、对照、观察窗口、成本口径与扩投决策 | JSON + 追加式观测记录 |

关系必须保留：`idea → research_run → evidence/keywords → topic → canonical → article/production_briefs → channel_packages → publish_job`。

## 3. 建议目录

遵守根 `AGENTS.md`，新结构先作为目标目录，不立即迁移现有编号模块：

```text
00-meta/content-engine/       设计、规则和证据台账
data/
  ideas/
  research/
    raw/
    normalized/
  topics/
  strategies/
  rules/
  publish-jobs/
content/
  canonical/
  articles/
  briefs/
  packages/
    channels/
    douyin/
    xhs/
    blog/
    media/
assets/
  source/
  generated/
  exports/
publish/
  drafts/
  receipts/
```

命名规则：`YYYYMMDD-{slug}-{id}`；渠道标识使用 `channels`、`douyin`、`xhs`、`blog`、`media-{outlet-slug}`；原始采集只追加，生成物可重建，发布凭证不可覆盖。

新闻网站必须绑定具体媒体名称和规则快照。没有目标媒体时只能形成候选媒体清单与通用新闻素材包，不能标记为可投稿。

## 4. 跨平台母稿

品牌创作在母稿前增加定位与场景选择：事实包 `positioning.json` → 本篇受众/场景/问题 → 证据 → 母稿 → 渠道变体 → 定位版本和正文语义复核。方法真源为 `capabilities/geo/methods/positioning-and-audience.md`。本地校验和 Skill 路由已实现；平台推荐效果与自动线上监测未实现。不同渠道可改变表达，不改变事实和适用边界。

母稿不是长文，而是不可漂移的内容真源：

```yaml
topic: ...
thesis: ...
audience_and_scene: ...
facts:
  - claim: ...
    evidence_ref: ...
stories:
  - source: user_experience | public_case | dramatization
    disclosure: ...
counterarguments: []
boundaries: []
desired_action: ...
available_assets: []
```

平台渲染器只能改变顺序、长度、语气、镜头和载体，不能悄悄改变核心事实。任何新增事实必须回写证据层。

## 5. 发布包契约

每个平台至少输出：

```text
manifest.yaml             平台、账号、主题、策略、规则快照、状态
copy.md                   标题、正文、话题、置顶评论建议
script.md                 口播与字幕真源
shot-list.md              镜头、画面、屏幕录制和 B-roll
cover.md / cover.*        封面文案与成品
captions.srt              字幕
assets/                   最终媒体文件
preflight.md              格式、事实、版权、AI 标识、风险检查
publish-checklist.md      发布时唯一需要执行的动作
```

## 6. 对话状态机

| 状态 | 系统行为 | 用户看到什么 |
|---|---|---|
| `idea_received` | 提取想法，形成最小研究简报 | 一句话理解 + 必要时一个问题 |
| `researching` | 自动调用三平台采集器和研究 Skill | 简短进度，不抛工具细节 |
| `topics_ready` | 聚类、找反例、形成 3—5 个选题 | 推荐选题、证据和风险 |
| `topic_selected` | 锁定观点、承诺与证据 | 一页内容方向确认 |
| `creating` | 生成母稿、策略和素材 | 可预览版本 |
| `packages_ready` | 三平台渲染、规则预检 | 三套发布包与差异 |
| `awaiting_publish` | 准备草稿或打开发布界面 | “只差发布”清单 |
| `published` | 用户授权后记录链接和时间 | 发布回执 |

任何时候用户都可以自然修改：“换受众”“保留观点，换形式”“只做小红书”“先不发布”。系统更新当前实体，不要求重跑全部流程。

## 7. 确定性与模型职责

### Python / 确定性层

- 写入、读取、去重、版本和状态迁移；
- 指标单位、时间窗、缺失值和平台来源校验；
- 图片尺寸、文件大小、视频时长、编码和字幕格式检查；
- 规则过期判断；
- 生成发布清单与审计日志；
- 防止未授权发布。

### 模型 / 推理层

- 从想法中提取暂定问题；
- 扩词、聚类用户语言、识别矛盾与反例；
- 选择 dbs 研究与创作 Skill；
- 生成选题、母稿和平台表达；
- 判断策略适配，但必须说明证据和边界。

### 浏览器 / 外部操作层

- 读取实时平台数据、规则和创作中心；
- 在隔离 task space 中复用登录态；
- 草稿填写后校验页面状态；
- 公共发布前等待明确授权。

## 8. 实施路线

### Phase 0：规则与设计基线

本轮完成：根 `AGENTS.md`、产品定义、调研设计、硬规则第一版、策略库第一版、证据台账和路线图。

### Phase 1：最小对话闭环

**实现状态：部分实现。** `content-orchestrator` 路由、GEO 完整/轻量模式和项目级 GEO Skills 已落地；三平台真实采样与 TopicCandidate 落盘尚未实现。

交付：

- `content-orchestrator` Skill；
- `IdeaBrief`、`ResearchRun`、`TopicCandidate` 数据契约；
- 允许用户一句话触发研究；
- 先用手动/半自动采样验证对话流程；
- 输出 3 个选题并支持继续对话修改。

验收：用户不需要说 Skill 名，不需要填表，不需要自己合并研究结果。

### Phase 2：三平台采集器

顺序：

1. 小红书：已有聚光 Skill 和登录态，先形成端到端参考实现；
2. 抖音：接入抖音指数、创作灵感、原生搜索和评论；
3. 视频号：接入原生搜索/评论与账号数据，微信指数只作代理信号。

交付：原始 JSONL、统一关键词信号、采样报告、来源缺失说明、可恢复任务状态。

### Phase 3：策略库与内容母稿

交付：

- 策略 YAML schema 与受约束随机选择器；
- dbs Skill 编排映射；
- 跨平台母稿；
- 事实、反例、用户经历和表达层分离；
- 选题确认后自动生成三平台内容蓝图。

### Phase 4：三平台物料生成与预检

交付：

- 三个平台 renderer；
- 图片、视频、字幕和封面生成；
- 当前规则快照与素材验证器；
- `PlatformPackage` 完整目录；
- 人类可读的一页发布前预览。

### Phase 5：发布交接

第一版目标不是“无人值守自动发”，而是：

- 自动打开正确账号的发布入口；
- 填好文本、上传素材、选择必要声明；
- 对页面最终状态截图/读回；
- 停在发布按钮前；
- 获得用户明确授权后再点击；
- 保存发布链接、时间、最终字段和回执。

## 9. 先不做的复杂度

- 不先上数据库、队列、Web 后台；
- 不先做全平台无人值守采集；
- 不把所有 Skill 复制进项目；
- 不把三平台适配写进一个超长 prompt；
- 不在反馈闭环前构造“AI 爆款评分”；
- 不在当前发布规则未知时承诺一键全自动发布。

## 10. 主要风险与缓解

| 风险 | 对用户的影响 | 缓解 |
|---|---|---|
| 登录、验证码、反爬和页面改版 | 研究或发稿中断 | 任务可恢复、运行时快照、必要时交还用户 |
| 指标口径不一致 | 错选题、虚假确定感 | 保存原始口径，只做平台内相对排名 |
| AI 编造事实或案例 | 信誉和合规风险 | 母稿事实引用、未核实即阻断 |
| 模板化内容 | 失去人格、平台降质 | 策略模式带边界，用户观点为必需输入 |
| 版权与肖像 | 下架或纠纷 | 素材来源台账与授权预检 |
| 规则变化 | 上传失败或违规 | 每次发布前核验当前 UI |
| 误触公开发布 | 不可逆外部影响 | 权限闸门与明确授权 |

## 11. 下一实施切片

最值得先做的不是发布器，而是一个可以真实使用的最小链路：

> 用户说一句想法 → 小红书/抖音/视频号各取一轮样本 → 返回 3 个有证据的选题 → 用户用自然语言修改并选中一个。

这一切片验证的是产品核心：AI 是否真的减少了思考和执行负担。只有这个环节顺滑，后面的脚本、图片和自动填表才值得投入。
