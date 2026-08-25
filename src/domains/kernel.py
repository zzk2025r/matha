# -*- coding: utf-8 -*-
"""内核数学函数注册。

供 SemanticAnalyzer 和 Interpreter 在初始化时调用，
将 kernel_math 模块的函数注册到内建符号表 / builtins。
"""

from src.domains.kernel_math import _register_kernel_builtins, kernel_symtab_names

# 导出别名，与其他 domain 模块保持一致的命名约定
_register_mechanics = _register_kernel_builtins  # 别名兼容
_register_kernel = _register_kernel_builtins

__all__ = ["_register_kernel_builtins", "kernel_symtab_names", "_register_mechanics", "_register_kernel"]
