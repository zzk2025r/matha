"""Matha 语言对不同人群的适用性测试。

验证 Matha 三层架构对五类人群的友好度：
  1. 小白    —— 纯自然语言意图块（【*/标注/*】+ 正文）
  2. 普通人  —— 自然语言意图块（中文意图描述）
  3. 外国人  —— 英文标注 + 英文正文（中英混排支持）
  4. 程序员  —— 机械语言（集合构造、变量绑定、段输出）
  5. 黑客    —— 链式命令 + 资源读取（URL/端口识别）

设计理念：自然语言前端服务小白/普通人/外国人，数学核心服务程序员，
命令链式 + 资源读取服务黑客。三层架构覆盖全人群。

运行：python -m tests.test_audience_fit
"""

from src.parser import parse, ParseError
from src.semantic import analyze_source
from src import ast_nodes as ast


def _check(src: str, label: str, verbose: bool = True) -> None:
    """通用校验：解析 + 语义分析，断言无 error。"""
    print(f"\n--- {label} ---")
    print(src.rstrip())
    try:
        program = parse(src)
    except ParseError as ex:
        print(f"  ✗ 解析失败: {ex}")
        raise
    decl_types = [type(d).__name__ for d in program.decls]
    _, errors = analyze_source(src, verbose=verbose)
    err_n = len([e for e in errors if e.severity == "error"])
    print(f"  → 解析 OK: {decl_types}，语义 error 数: {err_n}")
    assert err_n == 0, f"{label} 存在 error: {[e.msg for e in errors if e.severity=='error']}"
    print(f"  ✓ {label} 通过")


# ============================================================
# 1. 小白：纯自然语言意图块
# ============================================================

def test_novice():
    """小白：用标注 + 自然语言正文表达简单意图，无需懂语法。"""
    src = '【*/问候/*】输出"你好，Matha"'
    _check(src, "1. 小白（自然语言意图块）")


# ============================================================
# 2. 普通人：中文意图描述
# ============================================================

def test_layman():
    """普通人：用中文描述计算意图（求和）。"""
    src = "【*/求和/*】计算从1到10所有整数的和"
    _check(src, "2. 普通人（中文意图描述）")


# ============================================================
# 3. 外国人：英文标注 + 英文正文
# ============================================================

def test_foreigner():
    """外国人：英文标注 */sum/* + 英文正文（中英混排支持）。"""
    src = "【*/sum/*】compute the sum from 1 to 10"
    _check(src, "3. 外国人（英文意图块）")


# ============================================================
# 4. 程序员：机械语言
# ============================================================

def test_programmer():
    """程序员：集合构造、变量绑定、段输出（精确控制）。"""
    src = "S = {1, 2, 3}\n#1：[S]"
    _check(src, "4. 程序员（机械语言）")


# ============================================================
# 5. 黑客：链式命令 + 资源读取
# ============================================================

def test_hacker():
    """黑客：>> 链式命令表达多步操作流程 + URL 资源读取。

    安全说明：命令是文本字面量，语义层只识别资源类型，不执行真实操作。
    """
    src = "#1：【扫描目标 http://target.com】>>【获取权限】>>【提取数据】"
    _check(src, "5. 黑客（链式命令 + 资源读取）")


# ============================================================
# 6. 混排：中英标注 + 中英正文（跨人群协作）
# ============================================================

def test_mixed_audience():
    """混排：中文标注 + 英文正文，验证中英混排的灵活性。"""
    src = "【*/filter/*】select items where price > 100"
    _check(src, "6. 混排（中英标注 + 英文正文）")


if __name__ == "__main__":
    test_novice()
    test_layman()
    test_foreigner()
    test_programmer()
    test_hacker()
    test_mixed_audience()
    print("\n=== 全部人群适用性测试完成 ===")
