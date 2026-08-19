# -*- coding: utf-8 -*-
"""Graph 图算法领域测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from src.domains.graph import (
    Graph, bfs, bfs_path, dfs, dfs_cycles,
    dijkstra, dijkstra_path, prim, kruskal,
    topological_sort, connected_components,
    is_connected, random_graph, complete_graph,
)


class TestGraph(unittest.TestCase):
    def test_graph_create(self):
        g = Graph(3)
        g.add_edge(0, 1)
        g.add_edge(1, 2)
        self.assertEqual(g.degree(0), 1)
        self.assertEqual(g.degree(1), 2)

    def test_bfs(self):
        g = Graph(4)
        g.add_edge(0, 1)
        g.add_edge(0, 2)
        g.add_edge(1, 3)
        dist = bfs(g, 0)
        self.assertEqual(dist[0], 0)
        self.assertEqual(dist[1], 1)
        self.assertEqual(dist[3], 2)

    def test_bfs_path(self):
        g = Graph(4)
        g.add_edge(0, 1)
        g.add_edge(1, 2)
        g.add_edge(2, 3)
        path = bfs_path(g, 0, 3)
        self.assertEqual(path, [0, 1, 2, 3])

    def test_dfs(self):
        g = Graph(4)
        g.add_edge(0, 1)
        g.add_edge(1, 2)
        g.add_edge(2, 3)
        order = dfs(g, 0)
        self.assertEqual(order, [0, 1, 2, 3])

    def test_dijkstra(self):
        g = Graph(3)
        g.add_edge(0, 1, 1.0)
        g.add_edge(1, 2, 2.0)
        dist, prev = dijkstra(g, 0)
        self.assertEqual(dist[2], 3.0)

    def test_dijkstra_path(self):
        g = Graph(3)
        g.add_edge(0, 1, 1.0)
        g.add_edge(1, 2, 2.0)
        path = dijkstra_path(g, 0, 2)
        self.assertEqual(path, [0, 1, 2])

    def test_prim(self):
        g = Graph(3)
        g.add_edge(0, 1, 1.0)
        g.add_edge(1, 2, 2.0)
        g.add_edge(0, 2, 5.0)
        mst = prim(g)
        self.assertGreater(len(mst), 0)

    def test_kruskal(self):
        g = Graph(3)
        g.add_edge(0, 1, 1.0)
        g.add_edge(1, 2, 2.0)
        mst = kruskal(g)
        self.assertGreater(len(mst), 0)

    def test_topological_sort(self):
        g = Graph(3, directed=True)
        g.add_edge(0, 1)
        g.add_edge(1, 2)
        order = topological_sort(g)
        self.assertEqual(order, [0, 1, 2])

    def test_connected_components(self):
        g = Graph(4)
        g.add_edge(0, 1)
        g.add_edge(2, 3)
        comps = connected_components(g)
        self.assertEqual(len(comps), 2)

    def test_is_connected(self):
        g = Graph(3)
        g.add_edge(0, 1)
        g.add_edge(1, 2)
        self.assertTrue(is_connected(g))

    def test_random_graph(self):
        g = random_graph(10, 20)
        self.assertEqual(g.n, 10)
        self.assertGreater(len(g.edges()), 0)

    def test_complete_graph(self):
        g = complete_graph(5)
        expected_edges = 5 * 4 // 2
        self.assertEqual(len(g.edges()), expected_edges)

    def test_cycle_graph(self):
        from src.domains.graph import cycle_graph
        g = cycle_graph(5)
        self.assertEqual(len(g.edges()), 5)


if __name__ == '__main__':
    unittest.main()
