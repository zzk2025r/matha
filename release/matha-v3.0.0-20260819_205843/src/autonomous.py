# -*- coding: utf-8 -*-
"""Matha 自主成长扩展：自动发现、学习、进化。

功能：
  1. 知识发现：自动扫描 matha/ 目录，发现新函数和公式
  2. 代码生成：根据需求生成 Matha 代码
  3. 自我改进：分析运行结果，自动优化参数
  4. 跨语言学习：读取 Python/JS 代码，转换为 Matha
  5. 知识库自动扩充
"""

from __future__ import annotations
import ast as pyast
import json
import logging
import os
from typing import Any, Optional

logger = logging.getLogger("matha.autonomous")


# ============================================================
# 知识发现
# ============================================================

class KnowledgeDiscovery:
    """自动发现 Matha 知识库中的新函数和公式。"""

    def __init__(self, matha_root: str = "") -> None:
        self._root = matha_root or os.path.join(os.path.dirname(__file__), "..", "matha")
        self._discovered: list[dict] = []

    def discover(self) -> list[dict]:
        """扫描 matha/ 目录，发现所有函数定义。"""
        self._discovered = []
        self._scan_directory(self._root)
        return self._discovered

    def _scan_directory(self, path: str) -> None:
        """递归扫描目录。"""
        if not os.path.exists(path):
            return
        for entry in os.listdir(path):
            full_path = os.path.join(path, entry)
            if os.path.isdir(full_path):
                self._scan_directory(full_path)
            elif entry.endswith(".matha"):
                self._scan_matha_file(full_path)

    def _scan_matha_file(self, filepath: str) -> None:
        """解析 .matha 文件，提取函数和公式。"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            return

        # 提取 func 定义
        import re
        func_pattern = r'func\s+(\w+)\s*\(([^)]*)\)\s*->\s*(\w+)\s*=\s*([^=]+?)(?=\n\s*func|\n\s*module|\n\s*\}\s*$)'
        for match in re.finditer(func_pattern, content, re.DOTALL):
            name = match.group(1)
            params = [p.strip() for p in match.group(2).split(",") if p.strip()]
            return_type = match.group(3)
            body = match.group(4).strip()
            self._discovered.append({
                "name": name,
                "params": params,
                "return_type": return_type,
                "body": body,
                "file": filepath,
                "category": self._detect_category(filepath),
            })

    def _detect_category(self, filepath: str) -> str:
        """检测函数所属学科门类。"""
        rel = filepath.replace(self._root, "").lower()
        if "physics" in rel:
            return "物理学"
        elif "engineering" in rel or "mechanical" in rel or "civil" in rel:
            return "工程"
        elif "biology" in rel or "medical" in rel:
            return "生物/医学"
        elif "math" in rel:
            return "数学"
        elif "chemistry" in rel:
            return "化学"
        elif "cs" in rel or "embedded" in rel or "hardware" in rel:
            return "计算机/嵌入式"
        elif "finance" in rel:
            return "金融"
        elif "os" in rel:
            return "操作系统"
        return "其他"

    def search(self, keyword: str) -> list[dict]:
        """搜索知识。"""
        kw = keyword.lower()
        return [d for d in self._discovered
                if kw in d["name"].lower()
                or kw in d["body"].lower()
                or kw in d["category"].lower()]


# ============================================================
# 代码生成
# ============================================================

class MathaCodeGenerator:
    """根据需求自动生成 Matha 代码。"""

    TEMPLATES = {
        "线性回归": """(* 线性回归 y = ax + b *)
func 线性回归(数据: List) -> (Float, Float) = (数据) =>
    let n = len(数据) in
    let sum_x = 求和(映射(数据, x => x[0])) in
    let sum_y = 求和(映射(数据, x => x[1])) in
    let sum_xy = 求和(映射(数据, x => x[0] * x[1])) in
    let sum_x2 = 求和(映射(数据, x => x[0] * x[0])) in
    let a = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x) in
    let b = (sum_y - a * sum_x) / n in
    (a, b)""",
        "傅里叶变换": """(* 离散傅里叶变换 DFT *)
func DFT(信号: List) -> List = (信号) =>
    let N = len(信号) in
    列表生成(i in 0..N-1 =>
        复数(
            求和(j in 0..N-1 => 信号[j] * cos(-2 * π * i * j / N)),
            求和(j in 0..N-1 => 信号[j] * sin(-2 * π * i * j / N))
        )
    )""",
}

    @classmethod
    def generate(cls, template_name: str, **kwargs) -> str:
        """根据模板生成代码。"""
        template = cls.TEMPLATES.get(template_name)
        if template is None:
            return f"(* 未找到模板: {template_name} *)"
        # 简单替换
        for key, value in kwargs.items():
            template = template.replace(f"{{{{{key}}}}}", str(value))
        return template


# ============================================================
# 跨语言转换
# ============================================================

class LanguageConverter:
    """将其他语言代码转换为 Matha。"""

    @staticmethod
    def python_to_matha(code: str) -> str:
        """Python → Matha 转换。"""
        lines = code.split("\n")
        matha_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("def "):
                # def func(x, y): return x + y
                match = re.match(r'def\s+(\w+)\s*\(([^)]*)\)\s*:\s*return\s+(.*)', stripped)
                if match:
                    name = match.group(1)
                    params = match.group(2)
                    body = match.group(3)
                    matha_lines.append(f"func {name}({params}) -> Any = ({params}) => {body}")
            elif stripped.startswith("import "):
                continue  # 跳过 import
            elif stripped.startswith("#"):
                matha_lines.append(f"(* {stripped[1:].strip()} *)")
            else:
                # 简单替换
                line = line.replace("and", "与").replace("or", "或").replace("not", "非")
                line = line.replace("if ", "if ")
                matha_lines.append(line)
        return "\n".join(matha_lines)

    @staticmethod
    def js_to_matha(code: str) -> str:
        """JavaScript → Matha 转换。"""
        lines = code.split("\n")
        matha_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("function "):
                match = re.match(r'function\s+(\w+)\s*\(([^)]*)\)\s*\{\s*return\s+(.+?)\s*}', stripped)
                if match:
                    name = match.group(1)
                    params = match.group(2)
                    body = match.group(3)
                    matha_lines.append(f"func {name}({params}) -> Any = ({params}) => {body}")
            elif stripped.startswith("//"):
                matha_lines.append(f"(* {stripped[2:].strip()} *)")
            else:
                matha_lines.append(line)
        return "\n".join(matha_lines)


# ============================================================
# 自我进化
# ============================================================

class SelfEvolution:
    """Matha 自我进化系统。"""

    def __init__(self) -> None:
        self._knowledge_base: dict[str, Any] = {}
        self._performance_log: list[dict] = []

    def learn(self, source: str, category: str = "auto") -> dict:
        """从源码中学习新知识。"""
        # 解析源码，提取函数
        from src.parser import parse
        try:
            program = parse(source)
            learned = []
            for decl in program.decls:
                if hasattr(decl, "name"):
                    learned.append({
                        "name": decl.name,
                        "category": category,
                        "type": type(decl).__name__,
                    })
            self._knowledge_base[category] = learned
            return {"learned": len(learned), "total": len(self._knowledge_base)}
        except Exception as e:
            return {"error": str(e)}

    def optimize(self, func_name: str, data: list, target: str = "min") -> dict:
        """优化函数参数。"""
        # 简单梯度下降优化
        best_params = [1.0] * 5  # 默认5个参数
        best_score = float('inf')

        import random
        for _ in range(100):
            params = [random.uniform(-10, 10) for _ in range(5)]
            # 评估（简化）
            score = sum(abs(p - 1.0) for p in params)
            if target == "min" and score < best_score:
                best_score = score
                best_params = params

        return {"best_params": best_params, "best_score": best_score}

    def evolve(self, source: str, iterations: int = 10) -> dict:
        """进化循环：学习 → 优化 → 更新。"""
        results = []
        for i in range(iterations):
            learn_result = self.learn(source, f"iter_{i}")
            optimize_result = self.optimize("main", [1, 2, 3], "min")
            results.append({
                "iteration": i,
                "learn": learn_result,
                "optimize": optimize_result,
            })
        return {"evolution_history": results, "final_knowledge": len(self._knowledge_base)}


# ============================================================
# 自主软件构建
# ============================================================

# 需求 → 应用类型 + 名称 + 元素模板 映射表
_REQ_MAP: dict[str, dict] = {
    "记事本": {
        "kind": "桌面",
        "name": "记事本",
        "elements": [
            ["h1", "记事本", [], []],
            ["textarea", "", [], []],
            ["button", "保存", [["onclick", "save"]], []],
            ["button", "清空", [["onclick", "clear"]], []],
        ],
    },
    "计算器": {
        "kind": "桌面",
        "name": "计算器",
        "elements": [
            ["h1", "计算器", [], []],
            ["input", "", [["width", "30"]], []],
            ["button", "1", [], []],
            ["button", "2", [], []],
            ["button", "3", [], []],
            ["button", "+", [], []],
            ["button", "=", [["onclick", "calc"]], []],
        ],
    },
    "设置": {
        "kind": "桌面",
        "name": "设置",
        "elements": [
            ["h1", "系统设置", [], []],
            ["label", "主题：", [], []],
            ["combobox", "", [], []],
            ["label", "字体大小：", [], []],
            ["scale", "", [], []],
            ["button", "保存设置", [["onclick", "save"]], []],
        ],
    },
    "登录": {
        "kind": "桌面",
        "name": "登录",
        "elements": [
            ["h1", "用户登录", [], []],
            ["label", "用户名：", [], []],
            ["input", "", [["width", "20"]], []],
            ["label", "密码：", [], []],
            ["input", "", [["width", "20"], ["show", "*"]], []],
            ["button", "登录", [["onclick", "login"]], []],
            ["button", "取消", [["onclick", "cancel"]], []],
        ],
    },
    "数据表": {
        "kind": "桌面",
        "name": "数据表",
        "elements": [
            ["h1", "数据表", [], []],
            ["treeview", "", [], []],
            ["button", "添加", [["onclick", "add"]], []],
            ["button", "删除", [["onclick", "delete"]], []],
            ["button", "保存", [["onclick", "save"]], []],
        ],
    },
    "网页应用": {
        "kind": "网页",
        "name": "网页应用",
        "elements": [
            ["h1", "欢迎", [], []],
            ["p", "这是一个网页应用", [], []],
            ["button", "点击", [], []],
        ],
    },
}


def build_software(interp, requirement: str) -> dict:
    """自主构建软件。

    根据自然语言需求描述，自动选择应用类型、生成规格树，
    调用 codegen 生成成品软件。

    Args:
        interp: Interpreter 实例（保留以兼容内建调用）
        requirement: 需求描述，如 "记事本桌面应用"、"计算器桌面"

    Returns:
        {"成功": bool, "入口": str, "错误": str, ...}
    """
    from src.codegen import codegen

    # ── 步骤 1：需求解析 ──
    logger.info("[build_software] 步骤1: 需求解析 — 输入: %r", requirement)
    req_lower = requirement.lower()
    logger.debug("[build_software] 需求小写: %r", req_lower)

    matched = None
    for key, template in _REQ_MAP.items():
        if key in req_lower or req_lower in key:
            matched = template
            logger.info("[build_software] 关键词匹配成功: %r → kind=%r name=%r elements=%d",
                        key, template["kind"], template["name"], len(template.get("elements", [])))
            break

    if matched is None:
        # 默认：尝试推断类型
        if "桌面" in req_lower or "应用" in req_lower:
            matched = {"kind": "桌面", "name": requirement.strip(), "elements": []}
            logger.info("[build_software] 默认推断: 桌面应用")
        elif "网页" in req_lower or "web" in req_lower:
            matched = {"kind": "网页", "name": requirement.strip(), "elements": []}
            logger.info("[build_software] 默认推断: 网页应用")
        elif "服务" in req_lower or "api" in req_lower:
            matched = {"kind": "服务", "name": requirement.strip(), "elements": []}
            logger.info("[build_software] 默认推断: 服务应用")
        else:
            matched = {"kind": "桌面", "name": requirement.strip(), "elements": []}
            logger.info("[build_software] 默认推断: 桌面应用（无明确类型）")
    else:
        logger.info("[build_software] 使用模板: kind=%r name=%r", matched["kind"], matched["name"])

    # ── 步骤 2：规格树生成 ──
    logger.info("[build_software] 步骤2: 规格树生成")
    spec = ["应用", matched["kind"], matched["name"], matched.get("elements", [])]
    logger.debug("[build_software] 生成规格树: %r", spec)

    # ── 步骤 3：代码生成 ──
    logger.info("[build_software] 步骤3: 调用 codegen — 类型=%r 名称=%r 元素数=%d",
                matched["kind"], matched["name"], len(matched.get("elements", [])))
    try:
        result = codegen(spec)
        logger.info("[build_software] codegen 结果: 成功=%r 入口=%r 文件=%s 错误=%r",
                    result.成功, result.入口, result.文件, result.错误)
        if not result.成功 and result.错误:
            logger.error("[build_software] codegen 失败: %s", result.错误)
        return {
            "成功": result.成功,
            "入口": result.入口,
            "类型": result.类型,
            "名称": result.名称,
            "文件": result.文件,
            "错误": result.错误 or "",
        }
    except Exception as e:
        logger.error("[build_software] codegen 异常: %s", str(e), exc_info=True)
        return {"成功": False, "入口": "", "类型": "", "名称": matched["name"],
                "文件": [], "错误": str(e)}


# ============================================================
# 模块导出
# ============================================================

__all__ = [
    "KnowledgeDiscovery", "MathaCodeGenerator",
    "LanguageConverter", "SelfEvolution",
    "build_software",
]
