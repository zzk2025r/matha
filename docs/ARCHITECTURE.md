# Matha 架构现状（v4.6.0）

> 本文件描述**代码现在长什么样**，不是路线图，也不是成绩单。
> 所有数字来自 `python scripts/repo_facts.py`；所有门禁由 `make check`
> （= `python scripts/check.py`）判定，对外只产出**一个**通过率。
> 历史文档（118 份一次性报告）在 [`history/`](history/)，不作为现状依据。

## 一、唯一核心主线

```
src/lexer.py → src/parser.py → src/ast_nodes.py
      → src/mbc/compiler.py → src/mbc/vm.py        ← 默认执行
                                  └→ src/mbc/native.py → plugins/toolchain_msvc → 真实 exe ← 唯一机器码路径
```

- `src/mbc/opcodes.py`：指令码定义（33 条，VM 全分派、native 全发射）。
- `src/mbc/cli.py`：`compile_source → run_module` 统一入口，`repl.py` /
  `matha_main.py` / `exec_api` 都走它，不再有第二条执行链。
- **已删除的转译执行路径**：`convert(source,"matha","python") + exec()`。
- **已归档的第三条 VM**：`src/vm.py`（MIR 栈式 VM）已移为
  `src/plugins/legacy_mir_vm.py`，只能显式 `from src.plugins.legacy_mir_vm import MathaVM`
  使用，不在默认路径、不进文档宣传；`src/m3v_vm.py`（重复实现，内含坏导入
  `import compiler_matha`）已删除。
- `src/mir.py` / `src/mir_opt.py` 只作优化分析 IR，**不承担执行**。
- `src/interp.py`（4k+ 行）降级为诊断后端：执行轨迹 / 单步调试，
  经 `src/kernel/exec_api.py::run(source, mode=...)` 显式选择（`--backend=legacy-interp`
  仅测试与调试可见）。全仓库 `src.interp` 的引用已改指门面。

核心体量：`src/lexer.py + src/parser.py + src/ast_nodes.py + src/kernel/ + src/mbc/`
共 **30,870 行**（`repo_facts.core_py_lines`）。

## 二、L1 纯净内核与 import 白名单

内核 = `src/lexer.py`、`src/parser.py`、`src/ast_nodes.py`、`src/kernel/`、`src/mbc/`。

**允许**（标准库）：`math struct json re os sys io enum dataclasses typing logging
functools unicodedata textwrap heapq datetime importlib`。

**禁止**：`sympy numpy scipy numba tree_sitter ctypes cffi subprocess`、
`threading concurrent socket multiprocessing`，以及 `src.domains.*`、
`src.interp`、`src.stdlib.*`。

`mbc/native.py` 生成的 exe 调用 CRT（`_ecvt/rint/pow/fopen`）属 OS ABI 依赖，
不是 Python 依赖，明确不计为违规。

机器强制：
- [`tests/test_kernel_purity.py`](../tests/test_kernel_purity.py) —— AST 静态解析核心文件，白名单外 import 即 fail；
  并检查核心目录 `subprocess/threading/concurrent/socket/ctypes` 出现次数为 0（验收标准 1/2）。
- [`scripts/dep_audit.py`](../scripts/dep_audit.py) → 产出 [`DEP_BASELINE.md`](DEP_BASELINE.md)（依赖方向图 + 违规清单 + 插件越界）。

内核内建（`src/kernel/register_kernel_builtins()`）只有五组，全部纯标准库：
`src/kernel/math_builtin.py`（数学 + 单位换算，原 `src/mathlib.py`）、
`src/kernel/regex_builtin.py`（原 `src/regexlib.py`）、
`src/kernel/time_builtin.py`、`src/kernel/file_builtin.py`、`src/kernel/errors.py`。
> 修复点：原先 `src/mbc/vm.py` 的 `_default_builtins()` 里有一句
> `from src.domains.time_module import _register_time` —— 内核反向依赖领域层，
> 现由 `src/kernel/time_builtin.py` 承担。

## 三、符号能力：内核纯实现 + Matha 标准库

| 层 | 位置 | 角色 |
|---|---|---|
| stage0 引导实现 | `src/kernel/symbolic/`（expr/diff/integrate/simplify/limit/ode/series/domain/latex） | 纯标准库；CLI 不再默认走它，只作对拍基准 |
| Matha 标准库 | [`matha/library/*.matha`](../matha/library/)（calculus_diff → algebra_simplify → calculus_limit → calculus_series） | **CLI 默认路径**，由 mbc VM 编译执行 |
| 装载器 / 门面 | `src/stdlib/matha_symbolic.py` + `src/stdlib/calculus_symbolic.py` | Expr↔tagged 互转、`backend=auto|matha|stage0` 路由与回退记账 |

能力对照与缺口：[`symbolic_parity.md`](symbolic_parity.md)、
[`matha_stdlib_symbolic.md`](matha_stdlib_symbolic.md)。
`sympy` 已降为 `optional-dependencies.accelerated`，核心安装零第三方依赖。

## 四、插件层（联邦式）

- 契约：[`src/plugin_api.py`](../src/plugin_api.py) —— `MathaPlugin`（`name` /
  `exports()` / `arities` / `on_load(ctx)`）+ `PluginContext`（只暴露
  `register_builtin` / `register_formula` / `emit_diagnostic`，**禁止访问
  `vm.frames`/`vm.globals`/`_stack`**，由 `test_kernel_purity.py` 同思路静态守卫）。
- 适配层把历史 `_register_xxx(builtins: dict)` 签名统一包成 `exports()`，
  84 个 `src/domains/*.py` 中的 **82 个领域插件**零改写接入
  （`__init__.py` / `registry.py` 不是插件）。
- 清单：`src/domains/manifest.json`（`protocol_version = 1`，82 插件、0 不可用）。
  `src/semantic.py` 已改为读该静态清单，不再 import 6 个领域模块。
- **懒加载**：`exec_api.compile_module(..., plugins="auto|strict|off")`；
  未 `@：【加载领域】` 就引用领域符号 → 编译期诊断并列出候选插件名。
  验证：`tests/test_plugin_contract.py`（含子进程取证「只加载需要的那个」）。
- **第三方重后端只在调用那一刻 import**：`src/domains/symbolic_calculus.py`
  是这条纪律的样板 —— `integrate` 先问纯标准库内核引擎 `src/kernel/symbolic/`，
  只有内核返回 None（能力缺口，如 ∫e^(-x²)dx）才在函数体内 `import sympy`；
  顶层 import 一律禁止。验证：`tests/test_plugin_load.py` +
  `tests/test_plugin_load.matha`（`x = 符号原子("x")` 后 `integrate(x^2, x)` →
  `x**3/3`，这一条内核引擎就能答，全程不碰 sympy）。
- **插件命名卫生**（机器强制，见 `tests/test_plugin_contract.py` 第六节）：插件
  不得导出裸单字母符号，也不得与 `matha/*.matha`、`matha/library/**` 的顶层声明
  同名。原因：物化插件执行 `target.update(table)`（同名即覆盖），而清单符号名会经
  `LazyBuiltinTable.__contains__` 在全进程生效 —— 导出 `x` 会改掉「未定义名即报错」
  的内核契约，导出 `符号` 会抬掉 `stdlib_symbols.matha` 的自举符号表构造函数。
- 重型/逃逸能力全部外移：`src/plugins/`（14 个）——
  `numpy_accel` / `deps_probe` / `ffi` / `ffi_sdk` / `interop` / `device_config` /
  `tree_sitter_backends` / `tree_sitter_cext` / `parallel_parser` /
  `toolchain_llvm` / `toolchain_msvc` / `toolchain_signature` / `legacy_mir_vm`。
  核心解析单线程确定（`threading`/`concurrent.futures` 已移出 `src/parser.py`）。
- **消除静默假成功**：外部工具链不可用 → 显式失败 + 诊断，不再 `mode:"simulated"`
  冒充成功（`src/compiler/llvm_hybrid.py`；原 `src/mbc/native_link.py` 已移出内核
  删除，职责由 `src/plugins/toolchain_msvc.py` 承接，它无论环境如何都落一个 exe
  的旧行为已改为真失败）。

## 五、门禁与唯一口径

| 门禁 | 判据 |
|---|---|
| `tests/` | 56 个测试文件（全量见最近一次 `make check`） |
| `kernel_purity` | 白名单 + 核心无逃逸模块 + 插件不得碰 VM 私有面 |
| `ast_vm_gap` | 78 个 AST 节点、59 发射 / 19 有意无码 / **0 不认识**、**0 阻塞缺口**；指令码 33/33/33 |
| `golden` | 18 例 vm ↔ interp 逐字节；`--native` 追加真 exe 对拍（已知未实现 2 例显式列在 `golden_tests/manifest.json`） |
| `dep_audit` | 违规 0 条、插件越界 0 条 |
| `matha_stdlib_symbolic` | 阶段 4 逐位对拍 + 偏差双向锁定 + 缺口显式失败（107 项） |

```bash
make check          # 含 vm↔native 机器码对拍
make check-lite     # 本机无 nasm/link 时用
```

## 六、兼容承诺（未被重构破坏）

- 符号体系不删：`？ #： 【*/ */ @： >> []`（语句位单元素 `[x]` 是**打印括号**，
  列表字面量请用两元素形式或 `包(x)`，详见 [`ast_vm_gap.md`](ast_vm_gap.md) 第九节）。
- `matha/**/*.matha`（158 个）、`examples/` 全部保留；
  `matha/library|knowledge|resource/` 属标准库/扩展包，不内置内核。
- 82 个领域模块全部保留为插件，未加载时不产生 import 成本。
