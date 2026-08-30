#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Matha 离线打包脚本

用法:
    python scripts/package_offline.py                        # 完整离线包
    python scripts/package_offline.py --core                 # 仅核心包（最小）
    python scripts/package_offline.py --out /path/to/output  # 指定输出目录
    python scripts/package_offline.py --no-tests             # 不包含测试
    python scripts/package_offline.py --no-pycache           # 不包含 __pycache__

功能:
    1. 打包 Matha 源码（src/ + tests/ + scripts/ + docs/）
    2. 打包 pip 依赖 wheel（sympy, numpy, scipy, numba 等）
    3. 打包本地已安装包
    4. 生成离线部署清单和安装脚本
    5. 生成 SHA256 校验文件
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

# ═══════════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════════

PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "offline_package"

# 核心模块（必须打包）
CORE_DIRS = [
    "src",
    "tests",
    "scripts",
    "docs",
    "packages",
    "release",
]

# 核心文件（必须打包）
CORE_FILES = [
    "pyproject.toml",
    "requirements.txt",
    "requirements_core.txt",
    "requirements_all.txt",
    "README.md",
    "CHANGELOG.md",
    "LICENSE",
    ".gitignore",
]

# 可选模块（--core 模式不包含）
OPTIONAL_DIRS = []

# pip 依赖列表（离线安装用）
PIP_PACKAGES = [
    "sympy>=1.14.0",
    "numpy>=1.24.0",
    "scipy>=1.10.0",
    "numba>=0.57.0",
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
    "black>=23.0.0",
    "flake8>=6.0.0",
    "mypy>=1.0.0",
    "ruff>=0.1.0",
]

# 平台特定文件（Windows 需要）
WINDOWS_ONLY = ["llvmlite.dll"] if sys.platform == "win32" else []

# ═══════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════

def log(msg: str, indent: int = 0) -> None:
    """打印带缩进的消息。"""
    prefix = "  " * indent
    print(f"{prefix}[offline] {msg}")


def sha256_file(path: Path) -> str:
    """计算文件 SHA256。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def run_cmd(cmd: List[str], cwd: Optional[Path] = None) -> tuple[int, str, str]:
    """运行命令，返回 (returncode, stdout, stderr)。"""
    try:
        result = subprocess.run(
            cmd, cwd=str(cwd or PROJECT_ROOT),
            capture_output=True, text=True, timeout=120
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "Command timed out"
    except Exception as e:
        return 1, "", str(e)


# ═══════════════════════════════════════════════════════════════
# 打包函数
# ═══════════════════════════════════════════════════════════════

def get_python_version() -> str:
    """获取当前 Python 版本。"""
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def get_platform() -> str:
    """获取平台标识。"""
    import platform
    return f"{platform.system().lower()}-{platform.machine().lower()}"


def list_pip_packages() -> List[Dict]:
    """列出已安装的 pip 包。"""
    code, stdout, _ = run_cmd([sys.executable, "-m", "pip", "list", "--format=json"])
    if code != 0:
        return []
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return []


def get_pip_cache_dir() -> Path:
    """获取 pip 缓存目录。"""
    code, stdout, _ = run_cmd([sys.executable, "-m", "pip", "cache", "dir"])
    if code == 0 and stdout.strip():
        return Path(stdout.strip())
    # 默认缓存路径
    cache = Path.home() / ".pip" / "cache"
    if cache.exists():
        return cache
    return Path.home() / ".cache" / "pip"


def download_pip_wheels(packages: List[str], dest: Path) -> List[Path]:
    """下载指定包的 wheel 文件到目标目录。"""
    log(f"下载 {len(packages)} 个 pip 包...")
    dest.mkdir(parents=True, exist_ok=True)

    # pip download 命令
    cmd = [
        sys.executable, "-m", "pip", "download",
        "-d", str(dest),
        "--no-deps",  # 只下载指定的包，不下载依赖
    ] + packages

    code, stdout, stderr = run_cmd(cmd)
    if code != 0:
        log(f"部分包下载失败: {stderr[:200]}", indent=1)

    wheels = list(dest.glob("*.whl"))
    log(f"成功下载 {len(wheels)} 个 wheel 文件")
    return wheels


def download_pip_wheels_all(dest: Path) -> List[Path]:
    """下载所有已安装包的 wheel 文件。"""
    log("扫描已安装包...")
    packages = list_pip_packages()
    log(f"找到 {len(packages)} 个已安装包", indent=1)

    # 只下载 Matha 相关依赖
    relevant = [
        p["name"] for p in packages
        if p["name"].lower() in {
            "sympy", "numpy", "scipy", "numba",
            "pytest", "pytest-cov", "black", "flake8", "mypy", "ruff",
        }
    ]
    relevant = list(dict.fromkeys(relevant))  # 去重保持顺序
    log(f"需要下载 {len(relevant)} 个相关包", indent=1)

    return download_pip_wheels(relevant, dest)


def create_source_archive(output_dir: Path, include_tests: bool = True,
                          include_pycache: bool = False) -> Path:
    """创建 Matha 源码归档。"""
    log("创建源码归档...")

    archive_path = output_dir / f"matha-source-{datetime.now().strftime('%Y%m%d')}.tar.gz"

    with tarfile.open(archive_path, "w:gz") as tar:
        # 添加核心目录
        for d in CORE_DIRS:
            src = PROJECT_ROOT / d
            if src.exists():
                # 排除 __pycache__
                if not include_pycache:
                    tar.add(str(src), arcname=d,
                            filter=lambda x: _exclude_pycache(x))
                else:
                    tar.add(str(src), arcname=d)

        # 添加核心文件
        for f in CORE_FILES:
            src = PROJECT_ROOT / f
            if src.exists():
                tar.add(str(src), arcname=f)

        # 添加平台特定文件
        for f in WINDOWS_ONLY:
            src = PROJECT_ROOT / f
            if src.exists():
                tar.add(str(src), arcname=f)

    log(f"源码归档: {archive_path.name} ({archive_path.stat().st_size // 1024} KB)")
    return archive_path


def _exclude_pycache(tarinfo: tarfile.TarInfo) -> Optional[tarfile.TarInfo]:
    """过滤 __pycache__ 目录。"""
    if "__pycache__" in tarinfo.name:
        return None
    if tarinfo.name.endswith(".pyc"):
        return None
    return tarinfo


def create_packages_archive(wheel_dir: Path, output_dir: Path) -> Optional[Path]:
    """创建 pip 包归档。"""
    wheels = list(wheel_dir.glob("*.whl"))
    if not wheels:
        log("没有 wheel 文件可打包", indent=1)
        return None

    log(f"打包 {len(wheels)} 个 wheel 文件...")

    archive_path = output_dir / f"matha-pip-packages-{datetime.now().strftime('%Y%m%d')}.tar.gz"
    with tarfile.open(archive_path, "w:gz") as tar:
        for wheel in wheels:
            tar.add(str(wheel), arcname=f"pip/{wheel.name}")

    log(f"包归档: {archive_path.name} ({archive_path.stat().st_size // 1024} KB)")
    return archive_path


def create_offline_requirements(output_dir: Path) -> Path:
    """生成离线环境 requirements 文件。"""
    log("生成离线依赖清单...")

    content = f"""\
# Matha 离线环境依赖清单
# 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# Python 版本: {get_python_version()}
# 平台: {get_platform()}

# ============================================================
# 核心依赖（必须安装）
# ============================================================
sympy>=1.14.0

# ============================================================
# 性能依赖（强烈推荐）
# ============================================================
numpy>=1.24.0
scipy>=1.10.0
numba>=0.57.0

# ============================================================
# 开发依赖（可选）
# ============================================================
pytest>=7.0.0
pytest-cov>=4.0.0
black>=23.0.0
flake8>=6.0.0
mypy>=1.0.0
ruff>=0.1.0
"""

    req_path = output_dir / "offline_requirements.txt"
    req_path.write_text(content, encoding="utf-8")
    log(f"依赖清单: {req_path.name}")
    return req_path


def create_deploy_script(output_dir: Path) -> Path:
    """生成离线部署脚本。"""
    log("生成离线部署脚本...")

    script_content = f'''#!/usr/bin/env python3
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
    print(f"[deploy] {{msg}}")


def run(cmd: list, desc: str = "") -> int:
    if desc:
        log(f"执行: {{desc}}")
    print(f"  $ {{" ".join(cmd)}}")
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    return result.returncode


def install_pip_packages() -> bool:
    """安装 pip 依赖。"""
    log("检查 pip 依赖...")
    wheels = list(WHEELS_DIR.glob("*.whl")) if WHEELS_DIR.exists() else []

    if wheels:
        log(f"从本地 wheel 安装 {{len(wheels)}} 个包...")
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
            log(f"  {{name}}: OK")
        else:
            log(f"  {{name}}: FAIL ({{stderr[:100]}})")
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
'''

    deploy_path = output_dir / "deploy_offline.py"
    deploy_path.write_text(script_content, encoding="utf-8")
    log(f"部署脚本: {deploy_path.name}")
    return deploy_path


def create_readme(output_dir: Path) -> Path:
    """生成离线使用说明。"""
    log("生成离线使用说明...")

    content = f"""# Matha 离线部署包

## 概述

本目录包含 Matha 数学编程语言的完整离线安装包。

- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- Python 版本: {get_python_version()}
- 平台: {get_platform()}

## 目录结构

```
offline_package/
├── matha-source-*.tar.gz    # Matha 源码包
├── matha-pip-packages-*.tar.gz  # pip 依赖包
├── offline_requirements.txt # 离线依赖清单
├── deploy_offline.py        # 离线部署脚本
├── verify_offline.py        # 离线验证脚本
├── checksums.sha256        # 校验和文件
└── README.md                # 本文件
```

## 离线部署步骤

### 1. 传输到目标机器

将整个 `offline_package/` 目录通过 U 盘、内网传输等方式拷贝到目标机器。

### 2. 运行部署脚本

```bash
# 进入离线包目录
cd offline_package

# 运行部署（会自动安装依赖和运行测试）
python deploy_offline.py

# 或跳过测试加快部署
python deploy_offline.py --skip-tests
```

### 3. 验证安装

```bash
# 验证环境
python deploy_offline.py --check

# 或手动验证
python verify_offline.py
```

### 4. 开始使用

```bash
# 启动 REPL
matha

# 编译运行 Matha 程序
matha run examples/demo.matha

# 编译到 C
matha-cc compile demo.matha -o c

# 编译到 Python
matha-cc compile demo.matha -o python

# 运行测试
python -m unittest discover -s tests -p "test_*.py"
```

## 核心功能（离线可用）

- [x] 解释器/编译器（Lexer → Parser → MIR → CodeGen）
- [x] JIT 函数级编译 + 自动 Memoization
- [x] C/Python/Matha 代码生成
- [x] C++/Rust/Go/Java 代码生成
- [x] 性能 Profiler（火焰图 + Markdown/JSON 报告）
- [x] LSP 语言服务器（补全/悬停/定义跳转/诊断）
- [x] 包管理器（本地包管理）
- [x] API 文档生成（Markdown/HTML/JSON）
- [x] 多语言交叉验证
- [x] 类型系统增强（依赖类型/泛型/子类型）
- [x] CSP 进程级并发
- [x] SQLite 离线存储

## 网络依赖（离线不可用）

- 远程包安装/搜索（`matha install --remote`）
- LLM 意图解析（自动降级到正则解析）
- Growth Engine 网络搜索（自动降级到本地）
- 移动端 WebSocket 协作
- 3D 代码生成 CDN 依赖

## 校验文件完整性

```bash
# 在项目根目录运行
sha256sum -c checksums.sha256

# 或手动计算
python -c "import hashlib; print(hashlib.sha256(open('matha-source-*.tar.gz','rb').read()).hexdigest())"
```
"""

    readme_path = output_dir / "README.md"
    readme_path.write_text(content, encoding="utf-8")
    log(f"使用说明: {readme_path.name}")
    return readme_path


def create_checksums(output_dir: Path) -> Path:
    """生成校验和文件。"""
    log("生成校验和...")

    checksums = {}
    for f in output_dir.iterdir():
        if f.name == "checksums.sha256":
            continue
        if f.is_file() and not f.name.startswith("."):
            checksums[f.name] = sha256_file(f)

    lines = []
    for name, sha in sorted(checksums.items()):
        lines.append(f"{sha}  {name}")

    checksum_path = output_dir / "checksums.sha256"
    checksum_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"校验文件: {checksum_path.name} ({len(checksums)} 个文件)")
    return checksum_path


# ═══════════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Matha 离线打包工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/package_offline.py                    # 完整离线包
  python scripts/package_offline.py --core             # 仅核心包
  python scripts/package_offline.py --out /tmp/offline # 指定输出
  python scripts/package_offline.py --no-tests         # 不包含测试
        """
    )
    parser.add_argument("--core", action="store_true", help="仅打包核心功能（最小包）")
    parser.add_argument("--out", type=Path, default=OUTPUT_DIR, help=f"输出目录 (默认: {OUTPUT_DIR})")
    parser.add_argument("--no-tests", action="store_true", help="不包含测试文件")
    parser.add_argument("--no-wheels", action="store_true", help="不下载 wheel 包")
    parser.add_argument("--no-pycache", action="store_true", help="排除 __pycache__")
    parser.add_argument("--dry-run", action="store_true", help="只打印计划，不执行")
    args = parser.parse_args()

    print("=" * 60)
    print("Matha 离线打包工具")
    print("=" * 60)
    log(f"Python: {get_python_version()}")
    log(f"平台: {get_platform()}")
    log(f"项目: {PROJECT_ROOT}")
    print()

    # 创建输出目录
    args.out.mkdir(parents=True, exist_ok=True)
    wheel_dir = args.out / "wheels"

    if args.dry_run:
        log("干运行模式 - 仅显示计划", indent=1)
        log(f"输出目录: {args.out}", indent=1)
        log(f"核心包: {'是' if not args.core else '否'}", indent=1)
        log(f"测试文件: {'包含' if not args.no_tests else '排除'}", indent=1)
        log(f"wheel 包: {'下载' if not args.no_wheels else '跳过'}", indent=1)
        return

    # 1. 打包源码
    source_archive = create_source_archive(
        args.out,
        include_tests=not args.no_tests,
        include_pycache=not args.no_pycache
    )

    # 2. 下载 pip wheel 包
    wheels = []
    if not args.no_wheels:
        wheels = download_pip_wheels_all(wheel_dir)

    # 3. 打包 wheel 文件
    packages_archive = create_packages_archive(wheel_dir, args.out) if wheels else None

    # 4. 生成离线依赖清单
    req_file = create_offline_requirements(args.out)

    # 5. 生成部署脚本
    deploy_script = create_deploy_script(args.out)

    # 6. 生成使用说明
    readme = create_readme(args.out)

    # 7. 生成校验和
    checksums = create_checksums(args.out)

    # 汇总
    print()
    print("=" * 60)
    print("打包完成！")
    print("=" * 60)
    log(f"输出目录: {args.out}")
    log(f"源码归档: {source_archive.name if source_archive else 'N/A'}")
    log(f"Wheel 包: {len(wheels)} 个" if wheels else "Wheel 包: 未下载")
    log(f"包归档: {packages_archive.name if packages_archive else 'N/A'}")
    log(f"依赖清单: {req_file.name}")
    log(f"部署脚本: {deploy_script.name}")
    log(f"使用说明: {readme.name}")
    log(f"校验文件: {checksums.name}")
    print()
    log("离线部署步骤:")
    log("  1. 将整个 offline_package/ 目录拷贝到目标机器")
    log("  2. 在目标机器上运行: python deploy_offline.py")
    log("  3. 验证: python verify_offline.py")
    print()
    log("开始使用:")
    log("  matha run examples/demo.matha")
    log("  matha-cc compile demo.matha -o c")
    log("  python -m unittest discover -s tests -p test_*.py")


if __name__ == "__main__":
    main()
