# -*- coding: utf-8 -*-
"""Hardware domain 功能验证测试。"""
import sys
sys.path.insert(0, r"D:\trae")

from src.interp import interpret

tests = [
    # 系统信息（0 参函数：Matha 传入 0，lambda 忽略）
    ("cpu核数", "#1：[cpu核数(0)]"),
    ("平台", "#1：[平台(0)]"),
    ("架构", "#1：[架构(0)]"),
    # GPIO（Matha 单次应用，传 tuple [pin, mode/value]）
    ("GPIO初始化+写入",
     "GPIO初始化([1, \"out\"])\nGPIO写入([1, 1])\n#1：[\"GPIO ok\"]"),
    # ADC（3 参柯里化）
    ("ADC值", "v = ADC值(2.5)(3.3)(12)\n#1：[v]"),
    ("ADC电压", "v = ADC电压(4095)(3.3)(12)\n#1：[v]"),
    ("DAC值", "v = DAC值(2048)(3.3)(12)\n#1：[v]"),
    # PWM（2 参柯里化）
    ("PWM占空比", "d = PWM占空比(5.0)(10.0)\n#1：[d]"),
    ("PWM周期", "p = PWM周期(1000.0)\n#1：[p]"),
    ("PWM高电平", "t = PWM高电平(0.01)(50.0)\n#1：[t]"),
    # 执行命令
    ("执行命令", 'r = 执行命令("echo test")\n#1：[r]'),
    # DNS
    ("DNS解析", 'ips = DNS解析("localhost")\n#1：[len(ips)]'),
    # 文件操作
    ("列出目录", 'files = 列出目录(".")\n#1：[len(files)]'),
    ("文件存在", 'ok = 文件存在("src/interp.py")\n#1：[ok]'),
    ("文件大小", 'sz = 文件大小("src/interp.py")\n#1：[sz > 0]'),
    # 环境变量
    ("环境变量", 'home = 环境变量("HOME")\n#1：[len(home) > 0 or len(home) > 0]'),
    # 嵌入式传感器（2-3 参柯里化）
    ("热敏温度C", "t = 热敏温度C(10000.0)(10000.0)(298.15)(3950.0)\n#1：[t]"),
    ("超声波距离", "d = 超声波距离(29000.0)(343.0)\n#1：[d]"),
    ("加速度角度", "pitch = 加速度角度(0.0)(1.0)(0.0)\n#1：[pitch[0]]"),
    # 电机控制（3 参柯里化）
    ("步进角度", "a = 步进角度(200)(200)(1.0)\n#1：[a]"),
    ("舵机脉冲", "p = 舵机脉冲(90.0)(500.0)(2500.0)\n#1：[p]"),
    ("直流转速", "rpm = 直流转速(12.0)(1000.0)\n#1：[rpm]"),
    # 通信协议
    ("UART误差", "e = UART误差(9600.0)(11059200.0)(16)\n#1：[e]"),
    ("I2C上拉", "r = I2C上拉(3.3)(0.003)\n#1：[r]"),
    # 电源
    ("电池电压", 'v = 电池电压(3)("liion")\n#1：[v]'),
    ("电池容量", "wh = 电池容量(5.0)(12.0)\n#1：[wh]"),
]

passed, failed = 0, 0
for name, src in tests:
    try:
        out, trace = interpret(src)
        result = out[0] if out else None
        print(f"  PASS {name}: {result}")
        passed += 1
    except Exception as e:
        print(f"  FAIL {name}: {type(e).__name__}: {e}")
        failed += 1

print(f"\n{'='*50}")
print(f"结果: {passed} 通过, {failed} 失败 (共 {passed+failed})")
print(f"{'='*50}")
sys.exit(0 if failed == 0 else 1)
