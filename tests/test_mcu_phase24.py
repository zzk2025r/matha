# -*- coding: utf-8 -*-
"""阶段 24f 三锁：单片机面（图纸/编程/控制/烧录/驱动/写入）。

锁四面：
  A. 双面对拍 —— Matha 程序 host/VM 同值（SVG 真生成 + Arduino C 真代码
     生成 + 控制载荷归一化 + 驱动模板 + 文件落盘）；
  B. 诚实拒绝 —— 未知板型/元件/指令、非法电平、非 PWM 引脚、setup/loop
     分面越界、串口实时显式拒绝、hex 缺失、目录缺失，双面消息同形；
  C. 烧录真面 —— 注入 which/run 断言真实 argv 形态（avr/stm32/esp32/
     rp2040 四族）、退出码非零显式失败、工具缺失显式拒绝（不伪装成功）；
  D. 装配面 —— manifest 登记、SVG xml 可解析、读指令自动串口头、C 转义。
"""
import io
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.domains import mcu  # noqa: E402
from src.interp import Interpreter  # noqa: E402
from src.kernel import exec_api  # noqa: E402
from src.parser import parse  # noqa: E402
from src.plugin_api import MANIFEST_PATH  # noqa: E402

MANIFEST = json.loads(Path(MANIFEST_PATH).read_text(encoding="utf-8"))


def _host_run(source: str) -> list:
    ip = Interpreter()
    with redirect_stdout(io.StringIO()):
        ip.run(parse(source))
    return [str(o) for o in ip.outputs]


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

class TestMcuParity:
    UNO_SCHEMATIC = ('let 图 = 单片机_图纸({板: "uno", '
                     '元件: [["LED", 13], ["按键", 2]]})\n'
                     '输出(图.元件数)\n输出(图.板)\n输出(len(图.svg) > 0)')

    def test_schematic_uno_two_components(self):
        h = _host_run(self.UNO_SCHEMATIC)
        v = _vm_run(self.UNO_SCHEMATIC)
        assert h == ["2", "uno", "True"]
        assert h == v

    def test_schematic_analog_pin_component(self):
        src = ('let 图 = 单片机_图纸({板: "nano", '
               '元件: [["传感器", "A0"], ["电位器", "A1"]]})\n'
               '输出(图.元件数)')
        assert _host_run(src) == ["2"]
        assert _host_run(src) == _vm_run(src)

    NANO_PROGRAM = ('let c = 单片机_编程({板: "nano", '
                    '设置: [["串口开始", 115200], ["数字模式", 13, "输出"]], '
                    '循环: [["数字写", 13, "高"], ["延时", 500], '
                    '["数字写", 13, "低"], ["延时", 500]]})\n'
                    '输出(c.板)\n输出(len(c.代码) > 0)\n输出(c.字节数 > 0)')

    def test_program_nano_blink_code(self):
        h = _host_run(self.NANO_PROGRAM)
        v = _vm_run(self.NANO_PROGRAM)
        assert h == ["nano", "True", "True"]
        assert h == v

    def test_program_code_shape(self):
        ip = Interpreter()
        with redirect_stdout(io.StringIO()):
            ip.run(parse(self.NANO_PROGRAM))
        c = ip.env["c"]
        code = c["代码"]
        assert "void setup()" in code and "void loop()" in code
        assert "pinMode(13, OUTPUT);" in code
        assert "digitalWrite(13, HIGH);" in code
        assert "digitalWrite(13, LOW);" in code
        assert "delay(500);" in code

    CONTROL = ('let k = 单片机_控制({板: "uno", 指令: '
               '[["数字写", 13, "高"], ["数字写", 13, "低"]]})\n'
               '输出(k.条数)\n输出(k.板)\n输出(k.协议)')

    def test_control_payload(self):
        h = _host_run(self.CONTROL)
        v = _vm_run(self.CONTROL)
        assert h == ["2", "uno", "matha-mcu-ctl/1"]
        assert h == v

    def test_control_payload_shape(self):
        ip = Interpreter()
        with redirect_stdout(io.StringIO()):
            ip.run(parse(self.CONTROL))
        k = ip.env["k"]
        assert k["指令"] == [["digitalWrite", 13, "HIGH"],
                            ["digitalWrite", 13, "LOW"]]

    def test_driver_pwm_breathing(self):
        src = ('let d = 单片机_驱动({外设: "pwm", 板: "uno", 引脚: 9})\n'
               '输出(d.外设)\n输出(len(d.代码) > 0)')
        h = _host_run(src)
        v = _vm_run(src)
        assert h == ["pwm", "True"]
        assert h == v

    def test_driver_gpio_mega_pin22(self):
        src = ('let d = 单片机_驱动({外设: "gpio", 板: "mega", 引脚: 22})\n'
               '输出(len(d.代码) > 0)')
        assert _host_run(src) == ["True"]
        assert _host_run(src) == _vm_run(src)

    def test_write_file_roundtrip(self, tmp_path):
        target = tmp_path / "drv_gpio.c"
        src = (f'let w = 单片机_写入("{target.as_posix()}")("// smoke")\n'
               '输出(w.成功)\n输出(w.字节数)')
        h = _host_run(src)
        v = _vm_run(src)
        assert h == ["True", "8"]
        assert h == v
        assert target.read_text(encoding="utf-8") == "// smoke"

    def test_e2e_driver_then_write(self, tmp_path):
        """驱动真生成 → 写入真落盘 → 读回逐字节一致（资源库当代码用闭环）。"""
        target = tmp_path / "pwm9.c"
        gen = 'let d = 单片机_驱动({外设: "pwm", 板: "uno", 引脚: 9})'
        src = (f'{gen}\n'
               f'let w = 单片机_写入("{target.as_posix()}")(d.代码)\n'
               '输出(w.成功)\n输出(w.字节数 > 0)')
        h = _host_run(src)
        v = _vm_run(src)
        assert h == ["True", "True"]
        assert h == v
        ip = Interpreter()
        with redirect_stdout(io.StringIO()):
            ip.run(parse(gen))
        code = ip.env["d"]["代码"]
        assert target.read_text(encoding="utf-8") == code
        assert code.count("analogWrite") == 2


# ============================================================
# B. 诚实拒绝（双面消息同形）
# ============================================================

_ERR_CASES = [
    ('单片机_图纸({板: "x86"})', "未知板型"),
    ('单片机_图纸({板: "uno", 元件: []})', "须为非空元件列表"),
    ('单片机_图纸({板: "uno", 元件: [["继电器", 5]]})', "未知元件"),
    ('单片机_图纸({板: "uno", 元件: [["LED", 99]]})', "超出"),
    ('单片机_编程({板: "nano"})', "缺少程序体"),
    ('单片机_编程({板: "nano", 设置: [["眨眼", 5]]})', "未知指令"),
    ('单片机_编程({板: "nano", 循环: [["数字写", 13, "中"]]})', "电平须为 高/低"),
    ('单片机_编程({板: "nano", 循环: [["模拟写", 8, 100]]})', "PWM"),
    ('单片机_编程({板: "nano", 设置: [["数字读", 2]]})', "只能出现在「循环」"),
    ('单片机_编程({板: "nano", 循环: [["串口开始", 9600]]})', "只能出现在「设置」"),
    ('单片机_控制({板: "uno", 连接: "COM3", 指令: [["数字写", 13, "高"]]})',
     "串口实时控制在纯标准库边界外"),
    ('单片机_控制({板: "uno", 指令: []})', "「指令」须为非空指令列表"),
    ('单片机_驱动({外设: "can", 板: "uno"})', "「外设」须为"),
    ('单片机_驱动({外设: "pwm", 板: "uno", 引脚: 8})', "不是 uno 的 PWM 引脚"),
    ('单片机_烧录({板: "uno", 十六进制: "no_such_file.hex"})', "十六进制文件不存在"),
    ('单片机_写入("no_dir_zz/x.c")("x")', "目标目录不存在"),
    ('单片机_写入("x.c")(42)', "「内容」须为文本"),
]


class TestMcuHonest:
    @pytest.mark.parametrize("src,frag", _ERR_CASES)
    def test_reject_both_faces(self, src, frag):
        h = _host_err(src)
        v = _vm_err(src)
        assert frag in h, f"host 缺「{frag}」: {h}"
        assert frag in v, f"vm 缺「{frag}」: {v}"

    def test_serial_realtime_boundary_explicit(self):
        """串口实时收发显式拒绝（不假装已连板）——消息必须点明边界。"""
        v = _vm_err('单片机_控制({板: "uno", 连接: "COM3", 指令: [["数字写", 13, "高"]]})')
        assert "纯标准库边界外" in v and "无串口传输面" in v

    def test_flash_tool_missing_explicit(self, tmp_path):
        """hex 存在但工具链缺失 → 显式拒绝（不伪装成功）。"""
        hexfile = tmp_path / "blink.hex"
        hexfile.write_text(":00000001FF", encoding="ascii")
        with pytest.raises(ValueError, match="未检测到工具链 avrdude"):
            mcu.flash({"板": "uno", "十六进制": str(hexfile),
                       "端口": "COM3"}, which=lambda tool: None)


# ============================================================
# C. 烧录真面（注入 which/run，断言真实 argv）
# ============================================================

def _fake_run(returncode=0, stdout="", stderr=""):
    calls = {}

    def run(argv, capture_output=True, text=True, timeout=None):
        calls["argv"] = argv
        calls["kwargs"] = {"capture_output": capture_output,
                           "text": text, "timeout": timeout}
        return subprocess.CompletedProcess(argv, returncode,
                                           stdout=stdout, stderr=stderr)

    run.calls = calls
    return run


class TestMcuFlashArgv:
    def _hex(self, tmp_path):
        hexfile = tmp_path / "blink.hex"
        hexfile.write_text(":00000001FF", encoding="ascii")
        return str(hexfile)

    def test_avr_argv_exact(self, tmp_path):
        hexfile = self._hex(tmp_path)
        run = _fake_run(0, stdout="writing flash ok")
        res = mcu.flash({"板": "uno", "十六进制": hexfile, "端口": "COM3"},
                        which=lambda t: "C:/tools/avrdude.exe", run=run)
        assert res["成功"] is True and res["工具"] == "avrdude"
        assert run.calls["argv"] == [
            "C:/tools/avrdude.exe", "-c", "arduino", "-p", "atmega328p",
            "-P", "COM3", "-b", "115200",
            "-U", f"flash:w:{hexfile}:i"]
        assert run.calls["kwargs"] == {"capture_output": True,
                                       "text": True, "timeout": 120}
        assert res["输出"] == "writing flash ok"

    def test_stm32_argv(self, tmp_path):
        hexfile = self._hex(tmp_path)
        run = _fake_run(0)
        mcu.flash({"板": "stm32", "十六进制": hexfile},
                  which=lambda t: "st-flash", run=run)
        assert run.calls["argv"] == [
            "st-flash", "--port", "/dev/null", "write",
            hexfile, "0x08000000"]

    def test_esp32_argv(self, tmp_path):
        hexfile = self._hex(tmp_path)
        run = _fake_run(0)
        mcu.flash({"板": "esp32", "十六进制": hexfile, "端口": "COM7"},
                  which=lambda t: "esptool", run=run)
        assert run.calls["argv"] == [
            "esptool", "--chip", "esp32", "--port", "COM7",
            "write_flash", "0x1000", hexfile]

    def test_rp2040_argv(self, tmp_path):
        hexfile = self._hex(tmp_path)
        run = _fake_run(0)
        mcu.flash({"板": "rp2040", "十六进制": hexfile},
                  which=lambda t: "openocd", run=run)
        assert run.calls["argv"] == [
            "openocd", "-f", "interface/cmsis-dap.cfg",
            "-f", "target/rp2040.cfg",
            "-c", f"program {hexfile} verify reset exit"]

    def test_nonzero_exit_fails_loudly(self, tmp_path):
        hexfile = self._hex(tmp_path)
        run = _fake_run(1, stderr="avrdude: ser_open(): can't open device")
        with pytest.raises(ValueError,
                           match=r"烧录失败（avrdude 退出码 1）.*can't open device"):
            mcu.flash({"板": "uno", "十六进制": hexfile, "端口": "COM3"},
                      which=lambda t: "avrdude", run=run)

    def test_board_alias_resolves_same_argv(self, tmp_path):
        hexfile = self._hex(tmp_path)
        run = _fake_run(0)
        mcu.flash({"板": "arduino_uno", "十六进制": hexfile, "端口": "COM3"},
                  which=lambda t: "avrdude", run=run)
        assert "-p" in run.calls["argv"]
        assert run.calls["argv"][run.calls["argv"].index("-p") + 1] == "atmega328p"


# ============================================================
# D. 装配面
# ============================================================

class TestMcuWiring:
    def test_manifest_registers_mcu(self):
        plug = next(p for p in MANIFEST["plugins"] if p["name"] == "mcu")
        assert plug["module"] == "src.domains.mcu"
        assert set(plug["symbols"]) == {
            "单片机_图纸", "单片机_编程", "单片机_控制",
            "单片机_烧录", "单片机_驱动", "单片机_写入"}

    def test_svg_is_parseable_xml(self):
        ip = Interpreter()
        with redirect_stdout(io.StringIO()):
            ip.run(parse(self._uno_schematic()))
        svg = ip.env["图"]["svg"]
        root = ET.fromstring(svg)
        assert root.tag.endswith("svg")
        rects = [e for e in root.iter() if e.tag.endswith("rect")]
        assert len(rects) >= 2  # 背景板面 + 板体

    def _uno_schematic(self):
        return ('let 图 = 单片机_图纸({板: "uno", '
                '元件: [["LED", 13], ["蜂鸣器", 8]]})')

    def test_read_instruction_gets_serial_header(self):
        """读指令在循环 → 自动补 Serial.begin(9600) 与可观测打印。"""
        src = ('let c = 单片机_编程({板: "uno", '
               '循环: [["数字读", 2], ["模拟读", "A0"]]})')
        ip = Interpreter()
        with redirect_stdout(io.StringIO()):
            ip.run(parse(src))
        code = ip.env["c"]["代码"]
        assert "Serial.begin(9600);" in code
        assert "Serial.println(digitalRead(2));" in code
        assert "Serial.println(analogRead(A0));" in code

    def test_serial_print_escapes_c_string(self):
        src = ('let c = 单片机_编程({板: "uno", '
               '循环: [["串口打印", "说\\"你好\\""]]})')
        ip = Interpreter()
        with redirect_stdout(io.StringIO()):
            ip.run(parse(src))
        assert 'Serial.print("说\\"你好\\"");' in ip.env["c"]["代码"]

    def test_lazy_import_no_eager_domain_load(self):
        """宿主内建惰性装配：构造 Interpreter 不装载 mcu 域。"""
        code = (
            "import sys\n"
            "sys.path.insert(0, r'D:\\trae')\n"
            "from src.interp import Interpreter\n"
            "ip = Interpreter()\n"
            "assert 'src.domains.mcu' not in sys.modules, 'mcu 域被急切装载'\n"
            "print('LAZY-OK')\n")
        proc = subprocess.run([sys.executable, "-c", code],
                              capture_output=True, text=True, timeout=120)
        assert proc.returncode == 0, proc.stderr
        assert "LAZY-OK" in proc.stdout

    def test_program_defined_symbol_wins(self):
        """程序自定义同名符号优先（不覆盖程序定义）。"""
        src = ('func 单片机_图纸(规格) -> String = (规格) => "自定义"\n'
               '输出(单片机_图纸({板: "uno"}))')
        h = _host_run(src)
        assert h == ["自定义"]
        assert h == _vm_run(src)
