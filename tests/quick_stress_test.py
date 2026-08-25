import sys
import time
import logging
logging.disable(logging.CRITICAL)

sys.path.insert(0, r"D:\trae")
from src.hardware.hal import HardwareAbstractionLayer, MathaHardwareOps, GPIODevice

h = HardwareAbstractionLayer()
ops = MathaHardwareOps(h)
pins = [18, 19, 20, 21]
for p in pins:
    h.register(GPIODevice(p))

# 测试批量写入
t = time.perf_counter()
for _ in range(1000):
    ops.批量写入([(f'gpio_{p}', True) for p in pins])
t1 = (time.perf_counter() - t) * 1000

rate = 1000 / (t1 / 1000) * 4
period_us = t1 / 1000 * 1000
status = "OK" if period_us < 100 else "NEED Opt"

print('='*50)
print('  10kHz 压力测试结果')
print('='*50)
print(f'1000次批量写入(4路): {t1:.1f}ms')
print(f'单次耗时: {t1/1000:.4f}ms')
print(f'吞吐量: {rate:,.0f} ops/sec')
print(f'实际周期: {period_us:.1f}us')
print(f'10kHz可行性: {status}')

# 清理
for p in pins:
    h.unregister(f'gpio_{p}')
