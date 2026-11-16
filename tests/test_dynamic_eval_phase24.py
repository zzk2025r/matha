"""阶段 24d 三锁：动态解析——语言级动态求值双面（缺陷修复收口面）。

真化面：动态解析(源码串) 在**当前环境**解析并执行源码——绑定/函数/模块
持久可调用（资源库源码可当代码用/调用/编程的核心通道），尾裸表达式的值
作为返回值。宿主面 src.interp._b_dynamic_eval（当前解释器环境）；VM 面
src.mbc.vm._make_dynamic_eval（共享同一 _GlobalScope 的嵌套 VM，函数按
21a/21b 纪律钉源常量池/函数表，哨兵零参函数经 invoke_value 取值、取后即
弹出零污染）。与 执行Matha 的区别：共享环境 + 返回值（执行Matha 是进程
隔离全新运行）。

登记边界（现状锁）：函数体内动态解析，宿主面经动态作用域可见局部变量，
VM 面嵌套 VM 只共享全局（帧局部不跨编译单元）——顶层动态求值双面一致，
函数体形态双端分歧如实锁存。
"""
import pytest

from src.interp import Interpreter
from src.kernel import exec_api
from src.parser import parse


def _run_both(src):
    """双面对拍：宿主解释器 vs MBC VM（错误为 None 才算跑通）。"""
    ip = Interpreter()
    ip.run(parse(src))
    host = list(ip.outputs)
    outs, err = exec_api.run_checked(src, mode="vm")
    assert err is None, err
    return host, list(outs)


def _host_err(src):
    """宿主面运行，返回 (outputs, 错误消息|None)。"""
    ip = Interpreter()
    try:
        ip.run(parse(src))
        return list(ip.outputs), None
    except Exception as e:  # noqa: BLE001
        return list(ip.outputs), f"{type(e).__name__}: {e}"


def _vm_err(src):
    """VM 面运行，返回 (outputs, 错误消息|None)。"""
    outs, err = exec_api.run_checked(src, mode="vm")
    return list(outs), None if err is None else str(err)


class TestDynamicEvalParity:
    """对拍：动态求值核心语义双面逐字一致。"""

    def test_expression_value(self):
        host, vm = _run_both('输出(动态解析("6 * 7"))')
        assert host == vm == [42]

    def test_binding_persists(self):
        host, vm = _run_both('动态解析("y = 5")\n输出(y)')
        assert host == vm == [5]

    def test_binding_overwrite(self):
        host, vm = _run_both('let x = 1\n动态解析("x = 99")\n输出(x)')
        assert host == vm == [99]

    def test_function_defined_and_callable(self):
        host, vm = _run_both(
            '动态解析("let 三倍 = (n) => n * 3")\n输出(三倍(4))')
        assert host == vm == [12]

    def test_reads_outer_binding(self):
        host, vm = _run_both('let 基 = 10\n输出(动态解析("基 * 2"))')
        assert host == vm == [20]

    def test_output_side_effect_shared_stream(self):
        host, vm = _run_both('动态解析("输出(7)")')
        assert host == vm == [7]

    def test_no_tail_returns_null(self):
        host, vm = _run_both('输出(动态解析("let z = 1"))')
        assert host == vm == [None]

    def test_empty_fragment_returns_null(self):
        host, vm = _run_both('输出(动态解析(""))')
        assert host == vm == [None]

    def test_fragment_calls_outer_function(self):
        host, vm = _run_both(
            'let 加倍 = (n) => n * 2\n输出(动态解析("加倍(5)"))')
        assert host == vm == [10]

    def test_multi_statement_fragment(self):
        host, vm = _run_both('输出(动态解析("a = 1\\n输出(a)\\na + 41"))')
        assert host == vm == [1, 42]

    def test_string_literal_tail(self):
        host, vm = _run_both('输出(动态解析("\\"你好\\""))')
        assert host == vm == ["你好"]

    def test_variable_tail(self):
        host, vm = _run_both('let 名 = "值"\n输出(动态解析("名"))')
        assert host == vm == ["值"]

    def test_recursive_function_in_fragment(self):
        host, vm = _run_both(
            '动态解析("let rec 阶乘 = (n) => if n === 0 then 1 else n * 阶乘(n - 1)")\n'
            '输出(阶乘(5))')
        assert host == vm == [120]

    def test_fragment_defined_function_called_in_later_fragment(self):
        host, vm = _run_both(
            '动态解析("let 三倍 = (n) => n * 3")\n'
            '输出(动态解析("三倍(4)"))')
        assert host == vm == [12]

    def test_curried_call_in_fragment(self):
        host, vm = _run_both(
            '动态解析("let 连加 = (a) => (b) => a + b")\n输出(连加(2)(3))')
        assert host == vm == [5]


class TestDynamicEvalHonest:
    """诚实边界：显式拒绝 + 双端一致错误 + 登记分歧现状锁。"""

    def test_non_string_rejected_both_faces(self):
        msg = "动态解析: 需要文本源码，得到 123"
        h_out, h_err = _host_err("动态解析(123)")
        v_out, v_err = _vm_err("动态解析(123)")
        assert h_err is not None and msg in h_err
        assert v_err is not None and msg in v_err
        assert h_out == v_out == []

    def test_parse_error_propagates_both_faces(self):
        h_out, h_err = _host_err('动态解析("let (")')
        v_out, v_err = _vm_err('动态解析("let (")')
        assert h_err is not None and "期望 绑定名" in h_err
        assert v_err is not None and "期望 绑定名" in v_err
        assert h_out == v_out == []

    def test_undefined_name_in_fragment(self):
        msg = "未定义变量 '不存在变量'"
        h_out, h_err = _host_err('输出(动态解析("不存在变量 + 1"))')
        v_out, v_err = _vm_err('输出(动态解析("不存在变量 + 1"))')
        assert h_err is not None and msg in h_err
        assert v_err is not None and msg in v_err

    def test_undefined_function_in_fragment(self):
        msg = "未定义变量 '不存在的函数'"
        h_out, h_err = _host_err('输出(动态解析("不存在的函数(1)"))')
        v_out, v_err = _vm_err('输出(动态解析("不存在的函数(1)"))')
        assert h_err is not None and msg in h_err
        assert v_err is not None and msg in v_err

    def test_local_visibility_divergence_registered(self):
        """登记分歧现状锁（宿主动态作用域 vs VM 帧局部）：

        函数体内动态解析引用局部名——宿主面单环境可见（返回 21）；
        VM 面嵌套 VM 只共享全局，帧局部不跨编译单元（未定义变量 'n'）。
        顶层动态求值双面一致（TestDynamicEvalParity 全绿）；此形态为
        如实登记的架构边界，防回潮。
        """
        src = 'let 试探 = (n) =>\n  动态解析("n * 3")\n输出(试探(7))'
        h_out, h_err = _host_err(src)
        v_out, v_err = _vm_err(src)
        assert h_err is None and h_out == [21]
        assert v_err is not None and "未定义变量 'n'" in v_err


class TestDynamicEvalMechanics:
    """机制面：共享全局对象 / 哨兵零污染 / 动态闭包外层可调。"""

    def _make_vm(self, prog):
        from src.kernel.exec_api import _wire_plugin_runtime
        from src.mbc.vm import VM
        mod = exec_api.compile_module(prog)
        vm = VM(mod)
        _wire_plugin_runtime(vm)
        vm.run()
        return vm

    def test_vm_globals_shared_persistence(self):
        vm = self._make_vm('动态解析("y = 5")')
        assert vm.globals.get("y") == 5

    def test_vm_sentinel_not_polluting(self):
        vm = self._make_vm('输出(动态解析("1 + 1"))')
        assert "__动态解析值__" not in vm.globals
        assert vm.outputs == [2]

    def test_dynamic_closure_callable_after_eval(self):
        vm = self._make_vm('动态解析("let 三倍 = (n) => n * 3")')
        fn = vm.globals.get("三倍")
        assert fn is not None
        assert vm.invoke_value(fn, [4]) == 12

    def test_host_env_writeback(self):
        ip = Interpreter()
        ip.run(parse('动态解析("y = 5")'))
        assert ip.env.get("y") == 5


class TestDynamicEvalResourceLoop:
    """资源库代码化闭环（缺陷修复收口）：资源库源码 → 动态求值 → 当代码调用。"""

    def test_inline_func_source_both_faces(self):
        host, vm = _run_both(
            'let 源 = "func 动能(m: Float, v: Float) -> Float = '
            '(m, v) => 0.5 * m * v ^ 2"\n'
            '动态解析(源)\n输出(动能(2, 3))')
        assert host == vm == [9.0]

    def test_inline_module_source_both_faces(self):
        host, vm = _run_both(
            'let 源 = "module 计算动能 { func 动能(m: Float, v: Float) -> '
            'Float = (m, v) => 0.5 * m * v ^ 2 }"\n'
            '动态解析(源)\n输出(动能(2, 3))\n输出(计算动能.动能(2, 3))')
        assert host == vm == [9.0, 9.0]

    def test_library_entry_via_resource_read_host(self):
        """真资源库闭环（宿主面）：资源_读取 → 动态解析 → 平面调用 + 命名空间调用。

        资源_读取 为宿主面内建（VM 面登记边界，见阶段 21 收官登记），
        此锁钉宿主面全链；VM 面库源码闭环由上方内联形态双面锁覆盖。
        """
        ip = Interpreter()
        ip.run(parse(
            '动态解析(资源_读取("core/计算动能", 0))\n'
            '输出(动能(2, 3))\n输出(计算动能.动能(2, 3))'))
        assert ip.outputs == [9.0, 9.0]
