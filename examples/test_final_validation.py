# -*- coding: utf-8 -*-
"""自成长引擎优化能力最终验证"""
import sys
sys.path.insert(0, r"D:\trae")

# 清除缓存
import importlib, shutil
for mod in list(sys.modules.keys()):
    if 'matha' in mod or 'src' in mod:
        del sys.modules[mod]

from src.matha_growth import MathaGrowthEngine
engine = MathaGrowthEngine(verbose=False)

CASES = [
    ("循环展开", "s = 0.0\nfor i in range(4):\n    s = s + float(i)\nresult = s * 2.0\n#1：[result]", "result = 12.0"),
    ("嵌套函数", "def double(x):\n    return x * 2.0\ndef triple(x):\n    return x * 3.0\ndef compute(x):\n    return double(triple(x))\nresult = compute(5.0)\n#1：[result]", "result = 30.0"),
    ("常量链", "a = 10.0\nb = a + 5.0\nc = b * 2.0\nd = c - 10.0\nresult = d + 1.0\n#1：[result]", "result = 21.0"),
    ("死代码+函数", "unused = 999.0\ndef square(x):\n    return x * x\nresult = square(3.0)\n#1：[result]", "9.0"),
    ("混合优化", "unused1 = 999.0\nunused2 = 888.0\na = 10.0\nb = a + 5.0\ndef double(x):\n    return x * 2.0\ndef triple(x):\n    return x * 3.0\ndef compute(x):\n    return double(triple(x))\nresult = compute(a) + b\n#1：[result]", "result ="),
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
