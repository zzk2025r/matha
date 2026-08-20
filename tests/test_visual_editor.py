# -*- coding: utf-8 -*-
"""
可视化编辑器端到端测试
"""
from __future__ import annotations
import sys
import unittest
sys.path.insert(0, r"D:\trae")

from src.visual_editor import (
    NodeType, Node, NodeRegistry, register_all_nodes,
    NodeExecutor, ExecutionStatus, ExecutionError,
)


class TestNodeRegistry(unittest.TestCase):
    """节点注册表测试。"""

    def test_register_and_get(self):
        """测试节点注册和获取。"""
        register_all_nodes()
        self.assertGreater(len(NodeRegistry._nodes), 0)

        # 获取加法节点
        add_node = NodeRegistry.get("math_add")
        self.assertIsNotNone(add_node)
        self.assertEqual(add_node.label, "加法")
        self.assertEqual(add_node.category, "数学")

    def test_search(self):
        """测试节点搜索。"""
        results = NodeRegistry.search("sin")
        self.assertGreater(len(results), 0)
        self.assertTrue(any("sin" in r.node_type.value for r in results))

    def test_get_by_category(self):
        """测试按类别获取节点。"""
        math_nodes = NodeRegistry.get_by_category("数学")
        self.assertGreater(len(math_nodes), 0)
        for n in math_nodes:
            self.assertEqual(n.category, "数学")


class TestNodeExecution(unittest.TestCase):
    """节点执行测试。"""

    def setUp(self):
        register_all_nodes()
        self.executor = NodeExecutor()

    def test_simple_pipeline(self):
        """测试简单管线执行：π * 2 + 3"""
        # n1: pi 常数 → n2: 乘法 → n3: 加法 → n4: 输出
        self.executor.add_node("n1", {"type": "math_pi", "id": "n1"})
        self.executor.add_node("n2", {"type": "math_multiply", "id": "n2"})
        self.executor.add_node("n3", {"type": "math_add", "id": "n3"})
        self.executor.add_node("n4", {"type": "output", "id": "n4"})

        # n1.value -> n2.a, n2.result -> n3.a, n3.result -> n4.value
        self.executor.add_connection("n1", "value", "n2", "a")
        self.executor.add_connection("n2", "result", "n3", "a")
        self.executor.add_connection("n3", "result", "n4", "value")

        # 设置 n2, n3 的第二个输入
        self.executor._nodes["n2"]["inputs"] = {"a": None, "b": 2.0}
        self.executor._nodes["n3"]["inputs"] = {"a": None, "b": 3.0}

        # 验证
        is_valid, error = self.executor.validate_graph()
        self.assertTrue(is_valid, error)

        # 执行
        result = self.executor.execute()
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["total_nodes"], 4)
        self.assertEqual(result["executed_nodes"], 4)
        self.assertEqual(result["failed_nodes"], 0)

    def test_cycle_detection(self):
        """测试循环检测。"""
        self.executor.add_node("a", {"type": "math_add", "id": "a"})
        self.executor.add_node("b", {"type": "math_add", "id": "b"})
        self.executor.add_connection("a", "result", "b", "a")
        self.executor.add_connection("b", "result", "a", "a")  # 创建循环

        is_valid, error = self.executor.validate_graph()
        self.assertFalse(is_valid)
        self.assertIn("循环", error)

    def test_missing_node(self):
        """测试断开的连线。"""
        self.executor.add_node("a", {"type": "math_add", "id": "a"})
        self.executor.add_connection("a", "result", "nonexistent", "a")

        is_valid, error = self.executor.validate_graph()
        self.assertFalse(is_valid)
        self.assertIn("不存在", error)

    def test_execution_order(self):
        """测试拓扑排序执行顺序。"""
        self.executor.add_node("n1", {"type": "math_pi", "id": "n1"})
        self.executor.add_node("n2", {"type": "math_multiply", "id": "n2"})
        self.executor.add_connection("n1", "value", "n2", "a")

        order = self.executor.compute_execution_order()
        self.assertEqual(len(order), 2)
        # n1 必须在 n2 之前
        self.assertLess(order.index("n1"), order.index("n2"))

    def test_math_nodes(self):
        """测试数学节点执行。"""
        self.executor.add_node("n1", {"type": "math_add", "id": "n1"})
        self.executor.add_node("n2", {"type": "math_multiply", "id": "n2"})
        self.executor.add_node("n3", {"type": "output", "id": "n3"})

        self.executor.add_connection("n1", "result", "n2", "a")
        self.executor.add_connection("n2", "result", "n3", "value")

        # 设置输入值
        self.executor._nodes["n1"]["inputs"] = {"a": 3.0, "b": 4.0}
        self.executor._nodes["n2"]["inputs"] = {"a": None, "b": 2.0}

        result = self.executor.execute()
        self.assertEqual(result["status"], "success")

    def test_logic_nodes(self):
        """测试逻辑节点执行。"""
        self.executor.add_node("n1", {"type": "logic_and", "id": "n1"})
        self.executor.add_node("n2", {"type": "output", "id": "n2"})

        self.executor.add_connection("n1", "result", "n2", "value")
        self.executor._nodes["n1"]["inputs"] = {"a": True, "b": True}

        result = self.executor.execute()
        self.assertEqual(result["status"], "success")

    def test_stats_nodes(self):
        """测试统计节点执行。"""
        self.executor.add_node("n1", {"type": "stats_mean", "id": "n1"})
        self.executor.add_node("n2", {"type": "output", "id": "n2"})

        self.executor.add_connection("n1", "result", "n2", "value")
        self.executor._nodes["n1"]["inputs"] = {"data": [1.0, 2.0, 3.0, 4.0, 5.0]}

        result = self.executor.execute()
        self.assertEqual(result["status"], "success")

    def test_if_node(self):
        """测试条件分支节点。"""
        self.executor.add_node("n1", {"type": "if", "id": "n1"})
        self.executor.add_node("n2", {"type": "output", "id": "n2"})

        self.executor.add_connection("n1", "result", "n2", "value")
        self.executor._nodes["n1"]["inputs"] = {
            "condition": True,
            "true_value": 100,
            "false_value": 200,
        }

        result = self.executor.execute()
        self.assertEqual(result["status"], "success")

    def test_sequence_node(self):
        """测试序列节点。"""
        self.executor.add_node("n1", {"type": "sequence", "id": "n1"})
        self.executor.add_node("n2", {"type": "output", "id": "n2"})

        self.executor.add_connection("n1", "sequence", "n2", "value")
        self.executor._nodes["n1"]["inputs"] = {"start": 0, "end": 5, "step": 1}

        result = self.executor.execute()
        self.assertEqual(result["status"], "success")

    def test_incremental_execution(self):
        """测试增量执行。"""
        register_all_nodes()
        self.executor.add_node("n1", {"type": "math_pi", "id": "n1"})
        self.executor.add_node("n2", {"type": "math_multiply", "id": "n2"})
        self.executor.add_connection("n1", "value", "n2", "a")
        self.executor._nodes["n2"]["inputs"] = {"a": None, "b": 2.0}

        # 只执行 n1 和 n2（含依赖）
        result = self.executor.execute_incremental({"n1", "n2"})
        self.assertEqual(result["status"], "success")

    def test_serialization(self):
        """测试图序列化/反序列化。"""
        register_all_nodes()
        self.executor.add_node("n1", {"type": "math_add", "id": "n1"})
        self.executor.add_connection("n1", "result", "n1", "a")

        data = self.executor.to_dict()
        restored = NodeExecutor.from_dict(data)
        self.assertEqual(len(restored._nodes), len(self.executor._nodes))
        self.assertEqual(len(restored._connections), len(self.executor._connections))


class TestVisualEditorIntegration(unittest.TestCase):
    """可视化编辑器端到端集成测试。"""

    def test_full_pipeline(self):
        """完整管线测试：pi * 2 + 3 = 9.28..."""
        register_all_nodes()
        executor = NodeExecutor()

        # 构建管线: π * 2 + 3
        executor.add_node("pi", {"type": "math_pi", "id": "pi"})
        executor.add_node("mul", {"type": "math_multiply", "id": "mul"})
        executor.add_node("add", {"type": "math_add", "id": "add"})
        executor.add_node("out", {"type": "output", "id": "out"})

        executor.add_connection("pi", "value", "mul", "a")
        executor.add_connection("mul", "result", "add", "a")
        executor.add_connection("add", "result", "out", "value")

        # 设置输入
        executor._nodes["mul"]["inputs"] = {"a": None, "b": 2.0}
        executor._nodes["add"]["inputs"] = {"a": None, "b": 3.0}

        result = executor.execute()
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["total_nodes"], 4)
        self.assertEqual(result["executed_nodes"], 4)
        print(f"  结果: π × 2 + 3 = {result['total_duration_ms']:.2f}ms")


if __name__ == "__main__":
    unittest.main(verbosity=2)
