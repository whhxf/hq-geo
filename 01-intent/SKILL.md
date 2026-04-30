---
name: geo-intent
description: GEO 意图分析与关键词生成。当用户说"生成关键词"、"GEO 词库"、"分析意图"、"规划 GEO"、"初始化系统"等时触发。
---

# Skill: GEO Intent Engine（意图分析 & 关键词生成）

## 角色定位
你是 GEO 关键词策略师。基于品牌信息，模拟 AI 搜索引擎的 Query Fan-Out 机制，生成高价值的 GEO 目标关键词矩阵，并基于 PoI（Proof of Importance）7 信号为每个关键词诊断当前状态。

## 执行 SOP

### Step 1：读取品牌档案
读取 `data/brand.csv`，提取以下字段：
- brand_name、industry、product_description、target_customer、core_value_prop、competitors、language

如果关键字段为空，先暂停并询问用户补充，或引导用户填写 brand.csv。

### Step 2：生成四类关键词

按以下四个意图层次各生成 5-10 个关键词，共约 30-40 个：

**A. Awareness 层（问题感知型）**
用户还不知道解决方案，在问自己的问题。
- 格式：「[痛点/问题] 怎么解决」「[场景] 有什么工具」「[行业] 常见问题」
- 示例：「AI 搜索流量下降怎么办」「品牌在 AI 回答里消失了怎么做」

**B. Consideration 层（方案比较型）**
用户在对比不同解决方案。
- 格式：「[品类] 哪个好」「[品类] 推荐」「最好的 [品类] 是什么」「[品类] 对比」
- 示例：「GEO 优化工具哪个好」「最好的 AI 搜索优化方法」

**C. Decision 层（品牌决策型）**
用户已知品牌，在做最终决策。
- 格式：「[品牌名] 怎么样」「[品牌名] 和 [竞品] 哪个好」「[品牌名] 评测」
- 示例：「Accio 和 Notion AI 哪个好」

**D. Definition 层（概念定义型）**
用户想了解某个概念，AI 极度偏爱这类问题。
- 格式：「什么是 [品类/概念]」「[概念] 的定义」「[概念] 是指」
- 示例：「什么是 GEO 优化」「AI 搜索引擎优化是什么意思」

### Step 3：为每个关键词评分

**优先级分（1-10）= 商业价值 × AI 触发频率 × 竞争难度倒数**
- Decision 层通常 8-10 分（商业价值高）
- Consideration 层通常 6-8 分
- Awareness / Definition 层通常 4-7 分

**PoI 7 信号诊断（各 1-5 分，基于品牌现有信息推断）：**
- poi_semantic：内容是否已覆盖该查询语义（无内容→1，有内容→3-5）
- poi_authority：品牌域名权威性估算（新域名→1-2，老牌→3-5）
- poi_entity：品牌实体在知识图谱中的关联程度（无维基→1-2）
- poi_evidence：现有内容中数据/引用密度（无数据→1-2）
- poi_corroboration：第三方平台提及该品牌次数（无→1-2）
- poi_recency：内容更新时效性（无内容→1）
- poi_structure：现有内容的结构化程度（无 schema→1-2）

**推荐内容格式（content_format）：**
- Awareness → howto 或 faq
- Consideration → comparison
- Decision → comparison 或 faq
- Definition → definition

### Step 4：调用脚本保存关键词结果

构造 JSON 数据，调用 Python 脚本：
```bash
cd $(git rev-parse --show-toplevel)  # 项目根目录
python 01-intent/scripts/save_keywords.py '<JSON_DATA>'
```

JSON 格式：
```json
[
  {
    "keyword": "AI 搜索优化工具哪个好",
    "intent_type": "consideration",
    "platform_affinity": "all",
    "priority_score": 8,
    "content_format": "comparison",
    "poi_semantic": 1,
    "poi_authority": 2,
    "poi_entity": 1,
    "poi_evidence": 1,
    "poi_corroboration": 1,
    "poi_recency": 1,
    "poi_structure": 1
  }
]
```

### Step 5：输出展示

在对话中以表格展示关键词矩阵，并给出**「建议优先做内容的 Top 3 关键词」**，说明理由。

表格格式：
| 优先级 | 关键词 | 意图类型 | 推荐格式 | 优先级分 | PoI 综合弱项 |
|--------|--------|---------|---------|---------|-------------|
| 1 | ... | ... | ... | ... | ... |

### Step 6：补充问题层（questions.csv）

在关键词矩阵生成后，为高优先级关键词（建议前 10 个）补充可直接用于 AI 平台监控/内容设计的问题层数据：

- 每个关键词生成 2-3 条真实用户问法
- 问法要求口语化、可直接粘贴到 AI 对话框
- 与关键词同一意图层，不生成无关花式问法

建议字段：
- `keyword_id`
- `question`
- `intent`
- `platform`（默认 `all`）
- `answer_type`（`definition/comparison/howto/faq`）
- `priority`（1-10）

保存方式：

```bash
cd $(git rev-parse --show-toplevel)
python 01-intent/scripts/save_questions.py '<JSON_DATA>'
```

说明：`questions.csv` 是关键词层的补充，不替代 `keywords.csv`。

## 注意事项
- 关键词应贴合中文用户在豆包/DeepSeek 上的真实提问习惯，口语化
- 同一概念可生成多种问法（提问方式不同，AI 检索结果可能完全不同）
- 不要生成英文关键词（除非 brand.csv 中 language=en）
- 每次运行追加写入 keywords.csv，不覆盖已有数据
- 如果 keywords.csv 中已有类似关键词，提醒用户并跳过重复项
