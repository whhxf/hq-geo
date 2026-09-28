---
title: 'HQ Content Engine 到 Vidmix 的首条创作闭环'
type: 'feature'
created: '2026-09-11'
status: 'in-progress'
baseline_commit: '7fd0dc3d8a8da899d53e2560a75f257fce53222f'
context:
  - 'AGENTS.md'
  - '00-meta/content-engine/05-architecture-and-roadmap.md'
  - 'skills/content-orchestrator/SKILL.md'
  - '/Users/conan/project/hq-vidmix/AGENTS.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** HQ Content Engine 已能形成文本、脚本和制作简报，但没有稳定方式把创作任务交给本地 Vidmix，也不能让后续 Codex 会话可靠发现生成结果、执行记录和阻塞原因。

**Approach:** 建立版本化的 `CreativeJob → Vidmix project → ProductionReceipt` 文件协议、双端命令和 Vidmix“HQ 待制作任务”界面；以选题库第一项 `P1-01` 跑通一次图片与视频生产链路。首轮采用不冒充真实产品或客户证据的概念化视觉，真实生成费用仍经过一次明确授权。

## Boundaries & Constraints

**Always:** HQ Content Engine 保持内容、事实与平台要求的真源；Vidmix 保持生成策略、媒体工程和成品的真源；所有输入、输出均使用稳定 ID、绝对路径和可校验 JSON；策略记录版本、适用条件和失效边界；回执必须让 Codex 无需查询 Vidmix 数据库即可定位产物；修改规则后再改实现；保护两个仓库现有未提交内容。

**Ask First:** 调用产生实际 API 费用的图片或视频模型；缺失事实会改变内容承诺；需要覆盖已有同 ID 生产任务或成品。

**Never:** 合并两个仓库；复制整套 dbs Skills；把“爆火”写成效果保证；用生成图冒充产品 UI、客户案例或真实沟通记录；自动发布、git push、提交密钥；直接让 HQ Content Engine 写 Vidmix 数据库。

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| 首次交接 | P1-01 选题与可用脚本 | 生成有效 `creative-job.json`，Vidmix 创建隔离项目并可列出计划 | 缺少必填字段时拒绝导入并给出字段路径 |
| 生成完成 | 图片或视频文件已落盘 | 写入 `production-receipt.json`，包含绝对路径、校验和、策略版本与检查状态 | 文件不存在或越出项目目录时回执校验失败 |
| 事实不足 | P1-01 没有真实客户记录 | 只允许概念化画面并标注 synthetic，不生成伪造聊天截图 | 将依赖真实证据的镜头标记 blocked |
| 重复执行 | 相同 job ID 已存在 | 默认拒绝覆盖；显式 revision 创建新版本 | 保留旧回执和产物 |
| 多平台生产 | 同一母内容需要抖音、小红书、视频号和文章物料 | CreativeJob 明确共享母版、渠道交付矩阵、数量、比例、时长与验收要求 | 单张图或单段视频只能算阶段产物，不能把任务标记完成 |
| 人机决策 | 任务已导入但尚未生产 | 按范围、策略、关键视觉、母版、渠道包顺序一次展示一个决策 | 每批付费调用前再次确认数量、用途和成本 |

</frozen-after-approval>

## Code Map

- `capabilities/creative-handoff/` -- CreativeJob 与 ProductionReceipt 契约、规则和确定性校验/导出脚本的唯一真源。
- `content/briefs/video-album/P1-01/` -- 第一项选题的脚本、制作简报与实际交接任务。
- `test/suites/`、`test/feature_registry.json`、`test/test_manifest.json` -- HQ Content Engine 回归测试和能力登记。
- `/Users/conan/project/hq-vidmix/packages/engine/src/creative-handoff/` -- Vidmix 导入、项目初始化、回执写入及验证实现。
- `/Users/conan/project/hq-vidmix/packages/engine/src/cli.ts` -- 面向 Codex 和其他本地 Agent 的交接命令入口。
- `/Users/conan/project/hq-vidmix/creative-packs/` -- 首批版本化创作策略包；不复制 dbs 方法正文。
- `/Users/conan/project/hq-vidmix/packages/engine/src/__tests__/` -- 导入、拒绝覆盖、路径和回执契约测试。

## Tasks & Acceptance

**Execution:**
- [x] `AGENTS.md` 与 `/Users/conan/project/hq-vidmix/AGENTS.md` -- 先登记跨项目真源、目录和覆盖规则。
- [x] `capabilities/creative-handoff/` -- 定义两个 JSON Schema、示例、校验器及从 ProductionBrief 生成 CreativeJob 的命令。
- [x] `content/briefs/video-album/P1-01/` -- 补齐受事实边界约束的首条 ProductionBrief、脚本和交接任务。
- [x] `/Users/conan/project/hq-vidmix/creative-packs/` -- 建立策略包规范与一个适用于 P1-01 的概念化“收件箱断点解释”策略。
- [x] `/Users/conan/project/hq-vidmix/packages/engine/src/creative-handoff/`、`cli.ts` -- 导入任务、创建版本目录、生成计划、登记产物并写回执。
- [x] `/Users/conan/project/hq-vidmix/apps/desktop/src/pages/CreativeJobsHub.tsx` 及 Electron bridge -- 在 Vidmix 展示待制作任务、脚本、策略、事实边界，并把生产上下文预填到素材对话。
- [x] CreativeJob r3 与 Vidmix 状态机 -- 用共享母版、渠道交付矩阵和可复用生产单元替代“生成一张图/一段视频”，按五个决策点推进。
- [x] `/Users/conan/project/hq-vidmix/.agents/skills/content-production-orchestrator/SKILL.md` -- 一次只暴露当前决策，每批付费生成前显示数量、用途与成本，并在物料和检查齐全前阻止完成。
- [x] Vidmix 引导界面 -- 展示完整交付矩阵、生产批次、当前唯一决策和历史任务完成度；旧版单产物任务显式降级提示。
- [x] 双端测试登记 -- 覆盖正常交接、缺字段、越界路径、重复 job 和 synthetic 声明。
- [ ] 真实演练 -- 先导入 P1-01；获得费用授权后生成至少一张关键帧和一段短视频；登记回执并由 HQ Content Engine 回读。

**Acceptance Criteria:**
- Given P1-01 已形成合法 CreativeJob，when Vidmix 执行导入，then Codex 可从命令输出直接获得 Vidmix 项目和计划绝对路径。
- Given 生成文件已登记，when HQ Content Engine 回读回执，then 可定位并展示图片/视频，同时追溯 topic、job、strategy 和 revision。
- Given 真实素材缺失，when Agent 自动选择策略，then 只选允许 synthetic 的概念化表达，并阻断伪造客户或产品事实的镜头。
- Given P1-01 已导入，when 用户打开 Vidmix 的 HQ 待制作任务，then 能查看推荐策略和生产范围，并一键进入已预填上下文的素材对话。
- Given P1-01 r3 已导入，when 用户推进生产，then Vidmix 依次要求确认交付范围、创作策略、关键视觉、母版和渠道发布包，任一时刻只暴露一个主要决策。
- Given 已生成一张图或一段视频，when 交付矩阵仍有缺口，then 页面显示部分进度且引擎拒绝把任务标记为完成。
- Given 两端代码完成，when 执行 HQ quick/full/release 与 Vidmix build/typecheck/相关测试，then 必需门禁全部通过才宣称闭环完成。

## Design Notes

文件系统是第一版集成总线。HQ 只交付不可变任务；Vidmix 将每次尝试放入 `runs/<revision>/`，写出自包含回执；HQ 通过显式 import 命令接收回执，不使用软链接和数据库耦合。策略包把内容机制、视频形式与视觉皮肤分字段保存，避免“风格”退化为滤镜提示词。

## Verification

**Commands:**
- `python3 test/run_quality_gate.py quick` -- HQ 快速门禁 PASS。
- `python3 test/run_quality_gate.py full` -- HQ 跨模块门禁 PASS。
- `python3 test/run_quality_gate.py release` -- HQ 发布门禁 PASS。
- `npm run typecheck && npm run build`（Vidmix）-- 类型和构建通过。
- Vidmix creative-handoff 相关测试 -- 正常与错误矩阵全部通过。
