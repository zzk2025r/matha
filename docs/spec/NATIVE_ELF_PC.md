# Native ELF 后端 · P-c 阶段落地设计与分期路线图

> 本文是 [`NATIVE_CROSS_PLATFORM.md`](./NATIVE_CROSS_PLATFORM.md)（④ 立项总设计）、
> [`NATIVE_ELF_PA.md`](./NATIVE_ELF_PA.md)（P-a 整数骨架）与 [`NATIVE_ELF_PB.md`](./NATIVE_ELF_PB.md)（P-b 列表+堆）的接续，
> 聚焦 **P-c 阶段**：在 P-b 之上引入 **字符串 → 浮点 → 字典/闭包/异常/GC** 的动态值域。
> 本轮只产出文档（路线图），**不写实现代码**；§六 六个开放问题已拍板（见该节），经确认后可按 §三 N0 动工 P-c1 字符串。
> 目标平台不变：**Linux x86-64 / ELF64**，与 `native.py`（Windows PE）平行独立，不 import 之。
> 对拍基准仍是 `exec_api.run_checked(src, mode="vm")`（LF 行尾，每值按 Python `str(v)` 渲染）。

---

## 〇、P-c 的核心纪律：分型 + 分期立项

P-a（整数标量）与 P-b（列表）各自是**单一最小垂直切片**。P-c 名义上横跨**六个能力域**
（字符串 / 浮点 / 字典 / 闭包 / 异常 / GC 动态堆），体量远超任何单一切片——若把它们塞进一个
巨型 PR，将直接违反「杜绝全写完才第一次能跑」的铁律。

因此本路线图的**首要结论**是：把 P-c 拆成一条**串行子切片链**，每个子切片都是可独立验证、独立提交的
最小闭环，沿用 P-a/P-b 已验证的「**里程碑自底向上 + Gate 逐字节对拍 + 开放问题拍板**」范式：

| 子切片 | 能力域 | 立项形态 | 本详设覆盖度 |
|---|---|---|---|
| **P-c1** | 字符串（表示/输出/连接/比较/repr/len/索引） | **本轮即动工** | §三 N0/N1 **细化到位** |
| **P-c2** | 浮点（SSE2 算术 + 手写 `_dtoa` 最短往返） | 本轮骨架，拍板后可升独立 `NATIVE_ELF_PC2.md` | §三 N2 **给骨架与风险** |
| **P-c3** | GC / 动态堆（回收或多 mmap 增长） | **独立立项**（Q3 若延后则仅登记扩面表） | §二/§三 N3 **给策略选型** |
| **P-c4** | 字典 / 闭包 / 异常（`BUILD_DICT`/`MAKE_CLOSURE`/`RAISE`） | **各自独立立项**（`PC4` 或更细分文档） | §三 N4 **仅界边界** |

**本详设的可执行入口 = P-c1 字符串（N0/N1）**；N2-N4 确立边界与验收口径，但**不在本轮一次做完**，
每个待各自开放问题拍板后按其内部里程碑独立推进（对齐总设计 §9「P-c 各自独立立项」）。

---

## 一、P-c1 范围（做什么 / 不做什么）

总设计 §6.3 把「字符串」列为 P-c 首块：`输出路径扩展 + 堆字节串`。本细化锁定 **P-c1** 边界。

### 1.1 做（P-c1 字符串垂直切片）

| opcode / 构造 | P-c1 覆盖语义 | VM 真值锚点（`src/mbc/vm.py`）|
|---|---|---|
| `PUSH_CONST`（str 常量） | 常量池字符串 → 堆上建串对象，压串指针；**当前发射器 L467 拒绝非 int，本切片解禁** | 常量直取；OUTPUT 文本 = `str(v)` |
| `OUTPUT`（typ=`"str"`） | 弹串指针 → `write_span` 堆字节；**裸字符串无引号**（`f"{v}\n"` = `str(v)`） | L935-937 `_norm_output`：仅函数值特判，其余原样 |
| `BINOP "+"`（str 域） | `str+str` 连接；`str + 数值` / `数值 + str` **自动 `str(b)` 再连接**（非数值伪造） | `_op_add` L114-128：`isinstance(a,str) and isinstance(b,(int,float)) → b=str(b)` |
| `BINOP "=="`/`"!="`（str 域） | 逐字节比较返回 bool | 复用 `_CMP`，但需字节比较而非整数比较 |
| 内建 `len(s)` | 串长度；**首期限 ASCII：len = 字节数 = 码点数**（多字节见 Q2） | `b["len"]=len`，`len("hi")=2` |
| `INDEX_GET`（str × int） | `s[i]` → 长度 1 子串（堆上复制 1 字节）；**Python 同口径负索引**，越界 `exit_group(1)` | L874-884 `c[idx]` 语义（str 切片同 int 索引） |
| 整表 / 串列表 **repr 输出** | `#1：[l]`、`#1：[s]`（l/s 为含 str 的列表）→ Python list `repr`：**单引号包裹元素、逗号+空格分隔、转义** | `f"{v}\n"` = `str(list)` = Python list repr（与 `native.py` 既有「列表内字符串加引号」契约同源，见 Q2） |

### 1.2 不做（一律 `NativeNotSupported` 显式拒绝，不臆造 / 不数值伪造）

- **多字节 / 非 ASCII 字符串**（UTF-8 码点 vs 字节歧义）→ **首期拒**（Q2 拍板；ASCII 优先证明语义）。
- **字符串作 `*` 重复**（`"ab"*3`）、**`in` 子串/成员**、**切片 `s[a:b]`** → 拒（`BUILD_SLICE` 越界，归后续；`_op_mul` L138-155 支持但不入首刀）。
- **字典** `BUILD_DICT`(0x51) / `GET_ATTR`(0x54) → **P-c4**，本轮拒。
- **闭包** `MAKE_CLOSURE`(0x20) / `LOAD_OUTER`(0x15) / `LOAD_BOX`(0x11) / `MAKE_BOX`(0x13) → **P-c4**，本轮拒。
- **异常** `RAISE`(0x61) → **P-c4**，本轮拒（VM L940-941 抛 `MathaRuntimeError`）。
- **浮点**（`PUSH_CONST` float / SSE 算术 / `_dtoa`）→ **P-c2**（N2 骨架，非 P-c1）。
- **字符串跨 `CALL`/`RET` 边界**（作实参/返回值）→ 延后（沿用 P-b Q3 标量 ABI 纯净原则，串仅在 main/标量域构造）。

---

## 二、内存布局与堆回收 / GC 策略

沿用 P-a/P-b 固定布局（基址 `0x400000`，`DATA_VADDR=0x410000`，两 `PT_LOAD`；操作数栈 `rbx@VSP_OFF=0x100`、
全局槽 `GVARS_OFF=0x20000`、bump 堆 `HEAP_OFF=0x30000` / `HEAP_SIZE=0x80000`、bump 指针 `r12`）。P-c **不新增段**，只在同一堆上扩展对象布局。

### 2.1 串对象表示（P-c1）

```
串指针 sptr → [ len : 8B ][ b0 ][ b1 ] ... [ b_{len-1} ][ 对齐填充 → 8B 边界 ]
```
- `len` 为**字节长度**（ASCII 期 = 码点数）；字节紧随；块总大小 `align8(8 + len)`，`r12 += 之`（bump）。
- 与列表对象 `[len:8B][e0:8B]...` 同构（表头 8B 长度 + 载荷），差异仅在载荷是**字节**而非 8B 槽。
- **无运行期类型标签**——延续 P-b 静态域原则：`"str"` vs `("list",...)` 由编译期影子 typ 栈唯一决定；
  `OUTPUT` 只会收到已定型的 `str`/`int`/`bool`（P-c2 再 +`float`），运行期不做指针/整数多态判别。

### 2.2 浮点表示（P-c2，仅定边界）

- IEEE-754 double 原样 8B 存于操作数栈槽 / 全局/局部槽（与 int 搬运同构，仅 typ 记 `"float"`）；
  **不做运行期装箱**（静态值域）。算术走 **SSE2 标量**（`movsd/addsd/subsd/mulsd/divsd/ucomisd/cvtsi2sd/cvttsd2si`）——
  x86-64 基线保证 SSE2 存在。唯一硬骨头是**输出**（`_dtoa` 最短往返，见 N2 / Q1 / Q5）。

### 2.3 GC / 堆回收策略（三选一，Q3 拍板）

| 方案 | 做法 | 代价 | 适用 |
|---|---|---|---|
| **(a) 只 bump 不回收** | 与 P-b 完全一致；`r12` 只增 | 串连接循环 / 浮点装箱累积 → 512KB 可耗尽 | **P-c1/P-c2 首选**（用例一次性建串，规模远小于堆） |
| **(b) mark-sweep** | 根集 = 操作数栈在用区间 `[VSP_ADDR, rbx)` + 全局槽 `[GVARS_ADDR, +8·|gmap|)` + 活动帧局部槽；从根扫串/列表指针标记，再线性回收未标块 | 需对象头含类型/大小、指针与裸 int 同形难辨（P-b 已回避运行期判别） | P-c3 独立立项（连接/字典扩容产生真实垃圾时才需要） |
| **(c) mmap 增长** | `brk`/`mmap` 动态扩堆，仍不回收 | 引入 `mmap`(rax=9) syscall 与堆指针可移动性 | 备选（若某用例超固定堆但仍不需 GC） |

**推荐**：P-c1/P-c2 采 **(a) 只 bump**（对齐 P-b 先例，先证语义正确）；GC 升 **P-c3 独立立项**（Q3）。
容量风险与缓解见 §七。堆尾 `p_memsz` 已含 `HEAP_OFF+HEAP_SIZE`；若拍板扩容（如 512KB→2MB）仅改 `HEAP_SIZE` 常量。

### 2.4 影子 typ 栈扩展

P-a/b typ 域：`int | bool | null | ("fn",name) | ("list",eltyp) | ("builtin","len")`。
P-c 新增：`"str"`（堆串指针）、`"float"`（IEEE-754 值，P-c2）；`("builtin", ...)` 预留其余内建（本轮仍只 `len`）。
`OUTPUT` 分派：`"str"`→`print_str`（新增，write_span 堆字节）、`"float"`→`print_float`/`_dtoa`（P-c2）；
`INDEX_GET`：容器 typ 为 `"str"` → 返回**长度 1 子串**（typ `"str"`）；为 `("list",et)` → `et`（P-b 既有）。

---

## 三、P-c 里程碑拆分（自底向上，每个都是可独立验证的最小闭环）

> 纪律同 P-a/P-b：每里程碑末尾在 WSL/CI 实跑并逐字节对拍后方可提交。**N0/N1 = P-c1（即动工）；
> N2-N4 是边界确立，待各自开放问题拍板后按内部里程碑独立立项推进。**

### N0：字符串垂直切片最小闭环（P-c1 · 先勘察字节码）
- **先做字节码勘察**：`compile_source` 打印 `#1：["hi"]` 与 `let s="hi"\n#1：[s]`、`#1：[len("hi")]` 的真实指令流，
  锁定 ① str 常量在 `C[]` 的编码（Python `str` 对象，`PUSH_CONST idx`）、② `len("s")` 是否复用 `LOAD_GLOBAL len; CALL 1` 形态、
  ③ 串在列表内 `["a","b"]` 的 BUILD_LIST 交互（P-b 现拒字符串元素 → N0 解禁 typ `"str"` 作元素）。
- 落地：`_emit_push_const` 支持 `str` → 分配 `align8(8+len)`、写长度字、搬字节、压指针并注 typ `"str"`；
  `OUTPUT` 加 `"str"` 分支 → 新运行时子程序 `print_str`（取 `[sptr]` 长度、`[sptr+8]` 起 `write_span`，**无引号**）；
  `CALL` 的 builtin `len` 分派扩展到 `"str"` 容器（取串长度字压 int）；`STORE_GLOBAL` 承载串指针（8B，同表指针）。
- **验收**：`#1：["hi"]`→`hi`；`let s="hi"\n#1：[len(s)]`→`2`；串进全局槽往返；逐字节对齐 VM。

### N1：字符串组合 + repr 契约（P-c1 · 收期）
- `BINOP "+"` 在 `"str"` 域：弹 b、弹 a，任一为 str → 走**连接**（含 `str+数值` 自动 `str(数值)`，与 `_op_add` 一致）：
  新运行时 `str_concat`（分配 `align8(8+lenA+lenB)`、两次 `rep movsb`/字节循环搬入）；`"=="`/`"!="` → 新运行时 `str_eq`
  （长度等且逐字节等，产 bool）。`INDEX_GET` str×int（负索引归一、越界 `exit_group(1)`、返回 1 字节子串）。
- **整表 / 串列表 repr 输出**（`#1：[[1,"a"]]`、`#1：[s]`）：运行时 `repr_*` 递归构建——**口径见 Q2**（单引号包裹 str 元素、
  逗号+空格分隔、list repr；`native.py` 既有契约不得为对拍而去引号）。
- 混合类型列表 `[1, "a"]`：**借 P-c1 之力在 N1 同期解禁异构列表**（Q4 已采纳）——放弃 P-b 的元素同质约束，
  元素 typ 存 `("list", None)`，整表输出走运行期 repr（按元素实际类型渲染），不再依赖静态同质分派。
- **验收**：连接/比较/索引/repr 逐字节对拍；Gate 追加 P-c1 正/负例（§五）。

> **P-c1 内部子切片实况**（以下 N 为 **P-c1 内部编号**，与本节 §三按 P-c 阶段编号的 N2=浮点/N3=GC/N4=字典互不相干）：
> - **N0**（commit `95b04a9`）：串表示 + `print_str` 裸串输出 + `len(str)`。
> - **N1**（commit `b88108e`）：str+str 连接（`str_concat`/双段 `rep movsb`）、str `==`/`!=`（`str_eq`/长度短路 + `repe cmpsb` 取 ZF）、`s[i]` 取子串（正/负/越界 exit1）。
> - **N2**（本次）：**同质 int/bool 列表整表 repr 输出**（`plr_int`/`plr_bool` 运行期循环 `[e0, e1, …]`，字面量 `[`/`]`/`, ` 入 .data 空洞）。
>
> **如实收缩至 P-c1 后续**：`str×数值` 连接（需运行期 itoa）、**str 列表 repr**（需 Python 精确引号选择 + 字节分类转义，
> 如 `["it's"]`→`["it's"]`）、**异构列表解禁**（Q4）——前两者各为独立子切片（需新的运行时机器），异构列表需逐元素
> 运行期类型标签、与当前「无运行期标签、纯影子 typ」模型分歧（Q4 原假设在此不可行），归 P-c3/tagging。

### N2：浮点垂直切片（P-c2 · 骨架，建议独立立项）
- `PUSH_CONST` float → IEEE-754 8B；`BINOP + - * /` 在 `"float"` 域走 **SSE2 标量**；`int/float` 混型（`/` 真除产 float，
  对齐 `_op_div`）；比较走 `ucomisd`+setcc；`OUTPUT` typ `"float"` → **手写 `_dtoa`**。
- **`_dtoa` = 全期最大不确定项**：须与 Python 3 `repr(float)`（最短往返，Ryū/Grisu-JST 语义）逐字节对齐，
  含 `0.1+0.2 → 0.30000000000000004`、`1e16 → 1e+16` 科学计数切换、`inf/nan`。口径见 **Q1**，路线见 **Q5**。
- **验收**：浮点输出逐字节对齐 `str(float)`；若 `_dtoa` 未就绪，Gate 浮点例可**如实 SKIP**（登记独立立项），
  但**绝不允许数值近似伪通过**（与 P-a int64 溢出「干净失败」纪律一致）。

### N3：GC / 动态堆（P-c3 · 独立立项，Q3 拍板）
- 仅当连接循环 / 字典扩容产生真实堆耗尽需求时启动。选型见 §2.3(b)/(c)。
- 需要**对象头统一**（类型标签 + 块大小）以支持 mark-sweep 的标记/清扫——这与 P-b/P-c1「无运行期类型标签」是**架构分歧点**，
  须专门设计指针 tagging（保守标记 vs precise 根表）。本轮不实现，登记总设计 §6.3 扩面表。

### N4：字典 / 闭包 / 异常（P-c4 · 各自独立立项）+ 各子切片 Gate/CI/文档收口
- `BUILD_DICT`/`GET_ATTR`（堆哈希对象）、`MAKE_CLOSURE`/`LOAD_OUTER`/`BOX`（环境对象 + 捕获布局）、
  `RAISE`（处理器栈 + 长跳转）——每项需对应子设计，**各自成文**（本轮仅确立拒绝边界与登记扩面表）。
- **收口动作（每个子切片 N 各自执行，非一次）**：扩 `run_native_elf.py` Gate 用例；复用既有 `native-elf-gate` ubuntu job；
  同步 `docs/ARCHITECTURE.md` `core_py_lines` 与 `CHANGELOG.md`（无性能数字口径）；把总设计 §6.3 对应行转「已交付」。

---

## 四、验证方式（五层协议，与 P-a/P-b 同源，缺一不可）

| 层 | 手段 | 判定 |
|---|---|---|
| L1 结构 | `readelf -h -l <elf>`（CI/WSL）+ 模块自检 | 段表 `p_memsz>p_filesz` 覆盖堆尾；entry 落 RX 段 |
| L2 可执行 | WSL2 / qemu-x86_64 / CI ubuntu 实跑 | 正常退出、无加载失败/段错误 |
| L3 逐字节对拍 | `compile_to_elf(src)` stdout ↔ `run_checked(src, mode="vm")` | 全等记 `ok`；任一差即 FAIL（浮点/多字节未就绪则如实 SKIP，不伪通过） |
| L4 诚实边界 | `REJECT_CASES`（多字节/字典/闭包/异常/`s*3`/切片/浮点[未解禁期]） | **必须**抛 `NativeNotSupported`；误接受即 FAIL |
| L5 门禁 | `dep_audit` / `test_doc_facts` / `kernel_purity` / check-lite | 全绿；`core_py_lines` 与 `repo_facts` 一致 |

执行器探测优先级与退出码约定（`0` 全绿 / `1` 失败 / `2` SKIP）沿用 `run_native_elf.py`（WSL 冷启动探针超时 90s）。

---

## 五、Gate 用例增量（P-c1 起步；P-c2+ 拍板后追加）

正例（追加，逐字节对拍）：
- `c1_str_output`：`#1：["hi"]` `let s="Hello, Matha" #1：[s]` → 裸串无引号。
- `c2_str_len`：`#1：[len("hi")]` `#1：[len("")]` → `2`、`0`。
- `c3_str_concat`：`let a="foo" let b="bar" #1：[a + b]`、`#1：["n=" + 42]`（str+数值自动转）。
- `c4_str_compare`：`#1：["a" == "a"]` `#1：["a" != "b"]` → `True`、`True`。
- `c5_str_index`：`let s="abcdef" #1：[s[0]]` `#1：[s[-1]]` → `a`、`f`。
- `c6_list_repr`：`let l=[1, 2]` `#1：[l]`（P-b 曾拒整表输出）→ `[1, 2]`；含 str 元素 `[1, "a"]` → `[1, 'a']`（口径见 Q2/Q4）。
- （P-c2）`c7_float_basic`：`#1：[1.5]` `#1：[2.0 + 1]`；`c8_float_repr_edge`：`#1：[0.1 + 0.2]` → `0.30000000000000004`（依赖 `_dtoa`）。

负向（追加，断言编译期 `NativeNotSupported`）：
- `cr1_non_ascii`：`#1：["你好"]`（首期多字节拒·Q2）；`cr2_str_mul`：`#1：["a" * 3]`；`cr3_slice`：`#1：["abc"[0:2]]`；
- `cr4_dict`：`#1：[{"k": 1}]`（P-c4）；`cr5_closure`：`f = (x) => x`（已在册）；`cr6_raise`：`？ RAISE`（P-c4）；
- `cr7_str_cross_fn`（P-c1 期串不作函数实参/返回）：`func f(s: Str) -> Str = ...`（若方言有 Str 类型，本轮拒；见 Q4 语言面确认）。

行为断言（非 stdout 对拍）：
- `cb1_str_index_oob`：`"abc"[3]` → ELF `exit_group(1)` 且 VM 侧 `IndexError`（口径同 P-b Q2）。
- （P-c2）`cb2_float_special`：`1/0.0` 之类产 `inf` 的输出口径（若 `_dtoa` 覆盖）。

CI：复用现有 `native-elf-gate` job，用例表扩展即随之覆盖，无需新增 workflow job。

---

## 六、开放问题（已于 2026-11-01 拍板，全部采纳推荐口径）

> **拍板结论**：Q1 严格最短往返 + P-c2 独立立项 + 未就绪期 SKIP；Q2 ASCII 先行 + repr 遵 Python 语义；
> Q3 GC 延后（P-c1/P-c2 只 bump）；Q4 本轮只做 P-c1 字符串且 **N1 同期解禁异构列表**；Q5 浮点算术走**硬件 SSE2**。
> 下方各条保留原权衡记录，✅ 标记为已采纳口径。

- **Q1 浮点输出精度口径** ✅：`_dtoa` **必须严格匹配 Python 3 `repr(float)`（最短往返）**——这是逐字节对拍的硬前提
  （`0.1+0.2 → 0.30000000000000004`、`1e16 → 1e+16`、`inf/nan`）。
  **已采纳：严格最短往返口径；因实现难，把浮点整体划为 P-c2 独立立项，未就绪期 Gate 浮点例如实 SKIP（绝不数值近似伪通过）。**
- **Q2 字符串编码与 repr** ✅：① 首期限 **ASCII**（len=字节=码点，`s[i]` 取字节子串）——多字节 UTF-8 延后；
  ② 裸串 `OUTPUT` = **无引号**（对齐 `str(v)`）；③ **整表/串列表 repr** = Python `list`/`str` repr（元素单引号、逗号+空格、转义），
  且遵循 `native.py` 既有「列表内字符串加引号是既有契约，不可为对拍而去引号」的教训。
  **已采纳：ASCII 先行 + repr 遵 Python 语义；多字节另立子题。**
- **Q3 GC 是否延后** ✅：P-c1/P-c2 采 **§2.3(a) 只 bump 不回收**（对齐 P-b），GC 升 **P-c3 独立立项**，
  仅当连接/字典扩容产生真实堆耗尽需求时启动（届时须解决指针 tagging 与「无运行期类型标签」的架构分歧）。
  **已采纳：延后（先证语义正确，再谈回收）。**
- **Q4 P-c 分期与列表异质解禁** ✅：确认「**本轮只做 P-c1 字符串（N0/N1）即最小垂直切片；浮点/GC/字典/闭包/异常各后续独立立项**」；
  并决定：借字符串之力**同期在 N1 解禁异构列表**（`[1, "a"]`，放弃 P-b 的元素同质约束、元素 typ 存 `("list", None)`、OUTPUT 走 repr 而非静态分派）。
  **已采纳：整表输出走 repr（Q2）已在 N1 落地，运行期按元素实际类型渲染，同质约束反成多余——N1 一并解禁异构列表。**
- **Q5 浮点算术实现路线** ✅：**硬件 SSE2 标量**（`addsd/subsd/mulsd/divsd/ucomisd/cvtsi2sd`）vs **软浮点**（纯整数模拟 IEEE-754）。
  **已采纳：硬件 SSE2（x86-64 基线必带，算术简单可靠）；全期难点集中在 `_dtoa` 输出，而非算术本身。软浮点仅在需向非 SSE 目标（如未来 RV）移植时再评估。**

---

## 七、风险点与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| `_dtoa` 最短往返对齐 Python `repr` 极难 | 浮点例对拍恒差 | 划入 P-c2 独立立项；未就绪期 Gate **如实 SKIP**，不伪通过；参考已验证的 CPython `float_repr` 语义逐位实现 |
| 串/整表 repr 的引号/转义/分隔与 VM `str(v)` 口径不符 | N1 repr 输出对拍差 | N1 第一步即**旁录 VM `str([...])` 精确行为**（含空表、嵌套、转义、单引号）；遵 `native.py` 既有契约教训 |
| 只 bump 不回收，连接/装箱循环耗尽 512KB | 长用例 OOM/写越堆 | P-c1/P-c2 用例一次性建串；必要时经 Q3 扩 `HEAP_SIZE`；GC 归 P-c3 |
| 串指针 / 表指针 / 裸 int / float 在栈与 `.bss` 上**同形（皆 8B）** | 误把整数当指针解引用 | 编译期影子 typ 栈唯一决定用法，运行期不做判别；typ 不符即发射期拒（`5[0]`、`len(5)`、`"a" // 2`） |
| 多字节 UTF-8 下 len（码点）≠ 字节数、`s[i]` 取字节非字符 | 非 ASCII 用例静默产错 | 首期**拒非 ASCII**（Q2），Gate 断言 `cr1_non_ascii`；多字节另立子题 |
| P-c 六域一次做完 → 巨型 PR、无法逐里程碑验证 | 违反最小垂直切片纪律 | §〇 强制分期：本轮 N0/N1 落地，N2-N4 各独立立项 |
| `native_elf.py` 再进 `src/mbc` 改变 `core_py_lines` | `test_doc_facts` 漂移锁红 | **每子切片收口**前同步 `ARCHITECTURE.md`；L5 复跑确认 |
| Windows 原生 exe 用例高负载偶发超时（P-a 收期已遇） | check-lite 假红 | 甄别法：绕过 check.py 直接 `pytest` 干净重跑，全绿即非回归；CI ubuntu 兜底 |
| 依赖方向（dep_audit） | 反向 import 违规 | 仍只依赖 `compiler`/`opcodes`，不引 `native.py`；dep_audit 复跑 |

---

## 八、交付物清单

**本轮（P-c1 字符串，N0/N1）**：
- `src/mbc/native_elf.py` 扩展：`PUSH_CONST` str 分支 + 堆串对象；`OUTPUT` typ `"str"` 分支 + 运行时 `print_str`；
  `str_concat` / `str_eq` / `INDEX_GET`(str) / `len(str)`；影子 typ 栈纳入 `"str"`；repr 输出（若 N1 采纳 Q2/Q4）；各新拒绝点守卫。
- `baremetal/tools/native_elf/run_native_elf.py`：追加 §五 P-c1 正/负/行为用例（Gate 脚本，不入主线门禁）。
- CI：复用 `native-elf-gate` job（无需新增）。
- 文档同步：`docs/ARCHITECTURE.md`（`core_py_lines`）、`CHANGELOG.md`（P-c1 条目，无性能数字）、
  `docs/spec/NATIVE_CROSS_PLATFORM.md` §6.3 把「字符串」行转「P-c1 已交付」。

**后续（P-c2 浮点 / P-c3 GC / P-c4 字典·闭包·异常）**：各自独立立项文档（`NATIVE_ELF_PC2.md` 等）+ 独立里程碑与提交；本轮不产出其实现代码。

## 九、提交切分（收每个子切片时的 commit 粒度）
- **P-c1**：N0（串表示+输出+len）→ N1（连接/比较/索引/repr）→ 收口（Gate/CI/文档），各自全绿后独立 checkpoint。
- **P-c2/P-c3/P-c4**：拍板后各按内部里程碑分步独立提交（每步独立门禁），保持可回滚。

---

*本文 §六 六个开放问题已于 2026-11-01 拍板（均采推荐口径），本文已为决策完备的落地依据。下一步：按 §三 N0 启动 **P-c1 字符串**字节码勘察与编码（N1 同期解禁异构列表）；P-c2/P-c3/P-c4 待各自子文档另立。约束不变：不改任何 plan 文件、不改 `native.py` 主体、baremetal 门脚本不入门禁。*
