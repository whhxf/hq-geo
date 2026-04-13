"""
hq_geo_lib.py — HQ-GEO 公共工具函数
提供：ID 生成、CSV 安全写入、dotenv 加载、日志
"""

import os
import sys
import csv
import time
import logging
from datetime import date, datetime

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


# ── dotenv 加载 ──────────────────────────────────────────

def ensure_dotenv():
    """确保加载 .env，幂等，兼容无 dotenv 安装的环境"""
    if load_dotenv:
        load_dotenv()


# ── 日志 ─────────────────────────────────────────────────

def setup_logger(name: str = "hq-geo", log_dir: str = None) -> logging.Logger:
    """
    创建结构化日志记录器：同时输出到 stdout 和日志文件。
    日志文件自动按日期分割，保留最近 7 天。
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # 已初始化

    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # stdout: INFO 及以上
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.INFO)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    # 日志文件: DEBUG 及以上
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"hq-geo_{date.today().isoformat()}.log")
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger


# ── 路径计算 ─────────────────────────────────────────────

def get_root_dir(script_file: str) -> str:
    """从脚本路径推导项目根目录（脚本所在模块的上两级）"""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(script_file))))


# ── ID 生成 ──────────────────────────────────────────────

def generate_timestamp_id(prefix: str) -> str:
    """
    生成格式: {prefix}_YYYYMMDD_HHMMSS_NNN
    例: kw_20260414_143022_001
    """
    now = datetime.now()
    ts = now.strftime("%Y%m%d_%H%M%S")
    seq = now.microsecond // 1000
    return f"{prefix}_{ts}_{seq:03d}"


def get_next_id_sequential(prefix: str, csv_path: str) -> str:
    """
    读取 CSV 最后一条记录的序号 +1（兼容旧格式 kw_001）
    带 try/except 容错
    """
    if not os.path.exists(csv_path):
        return f"{prefix}_001"
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            return f"{prefix}_001"
        last_id = rows[-1].get("id", "")
        num_part = last_id.replace(f"{prefix}_", "")
        # 兼容新格式中的最后一段序号
        if "_" in num_part:
            num_part = num_part.split("_")[-1]
        num = int(num_part) + 1
        # 判断原格式
        if any(c.isdigit() and len(last_id) > 10 for c in last_id):
            parts = last_id.split("_")
            date_part = "_".join(parts[1:-1]) if len(parts) > 3 else ""
            if date_part:
                return f"{prefix}_{date_part}_{num:03d}"
        return f"{prefix}_{num:03d}"
    except (ValueError, KeyError, IndexError):
        return generate_timestamp_id(prefix)


# ── CSV 安全写入 ──────────────────────────────────────────

class CsvFileLock:
    """
    Windows 文件锁，防止并发写入 CSV 时数据交错。
    """

    def __init__(self, csv_path: str, timeout_sec: float = 10.0):
        self.csv_path = csv_path
        self.lock_path = csv_path + ".lock"
        self.timeout_sec = timeout_sec

    def acquire(self):
        start = time.monotonic()
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    self._lock_fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR)
                    msvcrt.locking(self._lock_fd, msvcrt.LK_NBLCK, 1)
                    return
                else:
                    import fcntl
                    self._lock_fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR)
                    fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return
            except (OSError, IOError):
                if hasattr(self, "_lock_fd"):
                    os.close(self._lock_fd)
                    self._lock_fd = None
                elapsed = time.monotonic() - start
                if elapsed >= self.timeout_sec:
                    raise TimeoutError(f"无法获取 CSV 写锁: {self.csv_path}（{self.timeout_sec}s 超时）")
                time.sleep(0.2)

    def release(self):
        try:
            if hasattr(self, "_lock_fd") and self._lock_fd is not None:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(self._lock_fd, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
                os.close(self._lock_fd)
                self._lock_fd = None
            if os.path.exists(self.lock_path):
                os.remove(self.lock_path)
        except (OSError, IOError):
            pass

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *args):
        self.release()


def csv_backup(csv_path: str) -> str:
    """
    在写入前创建 CSV 备份（.bak 文件）。
    返回备份文件路径。
    """
    if not os.path.exists(csv_path):
        return None
    backup_path = csv_path + ".bak"
    import shutil
    shutil.copy2(csv_path, backup_path)
    return backup_path


def csv_append(csv_path: str, fieldnames: list, row: dict, timeout_sec: float = 10.0,
               backup: bool = True) -> str:
    """
    带文件锁的安全 CSV 追加。
    写入前自动备份（可关闭）。
    """
    if backup:
        csv_backup(csv_path)
    lock = CsvFileLock(csv_path, timeout_sec=timeout_sec)
    with lock:
        file_exists = os.path.exists(csv_path)
        with open(csv_path, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
