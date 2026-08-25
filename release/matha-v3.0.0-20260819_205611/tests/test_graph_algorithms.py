# -*- coding: utf-8 -*-
"""Matha 图算法模块测试

测试图数据结构和图算法：
  - Graph 类
  - BFS/DFS 遍历
  - Dijkstra 最短路径
  - Prim/Kruskal 最小生成树
  - 拓扑排序
  - 连通性分析
"""
import unittest
import sys
from pathlib import Path

# 添加项目根目录到路径
_project_root = Path(__file__).parent.parent
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_project_root / 'src'))

from domains.graph import (
    Graph, bfs, bfs_path, dfs, dfs_cycles,
    dijkstra, dijkstra_path, prim, kruskal,
    topological_sort, connected_components, is_connected,
    random_graph, complete_graph, path_graph, cycle_graph
)


class TestGraphDataStructure(unittest.TestCase):
    """测试图数据结构"""

    def test_create_graph(self):
        """测试创建图"""
        g = Graph(5, directed=False)
        self.assertEqual(g.n, 5)
        self.assertFalse(g.directed)
        self.assertEqual(len(g.edges()), 0)

    def test_add_edge_undirected(self):
        """测试无向图添加边"""
        g = Graph(3, directed=False)
        g.add_edge(0, 1, 5.0)
        self.assertTrue(g.has_edge(0, 1))
        self.assertTrue(g.has_edge(1, 0))
        self.assertEqual(g.degree(0), 1)
        self.assertEqual(g.degree(1), 1)

    def test_add_edge_directed(self):
        """测试有向图添加边"""
        g = Graph(3, directed=True)
        g.add_edge(0, 1, 5.0)
        self.assertTrue(g.has_edge(0, 1))
        self.assertFalse(g.has_edge(1, 0))
        self.assertEqual(g.degree(0), 1)
        self.assertEqual(g.degree(1), 0)

    def test_remove_edge(self):
        """测试删除边"""
        g = Graph(3, directed=False)
        g.add_edge(0, 1)
        g.remove_edge(0, 1)
        self.assertFalse(g.has_edge(0, 1))

    def test_invalid_vertex(self):
        """测试无效顶点"""
        g = Graph(3, directed=False)
        with self.assertRaises(ValueError):
            g.add_edge(0, 5)
        with self.assertRaises(ValueError):
            g.neighbors(5)

    def test_density(self):
        """测试图密度"""
        g = complete_graph(4)
        self.assertAlmostEqual(g.density(), 1.0)

    def test_edges(self):
        """测试边列表"""
        g = Graph(3, directed=False)
        g.add_edge(0, 1)
        g.add_edge(1, 2)
        edges = g.edges()
        self.assertEqual(len(edges), 2)


class TestBFS(unittest.TestCase):
    """测试 BFS 算法"""

    def test_bfs_traversal(self):
        """测试 BFS 遍历"""
        g = Graph(4, directed=False)
        g.add_edge(0, 1)
        g.add_edge(0, 2)
        g.add_edge(1, 3)
        dist = bfs(g, 0)
        self.assertEqual(dist[0], 0)
        self.assertEqual(dist[1], 1)
        self.assertEqual(dist[2], 1)
        self.assertEqual(dist[3], 2)

    def test_bfs_path(self):
        """测试 BFS 最短路径"""
        g = Graph(4, directed=False)
        g.add_edge(0, 1)
        g.add_edge(1, 2)
        g.add_edge(2, 3)
        path = bfs_path(g, 0, 3)
        self.assertEqual(path, [0, 1, 2, 3])

    def test_bfs_no_path(self):
        """测试无路径情况"""
        g = Graph(4, directed=False)
        g.add_edge(0, 1)
        g.add_edge(2, 3)
        path = bfs_path(g, 0, 3)
        self.assertIsNone(path)


class TestDFS(unittest.TestCase):
    """测试 DFS 算法"""

    def test_dfs_traversal(self):
        """测试 DFS 遍历"""
        g = Graph(4, directed=False)
        g.add_edge(0, 1)
        g.add_edge(0, 2)
        g.add_edge(1, 3)
        order = dfs(g, 0)
        self.assertEqual(order[0], 0)
        self.assertIn(1, order)
        self.assertIn(2, order)
        self.assertIn(3, order)

    def test_dfs_cycle_detection(self):
        """测试环检测"""
        g = Graph(3, directed=True)
        g.add_edge(0, 1)
        g.add_edge(1, 2)
        g.add_edge(2, 0)  # 形成环
        cycles = dfs_cycles(g)
        self.assertTrue(len(cycles) > 0)


class TestDijkstra(unittest.TestCase):
    """测试 Dijkstra 算法"""

    def test_dijkstra_shortest_path(self):
        """测试 Dijkstra 最短路径"""
        g = Graph(4, directed=False)
        g.add_edge(0, 1, 1.0)
        g.add_edge(0, 2, 4.0)
        g.add_edge(1, 2, 2.0)
        g.add_edge(1, 3, 6.0)
        g.add_edge(2, 3, 1.0)

        dist, prev = dijkstra(g, 0)
        self.assertAlmostEqual(dist[0], 0.0)
        self.assertAlmostEqual(dist[1], 1.0)
        self.assertAlmostEqual(dist[2], 3.0)
        self.assertAlmostEqual(dist[3], 4.0)

    def test_dijkstra_path(self):
        """测试 Dijkstra 路径"""
        g = Graph(4, directed=False)
        g.add_edge(0, 1, 1.0)
        g.add_edge(1, 2, 2.0)
        g.add_edge(2, 3, 3.0)

        path = dijkstra_path(g, 0, 3)
        self.assertEqual(path, [0, 1, 2, 3])


class TestMST(unittest.TestCase):
    """测试最小生成树算法"""

    def test_prim_mst(self):
        """测试 Prim 算法"""
        g = Graph(4, directed=False)
        g.add_edge(0, 1, 1.0)
        g.add_edge(0, 2, 4.0)
        g.add_edge(1, 2, 2.0)
        g.add_edge(1, 3, 6.0)
        g.add_edge(2, 3, 1.0)

        mst = prim(g)
        total_weight = sum(w for _, _, w in mst)
        # 4 个顶点的 MST 应有 3 条边
        self.assertEqual(len(mst), 3)
        # 总权重应 <= 8
        self.assertLessEqual(total_weight, 8.0)

    def test_kruskal_mst(self):
        """测试 Kruskal 算法"""
        g = Graph(4, directed=False)
        g.add_edge(0, 1, 1.0)
        g.add_edge(0, 2, 4.0)
        g.add_edge(1, 2, 2.0)
        g.add_edge(1, 3, 6.0)
        g.add_edge(2, 3, 1.0)

        mst = kruskal(g)
        total_weight = sum(w for _, _, w in mst)
        self.assertEqual(len(mst), 3)
        self.assertLessEqual(total_weight, 8.0)

    def test_mst_directed_error(self):
        """测试有向图错误"""
        g = Graph(3, directed=True)
        g.add_edge(0, 1, 1.0)
        with self.assertRaises(ValueError):
            prim(g)
        with self.assertRaises(ValueError):
            kruskal(g)


class TestTopologicalSort(unittest.TestCase):
    """测试拓扑排序"""

    def test_topological_sort_valid(self):
        """测试有效的拓扑排序"""
        g = Graph(4, directed=True)
        g.add_edge(0, 1)
        g.add_edge(0, 2)
        g.add_edge(1, 3)
        g.add_edge(2, 3)

        result = topological_sort(g)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 4)
        # 0 必须在 1 和 2 之前
        self.assertLess(result.index(0), result.index(1))
        self.assertLess(result.index(0), result.index(2))
        # 1 和 2 必须在 3 之前
        self.assertLess(result.index(1), result.index(3))
        self.assertLess(result.index(2), result.index(3))

    def test_topological_sort_cycle(self):
        """测试有环图返回 None"""
        g = Graph(3, directed=True)
        g.add_edge(0, 1)
        g.add_edge(1, 2)
        g.add_edge(2, 0)  # 形成环

        result = topological_sort(g)
        self.assertIsNone(result)

    def test_topological_sort_undirected_error(self):
        """测试无向图错误"""
        g = Graph(3, directed=False)
        g.add_edge(0, 1)
        with self.assertRaises(ValueError):
            topological_sort(g)


class TestConnectivity(unittest.TestCase):
    """测试连通性分析"""

    def test_connected_graph(self):
        """测试连通图"""
        g = Graph(4, directed=False)
        g.add_edge(0, 1)
        g.add_edge(1, 2)
        g.add_edge(2, 3)
        self.assertTrue(is_connected(g))

    def test_disconnected_graph(self):
        """测试非连通图"""
        g = Graph(4, directed=False)
        g.add_edge(0, 1)
        g.add_edge(2, 3)
        self.assertFalse(is_connected(g))

    def test_connected_components(self):
        """测试连通分量"""
        g = Graph(4, directed=False)
        g.add_edge(0, 1)
        g.add_edge(2, 3)
        components = connected_components(g)
        self.assertEqual(len(components), 2)


class TestGraphGenerators(unittest.TestCase):
    """测试图生成器"""

    def test_random_graph(self):
        """测试随机图生成"""
        g = random_graph(10, 15, directed=False)
        self.assertEqual(g.n, 10)
        # 随机图可能因去重导致边数略少，检查范围
        self.assertLessEqual(len(g.edges()), 15)
        self.assertGreater(len(g.edges()), 0)

    def test_complete_graph(self):
        """测试完全图生成"""
        g = complete_graph(4)
        self.assertEqual(len(g.edges()), 6)  # C(4,2) = 6

    def test_path_graph(self):
        """测试路径图生成"""
        g = path_graph(5)
        self.assertEqual(len(g.edges()), 4)

    def test_cycle_graph(self):
        """测试环图生成"""
        g = cycle_graph(5)
        self.assertEqual(len(g.edges()), 5)


if __name__ == '__main__':
    unittest.main()
