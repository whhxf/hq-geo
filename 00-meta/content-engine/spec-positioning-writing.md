---
title: 品牌定位与场景驱动创作
type: feature
created: 2026-09-28
status: in-review
baseline_commit: 7fd0dc3d8a8da899d53e2560a75f257fce53222f
---

## Intent

把已经授权的定位与用户标签方法接入实际创作入口、事实包和交付检查。采用五步法删除形式要求后，再实现必要自动化。延续当前脏工作区，保留无关修改。

## Boundaries

定位为事实派生视图，不建第二套事实；纯社交也使用写作逻辑，但不加载完整 GEO；普通知识内容无需品牌卡。未知价格和无关人口属性不得编造。公开发布和费用另行授权。

## Tasks & Acceptance

- [x] 方法和根规则：定义五步法、事实引用与渠道表达。
- [x] 契约与校验器：支持草案、证据解析、版本和语义复核门禁。
- [x] 创作入口：编排、brief、renderer、预检、监测引用唯一方法。
- [x] 真实切片：视频画册定位草案只引用已有事实，未复核不放行。
- [ ] 测试登记：无来源、失效版本、禁止声明与未知标签测试；quick/full/release。

Given 缺失定位证据，when 校验草案，then 可保存但不能 creation_ready。
Given 渠道表达引用旧版本，when 交付检查，then 阻断。
Given 价格未知且文章不谈价格，when 其他检查通过，then 不为填满标签阻断。
Given 普通知识内容，when 编排，then 只检查受众场景问题，不强制品牌定位。

## Design Notes

机器只能验证结构和引用，语义复核必须读实际成稿。此轮不实现线上平台自动采样，不改历史成果。

## Review

独立检查发现：按渠道去重阻止同渠道多篇创作、复核未绑定正文、证据类型白名单缺失。修订要求：按产物路径区分 application，复核绑定 SHA-256，正文变化重审，证据类型显式校验。保持草案可保存及未知价位可说明的行为。

## Suggested Review Order

1. [创作路由](../../skills/content-orchestrator/SKILL.md)：先定位，再生成。
2. [方法真源](../../capabilities/geo/methods/positioning-and-audience.md)：五步法与表达边界。
3. [定位校验](../../capabilities/geo/scripts/validate_positioning.py)：事实、版本、正文绑定。
4. 真实定位草案（项目根 `facts/feature/<slug>--<entity>/positioning.json`）：只使用现有证据。
5. [行为测试](../../capabilities/geo/tests/test_positioning.py)：反例与过期复核。
