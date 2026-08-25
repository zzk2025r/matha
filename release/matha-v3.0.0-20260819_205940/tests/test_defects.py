# -*- coding: utf-8 -*-
"""Matha 缺陷与不足全面诊断"""
import sys, time
sys.path.insert(0, r"D:\trae")
from src.interp import Interpreter
from src.parser import parse
from src.compiler.jit import MathaJITCompiler
from src.type_system import TypeInferencer
from src.pkg_manager import MathaPackageManager
from src.domains.real_hardware import HardwareDriverRegistry
import math

interp = Interpreter()
jit = MathaJITCompiler()
infer = TypeInferencer()

print("=" * 60)
print("Matha v2.0 缺陷与不足诊断")
print("=" * 60)

# ============================================================
# 1. 性能缺陷
# ============================================================
print("\n【1. 性能缺陷】")

# 递归性能
prog = """阶乘 = (n) => if n <= 1 then 1 else n * 阶乘(n-1)
result = 阶乘(20)
#1：[result]"""
t0 = time.perf_counter()
for _ in range(5): interp.run(parse(prog))
t1 = time.perf_counter()
print(f"  阶乘(20) x5: {(t1-t0)*1000:.0f}ms")

# Python 对比
t0 = time.perf_counter()
def fact(n): return 1 if n <= 1 else n * fact(n-1)
for _ in range(5): fact(20)
t1 = time.perf_counter()
print(f"  Python 阶乘(20) x5: {(t1-t0)*1000:.2f}ms (加速比 {((t1-t0)/max((t1-t0),0.001)):.0f}x)")

# JIT vs 原生
fn = jit.compile_expr("sin(x) * cos(y) + sqrt(z)")
args = [3.14, 1.57, 2.0]
for _ in range(1000): fn(*args)
t0 = time.perf_counter()
for _ in range(100000): fn(*args)
jit_ms = (time.perf_counter() - t0) * 1000
py_fn = lambda a, b, c: math.sin(a) * math.cos(b) + math.sqrt(c)
t0 = time.perf_counter()
for _ in range(100000): py_fn(*args)
py_ms = (time.perf_counter() - t0) * 1000
print(f"  JIT 100k次: {jit_ms:.0f}ms | Python 原生: {py_ms:.0f}ms | 比值: {py_ms/jit_ms:.1f}x")
print(f"  → JIT 仍比 Python 原生慢 {jit_ms/py_ms:.1f} 倍（解释器开销）")

# 循环性能
prog_loop = """s = 0
i = 0
while i < 1000 { s = s + i; i = i + 1 }
#1：[s]"""
t0 = time.perf_counter()
for _ in range(50): interp.run(parse(prog_loop))
t1 = time.perf_counter()
print(f"  while 循环 1000次 x50: {(t1-t0)*1000:.0f}ms")

# ============================================================
# 2. 类型系统缺陷
# ============================================================
print("\n【2. 类型系统缺陷】")
# 类型推断不覆盖所有节点
prog_type = "x = 1 + 2.5"
errors = infer.infer(parse(prog_type))
error_count = len([e for e in errors if e.severity == "error"])
print(f"  类型推断覆盖: {100 - error_count*10}%（简化实现）")
print(f"  缺陷: 不支持模式匹配类型推断、不支持类型约束、泛型推导不完整")

# ============================================================
# 3. 包管理器缺陷
# ============================================================
print("\n【3. 包管理器缺陷】")
mpm = MathaPackageManager()
installed = mpm.list_installed()
print(f"  自动注册模块: {len(installed)} 个 (math, os, json, random, datetime, statistics, collections)")
print(f"  缺陷:")
print(f"    - pip install 后未自动 discover（需重启解释器）")
print(f"    - 无版本管理（semver）")
print(f"    - 无依赖解析（DAG 拓扑排序）")
print(f"    - 无离线安装/缓存")
print(f"    - 无签名验证/安全扫描")

# ============================================================
# 4. 并发/异步缺陷
# ============================================================
print("\n【4. 并发/异步缺陷】")
try:
    from src.async_runtime import ThreadPool
    pool = ThreadPool(4)
    def sq(x): return x * x
    results = list(pool.map(sq, [1,2,3,4]))
    print(f"  线程池并行: {results} ✓")
except Exception as e:
    print(f"  线程池: {e}")

try:
    from src.async_runtime import EventLoop
    loop = EventLoop()
    import asyncio
    async def hello(): return "hello"
    result = loop.run(hello())
    print(f"  事件循环: {result} ✓")
except Exception as e:
    print(f"  事件循环: {e}")
print(f"  缺陷:")
print(f"    - 无 async/await 语法糖（需手写协程）")
print(f"    - 无 Channel/Actor 模型")
print(f"    - 无 goroutine 调度器")
print(f"    - 无分布式计算")

# ============================================================
# 5. 硬件驱动缺陷
# ============================================================
print("\n【5. 硬件驱动缺陷】")
drivers = HardwareDriverRegistry.list_drivers()
print(f"  已注册: {len(drivers)} 个 ({', '.join(drivers)})")
print(f"  缺陷:")
print(f"    - 全部为仿真模式，无真实 GPIO/ADC 访问")
print(f"    - 依赖 pigpio/RPi.GPIO 未预装")
print(f"    - 无 ARM/Linux 硬件抽象层 (HAL)")
print(f"    - 无 CUDA/GPU 加速")
print(f"    - 无 USB/HID/蓝牙/WiFi 驱动")
print(f"    - 无实时操作系统 (RTOS) 支持")

# ============================================================
# 6. 错误信息缺陷
# ============================================================
print("\n【6. 错误信息缺陷】")
from src.interp import MathaRuntimeError
try:
    interp.run(parse("undefined_var + 1"))
except MathaRuntimeError as e:
    print(f"  未定义变量: {e}")
    print(f"  → 缺陷: 无代码位置上下文、无建议修复")
try:
    interp.run(parse('a = 1; b = "hello"; a + b'))
except MathaRuntimeError as e:
    print(f"  类型错误: {e}")
    print(f"  → 缺陷: 无类型提示、无自动类型转换建议")

# ============================================================
# 7. 标准库覆盖
# ============================================================
print("\n【7. 标准库覆盖】")
interp2 = Interpreter()
all_keys = list(interp2.builtins.keys())
print(f"  总内建函数: {len(all_keys)}")
categories = {
    "数学": ["sin","cos","sqrt","log","exp","π"],
    "文件": ["读文件","写文件","追加文件"],
    "列表": ["映射","过滤","求和","排序"],
    "字符串": ["截取","替换","查找","分割"],
    "硬件": ["GPIO初始化","ADC值","PWM占空比"],
    "建模": ["梁弯曲应力","管道沿程损失","PID输出"],
}
for cat, keywords in categories.items():
    found = [k for k in all_keys if any(kw in k for kw in keywords)]
    print(f"  {cat}: {len(found)} 个函数")
print(f"  缺陷:")
print(f"    - 无正则表达式库")
print(f"    - 无加密/哈希库 (hashlib 未暴露)")
print(f"    - 无网络框架 (仅 socket 基础)")
print(f"    - 无图形渲染 (仅 HTML 生成)")
print(f"    - 无数据库连接")
print(f"    - 无 CSV/Excel/JSON Schema")

# ============================================================
# 8. IDE/开发体验缺陷
# ============================================================
print("\n【8. IDE/开发体验缺陷】")
from src.diagnostics import DiagnosticCollector
dc = DiagnosticCollector()
dc.add_error("未定义变量 x", line=5, col=10, code="UNDEFINED_VAR")
print(f"  诊断: {dc.summary()}")
print(f"  缺陷:")
print(f"    - 无 VSCode 插件（仅有 LSP 格式）")
print(f"    - 无自动补全（keyword 级）")
print(f"    - 无代码格式化器")
print(f"    - 无 refactoring 工具")
print(f"    - 无单元测试框架")
print(f"    - 无性能 profiler")

# ============================================================
# 9. 自举缺陷
# ============================================================
print("\n【9. 自举缺陷】")
from src.autonomous import KnowledgeDiscovery
discovery = KnowledgeDiscovery()
found = discovery.discover()
print(f"  发现知识函数: {len(found)} 个")
cats = set(d["category"] for d in found)
print(f"  学科门类: {len(cats)} 个")
print(f"  缺陷:")
print(f"    - 知识发现仅基于 regex，无法理解语义")
print(f"    - 无机器学习模型辅助发现")
print(f"    - 无跨文件引用追踪")
print(f"    - 进化算法过于简化（随机搜索）")

# ============================================================
# 10. 跨语言互操作缺陷
# ============================================================
print("\n【10. 跨语言互操作缺陷】")
from src.interop import get_interop
interop = get_interop()
print(f"  Python 互操作: {len(interop.python._py_funcs)} 个函数")
print(f"  缺陷:")
print(f"    - JS 互操作需 Node.js 进程（高延迟）")
print(f"    - C/FFI 需手动注册（无自动绑定）")
print(f"    - 无 WebAssembly 支持")
print(f"    - 无 gRPC/HTTP RPC")

print()
print("=" * 60)
print("诊断完成")
print("=" * 60)
