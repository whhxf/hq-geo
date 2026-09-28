---
name: geo-attribution
description: 设计和复盘 GEO 商业效果归因、预算试点、线索/成交追踪、增量实验与 ROI。用户问 GEO 是否有效、该投多少钱、线索来自哪里、如何做 A/B 测试、怎样从可见度连到收入时使用；只查 AI 是否提及品牌时使用 geo-monitor。
---

# GEO Attribution

## 目的

把 GEO 的可见度样本、营销触点和业务结果连成可审计的决策实验。输出的是可执行计划或复盘结论，不承诺固定排名，也不把相关性包装成因果。

## 开始前

完整读取：

- `capabilities/geo/methods/measurement-attribution-and-roi.md`
- `capabilities/geo/methods/intent-and-query-model.md`
- `capabilities/geo/methods/evidence-and-entity-policy.md`
- `capabilities/geo/contracts/geo-attribution-plan.schema.json`

读取现有问题集、监控记录、CRM/销售口径、成本和转化数据。缺失信息会改变目标或利润口径时，一次只问一个最关键问题；不能取得的数据标成缺失，不自行估算。

## 工作流

1. 区分本轮目标是描述准确、可见度、合格线索、成交、收入还是贡献毛利。
2. 写明本轮要做的预算决策以及 `scale / iterate / stop` 条件。
3. 从历史成交词、SEM、客服与销售真实问法中选择 1—5 个意图簇；没有直接证据时标记为假设。
4. 建立基线，固定 AI 采样环境；调用 `geo-monitor` 只取得呈现层证据。
5. 选择最小标记组合：至少一个直接或交叉验证标记；具备条件时增加地域、门店、词根或分阶段对照。
6. 声明去重键、归因模型、观察窗口、成本与价值口径、同期活动和污染风险。
7. 用 `capabilities/geo/scripts/validate_attribution_plan.py` 校验计划。校验通过只代表实验要素齐全，不代表实验结论成立。
8. 复盘时按 `direct / corroborated / experimental / directional` 分层报告，不直接相加；只有实验条件足够时才报告增量。
9. ROI 优先使用贡献毛利；只有收入时输出 `revenue_return`；只有线索时输出合格线索成本。

## 输出

第一屏先回答：现在能否做预算判断、缺什么证据、下一步最小实验是什么。随后给出：

```markdown
## GEO 归因结论 / 试点计划
### 决策与主指标
### 意图簇与处理动作
### 标记和对照矩阵
### 成本、价值与公式
### 去重、混杂和数据缺口
### Scale / Iterate / Stop 条件
### 证据等级与不可声称事项
```

用户要求落盘时生成符合契约的 JSON；观测和结果只追加，不改写历史记录。

## 边界

- 不把提及率、Top3 或引用数量当作成交证据。
- 不使用来源文章中的固定比例、报价或 ROI 阈值替代企业单位经济。
- 不声称专属链接完全隔离 SEO 或其他渠道。
- 不因没有完美归因而拒绝行动；选择能支持下一次决策的最小证据组合。
- 不自动购买媒体、广告、电话或其他付费服务。
