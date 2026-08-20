"""发布 matha-auth 包到私有 PyPI 仓库"""
import subprocess
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).parent.parent / "packages"


def build_package():
    """构建源分发和 wheel。"""
    print("构建 matha-auth 包...")
    result = subprocess.run(
        [sys.executable, "setup.py", "sdist", "bdist_wheel"],
        cwd=PACKAGE_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"构建失败:\n{result.stderr}")
        sys.exit(1)
    print("构建成功!")


def upload_to_pypi(token: str | None = None):
    """上传到 PyPI 私有仓库。"""
    print("上传到 PyPI...")
    cmd = [sys.executable, "-m", "twine", "upload", "dist/*"]
    if token:
        cmd += ["--username", "__token__", "--password", token]
    result = subprocess.run(cmd, cwd=PACKAGE_DIR, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"上传失败:\n{result.stderr}")
        sys.exit(1)
    print("上传成功!")
    print("\n安装验证:")
    print(f"  pip install matha-auth")
    print(f"  python -c 'from matha_auth import SessionManager; print(\"OK\")'")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="发布 matha-auth 包")
    parser.add_argument("--token", help="PyPI API token")
    parser.add_argument("--skip-upload", action="store_true", help="仅构建不上传")
    args = parser.parse_args()

    build_package()
    if not args.skip_upload:
        upload_to_pypi(args.token)
