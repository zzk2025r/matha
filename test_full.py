# -*- coding: utf-8 -*-
"""Matha 全功能完整性检测脚本。"""
import sys
import os
import subprocess

sys.path.insert(0, '.')

passed = 0
failed = 0
errors = []

def test(name, func):
    global passed, failed
    try:
        func()
        print(f"  [PASS] {name}")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] {name}: {e}")
        failed += 1
        errors.append((name, str(e)))

# ============================================================
# 测试函数（先定义）
# ============================================================

def check_import(module_name, class_names):
    """检查模块导入。"""
    try:
        mod = __import__(module_name, fromlist=class_names)
        for cn in class_names:
            assert hasattr(mod, cn), f"{cn} not found in {module_name}"
    except Exception as e:
        raise AssertionError(f"Import {module_name}.{class_names}: {e}")

def test_imports():
    """测试所有导入。"""
    check_import('src.matha_system', ['MathaSystem', 'get_system'])
    check_import('src.visualizer', ['MathaVisualizer', 'get_visualizer'])
    check_import('src.domains.registry', ['DomainRegistry', 'get_registry'])
    check_import('src.virtual_code', ['VirtualCodeEngine', 'VirtualCodeRegistry', 'VirtualCodeDefinitionEngine'])
    check_import('src.bootstrap', ['MathaBootstrap', 'NumberSystemCompiler', 'MathaBytecodeCompiler', 'MathaSelfCompiler'])
    check_import('src.domains.game_engine', ['GameEngine', 'Scene', 'Entity', 'Vec2', 'Vec3'])
    check_import('src.domains.graphics_engine', ['Canvas', 'Color', 'Renderer'])
    check_import('src.domains.office_docs', ['Document', 'Spreadsheet', 'Presentation'])
    check_import('src.domains.os_module', ['ProcessManager', 'MemoryManager', 'ThreadManager'])
    check_import('src.domains.networking', ['MathaSocket', 'http_get', 'http_post'])
    check_import('src.domains.io_system', ['file_read', 'file_write', 'json_encode'])
    check_import('src.domains.time_module', ['Timer', 'now', 'today'])
    from src.matha_main import VERSION
    assert VERSION == "4.5"

def test_matha_system_init():
    """测试 MathaSystem 初始化。"""
    from src.matha_system import MathaSystem
    s = MathaSystem(debug=False)
    s.initialize()
    assert s._initialized is True
    status = s.get_status()
    assert status["initialized"] is True
    assert status["game_engine_class"] is True
    assert status["canvas_class"] is True
    assert status["document_class"] is True
    assert status["process_manager_class"] is True
    assert status["domain_registry"] is True

def test_visualizer():
    """测试可视化引擎。"""
    from src.matha_system import MathaSystem
    from src.visualizer import get_visualizer
    s = MathaSystem(debug=False)
    s.initialize()
    v = get_visualizer(s)
    assert v.pipeline is not None
    assert v.browser is not None
    assert v.perf is not None
    assert v.arch is not None

    # Pipeline
    result = v.pipeline.init_pipeline("result = 1 + 2 * 3", "c")
    assert len(result.steps) == 8

    # Arch
    ascii_art = v.visualize_architecture()
    assert "架构图" in ascii_art

    # Domains - pass the system's registry
    html = v.visualize_domains()
    assert html is not None
    assert len(html) > 0

    # Dashboard save
    path = v.save_dashboard()
    assert os.path.exists(path)

def test_cli():
    """测试 CLI 命令。"""
    result = subprocess.run([sys.executable, 'src/matha_main.py', 'arch'],
                          capture_output=True, text=True, timeout=10)
    assert result.returncode == 0
    assert "架构图" in result.stdout

    result = subprocess.run([sys.executable, 'src/matha_main.py', 'pipeline',
                           'result = 1 + 2 * 3', '-t', 'c'],
                          capture_output=True, text=True, timeout=10)
    assert result.returncode == 0
    assert "构建管线" in result.stdout

    result = subprocess.run([sys.executable, 'src/matha_main.py', 'domains'],
                          capture_output=True, text=True, timeout=10)
    assert result.returncode == 0

    result = subprocess.run([sys.executable, 'src/matha_main.py', 'test'],
                          capture_output=True, text=True, timeout=10)
    assert result.returncode == 0
    assert "5 通过" in result.stdout

    result = subprocess.run([sys.executable, 'src/matha_main.py', 'eval', '1+2*3'],
                          capture_output=True, text=True, timeout=10)
    assert result.returncode == 0
    assert "7" in result.stdout

def test_math_functions():
    """测试数学函数。"""
    from src.matha_runtime import sin, cos, sqrt, factorial, comb, gcd, is_prime, median, variance
    assert abs(sin(3.14159/2) - 1.0) < 0.01
    assert abs(cos(0) - 1.0) < 0.01
    assert abs(sqrt(4) - 2.0) < 0.01
    assert factorial(5) == 120
    assert comb(10, 3) == 120
    assert gcd(12, 8) == 4
    assert is_prime(17) is True
    assert median([1,2,3,4,5]) == 3

def test_builtins():
    """测试内置函数。"""
    from src.matha_runtime import get_builtin_names
    names = get_builtin_names()
    assert len(names) > 50

def test_domains():
    """测试领域模块。"""
    from src.domains.registry import get_registry
    reg = get_registry()
    domains = reg.list_domains()
    assert len(domains) >= 30

def test_compile_targets():
    """测试编译目标。"""
    from src.bootstrap import MathaBootstrap
    b = MathaBootstrap()
    targets = b.get_supported_targets()
    assert "binary" in targets
    assert "trinary" in targets
    assert "decimal" in targets
    assert "c" in targets
    assert "python" in targets
    assert "matha" in targets
    assert "llvm" in targets

def test_virtual_engine():
    """测试虚拟代码引擎。"""
    from src.virtual_code import VirtualCodeEngine, VirtualCodeDefinitionEngine
    engine = VirtualCodeEngine()
    entry = engine.register_any("test_func", "function")
    assert entry is not None
    assert entry.name == "test_func"

    defn_eng = VirtualCodeDefinitionEngine()
    defn = defn_eng.define("my_code")
    assert defn is not None

def test_game_engine():
    """测试游戏引擎。"""
    from src.domains.game_engine import GameEngine, Scene, Entity, Vec2, Vec3, ParticleSystem
    engine = GameEngine()
    scene = engine.create_scene("test")
    assert scene is not None
    entity = engine.create_entity("Player")
    assert entity is not None

def test_graphics_engine():
    """测试图形引擎。"""
    from src.domains.graphics_engine import Canvas, Color, Renderer
    canvas = Canvas(800, 600)
    assert canvas.width == 800
    color = Color.red()
    assert color.to_hex() == "#ff0000"

def test_office_docs():
    """测试办公文档。"""
    from src.domains.office_docs import Document, Spreadsheet, Presentation, analyze_data
    doc = Document("Test")
    assert doc.title == "Test"
    sheet = Spreadsheet(10, 5)
    assert sheet.rows == 10
    pres = Presentation("Slides")
    assert pres.title == "Slides"
    result = analyze_data([1, 2, 3, 4, 5])
    assert result["mean"] == 3.0

def test_os_module():
    """测试操作系统模块。"""
    from src.domains.os_module import ProcessManager, MemoryManager, ThreadManager, Semaphore, Event, Mutex
    pm = ProcessManager()
    pid = pm.create_process("test")
    assert pid > 0
    mm = MemoryManager()
    addr = mm.allocate(1024)
    assert addr >= 0
    sem = Semaphore(1)
    assert sem.get_value() == 1

def test_networking():
    """测试网络模块。"""
    from src.domains.networking import url_parse, dns_lookup
    parsed = url_parse("https://example.com/path")
    assert parsed["host"] == "example.com"

def test_io_system():
    """测试 IO 系统。"""
    from src.domains.io_system import file_read, file_write, file_exists, json_encode, json_decode
    assert json_encode({"a": 1}) is not None
    assert json_decode('{"a": 1}') is not None

def test_time_module():
    """测试时间模块。"""
    from src.domains.time_module import Timer, now, today, format_time
    t = Timer()
    t.start()
    t.stop()
    assert t.elapsed() >= 0
    assert today() is not None

def test_concurrent():
    """测试并发扩展。"""
    from src.domains.concurrent import Future, Promise, Mutex, Semaphore, Parallel, ConcurrentManager
    f = Future()
    f.set_result(42)
    assert f.result == 42
    assert f.is_done()
    p = Promise()
    assert p.future is not None
    m = Mutex()
    assert m.acquire()
    m.release()
    assert not m.locked
    s = Semaphore(2)
    assert s.acquire()
    assert s.count == 1
    s.release()
    assert s.count == 0
    r = Parallel.map(lambda x: x*2, [1,2,3])
    assert r == [2,4,6]
    cm = ConcurrentManager()
    assert cm.get_stats() is not None

def test_lsp_enhanced():
    """测试 LSP 增强功能。"""
    from src.lsp import MathaLSPEnhanced, CodeAction, SignatureInformation, CompletionContext
    lsp = MathaLSPEnhanced()
    completions = lsp.complete("fib(", (0, 4))
    assert completions is not None
    sig = lsp.signature_help("fib(x, y)", (0, 3))
    # signature_help may return None if no function found
    actions = lsp.code_actions("x = 1", (0, 0))
    assert actions is not None
    assert len(actions) >= 2
    ca = CodeAction(title="test", kind="refactor")
    assert ca.title == "test"

def test_graphics_extended():
    """测试图形扩展功能。"""
    from src.domains.graphics_engine import Canvas, Color, Renderer
    canvas = Canvas(800, 600)
    shader = canvas.create_shader("vertex")
    assert shader is not None
    fb = canvas.create_framebuffer(512, 512)
    assert fb is not None
    canvas.bind_framebuffer(fb)
    compute = canvas.compute_shader(256, 256)
    assert compute is not None
    assert canvas.generate_mipmap() is True
    canvas.set_viewport(0, 0, 800, 600)
    canvas.clear_buffers()
    renderer = Renderer(canvas)
    assert renderer is not None

def test_runtime_extended():
    """测试标准库扩展。"""
    from src.matha_runtime import get_builtin, get_builtin_names
    names = get_builtin_names()
    assert "len" in names
    assert "join" in names
    assert "split" in names
    assert "upper" in names
    assert "random_int" in names
    assert "json_dumps" in names
    assert len(names) > 100
    assert get_builtin("len")([1,2,3]) == 3
    assert get_builtin("join")(",", ["a","b"]) == "a,b"
    assert get_builtin("upper")("hello") == "HELLO"
    assert get_builtin("map")(lambda x: x*2, [1,2,3]) == [2,4,6]
    assert get_builtin("reverse")([1,2,3]) == [3,2,1]

def test_physics_extended():
    """测试物理引擎扩展。"""
    from src.domains.game_engine import (
        physics_check_collision, physics_apply_force,
        Vec2, Vec3, ParticleSystem, PhysicsWorld, RigidBody,
        Entity, Collider, Transform
    )
    w = PhysicsWorld(gravity=Vec2(0, -9.8))
    assert w is not None
    body = RigidBody(velocity=Vec2(0, 0))
    assert body is not None
    w.add_body(body)
    assert len(w.bodies) == 1
    w.step(0.016)
    assert body.velocity.y < 0
    # PhysicsWorld stats
    assert w.get_stats() is not None
    ps = ParticleSystem(max_particles=100)
    assert ps is not None
    # Test entity-based collision with colliders
    e1 = Entity(name="e1")
    e1.collider = Collider(width=10, height=10)
    e1.transform = Transform(position=Vec2(0, 0))
    e1.rigidbody = RigidBody(velocity=Vec2(0, 0))
    e2 = Entity(name="e2")
    e2.collider = Collider(width=10, height=10)
    e2.transform = Transform(position=Vec2(5, 5))
    e2.rigidbody = RigidBody(velocity=Vec2(0, 0))
    assert physics_check_collision(e1, e2) is not None
    physics_apply_force(e1, 10.0, 0.0)
    assert e1.rigidbody.velocity.x > 0

# ============================================================
# 主运行
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  Matha v4.5 全功能完整性检测")
    print("=" * 60)

    print()
    print("=== 1. 导入测试 ===")
    test("导入测试", test_imports)

    print()
    print("=== 2. MathaSystem 初始化 ===")
    test("MathaSystem初始化", test_matha_system_init)

    print()
    print("=== 3. Visualizer 测试 ===")
    test("Visualizer", test_visualizer)

    print()
    print("=== 4. CLI 命令测试 ===")
    test("CLI命令", test_cli)

    print()
    print("=== 5. 核心功能测试 ===")
    test("数学函数", test_math_functions)
    test("内置函数", test_builtins)
    test("领域模块", test_domains)
    test("编译目标", test_compile_targets)
    test("虚拟引擎", test_virtual_engine)
    test("游戏引擎", test_game_engine)
    test("图形引擎", test_graphics_engine)
    test("办公文档", test_office_docs)
    test("OS模块", test_os_module)
    test("网络通信", test_networking)
    test("IO系统", test_io_system)
    test("时间模块", test_time_module)
    test("并发模型", test_concurrent)
    test("LSP增强", test_lsp_enhanced)
    test("图形扩展", test_graphics_extended)
    test("标准库扩展", test_runtime_extended)
    test("物理引擎", test_physics_extended)

    print()
    print("=" * 60)
    print(f"  结果: {passed} 通过, {failed} 失败")
    if errors:
        print(f"  错误详情:")
        for name, err in errors:
            print(f"    - {name}: {err[:120]}")
    print("=" * 60)
    sys.exit(0 if failed == 0 else 1)
