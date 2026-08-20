# -*- coding: utf-8 -*-
"""matha-treesitter C 扩展构建脚本"""
from __future__ import annotations
import os
import sys
from pathlib import Path
from setuptools import setup, Extension, find_packages

PKG_DIR = Path(__file__).resolve().parent
SRC_DIR = PKG_DIR / "src"
EXT_DIR = SRC_DIR / "cext"

def _find_tree_sitter_headers() -> tuple[list[str], list[str]]:
    include_dirs = []
    library_dirs = []
    try:
        import tree_sitter
        ts_path = Path(tree_sitter.__file__).parent
        include_dirs.append(str(ts_path / "include"))
        for ext in [".so", ".dll", ".dylib"]:
            lib = ts_path / f"libtree_sitter{ext}"
            if lib.exists():
                library_dirs.append(str(ts_path))
                break
    except ImportError:
        pass
    for candidate in ["/usr/local/include", "/usr/include", "/opt/homebrew/include"]:
        if Path(candidate).exists():
            include_dirs.append(candidate)
    return include_dirs, library_dirs

def _create_extensions() -> list[Extension]:
    include_dirs, library_dirs = _find_tree_sitter_headers()
    if not include_dirs:
        return []
    return [
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
            define_macros=[("Py_LIMITED_API", "0x03090000"), ("TREE_SITTER_NO_THREADS", "1")],
            extra_compile_args=["-O2", "-std=c99"],
            py_limited_api=True,
        )
    ]

setup(
    name="matha-treesitter",
    version="1.0.0",
    description="Matha 高性能树形解析器 — Rust/Go/JS/C 绑定（支持 C 扩展加速）",
    package_dir={"": "."},
    packages=find_packages(where="."),
    ext_modules=_create_extensions(),
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
)
