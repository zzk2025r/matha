# Matha 内核依赖基线

> 本文件由 `python scripts/dep_audit.py --write-report` 生成，请勿手改。
> 棘轮基线见 `tests/kernel_purity_baseline.json`，守门测试见 `tests/test_kernel_purity.py`。

## 一、契约

- **唯一执行主线**：`lexer -> parser -> ast_nodes -> mbc.compiler -> mbc.vm`（`mbc.native` 为可选机器码发射）。
- **内核文件清单**：`KERNEL_FILES` + `src/kernel/**`（见 `scripts/dep_audit.py`）。
- **允许**：Python 标准库中不向外逃逸的模块。
- **禁止**：第三方包；`subprocess/threading/concurrent/multiprocessing/asyncio/socket/ctypes` 等逃逸模块；`src.domains.*`（插件层）、`src.interp` 与 `src.compiler.*` 等遗留层。
- **不视为违规的例外**：`mbc/native.py` 生成的 exe 调用 CRT（`_ecvt/rint/pow/fopen`）属 OS ABI 依赖，与 Python 依赖无关，记录于此但不进入统计。

## 二、审计范围

- 内核文件数：25
- 内核 import 边数：68
- 违规条目：**0**

## 三、违规清单（按类）

无。内核已达成零外部依赖。
## 四、内核 → 外部层 依赖方向

| 内核模块 | 外逸依赖 |
|---|---|
| `src.kernel.exec_api` | src.plugin_api [contract] |

## 五、插件层 → 内核 反向守卫（零容许）

联邦契约的对角线：领域插件只能通过 `src.plugin_api` 的公开接口与内核交互。
无越界条目：插件层不 import 内核私有名字，也不读 vm / interp 的私有成员。

## 六、每个内核文件的 import 清单

### `src/ast_ext.py`

- 标准库/外部：`__future__`, `dataclasses`, `src`, `typing`
- src.*：无

### `src/ast_nodes.py`

- 标准库/外部：`__future__`, `dataclasses`, `typing`
- src.*：无

### `src/custom_ops.py`

- 标准库/外部：`__future__`, `dataclasses`
- src.*：无

### `src/features.py`

- 标准库/外部：`__future__`, `os`
- src.*：无

### `src/formula_schema.py`

- 标准库/外部：`__future__`, `collections.abc`, `dataclasses`, `src`, `typing`
- src.*：无

### `src/kernel/__init__.py`

- 标准库/外部：`__future__`
- src.*：`src.kernel`, `src.kernel.file_builtin`, `src.kernel.time_builtin`, `src.mathlib`, `src.regexlib`

### `src/kernel/errors.py`

- 标准库/外部：`__future__`
- src.*：无

### `src/kernel/exec_api.py`

- 标准库/外部：`__future__`, `pathlib`, `typing`
- src.*：`src.kernel`, `src.mbc`, `src.mbc.compiler`, `src.mbc.native`, `src.mbc.vm`, `src.plugin_api`

### `src/kernel/file_builtin.py`

- 标准库/外部：`__future__`
- src.*：无

### `src/kernel/time_builtin.py`

- 标准库/外部：`__future__`, `calendar`, `datetime`, `time`
- src.*：无

### `src/lexer.py`

- 标准库/外部：无
- src.*：`src.tokens`

### `src/mathlib.py`

- 标准库/外部：`__future__`, `math`, `random`
- src.*：无

### `src/mbc/__init__.py`

- 标准库/外部：无
- src.*：`src.mbc`, `src.mbc.compiler`, `src.mbc.serial`, `src.mbc.vm`

### `src/mbc/cli.py`

- 标准库/外部：`__future__`, `argparse`, `pathlib`, `sys`
- src.*：`src.kernel`, `src.mbc`

### `src/mbc/compiler.py`

- 标准库/外部：`__future__`, `dataclasses`, `src`
- src.*：`src.mbc`, `src.parser`

### `src/mbc/native.py`

- 标准库/外部：`__future__`, `argparse`, `math`, `pathlib`, `struct`
- src.*：`src.mathlib`, `src.mbc`, `src.mbc.compiler`

### `src/mbc/native_regex.py`

- 标准库/外部：`__future__`, `struct`
- src.*：无

### `src/mbc/native_time.py`

- 标准库/外部：`__future__`, `struct`
- src.*：无

### `src/mbc/opcodes.py`

- 标准库/外部：`__future__`
- src.*：无

### `src/mbc/serial.py`

- 标准库/外部：`__future__`, `marshal`, `struct`
- src.*：`src.mbc`, `src.mbc.compiler`

### `src/mbc/vm.py`

- 标准库/外部：`__future__`, `math`, `operator`, `src`
- src.*：`src.kernel`, `src.kernel.errors`, `src.kernel.file_builtin`, `src.kernel.time_builtin`, `src.mathlib`, `src.mbc`, `src.mbc.compiler`, `src.regexlib`, `src.text_encoding`

### `src/parser.py`

- 标准库/外部：`__future__`, `enum`, `logging`, `re`, `src`, `typing`
- src.*：`src.lexer`, `src.tokens`

### `src/regexlib.py`

- 标准库/外部：`__future__`, `functools`
- src.*：无

### `src/text_encoding.py`

- 标准库/外部：`__future__`, `sys`, `typing`
- src.*：无

### `src/tokens.py`

- 标准库/外部：`enum`
- src.*：无

