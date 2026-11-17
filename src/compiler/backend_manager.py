"""
Matha 编译器后端管理器 - 支持多后端代码生成

这个模块提供了：
1. Backend 基类 - 所有编译后端的基础接口
2. BackendManager - 管理和执行多后端代码生成
3. 内置后端：LLVMBackend、CraneliftBackend、WASMBackend 等
4. 后端注册和发现机制
"""
from __future__ import annotations

import logging
import importlib
import pkgutil
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set, Type, Union

logger = logging.getLogger("matha.backend_manager")


class Backend(ABC):
    """编译后端基类 - 所有编译后端必须继承此类"""

    def __init__(self, name: Optional[str] = None) -> None:
        """
        初始化 Backend

        Args:
            name: 后端的名称，如果未提供则使用类名
        """
        self.name = name or self.__class__.__name__
        self._target: Optional[str] = None
        self._options: Dict[str, Any] = {}

    @abstractmethod
    def compile(self, program: Any) -> Any:
        """
        编译程序到目标平台

        Args:
            program: 输入的程序（通常是 MIR 表示）

        Returns:
            编译后的代码/对象文件/可执行文件等
        """
        pass

    @property
    def target(self) -> Optional[str]:
        """获取目标平台"""
        return self._target

    @target.setter
    def target(self, value: str) -> None:
        """设置目标平台"""
        self._target = value

    @property
    def options(self) -> Dict[str, Any]:
        """获取编译选项"""
        return self._options.copy()

    def set_option(self, key: str, value: Any) -> None:
        """设置编译选项"""
        self._options[key] = value

    def get_option(self, key: str, default: Any = None) -> Any:
        """获取编译选项"""
        return self._options.get(key, default)


class LLVMBackend(Backend):
    """LLVM 编译后端"""

    def __init__(self) -> None:
        super().__init__("LLVM")
        # 默认目标
        self._target = "x86_64-pc-linux-gnu"

    def compile(self, program: Any) -> Any:
        """编译程序到 LLVM IR（委托既有官方导出 matha_to_llvm_ir）"""
        logger.info(f"使用 LLVM 后端编译到 {self.target}")

        from .llvm_backend import matha_to_llvm_ir
        return matha_to_llvm_ir(program)


class CraneliftBackend(Backend):
    """Cranelift 编译后端 - 快速编译器后端"""

    def __init__(self) -> None:
        super().__init__("Cranelift")
        # 默认目标
        self._target = "x86_64"

    def compile(self, program: Any) -> Any:
        """编译程序到 Cranelift"""
        logger.info(f"使用 Cranelift 后端编译到 {self.target}")

        # TODO: 实现 Cranelift 后端
        logger.warning("Cranelift 后端尚未实现")
        raise NotImplementedError("Cranelift 后端尚未实现")


class WASMBackend(Backend):
    """WebAssembly 编译后端"""

    def __init__(self) -> None:
        super().__init__("WASM")
        # 默认目标
        self._target = "wasm32-wasi"

    def compile(self, program: Any) -> Any:
        """编译程序到 WebAssembly"""
        logger.info(f"使用 WASM 后端编译到 {self.target}")

        # TODO: 实现 WASM 后端
        logger.warning("WASM 后端尚未实现")
        raise NotImplementedError("WASM 后端尚未实现")


class EVMBackend(Backend):
    """Ethereum 虚拟机编译后端"""

    def __init__(self) -> None:
        super().__init__("EVM")
        # 默认目标
        self._target = "evm"

    def compile(self, program: Any) -> Any:
        """编译程序到 EVM 字节码"""
        logger.info(f"使用 EVM 后端编译到 {self.target}")

        # TODO: 实现 EVM 后端
        logger.warning("EVM 后端尚未实现")
        raise NotImplementedError("EVM 后端尚未实现")


class NativeBackend(Backend):
    """原生机器码编译后端"""

    def __init__(self) -> None:
        super().__init__("Native")
        # 默认目标
        self._target = "native"

    def compile(self, program: Any) -> Any:
        """编译程序到原生机器码"""
        logger.info(f"使用 Native 后端编译到 {self.target}")

        # TODO: 实现原生机器码后端
        logger.warning("Native 后端尚未实现")
        raise NotImplementedError("Native 后端尚未实现")


class BackendManager:
    """后端管理器 - 管理和执行多后端代码生成"""

    def __init__(self) -> None:
        self._backends: Dict[str, Backend] = {}
        self._default_backend: Optional[str] = "LLVM"

        # 注册内置后端
        self._register_builtin_backends()

    def _register_builtin_backends(self) -> None:
        """注册内置后端"""
        backends = [
            LLVMBackend(),
            CraneliftBackend(),
            WASMBackend(),
            EVMBackend(),
            NativeBackend(),
        ]

        for backend in backends:
            self.register_backend(backend)

    def register_backend(self, backend: Backend, replace: bool = False) -> None:
        """
        注册一个后端

        Args:
            backend: 后端实例
            replace: 是否替换已存在的同名后端
        """
        name = backend.name
        if name in self._backends and not replace:
            raise ValueError(f"后端 {name} 已存在")

        self._backends[name] = backend
        logger.debug(f"注册后端: {name}")

    def get_backend(self, name: str) -> Backend:
        """
        获取指定后端

        Args:
            name: 后端名称

        Returns:
            后端实例

        Raises:
            ValueError: 如果后端不存在
        """
        if name not in self._backends:
            raise ValueError(f"后端 {name} 不存在")
        return self._backends[name]

    def list_backends(self) -> List[str]:
        """列出所有可用后端"""
        return list(self._backends.keys())

    def set_default_backend(self, name: str) -> None:
        """
        设置默认后端

        Args:
            name: 后端名称
        """
        if name not in self._backends:
            raise ValueError(f"后端 {name} 不存在")
        self._default_backend = name

    def compile(self, program: Any, backend: Optional[str] = None, **options) -> Any:
        """
        编译程序

        Args:
            program: 输入程序
            backend: 使用的后端名称，如果为 None 则使用默认后端
            options: 编译选项

        Returns:
            编译结果
        """
        # 确定使用的后端
        if backend is None:
            backend = self._default_backend

        if backend not in self._backends:
            raise ValueError(f"后端 {backend} 不存在")

        # 设置编译选项
        backend_obj = self._backends[backend]
        for key, value in options.items():
            backend_obj.set_option(key, value)

        # 执行编译
        logger.info(f"使用 {backend} 后端编译程序")
        return backend_obj.compile(program)

    def auto_select_backend(self, program: Any, target: str) -> str:
        """
        根据程序和目标平台自动选择后端

        Args:
            program: 输入程序
            target: 目标平台

        Returns:
            选择的后端名称
        """
        # 简单实现：根据目标平台选择后端
        if target.startswith("wasm"):
            return "WASM"
        elif target == "evm":
            return "EVM"
        elif target == "native":
            return "Native"
        else:
            # 默认使用 LLVM
            return "LLVM"


# 全局后端管理器实例
_global_backend_manager = BackendManager()


def get_backend_manager() -> BackendManager:
    """获取全局后端管理器"""
    return _global_backend_manager


def register_backend(backend: Backend, replace: bool = False) -> None:
    """注册后端到全局管理器"""
    _global_backend_manager.register_backend(backend, replace)


def get_backend(name: str) -> Backend:
    """获取全局后端"""
    return _global_backend_manager.get_backend(name)


def list_backends() -> List[str]:
    """列出全局后端"""
    return _global_backend_manager.list_backends()


def set_default_backend(name: str) -> None:
    """设置全局默认后端"""
    _global_backend_manager.set_default_backend(name)


def compile_program(program: Any, backend: Optional[str] = None, **options) -> Any:
    """编译程序"""
    return _global_backend_manager.compile(program, backend, **options)


def auto_select_backend(program: Any, target: str) -> str:
    """自动选择后端"""
    return _global_backend_manager.auto_select_backend(program, target)


def discover_and_register_backends(package_name: str = "src.compiler.backends") -> None:
    """
    自动发现并注册指定包中的后端

    Args:
        package_name: 包名，默认为 "src.compiler.backends"
    """
    try:
        module = importlib.import_module(package_name)
        for _, name, _ in pkgutil.iter_modules(module.__path__):
            submodule = importlib.import_module(f"{package_name}.{name}")
            for attr_name in dir(submodule):
                attr = getattr(submodule, attr_name)
                if isinstance(attr, type) and issubclass(attr, Backend) and attr != Backend:
                    # 这是一个后端类，实例化并注册
                    backend_instance = attr()
                    register_backend(backend_instance)
                    logger.debug(f"自动发现并注册后端: {backend_instance.name}")
    except ImportError:
        logger.warning(f"无法导入包 {package_name}，跳过自动发现后端")
