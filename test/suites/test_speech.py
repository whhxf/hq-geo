#!/usr/bin/env python3
"""语音线的契约检查。

这条线最容易出的事不是崩，是**悄悄降级或悄悄花钱**：

- WebSocket 客户端退化成「只认文本帧」，音频帧被当 JSON 解析，成片变静音；
- 复刻音色没等部署就用，报一个看不出原因的 418，然后有人去改代码；
- 「必须公网 URL」这条被当成硬约束，于是有人去搭对象存储，绕远路；
- 单价被改小，或者干脆删掉，成本估算就成了安慰剂；
- 视频线的引擎开关被摘掉，退回只有 `say` 的年代，而没人发现。

所以这个检查盯的是**判据在不在、坑有没有留痕、钱有没有算**。
"""

import json
import sys
from pathlib import Path

SYSTEM = Path(__file__).resolve().parents[2]
CAP = "capabilities/speech"
VIDEO = "capabilities/video-production"

README = f"{CAP}/README.md"
WS = f"{CAP}/scripts/ws.py"
VOICES = f"{CAP}/scripts/voices.py"
SYNTH = f"{CAP}/scripts/synthesize.py"
DASHSCOPE = f"{CAP}/scripts/dashscope.py"
COMPOSE = f"{VIDEO}/scripts/compose.py"
SKILL = "skills/video-pipeline/SKILL.md"


def read(relative: str) -> str:
    return (SYSTEM / relative).read_text(encoding="utf-8")


def check_two_channels(errors: list) -> None:
    """两个通道都要在，而且各自的入口要写清楚。少一个就只剩半条线。"""
    for relative in (README, WS, VOICES, SYNTH, DASHSCOPE):
        if not (SYSTEM / relative).is_file():
            errors.append(f"语音线文件不见了：{relative}")
    if errors:
        return

    for target, anchor, reason in [
        (SYNTH, "def synthesize(", "没有合成通道，文字变不成语音"),
        (VOICES, "def create_voice(", "没有复刻通道，音色建不出来"),
        (VOICES, "def list_voices(", "不能列音色，就不知道账号里有几个、还剩几个名额"),
        (VOICES, "def delete_voice(", "不能删音色，30 个名额满了就卡死"),
        (VOICES, "def wait_until_ready(", "不等部署就用，会拿到看不出原因的 418"),
        (VOICES, "def check_audio(", "传之前不查音频，失败报错看不出哪里不合格"),
    ]:
        if anchor not in read(target):
            errors.append(f"{target} 少了 {anchor}——{reason}")


def check_websocket_is_real(errors: list) -> None:
    """客户端要真的实现 RFC 6455，不是个占位。

    CosyVoice 只有 WebSocket 接口。如果这个客户端退化成「只发不收」，
    合成会静默产出零字节音频，成片是静音的，而每一步都报成功。
    """
    source = read(WS)
    for anchor, reason in [
        ("258EAFA5-E914-47DA-95CA-C5AB0DC85B11", "握手校验的 GUID 没了，Accept 就没法验"),
        ("OP_BINARY = 0x2", "没有二进制帧，音频收不到"),
        ("def recv(", "没有接收，等于只发不收"),
        ("if opcode == OP_PING:", "不回 pong 会被服务端判死"),
    ]:
        if anchor not in source:
            errors.append(f"ws.py 少了 {anchor}——{reason}")

    # 客户端帧必须带掩码。这条写反了服务端直接断连。
    if "0x80 |" not in source:
        errors.append("ws.py 里找不到掩码位——客户端帧不带掩码会被服务端断连")

    if "OP_BINARY" not in read(SYNTH):
        errors.append("synthesize.py 不认二进制帧——音频会被当成 JSON 解析，成片静音")


def check_the_two_traps_are_recorded(errors: list) -> None:
    """两个实测出来的坑必须留在纸上。删掉就等于让人重新踩一遍。"""
    readme = read(README)
    for needle, reason in [
        ("data:audio/wav;base64", "本地文件变 data URL 这条实测发现必须留痕，否则会被当成必须传 OSS"),
        ("418", "部署未完成的报错码要写出来，否则没人认得出是「还没好」"),
        ("DEPLOYING", "音色的中间状态要写出来，否则 --wait 会被当成多余的"),
        ("没有 HTTP 接口", "要写死「只有 WebSocket」，否则下次还会去试 HTTP 端点"),
    ]:
        if needle not in readme:
            errors.append(f"语音 README 缺实测留痕（{reason}）: {needle}")


def check_cost_is_priced(errors: list) -> None:
    """钱要算得出来，而且单价要带来源。"""
    source = read(DASHSCOPE)
    if "PRICE_PER_10K_CHARS" not in source:
        errors.append("dashscope.py 没有单价常量——成本就估不出来")
    if "0.9541" not in source:
        errors.append("单价被改了或删了。改价要重新采集并在 README 写来源")
    if "def estimate_cost(" not in source:
        errors.append("没有成本估算函数，--dry-run 就没意义")
    if "月度上限" not in read(README):
        errors.append("README 没写月度上限这条红线——按量计费必须先去后台设硬上限")
    if "百炼" not in read(README) or "2026-10-10" not in read(README):
        errors.append("README 的单价没写来源和采集日期，那就是一个没法核验的数字")


def check_video_line_has_both_engines(errors: list) -> None:
    """视频线要能选引擎。只剩 say 的话，语音线等于没接。"""
    compose = read(COMPOSE)
    for anchor, reason in [
        ("ENGINES = (", "引擎清单没了，选引擎这件事就没有真源"),
        ('"dashscope-cosyvoice"', "CosyVoice 引擎没了，视频线退回只有 say"),
        ("AUDIO_SUFFIX", "两个引擎的输出后缀不同，不区分会让 ffmpeg 认错格式"),
        ("def engine_of(", "没有引擎校验，写错的引擎名会合成到一半才发现"),
        ("--dry-run", "没有花钱前的估算，按量计费就是闭着眼睛花"),
    ]:
        if anchor not in compose:
            errors.append(f"compose.py 少了 {anchor}——{reason}")

    if "check_tools(engine)" not in compose:
        errors.append("check_tools 没有按引擎区分——用 CosyVoice 时不该还要求机器上有 say")

    if "dashscope-cosyvoice" not in read(SKILL):
        errors.append("视频流水线 skill 没写 CosyVoice 引擎，执行者不知道有这条路")


def main() -> int:
    errors = []
    check_two_channels(errors)
    if not errors:
        check_websocket_is_real(errors)
        check_the_two_traps_are_recorded(errors)
        check_cost_is_priced(errors)
        check_video_line_has_both_engines(errors)

    if errors:
        print("FAIL speech")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS speech: 复刻与合成两个通道齐全、WebSocket 真实现、两个坑留痕、成本有价有源")
    return 0


if __name__ == "__main__":
    sys.exit(main())
