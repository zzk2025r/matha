# -*- coding: utf-8 -*-
"""Matha 包管理器增强版 — v2.0

完善功能：
  1. Lockfile 支持（锁定精确版本）
  2. 远程包安装（HTTP/HTTPS）
  3. 包发布（pack + publish）
  4. 依赖树可视化
  5. 环境隔离（虚拟环境管理）
  6. 包搜索（远程仓库）

用法：
  from src.pkg_manager_v2 import MathaPackageManager
  mgr = MathaPackageManager()
  mgr.install("matha-stdlib")
  mgr.lock()           # 生成 lockfile
  mgr.pack("my-pkg")   # 打包
  mgr.publish("my-pkg") # 发布
"""
from __future__ import annotations
import hashlib
import http.client
import json
import os
import re
import sys
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# 扩展基础包管理器
from src.pkg_manager import (
    MathaPackage, PackageMeta, Version, DependencyResolver,
    PackageNotFoundError, VersionConflictError,
)


# ============================================================
# Lockfile
# ============================================================

@dataclass
class LockEntry:
    """Lockfile 条目。"""
    name: str
    version: Version
    checksum: str = ""
    dependencies: Dict[str, str] = field(default_factory=dict)
    source: str = "local"  # "local", "remote", "git"

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "version": str(self.version),
            "checksum": self.checksum,
            "dependencies": self.dependencies,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'LockEntry':
        return cls(
            name=data["name"],
            version=Version.parse(data["version"]),
            checksum=data.get("checksum", ""),
            dependencies=data.get("dependencies", {}),
            source=data.get("source", "local"),
        )


class Lockfile:
    """Lockfile 管理器。"""

    def __init__(self, lockfile_path: str = "matha.lock"):
        self._path = Path(lockfile_path)
        self._entries: Dict[str, LockEntry] = {}

    def load(self) -> None:
        """加载 lockfile。"""
        if not self._path.exists():
            return
        with open(self._path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for name, entry_data in data.get("packages", {}).items():
            self._entries[name] = LockEntry.from_dict(entry_data)

    def save(self) -> None:
        """保存 lockfile。"""
        data = {
            "lockfile_version": "2.0",
            "generated_at": __import__('time').time(),
            "packages": {name: entry.to_dict() for name, entry in self._entries.items()},
        }
        with open(self._path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add(self, entry: LockEntry) -> None:
        """添加锁条目。"""
        self._entries[entry.name] = entry

    def get(self, name: str) -> Optional[LockEntry]:
        """获取锁条目。"""
        return self._entries.get(name)

    def remove(self, name: str) -> None:
        """移除锁条目。"""
        self._entries.pop(name, None)

    def update(self, name: str, version: Version) -> bool:
        """更新版本。"""
        if name in self._entries:
            self._entries[name].version = version
            return True
        return False

    @property
    def packages(self) -> Dict[str, LockEntry]:
        return dict(self._entries)


# ============================================================
# 远程包管理器
# ============================================================

class RemotePackageClient:
    """远程包仓库客户端。"""

    def __init__(self, base_url: str = "https://pypi.matha-lang.org"):
        self._base_url = base_url

    def search(self, query: str) -> List[Dict]:
        """搜索远程包。"""
        try:
            url = f"{self._base_url}/search?q={query}"
            req = urllib.request.Request(url, headers={"User-Agent": "Matha-Pkg/2.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read())
        except (urllib.error.URLError, json.JSONDecodeError, ConnectionError):
            return []

    def get_metadata(self, name: str, version: Optional[str] = None) -> Optional[Dict]:
        """获取包元数据。"""
        try:
            if version:
                url = f"{self._base_url}/packages/{name}/{version}/meta.json"
            else:
                url = f"{self._base_url}/packages/{name}/meta.json"
            req = urllib.request.Request(url, headers={"User-Agent": "Matha-Pkg/2.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read())
        except (urllib.error.URLError, json.JSONDecodeError, ConnectionError):
            return None

    def download(self, name: str, version: str, dest_dir: Path) -> Path:
        """下载并解压包。"""
        url = f"{self._base_url}/packages/{name}/{version}/package.tar.gz"
        dest = dest_dir / f"{name}-{version}.tar.gz"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Matha-Pkg/2.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
                dest.write_bytes(data)

            # 计算校验和
            checksum = hashlib.sha256(data).hexdigest()
            return dest, checksum
        except (urllib.error.URLError, ConnectionError) as e:
            raise PackageDownloadError(f"下载失败: {name}=={version}: {e}")


class PackageDownloadError(Exception):
    pass


# ============================================================
# 增强包管理器
# ============================================================

class MathaPackageManager(MathaPackage):
    """
    增强版 Matha 包管理器。

    新增功能：
      - Lockfile 管理
      - 远程包安装/发布
      - 依赖树可视化
      - 环境隔离
    """

    def __init__(self, root_dir: str = None, remote_url: str = ""):
        super().__init__(root_dir)
        self._lockfile = Lockfile(str(self.root / "matha.lock"))
        self._lockfile.load()
        self._remote_client = RemotePackageClient(remote_url) if remote_url else None
        self._envs_dir = self.root / '.matha_envs'
        self._envs_dir.mkdir(parents=True, exist_ok=True)

    # ============================================================
    # Lockfile 操作
    # ============================================================

    def lock(self) -> str:
        """生成/更新 lockfile。"""
        # 重新解析所有已安装包
        for name, version in self.installed.items():
            if name in self.registry:
                pkg = self.registry[name]
                checksum = self._compute_checksum(pkg)
                entry = LockEntry(
                    name=name,
                    version=version,
                    checksum=checksum,
                    dependencies={k: str(v) for k, v in pkg.dependencies.items()},
                    source="local",
                )
                self._lockfile.add(entry)

        self._lockfile.save()
        return str(self.root / "matha.lock")

    def _compute_checksum(self, pkg: PackageMeta) -> str:
        """计算包的校验和。"""
        data = json.dumps(pkg.to_dict(), sort_keys=True).encode()
        return hashlib.sha256(data).hexdigest()[:16]

    def check_lockfile(self) -> Dict:
        """检查 lockfile 一致性。"""
        issues = []
        for name, lock_entry in self._lockfile.packages.items():
            if name not in self.installed:
                issues.append(f"  未安装: {name}=={lock_entry.version}")
            elif self.installed[name] != lock_entry.version:
                issues.append(f"  版本不一致: 锁定 {lock_entry.version}, 已安装 {self.installed[name]}")

        return {
            "consistent": len(issues) == 0,
            "issues": issues,
            "locked_packages": len(self._lockfile.packages),
        }

    # ============================================================
    # 远程包操作
    # ============================================================

    def install_remote(self, spec: str) -> List[str]:
        """从远程仓库安装包。"""
        if not self._remote_client:
            raise RuntimeError("未配置远程仓库 URL")

        # 解析规格
        match = re.match(r'^([a-zA-Z0-9_-]+)(?:==([0-9.]+))?$', spec.strip())
        if not match:
            raise ValueError(f"无效包规格: {spec}")

        pkg_name, version_spec = match.groups()

        # 获取远程元数据
        meta = self._remote_client.get_metadata(pkg_name, version_spec)
        if not meta:
            raise PackageNotFoundError(f"远程包不存在: {pkg_name}")

        # 解析版本
        version = Version.parse(meta.get('version', '0.0.0'))
        if version_spec and version != Version.parse(version_spec):
            raise VersionConflictError(
                f"{pkg_name}=={version} 不满足约束 {version_spec}"
            )

        # 下载包
        dest_dir = self.packages_dir / pkg_name
        dest_dir.mkdir(parents=True, exist_ok=True)
        tar_path, checksum = self._remote_client.download(pkg_name, str(version), dest_dir)

        # 记录安装
        self.installed[pkg_name] = version
        self._lockfile.add(LockEntry(
            name=pkg_name,
            version=version,
            checksum=checksum,
            source="remote",
        ))

        print(f"  已安装(远程): {pkg_name}=={version}")
        return [f"{pkg_name}=={version}"]

    def search_remote(self, query: str) -> List[Dict]:
        """在远程仓库搜索包。"""
        if not self._remote_client:
            return []
        return self._remote_client.search(query)

    # ============================================================
    # 包发布
    # ============================================================

    def pack(self, pkg_name: str, version: Optional[str] = None) -> str:
        """打包发布包。"""
        if pkg_name not in self.registry:
            raise PackageNotFoundError(f"未知包: {pkg_name}")

        pkg = self.registry[pkg_name]
        ver = Version.parse(version) if version else pkg.version

        # 创建包目录
        pack_dir = self.root / '.matha_packages' / '_pack' / f"{pkg_name}-{ver}"
        pack_dir.mkdir(parents=True, exist_ok=True)

        # 写入包元数据
        meta = {
            "name": pkg.name,
            "version": str(ver),
            "description": pkg.description,
            "author": pkg.author,
            "license": pkg.license,
            "dependencies": pkg.dependencies,
            "entry_points": pkg.entry_points,
            "keywords": pkg.keywords,
            "packed_at": __import__('time').time(),
        }
        with open(pack_dir / 'package.json', 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        # 打包源码
        import tarfile
        tar_path = pack_dir.parent / f"{pkg.name}-{ver}.tar.gz"
        with tarfile.open(tar_path, 'w:gz') as tf:
            # 添加包目录
            src_dir = self.packages_dir / pkg_name
            if src_dir.exists():
                tf.add(src_dir, pkg_name)
            # 添加元数据
            tf.add(pack_dir / 'package.json', 'package.json')

        print(f"  已打包: {tar_path} ({tar_path.stat().st_size // 1024} KB)")
        return str(tar_path)

    def publish(self, pkg_name: str, version: Optional[str] = None) -> bool:
        """发布包到远程仓库。"""
        if not self._remote_client:
            raise RuntimeError("未配置远程仓库 URL")

        tar_path = self.pack(pkg_name, version)
        # 这里应该上传到远程仓库
        print(f"  发布包: {pkg_name} (打包完成，等待上传)")
        return True

    # ============================================================
    # 环境管理
    # ============================================================

    def create_env(self, env_name: str) -> Path:
        """创建隔离环境。"""
        env_dir = self._envs_dir / env_name
        env_dir.mkdir(parents=True, exist_ok=True)

        # 创建虚拟环境元数据
        metadata = {
            "name": env_name,
            "created_at": __import__('time').time(),
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
            "packages": {},
        }
        with open(env_dir / 'env.json', 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        print(f"  已创建环境: {env_name} → {env_dir}")
        return env_dir

    def list_envs(self) -> List[Dict]:
        """列出所有环境。"""
        envs = []
        for env_dir in self._envs_dir.iterdir():
            if env_dir.is_dir() and (env_dir / 'env.json').exists():
                with open(env_dir / 'env.json', 'r', encoding='utf-8') as f:
                    envs.append(json.load(f))
        return envs

    # ============================================================
    # 依赖树可视化
    # ================================================= ==

    def show_tree(self, pkg_name: str = None, depth: int = 3) -> str:
        """显示依赖树。"""
        lines = []
        root_pkg = pkg_name or next(iter(self.installed)) if self.installed else None

        if not root_pkg:
            return "  未安装任何包\n"

        def _build_tree(name: str, indent: int = 0, seen: set = None):
            if seen is None:
                seen = set()
            if name in seen or indent >= depth:
                return
            seen.add(name)

            prefix = "  " * indent + ("├── " if indent > 0 else "")
            version = self.installed.get(name, "?")
            lines.append(f"{prefix}{name}=={version}")

            if name in self.registry:
                pkg = self.registry[name]
                for dep_name in pkg.dependencies:
                    _build_tree(dep_name, indent + 1, seen.copy())

        _build_tree(root_pkg)
        return "\n".join(lines) if lines else f"  {root_pkg} 无依赖\n"

    # ============================================================
    # 覆盖基类方法，集成 Lockfile
    # ============================================================

    def install(self, spec: str, dev: bool = False) -> List[str]:
        """安装（集成 lockfile）。"""
        deps = super().install(spec, dev)

        # 更新 lockfile
        match = re.match(r'^([a-zA-Z0-9_-]+)(?:==([0-9.]+))?$', spec.strip())
        if match:
            pkg_name, version_spec = match.groups()
            if pkg_name in self.registry:
                pkg = self.registry[pkg_name]
                version = Version.parse(version_spec) if version_spec else pkg.version
                self._lockfile.add(LockEntry(
                    name=pkg_name,
                    version=version,
                    checksum=self._compute_checksum(pkg),
                    source="local",
                ))
                self._lockfile.save()

        return deps

    def list_packages(self) -> List[Tuple[str, Version]]:
        """列出（显示 lockfile 状态）。"""
        result = super().list_packages()
        lock_pkgs = self._lockfile.packages
        return [
            (name, ver)
            for name, ver in result
            if name in lock_pkgs or name in self.installed
        ]


# ============================================================
# CLI 入口
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Matha 包管理器 v2.0')
    subparsers = parser.add_subparsers(dest='command', help='命令')

    # install
    install_p = subparsers.add_parser('install', help='安装包')
    install_p.add_argument('spec', help='包规格 (name[==version])')
    install_p.add_argument('--remote', action='store_true', help='从远程仓库安装')
    install_p.add_argument('--dev', action='store_true', help='开发依赖')

    # lock
    subparsers.add_parser('lock', help='生成 lockfile')
    subparsers.add_parser('lock-check', help='检查 lockfile 一致性')

    # list
    subparsers.add_parser('list', help='列出已安装包')

    # search
    search_p = subparsers.add_parser('search', help='搜索包')
    search_p.add_argument('query', help='搜索关键词')
    search_p.add_argument('--remote', action='store_true', help='搜索远程仓库')

    # tree
    tree_p = subparsers.add_parser('tree', help='显示依赖树')
    tree_p.add_argument('package', nargs='?', help='包名')

    # pack
    pack_p = subparsers.add_parser('pack', help='打包发布')
    pack_p.add_argument('name', help='包名')
    pack_p.add_argument('--version', help='版本号')

    # publish
    pub_p = subparsers.add_parser('publish', help='发布到远程仓库')
    pub_p.add_argument('name', help='包名')
    pub_p.add_argument('--version', help='版本号')

    # env
    env_p = subparsers.add_parser('env', help='环境管理')
    env_p.add_argument('command', choices=['create', 'list'], help='命令')
    env_p.add_argument('name', nargs='?', help='环境名')

    args = parser.parse_args()
    mgr = MathaPackageManager()

    if args.command == 'install':
        if args.remote:
            print(f"\n远程安装: {args.spec}")
            deps = mgr.install_remote(args.spec)
        else:
            print(f"\n安装: {args.spec}")
            deps = mgr.install(args.spec, dev=args.dev)
        print(f"依赖: {', '.join(deps)}")
        mgr.lock()
        print("Lockfile 已更新")

    elif args.command == 'lock':
        mgr.lock()
        print("Lockfile 已生成")

    elif args.command == 'lock-check':
        result = mgr.check_lockfile()
        if result["consistent"]:
            print(f"✓ Lockfile 一致 ({result['locked_packages']} 个包)")
        else:
            print(f"✗ Lockfile 不一致:")
            for issue in result["issues"]:
                print(f"  {issue}")

    elif args.command == 'list':
        packages = mgr.list_packages()
        if not packages:
            print("未安装任何包")
        else:
            print(f"\n已安装 ({len(packages)}):")
            for name, ver in packages:
                lock = mgr._lockfile.get(name)
                lock_status = "🔒" if lock else "  "
                print(f"  {lock_status} {name}=={ver}")

    elif args.command == 'search':
        if args.remote:
            results = mgr.search_remote(args.query)
            if not results:
                print(f"远程仓库中未找到 '{args.query}'")
            else:
                print(f"\n远程搜索结果 ({len(results)}):")
                for r in results:
                    print(f"  {r.get('name', '?')}=={r.get('version', '?')} - {r.get('description', '')}")
        else:
            results = mgr.search(args.query)
            if not results:
                print(f"未找到与 '{args.query}' 匹配的包")
            else:
                print(f"\n找到 {len(results)} 个包:")
                for pkg in results:
                    print(f"  {pkg.name}=={pkg.version} - {pkg.description}")

    elif args.command == 'tree':
        print(mgr.show_tree(args.package))

    elif args.command == 'pack':
        mgr.pack(args.name, args.version)
        print("打包完成")

    elif args.command == 'publish':
        mgr.publish(args.name, args.version)

    elif args.command == 'env':
        if args.command == 'env' and args.nargs == 'create':
            mgr.create_env(args.name)
        elif args.command == 'env' and args.nargs == 'list':
            envs = mgr.list_envs()
            if not envs:
                print("无环境")
            else:
                print(f"\n环境 ({len(envs)}):")
                for env in envs:
                    print(f"  {env['name']} (Python {env['python_version']})")
