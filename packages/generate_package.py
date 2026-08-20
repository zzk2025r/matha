# 将 src/auth 中的模块复制为包内容
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).parent.parent
PKG = ROOT / "packages" / "matha_auth"
SRC = ROOT / "src" / "auth"

def copy_module(src_file: str, dst_name: str | None = None):
    src = SRC / src_file
    if not src.exists():
        print(f"  SKIP: {src_file} not found")
        return
    dst_name = dst_name or src_file.replace("/", "_").replace(".py", ".py")
    dst = PKG / dst_name
    shutil.copy2(src, dst)
    print(f"  ✓ {src_file} → {dst_name}")

PKG.mkdir(parents=True, exist_ok=True)
# 清除旧文件
for f in PKG.glob("*.py"):
    f.unlink()

print("Generating matha-auth package...")
copy_module("__init__.py", "__init__.py")
copy_module("models.py")
copy_module("jwt.py")
copy_module("password.py")
copy_module("service.py")
copy_module("rbac.py")
copy_module("api.py")
copy_module("exceptions.py")
print("Done!")
