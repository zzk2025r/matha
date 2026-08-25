# -*- coding: utf-8 -*-
"""Matha 可视化编程器 - 节点类型定义

定义各类计算节点的类型、输入输出端口、执行逻辑：
  - 数学运算节点
  - 逻辑判断节点
  - 变量节点
  - 输入输出节点
  - 控制流节点
"""
from __future__ import annotations
import math
import logging
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum


logger = logging.getLogger(__name__)


class NodeType(Enum):
    """节点类型枚举"""
    # 数学运算
    MATH_ADD = "math_add"
    MATH_SUBTRACT = "math_subtract"
    MATH_MULTIPLY = "math_multiply"
    MATH_DIVIDE = "math_divide"
    MATH_POWER = "math_power"
    MATH_SQRT = "math_sqrt"
    MATH_ABS = "math_abs"
    MATH_FLOOR = "math_floor"
    MATH_CEIL = "math_ceil"
    MATH_MODULO = "math_modulo"
    
    # 三角函数
    MATH_SIN = "math_sin"
    MATH_COS = "math_cos"
    MATH_TAN = "math_tan"
    MATH_ASIN = "math_asin"
    MATH_ACOS = "math_acos"
    MATH_ATAN = "math_atan"
    
    # 对数指数
    MATH_LOG = "math_log"
    MATH_LOG2 = "math_log2"
    MATH_LOG10 = "math_log10"
    MATH_EXP = "math_exp"
    
    # 常数
    MATH_PI = "math_pi"
    MATH_E = "math_e"
    
    # 逻辑运算
    LOGIC_AND = "logic_and"
    LOGIC_OR = "logic_or"
    LOGIC_NOT = "logic_not"
    LOGIC_EQUAL = "logic_equal"
    LOGIC_NOT_EQUAL = "logic_not_equal"
    LOGIC_LESS = "logic_less"
    LOGIC_GREATER = "logic_greater"
    LOGIC_LESS_EQUAL = "logic_less_equal"
    LOGIC_GREATER_EQUAL = "logic_greater_equal"
    
    # 变量
    VARIABLE = "variable"
    ASSIGN = "assign"
    
    # 输入输出
    INPUT = "input"
    OUTPUT = "output"
    
    # 控制流
    IF = "if"
    WHILE = "while"
    FOR = "for"
    
    # 矩阵运算
    MATRIX_CREATE = "matrix_create"
    MATRIX_multiply = "matrix_multiply"
    MATRIX_TRANSPOSE = "matrix_transpose"
    MATRIX_DETERMINANT = "matrix_determinant"
    MATRIX_INVERSE = "matrix_inverse"
    
    # 概率统计
    STATS_MEAN = "stats_mean"
    STATS_VARIANCE = "stats_variance"
    STATS_STD = "stats_std"
    STATS_SUM = "stats_sum"
    STATS_MIN = "stats_min"
    STATS_MAX = "stats_max"
    
    # 特殊
    CONSTANT = "constant"
    SEQUENCE = "sequence"


@dataclass
class PortDefinition:
    """端口定义"""
    name: str
    type: str  # "number", "boolean", "string", "matrix", "list", "any"
    is_input: bool
    default_value: Any = None
    description: str = ""


@dataclass
class NodeDefinition:
    """节点定义"""
    node_type: NodeType
    label: str
    description: str
    inputs: List[PortDefinition] = field(default_factory=list)
    outputs: List[PortDefinition] = field(default_factory=list)
    category: str = "数学"
    icon: str = ""
    execute_func: Optional[Callable] = None
    
    # 节点配置
    config: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def input_count(self) -> int:
        return len(self.inputs)
    
    @property
    def output_count(self) -> int:
        return len(self.outputs)


class NodeRegistry:
    """节点注册表"""
    
    _nodes: Dict[str, NodeDefinition] = {}
    
    @classmethod
    def register(cls, definition: NodeDefinition) -> None:
        """注册节点"""
        cls._nodes[definition.node_type.value] = definition
        logger.debug(f"注册节点: {definition.node_type.value}")
    
    @classmethod
    def get(cls, node_type: str) -> Optional[NodeDefinition]:
        """获取节点定义"""
        return cls._nodes.get(node_type)
    
    @classmethod
    def get_all(cls) -> Dict[str, NodeDefinition]:
        """获取所有节点"""
        return cls._nodes.copy()
    
    @classmethod
    def get_by_category(cls, category: str) -> List[NodeDefinition]:
        """按类别获取节点"""
        return [n for n in cls._nodes.values() if n.category == category]
    
    @classmethod
    def search(cls, keyword: str) -> List[NodeDefinition]:
        """搜索节点"""
        keyword = keyword.lower()
        return [
            n for n in cls._nodes.values()
            if keyword in n.node_type.value or keyword in n.label.lower()
        ]


class Node:
    """节点实例"""
    
    def __init__(
        self,
        node_type: NodeType,
        position: tuple = (0, 0),
        config: Optional[Dict[str, Any]] = None,
    ):
        self.id = id(self)
        self.node_type = node_type
        self.position = position
        self.config = config or {}
        self.inputs: Dict[str, Any] = {}
        self.outputs: Dict[str, Any] = {}
        self.connected_inputs: Dict[str, str] = {}  # port_name -> connection_id
        self.connected_outputs: Dict[str, str] = {}  # port_name -> connection_id
        
        # 获取节点定义
        self.definition = NodeRegistry.get(node_type.value)
        if self.definition is None:
            raise ValueError(f"未知的节点类型: {node_type.value}")
        
        # 初始化端口
        self._init_ports()
    
    def _init_ports(self) -> None:
        """初始化端口值"""
        for port in self.definition.inputs:
            self.inputs[port.name] = port.default_value
        
        for port in self.definition.outputs:
            self.outputs[port.name] = None
    
    def set_input(self, port_name: str, value: Any) -> None:
        """设置输入值"""
        if port_name in self.inputs:
            self.inputs[port_name] = value
    
    def get_input(self, port_name: str) -> Any:
        """获取输入值"""
        return self.inputs.get(port_name)
    
    def set_output(self, port_name: str, value: Any) -> None:
        """设置输出值"""
        if port_name in self.outputs:
            self.outputs[port_name] = value
    
    def get_output(self, port_name: str) -> Any:
        """获取输出值"""
        return self.outputs.get(port_name)
    
    def execute(self) -> Dict[str, Any]:
        """执行节点"""
        if self.definition.execute_func:
            try:
                result = self.definition.execute_func(self)
                if isinstance(result, dict):
                    self.outputs.update(result)
                return self.outputs
            except Exception as e:
                logger.error(f"节点执行失败: {e}")
                return {"error": str(e)}
        return self.outputs
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "id": self.id,
            "type": self.node_type.value,
            "position": list(self.position),
            "config": self.config,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "connected_inputs": self.connected_inputs,
            "connected_outputs": self.connected_outputs,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Node":
        """从字典反序列化"""
        node_type = NodeType(data["type"])
        position = tuple(data.get("position", [0, 0]))
        config = data.get("config", {})
        
        node = cls(node_type, position, config)
        node.inputs = data.get("inputs", {})
        node.outputs = data.get("outputs", {})
        node.connected_inputs = data.get("connected_inputs", {})
        node.connected_outputs = data.get("connected_outputs", {})
        return node


def _create_math_node(node_type: NodeType, label: str, category: str, **kwargs) -> NodeDefinition:
    """创建数学运算节点"""
    inputs = [PortDefinition("a", "number", True, description="输入 A")]
    outputs = [PortDefinition("result", "number", False, description="计算结果")]
    
    execute_funcs = {
        NodeType.MATH_ADD: lambda n: {"result": n.get_input("a") + n.get_input("b") if "b" in n.inputs else n.get_input("a")},
        NodeType.MATH_SUBTRACT: lambda n: n.get_input("a") - n.get_input("b"),
        NodeType.MATH_MULTIPLY: lambda n: n.get_input("a") * n.get_input("b"),
        NodeType.MATH_DIVIDE: lambda n: n.get_input("a") / n.get_input("b") if n.get_input("b") != 0 else float('inf'),
        NodeType.MATH_POWER: lambda n: n.get_input("a") ** n.get_input("b"),
        NodeType.MATH_SQRT: lambda n: math.sqrt(n.get_input("a")) if n.get_input("a") >= 0 else float('nan'),
        NodeType.MATH_ABS: lambda n: abs(n.get_input("a")),
        NodeType.MATH_FLOOR: lambda n: math.floor(n.get_input("a")),
        NodeType.MATH_CEIL: lambda n: math.ceil(n.get_input("a")),
        NodeType.MATH_MODULO: lambda n: n.get_input("a") % n.get_input("b"),
        NodeType.MATH_SIN: lambda n: math.sin(n.get_input("a")),
        NodeType.MATH_COS: lambda n: math.cos(n.get_input("a")),
        NodeType.MATH_TAN: lambda n: math.tan(n.get_input("a")),
        NodeType.MATH_ASIN: lambda n: math.asin(n.get_input("a")) if -1 <= n.get_input("a") <= 1 else float('nan'),
        NodeType.MATH_ACOS: lambda n: math.acos(n.get_input("a")) if -1 <= n.get_input("a") <= 1 else float('nan'),
        NodeType.MATH_ATAN: lambda n: math.atan(n.get_input("a")),
        NodeType.MATH_LOG: lambda n: math.log(n.get_input("a")) if n.get_input("a") > 0 else float('nan'),
        NodeType.MATH_LOG2: lambda n: math.log2(n.get_input("a")) if n.get_input("a") > 0 else float('nan'),
        NodeType.MATH_LOG10: lambda n: math.log10(n.get_input("a")) if n.get_input("a") > 0 else float('nan'),
        NodeType.MATH_EXP: lambda n: math.exp(n.get_input("a")),
    }
    
    definition = NodeDefinition(
        node_type=node_type,
        label=label,
        description=f"{label}运算",
        inputs=[
            PortDefinition("a", "number", True, description="输入 A"),
            PortDefinition("b", "number", True, default_value=0, description="输入 B"),
        ],
        outputs=[PortDefinition("result", "number", False, description="计算结果")],
        category=category,
        execute_func=execute_funcs.get(node_type),
    )
    return definition


def _create_logic_node(node_type: NodeType, label: str, **kwargs) -> NodeDefinition:
    """创建逻辑运算节点"""
    return NodeDefinition(
        node_type=node_type,
        label=label,
        description=f"{label}逻辑运算",
        inputs=[
            PortDefinition("a", "boolean", True, description="输入 A"),
            PortDefinition("b", "boolean", True, default_value=False, description="输入 B"),
        ],
        outputs=[PortDefinition("result", "boolean", False, description="结果")],
        category="逻辑",
    )


def _create_constant_node(node_type: NodeType, label: str, value: Any, **kwargs) -> NodeDefinition:
    """创建常量节点"""
    return NodeDefinition(
        node_type=node_type,
        label=label,
        description=f"常量 {value}",
        inputs=[],
        outputs=[PortDefinition("value", "number", False, default_value=value, description="常量值")],
        category="常量",
    )


def _create_variable_node(node_type: NodeType, label: str, **kwargs) -> NodeDefinition:
    """创建变量节点"""
    return NodeDefinition(
        node_type=node_type,
        label=label,
        description="变量读写",
        inputs=[PortDefinition("value", "any", True, description="写入值")],
        outputs=[PortDefinition("value", "any", False, description="读取值")],
        category="变量",
    )


def _create_input_node(**kwargs) -> NodeDefinition:
    """创建输入节点"""
    return NodeDefinition(
        node_type=NodeType.INPUT,
        label="输入",
        description="用户输入",
        inputs=[],
        outputs=[PortDefinition("value", "any", False, description="输入值")],
        category="输入输出",
    )


def _create_output_node(**kwargs) -> NodeDefinition:
    """创建输出节点"""
    return NodeDefinition(
        node_type=NodeType.OUTPUT,
        label="输出",
        description="显示结果",
        inputs=[PortDefinition("value", "any", True, description="输入值")],
        outputs=[],
        category="输入输出",
    )


def _create_if_node(**kwargs) -> NodeDefinition:
    """创建条件分支节点"""
    return NodeDefinition(
        node_type=NodeType.IF,
        label="条件判断",
        description="IF-ELSE 分支",
        inputs=[
            PortDefinition("condition", "boolean", True, description="条件"),
            PortDefinition("true_value", "any", True, description="True 分支值"),
            PortDefinition("false_value", "any", True, description="False 分支值"),
        ],
        outputs=[PortDefinition("result", "any", False, description="结果")],
        category="控制流",
    )


def _create_sequence_node(**kwargs) -> NodeDefinition:
    """创建序列节点"""
    return NodeDefinition(
        node_type=NodeType.SEQUENCE,
        label="序列",
        description="生成数字序列",
        inputs=[
            PortDefinition("start", "number", True, default_value=0, description="起始值"),
            PortDefinition("end", "number", True, default_value=10, description="结束值"),
            PortDefinition("step", "number", True, default_value=1, description="步长"),
        ],
        outputs=[PortDefinition("sequence", "list", False, description="序列")],
        category="序列",
    )


def _create_stats_node(node_type: NodeType, label: str, **kwargs) -> NodeDefinition:
    """创建统计节点"""
    execute_funcs = {
        NodeType.STATS_MEAN: lambda n: sum(n.get_input("data")) / len(n.get_input("data")) if n.get_input("data") else 0,
        NodeType.STATS_VARIANCE: lambda n: sum((x - sum(n.get_input("data"))/len(n.get_input("data")))**2 for x in n.get_input("data")) / len(n.get_input("data")) if n.get_input("data") else 0,
        NodeType.STATS_STD: lambda n: math.sqrt(sum((x - sum(n.get_input("data"))/len(n.get_input("data")))**2 for x in n.get_input("data")) / len(n.get_input("data"))) if n.get_input("data") else 0,
        NodeType.STATS_SUM: lambda n: sum(n.get_input("data")),
        NodeType.STATS_MIN: lambda n: min(n.get_input("data")) if n.get_input("data") else 0,
        NodeType.STATS_MAX: lambda n: max(n.get_input("data")) if n.get_input("data") else 0,
    }
    
    return NodeDefinition(
        node_type=node_type,
        label=label,
        description=f"{label}统计",
        inputs=[PortDefinition("data", "list", True, description="数据列表")],
        outputs=[PortDefinition("result", "number", False, description="统计结果")],
        category="统计",
        execute_func=execute_funcs.get(node_type),
    )


def _create_matrix_node(node_type: NodeType, label: str, **kwargs) -> NodeDefinition:
    """创建矩阵运算节点"""
    execute_funcs = {
        NodeType.MATRIX_CREATE: lambda n: {"result": n.get_input("data") or [[1, 0], [0, 1]]},
        NodeType.MATRIX_multiply: lambda n: {"result": n.get_input("a")},  # 简化实现
        NodeType.MATRIX_TRANSPOSE: lambda n: {"result": [[row[i] for row in n.get_input("matrix")] for i in range(len(n.get_input("matrix")))] if n.get_input("matrix") else []},
        NodeType.MATRIX_DETERMINANT: lambda n: {"result": 1},  # 简化实现
        NodeType.MATRIX_INVERSE: lambda n: {"result": n.get_input("matrix")},  # 简化实现
    }
    
    if node_type == NodeType.MATRIX_CREATE:
        inputs = [PortDefinition("data", "matrix", True, description="矩阵数据")]
    elif node_type == NodeType.MATRIX_multiply:
        inputs = [
            PortDefinition("a", "matrix", True, description="矩阵 A"),
            PortDefinition("b", "matrix", True, description="矩阵 B"),
        ]
    else:
        inputs = [PortDefinition("matrix", "matrix", True, description="输入矩阵")]
    
    return NodeDefinition(
        node_type=node_type,
        label=label,
        description=f"{label}矩阵运算",
        inputs=inputs,
        outputs=[PortDefinition("result", "matrix", False, description="结果矩阵")],
        category="矩阵",
        execute_func=execute_funcs.get(node_type),
    )


def register_all_nodes() -> None:
    """注册所有节点"""
    # 数学运算节点
    math_nodes = [
        (NodeType.MATH_ADD, "加法", "数学"),
        (NodeType.MATH_SUBTRACT, "减法", "数学"),
        (NodeType.MATH_MULTIPLY, "乘法", "数学"),
        (NodeType.MATH_DIVIDE, "除法", "数学"),
        (NodeType.MATH_POWER, "幂运算", "数学"),
        (NodeType.MATH_SQRT, "平方根", "数学"),
        (NodeType.MATH_ABS, "绝对值", "数学"),
        (NodeType.MATH_FLOOR, "向下取整", "数学"),
        (NodeType.MATH_CEIL, "向上取整", "数学"),
        (NodeType.MATH_MODULO, "取模", "数学"),
        (NodeType.MATH_SIN, "正弦", "数学"),
        (NodeType.MATH_COS, "余弦", "数学"),
        (NodeType.MATH_TAN, "正切", "数学"),
        (NodeType.MATH_ASIN, "反正弦", "数学"),
        (NodeType.MATH_ACOS, "反余弦", "数学"),
        (NodeType.MATH_ATAN, "反正切", "数学"),
        (NodeType.MATH_LOG, "自然对数", "数学"),
        (NodeType.MATH_LOG2, "对数(2)", "数学"),
        (NodeType.MATH_LOG10, "对数(10)", "数学"),
        (NodeType.MATH_EXP, "指数", "数学"),
    ]
    
    for node_type, label, category in math_nodes:
        NodeRegistry.register(_create_math_node(node_type, label, category))
    
    # 常数节点
    NodeRegistry.register(_create_constant_node(NodeType.MATH_PI, "π", 3.141592653589793))
    NodeRegistry.register(_create_constant_node(NodeType.MATH_E, "e", 2.718281828459045))
    
    # 逻辑运算节点
    logic_nodes = [
        (NodeType.LOGIC_AND, "与"),
        (NodeType.LOGIC_OR, "或"),
        (NodeType.LOGIC_NOT, "非"),
        (NodeType.LOGIC_EQUAL, "等于"),
        (NodeType.LOGIC_NOT_EQUAL, "不等于"),
        (NodeType.LOGIC_LESS, "小于"),
        (NodeType.LOGIC_GREATER, "大于"),
        (NodeType.LOGIC_LESS_EQUAL, "小于等于"),
        (NodeType.LOGIC_GREATER_EQUAL, "大于等于"),
    ]
    
    for node_type, label in logic_nodes:
        NodeRegistry.register(_create_logic_node(node_type, label))
    
    # 变量节点
    NodeRegistry.register(_create_variable_node(NodeType.VARIABLE, "变量"))
    NodeRegistry.register(_create_variable_node(NodeType.ASSIGN, "赋值"))
    
    # 输入输出节点
    NodeRegistry.register(_create_input_node())
    NodeRegistry.register(_create_output_node())
    
    # 控制流节点
    NodeRegistry.register(_create_if_node())
    NodeRegistry.register(_create_sequence_node())
    
    # 统计节点
    stats_nodes = [
        (NodeType.STATS_MEAN, "平均值"),
        (NodeType.STATS_VARIANCE, "方差"),
        (NodeType.STATS_STD, "标准差"),
        (NodeType.STATS_SUM, "求和"),
        (NodeType.STATS_MIN, "最小值"),
        (NodeType.STATS_MAX, "最大值"),
    ]
    
    for node_type, label in stats_nodes:
        NodeRegistry.register(_create_stats_node(node_type, label))
    
    # 矩阵节点
    matrix_nodes = [
        (NodeType.MATRIX_CREATE, "创建矩阵"),
        (NodeType.MATRIX_multiply, "矩阵乘法"),
        (NodeType.MATRIX_TRANSPOSE, "矩阵转置"),
        (NodeType.MATRIX_DETERMINANT, "矩阵行列式"),
        (NodeType.MATRIX_INVERSE, "矩阵求逆"),
    ]
    
    for node_type, label in matrix_nodes:
        NodeRegistry.register(_create_matrix_node(node_type, label))
    
    logger.info(f"已注册 {len(NodeRegistry._nodes)} 个节点类型")


# 注册所有节点
register_all_nodes()


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 60)
    print("  Matha 节点类型注册测试")
    print("=" * 60)
    
    # 测试节点注册
    print(f"\n已注册节点数: {len(NodeRegistry._nodes)}")
    
    # 按类别分组
    categories = {}
    for node in NodeRegistry._nodes.values():
        if node.category not in categories:
            categories[node.category] = []
        categories[node.category].append(node.label)
    
    print("\n节点类别:")
    for category, nodes in categories.items():
        print(f"  {category}: {', '.join(nodes[:5])}{'...' if len(nodes) > 5 else ''}")
    
    # 测试搜索
    print("\n搜索 'math':")
    results = NodeRegistry.search("math")
    for r in results[:5]:
        print(f"  - {r.label}")
    
    print("\n" + "=" * 60)
    print("  测试完成")
    print("=" * 60)
