# -*- coding: utf-8 -*-
"""Matha 代码生成子系统测试。

验证 codegen 能把 Matha 规格树编译为各类成品软件文件：
  - WebGenerator     → HTML/CSS/JS
  - DesktopGenerator → Python Tkinter（16 种控件、3 种布局、窗口属性、事件）
  - BackendGenerator → Python HTTP 服务
  - SystemGenerator  → .sh / .bat 脚本

运行：python -m tests.test_codegen
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.codegen import codegen, parse_app_spec, CodegenError
from src.codegen.base import Element, AppSpec

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


def test_parse_app_spec():
    """规格树解析。"""
    print("\n--- 规格解析 ---")
    spec = ["应用", "网页", "测试", [
        ["h1", "标题", [], []],
        ["button", "按钮", [["onclick", "fn()"]], []],
    ]]
    app = parse_app_spec(spec)
    check("解析应用类型", app.kind == "网页")
    check("解析应用名", app.name == "测试")
    check("解析元素数", len(app.elements) == 2)
    check("解析元素标签", app.elements[0].tag == "h1")
    check("解析元素文本", app.elements[0].text == "标题")
    check("解析属性", app.elements[1].attrs == [("onclick", "fn()")])

    # 省略 "应用" 头
    spec2 = ["网页", "简洁", [["p", "文本", [], []]]]
    app2 = parse_app_spec(spec2)
    check("省略应用头", app2.kind == "网页" and app2.name == "简洁")

    # 无效规格
    try:
        parse_app_spec(["错误"])
        check("无效规格报错", False)
    except CodegenError:
        check("无效规格报错", True)

    # 未知类型
    try:
        parse_app_spec(["应用", "未知", "名", []])
        check("未知类型报错", False)
    except CodegenError:
        check("未知类型报错", True)


def test_web_generator():
    """网页生成器。"""
    print("\n--- 网页生成 ---")
    with tempfile.TemporaryDirectory() as d:
        spec = ["应用", "网页", "测试页", [
            ["h1", "标题", [], []],
            ["input", "", [["id", "disp"]], []],
            ["button", "点", [["onclick", "fn()"]], []],
            ["样式", "h1", [["color", "red"]]],
            ["脚本", "function fn(){}"],
        ]]
        r = codegen(spec, d)
        check("网页生成成功", r.成功)
        check("网页类型", r.类型 == "网页")
        check("网页有HTML", any(f.endswith("index.html") for f in r.文件))
        check("网页有CSS", any(f.endswith("style.css") for f in r.文件))
        check("网页有JS", any(f.endswith("script.js") for f in r.文件))
        check("网页入口", r.入口.endswith("index.html"))
        # 检查 HTML 内容
        with open(r.入口, encoding="utf-8") as f:
            html = f.read()
        check("HTML含标题", "<title>测试页</title>" in html)
        check("HTML含按钮", "fn()" in html)


def test_web_nested():
    """网页嵌套元素。"""
    print("\n--- 网页嵌套 ---")
    with tempfile.TemporaryDirectory() as d:
        spec = ["网页", "嵌套", [
            ["div", "", [], [
                ["h1", "内层标题", [], []],
                ["p", "段落", [], []],
            ]],
        ]]
        r = codegen(spec, d)
        check("嵌套生成成功", r.成功)
        with open(r.入口, encoding="utf-8") as f:
            html = f.read()
        check("嵌套含div", "<div>" in html)
        check("嵌套含h1", "<h1>内层标题</h1>" in html)
        check("嵌套含p", "<p>段落</p>" in html)


def test_web_void():
    """自闭合标签。"""
    print("\n--- 自闭合标签 ---")
    with tempfile.TemporaryDirectory() as d:
        spec = ["网页", "空元素", [
            ["input", "", [["type", "text"]], []],
            ["br", "", [], []],
        ]]
        r = codegen(spec, d)
        check("空元素生成", r.成功)
        with open(r.入口, encoding="utf-8") as f:
            html = f.read()
        check("input自闭合", "<input" in html and "/>" in html)


def test_desktop_generator():
    """桌面生成器。"""
    print("\n--- 桌面生成 ---")
    with tempfile.TemporaryDirectory() as d:
        spec = ["桌面", "记事本", [
            ["h1", "记事本", [], []],
            ["input", "", [["width", "30"]], []],
            ["button", "保存", [["onclick", "save()"]], []],
        ]]
        r = codegen(spec, d)
        check("桌面生成成功", r.成功)
        check("桌面类型", r.类型 == "桌面")
        check("桌面有main.py", any(f.endswith("main.py") for f in r.文件))
        check("桌面入口", r.入口.endswith("main.py"))
        with open(r.入口, encoding="utf-8") as f:
            py = f.read()
        check("Python含tkinter", "import tkinter" in py)
        check("Python含标题", 'root.title("记事本")' in py)
        check("Python含按钮", "tk.Button" in py)


def test_desktop_widgets():
    """桌面 16 种控件。"""
    print("\n--- 桌面控件（16种） ---")
    import ast as _ast
    with tempfile.TemporaryDirectory() as d:
        spec = ["桌面", "全控件", [
            ["h1", "大标题", [], []],
            ["h2", "中标题", [], []],
            ["p", "段落", [], []],
            ["label", "标签", [], []],
            ["input", "默认值", [["width", "30"]], []],
            ["textarea", "多行", [["width", "40"], ["height", "8"]], []],
            ["button", "按钮", [["onclick", "doClick()"]], []],
            ["checkbox", "选项", [["checked", "true"]], []],
            ["radio", "A", [["group", "g1"], ["value", "A"]], []],
            ["select", "", [["options", "甲|乙|丙"]], []],
            ["list", "项1|项2|项3", [["height", "5"]], []],
            ["slider", "", [["min", "0"], ["max", "50"]], []],
            ["canvas", "", [["width", "300"], ["height", "200"], ["bg", "white"]], []],
            ["image", "", [["src", "x.png"]], []],
            ["separator", "", [["orient", "horizontal"]], []],
            ["table", "", [["columns", "名|值"]],
             [["", "a|1", [], []], ["", "b|2", [], []]]],
        ]]
        r = codegen(spec, d)
        check("全控件生成成功", r.成功, r.错误 or "")
        with open(r.入口, encoding="utf-8") as f:
            py = f.read()
        try:
            _ast.parse(py)
            check("全控件Python语法合法", True)
        except SyntaxError as e:
            check("全控件Python语法合法", False, str(e))
        check("含Label", "tk.Label" in py)
        check("含Entry", "tk.Entry" in py)
        check("含ScrolledText", "ScrolledText" in py)
        check("含Button", "tk.Button" in py)
        check("含Checkbutton", "tk.Checkbutton" in py)
        check("含Radiobutton", "tk.Radiobutton" in py)
        check("含Combobox", "ttk.Combobox" in py)
        check("含Listbox", "tk.Listbox" in py)
        check("含Scale", "tk.Scale" in py)
        check("含Canvas", "tk.Canvas" in py)
        check("含PhotoImage", "tk.PhotoImage" in py)
        check("含Separator", "ttk.Separator" in py)
        check("含Treeview", "ttk.Treeview" in py)


def test_desktop_layouts():
    """桌面三种布局：pack / grid / place。"""
    print("\n--- 桌面布局 ---")
    import ast as _ast
    # grid 布局
    with tempfile.TemporaryDirectory() as d:
        spec = ["桌面", "网格布局", [
            ["label", "A", [["row", "0"], ["col", "0"]], []],
            ["label", "B", [["row", "0"], ["col", "1"]], []],
            ["button", "C", [["row", "1"], ["col", "0"], ["columnspan", "2"]], []],
        ]]
        r = codegen(spec, d)
        check("grid布局生成", r.成功)
        py = open(r.入口, encoding="utf-8").read()
        check("grid含.grid(", ".grid(" in py)
        check("grid含columnspan", "columnspan=2" in py)
        try:
            _ast.parse(py); check("grid语法合法", True)
        except SyntaxError as e:
            check("grid语法合法", False, str(e))
    # place 布局
    with tempfile.TemporaryDirectory() as d:
        spec = ["桌面", "绝对布局", [
            ["label", "X", [["x", "10"], ["y", "20"], ["width", "100"]], []],
            ["button", "Y", [["x", "10"], ["y", "50"]], []],
        ]]
        r = codegen(spec, d)
        check("place布局生成", r.成功)
        py = open(r.入口, encoding="utf-8").read()
        check("place含.place(", ".place(" in py)
        check("place含x=", "x=10" in py)
    # pack 布局（默认）
    with tempfile.TemporaryDirectory() as d:
        spec = ["桌面", "堆叠布局", [
            ["label", "A", [], []],
            ["label", "B", [], []],
        ]]
        r = codegen(spec, d)
        check("pack布局生成", r.成功)
        py = open(r.入口, encoding="utf-8").read()
        check("pack含.pack(", ".pack(" in py)


def test_desktop_window_props():
    """桌面窗口属性：尺寸、背景、可调整。"""
    print("\n--- 桌面窗口属性 ---")
    import ast as _ast
    with tempfile.TemporaryDirectory() as d:
        spec = ["桌面", "属性窗", [
            ["label", "测试", [], []],
        ], [["尺寸", "400x300"], ["背景", "#f0f0f0"], ["可调整", "否"]]]
        r = codegen(spec, d)
        check("窗口属性生成", r.成功)
        py = open(r.入口, encoding="utf-8").read()
        check("含geometry", 'root.geometry("400x300")' in py)
        check("含背景", 'root.configure(bg="#f0f0f0")' in py)
        check("含resizable", "root.resizable(False, False)" in py)
        try:
            _ast.parse(py); check("窗口属性语法合法", True)
        except SyntaxError as e:
            check("窗口属性语法合法", False, str(e))


def test_desktop_events():
    """桌面事件处理：onclick 绑定。"""
    print("\n--- 桌面事件处理 ---")
    import ast as _ast
    with tempfile.TemporaryDirectory() as d:
        spec = ["桌面", "事件窗", [
            ["button", "保存", [["onclick", "save()"]], []],
            ["button", "加载", [["onclick", "load()"]], []],
        ]]
        r = codegen(spec, d)
        check("事件生成成功", r.成功)
        py = open(r.入口, encoding="utf-8").read()
        check("含save处理函数", "def save" in py)
        check("含load处理函数", "def load" in py)
        check("含command绑定", "command=self.save" in py or "command=self.load" in py)
        try:
            _ast.parse(py); check("事件处理语法合法", True)
        except SyntaxError as e:
            check("事件处理语法合法", False, str(e))


def test_desktop_autobuild():
    """自主构建多种桌面应用。"""
    print("\n--- 桌面自主构建 ---")
    import ast as _ast
    from src.autonomous import build_software
    from src.interp import Interpreter
    interp = Interpreter()
    for req in ["记事本桌面应用", "计算器桌面", "设置桌面", "登录桌面", "数据表桌面"]:
        r = build_software(interp, req)
        check(f"构建{req}", r.get("成功", False), r.get("错误", ""))
        if r.get("成功") and r.get("入口"):
            py = open(r["入口"], encoding="utf-8").read()
            try:
                _ast.parse(py); check(f"{req}语法合法", True)
            except SyntaxError as e:
                check(f"{req}语法合法", False, str(e))


def test_backend_generator():
    """后端生成器。"""
    print("\n--- 后端生成 ---")
    with tempfile.TemporaryDirectory() as d:
        spec = ["服务", "API", [
            ["接口", "GET", "/api/hello", '{"msg": "你好"}'],
            ["接口", "POST", "/api/echo", "echo"],
        ]]
        r = codegen(spec, d)
        check("后端生成成功", r.成功)
        check("后端类型", r.类型 == "服务")
        check("后端有server.py", any(f.endswith("server.py") for f in r.文件))
        with open(r.入口, encoding="utf-8") as f:
            py = f.read()
        check("Python含HTTPServer", "HTTPServer" in py)
        check("Python含GET路由", "/api/hello" in py)
        check("Python含POST路由", "/api/echo" in py)
        check("Python含端口", "8080" in py)


def test_system_generator():
    """系统脚本生成器。"""
    print("\n--- 系统脚本 ---")
    with tempfile.TemporaryDirectory() as d:
        spec = ["系统", "部署", [
            ["接口", "目录", "build", ""],
            ["接口", "命令", "", "echo 部署"],
            ["接口", "文件", "build/README.txt", "内容"],
        ]]
        r = codegen(spec, d)
        check("系统生成成功", r.成功)
        check("系统类型", r.类型 == "系统")
        check("系统有sh", any(f.endswith("run.sh") for f in r.文件))
        check("系统有bat", any(f.endswith("run.bat") for f in r.文件))
        sh_path = [f for f in r.文件 if f.endswith("run.sh")][0]
        with open(sh_path, encoding="utf-8") as f:
            sh = f.read()
        check("sh含mkdir", "mkdir" in sh)
        check("sh含echo", "echo" in sh)


def test_error_handling():
    """错误处理。"""
    print("\n--- 错误处理 ---")
    r = codegen("不是列表")
    check("非列表报错", not r.成功)
    check("错误信息", r.错误 is not None)

    r = codegen(["应用", "错误类型", "名", []])
    check("错误类型报错", not r.成功)


def main():
    print("=" * 60)
    print("Matha 代码生成子系统测试")
    print("=" * 60)

    test_parse_app_spec()
    test_web_generator()
    test_web_nested()
    test_web_void()
    test_desktop_generator()
    test_desktop_widgets()
    test_desktop_layouts()
    test_desktop_window_props()
    test_desktop_events()
    test_desktop_autobuild()
    test_backend_generator()
    test_system_generator()
    test_error_handling()

    print("\n" + "=" * 60)
    print(f"代码生成测试：{passed} 通过, {failed} 失败 (共 {passed + failed})")
    print("=" * 60)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
