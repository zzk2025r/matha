"""Matha 领域扩展模块：单片机（Microcontroller）。

五面真化 + 写入（阶段 24f）：图纸 / 编程 / 控制 / 烧录 / 驱动 / 写入。
全部为**规格面**（单字典规格，无 Matha 回调），宿主内建与 VM 清单物化
面共用同一实现，双面逐字一致。

  * 单片机_图纸(规格) → SVG 电路示意图真生成（板型引脚 + 元件 + 连线，
    xml 可解析的合法 SVG 文本）；
  * 单片机_编程(规格) → Matha 指令规格 → Arduino C 源码真代码生成
    （setup/loop/指令集校验；模拟写仅限 PWM 引脚——诚实校验非假放行）；
  * 单片机_控制(规格) → 控制指令序列归一化校验（上位机协议载荷）；
    **串口实时收发显式拒绝**——纯标准库无串口传输（ctypes 为内核红线），
    规格含「连接」键即报错；
  * 单片机_烧录(规格) → 工具链真检测（shutil.which：avrdude / st-flash /
    esptool / openocd 按板族路由）→ **真 subprocess 烧录**；工具缺失、
    hex 文件不存在、烧录退出码非零均显式拒绝（不伪装成功）；
  * 单片机_驱动(规格) → GPIO/UART/I2C/SPI/PWM 五类 Arduino C 驱动模板
    真生成（引脚/PWM 能力按板型校验）；
  * 单片机_写入(路径)(内容) → UTF-8 文本真落盘（返回 成功/路径/字节数）。

已知边界（如实声明）：
  * 烧录是**真执行**：机器上装了 avrdude 并接了板子才会真的写芯片；
    未装工具链/未接板 → 显式报错，绝不返回假成功；
  * 代码生成产物是 Arduino C 源码文本，编译 .hex 需 arduino-cli（不在
    本域边界内——写入 + 外部工具链组合可完成）；
  * 板型矩阵：uno / nano / mega（AVR·avrdude）、stm32（st-flash）、
    esp32（esptool）、rp2040（openocd）。
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


# ============================================================
# 板型矩阵（真参数：MCU / 烧录工具 / 数字与模拟引脚 / PWM 引脚）
# ============================================================

_BOARDS = {
    "uno": {"mcu": "atmega328p", "family": "avr", "tool": "avrdude",
            "digital": 14, "analog": 6, "pwm": [3, 5, 6, 9, 10, 11]},
    "nano": {"mcu": "atmega328p", "family": "avr", "tool": "avrdude",
             "digital": 14, "analog": 8, "pwm": [3, 5, 6, 9, 10, 11]},
    "mega": {"mcu": "atmega2560", "family": "avr", "tool": "avrdude",
             "digital": 54, "analog": 16, "pwm": list(range(2, 14))},
    "stm32": {"mcu": "stm32f103c8t6", "family": "stm32", "tool": "st-flash",
              "digital": 0, "analog": 0, "pwm": []},
    "esp32": {"mcu": "esp32", "family": "esp32", "tool": "esptool",
              "digital": 0, "analog": 0, "pwm": []},
    "rp2040": {"mcu": "rp2040", "family": "rp2040", "tool": "openocd",
               "digital": 0, "analog": 0, "pwm": []},
}

_BOARD_ALIASES = {
    "arduino_uno": "uno", "unor3": "uno", "arduino": "uno",
    "arduino_nano": "nano", "arduino_mega": "mega",
    "bluepill": "stm32", "stm32f103": "stm32",
    "pico": "rp2040", "raspberry_pi_pico": "rp2040",
}


def _board(name):
    if not isinstance(name, str) or not name:
        raise ValueError("单片机: 「板」须为板型名（uno/nano/mega/stm32/esp32/rp2040）")
    key = _BOARD_ALIASES.get(name.strip().lower(), name.strip().lower())
    if key not in _BOARDS:
        raise ValueError(
            f"单片机: 未知板型「{name}」——支持：{'/'.join(sorted(_BOARDS))}"
            f"（别名：{'/'.join(sorted(_BOARD_ALIASES))}）")
    return key, _BOARDS[key]


# ============================================================
# 指令集（编程/控制共用）：归一化校验 → C 发射参数
# ============================================================

_PIN_MODES = {"输出": "OUTPUT", "输入": "INPUT", "上拉": "INPUT_PULLUP"}
_PIN_LEVELS = {"高": "HIGH", "低": "LOW"}
_INSTR_OPS = ("数字模式", "数字写", "数字读", "模拟写", "模拟读",
              "延时", "串口开始", "串口打印", "串口换行打印")


def _instr(op, args, board, ctx):
    """单条指令归一化校验，返回 C 发射所需的 (op, 归一参数)。

    ctx: "编程"（setup/loop 分面校验）或 "控制"（载荷归一化）。
    """
    if op == "数字模式":
        if len(args) != 2:
            raise ValueError("单片机: 「数字模式」须为 [数字模式, 引脚, 模式]")
        pin, mode = args
        _digital_pin(pin, board)
        if mode not in _PIN_MODES:
            raise ValueError(
                f"单片机: 「数字模式」模式须为 输出/输入/上拉，得到 {mode!r}")
        return ("pinMode", [int(pin), _PIN_MODES[mode]])
    if op == "数字写":
        if len(args) != 2:
            raise ValueError("单片机: 「数字写」须为 [数字写, 引脚, 电平]")
        pin, level = args
        _digital_pin(pin, board)
        if level not in _PIN_LEVELS:
            raise ValueError(
                f"单片机: 「数字写」电平须为 高/低，得到 {level!r}")
        return ("digitalWrite", [int(pin), _PIN_LEVELS[level]])
    if op == "数字读":
        if len(args) != 1:
            raise ValueError("单片机: 「数字读」须为 [数字读, 引脚]")
        _digital_pin(args[0], board)
        return ("digitalRead", [int(args[0])])
    if op == "模拟写":
        if len(args) != 2:
            raise ValueError("单片机: 「模拟写」须为 [模拟写, 引脚, 占空比]")
        pin, duty = args
        if isinstance(duty, bool) or not isinstance(duty, int) or not 0 <= duty <= 255:
            raise ValueError("单片机: 「模拟写」占空比须为整数 0–255")
        if pin not in board["pwm"]:
            raise ValueError(
                f"单片机: 引脚 {pin} 不是 {ctx}板型的 PWM 引脚"
                f"（{board['mcu']} PWM：{board['pwm']}）")
        return ("analogWrite", [int(pin), int(duty)])
    if op == "模拟读":
        if len(args) != 1:
            raise ValueError("单片机: 「模拟读」须为 [模拟读, 通道]")
        ch = args[0]
        if not isinstance(ch, str) or ch not in _analog_channels(board):
            raise ValueError(
                f"单片机: 「模拟读」通道须为 {'/'.join(_analog_channels(board))}")
        return ("analogRead", [ch])
    if op == "延时":
        if len(args) != 1:
            raise ValueError("单片机: 「延时」须为 [延时, 毫秒]")
        ms = args[0]
        if isinstance(ms, bool) or not isinstance(ms, int) or ms < 1:
            raise ValueError("单片机: 「延时」毫秒须为正整数")
        return ("delay", [ms])
    if op == "串口开始":
        if len(args) != 1:
            raise ValueError("单片机: 「串口开始」须为 [串口开始, 波特率]")
        baud = args[0]
        if isinstance(baud, bool) or not isinstance(baud, int) or baud < 1:
            raise ValueError("单片机: 「串口开始」波特率须为正整数")
        return ("serial_begin", [baud])
    if op == "串口打印":
        if len(args) != 1 or not isinstance(args[0], str):
            raise ValueError("单片机: 「串口打印」须为 [串口打印, 文本]")
        return ("serial_print", [args[0]])
    if op == "串口换行打印":
        if len(args) != 1 or not isinstance(args[0], str):
            raise ValueError("单片机: 「串口换行打印」须为 [串口换行打印, 文本]")
        return ("serial_println", [args[0]])
    raise ValueError(
        f"单片机: 未知指令「{op}」——支持：{'/'.join(_INSTR_OPS)}")


def _analog_channels(board):
    return [f"A{i}" for i in range(board["analog"])]


def _digital_pin(pin, board):
    if isinstance(pin, bool) or not isinstance(pin, int):
        raise ValueError("单片机: 引脚须为整数")
    if not 0 <= pin < board["digital"]:
        raise ValueError(
            f"单片机: 数字引脚 {pin} 超出 {board['mcu']} 范围 0–{board['digital'] - 1}")


def _instr_list(raw, board, where):
    if not isinstance(raw, list):
        raise ValueError(f"单片机: 「{where}」须为指令列表")
    out = []
    for item in raw:
        if not isinstance(item, list) or not item or not isinstance(item[0], str):
            raise ValueError(
                f"单片机: 「{where}」指令须为 [操作, ...参数] 列表形态")
        out.append(_instr(item[0], item[1:], board, where))
    return out


# ============================================================
# 图纸：SVG 电路示意图真生成
# ============================================================

_COMPONENTS = {
    "LED": ("发光二极管", ["阳极", "阴极"]),
    "按键": ("轻触开关", ["一脚", "二脚"]),
    "电位器": ("电位器", ["输入", "输出"]),
    "蜂鸣器": ("无源蜂鸣器", ["正极", "负极"]),
    "传感器": ("模拟传感器", ["信号", "电源", "地"]),
    "电机": ("直流电机", ["正极", "负极"]),
    "OLED": ("OLED 显示屏（I2C）", ["SDA", "SCL", "VCC", "GND"]),
}


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def schematic(spec) -> dict:
    """单片机_图纸(规格)：SVG 电路示意图（真文本生成，xml 可解析）。"""
    if not isinstance(spec, dict):
        raise ValueError("单片机: 规格须为字典（键：板/元件/标题）")
    board_name, board = _board(spec.get("板"))
    title = str(spec.get("标题", f"{board_name} 电路图"))
    parts_raw = spec.get("元件", [])
    if not isinstance(parts_raw, list) or not parts_raw:
        raise ValueError("单片机: 「元件」须为非空元件列表（[名称, 引脚, ...]）")
    comps = []
    for item in parts_raw:
        if not isinstance(item, (list, tuple)) or not item:
            raise ValueError("单片机: 元件须为 [名称, 引脚, ...] 列表")
        name = str(item[0])
        if name not in _COMPONENTS:
            raise ValueError(
                f"单片机: 未知元件「{name}」——支持：{'/'.join(_COMPONENTS)}")
        pin = item[1] if len(item) > 1 else None
        if isinstance(pin, int) and not isinstance(pin, bool):
            _digital_pin(pin, board)
        elif isinstance(pin, str) and pin not in _analog_channels(board):
            raise ValueError(
                f"单片机: 元件「{name}」引脚 {pin} 不是本板型有效引脚")
        comps.append((name, pin))

    w, h = 640, 80 + 70 * len(comps)
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}">',
        f'  <rect width="{w}" height="{h}" fill="#ffffff"/>',
        f'  <text x="20" y="30" font-family="monospace" font-size="16" '
        f'fill="#111">{_esc(title)}</text>',
        # 板体 + MCU 标注
        f'  <rect x="40" y="60" width="220" height="{60 + 70 * len(comps)}" '
        f'fill="#e8f4e8" stroke="#1a6b1a" stroke-width="2"/>',
        f'  <text x="60" y="90" font-family="monospace" font-size="13" '
        f'fill="#1a6b1a">{_esc(board_name)} ({board["mcu"]})</text>',
    ]
    y0 = 130
    for i, (name, pin) in enumerate(comps):
        y = y0 + 70 * i
        label, _ = _COMPONENTS[name]
        pin_txt = "" if pin is None else f" D{pin}" if isinstance(pin, int) else f" {pin}"
        # 板上引脚点 + 连线 + 元件框
        svg.append(f'  <circle cx="260" cy="{y}" r="4" fill="#1a6b1a"/>')
        svg.append(f'  <line x1="260" y1="{y}" x2="360" y2="{y}" '
                   f'stroke="#3355aa" stroke-width="2"/>')
        svg.append(f'  <rect x="360" y="{y - 22}" width="180" height="44" '
                   f'fill="#fdf3d0" stroke="#8a6d1a" stroke-width="2"/>')
        svg.append(f'  <text x="370" y="{y + 5}" font-family="monospace" '
                   f'font-size="13" fill="#5a4712">{_esc(name)}（{label}）'
                   f'{_esc(pin_txt)}</text>')
    svg.append("</svg>")
    return {"svg": "\n".join(svg), "宽": w, "高": h,
            "板": board_name, "元件数": len(comps)}


# ============================================================
# 编程：Matha 指令规格 → Arduino C 真代码生成
# ============================================================

_C_EMIT = {
    "pinMode": "pinMode({0}, {1});",
    "digitalWrite": "digitalWrite({0}, {1});",
    "digitalRead": "{ret} = digitalRead({0});",
    "analogWrite": "analogWrite({0}, {1});",
    "analogRead": "{ret} = analogRead({0});",
    "delay": "delay({0});",
    "serial_begin": "Serial.begin({0});",
    "serial_print": 'Serial.print("{0}");',
    "serial_println": 'Serial.println("{0}");',
}


def _emit_c(instrs, in_setup):
    """归一指令列表 → C 语句。读指令（数字读/模拟读）在循环体里累积到
    串口打印（真实可观测形态），setup 里禁读。"""
    lines = []
    for op, args in instrs:
        if op in ("digitalRead", "analogRead"):
            if in_setup:
                raise ValueError("单片机: 「数字读/模拟读」只能出现在「循环」")
            fn = "digitalRead" if op == "digitalRead" else "analogRead"
            lines.append(f'  Serial.print("{fn}({args[0]})=");')
            lines.append(f'  Serial.println({fn}({args[0]}));')
            continue
        if op == "serial_begin" and not in_setup:
            raise ValueError("单片机: 「串口开始」只能出现在「设置」")
        tpl = _C_EMIT[op]
        if op in ("serial_print", "serial_println"):
            # C 字符串字面量转义：反斜杠与双引号，防生成破损 C 源码
            lines.append("  " + tpl.format(
                args[0].replace("\\", "\\\\").replace('"', '\\"')))
            continue
        if "{ret}" in tpl:
            lines.append("  " + tpl.format(ret="int v", *args))
        else:
            lines.append("  " + tpl.format(*args))
    return lines


def program(spec) -> dict:
    """单片机_编程(规格)：指令规格 → Arduino C 源码（真代码生成）。"""
    if not isinstance(spec, dict):
        raise ValueError("单片机: 规格须为字典（键：板/设置/循环）")
    board_name, board = _board(spec.get("板"))
    setup = _instr_list(spec.get("设置", []), board, "设置")
    loop = _instr_list(spec.get("循环", []), board, "循环")
    if not loop and not setup:
        raise ValueError("单片机: 规格缺少程序体（「设置」/「循环」至少其一）")
    setup_lines = _emit_c(setup, in_setup=True)
    loop_lines = _emit_c(loop, in_setup=False)
    uses_serial = any(op.startswith("serial")
                      for op, _ in setup + loop) or \
        any("digitalRead" == op or "analogRead" == op for op, _ in loop)
    src = [
        f"// 由 Matha 单片机_编程 生成 —— 板型 {board_name} ({board['mcu']})",
        "#include <Arduino.h>",
        "",
        "void setup() {",
        *setup_lines,
        "}",
        "",
        "void loop() {",
        *loop_lines,
        "}",
    ]
    if uses_serial:
        # 串口头并入 setup：读指令需要串口输出观测，无条件补 Serial.begin
        src = [
            f"// 由 Matha 单片机_编程 生成 —— 板型 {board_name} ({board['mcu']})",
            "#include <Arduino.h>",
            "",
            "void setup() {",
            "  Serial.begin(9600);",
            *setup_lines,
            "}",
            "",
            "void loop() {",
            *loop_lines,
            "}",
        ]
    code = "\n".join(src)
    return {"代码": code, "板": board_name, "mcu": board["mcu"],
            "字节数": len(code.encode("utf-8"))}


# ============================================================
# 控制：指令序列归一化（上位机协议载荷）
# ============================================================

def control(spec) -> dict:
    """单片机_控制(规格)：控制指令序列归一化校验。

    返回协议化载荷（matha-mcu-ctl/1）；**串口实时收发显式拒绝**——纯
    标准库无串口传输面，规格含「连接」键即报错（不假装已连板）。
    """
    if not isinstance(spec, dict):
        raise ValueError("单片机: 规格须为字典（键：板/指令）")
    if "连接" in spec:
        raise ValueError(
            "单片机: 串口实时控制在纯标准库边界外（无串口传输面）——"
            "控制面只做指令序列归一化，实时收发需外部上位机工具")
    board_name, board = _board(spec.get("板"))
    instrs = _instr_list(spec.get("指令", []), board, "指令")
    if not instrs:
        raise ValueError("单片机: 「指令」须为非空指令列表")
    payload = []
    for op, args in instrs:
        payload.append([op] + [str(a) if isinstance(a, str) else a for a in args])
    return {"指令": payload, "条数": len(payload), "板": board_name,
            "协议": "matha-mcu-ctl/1"}


# ============================================================
# 烧录：工具链真检测 + 真 subprocess
# ============================================================

_FLASH_TIMEOUT = 120


def _flash_argv(family, board, hex_path, port):
    """按板族构造真实烧录命令行（与官方工具文档一致的参数形态）。"""
    if family == "avr":
        return ["avrdude", "-c", "arduino", "-p", board["mcu"],
                "-P", port, "-b", "115200",
                "-U", f"flash:w:{hex_path}:i"]
    if family == "stm32":
        return ["st-flash", "--port", port or "/dev/null", "write",
                hex_path, "0x08000000"]
    if family == "esp32":
        return ["esptool", "--chip", "esp32", "--port", port,
                "write_flash", "0x1000", hex_path]
    if family == "rp2040":
        return ["openocd", "-f", "interface/cmsis-dap.cfg",
                "-f", "target/rp2040.cfg",
                "-c", f"program {hex_path} verify reset exit"]
    raise ValueError(f"单片机: 未知板族 {family}")


def flash(spec, *, which=shutil.which, run=subprocess.run) -> dict:
    """单片机_烧录(规格)：工具链真检测 → 真 subprocess 烧录。

    which/run 可注入（测试面）；生产路径为真 shutil.which + 真
    subprocess.run（capture_output/text/timeout=120）。工具缺失、hex
    不存在、退出码非零 → 显式报错，绝不伪装成功。
    """
    if not isinstance(spec, dict):
        raise ValueError("单片机: 规格须为字典（键：板/十六进制/端口）")
    board_name, board = _board(spec.get("板"))
    hex_path = spec.get("十六进制")
    if not isinstance(hex_path, str) or not hex_path:
        raise ValueError("单片机: 「十六进制」须为 .hex 文件路径")
    hp = Path(hex_path)
    if not hp.is_file():
        raise ValueError(f"单片机: 十六进制文件不存在: {hex_path}")
    port = spec.get("端口")
    if port is not None and not isinstance(port, str):
        raise ValueError("单片机: 「端口」须为串口名（如 COM3 / /dev/ttyUSB0）")
    tool = board["tool"]
    tool_path = which(tool)
    if tool_path is None:
        raise ValueError(
            f"单片机: 未检测到工具链 {tool}（{board_name} 烧录需要）——"
            f"请安装并加入 PATH（Arduino IDE / st-flash / esptool / openocd）")
    argv = [tool_path] + _flash_argv(board["family"], board, str(hp), port)[1:]
    try:
        proc = run(argv, capture_output=True, text=True,
                   timeout=_FLASH_TIMEOUT)
    except subprocess.TimeoutExpired as e:
        raise ValueError(f"单片机: 烧录超时（{_FLASH_TIMEOUT}s）：{tool} "
                         f"{e}") from e
    if proc.returncode != 0:
        tail = ((proc.stderr or "") + (proc.stdout or "")).strip()[-400:]
        raise ValueError(
            f"单片机: 烧录失败（{tool} 退出码 {proc.returncode}）——工具输出：{tail}")
    out = ((proc.stdout or "") + (proc.stderr or "")).strip()[-400:]
    return {"成功": True, "工具": tool, "板": board_name,
            "十六进制": str(hp), "输出": out}


# ============================================================
# 驱动：GPIO/UART/I2C/SPI/PWM 模板真生成
# ============================================================

_PERIPHERALS = ("gpio", "uart", "i2c", "spi", "pwm")


def driver(spec) -> dict:
    """单片机_驱动(规格)：五类外设 Arduino C 驱动模板真生成。"""
    if not isinstance(spec, dict):
        raise ValueError("单片机: 规格须为字典（键：外设/板/引脚/…）")
    periph = spec.get("外设")
    if not isinstance(periph, str) or periph.lower() not in _PERIPHERALS:
        raise ValueError(
            f"单片机: 「外设」须为 {'/'.join(_PERIPHERALS)}")
    periph = periph.lower()
    board_name, board = _board(spec.get("板"))
    pin = spec.get("引脚", 13)
    baud = spec.get("波特率", 9600)
    if isinstance(baud, bool) or not isinstance(baud, int) or baud < 1:
        raise ValueError("单片机: 「波特率」须为正整数")
    if periph == "gpio":
        _digital_pin(pin, board)
        code = f"""// GPIO 驱动模板 —— {board_name} ({board['mcu']}) 引脚 D{pin}
// AVR 寄存器面：DDRx（按引脚组别映射 PORTx/DDRx/PINx）由 Arduino
// pinMode 抽象；直接寄存器操作需按板型查 datasheet（诚实边界：模板走
// Arduino 抽象层）。
#include <Arduino.h>

const int PIN = {pin};

void setup() {{
  pinMode(PIN, OUTPUT);
}}

void loop() {{
  digitalWrite(PIN, HIGH);
  delay(500);
  digitalWrite(PIN, LOW);
  delay(500);
}}"""
    elif periph == "uart":
        code = f"""// UART 驱动模板 —— {board_name} ({board['mcu']}) 波特率 {baud}
#include <Arduino.h>

void setup() {{
  Serial.begin({baud});
}}

void loop() {{
  if (Serial.available() > 0) {{
    int b = Serial.read();
    Serial.write(b);            // 回显
  }}
}}"""
    elif periph == "i2c":
        code = f"""// I2C 驱动模板 —— {board_name} ({board['mcu']}) 总线扫描
#include <Arduino.h>
#include <Wire.h>

void setup() {{
  Wire.begin();
  Serial.begin({baud});
}}

void loop() {{
  for (int addr = 0x08; addr <= 0x77; addr++) {{
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) {{
      Serial.print("I2C 设备: 0x");
      Serial.println(addr, HEX);
    }}
  }}
  delay(1000);
}}"""
    elif periph == "spi":
        code = f"""// SPI 驱动模板 —— {board_name} ({board['mcu']}) 回环收发
#include <Arduino.h>
#include <SPI.h>

const int CS = {pin if isinstance(pin, int) and not isinstance(pin, bool) else 10};

void setup() {{
  pinMode(CS, OUTPUT);
  digitalWrite(CS, HIGH);
  SPI.begin();
  Serial.begin({baud});
}}

void loop() {{
  digitalWrite(CS, LOW);
  uint8_t r = SPI.transfer(0xA5);   // 收发一字节
  digitalWrite(CS, HIGH);
  Serial.print("SPI 回读: 0x");
  Serial.println(r, HEX);
  delay(1000);
}}"""
    else:  # pwm
        if pin not in board["pwm"]:
            raise ValueError(
                f"单片机: 引脚 {pin} 不是 {board_name} 的 PWM 引脚"
                f"（PWM：{board['pwm']}）")
        code = f"""// PWM 驱动模板 —— {board_name} ({board['mcu']}) 引脚 D{pin} 呼吸灯
#include <Arduino.h>

const int PIN = {pin};

void setup() {{
  pinMode(PIN, OUTPUT);
}}

void loop() {{
  for (int duty = 0; duty <= 255; duty += 5) {{
    analogWrite(PIN, duty);
    delay(20);
  }}
  for (int duty = 255; duty >= 0; duty -= 5) {{
    analogWrite(PIN, duty);
    delay(20);
  }}
}}"""
    return {"代码": code, "外设": periph, "板": board_name,
            "字节数": len(code.encode("utf-8"))}


# ============================================================
# 写入：UTF-8 文本真落盘
# ============================================================

def write(path, content) -> dict:
    """单片机_写入(路径)(内容)：驱动/代码文本真落盘。"""
    if not isinstance(path, str) or not path:
        raise ValueError("单片机: 「路径」须为非空字符串")
    if not isinstance(content, str):
        raise ValueError("单片机: 「内容」须为文本（生成的 C 源码为字符串）")
    p = Path(path)
    if not p.parent.is_dir():
        raise ValueError(f"单片机: 目标目录不存在: {p.parent}")
    p.write_text(content, encoding="utf-8")
    return {"成功": True, "路径": str(p.resolve()),
            "字节数": len(content.encode("utf-8"))}


# ============================================================
# 注册面
# ============================================================

def dispatch(op: str, spec):
    """宿主内建统一入口（阶段 24f）。"""
    if op == "图纸":
        return schematic(spec)
    if op == "编程":
        return program(spec)
    if op == "控制":
        return control(spec)
    if op == "烧录":
        return flash(spec)
    if op == "驱动":
        return driver(spec)
    if op == "写入":
        if not isinstance(spec, dict):
            raise ValueError("单片机: 写入规格须为字典（键：路径/内容）")
        return write(spec.get("路径"), spec.get("内容"))
    raise ValueError(f"单片机: 未知操作 {op!r}")


def _curry2(func):
    def with_first(a):
        return lambda b: func(a, b)
    return with_first


def toolchain_families() -> dict:
    """按烧录工具归并板族（只读静态矩阵；设备管理器/硬件盘点共用）。"""
    out: dict[str, list[str]] = {}
    for name, spec in _BOARDS.items():
        out.setdefault(spec["tool"], []).append(name)
    return {tool: sorted(boards) for tool, boards in sorted(out.items())}


def _write_entry(path, content):
    return write(path, content)


def _register_mcu(builtins: dict) -> None:
    """领域插件登记钩子（scripts/gen_domain_manifest.py 发现）。"""
    builtins["单片机_图纸"] = schematic
    builtins["单片机_编程"] = program
    builtins["单片机_控制"] = control
    builtins["单片机_烧录"] = flash
    builtins["单片机_驱动"] = driver
    builtins["单片机_写入"] = _curry2(_write_entry)


def _mcu_symtab_names() -> list[str]:
    return ["单片机_图纸", "单片机_编程", "单片机_控制",
            "单片机_烧录", "单片机_驱动", "单片机_写入"]


__all__ = [
    "schematic", "program", "control", "flash", "driver", "write",
    "dispatch", "_register_mcu", "_mcu_symtab_names",
]
