#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Matha 离线部署脚本（目标机器运行）

在离线目标机器上运行此脚本，将 Matha 离线包部署到 Python 环境。

用法:
    # 基本部署
    python deploy_offline.py

    # 跳过测试加快部署
    python deploy_offline.py --skip-tests

    # 验证当前环境
    python deploy_offline.py --check

    # 指定 wheel 目录（如果不在默认位置）
    python deploy_offline.py --wheels /path/to/wheels
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import shutil
import tarfile
from datetime import datetime
from pathlib import Path

# ═══════════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════════

PROJECT_ROOT = Path(__file__).parent.parent
SRC_DIR = PROJECT_ROOT / "src"
TESTS_DIR = PROJECT_ROOT / "tests"
WHEELS_DIR = PROJECT_ROOT / "wheels"
REQ_FILE = PROJECT_ROOT / "offline_requirements.txt"

# 验证的模块列表
REQUIRED_MODULES = [
    ("src.math_driver", "MathDriver"),
    ("src.compiler.matha_cc", "MathaLexer, MathaParser"),
    ("src.mir", "MIRGenerator"),
    ("src.mir_codegen", "MIRToCGenerator"),
    ("src.mir_converter", "convert"),
    ("src.compiler.memoize", "get_memoize_optimizer"),
    ("src.compiler.jit", "compile_func, jit_func"),
    ("src.compiler.llvm_hybrid", "HybridLLVMBackend"),
    ("src.profiler", "MathaProfiler"),
    ("src.lsp", "MathaLSP"),
    ("src.doc_gen", "DocGenerator"),
    ("src.pkg_manager_v2", "MathaPackageManager"),
    ("src.multi_lang_codegen", "MultiLangCodegen"),
    ("src.multi_lang_verifier", "MultiLangVerifier"),
    ("src.csp_os_thread", "CSPRuntime"),
    ("src.type_system_v2", "TypeSystemV2"),
    ("src.offline_store", "get_offline_store"),
    ("src.offline.sqlite_storage", "SQLiteStorage"),
]


# ═══════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════

def log(msg: str, indent: int = 0) -> None:
    """打印带缩进的消息。"""
    prefix = "  " * indent
    print(f"{prefix}[deploy] {msg}")


def run_cmd(cmd: list, desc: str = "", cwd: Path = None) -> int:
    """运行命令，返回退出码。"""
    if desc:
        log(f"执行: {desc}")
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        cwd=str(cwd or PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=300
    )
    if result.returncode != 0:
        log(f"警告: {desc} 返回码 {result.returncode}", indent=1)
        if result.stderr:
            log(result.stderr[:500], indent=1)
    return result.returncode


def check_python() -> bool:
    """检查 Python 版本。"""
    log("检查 Python 环境...")
    version = sys.version_info
    if version < (3, 10):
        log(f"错误: 需要 Python >= 3.10，当前为 {version.major}.{version.minor}", indent=1)
        return False
    log(f"Python {version.major}.{version.minor}.{version.micro} OK")
    return True


def install_pip_packages() -> bool:
    """安装 pip 依赖。"""
    log("检查 pip 依赖...")

    wheels = list(WHEELS_DIR.glob("*.whl")) if WHEELS_DIR.exists() else []

    if wheels:
        log(f"找到 {len(wheels)} 个 wheel 文件，本地安装...")
        cmd = [sys.executable, "-m", "pip", "install", "--no-index"]
        cmd += ["--find-links=" + str(WHEELS_DIR.absolute())]
        if REQ_FILE.exists():
            cmd += ["-r", str(REQ_FILE.absolute())]
        else:
            cmd += ["sympy>=1.14.0", "numpy>=1.24.0", "scipy>=1.10.0", "numba>=0.57.0",
                    "pytest>=7.0.0", "pytest-cov>=4.0.0"]
        return run_cmd(cmd, "安装 pip 依赖") == 0
    else:
        log("wheel 目录为空，尝试在线安装（需要网络）...", indent=1)
        if not REQ_FILE.exists():
            log("错误: 未找到 offline_requirements.txt", indent=1)
            return False
        return run_cmd([sys.executable, "-m", "pip", "install", "-r", str(REQ_FILE.absolute())],
                       "安装 pip 依赖") == 0


def setup_project() -> bool:
    """设置项目环境。"""
    log("设置 Matha 项目环境...")

    # 设置 PYTHONPATH
    os.environ["PYTHONPATH"] = str(PROJECT_ROOT)

    # 创建必要目录
    for d in [PROJECT_ROOT / ".matha", PROJECT_ROOT / ".matha" / "cache",
              PROJECT_ROOT / ".matha" / "envs", PROJECT_ROOT / ".matha" / "packages"]:
        d.mkdir(parents=True, exist_ok=True)
        log(f"创建目录: {d.name}/", indent=1)

    # 安装项目（editable 模式）
    if (PROJECT_ROOT / "pyproject.toml").exists():
        return run_cmd([sys.executable, "-m", "pip", "install", "-e", "."],
                       "安装 Matha 项目") == 0
    return True


def run_tests() -> bool:
    """运行测试。"""
    log("运行 Matha 测试套件...")
    cmd = [sys.executable, "-m", "unittest",
           "discover", "-s", "tests", "-p", "test_*.py",
           "-v", "--tb=short"]
    return run_cmd(cmd, "运行测试") == 0


def verify_installation() -> bool:
    """验证安装。"""
    log("验证模块导入...")
    all_ok = True
    # 确保项目根目录在 Python 路径中
    _root = str(PROJECT_ROOT)
    if _root not in sys.path:
        sys.path.insert(0, _root)
    # 也设置 PYTHONPATH 供 subprocess 子进程使用
    os.environ["PYTHONPATH"] = _root

    for module, names in REQUIRED_MODULES:
        try:
            exec(f"from {module} import {names}")
            log(f"  [OK] {module} ({names})", indent=1)
        except ImportError as e:
            log(f"  [FAIL] {module}: {e}", indent=1)
            all_ok = False
        except Exception as e:
            log(f"  [WARN] {module}: {e}", indent=1)

    return all_ok


def show_usage() -> None:
    """显示使用说明。"""
    print()
    print("=" * 60)
    print("Matha 已部署！快速开始：")
    print("=" * 60)
    print()
    print("  # 启动 REPL")
    print("  matha")
    print()
    print("  # 编译运行 Matha 程序")
    print("  matha run examples/demo.matha")
    print()
    print("  # 编译到 C")
    print("  matha-cc compile demo.matha -o c")
    print()
    print("  # 编译到 Python")
    print("  matha-cc compile demo.matha -o python")
    print()
    print("  # 运行测试")
    print("  python -m unittest discover -s tests -p 'test_*.py'")
    print()
    print("  # 验证离线环境")
    print("  python scripts/verify_offline.py")
    print()
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Matha 离线部署工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python deploy_offline.py                    # 完整部署
  python deploy_offline.py --skip-tests       # 跳过测试
  python deploy_offline.py --check            # 验证当前环境
  python deploy_offline.py --wheels /path     # 指定 wheel 目录
        """
    )
    parser.add_argument("--check", action="store_true", help="仅验证当前环境（不安装）")
    parser.add_argument("--skip-deps", action="store_true", help="跳过 pip 依赖安装")
    parser.add_argument("--skip-tests", action="store_true", help="跳过测试运行")
    parser.add_argument("--wheels", type=Path, help="指定 wheel 文件目录")
    args = parser.parse_args()

    # 覆盖 wheel 目录
    if args.wheels:
        global WHEELS_DIR
        WHEELS_DIR = args.wheels

    print("=" * 60)
    print("Matha 离线部署工具")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()

    # 检查 Python
    if not check_python():
        sys.exit(1)

    # 仅检查模式
    if args.check:
        log("验证模式 - 仅检查已安装模块...")
        ok = verify_installation()
        print()
        if ok:
            print("✅ 验证通过！")
        else:
            print("❌ 验证失败，请检查错误信息")
        sys.exit(0 if ok else 1)

    # 1. 安装 pip 依赖
    if not args.skip_deps:
        if not install_pip_packages():
            log("警告: 部分依赖安装可能有问题，继续...", indent=1)
    else:
        log("跳过 pip 依赖安装")

    # 2. 设置项目
    if not setup_project():
        log("警告: 项目设置可能有问题，继续...", indent=1)

    # 3. 验证安装
    log("")
    ok = verify_installation()

    # 4. 运行测试
    if not args.skip_tests:
        log("")
        test_ok = run_tests()
        if not test_ok:
            log("警告: 部分测试失败", indent=1)
    else:
        log("跳过测试运行")

    # 5. 显示使用说明
    show_usage()

    # 6. 返回结果
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
