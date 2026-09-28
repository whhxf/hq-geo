# 事实包数据契约

校验器以以下字段为稳定契约：

- 包身份：`schema_version`、`id`、`entity_type`、`slug`、`name`
- 所属关系：`belongs_to`
- 完整度：`required_slots`，每项包含 `id`、`label`、`kind`、`status` 和关联事实/资产
- 防遗漏：`protected_fact_ids`
- 来源：`sources`
- 媒体：`media_assets`
- 原子事实：`facts.jsonl`

状态枚举：

- 事实：`verified`、`needs_confirmation`、`conflict`、`expired`、`prohibited_claim`
- 槽位/媒体：`present`、`partial`、`missing`
- 证据类型：`official_source`、`direct_evidence`、`owner_statement`、`company_claim`、`customer_report`、`internal_definition`、`inference`、`unknown`

`pending_questions` 保存 Agent 需要在对话中追问的事实缺口。已解决问题不能删除，只更新为 `resolved` 并关联生成的事实或媒体 ID。
