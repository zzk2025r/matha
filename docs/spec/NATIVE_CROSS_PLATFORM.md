# Native 跨平台后端设计（Linux x86-64 / ELF64）

> 体检重构路线第 3 阶段功能补全第 4 项「native 跨平台」的立项设计文档。
> 本文只固化设计决策与分期路线，不含实现代码；实现按末尾 Roadmap 另起独立提交。
> 首期范围经用户确认收敛为 **单一目标平台 Linux x86-64（ELF64）** + **最小垂直切片**。

## 0. 背景与动机

现有原生后端 `src/mbc/native.py`（约 1.1 万行）把 Matha 源码经 `src.mbc.compiler.compile_source`
产出 M3V 字节码后，直接发射 **x86-64 机器码**并手写链接为 **Windows PE64 `.exe`**，不经过 C 中转。
它按「砖块」增量已覆盖到字符串 / 列表 / 字典 / 闭包 / 盒 / 异常 / 浮点 / 大整数 / GC / 文件 I/O /
regex / 时间等丰富能力，逐块由 8 个 `tests/test_native*.py`（约 4600 行）锁定回归。

但该后端与 Windows 深度耦合，无法在 Linux / macOS 产出可执行文件。跨平台的本质是同时移植三个
正交维度：

1. **容器格式**：PE64 → ELF64（Linux）/ Mach-O（macOS）。
2. **调用 ABI**：Microsoft x64 → System V AMD64（Linux/macOS x86-64）/ AAPCS64（ARM64）。
3. **系统接口与外部库**：`kernel32`（WriteFile/ExitProcess/VirtualAlloc，经 PEB 自解析）+
   `msvcrt` CRT（sqrt/pow/rint/_ecvt/fopen/…）→ 纯 Linux `syscall` + `libc`/`libm`。

一次性把全部砖块 × 全部平台对齐不现实。本设计据此确立「**平行独立发射器 + 静态纯 syscall +
最小垂直切片先行 + 逐砖块逐平台诚实扩面**」的取向，复用 P6 SPIKE 后端（`baremetal/tools/rv32_spike/`）
已验证成功的工程范式。

## 1. 现状勘察结论

### 1.1 入口链与产物组装

```
compile_to_exe(source) -> bytes            # 便捷入口：source → bytes
  └─ emit_exe(mod) -> bytes                # MModule → PE64 字节串
       ├─ _build_payload(mod)              # 发射 x86-64 机器码，返回 (text, bss, bss_vsize, data, data_vsize)
       │    ├─ _emit_data_section(...)     # 静态数据 / 常量池 / 对象布局
       │    └─ 各 _emit_*_runtime(...)      # 运行时例程（print/heap/gc/seq_dict/fs/encoding…）
       └─ _build_pe(text, bss, …, data, …) # 手写 PE64 头 + 节表 → 可执行字节
```

门面：`src.kernel.exec_api.build_exe(source, out_path) -> Path`（发射失败直接抛，不伪装成功）；
CLI：`python -m src.mbc.cli native 源.matha -o 输出.exe`。

### 1.2 Windows 绑定点（逐处须在 Linux 端给出对应）

- **容器** `_build_pe`：`MZ`/`PE\0\0` 签名、COFF 头 `Machine=0x8664`、可选头 `Magic=0x020B`（PE32+）、
  三节 `.text`/`.bss`/`.data`、`IMAGE_BASE=0x140000000`、`Subsystem=3`（WINDOWS_CUI）、
  `AddressOfEntryPoint` 指向 `_start`。关键常量：`TEXT_RVA=0x1000`、`HEADERS_SIZE=0x200`、
  `VSTACK_SIZE=0x10000`（64KB 操作数栈）、`NUMBUF_SIZE=64`、`HEAP_SIZE=0x40000000`（1GB 固定堆，
  data 段 BSS 按需提交）。
- **系统 API** `_APIS = [GetStdHandle, WriteFile, ExitProcess, LoadLibraryA, GetProcAddress, VirtualAlloc]`：
  不经 PE 导入表，运行期由 `_emit_resolve_apis` 通过遍历 **PEB → Ldr 链表 → 导出表** 自解析地址；
  输出全部走 `WriteFile(GetStdHandle(-11), …)`，退出走 `ExitProcess`，动态堆走 `VirtualAlloc`。
- **CRT 依赖** `_CRT_FUNCS = [_ecvt, strtod, sqrt, pow, floor, fmod, sin, …, fopen/…, _time64/…strftime]`：
  经 `LoadLibraryA("msvcrt"…) + GetProcAddress` 解析。这是浮点格式化、数学内建、文件 I/O、日期时间的底座。
- **调用约定**：Microsoft x64 —— 被调方入口处调用者须预留 **≥32 字节影子空间（shadow space）**，
  `call` 前 `RSP` 16 字节对齐；外部 API 整型参数走 `rcx/rdx/r8/r9`。

### 1.3 平台无关、可复用的部分

- Matha **函数间自调用约定**：`R12` 作操作数栈指针（栈体在数据段，向上增长），局部变量贴原生 `RBP`
  帧（`local i ↔ [rbp - 8*(nlocals-i)]`），参数经操作数栈传递、callee 序言搬入局部槽，`CALL/RET` 帧平衡。
  这些是后端自定义约定，与宿主 OS 无关，可在 Linux 端沿用同一设计。
- **整数算术 / 控制流 / 堆对象头** `[type][len][payload]` 布局（类型标签见 native.py 的 `TYPE_*`）。

### 1.4 门禁归属

`src/mbc/` 计入 `scripts/repo_facts.py` 的 `core_py_lines`（当前基线 31,545）。故任何新增/修改
`src/mbc/*.py` 都改变该数字，须同步 `docs/ARCHITECTURE.md`。`tests/test_doc_facts.py` 为文档漂移锁。

## 2. 架构取向：平行独立发射器，不改造 native.py

新增 `src/mbc/native_elf.py`（Linux x86-64 ELF64 发射器），与 `native.py` **并列**，共享
`src.mbc.compiler.compile_source` 与 `src.mbc.opcodes`，**不 import native.py 的运行时例程**。

理由：
- `native.py` 逾万行、逐砖块深绑 Windows（PEB 解析、CRT、WriteFile、影子空间）。把「OS 薄层」从中
  抽干净需要大范围重构既有发射代码，回归风险与工作量都远超首期收益。
- 平行模块沿用 P6 SPIKE 已验证的闭环范式：字节码 → 机器码直发 → 手写容器 → 逐字节对拍/执行 →
  runner（正例 + 负向断言）。既有 Windows 后端完全不受影响，8 个 `test_native*.py` 无需改动。
- 首期自成体系实现整数子集（见 §6），后续按 Roadmap 增量补齐，不背历史包袱。

## 3. 运行模型：静态、非 PIE、纯 syscall

- **静态 ELF64、非 PIE、固定基址 `0x400000`**；无 libc / libm / 动态链接器 / GOT / PLT / 重定位表。
  这样产物是**自包含**的：只要内核支持 x86-64 Linux ABI 即可运行，`qemu-x86_64`（用户态）能直接执行，
  这正是首期能在 Windows 开发机上间接验证的关键前提。
- **入口** `e_entry = _start`。内核在 `_start` 处把 `argc/argv/envp/auxv` 置于 `RSP` 顶端；首期程序
  不消费命令行参数，只需在进入主逻辑前把 `RSP` 调整回 16 字节对齐（SysV 规定函数被调入口 `(RSP+8)%16==0`）。
- **系统调用面（首期仅两条，最小化）**：
  | 用途 | 约定 |
  |---|---|
  | 写 stdout | `RAX=1 (write)`, `RDI=1 (fd)`, `RSI=buf`, `RDX=len`；`syscall`；返回 `RAX`=已写字节 |
  | 进程退出 | `RAX=231 (exit_group)`, `RDI=exit_code`；`syscall` |
  后续扩面（大对象/动态堆）再引入 `mmap`（`RAX=9`）。
- **删除的 Windows 机制**：PEB/Ldr 遍历、`GetProcAddress`、CRT 解析、影子空间预留，全部不再发射。
- **堆**：首期用 ELF `.bss`（`PT_LOAD` 的 `p_memsz > p_filesz` 零填充区）固定区 **bump 分配**，
  沿用 native.py 的「虚拟零尾不物化进文件」技巧（编译期只记尺寸、不把大堆写进镜像，页由内核按需分配）。
  指针判据 `(v - heap_base) < heap_used` 沿用 native.py 的区间法区分堆对象与裸整数。

## 4. ABI 差异对照

| 维度 | Microsoft x64（现状） | System V AMD64（Linux 目标） |
|---|---|---|
| 被调外部例程栈要求 | 调用者预留 ≥32B 影子空间 | **无影子空间** |
| `call` 前对齐 | RSP ≡ 0 (mod 16) | 被调入口 (RSP+8) ≡ 0 (mod 16)，即 call 前 RSP ≡ 0 (mod 16) |
| 整数参数寄存器 | rcx, rdx, r8, r9 | rdi, rsi, rdx, rcx, r8, r9 |
| 系统调用 | 走 API（WriteFile 等），非 syscall | `syscall` 指令；`RAX`=号，参数 rdi/rsi/rdx/r10/r8/r9，返回 rax；rcx/r11 被破坏 |
| Matha 函数自调用约定 | 操作数栈 R12 + RBP 帧（后端自定义） | 同一设计沿用，与 OS 无关 |

首期整数子集不调用任何外部库函数，故 SysV 整数参数约定主要用于 `syscall` 封装；Matha 函数间
调用仍走后端自定义约定，无需 SysV 参数寄存器。

## 5. 容器设计：`_build_pe` 的 ELF 等价 `_build_elf64`

新增 `_build_elf64(text, bss, bss_vsize, data, data_vsize) -> bytes`，与 `_build_pe` 同签名同职责，
产出 **ELF64 头 + program header 表**（首期可不写 section 表即可运行；为便于 `readelf` 调试可选加最小 SHT）。

固定字段：`e_ident` = {magic `\x7fELF`, `EI_CLASS=2`(64-bit), `EI_DATA=1`(LSB), `EI_OSABI=0`(System V)}；
`e_type=2`（ET_EXEC，非 PIE）；`e_machine=0x3E`（AMD x86-64）；`e_entry`=`_start` 的 vaddr；`e_phentsize=56`；
`e_phnum=2`。

两个 `PT_LOAD`：
| 段 | 内容 | vaddr 布局 | flags |
|---|---|---|---|
| RX | ELF 头 + program headers + `.text`（代码，含 `_start`） | 起于 `0x400000`，`p_offset=0`，代码紧随头后 | `PF_R\|PF_X`(5) |
| RW | `.data`（标量/静态对象）+ `.bss`（操作数栈/固定堆，`p_memsz>p_filesz`） | 页对齐（`p_align=0x1000`）接在 RX 之后 | `PF_R\|PF_W`(6) |

PE ↔ ELF 字段映射（供实现对照）：
| PE64 概念 | ELF64 对应 |
|---|---|
| `IMAGE_BASE=0x140000000` | 基址 `0x400000`（`p_vaddr` 起点） |
| `AddressOfEntryPoint`（`TEXT_RVA`） | `e_entry`（`_start` vaddr） |
| `.text` 节 `VirtualAddress`/`PointerToRawData` | RX `PT_LOAD` 的 `p_vaddr`/`p_offset` |
| `.data` 节 | RW `PT_LOAD` 的文件镜像部分（`p_filesz`） |
| `.bss` 节 `VirtualSize > SizeOfRawData` | RW `PT_LOAD` 的 `p_memsz > p_filesz`（差额零填充） |
| `SectionAlignment=0x1000` / `FileAlignment=0x200` | `p_align=0x1000`（vaddr≡offset mod 页） |
| COFF `Machine=0x8664` | `e_machine=0x3E` |
| 无导入表（PEB 自解析） | 无 `.dynamic`/GOT（纯 syscall） |

## 6. 首期能力子集与诚实边界

沿用 native.py 既有异常类 **`NativeNotSupported`** 作为「越界显式拒绝」信号，集合之外的构造一律抛出，
**绝不臆造乐观默认值 / 数值伪造 / 静默成功**（与 P6 SPIKE 纪律一致）。对拍基准 = `exec_api.run_checked(src, mode="vm")`。

### 6.1 首期覆盖（opcodes.py 命名）

| opcode | 覆盖语义 |
|---|---|
| `PUSH_CONST` | 仅 int64 常量池槽（字符串/浮点常量拒绝） |
| `PUSH_TRUE/PUSH_FALSE/PUSH_NULL` | 标量占位（null 真值性判与 VM 一致） |
| `LOAD_LOCAL/STORE_LOCAL` | 局部槽，int/bool/null 值型跟踪 |
| `LOAD_GLOBAL/STORE_GLOBAL` | 全局标量槽（不含函数地址混型） |
| `BINOP` | 整数 `+ - * // %` 与比较 `== != < > <=`（`//`/`%` 归一到 Python 地板除/取模口径；比较结果带 bool 标记） |
| `UNARYOP` | 仅 `neg`（`-a`，int64 溢出干净失败）与 `not`（真值性取反，带 bool 标记）；`sqrt/cbrt/sum/prod` 等拒绝 |
| `CALL/RET` | 直接调用已定义用户函数（编译期静态解析到标号），argc ≤ 2，实参与返回限标量 |
| `JMP/JZ/JNZ` | if/elif/else 链 + while 后向回跳，分支全路径 |
| `BUILD_LIST` | 堆 bump 分配 `[len, e0..]`，元素限 int/bool（嵌套列表拒绝） |
| `INDEX_GET` | 仅列表 × 整数下标，Python 负索引同口径；越界 → exit_code=1（对应 VM IndexError） |
| 内建 `len` | 列表长度（编译期静态分派） |
| `OUTPUT` | 按编译期值型分派：int64 十进制 / `True`/`False` + 换行（对齐 VM `print`） |
| `HALT` | 正常退出 `exit_group(0)` |

### 6.2 首期显式拒绝（抛 `NativeNotSupported`）

字符串 / 字典 / 闭包 / box / 外域 / 切片 / 解构 / 异常（`RAISE`）/ 浮点 / 大整数 / 文件 I/O / regex /
时间 / GC 动态堆 / `*` 与幂等超出 int64 的溢出 / `FORMULA_SCHEMA`。

### 6.3 扩面砖块登记（后续 Roadmap 逐块补，文档维护此表）

| 能力块 | 依赖新增 | 状态 |
|---|---|---|
| 字符串 + `str_concat/print_repr` | 输出路径扩展 + 堆字节串 | 待做（P-c） |
| 浮点 + repr 逐位对齐 | `libm` 或软浮点 + 手写 `_dtoa`（最大难点） | 待评估 |
| 字典 / GET_ATTR | 堆对象 + 哈希 | 待做 |
| 闭包 / box / 外域 | 环境对象 + 捕获布局 | 待做 |
| 异常 try/catch/raise | 处理器栈 + 长跳转 | 待做 |
| GC 动态堆 | `mmap` + mark-sweep | 待做 |

## 7. 验证与门禁

### 7.1 专用 Gate 脚本（参照 SPIKE，不进主线 check-lite）

新增 `scripts/run_native_elf.py`：
- **正例**：`compile_to_elf(src) -> bytes`（写临时文件）→ 用**目标执行器**跑 → 逐字节比对
  `exec_api.run_checked(src, mode="vm")` 输出；全等记 `ok`。
- **负向例（REJECT_CASES）**：集合之外的源码（字符串值 / 字典 / 浮点 / 闭包 / …）必须被
  `NativeNotSupported` 拒绝，误接受即 FAIL。
- **退出码约定**：0 全绿 / 1 有失败 / 2 无可用执行器如实 SKIP。

**执行器探测优先级**（本机为 Windows，无法直接跑 ELF）：
1. WSL2（`wsl -e ./prog` 或直接 `bash -c`）——真实 Linux 内核，最硬。
2. `qemu-x86_64`（用户态）——静态纯 syscall ELF 可直接执行。
3. 皆不可用 → SKIP（exit 2），与 P6 SPIKE 缺 QEMU 的 SKIP 约定一致。

### 7.2 CI

`.github/workflows` 增 **ubuntu runner job** 跑 `run_native_elf.py`（Linux 原生执行，验证途径最硬，
且不受本机 Windows 限制）。macOS runner 留待后续 ④-b（Mach-O 立项时）。

### 7.3 主线门禁影响与基线

- `native_elf.py` 进 `src/mbc` → `repo_facts.core_py_lines` 增加 → **须同步 `docs/ARCHITECTURE.md`**
  （否则 `test_doc_facts.py` 漂移锁失败）。
- `dep_audit`（依赖方向）、`kernel_purity`（仅 `src/kernel`）预期不受影响，落地后复跑确认。
- 当前主线基线（写入文档以免实现期误判）：`dep_audit` 违规 0、`test_doc_facts` 18/18、
  `kernel_purity` 14、check-lite **4794** 全绿。

## 8. 风险与踩坑（沿用 P6 SPIKE 经验）

- **手写字段错位 → 段不可加载**：ELF 头/program header 任一偏移错即崩溃；以 `readelf -a` +
  执行器首屏自检，先做「最小 hello-int」跑通再加指令。
- **无宿主模拟器兜底**：不像 SPIKE 有 `rv32sim`，x86-64 完整宿主模拟器成本过高。对拍完全依赖真实
  执行器 → **必须保证产物纯 syscall、零外部依赖**，方能被 `qemu-x86_64` 直跑；任何意外 CRT/libm 依赖
  都会让静态 ELF 加载失败。
- **数值口径偏差**：int64 溢出（VM 任意精度 vs 硬件回绕）、`//`/`%` 地板除/取模、比较结果 bool 打印，
  须与 VM 逐字节对齐（复用 native.py 与 SPIKE 已验证的归一逻辑）。
- **对齐陷阱**：`_start` 入口 `RSP` 未按 SysV 调整即 `call`，会让后续依赖 16 字节对齐的例程偶发崩溃。

## 9. Roadmap（本文档确认后另行分步实现，均独立提交）

- **P-a**：`native_elf.py` 骨架（`_build_elf64` + `_start` + write/exit 两条 syscall）+
  整数 / 输出 / 控制流 / `CALL`-`RET` 子集 + Gate 正负例 + CI ubuntu job → 独立 commit。
- **P-b**：`BUILD_LIST` / `INDEX_GET` / `len` + `.bss` bump 堆 → commit。
- **P-c**（各自独立立项）：字符串 → 浮点（libm 或软浮点，最大不确定项）→ 字典 / 闭包 / 异常 / GC。
- **④-b**：macOS Mach-O（x86-64 与/或 arm64）。本机无 macOS 硬件，仅 CI macos runner 验证；
  arm64 需新写整套指令发射器，投入最大，放最后。

## 10. 明确不做 / 假设

- 首期**只** Linux x86-64（用户已确认）；macOS / ARM64 / 全能力对齐均延后。
- 本文档为 ④ 的立项依据；**不改动 `native.py`**、不动主计划文件、不改现有 `test_native*.py`。
- 交付以 `docs/NATIVE_CROSS_PLATFORM.md` 为限；实现代码按 §9 Roadmap 分步、每步独立门禁与提交。
- 验证以 qemu-x86_64 / WSL2 / CI ubuntu 任一可用为准；本机皆不可用时 Gate 如实 SKIP（exit 2），
  以 CI 作为 P-a/P-b 的强制验收途径。
