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
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

# 扩展基础包管理器
from src.pkg_manager import (
    MathaPackage,
    PackageMeta,
    PackageNotFoundError,
    Version,
    VersionConflictError,
)

# ============================================================
# 签名验证 (cosign/sigstore) —— 已移出至工具链插件
# ============================================================
# cosign 是外部进程，属工具链而非包管理器主线，故实现搬到
# src/plugins/toolchain_signature.py。此处用 PEP 562 模块级 __getattr__
# 按需解析：不用签名功能就不 import 插件、不触发 subprocess。
# （旧实现在本文件内直接调 cosign 子进程，并使
# verify_signed_package 把包字节同时当数据/签名/公钥——不可信的「假验签」。）

_SIGNATURE_NAMES = ("SignatureError", "SignatureVerifier")


def __getattr__(name: str):
    if name in _SIGNATURE_NAMES:
        from src.plugins import toolchain_signature
        return getattr(toolchain_signature, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# ============================================================
# Lockfile
# ============================================================

@dataclass
class LockEntry:
    """Lockfile 条目。"""
    name: str
    version: Version
    checksum: str = ""
    dependencies: dict[str, str] = field(default_factory=dict)
    source: str = "local"  # "local", "remote", "git"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": str(self.version),
            "checksum": self.checksum,
            "dependencies": self.dependencies,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict) -> LockEntry:
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
        self._entries: dict[str, LockEntry] = {}

    def load(self) -> None:
        """加载 lockfile。"""
        if not self._path.exists():
            return
        with open(self._path, encoding='utf-8') as f:
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

    def get(self, name: str) -> LockEntry | None:
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
    def packages(self) -> dict[str, LockEntry]:
        return dict(self._entries)


# ============================================================
# 远程包管理器
# ============================================================

class RemotePackageClient:
    """远程包仓库客户端。"""

    def __init__(self, base_url: str = "https://pypi.matha-lang.org"):
        self._base_url = base_url

    def search(self, query: str) -> list[dict]:
        """搜索远程包。"""
        try:
            url = f"{self._base_url}/search?q={query}"
            req = urllib.request.Request(url, headers={"User-Agent": "Matha-Pkg/2.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read())
        except (urllib.error.URLError, json.JSONDecodeError, ConnectionError):
            return []

    def get_metadata(self, name: str, version: str | None = None) -> dict | None:
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

    def check_lockfile(self) -> dict:
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

    def install_remote(self, spec: str) -> list[str]:
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

    def search_remote(self, query: str) -> list[dict]:
        """在远程仓库搜索包。"""
        if not self._remote_client:
            return []
        return self._remote_client.search(query)

    def search_local(self, query: str) -> list[dict]:
        """在本地已安装/注册包中搜索。"""
        query_lower = query.lower()
        results = []
        for name, pkg in self.registry.items():
            if query_lower in name.lower() or query_lower in pkg.description.lower():
                results.append({
                    "name": pkg.name,
                    "version": str(pkg.version),
                    "description": pkg.description,
                    "author": pkg.author,
                    "keywords": pkg.keywords,
                    "score": self._calculate_relevance(query_lower, name, pkg.description),
                    "installed": name in self.installed,
                })
        # 按相关性排序
        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    def search(self, query: str, remote: bool = False) -> list[dict]:
        """统一搜索接口。"""
        if remote:
            remote_results = self.search_remote(query)
            local_results = self.search_local(query)
            # 合并结果，去重
            seen = set()
            results = []
            for r in remote_results + local_results:
                key = r["name"]
                if key not in seen:
                    seen.add(key)
                    results.append(r)
            return results
        return self.search_local(query)

    def _calculate_relevance(self, query: str, name: str, description: str) -> float:
        """计算搜索相关性得分。"""
        score = 0.0
        query_lower = query.lower()
        name_lower = name.lower()
        desc_lower = (description or "").lower()

        # 名称完全匹配
        if query_lower == name_lower:
            score += 100
        # 名称前缀匹配
        elif name_lower.startswith(query_lower):
            score += 50
        # 名称包含
        elif query_lower in name_lower:
            score += 30
        # 描述中包含
        elif query_lower in desc_lower:
            score += 10

        # 词级匹配
        query_words = query_lower.split()
        for word in query_words:
            if word in name_lower:
                score += 10
            if word in desc_lower:
                score += 5

        return score

    # ============================================================
    # 包评分系统
    # ============================================================

    def rate_package(self, pkg_name: str, rating: int, user: str = "anonymous") -> bool:
        """为包评分。"""
        if pkg_name not in self.registry:
            raise PackageNotFoundError(f"未知包: {pkg_name}")
        if not 1 <= rating <= 5:
            raise ValueError("评分必须在 1-5 之间")

        self.root / "ratings.json"
        ratings = {}
        if self.root.joinpath("ratings.json").exists():
            with open(self.root / "ratings.json", encoding='utf-8') as f:
                ratings = json.load(f)

        if pkg_name not in ratings:
            ratings[pkg_name] = {}

        ratings[pkg_name][user] = {
            "rating": rating,
            "timestamp": __import__('time').time()
        }

        with open(self.root / "ratings.json", 'w', encoding='utf-8') as f:
            json.dump(ratings, f, ensure_ascii=False, indent=2)
        return True

    def get_package_rating(self, pkg_name: str) -> dict:
        """获取包的评分信息。"""
        ratings_file = self.root / "ratings.json"
        if not ratings_file.exists():
            return {"average": 0, "count": 0, "distribution": {1:0,2:0,3:0,4:0,5:0}}

        with open(self.root / "ratings.json", encoding='utf-8') as f:
            ratings = json.load(f)

        if pkg_name not in ratings:
            return {"average": 0, "count": 0, "distribution": {1:0,2:0,3:0,4:0,5:0}}

        pkg_ratings = ratings[pkg_name]
        total = len(pkg_ratings)
        if total == 0:
            return {"average": 0, "count": 0, "distribution": {1:0,2:0,3:0,4:0,5:0}}

        distribution = {1:0, 2:0, 3:0, 4:0, 5:0}
        total_score = 0
        for user, data in pkg_ratings.items():
            rating = data.get("rating", 0)
            total_score += rating
            distribution[rating] = distribution.get(rating, 0) + 1

        return {
            "average": round(total_score / total, 2),
            "count": total,
            "distribution": distribution
        }

    def get_package_stats(self, pkg_name: str) -> dict:
        """获取包的统计信息。"""
        if pkg_name not in self.registry:
            return {}

        pkg = self.registry[pkg_name]
        rating_info = self.get_package_rating(pkg_name)

        return {
            "name": pkg.name,
            "version": str(pkg.version),
            "description": pkg.description,
            "author": pkg.author,
            "license": pkg.license,
            "keywords": pkg.keywords,
            "dependencies": pkg.dependencies,
            "installed": pkg_name in self.installed,
            "installed_version": str(self.installed.get(pkg_name, "")),
            "rating": rating_info,
            "downloads": 0,
        }

    # ============================================================
    # 依赖解析增强
    # ============================================================

    def resolve_dependencies(self, spec: str, dev: bool = False) -> dict[str, Version]:
        """解析依赖关系，返回完整的依赖树和版本。

        Returns:
            Dict[package_name, Version]: 完整的依赖树（包含传递依赖）
        """
        match = re.match(r'^([a-zA-Z0-9_-]+)(?:==([0-9.]+))?$', spec.strip())
        if not match:
            raise ValueError(f"无效包规格: {spec}")

        pkg_name, version_spec = match.groups()
        if pkg_name not in self.registry:
            raise PackageNotFoundError(f"未知包: {pkg_name}")

        target_version = Version.parse(version_spec) if version_spec else self.registry[pkg_name].version
        resolved = {}
        conflicts = []

        def _resolve(name: str, version: Version, path: list[str]) -> None:
            if name in resolved:
                if resolved[name] != version:
                    conflicts.append({
                        "package": name,
                        "required": version,
                        "existing": resolved[name],
                        "path": " -> ".join(path + [name])
                    })
                return

            if name in path:
                # 循环依赖检测（忽略根包自身）
                cycle = " -> ".join(path + [name])
                raise ValueError(f"循环依赖检测: {cycle}")

            resolved[name] = version
            path.append(name)

            if name in self.registry:
                pkg = self.registry[name]
                for dep_name, dep_spec in pkg.dependencies.items():
                    if dep_name not in self.registry:
                        continue
                    self.registry[dep_name]
                    dep_version = Version.parse(dep_spec) if isinstance(dep_spec, str) else dep_spec
                    _resolve(dep_name, dep_version, path.copy())

        try:
            _resolve(pkg_name, target_version, [])
        except ValueError as e:
            raise ValueError(f"依赖解析失败: {e}")

        if conflicts:
            raise VersionConflictError(f"版本冲突: {conflicts}")

        return resolved

    def check_conflicts(self, specs: list[str]) -> list[dict]:
        """检查多个包规格之间的版本冲突。"""
        all_deps = {}
        conflicts = []

        for spec in specs:
            try:
                resolved = self.resolve_dependencies(spec)
                for name, version in resolved.items():
                    if name in all_deps and all_deps[name] != version:
                        conflicts.append({
                            "package": name,
                            "versions": [str(all_deps[name]), str(version)],
                            "sources": "多个包依赖不同版本"
                        })
                    else:
                        all_deps[name] = version
            except Exception as e:
                conflicts.append({
                    "package": spec,
                    "error": str(e)
                })

        return conflicts

    def suggest_version_resolution(self, conflicts: list[dict]) -> dict[str, Version]:
        """建议版本冲突解决方案。"""
        suggestions = {}
        for conflict in conflicts:
            pkg = conflict["package"]
            versions = [Version.parse(v) for v in conflict["versions"]]
            if pkg in self.registry:
                self.registry[conflict["package"]]
                # 策略：选择最高版本
                suggestions[conflict["package"]] = max(versions)
        return suggestions

    def get_dependency_tree(self, pkg_name: str, depth: int = 5) -> dict:
        """获取完整的依赖树（包含版本信息）。"""
        if pkg_name not in self.registry:
            return {}

        result = {"name": pkg_name, "version": str(self.registry[pkg_name].version), "dependencies": {}}

        def _build_tree(name: str, depth: int, seen: set):
            if depth <= 0 or name in seen:
                return {}
            seen.add(name)

            if name not in self.registry:
                return {}

            pkg = self.registry[name]
            deps = {}
            for dep_name, dep_spec in pkg.dependencies.items():
                if dep_name not in self.registry:
                    continue
                dep_version = Version.parse(dep_spec) if isinstance(dep_spec, str) else dep_spec
                deps[dep_name] = {
                    "version": str(dep_version),
                    "installed": self.installed.get(dep_name),
                    "dependencies": self.get_dependency_tree(dep_name, depth - 1, seen.copy())
                }
            return deps

        result["dependencies"] = _build_tree(pkg_name, 5, set())
        return result

    def check_updates(self) -> list[dict]:
        """检查已安装包的更新。"""
        updates = []
        for name, installed_version in self.installed.items():
            if name in self.registry:
                latest = self.registry[name].version
                if Version.parse(installed_version) < latest:
                    updates.append({
                        "package": name,
                        "current": installed_version,
                        "latest": str(latest),
                        "type": "major" if Version.parse(installed_version).major < latest.major else "minor/patch"
                    })
        return updates

    def upgrade_all(self, dry_run: bool = False) -> list[str]:
        """升级所有可更新的包。"""
        updates = self.check_updates()
        upgraded = []
        for update in updates:
            if not dry_run:
                self.install(f"{update['package']}=={update['latest']}")
            upgraded.append(f"{update['package']} {update['current']} -> {update['latest']}")
        return upgraded

    def upgrade_package(self, pkg_name: str, dry_run: bool = False) -> list[str]:
        """升级指定包。"""
        updates = self.check_updates()
        pkg_update = next((u for u in updates if u['package'] == pkg_name), None)
        if not pkg_update:
            return []
        if not dry_run:
            self.install(f"{pkg_name}=={pkg_update['latest']}")
        return [f"{pkg_name} {pkg_update['current']} -> {pkg_update['latest']}"]

    # ============================================================
    # CLI 入口增强
    # ============================================================

    def show_package_info(self, pkg_name: str) -> str:
        """显示包的详细信息。"""
        stats = self.get_package_stats(pkg_name)
        if not stats:
            return f"包不存在: {pkg_name}"

        lines = [
            f"包名: {stats['name']}",
            f"版本: {stats['version']}",
            f"描述: {stats['description']}",
            f"作者: {stats['author']}",
            f"许可证: {stats['license']}",
            f"关键词: {', '.join(stats.get('keywords', []))}",
            f"依赖: {', '.join(stats.get('dependencies', {}).keys()) or '无'}",
            f"状态: {'已安装' if stats['installed'] else '未安装'}",
        ]
        if stats.get('installed'):
            lines.append(f"已安装版本: {stats['installed_version']}")

        rating = stats.get('rating', {})
        if rating.get('count', 0) > 0:
            lines.append(f"评分: {rating['average']}/5.0 ({rating['count']} 人评价)")

        return "\n".join(lines)

    # ============================================================
    # 包发布
    # ============================================================

    def pack(self, pkg_name: str, version: str | None = None) -> str:
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

    def publish(self, pkg_name: str, version: str | None = None) -> bool:
        """发布包到远程仓库。"""
        if not self._remote_client:
            raise RuntimeError("未配置远程仓库 URL")

        self.pack(pkg_name, version)
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

    def list_envs(self) -> list[dict]:
        """列出所有环境。"""
        envs = []
        for env_dir in self._envs_dir.iterdir():
            if env_dir.is_dir() and (env_dir / 'env.json').exists():
                with open(env_dir / 'env.json', encoding='utf-8') as f:
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

    def install(self, spec: str, dev: bool = False) -> list[str]:
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

    def list_packages(self) -> list[tuple[str, Version]]:
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
    search_p.add_argument('--detail', action='store_true', help='显示详细信息')

    # rate
    rate_p = subparsers.add_parser('rate', help='给包评分')
    rate_p.add_argument('package', help='包名')
    rate_p.add_argument('rating', type=int, help='评分 (1-5)')
    rate_p.add_argument('--user', default='anonymous', help='用户名')

    # info
    info_p = subparsers.add_parser('info', help='显示包详细信息')
    info_p.add_argument('package', help='包名')

    # upgrade
    upgrade_p = subparsers.add_parser('upgrade', help='升级包')
    upgrade_p.add_argument('package', nargs='?', help='包名 (不指定则升级所有)')
    upgrade_p.add_argument('--dry-run', action='store_true', help='仅显示将升级的包')

    # check-conflicts
    conflict_p = subparsers.add_parser('check-conflicts', help='检查依赖冲突')
    conflict_p.add_argument('specs', nargs='+', help='包规格列表')

    # deptree
    deptree_p = subparsers.add_parser('deptree', help='显示完整依赖树')
    deptree_p.add_argument('package', help='包名')
    deptree_p.add_argument('--depth', type=int, default=5, help='显示深度')

    # tree
    tree_p = subparsers.add_parser('tree', help='显示依赖树')
    tree_p.add_argument('package', nargs='?', help='包名')

    # pack
    pack_p = subparsers.add_parser('pack', help='打包发布')
    pack_p.add_argument('name', help='包名')
    pack_p.add_argument('--version', help='版本号')

    # sign
    sign_p = subparsers.add_parser('sign', help='签名包文件')
    sign_p.add_argument('package', help='包文件路径 (.tar.gz)')
    sign_p.add_argument('--key', required=True, help='私钥路径')
    sign_p.add_argument('--password', help='私钥密码')

    # verify
    verify_p = subparsers.add_parser('verify', help='验证包签名')
    verify_p.add_argument('package', help='包文件路径 (.tar.gz)')
    verify_p.add_argument('--key', required=True, help='公钥路径')
    verify_p.add_argument('--cert', help='证书路径 (可选，用于 keyless 验证)')

    # verify-slsa
    verify_slsa_p = subparsers.add_parser('verify-slsa', help='验证 SLSA 来源认证')
    verify_slsa_p.add_argument('package', help='包文件路径')
    verify_slsa_p.add_argument('--provenance', required=True, help='SLSA 来源文件路径')
    verify_slsa_p.add_argument('--builder-id', required=True, help='预期的构建器 ID')

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
            print("✗ Lockfile 不一致:")
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
                for r in results:
                    status = "🔒" if r.get('installed') else "  "
                    print(f"  {status} {r['name']}=={r['version']} - {r['description']}")
                    if args.detail:
                        print(f"      作者: {r.get('author', '未知')}")
                        print(f"      分类: {r.get('category', '未知')}")

    elif args.command == 'rate':
        try:
            mgr.rate_package(args.package, args.rating, args.user)
            print(f"✓ 已为 {args.package} 评分: {args.rating}/5")
        except Exception as e:
            print(f"评分失败: {e}")
            sys.exit(1)

    elif args.command == 'info':
        print(mgr.show_package_info(args.package))

    elif args.command == 'upgrade':
        if args.package:
            pkg_update = None
            updates = mgr.check_updates()
            for u in updates:
                if u['package'] == args.package:
                    pkg_update = u
                    break
            if pkg_update:
                if args.dry_run:
                    print(f"将升级: {pkg_update['package']} {pkg_update['current']} -> {pkg_update['latest']} ({pkg_update['type']})")
                else:
                    result = mgr.upgrade_package(args.package)
                    print(f"✓ 已升级: {result}")
            else:
                print(f"包 {args.package} 已是最新版本或未安装")
        else:
            updates = mgr.check_updates()
            if not updates:
                print("所有包均为最新版本")
            else:
                if args.dry_run:
                    print("将升级以下包:")
                    for u in updates:
                        print(f"  {u['package']} {u['current']} -> {u['latest']} ({u['type']})")
                else:
                    upgraded = mgr.upgrade_all()
                    print(f"✓ 已升级 {len(upgraded)} 个包:")
                    for u in upgraded:
                        print(f"  {u}")

    elif args.command == 'check-conflicts':
        conflicts = mgr.check_conflicts(args.specs)
        if not conflicts:
            print("✓ 无版本冲突")
        else:
            print(f"发现 {len(conflicts)} 个冲突:")
            for c in conflicts:
                if 'versions' in c:
                    print(f"  {c['package']}: {' vs '.join(c['versions'])} - {c.get('sources', '')}")
                else:
                    print(f"  {c['package']}: {c.get('error', '未知错误')}")
            # 建议解决方案
            suggestions = mgr.suggest_version_resolution(conflicts)
            if suggestions:
                print("\n建议解决方案:")
                for pkg, ver in suggestions.items():
                    print(f"  {pkg} -> {ver}")

    elif args.command == 'deptree':
        import json
        tree = mgr.get_dependency_tree(args.package, args.depth)
        if tree:
            print(json.dumps(tree, ensure_ascii=False, indent=2))
        else:
            print(f"包不存在: {args.package}")

    elif args.command == 'tree':
        print(mgr.show_tree(args.package))

    elif args.command == 'pack':
        mgr.pack(args.name, args.version)
        print("打包完成")

    elif args.command == 'publish':
        mgr.publish(args.name, args.version)

    elif args.command == 'sign':
        if not mgr._remote_client:
            print("错误: 未配置远程仓库，无法签名")
            sys.exit(1)

        # 初始化签名验证器（插件按需加载；require=False 保留下方显式报错文案）
        try:
            verifier = SignatureVerifier(require=False)
            if not verifier.is_available:
                print("错误: cosign 未安装，无法签名")
                print("请安装 cosign: https://docs.sigstore.dev/cosign/installation/")
                sys.exit(1)
        except Exception as e:
            print(f"错误: 初始化签名验证器失败: {e}")
            sys.exit(1)

        pkg_path = Path(args.package)
        if not pkg_path.exists():
            print(f"错误: 包文件不存在: {pkg_path}")
            sys.exit(1)

        print(f"正在签名: {pkg_path}")
        try:
            data = pkg_path.read_bytes()
            signature = verifier.sign_blob(data, args.key, args.password)

            # 写入签名文件
            sig_path = pkg_path.with_suffix(pkg_path.suffix + ".sig")
            sig_path.write_bytes(signature)
            print(f"✓ 签名完成: {sig_path}")
        except Exception as e:
            print(f"签名失败: {e}")
            sys.exit(1)

    elif args.command == 'verify':
        if not hasattr(mgr, '_verifier'):
            mgr._verifier = SignatureVerifier(require=False)

        if not mgr._verifier.is_available:
            print("错误: cosign 未安装，无法验证")
            print("请安装 cosign: https://docs.sigstore.dev/cosign/installation/")
            sys.exit(1)

        pkg_path = Path(args.package)
        if not pkg_path.exists():
            print(f"错误: 包文件不存在: {pkg_path}")
            sys.exit(1)

        print(f"正在验证: {pkg_path}")
        try:
            result = mgr._verifier.verify_signed_package(
                Path(args.package),
                args.key,
                args.cert
            )
            if result:
                print("✓ 验证通过: 签名有效")
            else:
                print("✗ 验证失败: 签名无效或文件已被篡改")
                sys.exit(1)
        except Exception as e:
            print(f"验证失败: {e}")
            sys.exit(1)

    elif args.command == 'verify-slsa':
        if not hasattr(mgr, '_verifier'):
            mgr._verifier = SignatureVerifier(require=False)

        if not mgr._verifier.is_available:
            print("错误: cosign 未安装，无法验证")
            sys.exit(1)

        pkg_path = Path(args.package)
        provenance_path = Path(args.provenance)

        if not pkg_path.exists() or not provenance_path.exists():
            print("错误: 包文件或来源文件不存在")
            sys.exit(1)

        print(f"正在验证 SLSA 来源认证: {args.package}")
        try:
            result = mgr._verifier.verify_slsa_provenance(
                Path(args.package),
                Path(args.provenance),
                args.builder_id
            )
            if result:
                print("✓ SLSA 来源认证验证通过")
            else:
                print("✗ SLSA 来源认证验证失败")
                sys.exit(1)
        except Exception as e:
            print(f"验证失败: {e}")
            sys.exit(1)

    elif args.command == 'env':
            envs = mgr.list_envs()
            if not envs:
                print("无环境")
            else:
                print(f"\n环境 ({len(envs)}):")
                for env in envs:
                    print(f"  {env['name']} (Python {env['python_version']})")
