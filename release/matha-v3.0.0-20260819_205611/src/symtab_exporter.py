# -*- coding: utf-8 -*-
"""Matha 符号表导出器：导出所有内建函数签名，供其它语言调用。

让其它编程语言能查询 Matha 的完整函数库（数学/工程/各学科），
知道每个函数的名称、参数数、所属领域，从而正确调用。

导出格式：
  - JSON：通用格式，任何语言可解析
  - Python dict：Python 直接可用
  - TypeScript .d.ts：类型声明
  - Markdown 表格：人类可读文档
"""

from __future__ import annotations
import json
from typing import Any

from src.interp import Interpreter


def _get_arity(fn) -> int:
    """推断函数的参数数。"""
    if hasattr(fn, '__code__'):
        return fn.__code__.co_argcount
    if hasattr(fn, '__wrapped__'):
        return _get_arity(fn.__wrapped__)
    if hasattr(fn, '__closure__') and fn.__closure__:
        return 1
    return 1


def _classify_function(name: str) -> tuple[str, str]:
    """根据函数名推断所属领域和分类。"""
    prefix_map = {
        "运动_": ("运动学", "运动"),
        "力_": ("动力学", "力"),
        "动量_": ("动力学", "动量"),
        "功_": ("动力学", "功"),
        "能量_": ("动力学", "能量"),
        "转动_": ("动力学", "转动"),
        "振动_": ("动力学", "振动"),
        "流体_": ("流体力学", "流体"),
        "浮力_": ("流体力学", "浮力"),
        "管道_": ("流体力学", "管道"),
        "流量_": ("流体力学", "流量"),
        "伯努利_": ("流体力学", "伯努利"),
        "电_": ("电磁学", "电"),
        "电路_": ("电磁学", "电路"),
        "磁_": ("电磁学", "磁"),
        "感应_": ("电磁学", "感应"),
        "交流_": ("电磁学", "交流"),
        "声_": ("声学", "声波"),
        "强级_": ("声学", "声强"),
        "多普勒_": ("声学", "多普勒"),
        "现象_": ("声学", "现象"),
        "弦管_": ("声学", "弦管"),
        "引力_": ("天体力学", "引力"),
        "开普勒_": ("天体力学", "开普勒"),
        "轨道_": ("天体力学", "轨道"),
        "潮汐_": ("天体力学", "潮汐"),
        "相对论_": ("天体力学", "相对论"),
        "轴设_": ("机械设计", "轴"),
        "轴承_": ("机械设计", "轴承"),
        "齿轮_": ("机械设计", "齿轮"),
        "弹簧_": ("机械设计", "弹簧"),
        "联接_": ("机械设计", "联接"),
        "公差_": ("机械设计", "公差"),
        "混凝_": ("建筑结构", "混凝土"),
        "钢结_": ("建筑结构", "钢"),
        "砌体_": ("建筑结构", "砌体"),
        "木结_": ("建筑结构", "木"),
        "基础_": ("建筑结构", "基础"),
        "抗震_": ("建筑结构", "抗震"),
        "换算_": ("数学核心", "单位换算"),
    }
    for prefix, (domain, category) in prefix_map.items():
        if name.startswith(prefix):
            return domain, category
    math_funcs = {"sin", "cos", "tan", "asin", "acos", "atan", "atan2",
                  "sinh", "cosh", "tanh", "sqrt", "ln", "log", "log10", "log2",
                  "exp", "pow", "abs", "floor", "ceil", "round", "trunc",
                  "max", "min", "sum", "sign", "hypot", "deg2rad", "rad2deg"}
    if name in math_funcs:
        return "数学核心", "数学函数"
    math_consts = {"pi", "e", "tau", "phi", "G", "c", "g", "h_planck", "N_A", "R"}
    if name in math_consts:
        return "数学核心", "常量"
    str_list = {"ord", "chr", "len", "get", "slice", "append", "list", "token"}
    if name in str_list:
        return "数学核心", "数据处理"
    if name.startswith("自主_"):
        return "自主系统", "自主"
    if name.startswith("资源_"):
        return "资源库", "资源"
    if name.startswith("生成_") or name.startswith("软件_"):
        return "代码生成", "codegen"
    if name.startswith("导出_") or name.startswith("转译_") or name.startswith("解析_"):
        return "互操作", "互操作"
    return "数学核心", "其它"


def export_symtab(interp: Interpreter = None) -> list[dict]:
    """导出 Matha 的完整符号表。"""
    if interp is None:
        interp = Interpreter()
    entries: list[dict] = []
    seen: set[str] = set()
    for name, fn in sorted(interp.builtins.items()):
        if name in seen:
            continue
        seen.add(name)
        domain, category = _classify_function(name)
        arity = _get_arity(fn)
        entries.append({
            "名称": name,
            "参数数": arity,
            "领域": domain,
            "分类": category,
            "类型": "函数" if callable(fn) else "常量",
        })
    for name, fn_def in sorted(interp.funcs.items()):
        if name in seen:
            continue
        seen.add(name)
        entries.append({
            "名称": name,
            "参数数": len(fn_def.params) if hasattr(fn_def, 'params') else 1,
            "领域": "用户定义",
            "分类": "函数",
            "类型": "函数",
        })
    return entries


def export_symtab_json(interp: Interpreter = None, indent: int = 2) -> str:
    """导出符号表为 JSON。"""
    return json.dumps(export_symtab(interp), ensure_ascii=False, indent=indent)


def export_symtab_d_ts(interp: Interpreter = None) -> str:
    """导出符号表为 TypeScript .d.ts 类型声明。"""
    entries = export_symtab(interp)
    lines = [
        "// Matha 符号表 TypeScript 声明",
        "// 由 Matha symtab_exporter 自动生成",
        "",
        "declare const matha: {",
    ]
    for e in entries:
        name = e["名称"]
        arity = e["参数数"]
        params = ", ".join(f"arg{i}: any" for i in range(arity))
        lines.append(f"  {name}: ({params}) => any,")
    lines.append("};")
    return "\n".join(lines) + "\n"


def export_symtab_markdown(interp: Interpreter = None) -> str:
    """导出符号表为 Markdown 表格。"""
    entries = export_symtab(interp)
    lines = [
        "# Matha 符号表",
        "",
        f"共 {len(entries)} 个符号",
        "",
        "| 名称 | 参数数 | 领域 | 分类 | 类型 |",
        "|------|--------|------|------|------|",
    ]
    for e in entries:
        lines.append(f"| {e['名称']} | {e['参数数']} | {e['领域']} | {e['分类']} | {e['类型']} |")
    return "\n".join(lines) + "\n"


def export_symtab_python(interp: Interpreter = None) -> str:
    """导出符号表为 Python 可导入模块字符串。"""
    entries = export_symtab(interp)
    lines = [
        "# -*- coding: utf-8 -*-",
        "# Matha 符号表（Python 格式）",
        "",
        "MATHA_SYMTAB = [",
    ]
    for e in entries:
        lines.append(f"    {e!r},")
    lines.append("]")
    return "\n".join(lines) + "\n"
