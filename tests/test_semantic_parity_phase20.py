# -*- coding: utf-8 -*-
"""阶段 20 · 双端语义第五片（match 分歧收口 + finally 全链同构）三锁。

阶段 15/19 拍板登记不修的语义分歧全部真化（用户拍板三项全选推荐）：
  20a match 对齐方向 = 编译面→解释面：src/mbc/compiler.py _emit_match 重构
      ——守卫先于模式测试（绑定名此刻未声明 → LOAD_GLOBAL，运行期未定义名
      报错与解释面逐字一致）；通配 _ 兜底改动态记录（标记槽 match_d：首个
      守卫通过的通配分支记录 tag，尾部分发链按 tag 取体）——对齐解释面
      「通配仅在守卫通过后记录首个默认、继续测试后续分支」语义（含
      lifestyle_math.matha 3 守卫通配 + 纯通配形态）；无匹配尾 RAISE_MATCH
      （0x63）新操作码，VM 端 _fmt_match_value 渲染被匹配值
      「match 无匹配分支: <值>」与解释器 _fmt 逐字一致。解释面零改动
      （参考语义不动）。
  20b finally 全链同构 = 先 finally 后重抛：host interp _exec_try 无 catch
      分支改 raise（宿主 Python finally 照跑）；VM _emit_try_stmt finally
      thunk 编译一次、正常/捕获正常/重抛尾三路 _emit_fin_call 先调 finally
      后留值/重抛，catch 体经 调用捕获 受保护运行（catch 再抛 → finally 照
      执行）；自举镜像 interp.matha 执行try + compiler_matha.matha _发射try
      同构。19c 登记「VM finally 无 catch 重抛路径不执行 thunk」勘误为已修。
  20c 自举镜像同步：compiler_matha.matha _发射match/_发射match分支/
      _发射match尾部/_发射try 全量重构 + OP_RAISE_MATCH 常量；字节级
      stage2≡stage3（test_mbc_bootstrap.py m18 全绿 + 新增镜像锁）。
  20d 原生后端 RAISE_MATCH：native.py match_render 运行时（标量
      value_to_str / 字符串/列表/字典 print_repr 两遍渲染）+
      err_match_nomsg 前缀拼接 → raise_rt；标量/字符串/短列表消息与
      VM/host 逐字一致。

登记边界（现状锁，不修）：
  - 镜像解析器 解析try语句 对「无 catch」与「显式空 catch {}」同形
    （捕获体.声明=[]）→ 镜像面（interp.matha 执行try / compiler_matha
    _发射try）显式空 catch = 重抛；宿主面（interp._exec_try 以
    catch_block is None 区分 / compiler 以 catch_block is not None 发射）
    显式空 catch = 吞错继续。语料零命中，镜像解析器不动（自举风险 >
    收益）。镜像面自身双面一致。
  - 原生 RAISE_MATCH 渲染差异：无 60 字符截断、无 >4/>6 容器缩略形态、
    字典键经 repr（VM/host 键原样）、闭包值原样（VM 报 <builtin …>）。

三锁封死：
  1. 对拍：守卫序矩阵（守卫引用外名/守卫引用绑定名双端同错同消息/守卫假
     落后续分支）、动态兜底矩阵（通配后可匹配/守卫通配在前/多守卫通配）、
     无匹配消息逐字（int/str/短列表/>4 列表/>6 字典）、语句位无匹配双端
     同错、finally 全路径（无 catch 重抛副作用序/catch 再抛重抛/正常与
     捕获正常 finally 副作用/错误传播部分输出同构）双端逐值一致。
  2. 闭环：matha run 真子进程 func 体 match 输出、无匹配退出码与 stderr
     消息形态、finally 重抛副作用序；原生 compile_to_exe 捕获消息与
     未捕获 stderr/退出码形态。
  3. 边界：镜像面空 catch 重抛 / 宿主面吞错登记分歧现状锁、stage2≡stage3
     字节级（通配 match/无变量 catch/try-finally，锁在
     test_mbc_bootstrap.py）、原生渲染差异面登记锁（>4 列表消息形态差异
     显式断言防静默漂移）。
"""
from __future__ import annotations

import contextlib
import io
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.interp import Interpreter  # noqa: E402
from src.mbc.compiler import Compiler  # noqa: E402
from src.mbc.native import compile_to_exe  # noqa: E402
from src.mbc.vm import VM  # noqa: E402
from src.parser import parse  # noqa: E402


def _run_host(src: str) -> list:
    interp = Interpreter(debug=False)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        interp.run(parse(src))
    return list(interp.outputs)


def _run_vm(src: str) -> list:
    mod = Compiler().compile_program(parse(src))
    vm = VM(mod)
    vm.run()
    return list(vm.outputs)


def _both(src: str, expected: list) -> None:
    assert _run_host(src) == expected, f"host: {_run_host(src)}"
    assert _run_vm(src) == expected, f"vm: {_run_vm(src)}"


def _run_raw(src: str, backend: str):
    """双端原始形态：成功返回 outputs 列表，失败返回 'ERR 类名: 消息'。"""
    try:
        if backend == "host":
            return _run_host(src)
        return _run_vm(src)
    except Exception as e:  # noqa: BLE001
        return f"ERR {type(e).__name__}: {e}"


def _partial(src: str, backend: str) -> tuple:
    """双端异常路径部分输出：跑到底再捕获，返回 (outputs, '类名: 消息')。"""
    try:
        return (  _run_host(src), ""   ) if backend == "host" else (  _run_vm(src), ""   )
    except Exception as e:  # noqa: BLE001
        outs = getattr(e, "matha_partial_outputs", None)
        return (list(outs) if outs else None, f"{type(e).__name__}: {e}")


def _run_file(src: str, name: str = "用例20.matha") -> subprocess.CompletedProcess:
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / name
        p.write_text(src, encoding="utf-8")
        return subprocess.run(
            [sys.executable, "-m", "src.matha_main", "run", str(p)],
            capture_output=True, timeout=120,
        )


# ============================================================
# 1. 对拍：match 收口（守卫序 + 动态兜底 + 无匹配消息）
# ============================================================

class TestMatchGuardOrder20:
    """守卫先于模式绑定（编译面→解释面）：守卫引用绑定名 → 双端同错同消息。"""

    def test_guard_refs_outer_var(self):
        _both(
            "func 拾(v: Int) -> Int =\n"
            "  (v) =>\n"
            "  match v {\n"
            "    | 1 if 外 > 0 => 10\n"
            "    | _ => 20\n"
            "  }\n"
            "外 = 5\n输出(拾(1))\n",
            [10],
        )

    def test_guard_refs_binding_name_undefined_both(self):
        # 守卫引用模式绑定名：绑定名尚未声明 → 双端同报错同消息
        src = (
            "func 拾(v: Int) -> Int =\n"
            "  (v) =>\n"
            "  match v {\n"
            "    | x if x > 0 => 10\n"
            "    | _ => 20\n"
            "  }\n"
            "输出(拾(1))\n"
        )
        ho = _run_raw(src, "host")
        vo = _run_raw(src, "vm")
        assert ho == vo
        assert isinstance(ho, str) and "未定义变量 'x'" in ho

    def test_guard_false_falls_through(self):
        # 守卫假 → 落后续分支（首个默认未记录前通配不拦截）
        _both(
            "func 拾(v: Int) -> Int =\n"
            "  (v) =>\n"
            "  match v {\n"
            "    | 1 if 1 > 2 => 10\n"
            "    | 1 => 20\n"
            "    | _ => 30\n"
            "  }\n"
            "输出(拾(1))\n输出(拾(9))\n",
            [20, 30],
        )

    def test_stmt_pos_guard_binding_undefined_both(self):
        # 语句位同源语义：守卫引用绑定名双端同错
        src = "match 5 {\n  | x if x > 0 => 输出(10)\n  | _ => 输出(20)\n}\n"
        ho = _run_raw(src, "host")
        vo = _run_raw(src, "vm")
        assert ho == vo
        assert isinstance(ho, str) and "未定义变量 'x'" in ho


class TestMatchDynamicDefault20:
    """通配 _ 兜底动态记录：首个守卫通过的通配分支生效，后续分支照测。"""

    def test_wildcard_then_matchable(self):
        # 通配分支只记录兜底不短路：循环内后续显式分支仍命中（记录在循环结束后才生效）
        _both(
            "func 拾(v: Int) -> String =\n"
            "  (v) =>\n"
            "  match v {\n"
            "    | _ if 1 > 0 => \"兜\"\n"
            "    | 2 => \"中\"\n"
            "  }\n"
            "输出(拾(2))\n输出(拾(9))\n",
            ["中", "兜"],
        )

    def test_guarded_wildcard_first_then_matchable(self):
        # 守卫假的通配不记录 → 后续字面分支命中
        _both(
            "func 拾(v: Int) -> String =\n"
            "  (v) =>\n"
            "  match v {\n"
            "    | _ if 1 > 2 => \"兜\"\n"
            "    | 2 => \"中\"\n"
            "    | _ => \"末\"\n"
            "  }\n"
            "输出(拾(2))\n输出(拾(9))\n",
            ["中", "末"],
        )

    def test_multi_guarded_wildcards(self):
        # lifestyle_math.matha bmi 同型：3 守卫通配 + 纯通配，按序首中
        _both(
            "func 分档(v: Float) -> String =\n"
            "  (v) =>\n"
            "  match v {\n"
            "    | _ if v < 18.5 => \"偏瘦\"\n"
            "    | _ if v < 24 => \"正常\"\n"
            "    | _ if v < 28 => \"偏胖\"\n"
            "    | _ => \"肥胖\"\n"
            "  }\n"
            "输出(分档(17.0))\n输出(分档(22.0))\n输出(分档(26.0))\n输出(分档(30.0))\n",
            ["偏瘦", "正常", "偏胖", "肥胖"],
        )

    def test_binding_rhs_match_wildcard(self):
        # 绑定 RHS 位 match（19a 既有路径 + 通配兜底组合）
        _both(
            "甲 = match 9 {\n  | 1 => 10\n  | _ if 1 > 0 => 50\n  | _ => 99\n}\n输出(甲)\n",
            [50],
        )


class TestMatchNoMatchMessage20:
    """无匹配报错：RAISE_MATCH 值渲染与解释面 _fmt 逐字一致。"""

    def test_no_match_int(self):
        src = "输出(match 9 {\n  | 1 => 10\n})\n"
        ho = _run_raw(src, "host")
        vo = _run_raw(src, "vm")
        assert ho == vo
        assert isinstance(ho, str) and "match 无匹配分支: 9" in ho

    def test_no_match_string(self):
        src = '输出(match "甲乙" {\n  | "丙" => "中"\n})\n'
        ho = _run_raw(src, "host")
        vo = _run_raw(src, "vm")
        assert ho == vo
        assert isinstance(ho, str) and "match 无匹配分支: '甲乙'" in ho

    def test_no_match_short_list(self):
        src = "输出(match [1, 2, 3] {\n  | 7 => \"七\"\n})\n"
        ho = _run_raw(src, "host")
        vo = _run_raw(src, "vm")
        assert ho == vo
        assert isinstance(ho, str) and "match 无匹配分支: [1, 2, 3]" in ho

    def test_no_match_long_list_abbrev(self):
        # >4 元素列表 → _fmt 缩略形态 [list len=6]
        src = "输出(match [1, 2, 3, 4, 5, 6] {\n  | 7 => \"七\"\n})\n"
        ho = _run_raw(src, "host")
        vo = _run_raw(src, "vm")
        assert ho == vo
        assert isinstance(ho, str) and "match 无匹配分支: [list len=6]" in ho

    def test_no_match_big_dict_abbrev(self):
        # >6 键字典 → _fmt 缩略形态 {dict keys=[…]}
        src = (
            "输出(match {\"a\": 1, \"b\": 2, \"c\": 3, \"d\": 4, \"e\": 5,"
            " \"f\": 6, \"g\": 7} {\n  | 7 => \"七\"\n})\n"
        )
        ho = _run_raw(src, "host")
        vo = _run_raw(src, "vm")
        assert ho == vo
        assert isinstance(ho, str) and "match 无匹配分支: {dict keys=['a'" in ho

    def test_stmt_pos_no_match_both_error(self):
        # 语句位 match 无匹配 → 双端同报错（旧登记「语句位 VM 静默」已收口）
        src = "match 9 {\n  | 1 => 输出(10)\n}\n输出(7)\n"
        ho = _run_raw(src, "host")
        vo = _run_raw(src, "vm")
        assert ho == vo
        assert isinstance(ho, str) and "match 无匹配分支: 9" in ho

    def test_caught_no_match_message_via_catch(self):
        # 无匹配错误经 try/catch 捕获：catch 变量 = 完整消息串（RAISE_MATCH
        # 消息保真）
        src = (
            "func 试() -> String = () => {\n"
            "  try {\n"
            "    match \"甲乙\" { | \"丙\" => \"中\" }\n"
            "  } catch (e) {\n"
            "    e\n"
            "  }\n"
            "}\n"
            "输出(试())\n"
        )
        _both(src, ["match 无匹配分支: '甲乙'"])

    def test_caught_no_match_list_via_catch(self):
        src = (
            "func 试() -> String = () => {\n"
            "  try {\n"
            "    match [1, 2, 3] { | 7 => \"七\" }\n"
            "  } catch (e) {\n"
            "    e\n"
            "  }\n"
            "}\n"
            "输出(试())\n"
        )
        _both(src, ["match 无匹配分支: [1, 2, 3]"])


# ============================================================
# 2. 对拍：finally 全链（先 finally 后重抛 / 三路 finally 调用）
# ============================================================

class TestFinallyParity20:
    """20b 全链同构：异常路径「先 finally 后重抛」双端一致。"""

    def test_no_catch_rethrow_finally_side_effect_order(self):
        # 无 catch 重抛：finally 副作用先落盘、错误照抛（19c 登记分歧已修）
        src = (
            "try {\n"
            "  输出(1)\n"
            "  1 / 0\n"
            "} finally {\n"
            "  输出(9)\n"
            "}\n"
        )
        ho = _run_raw(src, "host")
        vo = _run_raw(src, "vm")
        assert ho == vo
        assert isinstance(ho, str) and "除零错误" in ho
        # 部分输出：finally 的 9 在错误传播前已发射
        assert self._partial_outputs(src) == [1, 9]

    def _partial_outputs(self, src: str) -> list:
        interp = Interpreter(debug=False)
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                interp.run(parse(src))
        except Exception:  # noqa: BLE001
            pass
        return list(interp.outputs)

    def test_no_catch_rethrow_partial_outputs_vm(self):
        # VM 面部分输出同构（[1, 9] 后抛错）
        src = (
            "try {\n"
            "  输出(1)\n"
            "  1 / 0\n"
            "} finally {\n"
            "  输出(9)\n"
            "}\n"
        )
        mod = Compiler().compile_program(parse(src))
        vm = VM(mod)
        try:
            vm.run()
        except Exception as e:  # noqa: BLE001
            assert "除零错误" in str(e)
        assert list(vm.outputs) == [1, 9]

    def test_catch_raises_finally_still_runs(self):
        # catch 体再抛：finally 照执行后重抛（19c 前只有 host Python finally
        # 保底，VM 此前丢 finally）
        src = (
            "try {\n"
            "  输出(1)\n"
            "  throw \"炸\"\n"
            "} catch (e) {\n"
            "  输出(2)\n"
            "  throw e\n"
            "} finally {\n"
            "  输出(9)\n"
            "}\n"
        )
        ho = _run_raw(src, "host")
        vo = _run_raw(src, "vm")
        assert ho == vo
        assert isinstance(ho, str) and "炸" in ho
        assert self._partial_outputs(src) == [1, 2, 9]

    def test_catch_catches_finally_not_over_value(self):
        # 捕获正常：finally 执行但不覆盖 try/catch 值（既有语义回归锁）
        _both(
            "func 试() -> Int = () => {\n"
            "  try {\n"
            "    throw \"x\"\n"
            "  } catch (e) {\n"
            "    5\n"
            "  } finally {\n"
            "    输出(99)\n"
            "  }\n"
            "}\n"
            "输出(试())\n",
            [99, 5],
        )

    def test_normal_path_finally_side_effect(self):
        # 正常路径：先 finally 副作用后块尾值（发射序同构）
        _both(
            "func 试() -> Int = () => {\n"
            "  try {\n"
            "    8\n"
            "  } catch (e) {\n"
            "    0\n"
            "  } finally {\n"
            "    输出(1)\n"
            "  }\n"
            "}\n"
            "输出(试())\n",
            [1, 8],
        )

    def test_catch_varless_swallow(self):
        # 无变量 catch 吞错继续（宿主面既有语义；镜像面登记差异见边界锁）
        _both(
            "try {\n"
            "  throw \"x\"\n"
            "} catch {\n"
            "  输出(\"吞\")\n"
            "}\n"
            "输出(\"后\")\n",
            ["吞", "后"],
        )

    def test_error_propagation_identity_preserved(self):
        # 错误传播同构：异常消息跨 try 边界保真（旧登记 F4 形态）
        src = (
            "try {\n"
            "  输出(9)\n"
            "  throw \"x\"\n"
            "} finally {\n"
            "  输出(2)\n"
            "}\n"
        )
        ho = _run_raw(src, "host")
        vo = _run_raw(src, "vm")
        assert ho == vo
        assert isinstance(ho, str) and "x" in ho
        assert self._partial_outputs(src) == [9, 2]


# ============================================================
# 3. 闭环：matha run 真子进程 + 原生后端
# ============================================================

class TestEndToEndPhase20:
    def test_e2e_match_func_body(self):
        proc = _run_file(
            "func 词类(词: String) -> String =\n"
            "  (词) =>\n"
            "  match 词 {\n"
            "    | \"的\" => \"助词\"\n"
            "    | _ => \"名词\"\n"
            "  }\n"
            "输出(词类(\"的\"))\n输出(词类(\"跑\"))\n"
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.decode("utf-8").splitlines() == ["助词", "名词"]

    def test_e2e_no_match_exit_and_stderr(self):
        proc = _run_file("输出(match 9 {\n  | 1 => 10\n})\n")
        assert (proc.returncode & 0xFFFFFFFF) != 0
        assert "match 无匹配分支: 9" in proc.stderr.decode("utf-8", "replace")

    def test_e2e_finally_rethrow_order(self):
        proc = _run_file(
            "try {\n"
            "  输出(1)\n"
            "  1 / 0\n"
            "} finally {\n"
            "  输出(9)\n"
            "}\n"
        )
        assert (proc.returncode & 0xFFFFFFFF) != 0
        assert proc.stdout.decode("utf-8").splitlines() == ["1", "9"]
        assert "除零错误" in proc.stderr.decode("utf-8", "replace")


class TestNativeRaiseMatch20:
    """原生后端 RAISE_MATCH：捕获消息与未捕获 stderr 形态。"""

    def _run_exe(self, src: str, tag: str) -> subprocess.CompletedProcess:
        exe = os.path.join(tempfile.gettempdir(), f"probe20_lock_{tag}.exe")
        Path(exe).write_bytes(compile_to_exe(src))
        return subprocess.run([exe], capture_output=True, timeout=60)

    def test_native_caught_message(self):
        r = self._run_exe(
            'func 试() -> String = () => {\n'
            '  try {\n'
            '    match "甲乙" { | "丙" => "中" }\n'
            '  } catch (e) {\n'
            '    e\n'
            '  }\n'
            '}\n'
            '#1：[试()]',
            "caught",
        )
        assert (r.returncode & 0xFFFFFFFF) == 0
        assert r.stdout.decode("utf-8", "replace").strip() == \
            "match 无匹配分支: '甲乙'"

    def test_native_caught_list_message(self):
        r = self._run_exe(
            'func 试() -> String = () => {\n'
            '  try {\n'
            '    match [1, 2, 3] { | 7 => "七" }\n'
            '  } catch (e) {\n'
            '    e\n'
            '  }\n'
            '}\n'
            '#1：[试()]',
            "caught_list",
        )
        assert (r.returncode & 0xFFFFFFFF) == 0
        assert r.stdout.decode("utf-8", "replace").strip() == \
            "match 无匹配分支: [1, 2, 3]"

    def test_native_uncaught_stderr_and_exit(self):
        r = self._run_exe("#1：{ match 9 { | 1 => 10 } }", "uncaught")
        assert (r.returncode & 0xFFFFFFFF) == 1
        assert "match 无匹配分支: 9" in r.stderr.decode("utf-8", "replace")


# ============================================================
# 4. 边界：登记分歧现状锁
# ============================================================

class TestBoundariesPhase20:
    """登记边界现状锁（防静默漂移，非修）。"""

    def test_native_render_delta_long_list(self):
        # 登记差异锁：>4 列表原生渲染 = 完整列表形态（VM/host = 缩略
        # [list len=N]）——显式断言差异形态，静默收敛/漂移都会红
        exe = os.path.join(tempfile.gettempdir(), "probe20_lock_delta.exe")
        Path(exe).write_bytes(compile_to_exe(
            'func 试() -> String = () => {\n'
            '  try {\n'
            '    match [1, 2, 3, 4, 5, 6] { | 7 => "七" }\n'
            '  } catch (e) {\n'
            '    e\n'
            '  }\n'
            '}\n'
            '#1：[试()]'
        ))
        r = subprocess.run([exe], capture_output=True, timeout=60)
        out = r.stdout.decode("utf-8", "replace").strip()
        assert out == "match 无匹配分支: [1, 2, 3, 4, 5, 6]"
        # VM/host 同源 = 缩略形态（对照）
        src = (
            "func 试() -> String = () => {\n"
            "  try {\n"
            "    match [1, 2, 3, 4, 5, 6] { | 7 => \"七\" }\n"
            "  } catch (e) {\n"
            "    e\n"
            "  }\n"
            "}\n"
            "输出(试())\n"
        )
        assert _run_host(src) == ["match 无匹配分支: [list len=6]"]

    def test_host_empty_catch_swallows(self):
        # 宿主面：显式空 catch {} = 吞错继续（catch_block 非 None 但体空）
        _both(
            "try {\n"
            "  throw \"x\"\n"
            "} catch {\n"
            "}\n"
            "输出(\"后\")\n",
            ["后"],
        )
