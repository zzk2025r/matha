# -*- coding: utf-8 -*-
"""Matha 领域扩展模块：设备管理器（System Monitor）。

把 src/system_inventory.py 的四个盘点节暴露为 Matha 符号（阶段 26d：
设备/任务管理器的程序面——CLI matha sys 与本域共用同一信息层）：

  硬件_信息() → 硬件 dict        （平台/CPU/内存/GPU/单片机工具链/Python）
  自身_状况() → Matha 自身 dict  （版本/插件汇总/运行时后端/features/扩展/.matha）
  软件_清单() → 软件清单 dict    （.matha/apps 安装 + .matha_packages 包）
  模块_清单() → 模块清单 dict    （custom_ops/终端注册表/优化遍/插件使用）
  插件_冲突() → [{符号, 拥有者}] （注册表多拥有者符号——26c 冲突面）

全部只读探测：GPU 只查 nvidia-smi、单片机工具链只探存在性、内存面 psutil
缺席诚实降级为 不可得（不伪装成功）。探测边界与 CLI 同口径（登记于
system_inventory docstring）。
"""
from __future__ import annotations

from src.system_inventory import (
    hardware_info,
    modules_inventory,
    self_status,
    software_inventory,
)


def _硬件_信息(_占位=None) -> dict:
    return hardware_info()


def _自身_状况(_占位=None) -> dict:
    return self_status()


def _软件_清单(_占位=None) -> dict:
    return software_inventory()


def _模块_清单(_占位=None) -> dict:
    return modules_inventory()


def _插件_冲突(_占位=None) -> list[dict]:
    from src.plugin_api import get_resolver
    return get_resolver().conflicts()


def _register_system_monitor(builtins: dict) -> None:
    """领域插件登记钩子（scripts/gen_domain_manifest.py 发现）。"""
    builtins["硬件_信息"] = _硬件_信息
    builtins["自身_状况"] = _自身_状况
    builtins["软件_清单"] = _软件_清单
    builtins["模块_清单"] = _模块_清单
    builtins["插件_冲突"] = _插件_冲突


def _system_monitor_symtab_names() -> list[str]:
    return ["硬件_信息", "自身_状况", "软件_清单", "模块_清单", "插件_冲突"]


__all__ = [
    "_register_system_monitor", "_system_monitor_symtab_names",
    "_硬件_信息", "_自身_状况", "_软件_清单", "_模块_清单", "_插件_冲突",
]
