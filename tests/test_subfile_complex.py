"""M3.3 子文件引用 + 文件路径 复杂解析测试。

验证段循环后【子文件/路径】（| 分隔多个）与全局循环后【文件/路径】（文件分割）
在各种形态下的解析正确性：同行 / 分行 / 完整末行 / 向后兼容。

运行：python -m tests.test_subfile_complex
"""

from src.parser import parse
from src.semantic import analyze_source
from src import ast_nodes as ast


# ============================================================
# 测试源码：一个"生成显示器配置"的多段程序，覆盖所有循环后缀形态
# ============================================================
SOURCE = """#：{
   #1：【加载配置】
   @1:配置=1
   #1：[1]…1（0/1）【config_loader.matha】

   #2：【计算分辨率】
   @2:宽=3840，高=2160
   #2：？*？=？
   #2：宽*高=8294400
   #2：[8294400]…2（0/4）【calc_core.matha|format_util.matha】00001……（0/2）【display_part2.matha】

   #3：【渲染输出】
   #3：[3]
   #3：…3（0/1）【render.matha】00002……（0/2）【display_part3.matha】
   #：【文件】
}"""


def _find_all_output_trails(program) -> list:
    """递归遍历 program，按代码顺序收集所有 OutputTrail 节点。

    OutputTrail 同时具有 subfiles 与 seg_loop 字段，据此识别。
    收集后不再深入其子节点（避免重复）。
    """
    trails: list = []

    def visit(node):
        if node is None:
            return
        # OutputTrail 识别
        if hasattr(node, "subfiles") and hasattr(node, "seg_loop"):
            trails.append(node)
            return
        # 容器字段
        for attr in ("decls", "stmts", "items", "branches", "ctors", "fields"):
            child = getattr(node, attr, None)
            if isinstance(child, list):
                for c in child:
                    visit(c)
        # 单节点字段
        for attr in ("body", "content", "generate", "output", "value"):
            child = getattr(node, attr, None)
            if child is not None and not isinstance(child, (str, int, float, bool, list)):
                visit(child)

    visit(program)
    return trails


def test_complex_parse():
    """复杂用例：解析并严格断言每个 OutputTrail 的循环后缀字段。"""
    print("\n=== test_complex_parse ===")
    print("--- 源码 ---")
    print(SOURCE)

    program = parse(SOURCE)
    trails = _find_all_output_trails(program)

    print(f"\n--- 共找到 {len(trails)} 个 OutputTrail ---")
    for i, t in enumerate(trails):
        print(f"  [{i}] subfiles={t.subfiles}  seg_loop={t.seg_loop}  "
              f"id={t.global_code_id}  global_loop={t.global_loop}  file_ref={t.file_ref}")

    # 期望 4 个 OutputTrail：
    #  [0] #1 同行：单子文件
    #  [1] #2 同行：完整末行形态（多子文件 + 全局编号 + 全局循环 + 文件路径）
    #  [2] #3 分行主输出：纯输出（无后缀）
    #  [3] #3 分行循环行：子文件 + 全局编号 + 全局循环 + 文件路径（expr=None）
    assert len(trails) == 4, f"期望 4 个 OutputTrail，实际 {len(trails)}"

    # ---- [0] #1：同行单子文件 ----
    t0 = trails[0]
    assert t0.subfiles == ["config_loader.matha"], f"[0] subfiles 错误: {t0.subfiles}"
    assert t0.seg_loop is not None and t0.seg_loop.seg_id == 1
    assert t0.seg_loop.fraction.current == 0 and t0.seg_loop.fraction.maximum == 1
    assert t0.global_code_id is None, f"[0] 不应有全局编号: {t0.global_code_id}"
    assert t0.global_loop is None, "[0] 不应有全局循环"
    assert t0.file_ref is None, f"[0] 不应有 file_ref: {t0.file_ref}"
    print("  ✓ [0] #1 同行单子文件 正确")

    # ---- [1] #2：完整末行形态 ----
    t1 = trails[1]
    assert t1.subfiles == ["calc_core.matha", "format_util.matha"], f"[1] subfiles 错误: {t1.subfiles}"
    assert t1.seg_loop.seg_id == 2
    assert t1.seg_loop.fraction.current == 0 and t1.seg_loop.fraction.maximum == 4
    assert t1.global_code_id == "00001", f"[1] 全局编号错误: {t1.global_code_id}"
    assert t1.global_loop is not None
    assert t1.global_loop.fraction.current == 0 and t1.global_loop.fraction.maximum == 2
    assert t1.file_ref == "display_part2.matha", f"[1] file_ref 错误: {t1.file_ref}"
    print("  ✓ [1] #2 完整末行形态（多子文件+编号+全局循环+文件路径） 正确")

    # ---- [2] #3 分行主输出：纯输出，无任何后缀（向后兼容） ----
    t2 = trails[2]
    assert t2.subfiles is None, f"[2] 不应有 subfiles: {t2.subfiles}"
    assert t2.seg_loop is None, "[2] 不应有段循环"
    assert t2.global_code_id is None and t2.global_loop is None and t2.file_ref is None
    print("  ✓ [2] #3 分行主输出（纯输出无后缀） 正确")

    # ---- [3] #3 分行循环行：seg_loop_line 形式 ----
    t3 = trails[3]
    assert t3.subfiles == ["render.matha"], f"[3] subfiles 错误: {t3.subfiles}"
    assert t3.seg_loop.seg_id == 3
    assert t3.seg_loop.fraction.current == 0 and t3.seg_loop.fraction.maximum == 1
    assert t3.global_code_id == "00002", f"[3] 全局编号错误: {t3.global_code_id}"
    assert t3.global_loop is not None
    assert t3.global_loop.fraction.current == 0 and t3.global_loop.fraction.maximum == 2
    assert t3.file_ref == "display_part3.matha", f"[3] file_ref 错误: {t3.file_ref}"
    # 分行循环行的 output.expr 应为 None（纯循环追踪行，主输出已在上方）
    assert t3.output.expr is None, f"[3] 分行循环行 output.expr 应为 None: {t3.output.expr}"
    print("  ✓ [3] #3 分行循环行（seg_loop_line + 完整后缀） 正确")

    print("\n=== 全部复杂解析断言通过 ===")
    assert True


def test_complex_semantic():
    """复杂用例：语义分析不产生 error 级错误（新字段不破坏语义检查）。"""
    print("\n=== test_complex_semantic ===")
    program, errors = analyze_source(SOURCE)

    err_errors = [e for e in errors if e.severity == "error"]
    warnings = [e for e in errors if e.severity == "warning"]

    print(f"  error 数: {len(err_errors)}    warning 数: {len(warnings)}")
    for e in errors:
        print(f"  [{e.severity}] {e.msg}")

    # 关键断言：不应有 error 级语义错误（子文件/文件路径引用不应触发报错）
    assert not err_errors, f"存在 error 级语义错误: {[e.msg for e in err_errors]}"
    print("  ✓ 无 error 级语义错误")
    assert True


def test_subfile_only_no_global():
    """边界：仅段循环 + 多个子文件，无全局循环/文件路径。"""
    print("\n=== test_subfile_only_no_global ===")
    src = "#1:[结果]…1（0/3）【a.matha|b.matha|c.matha】"
    program = parse(src)
    trails = _find_all_output_trails(program)
    assert len(trails) == 1
    t = trails[0]
    assert t.subfiles == ["a.matha", "b.matha", "c.matha"], f"三子文件解析错误: {t.subfiles}"
    assert t.seg_loop.fraction.maximum == 3
    assert t.global_loop is None and t.file_ref is None
    print(f"  ✓ 三个子文件 | 分隔: {t.subfiles}")
    assert True


def test_template_global_only():
    """边界：模板形式（无段号、无段循环），仅全局循环 + 文件路径。"""
    print("\n=== test_template_global_only ===")
    src = "#：[输出]……（0/1）【only_file.matha】"
    program = parse(src)
    trails = _find_all_output_trails(program)
    assert len(trails) == 1
    t = trails[0]
    assert t.subfiles is None, f"模板形式不应有 subfiles: {t.subfiles}"
    assert t.seg_loop is None, "模板形式不应有段循环"
    assert t.global_loop is not None
    assert t.global_loop.fraction.current == 0 and t.global_loop.fraction.maximum == 1
    assert t.file_ref == "only_file.matha", f"file_ref 错误: {t.file_ref}"
    print(f"  ✓ 模板形式全局循环+文件路径: file_ref={t.file_ref}")
    assert True


if __name__ == "__main__":
    test_complex_parse()
    test_complex_semantic()
    test_subfile_only_no_global()
    test_template_global_only()
    print("\n=== 全部 M3.3 复杂测试完成 ===")
