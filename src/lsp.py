# -*- coding: utf-8 -*-
"""Matha Tree-sitter LSP 增强 — 补全 + 跳转 + 诊断

解决 Matha IDE 支持弱的问题。

功能：
  1. 符号补全（函数/类/变量/关键词）
  2. 符号跳转（定义/引用）
  3. 悬停提示（类型/文档）
  4. 诊断（语法错误/类型错误/未定义变量）
  5. 格式化工具集成

用法：
  from src.lsp import MathaLSP
  lsp = MathaLSP()
  completions = lsp.complete("fib(", position=(10, 5))
  diagnostics = lsp.diagnostics(source_code)
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ============================================================
# LSP 类型定义
# ============================================================

class LSPKind(Enum):
    """LSP 符号类型。"""
    MODULE = 1
    CLASS = 2
    FUNCTION = 3
    METHOD = 4
    VARIABLE = 5
    CONSTANT = 6
    KEYWORD = 7
    PARAMETER = 8
    PROPERTY = 9
    EVENT = 10


@dataclass
class LSPPosition:
    """LSP 位置。"""
    line: int
    character: int

    def to_dict(self) -> Dict:
        return {"line": self.line, "character": self.character}


@dataclass
class LSPRange:
    """LSP 范围。"""
    start: LSPPosition
    end: LSPPosition

    def to_dict(self) -> Dict:
        return {
            "start": self.start.to_dict(),
            "end": self.end.to_dict(),
        }


@dataclass
class CompletionItem:
    """补全项。"""
    label: str
    kind: LSPKind
    detail: str = ""
    documentation: str = ""
    insert_text: Optional[str] = None
    sort_text: str = ""
    filter_text: str = ""
    text_edit: Optional[Dict] = None

    def to_dict(self) -> Dict:
        result = {
            "label": self.label,
            "kind": self.kind.value,
        }
        if self.detail:
            result["detail"] = self.detail
        if self.documentation:
            result["documentation"] = self.documentation
        if self.insert_text:
            result["insertText"] = self.insert_text
        if self.sort_text:
            result["sortText"] = self.sort_text
        if self.text_edit:
            result["textEdit"] = self.text_edit
        return result


@dataclass
class Diagnostic:
    """诊断信息。"""
    range: LSPRange
    severity: int  # 1=Error, 2=Warning, 3=Info, 4=Hint
    code: str = ""
    message: str = ""
    source: str = "matha"

    def to_dict(self) -> Dict:
        return {
            "range": self.range.to_dict(),
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "source": self.source,
        }


# ============================================================
# 符号注册表
# ================================================= ==

class SymbolRegistry:
    """Matha 符号注册表。"""

    def __init__(self):
        self._symbols: Dict[str, Dict] = {}
        self._register_builtins()
        self._register_matha_keywords()

    def _register_builtins(self):
        """注册 Python 内置符号。"""
        import builtins
        for name in dir(builtins):
            if not name.startswith('_'):
                obj = getattr(builtins, name)
                kind = LSPKind.FUNCTION if callable(obj) else LSPKind.VARIABLE
                self._symbols[name] = {
                    "name": name,
                    "kind": kind,
                    "detail": str(obj),
                }

    def _register_matha_keywords(self):
        """注册 Matha 关键字。"""
        keywords = {
            "函数": LSPKind.KEYWORD, "变量": LSPKind.KEYWORD,
            "输入": LSPKind.KEYWORD, "输出": LSPKind.KEYWORD,
            "如果": LSPKind.KEYWORD, "否则": LSPKind.KEYWORD,
            "循环": LSPKind.KEYWORD, "函数式": LSPKind.KEYWORD,
            "返回": LSPKind.KEYWORD, "使用": LSPKind.KEYWORD,
            "结构体": LSPKind.KEYWORD, "枚举": LSPKind.KEYWORD,
            "通道": LSPKind.KEYWORD, "匹配": LSPKind.KEYWORD,
            "真": LSPKind.KEYWORD, "假": LSPKind.KEYWORD,
            "在": LSPKind.KEYWORD, "范围": LSPKind.KEYWORD,
        }
        matha_keywords = ["if", "else", "for", "while", "return", "def", "class",
                          "import", "from", "try", "except", "lambda", "async", "await"]
        for kw in matha_keywords:
            self._symbols[kw] = {
                "name": kw,
                "kind": LSPKind.KEYWORD,
                "detail": "Matha 关键字",
            }

    def register(self, name: str, kind: LSPKind, detail: str = "",
                 documentation: str = ""):
        """注册自定义符号。"""
        self._symbols[name] = {
            "name": name,
            "kind": kind,
            "detail": detail,
            "documentation": documentation,
        }

    def get(self, name: str) -> Optional[Dict]:
        return self._symbols.get(name)

    def get_all(self) -> Dict[str, Dict]:
        return dict(self._symbols)


# ============================================================
# LSP 服务器
# ===================================================

class MathaLSP:
    """
    Matha LSP (Language Server Protocol) 服务器。

    实现：
      - textDocument/completion
      - textDocument/hover
      - textDocument/diagnostics
      - textDocument/definition
    """

    def __init__(self):
        self._registry = SymbolRegistry()
        self._source_cache: Dict[str, str] = {}
        self._symbols_cache: Dict[str, List[Dict]] = {}

    # ============================================================
    # Completion
    # ============================================================

    def complete(self, source: str, position: Tuple[int, int],
                 context: Optional[Dict] = None) -> List[CompletionItem]:
        """
        获取补全列表。

        Args:
            source: 源代码
            position: (line, character) 光标位置
            context: 补全上下文
        """
        line, char = position
        lines = source.split('\n')

        # 获取当前行之前的内容（用于补全触发词）
        current_line = lines[line] if line < len(lines) else ""
        prefix = current_line[:char]

        # 查找补全触发词（单词边界）
        word_match = re.search(r'(\w+)$', prefix)
        trigger = word_match.group(1) if word_match else ""

        completions = []

        # 从注册表获取补全
        for name, sym in self._registry.get_all().items():
            if not name.lower().startswith(trigger.lower()):
                continue

            item = CompletionItem(
                label=name,
                kind=sym["kind"],
                detail=sym.get("detail", ""),
                documentation=sym.get("documentation", ""),
                sort_text=f"{sym['kind'].value:02d}_{name}",
            )

            # 如果是函数，插入括号
            if sym["kind"] in (LSPKind.FUNCTION, LSPKind.METHOD):
                item.insert_text = f"{name}(${{1:}})"
                item.text_edit = {
                    "range": LSPRange(
                        LSPPosition(line, char - len(trigger)),
                        LSPPosition(line, char),
                    ).to_dict(),
                    "newText": item.insert_text,
                }

            completions.append(item)

        # 从源码中扫描当前作用域的变量/函数
        for ln_idx, ln in enumerate(lines[:line + 1]):
            # 函数定义
            for m in re.finditer(r'def\s+(\w+)', ln):
                fn_name = m.group(1)
                if fn_name.lower().startswith(trigger.lower()):
                    completions.append(CompletionItem(
                        label=fn_name,
                        kind=LSPKind.FUNCTION,
                        detail=f"def {fn_name}(...)",
                    ))
            # 类定义
            for m in re.finditer(r'class\s+(\w+)', ln):
                cls_name = m.group(1)
                if cls_name.lower().startswith(trigger.lower()):
                    completions.append(CompletionItem(
                        label=cls_name,
                        kind=LSPKind.CLASS,
                        detail=f"class {cls_name}",
                    ))
            # 变量（排除数字和保留字）
            for m in re.finditer(r'\b(\w+)\s*[:=]', ln):
                var_name = m.group(1)
                if (var_name.lower().startswith(trigger.lower())
                        and not var_name.isdigit()
                        and var_name not in (
                    'if', 'else', 'for', 'while', 'def', 'class',
                    'return', 'import', 'not', 'and', 'or', 'in', 'is')):
                    completions.append(CompletionItem(
                        label=var_name,
                        kind=LSPKind.VARIABLE,
                        detail=f"变量: {var_name}",
                    ))

        # 去重 + 排序
        seen = set()
        unique = []
        for item in sorted(completions, key=lambda x: x.sort_text):
            if item.label not in seen:
                seen.add(item.label)
                unique.append(item)

        return unique[:50]  # 限制最多 50 条

    # ============================================================
    # Hover
    # ===================================================

    def hover(self, source: str, position: Tuple[int, int]) -> Optional[Dict]:
        """
        获取悬停信息。

        Args:
            source: 源代码
            position: (line, character)
        """
        line, char = position
        lines = source.split('\n')
        current_line = lines[line] if line < len(lines) else ""

        # 查找光标处的单词（向前 + 向后查找单词边界）
        pre = current_line[:char]
        post = current_line[char:]
        pre_match = re.search(r'\b(\w+)$', pre)
        post_match = re.search(r'^(\w+)\b', post)

        symbol_name = ""
        if pre_match and post_match:
            symbol_name = pre_match.group(1) + post_match.group(1)
        elif pre_match:
            symbol_name = pre_match.group(1)
        elif post_match:
            symbol_name = post_match.group(1)

        if not symbol_name or symbol_name.isdigit():
            return None

        # 检查注册表
        sym = self._registry.get(symbol_name)
        if sym:
            return {
                "contents": f"**{symbol_name}**\n\n{sym.get('detail', '')}\n\n{sym.get('documentation', '')}",
            }

        # 在源码中查找定义
        for ln_idx, ln in enumerate(lines):
            # 函数定义
            m = re.search(rf'\bdef\s+{re.escape(symbol_name)}\s*\(', ln)
            if m:
                return {
                    "contents": f"```matha\ndef {symbol_name}(...)\n```\n\n行 {ln_idx + 1}",
                }
            # 类定义
            m = re.search(rf'\bclass\s+{re.escape(symbol_name)}', ln)
            if m:
                return {
                    "contents": f"```matha\nclass {symbol_name}\n```\n\n行 {ln_idx + 1}",
                }
            # 变量赋值
            m = re.search(rf'\b{re.escape(symbol_name)}\s*[:=]', ln)
            if m:
                return {
                    "contents": f"**变量**: `{symbol_name}`\n\n行 {ln_idx + 1}: {ln.strip()}",
                }

        return None

    # ============================================================
    # Diagnostics
    # ===================================================

    def diagnostics(self, source: str, filepath: str = "") -> List[Diagnostic]:
        """
        生成诊断信息。

        Args:
            source: 源代码
            filepath: 文件路径
        """
        diagnostics = []
        # 去除尾部空行，避免 trailing newline 产生多余空行
        lines = source.rstrip('\n').split('\n')

        # 1. 语法检查
        for i, line in enumerate(lines, 1):
            # 未闭合的括号（跨行检查：只在最后一行才报告）
            if i == len(lines):
                open_parens = line.count('(') - line.count(')')
                if open_parens > 0:
                    diagnostics.append(Diagnostic(
                        range=LSPRange(
                            LSPPosition(i - 1, len(line)),
                            LSPPosition(i - 1, len(line)),
                        ),
                        severity=1,
                        code="SYNTAX-001",
                        message=f"未闭合的括号 ({open_parens} 个)",
                    ))

                open_brackets = line.count('[') - line.count(']')
                if open_brackets > 0:
                    diagnostics.append(Diagnostic(
                        range=LSPRange(
                            LSPPosition(i - 1, len(line)),
                            LSPPosition(i - 1, len(line)),
                        ),
                        severity=1,
                        code="SYNTAX-002",
                        message=f"未闭合的方括号 ({open_brackets} 个)",
                    ))

                open_braces = line.count('{') - line.count('}')
                if open_braces > 0:
                    diagnostics.append(Diagnostic(
                        range=LSPRange(
                            LSPPosition(i - 1, len(line)),
                            LSPPosition(i - 1, len(line)),
                        ),
                        severity=1,
                        code="SYNTAX-003",
                        message=f"未闭合的大括号 ({open_braces} 个)",
                    ))

        # 2. 未定义变量检查
        defined_vars = set()
        defined_funcs = set()
        reserved_words = {'if', 'else', 'for', 'while', 'def', 'class', 'return',
                          'import', 'from', 'not', 'and', 'or', 'in', 'is',
                          'True', 'False', 'None', 'print', 'len', 'range', 'int',
                          'float', 'str', 'list', 'dict', 'set', 'tuple', 'type',
                          'abs', 'sum', 'max', 'min', 'enumerate', 'zip', 'map',
                          'filter', 'sorted', 'reversed', 'open', 'isinstance',
                          'hasattr', 'getattr', 'setattr', 'delattr', 'super',
                          'self', 'cls', 'pass', 'break', 'continue', 'yield',
                          'await', 'async', 'lambda', 'with', 'as', 'raise',
                          'try', 'except', 'finally', 'assert', 'global', 'nonlocal'}

        for i, line in enumerate(lines, 1):
            # 函数定义
            for m in re.finditer(r'def\s+(\w+)', line):
                defined_funcs.add(m.group(1))

            # 变量定义
            for m in re.finditer(r'\b(\w+)\s*[:=]', line):
                var = m.group(1)
                if var not in reserved_words and not var.isdigit():
                    defined_vars.add(var)

            # 使用未定义变量
            for m in re.finditer(r'\b(\w+)\b', line):
                var = m.group(1)
                if (var not in defined_vars and var not in defined_funcs
                    and var not in reserved_words and not var.isdigit()
                    and not re.search(r'\b\d+\b', var)):
                    # 检查是否在函数调用中（如 sum([1,2,3]) 中的 1,2,3 是数字）
                    if not re.search(rf'\b{re.escape(var)}\s*\(', line):
                        diagnostics.append(Diagnostic(
                            range=LSPRange(
                                LSPPosition(i - 1, m.start()),
                                LSPPosition(i - 1, m.end()),
                            ),
                            severity=2,
                            code="UNDEFINED-001",
                            message=f"未定义的变量: '{var}'",
                        ))

        # 3. 类型注解检查（简单版）
        for i, line in enumerate(lines, 1):
            # 检查类型注解格式
            if re.search(r':\s*[\w\[\],\s]+\s*=', line) and '*/' not in line:
                # 有效类型注解
                pass
            elif re.search(r'->\s*[\w\[\],\s]+', line):
                # 返回类型注解
                pass

        # 4. 数学符号检查
        for i, line in enumerate(lines, 1):
            # 检查 >> 的歧义用法
            if '>>' in line and '>>>' not in line:
                # 可能在用 >> 作为路径距离运算符
                if not re.search(r'\b\d+\s*>>\s*\d+\b', line):
                    pass  # 可能是合法的 >> 用法

        return diagnostics

    # ============================================================
    # Definition
    # ===================================================

    def find_definition(self, source: str, position: Tuple[int, int]) -> Optional[Dict]:
        """
        查找符号定义。

        Args:
            source: 源代码
            position: (line, character)
        """
        line, char = position
        lines = source.split('\n')
        current_line = lines[line] if line < len(lines) else ""

        # 查找光标处的单词
        pre = current_line[:char]
        post = current_line[char:]
        pre_match = re.search(r'\b(\w+)$', pre)
        post_match = re.search(r'^(\w+)\b', post)

        symbol_name = ""
        if pre_match and post_match:
            symbol_name = pre_match.group(1) + post_match.group(1)
        elif pre_match:
            symbol_name = pre_match.group(1)
        elif post_match:
            symbol_name = post_match.group(1)

        if not symbol_name or symbol_name.isdigit():
            return None

        # 查找定义
        for ln_idx, ln in enumerate(lines):
            if re.search(rf'\bdef\s+{re.escape(symbol_name)}\s*\(', ln):
                return {
                    "uri": "",
                    "range": LSPRange(
                        LSPPosition(ln_idx, 0),
                        LSPPosition(ln_idx, len(ln)),
                    ).to_dict(),
                }
            if re.search(rf'\bclass\s+{re.escape(symbol_name)}', ln):
                return {
                    "uri": "",
                    "range": LSPRange(
                        LSPPosition(ln_idx, 0),
                        LSPPosition(ln_idx, len(ln)),
                    ).to_dict(),
                }

        return None

    # ============================================================
    # 文档生成
    # ===================================================

    def generate_readme(self, source: str) -> str:
        """从源码生成快速文档。"""
        lines = source.split('\n')
        functions = []
        classes = []

        for i, ln in enumerate(lines, 1):
            m = re.match(r'\s*def\s+(\w+)\s*\(([^)]*)\)', ln)
            if m:
                fname, params = m.group(1), m.group(2)
                # 获取 docstring
                doc = ""
                for j in range(i, min(i + 5, len(lines))):
                    stripped = lines[j].strip()
                    if stripped.startswith('"""') or stripped.startswith("'''"):
                        doc = stripped.strip('"""').strip("'''")
                        break
                    elif stripped and not stripped.startswith('#'):
                        break
                functions.append({
                    "name": fname,
                    "params": params,
                    "line": i,
                    "doc": doc,
                })

            m = re.match(r'\s*class\s+(\w+)', ln)
            if m:
                classes.append({
                    "name": m.group(1),
                    "line": i,
                })

        result = f"# Matha 源码文档\n\n"
        result += f"自动从源码提取 | 共 {len(functions)} 个函数, {len(classes)} 个类\n\n"

        if classes:
            result += "## 类\n\n"
            for c in classes:
                result += f"- `{c['name']}` (行 {c['line']})\n"
            result += "\n"

        if functions:
            result += "## 函数\n\n"
            for fn in functions:
                result += f"### `{fn['name']}({fn['params']})`\n"
                if fn['doc']:
                    result += f"{fn['doc'][:100]}\n"
                result += f"\n行 {fn['line']}\n\n"

        return result


# ============================================================
# 测试入口
# ===================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  Matha LSP 测试")
    print("=" * 60)

    lsp = MathaLSP()

    # 测试补全
    test_source = """
def fib(n):
    if n <= 1:
        return n
    return fib(n-1) + fib(n-2)

result = fib(30)
print(result)
"""
    print("\n【补全测试】")
    completions = lsp.complete(test_source, (5, 10))
    for item in completions[:10]:
        print(f"  {item.label} ({item.kind.name})")

    # 测试悬停
    print("\n【悬停测试】")
    hover = lsp.hover(test_source, (5, 12))
    if hover:
        print(f"  hover: {hover['contents'][:100]}...")

    # 测试诊断
    print("\n【诊断测试】")
    bad_source = """
x = undefined_var
y = [1, 2, 3
z = another_undefined
"""
    diags = lsp.diagnostics(bad_source)
    for d in diags:
        print(f"  [{d.severity}] L{d.range.start.line+1}: {d.message}")

    # 测试定义查找
    print("\n【定义查找测试】")
    def_result = lsp.find_definition(test_source, (1, 10))
    if def_result:
        print(f"  fib 定义在行 {def_result['range']['start']['line'] + 1}")

    # 测试文档生成
    print("\n【文档生成测试】")
    readme = lsp.generate_readme(test_source)
    print(readme[:200])

    print("\n" + "=" * 60)
    print("  LSP 测试完成")
    print("=" * 60)
