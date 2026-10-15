# 语音

两条通道，都接阿里云百炼的 CosyVoice：

| 通道 | 做什么 | 脚本 | 接口 |
|---|---|---|---|
| **复刻** | 一段录音 → 一个可复用的 `voice_id` | `scripts/voices.py` | 同步 HTTP |
| **合成** | 文字 → 音频 | `scripts/synthesize.py` | 流式 WebSocket |

**为什么要有这条线。** 视频线第一版用 macOS 自带的 `say` 配音。
`say` 是 2007 年的拼接式合成，念中文像机器人。它适合看节奏，不适合发出去。
CosyVoice 是神经语音合成，同一个人念同一句话，听感差一个档。

## 合成：CosyVoice 没有 HTTP 接口

官方只提供 **WebSocket**。所以这里有一个自己写的客户端 `scripts/ws.py`，
按 RFC 6455 实现，只用标准库——系统宪法第 187 行写着「新系统只使用标准库」。

写之前找过 HTTP 端点，试了 `services/aigc/multimodal-generation/generation`
和几个变体，都返回 `url error, please check url`。**别再去试 HTTP，没有。**

音频是**二进制帧**，不是 base64。服务端每发一个 `sentence-synthesis` 事件，
紧接着在 binary 通道推一帧音频，客户端按顺序拼起来。拼错顺序不会报错，只会听到乱码。

```sh
# 先看花多少钱
python capabilities/speech/scripts/synthesize.py \
  --text "买之前先问这七个问题。" --voice longanyang --dry-run

# 真合成
python capabilities/speech/scripts/synthesize.py \
  --text "买之前先问这七个问题。" --voice longanyang --out out.mp3
```

## 复刻：两件文档没写清楚的事

```sh
# 先查音频合不合规，不调用
python capabilities/speech/scripts/voices.py --check --audio sample.wav

# 复刻，并等它部署完
python capabilities/speech/scripts/voices.py --create --audio sample.wav --prefix conan --wait
```

### 一、可以直接给本地文件，不用先传 OSS

官方文档写 `url` 必须是**公网可达**地址。实测 `data:audio/wav;base64,...`
也收——传静音时返回的是 `Audio.AudioSilentError`，说明它已经进到音频处理了。
**这条文档里没有，是 2026-10-10 实测出来的。**

所以复刻不需要对象存储，一条命令就能做。

### 二、刚创建的音色不能用，要等约 10 秒

状态先是 `DEPLOYING`，然后变 `OK`。在 `OK` 之前合成会返回：

```
[cosyvoice]Engine return error code: 418
```

**这个报错看不出是「还没好」。** `--wait` 会替你轮询，别自己猜。

### 音频要求

| 项 | 要求 |
|---|---|
| 格式 | WAV(16-bit) / MP3 / M4A |
| 时长 | 推荐 10–20 秒，上限 60 秒 |
| 采样率 | ≥ 16 kHz |
| 大小 | ≤ 10 MB |
| 内容 | 至少 5 秒连续清晰说话，不能有背景音乐、环境噪声、别人的声音 |

不合规的音频传上去，报错很含糊。所以 `--check` 在本地先把能量出来的都量出来：

```sh
ffmpeg -i 原文件 -ar 16000 -ac 1 -c:a pcm_s16le 输出.wav
```

**账号音色上限 30 个。** `--list` 会报用了几个，满了要 `--delete`。

## 成本

| 项 | 数 |
|---|---|
| 单价 | **0.9541 元/万字符** |
| 来源 | 百炼 cosyvoice-v3-flash 模型页，2026-10-10 采集 |
| 一支 10 幕视频（旁白 446 个汉字） | 计费 827 字符，约 **¥0.079** |
| 复刻 | 不额外计费，只占音色名额 |

### 计费口径：一个汉字算两个字符

**文档里没写，是实测出来的。** 七组对照：

| 输入 | 长度 | 计费 | 比值 |
|---|---|---|---|
| 纯汉字 | 10 | 20 | 2.00 |
| 纯字母 | 10 | 10 | 1.00 |
| 纯数字 | 10 | 10 | 1.00 |
| 汉字加标点 | 10 | 15 | 1.50 |
| 英文句子 | 26 | 26 | 1.00 |

**汉字算两个，其他都算一个。** 标点算一个。

第一版 dry-run 按 `len(text)` 估，446 字的视频估成 ¥0.043，
实际账单 ¥0.079——**少算将近一半**。改成按口径算之后估 ¥0.084，
比实际高 6%，偏保守的那一边。`billable_characters()` 就是这个口径。

改价要重新采集，不许凭印象写。`--dry-run` 报的是估算，不是账单。

**月度上限。** 用户定的红线是任何按量计费服务不超过 10 美元/月。
按上面的单价，这个额度够生成约 7 万计费字符，也就是七八十支视频。
**但还是要去百炼控制台设硬上限**——估算不替代上限。

## 密钥

查找顺序：

1. 环境变量 `HQ_GEO_DASHSCOPE_API_KEY` 或 `DASHSCOPE_API_KEY`
2. `~/.config/hq-geo/dashscope.json`
3. `~/.config/hq-geo/image.json`

第 3 条是图片线先建的文件。名字带 `image`，但里面的 key 是**账号级**的，
语音线和图片线共用同一把。不搬它：搬一次要动图片线，收益只是名字好看。

**密钥不进代码，也不进 git。**

## 还没做

- **流式边收边放。** 现在是收完整个音频再写文件。配音不需要实时，
  但实时对话需要，那是另一个场景。
- **字级时间戳。** 接口支持 `word_timestamp_enabled`，可以用来做口播字幕对齐。
  视频线现在没有字幕，所以还没接。
- **SSML。** 接口支持 `enable_ssml`，能控制停顿和重音。
  现在的旁白靠标点控制节奏，够用。
- **声音设计。** 百炼还有「音色设计」（用文字描述生成音色），
  和复刻是两条路。这次只接了复刻。
