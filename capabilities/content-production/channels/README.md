# 渠道契约

渠道是**产物落盘的位置**，也是**发布前要过的规则**。`content/packages/<channel>/` 里的 `<channel>`
必须是这里登记过的 id。

**渠道分两类，走的路不一样：**

| 类型 | 是什么 | 产物 | 规则真源 |
|---|---|---|---|
| 内容渠道 | 视频号 / 抖音 / 小红书 / 自有博客 / 新闻媒体 | 母内容 + 各渠道版本（`article.md` / `copy.md`） | `00-meta/content-engine/03-platform-hard-rules.md` |
| 交易渠道 | 闲鱼 | 商品发布包（`copy.md` + 封面/内页简报 + 发布复核记录） | 本目录 `xianyu.md` |

**为什么分开：** 内容渠道回答「怎么让人看到并相信」，交易渠道回答「怎么把商品描述准确并促成交易」。
闲鱼是交易渠道——它不默认加载 GEO、FAQ、Schema 或关键词密度。把内容平台的做法套上去，
只会让商品页变成一篇没人看的软文。

## 接口

每个 `channels/<id>.md` 的 front matter 是机器读的，正文是给人读的：

```markdown
---
channel: <kebab-case id>
name: <显示名>
kind: content | marketplace_listing
deliverable: channel_package
rules_source: <规则文件路径，或当前发布入口>
status: verified | partial | unverified
verified_at: YYYY-MM-DD
review_after: YYYY-MM-DD
---
```

| 字段 | 说明 |
|---|---|
| `channel` | 落盘目录名。`content/packages/<channel>/` 必须用这个值 |
| `kind` | `content`（内容渠道）或 `marketplace_listing`（交易渠道） |
| `status` | `verified` 跑过真实发布；`partial` 结构已定但规则未全核验；`unverified` 只登记了入口 |
| `verified_at` / `review_after` | 上次核验 / 下次复核。平台会改版，**过期即视为未知** |

## 现有的渠道

**内容渠道**（视频号 / 抖音 / 小红书 / 自有博客 / 新闻媒体）：硬规则在
`00-meta/content-engine/03-platform-hard-rules.md`，产物是母内容与各渠道版本，
由 `skills/article-pipeline/SKILL.md` 和 `skills/content-orchestrator/SKILL.md` 处理，
不在本目录逐条登记。

**交易渠道：**

| channel | 平台 | 状态 | 契约 |
|---|---|---|---|
| `xianyu` | 闲鱼 | partial | [`xianyu.md`](./xianyu.md) |

**交易渠道不写「待建」空壳。** 下一个渠道由真实需求触发，不由蓝图触发——写一个空壳文件，
下次翻到会以为已经有了。

## 硬线

- **规则未知时阻止 `ready_to_publish`。** 未知不是「大概可以」，是「不许发」——发布包只能停在 `prepared`。
- **不虚构。** 销量、收入、评价、用户经验、版权授权一律不得编造。
- **AI 标识、版权链、类目资质逐项核验**，不得以「同行都这么发」代替。
- **公开发布、改价、删除和广告花费属外部状态变更**，必须由用户明确授权。
