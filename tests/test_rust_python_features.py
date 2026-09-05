"""Rust 构造子模式、Python for 解构、类型推断增强测试。"""
import sys
sys.path.insert(0, r"D:\trae")
from src.interp import interpret, MathaRuntimeError
from src.typesystem_v2 import EnhancedTypeInferencer
from src.parser import parse


# ============================================================
# Rust 风格构造子模式
# ============================================================

def test_match_constructor_tuple():
    """构造子模式 Some(x) 匹配 list ["Some", value] 形式"""
    s = '''#：{
  opt = ["Some", 42]
  v = match opt {
    | Some(x) => x
    | _ => 0
  }
  #：[v]
}'''
    out, _ = interpret(s)
    assert out[0] == 42, out
    print("test_match_constructor_tuple ✓")


def test_match_constructor_nested():
    """嵌套构造子模式：Pair(a, b)"""
    s = '''#：{
  pair = ("Pair", 1, 2)
  v = match pair {
    | Pair(a, b) => a + b
    | _ => 0
  }
  #：[v]
}'''
    out, _ = interpret(s)
    assert out[0] == 3, out
    print("test_match_constructor_nested ✓")


def test_match_constructor_miss():
    """构造子不匹配时走通配符"""
    s = '''#：{
  opt = ["None"]
  v = match opt {
    | Some(x) => x
    | _ => 99
  }
  #：[v]
}'''
    out, _ = interpret(s)
    assert out[0] == 99, out
    print("test_match_constructor_miss ✓")


def test_match_constructor_bind_var():
    """构造子模式绑定变量不泄漏"""
    s = '''#：{
  opt = ("Some", 10)
  v = match opt {
    | Some(x) => x
    | _ => 0
  }
  #：[v]
}
result = 0
#：[result]'''
    out, _ = interpret(s)
    assert out[0] == 10, out
    assert out[1] == 0, out
    print("test_match_constructor_bind_var ✓")


# ============================================================
# Python 风格 for 解构
# ============================================================

def test_for_tuple_destructure():
    """for (a, b) in list_of_tuples 解构"""
    s = '''#：{
  result = 0
  items = [(1, "a"), (2, "b"), (3, "c")]
  for (a, b) in items {
    result = result + a
  }
  #：[result]
}'''
    out, _ = interpret(s)
    assert out[0] == 6, out  # 1+2+3
    print("test_for_tuple_destructure ✓")


def test_for_dict_iteration():
    """for x in dict 迭代键"""
    s = '''#：{
  result = 0
  d = {"a": 1, "b": 2, "c": 3}
  for k in d {
    result = result + 1
  }
  #：[result]
}'''
    out, _ = interpret(s)
    assert out[0] == 3, out
    print("test_for_dict_iteration ✓")


def test_for_set_iteration():
    """for x in set 迭代"""
    s = '''#：{
  result = 0
  s = {1, 2, 3}
  for x in s {
    result = result + x
  }
  #：[result]
}'''
    out, _ = interpret(s)
    assert out[0] == 6, out  # 1+2+3
    print("test_for_set_iteration ✓")


def test_for_tuple_destructure_dict():
    """for (k, v) in dict.items() 形式"""
    s = '''#：{
  result = 0
  d = {"a": 10, "b": 20}
  for (k, v) in d {
    result = result + v
  }
  #：[result]
}'''
    out, _ = interpret(s)
    assert out[0] == 30, out  # 10+20
    print("test_for_tuple_destructure_dict ✓")


def test_for_var_cleanup():
    """for 循环变量结束后清理"""
    s = '''#：{
  i = 999
  for i in [1, 2, 3] {
    # body
  }
  #：[i]
}'''
    out, _ = interpret(s)
    assert out[0] == 999, out  # 原始值恢复
    print("test_for_var_cleanup ✓")


# ============================================================
# 类型推断增强
# ============================================================

def test_type_tuple_expr():
    """TupleExpr 类型推断"""
    checker = EnhancedTypeInferencer()
    ast = parse("(1, \"hello\", true)")
    errors = checker.infer(ast)
    error_count = len([e for e in errors if "error" in e.lower() or "Error" in e])
    assert error_count == 0, errors
    print("test_type_tuple_expr ✓")


def test_type_slice_expr():
    """SliceExpr 类型推断"""
    checker = EnhancedTypeInferencer()
    ast = parse("lst[0:2]")
    errors = checker.infer(ast)
    error_count = len([e for e in errors if "error" in e.lower() or "Error" in e])
    assert error_count == 0, errors
    print("test_type_slice_expr ✓")


def test_type_belongs():
    """Belongs (∈) 类型推断返回 Bool"""
    checker = EnhancedTypeInferencer()
    ast = parse("x ∈ lst")
    errors = checker.infer(ast)
    error_count = len([e for e in errors if "error" in e.lower() or "Error" in e])
    assert error_count == 0, errors
    print("test_type_belongs ✓")


def test_type_typeof():
    """TypeOfExpr 类型推断返回 String"""
    checker = EnhancedTypeInferencer()
    ast = parse("typeof(42)")
    errors = checker.infer(ast)
    error_count = len([e for e in errors if "error" in e.lower() or "Error" in e])
    assert error_count == 0, errors
    print("test_type_typeof ✓")


def test_type_for_stmt():
    """ForStmt 类型推断"""
    checker = EnhancedTypeInferencer()
    ast = parse("for x in items { result = x }")
    errors = checker.infer(ast)
    error_count = len([e for e in errors if "error" in e.lower() or "Error" in e])
    assert error_count == 0, errors
    print("test_type_for_stmt ✓")


def test_type_if_else_stmt():
    """IfElseStmt 类型推断"""
    checker = EnhancedTypeInferencer()
    ast = parse("if x > 0 { result = 1 } 否则 { result = 2 }")
    errors = checker.infer(ast)
    error_count = len([e for e in errors if "error" in e.lower() or "Error" in e])
    assert error_count == 0, errors
    print("test_type_if_else_stmt ✓")


def test_type_switch_stmt():
    """SwitchStmt 类型推断"""
    checker = EnhancedTypeInferencer()
    ast = parse("switch x { case 1: result = 10 default: result = 0 }")
    errors = checker.infer(ast)
    error_count = len([e for e in errors if "error" in e.lower() or "Error" in e])
    assert error_count == 0, errors
    print("test_type_switch_stmt ✓")


# ============================================================
# in 运算符运行时测试
# ============================================================

def test_in_operator_list():
    out, _ = interpret('v = 2 in [1, 2, 3] ; #：[v]')
    assert out[0] == True, out
    out2, _ = interpret('v = 5 in [1, 2, 3] ; #：[v]')
    assert out2[0] == False, out2
    print("test_in_operator_list ✓")


def test_in_operator_string():
    out, _ = interpret('v = "a" in "abc" ; #：[v]')
    assert out[0] == True, out
    out2, _ = interpret('v = "x" in "abc" ; #：[v]')
    assert out2[0] == False, out2
    print("test_in_operator_string ✓")


def test_in_operator_dict():
    out, _ = interpret('v = "a" in {"a": 1, "b": 2} ; #：[v]')
    assert out[0] == True, out
    out2, _ = interpret('v = "x" in {"a": 1, "b": 2} ; #：[v]')
    assert out2[0] == False, out2
    print("test_in_operator_dict ✓")


def test_in_type_error():
    try:
        interpret('v = 1 in 42 ; #：[v]')
        assert False, "Should raise"
    except MathaRuntimeError as e:
        assert "序列/集合/字典" in str(e), str(e)
    print("test_in_type_error ✓")


# ============================================================
# Belongs (∈) 运行时测试
# ============================================================

def test_belongs_operator():
    out, _ = interpret('v = 2 ∈ [1, 2, 3] ; #：[v]')
    assert out[0] == True, out
    out2, _ = interpret('v = 5 ∈ [1, 2, 3] ; #：[v]')
    assert out2[0] == False, out2
    print("test_belongs_operator ✓")


# ============================================================
# 运行
# ============================================================

if __name__ == "__main__":
    # Rust 构造子模式
    test_match_constructor_tuple()
    test_match_constructor_nested()
    test_match_constructor_miss()
    test_match_constructor_bind_var()

    # Python for 解构
    test_for_tuple_destructure()
    test_for_dict_iteration()
    test_for_set_iteration()
    test_for_tuple_destructure_dict()
    test_for_var_cleanup()

    # 类型推断
    test_type_tuple_expr()
    test_type_slice_expr()
    test_type_belongs()
    test_type_typeof()
    test_type_for_stmt()
    test_type_if_else_stmt()
    test_type_switch_stmt()

    # in 运算符
    test_in_operator_list()
    test_in_operator_string()
    test_in_operator_dict()
    test_in_type_error()

    # Belongs 运算符
    test_belongs_operator()

    print("\n所有 Rust/Python 风格增强测试通过 ✓")
