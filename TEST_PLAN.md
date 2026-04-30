# HQ-GEO 新 SOP 测试计划（v3）

> 目标：验证新 SOP 在设计范围内可稳定运行，且子系统配合、流程衔接、字段传递均正确。  
> 适用范围：`01-intent`、`02-compete`、`03-content`、`04-monitor`、`05-report`，以及新增 `questions/evidence/rules` 层。

---

## 一、测试原则

- 以“模板形态”验证，不引入数据库、任务队列、自动发布。
- 先验证字段契约，再验证脚本行为，再做端到端串联。
- 每个阶段保留输入、执行命令、输出快照，便于回归。
- 对外部依赖（平台登录态、网络）采用可跳过/可替身策略。

---

## 二、测试环境准备

### 2.1 必需环境

- Python 3.10+
- `pip install -r requirements.txt`
- `playwright install chromium`
- `.env` 已配置（至少包含模板默认配置）
- web-access 可用（用于内容求证流程）

### 2.2 测试数据初始状态

基础层（默认必需）文件需存在且格式正确：

- `data/brand.csv`
- `data/keywords.csv`

增强层（按需启用）仅在本轮测试覆盖对应能力时准备：

- `data/questions.csv`（问题层）
- `data/evidence.csv`（证据层）

建议在测试前备份：

- `data/*.csv`
- `03-content/output/`
- `05-report/output/`

---

## 三、测试矩阵（总览）

| 阶段 | 目标 | 通过标准 |
|------|------|----------|
| A. 静态契约检查 | 模板、脚本、规则文件一致 | 无字段缺失、无语法错误 |
| B. 单模块功能测试 | 每个脚本单独可用 | 输出结构正确、异常可控 |
| C. 跨模块集成测试 | 模块间字段传递正确 | 关键字段不丢失、不变形 |
| D. 新 SOP 端到端测试 | 从关键词到报告完整串联 | 全链路可跑通且审计通过 |
| E. 负向与边界测试 | 错误分支符合预期 | 脚本可报错、可定位、无脏写 |

---

## 四、阶段 A：静态契约检查

### A0. 一键轻量体检（先跑）

执行：

```bash
python3 lib/smoke_check.py
```

通过标准：

- 输出 `SMOKE CHECK PASSED`。
- 若失败，优先修复 CSV 头字段/平台配置/语法错误，再进入后续阶段。

### A1. Python 语法与导入检查

执行：

```bash
python3 -m py_compile \
  01-intent/scripts/save_keywords.py \
  01-intent/scripts/save_questions.py \
  02-compete/scripts/query_ai_platform.py \
  03-content/scripts/generate_schema.py \
  03-content/scripts/audit_content.py \
  03-content/scripts/check_claim_risk.py \
  03-content/scripts/save_content.py \
  03-content/scripts/save_evidence.py \
  04-monitor/scripts/monitor.py \
  04-monitor/scripts/analyze_trend.py \
  05-report/scripts/generate_report.py \
  lib/hq_geo_lib.py \
  lib/monitor_metrics.py
```

通过标准：

- 所有脚本编译通过，无语法错误。

### A2. 模板契约检查（FAQ/Schema）

检查文件：

- `03-content/templates/faq.md`
- `03-content/templates/howto.md`
- `03-content/SKILL.md`
- `03-content/scripts/audit_content.py`
- `03-content/scripts/generate_schema.py`

通过标准：

- FAQ 标题统一为 `## 常见问题（FAQ）`。
- 审计规则与模板标题一致。
- Schema 逻辑包含 `FAQPage.mainEntity`。

---

## 五、阶段 B：单模块功能测试

### B1. Intent 层（关键词 + 问题）

1) 执行 `save_keywords.py` 写入 2 条测试关键词  
2) 执行 `save_questions.py` 为其中 1 条关键词写入 2 条问题

通过标准：

- `keywords.csv` 新增 `kw_*` 且去重生效。
- `questions.csv` 新增 `q_*`，`keyword_id` 能关联到已有关键词。

### B2. Content 辅助层（Schema / Evidence / 审计）

1) 用 `generate_schema.py` 分别测试 `faq/howto/comparison/definition`  
2) 用 `save_evidence.py` 写入 2 条证据（含重复输入）  
3) 用 `check_claim_risk.py` 扫描一份含绝对化文案的测试文件  
4) 用 `audit_content.py` 对一份标准内容与一份故意错误内容审计

通过标准：

- 四种格式都可生成有效 JSON-LD。
- `save_evidence.py` 可去重，不重复写入同 claim+source_url。
- 风险扫描能命中高风险声明并返回非 0。
- 审计能准确区分通过/失败，并给出可读问题定位。

### B3. Monitor/Report 公共指标一致性

1) 准备同一批 `monitor_log.csv` 测试数据  
2) 分别运行 `analyze_trend.py` 与 `generate_report.py`

通过标准：

- 两者对同一周期提及率口径一致（允许展示格式不同）。
- 竞品计数与关键词分组统计结果一致。

---

## 六、阶段 C：跨模块集成测试（字段传递）

### C1. 关键词 -> 问题 -> 内容

验证字段：

- `keywords.id` -> `questions.keyword_id`
- `keywords.content_format` -> 内容模板选择
- `keywords.id` -> `content.keyword_id`

通过标准：

- 字段链路完整，无空值断链。

### C2. 内容 -> 证据 -> 监控

验证字段：

- 内容中的 `keyword_id` 对应 `evidence.keyword_id`
- `monitor_log.keyword_id` 可回溯到 `keywords.csv`

通过标准：

- 同一关键词在内容、证据、监控三层可追溯。

### C3. 监控 -> 报告

验证字段：

- `monitor_log.platform`
- `monitor_log.brand_mentioned`
- `monitor_log.competitor_mentioned`
- `keywords.priority_score/status`

通过标准：

- 报告中平台表现、关键词明细、竞品统计、内容缺口与源数据一致。

---

## 七、阶段 D：新 SOP 端到端测试（主流程）

建议执行顺序：

1. 维护 `brand.csv`
2. 通过 `01-intent` 生成 `keywords.csv`
3. 通过 `01-intent` 生成 `questions.csv`
4. 选择 1 个关键词生成内容（含 FAQ + Schema）
5. 运行 `check_claim_risk.py`
6. 运行 `audit_content.py`（需通过）
7. 写入 `content.csv` 与 `evidence.csv`
8. 运行 `monitor.py`（至少 1 平台）
9. 运行 `analyze_trend.py`
10. 运行 `generate_report.py`

通过标准：

- 全链路无手工修 CSV（除初始化外）。
- 审计通过后才进入监控与报告。
- 最终报告可回溯到关键词、监控日志与证据层。

---

## 八、阶段 E：负向与边界测试

### E1. 平台边界

- 在 `brand.csv` 配置未支持平台（如 `gemini`）
- 预期：脚本明确报“不支持的平台”，不中断其他数据文件完整性。

### E2. 字段缺失

- 刻意移除 `questions.csv` 必填列/空值
- 预期：保存脚本拒绝或跳过非法记录，并给出提示。

### E3. 审计失败分支

- 构造 FAQ 数量与 Schema 不一致内容
- 预期：`audit_content.py` 返回失败，阻止后续发布/监控环节。

### E4. 重复写入

- 重复执行 `save_questions.py` / `save_evidence.py` 同样输入
- 预期：去重生效，不产生重复记录。

---

## 九、执行记录模板

每个测试用例建议记录以下字段：

- 用例编号
- 前置数据
- 执行命令
- 关键输出
- 结果（PASS/FAIL）
- 失败原因
- 修复动作
- 回归结果

---

## 十、验收标准（本次改动）

满足以下全部条件，判定“新 SOP 可用”：

- 所有改动脚本语法通过。
- FAQ/Schema/审计契约一致，无互相打架。
- `questions/evidence` 两个新增数据层可独立写入并被主流程使用。
- monitor/report 口径统一，不出现同周期统计矛盾。
- 至少 1 条端到端链路在真实环境跑通并产出报告。

---

## 十一、明确不做（避免过度设计）

以下项刻意不引入，避免提升复杂度与故障面：

- 不引入数据库与 ORM
- 不引入任务队列与调度中心
- 不引入微服务拆分与 RPC
- 不引入额外测试框架作为运行前置（保留轻量脚本体检）

---

## 十二、测试后清理（防止模板污染）

测试使用临时样本时，结束后需恢复模板基线：

- 删除测试运行产物：`data/content.csv`、`data/monitor_log.csv`、`05-report/output/*.md`
- 清理测试注入记录：`data/keywords.csv`、`data/questions.csv`、`data/evidence.csv` 中的临时行
- 保留模板示例行，不保留测试业务数据
- 再次执行 `python3 lib/smoke_check.py`，确认基础层可用
