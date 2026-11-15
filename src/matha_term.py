# -*- coding: utf-8 -*-
"""Matha 终端 —— 独立入口（阶段 12d）。

以 CMD 为模板的显示型终端。终端的全部命令逻辑（词法/句法/分发/执行/透传决策）
为纯 Matha 模块（matha/term_lexer / term_parser / term_engine），跑在 Matha 自身
解释器上；本文件是**薄壳**：只做行读取、行打印、进程退出码与批处理文件读取，
不含任何命令逻辑（诚实边界，见 docs/KNOWN_ISSUES.md 阶段 12a 条目）。

用法：
  python -m src.matha_term                 交互式 REPL（提示符 Matha>）
  python -m src.matha_term -c "回显 hi"    单命令执行后退出（退出码 0/1 如实）
  python -m src.matha_term script.msh      批处理：逐行执行 .msh 脚本
  matha 终端 [同上三种形态]                 经统一 CLI 子命令进入（别名 term）

行为口径：
  - REPL：空行跳过；错误如实打印「错误: ...」后继续会话（CMD 风格不退出）；
    退出 命令（经引擎结果帧的 退出 标志）或 Ctrl-Z/Ctrl-D（EOF）结束。
  - -c：执行结果帧的 输出 逐行打印；错误如实打印并以退出码 1 结束；退出 标志
    → 退出码 0。
  - .msh 批处理：逐行执行；`#` 开头为注释；空行跳过；错误如实打印并继续
    （CMD 批处理风格）；任一行出错则最终退出码 1，否则 0；退出 标志终止批处理。
  - 启动自动加载（阶段 12e，CMD AutoRun 同族）：仅 REPL 在横幅后自动执行当前
    目录 matha_term_extensions.msh（`#` 注释/空行跳过；行错误如实打印前缀
    「自启动(第 N 行)」后继续；其中的 退出 标志**不**结束会话）。-c 与批处理
    不触发。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 词法器为字符级扫描递归（matha/lexer.matha 扫描 同先例），随行长线性增长
sys.setrecursionlimit(max(30000, sys.getrecursionlimit()))

PROMPT = "Matha>"
BANNER = "Matha 终端（CMD 模板子集）— 输入 帮助 查看命令，退出 结束会话"
AUTORUN_FILE = "matha_term_extensions.msh"


def _make_runner():
    """构建引擎调用器：宿主解释器加载 终端执行器（调试Matha 可用）。"""
    from src.interp import Interpreter

    interp = Interpreter()
    if not interp.load_matha_module("终端执行器"):
        raise RuntimeError("终端引擎加载失败：未找到 matha/term_engine.matha")
    interp.outputs.clear()

    def run(line: str) -> dict:
        interp.outputs.clear()
        frame = interp._call_func_or_closure(interp.funcs["终端解析"], [line])
        result = interp._call_func_or_closure(interp.funcs["终端执行"], [frame, line])
        return result

    return run


def _emit(result: dict) -> bool:
    """打印结果帧的输出行；返回 退出 标志。"""
    for line in result.get("输出", []):
        print(line, flush=True)
    return bool(result.get("退出", False))


def _autorun(run) -> None:
    """REPL 启动自动加载：执行当前目录 matha_term_extensions.msh（12e）。

    错误如实打印并继续；退出 标志不结束会话（自启动用于注册命令等准备，
    不允许隐式杀掉用户会话）。无自启动文件时静默跳过。
    """
    p = Path.cwd() / AUTORUN_FILE
    if p.is_file():
        _run_msh_lines(run, p.read_text(encoding="utf-8").splitlines(),
                       prefix="自启动")
    _autorun_extensions(run)


def _autorun_extensions(run) -> None:
    """统一扩展面（23d）：执行 .matha/extensions.json 里启用的 terminal 条目。

    每个条目名 = 当前目录下相对路径（通常为 .msh 文件）；禁用条目跳过；
    文件缺失如实打印后继续。仅 REPL 触发（-c / 批处理不注入扩展）。
    """
    from src.extensions import load_state

    p = Path.cwd() / ".matha" / "extensions.json"
    if not p.exists():
        return
    try:
        state = load_state().get("state", {}).get("terminal", {})
    except (OSError, ValueError, RuntimeError) as e:
        print(f"自启动(扩展) 错误: {e}", flush=True)
        return
    for name, on in sorted(state.items()):
        if not on or name == AUTORUN_FILE:
            continue
        f = Path.cwd() / name
        if not f.is_file():
            print(f"自启动(扩展) 错误: 找不到终端扩展文件 {name}", flush=True)
            continue
        _run_msh_lines(run, f.read_text(encoding="utf-8").splitlines(),
                       prefix=f"自启动(扩展 {name})")


def _run_msh_lines(run, lines, *, prefix: str) -> None:
    """逐行执行 .msh 行（注释/空行跳过；错误如实打印后继续；退出标志忽略）。"""
    for lineno, raw in enumerate(lines, 1):
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            result = run(line)
        except RuntimeError as e:
            print(f"{prefix}(第 {lineno} 行) 错误: {e}", flush=True)
            continue
        except Exception as e:  # noqa: BLE001
            print(f"{prefix}(第 {lineno} 行) 错误: {type(e).__name__}: {e}", flush=True)
            continue
        _emit(result)


def repl() -> int:
    """交互式主循环。"""
    run = _make_runner()
    print(BANNER, flush=True)
    _autorun(run)
    while True:
        try:
            line = input(PROMPT + " ")
        except EOFError:
            print(flush=True)
            return 0
        except KeyboardInterrupt:
            print(flush=True)
            continue
        line = line.rstrip()
        if not line.strip():
            continue
        try:
            result = run(line)
        except RuntimeError as e:
            print(f"错误: {e}", flush=True)
            continue
        except Exception as e:  # noqa: BLE001 —— 薄壳如实显示，不让终端崩溃
            print(f"错误: {type(e).__name__}: {e}", flush=True)
            continue
        if _emit(result):
            return 0


def run_command(line: str) -> int:
    """单命令模式：执行一行，退出码 0/1 如实。"""
    run = _make_runner()
    try:
        result = run(line)
    except RuntimeError as e:
        print(f"错误: {e}", flush=True)
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"错误: {type(e).__name__}: {e}", flush=True)
        return 1
    _emit(result)
    return 0


def run_script(path: str) -> int:
    """批处理模式：.msh 脚本逐行执行，错误如实打印继续（CMD 风格）。"""
    run = _make_runner()
    p = Path(path)
    if not p.is_file():
        print(f"错误: 脚本不存在: {path}", flush=True)
        return 1
    had_error = False
    for lineno, raw in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            result = run(line)
        except RuntimeError as e:
            print(f"错误(第 {lineno} 行): {e}", flush=True)
            had_error = True
            continue
        except Exception as e:  # noqa: BLE001
            print(f"错误(第 {lineno} 行): {type(e).__name__}: {e}", flush=True)
            had_error = True
            continue
        if _emit(result):
            return 0
    return 1 if had_error else 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        return repl()
    if argv[0] == "-c":
        if len(argv) < 2:
            print("错误: -c 需要一条命令", flush=True)
            return 1
        return run_command(argv[1])
    if argv[0] in ("-h", "--help"):
        print(__doc__, flush=True)
        return 0
    return run_script(argv[0])


if __name__ == "__main__":
    sys.exit(main())
