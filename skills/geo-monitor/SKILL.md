---
name: geo-monitor
description: 监控品牌、产品和竞品在 AI 平台回答中的出现、位置、引用来源、回答结构和变化。用户要求运行 GEO 监控、查看 ChatGPT/Perplexity/豆包/DeepSeek 是否提到品牌、比较 AI Share of Voice、追踪引用变化或生成 GEO 监控结果时使用；普通社交平台播放量监控不要触发。
---

# GEO Monitor

## 目的

用可重复问题观察 AI 回答变化。结果是有时间戳的样本，不是平台总体排名，也不能把一次回答当作稳定事实。

## 开始前

1. 读取 `capabilities/geo/methods/intent-and-query-model.md`、`capabilities/geo/methods/evidence-and-entity-policy.md` 和 `capabilities/geo/methods/measurement-attribution-and-roi.md`。
2. 问题集来源：**项目根** `topics/<idea>/` 的选题或用户指定问题。项目内没有自动采集器，采样统一通过 `web-access` 人工触发。

## 工作流

1. 固定问题集、语言、市场、目标平台和采样时间。
2. 对需要联网或登录的 AI 平台统一使用 `web-access`；不要绕过登录、验证码或用户接管。
3. 保存完整回答或允许保存的最小原始记录，再派生品牌/竞品出现、引用 URL、答案位置、语气和变化。
4. 多次采样时分别保存，不只保留平均值。
5. 把无法访问、登录失效、页面变化和无引用区分开，不能都记成“品牌未出现”。
6. 固定并记录平台入口、模型/版本、账号状态、地域、语言、时间和问题版本；无法固定时标成混杂因素。

## 输出

品牌定位监测按 `capabilities/geo/methods/positioning-and-audience.md` 使用适用场景和不适用场景问句，分别报告对象识别、受众匹配、场景匹配、事实准确、不当推荐。记录每项分子、有效分母和未知数，保留原回答。现状采样不因缺定位卡被阻断；无参照事实的匹配判断标为未知。

```markdown
## GEO 监控结论
### 本次变化
### 品牌与竞品出现
### 引用来源
### 失败与未知
### 建议研究/内容动作
```

需要长期记录时，把每次采样写入 `research/raw/`，只追加不覆盖；本 Skill 不产出趋势报告，也不自动生成图表。监控不自动触发内容改写或对外发布。监控只回答“AI 如何呈现品牌”，不能单独证明线索、成交或 ROI；商业效果进入 `geo-attribution`。
