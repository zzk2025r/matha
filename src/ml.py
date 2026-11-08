"""Matha 机器学习：ModelType 九种算法全部真实现（纯标准库，无第三方依赖）。

行为级锁见 tests/test_ml_models.py（线性/逻辑/KMeans/管理器）与
tests/test_ml_models_phase4.py（阶段 4 新增六种：手算对拍/收敛闭环/显式拒绝）。

阶段 4 实现口径（各模型为明确变体，不冒充通用实现）：
  - DecisionTreeClassifier：CART 分类树，gini 全特征确定性最优分裂；
  - RandomForestClassifier：bootstrap + 可选每树特征子集（random subspace
    变体，非逐节点抽样），多数投票，random_state 固定即完全确定；
  - NeuralNetworkMLP：单隐藏层 tanh + sigmoid 输出二分类（标签 0/1），
    MSE + 逐样本 SGD；多分类/回归请用神经网络插件或线性/逻辑回归；
  - KNN：平方欧氏距离 k 近邻多数投票（惰性学习）；
  - LinearSVM：线性 hinge + L2 正则逐样本 SGD（标签 0/1，内部映射 ±1）；
  - GaussianNB：每类每特征均值/总体方差 + var_smoothing，log 后验 argmax。
分类模型平票一律取训练标签首见顺序（KNN 投票平票先取最近类），确定性可锁。

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


def _validate_positive_int(value: Any, name: str, minimum: int = 1) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} 须为 ≥ {minimum} 的整数：{value!r}")


def _validate_seed(value: Any) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"random_state 须为整数：{value!r}")


def _validate_labels(y: list[Any]) -> None:
    """分类标签：有限数值或字符串（可哈希、可计数），bool 显式拒绝。"""
    if any(isinstance(t, bool) or not isinstance(t, (int, float, str))
           or (isinstance(t, float) and not math.isfinite(t)) for t in y):
        raise ValueError("分类标签须为有限数值或字符串")


def _sigmoid(z: float) -> float:
    """Sigmoid（双向数值稳定：|z| 极大时饱和，不 exp 溢出）。"""
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    ez = math.exp(z)
    return ez / (1.0 + ez)


def _classification_result(model_type: ModelType, preds: list[Any],
                           y: list[Any], **kwargs: Any) -> ModelResult:
    """分类模型训练结果：accuracy/loss 为训练集真算读数。"""
    acc = sum(1 for p, t in zip(preds, y) if p == t) / len(y)
    return ModelResult(model_type=model_type, accuracy=acc,
                       loss=1.0 - acc, **kwargs)


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
        return _sigmoid(z)

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


@dataclass
class _TreeNode:
    """CART 树节点（feature=None 即叶，value 为多数类）。"""
    n_samples: int
    value: Any = None
    feature: int | None = None
    threshold: float | None = None
    left: _TreeNode | None = None
    right: _TreeNode | None = None


class DecisionTreeClassifier:
    """CART 分类树（gini 不纯度，全特征确定性最优分裂）。

    分裂取严格更优（同增益保留先见特征/低阈值）；无正增益即停。
    叶多数类平票取训练标签首见顺序。feature_importance 为加权 gini
    下降（按节点样本占比）归一化读数。
    """

    def __init__(self, max_depth: int = 5, min_samples_split: int = 2):
        _validate_positive_int(max_depth, "max_depth")
        _validate_positive_int(min_samples_split, "min_samples_split", minimum=2)
        self.max_depth = max_depth
        self.min_samples_split = min_samples_split
        self.root: _TreeNode | None = None
        self.n_features = 0
        self.feature_importance: dict[str, float] = {}
        self.trained = False

    def fit(self, X: list[list[float]], y: list[Any]) -> ModelResult:
        """训练。"""
        if not X or not y:
            raise ValueError("训练数据为空")
        if len(X) != len(y):
            raise ValueError(f"样本数与标签数不一致：{len(X)} ≠ {len(y)}")
        _validate_labels(y)
        self.n_features = _validate_matrix(X)
        self._n_total = len(y)
        self._importance = [0.0] * self.n_features
        self.root = self._build(X, y, depth=0)
        total = sum(self._importance)
        self.feature_importance = {
            f"f{j}": (self._importance[j] / total if total > 0 else 0.0)
            for j in range(self.n_features)
        }
        self.trained = True
        return _classification_result(ModelType.DECISION_TREE,
                                      self.predict(X), y,
                                      feature_importance=dict(self.feature_importance))

    def predict(self, X: list[list[float]]) -> list[Any]:
        """预测。未训练/维度不合显式拒绝。"""
        if not self.trained:
            raise ValueError("模型未训练，请先 fit")
        if any(len(row) != self.n_features for row in X):
            raise ValueError("样本特征维度不一致")
        return [self._predict_one(row, self.root) for row in X]

    def _predict_one(self, row: list[float], node: _TreeNode) -> Any:
        while node.feature is not None:
            node = (node.left if row[node.feature] <= node.threshold
                    else node.right)
        return node.value

    @staticmethod
    def _gini(y: list[Any]) -> float:
        n = len(y)
        counts: dict[Any, int] = {}
        for t in y:
            counts[t] = counts.get(t, 0) + 1
        return 1.0 - sum((c / n) ** 2 for c in counts.values())

    @staticmethod
    def _majority(y: list[Any]) -> Any:
        counts: dict[Any, int] = {}
        for t in y:
            counts[t] = counts.get(t, 0) + 1
        return max(counts, key=counts.get)

    def _build(self, X: list[list[float]], y: list[Any],
               depth: int) -> _TreeNode:
        node = _TreeNode(n_samples=len(y), value=self._majority(y))
        parent_gini = self._gini(y)
        if (depth >= self.max_depth or len(y) < self.min_samples_split
                or parent_gini == 0.0):
            return node
        best = None
        for j in range(self.n_features):
            values = sorted({row[j] for row in X})
            for a, b in zip(values, values[1:]):
                threshold = (a + b) / 2.0
                left_idx = [i for i, row in enumerate(X) if row[j] <= threshold]
                right_idx = [i for i, row in enumerate(X) if row[j] > threshold]
                if not left_idx or not right_idx:
                    continue
                gini = (len(left_idx) * self._gini([y[i] for i in left_idx])
                        + len(right_idx) * self._gini([y[i] for i in right_idx])
                        ) / len(y)
                if best is None or gini < best[0]:
                    best = (gini, j, threshold, left_idx, right_idx)
        if best is None or best[0] >= parent_gini - 1e-12:
            return node
        gini, j, threshold, left_idx, right_idx = best
        self._importance[j] += (len(y) / self._n_total) * max(
            0.0, parent_gini - gini)
        node.feature = j
        node.threshold = threshold
        node.value = None
        node.left = self._build([X[i] for i in left_idx],
                                [y[i] for i in left_idx], depth + 1)
        node.right = self._build([X[i] for i in right_idx],
                                 [y[i] for i in right_idx], depth + 1)
        return node


class RandomForestClassifier:
    """随机森林（bootstrap 重采样 + 可选每树特征子集，多数投票）。

    口径：random subspace 变体——每树独立 bootstrap 样本与固定特征
    子集（非逐节点特征抽样）；max_features=None 即纯 bagging。
    投票平票取训练标签首见顺序；random_state 固定时完全确定。
    """

    def __init__(self, n_trees: int = 10, max_depth: int = 5,
                 max_features: int | None = None, random_state: int = 42):
        _validate_positive_int(n_trees, "n_trees")
        _validate_positive_int(max_depth, "max_depth")
        if max_features is not None:
            _validate_positive_int(max_features, "max_features")
        _validate_seed(random_state)
        self.n_trees = n_trees
        self.max_depth = max_depth
        self.max_features = max_features
        self.random_state = random_state
        self.trees: list[tuple[DecisionTreeClassifier, list[int]]] = []
        self.n_features = 0
        self.trained = False

    def fit(self, X: list[list[float]], y: list[Any]) -> ModelResult:
        """训练。"""
        if not X or not y:
            raise ValueError("训练数据为空")
        if len(X) != len(y):
            raise ValueError(f"样本数与标签数不一致：{len(X)} ≠ {len(y)}")
        _validate_labels(y)
        self.n_features = _validate_matrix(X)
        if self.max_features is not None and self.max_features > self.n_features:
            raise ValueError(
                f"max_features {self.max_features} 超过特征数 {self.n_features}")
        n = len(X)
        rng = random.Random(self.random_state)
        self._class_order = list(dict.fromkeys(y))
        self.trees = []
        for _ in range(self.n_trees):
            idx = [rng.randrange(n) for _ in range(n)]
            feats = (list(range(self.n_features)) if self.max_features is None
                     else sorted(rng.sample(range(self.n_features),
                                            self.max_features)))
            tree = DecisionTreeClassifier(max_depth=self.max_depth)
            tree.fit([[X[i][j] for j in feats] for i in idx],
                     [y[i] for i in idx])
            self.trees.append((tree, feats))
        self.trained = True
        importance = [0.0] * self.n_features
        for tree, feats in self.trees:
            for j, f in enumerate(feats):
                importance[f] += tree.feature_importance[f"f{j}"] / self.n_trees
        return _classification_result(
            ModelType.RANDOM_FOREST, self.predict(X), y,
            feature_importance={f"f{j}": importance[j]
                                for j in range(self.n_features)})

    def predict(self, X: list[list[float]]) -> list[Any]:
        """预测（多数投票）。未训练/维度不合显式拒绝。"""
        if not self.trained:
            raise ValueError("模型未训练，请先 fit")
        if any(len(row) != self.n_features for row in X):
            raise ValueError("样本特征维度不一致")
        preds = []
        for row in X:
            counts: dict[Any, int] = {}
            for tree, feats in self.trees:
                label = tree.predict([[row[j] for j in feats]])[0]
                counts[label] = counts.get(label, 0) + 1
            preds.append(self._vote(counts))
        return preds

    def _vote(self, counts: dict[Any, int]) -> Any:
        best = None
        for label in self._class_order:
            c = counts.get(label, 0)
            if best is None or c > best[1]:
                best = (label, c)
        return best[0]


class NeuralNetworkMLP:
    """单隐藏层 MLP 二分类器（tanh 隐藏层 + sigmoid 输出，MSE + SGD）。

    标签限 0/1；权重以 random_state 播种均匀(-1,1)初始化，固定种子
    完全确定。多分类/回归不在本实现口径（用神经网络插件或线性/
    逻辑回归）。loss 为训练集概率 MSE 真算读数。
    """

    def __init__(self, hidden_size: int = 8, learning_rate: float = 0.1,
                 epochs: int = 1000, random_state: int = 42):
        _validate_positive_int(hidden_size, "hidden_size")
        _validate_train_params(learning_rate, epochs)
        _validate_seed(random_state)
        self.hidden_size = hidden_size
        self.lr = learning_rate
        self.epochs = epochs
        self.random_state = random_state
        self.w1: list[list[float]] = []
        self.b1: list[float] = []
        self.w2: list[float] = []
        self.b2 = 0.0
        self.n_features = 0
        self.trained = False

    def _forward(self, x: list[float]) -> tuple[list[float], float]:
        h = [math.tanh(sum(x[i] * self.w1[i][j]
                           for i in range(self.n_features)) + self.b1[j])
             for j in range(self.hidden_size)]
        z = sum(h[j] * self.w2[j]
                for j in range(self.hidden_size)) + self.b2
        return h, _sigmoid(z)

    def fit(self, X: list[list[float]], y: list[int]) -> ModelResult:
        """训练（逐样本反向传播）。"""
        if not X or not y:
            raise ValueError("训练数据为空")
        if len(X) != len(y):
            raise ValueError(f"样本数与标签数不一致：{len(X)} ≠ {len(y)}")
        if any(t not in (0, 1) for t in y):
            raise ValueError("MLP 标签须为 0/1")
        self.n_features = _validate_matrix(X)
        rng = random.Random(self.random_state)
        self.w1 = [[rng.uniform(-1, 1) for _ in range(self.hidden_size)]
                   for _ in range(self.n_features)]
        self.b1 = [rng.uniform(-1, 1) for _ in range(self.hidden_size)]
        self.w2 = [rng.uniform(-1, 1) for _ in range(self.hidden_size)]
        self.b2 = rng.uniform(-1, 1)
        for _ in range(self.epochs):
            for i in range(len(X)):
                h, o = self._forward(X[i])
                do = (o - y[i]) * o * (1.0 - o)
                dh = [do * self.w2[j] * (1.0 - h[j] * h[j])
                      for j in range(self.hidden_size)]
                for j in range(self.hidden_size):
                    self.w2[j] -= self.lr * do * h[j]
                    for i2 in range(self.n_features):
                        self.w1[i2][j] -= self.lr * dh[j] * X[i][i2]
                    self.b1[j] -= self.lr * dh[j]
                self.b2 -= self.lr * do
        self.trained = True
        loss = sum((self._forward(x)[1] - t) ** 2
                   for x, t in zip(X, y)) / len(y)
        return ModelResult(model_type=ModelType.NEURAL_NETWORK, loss=loss)

    def predict(self, X: list[list[float]],
                threshold: float = 0.5) -> list[int]:
        """预测。未训练/维度不合/阈值越界显式拒绝。"""
        if not self.trained:
            raise ValueError("模型未训练，请先 fit")
        if any(len(row) != self.n_features for row in X):
            raise ValueError("样本特征维度不一致")
        if (isinstance(threshold, bool) or not isinstance(threshold, (int, float))
                or not 0 <= threshold <= 1):
            raise ValueError(f"阈值须在 [0, 1] 内：{threshold!r}")
        return [1 if self._forward(x)[1] >= threshold else 0 for x in X]


class KNN:
    """K 近邻分类（平方欧氏距离，多数投票；惰性学习，fit 即存储）。

    距离平票按样本索引序取前 k；投票平票先取距查询点最近的类，
    仍平取训练标签首见顺序。
    """

    def __init__(self, k: int = 3):
        _validate_positive_int(k, "k")
        self.k = k
        self._X: list[list[float]] = []
        self._y: list[Any] = []
        self.n_features = 0
        self.trained = False

    def fit(self, X: list[list[float]], y: list[Any]) -> ModelResult:
        """训练（存储样本）。"""
        if not X or not y:
            raise ValueError("训练数据为空")
        if len(X) != len(y):
            raise ValueError(f"样本数与标签数不一致：{len(X)} ≠ {len(y)}")
        if len(X) < self.k:
            raise ValueError(f"样本数 {len(X)} 小于 k={self.k}")
        _validate_labels(y)
        self.n_features = _validate_matrix(X)
        self._X = [list(row) for row in X]
        self._y = list(y)
        self._class_order = list(dict.fromkeys(y))
        self.trained = True
        return _classification_result(ModelType.KNN, self.predict(X), y)

    def predict(self, X: list[list[float]]) -> list[Any]:
        """预测。未训练/维度不合显式拒绝。"""
        if not self.trained:
            raise ValueError("模型未训练，请先 fit")
        if any(len(row) != self.n_features for row in X):
            raise ValueError("样本特征维度不一致")
        preds = []
        for row in X:
            dists = [sum((row[j] - x[j]) ** 2
                         for j in range(self.n_features))
                     for x in self._X]
            order = sorted(range(len(dists)), key=lambda i: (dists[i], i))
            counts: dict[Any, int] = {}
            nearest: dict[Any, float] = {}
            for i in order[:self.k]:
                label = self._y[i]
                counts[label] = counts.get(label, 0) + 1
                nearest.setdefault(label, dists[i])
            best = None
            for label in self._class_order:
                if label not in counts:
                    continue
                key = (counts[label], -nearest[label])
                if best is None or key > best[0]:
                    best = (key, label)
            preds.append(best[1])
        return preds


class LinearSVM:
    """线性 SVM（hinge 损失 + L2 正则，逐样本 SGD）。

    标签限 0/1（内部映射 ±1）；判定面 w·x+b=0，predict 以 ≥0 判 1。
    loss = 平均 hinge + reg/2·||w||²（真算，可对拍）。
    """

    def __init__(self, learning_rate: float = 0.01, epochs: int = 100,
                 reg: float = 0.01):
        _validate_train_params(learning_rate, epochs)
        if (isinstance(reg, bool) or not isinstance(reg, (int, float))
                or reg < 0 or (isinstance(reg, float) and not math.isfinite(reg))):
            raise ValueError(f"reg 须为非负有限数值：{reg!r}")
        self.lr = learning_rate
        self.epochs = epochs
        self.reg = reg
        self.weights: list[float] = []
        self.bias = 0.0
        self.trained = False

    def fit(self, X: list[list[float]], y: list[int]) -> ModelResult:
        """训练。"""
        if not X or not y:
            raise ValueError("训练数据为空")
        if len(X) != len(y):
            raise ValueError(f"样本数与标签数不一致：{len(X)} ≠ {len(y)}")
        if any(t not in (0, 1) for t in y):
            raise ValueError("SVM 标签须为 0/1")
        n_features = _validate_matrix(X)
        self.weights = [0.0] * n_features
        self.bias = 0.0
        for _ in range(self.epochs):
            for i in range(len(X)):
                t = 1.0 if y[i] == 1 else -1.0
                f = sum(X[i][j] * self.weights[j]
                        for j in range(n_features)) + self.bias
                if t * f < 1.0:
                    for j in range(n_features):
                        self.weights[j] += self.lr * (
                            t * X[i][j] - self.reg * self.weights[j])
                    self.bias += self.lr * t
                else:
                    for j in range(n_features):
                        self.weights[j] *= (1.0 - self.lr * self.reg)
        self.trained = True
        loss = self._hinge_loss(X, y)
        return ModelResult(
            model_type=ModelType.SVM,
            loss=loss,
            coefficients={f"w{i}": self.weights[i]
                          for i in range(n_features)},
            bias=self.bias)

    def predict(self, X: list[list[float]]) -> list[int]:
        """预测。未训练/维度不合显式拒绝。"""
        if not self.trained:
            raise ValueError("模型未训练，请先 fit")
        if any(len(row) != len(self.weights) for row in X):
            raise ValueError("样本特征维度不一致")
        return [1 if sum(x[j] * self.weights[j]
                         for j in range(len(self.weights))) + self.bias >= 0.0
                else 0 for x in X]

    def _hinge_loss(self, X: list[list[float]], y: list[int]) -> float:
        total = 0.0
        for x, t01 in zip(X, y):
            t = 1.0 if t01 == 1 else -1.0
            f = sum(x[j] * self.weights[j]
                    for j in range(len(self.weights))) + self.bias
            total += max(0.0, 1.0 - t * f)
        return total / len(y) + self.reg / 2.0 * sum(
            w * w for w in self.weights)


class GaussianNB:
    """高斯朴素贝叶斯（每类每特征均值/总体方差，log 后验 argmax）。

    方差 = 总体方差(/n) + var_smoothing（正常数，防零方差除零）；
    类序取训练标签首见顺序，后验平票取首见类。
    """

    def __init__(self, var_smoothing: float = 1e-9):
        if (isinstance(var_smoothing, bool)
                or not isinstance(var_smoothing, (int, float))
                or var_smoothing <= 0
                or (isinstance(var_smoothing, float)
                    and not math.isfinite(var_smoothing))):
            raise ValueError(f"var_smoothing 须为正有限数值：{var_smoothing!r}")
        self.var_smoothing = var_smoothing
        self.classes: list[Any] = []
        self.priors: dict[Any, float] = {}
        self.means: dict[Any, list[float]] = {}
        self.variances: dict[Any, list[float]] = {}
        self.n_features = 0
        self.trained = False

    def fit(self, X: list[list[float]], y: list[Any]) -> ModelResult:
        """训练（逐类统计均值/方差）。"""
        if not X or not y:
            raise ValueError("训练数据为空")
        if len(X) != len(y):
            raise ValueError(f"样本数与标签数不一致：{len(X)} ≠ {len(y)}")
        _validate_labels(y)
        self.n_features = _validate_matrix(X)
        self.classes = list(dict.fromkeys(y))
        self.priors = {}
        self.means = {}
        self.variances = {}
        for c in self.classes:
            rows = [X[i] for i in range(len(X)) if y[i] == c]
            n_c = len(rows)
            self.priors[c] = n_c / len(X)
            means = [sum(r[j] for r in rows) / n_c
                     for j in range(self.n_features)]
            self.means[c] = means
            self.variances[c] = [
                sum((r[j] - means[j]) ** 2 for r in rows) / n_c
                + self.var_smoothing
                for j in range(self.n_features)]
        self.trained = True
        return _classification_result(ModelType.NAIVE_BAYES,
                                      self.predict(X), y)

    def predict(self, X: list[list[float]]) -> list[Any]:
        """预测。未训练/维度不合显式拒绝。"""
        if not self.trained:
            raise ValueError("模型未训练，请先 fit")
        if any(len(row) != self.n_features for row in X):
            raise ValueError("样本特征维度不一致")
        preds = []
        for x in X:
            best = None
            for c in self.classes:
                s = self._log_posterior(x, c)
                if best is None or s > best[0]:
                    best = (s, c)
            preds.append(best[1])
        return preds

    def _log_posterior(self, x: list[float], c: Any) -> float:
        score = math.log(self.priors[c])
        for j in range(self.n_features):
            var = self.variances[c][j]
            diff = x[j] - self.means[c][j]
            score += (-0.5 * math.log(2.0 * math.pi * var)
                      - diff * diff / (2.0 * var))
        return score


_MODEL_CLASSES: dict[ModelType, type] = {
    ModelType.LINEAR_REGRESSION: LinearRegression,
    ModelType.LOGISTIC_REGRESSION: LogisticRegression,
    ModelType.DECISION_TREE: DecisionTreeClassifier,
    ModelType.RANDOM_FOREST: RandomForestClassifier,
    ModelType.NEURAL_NETWORK: NeuralNetworkMLP,
    ModelType.KNN: KNN,
    ModelType.KMEANS: KMeans,
    ModelType.SVM: LinearSVM,
    ModelType.NAIVE_BAYES: GaussianNB,
}


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
        """创建模型。九种 ModelType 全部真实现；未知类型显式拒绝，
        绝不静默回退线性回归。"""
        mt = ModelType(model_type)
        cls = _MODEL_CLASSES.get(mt)
        if cls is None:
            raise NotImplementedError(f"模型类型 {model_type!r} 未实现")
        model = cls(**params)
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


def create_decision_tree(max_depth: int = 5,
                         min_samples_split: int = 2) -> DecisionTreeClassifier:
    """创建决策树。"""
    return DecisionTreeClassifier(max_depth, min_samples_split)


def create_random_forest(n_trees: int = 10, max_depth: int = 5,
                         max_features: int | None = None,
                         random_state: int = 42) -> RandomForestClassifier:
    """创建随机森林。"""
    return RandomForestClassifier(n_trees, max_depth, max_features, random_state)


def create_mlp(hidden_size: int = 8, learning_rate: float = 0.1,
               epochs: int = 1000, random_state: int = 42) -> NeuralNetworkMLP:
    """创建 MLP 二分类器。"""
    return NeuralNetworkMLP(hidden_size, learning_rate, epochs, random_state)


def create_knn(k: int = 3) -> KNN:
    """创建 KNN。"""
    return KNN(k)


def create_svm(learning_rate: float = 0.01, epochs: int = 100,
               reg: float = 0.01) -> LinearSVM:
    """创建线性 SVM。"""
    return LinearSVM(learning_rate, epochs, reg)


def create_gaussian_nb(var_smoothing: float = 1e-9) -> GaussianNB:
    """创建高斯朴素贝叶斯。"""
    return GaussianNB(var_smoothing)


def _register_ml(builtins: dict) -> None:
    """注册 ML 内置函数。

    Matha f(a, b) 两侧均为柯里化单参应用 f(a)(b)，故注册形态为逐参
    lambda 链（与 ai_framework / data_science 同口径）；Python 侧默认
    参数在此显式化为必填参。
    """
    builtins["创建线性回归"] = lambda lr: lambda ep: create_linear_regression(lr, ep)
    builtins["创建逻辑回归"] = lambda lr: lambda ep: create_logistic_regression(lr, ep)
    builtins["创建KMeans"] = lambda k: create_kmeans(k)
    builtins["创建决策树"] = lambda md: lambda mss: create_decision_tree(md, mss)
    builtins["创建随机森林"] = lambda nt: lambda md: lambda mf: lambda rs: create_random_forest(nt, md, mf, rs)
    builtins["创建MLP"] = lambda hs: lambda lr: lambda ep: lambda rs: create_mlp(hs, lr, ep, rs)
    builtins["创建KNN"] = lambda k: create_knn(k)
    builtins["创建SVM"] = lambda lr: lambda ep: lambda rg: create_svm(lr, ep, rg)
    builtins["创建朴素贝叶斯"] = lambda vs: create_gaussian_nb(vs)


def _ml_symtab_names() -> list[str]:
    return ["创建线性回归", "创建逻辑回归", "创建KMeans",
            "创建决策树", "创建随机森林", "创建MLP",
            "创建KNN", "创建SVM", "创建朴素贝叶斯"]


__all__ = [
    "ModelType", "Metric", "ModelResult", "DatasetML",
    "LinearRegression", "LogisticRegression", "KMeans",
    "DecisionTreeClassifier", "RandomForestClassifier", "NeuralNetworkMLP",
    "KNN", "LinearSVM", "GaussianNB",
    "MathaML",
    "create_linear_regression", "create_logistic_regression",
    "create_kmeans",
    "create_decision_tree", "create_random_forest", "create_mlp",
    "create_knn", "create_svm", "create_gaussian_nb",
    "_register_ml", "_ml_symtab_names",
]
