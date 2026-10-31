"""漂移取证：MATHA_B09_FUSE=1 下 bootstrap/vm_matha 定点与黄金用例的真实读数。

诚实口径：本脚本只取证，不判分——融合开启导致定点红是预期结果，
写进《b09 底层重构验证报告》作为「合并前必须双侧同步」的证据。
"""
import os
import subprocess
import sys

ROOT = r"D:\trae"
env_on = dict(os.environ, MATHA_B09_FUSE="1")


def run(cmd, env, tail=8):
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, env=env,
                       timeout=3600)
    out = (p.stdout or "") + (p.stderr or "")
    lines = [ln for ln in out.splitlines() if ln.strip()]
    print(f"$ {' '.join(cmd)}  -> rc={p.returncode}")
    for ln in lines[-tail:]:
        print("   ", ln)
    return p.returncode


rc1 = run([sys.executable, "-u", "-m", "pytest",
           "tests/test_mbc_bootstrap.py", "tests/test_mbc_vm_matha.py",
           "-q", "--no-header"], env_on)
rc2 = run([sys.executable, "-u", "golden_tests/run_golden_tests.py"], env_on)
print(f"SUMMARY bootstrap_fuseON_rc={rc1} golden_fuseON_rc={rc2}")
