"""Matha 可视化编程器 - 节点类型定义

定义各类计算节点的类型、输入输出端口、执行逻辑：
  - 数学运算节点
  - 逻辑判断节点
  - 变量节点
  - 输入输出节点
  - 控制流节点
"""
from __future__ import annotations

import json
import logging
import math
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

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

    # 文件操作
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FILE_LIST = "file_list"
    FILE_DELETE = "file_delete"

    # 网络请求
    NET_HTTP_GET = "net_http_get"
    NET_HTTP_POST = "net_http_post"

    # 数据库操作
    DB_QUERY = "db_query"
    DB_EXECUTE = "db_execute"

    # 图像处理
    IMAGE_GRAYSCALE = "image_grayscale"
    IMAGE_INVERT = "image_invert"
    IMAGE_BRIGHTNESS = "image_brightness"
    IMAGE_RESIZE = "image_resize"

    # 音频处理
    AUDIO_SINE = "audio_sine"
    AUDIO_VOLUME = "audio_volume"
    AUDIO_NORMALIZE = "audio_normalize"
    AUDIO_FADE = "audio_fade"


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
    inputs: list[PortDefinition] = field(default_factory=list)
    outputs: list[PortDefinition] = field(default_factory=list)
    category: str = "数学"
    icon: str = ""
    execute_func: Callable | None = None

    # 节点配置
    config: dict[str, Any] = field(default_factory=dict)

    @property
    def input_count(self) -> int:
        return len(self.inputs)

    @property
    def output_count(self) -> int:
        return len(self.outputs)


class NodeRegistry:
    """节点注册表"""

    _nodes: dict[str, NodeDefinition] = {}

    @classmethod
    def register(cls, definition: NodeDefinition) -> None:
        """注册节点"""
        cls._nodes[definition.node_type.value] = definition
        logger.debug(f"注册节点: {definition.node_type.value}")

    @classmethod
    def get(cls, node_type: str) -> NodeDefinition | None:
        """获取节点定义"""
        return cls._nodes.get(node_type)

    @classmethod
    def get_all(cls) -> dict[str, NodeDefinition]:
        """获取所有节点"""
        return cls._nodes.copy()

    @classmethod
    def get_by_category(cls, category: str) -> list[NodeDefinition]:
        """按类别获取节点"""
        return [n for n in cls._nodes.values() if n.category == category]

    @classmethod
    def search(cls, keyword: str) -> list[NodeDefinition]:
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
        config: dict[str, Any] | None = None,
    ):
        self.id = id(self)
        self.node_type = node_type
        self.position = position
        self.config = config or {}
        self.inputs: dict[str, Any] = {}
        self.outputs: dict[str, Any] = {}
        self.connected_inputs: dict[str, str] = {}  # port_name -> connection_id
        self.connected_outputs: dict[str, str] = {}  # port_name -> connection_id

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

    def execute(self) -> dict[str, Any]:
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

    def to_dict(self) -> dict[str, Any]:
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
    def from_dict(cls, data: dict[str, Any]) -> Node:
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
    [PortDefinition("a", "number", True, description="输入 A")]
    [PortDefinition("result", "number", False, description="计算结果")]

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


def _create_file_node(node_type: NodeType, label: str, **kwargs) -> NodeDefinition:
    """创建文件操作节点"""
    if node_type == NodeType.FILE_READ:
        inputs = []
        outputs = [PortDefinition("content", "any", False, description="文件内容")]
        func = lambda n: {"content": _file_read(n.config.get("path", ""))}
    elif node_type == NodeType.FILE_WRITE:
        inputs = [PortDefinition("content", "any", True, description="写入内容")]
        outputs = [PortDefinition("written", "any", False, description="写入结果")]
        func = lambda n: {"written": _file_write(n.config.get("path", ""), n.get_input("content"))}
    elif node_type == NodeType.FILE_LIST:
        inputs = []
        outputs = [PortDefinition("files", "list", False, description="文件列表")]
        func = lambda n: {"files": _file_list(n.config.get("path", "."))}
    else:  # FILE_DELETE
        inputs = []
        outputs = [PortDefinition("deleted", "boolean", False, description="是否删除")]
        func = lambda n: {"deleted": _file_delete(n.config.get("path", ""))}

    return NodeDefinition(
        node_type=node_type,
        label=label,
        description=f"{label}（路径由节点配置指定）",
        inputs=inputs,
        outputs=outputs,
        category="文件",
        execute_func=func,
        config=kwargs.get("config", {}),
    )


def _create_network_node(node_type: NodeType, label: str, **kwargs) -> NodeDefinition:
    """创建网络请求节点"""
    if node_type == NodeType.NET_HTTP_GET:
        inputs = []
        outputs = [PortDefinition("status", "number", False, description="状态码"),
                   PortDefinition("body", "any", False, description="响应体")]
        func = lambda n: _http_get(n.config.get("url", ""), n.config.get("timeout", 5.0))
    else:  # NET_HTTP_POST
        inputs = [PortDefinition("body", "any", True, description="请求体")]
        outputs = [PortDefinition("status", "number", False, description="状态码"),
                   PortDefinition("body", "any", False, description="响应体")]
        func = lambda n: _http_post(n.config.get("url", ""), n.get_input("body"))
    return NodeDefinition(
        node_type=node_type,
        label=label,
        description=f"{label}（URL 由节点配置指定）",
        inputs=inputs,
        outputs=outputs,
        category="网络",
        execute_func=func,
        config=kwargs.get("config", {}),
    )


def _create_db_node(node_type: NodeType, label: str, **kwargs) -> NodeDefinition:
    """创建数据库操作节点"""
    db_path = kwargs.get("config", {}).get("path", ":memory:")
    if node_type == NodeType.DB_QUERY:
        inputs = [PortDefinition("sql", "string", True, description="SQL 查询")]
        outputs = [PortDefinition("rows", "list", False, description="查询结果"),
                   PortDefinition("columns", "list", False, description="列名")]
        func = lambda n: _db_query(db_path, n.get_input("sql"))
    else:  # DB_EXECUTE
        inputs = [PortDefinition("sql", "string", True, description="SQL 语句")]
        outputs = [PortDefinition("rowcount", "number", False, description="影响行数")]
        func = lambda n: {"rowcount": _db_execute(db_path, n.get_input("sql"))}
    return NodeDefinition(
        node_type=node_type,
        label=label,
        description=f"{label}（数据库路径由节点配置指定）",
        inputs=inputs,
        outputs=outputs,
        category="数据库",
        execute_func=func,
        config=kwargs.get("config", {}),
    )


def _create_image_node(node_type: NodeType, label: str, **kwargs) -> NodeDefinition:
    """创建图像处理节点（图像为 {width,height,pixels} 字典）"""
    func_map = {
        NodeType.IMAGE_GRAYSCALE: lambda n: {"image": _image_grayscale(n.get_input("image"))},
        NodeType.IMAGE_INVERT: lambda n: {"image": _image_invert(n.get_input("image"))},
        NodeType.IMAGE_BRIGHTNESS: lambda n: {"image": _image_brightness(n.get_input("image"), float(n.get_input("factor") or 0))},
        NodeType.IMAGE_RESIZE: lambda n: {"image": _image_resize(n.get_input("image"), int(n.get_input("width") or 0), int(n.get_input("height") or 0))},
    }
    if node_type == NodeType.IMAGE_BRIGHTNESS:
        inputs = [
            PortDefinition("image", "any", True, description="输入图像"),
            PortDefinition("factor", "number", True, default_value=0.0, description="亮度增量"),
        ]
        outputs = [PortDefinition("image", "any", False, description="输出图像")]
    elif node_type == NodeType.IMAGE_RESIZE:
        inputs = [
            PortDefinition("image", "any", True, description="输入图像"),
            PortDefinition("width", "number", True, default_value=100, description="目标宽度"),
            PortDefinition("height", "number", True, default_value=100, description="目标高度"),
        ]
        outputs = [PortDefinition("image", "any", False, description="输出图像")]
    else:
        inputs = [PortDefinition("image", "any", True, description="输入图像")]
        outputs = [PortDefinition("image", "any", False, description="输出图像")]
    return NodeDefinition(
        node_type=node_type,
        label=label,
        description=f"{label}（像素级过滤）",
        inputs=inputs,
        outputs=outputs,
        category="图像",
        execute_func=func_map[node_type],
    )


def _create_audio_node(node_type: NodeType, label: str, **kwargs) -> NodeDefinition:
    """创建音频处理节点（音频为 {sample_rate,samples} 字典）"""
    func_map = {
        NodeType.AUDIO_SINE: lambda n: {"audio": _audio_sine(float(n.get_input("freq") or 440.0), float(n.get_input("seconds") or 1.0), float(n.get_input("sample_rate") or 16000.0))},
        NodeType.AUDIO_VOLUME: lambda n: {"audio": _audio_volume(n.get_input("audio"), float(n.get_input("level") or 1.0))},
        NodeType.AUDIO_NORMALIZE: lambda n: {"audio": _audio_normalize(n.get_input("audio"))},
        NodeType.AUDIO_FADE: lambda n: {"audio": _audio_fade(n.get_input("audio"))},
    }
    if node_type == NodeType.AUDIO_SINE:
        inputs = [
            PortDefinition("freq", "number", True, default_value=440.0, description="频率 Hz"),
            PortDefinition("seconds", "number", True, default_value=1.0, description="时长秒"),
            PortDefinition("sample_rate", "number", True, default_value=16000.0, description="采样率"),
        ]
        outputs = [PortDefinition("audio", "any", False, description="生成音频")]
    elif node_type == NodeType.AUDIO_VOLUME:
        inputs = [
            PortDefinition("audio", "any", True, description="输入音频"),
            PortDefinition("level", "number", True, default_value=1.0, description="音量倍数"),
        ]
        outputs = [PortDefinition("audio", "any", False, description="输出音频")]
    else:
        inputs = [PortDefinition("audio", "any", True, description="输入音频")]
        outputs = [PortDefinition("audio", "any", False, description="输出音频")]
    return NodeDefinition(
        node_type=node_type,
        label=label,
        description=f"{label}（采样级处理）",
        inputs=inputs,
        outputs=outputs,
        category="音频",
        execute_func=func_map[node_type],
    )


# ── 文件／网络／数据库／图像／音频 执行逻辑（纯标准库）───────────────────────────

def _file_read(path: str) -> dict:
    if not path:
        raise ValueError("文件路径未配置")
    with open(path, encoding="utf-8") as f:
        return {"content": f.read()}


def _file_write(path: str, content: Any) -> bool:
    if not path:
        raise ValueError("文件路径未配置")
    with open(path, "w", encoding="utf-8") as f:
        f.write(str(content))
    return True


def _file_list(path: str) -> list[str]:
    return sorted(name for name in os.listdir(path) if not name.startswith("."))


def _file_delete(path: str) -> bool:
    if not path:
        return False
    if os.path.isdir(path):
        os.rmdir(path)
    else:
        os.remove(path)
    return True


def _http_get(url: str, timeout: float = 5.0) -> dict:
    import urllib.request
    if not url:
        raise ValueError("URL 未配置")
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return {"status": resp.status, "body": resp.read().decode("utf-8", errors="replace")}


def _http_post(url: str, data: Any) -> dict:
    import urllib.request
    if not url:
        raise ValueError("URL 未配置")
    body = json.dumps(data) if isinstance(data, (dict, list)) else str(data)
    req = urllib.request.Request(url, data=body.encode("utf-8"), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10.0) as resp:
        return {"status": resp.status, "body": resp.read().decode("utf-8", errors="replace")}


def _db_query(path: str, sql: str) -> dict:
    import sqlite3
    conn = sqlite3.connect(path)
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(sql)
        rows = [dict(row) for row in cursor.fetchall()]
        columns = [d[0] for d in cursor.description] if cursor.description else []
        return {"rows": rows, "columns": columns}
    finally:
        conn.close()


def _db_execute(path: str, sql: str) -> int:
    import sqlite3
    conn = sqlite3.connect(path)
    try:
        cursor = conn.execute(sql)
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def _image_grayscale(img: dict) -> dict:
    _require_image(img)
    pixel_count = img["width"] * img["height"]
    pixels = img["pixels"]
    out = []
    for i in range(pixel_count):
        r, g, b = pixels[i * 3], pixels[i * 3 + 1], pixels[i * 3 + 2]
        gray = round(0.299 * r + 0.587 * g + 0.114 * b)
        out.extend([gray, gray, gray])
    return {"width": img["width"], "height": img["height"], "pixels": out}


def _image_invert(img: dict) -> dict:
    _require_image(img)
    return {"width": img["width"], "height": img["height"],
            "pixels": [255 - v for v in img["pixels"]]}


def _image_brightness(img: dict, factor: float) -> dict:
    _require_image(img)
    def _clamp(v: float) -> int:
        return max(0, min(255, round(v)))
    return {"width": img["width"], "height": img["height"],
            "pixels": [_clamp(v + factor) for v in img["pixels"]]}


def _image_resize(img: dict, width: int, height: int) -> dict:
    _require_image(img)
    if width <= 0 or height <= 0:
        raise ValueError(f"非法尺寸: {width}x{height}")
    src = img
    out = []
    for y in range(height):
        for x in range(width):
            sx = min(src["width"] - 1, x * src["width"] // width)
            sy = min(src["height"] - 1, y * src["height"] // height)
            idx = (sy * src["width"] + sx) * 3
            out.extend(src["pixels"][idx:idx + 3])
    return {"width": width, "height": height, "pixels": out}


def _require_image(img) -> None:
    if not isinstance(img, dict) or "pixels" not in img:
        raise ValueError("输入不是有效图像（需 {width,height,pixels} 字典）")


def _audio_sine(freq: float, seconds: float, sample_rate: float) -> dict:
    import math
    n = int(seconds * sample_rate)
    samples = [round(math.sin(2 * math.pi * freq * i / sample_rate), 6) for i in range(n)]
    return {"sample_rate": int(sample_rate), "samples": samples}


def _audio_volume(audio: dict, level: float) -> dict:
    _require_audio(audio)
    return {"sample_rate": audio["sample_rate"], "samples": [s * level for s in audio["samples"]]}


def _audio_normalize(audio: dict) -> dict:
    _require_audio(audio)
    samples = audio["samples"]
    peak = max((abs(s) for s in samples), default=0.0)
    if peak == 0:
        return {"sample_rate": audio["sample_rate"], "samples": samples}
    scale = 1.0 / peak
    return {"sample_rate": audio["sample_rate"], "samples": [s * scale for s in samples]}


def _audio_fade(audio: dict) -> dict:
    """首尾 10% 线性淡入淡出"""
    _require_audio(audio)
    samples = audio["samples"]
    n = len(samples)
    fade_n = max(1, n // 10)
    out = list(samples)
    for i in range(fade_n):
        env = i / fade_n
        out[i] *= env
        out[n - 1 - i] *= env
    return {"sample_rate": audio["sample_rate"], "samples": out}


def _require_audio(audio) -> None:
    if not isinstance(audio, dict) or "samples" not in audio:
        raise ValueError("输入不是有效音频（需 {sample_rate,samples} 字典）")


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

    # 文件操作节点
    file_nodes = [
        (NodeType.FILE_READ, "读取文件"),
        (NodeType.FILE_WRITE, "写入文件"),
        (NodeType.FILE_LIST, "列出目录"),
        (NodeType.FILE_DELETE, "删除文件"),
    ]
    for node_type, label in file_nodes:
        NodeRegistry.register(_create_file_node(node_type, label))

    # 网络请求节点
    NodeRegistry.register(_create_network_node(NodeType.NET_HTTP_GET, "HTTP GET"))
    NodeRegistry.register(_create_network_node(NodeType.NET_HTTP_POST, "HTTP POST"))

    # 数据库操作节点
    NodeRegistry.register(_create_db_node(NodeType.DB_QUERY, "数据库查询"))
    NodeRegistry.register(_create_db_node(NodeType.DB_EXECUTE, "数据库执行"))

    # 图像处理节点
    image_nodes = [
        (NodeType.IMAGE_GRAYSCALE, "图像灰度"),
        (NodeType.IMAGE_INVERT, "图像反色"),
        (NodeType.IMAGE_BRIGHTNESS, "图像亮度"),
        (NodeType.IMAGE_RESIZE, "图像缩放"),
    ]
    for node_type, label in image_nodes:
        NodeRegistry.register(_create_image_node(node_type, label))

    # 音频处理节点
    audio_nodes = [
        (NodeType.AUDIO_SINE, "生成正弦波"),
        (NodeType.AUDIO_VOLUME, "音量调节"),
        (NodeType.AUDIO_NORMALIZE, "音频归一化"),
        (NodeType.AUDIO_FADE, "淡入淡出"),
    ]
    for node_type, label in audio_nodes:
        NodeRegistry.register(_create_audio_node(node_type, label))

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
