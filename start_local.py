"""可转债策略池的本地一键启动入口。

在项目根目录运行：python3 start_local.py
首次会安装依赖、生成最新快照，然后在 http://127.0.0.1:8000 打开网页。
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def ensure_dependencies() -> None:
    if importlib.util.find_spec("akshare") is None:
        print("首次运行：正在安装数据依赖，请稍等…")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            cwd=ROOT,
            check=True,
        )


def main() -> None:
    ensure_dependencies()
    print("正在读取公开可转债行情…")
    subprocess.run([sys.executable, "scripts/update_pool.py"], cwd=ROOT, check=True)
    print("\n数据已生成。请在浏览器打开：http://127.0.0.1:8000")
    print("停止服务请回到这个终端按 Ctrl+C。")
    server = ThreadingHTTPServer(("127.0.0.1", 8000), SimpleHTTPRequestHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
