"""native 实证：sys_env 折叠后**无需任何 OS API**即可编成 exe 并运行。

同时钉住语义边界：折叠发生在**编译期**，所以 exe 里的快/慢分支由「编译时那次
进程的环境」决定；同一枚 exe 换个环境再跑，输出不变（门控已烘进机器码）。
这不是缺陷，而是「编译期门控」与用户设想的「运行期自选」的本质区别，必须写实。

休眠态（折叠关）下的预期行为已实测钉死：native **编译能过**（字节码里是
LOAD_GLOBAL sys_env），但 exe **运行期**自己报「未定义变量」并非零退出——
与 VM 口径一致，符合 P3 定的「对未解析符号绝不静默造值」契约。
"""
import contextlib
import os
import subprocess
import sys

ROOT = r"D:\trae"
SRC = os.path.join(ROOT, ".trae", "p4_b09_preview", "se_native.matha")
EXE = os.path.join(ROOT, ".trae", "p4_b09_preview", "se_native_absent.exe")
EXE_FAST = os.path.join(ROOT, ".trae", "p4_b09_preview", "se_native_fast.exe")
EXE_DORMANT = os.path.join(ROOT, ".trae", "p4_b09_preview", "se_native_dormant.exe")


def sh(cmd, env=None, cwd=ROOT):
    e = dict(os.environ)
    e.pop("MATHA_SYSENV_FOLD", None)
    e.pop("MATHA_B09_FUSE", None)
    if env:
        e.update(env)
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, env=e,
                       timeout=600)
    return p


def main() -> int:
    rows = []
    try:
        return _run(rows)
    finally:
        # exe 是可再生成物，不入库（实证脚本结束即清，重跑可复现）。
        for p in (EXE, EXE_FAST, EXE_DORMANT):
            with contextlib.suppress(OSError):
                os.remove(p)


def _run(rows) -> int:
    # 1) 折叠开启 + 环境未设 → 编译期烘进「原路径」
    p = sh([sys.executable, "-u", "-m", "src.mbc.native", SRC, "-o", EXE],
           env={"MATHA_SYSENV_FOLD": "1"})
    print(f"[build/fold-on/env-absent] rc={p.returncode}")
    r1 = sh([EXE])
    print(f"  run exe                     -> rc={r1.returncode} out={r1.stdout.strip()!r}")
    rows.append(("编译期无 env → exe 烘进原路径", r1.returncode == 0
                 and r1.stdout.strip() == "1"))

    # 2) 同一枚 exe 换环境再跑：输出不变——证明门控属**编译期**，运行期不可选
    r2 = sh([EXE], env={"MATHA_FAST_B09": "1"})
    print(f"  run 同一 exe, env=1        -> rc={r2.returncode} out={r2.stdout.strip()!r}")
    rows.append(("同一 exe 换 env 输出不变（烘进机器码）",
                 r2.returncode == 0 and r2.stdout.strip() == "1"))

    # 3) 折叠开启 + 编译期 env=1 → 快路径烘进机器码（无 OS API 参与运行期）
    p3 = sh([sys.executable, "-u", "-m", "src.mbc.native", SRC, "-o", EXE_FAST],
            env={"MATHA_SYSENV_FOLD": "1", "MATHA_FAST_B09": "1"})
    r3 = sh([EXE_FAST])
    print(f"[build/fold-on/env=1] rc={p3.returncode} run -> "
          f"rc={r3.returncode} out={r3.stdout.strip()!r}")
    rows.append(("编译期 env=1 → exe 跑快路径", r3.returncode == 0
                 and r3.stdout.strip() == "99"))

    # 4) 折叠关闭 → 编译能过（字节码为 LOAD_GLOBAL sys_env），但 exe 运行期必须
    #    拒给值：非零退出 + 报未定义变量（与 VM 口径一致，符合「绝不静默造值」）。
    p4 = sh([sys.executable, "-u", "-m", "src.mbc.native", SRC, "-o", EXE_DORMANT])
    r4 = sh([EXE_DORMANT])
    print(f"[build/fold-off] rc={p4.returncode} run -> rc={r4.returncode} "
          f"out={r4.stdout.strip()!r} err={(r4.stderr or '').strip()[:80]!r}")
    rows.append(("休眠态 native 运行期拒给值（rc≠0、无合法输出）",
                 p4.returncode == 0 and r4.returncode != 0
                 and r4.stdout.strip() not in ("1", "99")))

    bad = [i for i, (ok, _) in enumerate(rows) if not ok]
    for name, ok in rows:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    print(f"SUMMARY native_proof={len(rows) - len(bad)}/{len(rows)} passed 失败项={bad or '无'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
