"""b09 预备融合·离线对照工具（P4 预备资产，不进任何门禁）。

两种模式：
  dump  --out <json>                当前工作树编译器，在 MATHA_B09_FUSE=0/1 下分别
                                    编译语料，导出逐指令字节码 + 运行值 + CALL arity 形状
  check --ref <json>                以「参照字节码」（HEAD 版编译器 dump 的产物）为准，
                                    断言 OFF 模式逐字节一致；ON 模式允许不同（形状变化
                                    正是本次预备手术的目标），但运行值必须一致

语料 = bench b09 场景 + for/列表推导定向回归（tests/test_listcomp_vm.py 同款口径）。
本脚本不 import 被测编译器的任何私有开关，只用公开 compile_source/run_source，
以保证「OFF 逐字节等价」的结论不受脚本自身篡改。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 以「当前工作目录」为仓库根（调用方先 cd 到目标仓库/ worktree 根再跑本脚本），
# 不硬开绝对盘符，避免参照侧意外 import 到被测工作树。
sys.path.insert(0, str(Path.cwd()))

# 语料：名字 -> Matha 源码。覆盖：for 单变量 / 多变量解构 / break-continue /
# 列表推导（无过滤 / 多过滤 / 嵌套）/ append 收集 / 顶层 FuncDef 遮蔽 get。
CASES: dict[str, str] = {
    "for_basic": (
        "xs = range(0)(10)\n"
        "s = 0\n"
        "for x in xs { s = s + x }\n"
        "输出(s)\n"
    ),
    "for_unpack": (
        "pairs = [[1, 2], [3, 4], [5, 6]]\n"
        "acc = 0\n"
        "for (a, b) in pairs { acc = acc + a * b }\n"
        "输出(acc)\n"
    ),
    "for_break": (
        "total = 0\n"
        "for i in range(0)(100) {\n"
        "  if i == 7 { break }\n"
        "  if i % 2 == 0 { continue }\n"
        "  total = total + i\n"
        "}\n"
        "输出(total)\n"
    ),
    "for_str": (
        "n = 0\n"
        "for ch in \"abcd\" { n = n + 1 }\n"
        "输出(n)\n"
    ),
    "lc_plain": (
        "ys = [x * x for x in range(0)(8)]\n"
        "输出(ys)\n"
    ),
    "lc_multi_if": (
        "zs = [x for x in range(0)(30) if x % 2 == 0 if x % 3 == 0]\n"
        "输出(zs)\n"
    ),
    "lc_nested": (
        "outer = [[y for y in range(0)(3)] for x in range(0)(3)]\n"
        "输出(len(outer))\n"
    ),
    "lc_append_collect": (
        "res = []\n"
        "for x in range(0)(5) { res = append(res)(x + 1) }\n"
        "输出(res)\n"
    ),
    "shadow_get_funcdef": (
        "func get(a, b) -> Int = 42\n"
        "acc = 0\n"
        "for x in range(0)(4) { acc = acc + get(x)(x) }\n"
        "输出(acc)\n"
    ),
    "b09_proxy": (
        "xs = range(0)(2000)\n"
        "s = 0\n"
        "for x in xs { s = s + x }\n"
        "输出(s)\n"
    ),
}


def _compile_dump(src: str):
    from src.mbc import opcodes as OP
    from src.mbc.compiler import compile_source
    mod = compile_source(src)
    codes = {"main": [list(i) for i in mod.main_code]}
    for fname, f in mod.functions.items():
        codes[fname] = [list(i) for i in f.code]
    argcs = [ins[1] for name, ins_list in codes.items() for ins in ins_list
             if len(ins) >= 2 and ins[0] == OP.CALL]
    return codes, argcs


def _run_dump(src: str):
    from src.mbc import run_source
    outs = run_source(src)
    return [str(o) for o in outs]


def _fuse_mode() -> str:
    """HEAD/基线编译器没有 _B09_FUSE 符号 → 视为 OFF（休眠态）。"""
    try:
        from src.mbc.compiler import _B09_FUSE
    except ImportError:
        return "OFF"
    return "ON" if _B09_FUSE else "OFF"


def do_dump(out_path: str) -> int:
    mode = _fuse_mode()
    payload = {"mode": mode, "cases": {}}
    for name, src in CASES.items():
        codes, argcs = _compile_dump(src)
        vals = _run_dump(src)
        payload["cases"][name] = {"codes": codes, "call_argcs": argcs,
                                  "outputs": vals, "source": src}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print(f"dump[{mode}] -> {out_path} ({len(payload['cases'])} cases)")
    return 0


def do_check(ref_path: str) -> int:
    mode = _fuse_mode()
    with open(ref_path, encoding="utf-8") as f:
        ref = json.load(f)
    # 参照文件必须包含 OFF 基线（HEAD 产物）
    assert ref.get("mode") == "OFF", "参照 JSON 必须是 MATHA_B09_FUSE=0 的产物"
    bad_byte, bad_val = [], []
    for name, rc in ref["cases"].items():
        codes, argcs = _compile_dump(rc["source"])
        vals = _run_dump(rc["source"])
        got = json.dumps(codes, sort_keys=True, ensure_ascii=False)
        exp = json.dumps(rc["codes"], sort_keys=True, ensure_ascii=False)
        if mode == "OFF" and got != exp:
            bad_byte.append(name)
        if vals != rc["outputs"]:
            bad_val.append(name)
        if mode == "ON":
            print(f"  [{name}] outputs={vals} call_argcs={argcs}")
    print(f"check[{mode}] cases={len(ref['cases'])} "
          f"byte_mismatch={bad_byte or '无'} value_mismatch={bad_val or '无'}")
    if mode == "OFF":
        return 1 if (bad_byte or bad_val) else 0
    return 1 if bad_val else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["dump", "check"], required=True)
    ap.add_argument("--out")
    ap.add_argument("--ref")
    a = ap.parse_args()
    if a.mode == "dump":
        return do_dump(a.out)
    return do_check(a.ref)


if __name__ == "__main__":
    sys.exit(main())
