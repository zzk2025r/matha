# -*- coding: utf-8 -*-
"""阶段 25a 三锁：socket 服务端真化（可句柄化诚实服务端面）。

锁四面：
  A. 原语往返 —— 网络_服务(0) 临时端口 / 网络_接受 → 收发回环 / 网络_关闭；
     无连接超时 {"超时": True}；
  B. 诚实拒绝 —— 端口越界、目标形态错（接受/收/发/关闭）、占用端口绑定失败；
  C. 假面清算 + 三表 parity —— 旧 5 符号（网络连接/网络绑定/网络监听/
     Socket发送/Socket接收）不再注册；symtab == manifest == registry；
  D. Matha 面程序闭环 —— 纯 Matha 源码经独立 Interpreter 驱动
     服务→接受→收→发→关闭 全链（宿主面端到端）+ VM 面经阶段 21
     插件接线同样可达（服务→关闭 闭环）。
"""
import json
import socket
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

MANIFEST = json.loads(
    (ROOT / "src" / "domains" / "manifest.json").read_text(encoding="utf-8"))

from src.domains.networking import (  # noqa: E402
    _networking_symtab_names,
    _register_networking,
)
from src.kernel import exec_api  # noqa: E402
from src.parser import parse  # noqa: E402
from src.interp import Interpreter  # noqa: E402


def _builtins():
    b = {}
    _register_networking(b)
    return b


# ============================================================
# A. 原语往返
# ============================================================

class TestSocketRoundTrip:
    def test_serve_ephemeral_port(self):
        b = _builtins()
        lis = b["网络_服务"](0)
        assert lis["端口"] > 0 and lis["主机"]
        b["网络_关闭"](lis)

    def test_accept_recv_send_close_roundtrip(self):
        b = _builtins()
        lis = b["网络_服务"](0)
        port = lis["端口"]

        got = {}

        def client():
            c = socket.socket()
            c.settimeout(5.0)
            c.connect(("127.0.0.1", port))
            c.sendall("你好服务端".encode("utf-8"))
            got["reply"] = c.recv(1024).decode("utf-8")
            got["addr_seen"] = True
            c.close()

        t = threading.Thread(target=client, daemon=True)
        t.start()
        conn = b["网络_接受"](lis)(2.0)
        assert conn["超时"] is False
        assert conn["地址"][0] == "127.0.0.1"
        assert b["网络_收"](conn["连接"])(1024) == "你好服务端"
        n = b["网络_发"](conn["连接"])("ack-回执")
        assert n > 0
        t.join(timeout=5.0)
        assert got.get("reply") == "ack-回执"
        assert b["网络_关闭"](conn["连接"]) is True
        b["网络_关闭"](lis)

    def test_accept_timeout_returns_honest_shape(self):
        b = _builtins()
        lis = b["网络_服务"](0)
        t0 = time.monotonic()
        r = b["网络_接受"](lis)(0.2)
        assert r == {"超时": True}
        assert time.monotonic() - t0 < 3.0
        b["网络_关闭"](lis)


# ============================================================
# B. 诚实拒绝
# ============================================================

class TestSocketHonest:
    def test_serve_port_range_reject(self):
        b = _builtins()
        for bad in (-1, 70000, "80", 1.5):
            with pytest.raises(ValueError, match="端口须为"):
                b["网络_服务"](bad)

    @pytest.mark.skipif(sys.platform == "win32",
                        reason="Windows SO_REUSEADDR 为强制复用语义（可重复绑定）"
                               "，绑定失败 ValueError 路径 POSIX 可复现")
    def test_serve_bind_failure_honest(self, tmp_path):
        b = _builtins()
        lis = b["网络_服务"](0)
        port = lis["端口"]
        with pytest.raises(ValueError, match="绑定失败"):
            b["网络_服务"](port)
        b["网络_关闭"](lis)

    def test_wrong_target_shapes(self):
        b = _builtins()
        with pytest.raises(ValueError, match="须为 网络_服务"):
            b["网络_接受"]("不是监听器")(1.0)
        with pytest.raises(ValueError, match="须为 网络_接受"):
            b["网络_收"]({"套接字": "假"})(16)
        with pytest.raises(ValueError, match="须为 网络_接受"):
            b["网络_发"]({"套接字": "假"})("x")
        with pytest.raises(ValueError, match="目标须为"):
            b["网络_关闭"](42)


# ============================================================
# C. 假面清算 + 三表 parity
# ============================================================

OLD_DEAD_SOCKET_NAMES = {"网络连接", "网络绑定", "网络监听",
                         "Socket发送", "Socket接收"}


class TestFakeFaceCleared:
    def test_old_names_unregistered(self):
        b = _builtins()
        assert not (OLD_DEAD_SOCKET_NAMES & set(b))

    def test_symtab_matches_registration(self):
        b = _builtins()
        assert set(_networking_symtab_names()) == set(b)

    def test_manifest_matches_symtab(self):
        plug = [p for p in MANIFEST["plugins"] if p["name"] == "networking"][0]
        assert sorted(plug["symbols"]) == sorted(_networking_symtab_names())

    def test_registry_matches_symtab(self):
        from src.domains.registry import DomainRegistry
        entry = DomainRegistry._DOMAIN_TEMPLATES["Networking"]
        assert set(entry["functions"]) == set(_networking_symtab_names())


# ============================================================
# D. Matha 面程序闭环 + VM 边界
# ============================================================

class TestMathaFace:
    def test_matha_source_drives_full_chain(self):
        ip = Interpreter()
        out0 = len(ip.outputs)
        ip.run(parse('let 监听器 = 网络_服务(0)\n输出(监听器["端口"])'))
        port = int(ip.outputs[out0])
        assert port > 0

        got = {}

        def client():
            c = socket.socket()
            c.settimeout(5.0)
            c.connect(("127.0.0.1", port))
            c.sendall("端到端探测".encode("utf-8"))
            got["reply"] = c.recv(1024).decode("utf-8")
            c.close()

        t = threading.Thread(target=client, daemon=True)
        t.start()
        src = ('let r = 网络_接受(监听器)(2.0)\n'
               'let c = r["连接"]\n'
               'let req = 网络_收(c)(64)\n'
               '输出(req)\n'
               'let n = 网络_发(c)("matha-ack")\n'
               '输出(n > 0)\n'
               '网络_关闭(c)\n'
               '网络_关闭(监听器)')
        ip.run(parse(src))
        new_outs = [str(o) for o in ip.outputs[out0 + 1:]]
        assert new_outs[0] == "端到端探测"
        assert new_outs[1] == "True"
        t.join(timeout=5.0)
        assert got.get("reply") == "matha-ack"

    def test_vm_face_serves_and_closes(self):
        # 阶段 21 插件符号接线后，VM 面同样可达 socket 原语（不再是未定义边界）
        outs, err = exec_api.run_checked(
            'let l = 网络_服务(0)\n输出(l["端口"] > 0)\n网络_关闭(l)',
            mode="vm")
        assert err is None
        assert outs == [True]
