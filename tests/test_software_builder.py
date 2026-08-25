# -*- coding: utf-8 -*-
"""Matha 自主软件构建测试。

验证 SoftwareBuilder 能从需求描述自主生成各类成品软件。

运行：python -m tests.test_software_builder
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.interp import Interpreter
from src.autonomous import SoftwareBuilder, build_software

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


def test_build_web():
    """自主构建网页。"""
    print("\n--- 自主构建网页 ---")
    interp = Interpreter()
    builder = SoftwareBuilder(interp)
    for req in ("计算器网页", "登录表单网页", "待办清单网页"):
        r = builder.build(req)
        check(f"构建{req}", r.成功, r.错误 or "")
        check(f"{req}类型", r.类型 == "网页")
        check(f"{req}有文件", len(r.文件) > 0)
        check(f"{req}有入口", r.入口 != "")


def test_build_desktop():
    """自主构建桌面应用。"""
    print("\n--- 自主构建桌面 ---")
    interp = Interpreter()
    builder = SoftwareBuilder(interp)
    r = builder.build("记事本桌面应用")
    check("构建记事本", r.成功, r.错误 or "")
    check("记事本类型", r.类型 == "桌面")
    check("记事本有main.py", any("main.py" in f for f in r.文件))


def test_build_service():
    """自主构建后端服务。"""
    print("\n--- 自主构建服务 ---")
    interp = Interpreter()
    builder = SoftwareBuilder(interp)
    r = builder.build("Echo 服务")
    check("构建Echo服务", r.成功, r.错误 or "")
    check("Echo类型", r.类型 == "服务")
    check("Echo有server.py", any("server.py" in f for f in r.文件))


def test_build_system():
    """自主构建系统脚本。"""
    print("\n--- 自主构建系统 ---")
    interp = Interpreter()
    builder = SoftwareBuilder(interp)
    r = builder.build("部署系统")
    check("构建部署脚本", r.成功, r.错误 or "")
    check("部署类型", r.类型 == "系统")
    check("部署有sh", any("run.sh" in f for f in r.文件))


def test_infer_kind():
    """类型自动推断。"""
    print("\n--- 类型推断 ---")
    interp = Interpreter()
    builder = SoftwareBuilder(interp)
    check("推断桌面", builder._infer_kind("记事本桌面应用", "网页") == "桌面")
    check("推断服务", builder._infer_kind("API 服务", "网页") == "服务")
    check("推断系统", builder._infer_kind("部署脚本", "网页") == "系统")
    check("推断网页", builder._infer_kind("计算器网页", "网页") == "网页")
    check("默认类型", builder._infer_kind("测试", "网页") == "网页")


def test_build_software_entry():
    """build_software 入口函数。"""
    print("\n--- 入口函数 ---")
    interp = Interpreter()
    d = build_software(interp, "计算器网页")
    check("入口返回dict", isinstance(d, dict))
    check("入口成功", d["成功"])
    check("入口有文件", len(d["文件"]) > 0)


def test_builtin_call():
    """Matha 内建调用。"""
    print("\n--- Matha 内建调用 ---")
    from src.interp import interpret
    src = '''
#：{
  结果 = 软件_构建 "计算器网页"
  #：[结果]
}
#：【文件】
'''
    out, _ = interpret(src)
    r = out[0]
    check("内建软件_构建", r["成功"], r.get("错误", ""))
    check("内建类型", r["类型"] == "网页")
    check("内建有入口", r["入口"] != "")


def test_builtin_json():
    """解析_JSON + 生成_网页 内建。"""
    print("\n--- 解析_JSON + 生成_网页 ---")
    from src.interp import interpret
    # 用 raw string 避免 Python 转义，Matha 词法器解释 \" 为字符串内引号
    src = r'''
规格 = 解析_JSON "[\"网页\", \"JSON测试\", [[\"h1\", \"标题\", [], []]]]"
#：{
  结果 = 生成_网页 规格
  #：[结果]
}
#：【文件】
'''
    out, _ = interpret(src)
    r = out[0]
    check("JSON解析+生成", r["成功"], r.get("错误", ""))
    check("JSON类型", r["类型"] == "网页")


def main():
    print("=" * 60)
    print("Matha 自主软件构建测试")
    print("=" * 60)
    test_build_web()
    test_build_desktop()
    test_build_service()
    test_build_system()
    test_infer_kind()
    test_build_software_entry()
    test_builtin_call()
    test_builtin_json()
    print("\n" + "=" * 60)
    print(f"软件构建测试：{passed} 通过, {failed} 失败 (共 {passed + failed})")
    print("=" * 60)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
