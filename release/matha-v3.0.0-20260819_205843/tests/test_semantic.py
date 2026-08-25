"""语义分析器测试。

验证变量赋值、命令链、段内顺序、公式分层、循环后缀等语义检查。
运行：python -m tests.test_semantic
"""

from src.semantic import analyze_source, SemanticAnalyzer
from src.parser import parse
from src import ast_nodes as ast
from src.symbols import detect_resource_type, RESOURCE_URL, RESOURCE_FILE, RESOURCE_DIR, RESOURCE_PORT, RESOURCE_TEXT


def _run(source: str, label: str = "") -> list:
    """运行语义分析，返回错误列表并打印。"""
    print(f"\n--- {label} ---")
    print(f"源码: {source[:80]}{'...' if len(source) > 80 else ''}")
    program, errors = analyze_source(source)
    if not errors:
        print("  ✓ 无语义错误")
    for err in errors:
        print(f"  {err}")
    return errors


def test_variable_definition():
    """变量定义与引用。"""
    print("\n=== test_variable_definition ===")
    # 正常：先声明再引用（端口、路径 都在 @ 中声明，连接 是公式输出变量）
    errs = _run("@1:端口=8080,路径=/data\n#1:端口+路径=连接", "先声明后引用")
    undef_errs = [e for e in errs if "未定义" in e.msg and e.severity == "error"]
    assert len(undef_errs) == 0, f"不应有未定义错误: {undef_errs}"

    # 错误：引用未定义变量
    errs = _run("#1:未定义变量+1=结果", "引用未定义变量")
    assert any("未定义" in e.msg for e in errs)


def test_set_up_declarations():
    """@ 设定声明变量。"""
    print("\n=== test_set_up_declarations ===")
    # @(a|b|c) 声明三个变量
    errs = _run("@(a|b|c)\n#1:a+b=c", "括号形式声明")
    # a, b, c 已声明，a+b=c 中 a,b 引用（已定义），c 是公式输出（已定义）
    undef_errs = [e for e in errs if "未定义" in e.msg and e.severity == "error"]
    assert len(undef_errs) == 0, f"不应有未定义错误: {undef_errs}"

    # @:单价=10元,数量=3
    errs = _run("@:单价=10元,数量=3\n#1:单价*数量=总价", "前缀形式声明")
    undef_errs = [e for e in errs if "未定义" in e.msg and e.severity == "error"]
    assert len(undef_errs) == 0, f"不应有未定义错误: {undef_errs}"


def test_command_chain():
    """命令链 >> 语义。"""
    print("\n=== test_command_chain ===")
    # 正常：命令链式
    errs = _run("#1：【启动服务】>>【读取配置】", "命令链式")
    print(f"  错误数: {len(errs)}")

    # 正常：输出链式
    errs = _run("#1:[结果A]>>[结果B]>>[结果C]", "输出链式")
    print(f"  错误数: {len(errs)}")


def test_segment_step_order():
    """段内 5 步固定顺序。"""
    print("\n=== test_segment_step_order ===")
    # 正常顺序：命令→变量→？公式→字母公式→输出
    source = (
        "#：{"
        "#1：【命令】\n"
        "@1:a=1,b=2\n"
        "#1:？+？=？\n"
        "#1:a+b=c\n"
        "#1:[c]\n"
        "}"
    )
    errs = _run(source, "正常 5 步顺序")
    order_errs = [e for e in errs if "顺序违规" in e.msg]
    assert len(order_errs) == 0, f"不应有顺序违规: {order_errs}"

    # 顺序违规：输出在变量之前
    source_violation = (
        "#：{"
        "#1:[结果]\n"
        "@1:变量=1\n"
        "}"
    )
    errs = _run(source_violation, "顺序违规：输出在变量之前")
    order_errs = [e for e in errs if "顺序违规" in e.msg]
    assert len(order_errs) > 0, "应检测到顺序违规"


def test_formula_layering():
    """公式分层检查。"""
    print("\n=== test_formula_layering ===")
    # 正常：？公式与字母公式结构一致
    source = (
        "#：{"
        "@1:a=1,b=2\n"
        "#1:？+？=？\n"
        "#1:a+b=c\n"
        "#1:[c]\n"
        "}"
    )
    errs = _run(source, "公式结构一致")
    layer_errs = [e for e in errs if "公式分层" in e.msg]
    assert len(layer_errs) == 0, f"不应有分层警告: {layer_errs}"

    # 不一致：？公式用 +，字母公式用 *
    source_mismatch = (
        "#：{"
        "@1:a=1,b=2\n"
        "#1:？+？=？\n"
        "#1:a*b=c\n"
        "#1:[c]\n"
        "}"
    )
    errs = _run(source_mismatch, "公式结构不一致")
    layer_errs = [e for e in errs if "公式分层" in e.msg]
    assert len(layer_errs) > 0, "应检测到公式分层不一致"


def test_loop_suffix():
    """循环后缀校验。"""
    print("\n=== test_loop_suffix ===")
    # 正常：段级循环 x ≤ y
    errs = _run("#2:[结果]…2（0/4）", "段级循环正常")
    loop_errs = [e for e in errs if "循环" in e.msg and e.severity == "error"]
    assert len(loop_errs) == 0

    # 异常：current > maximum
    errs = _run("#2:[结果]…2（5/3）", "段级循环 current>maximum")
    loop_errs = [e for e in errs if "循环分数无效" in e.msg]
    assert len(loop_errs) > 0, "应检测到循环分数无效"


def test_resource_detection():
    """资源读取识别。"""
    print("\n=== test_resource_detection ===")
    assert detect_resource_type("http://example.com/api") == RESOURCE_URL
    assert detect_resource_type("https://localhost:8080/data") == RESOURCE_URL
    assert detect_resource_type("/data/config.yaml") == RESOURCE_FILE
    assert detect_resource_type("d:\\trae\\docs\\") in (RESOURCE_DIR, RESOURCE_FILE)
    assert detect_resource_type("localhost:8080") == RESOURCE_PORT
    assert detect_resource_type("启动服务") == RESOURCE_TEXT

    # 相对文件名（含字母扩展名）→ FILE（M3.3 子文件引用修复）
    assert detect_resource_type("config_loader.matha") == RESOURCE_FILE
    assert detect_resource_type("calc_core.matha") == RESOURCE_FILE
    assert detect_resource_type("render.matha") == RESOURCE_FILE
    assert detect_resource_type("sub.py") == RESOURCE_FILE
    assert detect_resource_type("data/config.yaml") == RESOURCE_FILE

    # 边界：不应误识别为文件
    assert detect_resource_type("1.5") == RESOURCE_TEXT        # 数字小数
    assert detect_resource_type("v1.2") == RESOURCE_TEXT       # 版本号
    assert detect_resource_type("加载配置") == RESOURCE_TEXT    # 中文文本
    assert detect_resource_type("宽*高") == RESOURCE_TEXT       # 含运算符
    print("  ✓ 资源类型识别测试通过（含相对文件名扩展）")


def test_full_example():
    """完整示例：跨段 + 链式 + 公式分层。"""
    print("\n=== test_full_example ===")
    source = (
        "#：{【*/自然语言/*】\n"
        "#1：【启动服务】>>【读取配置】\n"
        "@1:端口=8080,路径=/data/config\n"
        "#1:？+？=？\n"
        "#1:端口+路径=连接\n"
        "#1:[连接成功]\n"
        "#1:…1（0/1）\n"
        "#2：【执行计算】\n"
        "@2:x=5米,y=3米\n"
        "#2:？*？=？\n"
        "#2:x*y=15\n"
        "#2:[15平方米]\n"
        "#2:…2（0/4）00001……（0/2）【file_2.matha】\n"
        "#：【文件】\n"
        "}"
    )
    errs = _run(source, "完整示例")
    print(f"\n  总错误/警告数: {len(errs)}")
    for e in errs:
        print(f"  {e}")


def test_set_construct_parse():
    """集合构造解析：枚举 / 理解 / 空集合（{} 双语义消解修复）。"""
    print("\n=== test_set_construct_parse ===")
    from src.parser import parse
    from src import ast_nodes as ast

    # 枚举形式
    p = parse("S = {1, 2, 3}")
    decl = p.decls[0]
    assert isinstance(decl, ast.Binding), f"应为 Binding，实际 {type(decl).__name__}"
    assert isinstance(decl.value, ast.SetConstruct), "value 应为 SetConstruct"
    assert decl.value.form == "enumeration"
    assert [l.value for l in decl.value.literals] == [1, 2, 3]
    print("  ✓ 枚举集合 {1, 2, 3}")

    # 理解形式
    p2 = parse("R = {x | x > 5}")
    decl2 = p2.decls[0]
    assert isinstance(decl2.value, ast.SetConstruct)
    assert decl2.value.form == "comprehension"
    assert len(decl2.value.variables) == 1
    print("  ✓ 理解集合 {x | x > 5}")

    # 空集合
    p3 = parse("E = {}")
    decl3 = p3.decls[0]
    assert isinstance(decl3.value, ast.SetConstruct)
    assert decl3.value.form == "enumeration"
    assert decl3.value.literals == []
    print("  ✓ 空集合 {}")

    # 代码块仍正常（#：{ 后跟换行 → 代码块，非集合）
    p4 = parse("#：{\n  #1：[1]\n}")
    assert hasattr(p4.decls[0], "generate"), "代码块应解析为 MechUnit"
    print("  ✓ 代码块 #：{...} 仍正常")
    print("  ✓ 集合构造解析测试通过")


def test_top_level_binding_scope():
    """顶层 binding 作用域贯通：顶层定义的变量，段内可引用（修复）。"""
    print("\n=== test_top_level_binding_scope ===")
    # 顶层变量 → 段内引用
    src = "数据=3\n#1：[数据]"
    program, errors = analyze_source(src)
    err_n = len([e for e in errors if e.severity == "error"])
    assert err_n == 0, f"顶层 binding 作用域应贯通，仍有 error: {[e.msg for e in errors if e.severity=='error']}"
    print("  ✓ 顶层变量 段内引用通过")

    # 集合变量跨段引用
    src2 = "S = {1, 2, 3}\n#2：[S]"
    _, errors2 = analyze_source(src2)
    err_n2 = len([e for e in errors2 if e.severity == "error"])
    assert err_n2 == 0, f"集合变量跨段引用应通过: {[e.msg for e in errors2 if e.severity=='error']}"
    print("  ✓ 集合变量跨段引用通过")
    assert True


if __name__ == "__main__":
    test_variable_definition()
    test_set_up_declarations()
    test_command_chain()
    test_segment_step_order()
    test_formula_layering()
    test_loop_suffix()
    test_resource_detection()
    test_set_construct_parse()
    test_top_level_binding_scope()
    test_full_example()
    print("\n=== 全部语义测试完成 ===")
