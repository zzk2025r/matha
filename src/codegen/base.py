# -*- coding: utf-8 -*-
"""代码生成器基类：规格树解析 + 分发。

规格树是 Matha 列表（Python list）的嵌套结构。本模块提供：
  - parse_app_spec(spec)  → 规范化的 AppSpec 字典
  - codegen(spec, out_dir) → 按类型分发到具体生成器，写文件，返回结果
  - Generator 基类：元素树遍历、属性序列化等公共工具
"""

from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Any, Optional


class CodegenError(Exception):
    """代码生成错误。"""


# ============================================================
# 规格树解析
# ============================================================

@dataclass
class Element:
    """UI 元素：标签 + 文本 + 属性 + 子元素。"""
    tag: str
    text: str = ""
    attrs: list[tuple[str, str]] = field(default_factory=list)
    children: list["Element"] = field(default_factory=list)

    def is_void(self) -> bool:
        """HTML 自闭合标签（无子元素）。"""
        return self.tag in {"input", "img", "br", "hr", "meta", "link"}


@dataclass
class Endpoint:
    """后端接口：方法 + 路径 + 处理逻辑。"""
    method: str
    path: str
    handler: str  # 处理函数名或内联代码


@dataclass
class StyleRule:
    """样式规则：选择器 + 属性。"""
    selector: str
    props: dict[str, str] = field(default_factory=dict)


@dataclass
class AppSpec:
    """规范化的应用规格。"""
    kind: str          # "网页" | "桌面" | "服务" | "系统"
    name: str          # 应用名
    elements: list[Element] = field(default_factory=list)   # UI 元素
    endpoints: list[Endpoint] = field(default_factory=list)  # 后端接口
    styles: list[StyleRule] = field(default_factory=list)    # 样式规则
    scripts: list[str] = field(default_factory=list)         # 脚本片段
    title: str = ""    # 标题（网页/桌面）
    meta: dict[str, Any] = field(default_factory=dict)       # 其他字段


def parse_app_spec(spec: Any) -> AppSpec:
    """把 Matha 列表规格树解析为 AppSpec。

    输入格式：
        ["应用", 类型, 名称, [元素...]]            # 最简形式
        ["应用", 类型, 名称, [元素...], {字段}]    # 带额外字段

    或直接 ["网页", 名称, [元素...]]（省略 "应用" 头）。
    """
    if not isinstance(spec, (list, tuple)) or len(spec) < 3:
        raise CodegenError(
            f"应用规格必须是长度≥3的列表，实际: {spec!r}")

    idx = 0
    # 可选的 "应用" 头
    if spec[0] == "应用":
        idx = 1
    kind = str(spec[idx]); idx += 1
    if kind not in ("网页", "桌面", "服务", "系统", "内核", "游戏", "建模"):
        raise CodegenError(f"未知应用类型: {kind!r}（应为 网页/桌面/服务/系统/内核/游戏/建模）")

    name = str(spec[idx]); idx += 1

    # 元素列表（可能是 UI 元素、接口、样式、脚本的混合）
    items = spec[idx] if idx < len(spec) and isinstance(spec[idx], (list, tuple)) else []
    idx += 1

    # 额外字段（dict 形式，由 Matha 列表对表示）
    extra = {}
    if idx < len(spec) and isinstance(spec[idx], (list, tuple)):
        for pair in spec[idx]:
            if isinstance(pair, (list, tuple)) and len(pair) >= 2:
                extra[str(pair[0])] = pair[1]

    app = AppSpec(kind=kind, name=name, title=name)
    # 保存原始规格（供内核生成器等需要原始列表的生成器使用）
    app.meta["raw_spec"] = spec
    for item in items:
        _parse_item(item, app)
    # 额外字段覆盖
    for k, v in extra.items():
        if k == "标题":
            app.title = str(v)
        else:
            app.meta[k] = v
    return app


def _parse_item(item: Any, app: AppSpec) -> None:
    """把单个规格项分类解析到 app 的对应列表。"""
    if not isinstance(item, (list, tuple)) or len(item) == 0:
        return
    head = str(item[0])

    # 接口：["接口", 方法, 路径, 处理]
    if head == "接口":
        if len(item) >= 4:
            app.endpoints.append(Endpoint(
                method=str(item[1]),
                path=str(item[2]),
                handler=str(item[3]),
            ))
        return
    # 样式：["样式", 选择器, {属性对}]
    if head == "样式":
        if len(item) >= 3:
            props = {}
            for pair in item[2]:
                if isinstance(pair, (list, tuple)) and len(pair) >= 2:
                    props[str(pair[0])] = str(pair[1])
            app.styles.append(StyleRule(selector=str(item[1]), props=props))
        return
    # 脚本：["脚本", 代码]
    if head == "脚本":
        if len(item) >= 2:
            app.scripts.append(str(item[1]))
        return

    # UI 元素：[标签, 文本, [属性对], [子元素]]
    tag = head
    text = str(item[1]) if len(item) > 1 and item[1] is not None else ""
    attrs: list[tuple[str, str]] = []
    if len(item) > 2 and isinstance(item[2], (list, tuple)):
        for pair in item[2]:
            if isinstance(pair, (list, tuple)) and len(pair) >= 2:
                attrs.append((str(pair[0]), str(pair[1])))
            elif isinstance(pair, (list, tuple)) and len(pair) == 1:
                attrs.append((str(pair[0]), str(pair[0])))
            elif isinstance(pair, (list, tuple)) and len(pair) == 1:
                attrs.append((str(pair[0]), str(pair[0])))
    children: list[Element] = []
    if len(item) > 3 and isinstance(item[3], (list, tuple)):
        for child in item[3]:
            child_elem = _parse_element(child)
            if child_elem is not None:
                children.append(child_elem)
    app.elements.append(Element(tag=tag, text=text, attrs=attrs, children=children))


def _parse_element(item: Any) -> Optional[Element]:
    """递归解析子元素。"""
    if not isinstance(item, (list, tuple)) or len(item) == 0:
        return None
    tag = str(item[0])
    text = str(item[1]) if len(item) > 1 and item[1] is not None else ""
    attrs: list[tuple[str, str]] = []
    if len(item) > 2 and isinstance(item[2], (list, tuple)):
        for pair in item[2]:
            if isinstance(pair, (list, tuple)) and len(pair) >= 2:
                attrs.append((str(pair[0]), str(pair[1])))
    children: list[Element] = []
    if len(item) > 3 and isinstance(item[3], (list, tuple)):
        for child in item[3]:
            ce = _parse_element(child)
            if ce is not None:
                children.append(ce)
    return Element(tag=tag, text=text, attrs=attrs, children=children)


# ============================================================
# 生成结果 + 文件写出
# ============================================================

@dataclass
class CodegenResult:
    """代码生成结果。"""
    成功: bool
    类型: str = ""            # 网页/桌面/服务/系统
    名称: str = ""
    文件: list[str] = field(default_factory=list)  # 写出的文件绝对路径
    错误: Optional[str] = None
    入口: str = ""            # 主入口文件（可双击/运行）

    def as_dict(self) -> dict:
        return {
            "成功": self.成功,
            "类型": self.类型,
            "名称": self.名称,
            "文件": self.文件,
            "入口": self.入口,
            "错误": self.错误,
        }


# 默认输出根目录：matha/output/
OUTPUT_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "matha", "output"
)


def codegen(spec: Any, out_dir: str = None) -> CodegenResult:
    """按规格类型分发到对应生成器，写出文件。

    Args:
        spec: Matha 列表规格树
        out_dir: 输出目录（None 则用 matha/output/<类型>/<名称>）

    Returns:
        CodegenResult
    """
    try:
        app = parse_app_spec(spec)
    except CodegenError as e:
        return CodegenResult(成功=False, 错误=str(e))

    if out_dir is None:
        out_dir = os.path.join(OUTPUT_ROOT, app.kind, app.name)
    os.makedirs(out_dir, exist_ok=True)

    # 延迟导入：避免循环依赖
    from src.codegen.web import WebGenerator
    from src.codegen.desktop import DesktopGenerator
    from src.codegen.backend import BackendGenerator
    from src.codegen.system import SystemGenerator
    from src.codegen.game import GameGenerator
    from src.codegen.model3d import Model3DGenerator
    from src.codegen.kernel import KernelGenerator

    generators = {
        "网页": WebGenerator,
        "桌面": DesktopGenerator,
        "服务": BackendGenerator,
        "系统": SystemGenerator,
        "内核": KernelGenerator,
        "游戏": GameGenerator,
        "建模": Model3DGenerator,
    }
    gen_cls = generators.get(app.kind)
    if gen_cls is None:
        return CodegenResult(成功=False, 错误=f"无生成器: {app.kind}")
    gen = gen_cls(app, out_dir)
    return gen.generate()


# ============================================================
# 生成器基类
# ============================================================

class Generator:
    """生成器基类：提供元素遍历、属性序列化、文件写出等公共工具。

    子类需实现 generate() → CodegenResult。
    """

    def __init__(self, app: AppSpec, out_dir: str):
        self.app = app
        self.out_dir = out_dir

    def generate(self) -> CodegenResult:
        raise NotImplementedError

    # ---- 文件写出 ----

    def _write(self, filename: str, content: str) -> str:
        """写出文件，返回绝对路径。"""
        path = os.path.join(self.out_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    # ---- HTML/CSS 序列化工具 ----

    @staticmethod
    def _serialize_attrs(attrs: list[tuple[str, str]]) -> str:
        """序列化属性对为 HTML 属性字符串。"""
        if not attrs:
            return ""
        parts = []
        for k, v in attrs:
            escaped = (v.replace("&", "&amp;")
                        .replace("<", "&lt;")
                        .replace(">", "&gt;")
                        .replace('"', "&quot;"))
            if k == v:
                parts.append(f" {k}")
            else:
                parts.append(f' {k}="{escaped}"')
        return "".join(parts)

    @staticmethod
    def _escape_html(text: str) -> str:
        """HTML 文本转义。"""
        return (text.replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;"))

    def _element_to_html(self, el: Element, indent: int = 0) -> str:
        """把 Element 序列化为 HTML 片段。"""
        pad = "  " * indent
        attrs_str = self._serialize_attrs(el.attrs)
        if el.is_void():
            return f"{pad}<{el.tag}{attrs_str} />"
        if not el.children:
            return f"{pad}<{el.tag}{attrs_str}>{self._escape_html(el.text)}</{el.tag}>"
        children_html = "\n".join(
            self._element_to_html(c, indent + 1) for c in el.children
        )
        text_part = self._escape_html(el.text) if el.text else ""
        return (f"{pad}<{el.tag}{attrs_str}>\n"
                f"{text_part}\n{children_html}\n"
                f"{pad}</{el.tag}>")
