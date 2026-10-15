# Image Production

图片线。**强依赖 AI 生成——不做图片编辑。**

```
任务 ──→ image-brief.json ──┬──→ 选风格（看样选）
                            │
    参考图（可选）──→ 量色板 ─┴──→ 组装 prompt ──→ 模型一步出图 ──→ 验收
                        └────────────────────────────────────────↗
                              同一份色板，回测时拿来做预期
    封面另加一步：cover_text 用真实文本渲染叠上去（A 方案），落 assets/composed/
```

## 这一线管什么

文章写错一句话，读者能追问出处。**图不行**——一张看起来像产品界面的生成图，
读者没有任何办法知道那是模型编的。所以图片线的事实纪律不能靠「写的时候注意」，
必须由字段强制。

`ImageBrief` 的每一格都在回答同一类问题：**这张图凭什么可以这么画。**

| 文件 | 作用 |
|---|---|
| `contracts/image-brief.schema.json` | 图片制作接口 |
| `styles/image-styles.json` | 14 套视觉风格（从 Vidmix 搬来，2026-09-29） |
| `scripts/validate_image_brief.py` | 简报校验器 |
| `scripts/generate_image.py` | 出图：组装 prompt → 调模型 → 存回项目 |
| `scripts/png_io.py` | PNG 读写，纯标准库（写只给测试用） |
| `scripts/color_math.py` | sRGB→OKLCH、CIEDE2000 ΔE |
| `scripts/measure_palette.py` | 从参考图量色板 |
| `scripts/verify_palette.py` | 回测：生成图的配色跟预期比 |
| `tests/test_image_brief.py` | 校验规则和 prompt 组装的单测 |
| `tests/test_palette.py` | 颜色数学、PNG 解码、取色、回测、参考吸收的单测 |
| `PRD-reference-absorption.md` | 参考吸收的设计文档（为什么这么做、边界在哪） |

**「有人愿意点」那半边在 `capabilities/image-appeal/`。** 那边有十四条吸引力判据、
像素测量器和执行者。两边共用一个契约、一份风格库——风格库的 `carrier` 字段
决定封面要不要底图，是两边唯一的接线点。

入口在 `skills/image-pipeline/SKILL.md`。

**零第三方依赖。** 这四个脚本只用标准库。PIL 在开发时被用作一次性
验证 oracle（和 `png_io` 逐像素对比过 61 张系统 PNG），**不出现在交付代码
和测试里**——否则「只用标准库」就成了一句只看目录的谎话。

## 校验器拦什么

**它拦的是「图冒充它没有的东西」。** 每条规则都对应一个真实的失败方式：

| 规则 | 不拦会怎样 |
|---|---|
| `subject_kind` 是产品界面/客户案例/真实记录时，`synthetic` 必须为 false | 生成图冒充真实产品，看图的人当真 |
| `synthetic` 必须显式写 | 生成图默默混进真实素材里，事后分不清 |
| 图上每句**事实主张**都要挂 `fact_ref` | 图上写「效率提升 300%」，正文里根本没这句 |
| 封面必须有 `cover_text`，且写清 `source_title` | 封面是一张无字的图，在一屏几十条的流里没人看得见 |
| `cover_text` 必须挂 `source_title`，不挂 `fact_ref` | 两类文字混在一起，封面要么被迫无字，要么变成绕过事实纪律的后门 |
| `cover_text` 与 `claims_on_image` 不许出现同一句话 | 同一句话既当题目又当事实主张，「挂没挂 `fact_ref`」这个信号就失真了 |
| `cover_text.layout` 必须在风格库出现过的位置里 | 文案压住主体，封面自己把自己废掉 |
| 有封面文案时，`ready` 必须带 `appeal_review` 且九项全 `pass` | 封面能出图、能发，却没有任何人问过它「能不能让人停下来」 |
| `appeal_review.reviewed_by` 必须与 `author` 不同，且必须写 `evidence` | 写简报的人自己判吸引力——2026-10-08 的事故就是这样发生的 |
| 多张图必须有 `deck` 四格 | 序号、单一风格、封面隔离、末页落点四条组层面判据无处落地 |
| `base_image` 必须在项目根内；`status=generated` 时文件必须真的在 | 路径拼错或忘了生成，封面渲染成一块空白底，而简报看上去是合规的 |
| 素材必须写权利状态 | 出事了说不清这张图哪来的 |
| `style_id` 必须在风格库里 | 拼错不报错，只是静默出一张没有风格的图 |
| `ready_for_production` 时不能有 blocked 的图 | 简报说可以出，实际有图出不来 |
| 有 `reference_images` 就必须写 `reference_instruction` | 模型把参考图当待编辑对象，你拿到「改了一下的参考图」 |
| 参考图路径必须在项目根内，且文件真的在 | 越出项目根的图没有权利登记；文件不在要到出图时才发现，钱已经花了 |
| `palette_ref` 必须在，且是测量结果 | 静默不出色板，图和预期两样，只能靠人肉发现 |

**数值判据不在这里。** 这个校验器守**结构与登记**；阈值类判据（封面标题长度、
视觉复杂度、风格漂移、序号、落点、文案机器化）住在
`capabilities/image-appeal/rules/appeal-rules.json`，由 `check_appeal.py` 执行。
`validate_image_brief.py` 把它调起来，**不重写它的数字**——一个方法只保留一个真源。

## 封面文字与吸引力（2026-10-07 补）

**两类文字分开走。** `claims_on_image` 是**事实主张**，必须挂 `fact_ref`——
这一半本来就有，是对的。`cover_text` 是**封面文案**（文章或商品的题目与钩子），
它不承诺效果，所以挂 `source_title`。

分开之前只有一条路：所有图上文字都得挂事实。封面标题是文章的题目、不是事实主张，
挂不上 `fact_ref`，于是**封面被迫无文字**。而风格库的 `sample` 里本来就定义了
`headline` / `kicker` / `meta` / `layout`——**风格支持封面文字，是契约把路堵了。**

**吸引力分成两半，两半都要（2026-10-08 补）。**

**机器判的那一半**住在 `capabilities/image-appeal/`——十四条判据、像素测量器、
执行者 `check_appeal.py`。它判的是能数出来的事：封面标题长度、封面底图复杂度、
封面与内页的隔离、全套单一风格、序号、单页要点条数、末页落点、文案机器化模式。

**人判的那一半**是 `appeal_review`：九项逐项给 `pass` / `fail` / `unknown`，
**九项全 `pass` 才允许简报进 `ready`**。前四项是 2026-10-07 定的同向与可读；
后五项是 2026-10-08 补的心理触发器（信息缺口 / 意外点 / 情绪唤醒 / 信息价值 / 社交货币），
每条对应 appeal-rules.json 里一条有来源的人判规则。

**复核人必须独立于作者。** `reviewed_by` 不能等于顶层 `author`，并且要写清
`evidence`——实际看过什么。这一条是 2026-10-08 加上的，因为出过事故：
写简报的 Agent 自己把四项全填了 `pass`，十张图交付，Conan 看完说「比较素」。
**登记了，质量没守住。**

**文案怎么上封面：A 方案。** 底图模型生成，文字用真实文本渲染叠上去——
改字不用重出图。**排版环节还没进系统**（合成脚本要依赖 PIL，系统根只用标准库），
当前由外部工具合成，产物落项目根 `assets/composed/<brief-id>/`，
与模型直出的 `assets/generated/` 分开。

## 参考吸收：从喜欢的图里量出风格

用户说不清自己喜欢什么，但能给出喜欢的图。**不让他描述**——让他把图放进项目根
`assets/reference/`，然后量：

```bash
python3 capabilities/image-production/scripts/measure_palette.py \
  项目根/assets/reference/图.png -o 项目根/assets/reference/palette.json
```

量出来的色板是数字。同一份文件喂两个下游，**中间不转译**（转译就是信息损失）：

| 下游 | 用它的什么 |
|---|---|
| `generate_image.py` | `dashscope_color_palette` → 万相的 `color_palette` 参数 |
| `verify_palette.py` | 作为回测的预期色板 |
| 将来的 `image-styles.json` | `role` + `hex` + `oklch`（**不自动写，由人决定**） |

三件事必须分清：

- **`hex` / `oklch` / `coverage` 是精确测量；`role` 是启发式猜测。**
  一张纯蓝渐变里没有文字色，脚本仍会把某个蓝标成 `text`。
  标签是猜的，颜色不是——所以 role 只用来让色板可读，不能当证据。
- **`ΔE76` 和 `ΔE00` 不是同一把尺。** 同一对色值上能差 71%。
  外部文档里的阈值**不能直接抄进来**，门禁会静默地松掉或紧掉。
  `color_math.delta_e_76()` 留着就是为了翻译外部数字。
- **回测只测颜色和面积。** 测不了「这张图配不配得上那句话」，
  构图、质感、有没有混进不该有的东西仍然归人。回测 PASS 不等于可以发。
  而且阈值**还没拿真实出图校准**（`thresholds.calibrated: false`）。

算法：5 位/通道量化成桶（桶内累计真实 RGB 均值）→ 桶上跑加权 k-means
（距离在 OKLab 里算）→ 按 ΔE00 合并近似中心 → 按覆盖率与明暗彩度分 role。
**全程确定性**，同输入同字节，所以能做黄金文件回归。

设计取舍、边界、以及为什么不直接用现成的开源方案，见
`PRD-reference-absorption.md`。

## 出图模型

`prompt.base_image_prefix` 描述不含文字的底图风格；存在时由生成器优先采用。
`prompt.prefix` 可保留完整成品的风格描述，但不能把“生成标题”带进底图请求。
文字由排版引擎渲染；底图请求的负面条件明确排除文字、字母和数字。

生成入口与简报校验分开守门：即使直接调用 `generate_image.py`，也必须拒绝
`synthetic != true`、真实界面/人物/案例/对话题材，以及 blocked/rejected 交付物。
真实素材走排版引擎合成，不送进模型重画。

`wan2.7-image-pro`（DashScope，异步 HTTP）。**密钥不进代码**：

1. `~/.config/hq-geo/image.json` 里写 `{"api_key": "sk-..."}`，或
2. 环境变量 `HQ_GEO_IMAGE_API_KEY`

**不读 Vidmix 的数据库。** 2026-09-29 定的：图片线和视频线是独立的两套，
读那边就是刚要去掉的耦合。

## 和另外两条线的关系

- **文章线**（`skills/article-pipeline/`）：八站，自建，已跑通。
- **视频线**（`skills/video-pipeline/`）：六站，**2026-10-10 起自建**。
  此前外发 Vidmix 的 `CreativeJob → ProductionReceipt` 协议已删除。
- **中间要不要搭桥**（图生视频首帧、视频截帧做图），**图片线走通之后再说，现在不设计。**

## 风格库从哪来

2026-09-29 从 Vidmix 的 `generate_image` skill 搬来 14 套，**搬过来后归 hq-geo 所有**。
Vidmix 那边自己留一份给视频用，两边不自动同步。

`capabilities/content-production/styles/README.md` 说的「三条流水线共用风格机制」，
共用的是**机制**（看样选，不靠文字描述）；**特征集各是各的**——
文章线的特征是句长、节奏、人称，图片线的特征是色板、光线、构图、排版。
