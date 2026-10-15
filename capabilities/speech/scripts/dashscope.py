#!/usr/bin/env python3
"""百炼语音能力共用的东西：密钥、端点、HTTP 调用、成本。

**密钥不进代码，也不进 git。** 查找顺序见 `resolve_api_key()`。
报错时要说清楚去哪配，不能只说「没有 key」——那是让用户自己猜。
"""

from __future__ import annotations

import json
import os
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

# 复刻通道：创建、查询、删除音色，都是同步 HTTP。
CUSTOMIZATION_URL = "https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization"
# 合成通道：CosyVoice 只有流式 WebSocket，没有 HTTP。
SYNTHESIS_WS_URL = "wss://dashscope.aliyuncs.com/api-ws/v1/inference"

# 单价，元/万字符。来源：百炼模型页 cosyvoice-v3-flash「模型价格」，
# 2026-10-10 采集。改价要重新采集，不许凭印象写。
PRICE_PER_10K_CHARS = 0.9541

# **计费口径：一个汉字算两个字符，其他都算一个。**
#
# 2026-10-10 实测出来的，文档里没有。七组对照：
#
#   纯汉字 10 字  → 计费 20（比值 2.00）
#   纯字母 10 字  → 计费 10（比值 1.00）
#   纯数字 10 字  → 计费 10（比值 1.00）
#   汉字+标点 10  → 计费 15（5 个汉字×2 + 5 个标点×1）
#   英文句子 26   → 计费 26
#
# 不按这个算，估算会**少算将近一半**。第一版 dry-run 按 `len(text)` 估，
# 446 字的视频估成 ¥0.043，实际账单 ¥0.079。
CJK_WEIGHT = 2
OTHER_WEIGHT = 1

DEFAULT_MODEL = "cosyvoice-v3-flash"
DEFAULT_FORMAT = "mp3"
DEFAULT_SAMPLE_RATE = 22050

# 复刻音色要等部署完成才能用。实测 DEPLOYING → OK 约 10 秒。
DEPLOY_POLL_SECONDS = 3
DEPLOY_TIMEOUT_SECONDS = 180

CONFIG_CANDIDATES = (
    Path.home() / ".config" / "hq-geo" / "dashscope.json",
    # 图片线先建的文件，名字带 image，但里面的 key 是账号级的，语音线共用。
    # 不搬它：搬一次要动图片线，收益只是名字好看。
    Path.home() / ".config" / "hq-geo" / "image.json",
)


class SpeechError(Exception):
    """调用失败。消息写给执行者看，不写给调试器看。"""


def resolve_api_key() -> str:
    for name in ("HQ_GEO_DASHSCOPE_API_KEY", "DASHSCOPE_API_KEY"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    for path in CONFIG_CANDIDATES:
        if path.is_file():
            try:
                value = json.loads(path.read_text(encoding="utf-8")).get("api_key", "").strip()
            except json.JSONDecodeError:
                continue
            if value:
                return value
    raise SpeechError(
        "找不到百炼 API Key。三选一：\n"
        f"  1. 建 {CONFIG_CANDIDATES[0]}，内容 {{\"api_key\": \"sk-...\"}}\n"
        "  2. export HQ_GEO_DASHSCOPE_API_KEY=sk-...\n"
        f"  3. 复用已有的 {CONFIG_CANDIDATES[1]}\n"
        "密钥不写进代码，也不进 git。"
    )


def post(body: dict, api_key: str, url: str = CUSTOMIZATION_URL, timeout: float = 120) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:600]
        raise SpeechError(f"百炼返回 {exc.code}：{detail}") from exc
    except urllib.error.URLError as exc:
        raise SpeechError(f"连不上百炼：{exc.reason}") from exc


def billable_characters(text: str) -> int:
    """按计费口径数字符：汉字算两个，其他都算一个（标点也算一个）。

    口径是实测出来的，见 `CJK_WEIGHT` 上面的注释。别改回 `len(text)`。

    **全角标点算一个，不算两个。** 实测「一，二。三！四？五；」计费 15，
    也就是 5 个汉字×2 + 5 个标点×1。所以判据是「这个字是不是字母」，
    不是「这个字是不是全角」。
    """
    total = 0
    for ch in text:
        wide = unicodedata.east_asian_width(ch) in ("W", "F")
        letter = unicodedata.category(ch).startswith("L")
        total += CJK_WEIGHT if (wide and letter) else OTHER_WEIGHT
    return total


def estimate_cost(characters: int) -> float:
    """按计费字符数估钱。单位：元。"""
    return characters / 10000 * PRICE_PER_10K_CHARS
