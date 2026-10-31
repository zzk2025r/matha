# Matha 架构冻结报告

**冻结时间：** 2026-10-23 16:02:22 +08:00  
**冻结分支：** mainline-frozen  
**冻结提交：** 286d4df（显式栈引擎：闭包环境改为叠加式作用域(Scope)并修正缓存失效）  
**仓库根目录：** D:\trae

## 1. 当前自举链路（冻结前）
当前主线采用的解释器主链路（按实现顺序）：

```
tokens -> lexer -> parser -> ast_nodes -> interp
```

- `src/lexer.py`（Python 实现的词法器）与 `matha/lexer.matha`（Matha 自举词法器）并存。
- `src/parser.py`（Python 实现的语法器，约 4400 行）是主线解析入口，负责将源码解析为 AST。
- `src/ast_nodes.py` 定义 AST 节点类型。
- `src/interp.py` 定义树走式解释器 `Interpreter`，主入口 `interpret(source)` 会调用 `parse(source)` 后执行 `Interpreter(debug=...).run(program)`。
- `src/interp_engine.py`、`src/interp_ic.py` 提供显式栈引引擎与内联缓存等优化路径，但默认均不破坏现有语义（特性开关控制）。

## 2. 黄金测试集
- **存放位置：** `golden_tests/`（位于项目根目录）
- **目录结构：**
  - `golden_tests/manifest.json`：用例清单、引擎信息、特性开关默认值及用例说明。
  - `golden_tests/run_golden_tests.py`：基于 `src.parser.parse` -> `src.interp.Interpreter.run` 的黄金测试运行器。
  - `golden_tests/cases/*.matha`：16 个核心语义用例。
  - `golden_tests/expected/*.out`、`golden_tests/expected/*.err`：冻结的基准输出（stdout/stderr）。
- **通过状态：** `python golden_tests/run_golden_tests.py` → **16 passed, 0 failed**（100% 通过）

黄金测试覆盖的核心语义：算术与关系、函数定义与返回类型、柯里化与闭包、高阶函数、块尾值（命令块）、SCOPED_BLOCKS 下函数语句块、多语句、`while/for`、`break/continue`、`try/catch/raise`、`throw`、内建运行时错误捕获、未捕获错误保留 stdout 与 stderr、类型标注与 `typeof`、递归等。

## 3. 待融合的多套实现清单（审计结论）
根据审计报告，当前主线中存在多套平行实现，需在后续融合工作中统一：

| 类别 | 数量（约） | 说明 |
| --- | --- | --- |
| **解释器** | 8 套 | `src/interp.py`、`src/interp_engine.py`、`src/interp_ic.py`、`matha/interp.matha`、`matha/interp_matha.matha`、`matha/vm.matha`、`src/mbc/*`（字节码 VM）、原生后端等多套执行路径并存。 |
| **类型系统** | 6 套 | 类型标注解析、运行时 `typeof`、类型检查相关逻辑分散在解释器、编译器、MBC、VM、原生后端及自举代码中，尚未统一契约。 |
| **AST** | 4 套 | `src/ast_nodes.py`、解析器内部节点构造、自举解析器（`matha/parser.matha`）产生的 AST 表示、MBC/IR 层的中间表示之间存在差异。 |
| **IR** | 4 套 | `src/mir.py`、`src/mir_codegen.py`、MBC 字节码 IR、各语言桥接（frontends）产生的 IR 等多套中间表示。 |
| **诊断** | 5 套 | `ParseError`、`MathaRuntimeError`、编译器诊断、自举诊断、各后端（VM/Native/MBC) 的错误处理与消息格式不统一。 |
| **测试入口** | 4 套 | `tests/`（pytest）、根目录大量调试脚本（`debug_*.py`）、`run_all.py`、各模块自带 CLI/入口等多种测试和运行方式。 |

## 4. 冻结声明
自此提交起，**主线代码正式冻结**。后续的重构、多路径融合工作，**必须在新建的功能分支中进行**，且**每一次改动都必须通过 `golden_tests/` 回归测试**。

在融合过程中，应优审计报告中指出的最关键问题：“块尾值与错误类型不统一”，并以黄金测试集为最高权威，确保融合后的行为与冻结前的现行语义完全一致。

---
**报告结束**
