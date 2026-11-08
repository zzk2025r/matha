# -*- coding: utf-8 -*-
"""MCP Server 门面契约锁（阶段 1 · AI 修复）。

背景：`src/mcp_server.py` 历史上 `MathaMCPServer(MCPServer)` 在缺 mcp SDK
时类定义即 NameError（import 都进不去），`_register_matha_tools` 是 pass
占位；版本硬编 "4.4" 漂移于唯一版本源。本轮：门面改纯同步类（零 SDK
依赖），create_server() 缺 SDK 显式 ImportError，版本走 src.__version__。

本文件锁：
  1. 缺 SDK 子进程内 import 不崩、门面可用、create_server 诚实拒绝；
  2. 门面六方法真算（eval/run_file/compile/diagnose/parse_intent/get_info，
     阶段 4-3 补齐 parse_intent 缺口，门面与注册工具一一对应）；
  3. create_server 工具注册形状（假 SDK 模块注入子进程，六工具名锁定，
     零环境依赖、零跳过）。

附带回归锁：legacy matha-cc lexer 的 id-start/续符谓词不一致曾使全角
标点（：【，）产出零宽 token 死循环（门面 compile 链实测踩中），
现首字符必消费，全角输入如实报语法失败而非挂死。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.__version__ import VERSION  # noqa: E402
from src.mcp_server import MathaMCPServer  # noqa: E402


# ============================================================
# 1. 缺 SDK 诚实面（干净子进程 + import 拦截）
# ============================================================

_NO_SDK_SNIPPET = """
import importlib.abc, sys
sys.path.insert(0, %r)

class Blocker(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "mcp" or fullname.startswith("mcp."):
            raise ModuleNotFoundError("blocked: %%s" %% fullname)
        return None

sys.meta_path.insert(0, Blocker())
import src.mcp_server as ms
assert ms.MCP_AVAILABLE is False
s = ms.MathaMCPServer()  # 历史：类定义即 NameError，import 都失败
info = s.get_info()
assert info["version"] == %r, info
try:
    ms.create_server()
except ImportError as e:
    assert "pip install mcp" in str(e)
    print("NO_SDK_OK")
else:
    raise AssertionError("缺 SDK 假成功复活：create_server 未拒绝")
""" % (str(ROOT), VERSION)


def test_import_and_facade_work_without_sdk():
    proc = subprocess.run([sys.executable, "-c", _NO_SDK_SNIPPET],
                          cwd=str(ROOT), capture_output=True, text=True,
                          timeout=120)
    assert proc.returncode == 0, proc.stderr[-800:]
    assert "NO_SDK_OK" in proc.stdout


# ============================================================
# 2. 门面六方法真算（进程内，零 SDK 依赖）
# ============================================================

class TestFacadeRealMethods:

    def test_eval_expr_computes_for_real(self):
        s = MathaMCPServer()
        assert s.eval_expr("1+2").strip() == "3"
        assert s.eval_expr("10*4").strip() == "40"

    def test_run_file_reads_and_executes(self, tmp_path):
        p = tmp_path / "t.matha"
        p.write_text('#1：[6*7]\n', encoding="utf-8")
        s = MathaMCPServer()
        assert s.run_file(str(p)).strip() == "42"

    def test_run_file_missing_honest_error(self, tmp_path):
        s = MathaMCPServer()
        out = s.run_file(str(tmp_path / "nope.matha"))
        assert "文件不存在" in out

    def test_compile_source_real(self, tmp_path):
        # x = 1+1 可过 legacy 语法；本机无 llc/clang 时须诚实报工具缺失，
        # 有工具链时须真产出。两条路径都不得假成功/挂死。
        s = MathaMCPServer()
        out = s.compile_source("x = 1+1", str(tmp_path / "out"))
        if "编译成功" in out:
            assert (tmp_path / "out").exists() or (tmp_path / "out.exe").exists()
        else:
            assert "编译失败" in out and ("工具缺失" in out or "token" in out)

    def test_compile_source_fullwidth_punctuation_no_hang(self, tmp_path):
        # 回归锁：legacy lexer 的 id-start/续符谓词不一致曾使全角标点
        # （：、【、，）产出零宽 token 死循环；现须如实报语法失败而非挂死
        s = MathaMCPServer()
        out = s.compile_source("#1：[1+1]\n", str(tmp_path / "out"))
        assert "编译失败" in out

    def test_lexer_consumes_id_start_chars(self):
        from src.compiler.matha_cc import MathaLexer
        for src in ("#1：[1+1]", "@：【加载领域】，神经网络", "，【："):
            tokens = MathaLexer(src).tokenize()  # 修复前：死循环
            assert tokens[-1].type == "EOF"
            assert all(t.value != "" or t.type == "EOF" for t in tokens)

    def test_diagnose_returns_list(self):
        s = MathaMCPServer()
        out = s.diagnose("#1：[1+1]\n")
        assert isinstance(out, list) and out
        assert all(isinstance(d, dict) and "message" in d for d in out)

    def test_get_info_version_single_source(self):
        info = MathaMCPServer().get_info()
        assert info["name"] == "Matha"
        assert info["version"] == VERSION  # 反硬编 "4.4" 漂移

    def test_parse_intent_real_decomposition(self):
        # 阶段 4-3：门面补齐 parse_intent（历史上六工具只有五方法）
        out = MathaMCPServer().parse_intent("计算 3 加 5")
        assert out["type"] == "arithmetic"
        assert out["confidence"] == 1.0
        assert out["total_steps"] == 1
        assert out["steps"] == ["计算 3.0 + 5.0"]

    def test_facade_six_methods_match_registered_tools(self):
        # 门面 ↔ 协议工具一一对应（命名映射固定，防再漂移）
        facade_to_tool = {
            "eval_expr": "eval_expression",
            "run_file": "run_file",
            "compile_source": "compile_source",
            "diagnose": "diagnose_source",
            "parse_intent": "parse_intent",
            "get_info": "get_info",
        }
        for method in facade_to_tool:
            assert callable(getattr(MathaMCPServer(), method)), method
        registered = {"eval_expression", "run_file", "compile_source",
                      "diagnose_source", "parse_intent", "get_info"}
        assert set(facade_to_tool.values()) == registered


# ============================================================
# 3. 工具注册形状（假 SDK 模块注入，干净子进程，零环境依赖）
# ============================================================

_FAKE_SDK_SNIPPET = """
import sys, types
sys.path.insert(0, %r)

registered = []

class FakeServer:
    def __init__(self, name=None, version=None):
        self.name, self.version = name, version
    def tool(self):
        def deco(fn):
            registered.append(fn.__name__)
            return fn
        return deco

mcp = types.ModuleType("mcp")
server_pkg = types.ModuleType("mcp.server")
mcpserver_mod = types.ModuleType("mcp.server.mcpserver")
mcpserver_mod.MCPServer = FakeServer
types_mod = types.ModuleType("mcp.types")
types_mod.TextContent = lambda **kw: kw
for name, mod in [("mcp", mcp), ("mcp.server", server_pkg),
                  ("mcp.server.mcpserver", mcpserver_mod),
                  ("mcp.types", types_mod)]:
    sys.modules[name] = mod

import src.mcp_server as ms
assert ms.MCP_AVAILABLE is True
s = ms.create_server()
assert s.name == "matha" and s.version == %r
assert set(registered) == {"eval_expression", "run_file", "compile_source",
                           "diagnose_source", "parse_intent", "get_info"}, registered
print("REGISTER_OK")
""" % (str(ROOT), VERSION)


def test_create_server_registers_six_tools():
    proc = subprocess.run([sys.executable, "-c", _FAKE_SDK_SNIPPET],
                          cwd=str(ROOT), capture_output=True, text=True,
                          timeout=120)
    assert proc.returncode == 0, proc.stderr[-800:]
    assert "REGISTER_OK" in proc.stdout