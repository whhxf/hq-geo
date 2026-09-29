# 选题记录

**选题不是想法。** 想法可以有一百个，选题是能答上五问的那几个。

```
data/ideas/          想法。想到就记，不设门槛
      ↓  关键词研究 + 和用户讨论
topics/<idea>/       选题。答不上五问的进不来
      ↓  选定
tasks/               生产。做到哪了在这看
```

这条分界线是**这个能力包存在的全部理由**。

## 五问是准入门槛

| # | 字段 | 问的是 |
|---|---|---|
| 1 | `audience_and_scene` | 谁在什么场景下遇到什么问题？ |
| 2 | `failing_explanation` | 现有解释或做法哪里失效？ |
| 3 | `own_judgment` | 你有什么不同判断或可展示证据？ |
| 4 | `content_promise` | 内容承诺是什么，看完能得到什么？ |
| 5 | `falsification` | **这个承诺如何被证伪？** |

**答不上第 5 问的不是选题，是想法。**

第 5 问是唯一一条能证伪自己的问题。答不上来，说明这条内容做出来**没人能判断它对不对**——
那它写得多顺都是自说自话。这一问别人替你答不了，所以它是选题里唯一真正属于你的部分。

**五问要么全答、要么全空。** 答一半的由校验器拦下：

> 半答比不答更危险——看起来像验证过了。

## 三态

| state | 意思 | 前提 |
|---|---|---|
| `candidate` | 备选，还没定 | 无 |
| `selected` | 选定要做 | **五问必须全答** |
| `dropped` | 放弃 | 无 |

**只到这里。** `stage`、`progress`、`next_action` 这些字段属于生产进度，按 `AGENTS.md` 第 31 行
「四层各自独立成文件」，它们在 `tasks/` 里。选题记录只管**做不做**，不管**做到哪了**。

混进来会怎样：选题记录变成第二个任务表，两边各说各话，谁也不知道哪个是真的。
校验器见到这五个字段直接报错。

## 三种来源

| `source.kind` | 从哪来 | 必须写 | 限制 |
|---|---|---|---|
| `research` | 关键词研究 + 讨论 | `research_ref`（校验器查文件存在）、`cluster_ref` | `evidence_refs` 非空 |
| `direct` | 你自己拍板 | `confirmed_at` | `evidence_refs` 非空 |
| `imported` | 历史导入，没经过调研和讨论 | `imported_from`、`imported_at` | **五问必须全空，state 只能是 `candidate`** |

`imported` 的限制是硬的：一条历史选题如果答了五问，说明它已经被讨论过——
那它不该是 `imported`，把 `kind` 改掉。**来源标签和实际经过的流程必须对得上。**

## 校验器

```bash
python3 capabilities/topic-registry/scripts/validate_topics.py --project <项目根>
```

| 拦的 | 为什么 |
|---|---|
| **想法冒充选题** | 五问没答全却进了 `selected` |
| **半答** | 五问答了一半 |
| **没有出处的选题** | `research` / `direct` 没有 `evidence_refs`，或 `research_ref` 指向不存在的文件 |
| **混层** | 出现 `stage` / `progress` / `next_action` / `updated_at` / `status` |

空项目 PASS——没有选题不是错误。

## 迁移

```bash
python3 capabilities/topic-registry/scripts/migrate_v1.py --project <项目根>          # 只看
python3 capabilities/topic-registry/scripts/migrate_v1.py --project <项目根> --yes    # 写
```

v1 把选题和生产进度混在一个文件里。迁移删掉进度字段（原值摘要进 `note`），
全部转成 `state: candidate` + `source.kind: imported`。

**为什么全部是 `candidate`**：五问一条都没答。**已经产出母脚本的也一样**——
推进得深不等于验证过。要提升状态得补答五问，不能靠迁移脚本替它升。

写盘前自动备份 `<name>.v1.bak.json`。校验器跳过 `.bak.json`——备份留作回溯，不是现行数据。

## 契约

`contracts/topic.schema.json`，`schema_version: 2`。落盘在项目根 `topics/<idea>/topics.json`。

**一个创意一个文件。** 一个文件里放多个创意的选题，`selected_topic_id` 就没法表达
「这个创意的哪一条定了」。

## 三条不做

1. **不产出选题。** 系统给证据和判断，**选定哪条是用户的决定**。校验器只拦不合规的，不推荐好的。
2. **不跟踪生产。** 做到哪了看 `tasks/`。
3. **不管研究。** 需求簇和证据在 `capabilities/keyword-research/`，这里只登记结果。
