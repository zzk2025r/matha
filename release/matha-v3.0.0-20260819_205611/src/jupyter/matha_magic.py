# -*- coding: utf-8 -*-
"""Matha Jupyter 集成

提供：
1. IPython 魔法命令（%matha, %%matha）
2. 自动意图解析
3. 可执行代码单元
4. 交互式计算

用法：
  %load_ext matha.jupyter
  %matha 计算 100 以内所有素数
  %%matha
  求解方程 x^2 - 3x + 2 = 0
"""
from __future__ import annotations
import sys
import re
from typing import Any, Dict, Optional

# 确保项目路径在 sys.path 中
sys.path.insert(0, '.')


class MathaMagics:
    """Matha Jupyter 魔法命令。"""

    def __init__(self, shell):
        self.shell = shell
        self._init_magics()

    def _init_magics(self):
        """注册 IPython 魔法命令。"""
        from IPython.core.magic import register_line_magic, register_cell_magic, Magics, magics_class

        @magics_class
        class MathaMagicsClass(Magics):
            @register_line_magic
            def matha(self, line: str) -> Any:
                """单行 Matha 表达式：%matha 计算 100 以内所有素数"""
                return self._execute_matha(line)

            @register_cell_magic
            def matha(self, line: str, cell: str) -> Any:
                """多行 Matha 代码：%%matha\n计算 100 以内所有素数"""
                return self._execute_matha(cell.strip())

            def _execute_matha(self, code: str) -> Any:
                """执行 Matha 代码。"""
                try:
                    from src.intent.intent_decomposer import IntentDecomposer
                    from src.intent.llm_parser import LLMIntentParser
                    from src.intent.mir_generator import MIRGenerator

                    # 1. 意图分解
                    ide = IntentDecomposer()
                    root = ide.decompose(code)

                    # 2. LLM 解析（可选）
                    parser = LLMIntentParser()
                    intent = parser.parse(code)

                    # 3. MIR 代码生成
                    generator = MIRGenerator()
                    mir_code = generator.generate(intent)

                    # 4. 执行
                    result = self._evaluate_mir(mir_code)

                    # 5. 显示结果
                    self._display_result(code, intent, mir_code, result)

                    return result

                except Exception as e:
                    print(f"[Matha] 执行失败: {e}")
                    return None

            def _evaluate_mir(self, mir_code) -> Any:
                """评估 MIR 代码。"""
                # TODO: 集成 MIR 解释器
                return f"MIR 结果: {mir_code}"

            def _display_result(self, code: str, intent, mir_code, result: Any):
                """显示执行结果。"""
                from IPython.display import Markdown, HTML, display

                # 意图摘要
                intent_md = f"""
## Matha 计算结果

**输入**: {code}

**意图类型**: {intent.intent_type.name}
**置信度**: {intent.confidence:.2f}

**MIR 代码**:
```matha
{mir_code.to_math_code()}
```

**结果**: {result}
"""
                display(Markdown(intent_md))


def load_ipython_extension(ipython):
    """IPython 扩展加载入口。"""
    magics = MathaMagics(ipython)
    print("[Matha] Jupyter 扩展已加载")
    print("  %matha <表达式>     — 执行单行 Matha 代码")
    print("  %%matha             — 执行多行 Matha 代码")


def unload_ipython_extension(ipython):
    """IPython 扩展卸载入口。"""
    print("[Matha] Jupyter 扩展已卸载")


# ============================================================
# 使用示例
# ============================================================

"""
# Notebook 使用示例

## 1. 加载扩展
%load_ext matha.jupyter

## 2. 单行计算
%matha 计算 100 以内所有素数

## 3. 多行代码
%%matha
求解方程 x^2 - 3x + 2 = 0
返回所有实数解

## 4. 数学证明
%matha 验证 √2 是无理数

## 5. 微积分
%matha 计算 sin(x) 在 [0, π] 上的积分

## 6. 代数运算
%matha 因式分解 x^2 - 5x + 6
"""
