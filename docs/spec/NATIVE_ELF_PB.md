# Native ELF 后端 · P-b 阶段落地设计与分期路线图

> 本文是 [`NATIVE_CROSS_PLATFORM.md`](./NATIVE_CROSS_PLATFORM.md)（④ 立项总设计）与
> [`NATIVE_ELF_PA.md`](./NATIVE_ELF_PA.md)（P-a 落地）的接续，聚焦 **P-b 阶段**：在 P-a 整数骨架之上
> 引入 **列表 + `.bss` bump 堆**。
> 本轮只产出文档，**不写实现代码、不提交**；经确认（尤其 §六 四个开放问题）后再按 §三 里程碑动工。
> 目标平台不变：**Linux x86-64 / ELF64**，与 `native.py`（Windows PE）平行独立，不 import 之。

---

## 一、P-b 范围（做什么 / 不做什么）

总设计 §6.3 把 P-b 定义为「`BUILD_LIST` / `INDEX_GET`(负索引) / 内建 `len` + `.bss` bump 堆（列表元素限 int/bool）」。
本细化文档据此锁定边界。对拍基准仍是 `exec_api.run_checked(src, mode="vm")`（LF 行尾）。

### 1.1 做

| opcode / 构造 | P-b 覆盖语义 | VM 真值锚点（`src/mbc/vm.py`） |
|---|---|---|
| `BUILD_LIST n` | 弹出 n 个元素（书写序）→ 堆上建表；**含 n=0 空表** | L891-899：`st[-n:]` 保序压列表 |
| `INDEX_GET` | 弹 index、弹 container，压 `container[index]`；**Python 同口径负索引** | L874-884：`c[idx]`，越界透传 `IndexError` |
| 内建 `len(l)` | 编译期识别 `LOAD_GLOBAL "len"` + `CALL 1` → 运行期取表头长度字 | L511：`b["len"]=len` |
| 列表承载 | 标量域内：模块级/局部 `let l=[...]` 经 `STORE_GLOBAL/STORE_LOCAL` 传**表指针**（8B），`gtype`/影子 typ 栈标注 `("list", eltyp)` | — |
| 列表 × 算术/控制流 | `l[i]`（→ int/bool）参与既有 `BINOP`、`if`、`while i < len(l)` 遍历 | — |

### 1.2 不做（一律 `NativeNotSupported` 显式拒绝，不臆造 / 不数值伪造）

- **嵌套列表** `[[1,2],[3]]`、**混合元素类型** `[1, True]`（int/bool 混排，OUTPUT 分派无法静态唯一）、
  元素含 **字符串 / 浮点 / 字典** → 拒。
- **列表整体输出** `#1：[l]`（需 `str(list)` repr 字符串构建）→ 归 **P-c 字符串**。
- **列表比较 / 相等 / 连接**（`BINOP` 作用于 list 操作数）→ 拒。
- **`BUILD_SLICE` / `BUILD_DICT` / `GET_ATTR` / `UNPACK_SEQ`** → 拒（`opcodes.py` L43-45,L51）。
- **对非列表取下标** `5[0]`（container 影子 typ 非 `("list",*)`）→ 编译期拒；
  （VM 端 L883 给 `MathaRuntimeError`，本后端更早、在发射期即拒）。
- **跨 `CALL`/`RET` 边界传列表**（作实参或返回值）→ **P-b 不做**（见开放问题 Q3），保持 P-a 标量 ABI 纯净。
- 列表**可变**：`opcodes.py` 无 `INDEX_SET`，Matha 列表本就不可变，故 P-b 无原地写需求。

---

## 二、内存布局与堆设计（关键决策）

沿用 P-a 固定布局（基址 `0x400000`，`DATA_VADDR=0x410000`，两 `PT_LOAD`），在 `.bss` 零尾区新增堆段：

| 区 | 起点偏移（相对 `DATA_VADDR`） | 大小 | 说明 |
|---|---|---|---|
| 操作数栈 `rbx` | `VSP_OFF=0x100` | `VSTACK_SIZE=0x10000` | P-a 已有；栈顶值在 `[rbx-8]` |
| 全局标量/指针槽 | `GVARS_OFF=0x20000` | `8×len(gmap)` | P-a 已有；P-b 起槽内可存**表指针** |
| **堆（新）** | `HEAP_OFF=0x30000` | `HEAP_SIZE=0x80000`（512KB） | `.bss` 零页**不物化进文件**（`p_memsz>p_filesz`）；bump 分配 |

- **bump 指针 = 寄存器 `r12`**：SysV **callee-saved**，P-a/P-b 自身代码生成不占用它；`_start` 处
  `mov r12, HEAP_ADDR`，分配即 `alloc(sz)`: 用 `r12` 当前值作块首、`add r12, sz`。**只增不减、无回收**
  （GC 动态堆留 P-c；P-b 用例规模远小于 512KB，见 §七风险）。
- **列表对象表示**（最简）：`[ len: 8B ][ e0: 8B ][ e1: 8B ] ...`。**不带类型标签**——因为运行期不做
  指针/整数多态判别，值型完全由编译期影子 typ 栈静态决定（OUTPUT 只会收到已定型 int/bool 标量）。
- **地址公式**：元素 `i`（已归一非负）→ `[listptr + 8 + 8*i]`；表头长度 → `[listptr]`。
- **发射器 memsz 计算扩展**：P-a 取 `max(VSP_OFF+VSTACK_SIZE, GVARS_OFF+8*len(gmap))`；
  P-b 追加 `HEAP_OFF+HEAP_SIZE` 项，确保堆零尾进 `p_memsz`。

### 2.1 影子 typ 栈扩展

P-a typ 域：`int | bool | null | ("fn", name)`。P-b 新增两类：
- `("list", eltyp)`：`eltyp ∈ {int, bool}`，`BUILD_LIST` 当且仅当 n 个元素 typ **全相同**才产出，否则拒。
- `("builtin", "len")`：`LOAD_GLOBAL "len"` 的编译期标记（不落入 `gmap`，规避 P-a 的 `undefined_global` 拒）。

`OUTPUT` / `INDEX_GET` 结果 typ 由上述静态推导：`INDEX_GET(("list",et))[int] → et`；`len → int`。

---

## 三、P-b 内部里程碑（自底向上，每个都是可独立验证的最小闭环）

> 纪律同 P-a：**杜绝"全写完才第一次能跑"**。每里程碑末尾在 WSL/CI 实跑并逐字节对拍后方可提交。

### N0：堆区 + bump 分配 + `BUILD_LIST` + `len`（先勘察字节码）
- **先做字节码勘察**（对齐 P-a 每里程碑的"勘察"步骤）：用 `compile_source` 打印
  `let l = [10,20,30]\n#1：[len(l)]` 与空表 `[].len` 的真实指令流，锁定 ① `BUILD_LIST n` 的 n 编码位置、
  ② `len(l)` 是否为 `LOAD_GLOBAL len; LOAD_GLOBAL l; CALL 1` 的确切形态、③ 元素压栈序与 `st[-n:]` 保序关系。
- 落地：`_start` 初始化 `r12=HEAP_ADDR`；`_emit_build_list(buf,n)` 分配 `8+8n`、写长度字、把
  `[rbx-8n .. rbx-8]` 逐槽搬入堆块、`sub rbx,8n`、压回表指针并注 `("list",eltyp)`；
  `LOAD_GLOBAL "len"` → `("builtin","len")` 标记；`CALL` 遇该标记 → 运行期 `[arg]` 取长度字压 int。
- **验收**：`let l=[10,20,30]` `#1：[len(l)]` 实跑输出 `3`；空表 `#1：[len([])]` 输出 `0`。逐字节对齐 VM。

### N1：`INDEX_GET` 正/负索引 + 越界行为
- `_emit_index_get`：弹 index、弹 listptr（typ 校验为 list）；`if idx<0: idx += [listptr]`；
  边界 `0<=idx<len` 否则 `exit_group(1)`；`mov rax,[listptr+8+8*idx]` 压回，typ=eltyp。
- **验收**：`#1：[l[1]]`→`20`、`#1：[l[-1]]`→`30`、`#1：[l[-3]]`→`10`；越界 `l[3]`/`l[-4]` 退出码 1（行为断言，见 Q2）。

### N2：元素类型完整 + 列表进全局/局部槽 + 混合/嵌套拒
- `STORE_GLOBAL/STORE_LOCAL` 承载表指针（8B 地址，与既有 int 搬运同构，仅 typ 记 `("list",*)`）；
  bool 元素列表 `let b=[True,False,True]`，`#1：[b[0]]`→`True`（eltyp=bool 经 OUTPUT 分派 `print_bool`）。
- 混合 `[1,True]`、嵌套 `[[1],[2]]`、`len` 作用非列表、`5[0]` → 编译期 `NativeNotSupported` 拒。
- **验收**：bool 列表索引逐字节对拍；四类非法构造全部显式拒。

### N3：列表 × 算术 × 控制流组合（真实用例）
- `#1：[l[0]+l[1]*2]`、`while i < len(l) { sum = sum + l[i]; i = i + 1 }` 遍历求和等——复用 P-a 的
  `BINOP`/`JZ`/`JNZ`/`STORE_GLOBAL`，元素 `l[i]` 落地为 int 参与运算。
- **验收**：求和/加权用例逐字节对齐 VM（含负元素、单元素表、空表边界）。

### N4：Gate 扩例 + CI 复用 + 文档门禁同步（收 P-b 期）
- 扩 `baremetal/tools/native_elf/run_native_elf.py`（见 §五）；复用既有 `native-elf-gate` ubuntu job，无需新增 job。
- 同步 `docs/ARCHITECTURE.md` `core_py_lines`（P-a 收期 32,237 → P-b 新值）；`CHANGELOG.md` 记 P-b 条目（无性能数字口径）。
- **验收**：Gate 全绿 + `test_doc_facts` 18/18 + 主线 check-lite 复跑不破（Windows 原生 exe 用例的
  高负载偶发超时须以「干净重跑 pytest 全绿」甄别，见 §七）。

---

## 四、验证方式（五层协议，与 P-a 同源，缺一不可）

| 层 | 手段 | 判定 |
|---|---|---|
| L1 结构 | `readelf -h -l <elf>`（CI/WSL）+ 模块自检 | 段表 `p_memsz>p_filesz` 覆盖堆尾；entry 落 RX 段 |
| L2 可执行 | WSL2 / qemu-x86_64 / CI ubuntu 实跑 | 正常退出、无加载失败/段错误 |
| L3 逐字节对拍 | `compile_to_elf(src)` stdout ↔ `run_checked(src, mode="vm")` | 全等记 `ok`；任一差即 FAIL |
| L4 诚实边界 | `REJECT_CASES`（嵌套/混合/字符串元素/切片/字典/`5[0]`/整表 repr 输出） | **必须**抛 `NativeNotSupported`；误接受即 FAIL |
| L5 门禁 | `dep_audit` / `test_doc_facts` / `kernel_purity` / check-lite | 全绿；`core_py_lines` 与 `repo_facts` 一致 |

执行器探测优先级与退出码约定（`0` 全绿 / `1` 失败 / `2` SKIP）沿用 P-a 的 `run_native_elf.py`（WSL 冷启动探针超时已放宽至 90s）。

---

## 五、Gate 用例增量

正例（追加，逐字节对拍）：
- `s10_build_list_len`：`let l=[10,20,30]` `#1：[len(l)]` `#1：[len([])]` → `3`,`0`。
- `s11_index_pos_neg`：`#1：[l[1]]` `#1：[l[-1]]` `#1：[l[0]]` → `20`,`30`,`10`。
- `s12_bool_list_index`：`let b=[True,False]` `#1：[b[0]]` `#1：[b[1]]` → `True`,`False`。
- `s13_while_index_sum`：`while` 遍历 `l` 求和 → 对齐 VM。

负向（追加，断言编译期 `NativeNotSupported`）：
- `r7_nested_list` `[[1,2],[3]]`；`r8_mixed_list` `[1,True]`；`r9_list_repr_output` `#1：[l]`；
  `r10_slice` `l[0:2]`；`r11_dict` `{"a":1}`；`r12_int_subscript` `5[0]`。

行为断言（非 stdout 对拍）：`b1_index_out_of_range` `l[3]` → ELF `exit_group(1)` 且 VM 侧确认 `IndexError`（口径见 Q2）。

CI：复用现有 `native-elf-gate` job（`PYTHONPATH=. python baremetal/tools/native_elf/run_native_elf.py`），
用例表扩展即随之覆盖，无需新增 workflow job。

---

## 六、开放问题（动工前需你拍板）

- **Q1 堆放置/容量**：`HEAP_OFF=0x30000`、`HEAP_SIZE=0x80000`（512KB）、bump 指针走 `r12`——是否认可？
  P-b **只 bump 不回收**（GC 属 P-c）；容量供 §五 用例远绰有余。**建议：认可，按此布局。**
- **Q2 越界索引口径**：`INDEX_GET` 越界发射 `exit_group(1)`，VM 端是抛未捕获 `IndexError`。
  Gate 里这类作为**行为断言**（校验 ELF 退出码=1 + VM 侧确为异常），不参与 stdout 逐字节对拍。**建议：采纳。**
- **Q3 列表跨函数边界**：P-b **不**把列表纳入 `CALL`/`RET` 实参与返回值（保持 P-a 标量 ABI 与 `_infer_fntyp` 纯净），
  列表仅在 `main` 及标量作用域内构造/索引/取长。**建议：延后到后续期（与字符串/引用语义一并评估）。**
- **Q4 元素类型同质性**：强制同一列表元素**全 int 或全 bool**，混合即编译期拒；bool 元素索引结果保 bool typ 供 OUTPUT。
  **建议：采纳（数值伪造或隐式 bool↔int 降级都会破坏逐字节对拍，故不接受混合）。**

---

## 七、风险点与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| `len(l)` / `BUILD_LIST` 字节码形态与勘察假设不符 | N0 发射错位、对拍恒差 | N0 **第一步即打印字节码**锁定编码；沿用 P-a「每里程碑先勘察再发射」纪律 |
| bump 堆无回收，遍历时重复 `BUILD_LIST` 累积 | 长循环用例耗尽显存 | P-b 用例均为**一次性建表**；容量 512KB 富余；GC 动态堆留 P-c 并登记扩面表 |
| 表指针与裸整数在 `.bss`/栈上同形（都是 8B） | 误把整数当指针解引用 | 编译期影子 typ 栈唯一决定用法，运行期不做判别；typ 不符即发射期拒（`5[0]`、`len(5)`） |
| memsz 未纳入堆尾 | 堆页未映射→写堆段错误 | N0 扩展 `_build_elf64` 的 `data_memsz` 取 `max(..., HEAP_OFF+HEAP_SIZE)`；L1 `readelf -l` 自检 |
| Windows 原生 exe 用例高负载偶发超时（P-a 收期已遇） | check-lite 假红 | 甄别法：**绕过 check.py 直接 `pytest` 干净重跑**，全绿即非回归；CI ubuntu 兜底 |
| `native_elf.py` 再进 `src/mbc` 改变 `core_py_lines` | `test_doc_facts` 漂移锁红 | N4 收期前同步 `ARCHITECTURE.md`；L5 复跑确认 |
| 依赖方向（dep_audit） | 反向 import 违规 | 仍只依赖 `compiler`/`opcodes`，不引 `native.py`；dep_audit 复跑 |

---

## 八、交付物清单（确认即按此产出）

- `src/mbc/native_elf.py` 扩展：`HEAP_OFF/HEAP_SIZE` 布局 + `_start` 初始化 `r12`；
  `_emit_build_list` / `_emit_index_get`；`LOAD_GLOBAL "len"` 与 `CALL` 的 builtin `len` 分派；
  影子 typ 栈与 `gtype` 纳入 `("list",eltyp)`；`_build_elf64` memsz 含堆尾；各新拒绝点守卫。
- `baremetal/tools/native_elf/run_native_elf.py`：追加 §五 正/负/行为用例（Gate 脚本，不入主线门禁）。
- CI：复用 `native-elf-gate` job（无需新增）。
- 文档同步：`docs/ARCHITECTURE.md`（`core_py_lines`）、`CHANGELOG.md`（P-b 条目，无性能数字）、
  `docs/spec/NATIVE_CROSS_PLATFORM.md` §6.3 扩面表把「列表」行转「P-b 已支持」。

## 九、提交切分（收 P-b 时的 commit 粒度）
- 每个里程碑（N0–N4）本地/CI 全绿后各自成 checkpoint，P-b 收期单 PR 内分步提交
  （N0 堆+建表+len → N1 索引 → N2 类型完整/拒 → N3 组合 → N4 Gate/CI/文档），保持可回滚。

---

*待你确认本文（尤其 §六 四个开放问题）后，再开始 N0 字节码勘察与编码。约束不变：不改任何 plan 文件、不改 `native.py` 主体、baremetal 门脚本不入门禁。*
