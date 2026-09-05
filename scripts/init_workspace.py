# -*- coding: utf-8 -*-
"""初始化 Matha 工作空间 - 复制源码到 client/"""
import shutil
from pathlib import Path

MATHA_HOME = Path.home() / ".matha-home"
PROJECT_ROOT = Path(__file__).parent  # d:\trae
CLIENT_SRC = MATHA_HOME / "client" / "src"
CLIENT_DOCS = MATHA_HOME / "client" / "docs"
CLIENT_TESTS = MATHA_HOME / "client" / "tests"

def safe_copy(src: Path, dst: Path, only_files: bool = False):
    """安全复制：只复制文件，跳过 __pycache__ 和 .pyc"""
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            if dst.exists():
                shutil.rmtree(dst)
            for item in src.iterdir():
                if item.name == "__pycache__":
                    continue
                if item.name.endswith(".pyc"):
                    continue
                dest_item = dst / item.name
                if item.is_dir():
                    safe_copy(item, dest_item, only_files)
                elif only_files or not item.name.endswith(".pyc"):
                    shutil.copy2(item, dest_item)
        else:
            shutil.copy2(src, dst)

print(f"复制源码到 {CLIENT_SRC} ...")
src_dir = PROJECT_ROOT / "src"
if src_dir.exists():
    if CLIENT_SRC.exists():
        shutil.rmtree(CLIENT_SRC)
    for item in src_dir.iterdir():
        if item.name == "__pycache__":
            continue
        if item.name.endswith(".pyc"):
            continue
        dest = CLIENT_SRC / item.name
        if item.is_dir():
            shutil.copytree(item, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(item, dest)
    print(f"  ✓ src/ 已复制 ({sum(1 for _ in CLIENT_SRC.rglob('*.py'))} 个 Python 文件)")

print(f"复制测试到 {CLIENT_TESTS} ...")
CLIENT_TESTS.mkdir(parents=True, exist_ok=True)
for f in ["test_matha_growth.py", "test_unified_layers.py", "test_matha_compiler.py"]:
    src = PROJECT_ROOT / "tests" / f
    if src.exists():
        shutil.copy2(src, CLIENT_TESTS / f)
print(f"  ✓ {len(list(CLIENT_TESTS.glob('*.py')))} 个测试文件")

print(f"复制文档到 {CLIENT_DOCS} ...")
if CLIENT_DOCS.exists():
    shutil.rmtree(CLIENT_DOCS)
CLIENT_DOCS.mkdir(parents=True, exist_ok=True)
docs_dir = PROJECT_ROOT / "docs"
if docs_dir.exists():
    for f in docs_dir.glob("*.md"):
        shutil.copy2(f, CLIENT_DOCS / f.name)
print(f"  ✓ {len(list(CLIENT_DOCS.glob('*.md')))} 个文档")

print("\n安装完成！")
print(f"工作空间: {MATHA_HOME}")
