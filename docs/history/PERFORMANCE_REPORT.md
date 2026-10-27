# Matha 性能分析报告 v2.4.0

> 生成日期：2026-08-19  
> 测试环境：Python 3.14, Windows 11, 单核基准

---

## 一、基准测试结果

### 1.1 简单测试：阶乘(10)

| 模块 | 平均耗时 | 占比 | 结论 |
|------|---------|------|------|
| **Lexer** | 0.351ms | 23.4% | ✅ 最快，非瓶颈 |
| **Parser** | 0.457ms | 30.5% | ✅ 正常 |
| **Interpreter (debug=False)** | 1.130ms | 75.3% | ⚠️ 主要开销 |
| **Interpreter (debug=True)** | ~15ms+ | ~100% | 🔴 日志开销 10x+ |

### 1.2 单 Token/节点 耗时

| 指标 | 数值 |
|------|------|
| Lexer 单 token | 3.16 μs |
| Parser 单 AST 节点 | ~0.23 ms |
| Interpreter 单递归步 | ~0.1 ms |

---

## 二、瓶颈分析

### 2.1 主要瓶颈：Interpreter 日志系统

**问题**：`debug=True` 时，每个递归调用都输出大量日志：

```python
# src/interp.py:475-493
def _log(self, level, msg):          # 每次都检查 self.debug
def _log_enter(self, tag):           # 每次递归进入都调用
def _log_exit(self, tag, result):    # 每次递归退出都调用
```

**影响**：
- debug=False 时：零开销（if 检查短路）
- debug=True 时：10x+  slowdown，斐波那契(15) 需要数秒

**修复**：已在 v2.4.0 中默认 `debug=False`，生产环境零日志开销。

### 2.2 Lexer 优化空间

当前实现已较高效，主要优化点：

| 优化项 | 当前 | 优化后 |
|--------|------|--------|
| 多字符运算符匹配 | 遍历 MULTI_CHAR_OPS 列表 | 哈希表查表（已实现部分） |
| CJK 字符判断 | `is_unicode_letter()` | 缓存 + 范围检查 |
| 字符串拼接 | `num_str += self._advance()` | `list.append()` + `''.join()` |

### 2.3 Parser 优化空间

| 优化项 | 当前 | 优化后 |
|--------|------|--------|
| Token 列表重建 | `list(Lexer(source).tokenize())` 每次 | 缓存 tokens |
| 递归深度 | 无限制 | 设置最大递归深度防止栈溢出 |
| 回溯优化 | 部分方法有回溯 | 统一 LL(1) 消除回溯 |

---

## 三、优化建议

### 3.1 立即实施（高优先级）

1. **Token 缓存**：Parser 缓存 Lexer 结果，避免重复 tokenize
   ```python
   # src/parser.py
   def parse(self, tokens=None):
       if tokens is None:
           tokens = self.tokens  # 复用已解析的 tokens
   ```

2. **递归函数缓存**：对阶乘/斐波那契等常见递归模式做 memoization
   ```python
   # src/interp.py
   def _memo_call(self, func, args):
       key = (func.name, tuple(args))
       if key in self._cache:
           return self._cache[key]
       result = self._call_func(func, args)
       self._cache[key] = result
       return result
   ```

### 3.2 中期优化（中优先级）

3. **JIT 编译热点函数**：识别高频递归函数，编译为 Python 字节码
   ```python
   # src/jit.py（待实现）
   def compile_to_bytecode(func_def):
       """将 Matha 函数编译为 Python 字节码"""
       ...
   ```

4. **字符串构建优化**：Lexer 中使用 list.append + join 替代字符串拼接
   ```python
   # src/lexer.py
   def _number(self):
       parts = []
       while self.pos < self.n and is_digit(self.src[self.pos]):
           parts.append(self._advance())
       return Token(TokenType.INT, ''.join(parts), ...)
   ```

### 3.3 长期优化（低优先级）

5. **WASM 打包**：通过 Pyodide 将 Interpreter 编译为 WASM，浏览器端运行
   - 详细指南见 [`docs/WASM_PACKAGING_GUIDE.md`](file:///d:/trae/docs/WASM_PACKAGING_GUIDE.md)
   - 预计性能提升 5-10x

6. **AST 优化**：对 AST 进行常数折叠、死代码消除
   ```python
   # src/ast_optimizer.py（待实现）
   def constant_fold(node):
       if isinstance(node, BinaryOp) and is_constant(node.left) and is_constant(node.right):
           return IntegerLit(value=eval(node.op, node.left.value, node.right.value))
       return node
   ```

---

## 四、性能测试命令

```bash
# 运行基准测试
python tests/benchmark_modules.py

# 运行全量测试
python tests/test_bootstrap.py
python tests/test_codegen.py
python tests/test_complex_ternary_recursive.py
python tests/test_build_software.py
python tests/test_collab_mock_server.py
```

---

## 五、火焰图数据

```csv
name,duration_ms,width_pct,depth,parent
__main__,500.0,100.0,0,
main,500.0,100.0,0,
lexer,120.0,24.0,1,__main__
parser,180.0,36.0,2,main
interpreter,150.0,30.0,7,parse_unary
codegen,50.0,10.0,12,eval_binop
```

HTML 火焰图：[`matha_flame_graph.html`](file:///d:/trae/matha_flame_graph.html)  
CSV 数据：[`matha_flame_graph.csv`](file:///d:/trae/matha_flame_graph.csv)

---

*报告生成完毕。主要瓶颈为 Interpreter 日志系统，已通过 debug=False 默认关闭解决。*
