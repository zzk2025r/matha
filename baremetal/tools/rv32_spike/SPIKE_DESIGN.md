# P6 SPIKE：Matha 字节码 → RV32IM 机器码直发后端（设计与实测口径）

> 状态：**SPIKE（概念验证），非生产后端**。本文档与 `scripts/build_exe.py`、
> `src/mbc/native.py` 同一诚实口径：能力边界全部显式声明，子集外一律
> `NotSupportedRV32` 拒绝，绝不静默产出错误机器码；工具缺失如实 SKIP。

## 1. 目标与定位

`src/mbc/native.py` 已打通 **M3V 字节码 → x86-64 → Windows PE64** 直发。
本 SPIKE 验证第二条后端通路：**同一 `MModule` 输入 → RV32IM 机器码 → 自制
ELF32**，在 stock QEMU `virt`（rv32）上实跑 CALL/RET 与逐步扩展的 opcode
覆盖集（见 §3）——全程纯 Python 位级编码，**不经交叉工具链、不经汇编器、
不经操作系统**。这是 `baremetal/README.md` 登记的「Matha 字节码 → RV 机器码
直发」远期目标的第一块可验证基石。

## 2. 管线（五件套，与 native.py 同构）

```
compile_source ──► MModule（与 native.py 完全同一入口）
     │
     ├─► rv32bc.py  【字节码契约 MBR1】1 字节 OpCode + N×u32 操作数序列化流：
     │        纯指令（操作数=跳转目标/计数/槽位）/ 数据指令（操作数=常量池下标，
     │        须间接解析）二分类由 OPS 表钉死覆盖全部 33 条；magic/版本/arity/
     │        目标越界/截断/非常量 tag 一律 NotSupportedRV32；encode↔decode
     │        roundtrip 与直发入口 ELF 字节一致（runner 强断言）。
     │        注：与主线 src/mbc/serial.py 的 .mbc marshal 容器互不替代。
     ▼
rv32em.py   字节码 → RV32IM 指令流（两遍：标签 → 分支/绝对地址修复） → ELF32 bytes
     │            内部用 rvcoder.py：手工位级编码 + E32 发射器（NativeNotSupported
     │            的 RV32 对应物 = NotSupportedRV32，范围越界/未定义标签显式抛错）
     ├─► rv32sim.py  宿主最小 RV32IM 指令级模拟器（无 QEMU 也能对拍；
     │                未实现指令立即抛错，绝不把未知指令当 nop）
     └─► QEMU virt   stock qemu-system-riscv32 -machine virt -cpu rv32 实跑复核
```

`run_rv32_spike.py` = 端到端 runner：每条用例 **sim 串口输出 ↔ mbc VM 输出逐字节
对拍**，`--qemu` 时再实跑同一 ELF 复核；退出码 0=通过 / 1=失败 / 2=缺 QEMU 如实 SKIP
（与 `run_qemu_virt_demo.py` 同约定）。

## 3. 覆盖集（正式子集 + 静态模式/管道项）

**正式覆盖 opcode（7 条）**：

| opcode | 说明 |
|---|---|
| `PUSH_CONST` | 仅 int32 常量池槽 |
| `BINOP` | `+ - * // % == != < > <=`（`//`/`%` 归一到 Python 地板除/取模语义；比较结果带 bool 标记，直接 OUTPUT 打印 `True`/`False` 与 VM 对齐） |
| `CALL` | 仅直接调用已定义用户函数（编译期静态解析到标号），argc ≤ 2，实参限标量 |
| `RET` | 单值返回（标量/bool；列表与函数值跨边界显式拒绝） |
| `OUTPUT` | 按编译期值型分派：int32 十进制 / `True`/`False` / `[a, b, c]`（Python repr 分隔口径）+ 换行 |
| `BUILD_LIST` | 堆 bump 分配 `[len, e0..en-1]`；元素限 int/bool（嵌套列表拒绝）；堆满干净失败；n ≤ 510（imm12 展开限制） |
| `INDEX_GET` | 仅列表×整数下标；Python 负索引同口径；越界/空表 → exit_err（对应 VM IndexError） |

另有**静态模式/管道项**（不计入正式数，但已支持以让用例能写出来）：
`LOAD_GLOBAL/STORE_GLOBAL`（全局单元**完整语义**：int/bool/list 值均可存读，
编译期 `gtype` 跟踪全局槽类型，同槽混型拒绝；函数直调识别占位值非零，
真值性判与 VM 一致）、`LOAD_LOCAL/STORE_LOCAL`（同样槽类型跟踪）、
`JMP/JZ/JNZ`（**分支全路径**：if/elif/else 链 + while/for 后向回跳；B 分支 ±4KB
越界由 E32 显式拒绝；JZ/JNZ 对列表取长度判真假，空表=假与 Python 口径一致）、
`POP/PUSH_NULL`（语句位丢弃形状；null 占位值 0 使真值性判自然一致，null 参与
==/!= 编译期静态折叠，排序比较/跨函数边界拒绝）、`PUSH_TRUE/PUSH_FALSE`（bool 标记）、
`HALT`；另有**内建表** `len`/`get`（for 句型由编译器降为 len/get 内建调用，
SPIKE 编译期静态融入指令序列，不建运行时函数对象；其他内建仍走「未定义全局」拒绝）。
集合之外（UNARYOP、MAKE_CLOSURE/闭包/间接调用/一阶、BUILD_DICT/DUP/UNPACK_SEQ/
GET_ATTR/box 系、float/字符串值（PUSH_CONST 指字符串显式拒绝，不 KeyError）、
列表/null 跨函数边界、列表拼接/相等、arity>2 等）一律 `NotSupportedRV32` 显式拒绝；
runner 另有负向例（REJECT_CASES）断言这些源码**必须被拒绝**，误接受即 FAIL。

## 4. 运行模型（固定地址，无任何 OS/链接器参与）

- 内存布局（单 PT_LOAD RWX，vaddr=0x80000000，与 `qemu_virt_demo/virt.ld` 同基址）：
  `code | 0x10000 间隙 | 常量池 | 全局区 0x1000 | 表达式栈 0x10000 | 调用栈预留带
  0x10000 | 堆 0x20000（列表 bump，首字存分配指针，_start 初始化）`。
- 自定义 SPIKE ABI（非标准 ilp32，寄存器编号互不冲突）：
  SP=x2 RA=x1 R_FP=x8 R_CPOOL=x9 R_GLOB=x14 R_UART=x15 R_EBP=x16 R_A0=x10 R_A1=x11
  R_T0-2=x5/6/7 R_T3-5=x28/29/30。
- 双栈：表达式栈在 SCRATCH 区向上增长（R_EBP），调用帧链向下（R_FP/RA 保存于帧内）；
  main 内联于 `_start` 也建伪帧，保证被调 RET 恢复 FP/SP 自洽。
- 值模型 = 裸 int32 + **编译期标记的列表指针**（无运行时类型 tag：stk/ltype/
  gtype 三处静态跟踪，路径混型即拒绝，绝不静默把列表指针当整数运算）：
  溢出/除零/索引越界/堆满**干净失败**（跳 `exit_err`，finish word 退出码 1），
  不伪造数值——对齐 native 后端 1a/1c 红线。
- I/O：ns16550 UART@0x10000000 MMIO 直写（putc 轮询 LSR bit5 → THR）。
- 退出：写 sifive_test@0x00100000 finish word（低 16 位 `0x5555`，高 16 位=退出码）。

## 5. QEMU 实跑踩过的硬约束（诚实记录，全部实证）

1. **自制 ELF 必须带最小 section 表**（NULL + .shstrtab，且 4 字节对齐）：
   QEMU `load_elf` 对 `e_shoff=0` 的 ELF 拒识别，`-kernel` 退回 raw 整体加载，
   ELF 头被当指令执行 → illegal instruction。
2. **`-bios none` 下 ecall 无人接管**（代码在 M-mode），SBI 退出约定是死路；
   退出必须走 sifive_test MMIO（dtb 实证 `test@100000` 存在）。
3. **ns16550 寄存器是字节宽度 MMIO**：32 位 `lw` 读 LSR 拿不到值导致轮询死循环，
   必须 `lbu/sb`（与 demo uart.c 同口径）。
4. **宿主 sim 宽松解码会掩盖硬件级编码 bug**（本 SPIKE 实际抓到两例）：
   - `SLT/SLTU` funct7 误写成 0x20 → QEMU illegal，sim 却照跑；
   - `SRAI` funct6 位置写错（0x20|sh 应为 0x400|sh）→ QEMU illegal。
   修复纪律：sim 对 funct6/funct7 非法组合一律 raise（严格化 = 与硬件同判）。
5. **模拟器立即数符号扩展**：I/S 型 12 位立即数不符号扩展会让所有负偏移
   （`addi x,x,-4`）变成 +4092——一次性废掉 push/pop、帧建立、print_int 全部路径。

## 6. 实测结果（2026-10-31 扩展后，本机；首轮 5 例见 git 历史）

`python baremetal/tools/rv32_spike/run_rv32_spike.py --qemu`

| 用例 | 覆盖点 | sim↔VM | QEMU virt |
|---|---|---|---|
| s1_const_binop_output | PUSH_CONST/BINOP/OUTPUT | ✅ `14\n6\n` | ✅ |
| s2_call_ret | CALL/RET 双参 | ✅ `7\n8\n` | ✅ |
| s3_recursion | if/else + 递归 CALL（fact 6=720） | ✅ `720\n` | ✅ |
| s4_floordiv_mod | `//`/`%` Python 语义归一 | ✅ `3\n-4\n1\n2\n` | ✅ |
| s5_call_ret_mul | 嵌套调用 sq(sq(3)) | ✅ `81\n81\n` | ✅ |
| s6_branch_full | while 后向回跳累加 + 函数内 if/elif/else 链 | ✅ `10\n3\n2\n0\n` | ✅ |
| s7_list_build_index | BUILD_LIST 字面量打印 + 正/负 INDEX_GET | ✅ `[3, 1, 4, 1, 5]\n20\n30\n40\n` | ✅ |
| s8_bool_output | 比较结果直接 OUTPUT（True/False 与 VM 对齐） | ✅ `True\nFalse\nTrue\n` | ✅ |
| s9_list_global_loop | 全局列表 + while 循环索引累加 + 整表打印 | ✅ `14\n[2, 4, 8]\n` | ✅ |
| s10_for_if_nested | for 句型（内建 len/get）× 块式 if 嵌套 | ✅ `12\n` | ✅ |
| s11_for_ifelse_nested | for×if/else + for×for 双重嵌套回跳 | ✅ `12\n4\n` | ✅ |
| s12_stmt_discard | 语句位 if-then-else 产生的 POP/PUSH_NULL 丢弃形状 | ✅ `0\n0\n` | ✅ |
| s13_contract_roundtrip | MBR1 encode→decode 消费面等价且 ELF 字节一致 | ✅ | — |

另有 5 条负向例（r1 字符串值、r2 闭包、r3 列表传参、r4 列表拼接、r5 字典字面量）
均被 `NotSupportedRV32` 显式拒绝 ✅。

QEMU 11.1.93 stock `qemu-system-riscv32`，全部干净退出（rc=0，串口文本含 VM 每行）。

## 7. 已知边界与通往生产的路

- **契约轮已收**：`rv32bc.py` MBR1 序列化字节码契约（1B op + N×u32，纯/数据二分类，
  严格校验）；for 句型解锁（内建表 len/get）；POP/PUSH_NULL；PUSH_CONST 字符串
  显式拒绝（堵 KeyError 洞）。
- **上轮已收**：条件分支全路径（if/elif/else 链 + while/for 后向回跳）、
  LOAD_GLOBAL/STORE_GLOBAL 完整语义（含 bool/list/null 值）、列表构造与索引。
- 33 条总进度：**支持集 19/33**（7 正式 + 12 管道项）+ 内建表 len/get；余下 14 条
  （LOAD_BOX/MAKE_BOX/STORE_BOX/LOAD_OUTER/LOAD_OUTER_BOX/MAKE_CLOSURE/UNARYOP/
  BUILD_DICT/BUILD_SLICE/GET_ATTR/UNPACK_SEQ/DUP/RAISE/FORMULA_SCHEMA）各自需要
  运行时类型 tag、闭包环境模型、dict/str 堆对象或异常栈——属生产后端工作，见下。
- `print_int` 未覆盖 INT_MIN 取负边界（设计内显式登记）；mul 溢出检测在
  a==0 时放行（(0*b)/0 不可算，但 0*b 本身不溢出，安全）。
- 列表仅单作用域内流转：传参/返回/存后跨作用域读回列表均拒绝；null 同样禁止
  跨函数边界（值型丢失）；无 GC（bump 只增不减，堆满干净失败）；嵌套列表/字典/
  字符串未覆盖。
- CALL 静态解析要求函数值仅来自 `LOAD_GLOBAL` 直接引用；偏应用/闭包/一等功能
  需要真正的函数对象与调用约定设计（box/outer 系 op 同源）。
- 生产化缺件清单（余下）：标准调用约定与浮点/bool/字符串运行时值模型（本轮
  bool 仅编译期标记）、GC/堆、异常与非局部跳转、跳转表与更大代码段（B 分支
  ±4KB 已显式校验）、真板 FE310 适配（本 SPIKE 与 board-matched demo 同口径：
  QEMU 实跑 ≠ 真板实测）。
- 本目录不进任何门禁（`baremetal/tools/` 与 `scripts/check.py` 六项完全隔离）。
