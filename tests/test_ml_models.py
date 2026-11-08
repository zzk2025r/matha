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

纪律：本锁背书线性/逻辑/KMeans 三模型与管理器的行为语义。

阶段 3 补锁（第 5–8 节）：未训练 predict/维度不合/构造期超参数/标签/
阈值显式拒绝，sigmoid 双向饱和不溢出，多特征闭式解与 k=1 手算闭环，
legacy registry 柯里化注册形态。

阶段 4 更新：ModelType 其余 6 种已纯标准库真实现（决策树/随机森林/
MLP/KNN/SVM/朴素贝叶斯），三锁见 tests/test_ml_models_phase4.py；
原「六类显式拒绝」回归锁随之改为 dispatch 正确类锁。
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ml import (  # noqa: E402
    DecisionTreeClassifier,
    GaussianNB,
    KMeans,
    KNN,
    LinearRegression,
    LinearSVM,
    LogisticRegression,
    MathaML,
    ModelResult,
    ModelType,
    NeuralNetworkMLP,
    RandomForestClassifier,
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

    @pytest.mark.parametrize("model_type,cls", [
        ("decision_tree", DecisionTreeClassifier),
        ("random_forest", RandomForestClassifier),
        ("neural_network", NeuralNetworkMLP),
        ("knn", KNN),
        ("svm", LinearSVM),
        ("naive_bayes", GaussianNB),
    ])
    def test_phase4_types_dispatch_correct_class(self, model_type, cls):
        """阶段 4：六种已真实现，dispatch 正确类（原显式拒绝锁随之收缩；
        行为三锁见 tests/test_ml_models_phase4.py）。"""
        assert isinstance(MathaML().create_model(model_type), cls)

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


# ============================================================
# 5. 阶段 3 · 未训练/维度边界显式拒绝
# ============================================================

class TestUntrainedPredictRejection:
    """回归锁：旧实现未训练 predict 静默返回偏置假值（线性/逻辑）或
    min([]) 裸抛（KMeans）；一律改为显式 ValueError。"""

    @pytest.mark.parametrize("factory", [
        LinearRegression, LogisticRegression, lambda: KMeans(k=2),
    ])
    def test_predict_before_fit_rejected(self, factory):
        model = factory()
        assert model.trained is False
        with pytest.raises(ValueError, match="未训练"):
            model.predict([[1.0]])

    @pytest.mark.parametrize("factory,fit", [
        (LinearRegression, lambda m: m.fit([[1.0], [2.0]], [3.0, 5.0])),
        (LogisticRegression, lambda m: m.fit([[0.0], [1.0]], [0, 1])),
        (lambda: KMeans(k=2), lambda m: m.fit([[0.0], [1.0]])),
    ])
    def test_trained_flag_lifecycle(self, factory, fit):
        model = factory()
        assert model.trained is False
        fit(model)
        assert model.trained is True

    def test_manager_predict_before_train_rejected(self):
        ml = MathaML()
        ml.create_model("linear_regression")
        with pytest.raises(ValueError, match="未训练"):
            ml.predict("linear_regression", [[1.0]])


class TestFeatureDimensionBoundary:

    @pytest.mark.parametrize("cls", [LinearRegression, LogisticRegression])
    def test_ragged_fit_rejected(self, cls):
        with pytest.raises(ValueError, match="维度不一致"):
            cls().fit([[1.0], [2.0, 3.0]], [0, 1])

    @pytest.mark.parametrize("cls", [LinearRegression, LogisticRegression])
    def test_empty_feature_fit_rejected(self, cls):
        with pytest.raises(ValueError, match="特征为空"):
            cls().fit([[]], [1.0])

    def test_kmeans_ragged_and_empty_rejected(self):
        with pytest.raises(ValueError, match="维度不一致"):
            KMeans(k=2).fit([[0.0], [1.0, 2.0]])
        with pytest.raises(ValueError, match="特征为空"):
            KMeans(k=1).fit([[]])

    @pytest.mark.parametrize("cls", [LinearRegression, LogisticRegression])
    def test_predict_wrong_width_rejected(self, cls):
        model = cls()
        model.fit([[1.0], [2.0]], [0, 1])
        with pytest.raises(ValueError, match="维度不一致"):
            model.predict([[1.0, 2.0]])
        assert model.predict([]) == []

    def test_kmeans_predict_wrong_width_rejected(self):
        model = KMeans(k=1)
        model.fit([[0.0, 0.0], [1.0, 1.0]])
        with pytest.raises(ValueError, match="维度不一致"):
            model.predict([[1.0]])
        assert model.predict([]) == []


# ============================================================
# 6. 阶段 3 · sigmoid 数值稳定（收敛闭环边界）
# ============================================================

class TestSigmoidSaturation:

    def test_extreme_values_saturate_without_overflow(self):
        """回归锁：旧实现 math.exp(-z) 在 z=-1000 时 OverflowError。"""
        lg = LogisticRegression()
        assert lg._sigmoid(1000) == 1.0
        assert lg._sigmoid(-1000) == 0.0
        assert lg._sigmoid(0) == 0.5

    @pytest.mark.parametrize("z", [1.0, 10.0, 100.0])
    def test_symmetry(self, z):
        lg = LogisticRegression()
        assert lg._sigmoid(z) + lg._sigmoid(-z) == pytest.approx(1.0)

    def test_monotone(self):
        lg = LogisticRegression()
        vals = [lg._sigmoid(z) for z in (-10.0, -1.0, 0.0, 1.0, 10.0)]
        assert vals == sorted(vals) and len(set(vals)) == 5

    def test_extreme_feature_fit_does_not_overflow(self):
        # 首轮更新后 w=5，次样本 z≈-5000：旧实现 exp(5000) 即崩
        model = LogisticRegression(learning_rate=0.01, epochs=5)
        model.fit([[1000.0], [-1000.0]], [1, 0])
        assert model.predict([[1000.0], [-1000.0]]) == [1, 0]


# ============================================================
# 7. 阶段 3 · 构造期超参数/标签/阈值显式拒绝
# ============================================================

class TestHyperparameterBoundary:

    @pytest.mark.parametrize("cls", [LinearRegression, LogisticRegression])
    @pytest.mark.parametrize("kwargs", [
        {"learning_rate": 0}, {"learning_rate": -0.1},
        {"learning_rate": float("nan")}, {"learning_rate": float("inf")},
        {"learning_rate": "x"}, {"learning_rate": True},
        {"epochs": 0}, {"epochs": -1}, {"epochs": 1.5},
        {"epochs": "10"}, {"epochs": True},
    ])
    def test_constructor_rejects(self, cls, kwargs):
        with pytest.raises(ValueError):
            cls(**kwargs)

    @pytest.mark.parametrize("kwargs", [
        {"k": 1.5}, {"k": True}, {"k": "2"},
        {"max_iters": 0}, {"max_iters": -1}, {"max_iters": 1.5},
    ])
    def test_kmeans_constructor_rejects(self, kwargs):
        """回归锁：旧实现 max_iters=0 时 fit 后 labels=[] → IndexError 裸抛。"""
        with pytest.raises(ValueError):
            KMeans(**kwargs)


class TestLogisticBoundary:

    @pytest.mark.parametrize("y", [[0, 2], ["0", "1"], [0, None]])
    def test_non_binary_labels_rejected(self, y):
        with pytest.raises(ValueError, match="0/1"):
            LogisticRegression().fit([[1.0], [2.0]], y)

    @pytest.mark.parametrize("threshold", [-0.1, 1.1, "x", None, True, float("nan")])
    def test_threshold_out_of_range_rejected(self, threshold):
        model = LogisticRegression()
        model.fit([[0.0], [1.0]], [0, 1])
        with pytest.raises(ValueError, match="阈值"):
            model.predict([[0.5]], threshold=threshold)


# ============================================================
# 8. 阶段 3 · 收敛闭环补强
# ============================================================

class TestPhase3Convergence:

    def test_multi_feature_closed_form(self):
        """y = 3*x1 - 2*x2 + 0.5：双特征 SGD 找回闭式解。"""
        X = [[float(i), float(j)] for i in range(4) for j in range(4)]
        y = [3.0 * a - 2.0 * b + 0.5 for a, b in X]
        model = LinearRegression(learning_rate=0.01, epochs=500)
        result = model.fit(X, y)
        assert model.weights[0] == pytest.approx(3.0, abs=1e-6)
        assert model.weights[1] == pytest.approx(-2.0, abs=1e-6)
        assert model.bias == pytest.approx(0.5, abs=1e-6)
        assert result.loss < 1e-10

    def test_logistic_loss_decreases_with_epochs(self):
        X = [[float(i)] for i in range(6)]
        y = [0, 0, 0, 1, 1, 1]
        short = LogisticRegression(learning_rate=0.1, epochs=1).fit(X, y)
        long = LogisticRegression(learning_rate=0.1, epochs=300).fit(X, y)
        assert long.loss < short.loss

    def test_kmeans_single_cluster_hand_computed(self):
        # k=1：质心必为全点均值 [2.0]，惯性 = 4+0+4 = 8（与种子无关）
        model = KMeans(k=1)
        result = model.fit([[0.0], [2.0], [4.0]])
        assert model.centroids == [[2.0]]
        assert model.labels == [0, 0, 0]
        assert result.loss == pytest.approx(8.0)
        assert model.predict([[100.0]]) == [0]


class TestEvaluateBoundary:

    def test_evaluate_length_mismatch_rejected(self):
        """回归锁：旧实现 zip 截断，静默按短边评估。"""
        ml = MathaML()
        ml.train("linear_regression", [[1.0], [2.0]], [3.0, 5.0])
        with pytest.raises(ValueError, match="不一致"):
            ml.evaluate("linear_regression", [[1.0]], [3.0, 5.0], metric="mse")


class TestRegistrationContract:
    """legacy registry  eager 路径的柯里化形态锁（ml 不在 manifest，
    符号面以 _ml_symtab_names 为准）。"""

    def test_symtab_names_match_registered(self):
        from src.ml import _ml_symtab_names, _register_ml
        b: dict = {}
        _register_ml(b)
        assert set(b) == set(_ml_symtab_names())

    def test_curried_forms(self):
        from src.ml import _register_ml
        b: dict = {}
        _register_ml(b)
        m = b["创建线性回归"](0.01)(300)
        assert isinstance(m, LinearRegression) and m.lr == 0.01 and m.epochs == 300
        m = b["创建逻辑回归"](0.1)(500)
        assert isinstance(m, LogisticRegression) and m.lr == 0.1 and m.epochs == 500
        m = b["创建KMeans"](2)
        assert isinstance(m, KMeans) and m.k == 2

    def test_partial_application_returns_callable(self):
        from src.ml import _register_ml
        b: dict = {}
        _register_ml(b)
        assert callable(b["创建线性回归"](0.01))