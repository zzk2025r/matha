"""阶段 1 验收探针：验证「未引用领域符号 ⇒ 不加载任何领域模块」。

不是 pytest 用例（避免与 pytest 的 conftest 相互影响），而是一段可反复运行的
口径检查，供 make check 与人工核对使用：

    python scripts/check_lazy_plugins.py
"""
from __future__ import annotations

import subprocess
import sys

PROBE = r"""
import json, sys
import src.interp as I

out = {}
out['domains_after_import'] = sorted(m for m in sys.modules if m.startswith('src.domains'))

it = I.Interpreter()

# 1) 取用内核内建：不得加载任何领域模块
out['sin'] = float(it.builtins['sin'](0))
out['after_kernel_use'] = sorted(m for m in sys.modules if m.startswith('src.domains'))

# 2) 名字类查询不触发 import
out['has_domain_symbol'] = '材料_胡克' in it.builtins
out['after_name_query'] = sorted(m for m in sys.modules if m.startswith('src.domains'))

# 3) 取用领域符号：只加载它所属的那一个模块
fn = it.builtins['材料_胡克']
out['callable'] = callable(fn)
out['after_domain_use'] = sorted(m for m in sys.modules if m.startswith('src.domains'))

out['builtin_count'] = len(it.builtins)
print(json.dumps(out, ensure_ascii=False))
"""


def main() -> int:
    proc = subprocess.run([sys.executable, "-c", PROBE], capture_output=True,
                          text=True, cwd=".")
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr)
        return 1
    import json
    data = json.loads(proc.stdout.strip().splitlines()[-1])
    print("import src.interp 后：      ", data["domains_after_import"])
    print("取用内核内建后：          ", data["after_kernel_use"])
    print("名字类查询后（不加载）：  ", data["after_name_query"],
          "| 符号存在于表中 =", data["has_domain_symbol"])
    print("取用领域符号后：          ", data["after_domain_use"])
    print("sin(0) =", data["sin"], "| 内建表规模 =", data["builtin_count"])
    ok = (not data["domains_after_import"]
          and not data["after_kernel_use"]
          and not data["after_name_query"]
          and data["has_domain_symbol"]
          and data["callable"]
          and len(data["after_domain_use"]) <= 2)
    print("[OK] 懒加载契约成立" if ok else "[FAIL] 懒加载契约被破坏")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
