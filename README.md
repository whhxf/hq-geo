# HQ-GEO Engine

> Unix 哲学：文件夹即应用，对话即操作，CSV 即数据库，Markdown 即内容仓库。

HQ-GEO 是一个本地 GEO 作战模板，不是重型后端系统。它通过 `SKILL.md + Python 脚本 + CSV/Markdown` 形成可复制的工作流闭环：

- 关键词规划（01-intent）
- 竞争观察（02-compete）
- 内容生产与审计（03-content）
- 平台监控（04-monitor）
- 报告生成（05-report）
- 问题层与证据层沉淀（data/questions.csv, data/evidence.csv）

## 这是什么 / 不是什么

- **是**：可对话驱动、可复制、可落盘的 GEO 工作流模板
- **不是**：含数据库、任务队列、自动发布、Web UI 的一体化 SaaS
- **当前主入口**：各模块 `SKILL.md`
- **主数据存储**：`data/*.csv`
- **内容资产**：`03-content/output/*.md`

## 快速开始

### 1) 安装 web-access 技能（必需）

本项目内容求证依赖 `/web-access`。

```bash
git clone https://github.com/eze-is/web-access.git ~/.claude/skills/web-access
bash ~/.claude/skills/web-access/scripts/check-deps.sh
```

若提示 Chrome 调试授权，请在 `chrome://inspect/#remote-debugging` 勾选 **Allow remote debugging for this browser instance** 并完成授权。

### 2) 配置环境

```bash
cd <项目路径>
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
```

### 3) 填写品牌档案

直接编辑 `data/brand.csv`（键值对模式：`field,value`）。

### 4) 对话触发

- "帮我生成 GEO 关键词"
- "分析一下我们在豆包上的竞争情况"
- "针对「XXX」这个关键词写一篇 GEO 内容"
- "运行今天的监控"
- "生成本周 GEO 报告"

## 关键文档路径

- 产品需求与范围：`00-meta/PRD.md`
- 架构思想与愿景：`00-meta/GEO系统设计方案.md`
- 测试与运行说明：`TEST_PLAN.md`

> 注：`00-meta/GEO系统设计方案.md` 中包含部分中长期愿景；当前仓库实现以 `SKILL.md + scripts` 实际行为为准。

## 目录结构（当前实现）

```text
hq-geo/
├── 00-meta/                      ← PRD 与架构文档
├── data/                         ← 主数据层（模板默认带 brand/keywords/questions/evidence）
├── 01-intent/
├── 02-compete/
├── 03-content/
├── 04-monitor/
├── 05-report/
├── lib/
├── requirements.txt
└── .env.example
```

## 新增抽象层（v2）

- `data/questions.csv`：关键词层的补充，沉淀真实用户问法（监控与内容结构共用）
- `data/evidence.csv`：求证后结构化证据资产，可复用到内容更新与报告分析
- `03-content/rules/`：白帽声明规则与合规检查清单
- `03-content/scripts/check_claim_risk.py`：轻量声明风险扫描

## 数据层分级（基础 / 增强）

- 基础层（默认必需）：`data/brand.csv`、`data/keywords.csv`
- 增强层（按需启用）：`data/questions.csv`、`data/evidence.csv`
- 运行期可选：`data/content.csv`、`data/monitor_log.csv`、`05-report/output/*.md`

## 数据流（实现语义）

```text
brand.csv（品牌档案）
  -> 01-intent 生成 keywords.csv
  -> 01-intent 可补充 questions.csv（问题层）
  -> 02-compete 查询平台并写 competitors.csv（可选）
  -> 03-content 生成内容文件与 content.csv（可选）
  -> 03-content 求证后可写 evidence.csv（证据层）
  -> 04-monitor 对已产内容关键词执行监控，写 monitor_log.csv（可选）
  -> 05-report 读取 CSV 聚合生成 report_YYYY-MM-DD.md（可选）
```

## 当前脚本实际支持的平台

`02-compete/scripts/query_ai_platform.py` 当前支持：

- `doubao`
- `deepseek`
- `chatgpt`
- `perplexity`

若在 `brand.csv` 配置未实现的平台（如 `gemini`），会导致查询报错。

## 运行边界说明

- 监控与竞争分析依赖本机浏览器登录态（Playwright 持久化 profile）。
- 多数输出文件默认被 `.gitignore` 忽略（例如 `03-content/output/`、`05-report/output/`、运行期 CSV）。
- 本仓库强调人机协同：Claude 负责策略/写作，Python 负责确定性落盘和检查。

## 稳定性优先约定（奥卡姆剃刀）

- 只保留必要机制：`CSV + Markdown + Python 脚本`，不引入数据库、消息队列、任务编排器。
- 多值字段统一约定：`competitor_mentioned` 允许 `,` 与 `;`，统计层做兼容解析。
- CSV 示例中若值包含逗号，必须加引号（如 `geo_target_platforms`），避免截断。
- 新增脚本遵循“单一职责 + 可直接命令行执行”，避免过度抽象。
- 任何增强先问：是否能减少故障面？若不能，则不加。

## 一键轻量体检

```bash
python3 lib/smoke_check.py
```

检查项：

- 基础层 CSV 文件存在且头字段完整
- 增强层 CSV 若存在则校验头字段
- `brand.csv` 平台配置不超出已支持平台
- 核心脚本语法可编译

> 说明：`smoke_check` 是运行前轻量体检，不等价于端到端回归测试。

## 验证新 SOP

请按 `TEST_PLAN.md` 执行全量验证，重点覆盖：

- 子系统协作（01→02→03→04→05）
- 字段传递（keywords/questions/evidence/monitor/report）
- 模板与审计契约一致性（FAQ + Schema + 审计）
- 异常分支（平台不支持、缺字段、未通过审计）
