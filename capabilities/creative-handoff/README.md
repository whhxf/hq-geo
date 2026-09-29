# Creative Handoff

HQ Content Engine 与本地媒体制作系统之间的文件协议。

**这是视频通道。** 2026-09-29 定：Vidmix 收窄为视频创作，图片线由 hq-geo 自建（见 `BACKLOG.md`）。
图片不走这里——`CreativeJob` 的形状是视频的（必填含 `scenes`、`production_units`、逐镜头 `spoken`）。

## 职责

- HQ 生成不可变的 `CreativeJob`，保存内容意图、事实边界、镜头和验收要求。
- Vidmix 导入任务并管理策略选择、生成过程和成品。
- Vidmix 输出自包含的 `ProductionReceipt`；HQ 只读取回执，不查询 Vidmix 数据库。
- 同一 `job_id + revision` 不覆盖。返工使用更高 revision。

## 命令

```bash
python3 capabilities/creative-handoff/scripts/handoff.py validate-job path/to/creative-job.json
python3 capabilities/creative-handoff/scripts/handoff.py validate-receipt path/to/production-receipt.json
python3 capabilities/creative-handoff/scripts/handoff.py sync-receipt path/to/production-receipt.json
```

`sync-receipt` 将可回读索引写入**项目根**的 `assets/generated/<content-id>/manifest.json`。媒体文件仍由 Vidmix 管理，manifest 使用绝对路径引用。
