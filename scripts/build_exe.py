# -*- coding: utf-8 -*-
"""
Matha 独立可执行文件打包脚本

用法:
    python scripts/build_exe.py                # 打包所有命令
    python scripts/build_exe.py --matha        # 仅打包 matha REPL
    python scripts/build_exe.py --matha-cc     # 仅打包 matha-cc 编译器
    python scripts/build_exe.py --output dist  # 指定输出目录
    python scripts/build_exe.py --onefile      # 单文件模式（启动慢但便携）
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
BUILD_DIR = PROJECT_ROOT / "build"
DIST_DIR = PROJECT_ROOT / "dist"
SPEC_DIR = PROJECT_ROOT


def log(msg: str) -> None:
    print(f"[build] {msg}")


def check_pyinstaller() -> bool:
    """检查 PyInstaller 是否已安装。"""
    code, _, _ = run_cmd([sys.executable, "-m", "pip", "show", "pyinstaller"])
    return code == 0


def install_pyinstaller() -> None:
    """安装 PyInstaller。"""
    log("安装 PyInstaller...")
    run_cmd([sys.executable, "-m", "pip", "install", "pyinstaller"])


def run_cmd(cmd: list, cwd: Path = None) -> tuple:
    """运行命令。"""
    result = subprocess.run(
        cmd, cwd=str(cwd or PROJECT_ROOT),
        capture_output=True, text=True, timeout=1800
    )
    return result.returncode, result.stdout, result.stderr


def build_one(name: str, spec: str, onefile: bool = False) -> bool:
    """构建单个可执行文件——产物平铺在 `dist/` 下（`dist/<name>.exe`）。

    平铺口径与 `.github/workflows/matha-ci.yml`（`ls -la dist/matha.exe` +
    upload-artifact 路径）和 `scripts/build.bat` 同源；旧写法把 `--distpath`
    设成 `dist/<name>`，本地产物落在 `dist/<name>/<name>.exe`，与 CI 断言的
    形状不一致（中间目录仍按名分档，避免两次构建互撞）。
    """
    log(f"构建 {name}...")

    cmd = [sys.executable, "-m", "PyInstaller", "--clean"]
    if onefile:
        cmd.append("--onefile")
    cmd += ["--noconfirm", "--distpath", str(DIST_DIR),
            "--workpath", str(BUILD_DIR / name),
            spec]

    log(f"  $ {' '.join(cmd)}")
    code, stdout, stderr = run_cmd(cmd)

    if code != 0:
        log(f"  构建失败: {stderr[:300]}")
        return False

    exe_file = DIST_DIR / (f"{name}.exe" if sys.platform.startswith("win") else name)
    if exe_file.is_file():
        log(f"  ✓ {exe_file.name} ({exe_file.stat().st_size // 1024 // 1024} MB)")
    return True


def main():
    global DIST_DIR, BUILD_DIR
    parser = argparse.ArgumentParser(description="Matha 可执行文件打包工具")
    parser.add_argument("--matha", action="store_true", help="构建 matha REPL")
    parser.add_argument("--matha-cc", dest="matha_cc", action="store_true", help="构建 matha-cc 编译器")
    parser.add_argument("--all", action="store_true", help="构建全部（默认）")
    parser.add_argument("--onefile", action="store_true", help="单文件模式")
    parser.add_argument("--output", type=Path, default=DIST_DIR, help="输出目录")
    args = parser.parse_args()

    DIST_DIR = args.output
    BUILD_DIR = DIST_DIR.parent / (DIST_DIR.name + "_build")

    print("=" * 60)
    print("Matha 可执行文件打包工具")
    print("=" * 60)
    print(f"Python: {sys.version.split()[0]}")
    print(f"平台: {sys.platform}")
    print(f"输出目录: {DIST_DIR}")
    print()

    # 检查 PyInstaller
    if not check_pyinstaller():
        install_pyinstaller()

    # 清理旧构建
    for d in [BUILD_DIR, DIST_DIR]:
        if d.exists():
            shutil.rmtree(d)
            log(f"清理: {d.name}/")

    DIST_DIR.mkdir(parents=True, exist_ok=True)

    # 确定要构建的组件
    components = []
    if args.all or args.matha:
        components.append(("matha", "matha.spec", "--matha"))
    if args.all or args.matha_cc:
        components.append(("matha-cc", "matha-cc.spec", "--matha-cc"))

    if not components:
        components = [
            ("matha", "matha.spec", "--matha"),
            ("matha-cc", "matha-cc.spec", "--matha-cc"),
        ]

    # 构建
    results = []
    for name, spec, _ in components:
        ok = build_one(name, spec, args.onefile)
        results.append((name, ok))

    # 汇总
    print()
    print("=" * 60)
    print("构建完成！")
    print("=" * 60)
    for name, ok in results:
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {name}")
    print()
    print(f"可执行文件位置: {DIST_DIR}")
    print()
    print("使用说明:")
    for name, ok in results:
        if name == "matha":
            print(f"  {DIST_DIR}/matha.exe          # 启动 REPL")
            print(f"  {DIST_DIR}/matha.exe eval 'sin(pi)'  # 计算表达式")
        elif name == "matha-cc":
            print(f"  {DIST_DIR}/matha-cc.exe compile demo.matha -o c  # 编译到 C")


if __name__ == "__main__":
    main()
