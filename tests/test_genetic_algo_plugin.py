# -*- coding: utf-8 -*-
"""阶段 3 · genetic_algo 行为级三锁（对齐 ai_framework 口径）。

原缺陷（审计 #16）：max_gen=0 裸抛 UnboundLocalError、空种群 max() 崩溃、
len-1 个体交叉 randint(1,0) 崩溃、全零适应度静默偏袒末位、负适应度/NaN
进轮盘赌静默错算、n_iterations=0 静默返回 {}/-inf、注册层平铺多参函数
（Matha f(a,b) 两侧均为 f(a)(b)，平铺形态首参即提前求值）。本轮直修后
以三类锁封死回退：

  1. **手算对拍**：退化轮盘/单点交叉/位翻转/累计边界/精英排序/模板替换/
     空白折叠/随机搜索最优，全部独立手算逐位比对；
  2. **收敛闭环**：ones-count 目标从随机/全零种群找回全 1 最优，
     神经进化与超参数搜索同口径闭环；
  3. **显式拒绝**：非法种群/参数/适应度/回调一律 ValueError——
     Matha 闭包（VM Closure / interp "__closure__" 元组）不可跨语言调用，
     显式拒绝不静默假算。

另有注册契约锁（manifest 符号面不漂移、柯里化形态）与主执行链端到端
（干净子进程经 exec_api 懒加载真算/拒绝，遵「sys.modules 断言起子进程」纪律）。
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

from src.domains.genetic_algo import (
    _crossover,
    _genetic_algo_symtab_names,
    _mutate,
    _register_genetic_algo,
    _roulette_select,
    code_generation,
    code_optimizer,
    elitism_preserve,
    ga_evolve,
    hyperparameter_search,
    nesma_estimate,
    neuro_evolve,
)

MANIFEST = ROOT / "src" / "domains" / "manifest.json"


def _ones_ratio(ind):
    return sum(ind) / len(ind)


# ============================================================
# 1. 手算对拍
# ============================================================

class TestHandComputedParity:

    def test_degenerate_roulette_breeds_deterministically(self):
        # fitness [0.5, 0.0] → probs [1, 0]：亲本恒为 [1,1]；零交叉零变异
        # → 子代全 [1,1]。全程无随机依赖，无需种子。
        r = ga_evolve([[1, 1], [0, 0]], lambda ind: sum(ind) / (2 * len(ind)),
                      pop_size=2, max_gen=3, mutation_rate=0.0, crossover_rate=0.0)
        assert r["best_individual"] == [1, 1]
        assert r["best_fitness"] == 0.5
        assert r["generations"] == 3
        assert r["population"] == [[1, 1], [1, 1]]

    def test_early_stop_on_initial_optimum(self):
        # 初始代 best_fit=1.0 → 第 0 代即 break：generations=1，种群不繁殖
        r = ga_evolve([[1, 1], [0, 0]], _ones_ratio, pop_size=2, max_gen=5)
        assert r["generations"] == 1
        assert r["best_fitness"] == 1.0
        assert r["best_individual"] == [1, 1]
        assert r["population"] == [[1, 1], [0, 0]]

    def test_single_generation_breeding(self):
        # fitness [0.25, 0.0] → probs [1, 0]；pop_size=1 → 子代恰一个 [1,0]
        r = ga_evolve([[1, 0], [0, 0]], lambda ind: sum(ind) / (2 * len(ind)),
                      pop_size=1, max_gen=1, mutation_rate=0.0, crossover_rate=0.0)
        assert r["population"] == [[1, 0]]
        assert r["best_fitness"] == 0.25
        assert r["generations"] == 1

    def test_all_zero_fitness_uniform_selection(self, monkeypatch):
        # 旧缺陷：全零适应度 probs 全 0 → 轮盘恒落末位。修复后均匀选择：
        # r=0.25 → 累计 0.5 >= 0.25 → 选第一个体 [1,0]（末位是 [0,1]）。
        monkeypatch.setattr(random, "random", lambda: 0.25)
        r = ga_evolve([[1, 0], [0, 1]], lambda ind: 0,
                      pop_size=1, max_gen=1, mutation_rate=0.0, crossover_rate=0.0)
        assert r["population"] == [[1, 0]]
        assert r["best_fitness"] == 0

    def test_crossover_single_point_semantics(self, monkeypatch):
        monkeypatch.setattr(random, "randint", lambda a, b: 2)
        assert _crossover([1, 1, 1, 1], [0, 0, 0, 0]) == [1, 1, 0, 0]

    def test_crossover_length_one_noop(self, monkeypatch):
        # 旧缺陷：randint(1, 0) ValueError。修复后不调 randint，直接复制。
        def _boom(a, b):
            raise AssertionError("len-1 交叉不应抽取交叉点")
        monkeypatch.setattr(random, "randint", _boom)
        parent = [1]
        child = _crossover(parent, [0])
        assert child == [1] and child is not parent

    def test_mutate_bitflip_boundary(self, monkeypatch):
        # 判定为 draw > rate 保留，否则翻转：0.9 保留 1；0.1 翻转 0→1；
        # 0.5 == rate 不满足 > → 翻转 1→0。
        monkeypatch.setattr(random, "random", iter([0.9, 0.1, 0.5]).__next__)
        assert _mutate([1, 0, 1], 0.5) == [1, 1, 0]

    @pytest.mark.parametrize("draw,expected_idx", [(0.5, 0), (0.6, 1), (0.99, 2)])
    def test_roulette_cumulative_boundary(self, monkeypatch, draw, expected_idx):
        # probs [0.5, 0.3, 0.2]：累计 0.5/0.8/1.0，判定 >=（0.5 恰好落首格）
        monkeypatch.setattr(random, "random", lambda: draw)
        pop = [[1, 0], [0, 1], [1, 1]]
        assert _roulette_select(pop, [0.5, 0.3, 0.2]) == pop[expected_idx]

    def test_elitism_order_and_count(self):
        pop = [[1, 0], [1, 1], [0, 0]]
        assert elitism_preserve(pop, sum, elite_count=2) == [[1, 1], [1, 0]]

    def test_elitism_count_exceeds_population(self):
        pop = [[1, 0], [1, 1], [0, 0]]
        assert elitism_preserve(pop, sum, elite_count=10) == [[1, 1], [1, 0], [0, 0]]

    def test_elitism_stable_on_ties(self):
        pop = [[1, 0], [0, 1]]
        assert elitism_preserve(pop, sum, elite_count=2) == [[1, 0], [0, 1]]

    @pytest.mark.parametrize("loc,expected", [(0, 0.0), (1, 0.5), (7, 3.5), (100, 50.0)])
    def test_nesma_hand_values(self, loc, expected):
        assert nesma_estimate(loc) == expected

    def test_code_generation_substitution(self):
        out = code_generation("func {name}(x) = x + {k}", {"name": "f", "k": 3})
        assert out == "func f(x) = x + 3"

    def test_code_generation_unmatched_placeholder_preserved(self):
        assert code_generation("x={v} y={missing}", {"v": 2}) == "x=2 y={missing}"

    def test_code_optimizer_whitespace(self):
        assert code_optimizer("def  f():\n\n    return   1") == "def f():\n return 1"
        assert code_optimizer("  a  b  ") == "a b"

    def test_hyperparameter_search_finds_optimum(self):
        random.seed(0)
        r = hyperparameter_search({"a": [1, 2, 3], "b": 10},
                                  lambda p: p["a"] + p["b"], n_iterations=50)
        assert r["best_params"] == {"a": 3, "b": 10}
        assert r["best_score"] == 13

    def test_hyperparameter_constant_passthrough(self):
        r = hyperparameter_search({"x": 5}, lambda p: p["x"] * 2, n_iterations=3)
        assert r == {"best_params": {"x": 5}, "best_score": 10}


# ============================================================
# 2. 收敛闭环
# ============================================================

class TestConvergenceClosedLoop:

    def test_ga_converges_to_all_ones(self):
        random.seed(42)
        pop = [[random.choice([0, 1]) for _ in range(8)] for _ in range(30)]
        r = ga_evolve(pop, _ones_ratio, pop_size=30, max_gen=100,
                      mutation_rate=0.05, crossover_rate=0.8)
        assert r["best_fitness"] == 1.0
        assert r["best_individual"] == [1] * 8
        assert r["generations"] <= 100
        assert len(r["population"]) == 30
        assert all(len(ind) == 8 and all(b in (0, 1) for b in ind)
                   for ind in r["population"])

    def test_ga_converges_from_all_zeros(self):
        # 最坏起点：全零种群（初始全零适应度走均匀选择），靠变异+选择爬坡
        random.seed(123)
        r = ga_evolve([[0] * 8 for _ in range(30)], _ones_ratio,
                      pop_size=30, max_gen=300, mutation_rate=0.1, crossover_rate=0.8)
        assert r["best_fitness"] == 1.0
        assert r["best_individual"] == [1] * 8

    def test_neuro_evolve_closed_loop(self):
        random.seed(7)
        r = neuro_evolve(6, _ones_ratio, pop_size=30, max_gen=100)
        assert r["best_fitness"] == 1.0
        assert r["best_individual"] == [1] * 6
        assert len(r["population"]) == 30
        assert all(len(ind) == 6 and all(b in (0, 1) for b in ind)
                   for ind in r["population"])

    def test_hyperparameter_converges_to_target(self):
        random.seed(1)
        r = hyperparameter_search({"lr": [0.1, 0.01, 0.001]},
                                  lambda p: -abs(p["lr"] - 0.01), n_iterations=100)
        assert r["best_params"] == {"lr": 0.01}
        assert r["best_score"] == 0.0


# ============================================================
# 3. 显式拒绝矩阵
# ============================================================

class TestExplicitRejection:

    @pytest.mark.parametrize("pop", [
        [], None, "abc", [None], [[]], [[1, 0], [1]],
        [[2, 0]], [[0.5, 1]], [[True, 0]], [[0, 1], [1, 0, 1]],
    ])
    def test_ga_rejects_bad_population(self, pop):
        with pytest.raises(ValueError):
            ga_evolve(pop, _ones_ratio)

    @pytest.mark.parametrize("kwargs", [
        {"pop_size": 0}, {"pop_size": -1}, {"pop_size": 1.5}, {"pop_size": True},
        {"max_gen": 0}, {"max_gen": -1}, {"max_gen": "10"},
        {"mutation_rate": -0.1}, {"mutation_rate": 1.1}, {"mutation_rate": "x"},
        {"crossover_rate": -0.1}, {"crossover_rate": 1.1},
    ])
    def test_ga_rejects_bad_params(self, kwargs):
        with pytest.raises(ValueError):
            ga_evolve([[1, 0]], _ones_ratio, **kwargs)

    @pytest.mark.parametrize("fn", [
        None, 42, "x", ("__closure__", ["i"], None, {}), object(),
    ])
    def test_ga_rejects_non_callable_fitness(self, fn):
        with pytest.raises(ValueError, match="跨语言回调"):
            ga_evolve([[1, 0]], fn)

    @pytest.mark.parametrize("fit", [-1, float("nan"), float("inf"), "1", True, None])
    def test_ga_rejects_bad_fitness_values(self, fit):
        with pytest.raises(ValueError):
            ga_evolve([[1, 0]], lambda ind: fit)

    @pytest.mark.parametrize("args", [
        ([], sum, 2), ([[1, 0]], None, 2), ([[1, 0]], sum, 0),
        ([[1, 0]], sum, -1), ([[1, 0]], sum, 1.5),
        ([[1, 0]], lambda ind: -1, 1),
    ])
    def test_elitism_rejects(self, args):
        with pytest.raises(ValueError):
            elitism_preserve(*args)

    @pytest.mark.parametrize("args", [
        (0, sum), (-1, sum), (1.5, sum), (True, sum), (4, None),
        (4, sum, 0), (4, sum, 50, 0),
    ])
    def test_neuro_evolve_rejects(self, args):
        with pytest.raises(ValueError):
            neuro_evolve(*args)

    @pytest.mark.parametrize("loc", [-1, 1.5, "100", None, True])
    def test_nesma_rejects(self, loc):
        with pytest.raises(ValueError):
            nesma_estimate(loc)

    @pytest.mark.parametrize("args", [(123, {}), ("x", []), ("x", None)])
    def test_code_generation_rejects(self, args):
        with pytest.raises(ValueError):
            code_generation(*args)

    @pytest.mark.parametrize("code", [123, None, []])
    def test_code_optimizer_rejects(self, code):
        with pytest.raises(ValueError):
            code_optimizer(code)

    @pytest.mark.parametrize("args", [
        ({}, sum), ([], sum), ({"a": []}, sum),
        ({"a": [1]}, None), ({"a": [1]}, sum, 0),
        ({"a": [1]}, sum, -1), ({"a": [1]}, sum, 1.5),
        ({"a": [1]}, lambda p: "x"), ({"a": [1]}, lambda p: float("nan")),
        ({"a": [1]}, lambda p: True),
    ])
    def test_hyperparameter_search_rejects(self, args):
        with pytest.raises(ValueError):
            hyperparameter_search(*args)


# ============================================================
# 4. 注册契约（manifest 符号面 + 柯里化形态）
# ============================================================

class TestRegistrationContract:

    def test_manifest_symbols_match_exports(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        plugins = (manifest["plugins"]
                   if isinstance(manifest, dict) and "plugins" in manifest
                   else manifest)
        entry = next(p for p in plugins
                     if p.get("module") == "src.domains.genetic_algo")
        builtins: dict = {}
        _register_genetic_algo(builtins)
        assert set(entry["symbols"]) == set(_genetic_algo_symtab_names())
        assert set(entry["symbols"]) == set(builtins)

    def test_curried_single_arg_forms(self):
        b: dict = {}
        _register_genetic_algo(b)
        assert b["NESMA估算"](100) == 50.0
        assert b["代码优化"]("a  b") == "a b"

    def test_curried_multi_arg_forms(self):
        b: dict = {}
        _register_genetic_algo(b)
        assert b["代码生成"]("x={v}")({"v": 2}) == "x=2"
        assert b["精英保留"]([[1, 0], [1, 1], [0, 0]])(sum)(2) == [[1, 1], [1, 0]]
        r = b["超参数搜索"]({"x": 5})(lambda p: p["x"] * 2)(3)
        assert r == {"best_params": {"x": 5}, "best_score": 10}
        r = b["遗传算法进化"]([[1, 1], [0, 0]])(_ones_ratio)(2)(5)(0.0)(0.0)
        assert r["best_fitness"] == 1.0 and r["generations"] == 1

    def test_curried_neuro_evolve_form(self):
        b: dict = {}
        _register_genetic_algo(b)
        random.seed(7)
        r = b["神经进化"](6)(_ones_ratio)(30)(100)
        assert r["best_fitness"] == 1.0

    def test_partial_application_returns_callable(self):
        b: dict = {}
        _register_genetic_algo(b)
        partial = b["遗传算法进化"]([[1, 0]])(_ones_ratio)
        assert callable(partial) and not isinstance(partial, dict)

    @pytest.mark.parametrize("fn", [None, 0, ("__closure__", ["i"], None, {})])
    def test_callback_rejected_at_boundary(self, fn):
        b: dict = {}
        _register_genetic_algo(b)
        with pytest.raises(ValueError, match="跨语言回调"):
            b["遗传算法进化"]([[1, 0]])(fn)(1)(1)(0.0)(0.0)

    def test_registered_forms_reject_bad_params(self):
        b: dict = {}
        _register_genetic_algo(b)
        with pytest.raises(ValueError):
            b["NESMA估算"](-1)
        with pytest.raises(ValueError):
            b["精英保留"]([])(sum)(1)


# ============================================================
# 5. 主执行链端到端（干净子进程，懒加载真算/拒绝）
# ============================================================

_E2E_SNIPPET = """
import json, sys
sys.path.insert(0, %r)
from src.kernel import exec_api
from src.plugin_api import get_resolver
src = '''@：【加载领域】，genetic_algo
#1：[NESMA估算(100)]
#1：[代码优化("a  b")]
'''
out = exec_api.run(src)
assert out == [50.0, "a b"], out
assert "genetic_algo" in get_resolver().loaded()
print(json.dumps({"out": out}))
""" % str(ROOT)


def test_main_chain_lazy_loads_and_computes_for_real():
    proc = subprocess.run([sys.executable, "-c", _E2E_SNIPPET],
                          cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=180)
    assert proc.returncode == 0, proc.stderr[-800:]
    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    assert payload["out"] == [50.0, "a b"]


_E2E_REJECT_SNIPPET = """
import sys
sys.path.insert(0, %r)
from src.kernel import exec_api
src = '''@：【加载领域】，genetic_algo
#1：[NESMA估算(-1)]
'''
try:
    exec_api.run(src)
except ValueError as e:
    assert "非负整数" in str(e)
    print("REJECTED")
else:
    raise AssertionError("负 LOC 假成功复活：未抛 ValueError")
""" % str(ROOT)


def test_main_chain_surfaces_honest_rejection():
    proc = subprocess.run([sys.executable, "-c", _E2E_REJECT_SNIPPET],
                          cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=180)
    assert proc.returncode == 0, proc.stderr[-800:]
    assert "REJECTED" in proc.stdout


_E2E_CALLBACK_SNIPPET = """
import sys
sys.path.insert(0, %r)
from src.kernel import exec_api
src = '''@：【加载领域】，genetic_algo
#1：[精英保留([[1, 0]], 0, 1)]
'''
try:
    exec_api.run(src)
except ValueError as e:
    assert "跨语言回调" in str(e)
    print("REJECTED")
else:
    raise AssertionError("非 callable 适应度假成功复活：未抛 ValueError")
""" % str(ROOT)


def test_main_chain_rejects_non_callable_fitness():
    proc = subprocess.run([sys.executable, "-c", _E2E_CALLBACK_SNIPPET],
                          cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=180)
    assert proc.returncode == 0, proc.stderr[-800:]
    assert "REJECTED" in proc.stdout