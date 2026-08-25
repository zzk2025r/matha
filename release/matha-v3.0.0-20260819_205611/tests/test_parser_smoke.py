"""parser 骨架冒烟测试。

用 18-示例程序集.md 中的片段验证 lexer + parser 能跑通。
运行：python -m tests.test_parser_smoke
"""

from src.parser import parse, Parser
from src.lexer import Lexer
from src import ast_nodes as ast


def _show_tokens(source: str) -> None:
    print(f"--- Tokens for: {source[:40]!r}... ---")
    for tok in Lexer(source).tokenize():
        print(f"  {tok}")


def _show_ast(source: str) -> None:
    print(f"--- AST for: {source[:40]!r}... ---")
    try:
        program = parse(source)
        for decl in program.decls:
            print(f"  {decl}")
    except Exception as e:
        print(f"  ERROR: {e}")


def test_lexer_basic():
    """词法分析器基础测试。"""
    print("\n=== test_lexer_basic ===")
    _show_tokens("#1：【启动服务】>>【读取配置】")
    _show_tokens("@1:端口=8080,路径=/data/config")
    _show_tokens("#1:？+？=？")
    _show_tokens("#1:[连接成功]")
    _show_tokens("…1（0/1）00001……（0/2）【file_2.matha】")
    _show_tokens("100米 + 262.5米")
    _show_tokens("^9 = 3")
    _show_tokens("<<90")
    _show_tokens("*/自然语言/*")
    assert True


def test_parser_minimal_template():
    """不可编辑模板：你好世界。"""
    print("\n=== test_parser_minimal_template ===")
    source = "#：{【*/你好，世界/*】\n#：[你好，世界]……（0/1）\n}"
    _show_ast(source)
    assert True


def test_parser_segment_chain():
    """可编辑代码：段编号 + >> 链式。"""
    print("\n=== test_parser_segment_chain ===")
    source = (
        "#1：【启动服务】>>【读取配置】\n"
        "@1:端口=8080,路径=/data/config\n"
        "#1:？+？=？\n"
        "#1:端口+路径=连接\n"
        "#1:[连接成功]\n"
    )
    _show_ast(source)
    assert True


def test_parser_output_trail():
    """输出追踪 + 循环 + 路径（向后兼容：无子文件，仅全局循环后文件路径）。"""
    print("\n=== test_parser_output_trail ===")
    source = "#2:[15平方米]…2（0/4）00001……（0/2）【file_2.matha】"
    _show_ast(source)
    assert True


def _find_output_trail(program):
    """从 program 中找到第一个 OutputTrail 节点。"""
    for decl in program.decls:
        body = getattr(decl, "body", None)
        content = getattr(body, "content", None)
        if hasattr(content, "subfiles"):
            return content
    return None


def test_parser_subfile_ref():
    """M3.3 子文件引用：段循环后【子文件|子文件】，全局循环后【文件/路径】。"""
    print("\n=== test_parser_subfile_ref ===")
    # 完整末行形态：段循环 + 子文件(|分隔) + 全局编号 + 全局循环 + 文件路径
    source = "#2:[结果]…2（0/4）【sub1.matha|sub2.matha】00001……（0/2）【file_2.matha】"
    _show_ast(source)
    program = parse(source)
    trail = _find_output_trail(program)
    assert trail is not None, "未找到 OutputTrail"
    assert trail.subfiles == ["sub1.matha", "sub2.matha"], f"子文件解析错误: {trail.subfiles}"
    assert trail.file_ref == "file_2.matha", f"文件路径解析错误: {trail.file_ref}"
    assert trail.global_code_id == "00001", f"全局编号错误: {trail.global_code_id}"
    assert trail.seg_loop.seg_id == 2
    assert trail.global_loop.fraction.current == 0
    print(f"  OK: subfiles={trail.subfiles}  file_ref={trail.file_ref}  id={trail.global_code_id}")
    assert True


def test_parser_subfile_single():
    """M3.3 单个子文件（无 | 分隔）+ 仅段循环，无全局循环/文件路径。"""
    print("\n=== test_parser_subfile_single ===")
    source = "#1:[输出]…1（0/1）【only_sub.matha】"
    _show_ast(source)
    program = parse(source)
    trail = _find_output_trail(program)
    assert trail is not None, "未找到 OutputTrail"
    assert trail.subfiles == ["only_sub.matha"], f"子文件解析错误: {trail.subfiles}"
    assert trail.file_ref is None, f"不应有 file_ref: {trail.file_ref}"
    assert trail.global_loop is None
    print(f"  OK: subfiles={trail.subfiles}  file_ref={trail.file_ref}")
    assert True


def test_parser_arithmetic():
    """算术表达式。"""
    print("\n=== test_parser_arithmetic ===")
    _show_ast("2 ^ 3 + 4 * 5")
    _show_ast("^9")
    _show_ast("a + b = c")
    assert True


def test_parser_set_up():
    """@ 设定双形式。"""
    print("\n=== test_parser_set_up ===")
    _show_ast("@(a|b|c)")
    _show_ast("@:单价=10元,数量=3")
    assert True


if __name__ == "__main__":
    test_lexer_basic()
    test_parser_minimal_template()
    test_parser_segment_chain()
    test_parser_output_trail()
    test_parser_subfile_ref()
    test_parser_subfile_single()
    test_parser_arithmetic()
    test_parser_set_up()
    print("\n=== 全部冒烟测试完成 ===")
