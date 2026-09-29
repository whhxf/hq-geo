# Content Production Contracts

本能力包定义“选题之后必须交付什么”，将内容推理结果稳定地交给文章编辑器、图片生成器或外部视频制作系统。

- `ProductionBrief`：视频制作接口。
- `ArticleDraft`：文章成稿接口。
- `ImageBrief`：图片制作接口。**2026-09-29 起有自己的契约与流水线**，见
  `capabilities/image-production/contracts/image-brief.schema.json` 和 `skills/image-pipeline/`；
  本能力包只保留这个名字作为交付物清单的一项。
- `ChannelPackage`：具体发布渠道的适配结果。

所有交付物必须引用 `fact_refs`，并区分 `draft`、`blocked`、`ready_for_production`、`ready_for_review`、`ready_to_publish`。只有标题和选题不能进入任何 ready 状态。

