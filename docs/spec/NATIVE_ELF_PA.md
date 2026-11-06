# Native ELF 后端 · P-a 阶段落地设计与分期路线图

> 本文是 [`NATIVE_CROSS_PLATFORM.md`](./NATIVE_CROSS_PLATFORM.md)（④ 立项总设计）的执行细化，
> 聚焦 **P-a 阶段**的子任务拆解、验证方式与风险点，并给出跨期 Roadmap。
> 本轮只产出文档，**不写实现代码、不提交**；经确认后再按本文动工。
> 首期目标平台锁定 **Linux x86-64 / ELF64**，范围 **最小垂直切片**（用户已确认）。

---

## 一、分期 Roadmap（细化）

总设计把实现切成 P-a / P-b / P-c / ④-b。本表细化每期的**范围、交付物、验收、门禁影响、退出准则**。
P-a 是本文重点，其余期为对齐上下文列出的骨架。

| 期 | 范围（能力子集） | 核心交付物 | 验收（全绿才收期） | 门禁影响 | 退出准则 |
|---|---|---|---|---|---|
| **P-a** | 整数常量/算术(`+ - * // %`)/比较(`== != < > <=`)/一元 `neg`/`not`、bool/null 标量、局部+全局标量槽、控制流 `JMP/JZ/JNZ`(if/elif/else+while)、`CALL/RET`(直接/递归,argc≤2,标量)、`OUTPUT`(整数/bool)、`HALT` | `src/mbc/native_elf.py`（ELF64 发射器）+ `scripts/run_native_elf.py`（Gate）+ CI ubuntu job | Gate ≥8 正例 sim↔VM 逐字节一致 + ≥4 负向例显式拒绝 + `readelf` 结构自检；主线 check-lite 复跑不破 | `native_elf.py` 入 `src/mbc` → `core_py_lines` 增，同步 `ARCHITECTURE.md` | 三执行器任一（WSL2/qemu-x86_64/CI）跑通全部正例且退出码语义正确 |
| **P-b** | `BUILD_LIST`/`INDEX_GET`(负索引)/内建 `len` + `.bss` bump 堆（列表元素限 int/bool） | native_elf.py 扩堆与列表指令；Gate 补列表例 | 列表用例逐字节对齐 VM；堆越界/嵌套列表显式拒 | 同上，`core_py_lines` 再增 | 列表构造/索引/负索引/len 全绿 |
| **P-c** | 字符串 → 浮点(libm 或软浮点) → 字典/闭包/box/外域 → 异常 → GC 动态堆 | 逐块扩展 + 每块对拍 | 每块单独立小提交，逐块登记扩面表 | 同 P-a/P-b | 见总设计 §6.3 扩面砖块表逐行转「已支持」 |
| **④-b** | macOS Mach-O（x86-64，视需求再评估 arm64） | 容器层 `_build_macho` + libSystem/syscall 适配 + CI macos runner | 本机无硬件，**仅 CI** 验证 | 视放置目录 | 立项时另出设计文档 |

关键次序原则：**P-a 内部再按 M0→M5 里程碑自底向上**（见第三节），每个里程碑都是一个可独立验证的最小闭环，
杜绝"全写完才第一次能跑"。

---

## 二、P-a 设计边界（做什么 / 不做什么）

### 2.1 做
- 静态、非 PIE、固定基址 `0x400000` 的 ELF64；无 libc/libm/动态链接器/GOT/PLT。
- 两条系统调用：`write`(rax=1) 输出、`exit_group`(rax=231) 退出。
- 复用 Matha 后端自定义调用约定：操作数栈指针 `R12`、局部贴 `RBP` 帧、整数算术、控制流、
  `CALL/RET` 帧平衡（这些与宿主 OS 无关，沿用 `native.py` 的设计思路，代码独立实现）。
- 唯一需平台化的输出路径：把 `write_span`（`native.py` 里走 `WriteFile`）改写为 `syscall write(1,buf,len)`。
- 整数→十进制打印逻辑（`native.py::_emit_print_int` 的 `div` 循环）平台无关，照搬思路独立实现。

### 2.2 不做（P-a 一律 `NativeNotSupported` 显式拒绝）
- 列表 / 字符串 / 字典 / 闭包 / box / 外域 / 切片 / 解构 / 异常(`RAISE`) / 浮点 / 大整数 /
  文件 IO / regex / 时间 / `FORMULA_SCHEMA` / 动态堆 GC。
- 超出 int64 的算术溢出（策略见 §6 开放问题 Q2）。
- **注意**：P-a 不发射任何列表/堆相关指令，故 P-a 阶段 `native_elf.py` **无需 `.bss` 大堆区**，
  仅需操作数栈缓冲（`vstack`）与整数输出缓冲（`numbuf`）两块小 BSS。堆留给 P-b。

---

## 三、P-a 内部里程碑（自底向上，每个都可独立验证）

### M0：能加载的 ELF 壳（先不跑业务）
- `_build_elf64(text, bss_vsize, data) -> bytes`：ELF64 头(64B) + 2 个 `PT_LOAD`
  （RX=头+phdr+text，`p_vaddr=0x400000`,`p_offset=0`,`p_flags=PF_R|PF_X`；
  RW=data+bss，页对齐 `p_align=0x1000`，`p_memsz>p_filesz` 零填充）；`e_ident`(magic/ELFCLASS64/LSB/SystemV)、
  `e_type=ET_EXEC(2)`、`e_machine=0x3E`、`e_entry=_start`、`e_phentsize=56`、`e_phnum=2`。
- 手写 `_start` 仅做：把 `0x400000` 段里的一个常量字节串（如 `"hello\n"`）经 `write(1,...)` 输出，再 `exit_group(0)`。
- **验收**：`readelf -h -l <elf>` 结构正确；任一执行器运行打印 `hello`；退出码 0。
- **DoD**：给出 PE↔ELF 字段的落地自检清单（对照总设计 §5 表）。

### M1：可复用的输出与退出原语
- `write_span`（Linux 版）：入参 `rsi=buf`,`rdx=len`；循环 `write(1)` 处理**部分写**（返回值 < len 时续写剩余）与
  `EINTR`(rax 为负 `-4`，重试)。放在数据段的 `numbuf`(64B)。
- `print_int`：`rax=整数` → 判符号 → `div 10` 逐位填 `numbuf` → 调 `write_span` → 追加 `\n`。
  **输出行尾统一 `\n`（LF），与 `exec_api.run_checked(mode="vm")` 的 `print` 逐字节对齐**
  （`native.py` 的 Windows exe 用 CRLF，跨平台对拍以 VM 的 LF 为准，见 §6 Q3）。
- `print_bool`：`True`/`False` 字面量（与 VM `str(True)` 一致）。
- `_start`：记录必要全局、`lea r12,[vstack]`、按 SysV 调整 `RSP`（进入时内核给 `argc`，
  先对齐到 `(rsp+8)%16==0` 再 `call main_entry`）、末尾 `exit_group`。
- **验收**：M0 的程序升级为「用 `print_int` 打印硬编码 `42`」，执行器输出 `42\n`。

### M2：字节码 dispatch 骨架 + 整数算术
- `compile_to_elf(source)->bytes`：`compile_source` → 遍历 `mod.main_code` 指令流 → 逐条 `_emit_*`；
  `NativeNotSupported` 守卫在每个发射点。
- 常量与算术：`PUSH_CONST`(仅 int)、`PUSH_TRUE/FALSE/NULL`、`BINOP`(`+ - * // %`)、`UNARYOP`(`neg`,`not`)、
  比较(`== != < > <=` 带 bool 标记)、`OUTPUT`、`HALT`、`POP`/`DUP`。
  `//`/`%` 归一到 Python 地板除/取模（复用 `native.py`/SPIKE 已验证的向零截断后修正逻辑）。
- **验收**：Gate 用例 `s1_const_binop_output` / `s4_floordiv_mod`（整数算术、地板除取模）逐字节对齐 VM。

### M3：标量变量槽 + 控制流
- `LOAD_LOCAL/STORE_LOCAL`、`LOAD_GLOBAL/STORE_GLOBAL`（标量 int/bool/null，编译期值型跟踪，混型拒）、
  `JMP/JZ/JNZ`（if/elif/else 链 + while 后向回跳，分支全路径；rel32 两遍修复）。
- **验收**：`s6_branch_full`（while 累加 + if/elif/else）对齐 VM。

### M4：函数调用与递归
- `CALL/RET`：编译期静态解析目标到标号；argc ≤ 2；参数经操作数栈传递、callee 序言搬入局部槽、`RET` 帧平衡；
  支持自递归（如 `fact`）。标量入参/返回；跨边界的列表/null/函数值拒。
- **验收**：`s2_call_ret` / `s3_recursion` / `s5_call_ret_mul` 对齐 VM。

### M5：Gate 脚本 + CI + 文档门禁收尾（收 P-a 期）
- 落地 `scripts/run_native_elf.py`（见第四节）；接入 CI ubuntu job（见第五节）；
  同步 `docs/ARCHITECTURE.md` 的 `core_py_lines`；CHANGELOG 记一条（无性能数字口径）。
- **验收**：Gate 全绿 + 主线 check-lite 复跑不破 + `test_doc_facts` 绿。

---

## 四、P-a 验证方式（分层，缺一不可）

| 层 | 手段 | 判定 |
|---|---|---|
| L1 结构 | `readelf -h -l <elf>`（CI/WSL 侧）+ 本模块自检函数 | ELF 头/program header 字段合法、段可加载、entry 落在 RX 段 |
| L2 可执行 | 执行器实跑，捕获 stdout + exit code | 进程正常退出、无段错误/加载失败 |
| L3 逐字节对拍 | 正例：`compile_to_elf(src)` 输出 ↔ `exec_api.run_checked(src, mode="vm")` 输出，逐字节全等 | 全等记 `ok`；任一差即 FAIL |
| L4 诚实边界 | 负向 `REJECT_CASES`（字符串/列表/浮点/闭包/字典源码） | **必须**抛 `NativeNotSupported`；误接受即 FAIL |
| L5 门禁 | `dep_audit`（方向）/`test_doc_facts`（`core_py_lines` 同步）/`kernel_purity`（不受影响）/check-lite 全量 | 全绿；文档数字与 `repo_facts` 一致 |

**执行器探测优先级**（本机 Windows 无法直接跑 ELF）：
1. WSL2（`wsl.exe -e <distro> -- <elf>`）——真实 Linux 内核，最硬。
2. `qemu-x86_64 <elf>`——静态纯 syscall ELF 可直接用户态执行（前提：产物零外部依赖）。
3. 皆不可用 → Gate 如实 **SKIP（exit 2）**，以 **CI ubuntu job** 作为强制验收途径。
退出码约定沿用 `run_rv32_spike.py`：`0` 全绿 / `1` 有失败 / `2` SKIP。

Gate 脚本结构（蓝本 = `run_rv32_spike.py`）：
- 内嵌 `CASES: dict[str,str]`（`.matha` 源码字符串，覆盖 M2–M4 各里程碑，避免向仓库语料/门禁增添 `.matha` 面）；
- `vm_plain(src)=exec_api.run_checked(src, mode="vm")` 归一输出文本；`elf_plain(src)=compile_to_elf→写临时文件→执行器跑→stdout`；
- 正例逐字节比对；`REJECT_CASES` 断言 `compile_to_elf` 抛 `NativeNotSupported`；
- 执行器探测函数返回可调用 runner 或 `None`（触发 SKIP）。

**正例最小集（P-a 收期门槛，≥8）**：常量算术、地板除/取模（含负操作数）、比较+bool 打印、
局部/全局标量、while 累加、if/elif/else 择一、直接调用、递归（fact）。
**负向集（≥4）**：字符串字面量、`[1,2,3]` 列表、`1.5` 浮点、`func f=... 闭包/高阶`。

---

## 五、CI 设计（P-a）

- 在 `.github/workflows/` 现有门禁工作流内新增（或复用一个）`ubuntu-latest` job：
  - 步骤：checkout → 装 Python → `python scripts/run_native_elf.py`（Linux 原生直接跑 ELF，无需 qemu）→ 断言 exit 0。
  - 该 job 独立于主线 check-lite；即使本机开发时无执行器，CI 兜底强制验收。
- **不**把 `run_native_elf.py` 塞进主线 `check.py`（依赖真实执行器，同 SPIKE 的 `run_rv32_spike.py` 入门禁隔离约定思路）；
  但它**发射器本体 `native_elf.py` 在 `src/mbc`**，会进 `repo_facts.core_py_lines`，故必须同步 `ARCHITECTURE.md`（L5）。
- macOS runner 留待 ④-b（本文不含）。

---

## 六、开放问题（动工前需你拍板）

- **Q1 本机执行器**：你当前是否有可用的 **WSL2** 或 **qemu-x86_64**？
  若都没有，P-a 本地只能做到「生成 ELF + `readelf` 自检 + 负向例」，逐字节对拍要**首次靠 CI 跑绿**（拉一次 CI 才知道结果）。
- **Q2 int64 溢出策略**：算术溢出时是（a）编译期/运行期干净失败抛 `NativeNotSupported`（对齐 SPIKE 的 `INT_MIN` 口径），还是
  （b）按 int64 硬件回绕（与 VM 任意精度不一致，需在扩面表登记偏差）？**建议 (a)**，用例只用不溢出的小整数。
- **Q3 输出行尾口径**：确认 P-a 对拍以 VM 的 **LF(`\n`)** 为唯一真值（`native.py` Windows exe 的 CRLF 不参与对拍）。**建议确认 LF**。
- **Q4 测试落点**：`native_elf` 的正/负例只放 `scripts/run_native_elf.py`（Gate，不入门禁），还是**同时**加一份
  `tests/test_native_elf.py`（进 pytest，但仅在探到执行器时跑、否则 `pytest.skip`）？**建议**：Gate 脚本为主 + 一份
  `tests/test_native_elf.py` 只做「发射结构 + 负向拒绝 + 无执行器则 skip 对拍」的轻量 pytest，兼顾门禁可见性与诚实 SKIP。

---

## 七、风险点与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| ELF 头/phdr 手写字段/偏移错位 | 段不可加载、`readelf` 报错、加载即崩 | M0 先做「hello 壳」单点闭环；`readelf -h -l` + 执行器首屏自检；字段逐一对照总设计 §5 映射表 |
| `_start` 未按 SysV 对齐 | 后续依赖 16B 对齐的例程偶发崩溃 | 进入即 `(rsp+8)%16` 校正；所有 `call` 前维护对齐；去掉 Windows 影子空间假设 |
| 无 x86-64 宿主模拟器 | 对拍完全依赖真实执行器，本机可能探不到 | 产物保证纯 syscall 零外部依赖 → qemu-x86_64 可直跑；CI ubuntu 兜底；无执行器如实 SKIP（不判成功） |
| `write` 部分写 / EINTR | 大输出截断或偶发少字节 | `write_span` 循环续写 + 负 errno 重试（M1 即覆盖） |
| 行尾 CRLF/LF 混用 | 逐字节对拍恒差 1B | 统一以 VM 的 LF 为真值（Q3）；发射器只写 `\n` |
| int64 溢出 / 地板除 / 取模负数口径 | 与 VM 数值不一致 | 复用 `native.py`/SPIKE 已验证的归一逻辑；溢出按 Q2 (a) 干净失败；用例规避 |
| `compile_source` 对某些构造的既有 VM 偏差（如列表推导历史静默失败） | 用例选到偏差构造导致基准本身可疑 | P-a 正例只取整数/控制流/调用等干净子集，与 SPIKE 同源用例口径 |
| `native_elf.py` 进 `src/mbc` 改变 `core_py_lines` | `test_doc_facts` 漂移锁红 | 收期前同步 `ARCHITECTURE.md`；L5 门禁复跑确认 |
| 依赖方向（dep_audit） | 反向 import 违规 | `native_elf.py` 只依赖 `compiler`/`opcodes`（同层向下），不引 `native.py`；dep_audit 复跑 |

---

## 八、P-a 交付物清单（确认即按此产出）

- `src/mbc/native_elf.py`：`_build_elf64` / `_Emitter`(或复用极简发射工具) / `_start`/`write_span`/`print_int`/`print_bool` /
  dispatch + 各 `_emit_*`（M2–M4 指令）/ `compile_to_elf(source)->bytes` / `emit_elf(mod)->bytes`。
- `scripts/run_native_elf.py`：Gate（CASES + REJECT_CASES + 执行器探测 + 退出码 0/1/2）。
- （Q4 若同意）`tests/test_native_elf.py`：结构自检 + 负向拒绝 + 执行器缺则 skip 的轻量 pytest。
- CI：门禁工作流新增 ubuntu job 调 `run_native_elf.py`。
- 文档同步：`docs/ARCHITECTURE.md`（`core_py_lines`）、`CHANGELOG.md`（P-a 条目，无性能数字）、
  `docs/spec/NATIVE_CROSS_PLATFORM.md` §6.3 扩面表把「控制流/调用/整数」行转「P-a 已支持」。

## 九、提交切分（收 P-a 时的 commit 粒度）
- 每个里程碑（M0–M5）本地/CI 全绿后可各自成 checkpoint，最终 P-a 收期建议**单 PR 内分步提交**
  （M0 壳 → M1 输出 → M2 算术 → M3 控制流 → M4 调用 → M5 Gate/CI/文档），保持可回滚。

---

*待你确认本文（尤其 §6 四个开放问题）后，再开始 M0 编码。*
