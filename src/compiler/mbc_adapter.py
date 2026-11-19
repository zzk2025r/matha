"""MBC 字节码适配器 — 编译器框架接入 MBC 主线的桥（29e）。

背景：编译器框架（src/compiler，26b 起）与 MBC 主线一直互不接触（框架级实现
未接入 MBC 主线，KNOWN_ISSUES 登记）。本模块是显式桥：

  1. 两条 MBC 字节码遍（Pass 子类，经 PassManager 框架调度）：
     - 字节码常量折叠：PUSH_CONST/PUSH_CONST/BINOP 与 PUSH_CONST/UNARYOP 调用
       VM 同一 _BINOPS/_UNARYOPS 实现求值——结果与运行期逐位一致（除零等报错
       不折叠，诚实保留运行期路径）；仅折叠不可变结果（int/float/bool/str），
       列表/字典折叠会共享池内可变对象，跳过。
     - 字节码死代码消除：按 JMP/JZ/JNZ/RET/RAISE/RAISE_MATCH/HALT 语义做
       可达性 BFS，删除不可达指令并重映射跳转目标。
  2. 反向注册接入：内核 exec_api 不得 import src.compiler（dep_audit 棘轮
     遗留面），接入方向反转——本模块被显式 import 时经 exec_api.set_compile_
     hook 反向注册编译后钩子；内核面默认无钩子。
  3. 双保险 opt-in 默认关：未 import 本模块 = 关（内核无钩子）；import 而开关
     features.MBC_PASSES 关 = 关（钩子自查直接返回原模块）。开启需同时
     import 本模块 + set_feature("MBC_PASSES", True)（或环境变量
     MATHA_FEATURE_MBC_PASSES=1）。

mbc 零改动：本模块只读 opcodes/_BINOPS/_UNARYOPS，不改 src/mbc/*。
跨模块函数纪律：MFunction.consts 非空时指向来源模块常量池，折叠产生的
新常量追加到该函数实际引用的池（与 VM 池分派同规则）。
"""
from __future__ import annotations

from typing import Any, Iterator

from src.compiler.pass_manager import Pass, PassManager
from src.mbc import opcodes as OP

#: 仅折叠这些类型的运算结果——池内共享对象必须不可变（bool 是 int 子类）。
_FOLDABLE_RESULTS = (int, float, str)

_JUMP_OPS = (OP.JMP, OP.JZ, OP.JNZ)
_TERMINAL_OPS = (OP.RET, OP.RAISE, OP.RAISE_MATCH, OP.HALT)


# ============================================================
# 指令流工具
# ============================================================

def _jump_targets(code: list) -> set[int]:
    targets: set[int] = set()
    for ins in code:
        if ins and ins[0] in _JUMP_OPS and isinstance(ins[1], int):
            targets.add(ins[1])
    return targets


def _iter_code(mod) -> Iterator[tuple[Any, str, list]]:
    """产出 (持有者, 属性名, 常量池)。主码 + 全部函数（含嵌套 lambda 表）。"""
    yield mod, "main_code", mod.constants
    seen: set[int] = set()
    stack = list(mod.functions.values())
    while stack:
        fn = stack.pop()
        if id(fn) in seen:
            continue
        seen.add(id(fn))
        pool = fn.consts if fn.consts is not None else mod.constants
        yield fn, "code", pool
        stack.extend((fn.functions or {}).values())


def _pool_intern(pool: list, value: Any) -> int:
    """类型严格去重（True 与 1 同池时不得互并——== 语义会混并布尔与整数）。"""
    for j, v in enumerate(pool):
        if type(v) is type(value) and v == value:
            return j
    pool.append(value)
    return len(pool) - 1


# ============================================================
# 遍一：常量折叠
# ============================================================

def _try_fold_unary(code: list, i: int, pool: list, targets: set[int], unary_ops: dict):
    if i + 1 >= len(code):
        return None
    if code[i][0] != OP.PUSH_CONST or code[i + 1][0] != OP.UNARYOP:
        return None
    if i + 1 in targets:
        return None
    ia, iop = code[i][1], code[i + 1][1]
    if not (isinstance(ia, int) and isinstance(iop, int)
            and 0 <= ia < len(pool) and 0 <= iop < len(pool)):
        return None
    a = pool[ia]
    op = pool[iop]
    fn = unary_ops.get(op) if isinstance(op, str) else None
    if fn is None:
        return None
    try:
        r = fn(a)
    except BaseException:  # noqa: BLE001——sqrt(-1) 等报错诚实保留运行期
        return None
    if not isinstance(r, _FOLDABLE_RESULTS):
        return None
    return (OP.PUSH_CONST, _pool_intern(pool, r))


def _try_fold_binary(code: list, i: int, pool: list, targets: set[int], bin_ops: dict):
    if i + 2 >= len(code):
        return None
    if (code[i][0] != OP.PUSH_CONST or code[i + 1][0] != OP.PUSH_CONST
            or code[i + 2][0] != OP.BINOP):
        return None
    if i + 1 in targets or i + 2 in targets:
        return None
    ia, ib, iop = code[i][1], code[i + 1][1], code[i + 2][1]
    if not (isinstance(ia, int) and isinstance(ib, int) and isinstance(iop, int)
            and 0 <= ia < len(pool) and 0 <= ib < len(pool) and 0 <= iop < len(pool)):
        return None
    a, b = pool[ia], pool[ib]
    op = pool[iop]
    fn = bin_ops.get(op) if isinstance(op, str) else None
    if fn is None:
        return None
    try:
        r = fn(a, b)
    except BaseException:  # noqa: BLE001——除零等报错诚实保留运行期
        return None
    if not isinstance(r, _FOLDABLE_RESULTS):
        return None
    return (OP.PUSH_CONST, _pool_intern(pool, r))


def _fold_code_list(code: list, pool: list, bin_ops: dict, unary_ops: dict
                    ) -> tuple[list, int]:
    """对一条指令流折叠到定点；返回 (新指令流, 折叠次数)。不改入参。"""
    total = 0
    work = list(code)
    while True:
        targets = _jump_targets(work)
        keep: list[tuple[int, int, Any]] = []
        folded = 0
        i = 0
        n = len(work)
        while i < n:
            repl = _try_fold_binary(work, i, pool, targets, bin_ops)
            if repl is not None:
                keep.append((i, i + 3, repl))
                folded += 1
                i += 3
                continue
            repl = _try_fold_unary(work, i, pool, targets, unary_ops)
            if repl is not None:
                keep.append((i, i + 2, repl))
                folded += 1
                i += 2
                continue
            keep.append((i, i + 1, None))
            i += 1
        if folded == 0:
            break
        new_code: list = []
        map_old: dict[int, int] = {}
        for start, end, repl in keep:
            new_idx = len(new_code)
            new_code.append(repl if repl is not None else work[start])
            for old in range(start, end):
                map_old[old] = new_idx
        remapped = []
        for ins in new_code:
            if ins[0] in _JUMP_OPS:
                ins = (ins[0], map_old[ins[1]])
            remapped.append(ins)
        work = remapped
        total += folded
    return work, total


# ============================================================
# 遍二：死代码消除
# ============================================================

def _reachable(code: list) -> set[int]:
    reach: set[int] = set()
    if not code:
        return reach
    stack = [0]
    while stack:
        i = stack.pop()
        if i in reach or not (0 <= i < len(code)):
            continue
        reach.add(i)
        ins = code[i]
        op = ins[0] if ins else None
        if op == OP.JMP:
            stack.append(ins[1])
        elif op in (OP.JZ, OP.JNZ):
            stack.append(i + 1)
            stack.append(ins[1])
        elif op in _TERMINAL_OPS:
            pass
        else:
            stack.append(i + 1)
    return reach


def _dead_code_list(code: list) -> tuple[list, int]:
    """删除不可达指令并重映射跳转目标；返回 (新指令流, 删除条数)。"""
    reach = _reachable(code)
    if len(reach) == len(code):
        return list(code), 0
    new_code: list = []
    map_old: dict[int, int] = {}
    for old, ins in enumerate(code):
        if old in reach:
            map_old[old] = len(new_code)
            new_code.append(ins)
    remapped = []
    for ins in new_code:
        if ins[0] in _JUMP_OPS:
            # 可达跳转的目标必可达（BFS 已入栈），映射必在
            ins = (ins[0], map_old[ins[1]])
        remapped.append(ins)
    return remapped, len(code) - len(reach)


# ============================================================
# Pass 子类（框架 PassManager 调度）
# ============================================================

class BytecodeConstFold(Pass):
    """MBC 字节码常量折叠遍（29e）。

    折叠语义与 VM 逐位一致：调用同一 _BINOPS/_UNARYOPS 实现；除零/sqrt(-1)
    等报错不折叠（诚实保留运行期路径）；可变结果（列表/字典）不折叠
    （池内共享可变对象会跨 VM 泄漏）。折叠到定点（a+b+c 型链逐轮收缩）。
    """

    def __init__(self) -> None:
        super().__init__(name="字节码常量折叠")
        from src.mbc.vm import _BINOPS, _UNARYOPS
        self._bin_ops = _BINOPS
        self._unary_ops = _UNARYOPS

    def run(self, program: Any) -> Any:
        total = 0
        for holder, attr, pool in _iter_code(program):
            new_code, n = _fold_code_list(getattr(holder, attr), pool,
                                          self._bin_ops, self._unary_ops)
            if n:
                setattr(holder, attr, new_code)
            total += n
        self.increment_stat("折叠次数", total)
        return program


class BytecodeDeadCode(Pass):
    """MBC 字节码死代码消除遍（29e）。

    按 JMP/JZ/JNZ/RET/RAISE/RAISE_MATCH/HALT 语义做可达性 BFS，删除不可达
    指令并重映射全部跳转目标；全可达 = 原样返回（零拷贝语义保持）。
    """

    def __init__(self) -> None:
        super().__init__(name="字节码死代码消除")

    def run(self, program: Any) -> Any:
        total = 0
        for holder, attr, _pool in _iter_code(program):
            new_code, n = _dead_code_list(getattr(holder, attr))
            if n:
                setattr(holder, attr, new_code)
            total += n
        self.increment_stat("删除指令数", total)
        return program


def make_mbc_pass_manager() -> PassManager:
    """构造独立的 MBC 字节码遍管理器（两遍注册并启用，无依赖注册序）。

    独立于全局 get_pass_manager()：全局管理器混装框架泛 IR 遍（26b）与
    MBC 字节码遍两种方言，混跑同一 program 会误读对象形状——字节码遍只经
    本管理器运行。
    """
    pm = PassManager()
    pm.register_pass(BytecodeConstFold())
    pm.register_pass(BytecodeDeadCode())
    pm.auto_order_passes()
    pm.enable_pass("字节码常量折叠")
    pm.enable_pass("字节码死代码消除")
    return pm


# ============================================================
# 反向注册接入内核 exec_api（import 即接线，开关面在 features.MBC_PASSES）
# ============================================================

_MANAGER = make_mbc_pass_manager()


def _apply_passes(module):
    from src import features
    if not features.mbc_passes():
        return module
    return _MANAGER.run(module)


def install() -> None:
    """向内核 exec_api 注册编译后钩子（幂等：重复注册以最后一次为准）。"""
    from src.kernel import exec_api
    exec_api.set_compile_hook(_apply_passes)


def uninstall() -> None:
    """清除内核编译后钩子。"""
    from src.kernel import exec_api
    exec_api.set_compile_hook(None)


install()
