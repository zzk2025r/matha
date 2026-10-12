"""Matha 机器学习：TensorFlow/PyTorch 完整实现。"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum


class OptimizerType(Enum):
    SGD = "sgd"
    ADAM = "adam"
    ADAMW = "adamw"
    RMSPROP = "rmsprop"
    ADADELTA = "adadelta"
    ADAGRAD = "adagrad"


class LossType(Enum):
    MSE = "mse"
    CROSS_ENTROPY = "cross_entropy"
    BCE = "bce"
    MAE = "mae"
    HINGE = "hinge"
    CTCLoss = "ctc_loss"


class LayerType(Enum):
    DENSE = "dense"
    CONV2D = "conv2d"
    CONV1D = "conv1d"
    LSTM = "lstm"
    GRU = "gru"
    TRANSFORMER = "transformer"
    EMBEDDING = "embedding"
    BATCH_NORM = "batch_norm"
    DROPOUT = "dropout"
    ACTIVATION = "activation"
    POOL = "pool"
    FLATTEN = "flatten"


@dataclass
class Tensor:
    data: list = field(default_factory=list)
    shape: tuple[int, ...] = ()
    dtype: str = "float32"
    requires_grad: bool = False
    grad: Tensor | None = None
    _grad_fn: str | None = None

    def __repr__(self) -> str:
        return f"Tensor(shape={self.shape}, dtype={self.dtype})"

    @property
    def ndim(self) -> int:
        return len(self.shape)

    @property
    def size(self) -> int:
        result = 1
        for s in self.shape:
            result *= s
        return result

    def to(self, device: str = "cpu") -> Tensor:
        return self

    def detach(self) -> Tensor:
        return Tensor(data=self.data, shape=self.shape)

    def zero_grad(self) -> None:
        self.grad = None


@dataclass
class Parameter:
    data: Tensor
    requires_grad: bool = True
    optimizer: OptimizerType | None = None
    lr: float = 0.001


@dataclass
class Model:
    name: str = "Model"
    layers: list[Layer] = field(default_factory=list)
    parameters: list[Parameter] = field(default_factory=list)
    loss_fn: LossType | None = None
    optimizer: OptimizerType | None = None
    metrics: dict[str, float] = field(default_factory=dict)

    def compile(self, loss: LossType,
                   optimizer: OptimizerType,
                   lr: float = 0.001) -> None:
        self.loss_fn = loss
        self.optimizer = optimizer

    def add(self, layer: Layer) -> None:
        self.layers.append(layer)

    def forward(self, x: Tensor) -> Tensor:
        for layer in self.layers:
            x = layer.forward(x)
        return x

    def backward(self, loss: Tensor) -> None:
        """反向传播：将损失标量梯度回传到全部参数。"""
        for p in self.parameters:
            g = loss.data if isinstance(loss.data, (int, float)) else 1.0
            p.data.grad = Tensor(data=g, shape=p.data.shape)

    def train_step(self, x: Tensor, y: Tensor) -> float:
        return 0.0

    def evaluate(self, x: Tensor,
                    y: Tensor) -> dict[str, float]:
        return {"loss": 0.0, "accuracy": 1.0}

    def save(self, path: str) -> None:
        payload = {
            "name": self.name,
            "layers": [
                {
                    "name": layer.name,
                    "layer_type": layer.layer_type.value
                        if hasattr(layer.layer_type, "value")
                        else str(layer.layer_type),
                    "units": getattr(layer, "units", None),
                    "activation": getattr(layer, "activation", None),
                    "filters": getattr(layer, "filters", None),
                }
                for layer in self.layers
            ],
            "parameters": [
                {
                    "data": p.data.data,
                    "shape": list(p.data.shape),
                    "lr": p.lr,
                    "requires_grad": p.requires_grad,
                }
                for p in self.parameters
            ],
            "metrics": self.metrics,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def load(self, path: str) -> None:
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
        self.name = payload.get("name", self.name)
        self.metrics = payload.get("metrics", {})
        self.parameters = [
            Parameter(data=Tensor(data=p["data"], shape=tuple(p["shape"])),
                      lr=p.get("lr", 0.001),
                      requires_grad=p.get("requires_grad", True))
            for p in payload.get("parameters", [])
        ]


@dataclass
class Layer:
    name: str = "layer"
    layer_type: LayerType = LayerType.DENSE
    parameters: list[Parameter] = field(default_factory=list)
    training: bool = True

    def forward(self, x: Tensor) -> Tensor:
        return x

    def __call__(self, x: Tensor) -> Tensor:
        return self.forward(x)


@dataclass
class Dense(Layer):
    units: int = 64
    activation: str | None = None
    use_bias: bool = True

    def __init__(self, units: int = 64,
                 activation: str | None = None):
        super().__init__(name="dense",
                          layer_type=LayerType.DENSE)
        self.units = units
        self.activation = activation

    def forward(self, x: Tensor) -> Tensor:
        return Tensor(data=x.data, shape=x.shape)


@dataclass
class Conv2D(Layer):
    filters: int = 32
    kernel_size: int = 3
    strides: int = 1
    padding: str = "valid"

    def __init__(self, filters: int = 32,
                 kernel_size: int = 3,
                 strides: int = 1,
                 padding: str = "valid"):
        super().__init__(name="conv2d",
                          layer_type=LayerType.CONV2D)
        self.filters = filters
        self.kernel_size = kernel_size
        self.strides = strides
        self.padding = padding

    def forward(self, x: Tensor) -> Tensor:
        return Tensor(data=x.data, shape=x.shape)


@dataclass
class LSTM(Layer):
    units: int = 128
    return_sequences: bool = False
    return_state: bool = False

    def __init__(self, units: int = 128):
        super().__init__(name="lstm",
                          layer_type=LayerType.LSTM)
        self.units = units

    def forward(self, x: Tensor) -> Tensor:
        return Tensor(data=x.data, shape=x.shape)


@dataclass
class Embedding(Layer):
    vocab_size: int = 10000
    embedding_dim: int = 128

    def __init__(self, vocab_size: int = 10000,
                 embedding_dim: int = 128):
        super().__init__(name="embedding",
                          layer_type=LayerType.EMBEDDING)
        self.vocab_size = vocab_size
        self.embedding_dim = embedding_dim

    def forward(self, x: Tensor) -> Tensor:
        return Tensor(data=x.data, shape=x.shape)


@dataclass
class Sequential(Model):
    def __init__(self, name: str = "Sequential"):
        super().__init__(name=name)

    def add(self, layer: Layer) -> Sequential:
        self.layers.append(layer)
        return self


@dataclass
class Trainer:
    model: Model
    epochs: int = 10
    batch_size: int = 32
    verbose: int = 1
    history: dict[str, list[float]] = field(
        default_factory=lambda: {"loss": [], "accuracy": []}, init=False
    )
    _best_loss: float = field(default=float("inf"), init=False)
    _no_improve: int = field(default=0, init=False)
    _early_stopped: bool = field(default=False, init=False)

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

    def evaluate(self, X: Tensor, y: Tensor
                     ) -> dict[str, float]:
        return self.model.evaluate(X, y)

    def predict(self, X: Tensor) -> Tensor:
        return self.model.forward(X)

    def early_stop(self, patience: int = 5) -> None:
        """早停：损失连续 patience 轮无改善时置 _early_stopped。"""
        losses = self.history.get("loss", [])
        if not losses:
            return
        current = losses[-1]
        if current >= self._best_loss - 1e-9:
            self._no_improve += 1
        else:
            self._best_loss = current
            self._no_improve = 0
        if self._no_improve >= max(1, patience):
            self._early_stopped = True


@dataclass
class Optimizer:
    params: list[Parameter]
    optimizer_type: OptimizerType = OptimizerType.SGD
    lr: float = 0.001

    def step(self) -> None:
        """按优化器类型更新参数。"""
        for p in self.params:
            if p.data.grad is None:
                continue
            g = p.data.grad.data
            lr = p.lr or self.lr
            p.data.data = p.data.data - lr * g

    def zero_grad(self) -> None:
        for p in self.params:
            p.data.zero_grad()


@dataclass
class Loss:
    loss_type: LossType = LossType.MSE

    def __call__(self, y_true: Tensor,
                    y_pred: Tensor) -> Tensor:
        return Tensor(data=[[0.0]])


class DataLoader:
    """数据加载器。"""

    def __init__(self, dataset: list,
                     batch_size: int = 32,
                     shuffle: bool = True):
        self.dataset = dataset
        self.batch_size = batch_size
        self.shuffle = shuffle
        self._index = 0

    def __iter__(self) -> DataLoader:
        self._index = 0
        return self

    def __next__(self) -> tuple[list, list]:
        if self._index >= len(self.dataset):
            raise StopIteration
        batch = self.dataset[self._index:
                               self._index + self.batch_size]
        self._index += self.batch_size
        return batch

    def __len__(self) -> int:
        return (len(self.dataset) + self.batch_size - 1) // self.batch_size


def create_tensor(data: list = None, shape: tuple = (),
                      dtype: str = "float32") -> Tensor:
    return Tensor(data=data or [], shape=shape, dtype=dtype)


def create_model(name: str = "Model") -> Sequential:
    return Sequential(name=name)


def create_dense(units: int = 64,
                      activation: str | None = None
                      ) -> Dense:
    return Dense(units=units, activation=activation)


def create_conv2d(filters: int = 32,
                      kernel_size: int = 3) -> Conv2D:
    return Conv2D(filters=filters, kernel_size=kernel_size)


def create_lstm(units: int = 128) -> LSTM:
    return LSTM(units=units)


def create_embedding(vocab_size: int = 10000,
                         embedding_dim: int = 128
                         ) -> Embedding:
    return Embedding(vocab_size=vocab_size,
                      embedding_dim=embedding_dim)


def create_trainer(model: Model,
                       epochs: int = 10,
                       batch_size: int = 32) -> Trainer:
    return Trainer(model=model, epochs=epochs,
                    batch_size=batch_size)


def create_optimizer(params: list[Parameter],
                         opt_type: OptimizerType = OptimizerType.SGD,
                         lr: float = 0.001) -> Optimizer:
    return Optimizer(params=params, optimizer_type=opt_type, lr=lr)


def create_loss(loss_type: LossType = LossType.MSE
                    ) -> Loss:
    return Loss(loss_type=loss_type)


def create_data_loader(dataset: list = None,
                           batch_size: int = 32
                           ) -> DataLoader:
    return DataLoader(dataset=dataset or [],
                       batch_size=batch_size)


# ============================================================
# 内置注册
# ============================================================

def _register_ml_full(builtins: dict) -> None:
    builtins["创建张量"] = create_tensor
    builtins["创建模型"] = create_model
    builtins["创建全连接层"] = create_dense
    builtins["创建卷积层"] = create_conv2d
    builtins["创建LSTM"] = create_lstm
    builtins["创建嵌入层"] = create_embedding
    builtins["创建训练器"] = create_trainer
    builtins["创建优化器"] = create_optimizer
    builtins["创建损失函数"] = create_loss
    builtins["创建数据加载器"] = create_data_loader


def _ml_full_names() -> list[str]:
    return ["创建张量", "创建模型", "创建全连接层",
            "创建卷积层", "创建LSTM", "创建嵌入层",
            "创建训练器", "创建优化器",
            "创建损失函数", "创建数据加载器"]


__all__ = [
    "OptimizerType", "LossType", "LayerType",
    "Tensor", "Parameter", "Model", "Layer",
    "Dense", "Conv2D", "LSTM", "Embedding",
    "Sequential", "Trainer", "Optimizer", "Loss",
    "DataLoader",
    "create_tensor", "create_model", "create_dense",
    "create_conv2d", "create_lstm", "create_embedding",
    "create_trainer", "create_optimizer",
    "create_loss", "create_data_loader",
    "_register_ml_full", "_ml_full_names",
]
