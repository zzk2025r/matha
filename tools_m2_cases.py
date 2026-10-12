import sys
sys.path.insert(0, ".")
import tools_m2_probe as P

CASES = [
    ("const", "x = 42"),
    ("arith", "y = 1 + 2 * 3"),
    ("unary", "y = -5"),
    ("if_expr", "y = if 1 < 2 then 10 else 20"),
    ("let", "z = let a = 2 in a + 3"),
    ("for", "t = 0\nfor i in [1, 2, 3] {\n  t = t + i\n}\n"),
    ("enum", "enum E { A B }\nx = E.A"),
    ("struct", "struct P { x: Int }\np = P\np.x = 7"),
    ("module", "module M {\n  func g(a: Int) -> Int = (a) => a + 1\n}\ny = M.g(4)"),
    ("use", "use stdlib"),
    ("tuple_ret", "func two() -> (Int, Int) = () => (1, 2)\nlet (a, b) = two()\ny = a + b"),
    ("nested_call", "func h(a: Int) -> Int = (a) => a * 2\ny = h(h(3))"),
    ("two_arg", "func g(a: Int, b: Int) -> Int = (a, b) => a + b\ny = g(10, 3)"),
    ("zero_arg", "func z() -> Int = () => 5\ny = z()"),
    ("lambda", "f = (a) => a + 1\ny = f(1)"),
    ("recursion",
     "func fact(n: Int) -> Int = (n) => if n <= 1 then 1 else n * fact(n - 1)\ny = fact(5)"),
    ("partial",
     "func add3(a: Int, b: Int, c: Int) -> Int = (a, b, c) => a + b + c\ng = add3(1)\ny = g(2)(3)"),
    ("list", "xs = [1, 2, 3]"),
    ("index", "y = [1, 2, 3][0]"),
    ("slice", "y = [1, 2, 3][0:1]"),
    ("dict", "d = {\"a\": 1, \"b\": 2}"),
    ("null", "x = [0, [], null, true]"),
    ("try_stmt", "try {\n  x = 1\n} catch (e) {\n  x = 2\n}\ny = x"),
    ("match", "func f(x: Int) -> Int = (x) =>\n  match x {\n    | 1 => 10\n    | _ => 20\n  }\ny = f(1)"),
    ("out_seg", "#1：[42]"),
    ("out_block", "#：{\n  x = 1 + 2\n  [x]\n}\ny = x"),
    ("out_stmt", "[x]"),
    ("out_empty", "[]"),
    ("out_list", "[1, 2, 3]"),
    ("bind_list", "y = [1, 2]"),
    ("string_escape", "s = \"a\\nb\""),
]

if __name__ == "__main__":
    vm = P.build_stage1()
    ok = 0
    for name, src in CASES:
        try:
            h = P.canon(P.host_compile(src))
        except Exception as e:
            print("HOST-ERR", name, type(e).__name__, str(e)[:70])
            continue
        try:
            s = P.canon(P.self_dict_to_module(vm.call("编译", src)))
        except Exception as e:
            print("SELF-ERR", name, type(e).__name__, str(e)[:70])
            continue
        d = P.first_diff(h, s)
        if d is None:
            ok += 1
        else:
            print("DIFF", name, d)
    print("matched", ok, "/", len(CASES))
