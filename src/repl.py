# -*- coding: utf-8 -*-
"""Matha REPL — 交互式开发环境 — v2.2

支持：
  1. 表达式求值（Matha 源码）
  2. 自然语言意图解析
  3. 结果自然语言解释
  4. 历史记录与变量持久化
  5. 多语言输出切换
"""
from __future__ import annotations
import sys
import os
import logging
from typing import Any, Optional
from dataclasses import dataclass, field

# 确保 src 在路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.parser import Parser
from src import ast_nodes as ast
from src.interp import interpret
from src.intent_parser import IntentParser, explain_intent
from src.result import Ok, Err, MathaResultError
# KNP-PYTHON-NONDEFAULT: stdlib/core 改为按需懒加载，不默认激活
# from src.stdlib.core import register_core_builtins  ← 已移除，按需调用
from src.repl_completion import REPLCompleter, REPLHistoryManager


logger = logging.getLogger("matha.repl")

# REPL 提示符
PROMPT_EXPR = "matha> "
PROMPT_NL = "nl> "
PROMPT_INTENT = "intent> "
PROMPT_CONT = "... "  # 多行输入延续提示符


@dataclass
class REPLState:
    """REPL 运行时状态。"""
    variables: dict[str, Any] = field(default_factory=dict)
    history: list[str] = field(default_factory=list)
    intent_parser: Optional[IntentParser] = None
    mode: str = "matha"  # "matha" | "nl" | "intent"
    continue_loop: bool = True
    error_count: int = 0
    success_count: int = 0


class MathaREPL:
    """Matha 交互式 REPL。"""

    MODES = {
        "matha": ("matha>", "Matha 表达式模式"),
        "nl": ("nl> ", "自然语言模式"),
        "intent": ("intent> ", "意图分析模式"),
        "help": ("> ", "帮助模式"),
        "quit": (None, "退出"),
    }

    def __init__(self, debug: bool = False):
        self.state = REPLState(intent_parser=IntentParser())
        self.debug = debug
        # 初始化补全器和历史记录管理器
        self.completer = REPLCompleter(self.state)
        self.history_manager = REPLHistoryManager()
        # 初始化语法高亮器
        self.highlighter = SyntaxHighlighter(enabled=True)
        # 设置 readline 补全
        self._setup_readline()
        if debug:
            logging.basicConfig(level=logging.DEBUG,
                              format="%(name)s [%(levelname)s] %(message)s")
        else:
            logging.basicConfig(level=logging.WARNING)

    def _setup_readline(self) -> None:
        """设置 readline 自动补全"""
        try:
            import readline
            readline.set_completer(self.completer.complete)
            readline.parse_and_bind("tab: complete")
            readline.parse_and_bind("\"\\e[A\": history-search-backward")
            readline.parse_and_bind("\"\\e[B\": history-search-forward")
            logger.debug("REPL 自动补全已启用")
        except ImportError:
            logger.warning("readline 模块不可用，自动补全已禁用")

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
        """打印欢迎信息。"""
        print()
        print("=" * 60)
        print("  Matha 自成长引擎 REPL v2.2")
        print("  命令: help | mode <matha|nl|int> | quit | exit")
        print("  自然语言: '计算 3 加 5' | '找出 1 到 100 的素数'")
        print("=" * 60)
        print()

    def _read_input(self) -> str:
        """读取用户输入，支持多行输入。"""
        mode = self.state.mode
        if mode == "nl":
            prompt = PROMPT_NL
        elif mode == "intent":
            prompt = PROMPT_INTENT
        else:
            prompt = PROMPT_EXPR

        # 多行输入支持
        lines = []
        while True:
            try:
                line = input(prompt)
            except EOFError:
                if lines:
                    return '\n'.join(lines)
                raise
            except KeyboardInterrupt:
                print()
                return ""

            lines.append(line)

            # 检查是否需要继续多行输入
            if self._needs_continuation('\n'.join(lines)):
                prompt = PROMPT_CONT
                continue
            else:
                break

        return '\n'.join(lines)

    def _needs_continuation(self, text: str) -> bool:
        """
        检查输入是否需要继续多行

        规则：
        - 未闭合的括号/方括号/花括号
        - 未完成的冒号语句（def, if, for, while）
        - 连续的缩进行
        """
        # 移除注释行
        stripped_lines = [l.strip() for l in text.split('\n') if not l.strip().startswith('#')]
        full_text = '\n'.join(stripped_lines)

        # 统计括号
        paren_count = full_text.count('(') - full_text.count(')')
        bracket_count = full_text.count('[') - full_text.count(']')
        brace_count = full_text.count('{') - full_text.count('}')

        # 检查未闭合的括号
        if paren_count > 0 or bracket_count > 0 or brace_count > 0:
            return True

        # 检查未完成的语句
        last_line = stripped_lines[-1] if stripped_lines else ''
        if last_line.endswith(':') or last_line.endswith(',') or last_line.endswith('(') or last_line.endswith('['):
            return True

        # 检查是否是控制流语句的开始
        if any(last_line.startswith(kw + ' ') for kw in ['if', 'elif', 'else', 'for', 'while', 'def', 'class', 'try', 'except', 'finally']):
            return True

        return False

    def _process_line(self, line: str) -> None:
        """处理输入行（支持多行）。"""
        # 多行处理：将多行代码分割并处理
        lines = line.strip().split('\n')

        # 命令（单行）
        single_line = lines[0].strip()
        if single_line in ("quit", "exit", "q"):
            self.state.continue_loop = False
            return

        if single_line in ("help", "h", "?"):
            self._print_help()
            return

        if single_line in ("clear", "cls"):
            os.system("cls" if os.name == "nt" else "clear")
            return

        if single_line == "history":
            self._print_history()
            return

        if single_line.startswith("mode "):
            self._set_mode(single_line[5:].strip())
            return

        if single_line.startswith("explain "):
            self._explain_intent(single_line[8:].strip())
            return

        if single_line.startswith("intent "):
            self._parse_intent(single_line[7:].strip())
            return

        # 自然语言模式
        if self.state.mode == "nl":
            self._process_natural_language(line)
            return

        # 意图模式
        if self.state.mode == "intent":
            self._parse_intent(line)
            return

        # 默认：Matha 表达式
        self._process_matha_expr(line)

    def _process_matha_expr(self, line: str) -> None:
        """处理 Matha 表达式。"""
        try:
            # 尝试解析
            p = Parser(line)
            program = p.parse()
            # 尝试执行
            outputs, trace = interpret(line)
            self.state.success_count += 1
            for i, out in enumerate(outputs):
                print(f"  = {out}")
            # 存储到变量
            self._store_result(outputs)
        except Exception as e:
            self.state.error_count += 1
            if self.debug:
                print(f"  [ERROR] {e}")
                import traceback
                traceback.print_exc()
            else:
                print(f"  [ERROR] {e}")

    def _process_natural_language(self, line: str) -> None:
        """处理自然语言输入。"""
        if not self.state.intent_parser:
            print("  [WARN] 意图解析器未初始化")
            return
        intent = self.state.intent_parser.parse(line)
        print()
        print("  " + "-" * 40)
        print("  " + self.state.intent_parser.explain(intent))
        print("  " + "-" * 40)
        print()
        # 尝试生成并执行代码
        if intent.confidence > 0.5 and intent.suggested_code:
            print(f"  {self.highlighter.CYAN}生成代码:{self.highlighter.RESET}")
            for code_line in intent.suggested_code.split("\n"):
                highlighted = self.highlighter.highlight(code_line)
                print(f"    {highlighted}")
            print()
            # 执行生成的代码
            try:
                outputs, trace = interpret(intent.suggested_code)
                for out in outputs:
                    print(f"  {self.highlighter.GREEN}→ 结果:{self.highlighter.RESET} {out}")
                self.state.success_count += 1
            except Exception as e:
                print(f"  {self.highlighter.RED}[执行失败]{self.highlighter.RESET} {e}")
                self.state.error_count += 1

    def _parse_intent(self, line: str) -> None:
        """解析意图并显示详细信息。"""
        if not self.state.intent_parser:
            return
        intent = self.state.intent_parser.parse(line)
        print()
        print("  " + "=" * 40)
        print("  意图分析结果")
        print("  " + "=" * 40)
        print("  " + self.state.intent_parser.explain(intent))
        print("  " + "=" * 40)
        print()

    def _explain_intent(self, line: str) -> None:
        """解释意图（简版）。"""
        if not self.state.intent_parser:
            return
        intent = self.state.intent_parser.parse(line)
        print("  " + self.state.intent_parser.explain(intent))

    def _set_mode(self, mode: str) -> None:
        """切换模式。"""
        mode = mode.lower()
        if mode in self.MODES:
            self.state.mode = mode
            label = self.MODES[mode][1]
            print(f"  [模式切换] {mode} — {label}")
        else:
            print(f"  [未知模式] {mode}，可用: {', '.join(self.MODES.keys())}")

    def _store_result(self, outputs: list) -> None:
        """将输出存储到变量 _1, _2, ..."""
        for i, out in enumerate(outputs):
            var_name = f"_{i + 1}"
            self.state.variables[var_name] = out

    def _print_help(self) -> None:
        """打印帮助信息。"""
        print()
        print("  可用命令:")
        print("    help          - 显示此帮助")
        print("    mode <m>      - 切换模式 (matha/nl/intent)")
        print("    history       - 显示输入历史")
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
        """打印历史输入。"""
        print()
        print("  输入历史:")
        for i, line in enumerate(self.state.history[-20:], 1):
            highlighted = self.highlighter.highlight(line)
            print(f"    {i:3d}. {highlighted}")
        print()

    def _print_summary(self) -> None:
        """打印会话摘要。"""
        total = self.state.success_count + self.state.error_count
        print()
        print("=" * 60)
        print(f"  会话结束 — 成功 {self.state.success_count}, 失败 {self.state.error_count}, 共 {total} 条")
        print(f"  当前模式: {self.state.mode}")
        print(f"  变量: {list(self.state.variables.keys())}")
        print("=" * 60)


# ============================================================
# 便捷入口
# ============================================================

def run_repl(debug: bool = False) -> None:
    """启动 REPL。"""
    repl = MathaREPL(debug=debug)
    repl.run()


def main(argv=None) -> int:
    """CLI 入口。支持：matha（REPL）、matha eval <expr>、matha run <file>。"""
    import argparse

    parser = argparse.ArgumentParser(
        prog="matha",
        description="Matha 数学编程语言 — 自然语言 → 数学核心 → 可读输出",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  matha                    # 启动交互式 REPL
  matha eval "sin(pi)"     # 计算表达式
  matha run demo.matha     # 运行 Matha 文件
  matha-cc compile demo.matha -o c   # 编译到 C
        """,
    )
    parser.add_argument("--debug", action="store_true", help="启用调试模式")
    parser.add_argument("--version", action="version", version="Matha v4.4")

    sub = parser.add_subparsers(dest="command", help="子命令")

    # eval: 单行表达式计算
    p_eval = sub.add_parser("eval", help="计算单行表达式")
    p_eval.add_argument("expr", help="Matha 表达式")
    p_eval.set_defaults(func=lambda args: _cmd_eval(args))

    # run: 运行 .matha 文件
    p_run = sub.add_parser("run", help="运行 Matha 源文件")
    p_run.add_argument("file", help=".matha 源文件路径")
    p_run.set_defaults(func=lambda args: _cmd_run(args))

    # help
    p_help = sub.add_parser("help", help="显示帮助")
    p_help.set_defaults(func=lambda args: parser.print_help())

    args = parser.parse_args(argv)
    if hasattr(args, "func"):
        return args.func(args)
    else:
        # 无子命令 → 启动 REPL
        run_repl(debug=args.debug)
        return 0


def _cmd_eval(args) -> int:
    """计算单行表达式。"""
    from src.mir_converter import convert
    c_code = convert(args.expr, "matha", "python")
    print(c_code)
    return 0


def _cmd_run(args) -> int:
    """运行 .matha 文件。"""
    import sys
    try:
        with open(args.file, "r", encoding="utf-8") as f:
            source = f.read()
        from src.mir_converter import convert
        py_code = convert(source, "matha", "python")
        exec(py_code, {"__name__": "__main__"})
        return 0
    except FileNotFoundError:
        print(f"错误: 文件不存在: {args.file}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
