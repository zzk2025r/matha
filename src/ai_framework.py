"""Matha AI 框架：AI框架（矩阵乘法地基、自动微分、计算图、神经网络、深度学习）。

【定位标注 2026-10 / P2 降级 · 2026-11 严格测试背书】仓库内未背书前端：
自 2026-11 起，`matmul`/`Linear`/激活/损失/反向链/优化器等**数值腿**已由
`tests/test_ai_framework_numerics.py`（76 条）严格测试并背书：手算对拍、跨引擎互证、
显式拒绝、代数性质律、边界值、全模型中心差分梯度神谕（含 BatchNorm/Conv2D
闭式反向、Dropout 冻结掩码神谕与输入梯度回流）、SymPy 符号对拍、确定性与无-NaN 健壮性，并经全量门禁
5257/5257 通过；训练**有效性主张（泛化/收敛速度）与深度能力**仍不背书，
不作为现功能主张。ComputationGraph 属如实的「演示级」，
口径见 docs/KNOWN_ISSUES.md 第七节 7c。
"""
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
        new = Tensor(data=_ew(lambda v: v, self.data), shape=self.shape,
                     dtype=self.dtype, device=self.device)
        return new

    def zero_grad(self) -> None:
        self.grad = None


# ============================================================
# 矩阵乘法地基：形状校验 + 显式拒绝 + 逐元素工具
# ============================================================

def _is_number(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _check_matrix(m: Any, name: str) -> None:
    """m 必须是同号宽度的二维数值矩阵，否则显式拒绝（严禁静默接受）。"""
    if not isinstance(m, list) or not m or not all(isinstance(r, list) for r in m):
        raise ValueError(f"{name} 必须是二维矩阵（list of lists），实得 {type(m).__name__}")
    width = len(m[0])
    for i, row in enumerate(m):
        if len(row) != width:
            raise ValueError(f"{name} 第 {i} 行宽度 {len(row)} ≠ 第 0 行宽度 {width}")
        if not all(_is_number(v) for v in row):
            raise ValueError(f"{name} 第 {i} 行含非数值元素")


def matmul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    """矩阵乘法 A(M×N) · B(N×P) → M×P。

    地基函数：`Linear`/反向链/优化器全部以此实现；形状不合即显式拒绝，
    不返回全零占位（历史缺陷：占位 forward 静默吞掉错误）。
    """
    _check_matrix(a, "matmul.a")
    _check_matrix(b, "matmul.b")
    n = len(a[0])
    if n != len(b):
        raise ValueError(f"内维不匹配：a 是 {len(a)}×{n}，b 是 {len(b)}×{len(b[0])}")
    p = len(b[0])
    return [[sum(a[i][k] * b[k][j] for k in range(n)) for j in range(p)]
            for i in range(len(a))]


def transpose(a: list[list[float]]) -> list[list[float]]:
    _check_matrix(a, "transpose.a")
    return [list(col) for col in zip(*a)]


def colsum(a: list[list[float]]) -> list[float]:
    """按列求和（bias 梯度用）。"""
    _check_matrix(a, "colsum.a")
    return [sum(row[j] for row in a) for j in range(len(a[0]))]


def _ew(f, x):
    """逐元素映射（递归进任意深度嵌套 list）。"""
    if isinstance(x, list):
        return [_ew(f, v) for v in x]
    return f(x)


def _ew2(f, a, b):
    """逐元素双参数映射；要求两侧结构一致（广播仅指标量 f 内部），
    不一致即显式拒绝——历史上宽容的标量/列表分支会把 tuple 漏进参数。"""
    if isinstance(a, list):
        if isinstance(b, list):
            if len(a) != len(b):
                raise ValueError(f"形状不匹配：{len(a)} vs {len(b)}")
            return [_ew2(f, u, v) for u, v in zip(a, b)]
        raise ValueError(f"结构不匹配：list vs {type(b).__name__}")
    if isinstance(b, list):
        raise ValueError(f"结构不匹配：{type(a).__name__} vs list")
    return f(a, b)


def _zeros_like(x):
    return [_zeros_like(v) for v in x] if isinstance(x, list) else 0.0


def _rand_matrix(rows: int, cols: int, sigma: float) -> list[list[float]]:
    return [[random.gauss(0.0, sigma) for _ in range(cols)] for _ in range(rows)]


@dataclass
class Operation:
    forward_fn: callable
    backward_fn: callable | None = None
    inputs: list[Tensor] = field(default_factory=list)
    output: Tensor | None = None
    op_type: OpType = OpType.ADD


class ComputationGraph:
    """计算图（演示级：tape 由调用方手工挂 backward_fn；训练链不依赖本类，
    走 Model 的逐层反向。头注横幅已如实登记）。"""

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
        """默认参数更新：随机梯度下降（无动量），逐元素作用于嵌套数据。"""
        for p in self.params:
            if p.grad is not None:
                p.data = _ew2(lambda d, g: d - self.lr * g, p.data, p.grad.data)

    def zero_grad(self) -> None:
        for p in self.params:
            p.zero_grad()


class SGD(Optimizer):
    """随机梯度下降（支持动量与权重衰减，逐元素实现）。"""

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
                grad = _ew2(lambda g, d: g + self.weight_decay * d, grad, param.data)
            if self.momentum != 0:
                if i >= len(self._velocities):
                    self._velocities.append(Tensor(data=_zeros_like(param.data)))
                v = self._velocities[i]
                v.data = _ew2(lambda vv, g: self.momentum * vv + self.lr * g, v.data, grad)
                param.data = _ew2(lambda d, vv: d - vv, param.data, v.data)
            else:
                param.data = _ew2(lambda d, g: d - self.lr * g, param.data, grad)


class Adam(Optimizer):
    """Adam 优化器（逐元素实现，作用于嵌套 list / 标量）。"""

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
        bc1 = 1 - self.beta1 ** self._t
        bc2 = 1 - self.beta2 ** self._t
        for i, param in enumerate(self.params):
            if param.grad is None:
                continue
            grad = param.grad.data
            if i >= len(self._m):
                self._m.append(Tensor(data=_zeros_like(param.data)))
                self._v.append(Tensor(data=_zeros_like(param.data)))
            m = self._m[i]
            v = self._v[i]
            m.data = _ew2(lambda mm, g: self.beta1 * mm + (1 - self.beta1) * g, m.data, grad)
            v.data = _ew2(lambda vv, g: self.beta2 * vv + (1 - self.beta2) * g * g, v.data, grad)
            param.data = _ew2(
                lambda d, pair: d - self.lr * (pair[0] / bc1) / (math.sqrt(pair[1] / bc2) + self.eps),
                param.data, _ew2(lambda a, b: (a, b), m.data, v.data))


class Layer:
    """神经网络层基类。"""

    def __init__(self, name: str = ""):
        self.name = name
        self.parameters: list[Tensor] = []
        self.training = True

    def forward(self, x: Tensor) -> Tensor:
        """基类不做恒等假算：未重写即显式拒绝。"""
        raise NotImplementedError(f"层 {self.name or type(self).__name__} 未实现 forward")

    def backward(self, grad_out):
        """未实现反向的层必须显式拒绝，严禁静默返回零梯度。"""
        raise NotImplementedError(
            f"层 {self.name or type(self).__name__} 未实现 backward，训练链请勿使用")

    def __call__(self, x: Tensor) -> Tensor:
        return self.forward(x)

    def eval(self) -> None:
        self.training = False

    def train(self) -> None:
        self.training = True


class Linear(Layer):
    """全连接层：out = X(B×in) · W(in×out) + b。前向/反向均以 matmul 地基实现。"""

    def __init__(self, in_features: int, out_features: int,
                 bias: bool = True):
        super().__init__("linear")
        self.in_features = in_features
        self.out_features = out_features
        self.weight = Tensor(
            data=_rand_matrix(in_features, out_features, 0.1),
            shape=(in_features, out_features),
            requires_grad=True,
        )
        self.bias = Tensor(
            data=[0.0] * out_features,
            shape=(out_features,),
            requires_grad=True,
        ) if bias else None
        self.parameters = [self.weight] + ([self.bias] if bias else [])
        self._last_input: list[list[float]] | None = None

    def forward(self, x: Tensor) -> Tensor:
        _check_matrix(x.data, "Linear.input")
        if len(x.data[0]) != self.in_features:
            raise ValueError(f"Linear 输入宽度 {len(x.data[0])} ≠ in_features {self.in_features}")
        self._last_input = x.data
        out = matmul(x.data, self.weight.data)
        if self.bias is not None:
            out = [_ew2(lambda a, b: a + b, row, self.bias.data) for row in out]
        return Tensor(data=out, shape=(len(out), len(out[0])))

    def backward(self, grad_out):
        if self._last_input is None:
            raise RuntimeError("Linear.backward 在没有前向记录时被调用")
        x = self._last_input
        w = self.weight.data
        self.weight.grad = Tensor(data=matmul(transpose(x), grad_out),
                                  shape=(self.in_features, self.out_features))
        if self.bias is not None:
            self.bias.grad = Tensor(data=colsum(grad_out), shape=(self.out_features,))
        return matmul(grad_out, transpose(w))


class ReLU(Layer):
    """ReLU 激活函数。"""

    def __init__(self):
        super().__init__("relu")
        self._mask = None

    def forward(self, x: Tensor) -> Tensor:
        self._mask = _ew2(lambda v, _v: v > 0, x.data, x.data)
        return Tensor(data=_ew(lambda v: max(0.0, v), x.data), shape=x.shape)

    def backward(self, grad_out):
        return _ew2(lambda g, m: g if m else 0.0, grad_out, self._mask)


class Sigmoid(Layer):
    """Sigmoid 激活函数（数值稳定）。"""

    def __init__(self):
        super().__init__("sigmoid")
        self._last_out = None

    @staticmethod
    def _sig(v: float) -> float:
        if v >= 0:
            return 1.0 / (1.0 + math.exp(-v))
        e = math.exp(v)
        return e / (1.0 + e)

    def forward(self, x: Tensor) -> Tensor:
        self._last_out = _ew(self._sig, x.data)
        return Tensor(data=self._last_out, shape=x.shape)

    def backward(self, grad_out):
        return _ew2(lambda g, s: g * s * (1.0 - s), grad_out, self._last_out)


class Tanh(Layer):
    """Tanh 激活函数。"""

    def __init__(self):
        super().__init__("tanh")
        self._last_out = None

    def forward(self, x: Tensor) -> Tensor:
        self._last_out = _ew(math.tanh, x.data)
        return Tensor(data=self._last_out, shape=x.shape)

    def backward(self, grad_out):
        return _ew2(lambda g, t: g * (1.0 - t * t), grad_out, self._last_out)


class Softmax(Layer):
    """Softmax 激活函数（逐行，数值稳定：先减行最大值）。"""

    def __init__(self, dim: int = -1):
        super().__init__("softmax")
        self.dim = dim
        self._probs = None

    @staticmethod
    def _row(p: list[float]) -> list[float]:
        mx = max(p)
        ex = [math.exp(v - mx) for v in p]
        s = sum(ex)
        return [e / s for e in ex]

    def forward(self, x: Tensor) -> Tensor:
        data = x.data
        if not isinstance(data, list):
            raise ValueError("Softmax 需要二维矩阵输入")
        if data and not isinstance(data[0], list):
            rows = [self._row(data)]  # 单行向量也接受
        else:
            rows = [self._row(r) for r in data]
        self._probs = rows
        shape = x.shape if (data and isinstance(data[0], list)) else (1, len(rows[0]))
        return Tensor(data=rows, shape=shape)

    def backward(self, grad_out):
        # dx_i = p_i * (g_i - Σ_j p_j g_j)
        rows = []
        for g, p in zip(grad_out, self._probs):
            dot = sum(gi * pi for gi, pi in zip(g, p))
            rows.append([pi * (gi - dot) for gi, pi in zip(g, p)])
        return rows


class Dropout(Layer):
    """Dropout 层（训练期真实掩码 + 1/(1-p) inverted scaling；推理期恒等）。

    随机性契约（2026-11 A3 坐实）：seed 非 None → 每次 forward 同掩码（冻结，
    可复现现场/梯度神谕可用）；seed=None → 掩码逐步推进，受全局 random.seed 控制。
    """

    def __init__(self, p: float = 0.5, seed: int | None = None):
        super().__init__("dropout")
        if not (0.0 <= p < 1.0):
            raise ValueError(f"Dropout p 必须在 [0,1)，实得 {p}")
        self.p = p
        self.seed = seed
        self._mask = None

    def forward(self, x: Tensor) -> Tensor:
        if not self.training or self.p == 0.0:
            return Tensor(data=_ew(lambda v: v, x.data), shape=x.shape)
        rng = random.Random(self.seed) if self.seed is not None else random
        scale = 1.0 / (1.0 - self.p)
        self._mask = _ew(lambda v: rng.random() >= self.p, x.data)
        return Tensor(data=_ew2(lambda v, keep: v * scale if keep else 0.0, x.data, self._mask),
                      shape=x.shape)

    def backward(self, grad_out):
        if not self.training or self.p == 0.0:
            return grad_out
        if self._mask is None:
            raise RuntimeError("Dropout.backward 在没有前向记录掩码时被调用")
        scale = 1.0 / (1.0 - self.p)
        return _ew2(lambda g, keep: g * scale if keep else 0.0, grad_out, self._mask)


class BatchNorm(Layer):
    """Batch Normalization（前向/反向均真算；反向为闭式归一化梯度）。"""

    def __init__(self, num_features: int, momentum: float = 0.1, eps: float = 1e-5):
        super().__init__("batch_norm")
        self.num_features = num_features
        self.momentum = momentum
        self.eps = eps
        self.weight = Tensor(data=[1.0] * num_features, shape=(num_features,),
                             requires_grad=True)   # gamma
        self.bias = Tensor(data=[0.0] * num_features, shape=(num_features,),
                           requires_grad=True)     # beta
        self.running_mean = [0.0] * num_features
        self.running_var = [1.0] * num_features
        self.parameters = [self.weight, self.bias]
        self._cache = None  # (hats, gamma, stds, m)：backward 所需的真前向现场

    def forward(self, x: Tensor) -> Tensor:
        _check_matrix(x.data, "BatchNorm.input")
        if len(x.data[0]) != self.num_features:
            raise ValueError("BatchNorm 特征维不匹配")
        b = len(x.data)
        f = self.num_features
        if self.training:
            mean = [sum(r[j] for r in x.data) / b for j in range(f)]
            var = [sum((r[j] - mean[j]) ** 2 for r in x.data) / b for j in range(f)]
            self.running_mean = [(1 - self.momentum) * m + self.momentum * mm
                                 for m, mm in zip(self.running_mean, mean)]
            self.running_var = [(1 - self.momentum) * v + self.momentum * vv
                                for v, vv in zip(self.running_var, var)]
        else:
            mean, var = self.running_mean, self.running_var
        g, beta = self.weight.data, self.bias.data
        out = []
        hats = []
        stds = [math.sqrt(v + self.eps) for v in var]
        for r in x.data:
            row = []
            hat = []
            for j in range(f):
                h = (r[j] - mean[j]) / stds[j]
                hat.append(h)
                row.append(g[j] * h + beta[j])
            hats.append(hat)
            out.append(row)
        self._cache = (hats, list(g), stds, b)
        return Tensor(data=out, shape=x.shape)

    def backward(self, grad_out):
        """闭式 BN 反向：dγ=Σ dout·x̂，dβ=Σ dout，
        dx = (dout·γ − mean(·) − x̂·mean(dout·γ·x̂)) / std（逐特征沿 batch 维）。"""
        if self._cache is None:
            raise RuntimeError("BatchNorm.backward 在没有前向记录时被调用")
        gv = grad_out.data if isinstance(grad_out, Tensor) else grad_out
        _check_matrix(gv, "BatchNorm.grad_out")
        hats, g, stds, m = self._cache
        if len(gv) != m or len(gv[0]) != self.num_features:
            raise ValueError(
                f"BatchNorm 梯度形状 {len(gv)}×{len(gv[0])} ≠ 前向现场 {m}×{self.num_features}")
        f = self.num_features
        dbeta = [sum(gv[i][j] for i in range(m)) for j in range(f)]
        dgamma = [sum(gv[i][j] * hats[i][j] for i in range(m)) for j in range(f)]
        dxhat = [[gv[i][j] * g[j] for j in range(f)] for i in range(m)]
        s_dx = [sum(dxhat[i][j] for i in range(m)) / m for j in range(f)]
        s_dx_hat = [sum(dxhat[i][j] * hats[i][j] for i in range(m)) / m for j in range(f)]
        dx = [[(dxhat[i][j] - s_dx[j] - hats[i][j] * s_dx_hat[j]) / stds[j]
               for j in range(f)] for i in range(m)]
        self.weight.grad = Tensor(data=dgamma, shape=(f,))
        self.bias.grad = Tensor(data=dbeta, shape=(f,))
        return dx


class Conv2D(Layer):
    """2D 卷积层（朴素前向/反向均真算：单样本 (C_in,H,W)）。"""

    def __init__(self, in_channels: int, out_channels: int,
                 kernel_size: int = 3, stride: int = 1,
                 padding: int = 0):
        super().__init__("conv2d")
        if stride < 1:
            raise ValueError(f"stride 必须 ≥1，实得 {stride}")
        if padding < 0:
            raise ValueError(f"padding 必须 ≥0，实得 {padding}")
        self.in_channels = in_channels
        self.out_channels = out_channels
        self.kernel_size = kernel_size
        self.stride = stride
        self.padding = padding
        k, s, pad = kernel_size, stride, padding
        sigma = math.sqrt(2.0 / (in_channels * k * k))
        # data[oc][ic][ky][kx] → 形状 (C_out, C_in, k, k)
        self.weight = Tensor(
            data=[[_rand_matrix(k, k, sigma) for _ in range(in_channels)]
                    for _ in range(out_channels)],
            shape=(out_channels, in_channels, k, k),
            requires_grad=True)
        self.bias = Tensor(data=[0.0] * out_channels, shape=(out_channels,),
                           requires_grad=True)
        self.parameters = [self.weight, self.bias]
        self._last_input = None   # 前向现场：输入 3D 数据（backward 用）
        self._last_geom = None    # (c_in, h, w_in, h_out, w_out)

    def forward(self, x: Tensor) -> Tensor:
        data = x.data
        if (not isinstance(data, list) or not data
                or not isinstance(data[0], list) or not isinstance(data[0][0], list)):
            raise ValueError("Conv2D 前向只接受三维 (C_in,H,W) 单样本输入")
        c_in = len(data)
        h, w_in = len(data[0]), len(data[0][0])
        if c_in != self.in_channels:
            raise ValueError(f"Conv2D 通道数 {c_in} ≠ in_channels {self.in_channels}")
        k, s, pad = self.kernel_size, self.stride, self.padding
        h_out = (h + 2 * pad - k) // s + 1
        w_out = (w_in + 2 * pad - k) // s + 1
        if h_out <= 0 or w_out <= 0:
            raise ValueError("卷积输出为空：核/步长/填充与输入尺寸不兼容")
        wt, bias = self.weight.data, self.bias.data
        out = [[[0.0] * w_out for _ in range(h_out)] for _ in range(self.out_channels)]
        self._last_input = data
        self._last_geom = (c_in, h, w_in, h_out, w_out)
        for oc in range(self.out_channels):
            for oy in range(h_out):
                for ox in range(w_out):
                    acc = bias[oc]
                    for ic in range(c_in):
                        for ky in range(k):
                            for kx in range(k):
                                iy = oy * s + ky - pad
                                ix = ox * s + kx - pad
                                if 0 <= iy < h and 0 <= ix < w_in:
                                    acc += data[ic][iy][ix] * wt[oc][ic][ky][kx]
                    out[oc][oy][ox] = acc
        return Tensor(data=out, shape=(self.out_channels, h_out, w_out))

    def backward(self, grad_out):
        """闭式卷积反向（与朴素前向逐路对应）：
        dW[oc][ic][ky][kx] = Σ_{oy,ox} dout·in；db[oc] = Σ dout；
        dIn[ic][iy][ix] = Σ_{oc,ky,kx} dout·W（窗位整除且InRange 才可回流）。"""
        if self._last_input is None:
            raise RuntimeError("Conv2D.backward 在没有前向记录时被调用")
        gv = grad_out.data if isinstance(grad_out, Tensor) else grad_out
        if (not isinstance(gv, list) or not gv or not isinstance(gv[0], list)
                or not isinstance(gv[0][0], list)):
            raise ValueError("Conv2D.backward 需要三维 (C_out,h_out,w_out) 梯度")
        c_in, h, w_in, h_out, w_out = self._last_geom
        if len(gv) != self.out_channels or len(gv[0]) != h_out or len(gv[0][0]) != w_out:
            raise ValueError(
                f"Conv2D 梯度形状 {len(gv)}×{len(gv[0])}×{len(gv[0][0])}"
                f" ≠ 前向输出 {self.out_channels}×{h_out}×{w_out}")
        data = self._last_input
        k, s, pad = self.kernel_size, self.stride, self.padding
        wt = self.weight.data
        dw = [[[ [0.0] * k for _ in range(k)] for _ in range(c_in)]
              for _ in range(self.out_channels)]
        db = [0.0] * self.out_channels
        din = [[[0.0] * w_in for _ in range(h)] for _ in range(c_in)]
        for oc in range(self.out_channels):
            db[oc] = sum(gv[oc][oy][ox] for oy in range(h_out) for ox in range(w_out))
            for ic in range(c_in):
                for ky in range(k):
                    for kx in range(k):
                        acc = 0.0
                        for oy in range(h_out):
                            for ox in range(w_out):
                                iy = oy * s + ky - pad
                                ix = ox * s + kx - pad
                                if 0 <= iy < h and 0 <= ix < w_in:
                                    acc += gv[oc][oy][ox] * data[ic][iy][ix]
                        dw[oc][ic][ky][kx] = acc
            for ic in range(c_in):
                for ky in range(k):
                    for kx in range(k):
                        for oy in range(h_out):
                            for ox in range(w_out):
                                iy = oy * s + ky - pad
                                ix = ox * s + kx - pad
                                if 0 <= iy < h and 0 <= ix < w_in:
                                    din[ic][iy][ix] += gv[oc][oy][ox] * wt[oc][ic][ky][kx]
        self.weight.grad = Tensor(data=dw, shape=(self.out_channels, c_in, k, k))
        self.bias.grad = Tensor(data=db, shape=(self.out_channels,))
        return din


class Model:
    """神经网络模型。"""

    def __init__(self, name: str = "Model"):
        self.name = name
        self.layers: list[Layer] = []
        self.parameters: list[Tensor] = []
        self.loss_fn: LossFunction | None = None
        self.optimizer: Optimizer | None = None
        self._graph = ComputationGraph()

    def add(self, layer: Layer) -> None:
        self.layers.append(layer)
        self.parameters.extend(layer.parameters)

    def compile(self, loss: LossFunction, optimizer: Optimizer) -> None:
        self.loss_fn = loss
        self.optimizer = optimizer

    def eval(self) -> None:
        """推理态级联：所有层走 eval（BN 用 running、Dropout 恒等）。"""
        for layer in self.layers:
            layer.eval()

    def train(self) -> None:
        """训练态级联：恢复所有层 training=True。"""
        for layer in self.layers:
            layer.train()

    def forward(self, x: Tensor) -> Tensor:
        for layer in self.layers:
            x = layer(x)
        return x

    def train_step(self, x: Tensor, y: Tensor) -> float:
        """真实前向 → 损失 → 逐层反向 → 优化器更新；返回损失值（非恒 0）。"""
        if self.loss_fn is None or self.optimizer is None:
            raise ValueError("train_step 前必须先 compile(loss, optimizer)")
        self.optimizer.zero_grad()
        output = self.forward(x)
        loss_t = self.loss_fn(output, y)
        g = self.loss_fn.backward(output, y)
        for layer in reversed(self.layers):
            g = layer.backward(g)
        self.optimizer.step()
        return loss_t.data

    def evaluate(self, x: Tensor, y: Tensor) -> dict[str, float]:
        """真实计算 MSE loss 与逐行 argmax 准确率（不再硬编码 0/1）。"""
        out = self.forward(x)
        o, yv = out.data, y.data
        _check_matrix(o, "evaluate.output")
        _check_matrix(yv, "evaluate.target")
        n = len(o) * len(o[0])
        loss = sum((a - b) ** 2 for row_o, row_y in zip(o, yv)
                   for a, b in zip(row_o, row_y)) / n
        correct = sum(1 for row_o, row_y in zip(o, yv)
                      if row_o.index(max(row_o)) == row_y.index(max(row_y)))
        return {"loss": loss, "accuracy": correct / len(o)}

    # ── 序列化：真存真读（线性/BN/Conv 参数逐字段往返，未知层显式拒绝） ──
    _SAVEABLE = ("linear", "sigmoid", "tanh", "relu", "softmax", "dropout",
                 "batch_norm", "conv2d")

    def save(self, path: str) -> None:
        specs = []
        for layer in self.layers:
            if layer.name not in self._SAVEABLE:
                raise ValueError(
                    f"save 不支持层类型 {layer.name!r}——拒绝静默丢参数（显式）")
            spec: dict[str, Any] = {"type": layer.name}
            if isinstance(layer, Linear):
                spec["in_features"] = layer.in_features
                spec["out_features"] = layer.out_features
                spec["weight"] = layer.weight.data
                spec["bias"] = layer.bias.data if layer.bias else None
            elif isinstance(layer, Dropout):
                spec["p"] = layer.p
            elif isinstance(layer, BatchNorm):
                spec.update(num_features=layer.num_features,
                            momentum=layer.momentum, eps=layer.eps,
                            weight=layer.weight.data, bias=layer.bias.data,
                            running_mean=layer.running_mean,
                            running_var=layer.running_var)
            elif isinstance(layer, Conv2D):
                spec.update(in_channels=layer.in_channels,
                            out_channels=layer.out_channels,
                            kernel_size=layer.kernel_size,
                            stride=layer.stride, padding=layer.padding,
                            weight=layer.weight.data, bias=layer.bias.data)
            specs.append(spec)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"name": self.name, "layers": specs}, f, ensure_ascii=False)

    def load(self, path: str) -> None:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.name = data["name"]
        self.layers = []
        self.parameters = []
        for spec in data["layers"]:
            t = spec["type"]
            if t == "linear":
                layer = Linear(spec["in_features"], spec["out_features"],
                               bias=spec.get("bias") is not None)
                layer.weight.data = spec["weight"]
                if layer.bias and spec.get("bias") is not None:
                    layer.bias.data = spec["bias"]
            elif t == "relu":
                layer = ReLU()
            elif t == "sigmoid":
                layer = Sigmoid()
            elif t == "tanh":
                layer = Tanh()
            elif t == "softmax":
                layer = Softmax()
            elif t == "dropout":
                layer = Dropout(p=spec.get("p", 0.5))
            elif t == "batch_norm":
                layer = BatchNorm(spec["num_features"],
                                  momentum=spec["momentum"], eps=spec["eps"])
                layer.weight.data = spec["weight"]
                layer.bias.data = spec["bias"]
                layer.running_mean = spec["running_mean"]
                layer.running_var = spec["running_var"]
            elif t == "conv2d":
                layer = Conv2D(spec["in_channels"], spec["out_channels"],
                               kernel_size=spec["kernel_size"],
                               stride=spec["stride"], padding=spec["padding"])
                layer.weight.data = spec["weight"]
                layer.bias.data = spec["bias"]
            else:
                raise ValueError(f"load 不支持的层类型：{t}")
            self.add(layer)


class LossFunction(Layer):
    """损失函数基类：forward(logits, targets) → 标量 Tensor。"""

    def __init__(self, name: str = "mse"):
        super().__init__(name)

    def forward(self, x: Tensor, y: Tensor) -> Tensor:
        raise NotImplementedError(f"损失 {self.name} 未实现 forward")

    def backward(self, x: Tensor | list, y: list):
        raise NotImplementedError(f"损失 {self.name} 未实现 backward")

    def __call__(self, x: Tensor, y: Tensor) -> Tensor:
        return self.forward(x, y)


class MSELoss(LossFunction):
    """均方误差损失：mean((o-y)²)，梯度 2(o-y)/n。"""

    def __init__(self):
        super().__init__("mse")

    def forward(self, x: Tensor, y: Tensor) -> Tensor:
        _check_matrix(x.data, "MSELoss.output")
        _check_matrix(y.data, "MSELoss.target")
        if len(x.data) != len(y.data) or len(x.data[0]) != len(y.data[0]):
            raise ValueError("MSELoss 形状不匹配")
        n = len(x.data) * len(x.data[0])
        total = sum((a - b) ** 2 for ro, ry in zip(x.data, y.data)
                    for a, b in zip(ro, ry))
        return Tensor(data=total / n, shape=())

    def backward(self, x: Tensor | list, y):
        o = x.data if isinstance(x, Tensor) else x
        yv = y.data if isinstance(y, Tensor) else y
        n = len(o) * len(o[0])
        return [[2.0 * (a - b) / n for a, b in zip(ro, ry)]
                for ro, ry in zip(o, yv)]


class CrossEntropyLoss(LossFunction):
    """交叉熵损失（logits + one-hot 目标），梯度 (softmax - y)/B。"""

    def __init__(self):
        super().__init__("cross_entropy")
        self._probs = None

    @staticmethod
    def _row(logits: list[float]) -> list[float]:
        mx = max(logits)
        ex = [math.exp(v - mx) for v in logits]
        s = sum(ex)
        return [e / s for e in ex]

    def forward(self, x: Tensor, y: Tensor) -> Tensor:
        _check_matrix(x.data, "CrossEntropy.output")
        _check_matrix(y.data, "CrossEntropy.target")
        probs = [self._row(r) for r in x.data]
        self._probs = probs
        eps = 1e-15
        b = len(probs)
        total = -sum(t * math.log(p + eps) for rp, ry in zip(probs, y.data)
                     for p, t in zip(rp, ry))
        return Tensor(data=total / b, shape=())

    def backward(self, x: Tensor | list, y):
        yv = y.data if isinstance(y, Tensor) else y
        b = len(self._probs)
        return [[(p - t) / b for p, t in zip(rp, ry)]
                for rp, ry in zip(self._probs, yv)]


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
        """训练模型；patience 非 None 时启用早停。loss/accuracy 为真实读数。"""
        self.history = {"loss": [], "accuracy": []}
        self._early_stopped = False
        for _ in range(self.epochs):
            loss = self.model.train_step(X, y)
            self.history["loss"].append(loss)
            self.history["accuracy"].append(
                self.model.evaluate(X, y)["accuracy"])
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
    """自动微分引擎（grad/jacobian 为有限差分数值微分，非真反向模式）。"""

    def __init__(self):
        self._graph = ComputationGraph()
        self._tape: list[Operation] = []

    def __call__(self, func: callable) -> callable:
        def wrapper(*args):
            return func(*args)
        return wrapper

    def grad(self, func: callable,
              arg_num: int = 0) -> callable:
        """对第 arg_num 个标量参数的前向差分数值导数。"""
        def gradient(*args):
            x = args[arg_num]
            eps = 1e-5
            f_x = func(*args)
            args_list = list(args)
            args_list[arg_num] = x + eps
            f_x_plus = func(*args_list)
            return (f_x_plus - f_x) / eps
        return gradient

    def jacobian(self, func: callable, eps: float = 1e-5) -> callable:
        """f: R^n → R^m 的数值雅可比（历史缺陷：恒等透传，已修）。"""
        def jac(x0: list[float]) -> list[list[float]]:
            base = list(func(list(x0)))
            m, n = len(base), len(x0)
            cols = []
            for j in range(n):
                xp = list(x0)
                xp[j] += eps
                fp = list(func(xp))
                cols.append([(fp[i] - base[i]) / eps for i in range(m)])
            return transpose(cols)
        return jac


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
    # Matha `f(a, b)` 两侧均编译为 f(a)(b)，零参 `f()` 传入常量 0：
    # 注册形态一律柯里化 lambda 链；无参创建器接收哑参 `_`；
    # Python 侧默认参数在此显式化为必填参。`创建神经网络` 归 neural_network 插件。
    builtins["创建张量"] = lambda shape: Tensor(
        data=[[0.0] * shape[1] for _ in range(shape[0])],
        shape=tuple(shape))
    builtins["矩阵乘法"] = lambda a: lambda b: matmul(a, b)
    builtins["创建模型"] = lambda name: Sequential(name=name)
    builtins["创建线性层"] = lambda in_f: lambda out_f: Linear(in_f, out_f)
    builtins["创建ReLU"] = lambda _: ReLU()
    builtins["创建Sigmoid"] = lambda _: Sigmoid()
    builtins["创建Tanh"] = lambda _: Tanh()
    builtins["创建Softmax"] = lambda dim: Softmax(dim)
    builtins["创建Dropout"] = lambda p: Dropout(p)
    builtins["创建BatchNorm"] = lambda n: BatchNorm(n)
    builtins["创建Adam"] = lambda params: lambda lr: Adam(params, lr)
    builtins["创建SGD"] = lambda params: lambda lr: SGD(params, lr)
    builtins["创建训练器"] = lambda model: lambda epochs: Trainer(model, epochs)
    builtins["创建自动微分"] = lambda _: AutoDiff()


def _ai_framework_names() -> list[str]:
    return ["创建张量", "矩阵乘法", "创建模型", "创建线性层", "创建ReLU",
            "创建Sigmoid", "创建Tanh",
            "创建Softmax", "创建Dropout", "创建BatchNorm",
            "创建Adam", "创建SGD", "创建训练器",
            "创建自动微分"]


__all__ = [
    "TensorType", "Device", "OpType",
    "Tensor", "Operation", "ComputationGraph",
    "matmul", "transpose", "colsum",
    "Optimizer", "SGD", "Adam",
    "Layer", "Linear", "Conv2D", "ReLU", "Sigmoid", "Tanh", "Softmax",
    "Dropout", "BatchNorm", "LossFunction", "MSELoss",
    "CrossEntropyLoss", "Model", "Sequential", "Trainer",
    "AutoDiff", "NeuralNetwork",
    "_register_ai_framework", "_ai_framework_names",
]
