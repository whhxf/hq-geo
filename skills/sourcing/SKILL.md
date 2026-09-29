---
name: sourcing
description: 把一个说不清的想法或一个主题，变成可执行的 production-brief、事实包条目和选题——创作链路的第一环。用户说「我有个想法」「帮我问出来」「采访我」「我想做一条关于……的视频/图/文章」但还没说清要什么时使用；已经给出完整 brief 或直接要求写正文时不要触发。
---

# 取材

## 目的

把脑子里的东西或外面的材料取回来，立起一份能推动下一步的 brief。
**不写成稿**——文章走 `article-pipeline` 八站，视频走 `creative-handoff`，图片走 `image-pipeline` 五站。

```
想法 / 主题 ──取材──→ production-brief.json ──┬──→ 文章：八站
                                              ├──→ 图片：image-pipeline 五站
                                              └──→ 视频：creative-job → Vidmix
```

## 开始前

完整读取：

- `capabilities/sourcing/interview-method.md`
- `capabilities/sourcing/research-method.md`
- `capabilities/content-production/contracts/production-brief.schema.json`

读取项目根的 `topics/<idea>/`、`facts/`、`content/briefs/`——**先看这个想法是不是已经有 brief 或选题**，
有就接着填，不新建第二份。

## 第一步：问走哪条路

**启动时问一次，不替用户选**（2026-09-28 Conan 定的：取材是可选的）：

> 「这个主题，你手上有独家经验或判断要讲（访谈），还是让我去找线上资料和第三方证据（检索）？」

| 用户选 | 走哪条 |
|---|---|
| 有独家材料 | **访谈路径** —— 按 `interview-method.md` 连续追问 |
| 通用主题 | **检索路径** —— 按 `research-method.md` 找外部证据 |
| 「都有」/ 说不清 | **两条并用** —— 访谈填只有他知道的格，检索填外部可查的格 |

用户说不清时可以**从他刚才那句话推断**，但要说明你的判断再开始：

> 「你提到『客户最常问认证』——这像是你自己的观察。我先按访谈走，从这件事问起。」

## 第二步：先把空格列出来

不管走哪条路，**先列出这份 brief 还缺哪几格**（对照 `production-brief.schema.json` 的
`objective`、`audience`、`core_thesis`、`script[]`、`required_assets[]`、`prohibited_claims[]`）。

**空格清单是给你自己看的，不是给用户的问卷。** 一次只问一个，问完再决定下一个。

列不出空格说明还不知道要做什么——先问一个能定方向的问题：

> 「这条东西做出来，你最想谁看到、看完之后他会做什么？」

## 第三步：按路径执行

**访谈路径**：五要素锁定 → 一次一问 → 说不清时换四个入口 → 原话逐轮保存 → 收束两问。
判据全在 `interview-method.md`。

**检索路径**：从空格出发 → 一手来源优先 → 三级定级 → 写全来源和范围。
判据全在 `research-method.md`。

## 第四步：落盘

**写盘前先把要写的东西给用户看一遍**——事实包是 protected 的，写进去会影响后续所有内容。

| 挖到什么 | 落到哪 |
|---|---|
| brief 的字段 | `content/briefs/<idea>/<topic>/production-brief.json` |
| 用户口述的四类事实 | 事实包，走 `capture_fact.py`（**先建 pending question**）|
| 外部查证的事实 | 事实包 `facts.jsonl`，`evidence_type` 按三级定 |
| 原话 / 检索记录 | `research/interviews/<date>-<slug>.md`、`research/raw/` |
| 选题 | `topics/<idea>/topics.json` |

**`capture_fact.py` 要求问题先存在**：

```bash
# 1. 在 manifest.json 的 pending_questions 里加一条（status: pending, answer_policy: owner_statement）
# 2. 再捕获
python3 capabilities/fact-packs/scripts/capture_fact.py \
  --pack facts/<pack> --question-id <q-id> --fact-id <new-id> \
  --claim "提炼后的原子陈述" --answer "用户原话，一字不改" \
  --category founder_viewpoint
```

**brief 的 `status` 按实际情况写**：格子没填满是 `draft`，有硬缺口是 `blocked`。
**不要为了让流程往下走就标 `ready_for_production`**——素材和界面没到位就是 `blocked`。

## 第五步：交出去

收束时给用户三样：

1. **这份 brief 现在能做什么**——还缺什么、缺的会影响什么
2. **旁支清单**——问「现在继续哪一条，还是先留到以后」
3. **下一步**——文章进 `article-pipeline`；图/视频走 `creative-handoff` 生成 creative-job

## 边界

- **不写成稿。** 写完 brief 就停，正文是下游的事。
- **不替用户下结论。** 说不清的保留为未知，**不提供候选答案让他认领**（宪法第 5 条的对话版）。
- **不把外部效果升级成事实。** 用户口述的效果是 `company_claim`，要写进内容得先有外部证据。
- **不重复建包。** 已经有 brief 或选题的，接着填，不新建。
