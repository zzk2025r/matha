# -*- coding: utf-8 -*-
"""Matha 图算法模块实现

提供图论算法的核心实现：
  - 图数据结构
  - BFS/DFS 遍历
  - Dijkstra 最短路径
  - Prim/Kruskal 最小生成树
  - 拓扑排序
  - 连通分量分析

数学表达：
  所有算法遵循图论定义，确保正确性。

用法：
  from src.domains.graph import Graph, bfs, dfs, dijkstra, prim, kruskal
"""
from __future__ import annotations
import math
import heapq
from typing import List, Tuple, Dict, Optional, Set, Any
from dataclasses import dataclass, field


# ============================================================
# 图数据结构
# ============================================================

@dataclass
class Graph:
    """
    有向/无向图数据结构

    属性：
        n: 顶点数
        directed: 是否为有向图
        adjacency: 邻接表
        weights: 边权重 { (u, v): weight }
    """

    n: int = 0
    directed: bool = False
    adjacency: List[List[int]] = field(default_factory=list)
    weights: Dict[Tuple[int, int], float] = field(default_factory=dict)

    def __post_init__(self):
        """初始化邻接表"""
        if len(self.adjacency) != self.n:
            self.adjacency = [[] for _ in range(self.n)]

    def add_edge(self, u: int, v: int, weight: float = 1.0) -> None:
        """
        添加边

        Args:
            u: 起点
            v: 终点
            weight: 边权重（默认 1.0）
        """
        if u < 0 or u >= self.n or v < 0 or v >= self.n:
            raise ValueError(f"顶点索引超出范围: {u}, {v} (图大小: {self.n})")

        self.adjacency[u].append(v)
        self.weights[(u, v)] = weight

        if not self.directed:
            self.adjacency[v].append(u)
            self.weights[(v, u)] = weight

    def remove_edge(self, u: int, v: int) -> None:
        """删除边"""
        if v in self.adjacency[u]:
            self.adjacency[u].remove(v)
        if (u, v) in self.weights:
            del self.weights[(u, v)]
        if not self.directed:
            if u in self.adjacency[v]:
                self.adjacency[v].remove(u)
            if (v, u) in self.weights:
                del self.weights[(v, u)]

    def has_edge(self, u: int, v: int) -> bool:
        """检查边是否存在"""
        return v in self.adjacency[u]

    def neighbors(self, u: int) -> List[int]:
        """获取邻接顶点"""
        if u < 0 or u >= self.n:
            raise ValueError(f"顶点索引超出范围: {u}")
        return list(self.adjacency[u])

    def degree(self, u: int) -> int:
        """获取顶点度数"""
        return len(self.adjacency[u])

    def edges(self) -> List[Tuple[int, int, float]]:
        """获取所有边"""
        result = []
        seen = set()
        for u in range(self.n):
            for v in self.adjacency[u]:
                if self.directed or (u, v) not in seen:
                    weight = self.weights.get((u, v), 1.0)
                    result.append((u, v, weight))
                    if not self.directed:
                        seen.add((u, v))
                        seen.add((v, u))
        return result

    def density(self) -> float:
        """计算图密度"""
        if self.n <= 1:
            return 0.0
        max_edges = self.n * (self.n - 1) if self.directed else self.n * (self.n - 1) // 2
        return len(self.edges()) / max_edges if max_edges > 0 else 0.0

    def __repr__(self) -> str:
        return f"Graph(n={self.n}, directed={self.directed}, edges={len(self.edges())})"


# ============================================================
# BFS 广度优先搜索
# ============================================================

def bfs(graph: Graph, start: int) -> Dict[int, int]:
    """
    BFS 遍历，返回各顶点到起点的距离

    Args:
        graph: 图对象
        start: 起始顶点

    Returns:
        距离字典 {顶点: 距离}
    """
    if start < 0 or start >= graph.n:
        raise ValueError(f"起始顶点超出范围: {start}")

    dist = {i: -1 for i in range(graph.n)}
    dist[start] = 0
    queue = [start]

    while queue:
        u = queue.pop(0)
        for v in graph.adjacency[u]:
            if dist[v] == -1:
                dist[v] = dist[u] + 1
                queue.append(v)

    return dist


def bfs_path(graph: Graph, start: int, end: int) -> Optional[List[int]]:
    """
    BFS 最短路径

    Args:
        graph: 图对象
        start: 起始顶点
        end: 目标顶点

    Returns:
        路径列表，不存在则返回 None
    """
    if start == end:
        return [start]

    parent = {start: None}
    visited = {start}
    queue = [start]

    while queue:
        u = queue.pop(0)
        for v in graph.adjacency[u]:
            if v not in visited:
                visited.add(v)
                parent[v] = u
                if v == end:
                    # 重建路径
                    path = []
                    node = end
                    while node is not None:
                        path.append(node)
                        node = parent[node]
                    return path[::-1]
                queue.append(v)

    return None


# ============================================================
# DFS 深度优先搜索
# ============================================================

def dfs(graph: Graph, start: int) -> List[int]:
    """
    DFS 遍历

    Args:
        graph: 图对象
        start: 起始顶点

    Returns:
        遍历顺序列表
    """
    if start < 0 or start >= graph.n:
        raise ValueError(f"起始顶点超出范围: {start}")

    visited = set()
    order = []

    def _dfs(u: int):
        visited.add(u)
        order.append(u)
        for v in graph.adjacency[u]:
            if v not in visited:
                _dfs(v)

    _dfs(start)
    return order


def dfs_cycles(graph: Graph) -> List[List[int]]:
    """
    DFS 检测环（有向图）

    Args:
        graph: 有向图对象

    Returns:
        环列表
    """
    cycles = []
    WHITE, GRAY, BLACK = 0, 1, 2
    color = [WHITE] * graph.n
    parent = [-1] * graph.n

    def _dfs(u: int):
        color[u] = GRAY
        for v in graph.adjacency[u]:
            if color[v] == WHITE:
                parent[v] = u
                _dfs(v)
            elif color[v] == GRAY:
                # 找到环
                cycle = [v]
                node = u
                while node != v:
                    cycle.append(node)
                    node = parent[node]
                cycle.append(v)
                cycles.append(cycle[::-1])
        color[u] = BLACK

    for i in range(graph.n):
        if color[i] == WHITE:
            _dfs(i)

    return cycles


# ============================================================
# Dijkstra 最短路径
# ============================================================

def dijkstra(graph: Graph, start: int) -> Tuple[List[float], List[Optional[int]]]:
    """
    Dijkstra 最短路径

    Args:
        graph: 图对象（权重必须非负）
        start: 起始顶点

    Returns:
        (距离列表, 前驱顶点列表)
    """
    if start < 0 or start >= graph.n:
        raise ValueError(f"起始顶点超出范围: {start}")

    dist = [float('inf')] * graph.n
    prev = [None] * graph.n
    dist[start] = 0
    pq = [(0, start)]  # (距离, 顶点)
    visited = set()

    while pq:
        d, u = heapq.heappop(pq)

        if u in visited:
            continue
        visited.add(u)

        for v in graph.adjacency[u]:
            weight = graph.weights.get((u, v), 1.0)
            new_dist = d + weight
            if new_dist < dist[v]:
                dist[v] = new_dist
                prev[v] = u
                heapq.heappush(pq, (new_dist, v))

    return dist, prev


def dijkstra_path(graph: Graph, start: int, end: int) -> Optional[List[int]]:
    """
    Dijkstra 最短路径（单点对）

    Args:
        graph: 图对象
        start: 起始顶点
        end: 目标顶点

    Returns:
        路径列表，不存在则返回 None
    """
    dist, prev = dijkstra(graph, start)

    if dist[end] == float('inf'):
        return None

    # 重建路径
    path = []
    node = end
    while node is not None:
        path.append(node)
        node = prev[node]
    return path[::-1]


# ============================================================
# 最小生成树
# ============================================================

def prim(graph: Graph, start: int = 0) -> List[Tuple[int, int, float]]:
    """
    Prim 算法最小生成树

    Args:
        graph: 无向连通图
        start: 起始顶点

    Returns:
        最小生成树的边列表 [(u, v, weight), ...]
    """
    if start < 0 or start >= graph.n:
        raise ValueError(f"起始顶点超出范围: {start}")
    if graph.directed:
        raise ValueError("Prim 算法仅适用于无向图")

    mst = []
    visited = {start}
    # 优先级队列：(weight, u, v)
    edges = []
    for v in graph.adjacency[start]:
        w = graph.weights.get((start, v), 1.0)
        heapq.heappush(edges, (w, start, v))

    while edges and len(visited) < graph.n:
        w, u, v = heapq.heappop(edges)
        if v in visited:
            continue
        visited.add(v)
        mst.append((u, v, w))

        for next_v in graph.adjacency[v]:
            if next_v not in visited:
                next_w = graph.weights.get((v, next_v), 1.0)
                heapq.heappush(edges, (next_w, v, next_v))

    return mst


def kruskal(graph: Graph) -> List[Tuple[int, int, float]]:
    """
    Kruskal 算法最小生成树

    Args:
        graph: 无向连通图

    Returns:
        最小生成树的边列表 [(u, v, weight), ...]
    """
    if graph.directed:
        raise ValueError("Kruskal 算法仅适用于无向图")

    # 并查集
    parent = list(range(graph.n))
    rank = [0] * graph.n

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]  # 路径压缩
            x = parent[x]
        return x

    def union(x: int, y: int) -> bool:
        px, py = find(x), find(y)
        if px == py:
            return False
        if rank[px] < rank[py]:
            px, py = py, px
        parent[py] = px
        if rank[px] == rank[py]:
            rank[px] += 1
        return True

    # 按权重排序所有边
    edges = sorted(graph.edges(), key=lambda e: e[2])
    mst = []

    for u, v, w in edges:
        if union(u, v):
            mst.append((u, v, w))
            if len(mst) == graph.n - 1:
                break

    return mst


# ============================================================
# 拓扑排序
# ============================================================

def topological_sort(graph: Graph) -> Optional[List[int]]:
    """
    拓扑排序（Kahn 算法）

    Args:
        graph: 有向无环图 (DAG)

    Returns:
        拓扑排序结果，有环则返回 None
    """
    if not graph.directed:
        raise ValueError("拓扑排序仅适用于有向图")

    # 计算入度
    in_degree = [0] * graph.n
    for u in range(graph.n):
        for v in graph.adjacency[u]:
            in_degree[v] += 1

    # 初始化队列（入度为 0 的顶点）
    queue = [i for i in range(graph.n) if in_degree[i] == 0]
    result = []

    while queue:
        u = queue.pop(0)
        result.append(u)

        for v in graph.adjacency[u]:
            in_degree[v] -= 1
            if in_degree[v] == 0:
                queue.append(v)

    # 检查是否有环
    if len(result) != graph.n:
        return None  # 有环

    return result


# ============================================================
# 连通性分析
# ============================================================

def connected_components(graph: Graph) -> List[List[int]]:
    """
    连通分量分析

    Args:
        graph: 无向图

    Returns:
        连通分量列表
    """
    if graph.directed:
        # 有向图使用强连通分量（简化版）
        return _strongly_connected_components(graph)

    visited = set()
    components = []

    for start in range(graph.n):
        if start not in visited:
            component = []
            stack = [start]
            while stack:
                u = stack.pop()
                if u in visited:
                    continue
                visited.add(u)
                component.append(u)
                for v in graph.adjacency[u]:
                    if v not in visited:
                        stack.append(v)
            components.append(component)

    return components


def _strongly_connected_components(graph: Graph) -> List[List[int]]:
    """有向图的强连通分量（简化版，使用 Kosaraju 算法）"""
    # 第一次 DFS，记录完成顺序
    visited = set()
    order = []

    def _dfs1(u: int):
        visited.add(u)
        for v in graph.adjacency[u]:
            if v not in visited:
                _dfs1(v)
        order.append(u)

    for i in range(graph.n):
        if i not in visited:
            _dfs1(i)

    # 构建转置图
    transpose = Graph(graph.n, directed=True)
    for u in range(graph.n):
        for v in graph.adjacency[u]:
            transpose.add_edge(v, u)

    # 第二次 DFS，按完成顺序逆序
    visited = set()
    components = []

    def _dfs2(u: int, component: list):
        visited.add(u)
        component.append(u)
        for v in transpose.adjacency[u]:
            if v not in visited:
                _dfs2(v, component)

    for u in reversed(order):
        if u not in visited:
            component = []
            _dfs2(u, component)
            components.append(component)

    return components


def is_connected(graph: Graph) -> bool:
    """
    检查图是否连通

    Args:
        graph: 无向图

    Returns:
        是否连通
    """
    if graph.n == 0:
        return True
    components = connected_components(graph)
    return len(components) == 1


# ============================================================
# 图生成工具
# ============================================================

def random_graph(n: int, m: int, directed: bool = False,
                 weight_range: Tuple[float, float] = (1.0, 10.0)) -> Graph:
    """
    生成随机图

    Args:
        n: 顶点数
        m: 边数
        directed: 是否为有向图
        weight_range: 权重范围

    Returns:
        随机图对象
    """
    import random
    graph = Graph(n, directed)

    # 确保不生成重边
    edges_set = set()
    for _ in range(m):
        u = random.randint(0, n - 1)
        v = random.randint(0, n - 1)
        if u != v and (u, v) not in edges_set:
            edges_set.add((u, v))
            weight = random.uniform(*weight_range)
            graph.add_edge(u, v, weight)

    return graph


def complete_graph(n: int, weight: float = 1.0) -> Graph:
    """生成完全图"""
    graph = Graph(n, directed=False)
    for i in range(n):
        for j in range(i + 1, n):
            graph.add_edge(i, j, weight)
    return graph


def path_graph(n: int, weight: float = 1.0) -> Graph:
    """生成路径图"""
    graph = Graph(n, directed=False)
    for i in range(n - 1):
        graph.add_edge(i, i + 1, weight)
    return graph


def cycle_graph(n: int, weight: float = 1.0) -> Graph:
    """生成环图"""
    graph = Graph(n, directed=False)
    for i in range(n - 1):
        graph.add_edge(i, i + 1, weight)
    graph.add_edge(n - 1, 0, weight)
    return graph


# ============================================================
# 注册为内建
# ============================================================

def _register_graph(builtins: dict) -> None:
    """注册图算法内建到解释器。"""
    builtins["图"] = Graph
    builtins["广度优先搜索"] = bfs
    builtins["bfs路径"] = bfs_path
    builtins["深度优先搜索"] = dfs
    builtins["dfs环检测"] = dfs_cycles
    builtins["迪杰斯特拉最短路径"] = dijkstra
    builtins["dijkstra路径"] = dijkstra_path
    builtins["普里姆最小生成树"] = prim
    builtins["克鲁斯卡尔最小生成树"] = kruskal
    builtins["拓扑排序"] = topological_sort
    builtins["连通分量"] = connected_components
    builtins["强连通分量"] = _strongly_connected_components
    builtins["是否连通"] = is_connected
    builtins["随机图"] = random_graph
    builtins["完全图"] = complete_graph
    builtins["路径图"] = path_graph
    builtins["环图"] = cycle_graph


def graph_symtab_names() -> list[str]:
    """返回图算法模块的符号表名列表。"""
    return ["图", "广度优先搜索", "bfs路径", "深度优先搜索", "dfs环检测",
            "迪杰斯特拉最短路径", "dijkstra路径", "普里姆最小生成树",
            "克鲁斯卡尔最小生成树", "拓扑排序", "连通分量", "强连通分量",
            "是否连通", "随机图", "完全图", "路径图", "环图"]


# ============================================================
# 使用示例
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  Matha 图算法模块演示")
    print("=" * 60)

    # 创建示例图
    print("\n【1. 创建图】")
    g = Graph(6, directed=False)
    g.add_edge(0, 1, 7)
    g.add_edge(0, 2, 9)
    g.add_edge(0, 5, 15)
    g.add_edge(1, 2, 10)
    g.add_edge(1, 3, 15)
    g.add_edge(2, 3, 11)
    g.add_edge(2, 5, 11)
    g.add_edge(3, 4, 6)
    g.add_edge(4, 5, 10)
    print(f"  图: {g}")
    print(f"  边数: {len(g.edges())}")
    print(f"  密度: {g.density():.4f}")

    # BFS
    print("\n【2. BFS 遍历】")
    dist = bfs(g, 0)
    print(f"  从顶点 0 出发:")
    for v, d in sorted(dist.items()):
        print(f"    顶点 {v}: 距离 {d}")

    path = bfs_path(g, 0, 4)
    print(f"  0 -> 4 路径: {path}")

    # DFS
    print("\n【3. DFS 遍历】")
    order = dfs(g, 0)
    print(f"  遍历顺序: {order}")

    # Dijkstra
    print("\n【4. Dijkstra 最短路径】")
    dist, prev = dijkstra(g, 0)
    print(f"  从顶点 0 出发的最短距离:")
    for v, d in enumerate(dist):
        print(f"    顶点 {v}: {d:.1f}")

    path = dijkstra_path(g, 0, 4)
    print(f"  0 -> 4 最短路径: {path}")

    # Prim MST
    print("\n【5. Prim 最小生成树】")
    mst = prim(g)
    total_weight = sum(w for _, _, w in mst)
    print(f"  最小生成树边: {mst}")
    print(f"  总权重: {total_weight:.1f}")

    # Kruskal MST
    print("\n【6. Kruskal 最小生成树】")
    mst_k = kruskal(g)
    total_weight_k = sum(w for _, _, w in mst_k)
    print(f"  最小生成树边: {mst_k}")
    print(f"  总权重: {total_weight_k:.1f}")

    # 连通性
    print("\n【7. 连通性分析】")
    print(f"  图是否连通: {is_connected(g)}")
    components = connected_components(g)
    print(f"  连通分量数: {len(components)}")

    # 随机图
    print("\n【8. 随机图生成】")
    rg = random_graph(10, 15, directed=False)
    print(f"  随机图: {rg}")

    print("\n" + "=" * 60)
    print("  演示完成")
    print("=" * 60)
