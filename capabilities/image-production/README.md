# Image Production

图片线。**强依赖 AI 生成——不做图片编辑。**

```
任务 ──→ image-brief.json ──┬──→ 选风格（看样选）
                            │
    参考图（可选）──→ 量色板 ─┴──→ 组装 prompt ──→ 模型一步出图 ──→ 验收
                        └────────────────────────────────────────↗
                              同一份色板，回测时拿来做预期
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
| 图上每句主张都要挂 `fact_ref` | 图上写「效率提升 300%」，正文里根本没这句 |
| 素材必须写权利状态 | 出事了说不清这张图哪来的 |
| `style_id` 必须在风格库里 | 拼错不报错，只是静默出一张没有风格的图 |
| `ready_for_production` 时不能有 blocked 的图 | 简报说可以出，实际有图出不来 |
| 有 `reference_images` 就必须写 `reference_instruction` | 模型把参考图当成待编辑对象，你拿到「改了一下的参考图」 |
| 参考图路径必须在项目根内，且文件真的在 | 越出项目根的图没有权利登记；文件不在要到出图时才发现，钱已经花了 |
| `palette_ref` 必须在，且是测量结果 | 静默不出色板，图和预期两样，只能靠人肉发现 |

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

`wan2.7-image-pro`（DashScope，异步 HTTP）。**密钥不进代码**：

1. `~/.config/hq-geo/image.json` 里写 `{"api_key": "sk-..."}`，或
2. 环境变量 `HQ_GEO_IMAGE_API_KEY`

**不读 Vidmix 的数据库。** 2026-09-29 定的：图片线和视频线是独立的两套，
读那边就是刚要去掉的耦合。

## 和另外两条线的关系

- **文章线**（`skills/article-pipeline/`）：八站，自建，已跑通。
- **视频线**：外发。hq-geo 出 `CreativeJob`，Vidmix 做，回 `ProductionReceipt`。
  协议在 `capabilities/creative-handoff/`。
- **中间要不要搭桥**（图生视频首帧、视频截帧做图），**图片线走通之后再说，现在不设计。**

## 风格库从哪来

2026-09-29 从 Vidmix 的 `generate_image` skill 搬来 14 套，**搬过来后归 hq-geo 所有**。
Vidmix 那边自己留一份给视频用，两边不自动同步。

`capabilities/content-production/styles/README.md` 说的「三条流水线共用风格机制」，
共用的是**机制**（看样选，不靠文字描述）；**特征集各是各的**——
文章线的特征是句长、节奏、人称，图片线的特征是色板、光线、构图、排版。
