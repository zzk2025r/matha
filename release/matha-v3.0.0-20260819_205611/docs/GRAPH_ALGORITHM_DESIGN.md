# -*- coding: utf-8 -*-
"""Matha 图算法模块设计文档

版本：v4.4.1
日期：2025-07-26
状态：设计阶段

---

## 一、模块概述

本模块提供图论算法的核心实现，包括：
- 图数据结构定义
- 图遍历算法（BFS/DFS）
- 最短路径算法（Dijkstra）
- 最小生成树算法（Prim/Kruskal）
- 拓扑排序
- 连通分量分析

---

## 二、设计目标

1. **零依赖**：纯 Python 实现，无需外部库
2. **移动端兼容**：内存优化，支持大规模图
3. **API 简洁**：与 NumPy 风格一致
4. **性能优化**：支持稀疏图和稠密图

---

## 三、核心接口定义

### 3.1 图数据结构

```python
class Graph:
    """有向/无向图数据结构"""

    def __init__(self, n: int, directed: bool = False):
        """
        初始化图

        Args:
            n: 顶点数（0 到 n-1）
            directed: 是否为有向图
        """
        self.n = n
        self.directed = directed
        self.adjacency: List[List[int]] = [[] for _ in range(n)]
        self.weights: Dict[Tuple[int, int], float] = {}

    def add_edge(self, u: int, v: int, weight: float = 1.0) -> None:
        """添加边"""
        ...

    def remove_edge(self, u: int, v: int) -> None:
        """删除边"""
        ...

    def has_edge(self, u: int, v: int) -> bool:
        """检查边是否存在"""
        ...

    def neighbors(self, u: int) -> List[int]:
        """获取邻接顶点"""
        ...

    def degree(self, u: int) -> int:
        """获取顶点度数"""
        ...

    def edges(self) -> List[Tuple[int, int, float]]:
        """获取所有边"""
        ...

    def density(self) -> float:
        """计算图密度"""
        ...
```

### 3.2 BFS 广度优先搜索

```python
def bfs(graph: Graph, start: int) -> Dict[int, int]:
    """
    BFS 遍历

    Args:
        graph: 图对象
        start: 起始顶点

    Returns:
        距离字典 {顶点: 距离}
    """
    ...

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
    ...
```

### 3.3 DFS 深度优先搜索

```python
def dfs(graph: Graph, start: int) -> List[int]:
    """
    DFS 遍历

    Args:
        graph: 图对象
        start: 起始顶点

    Returns:
        遍历顺序列表
    """
    ...

def dfs_cycles(graph: Graph) -> List[List[int]]:
    """
    DFS 检测环

    Args:
        graph: 图对象

    Returns:
        环列表
    """
    ...
```

### 3.4 Dijkstra 最短路径

```python
def dijkstra(graph: Graph, start: int) -> Tuple[List[float], List[Optional[int]]]:
    """
    Dijkstra 最短路径

    Args:
        graph: 图对象（权重必须非负）
        start: 起始顶点

    Returns:
        (距离列表, 前驱顶点列表)
    """
    ...

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
    ...
```

### 3.5 最小生成树

```python
def prim(graph: Graph, start: int = 0) -> List[Tuple[int, int, float]]:
    """
    Prim 算法最小生成树

    Args:
        graph: 无向连通图
        start: 起始顶点

    Returns:
        最小生成树的边列表 [(u, v, weight), ...]
    """
    ...

def kruskal(graph: Graph) -> List[Tuple[int, int, float]]:
    """
    Kruskal 算法最小生成树

    Args:
        graph: 无向连通图

    Returns:
        最小生成树的边列表 [(u, v, weight), ...]
    """
    ...
```

### 3.6 拓扑排序

```python
def topological_sort(graph: Graph) -> Optional[List[int]]:
    """
    拓扑排序（Kahn 算法）

    Args:
        graph: 有向无环图 (DAG)

    Returns:
        拓扑排序结果，有环则返回 None
    """
    ...
```

### 3.7 连通性分析

```python
def connected_components(graph: Graph) -> List[List[int]]:
    """
    连通分量分析

    Args:
        graph: 无向图

    Returns:
        连通分量列表
    """
    ...

def is_connected(graph: Graph) -> bool:
    """
    检查图是否连通

    Args:
        graph: 无向图

    Returns:
        是否连通
    """
    ...
```

---

## 四、类图设计

```
Graph
├── __init__(n, directed)
├── add_edge(u, v, weight)
├── remove_edge(u, v)
├── has_edge(u, v) -> bool
├── neighbors(u) -> List[int]
├── degree(u) -> int
├── edges() -> List[Tuple]
└── density() -> float

BFS
├── bfs(graph, start) -> Dict
└── bfs_path(graph, start, end) -> List

DFS
├── dfs(graph, start) -> List
└── dfs_cycles(graph) -> List

Dijkstra
├── dijkstra(graph, start) -> Tuple
└── dijkstra_path(graph, start, end) -> List

MST
├── prim(graph, start) -> List
└── kruskal(graph) -> List

Topological
└── topological_sort(graph) -> List

Connectivity
├── connected_components(graph) -> List
└── is_connected(graph) -> bool
```

---

## 五、性能预估

| 算法 | 时间复杂度 | 空间复杂度 |
|---|---|---|
| BFS | O(V + E) | O(V) |
| DFS | O(V + E) | O(V) |
| Dijkstra | O((V+E)log V) | O(V) |
| Prim | O((V+E)log V) | O(V) |
| Kruskal | O(E log E) | O(E) |
| 拓扑排序 | O(V + E) | O(V) |
| 连通分量 | O(V + E) | O(V) |

---

## 六、测试计划

```python
class TestGraphAlgorithms(unittest.TestCase):
    def test_graph_creation(self): ...
    def test_add_remove_edge(self): ...
    def test_bfs_traversal(self): ...
    def test_bfs_shortest_path(self): ...
    def test_dfs_traversal(self): ...
    def test_dfs_cycle_detection(self): ...
    def test_dijkstra(self): ...
    def test_prim_mst(self): ...
    def test_kruskal_mst(self): ...
    def test_topological_sort(self): ...
    def test_connected_components(self): ...
    def test_large_graph_performance(self): ...
```

---

## 七、实现步骤

1. **Phase 1**: 实现 Graph 类基础功能
2. **Phase 2**: 实现 BFS/DFS 遍历
3. **Phase 3**: 实现 Dijkstra 最短路径
4. **Phase 4**: 实现 Prim/Kruskal 最小生成树
5. **Phase 5**: 实现拓扑排序和连通性分析
6. **Phase 6**: 性能测试和优化

---

**设计状态**：✅ 设计完成，待实现
