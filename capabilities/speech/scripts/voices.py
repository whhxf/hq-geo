#!/usr/bin/env python3
"""复刻通道：一段录音 → 一个可复用的 voice_id。

**复刻不是「训练模型」，是登记一段音色特征。** 所以它很便宜也很快，
但有两件事必须记住：

1. **刚创建的音色不能用。** 状态先是 `DEPLOYING`，约 10 秒后变 `OK`。
   在 OK 之前合成会返回 `Engine return error code: 418`。
   `--wait` 会替你等。
2. **账号有音色上限（30 个）。** 满了要删。所以 `--list` 报「用了几个」。

**音频可以直接给本地文件。** 官方文档说 `url` 必须是公网可达地址，
但实测 `data:audio/wav;base64,...` 也收——所以不用先传到 OSS。
这条是 2026-10-10 实测出来的，文档里没有。

用法：

    # 先查音频合不合规，不调用
    python capabilities/speech/scripts/voices.py --check --audio sample.wav

    # 列已有的音色
    python capabilities/speech/scripts/voices.py --list

    # 复刻一个新音色（等它部署完）
    python capabilities/speech/scripts/voices.py --create --audio sample.wav --prefix conan --wait

    # 删掉一个
    python capabilities/speech/scripts/voices.py --delete --voice-id cosyvoice-v3-flash-...
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import dashscope  # noqa: E402

VOICE_LIMIT = 30

# 官方要求，来源：百炼「声音复刻」文档的音质要求表，2026-10-10 采集。
MIN_SECONDS = 5.0
MAX_SECONDS = 60.0
RECOMMENDED_MIN = 10.0
RECOMMENDED_MAX = 20.0
MAX_BYTES = 10 * 1024 * 1024
MIN_SAMPLE_RATE = 16000
ALLOWED_SUFFIXES = (".wav", ".mp3", ".m4a")

MIME = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".m4a": "audio/mp4"}


def probe_audio(path: Path) -> dict:
    """量一段音频的时长、采样率、声道、大小。ffprobe 是视频线已有的依赖。"""
    if not path.is_file():
        raise dashscope.SpeechError(f"找不到音频文件：{path}")
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=sample_rate,channels,codec_name",
         "-show_entries", "format=duration,size",
         "-of", "json", str(path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise dashscope.SpeechError(f"ffprobe 读不了这个文件：{result.stderr.strip()[:200]}")
    data = json.loads(result.stdout)
    stream = (data.get("streams") or [{}])[0]
    fmt = data.get("format") or {}
    return {
        "suffix": path.suffix.lower(),
        "seconds": float(fmt.get("duration") or 0),
        "bytes": int(fmt.get("size") or path.stat().st_size),
        "sample_rate": int(stream.get("sample_rate") or 0),
        "channels": int(stream.get("channels") or 0),
        "codec": stream.get("codec_name", ""),
    }


def check_audio(path: Path) -> list:
    """返回问题列表。空列表表示这段音频合规。

    **先查再传。** 复刻失败的报错很含糊（`Audio.AudioSilentError`），
    与其猜，不如本地把能量的都量出来。
    """
    info = probe_audio(path)
    problems = []
    if info["suffix"] not in ALLOWED_SUFFIXES:
        problems.append(
            f"格式是 {info['suffix'] or '(无后缀)'}，只收 {'/'.join(ALLOWED_SUFFIXES)}。"
            f"转一下：ffmpeg -i 原文件 -ar 16000 -ac 1 -c:a pcm_s16le 输出.wav"
        )
    if info["seconds"] < MIN_SECONDS:
        problems.append(f"只有 {info['seconds']:.1f} 秒，至少要 {MIN_SECONDS:.0f} 秒的连续说话")
    if info["seconds"] > MAX_SECONDS:
        problems.append(f"有 {info['seconds']:.1f} 秒，超过 {MAX_SECONDS:.0f} 秒上限")
    elif not (RECOMMENDED_MIN <= info["seconds"] <= RECOMMENDED_MAX):
        problems.append(
            f"{info['seconds']:.1f} 秒，不在推荐的 {RECOMMENDED_MIN:.0f}–{RECOMMENDED_MAX:.0f} 秒里。"
            "能用，但相似度会差一些"
        )
    if info["bytes"] > MAX_BYTES:
        problems.append(f"{info['bytes'] / 1024 / 1024:.1f} MB，超过 10 MB 上限")
    if info["sample_rate"] and info["sample_rate"] < MIN_SAMPLE_RATE:
        problems.append(f"采样率 {info['sample_rate']} Hz，低于 {MIN_SAMPLE_RATE} Hz")
    return problems


def audio_url(path: Path) -> str:
    """本地文件 → data URL。绕开「必须公网可达」这条要求。"""
    mime = MIME.get(path.suffix.lower()) or mimetypes.guess_type(path.name)[0] or "audio/wav"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def list_voices(api_key: str, prefix: str = "", page_size: int = 50) -> dict:
    body = {
        "model": "voice-enrollment",
        "input": {"action": "list_voice", "prefix": prefix,
                  "page_index": 0, "page_size": page_size},
    }
    output = dashscope.post(body, api_key).get("output", {})
    return {"total": output.get("total_count", 0), "voices": output.get("voice_list", [])}


def create_voice(api_key: str, audio: Path, prefix: str, model: str, public_url: str = "") -> str:
    if not prefix or not prefix.isalnum() or not prefix.islower() or len(prefix) > 10:
        raise dashscope.SpeechError(
            f"prefix「{prefix}」不合规：只能用小写字母和数字，最多 10 位"
        )
    url = public_url or audio_url(audio)
    body = {
        "model": "voice-enrollment",
        "input": {"action": "create_voice", "target_model": model,
                  "prefix": prefix, "url": url},
    }
    output = dashscope.post(body, api_key).get("output", {})
    voice_id = output.get("voice_id", "")
    if not voice_id:
        raise dashscope.SpeechError(f"创建成功但没返回 voice_id：{output}")
    return voice_id


def delete_voice(api_key: str, voice_id: str) -> None:
    body = {"model": "voice-enrollment",
            "input": {"action": "delete_voice", "voice_id": voice_id}}
    dashscope.post(body, api_key)


def wait_until_ready(api_key: str, voice_id: str, prefix: str,
                     timeout: float = dashscope.DEPLOY_TIMEOUT_SECONDS) -> str:
    """等音色部署完。返回最终状态。

    不等就合成，会拿到 `Engine return error code: 418`——那个报错看不出是「还没好」。
    """
    waited = 0.0
    while waited < timeout:
        time.sleep(dashscope.DEPLOY_POLL_SECONDS)
        waited += dashscope.DEPLOY_POLL_SECONDS
        for item in list_voices(api_key, prefix)["voices"]:
            if item.get("voice_id") == voice_id:
                status = item.get("status", "")
                print(f"  {waited:>3.0f}s  {status}", file=sys.stderr)
                if status == "OK":
                    return "OK"
                if status not in ("DEPLOYING", "UNDEPLOYED"):
                    raise dashscope.SpeechError(f"音色状态异常：{status}")
                break
    raise dashscope.SpeechError(f"等了 {timeout:.0f} 秒还没部署完，去控制台看一眼")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="声音复刻：查、建、删音色")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--list", action="store_true", help="列已有音色")
    action.add_argument("--create", action="store_true", help="复刻一个新音色")
    action.add_argument("--delete", action="store_true", help="删除一个音色")
    action.add_argument("--check", action="store_true", help="只检查音频合不合规，不调用")

    parser.add_argument("--audio", help="本地音频文件（--create / --check 用）")
    parser.add_argument("--prefix", default="", help="音色前缀，小写字母数字，最多 10 位")
    parser.add_argument("--model", default=dashscope.DEFAULT_MODEL, help="用哪个模型驱动这个音色")
    parser.add_argument("--public-url", default="", help="公网可达的音频地址，给了就不用 --audio")
    parser.add_argument("--voice-id", help="--delete 用")
    parser.add_argument("--wait", action="store_true", help="等音色部署完再返回")
    args = parser.parse_args(argv)

    try:
        if args.check:
            if not args.audio:
                raise dashscope.SpeechError("--check 要配 --audio")
            path = Path(args.audio)
            info = probe_audio(path)
            print(
                f"{path.name}：{info['seconds']:.1f}s · {info['sample_rate']} Hz · "
                f"{info['channels']} 声道 · {info['bytes'] / 1024:.0f} KB · {info['codec']}"
            )
            problems = check_audio(path)
            if problems:
                print("不合规：")
                for problem in problems:
                    print(f"  - {problem}")
                return 1
            print("合规：可以拿去复刻")
            return 0

        api_key = dashscope.resolve_api_key()

        if args.list:
            result = list_voices(api_key, args.prefix)
            print(f"共 {result['total']} 个（账号上限 {VOICE_LIMIT} 个）")
            for item in result["voices"]:
                print(f"  {item['voice_id']}\n    model={item.get('target_model')} "
                      f"status={item.get('status')} 建于 {item.get('gmt_create')}")
            return 0

        if args.create:
            if not args.audio and not args.public_url:
                raise dashscope.SpeechError("--create 要配 --audio 或 --public-url")
            if not args.prefix:
                raise dashscope.SpeechError("--create 要配 --prefix，它进 voice_id，之后靠它找")
            if args.audio:
                problems = check_audio(Path(args.audio))
                if problems:
                    print("音频不合规，先修再传：", file=sys.stderr)
                    for problem in problems:
                        print(f"  - {problem}", file=sys.stderr)
                    return 1
            used = list_voices(api_key)["total"]
            if used >= VOICE_LIMIT:
                raise dashscope.SpeechError(
                    f"账号已有 {used} 个音色，到上限了。先删掉不用的：--list 看，--delete 删"
                )
            voice_id = create_voice(
                api_key, Path(args.audio) if args.audio else Path(), args.prefix,
                args.model, args.public_url,
            )
            print(f"已创建 {voice_id}")
            if args.wait:
                wait_until_ready(api_key, voice_id, args.prefix)
                print("已就绪，可以拿去合成")
            else:
                print("还没部署完。等约 10 秒，或者下次加 --wait。")
            return 0

        if args.delete:
            if not args.voice_id:
                raise dashscope.SpeechError("--delete 要配 --voice-id")
            delete_voice(api_key, args.voice_id)
            print(f"已删除 {args.voice_id}（还剩 {list_voices(api_key)['total']} 个）")
            return 0
    except dashscope.SpeechError as exc:
        print(f"失败：{exc}", file=sys.stderr)
        return 1

    return 2


if __name__ == "__main__":
    sys.exit(main())
