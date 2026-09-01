"""Matha 语义分析器。

基于 parser 产出的 AST，执行以下语义检查（对应 M3.1/M3.2 规则）：

1. 变量赋值与作用域
   - @ 设定声明变量（@N:变量=值 / @(a|b|c)）
   - Binding 赋值（变量 = 表达式）
   - Variable 引用解析（未定义变量检测）

2. 命令链 >> 语义
   - 链式数据流追踪（前一环节输出 → 后一环节输入）
   - 链类型兼容性（command→command / output→output / command→output）
   - M3.2 触发条件：单条命令/单条输出不足以完成任务时才启用

3. 段内 5 步固定顺序（M3.1/M3.2）
   - 命令→变量→？公式→字母公式→输出
   - 顺序违规检测

4. 公式分层（M3.2）
   - ？公式 = 简化抽象（占位符结构）
   - 字母公式 = 精确化（变量替换占位符）
   - 结构对应检查

5. 资源读取能力（M3.2）
   - 命令/输出识别 URL/文件/目录/端口

6. 循环后缀校验
   - 段级循环 …N(x/y)：N 匹配段号，x ≤ y
   - 全局循环 ……(x/y)：x ≤ y
   - 全局编号一致性
"""

from __future__ import annotations
import logging
from typing import Any, Optional

from src import ast_nodes as ast
from src.symbols import (
    SymbolTable, SegmentTracker, STEP_NAMES,
    detect_resource_type,
    RESOURCE_URL, RESOURCE_FILE, RESOURCE_DIR, RESOURCE_PORT, RESOURCE_TEXT,
)

# 模块级 logger：默认静默（WARNING 级别），通过 SemanticAnalyzer(verbose=True) 开启 DEBUG 输出
logger = logging.getLogger("matha.semantic")


def _build_builtin_symtab() -> "SymbolTable":
    """构建包含所有内建符号的符号表（模块级缓存，仅调用一次）。"""
    from src.interp import BUILTINS as _BUILTINS
    from src.mathlib import CONSTANTS, PHYSICAL_CONSTANTS, UNIT_CONVERSIONS, TEMP_CONVERSIONS
    st = SymbolTable()
    for _name in _BUILTINS:
        st.define(_name, "function", decl=None)
    _math_names = (
        ["sin","cos","tan","asin","acos","atan","atan2",
         "sinh","cosh","tanh","log","ln","log10","log2","exp",
         "sqrt","pow","abs","floor","ceil","round","trunc",
         "max","min","sum","deg2rad","rad2deg","sign","hypot",
         "与","或","非"]
        + list(CONSTANTS.keys())
        + list(PHYSICAL_CONSTANTS.keys())
        + [f"换算_{k}" for k in UNIT_CONVERSIONS]
        + [f"换算_{k}" for k in TEMP_CONVERSIONS]
    )
    for _name in _math_names:
        st.define(_name, "function", decl=None)
    # 领域模块内建符号
    _domain_imports = [
        ("src.domains.mechanics", "_mechanics_symtab_names"),
        ("src.domains.dynamics", "_dynamics_symtab_names"),
        ("src.domains.fluid", "_fluid_symtab_names"),
        ("src.domains.thermo", "_thermo_symtab_names"),
        ("src.domains.em", "_em_symtab_names"),
        ("src.domains.acoustics", "_acoustics_symtab_names"),
        ("src.domains.optics", "_optics_symtab_names"),
        ("src.domains.structural", "_structural_symtab_names"),
        ("src.domains.quantum", "_quantum_symtab_names"),
        ("src.domains.celestial", "_celestial_symtab_names"),
        ("src.domains.nuclear", "_nuclear_symtab_names"),
        ("src.domains.statmech", "_statmech_symtab_names"),
        ("src.domains.fluid_exp", "_fluid_exp_symtab_names"),
        ("src.domains.biology", "_biology_symtab_names"),
        ("src.domains.medical", "_medical_symtab_names"),
        ("src.domains.medtools", "_medtools_symtab_names"),
        ("src.domains.anatomy", "_anatomy_symtab_names"),
        ("src.domains.architecture", "_architecture_symtab_names"),
        ("src.domains.building_struct", "_building_struct_symtab_names"),
        ("src.domains.mech_design", "_mech_design_symtab_names"),
        ("src.domains.kernel_math", "kernel_symtab_names"),
    ]
    for mod_path, fn_name in _domain_imports:
        mod = __import__(mod_path, fromlist=[fn_name])
        for _name in getattr(mod, fn_name)():
            st.define(_name, "function", decl=None)
    return st


# 缓存内建符号表（模块级，仅初始化一次）
_BUILTIN_SYMTAB = _build_builtin_symtab()


class SemanticError:
    """语义错误/警告条目。"""

    def __init__(self, msg: str, severity: str = "error", line: int = 0, node: Any = None):
        self.msg = msg
        self.severity = severity  # "error" | "warning"
        self.line = line
        self.node = node

    def __repr__(self) -> str:
        tag = "错误" if self.severity == "error" else "警告"
        loc = f"L{self.line}" if self.line else ""
        return f"[语义{tag}] {loc}: {self.msg}"


class SemanticAnalyzer:
    """Matha 语义分析器（visitor 模式）。

    用法：
        parser = Parser(source)
        program = parser.parse()
        analyzer = SemanticAnalyzer()
        analyzer.analyze(program)
        for err in analyzer.errors:
            print(err)
    """

    def __init__(self, verbose: bool = False):
        self.symtab = SymbolTable()
        # 注册内建标准库符号（ord/chr/len/get/slice/append/list/token），
        # 使函数式 Matha 引用内建时不报「未定义变量」。
        from src.interp import BUILTINS as _BUILTINS
        for _name in _BUILTINS:
            self.symtab.define(_name, "function", decl=None)
        # 数学函数库内建（实例化时注册，不在 BUILTINS 字典）
        from src.mathlib import CONSTANTS, PHYSICAL_CONSTANTS, UNIT_CONVERSIONS, TEMP_CONVERSIONS
        _math_names = (
            ["sin","cos","tan","asin","acos","atan","atan2",
             "sinh","cosh","tanh","log","ln","log10","log2","exp",
             "sqrt","pow","abs","floor","ceil","round","trunc",
             "max","min","sum","deg2rad","rad2deg","sign","hypot",
             "与","或","非"]
            + list(CONSTANTS.keys())
            + list(PHYSICAL_CONSTANTS.keys())
            + [f"换算_{k}" for k in UNIT_CONVERSIONS]
            + [f"换算_{k}" for k in TEMP_CONVERSIONS]
        )
        for _name in _math_names:
            self.symtab.define(_name, "function", decl=None)
        # 机械领域：运动学 + 材料力学 内建符号
        from src.domains.mechanics import _mechanics_symtab_names
        for _name in _mechanics_symtab_names():
            self.symtab.define(_name, "function", decl=None)
        # 动力学：牛顿定律/动量/功与能/转动/振动 内建符号
        from src.domains.dynamics import _dynamics_symtab_names
        for _name in _dynamics_symtab_names():
            self.symtab.define(_name, "function", decl=None)
        # 流体力学：静力学/运动学/动力学/粘性 内建符号
        from src.domains.fluid import _fluid_symtab_names
        for _name in _fluid_symtab_names():
            self.symtab.define(_name, "function", decl=None)
        # 热力学：气体状态/热力学过程/热传递/热机效率/相变 内建符号
        from src.domains.thermo import _thermo_symtab_names
        for _name in _thermo_symtab_names():
            self.symtab.define(_name, "function", decl=None)
        # 电磁学：静电学/直流电路/磁场/电磁感应/交流电路 内建符号
        from src.domains.em import _em_symtab_names
        for _name in _em_symtab_names():
            self.symtab.define(_name, "function", decl=None)
        # 声学：声波基础/声强声压级/多普勒效应/声学现象/管道弦振动 内建符号
        from src.domains.acoustics import _acoustics_symtab_names
        for _name in _acoustics_symtab_names():
            self.symtab.define(_name, "function", decl=None)
        # 光学：几何光学/波动光学/光度学/光学仪器/色散光谱 内建符号
        from src.domains.optics import _optics_symtab_names
        for _name in _optics_symtab_names():
            self.symtab.define(_name, "function", decl=None)
        # 结构力学：应力状态/梁弯曲/压杆稳定/桁架结构/应变能冲击 内建符号
        from src.domains.structural import _structural_symtab_names
        for _name in _structural_symtab_names():
            self.symtab.define(_name, "function", decl=None)
        # 量子力学：波函数/不确定性原理/角动量自旋/势阱能级/量子隧穿 内建符号
        from src.domains.quantum import _quantum_symtab_names
        for _name in _quantum_symtab_names():
            self.symtab.define(_name, "function", decl=None)
        # 天体力学：万有引力/开普勒定律/轨道参数/潮汐引力场/相对论修正 内建符号
        from src.domains.celestial import _celestial_symtab_names
        for _name in _celestial_symtab_names():
            self.symtab.define(_name, "function", decl=None)
        # 核物理：结合能/放射性衰变/核反应/粒子物理/核能反应堆 内建符号
        from src.domains.nuclear import _nuclear_symtab_names
        for _name in _nuclear_symtab_names():
            self.symtab.define(_name, "function", decl=None)
        # 统计力学：麦克斯韦分布/配分函数/熵与自由能/量子统计/涨落关联 内建符号
        from src.domains.statmech import _statmech_symtab_names
        for _name in _statmech_symtab_names():
            self.symtab.define(_name, "function", decl=None)
        # 流体力学进阶：边界层/可压缩流/明渠水力学/泵与风机/局部损失与管网
        from src.domains.fluid_exp import _fluid_exp_symtab_names
        for _name in _fluid_exp_symtab_names():
            self.symtab.define(_name, "function", decl=None)
        # 生物学：分子生物/细胞/生化/生理种群/微生物免疫
        from src.domains.biology import _biology_symtab_names
        for _name in _biology_symtab_names():
            self.symtab.define(_name, "function", decl=None)
        # 医疗与医药理疗：药代/药效/检验/影像放疗/理疗康复
        from src.domains.medical import _medical_symtab_names
        for _name in _medical_symtab_names():
            self.symtab.define(_name, "function", decl=None)
        # 中医/西医医药工具机械/设备
        from src.domains.medtools import _medtools_symtab_names
        for _name in _medtools_symtab_names():
            self.symtab.define(_name, "function", decl=None)
        # 解剖学：系统/局部/表面/影像/临床解剖
        from src.domains.anatomy import _anatomy_symtab_names
        for _name in _anatomy_symtab_names():
            self.symtab.define(_name, "function", decl=None)
        # 建筑学：物理/材料/设计/施工/规范
        from src.domains.architecture import _architecture_symtab_names
        for _name in _architecture_symtab_names():
            self.symtab.define(_name, "function", decl=None)
        # 建筑结构工程：混凝土/钢/砌体/木/地基/抗震
        from src.domains.building_struct import _building_struct_symtab_names
        for _name in _building_struct_symtab_names():
            self.symtab.define(_name, "function", decl=None)
        # 机械设计：轴/轴承/齿轮/弹簧/紧固件/公差
        from src.domains.mech_design import _mech_design_symtab_names
        for _name in _mech_design_symtab_names():
            self.symtab.define(_name, "function", decl=None)
        # 内核/操作系统：syscall/PCB/页表/中断 数学模型
        from src.domains.kernel_math import kernel_symtab_names
        for _name in kernel_symtab_names():
            self.symtab.define(_name, "function", decl=None)
        self.errors: list[SemanticError] = []
        # 段追踪器栈：在进入段时压入，退出时弹出
        self._seg_stack: list[SegmentTracker] = []
        # 全局编号集合（跨文件一致性检查）
        self._global_ids: dict[str, int] = {}  # code_id → 出现次数
        # 当前段号（用于步骤追踪）
        self._current_seg_id: Optional[int] = None
        # 输出上下文标志：在 [...] 内时，变量未定义降级为警告（可能是文本标签）
        self._in_output = False
        # 调试日志开关：verbose=True 时开启 DEBUG 级日志，便于排查子文件引用等问题
        self.verbose = verbose
        if verbose:
            self._enable_logging()

    # ============================================================
    # 调试日志（非侵入式：默认静默，verbose 模式下输出到 stderr）
    # ============================================================

    def _enable_logging(self) -> None:
        """配置 logger 输出到 stderr（仅 verbose 模式调用）。"""
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("[语义日志] %(message)s"))
            logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

    def _log(self, msg: str) -> None:
        """输出调试日志。仅在 verbose 模式下实际输出，否则静默。"""
        if self.verbose:
            logger.debug(msg)

    # ============================================================
    # 入口
    # ============================================================

    def analyze(self, program: ast.Program) -> list[SemanticError]:
        """分析整个程序，返回错误/警告列表。"""
        self._visit(program)
        return self.errors

    # ============================================================
    # 通用 visitor 分发
    # ============================================================

    def _visit(self, node: Any) -> Any:
        """根据节点类型分发到对应的 visit_* 方法。"""
        if node is None:
            return None
        method_name = f"_visit_{type(node).__name__}"
        visitor = getattr(self, method_name, self._visit_generic)
        return visitor(node)

    def _visit_generic(self, node: Any) -> Any:
        """默认 visitor：遍历 dataclass 字段中的 AST 节点。"""
        if hasattr(node, "__dataclass_fields__"):
            for field_name in node.__dataclass_fields__:
                value = getattr(node, field_name)
                if isinstance(value, list):
                    for item in value:
                        self._visit(item)
                else:
                    self._visit(value)
        return None

    def _error(self, msg: str, node: Any = None, severity: str = "error") -> None:
        """记录语义错误。"""
        line = getattr(node, "line", 0) if node else 0
        self.errors.append(SemanticError(msg, severity=severity, line=line, node=node))

    # ============================================================
    # Program
    # ============================================================

    def _visit_Program(self, node: ast.Program) -> None:
        for decl in node.decls:
            self._visit(decl)

    # ============================================================
    # 模块 / 导入
    # ============================================================

    def _visit_ModuleDecl(self, node: ast.ModuleDecl) -> None:
        self.symtab.define(node.name, "module", decl=node)
        self.symtab.push(f"module:{node.name}")
        # 预注册模块内全部函数名（两遍策略），支持互递归 / 前向引用；
        # 同时检测重复定义。
        for decl in node.decls:
            if isinstance(decl, ast.FuncDef):
                if not self.symtab.define(decl.name, "function", decl=decl):
                    self._error(f"函数 '{decl.name}' 重复定义", decl)
        for decl in node.decls:
            self._visit(decl)
        self.symtab.pop()

    def _visit_ImportDecl(self, node: ast.ImportDecl) -> None:
        # 导入项注册到当前作用域
        if node.import_list:
            for name in node.import_list:
                if not self.symtab.define(name, "import", decl=node):
                    self._error(f"导入项 '{name}' 与已有符号冲突", node)

    # ============================================================
    # 类型定义
    # ============================================================

    def _visit_StructDef(self, node: ast.StructDef) -> None:
        if not self.symtab.define(node.name, "type", decl=node):
            self._error(f"结构体 '{node.name}' 重复定义", node)
        self.symtab.push(f"struct:{node.name}")
        for field in node.fields:
            self._visit(field)
        self.symtab.pop()

    def _visit_EnumDef(self, node: ast.EnumDef) -> None:
        if not self.symtab.define(node.name, "type", decl=node):
            self._error(f"枚举 '{node.name}' 重复定义", node)
        # 构造子注册为值符号：可在表达式中直接引用（如 类型 = 整数）。
        # 构造子归入枚举所在作用域，与其他符号冲突时静默跳过（罕见，不报错）。
        for ctor in node.ctors:
            self.symtab.define(ctor, "constructor", decl=node)

    def _visit_AliasDef(self, node: ast.AliasDef) -> None:
        if not self.symtab.define(node.name, "type", decl=node):
            self._error(f"类型别名 '{node.name}' 重复定义", node)

    def _visit_FuncDef(self, node: ast.FuncDef) -> None:
        # 模块内函数已在 _visit_ModuleDecl 预注册（支持互递归）；
        # 顶层（非模块）函数此处注册。
        if self.symtab.resolve_local(node.name) is None:
            if not self.symtab.define(node.name, "function", decl=node):
                self._error(f"函数 '{node.name}' 重复定义", node)
        self.symtab.push(f"func:{node.name}")
        if node.body:
            self._visit(node.body)
        self.symtab.pop()

    # ============================================================
    # 机械单元 / 代码块 / 段
    # ============================================================

    def _visit_MechUnit(self, node: ast.MechUnit) -> None:
        """机械单元：进入段作用域，追踪 5 步顺序。"""
        seg_id = node.generate.seg_id if hasattr(node.generate, "seg_id") else None
        tracker = SegmentTracker(seg_id=seg_id)
        self._seg_stack.append(tracker)
        self._current_seg_id = seg_id
        self.symtab.push(f"seg#{seg_id}" if seg_id else "seg#_")

        self._visit(node.body)

        self.symtab.pop()
        self._seg_stack.pop()
        if self._seg_stack:
            self._current_seg_id = self._seg_stack[-1].seg_id
        else:
            self._current_seg_id = None

    def _visit_CodeBlock(self, node: ast.CodeBlock) -> None:
        """代码块：逐条分析语句。"""
        self.symtab.push("block")
        for stmt in node.stmts:
            self._visit(stmt)
        self.symtab.pop()

    def _visit_GenStmt(self, node: ast.GenStmt) -> None:
        """gen_stmt / gen_stmt_seg：分类步骤类型并记录到段追踪器。

        当段号变化时（#1 → #2），重置段追踪器。
        """
        content = node.content
        seg_id = node.generate.seg_id

        # 段号变化检测：重置追踪器
        if self._seg_stack:
            tracker = self._seg_stack[-1]
            if seg_id is not None and tracker.seg_id != seg_id:
                # 段号变化 → 创建新追踪器
                tracker = SegmentTracker(seg_id=seg_id)
                self._seg_stack[-1] = tracker
                self._current_seg_id = seg_id

        step = self._classify_gen_stmt_content(content)
        if step is not None and self._seg_stack:
            tracker = self._seg_stack[-1]
            err = tracker.record_step(step, content)
            if err:
                self._error(err, node)

            # 公式分层检查：当字母公式出现时，检查是否有对应的？公式
            if step == "formula_letter":
                self._check_formula_layering(tracker, content)

        # 访问内容
        self._visit(content)

    def _classify_gen_stmt_content(self, content: Any) -> Optional[str]:
        """将 GenStmt 内容分类为 5 步之一。"""
        if isinstance(content, ast.CommandLiteral):
            return "command"
        if isinstance(content, ast.OutputTrail):
            return "output"
        if isinstance(content, ast.Variable):
            if content.is_placeholder:
                return "formula_q"
            return "formula_letter"
        # 表达式：检查是否含 ？ 占位符
        if self._expr_contains_placeholder(content):
            return "formula_q"
        return "formula_letter"

    def _expr_contains_placeholder(self, expr: Any) -> bool:
        """递归检查表达式是否含 ？ 占位符变量。"""
        if expr is None:
            return False
        if isinstance(expr, ast.Variable):
            return expr.is_placeholder
        if isinstance(expr, ast.BinaryOp):
            return (self._expr_contains_placeholder(expr.left)
                    or self._expr_contains_placeholder(expr.right))
        if isinstance(expr, ast.UnaryOp):
            return self._expr_contains_placeholder(expr.operand)
        return False

    # ============================================================
    # 公式分层检查（M3.2）
    # ============================================================

    def _check_formula_layering(self, tracker: SegmentTracker, letter_formula: Any) -> None:
        """检查字母公式与？公式的结构对应。

        M3.2 语义：？公式 = 简化抽象；字母公式 = 精确化。
        若段内有？公式，检查字母公式的运算符结构与？公式一致。
        """
        q_formula = tracker.get_step("formula_q")
        if q_formula is None:
            return  # 无？公式，字母公式独立使用，不检查

        # 提取运算符结构
        q_ops = self._extract_op_structure(q_formula)
        letter_ops = self._extract_op_structure(letter_formula)

        if q_ops and letter_ops and q_ops != letter_ops:
            self._error(
                f"公式分层不一致：？公式的运算符结构 {q_ops} "
                f"与字母公式的运算符结构 {letter_ops} 不匹配；"
                f"字母公式应是对？公式的精确化（运算符结构保持一致）",
                severity="warning",
            )

    def _extract_op_structure(self, expr: Any) -> list[str]:
        """提取表达式的运算符结构（忽略操作数，只保留运算符序列）。

        例：？+？=？ → ["+", "="]
            a+b=c   → ["+", "="]
        """
        ops: list[str] = []
        self._collect_ops(expr, ops)
        return ops

    def _collect_ops(self, expr: Any, ops: list[str]) -> None:
        if isinstance(expr, ast.BinaryOp):
            self._collect_ops(expr.left, ops)
            ops.append(expr.op)
            self._collect_ops(expr.right, ops)
        elif isinstance(expr, ast.UnaryOp):
            ops.append(expr.op)
            self._collect_ops(expr.operand, ops)

    # ============================================================
    # 变量设定 @（变量声明）
    # ============================================================

    def _visit_SetUp(self, node: ast.SetUp) -> None:
        """@ 设定：声明变量 + 赋值检查。

        @N: 形式包含段号，需检测段号变化并重置追踪器。
        """
        # 检查 set_up 的段号（@N:形式），触发段切换
        # 注意：当前 parser 未将 seg_id 存入 SetUp 节点，
        # 段切换由后续 GenStmt 的 seg_id 触发，此处仅处理变量声明
        for item in node.items:
            self._visit_set_up_item(item)

    def _visit_set_up_item(self, item: ast.SetUpItem) -> None:
        """处理单个设定项：声明变量、检查赋值。"""
        target = item.target

        if isinstance(target, ast.Variable):
            # 声明变量
            if not self.symtab.define(
                target.name, "variable", decl=item,
                is_placeholder=target.is_placeholder,
            ):
                # 变量已存在 → 视为重新赋值（警告，非错误）
                self._error(
                    f"变量 '{target.name}' 在当前作用域已定义，此处为重新赋值",
                    severity="warning", node=item,
                )
            # 检查赋值表达式中的变量引用
            if item.value is not None:
                self._visit(item.value)
        elif isinstance(target, ast.PathExpr):
            # 路径表达式 a>>b：声明两端变量
            self._visit(target)
            if item.value is not None:
                self._visit(item.value)
        else:
            self._visit(target)

        # 记录到段追踪器（变量步骤）—— 仅记录第一个设定项，避免重复
        if self._seg_stack and not self._seg_stack[-1].seen_steps.count("variable"):
            tracker = self._seg_stack[-1]
            err = tracker.record_step("variable", item)
            if err:
                self._error(err, item)

    # ============================================================
    # 绑定（赋值）
    # ============================================================

    def _visit_Binding(self, node: ast.Binding) -> None:
        """绑定：target = value。

        语义：
        - 若 target 是 Variable 且未定义 → 声明新变量
        - 若 target 是 Variable 且已定义 → 重新赋值（警告）
        - value 中的变量引用需解析
        """
        target = node.target
        if isinstance(target, ast.Variable):
            existing = self.symtab.resolve(target.name)
            if existing is None:
                # 隐式声明（Matha 允许直接赋值声明）
                self.symtab.define(target.name, "variable", decl=node)
            else:
                if existing.kind != "variable":
                    self._error(
                        f"'{target.name}' 已定义为 {existing.kind}，不能作为变量赋值",
                        node,
                    )
        elif isinstance(target, ast.PathExpr):
            self._visit(target)

        # 检查值表达式
        if node.value is not None:
            self._visit(node.value)

    # ============================================================
    # 变量引用解析
    # ============================================================

    def _visit_Variable(self, node: ast.Variable) -> None:
        """变量引用解析：检查是否已定义。

        在输出上下文 [...] 内，未定义变量降级为警告（可能是文本标签而非变量引用）。
        """
        if node.is_placeholder:
            return  # ？ 占位符不需要解析
        sym = self.symtab.resolve(node.name)
        if sym is None:
            severity = "warning" if self._in_output else "error"
            self._error(f"未定义的变量 '{node.name}'", node, severity=severity)

    # ============================================================
    # 命令链 >> 语义（M3.1/M3.2）
    # ============================================================

    def _visit_ChainStmt(self, node: ast.ChainStmt) -> None:
        """命令链 >> 的语义分析。

        M3.2 规则：
        - 触发条件：单条命令/单条输出不足以完成任务时才启用
        - 链类型兼容：command→command / output→output / command→output
        - 数据流：前一环节的输出可作为后一环节的输入
        """
        if len(node.stmts) < 2:
            self._error("链式语句至少需要 2 个环节", node)
            return

        # M3.2 触发条件检查：若链中只有一个命令且无复杂依赖，提示可简化为单条
        self._check_chain_trigger_condition(node)

        # 逐环节分析 + 类型兼容性检查
        prev_type: Optional[str] = None
        prev_output_vars: list[str] = []

        for i, stmt in enumerate(node.stmts):
            curr_type = self._classify_chain_link(stmt)
            if curr_type is None:
                self._error(f"链式第 {i+1} 个环节类型无法识别", stmt)
                continue

            # 类型兼容性检查
            if prev_type is not None:
                compat = self._check_chain_compatibility(prev_type, curr_type)
                if not compat:
                    self._error(
                        f"链式类型不兼容：'{prev_type}' → '{curr_type}'（第{i}→{i+1}环节）",
                        stmt,
                    )

            # 数据流：提取当前环节的输出变量，供下一环节引用
            curr_output_vars = self._extract_output_vars(stmt)
            # 将前环节输出变量注入作用域（模拟数据流）
            for var_name in prev_output_vars:
                self.symtab.define(var_name, "variable", decl=stmt)
            # 访问当前环节（解析其中的变量引用）
            self._visit(stmt)

            prev_type = curr_type
            prev_output_vars = curr_output_vars

    def _check_chain_trigger_condition(self, node: ast.ChainStmt) -> None:
        """M3.2 触发条件检查：单条命令/单条输出是否已足够。

        简化判断：若所有环节都是相同类型的简单命令（无参数依赖），提示警告。
        """
        # 若链中所有环节都是纯命令文本（无变量依赖），且都是相同资源类型
        all_simple_commands = all(
            self._is_simple_command(stmt) for stmt in node.stmts
        )
        if all_simple_commands and len(node.stmts) >= 2:
            # 检查是否真的需要链式（有数据依赖）
            has_data_dependency = self._has_chain_data_dependency(node)
            if not has_data_dependency:
                self._error(
                    "链式可能不必要：所有环节均为简单命令且无数据依赖；"
                    "M3.2 规则——单条命令/单条输出足以完成任务时不应启用 >> 链式",
                    severity="warning", node=node,
                )

    def _is_simple_command(self, stmt: Any) -> bool:
        """判断链式环节是否为简单命令（无变量依赖）。"""
        content = self._unwrap_chain_link_content(stmt)
        if isinstance(content, ast.CommandLiteral):
            return True
        if isinstance(content, ast.Output):
            return content.expr is None or isinstance(content.expr, ast.StringLit)
        return False

    def _has_chain_data_dependency(self, node: ast.ChainStmt) -> bool:
        """检查链中是否有数据依赖（后一环节引用前一环节的输出）。"""
        for i in range(1, len(node.stmts)):
            vars_in_link = self._extract_output_vars(node.stmts[i - 1])
            if vars_in_link:
                return True
        return False

    def _classify_chain_link(self, stmt: Any) -> Optional[str]:
        """将链式环节分类为 "command" / "output" / "expr" / "setup"。"""
        content = self._unwrap_chain_link_content(stmt)
        if isinstance(content, ast.CommandLiteral):
            return "command"
        if isinstance(content, (ast.Output, ast.OutputTrail)):
            return "output"
        if isinstance(content, ast.SetUp):
            return "setup"
        if isinstance(content, ast.ReadBlock):
            return "command"
        return "expr"

    def _unwrap_chain_link_content(self, stmt: Any) -> Any:
        """解包链式环节，提取实际内容。"""
        if isinstance(stmt, ast.GenStmt):
            return stmt.content
        return stmt

    def _check_chain_compatibility(self, prev: str, curr: str) -> bool:
        """检查链式相邻环节的类型兼容性。

        兼容组合：
            command → command   （命令流水线）
            command → output    （命令结果→输出）
            output  → output    （多输出链式）
            output  → command   （输出→后续命令）
            setup   → command   （设定→命令）
            setup   → output    （设定→输出）
            expr    → expr      （表达式链式）
            expr    → output    （表达式→输出）
        不兼容：
            output → setup      （输出后不能设定变量）
            command → setup     （命令后不能设定变量）
        """
        incompatible = {
            ("output", "setup"),
            ("command", "setup"),
        }
        return (prev, curr) not in incompatible

    def _extract_output_vars(self, stmt: Any) -> list[str]:
        """从链式环节中提取输出变量名（用于数据流追踪）。"""
        content = self._unwrap_chain_link_content(stmt)
        vars_out: list[str] = []

        if isinstance(content, ast.OutputTrail):
            if content.output and content.output.expr:
                self._collect_var_names(content.output.expr, vars_out)
        elif isinstance(content, ast.Output):
            if content.expr:
                self._collect_var_names(content.expr, vars_out)
        elif isinstance(content, ast.CommandLiteral):
            # 命令的输出变量 = 命令文本（简化处理）
            if content.text:
                vars_out.append(content.text)

        return vars_out

    def _collect_var_names(self, expr: Any, names: list[str]) -> None:
        """递归收集表达式中的变量名。"""
        if isinstance(expr, ast.Variable):
            if not expr.is_placeholder:
                names.append(expr.name)
        elif isinstance(expr, ast.BinaryOp):
            self._collect_var_names(expr.left, names)
            self._collect_var_names(expr.right, names)
        elif isinstance(expr, ast.UnaryOp):
            self._collect_var_names(expr.operand, names)

    # ============================================================
    # 输出追踪 + 循环后缀校验
    # ============================================================

    def _visit_OutputTrail(self, node: ast.OutputTrail) -> None:
        """输出追踪：检查循环后缀 + 子文件/文件路径引用 + 资源读取 + 变量引用。"""
        # 总览日志：一行记录本输出追踪的全部后缀字段，便于排查子文件/文件路径问题
        seg_repr = (
            f"…{node.seg_loop.seg_id}({node.seg_loop.fraction.current}/{node.seg_loop.fraction.maximum})"
            if node.seg_loop and node.seg_loop.fraction else None
        )
        glob_repr = (
            f"……({node.global_loop.fraction.current}/{node.global_loop.fraction.maximum})"
            if node.global_loop and node.global_loop.fraction else None
        )
        self._log(
            f"OutputTrail seg=#{self._current_seg_id}: "
            f"subfiles={node.subfiles!r}, file_ref={node.file_ref!r}, "
            f"seg_loop={seg_repr!r}, global_code_id={node.global_code_id!r}, "
            f"global_loop={glob_repr!r}"
        )
        # 访问输出表达式
        self._visit(node.output)

        # 段级循环校验
        if node.seg_loop:
            self._check_seg_loop(node.seg_loop)

        # 子文件引用校验（M3.3：段循环后的下位文件，补充/扩充）
        if node.subfiles:
            self._check_subfiles(node.subfiles)

        # 全局编号一致性
        if node.global_code_id:
            self._global_ids[node.global_code_id] = \
                self._global_ids.get(node.global_code_id, 0) + 1

        # 全局循环校验
        if node.global_loop:
            self._check_global_loop(node.global_loop)

        # 文件路径引用校验（M3.3：全局循环后的文件分割标记）
        if node.file_ref:
            self._check_file_ref(node.file_ref)

        # 资源读取检查（M3.2）
        self._check_resource_reading(node)

    def _check_seg_loop(self, seg_loop: ast.SegLoopSuffix) -> None:
        """段级循环后缀校验：…N(x/y)。"""
        frac = seg_loop.fraction
        frac_repr = f"{frac.current}/{frac.maximum}" if frac else "无分数"
        self._log(f"段级循环校验: …{seg_loop.seg_id}({frac_repr}) 当前段=#{self._current_seg_id}")
        if seg_loop.seg_id is not None and self._current_seg_id is not None:
            if seg_loop.seg_id != self._current_seg_id:
                self._error(
                    f"段级循环段号不匹配：…{seg_loop.seg_id} 与当前段 {self._current_seg_id} 不一致",
                    severity="warning", node=seg_loop,
                )
        if frac:
            if frac.current > frac.maximum:
                self._error(
                    f"段级循环分数无效：{frac.current}/{frac.maximum}（当前次数不应超过最大次数）",
                    node=seg_loop,
                )
            if frac.maximum == 0:
                self._error(
                    f"段级循环最大次数为 0：…{seg_loop.seg_id}({frac.current}/{frac.maximum})",
                    severity="warning", node=seg_loop,
                )

    def _check_global_loop(self, global_loop: ast.GlobalLoopSuffix) -> None:
        """全局循环后缀校验：……(x/y)。"""
        frac = global_loop.fraction
        frac_repr = f"{frac.current}/{frac.maximum}" if frac else "无分数"
        self._log(f"全局循环校验: ……({frac_repr})")
        if frac:
            if frac.current > frac.maximum:
                self._error(
                    f"全局循环分数无效：{frac.current}/{frac.maximum}（当前次数不应超过最大次数）",
                    node=global_loop,
                )

    def _check_subfiles(self, subfiles: list[str]) -> None:
        """M3.3 子文件引用校验：段循环后的下位文件（补充/扩充当前段）。

        多个子文件用 | 分隔。骨架阶段仅识别资源类型，不强制存在性校验。
        """
        self._log(f"子文件引用校验: 共 {len(subfiles)} 个 → {subfiles}")
        for i, sub in enumerate(subfiles):
            if not sub:
                self._log(f"  [{i}] 空子文件引用（将发警告）")
                self._error("子文件引用为空（【】内无路径）", severity="warning")
                continue
            res_type = detect_resource_type(sub)
            self._log(f"  [{i}] '{sub}' → 资源类型={res_type}")
            # 子文件应为文件/目录资源；URL/端口为明显异常（text 可能是相对文件名，仅记录不报警）
            if res_type in (RESOURCE_URL, RESOURCE_PORT):
                self._log(f"  [{i}] 注意: '{sub}' 识别为 {res_type}（子文件应为 file/directory，不应是 URL/端口）")

    def _check_file_ref(self, file_ref: str) -> None:
        """M3.3 文件路径引用校验：全局循环后的文件分割标记。

        语义：当前代码文件被分割/分化成多个文件使用。
        骨架阶段仅识别资源类型，不强制存在性校验。
        """
        if not file_ref:
            self._log("文件路径引用为空（将发警告）")
            self._error("文件路径引用为空（【】内无路径）", severity="warning")
            return
        res_type = detect_resource_type(file_ref)
        self._log(f"文件路径引用: '{file_ref}' → 资源类型={res_type}")
        # 文件路径应为文件/目录资源；URL/端口为明显异常（text 可能是相对文件名，仅记录不报警）
        if res_type in (RESOURCE_URL, RESOURCE_PORT):
            self._log(f"  注意: '{file_ref}' 识别为 {res_type}（文件路径应为 file/directory，不应是 URL/端口）")

    def _check_resource_reading(self, node: ast.OutputTrail) -> None:
        """M3.2 资源读取检查：输出内容若为资源路径，识别并验证。"""
        if node.output and node.output.expr:
            text = self._extract_text(node.output.expr)
            if text:
                res_type = detect_resource_type(text)
                if res_type != RESOURCE_TEXT:
                    self._log(f"输出资源读取: '{text}' → 资源类型={res_type}")
                    # 资源读取是合法的一等能力，仅记录信息（不报错）
                    pass  # 可扩展：验证 URL 可达性、文件存在性等

    def _extract_text(self, expr: Any) -> Optional[str]:
        """从表达式中提取纯文本（用于资源识别）。"""
        if isinstance(expr, ast.StringLit):
            return expr.value
        if isinstance(expr, ast.Variable):
            return expr.name
        return None

    # ============================================================
    # 命令字面量 + 资源读取（M3.2）
    # ============================================================

    def _visit_CommandLiteral(self, node: ast.CommandLiteral) -> None:
        """命令字面量：识别资源读取能力（M3.2）。"""
        res_type = detect_resource_type(node.text)
        if res_type != RESOURCE_TEXT:
            self._log(f"命令资源读取: '{node.text}' → 资源类型={res_type}")
        # M3.2：命令独立拥有读取 URL/文件/文件夹/端口的能力
        # 此处仅做识别，不做强制校验（骨架阶段）
        # 可扩展：验证 URL 格式、文件存在性、端口范围等

    def _visit_ReadBlock(self, node: ast.ReadBlock) -> None:
        """读取块：识别资源类型。"""
        if isinstance(node.content, str):
            res_type = detect_resource_type(node.content)
            text = node.content
        elif isinstance(node.content, ast.CommandLiteral):
            res_type = detect_resource_type(node.content.text)
            text = node.content.text
        elif isinstance(node.content, ast.Annotation):
            res_type = RESOURCE_TEXT  # 自然语言标注
            text = node.content.text
        else:
            res_type = RESOURCE_TEXT
            text = None
        if res_type != RESOURCE_TEXT:
            self._log(f"读取块资源识别: '{text}' → 资源类型={res_type}")

    def _visit_NLBlock(self, node: ast.NLBlock) -> None:
        """自然语言意图块：记录意图，不检查正文变量（正文是自然语言文本）。"""
        self._log(f"自然语言意图块: */{node.annotation.text}/* → {node.natural_lang!r}")

    # ============================================================
    # 文件标记 + 全局编号
    # ============================================================

    def _visit_FileMarker(self, node: ast.FileMarker) -> None:
        """文件标记：#：【文件】或 #：【路径】。"""
        if node.is_end_marker:
            self._log(f"文件结束标记: #：【{node.path_content}】")
            # 文件结束标记：检查全局编号一致性
            pass  # 可扩展：验证所有引用的文件路径是否存在
        else:
            # 路径引用：识别资源类型
            res_type = detect_resource_type(node.path_content)
            self._log(f"文件路径标记: #：【{node.path_content}】 → 资源类型={res_type}")

    def _visit_GlobalIdStmt(self, node: ast.GlobalIdStmt) -> None:
        """全局编号语句：跨文件绑定。"""
        count = self._global_ids.get(node.code_id, 0) + 1
        self._global_ids[node.code_id] = count
        self._log(f"全局编号绑定: {node.code_id}（第 {count} 次出现）")
        if count > 1:
            self._error(
                f"全局编号 '{node.code_id}' 出现 {count} 次；"
                f"跨文件绑定应保持唯一",
                severity="warning", node=node,
            )

    # ============================================================
    # 表达式节点
    # ============================================================

    def _visit_DictLiteral(self, node: ast.DictLiteral) -> None:
        """字典字面量：keys 为字段名（非变量引用），只检查 values。"""
        for key in node.keys:
            # dict key 是字段名/字符串，不作为变量引用检查
            pass
        for value in node.values:
            self._visit(value)

    def _visit_BinaryOp(self, node: ast.BinaryOp) -> None:
        """二元运算的语义分析。

        特殊处理 `=` 运算符（公式赋值）：
        - 左侧变量为引用（必须已定义）
        - 右侧若为简单 Variable，视为公式输出（定义新变量）
        例：端口+路径=连接 → 连接 被定义
        """
        if node.op == "=":
            # 左侧：引用（必须已定义）
            self._visit(node.left)
            # 右侧：若为 Variable，定义为公式输出变量
            if isinstance(node.right, ast.Variable) and not node.right.is_placeholder:
                if self.symtab.resolve(node.right.name) is None:
                    self.symtab.define(node.right.name, "variable", decl=node)
                else:
                    # 已定义，正常引用
                    pass
            else:
                self._visit(node.right)
        else:
            self._visit(node.left)
            self._visit(node.right)

    def _visit_UnaryOp(self, node: ast.UnaryOp) -> None:
        self._visit(node.operand)

    def _visit_Output(self, node: ast.Output) -> None:
        """输出 [...]：设置输出上下文标志，变量未定义降级为警告。"""
        if node.expr is not None:
            prev = self._in_output
            self._in_output = True
            self._visit(node.expr)
            self._in_output = prev

    def _visit_AngleExpr(self, node: ast.AngleExpr) -> None:
        self._visit(node.expr)

    def _visit_FuncApp(self, node: ast.FuncApp) -> None:
        self._visit(node.func)
        self._visit(node.arg)

    def _visit_Lambda(self, node: ast.Lambda) -> None:
        self.symtab.push("lambda")
        for param in node.params:
            if isinstance(param, ast.Variable):
                self.symtab.define(param.name, "parameter", decl=node)
        if node.body:
            self._visit(node.body)
        self.symtab.pop()

    def _visit_LetBinding(self, node: ast.LetBinding) -> None:
        """let x = val [in body] — 局部绑定：在符号表中声明变量。"""
        self.symtab.define(node.name, "variable", decl=node)
        self._visit(node.value)
        if node.body:
            self._visit(node.body)

    def _visit_LetTupleBinding(self, node: ast.LetTupleBinding) -> None:
        """let (a, b, ...) = val [in body] — 元组解构绑定。"""
        for name in node.names:
            self.symtab.define(name, "variable", decl=node)
        self._visit(node.value)
        if node.body:
            self._visit(node.body)

    def _visit_IfExpr(self, node: ast.IfExpr) -> None:
        """三元表达式 cond ? then : else — 解析三个子表达式。"""
        self._visit(node.cond)
        self._visit(node.then)
        if node.else_ is not None:
            self._visit(node.else_)

    def _visit_PathExpr(self, node: ast.PathExpr) -> None:
        """路径表达式 a.b（属性访问）或 a >> b（路径/距离）。

        跨模块引用：模块名.成员 → 跳过成员解析（成员由导入模块定义）。
        """
        self._visit(node.left)
        # 如果左侧是模块引用（如 词法器.扫描），右侧是模块成员，跳过右侧变量检查
        left_sym = self.symtab.resolve_local(getattr(node.left, 'name', None))
        if left_sym and left_sym.kind == "module":
            return  # 跨模块引用：不检查右侧
        self._visit(node.right)

    # ============================================================
    # 控制流
    # ============================================================

    def _visit_IfStmt(self, node: ast.IfStmt) -> None:
        self._visit(node.cond)
        self._visit(node.then_block)
        if node.else_block:
            self._visit(node.else_block)

    def _visit_MatchStmt(self, node: ast.MatchStmt) -> None:
        self._visit(node.scrutinee)
        for pattern, guard, body in node.branches:
            self._visit(pattern)
            self._visit(body)

    def _visit_LoopStep(self, node: ast.LoopStep) -> None:
        self.symtab.push("loop")
        if isinstance(node.var, ast.Variable):
            self.symtab.define(node.var.name, "variable", decl=node)
        self._visit(node.iterable)
        self._visit(node.block)
        self.symtab.pop()

    def _visit_GoStmt(self, node: ast.GoStmt) -> None:
        """go 启动并发任务/协程。

        - go <任务名>：裸标识符视为任务名引用（类似命令名），不强制变量解析；
          若恰好已定义为函数/任务则视为正常引用。
        - go <函数调用> / go <lambda>：正常解析（检查函数已定义、解析实参）。
        """
        expr = node.expr
        if isinstance(expr, ast.Variable) and not expr.is_placeholder:
            # 任务名引用：不报未定义错误（任务可由外部系统/标准库提供）
            return
        self._visit(expr)

    # ============================================================
    # 字面量（叶子节点，无需递归）
    # ============================================================

    def _visit_IntegerLit(self, node: ast.IntegerLit) -> None:
        pass

    def _visit_FloatLit(self, node: ast.FloatLit) -> None:
        pass

    def _visit_StringLit(self, node: ast.StringLit) -> None:
        pass

    def _visit_BoolLit(self, node: ast.BoolLit) -> None:
        pass

    def _visit_Annotation(self, node: ast.Annotation) -> None:
        if node.formula:
            self._visit(node.formula)


# ============================================================
# 便捷入口
# ============================================================

def analyze_ast(program: ast.Program, verbose: bool = False) -> list[SemanticError]:
    """分析已解析的 AST，返回语义错误/警告列表。

    适用于已调用 parse() 得到 program 的场景，避免重复解析。
    """
    analyzer = SemanticAnalyzer(verbose=verbose)
    return analyzer.analyze(program)


def analyze(program: ast.Program, verbose: bool = False) -> list[SemanticError]:
    """分析 AST，返回语义错误/警告列表。

    verbose=True 时输出详细调试日志（子文件引用、文件路径、循环后缀等）。
    """
    analyzer = SemanticAnalyzer(verbose=verbose)
    return analyzer.analyze(program)


def analyze_source(source: str, verbose: bool = False) -> tuple[ast.Program, list[SemanticError]]:
    """从源码分析，返回 (AST, 错误列表)。

    verbose=True 时输出详细调试日志，便于排查子文件引用等潜在问题。
    """
    from src.parser import parse
    program = parse(source)
    errors = analyze(program, verbose=verbose)
    return program, errors
