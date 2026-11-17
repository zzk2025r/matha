"""
Matha 编译器框架 - 统一导出所有编译器组件

这个包提供了：
1. LLVM 后端 - LLVM IR 生成和 JIT 编译
2. Pass 管理器 - 管理和执行优化遍（框架级，未接入 MBC 主线，见 KNOWN_ISSUES）
3. 后端管理器 - 管理和执行多后端代码生成（Cranelift/WASM/EVM/Native 为诚实 stub）
4. 自适应优化器 - 根据程序特征动态选择优化策略（ML 路径 sklearn 可选，默认规则路径）
5. 分布式编译器 - 支持多节点协同编译（HTTP 面可选 aiohttp，本地面纯标准库）
6. 增量编译器 - 只重新编译发生变化的部分

口径纪律：import 面零第三方依赖（pyproject dependencies=[]），可选项全部惰性装入；
本文件不做 try/except ImportError 静默吞错——装不进去就大声失败（禁止静默假成功）。
"""
from __future__ import annotations

# LLVM 后端
from src.compiler.llvm_backend import (
    IRArithOp,
    IRAssignment,
    IRCompareOp,
    IRConstant,
    IRFunctionCall,
    IRFunctionDef,
    IRIfExpr,
    IRLogicalOp,
    IRLoop,
    IRVariable,
    IRVariableAccess,
    LLVMCompiler,
    LLVMHotJIT,
    LLVMIRGenerator,
    LLVMType,
    LLVMValue,
    MathaIRNode,
    MathaToIRConverter,
    compile_llvm_ir,
    create_hot_jit,
    matha_to_llvm_ir,
)

# Pass 管理器
from .pass_manager import (
    Pass,
    PassManager,
    get_pass_manager,
    register_pass,
    enable_pass,
    disable_pass,
    auto_order_passes,
    run_passes,
)

# 后端管理器
from .backend_manager import (
    Backend,
    BackendManager,
    LLVMBackend,
    CraneliftBackend,
    WASMBackend,
    EVMBackend,
    NativeBackend,
    get_backend_manager,
    compile_program,
    auto_select_backend,
)

# 自适应优化器
from .adaptive_optimizer import (
    ProgramFeature,
    OptimizationStrategy,
    ProgramAnalyzer,
    StrategySelector,
    AdaptiveOptimizer,
    get_adaptive_optimizer,
    optimize_program,
)

# 分布式编译器
from .distributed_compiler import (
    CompilationTask,
    NodeCapability,
    NodeInfo,
    CompilerNode,
    LocalCompilerNode,
    RemoteCompilerNode,
    TaskScheduler,
    DistributedCompiler,
    get_distributed_compiler,
)

# 增量编译器
from .incremental_compiler import (
    FileInfo,
    BuildResult,
    DependencyGraph,
    IncrementalCompiler,
    get_incremental_compiler,
)

__all__ = [
    # LLVM 后端
    "LLVMType", "LLVMValue",
    "MathaIRNode", "IRConstant", "IRVariable", "IRArithOp",
    "IRCompareOp", "IRLogicalOp", "IRFunctionCall",
    "IRVariableAccess", "IRAssignment", "IRIfExpr", "IRLoop", "IRFunctionDef",
    "MathaToIRConverter",
    "LLVMIRGenerator",
    "LLVMCompiler",
    "LLVMHotJIT",
    "matha_to_llvm_ir",
    "compile_llvm_ir",
    "create_hot_jit",

    # Pass 管理器
    "Pass", "PassManager", "get_pass_manager", "register_pass",
    "enable_pass", "disable_pass", "auto_order_passes", "run_passes",

    # 后端管理器
    "Backend", "BackendManager", "LLVMBackend", "CraneliftBackend",
    "WASMBackend", "EVMBackend", "NativeBackend", "get_backend_manager",
    "compile_program", "auto_select_backend",

    # 自适应优化器
    "ProgramFeature", "OptimizationStrategy", "ProgramAnalyzer",
    "StrategySelector", "AdaptiveOptimizer", "get_adaptive_optimizer",
    "optimize_program",

    # 分布式编译器
    "CompilationTask", "NodeCapability", "NodeInfo", "CompilerNode",
    "LocalCompilerNode", "RemoteCompilerNode", "TaskScheduler",
    "DistributedCompiler", "get_distributed_compiler",

    # 增量编译器
    "FileInfo", "BuildResult", "DependencyGraph",
    "IncrementalCompiler", "get_incremental_compiler",
]
