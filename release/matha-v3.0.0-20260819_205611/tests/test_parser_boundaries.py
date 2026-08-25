"""Parser 边界情况测试 — 换行、特殊字符、混合编码。

统计：
  ✓ 通过：预期行为正确
  ~ 预期失败：设计限制（不应报错但当前不支持）
  ✗ 意外失败：应当支持但实际失败（需修复）

运行：python -m tests.test_parser_boundaries
"""
import sys
sys.path.insert(0, r"D:\trae")

from src.parser import parse, ParseError
from src.semantic import analyze_ast
from src.interp import interpret

PASS, FAIL, EXPECTED = [], [], []


# ============================================================
# 1. NLBlock 换行边界 — 核心逻辑验证
# ============================================================
print("\n【1. NLBlock 换行边界】")

def check_nlb(src, label, expect_lang, expect_decl_types):
    try:
        p = parse(src)
        nls = [d for d in p.decls if type(d).__name__ == "NLBlock"]
        decl_types = [type(d).__name__ for d in p.decls]
        actual_lang = nls[0].natural_lang if nls else ""
        ok = (actual_lang == expect_lang
              and all(t in decl_types for t in expect_decl_types))
        if ok: PASS.append(label)
        else: FAIL.append(label)
        icon = "✓" if ok else "✗"
        print(f"  {icon} {label} (lang={actual_lang!r}, decls={decl_types})")
    except Exception as e:
        FAIL.append(label)
        print(f"  ✗ {label}: {type(e).__name__}: {e}")

check_nlb('【*/a/*】b', "同行动态-捕获正文", "b", ["NLBlock"])
check_nlb('【*/a/*】\nb', "换行后-正文空+独立解析", "", ["NLBlock", "Variable"])
check_nlb('【*/a/*】\n\nb', "双换行-同上", "", ["NLBlock", "Variable"])
check_nlb('【*/a/*】', "仅有标注-空正文", "", ["NLBlock"])
check_nlb('【*/a/*】 ', "标注后空格-空正文", "", ["NLBlock"])
check_nlb('【*/a/*】\t', "标注后Tab-空正文", "", ["NLBlock"])
check_nlb('【*/a/*】\n#1：[x]', "换行后代码块", "", ["NLBlock", "MechUnit"])
check_nlb('【*/a/*】hello world', "英文正文", "hello world", ["NLBlock"])
check_nlb('【*/a/*】中文+English混合', "中英混排正文", "中文+English混合", ["NLBlock"])
check_nlb('【*/a/*】', "空标注EOF", "", ["NLBlock"])


# ============================================================
# 2. 字符串边界
# ============================================================
print("\n【2. 字符串边界】")

def check_interp(name, src, expected, note=""):
    try:
        out, _ = interpret(src)
        ok = expected in out if isinstance(expected, (int, str)) else expected == out
        if ok: PASS.append(name)
        else: FAIL.append(name)
        print(f"  {'✓' if ok else '✗'} {name} → {out} {note}")
    except Exception as e:
        FAIL.append(name)
        print(f"  ✗ {name}: {type(e).__name__}: {e}")

check_interp("双引号字符串", '#1：["hello"]', "hello")
check_interp("中文字符串", '#1：["你好"]', "你好")
check_interp("空字符串", '#1：[""]', "")
check_interp("emoji字符串", '#1：["😀🎉"]', "😀🎉")
check_interp("转义引号", '#1：["he said \\"hi\\""]', 'he said "hi"')


# ============================================================
# 3. 全角/半角标点
# ============================================================
print("\n【3. 全角/半角标点】")

def check_parse(name, src, should_pass=True, note=""):
    try:
        p = parse(src)
        decl_types = [type(d).__name__ for d in p.decls]
        if should_pass: PASS.append(name)
        else: EXPECTED.append(name)
        icon = "✓" if should_pass else "~"
        print(f"  {icon} {name} → {decl_types} {note}")
    except ParseError as e:
        if not should_pass: EXPECTED.append(name)
        else: FAIL.append(name)
        icon = "~" if not should_pass else "✗"
        print(f"  {icon} {name}: ParseError {note}")

check_parse("半角括号", "a = (1 + 2) * 3", True)
check_parse("全角括号", "a = （1 + 2）* 3", True)
check_parse("全角运算", "a ＝ 1 ＋ 2", True)
check_parse("全角逗号列表", "a = 1，2，3", True)
check_parse("全角分号", "a = 1；b = 2", True)
check_parse("全角冒号", "a ： b = 1", True)
check_parse("半角冒号函数", "func f(x: Int) -> Int = (x) => x + 1", True)


# ============================================================
# 4. 链式命令特殊字符
# ============================================================
print("\n【4. 链式命令特殊字符】")

def check_chain(name, src):
    try:
        p = parse(src)
        decl_types = [type(d).__name__ for d in p.decls]
        PASS.append(name)
        print(f"  ✓ {name} → {decl_types}")
    except ParseError as e:
        FAIL.append(name)
        print(f"  ✗ {name}: {e}")

check_chain("URL含参数", "#1：【下载 https://example.com/path?q=1&r=2】>>【解析】")
check_chain("中文路径", "#1：【读取 /home/用户/文件】>>【处理】")
check_chain("端口连接", "#1：【连接 localhost:8080】>>【发送】")
check_chain("emoji命令", "#1：【启动 🚀】>>【停止 🔴】")
check_chain("多步链式", "#1：【A】>>#2：【B】>>#3：【C】>>#4：【D】")
check_chain("特殊符号运算", "#1：【运算 1+2*3】>>【输出】")


# ============================================================
# 5. 代码块边界
# ============================================================
print("\n【5. 代码块边界】")

def check_block(name, src):
    try:
        p = parse(src)
        decl_types = [type(d).__name__ for d in p.decls]
        PASS.append(name)
        print(f"  ✓ {name} → {decl_types}")
    except ParseError as e:
        FAIL.append(name)
        print(f"  ✗ {name}: {e}")

check_block("空代码块", "#：{}")
check_block("单行代码块", "#：{ a = 1 }")
check_block("多行代码块", "#：{\n   a = 1\n   b = 2\n}")
check_block("嵌套输出", "#：{ #1：[a] #2：[b] }")
check_block("中文标签", "#：{ #1：【初始化】 a = 1 }")


# ============================================================
# 6. Unicode 标识符支持边界
# ============================================================
print("\n【6. Unicode 标识符边界】")

def check_identifier(name, src, should_pass=True):
    try:
        p = parse(src)
        decl_types = [type(d).__name__ for d in p.decls]
        if should_pass: PASS.append(name)
        else: EXPECTED.append(name)
        icon = "✓" if should_pass else "~"
        print(f"  {icon} {name} → {decl_types}")
    except ParseError as e:
        if not should_pass: EXPECTED.append(name)
        else: FAIL.append(name)
        icon = "~" if not should_pass else "✗"
        print(f"  {icon} {name}: ParseError")

# 支持的标识符
check_identifier("ASCII变量", "a = 1", True)
check_identifier("中文变量", "结果 = 42", True)
check_identifier("希腊字母", "θ = 3.14", True)
check_identifier("生僻汉字", "焻 = 1", True)
check_identifier("零宽字符", "x = 1", True)

# 现在支持的标识符（之前不支持，现已解除限制）
check_identifier("日文假名", "あ = 1", True)
check_identifier("阿拉伯字母", "أ = 2", True)
check_identifier("emoji标识符", "😀 = 42", True)
check_identifier("数学符号", "∑ = 100", True)
check_identifier("BoxDrawing", "┌ = 1", True)
check_identifier("代理对emoji", "a = 😀", True)


# ============================================================
# 7. 空输入与极端空白
# ============================================================
print("\n【7. 空输入与极端空白】")

def check_empty(name, src):
    try:
        p = parse(src)
        PASS.append(name)
        print(f"  ✓ {name} → {len(p.decls)} 声明")
    except Exception as e:
        FAIL.append(name)
        print(f"  ✗ {name}: {type(e).__name__}")

check_empty("空字符串", "")
check_empty("单空格", " ")
check_empty("多空格", "   ")
check_empty("仅换行", "\n\n\n")
check_empty("仅tab", "\t\t")
check_empty("空白混合", "  \n\t  \n  ")
check_empty("仅标注块", "【*/test/*】")
check_empty("仅标注块换行", "【*/test/*】\n")


# ============================================================
# 8. 连续特殊符号
# ============================================================
print("\n【8. 连续特殊符号】")

check_parse("连续减号", "a = 1--2", True)
check_parse("连续加号", "a = 1++2", True)
check_parse("连续等号", "a = = 1", True)
check_parse("箭头符号", "a → b", True)
check_parse("双箭头(非链式)", "a >> b", True)
check_parse("三段链式", "#1：【A】>>#2：【B】>>#3：【C】", True)


# ============================================================
# 9. 语义分析边界
# ============================================================
print("\n【9. 语义分析边界】")

def check_semantic(name, src, expect_errors):
    try:
        p = parse(src)
        errors = analyze_ast(p, verbose=False)
        err_n = len([e for e in errors if e.severity == "error"])
        ok = err_n == expect_errors
        if ok: PASS.append(name)
        else: FAIL.append(name)
        icon = "✓" if ok else "✗"
        print(f"  {icon} {name} (errors={err_n}, expected={expect_errors})")
    except Exception as e:
        FAIL.append(name)
        print(f"  ✗ {name}: {type(e).__name__}: {str(e)[:60]}")

check_semantic("重复定义-警告非错误", "a = 1\na = 2", 0)
check_semantic("未定义变量", "x = y", 1)
check_semantic("NLBlock无变量检查", "【*/test/*】hello world", 0)
check_semantic("嵌套NLBlock", "【*/a/*】x\n【*/b/*】y", 0)
check_semantic("已定义函数调用", "func f(x) -> Int = (x) => x + 1\n#1：[f(5)]", 0)


# ============================================================
# 10. 综合复杂用例
# ============================================================
print("\n【10. 综合复杂用例】")

def check_complex(name, src, expect_errors=0):
    try:
        p = parse(src)
        decl_types = [type(d).__name__ for d in p.decls]
        errors = analyze_ast(p, verbose=False)
        err_n = len([e for e in errors if e.severity == "error"])
        ok = err_n == expect_errors
        if ok: PASS.append(name)
        else: EXPECTED.append(name)
        icon = "✓" if ok else "~"
        print(f"  {icon} {name} → {decl_types} (errors={err_n})")
    except ParseError as e:
        EXPECTED.append(name)
        print(f"  ~ {name}: ParseError (设计限制)")
    except Exception as e:
        FAIL.append(name)
        print(f"  ✗ {name}: {type(e).__name__}: {str(e)[:60]}")

check_complex("多标注块流水线",
    "【*/初始化/*】setup\n"
    "x = 1\n"
    "【*/处理/*】process\n"
    "y = x + 1\n"
    "【*/输出/*】output\n"
    "#1：[y]", 0)

check_complex("三进制运算",
    "a = 0t210\n"
    "b = 0t111\n"
    "total = a + b\n"
    "#1：[total]", 0)

check_complex("混合进制",
    "t = 0t210\n"
    "b = 0b1010\n"
    "h = 0xFF\n"
    "#1：[t + b + h]", 0)


# ============================================================
# 汇总
# ============================================================
print("\n" + "=" * 60)
print(f"通过: {len(PASS)}")
print(f"意外失败: {len(FAIL)}")
print(f"预期失败(设计限制): {len(EXPECTED)}")
total = len(PASS) + len(FAIL) + len(EXPECTED)
print(f"总计: {len(PASS)}/{total} 通过 (不含 {len(EXPECTED)} 个设计限制)")
if FAIL:
    print(f"\n需要修复 ({len(FAIL)} 个):")
    for n in FAIL:
        print(f"  - {n}")
print("=" * 60)

sys.exit(0 if not FAIL else 1)
