# -*- coding: utf-8 -*-
"""神经网络领域插件行为级门禁锁（阶段 1 · AI 修复）。

背景：`src/domains/neural_network.py` 历史上是假实现——forward/predict
原样透传输入、train 恒 loss=0、CNN/RNN 构建方法返回假 dict。本轮以已背书
的 ai_framework 数值腿为地基重写前向/训练/预测，本文件三类锁封死回退：

  1. **手算对拍**：前向输出与独立闭式手算（读底层权重逐元素算）逐位比对，
     封死「恒等透传」病理；
  2. **收敛闭环**：XOR 真训练（配方与 test_ai_framework_numerics 同：
     seed 7 / Adam lr=0.05 / 4000 轮），损失真降、预测方向正确，
     封死「恒 loss=0」病理；
  3. **显式拒绝**：未添加层、维度不合、未知激活、CNN/RNN 未实现链一律
     如实抛错，严禁静默占位。

另有注册契约锁（manifest 符号面不漂移、柯里化注册形态）与主执行链
端到端锁（干净子进程经 exec_api 懒加载真算，遵「sys.modules 断言起子进程」
纪律）。训练有效性主张（泛化/收敛速度）不背书，口径遵 KNOWN_ISSUES §7c。
"""
from __future__ import annotations

import json
import math
import random
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.domains.neural_network import (  # noqa: E402
    ConvNet,
    ModelConfig,
    NeuralNetwork,
    RNN,
    TrainingResult,
    _nn_symtab_names,
    _register_nn,
    create_convnet,
    create_neural_network,
    create_rnn,
)

MANIFEST = ROOT / "src" / "domains" / "manifest.json"


def _nn(layers=((2, 4, "sigmoid"), (4, 1, "sigmoid")),
        lr=0.05, epochs=100) -> NeuralNetwork:
    nn = create_neural_network()
    nn.config = ModelConfig(learning_rate=lr, epochs=epochs)
    for i, o, a in layers:
        nn.add_layer(i, o, a)
    return nn


# ============================================================
# 1. 前向手算对拍（封死恒等透传）
# ============================================================

class TestForwardHandComputed:

    def test_sigmoid_layer_matches_closed_form(self):
        random.seed(3)
        nn = _nn(layers=((2, 2, "sigmoid"),))
        out = nn.forward([1.0, 2.0])
        lin = nn._model.layers[0]
        W, b = lin.weight.data, lin.bias.data
        expect = [1.0 / (1.0 + math.exp(-(1.0 * W[0][j] + 2.0 * W[1][j] + b[j])))
                  for j in range(2)]
        assert out == pytest.approx(expect, abs=1e-12)
        assert out != [1.0, 2.0]          # 病理封条：不得原样透传

    def test_two_layer_relu_matches_closed_form(self):
        random.seed(11)
        nn = _nn(layers=((2, 3, "relu"), (3, 2, "relu")))
        x = [0.5, -1.0]
        out = nn.forward(x)
        m = nn._model
        h = [max(0.0, sum(x[k] * m.layers[0].weight.data[k][j]
                          for k in range(2)) + m.layers[0].bias.data[j])
             for j in range(3)]
        expect = [max(0.0, sum(h[k] * m.layers[2].weight.data[k][j]
                               for k in range(3)) + m.layers[2].bias.data[j])
                  for j in range(2)]
        assert out == pytest.approx(expect, abs=1e-12)

    def test_softmax_output_is_distribution(self):
        random.seed(5)
        nn = _nn(layers=((2, 3, "softmax"),))
        out = nn.forward([1.0, 2.0])
        assert len(out) == 3
        assert sum(out) == pytest.approx(1.0, abs=1e-12)
        assert all(0.0 < v < 1.0 for v in out)

    def test_predict_is_same_true_inference(self):
        random.seed(3)
        nn = _nn(layers=((2, 2, "sigmoid"),))
        assert nn.predict([1.0, 2.0]) == nn.forward([1.0, 2.0])


# ============================================================
# 2. 训练收敛闭环（封死恒 loss=0）
# ============================================================

class TestTrainingConvergence:

    def test_xor_learns_via_real_backprop(self):
        random.seed(7)
        nn = _nn(lr=0.05, epochs=4000)
        X = [[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0]]
        Y = [[0.0], [1.0], [1.0], [0.0]]
        result = nn.train(X, Y)
        assert isinstance(result, TrainingResult)
        assert result.final_loss < 0.02
        assert result.final_accuracy == 1.0
        outs = [nn.predict(x)[0] for x in X]
        assert outs[0] < 0.2 and outs[3] < 0.2
        assert outs[1] > 0.8 and outs[2] > 0.8

    def test_loss_history_is_real_readings(self):
        random.seed(7)
        nn = _nn(lr=0.05, epochs=200)
        X = [[0.0, 0.0], [1.0, 1.0]]
        Y = [[0.0], [1.0]]
        result = nn.train(X, Y)
        assert len(result.loss_history) == 200
        assert len(result.accuracy_history) == 200
        assert result.loss_history[0] > 0.0
        assert not all(l == 0.0 for l in result.loss_history)  # 病理封条
        assert result.final_loss == result.loss_history[-1]
        assert result.final_loss < result.loss_history[0] / 10
        assert result.epochs_trained == 200
        assert all(0.0 <= a <= 1.0 for a in result.accuracy_history)

    def test_converged_flag_tracks_absolute_tolerance(self):
        random.seed(2)
        # sigmoid 趋 0 为渐近逼近，实测 seed 2 / lr 0.05 / 8000 轮 → loss≈5.8e-7
        nn = _nn(layers=((1, 1, "sigmoid"),), lr=0.05, epochs=8000)
        result = nn.train([[1.0]], [[0.0]])
        assert result.converged == (result.final_loss < 1e-6)
        assert result.final_loss < 1e-6
        assert nn.predict([1.0])[0] < 1e-3

    def test_train_twice_continues_from_learned_weights(self):
        random.seed(7)
        nn = _nn(lr=0.05, epochs=300)
        X = [[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0]]
        Y = [[0.0], [1.0], [1.0], [0.0]]
        first = nn.train(X, Y)
        second = nn.train(X, Y)
        assert second.loss_history[0] <= first.final_loss * 1.5
        assert second.final_loss <= first.final_loss


# ============================================================
# 3. 显式拒绝（封死静默占位）
# ============================================================

class TestExplicitRejection:

    def test_forward_without_layers_rejected(self):
        with pytest.raises(RuntimeError):
            create_neural_network().forward([1.0])

    def test_train_without_layers_rejected(self):
        with pytest.raises(RuntimeError):
            create_neural_network().train([[1.0]], [[1.0]])

    @pytest.mark.parametrize("bad", [
        [], [1.0], [1.0, 2.0, 3.0], ["a", "b"], [1.0, None], [True, False],
    ])
    def test_forward_bad_input_rejected(self, bad):
        nn = _nn(layers=((2, 2, "relu"),))
        with pytest.raises(ValueError):
            nn.forward(bad)

    def test_layer_dimension_discontinuity_rejected(self):
        nn = create_neural_network()
        nn.add_layer(2, 3)
        with pytest.raises(ValueError):
            nn.add_layer(4, 1)

    @pytest.mark.parametrize("bad", [0, -1, 2.5, True, "3"])
    def test_bad_layer_size_rejected(self, bad):
        with pytest.raises(ValueError):
            create_neural_network().add_layer(bad, 2)
        with pytest.raises(ValueError):
            create_neural_network().add_layer(2, bad)

    def test_unknown_activation_rejected(self):
        with pytest.raises(ValueError):
            create_neural_network().add_layer(2, 2, "elu")

    def test_leaky_relu_declared_but_unimplemented_rejected(self):
        with pytest.raises(NotImplementedError):
            create_neural_network().add_layer(2, 2, "leaky_relu")

    def test_train_empty_data_rejected(self):
        nn = _nn(layers=((2, 1, "relu"),))
        with pytest.raises(ValueError):
            nn.train([], [])

    def test_train_width_mismatch_rejected(self):
        nn = _nn(layers=((2, 1, "relu"),))
        with pytest.raises(ValueError):
            nn.train([[1.0]], [[1.0]])
        with pytest.raises(ValueError):
            nn.train([[1.0, 2.0]], [[1.0, 2.0]])

    def test_train_count_mismatch_rejected(self):
        nn = _nn(layers=((2, 1, "relu"),))
        with pytest.raises(ValueError):
            nn.train([[1.0, 2.0]], [[1.0], [2.0]])

    def test_zero_epochs_rejected(self):
        nn = _nn(layers=((2, 1, "relu"),), epochs=0)
        with pytest.raises(ValueError):
            nn.train([[1.0, 2.0]], [[1.0]])

    @pytest.mark.parametrize("method,args", [
        ("add_conv2d", (8, 3)),
        ("add_pooling", (2,)),
        ("add_flatten", ()),
        ("add_dense", (16,)),
    ])
    def test_convnet_unimplemented_chain_rejected(self, method, args):
        """病理封条：旧实现返回假 dict 冒充成功。"""
        with pytest.raises(NotImplementedError):
            getattr(create_convnet(), method)(*args)

    @pytest.mark.parametrize("method,args", [
        ("add_lstm", (16,)), ("add_gru", (16,)),
    ])
    def test_rnn_unimplemented_chain_rejected(self, method, args):
        with pytest.raises(NotImplementedError):
            getattr(create_rnn(), method)(*args)


# ============================================================
# 4. 注册契约：符号面不漂移 + 柯里化形态
# ============================================================

class TestRegistrationContract:

    def test_symbols_match_manifest(self):
        payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
        entry = next(p for p in payload["plugins"] if p["name"] == "neural_network")
        assert set(entry["symbols"]) == set(_nn_symtab_names())
        builtins: dict = {}
        _register_nn(builtins)
        assert set(builtins) == set(entry["symbols"])

    def test_registered_forms_are_curried(self):
        """Matha 的 f(a,b) 编译为 f(a)(b)：注册必须是逐参 lambda 链。"""
        builtins: dict = {}
        _register_nn(builtins)
        nn = builtins["创建神经网络"](2)(4)
        assert isinstance(nn, NeuralNetwork)
        layer = builtins["添加层"](nn)(2)(2)("relu")
        assert layer.input_size == 2 and layer.output_size == 2
        assert isinstance(builtins["前向传播"](nn)([1.0, 2.0]), list)
        assert isinstance(builtins["创建CNN"](0), ConvNet)   # 零参写法传入 0
        assert isinstance(builtins["创建RNN"](0), RNN)


# ============================================================
# 5. 主执行链端到端（干净子进程，懒加载真算）
# ============================================================

_E2E_SNIPPET = """
import json, sys
sys.path.insert(0, %r)
from src.kernel import exec_api
from src.plugin_api import get_resolver
src = '''@：【加载领域】，神经网络
nn = 创建神经网络(2, 4)
添加层(nn, 2, 4, "sigmoid")
添加层(nn, 4, 1, "sigmoid")
r = 训练模型(nn, [[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0]], [[0.0], [1.0], [1.0], [0.0]])
#1：[前向传播(nn, [0.0, 1.0])]
'''
out = exec_api.run(src)
v = out[-1]
assert isinstance(v, list) and len(v) == 1 and 0.0 < v[0] < 1.0, out
assert "neural_network" in get_resolver().loaded()
print(json.dumps({"out": v}))
""" % str(ROOT)


def test_main_chain_lazy_loads_and_computes_for_real():
    proc = subprocess.run([sys.executable, "-c", _E2E_SNIPPET],
                          cwd=str(ROOT), capture_output=True, text=True,
                          timeout=180)
    assert proc.returncode == 0, proc.stderr[-800:]
    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    assert 0.0 < payload["out"][0] < 1.0


_E2E_REJECT_SNIPPET = """
import sys
sys.path.insert(0, %r)
from src.kernel import exec_api
src = '''@：【加载领域】，神经网络
c = 创建CNN(0)
添加卷积层(c, 8, 3, 1)
'''
try:
    exec_api.run(src)
except NotImplementedError as e:
    assert "CNN" in str(e)
    print("REJECTED")
else:
    raise AssertionError("CNN 假成功复活：未抛 NotImplementedError")
""" % str(ROOT)


def test_main_chain_surfaces_honest_rejection():
    proc = subprocess.run([sys.executable, "-c", _E2E_REJECT_SNIPPET],
                          cwd=str(ROOT), capture_output=True, text=True,
                          timeout=180)
    assert proc.returncode == 0, proc.stderr[-800:]
    assert "REJECTED" in proc.stdout