"""
Electron 主进程 — Matha AI Assistant 桌面应用

【定位标注 2026-10 / P2 降级 · 措辞 2026-11 随阶段 3 门禁锁更新】仓库内未背书前端：本入口复用
ai_assistant_server 同一条 AI 编排链（MathaAIAssistant.chat「输入→解析→执行→结果→感知」），
其编排契约已由 tests/test_ai_e2e_pipeline.py 入门禁锁固定（阶段 6e）；桌面/启动接线
（假 HTTPServer/webbrowser 注入，不开浏览器不占端口）已由 tests/test_ai_servers_smoke.py
入门禁（阶段 3），自然语言→代码/答案的**结果正确性不背书**，不作为现功能主张；
口径见 docs/KNOWN_ISSUES.md 第七节 7c。

打包命令：
  pip install electron-builder
  electron-builder --mac --win --linux
"""
from __future__ import annotations

import os
import sys

# 确保 src 在路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))



def launch_desktop():
    """启动桌面应用（通过 webview 嵌入）。"""
    import threading
    import time
    import webbrowser

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
