"""Matha 自举代码生成测试。

验证 Matha 自身语言能正确解析、语义校验，并通过解释器执行
代码生成内建函数（生成_网页/生成_桌面/生成_服务/生成_系统），
产出与 Python codegen 等价的 Python/HTML 代码。
"""

import os
import sys
import tempfile
import json
import ast as _ast

sys.path.insert(0, r"D:\trae")

from src.interp import interpret, Interpreter
from src.parser import parse
from src.semantic import analyze_source
from src.codegen import codegen

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


def _run_matha_src(src: str):
    """执行 Matha 源码（写入临时文件后执行）。"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.matha', delete=False, encoding='utf-8') as f:
        f.write(src)
        path = f.name
    try:
        with open(path, encoding='utf-8') as f:
            return interpret(f.read())
    finally:
        os.unlink(path)


def _matha_json_str(py_obj) -> str:
    """把 Python 对象序列化为可在 Matha 字符串中正确解析的 JSON 字符串。"""
    raw = json.dumps(py_obj, ensure_ascii=False)
    return raw.replace('"', '\\"')


def _find_files(directory: str, suffix: str) -> list:
    result = []
    if not directory:
        return result
    for root, dirs, files in os.walk(directory):
        for f in files:
            if f.endswith(suffix):
                result.append(os.path.join(root, f))
    return result


def _get_output_dir(kind: str, name: str) -> str:
    """获取 Matha codegen 默认输出目录。"""
    return os.path.join(r"D:\trae", "matha", "output", kind, name)


# ============================================================
# 1. 网页生成对比
# ============================================================
def test_web_matha_vs_codegen():
    print("\n=== 1. 网页生成对比 ===")
    spec = ["应用", "网页", "对比测试", [
        ["h1", "Matha 网页生成对比", [], []],
        ["p", "这是由 Matha 规格生成的页面", [], []],
        ["button", "点击我", [["onclick", "alert('Matha!')"]], []],
        ["input", "", [["id", "test"], ["placeholder", "输入文本"]], []],
    ]]
    extra = [["背景", "#f5f5f5"]]

    with tempfile.TemporaryDirectory() as d:
        r_py = codegen(spec + extra, d)
        check("Python codegen 网页成功", r_py.成功, r_py.错误 or "")
        html_py = ""
        if r_py.成功:
            with open(r_py.入口, encoding="utf-8") as f:
                html_py = f.read()

    interp = Interpreter()
    r_matha = interp.call("生成_网页", spec + extra)
    check("Matha 网页生成成功", r_matha.get("成功"), r_matha.get("错误", ""))

    output_dir = _get_output_dir("网页", "对比测试")
    html_files = _find_files(output_dir, ".html")
    html_matha = ""
    if html_files:
        with open(html_files[0], encoding="utf-8") as f:
            html_matha = f.read()

    if html_py and html_matha:
        check("标题一致", 'Matha 网页生成对比' in html_py and 'Matha 网页生成对比' in html_matha)
        check("按钮一致", "alert('Matha!')" in html_py and "alert('Matha!')" in html_matha)
        check("输入框一致", 'id="test"' in html_py and 'id="test"' in html_matha)
    else:
        check("文件生成对比", False, f"py={bool(html_py)}, matha={bool(html_matha)}")


# ============================================================
# 2. 桌面应用生成对比
# ============================================================
def test_desktop_matha_vs_codegen():
    print("\n=== 2. 桌面应用生成对比 ===")
    spec = ["应用", "桌面", "对比测试", [
        ["h1", "Matha 桌面应用", [], []],
        ["label", "姓名：", [], []],
        ["input", "", [["width", "20"]], []],
        ["button", "提交", [["onclick", "submit()"]], []],
    ]]
    extra = [["尺寸", "400x300"]]

    with tempfile.TemporaryDirectory() as d:
        r_py = codegen(spec + extra, d)
        check("Python codegen 桌面成功", r_py.成功, r_py.错误 or "")
        py_py = ""
        if r_py.成功:
            with open(r_py.入口, encoding="utf-8") as f:
                py_py = f.read()

    interp = Interpreter()
    r_matha = interp.call("生成_桌面", spec + extra)
    check("Matha 桌面生成成功", r_matha.get("成功"), r_matha.get("错误", ""))

    output_dir = _get_output_dir("桌面", "对比测试")
    py_files = _find_files(output_dir, "main.py")
    py_matha = ""
    if py_files:
        with open(py_files[0], encoding="utf-8") as f:
            py_matha = f.read()

    if py_py and py_matha:
        check("含 tkinter 导入", "import tkinter" in py_py and "import tkinter" in py_matha)
        check("含标题", 'root.title("对比测试")' in py_py and 'root.title("对比测试")' in py_matha)
        check("含按钮", "tk.Button" in py_py and "tk.Button" in py_matha)
        check("含 submit 函数", "def submit" in py_py and "def submit" in py_matha)
        try:
            _ast.parse(py_py)
            check("Python codegen 语法合法", True)
        except SyntaxError as e:
            check("Python codegen 语法合法", False, str(e))
        try:
            _ast.parse(py_matha)
            check("Matha 生成 Python 语法合法", True)
        except SyntaxError as e:
            check("Matha 生成 Python 语法合法", False, str(e))
    else:
        check("文件生成对比", False, f"py={bool(py_py)}, matha={bool(py_matha)}")


# ============================================================
# 3. 后端服务生成对比
# ============================================================
def test_backend_matha_vs_codegen():
    print("\n=== 3. 后端服务生成对比 ===")
    spec = ["应用", "服务", "对比测试", [
        ["接口", "GET", "/api/hello", '{"msg": "你好 Matha"}'],
        ["接口", "POST", "/api/echo", "echo"],
    ]]

    with tempfile.TemporaryDirectory() as d:
        r_py = codegen(spec, d)
        check("Python codegen 后端成功", r_py.成功, r_py.错误 or "")
        py_py = ""
        if r_py.成功:
            with open(r_py.入口, encoding="utf-8") as f:
                py_py = f.read()

    interp = Interpreter()
    r_matha = interp.call("生成_服务", spec)
    check("Matha 后端生成成功", r_matha.get("成功"), r_matha.get("错误", ""))

    output_dir = _get_output_dir("服务", "对比测试")
    py_files = _find_files(output_dir, "server.py")
    py_matha = ""
    if py_files:
        with open(py_files[0], encoding="utf-8") as f:
            py_matha = f.read()

    if py_py and py_matha:
        check("含 HTTPServer", "HTTPServer" in py_py and "HTTPServer" in py_matha)
        check("含 /api/hello", "/api/hello" in py_py and "/api/hello" in py_matha)
        check("含 /api/echo", "/api/echo" in py_py and "/api/echo" in py_matha)
        check("含 8080 端口", "8080" in py_py and "8080" in py_matha)
        try:
            _ast.parse(py_py)
            check("Python codegen 语法合法", True)
        except SyntaxError as e:
            check("Python codegen 语法合法", False, str(e))
        try:
            _ast.parse(py_matha)
            check("Matha 生成 Python 语法合法", True)
        except SyntaxError as e:
            check("Matha 生成 Python 语法合法", False, str(e))
    else:
        check("文件生成对比", False, f"py={bool(py_py)}, matha={bool(py_matha)}")


# ============================================================
# 4. 系统脚本生成对比
# ============================================================
def test_system_matha_vs_codegen():
    print("\n=== 4. 系统脚本生成对比 ===")
    spec = ["应用", "系统", "对比测试", [
        ["接口", "目录", "build", ""],
        ["接口", "命令", "", "echo 部署完成"],
    ]]

    with tempfile.TemporaryDirectory() as d:
        r_py = codegen(spec, d)
        check("Python codegen 系统成功", r_py.成功, r_py.错误 or "")

    interp = Interpreter()
    r_matha = interp.call("生成_系统", spec)
    check("Matha 系统生成成功", r_matha.get("成功"), r_matha.get("错误", ""))

    output_dir = _get_output_dir("系统", "对比测试")
    sh_files = _find_files(output_dir, ".sh")
    bat_files = _find_files(output_dir, ".bat")
    check("生成 .sh 脚本", len(sh_files) > 0, f"found: {sh_files}")
    check("生成 .bat 脚本", len(bat_files) > 0, f"found: {bat_files}")


# ============================================================
# 5. 自举验证：Matha 源文件解析
# ============================================================
def test_matha_source_bootstrap():
    print("\n=== 5. 自举验证：Matha 源文件解析 ===")
    examples = [
        ("matha/examples/01_arithmetic.matha", "算术示例"),
        ("matha/examples/02_functions.matha", "函数示例"),
        ("matha/examples/11_desktop.matha", "桌面示例"),
    ]
    for rel_path, desc in examples:
        full_path = os.path.join(r"D:\trae", rel_path)
        if not os.path.exists(full_path):
            check(f"{desc} 文件存在", False, f"文件不存在: {full_path}")
            continue
        with open(full_path, encoding="utf-8") as f:
            src = f.read()
        try:
            program = parse(src)
            check(f"{desc} 解析成功", True, "")
        except Exception as e:
            check(f"{desc} 解析成功", False, str(e))
            continue
        _, errors = analyze_source(src, verbose=False)
        err_count = sum(1 for e in errors if e.severity == "error")
        # 忽略未定义内建变量的错误（生成_桌面/软件_构建 是运行时内建，不在语义符号表中）
        builtin_errors = sum(1 for e in errors if e.severity == "error"
                           and ("生成_桌面" in str(e) or "软件_构建" in str(e)))
        real_errors = err_count - builtin_errors
        check(f"{desc} 语义校验 0 错误", real_errors == 0, f"总错误={err_count}, 忽略内建={builtin_errors}")


# ============================================================
# 6. 端到端：Matha 源文件执行 + 生成代码验证
# ============================================================
def test_end_to_end_execution():
    print("\n=== 6. 端到端：生成代码可执行性验证 ===")

    cases = [
        ("算术演示", ["桌面", "算术演示", [["label", "计算结果", [], []]]]),
        ("函数演示", ["桌面", "函数演示", [["button", "点击", [["onclick", "handle()"]], []]]]),
    ]
    for name, spec in cases:
        spec_json = _matha_json_str(spec)
        src = (
            '#：{\n'
            f'  规格 = 解析_JSON "{spec_json}"\n'
            '  结果 = 生成_桌面 规格\n'
            '  #：[结果]\n'
            '}'
        )
        try:
            out, trace = _run_matha_src(src)
            r = out[0] if out else {}
            check(f"{name} 生成成功", r.get("成功"), r.get("错误", ""))
            if r.get("入口"):
                with open(r["入口"], encoding="utf-8") as f:
                    py_src = f.read()
                try:
                    _ast.parse(py_src)
                    check(f"{name} Python 语法合法", True)
                except SyntaxError as e:
                    check(f"{name} Python 语法合法", False, str(e))
                check(f"{name} 含 tkinter", "tkinter" in py_src)
                check(f"{name} 含标题", name in py_src)
                if "函数" in name:
                    check(f"{name} 含 handle 函数", "def handle" in py_src)
                    check(f"{name} 含 command 绑定", "command=self.handle" in py_src)
            else:
                check(f"{name} 入口文件", False, "无入口")
        except Exception as e:
            check(f"{name} 生成执行", False, str(e))

    # 软件_构建 自主构建
    src = '#：{报告 = 软件_构建 "计算器桌面"; #：[报告]}'
    try:
        out, trace = _run_matha_src(src)
        r = out[0] if out else {}
        check("软件_构建 计算器桌面", r.get("成功"), r.get("错误", ""))
    except Exception as e:
        check("软件_构建 计算器桌面", False, str(e))


# ============================================================
# 主入口
# ============================================================
def main():
    print("=" * 60)
    print("Matha 自举代码生成测试")
    print("=" * 60)
    test_web_matha_vs_codegen()
    test_desktop_matha_vs_codegen()
    test_backend_matha_vs_codegen()
    test_system_matha_vs_codegen()
    test_matha_source_bootstrap()
    test_end_to_end_execution()
    print("\n" + "=" * 60)
    print(f"测试结果：{passed} 通过, {failed} 失败 (共 {passed + failed})")
    print("=" * 60)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
