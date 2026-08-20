# -*- coding: utf-8 -*-
"""
Electron 主进程 — Matha AI Assistant 桌面应用

打包命令：
  pip install electron-builder
  electron-builder --mac --win --linux
"""
from __future__ import annotations
import sys
import os

# 确保 src 在路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ai_assistant import MathaAIAssistant
from src.interp import Interpreter


def launch_desktop():
    """启动桌面应用（通过 webview 嵌入）。"""
    import webbrowser
    import threading
    import time

    # 启动后端服务
    from src.ai_assistant_server import APIHandler, HTTPServer
    server = HTTPServer(('127.0.0.1', 8080), APIHandler)

    def run_server():
        server.serve_forever()

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    time.sleep(0.5)  # 等待服务器启动

    print("🧮 Matha AI Assistant 桌面版已启动")
    print("📍 浏览器已打开: http://127.0.0.1:8080")
    print("💡 按 Ctrl+C 关闭")

    webbrowser.open('http://127.0.0.1:8080')

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.shutdown()
        print("\n已关闭。")


if __name__ == '__main__':
    launch_desktop()
