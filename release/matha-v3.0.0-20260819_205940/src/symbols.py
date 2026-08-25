"""符号表与作用域管理。

为语义分析器提供变量/函数/类型的定义追踪与引用解析。
作用域层级：全局 → 模块 → 代码块 → 段。
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Symbol:
    """符号表条目。"""

    name: str
    kind: str            # "variable" | "function" | "type" | "module" | "parameter" | "segment"
    decl: Any            # 定义处的 AST 节点
    line: int = 0
    type_info: Any = None    # 类型信息（骨架阶段简化为 None 或字符串）
    is_placeholder: bool = False  # True = ？占位符变量


@dataclass
class Scope:
    """作用域。"""

    name: str            # 作用域名（如 "global"、"module:math"、"seg#1"）
    parent: Optional["Scope"] = None
    symbols: dict[str, Symbol] = field(default_factory=dict)
    children: list["Scope"] = field(default_factory=list)

    def define(self, sym: Symbol) -> bool:
        """在当前作用域定义符号。若已存在同名符号则返回 False。"""
        if sym.name in self.symbols:
            return False
        self.symbols[sym.name] = sym
        return True

    def resolve(self, name: str) -> Optional[Symbol]:
        """从当前作用域向上查找符号。"""
        if name in self.symbols:
            return self.symbols[name]
        if self.parent is not None:
            return self.parent.resolve(name)
        return None

    def resolve_local(self, name: str) -> Optional[Symbol]:
        """仅在当前作用域查找（不向上）。"""
        return self.symbols.get(name)

    def child(self, name: str) -> "Scope":
        """创建并挂载子作用域。"""
        sub = Scope(name=name, parent=self)
        self.children.append(sub)
        return sub


class SymbolTable:
    """符号表：管理作用域栈。"""

    def __init__(self):
        self.global_scope = Scope(name="global")
        self.current = self.global_scope
        self.all_scopes: list[Scope] = [self.global_scope]

    def push(self, name: str) -> Scope:
        """进入新作用域。"""
        sub = self.current.child(name)
        self.all_scopes.append(sub)
        self.current = sub
        return sub

    def pop(self) -> Scope:
        """退出当前作用域，返回父作用域。"""
        if self.current.parent is None:
            return self.current
        self.current = self.current.parent
        return self.current

    def define(self, name: str, kind: str, decl: Any, line: int = 0,
               type_info: Any = None, is_placeholder: bool = False) -> bool:
        """在当前作用域定义符号。"""
        sym = Symbol(
            name=name, kind=kind, decl=decl, line=line,
            type_info=type_info, is_placeholder=is_placeholder,
        )
        return self.current.define(sym)

    def resolve(self, name: str) -> Optional[Symbol]:
        """解析符号引用。"""
        return self.current.resolve(name)

    def resolve_local(self, name: str) -> Optional[Symbol]:
        """仅在当前作用域解析（不向上查找）。"""
        return self.current.resolve_local(name)


# ============================================================
# 段内步骤追踪（M3.1/M3.2：5 步固定顺序）
# ============================================================

# 段内 5 步的固定顺序枚举
SEG_STEPS = {
    "command": 1,       # ① 段级命令  #N：【命令】
    "variable": 2,      # ② 段级变量  @N：变量
    "formula_q": 3,     # ③ ？公式    #N：？+？=？
    "formula_letter": 4,  # ④ 字母公式  #N：a+b=c
    "output": 5,        # ⑤ 输出      #N：[结果]
}

# 步骤中文名（用于错误信息）
STEP_NAMES = {
    "command": "命令",
    "variable": "变量",
    "formula_q": "？公式",
    "formula_letter": "字母公式",
    "output": "输出",
}


@dataclass
class SegmentTracker:
    """追踪单个段内的 5 步执行顺序。

    M3.1/M3.2 规则：命令→变量→？公式→字母公式→输出，顺序不可调换，可省略。
    """
    seg_id: Optional[int]
    seen_steps: list[str] = field(default_factory=list)
    # 记录每步的 AST 节点（用于公式对应检查）
    step_nodes: dict[str, Any] = field(default_factory=dict)

    def record_step(self, step: str, node: Any) -> Optional[str]:
        """记录一个步骤，返回错误信息（若有顺序违规）。"""
        expected_order = SEG_STEPS[step]
        # 检查是否有更晚的步骤已经出现过
        for prev_step in self.seen_steps:
            if SEG_STEPS[prev_step] > expected_order:
                return (
                    f"段 {self.seg_id} 内步骤顺序违规："
                    f"'{STEP_NAMES[step]}'（第{expected_order}步）出现在 "
                    f"'{STEP_NAMES[prev_step]}'（第{SEG_STEPS[prev_step]}步）之后；"
                    f"固定顺序为：命令→变量→？公式→字母公式→输出"
                )
        self.seen_steps.append(step)
        self.step_nodes[step] = node
        return None

    def get_step(self, step: str) -> Optional[Any]:
        return self.step_nodes.get(step)


# ============================================================
# 资源模式识别（M3.2：命令/输出独立读取能力）
# ============================================================

# 资源类型枚举
RESOURCE_URL = "url"           # http:// 或 https://
RESOURCE_FILE = "file"         # /path/to/file 或 C:\path 或 d:\path
RESOURCE_DIR = "directory"     # /path/to/dir/ 或 d:\dir\
RESOURCE_PORT = "port"         # host:port 或 localhost:8080
RESOURCE_TEXT = "text"         # 纯文本命令/输出（非资源）


def detect_resource_type(text: str) -> str:
    """识别命令/输出内容中的资源类型（M3.2 一等能力）。

    判断规则（按优先级）：
        1. 包含 :// → URL
        2. 以 / 或盘符开头（如 /data、d:\\）→ 文件/目录
        3. 相对路径含分隔符（如 ./data、data/file）→ 文件
        4. 匹配 host:port 模式 → 端口
        5. 含字母扩展名的相对文件名（如 config_loader.matha、sub.py）→ 文件
        6. 其他 → 纯文本
    """
    if not text:
        return RESOURCE_TEXT

    # URL: http:// https:// ftp:// 等
    if "://" in text:
        return RESOURCE_URL

    # Windows 盘符路径: d:\path 或 d:/path
    if len(text) >= 3 and text[1] == ":" and text[2] in ("\\", "/"):
        return RESOURCE_DIR if text.endswith(("/", "\\")) else RESOURCE_FILE

    # Unix 绝对路径: /path/to/file
    if text.startswith("/"):
        return RESOURCE_DIR if text.endswith("/") else RESOURCE_FILE

    # 相对路径含路径分隔符: ./data 或 data/file
    if text.startswith("./") or ("/" in text and not text.replace("/", "").replace(".", "").isspace()):
        # 排除纯标识符（如 file_2.matha 也算文件引用）
        if "/" in text or "\\" in text:
            return RESOURCE_FILE

    # host:port 模式（如 localhost:8080）
    if ":" in text:
        parts = text.rsplit(":", 1)
        if len(parts) == 2 and parts[1].isdigit():
            return RESOURCE_PORT

    # 相对文件名：含 . 且最后一段扩展名为纯字母（如 config_loader.matha、sub.py）
    # 排除数字小数（1.5）、版本号（v1.2）——要求扩展名部分为纯字母
    if "." in text:
        ext = text.rsplit(".", 1)[1]
        if ext.isalpha():
            return RESOURCE_FILE

    return RESOURCE_TEXT
