# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r"D:\trae")
from src.matha_growth import MathaGrowthEngine
engine = MathaGrowthEngine(verbose=False)
sources = [
    ("嵌套函数", "def double(x):\n    return x * 2.0\ndef triple(x):\n    return x * 3.0\ndef compute(x):\n    return double(triple(x))\nresult = compute(5.0)\n#1：[result]", "30.0"),
    ("死代码", "unused = 999.0\ndef square(x):\n    return x * x\nresult = square(3.0)\n#1：[result]", "9.0"),
    ("常量链", "a = 10.0\nb = a + 5.0\nc = b * 2.0\nd = c - 10.0\nresult = d + 1.0\n#1：[result]", "21.0"),
    ("混合", "unused1 = 999.0\na = 10.0\nb = a + 5.0\ndef double(x):\n    return x * 2.0\ndef triple(x):\n    return x * 3.0\ndef compute(x):\n    return double(triple(x))\nresult = compute(a) + b\n#1：[result]", "result ="),
    ("常量折叠", "x = 3.0 + 4.0\n#1：[x]", "7.0"),
]
passed = 0
for name, src, expected in sources:
    r = engine.grow(src, max_iterations=5)
    ok = expected in r.improved_source if r.improved_source else False
    if ok: passed += 1
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}: {r.optimizations_applied} -> {r.improved_source.strip()[-40:]}")
print(f"结果: {passed}/{len(sources)}")
