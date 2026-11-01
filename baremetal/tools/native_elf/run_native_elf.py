#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阶段3-3 ④ P-a/P-b/P-c1 端到端门禁：Matha → Linux x86-64 静态 ELF64 → 实跑 → 与 mbc VM 逐字节对拍。

流程（每条覆盖集内用例）：
  1. compile_source 出 MModule（与 native.py 同一入口）；
  2. src.mbc.native_elf.compile_to_elf 纯 Python 位级发射静态非 PIE ELF64（无 C 工具链）；
  3. 宿主执行器实跑该 ELF 收集 stdout：
       - Linux（CI ubuntu / 本机原生）：直接 fork 执行；
       - Windows：经 `wsl.exe -d Ubuntu` 实跑同一 ELF；
  4. 与 `exec_api.run_checked(mode="vm")` 的宿主原生口径文本逐字节比对。

另有 REJECT_CASES（负向）：覆盖集外的源码必须被 NativeNotSupported 显式拒绝，
误接受（静默产错）才是失败。

执行器探测：本机无 WSL/Ubuntu 且非 Linux 时，用例只做发射/拒绝校验，运行期对拍如实
SKIP（退出码 2，不判失败）——与 RV32 SPIKE 缺 QEMU 的 SKIP 口径一致。

退出码：0=全部通过，1=任一失败，2=运行期对拍因缺执行器而跳过。
门禁隔离：本目录位于 baremetal/ 下，不被 repo_facts / dep_audit / kernel_purity 扫描。
"""
from __future__ import annotations

import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent          # d:/trae（baremetal/tools/native_elf 上溯三级）
sys.path.insert(0, str(ROOT))

from src.kernel import exec_api  # noqa: E402
from src.mbc import native_elf  # noqa: E402
from src.mbc.native_elf import NativeNotSupported  # noqa: E402

# ---- 覆盖集内用例（源码内嵌，避免向仓库语料/门禁增添任何 .matha 面） ----
CASES = {
    "s1_const_binop_output": """\
#1：[2 + 3 * 4]
#1：[10 - 4]
#1：[1 < 2]
#1：[not 0]
""",
    "s2_floordiv_mod": """\
#1：[7 // 2]
#1：[-7 // 2]
#1：[7 % 3]
#1：[-7 % 3]
#1：[0 - 1]
#1：[123456789 * 987654321]
""",
    "s3_if_then_else": """\
let x = 5
let y = if x > 3 then 10 else 20
#1：[y]
let a = 1
let b = if a > 100 then 1 else 999
#1：[b]
""",
    "s4_while_loop": """\
let i = 0
let s = 0
while i < 5 {
  s = s + i
  i = i + 1
}
#1：[s]
let k = 3
let f = 1
while k > 0 {
  f = f * k
  k = k - 1
}
#1：[f]
""",
    "s5_call_direct": """\
func add(a: Int, b: Int) -> Int = (a, b) => a + b
#1：[add(3, 4)]
#1：[add(10, -2)]
""",
    "s6_recursion": """\
func fact(n: Int) -> Int = (n) => if n <= 1 then 1 else n * fact(n - 1)
#1：[fact(6)]
#1：[fact(0)]
""",
    "s7_double_recursion": """\
func fib(n: Int) -> Int = (n) => if n < 2 then n else fib(n - 1) + fib(n - 2)
#1：[fib(10)]
""",
    "s8_mutual_recursion": """\
func isEven(n: Int) -> Int = (n) => if n == 0 then 1 else isOdd(n - 1)
func isOdd(n: Int) -> Int = (n) => if n == 0 then 0 else isEven(n - 1)
#1：[isEven(6)]
#1：[isOdd(6)]
""",
    "s9_local_let": """\
func g(x: Int) -> Int = (x) => {
  let y = x * 2
  y + 1
}
#1：[g(5)]
""",
    # ---- P-b：列表 + bump 堆 ----
    "s10_build_list_len": """\
let l = [10, 20, 30]
#1：[len(l)]
#1：[len([])]
""",
    "s11_index_pos_neg": """\
let l = [10, 20, 30]
#1：[l[1]]
#1：[l[-1]]
#1：[l[0]]
#1：[l[-3]]
""",
    "s12_bool_list_index": """\
let b = [1 < 2, 2 < 1, 3 < 4]
#1：[b[0]]
#1：[b[1]]
#1：[b[-1]]
""",
    "s13_while_index_sum": """\
let l = [5, 10, 15]
let i = 0
let s = 0
while i < len(l) {
  s = s + l[i]
  i = i + 1
}
#1：[s]
""",
    # ---- P-c1 N0：字符串（裸串输出 / len / 全局槽承载） ----
    "c1_str_output": """\
#1：["hi"]
let s = "Hello, Matha"
#1：[s]
""",
    "c2_str_len": """\
#1：[len("hi")]
#1：[len("")]
let t = "abcdef"
#1：[len(t)]
""",
}

# ---- 覆盖集外（负向）：必须被 NativeNotSupported 显式拒绝 ----
REJECT_CASES = {
    "r1_non_ascii": '#1：["\u4f60\u597d"]\n',
    "r2_closure": "f = (x) => x + 1\n#1：[f(2)]\n",
    "r3_for_list": "let t = 0\nfor x in [1, 2, 3] {\n  t = t + x\n}\n#1：[t]\n",
    "r4_undefined_global": "let a = b\n#1：[a]\n",
    "r5_arity_mismatch": "func ov(a: Int, b: Int) -> Int = (a, b) => a + b\n#1：[ov(1)]\n",
    "r6_float": "#1：[1.5]\n",
    # ---- P-b 越界集外：嵌套/混合/整表输出/切片/字典/int 下标 ----
    "r7_nested_list": "#1：[len([[1, 2], [3]])]\n",
    "r8_mixed_list": "#1：[len([1, 2 < 1])]\n",
    "r9_list_repr_output": "let l = [1, 2]\n#1：[l]\n",
    "r10_slice": "let l = [1, 2, 3]\n#1：[l[0:2]]\n",
    "r11_dict": "#1：[len({\"a\": 1})]\n",
    "r12_int_subscript": "#1：[5[0]]\n",
}

# ---- P-b 行为断言：运行期越界索引 → ELF exit_group(1)（镜像 VM 未捕获 IndexError） ----
OOB_CASES = {
    "b1_index_oob_high": "let l = [1, 2, 3]\n#1：[l[3]]\n",
    "b2_index_oob_neg": "let l = [1, 2, 3]\n#1：[l[-4]]\n",
    "b3_empty_index": "#1：[[][0]]\n",
}


def vm_plain(source: str) -> str:
    outputs, err = exec_api.run_checked(source, mode="vm")
    if err is not None:
        raise RuntimeError(f"VM 参考失败：{type(err).__name__}: {err}")
    return "".join(f"{v}\n" for v in outputs)


def _to_wsl_path(p: str) -> str:
    """Windows 绝对路径 → WSL /mnt/<drive>/... 路径。"""
    ap = Path(p).resolve()
    drive = ap.drive[0].lower()
    rest = str(ap)[len(ap.drive):].replace("\\", "/")
    return f"/mnt/{drive}{rest}"


def _exec_linux(elf: bytes, timeout: float) -> tuple[str, int]:
    with tempfile.NamedTemporaryFile(suffix=".elf", delete=False) as f:
        f.write(elf)
        ep = f.name
    try:
        os.chmod(ep, 0o755)
        proc = subprocess.run([ep], capture_output=True, timeout=timeout)
        return proc.stdout.decode("utf-8", "replace").replace("\r\n", "\n"), proc.returncode
    finally:
        os.unlink(ep)


def _exec_wsl(elf: bytes, timeout: float) -> tuple[str, int]:
    tmp = HERE / "_gate_tmp.elf"
    tmp.write_bytes(elf)
    wslp = _to_wsl_path(str(tmp))
    script = f"cp {wslp} /tmp/_native_gate.elf && chmod +x /tmp/_native_gate.elf && /tmp/_native_gate.elf"
    proc = subprocess.run(["wsl.exe", "-d", "Ubuntu", "-e", "bash", "-lc", script],
                          capture_output=True, timeout=timeout)
    tmp.unlink(missing_ok=True)
    return proc.stdout.decode("utf-8", "replace").replace("\r\n", "\n"), proc.returncode


class _Executor:
    def __init__(self) -> None:
        self.kind, self.available = self._probe()

    def _probe(self) -> tuple[str, bool]:
        if platform.system() == "Linux":
            return "linux", True
        if platform.system() == "Windows":
            try:
                r = subprocess.run(["wsl.exe", "-d", "Ubuntu", "-e", "bash", "-lc", "uname"],
                                   capture_output=True, timeout=90)
                if r.returncode == 0 and b"Linux" in (r.stdout or b""):
                    return "wsl", True
            except Exception:  # noqa: BLE001
                pass
        return "none", False

    def run(self, elf: bytes, timeout: float = 30.0) -> str:
        return self.run_rc(elf, timeout)[0]

    def run_rc(self, elf: bytes, timeout: float = 30.0) -> tuple[str, int]:
        if self.kind == "linux":
            return _exec_linux(elf, timeout)
        return _exec_wsl(elf, timeout)


def main() -> int:
    ex = _Executor()
    print(f"执行器探测：kind={ex.kind} available={ex.available}")

    fails = 0
    skipped_runtime = False
    for name, src in REJECT_CASES.items():
        try:
            native_elf.compile_to_elf(src)
        except NativeNotSupported:
            print(f"[ok  ] {name}: 如期望被显式拒绝（NativeNotSupported）")
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
            elf = native_elf.compile_to_elf(src)
        except NativeNotSupported as e:
            print(f"[FAIL] {name}: 后端拒绝（应在子集内）：{e}")
            fails += 1
            continue
        except Exception as e:  # noqa: BLE001
            print(f"[FAIL] {name}: 发射异常 {type(e).__name__}: {e}")
            fails += 1
            continue
        if not ex.available:
            print(f"[SKIP] {name}: 无执行器，仅校验发射成功（elf={len(elf)}B）")
            skipped_runtime = True
            continue
        try:
            got = ex.run(elf)
        except Exception as e:  # noqa: BLE001
            print(f"[FAIL] {name}: 实跑异常 {type(e).__name__}: {e}")
            fails += 1
            continue
        ok = got == ref
        print(f"[{'ok  ' if ok else 'FAIL'}] {name}: run={got!r} vm={ref!r}")
        if not ok:
            fails += 1

    # 越界行为断言：VM 侧必为未捕获 IndexError，且 ELF 侧 exit_group(1)
    for name, src in OOB_CASES.items():
        try:
            vm_plain(src)
            print(f"[FAIL] {name}: 期望 VM IndexError，却正常返回")
            fails += 1
            continue
        except Exception:  # noqa: BLE001
            pass
        try:
            elf = native_elf.compile_to_elf(src)
        except NativeNotSupported as e:
            print(f"[FAIL] {name}: 后端发射拒绝（越界应运行期处理）：{e}")
            fails += 1
            continue
        except Exception as e:  # noqa: BLE001
            print(f"[FAIL] {name}: 发射异常 {type(e).__name__}: {e}")
            fails += 1
            continue
        if not ex.available:
            print(f"[SKIP] {name}: 无执行器，仅校验发射成功")
            skipped_runtime = True
            continue
        got, rc = ex.run_rc(elf)
        ok = (rc == 1 and got == "")
        print(f"[{'ok  ' if ok else 'FAIL'}] {name}: rc={rc} run={got!r}（期望 rc=1 空输出）")
        if not ok:
            fails += 1

    tail = "（运行期对拍因缺执行器跳过）" if skipped_runtime else ""
    print(f"\n=== 阶段3-3 ④ native ELF P-a/P-b/P-c1：{len(CASES)} 正例 + {len(REJECT_CASES)} 拒绝例 "
          f"+ {len(OOB_CASES)} 越界行为例，失败 {fails}{tail} ===")
    if fails:
        return 1
    return 2 if skipped_runtime else 0


if __name__ == "__main__":
    raise SystemExit(main())
