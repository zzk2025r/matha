# -*- coding: utf-8 -*-
"""AI 框架数值腿门禁锁（矩阵乘法地基 → 前向/反向/损失/训练/序列化）。

背景（2026-11 攻坚）：`src/ai_framework.py` 历史上是 API 壳——`Linear.forward`
对 bias 标量做下标即崩（实测 TypeError），Softmax 返均匀 1/n、损失恒返 0.0、
`train_step` 恒返 0.0、`evaluate` 硬编码 `{loss:0, accuracy:1}`。本轮以
**矩阵乘法 `matmul` 为地基**重写整条数值腿，本文件三类锁封死回退：

  1. **手算对拍**：matmul/Linear/激活/损失/Conv2D/jacobian 逐条与闭式手算值比对
     （离线零依赖，不经第三方库；另与 `domains.ai_data_science.matrix_mult`
     在**子进程**里做跨引擎互证，避免把领域模块带进主会话污染懒加载现场）；
  2. **收敛闭环**：线性回归 y=2x 与 XOR 训练证明「前向→损失→逐层反向→优化器」
     全链真接线（证明链路正确性，**不**背书深度学习的有效性/先进能力）；
  3. **显式拒绝**：形状不合、未前向先反向的 BatchNorm/Conv2D 误用、未 compile
     训练等一律如实抛错——严禁静默返回全零/假结果（历史缺陷的病理封条）；
     BatchNorm/Conv2D backward 已于后续攻坚为真梯度（手算+梯度神谕锁见
     TestBackwardCompletion，旧拒绝锁同步替换为误用拒绝锁）。

纪律（遵 KNOWN_ISSUES §7c）：本锁背书的是**数值腿语义**；`ai_framework.py`
整体仍属未背书前端，横幅口径为「数值腿已经严格测试背书、深度能力不背书」。
"""
import math
import random
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import ai_framework as ai  # noqa: E402


def _t(data, shape=None):
    if shape is None:
        if isinstance(data, list) and data and isinstance(data[0], list):
            shape = (len(data), len(data[0]))
        else:
            shape = (len(data),) if isinstance(data, list) else ()
    return ai.Tensor(data=data, shape=shape)


def _close(a, b, tol=1e-6):
    if isinstance(a, list):
        return len(a) == len(b) and all(_close(u, v, tol) for u, v in zip(a, b))
    return abs(a - b) <= tol


# ============================================================
# 1. 矩阵乘法地基
# ============================================================

class TestMatmulFoundation:

    def test_2x2_hand_computed(self):
        assert ai.matmul([[1, 2], [3, 4]], [[5, 6], [7, 8]]) == [[19, 22], [43, 50]]

    def test_2x3_times_3x2_hand_computed(self):
        a = [[1, 2, 3], [4, 5, 6]]
        b = [[7, 8], [9, 10], [11, 12]]
        assert ai.matmul(a, b) == [[58, 64], [139, 154]]

    def test_identity_and_column_row(self):
        m = [[2, 3], [4, 5]]
        assert ai.matmul(m, [[1, 0], [0, 1]]) == m
        assert ai.matmul([[1], [2], [3]], [[4, 5, 6]]) == [[4, 5, 6], [8, 10, 12], [12, 15, 18]]

    def test_non_commutative(self):
        a, b = [[1, 2], [3, 4]], [[0, 1], [1, 0]]
        assert ai.matmul(a, b) != ai.matmul(b, a)

    def test_dimension_mismatch_rejected(self):
        with pytest.raises(ValueError):
            ai.matmul([[1, 2]], [[1, 2]])          # 1×2 · 1×2 内维不合

    def test_ragged_and_nonnumeric_rejected(self):
        with pytest.raises(ValueError):
            ai.matmul([[1, 2], [3]], [[1], [2]])    # 锯齿阵
        with pytest.raises(ValueError):
            ai.matmul([[1, "x"]], [[1], [2]])       # 非数值
        with pytest.raises(ValueError):
            ai.matmul([1, 2], [[1], [2]])           # 非二维


def test_matmul_cross_check_with_domain_plugin_in_subprocess():
    """跨引擎互证：ai_framework.matmul ↔ domains.ai_data_science.matrix_mult。
    领域模块物化放子进程（项目纪律：不把 src.domains.* 带进主 pytest 会话）。"""
    snippet = (
        "import json, sys; sys.path.insert(0, r'D:\\trae');"
        "from src.ai_framework import matmul;"
        "from src.domains.ai_data_science import matrix_mult;"
        "pairs = [[[1,2,3],[4,5,6]], [[7,8],[9,10],[11,12]], [[1,0],[0,1]]];"
        "r1 = matmul(pairs[0], pairs[1]); r2 = matrix_mult(pairs[0], pairs[1]);"
        "e1 = matmul(pairs[2], pairs[2]);"
        "print(json.dumps({'ok': r1 == r2 and e1 == [[1,0],[0,1]]}))"
    )
    proc = subprocess.run([sys.executable, "-c", snippet], cwd=str(ROOT),
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr[-500:]
    assert '"ok": true' in proc.stdout.replace("'", '"').lower(), proc.stdout


# ============================================================
# 2. 层前向/反向（Linear 崩溃病理封条 + 激活真值）
# ============================================================

class TestLinearLayer:

    def test_forward_matches_hand_computed_matmul(self):
        lin = ai.Linear(2, 3)
        lin.weight.data = [[1, 2, 3], [4, 5, 6]]     # in×out
        lin.bias.data = [10, 20, 30]
        out = lin.forward(_t([[1, 1], [2, 0]]))
        # 行1: [1+4, 2+5, 3+6]+b = [15,27,39]；行2: [2+0,4+0,6+0]+b=[12,24,36]
        assert _close(out.data, [[15, 27, 39], [12, 24, 36]])

    def test_forward_no_longer_crashes(self):
        # 历史缺陷：bias.data 标量被下标 → TypeError（基本前向即崩）
        lin = ai.Linear(4, 3)
        out = lin.forward(_t([[0.1] * 4, [0.2] * 4]))
        assert out.shape == (2, 3)
        assert _close(out.data[0], out.data[0])          # 数值输出可读出
        other = lin.forward(_t([[9.0] * 4, [0.1] * 4]))   # 输入变→输出变（非恒零）
        assert other.data[0][0] != out.data[0][0] or lin.bias.data[0] == 0.0

    def test_backward_grads_hand_computed(self):
        lin = ai.Linear(2, 2)
        lin.weight.data = [[1, 2], [3, 4]]
        lin.bias.data = [0.0, 0.0]
        x = [[5.0, 6.0]]
        lin.forward(_t(x))
        g = lin.backward([[1.0, 1.0]])
        assert lin.weight.grad.data == [[5.0, 5.0], [6.0, 6.0]]  # Xᵀ·dY
        assert lin.bias.grad.data == [1.0, 1.0]                  # colsum(dY)
        # dX = dOut·Wᵀ：x0 影响 (o0,o1) 权重 (1,2)→1+2=3；x1 权重 (3,4)→3+4=7
        assert g == [[3.0, 7.0]]

    def test_wrong_input_width_rejected(self):
        with pytest.raises(ValueError):
            ai.Linear(2, 3).forward(_t([[1.0, 2.0, 3.0]]))


class TestActivations:

    def test_relu_values_and_backward_mask(self):
        r = ai.ReLU()
        out = r.forward(_t([[1.0, -2.0, 0.0], [3.0, -1.0, 2.0]]))
        assert out.data == [[1.0, 0.0, 0.0], [3.0, 0.0, 2.0]]
        assert r.backward([[1.0, 1.0, 1.0], [1.0, 1.0, 1.0]]) == [[1.0, 0.0, 0.0], [1.0, 0.0, 1.0]]

    def test_sigmoid_stable_extremes(self):
        s = ai.Sigmoid()
        out = s.forward(_t([[0.0, 1000.0, -1000.0]]))
        assert _close(out.data[0][0], 0.5)
        assert _close(out.data[0][1], 1.0, 1e-9)
        assert _close(out.data[0][2], 0.0, 1e-9)

    def test_tanh_hand(self):
        import math
        out = ai.Tanh().forward(_t([[0.0, 1.0]]))
        assert _close(out.data, [[0.0, math.tanh(1.0)]])

    def test_softmax_sums_to_one_and_monotone(self):
        import math
        sm = ai.Softmax()
        out = sm.forward(_t([[1.0, 2.0, 3.0]]))
        row = out.data[0]
        assert abs(sum(row) - 1.0) < 1e-12
        assert row[0] < row[1] < row[2]
        z = math.exp(1.0) + math.exp(2.0) + math.exp(3.0)
        assert _close(row, [math.exp(1.0) / z, math.exp(2.0) / z, math.exp(3.0) / z], 1e-12)

    def test_softmax_extreme_stable_not_uniform(self):
        # 历史缺陷：恒返均匀 1/n
        out = ai.Softmax().forward(_t([[1000.0, 0.0]]))
        assert out.data[0][0] == 1.0 and out.data[0][1] == 0.0

    def test_softmax_backward_matches_numeric_gradient(self):
        logits = [0.2, -0.3, 0.7]
        g = [1.0, 2.0, 0.5]
        sm = ai.Softmax()
        sm.forward(_t([logits]))
        analytic = sm.backward([g])[0]
        eps, numeric = 1e-6, []
        for i in range(3):
            lp = list(logits); lp[i] += eps
            lm = list(logits); lm[i] -= eps
            fp = sum(gi * pi for gi, pi in zip(g, ai.Softmax._row(lp)))
            fm = sum(gi * pi for gi, pi in zip(g, ai.Softmax._row(lm)))
            numeric.append((fp - fm) / (2 * eps))
        assert _close(analytic, numeric, 1e-4)


# ============================================================
# 3. 损失函数（历史缺陷：恒返 0.0）
# ============================================================

class TestLosses:

    def test_mse_forward_backward_hand(self):
        o, y = [[1.0, 2.0], [3.0, 4.0]], [[1.0, 2.0], [3.0, 6.0]]
        loss = ai.MSELoss().forward(_t(o), _t(y))
        assert _close(loss.data, 4.0 / 4)  # (0+0+0+4)/4 = 1.0
        assert loss.data == 1.0
        g = ai.MSELoss().backward(o, y)
        assert _close(g, [[0.0, 0.0], [0.0, -1.0]])  # 2(o-y)/n = 2(4-6)/4 = -1

    def test_cross_entropy_hand(self):
        import math
        logits, y = [[2.0, 1.0, 0.0]], [[1.0, 0.0, 0.0]]
        ce = ai.CrossEntropyLoss()
        loss = ce.forward(_t(logits), _t(y))
        z = math.exp(2.0) + math.exp(1.0) + math.exp(0.0)
        p0 = math.exp(2.0) / z
        assert _close(loss.data, -math.log(p0), 1e-12)
        probs = [math.exp(v) / z for v in logits[0]]
        g = ce.backward(None, y)
        assert _close(g[0], [probs[0] - 1.0, probs[1], probs[2]], 1e-9)

    def test_mse_shape_mismatch_rejected(self):
        with pytest.raises(ValueError):
            ai.MSELoss().forward(_t([[1.0, 2.0]]), _t([[1.0, 2.0, 3.0]]))


# ============================================================
# 4. 训练收敛闭环（证明反向链真接线，不背书深度能力）
# ============================================================

class TestTrainingConvergence:

    def test_linear_regression_recovers_slope(self):
        random.seed(42)
        m = ai.Sequential()
        m.add(ai.Linear(1, 1))
        m.compile(ai.MSELoss(), ai.Adam(m.parameters, lr=0.1))
        X = _t([[0.0], [1.0], [2.0], [3.0]])
        Y = _t([[0.0], [2.0], [4.0], [6.0]])
        first = m.train_step(X, Y)
        for _ in range(400):
            last = m.train_step(X, Y)
        assert last < first / 50.0          # 损失真实下降
        w = m.layers[0].weight.data[0][0]
        b = m.layers[0].bias.data[0]
        assert abs(w - 2.0) < 0.15 and abs(b) < 0.3   # 闭式解 y=2x 被找回

    def test_xor_learns_via_backprop(self):
        random.seed(7)
        m = ai.Sequential()
        m.add(ai.Linear(2, 4)); m.add(ai.Sigmoid())
        m.add(ai.Linear(4, 1)); m.add(ai.Sigmoid())
        m.compile(ai.MSELoss(), ai.Adam(m.parameters, lr=0.05))
        X = _t([[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [1.0, 1.0]])
        Y = _t([[0.0], [1.0], [1.0], [0.0]])
        losses = [m.train_step(X, Y) for _ in range(4000)]
        assert losses[-1] < 0.02                       # 收敛
        outs = m.forward(X).data
        assert outs[0][0] < 0.2 and outs[3][0] < 0.2   # 异或真值方向
        assert outs[1][0] > 0.8 and outs[2][0] > 0.8

    def test_train_step_without_compile_rejected(self):
        with pytest.raises(ValueError):
            ai.Model().train_step(_t([[1.0]]), _t([[1.0]]))

    def test_optimizer_updates_params(self):
        p = ai.Tensor(data=[[1.0, 2.0]], shape=(1, 2), requires_grad=True)
        p.grad = ai.Tensor(data=[[1.0, 1.0]], shape=(1, 2))
        ai.Optimizer([p], lr=0.5).step()
        assert p.data == [[0.5, 1.5]]
        random.seed(1)
        p.grad = ai.Tensor(data=[[1.0, 1.0]], shape=(1, 2))
        ai.Adam([p], lr=0.1).step()
        assert all(new < old for new, old in zip(p.data[0], [0.5, 1.5]))  # 首步方向 = -grad

    def test_sgd_momentum_and_weight_decay(self):
        p = ai.Tensor(data=[[1.0]], shape=(1, 1), requires_grad=True)
        opt = ai.SGD([p], lr=0.1, momentum=0.9, weight_decay=0.01)
        p.grad = ai.Tensor(data=[[0.0]], shape=(1, 1))
        opt.step()                       # grad=0 → decay 顶 -0.01·1.0 生效
        assert p.data[0][0] == pytest.approx(0.999)  # grad'=0.01; v=0.1*0.01=0.001; p-=v

    def test_evaluate_reports_real_numbers(self):
        # 历史缺陷：硬编码 {loss:0.0, accuracy:1.0}
        m = ai.Sequential()
        m.add(ai.Linear(2, 2))
        X, Y = _t([[1.0, 1.0]]), _t([[0.0, 0.0]])
        m.layers[0].weight.data = [[5.0, 0.0], [0.0, 0.0]]
        m.layers[0].bias.data = [0.0, 0.0]
        r = m.evaluate(X, Y)
        assert r["loss"] == 12.5          # ((5-0)²+(0-0)²)/2
        assert r["accuracy"] in (0.0, 1.0)


# ============================================================
# 5. 其余层的真语义与显式拒绝
# ============================================================

class TestOtherLayers:

    def test_dropout_eval_identity_and_seeded_mask(self):
        d = ai.Dropout(p=0.5, seed=3)
        x = _t([[1.0, 2.0, 3.0, 4.0]])
        d.eval()
        assert d.forward(x).data == x.data
        d.train()
        o1 = ai.Dropout(p=0.5, seed=3).forward(x)
        o2 = ai.Dropout(p=0.5, seed=3).forward(x)
        assert o1.data == o2.data                 # 同种子可复现
        d0 = ai.Dropout(p=0.0)
        assert d0.forward(x).data == x.data

    def test_dropout_invalid_p_rejected(self):
        with pytest.raises(ValueError):
            ai.Dropout(p=1.0)

    def test_batchnorm_forward_centers_and_eval_uses_running(self):
        import math
        bn = ai.BatchNorm(2)
        out = bn.forward(_t([[1.0, 10.0], [3.0, 20.0], [5.0, 30.0]]))
        col0 = [row[0] for row in out.data]
        assert abs(sum(col0) / 3.0) < 1e-9        # γ=1,β=0 → 批内均值归零
        bn.eval()
        # 推理走 running stats：rm=[0.3,2.0], rv=[7/6, 113.5/15] 手算
        rm = [0.1 * 3.0, 0.1 * 20.0]
        rv = [0.9 * 1.0 + 0.1 * (8.0 / 3.0), 0.9 * 1.0 + 0.1 * (200.0 / 3.0)]
        e = bn.forward(_t([[3.0, 20.0]]))
        expect = [(3.0 - rm[0]) / math.sqrt(rv[0] + 1e-5),
                  (20.0 - rm[1]) / math.sqrt(rv[1] + 1e-5)]
        assert _close(e.data[0], expect, 1e-9)

    def test_batchnorm_backward_requires_forward(self):
        bn = ai.BatchNorm(2)
        with pytest.raises(RuntimeError):
            bn.backward([[1.0, 1.0]])                    # 未前向先反向：误用拒绝

    def test_conv2d_hand_computed_valid_same(self):
        c = ai.Conv2D(1, 1, kernel_size=3, stride=1, padding=0)
        c.weight.data = [[[[1.0, 1.0, 1.0]] * 3]]          # (1,1,3,3) 全 1
        c.bias.data = [0.0]
        out = c.forward(ai.Tensor(data=[[[2.0] * 3] * 3], shape=(1, 3, 3)))
        assert out.data == [[[18.0]]]                        # 9 个窗口 ×2
        c2 = ai.Conv2D(1, 1, kernel_size=3, stride=2, padding=0)
        c2.weight.data = [[[[1.0] * 3] * 3]]; c2.bias.data = [0.0]
        o2 = c2.forward(ai.Tensor(data=[[[1.0] * 5] * 5], shape=(1, 5, 5)))
        assert o2.data == [[[9.0, 9.0], [9.0, 9.0]]]

    def test_conv2d_same_padding_corner_hand(self):
        c = ai.Conv2D(1, 1, kernel_size=3, stride=1, padding=1)
        c.weight.data = [[[[1.0] * 3] * 3]]; c.bias.data = [0.0]
        out = c.forward(ai.Tensor(data=[[[1.0] * 3] * 3], shape=(1, 3, 3)))
        assert out.data == [[[4.0, 6.0, 4.0], [6.0, 9.0, 6.0], [4.0, 6.0, 4.0]]]

    def test_conv2d_rejects_bad_usage(self):
        c = ai.Conv2D(1, 1, kernel_size=3)
        with pytest.raises(ValueError):
            c.forward(_t([[1.0, 2.0], [3.0, 4.0]]))      # 二维输入拒
        with pytest.raises(RuntimeError):
            c.backward([[[1.0]]])                        # 未前向先反向：误用拒
        c.weight.data = [[[[1.0] * 3] * 3]]; c.bias.data = [0.0]
        c.forward(ai.Tensor(data=[[[1.0] * 3] * 3], shape=(1, 3, 3)))
        with pytest.raises(ValueError):
            c.backward([[[1.0] * 2] * 2])                # 梯度形状≠前向输出：拒

    def test_base_layer_forward_rejects(self):
        with pytest.raises(NotImplementedError):
            ai.Layer("x").forward(_t([[1.0]]))


# ============================================================
# 6. AutoDiff / 序列化 / builtins
# ============================================================

class TestAutoDiffAndIO:

    def test_grad_finite_difference(self):
        ad = ai.AutoDiff()
        assert ad.grad(lambda v: v * v)(3.0) == pytest.approx(6.0, abs=1e-3)
        assert ad.grad(lambda v: v ** 3)(2.0) == pytest.approx(12.0, abs=1e-2)

    def test_jacobian_hand_computed(self):
        # 历史缺陷：jacobian 恒等透传
        import math
        f = lambda v: [v[0] ** 2 + v[1], math.sin(v[1])]
        J = ai.AutoDiff().jacobian(f)([3.0, 0.5])
        assert _close(J, [[6.0, 1.0], [0.0, math.cos(0.5)]], 1e-3)

    def test_save_load_roundtrip(self):
        import tempfile, os
        m = ai.Sequential("net")
        m.add(ai.Linear(2, 3)); m.add(ai.ReLU()); m.add(ai.Sigmoid())
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "model.json")
            m.save(p)
            m2 = ai.Sequential()
            m2.load(p)
            assert [l.name for l in m2.layers] == ["linear", "relu", "sigmoid"]
            assert m2.layers[0].weight.data == m.layers[0].weight.data
            assert m2.layers[0].bias.data == m.layers[0].bias.data
            x = _t([[1.0, 2.0]])
            assert _close(m2.forward(x).data, m.forward(x).data)

    def test_builtins_register_matrix_multiplication(self):
        d = {}
        ai._register_ai_framework(d)
        assert "矩阵乘法" in d and "矩阵乘法" in ai._ai_framework_names()
        assert d["矩阵乘法"]([[1, 2], [3, 4]], [[5, 6], [7, 8]]) == [[19, 22], [43, 50]]
        assert "创建Sigmoid" in d and "创建Tanh" in d

# ============================================================
# 7. 严格测试层（背书用）：代数性质律 / 边界值 / 全模型数值梯度神谕
#    / sympy 符号对拍 / 训练健壮性与确定性
# ============================================================

def _rand_mat(rows, cols, rng):
    return [[round(rng.uniform(-5.0, 5.0), 3) for _ in range(cols)] for _ in range(rows)]


class TestStrictAlgebraLaws:
    """seeded 随机的矩阵代数性质律（算法级正确，不只单点手算）。"""

    def test_associativity_and_distributivity(self):
        rng = random.Random(20261107)
        A = _rand_mat(3, 4, rng); B = _rand_mat(4, 5, rng); C = _rand_mat(5, 2, rng)
        lhs = ai.matmul(ai.matmul(A, B), C)
        rhs = ai.matmul(A, ai.matmul(B, C))
        assert _close(lhs, rhs, 1e-6)                      # (AB)C = A(BC)
        D = _rand_mat(3, 4, rng)
        s = [[a + b for a, b in zip(ra, rd)] for ra, rd in zip(A, D)]   # (A+D)B = AB + DB
        lhs2 = ai.matmul(s, B)
        rhs2 = [[x + y for x, y in zip(r1, r2)]
                for r1, r2 in zip(ai.matmul(A, B), ai.matmul(D, B))]
        assert _close(lhs2, rhs2, 1e-6)

    def test_transpose_laws(self):
        rng = random.Random(7)
        A = _rand_mat(3, 4, rng); B = _rand_mat(4, 2, rng)
        assert ai.transpose(ai.transpose(A)) == A                        # 对合
        lhs = ai.transpose(ai.matmul(A, B))
        rhs = ai.matmul(ai.transpose(B), ai.transpose(A))                # (AB)ᵀ=BᵀAᵀ
        assert _close(lhs, rhs, 1e-6)

    def test_identity_and_zero_boundaries(self):
        A = _rand_mat(2, 3, random.Random(1))
        I2, I3 = [[1.0, 0.0], [0.0, 1.0]], [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        assert _close(ai.matmul(I2, A), A, 1e-12)
        assert _close(ai.matmul(A, I3), A, 1e-12)
        Z = [[0.0, 0.0], [0.0, 0.0]]
        assert ai.matmul(Z, [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]) == [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]


class TestStrictBoundaryValues:
    """边界值纪律：0 / 极大值 / 近饱和 / 零方差，不得出 NaN・Inf・崩。"""

    def test_sigmoid_tanh_saturation_edges(self):
        s = ai.Sigmoid().forward(_t([[0.0, 1e308, -1e308]]))
        assert s.data[0] == [0.5, 1.0, 0.0]               # 无溢出
        t = ai.Tanh().forward(_t([[0.0, 1e308, -1e308]]))
        assert t.data[0] == [0.0, 1.0, -1.0]

    def test_softmax_huge_spread_and_zeros(self):
        row = ai.Softmax().forward(_t([[1e308, -1e308]])).data[0]
        assert row == [1.0, 0.0]
        row0 = ai.Softmax().forward(_t([[0.0, 0.0, 0.0]])).data[0]
        assert _close(row0, [1 / 3, 1 / 3, 1 / 3], 1e-15)  # 全零→均匀

    def test_mse_zero_when_perfect_and_no_diverge(self):
        o = [[1.5, -2.5]]
        assert ai.MSELoss().forward(_t(o), _t(o)).data == 0.0

    def test_batchnorm_zero_variance_column_finite(self):
        import math
        bn = ai.BatchNorm(2)
        out = bn.forward(_t([[3.0, 1.0], [3.0, 2.0], [3.0, 3.0]]))     # 常数列 var=0
        assert all(math.isfinite(v) for row in out.data for v in row)
        assert _close([r[0] for r in out.data], [0.0, 0.0, 0.0], 1e-12)  # 除 eps 后仍归零

    def test_conv_large_padding_finite_output_shape(self):
        c = ai.Conv2D(1, 1, kernel_size=3, stride=1, padding=3)
        c.weight.data = [[[[0.5] * 3] * 3]]; c.bias.data = [0.0]
        out = c.forward(ai.Tensor(data=[[[1.0] * 3] * 3], shape=(1, 3, 3)))
        assert out.shape == (1, 7, 7)                                   # 3+6-3+1=7
        assert all(math.isfinite(v) for p in out.data for r in p for v in r)
        assert out.data[0][3][3] == 4.5          # 中心窗口 9 格全落入×0.5
        assert out.data[0][0][0] == 0.0          # 角上窗口全在 padding 区

    def test_empty_and_degenerate_matmul_rejected(self):
        with pytest.raises(ValueError):
            ai.matmul([], [[1]])
        with pytest.raises(ValueError):
            ai.matmul([[]], [[]])                                       # 0 宽阵
        with pytest.raises(ValueError):
            ai.matmul([[1.0]], "bad")

    def test_adam_zero_grad_is_noop(self):
        p = ai.Tensor(data=[[2.0]], shape=(1, 1), requires_grad=True)
        p.grad = ai.Tensor(data=[[0.0]], shape=(1, 1))
        ai.Adam([p], lr=0.1).step()
        assert p.data == [[2.0]]


class TestStrictGradientOracle:
    """全模型中心差分神谕：反向解析梯度 ↔ 数值 ∂loss/∂param（逐元素），
    这是对「前向→损失→逐层反向」整链最硬的交叉证明。"""

    @staticmethod
    def _loss_of(model, X, Y):
        out = model.forward(X)
        return sum((a - b) ** 2 for ro, ry in zip(out.data, Y.data)
                   for a, b in zip(ro, ry)) / (len(out.data) * len(out.data[0]))

    @staticmethod
    def _oracle(model, X, Y, eps=1e-5):
        grads = []
        for li, layer in enumerate(model.layers):
            if not isinstance(layer, ai.Linear):
                continue
            entries = []
            for wname in ("weight", "bias"):
                w = getattr(layer, wname)
                if w is None:
                    continue
                data = w.data
                if wname == "bias":
                    for j in range(len(data)):
                        data[j] += eps; hp = TestStrictGradientOracle._loss_of(model, X, Y)
                        data[j] -= 2 * eps; hm = TestStrictGradientOracle._loss_of(model, X, Y)
                        data[j] += eps
                        entries.append(((li, wname, j), (hp - hm) / (2 * eps)))
                else:
                    for i in range(len(data)):
                        for k in range(len(data[i])):
                            data[i][k] += eps; hp = TestStrictGradientOracle._loss_of(model, X, Y)
                            data[i][k] -= 2 * eps; hm = TestStrictGradientOracle._loss_of(model, X, Y)
                            data[i][k] += eps
                            entries.append(((li, wname, (i, k)), (hp - hm) / (2 * eps)))
            grads.append(entries)
        return [x for sub in grads for x in sub]

    def test_mlp_backprop_matches_central_difference(self):
        random.seed(123)
        m = ai.Sequential()
        m.add(ai.Linear(3, 4)); m.add(ai.Sigmoid())
        m.add(ai.Linear(4, 2)); m.add(ai.Tanh())
        X = _t([[0.3, -0.7, 0.11], [0.9, 0.5, -0.4], [0.0, 1.0, 1.0]])
        Y = _t([[0.5, -0.2], [0.1, 0.9], [-0.8, 0.3]])
        m.optimizer = ai.Adam(m.parameters)      # 仅为 zero_grad/step 不跑，手写反传
        m.loss_fn = ai.MSELoss()
        m.optimizer.zero_grad()
        out = m.forward(X)
        g = m.loss_fn.backward(out, Y)
        for layer in reversed(m.layers):
            g = layer.backward(g)
        oracle = self._oracle(m, X, Y)
        checked = 0
        for (li, wname, idx), num in oracle:
            layer = m.layers[li]
            ana = getattr(layer, wname).grad.data
            got = ana[idx] if wname == "bias" else ana[idx[0]][idx[1]]
            assert abs(got - num) < 1e-5 * max(1.0, abs(num)), f"L{li}.{wname}{idx}: {got} vs {num}"
            checked += 1
        assert checked == 3 * 4 + 4 + 4 * 2 + 2      # 全部参数元素都被神谕验证


class TestStrictSympyCrossCheck:
    """外部权威库符号对拍（背书惯例：对标 SymPy；缺失即 skip 并如实登记）。"""

    @pytest.fixture(autouse=True)
    def _require_sympy(self):
        pytest.importorskip("sympy", reason="严格背书层需 sympy 符号对拍（本机已实测可用）")

    def test_mse_gradient_vs_sympy(self):
        import sympy as sp
        o0, o1, y0, y1 = sp.symbols("o0 o1 y0 y1")
        L = ((o0 - y0) ** 2 + (o1 - y1) ** 2) / 2
        d = [sp.diff(L, v) for v in (o0, o1)]
        pt = {o0: 1.3, o1: -0.7, y0: 0.2, y1: 0.5}
        expect = [float(x.subs(pt)) for x in d]
        got = ai.MSELoss().backward([[1.3, -0.7]], [[0.2, 0.5]])[0]
        assert _close(got, expect, 1e-12)

    def test_softmax_ce_gradient_vs_sympy(self):
        import sympy as sp
        l0, l1, l2 = sp.symbols("l0 l1 l2")
        p = [sp.exp(v) / (sp.exp(l0) + sp.exp(l1) + sp.exp(l2)) for v in (l0, l1, l2)]
        L = -sp.log(p[1])
        pt = {l0: 0.4, l1: 1.2, l2: -0.9}
        expect = [float(sp.diff(L, v).subs(pt)) for v in (l0, l1, l2)]
        ce = ai.CrossEntropyLoss()
        logits = [[0.4, 1.2, -0.9]]
        ce.forward(_t(logits), _t([[0.0, 1.0, 0.0]]))
        got = ce.backward(None, [[0.0, 1.0, 0.0]])[0]
        assert _close(got, expect, 1e-9)

    def test_matmul_product_vs_sympy(self):
        import sympy as sp
        rng = random.Random(99)
        for _ in range(3):
            A = _rand_mat(3, 3, rng); B = _rand_mat(3, 3, rng)
            expect = sp.Matrix(A) * sp.Matrix(B)
            assert _close(ai.matmul(A, B), expect.tolist(), 1e-9)

    def test_sigmoid_derivative_vs_sympy(self):
        import sympy as sp
        x = sp.symbols("x")
        f = 1 / (1 + sp.exp(-x))
        d = sp.diff(f, x)
        for v in (0.0, 0.7, -2.3, 30.0):
            s = ai.Sigmoid()
            s.forward(_t([[v]]))
            got = s.backward([[1.0]])[0][0]           # d sigmoid/dx
            expect = float(d.subs(x, v).evalf())
            assert abs(got - expect) < 1e-9


class TestStrictTrainingRobustness:
    """训练健壮性：随机目标记忆 / 同种子确定性 / 无 NaN 发散。"""

    def test_memorize_random_targets_then_no_nan(self):
        random.seed(2026)
        m = ai.Sequential()
        m.add(ai.Linear(2, 6)); m.add(ai.Sigmoid())
        m.add(ai.Linear(6, 1))
        m.compile(ai.MSELoss(), ai.Adam(m.parameters, lr=0.08))
        rng = random.Random(5)
        X = _t([[round(x, 2), round(y, 2)] for x, y in
                [(rng.uniform(-1, 1), rng.uniform(-1, 1)) for _ in range(8)]])
        Y = _t([[round(rng.uniform(-1, 1), 2)] for _ in range(8)])
        hist = [m.train_step(X, Y) for _ in range(4000)]
        assert all(math.isfinite(h) for h in hist)
        assert hist[-1] < 1e-3 and hist[-1] < hist[0] / 100

    def test_same_seed_identical_trajectory(self):
        def run():
            random.seed(555)
            m = ai.Sequential()
            m.add(ai.Linear(1, 2)); m.add(ai.Tanh()); m.add(ai.Linear(2, 1))
            m.compile(ai.MSELoss(), ai.Adam(m.parameters, lr=0.1))
            X = _t([[0.2], [0.7], [-0.5]]); Y = _t([[0.9], [0.1], [-0.3]])
            return [m.train_step(X, Y) for _ in range(30)]
        assert run() == run()                          # 逐位确定性

    def test_save_load_after_training_predicts_identically(self):
        import tempfile, os
        random.seed(31)
        m = ai.Sequential()
        m.add(ai.Linear(2, 3)); m.add(ai.ReLU()); m.add(ai.Linear(3, 1))
        m.compile(ai.MSELoss(), ai.Adam(m.parameters, lr=0.05))
        X = _t([[0.4, -0.2]]); Y = _t([[0.6]])
        for _ in range(120):
            m.train_step(X, Y)
        with tempfile.TemporaryDirectory() as td:
            pth = os.path.join(td, "m.json")
            m.save(pth)
            m2 = ai.Sequential(); m2.load(pth)
            assert m2.forward(X).data == m.forward(X).data   # 推理不变（无 Dropout 路径）
            assert m2.evaluate(X, Y)["loss"] == pytest.approx(m.evaluate(X, Y)["loss"])

    def test_trainer_history_real_and_early_stop(self):
        random.seed(11)
        m = ai.Sequential()
        m.add(ai.Linear(1, 1))
        m.compile(ai.MSELoss(), ai.Adam(m.parameters, lr=0.1))
        X, Y = _t([[1.0], [2.0]]), _t([[2.0], [4.0]])
        tr = ai.Trainer(m, epochs=50)
        h = tr.fit(X, Y)
        assert len(h["loss"]) == 50
        assert h["loss"][-1] < h["loss"][0]
        # 早停机制级锁：损失连续 patience 轮无改善即触发
        tr2 = ai.Trainer(m, epochs=10)
        tr2.history = {"loss": [1.0, 0.5, 0.5, 0.5], "accuracy": []}
        tr2._best_loss = 0.5
        tr2.early_stop(patience=3)
        assert not tr2._early_stopped           # 第 1 次无改善
        tr2.early_stop(patience=3)
        assert not tr2._early_stopped           # 第 2 次
        tr2.early_stop(patience=3)
        assert tr2._early_stopped               # 达 patience 触发


# ============================================================
# 8. BatchNorm/Conv2D backward 攻坚：闭式手算对拍 + 任意深度逐参数
#    中心差分神谕（含输入梯度回流）+ 训练链落地锁
# ============================================================

def _paths(data, prefix=()):
    """任意深度嵌套 → (路径, 值) 序列（神谕与解析侧同一遍历序）。"""
    if isinstance(data, list):
        for i, v in enumerate(data):
            yield from _paths(v, prefix + (i,))
    else:
        yield prefix, data


def _setp(data, path, v):
    for p in path[:-1]:
        data = data[p]
    data[path[-1]] = v


def _mse_any(out_data, y_data):
    fl = [v for _, v in _paths(out_data)]
    fy = [v for _, v in _paths(y_data)]
    return sum((a - b) ** 2 for a, b in zip(fl, fy)) / len(fl)


def _oracle_params(model, X, Y, eps=1e-5):
    """逐参数元素中心差分 ∂loss/∂θ（支持 Linear/BatchNorm/Conv2D 任意嵌套）。"""
    res = []
    for li, layer in enumerate(model.layers):
        for wname in ("weight", "bias"):
            w = getattr(layer, wname, None)
            if w is None:
                continue
            for path, val in list(_paths(w.data)):
                _setp(w.data, path, val + eps)
                hp = _mse_any(model.forward(X).data, Y.data)
                _setp(w.data, path, val - eps)      # 对称 ±eps（非对称会使商带 1.5× 系统误差）
                hm = _mse_any(model.forward(X).data, Y.data)
                _setp(w.data, path, val)
                res.append(((li, wname, path), (hp - hm) / (2 * eps)))
    return res


def _backchain_grads(model, X, Y):
    """解析反向链（与 train_step 同路），返回 {(li, wname): grad 嵌套 data}。"""
    model.optimizer.zero_grad()
    out = model.forward(X)
    n = len(out.data) * len(out.data[0])
    g = [[2.0 * (a - b) / n for a, b in zip(ro, ry)]
         for ro, ry in zip(out.data, Y.data)]
    for layer in reversed(model.layers):
        g = layer.backward(g)
    grads = {}
    for li, layer in enumerate(model.layers):
        for wname in ("weight", "bias"):
            w = getattr(layer, wname, None)
            if w is not None:
                grads[(li, wname)] = w.grad.data
    return grads


class MSEAnyLoss(ai.LossFunction):
    """任意深度嵌套 MSE（conv 3D 输出的训练链用）：mean((o−y)²)，grad 2(o−y)/n。"""

    def forward(self, x, y):
        return ai.Tensor(data=_mse_any(x.data, y.data), shape=())

    def backward(self, x, y):
        o = x.data if isinstance(x, ai.Tensor) else x
        yv = y.data if isinstance(y, ai.Tensor) else y
        n = len([1 for _ in _paths(o)])
        return _deep_diff(o, yv, n)


def _deep_diff(o, yv, n):
    if isinstance(o, list):
        return [_deep_diff(a, b, n) for a, b in zip(o, yv)]
    return 2.0 * (o - yv) / n


class TestBackwardCompletion:
    """BN/Conv2D backward 真梯度的攻坚锁。"""

    # ── 手算对拍（闭式小整数现场） ──

    def test_batchnorm_backward_hand_computed(self):
        # 现场：x 两列均为 mean=0, var=1；γ=1, β=0, eps=0 → x̂=x, std=1
        bn = ai.BatchNorm(2, eps=0.0)
        X = _t([[-1.0, -1.0], [-1.0, 1.0], [1.0, -1.0], [1.0, 1.0]])
        bn.forward(X)
        dout = [[0.5, -1.5], [1.0, 0.25], [-0.5, 2.0], [1.5, -0.75]]
        dx = bn.backward(dout)
        # dβ = 列和； dγ = Σ dout·x̂
        assert _close(bn.bias.grad.data, [2.5, 0.0], 1e-12)
        assert _close(bn.weight.grad.data, [-0.5, -1.0], 1e-12)
        # dx_ij = dout − mean(dout) − x̂·mean(dout·x̂)（std=1, γ=1）逐格手算：
        assert _close(dx, [[-0.25, -1.75], [0.25, 0.5], [-1.0, 1.75], [1.0, -0.5]], 1e-12)
        # 投影性质自检：dx 沿 batch 维均值=0、与 x̂ 正交（BN 反向的数学不变量）
        assert abs(sum(r[0] for r in dx)) < 1e-12
        assert abs(sum(r[0] * x0 for r, x0 in zip(dx, [-1.0, -1.0, 1.0, 1.0]))) < 1e-12

    def test_batchnorm_backward_nonunit_gamma(self):
        # γ≠1 时 dxhat=γ·dout 参与均值项：用另一组小整数现场手算
        bn = ai.BatchNorm(1, eps=0.0)
        bn.weight.data = [2.0]; bn.bias.data = [1.0]
        X = _t([[-1.0], [0.0], [1.0]])                      # mean=0, var=2/3
        std = math.sqrt(2.0 / 3.0)
        bn.forward(X)
        dout = [[1.0], [0.0], [-1.0]]
        dx = bn.backward(dout)
        # x̂ = x/std；dxhat = γ·dout = [2,0,-2]；mean(dxhat)=0；
        # mean(dxhat·x̂) = (2·(−1/s) + 0 + (−2)·(1/s))/3 = −4/(3s)
        # dx_i = (dxhat_i − 0 − x̂_i·(−4/(3s)))/s = 2·dout_i/s + x_i·4/(9·s²)·...逐步展开：
        s = std
        expect = [[(2.0 + (-1.0 / s) * (4.0 / (3.0 * s))) / s],
                  [0.0],
                  [(-2.0 + (1.0 / s) * (4.0 / (3.0 * s))) / s]]
        assert _close(dx, expect, 1e-12)
        assert _close(bn.weight.grad.data,
                      [1.0 * (-1.0 / s) + 0.0 + (-1.0) * (1.0 / s)], 1e-12)
        assert _close(bn.bias.grad.data, [0.0], 1e-12)

    def test_conv2d_backward_hand_computed(self):
        # 现场：1→1 道，3×3 输入，k=2, s=1, pad=0 → 2×2 输出
        c = ai.Conv2D(1, 1, kernel_size=2, stride=1, padding=0)
        c.weight.data = [[[[1.0, 2.0], [3.0, 4.0]]]]
        c.bias.data = [0.0]
        xin = [[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]]]
        c.forward(ai.Tensor(data=xin, shape=(1, 3, 3)))
        dout = [[[0.5, -1.0], [2.0, 0.25]]]
        din = c.backward(dout)
        assert _close(c.weight.grad.data[0][0], [[7.75, 9.5], [13.0, 14.75]], 1e-12)
        assert _close(c.bias.grad.data, [1.75], 1e-12)
        assert _close(din, [[[0.5, 0.0, -2.0], [3.5, 3.25, -3.5], [6.0, 8.75, 1.0]]], 1e-12)

    # ── 中心差分梯度神谕（逐参数元素 + 输入梯度回流） ──

    def test_bn_mlp_oracle_all_params(self):
        random.seed(4242)
        m = ai.Sequential()
        m.add(ai.Linear(2, 3)); m.add(ai.BatchNorm(3)); m.add(ai.Linear(3, 1))
        m.compile(ai.MSELoss(), ai.Adam(m.parameters, lr=0.1))
        X = _t([[0.3, -0.7], [0.9, 0.5], [0.0, 1.0], [-0.4, 0.2]])
        Y = _t([[0.5], [0.1], [-0.8], [0.3]])
        grads = _backchain_grads(m, X, Y)
        oracle = _oracle_params(m, X, Y)
        assert len(oracle) == 2 * 3 + 3 + 3 + 3 + 3 * 1 + 1   # W1+b1+γ+β+W2+b2 = 19
        for (li, wname, path), num in oracle:
            ana = grads[(li, wname)]
            got = _getp(ana, path)
            assert abs(got - num) < 2e-5 * max(1.0, abs(num)), \
                f"L{li}.{wname}{path}: 解析 {got} vs 神谕 {num}"

    def test_conv2d_oracle_weights_and_input_grads(self):
        c = ai.Conv2D(1, 1, kernel_size=2, stride=1, padding=1)
        c.weight.data = [[[[0.3, -0.2], [0.5, 0.1]]]]
        c.bias.data = [0.25]
        m = ai.Sequential(); m.add(c)
        X = ai.Tensor(data=[[[1.0, -0.5, 0.2], [0.7, 0.1, -0.3], [0.0, 0.6, 0.9]]],
                      shape=(1, 3, 3))
        Y = ai.Tensor(data=[[[0.4, 0.0, -0.2, 0.1], [0.2, 0.5, -0.1, 0.3],
                             [0.0, -0.4, 0.2, 0.6], [0.1, 0.2, 0.0, -0.3]]],
                      shape=(1, 4, 4))
        out = m.forward(X).data
        n = 16
        dout = _deep_diff(out, Y.data, n)
        din = c.backward(dout)
        # 1) 参数神谕：dW 4 元素 + db 1 元素
        for (li, wname, path), num in _oracle_params(m, X, Y):
            w = c.weight if wname == "weight" else c.bias
            assert abs(_getp(w.grad.data, path) - num) < 2e-5 * max(1.0, abs(num))
        # 2) 输入梯度回流：dIn 9 元素逐一对拍 ∂loss/∂in
        xin = X.data
        for path, val in list(_paths(xin)):
            _setp(xin, path, val + 1e-5)
            hp = _mse_any(c.forward(X).data, Y.data)
            _setp(xin, path, val - 1e-5)
            hm = _mse_any(c.forward(X).data, Y.data)
            _setp(xin, path, val)
            num = (hp - hm) / (2e-5)
            got = _getp(din, path)
            assert abs(got - num) < 2e-5 * max(1.0, abs(num)), f"dIn{path}: {got} vs {num}"

    def test_conv2d_oracle_stride2_multichannel(self):
        # 另一套窗位回流几何（s=2, pad=1, 2 通道输出）封死 stride/pad 分支
        c = ai.Conv2D(1, 2, kernel_size=2, stride=2, padding=1)
        c.weight.data = [[[[0.2, 0.4], [-0.3, 0.1]]], [[[0.5, -0.2], [0.3, 0.6]]]]
        c.bias.data = [0.1, -0.1]
        m = ai.Sequential(); m.add(c)
        rng = random.Random(7)
        xin = [[[round(rng.uniform(-1, 1), 2) for _ in range(4)] for _ in range(4)]]
        X = ai.Tensor(data=xin, shape=(1, 4, 4))
        # 输出几何：h_out=(4+2-2)//2+1=3 → 目标须为 2×3×3
        yin = [[[round(rng.uniform(-1, 1), 2) for _ in range(3)] for _ in range(3)]
               for _ in range(2)]
        Y = ai.Tensor(data=yin, shape=(2, 3, 3))
        out = m.forward(X).data
        n = len([1 for _ in _paths(out)])
        din = c.backward(_deep_diff(out, Y.data, n))
        checked = 0
        for (li, wname, path), num in _oracle_params(m, X, Y):
            base = c.weight.grad.data if wname == "weight" else c.bias.grad.data
            assert abs(_getp(base, path) - num) < 2e-5 * max(1.0, abs(num))
            checked += 1
        assert checked == 2 * 1 * 4 + 2                     # 10 个参数元素
        for path, val in list(_paths(xin)):
            _setp(xin, path, val + 1e-5)
            hp = _mse_any(c.forward(X).data, Y.data)
            _setp(xin, path, val - 1e-5)
            hm = _mse_any(c.forward(X).data, Y.data)
            _setp(xin, path, val)
            assert abs(_getp(din, path) - (hp - hm) / 2e-5) < 2e-5
        # 输出几何：h_out=(4+2-2)//2+1=3 → dIn 保持输入形状 1×4×4
        assert len(din) == 1 and len(din[0]) == 4 and len(din[0][0]) == 4
        assert len(out[0]) == 3 and len(out) == 2

    # ── 训练链落地（证明反向输出真接进优化器环） ──

    def test_train_step_with_batchnorm_memorizes(self):
        random.seed(2026)
        m = ai.Sequential()
        m.add(ai.Linear(2, 4)); m.add(ai.BatchNorm(4)); m.add(ai.Linear(4, 1))
        m.compile(ai.MSELoss(), ai.Adam(m.parameters, lr=0.05))
        X = _t([[0.2, -0.3], [0.7, 0.1], [-0.5, 0.9], [0.4, 0.4]])
        # 目标取线性可表示的 Y = 0.6·x0 + 0.4·x1：Linear+BN 的特征张成空间
        # 含 span{1, x0c, x1c}，此目标落在其中 → 全局最小可达 loss→0；
        # （任意 Y 对 2 维输入线性模型不可达，残余是真约束极小，非 bug）
        Y = _t([[0.0], [0.46], [0.06], [0.4]])
        hist = [m.train_step(X, Y) for _ in range(800)]
        assert all(math.isfinite(h) for h in hist)
        assert hist[-1] < 1e-6 and hist[400] < hist[0] / 100

    def test_train_step_conv2d_reduces_loss(self):
        m = ai.Sequential()
        c = ai.Conv2D(1, 1, kernel_size=2, stride=1, padding=0)
        c.weight.data = [[[[0.3, 0.1], [0.2, 0.4]]]]; c.bias.data = [0.1]
        m.add(c)
        m.compile(MSEAnyLoss(), ai.Adam(m.parameters, lr=0.05))
        X = ai.Tensor(data=[[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]]],
                      shape=(1, 3, 3))
        Y = ai.Tensor(data=[[[0.5, 1.0], [1.5, 2.0]]], shape=(1, 2, 2))
        hist = [m.train_step(X, Y) for _ in range(400)]
        assert all(math.isfinite(h) for h in hist)
        assert hist[-1] < hist[0] / 100


def _getp(data, path):
    """按路径取嵌套元素（与 _setp 对称）。"""
    for p in path:
        data = data[p]
    return data


# ============================================================
# 9. A1+A2：save/load 覆盖 BN・Conv（含未知层显式拒绝）
#    与 BN eval/训练态翻转（EMA 手算、级联翻转、训推不漂移）
# ============================================================

class TestSaveLoadModeFlip:

    def test_save_rejects_unsupported_layer_explicitly(self):
        # 封死历史病理：未知层 save 静默丢参数、load 才崩
        import tempfile, os
        m = ai.Sequential()
        m.add(ai.Linear(2, 2))
        junk = ai.Layer("custom_widget")
        m.add(junk)
        with tempfile.TemporaryDirectory() as td:
            with pytest.raises(ValueError):
                m.save(os.path.join(td, "x.json"))

    def test_batchnorm_roundtrip_exact(self):
        import tempfile, os
        bn = ai.BatchNorm(3, momentum=0.2, eps=1e-4)
        bn.weight.data = [1.1, 0.9, 1.0]
        bn.bias.data = [0.05, -0.05, 0.0]
        for _ in range(3):
            bn.forward(_t([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]))
        m = ai.Sequential("bnet"); m.add(bn)
        Xq = _t([[2.5, 1.5, 3.5]])
        bn.eval()
        before = bn.forward(Xq).data
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "bn.json")
            m.save(p)
            m2 = ai.Sequential(); m2.load(p)
            b2 = m2.layers[0]
            assert b2.weight.data == bn.weight.data          # γ 逐位往返
            assert b2.bias.data == bn.bias.data              # β
            assert b2.running_mean == bn.running_mean        # EMA 态也往返
            assert b2.running_var == bn.running_var
            assert b2.momentum == bn.momentum and b2.eps == bn.eps
            b2.eval()
            assert b2.forward(Xq).data == before             # 推理不变

    def test_conv2d_roundtrip_exact_and_trainable(self):
        import tempfile, os
        random.seed(777)
        c = ai.Conv2D(2, 3, kernel_size=3, stride=2, padding=1)
        xin = ai.Tensor(data=[[[1.0, 2.0, 3.0, 4.0], [0.5, 1.5, 2.5, 3.5],
                               [2.0, 1.0, 0.0, 1.0], [3.0, 2.0, 1.0, 0.0]],
                              [[0.1, 0.2, 0.3, 0.4]] * 4], shape=(2, 4, 4))
        before_w = [[[[v for v in r] for r in ic] for ic in oc] for oc in c.weight.data]
        before_out = c.forward(xin).data
        m = ai.Sequential("cnet"); m.add(c)
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "conv.json")
            m.save(p)
            m2 = ai.Sequential(); m2.load(p)
            c2 = m2.layers[0]
            assert c2.weight.data == before_w                # 4D 权重逐位往返
            assert c2.bias.data == c.bias.data
            assert (c2.in_channels, c2.out_channels, c2.kernel_size,
                    c2.stride, c2.padding) == (2, 3, 3, 2, 1)  # 几何参数往返
            assert c2.forward(xin).data == before_out        # 推理不变
            # load 后真接入可训练环：参数表/反传/优化器可用
            m2.compile(MSEAnyLoss(), ai.Adam(m2.parameters, lr=0.01))
            y = ai.Tensor(data=before_out, shape=(3, 2, 2))
            loss0 = m2.train_step(xin, y)
            assert math.isfinite(loss0) and loss0 < 1e-24     # 目标即自身输出→残差≈0
            assert c2.weight.grad is not None                 # 反传真落梯度

    def test_running_stats_ema_two_batches_hand(self):
        bn = ai.BatchNorm(1, momentum=0.5, eps=0.0)
        bn.forward(_t([[0.0], [2.0]]))        # batch mean=1 var=1；running 初值 m=0, v=1
        assert _close(bn.running_mean, [0.5], 1e-12)          # 0.5*0 + 0.5*1
        assert _close(bn.running_var, [1.0], 1e-12)           # 0.5*初值1 + 0.5*1
        bn.forward(_t([[4.0], [8.0]]))        # batch mean=6 var=4
        assert _close(bn.running_mean, [0.5 * 0.5 + 0.5 * 6.0], 1e-12)
        assert _close(bn.running_var, [0.5 * 1.0 + 0.5 * 4.0], 1e-12)

    def test_model_eval_train_cascade(self):
        m = ai.Sequential()
        m.add(ai.Linear(2, 2)); m.add(ai.BatchNorm(2)); m.add(ai.Dropout(0.5))
        m.add(ai.ReLU())
        m.eval()
        assert all(not layer.training for layer in m.layers)
        m.train()
        assert all(layer.training for layer in m.layers)

    def test_train_then_eval_predict_stable(self):
        # 全批训练下 running 收敛到 batch 统计（(1-momentum)^n→0），eval 记忆不漂移
        random.seed(2026)
        m = ai.Sequential()
        m.add(ai.Linear(2, 4)); m.add(ai.BatchNorm(4)); m.add(ai.Linear(4, 1))
        m.compile(ai.MSELoss(), ai.Adam(m.parameters, lr=0.05))
        X = _t([[0.2, -0.3], [0.7, 0.1], [-0.5, 0.9], [0.4, 0.4]])
        Y = _t([[0.0], [0.46], [0.06], [0.4]])
        for _ in range(800):
            m.train_step(X, Y)
        m.eval()
        assert m.evaluate(X, Y)["loss"] < 1e-4    # 推理态（running）仍记得训练目标


# ============================================================
# 10. A3：Dropout 训练链实战——误用拒绝、冻结掩码神谕、
#     逐变掩码统计健康、含 Dropout 的真实收敛
# ============================================================

class TestDropoutTrainingChain:

    def test_dropout_backward_before_forward_rejected(self):
        d = ai.Dropout(p=0.5)
        with pytest.raises(RuntimeError):
            d.backward([[1.0, 2.0]])              # 无掩码现场：误用显式拒绝

    def test_dropout_seed_freezes_mask_across_calls(self):
        # 显式契约：seed 非 None → 掩码冻结（每次 forward 同掩码，可复现现场）；
        # seed=None → 掩码逐步推进（训练语义，受全局 random.seed 控制）
        x = _t([[1.0, 2.0, 3.0, 4.0, 5.0, 6.0]])
        d = ai.Dropout(p=0.5, seed=11)
        o1 = d.forward(x).data
        o2 = d.forward(x).data
        assert o1 == o2                            # 冻结：同实例两次调用同掩码
        dn = ai.Dropout(p=0.5)
        random.seed(9)
        a1 = dn.forward(x).data
        a2 = dn.forward(x).data
        assert a1 != a2                            # 推进：seed=None 逐步变掩码

    def test_dropout_mask_keep_rate_statistical(self):
        # 掩码真随机的统计健康：200 次×20 元素，keep 率应贴近 1−p（固定假掩码会在此穿帮）
        random.seed(2026)
        d = ai.Dropout(p=0.5)
        x = _t([[1.0] * 20 for _ in range(10)])
        kept = total = 0
        for _ in range(200):
            out = d.forward(x).data
            for row in out:
                for v in row:
                    total += 1
                    kept += 1 if v != 0.0 else 0
        rate = kept / total
        assert 0.44 < rate < 0.56                  # 二项波动内（n=200×200=40000，σ≈0.0025）

    def test_dropout_frozen_mask_oracle_all_params(self):
        # 冻结掩码下含 Dropout 的两层链：全 13 参数元素中心差分对拍
        random.seed(6060)
        m = ai.Sequential()
        m.add(ai.Linear(2, 3)); m.add(ai.Dropout(p=0.4, seed=7))
        m.add(ai.Linear(3, 1))
        m.compile(ai.MSELoss(), ai.Adam(m.parameters, lr=0.1))
        X = _t([[0.3, -0.7], [0.9, 0.5], [0.0, 1.0], [-0.4, 0.2]])
        Y = _t([[0.5], [0.1], [-0.8], [0.3]])
        grads = _backchain_grads(m, X, Y)
        oracle = _oracle_params(m, X, Y)
        assert len(oracle) == 2 * 3 + 3 + 3 * 1 + 1        # W1+b1+W2+b2 = 13
        for (li, wname, path), num in oracle:
            got = _getp(grads[(li, wname)], path)
            assert abs(got - num) < 2e-5 * max(1.0, abs(num)), \
                f"L{li}.{wname}{path}: 解析 {got} vs 神谕 {num}"

    def test_train_step_with_dropout_converges(self):
        # 实战：seed=None 逐步随机掩码下记忆线性目标。如实登记：训练期 loss 的
        # forward 带掩码，存在噪声地板（探针实测 tail 均值~1e-3 量级而权重已近优），
        # 故锁尾窗均值降一个数量级以上而非绝对阈值。
        random.seed(303)
        m = ai.Sequential()
        m.add(ai.Linear(2, 8)); m.add(ai.Dropout(p=0.25)); m.add(ai.Linear(8, 1))
        m.compile(ai.MSELoss(), ai.Adam(m.parameters, lr=0.05))
        X = _t([[0.2, -0.3], [0.7, 0.1], [-0.5, 0.9], [0.4, 0.4]])
        Y = _t([[0.0], [0.46], [0.06], [0.4]])              # 线性可表示目标
        hist = [m.train_step(X, Y) for _ in range(2000)]
        assert all(math.isfinite(h) for h in hist)
        tail = sum(hist[-200:]) / 200
        assert tail < hist[0] / 20                   # 掩码噪声地板下仍大幅收敛
