# -*- coding: utf-8 -*-
"""不含 # 的样例集合：检验两前端共同支持子集上的定点一致性。"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path('.').resolve()))
import tools_m2_probe as P

CASES = {
    "绑定": "x = 5",
    "算术": "y = 1 + 2 * 3",
    "字符串": 's = "hi"',
    "列表": "L = [1, 2, 3]",
    "空列表": "L = []",
    "字典": 'd = {"a": 1, "b": 2}',
    "下标": "L = [10, 20, 30]\nz = L[1]",
    "字段": 'd = {"a": 1}\nz = d["a"]',
    "一元负": "z = -5",
    "比较": "z = (3 < 5)",
    "真值": "z = true",
    "函数": "func f(a: Int) -> Int = (a) => a * 2",
    "双参函数": "func g(a: Int, b: Int) -> Int = (a, b) => a - b",
    "递归": "func fact(n: Int) -> Int = (n) =>\n"
            "  if n <= 1 then 1 else n * fact(n - 1)",
    "let": "z = let a = 2 in a + 3",
    "lambda绑定": "g = (x) => x + 1",
    "if语句": "func f(n: Int) -> Int = (n) => if n >= 0 then 1 else -1",
    "while块": "func f(n: Int) -> Int = (n) => {\n"
               "  s = 0\n  i = 1\n"
               "  while i <= n { s = s + i\n i = i + 1 }\n  s\n}",
    "for": "func f(xs: List) -> Int = (xs) => {\n"
           "  s = 0\n"
           "  for x in xs { s = s + x }\n  s\n}",
    "多返回元组": "func f(n: Int) -> (Int, Int) = (n) => (n, n + 1)",
    "enum": "enum 色 {\n  红\n  绿\n}",
    "struct": "struct 点 { x: Int, y: Int }",
    "module": "module 主程序 {\n  func f(a: Int) -> Int = (a) => a\n}",
    "use": "module 主程序 {\n  use 标准库 { list_sort }\n}",
    "嵌套调用": "func a1(x: Int) -> Int = (x) => x + 1\n"
                "func b1(x: Int) -> Int = (x) => x * 3\n"
                "z = b1(a1(2))",
    "双参调用": "func g(a: Int, b: Int) -> Int = (a, b) => a - b\nz = g(10, 3)",
}

vm = P.build_stage1()
ok = 0
total = 0
for name, src in CASES.items():
    total += 1
    try:
        h = P.canon(P.host_compile(src))
    except Exception as e:  # noqa: BLE001
        print(f"  [HOST-FAIL] {name}: {type(e).__name__}: {e}")
        continue
    try:
        s = P.canon(P.self_dict_to_module(vm.call("编译", src)))
    except Exception as e:  # noqa: BLE001
        print(f"  [SELF-FAIL] {name}: {type(e).__name__}: {e}")
        continue
    d = P.first_diff(h, s)
    if d is None:
        print(f"  [ OK ] {name}")
        ok += 1
    else:
        print(f"  [DIFF] {name}: {d}")
print(f"\n一致 {ok}/{total}")
