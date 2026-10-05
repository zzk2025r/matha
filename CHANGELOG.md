# Matha 变更摘要

## 提交：`9a31a0c` — x86-64 原生发射器 + M3V 自举闭环 + 自然语言管线

**日期**：2026-09-10
**远程仓库**：`git@github.com:zzk2025r/matha.git`
**使用端**：`C:\Users\Admin\Matha`

---

## 一、变更范围

| 维度 | 新增 | 修改 | 删除 |
|------|------|------|------|
| 源码文件 | 28 | 10 | 5 |
| 测试文件 | 7 | 2 | 0 |
| Matha 源码 | 5 | 3 | 0 |
| 净代码行 | +12,111 | -1,133 | — |

---

## 二、新增模块

### 2.1 M3V 字节码编译器 (`src/mbc/`)

| 文件 | 职责 |
|------|------|
| `opcodes.py` | M3V 操作码定义（PUSH/CALL/RET/JMP/BINOP/OUTPUT/HALT 等 30+ 指令） |
| `compiler.py` | Matha AST → M3V 字节码（函数定义、递归、柯里化、控制流） |
| `vm.py` | M3V 虚拟机（栈式帧、闭包、偏应用、内建函数） |
| `serial.py` | 字节码序列化/反序列化（.mbc 文件格式） |
| `cli.py` | 命令行工具：`compile`/`run`/`eval`/`native` 子命令 |
| `native.py` | **x86-64 机器码发射器**（M3V → 机器码 → PE64 .exe） |

### 2.2 x86-64 原生发射器 (`src/mbc/native.py`, 约 1610 行)

**完整管线**：Matha 源码 → AST → M3V 字节码 → x86-64 机器码 → PE64 可执行文件

- **PEB 遍历自解析 kernel32 导出**（不依赖 PE 导入表，加载器兼容性最大化）
- 已支持的运行时能力（按「砖块」推进，每块有 `tests/test_native*.py` 覆盖）：
  - 砖块 0 基线：整数算术 `+ - * // %`、比较 `== != < > <= >=`、一元 `neg not`、
    控制流 `JMP JZ JNZ`（及 `and`/`or` 短路改写）、单参递归、整数十进制输出、进程退出
  - 砖块 1 多参数函数：序言按 arity 搬移入参（上限 `MAX_NATIVE_ARITY=8`）
  - 砖块 2 偏应用/柯里化：`apply_rt` 运行时 + `TYPE_PARTIAL` 记录
  - 砖块 3 堆与字符串：8MB bump 堆、对象头 `[type][len][payload]`、
    字符串拼接/比较/输出/repr、静态串对象
  - 砖块 4 列表：`BUILD_LIST` / `INDEX_GET` / `print_list` / `len`
  - 砖块 5 字典：`BUILD_DICT` / `dict_get` / `GET_ATTR` / `print_dict`
  - 砖块 6 整数幂 `**`（负指数提升为浮点幂，详见 3.5.4）
  - 砖块 7 闭包/盒/外域：`MAKE_CLOSURE` + 环境链、捕获静态分析、
    `LOAD_OUTER(_BOX)`、`MAKE/STORE/LOAD_BOX`、`R13` 环境寄存器
- 砖块 8 切片 `BUILD_SLICE`：`y[1:3]` / `y[2:]` / `y[:2]`，负下标归一化后钳到
  `[0, len]`，列表浅拷贝、字符串按字节切；非序列容器返回 `None`
- 砖块 9 解构 `UNPACK_SEQ`：`let (a, b) = …` 与 `for (i, j) in …`，
  缺项补 `None`，非序列全为 `None`
- 砖块 10 异常：`raise` / `错误(msg)` / `try-catch-finally`。处理器链存于
  `.data` 的 `hstack`，`raise_rt` 恢复 `rsp/rbp/r12/r13` 后长跳转回落地标签；
  `调用捕获` 为柯里化内建（arity 2），返回 `["__正常__", 值]` /
  `["__异常__", 消息]`；未捕获异常把 `str(值)` 写 stderr 并以退出码 1 结束
- 砖块 11 浮点：真除 `/` 恒返回 float，浮点 `+ - * / // % **`、比较
  `== != < > <= >=`、一元 `neg`。装箱 24 字节 `[TYPE_FLOAT][8][double@+16]`；
  `is_float`/`as_double`/`box_float` 复用「指针落在堆区间」判别。**浮点打印
  与 CPython `repr` 逐位一致**：`load_crt` 经 `LoadLibraryA`/`GetProcAddress`
  解析 `ucrtbase.dll`（回退 `msvcrt.dll`）的 `_ecvt`/`strtod`，`_ecvt` 取
  24 位精确十进制后按 p=1..17 做 round-half-even 舍入 + `strtod` 往返比较，
  首个可往返的 p 即最短表示，再按 `decpt<=-4 || decpt>16` 科学计数、
  `decpt<=0`、`decpt>=n`、中间四种规则拼串（指数恒 2 位且带 `+`/`-`）。
  特殊值 `inf`/`-inf`/`nan`/`0.0`/`-0.0` 单独处理
- 砖块 12 成员判断 `in` / `∈`：列表（线性扫描）、字符串（子串匹配）、
  字典（键存在性）；运行时 `seq_contains` 按对象类型分派
- 砖块 13 位移 `<<` / `>>`：整数移位
- 砖块 14 一元开方 `sqrt`（前缀 `^` / `**`）：运行时 `f_sqrt` 用 CRT
  `pow(x, 0.5)`，与 VM 的 `a ** 0.5` 逐位一致；整数且结果恰为整数时回退为
  整数（`^9 → 3`、`^16 → 4`），否则装箱浮点（`^2 → 1.4142135623730951`）；
  浮点输入恒返回浮点。负值经 `pow` 得 NaN（VM 侧为复数，属已知偏差）
- 砖块 15 浮点常量：mathlib 的 `CONSTANTS`（pi/e/tau/phi）与
  `PHYSICAL_CONSTANTS`（G/c/g/h_planck/N_A/R）发射为静态 `TYPE_FLOAT` 对象
  （`int` 值如 `c` 走裸整数），`LOAD_GLOBAL` 解析；此前单字母常量会静默读成 0
- 砖块 16 阶段一 数值 + 转换核心：
  - 一元数学 `sin/cos/tan/asin/acos/atan/sinh/cosh/tanh/exp/log/ln/log10/log2/sqrt`
    （恒浮点，复用 CRT、对齐 mathlib 的 `math.*`；可调用 `sqrt` 恒浮点，
    与一元 `^` 的整数完全平方回退不同）
  - 取整 `floor/ceil/trunc`、`round`（CRT `rint`，对齐 Python 半偶舍入）
  - `abs`/`sign`/`deg2rad`/`rad2deg`，二元柯里化 `pow`/`atan2`/`hypot`
  - 转换 `int`/`_to_int`/`float`/`_to_float`/`str`/`bool`
  - 类型 `type_of`（英文名）/`typeof`（中文名）；修复 `typeof` 关键字此前
    经 `LOAD_GLOBAL` 读 0 后调用即崩的潜在 bug
- 砖块 16 阶段二 序列 + 字典原语（不可变语义，浅拷贝）：
  - `slice(容器)(start)(stop)`（复用 `build_slice`，越界钳制、负下标归一）、
    `append(xs)(elem)`（新列表，非列表视作空列表 `[elem]`）、
    `mut_set_at(lst)(idx)(val)`（原地改列表，越界/类型错返回 `null`）
  - `_dict_keys`/`_dict_values`（新列表，按 VM 逻辑顺序 = 物理 pair 逆序）、
    `_dict_has`（布尔对象）、`_dict_put`（新字典：已有键原位更新，新键物理
    首位 ↔ VM 逻辑末尾）、`_dict_remove`（过滤生成新字典）、
    `_empty_dict`（静态空字典对象，值而非可调用）
- 砖块 16 阶段三 基础原语 / 序列构造 / 文件 I/O / 进制编解码：
  - `ord`/`chr`（UTF-8 首码点解码 / 码点编码，对齐 VM 的 Unicode 码点）；
    `list`（列表浅拷贝 / 文本→单字节列表 / 字典→键列表 / 其余→`null`）；
    `range(start)(end)`（stdlib 2 参闭开区间；VM 纯源码 2 参调用报错，
    故仅原生端定点断言，无法与 VM 对拍）
  - 文件 I/O `_read_file`/`_write_file`/`_append_file`（CRT `fopen`/`fread`/
    `fwrite`/`fseek`/`ftell`/`fclose`，字节 utf-8，失败静默返回 `null`）
  - 进制编解码 `encode_`/`decode_binary`·`ternary`·`decimal`（逐 Unicode
    码点，空格连接 / 空白切分）
- 砖块 17 阶段一 mathlib 数论 / 聚合：
  - 数论 `阶乘`（i64，`n>20` 溢出；`n<0 → 0`）、`最大公约数(a)(b)`、
    `最小公倍数(a)(b)`、`排列数(n)(r)`、`组合数(n)(r)`（`n<r → 0`）、
    `素数判定(n)`、`素数筛(n)`（素数字列表）、`杨辉三角(n)`（前 `max(n,1)` 行，
    `n<=1 → [[1]]`）
  - 聚合 `max`/`min`（列表→极值元素并保留类型；非列表→原值）、`sum`
    （整数累加保持整数，出现浮点则整体浮点，对齐 Python `sum`）
- 砖块 17 阶段二 mathlib 逻辑 / 集合：
  - 逻辑 `逻辑非(p)`；`逻辑与`/`逻辑或(a)(b)`（短路返回操作数，对齐 Python）、
    `逻辑蕴含(p)(q)=(not p) or q`、`逻辑异或(p)(q)=(p or q) and not(p and q)`、
    `逻辑双蕴含(p)(q)=(p==q)`（`val_eq`）
  - 集合 `集合并`/`集合交`/`集合差`/`集合补(a)(b)`（`ml_setify` 去重 +
    有符号整数升序，对齐 `set()`+`sorted`；集合补=集合差(全集)(子集)）、
    `集合子集(a)(b)`、`集合基数(s)=len(set(s))`、`集合幂集(s)`
    （第 `k` 项含元素 `i` 当且仅当 `k` 的第 `i` 位为 1，对齐 `_power_set`）
- 砖块 17 阶段三 mathlib 统计 / 随机：
  - 统计（确定性，与 VM 逐行对拍）`平均值(lst)`（空→int 0，否则 float）、
    `中位数(lst)`（数值插入排序，奇数→原元素、偶数→`(a+b)/2`，空→0）、
    `方差(lst)`（空→int 0）、`标准差(lst)`（恒 float，空→0.0）、
    `协方差(a)(b)`（长度不等/空→int 0）、`相关系数(a)(b)`（`sx==0` 或
    `sy==0`→int 0）、`正态密度(x)(mu)(sigma)`（`sigma<=0`→int 0，CRT
    `sqrt`/`exp`）。连续求和用 `ml_neumaier_add` 复刻 CPython 3.12+ `sum()`
    的补偿求和，浮点结果与 VM 逐位一致
  - 随机（非确定性，仅原生定点断言）`均匀随机(a)(b)=a+(b−a)·rand`、
    `正态随机(mu)(sigma)=mu+sigma·z`（Box-Muller）；`ml_rand` 为 xorshift64，
    首次以 `rdtsc` 播种（CRT 无 rand/srand）
- 砖块 18 堆 GC（保守式非移动 mark-sweep）：
  - 触发点：`alloc` 快路径发现空闲表非空或 bump 越界时跳 `alloc_slow`；
    冷路径「查空闲表 → 回收 → 再查 → bump」。快/冷路径均维持 `alloc` 调用
    契约（除 rax 返回值外不破坏调用者寄存器）
  - `start_bits`/`mark_bits` 各 1 bit/8 字节（128KB），显式标记栈
    `mark_stack`（1M 槽）；对象尺寸按类型标签精确推导，对象体
    `[obj+8,obj+size)` 逐字保守扫描
  - 根集：操作数栈 `[vstack,r12)`、CPU 栈 `[rsp,stack_top)`（含 `alloc_slow`
    保存的全部 GP 寄存器）、`raise_msg`、全局变量单元
    `[cells_begin,cells_end)`、异常处理器栈 `[hstack,hstack_ptr)`；
    `stack_top` 于 `_start` 记录
  - `sweep_start` 在 `main_entry` 内建闭包初始化后设置，令 `bclo:*`（永久
    全局闭包）与堆内静态对象（字符串/浮点/布尔/空字典）从不回收
  - sweep 仅遍历 `[sweep_start,heap_ptr)`：存活标记者保留，其余死亡对象按地址
    连续者合并为单块后挂入空闲表（块头 `[size][next]`）；空闲表始终按地址升序，
    回收时借单调游标把新块与前/后相邻空闲块再做地址级合并，分配时 first-fit
    并切分剩余块（split + coalesce）
  - 堆耗尽（GC 后仍无可用块且 bump 越界）时经 `print_uncaught` 写 stderr
    诊断「内存不足」并以退出码 1 终止；不再越过 `heap_limit` 覆写
    `start_bits`/`mark_bits`（旧行为会静默损坏，随后 GC 崩溃）
  - 已在 >8MB 累计分配场景经 100 万次非恒定分配、全局列表/字典/闭包跨
    GC 存活验证
- 砖块 19 嵌套文本 repr 对齐 CPython：
  - 新增运行时 `str_repr_body`（`rax`=STR 对象）：按 CPython `repr` 规则打印引号
    包裹的字符串 —— 引号选择（串内含 `'` 且不含 `"` → 用 `"`，否则用 `'`）、转义
    （当前引号字符与反斜杠前加 `\`；`\n`/`\r`/`\t` → `\\n`/`\\r`/`\\t`；其余
    `<0x20` 或 `0x7F` 字节 → `\xNN` 小写十六进制；`≥0x80` 字节原样透传以覆盖
    UTF-8 多字节/CJK/emoji）；连续普通字节按 run 批量写出
  - `print_list` 元素与 `print_dict` 值改经 `print_repr`（键原已如此）；顶层
    字符串输出仍走 `print_value`（= Python `str()`，无引号），与 VM 一致
  - 新增 `write_span(rdx=ptr,r8=len)` 低层写原语（保留 `r10`/`r11`）供 repr 逐段输出
  - `str(列表/字典)`：两遍渲染对齐 CPython 的 `str == repr` —— 新增输出汇全局
    `out_mode`/`out_count`/`out_buf_ptr`，`write_span`/`print_raw`/`print_int` 统一
    路由到汇：先计数（`out_mode=1`）得到精确字节数、分配目标 STR，再填充
    （`out_mode=2`）；容器与结果对象存帧局部作 GC 根（非移动 GC 下缓冲游标稳定）
  - `list(文本)`：改为按 Unicode 码点（UTF-8 前导字节定宽：1/2/3/4 字节）切分，
    对齐 VM（此前按单字节切分，非 ASCII 上输出错误）
  - 集合字面量 `{}` / `{1,2,3}`：新增 arity-3 内建 `构造集合(form)(variables)(elements)`
    与运行时 `list_dedup`（按 `val_eq` 去重、保序），对齐 VM `_builtin_make_set`
    （忽略 form/variables）。此前 `{}` 未在原生内建表注册，`LOAD_GLOBAL` 取到未初始化
    全局单元后以空地址 `CALL 3`，直接访问违例（0xC0000005）
    - 刻意分歧：`elements` 非列表时原生降级为空列表，VM 抛 `TypeError`（原生运行时无
      语言级异常机制，同 `len`/`append`；编译器恒传列表）
  - **集合理解 `{x | cond}` 仍整体未实现（三后端一致，非本次回归）**：解析器把 `|`
    归约为位或、链式比较 `1 <= x <= 10` 与生成子 `x >> S` 均解析报错、VM `_BINOPS`
    无 `|`、`_builtin_make_set` 无变量绑定/过滤。现报编译错误「不支持的二进制运算符
    '|'」属显式失败；仅修解析会令 `{x | x > 5}` 静默返回 `[False]`，故不修
- 尚未支持（编译期抛 `NativeNotSupported`）：`MathaIOError` 等非原生名字
  （mathlib 全部函数已实现）
- 结构性限制：操作数栈固定 64KB、8MB 堆（保守式 mark-sweep GC，非移动，
  空闲块可切分/相邻合并）、索引越界静默返回 0、
  仅生成 Windows PE64（无 ELF64/Mach-O）
- 手写 PE64 链接器：2 节（.text EXEC/.data RW），无数据目录；
  `.data` RVA 按 `.text` 实际大小动态对齐（固定值会在代码 >4KB 时与 `.text` 重叠）

### 2.3 自然语言管线 (`src/nl_*.py`)

| 文件 | 职责 |
|------|------|
| `nl_semantic.py` | 时代语义词典 — 中文/英文词汇的语义理解 |
| `nl_definition.py` | 定义构建器 — 列明条目 + 赋予时代定义 |
| `nl_to_formula.py` | 公式转换器 — 定义 → Matha 公式代码 |
| `nl_pipeline.py` | 统一管线 — NL 输入 → 语义 → 定义 → 公式 → 编译 → 执行 |

### 2.4 Matha 自举源码 (`matha/*.matha`)

| 文件 | 内容 |
|------|------|
| `stdlib.matha` | 纯 Matha 标准库（字符串/列表/JSON/文件IO/数学函数，542 行） |
| `interp.matha` | 用 Matha 实现的 Matha 解释器（eval/闭包/控制流） |
| `lexer.matha` | 用 Matha 实现的词法器 |
| `parser.matha` | 用 Matha 实现的语法器 |
| `bootstrap_matha.matha` | 自举测试套件 |
| `compiler_matha.matha` | 用 Matha 实现的编译器 |
| `interp_matha.matha` | 用 Matha 实现的完整解释器 |

### 2.5 其他新增模块

| 文件 | 职责 |
|------|------|
| `src/matha_vm.py` | 三进制原生虚拟机（Base2/Base3/Base10 底层数制） |
| `src/m3v_vm.py` | M3V 独立虚拟机实现 |
| `src/compiler_matha.py` | Matha → M3V 编译器 v2 |
| `src/lexer_matha.py` | Matha 词法器独立实现 |
| `src/matha_formula.py` | 公式系统 |
| `src/matha_runtime.py` | 运行时引擎 |
| `src/matha_service.py` | 集成服务层（eval/run/compile_to_c/compile_to_llvm/generate_code） |
| `src/matha/language_bridge.py` | 语言桥（吞噬 Rust/Go/JS/C/Python → Matha） |
| `src/matha/growth.py` | 成长引擎（组合/推导/生成/吞噬） |
| `src/base3_matha.py` | 三进制基础库 |

---

## 三、关键 Bug 修复

### 3.1 x86-64 机器码编码

| Bug | 位置 | 现象 | 修复 |
|-----|------|------|------|
| 尾声 ModRM 方向反 | `native.py` `_emit_epilogue`（约 258 行） | `0xE4`(mov rbp,rsp) 导致 ret 跳 0 崩溃 | → `0xEC`(mov rsp,rbp) |
| 序言 REX.X 误置 | `native.py` `_emit_prologue`（约 235 行） | `0x4F` 使 SIB 无索引变 r12+r12 | → `0x4D`(REX.X=0) |
| CALL 栈不平衡 | `native.py` `_emit_call`（约 267 行） | 返回值未覆盖函数槽 → BINOP 读到指针 | mov [r12-16],rax + sub r12,8 |
| PE 节区重叠 | `native.py` `_build_pe` | `DATA_RVA` 为固定常量 0x2000，代码 >4KB 时 `.text` 与 `.data` 重叠，`CreateProcess` 报 WinError 193 | `.data` RVA 按 `.text` 实际大小动态对齐到 SectionAlignment |
| 成员判断跳转错编码 | `native.py` `_emit_in_rt` | `jcc_rel32(0x77)` 发出 `0F 77`(EMMS) 而非近 `ja`，字符串 `in` 执行到垃圾指令 → `0xC0000005`（payload `0xC55`） | 两处 `0x77` → `0x87` |
| 成员判断取址基址错 | `native.py` `_emit_in_rt` | `48 8B 7F D8` 以 `rdi` 为基址取针，读到越界地址 → `0xC0000005`（payload `0xC70`） | → `48 8B 7D D8`（`[rbp-0x28]`） |
| 成员判断寄存器方向反 | `native.py` `_emit_in_rt` | `4C 89 C9` 是 `mov rcx,r9`，剩余长度寄存器未就绪 → 恒返回 `False` | → `49 89 C9`（`mov r9,rcx`） |
| try/catch 静默段错误 | `native.py` `_UNRESOLVED_GLOBALS` | try 脱糖先 `LOAD_GLOBAL "调用捕获"`，未拒绝该名 → 载入 0 值后调用 → `0xC0000005` | 将 `调用捕获` 加入 `_UNRESOLVED_GLOBALS`，编译期抛 `NativeNotSupported`（砖块 10 实现后已移出） |
| 处理器栈泄漏（try 循环崩溃） | `native.py` `_emit_builtin_guard` / `raise_rt` | 弹出处理器记录时误把 `hstack_ptr` 设为 `record+40`（等于当前值），指针每次调用只增不减 → 约 1638 次调用后溢出 64KB `hstack` → `0xC0000005` | 改为 `hstack_ptr = record`（`mov rdx,rcx`），栈顶真正回退，LIFO 平衡 |

### 3.2 语法解析与字节码编译

- 修复函数体内 `let f(带参类型标注) = ...` 被误归为 FuncDef 的问题
- 修复 `let` 体边界：`_parse_let` 解析完绑定值后把 `_in_let_value` 无条件置 `False`，
  嵌套 let 会清掉外层「in 是边界」标记，导致外层 `in` 被当作成员运算符
  （生成 `BINOP 'in'` 并把后续调用错误编进 lambda 内部）。
  同构问题另修 `func`/`and` 顶层 lambda 体漏设 `_in_let_value`
- 修复顶层同级多个 `let rec` 越界：`_emit_let` 的 rec 分支无条件申请局部槽并发射
  `MAKE_BOX`/`STORE_BOX`，但 main 帧无槽数组 → `IndexError`。
  补 `scope.is_main` 分支，main 下退化为 `STORE_GLOBAL`
- 修复 `in` 运算符在受限语境被误判为 let 边界：
  `_parse_if` / `_parse_if_expr_impl` 解析条件时、`_parse_paren_dispatch` 的
  分组与元组试探解析元素时，均暂置 `_in_let_value = False`（条件与括号内的
  `in` 必为成员运算符），使 `if x in [1, 2] then …`、
  `let b = (1 in [1]) in 输出(b)` 等正确解析。注意不可整体包裹
  `_parse_paren_dispatch`，否则与既有试探-回退叠加成指数级回溯
  （`test_let_in_and_mutual_rec.py` 会挂起）

### 3.3 VM 引擎修复引发的解释器回退（启动性能 + 后端能力差异）

VM 侧补齐能力时，`src/__init__.py` 被改写成 1182 行的 eager-import hub（导出
339 个名字），同时一批新内建只加进了 VM 而没同步解释器。两者叠加，使解释器在
**启动速度**和**可用能力**上都明显退化。

#### 3.3.1 启动性能：包初始化拖入 MCP SDK

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| `import src.interp` | 9.84s | 1.83s（**5.4×**，且优于 HEAD 基线 2.14s） |
| `import src` | 9.71s | 0.17s |

- **根因**：`src/__init__.py:110` 在包初始化时 eager `import src.mcp_server`，
  连带拖入 MCP SDK（`mcp_types`/pydantic/uvicorn/asyncio/ssl），`-X importtime`
  显示该子树累计约 **5.74s**（占启动 ~59%）。而包初始化是任何 `import src.*`
  的必经之路，于是解释器、编译器、原生后端与全部测试被一起拖慢。
- **修复**：改为惰性导出——`_LAZY` 映射表（name → module/attr/模式），
  首次访问才 `importlib.import_module` 并写入 `globals()` 缓存。
  - 用**模块类覆写 `__getattribute__`**（`_LazyExportModule`）而非 PEP 562 的
    `__getattr__`：`__getattr__` 只在正常查找失败时触发，而 `importlib` 导入
    子模块时会自动把 `src.matha_main` 这类**子模块**写进父包 `__dict__`，
    从而盖住同名导出（`src.matha_main` 应为 `main` 函数）。惰性解析必须主动覆写，
    这正是原先 eager `from ... import main as matha_main` 提供的效果。
  - 忠实保留原语义：try/except ImportError 的 `soft` 模式（模块缺失时该名字为
    `None`）；历史上列在 `__all__` 却从未绑定的 53 个名字继续抛 `AttributeError`
    （`from src import *` 仍因此报错，与改动前一致）。
  - **等价性验证**：对 `__all__` 全部 327 个名字快照 `getattr` 结果的
    `模块:限定名`，改动前后**零差异**。

#### 3.3.2 `interpret` 被意外遮蔽

`src/__init__.py` 先 `from src.interp import ... interpret ...`，后又
`from src.virtual_code import ... interpret ...` 覆盖了它，
`from src import interpret` 拿到的是 virtual_code 的实现而非解释器的。
它在导出表中与 `Interpreter`/`MathaRuntimeError` 同组，主入口 `matha_main`
也确实使用 `src.interp.interpret`，故改为绑定解释器；virtual_code 的版本仍可经
`src.virtual_code.interpret` 访问。

#### 3.3.3 解释器未同步 VM 新增能力

对拍（`tests/test_interp_parity.py`，34 项值级用例）逐项对齐解释器与 VM：

| 能力 | 解释器修复前 | 修复后 |
|------|-------------|--------|
| 前缀 `^` 开方 | 解析器记为 `UnaryOp(op='sqrt')`，解释器只认 `'^'` → 「未知一元运算符 'sqrt'」 | 同时接受 `'sqrt'`/`'^'`，并对齐完全平方回退整数（`^9` → `3` 而非 `3.0`） |
| 集合字面量 `{}` / `{1,2,2}` | 返回 Python `set`（无序），`len()`/索引/`去重()` 全部失效 | 去重保序的 `list`，与 VM `list_dedup` 一致 |
| `输出(v)` / `print(v)` | 未定义函数（只有 `Output` 语句） | 绑定实例输出流，记录并返回原值（可链式），对齐 VM `_make_output` |
| `安全索引(c)(k)` / `安全取属性(o)(n)` | 未定义函数 | 按 VM 语义：容器/对象为 `None` 或键缺失返回 `None`，不抛错 |
| `构造集合(form)(vars)(els)` | 未定义函数 | 去重保序 `list`（form/variables 为编译器降级路径保留） |
| `_empty_dict` | 未定义变量 | 提供空字典常量（`{}` 在语法中是空集合） |
| `typeof` / `n` 关键字 | 返回 Python 类型名（`'int'`/`'NoneType'`） | 统一到中文类型名表，与 VM `_builtin_typeof`、原生 `_TYPEOF_ZH` 一致 |
| `len()` | 只收 str/list/tuple，`len(_empty_dict)` 报错 | 追加 dict/set（VM 直接用 Python `len`） |

- 反向补齐：VM 缺 `去重` 内建（解释器有），新增 `_builtin_dedup`，
  并让 `_builtin_make_set` 复用它。
- 对拍结论：修复前 **13/21**（行为级）/ **25/34**（值级）一致，
  修复后 **34/34** 全部一致。
- 注：`输出`/`print`/`安全索引`/`安全取属性`/`_empty_dict` 在 HEAD 的解释器中
  也未发现，故属 VM 补齐后解释器未跟上的**能力差异**，而非被删除的功能。

---

### 3.4 砖块 19：文本语义三后端统一（转义 / repr / len / 索引 / 列表化 / 列表 `+`）

三后端 = 宿主 VM+原生 AOT（`src/mbc/*`）、解释器（`src/interp.py`）、
自举 Matha 实现（`matha/*.matha`）。本轮把字符串相关的CPython 语义补齐并加对拍。

| Bug | 位置 | 现象 | 修复 |
|-----|------|------|------|
| 转义集不完整且静默吞反斜杠 | `src/lexer.py` `_string` / `_ESCAPE_MAP` | 只认 `\n\t\"\\`；`"a\rb"` → `"arb"`；`"a\qb"` → `"aqb"`（无声改写源码字面量） | 新增 `_decode_escape`：补 `\r\b\f\v\a\'`、八进制 `\0~\777`、`\xNN`/`\uNNNN`/`\UNNNNNNNN`（含代理区与 >0x10FFFF 校验）；未知转义**保留反斜杠** |
| 指数浮点解析失败 | `src/parser.py` 数字字面量 | `1e20`/`1e-7`/`2E5` 退化为整数或报错 | 补指数部分（小数点后无数字也合法） |
| 原生 repr 未冲刷前置 run | `src/mbc/native.py` `str_repr_body` | `"ab\x01" > "ab"` 前缀丢字 | 遇转义/高位字节先 flush 已有 run |
| `movzx ecx,[r15+1]` SIB 用错索引 | 同上 | SIB `0x07` 以 RAX 为索引，读到垃圾字节，`\xNN` 完全错乱 | → `0x27`（无索引，基址 r15） |
| C1 控制码未按 CPython 转义 | 同上 | U+0080–U+009F 原样输出，且含 NBSP 的字符串比对失败 | 区间判定 `cmp cl,0x80` / `cmp cl,0xA1`，即转义 U+0080–U+00A0；U+00A1 起可打印透传 |
| 原生 `len()` 按字节计数 | `_emit_builtin_len` | `len("你好")` = 6 | 按 UTF-8 非续位字节统计码点 |
| 原生索引切出半个字符 | `_emit_getitem` / `_emit_utf8_width` | `s[1]` 返回半个 UTF-8 字符 | 按码点定位，返回整字符 |
| 解释器 `list(文本)` 按字节拆分 | `src/interp.py` `builtin_list` | `list("你好")` → 字节碎片 | 按码点拆分 |
| 原生列表 `+` 吐对象字节 | `_emit_in_rt` BINOP `+` | 只判「左值是否落堆区间」，`[1]+[2]` 走字符串拼接，把两个列表对象粘成假字符串 | 按两侧类型标签分派（str/list/int），新增 `list_concat`；不支持的组合返回 `null_obj`（与本后端 `str()`/`not` 既有约定一致） |
| 自举 lexer 转义与宿主不同构 | `matha/lexer.matha` `转义字符` | 只认 `\n\t`、其余 `\X` 丢弃反斜杠 → 自举编译器把 `" \t\n\r"` 编译成 `" \t\nr"`，**自举定点 stage2 ≡ stage3 失败** | 重写为 `解转义`（多返回 `(String, Int)`）+ `扫描十六进制转义续`/`扫描八进制转义续`，与宿主 `_decode_escape` 逐条同构 |
| 浮点分派只判右操作数 | `src/mbc/native.py` `is_float2` | 判右值容器时 `mov rax,r9` 后未改回 `r8` 就 `call is_float` → 「左浮右整」被判非浮点，`1.5 + 2` 走整数路径把堆指针当整数相加（输出 `None` 或指针样大数） | 补 `mov rax,r8`；左/右两侧各自先排容器再判浮点 |

- 新增 `tests/test_brick19_text.py`（41 项：三后端转义/ repr / len / 索引 / 列表化 / 列表 `+` 对拍）、
  `tests/test_native_encoding.py` 追加 3 项字节级编码断言（SIB `0x27`、`cmp cl`、`cmp al`）。
- `tests/test_mbc_bootstrap.py` 的 `test_m7_compiled_lexer_matches_host` 与
  `test_m7_double_bootstrap_lexer_chain` 各追加 15 条转义字面量，锁死宿主/自举同构。
- `tests/test_native.py` 新增 `float_left_operand` parity 用例（11 条浮点二元运算）。
- 对拍结论：repr 对 CPython **29/29**（AOT/VM/解释器三方一致）；
  全量回归 **1910 项通过**（此前 1865 项基线 + 本轮新增）。

---

### 3.5 AOT 算术语义与内存安全修复（除法 / 下标 / 幂 / 序列重复）

本轮针对 `src/mbc/native.py` 做 VM↔AOT 对拍定位的 5 类缺陷。全部经 Capstone
反汇编核对机器码，回归测试落在 `tests/test_native.py`。

### 3.5.1 整数除零崩溃 + 整除语义错误

| 现象 | 位置 | 修复 |
|------|------|------|
| `1 // 0` 直接 `0xC0000094`（#DE 整数除零） | BINOP `//` 直接发 `idiv` | 新增 `int_floordiv`：先查除数 0 → `raise_rt`（`err_divzero = "division by zero"`）；`rcx == -1` 短路返回 `-rax`，避开 `INT64_MIN / -1` 溢出 |
| `-7 // 2` 得 `-3`（x86 `idiv` 向零截断，Python 向下取整应为 `-4`） | 同上 | 整除后按符号修正（`rem != 0 && sign(r) != sign(divisor)` 则 `-1`） |
| `7 % -2` 得 `1`（`idiv` 余数取**被除数**符号，Python `%` 取**除数**符号） | BINOP `%` 直接用 `idiv` 余数 | 新增 `int_mod`：`r = a - floor(a/b)*b`，符号随除数 |

### 3.5.2 浮点 `//` / `%` 除零静默产出 `inf` / `nan`

`divsd` 除零不触发异常，原生侧会静默输出 `inf`、`nan`（浮点 `-7.5 % 2.0` 更得到 `-0.5`）。

- 新增 `f_floordiv` / `f_mod`：`crt_floor` + `a - floor(a/b)*b`。
- **除零判定必须与全零寄存器比较**：`ucomisd xmm1,xmm1` 只反映自相等，所有正常
  非 NaN 值都置 ZF=1（曾导致 `7.0 // 2.0` 一律抛 division by zero）。正确写法是
  先 `xorpd xmm2,xmm2` 再 `ucomisd xmm1,xmm2`，并以 `JP`（近端 `0x0F 0x8A`）
  排除 NaN、`JZ` 判零。条件码须落在**近端**表：`0x7A` 是短端 `jnp`，`0x0F 0xBA`
  则是 `btc`——两者都会错位指令流。
- 除零路径与整除共用 `fdivz` 抛出点。

### 3.5.3 列表下标越界读相邻堆字节

`_emit_getitem` 的列表分支直接 `mov rax,[rax+rcx*8+16]`，**不查界**：
`[1,2][9]` 静默返回 `0`（读到对象头之后的相邻堆字节），既与文本/字典路径
「越界返回 `null_obj`」的既有约定不一致，也是一处内存安全越界读。同时原生端
**完全不支持负下标**（`[1,2,3][-1]` 同样越界）。

- 补 `mov r8,[rax+8]` 取长度 + 符号分派：`rcx >= 0` 走 `cmp rcx,r8` / `jae`；
  `rcx < 0` 先 `neg rcx`，再 `cmp rcx,r8` / `jbe`（**含端点**：`-n` 合法且等于
  `a[0]`），随后 `base + (n-idx)*8` 取值。
- 越界（含 `-n-1`、空列表、`None` 容器）统一返回 `None`。

### 3.5.4 整数幂负指数静默返回 0

`2 ** -1` 在原生端得 `0`（整数幂连乘循环遇负指数只能给 0），Python 为 `0.5`。

- 负指数改走浮点幂 `f_pow`（`crt_pow`，与 VM 的 `float.__pow__` 逐位一致），
  `2 ** -100` 亦得逐位相同的 `7.888609052210118e-31`。
- `0 ** -1`：VM 抛 `ZeroDivisionError: zero to a negative power`，原生新增
  `err_powzero` 静态串走异常运行时（`pow(0.0,-1.0)` 只会给 `inf`）。

### 3.5.5 序列重复的两处编码缺陷

- `seq_repeat` 里两处奇偶测试发出 `49 F7 C4`（`test r12,1`），应为
  `49 F7 C6`（`test r14,1`）。奇偶判断错位导致 `seq * 1`、`1 * seq` 走倍增
  分支后返回垃圾。
- 交换操作数路径把整数当堆指针解引用：`3 * "xy"` 读 `[rcx+16]` 取类型标签，
  而此时该字段是整数 `3` 本身。应取右操作数 `r9`。

---

## 四、测试覆盖

| 测试文件 | 测试数 | 内容 |
|----------|--------|------|
| `test_native.py` | 371 | 端到端：编译 exe → 运行 → 校验 stdout/rc；含 VM/AOT parity 用例（含 `float_left_operand`、整除/取模 floor 语义、除零异常、列表负下标与越界、幂负指数） |
| `test_native_heap.py` | 132 | 字符串/列表/字典/与 VM 奇偶（含序列重复、交换操作数、不支持组合返回 `None`） |
| `test_native_encoding.py` | 23 | 字节级编码断言 + PE 节区布局（含 SIB/`cmp cl`/`cmp al` 回归、零填充尾段不得占文件体积） |
| `test_native_frontends.py` | 64 | 多前端一致性 |
| `test_brick19_text.py` | 41 | 砖块 19 三后端文本语义（转义/repr/len/索引/列表化/列表 `+`） |
| `test_let_in_and_mutual_rec.py` | 17 | `let … in` 体边界 + 同级/互递归 `let rec` 回归 |
| `test_mbc_bootstrap.py` | 236 | M3V 自举闭环测试（含自举/宿主 lexer 转义同构） |
| `test_mbc_bytecode.py` | 27 | M3V 字节码执行（递归/数论/字符串） |
| `test_new_features.py` | 24 | 新功能测试 |
| `test_nl_pipeline.py` | 39 | 自然语言管线测试 |
| `test_interp_parity.py` | 48 | 解释器/VM 值级对拍（34）+ 惰性导出契约（8）+ 导入性能守卫（2） |

**全量回归**：
- 砖块 19 轮次：1910 项通过（1817 基线 + 本轮砖块 19 新增回归；
  含自举定点 `matha/stdlib.matha` 恢复 stage2 ≡ stage3）
- 3.5 轮次：**2007 项通过**（1910 基线 + 97 项新增回归）。
  其中原生四套件 `test_native.py` / `test_native_heap.py` /
  `test_native_encoding.py` / `test_native_frontends.py` 共 **594 项通过**，
  用时 1557s。
- 性能基线未回退：VM 200,000 次循环约 5.9s，原生约 30–50ms。

---

## 五、Matha 能力版图

```
自然语言输入（中文/英文）
    │
    ▼
┌─────────────────────────────────┐
│ NL 语义层                       │
│ nl_semantic → nl_definition     │
│ → nl_to_formula                 │
│ （中文的语义精确性 +             │
│  英文的结构表达力）              │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│ Matha 源码（.matha）             │
│ func fib(n: Int) -> Int =       │
│   (n) => if n<2 then n          │
│   else fib(n-1)+fib(n-2)        │
│ #1：[fib(20)]                   │
└────────────┬────────────────────┘
             │
     ┌───────┴───────┐
     ▼               ▼
┌─────────┐   ┌──────────────┐
│ 解释器   │   │ 编译器        │
│ interp.py│   │ compiler.py  │
│ (Python) │   │ → M3V 字节码  │
└─────────┘   └──────┬───────┘
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
   ┌────────────┐      ┌──────────────┐
   │ M3V 虚拟机 │      │ x86-64 发射器 │
   │ vm.py      │      │ native.py    │
   │ (栈式帧)   │      │ → PE64 .exe  │
   └────────────┘      └──────────────┘
                              │
                              ▼
                      Windows 原生进程
                      fib(20) = 6765
```

### 中英互补设计

| 层次 | 中文角色 | 英文角色 |
|------|----------|----------|
| 语义层 | 时代语义词典（不可遗失的定义精确性） | 结构化表达（无限组合能力） |
| 源码层 | `#1：[...]` 输出标注、`真/假` 布尔值 | `func/if/then/else` 关键字 |
| 自举层 | `matha/stdlib.matha` 纯 Matha 标准库 | `matha/parser.matha` 语法器 |
| 底层 | 三进制（Base-3）映射汉字编码 | 二进制（Base-2）物理存储 |

### AI 编程能力

| 能力 | 实现 | 状态 |
|------|------|------|
| 虚构（从无到有生成公式） | `growth.py: generate()` | ✅ |
| 创造（组合已有公式导出新公式） | `growth.py: compose()` | ✅ |
| 解释（符号微分/代数变形） | `growth.py: infer()` | ✅ |
| 定义（时代语义→Matha 定义） | `nl_definition.py` | ✅ |
| 编程（NL → 公式代码 → 执行） | `nl_pipeline.py` | ✅ |
| 运行（解释器/VM/原生 exe） | `interp.py` / `vm.py` / `native.py` | ✅ |
| 改造（吞噬外部语言→融合） | `language_bridge.py: devour()` | ✅ |
| 代码生成（NL → Matha/Python/Rust/JS） | `matha_service.py: generate_code()` | ✅ |
| C/LLVM 编译 | `matha_service.py: compile_to_c/llvm()` | ✅ |
| x86-64 原生编译 | `native.py: compile_to_exe()` | ✅ |
| 自举（Matha 用 Matha 实现） | `matha/interp.matha` 等 | ✅ |

### 绝对底层

```
Base-2（二进制）  ← 物理存储（最终表示）
Base-3（三进制）  ← 字符编码（汉字/字母映射）
Base-10（十进制） ← 数值运算（Int/Float）
     ↑
  MathaVM（src/matha_vm.py）
  零 Python/C 依赖，所有类型基于原生数制
```

---

## 六、使用端同步

已将以下文件同步至 `C:\Users\Admin\Matha`：

- `src/` 下 22 个核心 .py 文件（含 `src/mbc/` 全目录 7 个文件）
- `matha/` 下 9 个 .matha 源文件（含自举标准库）
- 验证通过：`compile_to_exe('#1：[42]')` 生成 67584 字节 exe，`fib(20)=6765` 正确
