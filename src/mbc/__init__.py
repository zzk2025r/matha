"""M3V 字节码工具链：Matha 源码 → .mbc 二进制 → 栈式 VM 执行。"""
from src.mbc.compiler import (
    Compiler,
    MFunction,
    MModule,
    compile_program,
    compile_source,
)
from src.mbc.serial import read_mbc, write_mbc
from src.mbc.vm import VM, Box, Closure, Frame, Partial, run_module, run_source

__all__ = [
    "Compiler", "MModule", "MFunction", "compile_program", "compile_source",
    "VM", "Box", "Closure", "Partial", "Frame", "run_module", "run_source",
    "write_mbc", "read_mbc",
]
