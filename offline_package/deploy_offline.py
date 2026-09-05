#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Matha 离线部署脚本
用法:
    python deploy_offline.py [选项]

选项:
    --help          显示帮助
    --check         验证当前环境（不安装）
    --source=path   指定源码路径
    --wheels=path   指定 wheel 目录
    --skip-deps     跳过 pip 依赖安装
    --skip-tests    跳过测试运行
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
SRC_DIR = PROJECT_ROOT / "src"
TESTS_DIR = PROJECT_ROOT / "tests"
WHEELS_DIR = PROJECT_ROOT / "wheels"
REQ_FILE = PROJECT_ROOT / "offline_requirements.txt"


def log(msg: str) -> None:
    print(f"[deploy] {msg}")


def run(cmd: list, desc: str = "") -> int:
    if desc:
        log(f"执行: {desc}")
    print(f"  $ {" ".join(cmd)}")
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    return result.returncode


def install_pip_packages() -> bool:
    """安装 pip 依赖。"""
    log("检查 pip 依赖...")
    wheels = list(WHEELS_DIR.glob("*.whl")) if WHEELS_DIR.exists() else []

    if wheels:
        log(f"从本地 wheel 安装 {len(wheels)} 个包...")
        cmd = [sys.executable, "-m", "pip", "install", "--no-index"]
        cmd += ["--find-links=" + str(WHEELS_DIR)]
        if REQ_FILE.exists():
            cmd += ["-r", str(REQ_FILE)]
        else:
            cmd += ["sympy", "numpy", "scipy", "numba",
                    "pytest", "pytest-cov", "black", "flake8"]
        return run(cmd, "安装离线依赖") == 0
    else:
        log("wheel 目录为空，尝试在线安装（需要网络）...")
        cmd = [sys.executable, "-m", "pip", "install", "-r", str(REQ_FILE)]
        return run(cmd, "安装依赖") == 0


def setup_project() -> bool:
    """设置项目环境。"""
    log("设置 Matha 项目环境...")

    # 确保 PATH 正确
    os.environ["PYTHONPATH"] = str(PROJECT_ROOT)

    # 创建必要的目录
    for d in [PROJECT_ROOT / ".matha", PROJECT_ROOT / ".matha" / "cache"]:
        d.mkdir(exist_ok=True)

    # 安装项目
    if (PROJECT_ROOT / "pyproject.toml").exists():
        return run([sys.executable, "-m", "pip", "install", "-e", "."],
                   "安装 Matha 项目") == 0
    return True


def run_tests() -> bool:
    """运行测试。"""
    log("运行 Matha 测试...")
    cmd = [sys.executable, "-m", "unittest",
           "discover", "-s", "tests", "-p", "test_*.py",
           "-v", "--tb=short"]
    return run(cmd, "运行测试") == 0


def verify_installation() -> bool:
    """验证安装。"""
    log("验证安装...")

    checks = [
        ("数学核心", ["from src.math_driver import MathDriver"]),
        ("解释器", ["from src.compiler.matha_cc import MathaLexer, MathaParser"]),
        ("MIR", ["from src.mir import MIRGenerator"]),
        ("代码生成", ["from src.mir_codegen import MIRToCGenerator"]),
        ("Memoization", ["from src.compiler.memoize import get_memoize_optimizer"]),
        ("Profiler", ["from src.profiler import MathaProfiler"]),
        ("LSP", ["from src.lsp import MathaLSP"]),
        ("文档生成", ["from src.doc_gen import DocGenerator"]),
        ("包管理器", ["from src.pkg_manager_v2 import MathaPackageManager"]),
    ]

    all_ok = True
    for name, imports in checks:
        code = "; ".join(imports)
        rc, _, stderr = run_cmd([sys.executable, "-c", code])
        if rc == 0:
            log(f"  {name}: OK")
        else:
            log(f"  {name}: FAIL ({stderr[:100]})")
            all_ok = False

    return all_ok


def run_cmd(cmd: list) -> tuple:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return result.returncode, result.stdout, result.stderr


def main():
    parser = argparse.ArgumentParser(description="Matha 离线部署脚本")
    parser.add_argument("--check", action="store_true", help="验证当前环境")
    parser.add_argument("--skip-deps", action="store_true", help="跳过 pip 依赖")
    parser.add_argument("--skip-tests", action="store_true", help="跳过测试")
    args = parser.parse_args()

    log("=" * 50)
    log("Matha 离线部署工具")
    log("=" * 50)

    if args.check:
        ok = verify_installation()
        sys.exit(0 if ok else 1)

    # 1. 安装依赖
    if not args.skip_deps:
        if not install_pip_packages():
            log("警告: 依赖安装可能有问题，继续...")

    # 2. 设置项目
    setup_project()

    # 3. 运行测试
    if not args.skip_tests:
        if not run_tests():
            log("警告: 部分测试失败，请检查")

    # 4. 验证安装
    if verify_installation():
        log("部署完成！")
    else:
        log("警告: 部分模块导入失败")

    # 5. 显示信息
    log("")
    log("快速开始:")
    log("  matha run examples/demo.matha")
    log("  matha-cc compile demo.matha -o c")
    log("  python -m unittest discover -s tests -p test_*.py")
    log("")


if __name__ == "__main__":
    main()
