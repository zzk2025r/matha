"""Matha 内核 JSON 解析原语。

`解析_JSON(json字符串) → 嵌套列表/字典` 是 codegen 规格树与数据面共用的
最小内核能力，双面单一实现（与 file_builtin 同一布局）：

    宿主侧   src.interp.BUILTINS            —— 经本模块再导出
    VM 侧    src.mbc.vm._default_builtins   —— 注册同一实现
"""
from __future__ import annotations

import json
import logging

from src.kernel.errors import MathaRuntimeError


def parse_json(text) -> object:
    """解析_JSON(json字符串) → 嵌套列表/字典。"""
    try:
        result = json.loads(str(text))
        logging.getLogger("matha.interp").debug(f"parse_json: {text!r} → {result!r}")
        return result
    except (json.JSONDecodeError, TypeError) as e:
        logging.getLogger("matha.interp").debug(f"parse_json FAILED: {text!r} → {e}")
        raise MathaRuntimeError(f"JSON 解析失败: {e}")


__all__ = ["parse_json"]
