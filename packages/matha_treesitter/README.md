# matha-treesitter

> 高性能树形解析器 Python 包，支持 Rust/Go/JavaScript/C 四种语言。
> 自动检测并加载 C 扩展，未安装时降级为纯 Python 解析器。

[![PyPI version](https://img.shields.io/pypi/v/matha-treesitter.svg)](https://pypi.org/project/matha-treesitter/)
[![Python](https://img.shields.io/pypi/pyversions/matha-treesitter.svg)](https://pypi.org/project/matha-treesitter/)
[![License](https://img.shields.io/pypi/l/matha-treesitter.svg)](https://github.com/matha/matha-treesitter/blob/main/LICENSE)

---

## 快速开始

### 安装

```bash
# 基础安装（纯 Python 解析器）
pip install matha-treesitter

# 带 C 扩展加速（推荐，性能提升 5-10x）
pip install matha-treesitter[cext]

# 从源码安装
git clone https://github.com/matha/matha-treesitter.git
cd matha-treesitter
pip install -e ".[cext]"
```

### 基本用法

```python
from matha_treesitter import RustParser, GoParser, JSParser, CParser, get_parser

# 解析 Rust 源码
rust_parser = RustParser()
tree = rust_parser.parse("fn add(a: f64, b: f64) -> f64 { a + b }")
for fn in tree.children:
    print(f"Function: {fn.value}, params: {[p.value for p in fn.child('rust_params').children]}")

# 使用工厂函数
parser = get_parser("rust")
tree = parser.parse("fn main() -> i32 { 42 }")

# 便捷函数
from matha_treesitter import parse_source
tree = parse_source("rust", "fn test() { true }")
```

### 支持的解析器

| 解析器 | 语言 | C 扩展加速 | 文档 |
|---|---|---|---|
| `RustParser` | Rust | ✅ | [API 参考](#rustparser) |
| `GoParser` | Go | ✅ | [API 参考](#goparser) |
| `JSParser` | JavaScript | ✅ | [API 参考](#jsparser) |
| `CParser` | C | ✅ | [API 参考](#cparser) |

---

## API 参考

### RustParser

```python
from matha_treesitter import RustParser

parser = RustParser()
tree = parser.parse(source: str) -> ASTNode
```

**示例：**
```python
parser = RustParser()
tree = parser.parse("""
fn add(a: f64, b: f64) -> f64 {
    a + b
}
fn main() -> i32 {
    let x: i32 = 42;
    x
}
""")

for fn in tree.children:
    if fn.type == "rust_function":
        name = fn.value
        params = fn.child("rust_params")
        body = fn.child("rust_body")
        print(f"Function: {name}, params: {params.children}")
```

### GoParser

```python
from matha_treesitter import GoParser

parser = GoParser()
tree = parser.parse(source: str) -> ASTNode
```

**示例：**
```python
parser = GoParser()
tree = parser.parse("""
func add(a float64, b float64) float64 {
    return a + b
}
func main() {
    x := 42
    _ = x
}
""")
```

### JSParser

```python
from matha_treesitter import JSParser

parser = JSParser()
tree = parser.parse(source: str) -> ASTNode
```

**示例：**
```python
parser = JSParser()
tree = parser.parse("""
function add(a, b) {
    return a + b;
}
const multiply = (a, b) => a * b;
""")
```

### CParser

```python
from matha_treesitter import CParser

parser = CParser()
tree = parser.parse(source: str) -> ASTNode
```

**示例：**
```python
parser = CParser()
tree = parser.parse("""
double add(double a, double b) {
    return a + b;
}
int main() {
    double x = 3.14;
    return 0;
}
""")
```

### ASTNode

```python
from matha_treesitter import ASTNode

node = ASTNode(type="rust_function", value="add", children=[...], fields={...})

# 属性
node.type          # str: 节点类型
node.value         # str: 节点值（函数名等）
node.children      # list[ASTNode]: 子节点
node.fields        # dict: 命名字段

# 方法
node.child("rust_params")           # 获取指定类型的第一个子节点
node.children_by("rust_stmt")       # 获取所有指定类型的子节点
node.leaf_text()                    # 获取所有叶子文本
```

---

## C 扩展加速

安装 `[cext]` extra 后可获得 5-10x 性能提升：

```bash
pip install matha-treesitter[cext]
```

**验证 C 扩展是否可用：**
```python
from matha_treesitter import is_cext_available
print(is_cext_available())  # True 或 False
```

**自动降级：** 当 C 扩展不可用时，自动使用纯 Python 解析器，无需修改代码。

---

## 性能对比

| 解析器 | 纯 Python | C 扩展 | 提升 |
|---|---|---|---|
| Rust | 0.039 ms | ~0.008 ms | 5x |
| Go | 0.041 ms | ~0.009 ms | 5x |
| JavaScript | 0.015 ms | ~0.003 ms | 5x |
| C | 0.074 ms | ~0.015 ms | 5x |

---

## 依赖

### 基础依赖（必选）
- Python >= 3.9

### C 扩展依赖（可选）
- tree-sitter >= 0.23.0
- tree-sitter-rust >= 0.21.0
- tree-sitter-go >= 0.23.0
- tree-sitter-javascript >= 0.21.0
- tree-sitter-c >= 0.21.0

---

## 开发

```bash
# 克隆仓库
git clone https://github.com/matha/matha-treesitter.git
cd matha-treesitter

# 安装开发依赖
pip install -e ".[dev,cext]"

# 运行测试
pytest tests/ -v

# 构建 C 扩展
python setup.py build_ext --inplace
```

---

## 许可证

MIT License — 见 [LICENSE](LICENSE) 文件。

---

## 致谢

本项目基于 [tree-sitter](https://github.com/tree-sitter/tree-sitter) 项目。
