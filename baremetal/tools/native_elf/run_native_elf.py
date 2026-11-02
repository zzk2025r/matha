#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阶段3-3 ④ P-a/P-b/P-c1/P-c2 端到端门禁：Matha → Linux x86-64 静态 ELF64 → 实跑 → 与 mbc VM 逐字节对拍。

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
    # ---- P-c1 N1：字符串组合（连接 / 比较 / 取子串） ----
    "c3_str_concat": """\
#1：["foo" + "bar"]
#1：["a" + "b" + "c"]
let g = "He" + "llo"
#1：[g]
#1：[len(g)]
#1：["" + "x"]
#1：["x" + ""]
""",
    "c4_str_compare": """\
#1：["a" == "a"]
#1：["a" != "b"]
#1：["abc" == "abd"]
#1：["" == ""]
#1：["a" == ""]
#1：["abc" != "abcd"]
""",
    "c5_str_index": """\
let s = "hello"
#1：[s[0]]
#1：[s[4]]
#1：[s[-1]]
#1：[s[-5]]
#1：[len(s[2])]
#1：[s[0] + s[4]]
""",
    # ---- P-c1 N2：同质 int/bool 列表整表 repr 输出 ----
    "c6_int_list_repr": """\
let l = [1, 2, 3]
#1：[l]
let m = [10, -3, 0, 7]
#1：[m]
let e = []
#1：[e]
""",
    "c7_bool_list_repr": """\
let b = [1 < 2, 2 < 1, 3 < 4]
#1：[b]
let l = [5, 10, 15]
#1：[l]
#1：[len(l)]
#1：[l[1]]
""",
    # ---- P-c1 N3：编译期折叠 str/异构整表 repr（发射器 Python str() 逐字节精确）----
    "c8_str_list_repr": """\
let l = ["a", "b"]
#1：[l]
#1：["x", "y"]
let m = ["only"]
#1：[m]
#1：[len(["a", "b", "c"])]
#1：[["a"][0]]
""",
    "c9_hetero_list_repr": """\
let l = [1, "a"]
#1：[l]
let m = [10, "x", "y"]
#1：[m]
""",
    "c10_int_list_runtime": """\
let x = 5
let l = [x, x + 1, x + 2]
#1：[l]
""",
    # ---- P-c2 S1：字面量/编译器折叠 float 输出（发射器 str() 折叠，逐字节精确）----
    "c11_float_folded": """\
#1：[1.5]
#1：[2.0]
#1：[-1.5]
#1：[1.5 + 2.5]
#1：[0.1 + 0.2]
#1：[1 + 1.5]
#1：[1e20]
#1：[1e-7]
#1：[3.25 * 2.0]
""",
    # ---- P-c2 S2：SSE2 比较（ucomisd+setcc，bool 可输出）----
    "c12_float_sse_compare": """\
#1：[1.5 < 2.5]
#1：[1.5 == 1.5]
#1：[1.5 != 1.5]
#1：[1 < 1.5]
#1：[2 > 1.5]
#1：[1.5 <= 1.5]
#1：[1.5 >= 2.0]
""",
    # ---- P-c2 S2：SSE2 算术（addsd/subsd/mulsd/divsd+cvtsi2sd 混型）经比较消费；neg；循环浮点 ----
    "c13_float_sse_arith": """\
#1：[1.5 + 1.5 == 3.0]
#1：[2.0 - 0.5 > 1.0]
#1：[0.5 * 4.0 >= 2.0]
#1：[2.5 / 0.5 == 5.0]
let q = 7 / 2
#1：[q == 3.5]
#1：[q * 2 == 7.0]
let x = 2.5
#1：[-x < 0]
let a = 0.0
while a < 3.0 {
  a = a + 1.0
}
#1：[a >= 3.0]
#1：[not 1.5]
""",
    # ---- P-c2 S2：列表折叠扩 float 元素（N3 机制延伸）----
    "c14_float_list_repr": """\
let l = [1.5, 2.0]
#1：[l]
#1：[len([1.5, 2.0, 3.0])]
""",
    # ---- P-c2 S3a：运行期精确十进制域 floatq → dtoa 叶例定点展开输出（全局/求和/neg/循环）----
    "c15_float_dtoa": """\
let x = 1.5
let y = 2.0
#1：[x]
#1：[y]
#1：[x + y]
#1：[-x]
let s = 0.0
while s < 1.5 {
  s = s + 0.25
}
#1：[s]
""",
    # ---- P-c2 S4a：float/floatq 真值判定（位域判零；越域 float 值亦可判，输出仍拒）----
    "c16_float_truthiness": """\
let x = 1.5
let z = 0.0
let nz = -z
#1：[not x]
#1：[not z]
#1：[not nz]
let s = 0.0
let t = 0
while not (s >= 1.5) {
  s = s + 0.5
  t = t + 1
}
#1：[t]
#1：[s]
let w = 0.1
#1：[not w]
""",
    # ---- P-c2 S4b：floatq 精确域取整除/求余（floor 向 -inf、零余数随除数号）----
    "c17_float_findiv": """\
let a = 7.5
let b = 2.0
#1：[a // b]
#1：[a % b]
let n = -7.5
#1：[n // b]
#1：[n % b]
let z = 0.0
let nz = -z
#1：[nz // b]
#1：[z % -2.5]
let i = 7
#1：[i // b]
let s = 0.0
while s < 3.0 {
  s = s + 0.75
}
#1：[s % 1.0]
""",
    # ---- P-c2 S3c-2：floatq 双档并存——深档 d≤7..10 新入域值逐字节=str(v)（浅档原能力零回归一并锁定）----
    "c18_float_deep_tier": """\
let x = 0.0009765625
let y = 0.0078125
#1：[x]
#1：[y]
#1：[-y]
let mix = 0.5 + 0.0009765625
#1：[mix]
let big = 900719.0
#1：[big]
let sh = 1048576.0
#1：[sh]
let s = 0.0
while s < 0.01 {
  s = s + 0.001953125
}
#1：[s]
""",
    # ---- P-c2 S3c-5d：最短往返 _dtoa 机器码——全局/真除/降级 float 逐字节==str()；
    #      含科学计数法（dec>16）与多位尾数、负号前置三条本轮修复回归锁定 ----
    "c19_float_shortest_repr": """\
let x = 0.1
#1：[x]
#1：[7 / 2]
let y = 0.5
#1：[y * 1.0]
let z = 1.1
#1：[z]
let n = 123.456
#1：[n]
let neg = -0.15
#1：[neg]
let w = 1e16
#1：[w]
let sci = 1.5e16
#1：[sci]
let od = 0.00048828125
#1：[od]
""",
    # ---- P-c2 S3c-6a：κ>63 小数十进制解禁（判据 P=E·B 改 E<<κ 128 位移位）——全局/降级/带符/科学计数法
    #      逐字节==str()；回归锁定 0.0001 类（旧面曾运行期 exit1 如实拒）----
    "c20_float_kappa_gt63": """\
let x = 0.0001
#1：[x]
let y = 0.00001
#1：[y]
let z = 1.5e-08
#1：[z]
let w = -0.000123
#1：[w]
let a = 0.0002
#1：[a]
let b = 2.5e-07
#1：[b]
""",
    # ---- P-c2 S3c-6b-1：|u|=19 表跨小数解禁（P10I 整数表扩至 10^19 单字，守卫 18→19）——
    #      2^-19 类精确二进制小数旧面 pow10_out 运行期 exit1，现逐字节==str()----
    "c21_float_table_span_19": """\
let x = 1.9073486328125e-06
#1：[x]
let y = 5.7220458984375e-06
#1：[y]
let z = 9.5367431640625e-06
#1：[z]
let w = -1.9073486328125e-06
#1：[w]
let a = 2.47955322265625e-05
#1：[a]
""",
    # ---- P-c2 S3c-6b-2-A：u≥0 深表跨解禁（P10I 整数表升双字步长、u≤38，EB≤64×10^u 双字→P≤128）——
    #      旧面 pow10_out 运行期 exit1（如 1e+20），现逐字节==str()----
    "c22_float_table_span_pos": """\
let x = 1e+20
#1：[x]
let y = 1e+22
#1：[y]
let z = 1e+23
#1：[z]
let a = 5.37493431315913e+20
#1：[a]
let b = 6.49646161317273e+20
#1：[b]
let c = -1e+20
#1：[c]
""",
}

# ---- 覆盖集外（负向）：必须被 NativeNotSupported 显式拒绝 ----
REJECT_CASES = {
    "r1_non_ascii": '#1：["\u4f60\u597d"]\n',
    "r2_closure": "f = (x) => x + 1\n#1：[f(2)]\n",
    "r3_for_list": "let t = 0\nfor x in [1, 2, 3] {\n  t = t + x\n}\n#1：[t]\n",
    "r4_undefined_global": "let a = b\n#1：[a]\n",
    "r5_arity_mismatch": "func ov(a: Int, b: Int) -> Int = (a, b) => a + b\n#1：[ov(1)]\n",
    # ---- P-c2 S3c-5d：r6/r15/r16 原「越域运行期 float 输出」编译期拒例，现由最短往返
    #      _dtoa 机器码解禁 → 逐字节输出正确，已迁至 CASES 正例 c19_float_shortest_repr。----
    # ---- P-c2 S4b 越界集外：越域 float 的 //与%（需 CPython 精确有理商语义，S4c+）----
    "r17_float_floordiv": "let x = 0.1\nlet y = 2.0\n#1：[x // y]\n",
    "r18_float_mod": "let x = 0.1\nlet y = 2.0\n#1：[x % y]\n",
    # ---- P-c2 S3c-2 旧「既约分母 2^11 超深档阈」静态拒例 r19（0.00048828125=2^-11 输出）：
    #      最短往返 _dtoa 接管 OUTPUT 后，该精确可表 double 属放行子集→已迁至正例 c19。----
    # ---- P-b 越界集外：嵌套/混合/整表输出/切片/字典/int 下标 ----
    "r7_nested_list": "#1：[len([[1, 2], [3]])]\n",
    "r8_mixed_list": "#1：[len([1, 2 < 1])]\n",
    "r9_str_list_runtime": 'let s = "a"\nlet l = [s]\n#1：[l]\n',  # 元素来自全局（非字面量）→ 不可折叠→拒
    "r10_slice": "let l = [1, 2, 3]\n#1：[l[0:2]]\n",
    "r11_dict": "#1：[len({\"a\": 1})]\n",
    "r12_int_subscript": "#1：[5[0]]\n",
    # ---- P-c1 N1 越界集外：str×数值连接（需 itoa）/ str 参与算术 ----
    "r13_str_mul": "#1：[\"a\" * 3]\n",
    "r14_str_plus_int": "#1：[\"n\" + 42]\n",
}

# ---- P-b 行为断言：运行期越界索引 → ELF exit_group(1)（镜像 VM 未捕获 IndexError） ----
OOB_CASES = {
    "b1_index_oob_high": "let l = [1, 2, 3]\n#1：[l[3]]\n",
    "b2_index_oob_neg": "let l = [1, 2, 3]\n#1：[l[-4]]\n",
    "b3_empty_index": "#1：[[][0]]\n",
    # ---- P-c1 N1：串取子串越界（与列表同口径 exit_group(1)） ----
    "b4_str_index_oob": "let s = \"abc\"\n#1：[s[5]]\n",
    "b5_str_index_oob_neg": "let s = \"abc\"\n#1：[s[-4]]\n",
}

# ---- P-c2 S3c-2 行为断言：`+ -` 封闭后的“档空洞”（d∈7..10 且 |v|≥深档阈）----
#   VM 侧能正常输出（该值精确可表），但落在双档并集的缝隙：选浅档⇒N=v×1e6 非整⇒会被
#   cvttsd2si 截断而静默印错。故发射器照常发射、运行期由整数性回检转 exit_group(1)：
#   不伪通过、也不静默印错（双档并存的必然代价，已登记 docs/spec/NATIVE_ELF_PC.md）。
HOLE_CASES = {
    "h1_floatq_tier_hole": "let a = 0.0078125\nlet b = 1048576.0\n#1：[a + b]\n",
    "h2_floatq_tier_hole_d10": "let a = 0.0009765625\nlet b = 2097152.0\n#1：[a + b]\n",
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

    # 档空洞行为断言：VM 正常输出，但 native 运行期必 rc=1 且零输出（拒静默印错）
    for name, src in HOLE_CASES.items():
        try:
            ref = vm_plain(src)
        except Exception as e:  # noqa: BLE001
            print(f"[FAIL] {name}: 期望 VM 正常输出，却报 {type(e).__name__}: {e}")
            fails += 1
            continue
        try:
            elf = native_elf.compile_to_elf(src)
        except NativeNotSupported as e:
            print(f"[FAIL] {name}: 后端发射拒绝（域内封闭值应运行期处理）：{e}")
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
        print(f"[{'ok  ' if ok else 'FAIL'}] {name}: vm={ref!r} rc={rc} run={got!r}（期望 rc=1 空输出，不静默印错）")
        if not ok:
            fails += 1

    tail = "（运行期对拍因缺执行器跳过）" if skipped_runtime else ""
    print(f"\n=== 阶段3-3 ④ native ELF P-a/P-b/P-c1/P-c2：{len(CASES)} 正例 + {len(REJECT_CASES)} 拒绝例 "
          f"+ {len(OOB_CASES)} 越界行为例 + {len(HOLE_CASES)} 档空洞如实失败例，失败 {fails}{tail} ===")
    if fails:
        return 1
    return 2 if skipped_runtime else 0


if __name__ == "__main__":
    raise SystemExit(main())
