#!/usr/bin/env python3
"""帧 + 旁白 → 成片。

这一站做三件事，顺序不能换：

1. **先出声音，再定画面时长。** 每幕的时长由旁白念完需要多久决定，
   不由「我觉得 5 秒好看」决定。反过来的话，语速一变就出现
   「画面走完了话还没说完」或者「话说完画面还杵着」。
   这条来自白板视频那条线的铁律：先旁白后画面。

2. **每幕一个片段。** 帧做极慢的推近，让静止的字有呼吸。

3. **交叉叠化接起来，再把音轨铺上去。**

配音有两个引擎，按 `script.json` 的 `audio.engine` 选：

| 引擎 | 声音从哪来 | 花钱 | 什么时候用 |
|---|---|---|---|
| `macos-say` | macOS 自带 | 不花 | 离线、试排版、只想看节奏 |
| `dashscope-cosyvoice` | 百炼 CosyVoice | 约 ¥0.95/万字符 | 要发出去的成片 |

**`say` 的声音是合成的机器人声，只适合看节奏，不适合发。** 要发就换 CosyVoice。

用法：
    python compose.py --script script.json --frames frames/ --out out.mp4
    python compose.py --script script.json --frames frames/ --out out.mp4 --motion none
    python compose.py --script script.json --frames frames/ --out out.mp4 --dry-run
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SYSTEM = Path(__file__).resolve().parents[3]
SPEECH_SCRIPTS = SYSTEM / "capabilities/speech/scripts"
if str(SPEECH_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SPEECH_SCRIPTS))
import synthesize as SPEECH  # noqa: E402


class ComposeError(Exception):
    """成片失败。消息写给执行者看。"""


# 推近的幅度。0.045 在 5 秒里几乎看不出来，但静止和微动是两种观感。
# 再大就会让人注意到「画面在缩放」，那是干扰，不是质感。
ZOOM_AMOUNT = 0.045

ENGINES = ("macos-say", "dashscope-cosyvoice")
AUDIO_SUFFIX = {"macos-say": ".aiff", "dashscope-cosyvoice": ".mp3"}


def run(cmd: list, what: str) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        tail = (result.stderr or "").strip().splitlines()[-6:]
        raise ComposeError(f"{what}失败：\n  " + "\n  ".join(tail))


def probe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise ComposeError(f"读不到时长：{path}")
    return float(result.stdout.strip())


def engine_of(audio_cfg: dict) -> str:
    engine = str(audio_cfg.get("engine") or "macos-say")
    if engine not in ENGINES:
        raise ComposeError(
            f"不认识的配音引擎「{engine}」。只有 {' 或 '.join(ENGINES)}——"
            "写错了会在合成到一半才发现，所以先拦下来"
        )
    return engine


def check_tools(engine: str) -> None:
    needed = ["ffmpeg", "ffprobe"]
    if engine == "macos-say":
        needed.append("say")
    missing = [name for name in needed if not shutil.which(name)]
    if missing:
        raise ComposeError(
            f"缺少外部程序：{', '.join(missing)}。"
            f"引擎 {engine} 需要它们，不装第三方 Python 包"
        )


def synthesize(scene: dict, audio_cfg: dict, out_path: Path, api_key: str = "") -> dict:
    """把一幕的旁白合成成音频文件。返回计费信息。"""
    text = (scene.get("narration") or "").strip()
    if not text:
        raise ComposeError(f"分镜 {scene.get('id')} 没有旁白——没有旁白就没有时长依据")
    engine = engine_of(audio_cfg)

    if engine == "macos-say":
        cmd = ["say", "-v", str(audio_cfg.get("voice", "Tingting")), "-o", str(out_path)]
        rate = audio_cfg.get("rate")
        if rate:
            cmd += ["-r", str(rate)]
        cmd.append(text)
        run(cmd, f"合成旁白 {scene.get('id')}")
        return {"characters": 0, "cost_yuan": 0.0}

    if not api_key:
        raise ComposeError("选了 CosyVoice 但没拿到 API Key")
    try:
        return SPEECH.synthesize(
            text,
            voice=str(audio_cfg.get("voice", "")),
            out_path=out_path,
            api_key=api_key,
            model=str(audio_cfg.get("model") or SPEECH.dashscope.DEFAULT_MODEL),
            volume=int(audio_cfg.get("volume", 50)),
            rate=float(audio_cfg.get("speed", 1.0)),
            pitch=float(audio_cfg.get("pitch", 1.0)),
        )
    except SPEECH.dashscope.SpeechError as exc:
        raise ComposeError(f"合成旁白 {scene.get('id')} 失败：{exc}") from exc


def build_scene_plan(script: dict, frames_dir: Path, audio_dir: Path, dry_run: bool = False) -> list:
    """算出每一幕的时长。时长由旁白决定，不是拍脑袋定的。"""
    target = script["target"]
    fps = int(target.get("fps", 30))
    min_seconds = float(script.get("min_scene_seconds", 3.0))
    tail = float(script.get("tail_seconds", 0.8))
    audio_cfg = script.get("audio") or {}
    engine = engine_of(audio_cfg)
    audio_dir.mkdir(parents=True, exist_ok=True)

    api_key = ""
    if engine == "dashscope-cosyvoice" and not dry_run:
        try:
            api_key = SPEECH.dashscope.resolve_api_key()
        except SPEECH.dashscope.SpeechError as exc:
            raise ComposeError(str(exc)) from exc

    plan = []
    for index, scene in enumerate(script["scenes"], 1):
        scene_id = scene.get("id") or f"scene-{index:02d}"
        matches = sorted(frames_dir.glob(f"{index:02d}-{scene_id}.png"))
        if not matches:
            raise ComposeError(
                f"找不到第 {index} 幕的帧：{frames_dir}/{index:02d}-{scene_id}.png。"
                "先跑 build_frames.py"
            )
        audio_path = audio_dir / f"{index:02d}-{scene_id}{AUDIO_SUFFIX[engine]}"

        if dry_run:
            # 不合成，只按计费口径估。用来在花钱之前看一眼总账。
            # 注意：这里数的是**计费字符**，一个汉字算两个，不是 len(text)。
            characters = SPEECH.dashscope.billable_characters(
                (scene.get("narration") or "").strip()
            )
            seconds = min_seconds
            plan.append({
                "id": scene_id, "frame": matches[0], "audio": audio_path,
                "spoken": 0.0, "seconds": seconds,
                "frames": max(1, round(seconds * fps)),
                "characters": characters,
                "cost_yuan": SPEECH.dashscope.estimate_cost(characters),
            })
            continue

        billed = synthesize(scene, audio_cfg, audio_path, api_key)
        spoken = probe_duration(audio_path)
        seconds = max(min_seconds, spoken + tail)
        plan.append({
            "id": scene_id,
            "frame": matches[0],
            "audio": audio_path,
            "spoken": spoken,
            "seconds": seconds,
            "frames": max(1, round(seconds * fps)),
            "characters": billed.get("characters", 0),
            "cost_yuan": billed.get("cost_yuan", 0.0),
        })
    return plan


def scene_filter(index: int, item: dict, width: int, height: int, fps: int, motion: str) -> str:
    if motion == "zoom":
        # 先放大再推近：直接在原尺寸上 zoompan，推的过程会一直重采样，越推越糊。
        steps = (
            f"scale={width * 2}:{height * 2},zoompan="
            f"z='1+{ZOOM_AMOUNT}*on/{max(1, item['frames'] - 1)}':"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={item['frames']}:s={width}x{height}:fps={fps}"
        )
    else:
        steps = f"scale={width}:{height},fps={fps}"
    return f"[{index}:v]{steps}[v{index}]"


def input_args(item: dict, fps: int, motion: str) -> list:
    """静止帧要自己循环，否则整幕只有 1 帧。

    单张 PNG 当输入时，ffmpeg 只读一帧就走。zoom 那条路靠 zoompan 的 `d=`
    把这一帧撑成整幕，所以不用管；motion=none 那条路没有 `d=`，
    于是整幕塌成 2 帧（0.07 秒）——2026-10-10 在单测里撞到。
    """
    if motion == "zoom":
        return ["-i", str(item["frame"])]
    return ["-loop", "1", "-t", f"{item['frames'] / fps:.4f}", "-i", str(item["frame"])]


def render_video(plan: list, script: dict, out_path: Path, motion: str) -> None:
    target = script["target"]
    width, height = int(target["width"]), int(target["height"])
    fps = int(target.get("fps", 30))
    transition = float(script.get("transition_seconds", 0.5))

    inputs = []
    for item in plan:
        inputs += input_args(item, fps, motion)

    graph = [scene_filter(i, item, width, height, fps, motion) for i, item in enumerate(plan)]

    last = "v0"
    offset = plan[0]["frames"] / fps - transition
    for index in range(1, len(plan)):
        label = f"x{index}"
        graph.append(
            f"[{last}][v{index}]xfade=transition=fade:duration={transition}:offset={offset:.4f}[{label}]"
        )
        offset += plan[index]["frames"] / fps - transition
        last = label

    run(
        ["ffmpeg", "-v", "error", "-y"] + inputs
        + ["-filter_complex", ";".join(graph), "-map", f"[{last}]",
           # 中间产物会被最后那次编码再压一遍，所以这一遍用快档。
           # 慢档留给成片那一步，那里才决定最终画质。
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
           "-pix_fmt", "yuv420p", str(out_path)],
        "合成画面",
    )


def render_audio(plan: list, out_path: Path, transition: float) -> None:
    """铺音轨。

    **每一幕的旁白只占「这一幕的时长减去叠化」。** 叠化的那 0.55 秒里，
    画面已经进入下一幕了；如果旁白还按整幕长度铺，每叠化一次就落后 0.55 秒，
    十幕下来旁白比画面晚近 5 秒——而且全程没人报错。

    2026-10-10 实测过这个错：画面 94.7s、音轨 99.6s，成片取了长的那个，
    旁白一路追着画面跑。
    """
    inputs, parts = [], []
    last = len(plan) - 1
    for index, item in enumerate(plan):
        inputs += ["-i", str(item["audio"])]
        hold = item["seconds"] if index == last else item["seconds"] - transition
        if hold <= 0:
            raise ComposeError(
                f"第 {index + 1} 幕只有 {item['seconds']:.2f}s，扣掉 {transition}s 叠化之后没有时间了"
            )
        # 旁白念完之后的空白补到这一整幕的长度，音画才对得齐。
        parts.append(
            f"[{index}:a]aresample=44100,apad=whole_dur={hold:.4f},atrim=duration={hold:.4f},"
            f"asetpts=PTS-STARTPTS[a{index}]"
        )
    labels = "".join(f"[a{index}]" for index in range(len(plan)))
    graph = ";".join(parts) + f";{labels}concat=n={len(plan)}:v=0:a=1[aout]"
    run(
        ["ffmpeg", "-v", "error", "-y"] + inputs
        + ["-filter_complex", graph, "-map", "[aout]", "-c:a", "pcm_s16le", str(out_path)],
        "合成音轨",
    )


def verify_sync(out_path: Path) -> tuple:
    """成片之后量一遍：画面和声音必须一样长。

    这一条拦的是上面那个错。两份长度不一致时 ffmpeg 不报错，
    它只是让长的那条决定成片时长，短的那条要么提前结束、要么被拉伸。
    """
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,duration",
         "-of", "csv=p=0", str(out_path)],
        capture_output=True, text=True,
    )
    lengths = {}
    for line in result.stdout.strip().splitlines():
        kind, _, duration = line.partition(",")
        if duration:
            lengths[kind.strip()] = float(duration)
    if "video" not in lengths or "audio" not in lengths:
        raise ComposeError(f"读不到成片的音视频时长：{result.stdout.strip()!r}")
    drift = abs(lengths["video"] - lengths["audio"])
    if drift > 0.15:
        raise ComposeError(
            f"音画对不上：画面 {lengths['video']:.2f}s，声音 {lengths['audio']:.2f}s，"
            f"差 {drift:.2f}s。旁白会一路追着画面跑"
        )
    return lengths["video"], lengths["audio"]


def generate_bed(seconds: float, out_path: Path) -> None:
    """合成一条环境音垫。

    **不是音乐，是垫底。** 六个正弦叠一个空五度和弦（根音 + 五度 + 八度 + 两个微失谐副本），
    低通到 800Hz，压到比旁白低二十多分贝。作用是让静音处不空，不是让人听出旋律。

    为什么自己做而不是找现成曲子：系统里没有可商用的曲库（Apple Loops 是空的），
    网上找一个会带来授权问题——那正是图片线 `asset_rights` 要拦的东西。
    正弦叠出来的东西没有版权问题，但它**也没有旋律**，所以只适合当垫底。

    实测电平：旁白均值 −18.0 dB，这条垫子均值 −36.5 dB。
    """
    voices = [110, 110.4, 164.81, 165.3, 220, 329.63]
    inputs = []
    for freq in voices:
        inputs += ["-f", "lavfi", "-i", f"sine=frequency={freq}:duration={seconds:.3f}"]
    mix = "".join(f"[{i}:a]" for i in range(len(voices)))
    fade = max(0.0, seconds - 3.0)
    graph = (
        f"{mix}amix=inputs={len(voices)}:normalize=0,"
        f"lowpass=f=800,volume=-26dB,"
        f"afade=t=in:d=2.5,afade=t=out:st={fade:.3f}:d=2.5[a]"
    )
    run(
        ["ffmpeg", "-v", "error", "-y"] + inputs
        + ["-filter_complex", graph, "-map", "[a]", "-c:a", "pcm_s16le", str(out_path)],
        "合成环境音垫",
    )


def mux(video: Path, audio: Path, out_path: Path, total: float, bed: Path | None,
        progress: bool) -> None:
    fade_start = max(0.0, total - 0.6)

    # 进度条。观众知道还剩多少，才愿意看完。位置是排版判断，不是平台规则——
    # 平台遮挡范围没有核验过，见 README「还没做」。
    bar = ""
    if progress:
        bar = (
            f",drawbox=x=0:y=1688:w='iw*t/{total:.3f}':h=6:"
            f"color=#993C1D@0.55:t=fill"
        )

    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(video), "-i", str(audio)]
    if bed is not None:
        cmd += ["-i", str(bed)]
        audio_graph = "[1:a][2:a]amix=inputs=2:duration=first:normalize=0[aout]"
    else:
        audio_graph = "[1:a]anull[aout]"

    graph = f"[0:v]fade=t=in:st=0:d=0.4,fade=t=out:st={fade_start:.3f}:d=0.6{bar}[v];{audio_graph}"
    run(
        cmd + ["-filter_complex", graph, "-map", "[v]", "-map", "[aout]",
               "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out_path)],
        "合并音画",
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="把帧和旁白合成一支竖屏视频")
    parser.add_argument("--script", required=True, help="视频脚本 JSON")
    parser.add_argument("--frames", required=True, help="帧目录")
    parser.add_argument("--out", required=True, help="输出 mp4")
    parser.add_argument("--motion", choices=["zoom", "none"], default="zoom",
                        help="画面运动。zoom 是极慢推近，none 是完全静止")
    parser.add_argument("--no-bgm", action="store_true", help="不加环境音垫")
    parser.add_argument("--no-progress", action="store_true", help="不加底部进度条")
    parser.add_argument("--dry-run", action="store_true",
                        help="只报幕数、字数和估算花费，不出片也不配音")
    parser.add_argument("--work", help="中间产物目录，默认用临时目录")
    args = parser.parse_args(argv)

    try:
        script = json.loads(Path(args.script).read_text(encoding="utf-8"))
        engine = engine_of(script.get("audio") or {})
        check_tools(engine)
        frames_dir = Path(args.frames)
        out_path = Path(args.out)

        own_work = args.work is None
        work = Path(tempfile.mkdtemp(prefix="hq-video-")) if own_work else Path(args.work)
        work.mkdir(parents=True, exist_ok=True)
        audio_dir = work / "audio"
        audio_dir.mkdir(exist_ok=True)

        plan = build_scene_plan(script, frames_dir, audio_dir, dry_run=args.dry_run)

        if args.dry_run:
            characters = sum(item["characters"] for item in plan)
            cost = sum(item["cost_yuan"] for item in plan)
            print(f"引擎 {engine} · {len(plan)} 幕 · 旁白共 {characters} 字 · 估算 ¥{cost:.4f}")
            for index, item in enumerate(plan, 1):
                print(f"  {index:02d} {item['id']:<10} {item['characters']:>4} 字"
                      f"  约 ¥{item['cost_yuan']:.4f}")
            print("这是估算，不是账单。真花钱的是下一步。")
            return 0

        transition = float(script.get("transition_seconds", 0.5))
        total = sum(item["seconds"] for item in plan) - transition * (len(plan) - 1)

        print("每一幕的时长由旁白决定：")
        for index, item in enumerate(plan, 1):
            print(f"  {index:02d} {item['id']:<10} 旁白 {item['spoken']:5.1f}s → 这一幕 {item['seconds']:5.1f}s")

        video = work / "video.mp4"
        audio = work / "audio.wav"
        render_video(plan, script, video, args.motion)
        render_audio(plan, audio, transition)

        bed = None
        if not args.no_bgm:
            bed = work / "bed.wav"
            generate_bed(total, bed)

        out_path.parent.mkdir(parents=True, exist_ok=True)
        mux(video, audio, out_path, total, bed, progress=not args.no_progress)

        length, audio_length = verify_sync(out_path)
        billed = sum(item["characters"] for item in plan)
        cost = sum(item["cost_yuan"] for item in plan)
        print(f"\n成片：{out_path}")
        print(f"  时长 {length:.1f}s（画面 {length:.1f}s / 声音 {audio_length:.1f}s）"
              f" · {len(plan)} 幕 · 运动 {args.motion}"
              f" · 音垫 {'无' if bed is None else '有'} · 进度条 {'无' if args.no_progress else '有'}")
        if billed:
            print(f"  配音 {engine} · 计费 {billed} 字 · 约 ¥{cost:.4f}")
        if own_work:
            shutil.rmtree(work, ignore_errors=True)
    except ComposeError as exc:
        print(f"合成失败：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
