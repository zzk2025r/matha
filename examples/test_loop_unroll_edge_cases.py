# -*- coding: utf-8 -*-
"""
循环展开边界测试 — 复杂嵌套和条件分支场景
"""
import sys
sys.path.insert(0, r"D:\trae")
from src.matha_growth import MathaGrowthEngine

CASES = [
    # 1. 简单循环展开（应成功）
    {
        "name": "简单累加循环",
        "source": "s = 0.0\nfor i in range(4):\n    s = s + float(i)\nresult = s * 2.0\n#1：[result]",
        "should_unroll": True,
        "note": "单行 body，无嵌套",
    },
    # 2. 循环内含 if 分支（应跳过展开）
    {
        "name": "循环含 if 分支",
        "source": "s = 0.0\nfor i in range(4):\n    if i > 2:\n        s = s + float(i)\n    else:\n        s = s + 1.0\nresult = s\n#1：[result]",
        "should_unroll": False,
        "note": "body 含冒号，跳过展开",
    },
    # 3. 嵌套 for 循环（外层应跳过）
    {
        "name": "嵌套 for 循环",
        "source": "s = 0.0\nfor i in range(2):\n    for j in range(3):\n        s = s + float(i) + float(j)\nresult = s\n#1：[result]",
        "should_unroll": False,
        "note": "内层为多行 body，外层也跳过",
    },
    # 4. 循环变量与外部同名（body 是单行，应展开）
    {
        "name": "循环变量与外部同名",
        "source": "i = 10.0\nfor i in range(3):\n    i = i + 1.0\nresult = i\n#1：[result]",
        "should_unroll": True,
        "note": "body 是单行 i=i+1.0，应展开；常量传播后续处理",
    },
    # 5. 大循环（超出 MAX_UNROLL_FACTOR）
    {
        "name": "大循环（超出限制）",
        "source": "s = 0.0\nfor i in range(20):\n    s = s + float(i)\nresult = s\n#1：[result]",
        "should_unroll": False,
        "note": "N=20 > MAX_UNROLL_FACTOR=8，跳过",
    },
    # 6. 无累加器的简单循环
    {
        "name": "无累加器循环",
        "source": "for i in range(3):\n    x = float(i) * 2.0\nresult = x\n#1：[result]",
        "should_unroll": True,
        "note": "单行 body，无累加器冲突",
    },
    # 7. 循环体含表达式
    {
        "name": "循环体含表达式",
        "source": "s = 0.0\nfor i in range(3):\n    s = s + float(i) * 2.0\nresult = s\n#1：[result]",
        "should_unroll": True,
        "note": "单行 body，含表达式，可展开",
    },
    # 8. 循环后紧跟赋值（无空行）
    {
        "name": "循环紧接赋值",
        "source": "for i in range(3):\n    t = float(i)\nu = t + 1.0\nresult = u\n#1：[result]",
        "should_unroll": True,
        "note": "单行 body，紧接后续赋值",
    },
    # 9. while 循环（不应展开）
    {
        "name": "while 循环",
        "source": "i = 0\ns = 0.0\nwhile i < 3:\n    s = s + float(i)\n    i = i + 1\nresult = s\n#1：[result]",
        "should_unroll": False,
        "note": "while 循环，模式不匹配",
    },
    # 10. for 循环含函数调用
    {
        "name": "循环含函数调用",
        "source": "s = 0.0\nfor i in range(3):\n    s = s + helper(float(i))\nresult = s\n#1：[result]",
        "should_unroll": True,
        "note": "单行 body，含函数调用，可展开",
    },
]

print("=" * 60)
print("循环展开边界测试（复杂嵌套和条件分支）")
print("=" * 60)

passed = 0
for case in CASES:
    # 每次使用独立 engine，避免历史累积干扰
    eng = MathaGrowthEngine(verbose=False)
    name = case["name"]
    source = case["source"]
    should_unroll = case["should_unroll"]
    note = case["note"]

    r = eng.grow(source, max_iterations=2)
    # 累计所有迭代的优化
    all_opts = []
    for hist_r in eng.get_history():
        if hist_r.optimizations_applied:
            all_opts.extend(hist_r.optimizations_applied)
    unrolled = any("循环展开" in o for o in all_opts)

    ok = unrolled == should_unroll
    if ok:
        passed += 1

    status = "PASS" if ok else "FAIL"
    print(f"\n  [{status}] {name}")
    print(f"        期望展开: {should_unroll}, 实际: {unrolled}")
    print(f"        优化: {all_opts if all_opts else '无'}")
    print(f"        说明: {note}")
    if r.improved_source:
        lines = [l.strip() for l in r.improved_source.split('\n') if l.strip()]
        print(f"        结果: {lines[-1] if lines else ''}")

print(f"\n结果: {passed}/{len(CASES)} 通过")
