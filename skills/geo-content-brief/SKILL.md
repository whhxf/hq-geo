---
name: geo-content-brief
description: 把已确认的 GEO 研究、用户问题或内容选题转成可供官网文章、产品页、比较页、定义页和 FAQ 页面使用的内容蓝图。用户要为 AI 搜索准备官网内容、把社交选题沉淀为长期网站资产、基于研究结果规划页面但尚未要求直接写成完整网页时使用；普通短视频或小红书文案不要触发。
---

# GEO Content Brief

## 目的

在写正文前固定页面要回答的问题、可发布的声明、证据、实体和边界，避免为了结构或关键词改变原始观点。

## 开始前

完整读取：

- `capabilities/geo/methods/intent-and-query-model.md`
- `capabilities/geo/methods/evidence-and-entity-policy.md`
- `capabilities/geo/methods/citability-and-content-policy.md`
- `capabilities/geo/contracts/geo-context.schema.json`

读取上游 `geo-research` 结果、选定的 `TopicCandidate` 或用户材料。没有完成研究但输入足够时可以生成暂定蓝图，必须标记未验证项。

## 工作流

品牌/产品内容先执行 `capabilities/geo/methods/positioning-and-audience.md`：引用事实包 positioning.json 的 id/revision，选择本篇 audience/scenario/problem 和证明优势的 fact_ids；记录适用边界。定位缺证据时仅输出标明缺口的草案。普通概念解释只确认读者与场景，不强塞品牌。

1. 写出页面的一句话任务：谁在什么情况下，需要完成什么判断或行动。
2. 确定主问题和最多 3—7 个必要子问题；删除只为关键词覆盖而存在的问题。
3. 建立 Claim–Evidence Map：事实、解释、经验、观点和预测分别处理。
4. 固定品牌、产品、人物和概念实体名称，列出同名歧义。
5. 设计直接答案、解释、证据、条件、反例和下一步之间的顺序。
6. 判断页面类型。FAQ、HowTo、比较表和 Schema 只在内容真实需要时标记。
7. 标记版权、合规、过期来源和仍需用户确认的部分。

## 输出契约

```markdown
# Content Brief: {页面主题}
## 页面任务
- 目标受众与场景：
- 主问题：
- 一句话答案：
- 希望用户完成的下一步：
## 问题结构
## Claim–Evidence Map
## 实体卡
## 页面结构
## 可选机器结构
## 反例与边界
## 待核验与阻断项
```

用户要求保存时，优先写入 `content/canonical/` 或上游任务指定目录，并在 front matter 记录来源实体 ID。

## 边界

- 不直接生成平台社交文案。
- 不为凑结构强制 3 个 H2、FAQ 或统计数字。
- 不把未核实声明移交给 renderer 当成事实。
- 蓝图确认后才进入 `geo-website-renderer`。
