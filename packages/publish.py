"""
matha-auth PyPI 发布脚本（含自动版本号递增）

用法:
  python publish.py                  # patch 升级 (1.0.0 → 1.0.1)
  python publish.py minor            # minor 升级 (1.0.0 → 1.1.0)
  python publish.py major            # major 升级 (1.0.0 → 2.0.0)
  python publish.py --dry-run        # 只打印不执行

环境变量:
  PYPI_TOKEN   私有仓库 API Token
  PYPI_URL     私有仓库地址（默认 https://pypi.your-company.com/simple/）
"""
from __future__ import annotations
import argparse
import re
import subprocess
import sys
import textwrap
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent
VERSION_FILE = PKG_DIR / "matha_auth" / "_version.py"
PYPROJECT = PKG_DIR / "pyproject.toml"
SETUP_PY = PKG_DIR / "setup.py"
DIST_DIR = PKG_DIR / "dist"
SDist = subprocess  # noqa: N806 (compatibility)


# ── 版本号工具 ─────────────────────────────────────────────────────────────────

def read_version() -> str:
    """从 _version.py 读取当前版本号。"""
    content = VERSION_FILE.read_text(encoding="utf-8")
    m = re.search(r'__version__\s*=\s*"([^"]+)"', content)
    if not m:
        raise RuntimeError(f"无法在 {VERSION_FILE} 中找到版本号")
    return m.group(1)


def parse_version(ver: str) -> tuple[int, int, int]:
    """'1.2.3' → (1, 2, 3)。"""
    parts = ver.strip().split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError(f"版本号格式错误: {ver}")
    return int(parts[0]), int(parts[1]), int(parts[2])


def bump_version(ver: str, level: str) -> str:
    """递增版本号并返回新字符串。"""
    major, minor, patch = parse_version(ver)
    if level == "major":
        major, minor, patch = major + 1, 0, 0
    elif level == "minor":
        minor += 1
        patch = 0
    else:  # patch
        patch += 1
    return f"{major}.{minor}.{patch}"


def write_version(ver: str) -> None:
    """更新 _version.py、pyproject.toml、setup.py 三处版本号。"""
    # _version.py
    content = VERSION_FILE.read_text(encoding="utf-8")
    VERSION_FILE.write_text(
        re.sub(r'(__version__\s*=\s*)".*"', rf'\g<1>"{ver}"', content),
        encoding="utf-8",
    )
    print(f"  [version] _version.py → {ver}")

    # pyproject.toml
    content = PYPROJECT.read_text(encoding="utf-8")
    if 'version = "' in content:
        content = re.sub(r'version\s*=\s*"[^"]*"', f'version = "{ver}"', content)
        PYPROJECT.write_text(content, encoding="utf-8")
        print(f"  [version] pyproject.toml → {ver}")

    # setup.py
    content = SETUP_PY.read_text(encoding="utf-8")
    if 'version=VERSION["__version__"]' in content:
        # setup.py 从 _version.py 读取，无需额外修改
        pass
    print(f"  [version] setup.py (自动从 _version.py 读取)")


# ── Git 操作 ──────────────────────────────────────────────────────────────────

def git_commit(ver: str) -> None:
    subprocess.run(
        ["git", "add", str(VERSION_FILE), str(PYPROJECT), str(SETUP_PY)],
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-m", f"chore: bump version {ver}"],
        check=True,
    )
    subprocess.run(
        ["git", "tag", f"v{ver}", "-m", f"Release v{ver}"],
        check=True,
    )
    print(f"  [git] committed + tagged v{ver}")


def git_push() -> None:
    subprocess.run(["git", "push"], check=True)
    subprocess.run(["git", "push", "--tags"], check=True)
    print("  [git] pushed to remote + tags")


# ── 构建 & 发布 ───────────────────────────────────────────────────────────────

def build_package() -> None:
    """使用 setuptools 构建 sdist + wheel。"""
    dist = subprocess.run(
        [sys.executable, "setup.py", "sdist", "bdist_wheel"],
        cwd=str(PKG_DIR),
        capture_output=True,
        text=True,
    )
    if dist.returncode != 0:
        print("BUILD FAILED:")
        print(dist.stderr)
        sys.exit(1)
    print(f"  [build] {DIST_DIR} 已生成")


def publish_package() -> None:
    """上传到私有 PyPI。"""
    token = __import__("os").environ.get("PYPI_TOKEN")
    url = __import__("os").environ.get(
        "PYPI_URL", "https://pypi.your-company.com/simple/"
    )
    if not token:
        print("⚠  未设置 PYPI_TOKEN，跳过发布（如需发布请设置环境变量）")
        return
    dist.run(
        [
            sys.executable, "-m", "twine", "upload",
            str(DIST_DIR / "*"),
            "--repository-url", url,
            "--skip-existing",
        ],
        env={**__import__("os").environ, "TWINE_USERNAME": "__token__", "TWINE_PASSWORD": token},
        check=True,
    )
    print(f"  [publish] 已上传至 {url}")


# ── 主流程 ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="matha-auth 发布脚本")
    parser.add_argument(
        "level", choices=["patch", "minor", "major"], nargs="?", default="patch",
        help="版本号递增级别（默认 patch）",
    )
    parser.add_argument("--dry-run", action="store_true", help="仅打印计划操作")
    args = parser.parse_args()

    print("=" * 60)
    print("  matha-auth 发布工具")
    print("=" * 60)

    current = read_version()
    new_ver = bump_version(current, args.level)
    print(f"\n  当前版本: {current}")
    print(f"  升级级别: {args.level}")
    print(f"  新版本  : {new_ver}")

    if args.dry_run:
        print("\n  [dry-run] 以下操作将被执行：")
        print(f"    1. 更新版本号 → {new_ver}")
        print(f"    2. git commit + tag v{new_ver}")
        print(f"    3. git push")
        print(f"    4. pip install build twine")
        print(f"    5. python setup.py sdist bdist_wheel")
        print(f"    6. twine upload")
        return

    # 1. 更新版本号
    print(f"\n[1/5] 更新版本号 {current} → {new_ver}")
    write_version(new_ver)

    # 2. Git 提交 & tag
    print(f"\n[2/5] Git commit + tag")
    git_commit(new_ver)

    # 3. 推送
    print(f"\n[3/5] Git push")
    git_push()

    # 4. 构建
    print(f"\n[4/5] 构建包")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "build", "twine"], check=True)
    build_package()

    # 5. 发布
    print(f"\n[5/5] 发布到 PyPI")
    publish_package()

    print("\n" + "=" * 60)
    print(f"  ✓ 发布完成！新版本: {new_ver}")
    print("=" * 60)


if __name__ == "__main__":
    main()
