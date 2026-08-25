# -*- coding: utf-8 -*-
"""
Matha AI 与数据科学领域模块。

覆盖：
  1) 激活函数：sigmoid, relu, softmax, tanh
  2) 损失函数：MSE, MAE, cross_entropy, log_loss
  3) 优化器：SGD, Adam
  4) 前向/反向传播
  5) 矩阵运算
"""
from __future__ import annotations
import math
from typing import Optional


# ============================================================
# 激活函数
# ============================================================

def sigmoid(x: float) -> float:
    """Sigmoid 激活函数。"""
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    else:
        ez = math.exp(x)
        return ez / (1.0 + ez)


def sigmoid_deriv(x: float) -> float:
    """Sigmoid 导数。"""
    s = sigmoid(x)
    return s * (1.0 - s)


def relu(x: float) -> float:
    """ReLU 激活函数。"""
    return max(0.0, x)


def relu_deriv(x: float) -> float:
    """ReLU 导数。"""
    return 1.0 if x > 0 else 0.0


def softmax(values: list[float]) -> list[float]:
    """Softmax 激活函数。"""
    max_v = max(values)
    exps = [math.exp(v - max_v) for v in values]
    total = sum(exps)
    return [e / total for e in exps]


def tanh(x: float) -> float:
    """Tanh 激活函数。"""
    return math.tanh(x)


# ============================================================
# 损失函数
# ============================================================

def mse(y_true: list[float], y_pred: list[float]) -> float:
    """均方误差。"""
    n = len(y_true)
    return sum((t - p) ** 2 for t, p in zip(y_true, y_pred)) / n


def mae(y_true: list[float], y_pred: list[float]) -> float:
    """平均绝对误差。"""
    n = len(y_true)
    return sum(abs(t - p) for t, p in zip(y_true, y_pred)) / n


def cross_entropy(y_true: list[float], y_pred: list[float]) -> float:
    """交叉熵损失。"""
    eps = 1e-15
    total = 0.0
    for t, p in zip(y_true, y_pred):
        p = max(eps, min(1.0 - eps, p))
        total += t * math.log(p) + (1.0 - t) * math.log(1.0 - p)
    return -total / len(y_true)


def log_loss(y_true: list[float], y_pred: list[float]) -> float:
    """对数损失（同交叉熵）。"""
    return cross_entropy(y_true, y_pred)


def accuracy(y_true: list[float], y_pred: list[float]) -> float:
    """准确率。"""
    n = len(y_true)
    correct = sum(1 for t, p in zip(y_true, y_pred) if round(t) == round(p))
    return correct / n


# ============================================================
# 线性代数
# ============================================================

def dot_product(a: list[float], b: list[float]) -> float:
    """点积。"""
    return sum(x * y for x, y in zip(a, b))


def matrix_mult(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    """矩阵乘法。"""
    rows_a, cols_a = len(a), len(a[0])
    rows_b, cols_b = len(b), len(b[0])
    assert cols_a == rows_b, f"矩阵维度不匹配: {cols_a} != {rows_b}"
    result = [[0.0] * cols_b for _ in range(rows_a)]
    for i in range(rows_a):
        for j in range(cols_b):
            for k in range(cols_a):
                result[i][j] += a[i][k] * b[k][j]
    return result


def transpose(matrix: list[list[float]]) -> list[list[float]]:
    """矩阵转置。"""
    rows, cols = len(matrix), len(matrix[0])
    return [[matrix[j][i] for j in range(rows)] for i in range(cols)]


def matrix_add(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    """矩阵加法。"""
    return [[a[i][j] + b[i][j] for j in range(len(a[0]))] for i in range(len(a))]


# ============================================================
# 优化器
# ============================================================

class AdamOptimizer:
    """Adam 优化器。"""

    def __init__(self, lr: float = 0.001, beta1: float = 0.9, beta2: float = 0.999, eps: float = 1e-8):
        self.lr = lr
        self.beta1 = beta1
        self.beta2 = beta2
        self.eps = eps
        self.m: dict = {}
        self.v: dict = {}
        self.t = 0

    def step(self, params: dict, grads: dict) -> dict:
        """更新参数。"""
        self.t += 1
        for key in params:
            if key not in self.m:
                self.m[key] = 0.0
                self.v[key] = 0.0
            self.m[key] = self.beta1 * self.m[key] + (1.0 - self.beta1) * grads.get(key, 0)
            self.v[key] = self.beta2 * self.v[key] + (1.0 - self.beta2) * grads.get(key, 0) ** 2
            m_hat = self.m[key] / (1.0 - self.beta1 ** self.t)
            v_hat = self.v[key] / (1.0 - self.beta2 ** self.t)
            params[key] -= self.lr * m_hat / (math.sqrt(v_hat) + self.eps)
        return params


def gradient_descent(params: dict, grads: dict, lr: float = 0.001) -> dict:
    """SGD 梯度下降。"""
    for key in params:
        params[key] -= lr * grads.get(key, 0)
    return params


# ============================================================
# 前向/反向传播
# ============================================================

def forward_prop(layers: list[list[float]], weights: list[list[list[float]]], biases: list[list[float]]) -> list[list[float]]:
    """前向传播。"""
    outputs = [layers[0]]
    for i in range(len(weights)):
        z = matrix_add(matrix_mult(outputs[-1], weights[i]), biases[i])
        a = [sigmoid(x) for x in z[0]]
        outputs.append([a])
    return outputs


def backward_prop(
    layers: list[list[float]],
    weights: list[list[list[float]]],
    outputs: list[list[float]],
    y_true: list[float]
) -> tuple[list[list[list[float]]], list[list[float]]]:
    """反向传播（简化版）。"""
    n_layers = len(weights)
    d_weights = [[[0.0 for _ in w] for w in layer] for layer in weights]
    d_biases = [[0.0 for _ in b] for b in biases]

    # 输出层梯度
    delta = [outputs[-1][0][i] - y_true[i] for i in range(len(y_true))]

    for i in range(n_layers - 1, -1, -1):
        for j in range(len(weights[i])):
            for k in range(len(weights[i][j])):
                d_weights[i][j][k] = delta[j] * outputs[i][0][k]
            d_biases[i][j] = delta[j]

        if i > 0:
            new_delta = []
            for k in range(len(weights[i - 1][0])):
                s = sum(delta[j] * weights[i][j][k] for j in range(len(delta)))
                s *= sigmoid_deriv(outputs[i][0][k])
                new_delta.append(s)
            delta = new_delta

    return d_weights, d_biases


# ============================================================
# 统计数据
# ============================================================

def mean(values: list[float]) -> float:
    """平均值。"""
    return sum(values) / len(values) if values else 0.0


def variance(values: list[float]) -> float:
    """方差。"""
    m = mean(values)
    return sum((x - m) ** 2 for x in values) / len(values) if values else 0.0


def std(values: list[float]) -> float:
    """标准差。"""
    return math.sqrt(variance(values))


def correlation(x: list[float], y: list[float]) -> float:
    """皮尔逊相关系数。"""
    n = len(x)
    if n == 0:
        return 0.0
    mx, my = mean(x), mean(y)
    num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    dx = math.sqrt(sum((xi - mx) ** 2 for xi in x))
    dy = math.sqrt(sum((yi - my) ** 2 for yi in y))
    return num / (dx * dy) if dx * dy != 0 else 0.0


# ============================================================
# 模块导出
# ============================================================

__all__ = [
    # 激活函数
    "sigmoid", "sigmoid_deriv", "relu", "relu_deriv", "softmax", "tanh",
    # 损失函数
    "mse", "mae", "cross_entropy", "log_loss", "accuracy",
    # 线性代数
    "dot_product", "matrix_mult", "transpose", "matrix_add",
    # 优化器
    "AdamOptimizer", "gradient_descent",
    # 反向传播
    "forward_prop", "backward_prop",
    # 统计
    "mean", "variance", "std", "correlation",
]


# ============================================================
# 注册到解释器
# ============================================================

def _register_ai_data_science(builtins: dict) -> None:
    """注册 AI 与数据科学内建到解释器。"""
    builtins["sigmoid"] = sigmoid
    builtins["sigmoid_deriv"] = sigmoid_deriv
    builtins["relu"] = relu
    builtins["relu_deriv"] = relu_deriv
    builtins["softmax"] = softmax
    builtins["tanh"] = tanh
    builtins["mse"] = mse
    builtins["mae"] = mae
    builtins["cross_entropy"] = cross_entropy
    builtins["log_loss"] = log_loss
    builtins["accuracy"] = accuracy
    builtins["dot_product"] = dot_product
    builtins["matrix_mult"] = matrix_mult
    builtins["transpose"] = transpose
    builtins["matrix_add"] = matrix_add
    builtins["gradient_descent"] = gradient_descent
    builtins["mean"] = mean
    builtins["variance"] = variance
    builtins["std"] = std
    builtins["correlation"] = correlation


def _ai_data_science_symtab_names() -> list[str]:
    return [
        "sigmoid", "sigmoid_deriv", "relu", "relu_deriv", "softmax", "tanh",
        "mse", "mae", "cross_entropy", "log_loss", "accuracy",
        "dot_product", "matrix_mult", "transpose", "matrix_add",
        "gradient_descent", "mean", "variance", "std", "correlation",
    ]
