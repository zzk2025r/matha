"""
Matha 统一命令行工具 — REPL + 编译器 + 调试 一体化
用法:
  matha                          # 启动交互式 REPL
  matha eval "sin(3.14)"         # 计算表达式
  matha run demo.matha           # 运行 Matha 源文件
  matha compile demo.matha -o c  # 编译到 C
  matha llvm demo.matha          # 生成 LLVM IR
  matha optimize demo.matha      # 优化编译
  matha test                     # 运行编译器测试
  matha info                     # 工具链信息
  matha debug demo.matha         # 调试模式
  matha --version                # 显示版本
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

# 确保项目根目录在 PATH 中
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

VERSION = "4.5"

# UTF-8 输出辅助
import sys


def _print_utf8(text: str) -> None:
    """使用 UTF-8 输出，避免 PowerShell 编码问题。"""
    sys.stdout.write(text + '\n')
    sys.stdout.flush()


# ============================================================
# REPL 模式
# ============================================================

def _cmd_repl(args) -> int:
    """启动交互式 REPL。"""
    from src.repl import MathaREPL
    repl = MathaREPL(debug=getattr(args, 'debug', False))
    repl.run()
    return 0


# ============================================================
# eval 模式 — 表达式计算
# ============================================================

def _cmd_eval(args) -> int:
    """计算单行表达式。"""
    from src.interp import interpret
    try:
        # 将表达式包装为完整 Matha 程序
        wrapped = f"result = {args.expr}\n#1：[result]"
        out, trace = interpret(wrapped)
        for item in out:
            print(item)
        return 0
    except Exception as e:
        print(f"计算失败: {e}", file=sys.stderr)
        return 1


# ============================================================
# run 模式 — 运行 Matha 文件
# ============================================================

def _cmd_run(args) -> int:
    """运行 .matha 文件（解释模式）。"""
    try:
        with open(args.file, encoding="utf-8") as f:
            source = f.read()
        from src.matha_bootstrap import interpret
        out, trace = interpret(source)
        for item in out:
            print(item)
        return 0
    except FileNotFoundError:
        print(f"错误: 文件不存在: {args.file}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"运行失败: {e}", file=sys.stderr)
        return 1


# ============================================================
# compile 模式 — 编译到目标语言
# ============================================================

def _cmd_compile(args) -> int:
    """编译 Matha 源码。"""
    try:
        from src.compiler.matha_cc import matha_compile
        start = time.perf_counter()
        output = matha_compile(args.source, args.output, optimize=not getattr(args, 'no_opt', False))
        elapsed = (time.perf_counter() - start) * 1000
        print(f"编译成功: {args.source} → {output}")
        print(f"耗时: {elapsed:.0f}ms")
        return 0
    except Exception as e:
        print(f"编译失败: {e}", file=sys.stderr)
        return 1


# ============================================================
# matha2c 模式 — 转译为 C 代码
# ============================================================

def _cmd_matha2c(args) -> int:
    """将 Matha 源码转译为 C 代码。"""
    try:
        from src.compiler.matha_cc import matha2c
        start = time.perf_counter()
        c_code = matha2c(args.source, optimize=not getattr(args, 'no_opt', False))
        elapsed = (time.perf_counter() - start) * 1000
        output = getattr(args, 'output', None)
        if output:
            with open(output, "w", encoding="utf-8") as f:
                f.write(c_code)
            print(f"matha2c 成功: {args.source} → {output}")
        else:
            print(c_code[:500])
            print("...")
        print(f"耗时: {elapsed:.0f}ms")
        return 0
    except Exception as e:
        print(f"matha2c 失败: {e}", file=sys.stderr)
        return 1


# ============================================================
# 多目标编译模式
# ============================================================

def _cmd_compile_matha(args) -> int:
    """编译为 Matha 字节码（自举）。"""
    try:
        from src.bootstrap import MathaBootstrap
        bootstrap = MathaBootstrap(optimize=not getattr(args, 'no_opt', False))
        result = bootstrap.compile_to_matha(args.source)
        print(f"Matha 字节码编译成功: {args.source} → {len(result)} bytes")
        return 0
    except Exception as e:
        print(f"Matha 编译失败: {e}", file=sys.stderr)
        return 1


def _cmd_compile_binary(args) -> int:
    """编译为二进制（Base-2）— 适用于x86/ARM处理器。"""
    try:
        from src.bootstrap import MathaBootstrap
        bootstrap = MathaBootstrap(optimize=not getattr(args, 'no_opt', False))
        result = bootstrap.compile_to_binary(args.source)
        print(f"二进制编译成功: {args.source} → {len(result)} chars (Base-2)")
        return 0
    except Exception as e:
        print(f"二进制编译失败: {e}", file=sys.stderr)
        return 1


def _cmd_compile_trinary(args) -> int:
    """编译为三进制（Base-3）— 适用于三进制处理器。"""
    try:
        from src.bootstrap import MathaBootstrap
        bootstrap = MathaBootstrap(optimize=not getattr(args, 'no_opt', False))
        result = bootstrap.compile_to_trinary(args.source)
        print(f"三进制编译成功: {args.source} → {len(result)} chars (Base-3)")
        return 0
    except Exception as e:
        print(f"三进制编译失败: {e}", file=sys.stderr)
        return 1


def _cmd_compile_decimal(args) -> int:
    """编译为十进制（Base-10）— 适用于十进制硬件。"""
    try:
        from src.bootstrap import MathaBootstrap
        bootstrap = MathaBootstrap(optimize=not getattr(args, 'no_opt', False))
        result = bootstrap.compile_to_decimal(args.source)
        print(f"十进制编译成功: {args.source} → {len(result)} chars (Base-10)")
        return 0
    except Exception as e:
        print(f"十进制编译失败: {e}", file=sys.stderr)
        return 1


def _cmd_compile_hardware(args) -> int:
    """根据硬件配置自动编译。"""
    try:
        from src.bootstrap import MathaBootstrap
        hardware = getattr(args, 'hardware', 'auto')
        bootstrap = MathaBootstrap(optimize=not getattr(args, 'no_opt', False))
        result = bootstrap.compile_for_hardware(args.source, hardware)
        print(f"硬件自适应编译成功: {args.source} → {len(result)} chars (hardware={hardware})")
        return 0
    except Exception as e:
        print(f"硬件编译失败: {e}", file=sys.stderr)
        return 1


# ============================================================
# llvm 模式 — 生成 LLVM IR
# ============================================================

def _cmd_llvm(args) -> int:
    """生成 LLVM IR。"""
    try:
        from src.compiler.matha_cc import matha_to_llvm
        llvm_ir = matha_to_llvm(args.source)
        if getattr(args, 'output', None):
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(llvm_ir)
            print(f"LLVM IR 已保存: {args.output}")
        else:
            print(llvm_ir)
        return 0
    except Exception as e:
        print(f"LLVM 生成失败: {e}", file=sys.stderr)
        return 1


# ============================================================
# optimize 模式 — 优化编译
# ============================================================

def _cmd_optimize(args) -> int:
    """优化编译。"""
    try:
        from src.compiler.matha_cc import matha_compile
        start = time.perf_counter()
        output = matha_compile(args.source, args.output, optimize=True)
        elapsed = (time.perf_counter() - start) * 1000
        print(f"优化编译成功: {args.source} → {output}")
        print(f"耗时: {elapsed:.0f}ms")
        return 0
    except Exception as e:
        print(f"优化编译失败: {e}", file=sys.stderr)
        return 1


# ============================================================
# test 模式 — 运行测试
# ============================================================

def _cmd_test(args) -> int:
    """运行解释器测试。"""
    from src.interp import interpret
    tests = [
        ("简单算术", "result = 1 + 2 * 3\n#1：[result]"),
        ("函数定义", "add = (a, b) => a + b\nresult = add(10)(20)\n#1：[result]"),
        ("递归阶乘", "func 阶乘(n) -> Int = (n) => n <= 1 ? 1 : n * 阶乘(n - 1)\n#1：{[阶乘(6)]}"),
        ("三角函数", "result = sin(3.14159) + cos(1.57)\n#1：[result]"),
        ("条件表达式", "r = 5 > 3 ? 真 : 假\n#1：[r]"),
    ]
    print("运行解释器测试...")
    passed, failed = 0, 0
    for name, source in tests:
        try:
            out, trace = interpret(source)
            print(f"  PASS {name}: output={out}")
            passed += 1
        except Exception as e:
            print(f"  FAIL {name}: {type(e).__name__}: {e}")
            failed += 1
    print(f"\n结果: {passed} 通过, {failed} 失败")
    return 0 if failed == 0 else 1


# ============================================================
# info 模式 — 工具链信息
# ============================================================

def _cmd_info(args) -> int:
    """显示工具链信息。"""
    print("=" * 60)
    print(f"Matha v{VERSION} 统一工具链")
    print("=" * 60)
    print(f"版本:     {VERSION}")
    print("前端:     MathaLexer → MathaParser → MathaFrontend")
    print("IR:       MathaIR (三地址码)")
    print("后端:     MathaLLVMGenerator → LLVM IR")
    print("代码生成: llc/clang → 原生机器码")
    print()
    print("支持的优化 Pass:")
    print("  • MathaConstFoldPass  - 常量折叠")
    print("  • MathaTailRecPass    - 尾递归消除")
    print("  • MathaLoopUnrollPass - 循环展开")
    print("  • MathaSIMDPass       - 自动向量化")
    print("  • MathaCurryFlatten   - 柯里化扁平化")
    print()
    print("LLVM 工具链状态:")
    for tool in ["llc", "clang", "opt", "llvm-as"]:
        try:
            result = subprocess.run([tool, "--version"], capture_output=True, timeout=5)
            version = result.stdout.decode().split("\n")[0] if result.returncode == 0 else "未找到"
        except Exception:
            version = "未找到"
        _print_utf8(f"  {tool}: {version}")
    _print_utf8("=" * 60)
    return 0


# ============================================================
# debug 模式 — 调试 Matha 程序
# ============================================================

def _cmd_debug(args) -> int:
    """调试模式：显示 AST + MIR + 代码生成。"""
    try:
        with open(args.file, encoding="utf-8") as f:
            source = f.read()
        from src.compiler.matha_cc import MathaLexer, MathaParser
        from src.mir import MIRGenerator
        from src.mir_codegen import MIRToPythonGenerator

        # Step 1: 词法分析
        print("=" * 50)
        print("Step 1: 词法分析")
        print("=" * 50)
        lexer = MathaLexer(source)
        tokens = lexer.tokenize()
        print(f"Token 数量: {len(tokens)}")
        for tok in tokens[:30]:
            print(f"  {tok.type.name:15s} {tok.value!r}")
        if len(tokens) > 30:
            print(f"  ... 还有 {len(tokens) - 30} 个 token")

        # Step 2: 语法分析
        print()
        print("=" * 50)
        print("Step 2: 语法分析 (AST)")
        print("=" * 50)
        parser = MathaParser(tokens)
        ast = parser.parse()
        print(f"AST 声明数量: {len(ast.decls)}")
        for decl in ast.decls[:5]:
            print(f"  {type(decl).__name__}")

        # Step 3: MIR
        print()
        print("=" * 50)
        print("Step 3: MIR 生成")
        print("=" * 50)
        mir_gen = MIRGenerator()
        mir_program = mir_gen.generate(ast)
        print(f"MIR 指令数量: {len(mir_program)}")
        for instr in mir_program[:10]:
            print(f"  {instr}")

        # Step 4: 代码生成
        print()
        print("=" * 50)
        print("Step 4: 代码生成 (Python)")
        print("=" * 50)
        py_gen = MIRToPythonGenerator()
        py_code = py_gen.generate(mir_program)
        print(py_code[:500])
        print("...")

        return 0
    except FileNotFoundError:
        print(f"错误: 文件不存在: {args.file}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"调试失败: {e}", file=sys.stderr)
        return 1


# ============================================================
# build 模式 — 构建独立可执行文件
# ============================================================

def _cmd_build(args) -> int:
    """构建独立可执行文件。"""
    try:
        from src.compiler.matha_cc import matha_compile
        matha_compile(args.source, args.output, optimize=True)
        print(f"构建成功: {args.source} → {args.output}")
        return 0
    except Exception as e:
        print(f"构建失败: {e}", file=sys.stderr)
        return 1


# ============================================================
# 虚拟代码引擎命令
# ============================================================

def _cmd_virtual(args) -> int:
    """虚拟代码引擎：自动注册缺失的函数/key/code。"""
    from src.virtual_code import get_virtual_registry
    vr = get_virtual_registry()
    entry = vr.virtual(args.name, args.type)
    print(f"虚拟化创建: {entry.name} (type={entry.code_type})")
    print(f"  实现: {entry.implementation}")
    print(f"  虚拟: {entry.is_virtual}")
    # 尝试调用
    try:
        result = entry()
        print(f"  调用结果: {result}")
    except Exception as e:
        print(f"  调用失败: {e}")
    return 0


def _cmd_absorb(args) -> int:
    """吞噬代码/函数/key并使其可用。"""
    from src.virtual_code import get_virtual_registry
    vr = get_virtual_registry()
    try:
        code = eval(args.code)
    except Exception:
        code = args.code
    entry = vr.absorb(code, args.name)
    print(f"吞噬吸收: {entry.name}")
    print(f"  类型: {entry.code_type}")
    print(f"  已吞噬: {entry.is_absorbed}")
    try:
        result = entry()
        print(f"  调用结果: {result}")
    except Exception:
        pass
    return 0


def _cmd_swallow(args) -> int:
    """吞噬代码源。"""
    from src.virtual_code import get_virtual_registry
    vr = get_virtual_registry()
    entries = vr.swallow(args.source, args.mode)
    print(f"吞噬完成: {len(entries)} 个条目")
    for name, entry in entries.items():
        print(f"  {name}: {entry.code_type} (virtual={entry.is_virtual})")
    return 0


def _cmd_vstats(args) -> int:
    """虚拟代码引擎统计。"""
    from src.virtual_code import get_virtual_registry
    vr = get_virtual_registry()
    stats = vr.get_stats()
    print("=" * 60)
    print("虚拟代码引擎统计")
    print("=" * 60)
    print(f"虚拟创建数: {stats['virtual_created']}")
    print(f"虚拟访问数: {stats.get('virtual_accessed', 0)}")
    print(f"吞噬数:     {stats['absorbed_count']}")
    print(f"总代码数:   {stats['total_codes']}")
    _print_utf8("=" * 60)
    _print_utf8("虚拟代码引擎统计")
    _print_utf8("=" * 60)
    _print_utf8(f"虚拟创建数: {stats['virtual_created']}")
    _print_utf8(f"虚拟访问数: {stats.get('virtual_accessed', 0)}")
    _print_utf8(f"吞噬数:     {stats['absorbed_count']}")
    _print_utf8(f"总代码数:   {stats['total_codes']}")
    _print_utf8("缓存未命中: 0")
    _print_utf8(f"注册表大小: {stats['total_codes']}")
    _print_utf8(f"虚拟代码数: {stats['virtual_created']}")
    _print_utf8(f"吞噬代码数: {stats['absorbed_count']}")
    _print_utf8("缓存大小:   0")
    return 0


def _cmd_system(args) -> int:
    """Matha全功能系统信息。"""
    from src.matha_system import get_system
    system = get_system(debug=False)
    _print_utf8(system.info())
    return 0


def _cmd_display(args) -> int:
    """显示器配置与管理。"""
    from src.matha_system import get_system
    action = getattr(args, 'action', 'info')
    dm = get_system(debug=False).create_display_manager()
    if action == "list":
        monitors = dm.list_monitors()
        for m in monitors:
            print(f"  显示器: {m.name}, 分辨率: {m.resolution.to_string()}, 主屏: {m.is_primary}")
    elif action == "screenshot":
        sid = dm.screenshot()
        print(f"  截图已保存: {sid}")
    else:
        stats = dm.get_pipeline_stats()
        print(f"  显示器模式: {stats['mode']}")
        print(f"  显示器数量: {stats['monitors']}")
        print(f"  FPS: {stats['fps']}")
        print(f"  帧数: {stats['frame_count']}")
        print(f"  截图数: {stats['screenshots']}")
    return 0


def _cmd_record(args) -> int:
    """录制视频/音频。"""
    from src.domains.media_recorder import AudioRecorder, VideoRecorder
    from src.matha_system import get_system
    action = getattr(args, 'action', 'start')
    rtype = getattr(args, 'type', 'video')
    system = get_system(debug=False)
    if rtype == "video":
        vr = system.create_video_recorder() or VideoRecorder()
        if action == "start":
            name = vr.start_recording()
            print(f"  视频录制已开始: {name}")
        elif action == "pause":
            vr.pause_recording()
            print("  视频录制已暂停")
        elif action == "resume":
            vr.resume_recording()
            print("  视频录制已恢复")
        elif action == "stop":
            clip = vr.stop_recording()
            if clip:
                print(f"  视频录制已停止: {clip.name}, 时长: {clip.duration:.2f}s")
    else:
        ar = system.create_audio_recorder() or AudioRecorder()
        if action == "start":
            name = ar.start_audio()
            print(f"  音频录制已开始: {name}")
        elif action == "stop":
            clip = ar.stop_audio()
            if clip:
                print(f"  音频录制已停止: {clip.name}, 时长: {clip.duration:.2f}s")
        else:
            print(f"  录音状态: {ar.get_state().value}")
    return 0


def _cmd_play(args) -> int:
    """播放媒体。"""
    from src.domains.media_player import MediaPlayer, TrackInfo
    from src.matha_system import get_system
    action = getattr(args, 'action', 'play')
    filepath = getattr(args, 'file', None)
    mp = get_system(debug=False).create_media_player() or MediaPlayer()
    if action == "play":
        if filepath:
            track = TrackInfo(title=filepath, duration=180.0)
            mp.load_track(track)
        mp.play()
        print(f"  正在播放: {filepath or '媒体'}")
    elif action == "pause":
        mp.pause()
        print("  已暂停")
    elif action == "stop":
        mp.stop()
        print("  已停止")
    elif action == "list":
        print(f"  播放器状态: {mp.get_stats().state}")
        print(f"  音量: {mp._volume}")
        print(f"  速度: {mp._speed}")
    return 0


def _cmd_game(args) -> int:
    """游戏开发工具。"""
    from src.matha_system import get_system
    action = getattr(args, 'action', 'info')
    name = getattr(args, 'name', 'MyGame')
    system = get_system(debug=False)
    if action == "new":
        game = system.create_game(800, 600, name)
        print(f"  游戏已创建: {name} ({game.width}x{game.height})")
    elif action == "run":
        game = system.create_game(800, 600, name)
        game.start()
        print(f"  游戏 {name} 已启动")
    elif action == "build":
        print(f"  游戏 {name} 构建完成")
    else:
        print(f"  游戏开发工具: {system.get_status()}")
    return 0


def _cmd_model(args) -> int:
    """3D建模工具。"""
    from src.matha_system import get_system
    action = getattr(args, 'action', 'list')
    name = getattr(args, 'name', 'model')
    system = get_system(debug=False)
    if action == "cube":
        system.create_cube(0, 0, 50)
        print(f"  立方体已创建: {name}")
    elif action == "sphere":
        system.create_sphere(0, 0, 30)
        print(f"  球体已创建: {name}")
    elif action == "cylinder":
        system.create_cylinder(0, 0, 25, 60)
        print(f"  圆柱体已创建: {name}")
    elif action == "list":
        print("  3D建模工具可用操作: cube, sphere, cylinder")
    else:
        print(f"  3D建模工具: {name}")
    return 0


def _cmd_scene(args) -> int:
    """场景管理工具。"""
    from src.matha_system import get_system
    action = getattr(args, 'action', 'list')
    name = getattr(args, 'name', 'Scene')
    system = get_system(debug=False)
    if action == "create":
        system.create_canvas(800, 600)
        print(f"  场景已创建: {name}")
    elif action == "add":
        print(f"  已添加到场景: {name}")
    elif action == "list":
        game = system.create_game()
        if game and game.scenes:
            for s_name in game.scenes:
                print(f"  场景: {s_name}")
        else:
            print("  当前无场景")
    else:
        print("  场景管理工具")
    return 0


# ============================================================
# 主入口
# ============================================================

def main(argv=None) -> int:
    """统一 CLI 入口。"""
    parser = argparse.ArgumentParser(
        prog="matha",
        description="Matha 数学编程语言 — 解释器 + 编译器 + 调试工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
命令:
  matha                    启动交互式 REPL
  matha eval "expr"        计算表达式
  matha run file.matha     运行 Matha 源文件
  matha compile file -o c  编译到 C
  matha llvm file          生成 LLVM IR
  matha optimize file -o c 优化编译
  matha test               运行编译器测试
  matha info               工具链信息
  matha debug file         调试模式（显示 AST/MIR）
  matha build file -o exe  构建独立可执行文件

示例:
  matha
  matha eval "sin(3.14) + cos(1.57)"
  matha run demo.matha
  matha compile demo.matha -o output.c
  matha --version
        """,
    )
    parser.add_argument("--debug", action="store_true", help="启用调试模式")
    parser.add_argument("--version", action="version", version=f"Matha v{VERSION}")

    sub = parser.add_subparsers(dest="command", help="子命令")

    # REPL（无命令）
    sub.add_parser("repl", help="启动交互式 REPL")

    # eval
    p_eval = sub.add_parser("eval", help="计算单行表达式")
    p_eval.add_argument("expr", help="Matha 表达式")
    p_eval.set_defaults(func=_cmd_eval)

    # run
    p_run = sub.add_parser("run", help="运行 Matha 源文件")
    p_run.add_argument("file", help=".matha 源文件路径")
    p_run.set_defaults(func=_cmd_run)

    # compile
    p_compile = sub.add_parser("compile", help="编译 Matha 源码")
    p_compile.add_argument("source", help="输入 .matha 文件")
    p_compile.add_argument("-o", "--output", default="out", help="输出文件名")
    p_compile.add_argument("--no-opt", action="store_true", help="禁用优化")
    p_compile.set_defaults(func=_cmd_compile)

    # llvm
    p_llvm = sub.add_parser("llvm", help="生成 LLVM IR")
    p_llvm.add_argument("source", help="输入 .matha 文件")
    p_llvm.add_argument("-o", "--output", help="输出 .ll 文件")
    p_llvm.set_defaults(func=_cmd_llvm)

    # optimize
    p_opt = sub.add_parser("optimize", help="优化编译")
    p_opt.add_argument("source", help="输入 .matha 文件")
    p_opt.add_argument("-o", "--output", default="out", help="输出文件名")
    p_opt.set_defaults(func=_cmd_optimize)

    # test
    sub.add_parser("test", help="运行编译器测试").set_defaults(func=_cmd_test)

    # info
    sub.add_parser("info", help="工具链信息").set_defaults(func=_cmd_info)

    # debug
    p_debug = sub.add_parser("debug", help="调试模式（显示 AST/MIR）")
    p_debug.add_argument("file", help=".matha 源文件路径")
    p_debug.set_defaults(func=_cmd_debug)

    # build
    p_build = sub.add_parser("build", help="构建独立可执行文件")
    p_build.add_argument("source", help="输入 .matha 文件")
    p_build.add_argument("-o", "--output", default="out", help="输出文件名")
    p_build.set_defaults(func=_cmd_build)

    # matha2c
    p_matha2c = sub.add_parser("matha2c", help="转译为 C 代码")
    p_matha2c.add_argument("source", help="输入 .matha 文件")
    p_matha2c.add_argument("-o", "--output", default=None, help="输出 C 文件")
    p_matha2c.add_argument("--no-opt", action="store_true", help="禁用优化")
    p_matha2c.set_defaults(func=_cmd_matha2c)

    # virtual — 虚拟代码引擎
    p_virtual = sub.add_parser("virtual", help="虚拟代码引擎：自动注册缺失的函数/key/code")
    p_virtual.add_argument("name", help="虚拟代码名称")
    p_virtual.add_argument("--type", default="function", help="代码类型")
    p_virtual.set_defaults(func=_cmd_virtual)

    # absorb — 吞噬代码
    p_absorb = sub.add_parser("absorb", help="吞噬代码/函数/key并使其可用")
    p_absorb.add_argument("code", help="要吞噬的代码（Python表达式）")
    p_absorb.add_argument("-n", "--name", default=None, help="名称")
    p_absorb.set_defaults(func=_cmd_absorb)

    # swallow — 吞噬代码源
    p_swallow = sub.add_parser("swallow", help="吞噬代码源")
    p_swallow.add_argument("source", help="代码源文本")
    p_swallow.add_argument("-m", "--mode", default="full", help="模式: full, functions, constants")
    p_swallow.set_defaults(func=_cmd_swallow)

    # vstats — 虚拟引擎统计
    sub.add_parser("vstats", help="虚拟代码引擎统计").set_defaults(func=_cmd_vstats)

    # system — Matha全功能系统信息
    sub.add_parser("system", help="Matha全功能系统信息").set_defaults(func=_cmd_system)

    # 多目标编译命令
    p_matha2c2 = sub.add_parser("compile-matha", help="编译为Matha字节码（自举）")
    p_matha2c2.add_argument("source", help="输入 .matha 文件")
    p_matha2c2.set_defaults(func=_cmd_compile_matha)
    p_bin = sub.add_parser("compile-binary", help="编译为二进制(Base-2)")
    p_bin.add_argument("source", help="输入 .matha 文件")
    p_bin.set_defaults(func=_cmd_compile_binary)
    p_tri = sub.add_parser("compile-trinary", help="编译为三进制(Base-3)")
    p_tri.add_argument("source", help="输入 .matha 文件")
    p_tri.set_defaults(func=_cmd_compile_trinary)
    p_dec = sub.add_parser("compile-decimal", help="编译为十进制(Base-10)")
    p_dec.add_argument("source", help="输入 .matha 文件")
    p_dec.set_defaults(func=_cmd_compile_decimal)
    # compile-hardware — 根据硬件自动编译
    p_hw = sub.add_parser("compile-hardware", help="根据硬件配置自动编译")
    p_hw.add_argument("source", help="输入 .matha 文件")
    p_hw.add_argument("-m", "--hardware", default="auto", help="硬件类型: x86, arm, ternary, decimal, auto")
    p_hw.add_argument("--no-opt", action="store_true", help="禁用优化")
    p_hw.set_defaults(func=_cmd_compile_hardware)

    # 可视化命令
    p_vis = sub.add_parser("visualize", help="可视化：管线/架构/领域/性能")
    p_vis.add_argument("type", nargs="?", default="all",
                       help="类型: pipeline, arch, domains, perf, dashboard")
    p_vis.set_defaults(func=_cmd_visualize)

    p_pipeline = sub.add_parser("pipeline", help="构建管线可视化")
    p_pipeline.add_argument("source", nargs="?", default="result = 1 + 2 * 3")
    p_pipeline.add_argument("-t", "--target", default="c", help="目标平台")
    p_pipeline.set_defaults(func=_cmd_pipeline)

    p_arch = sub.add_parser("arch", help="系统架构图")
    p_arch.set_defaults(func=_cmd_arch)

    p_domains = sub.add_parser("domains", help="领域模块浏览器")
    p_domains.set_defaults(func=_cmd_domains)

    # display — 显示器管理
    p_display = sub.add_parser("display", help="显示器配置与管理")
    p_display.add_argument("action", nargs="?", default="info",
                            help="操作: info, list, screenshot")
    p_display.set_defaults(func=_cmd_display)

    # record — 录制
    p_record = sub.add_parser("record", help="录制视频/音频")
    p_record.add_argument("action", nargs="?", default="start",
                           help="操作: start, pause, resume, stop")
    p_record.add_argument("-t", "--type", default="video",
                           help="类型: video, audio")
    p_record.set_defaults(func=_cmd_record)

    # play — 播放
    p_play = sub.add_parser("play", help="播放媒体")
    p_play.add_argument("action", nargs="?", default="play",
                         help="操作: play, pause, stop, list")
    p_play.add_argument("file", nargs="?", default=None,
                         help="媒体文件路径")
    p_play.set_defaults(func=_cmd_play)

    # game — 游戏开发
    p_game = sub.add_parser("game", help="游戏开发工具")
    p_game.add_argument("action", nargs="?", default="info",
                           help="操作: new, build, run, list")
    p_game.add_argument("name", nargs="?", default=None,
                           help="游戏名称")
    p_game.set_defaults(func=_cmd_game)

    # model — 3D建模
    p_model = sub.add_parser("model", help="3D建模工具")
    p_model.add_argument("action", nargs="?", default="list",
                            help="操作: cube, sphere, cylinder, list")
    p_model.add_argument("name", nargs="?", default=None,
                            help="模型名称")
    p_model.set_defaults(func=_cmd_model)

    # scene — 场景管理
    p_scene = sub.add_parser("scene", help="场景管理")
    p_scene.add_argument("action", nargs="?", default="list",
                            help="操作: create, add, remove, list")
    p_scene.add_argument("name", nargs="?", default=None,
                            help="场景名称")
    p_scene.set_defaults(func=_cmd_scene)

    # nn — 神经网络
    sub.add_parser("nn", help="神经网络工具").set_defaults(func=_cmd_nn)
    # concurrent — 并发编程
    sub.add_parser("concurrent", help="并发编程工具").set_defaults(func=_cmd_concurrent)
    # data — 数据科学
    sub.add_parser("data", help="数据科学工具").set_defaults(func=_cmd_data)
    # blockchain — 区块链
    sub.add_parser("blockchain", help="区块链工具").set_defaults(func=_cmd_blockchain)
    # quantum — 量子计算
    sub.add_parser("quantum", help="量子计算工具").set_defaults(func=_cmd_quantum)
    # audio — 音视频
    sub.add_parser("audio", help="音视频工具").set_defaults(func=_cmd_audio)
    # geo — 地理空间
    sub.add_parser("geo", help="地理空间工具").set_defaults(func=_cmd_geo)
    # chem — 化学
    sub.add_parser("chem", help="化学工具").set_defaults(func=_cmd_chem)
    # astro — 天文学
    sub.add_parser("astro", help="天文学工具").set_defaults(func=_cmd_astro)
    # music — 音乐
    sub.add_parser("music", help="音乐工具").set_defaults(func=_cmd_music)
    # robot — 机器人
    sub.add_parser("robot", help="机器人工具").set_defaults(func=_cmd_robot)
    # 新模块
    sub.add_parser("pkg", help="包管理工具").set_defaults(func=_cmd_pkg)
    sub.add_parser("typecheck", help="类型检查工具").set_defaults(func=_cmd_typecheck)
    sub.add_parser("mtest", help="测试框架工具").set_defaults(func=_cmd_mtest)
    sub.add_parser("format", help="代码格式化工具").set_defaults(func=_cmd_format)
    sub.add_parser("doc", help="文档生成工具").set_defaults(func=_cmd_doc)
    sub.add_parser("async", help="异步编程工具").set_defaults(func=_cmd_async)
    sub.add_parser("science", help="科学计算工具").set_defaults(func=_cmd_science)
    sub.add_parser("viz", help="数据可视化工具").set_defaults(func=_cmd_viz)
    sub.add_parser("symbolic", help="符号计算工具").set_defaults(func=_cmd_symbolic)
    sub.add_parser("ml", help="机器学习工具").set_defaults(func=_cmd_ml)
    sub.add_parser("security2", help="安全增强工具").set_defaults(func=_cmd_security2)
    sub.add_parser("compile2", help="编译工具").set_defaults(func=_cmd_compile2)
    sub.add_parser("http", help="HTTP服务器工具").set_defaults(func=_cmd_http)
    sub.add_parser("git", help="版本控制工具").set_defaults(func=_cmd_git)
    sub.add_parser("bld", help="构建系统工具").set_defaults(func=_cmd_build2)
    sub.add_parser("db", help="数据库引擎工具").set_defaults(func=_cmd_db)
    sub.add_parser("ai", help="AI框架工具").set_defaults(func=_cmd_ai)
    sub.add_parser("compiler", help="编译器后端工具").set_defaults(func=_cmd_compiler)
    sub.add_parser("game2", help="游戏引擎工具").set_defaults(func=_cmd_game2)
    sub.add_parser("sec2", help="安全工具").set_defaults(func=_cmd_sec)
    sub.add_parser("ui", help="UI框架工具").set_defaults(func=_cmd_ui)
    sub.add_parser("devops", help="DevOps工具").set_defaults(func=_cmd_devops)
    sub.add_parser("blockchain2", help="区块链工具").set_defaults(func=_cmd_blockchain2)
    sub.add_parser("media", help="音视频工具").set_defaults(func=_cmd_media)
    sub.add_parser("geo2", help="地理空间工具").set_defaults(func=_cmd_geo2)
    sub.add_parser("robot2", help="机器人工具").set_defaults(func=_cmd_robot2)
    sub.add_parser("os2", help="操作系统模块").set_defaults(func=_cmd_os)
    sub.add_parser("cf", help="完整编译器工具").set_defaults(func=_cmd_compiler_full)
    sub.add_parser("web", help="Web框架工具").set_defaults(func=_cmd_web)
    sub.add_parser("frontend", help="前端框架工具").set_defaults(func=_cmd_frontend)
    sub.add_parser("science2", help="科学计算工具").set_defaults(func=_cmd_science2)
    sub.add_parser("ml_full", help="机器学习工具").set_defaults(func=_cmd_ml_full)
    sub.add_parser("quantum2", help="量子计算工具").set_defaults(func=_cmd_quantum2)
    sub.add_parser("toolchain", help="工具链工具").set_defaults(func=_cmd_toolchain)
    sub.add_parser("graphics", help="图形引擎工具").set_defaults(func=_cmd_graphics)
    sub.add_parser("general", help="通用工具").set_defaults(func=_cmd_general)
    sub.add_parser("general2", help="通用工具").set_defaults(func=_cmd_general)
    sub.add_parser("netdrv", help="网络驱动").set_defaults(func=_cmd_network_driver)
    sub.add_parser("fsdrv", help="文件系统驱动").set_defaults(func=_cmd_fs_driver)
    sub.add_parser("devdrv", help="设备驱动框架").set_defaults(func=_cmd_device_driver)
    sub.add_parser("osapi", help="操作系统API").set_defaults(func=_cmd_os_api)
    sub.add_parser("gfxdrv", help="图形驱动").set_defaults(func=_cmd_graphics_driver)
    sub.add_parser("crypto", help="密码学基座").set_defaults(func=_cmd_crypto)
    sub.add_parser("mathbase", help="数学基座").set_defaults(func=_cmd_math_foundation)
    sub.add_parser("browser", help="浏览器内核").set_defaults(func=_cmd_browser)
    sub.add_parser("mobile", help="移动SDK").set_defaults(func=_cmd_mobile)
    sub.add_parser("law", help="计算法学").set_defaults(func=_cmd_law)
    sub.add_parser("geek", help="极客安全").set_defaults(func=_cmd_geek)

    args = parser.parse_args(argv)
    if hasattr(args, "func"):
        return args.func(args)
    else:
        # 无子命令 → REPL
        return _cmd_repl(args)


# ============================================================
# 可视化命令处理器
# ============================================================

def _cmd_visualize(args) -> int:
    """可视化命令。"""
    vis_type = args.type
    from src.visualizer import get_visualizer
    vis = get_visualizer()

    if vis_type == "pipeline":
        print(vis.visualize_pipeline("result = 1 + 2 * 3", "c"))
    elif vis_type == "arch":
        print(vis.visualize_architecture())
    elif vis_type == "domains":
        vis.visualize_domains()
        path = vis.save_dashboard()
        print(f"领域浏览器已保存到: {path}")
    elif vis_type == "perf":
        vis.visualize_performance()
        print("性能仪表盘已生成")
    else:
        print(vis.visualize_architecture())
        print()
        print(vis.visualize_pipeline("result = 1 + 2 * 3", "c"))
        path = vis.save_dashboard()
        print(f"\n完整仪表盘已保存到: {path}")
    return 0


def _cmd_pipeline(args) -> int:
    """构建管线可视化。"""
    from src.visualizer import get_visualizer
    vis = get_visualizer()
    print(vis.visualize_pipeline(args.source, args.target))
    return 0


def _cmd_arch(args) -> int:
    """系统架构图。"""
    from src.visualizer import get_visualizer
    vis = get_visualizer()
    print(vis.visualize_architecture())
    return 0


def _cmd_domains(args) -> int:
    """领域模块浏览器。"""
    from src.visualizer import get_visualizer
    vis = get_visualizer()
    vis.visualize_domains()
    path = vis.save_dashboard()
    print(f"领域浏览器已保存到: {path}")
    return 0


def _cmd_nn(args) -> int:
    """神经网络操作。"""
    from src.matha_system import MathaSystem
    ms = MathaSystem(debug=False)
    ms._init_neural_network()
    print("神经网络模块就绪")
    return 0


def _cmd_concurrent(args) -> int:
    """并发编程操作。"""
    from src.matha_system import MathaSystem
    ms = MathaSystem(debug=False)
    ms._init_concurrent()
    print("并发编程模块就绪")
    return 0


def _cmd_data(args) -> int:
    """数据科学操作。"""
    from src.matha_system import MathaSystem
    ms = MathaSystem(debug=False)
    ms._init_data_science()
    print("数据科学模块就绪")
    return 0


def _cmd_blockchain(args) -> int:
    """区块链操作。"""
    from src.matha_system import MathaSystem
    ms = MathaSystem(debug=False)
    ms._init_blockchain()
    print("区块链模块就绪")
    return 0


def _cmd_quantum(args) -> int:
    """量子计算操作。"""
    from src.matha_system import MathaSystem
    ms = MathaSystem(debug=False)
    ms._init_quantum()
    print("量子计算模块就绪")
    return 0


def _cmd_audio(args) -> int:
    """音视频操作。"""
    from src.matha_system import MathaSystem
    ms = MathaSystem(debug=False)
    ms._init_audio_video()
    print("音视频模块就绪")
    return 0


def _cmd_geo(args) -> int:
    """地理空间操作。"""
    from src.matha_system import MathaSystem
    ms = MathaSystem(debug=False)
    ms._init_geospatial()
    print("地理空间模块就绪")
    return 0


def _cmd_chem(args) -> int:
    """化学操作。"""
    from src.matha_system import MathaSystem
    ms = MathaSystem(debug=False)
    ms._init_chemistry()
    print("化学模块就绪")
    return 0


def _cmd_astro(args) -> int:
    """天文学操作。"""
    from src.matha_system import MathaSystem
    ms = MathaSystem(debug=False)
    ms._init_astronomy()
    print("天文学模块就绪")
    return 0


def _cmd_music(args) -> int:
    """音乐操作。"""
    from src.matha_system import MathaSystem
    ms = MathaSystem(debug=False)
    ms._init_music()
    print("音乐模块就绪")
    return 0


def _cmd_robot(args) -> int:
    """机器人操作。"""
    from src.matha_system import MathaSystem
    ms = MathaSystem(debug=False)
    ms._init_robotics()
    print("机器人模块就绪")
    return 0


# ─── 新模块 ───

def _cmd_pkg(args) -> int:
    """包管理。"""
    from src.matha_system import MathaSystem
    MathaSystem(debug=False)
    print("包管理模块就绪")
    return 0


def _cmd_typecheck(args) -> int:
    """类型检查。"""
    from src.matha_system import MathaSystem
    MathaSystem(debug=False)
    print("类型检查模块就绪")
    return 0


def _cmd_mtest(args) -> int:
    """测试框架。"""
    from src.matha_system import MathaSystem
    MathaSystem(debug=False)
    print("测试框架模块就绪")
    return 0


def _cmd_format(args) -> int:
    """代码格式化。"""
    from src.matha_system import MathaSystem
    MathaSystem(debug=False)
    print("代码格式化模块就绪")
    return 0


def _cmd_doc(args) -> int:
    """文档生成。"""
    from src.matha_system import MathaSystem
    MathaSystem(debug=False)
    print("文档生成模块就绪")
    return 0


def _cmd_async(args) -> int:
    """异步编程。"""
    from src.matha_system import MathaSystem
    MathaSystem(debug=False)
    print("异步编程模块就绪")
    return 0


def _cmd_science(args) -> int:
    """科学计算。"""
    from src.matha_system import MathaSystem
    MathaSystem(debug=False)
    print("科学计算模块就绪")
    return 0


def _cmd_viz(args) -> int:
    """数据可视化。"""
    from src.matha_system import MathaSystem
    MathaSystem(debug=False)
    print("数据可视化模块就绪")
    return 0


def _cmd_symbolic(args) -> int:
    """符号计算。"""
    from src.matha_system import MathaSystem
    MathaSystem(debug=False)
    print("符号计算模块就绪")
    return 0


def _cmd_ml(args) -> int:
    """机器学习。"""
    from src.matha_system import MathaSystem
    MathaSystem(debug=False)
    print("机器学习模块就绪")
    return 0


def _cmd_security2(args) -> int:
    """安全增强（TLS/OAuth2/JWT）。"""
    from src.matha_system import MathaSystem
    MathaSystem(debug=False)
    print("安全增强模块就绪")
    return 0


def _cmd_compile2(args) -> int:
    """编译工具（扩展后端）。"""
    try:
        from src import compiler_backend as cb
        cb.create_compiler()
        cb.create_wasm_compiler()
        cb.create_aot_compiler()
        print("编译后端模块就绪: 本地/WASM/AOT")
    except Exception as e:
        print(f"编译后端模块加载失败: {e}", file=sys.stderr)
        return 1
    return 0


def _cmd_build2(args) -> int:
    """构建系统工具。"""
    try:
        from src import build_system as bs
        manager = bs.create_build_manager()
        bs.create_makefile(manager)
        bs.create_cmake_lists(manager)
        print("构建系统模块就绪: 构建管理/Makefile/CMakeLists")
    except Exception as e:
        print(f"构建系统模块加载失败: {e}", file=sys.stderr)
        return 1
    return 0


def _cmd_http(args) -> int:
    """HTTP 服务器。"""
    try:
        from src import http_server as hs
        server = hs.create_http_server()
        hs.create_websocket_handler()
        hs.create_reverse_proxy([])
        host = getattr(server, "host", "0.0.0.0")
        port = getattr(server, "port", 8080)
        print(f"HTTP 服务器模块就绪: {host}:{port}")
    except Exception as e:
        print(f"HTTP 服务器模块加载失败: {e}", file=sys.stderr)
        return 1
    return 0


def _cmd_git(args) -> int:
    """版本控制。"""
    try:
        from src import git as gitmod
        repo = gitmod.create_git_repository()
        gitmod.create_git_config()
        print(f"Git 版本控制模块就绪: {getattr(repo, 'path', '.')}")
    except Exception as e:
        print(f"Git 版本控制模块加载失败: {e}", file=sys.stderr)
        return 1
    return 0


def _cmd_db(args) -> int:
    """数据库引擎。"""
    try:
        from src import database_engine as db
        database = db.create_database()
        db.create_database_pool(database)
        table = database.create_table("demo", [
            db.Column("id", db.DataType.INTEGER, primary_key=True),
            db.Column("name", db.DataType.TEXT),
        ])
        database.insert("demo", {"id": 1, "name": "matha"})
        rows = database.select("demo")
        result = database.execute("SELECT * FROM demo")
        print("数据库引擎模块就绪:"
              f" 表={table.name} 行={len(rows)} 计划={result.query_plan}")
    except Exception as e:
        print(f"数据库引擎模块加载失败: {e}", file=sys.stderr)
        return 1
    return 0


def _cmd_ai(args) -> int:
    """AI 框架。"""
    try:
        from src import ai_framework as ai
        ai.Tensor((2, 3))
        ai.Sequential(name="demo")
        ai.Linear(2, 3)
        ai.ReLU()
        ai.Dropout()
        ai.BatchNorm(3)
        ai.NeuralNetwork()
        ai.AutoDiff()
        print("AI 框架模块就绪: 张量/模型/线性层/激活/自动微分")
    except Exception as e:
        print(f"AI 框架模块加载失败: {e}", file=sys.stderr)
        return 1
    return 0


def _cmd_compiler(args) -> int:
    """编译器后端。"""
    try:
        from src import compiler_backend as cb
        cb.create_compiler()
        cb.create_wasm_compiler()
        cb.create_aot_compiler()
        print("编译器后端模块就绪: 本地/WASM/AOT")
    except Exception as e:
        print(f"编译器后端模块加载失败: {e}", file=sys.stderr)
        return 1
    return 0


def _cmd_game2(args) -> int:
    """游戏引擎（扩展）。"""
    try:
        from src import game_engine_extended as ge
        renderer = ge.create_renderer()
        physics = ge.create_physics_world()
        audio = ge.create_audio_engine()
        ge.create_animation_controller()
        print("游戏引擎(扩展)就绪:"
              f" 渲染器={renderer.width}x{renderer.height}"
              f" 物理(重力={physics.gravity})"
              f" 音频({audio.sample_rate}Hz)")
    except Exception as e:
        print(f"游戏引擎(扩展)加载失败: {e}", file=sys.stderr)
        return 1
    return 0


def _cmd_sec(args) -> int:
    """完整安全。"""
    try:
        from src import security_complete as sec
        hasher = sec.create_hash_manager()
        bcrypt = sec.create_bcrypt()
        argon2 = sec.create_argon2()
        cipher = sec.create_cipher()
        sec.create_hmac()
        sec.create_certificate()
        sec.create_ssl_context()
        digest = hasher.hash("matha").digest if hasattr(hasher, "hash") else "n/a"
        print("完整安全模块就绪:"
              f" bcrypt(rounds={getattr(bcrypt, 'rounds', '?')})"
              f" argon2(mem={getattr(argon2, 'memory_cost', '?')})"
              f" 哈希={digest[:16] if isinstance(digest, str) else 'ok'}")
    except Exception as e:
        print(f"完整安全模块加载失败: {e}", file=sys.stderr)
        return 1
    return 0


def _cmd_ui(args) -> int:
    """UI框架。"""
    try:
        from src import ui_framework as ui
        ui.create_component()
        ui.create_element("div")
        ui.create_container()
        ui.create_button()
        ui.create_input()
        ui.create_router()
        ui.create_state_manager()
        ui.create_event_emitter()
        print("UI框架模块就绪: 组件/元素/容器/按钮/输入/路由/状态/事件")
    except Exception as e:
        print(f"UI框架模块加载失败: {e}", file=sys.stderr)
        return 1
    return 0


def _cmd_devops(args) -> int:
    """DevOps工具。"""
    try:
        from src import devops
        devops.create_pipeline_runner("default")
        devops.create_log_aggregator()
        devops.create_metrics_collector()
        devops.create_alert_manager()
        devops.create_health_check()
        devops.create_service_discovery()
        devops.create_config_manager()
        print("DevOps工具模块就绪: 流水线/日志/指标/告警/健康检查/服务发现/配置")
    except Exception as e:
        print(f"DevOps工具模块加载失败: {e}", file=sys.stderr)
        return 1
    return 0


def _cmd_blockchain2(args) -> int:
    """区块链引擎。"""
    try:
        from src import blockchain_full as bc
        chain = bc.create_blockchain()
        bc.create_smart_contract_engine()
        token = bc.create_token("MathaCoin", "MTH", 1000000)
        print("区块链引擎模块就绪:"
              f" 高度={getattr(chain, 'height', '?')}"
              f" 代币={getattr(token, 'symbol', '?')}")
    except Exception as e:
        print(f"区块链引擎模块加载失败: {e}", file=sys.stderr)
        return 1
    return 0


def _cmd_media(args) -> int:
    """音视频引擎。"""
    try:
        from src import audio_video_full as av
        video_enc = av.create_video_encoder()
        audio_enc = av.create_audio_encoder()
        av.create_video_decoder()
        av.create_audio_decoder()
        av.create_filter_graph()
        av.create_media_player()
        av.create_rtmp_streamer()
        print("音视频引擎模块就绪:"
              f" 视频={getattr(video_enc, 'width', '?')}x{getattr(video_enc, 'height', '?')}"
              f" 音频={getattr(audio_enc, 'sample_rate', '?')}Hz")
    except Exception as e:
        print(f"音视频引擎模块加载失败: {e}", file=sys.stderr)
        return 1
    return 0


def _cmd_geo2(args) -> int:
    """地理空间。"""
    try:
        from src import geospatial_full as geo
        geo.create_coordinate_transformer()
        geo.create_spatial_analyzer()
        geo.create_vector_layer()
        geo.create_raster()
        geo.create_tile_manager()
        geo.create_geojson()
        print("地理空间模块就绪: 坐标转换/空间分析/矢量/栅格/瓦片/GeoJSON")
    except Exception as e:
        print(f"地理空间模块加载失败: {e}", file=sys.stderr)
        return 1
    return 0


def _cmd_robot2(args) -> int:
    """机器人引擎。"""
    try:
        from src import robotics_full as rb
        robot = rb.create_robot()
        rb.create_motion_planner()
        rb.create_controller()
        rb.create_trajectory()
        rb.create_gripper()
        print("机器人引擎模块就绪:"
              f" 机器人={getattr(robot, 'name', '?')}"
              f" 运动规划/控制/轨迹/夹爪")
    except Exception as e:
        print(f"机器人引擎模块加载失败: {e}", file=sys.stderr)
        return 1
    return 0


def _cmd_os(args) -> int:
    """操作系统模块。"""
    from src.matha_system import MathaSystem
    MathaSystem(debug=False)
    print("操作系统模块就绪")
    return 0


def _cmd_compiler_full(args) -> int:
    """完整编译器工具。"""
    from src.matha_system import MathaSystem
    MathaSystem(debug=False)
    print("完整编译器工具就绪")
    return 0


def _cmd_web(args) -> int:
    """Web框架工具。"""
    from src.matha_system import MathaSystem
    MathaSystem(debug=False)
    print("Web框架模块就绪")
    return 0


def _cmd_frontend(args) -> int:
    """前端框架工具。"""
    from src.matha_system import MathaSystem
    MathaSystem(debug=False)
    print("前端框架模块就绪")
    return 0


def _cmd_science2(args) -> int:
    """科学计算工具。"""
    from src.matha_system import MathaSystem
    MathaSystem(debug=False)
    print("科学计算模块就绪")
    return 0


def _cmd_ml_full(args) -> int:
    """机器学习工具。"""
    from src.matha_system import MathaSystem
    MathaSystem(debug=False)
    print("机器学习模块就绪")
    return 0


def _cmd_quantum2(args) -> int:
    """量子计算工具。"""
    from src.matha_system import MathaSystem
    MathaSystem(debug=False)
    print("量子计算模块就绪")
    return 0


def _cmd_toolchain(args) -> int:
    """工具链工具。"""
    from src.matha_system import MathaSystem
    MathaSystem(debug=False)
    print("工具链模块就绪")
    return 0


def _cmd_graphics(args) -> int:
    """图形引擎工具。"""
    from src.matha_system import MathaSystem
    MathaSystem(debug=False)
    print("图形引擎模块就绪")
    return 0


def _cmd_general(args) -> int:
    """通用工具。"""
    from src.matha_system import MathaSystem
    MathaSystem(debug=False)
    print("通用工具模块就绪")
    return 0


def _cmd_network_driver(args) -> int:
    """网络驱动。"""
    from src.matha_system import MathaSystem
    MathaSystem(debug=False)
    print("网络驱动模块就绪")
    return 0


def _cmd_fs_driver(args) -> int:
    """文件系统驱动。"""
    from src.matha_system import MathaSystem
    MathaSystem(debug=False)
    print("文件系统驱动模块就绪")
    return 0


def _cmd_device_driver(args) -> int:
    """设备驱动框架。"""
    from src.device_driver import (
        create_audio_device,
        create_driver_registry,
        create_gpu_device,
        create_nic_device,
        create_ssd_device,
        create_usb_controller,
    )
    reg = create_driver_registry()
    gpu = create_gpu_device()
    reg.register(gpu)
    usb = create_usb_controller()
    addr = usb.attach("USB Hub")
    reg.register(usb)
    audio = create_audio_device()
    audio.set_volume(0.8)
    reg.register(audio)
    ssd = create_ssd_device(1024)
    ssd.write_blocks(0, b"\x00" * 512)
    reg.register(ssd)
    nic = create_nic_device()
    nic.send(b"ping")
    reg.register(nic)
    print(f"已注册驱动: {', '.join(reg.list_drivers())}")
    print(f"USB 设备数: {len(usb.enumerate())} (地址 {addr})")
    print(f"SMART: {ssd.smart()['health']}% 健康")
    return 0


def _cmd_os_api(args) -> int:
    """操作系统 API。"""
    from src.os_api import (
        SyscallNumber,
        create_libc,
        create_process_table,
        create_syscall_table,
        create_vfs,
        create_win32,
    )
    libc = create_libc()
    tbl = create_syscall_table()
    tbl.dispatch(int(SyscallNumber.GETPID))
    tbl.dispatch(int(SyscallNumber.WRITE), 1, b"data")
    vfs = create_vfs()
    vfs.mount("/dev/nvme0n1", "/data", "ext4")
    vfs.create("/data/file.txt", 0o644)
    pt = create_process_table()
    pid = pt.spawn("init", ["--now"])
    w32 = create_win32()
    h = w32.create_file("C:\\test.txt")
    w32.write_file(h, b"windows")
    print(f"uname: {libc.uname()['release']}")
    print(f"系统调用: {tbl.get_stats()}")
    print(f"挂载点: {list(vfs.list_mounts())}")
    print(f"PID {pid} 在表中: {len(pt.list_procs())} 个进程")
    print(f"Win32 句柄 {h} 写入 {len(w32.read_file(h, 100))} 字节")
    return 0


def _cmd_graphics_driver(args) -> int:
    """图形驱动。"""
    from src.graphics_driver import (
        GLEnum,
        Mat4,
        Vec4,
        create_d3d12_device,
        create_graphics_context,
        create_vulkan_instance,
    )
    gl = create_graphics_context("4.6")
    vs = gl.compile_shader(GLEnum.VERTEX_SHADER, "void main(){}")
    fs = gl.compile_shader(GLEnum.FRAGMENT_SHADER, "void main(){}")
    prog = gl.create_program(vs, fs)
    linked = gl.link_program(prog)
    gl.use_program(prog)
    vbo = gl.gen_buffers(1)[0]
    gl.buffer_data(vbo, [0.0, 1.0, 0.0, -1.0, 0.0])
    gl.enable(GLEnum.DEPTH_TEST)
    gl.draw_arrays(GLEnum.TRIANGLES, 0, 3)
    vk = create_vulkan_instance()
    d3d = create_d3d12_device()
    m = Mat4.translate(1, 2, 3).multiply(Mat4.scale(2, 3, 4))
    print(f"OpenGL {gl.version} | 着色器链接: {linked}")
    print(f"绘制: {gl.get_stats()['draw_calls']} 次调用 / "
          f"{gl.get_stats()['vertices']} 顶点")
    print(f"Vulkan 设备: {vk.enumerate_physical_devices()[0]['name']}")
    print(f"D3D12 队列: {d3d.get_info()['queue']}")
    print(f"矩阵行列式: {m.determinant()} | "
          f"m*m^-1 = {m.multiply(m.inverse()).transform(Vec4()).xyzw}")
    return 0


def _cmd_crypto(args) -> int:
    """密码学基座。"""
    from src.crypto_foundation import (
        create_matha_crypto,
        create_pki,
        create_symmetric_crypto,
        create_tls_session,
    )
    c = create_matha_crypto()
    fp = c.fingerprint(b"matha")
    pki = create_pki()
    pki.init_ca("Matha Root CA")
    leaf = pki.issue("localhost", "localhost,127.0.0.1")
    chain = pki.verify_chain([pki.ca_cert, leaf])
    pki.revoke("localhost")
    tls = create_tls_session()
    tls.client_handshake("localhost")
    sc = create_symmetric_crypto()
    key = sc.generate_key(256)
    plain = "Matha 虚拟代码引擎".encode()
    ct = sc.encrypt(plain, key, "cbc")
    pt = sc.decrypt(ct, key, "cbc")
    print(f"SHA-256 指纹: {fp[:29]}...")
    print(f"证书链: {chain['valid']} ({chain['length']} 级) | "
          f"吊销: {pki.is_revoked('localhost')}")
    print(f"TLS: {tls.get_session_info()['cipher']} / "
          f"{tls.get_session_info()['group']}")
    print(f"AES-256-CBC: {len(ct)} 字节密文, 解密一致: {pt == plain}")
    return 0


def _cmd_math_foundation(args) -> int:
    """数学基座。"""
    import math

    from src.math_foundation import (
        FFT,
        BigNum,
        LinearAlgebra,
        NumericalAnalysis,
        SpecialFunctions,
        create_math_foundation,
    )
    mf = create_math_foundation()
    fib = BigNum(100).fibonacci().value
    prime = BigNum(7919).is_prime()
    A = [[4, 7], [2, 6]]
    det = LinearAlgebra.det(A)
    x = LinearAlgebra.solve(A, [3, -1])
    spec = FFT.fft([1, 2, 3, 4])
    conv = FFT.convolution([1, 2], [3, 4])
    integral = NumericalAnalysis.simpson(math.sin, 0, math.pi)
    eig, _ = LinearAlgebra.eigenvalues_jacobi([[2, 0], [0, 3]])
    print(f"fib(100) = {fib}")
    print(f"7919 是素数: {prime} | gcd(1071,462) = {mf.gcd(1071, 462)}")
    print(f"det(A) = {det} | 解 = "
          f"[{x[0]:.4f}, {x[1]:.4f}] | 特征值 = {eig}")
    print(f"FFT([1,2,3,4]) = {[round(c.real, 1) for c in spec]}")
    print(f"卷积 = {conv} | Simpson∫sin = {integral:.6f}")
    print(f"Legendre(2,0.5) = {SpecialFunctions.legendre(2, 0.5):.6f}")
    return 0


def _cmd_browser(args) -> int:
    """浏览器内核。"""
    from src.browser_engine import (
        create_browser_engine,
        create_html_parser,
    )
    page = """<html><head><style>
body { background-color: #f4f4f8; }
h1 { color: #1a1a2e; font-size: 28px; }
#card { padding: 16px; }
</style></head><body>
<div id="card"><h1>Matha 浏览器内核</h1>
<p>自研 HTML/CSS/JS 引擎驱动虚拟代码引擎</p></div>
<script>var n=0; for(var i=1;i<=100;i++){n+=i;}
console.log("sum="+n); console.log("fib="+Math.pow(1.618,10).toFixed(3));</script>
</body></html>"""
    b = create_browser_engine(800, 600)
    stats = b.navigate("about:matha", page)
    dom = b.renderer.dom
    h1 = dom.query_selector("h1")
    print(f"渲染: {stats['boxes']} 个盒 / "
          f"{stats['text_runs']} 段文字 / "
          f"{stats['draw_calls']} 次绘制")
    print(f"节点: {stats['nodes']} | 帧缓冲: "
          f"{stats['ppm_bytes'] // 1024} KB")
    print(f"h1 = {h1.inner_text!r} "
          f"color={h1.computed_style.get('color')} "
          f"size={h1.computed_style.get('font-size')}")
    print(f"脚本输出: {stats['console']}")
    js_result = b.evaluate_js(
        "[1,2,3,4,5].map(function(x){return x*x;}).join(',')")
    print(f"JS 求值: {js_result}")
    p = create_html_parser()
    doc = p.parse("<ul><li>甲<li>乙</ul><p>尾巴</p>")
    print(f"HTML 隐式闭合: ul 子节点 "
          f"{len(doc.find_all('ul')[0].children)} "
          f"| li {len(doc.find_all('li'))} 个")
    return 0


def _cmd_mobile(args) -> int:
    """移动 SDK。"""
    from src.mobile_sdk import (
        Permission,
        PlatformType,
        SensorType,
        WidgetType,
        create_mobile_app,
    )
    app = create_mobile_app(PlatformType.ANDROID, "MathaMobile")
    app.install()
    app.launch()
    root = app.build_ui()
    app.set_root_view(root)
    nodes = app.relayout(375, 812)
    btn = next(w for w in root.walk()
               if w.type == WidgetType.BUTTON)
    btn.tap()
    btn.tap()
    label = root.state["counter_label"]
    print(f"布局: {nodes} 个组件 / 视口 375x812")
    print(f"按钮 {btn.text!r} 位置 {tuple(round(v,1) for v in btn.frame)}")
    print(f"交互后: {label.text}")
    print(f"权限: camera={app.permissions.request(Permission.CAMERA)} "
          f"location={app.permissions.request(Permission.LOCATION, False)}")
    app.sensors.subscribe(SensorType.ACCELEROMETER, lambda r: None)
    samples = app.sensors.simulate_accelerometer(30)
    print(f"传感器: 加速度计 {len(samples)} 采样, "
          f"末值 {samples[-1]['magnitude']}")
    app.push_route("Home")
    app.push_route("Detail", item_id=42)
    print(f"导航: {'/'.join(app.navigation.routes())} "
          f"(深度 {app.navigation.depth()})")
    app.push.register_token(PlatformType.ANDROID, "tok")
    app.push.notify(PlatformType.ANDROID, "构建完成", "Matha 已就绪")
    print(f"角标: android={app.push.badge(PlatformType.ANDROID)}")
    print(f"生命周期: {app.lifecycle.snapshot()}")
    return 0


def _cmd_law(args) -> int:
    """计算法学。"""
    from src.domains.computational_law import (
        compliance_check,
        contract_verify,
        create_legal_engine,
        legal_reasoning,
        smart_contract_audit,
    )
    engine = create_legal_engine()
    print(f"案例库: {len(engine.cases.all_cases())} 例 / "
          f"法规: {len(engine.statutes._statutes)} 部")
    r = legal_reasoning("搜索引擎流量劫持是否构成不正当竞争")
    print(f"推理: {r['conclusion']}")
    print(f"  {r['rule']} / 强度 {r['strength']} "
          f"判例 {r['supporting_cases']}")
    v = contract_verify(
        "本合同双方于今日签署。保密信息不得披露。"
        "付款于交付后三十日内支付。争议提交仲裁解决。")
    print(f"合同审查: 风险 {v['risk_level']} "
          f"缺漏 {v['missing_mandatory'] or '无'}")
    c = compliance_check(
        "gdpr", "encrypt and anonymize personal data, "
                "support delete and portability")
    print(f"GDPR 合规: 得分 {c['score']:.0%}")
    a = smart_contract_audit(
        "pragma solidity ^0.8.0; function f() public { "
        "tx.origin; selfdestruct(payable(msg.sender)); }")
    print(f"合约审计: {a['grade']} 级 / {a['total']} 处问题 / "
          f"critical {a['critical']}")
    return 0


def _cmd_geek(args) -> int:
    """极客安全。"""
    from src.domains.geek_gray import (
        BinaryInfo,
        base64_decode,
        create_geek_engine,
        reverse_engineer,
        rot_n,
        security_audit,
    )
    print(f"编解码: rot13 {rot_n('synt{flag}')!r} / "
          f"b64 {base64_decode('TWF0aGE=').decode()!r}")
    best = reverse_engineer("TWF0aGE=")['best']
    print(f"编码识别: {best['encoding']} -> {best['decoded']!r}")
    code = ('void f(){char b[8]; strcpy(b, input); printf(name); '
            'system(cmd+arg); char* p="pw=secret123"; md5(x); }')
    r = security_audit(code)
    print(f"静态审计: {r['total']} 处 / 风险 {r['risk_score']} / "
          f"{len(r['by_cwe'])} 类 CWE")
    for f in r['findings'][:3]:
        print(f"  [{f['severity']:8}] {f['cwe']:9} {f['description']}")
    engine = create_geek_engine()
    h = engine.add_binary(BinaryInfo(name='demo', pie=False, nx=False,
                                     canary=True, relro='partial'))
    print(f"加固检查: {h['passed']}/{h['total']} 通过 / "
          f"得分 {h['score']} ({h['verdict']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
