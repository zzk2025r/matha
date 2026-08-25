# Matha 性能优化总结

## 已实施的优化

### 1. Lexer 单字符映射表模块级缓存 ([src/lexer.py](file:///D:/trae/src/lexer.py))
- 将 `_single_char()` 内的 ~100 项 dict 提升为模块级常量 `_SINGLE_CHAR_MAP`
- 新增 `_RADIX_VALID` 和 `_ESCAPE_MAP` 模块级常量
- **效果**: 消除每次调用重建 dict 的开销（cProfile 显示 30000 calls → 0）

### 2. SemanticAnalyzer 内建符号表缓存 ([src/semantic.py](file:///D:/trae/src/semantic.py))
- 新增 `_build_builtin_symtab()` 模块级函数，在模块加载时一次性构建
- `SemanticAnalyzer.__init__` 直接复用缓存的 symbols dict
- 新增 `analyze_ast()` 避免双重解析

### 3. Interpreter 内建符号表缓存 ([src/interp.py](file:///D:/trae/src/interp.py))
- 新增 `_build_domain_builtins()` 模块级函数，缓存所有领域内建符号
- 新增模块级 `_curry_module()` 解决循环依赖
- `_DOMAIN_BUILTINS` 延迟初始化（在 Interpreter 类定义之后）
- 删除重复的 `_b_gen_game` / `_b_gen_model3d` 方法定义（2处冗余）
- `import json` 提升到模块级

### 4. 测试双重解析修复
- `test_ternary_arithmetic.py`, `test_parser_boundaries.py`, `test_parser_perf.py`:
  改用 `analyze_ast(p)` 替代 `analyze_source(src)`

## 剩余潜在优化点（未实施，供后续参考）

| 优先级 | 位置 | 问题 | 建议 | 预期收益 |
|---|---|---|---|---|
| 中 | [src/lexer.py:388-410](file:///D:/trae/src/lexer.py#L388-L410) | `_number` 中 `num_str +=` 字符串拼接 | 改用 `list.append()` + `''.join()` | 长数字字面量 ~2x |
| 中 | [src/lexer.py:432-441](file:///D:/trae/src/lexer.py#L432-L441) | `_string` 中 `result +=` 字符串拼接 | 同上 | 长字符串 ~2x |
| 中 | [src/lexer.py:422-424](file:///D:/trae/src/lexer.py#L422-L424) | `_radix_literal` 中 `digits +=` 拼接 | 同上 | 进制字面量 ~2x |
| 低 | [src/mathlib.py:133-136](file:///D:/trae/src/mathlib.py#L133-L136) | 集合运算重复 `sorted(set(...))` | 移除 `sorted()` 若不需要排序 | 微优化 |
| 低 | [src/parser.py:47](file:///D:/trae/src/parser.py#L47) | 全量 token 列表物化 | 改为 iterator（惰性求值） | 大文件内存优化 |

## 性能对比

| 场景 | 优化前 avg | 优化后 avg | 提升 |
|---|---|---|---|
| 1行赋值 | 4.35ms | **0.06ms** | **72x** |
| 10行赋值 | 6.74ms | **0.50ms** | **13.5x** |
| 100行赋值 | 29.25ms | **5.36ms** | **5.5x** |
| 10步链式 | 8.59ms | **0.61ms** | **14.1x** |
| 50步链式 | 26.94ms | **3.28ms** | **8.2x** |
| Small 全量 | 6.40ms | **4.02ms** | **1.6x** |
| Medium 全量 | 5.98ms | **4.85ms** | **1.2x** |
| Large 全量 | 8.44ms | **7.74ms** | **1.1x** |

## 测试结果

- **全量回归**: 51/51 通过 ✓
- **性能基准**: 4/4 通过 ✓（median < 10ms, avg < 15ms）
- **零新增失败**
