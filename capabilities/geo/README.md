# GEO Capability Pack

**状态：** 已实现项目级方法真源与 Skill 路由；不依赖任何采集、评分或 Schema 生成脚本  
**版本：** 2.0.0  
**建立日期：** 2026-09-09  
**最后核验日期：** 2026-09-28

这里是 HQ Content Engine 的 GEO 能力唯一真源。GEO 用于提高品牌内容被 AI 搜索系统理解、检索、引用和正确归因的准备度，不承诺排名、引用或流量结果。

## 分层

```text
methods/                 方法与判断标准
contracts/               Skill 之间传递的数据结构
scripts/                 确定性校验
skills/geo-*/            项目内对话入口与工作流
```

Skill 负责决定做什么、读取什么和如何与用户交互；本目录保存共享方法；Python 脚本负责确定性检查。多个 Skill 不复制方法正文。

## 完整 GEO 何时加载

- 用户明确说 GEO、AI 搜索优化、AI 引用或品牌在 AI 回答中的可见性；
- 目标产物是官网文章、产品页、FAQ、比较页、定义页或品牌知识页；
- 用户要求检查官网能否被 AI 理解、引用或正确归因；
- 用户要求建设信源、监控 ChatGPT、Perplexity、豆包、DeepSeek 等 AI 回答。

## 只加载轻量守卫的情况

视频号、抖音、小红书等纯社交内容默认只复用：

1. 事实可验证；
2. 品牌、产品、人物与概念名称一致；
3. 核心观点能被一句话准确复述。

不因此强制 FAQ、Schema、llms.txt、关键词出现次数或 GEO 评分。

## 方法文件

- [核心写作：定位与用户场景](./methods/positioning-and-audience.md)：品牌社交与 GEO 共用，事实包中保存派生定位，交付前校验版本、事实引用与语义复核。

- [意图与查询模型](./methods/intent-and-query-model.md)
- [证据与实体政策](./methods/evidence-and-entity-policy.md)
- [可引用性与内容政策](./methods/citability-and-content-policy.md)
- [测量、归因与 ROI](./methods/measurement-attribution-and-roi.md)
- [GEO 上下文数据契约](./contracts/geo-context.schema.json)
- [GEO 归因计划数据契约](./contracts/geo-attribution-plan.schema.json)
- [能力清单与路由](./manifest.json)

## 执行边界

本能力包提供方法、契约和校验器，**不提供执行器**。平台采样通过 `web-access` 人工触发；Schema 按页面实际内容手写；发布前判定只用 `ready` / `needs_revision` / `blocked` 三档，不产出数值评分。

2026-09-28 之前存在 `01-intent` 至 `07-prepublish` 七个编号模块，其中的采集、评分与 Schema 生成脚本已归档到仓库外的 `hq-geo-retired-20260928/`。需要时从归档或 git 历史取回，不在本目录重建。

## 验证

```bash
python3 capabilities/geo/scripts/validate_pack.py
python3 capabilities/geo/scripts/validate_attribution_plan.py capabilities/geo/examples/attribution-plan.example.json
python3 -m unittest capabilities.geo.tests.test_validate_pack
```
