# Matha 大文件自举测试报告

生成时间: 2026-09-01 02:06:20

总计: 127 文件 | 通过: 83 | 失败: 44

## 总体统计

| 指标 | 数值 |
|------|------|
| 总文件数 | 127 |
| 通过 | 83 |
| 失败 | 44 |
| 通过率 | 65.4% |
| 总字符数 | 257,722 |
| 总行数 | 6,946 |

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
- 耗时: 1ms
- 错误: RuntimeError: 未定义变量 'source'

```matha
(无法读取源文件)
```

### examples\10_library_read.matha

- 状态: **RUNTIME_ERROR**
- 大小: 13 行, 374 字符
- 耗时: 30ms
- 错误: RuntimeError: 暂不支持求值: GlobalIdStmt

```matha
(无法读取源文件)
```

### firewall_rules.matha

- 状态: **PARSE_ERROR**
- 大小: 75 行, 4390 字符
- 耗时: 4ms
- 错误: ParseError at L51:18: 期望变量名或占位符 ？ (got LIT_STRING 'chr')

```matha
(无法读取源文件)
```

### interp.matha

- 状态: **PARSE_ERROR**
- 大小: 279 行, 11218 字符
- 耗时: 32ms
- 错误: ParseError at L165:12: 期望 { (got IDENTIFIER '求值')

```matha
(无法读取源文件)
```

### knowledge\chemistry\elements.matha

- 状态: **RUNTIME_ERROR**
- 大小: 21 行, 681 字符
- 耗时: 4ms
- 错误: TypeError: 'int' object is not iterable

```matha
(无法读取源文件)
```

### knowledge\cs\algorithms.matha

- 状态: **PARSE_ERROR**
- 大小: 33 行, 906 字符
- 耗时: 2ms
- 错误: ParseError at L14:37: 期望 { (got OP_COLON ':')

```matha
(无法读取源文件)
```

### knowledge\cs\data_structures.matha

- 状态: **PARSE_ERROR**
- 大小: 80 行, 2458 字符
- 耗时: 11ms
- 错误: ParseError at L10:5: 期望类型表达式 (got NEWLINE '\\n')

```matha
(无法读取源文件)
```

### knowledge\cs\discrete_math.matha

- 状态: **RUNTIME_ERROR**
- 大小: 72 行, 2090 字符
- 耗时: 12ms
- 错误: RuntimeError: 未定义函数 'check'

```matha
(无法读取源文件)
```

### resource\apps\education_news.matha

- 状态: **PARSE_ERROR**
- 大小: 118 行, 5010 字符
- 耗时: 11ms
- 错误: ParseError at L33:17: 期望 = (got PUNCT_LPAREN '(')

```matha
(无法读取源文件)
```

### resource\apps\lifestyle_math.matha

- 状态: **PARSE_ERROR**
- 大小: 114 行, 4673 字符
- 耗时: 10ms
- 错误: ParseError at L54:11: 期望 => (got KW_IF 'if')

```matha
(无法读取源文件)
```

### resource\apps\media_math.matha

- 状态: **PARSE_ERROR**
- 大小: 112 行, 4366 字符
- 耗时: 11ms
- 错误: ParseError at L105:17: 期望 = (got PUNCT_LPAREN '(')

```matha
(无法读取源文件)
```

### resource\apps\social_ecommerce.matha

- 状态: **PARSE_ERROR**
- 大小: 113 行, 4725 字符
- 耗时: 10ms
- 错误: ParseError at L21:16: 期望 = (got PUNCT_LPAREN '(')

```matha
(无法读取源文件)
```

### resource\cs\algorithms.matha

- 状态: **PARSE_ERROR**
- 大小: 59 行, 1662 字符
- 耗时: 5ms
- 错误: ParseError at L14:37: 期望 { (got OP_COLON ':')

```matha
(无法读取源文件)
```

### resource\cs\data_structures.matha

- 状态: **PARSE_ERROR**
- 大小: 45 行, 1432 字符
- 耗时: 3ms
- 错误: ParseError at L11:5: 期望 { (got NEWLINE '\\n')

```matha
(无法读取源文件)
```

### resource\cs\game_algorithms.matha

- 状态: **PARSE_ERROR**
- 大小: 74 行, 2958 字符
- 耗时: 7ms
- 错误: ParseError at L43:9: 期望变量名或占位符 ？ (got PUNCT_LPAREN '(')

```matha
(无法读取源文件)
```

### resource\cs\game_apps_math.matha

- 状态: **PARSE_ERROR**
- 大小: 130 行, 5260 字符
- 耗时: 14ms
- 错误: ParseError at L68:11: 期望 ( (got IDENTIFIER 'best_first')

```matha
(无法读取源文件)
```

### resource\cs\os_concepts.matha

- 状态: **PARSE_ERROR**
- 大小: 82 行, 3015 字符
- 耗时: 6ms
- 错误: ParseError at L11:9: 期望变量名或占位符 ？ (got PUNCT_LPAREN '(')

```matha
(无法读取源文件)
```

### resource\embedded\industrial_math.matha

- 状态: **PARSE_ERROR**
- 大小: 128 行, 4848 字符
- 耗时: 11ms
- 错误: ParseError at L74:16: 期望 = (got PUNCT_LPAREN '(')

```matha
(无法读取源文件)
```

### resource\finance\advanced.matha

- 状态: **PARSE_ERROR**
- 大小: 119 行, 4408 字符
- 耗时: 11ms
- 错误: ParseError at L25:5: 期望 { (got NEWLINE '\\n')

```matha
(无法读取源文件)
```

### resource\finance\math.matha

- 状态: **RUNTIME_ERROR**
- 大小: 51 行, 1628 字符
- 耗时: 6ms
- 错误: RuntimeError: 未定义函数 'npv'

```matha
(无法读取源文件)
```

### resource\hardware\embedded_math.matha

- 状态: **PARSE_ERROR**
- 大小: 104 行, 4253 字符
- 耗时: 6ms
- 错误: ParseError at L13:21: 期望 ) (got OP_COLON ':')

```matha
(无法读取源文件)
```

### resource\hardware\system_math.matha

- 状态: **PARSE_ERROR**
- 大小: 92 行, 3374 字符
- 耗时: 4ms
- 错误: ParseError at L13:17: 期望表达式 (got OP_ARROW '->')

```matha
(无法读取源文件)
```

### resource\linguistics\basics.matha

- 状态: **RUNTIME_ERROR**
- 大小: 25 行, 818 字符
- 耗时: 3ms
- 错误: RuntimeError: 未定义函数 'count'

```matha
(无法读取源文件)
```

### resource\logic\advanced_math.matha

- 状态: **PARSE_ERROR**
- 大小: 119 行, 4414 字符
- 耗时: 36ms
- 错误: ParseError at L10:18: 期望 = (got PUNCT_LPAREN '(')

```matha
(无法读取源文件)
```

### resource\logic\discrete_math.matha

- 状态: **PARSE_ERROR**
- 大小: 46 行, 1399 字符
- 耗时: 5ms
- 错误: ParseError at L17:21: 期望 ) (got IDENTIFIER 'q')

```matha
(无法读取源文件)
```

### resource\math\3d_transform.matha

- 状态: **PARSE_ERROR**
- 大小: 97 行, 4143 字符
- 耗时: 11ms
- 错误: ParseError at L15:5: 期望 { (got NEWLINE '\\n')

```matha
(无法读取源文件)
```

### resource\math\algebra_advanced.matha

- 状态: **PARSE_ERROR**
- 大小: 75 行, 2441 字符
- 耗时: 7ms
- 错误: ParseError at L20:5: 期望 { (got NEWLINE '\\n')

```matha
(无法读取源文件)
```

### resource\os\deadlock_sync_math.matha

- 状态: **PARSE_ERROR**
- 大小: 88 行, 3451 字符
- 耗时: 6ms
- 错误: ParseError at L23:16: 期望 = (got PUNCT_LPAREN '(')

```matha
(无法读取源文件)
```

### resource\os\filesystem_math.matha

- 状态: **PARSE_ERROR**
- 大小: 121 行, 4150 字符
- 耗时: 10ms
- 错误: ParseError at L83:5: 期望 { (got NEWLINE '\\n')

```matha
(无法读取源文件)
```

### resource\os\kernel_memory.matha

- 状态: **PARSE_ERROR**
- 大小: 76 行, 3832 字符
- 耗时: 6ms
- 错误: ParseError at L64:52: 期望 ) (got OP_PLUS '+')

```matha
(无法读取源文件)
```

### resource\os\kernel_process.matha

- 状态: **RUNTIME_ERROR**
- 大小: 69 行, 3452 字符
- 耗时: 8ms
- 错误: RuntimeError: 未定义函数 'μs'

```matha
(无法读取源文件)
```

### resource\os\kernel_syscall.matha

- 状态: **PARSE_ERROR**
- 大小: 120 行, 4783 字符
- 耗时: 6ms
- 错误: ParseError at L120:1: 期望 } (got EOF '')

```matha
(无法读取源文件)
```

### resource\os\memory_math.matha

- 状态: **PARSE_ERROR**
- 大小: 111 行, 4388 字符
- 耗时: 16ms
- 错误: ParseError at L31:5: 期望 { (got NEWLINE '\\n')

```matha
(无法读取源文件)
```

### resource\os\os_concepts_math.matha

- 状态: **PARSE_ERROR**
- 大小: 67 行, 2589 字符
- 耗时: 4ms
- 错误: ParseError at L11:10: 期望 ) (got KW_IN 'in')

```matha
(无法读取源文件)
```

### resource\os\process_math.matha

- 状态: **PARSE_ERROR**
- 大小: 107 行, 3923 字符
- 耗时: 20ms
- 错误: ParseError at L52:9: 期望变量名或占位符 ？ (got PUNCT_LPAREN '(')

```matha
(无法读取源文件)
```

### resource\os\scheduling_math.matha

- 状态: **PARSE_ERROR**
- 大小: 76 行, 3375 字符
- 耗时: 10ms
- 错误: ParseError at L11:17: 期望 = (got PUNCT_LPAREN '(')

```matha
(无法读取源文件)
```

### resource\platforms\emerging_math.matha

- 状态: **PARSE_ERROR**
- 大小: 103 行, 4289 字符
- 耗时: 14ms
- 错误: ParseError at L78:18: 期望 = (got PUNCT_LPAREN '(')

```matha
(无法读取源文件)
```

### resource\security\crypto_math.matha

- 状态: **PARSE_ERROR**
- 大小: 147 行, 5077 字符
- 耗时: 16ms
- 错误: ParseError at L60:18: 期望 = (got PUNCT_LPAREN '(')

```matha
(无法读取源文件)
```

### resource\statistics\analysis.matha

- 状态: **PARSE_ERROR**
- 大小: 109 行, 3575 字符
- 耗时: 18ms
- 错误: ParseError at L50:37: 期望 { (got OP_COLON ':')

```matha
(无法读取源文件)
```

### resource\statistics\probability.matha

- 状态: **RUNTIME_ERROR**
- 大小: 40 行, 1279 字符
- 耗时: 13ms
- 错误: TypeError: 'int' object is not iterable

```matha
(无法读取源文件)
```

### resource\tools\utility_math.matha

- 状态: **PARSE_ERROR**
- 大小: 149 行, 5039 字符
- 耗时: 13ms
- 错误: ParseError at L15:10: 期望 => (got PUNCT_COMMA ',')

```matha
(无法读取源文件)
```

### resource\web\network_math.matha

- 状态: **PARSE_ERROR**
- 大小: 97 行, 3218 字符
- 耗时: 6ms
- 错误: ParseError at L28:5: 期望 { (got NEWLINE '\\n')

```matha
(无法读取源文件)
```

### resource\web\web_math.matha

- 状态: **PARSE_ERROR**
- 大小: 138 行, 4974 字符
- 耗时: 14ms
- 错误: ParseError at L74:18: 期望 = (got PUNCT_LPAREN '(')

```matha
(无法读取源文件)
```

## 通过测试

- ✅ bootstrap_test_v2.matha (105L, 54ms)
- ✅ examples\01_arithmetic.matha (11L, 2ms)
- ✅ examples\02_functions.matha (14L, 5ms)
- ✅ examples\03_set_iter.matha (29L, 3ms)
- ✅ examples\05_sensor_read.matha (9L, 1ms)
- ✅ examples\06_main.matha (11L, 2ms)
- ✅ examples\06_sub.matha (10L, 2ms)
- ✅ examples\07_auto_debug.matha (10L, 8ms)
- ✅ examples\07_debug_sub.matha (8L, 1ms)
- ✅ examples\08_auto_optimize.matha (12L, 2ms)
- ✅ examples\08_optimize_sub.matha (11L, 1ms)
- ✅ examples\09_grow_sub.matha (11L, 1ms)
- ✅ examples\09_self_grow.matha (10L, 3ms)
- ✅ examples\10_library_sub.matha (12L, 4ms)
- ✅ examples\10_web_app.matha (19L, 1ms)
- ✅ examples\11_desktop.matha (25L, 4ms)
- ✅ examples\11_grow_sub.matha (10L, 3ms)
- ✅ examples\11_library_grow.matha (10L, 4ms)
- ✅ examples\12_backend.matha (16L, 3ms)
- ✅ examples\12_library_discipline.matha (13L, 5ms)
- ✅ examples\12_mech_sub.matha (10L, 17ms)
- ✅ examples\99_multiParam_boundary.matha (21L, 5ms)
- ✅ knowledge\biology\cell.matha (16L, 1ms)
- ✅ knowledge\biology\ecology_human.matha (23L, 2ms)
- ✅ knowledge\biology\genetics.matha (22L, 1ms)
- ✅ knowledge\chemistry\organic.matha (16L, 2ms)
- ✅ knowledge\chemistry\stoichiometry.matha (22L, 2ms)
- ✅ knowledge\cs\complexity.matha (20L, 2ms)
- ✅ knowledge\engineering\civil.matha (18L, 2ms)
- ✅ knowledge\engineering\electrical.matha (21L, 4ms)
- ✅ knowledge\engineering\mechanical.matha (21L, 3ms)
- ✅ knowledge\history\chronology.matha (32L, 5ms)
- ✅ knowledge\index.matha (52L, 2ms)
- ✅ knowledge\linguistics\grammar.matha (23L, 2ms)
- ✅ knowledge\math\algebra.matha (41L, 6ms)
- ✅ knowledge\math\arithmetic.matha (38L, 6ms)
- ✅ knowledge\math\calculus.matha (19L, 3ms)
- ✅ knowledge\math\geometry.matha (52L, 7ms)
- ✅ knowledge\math\logic.matha (19L, 3ms)
- ✅ knowledge\math\number_theory.matha (33L, 5ms)
- ✅ knowledge\math\statistics.matha (29L, 4ms)
- ✅ knowledge\math\trigonometry.matha (30L, 4ms)
- ✅ knowledge\physics\celestial.matha (18L, 2ms)
- ✅ knowledge\physics\electromagnetism.matha (23L, 3ms)
- ✅ knowledge\physics\mechanics.matha (27L, 4ms)
- ✅ knowledge\physics\optics.matha (20L, 3ms)
- ✅ knowledge\physics\quantum.matha (14L, 2ms)
- ✅ knowledge\physics\thermodynamics.matha (20L, 2ms)
- ✅ lexer.matha (215L, 45ms)
- ✅ library\core\arithmetic.matha (11L, 2ms)
- ✅ library\core\geometry.matha (9L, 2ms)
- ✅ library\core\trigonometry.matha (7L, 2ms)
- ✅ library\core\圆柱体积.matha (5L, 1ms)
- ✅ library\core\球体积.matha (5L, 2ms)
- ✅ library\core\计算球体积.matha (5L, 1ms)
- ✅ library\index.matha (16L, 1ms)
- ✅ library\mechanics\bearing.matha (8L, 3ms)
- ✅ library\mechanics\shaft.matha (8L, 2ms)
- ✅ library\mechanics\stress.matha (7L, 1ms)
- ✅ library\physics\mechanics.matha (9L, 2ms)
- ✅ library\structural\beam.matha (7L, 1ms)
- ✅ library\structural\column.matha (6L, 1ms)
- ✅ parser.matha (601L, 0ms)
- ✅ resource\biology\genetics.matha (29L, 3ms)
- ✅ resource\biology\molecular.matha (37L, 3ms)
- ✅ resource\chemistry\stoichiometry.matha (36L, 4ms)
- ✅ resource\engineering\civil.matha (34L, 3ms)
- ✅ resource\engineering\mechanical.matha (37L, 5ms)
- ✅ resource\extended\modeling_math.matha (83L, 9ms)
- ✅ resource\geography\info.matha (30L, 3ms)
- ✅ resource\index.matha (57L, 6ms)
- ✅ resource\math\conic_sections.matha (44L, 6ms)
- ✅ resource\math\exponent_logarithm.matha (26L, 3ms)
- ✅ resource\math\trigonometry_advanced.matha (38L, 7ms)
- ✅ resource\os\boot_sector.matha (97L, 7ms)
- ✅ resource\physics\electromagnetism.matha (43L, 8ms)
- ✅ resource\physics\optics.matha (34L, 8ms)
- ✅ resource\physics\quantum.matha (27L, 7ms)
- ✅ resource\physics\thermodynamics.matha (30L, 4ms)
- ✅ resource\航空航天\orbital_math.matha (67L, 9ms)
- ✅ shaft_sub.matha (11L, 2ms)
- ✅ template_new.matha (14L, 3ms)
- ✅ template_old.matha (15L, 2ms)

## 按目录统计

| 目录 | 通过 | 失败 | 总字符 |
|------|------|------|--------|
| . | 6 | 3 | 63,341 |
| examples | 21 | 2 | 9,592 |
| knowledge | 1 | 0 | 990 |
| knowledge\biology | 3 | 0 | 1,721 |
| knowledge\chemistry | 2 | 1 | 1,929 |
| knowledge\cs | 1 | 3 | 6,187 |
| knowledge\engineering | 3 | 0 | 2,127 |
| knowledge\history | 1 | 0 | 1,013 |
| knowledge\linguistics | 1 | 0 | 580 |
| knowledge\math | 8 | 0 | 8,935 |
| knowledge\physics | 6 | 0 | 4,158 |
| library | 1 | 0 | 357 |
| library\core | 6 | 0 | 1,714 |
| library\mechanics | 3 | 0 | 890 |
| library\physics | 1 | 0 | 458 |
| library\structural | 2 | 0 | 503 |
| resource | 1 | 0 | 2,098 |
| resource\apps | 0 | 4 | 18,774 |
| resource\biology | 2 | 0 | 2,049 |
| resource\chemistry | 1 | 0 | 1,311 |
| resource\cs | 0 | 5 | 14,327 |
| resource\embedded | 0 | 1 | 4,848 |
| resource\engineering | 2 | 0 | 2,455 |
| resource\extended | 1 | 0 | 3,053 |
| resource\finance | 0 | 2 | 6,036 |
| resource\geography | 1 | 0 | 1,115 |
| resource\hardware | 0 | 2 | 7,627 |
| resource\linguistics | 0 | 1 | 818 |
| resource\logic | 0 | 2 | 5,813 |
| resource\math | 3 | 2 | 10,586 |
| resource\os | 1 | 9 | 37,854 |
| resource\physics | 4 | 0 | 4,676 |
| resource\platforms | 0 | 1 | 4,289 |
| resource\security | 0 | 1 | 5,077 |
| resource\statistics | 0 | 2 | 4,854 |
| resource\tools | 0 | 1 | 5,039 |
| resource\web | 0 | 2 | 8,192 |
| resource\航空航天 | 1 | 0 | 2,336 |

## 错误类型统计

- **PARSE_ERROR**: 35
- **RUNTIME_ERROR**: 8
- **SKIPPED**: 1

