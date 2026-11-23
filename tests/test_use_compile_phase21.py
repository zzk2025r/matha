# -*- coding: utf-8 -*-
"""阶段 21b 三锁：编译面 use 解析（自举链收口）。

拍板面：编译器 use 发射 CALL 加载模块（宿主注入的插件层胶水把被 use
模块函数/枚举/模块级 let 平铺合并进同一个运行中 VM + 命名空间绑定）；
被 use 模块已内联在同一程序（自举链多文件合并编译）时不发射（符号就在
本模块全局域，加载调用多余且会二次合并）。GET_ATTR 补宿主 PathExpr
「dict 缺失成员退回内建表」同构回退（标准库.len 一类内建透传）。

- 对拍：官方门面（exec_api）与宿主面在 use 解析后收敛
- 闭环：加载模块 胶水真加载/幂等/命名空间/枚举/let 物化；发射与内联抑制
- 防回潮：stdlib 死导入清除 + 双端内联守卫在场
- 登记边界：裸 VM 无加载全局诚实报错；三链文件双面形态（39c/39d 后两文件
  双面 ok、bootstrap_test 双端同判 err——加载模块 形状与三引号字符串残留）
"""

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.interp import Interpreter
from src.kernel import exec_api
from src.mbc.compiler import compile_program
from src.mbc.vm import VM, Closure
from src.parser import parse

_BOOT = ROOT / "matha"


def _norm(v):
    fields = getattr(v, "__dict__", None)
    if fields is not None:
        return {"__type__": type(v).__name__,
                **{k: repr(x) for k, x in fields.items()}}
    return v


def _host_src(source: str):
    it = Interpreter()
    it.run(parse(source))
    return [repr(_norm(x)) for x in it.outputs]


def _vm_src(source: str):
    outs, err = exec_api.run_checked(source)
    if err is not None:
        raise err
    return [repr(_norm(x)) for x in outs]


def _faces(path: pathlib.Path):
    """(宿主面, 官方门面 VM 面) 输出或错误摘要。"""
    try:
        h = ("ok", _host_src(path.read_text(encoding="utf-8")))
    except Exception as e:  # noqa: BLE001
        h = ("err", f"{type(e).__name__}: {e}")
    outs, err = exec_api.run_file_checked(path)
    if err is not None:
        v = ("err", f"{type(err).__name__}: {err}")
    else:
        v = ("ok", [repr(_norm(x)) for x in outs])
    return h, v


# ============================================================
# 对拍：官方门面 ↔ 宿主面
# ============================================================

@pytest.mark.parametrize("rel", [
    "matha/bootstrap_test_v2.matha",
    "matha/interp.matha",
    "matha/interp_matha.matha",
])
def test_use_chain_file_faces_converge(rel):
    h, v = _faces(ROOT / rel)
    assert h == v, f"{rel} 双面分歧:\n  host={h}\n  vm  ={v}"


def test_use_ns_dot_call_both_faces():
    """模块.函数 点号调用 + 内建透传（标准库.len 经 GET_ATTR 回退）双面同值。"""
    src = ("use 标准库\n"
           "#1：[标准库.list_concat([1, 2], [3])]\n"
           "#2：[标准库.len([5, 6, 7])]\n")
    assert _host_src(src) == _vm_src(src) == ["[1, 2, 3]", "3"]


def test_use_member_bind_and_module_let_both_faces():
    """use 成员绑定（list_concat）+ 被载模块级 let（PI）双面同值。"""
    src = ("use 标准库 { list_concat }\n"
           "use 运行时引擎\n"
           "#1：[list_concat([9], [8])]\n"
           "#2：[运行时引擎.PI > 3.14]\n"
           "#3：[运行时引擎.PI < 3.15]\n")
    assert _host_src(src) == _vm_src(src) == ["[9, 8]", "True", "True"]


# ============================================================
# 闭环：加载模块 胶水 + 编译器发射
# ============================================================

def test_loader_real_load_and_idempotent():
    """加载模块 真加载：函数/枚举/let/命名空间落 globals；重复加载幂等。"""
    from src.domains.capability import make_module_loader
    mod = compile_program(parse("let 甲 = 1\n"))
    vm = VM(mod)
    loader = make_module_loader(vm)
    vm.globals.setdefault("加载模块", loader)
    merged1 = loader("标准库")
    assert "list_concat" in merged1
    ns = vm.globals["标准库"]
    assert isinstance(ns["list_concat"], Closure)
    assert vm.globals["list_concat"] is ns["list_concat"]
    assert loader("标准库") == []
    # 中文模块名与实际模块名都登记（幂等集双名）
    assert loader("运行时引擎") != []
    assert vm.globals["运行时引擎"]["PI"] == pytest.approx(3.141592653589793)


def test_loader_registers_enum_members():
    """词法器 的枚举：成员注册为全局字符串、枚举名注册为成员 dict。"""
    from src.domains.capability import make_module_loader
    vm = VM(compile_program(parse("let 甲 = 1\n")))
    make_module_loader(vm)("词法器")
    assert vm.globals["整数"] == "整数"
    ty = vm.globals["类型"]
    assert isinstance(ty, dict) and ty["整数"] == "整数"
    assert isinstance(vm.globals["扫描"], Closure)


def test_import_emits_loader_call_when_not_inline():
    """use 目标未内联：主码发射 LOAD_GLOBAL 加载模块 + PUSH_CONST 模块名 + CALL 1。"""
    from src.mbc.vm import OP
    prog = parse("use 标准库 { list_concat }\nlet 甲 = 1\n")
    mod = compile_program(prog)
    consts = mod.constants
    gidx, midx = consts.index("加载模块"), consts.index("标准库")
    seq = [(OP.LOAD_GLOBAL, gidx), (OP.PUSH_CONST, midx), (OP.CALL, 1)]
    main = mod.main_code
    assert any(list(main[i:i + 3]) == seq for i in range(len(main) - 2)), \
        "use 未发射 CALL 加载模块（主码无 LOAD_GLOBAL/PUSH_CONST/CALL 序列）"


def test_inline_module_import_suppressed():
    """use 目标已内联（同程序含同名 module 声明）：不发射加载调用。"""
    src = ("module 标准库 {\n"
           "  func 加一(x: Int) -> Int = x + 1\n"
           "}\n"
           "module 主 {\n"
           "  use 标准库 { 加一 }\n"
           "  func 起始() -> Int = 加一(1)\n"
           "}\n")
    mod = compile_program(parse(src))
    assert "加载模块" not in mod.constants


def test_bare_vm_rejects_use_honestly():
    """裸 VM（无插件层注入）遇 use：未定义名诚实报错（登记边界）。"""
    from src.kernel.errors import MathaUndefinedNameError
    mod = compile_program(parse("use 标准库 { list_concat }\nlet 甲 = 1\n"))
    vm = VM(mod)
    with pytest.raises(MathaUndefinedNameError, match="加载模块"):
        vm.run()


def test_getattr_fallback_matches_host_pathexpr():
    """VM GET_ATTR dict 缺失成员：内建名回退内建表、非内建名 None——
    与宿主 PathExpr「模块属性 fallback」同构（字节码直驱）。"""
    from src.mbc.compiler import MModule
    from src.mbc.vm import OP
    m = MModule(module_name="探针")
    m.constants = ["len", "不存在名", [7, 8]]
    m.main_code = [
        (OP.BUILD_DICT, 0),          # 空字典（模块 ns 形态）
        (OP.GET_ATTR, 0),            # 缺失成员 len → 回退内建表
        (OP.PUSH_CONST, 2),          # 实参 [7, 8]
        (OP.CALL, 1),                # len([7, 8]) → 2
        (OP.HALT,),
    ]
    vm = VM(m)
    vm.run()
    assert vm.main_frame.stack[-1] == 2
    # 非内建名：缺失成员 → None（不回退）
    m2 = MModule(module_name="探针2")
    m2.constants = ["不存在名"]
    m2.main_code = [
        (OP.BUILD_DICT, 0),
        (OP.GET_ATTR, 0),
        (OP.HALT,),
    ]
    vm2 = VM(m2)
    vm2.run()
    assert vm2.main_frame.stack[-1] is None
    assert "len" in vm.builtin_names
    assert "不存在名" not in vm2.builtin_names


# ============================================================
# 防回潮
# ============================================================

def test_stdlib_dead_import_removed():
    """stdlib.matha 的死导入（use 运行时引擎，零引用）已清除。"""
    text = (_BOOT / "stdlib.matha").read_text(encoding="utf-8")
    assert "use 运行时引擎" not in text


def test_mirror_inline_guard_present():
    """镜像编译器内联守卫三件在场（_收集模块名/_名单含/_清内联导入）。"""
    text = (_BOOT / "compiler_matha.matha").read_text(encoding="utf-8")
    for name in ("_收集模块名", "_名单含", "_清内联导入"):
        assert f"func {name}" in text


def test_host_compiler_inline_guard_present():
    """宿主编译器 _inline_modules 预扫在场。"""
    text = (ROOT / "src" / "mbc" / "compiler.py").read_text(encoding="utf-8")
    assert "_inline_modules" in text


# ============================================================
# 登记边界：链文件双面形态（39 收官后两文件转 ok，bootstrap_test 仍双端同判 err）
# HEAD 9803068 基线：六链文件 VM 面全部 未定义变量（use 符号无绑定）——
# 21b 真化消除该屏障后 VM 面走深；39c/39d 进一步把 bootstrap_matha 语料刷新到
# 现行柯里化 API、compiler_matha 的 不折叠 模块级 let 前移（宿主闭包按定义序
# 快照环境），两文件 host 面旧错误退役为 ok。bootstrap_test 残留三引号字符串
# 根因双端同判（both_err_equal 边界，见 phase39 锁）。
# ============================================================

def test_boundary_bootstrap_full_test():
    """39d 后双面全跑通：host 面旧首错名 '不折叠' 退役（模块级 let 前移），
    与 VM 面 22 输出逐字同判。"""
    h, v = _faces(ROOT / "matha/bootstrap_full_test.matha")
    assert h == v, f"host={h}\n  vm={v}"
    assert h[0] == "ok" and len(h[1]) == 22, (len(h[1]), h[1][:3])


def test_boundary_bootstrap_matha():
    """39c 语料刷新后双面 ok：旧 host 面 属性访问失败 str.类型 与 VM 面
    TypeError len(Partial) 均退役；前 3 输出同判，第 4 项为 加载模块 胶水
    返回形状（hi bool vs VM 面 list[str]，登记边界）。"""
    h, v = _faces(ROOT / "matha/bootstrap_matha.matha")
    assert h[0] == "ok" and v[0] == "ok", (h[1], v[1])
    assert len(h[1]) == len(v[1]) == 4, (h[1], v[1])
    assert h[1][:3] == v[1][:3], (h[1], v[1])


def test_boundary_bootstrap_test():
    """host 面 不可调用的值（HEAD 同形不变）；
    VM 面 HEAD err 未定义变量 '词法器' → 21b 后 KeyError: 0 → 29b-④ 缺键返
    null（vm→host 对齐，应用函数 f[0] 探测字典键落到 错误 分支）后与 host
    同文案，双端消息逐字一致。"""
    h, v = _faces(ROOT / "matha/bootstrap_test.matha")
    assert h[0] == "err" and "不可调用的值" in h[1]
    assert v[0] == "err" and "不可调用的值" in v[1]
    assert h[1] == v[1]
