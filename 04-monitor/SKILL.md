---
name: geo-monitor
description: GEO 监控。当用户说"运行监控"、"监控一下"、"今天被引用了吗"、"看看我们的表现"、"跑一次监控"等时触发。
---

# Skill: GEO Monitor Engine（AI 平台引用监控）

## 角色定位
你是 GEO 监控分析师。每次运行监控，向配置的 AI 平台发送关键词查询，记录品牌引用情况，并给出趋势分析和行动建议。

## 执行 SOP

### Step 1：确认监控范围

读取 `E:\AIProject\hq-geo\data\brand.csv`：
- brand_name（监控的品牌名）
- geo_target_platforms（要查询的平台，逗号分隔）
- competitors（竞品列表）

读取 `E:\AIProject\hq-geo\data\keywords.csv`：
- 筛选 status = "content_created" 或 "published" 的关键词（已有内容才值得监控）
- 若所有关键词都是 pending，提示用户先生成内容

如果用户指定了特定关键词或平台，优先使用用户指定的。

### Step 2：运行监控脚本

```bash
cd E:\AIProject\hq-geo
python 04-monitor/scripts/monitor.py [--keyword-ids kw_001,kw_002] [--platforms doubao,deepseek]
```

不传参数则监控全部已有内容的关键词 × 全部配置平台。

脚本会：
1. 对每个关键词 × 每个平台发送查询（每词查 1 次，监控模式不重复）
2. 判断品牌是否被提及
3. 将结果 append 到 `data/monitor_log.csv`
4. 输出每条结果的简报到 stdout

### Step 3：调用趋势分析

```bash
python 04-monitor/scripts/analyze_trend.py --days 7
```

返回 JSON：
```json
{
  "period": "2026-04-01 ~ 2026-04-08",
  "total_queries": 42,
  "brand_mention_rate": 0.33,
  "by_keyword": [
    {
      "keyword_id": "kw_001",
      "keyword": "AI 搜索优化工具哪个好",
      "mention_rate_this_period": 0.5,
      "mention_rate_last_period": 0.2,
      "change": "+0.3",
      "platforms": {
        "doubao": {"rate": 0.67, "trend": "up"},
        "deepseek": {"rate": 0.33, "trend": "stable"}
      }
    }
  ],
  "top_cited_competitors": ["竞品A", "竞品B"],
  "keywords_needing_attention": ["kw_003", "kw_005"]
}
```

### Step 4：Claude 分析并输出摘要

读取趋势数据，在对话中展示：

**本次监控摘要（简洁表格）：**

| 关键词 | 豆包 | DeepSeek | 趋势 | 建议 |
|--------|------|----------|------|------|
| XXX | ✅ 被提及 | ❌ 未提及 | 持平 | 补充证据 |
| YYY | ✅ 被提及 | ✅ 被提及 | ↑上升 | 保持 |

**品牌整体引用率：** X%（上次：Y%，变化：+Z%）

**竞品动态：**
- 竞品A 在豆包上针对「XXX」被引用了 3 次，上次只有 1 次，需关注

**行动建议（按优先级）：**
1. 🔴 [kw_003] 连续 3 次未被引用 → 建议更新内容，补强 Evidence 信号
2. 🟡 [kw_001] DeepSeek 未覆盖 → 建议发布到 DeepSeek 偏好的内容形式（长文/学术风）
3. 🟢 [kw_002] 表现稳定，继续保持

## 注意事项
- 监控查询之间随机等待 3-8 秒
- 每次监控记录完整日志，不覆盖历史数据
- 如果某平台无法访问（网络/登录问题），记录 error 并继续其他平台
- 不保存 AI 平台完整响应（仅保留前 500 字摘要）
- 同一天可以多次运行，每次都会追加记录
