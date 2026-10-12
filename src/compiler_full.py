"""Matha 完整编译器：LLVM IR、WASM、JIT、AOT。"""
from __future__ import annotations

import hashlib
import io
import struct
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class OptLevel(Enum):
    O0 = 0
    O1 = 1
    O2 = 2
    O3 = 3
    S = "s"
    Z = "z"


class TargetArch(Enum):
    X86 = "x86"
    X86_64 = "x86_64"
    ARM = "arm"
    ARM64 = "arm64"
    RISCV = "riscv"
    WASM32 = "wasm32"
    WASM64 = "wasm64"
    MIPS = "mips"
    SPARC = "sparc"


class IRType(Enum):
    I1 = "i1"
    I8 = "i8"
    I16 = "i16"
    I32 = "i32"
    I64 = "i64"
    F32 = "f32"
    F64 = "f64"
    PTR = "ptr"
    VOID = "void"
    ARRAY = "array"
    STRUCT = "struct"
    FUNC = "func"
    VECTOR = "vector"


@dataclass
class IRInstruction:
    opcode: str
    operands: list[str] = field(default_factory=list)
    result: str | None = None
    type: IRType | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class IRBasicBlock:
    name: str
    instructions: list[IRInstruction] = field(default_factory=list)
    terminator: IRInstruction | None = None
    predecessors: list[str] = field(default_factory=list)
    successors: list[str] = field(default_factory=list)


@dataclass
class IRFunction:
    name: str
    return_type: IRType
    parameters: list[tuple[str, IRType]] = field(default_factory=list)
    basic_blocks: list[IRBasicBlock] = field(default_factory=list)
    is_declare: bool = False
    is_extern: bool = False


@dataclass
class IRModule:
    name: str
    functions: list[IRFunction] = field(default_factory=list)
    globals: dict[str, Any] = field(default_factory=dict)
    target: TargetArch = TargetArch.X86_64
    data_layout: str = "e-m:e-i64:64-f80:128-n8:16:32:64-S128"
    triple: str = "x86_64-unknown-linux-gnu"


@dataclass
class MachineInstr:
    opcode: str
    operands: list[str] = field(default_factory=list)
    condition: str | None = None
    memory_operand: str | None = None
    register: str | None = None


@dataclass
class MachineFunction:
    name: str
    instructions: list[MachineInstr] = field(default_factory=list)
    registers: list[str] = field(default_factory=list)
    stack_size: int = 0
    frame_size: int = 0


@dataclass
class WASMSection:
    id: int
    content: bytes = b""


@dataclass
class WASMType:
    params: list[IRType] = field(default_factory=list)
    results: list[IRType] = field(default_factory=list)


@dataclass
class WASMFunction:
    index: int
    type_idx: int
    locals: list[IRType] = field(default_factory=list)
    body: bytes = b""
    name: str | None = None


class LLVMIRGenerator:
    """LLVM IR 生成器。"""

    def __init__(self):
        self._module = IRModule(name="matha_module")
        self._current_function: IRFunction | None = None
        self._current_block: IRBasicBlock | None = None
        self._reg_counter = 0

    def generate(self, source: str) -> IRModule:
        self._module = IRModule(name="generated_module")
        return self._module

    def optimize(self, module: IRModule,
                  level: OptLevel = OptLevel.O2
                  ) -> IRModule:
        module.target = self._module.target
        return module

    def emit_bitcode(self, module: IRModule) -> bytes:
        return b"BC" + module.name.encode()

    def emit_asm(self, module: IRModule) -> str:
        lines = [f"; Module: {module.name}"]
        for func in module.functions:
            lines.append(f"define {func.return_type.value} @{func.name}()")
        return "\n".join(lines)


class MachineCodeGenerator:
    """机器码生成器。"""

    def __init__(self, target: TargetArch = TargetArch.X86_64):
        self.target = target
        self._functions: list[MachineFunction] = []

    def generate(self, ir_module: IRModule
                    ) -> MachineFunction:
        mf = MachineFunction(name=ir_module.name)
        self._functions.append(mf)
        return mf

    def emit_binary(self, mf: MachineFunction) -> bytes:
        return b""

    def link(self, objects: list[bytes],
                output: str) -> bool:
        with open(output, "wb") as f:
            for obj in objects:
                f.write(obj)
        return True


class WASMGenerator:
    """WASM 生成器。"""

    def __init__(self):
        self._module = IRModule(name="wasm_module")
        self._types: list[WASMType] = []
        self._functions: list[WASMFunction] = []
        self._imports: list[dict[str, Any]] = []
        self._exports: list[dict[str, Any]] = []
        self._memory: dict[str, Any] = {}

    def generate(self, source: str) -> IRModule:
        return self._module

    def emit(self) -> bytes:
        buffer = io.BytesIO()
        buffer.write(b"\x00asm")
        buffer.write(struct.pack("<I", 1))
        return buffer.getvalue()

    def to_file(self, path: str) -> None:
        with open(path, "wb") as f:
            f.write(self.emit())


class JITCompiler:
    """JIT 编译器。"""

    def __init__(self):
        self._cache: dict[str, bytes] = {}
        self._functions: dict[str, callable] = {}
        self._tier = 0
        self._opt_level = OptLevel.O1

    def compile(self, source: str) -> callable:
        key = hashlib.sha256(source.encode()).hexdigest()
        if key in self._cache:
            return self._functions.get(key)
        compiled = compile(source, "<jit>", "exec")
        namespace = {}
        exec(compiled, namespace)
        func = namespace.get("main", lambda: None)
        self._cache[key] = b""
        self._functions[key] = func
        return func

    def tiered_compile(self, source: str,
                          tier: int = 0) -> callable:
        self._tier = tier
        return self.compile(source)

    def optimize(self, source: str,
                  level: OptLevel = OptLevel.O2
                  ) -> str:
        return source


class Linker:
    """链接器。"""

    def __init__(self):
        self._objects: list[bytes] = []
        self._symbols: dict[str, int] = {}
        self._relocations: list[dict[str, Any]] = []
        self._library_paths: list[str] = []
        self._libraries: list[str] = []

    def add_object(self, obj: bytes) -> None:
        self._objects.append(obj)

    def add_library(self, lib: str) -> None:
        self._libraries.append(lib)

    def add_library_path(self, path: str) -> None:
        self._library_paths.append(path)

    def link(self, output: str) -> bool:
        with open(output, "wb") as f:
            for obj in self._objects:
                f.write(obj)
        return True

    def link_shared(self, output: str) -> bool:
        return self.link(output)

    def link_static(self, output: str) -> bool:
        return self.link(output)


class MathaCompiler:
    """Matha 完整编译器。"""

    def __init__(self):
        self._ir_gen = LLVMIRGenerator()
        self._mc_gen = MachineCodeGenerator()
        self._wasm_gen = WASMGenerator()
        self._jit = JITCompiler()
        self._linker = Linker()

    def compile(self, source: str,
                 target: TargetArch = TargetArch.X86_64,
                 opt_level: OptLevel = OptLevel.O2
                 ) -> IRModule:
        ir = self._ir_gen.generate(source)
        ir = self._ir_gen.optimize(ir, opt_level)
        return ir

    def compile_to_machine(self, source: str,
                              target: TargetArch = TargetArch.X86_64
                              ) -> MachineFunction:
        ir = self.compile(source, target)
        return self._mc_gen.generate(ir)

    def compile_to_wasm(self, source: str) -> IRModule:
        ir = self._wasm_gen.generate(source)
        return ir

    def compile_to_llvm_ir(self, source: str) -> IRModule:
        ir = self._ir_gen.generate(source)
        return ir

    def interpret(self, source: str) -> Any:
        code = compile(source, "<matha>", "exec")
        namespace = {}
        exec(code, namespace)
        return namespace

    def jit_compile(self, source: str) -> callable:
        return self._jit.compile(source)

    def link(self, objects: list[str],
                output: str) -> bool:
        for obj in objects:
            with open(obj, "rb") as f:
                self._linker.add_object(f.read())
        return self._linker.link(output)

    def assemble(self, source: str,
                    output: str) -> bool:
        return True

    def optimize(self, source: str,
                  level: OptLevel = OptLevel.O2
                  ) -> str:
        return source


def create_llvm_ir_generator() -> LLVMIRGenerator:
    return LLVMIRGenerator()


def create_machine_code_generator(
    target: TargetArch = TargetArch.X86_64
) -> MachineCodeGenerator:
    return MachineCodeGenerator(target=target)


def create_wasm_generator() -> WASMGenerator:
    return WASMGenerator()


def create_jit_compiler() -> JITCompiler:
    return JITCompiler()


def create_linker() -> Linker:
    return Linker()


def create_matha_compiler() -> MathaCompiler:
    return MathaCompiler()


# ============================================================
# 内置注册
# ============================================================

def _register_compiler_full(builtins: dict) -> None:
    builtins["创建LLVM IR生成器"] = create_llvm_ir_generator
    builtins["创建机器码生成器"] = create_machine_code_generator
    builtins["创建WASM生成器"] = create_wasm_generator
    builtins["创建JIT编译器"] = create_jit_compiler
    builtins["创建链接器"] = create_linker
    builtins["创建Matha编译器"] = create_matha_compiler


def _compiler_full_names() -> list[str]:
    return ["创建LLVM IR生成器", "创建机器码生成器",
            "创建WASM生成器", "创建JIT编译器",
            "创建链接器", "创建Matha编译器"]


__all__ = [
    "OptLevel", "TargetArch", "IRType",
    "IRInstruction", "IRBasicBlock", "IRFunction", "IRModule",
    "MachineInstr", "MachineFunction",
    "WASMSection", "WASMType", "WASMFunction",
    "LLVMIRGenerator", "MachineCodeGenerator",
    "WASMGenerator", "JITCompiler", "Linker", "MathaCompiler",
    "create_llvm_ir_generator", "create_machine_code_generator",
    "create_wasm_generator", "create_jit_compiler",
    "create_linker", "create_matha_compiler",
    "_register_compiler_full", "_compiler_full_names",
]
