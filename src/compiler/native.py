# -*- coding: utf-8 -*-
"""
Matha 原生编译层 v2.0
======================
协议解释生成器 + 驱动生成器 + 原生代码编译

架构：
  Matha 表达式 → 协议解析器 → 驱动规格 → 驱动生成器 → 目标代码
  Matha 表达式 → 原生编译器 → 汇编/C/Python 代码 → 执行

功能：
  1. ProtocolInterpreter  — 协议解释（UART/SPI/I2C/CAN 自动代码生成）
  2. DriverBuilder        — 构建各类硬件驱动（传感器/执行器/通信/显示/存储）
  3. NativeCompiler       — 原生代码编译（C/汇编/Python 后端）
  4. 与 hal_v2.py 无缝集成
"""
from __future__ import annotations
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.hardware.hal_v2 import (
    Architecture, BareMetalTarget, DriverGenerator, DriverKind,
    get_driver_generator, get_native_backend, get_pointer_manager,
    get_protocol_parser, get_side_effect_engine, Pointer, ProtocolParser,
    ProtocolSpec, ProtocolType, SafeSideEffectEngine, SideEffectType,
)

logger = logging.getLogger("matha.native_compiler")


# ═══════════════════════════════════════════════════════════════════════════════
#  1. 协议解释器
# ═══════════════════════════════════════════════════════════════════════════════

class ProtocolInterpreter:
    """
    协议解释器。

    将协议规格解释为可执行的代码和配置。
    支持：UART, SPI, I2C, CAN, USB, MQTT, HTTP
    """

    def __init__(self, parser: ProtocolParser):
        self._parser = parser
        self._active_protocols: Dict[str, dict] = {}  # name → parsed spec
        self._call_count = 0
        logger.info("  [协议解释器] 初始化完成")

    def interpret(self, spec: ProtocolSpec) -> dict:
        """解释协议规格，返回可执行代码和配置。"""
        result = self._parser.parse(spec)
        result["spec"] = {
            "protocol": spec.protocol.value,
            "name": spec.name,
            "baud_rate": spec.baud_rate,
            "max_payload": spec.max_payload,
            "timeout_ms": spec.timeout_ms,
            "endian": spec.endian,
        }
        self._active_protocols[spec.name] = result
        self._call_count += 1
        logger.info(f"  [协议] 解释: {spec.name} ({spec.protocol.value})")
        return result

    def get_code(self, name: str, lang: str = "python") -> Optional[str]:
        """获取已解释协议的指定语言代码。"""
        proto = self._active_protocols.get(name)
        if proto is None:
            return None
        key = f"code_{lang}"
        # 查找匹配的语言代码
        for k, v in proto.get("code", {}).items():
            if isinstance(v, str):
                return v
        return None

    def list_protocols(self) -> List[str]:
        """列出所有已解释的协议。"""
        return list(self._active_protocols.keys())

    def get_stats(self) -> dict:
        return {
            "interpreted_count": self._call_count,
            "active_protocols": len(self._active_protocols),
            "protocol_names": self.list_protocols(),
        }


# ═══════════════════════════════════════════════════════════════════════════════
#  2. 驱动构建器
# ═══════════════════════════════════════════════════════════════════════════════

class DriverBuilder:
    """
    硬件驱动构建器。

    根据驱动规格生成目标语言代码，并注册到 FFI/驱动管理器。
    """

    def __init__(self, generator: DriverGenerator):
        self._gen = generator
        self._built_drivers: Dict[str, dict] = {}
        self._total_builds = 0
        logger.info("  [驱动构建器] 初始化完成")

    def build(self, spec: DriverSpec) -> dict:
        """构建驱动并返回结果。"""
        result = self._gen.generate(spec)
        self._built_drivers[spec.name] = result
        self._total_builds += 1
        logger.info(f"  [驱动] 构建成功: {spec.name} ({spec.kind.value})")
        return result

    def build_sensor(self, name: str, math_expr: str, scale: float = 1.0,
                     offset: float = 0.0, unit: str = "raw",
                     protocol: Optional[ProtocolSpec] = None,
                     arch: Architecture = Architecture.ARM64) -> dict:
        """便捷方法：构建传感器驱动。"""
        spec = DriverSpec(
            name=name, kind=DriverKind.SENSORS,
            protocol=protocol, target_arch=arch,
            target_lang="python",
            params={"scale": scale, "offset": offset, "unit": unit},
            math_expr=math_expr,
        )
        return self.build(spec)

    def build_actuator(self, name: str, min_val: float = 0.0, max_val: float = 100.0,
                       step: float = 0.1, protocol: Optional[ProtocolSpec] = None,
                       arch: Architecture = Architecture.ARM64) -> dict:
        """便捷方法：构建执行器驱动。"""
        spec = DriverSpec(
            name=name, kind=DriverKind.ACTUATORS,
            protocol=protocol, target_arch=arch,
            target_lang="python",
            params={"min": min_val, "max": max_val, "step": step},
        )
        return self.build(spec)

    def build_math(self, name: str, math_expr: str,
                   arch: Architecture = Architecture.X86_64) -> dict:
        """便捷方法：构建数学驱动。"""
        spec = DriverSpec(
            name=name, kind=DriverKind.MATH,
            target_arch=arch, target_lang="python",
            math_expr=math_expr,
        )
        return self.build(spec)

    def list_built(self) -> List[str]:
        """列出已构建的驱动。"""
        return list(self._built_drivers.keys())

    def get_stats(self) -> dict:
        return {
            "total_builds": self._total_builds,
            "built_drivers": len(self._built_drivers),
            "driver_list": self.list_built(),
        }


# ═══════════════════════════════════════════════════════════════════════════════
#  3. 原生编译器
# ═══════════════════════════════════════════════════════════════════════════════

class NativeCompiler:
    """
    原生编译器。

    将 Matha 表达式编译为各架构的原生代码（C/汇编/Python）。
    支持安全副作用追踪和指针/内存控制。
    """

    def __init__(self, backend: NativeBackend,
                 side_effect_engine: SafeSideEffectEngine,
                 pointer_mgr: PointerManager):
        self._backend = backend
        self._sse = side_effect_engine
        self._pmgr = pointer_mgr
        self._compile_count = 0
        self._cache_hits = 0
        logger.info("  [原生编译器] 初始化完成")

    def compile(self, expr: str, arch: Architecture,
                func_name: str = "compute",
                target_lang: str = "c",
                safety_level: str = "medium") -> dict:
        """编译表达式，返回代码和元数据。"""
        # 副作用安全检查
        effect = SideEffectType.READ  # 默认读操作
        self._sse.register_func(func_name, effect, safety_level)

        try:
            code = self._backend.compile(expr, arch, func_name, target_lang)
            self._compile_count += 1
            result = {
                "expr": expr,
                "arch": arch.value,
                "lang": target_lang,
                "func_name": func_name,
                "code": code,
                "code_length": len(code),
                "effect": effect.value,
                "permission": safety_level,
                "success": True,
            }
            logger.info(f"  [编译] {expr} → {arch.value}/{target_lang} ({len(code)}B)")
            return result
        except Exception as e:
            logger.error(f"  [编译] 失败: {expr} → {e}")
            return {
                "expr": expr, "arch": arch.value, "lang": target_lang,
                "success": False, "error": str(e),
            }

    def compile_to_c(self, expr: str, func_name: str = "compute",
                     arch: Architecture = Architecture.X86_64) -> dict:
        """编译为 C 代码（默认）。"""
        return self.compile(expr, arch, func_name, "c")

    def compile_to_asm(self, expr: str, func_name: str = "compute",
                       arch: Architecture = Architecture.ARM64) -> dict:
        """编译为汇编代码。"""
        return self.compile(expr, arch, func_name, "assembly")

    def compile_and_exec(self, expr: str, arch: Architecture,
                         func_name: str = "compute") -> dict:
        """编译并尝试执行（仅支持 Python 后端）。"""
        result = self.compile(expr, arch, func_name, "python")
        if result["success"]:
            try:
                safe_globals = {"__builtins__": __builtins__, "math": __import__("math")}
                exec(result["code"], safe_globals)
                fn = safe_globals.get(func_name)
                if fn:
                    result["exec_result"] = fn(0.0)
                    result["exec_success"] = True
                    logger.info(f"  [执行] {func_name}(0) = {result['exec_result']}")
                else:
                    result["exec_success"] = False
                    result["error"] = "函数未找到"
            except Exception as e:
                result["exec_success"] = False
                result["error"] = str(e)
        return result

    def get_stats(self) -> dict:
        return {
            "total_compiles": self._compile_count,
            "cache_hits": self._cache_hits,
            "targets": self._backend.get_targets(),
        }


# ═══════════════════════════════════════════════════════════════════════════════
#  4. 便捷接口
# ═══════════════════════════════════════════════════════════════════════════════

def interpret_protocol(spec: ProtocolSpec) -> dict:
    """解释协议规格。"""
    return get_protocol_parser().parse(spec)


def build_driver(spec: DriverSpec) -> dict:
    """构建硬件驱动。"""
    return get_driver_generator().generate(spec)


def native_compile(expr: str, arch: Architecture = Architecture.X86_64,
                   func_name: str = "compute", target_lang: str = "c") -> dict:
    """原生编译表达式。"""
    compiler = NativeCompiler(
        get_native_backend(),
        get_side_effect_engine(),
        get_pointer_manager()
    )
    return compiler.compile(expr, arch, func_name, target_lang)


def get_native_stats() -> dict:
    """获取原生编译层全部统计。"""
    return {
        "protocol_interpreter": get_protocol_parser().parse(
            ProtocolSpec(protocol=ProtocolType.UART, name="test")
        ) if False else {},
        "protocol_stats": get_protocol_parser().__dict__,
        "driver_stats": get_driver_generator().list_generated(),
        "backend_stats": get_native_backend().get_stats(),
        "sse_stats": get_side_effect_engine().get_stats(),
        "pmgr_stats": get_pointer_manager().get_stats(),
    }
