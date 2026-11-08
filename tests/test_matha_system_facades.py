# -*- coding: utf-8 -*-
"""MathaSystem AI/ML/数据门面修复锁（阶段 5）。

背景（docs/KNOWN_ISSUES.md 阶段 1 余项登记「未修」，本轮清除）：
  - create_convnet/create_rnn 返回假 dict；
  - create_neural_network 真接路径 kwargs 与 NeuralNetwork(config) 签名不合
    （必 TypeError），模块缺席时回退假 dict；
  - load_csv 恒 True、normalize_data 透传；
  - train_model 无 fit 时回退假 dict；
  - _init_ml 从未被调用（create_ml_manager 等四方法 AttributeError 死接线），
    模块缺席时回退假 dict；create_data_science 同形。
本文件锁：真接路径真算（手算对拍/闭环/与插件及已背书实现对拍）、
缺席与误用一律显式拒绝（不再产出任何假 dict）。
用 __new__ 轻量构造 + 注入真实类（同 test_matha_system_ai_wiring 口径）。
"""
from __future__ import annotations

import copy
import inspect
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.matha_system import MathaSystem  # noqa: E402
from src.domains.neural_network import (  # noqa: E402
    ModelConfig, NeuralNetwork, create_neural_network as plugin_create_nn)
from src.domains.data_science import (  # noqa: E402
    DataScienceManager, Dataset)
from src.ml import (  # noqa: E402
    KMeans, LinearRegression, LogisticRegression, MathaML, ModelResult)


def _bare_system() -> MathaSystem:
    s = MathaSystem.__new__(MathaSystem)
    s.neural_network_class = NeuralNetwork
    s.data_science_class = DataScienceManager
    s.ml_class = MathaML
    s.linear_regression_class = LinearRegression
    s.logistic_regression_class = LogisticRegression
    s.kmeans_class = KMeans
    s.dataset = None
    return s


def _csv(tmp_path: Path, text: str) -> str:
    p = tmp_path / "data.csv"
    p.write_text(text, encoding="utf-8")
    return str(p)


# ============================================================
# 1. create_neural_network：真接修复（原 kwargs 必崩）+ 缺席拒绝
# ============================================================

class TestCreateNeuralNetwork:

    def test_real_path_returns_real_network(self):
        nn = _bare_system().create_neural_network(2, 4)
        assert isinstance(nn, NeuralNetwork)
        assert nn.config.layers == 2 and nn.config.hidden_size == 4

    def test_real_path_matches_plugin_factory(self):
        facade = _bare_system().create_neural_network(3, 16)
        plugin = plugin_create_nn(3, 16)
        assert type(facade) is type(plugin)
        assert facade.config == plugin.config

    def test_injected_class_receives_modelconfig(self):
        seen = []

        class FakeNN:
            def __init__(self, config):
                seen.append(config)

        s = _bare_system()
        s.neural_network_class = FakeNN
        s.create_neural_network(5, 32)
        assert isinstance(seen[0], ModelConfig)
        assert seen[0].layers == 5 and seen[0].hidden_size == 32

    def test_closed_loop_forward_and_train(self):
        nn = _bare_system().create_neural_network(2, 4)
        nn.add_layer(2, 4, "sigmoid")
        nn.add_layer(4, 1, "sigmoid")
        out = nn.forward([0.0, 1.0])
        assert len(out) == 1 and 0.0 < out[0] < 1.0
        result = nn.train([[0.0, 0.0], [1.0, 1.0]], [[0.0], [1.0]])
        assert result.epochs_trained > 0
        assert result.final_loss == result.loss_history[-1]
        assert result.final_loss <= result.loss_history[0]

    def test_absent_module_rejects(self):
        s = _bare_system()
        s.neural_network_class = None
        with pytest.raises(RuntimeError, match="神经网络"):
            s.create_neural_network()


# ============================================================
# 2. create_convnet/create_rnn：无背书实现，显式拒绝（原假 dict）
# ============================================================

class TestConvnetRnnRejection:

    def test_convnet_rejects(self):
        with pytest.raises(NotImplementedError, match="CNN"):
            _bare_system().create_convnet()

    def test_rnn_rejects(self):
        with pytest.raises(NotImplementedError, match="RNN"):
            _bare_system().create_rnn()

    def test_rejects_even_with_classes_present(self):
        s = _bare_system()  # 注入真实类也不改变拒绝口径
        with pytest.raises(NotImplementedError):
            s.create_convnet()
        with pytest.raises(NotImplementedError):
            s.create_rnn()


# ============================================================
# 3. load_csv：真读真校验 + 数据集留置（原恒 True）
# ============================================================

class TestLoadCsv:

    def test_real_load_and_retention(self, tmp_path):
        s = _bare_system()
        assert s.load_csv(_csv(tmp_path, "1,10\n2,20\n3,30\n")) is True
        assert s.dataset._data == [[1.0, 10.0], [2.0, 20.0], [3.0, 30.0]]
        assert s.dataset.samples == 3 and s.dataset.features == 2

    def test_missing_file_raises_and_keeps_dataset(self, tmp_path):
        s = _bare_system()
        s.load_csv(_csv(tmp_path, "1,10\n2,20\n"))
        before = s.dataset
        with pytest.raises(FileNotFoundError):
            s.load_csv(str(tmp_path / "nope.csv"))
        assert s.dataset is before  # 失败不换数据集

    def test_bad_cell_raises(self, tmp_path):
        s = _bare_system()
        with pytest.raises(ValueError, match="非数值"):
            s.load_csv(_csv(tmp_path, "1,cat\n2,3\n"))
        assert s.dataset is None

    def test_ragged_raises(self, tmp_path):
        s = _bare_system()
        with pytest.raises(ValueError, match="宽度"):
            s.load_csv(_csv(tmp_path, "1,2\n3\n"))

    def test_empty_raises(self, tmp_path):
        s = _bare_system()
        with pytest.raises(ValueError, match="为空"):
            s.load_csv(_csv(tmp_path, ""))


# ============================================================
# 4. normalize_data：真 min-max（原透传），契约同 Dataset.normalize
# ============================================================

class TestNormalizeData:

    def test_hand_computed(self):
        got = _bare_system().normalize_data([[0, 10], [2, 20], [4, 30]])
        assert got == [[0.0, 0.0], [0.5, 0.5], [1.0, 1.0]]

    def test_input_not_mutated(self):
        data = [[0, 10], [2, 20], [4, 30]]
        before = copy.deepcopy(data)
        out = _bare_system().normalize_data(data)
        assert data == before
        assert out is not data

    def test_parity_with_dataset_normalize(self):
        rng = random.Random(42)
        data = [[rng.uniform(-5, 5) for _ in range(3)] for _ in range(6)]
        ds = Dataset()
        ds._data = [list(r) for r in data]
        ds.features = 3
        ds.normalize()
        got = _bare_system().normalize_data(data)
        assert got == ds._data

    @pytest.mark.parametrize("data", [
        [], "abc", [5], [[]], [[1, 2], [3]], [[1, "a"]], [[True, 1]],
        [[1, 5], [1, 7]], [[1, 2]],
    ])
    def test_rejection_matrix(self, data):
        with pytest.raises(ValueError):
            _bare_system().normalize_data(data)


# ============================================================
# 5. ML 工厂：_init_ml 死接线修复 + 缺席拒绝（原 AttributeError/假 dict）
# ============================================================

class TestMlFactories:

    def test_init_ml_wired_into_domains(self):
        src = inspect.getsource(MathaSystem._init_domains)
        assert "self._init_ml()" in src

    def test_init_ml_sets_real_classes(self):
        s = MathaSystem.__new__(MathaSystem)
        s.debug = False
        s._init_ml()
        assert s.ml_class is MathaML
        assert s.linear_regression_class is LinearRegression
        assert s.logistic_regression_class is LogisticRegression
        assert s.kmeans_class is KMeans

    def test_real_factories(self):
        s = _bare_system()
        assert isinstance(s.create_ml_manager(), MathaML)
        lr = s.create_linear_regression(0.05, 10)
        assert isinstance(lr, LinearRegression)
        assert lr.lr == 0.05 and lr.epochs == 10
        assert isinstance(s.create_logistic_regression(), LogisticRegression)
        km = s.create_kmeans(2)
        assert isinstance(km, KMeans) and km.k == 2

    @pytest.mark.parametrize("attr,method", [
        ("ml_class", "create_ml_manager"),
        ("linear_regression_class", "create_linear_regression"),
        ("logistic_regression_class", "create_logistic_regression"),
        ("kmeans_class", "create_kmeans"),
    ])
    def test_absent_module_rejects(self, attr, method):
        s = _bare_system()
        setattr(s, attr, None)
        with pytest.raises(RuntimeError, match="机器学习"):
            getattr(s, method)()


# ============================================================
# 6. train_model：真委托 fit（原无 fit 回退假 dict）
# ============================================================

class TestTrainModel:

    def test_delegates_to_real_fit(self):
        s = _bare_system()
        lr = s.create_linear_regression(0.01, 200)
        result = s.train_model(lr, [[1], [2], [3]], [2, 4, 6])
        assert isinstance(result, ModelResult)
        assert lr.trained is True

    def test_fit_args_forwarded_exactly(self):
        seen = []

        class FakeModel:
            def fit(self, X, y):
                seen.append((X, y))
                return "trained"

        X, y = [[1, 2]], [3]
        assert _bare_system().train_model(FakeModel(), X, y) == "trained"
        assert seen == [(X, y)]

    def test_no_fit_rejects(self):
        with pytest.raises(TypeError, match="fit"):
            _bare_system().train_model({"type": "fake"}, [[1]], [1])

    def test_non_callable_fit_rejects(self):
        class NotCallable:
            fit = 5

        with pytest.raises(TypeError, match="fit"):
            _bare_system().train_model(NotCallable(), [[1]], [1])


# ============================================================
# 7. create_data_science：缺席拒绝（原假 dict）
# ============================================================

class TestCreateDataScience:

    def test_real_manager(self):
        assert isinstance(_bare_system().create_data_science(),
                          DataScienceManager)

    def test_absent_module_rejects(self):
        s = _bare_system()
        s.data_science_class = None
        with pytest.raises(RuntimeError, match="数据科学"):
            s.create_data_science()