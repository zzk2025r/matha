# RISC-V 裸机驱动构建脚本
# 用法: python scripts/build_riscv_baremetal.py [target_arch] [expression]
# 示例: python scripts/build_riscv_baremetal.py riscv32 "x^2 + 3*x - 5"

from __future__ import annotations
import sys
import os
import json
import argparse
import time
from pathlib import Path

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from src.hardware.hal_v2 import (
    Architecture, BareMetalTarget, DriverKind, DriverSpec,
    ProtocolSpec, ProtocolType,
    get_side_effect_engine, get_pointer_manager,
    get_protocol_parser, get_driver_generator, get_native_backend,
)
from src.compiler.native import ProtocolInterpreter, DriverBuilder, NativeCompiler
from src.symbolic import symbol_expr, eval_expr


def parse_args():
    parser = argparse.ArgumentParser(description="Matha v2.0 RISC-V Bare-Metal Builder")
    parser.add_argument("expression", nargs="?", default="x^2 + 3*x - 5",
                        help="Matha 表达式 (默认: x^2 + 3*x - 5)")
    parser.add_argument("--arch", default="riscv32",
                        choices=["riscv32", "riscv64", "arm64", "x86_64"],
                        help="目标架构 (默认: riscv32)")
    parser.add_argument("--lang", default="c", choices=["c", "assembly", "python"],
                        help="输出语言 (默认: c)")
    parser.add_argument("--func-name", default="compute",
                        help="函数名 (默认: compute)")
    parser.add_argument("--output", default=None,
                        help="输出文件路径 (默认: stdout)")
    parser.add_argument("--driver", action="store_true",
                        help="生成驱动模板而非编译表达式")
    parser.add_argument("--driver-name", default="my_driver",
                        help="驱动名称 (默认: my_driver)")
    parser.add_argument("--driver-kind", default="math",
                        choices=["math", "sensor", "actuator", "comm"],
                        help="驱动类型 (默认: math)")
    parser.add_argument("--protocol", default=None,
                        help="协议规格 JSON 文件路径")
    parser.add_argument("--optimize", default="Os",
                        choices=["O0", "O1", "O2", "Os"],
                        help="优化级别 (默认: Os)")
    parser.add_argument("--verify", action="store_true",
                        help="验证表达式数值结果")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="详细输出")
    return parser.parse_args()


def main():
    args = parse_args()

    # 初始化子系统
    sse = get_side_effect_engine(mode="full")
    pmgr = get_pointer_manager(page_count=16)
    pp = get_protocol_parser()
    dg = get_driver_generator()
    nb = get_native_backend()
    pi = ProtocolInterpreter(pp)
    db = DriverBuilder(dg)
    nc = NativeCompiler(nb, sse, pmgr)

    arch_map = {
        "riscv32": Architecture.RISCV32,
        "riscv64": Architecture.RISCV64,
        "arm64": Architecture.ARM64,
        "x86_64": Architecture.X86_64,
    }
    arch = arch_map[args.arch]

    # 注册目标
    nb.register_target(BareMetalTarget(arch, optimize=args.optimize))

    start_time = time.time()

    if args.driver:
        # 驱动生成模式
        kind_map = {
            "math": DriverKind.MATH,
            "sensor": DriverKind.SENSORS,
            "actuator": DriverKind.ACTUATORS,
            "comm": DriverKind.COMM,
        }
        kind = kind_map[args.driver_kind]

        spec = DriverSpec(
            name=args.driver_name,
            kind=kind,
            target_arch=arch,
            target_lang=args.lang,
            math_expr=args.expression if kind == DriverKind.MATH else "",
            params={"optimize": args.optimize},
        )
        result = dg.generate(spec)
        output = result["code"].get(args.lang, result["code"].get("core", ""))
    else:
        # 原生编译模式
        result = nc.compile(args.expression, arch, args.func_name, args.lang)
        if not result.get("success"):
            print(f"错误: 编译失败 - {result.get('error')}", file=sys.stderr)
            sys.exit(1)
        output = result["code"]

    # 数值验证
    if args.verify and args.lang == "python":
        try:
            expr = symbol_expr(args.expression)
            val = eval_expr(expr, x=1.0)
            print(f"  [验证] {args.expression}(x=1) = {val}", file=sys.stderr)
        except Exception as e:
            print(f"  [验证警告] {e}", file=sys.stderr)

    # 输出
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
        if args.verbose:
            print(f"  输出已保存: {out_path} ({len(output)} 字节)", file=sys.stderr)
    else:
        print(output)

    # 统计
    elapsed = time.time() - start_time
    if args.verbose:
        pmgr_stats = pmgr.get_stats()
        sse_stats = sse.get_stats()
        nb_stats = nb.get_stats()
        print(f"\n  [构建统计]", file=sys.stderr)
        print(f"    耗时: {elapsed*1000:.1f}ms", file=sys.stderr)
        print(f"    架构: {arch.value}, 语言: {args.lang}, 优化: {args.optimize}", file=sys.stderr)
        print(f"    代码大小: {len(output)} 字节", file=sys.stderr)
        print(f"    内存: {pmgr_stats['total_pages']}页, {pmgr_stats['total_memory_kb']}KB", file=sys.stderr)
        print(f"    编译目标: {nb_stats['registered_targets']}", file=sys.stderr)
        print(f"    副作用注册: {sse_stats['registered_funcs']}", file=sys.stderr)

    # 输出 JSON 摘要
    summary = {
        "version": "2.0.0",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "architecture": arch.value,
        "language": args.lang,
        "optimize": args.optimize,
        "expression": args.expression,
        "func_name": args.func_name,
        "code_size": len(output),
        "elapsed_ms": round(elapsed * 1000, 1),
        "memory_stats": pmgr.get_stats(),
        "compile_success": True,
    }
    print(f"\n  [摘要] {json.dumps(summary, ensure_ascii=False)}", file=sys.stderr)


if __name__ == "__main__":
    main()
