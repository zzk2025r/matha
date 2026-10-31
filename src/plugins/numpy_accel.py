# -*- coding: utf-8 -*-
"""可选数值加速插件：NumPy 后端内建（阶段 3 从 `src/stdlib_extend.py` 搬出）。

内核与标准库扩展**不**依赖 NumPy（`pyproject.toml` 的 `dependencies` 为空，
NumPy 只在 `[project.optional-dependencies].performance` 里）。原先
`stdlib_extend` 用 ``try: import numpy ... except ImportError: pass`` 注册
一批 `numpy*` 内建 —— 那是一种静默降级：装了就有、没装就当场「未定义符号」，
用户得不到任何说明。现在改成显式插件：

* 未加载本插件而引用 ``numpy数组`` 等符号 → 就是普通的未定义内建诊断（而不是
  「有时候有、有时候没」取决于装了什么包）；
* 加载本插件但环境无 NumPy → **立即**给出明确错误，不假装成功。

用法（显式加载，与 `toolchain_llvm` 等工具插件同层）::

    from src.plugins.numpy_accel import _register_numpy_accel
    _register_numpy_accel(vm_builtins)          # 无 NumPy 则抛 NumpyBackendUnavailable

旧式注册签名 ``_register_xxx(builtins: dict)`` 由 `src.plugin_api.LegacyModulePlugin`
适配为 `exports()`，本模块不需要改写其它代码。（本插件不在
`src/domains/manifest.json` 里 —— 该清单由 `scripts/gen_domain_manifest.py`
从领域名自动生成，工具型插件不入该表。）
"""
from __future__ import annotations

import logging

logger = logging.getLogger("matha.plugins.numpy_accel")

__all__ = ["PLUGIN_NAME", "NumpyBackendUnavailable", "_register_numpy_accel",
           "exports", "arities"]

PLUGIN_NAME = "numpy_accel"

#: 本插件提供的内建名 → 元数（arity），供编译期诊断与契约校验使用
_ARITIES: dict[str, int] = {
    "numpy数组": -1,      # 变元
    "numpy求和": 1,
    "numpy均值": 1,
    "numpy标准差": 1,
    "numpy矩阵乘": 2,
    "numpy转置": 1,
    "numpy逆": 1,
}


class NumpyBackendUnavailable(RuntimeError):
    """插件被显式加载，但环境里没有 NumPy（如实失败，不静默跳过）。"""


def _require_numpy():
    try:
        import numpy as np
    except ImportError as exc:            # noqa: PERF203 - 单一出口
        raise NumpyBackendUnavailable(
            "数值加速插件需要 NumPy，但当前环境未安装；核心能力（纯 Python "
            "线代/矩阵/微积分）不受影响。安装：pip install 'matha[performance]' "
            f"（原始错误：{exc}）"
        ) from exc
    return np


def _register_numpy_accel(builtins: dict) -> None:
    """旧式注册入口：把 NumPy 后端内建写入 ``builtins``。

    与搬出前的关键区别：**没有** ``except ImportError: pass``。要么全部注册成功，
    要么抛 :class:`NumpyBackendUnavailable`，不存在「装了才有、没装当没说过」。
    """
    np = _require_numpy()
    builtins["numpy数组"] = lambda *args: np.array(args)
    builtins["numpy求和"] = lambda arr: float(np.sum(arr)) if hasattr(arr, "__len__") else arr
    builtins["numpy均值"] = lambda arr: float(np.mean(arr)) if hasattr(arr, "__len__") else arr
    builtins["numpy标准差"] = lambda arr: float(np.std(arr)) if hasattr(arr, "__len__") else arr
    builtins["numpy矩阵乘"] = lambda a, b: (np.array(a) @ np.array(b)).tolist()
    builtins["numpy转置"] = lambda m: (np.array(m).T).tolist()
    builtins["numpy逆"] = lambda m: np.linalg.inv(np.array(m)).tolist()
    logger.info("数值加速插件已注册 %d 个 NumPy 后端内建", len(_ARITIES))


def exports() -> dict:
    """`MathaPlugin` 契约：返回可调用表（由适配层按 legacy 签名包装）。"""
    return {"_register_numpy_accel": _register_numpy_accel}


def arities() -> dict[str, int]:
    return dict(_ARITIES)
