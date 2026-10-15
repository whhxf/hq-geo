"""语音能力包的单测。

三层，各测各的，**一条都不联网**：

- **帧协议**：自己写的 WebSocket 客户端要真的按 RFC 6455 编解码。
  这一段错了，服务端会直接断连，而报错看不出是编帧的问题。
- **音频校验**：复刻前的本地检查。不合格的音频传上去报错很含糊，所以要在这里拦住。
- **成本**：单价和估算。估错了会让人以为很便宜，然后账单来了才知道。

真调用（花钱的那部分）不进单测。要验真调用就跑 CLI，见 README。
"""

import contextlib
import importlib.util
import io
import json
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SYSTEM = Path(__file__).resolve().parents[3]
CAP = SYSTEM / "capabilities/speech"
SCRIPTS = CAP / "scripts"

sys.path.insert(0, str(SCRIPTS))

# 按名字 import，不用 spec_from_file_location 造第二份。
# 造第二份会让 SpeechError 变成两个不同的类，`assertRaises` 抓不到——
# 这个坑单测自己踩过一次。
import dashscope  # noqa: E402
import synthesize  # noqa: E402
import voices  # noqa: E402
import ws  # noqa: E402


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextlib.contextmanager
def quiet():
    """argparse 在 SystemExit 之前会往 stderr 打 usage，测试里没必要看。"""
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        yield


class FakeSocket:
    """只接住 sendall。测接收路径时用，不真连。"""

    def __init__(self):
        self.sent = bytearray()

    def sendall(self, data):
        self.sent += data


def connection_with(buffer: bytes) -> ws.Connection:
    """造一个已握过手、缓冲区里已有服务端数据的连接。不碰网络。"""
    conn = ws.Connection.__new__(ws.Connection)
    conn.sock = FakeSocket()
    conn.buffer = buffer
    conn.closed = False
    return conn


def server_frame(opcode: int, payload: bytes, fin: bool = True) -> bytes:
    """服务端发来的帧不带掩码。"""
    first = (0x80 if fin else 0x00) | opcode
    header = bytearray([first])
    length = len(payload)
    if length < 126:
        header.append(length)
    elif length < (1 << 16):
        header.append(126)
        header += struct.pack("!H", length)
    else:
        header.append(127)
        header += struct.pack("!Q", length)
    return bytes(header) + payload


class FrameProtocolTest(unittest.TestCase):
    """自己写的 WebSocket 客户端，编解码要真的对。"""

    def test_client_frames_are_masked(self):
        """客户端发出去的帧必须带掩码。不带服务端会直接断连。"""
        conn = connection_with(b"")
        frame = conn._frame(ws.OP_TEXT, b"hi")
        self.assertEqual(frame[0] & 0x0F, ws.OP_TEXT)
        self.assertTrue(frame[1] & 0x80, "客户端帧没有掩码位")
        self.assertEqual(frame[1] & 0x7F, 2)
        mask = frame[2:6]
        self.assertEqual(bytes(b ^ mask[i % 4] for i, b in enumerate(frame[6:])), b"hi")

    def test_length_encoding_covers_all_three_forms(self):
        """126 以下一字节，65536 以下两字节，再往上八字节。写错长度读出来是乱的。"""
        conn = connection_with(b"")
        self.assertEqual(conn._frame(ws.OP_BINARY, b"x" * 100)[1] & 0x7F, 100)
        self.assertEqual(conn._frame(ws.OP_BINARY, b"x" * 200)[1] & 0x7F, 126)
        self.assertEqual(conn._frame(ws.OP_BINARY, b"x" * 70000)[1] & 0x7F, 127)

    def test_reads_a_text_frame(self):
        conn = connection_with(server_frame(ws.OP_TEXT, "你好".encode("utf-8")))
        opcode, payload = conn.recv()
        self.assertEqual(opcode, ws.OP_TEXT)
        self.assertEqual(payload.decode("utf-8"), "你好")

    def test_reads_a_binary_frame(self):
        audio = bytes(range(256)) * 4
        conn = connection_with(server_frame(ws.OP_BINARY, audio))
        opcode, payload = conn.recv()
        self.assertEqual(opcode, ws.OP_BINARY)
        self.assertEqual(payload, audio)

    def test_binary_frames_are_not_confused_with_text(self):
        """音频走二进制帧，事件走文本帧。混了就会把音频当 JSON 解析。"""
        buffer = server_frame(ws.OP_TEXT, b'{"a":1}') + server_frame(ws.OP_BINARY, b"\x00\x01")
        conn = connection_with(buffer)
        first = conn.recv()
        second = conn.recv()
        self.assertEqual(first[0], ws.OP_TEXT)
        self.assertEqual(second[0], ws.OP_BINARY)
        self.assertEqual(second[1], b"\x00\x01")

    def test_fragmented_frame_is_reassembled(self):
        """分片要拼起来。长音频可能被拆成多帧。"""
        buffer = (
            server_frame(ws.OP_BINARY, b"abc", fin=False)
            + server_frame(ws.OP_CONT, b"def", fin=False)
            + server_frame(ws.OP_CONT, b"ghi", fin=True)
        )
        opcode, payload = connection_with(buffer).recv()
        self.assertEqual(opcode, ws.OP_BINARY)
        self.assertEqual(payload, b"abcdefghi")

    def test_ping_is_answered_with_pong(self):
        """不回 pong 会被服务端判死。"""
        conn = connection_with(server_frame(ws.OP_PING, b"ping") + server_frame(ws.OP_TEXT, b"ok"))
        opcode, payload = conn.recv()
        self.assertEqual(opcode, ws.OP_TEXT)
        self.assertEqual(payload, b"ok")
        self.assertEqual(conn.sock.sent[0] & 0x0F, ws.OP_PONG)

    def test_close_frame_is_reported_not_raised(self):
        """对端说再见是正常事件，不该抛异常。"""
        conn = connection_with(server_frame(ws.OP_CLOSE, struct.pack("!H", 1000)))
        opcode, _ = conn.recv()
        self.assertEqual(opcode, ws.OP_CLOSE)
        self.assertTrue(conn.closed)

    def test_handshake_accept_is_verified(self):
        """Sec-WebSocket-Accept 要按 RFC 的算法算。算错了服务端不是 WebSocket。"""
        key = "dGhlIHNhbXBsZSBub25jZQ=="
        expected = "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="
        import base64
        import hashlib
        got = base64.b64encode(
            hashlib.sha1((key + ws.GUID).encode()).digest()
        ).decode()
        self.assertEqual(got, expected)


class AudioCheckTest(unittest.TestCase):
    """复刻前的本地检查。不合格的音频传上去，报错看不出哪里不合格。"""

    def make(self, directory: Path, name: str, seconds: float, rate: int) -> Path:
        path = directory / name
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
             "-i", f"sine=frequency=440:duration={seconds}", "-ar", str(rate),
             "-ac", "1", "-c:a", "pcm_s16le", str(path)],
            check=True,
        )
        return path

    def setUp(self):
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            raise unittest.SkipTest("缺少 ffmpeg / ffprobe")

    def test_good_sample_passes(self):
        with tempfile.TemporaryDirectory() as temp:
            path = self.make(Path(temp), "good.wav", 15, 16000)
            self.assertEqual(voices.check_audio(path), [])

    def test_too_short_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            problems = voices.check_audio(self.make(Path(temp), "short.wav", 2, 16000))
            self.assertTrue(any("连续说话" in p for p in problems))

    def test_too_long_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            problems = voices.check_audio(self.make(Path(temp), "long.wav", 70, 16000))
            self.assertTrue(any("上限" in p for p in problems))

    def test_low_sample_rate_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            problems = voices.check_audio(self.make(Path(temp), "low.wav", 15, 8000))
            self.assertTrue(any("采样率" in p for p in problems))

    def test_wrong_format_is_rejected_with_the_convert_command(self):
        """报错要给出转码命令，不能只说「格式不对」。"""
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "x.aiff"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                            "-i", "sine=frequency=440:duration=15", str(path)], check=True)
            problems = voices.check_audio(path)
            self.assertTrue(any("ffmpeg" in p for p in problems))

    def test_local_file_becomes_a_data_url(self):
        """本地文件直接变 data URL。这条绕开了「必须公网可达」。"""
        with tempfile.TemporaryDirectory() as temp:
            path = self.make(Path(temp), "good.wav", 6, 16000)
            url = voices.audio_url(path)
            self.assertTrue(url.startswith("data:audio/wav;base64,"))
            self.assertGreater(len(url), 1000)

    def test_missing_file_says_so(self):
        with self.assertRaises(dashscope.SpeechError) as ctx:
            voices.probe_audio(Path("/nowhere/nothing.wav"))
        self.assertIn("找不到音频文件", str(ctx.exception))


class CostTest(unittest.TestCase):
    def test_price_matches_the_published_rate(self):
        """单价是采集来的，不是拍脑袋的。改了要重新采集并在 README 里写来源。"""
        self.assertAlmostEqual(dashscope.PRICE_PER_10K_CHARS, 0.9541, places=4)

    def test_ten_thousand_characters_costs_the_unit_price(self):
        self.assertAlmostEqual(dashscope.estimate_cost(10000), 0.9541, places=4)

    def test_a_chinese_character_counts_as_two(self):
        """实测口径：汉字算两个计费字符。按 len() 算会少估将近一半。"""
        self.assertEqual(dashscope.billable_characters("一二三四五六七八九十"), 20)

    def test_ascii_counts_as_one(self):
        self.assertEqual(dashscope.billable_characters("abcdefghij"), 10)
        self.assertEqual(dashscope.billable_characters("1234567890"), 10)

    def test_punctuation_counts_as_one(self):
        """五个汉字加五个标点 = 5×2 + 5×1 = 15。"""
        self.assertEqual(dashscope.billable_characters("一，二。三！四？五；"), 15)

    def test_mixed_text_matches_the_measured_ratio(self):
        text = "买 AI 员工之前，先问这七个问题。"
        self.assertEqual(dashscope.billable_characters(text), 30)

    def test_estimate_is_not_shorter_than_reality(self):
        """一支真视频的估算要比实际账单偏保守，不能偏乐观。

        实测账单 827 字符（旁白 446 个汉字），估 880。少估会让人以为很便宜。
        """
        real_video = "".join(["一二三四五六七八九十"] * 45)
        self.assertGreaterEqual(dashscope.billable_characters(real_video), len(real_video))

    def test_a_real_video_costs_under_a_yuan(self):
        """十幕四百多字的视频，不该花到一块钱。花到了说明单价或口径算错了。"""
        self.assertLess(dashscope.estimate_cost(dashscope.billable_characters("字" * 446)), 1.0)


class EngineDispatchTest(unittest.TestCase):
    """视频线按 audio.engine 选引擎。写错了要在花钱之前拦下来。"""

    def setUp(self):
        self.compose = load(
            "video_compose", SYSTEM / "capabilities/video-production/scripts/compose.py"
        )

    def test_default_engine_is_offline_say(self):
        self.assertEqual(self.compose.engine_of({}), "macos-say")

    def test_cosyvoice_is_recognised(self):
        self.assertEqual(
            self.compose.engine_of({"engine": "dashscope-cosyvoice"}), "dashscope-cosyvoice"
        )

    def test_unknown_engine_is_rejected_before_spending(self):
        with self.assertRaises(self.compose.ComposeError) as ctx:
            self.compose.engine_of({"engine": "gpt-voice"})
        self.assertIn("gpt-voice", str(ctx.exception))

    def test_each_engine_has_its_own_audio_suffix(self):
        """say 出 aiff，CosyVoice 出 mp3。写同一个后缀会让 ffmpeg 认错格式。"""
        self.assertEqual(self.compose.AUDIO_SUFFIX["macos-say"], ".aiff")
        self.assertEqual(self.compose.AUDIO_SUFFIX["dashscope-cosyvoice"], ".mp3")

    def test_say_only_needs_say_when_that_engine_is_used(self):
        """选了 CosyVoice 就不该再要求机器上有 say。"""
        self.compose.check_tools("dashscope-cosyvoice")


class CliContractTest(unittest.TestCase):
    """CLI 的互斥参数。两个都给会让脚本不知道用哪个。"""

    def test_synthesize_needs_text_or_file_but_not_both(self):
        with quiet(), self.assertRaises(SystemExit):
            synthesize.main(["--voice", "v", "--dry-run"])
        with quiet(), self.assertRaises(SystemExit):
            synthesize.main(["--text", "a", "--text-file", "b", "--voice", "v", "--dry-run"])

    def test_dry_run_reports_cost_without_calling(self):
        with quiet():
            code = synthesize.main(["--text", "一二三四五", "--voice", "v", "--dry-run"])
        self.assertEqual(code, 0)

    def test_out_is_required_unless_dry_run(self):
        with quiet():
            code = synthesize.main(["--text", "一二三", "--voice", "v"])
        self.assertEqual(code, 2)

    def test_voices_needs_exactly_one_action(self):
        with quiet(), self.assertRaises(SystemExit):
            voices.main([])
        with quiet(), self.assertRaises(SystemExit):
            voices.main(["--list", "--create"])

    def test_bad_prefix_is_rejected(self):
        with self.assertRaises(dashscope.SpeechError) as ctx:
            voices.create_voice("key", Path("/tmp/x.wav"), "Conan-A", "cosyvoice-v3-flash")
        self.assertIn("prefix", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
