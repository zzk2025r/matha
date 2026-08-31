# -*- coding: utf-8 -*-
"""
Matha Windows 安装程序包装器
用法:
    python scripts/setup_matha.py              # 运行安装程序
    python scripts/setup_matha.py --uninstall  # 卸载
"""
import subprocess
import sys
import os
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.parent / "scripts"
DIST_DIR = Path(__file__).parent.parent / "dist"
VERSION = "4.4"


def log(msg: str) -> None:
    print(msg)


def run_ps1(ps1_path: Path, args: list = None) -> int:
    """运行 PowerShell 脚本。"""
    cmd = ["powershell", "-ExecutionPolicy", "Bypass"]
    if args:
        cmd.extend(args)
    cmd.extend(["-File", str(ps1_path)])

    log(f"运行: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(Path(__file__).parent.parent))
    return result.returncode


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Matha Windows 安装程序")
    parser.add_argument("--uninstall", action="store_true", help="卸载 Matha")
    parser.add_argument("--quiet", action="store_true", help="静默模式")
    args = parser.parse_args()

    if args.uninstall:
        # 运行卸载脚本
        uninstall_ps1 = SCRIPT_DIR / "uninstall.ps1"
        if uninstall_ps1.exists():
            return run_ps1(uninstall_ps1)
        else:
            log("错误: 找不到卸载脚本")
            return 1

    # 运行安装脚本
    setup_ps1 = SCRIPT_DIR / "setup_matha.ps1"
    if not setup_ps1.exists():
        log("错误: 安装脚本不存在，请先运行 build_setup.py")
        log("")
        log("构建安装程序:")
        log("  python scripts/build_setup.py")
        log("")
        log("或直接运行:")
        log(f"  powershell -ExecutionPolicy Bypass -File {setup_ps1}")
        return 1

    return run_ps1(setup_ps1)


if __name__ == "__main__":
    sys.exit(main())
