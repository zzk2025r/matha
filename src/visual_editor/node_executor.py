"""Matha 可视化编程器 - 节点执行引擎

支持拓扑排序执行节点图：
  - 检测循环依赖
  - 拓扑排序计算执行顺序
  - 增量执行（只执行变更节点）
  - 错误处理和恢复
  - 执行监控和日志
"""
from __future__ import annotations

import logging
import math
import time
from collections import deque
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ExecutionStatus(Enum):
    """执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class ExecutionError(Exception):
    """执行错误"""
    def __init__(self, message: str, node_id: str | None = None, port_name: str | None = None):
        super().__init__(message)
        self.node_id = node_id
        self.port_name = port_name


class NodeExecutionResult:
    """节点执行结果"""
    def __init__(
        self,
        node_id: str,
        node_type: str,
        status: ExecutionStatus,
        output: dict[str, Any] | None = None,
        error: str | None = None,
        duration_ms: float = 0.0,
    ):
        self.node_id = node_id
        self.node_type = node_type
        self.status = status
        self.output = output or {}
        self.error = error
        self.duration_ms = duration_ms
        self.timestamp = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            'node_id': self.node_id,
            'node_type': self.node_type,
            'status': self.status.value,
            'output': self.output,
            'error': self.error,
            'duration_ms': self.duration_ms,
            'timestamp': self.timestamp,
        }


class GraphMetrics:
    """图指标统计"""
    def __init__(self):
        self.total_nodes = 0
        self.total_edges = 0
        self.max_depth = 0
        self.max_width = 0
        self.has_cycles = False
        self.execution_order: list[str] = []

    def to_dict(self) -> dict[str, Any]:
        return {
            'total_nodes': self.total_nodes,
            'total_edges': self.total_edges,
            'max_depth': self.max_depth,
            'max_width': self.max_width,
            'has_cycles': self.has_cycles,
            'execution_order': self.execution_order,
        }


class NodeExecutor:
    """
    节点执行器

    负责：
    1. 图结构验证（检测循环依赖）
    2. 拓扑排序计算执行顺序
    3. 执行节点并传递数据
    4. 错误处理和恢复
    """

    def __init__(self):
        self._nodes: dict[str, Any] = {}
        self._connections: list[dict[str, str]] = []
        self._execution_order: list[str] = []
        self._metrics = GraphMetrics()
        self._execution_history: list[NodeExecutionResult] = []
        self._on_node_execute = None
        self._on_execution_complete = None
        self._on_error = None

        # 断点调试
        self._breakpoints: dict[str, dict[str, Any]] = {}
        self._paused_at: str | None = None
        self._last_summary: dict[str, Any] | None = None
        self._last_outputs: dict[str, dict[str, Any]] = {}
        self._last_results: dict[str, NodeExecutionResult] = {}

        # 执行缓存
        self._cache: dict[tuple, NodeExecutionResult] = {}
        self._cache_enabled = False
        self._cache_hits = 0
        self._cache_misses = 0

        # 撤销/重做（图快照）
        self._undo_stack: list[dict[str, Any]] = []
        self._redo_stack: list[dict[str, Any]] = []

        # 性能统计
        self._perf_stats: dict[str, dict[str, float]] = {}

    def add_node(self, node_id: str, node_data: dict[str, Any]) -> None:
        """添加节点"""
        self._nodes[node_id] = node_data
        self._metrics.total_nodes = len(self._nodes)
        self._invalidate_cache(node_id)
        self._redo_stack.clear()
        logger.debug(f"添加节点: {node_id} ({node_data.get('type', 'unknown')})")

    def add_connection(self, from_node: str, from_port: str, to_node: str, to_port: str) -> None:
        """添加连线"""
        logger.info(f"[执行引擎] 添加连线: {from_node}.{from_port} -> {to_node}.{to_port}")
        self._connections.append({
            'from': from_node,
            'from_port': from_port,
            'to': to_node,
            'to_port': to_port,
        })
        self._metrics.total_edges = len(self._connections)
        self._invalidate_cache(to_node)
        self._redo_stack.clear()
        logger.debug(f"[执行引擎] 当前连线数: {self._metrics.total_edges}")

    def remove_node(self, node_id: str) -> bool:
        """移除节点"""
        if node_id in self._nodes:
            del self._nodes[node_id]
            self._connections = [
                c for c in self._connections
                if c['from'] != node_id and c['to'] != node_id
            ]
            self._metrics.total_nodes = len(self._nodes)
            self._metrics.total_edges = len(self._connections)
            self._invalidate_cache(node_id)
            self._redo_stack.clear()
            return True
        return False

    def remove_connection(self, from_node: str, from_port: str, to_node: str, to_port: str) -> bool:
        """移除连线"""
        for i, conn in enumerate(self._connections):
            if (conn['from'] == from_node and conn['from_port'] == from_port and
                conn['to'] == to_node and conn['to_port'] == to_port):
                self._connections.pop(i)
                self._metrics.total_edges = len(self._connections)
                self._invalidate_cache(to_node)
                self._redo_stack.clear()
                return True
        return False

    def _invalidate_cache(self, node_id: str | None = None) -> None:
        """使缓存失效（指定节点或全部）"""
        if not self._cache:
            return
        if node_id is None:
            self._cache.clear()
        else:
            for key in [k for k in self._cache if k[0] == node_id]:
                self._cache.pop(key, None)

    def clear(self) -> None:
        """清空图"""
        self._nodes.clear()
        self._connections.clear()
        self._execution_order.clear()
        self._execution_history.clear()
        self._metrics = GraphMetrics()

    def validate_graph(self) -> tuple[bool, str | None]:
        """
        验证图结构

        Returns:
            (是否有效, 错误信息)
        """
        logger.info(f"[执行引擎] 开始验证图结构 (节点: {len(self._nodes)}, 连线: {len(self._connections)})")

        # 检查孤立节点（无输入无输出）
        connected_nodes = set()
        for conn in self._connections:
            connected_nodes.add(conn['from'])
            connected_nodes.add(conn['to'])

        # 检查循环依赖
        has_cycle, cycle_path = self._detect_cycle()
        if has_cycle:
            logger.error(f"[执行引擎] 检测到循环依赖: {' -> '.join(cycle_path)}")
            return False, f"检测到循环依赖: {' -> '.join(cycle_path)}"

        logger.info("[执行引擎] 循环依赖检查通过")

        # 检查断开的连线
        missing_nodes = []
        for conn in self._connections:
            if conn['from'] not in self._nodes:
                missing_nodes.append(f"连线来源节点 {conn['from']} 不存在")
            if conn['to'] not in self._nodes:
                missing_nodes.append(f"连线目标节点 {conn['to']} 不存在")

        if missing_nodes:
            logger.error(f"[执行引擎] 发现断开连线: {missing_nodes}")
            return False, "; ".join(missing_nodes)

        logger.info("[执行引擎] 图结构验证通过")
        return True, None

    def _detect_cycle(self) -> tuple[bool, list[str]]:
        """检测图中是否有循环"""
        visited = set()
        rec_stack = set()
        path = []

        def dfs(node_id: str) -> tuple[bool, list[str]]:
            visited.add(node_id)
            rec_stack.add(node_id)
            path.append(node_id)

            # 查找从当前节点出发的连线
            for conn in self._connections:
                if conn['from'] == node_id:
                    next_node = conn['to']
                    if next_node not in visited:
                        has_cycle, cycle_path = dfs(next_node)
                        if has_cycle:
                            return True, cycle_path
                    elif next_node in rec_stack:
                        # 找到循环
                        cycle_start = path.index(next_node)
                        return True, path[cycle_start:] + [next_node]

            path.pop()
            rec_stack.remove(node_id)
            return False, []

        for node_id in self._nodes:
            if node_id not in visited:
                has_cycle, cycle_path = dfs(node_id)
                if has_cycle:
                    return True, cycle_path

        return False, []

    def compute_execution_order(self) -> list[str]:
        """
        计算拓扑排序执行顺序

        使用 Kahn 算法：
        1. 计算每个节点的入度
        2. 将入度为 0 的节点加入队列
        3. 依次处理队列中的节点，减少相邻节点的入度
        4. 重复直到队列为空
        """
        # 计算入度
        in_degree = dict.fromkeys(self._nodes, 0)
        adjacency = {node_id: [] for node_id in self._nodes}

        for conn in self._connections:
            if conn['from'] in adjacency and conn['to'] in in_degree:
                adjacency[conn['from']].append(conn['to'])
                in_degree[conn['to']] += 1

        # 初始化队列（入度为 0 的节点）
        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
        execution_order = []

        while queue:
            # 按节点 ID 排序，保证确定性
            node_ids = sorted(queue)
            queue.clear()

            for node_id in node_ids:
                execution_order.append(node_id)

                for neighbor in adjacency[node_id]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)

        # 检查是否所有节点都已处理
        if len(execution_order) != len(self._nodes):
            logger.warning(f"拓扑排序未完成，{len(self._nodes) - len(execution_order)} 个节点未处理")

        self._execution_order = execution_order
        self._metrics.execution_order = execution_order
        return execution_order

    def execute(
        self,
        node_executor: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        parallel: bool = False,
        max_workers: int = 4,
        use_cache: bool = False,
    ) -> dict[str, Any]:
        """
        执行整个节点图

        Args:
            node_executor: 节点执行函数字典 {node_type: func}
            context: 执行上下文（共享数据）
            parallel: 是否并行执行无依赖节点
            max_workers: 并行工作线程数
            use_cache: 是否启用结果缓存

        Returns:
            执行结果摘要
        """
        logger.info("[执行引擎] ========== 开始执行节点图 ==========")

        if context is None:
            context = {}

        self._cache_enabled = use_cache
        self._paused_at = None

        # 验证图
        is_valid, error_msg = self.validate_graph()
        if not is_valid:
            logger.error(f"[执行引擎] 图验证失败: {error_msg}")
            return {
                'status': 'error',
                'error': error_msg,
                'results': [],
            }

        logger.info("[执行引擎] 图验证通过，开始计算执行顺序...")

        # 计算执行顺序
        execution_order = self.compute_execution_order()
        if not execution_order:
            logger.warning("[执行引擎] 没有可执行的节点")
            return {
                'status': 'empty',
                'results': [],
            }

        logger.info(f"[执行引擎] 执行顺序已确定: {execution_order}")

        # 执行节点
        results = []
        start_time = time.time()

        if parallel:
            # 并行执行模式
            results = self._execute_parallel(execution_order, node_executor, context, max_workers)
        else:
            # 顺序执行模式
            results = self._execute_sequential(execution_order, node_executor, context)

        total_duration = (time.time() - start_time) * 1000
        self._execution_history.extend(results)

        # 记录本次运行状态（用于错误恢复/断点续跑）
        self._last_results = {r.node_id: r for r in results}
        self._last_outputs = {r.node_id: r.output for r in results if r.status == ExecutionStatus.SUCCESS}

        # 统计结果
        success_count = len([r for r in results if r.status == ExecutionStatus.SUCCESS])
        failed_count = len([r for r in results if r.status == ExecutionStatus.FAILED])
        paused = self._paused_at is not None

        logger.info("[执行引擎] ========== 执行完成 ==========")
        logger.info(f"[执行引擎] 总节点数: {len(self._nodes)}, 成功: {success_count}, 失败: {failed_count}, 暂停: {paused}, 总耗时: {total_duration:.2f}ms")

        # 通知完成回调
        if self._on_execution_complete:
            self._on_execution_complete(results, total_duration)

        summary = {
            'status': 'paused' if paused else ('success' if failed_count == 0 else 'partial_success'),
            'total_nodes': len(self._nodes),
            'executed_nodes': success_count,
            'failed_nodes': failed_count,
            'paused_at': self._paused_at,
            'total_duration_ms': total_duration,
            'results': [r.to_dict() for r in results],
        }
        self._last_summary = summary
        return summary

    def _execute_sequential(
        self,
        execution_order: list[str],
        node_executor: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[NodeExecutionResult]:
        """顺序执行节点（支持断点暂停与结果缓存）"""
        results = []
        node_outputs = {node_id: {} for node_id in self._nodes}

        for i, node_id in enumerate(execution_order):
            node_data = self._nodes[node_id]
            node_type = node_data.get('type', 'unknown')

            logger.info(f"[执行引擎] 执行节点 [{i+1}/{len(execution_order)}]: {node_id} ({node_type})")

            # 获取节点执行函数
            execute_func = node_executor.get(node_type) if node_executor else None
            if execute_func is None:
                execute_func = self._default_execute

            # 准备输入
            inputs = self._collect_inputs(node_id, node_outputs)
            inputs.update(context.get('inputs', {}))

            # 断点暂停
            if node_id in self._breakpoints and self._breakpoints.get(node_id, {}).get('enabled', True):
                if self._breakpoint_matches(node_id, inputs):
                    self._paused_at = node_id
                    results.append(NodeExecutionResult(
                        node_id=node_id,
                        node_type=node_type,
                        status=ExecutionStatus.PAUSED,
                        error=f"命中断点: {node_id}",
                    ))
                    logger.info(f"[执行引擎] 节点 {node_id} 命中断点，执行暂停")
                    break

            result = self._run_node(node_id, node_type, execute_func, inputs, context)
            results.append(result)

            if result.status == ExecutionStatus.SUCCESS:
                node_outputs[node_id] = result.output
                logger.info(f"[执行引擎] 节点 {node_id} 执行成功，输出: {result.output} (耗时: {result.duration_ms:.2f}ms)")
            else:
                logger.error(f"[执行引擎] 节点 {node_id} 执行失败: {result.error}")

                if self._on_error:
                    self._on_error(node_id, node_type, result.error)

            if self._on_node_execute:
                self._on_node_execute(node_id, node_type, result.output)

        return results

    def _execute_parallel(
        self,
        execution_order: list[str],
        node_executor: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        max_workers: int = 4,
    ) -> list[NodeExecutionResult]:
        """并行执行节点（基于层级的并行）"""

        # 计算层级（同一层级的节点可以并行执行）
        levels = self._compute_execution_levels(execution_order)
        logger.info(f"[执行引擎] 并行执行模式，共 {len(levels)} 个层级")

        results = []
        node_outputs = {node_id: {} for node_id in self._nodes}

        for level_idx, level_nodes in enumerate(levels):
            logger.info(f"[执行引擎] 并行执行层级 {level_idx+1}/{len(levels)}: {level_nodes}")

            with ThreadPoolExecutor(max_workers=min(max_workers, len(level_nodes))) as executor:
                future_to_node = {}

                for node_id in level_nodes:
                    node_data = self._nodes[node_id]
                    node_type = node_data.get('type', 'unknown')

                    execute_func = node_executor.get(node_type) if node_executor else None
                    if execute_func is None:
                        execute_func = self._default_execute

                    # 收集输入（同一层级的节点可以同时读取上一层级的输出）
                    inputs = self._collect_inputs(node_id, node_outputs)
                    inputs.update(context.get('inputs', {}))

                    future = executor.submit(self._execute_single_node, node_id, node_type, execute_func, inputs, context)
                    future_to_node[future] = node_id

                # 收集结果
                for future in as_completed(future_to_node):
                    node_id = future_to_node[future]
                    try:
                        result = future.result()
                        results.append(result)
                        if result.status == ExecutionStatus.SUCCESS:
                            node_outputs[node_id] = result.output
                            logger.info(f"[执行引擎] 节点 {node_id} 执行成功 (层级 {level_idx+1})")
                        elif result.status == ExecutionStatus.PAUSED:
                            self._paused_at = node_id
                            logger.info(f"[执行引擎] 节点 {node_id} 命中断点，执行暂停")
                        else:
                            logger.error(f"[执行引擎] 节点 {node_id} 执行失败: {result.error}")
                    except Exception as e:
                        logger.error(f"[执行引擎] 节点 {node_id} 异常: {e}")
                        results.append(NodeExecutionResult(
                            node_id=node_id,
                            node_type=self._nodes[node_id].get('type', 'unknown'),
                            status=ExecutionStatus.FAILED,
                            error=str(e),
                        ))

                if self._paused_at is not None:
                    break

        return results

    def _compute_execution_levels(self, execution_order: list[str]) -> list[list[str]]:
        """计算执行层级（同一层级可并行执行）"""
        # 计算每个节点的层级（基于最长路径）
        levels_dict = {}

        for node_id in execution_order:
            # 找到所有前驱节点
            predecessors = [conn['from'] for conn in self._connections if conn['to'] == node_id]
            if not predecessors:
                level = 0
            else:
                level = max(levels_dict.get(p, 0) for p in predecessors) + 1
            levels_dict[node_id] = level

        # 按层级分组
        max_level = max(levels_dict.values()) if levels_dict else 0
        levels = [[] for _ in range(max_level + 1)]
        for node_id, level in levels_dict.items():
            levels[level].append(node_id)

        return [level for level in levels if level]

    def _execute_single_node(
        self,
        node_id: str,
        node_type: str,
        execute_func: Callable,
        inputs: dict,
        context: dict,
    ) -> NodeExecutionResult:
        """执行单个节点（用于并行执行）"""
        if node_id in self._breakpoints and self._breakpoints.get(node_id, {}).get('enabled', True):
            if self._breakpoint_matches(node_id, inputs):
                self._paused_at = node_id
                return NodeExecutionResult(
                    node_id=node_id,
                    node_type=node_type,
                    status=ExecutionStatus.PAUSED,
                    error=f"命中断点: {node_id}",
                )
        return self._run_node(node_id, node_type, execute_func, inputs, context)

    def execute_incremental(
        self,
        changed_node_ids: set[str],
        node_executor: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        增量执行（只执行变更节点及其依赖）

        Args:
            changed_node_ids: 发生变更的节点 ID 集合
            node_executor: 节点执行函数字典
            context: 执行上下文

        Returns:
            执行结果摘要
        """
        # 找出受影响的节点（变更节点的下游依赖）
        affected_nodes = self._get_affected_nodes(changed_node_ids)

        # 只执行受影响的节点
        original_nodes = self._nodes.copy()
        original_connections = self._connections.copy()

        # 临时只保留受影响的节点
        self._nodes = {nid: data for nid, data in self._nodes.items() if nid in affected_nodes}

        result = self.execute(node_executor, context)

        # 恢复原始状态
        self._nodes = original_nodes
        self._connections = original_connections

        return result

    def _get_affected_nodes(self, changed_node_ids: set[str]) -> set[str]:
        """获取受影响的节点（变更节点及其下游依赖）"""
        affected = set(changed_node_ids)
        queue = deque(changed_node_ids)

        while queue:
            node_id = queue.popleft()

            # 找出所有从该节点出发的连线
            for conn in self._connections:
                if conn['from'] == node_id and conn['to'] in self._nodes:
                    if conn['to'] not in affected:
                        affected.add(conn['to'])
                        queue.append(conn['to'])

        return affected

    def _collect_inputs(self, node_id: str, node_outputs: dict[str, dict]) -> dict[str, Any]:
        """收集节点的输入值"""
        inputs = {}
        self._nodes.get(node_id, {})

        for conn in self._connections:
            if conn['to'] == node_id:
                from_output = node_outputs.get(conn['from'], {})
                inputs[conn['to_port']] = from_output.get(conn['from_port'])

        return inputs

    def _default_execute(self, node_data: dict, inputs: dict, context: dict) -> dict:
        """默认节点执行函数"""
        node_type = node_data.get('type', 'unknown')
        output = {}

        # 根据节点类型执行不同逻辑
        if node_type.startswith('math_'):
            output = self._execute_math_node(node_type, inputs)
        elif node_type.startswith('logic_'):
            output = self._execute_logic_node(node_type, inputs)
        elif node_type.startswith('stats_'):
            output = self._execute_stats_node(node_type, inputs)
        elif node_type.startswith('matrix_'):
            output = self._execute_matrix_node(node_type, inputs)
        elif node_type.startswith('file_'):
            output = self._execute_file_node(node_type, node_data, inputs)
        elif node_type.startswith('net_'):
            output = self._execute_network_node(node_type, node_data, inputs)
        elif node_type.startswith('db_'):
            output = self._execute_db_node(node_type, node_data, inputs)
        elif node_type.startswith('image_'):
            output = self._execute_image_node(node_type, inputs)
        elif node_type.startswith('audio_'):
            output = self._execute_audio_node(node_type, inputs)
        elif node_type in ('input', 'output', 'variable', 'assign', 'if', 'sequence', 'constant'):
            output = self._execute_special_node(node_type, node_data, inputs)

        return output

    def _execute_math_node(self, node_type: str, inputs: dict) -> dict:
        """执行数学运算节点"""
        a = inputs.get('a', 0)
        b = inputs.get('b', 0)
        result = 0

        try:
            if node_type == 'math_pi':
                return {'value': math.pi}
            elif node_type == 'math_e':
                return {'value': math.e}
            elif node_type == 'math_add':
                result = a + b
            elif node_type == 'math_subtract':
                result = a - b
            elif node_type == 'math_multiply':
                result = a * b
            elif node_type == 'math_divide':
                result = a / b if b != 0 else float('inf')
            elif node_type == 'math_power':
                result = a ** b
            elif node_type == 'math_sqrt':
                result = math.sqrt(a) if a >= 0 else float('nan')
            elif node_type == 'math_abs':
                result = abs(a)
            elif node_type == 'math_floor':
                result = math.floor(a)
            elif node_type == 'math_ceil':
                result = math.ceil(a)
            elif node_type == 'math_modulo':
                result = a % b if b != 0 else float('nan')
            elif node_type == 'math_sin':
                result = math.sin(a)
            elif node_type == 'math_cos':
                result = math.cos(a)
            elif node_type == 'math_tan':
                result = math.tan(a)
            elif node_type == 'math_log':
                result = math.log(a) if a > 0 else float('nan')
            elif node_type == 'math_log2':
                result = math.log2(a) if a > 0 else float('nan')
            elif node_type == 'math_log10':
                result = math.log10(a) if a > 0 else float('nan')
            elif node_type == 'math_exp':
                result = math.exp(a)
            elif node_type == 'math_pi':
                result = math.pi
            elif node_type == 'math_e':
                result = math.e
        except Exception as e:
            raise ExecutionError(f"数学运算错误: {e}")

        return {'result': result}

    def _execute_logic_node(self, node_type: str, inputs: dict) -> dict:
        """执行逻辑运算节点"""
        a = inputs.get('a', False)
        b = inputs.get('b', False)
        result = False

        try:
            if node_type == 'logic_and':
                result = a and b
            elif node_type == 'logic_or':
                result = a or b
            elif node_type == 'logic_not':
                result = not a
            elif node_type == 'logic_equal':
                result = a == b
            elif node_type == 'logic_not_equal':
                result = a != b
            elif node_type == 'logic_less':
                result = a < b
            elif node_type == 'logic_greater':
                result = a > b
            elif node_type == 'logic_less_equal':
                result = a <= b
            elif node_type == 'logic_greater_equal':
                result = a >= b
        except Exception as e:
            raise ExecutionError(f"逻辑运算错误: {e}")

        return {'result': result}

    def _execute_stats_node(self, node_type: str, inputs: dict) -> dict:
        """执行统计节点"""
        data = inputs.get('data', [])
        result = 0

        try:
            if node_type == 'stats_mean':
                result = sum(data) / len(data) if data else 0
            elif node_type == 'stats_variance':
                if data:
                    mean = sum(data) / len(data)
                    result = sum((x - mean) ** 2 for x in data) / len(data)
            elif node_type == 'stats_std':
                if data:
                    mean = sum(data) / len(data)
                    variance = sum((x - mean) ** 2 for x in data) / len(data)
                    result = math.sqrt(variance)
            elif node_type == 'stats_sum':
                result = sum(data)
            elif node_type == 'stats_min':
                result = min(data) if data else 0
            elif node_type == 'stats_max':
                result = max(data) if data else 0
        except Exception as e:
            raise ExecutionError(f"统计运算错误: {e}")

        return {'result': result}

    def _execute_matrix_node(self, node_type: str, inputs: dict) -> dict:
        """执行矩阵运算节点"""
        matrix = inputs.get('matrix', [])
        result = []

        try:
            if node_type == 'matrix_create':
                result = inputs.get('data', [[1, 0], [0, 1]])
            elif node_type == 'matrix_transpose':
                if matrix:
                    result = [[matrix[row][col] for row in range(len(matrix))]
                              for col in range(len(matrix[0]))]
            elif node_type == 'matrix_determinant':
                # 简化：2x2 矩阵行列式
                if len(matrix) == 2 and len(matrix[0]) == 2:
                    result = matrix[0][0] * matrix[1][1] - matrix[0][1] * matrix[1][0]
                else:
                    result = 1
            elif node_type == 'matrix_inverse':
                # 简化：返回原矩阵
                result = matrix
            elif node_type == 'matrix_multiply':
                # 简化：返回第一个矩阵
                result = inputs.get('a', [])
        except Exception as e:
            raise ExecutionError(f"矩阵运算错误: {e}")

        return {'result': result}

    def _execute_special_node(self, node_type: str, node_data: dict, inputs: dict) -> dict:
        """执行特殊节点"""
        if node_type == 'input':
            return {'value': node_data.get('default_value')}
        elif node_type == 'output':
            return {}
        elif node_type == 'variable' or node_type == 'assign':
            var_name = node_data.get('var_name', 'x')
            return {var_name: inputs.get('value')}
        elif node_type == 'if':
            condition = inputs.get('condition', False)
            if condition:
                return {'result': inputs.get('true_value')}
            else:
                return {'result': inputs.get('false_value')}
        elif node_type == 'sequence':
            start = inputs.get('start', 0)
            end = inputs.get('end', 10)
            step = inputs.get('step', 1)
            return {'sequence': list(range(int(start), int(end), int(step)))}
        elif node_type == 'constant':
            return {'value': node_data.get('value')}

        return {}

    def _execute_file_node(self, node_type: str, node_data: dict, inputs: dict) -> dict:
        """执行文件操作节点"""
        import os
        path = node_data.get('config', {}).get('path', '')
        if node_type == 'file_read':
            if not path:
                raise ExecutionError("文件路径未配置")
            with open(path, encoding='utf-8') as f:
                return {'content': f.read()}
        elif node_type == 'file_write':
            content = inputs.get('content', '')
            if not path:
                raise ExecutionError("文件路径未配置")
            with open(path, 'w', encoding='utf-8') as f:
                f.write(str(content))
            return {'written': True}
        elif node_type == 'file_list':
            return {'files': sorted(name for name in os.listdir(path) if not name.startswith('.'))}
        elif node_type == 'file_delete':
            if os.path.isdir(path):
                os.rmdir(path)
            else:
                os.remove(path)
            return {'deleted': True}
        return {}

    def _execute_network_node(self, node_type: str, node_data: dict, inputs: dict) -> dict:
        """执行网络请求节点"""
        import json
        import urllib.request
        url = node_data.get('config', {}).get('url', '')
        if not url:
            raise ExecutionError("URL 未配置")
        if node_type == 'net_http_get':
            timeout = float(node_data.get('config', {}).get('timeout', 5.0))
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                return {'status': resp.status, 'body': resp.read().decode('utf-8', errors='replace')}
        elif node_type == 'net_http_post':
            data = inputs.get('body')
            body = json.dumps(data) if isinstance(data, (dict, list)) else str(data)
            req = urllib.request.Request(
                url,
                data=body.encode('utf-8'),
                headers={'Content-Type': 'application/json'},
            )
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                return {'status': resp.status, 'body': resp.read().decode('utf-8', errors='replace')}
        return {}

    def _execute_db_node(self, node_type: str, node_data: dict, inputs: dict) -> dict:
        """执行数据库操作节点"""
        import sqlite3
        path = node_data.get('config', {}).get('path', ':memory:')
        sql = inputs.get('sql', '')
        if node_type == 'db_query':
            conn = sqlite3.connect(path)
            try:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(sql)
                rows = [dict(row) for row in cursor.fetchall()]
                columns = [d[0] for d in cursor.description] if cursor.description else []
                return {'rows': rows, 'columns': columns}
            finally:
                conn.close()
        elif node_type == 'db_execute':
            conn = sqlite3.connect(path)
            try:
                cursor = conn.execute(sql)
                conn.commit()
                return {'rowcount': cursor.rowcount}
            finally:
                conn.close()
        return {}

    def _execute_image_node(self, node_type: str, inputs: dict) -> dict:
        """执行图像处理节点（图像为 {width,height,pixels} 字典）"""
        img = inputs.get('image')
        if not isinstance(img, dict) or 'pixels' not in img:
            raise ExecutionError("输入不是有效图像（需 {width,height,pixels} 字典）")
        w, h, pixels = img['width'], img['height'], img['pixels']
        if node_type == 'image_grayscale':
            out = []
            for i in range(w * h):
                r, g, b = pixels[i * 3], pixels[i * 3 + 1], pixels[i * 3 + 2]
                gray = round(0.299 * r + 0.587 * g + 0.114 * b)
                out.extend([gray, gray, gray])
            return {'image': {'width': w, 'height': h, 'pixels': out}}
        elif node_type == 'image_invert':
            return {'image': {'width': w, 'height': h, 'pixels': [255 - v for v in pixels]}}
        elif node_type == 'image_brightness':
            factor = float(inputs.get('factor', 0))
            def _clamp(v):
                return max(0, min(255, round(v)))
            return {'image': {'width': w, 'height': h, 'pixels': [_clamp(v + factor) for v in pixels]}}
        elif node_type == 'image_resize':
            nw, nh = int(inputs.get('width', 100)), int(inputs.get('height', 100))
            if nw <= 0 or nh <= 0:
                raise ExecutionError(f"非法尺寸: {nw}x{nh}")
            out = []
            for y in range(nh):
                for x in range(nw):
                    sx = min(w - 1, x * w // nw)
                    sy = min(h - 1, y * h // nh)
                    idx = (sy * w + sx) * 3
                    out.extend(pixels[idx:idx + 3])
            return {'image': {'width': nw, 'height': nh, 'pixels': out}}
        return {}

    def _execute_audio_node(self, node_type: str, inputs: dict) -> dict:
        """执行音频处理节点（音频为 {sample_rate,samples} 字典）"""
        if node_type == 'audio_sine':
            freq = float(inputs.get('freq', 440.0))
            seconds = float(inputs.get('seconds', 1.0))
            rate = float(inputs.get('sample_rate', 16000.0))
            n = int(seconds * rate)
            samples = [round(math.sin(2 * math.pi * freq * i / rate), 6) for i in range(n)]
            return {'audio': {'sample_rate': int(rate), 'samples': samples}}

        audio = inputs.get('audio')
        if not isinstance(audio, dict) or 'samples' not in audio:
            raise ExecutionError("输入不是有效音频（需 {sample_rate,samples} 字典）")
        samples = audio['samples']
        rate = audio['sample_rate']
        if node_type == 'audio_volume':
            level = float(inputs.get('level', 1.0))
            return {'audio': {'sample_rate': rate, 'samples': [s * level for s in samples]}}
        elif node_type == 'audio_normalize':
            peak = max((abs(s) for s in samples), default=0.0)
            if peak == 0:
                return {'audio': {'sample_rate': rate, 'samples': samples}}
            scale = 1.0 / peak
            return {'audio': {'sample_rate': rate, 'samples': [s * scale for s in samples]}}
        elif node_type == 'audio_fade':
            n = len(samples)
            fade_n = max(1, n // 10)
            out = list(samples)
            for i in range(fade_n):
                env = i / fade_n
                out[i] *= env
                out[n - 1 - i] *= env
            return {'audio': {'sample_rate': rate, 'samples': out}}
        return {}

    def _run_node(
        self,
        node_id: str,
        node_type: str,
        execute_func: Callable,
        inputs: dict,
        context: dict,
    ) -> NodeExecutionResult:
        """执行单个节点（统一入口：缓存 + 性能统计 + 异常转换）"""
        node_data = self._nodes[node_id]

        # 缓存命中
        key = self._inputs_key(inputs)
        if self._cache_enabled and key is not None:
            cached = self._cache.get((node_id, key))
            if cached is not None:
                self._cache_hits += 1
                logger.debug(f"[执行引擎] 命中缓存: {node_id}")
                return NodeExecutionResult(
                    node_id=node_id,
                    node_type=node_type,
                    status=cached.status,
                    output=cached.output,
                    error=cached.error,
                    duration_ms=cached.duration_ms,
                )
            self._cache_misses += 1

        node_start = time.time()
        try:
            output = execute_func(node_data, inputs, context)
            duration = (time.time() - node_start) * 1000
            logger.debug(f"[执行引擎] 节点 {node_id} 执行成功 (耗时: {duration:.2f}ms)")
            result = NodeExecutionResult(
                node_id=node_id,
                node_type=node_type,
                status=ExecutionStatus.SUCCESS,
                output=output,
                duration_ms=duration,
            )
        except Exception as e:
            duration = (time.time() - node_start) * 1000
            logger.error(f"[执行引擎] 节点 {node_id} 执行失败: {e}")
            result = NodeExecutionResult(
                node_id=node_id,
                node_type=node_type,
                status=ExecutionStatus.FAILED,
                error=str(e),
                duration_ms=duration,
            )

        self._record_perf(node_id, node_type, result.duration_ms, result.status)
        if self._cache_enabled and key is not None and result.status == ExecutionStatus.SUCCESS:
            self._cache[(node_id, key)] = result
        return result

    def _inputs_key(self, inputs: dict) -> tuple | None:
        """生成输入缓存键"""
        try:
            return tuple(sorted((k, repr(v)) for k, v in (inputs or {}).items()))
        except Exception:
            return None

    def _record_perf(self, node_id: str, node_type: str, duration_ms: float, status: ExecutionStatus) -> None:
        """累计节点性能统计"""
        stat = self._perf_stats.setdefault(node_id, {'node_type': node_type, 'count': 0, 'total_ms': 0.0, 'max_ms': 0.0})
        stat['count'] += 1
        stat['total_ms'] += duration_ms
        stat['max_ms'] = max(stat['max_ms'], duration_ms)

    # ── 断点调试 API ──────────────────────────────────────────────────────────

    def set_breakpoint(self, node_id: str, enabled: bool = True, condition: str | None = None) -> None:
        """设置断点（可选 condition：按输入端口名判断真假）"""
        if node_id not in self._nodes:
            raise ValueError(f"节点不存在: {node_id}")
        self._breakpoints[node_id] = {'enabled': enabled, 'condition': condition}
        logger.info(f"[执行引擎] 设置断点: {node_id} (condition={condition})")

    def remove_breakpoint(self, node_id: str) -> bool:
        """移除断点"""
        return self._breakpoints.pop(node_id, None) is not None

    def clear_breakpoints(self) -> None:
        """清空所有断点"""
        self._breakpoints.clear()

    @property
    def breakpoints(self) -> dict[str, dict[str, Any]]:
        """获取断点列表"""
        return {nid: dict(bp) for nid, bp in self._breakpoints.items()}

    @property
    def paused_at(self) -> str | None:
        """最近一次暂停位置"""
        return self._paused_at

    def _breakpoint_matches(self, node_id: str, inputs: dict) -> bool:
        """判断断点条件是否满足（condition 为输入端口名时按输入值判断）"""
        condition = self._breakpoints.get(node_id, {}).get('condition')
        if not condition:
            return True
        return bool(inputs.get(condition, False))

    # ── 错误恢复 / 断点续跑 ───────────────────────────────────────────────────

    def resume(
        self,
        node_executor: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        从上次失败/暂停位置继续执行。

        仅重跑上一次执行中 FAILED/PAUSED 的节点及其下游依赖，
        未受影响节点的输出从上次成功结果中复用。
        """
        if context is None:
            context = {}
        start_time = time.time()

        target = {
            nid for nid, res in self._last_results.items()
            if res.status in (ExecutionStatus.FAILED, ExecutionStatus.PAUSED)
        }
        if not target:
            logger.info("[执行引擎] 没有需要恢复的节点")
            return {
                'status': 'idle',
                'total_nodes': len(self._nodes),
                'executed_nodes': 0,
                'failed_nodes': 0,
                'paused_at': None,
                'total_duration_ms': 0.0,
                'results': [r.to_dict() for r in self._last_results.values()],
            }

        affected = self._get_affected_nodes(target)
        order = [nid for nid in self.compute_execution_order() if nid in affected]
        logger.info(f"[执行引擎] 恢复执行节点: {order}")

        # 以成功节点输出作为种子输入
        node_outputs = {
            nid: res.output
            for nid, res in self._last_results.items()
            if res.status == ExecutionStatus.SUCCESS
        }

        new_results = {}
        for node_id in order:
            node_data = self._nodes[node_id]
            node_type = node_data.get('type', 'unknown')
            execute_func = node_executor.get(node_type) if node_executor else None
            if execute_func is None:
                execute_func = self._default_execute

            inputs = self._collect_inputs(node_id, node_outputs)
            inputs.update(context.get('inputs', {}))
            result = self._run_node(node_id, node_type, execute_func, inputs, context)
            new_results[node_id] = result
            if result.status == ExecutionStatus.SUCCESS:
                node_outputs[node_id] = result.output
                logger.info(f"[执行引擎] 恢复节点 {node_id} 成功")
                if self._on_node_execute:
                    self._on_node_execute(node_id, node_type, result.output)
            else:
                logger.error(f"[执行引擎] 恢复节点 {node_id} 仍失败: {result.error}")
                if self._on_error:
                    self._on_error(node_id, node_type, result.error)

        # 合并结果
        self._last_results.update(new_results)
        self._last_outputs = {
            nid: res.output
            for nid, res in self._last_results.items()
            if res.status == ExecutionStatus.SUCCESS
        }
        self._paused_at = None

        failed_count = len([r for r in new_results.values() if r.status == ExecutionStatus.FAILED])
        total_duration = (time.time() - start_time) * 1000
        summary = {
            'status': 'success' if failed_count == 0 else 'partial_success',
            'total_nodes': len(self._nodes),
            'executed_nodes': len([r for r in new_results.values() if r.status == ExecutionStatus.SUCCESS]),
            'failed_nodes': failed_count,
            'paused_at': None,
            'total_duration_ms': total_duration,
            'results': [r.to_dict() for r in self._last_results.values()],
        }
        self._last_summary = summary
        return summary

    # ── 结果缓存 API ──────────────────────────────────────────────────────────

    def clear_cache(self) -> None:
        """清空结果缓存"""
        self._cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0

    def get_cache_stats(self) -> dict[str, Any]:
        """获取缓存统计"""
        return {
            'size': len(self._cache),
            'hits': self._cache_hits,
            'misses': self._cache_misses,
            'enabled': self._cache_enabled,
        }

    # ── 撤销 / 重做（图快照）──────────────────────────────────────────────────

    def snapshot(self) -> dict[str, Any]:
        """生成当前图快照"""
        return {
            'nodes': {nid: dict(data) for nid, data in self._nodes.items()},
            'connections': [dict(c) for c in self._connections],
        }

    def restore(self, snap: dict[str, Any]) -> None:
        """恢复图快照"""
        self._nodes = {nid: dict(data) for nid, data in snap.get('nodes', {}).items()}
        self._connections = [dict(c) for c in snap.get('connections', [])]
        self._metrics.total_nodes = len(self._nodes)
        self._metrics.total_edges = len(self._connections)
        self._execution_order.clear()
        self._execution_history.clear()

    def push_undo(self) -> None:
        """记录一条撤销快照（重做栈清空）"""
        self._undo_stack.append(self.snapshot())
        self._redo_stack.clear()
        # 限制栈深度
        if len(self._undo_stack) > 100:
            self._undo_stack.pop(0)

    def undo(self) -> bool:
        """撤销上一次修改"""
        if not self._undo_stack:
            return False
        self._redo_stack.append(self.snapshot())
        self.restore(self._undo_stack.pop())
        return True

    def redo(self) -> bool:
        """重做被撤销的修改"""
        if not self._redo_stack:
            return False
        self._undo_stack.append(self.snapshot())
        self.restore(self._redo_stack.pop())
        return True

    @property
    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    # ── 性能分析 ──────────────────────────────────────────────────────────────

    def get_performance_report(self) -> list[dict[str, Any]]:
        """获取节点性能分析报告（按总耗时降序）"""
        report = []
        for node_id, stat in self._perf_stats.items():
            count = stat['count']
            report.append({
                'node_id': node_id,
                'node_type': stat['node_type'],
                'call_count': count,
                'total_ms': round(stat['total_ms'], 3),
                'avg_ms': round(stat['total_ms'] / count, 3) if count else 0.0,
                'max_ms': round(stat['max_ms'], 3),
            })
        report.sort(key=lambda r: r['total_ms'], reverse=True)
        return report

    def clear_history(self) -> None:
        """清空执行历史与性能统计"""
        self._execution_history.clear()
        self._perf_stats.clear()

    # 回调注册
    def on_node_execute(self, callback) -> None:
        """注册节点执行回调"""
        self._on_node_execute = callback

    def on_execution_complete(self, callback) -> None:
        """注册执行完成回调"""
        self._on_execution_complete = callback

    def on_error(self, callback) -> None:
        """注册错误回调"""
        self._on_error = callback

    # 属性
    @property
    def nodes(self) -> dict[str, Any]:
        return self._nodes.copy()

    @property
    def connections(self) -> list[dict[str, str]]:
        return self._connections.copy()

    @property
    def execution_order(self) -> list[str]:
        return self._execution_order.copy()

    @property
    def metrics(self) -> GraphMetrics:
        return self._metrics

    @property
    def execution_history(self) -> list[NodeExecutionResult]:
        return self._execution_history.copy()

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return {
            'nodes': self._nodes,
            'connections': self._connections,
            'execution_order': self._execution_order,
            'metrics': self._metrics.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NodeExecutor:
        """从字典反序列化"""
        executor = cls()
        executor._nodes = data.get('nodes', {})
        executor._connections = data.get('connections', [])
        executor._execution_order = data.get('execution_order', [])
        return executor


# 全局执行器实例
_executor: NodeExecutor | None = None


def get_executor() -> NodeExecutor:
    """获取全局执行器实例"""
    global _executor
    if _executor is None:
        _executor = NodeExecutor()
    return _executor


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("  Matha 节点执行引擎测试")
    print("=" * 60)

    executor = NodeExecutor()

    # 添加节点
    executor.add_node("n1", {"type": "math_pi", "id": "n1"})
    executor.add_node("n2", {"type": "math_multiply", "id": "n2"})
    executor.add_node("n3", {"type": "math_add", "id": "n3"})
    executor.add_node("n4", {"type": "output", "id": "n4"})

    # 添加连线
    executor.add_connection("n1", "value", "n2", "a")
    executor.add_connection("n2", "result", "n3", "a")
    executor.add_connection("n3", "result", "n4", "value")

    # 验证图
    is_valid, error = executor.validate_graph()
    print(f"\n图验证: {'通过' if is_valid else '失败'}")
    if error:
        print(f"错误: {error}")

    # 计算执行顺序
    order = executor.compute_execution_order()
    print(f"\n执行顺序: {order}")

    # 执行
    result = executor.execute()
    print("\n执行结果:")
    print(f"  状态: {result['status']}")
    print(f"  总节点数: {result['total_nodes']}")
    print(f"  执行节点数: {result['executed_nodes']}")
    print(f"  失败节点数: {result['failed_nodes']}")
    print(f"  总耗时: {result['total_duration_ms']:.2f}ms")

    print("\n" + "=" * 60)
    print("  测试完成")
    print("=" * 60)
