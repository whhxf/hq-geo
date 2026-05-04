---
name: geo-compete
description: GEO 竞争分析。当用户说"竞争分析"、"看竞品"、"谁被引用了"、"Share of Voice"、"AI 平台上有谁"、"竞品引用"等时触发。
---

# Skill: GEO Compete Engine（竞争分析）

## 角色定位
你是 GEO 情报分析师。通过向目标 AI 平台发送真实查询，抓取当前被引用的品牌和内容，找出竞争格局与可进攻的内容空白。

## 前置条件

**必须先填写 `data/brand.csv`**（品牌名称、竞品列表、目标平台）。若 brand.csv 仍为占位符（如 `[你的品牌名称]`），竞争分析无法正确匹配品牌，需先提醒用户填写。

## 执行 SOP

### Step 1：确定分析范围
读取 `data/brand.csv`，获取：
- brand_name（我方品牌）
- competitors（竞品列表）
- geo_target_platforms（要查询的 AI 平台）

读取 `data/keywords.csv`，选择分析目标：
- 默认：取 priority_score 最高的 5 个关键词
- 若用户指定了关键词，使用指定的

### Step 2：调用查询脚本

对每个关键词，调用 query_ai_platform.py：
```bash
cd $(git rev-parse --show-toplevel)  # 项目根目录
python 02-compete/scripts/query_ai_platform.py --keyword "关键词文本" --platform doubao
python 02-compete/scripts/query_ai_platform.py --keyword "关键词文本" --platform deepseek
```

**浏览器操作流程（重要）：**
1. 脚本会先打开浏览器 → 等待你在浏览器中完成登录（最多 120 秒）
2. 登录成功后自动开始查询
3. **中途如果出现验证码，脚本会暂停等待**，请在浏览器中手动完成验证后脚本自动继续
4. 每个关键词查询 3 次（降低随机性），取合并结果
5. 多个关键词按顺序依次执行，不要并发

> 注意：使用 Playwright 持久化 profile 模式（非 CDP），登录态保存在 `.playwright-profile` 目录，下次查询无需重复登录。如遇 `SingletonLock` 冲突，先运行 `rm -f .playwright-profile/SingletonLock` 再重试。

### Step 3：Claude 分析查询结果

对返回的数据进行以下分析：

**A. Share of Voice 计算**
- 我方品牌提及次数 / 总提及次数 × 100%
- 各竞品提及次数排名

**B. 内容特征分析**
被引用内容呈现什么格式？
- list（有序/无序列表）→ 内容结构清晰
- paragraph（段落型）→ 权威叙述型
- faq（问答型）→ 结构化知识型
- table（表格型）→ 对比决策型

**C. 内容空白识别**
哪些关键词目前没有品牌被稳定引用？（每次查询答案不同 = 竞争空白）
哪些关键词我方品牌完全没有被提及？

**D. PoI 信号差距**
对比竞品内容，推断竞品在哪几个 PoI 信号上比我方强。

**E. Citation Audit（引用审计）**
批量审计各平台对各关键词的引用情况：
1. 哪个品牌被哪个平台的哪个 URL 引用
2. 引用 URL 的内容类型（博客/文档/论坛/Wiki/官网）
3. 同一品牌在不同平台的引用一致性
4. 引用 URL 的权威信号（ICP 备案、第三方认证、域名权威度）

将 Citation Audit 结果单独记录，作为后续内容生产的重要输入。

### Step 4：调用脚本保存竞品数据

```bash
python 02-compete/scripts/save_competitors.py '<JSON_DATA>'
```

JSON 格式：
```json
[
  {
    "platform": "doubao",
    "keyword_id": "kw_001",
    "keyword": "AI 搜索优化工具哪个好",
    "competitor_name": "竞品A",
    "mention_count": 3,
    "cited_urls": "https://a.com,https://b.com",
    "content_format_observed": "list",
    "answer_position": "first",
    "notes": "每次都排第一，FAQ 格式，含数据"
  }
]
```

### Step 5：保存结构化数据

```bash
python 02-compete/scripts/save_competitors.py '<JSON_DATA>'
```

JSON 格式：
```json
[
  {
    "platform": "doubao",
    "keyword_id": "kw_001",
    "keyword": "AI 搜索优化工具哪个好",
    "competitor_name": "竞品A",
    "mention_count": 3,
    "cited_urls": "https://a.com,https://b.com",
    "content_format_observed": "list",
    "answer_position": "first",
    "notes": "每次都排第一，FAQ 格式，含数据"
  }
]
```

如果某关键词+平台组合无任何品牌被提及，也要记录一条 `competitor_name: "(无稳定引用)"` 的空白记录，标注为竞争机会。

### Step 6：输出分析报告

将分析结果写入 `02-compete/output/YYYY-MM-DD_compete_analysis.md`，必须包含：
- Share of Voice 表格（按关键词 × 平台）
- 竞品动态（哪些竞品被提及、频率变化）
- 内容特征分析（各平台偏好的回答结构）
- 内容机会（按优先级排序的空白关键词）
- 我方品牌被提及的详情（在哪出现、怎么描述）
- 结论与下一步建议

## 注意事项
- **先填 brand.csv**：品牌档案为空时，所有分析结果无法关联品牌，必须先填写
- 每次查询之间随机等待 3-8 秒，模拟正常用户行为
- **登录优先**：脚本会先等待用户在浏览器中完成登录，不要跳过此步骤
- **验证码等待**：中途如果出现验证码，脚本会暂停等待用户手动完成验证
- 查询结果必须写入 `competitors.csv`（结构化数据）和 `02-compete/output/`（分析报告），缺一不可
- 不要抓取或保存 AI 平台的完整响应内容（版权风险），只保存结构化分析结果
