# -*- coding: utf-8 -*-
"""
Matha 遗传算法与 AI 编写代码领域模块。

覆盖：
  1) 遗传算法核心（选择、交叉、变异）
  2) 神经进化（NEAT简化版）
  3) 自动代码生成
  4) 超参数搜索
"""
from __future__ import annotations
import random
from typing import Callable, Optional


# ============================================================
# 遗传算法
# ============================================================

def ga_evolve(population: list[list[int]], fitness_fn: Callable,
              pop_size: int = 100, max_gen: int = 100,
              mutation_rate: float = 0.01, crossover_rate: float = 0.8) -> dict:
    """遗传算法主循环。"""
    for gen in range(max_gen):
        # 评估适应度
        fitness = [fitness_fn(ind) for ind in population]
        best_idx = max(range(len(fitness)), key=lambda i: fitness[i])
        best_fit = fitness[best_idx]

        # 终止条件
        if best_fit >= 1.0:
            break

        # 选择（轮盘赌）
        total = sum(fitness)
        if total == 0:
            total = 1
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

    fitness = [fitness_fn(ind) for ind in population]
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
    """单点交叉。"""
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
    """精英保留。"""
    fitness = [(fitness_fn(ind), ind) for ind in population]
    fitness.sort(key=lambda x: x[0], reverse=True)
    return [ind for _, ind in fitness[:elite_count]]


# ============================================================
# 神经进化
# ============================================================

def neuro_evolve(genome_length: int, fitness_fn: Callable,
                 pop_size: int = 50, max_gen: int = 50) -> dict:
    """简化版神经进化（NEAT风格）。"""
    population = [[random.choice([0, 1]) for _ in range(genome_length)] for _ in range(pop_size)]
    return ga_evolve(population, fitness_fn, pop_size, max_gen)


def nesma_estimate(lines_of_code: int) -> float:
    """NESMA 功能点估算。"""
    # 简化公式
    return lines_of_code * 0.5  # 约0.5 FP/LOC


# ============================================================
# 自动代码生成
# ============================================================

def code_generation(template: str, params: dict) -> str:
    """模板代码生成。"""
    result = template
    for key, value in params.items():
        result = result.replace(f"{{{key}}}", str(value))
    return result


def code_optimizer(code: str) -> str:
    """简单代码优化（字符串层面）。"""
    # 移除多余空白
    import re
    code = re.sub(r'\n\s*\n', '\n', code)
    code = re.sub(r'[ \t]+', ' ', code)
    return code.strip()


# ============================================================
# 超参数搜索
# ============================================================

def hyperparameter_search(search_space: dict, fitness_fn: Callable, n_iterations: int = 20) -> dict:
    """随机超参数搜索。"""
    best_params = {}
    best_score = float('-inf')

    for _ in range(n_iterations):
        params = {k: random.choice(v) if isinstance(v, list) else v
                  for k, v in search_space.items()}
        score = fitness_fn(params)
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
    """注册遗传算法内建到解释器。"""
    builtins["遗传算法进化"] = ga_evolve
    builtins["精英保留"] = elitism_preserve
    builtins["神经进化"] = neuro_evolve
    builtins["NESMA估算"] = nesma_estimate
    builtins["代码生成"] = code_generation
    builtins["代码优化"] = code_optimizer
    builtins["超参数搜索"] = hyperparameter_search


def _genetic_algo_symtab_names() -> list[str]:
    return ["遗传算法进化", "精英保留", "神经进化", "NESMA估算",
            "代码生成", "代码优化", "超参数搜索"]
