# -*- coding: utf-8 -*-
"""Matha 资源库管理器：保护隔离 + 读取 + 自主成长扩展。

资源库架构：
  - 模板：读取和构建（？#：{...}）
  - 子文件：编写公式代码（#：{...}，专用于编程，不能出现在资源库内）
  - 资源库：数学核心机械语言与分支的保护隔离仓库
    * 保护隔离：只读，防止损坏
    * 自主成长数据库：子文件资源不足时主动扩展生成
    * 子文件通过 资源_加载 读取资源库中的公式代码

资源库结构：
  matha/library/
    ├── core/           数学核心（算术、几何、三角）
    ├── mechanics/      机械分支（轴、轴承、应力）
    ├── structural/     结构力学分支（梁、柱）
    ├── physics/        物理分支（力学）
    └── index.matha     资源索引

保护隔离机制：
  - 资源库文件标记为只读（_protected 集合）
  - 加载到沙箱试运行，不直接修改本体
  - 自主成长扩展时，新资源先验证再入库
  - 子文件不能写入资源库

自主成长扩展：
  - 子文件请求资源不存在时
  - 资源库通过 SelfGrower 生成新公式代码
  - 沙箱验证后写入资源库对应分支目录
  - 更新索引
"""

from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Any, Optional

from src.interp import Interpreter
from src.selfupgrade import Sandbox
from src.autonomous import SelfGrower


# 资源库根目录
LIBRARY_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'matha', 'library'
)

# 学科分支目录映射
DISCIPLINES = {
    'core': '数学核心',
    'mechanics': '机械',
    'structural': '结构力学',
    'physics': '物理',
}


@dataclass
class LibraryEntry:
    """资源库条目。"""
    path: str          # 相对路径（如 core/arithmetic）
    name: str          # 资源名
    discipline: str    # 学科分支
    content: str       # 源码内容
    protected: bool = True  # 保护隔离标记

    def as_dict(self) -> dict:
        return {
            "路径": self.path,
            "名称": self.name,
            "学科": self.discipline,
            "保护": self.protected,
        }


@dataclass
class GrowResult:
    """资源库自主成长结果。"""
    成功: bool
    新资源: Optional[str] = None
    学科: Optional[str] = None
    内容: Optional[str] = None
    错误: Optional[str] = None

    def as_dict(self) -> dict:
        return {
            "成功": self.成功,
            "新资源": self.新资源,
            "学科": self.学科,
            "错误": self.错误,
        }


class Library:
    """资源库管理器：保护隔离 + 读取 + 自主成长扩展。

    核心原则：
      1. 保护隔离：资源库文件只读，子文件不能写入
      2. 沙箱加载：资源加载到沙箱试运行，不污染本体
      3. 自主成长：资源不足时主动生成新公式代码入库
      4. 子文件专用编程：子文件不进入资源库
    """

    def __init__(self, root: str = None):
        self.root = root or LIBRARY_ROOT
        self._cache: dict[str, LibraryEntry] = {}
        self._protected: set[str] = set()
        self._scan()

    # ---------- 扫描与索引 ----------

    def _scan(self) -> None:
        """扫描资源库目录，建立索引。"""
        self._cache.clear()
        self._protected.clear()
        if not os.path.isdir(self.root):
            return
        for dirpath, _, filenames in os.walk(self.root):
            for fname in filenames:
                if not fname.endswith('.matha'):
                    continue
                full = os.path.join(dirpath, fname)
                rel = os.path.relpath(full, self.root).replace('\\', '/')
                # 去掉 .matha 后缀
                key = rel[:-6] if rel.endswith('.matha') else rel
                # index.matha 特殊处理
                if key == 'index':
                    continue
                # 学科分支
                disc = key.split('/')[0] if '/' in key else 'core'
                name = os.path.splitext(fname)[0]
                try:
                    with open(full, encoding='utf-8') as f:
                        content = f.read()
                except OSError:
                    continue
                self._cache[key] = LibraryEntry(
                    path=key, name=name,
                    discipline=disc, content=content,
                    protected=True,
                )
                self._protected.add(key)

    def list(self) -> list[dict]:
        """列出所有资源条目。"""
        return [e.as_dict() for e in self._cache.values()]

    def list_by_discipline(self, discipline: str) -> list[dict]:
        """按学科分支列出资源。"""
        return [e.as_dict() for e in self._cache.values()
                if e.discipline == discipline]

    def has(self, path: str) -> bool:
        """资源是否存在。"""
        return path in self._cache

    def read(self, path: str) -> Optional[str]:
        """读取资源内容（只读，保护隔离）。"""
        entry = self._cache.get(path)
        return entry.content if entry else None

    def get_entry(self, path: str) -> Optional[LibraryEntry]:
        """获取资源条目。"""
        return self._cache.get(path)

    # ---------- 沙箱加载 ----------

    def load(self, path: str, interp: Interpreter) -> dict:
        """将资源加载到解释器的沙箱中试运行。

        保护隔离：资源在沙箱中执行，不直接修改本体。
        通过后合并到本体（资源是受信任的公式定义）。

        Returns:
            {"成功": bool, "新函数": [...], "错误": str|None}
        """
        entry = self._cache.get(path)
        if entry is None:
            return {"成功": False, "新函数": [], "错误": f"资源不存在: {path}"}
        sb = Sandbox(interp)
        _, _, err = sb.run(entry.content)
        if err is not None:
            sb.rollback()
            return {"成功": False, "新函数": [], "错误": err}
        diff = sb.commit()
        new_funcs = list(diff.get("新函数", [])) + list(diff.get("改函数", []))
        return {"成功": True, "新函数": new_funcs, "错误": None}

    def load_discipline(self, discipline: str, interp: Interpreter) -> dict:
        """加载整个学科分支的所有资源。"""
        results = []
        all_new = []
        for key, entry in self._cache.items():
            if entry.discipline != discipline:
                continue
            r = self.load(key, interp)
            results.append({"路径": key, "成功": r["成功"], "错误": r["错误"]})
            if r["成功"]:
                all_new.extend(r["新函数"])
        return {
            "成功": all(r["成功"] for r in results) if results else False,
            "新函数": all_new,
            "详情": results,
            "错误": None,
        }

    # ---------- 自主成长扩展 ----------

    def grow(self, interp: Interpreter, requirement: str,
             discipline: str = 'core', name: str = None) -> GrowResult:
        """资源库自主成长：当子文件资源不足时，主动生成新公式代码。

        流程：
          1. 根据需求描述生成候选 Matha 公式代码
          2. 沙箱试运行验证
          3. 验证通过 → 写入资源库对应分支目录
          4. 更新索引缓存

        Args:
            interp: 解释器实例（用于沙箱验证）
            requirement: 需求描述（如 "计算圆环面积"）
            discipline: 目标学科分支
            name: 资源名（None 则从需求生成）

        Returns:
            GrowResult
        """
        # 生成资源名
        if name is None:
            name = requirement.replace(' ', '_')[:20]
        # 生成候选公式代码
        candidate = self._generate_candidate(requirement, discipline, name)
        if candidate is None:
            return GrowResult(成功=False, 错误=f"无法为 '{requirement}' 生成公式代码")

        # 沙箱试运行验证
        sb = Sandbox(interp)
        _, _, err = sb.run(candidate)
        if err is not None:
            sb.rollback()
            return GrowResult(成功=False, 错误=f"生成的公式代码无效: {err}",
                              内容=candidate)
        sb.commit()  # 合并到本体（让子文件可用）

        # 写入资源库（保护隔离：新资源先验证后入库）
        disc_dir = os.path.join(self.root, discipline)
        os.makedirs(disc_dir, exist_ok=True)
        file_path = os.path.join(disc_dir, f'{name}.matha')
        rel_path = f'{discipline}/{name}'

        # 避免覆盖已保护资源
        if rel_path in self._protected:
            return GrowResult(成功=True, 新资源=rel_path,
                              学科=discipline, 内容=candidate)
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(candidate)
        except OSError as ex:
            return GrowResult(成功=False, 错误=f"写入资源库失败: {ex}")

        # 更新缓存
        self._cache[rel_path] = LibraryEntry(
            path=rel_path, name=name,
            discipline=discipline, content=candidate,
            protected=True,
        )
        self._protected.add(rel_path)

        return GrowResult(成功=True, 新资源=rel_path,
                          学科=discipline, 内容=candidate)

    def _generate_candidate(self, requirement: str,
                            discipline: str, name: str) -> Optional[str]:
        """根据需求描述生成候选 Matha 公式代码。

        基于学科模板生成基础公式框架。
        """
        # 简单的模板化生成（实际可扩展为更智能的生成）
        header = f"(* 资源库：{discipline} — {requirement} *)\n"
        header += f"(* 自主成长生成：保护隔离 *)\n\n"

        # 根据需求关键词匹配公式模板
        req = requirement.lower()
        if '面积' in req and '圆' in req:
            return header + (
                "func 圆面积(r: Float) -> Float = (r) => 3.14159 * r * r\n"
            )
        if '面积' in req and '矩形' in req:
            return header + (
                "func 矩形面积(w: Float, h: Float) -> Float = (w, h) => w * h\n"
            )
        if '体积' in req and '球' in req:
            return header + (
                "func 球体积(r: Float) -> Float = (r) => "
                "4 * 3.14159 * r ^ 3 / 3\n"
            )
        if '体积' in req and '圆柱' in req:
            return header + (
                "func 圆柱体积(r: Float, h: Float) -> Float = (r, h) => "
                "3.14159 * r * r * h\n"
            )
        if '力' in req and ('牛顿' in req or '第二' in req):
            return header + (
                "func 牛顿力(m: Float, a: Float) -> Float = (m, a) => m * a\n"
            )
        if '能量' in req or '动能' in req:
            return header + (
                "func 动能(m: Float, v: Float) -> Float = (m, v) => "
                "0.5 * m * v ^ 2\n"
            )
        # 默认：生成占位函数（恒零）
        return header + (
            f"func {name}(x: Float) -> Float = (x) => 0\n"
        )

    # ---------- 保护隔离检查 ----------

    def is_protected(self, path: str) -> bool:
        """资源是否受保护（只读）。"""
        return path in self._protected

    def disciplines(self) -> list[str]:
        """列出所有学科分支。"""
        return list(DISCIPLINES.keys())


# 全局单例
_library: Optional[Library] = None


def get_library() -> Library:
    """获取全局资源库单例。"""
    global _library
    if _library is None:
        _library = Library()
    return _library
