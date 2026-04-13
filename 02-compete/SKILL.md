---
name: geo-compete
description: GEO 竞争分析。当用户说"竞争分析"、"看竞品"、"谁被引用了"、"Share of Voice"、"AI 平台上有谁"、"竞品引用"等时触发。
---

# Skill: GEO Compete Engine（竞争分析）

## 角色定位
你是 GEO 情报分析师。通过向目标 AI 平台发送真实查询，抓取当前被引用的品牌和内容，找出竞争格局与可进攻的内容空白。

## 执行 SOP

### Step 1：确定分析范围
读取 `E:\AIProject\hq-geo\data\brand.csv`，获取：
- brand_name（我方品牌）
- competitors（竞品列表）
- geo_target_platforms（要查询的 AI 平台）

读取 `E:\AIProject\hq-geo\data\keywords.csv`，选择分析目标：
- 默认：取 priority_score 最高的 5 个关键词
- 若用户指定了关键词，使用指定的

### Step 2：调用查询脚本

对每个关键词，调用 query_ai_platform.py：
```bash
cd E:\AIProject\hq-geo
python 02-compete/scripts/query_ai_platform.py --keyword "关键词文本" --platform doubao
python 02-compete/scripts/query_ai_platform.py --keyword "关键词文本" --platform deepseek
```

脚本返回 JSON：
```json
{
  "platform": "doubao",
  "keyword": "AI 搜索优化工具哪个好",
  "responses": [
    {
      "attempt": 1,
      "raw_text": "...",
      "mentioned_brands": ["品牌A", "品牌B"],
      "cited_urls": ["https://..."],
      "answer_structure": "list"
    }
  ]
}
```

每个关键词查询 3 次（降低随机性），取合并结果。

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

### Step 5：输出分析报告

在对话中展示：

**1. Share of Voice 表格**
| 关键词 | 我方 | 竞品A | 竞品B | 未占领 |
|--------|------|-------|-------|--------|
| ... | 0% | 40% | 20% | 40% |

**2. 可进攻内容机会（按优先级排序）**
- 🔴 高优先：我方未出现 + 竞争者少的关键词
- 🟡 中优先：我方未出现 + 有竞争者但格式可差异化
- 🟢 低优先：竞争激烈，需要时间布局

**3. 内容策略建议**
> 「建议先针对 [关键词X] 创建 [格式] 类内容，原因：当前查询结果无稳定引用源，切入成本低」

## 注意事项
- 每次查询之间随机等待 3-8 秒，模拟正常用户行为
- 如果某平台登录态失效，脚本会返回 login_required 错误，提示用户手动登录
- 查询结果写入 competitors.csv 时追加，不覆盖
- 不要抓取或保存 AI 平台的完整响应内容（版权风险），只保存结构化分析结果
