# Matha v2.0 HAL 发布说明

**发布日期**: 2026-08-23
**版本**: 2.0
**父版本**: 1.3.0
**健康分**: 100.0
**测试通过率**: 135/135 (100%)

---

## 概述

v2.0 HAL 是 Matha 语言的硬件抽象层重大升级，引入了安全副作用追踪、指针与内存控制、裸机编译、协议自动代码生成和硬件驱动自动生成能力。本次更新使 Matha 从纯软件数学计算语言扩展为支持嵌入式/裸机开发的完整工具链。

---

## 新模块

### `src/hardware/hal_v2.py` — 硬件抽象层 v2.0

| 组件 | 类 | 行数 | 功能 |
|------|----|------|------|
| 副作用引擎 | `SafeSideEffectEngine` | ~100 | 追踪副作用类型，权限检查，沙箱隔离 |
| 指针管理器 | `PointerManager` | ~80 | 4KB页式内存，堆分配/释放，越界检测 |
| 裸机目标 | `BareMetalTarget` | ~20 | 架构配置(8种CPU目标) |
| 协议解析器 | `ProtocolParser` | ~120 | UART/SPI/I2C/CAN 自动代码生成 |
| 驱动生成器 | `DriverGenerator` | ~100 | 传感器/执行器/通信/数学驱动模板 |
| 原生编译 | `NativeBackend` | ~60 | C/汇编/Python 多目标编译 |

**单例导出**: `get_side_effect_engine()`, `get_pointer_manager()`, `get_protocol_parser()`, `get_driver_generator()`, `get_native_backend()`

### `src/compiler/native.py` — 原生编译层 v2.0

| 组件 | 类 | 功能 |
|------|----|------|
| 协议解释器 | `ProtocolInterpreter` | 协议解析 → 可执行代码 |
| 驱动构建器 | `DriverBuilder` | 驱动规格 → 代码生成 + FFI注册 |
| 原生编译器 | `NativeCompiler` | 表达式 → 多架构原生代码 |

**便捷函数**: `interpret_protocol()`, `build_driver()`, `native_compile()`, `get_native_stats()`

---

## 功能详情

### 1. 安全副作用引擎

```python
from src.hardware.hal_v2 import get_side_effect_engine, SideEffectType

sse = get_side_effect_engine(mode="sandbox")  # sandbox / restricted / full
sse.register_func("uart_send", SideEffectType.IO, "exec")
sse.register_func("math_sqrt", SideEffectType.READ, "readonly")

# 权限检查
assert sse.check_permission("uart_send", "exec")    # True
assert sse.check_permission("math_sqrt", "readonly")  # True

# 受保护执行
result = sse.execute_with_check(my_function, arg1, arg2)

# 统计
stats = sse.get_stats()
# {'mode': 'sandbox', 'registered_funcs': 4, 'total_calls': 10,
#  'blocked_calls': 2, 'by_type': {'read': 2, 'io': 1, 'hardware': 1}}
```

**副作用类型**: `NONE`, `READ`, `WRITE`, `IO`, `MEMORY`, `HARDWARE`, `SYSTEM`
**权限等级**: `readonly` < `write` < `exec`

### 2. 指针与内存控制

```python
from src.hardware.hal_v2 import get_pointer_manager

pmgr = get_pointer_manager(page_count=32)  # 32页 × 4KB = 128KB

# 分配
ptr = pmgr.alloc(256, "uart_tx_buf")
# Ptr(uart_tx_buf@0x4000 type=alloc_256B)

# 读写
ptr.set(42)
val = ptr.get()  # 42

ptr2 = ptr.plus(10)  # 指针算术

# 释放
pmgr.free(ptr)

# 统计
stats = pmgr.get_stats()
# {'total_pages': 32, 'total_memory_kb': 128, 'active_allocs': 0,
#  'bounds_violations': 0}
```

**内存保护**:
- 前 4 页为系统区(只读)，用户页可写
- 分配超过 4KB 页大小自动拒绝
- 释放后悬空指针检测并记录警告

### 3. 协议解释生成器

```python
from src.hardware.hal_v2 import ProtocolParser, ProtocolSpec, ProtocolType

pp = ProtocolParser()
spec = ProtocolSpec(protocol=ProtocolType.UART, name="uart0",
                    baud_rate=115200, data_bits=8, parity="none", stop_bits=1)
result = pp.parse(spec)
# {'code_python': '...', 'code_c': '...', 'params': {...}}
```

**支持的协议**:
| 协议 | 参数 | 生成代码 |
|------|------|---------|
| UART | 波特率/数据位/校验/停止位 | Python串口 + C寄存器操作 |
| SPI | 时钟/通道/模式 | Pythonspidev + C SPI寄存器 |
| I2C | 地址/总线 | Pythonsmbus + C I2C寄存器 |
| CAN | 波特率/ID类型 | Python cantools + C CAN寄存器 |

### 4. 驱动生成器

```python
from src.hardware.hal_v2 import DriverGenerator, DriverKind, DriverSpec, Architecture

dg = DriverGenerator(pp)
spec = DriverSpec(
    name="ads1115_temp", kind=DriverKind.SENSORS,
    target_arch=Architecture.RISCV32, target_lang="c",
    params={"scale": 0.0078125, "offset": -40.0, "unit": "°C"},
    math_expr="raw * 0.0078125 - 40.0",
)
result = dg.generate(spec)
# 生成 C 类模板代码，包含 SCALE/OFFSET/UNIT 常量和 read()/calibrated_read() 方法
```

**驱动类型**: `SENSORS`, `ACTUATORS`, `COMM`, `DISPLAY`, `STORAGE`, `POWER`, `MATH`

### 5. 原生编译后端

```python
from src.hardware.hal_v2 import NativeBackend, Architecture

nb = NativeBackend()
nb.register_target(BareMetalTarget(Architecture.RISCV32, optimize="Os"))

# 编译为 C
code = nb.compile("x^2 + 3*x - 5", Architecture.RISCV32, "compute", "c")
# 包含链接脚本、头文件、函数定义

# 编译为汇编
asm = nb.compile("sin(x)", Architecture.RISCV32, "sin_fn", "assembly")
# 生成 RISC-V 汇编框架
```

**支持目标**: `x86_64`, `arm64`, `arm32`, `riscv64`, `riscv32`, `avr`, `msp430`, `wasm`

---

## 端到端示例

### RISC-V 裸机固件构建 (`scripts/baremetal_riscv_demo.py`)

```
目标芯片: SiFive FE310 (RISC-V 32-bit)
协议: UART 115200 8N1 + I2C 100kHz (ADS1115)

[1] 协议解析
  UART: Python 234B, C 318B
  I2C:  Python 146B, C 209B

[2] 驱动生成
  温度传感器 (C/RISCV32):    432B
  多项式求值 (C/RISCV64):    133B
  PWM电机 (Python/ARM64):     311B

[3] 原生编译
  RISC-V32 汇编: 186B
  RISC-V32 C:    661B
  ARM64 C:       651B
  x86_64 C:      649B

[4] 指针管理
  分配 UART TX/RX buf + I2C regs
  读写验证: 0x48, 0x01 ✓
  释放后剩余: 4096B ✓

[5] 固件统计
  代码: ~2005B | RAM: ~528B
  Flash: 0x08000000 (256K) | RAM: 0x20000000 (64K)
```

---

## 内存日志增强

PointerManager 新增详细日志，方便排查内存问题：

```
[内存] 候选页[4] base=0x4000 used=0B remaining=4096B size=256B ✓ 可用
[内存] 分配 ✓: uart_tx_buf @ 0x4000 page[4] size=256B used_after=256B remaining=3840B
[内存] 分配 ✓: uart_rx_buf @ 0x4100 page[4] size=256B used_after=512B remaining=3584B
[内存] 分配 ✓: i2c_regs @ 0x4200 page[4] size=16B used_after=528B remaining=3568B
[内存] 释放 ✓: 0x4000 page[4] size=256B remaining=3824B
[内存] 释放 ✓: 0x4100 page[4] size=256B remaining=4080B
[内存] 释放 ✓: 0x4200 page[4] size=16B remaining=4096B
[内存] 释放 ✗: 悬空指针 0xFFFF 未找到分配记录   ← 警告
[内存] 候选页[4] base=0x4000 used=4096B remaining=0B size=100B ✗ 不足
MemoryError: 内存不足: 请求 100B, 总空闲=0B (页总数=32, 活跃分配=8)
```

---

## API 端点 (v2.0)

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/hardware/hal_v2/stats` | GET | HAL v2.0 全部统计 |
| `/api/hardware/protocol/parse` | POST | 协议解析 |
| `/api/hardware/driver/generate` | POST | 驱动生成 |
| `/api/hardware/native/compile` | POST | 原生编译 |
| `/api/hardware/memory/alloc` | POST | 内存分配 |
| `/api/hardware/memory/free` | POST | 内存释放 |

---

## 测试覆盖

| 模块 | 测试数 | 通过 | 通过率 |
|------|--------|------|--------|
| 安全副作用引擎 | 4 | 4 | 100% |
| 指针与内存控制 | 9 | 9 | 100% |
| 协议解释生成器 | 4 | 4 | 100% |
| 驱动生成器 | 4 | 4 | 100% |
| 原生编译后端 | 5 | 5 | 100% |
| 端到端流水线 | 5 | 5 | 100% |
| 内循环 HAL 自检 | 2 | 2 | 100% |
| **HAL v2.0 小计** | **33** | **33** | **100%** |
| v1.3.0 符号/FFI/多范式/CodeGen/驱动/沙箱/E2E | 59 | 59 | 100% |
| 成长引擎 | 29 | 29 | 100% |
| LISP/Python 混合 FFI | 5 | 5 | 100% |
| 健康检查 | 9 | 9 | 100% |
| **总计** | **135** | **135** | **100%** |

---

## 兼容性说明

- **Python 版本**: 需要 Python 3.8+
- **依赖**: 无新增外部依赖（仅使用标准库）
- **API 变更**: 新增 `/api/hardware/` 前缀端点，无破坏性变更
- **内存模型**: 4KB 页大小，128KB 默认内存(32页)，可通过 `page_count` 参数调整
- **代码生成**: 生成的 C 代码含链接脚本，适用于标准裸机工具链(GCC/LLVM)

---

## 已知限制

1. 汇编代码生成器为占位符框架，实际汇编需通过 LLVM/GCC 后端生成
2. 内存分配为简化模型，不支持碎片整理和页面回收
3. 协议解析器仅生成 Python/C 框架代码，需根据具体硬件填充寄存器操作
4. 副作用引擎审计日志固定 1000 条，高频场景可能丢失历史

---

## 文件清单

| 文件 | 变更 |
|------|------|
| `src/hardware/hal_v2.py` | 新增 v2.0 HAL 模块 (800+ 行) |
| `src/compiler/native.py` | 新增原生编译层 (260+ 行) |
| `src/inner_loop.py` | 集成 v2.0 HAL 模块 + Phase 4.56 自检 |
| `scripts/baremetal_riscv_demo.py` | RISC-V 裸机驱动生成示例 |
| `tests/test_hal_v2.py` | HAL v2.0 单元测试 (33 用例) |
| `tests/v2.0_hal_test_report.json` | 结构化测试报告 |

---

**完整测试报告**: `tests/v2.0_hal_test_report.json`
