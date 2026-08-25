# -*- coding: utf-8 -*-
"""测试新增 builtin 和领域模块。

Matha 函数应用为柯里化：多参函数用 f(a)(b) 语法。
多参函数调用 f(a, b) 在 Matha 中不被支持（会被解析为字符串）。
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.interp import interpret

passed = 0
failed = 0

def check(name, actual, expected):
    global passed, failed
    if actual == expected:
        passed += 1
        print(f"  ✓ {name}: {actual}")
    else:
        failed += 1
        print(f"  ✗ {name}: 期望 {expected}, 实际 {actual}")

def run_approx(name, src, expected, tol=1e-6):
    global passed, failed
    try:
        out, trace = interpret(src)
        result = out[0] if out else None
        if isinstance(result, (int, float)) and isinstance(expected, (int, float)):
            if abs(result - expected) < tol:
                passed += 1
                print(f"  ✓ {name}: {result}")
            else:
                failed += 1
                print(f"  ✗ {name}: 期望 {expected}, 实际 {result}")
        else:
            check(name, result, expected)
    except Exception as e:
        failed += 1
        print(f"  ✗ {name}: 异常 {type(e).__name__}: {e}")

def run(name, src, expected):
    global passed, failed
    try:
        out, trace = interpret(src)
        result = out[0] if out else None
        check(name, result, expected)
    except Exception as e:
        failed += 1
        print(f"  ✗ {name}: 异常 {type(e).__name__}: {e}")

print("=" * 60)
print("新增 builtin 测试")
print("=" * 60)

# --- 文件 I/O ---
print("\n=== 文件 I/O ===")
test_path = "/tmp/matha_test_io.txt"
if os.path.exists(test_path):
    os.remove(test_path)

run("写文件", f'#：{{ 写文件("{test_path}")("Hello") }}', None)
run("读文件", f'#：{{ [读文件("{test_path}")] }}', "Hello")
run("追加文件", f'#：{{ 追加文件("{test_path}")(" World") }}', None)
run("读追加后", f'#：{{ [读文件("{test_path}")] }}', "Hello World")

# --- 字符串操作（单参） ---
print("\n=== 字符串操作 ===")
run("去空白", '#1：[去空白("  hello  ")]', "hello")
run("小写", '#1：[小写("Hello")]', "hello")
run("大写", '#1：[大写("hello")]', "HELLO")

# --- 列表操作（单参） ---
print("\n=== 列表操作 ===")
run("反转", '#1：[反转([1, 2, 3])]', [3, 2, 1])
run("求和", '#1：[求和([1, 2, 3, 4, 5])]', 15)
run("去重", '#1：[去重([1, 2, 2, 3, 3, 3])]', [1, 2, 3])

# --- 化学 ---
print("\n=== 化学 ===")
run("摩尔质量H2O", '#1：[摩尔质量("H2O")]', 18.015)
run("摩尔质量CO2", '#1：[摩尔质量("CO2")]', 44.01)
run("溶液浓度", '#1：[溶液浓度(0.5)(2)]', 0.25)
run("pH计算", '#1：[pH计算(0.0000001)]', 7.0)
run("pOH计算", '#1：[pOH计算(0.0000000001)]', 10.0)
run("Henderson方程", '#1：[Henderson方程(4.76)(0.1)(0.1)]', 4.76)
run("Gibbs自由能", '#1：[Gibbs自由能(1000)(2)(300)]', 400.0)
run("平衡常数", '#1：[平衡常数(0)(300)]', 1.0)
run("烷烃通式_C3", '#1：[烷烃通式(3)]', "C3H8")
run("烯烃通式_C4", '#1：[烯烃通式(4)]', "C4H8")
run("同分异构体数_C5", '#1：[同分异构体数(5)]', 3)
run("不饱和度_C6H12", '#1：[不饱和度("C6H12")]', 1.0)

# --- 电气 ---
print("\n=== 电气 ===")
run("欧姆定律", '#1：[欧姆定律(12)(4)]', 3.0)
run("电功率", '#1：[电功率(12)(2)]', 24)
run("分压公式", '#1：[分压公式(10)(1000)(2000)]', 6.666666666666667)
run("感抗", '#1：[感抗(50)(0.01)]', 3.141592653589793)
run("容抗", '#1：[容抗(50)(0.000001)]', 3183.098861837907)
run("功率因数", '#1：[功率因数(10)(10)]', 1.0)
run("RC截止频率", '#1：[RC截止频率(1000)(0.000001)]', 159.15494309189535)
run("奈奎斯特速率", '#1：[奈奎斯特速率(1000)]', 2000.0)

# --- 经济学 ---
print("\n=== 经济学 ===")
run_approx("复利终值", '#1：[复利终值(1000)(0.05)(3)]', 1157.625)
run_approx("复利现值", '#1：[复利现值(1157.63)(0.05)(3)]', 1000.0, tol=0.01)
run_approx("年金现值", '#1：[年金现值(100)(0.05)(5)]', 432.95, tol=0.01)
run("单利终值", '#1：[单利终值(1000)(0.05)(3)]', 1150.0)
run("需求价格弹性", '#1：[需求价格弹性(10)(100)(-5)]', -0.5)
run("消费者剩余", '#1：[消费者剩余([100, 1])(50)]', 1250.0)
run("GDP支出法", '#1：[GDP支出法(500)(200)(100)(50)(30)]', 820)
run_approx("乘数效应", '#1：[乘数效应(0.8)]', 5.0)
run("通货膨胀率", '#1：[通货膨胀率(100)(105)]', 5.0)
run("人均GDP", '#1：[人均GDP(1000000)(1000)]', 1000.0)

# --- 计算机科学 ---
print("\n=== 计算机科学 ===")
run("香农熵", '#1：[香农熵([0.5, 0.5])]', 1.0)
run("信息量", '#1：[信息量(0.25)]', 2.0)
run("完全图边数", '#1：[完全图边数(5)]', 10)
run("树边数", '#1：[树边数(5)]', 4)
run("真值表行数", '#1：[真值表行数(3)]', 8)

print("\n" + "=" * 60)
print(f"测试结果：{passed} 通过, {failed} 失败 (共 {passed + failed})")
print("=" * 60)

if failed > 0:
    sys.exit(1)
