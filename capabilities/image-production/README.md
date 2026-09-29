# Image Production

图片线。**强依赖 AI 生成——不做图片编辑。**

```
任务 ──→ image-brief.json ──┬──→ 选风格（看样选）
                            └──→ 组装 prompt ──→ 模型一步出图 ──→ 验收
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
| `tests/test_image_brief.py` | 校验规则和 prompt 组装的单测 |

入口在 `skills/image-pipeline/SKILL.md`。

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
