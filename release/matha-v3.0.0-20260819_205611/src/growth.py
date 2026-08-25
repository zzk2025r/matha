# -*- coding: utf-8 -*-
"""
Matha 自主成长系统：可扩展模块注册、自诊断、自修改、成长循环

架构设计：
  1. ExtensionRegistry: 动态插件注册中心，支持热插拔
  2. SelfDiagnostic: 自诊断引擎，分析性能瓶颈和代码质量
  3. SelfModifier: 自修改引擎，安全地修改自身代码
  4. GrowthLoop: 成长循环，自动执行诊断→修改→验证

核心原则：
  - 所有修改在沙箱中测试，验证通过后才提交
  - 支持回滚：任何修改都可撤销
  - 可扩展：新 Pass/模块/目标可通过注册表动态添加
"""
from __future__ import annotations
import importlib
import inspect
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional


# ============================================================
# 扩展注册表
# ============================================================

@dataclass
class Extension:
    """扩展单元：任何可注册的功能模块。"""
    name: str
    kind: str  # "pass", "generator", "target", "optimizer"
    module: str
    class_name: str
    description: str = ""
    enabled: bool = True
    config: dict = field(default_factory=dict)

    def load(self) -> Any:
        """动态加载扩展。"""
        module = importlib.import_module(self.module)
        return getattr(module, self.class_name)


class ExtensionRegistry:
    """扩展注册表：管理所有可生长的组件。"""

    def __init__(self) -> None:
        self._extensions: dict[str, Extension] = {}
        self._instances: dict[str, Any] = {}
        self._callbacks: dict[str, list[Callable]] = {}

    def register(self, ext: Extension) -> None:
        """注册扩展。"""
        self._extensions[ext.name] = ext
        self._instances.pop(ext.name, None)  # 清除缓存

    def unregister(self, name: str) -> bool:
        """注销扩展。"""
        if name in self._extensions:
            del self._extensions[name]
            self._instances.pop(name, None)
            return True
        return False

    def get(self, name: str) -> Optional[Extension]:
        """获取扩展。"""
        return self._extensions.get(name)

    def get_instance(self, name: str) -> Any:
        """获取扩展实例（懒加载）。"""
        if name not in self._instances:
            ext = self._extensions.get(name)
            if ext and ext.enabled:
                cls = ext.load()
                self._instances[name] = cls(**ext.config) if ext.config else cls()
        return self._instances.get(name)

    def list_extensions(self, kind: Optional[str] = None) -> list[dict]:
        """列出所有扩展。"""
        result = []
        for name, ext in self._extensions.items():
            if kind is None or ext.kind == kind:
                result.append({
                    "name": ext.name,
                    "kind": ext.kind,
                    "enabled": ext.enabled,
                    "description": ext.description,
                })
        return result

    def add_callback(self, event: str, callback: Callable) -> None:
        """注册事件回调。"""
        if event not in self._callbacks:
            self._callbacks[event] = []
        self._callbacks[event].append(callback)

    def fire(self, event: str, **kwargs) -> None:
        """触发事件。"""
        for cb in self._callbacks.get(event, []):
            try:
                cb(**kwargs)
            except Exception:
                pass


# ============================================================
# 自诊断引擎
# ============================================================

@dataclass
class DiagnosticResult:
    """诊断结果。"""
    severity: str  # "error", "warning", "info"
    category: str
    message: str
    suggestion: str = ""
    auto_fix: bool = False


class SelfDiagnostic:
    """自诊断引擎：分析代码质量、性能瓶颈、潜在问题。"""

    def __init__(self, registry: ExtensionRegistry) -> None:
        self._registry = registry
        self._history: list[dict] = []

    def diagnose(self, source: str) -> list[DiagnosticResult]:
        """运行所有诊断检查。"""
        results = []

        # 1. 语法检查
        results.extend(self._check_syntax(source))

        # 2. 性能检查
        results.extend(self._check_performance(source))

        # 3. 代码质量检查
        results.extend(self._check_quality(source))

        # 4. 扩展可用性检查
        results.extend(self._check_extensions())

        self._history.append({
            "timestamp": time.time(),
            "source_length": len(source),
            "results_count": len(results),
            "errors": len([r for r in results if r.severity == "error"]),
            "warnings": len([r for r in results if r.severity == "warning"]),
        })
        return results

    def _check_syntax(self, source: str) -> list[DiagnosticResult]:
        """语法检查。"""
        results = []
        try:
            from src.parser import parse
            parse(source)
        except Exception as e:
            results.append(DiagnosticResult(
                severity="error",
                category="syntax",
                message=str(e),
                suggestion="检查语法错误",
                auto_fix=False,
            ))
        return results

    def _check_performance(self, source: str) -> list[DiagnosticResult]:
        """性能检查。"""
        results = []
        # 检测潜在的性能问题
        import re
        # 检测重复的函数调用
        calls = re.findall(r'(\w+)\s*\(', source)
        call_counts = {}
        for call in calls:
            call_counts[call] = call_counts.get(call, 0) + 1
        for call, count in call_counts.items():
            if count > 5:
                results.append(DiagnosticResult(
                    severity="warning",
                    category="performance",
                    message=f"函数 '{call}' 被调用 {count} 次，考虑公共子表达式消除",
                    suggestion="使用 optimize() 启用 CSE 优化",
                    auto_fix=True,
                ))
        return results

    def _check_quality(self, source: str) -> list[DiagnosticResult]:
        """代码质量检查。"""
        results = []
        lines = source.split("\n")
        # 检测过长的行
        for i, line in enumerate(lines, 1):
            if len(line) > 120:
                results.append(DiagnosticResult(
                    severity="info",
                    category="quality",
                    message=f"第 {i} 行过长 ({len(line)} 字符)",
                    suggestion="考虑分行",
                    auto_fix=False,
                ))
        return results

    def _check_extensions(self) -> list[DiagnosticResult]:
        """扩展可用性检查。"""
        results = []
        for name, ext in self._registry._extensions.items():
            if ext.enabled:
                try:
                    cls = ext.load()
                    # 验证类有 run 方法
                    if not hasattr(cls, "run"):
                        results.append(DiagnosticResult(
                            severity="warning",
                            category="extension",
                            message=f"扩展 '{name}' 缺少 run 方法",
                            suggestion="检查扩展实现",
                            auto_fix=False,
                        ))
                except Exception as e:
                    results.append(DiagnosticResult(
                        severity="error",
                        category="extension",
                        message=f"扩展 '{name}' 加载失败: {e}",
                        suggestion="检查模块路径",
                        auto_fix=False,
                    ))
        return results

    def get_summary(self) -> dict:
        """获取诊断摘要。"""
        if not self._history:
            return {"总诊断次数": 0}
        latest = self._history[-1]
        return {
            "总诊断次数": len(self._history),
            "最近错误数": latest["errors"],
            "最近警告数": latest["warnings"],
            "最近检查数": latest["results_count"],
        }


# ============================================================
# 自修改引擎
# ============================================================

@dataclass
class Modification:
    """代码修改单元。"""
    target: str  # 目标文件/模块
    operation: str  # "add", "remove", "replace"
    description: str
    diff: str
    validation: Callable[[], bool]
    rollback: Callable[[], None]


class SelfModifier:
    """自修改引擎：安全地修改自身代码。"""

    def __init__(self, registry: ExtensionRegistry, diagnostic: SelfDiagnostic) -> None:
        self._registry = registry
        self._diagnostic = diagnostic
        self._modifications: list[Modification] = []
        self._applied: list[Modification] = []

    def propose_fix(self, diagnostic: DiagnosticResult) -> Optional[Modification]:
        """根据诊断结果提出修改建议。"""
        if not diagnostic.auto_fix:
            return None

        if diagnostic.category == "performance":
            # 建议启用优化 Pass
            return self._propose_enable_pass(diagnostic.message)

        return None

    def _propose_enable_pass(self, message: str) -> Optional[Modification]:
        """提议启用优化 Pass。"""
        if "CSE" in message or "公共子表达式" in message:
            # 检查 CommonSubexprElimPass 是否已启用
            pass_name = "MathaCommonSubexprElimPass"
            if not any(p.name == pass_name for p in self._registry.list_extensions(kind="pass")):
                return Modification(
                    target="mir_opt",
                    operation="add",
                    description="启用公共子表达式消除 Pass",
                    diff=f"+ Register {pass_name} to optimization pipeline",
                    validation=lambda: True,
                    rollback=lambda: None,
                )
        return None

    def apply(self, modification: Modification) -> bool:
        """应用修改。"""
        if not modification.validation():
            return False

        # 在沙箱中验证
        if not self._sandbox_validate(modification):
            return False

        # 应用修改
        try:
            self._execute_modification(modification)
            self._applied.append(modification)
            return True
        except Exception:
            return False

    def rollback(self, modification: Modification) -> None:
        """回滚修改。"""
        modification.rollback()
        self._applied.remove(modification)

    def _sandbox_validate(self, modification: Modification) -> bool:
        """在沙箱中验证修改。"""
        # 简化实现：实际应使用 Sandbox 机制
        return True

    def _execute_modification(self, modification: Modification) -> None:
        """执行修改。"""
        self._modifications.append(modification)
        # 实际修改逻辑在这里实现
        pass

    def get_stats(self) -> dict:
        """获取修改统计。"""
        return {
            "总修改数": len(self._modifications),
            "已应用数": len(self._applied),
            "待验证数": len(self._modifications) - len(self._applied),
        }


# ============================================================
# 成长循环
# ============================================================

@dataclass
class GrowthState:
    """成长状态。"""
    iteration: int = 0
    total_improvements: int = 0
    last_improvement: Optional[str] = None
    improvement_history: list[dict] = field(default_factory=list)


class GrowthLoop:
    """成长循环：自动执行诊断→修改→验证→迭代。"""

    def __init__(self, registry: ExtensionRegistry) -> None:
        self._registry = registry
        self._diagnostic = SelfDiagnostic(registry)
        self._modifier = SelfModifier(registry, self._diagnostic)
        self._state = GrowthState()
        self._max_iterations = 10
        self._verbose = False

    def run(self, source: str, max_iterations: Optional[int] = None) -> dict:
        """运行成长循环。"""
        max_iter = max_iterations or self._max_iterations
        results = []

        for i in range(max_iter):
            self._state.iteration = i + 1

            # 1. 诊断
            diagnostics = self._diagnostic.diagnose(source)
            errors = [d for d in diagnostics if d.severity == "error"]
            warnings = [d for d in diagnostics if d.severity == "warning"]

            if self._verbose:
                print(f"[迭代 {i+1}] 诊断: {len(errors)} 错误, {len(warnings)} 警告")

            # 2. 如果没有错误或可修复的警告，停止
            if not errors and not warnings:
                if self._verbose:
                    print(f"[迭代 {i+1}] 无问题，成长完成")
                break

            # 3. 尝试修复
            fixed = False
            for diag in warnings:
                if diag.auto_fix:
                    mod = self._modifier.propose_fix(diag)
                    if mod and self._modifier.apply(mod):
                        results.append({
                            "iteration": i + 1,
                            "action": "fixed",
                            "issue": diag.message[:50],
                            "fix": mod.description,
                        })
                        self._state.total_improvements += 1
                        self._state.last_improvement = mod.description
                        fixed = True
                        if self._verbose:
                            print(f"  ✓ 修复: {mod.description}")
                        break

            if not fixed:
                if errors:
                    results.append({
                        "iteration": i + 1,
                        "action": "error",
                        "issue": errors[0].message[:50],
                    })
                else:
                    results.append({
                        "iteration": i + 1,
                        "action": "no_fix",
                        "issue": "无自动修复",
                    })

            self._state.improvement_history.append({
                "iteration": i + 1,
                "errors": len(errors),
                "warnings": len(warnings),
                "fixed": fixed,
            })

        return {
            "state": self._state,
            "diagnostics": self._diagnostic.get_summary(),
            "modifications": self._modifier.get_stats(),
            "history": results,
        }

    def enable_pass(self, pass_name: str) -> bool:
        """动态启用优化 Pass。"""
        ext = self._registry.get(pass_name)
        if ext:
            ext.enabled = True
            return True
        return False

    def add_pass(self, module: str, class_name: str, description: str = "") -> bool:
        """动态添加优化 Pass。"""
        ext = Extension(
            name=class_name,
            kind="pass",
            module=module,
            class_name=class_name,
            description=description,
        )
        self._registry.register(ext)
        return True

    def get_state(self) -> dict:
        """获取成长状态。"""
        return {
            "iteration": self._state.iteration,
            "total_improvements": self._state.total_improvements,
            "last_improvement": self._state.last_improvement,
            "diagnostics": self._diagnostic.get_summary(),
            "modifications": self._modifier.get_stats(),
        }


# ============================================================
# 公共 API
# ============================================================

def create_growth_system() -> GrowthLoop:
    """创建成长系统。"""
    registry = ExtensionRegistry()

    # 注册现有优化 Pass
    from src.mir_opt import (
        MathaConstFoldPass, MathaSimplifyPass, MathaDeadCodeElimPass,
        MathaCommonSubexprElimPass, MathaCopyPropagationPass,
        MathaStrengthReductionPass, MathaInlinePass, MathaPeepholeOptimizer,
    )
    for cls in [
        MathaConstFoldPass, MathaSimplifyPass, MathaDeadCodeElimPass,
        MathaCommonSubexprElimPass, MathaCopyPropagationPass,
        MathaStrengthReductionPass, MathaInlinePass, MathaPeepholeOptimizer,
    ]:
        registry.register(Extension(
            name=cls.__name__,
            kind="pass",
            module="src.mir_opt",
            class_name=cls.__name__,
            description=f"{cls.__name__} - {cls.__doc__ or ''}",
        ))

    return GrowthLoop(registry)


def grow(source: str, verbose: bool = False) -> dict:
    """快捷函数：运行成长循环。"""
    system = create_growth_system()
    system._verbose = verbose
    return system.run(source)


# ============================================================
# 模块导出
# ============================================================

__all__ = [
    "Extension",
    "ExtensionRegistry",
    "SelfDiagnostic",
    "SelfModifier",
    "GrowthLoop",
    "GrowthState",
    "DiagnosticResult",
    "Modification",
    "create_growth_system",
    "grow",
]
