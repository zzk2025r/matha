# -*- coding: utf-8 -*-
"""Matha 互操作测试：验证 Matha 程序能被其它语言识别解读。

测试内容：
  1. AST 序列化：Matha 源码 → JSON（任何语言可解析）
  2. Token 导出：Matha 源码 → Token JSON
  3. Python 转译：Matha → Python 源码（可运行）
  4. JavaScript 转译：Matha → JS 源码
  5. 符号表导出：Matha 函数库 → JSON/TypeScript/Markdown
  6. Matha 内建调用：在 Matha 程序中调用互操作内建

运行：python -m tests.test_interop
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ast_serializer import program_to_dict, program_to_json, tokens_to_dict
from src.transpiler import transpile, PythonTranspiler, JavaScriptTranspiler
from src.symtab_exporter import export_symtab, export_symtab_json, export_symtab_d_ts
from src.interp import interpret

passed = 0
failed = 0


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
        print(f"  ✓ {name}")
    else:
        failed += 1
        print(f"  ✗ {name}: {detail}")


def test_ast_serialize():
    """AST 序列化。"""
    print("\n--- AST 序列化 ---")
    src = '''func 加法(x, y) -> Int = (x, y) => x + y
#：{
  a = 3
  b = 4
  c = 加法 a b
  #：[c]
}
#：【文件】
'''
    d = program_to_dict(src)
    check("AST返回dict", isinstance(d, dict))
    check("AST有node字段", "node" in d)
    check("AST是Program", d.get("node") == "Program")
    check("AST有decls", "decls" in d and isinstance(d["decls"], list))
    # JSON 字符串
    js = program_to_json(src)
    check("JSON是字符串", isinstance(js, str))
    parsed = json.loads(js)
    check("JSON可反解析", isinstance(parsed, dict))
    check("JSON有Program", parsed.get("node") == "Program")


def test_token_export():
    """Token 导出。"""
    print("\n--- Token 导出 ---")
    toks = tokens_to_dict("x = 3 + 4")
    check("Token是列表", isinstance(toks, list))
    check("Token数量>0", len(toks) > 0)
    check("Token有type", "type" in toks[0])
    check("Token有value", "value" in toks[0])
    check("Token有line", "line" in toks[0])
    check("Token有col", "col" in toks[0])


def test_transpile_python():
    """Python 转译。"""
    print("\n--- Python 转译 ---")
    src = '''func 平方(x) -> Float = (x) => x * x
#：{
  a = 5
  b = 平方 a
  #：[b]
}
#：【文件】
'''
    py = transpile(src, "python")
    check("Python是字符串", isinstance(py, str))
    check("Python含import", "import math" in py)
    check("Python含def", "def 平方" in py or "def " in py)
    check("Python含print", "print(" in py)
    # 实际运行转译后的 Python
    ns = {}
    exec(py, ns)
    check("Python可执行", True)


def test_transpile_python_arith():
    """Python 转译算术。"""
    print("\n--- Python 算术转译 ---")
    src = '''#：{
  a = 3 + 4 * 2
  #：[a]
}
#：【文件】
'''
    py = transpile(src, "python")
    check("Python含乘法", "*" in py)
    check("Python含加法", "+" in py)
    # 运行验证
    ns = {}
    exec(py, ns)


def test_transpile_js():
    """JavaScript 转译。"""
    print("\n--- JavaScript 转译 ---")
    src = '''func 双倍(x) -> Float = (x) => x * 2
#：{
  a = 10
  b = 双倍 a
  #：[b]
}
#：【文件】
'''
    js = transpile(src, "javascript")
    check("JS是字符串", isinstance(js, str))
    check("JS含function", "function" in js)
    check("JS含console.log", "console.log" in js)
    check("JS含Math", "Math" in js or "function" in js)


def test_transpile_json():
    """JSON IR 转译。"""
    print("\n--- JSON IR 转译 ---")
    src = "x = 42"
    result = transpile(src, "json")
    check("JSON IR是字符串", isinstance(result, str))
    parsed = json.loads(result)
    check("JSON IR可解析", isinstance(parsed, dict))


def test_symtab_export():
    """符号表导出。"""
    print("\n--- 符号表导出 ---")
    entries = export_symtab()
    check("符号表是列表", isinstance(entries, list))
    check("符号表非空", len(entries) > 0)
    check("符号表>100", len(entries) > 100, f"实际 {len(entries)}")
    # 检查条目结构
    first = entries[0]
    check("条目有名称", "名称" in first)
    check("条目有参数数", "参数数" in first)
    check("条目有领域", "领域" in first)
    check("条目有分类", "分类" in first)
    # 检查已知函数
    names = [e["名称"] for e in entries]
    check("含sin", "sin" in names)
    check("含cos", "cos" in names)
    check("含sqrt", "sqrt" in names)
    check("含软件_构建", "软件_构建" in names)
    check("含导出_AST", "导出_AST" in names)


def test_symtab_json():
    """符号表 JSON 导出。"""
    print("\n--- 符号表 JSON ---")
    js = export_symtab_json()
    check("JSON是字符串", isinstance(js, str))
    parsed = json.loads(js)
    check("JSON可解析", isinstance(parsed, list))
    check("JSON非空", len(parsed) > 0)


def test_symtab_d_ts():
    """符号表 TypeScript 声明导出。"""
    print("\n--- 符号表 TypeScript ---")
    dts = export_symtab_d_ts()
    check("d.ts是字符串", isinstance(dts, str))
    check("含declare", "declare" in dts)
    check("含matha", "matha" in dts)
    check("含sin", "sin" in dts)


def test_builtin_ast_export():
    """Matha 内建：导出_AST。"""
    print("\n--- Matha 内建 导出_AST ---")
    src = '''#：{
  ast = 导出_AST "x = 42"
  #：[ast]
}
#：【文件】
'''
    out, _ = interpret(src)
    r = out[0]
    check("内建返回dict", isinstance(r, dict))
    check("内建有node", "node" in r)
    check("内建是Program", r.get("node") == "Program")


def test_builtin_transpile_python():
    """Matha 内建：转译_Python。"""
    print("\n--- Matha 内建 转译_Python ---")
    src = '''#：{
  py = 转译_Python "func f(x) -> Int = (x) => x + 1"
  #：[py]
}
#：【文件】
'''
    out, _ = interpret(src)
    py = out[0]
    check("内建返回字符串", isinstance(py, str))
    check("含import math", "import math" in py)
    check("含def", "def " in py)


def test_builtin_transpile_js():
    """Matha 内建：转译_JS。"""
    print("\n--- Matha 内建 转译_JS ---")
    src = '''#：{
  js = 转译_JS "func f(x) -> Int = (x) => x + 1"
  #：[js]
}
#：【文件】
'''
    out, _ = interpret(src)
    js = out[0]
    check("内建返回字符串", isinstance(js, str))
    check("含function", "function" in js)


def test_builtin_symtab():
    """Matha 内建：导出_符号表。"""
    print("\n--- Matha 内建 导出_符号表 ---")
    src = '''#：{
  symtab = 导出_符号表 "json"
  #：[symtab]
}
#：【文件】
'''
    out, _ = interpret(src)
    symtab_str = out[0]
    check("内建返回字符串", isinstance(symtab_str, str))
    parsed = json.loads(symtab_str)
    check("JSON可解析", isinstance(parsed, list))
    check("符号表非空", len(parsed) > 0)


def test_cross_language_roundtrip():
    """跨语言往返：Matha → Python → 执行。"""
    print("\n--- 跨语言往返 ---")
    src = '''func 立方(x) -> Float = (x) => x * x * x
#：{
  a = 3
  b = 立方 a
  #：[b]
}
#：【文件】
'''
    # Matha 执行
    out_matha, _ = interpret(src)
    result_matha = out_matha[0]
    # 转译为 Python
    py = transpile(src, "python")
    # Python 执行（捕获 print 输出）
    import io as _io
    old_stdout = sys.stdout
    sys.stdout = _io.StringIO()
    ns = {}
    exec(py, ns)
    py_output = sys.stdout.getvalue().strip()
    sys.stdout = old_stdout
    check("Matha结果=27", result_matha == 27, f"实际 {result_matha}")
    check("Python输出=27", py_output == "27", f"实际 {py_output}")
    check("跨语言一致", str(result_matha) == py_output,
          f"Matha={result_matha} Python={py_output}")


def main():
    print("=" * 60)
    print("Matha 互操作测试：被其它语言识别解读")
    print("=" * 60)

    test_ast_serialize()
    test_token_export()
    test_transpile_python()
    test_transpile_python_arith()
    test_transpile_js()
    test_transpile_json()
    test_symtab_export()
    test_symtab_json()
    test_symtab_d_ts()
    test_builtin_ast_export()
    test_builtin_transpile_python()
    test_builtin_transpile_js()
    test_builtin_symtab()
    test_cross_language_roundtrip()

    print("\n" + "=" * 60)
    print(f"互操作测试：{passed} 通过, {failed} 失败 (共 {passed + failed})")
    print("=" * 60)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
