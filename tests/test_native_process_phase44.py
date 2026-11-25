"""阶段 44 锁档：原生 OS 派生面（Matha 映像自己触达 kernel32）。

拍板口径（阶段 44）：Matha 与 Python 共存期不再调用任何 Python 模块触达 OS——
进程映像族（派生/等候/退出码/终止/关闭）只在 **原生 PE64 映像面** 为真实现，
宿主 hi 面与 MBC vm 面按「核心必须单线程确定、且不驱动外部进程」红线 **显式拒绝**
（同文案，非静默降级），链面（boot 五文件）无该名 → 未定义变量。

覆盖：
- 44a 原生映像面 e2e：真 OS 子进程派生/等候/取码/终止/关闭，含无定义读数一律
  null（不哨兵冒充）、坏形状实参、空命令行 -1、槽表满槽诚实失败。
- 44b CLI `matha 原生构建` 命令位 e2e（真产物 PE64：无导入表）+ `build` 假广告清算。
- 44c hi/vm 同文案显式拒绝 + 链面名集边界（静态锁 + boot 面真跑）。
- 44d 宿主桥载体进程回收（43-④ 退役）：内核判定落地后桥补真终止、判定被拒不伤进程、
  回收粒度为「单元名一格」。
- 44e 静态结构锁：三面名集/arity 一致、native_process 运行路径零 Python 模块。
- 44f CIM 取证：派生子的 OS 父映像就是构建产物本身（进程树中无 python.exe）。

口径来源见 src/mbc/native_process.py 模块注（句柄生命周期、32 槽、null 读数、
TerminateProcess 退出码 1、不建作业对象）。
"""
import contextlib
import io
import json
import struct
import subprocess
import sys
import time
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from src import interp as interp_mod  # noqa: E402
from src.ast_nodes import Program  # noqa: E402
from src.interp import MathaUndefinedNameError, interpret  # noqa: E402
from src.kernel import exec_api  # noqa: E402
from src.mbc import native_process as np_mod  # noqa: E402
from src.mbc.compiler import Compiler  # noqa: E402
from src.mbc.native import NativeNotSupported, compile_to_exe  # noqa: E402
from src.mbc.vm import VM  # noqa: E402
from src.os_runtime import OsRuntime  # noqa: E402
from src.parser import parse as py_parse  # noqa: E402

_BOOT_FILES = ["matha/lexer.matha", "matha/stdlib.matha", "matha/parser.matha",
               "matha/runtime/matha_runtime.matha", "matha/interp_matha.matha"]

IMAGE_NAMES = ("派生映像", "等候映像", "映像退出码", "终止映像", "关闭映像")

_REFUSAL = ("需原生后端：进程映像族由 Matha 原生映像经 kernel32 直接派生与回收，"
            "宿主/VM 面属核心主线，按「核心必须单线程确定、且不驱动外部进程」"
            "红线不提供该能力（显式拒绝，非静默降级）。请改用原生后端运行"
            "（src.mbc.native.compile_to_exe 产物）。")

# 静默长命子进程：ping 无 stdout，cmd.exe 外壳 12 秒内自己收尾（终止只收外壳）。
_LONG = "cmd.exe /c ping 127.0.0.1 -n 12 > nul"


# ============================================================
# 助手
# ============================================================

def _strip_bom(src: str) -> str:
    return src.lstrip("\ufeff") if src and src[0] == "\ufeff" else src


def _run_native(src: str, tmp_path: Path, name: str = "p44.exe", timeout=180):
    """把 Matha 源发射成原生映像并真跑，返回 (stdout 行, returncode)。"""
    exe = tmp_path / name
    exe.write_bytes(compile_to_exe(src))
    r = subprocess.run([str(exe)], capture_output=True, timeout=timeout)
    out = r.stdout.decode("utf-8", "replace").splitlines()
    return [ln.strip() for ln in out if ln.strip()], r.returncode


def _pe_facts(blob: bytes) -> dict:
    """PE 头取证走 e_lfanew 相对偏移（固定偏移 4 处不是 PE 签名）。"""
    off = struct.unpack_from("<I", blob, 0x3C)[0]
    nsec = struct.unpack_from("<H", blob, off + 6)[0]
    optsize = struct.unpack_from("<H", blob, off + 20)[0]
    opt = off + 24
    magic = struct.unpack_from("<H", blob, opt)[0]
    dd = opt + (112 if magic == 0x20B else 96)
    imp_rva, imp_size = struct.unpack_from("<II", blob, dd)
    sec = opt + optsize
    return {
        "sig": blob[off:off + 4] == b"PE\x00\x00",
        "machine": struct.unpack_from("<H", blob, off + 4)[0],
        "opt_magic": magic,
        "sections": [blob[sec + i * 40: sec + i * 40 + 8].rstrip(b"\0").decode()
                     for i in range(nsec)],
        "import_rva": imp_rva,
        "import_size": imp_size,
    }


def _cli(*args: str, timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "src.matha_main", *args],
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          cwd=str(_ROOT), timeout=timeout)


def _hi(src: str):
    try:
        return ("ok", [str(x) for x in interpret(src)[0]])
    except Exception as e:  # noqa: BLE001
        return ("err", f"{type(e).__name__}: {e}")


def _vm(src: str):
    try:
        outs, err = exec_api.run_checked(src)
        if err is not None:
            raise err if isinstance(err, BaseException) else RuntimeError(str(err))
        return ("ok", [str(x) for x in outs])
    except Exception as e:  # noqa: BLE001
        return ("err", f"{type(e).__name__}: {e}")


def _call_face(name: str) -> str:
    """映像族调用源：等候映像 二参柯里化，其余单参。"""
    if name == "等候映像":
        return "let f = 等候映像(1)\n输出(f(10))\n"
    return f"输出({name}(1))\n"


def _live_carrier(rt: OsRuntime, name: str):
    """登记一个长命外部单元并跑出一真 OS 载体进程，返回 Popen。"""
    desc = rt.register_external(name, ["cmd.exe", "/c", "ping", "127.0.0.1", "-n", "12"],
                                常驻=True, 重启预算=1)
    rt.load_descriptor(desc)
    rt.start(name)
    rt.tick(1)
    return rt._handles[name]["proc"]


def _os_alive(proc) -> bool:
    return proc is not None and proc.poll() is None


# ============================================================
# 44a 原生映像面 e2e（真 OS 进程，运行路径无 Python）
# ============================================================

def test_44a_spawn_wait_exitcode_close_roundtrip(tmp_path):
    """派生→等候→取码→关闭 全链读数（cmd.exe /c exit 7 的退出码就是 7）。"""
    src = (f'let a = 派生映像("cmd.exe /c exit 7")\n'
           "输出(a > 0)\n"
           "输出(等候映像(a)(5000))\n"
           "输出(映像退出码(a))\n"
           "输出(关闭映像(a))\n")
    out, rc = _run_native(src, tmp_path)
    assert rc == 0, out
    assert out == ["True", "True", "7", "True"], out


def test_44a_kill_running_image_then_code_is_one(tmp_path):
    """仍在跑 → 等候(200) 假 + 退出码 null；终止后退出码恰为 1（对齐 CPython）。"""
    src = (f'let b = 派生映像("{_LONG}")\n'
           "输出(b > 0)\n"
           "输出(等候映像(b)(200))\n"
           "输出(映像退出码(b))\n"
           "输出(终止映像(b))\n"
           "输出(等候映像(b)(5000))\n"
           "输出(映像退出码(b))\n"
           "输出(关闭映像(b))\n")
    out, rc = _run_native(src, tmp_path, "p44_kill.exe")
    assert rc == 0, out
    assert out == ["True", "False", "None", "True", "True", "1", "True"], out


def test_44a_kill_after_exit_is_honest_false(tmp_path):
    """已退出的映像没有「可终止」这件事发生 → 假（不谎报成功）。"""
    src = ('let a = 派生映像("cmd.exe /c exit 3")\n'
           "输出(等候映像(a)(5000))\n"
           "输出(终止映像(a))\n"
           "输出(关闭映像(a))\n")
    out, rc = _run_native(src, tmp_path, "p44_killed.exe")
    assert rc == 0, out
    assert out == ["True", "False", "True"], out


def test_44a_close_twice_second_is_null(tmp_path):
    """句柄生命周期归调用方：关闭一次释放槽位，再关闭即无记录 → null。"""
    src = ('let a = 派生映像("cmd.exe /c exit 0")\n'
           "输出(等候映像(a)(5000))\n"
           "输出(关闭映像(a))\n"
           "输出(关闭映像(a))\n")
    out, rc = _run_native(src, tmp_path, "p44_twice.exe")
    assert rc == 0, out
    assert out == ["True", "True", "None"], out


def test_44a_exit_code_after_close_is_null(tmp_path):
    """槽位释放后读数无定义 → null（不用上一次缓存值冒充可查）。"""
    src = ('let a = 派生映像("cmd.exe /c exit 9")\n'
           "输出(等候映像(a)(5000))\n"
           "输出(映像退出码(a))\n"
           "输出(关闭映像(a))\n"
           "输出(映像退出码(a))\n")
    out, rc = _run_native(src, tmp_path, "p44_afterclose.exe")
    assert rc == 0, out
    assert out == ["True", "9", "True", "None"], out


def test_44a_undefined_readouts_are_null_not_sentinel(tmp_path):
    """坏形状实参（非整数/非正 pid/无记录）一律 null，不产 0 或 999 哨兵读数。"""
    src = ('输出(等候映像("字符串")(10))\n'
           "输出(映像退出码([1]))\n"
           "输出(终止映像(null))\n"
           "输出(关闭映像(0))\n"
           "输出(映像退出码(999999))\n")
    out, rc = _run_native(src, tmp_path, "p44_badargs.exe")
    assert rc == 0, out
    assert out == ["None"] * 5, out


def test_44a_spawn_bad_command_line_is_minus_one(tmp_path):
    """派生失败的形态是 -1（不是 null）：空串、非字符串、不存在的可执行名。"""
    src = ('输出(派生映像(""))\n'
           "输出(派生映像(123))\n"
           "输出(派生映像([1]))\n"
           '输出(派生映像("__no_such_image__.exe"))\n')
    out, rc = _run_native(src, tmp_path, "p44_badspawn.exe")
    assert rc == 0, out
    assert out == ["-1", "-1", "-1", "-1"], out


def test_44a_slot_table_full_honest_failure(tmp_path):
    """满槽（32 槽）诚实返回 -1，不覆盖旧槽——前 32 真、后两条假。"""
    src = "".join('输出(派生映像("cmd.exe /c exit 0") > 0)\n' for _ in range(34))
    out, rc = _run_native(src, tmp_path, "p44_slots.exe", timeout=300)
    assert rc == 0, out
    assert out == ["True"] * np_mod._SLOTS + ["False"] * 2, out


def test_44a_curried_wait_is_partial_application(tmp_path):
    """等候映像 是二参柯里化内建：先偏应用得可调用，再喂时限。"""
    src = ('let a = 派生映像("cmd.exe /c exit 5")\n'
           "let w = 等候映像(a)\n"
           "输出(w(5000))\n"
           "输出(映像退出码(a))\n"
           "输出(关闭映像(a))\n")
    out, rc = _run_native(src, tmp_path, "p44_curry.exe")
    assert rc == 0, out
    assert out == ["True", "5", "True"], out


def test_44a_canonical_full_readout_sequence(tmp_path):
    """16 形态一次性正典读数（派生/等候/取码/终止/关闭 + 五坏形状 + 空命令行）。"""
    src = (f'let a = 派生映像("cmd.exe /c exit 7")\n'
           "输出(a > 0)\n"
           "输出(等候映像(a)(5000))\n"
           "输出(映像退出码(a))\n"
           "输出(关闭映像(a))\n"
           f'let b = 派生映像("{_LONG}")\n'
           "输出(b > 0)\n"
           "输出(等候映像(b)(200))\n"
           "输出(映像退出码(b))\n"
           "输出(终止映像(b))\n"
           "输出(等候映像(b)(5000))\n"
           "输出(映像退出码(b))\n"
           "输出(关闭映像(b))\n"
           '输出(等候映像("字符串")(10))\n'
           "输出(映像退出码([1]))\n"
           "输出(终止映像(null))\n"
           "输出(关闭映像(0))\n"
           '输出(派生映像(""))\n')
    out, rc = _run_native(src, tmp_path, "p44_canon.exe")
    assert rc == 0, out
    assert out == ["True", "True", "7", "True",
                   "True", "False", "None", "True", "True", "1", "True",
                   "None", "None", "None", "None", "-1"], out


# ============================================================
# 44b CLI 原生构建 命令位 + build 假广告清算
# ============================================================

_SRC = 'let a = 派生映像("cmd.exe /c exit 11")\n输出(等候映像(a)(5000))\n' \
       "输出(映像退出码(a))\n输出(关闭映像(a))\n"


def test_44b_cli_native_build_emits_importless_pe64(tmp_path):
    """走产品入口 `matha 原生构建` → 真 PE64（无导入表）且产物可跑。"""
    src = tmp_path / "app.matha.txt"
    src.write_text(_SRC, encoding="utf-8")
    exe = tmp_path / "app.exe"
    r = _cli("原生构建", str(src), "-o", str(exe))
    txt = r.stdout.decode("utf-8", "replace")
    assert r.returncode == 0, txt
    assert "原生构建成功" in txt, txt
    assert "无导入表" in txt, txt
    blob = exe.read_bytes()
    pe = _pe_facts(blob)
    assert blob[:2] == b"MZ", pe
    assert pe["sig"] and pe["machine"] == 0x8664 and pe["opt_magic"] == 0x20B, pe
    assert pe["import_rva"] == 0 and pe["import_size"] == 0, \
        "原生映像必须无导入表（运行期由 PEB 走表解析 kernel32）"
    assert pe["sections"] == [".text", ".bss", ".data"], pe
    # 产物字节与直调库路径逐字一致（CLI 不引入额外不确定性）
    assert blob == compile_to_exe(_SRC)
    out, rc = _run_native(_SRC, tmp_path, "again.exe")
    assert (rc, out) == (0, ["True", "11", "True"]), out


def test_44b_cli_native_build_default_output_path(tmp_path):
    """不给 -o 时取源名换 .exe 后缀（与 src.mbc.native.main 同口径）。"""
    src = tmp_path / "dflt.matha.txt"
    src.write_text('输出(1 + 1)\n', encoding="utf-8")
    r = _cli("原生构建", str(src))
    assert r.returncode == 0, r.stdout.decode("utf-8", "replace")
    out = src.with_suffix(".exe")
    assert out.is_file() and out.read_bytes()[:2] == b"MZ"


def test_44b_cli_native_build_aliases(tmp_path):
    """native-build / exe 两个别名同命令位。"""
    src = tmp_path / "alias.matha.txt"
    src.write_text('输出(7)\n', encoding="utf-8")
    for alias in ("native-build", "exe"):
        exe = tmp_path / f"{alias}.exe"
        r = _cli(alias, str(src), "-o", str(exe))
        assert r.returncode == 0, (alias, r.stdout.decode("utf-8", "replace"))
        assert exe.read_bytes()[:2] == b"MZ"


def test_44b_cli_native_build_missing_source_rc2(tmp_path):
    """源不可读 → rc 2 且 stderr 报「源不可读」（不伪造「已构建」）。"""
    r = _cli("原生构建", str(tmp_path / "nope.matha.txt"),
             "-o", str(tmp_path / "nope.exe"))
    txt = r.stdout.decode("utf-8", "replace")
    assert r.returncode == 2, txt
    assert "原生构建失败" in txt and "源不可读" in txt, txt


def test_44b_cli_native_build_unsupported_source_rc1_no_artifact(tmp_path):
    """超出原生子集 → NativeNotSupported 如实非零退出，且不留半成品产物。"""
    src = tmp_path / "unsupp.matha.txt"
    src.write_text("输出(1 is 1)\n", encoding="utf-8")      # 'is' 无原生发射
    exe = tmp_path / "unsupp.exe"
    r = _cli("原生构建", str(src), "-o", str(exe))
    txt = r.stdout.decode("utf-8", "replace")
    assert r.returncode == 1, txt
    assert "超出原生子集" in txt, txt
    assert not exe.exists(), "发射失败不得留下产物"
    with pytest.raises(NativeNotSupported):            # 库面同判，非仅 CLI 包装
        compile_to_exe("输出(1 is 1)\n")


def test_44b_cli_build_help_no_longer_advertises_standalone_exe():
    """假广告清算：`build` 只声称 M3V 字节码工件，机器码归 `原生构建`。"""
    text = (_ROOT / "src" / "matha_main.py").read_text(encoding="utf-8")
    assert 'add_parser("build", help="构建 M3V 字节码工件（MBC1，须 Matha 载体执行）"' in text
    assert "构建独立可执行文件" not in text.split('"""')[0]      # 模块注不得残留旧声称
    seg = text[text.index("def _cmd_build("):text.index("def _cmd_native_build(")]
    assert "emit_exe" not in seg and "build_exe" not in seg, \
        "build 命令位不得再走机器码路径"
    assert "原生构建" in text[text.index("def _cmd_build("):], \
        "build 的分工注须指向 原生构建"


# ============================================================
# 44c hi/vm 显式拒绝（同文案）+ 链面名集边界
# ============================================================

@pytest.mark.parametrize("name", IMAGE_NAMES)
def test_44c_host_and_vm_refuse_with_identical_text(name):
    """五名在 hi/vm 两面同名同消息显式拒绝——不静默降级、不返回假读数。"""
    src = _call_face(name)
    hi, vm = _hi(src), _vm(src)
    assert hi[0] == "err" and vm[0] == "err", (hi, vm)
    assert hi[1].startswith("MathaRuntimeError: "), hi
    assert hi == vm, f"两面消息须逐字同判:\n hi={hi[1]}\n vm={vm[1]}"
    assert name in hi[1] and hi[1].endswith(_REFUSAL), hi


def test_44c_refusal_names_the_native_route():
    """拒绝文案须给出可执行的下一步（原生后端产物名），而非只说「不支持」。"""
    msg = _hi(_call_face("派生映像"))[1]
    for token in ("需原生后端", "kernel32", "显式拒绝，非静默降级",
                  "src.mbc.native.compile_to_exe"):
        assert token in msg, (token, msg)


def test_44c_registration_sites_carry_the_same_refusal():
    """两面各自独立造文案（无共享常量），故逐字对拍——漂移即红。"""
    assert interp_mod.PROCESS_IMAGE_BUILTINS == IMAGE_NAMES
    sites = [(_ROOT / "src" / "interp.py").read_text(encoding="utf-8"),
             (_ROOT / "src" / "mbc" / "vm.py").read_text(encoding="utf-8")]
    for text in sites:
        assert "需原生后端：进程映像族由 Matha 原生映像经 kernel32 直接派生与" in text
    assert len(sites) == 2


def test_44c_no_matha_source_names_the_image_family():
    """链面边界：任何 .matha 语料都未定义/引用映像族名 → boot 面只能是未定义变量。

    刻意不扩 注册内建(空环境) 名集（41d-1 同族口径）：动 boot 链可用名集会扰动
    Track B 语料快照与 stage2↔stage3 定点，表差本身登记不修。
    """
    dirs = ["matha", "examples", "golden_tests", "tests", "stdlib"]
    hits = []
    for d in dirs:
        for p in (_ROOT / d).rglob("*.matha"):
            txt = p.read_text(encoding="utf-8", errors="replace")
            hits += [f"{p}:{n}" for n in IMAGE_NAMES if n in txt]
    assert hits == [], f"链面不得出现映像族名: {hits}"


def test_44c_boot_face_reports_undefined_name():
    """boot 链面真跑：调用映像族 → 未定义变量（诚实缺名，非假读数）。"""
    comp = Compiler()
    decls = []
    for rel in _BOOT_FILES:
        decls.extend(py_parse(_strip_bom(
            (_ROOT / rel).read_text(encoding="utf-8"))).decls)
    comp.compile_program(Program(decls=decls))
    vm = VM(comp.mod)
    with contextlib.redirect_stdout(io.StringIO()):
        vm.run()
    src = '输出(派生映像("cmd.exe /c exit 0"))\n'
    env = vm.call("注册内建", vm.call("空环境"))
    prog = vm.call("parse", vm.call("扫描", src, 0, 1, 1, []))
    with pytest.raises(MathaUndefinedNameError) as ei:
        with contextlib.redirect_stdout(io.StringIO()):
            vm.call("执行语句", prog, env)
    assert "未定义变量" in str(ei.value) and "派生映像" in str(ei.value), str(ei.value)


# ============================================================
# 44d 宿主桥载体进程回收（43-④ 退役）
# ============================================================

def test_44d_stop_terminates_the_carrier_process():
    """桥面 停止 真终止 OS 载体进程并交还句柄格（旧代码只 terminate 不还格）。"""
    rt = OsRuntime()
    proc = _live_carrier(rt, "回收停")
    assert _os_alive(proc), "载体应已派生为真 OS 进程"
    r = rt.stop("回收停")
    time.sleep(0.3)
    assert r["结果"] == "已停止", r
    assert proc.poll() is not None, "停止后载体进程必须已不存在"
    assert "proc" not in (rt._handles.get("回收停") or {}), "句柄格须交还"
    assert rt._终止载体("回收停") is False, "无载体即幂等假"


def test_44d_refused_lifecycle_calls_do_not_touch_the_process():
    """被拒的 停止/卸载 不得伤进程；随后被 接受 的 卸载 才回收。"""
    rt = OsRuntime()
    proc = _live_carrier(rt, "活拒")
    assert rt.unload("活拒")["原因"] == "须先停止"
    time.sleep(0.3)
    assert _os_alive(proc), "拒绝的卸载不得杀载体"
    assert rt.stop("活拒")["结果"] == "已停止"       # 簿记仍在运行 → 这次被接受
    time.sleep(0.3)
    assert proc.poll() is not None
    assert rt.stop("活拒")["结果"] == "拒绝", "重复停止被拒且无副作用"


def test_44d_refused_stop_after_kernel_side_stop_is_followed_by_unload():
    """内核侧直接 停止（绕过桥）→ 桥 停止 被拒且不杀；卸载 落地才杀。"""
    rt = OsRuntime()
    proc = _live_carrier(rt, "绕桥")
    rt._call("停止", rt._k, "绕桥")                  # 只改簿记，OS 仍活
    assert _os_alive(proc)
    assert rt.stop("绕桥")["结果"] == "拒绝"
    assert _os_alive(proc), "被拒的停止不得杀载体"
    assert rt.unload("绕桥")["结果"] == "已卸载"
    time.sleep(0.3)
    assert proc.poll() is not None, "卸载落地后载体必须回收"


def test_44d_restart_reaps_stale_carrier_on_kernel_reclaim_event():
    """内核 收旧进程 改判时，桥补那一步真终止（否则旧载体继续跑）。"""
    rt = OsRuntime()
    proc = _live_carrier(rt, "收旧")
    rt._call("停止", rt._k, "收旧")                  # 簿记已停，OS 仍活
    assert rt.start("收旧")["结果"] == "运行中"
    assert ["收旧进程", "收旧", [1]] in rt._k[5], rt._k[5]
    time.sleep(0.3)
    assert proc.poll() is not None, "收旧进程 事件后旧载体必须已终止"
    assert sum(1 for row in rt.process_list()
               if row[1] == "收旧" and row[3] == "就绪") == 1


def test_44d_stop_process_reaps_only_when_last_ready_row_is_gone():
    """回收粒度是「单元」：同单元多条就绪共用一格，最后一条停掉才杀进程。"""
    rt = OsRuntime()
    proc = _live_carrier(rt, "双跑")
    assert rt.start_process("双跑", "主")["结果"] == "已启动"
    pids = [row[0] for row in rt.process_list()
            if row[1] == "双跑" and row[3] == "就绪"]
    assert len(pids) == 2, pids
    assert rt.stop_process(pids[0])["结果"] == "已停止"
    assert _os_alive(proc), "仍有就绪进程共用该格，不得早收"
    assert rt.stop_process(pids[1])["结果"] == "已停止"
    time.sleep(0.3)
    assert proc.poll() is not None, "最后一条就绪停掉后必须回收"
    assert "proc" not in (rt._handles.get("双跑") or {})


def test_44d_reap_without_carrier_is_false_and_unknown_pid_honest():
    """无载体幂等假 / 未装载名 / 不存在 pid 全部诚实拒绝，不抛不吞。"""
    rt = OsRuntime()
    assert rt._终止载体("不存在") is False
    assert rt.stop("不存在")["结果"] == "拒绝"
    r = rt.stop_process(999999)
    assert r["结果"] == "拒绝" and r["原因"] == "进程不存在", r


# ============================================================
# 44e 静态结构锁
# ============================================================

def test_44e_native_backend_registers_all_five_names():
    """原生面注册面齐名：NATIVE_BUILTINS / arity / emitter 三处一致。"""
    from src.mbc import native
    for name in IMAGE_NAMES:
        assert name in native.NATIVE_BUILTINS, name
        assert name in native._BUILTIN_ARITY, name
        assert name in native._BUILTIN_EMITTERS, name
    assert native._BUILTIN_ARITY["等候映像"] == 2
    assert all(native._BUILTIN_ARITY[n] == 1 for n in IMAGE_NAMES if n != "等候映像")


def test_44e_curried_shape_lands_outside_the_compiler_fold_table():
    """柯里化落点：native 走 `_BUILTIN_ARITY`，hi/vm 走内建安装期 curry 包装。

    编译器 `_CURRIED_BUILTIN_ARITY`（get/append/slice/range 四名的编译期折叠表，
    与 matha/compiler_matha.matha 的 `_预扫元数` 逐项同值、且被 stage2↔stage3
    定点锁保护）刻意**不含**映像族名——加名即扰动自举编译器镜像与 Track B 口径。
    """
    from src.mbc import native
    from src.mbc.compiler import _CURRIED_BUILTIN_ARITY
    assert native._BUILTIN_ARITY["等候映像"] == 2
    assert not [n for n in IMAGE_NAMES if n in _CURRIED_BUILTIN_ARITY], \
        "映像族不得进编译器折叠表（boot 镜像定点面）"
    # 偏应用本身不触达 OS，故不触发拒绝——只有真正调用才显式拒绝
    partial = "let f = 等候映像(1)\n输出(42)\n"
    assert _hi(partial) == ("ok", ["42"]), _hi(partial)
    assert _vm(partial) == ("ok", ["42"]), _vm(partial)
    assert _hi(_call_face("等候映像"))[0] == "err"
    assert _vm(_call_face("等候映像"))[0] == "err"


def test_44e_runtime_path_imports_no_python_os_modules():
    """发射器运行路径不得引入任何 Python OS 模块——只 struct 排布字节。"""
    text = (_ROOT / "src" / "mbc" / "native_process.py").read_text(encoding="utf-8")
    body = text.split('"""', 2)[2]                     # 去模块注（注内引用名不算导入）
    for mod in ("subprocess", "ctypes", "os.", "winreg", "multiprocessing"):
        assert mod not in body, mod
    assert "import struct" in body
    assert sorted({ln.split()[1] for ln in body.splitlines()
                   if ln.startswith("import ")}) == ["struct"]


def test_44e_api_set_is_kernel32_only_with_documented_policy():
    """六个 API 全 kernel32 导出；槽表 32 槽、终止码 1、收殓上限 5000ms。"""
    assert [a for _s, _n, a in np_mod._APIS] == [
        "CreateProcessW", "WaitForSingleObject", "GetExitCodeProcess",
        "TerminateProcess", "CloseHandle", "MultiByteToWideChar"]
    assert np_mod._SLOTS == 32 and np_mod._KILL_CODE == 1
    assert np_mod._REAP_MS == 5000 and np_mod._STILL_ACTIVE == 259
    assert np_mod._SLOT == 40 and np_mod._CMD_MAX == 2048


def test_44e_built_image_carries_no_python_marker(tmp_path):
    """产物字节里无 python/Cpython 标记（自证：不链 CPython 也不嵌其符号名）。"""
    blob = compile_to_exe(_SRC)
    low = blob.lower()
    for marker in (b"python", b"cpython", b"python3"):
        assert marker not in low, marker
    assert b"CreateProcessW" in blob, "导出名以 ANSI 落在 .data 供 GetProcAddress"


# ============================================================
# 44f CIM 父进程取证
# ============================================================

def _cim_rows(pids):
    filt = " or ".join(f"ProcessId={p}" for p in pids)
    ps = (f"Get-CimInstance Win32_Process -Filter \"{filt}\" | "
          "Select-Object ProcessId,ParentProcessId,Name | ConvertTo-Json -Compress")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
    txt = r.stdout.decode("utf-8", "replace").strip()
    if not txt:
        return []
    rows = json.loads(txt)
    return rows if isinstance(rows, list) else [rows]


def test_44f_derived_child_is_parented_by_the_native_image(tmp_path):
    """派生子的 OS 父映像就是构建产物本身——进程树中没有 python.exe 中转。"""
    src = (f'let 子 = 派生映像("{_LONG}")\n'
           "输出(子)\n"
           "输出(等候映像(子)(4000))\n"
           "输出(终止映像(子))\n"
           "输出(关闭映像(子))\n")
    exe = tmp_path / "p44_parent.exe"
    exe.write_bytes(compile_to_exe(src))
    p = subprocess.Popen([str(exe)], stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, errors="replace",
                         cwd=str(_ROOT))
    try:
        # 逐行读首行拿子 pid（`for line in p.stdout` 会预读整块，后续 read 只剩空串）
        首行 = p.stdout.readline().strip()
        assert 首行.isdigit(), f"派生映像未给出子 pid: {首行!r}"
        子pid = int(首行)
        assert 子pid > 0, f"派生映像未给出子 pid: {首行!r}"
        rows = {r["ProcessId"]: r for r in _cim_rows([子pid, p.pid])}
        assert 子pid in rows and p.pid in rows, f"CIM 取证缺行: {rows}"
        assert rows[子pid]["ParentProcessId"] == p.pid, rows[子pid]
        assert rows[子pid]["Name"].lower() == "cmd.exe", rows[子pid]
        assert rows[p.pid]["Name"].lower() == exe.name.lower(), rows[p.pid]
        assert rows[p.pid]["Name"].lower() not in ("python.exe", "pythonw.exe")
        rest = p.stdout.read()
        rc = p.wait(timeout=120)
    finally:
        if p.poll() is None:
            p.kill()
            p.wait(timeout=60)
    assert rc == 0, rest
    assert [ln.strip() for ln in rest.splitlines() if ln.strip()] == [
        "False", "True", "True"], rest
