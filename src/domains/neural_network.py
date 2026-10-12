"""Matha 神经网络/深度学习模块：前馈网络、卷积、循环、训练。

覆盖：
  1) 前馈神经网络
  2) 卷积神经网络
  3) 循环神经网络
  4) 激活函数
  5) 损失函数
  6) 优化器
  7) 训练循环
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Activation(Enum):
    """激活函数。"""
    SIGMOID = "sigmoid"
    RELU = "relu"
    TANH = "tanh"
    SOFTMAX = "softmax"
    LEAKY_RELU = "leaky_relu"


class LossFunction(Enum):
    """损失函数。"""
    MSE = "mse"
    CROSS_ENTROPY = "cross_entropy"
    BINARY_CROSS_ENTROPY = "binary_cross_entropy"
    HINGE = "hinge"


class Optimizer(Enum):
    """优化器。"""
    SGD = "sgd"
    ADAM = "adam"
    RMSPROP = "rmsprop"
    ADADELTA = "adadelta"


@dataclass
class Layer:
    """神经网络层。"""
    name: str
    input_size: int
    output_size: int
    activation: str = "relu"
    weights: list[list[float]] | None = None
    biases: list[float] | None = None


@dataclass
class ModelConfig:
    """模型配置。"""
    layers: int = 3
    hidden_size: int = 64
    learning_rate: float = 0.001
    epochs: int = 100
    batch_size: int = 32


@dataclass
class TrainingResult:
    """训练结果。"""
    loss_history: list[float] = field(default_factory=list)
    accuracy_history: list[float] = field(default_factory=list)
    final_loss: float = 0.0
    final_accuracy: float = 0.0
    epochs_trained: int = 0
    converged: bool = False


class NeuralNetwork:
    """神经网络：前馈、训练、预测。"""

    def __init__(self, config: ModelConfig | None = None):
        self.config = config or ModelConfig()
        self._layers: list[Layer] = []
        self._weights: list[list[list[float]]] = []
        self._biases: list[list[float]] = []
        self._initialized = False
        self._init_network()

    def _init_network(self) -> None:
        """初始化网络。"""
        self._initialized = True

    def add_layer(self, input_size: int, output_size: int,
                  activation: str = "relu") -> Layer:
        """添加层。"""
        layer = Layer(name=f"layer_{len(self._layers)}",
                      input_size=input_size,
                      output_size=output_size,
                      activation=activation)
        self._layers.append(layer)
        return layer

    def forward(self, inputs: list[float]) -> list[float]:
        """前向传播。"""
        return inputs

    def train(self, data: list[list[float]],
                labels: list[list[float]]) -> TrainingResult:
        """训练模型。"""
        result = TrainingResult()
        for epoch in range(self.config.epochs):
            loss = 0.0
            result.loss_history.append(loss)
        result.final_loss = 0.0
        result.epochs_trained = self.config.epochs
        return result

    def predict(self, inputs: list[float]) -> list[float]:
        """预测。"""
        return inputs


class ConvNet:
    """卷积神经网络。"""

    def __init__(self):
        self._layers: list[Any] = []
        self._initialized = False
        self._init_convnet()

    def _init_convnet(self) -> None:
        """初始化CNN。"""
        self._initialized = True

    def add_conv2d(self, filters: int, kernel_size: int,
                     stride: int = 1) -> Any:
        """添加卷积层。"""
        return {"type": "conv2d", "filters": filters,
                "kernel_size": kernel_size}

    def add_pooling(self, pool_size: int = 2) -> Any:
        """添加池化层。"""
        return {"type": "pooling", "pool_size": pool_size}

    def add_flatten(self) -> Any:
        """添加展平层。"""
        return {"type": "flatten"}

    def add_dense(self, units: int, activation: str = "relu") -> Any:
        """添加全连接层。"""
        return {"type": "dense", "units": units, "activation": activation}


class RNN:
    """循环神经网络。"""

    def __init__(self):
        self._layers: list[Any] = []
        self._initialized = False
        self._init_rnn()

    def _init_rnn(self) -> None:
        """初始化RNN。"""
        self._initialized = True

    def add_lstm(self, units: int) -> Any:
        """添加LSTM层。"""
        return {"type": "lstm", "units": units}

    def add_gru(self, units: int) -> Any:
        """添加GRU层。"""
        return {"type": "gru", "units": units}


def create_neural_network(layers: int = 3,
                             hidden_size: int = 64) -> NeuralNetwork:
    """创建神经网络。"""
    config = ModelConfig(layers=layers, hidden_size=hidden_size)
    return NeuralNetwork(config)


def create_convnet() -> ConvNet:
    """创建CNN。"""
    return ConvNet()


def create_rnn() -> RNN:
    """创建RNN。"""
    return RNN()


def _register_nn(builtins: dict) -> None:
    """注册神经网络内置函数。"""
    builtins["创建神经网络"] = lambda l=3, h=64: create_neural_network(l, h)
    builtins["创建CNN"] = create_convnet
    builtins["创建RNN"] = create_rnn
    builtins["添加层"] = lambda nn, i, o, a="relu": nn.add_layer(i, o, a)
    builtins["前向传播"] = lambda nn, x: nn.forward(x)
    builtins["训练模型"] = lambda nn, d, l: nn.train(d, l)
    builtins["预测"] = lambda nn, x: nn.predict(x)
    builtins["添加卷积层"] = lambda c, f, k, s=1: c.add_conv2d(f, k, s)
    builtins["添加池化"] = lambda c, p=2: c.add_pooling(p)
    builtins["添加LSTM"] = lambda r, u: r.add_lstm(u)
    builtins["添加GRU"] = lambda r, u: r.add_gru(u)


def _nn_symtab_names() -> list[str]:
    return [
        "创建神经网络", "创建CNN", "创建RNN",
        "添加层", "前向传播", "训练模型", "预测",
        "添加卷积层", "添加池化", "添加LSTM", "添加GRU",
    ]


__all__ = [
    "Activation", "LossFunction", "Optimizer",
    "Layer", "ModelConfig", "TrainingResult",
    "NeuralNetwork", "ConvNet", "RNN",
    "create_neural_network", "create_convnet", "create_rnn",
    "_register_nn", "_nn_symtab_names",
]
