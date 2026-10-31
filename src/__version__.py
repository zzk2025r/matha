# -*- coding: utf-8 -*-
"""唯一版本源（重构阶段 5 第 1 项）。

规则（由 `tests/test_single_version.py` 将行为断言）：

  * 仓库里**只有本文件**允许出现字面量版本号；
  * `src/__init__.py`、`src/matha_main.py`、`src/visual_editor/__init__.py`
    一律从这里取值；
  * `pyproject.toml` 用 `[tool.setuptools.dynamic] version = {attr =
    "src.__version__.__version__"}` 指向本文件，安装元数据不再各说各话；
  * README / ARCHITECTURE / MATHA_COMPARISON 若需写版本，必须与本文件一致。

历史包袱：本文件建立之前，同一份代码里同时存在 v4.3 / v4.4 / v4.4.57 / v4.5 /
v4.6 / 1.0.0 六个「版本号」，`matha --version` 与 `pip show matha` 与 README
互相矛盾。现在统一到 `__version__`。
"""
from __future__ import annotations

#: PEP 625 风格的发布版本（MAJOR.MINOR.PATCH）
__version__ = "4.6.0"

#: 兼容旧写法：`from src.matha_main import VERSION` 时代的习惯名，与 `__version__` 同值
VERSION = __version__

#: 面向用户的展示串
VERSION_LABEL = f"Matha v{__version__}"

#: 语义化版本三元组（供比较与诊断）
VERSION_INFO = tuple(int(x) for x in __version__.split("."))

#: 内核（L1 纯净层）协议版本：与 `src/plugin_api` 契约、`src/domains/manifest.json`
#: 的 `protocol_version` 一起演进；插件据此判断兼容性，与发行号解耦。
KERNEL_PROTOCOL = 1


def get_version() -> str:
    """返回当前版本号字符串。"""
    return __version__


def version_info() -> dict[str, object]:
    """结构化版本信息（`matha --version --json` 一类诊断输出用）。"""
    return {
        "version": __version__,
        "display": VERSION,
        "label": VERSION_LABEL,
        "tuple": VERSION_INFO,
        "kernel_protocol": KERNEL_PROTOCOL,
    }


__all__ = [
    "KERNEL_PROTOCOL", "VERSION", "VERSION_INFO", "VERSION_LABEL",
    "__version__", "get_version", "version_info",
]
