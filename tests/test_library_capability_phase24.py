# -*- coding: utf-8 -*-
"""阶段 24h：资源库新能力模块（建模仿真 / 单片机）双面锁。

24e/24f 域符号之上的纯 Matha 组合层落进 matha/library/（24a 缺陷修复
「资源库当代码用」的延伸面）：use 建模仿真 / use 单片机 双面可达、
真调用、模板程序化构造（呼吸灯 模拟写 斜坡 = 资源库生成指令列表）。

本文件锁（host = Interpreter，vm = exec_api.run_checked 双面对拍）：
  A. 建模仿真：双法对比（RK4 对齐 exp(-2) 至 1e-9、误差 = |欧拉−RK4|）+
     步长扫描（RK4 误差随步数单调收敛）+ 轨迹抽样（含首条等间隔）；
  B. 单片机：闪灯程序 C 形态 + 闪灯图纸 SVG 形态 + 呼吸灯斜坡
     （22 条 analogWrite）+ 控制载荷协议归一化；
  C. 边界：非 PWM 引脚呼吸灯双面如实报错（域面校验穿透组合层）。
"""
from __future__ import annotations

import contextlib
import io
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.interp import Interpreter  # noqa: E402
from src.kernel import exec_api  # noqa: E402

E2 = math.exp(-2.0)


def _host_run(source: str) -> list:
    ip = Interpreter(debug=False)
    with contextlib.redirect_stdout(io.StringIO()):
        ip.run(parse_src(source))
    return list(ip.outputs)


def parse_src(source: str):
    from src.parser import parse
    return parse(source)


def _vm_run(source: str) -> list:
    outs, err = exec_api.run_checked(source, mode="vm")
    assert err is None, f"vm 面不应报错: {type(err).__name__}: {err}"
    return list(outs)


def _run(face: str, source: str) -> list:
    return _host_run(source) if face == "host" else _vm_run(source)


# ============================================================
# A. 建模仿真组合层
# ============================================================

_双法对比 = (
    "use 建模仿真\n"
    "let r = 双法对比((t, y) => 0 - y, 1, 0, 2, 1000)\n"
    "输出(r[0])\n"
    "输出(r[1])\n"
    "输出(r[2])\n"
)

_步长扫描 = (
    "use 建模仿真\n"
    "let 行表 = 步长扫描((t, y) => 0 - y, 1, 0, 2, [10, 100, 1000])\n"
    "输出(len(行表))\n"
    "输出(行表[0][0])\n"
    "输出(行表[2][0])\n"
    "输出(行表[0][2])\n"
    "输出(行表[2][2])\n"
)

_轨迹抽样 = (
    "use 建模仿真\n"
    "let r = 仿真_欧拉({\"导函数\": (t, y) => 0 - y, \"初值\": 1, "
    "\"起点\": 0, \"终点\": 2, \"步数\": 1000})\n"
    "let s = 轨迹抽样(r, 250)\n"
    "输出(len(s))\n"
    "输出(s[0])\n"
    "输出(len(r[\"轨迹\"]))\n"
)


class TestSimLibrary:

    @pytest.mark.parametrize("face", ["host", "vm"])
    def test_双法对比_rk4_matches_exp(self, face):
        outs = _run(face, _双法对比)
        euler, rk4, err = outs
        assert rk4 == pytest.approx(E2, abs=1e-9)
        assert euler == pytest.approx(E2, abs=5e-3)
        assert err == pytest.approx(abs(euler - rk4), abs=1e-15)

    @pytest.mark.parametrize("face", ["host", "vm"])
    def test_步长扫描_rk4_converges_monotonically(self, face):
        outs = _run(face, _步长扫描)
        n_rows, first_n, last_n, rk4_coarse, rk4_fine = outs
        assert (n_rows, first_n, last_n) == (3, 10, 1000)
        assert rk4_fine == pytest.approx(E2, abs=1e-9)
        assert abs(rk4_coarse - E2) > abs(rk4_fine - E2)

    @pytest.mark.parametrize("face", ["host", "vm"])
    def test_轨迹抽样_first_entry_and_stride(self, face):
        outs = _run(face, _轨迹抽样)
        assert outs == [5, [0.0, 1], 1001]


# ============================================================
# B. 单片机组合层
# ============================================================

_闪灯程序 = (
    "use 单片机\n"
    "let r = 闪灯程序(\"uno\", 13, 500)\n"
    "输出(r[\"代码\"])\n"
)

_闪灯图纸 = (
    "use 单片机\n"
    "let s = 闪灯图纸(\"uno\", 13)\n"
    "输出(s[\"svg\"])\n"
    "输出(s[\"板\"])\n"
    "输出(s[\"元件数\"])\n"
)

_呼吸灯 = (
    "use 单片机\n"
    "let r = 呼吸灯程序(\"uno\", 9)\n"
    "输出(r[\"代码\"])\n"
)

_控制载荷 = (
    "use 单片机\n"
    "let p = 控制载荷(\"uno\", [[\"数字写\", 13, \"高\"], [\"延时\", 100]])\n"
    "输出(p)\n"
)


class TestMcuLibrary:

    @pytest.mark.parametrize("face", ["host", "vm"])
    def test_闪灯程序_arduino_c_shape(self, face):
        code = _run(face, _闪灯程序)[0]
        assert "void setup()" in code and "void loop()" in code
        assert "pinMode(13, OUTPUT);" in code
        assert "digitalWrite(13, HIGH);" in code
        assert "digitalWrite(13, LOW);" in code
        assert "delay(500);" in code

    @pytest.mark.parametrize("face", ["host", "vm"])
    def test_闪灯图纸_svg_shape(self, face):
        outs = _run(face, _闪灯图纸)
        svg, board, count = outs
        assert board == "uno" and count == 1
        assert "<svg" in svg and "</svg>" in svg
        assert "LED" in svg and "D13" in svg

    @pytest.mark.parametrize("face", ["host", "vm"])
    def test_呼吸灯_ramp_is_generated_instruction_list(self, face):
        code = _run(face, _呼吸灯)[0]
        assert code.count("analogWrite(9,") == 22
        assert code.count("delay(15);") == 22
        assert "void loop()" in code

    @pytest.mark.parametrize("face", ["host", "vm"])
    def test_控制载荷_protocol_payload(self, face):
        outs = _run(face, _控制载荷)
        assert outs == [{
            "指令": [["digitalWrite", 13, "HIGH"], ["delay", 100]],
            "条数": 2, "板": "uno", "协议": "matha-mcu-ctl/1",
        }]


# ============================================================
# C. 边界：域面校验穿透组合层（双面如实报错）
# ============================================================

_非PWM = "use 单片机\n输出(呼吸灯程序(\"uno\", 13))\n"


class TestHonestBoundary:

    def test_非PWM引脚_host(self):
        with pytest.raises(Exception) as ei:
            _host_run(_非PWM)
        assert "PWM 引脚" in str(ei.value)

    def test_非PWM引脚_vm(self):
        _, err = exec_api.run_checked(_非PWM, mode="vm")
        assert err is not None
        assert "PWM 引脚" in str(err)
