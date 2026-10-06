---
name: geo-website-renderer
description: 将已确认的母内容或 GEO Content Brief 渲染为人和 AI 都容易理解的官网文章、产品页、比较页、定义页、案例页或 FAQ 页面，并按实际内容选择 Schema 与 llms.txt。用户要求写官网 GEO 内容、生成 AI 友好的网站版本、把三平台内容沉淀到官网时使用；不用于直接生成视频号、抖音或小红书发布文案。
---

# GEO Website Renderer

## 目的

把已确认的观点和证据变成网站内容。优化可理解、可抓取和可引用的准备度，但不牺牲人的阅读体验，也不承诺 AI 平台一定采用。

## 开始前

1. 完整读取：
   - `capabilities/geo/methods/evidence-and-entity-policy.md`
   - `capabilities/geo/methods/citability-and-content-policy.md`
2. 读取 `geo-content-brief` 或 `CanonicalContent`。核心声明未核实时，停止渲染并返回阻断项。
3. 如需外部补证，优先使用 `ego-browser`（跑不通时退回 `web-access`），先核验再写入。

## 渲染规则

品牌内容读取 `capabilities/geo/methods/positioning-and-audience.md` 和 brief 关联的定位版本。围绕本篇读者和场景展开，以证据说明优势；保持语义一致，不机械重复定位长句。生成后在定位卡 applications 中登记实际成稿路径及语义复核，运行定位校验器；新增价格、用户特征或效果承诺必须先进入事实包。

- 标题准确表达页面任务，不用“最新”“最好”等无法持续证明的词。
- 开头尽快给出主问题的直接答案。
- 每个章节回答一个子问题；长度由问题决定，不按固定 token 或字数切块。
- 事实与来源对应，经验注明主体，观点给出理由，预测说明假设。
- 保持实体名称和品牌关系一致。
- 包含必要条件、反例、限制和更新时间。
- 避免 AI 套话、关键词堆砌和重复改写同一句话。

## 可选机器结构

按实际页面选择，而不是全部生成：

- 正文确有问答区时才生成 `FAQPage`；
- 正文确有可执行步骤且满足规范时才生成 `HowTo`；
- Article、Organization、Product 等与页面实体一致；
- Schema 必须与用户可见正文一致；
- `llms.txt` 片段仅在项目确有该入口时生成。

项目内没有 Schema 生成器。Schema 按页面实际内容手写，并与可见正文逐项对齐；对不上就省略，不输出与正文不符的结构。

## 输出

- 完整网站正文；
- 来源与核验日期；
- 生成或明确省略的 Schema/llms.txt 及原因；
- 实体一致性说明；
- 未解决风险；
- 建议交给 `geo-prepublish-core` 的文件路径。

用户要求落盘时，沿用项目内容命名约定写入 `content/`。保存不等于发布。
