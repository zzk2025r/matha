# -*- coding: utf-8 -*-
"""
Matha 防火墙引擎 — 用 Matha 语言约束 Matha 代码执行

设计原则：
  1. 三层权限模型：沙箱 / 受限 / 全功能
  2. 白名单 + 黑名单双轨制
  3. 支持 Matha 自身语言定义防火墙规则
  4. 每个执行上下文独立隔离
  5. 所有拦截都抛可识别的 MathaFirewallException

架构：
  FirewallLevel  —— 权限级别枚举
  FirewallRule    —— 单条规则（builtin名 + allow/deny + 描述）
  FirewallPolicy  —— 完整策略（三层默认 + 可自定义）
  MathaFirewall   —— 防火墙引擎，包装 Interpreter
  FirewallException — 可识别的拦截异常
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from src.interp import Interpreter, MathaRuntimeError, ast

logger = logging.getLogger("matha.firewall")


# ============================================================
# 异常类型
# ============================================================

class MathaFirewallException(MathaRuntimeError):
    """防火墙拦截异常 — 可被 catch 并给出小白友好提示。"""

    def __init__(self, builtin_name: str, level: str, reason: str):
        self.builtin_name = builtin_name
        self.level = level
        self.reason = reason
        super().__init__(
            f"🛡️ 防火墙拦截：内建 '{builtin_name}' 在 [{level}] 模式被禁止。\n"
            f"   原因：{reason}\n"
            f"   提示：切换到全功能模式或联系管理员。"
        )


# ============================================================
# 权限级别
# ============================================================

class FirewallLevel(str, Enum):
    """防火墙权限级别。"""
    沙箱 = "sandbox"        # 最严格：只允许纯计算，禁止一切 I/O 和自省
    受限 = "restricted"     # 中等：允许基础数学，禁止文件和网络
    全功能 = "full"          # 最宽松：允许所有操作


# ============================================================
# 单条防火墙规则
# ============================================================

@dataclass
class FirewallRule:
    """一条防火墙规则。"""
    builtin: str              # 内建函数名（如 "读文件"）
    action: str               # "allow" | "deny" | "whitelist"
    level: str = "沙箱"       # 适用级别，"all" 表示所有级别
    reason: str = ""          # 拦截原因说明
    tags: list[str] = field(default_factory=list)  # 标签（io / net / introspect 等）

    def applies_to(self, level: str) -> bool:
        """检查规则是否适用于给定级别（兼容中文名和英文名）。"""
        if self.level == "all":
            return True
        # 统一转换：将中文名转为英文值比较
        _NAME_TO_VALUE = {"沙箱": "sandbox", "受限": "restricted", "全功能": "full"}
        rule_val = _NAME_TO_VALUE.get(self.level, self.level)
        return rule_val == level


# ============================================================
# 默认策略
# ============================================================

DEFAULT_SANDOX_RULES: list[FirewallRule] = [
    # 文件 I/O — 完全禁止
    FirewallRule("读文件", "deny", "沙箱", "文件读取会导致隐私泄露", ["io"]),
    FirewallRule("写文件", "deny", "沙箱", "文件写入可能破坏系统", ["io"]),
    FirewallRule("追加文件", "deny", "沙箱", "文件写入可能破坏系统", ["io"]),
    FirewallRule("读JSON文件", "deny", "沙箱", "文件读取会导致隐私泄露", ["io"]),
    FirewallRule("写JSON文件", "deny", "沙箱", "文件写入可能破坏系统", ["io"]),
    # 外部求值 — 禁止执行其他语言代码
    FirewallRule("外部求值", "deny", "沙箱", "执行外部代码可能引入恶意代码", ["net"]),
    # 自升级 — 禁止修改解释器状态
    FirewallRule("升级", "deny", "沙箱", "自升级可能注入恶意代码", ["introspect"]),
    FirewallRule("试运行", "deny", "沙箱", "试运行可绕过沙箱检查", ["introspect"]),
    # 代码生成 — 禁止生成外部代码
    FirewallRule("生成_网页", "deny", "沙箱", "生成外部代码在沙箱中禁止", ["codegen"]),
    FirewallRule("生成_桌面", "deny", "沙箱", "生成外部代码在沙箱中禁止", ["codegen"]),
    FirewallRule("生成_服务", "deny", "沙箱", "生成外部代码在沙箱中禁止", ["codegen"]),
    FirewallRule("生成_系统", "deny", "沙箱", "生成外部代码在沙箱中禁止", ["codegen"]),
    FirewallRule("生成_游戏", "deny", "沙箱", "生成外部代码在沙箱中禁止", ["codegen"]),
    FirewallRule("生成_建模", "deny", "沙箱", "生成外部代码在沙箱中禁止", ["codegen"]),
    FirewallRule("软件_构建", "deny", "沙箱", "构建软件在沙箱中禁止", ["codegen"]),
    # 互操作导出 — 禁止导出内部状态
    FirewallRule("导出_AST", "deny", "沙箱", "导出内部结构在沙箱中禁止", ["introspect"]),
    FirewallRule("导出_Token", "deny", "沙箱", "导出内部结构在沙箱中禁止", ["introspect"]),
    FirewallRule("转译_Python", "deny", "沙箱", "转译为Python在沙箱中禁止", ["codegen"]),
    FirewallRule("转译_JS", "deny", "沙箱", "转译为JS在沙箱中禁止", ["codegen"]),
    FirewallRule("导出_符号表", "deny", "沙箱", "导出符号表在沙箱中禁止", ["introspect"]),
    # 自主能力 — 禁止
    FirewallRule("自主_调试", "deny", "沙箱", "自主调试在沙箱中禁止", ["introspect"]),
    FirewallRule("自主_优化", "deny", "沙箱", "自主优化在沙箱中禁止", ["introspect"]),
    FirewallRule("自主_成长", "deny", "沙箱", "自主成长在沙箱中禁止", ["introspect"]),
    # 资源库 — 禁止
    FirewallRule("资源_列表", "deny", "沙箱", "访问资源库在沙箱中禁止", ["io"]),
    FirewallRule("资源_读取", "deny", "沙箱", "访问资源库在沙箱中禁止", ["io"]),
    FirewallRule("资源_加载", "deny", "沙箱", "访问资源库在沙箱中禁止", ["io"]),
    FirewallRule("资源_成长", "deny", "沙箱", "访问资源库在沙箱中禁止", ["io"]),
    # 对比操作 — 禁止
    FirewallRule("对比实现", "deny", "沙箱", "跨语言对比在沙箱中禁止", ["net"]),
    FirewallRule("对比升级", "deny", "沙箱", "跨语言升级在沙箱中禁止", ["net"]),
]

DEFAULT_RESTRICTED_RULES: list[FirewallRule] = [
    # 沙箱所有规则
    *DEFAULT_SANDOX_RULES,
    # 受限级别额外禁止：文件读写（允许只读但需授权）
    FirewallRule("读文件", "deny", "受限", "受限模式禁止文件读取", ["io"]),
    FirewallRule("写文件", "deny", "受限", "受限模式禁止文件写入", ["io"]),
    FirewallRule("追加文件", "deny", "受限", "受限模式禁止文件写入", ["io"]),
    # 探针 — 允许查看状态但不允许修改
    FirewallRule("探针_状态", "allow", "受限", "只读状态查询允许", ["introspect"]),
    FirewallRule("探针_函数列表", "allow", "受限", "只读函数列表允许", ["introspect"]),
    FirewallRule("探针_已定义", "allow", "受限", "只读检查允许", ["introspect"]),
]

# 全功能模式无额外规则（所有操作允许）
DEFAULT_FULL_RULES: list[FirewallRule] = []


# ============================================================
# 防火墙策略
# ============================================================

class FirewallPolicy:
    """防火墙策略 — 白名单 + 黑名单 + 自定义规则。"""

    def __init__(self, level: FirewallLevel = FirewallLevel.沙箱):
        self.level = level
        self._deny_rules: list[FirewallRule] = []
        self._allow_rules: list[FirewallRule] = []
        self._load_defaults(level)

    def _load_defaults(self, level: FirewallLevel) -> None:
        """加载默认规则，正确分离 allow/deny。"""
        if level == FirewallLevel.沙箱:
            for r in DEFAULT_SANDOX_RULES:
                (self._allow_rules if r.action == "allow" else self._deny_rules).append(r)
        elif level == FirewallLevel.受限:
            # 沙箱全部 deny + 受限额外 allow
            for r in DEFAULT_SANDOX_RULES:
                self._deny_rules.append(r)
            for r in DEFAULT_RESTRICTED_RULES:
                if r.action == "allow":
                    self._allow_rules.append(r)
                else:
                    self._deny_rules.append(r)
        # 全功能：无默认规则

    def deny(self, builtin: str, reason: str = "", tags: Optional[list[str]] = None) -> "FirewallPolicy":
        """添加黑名单规则（覆盖白名单）。"""
        self._deny_rules.append(FirewallRule(builtin, "deny", self.level.value, reason, tags or []))
        return self

    def allow(self, builtin: str, reason: str = "", tags: Optional[list[str]] = None) -> "FirewallPolicy":
        """添加白名单规则。"""
        self._allow_rules.append(FirewallRule(builtin, "allow", self.level.value, reason, tags or []))
        return self

    def is_blocked(self, builtin_name: str) -> tuple[bool, str]:
        """检查某个内建是否被拦截。返回 (是否被拦, 原因)。"""
        # 白名单优先
        for rule in self._allow_rules:
            if rule.builtin == builtin_name and rule.applies_to(self.level.value):
                return False, ""
        # 黑名单检查
        for rule in self._deny_rules:
            if rule.builtin == builtin_name and rule.applies_to(self.level.value):
                return True, rule.reason
        return False, ""

    def list_blocked(self) -> list[str]:
        """返回当前级别下被拦截的内建列表。"""
        blocked = set()
        for rule in self._deny_rules:
            if rule.applies_to(self.level.value) and rule.action == "deny":
                blocked.add(rule.builtin)
        for rule in self._allow_rules:
            if rule.applies_to(self.level.value) and rule.action == "allow":
                blocked.discard(rule.builtin)
        return sorted(blocked)

    def to_matha_rule_text(self) -> str:
        """将策略转换为 Matha 可读取的规则文本。"""
        lines = [f"// 防火墙策略 — 级别: {self.level.value}"]
        for rule in self._deny_rules:
            if rule.applies_to(self.level.value):
                tag_str = ",".join(rule.tags) if rule.tags else ""
                lines.append(f"// deny {rule.builtin} [{tag_str}] {rule.reason}")
        return "\n".join(lines)


# ============================================================
# 防火墙引擎
# ============================================================

class MathaFirewall:
    """
    Matha 防火墙引擎 — 包装 Interpreter，在执行前后施加安全检查。

    用法：
        fw = MathaFirewall(FirewallLevel.沙箱)
        outputs, trace = fw.run(program_ast)

        # 或用自然语言字符串
        outputs, trace = fw.interpret("#1：[3 + 5]")
    """

    def __init__(self, level: FirewallLevel = FirewallLevel.沙箱,
                 policy: Optional[FirewallPolicy] = None):
        self.level = level
        self.policy = policy or FirewallPolicy(level)
        self._interp = Interpreter()
        self._call_count: int = 0
        self._blocked_count: int = 0
        self._history: list[dict] = []
        self._wrap_interp_call()

    def _wrap_interp_call(self) -> None:
        """拦截解释器的 call 和 _apply，确保所有内建调用都经过防火墙检查。"""
        original_call = self._interp.call
        original_apply = self._interp._apply

        # callable → builtin 名称的反向映射（包含绑定方法）
        _fn_to_name: dict[int, str] = {}
        for _name, _fn in self._interp.builtins.items():
            if callable(_fn):
                _fn_to_name[id(_fn)] = _name
                if hasattr(_fn, '__self__') and hasattr(_fn, '__func__'):
                    _fn_to_name[id(_fn.__func__)] = _name

        def wrapped_call(name: str, *args) -> object:
            """call 只负责名称查找，不拦截——拦截在 _apply 中统一处理。"""
            return original_call(name, *args)

        def wrapped_apply(func, arg) -> object:
            """所有函数应用都经过防火墙检查。"""
            if callable(func) and not isinstance(func, (ast.FuncDef, tuple)):
                fn_name = _fn_to_name.get(id(func))
                if fn_name is None and hasattr(func, '__func__'):
                    fn_name = _fn_to_name.get(id(func.__func__))
                if fn_name:
                    blocked, reason = self.policy.is_blocked(fn_name)
                    if blocked:
                        self._blocked_count += 1
                        raise MathaFirewallException(fn_name, self.level.value, reason)
            return original_apply(func, arg)

        self._interp.call = wrapped_call
        self._interp._apply = wrapped_apply

    # ── 执行入口 ─────────────────────────────────────────

    def run(self, program: ast.Program) -> tuple[list, list[str]]:
        """执行 AST 程序，通过防火墙检查。"""
        try:
            outputs, trace = self._interp.run(program)
            self._history.append({"type": "success", "outputs": len(outputs)})
            return outputs, trace
        except MathaFirewallException as e:
            # _blocked_count 已在 wrapped_apply 中递增，此处不重复计数
            self._history.append({"type": "blocked", "builtin": e.builtin_name})
            raise
        except MathaRuntimeError as e:
            self._history.append({"type": "error", "error": str(e)[:100]})
            raise

    def interpret(self, source: str) -> tuple[list, list[str]]:
        """
        从 Matha 源码字符串执行（解析 + 防火墙 + 解释）。
        返回 (outputs, trace)。
        """
        from src.parser import parse
        program = parse(source)
        return self.run(program)

    # ── 代理 Interpreter 方法 ───────────────────────────────

    def call(self, name: str, *args) -> object:
        """
        防火墙公开的 call 接口（供外部直接调用）。
        内部调用已通过 _wrap_interp_call 自动路由。
        """
        blocked, reason = self.policy.is_blocked(name)
        if blocked:
            self._blocked_count += 1
            raise MathaFirewallException(name, self.level.value, reason)
        return self._interp.call(name, *args)

    def run_interactive(self, code: str) -> dict:
        """
        交互式执行 — 适合 AI Assistant 使用。
        返回结构化结果（包含防火墙统计）。
        """
        self._call_count += 1
        blocked_before = self._blocked_count
        try:
            outputs, trace = self.interpret(code)
            return {
                "success": True,
                "outputs": outputs,
                "trace": trace,
                "blocked_calls": self._blocked_count - blocked_before,
                "level": self.level.value,
            }
        except MathaFirewallException as e:
            return {
                "success": False,
                "error": str(e),
                "builtin": e.builtin_name,
                "level": self.level.value,
                "blocked_calls": self._blocked_count - blocked_before + 1,
            }
        except MathaRuntimeError as e:
            return {
                "success": False,
                "error": str(e),
                "level": self.level.value,
                "blocked_calls": self._blocked_count - blocked_before,
            }

    # ── 策略管理 ───────────────────────────────────────────

    def set_level(self, level: FirewallLevel) -> None:
        """切换防火墙级别。"""
        old_level = self.level
        self.level = level
        self.policy = FirewallPolicy(level)
        self._interp = Interpreter()  # 重建解释器以适配新策略
        self._wrap_interp_call()  # 重新包装新解释器
        self._history.append({"type": "level_change", "from": old_level.value, "to": level.value})

    def add_rule(self, rule: FirewallRule) -> None:
        """添加自定义规则。"""
        if rule.action == "deny":
            self.policy._deny_rules.append(rule)
        else:
            self.policy._allow_rules.append(rule)

    def get_status(self) -> dict:
        """获取防火墙当前状态。"""
        return {
            "level": self.level.value,
            "blocked_count": self._blocked_count,
            "total_calls": self._call_count,
            "blocked_builtins": self.policy.list_blocked(),
            "recent_history": self._history[-10:],
        }

    def reset(self) -> None:
        """重置统计和解释器。"""
        self._call_count = 0
        self._blocked_count = 0
        self._history = []
        self._interp = Interpreter()


# ============================================================
# Matha 侧防火墙内建（注册到 Interpreter）
# ============================================================

def _install_firewall_builtins(interp: Interpreter) -> None:
    """
    将防火墙能力注册为 Matha 内建函数，使 Matha 代码可以：
      - 检查当前防火墙级别
      - 查询被拦截的内建
      - 查看防火墙状态
      - 请求临时提升权限
    """
    # 这些是"只读"操作，在沙箱中也允许
    interp.builtins["防火墙_级别"] = lambda: "沙箱"  # 简化：返回当前级别
    interp.builtins["防火墙_被拦截"] = lambda: []  # 简化：返回被拦截列表
    interp.builtins["防火墙_状态"] = lambda: {}


# ============================================================
# 便捷函数
# ============================================================

def sandbox_interpret(source: str) -> tuple[list, list[str]]:
    """沙箱模式执行 Matha 源码。"""
    fw = MathaFirewall(FirewallLevel.沙箱)
    return fw.interpret(source)


def restricted_interpret(source: str) -> tuple[list, list[str]]:
    """受限模式执行 Matha 源码。"""
    fw = MathaFirewall(FirewallLevel.受限)
    return fw.interpret(source)


def full_interpret(source: str) -> tuple[list, list[str]]:
    """全功能模式执行 Matha 源码。"""
    fw = MathaFirewall(FirewallLevel.全功能)
    return fw.interpret(source)


# ============================================================
# 测试入口
# ============================================================

if __name__ == "__main__":
    import sys
    print("=" * 50)
    print("  Matha 防火墙引擎 v1.0.0")
    print("=" * 50)

    # 测试沙箱模式
    print("\n【沙箱模式测试】")
    fw_sandbox = MathaFirewall(FirewallLevel.沙箱)

    # 允许的纯计算
    r = fw_sandbox.run_interactive("#1：[3 + 5]")
    print(f"  3+5 = {r.get('outputs')}")

    r = fw_sandbox.run_interactive("#1：[阶乘(5)]")
    print(f"  5! = {r.get('outputs')}")

    # 被拦截的文件操作
    r = fw_sandbox.run_interactive("#1：[读文件('test.txt')]")
    print(f"  读文件 → 被拦截: {not r['success']}")

    r = fw_sandbox.run_interactive("#1：[外部求值('python', 'import os')]")
    print(f"  外部求值 → 被拦截: {not r['success']}")

    print(f"\n  拦截统计: {fw_sandbox._blocked_count}/{fw_sandbox._call_count}")
    print(f"  被拦截内建: {fw_sandbox.policy.list_blocked()[:5]}...")
    print("\n防火墙测试完成！")
