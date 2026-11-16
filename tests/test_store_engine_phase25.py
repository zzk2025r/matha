# -*- coding: utf-8 -*-
"""阶段 25c 三锁：纯 Matha 应用中心引擎（matha/store_engine.matha）。

锁五面：
  A. 模块加载零杂散 —— load_matha_module("应用中心") 成功且自测块
     不泄输出（MechUnit 载入跳过语义）；
  B. 路由面 —— /health /apps /apps/<名> /search /token /publish
     /revoke 全表 + 错误面（400/401/404/405/500 诚实消息）；
  C. 持久面 —— 发布落盘 .matha/store/index.json，重载索引可见；
     索引损坏诚实 500；
  D. Matha 面 —— matha run 子进程自测块输出 + VM 面 use 应用中心
     双面路由可达；
  E. 端到端 —— 真实 socket 客户端 ↔ 25a 服务端原语驱动引擎，
     HTTP/1.1 文本往返（自举商店全链）。
所有用例 chdir 到 tmp_path，索引与密钥落 tmp 的 .matha/store/。
"""
import json
import socket
import subprocess
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

from src.interp import Interpreter  # noqa: E402
from src.kernel import exec_api  # noqa: E402
from src.parser import parse  # noqa: E402


def _engine(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ip = Interpreter()
    assert ip.load_matha_module("应用中心") is True

    def call(name, *args):
        return ip._call_func_or_closure(ip.funcs[name], list(args))

    return call


def _body(frame):
    return json.loads(frame["响应"].split("\r\n\r\n", 1)[1])


def _post(route, payload):
    return "POST " + route + " HTTP/1.1\r\nContent-Type: application/json\r\n\r\n" + \
        json.dumps(payload, ensure_ascii=False)


# ============================================================
# A. 模块加载零杂散
# ============================================================

class TestLoad:
    def test_load_zero_stray(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        ip = Interpreter()
        assert ip.load_matha_module("应用中心") is True
        assert ip.outputs == []
        assert "处理请求" in ip.funcs
        assert "解析请求" in ip.funcs

    def test_self_test_block_outputs_when_run_directly(self, tmp_path):
        r = subprocess.run(
            [sys.executable, str(ROOT / "src" / "matha_main.py"),
             "run", str(ROOT / "matha" / "store_engine.matha")],
            capture_output=True, text=True, timeout=180, cwd=str(tmp_path))
        assert r.returncode == 0, r.stderr[-500:]
        assert "方法=GET 路径=/health" in r.stdout
        assert "q=体积" in r.stdout
        assert "拒绝面=请求行须为 方法 路径 协议 三段" in r.stdout
        assert "未知路由码=404" in r.stdout
        assert "应用中心自测完成" in r.stdout


# ============================================================
# B. 路由面
# ============================================================

class TestRoutes:
    def test_health_empty_store(self, tmp_path, monkeypatch):
        call = _engine(tmp_path, monkeypatch)
        frame = call("处理请求", "GET /health HTTP/1.1\r\nHost: x\r\n\r\n")
        assert frame["码"] == 200 and frame["方法"] == "GET"
        assert _body(frame) == {"状态": "ok", "应用数": 0}

    def test_apps_list_sorted(self, tmp_path, monkeypatch):
        call = _engine(tmp_path, monkeypatch)
        tok = _body(call("处理请求", _post("/token", {"主体": "甲"})))["令牌"]
        for name in ("乙应用", "甲应用"):
            payload = {"应用": name, "版本": "1.0", "内容": "输出(1)",
                       "令牌": tok}
            assert call("处理请求", _post("/publish", payload))["码"] == 201
        frame = call("处理请求", "GET /apps HTTP/1.1\r\n\r\n")
        # list_sort 按 Unicode 码点升序：乙(U+4E59) < 甲(U+7532)
        assert _body(frame)["应用"] == ["乙应用", "甲应用"]
        assert _body(frame)["应用数"] == 2

    def test_publish_requires_token_401(self, tmp_path, monkeypatch):
        call = _engine(tmp_path, monkeypatch)
        r = call("处理请求", _post("/publish", {
            "应用": "x", "版本": "1", "内容": "输出(1)", "令牌": "a.b.c"}))
        assert r["码"] == 401
        assert "签名不符" in _body(r)["错误"] or "三段式" in _body(r)["错误"]

    def test_publish_missing_fields_400(self, tmp_path, monkeypatch):
        call = _engine(tmp_path, monkeypatch)
        tok = _body(call("处理请求", _post("/token", {"主体": "甲"})))["令牌"]
        r = call("处理请求", _post("/publish", {"应用": "x", "令牌": tok}))
        assert r["码"] == 400
        assert "发布缺字段" in _body(r)["错误"]

    def test_publish_empty_field_400(self, tmp_path, monkeypatch):
        call = _engine(tmp_path, monkeypatch)
        tok = _body(call("处理请求", _post("/token", {"主体": "甲"})))["令牌"]
        r = call("处理请求", _post("/publish", {
            "应用": "", "版本": "1", "内容": "输出(1)", "令牌": tok}))
        assert r["码"] == 400
        assert "非空字符串" in _body(r)["错误"]

    def test_bad_json_body_400(self, tmp_path, monkeypatch):
        call = _engine(tmp_path, monkeypatch)
        r = call("处理请求",
                 "POST /token HTTP/1.1\r\n\r\n{不是json")
        assert r["码"] == 400
        assert "请求体不是合法 JSON" in _body(r)["错误"]

    def test_bad_request_line_400(self, tmp_path, monkeypatch):
        call = _engine(tmp_path, monkeypatch)
        r = call("处理请求", "只有一个词\r\n\r\n")
        assert r["码"] == 400
        assert "三段" in _body(r)["错误"]

    def test_detail_404_and_search(self, tmp_path, monkeypatch):
        call = _engine(tmp_path, monkeypatch)
        tok = _body(call("处理请求", _post("/token", {"主体": "甲"})))["令牌"]
        call("处理请求", _post("/publish", {
            "应用": "计算器", "版本": "2.1", "说明": "做体积计算",
            "入口": "calc.matha", "内容": "输出(1)", "令牌": tok}))
        miss = call("处理请求", "GET /apps/不存在 HTTP/1.1\r\n\r\n")
        assert miss["码"] == 404 and "应用不存在" in _body(miss)["错误"]
        hit = call("处理请求", "GET /apps/计算器 HTTP/1.1\r\n\r\n")
        assert hit["码"] == 200
        rec = _body(hit)
        assert rec["版本"] == "2.1" and rec["说明"] == "做体积计算"
        assert rec["入口"] == "calc.matha" and rec["主体"] == "甲"
        assert rec["内容"] == "输出(1)"
        s = call("处理请求", "GET /search?q=体积 HTTP/1.1\r\n\r\n")
        assert _body(s)["命中"] == ["计算器"] and _body(s)["数量"] == 1
        s2 = call("处理请求", "GET /search?q=没有 HTTP/1.1\r\n\r\n")
        assert _body(s2)["命中"] == []

    def test_revoke_then_publish_401(self, tmp_path, monkeypatch):
        call = _engine(tmp_path, monkeypatch)
        tok = _body(call("处理请求", _post("/token", {"主体": "甲"})))["令牌"]
        assert call("处理请求", _post("/revoke", {"令牌": tok}))["码"] == 200
        r = call("处理请求", _post("/publish", {
            "应用": "x", "版本": "1", "内容": "输出(1)", "令牌": tok}))
        assert r["码"] == 401 and "已吊销" in _body(r)["错误"]
        revoke_missing = call("处理请求", _post("/revoke", {}))
        assert revoke_missing["码"] == 400 and "吊销缺字段" in _body(revoke_missing)["错误"]

    def test_method_and_route_honesty(self, tmp_path, monkeypatch):
        call = _engine(tmp_path, monkeypatch)
        assert call("处理请求", "GET /token HTTP/1.1\r\n\r\n")["码"] == 405
        assert call("处理请求", "DELETE /apps HTTP/1.1\r\n\r\n")["码"] == 405
        assert call("处理请求", "PUT /health HTTP/1.1\r\n\r\n")["码"] == 405
        r = call("处理请求", "GET /未知 HTTP/1.1\r\n\r\n")
        assert r["码"] == 404 and "未知路由" in _body(r)["错误"]

    def test_corrupt_index_500(self, tmp_path, monkeypatch):
        call = _engine(tmp_path, monkeypatch)
        d = tmp_path / ".matha" / "store"
        d.mkdir(parents=True)
        (d / "index.json").write_text("{损坏", encoding="utf-8")
        r = call("处理请求", "GET /health HTTP/1.1\r\n\r\n")
        assert r["码"] == 500 and "索引损坏" in _body(r)["错误"]
        r2 = call("处理请求", "GET /health HTTP/1.1\r\n\r\n")
        assert r2["码"] == 500


# ============================================================
# C. 持久面
# ============================================================

class TestPersistence:
    def test_publish_persists_index_and_reload_sees(self, tmp_path, monkeypatch):
        call = _engine(tmp_path, monkeypatch)
        tok = _body(call("处理请求", _post("/token", {"主体": "持久主体"})))["令牌"]
        call("处理请求", _post("/publish", {
            "应用": "持久应用", "版本": "3.0", "内容": "输出(42)", "令牌": tok}))
        disk = json.loads((tmp_path / ".matha" / "store" / "index.json")
                          .read_text(encoding="utf-8"))
        assert disk["apps"]["持久应用"]["版本"] == "3.0"
        assert disk["apps"]["持久应用"]["主体"] == "持久主体"
        frame = call("处理请求", "GET /apps/持久应用 HTTP/1.1\r\n\r\n")
        assert _body(frame)["内容"] == "输出(42)"


# ============================================================
# D. Matha 面（VM use + 子进程已测）
# ============================================================

class TestMathaFace:
    def test_vm_face_use_engine(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        src = ('use 应用中心\n'
               'let 回 = 处理请求("GET /health HTTP/1.1\\r\\n\\r\\n")\n'
               '输出(回["码"])\n'
               '输出(处理请求("GET /无 HTTP/1.1\\r\\n\\r\\n")["码"])')
        outs, err = exec_api.run_checked(src, mode="vm")
        assert err is None, str(err)
        assert outs == [200, 404]

    def test_vm_face_publish_roundtrip(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        src = ('use 应用中心\n'
               'let 令牌帧 = 处理请求("POST /token HTTP/1.1\\r\\n\\r\\n{\\"主体\\":\\"虚拟主体\\"}")\n'
               'let 令牌 = 解析_JSON(截取(令牌帧["响应"], find("\\r\\n\\r\\n", 令牌帧["响应"]) + 4, len(令牌帧["响应"])))["令牌"]\n'
               'let 发布体 = "{\\"应用\\":\\"虚拟应用\\",\\"版本\\":\\"1.0\\",\\"内容\\":\\"输出(9)\\",\\"令牌\\":\\"" + 令牌 + "\\"}"\n'
               'let 发布帧 = 处理请求("POST /publish HTTP/1.1\\r\\n\\r\\n" + 发布体)\n'
               '输出(发布帧["码"])\n'
               'let 详情帧 = 处理请求("GET /apps/虚拟应用 HTTP/1.1\\r\\n\\r\\n")\n'
               'let 详情 = 解析_JSON(截取(详情帧["响应"], find("\\r\\n\\r\\n", 详情帧["响应"]) + 4, len(详情帧["响应"])))\n'
               '输出(详情["版本"])\n'
               '输出(详情["主体"])')
        outs, err = exec_api.run_checked(src, mode="vm")
        assert err is None, str(err)
        assert outs == [201, "1.0", "虚拟主体"]


# ============================================================
# E. 端到端（真 socket ↔ 引擎）
# ============================================================

class TestSocketE2E:
    def test_http_roundtrip_over_real_socket(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        ip = Interpreter()
        assert ip.load_matha_module("应用中心") is True
        ip.run(parse('let 监听器 = 网络_服务(0)'))
        port = int(ip.env["监听器"]["端口"])
        got = {}

        def client():
            c = socket.create_connection(("127.0.0.1", port), timeout=5)
            body = json.dumps({"主体": "端到端"}, ensure_ascii=False)
            c.sendall(("POST /token HTTP/1.1\r\n"
                       "Content-Type: application/json\r\n\r\n" + body)
                      .encode("utf-8"))
            data = b""
            while True:
                chunk = c.recv(4096)
                if not chunk:
                    break
                data += chunk
            c.close()
            got["raw"] = data

        t = threading.Thread(target=client, daemon=True)
        t.start()
        ip.run(parse('let 连接帧 = 网络_接受(监听器)(5.0)\n'
                     'let 请求 = 网络_收(连接帧["连接"])(4096)\n'
                     'let 回 = 处理请求(请求)\n'
                     '网络_发(连接帧["连接"])(回["响应"])\n'
                     '网络_关闭(连接帧["连接"])\n'
                     '网络_关闭(监听器)'))
        t.join(timeout=5.0)

        raw = got["raw"].decode("utf-8")
        assert raw.startswith("HTTP/1.1 200 OK")
        assert "Connection: close" in raw
        payload = json.loads(raw.split("\r\n\r\n", 1)[1])
        assert payload["令牌"]
        assert payload["令牌"].count(".") == 2
