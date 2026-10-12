# 贡献指南

感谢您对 Matha 的贡献！本指南将帮助您开始。

## 快速开始

### 环境准备

```bash
# 克隆仓库
git clone https://github.com/zzk2025r/matha.git
cd matha

# 安装依赖
pip install -e .

# 运行测试
python test_full.py
```

### 代码结构

```
src/
├── domains/          # 领域模块（每个功能一个文件）
├── compiler/         # 编译器
├── lsp.py            # LSP 服务器
├── matha_main.py     # CLI 入口
├── matha_system.py   # 系统核心
├── virtual_code.py   # 虚拟代码引擎
└── __init__.py       # 导出
```

## 添加新领域模块

### 步骤 1：创建模块文件

在 `src/domains/` 下创建新文件，例如 `src/domains/my_module.py`：

```python
# -*- coding: utf-8 -*-
"""模块描述。"""
from __future__ import annotations
from typing import Any

class MyClass:
    """我的类。"""
    def __init__(self):
        self.value = 0

    def do_something(self) -> Any:
        """做某事。"""
        return self.value

def create_my_class() -> MyClass:
    """创建实例。"""
    return MyClass()

def _register_my_module(builtins: dict) -> None:
    """注册内置函数。"""
    builtins["创建我的类"] = create_my_class

def _my_module_symtab_names() -> list:
    return ["创建我的类"]
```

### 步骤 2：在 registry.py 中注册

```python
"MyModule": {
    "display_name": "我的模块",
    "description": "模块描述",
    "module": "src.domains.my_module",
    "functions": ["创建我的类"],
    "category": "engineering",
    "targets": ["python", "c"],
},
```

### 步骤 3：在 get_builtins() 中添加

```python
if mod and hasattr(mod, '_register_my_module'):
    reg = {}
    mod._register_my_module(reg)
    builtins.update(reg)
```

### 步骤 4：添加测试

```python
def test_my_module():
    from src.domains.my_module import MyClass
    obj = MyClass()
    assert obj.do_something() is not None
```

### 步骤 5：运行测试

```bash
python test_full.py
```

## 代码规范

### 类型注解

所有函数必须有类型注解：

```python
def add(a: int, b: int) -> int:
    return a + b
```

### 命名规范

- 类名：PascalCase
- 函数名：snake_case
- 变量名：snake_case
- 常量名：UPPER_CASE
- 中文函数名：使用动词+名词

### 文档字符串

```python
def my_function(param: str) -> str:
    """函数描述。
    
    Args:
        param: 参数描述
    
    Returns:
        返回值描述
    """
    return param.upper()
```

## 提交 PR

1. 创建分支
2. 编写代码和测试
3. 确保 `python test_full.py` 通过
4. 提交 PR 并描述变更

## 问题反馈

使用 GitHub Issues 报告问题，包含：
- Matha 版本
- Python 版本
- 复现步骤
- 期望行为 vs 实际行为

---

*Matha v4.5 | 贡献指南*