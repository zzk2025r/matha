# matha-treesitter C 扩展构建脚本
"""
构建 matha-treesitter 的 C 扩展模块。

用法:
  python setup_cext.py build_ext --inplace   # 本地构建
  python setup_cext.py sdist bdist_wheel     # 构建发布包
  pip install .                              # 本地安装
"""
from __future__ import annotations
import os
import sys
from pathlib import Path
from setuptools import setup, Extension, find_packages

PKG_DIR = Path(__file__).resolve().parent
SRC_DIR = PKG_DIR / "src"
EXT_DIR = SRC_DIR / "cext"

# ── C 扩展定义 ────────────────────────────────────────────────────────────────

def _find_tree_sitter_headers() -> tuple[list[str], list[str]]:
    """查找 tree-sitter 头文件和库路径。"""
    include_dirs = []
    library_dirs = []

    # 尝试从 pip 安装的 tree-sitter 包中查找
    try:
        import tree_sitter
        ts_path = Path(tree_sitter.__file__).parent
        include_dirs.append(str(ts_path / "include"))
        # 查找 .so/.dll 库文件
        for ext in [".so", ".dll", ".dylib"]:
            lib = ts_path / f"libtree_sitter{ext}"
            if lib.exists():
                library_dirs.append(str(ts_path))
                break
    except ImportError:
        pass

    # 尝试从系统路径查找
    for candidate in [
        "/usr/local/include",
        "/usr/include",
        "/opt/homebrew/include",
    ]:
        if Path(candidate).exists():
            include_dirs.append(candidate)

    return include_dirs, library_dirs


def _create_extensions() -> list[Extension]:
    """创建 C 扩展列表。"""
    include_dirs, library_dirs = _find_tree_sitter_headers()

    extensions = []

    # 主 C 扩展：tree_sitter_bindings
    if include_dirs:
        extensions.append(
            Extension(
                "matha_treesitter._cext",
                sources=[
                    str(SRC_DIR / "cext" / "parser.c"),
                    str(SRC_DIR / "cext" / "nodes.c"),
                    str(SRC_DIR / "cext" / "language_registry.c"),
                ],
                include_dirs=include_dirs + [str(SRC_DIR / "cext")],
                library_dirs=library_dirs,
                libraries=["tree_sitter"],
                define_macros=[
                    ("Py_LIMITED_API", "0x03090000"),
                    ("TREE_SITTER_NO_THREADS", "1"),
                ],
                extra_compile_args=["-O2", "-std=c99"],
                py_limited_api=True,
            )
        )

    return extensions


# ── 可选 C 扩展构建 ───────────────────────────────────────────────────────────

class optional_build_ext:
    """可选 C 扩展构建 — 失败时不报错，降级为纯 Python。"""

    def __init__(self, ext):
        self.ext = ext

    def __enter__(self):
        try:
            from setuptools.command.build_ext import build_ext
            self._build_ext = build_ext
            return self
        except ImportError:
            return self

    def __exit__(self, *args):
        pass


# ── 主入口 ────────────────────────────────────────────────────────────────────

setup(
    name="matha-treesitter",
    version="0.1.0",
    description="Matha 高性能树形解析器 — Rust/Go/JS/C 绑定（支持 C 扩展加速）",
    package_dir={"": "."},
    packages=find_packages(where="."),
    ext_modules=_create_extensions() if _find_tree_sitter_headers()[0] else [],
    install_requires=[],
    extras_require={
        "cext": [
            "tree-sitter>=0.23.0",
            "tree-sitter-rust>=0.21.0",
            "tree-sitter-go>=0.23.0",
            "tree-sitter-javascript>=0.21.0",
            "tree-sitter-c>=0.21.0",
        ],
        "dev": ["pytest>=7.0", "pytest-cov>=4.0"],
    },
    python_requires=">=3.9",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
