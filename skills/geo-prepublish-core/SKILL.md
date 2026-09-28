---
name: geo-prepublish-core
description: GEO 发布准备度的项目内部方法入口，审核官网或自有站点内容的问题覆盖、声明证据、实体一致性、页面可理解性、结构化数据和时效性。由 content-orchestrator 或 geo-website-renderer 调用；用户直接说 GEO 发布前检查时也可使用，但三大社交平台规则检查不使用本 Skill。
---

# GEO Prepublish Core

## 目的

找出会让人或 AI 误解页面、无法核验声明或错误识别实体的问题。硬性风险优先于总分。

## 开始前

完整读取：

- `capabilities/geo/methods/evidence-and-entity-policy.md`
- `capabilities/geo/methods/citability-and-content-policy.md`

读取待审内容、对应 brief、证据记录和品牌实体资料。缺少关联材料时先做可完成的检查，并列出无法判断项。

## 检查顺序

品牌/产品内容先执行 `capabilities/geo/methods/positioning-and-audience.md`：运行 `python3 capabilities/geo/scripts/validate_positioning.py <定位卡路径> --require-ready`，creation_ready 不为 true 时不得 ready。检查本篇 application 对应的实际正文、定位版本和语义复核；正文改动导致校验和失配时必须重审。结构通过不能替代正文审阅。纯知识文章无需品牌卡。

1. **阻断项**：未核实核心事实、来源与声明不符、实体冲突、版权/合规问题、Schema 与可见正文不一致。
2. **问题覆盖**：主问题是否被直接回答，必要子问题是否遗漏。
3. **证据**：重要声明能否追溯，来源、日期、范围和置信度是否清楚。
4. **实体**：品牌、产品、人物、地点和关系是否一致且无歧义。
5. **可理解性**：标题、开头、章节和表格是否让人快速找到答案。
6. **机器结构**：仅检查实际存在且适用的 Schema、元信息、canonical、robots、sitemap 或 llms.txt。
7. **时效性**：规则、价格、规格、排名和“最新”声明是否过期。

## 结果

- `ready`：没有阻断项，当前目标所需检查通过；
- `needs_revision`：列出按影响排序的最小修改；
- `blocked`：说明阻断事实、需要谁提供什么。

本 Skill 不产出数值评分。判定只用 `ready` / `needs_revision` / `blocked` 三档；不引入加权总分，因为总分会让阻断项被平均掉。检查通过不代表外部平台会引用。

## 输出

```markdown
## GEO 发布前结论
状态：ready / needs_revision / blocked
### 阻断项
### 最小修改
### 已通过检查
### 无法判断
```

不执行公开发布，不代替视频号、抖音、小红书平台规则预检。
