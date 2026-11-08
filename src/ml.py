"""Matha 机器学习：线性回归、逻辑回归、K-Means 聚类（纯标准库 SGD/Lloyd 实现）。

行为级锁见 tests/test_ml_models.py：闭式解对拍、收敛、显式拒绝。
ModelType 中未实现的类型（decision_tree/random_forest/neural_network/knn/svm/
naive_bayes）在 create_model 处显式抛 NotImplementedError，不静默回退。

阶段 3 边界口径：未训练 predict 显式拒绝（不再静默返回偏置假值/min([]) 崩溃）；
特征维度不合显式拒绝；sigmoid 双向数值稳定（|z| 极大饱和不溢出）；
学习率/epochs/k/max_iters 构造期校验；逻辑回归标签限 0/1、阈值限 [0,1]。
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ModelType(Enum):
    """模型类型。"""
    LINEAR_REGRESSION = "linear_regression"
    LOGISTIC_REGRESSION = "logistic_regression"
    DECISION_TREE = "decision_tree"
    RANDOM_FOREST = "random_forest"
    NEURAL_NETWORK = "neural_network"
    KNN = "knn"
    KMEANS = "kmeans"
    SVM = "svm"
    NAIVE_BAYES = "naive_bayes"


class Metric(Enum):
    """评估指标。"""
    ACCURACY = "accuracy"
    PRECISION = "precision"
    RECALL = "recall"
    F1_SCORE = "f1_score"
    MSE = "mse"
    RMSE = "rmse"
    R2_SCORE = "r2_score"


@dataclass
class ModelResult:
    """模型结果。"""
    model_type: ModelType
    accuracy: float = 0.0
    loss: float = 0.0
    predictions: list[Any] = field(default_factory=list)
    coefficients: dict[str, float] = field(default_factory=dict)
    feature_importance: dict[str, float] = field(default_factory=dict)
    bias: float = 0.0


@dataclass
class DatasetML:
    """机器学习数据集。"""
    features: list[list[float]] = field(default_factory=list)
    labels: list[Any] = field(default_factory=list)
    test_split: float = 0.2


def _validate_train_params(lr, epochs) -> None:
    if (isinstance(lr, bool) or not isinstance(lr, (int, float))
            or lr <= 0 or (isinstance(lr, float) and not math.isfinite(lr))):
        raise ValueError(f"学习率须为正有限数值：{lr!r}")
    if isinstance(epochs, bool) or not isinstance(epochs, int) or epochs < 1:
        raise ValueError(f"epochs 须为正整数：{epochs!r}")


def _validate_matrix(X: list[list[float]]) -> int:
    """校验样本矩阵（调用方已查空）：行非空、等宽，返回特征数。"""
    n_features = len(X[0])
    if n_features == 0:
        raise ValueError("样本特征为空")
    if any(len(row) != n_features for row in X):
        raise ValueError("样本特征维度不一致")
    return n_features


class LinearRegression:
    """线性回归。"""

    def __init__(self, learning_rate: float = 0.01,
                    epochs: int = 100):
        _validate_train_params(learning_rate, epochs)
        self.lr = learning_rate
        self.epochs = epochs
        self.weights: list[float] = []
        self.bias = 0.0
        self.trained = False

    def fit(self, X: list[list[float]], y: list[float]) -> ModelResult:
        """训练。"""
        if not X or not y:
            raise ValueError("训练数据为空")
        if len(X) != len(y):
            raise ValueError(f"样本数与标签数不一致：{len(X)} ≠ {len(y)}")
        n_samples = len(X)
        n_features = _validate_matrix(X)
        self.weights = [0.0] * n_features

        for epoch in range(self.epochs):
            for i in range(n_samples):
                prediction = sum(X[i][j] * self.weights[j]
                                  for j in range(n_features)) + self.bias
                error = prediction - y[i]
                for j in range(n_features):
                    self.weights[j] -= self.lr * error * X[i][j]
                self.bias -= self.lr * error

        self.trained = True
        # 计算损失
        mse = self._mse(X, y)
        return ModelResult(
            model_type=ModelType.LINEAR_REGRESSION,
            loss=mse,
            coefficients={f"w{i}": self.weights[i]
                           for i in range(n_features)},
            bias=self.bias
        )

    def predict(self, X: list[list[float]]) -> list[float]:
        """预测。未训练/维度不合显式拒绝，不静默返回偏置假值。"""
        if not self.trained:
            raise ValueError("模型未训练，请先 fit")
        if any(len(row) != len(self.weights) for row in X):
            raise ValueError("样本特征维度不一致")
        return [sum(x[j] * self.weights[j]
                     for j in range(len(self.weights))) + self.bias
                for x in X]

    def _mse(self, X: list[list[float]], y: list[float]) -> float:
        """均方误差。"""
        preds = self.predict(X)
        return sum((p - t) ** 2 for p, t in zip(preds, y)) / len(y)


class LogisticRegression:
    """逻辑回归。"""

    def __init__(self, learning_rate: float = 0.01,
                    epochs: int = 100):
        _validate_train_params(learning_rate, epochs)
        self.lr = learning_rate
        self.epochs = epochs
        self.weights: list[float] = []
        self.bias = 0.0
        self.trained = False

    def _sigmoid(self, z: float) -> float:
        """Sigmoid（双向数值稳定：|z| 极大时饱和，不 exp 溢出）。"""
        if z >= 0:
            return 1.0 / (1.0 + math.exp(-z))
        ez = math.exp(z)
        return ez / (1.0 + ez)

    def fit(self, X: list[list[float]], y: list[int]
                 ) -> ModelResult:
        """训练。"""
        if not X or not y:
            raise ValueError("训练数据为空")
        if len(X) != len(y):
            raise ValueError(f"样本数与标签数不一致：{len(X)} ≠ {len(y)}")
        if any(t not in (0, 1) for t in y):
            raise ValueError("逻辑回归标签须为 0/1")
        n_samples = len(X)
        n_features = _validate_matrix(X)
        self.weights = [0.0] * n_features

        for epoch in range(self.epochs):
            for i in range(n_samples):
                z = sum(X[i][j] * self.weights[j]
                         for j in range(n_features)) + self.bias
                pred = self._sigmoid(z)
                error = pred - y[i]
                for j in range(n_features):
                    self.weights[j] -= self.lr * error * X[i][j]
                self.bias -= self.lr * error

        self.trained = True
        mse = self._mse(X, y)
        return ModelResult(
            model_type=ModelType.LOGISTIC_REGRESSION,
            loss=mse,
            coefficients={f"w{i}": self.weights[i]
                           for i in range(n_features)},
            bias=self.bias
        )

    def predict(self, X: list[list[float]],
                   threshold: float = 0.5) -> list[int]:
        """预测。未训练/维度不合/阈值越界显式拒绝。"""
        if not self.trained:
            raise ValueError("模型未训练，请先 fit")
        if any(len(row) != len(self.weights) for row in X):
            raise ValueError("样本特征维度不一致")
        if (isinstance(threshold, bool) or not isinstance(threshold, (int, float))
                or not 0 <= threshold <= 1):
            raise ValueError(f"阈值须在 [0, 1] 内：{threshold!r}")
        preds = []
        for x in X:
            z = sum(x[j] * self.weights[j]
                     for j in range(len(self.weights))) + self.bias
            preds.append(1 if self._sigmoid(z) >= threshold else 0)
        return preds

    def _mse(self, X: list[list[float]], y: list[int]) -> float:
        preds = self.predict(X)
        return sum((p - t) ** 2 for p, t in zip(preds, y)) / len(y)


class KMeans:
    """K-Means 聚类。"""

    def __init__(self, k: int = 3, max_iters: int = 100):
        if isinstance(k, bool) or not isinstance(k, int) or k < 1:
            raise ValueError(f"簇数 k 必须 ≥ 1：{k}")
        if isinstance(max_iters, bool) or not isinstance(max_iters, int) or max_iters < 1:
            raise ValueError(f"max_iters 须为正整数：{max_iters!r}")
        self.k = k
        self.max_iters = max_iters
        self.centroids: list[list[float]] = []
        self.labels: list[int] = []
        self.inertia = 0.0
        self.trained = False

    def fit(self, X: list[list[float]]) -> ModelResult:
        """训练。"""
        n = len(X)
        if n == 0:
            raise ValueError("训练数据为空")
        if n < self.k:
            raise ValueError(f"样本数 {n} 小于簇数 k={self.k}")
        n_features = _validate_matrix(X)

        # 初始化质心
        indices = random.sample(range(n), self.k)
        self.centroids = [X[i] for i in indices]

        for _ in range(self.max_iters):
            # 分配簇
            self.labels = self._assign_clusters(X)
            # 更新质心
            new_centroids = self._update_centroids(X, n_features)
            if new_centroids == self.centroids:
                break
            self.centroids = new_centroids

        self.trained = True
        self.inertia = self._compute_inertia(X)
        return ModelResult(
            model_type=ModelType.KMEANS,
            loss=self.inertia,
            coefficients={f"cluster_{i}": len([l for l in self.labels if l == i])
                           for i in range(self.k)}
        )

    def predict(self, X: list[list[float]]) -> list[int]:
        """预测簇。未训练/维度不合显式拒绝（不再 min([]) 裸抛）。"""
        if not self.trained:
            raise ValueError("模型未训练，请先 fit")
        width = len(self.centroids[0])
        if any(len(row) != width for row in X):
            raise ValueError("样本特征维度不一致")
        return self._assign_clusters(X)

    def _assign_clusters(self, X: list[list[float]]) -> list[int]:
        """分配簇。"""
        labels = []
        for point in X:
            distances = [sum((point[j] - c[j]) ** 2
                              for j in range(len(point)))
                          for c in self.centroids]
            labels.append(distances.index(min(distances)))
        return labels

    def _update_centroids(self, X: list[list[float]],
                            n_features: int) -> list[list[float]]:
        """更新质心。"""
        new_centroids = []
        for i in range(self.k):
            cluster_points = [X[j] for j in range(len(X))
                               if self.labels[j] == i]
            if cluster_points:
                new_centroids.append([sum(p[f] for p in cluster_points) / len(cluster_points)
                                      for f in range(n_features)])
            else:
                new_centroids.append(self.centroids[i])
        return new_centroids

    def _compute_inertia(self, X: list[list[float]]) -> float:
        """计算惯性。"""
        inertia = 0.0
        for i, point in enumerate(X):
            c = self.centroids[self.labels[i]]
            inertia += sum((point[j] - c[j]) ** 2
                            for j in range(len(point)))
        return inertia


class MathaML:
    """Matha ML 管理器。"""

    def __init__(self):
        self._models: dict[str, Any] = {}
        self._initialized = False
        self._init_ml()

    def _init_ml(self) -> None:
        """初始化 ML 管理器。"""
        self._initialized = True

    def create_model(self, model_type: str,
                        **params: Any) -> Any:
        """创建模型。未实现的类型显式拒绝，绝不静默回退线性回归。"""
        mt = ModelType(model_type)
        if mt == ModelType.LINEAR_REGRESSION:
            model = LinearRegression(**params)
        elif mt == ModelType.LOGISTIC_REGRESSION:
            model = LogisticRegression(**params)
        elif mt == ModelType.KMEANS:
            model = KMeans(**params)
        else:
            raise NotImplementedError(
                f"模型类型 {model_type!r} 未实现"
                "（当前支持：linear_regression / logistic_regression / kmeans）")
        self._models[model_type] = model
        return model

    def train(self, model_type: str, X: list[list[float]],
                 y: list[Any]) -> ModelResult:
        """训练模型。"""
        model = self._models.get(model_type)
        if model is None:
            model = self.create_model(model_type)
        if isinstance(model, KMeans):
            return model.fit(X)
        return model.fit(X, y)

    def predict(self, model_type: str, X: list[list[float]]
                   ) -> list[Any]:
        """预测。"""
        model = self._models.get(model_type)
        if model is None:
            raise LookupError(f"模型 {model_type!r} 尚未创建，请先 create_model/train")
        return model.predict(X)

    def evaluate(self, model_type: str, X: list[list[float]],
                    y: list[Any],
                    metric: str = "accuracy") -> float:
        """评估模型。未实现的指标显式拒绝，不返回假 0.0。"""
        if not y:
            raise ValueError("评估数据为空")
        if len(X) != len(y):
            raise ValueError(f"样本数与标签数不一致：{len(X)} ≠ {len(y)}")
        preds = self.predict(model_type, X)
        if metric == "accuracy":
            correct = sum(1 for p, t in zip(preds, y) if p == t)
            return correct / len(y)
        elif metric == "mse":
            return sum((p - t) ** 2 for p, t in zip(preds, y)) / len(y)
        raise NotImplementedError(
            f"评估指标 {metric!r} 未实现（当前支持：accuracy / mse）")

    def get_stats(self) -> dict:
        """获取统计信息。"""
        return {
            "initialized": self._initialized,
            "models": len(self._models),
        }


# ============================================================
# 内置注册
# ============================================================

def create_linear_regression(learning_rate: float = 0.01,
                                epochs: int = 100) -> LinearRegression:
    """创建线性回归。"""
    return LinearRegression(learning_rate, epochs)


def create_logistic_regression(learning_rate: float = 0.01,
                                  epochs: int = 100) -> LogisticRegression:
    """创建逻辑回归。"""
    return LogisticRegression(learning_rate, epochs)


def create_kmeans(k: int = 3) -> KMeans:
    """创建 K-Means。"""
    return KMeans(k)


def _register_ml(builtins: dict) -> None:
    """注册 ML 内置函数。

    Matha f(a, b) 两侧均为柯里化单参应用 f(a)(b)，故注册形态为逐参
    lambda 链（与 ai_framework / data_science 同口径）；Python 侧默认
    参数在此显式化为必填参。
    """
    builtins["创建线性回归"] = lambda lr: lambda ep: create_linear_regression(lr, ep)
    builtins["创建逻辑回归"] = lambda lr: lambda ep: create_logistic_regression(lr, ep)
    builtins["创建KMeans"] = lambda k: create_kmeans(k)


def _ml_symtab_names() -> list[str]:
    return ["创建线性回归", "创建逻辑回归", "创建KMeans"]


__all__ = [
    "ModelType", "Metric", "ModelResult", "DatasetML",
    "LinearRegression", "LogisticRegression", "KMeans",
    "MathaML",
    "create_linear_regression", "create_logistic_regression",
    "create_kmeans",
    "_register_ml", "_ml_symtab_names",
]
