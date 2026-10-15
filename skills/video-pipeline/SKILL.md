---
name: video-pipeline
description: 从任务文件到竖屏视频成片的完整流水线。用户说「做个视频」「把这条做成短视频」「推进视频任务」「生成一条竖屏视频」，或要求把某个选题做成抖音、小红书、视频号的视频时使用；只做文章或图片时不要触发。
---

# 视频流水线

## 目的

把 `tasks/<id>.md` 里的一句话，变成一支能发出去的竖屏视频，每一站留下可追溯的产出。

这条线只做视频。文章和图片是另外两条流水线，它们共用同一份任务单据和事实上下文，但不共用步骤。

## 开始前

完整读取：

- `tasks/<id>.md` — 任务本身，`## 任务` 区块是用户原话，不得改写
- `capabilities/content-production/tasks/README.md` — 状态字段和区块归属的约定
- `00-meta/content-engine/03-platform-hard-rules.md` — 目标渠道的硬规则
- `00-meta/content-engine/07-authorial-quality-system.md` — 作者化规范
- `capabilities/video-production/README.md` — 三站、依赖、金样本、参数在哪
- `capabilities/typography/README.md` — 排版判据的真源

涉及品牌或产品推广时，再读对应事实包的 `positioning.json`。
**叙事顺序优先看事实包里的方法条目**——有的包会写明「不要从功能列表开始」，
并给出要求的顺序（场景 → 摩擦 → 谁做了哪一步 → 谁接手 → 证据 → 边界）。

## 六站

### 站 1 · 读任务，查事实，定受众坐标

从 `## 任务` 区块提取：想要什么、给谁看、发哪里、手上有什么素材。

核对事实包 `facts/`。列出**会影响内容承诺、案例真实性或操作步骤**的缺口。
**缺料停机**：没有真实商品或真实事实前，视频只能标 `prepared`。

受众坐标必须能回答四个问题，答不上来就是没定：

| 问题 | 用在哪 |
|---|---|
| 他是谁（决策者还是使用者） | 决定第二人称落在谁身上 |
| 他刷到这条时卡在哪 | 决定开场第一句 |
| 他看完会做什么 | 决定结尾给什么动作 |
| 他现在相信什么错的 | 决定核心判断 |

产出：缺口清单，写进任务的 `## 待确认` 区块。

### 站 2 · 选风格，写分镜脚本

**先选风格，再写脚本。** 每种风格擅长演绎的句子不同，顺序反了要返工。

先检查实际执行器。huashu 源码在 `capabilities/video-production/engines/huashu/`，完整读取其中 `SKILL.md` 后走镜头表、lint、逐镜渲染、QA、独立审片、交付门禁。调用上级 `scripts/huashu_adapter.py --spec <片段> --out <文件>`；不要把 huashu 风格交给文字卡片出帧器。本文下方出帧命令仅适用于 `typographic-cards`。其他来源未接入前只能作为参考候选，不可声称可执行。

先读 `capabilities/video-production/styles/README.md`。

1. 读 `style-map.json`，用选题的措辞匹配 `cues`，取命中的第一条；没命中用 `default`。
2. 出 2-3 个候选（首选加备选），连同理由给用户。
3. **打开 `gallery.html` 让人看。** 在库 44 条，全部有示意图。被屏蔽的 32 条不上页面。
   风格靠看，不靠读。
4. 用户确认后，把风格 id 写进 `script.json` 的 `style` 字段。

**候选全落在 `prompt-only` 或 `paid-api` 时停机问人。** 不擅自接外部生图模型，不擅自花钱。

然后产出 `content/videos/<task-id>/script.json`。逐幕四样：

| 字段 | 写什么 |
|---|---|
| `narration` | 旁白。**口语**，一句话一个意思 |
| `kicker` | 幕标。序号、栏目标签 |
| `headline` | 大标题。**这一行几个字是有上限的** |
| `meta` | 补充说明。一到两句 |

**先写旁白，再写画面。** 顺序反了就会出现「画面漂亮但没话说」。
这条来自白板视频那条线：先旁白后画面。

**旁白的每一句都要能挂上事实。** 陈述效果、数字、案例的句子挂 `fact_ref`；
纯提问、纯过渡的句子写 `null`。分不清「本来没事实」和「忘了挂」的句子，
在契约里就是错的。

**一行放几个字有硬上限。** 金样本 1080 宽下大标题一行最多 7 个汉字。
写超了要跑合身检查才知道——见站 3。

**禁止的写法**（与图片线同一套）：

- 图上的文字不虚构数字、评价、客户案例
- 不留电话、微信、邮箱、网址、二维码——目标渠道可能禁
- 不用内部代号当对外名称

### 站 3 · 出帧

```sh
python capabilities/video-production/scripts/build_frames.py \
  --script <script.json> \
  --spec capabilities/video-production/templates/video-scene-type-spec.json \
  --out <frames 目录>
```

这一站会**先跑合身检查，再渲染**。放不下就停，不出帧。

合身检查单独跑：

```sh
python capabilities/typography/scripts/check_fit.py \
  --script <script.json> \
  --spec capabilities/video-production/templates/video-scene-type-spec.json
```

**检查器只负责说出来。** 改文案还是改字号，是执行者的决定。

**渲染不在这里实现。** 帧走排版线的同一套引擎，所以字号阶梯、对比度、
避头尾、中西文间距的判据自动生效。

**逐张看帧。** 打开每一张 PNG。机器能判「放不放得下」，
判不了「这一屏有没有信息量」。看到空的一屏就回站 2 改。

### 站 4 · 成片

```sh
python capabilities/video-production/scripts/compose.py \
  --script <script.json> \
  --frames <frames 目录> \
  --out <输出 mp4>
```

**先跑 `--dry-run` 看账。** 它会报幕数、旁白字数和估算花费，不配音也不出片。
按量计费的东西，闭着眼睛花是错的。

**每一幕的时长由旁白决定**，不是拍脑袋定的。
脚本里的 `min_scene_seconds` 是下限，`tail_seconds` 是念完之后的留白。

配音引擎写在 `script.json` 的 `audio.engine` 里，两个选一个：

| 引擎 | 声音 | 花钱 | 什么时候用 |
|---|---|---|---|
| `macos-say` | macOS 自带，机器人声 | 不花 | 试排版、看节奏、离线 |
| `dashscope-cosyvoice` | 百炼 CosyVoice，真人感 | 约 ¥0.95/万字符 | 要发出去的成片 |

**`say` 只适合看节奏，不适合发。** 要发就换 `dashscope-cosyvoice`。
CosyVoice 的音色可以是你自己复刻的——见 `capabilities/speech/README.md`。

两个引擎的参数名不一样，别混：

| 引擎 | 音色字段 | 其他 |
|---|---|---|
| `macos-say` | `voice`（如 `Tingting`） | `rate` 是每分钟词数 |
| `dashscope-cosyvoice` | `voice`（复刻音色的 voice_id） | `model` / `speed` / `volume` / `pitch` |

可用开关：

| 开关 | 作用 |
|---|---|
| `--motion zoom` | 极慢推近。默认 |
| `--motion none` | 完全静止 |
| `--dry-run` | 只报账，不配音不出片 |
| `--no-bgm` | 不加环境音垫 |
| `--no-progress` | 不加底部进度条 |

**环境音垫是垫底，不是音乐。** 它由正弦叠一个空五度和弦合成，
没有旋律，压到比旁白低二十多分贝。系统里没有可商用曲库，
网上找一个会带来授权问题——那正是图片线 `asset_rights` 要拦的东西。

### 站 5 · 验收

**人看一遍。** 机器判不了「好不好看」。看四件事：

| 看什么 | 不通过就怎么办 |
|---|---|
| 第一幕三秒内说清这是讲什么的 | 回站 2 改开场 |
| 每一幕停留够读完一行大字 | 调 `min_scene_seconds` 或改语速 |
| 旁白和画面文字说的是同一件事 | 回站 2 改，不是改画面 |
| 有没有哪一幕是空的 | 回站 2 补内容 |

**判的人不能是写脚本的人。** 自评等于没评。

### 站 6 · 写回任务

在任务的 `## 交付` 区块登记：

- 产物路径、时长、幕数
- `script.json` 路径
- 事实引用清单
- 验收结论
- 音垫与进度条是否开启

`stage` 改为 `review`。**公开发布要单独授权。**

## 边界

- **没有真实事实就不出片。** 缺料停机写在项目宪法里。
- **不替用户做内容决策。** 选什么角度、删哪一句，是用户的判断。
- **不自动发布。** 视频做出来就停在 `review`。
- **平台安全区未核验。** 现在的留白是排版判断，不是平台规则。
  核验前不许写成「已适配平台安全区」。
- **背景音乐还没接。** 现在只有合成的环境音垫，没有真实音源。
