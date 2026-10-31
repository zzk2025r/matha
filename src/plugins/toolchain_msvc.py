# -*- coding: utf-8 -*-
"""toolchain_msvc —— 可选 MSVC/NASM 外部工具链插件（``nasm`` + ``link``）。

承接原 ``src/mbc/native_link.py``（已移出内核并删除）的职责：把
``src.mbc.native.X86Emitter`` 发射出的机器码导出为 NASM 文本，并在环境确实
装有 ``nasm``/``link`` 时汇编成 obj。该路径**不在主链上**：主链的真实机器码
产物由 ``src.mbc.native`` 自行写 PE，不需要任何外部汇编器/链接器。

**没有静默假成功**：旧 ``native_link_exe`` 无论环境如何都会落一个
``*.link.json`` 并标 ``mode:"simulated"``，让调用方误认为已产出 exe。现改为
工具缺失即抛 :class:`ToolchainUnavailable`；导出汇编文本用显式命名的
:func:`dump_asm`，不冒充链接产物。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

__all__ = [
    "ToolchainUnavailable",
    "TOOLS",
    "available",
    "describe_availability",
    "generate_x86_64_asm",
    "dump_asm",
    "assemble_obj",
]

TOOLS: dict[str, str] = {
    "nasm": "安装 NASM（https://www.nasm.us/pub/nasm/releasebuilds/）并加入 PATH"
            "（Windows 上默认路径 C:\\nasm\\asm.exe），验证：nasm -v",
    "link": "link.exe 属 MSVC 工具链，需安装 Visual Studio Build Tools 并在"
            "「开发者命令提示」中启动进程，验证：link /NOLOGO /VERSION",
}

_NASM_TIMEOUT = 60.0
#: nasm 的额外候选路径（历史实现硬编码 C:\nasm\asm.exe，保留兼容）
_NASM_FALLBACKS: tuple[str, ...] = (r"C:\nasm\asm.exe",)


class ToolchainUnavailable(RuntimeError):
    """外部汇编/链接工具链缺失或调用失败（显式失败，不生成伪造 exe）。"""

    def __init__(self, message: str, *, detail: str = "") -> None:
        super().__init__(message if not detail else f"{message}\n{detail}")
        self.detail = detail


def available() -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for name in TOOLS:
        found = shutil.which(name)
        if found is None and name == "nasm":
            found = next((p for p in _NASM_FALLBACKS if os.path.exists(p)), None)
        out[name] = found
    return out


def describe_availability() -> str:
    found = {k: v for k, v in available().items() if v}
    if len(found) == len(TOOLS):
        return "MSVC/NASM 工具链就绪：" + "、".join(f"{k}={v}" for k, v in found.items())
    return "MSVC/NASM 工具链缺失：" + "、".join(k for k in TOOLS if k not in found)


def generate_x86_64_asm(emitter, label_prefix: str = "matha") -> str:
    """将发射器缓冲转换为简化 NASM 风格汇编（便于人工检查，不保证可汇编）。

    ``emitter`` 为 ``src.mbc.native.X86Emitter``（鸭子类型：只用 ``labels``/``buf``，
    故本插件不 import 内核，方向保持「插件 → 内核」）。
    """
    lines = ["; Matha MBC -> x86-64 (NASM syntax, Win64)", "bits 64",
             "default rel", "section .text"]
    for name in sorted(emitter.labels.keys()):
        lines.append(f"{label_prefix}_{name}:")
        lines.append(f"    ; RVA 0x{emitter.labels[name]:X}")
    lines.append(f"; code bytes: {len(emitter.buf)}")
    return "\n".join(lines) + "\n"


def dump_asm(emitter, asm_path: str | None = None,
             label_prefix: str = "matha") -> str:
    """导出汇编文本并返回其路径。诊断用，**不**声称生成了可执行文件。"""
    asm_path = asm_path or os.path.join(tempfile.mkdtemp(prefix="matha_mbc_"),
                                        "out.asm")
    with open(asm_path, "w", encoding="utf-8") as f:
        f.write(generate_x86_64_asm(emitter, label_prefix))
    return asm_path


def assemble_obj(emitter, obj_path: str | None = None,
                 asm_path: str | None = None) -> str:
    """``nasm -f win64`` 汇编为 obj；工具缺失或失败一律抛错。"""
    nasm = available()["nasm"]
    if nasm is None:
        raise ToolchainUnavailable("外部工具缺失：nasm（不生成伪造 obj/exe）",
                                   detail=TOOLS["nasm"])
    asm_path = dump_asm(emitter, asm_path)
    obj_path = obj_path or os.path.splitext(asm_path)[0] + ".obj"
    try:
        proc = subprocess.run([nasm, "-f", "win64", asm_path, "-o", obj_path],
                              capture_output=True, text=True, timeout=_NASM_TIMEOUT)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise ToolchainUnavailable(f"nasm 调用失败：{exc}", detail=TOOLS["nasm"]) from exc
    if proc.returncode != 0 or not os.path.exists(obj_path):
        raise ToolchainUnavailable(
            f"nasm 汇编失败（退出码 {proc.returncode}）",
            detail=(proc.stderr or proc.stdout or "").strip())
    return obj_path
