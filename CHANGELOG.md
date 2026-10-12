# Matha 变更摘要

## 原生后端：正则内建（阶段 A：字面量）

**日期**：2026-02-14

### 变更范围

原生后端（`src/mbc/native.py`）新增正则内建 `匹配`/`全匹配` 的机器码发射，
由新模块 `src/mbc/native_regex.py` 提供。阶段 A 仅实现**纯字面量模式**的
子串/全串匹配（按 UTF-8 字节比较），模式串含元字符
（`. ^ $ * + ? { } [ ] ( ) | \`）时于运行期抛出**可捕获**异常
（「暂不支持元字符模式」），避免给出静默的错误答案。此为「完整 PCRE 风格
原生引擎」的第一阶段，解析器 + 回溯 VM（阶段 B）后续补齐。

### 变更内容

- 新增 `src/mbc/native_regex.py`：`re_check_str`/`re_has_meta`/
  `re_lit_match_at`/`re_lit_search` 运行时助手，`匹配`/`全匹配` 内建发射器，
  `_emit_re_runtime`（追加到 `_build_emitters` 的运行时段）、`emit_regex_data`
  （元字符查表 + 两条错误消息串，随静态数据区发射）。`configure()` 注入
  `_emit_prologue/_emit_epilogue`，避免与 `native.py` 循环导入。
- `native.py`：`NATIVE_BUILTINS`/`_BUILTIN_ARITY`/`_BUILTIN_EMITTERS` 注册两个
  内建；`_UNRESOLVED_GLOBALS` 增加 `查找正则/查找全部/命名组/替换正则/分割正则`
  （编译期明确报错，避免静默读到空 cell）；调用 `_emit_re_runtime`/`emit_regex_data`。
- 阶段 A 不做任何堆分配（静态 scratch cell 非 GC 根），空模式/错误路径均安全。

### 关键修复

- 字面量循环此前以「模式长度」为基址读 haystack（漏加 haystack 指针），
  运行期访问违例（0xC0000005）。修复为 `hay_ptr + idx + k`。
- `raise_rt` 改为 `and rsp,-16` 自对齐：此前依赖入口 `rsp≡8`，任何在奇数个
  寄存器入栈后直接 `call raise_rt` 的调用点都会破坏 SSE 对齐而崩溃。现兼容
  任意入口对齐。

### 验证

- 新增 `tests/test_native_regex.py`（29 项）：字面量子串/精确、空模式、
  UTF-8 多字节、元字符/非字符串的可捕获错误与未捕获退出码（=1）、
  未实现内建的编译期拒绝、与解释器/VM 的 parity。
- 全量：`2515 passed`（净增 29）。

## 正则表达式库：解释器与 VM 双端内建（`src/regexlib.py`）

**日期**：2026-10-12

### 变更范围

新增可移植回溯正则引擎 `src/regexlib.py` 作为**单一语义源**：解释器
（`src/interp.py`）与 M3V VM（`src/mbc/vm.py`）复用同一 `_register_regex_builtins`
注册函数，保证两端语义一致（原生后端后续将复用同一「模式 → 节点」编译结果与
匹配算法）。

支持 PCRE 风格语法：字面量/转义、`.`、字符类 `[...]`（含范围/取反/内嵌
`\d\w\s`）、简写类、锚点 `^ $ \A \Z \z \b \B`、量词（贪婪/惰性/占有）、
捕获/非捕获/命名组、反向引用（`\1`、`\k<名>`、`\g<名>`、`(?P=名)`）、
环绕断言（`(?=) (?! ) (?<=) (?<!)`）、内联标志 `(?imsx)` 与作用域 `(?i:…)`。

### 内建（柯里化，`查找` 加「正则」后缀以不遮蔽字符串内建 `查找(文本,子串)->索引`）

- `匹配(re)(s)` → 布尔（search）
- `全匹配(re)(s)` → 布尔（fullmatch）
- `查找正则(re)(s)` → `[整体, 组1, …]`（未参与组为 null），无匹配为 null
- `查找全部(re)(s)` → 列表，每项同上
- `命名组(re)(s)` → `{组名: 文本}`，无匹配为 null
- `替换正则(re)(新)(s)` → 文本（`新` 可含 `\1..\9`、`$1`、`\g<名>`）
- `分割正则(re)(s)` → 列表（含捕获组）

### 变更内容

- 新增 `src/regexlib.py`：`_Parser`（模式 → 节点 AST）、`Pattern`/`Match`
  （CPS 回溯匹配器）、`_expand_repl`、`compile_regex`、`_register_regex_builtins`。
- `src/interp.py::_build_domain_builtins` 与 `src/mbc/vm.py::_default_builtins`
  调用 `_register_regex_builtins`。

### 验证

- 新增 `tests/test_regex.py`（37 项）：引擎单元（回溯/字符类/分组/环视/
  反向引用/贪婪惰性/标志/替换/分割）+ 解释器↔VM parity（含一等值调用）。
- 全量：`2486 passed`（净增 37）。

## 原生后端：修复顶层 `func` 值不支持偏应用/柯里化的崩溃

**日期**：2026-10-12

### 变更范围

顶层 `func` 名在值位置（`let f = g`、放入列表、作为实参传递）此前被发射为
`.text` 中的**纯代码地址**。`apply_rt` 对落在堆区间之外的值走 `ar_plain`：
`xor r13d,r13d; jmp rax`，**完全忽略实参数**。因此任何非「实参数 == 形参数」
的调用都会跳入函数序言并按 arity 弹参数，而栈上并无那么多实参：

- `func g(a,b,c) = …` 时 `g(1)(2)` → 访问违例 `0xC0000005`；
- `let h = g(1)` 后再 `h(2)` → 崩；
- `let fns = [g]` 后 `fns[0](1)(2)(3)` → 崩。

直接写 `g(1)(2)(3)` 之所以正常，是因为编译器把**完全应用**的调用融成了单条
`CALL 3`（`compiler.py:_flatten_call` + `_scan_fn_arities`），绕开了偏应用路径，
从而长期掩盖了该缺陷。VM 侧无此问题（始终用闭包/Partial）。

### 变更内容

- 新增 `_user_closure_arities`：静态扫描所有 `LOAD_GLOBAL`，凡引用到「顶层
  `func`、未被同名全局变量遮蔽、且无捕获」的函数，收集 `name → arity`。
- 启动期 `_start` 为这些函数各分配一条 `[TYPE_CLOSURE][fn][env=0][arity]`
  记录，指针写入数据槽 `bclo:{name}`（复用 arity>1 内建的柯里化机制）。
- `LOAD_GLOBAL` 对上述函数名改为载入 `bclo:{name}`（而非裸代码地址），使其
  调用经 `apply_rt → ar_close` 按 arity 决定「直调 / 偏应用 / 重建调用」。
- 数据节为这些名字补发 `bclo:` 槽位。

捕获型函数不受影响：它们在运行期经 `MAKE_CLOSURE` 实例化，绝不按名加载。

### 测试

- 新增 `test_func_declaration_value_is_curriable` 与
  `test_func_declaration_first_class_in_list`（`tests/test_native.py`）：
  覆盖偏应用、绑定后再调用、经列表一等调用；修复前确定性崩溃，修复后通过
  且与 VM 输出一致。
- 新增 `test_gc_survives_many_cycles_small_heap`（`tests/test_native_heap.py`）：
  把 `HEAP_SIZE` 调小到 `0x200000`（2MB）使程序反复穿越数十轮 GC，验证
  2000 结点的多层存活图在大量回收后仍完整。原生四套件 **810 passed**，
  全量 **2449 passed**。

## 原生后端：修复标记栈扩容的保存槽覆写（`mark_stack_grow`）

**日期**：2026-10-12

### 变更范围

`mark_stack_grow`（标记栈跨越单个 16MB chunk 时扩容）把 `rax..r11` 等易失
寄存器保存到 `[rsp-8..]`（base=4=rsp），随后内部的 `call VirtualAlloc` 会用
返回地址/被调栈帧覆盖这些槽位；恢复出的 `rax`（即越界那次入栈的对象指针）
是 `call` 的返回地址（`.text` 地址），写入标记栈槽后该对象被标记却**从不扫
描**，其后代被后续 GC 误回收。此缺陷与上一轮修复的 `heap_extend` 同源，但更
隐蔽：`gc_scan_object` 把 `.text` 地址当作未知类型（size 0）而静默跳过，
故常规用例不崩、不报错。

### 关键实现

- 保存/恢复槽位由 base 4（rsp）改为 base 5（rbp），即 `[rbp-8]`..`[rbp-56]`，
  与 `heap_extend` 一致。函数已 `and rsp,-16; sub rsp,0x60`，`[rbp-0x38]` 以上
  均在已分配帧内。

### 测试

- 新增 `test_mark_stack_growth_preserves_live_graph`：把 `MARK_CHUNK` 调小到
  `0x1000`（512 槽）以在轻量程序中触达扩容，构造「外层列表 → 900 个子列表
  → 各含一个字符串」的存活图并触发 GC（分配 >1GB），断言 900 个后代全部存活
  （无 `None`）。经 A/B 校验：修复前该用例确定性失败，修复后通过。原生四套件
  合计 **810 passed**，全量 **2446 passed**。

## 原生后端：1GB 固定堆 + 16GB 动态竞技场（无界增长）

**日期**：2026-10-12

### 变更范围

固定的 1GB 镜像内堆之上，新增启动期预留的 **16GB 连续动态竞技场**，单个存活
分配与存活集总量均可越过 1GB；固定区与动态区**地址连续、协同工作**（固定区
服务常规分配，动态区按 16MB chunk 按需提交）。此前单个 >1GB 的分配确定性
OOM（如 `range(0, 140000000)` 约 1.12GB）。

### 关键实现

- **三节布局**：`.text` / `.bss`（GC 位图、异常栈、兜底标记栈，纯零不物化）/
  `.data`（标量 + 静态对象 + 末尾 1GB 固定堆）。`.data` 为末节，其**绝对末梢**
  向上取整到 64KB 即 `SizeOfImage`，也就是动态区预留起点（`dyn_base`）。
- **`heap_init`**（`_start` 调用）：`VirtualAlloc(dyn_base, 16GB, MEM_RESERVE)`
  预留连续竞技场；再预留标记栈区并提交首个 16MB chunk。
- **`heap_extend`**：`alloc_slow` 在 bump 越界时逐 chunk `MEM_COMMIT`（每次
  16MB，夹到 `dyn_end`），返回成功/耗尽；`alloc_slow` **循环扩展**直至当前块
  容纳得下——故单个超过一个 chunk 的大分配也能满足。
- **判据用 `heap_used = heap_ptr - heap_base`**（分配时更新），把「是否堆指针」
  的位图边界限制在实际已用量内；因无 imm32 符号扩展，大 span 比较一律走内存
  操作数 `cmp r64,[rip+heap_used]`。
- `_APIS` 经 PEB 名解析新增 `VirtualAlloc`；`_start` 先设
  `heap_limit = heap_free + HEAP_SIZE`，`heap_init` 成功后再前移到 `dyn_base`。

### 修过的坑（均为本轮定位）

- **禁用了 ASLR**：镜像无重定位表却带 `DYNAMIC_BASE|HIGH_ENTROPY`，Windows 会把
  镜像加载到**非 64KB 对齐**的随机基址，使运行时按绝对地址 64KB 对齐算出的
  `dyn_base` 落回镜像内部，`VirtualAlloc` 预留失败。清掉这两个位（仅留
  `NX_COMPAT`）后固定加载到 `0x140000000`，`dyn_base` 恰等于 `SizeOfImage`。
- `heap_extend` 曾把「新末端」存到 `[rsp-8]`，被紧接着的 `call` 压入的返回地址
  覆盖；改用 `[rbp-8]`。
- `alloc_slow` 的 bump 路径曾把 `heap_used` 设为**旧**堆顶（`rdx` 被
  `lea heap_base` 覆盖），使刚分配的大对象被判为「非堆指针」（`len` 误得 0）。
  改为从 `[heap_ptr]` 重取新堆顶。

### 测试

- 新增 `test_single_allocation_beyond_1gb_uses_dynamic_arena`（1.12GB 列表）、
  `test_multiple_allocations_span_fixed_and_dynamic_regions`（两个 1.2GB 列表，
  合计 >2GB，地址连续）。
- OOM 用例改为超过「1GB + 16GB」总跨度（`range(0, 2500000000)`），仍确定性
  终止（stderr 诊断 + 退出码 1）。原生四套件合计 **809 passed**。

## 原生后端：堆上限 8MB → 1GB（虚拟零尾 + 按需提交页）

**日期**：2026-10-12

### 变更范围

此前原生后端的堆是 `.data` 段里固定的 **8MB** BSS，存活集略超 8MB 即确定性
OOM。本变更把保留区放大到 **1GB（128×）**，并让巨大的零区不再写进文件、
也不在编译期物化进 Python 内存。

### 关键实现

- **虚拟零尾**：`_Emitter` 新增 `emit_virtual(n)` / `virtual_len`：`.data` 尾部的
  恒零运行时状态（堆 free 区、64KB 异常栈、两片 GC 位图、标记栈）只记尺寸，
  不追加字节；`align`/`label_here`/`patch` 均按「实字节 + 虚拟尾」计算 RVA。
- `_build_pe` 用独立 `data_vsize` 填节表 VirtualSize 与 SizeOfImage；
  SizeOfRawData 仍截到首个尾零之前，加载器按规范补零。RVA 布局逐字节不变，
  故 ~65 处 `(v - heap_base) < HEAP_SIZE` 指针判据与 ~65 处 `lea heap_base`
  引用**无需改动**。
- 常量随手放大：`HEAP_SIZE = 0x40000000`；`GC_BITMAP_BYTES = HEAP_SIZE//64`
  （各 16MB）；`GC_MARK_STACK_ENTRIES = HEAP_SIZE//16`；OOM 文案随 `HEAP_SIZE`
  动态生成。

### 依据 / 代价

- 实测（`GetProcessMemoryInfo`）：1GB 保留堆的空转进程 commit 仅 ~0.1MB ——
  Windows **不预提交**镜像未初始化尾段，物理页按需分页。故放大保留区运行时
  几乎零成本，仅镜像 VirtualSize 增长，文件仍 ~104KB。
- **加载器 2GB 上限（本轮新发现）**：Windows 拒绝 SizeOfImage ≥ ~2GB 的 PE
  镜像（`OSError: [WinError 193] …不是有效的 Win32 应用程序`；实测 1979.9MB
  可加载、2013.4MB 失败）。故标记栈容量不能取 2× 余量：每对象至多入栈一次
  （`mark_bits` 保证幂等），`HEAP_SIZE/16` 已是精确上界，取 `HEAP_SIZE//16`
  即可，镜像停在 ~1.6GB。

### 测试

- 新增 `test_heap_grows_beyond_old_8mb_limit`（16MB 存活列表）、
  `test_gc_collects_cumulative_allocation_over_1gb`（累计分配 >1GB 靠 GC 回收）；
  OOM 用例改为 1.12GB 请求。既有 GC/复用用例仍通过（堆变大后不再必然触发 GC，
  由上述新用例补足）。


## 原生后端：任意精度整数（BigInt 运行期对象）

**日期**：2026-10-12

### 变更范围

PE64 原生后端（`src/mbc/native.py`）新增运行期任意精度整数，消除「原生整数
恒为 int64」的溢出局限。VM 本就是任意精度 Python int，本改为向 VM 靠拢。

| 项 | 变更前 | 变更后 |
|----|--------|--------|
| `a**b`（如 `a=2;b=100`） | int64 回绕/错误 | 任意精度 BigInt，打印/比较/负数/`str`/`type_of` 均正确 |
| `x*x`、`x+1`（超 int64） | 回绕 | 溢出时自动提升为 BigInt（`jo` → 提升路径） |
| 源码中的超 int64 **字面量常量**（如 `12345678901234567890`） | 编译期回绕为 int64 | 数据节生成静态 BigInt 对象，按任意精度使用 |
| BigInt 参与 `== != < <= > >=` | 崩溃（0xC0000005）或错值 | `bi_cmp` + `setCC` 正确比较 |
| 容器内 BigInt（`[a**b, ...]`、字典值）、GC | — | 纳入 `value_to_str`/`gc_obj_size`，反复分配触发 GC 不崩溃 |

### 表示与算法

- 对象布局：`[0]=TYPE_BIGINT(11) [8]=nlimbs [16]=sign(0/1) [24+i*8]=limb i`，
  基 `10^9`，低位在前，符号-绝对值。规范形：无前导零 limb；能装进 int64 的
  值一律降级为裸 int64，故「堆上的 BigInt」必然超出 int64。
- 例程：`bi_alloc/bi_from_i64/bi_trim/bi_normalize/bi_to_str/bi_neg/bi_mag_cmp/
  bi_add/bi_sub/bi_mul/bi_cmp/bi_pow_i`。`bi_trim` 在每次 `bi_mul` 后裁剪高零
  limb，避免指数级 limb 膨胀（原 OOM 根因）。
- 常量：`_bigint_static_limbs()` 把超 int64 的 Python 常量拆为 `bob:{i}` 静态
  对象写入数据节；`PUSH_CONST` 据此 `lea` 而非 `mov imm64`。

### 本轮修复的编码/逻辑缺陷

1. `bi_to_str` 序言 `sub rsp` 误用 imm8（`48 83 EC 80` 被符号扩展为 `-128`）→ 改 imm32 `48 81 EC 80 00 00 00`。
2. `bi_to_str` 的 `signlen` 局部（`[rbp-48]`）对正数未初始化 → 读到栈垃圾致巨大分配；改为先清零。
3. `bi_to_str` 总位数计算遗漏 `mov rax, r8`（`imul rax, rax, 9` 前）。
4. `bi_cmp` 负数翻转误写 `neg rcx` → `neg rax`。
5. `+` 的 int64 溢出路径未复原 `rax`（提升前应等于左操作数）→ 新增 `laddovf` 标签复原。
6. `**`：`_emit_bigint_binop` 已把底数提升为 BigInt，`bi_pow_i` 内又 `bi_from_i64` 二次转换（对对象指针取垃圾）→ `bi_pow_i` 直接接收 BigInt 底数。
7. BigInt 比较分支误用 **Jcc** 操作码（`0F 8x`）当 `setCC`（`0F 9x`），产生 `je rel32` 越界跳转 → 改用 `_CC`（`setCC`）表。

### 语义边界（本轮不扩展）

- `// %` 及位运算/移位遇 BigInt 仍抛可捕获错误 `大整数不支持该运算`（`err_bigintop`，退出码 1）；`**` 遇 BigInt 指数或负指数+BigInt 底同理。原生 int64 路径不变。
- 已知遗留（非本改）：`函数(x) … 结束` 表面语法对**任意**参数（含普通 int）均崩溃，属前端解析问题，与本 BigInt 增量无关。

### 验证

`tests/test_native.py`（新增 31 项 BigInt 用例：算术/比较/容器+GC/拒绝路径，及 5 条 VM↔AOT parity）+ `test_native_heap.py` + `test_interp_parity.py` 共 **782 passed**。

## 原生后端语义对齐 —— 深层相等、可捕获的越界/属性错误、补齐内建（含 `?.` 可选链）

**日期**：2026-10-12

### 变更范围

PE64 原生后端（`src/mbc/native.py`）向 VM 语义靠拢的三组修复：

| 项 | 变更前 | 变更后 |
|----|--------|--------|
| `[1,3] == [1,4]` | 原生按对象长度（元素个数）逐字节比 → 误判为 `真` | `val_eq` 深层结构相等 → `假` |
| `[[1,3]] == [[1,3]]` | 误判为 `假` | `真`（列表/字典/字符串逐元素递归；整数↔浮点↔布尔按数值比较，NaN≠NaN） |
| 列表/字符串下标越界 | 静默返回 `None` | 经 `raise_rt` 抛 `list/string index out of range`，可被 `try…catch` 捕获；未捕获写 stderr、退出码 1 |
| 非字典属性访问 `3.z` | 静默返回 `None` | 抛 `属性访问失败: 非字典对象`，可捕获 |
| `print(...)` | 未实现 → 调用崩溃 | `输出` 的别名（LOAD_GLOBAL 期改写） |
| `去重(xs)` | 未实现 → 调用崩溃 | 按 `==` 去重保序；非列表抛可捕获异常 |
| `安全索引(c)(k)` | 未实现 → 调用崩溃 | 越界/缺键/不可下标返回 `None` |
| `安全取属性(o)(name)` | 未实现 → 调用崩溃 | 非字典/`None` 返回 `None`；字典缺键返回 `None` |
| `a?.b` / `a?.[i]` 可选链 | 脱糖到未实现的 `安全索引`/`安全取属性` → **原生端整段崩溃** | 正常工作 |

### 语义决定

1. **深层相等只用于 `==`/`!=`**：`val_eq` 为自包含递归例程，浮点比较用
   `setnp`+`sete` 排除 NaN。集合去重（`list_dedup`）本就经 `val_eq`，故
   `{([1,3]), ([1,3])}` 现按结构去重。
2. **「越界/属性错」改为抛异常而非 `None`**，与 VM 一致；`安全索引`/`安全取属性`
   则保留「不抛、返回 `None`」语义（VM `_builtin_safe_index`/`_builtin_safe_attr`），
   二者分工不重叠——`_emit_getitem` 新增 `raise_oob` 开关复用同一取值核心。
3. **字典缺键索引仍返回 `None`**（VM 抛 `KeyError`），登记于
   `tests/test_native_heap.py::test_dict_missing_index_returns_none`，本轮不动。

### 验证

`tests/test_native.py` 521 + `tests/test_native_heap.py` 136 + 编码/前端/brick19/
多语言/集合理解 288 + `test_interp_parity.py` 94 全绿；新增
`test_native_print_alias` / `test_native_dedup_raises_on_non_list` /
`test_native_safe_index_and_attr_never_raise` / `test_native_optional_chaining` /
`test_native_deep_equality` / `test_native_nested_set_dedup` /
`test_list_index_oob_raises_catchable` / `test_string_index_oob_raises_catchable` /
`test_uncaught_index_oob_exits_one` / `test_non_dict_attr_raises_catchable` 及
VM↔AOT 对拍用例 `new_builtins`。文档同步：`docs/matha-vs-mainstream.md`、
`docs/04-数学核心（机械语言）.md` §3.1。

---

## 提交：`50b0267` 后续 — `@(...)` 括号式设定此前完全无法解析

**日期**：2026-10-06

### 变更范围

EBNF §2.4 的 `@(...)`（`|` 分格）**整条形式此前都无法通过解析**，而 `@:` 前缀形式
一直是好的——两条等价形式只有半条可用。

| 项 | 变更前 | 变更后 |
|----|--------|--------|
| `@(x=1)` | `期望 ) (got EOF)` — 值的「消费完整性」检查只认逗号/换行/EOF/`|`，**漏了 `)`**，于是回退分支把 `)` 一并吞进字符串值 | 解析成功，绑定 `x=1` |
| `@(x=1\|y=2)` | `未定义变量 'y'` — `_parse_bit_expr` 把顶层 `\|` 当**位或**吃进第一项的值（`1\|y=2`），第二项从未创建 | `|` 作项分隔符，两项都绑定 |
| `@(m=(6\|1))` | 同上连带 | 嵌套分组内 `\|` **仍是位或**（恢复原语义），`m=7` |
| `*/文字*公式/*` | 不解析公式部分 | **维持不变**（见下） |

### 语义决定

1. **`@()` 顶层 `|` 是分隔符，嵌套分组内 `|` 是位或**。二者由**括号层级**消解：
   进入 `( ... )` 分组时清掉「正解析 `@()` 项」标志，退出时恢复。这样
   `@(a=1|b=2)` 分两项，`@(m=(6|1))` 的组内仍是位或，无需在两种读法间二选一。
2. **`*/文字*公式/*` 维持自由文本、`formula=None`**——不是待补的缺口。原文法的
   `[ "*" , <expr> ]` 公式形态与自由文本冲突（文本里的 `*` 会被误当公式起点，如
   `【*/计算 2*3 的和/*】`），仓库内无任何公式形态用例，且 `Annotation` 是编译期
   NOOP（不参与字节码），故此处**刻意不区分公式**。

### 验证

新增 `test_interpreter.py` 2 例（括号式四形态 + 嵌套 `|` 保留位或）。全量：
`1705 passed`（非原生）+ `510 passed`（原生）= `2215 passed`，无回归。

---

## 提交：`50b0267` 后续 — `？` 公式模式库：按「格式」统一同形公式

**日期**：2026-10-06

### 变更范围

`？` 不是运算符，而是「此处为一个变量」的**槽**。按用户确认的语义：`**#：？公式`
登记为模式进公式库（不可执行）**，具体公式与库中模式按**格式**合一。

| 项 | 变更前 | 变更后 |
|----|--------|--------|
| `#：？+？=？` | 求值 → `未定义变量 '？'` | 登记为模式（公式模式库） |
| VM 执行 `#：？公式` | **`KeyError '？'`** | 登记进 VM 公式库 |
| AOT 编译 `#：？公式` | `NativeNotSupported` | 空实现（无运行期效果） |
| 表达式中的 `？name` | 被读成「万能占位符**当作函数**作用于 name」 | 具名模式槽，跨出现强制一致 |
| 具体公式命中模式 | 解释器记录合一；**VM `KeyError '单价'`**、AOT 撞未定义全局 | 三端一致：不发求值代码 |
| 槽遍历 | `FuncApp` 漏收集；列表/元组/索引字段名写错致静默跳过 | 覆盖全部表达式形态 |

### 语义决定

1. **格式即身份**。归一化形状相同的公式即**同一条公式**，登记时归并、不重复堆积。
   运算符与结合结构属于格式，槽名不属于——故 `单价+运费=总价` 与 `？+？=？` 统一，
   而 `单价*数量=总价` 不统一。
2. **裸 `？` 是匿名槽**，每次出现彼此独立；**`？name` 是具名槽**，跨出现**强制一致**
   （Prolog 变量 / Python `{name}`）。这正是 `？name` 存在的意义：它给形状加上
   等式约束，故 `？a + ？a = ？b` 接受 `面积 + 面积 = 周长` 而拒绝 `x + y = z`。
   （此前解析器只在**绑定**位置遵守「`？` 可被字母替代」，表达式位置把 `？sum`
   误读成对 `sum` 施加万能占位符，报「未定义函数 FuncApp」。）
3. **两个方向的效果**：
   - *多公式一用途意图*：格式相同的任意多个具体公式合一到同一模式。
   - *一公式多用途意图*：同一模式换基础定义（换绑定）即换用途——`？+？=？`
     绑成 `收入+支出=结余` / `长+宽=周长` / `速度+时间=距离` 是同一条公式的三个实例。
4. **匿名槽无需改 AST**：`ast_nodes.Variable` 只有 `name` 与 `is_placeholder`，
   每个裸 `？` 都是同一个 `Variable('？', True)`。这里用**左到右遍历次序**充当
   匿名槽序号（1、2、3……），序号可序列化、可用于实例化。

### 关键修复

`docs/02-词法结构.md` 原文把 `#：？+？=？` 列为「运行：执行公式」，与槽语义冲突
（槽没有可求值的值，无法执行），已更正为「登记」并补上完整语义表。

### 三端分工

合一是 **AST 级**操作，故在解释器完成。编译器把模式整体常量化成
`(段号, 文本, 形状, 槽位表)` 并发新指令 `FORMULA_SCHEMA`(0x62)；VM 据此登记进
公式库；原生后端发空实现。

**具体公式命不命中模式也在编译期判定**：编译器与解释器按**同源同序**建同一套
公式库，故静态判定结果与解释器运行期判定必然一致。命中的具体公式**不发求值
代码**——否则 VM 会把 `单价 + 运费 = 总价` 当表达式求值而 `KeyError '单价'`，
AOT 同样撞未定义全局；编译期判掉之后三端 stdout 一致，且原生后端无需运行期
匹配、无需跳转指令。三端**可观察行为（stdout）一致**，模式本身对程序输出无影响。

### 测试

新增解释器 9 例（登记/不求值、同形统一、运算符属格式、具名槽一致、同形归并、
匿名独立、一公式多用途、遍历覆盖、函数与索引合一）+ VM/AOT 19 例（含三端
「命中模式的具体公式不求值」回归）。全量：`1705 passed`（非原生）+
`510 passed`（原生）= `2215 passed`，无回归。
新增模块 `src/formula_schema.py` 通过 mypy 零告警。

---

## 提交：`50b0267` 后续 — 前缀 `++`/`--` 三端补齐 + `？` 占位符等价于具名变量

**日期**：2026-10-06

### 变更范围

| 项 | 变更前 | 变更后 |
|----|--------|--------|
| 前缀 `++`/`--` | 解释器支持，**编译器报「不支持的一元运算符」** | 三端一致 |
| AOT 运行期浮点自减 | `subsd` 结果留在 `xmm1`，而 `box_float` 只读 `xmm0`，恒得 `1.0` | 正确 |
| 表达式中的 `？name` | 被读成「万能占位符**当作函数**作用于 name」，报「未定义函数 FuncApp」 | 与绑定位置一致，等价于具名变量 |

### 语义决定

1. **`++`/`--` 是非原地运算**，语义为 `v + 1` / `v - 1`，**不修改变量绑定**：
   `let x = 5; 输出(++x); 输出(x)` 得 `6` 与 `5`（两个后端一致）。沿用解释器既有
   行为，未改造成自增/自减赋值号。
2. **`？` 不是运算符**，而是「此处为一个变量」的占位符。按 `docs/02-词法结构.md`
   占位符条与 `docs/00-前言与概述.md` L135，它**可被任意字母替代**
   （`？ = a = g1 = c3 = m1 = Z`），且 `？sum` **等价于**具名变量 `sum`。
   故不存在「与 `？` 等价的另一个符号」——`？` 的含义就等于普通标识符。

### 关键修复

1. **AOT 浮点自减恒为 `1.0`**：SSE 标量指令（`movsd`/`addsd`/`subsd`）的
   `ModRM.reg` 是**目的**操作数，与 GPR 指令的直觉相反。原写法
   `subsd xmm1, xmm0`（ModRM `C8`）把结果留在 `xmm1`，而 `box_float` 只读
   `xmm0`，于是 `2.5` 被当成 `1.0` 装箱。现改为把 `1.0` 放入 `xmm1`、让
   `xmm0` 作被运算数并保留结果（`addsd/subsd xmm0, xmm1`，ModRM `C1`）。
2. **`？name` 在表达式位置不生效**：解析器此前只在**绑定**位置按「`？` 可被字母
   替代」处理（`？sum = 0` 一直绑定 `sum`），表达式位置则把 `？sum` 读成对 `sum`
   施加万能占位符。新增 `_parse_placeholder_var`，`？` 后紧跟标识符时合成一个
   **以该名字为名**的占位变量，两条路径一致。

### 已知限制

裸 `？`（不带名字）在表达式中仍无定义：它表示公式模板上的「洞」，没有可求值的
值，报「未定义变量 '？'」。`docs/02` 的既有约定是在需要数字处（如循环分数
`(？/？)`）把 `？` 记为「待定」`-1`；`#：？+？=？` 这类**模板求值**语义待定，
本次未擅自实现。

### 测试

新增解释器 / VM / AOT 三端对拍用例（`++`/`--` 共 11 例含运行期浮点与嵌套角度、
`？` 占位符 5 例）。该步提交时全量 `1696 + 491 = 2187 passed`，无回归；
（后续 `？` 模式库并入同一批改动，最终全量见本文件首条目）

---

## 提交：`50b0267` 后续 — `<<` 角度前缀三端补齐 + AOT 浮点取反/`~bool` 修复

**日期**：2026-10-06

### 变更范围

补齐 `docs/06` 级 6 的 `<<` 角度前缀在**解释器 / MBC VM / 原生 AOT** 三端的缺失。
排查过程中发现并修复了两个**先前存在**的原生 AOT 算术 bug（浮点取反、`~bool`）。

| 项 | 变更前 | 变更后 |
|----|--------|--------|
| `<<n` 角度前缀 | 仅文档描述，三端均不支持 | 三端一致，度数 → 弧度 |
| `<<-90` 等前缀叠加 | 解析器报「期望表达式」 | 任意层 `<<`/`-`/`~`/`^` 叠加可用 |
| AOT 运行期浮点取反 | **静默算错**（`-1.5` → `-1.0`） | 正确 |
| AOT `~bool` | **输出堆指针**（`~真` → `-140699650725569`） | `-2`（对齐 `~int(v)`） |
| AOT `<<` 非法类型 | 静默返回 `null` | 抛可捕获异常 |

### 语义决定

`<<n` 归一化为**弧度数值**而非独立 `Angle` 类型。依据是 docs/06 的示例
`sin(<<30)`：三角内建只吃弧度，故 `<<30` 必须先除以 180 再乘 π 才能得 0.5。
因此 `输出(<<90)` 为 `1.5707963267948966` 而非 `90`。

### 关键修复

1. **`f_deg` 尾部指令错误导致 `0xC0000005`**：新 helper 曾以 `pop rbp; ret`（`5D C3`）
   收尾，在 `box_float` 返回后使进程崩溃。本文件其余 helper（`f_sqrt` / `f_neg` /
   `f_pow`）一律用 `mov rsp,rbp; pop rbp; ret`（`48 89 EC 5D C3`）。修正后 `<<90`
   正常输出 `1.5707963267948966`。
2. **`movsd` 操作数写反**：`F2 0F 10 C1` 的 ModRM `C1` 是「`xmm0 = xmm1`」，会把
   刚算出的度数丢掉、拿未初始化寄存器去乘。应为 `C8`（`xmm1 = xmm0`），与本文件
   `bin_to_xmm2` 的写法一致。
3. **原生浮点取反全错**（先前存在）：`neg` 分支 `read_top_to(0)` 后调 `is_float`，
   而 `is_float` 以 `mov eax,1` / `xor eax,eax` 返回，**rax 被整个清掉**；浮点路径
   再调 `f_neg` 时操作数已成 0/1，于是 `f_neg(1)` = `-1.0`。字面量 `-1.5` 因常量
   折叠不受影响，故长期未被发现。现于浮点路径从栈槽重新读回。文件内其余
   `is_float` 调用点（`_emit_builtin_math_round`/`abs`/`sign`/`int`/`float`、
   `sum`/`max` 循环、`is_float2` 内部、`f_sqrt`）均已核查为安全。
4. **`~bool` 把堆指针当整数**（先前存在）：bool 在原生端是 `bool_true` /
   `bool_false` 两个内部对象的指针，`not rax` 得到 `-(ptr+1)`。现按指针还原成
   0/1 再取反，与解释器/VM 的 `~int(v)` 对齐。
5. **前缀操作数解析**：新增 `_parse_unary_operand()` 递归处理 `<<` / `-` / `~` /
   `^`，使 `-<<90`、`<<-90`、`^<<16` 均可解析；中缀 `<<` 位移不受影响。
6. **AOT 判浮点不用 `is_float`**：`<<` 分支改为自判「是否落在堆区间」+ 查
   `TYPE_FLOAT` 标签，避免上述 rax 被清空问题。

### 测试

新增 69 项回归：`test_new_features.py` 角度语义 7 项、`test_interp_parity.py`
解释器/VM 对拍 19 项、`test_native.py` AOT 角度 13×2 + 角度报错 3×2 +
运行期浮点取反 5×2 + `~bool` 3 项。
全量 pytest **2133 passed**（此前 2064）。

---

## 提交：`50b0267` 后续 — 位运算族三端补齐 + 中缀 `^` 回归规范

**日期**：2026-10-06

### 变更范围

以 `docs/17-完整语法EBNF.md` 与 `docs/06-表达式与运算符.md` 为基准，补齐位运算
`&` `|` `⊕` `~` 在**解释器 / MBC VM / 原生 AOT** 三端的缺失，并修正中缀 `^` 的
语义与优先级。

| 项 | 变更前 | 变更后 |
|----|--------|--------|
| `&` 位与 | 仅解释器 | 三端一致 |
| `\|` 位或 | 仅解释器 | 三端一致 |
| `⊕` 位异或 | 仅解释器，且与 `^` 混用同一 token | 三端一致，独立 `TokenType.OP_XOR` |
| `~` 位取反 | 仅解释器 | 三端一致 |
| 中缀 `^` | 解释器当异或、VM/原生当次方 | **三端统一为次方**（EBNF 2.1 `<power> = "^"`） |
| `^` 结合性 | 左结合 | **右结合**（docs/06 级 5） |
| `^` 优先级 | 低于 `*` | **高于 `*`**（级 5 > 级 4） |
| `~` 作用于 bool | 依赖 `~True`，Python 3.16 将移除 | 显式 `~int(v)`，无弃用告警 |

### 关键修复

1. **`^` 双后端语义冲突**：`src/mbc/compiler.py::_BIN_OPS` 早已把 AST `^` 归约为
   `**`，而 `src/interp.py` 按位异或处理，同一段 `2 ^ 3` 解释器得 1、VM/原生得 8。
   现按规范统一为次方；异或改用专用符号 `⊕`（新增 `TokenType.OP_XOR`，此前
   `⊕` 与 `^` 共用 `OP_BIT_XOR` token，故 `^` 改动会连带影响 `⊕`）。
2. **`^` 结合性与优先级**：`^` 原留在 `_parse_bit_expr`（位运算层），导致
   `2 ^ 3 ^ 2 = 64`（应 512）、`2 ^ 3 * 2 = 64`（应 16）。现移至
   `_parse_pow_expr` 与 `**` 同层，右结合且优先于 `*`。
   docs/06 的示例 `2^2^3 = 2^(2^3) = 256` 现已成立（此前为 64）。
3. **原生 AOT 位运算**：`& | ⊕` 用 `and/or/xor rax,rcx`（`21 C8` / `09 C8` /
   `31 C8`）；`~` 用 `not rax`（`48 F7 D0`）。两侧非整数时走 `raise_rt` 抛可捕获
   异常，而不是把堆地址当整数按位算出垃圾值，也不返回 `null_obj`（后者会把类型
   错误伪装成「无值」）。
   注意原生后端的整数是**裸 int64 而非堆对象**，故判据必须用
   `(rax - heap_base) < HEAP_SIZE`，不能按类型标签解引用 `rax`——早期误用
   `mov edi,[rax]` 直接触发 `0xC0000005` 访问违例。
4. **VM 侧新增** `_bitop()` 校验与 `~` 一元表项，错误类型沿用本模块惯例
   （`RuntimeError`），消息与解释器对齐。

### 语法变更（面向用户）

- 异或请用 `⊕`，不要用 `^`。旧的 `a ^ b`（原意异或）需改写为 `a ⊕ b`。
- `^` 前有操作数为次方（右结合、优先于 `*`），前无操作数仍为开方。

### 测试

新增 57 项回归：位运算族三端对拍 15 项、`^` 规范用例、docs/06 示例核对、
原生 AOT 位运算 26 项、非整数操作数报错与可捕获性 14 项。
全量 pytest **2064 passed**（此前 2007）。

---

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
