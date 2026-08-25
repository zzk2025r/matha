# Matha 自成长引擎 v2.2 发布说明

## 版本信息
- **版本**: v2.2.0
- **日期**: 2025-07-26
- **核心新增**: 标准库 Core、Result 类型、意图解析器、REPL

---

## 新增能力

### 1. 标准库 Core (`src/stdlib/core.py`)

| 类型 | 内建函数数量 | 核心能力 |
|---|---|---|
| **Int** | 14 | 转换、GCD/LCM、素数判断、因数分解、罗马数字 |
| **String** | 22 | 大小写、分割/拼接、替换、切片、反转、填充、词频/行频 |
| **Bool** | 8 | 逻辑运算、条件选择、类型转换 |
| **Array** | 30 | 增删改查、排序、过滤、映射、归约、分块、扁平化、去重 |

### 2. Result 类型 (`src/result.py`)

Rust 风格的错误处理类型：

```python
from src.result import Ok, Err, Some, None_, result

# Result<T, E>
r = result(lambda: 1 / 0)    # Err("ZeroDivisionError: ...")
r = result(lambda: 42)        # Ok(42)

# Option<T>
o = Some(10).map(lambda x: x * 2)  # Some(20)
o = None_().map(lambda x: x * 2)   # None

# 链式调用
result = Ok(5).map(lambda x: x + 1).and_then(lambda x: Ok(x * 2))
```

### 3. 意图解析器 (`src/intent_parser.py`)

自然语言 → 计算意图 → 代码生成：

```python
from src.intent_parser import parse_intent, explain_intent

# 意图分类（9 种类型，优先级排序）
intent = parse_intent("计算 100 以内所有素数")
# IntentType.MATH_FUNC, confidence=0.9

# 参数提取
print(intent.params)  # {'numbers': [100], 'range': (1, 100), ...}

# 代码生成
print(intent.suggested_code)  # Python 代码片段
```

### 4. REPL 交互环境 (`src/repl.py`)

三种交互模式：

```
matha> x = 3.0 + 4.0     # Matha 表达式模式
nl>   计算 100 以内素数   # 自然语言模式
intent> 反转字符串 abc    # 意图分析模式
```

### 5. 意图识别层架构

```
自然语言输入
    │
    ▼
┌─────────────────────────────────────┐
│  IntentClassifier（正则关键词分类）  │
│  9 种意图类型 + 优先级权重            │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  ParamExtractor（参数提取）          │
│  数字/变量/范围/关键词               │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  CodeGenerator（代码生成）           │
│  Python / Rust / Go                 │
└──────────────┬──────────────────────┘
               │
               ▼
         执行 + 结果解释
```

---

## 测试

```
标准库 Core:     60/60 通过
Result 类型:     17/17 通过
Option 类型:      9/9 通过
意图解析器:       9/9 通过
全量回归:        284/284 通过
────────────────────────────
总计:            379/379 通过
```

---

## 快速开始

```python
# 标准库
from src.stdlib.core import register_core_builtins
builtins = {}
register_core_builtins(builtins)
print(builtins["ArraySort"]([3, 1, 2]))   # [1, 2, 3]
print(builtins["StrReverse"]("hello"))    # "olleh"

# Result 类型
from src.result import Ok, Err, result
r = result(lambda: int("abc"))            # Err("ValueError: ...")
print(r.unwrap_or(0))                     # 0

# 意图解析
from src.intent_parser import explain_intent
print(explain_intent("对数组 [3,1,2] 排序"))
```
