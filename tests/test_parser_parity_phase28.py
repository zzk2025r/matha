# -*- coding: utf-8 -*-
"""阶段 28b 三锁：parser/lexer 语法完备性 + Matha↔宿主 AST 全语料对拍。

自举解析器（lexer.matha/stdlib.matha/parser.matha 编译为字节码跑在 VM 上）
与宿主解析器（src/parser.py）对同一源码产出的 AST 逐节点结构一致：

  1. 块体/顶层双轨分派（在块体 旗标）——宿主 _parse_top_decl vs
     _parse_statement 的 `#`/【 双轨行为在自举侧逐分支镜像：
     `#：`/`#N：` 顶层产 机械单元（含 { 合并），语句位产 生成语句（无包装）；
     【…】 顶层（*/ 标注形）产 自然语言块，语句位产 读取块；链内 【 项
     恒为读取块（宿主 _parse_mech_stmt → _parse_read_or_command）。
  2. 占位符 ？/？名 → is_placeholder=True 的 Variable；设值裸标识符值 →
     配置字符串；占位符值保持 Variable（宿主 _parse_placeholder_var/423）。
  3. typeof 关键字 → TypeOfExpr（缺关键字表条目时被并列应用吞成 FuncApp）；
     值结尾 token 集（布尔/占位符）保证 `: 假\n[r6]` 不被下标吞并。
  4. 全语料对拍：Matha dict-AST 转换为宿主 dataclass AST 后与宿主
     py_parse 产物逐字段相等（先前分歧回归文件 + 自举链自文件）。
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.set_int_max_str_digits(0)

from pathlib import Path

from src.parser import parse as py_parse
from src.mbc.compiler import Compiler
from src.mbc.vm import VM
from src import ast_nodes as ast

_ROOT = Path(__file__).resolve().parent.parent
_BOOT_FILES = ["matha/lexer.matha", "matha/stdlib.matha", "matha/parser.matha"]


# ============================================================
# 对拍基础设施（28b 探针移植：转换器 + 差异行走器）
# ============================================================

def conv_type(d):
    """类型表达式：基本类型/元组类型/集合类型 → BasicType/TupleType/SetType"""
    if d is None:
        return None
    t = d["类型"]
    if t == "基本类型":
        return ast.BasicType(name=d["名"])
    if t == "元组类型":
        return ast.TupleType(types=[conv_type(x) for x in d["types"]])
    if t == "集合类型":
        return ast.SetType(elem_type=conv_type(d["元素"]))
    raise ValueError(f"未知类型节点 {t!r}")


def func_type_of(param_types, ret):
    """宿主 _parse_func_def 的 func_type 合成规则（4141-4147 同构）"""
    n = len(param_types)
    if n == 0:
        pt = ast.BasicType(name="Unit")
    elif n == 1:
        pt = conv_type(param_types[0]) or ast.BasicType(name="Int")
    else:
        pt = ast.TupleType(types=[conv_type(t) or ast.BasicType(name="Int")
                                  for t in param_types])
    return ast.FuncType(param_type=pt, return_type=conv_type(ret))


def _empty_program(d):
    return isinstance(d, dict) and d.get("类型") == "程序" and d.get("声明") == []


def is_block(d):
    """Matha 块体：解析语句列表 产出的 程序 节点（嵌套语境）"""
    return isinstance(d, dict) and d.get("类型") == "程序"


def conv_lambda_param(p):
    if isinstance(p, str):
        return ast.Variable(name=p)
    if isinstance(p, dict) and p.get("类型") == "变量":
        return ast.Variable(name=p["名"], is_placeholder=p.get("是占位", False))
    raise ValueError(f"未知 lambda 参数形态 {p!r}")


def conv(n):
    if n is None:
        return None
    if isinstance(n, bool) or isinstance(n, (int, float, str)):
        return n
    if isinstance(n, list):
        return [conv(x) for x in n]
    if not isinstance(n, dict):
        raise ValueError(f"未知节点 {type(n).__name__} {n!r}")
    t = n["类型"]

    if t == "程序":  # 嵌套块体
        return ast.CodeBlock(stmts=[conv(x) for x in n["声明"]])

    if t == "函数定义":
        return ast.FuncDef(
            name=n["名"], annotation=None,
            func_type=func_type_of(n["参数类型"], n["返回类型"]),
            body=ast.Lambda(params=[conv_lambda_param(p) for p in n["参数"]],
                            body=conv(n["体"])))

    if t == "绑定":
        return ast.Binding(target=ast.Variable(name=n["名"]),
                           annotation=None, value=conv(n["值"]))

    if t == "let绑定":
        ps = n.get("参数")
        body = conv(n["体"]) if n["有体"] else None
        if ps:  # 函数式直接体：宿主值=裸体、params=带类型参数
            value = conv(n["值"]["体"])
            params = [(p["名"], conv_type(p["类型"])) for p in ps]
        else:
            value = conv(n["值"])
            params = []
        return ast.LetBinding(name=n["名"], value=value,
                              is_recursive=n["递归"], params=params, body=body)

    if t == "let元组绑定":
        return ast.LetTupleBinding(names=n["名字"], value=conv(n["值"]),
                                   body=conv(n["体"]) if n["有体"] else None)

    if t == "输出":
        return ast.Output(expr=conv(n["expr"]), target="printf")

    if t == "空输出":
        return ast.Output(expr=None)

    if t == "机械单元":
        b = n["body"]
        body = [conv(x) for x in b] if isinstance(b, list) else conv(b)
        return ast.MechUnit(generate=ast.Generate(seg_id=n["段号"]), body=body)

    if t == "生成语句":
        return ast.GenStmt(generate=ast.Generate(seg_id=n["段号"]),
                           content=conv(n["content"]))

    if t == "链式语句":
        return ast.ChainStmt(stmts=[conv(x) for x in n["语句"]])

    if t == "输出追踪":
        gid = n.get("全局编号")
        return ast.OutputTrail(
            output=conv(n["输出"]),
            seg_loop=conv(n.get("段循环")),
            subfiles=n.get("子文件"),
            global_code_id=str(gid) if gid is not None else None,
            global_loop=conv(n.get("全局循环")),
            file_ref=n.get("文件"))

    if t == "循环分数":
        return ast.LoopFraction(current=n["当前"], maximum=n["最大"])

    if t == "段循环":
        return ast.SegLoopSuffix(seg_id=n["段号"], fraction=conv(n["分数"]))

    if t == "抛出":
        return ast.RaiseExpr(value=conv(n["值"]))

    if t == "集合构造":
        form = n["form"]
        if form == "comprehension":
            variables = [(v["名"], conv(v["集合"])) for v in n["variables"]]
            conditions = [conv(c) for c in n["conditions"]]
            literals = None
        else:
            variables = None
            conditions = None
            literals = [conv(x) for x in n["literals"]]
        return ast.SetConstruct(form=form, variables=variables,
                                conditions=conditions, literals=literals,
                                output=conv(n["output"]) if form == "comprehension" else None)

    if t == "属于":
        return ast.Belongs(left=conv(n["左"]), right=conv(n["右"]))

    if t == "typeof":
        return ast.TypeOfExpr(operand=conv(n["操作数"]))

    if t == "同一性":
        return ast.IsExpr(left=conv(n["左"]), right=conv(n["右"]))

    if t == "try":
        fin = n["finally体"]
        fin_block = None if _empty_program(fin) else conv(fin)
        catch_body = None if n["捕获体"] is None else conv(n["捕获体"])
        return ast.TryStmt(try_block=conv(n["try体"]),
                           catch_var=n["捕获变量"] or None,
                           catch_block=catch_body,
                           finally_block=fin_block)

    if t == "if":
        then = n["真分支"]
        els = n["假分支"]
        if is_block(then):  # 语句形式：if cond { 块 } [else { 块 }]
            if els is None or _empty_program(els):
                else_block = None
            else:
                else_block = conv(els)
            return ast.IfStmt(cond=conv(n["条件"]), then_block=conv(then),
                              else_block=else_block)
        return ast.IfExpr(cond=conv(n["条件"]), then=conv(then),
                          else_=conv(els))

    if t == "自然语言块":
        return ast.NLBlock(annotation=ast.Annotation(text=n["标注"]),
                           natural_lang=n["正文"])

    if t == "读取块":
        return ast.ReadBlock(content=n["内容"])

    if t == "全局循环":
        return ast.GlobalLoopSuffix(fraction=conv(n["分数"]))

    if t == "命令文字":
        return ast.CommandLiteral(text=n["文本"], form=n["形式"])

    if t == "定义运算符":
        return ast.DefineOp(symbol=n["符号"], precedence=n["优先级"],
                            assoc=n["结合性"], token_type=None)

    if t == "通道":
        return ast.ChanExpr(elem_type=n["元素类型"], buffer_size=None)

    if t == "发送":
        return ast.SendExpr(channel=conv(n["通道"]), value=conv(n["值"]))

    if t == "while":
        return ast.WhileStmt(cond=conv(n["条件"]), block=conv(n["体"]))

    if t == "for":
        return ast.ForStmt(var=n["变量"], iterable=conv(n["迭代"]),
                           block=conv(n["体"]))

    if t == "match":
        branches = []
        for b in n["分支"]:
            pat, guard, body = b
            branches.append((conv(pat), conv(guard) if guard is not None else None,
                             conv(body)))
        return ast.MatchStmt(scrutinee=conv(n["scrutinee"]), branches=branches)

    if t == "switch":
        cases = [(conv(v), conv(b)) for v, b in n["分支"]]
        return ast.SwitchStmt(value=conv(n["值"]), cases=cases,
                              default_block=conv(n["默认"]))

    if t == "构造子模式":
        return ast.ConstructorPat(name=n["名"], fields=[conv(x) for x in n["字段"]])

    if t == "go":
        return ast.GoStmt(expr=conv(n["expr"]))

    if t == "lambda":
        return ast.Lambda(params=[conv_lambda_param(p) for p in n["参数"]],
                          body=conv(n["体"]))

    if t == "二元运算":
        return ast.BinaryOp(op=n["运算符"], left=conv(n["左"]), right=conv(n["右"]))

    if t == "自定义二元":
        return ast.BinaryOp(op=n["运算符"], left=conv(n["左"]), right=conv(n["右"]))

    if t == "一元运算":
        return ast.UnaryOp(op=n["运算符"], operand=conv(n["操作数"]))

    if t == "函数应用":
        return ast.FuncApp(func=conv(n["函数"]), arg=conv(n["参数"]))

    if t == "整数":
        return ast.IntegerLit(value=n["值"], unit="")

    if t == "浮点":
        return ast.FloatLit(value=n["值"], unit="")

    if t == "字符串":
        return ast.StringLit(value=n["值"])

    if t == "布尔":
        return ast.BoolLit(value=n["值"])

    if t == "变量":
        return ast.Variable(name=n["名"], is_placeholder=n.get("是占位", False))

    if t == "设值":
        return ast.SetUp(items=[conv(x) for x in n["项"]], form=n["形式"])

    if t == "设值项":
        ann = conv(n["标注"]) if n.get("标注") else None
        return ast.SetUpItem(target=conv(n["目标"]), annotation=ann,
                             value=conv(n["值"]) if n["值"] is not None else None)

    if t == "全局标识":
        return ast.GlobalIdStmt(code_id=n["编号"], is_placeholder=n["是占位"])

    if t == "外来声明":
        return ast.ForeignDecl(text=n["文本"], prefix="#", lang="")

    if t == "结构体":
        return ast.StructDef(name=n["名"], type_params=[], annotation=None,
                             fields=[(f["名"], conv_type(f["类型"])) for f in n["字段"]])

    if t == "枚举":
        return ast.EnumDef(name=n["名"], type_params=[], annotation=None,
                           ctors=list(n["构造子"]))

    if t == "属性":
        # 宿主 _parse_postfix PUNCT_DOT → PathExpr(left=expr, right=字段名字符串)
        return ast.PathExpr(left=conv(n["对象"]), right=n["名"])

    if t == "列表":
        return ast.ListLiteral(elements=[conv(x) for x in n["元素"]])

    if t == "元组":
        return ast.TupleExpr(elements=[conv(x) for x in n["元素"]])

    if t == "下标":
        return ast.IndexExpr(container=conv(n["容器"]), index=conv(n["索引"]))

    if t == "安全路径":
        right = conv(n["右"]) if n["是下标"] else n["右"]
        return ast.SafePathExpr(left=conv(n["左"]), is_index=n["是下标"],
                                right=right)

    if t == "尖括号":
        return ast.AngleExpr(expr=conv(n["内"]))

    if t == "切片":
        def bound(v):
            if v is None:
                return None
            if isinstance(v, dict) and v.get("类型") == "整数" and v.get("值") == -1:
                return None
            return conv(v)
        return ast.SliceExpr(container=conv(n["容器"]),
                             start=bound(n["开始"]), end=bound(n["结束"]))

    if t == "字典":
        return ast.DictLiteral(keys=[conv(k) for k in n["键"]],
                               values=[conv(v) for v in n["值"]])

    if t == "模块":
        return ast.ModuleDecl(name=n["名"], annotation=None,
                              decls=[conv(x) for x in n["声明"]])

    if t == "导入":
        return ast.ImportDecl(module_name=n["模块名"],
                              import_list=n["名字"] or None, alias=None)

    if t == "返回语句":
        return ast.ReturnStmt(value=conv(n["值"]))

    if t == "跳出语句":
        return ast.BreakStmt()

    if t == "继续语句":
        return ast.ContinueStmt()

    raise ValueError(f"未支持的 Matha 节点类型 {t!r}")


def _show(x, limit=200):
    s = repr(x)
    return s if len(s) <= limit else s[:limit] + "…"


def diff(a, b, path, out, max_out=8):
    if len(out) >= max_out:
        return
    from dataclasses import fields, is_dataclass
    if is_dataclass(a) and is_dataclass(b):
        if type(a) is not type(b):
            out.append((path, f"类型 {type(a).__name__} ≠ {type(b).__name__}",
                        _show(a), _show(b)))
            return
        for f in fields(type(a)):
            diff(getattr(a, f.name), getattr(b, f.name),
                 f"{path}.{f.name}", out, max_out)
        return
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append((path, f"长度 {len(a)} ≠ {len(b)}", _show(a), _show(b)))
            return
        for i, (x, y) in enumerate(zip(a, b)):
            diff(x, y, f"{path}[{i}]", out, max_out)
        return
    if isinstance(a, tuple) and isinstance(b, tuple):
        if len(a) != len(b):
            out.append((path, f"长度 {len(a)} ≠ {len(b)}", _show(a), _show(b)))
            return
        for i, (x, y) in enumerate(zip(a, b)):
            diff(x, y, f"{path}({i})", out, max_out)
        return
    if type(a) is not type(b) and not (a is None and b is None):
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) and a == b:
            return
        out.append((path, f"形态 {type(a).__name__} ≠ {type(b).__name__}",
                    _show(a), _show(b)))
        return
    try:
        eq = a == b
    except Exception:
        eq = False
    if not eq:
        out.append((path, "值不等", _show(a), _show(b)))


# ============================================================
# 自举 VM fixture
# ============================================================

@pytest.fixture(scope="module")
def mvm():
    comp = Compiler()
    decls = []
    for rel in _BOOT_FILES:
        src = (_ROOT / rel).read_text(encoding="utf-8")
        decls.extend(py_parse(src.lstrip("\ufeff")).decls)
    comp.compile_program(ast.Program(decls=decls))
    vm = VM(comp.mod)
    vm.run()
    return vm


def matha_parse(mvm, src):
    toks = mvm.call("tokenize", src)
    return mvm.call("parse", toks)


def assert_parity(mvm, src, label=""):
    host_tree = py_parse(src)
    mtree = matha_parse(mvm, src)
    rebuilt = ast.Program(decls=[conv(x) for x in mtree["声明"]])
    out = []
    diff(host_tree, rebuilt, label or "<src>", out)
    assert not out, "\n".join(f"{p}\n  host: {a}\n  matha: {b}  [{w}]"
                              for p, w, a, b in out)


def parse_body(mvm, src):
    """解析并返回首个顶层声明体（module decls / 语句列表）的语句序列。"""
    return matha_parse(mvm, src)["声明"]


# ============================================================
# 锁 1：块体/顶层双轨分派
# ============================================================

def test_top_level_hash_is_mech_unit(mvm):
    """顶层 `#N：…` → 机械单元（宿主 _parse_top_decl → _parse_mech_unit）。"""
    decls = parse_body(mvm, "#1：【命令】\n")
    assert len(decls) == 1
    assert decls[0]["类型"] == "机械单元"
    assert decls[0]["段号"] == 1


def test_body_hash_is_gen_stmt(mvm):
    """语句位 `#N：…` → 生成语句直返（宿主 _parse_statement →
    _parse_gen_or_file_marker，无机械单元包装）。"""
    src = "func f() -> Int = () => {\n  #1：【命令】\n}\n"
    fn = parse_body(mvm, src)[0]
    body_stmts = fn["体"]["声明"]
    assert len(body_stmts) == 1
    assert body_stmts[0]["类型"] == "生成语句"
    assert body_stmts[0]["段号"] == 1


def test_top_level_hash_body_merge(mvm):
    """顶层 `#N：命令` 后紧跟 { → 体 = [生成语句, 块]（宿主 623-628 合并）。"""
    src = "#1：【命令】\n{\n  x = 1\n}\n"
    unit = parse_body(mvm, src)[0]
    assert unit["类型"] == "机械单元"
    assert isinstance(unit["body"], list)
    assert unit["body"][0]["类型"] == "生成语句"
    assert unit["body"][1]["类型"] == "程序"


def test_body_hash_no_merge(mvm):
    """语句位生成语句不合并后续块（合并仅存在于宿主 _parse_mech_unit）。"""
    src = "func f() -> Int = () => {\n  #1：【命令】\n}\n"
    fn = parse_body(mvm, src)[0]
    body_stmts = fn["体"]["声明"]
    assert body_stmts[0]["类型"] == "生成语句"


def test_top_level_annot_block(mvm):
    """顶层 【*/…/*】 → 自然语言块（宿主 _parse_top_decl 275）。"""
    src = "【*/标注/*】\n"
    decls = parse_body(mvm, src)
    assert decls[0]["类型"] == "自然语言块"


def test_body_read_block(mvm):
    """语句位 【…】 → 读取块（宿主 _parse_statement 797 →
    _parse_read_or_command：原始内文含 */…/* 标记）。"""
    src = "func f() -> Int = () => {\n  【*/正文/*】\n}\n"
    fn = parse_body(mvm, src)[0]
    stmts = fn["体"]["声明"]
    assert len(stmts) == 1
    assert stmts[0]["类型"] == "读取块"
    assert stmts[0]["内容"] == "*/正文/*"


def test_chain_read_item_is_read_block(mvm):
    """链内 【…】 项恒为读取块（宿主 _parse_chain → _parse_mech_stmt 797）；
    链首项（#N： 后首个）仍为命令字面量。语句位 《…》 宿主报
    ParseError（_is_read_open 不含 《），Matha 表达式位宽容接受——登记不修。"""
    src = "#1：【首项】>>【次项】\n"
    unit = parse_body(mvm, src)[0]
    chain = unit["body"]
    assert chain["类型"] == "链式语句"
    first, second = chain["语句"][0], chain["语句"][1]
    assert first["content"]["类型"] == "命令文字"
    assert second["类型"] == "读取块"
    assert second["内容"] == "次项"


def test_bare_hash_top_wrapped_body_direct(mvm):
    """裸 # 行：顶层包 机械单元(Generate(None)+ForeignDecl)；语句位直返。"""
    top = parse_body(mvm, "# 注释\n")[0]
    assert top["类型"] == "机械单元"
    assert top["body"]["类型"] == "外来声明"
    body = parse_body(mvm, "func f() -> Int = () => {\n  # 注释\n}\n")[0]
    stmts = body["体"]["声明"]
    assert stmts[0]["类型"] == "外来声明"


# ============================================================
# 锁 2：占位符 ？/？名 与设值面
# ============================================================

def test_placeholder_variants(mvm):
    """？ → 占位变量；？x → 合成以 x 为名的占位变量（宿主
    _parse_placeholder_var 3066-3072）。"""
    src = "x = ？\ny = ？名\n"
    decls = parse_body(mvm, src)
    assert decls[0]["值"]["是占位"] is True
    assert decls[0]["值"]["名"] == "？"
    assert decls[1]["值"]["是占位"] is True
    assert decls[1]["值"]["名"] == "名"


def test_placeholder_not_merged_across_newline(mvm):
    """？ 行尾换行后随标识符不得合并（宿主看原始下一 token，不跳换行）。"""
    src = "x = ？\ny = 2\n"
    decls = parse_body(mvm, src)
    assert len(decls) == 2
    assert decls[0]["值"]["名"] == "？"


def test_set_up_placeholder_and_config_string(mvm):
    """@：cmd 形式 ？ 目标占位；裸标识符值 → 配置字符串；占位符值保持
    Variable（宿主 _parse_set_up 372/423）。"""
    src = "@：【文本】，a=2，k=Config\n"
    setup = parse_body(mvm, src)[0]
    items = setup["项"]
    assert items[0]["目标"]["是占位"] is True
    assert items[0]["值"]["类型"] == "字符串"
    assert items[1]["值"]["类型"] == "整数"
    assert items[2]["值"]["类型"] == "字符串"
    assert items[2]["值"]["值"] == "Config"


# ============================================================
# 锁 3：typeof 关键字 + 值结尾换行判定
# ============================================================

def test_typeof_keyword(mvm):
    """typeof <expr> → typeof 节点（宿主 TypeOfExpr）；不得被并列应用
    吞成 FuncApp(Variable typeof, x)。"""
    src = "y = typeof x\n"
    decls = parse_body(mvm, src)
    assert decls[0]["值"]["类型"] == "typeof"
    assert decls[0]["值"]["操作数"]["名"] == "x"


def test_newline_value_end_no_index_swallow(mvm):
    """`: 假\n[r6]` —— 布尔是值结尾 token，[ 开启新输出语句而非下标
    （bootstrap_test_v2 测试 7 形态；宿主靠原始换行终止语句）。"""
    src = "r6 = 5 > 3 ? 真 : 假\n[r6]\nr7 = 5 < 3 ? 真 : 假\n[r7]\n"
    decls = parse_body(mvm, src)
    assert len(decls) == 4, f"应为 4 条语句（2 绑定 + 2 输出），得 {len(decls)}"
    assert decls[1]["类型"] == "输出追踪"
    assert decls[3]["类型"] == "输出追踪"


# ============================================================
# 锁 4：全语料对拍（先前分歧回归文件 + 自举链自文件）
# ============================================================

_PARITY_FILES = [
    "matha/lexer.matha",
    "matha/stdlib.matha",
    "matha/parser.matha",
    "matha/bootstrap_test_v2.matha",
    "matha/examples/01_arithmetic.matha",
    "matha/frontends/multi_lang.matha",
    "matha/vm/matha_vm.matha",
    "matha/resource/os/filesystem_math.matha",
    "matha/knowledge/physics/celestial.matha",
]


@pytest.mark.parametrize("rel", _PARITY_FILES)
def test_corpus_parity(mvm, rel):
    src = (_ROOT / rel).read_text(encoding="utf-8").lstrip("\ufeff")
    assert_parity(mvm, src, rel)
