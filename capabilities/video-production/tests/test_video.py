"""视频生产线的单测。

分三层，各测各的：

- **合身**：`check_fit` 量的是「这一行放不放得下」。有正例，也有会红的反例。
- **出帧**：小画布跑一遍真渲染，确认帧数和尺寸对得上。
- **成片**：小画布真跑 `say` + `ffmpeg`，确认时长由旁白决定。

用 270×480 的小画布。1080×1920 真跑一遍要几十秒，测试里没必要。
"""

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SYSTEM = Path(__file__).resolve().parents[3]
CAP = SYSTEM / "capabilities/video-production"
TYPO = SYSTEM / "capabilities/typography/scripts"
TEMPLATE = CAP / "templates/video-scene-type-spec.json"

for path in (CAP / "scripts", TYPO):
    sys.path.insert(0, str(path))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build_frames = load("vp_build_frames", CAP / "scripts/build_frames.py")
compose = load("vp_compose", CAP / "scripts/compose.py")
check_fit = load("vp_check_fit", TYPO / "check_fit.py")
validate = load("vp_validate", TYPO / "validate_type_spec.py")

SMALL = {"width": 270, "height": 480}


def small_spec() -> dict:
    """金样本缩到测试尺寸。

    字号**和留白**都要按同一个比例缩。只缩字号不缩留白的话，
    可用宽度会变成 270−108−108 = 54px，所有合身判据全红——
    那测的就不是判据，是测试自己写错了。
    """
    spec = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    ratio = SMALL["width"] / spec["canvas"]["width"]
    spec["canvas"]["width"] = SMALL["width"]
    spec["canvas"]["height"] = SMALL["height"]
    for side in ("top", "right", "bottom", "left"):
        spec["canvas"]["margin"][side] = max(4, round(spec["canvas"]["margin"][side] * ratio))
    for name, role in spec["roles"].items():
        spec["roles"][name]["size_px"] = max(12, round(role["size_px"] * ratio))
    return spec


def scene(scene_id: str, headline: str, narration: str) -> dict:
    return {
        "id": scene_id,
        "narration": narration,
        "content": {"kicker": "问题 1 / 7", "headline": headline, "meta": "样例说明"},
    }


def small_script() -> dict:
    return {
        "schema_version": 1,
        "id": "unit-sample",
        "brand_footer": "样例落款",
        "target": {**SMALL, "fps": 30, "aspect_ratio": "9:16"},
        "audio": {"engine": "macos-say", "voice": "Tingting", "rate": 200},
        "tail_seconds": 0.6,
        "min_scene_seconds": 1.0,
        "transition_seconds": 0.3,
        "scenes": [
            scene("a", "第一幕", "第一幕的旁白。"),
            scene("b", "第二幕", "第二幕的旁白。"),
        ],
    }


def write_frames(frames_dir: Path, script: dict) -> None:
    frames_dir.mkdir(parents=True, exist_ok=True)
    for index, item in enumerate(script["scenes"], 1):
        (frames_dir / f"{index:02d}-{item['id']}.png").write_bytes(b"x")


class GoldenSpecTest(unittest.TestCase):
    def test_golden_video_spec_is_valid(self):
        spec = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        self.assertEqual(validate.validate(spec), [])

    def test_golden_video_spec_is_portrait_9_16(self):
        spec = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        canvas = spec["canvas"]
        self.assertEqual((canvas["width"], canvas["height"]), (1080, 1920))
        self.assertEqual(canvas["width"] * 16, canvas["height"] * 9)

    def test_headline_holds_seven_characters(self):
        """一行 7 个汉字要放得下——这是金样本的排版承诺，不是巧合。"""
        spec = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        self.assertEqual(check_fit.check_content(spec, {"headline": "买" * 7}), [])

    def test_eight_character_headline_is_rejected(self):
        spec = json.loads(TEMPLATE.read_text(encoding="utf-8"))
        problems = check_fit.check_content(spec, {"headline": "买" * 8})
        self.assertTrue(problems, "8 个汉字超过一行容量，合身检查必须报出来")
        self.assertIn("headline", problems[0])


class FitTest(unittest.TestCase):
    def test_content_that_fits_passes(self):
        self.assertEqual(check_fit.check_content(small_spec(), {"headline": "放得下"}), [])

    def test_overlong_line_is_reported(self):
        problems = check_fit.check_content(small_spec(), {"headline": "这一行" * 12})
        self.assertTrue(problems)
        self.assertIn("放不下", problems[0])

    def test_unknown_role_is_reported(self):
        """文案里有规格没定义的层级时，渲染会崩。这里要先说清楚原因。"""
        problems = check_fit.check_content(small_spec(), {"subtitle": "没有这一格"})
        self.assertTrue(problems)
        self.assertIn("规格里只有", problems[0])

    def test_empty_line_is_skipped(self):
        self.assertEqual(check_fit.check_content(small_spec(), {"headline": "第一行\n\n第二行"}), [])

    def test_block_that_is_too_tall_is_reported(self):
        spec = small_spec()
        spec["canvas"]["height"] = 60
        problems = check_fit.check_content(spec, {"headline": "第一行\n第二行\n第三行"})
        self.assertTrue(any("整块文案放不下" in problem for problem in problems))


class FrameTest(unittest.TestCase):
    def test_unwired_style_fails_before_output(self):
        script = small_script()
        script['style'] = 'wb-stream-whiteboard'
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(build_frames.FrameError, '未接通'):
                build_frames.build(script, small_spec(), Path(temp))
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_background_requires_existing_file_and_rights(self):
        script = small_script()
        script['scenes'][0]['background_image'] = '/missing/frame.png'
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(build_frames.FrameError, '权利'):
                build_frames.build(script, small_spec(), Path(temp))
            script['scenes'][0]['background_rights'] = 'own_capture'
            with self.assertRaisesRegex(build_frames.FrameError, '不存在'):
                build_frames.build(script, small_spec(), Path(temp))

    @classmethod
    def setUpClass(cls):
        if not shutil.which("ffmpeg"):
            raise unittest.SkipTest("没有 ffmpeg")

    def test_frames_have_expected_count_and_size(self):
        script = small_script()
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            frames = build_frames.build(script, small_spec(), out)
            self.assertEqual(len(frames), 2)
            for path in frames:
                self.assertTrue(path.is_file())
                self.assertGreater(path.stat().st_size, 0)
            names = sorted(path.name for path in out.glob("*.png"))
            self.assertEqual(names, ["01-a.png", "02-b.png"])

    def test_overlong_copy_stops_before_rendering(self):
        """放不下就不出帧——出了帧再改，等于让人对着错的东西做判断。"""
        script = small_script()
        script["scenes"][0]["content"]["headline"] = "这一行" * 12
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            with self.assertRaises(build_frames.FrameError):
                build_frames.build(script, small_spec(), out)
            self.assertEqual(sorted(out.glob("*.png")), [])

    def test_brand_footer_is_stamped_on_every_scene(self):
        """落款写在脚本顶层。逐幕写就会有人漏写一幕。"""
        script = small_script()
        content = build_frames.scene_content(script["scenes"][0], script["brand_footer"])
        self.assertEqual(content["footer"], "样例落款")


class ComposeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        missing = [name for name in ("say", "ffmpeg", "ffprobe") if not shutil.which(name)]
        if missing:
            raise unittest.SkipTest(f"缺少 {missing}")

    def test_duration_comes_from_narration(self):
        """短旁白被最短时长托住，长旁白把这一幕撑长。"""
        script = small_script()
        script["scenes"][1]["narration"] = "这是一句明显更长的旁白，" * 6
        with tempfile.TemporaryDirectory() as temp:
            frames_dir = Path(temp) / "frames"
            write_frames(frames_dir, script)
            plan = compose.build_scene_plan(script, frames_dir, Path(temp) / "audio")

        self.assertGreaterEqual(plan[0]["seconds"], script["min_scene_seconds"])
        self.assertGreater(plan[1]["spoken"], plan[0]["spoken"])
        self.assertGreater(plan[1]["seconds"], plan[0]["seconds"])

    def test_every_scene_gets_an_audio_file(self):
        script = small_script()
        with tempfile.TemporaryDirectory() as temp:
            frames_dir = Path(temp) / "frames"
            write_frames(frames_dir, script)
            plan = compose.build_scene_plan(script, frames_dir, Path(temp) / "audio")
            for item in plan:
                self.assertTrue(item["audio"].is_file())
                self.assertGreater(item["spoken"], 0)

    def test_missing_narration_is_rejected(self):
        script = small_script()
        script["scenes"][0]["narration"] = "  "
        with tempfile.TemporaryDirectory() as temp:
            frames_dir = Path(temp) / "frames"
            write_frames(frames_dir, script)
            with self.assertRaises(compose.ComposeError):
                compose.build_scene_plan(script, frames_dir, Path(temp) / "audio")

    def test_missing_frame_is_reported_with_the_path(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(compose.ComposeError) as ctx:
                compose.build_scene_plan(small_script(), Path(temp), Path(temp) / "audio")
            self.assertIn("build_frames.py", str(ctx.exception))

    def test_bed_is_low_and_long_enough(self):
        """垫子必须比旁白低二十多分贝，否则会盖住人声。"""
        if not shutil.which("ffmpeg"):
            raise unittest.SkipTest("没有 ffmpeg")
        with tempfile.TemporaryDirectory() as temp:
            bed = Path(temp) / "bed.wav"
            compose.generate_bed(6.0, bed)
            self.assertAlmostEqual(compose.probe_duration(bed), 6.0, delta=0.2)
            result = subprocess.run(
                ["ffmpeg", "-v", "info", "-i", str(bed), "-af", "volumedetect", "-f", "null", "-"],
                capture_output=True, text=True,
            )
            mean = [line for line in result.stderr.splitlines() if "mean_volume" in line]
            self.assertTrue(mean, "量不到音垫电平")
            level = float(mean[0].split(":")[-1].replace("dB", "").strip())
            self.assertLess(level, -30.0, f"音垫均值 {level} dB 太响，会盖住人声")

    def test_audio_matches_the_picture_to_the_frame(self):
        """音轨和画面的长度必须一样。这是这条线唯一能红的地方。

        叠化吃掉 transition 秒：三幕各 5.0 秒、叠化 0.5 秒，
        画面总长 = 5.0×3 − 0.5×2 = 14.0。
        音轨要按同一笔账铺：前两幕各铺 5.0−0.5，最后一幕铺满 5.0。

        2026-10-10 真出过这个错：音轨按整幕铺，画面 94.7s、音轨 99.6s，
        ffmpeg 一条都不报，成片取了长的那个，旁白一路追着画面跑。
        所以这里不写死期望值，而是拿真画面来对——写死的话，
        公式和测试会一起错，错得一样。
        """
        if not shutil.which("ffmpeg"):
            raise unittest.SkipTest("没有 ffmpeg")
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            script = small_script()
            names = ["a", "b", "c"]
            script["scenes"] = [scene(name, "样例", "样例旁白。") for name in names]
            script["transition_seconds"] = 0.5

            frames_dir = temp / "frames"
            frames_dir.mkdir(parents=True, exist_ok=True)
            plan = []
            for index, name in enumerate(names):
                frame = frames_dir / f"{index + 1:02d}-{name}.png"
                subprocess.run(
                    ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                     "-i", f"color=c=black:s={SMALL['width']}x{SMALL['height']}", "-frames:v", "1", str(frame)],
                    check=True,
                )
                wav = temp / f"s{index}.aiff"
                subprocess.run(
                    ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                     "-i", "anullsrc=r=44100:cl=mono", "-t", "3", str(wav)],
                    check=True,
                )
                plan.append({"id": name, "audio": wav, "spoken": 3.0,
                             "seconds": 5.0, "frames": 150, "frame": frame})

            picture = temp / "picture.mp4"
            compose.render_video(plan, script, picture, motion="none")
            audio = temp / "audio.wav"
            compose.render_audio(plan, audio, transition=0.5)

            expected = 5.0 * 3 - 0.5 * 2
            self.assertAlmostEqual(compose.probe_duration(picture), expected, delta=0.2)
            self.assertAlmostEqual(compose.probe_duration(audio), expected, delta=0.2)

    def test_verify_sync_rejects_mismatched_tracks(self):
        """音画长度不一致时 ffmpeg 不报错，所以必须自己量。"""
        if not shutil.which("ffmpeg"):
            raise unittest.SkipTest("没有 ffmpeg")
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            video = temp / "v.mp4"
            audio = temp / "a.wav"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                            "-i", "color=c=black:s=64x64:d=2:r=10",
                            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video)], check=True)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                            "-i", "anullsrc=r=44100:cl=mono", "-t", "4",
                            "-c:a", "pcm_s16le", str(audio)], check=True)
            merged = temp / "out.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-i", str(audio),
                            "-c:v", "copy", "-c:a", "aac", str(merged)], check=True)
            with self.assertRaises(compose.ComposeError) as ctx:
                compose.verify_sync(merged)
            self.assertIn("音画对不上", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
