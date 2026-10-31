# -*- coding: utf-8 -*-
"""toolchain_llvm —— 可选 LLVM 外部工具链插件（``llc`` / ``clang``）。

内核主链（lexer → parser → ast_nodes → mbc.compiler → mbc.vm[/mbc.native]）
**不调用任何外部进程**：机器码发射只承认 ``src.mbc.native`` 一条真实路径。
LLVM 后端属外部工具链，故独立成插件，按需加载（本模块 import 即触发
``subprocess``，主链永不 import 它）。

**没有静默假成功**（重构红线）：工具缺失或调用失败一律抛
:class:`ToolchainUnavailable` 并附诊断信息，绝不返回伪造的 exe 路径，
也绝不返回「模拟」出来的执行结果。旧实现里 ``MathaBackend.compile`` 在
``llc``/``clang`` 缺失时返回空串、``llvm_hybrid.SimulatedLLVMBackend`` 甚至
把「正则扫常量再相加」当作编译产物 —— 两者都会让上层把假产物当成功，已废除。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

__all__ = [
    "ToolchainUnavailable",
    "TOOLS",
    "INFO_TOOLS",
    "available",
    "describe_availability",
    "version_report",
    "compile_llvm",
    "run_exe",
]

#: 需要的工具名 → 安装指引（诊断信息直接面向用户）
TOOLS: dict[str, str] = {
    "llc": "安装 LLVM（https://github.com/llvm/llvm-project/releases）后把 "
           "bin 目录加入 PATH，验证：llc --version",
    "clang": "安装 clang（https://releases.llvm.org/download.html）并加入 PATH，"
             "验证：clang --version",
}

_CHECK_TIMEOUT = 5.0
_COMPILE_TIMEOUT = 60.0
_LINK_TIMEOUT = 30.0
_RUN_TIMEOUT = 30.0

#: `matha info` 需要展示版本的工具（比编译所需的 TOOLS 宽）
INFO_TOOLS: tuple[str, ...] = ("llc", "clang", "opt", "llvm-as")


class ToolchainUnavailable(RuntimeError):
    """外部 LLVM 工具链缺失或调用失败（显式失败，不降级为假成功）。"""

    def __init__(self, message: str, *, detail: str = "") -> None:
        super().__init__(message if not detail else f"{message}\n{detail}")
        self.detail = detail


def available() -> dict[str, str | None]:
    """返回 {工具名: 可执行文件路径或 None}（只查 PATH，不启动进程）。"""
    return {name: shutil.which(name) for name in TOOLS}


def describe_availability() -> str:
    found = {k: v for k, v in available().items() if v}
    if len(found) == len(TOOLS):
        return "LLVM 工具链就绪：" + "、".join(f"{k}={v}" for k, v in found.items())
    missing = [k for k in TOOLS if k not in found]
    return "LLVM 工具链缺失：" + "、".join(missing)


def version_report() -> dict[str, str]:
    """{工具名: 版本首行 或 "未找到"}，供 `matha info` 使用。

    子进程只发生在本插件内（阶段 3 第 5 项）：CLI 与内核不再直接
    `subprocess.run(["llc", "--version"])`。
    """
    report: dict[str, str] = {}
    for tool in INFO_TOOLS:
        try:
            proc = subprocess.run([tool, "--version"], capture_output=True,
                                  text=True, timeout=_CHECK_TIMEOUT)
            lines = (proc.stdout or "").splitlines()
            report[tool] = lines[0].strip() if proc.returncode == 0 and lines else "未找到"
        except (OSError, subprocess.SubprocessError):
            report[tool] = "未找到"
    return report


def _require(*names: str) -> None:
    missing = [n for n in names if shutil.which(n) is None]
    if missing:
        hints = "\n".join(TOOLS[n] for n in missing if n in TOOLS)
        raise ToolchainUnavailable(
            f"外部工具缺失：{'、'.join(missing)}（本插件不会以模拟产物代替真实编译）",
            detail=hints)


def _invoke(cmd: list[str], timeout: float, *, allow_fail: bool = False
            ) -> subprocess.CompletedProcess:
    """执行外部命令；FileNotFoundError 同样归一为 ToolchainUnavailable。"""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        raise ToolchainUnavailable(f"外部命令不可用：{cmd[0]}", detail=str(exc)) from exc
    except subprocess.TimeoutExpired as exc:
        raise ToolchainUnavailable(
            f"外部命令超时（{timeout}s）：{' '.join(cmd)}") from exc
    if proc.returncode != 0 and not allow_fail:
        raise ToolchainUnavailable(
            f"外部命令失败（退出码 {proc.returncode}）：{' '.join(cmd)}",
            detail=(proc.stderr or proc.stdout or "").strip())
    return proc


def compile_llvm(llvm_ir: str, output_name: str = "matha_out") -> str:
    """LLVM IR 文本 → 原生可执行文件，返回 exe 路径。

    与旧实现的行为差异（刻意为之）：
      * 工具缺失 → :class:`ToolchainUnavailable`（旧实现返回 ``""``，上层当成功）
      * ``llc`` 失败后回退 ``clang`` 属**同一工具链内部**的备选路径，保留；
        两条都失败则抛出，附 stderr 诊断。
    """
    _require("llc", "clang")
    ll_fd, ll_file = tempfile.mkstemp(suffix=".ll", prefix="matha_")
    obj_file = ll_file + ".o"
    exe_file = f"{output_name}.exe"
    try:
        with os.fdopen(ll_fd, "w", encoding="utf-8") as f:
            f.write(llvm_ir)
        proc = _invoke(["llc", "-O2", ll_file, "-o", obj_file], _COMPILE_TIMEOUT,
                       allow_fail=True)
        if proc.returncode != 0:
            proc = _invoke(["clang", "-O2", "-c", ll_file, "-o", obj_file],
                           _COMPILE_TIMEOUT, allow_fail=True)
        if proc.returncode != 0:
            raise ToolchainUnavailable(
                "llc/clang 均无法把 LLVM IR 编成目标文件",
                detail=(proc.stderr or proc.stdout or "").strip())
        proc = _invoke(["clang", obj_file, "-o", exe_file], _LINK_TIMEOUT,
                       allow_fail=True)
        if proc.returncode != 0:
            raise ToolchainUnavailable(
                "链接失败（clang <obj> -o exe）",
                detail=(proc.stderr or proc.stdout or "").strip())
        return exe_file
    finally:
        for p in (ll_file, obj_file):
            if os.path.exists(p):
                try:
                    os.unlink(p)
                except OSError:      # 临时文件清理失败不影响编译结论
                    pass


def run_exe(exe_path: str, args: list | None = None) -> subprocess.CompletedProcess:
    """运行**真实**产物。路径为空或不存在即报错——不返回 0 码的伪造输出。"""
    if not exe_path or not os.path.exists(exe_path):
        raise ToolchainUnavailable(f"可执行文件不存在：{exe_path!r}")
    try:
        return subprocess.run([exe_path] + list(args or []),
                              capture_output=True, text=True, timeout=_RUN_TIMEOUT)
    except OSError as exc:
        raise ToolchainUnavailable(f"无法运行产物 {exe_path}", detail=str(exc)) from exc
