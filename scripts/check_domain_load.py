"""阶段 1 第 4 项验收探针：显式加载语法 + 未加载引用的编译期诊断。

跑法：python scripts/check_domain_load.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.kernel import exec_api as E


def _domain_modules() -> list[str]:
    return sorted(m for m in sys.modules
                  if m == "src.domains" or m.startswith("src.domains."))


def main() -> int:
    fails: list[str] = []

    # 1) 默认（auto）：内核符号求值不触发任何领域 import
    sys.modules.pop("src.domains", None)
    out = E.run("result = sin(0)\n#1：[result]")
    if out != [0.0]:
        fails.append(f"auto 求值结果异常：{out!r}")
    if _domain_modules():
        fails.append(f"内核求值意外加载了领域模块：{_domain_modules()}")

    # 2) off：完全不接插件层
    out = E.run("result = sin(0)\n#1：[result]", plugins="off")
    if out != [0.0]:
        fails.append(f"off 求值结果异常：{out!r}")

    # 3) 未写指令时引用领域符号 → strict 模式编译期诊断
    src_missing = "result = 公差系数_IT10\n#1：[result]"
    try:
        E.run(src_missing, plugins="strict")
        fails.append("strict 模式下未加载领域却成功执行，诊断未生效")
    except RuntimeError as e:
        msg = str(e)
        if "加载领域" not in msg:
            fails.append(f"诊断信息未给出加载指令提示：{msg}")
        else:
            print(f"[OK] 编译期诊断：{msg}")

    # 4) 写上指令后即可用，且只加载被点名的插件（中文名作为寻址别名）
    out = E.run("@：【加载领域】，机械设计\nresult = 公差系数_IT10\n#1：[result]",
                plugins="strict")
    if out != [64.0]:
        fails.append(f"显式加载后取值不对：{out!r}")
    loaded = E._resolver().loaded()
    if set(loaded) != {"mech_design"}:
        fails.append(f"显式加载波及了其它插件：{loaded}")
    print(f"[OK] 显式加载（strict）：{out!r} 已加载插件 {loaded}")

    # 5) auto 模式下未写指令也能按需懒加载（旧程序不受影响）：只多拉一个插件
    out = E.run("fn = 胡克定律\nresult = 1\n#1：[result]")
    loaded = E._resolver().loaded()
    if set(loaded) != {"mech_design", "extended_modeling"}:
        fails.append(f"auto 懒加载范围不对：{loaded}")
    print(f"[OK] auto 懒加载：{out!r} 已加载插件 {loaded}")
    print("[OK] 可用后端：", ", ".join(E.available_modes()))

    # 6) 插件枚举零 import 成本
    before = set(sys.modules)
    plugins = E.list_domains()
    leaked = sorted(m for m in set(sys.modules) - before if m.startswith("src.domains."))
    if leaked:
        fails.append(f"枚举插件产生了 import 成本：{leaked}")
    print(f"[OK] 枚举插件 {len(plugins)} 个，未加载任何模块")

    for f in fails:
        print(f"[FAIL] {f}")
    if fails:
        return 1
    print("[OK] 阶段 1 第 4 项契约成立")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
