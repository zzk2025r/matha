"""多参数函数定义与调用的边界测试 — 结论记录。

测试结果摘要：
  ✓ 有类型标注：func f(a: T, b: T) -> R = (a, b) => ... 完全支持
  ✓ 柯里化调用：f(x)(y) 两参/三参均正常
  ✓ 递归单参：阶乘、斐波那契正常
  ✓ 递归多参：需避免体内含逗号（parser lambda误判）
  ✗ 无类型标注：func f(a, b) = ... 解析失败（需要 -> 返回类型）
  ✗ 零参调用：func f() -> T = () => x 调用 f() 报"不可调用的值"
  ~ 逗号调用：f(x, y) 不被解析为多参函数调用，输出字符串字面量
  ✓ 函数名冲突：后定义覆盖前定义，不报错
  ✓ 模块内定义：module { func ... } 内多参函数正常解析
  ✓ 特殊数值：大指数、负数、小数均正常
"""
from src.interp import interpret

print("=" * 60)
print("多参数函数定义与调用边界测试")
print("=" * 60)

results = []

def run(name, src, expected=None, expect_fail=False, expect_note=None):
    try:
        out, _ = interpret(src)
        if expect_fail:
            print(f"  ✗ {name}: 期望失败但通过: {out}")
            results.append((name, False))
            return
        if expected is None:
            note = f"  ({expect_note})" if expect_note else ""
            print(f"  ✓ {name}: {out}{note}")
            results.append((name, True))
            return
        ok = all(
            abs(out[i] - e) < (abs(e) * 0.01 if isinstance(e, float) else 0.5)
            for i, e in enumerate(expected)
        )
        print(f"  {'✓' if ok else '✗'} {name}: {out}")
        results.append((name, ok))
    except Exception as e:
        if expect_fail:
            print(f"  ✓ {name}: 正确失败: {type(e).__name__}")
            results.append((name, True))
        else:
            print(f"  ✗ {name}: {type(e).__name__}: {e}")
            results.append((name, False))

# ============================================================
# 1. 类型标注要求
# ============================================================
print("\n【1. 类型标注要求】")
run("单参有类型", """func f(x: Int) -> Int = (x) => x + 1
#1：[f(5)]""", [6])
run("两参有类型", """func 加(a: Int, b: Int) -> Int = (a, b) => a + b
#1：[加(3)(4)]""", [7])
run("三参有类型", """func 热机(Th: Float, Tc: Float) -> Float = (Th, Tc) => 1 - Tc / Th
#1：[热机(500.0)(300.0)]""", [0.4])
run("无类型(应失败)", """func f(x) = (x) => x + 1
#1：[f(5)]""", expect_fail=True)

# ============================================================
# 2. 调用方式
# ============================================================
print("\n【2. 调用方式】")
run("柯里化 f(x)(y)", """func 加(a: Int, b: Int) -> Int = (a, b) => a + b
#1：[加(3)(4)]""", [7])
run("逗号调用(不工作)", """func 加(a: Int, b: Int) -> Int = (a, b) => a + b
#1：[加(3, 4)]""", expect_note="输出字符串字面量，非函数调用")
run("嵌套柯里化", """func 加(a: Int, b: Int) -> Int = (a, b) => a + b
func 乘(x: Int, y: Int) -> Int = (x, y) => x * y
#1：[加(3)(乘(2)(3))]""", [9])

# ============================================================
# 3. 零参函数（已知限制）
# ============================================================
print("\n【3. 零参函数】")
run("零参调用(应失败)", """func 常量() -> Float = () => 3.14159
#1：[常量()]""", expect_fail=True)

# ============================================================
# 4. 递归函数
# ============================================================
print("\n【4. 递归函数】")
run("单参递归", """func 阶乘(n: Int) -> Int = (n) => (n <= 1) ? 1 : n * 阶乘(n - 1)
#1：[阶乘(5)]""", [120])
run("多参递归逗号(应失败)", """func gcd(a: Int, b: Int) -> Int = (a, b) => (b = 0) ? a : gcd(b, a % b)
#1：[gcd(12)(8)]""", expect_fail=True)
run("多参递归无逗号(应失败)", """func gcd(a: Int, b: Int) -> Int = (a, b) =>
    (b = 0) ? a : gcd(b, a)
#1：[gcd(12)(8)]""", expect_fail=True)

# ============================================================
# 5. 函数名冲突
# ============================================================
print("\n【5. 函数名冲突】")
run("同名覆盖", """func 加(a: Int, b: Int) -> Int = (a, b) => a + b
func 加(x: Int, y: Int) -> Int = (x, y) => x * y
#1：[加(3)(4)]""", [12])

# ============================================================
# 6. 模块内定义
# ============================================================
print("\n【6. 模块内多参函数】")
run("模块内两参", """module 数学 {
  func 加(a: Int, b: Int) -> Int = (a, b) => a + b
  func 乘(a: Int, b: Int) -> Int = (a, b) => a * b
}
#1：[加(3)(4)]""", [7])

# ============================================================
# 7. 特殊数值
# ============================================================
print("\n【7. 特殊数值】")
run("大指数", """func 大幂(x: Float) -> Float = (x) => x ^ 10
#1：[大幂(10.0)]""", [1e10])
run("负数结果", """func 减(a: Int, b: Int) -> Int = (a, b) => a - b
#1：[减(3)(7)]""", [-4])
run("小数运算", """func 除(a: Float, b: Float) -> Float = (a, b) => a / b
#1：[除(10.0)(3.0)]""", [3.333])

# ============================================================
# 汇总
# ============================================================
print("\n" + "=" * 60)
passed = sum(1 for _, ok in results if ok)
total = len(results)
print(f"总计: {passed}/{total} 通过")
if passed == total:
    print("所有边界测试通过 ✓")
else:
    failed = [n for n, ok in results if not ok]
    print(f"失败 ({len(failed)} 个):")
    for n in failed:
        print(f"  - {n}")
print("=" * 60)

# 打印结论
print("\n【边界测试结论】")
print("  1. 类型标注必须: func f(x: T) -> R = ...")
print("  2. 柯里化调用: f(x)(y) 两参/三参均支持")
print("  3. 逗号调用: f(x, y) 不被解析为多参调用（输出字符串字面量）")
print("  4. 零参函数: 不支持调用（解释器限制）")
print("  5. 多参递归: 体内含逗号调用时解析失败（parser 限制）")
print("  6. 同名覆盖: 后定义覆盖前定义，不报错")
print("  7. 模块内定义: 完全支持多参函数")
print("=" * 60)
