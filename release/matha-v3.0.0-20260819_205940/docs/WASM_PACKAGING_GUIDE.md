# -*- coding: utf-8 -*-
"""Matha WASM 打包指南

本文档说明如何将 Matha 核心打包为 WebAssembly，
使移动应用和网页端可以直接在浏览器中运行 Matha 解释器。

## 方案对比

| 方案 | 难度 | 性能 | 生态 | 推荐度 |
|------|------|------|------|--------|
| Pyodide (CPython → WASM) | 低 | ⭐⭐ | 成熟 | ⭐⭐⭐⭐ |
| Cython → WASM | 中 | ⭐⭐⭐ | 有限 | ⭐⭐ |
| MicroPython → WASM | 低 | ⭐ | 精简 | ⭐⭐ |
| 自研 WASM 运行时 | 高 | ⭐⭐⭐⭐⭐ | 需自建 | ⭐ |

**推荐：Pyodide 方案** — 已有 Flutter 桥接框架，只需补充打包脚本。

## 方案 A：Pyodide 打包（推荐）

### 依赖清单

```
# 基础依赖
pyodide-build>=0.25.0      # WASM 构建工具
micropip>=0.5.0            # WASM 包管理
emscripten>=3.1.0          # WASM 编译器（通过 pyodide-build 自动下载）

# Matha 依赖
numpy>=1.24                # 数学计算（Pyodide 内置支持）
scipy>=1.10                # 科学计算（可选）
sympy>=1.12                # 符号计算（可选）

# 打包配置
webencodings               # 编码支持
```

### 步骤 1：创建 Matha WASM 包定义

```python
# matha_wasm/build_matha_wasm.py
"""将 Matha 打包为 Pyodide 包。"""
import os
import shutil
from pathlib import Path

BASE = Path(__file__).parent.parent
WASM_SRC = BASE / "matha_wasm"
WASM_SRC.mkdir(exist_ok=True)

# 创建 pyproject.toml
(WASM_SRC / "pyproject.toml").write_text("""
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "matha"
version = "2.4.0"
description = "Matha 自成长编程语言解释器"
requires-python = ">=3.8"
dependencies = [
    "numpy",
]

[tool.setuptools.packages.find]
where = ["src"]
""", encoding="utf-8")

# 复制 src 目录
src_dir = WASM_SRC / "src"
if src_dir.exists():
    shutil.rmtree(src_dir)
shutil.copytree(BASE / "src", src_dir, ignore=shutil.ignore_patterns(
    "__pycache__", "*.pyc", "hardware", "compiler"
))

# 创建 package.yaml（Pyodide 包描述）
(WASM_SRC / "package.yaml").write_text("""
source:
  path: .

requirements:
  python:
    - numpy

test:
  imports:
    - src
  scripts:
    - tests/test_wasm_smoke.py

about:
  homepage: https://github.com/example/matha
  license: MIT
""")

print(f"WASM 包定义已生成: {WASM_SRC}")
"""
```

### 步骤 2：运行打包

```bash
# 安装构建工具
pip install pyodide-build setuptools

# 生成包定义
python matha_wasm/build_matha_wasm.py

# 构建 WASM 包
cd matha_wasm
pyodide build --output dist/

# 打包为 zip（Pyodide 格式）
pyodide package build-pypi-package matha/
```

### 步骤 3：在 Flutter 中使用

```dart
// lib/pyodide/pyodide_bridge.dart (已存在，需补充 WASM 加载)
import 'package:pyodide_dart/pyodide_dart.dart';

class MathaWasmBridge {
  static const String WASM_URL = 'assets/matha-2.4.0-py3-none-any.whl';
  static PyodideInterface? _pyodide;

  static Future<bool> init() async {
    _pyodide = await PyodideDart.loadPyodide(options: PyodideOptions(
      indexUrl: 'https://cdn.jsdelivr.net/pyodide/v0.25.1/full/',
    ));

    // 加载 Matha 包
    await _pyodide!.loadPackage(WASM_URL);

    // 注册 Matha 模块
    await _pyodide!.runPythonAsync('''
      import src.interp as interp
      import src.parser as parser
      import src.lexer as lexer
    ''');

    return true;
  }

  static Future<dynamic> execute(String code) async {
    if (_pyodide == null) await init();
    return await _pyodide!.runPythonAsync(code);
  }
}
```

## 方案 B：MicroPython 精简版

适合资源受限设备，去掉 numpy/scipy 等重型依赖。

```bash
# 构建 MicroPython WASM
git clone https://github.com/micropython/micropython.git
cd micropython/mpw
./mpw.py package add matha
./mpw.py build wasm
```

## 依赖树（完整）

```
matha-wasm
├── 核心（必须）
│   ├── src/lexer.py         → tokenizer
│   ├── src/parser.py        → AST builder
│   ├── src/interp.py        → interpreter
│   └── src/tokens.py        → token types
├── 标准库（必须）
│   ├── src/stdlib/core.py   → print, len, range
│   └── src/result.py        → Ok/Err
├── 数学（推荐）
│   ├── numpy                → ndarray, 矩阵运算
│   └── math                 → sin, cos, sqrt
├── 领域（可选）
│   ├── src/domains/         → AI, 物理, 化学
│   └── scipy                → 高级科学计算
└── 工具（可选）
    ├── src/tools/perf_profiler.py
    └── src/codegen/         → 代码生成器
```

## 文件大小预估

| 组件 | 压缩后大小 |
|------|-----------|
| Pyodide 运行时 | ~15 MB |
| Matha 核心 | ~50 KB |
| numpy（精简） | ~5 MB |
| **总计（最小）** | **~15.1 MB** |
| **总计（完整）** | **~20 MB** |
"""