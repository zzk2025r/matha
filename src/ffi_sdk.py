"""
Matha FFI SDK - 多语言调用接口

提供统一的 API 供各种语言调用 Matha：
- C API (matha.h / libmatha.so/.dll)
- Python 绑定 (pip install matha)
- Rust FFI (matha-sys / matha crate)
- Go CGO 绑定
- Node.js NAPI 绑定
- Java JNI 绑定
- WASM 绑定 (Web 运行时)

核心能力：
- 引擎创建/销毁
- 代码编译/执行
- 值传递 (标量/数组/矩阵)
- 异步执行/流式输出
- 内存管理
- 错误处理
"""

from __future__ import annotations

import ctypes
import os
import platform
from dataclasses import dataclass
from enum import Enum
from typing import Any

# ============================================================
# 核心类型定义
# ============================================================

class MathaErrorCode(Enum):
    """错误码"""
    SUCCESS = 0
    INVALID_ARGUMENT = -1
    COMPILE_ERROR = -2
    RUNTIME_ERROR = -3
    MEMORY_ERROR = -4
    NOT_INITIALIZED = -5
    ALREADY_INITIALIZED = -6
    INVALID_HANDLE = -7
    NOT_FOUND = -8
    PERMISSION_DENIED = -9
    TIMEOUT = -10
    INTERNAL_ERROR = -100


class MathaValueType(Enum):
    """值类型"""
    NULL = 0
    BOOL = 1
    INT = 2
    FLOAT = 3
    DOUBLE = 4
    STRING = 5
    ARRAY = 6
    MATRIX = 7
    VECTOR = 8
    OBJECT = 9
    FUNCTION = 10
    CHANNEL = 11
    MUTEX = 12


@dataclass
class MathaValue:
    """统一值表示"""
    type: MathaValueType
    bool_val: bool = False
    int_val: int = 0
    float_val: float = 0.0
    double_val: float = 0.0
    string_val: str = ""
    array_val: list[MathaValue] = None
    matrix_val: list[list[float]] = None
    vector_val: list[float] = None
    object_val: dict[str, MathaValue] = None
    ptr_val: int = 0  # 内部指针/句柄

    def to_python(self) -> Any:
        """转换为 Python 原生类型"""
        if self.type == MathaValueType.NULL:
            return None
        elif self.type == MathaValueType.BOOL:
            return self.bool_val
        elif self.type == MathaValueType.INT:
            return self.int_val
        elif self.type in (MathaValueType.FLOAT, MathaValueType.DOUBLE):
            return self.double_val
        elif self.type == MathaValueType.STRING:
            return self.string_val
        elif self.type == MathaValueType.ARRAY:
            return [v.to_python() for v in (self.array_val or [])]
        elif self.type == MathaValueType.MATRIX:
            return self.matrix_val
        elif self.type == MathaValueType.VECTOR:
            return self.vector_val
        elif self.type == MathaValueType.OBJECT:
            return {k: v.to_python() for k, v in (self.object_val or {}).items()}
        elif self.type == MathaValueType.FUNCTION:
            return f"<function:{self.ptr_val}>"
        elif self.type == MathaValueType.CHANNEL:
            return f"<channel:{self.ptr_val}>"
        elif self.type == MathaValueType.MUTEX:
            return f"<mutex:{self.ptr_val}>"
        return str(self.ptr_val)

    @classmethod
    def from_python(cls, val: Any) -> MathaValue:
        """从 Python 值创建"""
        if val is None:
            return cls(MathaValueType.NULL)
        elif isinstance(val, bool):
            return cls(MathaValueType.BOOL, bool_val=val)
        elif isinstance(val, int):
            return cls(MathaValueType.INT, int_val=val)
        elif isinstance(val, float):
            return cls(MathaValueType.DOUBLE, double_val=val)
        elif isinstance(val, str):
            return cls(MathaValueType.STRING, string_val=val)
        elif isinstance(val, list):
            if val and isinstance(val[0], list):
                # 矩阵
                return cls(MathaValueType.MATRIX, matrix_val=val)
            else:
                # 数组/向量
                return cls(MathaValueType.ARRAY, array_val=[cls.from_python(v) for v in val])
        elif isinstance(val, dict):
            return cls(MathaValueType.OBJECT, object_val={k: cls.from_python(v) for k, v in val.items()})
        else:
            return cls(MathaValueType.OBJECT, ptr_val=id(val))


# ============================================================
# 引擎配置
# ============================================================

@dataclass
class MathaEngineConfig:
    """引擎配置"""
    # 内存限制 (MB)
    memory_limit_mb: int = 256
    # 最大执行时间 (ms)
    max_execution_time_ms: int = 30000
    # 启用 JIT
    enable_jit: bool = True
    # 启用并行执行
    enable_parallel: bool = True
    # 最大工作线程数
    max_workers: int = 4
    # 优化级别 (0-3)
    optimization_level: int = 2
    # 目标架构
    target_arch: str = "native"
    # 启用调试
    debug: bool = False
    # 自定义库路径
    custom_lib_path: str = ""


# ============================================================
# Python 高级绑定
# ============================================================

class MathaEngine:
    """Matha 引擎 Python 高级封装"""

    def __init__(self, config: MathaEngineConfig | None = None):
        self.config = config or MathaEngineConfig()
        self._initialized = False
        self._modules: dict[str, Any] = {}
        self._context: dict[str, Any] = {}

    def initialize(self) -> bool:
        """初始化引擎"""
        if self._initialized:
            return True

        # 初始化核心组件
        from src.interp import Interpreter
        from src.mir import MIRGenerator
        from src.mir_opt import MathaOptimizationPipeline
        from src.parser import parse
        from src.vm import MathaVM

        self._interpreter = Interpreter()
        self._parser = parse
        self._mir_gen = MIRGenerator()
        self._vm = MathaVM()
        self._optimizer = MathaOptimizationPipeline()

        self._initialized = True
        return True

    def shutdown(self) -> None:
        """关闭引擎"""
        self._initialized = False
        self._modules.clear()
        self._context.clear()

    def compile(self, source: str, target: str = "mir") -> Any:
        """编译源码"""
        if not self._initialized:
            self.initialize()

        ast = self._parser(source)

        if target == "ast":
            return ast
        elif target == "mir":
            return self._mir_gen.generate(ast)
        elif target == "optimized_mir":
            mir = self._mir_gen.generate(ast)
            return self._optimizer.run(mir)
        elif target == "llvm":
            mir = self._mir_gen.generate(ast)
            mir = self._optimizer.run(mir)
            from src.mir_codegen import MathaLLVMGenerator
            gen = MathaLLVMGenerator()
            return gen.generate(mir)
        elif target == "python":
            from src.codegen.python_backend import PythonGenerator
            mir = self._mir_gen.generate(ast)
            gen = PythonGenerator(mir, "/tmp")
            return gen._build_main()
        elif target == "rust":
            from src.codegen.rust_backend import RustGenerator
            mir = self._mir_gen.generate(ast)
            gen = RustGenerator(mir, "/tmp")
            return gen._build_lib_rs()
        elif target == "c":
            from src.codegen.c_backend import CGenerator
            mir = self._mir_gen.generate(ast)
            gen = CGenerator(mir, "/tmp")
            return gen._build_header() + "\n\n" + gen._build_source()
        elif target == "cpp":
            from src.codegen.cpp_backend import CppGenerator
            mir = self._mir_gen.generate(ast)
            gen = CppGenerator(mir, "/tmp")
            return gen._build_header() + "\n\n" + gen._build_source()
        elif target == "go":
            from src.codegen.go_backend import GoGenerator
            mir = self._mir_gen.generate(ast)
            gen = GoGenerator(mir, "/tmp")
            return gen._build_main()
        elif target == "java":
            from src.codegen.java_backend import JavaGenerator
            mir = self._mir_gen.generate(ast)
            gen = JavaGenerator(mir, "/tmp")
            return gen._build_main()
        elif target == "js":
            from src.codegen.js_backend import JSGenerator
            mir = self._mir_gen.generate(ast)
            gen = JSGenerator(mir, "/tmp")
            return gen._build_main()

        raise ValueError(f"不支持的目标: {target}")

    def execute(self, source: str, inputs: dict[str, Any] | None = None) -> list[Any]:
        """执行源码"""
        if not self._initialized:
            self.initialize()

        ast = self._parser(source)
        outputs, trace = self._interpreter.run(ast)
        return outputs

    def execute_async(self, source: str, inputs: dict[str, Any] | None = None) -> Any:
        """异步执行源码"""
        import asyncio
        return asyncio.get_event_loop().run_in_executor(None, self.execute, source, inputs)

    def compile_and_execute(self, source: str, target: str = "mir") -> Any:
        """编译并执行"""
        mir = self.compile(source, target)

        if target in ("mir", "optimized_mir"):
            # 使用 VM 执行
            outputs, trace = self._vm.run(mir)
            return outputs
        elif target in ("python", "js", "wasm"):
            # 这些目标生成可直接运行的代码
            return {"compiled_code": mir}
        else:
            return {"compiled": True, "target": target}

    def register_module(self, name: str, module: Any) -> None:
        """注册外部模块"""
        self._modules[name] = module

    def call_function(self, module_name: str, func_name: str, *args) -> Any:
        """调用模块中的函数"""
        if module_name in self._modules:
            module = self._modules[module_name]
            func = getattr(module, func_name, None)
            if func:
                return func(*args)
        raise ValueError(f"模块或函数不存在: {module_name}.{func_name}")

    def set_global(self, name: str, value: Any) -> None:
        """设置全局变量"""
        self._context[name] = value

    def get_global(self, name: str) -> Any:
        """获取全局变量"""
        return self._context.get(name)


# ============================================================
# C API 兼容层 (供 ctypes 使用)
# ============================================================

# 定义 C 兼容的结构体
class CMathaValue(ctypes.Structure):
    """C 兼容的值结构"""
    _fields_ = [
        ("type", ctypes.c_int),
        ("bool_val", ctypes.c_bool),
        ("int_val", ctypes.c_longlong),
        ("float_val", ctypes.c_float),
        ("double_val", ctypes.c_double),
        ("string_val", ctypes.c_char_p),
        ("ptr_val", ctypes.c_void_p),
    ]


class CMathaConfig(ctypes.Structure):
    """C 兼容的配置结构"""
    _fields_ = [
        ("memory_limit_mb", ctypes.c_int),
        ("max_execution_time_ms", ctypes.c_int),
        ("enable_jit", ctypes.c_bool),
        ("enable_parallel", ctypes.c_bool),
        ("max_workers", ctypes.c_int),
        ("optimization_level", ctypes.c_int),
        ("target_arch", ctypes.c_char_p),
        ("debug", ctypes.c_bool),
        ("custom_lib_path", ctypes.c_char_p),
    ]


# 动态库加载器
class MathaLibrary:
    """Matha 动态库加载器"""

    _instance: MathaLibrary | None = None
    _lib: ctypes.CDLL | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load(self, lib_path: str | None = None) -> bool:
        """加载动态库"""
        if self._lib is not None:
            return True

        # 自动查找库文件
        if lib_path is None:
            lib_names = {
                "windows": ["matha.dll", "libmatha.dll"],
                "linux": ["libmatha.so", "libmatha.so.1"],
                "darwin": ["libmatha.dylib", "libmatha.1.dylib"],
            }
            system = platform.system().lower()
            candidates = lib_names.get(system, ["libmatha.so"])

            for name in candidates:
                for path in [".", "./dist", "./build", "/usr/local/lib", "/usr/lib"]:
                    full = os.path.join(path, name)
                    if os.path.exists(full):
                        lib_path = full
                        break
                else:
                    continue
                break
            else:
                return False

        try:
            self._lib = ctypes.CDLL(lib_path)
            self._setup_function_signatures()
            return True
        except Exception as e:
            print(f"加载库失败: {e}")
            return False

    def _setup_function_signatures(self) -> None:
        """设置函数签名"""
        lib = self._lib

        # 引擎管理
        lib.matha_engine_create.argtypes = [ctypes.POINTER(CMathaConfig)]
        lib.matha_engine_create.restype = ctypes.c_void_p

        lib.matha_engine_destroy.argtypes = [ctypes.c_void_p]
        lib.matha_engine_destroy.restype = ctypes.c_int

        # 编译执行
        lib.matha_compile.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
        lib.matha_compile.restype = ctypes.c_int

        lib.matha_execute.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        lib.matha_execute.restype = ctypes.c_int

        lib.matha_execute_with_inputs.argtypes = [
            ctypes.c_void_p, ctypes.c_char_p, ctypes.POINTER(CMathaValue), ctypes.c_int
        ]
        lib.matha_execute_with_inputs.restype = ctypes.c_int

        # 值操作
        lib.matha_value_create_bool.argtypes = [ctypes.c_bool]
        lib.matha_value_create_bool.restype = ctypes.POINTER(CMathaValue)

        lib.matha_value_create_int.argtypes = [ctypes.c_longlong]
        lib.matha_value_create_int.restype = ctypes.POINTER(CMathaValue)

        lib.matha_value_create_double.argtypes = [ctypes.c_double]
        lib.matha_value_create_double.restype = ctypes.POINTER(CMathaValue)

        lib.matha_value_create_string.argtypes = [ctypes.c_char_p]
        lib.matha_value_create_string.restype = ctypes.POINTER(CMathaValue)

        lib.matha_value_destroy.argtypes = [ctypes.POINTER(CMathaValue)]
        lib.matha_value_destroy.restype = None

        lib.matha_value_to_python.argtypes = [ctypes.POINTER(CMathaValue)]
        lib.matha_value_to_python.restype = ctypes.c_char_p  # JSON 字符串

        # 内存管理
        lib.matha_alloc.argtypes = [ctypes.c_size_t]
        lib.matha_alloc.restype = ctypes.c_void_p

        lib.matha_free.argtypes = [ctypes.c_void_p]
        lib.matha_free.restype = None

        # 错误处理
        lib.matha_get_last_error.argtypes = []
        lib.matha_get_last_error.restype = ctypes.c_char_p

        lib.matha_get_error_code.argtypes = []
        lib.matha_get_error_code.restype = ctypes.c_int

    # 高级封装方法
    def create_engine(self, config: MathaEngineConfig | None = None) -> int:
        """创建引擎，返回句柄"""
        if config is None:
            config = MathaEngineConfig()

        c_config = CMathaConfig(
            memory_limit_mb=config.memory_limit_mb,
            max_execution_time_ms=config.max_execution_time_ms,
            enable_jit=config.enable_jit,
            enable_parallel=config.enable_parallel,
            max_workers=config.max_workers,
            optimization_level=config.optimization_level,
            target_arch=config.target_arch.encode() if config.target_arch else b"native",
            debug=config.debug,
            custom_lib_path=config.custom_lib_path.encode() if config.custom_lib_path else b"",
        )

        handle = self._lib.matha_engine_create(ctypes.byref(c_config))
        return handle

    def destroy_engine(self, handle: int) -> int:
        return self._lib.matha_engine_destroy(handle)

    def compile(self, handle: int, source: str, target: str) -> int:
        return self._lib.matha_compile(handle, source.encode(), target.encode())

    def execute(self, handle: int, source: str) -> int:
        return self._lib.matha_execute(handle, source.encode())

    def execute_with_inputs(self, handle: int, source: str, inputs: list[MathaValue]) -> int:
        c_values = (ctypes.POINTER(CMathaValue) * len(inputs))()
        for i, v in enumerate(inputs):
            c_val = CMathaValue(
                type=v.type.value,
                bool_val=v.bool_val,
                int_val=v.int_val,
                double_val=v.double_val,
                string_val=v.string_val.encode() if v.string_val else None,
                ptr_val=v.ptr_val,
            )
            c_values[i] = ctypes.pointer(c_val)

        return self._lib.matha_execute_with_inputs(handle, source.encode(), c_values, len(inputs))

    def get_last_error(self) -> str:
        err = self._lib.matha_get_last_error()
        return err.decode() if err else ""

    def get_error_code(self) -> int:
        return self._lib.matha_get_error_code()


# ============================================================
# 统一入口
# ============================================================

_default_engine: MathaEngine | None = None
_default_lib: MathaLibrary | None = None


def get_engine(config: MathaEngineConfig | None = None) -> MathaEngine:
    """获取默认引擎实例"""
    global _default_engine
    if _default_engine is None:
        _default_engine = MathaEngine(config)
    return _default_engine


def get_library() -> MathaLibrary:
    """获取默认库实例"""
    global _default_lib
    if _default_lib is None:
        _default_lib = MathaLibrary()
    return _default_lib


def init(config: MathaEngineConfig | None = None) -> bool:
    """初始化 Matha"""
    engine = get_engine(config)
    return engine.initialize()


def shutdown() -> None:
    """关闭 Matha"""
    global _default_engine, _default_lib
    if _default_engine:
        _default_engine.shutdown()
        _default_engine = None
    if _default_lib:
        _default_lib._lib = None
        _default_lib = None


def compile_source(source: str, target: str = "mir") -> Any:
    """编译源码"""
    return get_engine().compile(source, target)


def execute_source(source: str, inputs: dict[str, Any] | None = None) -> list[Any]:
    """执行源码"""
    return get_engine().execute(source, inputs)


async def execute_source_async(source: str, inputs: dict[str, Any] | None = None) -> list[Any]:
    """异步执行源码"""
    return await get_engine().execute_async(source, inputs)


def run_pipeline(source: str, targets: list[str] = None) -> dict[str, Any]:
    """运行完整管线：编译 -> 优化 -> 多目标代码生成 -> 执行验证"""
    if targets is None:
        targets = ["mir", "optimized_mir", "python", "rust", "c", "cpp", "go", "java", "js"]

    results = {"source": source, "targets": {}}

    for target in targets:
        try:
            compiled = compile_source(source, target)
            results["targets"][target] = {"success": True, "output": compiled}
        except Exception as e:
            results["targets"][target] = {"success": False, "error": str(e)}

    # 执行验证
    try:
        outputs = execute_source(source)
        results["execution"] = {"success": True, "outputs": outputs}
    except Exception as e:
        results["execution"] = {"success": False, "error": str(e)}

    return results


# ============================================================
# 便捷函数
# ============================================================

def matha_eval(expression: str) -> Any:
    """计算表达式"""
    return execute_source(f"#1：[{expression}]")[0] if execute_source(f"#1：[{expression}]") else None


def matha_run_file(filepath: str) -> list[Any]:
    """运行 .matha 文件"""
    with open(filepath, encoding='utf-8') as f:
        source = f.read()
    return execute_source(source)


def matha_compile_file(filepath: str, target: str = "python") -> str:
    """编译 .matha 文件到目标语言"""
    with open(filepath, encoding='utf-8') as f:
        source = f.read()
    return compile_source(source, target)


# ============================================================
# 导出
# ============================================================

__all__ = [
    # 核心类型
    "MathaErrorCode",
    "MathaValueType",
    "MathaValue",
    "MathaEngineConfig",
    # 引擎
    "MathaEngine",
    "get_engine",
    "init",
    "shutdown",
    # 库
    "MathaLibrary",
    "get_library",
    "CMathaValue",
    "CMathaConfig",
    # 高级 API
    "compile_source",
    "execute_source",
    "execute_source_async",
    "run_pipeline",
    # 便捷函数
    "matha_eval",
    "matha_run_file",
    "matha_compile_file",
    # FFI
    "CMathaValue",
    "CMathaConfig",
    "MathaLibrary",
]


if __name__ == "__main__":
    # 简单测试
    print("=" * 60)
    print("  Matha FFI SDK 测试")
    print("=" * 60)

    # 测试值转换
    print("\n[值转换测试]")
    test_values = [None, True, 42, 3.14, "hello", [1, 2, 3], [[1, 2], [3, 4]], {"a": 1, "b": 2}]
    for v in test_values:
        mv = MathaValue.from_python(v)
        back = mv.to_python()
        print(f"  {type(v).__name__}: {v} -> {mv.type.name} -> {back}")

    # 测试引擎初始化
    print("\n[引擎初始化测试]")
    engine = get_engine()
    success = engine.initialize()
    print(f"  初始化: {'成功' if success else '失败'}")

    # 测试执行
    print("\n[执行测试]")
    outputs = execute_source("#1：[sin(3.14)]")
    print(f"  sin(3.14) = {outputs}")

    # 测试编译
    print("\n[编译测试]")
    c_code = compile_source("#1：[x + 1]", "c")
    print(f"  C 代码生成: {'成功' if c_code else '失败'} (长度: {len(c_code)} 字符)")

    py_code = compile_source("#1：[x + 1]", "python")
    print(f"  Python 代码生成: {'成功' if py_code else '失败'} (长度: {len(py_code)} 字符)")

    rust_code = compile_source("#1：[x + 1]", "rust")
    print(f"  Rust 代码生成: {'成功' if rust_code else '失败'} (长度: {len(rust_code)} 字符)")

    # 管线测试
    print("\n[管线测试]")
    pipeline_result = run_pipeline("#1：[x^2 + 2*x + 1]", ["python", "rust", "c"])
    print(f"  管线执行: {pipeline_result['execution']['success']}")

    print("\n" + "=" * 60)
    print("  测试完成")
    print("=" * 60)
