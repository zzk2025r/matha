# Matha 大文件自举测试报告

生成时间: 2026-08-31 15:35:56

总计: 127 文件 | 通过: 62 | 失败: 65

## 总体统计

| 指标 | 数值 |
|------|------|
| 总文件数 | 127 |
| 通过 | 62 |
| 失败 | 65 |
| 通过率 | 48.8% |
| 总字符数 | 251,246 |
| 总行数 | 6,922 |

## 失败测试详情

### bootstrap_test.matha

- 状态: **SKIPPED**
- 大小: 279 行, 10977 字符
- 耗时: 0ms
- 错误: 旧版测试（已被 bootstrap_test_v2 替代）

```matha
(无法读取源文件)
```

### examples\01_arithmetic.matha

- 状态: **RUNTIME_ERROR**
- 大小: 11 行, 230 字符
- 耗时: 1ms
- 错误: RuntimeError: 未定义变量 'b'

```matha
(无法读取源文件)
```

### examples\02_functions.matha

- 状态: **PARSE_ERROR**
- 大小: 14 行, 334 字符
- 耗时: 2ms
- 错误: ParseError at L7:33: 期望表达式 (got OP_FATARROW '=>')

```matha
(无法读取源文件)
```

### examples\03_set_iter.matha

- 状态: **RUNTIME_ERROR**
- 大小: 29 行, 442 字符
- 耗时: 3ms
- 错误: RuntimeError: 未定义变量 'end'

```matha
(无法读取源文件)
```

### examples\06_main.matha

- 状态: **RUNTIME_ERROR**
- 大小: 11 行, 313 字符
- 耗时: 1ms
- 错误: RuntimeError: 未定义变量 'y'

```matha
(无法读取源文件)
```

### examples\06_sub.matha

- 状态: **RUNTIME_ERROR**
- 大小: 10 行, 216 字符
- 耗时: 1ms
- 错误: RuntimeError: 未定义变量 '数量'

```matha
(无法读取源文件)
```

### examples\07_auto_debug.matha

- 状态: **RUNTIME_ERROR**
- 大小: 10 行, 391 字符
- 耗时: 1ms
- 错误: RuntimeError: 未定义变量 '最大尝试'

```matha
(无法读取源文件)
```

### examples\09_self_grow.matha

- 状态: **RUNTIME_ERROR**
- 大小: 10 行, 421 字符
- 耗时: 1ms
- 错误: RuntimeError: 未定义变量 '描述'

```matha
(无法读取源文件)
```

### examples\10_library_read.matha

- 状态: **RUNTIME_ERROR**
- 大小: 13 行, 374 字符
- 耗时: 25ms
- 错误: RuntimeError: 暂不支持求值: GlobalIdStmt

```matha
(无法读取源文件)
```

### examples\10_library_sub.matha

- 状态: **RUNTIME_ERROR**
- 大小: 12 行, 260 字符
- 耗时: 1ms
- 错误: RuntimeError: 未定义变量 'b'

```matha
(无法读取源文件)
```

### examples\11_library_grow.matha

- 状态: **RUNTIME_ERROR**
- 大小: 10 行, 374 字符
- 耗时: 1ms
- 错误: RuntimeError: 未定义变量 '学科'

```matha
(无法读取源文件)
```

### examples\12_library_discipline.matha

- 状态: **RUNTIME_ERROR**
- 大小: 13 行, 363 字符
- 耗时: 3ms
- 错误: RuntimeError: 未定义变量 'n'

```matha
(无法读取源文件)
```

### examples\12_mech_sub.matha

- 状态: **RUNTIME_ERROR**
- 大小: 10 行, 259 字符
- 耗时: 1ms
- 错误: RuntimeError: 未定义变量 'tau_allow'

```matha
(无法读取源文件)
```

### examples\99_multiParam_boundary.matha

- 状态: **RUNTIME_ERROR**
- 大小: 21 行, 660 字符
- 耗时: 4ms
- 错误: RuntimeError: 未定义变量 'a'

```matha
(无法读取源文件)
```

### interp.matha

- 状态: **PARSE_ERROR**
- 大小: 279 行, 11218 字符
- 耗时: 29ms
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

- 状态: **PARSE_ERROR**
- 大小: 33 行, 876 字符
- 耗时: 2ms
- 错误: ParseError at L14:37: 期望 { (got OP_COLON ':')

```matha
(无法读取源文件)
```

### knowledge\cs\data_structures.matha

- 状态: **PARSE_ERROR**
- 大小: 80 行, 2387 字符
- 耗时: 7ms
- 错误: ParseError at L9:7: 期望类型表达式 (got NEWLINE '\\n')

```matha
(无法读取源文件)
```

### knowledge\cs\discrete_math.matha

- 状态: **PARSE_ERROR**
- 大小: 72 行, 1979 字符
- 耗时: 4ms
- 错误: ParseError at L9:5: 期望 ( (got PUNCT_LBRACKET '[')

```matha
(无法读取源文件)
```

### knowledge\linguistics\grammar.matha

- 状态: **PARSE_ERROR**
- 大小: 22 行, 542 字符
- 耗时: 1ms
- 错误: ParseError at L10:13: 期望表达式 (got OP_ARROW '->')

```matha
(无法读取源文件)
```

### knowledge\math\calculus.matha

- 状态: **RUNTIME_ERROR**
- 大小: 19 行, 620 字符
- 耗时: 2ms
- 错误: RuntimeError: 未定义函数 'trap'

```matha
(无法读取源文件)
```

### knowledge\math\number_theory.matha

- 状态: **RUNTIME_ERROR**
- 大小: 33 行, 950 字符
- 耗时: 6ms
- 错误: RuntimeError: 未定义函数 'power'

```matha
(无法读取源文件)
```

### knowledge\math\statistics.matha

- 状态: **RUNTIME_ERROR**
- 大小: 29 行, 975 字符
- 耗时: 4ms
- 错误: RuntimeError: 未定义函数 's'

```matha
(无法读取源文件)
```

### resource\apps\education_news.matha

- 状态: **PARSE_ERROR**
- 大小: 118 行, 4873 字符
- 耗时: 10ms
- 错误: ParseError at L33:17: 期望 = (got PUNCT_LPAREN '(')

```matha
(无法读取源文件)
```

### resource\apps\lifestyle_math.matha

- 状态: **PARSE_ERROR**
- 大小: 113 行, 4546 字符
- 耗时: 11ms
- 错误: ParseError at L54:7: 期望表达式 (got PUNCT_UNDERSCORE '_')

```matha
(无法读取源文件)
```

### resource\apps\media_math.matha

- 状态: **PARSE_ERROR**
- 大小: 112 行, 4240 字符
- 耗时: 13ms
- 错误: ParseError at L105:17: 期望 = (got PUNCT_LPAREN '(')

```matha
(无法读取源文件)
```

### resource\apps\social_ecommerce.matha

- 状态: **PARSE_ERROR**
- 大小: 113 行, 4608 字符
- 耗时: 8ms
- 错误: ParseError at L21:16: 期望 = (got PUNCT_LPAREN '(')

```matha
(无法读取源文件)
```

### resource\biology\molecular.matha

- 状态: **PARSE_ERROR**
- 大小: 36 行, 1069 字符
- 耗时: 2ms
- 错误: ParseError at L16:13: 期望表达式 (got OP_ARROW '->')

```matha
(无法读取源文件)
```

### resource\cs\algorithms.matha

- 状态: **PARSE_ERROR**
- 大小: 59 行, 1589 字符
- 耗时: 4ms
- 错误: ParseError at L14:37: 期望 { (got OP_COLON ':')

```matha
(无法读取源文件)
```

### resource\cs\data_structures.matha

- 状态: **PARSE_ERROR**
- 大小: 45 行, 1271 字符
- 耗时: 4ms
- 错误: ParseError at L10:22: 期望 { (got OP_COLON ':')

```matha
(无法读取源文件)
```

### resource\cs\game_algorithms.matha

- 状态: **PARSE_ERROR**
- 大小: 72 行, 2851 字符
- 耗时: 5ms
- 错误: ParseError at L15:58: 期望 参数名 (got NEWLINE '\\n')

```matha
(无法读取源文件)
```

### resource\cs\game_apps_math.matha

- 状态: **PARSE_ERROR**
- 大小: 129 行, 5113 字符
- 耗时: 13ms
- 错误: ParseError at L36:58: 期望 参数名 (got NEWLINE '\\n')

```matha
(无法读取源文件)
```

### resource\cs\os_concepts.matha

- 状态: **PARSE_ERROR**
- 大小: 81 行, 2818 字符
- 耗时: 4ms
- 错误: ParseError at L11:30: 期望表达式 (got OP_ARROW '->')

```matha
(无法读取源文件)
```

### resource\embedded\industrial_math.matha

- 状态: **PARSE_ERROR**
- 大小: 128 行, 4706 字符
- 耗时: 10ms
- 错误: ParseError at L74:16: 期望 = (got PUNCT_LPAREN '(')

```matha
(无法读取源文件)
```

### resource\engineering\civil.matha

- 状态: **PARSE_ERROR**
- 大小: 33 行, 1030 字符
- 耗时: 2ms
- 错误: ParseError at L25:18: 期望表达式 (got OP_ARROW '->')

```matha
(无法读取源文件)
```

### resource\extended\modeling_math.matha

- 状态: **PARSE_ERROR**
- 大小: 83 行, 2971 字符
- 耗时: 6ms
- 错误: ParseError at L31:44: 期望 参数名 (got NEWLINE '\\n')

```matha
(无法读取源文件)
```

### resource\finance\advanced.matha

- 状态: **PARSE_ERROR**
- 大小: 119 行, 4198 字符
- 耗时: 11ms
- 错误: ParseError at L24:22: 期望 { (got OP_COLON ':')

```matha
(无法读取源文件)
```

### resource\finance\math.matha

- 状态: **RUNTIME_ERROR**
- 大小: 51 行, 1580 字符
- 耗时: 5ms
- 错误: RuntimeError: 未定义函数 'npv'

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
- 耗时: 3ms
- 错误: ParseError at L13:17: 期望表达式 (got OP_ARROW '->')

```matha
(无法读取源文件)
```

### resource\linguistics\basics.matha

- 状态: **RUNTIME_ERROR**
- 大小: 25 行, 796 字符
- 耗时: 3ms
- 错误: RuntimeError: 未定义函数 'count'

```matha
(无法读取源文件)
```

### resource\logic\advanced_math.matha

- 状态: **PARSE_ERROR**
- 大小: 119 行, 4150 字符
- 耗时: 7ms
- 错误: ParseError at L10:18: 期望 = (got PUNCT_LPAREN '(')

```matha
(无法读取源文件)
```

### resource\logic\discrete_math.matha

- 状态: **PARSE_ERROR**
- 大小: 46 行, 1312 字符
- 耗时: 4ms
- 错误: ParseError at L8:5: 期望 ( (got PUNCT_LBRACKET '[')

```matha
(无法读取源文件)
```

### resource\math\3d_transform.matha

- 状态: **PARSE_ERROR**
- 大小: 97 行, 4015 字符
- 耗时: 10ms
- 错误: ParseError at L5:8: 期望 模块名 (got LIT_INTEGER '3')

```matha
(无法读取源文件)
```

### resource\math\algebra_advanced.matha

- 状态: **PARSE_ERROR**
- 大小: 75 行, 2356 字符
- 耗时: 8ms
- 错误: ParseError at L19:14: 期望 { (got OP_COLON ':')

```matha
(无法读取源文件)
```

### resource\os\boot_sector.matha

- 状态: **PARSE_ERROR**
- 大小: 97 行, 3815 字符
- 耗时: 2ms
- 错误: ParseError at L17:32: 期望 ( (got LIT_INTEGER '512')

```matha
(无法读取源文件)
```

### resource\os\deadlock_sync_math.matha

- 状态: **PARSE_ERROR**
- 大小: 88 行, 3287 字符
- 耗时: 6ms
- 错误: ParseError at L23:16: 期望 = (got PUNCT_LPAREN '(')

```matha
(无法读取源文件)
```

### resource\os\filesystem_math.matha

- 状态: **PARSE_ERROR**
- 大小: 121 行, 3968 字符
- 耗时: 8ms
- 错误: ParseError at L82:23: 期望 { (got OP_COLON ':')

```matha
(无法读取源文件)
```

### resource\os\kernel_memory.matha

- 状态: **PARSE_ERROR**
- 大小: 76 行, 3757 字符
- 耗时: 4ms
- 错误: ParseError at L53:35: 期望 ( (got LIT_INTEGER '0x100000')

```matha
(无法读取源文件)
```

### resource\os\kernel_process.matha

- 状态: **PARSE_ERROR**
- 大小: 69 行, 3386 字符
- 耗时: 3ms
- 错误: ParseError at L15:34: 期望 ( (got LIT_INTEGER '80')

```matha
(无法读取源文件)
```

### resource\os\kernel_syscall.matha

- 状态: **PARSE_ERROR**
- 大小: 119 行, 4578 字符
- 耗时: 3ms
- 错误: ParseError at L22:5: 期望 ( (got IDENTIFIER 'case')

```matha
(无法读取源文件)
```

### resource\os\memory_math.matha

- 状态: **PARSE_ERROR**
- 大小: 111 行, 4186 字符
- 耗时: 8ms
- 错误: ParseError at L30:15: 期望 { (got OP_COLON ':')

```matha
(无法读取源文件)
```

### resource\os\os_concepts_math.matha

- 状态: **PARSE_ERROR**
- 大小: 67 行, 2518 字符
- 耗时: 4ms
- 错误: ParseError at L11:10: 期望 ) (got KW_IN 'in')

```matha
(无法读取源文件)
```

### resource\os\process_math.matha

- 状态: **PARSE_ERROR**
- 大小: 105 行, 3747 字符
- 耗时: 6ms
- 错误: ParseError at L52:29: 期望表达式 (got OP_ARROW '->')

```matha
(无法读取源文件)
```

### resource\os\scheduling_math.matha

- 状态: **PARSE_ERROR**
- 大小: 76 行, 3272 字符
- 耗时: 6ms
- 错误: ParseError at L11:17: 期望 = (got PUNCT_LPAREN '(')

```matha
(无法读取源文件)
```

### resource\platforms\emerging_math.matha

- 状态: **PARSE_ERROR**
- 大小: 101 行, 4144 字符
- 耗时: 7ms
- 错误: ParseError at L22:15: 期望表达式 (got OP_ARROW '->')

```matha
(无法读取源文件)
```

### resource\security\crypto_math.matha

- 状态: **PARSE_ERROR**
- 大小: 143 行, 4858 字符
- 耗时: 8ms
- 错误: ParseError at L11:15: 期望表达式 (got OP_ARROW '->')

```matha
(无法读取源文件)
```

### resource\statistics\analysis.matha

- 状态: **PARSE_ERROR**
- 大小: 109 行, 3464 字符
- 耗时: 13ms
- 错误: ParseError at L50:37: 期望 { (got OP_COLON ':')

```matha
(无法读取源文件)
```

### resource\statistics\probability.matha

- 状态: **PARSE_ERROR**
- 大小: 40 行, 1253 字符
- 耗时: 3ms
- 错误: ParseError at L14:17: 期望 ) (got OP_PIPE '|')

```matha
(无法读取源文件)
```

### resource\tools\utility_math.matha

- 状态: **PARSE_ERROR**
- 大小: 143 行, 4790 字符
- 耗时: 11ms
- 错误: ParseError at L14:11: 期望表达式 (got OP_ARROW '->')

```matha
(无法读取源文件)
```

### resource\web\network_math.matha

- 状态: **PARSE_ERROR**
- 大小: 97 行, 3090 字符
- 耗时: 5ms
- 错误: ParseError at L27:25: 期望 { (got OP_COLON ':')

```matha
(无法读取源文件)
```

### resource\web\web_math.matha

- 状态: **PARSE_ERROR**
- 大小: 137 行, 4754 字符
- 耗时: 9ms
- 错误: ParseError at L11:13: 期望表达式 (got OP_ARROW '->')

```matha
(无法读取源文件)
```

### resource\航空航天\orbital_math.matha

- 状态: **PARSE_ERROR**
- 大小: 67 行, 2270 字符
- 耗时: 5ms
- 错误: ParseError at L54:38: 期望 参数名 (got NEWLINE '\\n')

```matha
(无法读取源文件)
```

### shaft_sub.matha

- 状态: **RUNTIME_ERROR**
- 大小: 11 行, 316 字符
- 耗时: 1ms
- 错误: RuntimeError: 未定义变量 'tau_allow'

```matha
(无法读取源文件)
```

### template_new.matha

- 状态: **RUNTIME_ERROR**
- 大小: 14 行, 462 字符
- 耗时: 3ms
- 错误: RuntimeError: 未定义变量 'n'

```matha
(无法读取源文件)
```

## 通过测试

- ✅ bootstrap_test_v2.matha (105L, 57ms)
- ✅ examples\04_pipeline.matha (9L, 1ms)
- ✅ examples\05_sensor_read.matha (9L, 1ms)
- ✅ examples\07_debug_sub.matha (8L, 4ms)
- ✅ examples\08_auto_optimize.matha (12L, 4ms)
- ✅ examples\08_optimize_sub.matha (11L, 1ms)
- ✅ examples\09_grow_sub.matha (11L, 1ms)
- ✅ examples\10_web_app.matha (19L, 1ms)
- ✅ examples\11_desktop.matha (25L, 3ms)
- ✅ examples\11_grow_sub.matha (10L, 4ms)
- ✅ examples\12_backend.matha (16L, 1ms)
- ✅ firewall_rules.matha (75L, 4ms)
- ✅ knowledge\biology\cell.matha (16L, 1ms)
- ✅ knowledge\biology\ecology_human.matha (23L, 2ms)
- ✅ knowledge\biology\genetics.matha (22L, 1ms)
- ✅ knowledge\chemistry\organic.matha (16L, 2ms)
- ✅ knowledge\chemistry\stoichiometry.matha (22L, 2ms)
- ✅ knowledge\cs\complexity.matha (20L, 2ms)
- ✅ knowledge\engineering\civil.matha (18L, 2ms)
- ✅ knowledge\engineering\electrical.matha (21L, 4ms)
- ✅ knowledge\engineering\mechanical.matha (21L, 2ms)
- ✅ knowledge\history\chronology.matha (32L, 4ms)
- ✅ knowledge\index.matha (52L, 1ms)
- ✅ knowledge\math\algebra.matha (41L, 6ms)
- ✅ knowledge\math\arithmetic.matha (38L, 5ms)
- ✅ knowledge\math\geometry.matha (52L, 6ms)
- ✅ knowledge\math\logic.matha (19L, 3ms)
- ✅ knowledge\math\trigonometry.matha (30L, 4ms)
- ✅ knowledge\physics\celestial.matha (18L, 2ms)
- ✅ knowledge\physics\electromagnetism.matha (23L, 4ms)
- ✅ knowledge\physics\mechanics.matha (27L, 4ms)
- ✅ knowledge\physics\optics.matha (20L, 2ms)
- ✅ knowledge\physics\quantum.matha (14L, 4ms)
- ✅ knowledge\physics\thermodynamics.matha (20L, 3ms)
- ✅ lexer.matha (215L, 35ms)
- ✅ library\core\arithmetic.matha (11L, 2ms)
- ✅ library\core\geometry.matha (9L, 3ms)
- ✅ library\core\trigonometry.matha (7L, 4ms)
- ✅ library\core\圆柱体积.matha (5L, 1ms)
- ✅ library\core\球体积.matha (5L, 1ms)
- ✅ library\core\计算球体积.matha (5L, 1ms)
- ✅ library\index.matha (16L, 1ms)
- ✅ library\mechanics\bearing.matha (8L, 4ms)
- ✅ library\mechanics\shaft.matha (8L, 2ms)
- ✅ library\mechanics\stress.matha (7L, 2ms)
- ✅ library\physics\mechanics.matha (9L, 6ms)
- ✅ library\structural\beam.matha (7L, 3ms)
- ✅ library\structural\column.matha (6L, 2ms)
- ✅ parser.matha (601L, 0ms)
- ✅ resource\biology\genetics.matha (29L, 4ms)
- ✅ resource\chemistry\stoichiometry.matha (36L, 3ms)
- ✅ resource\engineering\mechanical.matha (37L, 6ms)
- ✅ resource\geography\info.matha (30L, 3ms)
- ✅ resource\index.matha (57L, 4ms)
- ✅ resource\math\conic_sections.matha (44L, 5ms)
- ✅ resource\math\exponent_logarithm.matha (26L, 3ms)
- ✅ resource\math\trigonometry_advanced.matha (38L, 6ms)
- ✅ resource\physics\electromagnetism.matha (43L, 5ms)
- ✅ resource\physics\optics.matha (34L, 3ms)
- ✅ resource\physics\quantum.matha (27L, 4ms)
- ✅ resource\physics\thermodynamics.matha (30L, 3ms)
- ✅ template_old.matha (15L, 2ms)

## 按目录统计

| 目录 | 通过 | 失败 | 总字符 |
|------|------|------|--------|
| . | 5 | 4 | 63,145 |
| examples | 10 | 13 | 9,572 |
| knowledge | 1 | 0 | 990 |
| knowledge\biology | 3 | 0 | 1,663 |
| knowledge\chemistry | 2 | 1 | 1,875 |
| knowledge\cs | 1 | 3 | 5,956 |
| knowledge\engineering | 3 | 0 | 2,070 |
| knowledge\history | 1 | 0 | 982 |
| knowledge\linguistics | 0 | 1 | 542 |
| knowledge\math | 5 | 3 | 8,682 |
| knowledge\physics | 6 | 0 | 4,042 |
| library | 1 | 0 | 357 |
| library\core | 6 | 0 | 1,714 |
| library\mechanics | 3 | 0 | 890 |
| library\physics | 1 | 0 | 458 |
| library\structural | 2 | 0 | 503 |
| resource | 1 | 0 | 2,098 |
| resource\apps | 0 | 4 | 18,267 |
| resource\biology | 1 | 1 | 1,967 |
| resource\chemistry | 1 | 0 | 1,276 |
| resource\cs | 0 | 5 | 13,642 |
| resource\embedded | 0 | 1 | 4,706 |
| resource\engineering | 1 | 1 | 2,372 |
| resource\extended | 0 | 1 | 2,971 |
| resource\finance | 0 | 2 | 5,778 |
| resource\geography | 1 | 0 | 1,086 |
| resource\hardware | 0 | 2 | 7,433 |
| resource\linguistics | 0 | 1 | 796 |
| resource\logic | 0 | 2 | 5,462 |
| resource\math | 3 | 2 | 10,268 |
| resource\os | 0 | 10 | 36,514 |
| resource\physics | 4 | 0 | 4,546 |
| resource\platforms | 0 | 1 | 4,144 |
| resource\security | 0 | 1 | 4,858 |
| resource\statistics | 0 | 2 | 4,717 |
| resource\tools | 0 | 1 | 4,790 |
| resource\web | 0 | 2 | 7,844 |
| resource\航空航天 | 0 | 1 | 2,270 |

## 错误类型统计

- **PARSE_ERROR**: 44
- **RUNTIME_ERROR**: 20
- **SKIPPED**: 1

