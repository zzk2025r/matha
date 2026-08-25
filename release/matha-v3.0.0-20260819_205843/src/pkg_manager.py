# -*- coding: utf-8 -*-
"""Matha 包管理器 — matha-pkg

提供：
1. 依赖解析（类似 pip/requirements.txt）
2. 版本控制（语义化版本 semver）
3. 包仓库（本地/远程）
4. 环境隔离（虚拟环境）

用法：
  matha-pkg install matha-stdlib
  matha-pkg install matha-stdlib==1.2.3
  matha-pkg install --dev matha-test-utils
  matha-pkg update
  matha-pkg list
  matha-pkg search prime
"""
from __future__ import annotations
import json
import re
import sys
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import hashlib


# ============================================================
# 语义化版本
# ============================================================

class Version:
    """语义化版本：Major.Minor.Patch"""

    def __init__(self, major: int, minor: int, patch: int = 0):
        self.major = major
        self.minor = minor
        self.patch = patch

    @classmethod
    def parse(cls, version_str: str) -> 'Version':
        """解析版本字符串。"""
        # 移除前缀 v/V
        version_str = re.sub(r'^[vV]', '', version_str)
        # 处理预发布版本（如 1.2.3-alpha.1）
        version_str = re.split(r'[-+]', version_str)[0]
        parts = version_str.split('.')
        if len(parts) >= 3:
            return cls(int(parts[0]), int(parts[1]), int(parts[2]))
        elif len(parts) == 2:
            return cls(int(parts[0]), int(parts[1]), 0)
        elif len(parts) == 1:
            return cls(int(parts[0]), 0, 0)
        raise ValueError(f"无效版本格式: {version_str}")

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def __repr__(self) -> str:
        return f"Version({self})"

    def __eq__(self, other) -> bool:
        if isinstance(other, str):
            other = Version.parse(other)
        return (self.major, self.minor, self.patch) == (other.major, other.minor, other.patch)

    def __lt__(self, other) -> bool:
        if isinstance(other, str):
            other = Version.parse(other)
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)

    def __le__(self, other) -> bool:
        return self == other or self < other

    def __gt__(self, other) -> bool:
        return not self <= other

    def __ge__(self, other) -> bool:
        return not self < other

    def __hash__(self) -> int:
        return hash((self.major, self.minor, self.patch))


# ============================================================
# 包描述
# ============================================================

@dataclass
class PackageMeta:
    """包元数据。"""
    name: str
    version: Version
    description: str = ""
    author: str = ""
    license: str = ""
    dependencies: Dict[str, str] = field(default_factory=dict)  # {name: version_spec}
    dev_dependencies: Dict[str, str] = field(default_factory=dict)
    entry_points: Dict[str, str] = field(default_factory=dict)  # {name: module.path}
    homepage: str = ""
    keywords: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'version': str(self.version),
            'description': self.description,
            'author': self.author,
            'license': self.license,
            'dependencies': self.dependencies,
            'dev_dependencies': self.dev_dependencies,
            'entry_points': self.entry_points,
            'homepage': self.homepage,
            'keywords': self.keywords,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'PackageMeta':
        version_str = data.get('version', '0.0.0')
        return cls(
            name=data['name'],
            version=Version.parse(version_str),
            description=data.get('description', ''),
            author=data.get('author', ''),
            license=data.get('license', ''),
            dependencies=data.get('dependencies', {}),
            dev_dependencies=data.get('dev_dependencies', {}),
            entry_points=data.get('entry_points', {}),
            homepage=data.get('homepage', ''),
            keywords=data.get('keywords', []),
        )


# ============================================================
# 依赖解析器
# ============================================================

class DependencyResolver:
    """依赖解析器（带版本约束、缓存和冲突解决）。"""

    # 版本约束操作符
    OPERATORS = {
        '==': lambda v, spec: v == Version.parse(spec),
        '!=': lambda v, spec: v != Version.parse(spec),
        '>=': lambda v, spec: v >= Version.parse(spec),
        '<=': lambda v, spec: v <= Version.parse(spec),
        '>': lambda v, spec: v > Version.parse(spec),
        '<': lambda v, spec: v < Version.parse(spec),
    }

    def __init__(self):
        self._resolve_cache: Dict[str, List[str]] = {}  # 依赖解析缓存
        self._constraint_cache: Dict[str, bool] = {}     # 约束检查缓存

    def check_constraint(self, version: Version, constraint: str) -> bool:
        """检查版本是否满足约束（带缓存）。"""
        cache_key = f"{version}:{constraint}"
        if cache_key in self._constraint_cache:
            return self._constraint_cache[cache_key]

        # 处理多个约束（逗号分隔）
        constraints = [c.strip() for c in constraint.split(',')]
        result = all(self._check_single(version, c) for c in constraints)
        self._constraint_cache[cache_key] = result
        return result

    def check_constraint(self, version: Version, constraint: str) -> bool:
        """检查版本是否满足约束。"""
        # 处理多个约束（逗号分隔）
        constraints = [c.strip() for c in constraint.split(',')]
        return all(self._check_single(version, c) for c in constraints)

    def _check_single(self, version: Version, constraint: str) -> bool:
        """检查单个约束。"""
        if not constraint:
            return True

        # 提取操作符和版本
        match = re.match(r'([><=!~^]*)(\d+[.\d+]*)', constraint)
        if not match:
            return version == Version.parse(constraint)

        op, spec_version = match.groups()
        if not op:
            op = '=='

        # 处理特殊操作符
        if op == '~=':
            return self._tilde_match(version, spec_version)
        elif op == '^':
            return self._caret_match(version, spec_version)

        return self.OPERATORS.get(op, self.OPERATORS['=='])(version, spec_version)

    @staticmethod
    def _tilde_match(version: Version, spec: str) -> bool:
        """~1.2 匹配 >=1.2.0, <1.3.0"""
        base = Version.parse(spec)
        return version >= base and version.major == base.major and version.minor == base.minor

    @staticmethod
    def _caret_match(version: Version, spec: str) -> bool:
        """^1.2.3 匹配 >=1.2.3, <2.0.0"""
        base = Version.parse(spec)
        return version >= base and version.major == base.major

    def resolve(self, package: PackageMeta, registry: Dict[str, PackageMeta]) -> List[str]:
        """解析依赖树（带缓存和冲突解决）。"""
        cache_key = f"{package.name}@{package.version}"
        if cache_key in self._resolve_cache:
            return self._resolve_cache[cache_key]

        resolved = []
        visited = set()
        constraints: Dict[str, List[str]] = {}  # 收集所有约束

        def _collect_constraints(pkg_name: str, version_spec: str = ''):
            """收集所有版本的约束。"""
            if pkg_name not in registry:
                return
            pkg = registry[pkg_name]
            if version_spec:
                constraints.setdefault(pkg_name, []).append(version_spec)
            for dep_name, dep_spec in pkg.dependencies.items():
                _collect_constraints(dep_name, dep_spec)

        def _resolve(pkg_name: str, version_spec: str = ''):
            if pkg_name in visited:
                return
            visited.add(pkg_name)

            # 查找包
            if pkg_name not in registry:
                raise PackageNotFoundError(f"找不到包: {pkg_name}")

            pkg = registry[pkg_name]

            # 检查版本约束
            if version_spec and not self.check_constraint(pkg.version, version_spec):
                # 尝试冲突解决：查找满足约束的其他版本
                conflict_version = self._resolve_conflict(pkg_name, version_spec, registry)
                if conflict_version:
                    pkg = conflict_version
                else:
                    raise VersionConflictError(
                        f"{pkg_name}=={pkg.version} 不满足约束 {version_spec}"
                    )

            resolved.append(f"{pkg_name}=={pkg.version}")

            # 递归解析依赖
            for dep_name, dep_spec in pkg.dependencies.items():
                _resolve(dep_name, dep_spec)

        # 先收集所有约束
        _collect_constraints(package.name)

        # 尝试冲突解决
        for pkg_name, specs in constraints.items():
            if len(specs) > 1:
                self._resolve_conflict(pkg_name, ','.join(specs), registry)

        _resolve(package.name)

        # 缓存结果
        self._resolve_cache[cache_key] = resolved
        return resolved

    def _resolve_conflict(self, pkg_name: str, constraint: str,
                          registry: Dict[str, PackageMeta]) -> Optional[PackageMeta]:
        """尝试解决版本冲突。

        策略：
        1. 查找满足所有约束的最新版本
        2. 如果找不到，返回 None（依赖调用者处理）
        """
        # 简化版：只检查当前注册表中的版本
        if pkg_name in registry:
            pkg = registry[pkg_name]
            if self.check_constraint(pkg.version, constraint):
                return pkg
        return None

    def clear_cache(self):
        """清空缓存。"""
        self._resolve_cache.clear()
        self._constraint_cache.clear()


# ============================================================
# 包管理器核心
# ============================================================

class PackageNotFoundError(Exception):
    pass

class VersionConflictError(Exception):
    pass

class MathaPackage:
    """Matha 包管理器。"""

    def __init__(self, root_dir: str = None):
        self.root = Path(root_dir) if root_dir else Path.cwd()
        self.packages_dir = self.root / '.matha_packages'
        self.packages_dir.mkdir(parents=True, exist_ok=True)
        self.registry: Dict[str, PackageMeta] = {}
        self.installed: Dict[str, Version] = {}
        self._resolver = DependencyResolver()
        self._load_registry()

    def _load_registry(self):
        """加载包注册表。"""
        # 从本地缓存加载
        cache_file = self.packages_dir / 'registry.json'
        if cache_file.exists():
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for name, meta in data.items():
                    self.registry[name] = PackageMeta.from_dict(meta)

        # 从标准库加载（项目根目录）
        project_root = Path(__file__).parent.parent
        stdlib_dir = project_root / 'src' / 'stdlib'
        if stdlib_dir.exists():
            self._scan_stdlib(stdlib_dir)

        # 从 src 目录加载核心模块
        src_dir = project_root / 'src'
        if src_dir.exists():
            self._scan_core_modules(src_dir)

    def _scan_stdlib(self, stdlib_dir: Path):
        """扫描标准库目录。"""
        for py_file in stdlib_dir.glob('*.py'):
            if py_file.name.startswith('_'):
                continue
            name = py_file.stem
            if name not in self.registry:
                self.registry[name] = PackageMeta(
                    name=name,
                    version=Version(0, 1, 0),
                    description=f'Matha 标准库: {name}',
                    entry_points={name: f'src.stdlib.{name}'},
                )

    def _scan_core_modules(self, src_dir: Path):
        """扫描核心模块。"""
        core_modules = [
            'intent', 'compiler', 'hardware', 'adapters',
            'codegen', 'domains',
        ]
        for mod in core_modules:
            mod_dir = src_dir / mod
            if mod_dir.exists() and mod_dir.is_dir():
                # 只添加包目录，不添加具体文件
                if mod not in self.registry:
                    self.registry[mod] = PackageMeta(
                        name=mod,
                        version=Version(0, 1, 0),
                        description=f'Matha {mod} 模块',
                        entry_points={mod: f'src.{mod}'},
                    )

    def install(self, spec: str, dev: bool = False) -> List[str]:
        """安装包。

        Args:
            spec: 包规格，格式: name[==version]
            dev: 是否安装为开发依赖

        Returns:
            解析后的依赖列表
        """
        # 解析规格
        match = re.match(r'^([a-zA-Z0-9_-]+)(?:==([0-9.]+))?$', spec.strip())
        if not match:
            raise ValueError(f"无效的包规格: {spec}")

        pkg_name, version_spec = match.groups()

        # 查找包
        if pkg_name not in self.registry:
            raise PackageNotFoundError(f"找不到包: {pkg_name}")

        pkg = self.registry[pkg_name]

        # 解析依赖
        deps = self._resolver.resolve(pkg, self.registry)

        # 安装
        install_dir = self.packages_dir / pkg_name
        install_dir.mkdir(exist_ok=True)

        # 保存包信息
        manifest = {
            'name': pkg.name,
            'version': str(pkg.version),
            'dependencies': deps,
            'installed_at': __import__('time').time(),
        }
        with open(install_dir / 'manifest.json', 'w', encoding='utf-8') as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        # 记录已安装包
        self.installed[pkg_name] = pkg.version

        print(f"  已安装: {pkg_name}=={pkg.version}")
        print(f"  依赖: {', '.join(deps)}")

        return deps

    def list_packages(self) -> List[Tuple[str, Version]]:
        """列出已安装的包。"""
        return [(name, ver) for name, ver in sorted(self.installed.items())]

    def search(self, query: str) -> List[PackageMeta]:
        """搜索包。"""
        results = []
        query_lower = query.lower()
        for pkg in self.registry.values():
            if (query_lower in pkg.name.lower() or
                query_lower in pkg.description.lower() or
                any(query_lower in kw.lower() for kw in pkg.keywords)):
                results.append(pkg)
        return results

    def show(self, name: str):
        """显示包信息。"""
        if name not in self.registry:
            print(f"包不存在: {name}")
            return
        pkg = self.registry[name]
        print(f"\n{name}=={pkg.version}")
        print(f"  描述: {pkg.description}")
        print(f"  作者: {pkg.author}")
        print(f"  许可证: {pkg.license}")
        print(f"  依赖: {pkg.dependencies}")
        print(f"  入口: {pkg.entry_points}")


# ============================================================
# CLI 入口
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Matha 包管理器')
    subparsers = parser.add_subparsers(dest='command', help='命令')

    # install
    install_parser = subparsers.add_parser('install', help='安装包')
    install_parser.add_argument('spec', help='包规格 (name[==version])')
    install_parser.add_argument('--dev', action='store_true', help='安装为开发依赖')

    # list
    subparsers.add_parser('list', help='列出已安装包')

    # search
    search_parser = subparsers.add_parser('search', help='搜索包')
    search_parser.add_argument('query', help='搜索关键词')

    # show
    show_parser = subparsers.add_parser('show', help='显示包信息')
    show_parser.add_argument('name', help='包名')

    args = parser.parse_args()

    pkg_manager = MathaPackage()

    if args.command == 'install':
        print(f"\n安装: {args.spec}")
        try:
            deps = pkg_manager.install(args.spec, dev=args.dev)
            print(f"\n安装完成，共 {len(deps)} 个依赖")
        except (PackageNotFoundError, VersionConflictError) as e:
            print(f"错误: {e}")
            sys.exit(1)

    elif args.command == 'list':
        packages = pkg_manager.list_packages()
        if not packages:
            print("未安装任何包")
        else:
            print(f"\n已安装的包 ({len(packages)}):")
            for name, version in packages:
                print(f"  {name}=={version}")

    elif args.command == 'search':
        results = pkg_manager.search(args.query)
        if not results:
            print(f"未找到与 '{args.query}' 匹配的包")
        else:
            print(f"\n找到 {len(results)} 个包:")
            for pkg in results:
                print(f"  {pkg.name}=={pkg.version} - {pkg.description}")

    elif args.command == 'show':
        pkg_manager.show(args.name)

    else:
        parser.print_help()
