# -*- coding: utf-8 -*-
"""原生后端设计契约：机器码 exe 不承载懒加载领域/插件符号，且绝不静默造值。

背景（任务B）：领域插件（如 `机械设计` 的 `公差系数_IT10`）只在宿主进程里
经 `src.plugin_api` 懒加载 `import` 进来。`mbc.native` 产出的是一枚**独立**
可执行文件，运行时没有 Python 宿主、没有那张全局符号表，因此这类符号在
native 侧本质上不存在。

这不是缺陷，而是设计边界。但要防的是它退化成 NI-001/002 那一类「静默错值」：
未定义的名字被读成裸 0 打到 stdout，用户以为算出了结果。本测试锁定 native
的真实可观察行为——遇到未加载符号时**要么编译期抛 NativeNotSupported，要么
运行期以非零码干净退出且不产出任何值**，绝不允许 stdout 出现被伪造的数值。
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.mbc.native import compile_to_exe, NativeNotSupported


def _toolchain_available() -> bool:
    """纯算术程序能编能跑 → 工具链可用；否则本机缺 nasm/link → 跳过。"""
    try:
        exe = Path(tempfile.gettempdir()) / "matha_native_probe.exe"
        exe.write_bytes(compile_to_exe("#1：[6*7]"))
        r = subprocess.run([str(exe)], capture_output=True, timeout=30)
        return r.returncode == 0 and r.stdout.strip() == b"42"
    except (NativeNotSupported, OSError, subprocess.SubprocessError):
        return False


pytestmark = pytest.mark.skipif(
    not _toolchain_available(),
    reason="原生工具链不可用（缺 nasm/link）——本契约仅约束真实机器码路径",
)


def _run_native(src: str, tag: str) -> tuple[str | None, int, str, str]:
    """返回 (编译期异常名或 None, 退出码, stdout, stderr)。"""
    exe = Path(tempfile.gettempdir()) / f"matha_native_{tag}.exe"
    try:
        exe.write_bytes(compile_to_exe(src))
    except NativeNotSupported as e:
        return ("NativeNotSupported", 0, "", str(e))
    except Exception as e:  # noqa: BLE001
        return (type(e).__name__, 0, "", str(e))
    r = subprocess.run([str(exe)], capture_output=True, timeout=60)
    out = r.stdout.decode("utf-8", "replace").replace("\r\n", "\n")
    err = r.stderr.decode("utf-8", "replace").replace("\r\n", "\n")
    return (None, r.returncode, out, err)


# 引用一个「只在宿主进程懒加载才存在」的领域插件符号的两种写法：
#   1) 带 `@：【加载领域】` 指令（native 忽略该指令，符号仍不可解析）；
#   2) 直接引用同名符号。
DOMAIN_CASES = {
    "with_load_directive": "@：【加载领域】，机械设计\nresult = 公差系数_IT10\n#1：[result]\n",
    "bare_domain_symbol": "result = 公差系数_IT10\n#1：[result]\n",
    "domain_call": "@：【加载领域】，symbolic\ny = 泰勒展开(sin, x, 3)\n#1：[y]\n",
}


@pytest.mark.parametrize("tag", sorted(DOMAIN_CASES))
def test_native_never_fabricates_value_for_unloaded_symbol(tag):
    """未加载的领域符号在 native 侧绝不能被伪造成一个 stdout 数值。"""
    exc, rc, out, err = _run_native(DOMAIN_CASES[tag], tag)

    # 路径 A：编译期就明确拒绝（native 未实现该全局）——合规。
    if exc == "NativeNotSupported":
        return

    # 路径 B：能编译，但运行到该符号时必须干净失败（非零退出 + 无 stdout 值）。
    assert exc is None, f"{tag}: 意外编译期异常 {exc}: {err[:120]}"
    # 核心红线：native 不得把未定义符号读成裸 0 打到 stdout（NI-001 静默错值）。
    assert out.strip() == "", (
        f"{tag}: native 对未加载领域符号静默产出了值 {out!r}，"
        f"违反了『不承载插件符号且不伪造值』的设计契约"
    )
    assert rc != 0, (
        f"{tag}: native 遇未加载领域符号却以 0 码成功退出且无输出，语义不明"
    )


def test_native_domain_boundary_is_stable_across_runs():
    """同一未加载符号多次编译运行，行为一致（不会时好时坏地漏出假值）。"""
    src = DOMAIN_CASES["bare_domain_symbol"]
    results = {_run_native(src, "stable")[:3] for _ in range(2)}
    codes = {r[1] for r in results}
    outs = {r[2] for r in results}
    assert len(codes) == 1 and len(outs) == 1, "同一程序 native 行为不应非确定"
    assert "" == list(outs)[0].strip() or list(outs)[0].strip() == ""
