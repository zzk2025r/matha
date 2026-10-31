"""b09 紧邻 A/B：同一进程脚本内先后测 OFF/ON 两轮的纯执行耗时（排除跨时段漂移）。

方法学与 KNOWN_ISSUES 第六节一致：同机相邻两轮，各取 min+median。
编译耗时单列（融合改变指令数，编译期扫描成本几乎不变）。
"""
import os
import statistics
import subprocess
import sys

RUNNER = r"""
import os, statistics, sys, time
sys.path.insert(0, r"D:\trae")
from src.mbc.compiler import compile_source, _B09_FUSE
from src.mbc.vm import run_module

SRC = (open(r"D:\trae\scripts\bench_cases\b09_for_iter.matha", encoding="utf-8")
       .read().replace("{N}", "50000"))
REPEATS = 7
ts, ct = [], None
for _ in range(REPEATS):
    t0 = time.perf_counter()
    mod = compile_source(SRC)
    t1 = time.perf_counter()
    run_module(mod)
    ts.append((time.perf_counter() - t1) * 1000.0)
    ct = (t1 - t0) * 1000.0
print(f"fuse={_B09_FUSE} run_min={min(ts):8.1f} run_med={statistics.median(ts):8.1f} compile={ct:6.1f}")
"""


def run(env_val: str) -> str:
    env = dict(os.environ)
    if env_val == "1":
        env["MATHA_B09_FUSE"] = "1"
    else:
        env.pop("MATHA_B09_FUSE", None)
    p = subprocess.run([sys.executable, "-u", "-c", RUNNER], capture_output=True,
                       text=True, env=env, cwd=r"D:\trae", timeout=600)
    return (p.stdout or p.stderr).strip()


if __name__ == "__main__":
    print("OFF:", run("0"))
    print("ON :", run("1"))
    print("OFF:", run("0"))
    print("ON :", run("1"))
