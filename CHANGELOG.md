# Matha v1.3.0 发布说明

**发布日期**: 2026-08-23
**版本**: 1.3.0
**健康分**: 100.0
**测试通过率**: 59/59 (100%)

---

## 概述

v1.3.0 是一次重大架构升级，引入了统一的符号表达式系统、外部函数接口(FFI)、多范式融合引擎、跨平台代码生成器和数学抽象驱动层。本次更新还修复了 13 个缺陷/漏洞，显著提升了系统的可靠性、安全性和性能。

---

## 新功能

### 1. 统一符号表达式引擎 (`src/symbolic.py`)
- **AST 节点**: Num/Var/Add/Mul/Sub/Div/Pow/Neg/Log/FuncCall
- **符号解析**: 支持 `^` 幂运算、`*` 隐式乘法、`sin/cos/tan/sqrt/log/exp` 等函数
- **代数简化**: 自动合并同类项、化简常数
- **符号求导**: 支持链式法则、幂法则、三角函数求导
- **数值求值**: 代入变量求数值结果
- **AST 序列化**: 支持 JSON 格式导出，用于跨语言代码生成

### 2. FFI 外部函数接口 (`src/ffi.py`)
- **Python 函数注册**: 将 Python 函数注册为 Matha 内建函数
- **模块导入**: 通过 `import_module` 将 Python 模块桥接到 Matha 命名空间
- **27+ 数学函数预注册**: sin/cos/sqrt/log/exp/abs/factorial/pow 等
- **线性插值/钳制**: 新增 `lerp`/`clamp` 实用函数
- **调用日志**: 追踪每次调用的参数、结果、延迟
- **线程安全**: 使用 `threading.Lock` 保护并发访问

### 3. 多范式融合引擎 (`src/multi_paradigm.py`)
- **函数式引擎**: LISP/Scheme S-表达式求值，支持 let 绑定、lambda
- **命令式引擎**: Python 风格赋值、for 循环、if-else
- **符号式引擎**: 集成符号表达式解析、求导、简化
- **逻辑式引擎**: 谓词逻辑、约束求解
- **数据流引擎**: DAG 节点执行，支持 FFI 节点集成
- **智能任务分发**: 根据任务特征自动选择最优范式

### 4. 跨平台代码生成器 (`src/symbol_codegen.py`)
- **Python 代码生成**: `x^2 + 3*x - 5` → `def f(x): result = x**2 + 3*x - 5; return result`
- **JavaScript 代码生成**: 使用 `Math.sin`/`Math.cos` 等标准 API
- **C 代码生成**: 使用 `pow()`/`sin()`/`cos()` 等标准函数
- **e 常量边界匹配**: 使用 `re.sub(r'\be\b', ...)` 避免误替换变量名
- **驱动规格生成**: 支持硬件驱动代码自动生成

### 5. 数学驱动层 (`src/math_driver.py`)
- **线性代数驱动**: 矩阵行列式、乘法、转置、特征值、范数、点积、叉积等
- **微积分驱动**: 数值导数、泰勒展开、数值积分、极限
- **信号处理驱动**: FFT、IFFT、卷积、滤波
- **几何驱动**: 圆面积、球体积、距离计算
- **优化驱动**: 梯度下降、二分搜索、黄金分割搜索
- **吞噬/同化**: 将 Python/JS/C 函数注册为 Matha 运算

### 6. 内循环自检增强 (Phase 4.55)
- **FFI 健康检查**: 抽样调用 sin/cos/sqrt/exp/log 验证
- **驱动健康检查**: 验证 mat_det/dot/circle_area/binary_search
- **符号引擎检查**: 验证基础表达式解析和求值
- **微积分检查**: 验证导数计算 `d/dx(x³+2x²-5x+3) at x=1 = 2`
- **代码生成检查**: 验证 Python/JS/C 三语言代码生成
- **沙箱执行检查**: 验证安全 exec 环境
- **多范式检查**: 验证函数式/命令式/数据流范式
- **完整日志**: 每项检查详细日志输出，方便排查

---

## 修复的缺陷

### P0 严重缺陷

| # | 模块 | 问题 | 修复 |
|---|------|------|------|
| 1 | `inner_loop.py:836` | `last_duration` 字段不存在导致 `AttributeError` | 添加到 `LoopState` 数据类 |
| 2 | `inner_loop.py:344` | `_parse_intent_from_text` 返回 `str` 而非 `IntentType` | 改为返回枚举类型 |
| 3 | `inner_loop.py:362/477` | 自扩展创建临时 `FriendlyIntentParser`，修改不持久化 | 改用 `self._assistant.parser` 共享实例 |
| 4 | `math_driver.py:546` | `exec(code, globals())` 代码注入漏洞 | 使用沙箱 `safe_globals` 限制作用域 |
| 5 | `symbolic.py:240/246` | 除零返回 `inf` 而非异常 | 改为抛 `ZeroDivisionError` |
| 6 | `symbolic.py:343` | `to_expr("3.14")` 误转 `Var("3.14")` | 数字字符串优先转 `Num` |
| 7 | `symbolic.py:403` | `_parse_term` 用 `_split_top_level` 不记录分隔符，导致 `1/x` 解析为 `x` | 改用 `_split_with_ops` 跟踪 `*`/`/` 分隔符 |
| 8 | `symbol_codegen.py:99` | `.replace('e', 'math.e')` 误替换所有字母 `e`（包括变量名） | 改用 `re.sub(r'\be\b', 'math.e', result)` |
| 9 | `symbol_codegen.py:72-74` | Python 代码生成 `return result` 在表达式赋值之前，导致 `UnboundLocalError` | 将表达式插入到 `return` 之前 |
| 10 | `symbol_codegen.py:180` | C 代码 `^` 生成 `**`（C 不支持幂运算符） | 改用 `re.sub(r'(\w+)\s*\^\s*(\w+)', r'pow(\1, \2)', expr)` |

### P1 中等缺陷

| # | 模块 | 问题 | 修复 |
|---|------|------|------|
| 11 | `multi_paradigm.py:137` | `except Exception: pass` 吞掉所有异常 | 区分 `ValueError`（FFI不存在）和警告日志 |
| 12 | `ffi.py` | 无线程锁，多线程竞态条件 | 添加 `threading.Lock()` 保护 `_registry`/`_imports`/`_call_log` |
| 13 | `inner_loop.py:125` | `init_modules()` 缺少 v1.3.0 模块初始化 | 补回 `_symbolic_parser`/`_ffi`/`_driver_mgr`/`_paradigm`/`_codegen` |

### P2 轻微缺陷

| # | 模块 | 问题 | 修复 |
|---|------|------|------|
| 14 | `math_driver.py:267` | 泰勒展开高阶导数运行时崩溃 | 改为链式函数求导 |
| 15 | `inner_loop.py:510/558/686` | 版本号硬编码 `1.2.21/1.2.22` | 统一为 `1.3.0` |

---

## 测试覆盖

### 单元测试 (59/59 通过)

| 模块 | 测试数 | 通过 | 通过率 |
|------|--------|------|--------|
| 符号引擎 | 18 | 18 | 100% |
| FFI 桥接器 | 11 | 11 | 100% |
| 多范式引擎 | 6 | 6 | 100% |
| 代码生成 | 5 | 5 | 100% |
| 数学驱动 | 9 | 9 | 100% |
| 沙箱安全 | 2 | 2 | 100% |
| 内循环自检 | 2 | 2 | 100% |
| 复杂数学 E2E | 6 | 6 | 100% |

### 集成测试

| 测试文件 | 结果 |
|---------|------|
| `tests/test_v130_unit_report.py` | 59/59 ✅ |
| `tests/test_lisp_ffi_mixed.py` | 5/5 ✅ |
| `tests/test_growth_engine.py` | 29/29 ✅ |
| `tests/test_health_check.py` | 9/9 ALL OK ✅ |

---

## API 端点 (v1.3.0)

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/symbolic/parse` | POST | 符号表达式解析+求导+求值 |
| `/api/ffi/list` | GET | FFI 函数列表 |
| `/api/ffi/call` | POST | FFI 函数调用 |
| `/api/paradigm/compute` | POST | 多范式计算 |
| `/api/codegen/python` | POST | Python 代码生成 |
| `/api/codegen/javascript` | POST | JS 代码生成 |
| `/api/codegen/c` | POST | C 代码生成 |
| `/api/drivers/list` | GET | 驱动列表 |
| `/api/drivers/execute` | POST | 驱动执行 |

---

## 变更文件

| 文件 | 变更说明 |
|------|---------|
| `src/symbolic.py` | 除法解析修复、除零异常、to_expr 修复 |
| `src/ffi.py` | clamp/lerp 函数、线程锁 |
| `src/multi_paradigm.py` | 异常处理优化 |
| `src/math_driver.py` | 沙箱安全、泰勒展开修复 |
| `src/symbol_codegen.py` | e 常量修复、C 代码生成、代码结构修复 |
| `src/inner_loop.py` | v1.3.0 模块初始化、自检增强、版本统一 |
| `src/ai_assistant_server.py` | 新增 v1.3.0 API 端点 |
| `tests/test_v130_unit_report.py` | 新增完整单元测试 |
| `tests/test_lisp_ffi_mixed.py` | LISP/Python 混合测试 |
| `tests/test_health_check.py` | 健康检查测试 |

---

## 兼容性说明

- **Python 版本**: 需要 Python 3.8+
- **依赖**: 无新增外部依赖（仅使用标准库 `math`/`re`/`threading`）
- **API 变更**: 新增端点，无破坏性变更
- **代码生成**: 生成的 Python 代码函数签名从 `def f():` 改为 `def f(x):`

---

## 已知限制

1. 符号表达式解析不支持连续分隔符（如 `x + + y`）
2. 驱动吞噬功能使用 `exec()` 但已限制为沙箱环境
3. 内循环自检在模块未初始化时跳过（不影响主循环）

---

**完整报告**: `tests/v1.3.0_test_report.json`
**HTML 报告**: `tests/v1.3.0_test_report.html`
