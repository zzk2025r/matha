# -*- coding: utf-8 -*-
"""Matha 结构化异常系统 — v2.3

设计原则：
  1. 类型安全：每个错误阶段有明确的错误类型
  2. 错误链：错误可嵌套，保留完整上下文
  3. 错误组合：多个错误可聚合为一个 CompositeError
  4. 错误恢复：提供 recover() 尝试替代方案
  5. 用户友好：auto_report() 生成自然语言错误报告

使用示例：
    try:
        result = parse_intent("计算100以内所有素数")
    except MathaIntentError as e:
        print(e.report())
        print(e.suggestions())
"""
from __future__ import annotations
import threading
import traceback
from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum, auto
from src.result import Ok, Err, MathaResultError


# Result 类型别名（动态）
Result = type


# ============================================================
# 错误阶段枚举
# ============================================================

class ErrorStage(Enum):
    """错误发生阶段。"""
    PARSING = auto()       # 语法解析
    LEXING = auto()        # 词法分析
    CLASSIFYING = auto()   # 意图分类
    PARAM_EXTRACTING = auto()  # 参数提取
    CODE_GENERATING = auto()   # 代码生成
    EXECUTING = auto()     # 代码执行
    VALIDATING = auto()    # 结果验证
    UNKNOWN = auto()


class ErrorSeverity(Enum):
    """错误严重程度。"""
    INFO = 0           # 提示（可忽略）
    WARNING = 1        # 警告（部分失败）
    ERROR = 2          # 错误（操作失败）
    FATAL = 3          # 致命（无法恢复）

    def __lt__(self, other: "ErrorSeverity") -> bool:
        return self.value < other.value

    def __gt__(self, other: "ErrorSeverity") -> bool:
        return self.value > other.value


# ============================================================
# 基础错误类
# ============================================================

class MathaError(Exception):
    """Matha 结构化异常基类（继承 Exception 以支持 raise/except）。"""
    __slots__ = ('message', 'stage', 'severity', 'code', 'suggestions',
                 'context', 'cause', 'stack', 'children')

    def __init__(self, message: str = "", stage: ErrorStage = ErrorStage.UNKNOWN,
                 severity: ErrorSeverity = ErrorSeverity.ERROR,
                 code: str = "", suggestions: list = None,
                 context: dict = None, cause: "MathaError" = None,
                 stack: list = None, children: list = None):
        self.message = message
        self.stage = stage
        self.severity = severity
        self.code = code
        self.suggestions = suggestions or []
        self.context = context or {}
        self.cause = cause
        self.stack = stack or []
        self.children = children or []
        Exception.__init__(self, message)

    def with_cause(self, cause: "MathaError") -> "MathaError":
        """链接因果错误。"""
        self.cause = cause
        self.stack = [f"  caused by: {cause.message}"] + (cause.stack or [])
        return self

    def add_child(self, child: "MathaError") -> "MathaError":
        """添加子错误。"""
        self.children.append(child)
        return self

    def add_suggestion(self, suggestion: str) -> "MathaError":
        """添加恢复建议。"""
        if suggestion not in self.suggestions:
            self.suggestions.append(suggestion)
        return self

    def report(self, indent: int = 0) -> str:
        """生成错误报告。"""
        prefix = "  " * indent
        lines = [f"{prefix}[{self.severity.name}] {self.stage.name}: {self.message}"]
        if self.code:
            lines.append(f"{prefix}  Code: {self.code}")
        if self.children:
            lines.append(f"{prefix}  Sub-errors:")
            for child in self.children:
                lines.append(child.report(indent + 2))
        if self.cause:
            lines.append(f"{prefix}  Caused by:")
            lines.append(self.cause.report(indent + 2))
        if self.stack:
            lines.append(f"{prefix}  Stack:")
            for frame in self.stack:
                lines.append(f"{prefix}    {frame}")
        return "\n".join(lines)

    def suggestions_text(self) -> str:
        """生成建议文本。"""
        if not self.suggestions:
            return "请检查输入或联系开发者。"
        lines = ["建议："]
        for i, s in enumerate(self.suggestions, 1):
            lines.append(f"  {i}. {s}")
        return "\n".join(lines)

    def to_result(self) -> Err:
        """转换为 Result 错误。"""
        return Err(self.report(), trace=self._format_trace())

    def _format_trace(self) -> str:
        """格式化调用栈。"""
        return "\n".join(f"  {line}" for line in self.stack)


# ============================================================
# 阶段特定错误
# ============================================================

class ParseError(MathaError):
    """语法解析错误。"""
    def __init__(self, message: str, line: int = 0, col: int = 0, expected: str = ""):
        super().__init__(
            message=message,
            stage=ErrorStage.PARSING,
            code=f"PARSE:{line}:{col}" if line else "PARSE",
        )
        if expected:
            self.add_suggestion(f"期望: {expected}")
        if line:
            self.context["line"] = line
            self.context["col"] = col

    def add_suggestion(self, suggestion: str) -> "ParseError":
        self.suggestions.append(suggestion)
        return self


class ClassifyError(MathaError):
    """意图分类错误。"""
    def __init__(self, message: str, candidates: list[str] = None):
        super().__init__(
            message=message,
            stage=ErrorStage.CLASSIFYING,
            severity=ErrorSeverity.WARNING,
        )
        if candidates:
            self.add_suggestion(f"可能的意图: {', '.join(candidates)}")
        self.add_suggestion("尝试重新表述您的请求，加入更多关键词。")


class ParamExtractError(MathaError):
    """参数提取错误。"""
    def __init__(self, message: str, expected_type: str = "", actual_type: str = ""):
        super().__init__(
            message=message,
            stage=ErrorStage.PARAM_EXTRACTING,
            severity=ErrorSeverity.ERROR,
        )
        if expected_type:
            self.add_suggestion(f"期望类型: {expected_type}")
        if actual_type:
            self.context["actual_type"] = actual_type


class CodeGenError(MathaError):
    """代码生成错误。"""
    def __init__(self, message: str, target_lang: str = "python"):
        super().__init__(
            message=message,
            stage=ErrorStage.CODE_GENERATING,
            severity=ErrorSeverity.ERROR,
        )
        self.add_suggestion(f"尝试使用目标语言: {target_lang}")
        self.add_suggestion("检查参数是否完整。")


class ExecError(MathaError):
    """代码执行错误。"""
    def __init__(self, message: str, exception: Exception = None):
        super().__init__(
            message=message,
            stage=ErrorStage.EXECUTING,
            severity=ErrorSeverity.ERROR,
        )
        if exception:
            self.stack = traceback.format_exception(type(exception), exception, exception.__traceback__)
            self.add_suggestion("检查生成的代码是否有语法错误。")
            self.add_suggestion("验证参数值是否合法。")


class CompositeError(MathaError):
    """复合错误：多个错误聚合。"""
    def __init__(self, message: str, errors: list[MathaError] = None):
        super().__init__(
            message=message,
            stage=ErrorStage.UNKNOWN,
            severity=ErrorSeverity.ERROR,
        )
        if errors:
            for e in errors:
                self.add_child(e)
            # 提升严重级别为最严重的子错误
            max_sev = max((e.severity for e in errors), default=ErrorSeverity.ERROR)
            self.severity = max_sev

    def recover(self) -> Optional[MathaError]:
        """尝试从复合错误中恢复。"""
        # 找出可恢复的错误
        recoverable = [e for e in self.children if e.severity in
                       (ErrorSeverity.INFO, ErrorSeverity.WARNING)]
        if recoverable:
            # 返回第一个可恢复错误，标记为已尝试恢复
            first = recoverable[0]
            first.add_suggestion("已尝试自动恢复。")
            return first
        return None


# ============================================================
# Result 扩展：带上下文的错误传播
# ============================================================

def ok_with_context(value, **ctx) -> Result:
    """创建带上下文的 Ok。"""
    return Ok(value, label=str(ctx))


def err_with_stage(message: str, stage: ErrorStage, **kwargs) -> Result:
    """创建带阶段的 Err。"""
    error = MathaError(message=message, stage=stage, **kwargs)
    return Err(error)


def map_errors(fn, *args, stage: ErrorStage = ErrorStage.UNKNOWN, **kwargs) -> Result:
    """执行函数并映射错误到结构化错误。"""
    try:
        return Ok(fn(*args, **kwargs))
    except MathaError as e:
        e.stage = stage
        return Err(e)
    except Exception as e:
        return Err(MathaError(
            message=f"{type(e).__name__}: {e}",
            stage=stage,
        ))


# ============================================================
# 错误恢复策略
# ============================================================

class RecoveryStrategy:
    """错误恢复策略注册表（读写锁分离，v2.4 优化）。

    锁层次结构：
      _suggestion_lock (Level 0): 最细粒度，仅保护 suggestions 列表
      _read_lock   (Level 1): 保护 _strategies 字典读取
      _write_lock  (Level 2): 保护 _strategies 字典写入

    规则：持有高层锁时不获取低层锁，避免死锁。
    """

    _strategies: dict[ErrorStage, list] = {}

    # Level 1: 读锁（高频，保护读取）
    _read_lock = threading.RLock()
    # Level 2: 写锁（低频，保护写入）
    _write_lock = threading.Lock()
    # Level 0: 建议修改锁（最细粒度）
    _suggestion_lock = threading.Lock()

    @classmethod
    def register(cls, stage: ErrorStage):
        """装饰器：注册恢复策略（写锁，Level 2）。"""
        def decorator(fn):
            with cls._write_lock:
                if stage not in cls._strategies:
                    cls._strategies[stage] = []
                cls._strategies[stage].append(fn)
            return fn
        return decorator

    @classmethod
    def try_recover(cls, error: MathaError) -> Optional[MathaError]:
        """尝试所有注册的恢复策略（读锁 → 锁外执行 → 建议锁）。

        锁使用策略：
          1. 获取读锁 → 复制策略列表 → 释放读锁（快，O(n) 但 n 很小）
          2. 在锁外执行策略函数（慢，不持有锁，允许其他线程并发读取）
          3. 若需要修改 error.suggestions，获取建议锁（快，仅追加字符串）
        """
        # Step 1: 读锁保护下复制策略列表
        with cls._read_lock:
            strategies = list(cls._strategies.get(error.stage, []))

        # Step 2: 锁外执行策略（不阻塞其他读操作）
        for strategy in strategies:
            try:
                result = strategy(error)
                if result is not None:
                    # Step 3: 仅修改建议时加建议锁
                    with cls._suggestion_lock:
                        suggestion = f"恢复策略成功: {strategy.__name__}"
                        if suggestion not in error.suggestions:
                            error.suggestions.append(suggestion)
                    return result
            except Exception:
                continue

        return None

    @classmethod
    def get_strategy_count(cls, stage: ErrorStage) -> int:
        """获取指定阶段的策略数量（读锁保护）。"""
        with cls._read_lock:
            return len(cls._strategies.get(stage, []))

    # 内置策略名称集合（不会被 clear() 清除）
    _builtin_names: set = set()

    @classmethod
    def _mark_builtin(cls, fn) -> None:
        """标记策略为内置（测试 clear 时保留）。"""
        cls._builtin_names.add(fn.__name__)

    @classmethod
    def clear(cls) -> None:
        """清空测试期间添加的策略，保留内置策略。"""
        with cls._write_lock:
            for stage in list(cls._strategies.keys()):
                original = cls._strategies[stage]
                cls._strategies[stage] = [
                    fn for fn in original if fn.__name__ in cls._builtin_names
                ]


# ============================================================
# 预定义的恢复策略
# ============================================================

@RecoveryStrategy.register(ErrorStage.CLASSIFYING)
def _recover_classify(error: MathaError) -> Optional[MathaError]:
    """意图分类失败的恢复策略。"""
    if "关键词匹配" in error.message or "未知意图" in error.message:
        error.add_suggestion("尝试加入更多描述性词汇，如'计算'、'排序'、'转换'等。")
        error.add_suggestion("检查是否有拼写错误。")
        return None
    return None
RecoveryStrategy._mark_builtin(_recover_classify)


@RecoveryStrategy.register(ErrorStage.PARAM_EXTRACTING)
def _recover_params(error: MathaError) -> Optional[MathaError]:
    """参数提取失败的恢复策略。"""
    if "类型不匹配" in error.message:
        error.add_suggestion("检查数字格式，使用阿拉伯数字。")
        return None
    if "缺少必要参数" in error.message:
        error.add_suggestion("请补充缺失的参数信息。")
        return None
    return None
RecoveryStrategy._mark_builtin(_recover_params)


@RecoveryStrategy.register(ErrorStage.CODE_GENERATING)
def _recover_codegen(error: MathaError) -> Optional[MathaError]:
    """代码生成失败的恢复策略。"""
    if "参数不足" in error.message:
        error.add_suggestion("尝试使用默认参数值。")
        error.add_suggestion("简化请求，减少参数数量。")
        return None
    return None
RecoveryStrategy._mark_builtin(_recover_codegen)


@RecoveryStrategy.register(ErrorStage.EXECUTING)
def _recover_exec(error: MathaError) -> Optional[MathaError]:
    """执行失败的恢复策略。"""
    if "NameError" in error.message:
        error.add_suggestion("检查变量名是否正确定义。")
        return None
    if "TypeError" in error.message:
        error.add_suggestion("检查参数类型是否匹配。")
        return None
    if "ZeroDivisionError" in error.message:
        error.add_suggestion("避免除零操作。")
        return None
    return None
RecoveryStrategy._mark_builtin(_recover_exec)


# ============================================================
# 便捷工厂函数
# ============================================================

def classify_error(msg: str, candidates: list = None) -> MathaError:
    return ClassifyError(msg, candidates)


def parse_error(msg: str, line: int = 0, col: int = 0, expected: str = ""):
    return ParseError(msg, line, col, expected)


def param_error(msg: str, expected: str = "", actual: str = ""):
    return ParamExtractError(msg, expected, actual)


def codegen_error(msg: str, lang: str = "python"):
    return CodeGenError(msg, lang)


def exec_error(msg: str, exc: Exception = None):
    return ExecError(msg, exc)


def composite_error(msg: str, errors: list = None):
    return CompositeError(msg, errors)
