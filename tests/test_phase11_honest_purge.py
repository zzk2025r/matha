# -*- coding: utf-8 -*-
"""阶段 11 全面清算三锁测试（手算对拍 / 闭环 / 显式拒绝）。

覆盖 #14-#21 各修复面：
- P0：symbolic.py 幂规则积分/真导数/除零诚实（手算对拍）
- P1：domains 假值真化（robotics/hardware/web/matha_system 门面 + database_engine 真 sqlite）
- P2：多语言链真化（前端/转译器/hybrid/Rust 生成器/unified_multilang）
- P3：其余诚实化（插件市场包装/意图 LLM 拒绝/占位密钥边界/registry 吞错清除）

旧缺陷口径一律在测试内点名，防止回归复活。
"""
import subprocess
import sys
import time as _time
import types

import pytest


# ============================================================
# P0 · symbolic.py：手算对拍 + 除零诚实
# ============================================================

class TestSymbolicHonest:
    def _sym(self):
        from src.symbolic import MathaSymbolic
        return MathaSymbolic()

    def test_power_rule_integral_hand_calc(self):
        """∫x² dx = x³/3（旧缺陷漏 ÷(n+1) 产 x³）：结构手算对拍。"""
        s = self._sym()
        r = s.integrate(s.parse("x^2"), "x")
        assert r.operator == "/"
        denom = r.operands[1]
        assert denom.operator == "number" and float(denom.operands[0]) == 3.0
        power = r.operands[0]
        assert power.operator == "**"
        assert power.operands[0].operator == "symbol"
        assert float(power.operands[1].operands[0]) == 3.0

    def test_diff_rules_hand_calc(self):
        """(x²)'=2x（旧缺陷 diff 恒等返回）：symbolic_calc 手算对拍。"""
        from src.symbolic import symbolic_calc
        out = symbolic_calc("x^2", x=3)
        assert out["derivative"] == "(2 * x)"
        assert out["value"] == 9.0
        out3 = symbolic_calc("x^3", x=2)
        assert out3["value"] == 8.0

    def test_division_by_zero_honest(self):
        """1/0 显式拒绝（旧实现假值）：求值抛 ZeroDivisionError、
        统一接口 value=None 不冒充数值。"""
        from src.symbolic import symbolic_calc
        s = self._sym()
        with pytest.raises(ZeroDivisionError, match="除数为零"):
            s._evaluate(s.parse("1/0"), {})
        out = symbolic_calc("1/0")
        assert out["value"] is None

    def test_parse_parens_boundary_honest(self):
        """B组 parse 无括号支持属已知边界：括号内容如实落成 unknown 节点，
        不静默产错值（对照 '2*x' 真解析）。"""
        s = self._sym()
        expr = s.parse("(2*x)")
        assert expr.operator == "*"
        assert all(o.operator == "unknown" for o in expr.operands)
        real = s.parse("2*x")
        assert real.operator == "*"
        assert real.operands[0].operator == "number"
        assert real.operands[1].operator == "symbol"


# ============================================================
# P1 · domains 假值真化
# ============================================================

class TestDomainsHonest:
    def test_robotics_plan_path_hand_calc(self):
        """[0,0]→[1,0] 距离 1.0 → n=11 点，步长 0.1（手算对拍）。"""
        from src.domains.robotics import RobotEngine
        eng = RobotEngine()
        robot = eng.create_robot("r1", "arm")
        eng.add_joint(robot, "shoulder", max_angle=90)
        path = eng.plan_path([0.0, 0.0], [1.0, 0.0])
        assert len(path) == 11
        assert path[0] == [0.0, 0.0]
        assert path[3] == [0.3, 0.0]
        assert abs(path[-1][0] - 1.0) < 1e-9

    def test_robotics_plan_path_dim_mismatch_rejected(self):
        from src.domains.robotics import RobotEngine
        eng = RobotEngine()
        with pytest.raises(ValueError):
            eng.plan_path([0.0, 0.0], [1.0])

    def test_robotics_control_arm_writes_joints(self):
        from src.domains.robotics import RobotEngine
        eng = RobotEngine()
        robot = eng.create_robot("r1", "arm")
        eng.add_joint(robot, "shoulder", max_angle=90)
        eng.add_joint(robot, "elbow", max_angle=120)
        assert eng.control_arm(robot, [30.0, -45.0]) is True
        assert robot.joints[0].angle == 30.0
        assert robot.joints[1].angle == -45.0

    def test_robotics_control_arm_range_rejected(self):
        """越界显式拒绝（旧实现假置角）。"""
        from src.domains.robotics import RobotEngine
        eng = RobotEngine()
        robot = eng.create_robot("r1", "arm")
        eng.add_joint(robot, "shoulder", max_angle=90)
        with pytest.raises(ValueError, match="越界"):
            eng.control_arm(robot, [95.0])

    def test_robotics_read_sensor_no_fake(self):
        """无硬件驱动显式拒绝（旧实现恒返回 0.0 假读数）。"""
        from src.domains.robotics import RobotEngine
        eng = RobotEngine()
        robot = eng.create_robot("r1", "arm")
        with pytest.raises(RuntimeError, match="硬件"):
            eng.read_sensor(robot, "ultrasonic")

    def test_hardware_wait_short_process_true(self):
        from src.domains.hardware import _wait
        proc = subprocess.Popen([sys.executable, "-c", "pass"])
        assert _wait(proc.pid, timeout=10) is True

    def test_hardware_wait_long_process_timeout_false(self):
        """真等待：长进程 timeout=1 → False，耗时 ≈1s（旧实现假成功）。"""
        from src.domains.hardware import _wait
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(10)"])
        try:
            t0 = _time.monotonic()
            r = _wait(proc.pid, timeout=1)
            elapsed = _time.monotonic() - t0
            assert r is False
            assert 0.9 <= elapsed < 5
        finally:
            proc.kill()
            proc.wait()

    def test_hardware_wait_dead_pid_true(self):
        from src.domains.hardware import _wait
        assert _wait(999999, timeout=1) is True

    def test_websocket_connect_rejected(self):
        """RFC6455 未实现显式拒绝（旧实现直接置 connected=True 假连接）。"""
        from src.domains.web_framework import WebSocket
        ws = WebSocket("ws://x")
        assert ws.connected is False
        with pytest.raises(NotImplementedError, match="RFC6455"):
            ws.connect()
        assert ws.connected is False
        assert ws.send("hi") is False

    def test_matha_system_concurrency_uninitialized_rejected(self):
        """未 initialize：并发门面显式拒绝（旧实现返回假字典/0）。"""
        from src.matha_system import MathaSystem
        sys_uninit = MathaSystem()
        for name, arg in (("create_thread_pool", ()), ("create_channel", ()),
                          ("create_actor", ("a",)),
                          ("submit_task", (lambda: None,))):
            with pytest.raises(RuntimeError, match="并发模块"):
                getattr(sys_uninit, name)(*arg)

    def test_matha_system_concurrency_real_execution(self):
        """initialize 后：真线程池/通道/actor + submit_task 真执行。"""
        from src.matha_system import MathaSystem
        system = MathaSystem()
        system.initialize()
        tp = system.create_thread_pool(2)
        assert type(tp).__name__ == "ThreadPool"
        ch = system.create_channel(5)
        assert type(ch).__name__ == "Channel"
        assert system._shared_concurrent is not None
        assert len(system._shared_concurrent._channels) == 1
        actor = system.create_actor("worker")
        assert type(actor).__name__ == "Actor"
        result_box = []
        idx = system.submit_task(lambda: result_box.append(42))
        assert idx == 0
        assert system._shared_concurrent.await_all() == 1
        assert result_box == [42]

    def test_matha_system_web_facade(self):
        from src.matha_system import MathaSystem
        from src.domains.web_framework import WebServer
        system = MathaSystem()
        system.initialize()
        app = system.create_web_app("MyApp")
        assert isinstance(app, WebServer)
        wsock = system.create_websocket("ws://a")
        assert type(wsock).__name__ == "WebSocket"
        server = system.create_web_server("127.0.0.1", 9999)
        assert isinstance(server, WebServer)
        with pytest.raises(RuntimeError, match="create_web_server"):
            system.add_web_route("/x")

    def test_matha_system_database_real_sqlite(self):
        """真 sqlite3 存储 + 真事务回滚/提交（旧实现 SQL 从未执行）。"""
        from src.matha_system import MathaSystem
        system = MathaSystem()
        system.initialize()
        db = system.create_db_connection(db_type="memory")
        assert type(db).__name__ == "Database"
        db.execute("CREATE TABLE t (id INTEGER, name TEXT)")
        db.execute("INSERT INTO t VALUES (1, 'a')")
        qr = db.execute("SELECT * FROM t")
        assert qr.rows == [{"id": 1, "name": "a"}]
        assert qr.columns == ["id", "name"]
        assert db.insert("t", {"id": 2, "name": "b"}) is True
        assert len(db.execute("SELECT * FROM t").rows) == 2
        tx = db.begin_transaction()
        db.execute("INSERT INTO t VALUES (3, 'c')")
        assert db.rollback(tx) is True
        assert len(db.execute("SELECT * FROM t").rows) == 2
        tx2 = db.begin_transaction()
        db.execute("INSERT INTO t VALUES (4, 'd')")
        assert db.commit(tx2) is True
        assert len(db.execute("SELECT * FROM t").rows) == 3

    def test_matha_system_database_dict_api_same_store(self):
        """create_table 真 DDL + dict API 与 SQL 同库 + drop_table 真删。"""
        from src.matha_system import MathaSystem
        from src.database_engine import Column as _DCol, DataType as _DType
        system = MathaSystem()
        system.initialize()
        db = system.create_db_connection(db_type="memory")
        db.create_table("users", [_DCol("id", _DType.INTEGER, primary_key=True),
                                  _DCol("name", _DType.TEXT)])
        db.insert("users", {"id": 1, "name": "matha"})
        assert db.select("users") == [{"id": 1, "name": "matha"}]
        assert db.select("users", columns=["name"]) == [{"name": "matha"}]
        assert db.execute("SELECT name FROM users").rows == [{"name": "matha"}]
        assert db.drop_table("users") is True
        with pytest.raises(Exception, match="no such table"):
            db.execute("SELECT * FROM users")

    def test_matha_system_database_facade_rejections(self):
        """无连接的查询/事务门面显式拒绝（旧实现假返回）。"""
        from src.matha_system import MathaSystem
        system = MathaSystem()
        system.initialize()
        for name, arg in (("execute_query", ("SELECT 1",)),
                          ("begin_transaction", ()),
                          ("commit_transaction", ()),
                          ("rollback_transaction", ())):
            with pytest.raises(RuntimeError, match="create_db_connection"):
                getattr(system, name)(*arg)

    def test_matha_system_event_loop_real(self):
        from src.matha_system import MathaSystem
        system = MathaSystem()
        system.initialize()
        el = system.create_event_loop()
        assert type(el).__name__ == "EventLoop"


# ============================================================
# P2 · 多语言链真化
# ============================================================

class TestMultilangHonest:
    def test_frontends_real_registration(self):
        """真前端取代坏适配器（旧 _TS_*Adapter 路径产空 IR）。"""
        from src.multi_lang_frontend import get_frontend
        fe = get_frontend()
        assert fe.supported_languages() == ["python", "rust", "go",
                                            "javascript", "c"]
        res = fe.compile("fn foo(x: i32) -> i32 { x + 1 }", "rust")
        assert "foo" in res.functions and len(res.functions["foo"]) > 0
        res_g = fe.compile("func bar(x int) int { return x + 1 }", "go")
        assert "bar" in res_g.functions and len(res_g.functions["bar"]) > 0
        res_j = fe.compile("function baz(x) { return x + 1; }", "javascript")
        assert "baz" in res_j.functions and len(res_j.functions["baz"]) > 0
        res_c = fe.compile("int qux(int x) { return x + 1; }", "c")
        assert "qux" in res_c.functions and len(res_c.functions["qux"]) > 0

    def test_type_inference_real_map(self):
        """i64 → T_INT（旧恒 T_FLOAT 假推断）。"""
        from src.multi_lang_frontend import get_frontend
        from src.typesystem_v2_fixed import T_INT
        fe = get_frontend()
        types = fe.infer_types("fn f() -> i64 { 1 }", "rust")
        assert types.get("f") == T_INT

    def test_python_transpiler_pi_constant(self):
        """裸变量 pi → math.pi（旧产 'None  # 未转译' 假产物）。"""
        from src.transpiler import PythonTranspiler
        code = PythonTranspiler().transpile("x = pi * 2")
        assert "math.pi" in code

    def test_transpiler_unknown_expr_rejected(self):
        """未知表达式节点显式拒绝，不产假转译产物。"""
        from src.transpiler import PythonTranspiler, TranspileError

        class FakeNode:
            pass

        with pytest.raises(TranspileError):
            PythonTranspiler()._transpile_expr(FakeNode())

    def test_hybrid_stubs_rejected(self):
        """C/Rust/Go 降级空壳与反向假转译显式拒绝；TS 真转译仍工作。"""
        from src.hybrid_compiler import Language, LanguageBridge
        bridge = LanguageBridge()
        with pytest.raises(NotImplementedError, match="显式拒绝"):
            bridge.transpile_to("x = 1", Language.C)
        with pytest.raises(NotImplementedError):
            bridge.transpile_to("x = 1", Language.RUST)
        with pytest.raises(ValueError, match="显式拒绝"):
            bridge.from_language("int x;", Language.GO)
        ts = bridge.transpile_to("x = pi * 2", Language.TYPESCRIPT)
        assert isinstance(ts, str) and len(ts) > 0

    def test_rust_generator_no_fake_harness(self):
        """不再伪造 assert!/test_compute 测试架（旧假预期值断言）。"""
        from src.multi_lang_codegen import RustGenerator
        rg = RustGenerator("compute")
        code = rg.generate_function([("f64", "x")], "x * 2.0 + 1.0")
        assert "assert!" not in code and "test_compute" not in code
        assert "pub fn compute(x: f64) -> f64" in code
        main_code = rg.generate_main()
        assert "test_compute" not in main_code

    def test_unified_multilang_honest_verify(self):
        """verify_cross_language 诚实失败结构（幻影类如实点名）。"""
        from src.unified_multilang import get_unified_multilang
        ml = get_unified_multilang()
        r = ml.verify_cross_language(
            "func 求和(a, b) -> Int = (a, b) => a + b",
            languages=["python"], test_cases=[])
        assert isinstance(r, dict) and r["success"] is False
        assert "MultiLangVerifier.verify" in r["error"]

    def test_unified_multilang_full_workflow_python_real(self):
        from src.unified_multilang import get_unified_multilang
        ml = get_unified_multilang()
        r2 = ml.full_workflow("x = pi * 2", target_langs=["python"],
                              verify=False)
        assert r2["success"] is True
        assert "math.pi" in r2["generations"]["python"]

    def test_unified_multilang_full_workflow_rust_honest_error(self):
        """rust 目标诚实报错（旧吞成空串假成功）。"""
        from src.unified_multilang import get_unified_multilang
        ml = get_unified_multilang()
        r3 = ml.full_workflow("x = 1", target_langs=["rust"], verify=False)
        assert r3["success"] is False
        assert any("rust" in e and "generate_code" in e
                   for e in r3["errors"])

    def test_unified_multilang_ts_real(self):
        from src.unified_multilang import get_unified_multilang
        ts_code = get_unified_multilang().transpile_to_typescript("x = pi * 2")
        assert isinstance(ts_code, str) and "not available" not in ts_code


# ============================================================
# P3 · 其余诚实化
# ============================================================

class TestMarketWrappersHonest:
    def test_types_contract(self):
        """锁定契约保持：8 包装返回类型 + 未知包诚实降级。"""
        from src.unified_growth import UnifiedGrowth
        ug = UnifiedGrowth()
        assert isinstance(ug.search_packages("arithmetic", remote=False), list)
        info = ug.get_package_info("__nope__")
        assert isinstance(info, str) and "包不存在" in info
        assert ug.rate_package("__nope__", 5) is False
        rating = ug.get_package_rating("__nope__")
        assert isinstance(rating, dict) and "average" in rating and "count" in rating
        assert isinstance(ug.check_updates(), list)
        tree = ug.get_dependency_tree("__nope__")
        assert isinstance(tree, dict) and tree == {}
        assert isinstance(ug.check_conflicts(["__nope__"]), list)
        assert ug.upgrade_packages("__nope__", dry_run=True) == []

    def test_breakage_propagates_not_faked(self, monkeypatch):
        """管理器损坏如实抛出（旧 except 吞错返回假空/假 0 分统计）。"""
        import src.pkg_manager_v2 as pm2
        from src.unified_growth import UnifiedGrowth

        class Boom:
            def __init__(self):
                raise RuntimeError("管理器损坏")

        monkeypatch.setattr(pm2, "MathaPackageManager", Boom)
        ug = UnifiedGrowth()
        calls = [
            ("search_packages", lambda: ug.search_packages("x")),
            ("get_package_info", lambda: ug.get_package_info("x")),
            ("rate_package", lambda: ug.rate_package("x", 5)),
            ("get_package_rating", lambda: ug.get_package_rating("x")),
            ("check_updates", lambda: ug.check_updates()),
            ("get_dependency_tree", lambda: ug.get_dependency_tree("x")),
            ("check_conflicts", lambda: ug.check_conflicts(["x"])),
            ("upgrade_packages", lambda: ug.upgrade_packages()),
        ]
        for name, call in calls:
            with pytest.raises(RuntimeError, match="管理器损坏"):
                call()


class TestIntentLlmHonest:
    def test_llm_decompose_rejected(self):
        """use_llm=True 显式拒绝（旧返回模拟结果冒充 LLM 输出）。"""
        from src.intent.intent_decomposer import IntentDecomposer
        d = IntentDecomposer(use_llm=True)
        long_text = ("计算 1 加 1 并且排序数组 [3,1,2] 然后求 2 到 100 的素数"
                     + "补" * 60)
        with pytest.raises(NotImplementedError, match="模拟结果冒充"):
            d._llm_decompose(long_text)

    def test_simulate_method_deleted(self):
        from src.intent.intent_decomposer import IntentDecomposer
        assert not hasattr(IntentDecomposer(), "_simulate_llm_decomposition")

    def test_heuristic_path_alive(self):
        """默认启发式分解路径存活（生产唯一在用路径）。"""
        from src.intent.intent_decomposer import IntentDecomposer
        node = IntentDecomposer().decompose("计算 3.5 + 2.1")
        assert "3.5" in (node.math_expr or "")


class TestLlmParserKeyBoundary:
    @pytest.fixture()
    def fake_openai(self, monkeypatch):
        seen = {}
        fake = types.ModuleType("openai")

        class FakeOpenAI:
            def __init__(self, **kw):
                seen.update(kw)

        fake.OpenAI = FakeOpenAI
        monkeypatch.setitem(sys.modules, "openai", fake)
        return seen

    @pytest.fixture(autouse=True)
    def _no_keys(self, monkeypatch, tmp_path):
        monkeypatch.setenv("MATHA_CONFIG_DIR", str(tmp_path / "cfg"))
        for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY",
                    "GEMINI_API_KEY", "ZHIPUAI_API_KEY", "MATHA_LLM_API_KEY",
                    "MATHA_LLM_MODEL"):
            monkeypatch.delenv(key, raising=False)

    def test_local_placeholder_allowed(self, fake_openai):
        """本地推理服务占位密钥仅满足 SDK 必填参数。"""
        from src.intent.llm_parser import LLMIntentParser
        p = LLMIntentParser(model="custom-local-model",
                            base_url="http://localhost:11434/v1")
        assert p._api_key is None
        assert p._get_client() is not None
        assert fake_openai["api_key"] == "sk-placeholder"

    def test_remote_no_key_rejected(self):
        """远程 base_url 无密钥显式拒绝（旧以 sk-placeholder 冒充）。"""
        from src.intent.llm_parser import LLMIntentParser
        p = LLMIntentParser(model="custom-remote-model",
                            base_url="https://api.example.com/v1")
        with pytest.raises(ValueError, match="显式拒绝"):
            p._get_client()

    def test_remote_with_key_allowed(self, fake_openai):
        from src.intent.llm_parser import LLMIntentParser
        p = LLMIntentParser(model="custom-remote-model", api_key="test-key",
                            base_url="https://api.example.com/v1")
        assert p._get_client() is not None
        assert fake_openai["api_key"] == "test-key"


class TestRegistryHonest:
    def test_fire_propagates(self):
        """事件回调异常如实抛出（旧静默吞掉）。"""
        from src.domains.registry import DomainRegistry
        r = DomainRegistry()

        def boom(**kw):
            raise RuntimeError("回调坏了")

        r.add_callback("evt", boom)
        with pytest.raises(RuntimeError, match="回调坏了"):
            r.fire("evt")

    def test_dispatch_register_propagates(self):
        """回退分发钩子异常如实抛出（旧静默跳过冒充注册成功）。"""
        from src.domains.registry import DomainRegistry
        r = DomainRegistry()

        class FakeMod:
            def _register_widget(self, reg):
                raise RuntimeError("钩子坏了")

        with pytest.raises(RuntimeError, match="钩子坏了"):
            r._dispatch_register("widget", FakeMod(), {})

    def test_all_domains_get_builtins_clean(self):
        """清吞错后的回归确认：全领域 get_builtins 不抛。"""
        from src.domains.registry import get_registry
        reg = get_registry()
        assert reg._domains
        for key in list(reg._domains):
            reg.get_builtins(key)


class TestMobileSdkHttpHonest:
    def test_network_client_real_http_method(self):
        """NetworkClient.get 走真 HTTP（urllib），不再伪造响应。"""
        import inspect
        from src.mobile_sdk import NetworkClient
        src_text = inspect.getsource(NetworkClient)
        assert "_http_get" in src_text
        assert "_fake_response" not in src_text

    def test_mir_codegen_no_swallow(self):
        """MIR 清洗管线异常如实传播（旧 try/except-pass 双吞）。"""
        import inspect
        import src.mir_codegen as mc
        src_text = inspect.getsource(mc)
        assert "except Exception" not in src_text.split("def generate(")[1].split("def ")[0]


class TestLockedContractsUnchanged:
    """已上锁契约确认未误改（登记不修 ≠ 可删）。"""

    def test_time_builtin_parse_time_failure_zero(self):
        from src.kernel.time_builtin import parse_time
        assert parse_time("不是时间") == 0.0

    def test_time_builtin_unknown_tz_zero(self):
        from src.kernel.time_builtin import timezone_offset
        assert timezone_offset("未知时区") == 0

    def test_openai_compat_error_reply_honest(self):
        """chat 腿异常 → 200 但 reply 如实透出（锁定诚实契约）。"""
        import inspect
        import src.openai_compat_server as ocs
        text = inspect.getsource(ocs)
        assert "Matha 错误" in text


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
