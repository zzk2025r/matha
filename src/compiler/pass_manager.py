"""
Matha 编译器 Pass 管理系统 - 实现插件化优化遍

这个模块提供了：
1. Pass 基类 - 所有优化遍的基础接口
2. PassManager - 管理和执行优化遍的管道
3. Pass 注册和发现机制
4. Pass 依赖关系解析
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set, Type, Union

logger = logging.getLogger("matha.pass_manager")


class Pass(ABC):
    """优化遍基类 - 所有优化遍必须继承此类"""

    def __init__(self, name: Optional[str] = None) -> None:
        """
        初始化 Pass

        Args:
            name: Pass 的名称，如果未提供则使用类名
        """
        self.name = name or self.__class__.__name__
        self._stats: Dict[str, int] = {}
        self._dependencies: List[str] = []
        self._required_passes: List[str] = []

    @abstractmethod
    def run(self, program: Any) -> Any:
        """
        执行优化遍

        Args:
            program: 输入的程序（通常是 MIR 表示）

        Returns:
            优化后的程序
        """
        pass

    @property
    def stats(self) -> Dict[str, int]:
        """获取优化统计信息"""
        return self._stats.copy()

    def get_stat(self, key: str, default: int = 0) -> int:
        """获取特定统计值"""
        return self._stats.get(key, default)

    def increment_stat(self, key: str, amount: int = 1) -> None:
        """增加统计值"""
        self._stats[key] = self._stats.get(key, 0) + amount

    def add_dependency(self, pass_name: str) -> None:
        """添加依赖的 Pass 名称"""
        if pass_name not in self._dependencies:
            self._dependencies.append(pass_name)

    def add_required_pass(self, pass_name: str) -> None:
        """添加此 Pass 依赖的其他 Pass（必须先执行）"""
        if pass_name not in self._required_passes:
            self._required_passes.append(pass_name)

    def validate_dependencies(self, available_passes: Set[str]) -> None:
        """
        验证依赖是否满足

        Args:
            available_passes: 可用的 Pass 名称集合

        Raises:
            ValueError: 如果依赖不满足
        """
        missing = set(self._required_passes) - available_passes
        if missing:
            raise ValueError(f"Pass {self.name} 缺少依赖: {missing}")


class PassManager:
    """Pass 管理器 - 管理和执行优化遍"""

    def __init__(self) -> None:
        self._passes: Dict[str, Pass] = {}
        self._pass_order: List[str] = []
        self._enabled_passes: Set[str] = set()

    def register_pass(self, pass_instance: Pass, replace: bool = False) -> None:
        """
        注册一个 Pass

        Args:
            pass_instance: Pass 实例
            replace: 是否替换已存在的同名 Pass
        """
        name = pass_instance.name
        if name in self._passes and not replace:
            raise ValueError(f"Pass {name} 已存在")

        # 验证依赖
        pass_instance.validate_dependencies(set(self._passes.keys()))
        self._passes[name] = pass_instance
        logger.debug(f"注册 Pass: {name}")

    def enable_pass(self, name: str) -> None:
        """启用一个 Pass"""
        if name not in self._passes:
            raise ValueError(f"Pass {name} 未注册")
        self._enabled_passes.add(name)

    def unregister_pass(self, name: str) -> bool:
        """注销一个 Pass（阶段 28e 统一端口协议的注销动作面）。

        仅移除已注册的 Pass（未知名返回 False）；启用态同步摘除。
        """
        if name not in self._passes:
            return False
        del self._passes[name]
        self._enabled_passes.discard(name)
        if name in self._pass_order:
            self._pass_order.remove(name)
        return True

    def disable_pass(self, name: str) -> None:
        """禁用一个 Pass"""
        if name in self._enabled_passes:
            self._enabled_passes.remove(name)

    def set_pass_order(self, order: List[str]) -> None:
        """
        设置 Pass 执行顺序

        Args:
            order: Pass 名称列表
        """
        # 验证所有 Pass 是否已注册
        for name in order:
            if name not in self._passes:
                raise ValueError(f"Pass {name} 未注册")

        self._pass_order = order

    def auto_order_passes(self) -> None:
        """根据依赖关系自动排序 Pass"""
        # 使用拓扑排序算法
        graph: Dict[str, List[str]] = {}
        in_degree: Dict[str, int] = {}

        # 初始化图和入度
        for name, pass_obj in self._passes.items():
            graph[name] = []
            in_degree[name] = 0

        # 构建图和入度
        for name, pass_obj in self._passes.items():
            for dep in pass_obj._dependencies:
                if dep in graph:
                    graph[dep].append(name)
                    in_degree[name] += 1

        # 拓扑排序
        queue = [name for name, degree in in_degree.items() if degree == 0]
        ordered = []

        while queue:
            node = queue.pop(0)
            ordered.append(node)

            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # 检查是否有环
        if len(ordered) != len(self._passes):
            raise ValueError("Pass 依赖图中存在循环")

        self._pass_order = ordered

    def run(self, program: Any, enabled_only: bool = True) -> Any:
        """
        运行所有启用的 Pass

        Args:
            program: 输入程序
            enabled_only: 是否只运行启用的 Pass

        Returns:
            优化后的程序
        """
        # 确定要运行的 Pass
        passes_to_run = []
        for name in self._pass_order:
            if enabled_only and name not in self._enabled_passes:
                continue
            passes_to_run.append(name)

        # 运行 Pass
        for name in passes_to_run:
            pass_obj = self._passes[name]
            logger.info(f"运行 Pass: {name}")
            program = pass_obj.run(program)

        return program

    def get_stats(self) -> Dict[str, Dict[str, int]]:
        """获取所有 Pass 的统计信息"""
        return {name: pass_obj.stats for name, pass_obj in self._passes.items()}

    def get_summary(self) -> str:
        """获取优化摘要"""
        lines = ["Matha 优化摘要:", "=" * 50]
        total = 0

        for name, pass_obj in self._passes.items():
            if name in self._enabled_passes:
                stats = pass_obj.stats
                if stats:
                    lines.append(f"  {name}: {stats}")
                    total += sum(stats.values())

        lines.append("-" * 50)
        lines.append(f"  总计: {total} 次优化")
        return "\n".join(lines)


# 全局 Pass 管理器实例
_global_pass_manager = PassManager()


def get_pass_manager() -> PassManager:
    """获取全局 Pass 管理器"""
    return _global_pass_manager


def register_pass(pass_instance: Pass, replace: bool = False) -> None:
    """注册 Pass 到全局管理器"""
    _global_pass_manager.register_pass(pass_instance, replace)


def enable_pass(name: str) -> None:
    """启用全局 Pass"""
    _global_pass_manager.enable_pass(name)


def disable_pass(name: str) -> None:
    """禁用全局 Pass"""
    _global_pass_manager.disable_pass(name)


def auto_order_passes() -> None:
    """自动排序全局 Pass"""
    _global_pass_manager.auto_order_passes()


def run_passes(program: Any, enabled_only: bool = True) -> Any:
    """运行全局 Pass"""
    return _global_pass_manager.run(program, enabled_only)
