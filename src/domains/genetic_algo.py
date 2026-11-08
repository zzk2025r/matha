"""
Matha 遗传算法与 AI 编写代码领域模块。

覆盖：
  1) 遗传算法核心（选择、交叉、变异）
  2) 神经进化（NEAT简化版）
  3) 自动代码生成
  4) 超参数搜索

边界口径（阶段 3 行为锁）：种群为等长非空二进制（int 0/1）个体；
适应度须为非负有限数值（轮盘赌）；适应度回调仅接受 Python 可调用对象——
Matha 闭包（VM Closure / interp "__closure__" 元组）不可跨语言调用，
一律显式拒绝，不静默假算。非法参数一律 ValueError。
"""
from __future__ import annotations

import math
import random
from collections.abc import Callable

# ============================================================
# 边界校验（显式拒绝，不静默假算）
# ============================================================

def _require_positive_int(name: str, value) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} 须为正整数：{value!r}")


def _require_rate(name: str, value) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
        raise ValueError(f"{name} 须在 [0, 1] 内：{value!r}")


def _require_fitness_fn(fitness_fn) -> None:
    if not callable(fitness_fn):
        raise ValueError("适应度函数须为 Python 可调用对象；"
                         "Matha 闭包暂不支持跨语言回调")


def _check_fitness(value) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"适应度须为数值：{value!r}")
    if value < 0:
        raise ValueError(f"适应度须非负（轮盘赌选择）：{value!r}")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"适应度须为有限数值：{value!r}")


def _validate_population(population) -> None:
    if not isinstance(population, list) or not population:
        raise ValueError("种群须为非空列表")
    width = None
    for i, ind in enumerate(population):
        if not isinstance(ind, list) or not ind:
            raise ValueError(f"第 {i + 1} 个个体须为非空列表")
        if any(type(bit) is not int or bit not in (0, 1) for bit in ind):
            raise ValueError(f"第 {i + 1} 个个体含非二进制基因（须为 int 0/1）")
        if width is None:
            width = len(ind)
        elif len(ind) != width:
            raise ValueError("个体长度须一致")


def _evaluate(population: list, fitness_fn: Callable) -> list:
    fitness = [fitness_fn(ind) for ind in population]
    for f in fitness:
        _check_fitness(f)
    return fitness


# ============================================================
# 遗传算法
# ============================================================

def ga_evolve(population: list[list[int]], fitness_fn: Callable,
              pop_size: int = 100, max_gen: int = 100,
              mutation_rate: float = 0.01, crossover_rate: float = 0.8) -> dict:
    """遗传算法主循环。非法参数/非法适应度显式抛 ValueError。"""
    _validate_population(population)
    _require_fitness_fn(fitness_fn)
    _require_positive_int("pop_size", pop_size)
    _require_positive_int("max_gen", max_gen)
    _require_rate("mutation_rate", mutation_rate)
    _require_rate("crossover_rate", crossover_rate)
    for gen in range(max_gen):
        # 评估适应度
        fitness = _evaluate(population, fitness_fn)
        best_idx = max(range(len(fitness)), key=lambda i: fitness[i])
        best_fit = fitness[best_idx]

        # 终止条件
        if best_fit >= 1.0:
            break

        # 选择（轮盘赌）；全零适应度退化为均匀选择，不偏袒末位
        total = sum(fitness)
        if total == 0:
            probs = [1.0 / len(fitness)] * len(fitness)
        else:
            probs = [f / total for f in fitness]

        # 繁殖新一代
        new_pop = []
        while len(new_pop) < pop_size:
            parent1 = _roulette_select(population, probs)
            parent2 = _roulette_select(population, probs)

            # 交叉
            if random.random() < crossover_rate:
                child = _crossover(parent1, parent2)
            else:
                child = parent1[:]

            # 变异
            child = _mutate(child, mutation_rate)
            new_pop.append(child)

        population = new_pop

    fitness = _evaluate(population, fitness_fn)
    best_idx = max(range(len(fitness)), key=lambda i: fitness[i])
    return {
        "best_individual": population[best_idx],
        "best_fitness": fitness[best_idx],
        "generations": gen + 1,
        "population": population,
    }


def _roulette_select(population: list, probs: list) -> list[int]:
    """轮盘赌选择。"""
    r = random.random()
    cumulative = 0.0
    for i, p in enumerate(probs):
        cumulative += p
        if cumulative >= r:
            return population[i][:]
    return population[-1][:]


def _crossover(parent1: list[int], parent2: list[int]) -> list[int]:
    """单点交叉；长度 ≤1 无交叉点，直接复制（不再 randint(1,0) 崩溃）。"""
    if len(parent1) <= 1:
        return parent1[:]
    point = random.randint(1, len(parent1) - 1)
    child = parent1[:point] + parent2[point:]
    return child


def _mutate(individual: list[int], rate: float) -> list[int]:
    """位翻转变异。"""
    return [bit if random.random() > rate else 1 - bit for bit in individual]


# ============================================================
# 精英保留
# ============================================================

def elitism_preserve(population: list[list[int]], fitness_fn: Callable, elite_count: int = 2) -> list[list[int]]:
    """精英保留（按适应度降序取前 elite_count 个；超出种群大小时取全部）。"""
    _validate_population(population)
    _require_fitness_fn(fitness_fn)
    _require_positive_int("elite_count", elite_count)
    fitness = _evaluate(population, fitness_fn)
    order = sorted(range(len(population)), key=lambda i: fitness[i], reverse=True)
    return [population[i] for i in order[:elite_count]]


# ============================================================
# 神经进化
# ============================================================

def neuro_evolve(genome_length: int, fitness_fn: Callable,
                 pop_size: int = 50, max_gen: int = 50) -> dict:
    """简化版神经进化（NEAT风格）：随机二进制种群 + ga_evolve。"""
    _require_positive_int("genome_length", genome_length)
    _require_fitness_fn(fitness_fn)
    _require_positive_int("pop_size", pop_size)
    _require_positive_int("max_gen", max_gen)
    population = [[random.choice([0, 1]) for _ in range(genome_length)] for _ in range(pop_size)]
    return ga_evolve(population, fitness_fn, pop_size, max_gen)


def nesma_estimate(lines_of_code: int) -> float:
    """NESMA 功能点估算（简化公式：约 0.5 FP/LOC）。"""
    if isinstance(lines_of_code, bool) or not isinstance(lines_of_code, int) or lines_of_code < 0:
        raise ValueError(f"lines_of_code 须为非负整数：{lines_of_code!r}")
    return lines_of_code * 0.5


# ============================================================
# 自动代码生成
# ============================================================

def code_generation(template: str, params: dict) -> str:
    """模板代码生成（{key} 替换；未匹配占位符原样保留）。"""
    if not isinstance(template, str):
        raise ValueError("template 须为字符串")
    if not isinstance(params, dict):
        raise ValueError("params 须为字典")
    result = template
    for key, value in params.items():
        result = result.replace(f"{{{key}}}", str(value))
    return result


def code_optimizer(code: str) -> str:
    """简单代码优化（字符串层面：折叠空白）。"""
    if not isinstance(code, str):
        raise ValueError("code 须为字符串")
    # 移除多余空白
    import re
    code = re.sub(r'\n\s*\n', '\n', code)
    code = re.sub(r'[ \t]+', ' ', code)
    return code.strip()


# ============================================================
# 超参数搜索
# ============================================================

def hyperparameter_search(search_space: dict, fitness_fn: Callable, n_iterations: int = 20) -> dict:
    """随机超参数搜索（最大化 fitness_fn；非法参数显式抛 ValueError）。"""
    if not isinstance(search_space, dict) or not search_space:
        raise ValueError("search_space 须为非空字典")
    for k, v in search_space.items():
        if isinstance(v, list) and not v:
            raise ValueError(f"参数 {k!r} 的候选列表为空")
    _require_fitness_fn(fitness_fn)
    _require_positive_int("n_iterations", n_iterations)
    best_params = {}
    best_score = float('-inf')

    for _ in range(n_iterations):
        params = {k: random.choice(v) if isinstance(v, list) else v
                  for k, v in search_space.items()}
        score = fitness_fn(params)
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise ValueError(f"评分须为数值：{score!r}")
        if isinstance(score, float) and not math.isfinite(score):
            raise ValueError(f"评分须为有限数值：{score!r}")
        if score > best_score:
            best_score = score
            best_params = params

    return {"best_params": best_params, "best_score": best_score}


# ============================================================
# 模块导出
# ============================================================

__all__ = [
    # 遗传算法
    "ga_evolve", "elitism_preserve",
    # 神经进化
    "neuro_evolve", "nesma_estimate",
    # 代码生成
    "code_generation", "code_optimizer",
    # 超参数搜索
    "hyperparameter_search",
]


# ============================================================
# 注册到解释器
# ============================================================

def _register_genetic_algo(builtins: dict) -> None:
    """注册遗传算法内建到解释器。

    Matha f(a, b) 在 VM 与 interp 两侧均为柯里化单参应用 f(a)(b)，
    零参 f() 传入 0，故注册形态为逐参 lambda 链（与 ai_framework /
    data_science 同口径）；Python 侧默认参数在此显式化为必填参。
    """
    builtins["遗传算法进化"] = lambda pop: lambda fn: lambda ps: lambda mg: \
        lambda mr: lambda cr: ga_evolve(pop, fn, ps, mg, mr, cr)
    builtins["精英保留"] = lambda pop: lambda fn: lambda ec: elitism_preserve(pop, fn, ec)
    builtins["神经进化"] = lambda gl: lambda fn: lambda ps: lambda mg: neuro_evolve(gl, fn, ps, mg)
    builtins["NESMA估算"] = lambda loc: nesma_estimate(loc)
    builtins["代码生成"] = lambda t: lambda p: code_generation(t, p)
    builtins["代码优化"] = lambda code: code_optimizer(code)
    builtins["超参数搜索"] = lambda ss: lambda fn: lambda n: hyperparameter_search(ss, fn, n)


def _genetic_algo_symtab_names() -> list[str]:
    return ["遗传算法进化", "精英保留", "神经进化", "NESMA估算",
            "代码生成", "代码优化", "超参数搜索"]
