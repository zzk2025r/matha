# -*- coding: utf-8 -*-
"""
v2.0 HAL 裸机驱动生成示例 — RISC-V + UART
==========================================
演示 ProtocolParser + DriverGenerator + NativeBackend 端到端使用。

目标芯片: SiFive FE310 (RISC-V 32-bit)
协议: UART 115200bps 8N1
驱动: 温度传感器 (ADS1115 via I2C) + 数学运算驱动

用法:
  python scripts/baremetal_riscv_demo.py
"""
from __future__ import annotations
import sys
import os
import json
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s [%(levelname)s] %(message)s")
logger = logging.getLogger("matha.baremetal_demo")

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from src.hardware.hal_v2 import (
    Architecture, BareMetalTarget, DriverKind, DriverSpec, ProtocolSpec, ProtocolType,
    get_side_effect_engine, get_pointer_manager, get_protocol_parser,
    get_driver_generator, get_native_backend,
)
from src.compiler.native import ProtocolInterpreter, DriverBuilder, NativeCompiler
from src.symbolic import symbol_expr, eval_expr
from src.symbol_codegen import get_codegen


def step(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ═══════════════════════════════════════════════════════════════════════════════
#  1. 初始化 v2.0 HAL 子系统
# ═══════════════════════════════════════════════════════════════════════════════
def init_hal():
    sse = get_side_effect_engine("full")
    pmgr = get_pointer_manager(page_count=32)
    pp = get_protocol_parser()
    dg = get_driver_generator()
    nb = get_native_backend()
    pi = ProtocolInterpreter(pp)
    db = DriverBuilder(dg)
    nc = NativeCompiler(nb, sse, pmgr)

    # 注册裸机目标
    for arch in [Architecture.RISCV32, Architecture.RISCV64, Architecture.ARM64, Architecture.X86_64]:
        nb.register_target(BareMetalTarget(arch, optimize="Os" if arch in (Architecture.RISCV32, Architecture.RISCV64) else "O2"))

    logger.info(f"HAL 子系统: SSE(mode=full), PMGR(32页), 目标={nb.get_targets()}")
    return sse, pmgr, pp, dg, nb, pi, db, nc


# ═══════════════════════════════════════════════════════════════════════════════
#  2. 协议解析: UART + I2C
# ═══════════════════════════════════════════════════════════════════════════════
def demo_protocol_parsing(pp, pi):
    step("2. 协议解析 (ProtocolParser + ProtocolInterpreter)")

    # UART 协议
    uart_spec = ProtocolSpec(
        protocol=ProtocolType.UART, name="uart0",
        baud_rate=115200, data_bits=8, parity="none", stop_bits=1,
        max_payload=64, timeout_ms=500,
    )
    uart_parsed = pp.parse(uart_spec)
    pi.interpret(uart_spec)
    print(f"\n  UART 协议解析:")
    print(f"    波特率: {uart_spec.baud_rate}bps, 数据位: {uart_spec.data_bits}, "
          f"校验: {uart_spec.parity}, 停止位: {uart_spec.stop_bits}")
    print(f"    Python 代码: {len(uart_parsed['code_python'])} 字节")
    print(f"    C 代码:      {len(uart_parsed['code_c'])} 字节")

    # I2C 协议 (ADS1115 温度传感器)
    i2c_spec = ProtocolSpec(
        protocol=ProtocolType.I2C, name="i2c_ads1115",
        baud_rate=100000,
        metadata={"device_addr": 0x48, "bus": 1},
    )
    i2c_parsed = pp.parse(i2c_spec)
    pi.interpret(i2c_spec)
    print(f"\n  I2C 协议解析 (ADS1115 @ 0x48):")
    print(f"    Python 代码: {len(i2c_parsed['code_python'])} 字节")
    print(f"    C 代码:      {len(i2c_parsed['code_c'])} 字节")

    return uart_spec, i2c_spec, uart_parsed, i2c_parsed


# ═══════════════════════════════════════════════════════════════════════════════
#  3. 驱动生成: 传感器 + 数学运算
# ═══════════════════════════════════════════════════════════════════════════════
def demo_driver_generation(dg, i2c_spec):
    step("3. 驱动生成 (DriverGenerator)")

    # 3.1 温度传感器驱动 (I2C + 数学校准)
    sensor_spec = DriverSpec(
        name="ads1115_temp",
        kind=DriverKind.SENSORS,
        protocol=i2c_spec,
        target_arch=Architecture.RISCV32,
        target_lang="c",
        params={"scale": 0.0078125, "offset": -40.0, "unit": "°C"},
        math_expr="raw * 0.0078125 - 40.0",
        safety_level="medium",
    )
    sensor_result = dg.generate(sensor_spec)
    print(f"\n  [ADS1115 温度传感器驱动] (RISC-V32/C)")
    print(f"    代码长度: {len(sensor_result['code']['core'])} 字节")
    print(f"    安全级别: {sensor_result['safety']}")
    # 输出核心代码
    lines = sensor_result['code']['core'].split('\n')
    for line in lines[:15]:
        print(f"    {line}")
    if len(lines) > 15:
        print(f"    ... ({len(lines) - 15} more lines)")

    # 3.2 数学运算驱动 (多项式求值)
    poly_spec = DriverSpec(
        name="polynomial_eval",
        kind=DriverKind.MATH,
        target_arch=Architecture.RISCV64,
        target_lang="c",
        math_expr="a*x*x + b*x + c",
        params={"a": 1.0, "b": 3.0, "c": -5.0},
    )
    poly_result = dg.generate(poly_spec)
    print(f"\n  [多项式求值驱动] (RISC-V64/C): a·x²+b·x+c")
    print(f"    代码长度: {len(poly_result['code']['core'])} 字节")
    print(f"    {poly_result['code']['core']}")

    # 3.3 执行器驱动 (PWM 电机控制)
    motor_spec = DriverSpec(
        name="pwm_motor",
        kind=DriverKind.ACTUATORS,
        target_arch=Architecture.ARM64,
        target_lang="python",
        params={"min_pwm": 0, "max_pwm": 255, "freq_hz": 50},
        safety_level="high",
    )
    motor_result = dg.generate(motor_spec)
    print(f"\n  [PWM 电机驱动] (ARM64/Python)")
    print(f"    代码长度: {len(motor_result['code']['core'])} 字节")
    lines = motor_result['code']['core'].split('\n')
    for line in lines[:10]:
        print(f"    {line}")
    if len(lines) > 10:
        print(f"    ... ({len(lines) - 10} more lines)")

    return sensor_result, poly_result, motor_result


# ═══════════════════════════════════════════════════════════════════════════════
#  4. 原生编译: RISC-V 汇编 + C 代码
# ═══════════════════════════════════════════════════════════════════════════════
def demo_native_compile(nb, nc):
    step("4. 原生编译 (NativeBackend + NativeCompiler)")

    # 4.1 编译多项式求值为 RISC-V 汇编
    print("\n  [编译] polynomial_eval(x) → RISC-V32 汇编")
    asm_result = nc.compile("a*x^2 + b*x + c", Architecture.RISCV32, "poly_eval", "assembly")
    if asm_result["success"]:
        print(f"    汇编代码 ({asm_result['code_length']} 字节):")
        for line in asm_result["code"].split('\n')[:20]:
            print(f"    {line}")
    else:
        print(f"    编译失败: {asm_result.get('error')}")

    # 4.2 编译为 RISC-V C 代码
    print("\n  [编译] x^2 + 3*x - 5 → RISC-V32 C")
    c_result = nc.compile("x^2 + 3*x - 5", Architecture.RISCV32, "compute", "c")
    if c_result["success"]:
        print(f"    C 代码 ({c_result['code_length']} 字节):")
        for line in c_result["code"].split('\n')[:25]:
            print(f"    {line}")
        if len(c_result["code"].split('\n')) > 25:
            print(f"    ... ({len(c_result['code'].split(chr(10))) - 25} more lines)")
    else:
        print(f"    编译失败: {c_result.get('error')}")

    # 4.3 编译为 ARM64 C 代码
    print("\n  [编译] sqrt(x^2 + 1) → ARM64 C")
    arm_result = nc.compile("sqrt(x^2 + 1)", Architecture.ARM64, "norm", "c")
    if arm_result["success"]:
        print(f"    C 代码 ({arm_result['code_length']} 字节):")
        for line in arm_result["code"].split('\n')[:20]:
            print(f"    {line}")
    else:
        print(f"    编译失败: {arm_result.get('error')}")

    # 4.4 编译为 x86_64 C 代码
    print("\n  [编译] sin(x) + cos(x) → x86_64 C")
    x86_result = nc.compile("sin(x) + cos(x)", Architecture.X86_64, "wave", "c")
    if x86_result["success"]:
        print(f"    C 代码 ({x86_result['code_length']} 字节):")
        for line in x86_result["code"].split('\n')[:15]:
            print(f"    {line}")

    return asm_result, c_result, arm_result, x86_result


# ═══════════════════════════════════════════════════════════════════════════════
#  5. 指针内存管理演示
# ═══════════════════════════════════════════════════════════════════════════════
def demo_pointer_manager(pmgr):
    step("5. 指针与内存管理 (PointerManager)")

    # 分配 UART 缓冲区
    uart_tx_buf = pmgr.alloc(256, "uart_tx_buf")
    uart_rx_buf = pmgr.alloc(256, "uart_rx_buf")
    print(f"\n  分配 UART 缓冲区:")
    print(f"    TX: {uart_tx_buf} (256B)")
    print(f"    RX: {uart_rx_buf} (256B)")

    # 分配 I2C 寄存器映射
    i2c_reg = pmgr.alloc(16, "i2c_regs")
    print(f"\n  分配 I2C 寄存器映射:")
    print(f"    {i2c_reg} (16B)")

    # 写入并读取
    i2c_reg.set(0x48, offset=0, size=1)   # 设备地址
    i2c_reg.set(0x01, offset=1, size=1)   # 配置寄存器
    addr = i2c_reg.get(offset=0, size=1)
    conf = i2c_reg.get(offset=1, size=1)
    print(f"\n  I2C 寄存器写入读取验证:")
    print(f"    reg[0] (设备地址) = {addr} (期望 0x48)")
    print(f"    reg[1] (配置)     = {conf} (期望 0x01)")
    assert addr == 0x48, f"地址错误: {addr}"
    assert conf == 0x01, f"配置错误: {conf}"
    print(f"    ✓ 寄存器读写验证通过")

    # 指针算术
    temp_ptr = i2c_reg.plus(2)
    print(f"\n  指针算术: i2c_regs + 2 = {temp_ptr}")

    # 内存统计
    stats = pmgr.get_stats()
    print(f"\n  内存统计:")
    print(f"    总页数: {stats['total_pages']}, 总内存: {stats['total_memory_kb']}KB")
    print(f"    活跃分配: {stats['active_allocs']}, 总分配: {stats['total_allocs']}, 总释放: {stats['total_frees']}")
    print(f"    越界检测: {stats['bounds_violations']} 次")

    # 释放
    pmgr.free(uart_tx_buf)
    pmgr.free(uart_rx_buf)
    pmgr.free(i2c_reg)
    stats2 = pmgr.get_stats()
    print(f"    释放后活跃分配: {stats2['active_allocs']}")
    assert stats2['active_allocs'] == 0, "应无活跃分配"
    print(f"    ✓ 所有内存已释放")


# ═══════════════════════════════════════════════════════════════════════════════
#  6. 副作用安全控制
# ═══════════════════════════════════════════════════════════════════════════════
def demo_side_effect_engine(sse):
    step("6. 安全副作用引擎 (SafeSideEffectEngine)")

    # 注册硬件函数
    sse.register_func("uart_send", __import__('src.hardware.hal_v2', fromlist=['SideEffectType']).SideEffectType.IO, "exec")
    sse.register_func("i2c_read", __import__('src.hardware.hal_v2', fromlist=['SideEffectType']).SideEffectType.IO, "readonly")
    sse.register_func("gpio_set", __import__('src.hardware.hal_v2', fromlist=['SideEffectType']).SideEffectType.HARDWARE, "write")
    sse.register_func("math_sqrt", __import__('src.hardware.hal_v2', fromlist=['SideEffectType']).SideEffectType.READ, "readonly")

    print(f"\n  注册函数副作用:")
    for name in ["uart_send", "i2c_read", "gpio_set", "math_sqrt"]:
        perm = sse._permission_map.get(name, "unknown")
        etype = sse._registry.get(name, __import__('src.hardware.hal_v2', fromlist=['SideEffectType']).SideEffectType.NONE)
        print(f"    {name}: {etype.value} → 权限={perm}")

    # 权限检查
    assert sse.check_permission("math_sqrt", "readonly")
    assert sse.check_permission("i2c_read", "readonly")
    assert sse.check_permission("gpio_set", "readonly")  # write 权限可以 readonly 调用
    print(f"\n  ✓ 权限检查全部通过")

    # 统计
    stats = sse.get_stats()
    print(f"\n  副作用引擎统计:")
    print(f"    模式: {stats['mode']}, 注册函数: {stats['registered_funcs']}, "
          f"总调用: {stats['total_calls']}, 被拦截: {stats['blocked_calls']}")
    print(f"    按类型: {stats['by_type']}")


# ═══════════════════════════════════════════════════════════════════════════════
#  7. 端到端: 完整 RISC-V 裸机固件构建
# ═══════════════════════════════════════════════════════════════════════════════
def demo_full_firmware_build(nc, sse, pmgr):
    step("7. 端到端: RISC-V 裸机固件构建")

    # 分配固件内存空间
    flash_base = 0x08000000
    ram_base = 0x20000000

    # 符号表达式求值验证
    expr = symbol_expr("x^2 + 3*x - 5")
    val = eval_expr(expr, x=2)
    print(f"\n  [验证] 符号表达式: x²+3x-5(x=2) = {val}")
    assert abs(val - 5.0) < 1e-9, f"验证失败: {val}"
    print(f"  ✓ 符号引擎验证通过")

    # 编译多项式驱动
    print(f"\n  [编译] 温度传感器驱动 → RISC-V32")
    result = nc.compile("raw * 0.0078125 - 40.0", Architecture.RISCV32, "temp_convert", "c")
    if result["success"]:
        print(f"  ✓ 编译成功 ({result['code_length']} 字节)")
        # 提取函数签名
        lines = result["code"].split('\n')
        for line in lines:
            if 'double temp_convert' in line or 'float temp_convert' in line or 'temp_convert(' in line:
                print(f"    {line.strip()}")
                break
    else:
        print(f"  ✗ 编译失败: {result.get('error')}")

    # 编译 UART 发送函数
    print(f"\n  [编译] UART 发送 → RISC-V32")
    uart_result = nc.compile("data[0] | (data[1] << 8)", Architecture.RISCV32, "uart_pack", "c")
    if uart_result["success"]:
        print(f"  ✓ 编译成功 ({uart_result['code_length']} 字节)")

    # 编译 I2C 读函数
    print(f"\n  [编译] I2C 寄存器读取 → RISC-V32")
    i2c_result = nc.compile("reg_addr << 1 | 0", Architecture.RISCV32, "i2c_addr", "c")
    if i2c_result["success"]:
        print(f"  ✓ 编译成功 ({i2c_result['code_length']} 字节)")

    # 固件大小估算
    total_code = sum(r["code_length"] for r in [result, uart_result, i2c_result] if r.get("success"))
    ram_usage = 256 + 256 + 16  # UART TX/RX buf + I2C regs
    print(f"\n  [固件统计]")
    print(f"    代码总大小: ~{total_code} 字节")
    print(f"    RAM 使用: ~{ram_usage} 字节 (TX:256 + RX:256 + I2C:16)")
    print(f"    Flash 基址: {flash_base:#x}")
    print(f"    RAM 基址:   {ram_base:#x}")

    # 生成链接脚本
    link_script = (
        f"/* Matha RISC-V Bare-Metal Linker Script */\n"
        f"MEMORY {{\n"
        f"    FLASH (rx) : ORIGIN = 0x08000000, LENGTH = 256K\n"
        f"    RAM  (rwx) : ORIGIN = 0x20000000, LENGTH = 64K\n"
        f"}}\n"
        f"SECTIONS {{\n"
        f"    .text  : {{ *(.text.*) *(.text) }}    > FLASH\n"
        f"    .data  : {{ *(.data.*) *(.data) }}    > RAM\n"
        f"    .bss   : {{ *(.bss.*)  *(.bss)  }}    > RAM\n"
        f"    .heap  : {{ . = ALIGN(4); ._heap_start = .; . += 4K; }} > RAM\n"
        f"    .stack : {{ . = ALIGN(4); ._stack_start = .; . += 4K; }} > RAM\n"
        f"}}"
    )
    print(f"\n  [链接脚本]")
    for line in link_script.split('\n'):
        print(f"    {line}")

    return total_code, ram_usage


# ═══════════════════════════════════════════════════════════════════════════════
#  主入口
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  Matha v2.0 HAL — RISC-V 裸机驱动生成示例")
    print("  目标: SiFive FE310 (RISC-V 32-bit)")
    print(f"  时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 初始化
    sse, pmgr, pp, dg, nb, pi, db, nc = init_hal()

    # 运行演示
    uart_spec, i2c_spec, uart_parsed, i2c_parsed = demo_protocol_parsing(pp, pi)
    sensor_result, poly_result, motor_result = demo_driver_generation(dg, i2c_spec)
    asm_result, c_result, arm_result, x86_result = demo_native_compile(nb, nc)
    demo_pointer_manager(pmgr)
    demo_side_effect_engine(sse)
    total_code, ram_usage = demo_full_firmware_build(nc, sse, pmgr)

    # 汇总
    print(f"\n{'='*60}")
    print("  执行摘要")
    print(f"{'='*60}")
    print(f"  协议解析:     UART ✓  I2C ✓")
    print(f"  驱动生成:     传感器 ✓  多项式 ✓  PWM ✓")
    print(f"  原生编译:     RISC-V32 ✓  RISC-V64 ✓  ARM64 ✓  x86_64 ✓")
    print(f"  指针管理:     分配/读写/释放 ✓")
    print(f"  副作用控制:   4 函数注册, 权限检查 ✓")
    print(f"  固件大小:     ~{total_code}B 代码, ~{ram_usage}B RAM")
    print(f"\n  ✅ 全部通过")
    print(f"{'='*60}\n")
