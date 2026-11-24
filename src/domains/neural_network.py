"""Matha 神经网络领域插件：前馈网络真实现（委托 src.ai_framework 数值腿）。

【定位 2026-11 · 阶段 1 AI 修复】历史上 forward/predict 原样透传输入、
train 恒 loss=0，属假实现。本轮以已严格背书的 ai_framework（Linear/激活/
MSE/Adam，tests/test_ai_framework_numerics.py 76 条数值锁）为地基重写
前向/训练/预测；行为级锁见 tests/test_neural_network_plugin.py
（手算对拍 / 收敛闭环 / 显式拒绝）。CNN/RNN 在仓库内无背书实现，
其构建方法显式拒绝，不再返回假 dict 冒充成功。
口径遵 docs/KNOWN_ISSUES.md §7c：数值腿委托已背书引擎，
训练有效性主张（泛化/收敛速度）不背书。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src import ai_framework as _af


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
    """神经网络层规格（实际计算层由 ai_framework 承载）。"""
    name: str
    input_size: int
    output_size: int
    activation: str = "relu"
    weights: list[list[float]] | None = None
    biases: list[float] | None = None


@dataclass
class ModelConfig:
    """模型配置。训练为全批量（与 ai_framework.Trainer 同口径），
    batch_size 仅保留字段兼容，不参与切批。"""
    layers: int = 3
    hidden_size: int = 64
    learning_rate: float = 0.001
    epochs: int = 100
    batch_size: int = 32


@dataclass
class TrainingResult:
    """训练结果。loss/accuracy 均为真实读数；converged 判据为
    末轮 MSE < 1e-6（绝对容差，非泛化主张）。"""
    loss_history: list[float] = field(default_factory=list)
    accuracy_history: list[float] = field(default_factory=list)
    final_loss: float = 0.0
    final_accuracy: float = 0.0
    epochs_trained: int = 0
    converged: bool = False


#: 有背书实现的激活函数（leaky_relu 在枚举中声明但无实现，显式拒绝）
_ACTIVATIONS: dict[str, type] = {
    "relu": _af.ReLU,
    "sigmoid": _af.Sigmoid,
    "tanh": _af.Tanh,
    "softmax": _af.Softmax,
}


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _check_row(row: Any, width: int, what: str) -> list[float]:
    if not isinstance(row, (list, tuple)) or not row:
        raise ValueError(f"{what}须为非空数值列表")
    if len(row) != width:
        raise ValueError(f"{what}宽度 {len(row)} ≠ 期望 {width}")
    if not all(_is_number(v) for v in row):
        raise ValueError(f"{what}含非数值元素")
    return [float(v) for v in row]


def _check_rows(rows: Any, width: int, what: str) -> list[list[float]]:
    if not isinstance(rows, (list, tuple)) or not rows:
        raise ValueError(f"{what}须为非空二维列表")
    return [_check_row(r, width, what) for r in rows]


class NeuralNetwork:
    """前馈神经网络：add_layer 搭结构，forward/train/predict 真算。

    计算委托 ai_framework.Model（Linear + 激活 + MSELoss + Adam），
    未添加层即前向/训练属误用，显式拒绝。
    """

    def __init__(self, config: ModelConfig | None = None):
        self.config = config or ModelConfig()
        self._layers: list[Layer] = []
        self._model: _af.Model | None = None

    def add_layer(self, input_size: int, output_size: int,
                  activation: str = "relu") -> Layer:
        """添加层。维度不连续/未知激活显式拒绝；结构变更后重建计算模型。"""
        for name, size in (("input_size", input_size),
                           ("output_size", output_size)):
            if not isinstance(size, int) or isinstance(size, bool) or size < 1:
                raise ValueError(f"{name} 须为正整数：{size!r}")
        if self._layers and input_size != self._layers[-1].output_size:
            raise ValueError(
                f"层间维度不连续：上一层输出 {self._layers[-1].output_size}"
                f" ≠ 本层输入 {input_size}")
        if activation == "leaky_relu":
            raise NotImplementedError(
                "激活函数 leaky_relu 未实现（支持 relu/sigmoid/tanh/softmax）")
        if activation not in _ACTIVATIONS:
            raise ValueError(
                f"未知激活函数 {activation!r}（支持 relu/sigmoid/tanh/softmax）")
        layer = Layer(name=f"layer_{len(self._layers)}",
                      input_size=input_size,
                      output_size=output_size,
                      activation=activation)
        self._layers.append(layer)
        self._model = None
        return layer

    def _build_model(self) -> _af.Model:
        if not self._layers:
            raise RuntimeError("神经网络尚未添加任何层，请先调用 添加层")
        if self._model is None:
            model = _af.Model(name="matha_nn")
            for spec in self._layers:
                model.add(_af.Linear(spec.input_size, spec.output_size))
                model.add(_ACTIVATIONS[spec.activation]())
            self._model = model
        return self._model

    def forward(self, inputs: list[float]) -> list[float]:
        """前向传播：单样本真算（委托 ai_framework 逐层前向）。"""
        model = self._build_model()
        x = _check_row(inputs, self._layers[0].input_size, "前向输入")
        out = model.forward(_af.Tensor(data=[x], shape=(1, len(x))))
        return list(out.data[0])

    def train(self, data: list[list[float]],
                labels: list[list[float]]) -> TrainingResult:
        """全批量训练：每轮真前向→MSE→逐层反向→Adam 更新，记录真实损失。"""
        if self.config.epochs < 1:
            raise ValueError(f"epochs 须 ≥ 1：{self.config.epochs}")
        model = self._build_model()
        in_width = self._layers[0].input_size
        out_width = self._layers[-1].output_size
        X = _check_rows(data, in_width, "训练数据")
        Y = _check_rows(labels, out_width, "训练标签")
        if len(X) != len(Y):
            raise ValueError(f"样本数与标签数不一致：{len(X)} ≠ {len(Y)}")
        model.compile(_af.MSELoss(),
                      _af.Adam(model.parameters, lr=self.config.learning_rate))
        xt = _af.Tensor(data=X, shape=(len(X), in_width))
        yt = _af.Tensor(data=Y, shape=(len(Y), out_width))
        result = TrainingResult()
        for _ in range(self.config.epochs):
            loss = model.train_step(xt, yt)
            result.loss_history.append(loss)
            out = model.forward(xt).data
            correct = sum(
                1 for row_o, row_y in zip(out, Y)
                if row_o.index(max(row_o)) == row_y.index(max(row_y)))
            result.accuracy_history.append(correct / len(Y))
        result.final_loss = result.loss_history[-1]
        result.final_accuracy = result.accuracy_history[-1]
        result.epochs_trained = self.config.epochs
        result.converged = result.final_loss < 1e-6
        return result

    def predict(self, inputs: list[float]) -> list[float]:
        """预测：与 forward 同口径的真推理。"""
        return self.forward(inputs)


class ConvNet:
    """卷积神经网络（占位边界：执行链未实现，构建方法显式拒绝）。"""

    def add_conv2d(self, filters: int, kernel_size: int,
                     stride: int = 1) -> Any:
        raise NotImplementedError(
            "CNN 执行链未实现（池化/展平无背书实现）；"
            "前馈网络请用 创建神经网络 + 添加层")

    def add_pooling(self, pool_size: int = 2) -> Any:
        raise NotImplementedError(
            "CNN 执行链未实现（池化/展平无背书实现）；"
            "前馈网络请用 创建神经网络 + 添加层")

    def add_flatten(self) -> Any:
        raise NotImplementedError(
            "CNN 执行链未实现（池化/展平无背书实现）；"
            "前馈网络请用 创建神经网络 + 添加层")

    def add_dense(self, units: int, activation: str = "relu") -> Any:
        raise NotImplementedError(
            "CNN 执行链未实现（池化/展平无背书实现）；"
            "前馈网络请用 创建神经网络 + 添加层")


class RNN:
    """循环神经网络（占位边界：LSTM/GRU 未实现，构建方法显式拒绝）。"""

    def add_lstm(self, units: int) -> Any:
        raise NotImplementedError(
            "LSTM 未实现（仓库无背书实现）；前馈网络请用 创建神经网络 + 添加层")

    def add_gru(self, units: int) -> Any:
        raise NotImplementedError(
            "GRU 未实现（仓库无背书实现）；前馈网络请用 创建神经网络 + 添加层")


def create_neural_network(layers: int = 3,
                             hidden_size: int = 64) -> NeuralNetwork:
    """创建神经网络（结构经 添加层 指定；layers/hidden_size 仅保留配置兼容）。"""
    config = ModelConfig(layers=layers, hidden_size=hidden_size)
    return NeuralNetwork(config)


def create_convnet() -> ConvNet:
    """创建CNN。"""
    return ConvNet()


def create_rnn() -> RNN:
    """创建RNN。"""
    return RNN()


def _register_nn(builtins: dict) -> None:
    """注册神经网络内置函数。

    Matha 调用 f(a, b) 在 VM 与 interp 两侧均为柯里化单参应用 f(a)(b)，
    零参写法 f() 传入 0，故注册形态必须是逐参 lambda 链；平铺多参 lambda
    会被首参提前求值（历史缺陷：创建神经网络(2,4) 报「不可调用的值」）。
    """
    builtins["创建神经网络"] = lambda l: lambda h: create_neural_network(l, h)
    builtins["创建CNN"] = lambda _: create_convnet()
    builtins["创建RNN"] = lambda _: create_rnn()
    builtins["添加层"] = lambda nn: lambda i: lambda o: lambda a: nn.add_layer(i, o, a)
    builtins["前向传播"] = lambda nn: lambda x: nn.forward(x)
    builtins["训练模型"] = lambda nn: lambda d: lambda l: nn.train(d, l)
    builtins["预测"] = lambda nn: lambda x: nn.predict(x)
    builtins["添加卷积层"] = lambda c: lambda f: lambda k: lambda s: c.add_conv2d(f, k, s)
    builtins["添加池化"] = lambda c: lambda p: c.add_pooling(p)
    builtins["添加LSTM"] = lambda r: lambda u: r.add_lstm(u)
    builtins["添加GRU"] = lambda r: lambda u: r.add_gru(u)
    # 权重初始化走全局 random（ai_framework._rand_matrix）——无播种插口时同一
    # 源码两次运行/双执行面不可比。单插件一名（与 创建神经网络 归本插件同口径）。
    builtins["随机种子"] = lambda s: _af.seed_random(s)


def _nn_symtab_names() -> list[str]:
    return [
        "创建神经网络", "创建CNN", "创建RNN",
        "添加层", "前向传播", "训练模型", "预测",
        "添加卷积层", "添加池化", "添加LSTM", "添加GRU",
        "随机种子",
    ]


__all__ = [
    "Activation", "LossFunction", "Optimizer",
    "Layer", "ModelConfig", "TrainingResult",
    "NeuralNetwork", "ConvNet", "RNN",
    "create_neural_network", "create_convnet", "create_rnn",
    "_register_nn", "_nn_symtab_names",
]
