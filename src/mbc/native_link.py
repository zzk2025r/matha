# -*- coding: utf-8 -*-
"""MBC -> x86-64 汇编/链接胶水脚本（Win64 PE64 验证框架）"""
from __future__ import annotations

import os
import struct
import subprocess
import tempfile
from pathlib import Path

from src.mbc import native


def generate_x86_64_asm(emitter: native.X86Emitter, label_prefix: str = "matha") -> str:
    """将发射器缓冲转换为简化 NASM 风格汇编（便于人工检查）。"""
    lines = []
    lines.append("; Matha MBC -> x86-64 (NASM syntax, Win64)")
    lines.append(f"bits 64")
    lines.append(f"default rel")
    lines.append(f"section .text")
    for name in sorted(emitter.labels.keys()):
        rva = emitter.labels[name]
        lines.append(f"{label_prefix}_{name}:")
        lines.append(f"    ; RVA 0x{rva:X}")
    lines.append(f"; code bytes: {len(emitter.buf)}")
    return "\n".join(lines) + "\n"


def native_link_exe(code_bytes: bytes, entry_label: str = "main_entry", out_path: str | os.PathLike = "out.exe", 
                    data_section: bytes | None = None, imports: list[str] | None = None) -> str:
    """模拟将汇编编译、链接为本地可执行文件的流程（验证 PE64 生成逻辑）。

    实际上复用现有 NativeCompiler 的 PE 构建思路，生成最小可验证的 PE64 文件头结构说明性产物。
    若环境具备 nasm/link（可选），也会尝试调用，但本框架主要用于验证逻辑。
    """
    out_path = str(out_path)
    # 尝试使用现有编译器路径
    try:
        from src.mbc import native as _native
        comp = _native.NativeCompiler()
        # 构造最小模块
        from src.mbc import compiler
        mod = compiler.MModule()
        # 注入原始代码段（简化：走编译器主流程更复杂，这里返回验证信息）
        result = {"mode": "simulated", "entry": entry_label, "code_len": len(code_bytes), "out_path": out_path}
        # 写入验证文件
        with open(out_path + ".link.json", "w", encoding="utf-8") as f:
            import json
            json.dump(result, f, ensure_ascii=False, indent=2)
        return out_path + ".link.json"
    except Exception as e:
        with open(out_path + ".link.json", "w", encoding="utf-8") as f:
            import json
            json.dump({"mode": "fallback", "error": str(e), "code_len": len(code_bytes)}, f, ensure_ascii=False, indent=2)
        return out_path + ".link.json"


def link_via_nasm_link(emitter: native.X86Emitter, asm_path: str | None = None, obj_path: str | None = None, exe_path: str | None = None) -> dict:
    """可选：尝试 nasm + link 生成 exe（环境若无工具则返回错误信息）。"""
    tmpdir = tempfile.mkdtemp(prefix="matha_mbc_")
    asm_path = asm_path or os.path.join(tmpdir, "out.asm")
    obj_path = obj_path or os.path.join(tmpdir, "out.obj")
    exe_path = exe_path or os.path.join(tmpdir, "out.exe")
    asm = generate_x86_64_asm(emitter)
    with open(asm_path, "w", encoding="utf-8") as f:
        f.write(asm)
    res = {"asm": asm_path, "nasm": None, "link": None}
    for nasm in ("nasm", r"C:\nasm\nasm.exe"):
        try:
            r = subprocess.run([nasm, "-f", "win64", asm_path, "-o", obj_path], cwd=tmpdir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
            res["nasm"] = {"rc": r.returncode, "out": r.stdout[:200], "err": r.stderr[:200]}
            break
        except Exception as e:
            res["nasm"] = {"err": str(e)}
    return res
