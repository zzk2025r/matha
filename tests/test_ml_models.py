# -*- coding: utf-8 -*-
"""src/ml.py 行为级门禁锁（阶段 1 · AI 修复）。

背景：`src/ml.py` 历史上两处病理——
  1. `LinearRegression.fit` / `LogisticRegression.fit` 向 `ModelResult` 传
     dataclass 不存在的 `bias` 字段，训练即 TypeError（实测复现）；
  2. `MathaML.create_model` 对 ModelType 宣称的 9 种算法中未实现的 6 种
     **静默回退线性回归**，`predict` 未创建返回 []、`evaluate` 未知指标
     返回假 0.0——同属「静默占位」病理。

本文件三类锁封死回退（口径仿 tests/test_ai_framework_numerics.py）：
  1. **闭式解对拍**：线性回归找回 y=2x+1、KMeans 质心/惯性手算值；
  2. **收敛闭环**：逻辑回归可分数据全对、损失随训练下降（证明 SGD 真接线）；
  3. **显式拒绝**：未实现模型/指标、空数据、形状不合、未创建即预测一律
     如实抛错——严禁静默回退/假值。

纪律：本锁背书的是三个已实现模型的行为语义；ModelType 其余 6 种仍属
未实现（显式拒绝即其当前口径），不背书任何「9 种算法齐全」主张。
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ml import (  # noqa: E402
    KMeans,
    LinearRegression,
    LogisticRegression,
    MathaML,
    ModelResult,
    ModelType,
)


# ============================================================
# 1. 线性回归：闭式解对拍 + bias 崩溃回归锁
# ============================================================

class TestLinearRegression:

    def test_recovers_closed_form_solution(self):
        """y = 2x + 1：SGD 找回闭式解（权重/偏置/损失三重对拍）。"""
        X = [[float(i)] for i in range(5)]
        y = [2.0 * i + 1.0 for i in range(5)]
        model = LinearRegression(learning_rate=0.01, epochs=300)
        result = model.fit(X, y)
        assert isinstance(result, ModelResult)
        assert abs(model.weights[0] - 2.0) < 0.01
        assert abs(model.bias - 1.0) < 0.01
        assert result.loss < 1e-4

    def test_fit_result_carries_bias(self):
        """回归锁：fit 曾因 ModelResult(bias=...) 字段不存在即 TypeError。"""
        model = LinearRegression(epochs=10)
        result = model.fit([[1.0], [2.0]], [3.0, 5.0])
        assert result.bias == model.bias
        assert result.model_type == ModelType.LINEAR_REGRESSION
        assert result.coefficients == {"w0": model.weights[0]}

    def test_loss_decreases_with_more_epochs(self):
        X = [[float(i)] for i in range(5)]
        y = [2.0 * i + 1.0 for i in range(5)]
        short = LinearRegression(learning_rate=0.01, epochs=1).fit(X, y)
        long = LinearRegression(learning_rate=0.01, epochs=300).fit(X, y)
        assert long.loss < short.loss

    def test_predict_matches_manual_formula(self):
        model = LinearRegression(learning_rate=0.01, epochs=300)
        model.fit([[0.0], [1.0], [2.0]], [1.0, 3.0, 5.0])
        for x, got in zip([[3.0], [4.0]], model.predict([[3.0], [4.0]])):
            assert got == pytest.approx(x[0] * model.weights[0] + model.bias)

    def test_empty_data_rejected(self):
        model = LinearRegression()
        with pytest.raises(ValueError):
            model.fit([], [])
        with pytest.raises(ValueError):
            model.fit([[1.0]], [])

    def test_length_mismatch_rejected(self):
        with pytest.raises(ValueError):
            LinearRegression().fit([[1.0], [2.0]], [1.0])


# ============================================================
# 2. 逻辑回归：收敛闭环
# ============================================================

class TestLogisticRegression:

    def test_separable_data_fully_classified(self):
        X = [[float(i)] for i in range(6)]
        y = [0, 0, 0, 1, 1, 1]
        model = LogisticRegression(learning_rate=0.1, epochs=500)
        result = model.fit(X, y)
        assert model.predict(X) == y
        assert result.loss < 0.01
        assert result.bias == model.bias

    def test_predict_threshold_is_real(self):
        """阈值参数真生效（非硬编码 0.5 透传）。"""
        model = LogisticRegression(learning_rate=0.1, epochs=300)
        model.fit([[0.0], [1.0], [2.0], [3.0]], [0, 0, 1, 1])
        X = [[0.0], [3.0]]
        assert model.predict(X, threshold=0.0) == [1, 1]
        assert model.predict(X, threshold=1.0) == [0, 0]

    def test_empty_data_rejected(self):
        with pytest.raises(ValueError):
            LogisticRegression().fit([], [])

    def test_length_mismatch_rejected(self):
        with pytest.raises(ValueError):
            LogisticRegression().fit([[1.0]], [0, 1])


# ============================================================
# 3. KMeans：质心/惯性手算对拍
# ============================================================

class TestKMeans:

    def test_two_clusters_hand_computed(self):
        """两簇分离数据：质心=簇均值、惯性=逐点偏差平方和（手算 0.08）。"""
        random.seed(42)
        X = [[0.0, 0.0], [0.1, -0.1], [-0.1, 0.1],
             [10.0, 10.0], [10.1, 9.9], [9.9, 10.1]]
        model = KMeans(k=2)
        result = model.fit(X)
        assert model.labels[:3] == [model.labels[0]] * 3
        assert model.labels[3:] == [model.labels[3]] * 3
        assert model.labels[0] != model.labels[3]
        near = [p for p, l in zip(X, model.labels) if l == model.labels[0]]
        mean = [sum(p[j] for p in near) / len(near) for j in range(2)]
        assert model.centroids[model.labels[0]] == pytest.approx(mean)
        assert result.loss == pytest.approx(0.08, abs=1e-9)
        assert model.predict([[0.05, 0.05]]) == [model.labels[0]]

    def test_empty_data_rejected(self):
        with pytest.raises(ValueError):
            KMeans(k=2).fit([])

    def test_k_less_than_one_rejected(self):
        with pytest.raises(ValueError):
            KMeans(k=0)

    def test_k_greater_than_samples_rejected(self):
        """回归锁：旧实现 k>n 时质心表越界 IndexError。"""
        with pytest.raises(ValueError):
            KMeans(k=5).fit([[0.0], [1.0]])


# ============================================================
# 4. MathaML 管理器：显式拒绝 + 端到端
# ============================================================

class TestMathaMLManager:

    @pytest.mark.parametrize("model_type,cls", [
        ("linear_regression", LinearRegression),
        ("logistic_regression", LogisticRegression),
        ("kmeans", KMeans),
    ])
    def test_implemented_types_create_correct_class(self, model_type, cls):
        assert isinstance(MathaML().create_model(model_type), cls)

    @pytest.mark.parametrize("model_type", [
        "decision_tree", "random_forest", "neural_network",
        "knn", "svm", "naive_bayes",
    ])
    def test_unimplemented_types_explicitly_rejected(self, model_type):
        """回归锁：旧实现静默回退 LinearRegression，拿假模型冒充成功。"""
        with pytest.raises(NotImplementedError) as excinfo:
            MathaML().create_model(model_type)
        assert model_type in str(excinfo.value)

    def test_unknown_type_rejected(self):
        with pytest.raises(ValueError):
            MathaML().create_model("nope")

    def test_train_predict_evaluate_e2e(self):
        ml = MathaML()
        ml.create_model("linear_regression", learning_rate=0.01, epochs=300)
        X = [[float(i)] for i in range(5)]
        y = [2.0 * i + 1.0 for i in range(5)]
        result = ml.train("linear_regression", X, y)
        assert result.loss < 1e-4
        preds = ml.predict("linear_regression", X)
        assert all(abs(p - t) < 0.05 for p, t in zip(preds, y))
        assert ml.evaluate("linear_regression", X, y, metric="mse") < 1e-4

    def test_train_autocreates_model(self):
        ml = MathaML()
        result = ml.train("linear_regression", [[1.0], [2.0]], [3.0, 5.0])
        assert isinstance(result, ModelResult)
        assert ml.get_stats()["models"] == 1

    def test_kmeans_via_manager_ignores_labels(self):
        """回归锁：KMeans.fit 只吃 X，管理器不得把 y 硬塞进去。"""
        random.seed(42)
        ml = MathaML()
        X = [[0.0], [0.1], [10.0], [10.1]]
        result = ml.train("kmeans", X, [])
        assert result.model_type == ModelType.KMEANS
        assert len(ml.predict("kmeans", X)) == 4

    def test_predict_before_create_rejected(self):
        """回归锁：旧实现静默返回 []。"""
        with pytest.raises(LookupError):
            MathaML().predict("knn", [[1.0]])

    def test_unsupported_metric_rejected(self):
        """回归锁：旧实现对未知指标返回假 0.0。"""
        ml = MathaML()
        ml.train("linear_regression", [[1.0], [2.0]], [3.0, 5.0])
        with pytest.raises(NotImplementedError):
            ml.evaluate("linear_regression", [[1.0]], [3.0], metric="f1_score")

    def test_evaluate_empty_rejected(self):
        ml = MathaML()
        ml.train("linear_regression", [[1.0], [2.0]], [3.0, 5.0])
        with pytest.raises(ValueError):
            ml.evaluate("linear_regression", [], [])

    def test_evaluate_accuracy_real(self):
        ml = MathaML()
        ml.create_model("logistic_regression", learning_rate=0.1, epochs=500)
        X = [[float(i)] for i in range(6)]
        y = [0, 0, 0, 1, 1, 1]
        ml.train("logistic_regression", X, y)
        assert ml.evaluate("logistic_regression", X, y, metric="accuracy") == 1.0