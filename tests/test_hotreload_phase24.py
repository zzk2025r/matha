# -*- coding: utf-8 -*-
"""阶段 24g 三锁：热启动与运行（mtime 热重载，双面）。

锁四面：
  A. 双面对拍 —— 热启动装载 + 调用、未变更 重载=False、单运行内自改
     自重载（宿主 写文件 / VM _write_file）、自测块不执行、资源库
     模块名解析；
  B. 诚实拒绝 —— 未热启动重载、模块不存在、目标非文本、源文件被删、
     语法错误如实上抛、程序自定义同名优先；
  C. 装配面 —— 快照落解释器本体、manifest 不登记（加载胶水面同
     加载模块）、VM 快照生命周期 = 单次运行（跨运行如实报未热启动）。
"""
import io
import json
import os
import sys
import time
from contextlib import redirect_stdout
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.interp import Interpreter  # noqa: E402
from src.kernel import exec_api  # noqa: E402
from src.parser import parse  # noqa: E402
from src.plugin_api import MANIFEST_PATH  # noqa: E402

MANIFEST = json.loads(Path(MANIFEST_PATH).read_text(encoding="utf-8"))


def _host_run(ip: Interpreter, source: str) -> list:
    before = len(ip.outputs)
    with redirect_stdout(io.StringIO()):
        ip.run(parse(source))
    return [str(o) for o in ip.outputs[before:]]


def _host_outputs(source: str) -> list:
    return _host_run(Interpreter(), source)


def _vm_run(source: str) -> list:
    outs, err = exec_api.run_checked(source, mode="vm")
    assert err is None, f"vm 面不应报错: {type(err).__name__}: {err}"
    return [str(o) for o in outs]


def _host_err(source: str) -> str:
    ip = Interpreter()
    with redirect_stdout(io.StringIO()):
        try:
            ip.run(parse(source))
        except Exception as e:
            return f"{type(e).__name__}: {e}"
    raise AssertionError("host 面应报错")


def _vm_err(source: str) -> str:
    outs, err = exec_api.run_checked(source, mode="vm")
    assert err is not None, "vm 面应报错"
    return str(err)


# ============================================================
# A. 双面对拍
# ============================================================

class TestHotParity:
    def _module(self, tmp_path, body="x * 3"):
        mod = tmp_path / "hot_probe.matha"
        mod.write_text(f"func 三倍(x) -> Int = (x) => {body}\n",
                       encoding="utf-8")
        return mod

    def test_hot_start_then_call(self, tmp_path):
        mod = self._module(tmp_path)
        src = (f'let r = 热启动("{mod.as_posix()}")\n'
               '输出(r.已加载)\n输出(r.声明数)\n输出(三倍(4))')
        h = _host_outputs(src)
        v = _vm_run(src)
        assert h == ["True", "1", "12"]
        assert h == v

    def test_reload_unchanged_noop(self, tmp_path):
        mod = self._module(tmp_path)
        src = (f'let r1 = 热启动("{mod.as_posix()}")\n'
               f'let r2 = 热重载("{mod.as_posix()}")\n'
               '输出(r1.已加载)\n输出(r2.重载)\n输出(三倍(4))')
        h = _host_outputs(src)
        v = _vm_run(src)
        assert h == ["True", "False", "12"]
        assert h == v

    def test_reload_picks_up_change_in_run(self, tmp_path):
        """单运行内自改自重载：写文件(宿主)/_write_file(VM) → mtime 变 →
        热重载 True → 新定义生效（长运行程序热更新闭环）。
        双面各用独立模块文件——宿主运行会改写文件，不能共用。"""
        mod_h = tmp_path / "hot_chg_h.matha"
        mod_v = tmp_path / "hot_chg_v.matha"
        for m in (mod_h, mod_v):
            m.write_text("func 三倍(x) -> Int = (x) => x * 3\n",
                         encoding="utf-8")
        # Windows 同刻度两写 mtime 可能相同 → 热重载误判 未变更；
        # 把初版 mtime 回拨，保证运行内覆写严格更新（双面 == 检测）。
        past = time.time() - 10
        for m in (mod_h, mod_v):
            os.utime(m, (past, past))
        ph, pv = mod_h.as_posix(), mod_v.as_posix()
        host_src = (f'let r1 = 热启动("{ph}")\n'
                    '输出(三倍(4))\n'
                    f'写文件("{ph}")("func 三倍(x) -> Int = (x) => x * 9")\n'
                    f'let r2 = 热重载("{ph}")\n'
                    '输出(r2.重载)\n输出(三倍(4))')
        vm_src = (f'let r1 = 热启动("{pv}")\n'
                  '输出(三倍(4))\n'
                  f'_write_file("{pv}")("func 三倍(x) -> Int = (x) => x * 9")\n'
                  f'let r2 = 热重载("{pv}")\n'
                  '输出(r2.重载)\n输出(三倍(4))')
        h = _host_outputs(host_src)
        v = _vm_run(vm_src)
        assert h == ["12", "True", "36"]
        assert h == v

    def test_module_selftest_not_executed(self, tmp_path):
        """被载模块自测块不执行（宿主 _loading_module 跳过 / VM 只合并
        函数面）——装载本身零输出。"""
        mod = tmp_path / "hot_selftest.matha"
        mod.write_text('func 加一(x) -> Int = (x) => x + 1\n'
                       '#1：{ 输出(加一(0)) }\n', encoding="utf-8")
        src = (f'let r = 热启动("{mod.as_posix()}")\n'
               '输出(加一(1))')
        h = _host_outputs(src)
        v = _vm_run(src)
        assert h == ["2"]  # 自测块若执行会多出 1
        assert h == v

    def test_name_mode_resolves_resource_library(self):
        """模块名模式：三级解析落到资源库（24a 代码化资源）。"""
        src = 'let r = 热启动("计算动能")\n输出(r.已加载)'
        h = _host_outputs(src)
        v = _vm_run(src)
        assert h == ["True"]
        assert h == v

    def test_module_decl_name_reported(self, tmp_path):
        mod = tmp_path / "hot_named.matha"
        mod.write_text('module 热探针 {\n'
                       '  func 双倍(x) -> Int = (x) => x * 2\n'
                       '}\n', encoding="utf-8")
        src = (f'let r = 热启动("{mod.as_posix()}")\n'
               '输出(r.模块)\n输出(双倍(5))')
        h = _host_outputs(src)
        v = _vm_run(src)
        assert h == ["热探针", "10"]
        assert h == v


# ============================================================
# B. 诚实拒绝
# ============================================================

class TestHotHonest:
    def test_reload_requires_start(self):
        src = '热重载("从未启动zz")'
        h = _host_err(src)
        v = _vm_err(src)
        assert "尚未热启动" in h and "热启动(" in h
        assert "尚未热启动" in v and "热启动(" in v

    def test_missing_module(self):
        src = '热启动("不存在模块zz")'
        h = _host_err(src)
        v = _vm_err(src)
        assert "找不到 Matha 模块" in h
        assert "找不到 Matha 模块" in v

    def test_non_text_target(self):
        src = "热启动(42)"
        h = _host_err(src)
        v = _vm_err(src)
        assert "须为非空文本" in h
        assert "须为非空文本" in v

    def test_source_deleted_after_start(self, tmp_path):
        """宿主面：热启动后源文件被删 → 热重载显式拒绝（不假重载）。
        VM 面运行内无法删除文件（无删除内建），此形态为宿主长运行边界。"""
        mod = tmp_path / "hot_vanish.matha"
        mod.write_text("func 一(x) -> Int = (x) => x\n", encoding="utf-8")
        ip = Interpreter()
        _host_run(ip, f'热启动("{mod.as_posix()}")')
        mod.unlink()
        with pytest.raises(Exception, match="源文件已不存在"):
            _host_run(ip, f'热重载("{mod.as_posix()}")')

    def test_parse_error_propagates_honestly(self, tmp_path):
        """被热装载模块语法错误 → 如实上抛（不吞、不假装载）。"""
        mod = tmp_path / "hot_broken.matha"
        mod.write_text("let x = !!!\n", encoding="utf-8")
        src = f'热启动("{mod.as_posix()}")'
        h = _host_err(src)
        v = _vm_err(src)
        assert h and v  # 双面均报错；具体消息来自解析器，属既有语义

    def test_program_defined_symbol_wins(self):
        """程序自定义同名函数优先（setdefault 注入面 / 内建表语义）。"""
        src = ('func 热启动(目标) -> String = (目标) => "自定义"\n'
               '输出(热启动("x"))')
        h = _host_outputs(src)
        v = _vm_run(src)
        assert h == ["自定义"]
        assert h == v


# ============================================================
# C. 装配面
# ============================================================

class TestHotWiring:
    def test_manifest_does_not_register_hot_symbols(self):
        """热启动/热重载是加载胶水面（同 加载模块），不进领域清单。"""
        syms = {s for p in MANIFEST["plugins"] for s in p["symbols"]}
        assert "热启动" not in syms and "热重载" not in syms

    def test_host_snapshot_recorded_on_interpreter(self, tmp_path):
        mod = tmp_path / "hot_snap.matha"
        mod.write_text("func 零(x) -> Int = (x) => 0\n", encoding="utf-8")
        ip = Interpreter()
        _host_run(ip, f'let r = 热启动("{mod.as_posix()}")')
        key = mod.as_posix()
        assert key in ip._hot_mtimes
        path_str, mtime = ip._hot_mtimes[key]
        assert path_str == str(mod)
        assert mtime == mod.stat().st_mtime

    def test_host_snapshot_persists_across_run_calls(self, tmp_path):
        """宿主长运行形态：同一 Interpreter 多次 run() 间快照持久
        （REPL 轮询热重载的真实用法）。"""
        mod = tmp_path / "hot_longrun.matha"
        mod.write_text("func 语义(x) -> Int = (x) => x + 1\n", encoding="utf-8")
        p = mod.as_posix()
        ip = Interpreter()
        assert _host_run(ip, f'热启动("{p}")\n输出(语义(1))') == ["2"]
        mod.write_text("func 语义(x) -> Int = (x) => x + 100\n",
                       encoding="utf-8")
        st = mod.stat()
        os.utime(mod, (st.st_atime, st.st_mtime + 5))
        assert _host_run(ip, f'let r = 热重载("{p}")\n输出(r.重载)\n'
                             '输出(语义(1))') == ["True", "101"]
        assert _host_run(ip, f'let r = 热重载("{p}")\n输出(r.重载)') == ["False"]

    def test_vm_snapshot_lifecycle_is_per_run(self, tmp_path):
        """VM 面快照随运行本体（与 加载模块 loaded-set 同生命周期）：
        单运行内持久、跨运行如实报「尚未热启动」。"""
        mod = tmp_path / "hot_vmlife.matha"
        mod.write_text("func 恒(x) -> Int = (x) => 7\n", encoding="utf-8")
        p = mod.as_posix()
        src = (f'let r1 = 热启动("{p}")\n'
               f'let r2 = 热重载("{p}")\n'
               f'let r3 = 热重载("{p}")\n'
               '输出(r1.已加载)\n输出(r2.重载)\n输出(r3.重载)\n输出(恒(0))')
        assert _vm_run(src) == ["True", "False", "False", "7"]
        # 跨运行：快照不随 VM 持久（诚实边界，宿主面才有跨调用持久）
        cross = _vm_err(f'热重载("{p}")')
        assert "尚未热启动" in cross
