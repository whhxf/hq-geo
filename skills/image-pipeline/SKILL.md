---
name: image-pipeline
description: 图片流水线——把图片简报变成真实的图。用户要生成配图、封面图、小红书图、海报、产品场景图时使用；要改一张已有的图（局部修改、换背景）时不要触发，那是编辑不是生成。
---

# 图片流水线

## 目的

从一条任务出发，产出一组**能说清自己是什么**的图。

**这条线强依赖 AI 生成，不做图片编辑。** 没有图层、没有涂抹、没有局部修改——
做的是把「要什么」说清楚，组装 prompt，调模型一步出图。
用户要改一张已有的图，直说这条线不干这个。

## 开始前

完整读取：

- `capabilities/image-production/contracts/image-brief.schema.json`
- `capabilities/image-production/styles/image-styles.json`——**不要凭记忆背风格清单**，以文件为准
- `capabilities/content-production/styles/README.md`——风格「看样选」的机制

读项目根的 `tasks/<id>.md`、`facts/`、`topics/`。图片简报住在
`content/briefs/<idea>/<topic>/image-brief.json`，和视频简报同一个位置。

**先看这个选题是不是已经有图片简报**，有就接着改，不新建第二份。

---

## 五站

### 站 1 · 读任务，查事实

从任务单里读出：这条内容对谁讲、核心判断是什么、要发在哪。

**平台决定尺寸，用途决定构图，核心判断决定画面上能出现什么。** 三样缺一样就不要往下走。

查事实包：这张图要表达的东西，有没有 `fact_refs` 撑得住？
撑不住的先回站 2 补料，不要先画出来再说——**画出来之后你会舍不得删**。

### 站 2 · 写图片简报

按 schema 写 `image-brief.json`。逐张图填：

| 字段 | 要回答的问题 |
|---|---|
| `role` | 这张图在内容里干什么用（封面 / 配图 / 步骤示意 / 对比） |
| `size` | 发在哪，什么尺寸 |
| `subject` | 画面里有什么。**写具体的物和光，不写形容词**——「米白色桌面、柔和侧光、浅阴影」，不是「高级感」 |
| `subject_kind` | 这张图画的是**概念**，还是**声称真实存在的东西** |
| `synthetic` | 是不是模型生成的。**必须显式写** |
| `source_assets` | 素材哪来的，权利状态 |
| `claims_on_image` | 图上出现的每一句主张，逐条挂 `fact_ref` |
| `status` | 这张图能不能出 |

**`subject_kind` 是这份简报最重要的一格。** 它决定这张图能不能由模型生成：

- `concept`——概念图、氛围图、示意。模型生成没问题。
- `product_ui` / `customer_case` / `real_conversation` / `real_person`——**声称真实存在的东西。**
  这四类不能生成。模型画出来的界面按钮位置、字段名全是编的，看图的人会以为那是真的产品。

用户说「画一张我们的产品界面」时，**不要直接画**，告诉他：界面要真截图，模型会编；
要的是概念图的话，改 `subject_kind` 为 `concept`，画面上就不出现具体界面。

**图上不要写字，除非它能挂上事实。** 写进 `claims_on_image` 的每一句都要有 `fact_ref`——
图上写的字和正文一样要能被追问出处。挂不上事实的那句话，从图上拿掉。

### 站 3 · 选风格

**风格靠看，不靠读。** 不要凭风格名推荐，不要跳过预览直接生成。

从 `image-styles.json` 里按 `platforms` 和 `best_for` 筛出 3 个候选，
用每个风格自己的 `sample` 字段生成真实样张，并排给用户看。用户选完写回每张图的 `style_id`。

**一套图共用一个 `style_id`。** 风格漂移（同一组图里有的米白有的深色）是成套图最明显的破绽。

用户对某张图有特殊要求时，改的是 `subject` 和 `intent`，**不是换风格**。

### 站 4 · 出图

先 dry-run 看组装出来的 prompt：

```bash
python3 capabilities/image-production/scripts/generate_image.py \
  --brief <项目根>/content/briefs/<idea>/<topic>/image-brief.json --dry-run
```

**把 prompt 念给用户听一遍再出图。** 出图要花钱，而 prompt 里写错一个词，
四张图一起错——先看后做比先做后改便宜。

确认后去掉 `--dry-run` 出图。图落在项目根 `assets/generated/<brief-id>/`，
回执写在同目录的 `manifest.json`。

### 站 5 · 验收

**机器检查 + 人看，两道都要，不能互相替代。**

机器能查的（跑校验器）：

```bash
python3 capabilities/image-production/scripts/validate_image_brief.py
```

- 尺寸和张数对不对
- 该标 `synthetic` 的标了没有
- `claims_on_image` 挂上事实没有
- 素材权利状态写全没有

机器**查不了**的，必须自己看：

- 图上的字有没有糊、有没有错别字、有没有多出没要求的字
- 画面里有没有混进不该有的东西（别人的 logo、真实人脸、错误的品牌色）
- 这张图**配不配得上那句话**——图好看但和核心判断无关，是废图

验收结论写回任务单的 `## 交付` 区块。**生成的图 `synthetic=true`，
不能当产品界面、客户案例或真实记录用**，交付时要写明。

---

## 边界

- **不做图片编辑。** 局部修改、换背景、涂抹——直说这条线不干这个。
- **不做视频。** 视频走 `capabilities/creative-handoff/`，是另一条线，中间没有桥。
- **不自动发布。** 出图和预览是内部动作，发到平台要用户明确授权。
- **不出带文字的图去挂无法证实的主张。** 这是本线的硬线，和文章线同源。
- **不绕过 dry-run。** 用户明确说「直接出」才跳过，跳过时说明会花几张的钱。
