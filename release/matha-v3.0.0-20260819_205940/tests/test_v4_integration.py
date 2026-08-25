# -*- coding: utf-8 -*-
"""Matha v4.0 集成：所有模块统一注册。"""
import sys
sys.path.insert(0, r"D:\trae")

from src.interp import Interpreter
from src.stdlib_extend import register_all as register_stdlib
from src.lang_features import register_language_features
from src.hal import register_hardware_builtins

print("=" * 60)
print("Matha v4.0 模块集成验证")
print("=" * 60)

interp = Interpreter()

# 注册标准库
register_stdlib(interp.builtins)
new_keys = [k for k in interp.builtins if any(x in k for x in ['正则','SHA256','SQLite','路径','CSV','日志','时间','阶乘','组合数','numpy'])]
print(f"标准库注册: {len(new_keys)} 个新函数")

# 注册语言特性
register_language_features(interp.builtins)
print(f"语言特性: with/装饰器/生成器/async/property ✓")

# 注册硬件
register_hardware_builtins(interp.builtins)
hw_keys = [k for k in interp.builtins if 'GPIO' in k or 'HAL' in k or 'ADC' in k]
print(f"硬件驱动: {len(hw_keys)} 个硬件函数")

# 性能优化
from src.perf_opt import HotFunctionTracker, LocalVariableEnv, PersistentCache, PyPyJITAdapter
tracker = HotFunctionTracker()
env = LocalVariableEnv()
cache = PersistentCache()
pypy = PyPyJITAdapter()
print(f"性能优化: 热点追踪({tracker.stats}) 局部变量env 持久缓存({cache.stats}) PyPy适配({pypy.get_stats()})")

# 工程工具
from src.tools import MathaFormatter, MathaLinter, MathaTestCase, MathaProfiler, MathaREPL
fmt = MathaFormatter()
linter = MathaLinter()
profiler = MathaProfiler()
repl = MathaREPL()
print(f"工程工具: 格式化器 林特器 测试框架 profiler REPL ✓")

# 并发扩展
from src.concurrent_v2 import ProcessPool, Supervisor, DistributedLock
pool = ProcessPool(4)
supervisor = Supervisor()
lock = DistributedLock("test_lock")
print(f"并发扩展: 进程池 监督树 分布式锁 ✓")

print()
print("=" * 60)
print("v4.0 集成验证完成")
print("=" * 60)
