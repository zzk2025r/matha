# Matha 自成长引擎 — 优化规则文档 v2

## 概述

Matha 自成长引擎（`MathaGrowthEngine`）是一个自动源码分析与优化系统，支持多语言前端编译对比、跨语言交叉验证和自动优化生成。

核心架构：
```
源码 → 多语言前端编译 → IR分析 → 优化建议 → 优化管道 → 验证 → 改进版本
          (Rust/Go/JS/C/Python)    (MIR对比)   (诊断+规则)   (7条规则)  (执行对比)
```

---

## 优化规则集（按优先级排序）

### P0 级优化（常量级）

#### 1. 常量折叠（Const Folding）
**规则 ID**: `OPT-001`
**触发条件**: 变量赋值右侧为纯常量表达式
**数学原理**: 常量表达式可在编译期求值
**示例**:
```python
# 优化前
x = 3.0 + 4.0
y = 2.0 * 5.0 + 1.0

# 优化后
x = 7.0
y = 11.0
```
**实现**: `_apply_const_folding()`
**正则**: `(\w+)\s*=\s*([\d.]+\s*[+\-*/%]\s*[\d.]+)`
**安全约束**: 仅当表达式可被 `eval()` 安全求值时应用

---

#### 2. 死代码消除（Dead Code Elimination）
**规则 ID**: `OPT-002`
**触发条件**: 变量赋值后无后续引用
**数学原理**: 无副作用的未使用赋值不影响程序语义
**示例**:
```python
# 优化前
unused = 999.0
a = 10.0
result = a + 1.0

# 优化后
a = 10.0
result = a + 1.0
```
**实现**: `_apply_dead_code_elimination()`
**分析方法**: 遍历赋值行，检查剩余代码中是否存在变量引用
**安全约束**: 不消除函数定义、控制流关键字

---

#### 3. 常量传播（Constant Propagation）
**规则 ID**: `OPT-003`
**触发条件**: 变量被赋值为常量，且后续被引用
**数学原理**: 常量值可代入引用点消除中间变量
**示例**:
```python
# 优化前
a = 10.0
b = a + 5.0
result = b * 2.0

# 优化后
a = 10.0
b = 10.0 + 5.0
result = b * 2.0
```
**实现**: `_apply_const_propagation()`
**注意**: 此优化不合并赋值链（由内存优化处理），仅替换引用点

---

### P1 级优化（函数级）

#### 4. 函数内联 — 单用函数（Single-Use Inlining）
**规则 ID**: `OPT-004a`
**触发条件**: 函数只被调用一次（调用次数 = 总出现次数 - 定义次数）
**数学原理**: 单次调用的函数开销可被消除，减少函数调用栈
**示例**:
```python
# 优化前
def square(x):
    return x * x

result = square(5.0)

# 优化后
result = 5.0 * 5.0
```
**实现**: `_apply_function_inlining()` 阶段 1
**检测逻辑**:
1. 找到所有 `def f(params): return expr` 格式的函数
2. 统计每个函数的调用次数（排除 `def` 定义本身）
3. 调用次数 = 1 时执行内联
**嵌套函数**: 支持多轮迭代内联（最多 10 轮），从后往前处理避免位置偏移

---

#### 5. 函数内联 — 递归展开（Recursive Inlining）
**规则 ID**: `OPT-004b`
**触发条件**: 函数是递归的，且只被调用一次
**数学原理**: 递归展开消除调用开销，适用于深度受限的递归
**示例**:
```python
# 优化前（factorial(3)）
def factorial(n):
    if n <= 1.0:
        return 1.0
    return n * factorial(n - 1.0)

result = factorial(3.0)

# 优化后（展开 2 层）
result = 3.0 * (2.0 * (1.0 <= 1.0 ? 1.0 : ...))
```
**实现**: `_apply_function_inlining()` 阶段 2 + `_expand_recursive_call()`
**深度限制**: `MAX_INLINE_DEPTH = 5`（防止爆炸式展开）

---

#### 6. 递归函数诊断
**规则 ID**: `OPT-004c`
**触发条件**: 检测到函数体内引用自身
**诊断信息**: `"函数 'fname' 是递归函数，可尝试递归内联优化"`
**实现**: `_diagnose()` 中的递归检测逻辑

---

### P2 级优化（循环级）

#### 7. 循环展开（Loop Unrolling）
**规则 ID**: `OPT-005`
**触发条件**: `for i in range(N):` 模式，且 N ≤ 8
**数学原理**: 展开循环消除迭代开销，适合小型循环
**示例**:
```python
# 优化前
s = 0.0
for i in range(4):
    s = s + float(i)

# 优化后
s = 0.0 + float(0) + 0.0 + float(1) + 0.0 + float(2) + 0.0 + float(3)
```
**实现**: `_apply_loop_unrolling()`
**限制**: `MAX_UNROLL_FACTOR = 8`（防止代码膨胀）
**展开模式**: `body.replace(var_name, f"({i})")` 并合并为加法链

---

### P3 级优化（内存级）

#### 8. 内存优化 — 赋值链合并（Assignment Chain Merge）
**规则 ID**: `OPT-006`
**触发条件**: 连续三行赋值形成链式依赖（a→b→c）
**数学原理**: 消除中间变量减少内存分配
**示例**:
```python
# 优化前
a = 10.0
b = a + 5.0
c = b * 2.0

# 优化后
c = 10.0 + 5.0 * 2.0
```
**实现**: `_apply_memory_optimization()`
**安全约束**: 仅当两端表达式均可被 `eval()` 求值时应用

---

### P4 级优化（数学级）

#### 9. 三角恒等式（Trigonometric Identity）
**规则 ID**: `OPT-007`
**触发条件**: `sin(x) + cos(π/2-x)` 模式
**数学原理**: sin(x) + cos(π/2-x) = 2sin(x)（特定近似）
**示例**:
```python
# 优化前
x = sin(3.14159) + cos(1.5708)

# 优化后
x = sin(3.14159) + sin(3.14159/2.0)
```
**实现**: `_generate_improved()` 中的硬编码替换
**注意**: 这是特定模式的简化，非通用恒等式推导

---

## 优化管道执行顺序

```
输入源码
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  Step 1: 诊断 (_diagnose)                            │
│    • 三角恒等式检测                                   │
│    • 多步赋值检测                                     │
│    • 循环检测                                         │
│    • 递归函数检测                                     │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  Step 2: 多语言编译 (_compile_all_languages)         │
│    Python / Rust / Go / JavaScript / C 各5个前端    │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  Step 3: 性能基准 (_detect_and_convert + interpret)  │
│    转换为 Matha 可执行格式并测量执行时间              │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  Step 4: 优化建议 (_suggest_optimizations)           │
│    综合诊断 + 多语言对比 + MIR 分析                  │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  Step 5: 优化管道 (_generate_improved)               │
│                                                      │
│  P0: 常量折叠 → 死代码消除 → 常量传播                │
│  P1: 函数内联（单用 + 递归展开）                      │
│  P2: 循环展开                                       │
│  P3: 内存优化（赋值链合并）                           │
│  P4: 三角恒等式                                     │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  Step 6: 验证 (_detect_and_convert + interpret)      │
│    改进版本执行对比，检测错误                         │
└─────────────────────────────────────────────────────┘
    │
    └──→ 生成 GrowthReport（含优化应用记录）
```

---

## 安全约束与边界

| 约束 | 规则 | 说明 |
|---|---|---|
| 递归深度限制 | OPT-004b | 最大内联深度 5 层 |
| 循环展开限制 | OPT-005 | 最大展开倍数 8 |
| 常量求值安全 | OPT-001, 003 | 仅当 `eval()` 不抛异常时应用 |
| 死代码识别 | OPT-002 | 不消除函数定义和控制流 |
| 赋值链验证 | OPT-006 | 仅当两端均可 eval 时合并 |
| 多语言一致性 | 全局 | 改进后需通过跨语言验证 |
| 函数调用计数 | OPT-004a | 排除 `def` 定义行，仅统计调用 |
| 位置偏移防护 | OPT-004a | 函数内联从后往前处理，重新扫描 |

---

## 典型优化路径示例

### 示例 1: 嵌套函数链
```python
# 原始源码
def double(x): return x * 2.0
def triple(x): return x * 3.0
def compute(x): return double(triple(x))
result = compute(5.0)

# 优化路径: compute → double → triple
result = 5.0 * 3.0 * 2.0    # 函数内联 × 3
result = 30.0                # 常量折叠 × 2
```

### 示例 2: 死代码 + 函数
```python
# 原始源码
unused = 999.0
def square(x): return x * x
result = square(3.0)

# 优化路径: 移除死代码 → 内联函数
result = 3.0 * 3.0           # 死代码消除 × 1, 函数内联 × 1
result = 9.0                  # 常量折叠 × 1
```

### 示例 3: 常量传播链
```python
# 原始源码
a = 10.0
b = a + 5.0
c = b * 2.0
d = c - 10.0
result = d + 1.0

# 优化路径: 传播 + 折叠
b = 15.0
c = 30.0
result = 21.0
```

---

## API 使用

```python
from src.matha_growth import MathaGrowthEngine

engine = MathaGrowthEngine(verbose=True)

# 单次成长
report = engine.grow(source, max_iterations=3)
print(report.optimizations_applied)  # ['函数内联 × 3', '常量折叠 × 2']
print(report.improved_source)        # 优化后的源码

# 查看历史
history = engine.get_history()
for r in history:
    print(f"迭代 {r.iteration}: {r.optimizations_applied}")

# 摘要
print(engine.get_summary())
```

---

## 文件索引

| 模块 | 文件 | 说明 |
|---|---|---|
| 成长引擎 | [src/matha_growth.py](file:///d:/trae/src/matha_growth.py) | 核心优化管道（v2） |
| 多语言前端 | [src/multi_lang_frontend.py](file:///d:/trae/src/multi_lang_frontend.py) | 5 语言前端实现 |
| 交叉验证 | [src/cross_language_verifier.py](file:///d:/trae/src/cross_language_verifier.py) | 跨语言一致性检查 |
| 单元测试 | [tests/test_multi_lang_frontend.py](file:///d:/trae/tests/test_multi_lang_frontend.py) | 31 个测试用例 |
| 集成测试 | [examples/test_multilang_integration.py](file:///d:/trae/examples/test_multilang_integration.py) | 端到端验证 |
| 复杂测试 | [examples/test_recursive_closure.py](file:///d:/trae/examples/test_recursive_closure.py) | 递归/闭包/循环测试 |
