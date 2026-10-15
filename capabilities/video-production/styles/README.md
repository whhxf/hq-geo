# 视频风格库

**视频线此前没有风格层。** 2026-10-10 建。

此前视频风格由 Vidmix 外部管。2026-10-10 Conan 定暂时放弃 Vidmix，
风格层收回 hq-geo 自建。

## 文件

| 文件 | 是什么 | 谁改 |
|---|---|---|
| `video-styles.json` | 事实：风格清单、来源、执行方式、依赖、成本 | 加风格时改 |
| `style-map.json` | 判断：什么选题配什么风格 | 判断变了就改 |
| `build_previews.py` | 生成器：从样片切示意图 | 来源或网格变了才改 |
| `previews/` | 产物：每风格一张示意图，文件名等于风格 id | 跑生成器产出 |
| `previews-src/` | 上游拿不到时的备用拼图，3 张 | 只在重生成拼图时改 |
| `gallery.html` | 视图：并排看，人工选 | 跑生成器产出 |

**两个 JSON 是真源，HTML 是视图。** 改完数据跑：

```sh
python3 capabilities/video-production/styles/build_gallery.py
```

改完示意图来源跑：

```sh
python3 capabilities/video-production/styles/build_previews.py
```

## 示意图

**为什么有这一层**：风格靠看，不靠读。2026-10-10 前 gallery 只有文字，
人没法从视觉上选。现在每张卡片顶上放一张示意图。

**44 条在库，全部有图。** 卡片不出现「无示意图」。
被屏蔽的 32 条也有图，只是不上页面，见下节「屏蔽」。

### 六成来自上游样片

| 来源 | 原图 | 切法 | 覆盖 |
|---|---|---|---|
| huashu | `assets/全风格总览.jpg`（6×6 拼图） | 按网格切 35 格 | 35 段艺术风格 |
| huashu | `assets/动画语法/*_总览.jpg` | 取最左一个镜头 | 8 个语法 |
| huashu | `assets/角色/花叔形象_对比.jpg` | 整张 | `g-y6` 讲解员（已屏蔽） |
| lanshu | `explainer/gallery/nine-styles-kv-cache.jpg`（3×3 拼图） | 按网格切 9 格 | V1–V9 |
| geeklee | `examples/scene-01-monkey-mountain.png` | 整张 | 白板 |

### 两成来自本地拼图

handdrawn 的 21 条和 `presenter-digital-human`（已屏蔽）用 `previews-src/` 里的三张拼图切。
**这三张是 AI 生成的示意，不是上游样片。** 风格由提示词描述，不是真引擎输出。

上游真图拿不到。handdrawn 把样图放在 `gentle-starburst-99bd99.netlify.app`，
仓库里只有 `.privacy.json` 和 `.provenance.json`。
2026-10-10 实测该站整站返回 503，连根路径也是。

脚本的处理顺序：

1. 先按清单下载真图，逐个核 `sha256`。
2. 任何一个核不过，整体退回本地拼图。
3. **不用别的图冒充真图。**

上游恢复后重跑脚本，会自动换回真图。

### 网格不是等分的

AI 给的拼图格子不齐。边界是实测出来的，写在 `build_previews.py` 的
`HANDDRAWN_SHEETS` 里，不是按 1/3 猜的。

### 占多大

| 目录 | 内容 | 体积 |
|---|---|---|
| `previews/` | 76 张（含被屏蔽的 32 张），宽 640 | 4.2MB |
| `previews-src/` | 3 张拼图，1536 见方 | 2.2MB |

**本目录存图是对「不复制仓库内容」的例外。** 存的是切好的缩略图，
不是仓库内容。理由：gallery 要离线可看，热链 GitHub 在国内常连不上。
源图仍不复制，生成时按需从本地克隆或上游拉取。

## 现状

- 44 条在库：36 种视觉风格 + 8 种解说语法。
- 23 条本地渲染，21 条只出提示词，0 条付费接口。
- 另有 32 条被屏蔽，见下节。

来源四个仓库，全部 MIT：

| 仓库 | 条目 | 形态 |
|---|---|---|
| geeklee/srt-whiteboard-animation | 1 | 本地渲染器 |
| cclank/lanshu-create-ai-presenter-video | 5 | 本地渲染器 |
| alchaincyf/huashu-art-motion | 17 | 代码绘制引擎 |
| threerocks/hand-drawn-styles | 21 | 提示词生成器 |

## 屏蔽

**2026-10-11 Conan 判 32 条不需要。** 清单在 `video-styles.json` 的 `blocked.ids`。

| 来源 | 条数 | 例子 |
|---|---|---|
| lanshu | 5 | V1 留白、V2 信号、V6 一镜到底、V7 图纸、数字人口播 |
| huashu 艺术史 | 26 | 印象派、包豪斯、克里姆特、莫奈、毕加索蓝 |
| huashu 语法 | 1 | 讲解员风格 |

**条目没删，只是不上页面。** 理由：整个 `capabilities/video-production/`
还是未跟踪目录，没有 git 历史，删掉就找不回来。改主意时从 `ids`
里删掉那一行即可恢复。

屏蔽生效在三处：

| 位置 | 怎么生效 |
|---|---|
| `gallery.html` | `build_gallery.py` 按清单跳过，页面只出 44 条 |
| `style-map.json` | 被屏蔽的 id 不参与选题映射，首选全部换成存活的风格 |
| `test_video_pipeline.py` | 清单写错 id 会红；页面里还留着被屏蔽的风格也会红 |

`previews/` 仍留 76 张。被屏蔽的 32 张不再被页面引用，但保留着——
解屏蔽时不用重新生成。

## 怎么用

选风格在 `skills/video-pipeline/SKILL.md` 的站 2。

1. 读 `style-map.json`，按选题措辞匹配 `cues`。
2. 出 2-3 个候选，给理由。
3. 打开 `gallery.html` 给人看。每张卡片顶上有一张示意图，可以直接比。
4. 确认后写进 `script.json` 的 `style` 字段。

**候选全落在 `prompt-only` 或 `paid-api` 时停机问人。**

## 执行分级

| 状态 | 数量 | 含义 |
|---|---|---|
| 本地渲染 | 23 | 装依赖即可跑，不调外部 API |
| 只出提示词 | 21 | 缺外部生图模型，现在出不了画面 |
| 付费接口 | 0 | 唯一一条（数字人口播）已屏蔽 |

**现在没有一条装好依赖。** 全部标 `needs-install` 或 `prompt-only`。

## 同类项分组

12 组有成员。两个组空了：**科技暗色**与**真人/数字人**——
成员都被屏蔽。空组保留在 `groups` 里，不删。

重复最多的两处：

- **白板/黑板手写**：geeklee 白板、lanshu V8 黑板报。
- **波普/漫画**：lanshu V5、huashu 利希滕斯坦与哈林、handdrawn 两种。

分组只标重叠，**不合并条目**。三套引擎的画法不同，合并会丢信息。

## 与图片线风格库的区别

- 图片线在 `capabilities/image-production/styles/`，字段是色板与排版。
- 视频线在本目录，字段是比例、执行方式、依赖。
- **两条线不共用风格条目。** 做法同源（并排看、人工选），内容各管各的。

## 未决

1. **装哪些依赖？** geeklee 要 Python venv，lanshu 要 Node 加 jq，huashu 要 uv 加 Playwright。
2. **threerocks 的 21 条要外部生图模型。** 接哪个？还是先不接？

## 边界

- 系统根只存清单与来源，**不复制仓库内容**。执行时按需拉取。
- 四个仓库都是 MIT，但各自的素材（锚点图、字体）要单独核授权。
- **没有真实事实就不出片。** 这条不变。
