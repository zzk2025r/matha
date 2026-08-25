# -*- coding: utf-8 -*-
"""WebGenerator：把 Matha 规格编译为 HTML/CSS/JS 网页成品。

输出文件：
  - index.html   主页面（含内联 CSS/JS，单文件可双击打开）
  - style.css    样式（若样式规则≥1）
  - script.js    脚本（若脚本片段≥1）

布局辅助：Matha 侧可用数学方程算出网格位置/尺寸，通过
  ["样式", 选择器, [("left", "24px"), ("top", "32px")]]
  传入计算结果，本生成器原样序列化为 CSS。
"""

from __future__ import annotations
import os
from src.codegen.base import Generator, CodegenResult


class WebGenerator(Generator):
    """网页生成器：AppSpec → HTML/CSS/JS 文件。"""

    def generate(self) -> CodegenResult:
        files: list[str] = []
        try:
            html = self._build_html()
            files.append(self._write("index.html", html))

            if self.app.styles:
                css = self._build_css()
                files.append(self._write("style.css", css))

            if self.app.scripts:
                js = self._build_js()
                files.append(self._write("script.js", js))
        except Exception as e:
            return CodegenResult(成功=False, 类型="网页", 名称=self.app.name,
                                 错误=str(e))

        return CodegenResult(
            成功=True, 类型="网页", 名称=self.app.name,
            文件=files, 入口=files[0],
        )

    # ---- HTML 构建 ----

    def _build_html(self) -> str:
        """构建完整 HTML 文档。"""
        title = self._escape_html(self.app.title or self.app.name)
        body_parts = [self._element_to_html(el, 2) for el in self.app.elements]

        css_link = '\n  <link rel="stylesheet" href="style.css">' if self.app.styles else ""
        js_link = '\n  <script src="script.js"></script>' if self.app.scripts else ""

        # 内联兜底样式（无 style.css 时也给基本排版）
        inline_style = "" if self.app.styles else (
            "\n  <style>\n"
            "    body { font-family: sans-serif; margin: 24px; }\n"
            "    button { padding: 8px 16px; margin: 4px; cursor: pointer; }\n"
            "    input { padding: 6px; font-size: 16px; }\n"
            "  </style>"
        )

        body = "\n".join(body_parts) if body_parts else "  <!-- 空 应用 -->"
        return (
            "<!DOCTYPE html>\n"
            '<html lang="zh-CN">\n'
            "<head>\n"
            '  <meta charset="UTF-8">\n'
            f"  <title>{title}</title>{css_link}{inline_style}\n"
            "</head>\n"
            "<body>\n"
            f"{body}\n"
            f"{js_link}\n"
            "</body>\n"
            "</html>\n"
        )

    def _build_css(self) -> str:
        """构建 CSS 文件。"""
        lines = ["/* 由 Matha codegen 生成 */", ""]
        for rule in self.app.styles:
            props_str = "\n".join(f"  {k}: {v};" for k, v in rule.props.items())
            lines.append(f"{rule.selector} {{")
            lines.append(props_str)
            lines.append("}")
            lines.append("")
        return "\n".join(lines)

    def _build_js(self) -> str:
        """构建 JS 文件。"""
        lines = ["// 由 Matha codegen 生成", ""]
        for script in self.app.scripts:
            lines.append(script)
            lines.append("")
        return "\n".join(lines)
