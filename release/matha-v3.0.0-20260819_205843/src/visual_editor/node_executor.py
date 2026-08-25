# -*- coding: utf-8 -*-
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
import time
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import deque
from enum import Enum
import math


logger = logging.getLogger(__name__)


class ExecutionStatus(Enum):
    """执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionError(Exception):
    """执行错误"""
    def __init__(self, message: str, node_id: Optional[str] = None, port_name: Optional[str] = None):
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
        output: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        duration_ms: float = 0.0,
    ):
        self.node_id = node_id
        self.node_type = node_type
        self.status = status
        self.output = output or {}
        self.error = error
        self.duration_ms = duration_ms
        self.timestamp = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
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
        self.execution_order: List[str] = []
    
    def to_dict(self) -> Dict[str, Any]:
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
        self._nodes: Dict[str, Any] = {}
        self._connections: List[Dict[str, str]] = []
        self._execution_order: List[str] = []
        self._metrics = GraphMetrics()
        self._execution_history: List[NodeExecutionResult] = []
        self._on_node_execute = None
        self._on_execution_complete = None
        self._on_error = None
    
    def add_node(self, node_id: str, node_data: Dict[str, Any]) -> None:
        """添加节点"""
        self._nodes[node_id] = node_data
        self._metrics.total_nodes = len(self._nodes)
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
            return True
        return False
    
    def remove_connection(self, from_node: str, from_port: str, to_node: str, to_port: str) -> bool:
        """移除连线"""
        for i, conn in enumerate(self._connections):
            if (conn['from'] == from_node and conn['from_port'] == from_port and
                conn['to'] == to_node and conn['to_port'] == to_port):
                self._connections.pop(i)
                self._metrics.total_edges = len(self._connections)
                return True
        return False
    
    def clear(self) -> None:
        """清空图"""
        self._nodes.clear()
        self._connections.clear()
        self._execution_order.clear()
        self._execution_history.clear()
        self._metrics = GraphMetrics()
    
    def validate_graph(self) -> Tuple[bool, Optional[str]]:
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
    
    def _detect_cycle(self) -> Tuple[bool, List[str]]:
        """检测图中是否有循环"""
        visited = set()
        rec_stack = set()
        path = []
        
        def dfs(node_id: str) -> Tuple[bool, List[str]]:
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
    
    def compute_execution_order(self) -> List[str]:
        """
        计算拓扑排序执行顺序
        
        使用 Kahn 算法：
        1. 计算每个节点的入度
        2. 将入度为 0 的节点加入队列
        3. 依次处理队列中的节点，减少相邻节点的入度
        4. 重复直到队列为空
        """
        # 计算入度
        in_degree = {node_id: 0 for node_id in self._nodes}
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
        node_executor: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        执行整个节点图
        
        Args:
            node_executor: 节点执行函数字典 {node_type: func}
            context: 执行上下文（共享数据）
        
        Returns:
            执行结果摘要
        """
        logger.info("[执行引擎] ========== 开始执行节点图 ==========")
        
        if context is None:
            context = {}
        
        # 验证图
        is_valid, error_msg = self.validate_graph()
        if not is_valid:
            logger.error(f"[执行引擎] 图验证失败: {error_msg}")
            return {
                'status': 'error',
                'error': error_msg,
                'results': [],
            }
        
        logger.info(f"[执行引擎] 图验证通过，开始计算执行顺序...")
        
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
        node_outputs = {node_id: {} for node_id in self._nodes}
        start_time = time.time()
        
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
            logger.debug(f"[执行引擎] 节点 {node_id} 输入: {inputs}")
            
            # 执行节点
            try:
                node_start = time.time()
                output = execute_func(node_data, inputs, context)
                duration = (time.time() - node_start) * 1000
                
                node_outputs[node_id] = output
                logger.info(f"[执行引擎] 节点 {node_id} 执行成功，输出: {output} (耗时: {duration:.2f}ms)")
                
                result = NodeExecutionResult(
                    node_id=node_id,
                    node_type=node_type,
                    status=ExecutionStatus.SUCCESS,
                    output=output,
                    duration_ms=duration,
                )
                results.append(result)
                
                # 通知回调
                if self._on_node_execute:
                    self._on_node_execute(node_id, node_type, output)
                
            except Exception as e:
                duration = (time.time() - node_start) * 1000 if 'node_start' in dir() else 0
                error_msg = str(e)
                logger.error(f"[执行引擎] 节点 {node_id} 执行失败: {error_msg}")
                
                result = NodeExecutionResult(
                    node_id=node_id,
                    node_type=node_type,
                    status=ExecutionStatus.FAILED,
                    error=error_msg,
                    duration_ms=duration,
                )
                results.append(result)
                
                # 通知错误回调
                if self._on_error:
                    self._on_error(node_id, node_type, error_msg)

        total_duration = (time.time() - start_time) * 1000
        self._execution_history.extend(results)
        
        # 统计结果
        success_count = len([r for r in results if r.status == ExecutionStatus.SUCCESS])
        failed_count = len([r for r in results if r.status == ExecutionStatus.FAILED])
        
        logger.info(f"[执行引擎] ========== 执行完成 ==========")
        logger.info(f"[执行引擎] 总节点数: {len(self._nodes)}, 成功: {success_count}, 失败: {failed_count}, 总耗时: {total_duration:.2f}ms")
        
        # 通知完成回调
        if self._on_execution_complete:
            self._on_execution_complete(results, total_duration)
        
        return {
            'status': 'success' if failed_count == 0 else 'partial_success',
            'total_nodes': len(self._nodes),
            'executed_nodes': success_count,
            'failed_nodes': failed_count,
            'total_duration_ms': total_duration,
            'results': [r.to_dict() for r in results],
        }
    
    def execute_incremental(
        self,
        changed_node_ids: Set[str],
        node_executor: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
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
    
    def _get_affected_nodes(self, changed_node_ids: Set[str]) -> Set[str]:
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
    
    def _collect_inputs(self, node_id: str, node_outputs: Dict[str, Dict]) -> Dict[str, Any]:
        """收集节点的输入值"""
        inputs = {}
        node_data = self._nodes.get(node_id, {})
        
        for conn in self._connections:
            if conn['to'] == node_id:
                from_output = node_outputs.get(conn['from'], {})
                inputs[conn['to_port']] = from_output.get(conn['from_port'])
        
        return inputs
    
    def _default_execute(self, node_data: Dict, inputs: Dict, context: Dict) -> Dict:
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
        elif node_type in ('input', 'output', 'variable', 'assign', 'if', 'sequence', 'constant'):
            output = self._execute_special_node(node_type, node_data, inputs)
        
        return output
    
    def _execute_math_node(self, node_type: str, inputs: Dict) -> Dict:
        """执行数学运算节点"""
        a = inputs.get('a', 0)
        b = inputs.get('b', 0)
        result = 0
        
        try:
            if node_type == 'math_add':
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
    
    def _execute_logic_node(self, node_type: str, inputs: Dict) -> Dict:
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
    
    def _execute_stats_node(self, node_type: str, inputs: Dict) -> Dict:
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
    
    def _execute_matrix_node(self, node_type: str, inputs: Dict) -> Dict:
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
    
    def _execute_special_node(self, node_type: str, node_data: Dict, inputs: Dict) -> Dict:
        """执行特殊节点"""
        if node_type == 'input':
            return {'value': node_data.get('default_value')}
        elif node_type == 'output':
            return {}
        elif node_type == 'variable':
            var_name = node_data.get('var_name', 'x')
            return {var_name: inputs.get('value')}
        elif node_type == 'assign':
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
    def nodes(self) -> Dict[str, Any]:
        return self._nodes.copy()
    
    @property
    def connections(self) -> List[Dict[str, str]]:
        return self._connections.copy()
    
    @property
    def execution_order(self) -> List[str]:
        return self._execution_order.copy()
    
    @property
    def metrics(self) -> GraphMetrics:
        return self._metrics
    
    @property
    def execution_history(self) -> List[NodeExecutionResult]:
        return self._execution_history.copy()
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            'nodes': self._nodes,
            'connections': self._connections,
            'execution_order': self._execution_order,
            'metrics': self._metrics.to_dict(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NodeExecutor':
        """从字典反序列化"""
        executor = cls()
        executor._nodes = data.get('nodes', {})
        executor._connections = data.get('connections', [])
        executor._execution_order = data.get('execution_order', [])
        return executor


# 全局执行器实例
_executor: Optional[NodeExecutor] = None


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
    print(f"\n执行结果:")
    print(f"  状态: {result['status']}")
    print(f"  总节点数: {result['total_nodes']}")
    print(f"  执行节点数: {result['executed_nodes']}")
    print(f"  失败节点数: {result['failed_nodes']}")
    print(f"  总耗时: {result['total_duration_ms']:.2f}ms")
    
    print("\n" + "=" * 60)
    print("  测试完成")
    print("=" * 60)
