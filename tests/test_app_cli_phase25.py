# -*- coding: utf-8 -*-
"""阶段 25d 三锁：matha app CLI 子命令族（src/app_cli.py）。

锁三面：
  A. 本地面 —— token/publish/list/search/install/upgrade 全链在 tmp 根目录
     经进程内引擎驱动；发布→安装→matha run 安装产物真运行闭合；
  B. 远程面 —— 真 serve 子进程（socket 驱动同一引擎）+ --store 客户端
     端到端：token/publish/list/search/install 全走真 HTTP/1.1 往返；
     无 token 远程发布诚实拒绝；连不上商店诚实降级；
  C. import-release —— Release 附件导入（本地静态 HTTP 站点替身）+
     不可达站点诚实失败。

所有用例 chdir/tmp_path 隔离；serve 进程用 Popen 终止收尾。
"""
import json
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

CLI = [sys.executable, str(ROOT / "src" / "matha_main.py"), "app"]


def _cli(*argv, cwd, timeout=180):
    return subprocess.run(CLI + list(argv), capture_output=True, text=True,
                          timeout=timeout, cwd=str(cwd))


def _wait_port(proc, timeout=60):
    """读 serve 启动行 → (端口, 已读行)。"""
    deadline = time.time() + timeout
    line = proc.stdout.readline()
    while line and time.time() < deadline:
        m = re.search(r"http://[\d.]+:(\d+)", line)
        if m:
            return int(m.group(1)), line
        line = proc.stdout.readline()
    raise RuntimeError("serve 未输出启动行")


# ============================================================
# A. 本地面
# ============================================================

class TestLocalFace:
    def test_token_and_publish_and_index(self, tmp_path):
        r = _cli("token", "--subject", "甲", cwd=tmp_path)
        assert r.returncode == 0, r.stderr[-400:]
        token = r.stdout.strip()
        assert token.count(".") == 2
        secret = tmp_path / ".matha" / "store" / "secret.key"
        assert secret.is_file()

        app = tmp_path / "demo.matha"
        app.write_text("输出(42)", encoding="utf-8")
        r = _cli("publish", "--app", "演示", "--version", "1.0",
                 "--desc", "第一个应用", "--file", str(app),
                 "--subject", "甲", cwd=tmp_path)
        assert r.returncode == 0, r.stderr[-400:]
        assert "已发布 演示" in r.stdout
        index = json.loads((tmp_path / ".matha" / "store" / "index.json")
                           .read_text(encoding="utf-8"))
        rec = index["apps"]["演示"]
        assert rec["版本"] == "1.0" and rec["说明"] == "第一个应用"
        assert rec["入口"] == "main.matha" and rec["内容"] == "输出(42)"
        assert rec["主体"] == "甲"

    def test_publish_content_flag(self, tmp_path):
        r = _cli("publish", "--app", "内联", "--version", "0.1",
                 "--content", "输出(1)", cwd=tmp_path)
        assert r.returncode == 0, r.stderr[-400:]
        assert "已发布 内联" in r.stdout

    def test_publish_content_source_conflict_and_missing(self, tmp_path):
        r = _cli("publish", "--app", "x", "--version", "1",
                 "--file", "a.matha", "--content", "y", cwd=tmp_path)
        assert r.returncode == 1 and "二选一" in r.stderr
        r = _cli("publish", "--app", "x", "--version", "1", cwd=tmp_path)
        assert r.returncode == 1 and "--file 或 --content" in r.stderr
        r = _cli("publish", "--app", "x", "--version", "1",
                 "--file", str(tmp_path / "无.matha"), cwd=tmp_path)
        assert r.returncode == 1 and "不存在" in r.stderr

    def test_list_search(self, tmp_path):
        _cli("publish", "--app", "计算器", "--version", "1.0",
             "--desc", "做体积计算", "--content", "输出(1)", cwd=tmp_path)
        _cli("publish", "--app", "画板", "--version", "2.0",
             "--desc", "涂鸦", "--content", "输出(2)", cwd=tmp_path)
        r = _cli("list", cwd=tmp_path)
        assert r.returncode == 0
        # 码点升序：画(U+753B) < 计(U+8BA1)
        assert r.stdout.split() == ["画板", "计算器"]
        r = _cli("search", "--word", "体积", cwd=tmp_path)
        assert r.stdout.split() == ["计算器"]
        r = _cli("search", "--word", "不存在的词", cwd=tmp_path)
        assert r.returncode == 0 and r.stdout.strip() == ""

    def test_install_runs_published_app(self, tmp_path):
        _cli("publish", "--app", "演示", "--version", "3.1",
             "--content", "输出(123)", cwd=tmp_path)
        r = _cli("install", "--app", "演示", cwd=tmp_path)
        assert r.returncode == 0, r.stderr[-400:]
        assert "已安装 演示 版本 3.1" in r.stdout
        installed = tmp_path / ".matha" / "apps" / "演示" / "main.matha"
        assert installed.read_text(encoding="utf-8") == "输出(123)"
        manifest = json.loads((installed.parent / "manifest.json")
                              .read_text(encoding="utf-8"))
        assert manifest["版本"] == "3.1" and manifest["来源"] == "本地索引"
        run = subprocess.run(
            [sys.executable, str(ROOT / "src" / "matha_main.py"),
             "run", str(installed)],
            capture_output=True, text=True, timeout=120, cwd=str(tmp_path))
        assert run.returncode == 0 and run.stdout.strip() == "123"

    def test_install_version_mismatch_and_missing_app(self, tmp_path):
        _cli("publish", "--app", "演示", "--version", "3.1",
             "--content", "输出(1)", cwd=tmp_path)
        r = _cli("install", "--app", "演示", "--version", "9.9", cwd=tmp_path)
        assert r.returncode == 1 and "版本不符" in r.stderr
        assert "3.1" in r.stderr and "9.9" in r.stderr
        r = _cli("install", "--app", "不存在", cwd=tmp_path)
        assert r.returncode == 1 and "应用不存在" in r.stderr

    def test_upgrade_flow(self, tmp_path):
        _cli("publish", "--app", "演示", "--version", "1.0",
             "--content", "输出(1)", cwd=tmp_path)
        r = _cli("upgrade", "--app", "演示", "--version", "2.0",
                 "--content", "输出(2)", cwd=tmp_path)
        assert r.returncode == 0, r.stderr[-400:]
        assert "已升级 演示: 1.0 → 2.0" in r.stdout
        index = json.loads((tmp_path / ".matha" / "store" / "index.json")
                           .read_text(encoding="utf-8"))
        assert index["apps"]["演示"]["版本"] == "2.0"
        assert index["apps"]["演示"]["内容"] == "输出(2)"
        r = _cli("upgrade", "--app", "没有", "--version", "1.0",
                 "--content", "y", cwd=tmp_path)
        assert r.returncode == 1 and "应用不存在" in r.stderr and "publish" in r.stderr

    def test_remote_publish_without_token_honest_local_ok(self, tmp_path):
        r = _cli("publish", "--app", "x", "--version", "1",
                 "--content", "y", "--store", "http://127.0.0.1:1", cwd=tmp_path)
        assert r.returncode == 1 and "--token" in r.stderr


# ============================================================
# B. 远程面（真 serve 子进程 + --store 客户端）
# ============================================================

class TestServeE2E:
    @pytest.fixture()
    def serve(self, tmp_path):
        proc = subprocess.Popen(
            CLI + ["serve", "--port", "0", "--root", str(tmp_path)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            cwd=str(tmp_path))
        try:
            port, _ = _wait_port(proc)
            yield tmp_path, f"http://127.0.0.1:{port}"
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()

    def test_full_remote_roundtrip(self, serve, tmp_path):
        root, store = serve
        r = _cli("token", "--subject", "远程甲", "--store", store, cwd=root)
        assert r.returncode == 0, r.stderr[-400:]
        token = r.stdout.strip()
        assert token.count(".") == 2

        r = _cli("publish", "--app", "远程应用", "--version", "1.2",
                 "--desc", "真socket发布", "--content", "输出(7)",
                 "--store", store, "--token", token, cwd=root)
        assert r.returncode == 0, r.stderr[-400:]
        assert "已发布 远程应用" in r.stdout

        r = _cli("list", "--store", store, cwd=root)
        assert r.stdout.split() == ["远程应用"]
        r = _cli("search", "--word", "socket", "--store", store, cwd=root)
        assert r.stdout.split() == ["远程应用"]

        r = _cli("install", "--app", "远程应用", "--store", store, cwd=root)
        assert r.returncode == 0 and "已安装 远程应用 版本 1.2" in r.stdout
        installed = root / ".matha" / "apps" / "远程应用" / "main.matha"
        assert installed.read_text(encoding="utf-8") == "输出(7)"

        index = json.loads((root / ".matha" / "store" / "index.json")
                           .read_text(encoding="utf-8"))
        assert index["apps"]["远程应用"]["主体"] == "远程甲"

    def test_remote_publish_without_token_refused(self, serve):
        root, store = serve
        r = _cli("publish", "--app", "x", "--version", "1",
                 "--content", "y", "--store", store, cwd=root)
        assert r.returncode == 1 and "--token" in r.stderr

    def test_unreachable_store_honest(self, tmp_path):
        # 占用一个端口再释放，保证「无服务监听」
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        dead_port = s.getsockname()[1]
        s.close()
        r = _cli("list", "--store", f"http://127.0.0.1:{dead_port}",
                 cwd=tmp_path, timeout=60)
        assert r.returncode == 1 and "无法连接商店" in r.stderr


# ============================================================
# C. import-release
# ============================================================

class TestImportRelease:
    @pytest.fixture()
    def release_site(self, tmp_path):
        asset = ("输出(9)\n"
                 "# 模拟 Release 附件\n")
        holder = {"data": asset.encode("utf-8")}

        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                path = urllib.parse.unquote(self.path)
                if path == "/示例组/仓库/releases/download/v1.0/示例.matha":
                    body = holder["data"]
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self.send_error(404)

            def log_message(self, *a):
                pass

        srv = HTTPServer(("127.0.0.1", 0), H)
        port = srv.server_address[1]
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        try:
            yield f"http://127.0.0.1:{port}"
        finally:
            srv.shutdown()
            srv.server_close()

    def test_import_installs_asset(self, release_site, tmp_path):
        r = _cli("import-release", "--repo", "示例组/仓库", "--tag", "v1.0",
                 "--asset", "示例.matha", "--app", "发行应用",
                 "--base-url", release_site, cwd=tmp_path)
        assert r.returncode == 0, r.stderr[-400:]
        assert "已导入 发行应用" in r.stdout
        installed = tmp_path / ".matha" / "apps" / "发行应用" / "main.matha"
        assert "输出(9)" in installed.read_text(encoding="utf-8")
        manifest = json.loads((installed.parent / "manifest.json")
                              .read_text(encoding="utf-8"))
        assert manifest["版本"] == "v1.0"
        # 来源记录真实下载 URL（非 ASCII 段经百分号编码上线）
        assert manifest["来源"].startswith(release_site)
        assert "releases/download/v1.0" in manifest["来源"]

    def test_import_default_app_name_and_404_honest(self, release_site, tmp_path):
        r = _cli("import-release", "--repo", "示例组/仓库", "--tag", "v1.0",
                 "--asset", "示例.matha", "--base-url", release_site,
                 cwd=tmp_path)
        assert r.returncode == 0
        assert (tmp_path / ".matha" / "apps" / "示例" / "main.matha").is_file()
        r = _cli("import-release", "--repo", "示例组/仓库", "--tag", "v2.0",
                 "--asset", "示例.matha", "--base-url", release_site,
                 cwd=tmp_path)
        assert r.returncode == 1 and "404" in r.stderr

    def test_import_unreachable_site_honest(self, tmp_path):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        dead_port = s.getsockname()[1]
        s.close()
        r = _cli("import-release", "--repo", "a/b", "--tag", "v1",
                 "--asset", "x.matha",
                 "--base-url", f"http://127.0.0.1:{dead_port}", cwd=tmp_path)
        assert r.returncode == 1 and "导入失败" in r.stderr
