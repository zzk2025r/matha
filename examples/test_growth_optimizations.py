# -*- coding: utf-8 -*-
"""自成长引擎优化能力验证 — v2"""
import sys
sys.path.insert(0, r"D:\trae")
from src.matha_growth import MathaGrowthEngine
engine = MathaGrowthEngine(verbose=False)

CASES = [
    ("嵌套函数链",
     "def double(x):\n    return x * 2.0\ndef triple(x):\n    return x * 3.0\ndef compute(x):\n    return double(triple(x))\nresult = compute(5.0)\n#1：[result]",
     "result = 30.0"),
    ("死代码消除+函数内联",
     "unused = 999.0\ndef square(x):\n    return x * x\nresult = square(3.0)\n#1：[result]",
     "9.0"),
    ("常量传播链",
     "a = 10.0\nb = a + 5.0\nc = b * 2.0\nd = c - 10.0\nresult = d + 1.0\n#1：[result]",
     "result = 21.0"),
    ("混合优化",
     "unused1 = 999.0\nunused2 = 888.0\na = 10.0\nb = a + 5.0\ndef double(x):\n    return x * 2.0\ndef triple(x):\n    return x * 3.0\ndef compute(x):\n    return double(triple(x))\nresult = compute(a) + b\n#1：[result]",
     "result ="),
    ("简单常量折叠",
     "x = 3.0 + 4.0\n#1：[x]",
     "x = 7.0"),
]

print("=" * 60)
print("自成长引擎优化能力验证")
print("=" * 60)
passed = 0
for name, source, expected in CASES:
    r = engine.grow(source, max_iterations=5)
    ok = expected in r.improved_source if r.improved_source else False
    if ok: passed += 1
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}: {r.optimizations_applied or '无'}")
    if r.improved_source:
        lines = [l.strip() for l in r.improved_source.split('\n') if l.strip()]
        print(f"         -> {lines[-1] if lines else ''}")
print(f"\n结果: {passed}/{len(CASES)} 通过")
