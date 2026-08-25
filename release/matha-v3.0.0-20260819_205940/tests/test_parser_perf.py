"""Parser 性能基准测试 — 检测复杂边界情况下的耗时瓶颈。

运行：python -m tests.test_parser_perf
"""
import sys, time, statistics
sys.path.insert(0, r"D:\trae")

from src.parser import parse, ParseError
from src.semantic import analyze_ast

# ============================================================
# 测试用例集合
# ============================================================

SMALL = [
    "a = 1",
    "b = 2 + 3",
    "#1：[a + b]",
    "【*/test/*】hello",
    "func f(x: Int) -> Int = (x) => x + 1",
]

MEDIUM = [
    "#：{\n" + "\n   ".join(f"a{i} = {i}" for i in range(20)) + "\n}",
    "#1：【下载 https://example.com/path?q=1&r=2&x=3】>>#2：【解析】>>#3：【输出】",
    "【*/初始化/*】setup\nx = 1\n【*/处理/*】process\ny = x + 1\n【*/输出/*】output\n#1：[y]",
    "a = 0t210\nb = 0t111\nc = 0b1010\nd = 0xFF\nresult = a + b + c + d\n#1：[result]",
    "θ = 3.14\n焻 = 42\n结果 = θ + 焻\n【*/问候/*】output\n#1：[结果]",
    "#1：【运算 1+2*3】>>#2：【处理】>>#3：【输出】\n#4：【加密】>>#5：【验证】",
]

LARGE = [
    # 深度嵌套代码块
    "#：{\n"
    "  a = 1\n"
    "  b = 2\n"
    "  c = a + b\n"
    "  #：{\n"
    "    d = 3\n"
    "    e = d * 2\n"
    "    f = c + e\n"
    "    #：{\n"
    "      g = 4\n"
    "      h = g + h\n"
    "    }\n"
    "  }\n"
    "}",
    # 长链式命令
    ">>".join(f"# {i}：【步骤{i}】" for i in range(50)),
    # 大量声明
    "\n".join(f"var{i} = {i} * {i}" for i in range(100)),
    # 混合复杂用例
    (
        "【*/数据处理/*】pipeline\n"
        "a = 0t1010\n"
        "b = 0b1111\n"
        "c = 0xFF\n"
        "d = a + b + c\n"
        "【*/验证/*】check\n"
        "result = d * 2\n"
        "#1：【加载】>>#2：【处理】>>#3：【验证】\n"
        "#4：[result]"
    ),
]

# 边界重复输入（模拟恶意 fuzz）
FUZZ = [
    " " * 1000,
    "\n" * 500,
    "a = 1\n" * 100,
    "【*/test/*】x\n" * 50,
    "#：{}\n" * 50,
    "x = " + " + ".join(str(i) for i in range(200)),
    "a = 1" + "\t" * 100 + "\n",
    "【*/" + "a" * 500 + "/*】" + "b" * 500,
]

PASS, FAIL = [], []

def benchmark(name, cases, iterations=100):
    """对一个 case 列表运行 iterations 次解析，统计耗时。"""
    total = 0
    times = []
    for _ in range(iterations):
        for case in cases:
            t0 = time.perf_counter()
            try:
                p = parse(case)
                errs = analyze_ast(p, verbose=False)
            except Exception:
                pass
            dt = time.perf_counter() - t0
            total += dt
            times.append(dt)

    if not times:
        return None

    avg = statistics.mean(times)
    median = statistics.median(times)
    p95 = sorted(times)[int(len(times) * 0.95)] if len(times) >= 20 else max(times)
    max_t = max(times)
    total_ms = total * 1000
    avg_ms = avg * 1000
    median_ms = median * 1000
    p95_ms = p95 * 1000
    max_ms = max_t * 1000

    # 判断瓶颈：预热后 median 应 < 20ms，avg 容忍 < 25ms（GC/OS 抖动显著）
    status = "✓"
    if median_ms > 20.0:
        status = "⚠"
    if avg_ms > 25.0:
        status = "✗"
        FAIL.append(name)
    else:
        PASS.append(name)

    print(f"  {status} {name:40s} avg={avg_ms:7.3f}ms  med={median_ms:7.3f}ms  p95={p95_ms:7.3f}ms  max={max_ms:7.3f}ms  total={total_ms:.1f}ms")
    return {"avg_ms": avg_ms, "median_ms": median_ms, "p95_ms": p95_ms, "max_ms": max_ms, "total_ms": total_ms}


print("=" * 80)
print("Parser 性能基准测试")
print(f"Python {sys.version.split()[0]}  |  iterations={100}")
print("=" * 80)

results = {}
print("\n【Small 简单用例 (100 iterations)】")
results["small"] = benchmark("Small simple", SMALL, 100)

print("\n【Medium 中等用例 (100 iterations)】")
results["medium"] = benchmark("Medium cases", MEDIUM, 100)

print("\n【Large 复杂用例 (20 iterations)】")
results["large"] = benchmark("Large cases", LARGE, 20)

print("\n【Fuzz 边界重复 (20 iterations)】")
results["fuzz"] = benchmark("Fuzz boundary", FUZZ, 20)

# ============================================================
# 单项耗时分析
# ============================================================
print("\n【单项耗时分析】")
single_cases = {
    "1行赋值": "a = 1",
    "10行赋值": "\n".join(f"x{i} = {i}" for i in range(10)),
    "100行赋值": "\n".join(f"x{i} = {i}" for i in range(100)),
    "1000行赋值": "\n".join(f"x{i} = {i}" for i in range(1000)),
    "10步链式": ">>".join(f"# {i}：【step{i}】" for i in range(10)),
    "50步链式": ">>".join(f"# {i}：【step{i}】" for i in range(50)),
    "100步链式": ">>".join(f"# {i}：【step{i}】" for i in range(100)),
    "NLBlock+代码": "【*/test/*】hello\na = 1\nb = 2\nc = a + b\n#1：[c]",
    "嵌套3层代码块": "#：{\n  a = 1\n  #：{\n    b = 2\n    #：{\n      c = 3\n    }\n  }\n}",
    "混合进制": "a = 0t210\nb = 0b1010\nc = 0xFF\nd = a + b + c",
}

for label, src in single_cases.items():
    n = 200 if len(src) < 500 else 50 if len(src) < 5000 else 10
    times = []
    for _ in range(n):
        t0 = time.perf_counter()
        try:
            p = parse(src)
            _, errs = analyze_source(src, verbose=False)
        except:
            pass
        times.append(time.perf_counter() - t0)
    if times:
        avg = statistics.mean(times) * 1000
        icon = "✓" if avg < 10 else "⚠"
        print(f"  {icon} {label:20s} avg={avg:8.3f}ms  (n={n})")

# ============================================================
# 汇总
# ============================================================
print("\n" + "=" * 80)
total_pass = len(PASS)
total_fail = len(FAIL)
total_cases = total_pass + total_fail
print(f"总计: {len(PASS)}/{total_cases} 通过 (median_ms < 15ms, p95_ms < 30ms)")
if FAIL:
    print(f"\n性能瓶颈 ({len(FAIL)} 个):")
    for n in FAIL:
        r = results.get(n.split(" ")[0])
        print(f"  - {n}")
else:
    print("所有场景性能正常 ✓")
print("=" * 80)

sys.exit(0 if not FAIL else 1)
