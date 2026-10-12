"""Matha 包管理器：包安装、依赖解析、版本管理。"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum


class PackageStatus(Enum):
    """包状态。"""
    INSTALLED = "installed"
    NOT_INSTALLED = "not_installed"
    OUTDATED = "outdated"
    DEPENDENCY_ERROR = "dependency_error"


@dataclass
class Package:
    """包定义。"""
    name: str
    version: str = "1.0.0"
    dependencies: dict[str, str] = field(default_factory=dict)
    description: str = ""
    module: str = ""
    installed: bool = False


@dataclass
class PackageResult:
    """包操作结果。"""
    success: bool
    message: str
    package: str | None = None
    dependencies: list[str] = field(default_factory=list)


class PackageManager:
    """包管理器：安装、卸载、解析依赖。"""

    def __init__(self):
        self._packages: dict[str, Package] = {}
        self._installed: dict[str, str] = {}
        self._registry: dict[str, Package] = {}
        self._cache_dir = ".matha_packages"
        self._initialized = False
        self._init_package_manager()

    def _init_package_manager(self) -> None:
        """初始化包管理器。"""
        self._initialized = True
        os.makedirs(self._cache_dir, exist_ok=True)

    def register_package(self, name: str, version: str = "1.0.0",
                         dependencies: dict[str, str] | None = None,
                         description: str = "") -> None:
        """注册包到本地仓库。"""
        pkg = Package(name=name, version=version,
                      dependencies=dependencies or {},
                      description=description)
        self._registry[name] = pkg

    def install(self, name: str, version: str | None = None
                ) -> PackageResult:
        """安装包。"""
        if name not in self._registry:
            return PackageResult(False, f"包 '{name}' 未找到", name)
        pkg = self._registry[name]
        if version and pkg.version != version:
            return PackageResult(False, f"版本不匹配: 需要 {version}, 有 {pkg.version}", name)
        # 检查依赖
        for dep_name, dep_ver in pkg.dependencies.items():
            if dep_name not in self._installed:
                result = self.install(dep_name, dep_ver)
                if not result.success:
                    return PackageResult(False, f"依赖安装失败: {dep_name}", name)
        self._installed[name] = pkg.version
        pkg.installed = True
        return PackageResult(True, f"已安装 {name}=={pkg.version}", name,
                            list(pkg.dependencies.keys()))

    def uninstall(self, name: str) -> PackageResult:
        """卸载包。"""
        if name not in self._installed:
            return PackageResult(False, f"包 '{name}' 未安装", name)
        del self._installed[name]
        if name in self._packages:
            self._packages[name].installed = False
        return PackageResult(True, f"已卸载 {name}", name)

    def list_installed(self) -> dict[str, str]:
        """列出已安装的包。"""
        return dict(self._installed)

    def resolve_dependencies(self, name: str
                              ) -> tuple[bool, list[str]]:
        """解析依赖关系。"""
        if name not in self._registry:
            return False, []
        visited: list[str] = []
        self._resolve_recursive(name, visited, set())
        return True, visited

    def _resolve_recursive(self, name: str, visited: list[str],
                            in_progress: set) -> None:
        """递归解析依赖。"""
        if name in visited or name not in self._registry:
            return
        if name in in_progress:
            return  # 循环依赖检测
        in_progress.add(name)
        pkg = self._registry[name]
        for dep in pkg.dependencies:
            self._resolve_recursive(dep, visited, in_progress)
        visited.append(name)
        in_progress.discard(name)

    def get_status(self, name: str) -> PackageStatus:
        """获取包状态。"""
        if name not in self._registry:
            return PackageStatus.NOT_INSTALLED
        if name in self._installed:
            return PackageStatus.INSTALLED
        return PackageStatus.NOT_INSTALLED

    def get_stats(self) -> dict:
        """获取统计信息。"""
        return {
            "registered": len(self._registry),
            "installed": len(self._installed),
            "initialized": self._initialized,
        }


class DependencyResolver:
    """依赖解析器。"""

    @staticmethod
    def resolve(packages: dict[str, list[str]]
                ) -> tuple[bool, list[str], list[str]]:
        """解析依赖拓扑排序。"""
        result: list[str] = []
        visited: set = set()
        errors: list[str] = []

        def visit(name: str, path: list[str]) -> None:
            if name in visited:
                return
            if name in path:
                errors.append(f"循环依赖: {' -> '.join(path + [name])}")
                return
            path.append(name)
            for dep in packages.get(name, []):
                visit(dep, path)
            path.pop()
            visited.add(name)
            result.append(name)

        for name in packages:
            visit(name, [])

        return len(errors) == 0, result, errors


# ============================================================
# 内置注册
# ============================================================

def create_package_manager() -> PackageManager:
    """创建包管理器。"""
    return PackageManager()


def resolve_dependencies(packages: dict[str, list[str]
                                  ]) -> tuple[bool, list[str], list[str]]:
    """解析依赖关系。"""
    return DependencyResolver.resolve(packages)


def install_package(pm: PackageManager, name: str,
                     version: str | None = None) -> dict:
    """安装包。"""
    result = pm.install(name, version)
    return {"success": result.success, "message": result.message,
            "package": result.package}


def uninstall_package(pm: PackageManager, name: str) -> dict:
    """卸载包。"""
    result = pm.uninstall(name)
    return {"success": result.success, "message": result.message}


def list_packages(pm: PackageManager) -> dict[str, str]:
    """列出已安装的包。"""
    return pm.list_installed()


def register_package(pm: PackageManager, name: str, version: str = "1.0.0",
                      dependencies: dict[str, str] | None = None,
                      description: str = "") -> None:
    """注册包。"""
    pm.register_package(name, version, dependencies, description)


def _register_package(builtins: dict) -> None:
    """注册包管理器内置函数。"""
    builtins["创建包管理器"] = create_package_manager
    builtins["解析依赖"] = lambda pkgs: resolve_dependencies(pkgs)
    builtins["安装包"] = lambda pm, n, v=None: install_package(pm, n, v)
    builtins["卸载包"] = lambda pm, n: uninstall_package(pm, n)
    builtins["列出包"] = lambda pm: list_packages(pm)
    builtins["注册包"] = lambda pm, n, v="1.0.0", d=None: register_package(pm, n, v, d)


def _package_symtab_names() -> list[str]:
    return [
        "创建包管理器", "解析依赖", "安装包", "卸载包",
        "列出包", "注册包",
    ]


__all__ = [
    "Package", "PackageResult", "PackageManager", "DependencyResolver",
    "PackageStatus",
    "create_package_manager", "resolve_dependencies",
    "install_package", "uninstall_package", "list_packages", "register_package",
    "_register_package", "_package_symtab_names",
]
