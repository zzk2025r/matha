# -*- coding: utf-8 -*-
"""阶段 24e 三锁：建模仿真（仿真_欧拉 / 仿真_龙格库塔 数值积分双面回调）。

对拍锁：host/vm 双面输出逐位一致（同一 Python 浮点运算序列）+ 解析解近似。
诚实锁：规格校验错误消息双面逐字一致 + 清单物化面 VM 闭包显式拒绝 +
回调内 Matha 错误原样传播。机械锁：清单注册 + 注入面惰性（零急切 import）+
setdefault 程序自定义优先。
"""
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.interp import Interpreter  # noqa: E402
from src.kernel import exec_api  # noqa: E402


def _parse(src):
    from src.parser import parse
    return parse(src)


def _run_both(src):
    """双面运行：host 输出 + vm run_checked 输出（错误必须为 None 且逐位一致）。"""
    ip = Interpreter()
    ip.run(_parse(src))
    outs, err = exec_api.run_checked(src, mode="vm")
    assert err is None, f"VM 错误: {err}"
    assert outs == ip.outputs, f"双面分歧: host={ip.outputs} vm={outs}"
    return ip.outputs


def _host_err(src):
    ip = Interpreter()
    try:
        ip.run(_parse(src))
        return ip.outputs, None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def _vm_err(src):
    outs, err = exec_api.run_checked(src, mode="vm")
    return outs, (str(err) if err is not None else None)


# ============================================================
# 对拍锁：双面一致 + 解析解近似
# ============================================================

class TestSimulationParity:
    """欧拉/RK4 数值积分双面逐位一致。"""

    def test_euler_decay_exact_parity(self):
        # y' = -y, y(0)=1, [0,2]×1000 步：解析解 e^-2
        src = (
            'let r = 仿真_欧拉({"导函数": (t, y) => -y, "初值": 1, '
            '"起点": 0, "终点": 2, "步数": 1000})\n'
            '输出(r["方法"])\n输出(r["末态"])\n输出(r["步数"])\n'
        )
        outs = _run_both(src)
        assert outs[0] == "欧拉"
        assert abs(outs[1] - math.exp(-2)) < 1e-3
        assert outs[2] == 1000

    def test_rk4_accuracy_order(self):
        # RK4 n=50：误差 O(h^4)，远小于欧拉
        src = (
            'let r = 仿真_龙格库塔({"导函数": (t, y) => -y, "初值": 1, '
            '"起点": 0, "终点": 2, "步数": 50})\n'
            '输出(r["方法"])\n输出(r["末态"])\n'
        )
        outs = _run_both(src)
        assert outs[0] == "龙格库塔"
        assert abs(outs[1] - math.exp(-2)) < 1e-6

    def test_vector_spring_period(self):
        # 弹簧振子 x''=-x：t=2π 回到 x≈1（周期闭合）
        src = (
            'let r = 仿真_龙格库塔({"导函数": (t, s) => [s[1], -s[0]], '
            '"初值": [1, 0], "起点": 0, "终点": 6.283185307179586, "步数": 2000})\n'
            '输出(r["末态"][0])\n'
        )
        outs = _run_both(src)
        assert outs[0] == pytest.approx(1.0, abs=1e-9)

    def test_trajectory_shape(self):
        # 轨迹 n+1 条，首条 [起点, 初值]，末条 [终点, 末态]
        src = (
            'let r = 仿真_欧拉({"导函数": (t, y) => -y, "初值": 2, '
            '"起点": 1, "终点": 3, "步数": 100})\n'
            '输出(r["轨迹"][0])\n输出(r["轨迹"][100])\n'
        )
        outs = _run_both(src)
        assert outs[0] == [1.0, 2]
        assert outs[1][0] == pytest.approx(3.0)
        assert outs[1][1] == pytest.approx(2 * math.exp(-2), abs=5e-2)

    def test_trajectory_python_side_structure(self):
        # Python 侧结构锁：轨迹长度 = 步数+1，末态与末轨迹条目同值
        ip = Interpreter()
        ip.run(_parse(
            'let r = 仿真_欧拉({"导函数": (t, y) => -y, "初值": 1, '
            '"起点": 0, "终点": 2, "步数": 40})'))
        r = ip.env["r"]
        assert r["方法"] == "欧拉"
        assert len(r["轨迹"]) == 41
        assert r["轨迹"][0] == [0.0, 1]
        assert r["末态"] == r["轨迹"][-1][1]

    def test_callback_closes_over_outer_binding(self):
        # 导函数闭包引用外层绑定（阻尼系数）——双面一致
        src = (
            'let 阻尼 = 0.5\n'
            'let r = 仿真_龙格库塔({"导函数": (t, y) => -阻尼 * y, "初值": 1, '
            '"起点": 0, "终点": 2, "步数": 200})\n'
            '输出(r["末态"])\n'
        )
        outs = _run_both(src)
        assert outs[0] == pytest.approx(math.exp(-1.0), abs=1e-6)

    def test_int_initial_value(self):
        # 整数初值：首轨迹条目保持原值，推进后转浮点
        src = (
            'let r = 仿真_欧拉({"导函数": (t, y) => 0 * y + 1, "初值": 1, '
            '"起点": 0, "终点": 1, "步数": 10})\n'
            '输出(r["轨迹"][0])\n输出(r["轨迹"][10])\n'
        )
        outs = _run_both(src)
        assert outs[0] == [0.0, 1]
        assert outs[1][1] == pytest.approx(2.0, abs=1e-9)

    def test_euler_rk4_same_problem_diverge_honestly(self):
        # 同一问题两方法不同末态（欧拉误差可见）——双面各自一致
        spec = '"导函数": (t, y) => -y, "初值": 1, "起点": 0, "终点": 1, "步数": 10'
        e = _run_both(f'let r = 仿真_欧拉({{{spec}}})\n输出(r["末态"])')
        rk = _run_both(f'let r = 仿真_龙格库塔({{{spec}}})\n输出(r["末态"])')
        assert e[0] != rk[0]
        assert abs(rk[0] - math.exp(-1)) < abs(e[0] - math.exp(-1))


# ============================================================
# 闭环：资源库当代码用 → 动态解析 → 仿真
# ============================================================

class TestSimulationResourceLoop:
    """建模 → 资源 → 调用：资源库代码化链路上的仿真能力。"""

    def test_dynamic_eval_defines_model_then_simulate(self):
        # 动态解析定义动力学模型 → 仿真调用（闭环面，双面一致）
        src = (
            '动态解析("let 阻尼振动 = (t, s) => [s[1], -0.2 * s[1] - 4 * s[0]]")\n'
            'let r = 仿真_龙格库塔({"导函数": 阻尼振动, "初值": [1, 0], '
            '"起点": 0, "终点": 1.5707963267948966, "步数": 1500})\n'
            '输出(r["末态"][0])\n'
        )
        outs = _run_both(src)
        # 半周期（ω=2 → π/2）后位移翻转为负（阻尼衰减幅度略小于 1）
        assert outs[0] < -0.7


# ============================================================
# 诚实锁：显式拒绝 + 双面逐字一致错误
# ============================================================

_ERR_CASES = [
    ('仿真_欧拉(123)', "仿真: 规格须为字典"),
    ('仿真_欧拉({"初值": 1, "终点": 2})', "仿真: 规格缺少「导函数」"),
    ('仿真_欧拉({"导函数": (t, y) => -y, "终点": 2})', "仿真: 规格缺少「初值」"),
    ('仿真_欧拉({"导函数": (t, y) => -y, "初值": 1})', "仿真: 规格缺少「终点」"),
    ('仿真_欧拉({"导函数": 123, "初值": 1, "终点": 2})', "仿真: 「导函数」须为函数"),
    ('仿真_欧拉({"导函数": (t, y) => -y, "初值": "x", "终点": 2})',
     "仿真: 「初值」须为数值或数值列表"),
    ('仿真_欧拉({"导函数": (t, y) => -y, "初值": [], "终点": 2})',
     "仿真: 「初值」列表须为非空数值列表"),
    ('仿真_欧拉({"导函数": (t, y) => -y, "初值": 1, "起点": "a", "终点": 2})',
     "仿真: 「起点」须为数值"),
    ('仿真_欧拉({"导函数": (t, y) => -y, "初值": 1, "起点": 2, "终点": 2})',
     "仿真: 「终点」须大于「起点」"),
    ('仿真_欧拉({"导函数": (t, y) => -y, "初值": 1, "终点": 2, "步数": 0})',
     "仿真: 「步数」须为正整数"),
    ('仿真_欧拉({"导函数": (t, y) => -y, "初值": 1, "终点": 2, "步数": 真})',
     "仿真: 「步数」须为正整数"),
    ('输出(仿真_欧拉({"导函数": (t, s) => 5, "初值": [1, 0], "终点": 1, '
     '"步数": 10})["末态"])', "仿真: 导函数须返回长度 2 的数值列表"),
    ('仿真_龙格库塔({"导函数": (t, y) => -y, "初值": 1, "终点": 2, "步数": -1})',
     "仿真: 「步数」须为正整数"),
]


class TestSimulationHonest:
    """诚实边界：规格校验双面逐字一致 + 回调错误原样传播。"""

    @pytest.mark.parametrize("src,frag", _ERR_CASES)
    def test_spec_validation_parity(self, src, frag):
        h_out, h_err = _host_err(src)
        assert h_err is not None and frag in h_err, h_err
        v_out, v_err = _vm_err(src)
        assert v_err is not None and frag in v_err, v_err

    def test_callback_error_propagates_verbatim(self):
        src = '仿真_欧拉({"导函数": (t, y) => y / 0, "初值": 1, "终点": 1, "步数": 5})'
        h_out, h_err = _host_err(src)
        v_out, v_err = _vm_err(src)
        assert h_err is not None and "除零错误" in h_err
        assert v_err is not None and "除零错误" in v_err

    def test_vm_closure_rejected_on_manifest_face(self):
        # 清单物化面（共享语境解释器）收到 VM 闭包 → 显式拒绝并指向官方入口
        from src.mbc.vm import VM
        from src.domains.simulation import integrate_euler_plain
        mod = exec_api.compile_module('let f = (t, y) => -y')
        vm = VM(mod)
        vm.run()
        closure = vm.globals["f"]
        assert type(closure).__name__ == "Closure"
        with pytest.raises(ValueError, match="官方入口"):
            integrate_euler_plain({"导函数": closure, "初值": 1,
                                   "起点": 0, "终点": 1, "步数": 10})

    def test_manifest_face_accepts_host_closure(self):
        # 清单物化面：宿主闭包（跨解释器实例，闭包元组自带捕获环境）可回调
        from src.domains.simulation import integrate_euler_plain
        ip = Interpreter()
        ip.run(_parse('let f = (t, y) => -y'))
        r = integrate_euler_plain({"导函数": ip.env["f"], "初值": 1,
                                   "起点": 0, "终点": 2, "步数": 100})
        assert r["方法"] == "欧拉"
        assert abs(r["末态"] - math.exp(-2)) < 5e-3


# ============================================================
# 机械锁：清单注册 + 注入面纪律
# ============================================================

class TestSimulationWiring:
    """清单数据 + 注入面：惰性跳板 / setdefault 程序优先。"""

    def test_manifest_contains_simulation(self):
        from src.plugin_api import MANIFEST_PATH
        with open(MANIFEST_PATH, encoding="utf-8") as f:
            m = json.load(f)
        plug = next(p for p in m["plugins"] if p["module"] == "src.domains.simulation")
        assert "仿真_欧拉" in plug["symbols"]
        assert "仿真_龙格库塔" in plug["symbols"]

    def test_lazy_trampoline_no_eager_import(self):
        # 注入面惰性：构造零 import，首次调用才装入插件（eval/auto 纪律）
        code = (
            "import sys\n"
            "sys.path.insert(0, r'" + str(ROOT) + "')\n"
            "from src.kernel.exec_api import compile_module\n"
            "from src.mbc.vm import VM\n"
            "from src.plugin_api import make_simulation_runtime\n"
            "vm = VM(compile_module(''))\n"
            "glue = make_simulation_runtime(vm)\n"
            "assert 'src.domains.simulation' not in sys.modules, '构造即 import'\n"
            "try:\n"
            "    glue['仿真_欧拉']('触发物化')\n"
            "except Exception:\n"
            "    pass\n"
            "assert 'src.domains.simulation' in sys.modules, '首调未物化'\n"
            "print('OK')\n"
        )
        p = subprocess.run([sys.executable, "-c", code], capture_output=True,
                           text=True, timeout=120)
        assert p.returncode == 0 and p.stdout.strip() == "OK", p.stderr[-500:]

    def test_program_defined_symbol_wins(self):
        # setdefault 纪律：程序自定义同名函数不被注入面覆盖
        src = (
            'func 仿真_欧拉(规格) -> String = (规格) => "自定义"\n'
            '输出(仿真_欧拉({}))\n'
        )
        assert _run_both(src) == ["自定义"]

    def test_wire_injects_runtime_bound_versions(self):
        # 官方入口运行面：仿真符号在纯 VM 程序里可直接调用（注入版生效）
        code = (
            "import sys\n"
            "sys.path.insert(0, r'" + str(ROOT) + "')\n"
            "from src.kernel import exec_api\n"
            "outs, err = exec_api.run_checked(\n"
            "    '输出(仿真_欧拉({\"导函数\": (t, y) => -y, \"初值\": 1, "
            "\"终点\": 1, \"步数\": 10})[\"末态\"])', mode='vm')\n"
            "assert err is None, err\n"
            "print('OK', outs[0])\n"
        )
        p = subprocess.run([sys.executable, "-c", code], capture_output=True,
                           text=True, timeout=120)
        assert p.returncode == 0, p.stderr[-500:]
        assert "OK" in p.stdout
