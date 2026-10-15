#!/usr/bin/env python3
"""最小 WebSocket 客户端（RFC 6455）。只用标准库。

**为什么要自己写。** CosyVoice 的合成接口只有 WebSocket，没有 HTTP。
系统宪法第 187 行写着「新系统只使用标准库，不引入第三方依赖」，
而 Python 标准库没有 WebSocket 客户端。所以这里按 RFC 6455 写一个够用的。

**够用**指：文本帧、二进制帧、分片、ping/pong、close、掩码。
**不做**：permessage-deflate（服务端不要求）、重连、代理、扩展协商。
多了就是自己造一个库，那是另一种负担。

服务端发来的帧不带掩码，客户端发出去的一定带掩码——这是协议规定，
写反了服务端会直接断连。
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import ssl
import struct
import urllib.parse

OP_CONT = 0x0
OP_TEXT = 0x1
OP_BINARY = 0x2
OP_CLOSE = 0x8
OP_PING = 0x9
OP_PONG = 0xA

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class WebSocketError(Exception):
    """连不上、握不上手、或读到半帧。消息写给执行者看。"""


def _handshake(sock, host, path, headers) -> bytes:
    key = base64.b64encode(os.urandom(16)).decode()
    lines = [
        f"GET {path} HTTP/1.1",
        f"Host: {host}",
        "Upgrade: websocket",
        "Connection: Upgrade",
        f"Sec-WebSocket-Key: {key}",
        "Sec-WebSocket-Version: 13",
    ]
    for name, value in headers.items():
        lines.append(f"{name}: {value}")
    sock.sendall(("\r\n".join(lines) + "\r\n\r\n").encode("latin-1"))

    raw = b""
    while b"\r\n\r\n" not in raw:
        chunk = sock.recv(4096)
        if not chunk:
            raise WebSocketError(f"握手时连接被关闭，只收到 {raw[:200]!r}")
        raw += chunk
    head, _, rest = raw.partition(b"\r\n\r\n")
    text = head.decode("latin-1")
    status = text.split("\r\n", 1)[0]

    # 101 之前先认 401/403：那是密钥的问题，不是协议的问题。
    if " 401" in status or " 403" in status:
        raise WebSocketError(f"鉴权失败：{status}\n{text[:400]}")
    if "101" not in status:
        raise WebSocketError(f"握手失败：{status}\n{text[:400]}")

    expected = base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()
    if expected.lower() not in text.lower():
        raise WebSocketError(f"Sec-WebSocket-Accept 对不上，可能不是 WebSocket 服务端：{text[:300]}")
    return rest


class Connection:
    def __init__(self, url: str, headers: dict | None = None, timeout: float = 30):
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme not in ("ws", "wss"):
            raise WebSocketError(f"只支持 ws/wss：{url}")
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "wss" else 80)
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query

        raw = socket.create_connection((host, port), timeout=timeout)
        if parsed.scheme == "wss":
            raw = ssl.create_default_context().wrap_socket(raw, server_hostname=host)
        raw.settimeout(timeout)
        self.sock = raw
        self.buffer = _handshake(raw, host, path, headers or {})
        self.closed = False

    # ---- 发送 ----

    def _frame(self, opcode: int, payload: bytes) -> bytes:
        header = bytearray([0x80 | opcode])
        length = len(payload)
        if length < 126:
            header.append(0x80 | length)
        elif length < (1 << 16):
            header.append(0x80 | 126)
            header += struct.pack("!H", length)
        else:
            header.append(0x80 | 127)
            header += struct.pack("!Q", length)
        mask = os.urandom(4)
        header += mask
        return bytes(header) + bytes(b ^ mask[i % 4] for i, b in enumerate(payload))

    def send_text(self, text: str) -> None:
        self.sock.sendall(self._frame(OP_TEXT, text.encode("utf-8")))

    def send_json(self, obj) -> None:
        self.send_text(json.dumps(obj, ensure_ascii=False))

    def _send_control(self, opcode: int, payload: bytes = b"") -> None:
        self.sock.sendall(self._frame(opcode, payload))

    # ---- 接收 ----

    def _read(self, count: int) -> bytes:
        while len(self.buffer) < count:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise WebSocketError("连接在读满一帧之前被关闭")
            self.buffer += chunk
        data, self.buffer = self.buffer[:count], self.buffer[count:]
        return data

    def _read_header(self):
        first, second = self._read(2)
        fin = bool(first & 0x80)
        opcode = first & 0x0F
        masked = bool(second & 0x80)
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._read(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._read(8))[0]
        mask = self._read(4) if masked else b""
        return fin, opcode, mask, length

    def _read_payload(self, mask: bytes, length: int) -> bytes:
        payload = self._read(length) if length else b""
        if mask:
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        return payload

    def recv(self) -> tuple:
        """返回 (opcode, payload)。分片已经拼好，ping 已经自动回 pong。"""
        while True:
            fin, opcode, mask, length = self._read_header()
            payload = self._read_payload(mask, length)

            if opcode == OP_PING:
                self._send_control(OP_PONG, payload)
                continue
            if opcode == OP_PONG:
                continue
            if opcode == OP_CLOSE:
                self.closed = True
                return OP_CLOSE, payload
            if fin:
                return opcode, payload

            # 分片：把后续的 continuation 帧拼起来
            chunks = [payload]
            while True:
                fin, opcode2, mask2, length2 = self._read_header()
                piece = self._read_payload(mask2, length2)
                if opcode2 == OP_PING:
                    self._send_control(OP_PONG, piece)
                    continue
                if opcode2 == OP_PONG:
                    continue
                chunks.append(piece)
                if fin:
                    break
            return opcode, b"".join(chunks)

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            self._send_control(OP_CLOSE, struct.pack("!H", 1000))
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass
