# tree-sitter C 扩展模块构建脚本
from __future__ import annotations
from setuptools import setup, Extension
from setuptools.command.build_ext import build_ext
import os


class OptionalBuildExt(build_ext):
    """可选的 C 扩展构建 — 失败时降级为纯 Python。"""

    def build_extension(self, ext):
        try:
            super().build_extension(ext)
        except Exception as e:
            print(f"[WARN] C 扩展构建失败，降级为纯 Python 解析器: {e}")


ext_modules = []
try:
    ext_modules = [
        Extension(
            "matha_auth._tree_sitter_ext",
            sources=["src/tree_sitter_ext.c"],
            define_macros=[("Py_LIMITED_API", "0x03090000")],
            extra_compile_args=["-O2"],
        ),
    ]
except Exception:
    pass

setup(
    name="matha-auth-tree-sitter-ext",
    version="0.1.0",
    ext_modules=ext_modules,
    cmdclass={"build_ext": OptionalBuildExt} if ext_modules else {},
    python_requires=">=3.9",
)
