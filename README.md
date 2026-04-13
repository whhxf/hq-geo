# HQ-GEO Engine

> Unix 哲学：文件夹即应用，对话即操作，CSV 即数据库，Markdown 即内容仓库。

## 快速开始

### 第一步：配置环境
```bash
cd E:\AIProject\hq-geo
pip install -r requirements.txt
playwright install chromium
cp .env.example .env   # 填入你的 API Key
```

### 第二步：填写品牌档案
直接编辑 `data/brand.csv`，或对 Claude 说：
> "帮我填写品牌档案"

### 第三步：开始对话
对 Claude 说任意一句：
- "帮我生成 GEO 关键词"
- "分析一下我们在豆包上的竞争情况"
- "针对「XXX」这个关键词写一篇 GEO 内容"
- "运行今天的监控"
- "生成本周 GEO 报告"

---

## 文件夹结构

```
hq-geo/
├── README.md
├── PRD.md                        ← 需求说明书
├── .env                          ← API Keys（不提交 git）
├── .env.example                  ← 环境变量模板
├── requirements.txt              ← Python 依赖
│
├── data/                         ← 统一数据层
│   ├── brand.csv                 ← 品牌档案（先填这个）
│   ├── keywords.csv              ← GEO 关键词库
│   ├── content.csv               ← 内容索引
│   ├── monitor_log.csv           ← 监控日志
│   └── competitors.csv           ← 竞品分析结果
│
├── 01-intent/                    ← 意图分析 & 关键词生成
│   ├── SKILL.md                  ← Claude 的执行 SOP
│   └── scripts/
│       └── save_keywords.py
│
├── 02-compete/                   ← 竞争分析
│   ├── SKILL.md
│   └── scripts/
│       ├── query_ai_platform.py
│       └── save_competitors.py
│
├── 03-content/                   ← 内容生成工厂
│   ├── SKILL.md
│   ├── templates/
│   │   ├── definition.md
│   │   ├── comparison.md
│   │   ├── howto.md
│   │   └── faq.md
│   ├── scripts/
│   │   ├── generate_schema.py
│   │   └── save_content.py
│   └── output/                   ← 生成的内容文件
│
├── 04-monitor/                   ← AI 平台引用监控
│   ├── SKILL.md
│   └── scripts/
│       ├── monitor.py
│       └── analyze_trend.py
│
└── 05-report/                    ← 报告生成
    ├── SKILL.md
    ├── scripts/
    │   └── generate_report.py
    └── output/                   ← 生成的报告文件
```

## 数据流

```
brand.csv（品牌档案）
    ↓ [01-intent]
keywords.csv（关键词矩阵）
    ↓ [02-compete]
competitors.csv（竞品引用分析）
    ↓ [03-content]
03-content/output/*.md（内容文件）+ content.csv（索引）
    ↓ [04-monitor]
monitor_log.csv（每日监控数据）
    ↓ [05-report]
05-report/output/report_*.md（周报/月报）
```

## 支持的监控平台（可配置）

在 `data/brand.csv` 的 `geo_target_platforms` 字段配置，逗号分隔：

| 平台标识 | 说明 |
|---------|------|
| `doubao` | 豆包（默认启用）|
| `deepseek` | DeepSeek（默认启用）|
| `chatgpt` | ChatGPT |
| `perplexity` | Perplexity |
| `gemini` | Gemini |

默认：`doubao,deepseek`
