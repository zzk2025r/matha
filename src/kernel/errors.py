# -*- coding: utf-8 -*-
"""内核运行时错误类型（单一来源）。

重构前 `MathaRuntimeError` 只在 `src/interp.py` 里定义，字节码 VM 要给出同款
错误就必须 import 解释器 —— 而「内核不依赖解释器」是本次重构的冻结契约。
故把这个类型下沉到内核：

- `src/interp.py` 从此 import 再导出（类对象同一，`except MathaRuntimeError`
  的既有写法与测试断言全部不变）；
- `src/mbc/vm.py` 用它在运算/内建层面抛出与解释器**逐字一致**的消息文本，
  使 `try { ... } catch (e) { e }` 取到的 `e` 在主链与遗留后端上相同。

基底选 `RuntimeError`（而非 `Exception`）：`MathaRuntimeError` 是运行时错误，
`except RuntimeError` 的宿主代码应能一并捕获；`except Exception` 行为不变。

纯标准库，无任何第三方依赖（受 tests/test_kernel_purity.py 守卫）。
"""
from __future__ import annotations


class MathaRuntimeError(RuntimeError):
    """运行时错误，携带代码位置信息（行/列）。"""

    line: int | None
    col: int | None

    def __init__(self, msg: str, line: int | None = None, col: int | None = None):
        super().__init__(msg)
        self.line = line
        self.col = col

    def __str__(self) -> str:
        return super().__str__()


class MathaUndefinedNameError(MathaRuntimeError, KeyError):
    """未定义变量：同时是 `MathaRuntimeError` 与 `KeyError`。

    字节码 VM 的全局表是 `dict`，名字未命中时历史上抛 `KeyError`（宿主与
    既有测试依赖 `except KeyError`）；而遗留解释器给用户的文本是
    `未定义变量 'x'`。两个后端归一到一条主线后，同一源串在 `catch (e) { 输出(e) }`
    里取到的文本必须相同，故用一个兼具两种身份的类：

    - 消息主体与解释器逐字一致（`__str__` 取 RuntimeError 版本，KeyError 默认会多一层引号）；
    - `except KeyError` / `pytest.raises(KeyError)` 的既有写法仍然成立。
    """

    def __str__(self) -> str:
        return RuntimeError.__str__(self)


__all__ = ["MathaRuntimeError", "MathaUndefinedNameError"]
