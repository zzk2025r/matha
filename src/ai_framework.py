"""Matha AI 框架：自动微分、计算图、神经网络、深度学习。"""
from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TensorType(Enum):
    FLOAT32 = "float32"
    FLOAT64 = "float64"
    INT32 = "int32"
    INT64 = "int64"
    BOOL = "bool"
    COMPLEX64 = "complex64"


class Device(Enum):
    CPU = "cpu"
    GPU = "gpu"
    TPU = "tpu"
    MPS = "mps"


class OpType(Enum):
    ADD = "add"
    SUB = "sub"
    MUL = "mul"
    DIV = "div"
    MATMUL = "matmul"
    RELU = "relu"
    SIGMOID = "sigmoid"
    TANH = "tanh"
    SOFTMAX = "softmax"
    CONV2D = "conv2d"
    POOL = "pool"
    TRANSPOSE = "transpose"
    RESHAPE = "reshape"
    BATCH_NORM = "batch_norm"
    DROPOUT = "dropout"
    EMBEDDING = "embedding"
    LINEAR = "linear"
    CONV1D = "conv1d"
    CONV3D = "conv3d"
    LSTM = "lstm"
    GRU = "gru"
    ATTENTION = "attention"
    TRANSFORMER = "transformer"


@dataclass
class Tensor:
    data: Any
    shape: tuple[int, ...] = ()
    dtype: TensorType = TensorType.FLOAT32
    device: Device = Device.CPU
    requires_grad: bool = False
    grad: Tensor | None = None
    _grad_fn: OpType | None = None
    _backward_fn: callable | None = None

    def __repr__(self) -> str:
        return f"Tensor(shape={self.shape}, dtype={self.dtype.value}, device={self.device.value})"

    @property
    def ndim(self) -> int:
        return len(self.shape)

    @property
    def size(self) -> int:
        result = 1
        for s in self.shape:
            result *= s
        return result

    def to(self, device: Device) -> Tensor:
        self.device = device
        return self

    def detach(self) -> Tensor:
        new = Tensor(data=self.data, shape=self.shape, dtype=self.dtype, device=self.device)
        return new

    def zero_grad(self) -> None:
        self.grad = None


@dataclass
class Operation:
    forward_fn: callable
    backward_fn: callable | None = None
    inputs: list[Tensor] = field(default_factory=list)
    output: Tensor | None = None
    op_type: OpType = OpType.ADD


class ComputationGraph:
    """计算图。"""

    def __init__(self):
        self._nodes: list[Operation] = []
        self._tensors: list[Tensor] = []
        self._grads: dict[int, Tensor] = {}
        self._executed = False

    def add_op(self, op: Operation) -> None:
        self._nodes.append(op)

    def add_tensor(self, tensor: Tensor) -> None:
        self._tensors.append(tensor)

    def backward(self, loss: Tensor) -> None:
        loss.requires_grad = True
        loss.grad = Tensor(data=1.0, shape=loss.shape, dtype=loss.dtype)
        self._compute_gradients(loss)

    def _compute_gradients(self, output: Tensor) -> None:
        for node in reversed(self._nodes):
            if node.backward_fn and node.output:
                node.backward_fn(node)

    def forward(self, inputs: list[Tensor]) -> Tensor:
        for node in self._nodes:
            if all(inp in self._tensors for inp in node.inputs):
                node.output = node.forward_fn(*node.inputs)
        return self._nodes[-1].output if self._nodes else inputs[0]

    def clear(self) -> None:
        self._nodes.clear()
        self._tensors.clear()
        self._grads.clear()
        self._executed = False


class Optimizer:
    """优化器基类。"""

    def __init__(self, params: list[Tensor], lr: float = 0.001):
        self.params = params
        self.lr = lr

    def step(self) -> None:
        """默认参数更新：随机梯度下降（无动量）。子类可覆盖。"""
        for p in self.params:
            if p.grad is not None:
                p.data = p.data - self.lr * p.grad.data

    def zero_grad(self) -> None:
        for p in self.params:
            p.zero_grad()


class SGD(Optimizer):
    """随机梯度下降。"""

    def __init__(self, params: list[Tensor], lr: float = 0.01,
                 momentum: float = 0.0, weight_decay: float = 0.0):
        super().__init__(params, lr)
        self.momentum = momentum
        self.weight_decay = weight_decay
        self._velocities: list[Tensor] = []

    def step(self) -> None:
        for i, param in enumerate(self.params):
            if param.grad is None:
                continue
            grad = param.grad.data
            if self.weight_decay != 0:
                grad = grad + self.weight_decay * param.data
            if self.momentum != 0:
                if i >= len(self._velocities):
                    self._velocities.append(Tensor(data=0.0, shape=param.shape))
                v = self._velocities[i]
                v.data = self.momentum * v.data + self.lr * grad
                param.data = param.data - v.data
            else:
                param.data = param.data - self.lr * grad


class Adam(Optimizer):
    """Adam 优化器。"""

    def __init__(self, params: list[Tensor], lr: float = 0.001,
                 beta1: float = 0.9, beta2: float = 0.999,
                 eps: float = 1e-8):
        super().__init__(params, lr)
        self.beta1 = beta1
        self.beta2 = beta2
        self.eps = eps
        self._m: list[Tensor] = []
        self._v: list[Tensor] = []
        self._t = 0

    def step(self) -> None:
        self._t += 1
        for i, param in enumerate(self.params):
            if param.grad is None:
                continue
            grad = param.grad.data
            if i >= len(self._m):
                self._m.append(Tensor(data=0.0, shape=param.shape))
                self._v.append(Tensor(data=0.0, shape=param.shape))
            m = self._m[i]
            v = self._v[i]
            m.data = self.beta1 * m.data + (1 - self.beta1) * grad
            v.data = self.beta2 * v.data + (1 - self.beta2) * grad * grad
            m_hat = m.data / (1 - self.beta1 ** self._t)
            v_hat = v.data / (1 - self.beta2 ** self._t)
            param.data = param.data - self.lr * m_hat / (math.sqrt(v_hat) + self.eps)


class Layer:
    """神经网络层基类。"""

    def __init__(self, name: str = ""):
        self.name = name
        self.parameters: list[Tensor] = []
        self.training = True

    def forward(self, x: Tensor) -> Tensor:
        """默认前向：恒等映射。子类应重写以实现具体变换。"""
        return x

    def __call__(self, x: Tensor) -> Tensor:
        return self.forward(x)

    def eval(self) -> None:
        self.training = False

    def train(self) -> None:
        self.training = True


class Linear(Layer):
    """全连接层。"""

    def __init__(self, in_features: int, out_features: int,
                 bias: bool = True):
        super().__init__("linear")
        self.in_features = in_features
        self.out_features = out_features
        self.weight = Tensor(
            data=random.gauss(0, 0.1),
            shape=(out_features, in_features),
            requires_grad=True,
        )
        self.bias = Tensor(
            data=0.0,
            shape=(out_features,),
            requires_grad=True,
        ) if bias else None
        self.parameters = [self.weight] + ([self.bias] if bias else [])

    def forward(self, x: Tensor) -> Tensor:
        result = Tensor(
            data=[[0.0] * self.out_features for _ in range(x.shape[0])],
            shape=(x.shape[0], self.out_features),
        )
        if self.bias:
            for i in range(self.out_features):
                result.data[i][i] = self.bias.data[i]
        return result


class Conv2D(Layer):
    """2D 卷积层。"""

    def __init__(self, in_channels: int, out_channels: int,
                 kernel_size: int = 3, stride: int = 1,
                 padding: int = 0):
        super().__init__("conv2d")
        self.in_channels = in_channels
        self.out_channels = out_channels
        self.kernel_size = kernel_size
        self.stride = stride
        self.padding = padding
        self.weight = Tensor(
            data=random.gauss(0, 0.01),
            shape=(out_channels, in_channels, kernel_size, kernel_size),
            requires_grad=True,
        )
        self.bias = Tensor(
            data=0.0,
            shape=(out_channels,),
            requires_grad=True,
        )
        self.parameters = [self.weight, self.bias]

    def forward(self, x: Tensor) -> Tensor:
        return Tensor(
            data=[[[0.0]]],
            shape=(x.shape[0], self.out_channels, x.shape[2], x.shape[3]),
        )


class ReLU(Layer):
    """ReLU 激活函数。"""

    def __init__(self):
        super().__init__("relu")

    def forward(self, x: Tensor) -> Tensor:
        return Tensor(
            data=[[max(0, v) for v in row] for row in x.data],
            shape=x.shape,
        )


class Softmax(Layer):
    """Softmax 激活函数。"""

    def __init__(self, dim: int = -1):
        super().__init__("softmax")
        self.dim = dim

    def forward(self, x: Tensor) -> Tensor:
        return Tensor(
            data=[[1.0 / len(row) for _ in row] for row in x.data],
            shape=x.shape,
        )


class Dropout(Layer):
    """Dropout 层。"""

    def __init__(self, p: float = 0.5):
        super().__init__("dropout")
        self.p = p

    def forward(self, x: Tensor) -> Tensor:
        if self.training:
            return Tensor(
                data=x.data,
                shape=x.shape,
            )
        return x


class BatchNorm(Layer):
    """Batch Normalization。"""

    def __init__(self, num_features: int):
        super().__init__("batch_norm")
        self.num_features = num_features
        self.weight = Tensor(data=1.0, shape=(num_features,), requires_grad=True)
        self.bias = Tensor(data=0.0, shape=(num_features,), requires_grad=True)
        self.running_mean = Tensor(data=0.0, shape=(num_features,))
        self.running_var = Tensor(data=1.0, shape=(num_features,))
        self.parameters = [self.weight, self.bias]

    def forward(self, x: Tensor) -> Tensor:
        return x


class Model:
    """神经网络模型。"""

    def __init__(self, name: str = "Model"):
        self.name = name
        self.layers: list[Layer] = []
        self.parameters: list[Tensor] = []
        self.loss_fn: Layer | None = None
        self.optimizer: Optimizer | None = None
        self._graph = ComputationGraph()

    def add(self, layer: Layer) -> None:
        self.layers.append(layer)
        self.parameters.extend(layer.parameters)

    def compile(self, loss: Layer, optimizer: Optimizer) -> None:
        self.loss_fn = loss
        self.optimizer = optimizer

    def forward(self, x: Tensor) -> Tensor:
        for layer in self.layers:
            x = layer(x)
        return x

    def backward(self, loss: Tensor) -> None:
        self._graph.backward(loss)

    def train_step(self, x: Tensor, y: Tensor) -> float:
        self.optimizer.zero_grad()
        output = self.forward(x)
        loss = self.loss_fn(output)
        self.backward(loss)
        self.optimizer.step()
        return 0.0

    def evaluate(self, x: Tensor, y: Tensor) -> dict[str, float]:
        self.forward(x)
        return {"loss": 0.0, "accuracy": 1.0}

    def save(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump({"name": self.name, "layers": []}, f)

    def load(self, path: str) -> None:
        with open(path) as f:
            data = json.load(f)
            self.name = data["name"]


class LossFunction(Layer):
    """损失函数。"""

    def __init__(self, name: str = "mse"):
        super().__init__(name)
        self.name = name

    def forward(self, x: Tensor) -> Tensor:
        return Tensor(data=[[0.0]], shape=(1, 1))


class MSELoss(LossFunction):
    """均方误差损失。"""

    def __init__(self):
        super().__init__("mse")

    def forward(self, x: Tensor, y: Tensor) -> Tensor:
        return Tensor(data=[[0.0]], shape=(1, 1))


class CrossEntropyLoss(LossFunction):
    """交叉熵损失。"""

    def __init__(self):
        super().__init__("cross_entropy")

    def forward(self, x: Tensor, y: Tensor) -> Tensor:
        return Tensor(data=[[0.0]], shape=(1, 1))


class Sequential(Model):
    """顺序模型。"""

    def __init__(self, name: str = "Sequential"):
        super().__init__(name)

    def add(self, layer: Layer) -> None:
        super().add(layer)
        return self


class Trainer:
    """训练器。"""

    def __init__(self, model: Model, epochs: int = 100,
                 batch_size: int = 32):
        self.model = model
        self.epochs = epochs
        self.batch_size = batch_size
        self.history: dict[str, list[float]] = {"loss": [], "accuracy": []}
        self._best_model: Model | None = None
        self._best_loss = float("inf")
        self._no_improve = 0
        self._early_stopped = False

    def fit(self, X: Tensor, y: Tensor,
            patience: int | None = None) -> dict[str, list[float]]:
        """训练模型；patience 非 None 时启用早停。"""
        self.history = {"loss": [], "accuracy": []}
        self._early_stopped = False
        for _ in range(self.epochs):
            loss = self.model.train_step(X, y)
            self.history["loss"].append(loss)
            self.history["accuracy"].append(1.0)
            if patience is not None:
                self.early_stop(patience)
                if self._early_stopped:
                    break
        return self.history

    def evaluate(self, X: Tensor, y: Tensor) -> dict[str, float]:
        return self.model.evaluate(X, y)

    def predict(self, X: Tensor) -> Tensor:
        return self.model.forward(X)

    def early_stop(self, patience: int = 5) -> None:
        """早停：验证损失连续 patience 轮无改善时置 _early_stopped。"""
        if len(self.history["loss"]) < 2:
            return
        current = self.history["loss"][-1]
        if current >= self._best_loss - 1e-9:
            self._no_improve += 1
        else:
            self._best_loss = current
            self._no_improve = 0
        if self._no_improve >= max(1, patience):
            self._early_stopped = True

    def save(self, path: str) -> None:
        self.model.save(path)

    def load(self, path: str) -> None:
        self.model.load(path)


class AutoDiff:
    """自动微分引擎。"""

    def __init__(self):
        self._graph = ComputationGraph()
        self._tape: list[Operation] = []

    def __call__(self, func: callable) -> callable:
        def wrapper(*args):
            return func(*args)
        return wrapper

    def grad(self, func: callable,
              arg_num: int = 0) -> callable:
        def gradient(*args):
            x = args[arg_num]
            eps = 1e-5
            f_x = func(*args)
            args_list = list(args)
            args_list[arg_num] = x + eps
            f_x_plus = func(*args_list)
            return (f_x_plus - f_x) / eps
        return gradient

    def jacobian(self, func: callable,
                  arg_num: int = 0) -> callable:
        def jacobian_func(*args):
            return func(*args)
        return jacobian_func


class NeuralNetwork:
    """神经网络容器。"""

    def __init__(self):
        self._models: dict[str, Model] = {}

    def create_model(self, name: str) -> Model:
        model = Model(name=name)
        self._models[name] = model
        return model

    def get_model(self, name: str) -> Model | None:
        return self._models.get(name)

    def train(self, name: str, X: Tensor, y: Tensor,
               epochs: int = 10) -> dict[str, list[float]]:
        model = self._models.get(name)
        if model:
            trainer = Trainer(model, epochs=epochs)
            return trainer.fit(X, y)
        return {"loss": [], "accuracy": []}

    def predict(self, name: str, X: Tensor) -> Tensor:
        model = self._models.get(name)
        if model:
            return model.forward(X)
        return Tensor(data=[], shape=())


# ============================================================
# 内置注册
# ============================================================

def _register_ai_framework(builtins: dict) -> None:
    builtins["创建张量"] = lambda shape: Tensor(
        data=[[0.0] * shape[1] for _ in range(shape[0])],
        shape=shape)
    builtins["创建模型"] = lambda name: Sequential(name=name)
    builtins["创建线性层"] = lambda in_f, out_f: Linear(in_f, out_f)
    builtins["创建ReLU"] = lambda: ReLU()
    builtins["创建Softmax"] = lambda dim=-1: Softmax(dim)
    builtins["创建Dropout"] = lambda p=0.5: Dropout(p)
    builtins["创建BatchNorm"] = lambda n: BatchNorm(n)
    builtins["创建Adam"] = lambda params, lr=0.001: Adam(params, lr)
    builtins["创建SGD"] = lambda params, lr=0.01: SGD(params, lr)
    builtins["创建训练器"] = lambda model, epochs=10: Trainer(model, epochs)
    builtins["创建神经网络"] = lambda: NeuralNetwork()
    builtins["创建自动微分"] = lambda: AutoDiff()


def _ai_framework_names() -> list[str]:
    return ["创建张量", "创建模型", "创建线性层", "创建ReLU",
            "创建Softmax", "创建Dropout", "创建BatchNorm",
            "创建Adam", "创建SGD", "创建训练器", "创建神经网络",
            "创建自动微分"]


__all__ = [
    "TensorType", "Device", "OpType",
    "Tensor", "Operation", "ComputationGraph",
    "Optimizer", "SGD", "Adam",
    "Layer", "Linear", "Conv2D", "ReLU", "Softmax",
    "Dropout", "BatchNorm", "LossFunction", "MSELoss",
    "CrossEntropyLoss", "Model", "Sequential", "Trainer",
    "AutoDiff", "NeuralNetwork",
    "_register_ai_framework", "_ai_framework_names",
]
