"""
Matha 增量编译系统 - 只重新编译发生变化的部分

这个模块提供了：
1. 文件依赖图 - 跟踪文件之间的依赖关系
2. 变更检测 - 检测文件是否发生变化
3. 增量构建 - 只重新编译发生变化的部分
4. 缓存管理 - 管理编译结果的缓存

这个系统是 Matha 实现快速迭代开发的核心组件。
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger("matha.incremental_compiler")


@dataclass
class FileInfo:
    """文件信息"""
    path: str
    hash: str = ""
    last_modified: float = 0.0
    size: int = 0
    dependencies: Set[str] = field(default_factory=set)
    dependents: Set[str] = field(default_factory=set)
    is_source: bool = True
    is_generated: bool = False

    def compute_hash(self) -> str:
        """计算文件哈希"""
        try:
            with open(self.path, 'rb') as f:
                content = f.read()
                self.hash = hashlib.sha256(content).hexdigest()
                self.last_modified = os.path.getmtime(self.path)
                self.size = os.path.getsize(self.path)
                return self.hash
        except FileNotFoundError:
            logger.warning(f"文件不存在: {self.path}")
            return ""
        except Exception as e:
            logger.error(f"计算文件哈希失败: {e}")
            return ""

    def has_changed(self) -> bool:
        """检查文件是否发生变化"""
        try:
            current_mtime = os.path.getmtime(self.path)
            if current_mtime != self.last_modified:
                # 文件修改时间变化，重新计算哈希
                old_hash = self.hash
                new_hash = self.compute_hash()
                return old_hash != new_hash
            return False
        except FileNotFoundError:
            return True
        except Exception as e:
            logger.error(f"检查文件变化失败: {e}")
            return True

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "path": self.path,
            "hash": self.hash,
            "last_modified": self.last_modified,
            "size": self.size,
            "dependencies": list(self.dependencies),
            "dependents": list(self.dependents),
            "is_source": self.is_source,
            "is_generated": self.is_generated
        }

    @classmethod
    def from_dict(cls, data: Dict) -> FileInfo:
        """从字典创建文件信息"""
        return cls(
            path=data["path"],
            hash=data.get("hash", ""),
            last_modified=data.get("last_modified", 0.0),
            size=data.get("size", 0),
            dependencies=set(data.get("dependencies", [])),
            dependents=set(data.get("dependents", [])),
            is_source=data.get("is_source", True),
            is_generated=data.get("is_generated", False)
        )


@dataclass
class BuildResult:
    """构建结果"""
    target: str
    sources: List[str] = field(default_factory=list)
    output_files: List[str] = field(default_factory=list)
    success: bool = False
    error: Optional[str] = None
    compile_time: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "target": self.target,
            "sources": self.sources,
            "output_files": self.output_files,
            "success": self.success,
            "error": self.error,
            "compile_time": self.compile_time,
            "timestamp": self.timestamp
        }

    @classmethod
    def from_dict(cls, data: Dict) -> BuildResult:
        """从字典创建构建结果"""
        return cls(
            target=data["target"],
            sources=data.get("sources", []),
            output_files=data.get("output_files", []),
            success=data.get("success", False),
            error=data.get("error"),
            compile_time=data.get("compile_time", 0.0),
            timestamp=data.get("timestamp", time.time())
        )


class DependencyGraph:
    """依赖图 - 跟踪文件之间的依赖关系"""

    def __init__(self) -> None:
        """初始化依赖图"""
        self.files: Dict[str, FileInfo] = {}
        self.build_results: Dict[str, BuildResult] = {}

    def add_file(self, path: str, is_source: bool = True) -> FileInfo:
        """
        添加文件到依赖图

        Args:
            path: 文件路径
            is_source: 是否是源文件

        Returns:
            文件信息
        """
        if path not in self.files:
            info = FileInfo(path=path, is_source=is_source)
            info.compute_hash()
            self.files[path] = info
        return self.files[path]

    def remove_file(self, path: str) -> bool:
        """从依赖图中移除文件"""
        if path not in self.files:
            return False

        # 移除依赖关系
        info = self.files[path]
        for dep in info.dependencies:
            if dep in self.files:
                self.files[dep].dependents.remove(path)
        for dep in info.dependents:
            if dep in self.files:
                self.files[dep].dependencies.remove(path)

        del self.files[path]
        return True

    def add_dependency(self, source: str, target: str) -> None:
        """
        添加依赖关系

        Args:
            source: 源文件
            target: 目标文件（源文件依赖的文件）
        """
        # 确保两个文件都存在
        self.add_file(source)
        self.add_file(target)

        # 添加依赖关系
        self.files[source].dependencies.add(target)
        self.files[target].dependents.add(source)

    def remove_dependency(self, source: str, target: str) -> None:
        """移除依赖关系"""
        if source in self.files and target in self.files:
            self.files[source].dependencies.discard(target)
            self.files[target].dependents.discard(source)

    def get_dependencies(self, path: str) -> Set[str]:
        """获取文件的所有直接依赖"""
        if path in self.files:
            return self.files[path].dependencies.copy()
        return set()

    def get_all_dependencies(self, path: str, visited: Optional[Set[str]] = None) -> Set[str]:
        """获取文件的所有传递依赖"""
        if visited is None:
            visited = set()

        if path in visited:
            return set()
        visited.add(path)

        deps = set()
        if path in self.files:
            for dep in self.files[path].dependencies:
                deps.add(dep)
                deps.update(self.get_all_dependencies(dep, visited))

        return deps

    def get_dependents(self, path: str) -> Set[str]:
        """获取文件的所有直接依赖者"""
        if path in self.files:
            return self.files[path].dependents.copy()
        return set()

    def get_all_dependents(self, path: str, visited: Optional[Set[str]] = None) -> Set[str]:
        """获取文件的所有传递依赖者"""
        if visited is None:
            visited = set()

        if path in visited:
            return set()
        visited.add(path)

        deps = set()
        if path in self.files:
            for dep in self.files[path].dependents:
                deps.add(dep)
                deps.update(self.get_all_dependents(dep, visited))

        return deps

    def get_changed_files(self) -> Set[str]:
        """获取所有发生变化的文件"""
        changed = set()
        for path, info in self.files.items():
            if info.is_source and info.has_changed():
                changed.add(path)
        return changed

    def get_affected_files(self, changed_files: Set[str]) -> Set[str]:
        """获取受变化影响的所有文件"""
        affected = changed_files.copy()
        for path in changed_files:
            affected.update(self.get_all_dependents(path))
        return affected

    def topological_sort(self, files: Optional[Set[str]] = None) -> List[str]:
        """
        拓扑排序文件

        Args:
            files: 要排序的文件集合，如果为 None 则排序所有文件

        Returns:
            排序后的文件列表
        """
        if files is None:
            files = set(self.files.keys())

        # 构建子图
        in_degree: Dict[str, int] = {f: 0 for f in files}
        for f in files:
            if f in self.files:
                for dep in self.files[f].dependencies:
                    if dep in files:
                        in_degree[f] += 1

        # 拓扑排序
        queue = [f for f, d in in_degree.items() if d == 0]
        sorted_files = []

        while queue:
            # 按路径排序，确保确定性
            queue.sort()
            f = queue.pop(0)
            sorted_files.append(f)

            if f in self.files:
                for dep in self.files[f].dependents:
                    if dep in files:
                        in_degree[dep] -= 1
                        if in_degree[dep] == 0:
                            queue.append(dep)

        # 检查是否有环
        if len(sorted_files) != len(files):
            logger.warning("依赖图中存在循环依赖")
            # 添加未排序的文件
            for f in files:
                if f not in sorted_files:
                    sorted_files.append(f)

        return sorted_files

    def save(self, path: str) -> None:
        """保存依赖图"""
        data = {
            "files": {k: v.to_dict() for k, v in self.files.items()},
            "build_results": {k: v.to_dict() for k, v in self.build_results.items()}
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def load(self, path: str) -> None:
        """加载依赖图"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.files = {k: FileInfo.from_dict(v) for k, v in data.get("files", {}).items()}
            self.build_results = {k: BuildResult.from_dict(v) for k, v in data.get("build_results", {}).items()}
        except FileNotFoundError:
            logger.warning(f"依赖图文件不存在: {path}")
        except Exception as e:
            logger.error(f"加载依赖图失败: {e}")


class IncrementalCompiler:
    """增量编译器 - 只重新编译发生变化的部分"""

    def __init__(self, cache_dir: Optional[str] = None) -> None:
        """
        初始化增量编译器

        Args:
            cache_dir: 缓存目录
        """
        self.cache_dir = Path(cache_dir or os.path.expanduser("~/.matha/cache"))
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.dependency_graph = DependencyGraph()
        self.compile_cache: Dict[str, BuildResult] = {}

        # 加载缓存
        self._load_cache()

    def _load_cache(self) -> None:
        """加载编译缓存"""
        cache_file = self.cache_dir / "compile_cache.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.compile_cache = {k: BuildResult.from_dict(v) for k, v in data.items()}
            except Exception as e:
                logger.error(f"加载编译缓存失败: {e}")

    def _save_cache(self) -> None:
        """保存编译缓存"""
        cache_file = self.cache_dir / "compile_cache.json"
        try:
            data = {k: v.to_dict() for k, v in self.compile_cache.items()}
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"保存编译缓存失败: {e}")

    def add_source_file(self, path: str) -> None:
        """添加源文件"""
        self.dependency_graph.add_file(path, is_source=True)

    def add_dependency(self, source: str, target: str) -> None:
        """添加依赖关系"""
        self.dependency_graph.add_dependency(source, target)

    def compile(self, target: str, force: bool = False) -> BuildResult:
        """
        编译目标

        Args:
            target: 目标文件
            force: 是否强制重新编译

        Returns:
            构建结果
        """
        start_time = time.time()

        if not force:
            # 检查是否需要重新编译
            if not self._needs_recompile(target):
                logger.info(f"目标 {target} 无需重新编译")
                return self.compile_cache.get(target, BuildResult(target=target))

        logger.info(f"编译目标: {target}")

        # 获取受影响的文件
        changed_files = self.dependency_graph.get_changed_files()
        affected_files = self.dependency_graph.get_affected_files(changed_files)

        # 获取需要编译的文件
        if target in affected_files or force:
            files_to_compile = self._get_files_to_compile(target, affected_files)
        else:
            files_to_compile = []

        if not files_to_compile:
            logger.info(f"目标 {target} 无需重新编译")
            return self.compile_cache.get(target, BuildResult(target=target))

        # 按拓扑排序编译文件
        sorted_files = self.dependency_graph.topological_sort(set(files_to_compile))

        # 编译每个文件
        all_output_files = []
        errors = []

        for file_path in sorted_files:
            result = self._compile_file(file_path)
            if result.success:
                all_output_files.extend(result.output_files)
                self.compile_cache[file_path] = result
            else:
                errors.append(result.error)

        # 创建构建结果
        build_result = BuildResult(
            target=target,
            sources=sorted_files,
            output_files=all_output_files,
            success=len(errors) == 0,
            error="; ".join(errors) if errors else None,
            compile_time=time.time() - start_time
        )

        # 保存缓存
        self.compile_cache[target] = build_result
        self._save_cache()

        return build_result

    def _needs_recompile(self, target: str) -> bool:
        """检查目标是否需要重新编译"""
        # 检查目标是否存在
        if target not in self.compile_cache:
            return True

        # 检查目标文件是否存在
        if not os.path.exists(target):
            return True

        # 检查源文件是否发生变化
        changed_files = self.dependency_graph.get_changed_files()
        if not changed_files:
            return False

        # 检查目标是否受影响
        affected_files = self.dependency_graph.get_affected_files(changed_files)
        return target in affected_files

    def _get_files_to_compile(self, target: str, affected_files: Set[str]) -> List[str]:
        """获取需要编译的文件列表"""
        # 获取目标的所有依赖
        all_deps = self.dependency_graph.get_all_dependencies(target)
        all_deps.add(target)

        # 只编译受影响的文件
        files_to_compile = [f for f in all_deps if f in affected_files]
        return files_to_compile

    def _compile_file(self, file_path: str) -> BuildResult:
        """编译单个文件"""
        start_time = time.time()

        logger.info(f"编译文件: {file_path}")

        try:
            # 这里应该调用实际的编译器
            # 简化实现，模拟编译过程
            output_file = str(Path(file_path).with_suffix('.o'))

            # 模拟编译时间
            time.sleep(0.1)

            result = BuildResult(
                target=file_path,
                sources=[file_path],
                output_files=[output_file],
                success=True,
                compile_time=time.time() - start_time
            )

            return result

        except Exception as e:
            logger.error(f"编译文件 {file_path} 失败: {e}")
            return BuildResult(
                target=file_path,
                sources=[file_path],
                success=False,
                error=str(e),
                compile_time=time.time() - start_time
            )

    def clean(self) -> None:
        """清理编译缓存"""
        self.compile_cache.clear()
        self._save_cache()
        logger.info("编译缓存已清理")

    def get_build_status(self, target: str) -> Optional[BuildResult]:
        """获取构建状态"""
        return self.compile_cache.get(target)

    def save_dependency_graph(self, path: str) -> None:
        """保存依赖图"""
        self.dependency_graph.save(path)

    def load_dependency_graph(self, path: str) -> None:
        """加载依赖图"""
        self.dependency_graph.load(path)


# 全局增量编译器实例
_global_incremental_compiler = None


def get_incremental_compiler(cache_dir: Optional[str] = None) -> IncrementalCompiler:
    """获取全局增量编译器"""
    global _global_incremental_compiler
    if _global_incremental_compiler is None:
        _global_incremental_compiler = IncrementalCompiler(cache_dir)
    return _global_incremental_compiler


def add_source_file(path: str) -> None:
    """添加源文件"""
    compiler = get_incremental_compiler()
    compiler.add_source_file(path)


def add_dependency(source: str, target: str) -> None:
    """添加依赖关系"""
    compiler = get_incremental_compiler()
    compiler.add_dependency(source, target)


def compile_target(target: str, force: bool = False) -> BuildResult:
    """编译目标"""
    compiler = get_incremental_compiler()
    return compiler.compile(target, force)


def clean_cache() -> None:
    """清理编译缓存"""
    compiler = get_incremental_compiler()
    compiler.clean()


def get_build_status(target: str) -> Optional[BuildResult]:
    """获取构建状态"""
    compiler = get_incremental_compiler()
    return compiler.get_build_status(target)
