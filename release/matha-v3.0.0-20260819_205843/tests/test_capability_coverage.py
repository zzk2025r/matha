"""Matha 语言能力覆盖测试。

验证 Matha 语法/语义能否表达三类操作：
  1. 输入/构建（数据结构、配置、集合）
  2. 黑入/攻击/修改（命令链式表达攻击流程）
  3. 打开/使用网页/网址/网络/界面（URL/端口/界面命令）

安全说明：
  - Matha 是规格语言，命令字面量（【...】/《...》）是**文本描述**，语义层只识别
    命令结构和资源类型（URL/file/port），**不执行**任何真实网络操作或攻击。
  - 攻击类命令仅验证语法可表达性，不构成实际攻击工具。

运行：python -m tests.test_capability_coverage
"""

from src.parser import parse, ParseError
from src.semantic import analyze_source
from src.symbols import detect_resource_type, RESOURCE_URL, RESOURCE_FILE, RESOURCE_PORT, RESOURCE_TEXT


def _check(src: str, label: str, verbose: bool = True) -> None:
    """通用校验：解析 + 语义分析，断言无 error。"""
    print(f"\n--- {label} ---")
    print(src.rstrip())
    try:
        program = parse(src)
    except ParseError as ex:
        print(f"  ✗ 解析失败: {ex}")
        raise
    _, errors = analyze_source(src, verbose=verbose)
    err_n = len([e for e in errors if e.severity == "error"])
    print(f"  → 解析 OK，语义 error 数: {err_n}")
    assert err_n == 0, f"{label} 存在 error: {[e.msg for e in errors if e.severity=='error']}"
    print(f"  ✓ {label} 通过")


# ============================================================
# 1. 输入/构建
# ============================================================

def test_input_build():
    """输入/构建：配置设定、集合构造、变量绑定与段内引用。

    同时验证两个修复：
    - {} 集合消解（S = {1, 2, 3} 解析为集合构造而非代码块）
    - 顶层 binding 作用域（顶层 S 定义后，段 #1 内 [S] 能引用）
    """
    src = """@:端口=8080，路径=/api
S = {1, 2, 3}
#1：【构建数据集】
#1：[S]"""
    _check(src, "1. 输入/构建")


# ============================================================
# 2. 黑入/攻击/修改（命令链式表达攻击流程）
# ============================================================

def test_attack_modify():
    """攻击/修改：>> 链式命令表达多步攻击流程。"""
    src = "#2：【扫描目标 http://target.com】>>【获取访问权限】>>【修改数据库】"
    _check(src, "2. 黑入/攻击/修改（链式命令）")


# ============================================================
# 3. 打开/使用网页/网址/网络/界面
# ============================================================

def test_web_network_ui():
    """网页/网址/网络/界面：URL 命令、端口命令、界面命令。"""
    src = """#3：【打开网页 http://example.com】
#4：【http://api.example.com/data】
#5：【连接服务 localhost:8080】
#6：【渲染用户界面】"""
    _check(src, "3. 网页/网址/网络/界面")


# ============================================================
# 4. 资源类型识别验证（独立断言，不依赖 verbose）
# ============================================================

def test_resource_recognition():
    """验证三类操作涉及的资源类型识别正确。"""
    print("\n--- 4. 资源类型识别 ---")
    cases = [
        ("http://target.com", RESOURCE_URL, "攻击目标 URL"),
        ("http://example.com", RESOURCE_URL, "网页 URL"),
        ("http://api.example.com/data", RESOURCE_URL, "API 网址"),
        ("localhost:8080", RESOURCE_PORT, "网络端口"),
        ("/api/config.yaml", RESOURCE_FILE, "配置文件路径"),
        ("渲染用户界面", RESOURCE_TEXT, "界面命令文本"),
        ("修改数据库", RESOURCE_TEXT, "攻击命令文本"),
    ]
    for text, expected, desc in cases:
        actual = detect_resource_type(text)
        ok = "✓" if actual == expected else "✗"
        print(f"  {ok} {desc}: '{text}' → {actual}（预期 {expected}）")
        assert actual == expected, f"'{text}' 识别为 {actual}，预期 {expected}"
    print("  ✓ 资源类型识别全部正确")


# ============================================================
# 5. 综合测试：三类操作合一
# ============================================================

def test_comprehensive():
    """综合：三类操作在一个程序中并存。"""
    src = """#：{
   #1：【构建数据集】
   #1：[1]
   #2：【扫描目标 http://target.com】>>【获取访问权限】>>【修改数据库】
   #3：【打开网页 http://example.com】
   #4：【http://api.example.com/data】
   #5：【连接服务 localhost:8080】
   #6：【渲染用户界面】
}"""
    _check(src, "5. 综合三类操作")


if __name__ == "__main__":
    test_input_build()
    test_attack_modify()
    test_web_network_ui()
    test_resource_recognition()
    test_comprehensive()
    print("\n=== 全部能力覆盖测试完成 ===")
