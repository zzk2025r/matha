"""
Matha 分布式编译系统 - 支持多节点协同编译

这个模块提供了：
1. 编译任务分发 - 将编译任务分发到多个节点
2. 节点管理 - 管理编译节点的状态和能力
3. 任务调度 - 根据节点负载和能力调度任务
4. 结果收集 - 收集和合并编译结果

这个系统是 Matha 实现大规模并行编译的核心组件。
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger("matha.distributed_compiler")

# HTTP 远程节点路径为可选依赖（aiohttp）：核心安装第三方依赖为 0（pyproject dependencies=[]），
# 仅在 RemoteCompilerNode 实际收发请求时惰性装入；本地节点/调度器零第三方依赖可用。
# 依赖图用下方 _DiGraph 纯标准库实现，替代 networkx（本模块只用 add_edge/successors 两面）。


class _DiGraph:
    """极简有向图（dict 邻接表）——替代 networkx.DiGraph，只承载本模块用到的两面。"""

    def __init__(self) -> None:
        self._succ: Dict[str, Set[str]] = {}

    def add_edge(self, u: str, v: str) -> None:
        """加边 u → v（节点不存在则自动登记）"""
        self._succ.setdefault(u, set()).add(v)
        self._succ.setdefault(v, set())

    def successors(self, node: str) -> List[str]:
        """node 的全部后继（不存在则空）"""
        return list(self._succ.get(node, ()))


@dataclass
class CompilationTask:
    """编译任务"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    program: Any = None
    options: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    priority: int = 0
    timeout: int = 300  # 默认超时时间（秒）
    status: str = "pending"  # pending, running, completed, failed
    assigned_node: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    result: Any = None
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "id": self.id,
            "program": self.program,
            "options": self.options,
            "dependencies": self.dependencies,
            "priority": self.priority,
            "timeout": self.timeout,
            "status": self.status,
            "assigned_node": self.assigned_node,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "result": self.result,
            "error": self.error
        }

    @classmethod
    def from_dict(cls, data: Dict) -> CompilationTask:
        """从字典创建任务"""
        return cls(
            id=data["id"],
            program=data.get("program"),
            options=data.get("options", {}),
            dependencies=data.get("dependencies", []),
            priority=data.get("priority", 0),
            timeout=data.get("timeout", 300),
            status=data.get("status", "pending"),
            assigned_node=data.get("assigned_node"),
            start_time=data.get("start_time"),
            end_time=data.get("end_time"),
            result=data.get("result"),
            error=data.get("error")
        )


@dataclass
class NodeCapability:
    """节点能力"""
    max_concurrent_tasks: int = 1
    supported_targets: List[str] = field(default_factory=list)
    supported_optimizations: List[str] = field(default_factory=list)
    cpu_count: int = 1
    memory_size: int = 1024  # MB
    gpu_available: bool = False
    gpu_count: int = 0
    gpu_memory: int = 0  # MB
    network_bandwidth: int = 100  # Mbps
    storage_size: int = 1024  # GB
    os_type: str = "linux"
    arch: str = "x86_64"
    compiler_version: str = "1.0.0"
    last_heartbeat: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "supported_targets": self.supported_targets,
            "supported_optimizations": self.supported_optimizations,
            "cpu_count": self.cpu_count,
            "memory_size": self.memory_size,
            "gpu_available": self.gpu_available,
            "gpu_count": self.gpu_count,
            "gpu_memory": self.gpu_memory,
            "network_bandwidth": self.network_bandwidth,
            "storage_size": self.storage_size,
            "os_type": self.os_type,
            "arch": self.arch,
            "compiler_version": self.compiler_version,
            "last_heartbeat": self.last_heartbeat
        }

    @classmethod
    def from_dict(cls, data: Dict) -> NodeCapability:
        """从字典创建节点能力"""
        return cls(
            max_concurrent_tasks=data.get("max_concurrent_tasks", 1),
            supported_targets=data.get("supported_targets", []),
            supported_optimizations=data.get("supported_optimizations", []),
            cpu_count=data.get("cpu_count", 1),
            memory_size=data.get("memory_size", 1024),
            gpu_available=data.get("gpu_available", False),
            gpu_count=data.get("gpu_count", 0),
            gpu_memory=data.get("gpu_memory", 0),
            network_bandwidth=data.get("network_bandwidth", 100),
            storage_size=data.get("storage_size", 1024),
            os_type=data.get("os_type", "linux"),
            arch=data.get("arch", "x86_64"),
            compiler_version=data.get("compiler_version", "1.0.0"),
            last_heartbeat=data.get("last_heartbeat", time.time())
        )


@dataclass
class NodeInfo:
    """节点信息"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    address: str = ""
    port: int = 8080
    capability: NodeCapability = field(default_factory=NodeCapability)
    current_tasks: Set[str] = field(default_factory=set)
    status: str = "active"  # active, inactive, busy
    last_heartbeat: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "address": self.address,
            "port": self.port,
            "capability": self.capability.to_dict(),
            "current_tasks": list(self.current_tasks),
            "status": self.status,
            "last_heartbeat": self.last_heartbeat
        }

    @classmethod
    def from_dict(cls, data: Dict) -> NodeInfo:
        """从字典创建节点信息"""
        return cls(
            id=data["id"],
            name=data.get("name", ""),
            address=data.get("address", ""),
            port=data.get("port", 8080),
            capability=NodeCapability.from_dict(data.get("capability", {})),
            current_tasks=set(data.get("current_tasks", [])),
            status=data.get("status", "active"),
            last_heartbeat=data.get("last_heartbeat", time.time)
        )


class CompilerNode(ABC):
    """编译节点基类"""

    def __init__(self, node_info: NodeInfo) -> None:
        """
        初始化编译节点

        Args:
            node_info: 节点信息
        """
        self.node_info = node_info
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.task_results: Dict[str, Any] = {}

    @abstractmethod
    async def compile(self, task: CompilationTask) -> Any:
        """
        编译程序

        Args:
            task: 编译任务

        Returns:
            编译结果
        """
        pass

    async def execute_task(self, task: CompilationTask) -> Any:
        """
        执行编译任务

        Args:
            task: 编译任务

        Returns:
            编译结果
        """
        task.status = "running"
        task.start_time = time.time()
        self.node_info.current_tasks.add(task.id)

        try:
            # 执行编译
            result = await self.compile(task)

            # 记录结果
            task.result = result
            task.status = "completed"
            task.end_time = time.time()

            # 更新节点信息
            self.node_info.current_tasks.remove(task.id)
            self.task_results[task.id] = result

            return result

        except Exception as e:
            # 记录错误
            task.error = str(e)
            task.status = "failed"
            task.end_time = time.time()

            # 更新节点信息
            self.node_info.current_tasks.remove(task.id)
            self.task_results[task.id] = None

            logger.error(f"任务 {task.id} 执行失败: {e}")
            raise

    async def heartbeat(self) -> NodeInfo:
        """发送心跳"""
        self.node_info.last_heartbeat = time.time()
        return self.node_info

    def get_task_status(self, task_id: str) -> Optional[str]:
        """获取任务状态"""
        if task_id in self.running_tasks:
            return "running"
        elif task_id in self.task_results:
            return "completed" if self.task_results[task_id] is not None else "failed"
        else:
            return None

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        if task_id in self.running_tasks:
            task = self.running_tasks[task_id]
            task.cancel()
            del self.running_tasks[task_id]
            return True
        return False


class LocalCompilerNode(CompilerNode):
    """本地编译节点"""

    def __init__(self, node_info: NodeInfo) -> None:
        """初始化本地编译节点"""
        super().__init__(node_info)

    async def compile(self, task: CompilationTask) -> Any:
        """编译程序"""
        # 模拟编译过程
        await asyncio.sleep(1)  # 模拟编译时间

        # 这里应该调用实际的编译器
        # 简化实现，返回模拟结果
        return {
            "status": "success",
            "output": f"编译结果: {task.id}",
            "statistics": {
                "compile_time": 1.0,
                "optimizations_applied": ["常量折叠", "死代码消除"],
                "code_size": 1024
            }
        }


class RemoteCompilerNode(CompilerNode):
    """远程编译节点"""

    def __init__(self, node_info: NodeInfo) -> None:
        """初始化远程编译节点"""
        super().__init__(node_info)
        self.session = None  # aiohttp.ClientSession，首次请求时惰性创建

    async def compile(self, task: CompilationTask) -> Any:
        """编译程序"""
        # HTTP 依赖惰性装入：缺席时诚实报错（本地节点不受影响）
        try:
            import aiohttp
        except ImportError as e:
            raise ImportError(
                "RemoteCompilerNode 需要 aiohttp（pip install aiohttp）才可发起远程编译；"
                "纯本地编译请使用 LocalCompilerNode。"
            ) from e

        # 创建HTTP会话
        if self.session is None:
            self.session = aiohttp.ClientSession()

        # 发送编译请求
        url = f"http://{self.node_info.address}:{self.node_info.port}/compile"
        try:
            async with self.session.post(url, json=task.to_dict()) as response:
                if response.status == 200:
                    result = await response.json()
                    return result
                else:
                    error = await response.text()
                    raise Exception(f"编译失败: {error}")
        except Exception as e:
            logger.error(f"远程编译失败: {e}")
            raise

    async def heartbeat(self) -> NodeInfo:
        """发送心跳"""
        # HTTP 依赖惰性装入：缺席时诚实报错
        try:
            import aiohttp
        except ImportError as e:
            raise ImportError(
                "RemoteCompilerNode 需要 aiohttp（pip install aiohttp）才可发送心跳。"
            ) from e

        # 创建HTTP会话
        if self.session is None:
            self.session = aiohttp.ClientSession()

        url = f"http://{self.node_info.address}:{self.node_info.port}/heartbeat"
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    self.node_info = NodeInfo.from_dict(data)
                    return self.node_info
                else:
                    raise Exception(f"心跳失败: {response.status}")
        except Exception as e:
            logger.error(f"心跳失败: {e}")
            raise

    async def close(self) -> None:
        """关闭会话"""
        if self.session:
            await self.session.close()


class TaskScheduler:
    """任务调度器 - 负责任务调度和分发"""

    def __init__(self) -> None:
        """初始化任务调度器"""
        self.nodes: Dict[str, CompilerNode] = {}
        self.tasks: Dict[str, CompilationTask] = {}
        self.dependency_graph = _DiGraph()
        self.load_balancing_strategy = "round_robin"  # round_robin, least_loaded, random

    def add_node(self, node: CompilerNode) -> None:
        """添加编译节点"""
        self.nodes[node.node_info.id] = node
        logger.info(f"添加编译节点: {node.node_info.id}")

    def remove_node(self, node_id: str) -> bool:
        """移除编译节点"""
        if node_id in self.nodes:
            node = self.nodes[node_id]

            # 取消该节点的所有任务
            for task_id in list(node.running_tasks.keys()):
                node.cancel_task(task_id)

            # 移除节点
            del self.nodes[node_id]
            logger.info(f"移除编译节点: {node_id}")
            return True
        return False

    def submit_task(self, task: CompilationTask) -> None:
        """提交编译任务"""
        self.tasks[task.id] = task

        # 添加到依赖图
        for dep_id in task.dependencies:
            self.dependency_graph.add_edge(dep_id, task.id)

        # 尝试调度任务
        self._schedule_task(task.id)

    def _schedule_task(self, task_id: str) -> None:
        """调度单个任务"""
        if task_id not in self.tasks:
            return

        task = self.tasks[task_id]

        # 检查依赖是否完成
        for dep_id in task.dependencies:
            if dep_id not in self.tasks:
                logger.error(f"任务 {task_id} 的依赖 {dep_id} 不存在")
                return

            dep_task = self.tasks[dep_id]
            if dep_task.status != "completed":
                logger.debug(f"任务 {task_id} 的依赖 {dep_id} 未完成")
                return

        # 选择合适的节点
        node = self._select_node(task)
        if not node:
            logger.debug(f"没有合适的节点执行任务 {task_id}")
            return

        # 分配任务到节点
        task.assigned_node = node.node_info.id
        task.status = "running"
        task.start_time = time.time()
        node.node_info.current_tasks.add(task_id)

        # 创建异步任务
        async def run_task():
            try:
                result = await node.execute_task(task)
                self.tasks[task_id] = task
                logger.info(f"任务 {task_id} 完成")

                # 尝试调度依赖该任务的其他任务
                for dependent_id in list(self.dependency_graph.successors(task_id)):
                    self._schedule_task(dependent_id)

            except Exception as e:
                logger.error(f"任务 {task_id} 执行失败: {e}")
                task.status = "failed"
                self.tasks[task_id] = task

        # 运行任务
        asyncio.create_task(run_task())

    def _select_node(self, task: CompilationTask) -> Optional[CompilerNode]:
        """选择合适的节点"""
        candidate_nodes = []

        # 筛选符合条件的节点
        for node in self.nodes.values():
            # 检查节点状态
            if node.node_info.status != "active":
                continue

            # 检查并发任务数
            if len(node.node_info.current_tasks) >= node.node_info.capability.max_concurrent_tasks:
                continue

            # 检查目标平台支持
            if task.options.get("target") not in node.node_info.capability.supported_targets:
                continue

            # 检查优化支持
            required_opts = task.options.get("optimizations", [])
            if not all(opt in node.node_info.capability.supported_optimizations for opt in required_opts):
                continue

            candidate_nodes.append(node)

        if not candidate_nodes:
            return None

        # 根据负载均衡策略选择节点
        if self.load_balancing_strategy == "round_robin":
            # 轮询策略
            return candidate_nodes[len(self.tasks) % len(candidate_nodes)]

        elif self.load_balancing_strategy == "least_loaded":
            # 最少负载策略
            return min(candidate_nodes, key=lambda n: len(n.node_info.current_tasks))

        elif self.load_balancing_strategy == "random":
            # 随机策略
            import random
            return random.choice(candidate_nodes)

        else:
            # 默认策略
            return candidate_nodes[0]

    def get_task_status(self, task_id: str) -> Optional[str]:
        """获取任务状态"""
        if task_id in self.tasks:
            return self.tasks[task_id].status
        return None

    def get_task_result(self, task_id: str) -> Optional[Any]:
        """获取任务结果"""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            if task.status == "completed":
                return task.result
        return None

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        if task_id not in self.tasks:
            return False

        task = self.tasks[task_id]
        if task.status != "running":
            return False

        # 从节点取消任务
        if task.assigned_node and task.assigned_node in self.nodes:
            self.nodes[task.assigned_node].cancel_task(task_id)

        # 更新任务状态
        task.status = "cancelled"
        task.end_time = time.time()

        return True

    def list_tasks(self, status: Optional[str] = None) -> List[CompilationTask]:
        """列出任务"""
        tasks = list(self.tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return tasks

    def list_nodes(self, status: Optional[str] = None) -> List[CompilerNode]:
        """列出节点"""
        nodes = list(self.nodes.values())
        if status:
            nodes = [n for n in nodes if n.node_info.status == status]
        return nodes

    def update_node_status(self, node_id: str, status: str) -> bool:
        """更新节点状态"""
        if node_id in self.nodes:
            self.nodes[node_id].node_info.status = status
            return True
        return False

    def update_node_heartbeat(self, node_id: str, node_info: NodeInfo) -> bool:
        """更新节点心跳"""
        if node_id in self.nodes:
            self.nodes[node_id].node_info = node_info
            return True
        return False

    def check_node_health(self, timeout: float = 30.0) -> None:
        """检查节点健康状态"""
        current_time = time.time()
        for node in self.nodes.values():
            if current_time - node.node_info.last_heartbeat > timeout:
                logger.warning(f"节点 {node.node_info.id} 心跳超时")
                node.node_info.status = "inactive"

    def set_load_balancing_strategy(self, strategy: str) -> None:
        """设置负载均衡策略"""
        if strategy in ["round_robin", "least_loaded", "random"]:
            self.load_balancing_strategy = strategy
        else:
            logger.error(f"不支持的负载均衡策略: {strategy}")


class DistributedCompiler:
    """分布式编译器 - 核心组件"""

    def __init__(self) -> None:
        """初始化分布式编译器"""
        self.scheduler = TaskScheduler()
        self.is_running = False

    def add_node(self, node: CompilerNode) -> None:
        """添加编译节点"""
        self.scheduler.add_node(node)

    def remove_node(self, node_id: str) -> bool:
        """移除编译节点"""
        return self.scheduler.remove_node(node_id)

    def submit_task(self, task: CompilationTask) -> str:
        """提交编译任务"""
        self.scheduler.submit_task(task)
        return task.id

    def get_task_status(self, task_id: str) -> Optional[str]:
        """获取任务状态"""
        return self.scheduler.get_task_status(task_id)

    def get_task_result(self, task_id: str) -> Optional[Any]:
        """获取任务结果"""
        return self.scheduler.get_task_result(task_id)

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        return self.scheduler.cancel_task(task_id)

    def list_tasks(self, status: Optional[str] = None) -> List[CompilationTask]:
        """列出任务"""
        return self.scheduler.list_tasks(status)

    def list_nodes(self, status: Optional[str] = None) -> List[CompilerNode]:
        """列出节点"""
        return self.scheduler.list_nodes(status)

    def update_node_status(self, node_id: str, status: str) -> bool:
        """更新节点状态"""
        return self.scheduler.update_node_status(node_id, status)

    def update_node_heartbeat(self, node_id: str, node_info: NodeInfo) -> bool:
        """更新节点心跳"""
        return self.scheduler.update_node_heartbeat(node_id, node_info)

    def check_node_health(self, timeout: float = 30.0) -> None:
        """检查节点健康状态"""
        self.scheduler.check_node_health(timeout)

    def set_load_balancing_strategy(self, strategy: str) -> None:
        """设置负载均衡策略"""
        self.scheduler.set_load_balancing_strategy(strategy)

    def start(self) -> None:
        """启动分布式编译器"""
        self.is_running = True
        logger.info("分布式编译器已启动")

    def stop(self) -> None:
        """停止分布式编译器"""
        self.is_running = False
        logger.info("分布式编译器已停止")


# 全局分布式编译器实例
_global_distributed_compiler = None


def get_distributed_compiler() -> DistributedCompiler:
    """获取全局分布式编译器"""
    global _global_distributed_compiler
    if _global_distributed_compiler is None:
        _global_distributed_compiler = DistributedCompiler()
    return _global_distributed_compiler


def add_node(node: CompilerNode) -> None:
    """添加编译节点"""
    compiler = get_distributed_compiler()
    compiler.add_node(node)


def remove_node(node_id: str) -> bool:
    """移除编译节点"""
    compiler = get_distributed_compiler()
    return compiler.remove_node(node_id)


def submit_task(task: CompilationTask) -> str:
    """提交编译任务"""
    compiler = get_distributed_compiler()
    return compiler.submit_task(task)


def get_task_status(task_id: str) -> Optional[str]:
    """获取任务状态"""
    compiler = get_distributed_compiler()
    return compiler.get_task_status(task_id)


def get_task_result(task_id: str) -> Optional[Any]:
    """获取任务结果"""
    compiler = get_distributed_compiler()
    return compiler.get_task_result(task_id)


def cancel_task(task_id: str) -> bool:
    """取消任务"""
    compiler = get_distributed_compiler()
    return compiler.cancel_task(task_id)


def list_tasks(status: Optional[str] = None) -> List[CompilationTask]:
    """列出任务"""
    compiler = get_distributed_compiler()
    return compiler.list_tasks(status)


def list_nodes(status: Optional[str] = None) -> List[CompilerNode]:
    """列出节点"""
    compiler = get_distributed_compiler()
    return compiler.list_nodes(status)


def start_distributed_compiler() -> None:
    """启动分布式编译器"""
    compiler = get_distributed_compiler()
    compiler.start()


def stop_distributed_compiler() -> None:
    """停止分布式编译器"""
    compiler = get_distributed_compiler()
    compiler.stop()
