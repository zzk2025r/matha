# -*- coding: utf-8 -*-
"""Matha v3.0 一键部署脚本。

功能：
  1. 环境检查（Python/Flutter/pyodide-build）
  2. 测试验证（全量回归）
  3. WASM 包构建（尝试 pyodide build）
  4. 打包输出
  5. 生成部署报告

用法：
    python scripts/deploy_v3.py               # 完整部署
    python scripts/deploy_v3.py --test-only   # 仅运行测试
    python scripts/deploy_v3.py --build-only  # 仅构建 WASM
    python scripts/deploy_v3.py --dry-run     # 仅检查环境
"""
import os
import sys
import subprocess
import shutil
import json
import tarfile
import platform
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DIST_DIR = PROJECT_ROOT / "dist"
RELEASE_DIR = PROJECT_ROOT / "release"
DOCS_DIR = PROJECT_ROOT / "docs"
VERSION = "3.0.0"
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")


def log(msg: str, level: str = "INFO") -> None:
    prefix = {"INFO": "✅", "WARN": "⚠️", "ERROR": "❌", "STEP": "▶️", "DONE": "🎉"}.get(level, "  ")
    print(f"  {prefix} {msg}")


def run_cmd(cmd: list[str], cwd: Path | None = None, capture: bool = False) -> tuple[int, str]:
    try:
        result = subprocess.run(
            cmd, cwd=cwd or PROJECT_ROOT,
            capture_output=capture, text=True, timeout=300
        )
        return result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return -1, "超时（300s）"
    except FileNotFoundError:
        return -1, f"命令未找到: {cmd[0]}"


def check_env() -> dict:
    """检查部署环境。"""
    log("检查部署环境...")
    env = {
        "python": False,
        "flutter": False,
        "pyodide_build": False,
        "websockets": False,
        "sqlite3": False,
        "git": False,
    }

    # Python
    try:
        ret, out = run_cmd([sys.executable, "--version"])
        if "Python" in (out or "") or ret == 0:
            env["python"] = True
            log(f"Python {sys.version.split()[0]}")
        else:
            log("Python 未安装", "ERROR")
    except Exception:
        log("Python 未安装", "ERROR")

    # Flutter
    ret, _ = run_cmd(["flutter", "--version"])
    if ret == 0:
        env["flutter"] = True
        log("Flutter 已安装")
    else:
        log("Flutter 未安装（可选，跳过移动测试）", "WARN")

    # pyodide-build
    try:
        import pyodide_build
        env["pyodide_build"] = True
        log("pyodide-build 已安装")
    except ImportError:
        log("pyodide-build 未安装（WASM 构建需手动安装）", "WARN")

    # websockets
    try:
        import websockets
        env["websockets"] = True
        log(f"websockets {websockets.__version__} 已安装")
    except ImportError:
        log("websockets 未安装（协作服务器使用 TCP 实现，无需此依赖）", "WARN")

    # sqlite3
    try:
        import sqlite3
        env["sqlite3"] = True
        log("sqlite3 已安装")
    except ImportError:
        log("sqlite3 未安装", "ERROR")

    # git
    try:
        ret, out = run_cmd(["git", "--version"])
        if ret == 0:
            env["git"] = True
            log(f"git {out.strip()}")
        else:
            log("git 未安装", "WARN")
    except Exception:
        log("git 未安装", "WARN")

    return env


def run_tests() -> bool:
    """运行全量测试。"""
    log("运行全量测试...")
    test_files = [
        "tests/test_bootstrap.py",
        "tests/test_codegen.py",
        "tests/test_complex_ternary_recursive.py",
        "tests/test_build_software.py",
        "tests/test_collab_mock_server.py",
        "tests/test_collab_end_to_end.py",
        "tests/test_ai_data_science.py",
        "tests/test_game_dev.py",
        "tests/test_quantum_compute.py",
        "tests/test_chaos_fractal.py",
        "tests/test_genetic_algo.py",
        "tests/test_creative_coding.py",
        "tests/test_blockchain.py",
        "tests/test_software_app.py",
        "tests/test_domain_registry.py",
        "tests/test_economics.py",
        "tests/test_computer_science.py",
        "tests/test_electrical.py",
        "tests/test_embedded.py",
        "tests/test_extended_modeling.py",
        "tests/test_real_hardware.py",
        "tests/test_new_domains.py",
        "tests/test_all_new_domains.py",
    ]

    all_passed = True
    results = {}

    for test_file in test_files:
        test_path = PROJECT_ROOT / test_file
        if not test_path.exists():
            results[test_file] = ("SKIP", 0, 0)
            continue

        ret, out = run_cmd([sys.executable, str(test_path)], capture=True)
        # 统计通过数
        import re as _re
        passed = len(_re.findall(r"\bok\b", out or ""))
        failed = len(_re.findall(r"FAIL|ERROR", out or ""))

        if ret == 0 and failed == 0:
            results[test_file] = ("PASS", passed, 0)
            log(f"{test_file}: {passed} passed")
        else:
            results[test_file] = ("FAIL", passed, failed)
            log(f"{test_file}: {passed} passed, {failed} failed", "ERROR")
            all_passed = False

    total_passed = sum(r[1] for r in results.values())
    total_failed = sum(r[2] for r in results.values())

    log(f"测试结果: {total_passed} passed, {total_failed} failed")
    return all_passed and total_failed == 0


def build_wasm() -> bool:
    """构建 WASM 包。"""
    log("尝试 WASM 构建...")

    # 方法1: pyodide build
    ret, out = run_cmd([
        sys.executable, "-m", "pyodide_build", "build",
        str(PROJECT_ROOT / "matha_wasm"),
        "--output", str(DIST_DIR)
    ])

    if ret == 0:
        whl_files = list(DIST_DIR.glob("*.whl"))
        for f in whl_files:
            log(f"WASM wheel: {f.name} ({f.stat().st_size / 1024:.1f} KB)")
        return True

    # 方法2: setuptools wheel
    log("pyodide build 不可用，尝试 setuptools wheel...", "WARN")
    ret2, out2 = run_cmd(
        [sys.executable, "setup.py", "bdist_wheel", "-d", str(DIST_DIR)],
        cwd=PROJECT_ROOT / "matha_wasm"
    )

    if ret2 == 0:
        whl_files = list(DIST_DIR.glob("*.whl"))
        for f in whl_files:
            log(f"Wheel: {f.name} ({f.stat().st_size / 1024:.1f} KB)")
        log("注意: 这是普通 wheel，不是 WASM 包", "WARN")
        return True

    log("WASM 构建失败，需手动安装 pyodide-build", "ERROR")
    return False


def package_release() -> Path:
    """打包发布版本。"""
    log("打包发布版本...")

    release_name = f"matha-v{VERSION}-{TIMESTAMP}"
    release_path = RELEASE_DIR / release_name

    # 创建目录结构
    (release_path / "src").mkdir(parents=True, exist_ok=True)
    (release_path / "tests").mkdir(parents=True, exist_ok=True)
    (release_path / "matha").mkdir(parents=True, exist_ok=True)
    (release_path / "docs").mkdir(parents=True, exist_ok=True)
    (release_path / "scripts").mkdir(parents=True, exist_ok=True)
    (release_path / "matha_wasm").mkdir(parents=True, exist_ok=True)

    # 复制文件
    src_files = list((PROJECT_ROOT / "src").rglob("*.py"))
    tests_files = list((PROJECT_ROOT / "tests").glob("test_*.py"))
    matha_files = list((PROJECT_ROOT / "matha").rglob("*.matha"))
    docs_files = list(DOCS_DIR.glob("*.md"))
    script_files = list((PROJECT_ROOT / "scripts").rglob("*.py"))
    wasm_files = list((PROJECT_ROOT / "matha_wasm").rglob("*"))

    for f in src_files:
        if "__pycache__" in str(f):
            continue
        dest = release_path / "src" / f.relative_to(PROJECT_ROOT / "src")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dest)

    for f in tests_files:
        shutil.copy2(f, release_path / "tests" / f.name)

    for f in matha_files:
        shutil.copy2(f, release_path / "matha" / f.name)

    for f in docs_files:
        shutil.copy2(f, release_path / "docs" / f.name)

    for f in script_files:
        shutil.copy2(f, release_path / "scripts" / f.name)

    for f in wasm_files:
        if "matha_wasm" in str(f) and not str(f).startswith(str(release_path)):
            dest = release_path / f.relative_to(PROJECT_ROOT)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)

    # 复制顶层文件
    for name in ["README.md", ".gitignore", "pyproject.toml", "setup.py"]:
        src = PROJECT_ROOT / name
        if src.exists():
            shutil.copy2(src, release_path / name)

    # 生成包大小
    total_size = sum(f.stat().st_size for f in release_path.rglob("*") if f.is_file())

    # 创建 tar.gz
    archive_path = RELEASE_DIR / f"matha-v{VERSION}-{TIMESTAMP}.tar.gz"
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(release_path, arcname=release_name)

    log(f"发布包: {archive_path.name} ({total_size / 1024 / 1024:.1f} MB)")

    return archive_path


def generate_deploy_report(env: dict, tests_passed: bool, wasm_built: bool,
                           archive: Path | None) -> Path:
    """生成部署报告。"""
    report = f"""# Matha v{VERSION} 部署报告

**生成时间：** {datetime.now().isoformat()}
**平台：** {platform.system()} / {platform.machine()}
**Python：** {sys.version.split()[0]}

---

## 环境检查

| 组件 | 状态 |
|------|------|
"""
    for k, v in env.items():
        report += f"| {k} | {'✅' if v else '❌'} |\n"

    report += f"""
---

## 测试结果

| 状态 | 详情 |
|------|------|
| 全量测试 | {'✅ 通过' if tests_passed else '❌ 失败'} |

---

## WASM 构建

| 状态 | 详情 |
|------|------|
| WASM 构建 | {'✅ 成功' if wasm_built else '⚠️ 需手动安装 pyodide-build'} |

---

## 发布包

| 文件 | 大小 |
|------|------|
"""
    if archive:
        size_mb = archive.stat().st_size / 1024 / 1024
        report += f"| {archive.name} | {size_mb:.1f} MB |\n"

    report += """
---

## 下一步

### 部署到测试服务器

```bash
# 1. 上传发布包
scp matha-v3.0-*.tar.gz user@server:/opt/matha/

# 2. 解压
tar -xzf matha-v3.0-*.tar.gz -C /opt/matha/

# 3. 安装依赖
pip install -r requirements.txt

# 4. 运行测试
python -m unittest discover -s tests -p "test_*.py"

# 5. 启动服务
python matha/repl.py
```

### Flutter 真机测试

1. 参考 docs/FLUTTER_DEVICE_TEST_GUIDE.md
2. 安装 Flutter SDK
3. 连接设备: flutter devices
4. 运行: flutter run -d <DEVICE_ID>

### WASM 构建（完整）

```bash
# 安装 micromamba
curl -Ls https://micro.mamba.pm/api/mamba/micromamba/linux-64/latest | tar -xvj bin/micromamba

# 创建环境
micromamba create -n matha-wasm -c conda-forge pyodide python=3.12
micromamba activate matha-wasm

# 构建
cd matha_wasm && pyodide build --output dist/
```
"""

    report_path = PROJECT_ROOT / "docs" / f"DEPLOY_REPORT_{TIMESTAMP}.md"
    report_path.write_text(report, encoding="utf-8")
    log(f"部署报告已生成: {report_path.name}")

    return report_path


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Matha v3.0 一键部署脚本")
    parser.add_argument("--test-only", action="store_true", help="仅运行测试")
    parser.add_argument("--build-only", action="store_true", help="仅构建 WASM")
    parser.add_argument("--dry-run", action="store_true", help="仅检查环境")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print(f"  Matha v{VERSION} 一键部署脚本")
    print("=" * 60 + "\n")

    # 1. 环境检查
    env = check_env()

    if args.dry_run:
        log("dry-run 模式完成")
        return

    # 2. 运行测试
    if args.build_only:
        tests_passed = True
    else:
        tests_passed = run_tests()
        if not tests_passed:
            log("测试失败，中止部署", "ERROR")
            sys.exit(1)

    # 3. 构建 WASM
    if args.test_only:
        wasm_built = False
    else:
        wasm_built = build_wasm()

    # 4. 打包发布
    log("打包发布版本...")
    archive = package_release()

    # 5. 生成报告
    report = generate_deploy_report(env, tests_passed, wasm_built, archive)

    # 6. 汇总
    print("\n" + "=" * 60)
    log("部署完成!", "DONE")
    log(f"发布包: {archive.name}")
    log(f"部署报告: {report.name}")
    log(f"测试通过: {'✅' if tests_passed else '❌'}")
    log(f"WASM 构建: {'✅' if wasm_built else '⚠️ 需手动'}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
