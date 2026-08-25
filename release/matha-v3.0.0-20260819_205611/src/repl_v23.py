# -*- coding: utf-8 -*-
"""v2.3 异常处理集成到 REPL — 增强版

改动点：
  1. REPL 使用 EnhancedIntentParser 替代基础 IntentParser
  2. 自然语言模式下显示结构化错误报告（含恢复建议）
  3. 错误计数区分 WARNING/ERROR
  4. 提供 "recover" 命令尝试自动恢复
"""
from __future__ import annotations
import sys
import os
import logging
import threading
from typing import Any, Optional
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.parser import Parser
from src import ast_nodes as ast
from src.interp import interpret
from src.enhanced_intent import (
    EnhancedIntentParser,
    IntentParseContext,
    ErrorAggregator,
    explain_intent_safe,
    execute_intent,
)
from src.errors import (
    MathaError, ErrorStage, ErrorSeverity,
    CompositeError, RecoveryStrategy,
)
from src.result import Ok, Err
from src.stdlib.core import register_core_builtins


logger = logging.getLogger("matha.repl")

PROMPT_EXPR = "matha> "
PROMPT_NL = "nl> "
PROMPT_INTENT = "intent> "


@dataclass
class REPLState:
    """REPL 运行时状态（v2.3 增强，线程安全）。"""
    variables: dict[str, Any] = field(default_factory=dict)
    history: list[str] = field(default_factory=list)
    intent_parser: Optional[EnhancedIntentParser] = None
    error_log: list[MathaError] = field(default_factory=list)
    _error_lock: threading.RLock = field(default_factory=threading.RLock, repr=False, compare=False)
    mode: str = "matha"
    continue_loop: bool = True
    success_count: int = 0
    error_count: int = 0
    warning_count: int = 0

    def append_error(self, error: MathaError) -> None:
        """线程安全地追加错误到日志。"""
        with self._error_lock:
            self.error_log.append(error)

    def get_error_log(self) -> list[MathaError]:
        """线程安全地获取错误日志副本。"""
        with self._error_lock:
            return list(self.error_log)


class MathaREPL:
    """Matha 交互式 REPL v2.3 — 集成结构化异常处理。"""

    MODES = {
        "matha": ("matha> ", "Matha 表达式模式"),
        "nl": ("nl> ", "自然语言模式"),
        "intent": ("intent> ", "意图分析模式"),
        "help": ("> ", "帮助模式"),
        "quit": (None, "退出"),
    }

    def __init__(self, debug: bool = False):
        self.state = REPLState(intent_parser=EnhancedIntentParser())
        self.debug = debug
        if debug:
            logging.basicConfig(level=logging.DEBUG,
                              format="%(name)s [%(levelname)s] %(message)s")
        else:
            logging.basicConfig(level=logging.WARNING)

    def run(self) -> None:
        """运行 REPL 主循环。"""
        self._print_banner()
        try:
            while self.state.continue_loop:
                try:
                    line = self._read_input()
                except EOFError:
                    break
                except KeyboardInterrupt:
                    print("\n(按 Ctrl+C 退出)")
                    continue

                line = line.strip()
                if not line:
                    continue

                self.state.history.append(line)
                self._process_line(line)

        except Exception as e:
            logger.error("REPL 异常: %s", e)
        finally:
            self._print_summary()

    def _print_banner(self) -> None:
        print()
        print("=" * 60)
        print("  Matha 自成长引擎 REPL v2.3（集成结构化异常处理）")
        print("  命令: help | mode <matha|nl|int> | quit | exit | recover")
        print("  自然语言: '计算 3 加 5' | '找出 1 到 100 的素数'")
        print("=" * 60)
        print()

    def _read_input(self) -> str:
        mode = self.state.mode
        prompts = {"nl": PROMPT_NL, "intent": PROMPT_INTENT}
        return input(prompts.get(mode, PROMPT_EXPR))

    def _process_line(self, line: str) -> None:
        if line in ("quit", "exit", "q"):
            self.state.continue_loop = False
            return
        if line in ("help", "h", "?"):
            self._print_help()
            return
        if line in ("clear", "cls"):
            os.system("cls" if os.name == "nt" else "clear")
            return
        if line == "history":
            self._print_history()
            return
        if line == "errors":
            self._print_errors()
            return
        if line == "recover":
            self._recover_last_error()
            return
        if line.startswith("mode "):
            self._set_mode(line[5:].strip())
            return
        if line.startswith("explain "):
            self._explain_intent(line[8:].strip())
            return
        if line.startswith("intent "):
            self._parse_intent(line[7:].strip())
            return
        if self.state.mode == "nl":
            self._process_natural_language(line)
            return
        if self.state.mode == "intent":
            self._parse_intent(line)
            return
        self._process_matha_expr(line)

    def _process_matha_expr(self, line: str) -> None:
        try:
            p = Parser(line)
            program = p.parse()
            outputs, trace = interpret(line)
            self.state.success_count += 1
            for i, out in enumerate(outputs):
                print(f"  = {out}")
            self._store_result(outputs)
        except MathaError as e:
            self._handle_matha_error(e, line)
        except Exception as e:
            self.state.error_count += 1
            print(f"  [ERROR] {type(e).__name__}: {e}")

    def _process_natural_language(self, line: str) -> None:
        parser = self.state.intent_parser
        if not parser:
            print("  [WARN] 意图解析器未初始化")
            return
        # 使用安全解析（返回 Result，不抛出）
        result = parser.parse(line)
        if result.is_ok():
            intent = result.unwrap()
            print()
            print("  " + "-" * 40)
            print("  " + parser.explain(intent))
            print("  " + "-" * 40)
            print()
            if intent.confidence > 0.5 and intent.suggested_code:
                print("  生成代码:")
                for code_line in intent.suggested_code.split("\n"):
                    print(f"    {code_line}")
                print()
                try:
                    outputs, trace = interpret(intent.suggested_code)
                    for out in outputs:
                        print(f"  → 结果: {out}")
                    self.state.success_count += 1
                except Exception as e:
                    self.state.error_count += 1
                    err = ExecError(f"执行失败: {e}", e)
                    self.state.append_error(err)
                    print(f"  [执行错误] {err.message}")
                    print(f"  {err.suggestions_text()}")
        else:
            error = result.err()
            self.state.error_count += 1
            self.state.error_log.append(error)
            print()
            print("  " + "=" * 40)
            print("  解析失败")
            print("  " + "=" * 40)
            print("  " + error.report())
            print()
            print("  " + error.suggestions_text())
            print("  " + "=" * 40)
            print()

    def _parse_intent(self, line: str) -> None:
        parser = self.state.intent_parser
        if not parser:
            return
        result = parser.parse(line)
        print()
        print("  " + "=" * 40)
        print("  意图分析结果")
        print("  " + "=" * 40)
        if result.is_ok():
            print("  " + parser.explain(result.unwrap()))
        else:
            error = result.err()
            print(f"  [ERROR] {error.message}")
            print(f"  阶段: {error.stage.name}")
            print(f"  严重度: {error.severity.name}")
            if error.suggestions:
                print(f"\n  建议:")
                for s in error.suggestions:
                    print(f"    • {s}")
            if error.cause:
                print(f"\n  原因:")
                print(f"    {error.cause.message}")
        print("  " + "=" * 40)
        print()

    def _explain_intent(self, line: str) -> None:
        report = explain_intent_safe(line)
        print("  " + report)

    def _recover_last_error(self) -> None:
        """尝试恢复最近一次错误。"""
        errors = self.state.get_error_log()
        if not errors:
            print("  [INFO] 没有可恢复的错误。")
            return
        last = errors[-1]
        print(f"  [RECOVER] 尝试恢复: {last.message}")
        recovered = RecoveryStrategy.try_recover(last)
        if recovered:
            print(f"  [OK] 恢复策略成功: {recovered.message}")
            print(f"  建议: {recovered.suggestions}")
        else:
            print("  [WARN] 无法自动恢复，请参考错误建议手动修正。")

    def _handle_matha_error(self, error: MathaError, source: str) -> None:
        """处理 MathaError，显示友好报告。"""
        self.state.error_count += 1
        self.state.append_error(error)
        print()
        print("  " + "=" * 40)
        print("  解析错误报告")
        print("  " + "=" * 40)
        print(f"  输入: {source!r}")
        print()
        print("  " + error.report())
        print()
        print("  " + error.suggestions_text())
        print("  " + "=" * 40)
        print()

    def _set_mode(self, mode: str) -> None:
        mode = mode.lower()
        if mode in self.MODES:
            self.state.mode = mode
            print(f"  [模式切换] {mode} — {self.MODES[mode][1]}")
        else:
            print(f"  [未知模式] {mode}，可用: {', '.join(self.MODES.keys())}")

    def _store_result(self, outputs: list) -> None:
        for i, out in enumerate(outputs):
            self.state.variables[f"_{i + 1}"] = out

    def _print_help(self) -> None:
        print()
        print("  可用命令:")
        print("    help          - 显示此帮助")
        print("    mode <m>      - 切换模式 (matha/nl/intent)")
        print("    history       - 显示输入历史")
        print("    errors        - 显示错误日志")
        print("    recover       - 尝试恢复最近错误")
        print("    clear         - 清屏")
        print("    explain <s>   - 解释自然语言")
        print("    intent <s>    - 深度意图分析")
        print("    quit/exit     - 退出")
        print()
        print("  示例:")
        print("    matha> x = 3.0 + 4.0")
        print("    nl> 计算 100 以内所有素数")
        print("    intent> 将字符串 'hello' 反转")
        print()

    def _print_history(self) -> None:
        print()
        print("  输入历史:")
        for i, line in enumerate(self.state.history[-20:], 1):
            print(f"    {i:3d}. {line}")
        print()

    def _print_errors(self) -> None:
        print()
        if not self.state.error_log:
            print("  暂无错误记录。")
            return
        print(f"  共 {len(self.state.error_log)} 条错误记录:")
        agg = ErrorAggregator()
        for e in self.state.error_log:
            agg.add(e)
        print("  " + agg.report())
        print()

    def _print_summary(self) -> None:
        total = self.state.success_count + self.state.error_count
        print()
        print("=" * 60)
        print(f"  会话结束 — 成功 {self.state.success_count}, "
              f"失败 {self.state.error_count}, 共 {total} 条")
        if errors := self.state.get_error_log():
            print(f"  错误日志: {len(errors)} 条")
        print(f"  当前模式: {self.state.mode}")
        print(f"  变量: {list(self.state.variables.keys())}")
        print("=" * 60)


def run_repl(debug: bool = False) -> None:
    repl = MathaREPL(debug=debug)
    repl.run()


if __name__ == "__main__":
    run_repl()
