# -*- coding: utf-8 -*-
"""Matha 代码生成子系统：把 Matha 数据规格编译成成品软件产物。

设计哲学（独立生态原则）：
  - 用户只写 Matha（列表/字符串/函数/数学方程）
  - codegen 把 Matha 数据树编译为目标产物（HTML/CSS/JS/Python/ASM）
  - 目标产物是「编译输出」，类似 C 编译为汇编——用户不写目标语言
  - 数学方程辅助布局/尺寸/动画计算（在 Matha 侧求解后传入规格）

规格树格式（纯 Matha 列表表示）：
  ["应用", 类型, 名称, [元素...], {可选字段}]
    类型 ∈ {"网页", "桌面", "服务", "系统", "内核"}
    元素 = [标签, 文本, [属性对], [子元素]]   # UI 元素
         | ["接口", 方法, 路径, 处理函数名]    # 后端接口
         | ["路由", 路径, 文件]               # 静态路由
         | ["样式", 选择器, {属性: 值}]       # 样式规则
         | ["脚本", 代码]                     # 脚本片段
         | ["系统名", "MyOS"]                  # 内核规格
         | ["内核版本", "0.1"]
         | ["系统调用", "write,read,exit"]
         | ["页大小", "4096"]

示例（内核生成）：
  内核规格 = ["应用", "内核", "MyOS", [
    ["系统名", "MyOS", [], []],
    ["内核版本", "0.1", [], []],
    ["系统调用", "write,read,exit,fork", [], []],
  ]]

生成器：
  - WebGenerator     → .html / .css / .js（可直接浏览器打开）
  - DesktopGenerator → .py（Tkinter 壳，可双击运行）
  - BackendGenerator → .py（http.server，可启动 HTTP 服务）
  - SystemGenerator  → .sh / .bat（系统脚本）
  - KernelGenerator  → .asm（x86 NASM 汇编，可构建为内核镜像）

自主构建：SoftwareBuilder（src/autonomous.py）从需求描述生成规格 → codegen → 沙箱验证 → 输出。
"""

from src.codegen.base import (
    CodegenError,
    CodegenResult,
    parse_app_spec,
    codegen,
)
from src.codegen.web import WebGenerator
from src.codegen.desktop import DesktopGenerator
from src.codegen.backend import BackendGenerator
from src.codegen.system import SystemGenerator
from src.codegen.kernel import KernelGenerator

__all__ = [
    "CodegenError",
    "CodegenResult",
    "parse_app_spec",
    "codegen",
    "WebGenerator",
    "DesktopGenerator",
    "BackendGenerator",
    "SystemGenerator",
    "KernelGenerator",
]
