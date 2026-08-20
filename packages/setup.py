"""
matha-auth setup.py — 兼容 setuptools 的旧式构建入口

生产环境推荐使用 pyproject.toml + build 工具链；
此文件仅为 pip install -e . 和 twine upload 提供向后兼容。
"""
from __future__ import annotations
import os
from pathlib import Path

from setuptools import find_packages, setup

PKG_DIR = Path(__file__).parent / "matha_auth"
README = (Path(__file__).parent / "README.md").read_text(encoding="utf-8")
VERSION = {}
exec((PKG_DIR / "_version.py").read_text(encoding="utf-8"), VERSION)


setup(
    name="matha-auth",
    version=VERSION["__version__"],
    description="Matha 认证与 RBAC 权限管理系统",
    long_description=README,
    long_description_content_type="text/markdown",
    author=VERSION.get("__author__", "Matha Team"),
    author_email=VERSION.get("__email__", "matha@example.com"),
    license="MIT",
    keywords=["auth", "rbac", "jwt", "security", "authentication"],
    url="https://github.com/matha/matha-auth",

    packages=find_packages(where="."),
    package_dir={"": "."},
    include_package_data=True,

    python_requires=">=3.9",
    install_requires=[],
    extras_require={
        "dev": ["pytest>=7.0", "pytest-cov>=4.0", "black>=23.0", "mypy>=1.0"],
        "server": ["fastapi>=0.111.0", "uvicorn[standard]>=0.29.0", "gunicorn>=22.0"],
    },

    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
        "Topic :: Security",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    entry_points={
        "console_scripts": [
            "matha-auth=matha_auth.server:main",
        ],
    },
)
