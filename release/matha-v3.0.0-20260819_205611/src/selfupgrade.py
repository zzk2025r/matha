"""Matha 自我升级子系统：探针 + 沙箱 + 升级。

为解释器提供运行时内省（探针）、隔离试运行（沙箱）与安全合并
（升级）三件套，使 Matha 程序可在运行时加载新源码、先在沙箱中
验证、再决定是否提交到本体——实现「自我升级」而不会因坏代码
污染已注册的函数/变量。

设计要点：
  - Probe：只读内省，返回普通 dict/list，供 Matha 与 Python 两侧使用。
  - Sandbox：克隆本体解释器的 env/funcs/constructors/builtins，在其上
    运行新源码；本体不受影响。提供 diff()/commit()/rollback()。
  - upgrade(parent, source, verify)：沙箱试运行 →（可选）校验 → 通过
    则 commit，失败/校验不过则 rollback，返回 UpgradeResult。

状态化内建（探针_状态 / 试运行 / 升级 等）由 Interpreter._install_self_builtins
注册并绑定到各自解释器实例；沙箱克隆后会重新绑定到沙箱自身解释器，
故在沙箱内部调用 升级(...) 会在沙箱内部再开一层沙箱，层间隔离。
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from src.interp import Interpreter, MathaRuntimeError


# ============================================================
# 探针：只读内省
# ============================================================

class Probe:
    """对解释器运行时状态的只读内省视图。

    所有方法返回普通容器（dict/list/bool），不返回解释器内部对象的
    可变引用，便于跨语言边界（Matha 侧只能消费 dict/list/标量）。
    """

    def __init__(self, interp: Interpreter):
        self._i = interp

    def state(self) -> dict:
        """综合状态快照：变量/函数/内建/构造子名 + 输出/追踪/深度计数。"""
        i = self._i
        return {
            "变量": list(i.env.keys()),
            "函数": list(i.funcs.keys()),
            "内建": list(i.builtins.keys()),
            "构造子": list(i.constructors),
            "输出数": len(i.outputs),
            "追踪数": len(i.trace),
            "深度": i._depth,
        }

    def env(self) -> dict:
        """环境变量名 → 值 的浅快照。"""
        return dict(self._i.env)

    def func_names(self) -> list:
        """已注册函数名列表。"""
        return list(self._i.funcs.keys())

    def builtin_names(self) -> list:
        return list(self._i.builtins.keys())

    def has(self, name: str) -> bool:
        """name 是否已定义（变量/函数/内建/构造子任一）。"""
        i = self._i
        return (name in i.env or name in i.funcs
                or name in i.builtins or name in i.constructors)

    def func_info(self, name: str) -> Optional[dict]:
        """单个函数的参数信息；未定义返回 None。"""
        f = self._i.funcs.get(name)
        if f is None:
            return None
        params: list[str] = []
        if f.body is not None:
            params = [self._i._param_name(p) for p in f.body.params]
        return {"名": name, "参数": params}


# ============================================================
# 沙箱：隔离试运行
# ============================================================

# 状态化内建名集合：克隆时需重新绑定到沙箱自身解释器
_STATEFUL_BUILTINS = ("探针_状态", "探针_函数列表", "探针_已定义",
                      "试运行", "升级")


class Sandbox:
    """隔离执行环境：克隆本体解释器状态，代码运行不影响本体。

    典型流程：
        sb = interp.sandbox()
        outs, trace, err = sb.run(new_source)
        if err is None and ok(outs): sb.commit()
        else: sb.rollback()

    合并策略（commit）：env/funcs/constructors 以 update 合并到本体；
    builtins 不合并（升级不改 Python 内建）。一次性：commit 或
    rollback 后沙箱即作废，不可再用。
    """

    def __init__(self, parent: Interpreter):
        self.parent = parent
        # 新建独立解释器实例，避免共享可变状态
        self.interp = Interpreter(debug=False)
        self.interp.env = dict(parent.env)
        self.interp.funcs = dict(parent.funcs)
        self.interp.constructors = set(parent.constructors)
        # 继承父级纯函数内建；状态化内建重新绑定到沙箱自身
        self.interp.builtins = {k: v for k, v in parent.builtins.items()
                                if k not in _STATEFUL_BUILTINS}
        self.interp._install_self_builtins()
        # 初始快照（保留对象引用以检测覆写）
        self._snapshot = {
            "env": dict(self.interp.env),
            "funcs": dict(self.interp.funcs),
            "ctors": set(self.interp.constructors),
        }
        self._disposed = False

    # ---------- 运行 ----------

    def run(self, source: str) -> tuple[list, list[str], Optional[str]]:
        """在沙箱中解析并运行源码；返回 (outputs, trace, error)。

        error 非 None 表示解析或运行时出错（已捕获，不抛出）。
        """
        self._check()
        from src.parser import parse
        try:
            program = parse(source)
            outputs, trace = self.interp.run(program)
            return outputs, trace, None
        except Exception as ex:  # 含 ParseError / MathaRuntimeError
            return self.interp.outputs, self.interp.trace, \
                f"{type(ex).__name__}: {ex}"

    def call(self, name: str, *args):
        """在沙箱解释器上调用函数/内建。"""
        self._check()
        return self.interp.call(name, *args)

    # ---------- 变更检测 ----------

    def diff(self) -> dict:
        """沙箱相对初始快照的变更摘要。

        返回：
            {
              "新函数": [...],      # 新增名
              "改函数": [...],      # 覆写名（FuncDef 对象变了）
              "新变量": {名: 值},
              "改变量": {名: 新值},
              "新构造子": [...],
            }
        """
        self._check()
        snap = self._snapshot
        i = self.interp
        new_funcs = [n for n in i.funcs if n not in snap["funcs"]]
        redef_funcs = [n for n, f in i.funcs.items()
                       if n in snap["funcs"] and f is not snap["funcs"][n]]
        new_vars = {n: v for n, v in i.env.items() if n not in snap["env"]}
        changed_vars = {n: v for n, v in i.env.items()
                        if n in snap["env"] and v != snap["env"][n]}
        new_ctors = sorted(i.constructors - snap["ctors"])
        return {
            "新函数": sorted(new_funcs),
            "改函数": sorted(redef_funcs),
            "新变量": new_vars,
            "改变量": changed_vars,
            "新构造子": new_ctors,
        }

    # ---------- 提交 / 回滚 ----------

    def commit(self) -> dict:
        """将沙箱变更合并回本体解释器；返回 diff。一次性。"""
        self._check()
        d = self.diff()
        self.parent.env.update(self.interp.env)
        self.parent.funcs.update(self.interp.funcs)
        self.parent.constructors.update(self.interp.constructors)
        self._disposed = True
        return d

    def rollback(self) -> None:
        """放弃沙箱变更。一次性。"""
        self._disposed = True

    def _check(self) -> None:
        if self._disposed:
            raise MathaRuntimeError("沙箱已 commit/rollback，不可再用")


# ============================================================
# 升级结果
# ============================================================

@dataclass
class UpgradeResult:
    """升级流程的统一结果。"""
    成功: bool
    错误: Optional[str]
    输出: list = field(default_factory=list)
    追踪: list = field(default_factory=list)
    变更: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        """转为普通 dict（供 Matha 侧消费）。"""
        return {
            "成功": self.成功,
            "错误": self.错误,
            "输出": self.输出,
            "变更": self.变更,
        }


# ============================================================
# 升级入口
# ============================================================

def upgrade(parent: Interpreter, source: str,
            verify: Optional[Callable[[Sandbox], bool]] = None) -> UpgradeResult:
    """加载 Matha 源码到沙箱试运行，通过后合并到本体解释器。

    流程：
      1. 创建沙箱（克隆本体状态）
      2. 在沙箱中解析 + 运行源码
      3. 运行出错 → rollback，返回失败结果（本体未被触碰）
      4. verify 给定时调用 verify(sandbox)；返回假或抛错 → rollback
      5. 通过 → commit，返回成功结果（含变更 diff）

    Args:
        parent: 本体解释器（升级目标）。
        source: 待加载的 Matha 源码（通常含 func 定义）。
        verify: 可选校验回调，接收沙箱，返回 bool。

    Returns:
        UpgradeResult
    """
    sb = Sandbox(parent)
    outputs, trace, err = sb.run(source)
    if err is not None:
        sb.rollback()
        return UpgradeResult(成功=False, 错误=err, 输出=outputs,
                             追踪=trace, 变更={})
    if verify is not None:
        try:
            ok = verify(sb)
        except Exception as ex:
            sb.rollback()
            return UpgradeResult(成功=False, 错误=f"校验异常: {ex}",
                                 输出=outputs, 追踪=trace, 变更={})
        if not ok:
            sb.rollback()
            return UpgradeResult(成功=False, 错误="校验未通过",
                                 输出=outputs, 追踪=trace, 变更={})
    diff = sb.commit()
    return UpgradeResult(成功=True, 错误=None, 输出=outputs,
                         追踪=trace, 变更=diff)
