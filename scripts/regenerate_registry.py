# -*- coding: utf-8 -*-
"""
自动扫描 src/domains/ 目录，生成/更新 interp.py 中的注册条目。

用法:
    python scripts/regenerate_registry.py
"""
import os
import re
from pathlib import Path

DOMAINS_DIR = Path(__file__).parent.parent / "src" / "domains"
INTERP_FILE = Path(__file__).parent.parent / "src" / "interp.py"


def scan_domains() -> dict[str, str]:
    """扫描所有域文件，提取注册函数名。"""
    domains = {}
    for f in sorted(DOMAINS_DIR.glob("*.py")):
        if f.name.startswith("_") or f.name == "__init__.py":
            continue
        content = f.read_text(encoding="utf-8")
        match = re.search(r"def (_register_\w+)\(builtins", content)
        if match:
            module_name = f.stem
            fn_name = match.group(1)
            domains[module_name] = fn_name
    return domains


def generate_registry_lines(domains: dict[str, str]) -> list[str]:
    """生成 interp.py 中的注册条目列表。"""
    lines = []
    for mod_name in sorted(domains.keys()):
        fn_name = domains[mod_name]
        lines.append(f'        ("src.domains.{mod_name}", "{fn_name}"),')
    return lines


def update_interp_py(lines: list[str]) -> bool:
    """将注册条目注入到 interp.py 中。"""
    content = INTERP_FILE.read_text(encoding="utf-8")

    # 找到现有的注册列表结束位置（在 "hardware" 条目之后）
    marker = '        ("src.domains.hardware", "_register_hardware"),'
    if marker not in content:
        print(f"ERROR: 未找到注册标记: {marker}")
        return False

    # 找到 # AI/游戏/前沿领域 注释位置，在其后插入新条目
    insert_marker = '        # 硬件控制与嵌入式'
    if insert_marker not in content:
        print(f"ERROR: 未找到插入位置标记")
        return False

    new_entries = "\n".join(lines)
    replacement = new_entries + "\n" + insert_marker

    if replacement in content:
        print("注册条目已存在，跳过更新")
        return False

    # 在硬件注释前插入新条目
    updated = content.replace(insert_marker, replacement, 1)
    INTERP_FILE.write_text(updated, encoding="utf-8")
    print(f"已更新 {INTERP_FILE}")
    return True


def main() -> None:
    print("=== Matha 领域注册生成器 ===")
    domains = scan_domains()
    print(f"发现 {len(domains)} 个已注册领域")
    for name, fn in sorted(domains.items()):
        print(f"  {name:30s} -> {fn}")

    lines = generate_registry_lines(domains)
    if lines:
        print(f"\n生成 {len(lines)} 行注册条目")
        update_interp_py(lines)
    else:
        print("未发现任何注册函数")


if __name__ == "__main__":
    main()
