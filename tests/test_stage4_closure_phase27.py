"""阶段 27b：stage-4 脱宿主闭环三锁（编译出的 VM 跑编译出的代码）。

自举链既有状态：stage-2≡stage-3 不动点（lexer/stdlib/parser/interp/
compiler_matha 五文件，test_mbc_bootstrap 锁定）。本文件把
matha/vm.matha（纯 Matha 实现的 M3V 字节码解释器）以「编译出的 VM」
身份纳入闭环，分三级锁定：

tier C（自举编译逐位一致 · joined 形态）：Matha 编译器编译
  stdlib+vm.matha 拼接源 ≡ 宿主编译产物（模块名/主码/常量池/函数表
  逐位一致）。既有 test_bootstrap_compiles_vm_matha_identically 锁的是
  vm.matha 单文件形态（产物含未解析 use 胶、不可独立运行）；joined
  形态才是脱宿主运行的真实产物。
tier A（编译出的 VM 实例化）：Matha 编译器编译出的 stdlib+vm.matha
  产物经宿主 VM 实例化为独立 VM（inner），执行 Matha 编译器编译的
  目标程序，与宿主 VM 基准逐条对拍。
tier B（全脱宿主 VM²）：目标程序（Matha 编译器产物 dict 以紧凑 JSON 串
  内嵌，driver 运行期经 stdlib parse_JSON 还原真字典——见下 ③）+
  vm.matha + stdlib 整体由 Matha 编译器编译为字节码，在 fixture 的
  Matha VM（运行M3V）内解释执行——目标程序跑在「Matha VM 之中的
  Matha VM」，与宿主基准和期望值双重对拍。

27b 附带脱宿主真化（本闭环的前置缺陷修复）：stdlib.matha/vm.matha
原有 5 处 `_to_float` 调用直接依赖宿主 VM 注入的内建（src/mbc/vm.py
`b.setdefault("_to_float", float)`）——VM² 第三层（被再解释的
vm.matha）解析不到该宿主专属名（探针取证：MathaRuntimeError 变量未
被定义: _to_float）。真化：Int→Float 叶子改 `× 1.0`（单次舍入，与
float(x) 逐位一致）、String 解析委托 stdlib 的 Matha 解析器、∞ 种子
改 ∞ 字面量。宿主侧 setdefault 保留（test_operator_dict_fixes 锁定
的宿主内建面）。

27b 探针定位并修复的两处产品缺陷（tier B 此前 0 输出/静默失败的根因）：
① 运行M3V 把 执行 返回的 __抛错__ 标记吞掉只返回 输出指针[1]——目标
  程序错误静默消失（探针取证：错误目标返回 [] 而非抛出），与宿主
  VM.call 抛错面（MathaRuntimeError）分歧。修复：__抛错__ →
  错误(消息) 真抛出（test_stage4a_error_face_propagates 锁定）。
② vm.matha 操作码常量函数 输出() 与内建名表的 "输出" 同名——joined
  自举形态下经 设全局 覆盖语义注册在 fixture 播种的 __内建__ marker
  之上，层-2 driver 的 输出(x) 被静默劫持为 0 元数常量函数（实参被
  丢、返回 96、无记录、无报错；探针取证：308s 真跑完探针计算却
  0 条输出）。修复：改名 输出码()（test_vm_matha_opcode_constants_
  do_not_shadow_special_builtins 锁定）。
③ tier B 初版以 Matha dict 字面量内嵌产物 dict——`{"函数": [["名", {...}]]}`
  形态（单元素表、无深度 1 逗号、前导 : 不在 18d `[` 派发中缀白名单）
  被误析为输出语句面（ast.Output → DUP+OUTPUT）：VM 面记录多余输出且
  字典值被破坏（宿主/VM 双面同源误析，tier C 字节一致不受影响；
  mini-repro：let d = {"函数": [["阶乘", {"元数": 1}]]} in 输出(d["函数"])
  → 宿主 [[['阶乘',{'元数':1}]]] / VM 同值多一条记录并破坏值面）。
  登记 KNOWN_ISSUES（27g 收官条目）；driver 改紧凑 JSON 串内嵌 +
  stdlib parse_JSON 运行期还原真字典（_json_matha_literal + driver 内
  对取/修函数/造目标），字符串对双编译器不透明、绕开 `[` 派发启发式。
④⑤⑥ tier B 探针逐层定位并修复的三处 vm.matha 模拟器缺陷（此前从未被
  执行路径踩中——VM² 面首次真跑 函数体内解包/let rec 盒绑定）：
④ 建盒 (MAKE_BOX) 创建 1 槽盒 [null]，而 读盒/写盒/读外部盒 均按下标
  1 取值（宿主 Box(None) 对象的镜像形态是 [占位, 值] 双槽）。任何
  emulated let rec（编译器经 占位符+盒 实现 rec 绑定）即触发
  （探针取证：IndexError lst[idx] = v）。修复：建盒 [null, null]。
⑤ 解包栈 (UNPACK_SEQ) 逆序压栈（顶=seq[0]）vs 宿主顺序压栈（顶=
  seq[n-1]，vm.py for i in range(n): append(seq[i])）——编译器逆序
  STORE 配对错位（探针取证：_json_skip_ws(s, pos='模块名') →
  TypeError '<' between str and int）。修复：解包栈(序列[1:], n-1,
  栈 + [解包项(序列, 0)])——首压 seq[0]、顶=seq[n-1] 与宿主一致。
⑥ 写局部/写盒 (STORE_LOCAL/STORE_BOX) 弹栈后未 换栈 写回帧——弹出值
  滞留操作数栈，连续两条 STORE 弹同一栈顶：函数体内 2 元组解包两个
  名字都绑 seq[1]（探针取证：_json_value("[1,2]", 0) → (5, 5)——值槽
  被位置覆盖；微复现 let (v, q) = 数值(i) in ... 双名同得第二元）。
  主码级解包走 写全局（有 换栈）不受累——故直线性语料全部侥幸对拍。
  修复：两 handler 补 换顶(帧栈步, 换栈(帧步, 栈1/栈2))，与 写全局
  同构。④⑤⑥ 由 test_stage4b_embedded_vm_squared_full_dehosted
  （stdlib parse_JSON 全链含 函数体内解包 + let rec 盒绑定经 VM²）
  锁定；⑦ 处理 全 handler 换栈审计：除 ④⑤⑥ 外其余 handler
  （调用/返回/跳转/二元/一元/建列表/建字典/取下标/切片/取属性/解包/
  复制/弹栈/输出码）均正确换栈，无同类缺陷。

边界（层-3 内建可达面）：内建名表内的名字逐层走 __内建__ 标记分派
（每层 应用内建 → 内建一元/二元/三元 的裸调用落到最外层宿主 Python
面 _GlobalScope 的 C 内建），宿主专属内建（floor/sin 等）层-3 实测
可达（tier B 目标三 floor(3.7) → [3]）。真正不可达的是不在内建名表
的宿主专属名（_to_float 等）——已由本阶段脱宿主真化消除。
"""

import json

import pytest

from src.parser import parse as py_parse
from src.mbc.compiler import Compiler, MFunction, MModule
from src.mbc.vm import VM
from src import ast_nodes as ast


def _read_source(rel):
    with open(rel, encoding="utf-8") as f:
        return f.read()


def _compile_files(rels, extra_src=""):
    comp = Compiler()
    decls = []
    for rel in rels:
        decls.extend(py_parse(_read_source(rel)).decls)
    if extra_src:
        decls.extend(py_parse(extra_src).decls)
    comp.compile_program(ast.Program(decls=decls))
    return comp


def dict_to_module(d):
    """自举编译器产物 dict → 宿主 MModule（指令 list 转 tuple，结构等价）。"""
    mod = MModule(module_name=d.get("模块名", "主程序"))
    mod.constants = list(d["常量"])
    mod.main_code = [tuple(x) for x in d["主码"]]
    for entry in d["函数"]:
        name, info = entry[0], entry[1]
        mod.functions[name] = MFunction(
            name, info["元数"], info["局部数"],
            [tuple(x) for x in info["码"]], list(info["参数"]))
    return mod


def module_to_dict(mod):
    """宿主 MModule → 自举编译器同构 dict（逐位比对基准）。"""
    d = {"模块名": mod.module_name, "常量": list(mod.constants),
         "主码": [list(x) for x in mod.main_code], "函数": []}
    for name, fn in mod.functions.items():
        info = {"元数": fn.arity, "局部数": fn.nlocals,
                "码": [list(x) for x in fn.code], "参数": list(fn.params)}
        d["函数"].append([name, info])
    return d


_COMPILER_BOOT_FILES = ["matha/lexer.matha", "matha/stdlib.matha",
                        "matha/parser.matha", "matha/interp.matha",
                        "matha/compiler_matha.matha"]
_JOINED_VM_FILES = ["matha/stdlib.matha", "matha/vm.matha"]


@pytest.fixture(scope="module")
def vm_boot_vm():
    """自举链 + Matha 实现的 M3V 虚拟机（宿主编译产物实例）。"""
    comp = _compile_files(_COMPILER_BOOT_FILES + ["matha/vm.matha"])
    vm = VM(comp.mod)
    vm.run()
    return vm


@pytest.fixture(scope="module")
def stage4(vm_boot_vm):
    """（tier C/A 公共）Matha 编译器编译 stdlib+vm.matha 拼接源 ≈43s，
    同时产出宿主编译同源逐位比对基线。"""
    joined = "\n".join(_read_source(p) for p in _JOINED_VM_FILES)
    matha_dict = vm_boot_vm.call("编译", joined)
    assert isinstance(matha_dict, dict)
    host_dict = module_to_dict(_compile_files(_JOINED_VM_FILES).mod)
    return matha_dict, host_dict


@pytest.fixture(scope="module")
def stage4_inner(stage4):
    """tier A：Matha 编译器编译出的 stdlib+vm.matha 产物实例化的独立 VM。"""
    matha_dict, _ = stage4
    vm = VM(dict_to_module(matha_dict))
    vm.run()
    return vm


def test_stage4c_joined_compile_identical(stage4):
    """tier C：Matha 编译器编译 stdlib+vm.matha 拼接源 ≡ 宿主编译产物
    （模块名/主码/常量池/函数表逐位一致）——可运行形态的自举闭环。"""
    matha_dict, host_dict = stage4
    assert matha_dict["模块名"] == host_dict["模块名"]
    assert matha_dict["主码"] == host_dict["主码"]
    assert matha_dict["常量"] == host_dict["常量"]
    assert matha_dict["函数"] == host_dict["函数"]


_STAGE4A_CASES = [
    "输出(1 + 2 * 3)\n",
    "func 阶乘(n: Int) -> Int =\n  n <= 1 ? 1 : n * 阶乘(n - 1)\n输出(阶乘(6))\n",
    "let d = {\"a\": 1, \"b\": 2} in 输出(d[\"a\"] + d[\"b\"])\n",
    "let 加 = (y) => (x) => x + y in\n输出(加(3)(4))\n",
    "func 提错() -> Int =\n  错误(\"boom\")\n输出(调用捕获(提错)([]))\n",
]


@pytest.mark.parametrize("src", _STAGE4A_CASES, ids=lambda s: s[:36].replace("\n", "\\n"))
def test_stage4a_compiled_vm_runs_programs(vm_boot_vm, stage4_inner, src):
    """tier A：Matha 编译器编译出的 VM（stdlib+vm 产物实例化）执行
    Matha 编译器编译的目标程序，与宿主 VM 基准逐条一致。"""
    d = vm_boot_vm.call("编译", src)
    host = VM(dict_to_module(d))
    host.run()
    assert stage4_inner.call("运行M3V", d) == host.outputs


def test_stage4a_error_face_propagates(vm_boot_vm, stage4_inner):
    """27b 缺陷修复锁①：运行M3V 原把 __抛错__ 吞为部分输出（探针取证：
    错误目标静默返回 []），与宿主 VM.call 抛错面分歧。修复后对齐：
    目标程序错误经 错误(消息) 真抛出，不再静默吞掉。双面异常类按
    实际形态锁定：宿主面 CALL 形态 错误 走 _raise_builtin → 原生
    RuntimeError；编译 VM 面 vm.matha 的传播行经宿主编译为 OP.RAISE
    → MathaRuntimeError（RuntimeError 子类）。二者同为 RuntimeError
    家族、消息一致，此处按父类匹配（MathaRuntimeError 一并被覆盖）。"""
    d = vm_boot_vm.call("编译", '错误("boom")\n')
    host = VM(dict_to_module(d))
    with pytest.raises(RuntimeError, match="boom"):
        host.run()
    with pytest.raises(RuntimeError, match="boom"):
        stage4_inner.call("运行M3V", d)


def _collect_func_names(decls, out):
    for d in decls:
        if isinstance(d, ast.FuncDef):
            out.add(d.name)
        inner = getattr(d, "decls", None)
        if inner:
            _collect_func_names(inner, out)


def test_vm_matha_opcode_constants_do_not_shadow_special_builtins():
    """27b 缺陷修复锁②：joined 自举形态下 vm.matha 函数表经 设全局
    覆盖语义注册在 fixture 播种的 __内建__ marker 之上；若操作码常量
    函数与 应用内建 特殊分派名同名，层-2 代码的对应调用被静默劫持
    （探针取证：输出(x) 调到 输出()→96，实参被丢、无记录、无报错，
    308s 真跑完探针计算却 0 条输出）。锁：vm.matha 不得定义特殊分派
    名；输出操作码常量函数名为 输出码。"""
    names = set()
    _collect_func_names(py_parse(_read_source("matha/vm.matha")).decls, names)
    assert "输出码" in names
    special = {"输出", "print", "打印文本", "调用捕获", "错误", "MathaIOError"}
    assert names.isdisjoint(special)


def _json_matha_literal(t):
    """编译产物 dict → 紧凑 JSON 串的 Matha 字符串字面量。

    不用 Matha dict 字面量内嵌（见 docstring ③）：`{"函数": [[...]]}` 形态
    被双编译器同源误析。JSON 串对双编译器都是不透明字符串，driver 运行期
    经 stdlib parse_JSON（stdlib.matha:604；模块函数平铺注册，joined 形态
    层-2 可达）还原真字典。紧凑分隔符：stdlib JSON 解析器在 ":" 后不跳
    空白（_json_value(s, pos2+1)，stdlib.matha:581），逗号后空白有跳、
    冒号后没有。Matha 字面量转义与 Matha 词法器 \\ \\" 支持面一致。
    """
    s = json.dumps(t, ensure_ascii=False, separators=(",", ":"))
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


_TIERB_DRIVER_HELPERS = (
    "func 对取(们: List, 键: String) -> Value =\n"
    "  if 们[0][0] = 键 then 们[0][1]\n"
    "  else 对取(们[1:], 键)\n"
    "\n"
    "func 修函数(们: List) -> List =\n"
    "  if 们 = [] then []\n"
    "  else\n"
    "    let 条目对 = 们[0] in\n"
    "    let 信息对 = 条目对[1] in\n"
    "    let 信息 = {\"元数\": 对取(信息对, \"元数\"), \"局部数\": 对取(信息对, \"局部数\"), \"码\": 对取(信息对, \"码\"), \"参数\": 对取(信息对, \"参数\")} in\n"
    "    let 条目 = [条目对[0], 信息] in\n"
    "    append(修函数(们[1:]), 条目)\n"
    "\n"
    "func 造目标(对: List) -> Value =\n"
    "  {\"模块名\": 对取(对, \"模块名\"), \"常量\": 对取(对, \"常量\"), \"主码\": 对取(对, \"主码\"), \"函数\": 修函数(对取(对, \"函数\"))}\n"
)


def test_stage4b_embedded_vm_squared_full_dehosted(vm_boot_vm):
    """tier B：全脱宿主 VM²——三个目标程序（Matha 编译器产物 dict）以
    紧凑 JSON 串内嵌进驱动，driver 运行期经 stdlib parse_JSON 还原真
    字典（对取/修函数/造目标）；驱动 + vm.matha + stdlib 整体由 Matha
    编译器编译为字节码，在 fixture 的 Matha VM（运行M3V）内解释执行：
    目标程序跑在「Matha VM 之中的 Matha VM」。目标三覆盖宿主专属内建
    （floor），证明 __内建__ 标记链逐层分派落到最外层宿主面。四重对拍：
    VM² 输出 = 宿主执行同链基准 = 各目标产物直接跑宿主 VM 的期望值。"""
    t1 = vm_boot_vm.call("编译", "输出(1 + 2 * 3)\n")
    t2 = vm_boot_vm.call(
        "编译", "func 阶乘(n: Int) -> Int = n <= 1 ? 1 : n * 阶乘(n - 1)\n输出(阶乘(6))\n")
    t3 = vm_boot_vm.call("编译", "输出(floor(3.7))\n")
    driver = (
        _TIERB_DRIVER_HELPERS
        + f"let 目标一 = 造目标(parse_JSON({_json_matha_literal(t1)})) in\n"
        + f"let 目标二 = 造目标(parse_JSON({_json_matha_literal(t2)})) in\n"
        + f"let 目标三 = 造目标(parse_JSON({_json_matha_literal(t3)})) in\n"
        + "let outs1 = 运行M3V(目标一) in\n"
        + "let outs2 = 运行M3V(目标二) in\n"
        + "let outs3 = 运行M3V(目标三) in\n"
        + "输出(outs1)\n输出(outs2)\n输出(outs3)\n")
    joined = (_read_source("matha/stdlib.matha") + "\n"
              + _read_source("matha/vm.matha") + "\n" + driver)

    d2 = vm_boot_vm.call("编译", joined)
    assert isinstance(d2, dict)
    outer = vm_boot_vm.call("运行M3V", d2)

    host_chain = VM(_compile_files(_JOINED_VM_FILES, driver).mod)
    host_chain.run()

    h1 = VM(dict_to_module(t1))
    h1.run()
    h2 = VM(dict_to_module(t2))
    h2.run()
    h3 = VM(dict_to_module(t3))
    h3.run()

    assert outer == host_chain.outputs == [h1.outputs, h2.outputs, h3.outputs]
    assert outer == [[7], [720], [3]]
