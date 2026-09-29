# 取材

**创作链路的第一环**：把一个想法或一个主题，变成能推动下一步的东西——
`production-brief.json`、事实包条目、选题。

```
想法 / 主题 ──取材──→ production-brief.json ──┬──→ 文章：article-pipeline 八站
                                              ├──→ 图片：image-pipeline 五站
                                              └──→ 视频：creative-job → Vidmix
```

## 两条路径，由用户选

2026-09-28 Conan 定的：**「并不是每一次都要访谈，这是可以选的。」**

| | 访谈路径 | 检索路径 |
|---|---|---|
| 材料从哪来 | 用户脑子里已有的经验和判断 | 线上资料、第三方证据 |
| 怎么取 | 连续追问 | 检索 + 核验 |
| 落成什么事实 | `owner_statement`（只能验证四类 owner 事实）| `official_source` / `direct_evidence` |
| 适用 | 有独家经验、内部判断、亲历故事要讲 | 通用主题、需要外部数据和第三方证据 |
| 判据文档 | `interview-method.md` | `research-method.md` |

**启动时问一次**，不替用户选。只有用户知道这个主题他手上有没有独家材料。

两条路径可以并用：访谈挖到「我们客户最常问的是认证」，
检索去查「这个行业的认证要求是什么」——**同一个 brief，两路填不同的格**。

## 为什么要有这一环

系统原来只有**补料**——站 2 遇到事实缺口，问一个具体问题。那是**被动**的：
问题由缺口清单产生，问的是「发布渠道定不定」这类事实型问题。第一篇文章的四个缺口全是事实型。

取材补的是另一半：**主动**。用户说「我想做一条关于展会视频画册的东西」，
brief 的每一格都是空的，而用户自己也说不清要什么。

**它填的是已有的空位，不是新造一层。** `content/briefs/` 和 `production-brief.schema.json`
早就在系统里，项目里已经出现过填到一半的 brief，那份 brief 自己的 README 里写着：

> 「你的下一次回答会先进入视频画册事实包，再回填 `evidence-list` 段落。」

那句话描述的正是取材——只是之前没有哪份文档规定「怎么问出来」。

## 产物去向

取材**不产出成稿**。按挖到的东西分四路：

| 挖到什么 | 落到哪 | 用什么 |
|---|---|---|
| brief 的字段 | `content/briefs/<idea>/<topic>/production-brief.json` | 对 `production-brief.schema.json` 手写 |
| 用户口述的事实 | 事实包 `facts.jsonl` | `capture_fact.py`（需先有 pending question）|
| 外部查证的事实 | 事实包 `facts.jsonl` | 手写，`evidence_type` 按来源定 |
| 原话 / 检索记录 | `research/interviews/`、`research/raw/` | 逐轮保存 |
| 选题 | `topics/<idea>/topics.json` | 复用现有 Topic 格式 |

**原话必须留。** 它是三样东西的来源：事实条目的原始证据、Gate E 的作者语料、
以及以后回看「当时是怎么想的」。

## 一条硬线：什么能变成 verified 事实

事实包校验器已经把这条线写成了代码，取材必须遵守：

- **`inference` 和 `unknown` 不能是 `verified`**——模型推断出来的东西不许进事实包当事实
- **`owner_statement` 只能验证四类**：`founder_viewpoint`、`firsthand_experience`、
  `internal_process`、`product_intent`——用户口述的「我们客户用了效果很好」
  **不能**变成一个 verified 的 case 事实，它只能是 `company_claim` 或 `customer_report`
- 用户答不出来、外面也查不到的，**保留为未知**，不提供候选答案让他认领

这不是取材自己定的规矩，是宪法第 5 条（缺料停机，不许模型代填）在创作前端的样子。

## 边界

- **不写成稿**。文章走八站，视频走 creative-handoff，图片走 image-pipeline 五站。取材只管把材料取回来、把 brief 立起来。
- **不替用户下结论**。用户说不清的，追问；追问也说不清的，记成未知。
- **不把外部效果升级成事实**。检索到的第三方评价要标来源和强度，不能和官方来源混为一谈。

## 文件

| 文件 | 作用 |
|---|---|
| `interview-method.md` | 访谈路径：怎么问、什么时候换问法、什么时候停 |
| `research-method.md` | 检索路径：找什么、从哪找、怎么分级落盘 |
| `../../skills/sourcing/SKILL.md` | 入口：什么时候启动、先问什么、怎么分派 |
