# -*- coding: utf-8 -*-
"""src/ml.py 阶段 4 补锁：ModelType 其余六种算法三锁。

阶段 4 前这六种（decision_tree/random_forest/neural_network/knn/svm/
naive_bayes）在 create_model 处显式拒绝（阶段 1-3 口径）；本轮全部
纯标准库真实现，拒绝面收缩为「未知类型字符串」。本文件三类锁：
  1. **手算对拍**：树 gini 分裂/特征重要性、森林投票决胜、KNN 近邻
     投票、SVM 判定面与 hinge 损失公式、NB 均值/方差/后验决胜、
     MLP 前向公式与损失读数；
  2. **收敛闭环**：可分数据全对、MLP XOR 学会（非线性真接线）、
     损失随训练下降、固定种子完全确定；
  3. **显式拒绝**：构造期超参数/标签/空数据/形状不合/未训练/维度/
     阈值矩阵，一律如实抛错，严禁静默占位。
另有管理器九类型 dispatch + e2e、legacy registry 柯里化注册形态锁。
"""
from __future__ import annotations

import math
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
    ModelType,
    NeuralNetworkMLP,
    RandomForestClassifier,
)


# ============================================================
# 1. 决策树：gini 分裂手算对拍 + 收敛闭环
# ============================================================

class TestDecisionTree:

    def test_perfect_split_hand_computed(self):
        """一维可分：根分裂阈值 1.5（手算），纯叶，重要性全归 f0。"""
        tree = DecisionTreeClassifier()
        result = tree.fit([[0.0], [1.0], [2.0], [3.0]], [0, 0, 1, 1])
        assert tree.root.feature == 0
        assert tree.root.threshold == 1.5
        assert tree.root.left.value == 0 and tree.root.right.value == 1
        assert tree.predict([[1.4], [1.6]]) == [0, 1]
        assert result.accuracy == 1.0 and result.loss == 0.0
        assert result.model_type == ModelType.DECISION_TREE
        assert tree.feature_importance == {"f0": 1.0}

    def test_constant_feature_gets_zero_importance(self):
        """f1 恒定无候选阈值：分裂必在 f0，重要性 f0=1/f1=0（手算）。"""
        tree = DecisionTreeClassifier()
        tree.fit([[0.0, 5.0], [1.0, 5.0], [2.0, 5.0], [3.0, 5.0]],
                 [0, 0, 1, 1])
        assert tree.root.feature == 0
        assert tree.feature_importance == {"f0": 1.0, "f1": 0.0}

    def test_majority_tie_first_seen(self):
        """恒定特征 impure 叶：多数类平票取首见标签（确定性锁）。"""
        tree = DecisionTreeClassifier()
        tree.fit([[0.0], [0.0]], [1, 0])
        assert tree.predict([[0.0]]) == [1]
        tree2 = DecisionTreeClassifier()
        tree2.fit([[0.0], [0.0]], [0, 1])
        assert tree2.predict([[0.0]]) == [0]

    def test_depth_closed_loop(self):
        """交替标签：单 stump 只能拿 0.75，足深树全对（深度真接线）。"""
        X = [[0.0], [1.0], [2.0], [3.0]]
        y = [0, 1, 0, 1]
        stump = DecisionTreeClassifier(max_depth=1)
        r1 = stump.fit(X, y)
        assert r1.accuracy == 0.75
        deep = DecisionTreeClassifier(max_depth=5)
        r2 = deep.fit(X, y)
        assert deep.predict(X) == y
        assert r2.accuracy == 1.0 and r2.loss == 0.0

    def test_xor_zero_gain_stops_honestly(self):
        """XOR 首分裂零增益：贪心 CART 如实停为叶（不硬造无增益分裂）。"""
        X = [[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0]]
        y = [0, 1, 1, 0]
        tree = DecisionTreeClassifier(max_depth=3)
        result = tree.fit(X, y)
        assert tree.root.feature is None
        assert result.accuracy == 0.5

    def test_min_samples_split_is_real(self):
        """交替标签：min_samples_split=4 阻止子节点再分（acc=0.75 手算）。"""
        X = [[0.0], [1.0], [2.0], [3.0]]
        y = [0, 1, 0, 1]
        restricted = DecisionTreeClassifier(min_samples_split=4)
        r1 = restricted.fit(X, y)
        assert r1.accuracy == 0.75
        full = DecisionTreeClassifier()
        r2 = full.fit(X, y)
        assert r2.accuracy == 1.0

    def test_string_labels(self):
        tree = DecisionTreeClassifier()
        tree.fit([[0.0], [1.0], [2.0], [3.0]], ["a", "a", "b", "b"])
        assert tree.predict([[0.5], [2.5]]) == ["a", "b"]


# ============================================================
# 2. 随机森林：bootstrap/投票/确定性
# ============================================================

class TestRandomForest:

    def test_separable_closed_loop(self):
        X = [[float(i)] for i in [0, 1, 2, 3, 10, 11, 12, 13]]
        y = [0] * 4 + [1] * 4
        rf = RandomForestClassifier(n_trees=5, random_state=7)
        result = rf.fit(X, y)
        assert rf.predict(X) == y
        assert result.accuracy == 1.0
        assert result.model_type == ModelType.RANDOM_FOREST

    def test_trees_are_real_bootstrap_trees(self):
        rf = RandomForestClassifier(n_trees=4, random_state=1)
        rf.fit([[0.0], [1.0], [2.0], [3.0]], [0, 0, 1, 1])
        assert len(rf.trees) == 4
        assert all(isinstance(t, DecisionTreeClassifier) and t.trained
                   for t, _ in rf.trees)

    def test_same_seed_fully_deterministic(self):
        X = [[float(i), float(i % 3)] for i in range(8)]
        y = [0, 0, 0, 0, 1, 1, 1, 1]
        a = RandomForestClassifier(n_trees=6, random_state=9).fit(X, y)
        b = RandomForestClassifier(n_trees=6, random_state=9).fit(X, y)
        assert a.feature_importance == b.feature_importance

    def test_vote_tie_first_seen(self):
        rf = RandomForestClassifier()
        rf._class_order = [0, 1]
        assert rf._vote({0: 2, 1: 2}) == 0
        assert rf._vote({0: 1, 1: 3}) == 1
        rf._class_order = [1, 0]
        assert rf._vote({0: 2, 1: 2}) == 1

    def test_max_features_subspace_is_real(self):
        """max_features=1：每树只见 1 个特征（random subspace 真接线）。"""
        rf = RandomForestClassifier(n_trees=3, max_features=1, random_state=7)
        rf.fit([[0.0, 1.0], [1.0, 2.0], [2.0, 3.0], [3.0, 4.0]],
               [0, 0, 1, 1])
        for tree, feats in rf.trees:
            assert len(feats) == 1 and feats[0] in (0, 1)
            assert tree.n_features == 1

    def test_max_features_exceeding_width_rejected(self):
        rf = RandomForestClassifier(max_features=3)
        with pytest.raises(ValueError, match="超过特征数"):
            rf.fit([[0.0, 1.0], [1.0, 2.0]], [0, 1])


# ============================================================
# 3. MLP：前向手算对拍 + XOR 收敛闭环
# ============================================================

class TestNeuralNetworkMLP:

    def test_forward_matches_manual_formula(self):
        """手设权重：h=tanh(1)、o=sigmoid(tanh(1))，前向逐层真算。"""
        m = NeuralNetworkMLP(hidden_size=1)
        m.n_features = 1
        m.w1 = [[1.0]]
        m.b1 = [0.0]
        m.w2 = [1.0]
        m.b2 = 0.0
        m.trained = True
        h, o = m._forward([1.0])
        assert h[0] == pytest.approx(math.tanh(1.0))
        assert o == pytest.approx(1.0 / (1.0 + math.exp(-math.tanh(1.0))))
        assert m.predict([[1.0]]) == [1]
        assert m.predict([[1.0]], threshold=0.9) == [0]

    def test_zero_input_exact_half(self):
        """x=0、零偏置：h=0、o=0.5 精确值，阈值边界 ≥ 判 1。"""
        m = NeuralNetworkMLP(hidden_size=2)
        m.n_features = 1
        m.w1 = [[1.0, 1.0]]
        m.b1 = [0.0, 0.0]
        m.w2 = [1.0, 1.0]
        m.b2 = 0.0
        m.trained = True
        assert m._forward([0.0]) == ([0.0, 0.0], 0.5)
        assert m.predict([[0.0]]) == [1]
        assert m.predict([[0.0]], threshold=0.5001) == [0]

    def test_xor_converges(self):
        """XOR 非线性可分：SGD 反向传播真接线（线性模型不可能全对）。"""
        X = [[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0]]
        y = [0, 1, 1, 0]
        m = NeuralNetworkMLP(hidden_size=4, learning_rate=0.5,
                             epochs=3000, random_state=42)
        result = m.fit(X, y)
        assert m.predict(X) == y
        assert result.loss < 0.01
        assert result.model_type == ModelType.NEURAL_NETWORK

    def test_loss_is_real_reading(self):
        """result.loss == 末权重前向概率 MSE（手算对拍，非假 0）。"""
        X = [[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0]]
        y = [0, 1, 1, 0]
        m = NeuralNetworkMLP(hidden_size=4, learning_rate=0.5,
                             epochs=200, random_state=42)
        result = m.fit(X, y)
        manual = sum((m._forward(x)[1] - t) ** 2
                     for x, t in zip(X, y)) / len(y)
        assert result.loss == pytest.approx(manual, abs=1e-12)

    def test_loss_decreases_with_epochs(self):
        X = [[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0]]
        y = [0, 1, 1, 0]
        short = NeuralNetworkMLP(hidden_size=4, learning_rate=0.5,
                                 epochs=10, random_state=42).fit(X, y)
        long = NeuralNetworkMLP(hidden_size=4, learning_rate=0.5,
                                epochs=3000, random_state=42).fit(X, y)
        assert long.loss < short.loss

    def test_same_seed_same_weights(self):
        X = [[0.0], [1.0]]
        y = [0, 1]
        a = NeuralNetworkMLP(hidden_size=3, epochs=5, random_state=5)
        b = NeuralNetworkMLP(hidden_size=3, epochs=5, random_state=5)
        a.fit(X, y)
        b.fit(X, y)
        assert a.w1 == b.w1 and a.b1 == b.b1
        assert a.w2 == b.w2 and a.b2 == b.b2


# ============================================================
# 4. KNN：近邻投票手算对拍
# ============================================================

class TestKNN:

    def test_k1_nearest_hand_computed(self):
        m = KNN(k=1)
        m.fit([[0.0], [1.0], [10.0]], [0, 0, 1])
        assert m.predict([[0.4], [9.0]]) == [0, 1]

    def test_k3_vote_hand_computed(self):
        """[1.5] 前三近邻 0/1/2 → 3:0 判 0；[9] 前三近邻 10/11/2 → 2:1 判 1。"""
        m = KNN(k=3)
        result = m.fit([[0.0], [1.0], [2.0], [10.0], [11.0]],
                       [0, 0, 0, 1, 1])
        assert m.predict([[1.5], [9.0]]) == [0, 1]
        assert result.model_type == ModelType.KNN
        assert result.accuracy == 1.0

    def test_vote_tie_nearest_class_wins(self):
        """[0.9] 两近邻 1(距0.01)/0(距0.81)：票 1:1，最近类 1 胜（手算）。"""
        m = KNN(k=2)
        m.fit([[0.0], [1.0], [3.0]], [0, 1, 1])
        assert m.predict([[0.9]]) == [1]

    def test_full_tie_first_seen(self):
        """[1] 距两类等距等票：取首见类 0；换标签序则取 1。"""
        m = KNN(k=2)
        m.fit([[0.0], [2.0]], [0, 1])
        assert m.predict([[1.0]]) == [0]
        m2 = KNN(k=2)
        m2.fit([[0.0], [2.0]], [1, 0])
        assert m2.predict([[1.0]]) == [1]

    def test_k_greater_than_samples_rejected(self):
        with pytest.raises(ValueError, match="小于 k"):
            KNN(k=5).fit([[0.0], [1.0]], [0, 1])


# ============================================================
# 5. 线性 SVM：判定面/hinge 损失手算对拍 + 收敛闭环
# ============================================================

class TestLinearSVM:

    def test_decision_boundary_manual(self):
        """手设 w=1,b=-1.5：f=x-1.5，≥0 判 1（边界 f=0 判 1）。"""
        s = LinearSVM()
        s.weights = [1.0]
        s.bias = -1.5
        s.trained = True
        assert s.predict([[1.0], [1.5], [2.0]]) == [0, 1, 1]

    def test_separable_closed_loop(self):
        X = [[float(i)] for i in range(6)]
        y = [0, 0, 0, 1, 1, 1]
        s = LinearSVM(learning_rate=0.1, epochs=200)
        result = s.fit(X, y)
        assert s.predict(X) == y
        assert result.model_type == ModelType.SVM
        assert result.bias == s.bias
        assert result.coefficients == {"w0": s.weights[0]}

    def test_hinge_loss_manual_parity(self):
        """loss == 平均 hinge + reg/2·||w||²（末权重手算，真读数）。"""
        X = [[float(i)] for i in range(6)]
        y = [0, 0, 0, 1, 1, 1]
        s = LinearSVM(learning_rate=0.1, epochs=50, reg=0.05)
        result = s.fit(X, y)
        hinge = sum(max(0.0, 1.0 - (1.0 if t else -1.0)
                        * (x[0] * s.weights[0] + s.bias))
                    for x, t in zip(X, y)) / len(y)
        expected = hinge + 0.05 / 2.0 * s.weights[0] ** 2
        assert result.loss == pytest.approx(expected, abs=1e-12)

    def test_loss_decreases_with_epochs(self):
        X = [[float(i)] for i in range(6)]
        y = [0, 0, 0, 1, 1, 1]
        short = LinearSVM(learning_rate=0.1, epochs=1).fit(X, y)
        long = LinearSVM(learning_rate=0.1, epochs=200).fit(X, y)
        assert long.loss < short.loss

    def test_zero_reg_allowed(self):
        """reg=0：损失退化为纯平均 hinge（手算对拍）。"""
        X = [[0.0], [3.0]]
        y = [0, 1]
        s = LinearSVM(learning_rate=0.1, epochs=20, reg=0)
        result = s.fit(X, y)
        hinge = sum(max(0.0, 1.0 - (1.0 if t else -1.0)
                        * (x[0] * s.weights[0] + s.bias))
                    for x, t in zip(X, y)) / len(y)
        assert result.loss == pytest.approx(hinge, abs=1e-12)


# ============================================================
# 6. 高斯朴素贝叶斯：统计量/后验手算对拍
# ============================================================

class TestGaussianNB:

    def test_stats_hand_computed(self):
        """类0均值1/类1均值11，总体方差 2/3，加 var_smoothing=1（手算）。"""
        nb = GaussianNB(var_smoothing=1.0)
        X = [[0.0], [1.0], [2.0], [10.0], [11.0], [12.0]]
        y = [0, 0, 0, 1, 1, 1]
        result = nb.fit(X, y)
        assert nb.classes == [0, 1]
        assert nb.priors == {0: 0.5, 1: 0.5}
        assert nb.means == {0: [1.0], 1: [11.0]}
        assert nb.variances[0][0] == pytest.approx(2.0 / 3.0 + 1.0)
        assert nb.variances[1][0] == pytest.approx(2.0 / 3.0 + 1.0)
        assert result.model_type == ModelType.NAIVE_BAYES
        assert result.accuracy == 1.0

    def test_predict_hand_computed(self):
        nb = GaussianNB(var_smoothing=1.0)
        nb.fit([[0.0], [1.0], [2.0], [10.0], [11.0], [12.0]],
               [0, 0, 0, 1, 1, 1])
        assert nb.predict([[0.5], [10.5]]) == [0, 1]

    def test_posterior_tie_first_seen(self):
        """x=6 距两均值等距、先验相等：后验平票取首见类。"""
        X = [[0.0], [1.0], [2.0], [10.0], [11.0], [12.0]]
        nb = GaussianNB(var_smoothing=1.0)
        nb.fit(X, [0, 0, 0, 1, 1, 1])
        assert nb.predict([[6.0]]) == [0]
        nb2 = GaussianNB(var_smoothing=1.0)
        nb2.fit(X, [1, 1, 1, 0, 0, 0])
        assert nb2.predict([[6.0]]) == [1]

    def test_zero_variance_smoothed(self):
        """单样本类方差 0：var_smoothing 防除零，预测仍真算。"""
        nb = GaussianNB()
        nb.fit([[0.0], [0.0], [5.0]], [0, 0, 1])
        assert nb.variances[1][0] == 1e-9
        assert nb.predict([[5.0], [0.0]]) == [1, 0]

    def test_string_labels(self):
        nb = GaussianNB()
        nb.fit([[0.0], [1.0], [10.0], [11.0]], ["a", "a", "b", "b"])
        assert nb.predict([[0.5], [10.5]]) == ["a", "b"]


# ============================================================
# 7. 显式拒绝矩阵（六模型统一边界）
# ============================================================

_FACTORIES = [
    DecisionTreeClassifier,
    lambda: RandomForestClassifier(n_trees=2),
    lambda: NeuralNetworkMLP(epochs=5),
    lambda: KNN(k=1),
    lambda: LinearSVM(epochs=5),
    GaussianNB,
]


class TestPhase4RejectionMatrix:

    @pytest.mark.parametrize("factory", _FACTORIES)
    def test_predict_before_fit_rejected(self, factory):
        model = factory()
        assert model.trained is False
        with pytest.raises(ValueError, match="未训练"):
            model.predict([[1.0]])

    @pytest.mark.parametrize("factory", _FACTORIES)
    def test_empty_fit_rejected(self, factory):
        with pytest.raises(ValueError, match="训练数据为空"):
            factory().fit([], [])

    @pytest.mark.parametrize("factory", _FACTORIES)
    def test_length_mismatch_rejected(self, factory):
        with pytest.raises(ValueError, match="不一致"):
            factory().fit([[1.0], [2.0]], [0])

    @pytest.mark.parametrize("factory", _FACTORIES)
    def test_ragged_fit_rejected(self, factory):
        with pytest.raises(ValueError, match="维度不一致"):
            factory().fit([[1.0], [2.0, 3.0]], [0, 1])

    @pytest.mark.parametrize("factory", _FACTORIES)
    def test_empty_feature_fit_rejected(self, factory):
        with pytest.raises(ValueError, match="特征为空"):
            factory().fit([[]], [0])

    @pytest.mark.parametrize("factory", _FACTORIES)
    def test_predict_wrong_width_rejected(self, factory):
        model = factory()
        model.fit([[1.0], [2.0]], [0, 1])
        with pytest.raises(ValueError, match="维度不一致"):
            model.predict([[1.0, 2.0]])
        assert model.predict([]) == []

    @pytest.mark.parametrize("factory", [_FACTORIES[0], _FACTORIES[1],
                                         _FACTORIES[3], _FACTORIES[5]])
    @pytest.mark.parametrize("y", [[0, None], [True, False],
                                   [0, float("nan")], [0, [1]]])
    def test_bad_labels_rejected(self, factory, y):
        with pytest.raises(ValueError, match="标签"):
            factory().fit([[1.0], [2.0]], y)

    @pytest.mark.parametrize("factory", [_FACTORIES[2], _FACTORIES[4]])
    @pytest.mark.parametrize("y", [[0, 2], ["0", "1"]])
    def test_non_binary_labels_rejected(self, factory, y):
        with pytest.raises(ValueError, match="0/1"):
            factory().fit([[1.0], [2.0]], y)


class TestPhase4ConstructorRejection:

    @pytest.mark.parametrize("kwargs", [
        {"max_depth": 0}, {"max_depth": -1}, {"max_depth": 1.5},
        {"max_depth": True}, {"max_depth": "x"},
        {"min_samples_split": 1}, {"min_samples_split": 0},
        {"min_samples_split": True}, {"min_samples_split": 2.5},
    ])
    def test_decision_tree_rejects(self, kwargs):
        with pytest.raises(ValueError):
            DecisionTreeClassifier(**kwargs)

    @pytest.mark.parametrize("kwargs", [
        {"n_trees": 0}, {"n_trees": True}, {"n_trees": 1.5},
        {"max_depth": 0}, {"max_features": 0}, {"max_features": -1},
        {"max_features": 1.5}, {"max_features": True},
        {"random_state": True}, {"random_state": "x"},
        {"random_state": 1.5},
    ])
    def test_random_forest_rejects(self, kwargs):
        with pytest.raises(ValueError):
            RandomForestClassifier(**kwargs)

    @pytest.mark.parametrize("kwargs", [
        {"hidden_size": 0}, {"hidden_size": 1.5}, {"hidden_size": True},
        {"learning_rate": 0}, {"learning_rate": float("nan")},
        {"epochs": 0}, {"epochs": True},
        {"random_state": "x"}, {"random_state": True},
    ])
    def test_mlp_rejects(self, kwargs):
        with pytest.raises(ValueError):
            NeuralNetworkMLP(**kwargs)

    @pytest.mark.parametrize("kwargs", [
        {"k": 0}, {"k": -1}, {"k": 1.5}, {"k": True}, {"k": "2"},
    ])
    def test_knn_rejects(self, kwargs):
        with pytest.raises(ValueError):
            KNN(**kwargs)

    @pytest.mark.parametrize("kwargs", [
        {"learning_rate": 0}, {"epochs": 0},
        {"reg": -0.1}, {"reg": float("nan")}, {"reg": float("inf")},
        {"reg": True}, {"reg": "x"},
    ])
    def test_svm_rejects(self, kwargs):
        with pytest.raises(ValueError):
            LinearSVM(**kwargs)

    @pytest.mark.parametrize("var_smoothing", [
        0, -1.0, float("nan"), float("inf"), True, "x",
    ])
    def test_naive_bayes_rejects(self, var_smoothing):
        with pytest.raises(ValueError):
            GaussianNB(var_smoothing=var_smoothing)

    @pytest.mark.parametrize("threshold", [-0.1, 1.1, "x", True])
    def test_mlp_threshold_rejected(self, threshold):
        m = NeuralNetworkMLP(epochs=5)
        m.fit([[0.0], [1.0]], [0, 1])
        with pytest.raises(ValueError, match="阈值"):
            m.predict([[0.5]], threshold=threshold)


# ============================================================
# 8. 管理器：九类型 dispatch + e2e
# ============================================================

class TestManagerNineTypes:

    @pytest.mark.parametrize("model_type,cls", [
        ("linear_regression", LinearRegression),
        ("logistic_regression", LogisticRegression),
        ("kmeans", KMeans),
        ("decision_tree", DecisionTreeClassifier),
        ("random_forest", RandomForestClassifier),
        ("neural_network", NeuralNetworkMLP),
        ("knn", KNN),
        ("svm", LinearSVM),
        ("naive_bayes", GaussianNB),
    ])
    def test_all_nine_types_dispatch(self, model_type, cls):
        assert isinstance(MathaML().create_model(model_type), cls)

    @pytest.mark.parametrize("model_type,params", [
        ("decision_tree", {}),
        ("random_forest", {"n_trees": 5}),
        ("neural_network", {"hidden_size": 4, "learning_rate": 0.5,
                            "epochs": 1000}),
        ("knn", {"k": 1}),
        ("svm", {"learning_rate": 0.1, "epochs": 200}),
        ("naive_bayes", {}),
    ])
    def test_manager_e2e_accuracy(self, model_type, params):
        """train→predict→evaluate 全链：可分数据 accuracy=1.0（真算）。"""
        ml = MathaML()
        ml.create_model(model_type, **params)
        X = [[float(i)] for i in range(6)]
        y = [0, 0, 0, 1, 1, 1]
        ml.train(model_type, X, y)
        assert ml.predict(model_type, X) == y
        assert ml.evaluate(model_type, X, y, metric="accuracy") == 1.0

    def test_unknown_type_still_rejected(self):
        with pytest.raises(ValueError):
            MathaML().create_model("nope")


# ============================================================
# 9. 注册契约：柯里化形态（legacy registry 通道）
# ============================================================

class TestPhase4Registration:

    def test_symtab_names_match_registered(self):
        from src.ml import _ml_symtab_names, _register_ml
        b: dict = {}
        _register_ml(b)
        assert set(b) == set(_ml_symtab_names())
        assert len(_ml_symtab_names()) == 9

    def test_curried_forms(self):
        from src.ml import _register_ml
        b: dict = {}
        _register_ml(b)
        m = b["创建决策树"](3)(4)
        assert isinstance(m, DecisionTreeClassifier)
        assert m.max_depth == 3 and m.min_samples_split == 4
        m = b["创建随机森林"](5)(3)(2)(7)
        assert isinstance(m, RandomForestClassifier)
        assert (m.n_trees, m.max_depth, m.max_features, m.random_state) == (5, 3, 2, 7)
        m = b["创建MLP"](4)(0.5)(100)(7)
        assert isinstance(m, NeuralNetworkMLP)
        assert (m.hidden_size, m.lr, m.epochs, m.random_state) == (4, 0.5, 100, 7)
        m = b["创建KNN"](2)
        assert isinstance(m, KNN) and m.k == 2
        m = b["创建SVM"](0.1)(200)(0.05)
        assert isinstance(m, LinearSVM)
        assert (m.lr, m.epochs, m.reg) == (0.1, 200, 0.05)
        m = b["创建朴素贝叶斯"](1e-6)
        assert isinstance(m, GaussianNB) and m.var_smoothing == 1e-6

    def test_partial_application_returns_callable(self):
        from src.ml import _register_ml
        b: dict = {}
        _register_ml(b)
        assert callable(b["创建决策树"](3))
        assert callable(b["创建随机森林"](5))
        assert callable(b["创建随机森林"](5)(3))
        assert callable(b["创建随机森林"](5)(3)(2))
        assert callable(b["创建MLP"](4))
        assert callable(b["创建MLP"](4)(0.5))
        assert callable(b["创建MLP"](4)(0.5)(100))
        assert callable(b["创建SVM"](0.1))
        assert callable(b["创建SVM"](0.1)(200))