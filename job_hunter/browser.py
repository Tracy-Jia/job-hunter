"""浏览器连接：CDP 连接本地 Chrome/Chromium 浏览器。"""

import socket
import subprocess
import sys
import time
from pathlib import Path

from DrissionPage import ChromiumPage


def _find_browser_path(config: dict | None = None) -> str:
    """从配置或系统默认路径中查找浏览器可执行文件路径。"""
    cfg_paths = []
    if config and "browser" in config:
        cfg_paths = config["browser"].get("paths", [])

    default_paths = []
    if sys.platform == "win32":
        default_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
    elif sys.platform == "darwin":
        default_paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ]
    else:
        default_paths = [
            "/usr/bin/google-chrome",
            "/usr/bin/chromium-browser",
        ]

    all_paths = cfg_paths + [p for p in default_paths if p not in cfg_paths]
    for p in all_paths:
        if Path(p).exists():
            return p
    return ""


def connect_chrome(port: int | None = None, config: dict | None = None) -> ChromiumPage:
    """CDP 连接本地浏览器。

    优先通过 CDP 端口连接已运行的浏览器；若端口未开启，自动启动配置中指定的浏览器。
    port 默认从 config['browser']['port'] 读取，兜底 9222。
    """
    if config is None:
        config = {}
    if port is None:
        port = config.get("browser", {}).get("port", 9222)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    port_open = sock.connect_ex(("127.0.0.1", port)) == 0
    sock.close()

    if port_open:
        return ChromiumPage(f"127.0.0.1:{port}")

    browser_path = _find_browser_path(config)
    if not browser_path:
        raise FileNotFoundError(
            "未找到可用的 Chrome/Chromium 浏览器。请在 config.json 的 browser.paths 中配置路径。"
        )

    subprocess.Popen([browser_path, f"--remote-debugging-port={port}"])
    time.sleep(3)
    return ChromiumPage(f"127.0.0.1:{port}")
