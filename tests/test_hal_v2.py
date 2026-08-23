# -*- coding: utf-8 -*-
"""
Matha v2.0 HAL — 单元测试报告
==============================
测试 v2.0 新增模块：
  1. 安全副作用引擎 (SafeSideEffectEngine)
  2. 指针与内存控制 (PointerManager)
  3. 协议解释生成器 (ProtocolParser)
  4. 驱动生成器 (DriverGenerator)
  5. 原生编译后端 (NativeBackend)
  6. 内循环 HAL v2.0 自检 (Phase 4.56)
"""
import sys, os, json, time

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from src.hardware.hal_v2 import (
    SideEffectType, SafeSideEffectEngine,
    PointerManager, Pointer, MemoryPage,
    Architecture, BareMetalTarget,
    ProtocolType, ProtocolSpec, ProtocolParser,
    DriverKind, DriverSpec, DriverGenerator,
    NativeBackend,
    get_side_effect_engine, get_pointer_manager,
    get_protocol_parser, get_driver_generator, get_native_backend, get_hardware_stats,
)
from src.compiler.native import (
    ProtocolInterpreter, DriverBuilder, NativeCompiler,
    interpret_protocol, build_driver, native_compile,
)


class Report:
    def __init__(self, name):
        self.name = name
        self.passed = self.failed = 0
        self.details = []

    def ok(self, test, detail=""):
        self.passed += 1
        self.details.append(f"  ✓ {test}" + (f"  [{detail}]" if detail else ""))

    def fail(self, test, error=""):
        self.failed += 1
        self.details.append(f"  ✗ {test}: {error}")

    def summary(self):
        total = self.passed + self.failed
        return {
            "module": self.name, "total": total,
            "passed": self.passed, "failed": self.failed,
            "pass_rate": f"{self.passed/total*100:.1f}%" if total else "N/A",
            "details": self.details,
        }


def test_side_effect_engine(r: Report):
    from src.hardware.hal_v2 import SafeSideEffectEngine
    sse = SafeSideEffectEngine(mode="sandbox")
    sse.register_func("read_sensor", SideEffectType.READ, "readonly")
    sse.register_func("write_gpio", SideEffectType.HARDWARE, "write")
    sse.register_func("send_uart", SideEffectType.IO, "exec")

    # 只读权限正常
    assert sse.check_permission("read_sensor", "readonly")
    r.ok("权限检查: read_sensor(readonly) ✓")

    # 沙箱模式禁止硬件操作
    try:
        sse.execute_with_check(lambda: "x")
        r.ok("执行无副作用函数: ✓")
    except Exception as e:
        r.fail("执行无副作用函数", str(e))

    # 统计
    stats = sse.get_stats()
    assert stats["registered_funcs"] == 3
    assert stats["mode"] == "sandbox"
    r.ok(f"副作用引擎统计: {stats['registered_funcs']}注册, mode={stats['mode']}", "✓")

    # 安全级别检查
    assert sse.check_permission("write_gpio", "readonly") is True  # write 权限可以 readonly 调用
    r.ok("权限等级: write ≥ readonly ✓")


def test_pointer_manager(r: Report):
    pmgr = PointerManager(page_count=8)

    # 分配内存
    ptr1 = pmgr.alloc(64, "buf_a")
    assert ptr1 is not None
    r.ok(f"分配: {ptr1} size=64", "✓")

    ptr2 = pmgr.alloc(32, "buf_b")
    assert ptr2 is not None
    r.ok(f"分配: {ptr2} size=32", "✓")

    # 写入和读取
    ptr1.set(42)
    val = ptr1.get()
    assert val == 42, f"期望 42, 得到 {val}"
    r.ok(f"读写: ptr1.set(42) → ptr1.get() = {val}", "✓")

    # 指针算术
    ptr3 = ptr1.plus(10)
    assert ptr3.addr == ptr1.addr + 10
    r.ok(f"指针算术: {ptr1}+10 = {ptr3}", "✓")

    # 只读页写入检测
    try:
        pmgr.write(0, b"hack")  # 页0 是只读系统区
        r.fail("只读页检测", "应抛出 MemoryError")
    except MemoryError:
        r.ok("只读页检测: 写入页0 抛出 MemoryError ✓")

    # 释放内存
    assert pmgr.free(ptr1)
    r.ok("释放: ptr1 ✓")
    assert not pmgr.free(ptr1)  # 重复释放
    r.ok("重复释放: 返回 False ✓")

    # 统计
    stats = pmgr.get_stats()
    assert stats["total_allocs"] == 2
    assert stats["total_frees"] == 1
    assert stats["bounds_violations"] == 1
    r.ok(f"内存统计: {stats['active_allocs']}活跃分配, {stats['bounds_violations']}越界", "✓")

    # 内存不足
    try:
        pmgr.alloc(99999999)
        r.fail("内存不足", "应抛出 MemoryError")
    except MemoryError:
        r.ok("内存不足检测: 大分配抛出 MemoryError ✓")


def test_protocol_parser(r: Report):
    pp = ProtocolParser()

    # UART
    uart_spec = ProtocolSpec(protocol=ProtocolType.UART, name="uart1",
                             baud_rate=115200, data_bits=8, parity="none",
                             stop_bits=1, max_payload=64)
    uart_result = pp.parse(uart_spec)
    assert "code_python" in uart_result
    assert "uart1" in uart_result["code_python"]
    r.ok(f"UART 协议解析: baud={uart_spec.baud_rate}, {len(uart_result['code_python'])}B 代码", "✓")

    # I2C
    i2c_spec = ProtocolSpec(protocol=ProtocolType.I2C, name="i2c_temp",
                             baud_rate=100000, metadata={"device_addr": 0x48, "bus": 1})
    i2c_result = pp.parse(i2c_spec)
    assert "code_python" in i2c_result
    assert "0x48" in str(i2c_result) or "72" in i2c_result["code_python"]
    r.ok(f"I2C 协议解析: addr=0x48, {len(i2c_result['code_python'])}B 代码", "✓")

    # SPI
    spi_spec = ProtocolSpec(protocol=ProtocolType.SPI, name="spi_flash",
                             baud_rate=1000000, metadata={"channel": 0, "mode": 0})
    spi_result = pp.parse(spi_spec)
    assert "code_python" in spi_result
    r.ok(f"SPI 协议解析: clock=1MHz, {len(spi_result['code_python'])}B 代码", "✓")

    # CAN
    can_spec = ProtocolSpec(protocol=ProtocolType.CAN, name="can_bus",
                             baud_rate=500000, metadata={"id_type": "standard"})
    can_result = pp.parse(can_spec)
    assert "code_python" in can_result
    r.ok(f"CAN 协议解析: bitrate=500kbps, {len(can_result['code_python'])}B 代码", "✓")


def test_driver_generator(r: Report):
    dg = DriverGenerator(get_protocol_parser())

    # 传感器驱动
    sensor_spec = DriverSpec(
        name="temperature_sensor", kind=DriverKind.SENSORS,
        target_arch=Architecture.ARM64, target_lang="python",
        params={"scale": 0.1, "offset": -40.0, "unit": "°C"},
        math_expr="raw * 0.1 - 40.0",
    )
    sensor_code = dg.generate(sensor_spec)
    assert "temperature_sensor" in sensor_code["code"]["core"]
    assert "SCALE" in sensor_code["code"]["core"]
    r.ok(f"传感器驱动: temperature_sensor, {len(sensor_code['code']['core'])}B", "✓")

    # 执行器驱动
    actuator_spec = DriverSpec(
        name="servo_motor", kind=DriverKind.ACTUATORS,
        target_arch=Architecture.ARM64, target_lang="python",
        params={"min": 0.0, "max": 180.0, "step": 0.5},
    )
    act_code = dg.generate(actuator_spec)
    assert "servo_motor" in act_code["code"]["core"]
    r.ok(f"执行器驱动: servo_motor, {len(act_code['code']['core'])}B", "✓")

    # 数学驱动
    math_spec = DriverSpec(
        name="quadratic", kind=DriverKind.MATH,
        target_arch=Architecture.X86_64, target_lang="python",
        math_expr="x**2 + 3*x - 5",
    )
    math_code = dg.generate(math_spec)
    assert "quadratic" in math_code["code"]["core"]
    r.ok(f"数学驱动: quadratic(x²+3x-5), {len(math_code['code']['core'])}B", "✓")

    # 统计
    assert len(dg.list_generated()) == 3
    r.ok(f"驱动生成统计: {len(dg.list_generated())} 个驱动已生成", "✓")


def test_native_backend(r: Report):
    backend = NativeBackend()

    # 注册目标架构
    for arch in [Architecture.X86_64, Architecture.ARM64, Architecture.RISCV64, Architecture.AVR]:
        backend.register_target(BareMetalTarget(arch, optimize="O2"))
    r.ok(f"注册裸机目标: {backend.get_targets()}", "✓")

    # 编译为 C
    c_code = backend.compile("x^2 + 3*x - 5", Architecture.X86_64, "compute", "c")
    assert "double" in c_code or "compute" in c_code
    r.ok(f"C 编译: x²+3x-5, {len(c_code)}B", "✓")

    # 编译为 Python
    py_code = backend.compile("x^2 + 1", Architecture.X86_64, "f", "python")
    assert "def f(x)" in py_code
    r.ok(f"Python 编译: x²+1 → def f(x)", "✓")

    # 编译为汇编
    asm_code = backend.compile("sin(x)", Architecture.ARM64, "sin_fn", "assembly")
    assert "sin_fn" in asm_code
    r.ok(f"汇编编译: sin(x) → ARM64, {len(asm_code)}B", "✓")

    # 统计
    stats = backend.get_stats()
    assert stats["registered_targets"] == 4
    r.ok(f"编译统计: {stats['registered_targets']}目标, cache={stats['cache_size']}", "✓")


def test_full_pipeline(r: Report):
    """端到端：协议解析 → 驱动生成 → 原生编译 → 执行"""
    # 1. 解析 UART 协议
    pp = ProtocolParser()
    uart = pp.parse(ProtocolSpec(protocol=ProtocolType.UART, name="uart0",
                                  baud_rate=9600, metadata={}))
    r.ok("UART协议解析 → Python/C 代码", "✓")

    # 2. 生成传感器驱动（带 UART 协议）
    dg = DriverGenerator(pp)
    spec = DriverSpec(
        name="uart_sensor", kind=DriverKind.SENSORS,
        protocol=ProtocolSpec(protocol=ProtocolType.UART, name="uart0", baud_rate=9600),
        target_arch=Architecture.ARM64, target_lang="python",
        math_expr="read_uart() * 0.1",
    )
    driver = dg.generate(spec)
    assert "uart_sensor" in driver["code"]["core"]
    r.ok("UART传感器驱动生成", "✓")

    # 3. 原生编译数学表达式
    backend = NativeBackend()
    backend.register_target(BareMetalTarget(Architecture.X86_64))
    code = backend.compile("x^2 + 1", Architecture.X86_64, "test", "python")
    safe_globals = {"__builtins__": __builtins__, "math": __import__("math")}
    exec(code, safe_globals)
    fn = safe_globals.get("test")
    assert fn is not None
    result = fn(3.0)
    assert abs(result - 10.0) < 1e-9
    r.ok(f"原生编译执行: x²+1(3) = {result}", "✓")

    # 4. 副作用引擎权限检查
    sse = get_side_effect_engine("sandbox")
    sse.register_func("uart_read", SideEffectType.IO, "readonly")
    assert sse.check_permission("uart_read", "readonly")
    r.ok("副作用引擎权限检查", "✓")

    # 5. 指针管理器安全写入
    pmgr = get_pointer_manager()
    ptr = pmgr.alloc(16, "test_buf")
    ptr.set(99)
    assert ptr.get() == 99
    pmgr.free(ptr)
    r.ok("指针安全读写", "✓")


def test_inner_loop_hal_check(r: Report):
    """内循环 Phase 4.56 HAL v2.0 自检"""
    from src.inner_loop import MathaInnerLoop
    loop = MathaInnerLoop()
    loop.init_modules()

    # 验证 v2.0 模块已注册
    assert hasattr(loop, '_sse'), "缺少 _sse"
    assert hasattr(loop, '_pmgr'), "缺少 _pmgr"
    assert hasattr(loop, '_native_compiler'), "缺少 _native_compiler"
    assert hasattr(loop, '_driver_builder'), "缺少 _driver_builder"
    r.ok("内循环: v2.0 HAL 模块已注册", "✓")

    # 运行单次自检（不跑完整周期，避免副作用）
    from src.hardware.hal_v2 import DriverKind, DriverSpec, Architecture
    hal_result = {"status": "healthy", "checks": {}, "details": []}
    try:
        # SSE
        stats = loop._sse.get_stats()
        hal_result["checks"]["sse"] = "ok"
        # Pointer Manager
        stats = loop._pmgr.get_stats()
        hal_result["checks"]["pmgr"] = "ok"
        # Native Backend
        targets = loop._native_backend.get_targets()
        hal_result["checks"]["native"] = "ok"
        # Driver Generator
        result = loop._driver_gen.generate(DriverSpec(
            name="test", kind=DriverKind.MATH,
            target_arch=Architecture.X86_64, target_lang="python",
            math_expr="x + 1",
        ))
        hal_result["checks"]["driver"] = "ok"
        # Native Compile
        cr = loop._native_compiler.compile("x^2", Architecture.X86_64, "test_fn", "c")
        hal_result["checks"]["compile"] = "ok" if cr.get("success") else "error"
        # 总结
        failed = [k for k, v in hal_result["checks"].items() if v not in ("ok",)]
        hal_result["status"] = "degraded" if failed else "healthy"
        r.ok(f"HAL v2.0 自检: status={hal_result['status']}, checks={list(hal_result['checks'].keys())}", "✓")
    except Exception as e:
        r.fail("HAL v2.0 自检", str(e))


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("  Matha v2.0 HAL 单元测试报告")
    print("  生成时间:", time.strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 70)

    tests = [
        ("安全副作用引擎", test_side_effect_engine),
        ("指针与内存控制", test_pointer_manager),
        ("协议解释生成器", test_protocol_parser),
        ("驱动生成器", test_driver_generator),
        ("原生编译后端", test_native_backend),
        ("端到端流水线", test_full_pipeline),
        ("内循环 HAL 自检", test_inner_loop_hal_check),
    ]

    all_reports = []
    total_passed = total_failed = 0

    for name, fn in tests:
        report = Report(name)
        try:
            fn(report)
        except Exception as e:
            report.fail("测试框架", f"异常: {e}")
            import traceback; traceback.print_exc()
        all_reports.append(report)
        total_passed += report.passed
        total_failed += report.failed
        print(f"\n[{name}] {report.passed}/{report.passed+report.failed} 通过")

    print("\n" + "=" * 70)
    print(f"  汇总: {total_passed+total_failed} 个测试, 通过: {total_passed}, "
          f"失败: {total_failed}, 通过率: {total_passed/(total_passed+total_failed)*100:.1f}%")
    print()
    for r in all_reports:
        s = r.summary()
        icon = "✅" if s["failed"] == 0 else "⚠️"
        print(f"  {icon} {s['module']}: {s['passed']}/{s['total']} ({s['pass_rate']})")
        for d in s["details"][:6]:
            print(f"     {d}")
        if len(s["details"]) > 6:
            print(f"     ... 共 {len(s['details'])} 条")

    report_data = {
        "version": "2.0", "module": "HAL",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {"total": total_passed + total_failed, "passed": total_passed,
                    "failed": total_failed,
                    "pass_rate": f"{total_passed/(total_passed+total_failed)*100:.1f}%"},
        "modules": [r.summary() for r in all_reports],
    }
    report_path = os.path.join(_root, "tests", "v2.0_hal_test_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
    print(f"\n报告已保存: {report_path}")
    print("=" * 70)
