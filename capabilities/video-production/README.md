# 视频生产

把一份分镜脚本变成一支竖屏视频。

## 为什么这样切

视频帧和封面是同一类东西：**底图加文字层**。
排版判据（字号阶梯、字距范围、对比度、避头尾、中西文间距）已经在
`capabilities/typography/` 里建好、测好、有金样本。

所以这一站**不重写渲染**。它做两件排版线做不了的事：

1. **合身检查**——规格合法不等于文案放得下。见下。
2. **成片**——旁白、时长、运动、叠化、音轨。

复制一份渲染器，等于让两套判据各自漂移。这里不复制。

## 三站

### 执行边界（实测修订）

内置可执行样式是 `typographic-cards`。外部风格清单不是已安装的渲染器；
`build_frames.py` 必须拒绝未接通的 `style`，不能静默改成文字卡片。
每幕可用 `background_image` 引用本地真实图片，并用 `background_rights` 登记权利；
相对路径按脚本所在目录解析。缺图或缺权利时在渲染前失败。
音轨每幕先统一采样率，再补静音并精确裁到该幕扣除叠化的时长；不能仅依赖补静音参数推断成片长度。

| 站 | 脚本 | 输入 | 输出 |
|---|---|---|---|
| 1 定分镜 | 人工写 `script.json` | 事实包 + 创意 | 逐幕的文案与旁白 |
| 2 出帧 | `scripts/build_frames.py` | `script.json` + TypeSpec | 每幕一张 PNG |
| 3 成片 | `scripts/compose.py` | 帧 + 旁白 | mp4 |

站 2 调排版线的 `render_cover()` 和 `render_png()`。
站 3 调配音引擎和 `ffmpeg`。

## 配音：两个引擎，按 `audio.engine` 选

| 引擎 | 声音从哪来 | 花钱 | 什么时候用 |
|---|---|---|---|
| `macos-say` | macOS 自带 | 不花 | 试排版、看节奏、离线 |
| `dashscope-cosyvoice` | 百炼 CosyVoice | 约 ¥0.95/万字符 | 要发出去的成片 |

**`say` 是 2007 年的拼接式合成，念中文像机器人。**
2026-10-10 第一版成片就是它配的，Conan 的判词是「效果比较垃圾」。
它只适合看节奏。要发就换 CosyVoice，音色可以用自己复刻的。

两个引擎的参数名不一样，**别混**：

| 引擎 | `voice` | 其他字段 |
|---|---|---|
| `macos-say` | 系统语音名，如 `Tingting` | `rate` 是每分钟词数 |
| `dashscope-cosyvoice` | 复刻音色的 voice_id | `model` / `speed` / `volume` / `pitch` |

**`--dry-run` 先看账。** 按量计费的东西，闭着眼睛花是错的。
见 `capabilities/speech/README.md`。

## 依赖

只用系统已装好的东西：

| 程序 | 来源 | 用途 |
|---|---|---|
| Chrome | 已装浏览器 | HTML → PNG |
| `say` | macOS 自带 | 离线配音（可选，只走 `macos-say` 时需要） |
| `ffmpeg` / `ffprobe` | 已装 | 运动、叠化、混音、量音频 |

**零 Python 第三方依赖。** 这条和排版线一致——连 CosyVoice 的 WebSocket
客户端也是按 RFC 6455 自己写的，见 `capabilities/speech/scripts/ws.py`。

## 金样本

`templates/video-scene-type-spec.json`：1080×1920，四个层级（kicker / headline / meta / footer）。
字号按「一行放几个字」定，不是按「看起来多大」定。

实测（1080 宽，左右留白各 108，可用 864px）：

| 层级 | 字号 | 一行最多 |
|---|---|---|
| headline | 108px | 7 个汉字 |
| meta | 40px | 20 个汉字 |
| kicker | 36px | 23 个汉字 |

## 合身检查：补的是排版线的漏洞

`validate_type_spec.py` 只校验**规格本身**。它不知道你要写什么字。
于是「规格合法 + 文案太长 = 标题折成孤字」这条路一直没人拦。

**2026-10-10 实测**：9 个字的「或者遇到敏感问题，」在 108px 下要 1030px，
只有 864px 可用 → 折成「或者遇到敏感问」+「题，」。
多出来的那半行只有一个字，很难看，**而机器不报错**。

`capabilities/typography/scripts/check_fit.py` 量这件事：

```sh
python capabilities/typography/scripts/check_fit.py \
  --script script.json \
  --spec templates/video-scene-type-spec.json
```

`build_frames.py` 会在渲染前自动跑它。放不下就停，不出帧。

**检查器只负责说出来。** 改文案还是改字号，是执行者的决定。

## 时长由旁白决定

**先出声音，再定画面时长。** 这条来自白板视频那条线的铁律：先旁白后画面。

反过来的话，语速一变就出现两种难看：画面走完了话还没说完，
或者话说完画面还杵着。

`compose.py` 每幕的时长 = `max(最短时长, 旁白时长 + 尾留)`。
默认最短 3.4s、尾留 0.9s。

## 参数在哪

| 参数 | 位置 | 说明 |
|---|---|---|
| 尺寸、帧率 | `script.json` 的 `target` | 覆盖 TypeSpec 里的画布尺寸 |
| 语音、语速 | `script.json` 的 `audio` | `voice` 是 macOS 的语音名，`rate` 是每分钟词数 |
| 最短时长、尾留 | `script.json` 顶层 | 见上 |
| 叠化时长 | `script.json` 的 `transition_seconds` | 默认 0.55s |
| 运动 | 命令行 `--motion zoom\|none` | 默认 zoom，极慢推近 |

## 还没做

- **背景音乐。** `ffmpeg` 合成不出好听的音乐床，系统里也没有可商用的曲库。
  要加就得引入一个真实音源，那是另一个决定。
- **平台安全区。** 抖音 / 视频号的界面遮挡范围**没有核验过**。
  现在的留白（上 280 / 下 460）是排版判断，不是平台规则。
  核验前不许写成「已适配平台安全区」。
- **逐字或逐行入场。** 现在是整幕交叉叠化。做逐行入场要每幕渲多张分层图，
  成本是现在的三倍。等这个需求重复到第三次再说。
- **口播与字幕对齐检查。** 旁白和画面文字是两份东西，现在没人验它们说的是不是同一件事。
