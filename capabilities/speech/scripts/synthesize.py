#!/usr/bin/env python3
"""合成通道：文字 → 语音。走 CosyVoice 流式 WebSocket。

**CosyVoice 没有 HTTP 接口。** 官方只提供 WebSocket，所以这里用
`ws.py` 那个最小客户端。别去找 HTTP 端点，找不到的。

**音频是二进制帧，不是 base64。** 服务端每发一个 `sentence-synthesis`
事件，紧接着就在 binary 通道推一帧音频。要按顺序拼起来。

用法：

    # 先看要花多少钱，不调用
    python capabilities/speech/scripts/synthesize.py --text "你好" --voice longanyang --dry-run

    # 真合成
    python capabilities/speech/scripts/synthesize.py --text "你好" --voice longanyang --out out.mp3

    # 用复刻音色（voice_id 从 voices.py --list 拿）
    python capabilities/speech/scripts/synthesize.py --text "你好" \
        --voice cosyvoice-v3-flash-xxxx-... --model cosyvoice-v3-flash --out out.mp3
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import dashscope  # noqa: E402
import ws  # noqa: E402


def synthesize(
    text: str,
    voice: str,
    out_path: Path,
    api_key: str,
    model: str = dashscope.DEFAULT_MODEL,
    fmt: str = dashscope.DEFAULT_FORMAT,
    sample_rate: int = dashscope.DEFAULT_SAMPLE_RATE,
    volume: int = 50,
    rate: float = 1.0,
    pitch: float = 1.0,
    timeout: float = 60,
) -> dict:
    """合成一段文字，写成音频文件。返回字节数、计费字数、估算成本。"""
    if not text.strip():
        raise dashscope.SpeechError("要合成的文字是空的")
    if not voice.strip():
        raise dashscope.SpeechError("没有指定音色")

    connection = ws.Connection(
        dashscope.SYNTHESIS_WS_URL,
        headers={"Authorization": f"Bearer {api_key}", "user-agent": "hq-geo-speech/1.0"},
        timeout=timeout,
    )
    task_id = str(uuid.uuid4())
    try:
        connection.send_json({
            "header": {"action": "run-task", "task_id": task_id, "streaming": "duplex"},
            "payload": {
                "task_group": "audio",
                "task": "tts",
                "function": "SpeechSynthesizer",
                "model": model,
                "parameters": {
                    "text_type": "PlainText",
                    "voice": voice,
                    "format": fmt,
                    "sample_rate": sample_rate,
                    "volume": volume,
                    "rate": rate,
                    "pitch": pitch,
                },
                "input": {},
            },
        })

        audio = bytearray()
        characters = 0
        started = False
        while True:
            opcode, payload = connection.recv()
            if opcode == ws.OP_BINARY:
                audio += payload
                continue
            if opcode == ws.OP_CLOSE:
                raise dashscope.SpeechError("服务端提前关闭了连接，音频可能不完整")
            if opcode != ws.OP_TEXT:
                continue

            event = json.loads(payload.decode("utf-8"))
            name = event.get("header", {}).get("event")

            if name == "task-started":
                started = True
                # 文本一次性发完。分多次发是给实时对话用的，配音不需要。
                connection.send_json({
                    "header": {"action": "continue-task", "task_id": task_id, "streaming": "duplex"},
                    "payload": {"input": {"text": text}},
                })
                connection.send_json({
                    "header": {"action": "finish-task", "task_id": task_id, "streaming": "duplex"},
                    "payload": {"input": {}},
                })
            elif name == "result-generated":
                usage = event.get("payload", {}).get("usage") or {}
                characters = usage.get("characters", characters)
            elif name == "task-finished":
                usage = event.get("payload", {}).get("usage") or {}
                characters = usage.get("characters", characters)
                break
            elif name == "task-failed":
                header = event.get("header", {})
                raise dashscope.SpeechError(
                    f"合成失败 {header.get('error_code')}：{header.get('error_message')}\n"
                    "  复刻音色刚创建时会返回 418，等状态变 OK 再试。"
                )
    finally:
        connection.close()

    if not started:
        raise dashscope.SpeechError("没收到 task-started，任务没有真正开始")
    if not audio:
        raise dashscope.SpeechError("服务端一个音频帧都没发，成片会是静音")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(bytes(audio))
    return {
        "path": str(out_path),
        "bytes": len(audio),
        "characters": characters,
        "cost_yuan": dashscope.estimate_cost(characters or len(text)),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="把文字合成为语音（CosyVoice 流式）")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text", help="要合成的文字")
    source.add_argument("--text-file", help="从文件读文字")
    parser.add_argument("--voice", required=True, help="音色。系统音色名，或复刻音色的 voice_id")
    parser.add_argument("--model", default=dashscope.DEFAULT_MODEL, help="驱动这个音色的模型")
    parser.add_argument("--out", help="输出音频文件")
    parser.add_argument("--format", default=dashscope.DEFAULT_FORMAT, choices=["mp3", "pcm", "opus"])
    parser.add_argument("--sample-rate", type=int, default=dashscope.DEFAULT_SAMPLE_RATE)
    parser.add_argument("--volume", type=int, default=50, help="音量 0-100")
    parser.add_argument("--rate", type=float, default=1.0, help="语速 0.5-2.0")
    parser.add_argument("--pitch", type=float, default=1.0, help="音调 0.5-2.0")
    parser.add_argument("--dry-run", action="store_true", help="只报字数和估算成本，不调用")
    args = parser.parse_args(argv)

    text = args.text if args.text is not None else Path(args.text_file).read_text(encoding="utf-8")
    characters = dashscope.billable_characters(text)

    if args.dry_run:
        print(f"要合成 {len(text)} 字，按计费口径是 {characters} 字符，"
              f"估算 ¥{dashscope.estimate_cost(characters):.4f}（不调用）")
        return 0

    if not args.out:
        print("要么给 --out，要么加 --dry-run", file=sys.stderr)
        return 2

    try:
        result = synthesize(
            text, args.voice, Path(args.out), dashscope.resolve_api_key(),
            model=args.model, fmt=args.format, sample_rate=args.sample_rate,
            volume=args.volume, rate=args.rate, pitch=args.pitch,
        )
    except dashscope.SpeechError as exc:
        print(f"合成失败：{exc}", file=sys.stderr)
        return 1

    print(
        f"已写入 {result['path']}（{result['bytes'] / 1024:.0f} KB）· "
        f"计费 {result['characters']} 字 · 约 ¥{result['cost_yuan']:.4f}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
