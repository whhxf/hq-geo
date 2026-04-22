#!/usr/bin/env python3
"""
query_ai_platform.py
向目标 AI 平台发送关键词查询，返回品牌提及和引用信息。
使用 Playwright 复用本地浏览器登录态。

用法：
  python query_ai_platform.py --keyword "AI 搜索优化工具哪个好" --platform doubao [--attempts 3] [--headless]
"""

import argparse
import json
import os
import re
import sys
import time
import random

# 添加 lib 到路径
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "lib"))
from hq_geo_lib import ensure_dotenv, setup_logger

ensure_dotenv()
logger = setup_logger("query_ai_platform", log_dir=os.path.join(ROOT, "logs"))

# 各平台配置
PLATFORM_CONFIG = {
    "doubao": {
        "url": "https://www.doubao.com/chat/",
        "name": "豆包",
        "input_selector": 'textarea[placeholder]',
        "send_selector": 'button[type="submit"], button[aria-label*="发送"]',
        "response_js": """() => {
            const lists = document.querySelectorAll('[class*="message-list"]');
            if (!lists.length) return '';
            const list = lists[0];
            const t = list.textContent || '';
            return t.trim();
        }""",
        "wait_ms": 12000,
    },
    "deepseek": {
        "url": "https://chat.deepseek.com/",
        "name": "DeepSeek",
        "input_selector": 'textarea',
        "send_selector": 'div._52c986b',
        "response_js": """() => {
            const container = document.querySelector('.ds-virtual-list');
            if (!container) return '';
            return (container.textContent || '').trim();
        }""",
        "wait_ms": 15000,
    },
    "chatgpt": {
        "url": "https://chat.openai.com/",
        "name": "ChatGPT",
        "input_selector": '#prompt-textarea',
        "send_selector": 'button[data-testid="send-button"]',
        "response_js": """() => {
            const els = document.querySelectorAll('[data-message-author-role="assistant"]');
            if (!els.length) return '';
            return Array.from(els).map(e => e.textContent || '').join('\\n').trim();
        }""",
        "wait_ms": 15000,
    },
    "perplexity": {
        "url": "https://www.perplexity.ai/",
        "name": "Perplexity",
        "input_selector": 'textarea[placeholder]',
        "send_selector": 'button[aria-label*="Submit"], button[type="submit"]',
        "response_js": """() => {
            const els = document.querySelectorAll('[class*="prose"], [class*="answer"]');
            if (!els.length) return '';
            return els[0].textContent || '';
        }""",
        "wait_ms": 15000,
    },
}


def extract_brands_and_urls(text: str, brand_name: str, competitors: list, keyword: str = "") -> dict:
    """从响应文本中提取品牌提及和 URL

    豆包的 text 可能包含整个页面的文本，需要从中提取 AI 回复部分。
    """
    mentioned_brands = []
    all_brands = [brand_name] + competitors

    # 如果文本过长（超过 1000 字符），尝试从中提取 AI 回复部分
    if len(text) > 1000 and keyword:
        kw_pos = text.find(keyword)
        if kw_pos >= 0:
            # 从关键词位置往后截取
            text = text[kw_pos:]
            # 再取后面 3000 字符（足够包含 AI 回复）
            if len(text) > 3000:
                text = text[:3000]

    for brand in all_brands:
        if brand and brand.lower() in text.lower():
            mentioned_brands.append(brand)

    # 提取 URL
    url_pattern = r'https?://[^\s\)\]\>\"\'，。]+'
    cited_urls = list(set(re.findall(url_pattern, text)))

    # 判断答案结构
    structure = "paragraph"
    if re.search(r'^\s*[-\*\d]+[\.\)]\s', text, re.MULTILINE):
        structure = "list"
    if re.search(r'\|.*\|', text):
        structure = "table"
    if re.search(r'(Q:|问：|问题：).+\n.*(A:|答：|答案：)', text, re.IGNORECASE):
        structure = "faq"

    return {
        "mentioned_brands": mentioned_brands,
        "cited_urls": cited_urls[:5],  # 最多保留5个
        "answer_structure": structure,
    }


def detect_captcha(page) -> bool:
    """检测页面是否出现验证码（CAPTCHA）"""
    # 先排除登录页/注册页——这些页面本身不含验证码
    if any(skip in page.url.lower() for skip in ["sign_in", "sign-up", "login", "register"]):
        return False
    captcha_indicators = [
        # 常见验证码文字
        "captcha", "verification", "验证", "人机", "滑块",
        # 常见验证码元素 ID/class
        "captcha-container", "captcha-box", "geetest", "recaptcha",
        # 豆包验证码
        "verify.doubao.com",
    ]
    # 检查 URL（排除已跳过的登录页）
    if any(ind in page.url.lower() for ind in ["captcha", "verification"]):
        return True
    # 检查页面文本
    try:
        body_text = page.inner_text("body").lower()
        if any(ind in body_text for ind in ["captcha", "verification", "请完成验证", "人机验证", "滑块验证"]):
            return True
    except Exception:
        pass
    # 检查常见验证码元素
    for selector in [".captcha", "#captcha", ".geetest", "[class*='captcha']", "[class*='verify']"]:
        try:
            if page.query_selector(selector):
                return True
        except Exception:
            pass
    return False


def wait_for_response(page, config: dict, timeout_sec: float = 90.0) -> str:
    """
    轮询等待 AI 响应生成完成。
    使用平台特定的 JS 提取器读取响应文本。

    策略：
    1. 先等 AI 开始响应（内容 > 100 字）
    2. 然后再等内容连续稳定 N 秒（默认 8 秒），确保流式生成完全结束
    """
    response_js = config.get("response_js")
    start = time.time()
    poll_interval = 1.0
    last_text = ""
    last_length = 0
    stable_seconds = 0
    waiting_for_start = True  # 先等 AI 开始响应

    while time.time() - start < timeout_sec:
        try:
            if response_js:
                text = page.evaluate(response_js)
            else:
                text = ""
            text_len = len(text) if text else 0

            if waiting_for_start:
                if text_len > 100:
                    # AI 开始响应了
                    waiting_for_start = False
                    last_text = text
                    last_length = text_len
                    stable_seconds = 0
            else:
                # 已经在生成中，检查是否停止增长
                if text_len == last_length:
                    stable_seconds += poll_interval
                    if stable_seconds >= 8:  # 连续 8 秒没变化，认为完成
                        return text
                else:
                    stable_seconds = 0
                    last_length = text_len
                    last_text = text
        except Exception:
            pass
        time.sleep(poll_interval)

    # 超时：返回最后一次拿到的内容
    if last_text and len(last_text) > 50:
        return last_text

    # fallback: 尝试读取 body 文本
    try:
        body_text = page.inner_text("body")
        return body_text[-3000:] if len(body_text) > 3000 else body_text
    except Exception:
        return ""


def wait_for_login(page, config: dict, timeout_sec: float = 120.0) -> bool:
    """
    等待用户完成登录。
    轮询检查输入框是否出现（表示已登录）。
    返回 True 表示登录成功，False 表示超时。
    """
    start = time.time()
    while time.time() - start < timeout_sec:
        try:
            input_el = page.query_selector(config["input_selector"])
            if input_el:
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


def query_platform(keyword: str, platform: str, attempts: int = 3,
                   brand_name: str = "", competitors: list = None,
                   headless: bool = False) -> dict:
    """向指定 AI 平台查询关键词，返回结构化结果"""
    if competitors is None:
        competitors = []

    if platform not in PLATFORM_CONFIG:
        return {"error": f"不支持的平台: {platform}，可选: {list(PLATFORM_CONFIG.keys())}"}

    config = PLATFORM_CONFIG[platform]

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"error": "请先安装 playwright: pip install playwright && playwright install chromium"}

    results = []
    delay_min = int(os.getenv("MONITOR_DELAY_MIN", 3))
    delay_max = int(os.getenv("MONITOR_DELAY_MAX", 8))

    # 使用 Playwright 自带的 Chromium
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    root_dir = os.path.dirname(script_dir)
    pw_profile_dir = os.path.join(root_dir, ".playwright-profile")
    os.makedirs(pw_profile_dir, exist_ok=True)

    logger.info("浏览器启动 | platform=%s | headless=%s | profile=%s", platform, headless, pw_profile_dir)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=pw_profile_dir,
            headless=headless,
        )

        # 第一步：打开页面并等待登录
        page = context.new_page()
        try:
            page.goto(config["url"], timeout=30000)
            try:
                page.wait_for_load_state("domcontentloaded", timeout=10000)
            except Exception:
                pass
            time.sleep(3)

            # 检查是否需要登录
            input_el = page.query_selector(config["input_selector"])
            if not input_el:
                # 可能需要登录，等待用户操作
                logger.warning("等待登录 | platform=%s | url=%s", platform, page.url)
                print(f"\n⚠️  请先在浏览器中登录 {config['name']}，登录后脚本将自动继续...")
                if wait_for_login(page, config, timeout_sec=120.0):
                    logger.info("登录成功 | platform=%s", platform)
                    print("✅ 检测到登录成功，开始查询...\n")
                else:
                    logger.error("登录超时 | platform=%s", platform)
                    context.close()
                    return {"error": "login_timeout", "platform": platform,
                            "message": f"等待 {config['name']} 登录超时（120秒），请重试"}
        except Exception as e:
            logger.error("页面打开失败 | platform=%s | error=%s", platform, str(e))
            context.close()
            return {"error": "page_load_failed", "platform": platform, "message": str(e)}
        finally:
            page.close()

        # 第二步：执行查询
        for attempt in range(1, attempts + 1):
            page = context.new_page()
            try:
                page.goto(config["url"], timeout=30000)
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=10000)
                except Exception:
                    pass
                time.sleep(3)  # 额外等待页面 JS 渲染

                # 检查验证码
                if detect_captcha(page):
                    logger.error("CAPTCHA 检测到 | platform=%s | url=%s", platform, page.url)
                    print(f"\n⚠️  检测到验证码，请在浏览器中完成验证后继续...")
                    # 等待验证码解决（最多60秒）
                    time.sleep(5)
                    for _ in range(12):
                        if not detect_captcha(page):
                            break
                        time.sleep(5)
                    if detect_captcha(page):
                        results.append({"attempt": attempt, "error": "captcha_not_resolved",
                                        "raw_text": "", "mentioned_brands": [],
                                        "cited_urls": [], "answer_structure": "unknown"})
                        page.close()
                        continue

                # 找到输入框
                try:
                    input_el = page.wait_for_selector(config["input_selector"], timeout=8000)
                except Exception:
                    results.append({"attempt": attempt, "error": "input_not_found",
                                    "raw_text": "", "mentioned_brands": [],
                                    "cited_urls": [], "answer_structure": "unknown"})
                    page.close()
                    continue

                # 清空并输入查询词
                input_el.click()
                input_el.fill("")
                input_el.type(keyword, delay=80)
                time.sleep(0.5)

                # 发送
                try:
                    send_btn = page.wait_for_selector(config["send_selector"], timeout=5000)
                    send_btn.click()
                except Exception:
                    input_el.press("Enter")

                # 等待响应生成（轮询，非固定 sleep）
                raw_text = wait_for_response(page, config, timeout_sec=90.0)

                extracted = extract_brands_and_urls(raw_text, brand_name, competitors, keyword)
                logger.info("响应提取 | attempt=%d | len=%d | brands=%s | urls=%d",
                           attempt, len(raw_text), extracted.get("mentioned_brands", []),
                           len(extracted.get("cited_urls", [])))
                results.append({
                    "attempt": attempt,
                    "raw_text": raw_text,  # 不截断，完整保留
                    **extracted,
                })

            except Exception as e:
                results.append({"attempt": attempt, "error": str(e),
                                "raw_text": "", "mentioned_brands": [],
                                "cited_urls": [], "answer_structure": "unknown"})
            finally:
                page.close()

            if attempt < attempts:
                sleep_sec = random.uniform(delay_min, delay_max)
                time.sleep(sleep_sec)

        context.close()

    return {
        "platform": platform,
        "keyword": keyword,
        "responses": results,
    }


def load_brand_info():
    """读取 brand.csv 中的品牌信息"""
    import csv
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    brand_csv = os.path.join(root, "data", "brand.csv")
    info = {}
    if os.path.exists(brand_csv):
        with open(brand_csv, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                info[row["field"]] = row["value"]
    return info


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="查询 AI 平台上的关键词引用情况")
    parser.add_argument("--keyword", required=True, help="要查询的关键词")
    parser.add_argument("--platform", required=True,
                        choices=list(PLATFORM_CONFIG.keys()),
                        help=f"目标平台: {', '.join(PLATFORM_CONFIG.keys())}")
    parser.add_argument("--attempts", type=int, default=3, help="查询次数（默认3次）")
    parser.add_argument("--headless", action="store_true",
                        help="无头模式（无需显示器，适合服务器/Cron）")
    args = parser.parse_args()

    brand = load_brand_info()
    brand_name = brand.get("brand_name", "")
    competitors_raw = brand.get("competitors", "")
    competitors = [c.strip() for c in competitors_raw.split(",") if c.strip()]

    result = query_platform(
        keyword=args.keyword,
        platform=args.platform,
        attempts=args.attempts,
        brand_name=brand_name,
        competitors=competitors,
        headless=args.headless,
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))
