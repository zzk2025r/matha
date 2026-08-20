# -*- coding: utf-8 -*-
"""
移动端、离线存储、协作功能端到端测试
"""
from __future__ import annotations
import sys
import unittest
sys.path.insert(0, r"D:\trae")

from src.offline_store import OfflineStore, ChangeEntry
from src.collaboration import (
    CollaborationSession, Operation, OperationTransformer,
    create_session, get_session, destroy_session, list_sessions,
)
from src.mobile_full import (
    MobileDeviceDetector, MobileAPI, MobileConfig, FlutterShell,
    is_mobile, get_mobile_api, get_mobile_state,
)


class TestOfflineStore(unittest.TestCase):
    """离线存储测试。"""

    def setUp(self):
        self.store = OfflineStore(":memory:")

    def tearDown(self):
        self.store.close()

    def test_save_and_load_project(self):
        """测试项目保存和加载。"""
        self.store.save_project("proj_001", "测试项目", {"nodes": [], "connections": []})
        project = self.store.load_project("proj_001")
        self.assertIsNotNone(project)
        self.assertEqual(project["name"], "测试项目")

    def test_list_projects(self):
        """测试项目列表。"""
        self.store.save_project("p1", "项目1", {})
        self.store.save_project("p2", "项目2", {})
        projects = self.store.list_projects()
        self.assertEqual(len(projects), 2)

    def test_delete_project(self):
        """测试项目删除。"""
        self.store.save_project("p_del", "待删除", {})
        self.assertTrue(self.store.delete_project("p_del"))
        self.assertIsNone(self.store.load_project("p_del"))

    def test_change_logging(self):
        """测试变更日志。"""
        self.store._log_change("node", "n1", "create", {"type": "math_add"})
        changes = self.store.get_pending_changes()
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].action, "create")

    def test_conflict_resolution(self):
        """测试冲突解决。"""
        import time
        local = {"value": 1}
        remote = {"value": 2}
        result = self.store.resolve_conflict(local, remote, time.time(), time.time() - 1)
        self.assertTrue(result["conflict"])
        self.assertEqual(result["strategy"], "lww")

    def test_sync_stats(self):
        """测试同步统计。"""
        stats = self.store.get_sync_stats()
        self.assertIn("total_changes", stats)
        self.assertIn("pending_sync", stats)


class TestCollaboration(unittest.TestCase):
    """协作功能测试。"""

    def test_create_session(self):
        """测试创建会话。"""
        session = create_session("sess_test", "proj_test")
        self.assertIsNotNone(session)
        self.assertEqual(session.project_id, "proj_test")

    def test_join_leave(self):
        """测试成员加入和离开。"""
        session = create_session("sess_002", "proj_002")
        alice = session.join("alice", "Alice", "#e74c3c")
        self.assertEqual(alice.username, "Alice")
        self.assertTrue(alice.is_online)

        session.leave("alice")
        self.assertFalse(session.collaborators["alice"].is_online)

    def test_operation_broadcast(self):
        """测试操作广播。"""
        session = create_session("sess_003", "proj_003")
        op = Operation(
            op_id="op_001",
            user_id="alice",
            timestamp=1000.0,
            target_entity="node",
            entity_id="node_1",
            action="create",
            data={"type": "math_add"},
        )
        session.broadcast_operation(op)
        self.assertEqual(len(session.get_operation_history()), 1)

    def test_chat(self):
        """测试聊天功能。"""
        session = create_session("sess_004", "proj_004")
        msg = session.send_message("alice", "Alice", "Hello!")
        self.assertEqual(msg.content, "Hello!")
        self.assertEqual(len(session.get_chat_history()), 1)

    def test_invite_system(self):
        """测试邀请系统。"""
        session = create_session("sess_005", "proj_005")
        invite = session.create_invite("alice", "Alice")
        self.assertIsNotNone(invite.code)

        # 兑换邀请
        charlie = session.redeem_invite(invite.code, "charlie", "Charlie")
        self.assertIsNotNone(charlie)
        self.assertEqual(charlie.username, "Charlie")

    def test_ot_transformer(self):
        """测试 OT 算法。"""
        transformer = OperationTransformer()
        op_a = Operation("a", "u1", 100.0, "node", "n1", "create", {"x": 1})
        op_b = Operation("b", "u2", 100.0, "node", "n1", "update", {"y": 2})
        t_a, t_b = transformer.transform(op_a, op_b)
        self.assertEqual(t_a.op_id, "a")
        self.assertEqual(t_b.op_id, "b")

    def test_destroy_session(self):
        """测试销毁会话。"""
        sid = "sess_destroy"
        create_session(sid, "proj_destroy")
        self.assertIsNotNone(get_session(sid))
        destroy_session(sid)
        self.assertIsNone(get_session(sid))


class TestMobileFull(unittest.TestCase):
    """移动端完整功能测试。"""

    def test_device_detector(self):
        """测试设备检测。"""
        result = MobileDeviceDetector.detect()
        self.assertIsInstance(result, bool)

    def test_mobile_api_zeros(self):
        """测试矩阵创建。"""
        api = get_mobile_api()
        result = api.zeros((3, 3))
        self.assertIsNotNone(result)

    def test_mobile_api_eye(self):
        """测试单位矩阵。"""
        from src.mobile_full import MobileAPI, MobileConfig
        api = MobileAPI(MobileConfig(memory_limit_mb=128))
        result = api.eye(3)
        self.assertIsNotNone(result)

    def test_flutter_shell_messages(self):
        """测试 Flutter 消息协议。"""
        init = FlutterShell.create_init_message("Matha", "4.4.0")
        self.assertEqual(init["type"], "init")
        self.assertEqual(init["app"], "Matha")

        math_req = FlutterShell.create_math_request("r1", "zeros", [[3], [3]])
        self.assertEqual(math_req["operation"], "zeros")

        math_resp = FlutterShell.create_math_response("r1", [[1, 0], [0, 1]])
        self.assertEqual(math_resp["result"], [[1, 0], [0, 1]])

    def test_mobile_state(self):
        """测试移动端状态。"""
        state = get_mobile_state()
        self.assertIn("is_mobile", state)
        self.assertIn("config", state)
        self.assertIn("api_available", state)

    def test_mobile_config(self):
        """测试移动端配置。"""
        config = MobileConfig(memory_limit_mb=128, touch_sensitivity=2.0)
        self.assertEqual(config.memory_limit_mb, 128)
        self.assertEqual(config.touch_sensitivity, 2.0)


class TestIntegrationEndToEnd(unittest.TestCase):
    """端到端集成测试。"""

    def test_visual_editor_to_collaboration(self):
        """可视化编辑器 → 协作流程测试。"""
        from src.visual_editor import NodeExecutor, register_all_nodes

        register_all_nodes()
        executor = NodeExecutor()

        # 添加节点
        executor.add_node("pi", {"type": "math_pi", "id": "pi"})
        executor.add_node("mul", {"type": "math_multiply", "id": "mul"})
        executor.add_node("out", {"type": "output", "id": "out"})

        executor.add_connection("pi", "value", "mul", "a")
        executor.add_connection("mul", "result", "out", "value")

        # 设置输入
        executor._nodes["mul"]["inputs"] = {"a": None, "b": 2.0}

        # 执行
        result = executor.execute()
        self.assertEqual(result["status"], "success")

        # 同步到协作会话
        session = create_session("sess_e2e", "proj_e2e")
        session.join("user1", "TestUser", "#ff0000")

        op = Operation(
            op_id="op_e2e",
            user_id="user1",
            timestamp=2000.0,
            target_entity="project",
            entity_id="proj_e2e",
            action="update",
            data={"executor_state": result},
        )
        session.broadcast_operation(op)
        self.assertEqual(len(session.get_operation_history()), 1)

        # 离线保存
        store = OfflineStore(":memory:")
        store.save_project("proj_e2e", "E2E 测试", result)
        project = store.load_project("proj_e2e")
        self.assertIsNotNone(project)
        store.close()
        destroy_session("sess_e2e")


if __name__ == "__main__":
    unittest.main(verbosity=2)
