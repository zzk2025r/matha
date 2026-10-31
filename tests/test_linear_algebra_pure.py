"""纯 Python 线代后端回归锁（阶段 3：numpy SVD 分支移除后的能力证明）。

`svd_decompose` 原先优先走 `np.linalg.svd`，装不上才退回纯 Python —— 而那条
退回路径（无 deflation 的幂迭代）对非对称矩阵是错的。现在主路是单侧 Jacobi，
本文件锁定三件事：**重构正确**、**奇异值降序且与已知值一致**、**确定性**。
"""
from __future__ import annotations

import pytest

from src.stdlib.linear_algebra import (
    Matrix, _svd_power_iteration, svd_decompose, svd_decompose_sparse,
)


def _mul(X, Y):
    cols = len(Y[0])
    inner = len(Y)
    return [[sum(X[i][t] * Y[t][j] for t in range(inner)) for j in range(cols)]
            for i in range(len(X))]


def _svd_check(data):
    A = Matrix(data)
    U, S, Vt = svd_decompose(A)
    m, n = A.rows, A.cols
    recon = _mul(_mul(U.data, S.data), Vt.data)
    err = max(abs(A.data[i][j] - recon[i][j]) for i in range(m) for j in range(n))
    assert err < 1e-8, f"U·S·Vᵗ ≠ A（误差 {err}）"
    # U 正交
    gram = _mul(U.data, [[U.data[r][c] for r in range(m)] for c in range(m)])
    orth = max(abs(gram[i][j] - (1.0 if i == j else 0.0))
               for i in range(m) for j in range(m))
    assert orth < 1e-8, f"U 非正交（{orth}）"
    sig = [S.data[i][i] for i in range(min(m, n))]
    assert all(sig[i] >= sig[i + 1] - 1e-12 for i in range(len(sig) - 1)), sig
    return sig


CASES = [
    [[1.0, 2.0], [3.0, 4.0]],
    [[1.0, 0.0, 0.0], [0.0, 2.0, 0.0], [0.0, 0.0, -3.0]],
    [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]],       # 秩亏
    [[2.0, 1.0], [1.0, 2.0], [0.0, 0.0]],                       # 高瘦
    [[3.0, 0.0, 0.0, 0.0], [0.0, 2.0, 0.0, 0.0]],               # 扁矩阵
    [[0.0, 0.0], [0.0, 0.0]],                                   # 零矩阵
    [[5.0]],
]

# 与 numpy.linalg.svd(compute_uv=False) 的实测奇异值对拍
EXPECTED = {
    0: [5.464985704219043, 0.3659661906262573],
    1: [3.0, 2.0, 1.0],
    2: [16.848103352984354, 1.068369515996825, 4.4068855e-15],
    3: [3.0, 1.0],
    4: [3.0, 2.0],
    5: [0.0, 0.0],
    6: [5.0],
}


@pytest.mark.parametrize("idx,data", list(enumerate(CASES)))
def test_svd_reconstruction_orthogonality_and_order(idx, data):
    sig = _svd_check(data)
    want = EXPECTED[idx]
    for got, exp in zip(sig, want):
        assert abs(got - exp) < 1e-8, f"{idx}: {sig} vs {want}"


def test_svd_is_deterministic():
    data = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]
    a = svd_decompose(Matrix(data))[1].data
    b = svd_decompose(Matrix([row[:] for row in data]))[1].data
    assert a == b


def test_power_iteration_deflates():
    """加固点：第 2 个奇异值必须与第 1 个不同（旧版无 deflation 会重复）。"""
    A = Matrix([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
    U, S, Vt = _svd_power_iteration(A)
    s0, s1 = S.data[0][0], S.data[1][1]
    assert abs(s0 - 9.525518) < 1e-5, s0
    assert abs(s1 - 0.514301) < 1e-5, s1
    assert s0 > s1 > 0


def test_sparse_path_still_works():
    """稀疏迭代路：σ 必须是真实奇异值（旧实现恒返回 1.0）。"""
    A = Matrix([[0.0, 3.0, 0.0], [0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
    U, S, Vt = svd_decompose_sparse(A, max_iter=300)
    sig = [S.data[i][i] for i in range(min(A.rows, A.cols))]
    assert abs(sig[0] - 3.0) < 1e-6, sig
    assert abs(sig[1] - 1.0) < 1e-6, sig
    assert sig[2] == 0.0, sig
    recon = _mul(_mul(U.data, S.data), Vt.data)
    err = max(abs(A.data[i][j] - recon[i][j])
              for i in range(A.rows) for j in range(A.cols))
    assert err < 1e-8, err


def test_no_numpy_in_linear_algebra():
    """核心线代模块不得再 import numpy（去依赖红线）。"""
    import pathlib
    import re

    src = pathlib.Path("src/stdlib/linear_algebra.py").read_text(encoding="utf-8")
    assert not re.search(r"^\s*(import numpy|from numpy)", src, re.M)
