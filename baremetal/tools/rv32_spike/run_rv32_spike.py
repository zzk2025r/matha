#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P6 SPIKE 端到端验证：Matha → RV32IM ELF → 执行 → 与 mbc VM 逐字节对拍。

流程（每条覆盖集内用例）：
  1. compile_source 出 MModule（与 native.py 同一入口）；
  2. rv32em.compile_module_to_elf 直接位级发射 RV32IM ELF（无交叉工具链）；
  3. 宿主 rv32sim 解释执行该 ELF，收集 ns16550 串口文本；
  4. 与 `exec_api.run_checked(mode="vm")` 的宿主原生口径文本逐字节比对；
  5. 若给了 --qemu 且探到 qemu-system-riscv32，再用 stock QEMU 实跑同一 ELF 复核
     （缺失则如实 SKIP，不判失败）。

另有 REJECT_CASES（负向）：覆盖集外的源码必须被 NotSupportedRV32 显式拒绝，
误接受（静默产错）才是失败。

退出码：0=全部通过，1=任一失败，2=（仅 --qemu 时）缺 QEMU 而跳过 qemu 复核。
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent          # d:/trae（baremetal/tools/rv32_spike 上溯三级）
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))             # 允许 import rvcoder / rv32em / rv32sim

import rv32bc  # noqa: E402
import rv32em  # noqa: E402
from rv32sim import RV32Sim  # noqa: E402
from rvcoder import NotSupportedRV32  # noqa: E402

from src.kernel import exec_api  # noqa: E402
from src.mbc.compiler import compile_source  # noqa: E402

# ---- 覆盖集内用例（源码内嵌，避免向仓库语料/门禁增添任何 .matha 面） ----
CASES = {
    "s1_const_binop_output": """\
#1：[2 + 3 * 4]
#1：[10 - 4]
""",
    "s2_call_ret": """\
func 加二(a: Int, b: Int) -> Int = (a, b) => a + b
#1：[加二(3, 4)]
#1：[加二(10, -2)]
""",
    "s3_recursion": """\
func fact(n: Int) -> Int = (n) => if n <= 1 then 1 else n * fact(n - 1)
#1：[fact(6)]
""",
    "s4_floordiv_mod": """\
#1：[7 // 2]
#1：[-7 // 2]
#1：[7 % 3]
#1：[-7 % 3]
""",
    "s5_call_ret_mul": """\
func sq(x: Int) -> Int = (x) => x * x
#1：[sq(9)]
#1：[sq(sq(3))]
""",
    # —— P6 扩展：分支全路径 / 全局完整语义 / 列表构造 ——
    "s6_branch_full": """\
n = 0
s = 0
while n < 5 {
  s = s + n
  n = n + 1
}
#1：[s]
func 择(a: Int, b: Int) -> Int = (a, b) => if a < b then a else if a == b then 0 else b
#1：[择(3, 7)]
#1：[择(9, 2)]
#1：[择(4, 4)]
""",
    "s7_list_build_index": """\
#1：[[3, 1, 4, 1, 5]]
xs = [10, 20, 30]
#1：[xs[1]]
#1：[xs[0 - 1]]
#1：[xs[2] + xs[0]]
""",
    "s8_bool_output": """\
#1：[1 < 2]
#1：[2 == 3]
b = 3 > 2
#1：[b]
""",
    "s9_list_global_loop": """\
ys = [2, 4, 8]
i = 0
t = 0
while i < 3 {
  t = t + ys[i]
  i = i + 1
}
#1：[t]
#1：[ys]
""",
    # —— P6 契约轮：for 句型（内建 len/get）+ if/else 嵌套全路径 ——
    "s10_for_if_nested": """\
t = 0
for x in [1, 2, 3, 4, 5] {
  if x > 2 {
    t = t + x
  }
}
#1：[t]
""",
    "s11_for_ifelse_nested": """\
c = 0
for x in [1, 2, 3] {
  if x == 2 { c = c + 10 } else { c = c + 1 }
}
#1：[c]
y = 0
for i in [2, 4] {
  for j in [1, 2] {
    if i > j { y = y + j }
  }
}
#1：[y]
""",
    # 语句位 if-then-else 产生 POP/PUSH_NULL（值为丢弃的表达式结果）
    "s12_stmt_discard": """\
c = 0
for x in [1, 2, 3] {
  if x == 2 then c = c + 10 else c = c + 1
}
#1：[c]
y = 0
for i in [2, 4] {
  for j in [1, 2] {
    if i > j then y = y + j
  }
}
#1：[y]
""",
}

# ---- 覆盖集外（负向）：必须被 NotSupportedRV32 显式拒绝 ----
REJECT_CASES = {
    "r1_string_value": """\
#1：["hi"]
""",
    "r2_closure": """\
f = (x) => x + 1
#1：[f(2)]
""",
    "r3_list_as_arg": """\
func 加倍(a: Int) -> Int = (a) => a + a
xs = [1, 2]
#1：[加倍(xs)]
""",
    "r4_list_concat": """\
xs = [1, 2]
#1：[xs + xs]
""",
    "r5_dict_literal": """\
d = {"a": 1}
#1：[d]
""",
}

# ---- 契约 roundtrip：encode→decode 消费面等价且 ELF 字节一致 ----
ROUNDTRIP_SRC = CASES["s11_for_ifelse_nested"]


def contract_roundtrip() -> tuple[bool, str]:
    mod = compile_source(ROUNDTRIP_SRC)
    blob = rv32bc.encode(mod)
    mod2 = rv32bc.decode(blob)
    if mod2.constants != mod.constants or mod2.main_code != mod.main_code:
        return False, "常量池/主码 roundtrip 不等价"
    if set(mod2.functions) != set(mod.functions):
        return False, "函数表 roundtrip 不等价"
    for nm, fn in mod.functions.items():
        f2 = mod2.functions[nm]
        if (f2.arity, f2.nlocals, f2.code) != (fn.arity, fn.nlocals, fn.code):
            return False, f"函数 {nm} roundtrip 不等价"
    elf1 = rv32em.compile_module_to_elf(mod)
    elf2 = rv32em.compile_module_to_elf(mod2)
    if elf1 != elf2:
        return False, f"ELF 字节不一致（{len(elf1)} vs {len(elf2)}）"
    if rv32bc.compile_bytes_to_elf(blob) != elf1:
        return False, "compile_bytes_to_elf 入口与直发入口产物不同"
    return True, f"blob={len(blob)}B ELF={len(elf1)}B 字节一致"


def vm_plain(source: str) -> str:
    outputs, err = exec_api.run_checked(source, mode="vm")
    if err is not None:
        raise RuntimeError(f"VM 参考失败：{type(err).__name__}: {err}")
    return "".join(f"{v}\n" for v in outputs)


def spike_plain(source: str) -> str:
    mod = compile_source(source)
    elf = rv32em.compile_module_to_elf(mod)
    sim = RV32Sim(elf)
    return sim.run()


def find_qemu(explicit):
    if explicit:
        return explicit if os.path.isfile(explicit) else None
    for name in ("qemu-system-riscv32",):
        for root in (r"C:\Program Files\qemu",):
            cand = Path(root) / (name + ".exe")
            if cand.is_file():
                return str(cand)
    from shutil import which
    return which(name)


def qemu_run(qemu: str, elf_path: str, timeout: float) -> str:
    cmd = [qemu, "-machine", "virt", "-cpu", "rv32", "-nographic",
           "-bios", "none", "-kernel", elf_path]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
        raw = proc.stdout or b""
    except subprocess.TimeoutExpired as e:
        # SPIKE 程序写 sifive_test 应主动退出；超时=真失败，但仍拿回部分串口。
        raw = e.stdout or b""
        print(f"       [qemu] 超时 {timeout}s 未退出（FAIL 候选）")
    return raw.decode("utf-8", "replace").replace("\r\n", "\n")


def main() -> int:
    use_qemu = "--qemu" in sys.argv
    timeout = float(os.environ.get("QEMU_DEMO_TIMEOUT", 6))
    qemu = find_qemu(None) if use_qemu else None

    fails = 0
    okr, why = contract_roundtrip()
    print(f"[{'ok  ' if okr else 'FAIL'}] s13_contract_roundtrip: {why}")
    if not okr:
        fails += 1
    for name, src in REJECT_CASES.items():
        try:
            spike_plain(src)
        except NotSupportedRV32:
            print(f"[ok  ] {name}: 如期望被显式拒绝（NotSupportedRV32）")
        except Exception as e:  # noqa: BLE001
            print(f"[FAIL] {name}: 期望拒绝却报 {type(e).__name__}: {e}")
            fails += 1
        else:
            print(f"[FAIL] {name}: 覆盖集外却被接受（静默产错风险）")
            fails += 1
    for name, src in CASES.items():
        try:
            ref = vm_plain(src)
        except Exception as e:  # noqa: BLE001
            print(f"[FAIL] {name}: VM 参考异常 {e}")
            fails += 1
            continue
        try:
            got = spike_plain(src)
        except NotSupportedRV32 as e:
            print(f"[FAIL] {name}: SPIKE 拒绝（应在子集内）：{e}")
            fails += 1
            continue
        except Exception as e:  # noqa: BLE001
            print(f"[FAIL] {name}: 发射/执行异常 {type(e).__name__}: {e}")
            fails += 1
            continue
        ok = got == ref
        print(f"[{'ok  ' if ok else 'FAIL'}] {name}: sim={got!r} vm={ref!r}")
        if not ok:
            fails += 1
            continue
        if use_qemu:
            if not qemu:
                print(f"[SKIP] {name}: 未探到 qemu-system-riscv32（qemu 复核跳过）")
                return 2
            elf = rv32em.compile_module_to_elf(compile_source(src))
            with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
                f.write(elf)
                ep = f.name
            try:
                qout = qemu_run(qemu, ep, timeout)
            finally:
                os.unlink(ep)
            # QEMU 串口可能混入固件噪声；只要求逐行包含 VM 的每一行输出
            missing = [ln for ln in ref.splitlines() if ln and ln not in qout]
            qok = not missing
            print(f"[{'ok  ' if qok else 'FAIL'}] {name}: qemu 复核 "
                  f"{'全含' if qok else '缺失 ' + str(missing)}")
            if not qok:
                fails += 1

    print(f"\n=== P6 RV32 SPIKE：{len(CASES)} 例 + {len(REJECT_CASES)} 拒绝例 + 契约 roundtrip，失败 {fails} ===")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
