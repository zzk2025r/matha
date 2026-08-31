# Matha 大文件自举测试报告

生成时间: 2026-08-31 23:47:30

总计: 127 文件 | 通过: 82 | 失败: 45

## 总体统计

| 指标 | 数值 |
|------|------|
| 总文件数 | 127 |
| 通过 | 82 |
| 失败 | 45 |
| 通过率 | 64.6% |
| 总字符数 | 253,341 |
| 总行数 | 6,860 |

## 失败测试详情

### bootstrap_test.matha

- 状态: **SKIPPED**
- 大小: 279 行, 10977 字符
- 耗时: 0ms
- 错误: 旧版测试（已被 bootstrap_test_v2 替代）

```matha
(无法读取源文件)
```

### examples\04_pipeline.matha

- 状态: **RUNTIME_ERROR**
- 大小: 9 行, 285 字符
- 耗时: 2ms
- 错误: RuntimeError: 未定义变量 'source'

```matha
(无法读取源文件)
```

### examples\10_library_read.matha

- 状态: **RUNTIME_ERROR**
- 大小: 13 行, 374 字符
- 耗时: 32ms
- 错误: RuntimeError: 暂不支持求值: GlobalIdStmt

```matha
(无法读取源文件)
```

### firewall_rules.matha

- 状态: **PARSE_ERROR**
- 大小: 75 行, 4316 字符
- 耗时: 4ms
- 错误: ParseError at L51:18: 期望变量名或占位符 ？ (got LIT_STRING 'chr')

```matha
(无法读取源文件)
```

### interp.matha

- 状态: **PARSE_ERROR**
- 大小: 279 行, 11218 字符
- 耗时: 43ms
- 错误: ParseError at L165:12: 期望 { (got IDENTIFIER '求值')

```matha
(无法读取源文件)
```

### knowledge\chemistry\elements.matha

- 状态: **RUNTIME_ERROR**
- 大小: 21 行, 663 字符
- 耗时: 3ms
- 错误: TypeError: 'int' object is not iterable

```matha
(无法读取源文件)
```

### knowledge\cs\algorithms.matha

- 状态: **RUNTIME_ERROR**
- 大小: 36 行, 897 字符
- 耗时: 4ms
- 错误: RuntimeError: 未定义函数 'search'

```matha
(无法读取源文件)
```

### knowledge\cs\data_structures.matha

- 状态: **PARSE_ERROR**
- 大小: 80 行, 2387 字符
- 耗时: 7ms
- 错误: ParseError at L10:5: 期望类型表达式 (got NEWLINE '\\n')

```matha
(无法读取源文件)
```

### knowledge\cs\discrete_math.matha

- 状态: **PARSE_ERROR**
- 大小: 72 行, 1979 字符
- 耗时: 6ms
- 错误: ParseError at L27:13: 期望 参数名 (got OP_PIPE '|')

```matha
(无法读取源文件)
```

### resource\apps\education_news.matha

- 状态: **PARSE_ERROR**
- 大小: 111 行, 4934 字符
- 耗时: 18ms
- 错误: ParseError at L33:17: 期望 = (got PUNCT_LPAREN '(')

```matha
(无法读取源文件)
```

### resource\apps\lifestyle_math.matha

- 状态: **PARSE_ERROR**
- 大小: 113 行, 4546 字符
- 耗时: 15ms
- 错误: ParseError at L54:7: 期望表达式 (got PUNCT_UNDERSCORE '_')

```matha
(无法读取源文件)
```

### resource\apps\media_math.matha

- 状态: **PARSE_ERROR**
- 大小: 111 行, 4343 字符
- 耗时: 16ms
- 错误: ParseError at L105:17: 期望 = (got PUNCT_LPAREN '(')

```matha
(无法读取源文件)
```

### resource\apps\social_ecommerce.matha

- 状态: **PARSE_ERROR**
- 大小: 107 行, 4672 字符
- 耗时: 14ms
- 错误: ParseError at L21:16: 期望 = (got PUNCT_LPAREN '(')

```matha
(无法读取源文件)
```

### resource\biology\molecular.matha

- 状态: **PARSE_ERROR**
- 大小: 36 行, 1104 字符
- 耗时: 3ms
- 错误: ParseError at L16:13: 期望表达式 (got OP_ARROW '->')

```matha
(无法读取源文件)
```

### resource\cs\algorithms.matha

- 状态: **PARSE_ERROR**
- 大小: 58 行, 1639 字符
- 耗时: 5ms
- 错误: ParseError at L14:37: 期望 { (got OP_COLON ':')

```matha
(无法读取源文件)
```

### resource\cs\data_structures.matha

- 状态: **PARSE_ERROR**
- 大小: 44 行, 1307 字符
- 耗时: 4ms
- 错误: ParseError at L10:22: 期望 { (got OP_COLON ':')

```matha
(无法读取源文件)
```

### resource\cs\game_algorithms.matha

- 状态: **PARSE_ERROR**
- 大小: 72 行, 2851 字符
- 耗时: 14ms
- 错误: ParseError at L43:27: 期望表达式 (got OP_ARROW '->')

```matha
(无法读取源文件)
```

### resource\cs\game_apps_math.matha

- 状态: **PARSE_ERROR**
- 大小: 129 行, 5113 字符
- 耗时: 18ms
- 错误: ParseError at L68:11: 期望 ( (got IDENTIFIER 'best_first')

```matha
(无法读取源文件)
```

### resource\cs\os_concepts.matha

- 状态: **PARSE_ERROR**
- 大小: 78 行, 2874 字符
- 耗时: 7ms
- 错误: ParseError at L11:30: 期望表达式 (got OP_ARROW '->')

```matha
(无法读取源文件)
```

### resource\embedded\industrial_math.matha

- 状态: **PARSE_ERROR**
- 大小: 127 行, 4825 字符
- 耗时: 15ms
- 错误: ParseError at L74:16: 期望 = (got PUNCT_LPAREN '(')

```matha
(无法读取源文件)
```

### resource\engineering\civil.matha

- 状态: **PARSE_ERROR**
- 大小: 33 行, 1062 字符
- 耗时: 3ms
- 错误: ParseError at L25:18: 期望表达式 (got OP_ARROW '->')

```matha
(无法读取源文件)
```

### resource\finance\advanced.matha

- 状态: **PARSE_ERROR**
- 大小: 114 行, 4276 字符
- 耗时: 16ms
- 错误: ParseError at L24:22: 期望 { (got OP_COLON ':')

```matha
(无法读取源文件)
```

### resource\finance\math.matha

- 状态: **PARSE_ERROR**
- 大小: 51 行, 1631 字符
- 耗时: 6ms
- 错误: ParseError at L38:16: 期望 = (got PUNCT_LPAREN '(')

```matha
(无法读取源文件)
```

### resource\hardware\embedded_math.matha

- 状态: **PARSE_ERROR**
- 大小: 104 行, 4150 字符
- 耗时: 6ms
- 错误: ParseError at L13:21: 期望 ) (got OP_COLON ':')

```matha
(无法读取源文件)
```

### resource\hardware\system_math.matha

- 状态: **PARSE_ERROR**
- 大小: 92 行, 3283 字符
- 耗时: 11ms
- 错误: ParseError at L13:17: 期望表达式 (got OP_ARROW '->')

```matha
(无法读取源文件)
```

### resource\linguistics\basics.matha

- 状态: **PARSE_ERROR**
- 大小: 25 行, 821 字符
- 耗时: 6ms
- 错误: ParseError at L19:18: 期望 = (got PUNCT_LPAREN '(')

```matha
(无法读取源文件)
```

### resource\logic\advanced_math.matha

- 状态: **PARSE_ERROR**
- 大小: 111 行, 4196 字符
- 耗时: 10ms
- 错误: ParseError at L10:18: 期望 = (got PUNCT_LPAREN '(')

```matha
(无法读取源文件)
```

### resource\math\3d_transform.matha

- 状态: **PARSE_ERROR**
- 大小: 95 行, 4104 字符
- 耗时: 17ms
- 错误: ParseError at L72:43: 期望 属性名 (got LIT_INTEGER '1')

```matha
(无法读取源文件)
```

### resource\math\algebra_advanced.matha

- 状态: **PARSE_ERROR**
- 大小: 73 行, 2412 字符
- 耗时: 10ms
- 错误: ParseError at L10:17: 期望 = (got PUNCT_LPAREN '(')

```matha
(无法读取源文件)
```

### resource\os\deadlock_sync_math.matha

- 状态: **PARSE_ERROR**
- 大小: 84 行, 3342 字符
- 耗时: 6ms
- 错误: ParseError at L23:16: 期望 = (got PUNCT_LPAREN '(')

```matha
(无法读取源文件)
```

### resource\os\filesystem_math.matha

- 状态: **PARSE_ERROR**
- 大小: 118 行, 4064 字符
- 耗时: 10ms
- 错误: ParseError at L82:23: 期望 { (got OP_COLON ':')

```matha
(无法读取源文件)
```

### resource\os\kernel_memory.matha

- 状态: **PARSE_ERROR**
- 大小: 76 行, 3757 字符
- 耗时: 7ms
- 错误: ParseError at L64:52: 期望 ) (got OP_PLUS '+')

```matha
(无法读取源文件)
```

### resource\os\kernel_process.matha

- 状态: **PARSE_ERROR**
- 大小: 69 行, 3386 字符
- 耗时: 5ms
- 错误: ParseError at L64:23: 期望表达式 (got PUNCT_UNDERSCORE '_')

```matha
(无法读取源文件)
```

### resource\os\kernel_syscall.matha

- 状态: **PARSE_ERROR**
- 大小: 121 行, 4762 字符
- 耗时: 9ms
- 错误: ParseError at L23:19: 期望表达式 (got OP_ARROW '->')

```matha
(无法读取源文件)
```

### resource\os\memory_math.matha

- 状态: **PARSE_ERROR**
- 大小: 106 行, 4256 字符
- 耗时: 12ms
- 错误: ParseError at L30:15: 期望 { (got OP_COLON ':')

```matha
(无法读取源文件)
```

### resource\os\os_concepts_math.matha

- 状态: **PARSE_ERROR**
- 大小: 67 行, 2518 字符
- 耗时: 5ms
- 错误: ParseError at L11:10: 期望 ) (got KW_IN 'in')

```matha
(无法读取源文件)
```

### resource\os\process_math.matha

- 状态: **PARSE_ERROR**
- 大小: 105 行, 3852 字符
- 耗时: 15ms
- 错误: ParseError at L34:16: 期望 = (got PUNCT_LPAREN '(')

```matha
(无法读取源文件)
```

### resource\os\scheduling_math.matha

- 状态: **PARSE_ERROR**
- 大小: 73 行, 3323 字符
- 耗时: 10ms
- 错误: ParseError at L11:17: 期望 = (got PUNCT_LPAREN '(')

```matha
(无法读取源文件)
```

### resource\platforms\emerging_math.matha

- 状态: **PARSE_ERROR**
- 大小: 100 行, 4236 字符
- 耗时: 7ms
- 错误: ParseError at L22:15: 期望表达式 (got OP_ARROW '->')

```matha
(无法读取源文件)
```

### resource\security\crypto_math.matha

- 状态: **PARSE_ERROR**
- 大小: 142 行, 4992 字符
- 耗时: 12ms
- 错误: ParseError at L11:15: 期望表达式 (got OP_ARROW '->')

```matha
(无法读取源文件)
```

### resource\statistics\analysis.matha

- 状态: **PARSE_ERROR**
- 大小: 102 行, 3516 字符
- 耗时: 13ms
- 错误: ParseError at L11:14: 期望 = (got PUNCT_LPAREN '(')

```matha
(无法读取源文件)
```

### resource\statistics\probability.matha

- 状态: **PARSE_ERROR**
- 大小: 39 行, 1284 字符
- 耗时: 3ms
- 错误: ParseError at L14:17: 期望 ) (got OP_PIPE '|')

```matha
(无法读取源文件)
```

### resource\tools\utility_math.matha

- 状态: **PARSE_ERROR**
- 大小: 141 行, 4916 字符
- 耗时: 14ms
- 错误: ParseError at L14:11: 期望表达式 (got OP_ARROW '->')

```matha
(无法读取源文件)
```

### resource\web\network_math.matha

- 状态: **PARSE_ERROR**
- 大小: 96 行, 3178 字符
- 耗时: 8ms
- 错误: ParseError at L27:25: 期望 { (got OP_COLON ':')

```matha
(无法读取源文件)
```

### resource\web\web_math.matha

- 状态: **PARSE_ERROR**
- 大小: 134 行, 4866 字符
- 耗时: 9ms
- 错误: ParseError at L11:13: 期望表达式 (got OP_ARROW '->')

```matha
(无法读取源文件)
```

## 通过测试

- ✅ bootstrap_test_v2.matha (105L, 66ms)
- ✅ examples\01_arithmetic.matha (11L, 2ms)
- ✅ examples\02_functions.matha (14L, 3ms)
- ✅ examples\03_set_iter.matha (29L, 7ms)
- ✅ examples\05_sensor_read.matha (9L, 2ms)
- ✅ examples\06_main.matha (11L, 2ms)
- ✅ examples\06_sub.matha (10L, 2ms)
- ✅ examples\07_auto_debug.matha (10L, 7ms)
- ✅ examples\07_debug_sub.matha (8L, 1ms)
- ✅ examples\08_auto_optimize.matha (12L, 3ms)
- ✅ examples\08_optimize_sub.matha (11L, 1ms)
- ✅ examples\09_grow_sub.matha (11L, 2ms)
- ✅ examples\09_self_grow.matha (10L, 3ms)
- ✅ examples\10_library_sub.matha (12L, 7ms)
- ✅ examples\10_web_app.matha (19L, 1ms)
- ✅ examples\11_desktop.matha (25L, 3ms)
- ✅ examples\11_grow_sub.matha (10L, 10ms)
- ✅ examples\11_library_grow.matha (10L, 4ms)
- ✅ examples\12_backend.matha (16L, 1ms)
- ✅ examples\12_library_discipline.matha (13L, 8ms)
- ✅ examples\12_mech_sub.matha (10L, 6ms)
- ✅ examples\99_multiParam_boundary.matha (21L, 9ms)
- ✅ knowledge\biology\cell.matha (16L, 1ms)
- ✅ knowledge\biology\ecology_human.matha (23L, 3ms)
- ✅ knowledge\biology\genetics.matha (22L, 2ms)
- ✅ knowledge\chemistry\organic.matha (16L, 2ms)
- ✅ knowledge\chemistry\stoichiometry.matha (22L, 2ms)
- ✅ knowledge\cs\complexity.matha (20L, 3ms)
- ✅ knowledge\engineering\civil.matha (18L, 2ms)
- ✅ knowledge\engineering\electrical.matha (21L, 4ms)
- ✅ knowledge\engineering\mechanical.matha (21L, 4ms)
- ✅ knowledge\history\chronology.matha (32L, 11ms)
- ✅ knowledge\index.matha (52L, 2ms)
- ✅ knowledge\linguistics\grammar.matha (23L, 2ms)
- ✅ knowledge\math\algebra.matha (41L, 7ms)
- ✅ knowledge\math\arithmetic.matha (38L, 11ms)
- ✅ knowledge\math\calculus.matha (19L, 4ms)
- ✅ knowledge\math\geometry.matha (52L, 12ms)
- ✅ knowledge\math\logic.matha (19L, 4ms)
- ✅ knowledge\math\number_theory.matha (33L, 9ms)
- ✅ knowledge\math\statistics.matha (29L, 7ms)
- ✅ knowledge\math\trigonometry.matha (30L, 7ms)
- ✅ knowledge\physics\celestial.matha (18L, 2ms)
- ✅ knowledge\physics\electromagnetism.matha (23L, 4ms)
- ✅ knowledge\physics\mechanics.matha (27L, 5ms)
- ✅ knowledge\physics\optics.matha (20L, 2ms)
- ✅ knowledge\physics\quantum.matha (14L, 2ms)
- ✅ knowledge\physics\thermodynamics.matha (20L, 8ms)
- ✅ lexer.matha (215L, 51ms)
- ✅ library\core\arithmetic.matha (11L, 7ms)
- ✅ library\core\geometry.matha (9L, 2ms)
- ✅ library\core\trigonometry.matha (7L, 3ms)
- ✅ library\core\圆柱体积.matha (5L, 1ms)
- ✅ library\core\球体积.matha (5L, 2ms)
- ✅ library\core\计算球体积.matha (5L, 1ms)
- ✅ library\index.matha (16L, 1ms)
- ✅ library\mechanics\bearing.matha (8L, 2ms)
- ✅ library\mechanics\shaft.matha (8L, 2ms)
- ✅ library\mechanics\stress.matha (7L, 2ms)
- ✅ library\physics\mechanics.matha (9L, 7ms)
- ✅ library\structural\beam.matha (7L, 3ms)
- ✅ library\structural\column.matha (6L, 1ms)
- ✅ parser.matha (601L, 0ms)
- ✅ resource\biology\genetics.matha (29L, 8ms)
- ✅ resource\chemistry\stoichiometry.matha (36L, 5ms)
- ✅ resource\engineering\mechanical.matha (37L, 11ms)
- ✅ resource\extended\modeling_math.matha (83L, 12ms)
- ✅ resource\geography\info.matha (30L, 7ms)
- ✅ resource\index.matha (57L, 5ms)
- ✅ resource\logic\discrete_math.matha (46L, 6ms)
- ✅ resource\math\conic_sections.matha (44L, 11ms)
- ✅ resource\math\exponent_logarithm.matha (26L, 3ms)
- ✅ resource\math\trigonometry_advanced.matha (38L, 6ms)
- ✅ resource\os\boot_sector.matha (97L, 6ms)
- ✅ resource\physics\electromagnetism.matha (43L, 6ms)
- ✅ resource\physics\optics.matha (34L, 6ms)
- ✅ resource\physics\quantum.matha (27L, 4ms)
- ✅ resource\physics\thermodynamics.matha (30L, 9ms)
- ✅ resource\航空航天\orbital_math.matha (67L, 9ms)
- ✅ shaft_sub.matha (11L, 2ms)
- ✅ template_new.matha (14L, 3ms)
- ✅ template_old.matha (15L, 2ms)

## 按目录统计

| 目录 | 通过 | 失败 | 总字符 |
|------|------|------|--------|
| . | 6 | 3 | 63,145 |
| examples | 21 | 2 | 9,572 |
| knowledge | 1 | 0 | 990 |
| knowledge\biology | 3 | 0 | 1,663 |
| knowledge\chemistry | 2 | 1 | 1,875 |
| knowledge\cs | 1 | 3 | 5,977 |
| knowledge\engineering | 3 | 0 | 2,070 |
| knowledge\history | 1 | 0 | 982 |
| knowledge\linguistics | 1 | 0 | 558 |
| knowledge\math | 8 | 0 | 8,682 |
| knowledge\physics | 6 | 0 | 4,042 |
| library | 1 | 0 | 357 |
| library\core | 6 | 0 | 1,714 |
| library\mechanics | 3 | 0 | 890 |
| library\physics | 1 | 0 | 458 |
| library\structural | 2 | 0 | 503 |
| resource | 1 | 0 | 2,098 |
| resource\apps | 0 | 4 | 18,495 |
| resource\biology | 1 | 1 | 2,002 |
| resource\chemistry | 1 | 0 | 1,276 |
| resource\cs | 0 | 5 | 13,784 |
| resource\embedded | 0 | 1 | 4,825 |
| resource\engineering | 1 | 1 | 2,404 |
| resource\extended | 1 | 0 | 2,971 |
| resource\finance | 0 | 2 | 5,907 |
| resource\geography | 1 | 0 | 1,086 |
| resource\hardware | 0 | 2 | 7,433 |
| resource\linguistics | 0 | 1 | 821 |
| resource\logic | 1 | 1 | 5,469 |
| resource\math | 3 | 2 | 10,413 |
| resource\os | 1 | 9 | 37,075 |
| resource\physics | 4 | 0 | 4,546 |
| resource\platforms | 0 | 1 | 4,236 |
| resource\security | 0 | 1 | 4,992 |
| resource\statistics | 0 | 2 | 4,800 |
| resource\tools | 0 | 1 | 4,916 |
| resource\web | 0 | 2 | 8,044 |
| resource\航空航天 | 1 | 0 | 2,270 |

## 错误类型统计

- **PARSE_ERROR**: 40
- **RUNTIME_ERROR**: 4
- **SKIPPED**: 1

