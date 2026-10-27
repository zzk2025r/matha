"""Matha 执行门面 —— 主执行链的唯一对外入口（重构阶段 2 的前置件）。

背景：仓库里曾有四条并行执行路径（`src/interp.py` 树走式解释器、`src/vm.py`
MIR 栈式 VM、`m3v_vm.py`、以及 `convert(...)+exec()` 的转译执行）。它们语义不
一致、测试口径分散。本门面把「唯一主线」固定为

    lexer → parser → ast_nodes → mbc.compiler → mbc.vm

其余后端只能以显式 `mode` 注册进来，供诊断与调试使用，绝不进默认路径。

内核纪律（由 `scripts/dep_audit.py` + `tests/test_kernel_purity.py` 守门）：
  * 本文件不 import `src.domains.*`、`src.interp`，也不 import 任何第三方包；
  * 插件层只经由 `src.plugin_api`（联邦契约）接入，且只以对象注入的方式交给
    VM/Compiler 使用 —— 内核不认识插件的实现，只认识它的公开方法签名。

`plugins` 三种模式：
  "auto"   引用到未加载的领域符号时才 import 该插件（默认，取代旧的静默全量注册）
  "strict" 编译期即拒绝未加载的领域符号，并给出 `@：【加载领域】，X` 提示
  "off"    完全不接入插件层：只有内核内建与程序自身定义的名字可用
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

__all__ = [
    "run", "run_file", "run_expr", "compile_module", "build_exe", "run_checked",
    "run_file_checked", "run_expr_checked",
    "register_backend", "available_modes", "runnable_modes",
    "list_domains", "domain_symbol_index",
]

#: 内核自带后端；其余由遗留层显式注册（见 src/interp.py 末尾）。
_BACKENDS: dict[str, tuple[Callable[..., list], str]] = {}

_MODE_MBC = "vm"      # 唯一主线：mbc 字节码 VM
_MODE_NATIVE = "native"


# ============================================================
# 后端注册（遗留诊断后端由此进入，默认路径不受影响）
# ============================================================

def register_backend(mode: str, fn: Callable[..., list], *, description: str = "") -> None:
    """登记一个额外执行后端。`mode` 不得覆盖主线。"""
    if mode in (_MODE_MBC, _MODE_NATIVE):
        raise ValueError(f"后端名 {mode!r} 保留给核心主线")
    _BACKENDS[mode] = (fn, description)


def available_modes() -> dict[str, str]:
    """当前可用的执行后端 → 说明。"""
    out = {
        _MODE_MBC: "核心主线：mbc.compiler → mbc.vm",
        _MODE_NATIVE: "机器码发射（只产出 exe，不可用于 run；见 build_exe）",
    }
    out.update({k: v[1] for k, v in sorted(_BACKENDS.items())})
    return out


def runnable_modes() -> list[str]:
    """可在进程内执行的后端（供 CLI 作 `--backend` 候选）。

    `native` 不在其内：它只产出可执行文件，把它当执行后端会得到一个静默
    的空结果，不如直接从候选里去掉。
    """
    return [m for m in available_modes() if m != _MODE_NATIVE]


# ============================================================
# 插件层接入（只经 src.plugin_api 契约）
# ============================================================

def _resolver():
    """取默认插件解析器。清单驱动，调用本身不 import 任何领域模块。"""
    from src.plugin_api import get_resolver
    return get_resolver()


def kernel_symbol_names() -> set[str]:
    """内核已提供的符号名（数学/正则/时间/文件 + VM 基础原语）。

    编译期「未加载领域」诊断必须排除这些名字，否则 `tanh` 一类「插件恰好覆盖
    内核同名符号」的历史重名会被误报为不可用。
    """
    from src.kernel import register_kernel_builtins
    from src.mbc.vm import _default_builtins
    names = set(register_kernel_builtins({}))
    names.update(_default_builtins())
    return names


def domain_symbol_index(*, exclude_kernel: bool = True) -> dict[str, list[str]]:
    """符号 → 归属插件名列表（纯清单，不 import 领域模块）。"""
    exclude = kernel_symbol_names() if exclude_kernel else ()
    return _resolver().domain_symbol_index(exclude)


def plugin_wiring() -> tuple[dict[str, list[str]], dict[str, str]]:
    """供入编译器的两份纯数据：符号→插件归属、写法→插件名别名。"""
    r = _resolver()
    return r.domain_symbol_index(kernel_symbol_names()), r.domain_alias_map()


def list_domains() -> list[dict]:
    """枚举全部领域插件（名称/中文显示名/类别/符号数/是否已加载），零 import 成本。"""
    return _resolver().list_plugins()


# ============================================================
# 编译 / 运行
# ============================================================

def compile_module(source: str, *, plugins: str = "auto"):
    """编译源码为 mbc 模块；`plugins="strict"` 时启用未加载领域的编译期诊断。

    命名不叫 `compile`：避免遮住宿主内建 `compile()`（内核不得借转译执行，见
    `tests/test_kernel_purity.py`）。
    """
    from src.mbc.compiler import compile_source
    index = aliases = None
    if plugins == "strict":
        index, aliases = plugin_wiring()
    elif plugins not in ("auto", "off"):
        raise ValueError(f"未知 plugins 模式 {plugins!r}（auto | strict | off）")
    return compile_source(source, plugin_index=index, domain_aliases=aliases)


def build_exe(source: str, out_path: str | Path) -> Path:
    """走 `mbc.native` 发射机器码并写入可执行文件（唯一真实的机器码路径）。

    没有实现“模拟成功”：发射失败时直接抛出，不伪装成已编译。
    """
    from src.mbc.native import compile_to_exe
    exe = compile_to_exe(source)
    out = Path(out_path)
    out.write_bytes(exe)
    return out


def run(source: str, mode: str = _MODE_MBC, *, plugins: str = "auto",
        verbose: bool = False) -> list[Any]:
    """执行一段 Matha 源码，返回输出列表（`输出`/`print` 收集到的行）。"""
    if mode == _MODE_MBC:
        return _run_mbc(source, plugins=plugins, verbose=verbose)
    if mode == _MODE_NATIVE:
        raise RuntimeError(
            "mode='native' 不是一种执行后端：机器码只产出可执行文件，不在进程内跑。"
            "请改用 build_exe(source, out) 后再执行生成的文件。")
    backend = _BACKENDS.get(mode)
    if backend is None:
        raise ValueError(f"未知执行后端 {mode!r}；可用：{', '.join(available_modes())}")
    return backend[0](source)


def run_checked(source: str, mode: str = _MODE_MBC, *, plugins: str = "auto",
                verbose: bool = False) -> tuple[list[Any], BaseException | None]:
    """执行并返回 (已产生的输出, 错误)；错误不抛出。

    存在理由：未捕获错误之前的输出也是可观察行为（`输出("before")` 后紧跟除零），
    黄金测试要逐字节锁定这部分，不能因为抱错就丢掉已有输出。
    与 `run()` 的区别只在是否重新抛出。
    """
    if mode != _MODE_MBC:
        try:
            return run(source, mode, plugins=plugins, verbose=verbose), None
        except BaseException as e:  # noqa: BLE001
            return [], e
    from src.mbc.vm import VM
    try:
        mod = compile_module(source, plugins=plugins)
    except BaseException as e:  # noqa: BLE001
        return [], e
    vm = VM(mod, verbose=verbose)
    if plugins != "off":
        vm.domain_resolver = _resolver()
    try:
        return list(vm.run()), None
    except BaseException as e:  # noqa: BLE001
        return list(vm.outputs), e


def _run_mbc(source: str, *, plugins: str = "auto", verbose: bool = False) -> list[Any]:
    from src.mbc.vm import VM
    mod = compile_module(source, plugins=plugins)
    vm = VM(mod, verbose=verbose)
    if plugins != "off":
        vm.domain_resolver = _resolver()
    return vm.run()


def run_file(path: str | Path, mode: str = _MODE_MBC, *, plugins: str = "auto",
             verbose: bool = False) -> list[Any]:
    """运行一个 `.matha` 源文件（或已编译的 `.mbc` 字节码）。"""
    p = Path(path)
    if p.suffix == ".mbc":
        return _run_mbc_module(p, plugins=plugins, verbose=verbose)
    return run(p.read_text(encoding="utf-8"), mode, plugins=plugins, verbose=verbose)


def run_file_checked(path: str | Path, mode: str = _MODE_MBC, *, plugins: str = "auto",
                     verbose: bool = False) -> tuple[list[Any], BaseException | None]:
    """`run_file` 的不抛版本：返回 (已产生的输出, 错误)。

    CLI 入口用它：`输出(...)` 在运行时报错之前已经发生的就是可观察行为，
    一并丢掉会把“已打印的行”变成静默失败。
    """
    p = Path(path)
    if p.suffix != ".mbc":
        return run_checked(p.read_text(encoding="utf-8"), mode,
                           plugins=plugins, verbose=verbose)
    from src.mbc import read_mbc
    from src.mbc.vm import VM
    try:
        mod = read_mbc(str(p))
    except BaseException as e:  # noqa: BLE001
        return [], e
    vm = VM(mod, verbose=verbose)
    if plugins != "off":
        vm.domain_resolver = _resolver()
    try:
        return list(vm.run()), None
    except BaseException as e:  # noqa: BLE001
        return list(vm.outputs), e


def _run_mbc_module(p: Path, *, plugins: str = "auto", verbose: bool = False) -> list[Any]:
    from src.mbc import read_mbc
    from src.mbc.vm import VM
    vm = VM(read_mbc(str(p)), verbose=verbose)
    if plugins != "off":
        vm.domain_resolver = _resolver()
    return vm.run()


def run_expr(expr: str, mode: str = _MODE_MBC, *, plugins: str = "auto") -> list[Any]:
    """求值单行表达式并打印结果（`matha eval` 的语义）。"""
    return run(_wrap_expr(expr), mode, plugins=plugins)


def run_expr_checked(expr: str, mode: str = _MODE_MBC,
                     *, plugins: str = "auto") -> tuple[list[Any], BaseException | None]:
    """`run_expr` 的不抛版本（错误前的输出同样入账）。"""
    return run_checked(_wrap_expr(expr), mode, plugins=plugins)


def _wrap_expr(expr: str) -> str:
    """把孤立表达式包装成一个会输出 `result` 的最小 Matha 程序。"""
    return f"result = {expr}\n#1：[result]"
