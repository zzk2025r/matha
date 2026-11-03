# Native ELF 跨平台 · 剩余缺口台账（GAP LEDGER）

> 本文是 [`NATIVE_CROSS_PLATFORM.md`](./NATIVE_CROSS_PLATFORM.md)（④ 立项总设计）、
> [`NATIVE_ELF_PA.md`](./NATIVE_ELF_PA.md)（P-a 整数骨架）、[`NATIVE_ELF_PB.md`](./NATIVE_ELF_PB.md)（P-b 列表+堆）、
> [`NATIVE_ELF_PC.md`](./NATIVE_ELF_PC.md)（P-c 分期路线图）的**缺口盘点接续**，
> 汇总 `src/mbc/native_elf.py`（纯 Python 位级发射 Linux x86-64 静态非 PIE ELF64，无 libc/libm，仅 `write`/`exit_group`）
> 当前**尚未覆盖的能力面**，作为后续排期的单一事实来源。
>
> **基准口径**：对拍 `exec_api.run_checked(src, mode="vm")`，每值按 CPython `str(v)` 渲染（LF 行尾）。
> **核心纪律**：所有缺口一律**编译期 `NativeNotSupported` 显式拒**或**运行期 `exit_group(1)`（rc=1、空输出）诚实拒**，
> **绝不伪通过、绝不静默印错**。放行面内逐字节 `==repr(v)`。

---

## 〇、当前能力天花板（截至本台账）

P-c2 浮点最短往返 `dtoa_shortest` 已交付至 **S3c-6c-4 收官**（提交链 `cc0c7c4 → 6cbec52 → 960ae4f`）：
轴 C 四刀（6c-1/2/3a/3b/4a/4b）+ 6a（κ>63）+ 6b（表跨）+ 6c-4（band_neg 大整数长除族）全部落地。

**放行面（逐字节 `==repr`）**：`sig≤17` 且 `|u|≤38`、`E≤64` 位、整数支 `A≤2^128 ∧ |s|≤19`、`D≤128`/`EB≤192`（u<0 三字）
——即**现实量级浮点（`|v| ∈ [~1e-38, 1e38]`、≤17 位有效、整数 ≤2^128）已全覆盖**。
门禁实况：oracle（`.trae/pc_dso_oracle.py` 全域 WSL）**OK=915 / 如实拒=114 / 失败 0**；Gate（`run_native_elf.py`）**43 正 / 15 拒 / 5 越界 / 2 档空洞，失败 0**。

以下按五个维度盘点**剩余缺口**（均为「已登记 + 当前诚实拒/静态拒」，非缺陷）。

---

## 一、P-c2 浮点输出（dtoa_shortest）越子集 — 运行期诚实拒

数据源：`.trae/pc_s3c5d1d_gates.py::pipeline(v, crit_strict)`。
两口径：① **全随机 8 万 double**（均匀采样 64 位位模式，含极端指数）；② `build_subset` 4.3 万（既有 6c 语料，偏现实量级）。

| 拒因 | 含义 | 全随机占比 | 性质 / 决策 |
|---|---|---|---|
| **`pow10_out`** | `10^|u|` 越双字表（`|u|>38`，即 `|v|>1e38` 大数 或 `<1e-38` 深小数，`repr` 走科学计数 `1e+100` 类） | **65.6%** | 随机指数均匀故占比虚高，**现实量级几乎不触发**。要扩须**真任意精度 10^u 表 / 多字长除**——最大结构性面，高风险 |
| **`D_gt128`** | `u<0` 三字差值 `|P−Q|>128` 位（`κ` 大且深表跨，超三字地基） | 1.8% | 需四字以上地基，中-高 |
| `int16_band_neg`（`|s|≥20`） | 6c-4c 真 128/128 长除（仅 ~31 例） | 0.4% | ✅ **已决定长期如实拒、不做**（见 `NATIVE_ELF_PC.md` 6c-4 收官） |
| `shl_gt128` / `prod_gt128` / `thr_gt128` | 阈值 / 乘积超 128/192 位 | ~0.17% | 深极端值，高 |
| `decpt_notable` | 定档不可表（近特殊值边界） | 0.03% | 极少 |
| `int17_band_big`（`s>38`）/ `int16_kap128`（`κ≥128`） | 整数支 `s` 越 38 / `κ≥128` | ~0.04% | 真大数，高 |
| **次正规**（`e=0`）/ `inf` / `nan` | 次正规 Phase A 位域入口拒；`inf`/`nan` 走静态串直出 | 极 | 设计内 |

**小结**：现实量级浮点已收官；剩余几乎全是**极端指数科学计数值**。若追求全-double 覆盖，唯一大头是 `pow10_out` 的任意精度 10 幂地基（实用价值低，建议长期诚实拒）。

---

## 二、浮点算术越界 — 编译期静态拒

| 缺口 | Gate 拒例 | 归属 / 决策 |
|---|---|---|
| 越域 float `//`（floordiv） | `r17_float_floordiv` | 需 CPython 精确有理商语义，**归 S4c+** |
| 越域 float `%`（mod） | `r18_float_mod` | 同上，**归 S4c+** |
| `/` 真除越域产 `±inf` vs VM `ZeroDivisionError`（÷0） | —（`native_elf.py` L82 登记） | **行为分歧未对齐**：机器出 `inf`/exit、VM 抛异常 |

---

## 三、P-c1 字符串后续 — 编译期静态拒

| 缺口 | Gate 拒例 | 依赖 |
|---|---|---|
| `str × 数值` 连接 / `str + int` 混合 | `r13_str_mul` / `r14_str_plus_int` | **需 itoa**（整数→串） |
| 非 ASCII / UTF-8 串 | `r1_non_ascii` | Q2 拍板 ASCII 优先，多字节歧义未做 |
| 运行期（非字面量）计算的 str / 异构 · 嵌套列表 repr | `r7_nested_list` / `r8_mixed_list` / `r9_str_list_runtime` | 需运行期类型标签 |
| 字符串 `*` 重复、`in` 子串/成员、切片 `s[a:b]` | — | 归 P-c1 后续 |

> 注：字面量 str、同构列表、字面量折叠的异构列表 repr **已支持**；上表仅「运行期动态」部分未覆盖。

---

## 四、P-c3 / P-c4 — 未动工（最大结构性缺口）

| 域 | 缺口（Gate 拒例） | 归属 |
|---|---|---|
| **GC / 动态堆** | 现仅 bump 堆（`HEAP_OFF=0x30000`/`HEAP_SIZE=0x80000`），**无回收、无 mmap 增长** → 长程/无界分配 | **P-c3**（独立立项，Q3 若延后仅登记） |
| **字典** | `BUILD_DICT`(0x51)/`GET_ATTR`(0x54)（`r11_dict`） | **P-c4** |
| **闭包** | `MAKE_CLOSURE`(0x20)/`LOAD_OUTER`/`BOX`（`r2_closure`） | **P-c4** |
| **异常** | `RAISE`(0x61)（VM `MathaRuntimeError`） | **P-c4** |
| **控制流** | `for x in list`（`r3_for_list`，仅支持 while） | 待定 |
| 其它 | `int` 下标 `5[0]`（`r12_int_subscript`）、列表切片（`r10_slice`）、实参数量不符（`r5_arity_mismatch`）、未定义全局（`r4_undefined_global`） | 各自后续 |

---

## 五、已知运行期如实失败面（**非缺陷，设计内**）

| 面 | Gate 用例 | 行为 |
|---|---|---|
| 越界索引 `l[3]/l[-4]/[][0]/s[5]/s[-4]` | `b1–b5` | `exit_group(1)` 镜像 VM 未捕获 `IndexError` |
| floatq 双档空洞（`d∈7..10` 且 `|v|≥深档阈`） | `h1/h2` | 整数性回检转 `exit1`，不静默印错（双档并存必然代价） |

---

## 六、排期建议（按风险/收益）

1. **低优先·建议长期诚实拒**：`pow10_out`（极端指数，实用价值低）、6c-4c（已决定不做）、`D_gt128`/三字以上地基。
2. **中优先·语义对齐**：`/` ÷0 行为分歧（`inf` vs `ZeroDivisionError`）先定性口径。
3. **能力大头·需独立立项**：P-c3 GC/动态堆、P-c4 字典/闭包/异常、`for` 控制流、itoa（`str×数值`/`str+int`）——
   各按 `NATIVE_ELF_PC.md` §「独立立项 + 里程碑自底向上 + Gate 逐字节对拍 + 开放问题拍板」范式推进，高风险切片需单独授权。

---

## 维护说明

- 拒因分布**复现**：`python .trae/pc_s3c5d1d_gates.py`（打印 `build_subset` 严门拒因）；全随机口径见本文 §一 数据源函数。
- 缺口用例权威登记：`baremetal/tools/native_elf/run_native_elf.py` 的 `REJECT_CASES` / `OOB_CASES` / `HOLE_CASES`。
- `.trae/` 已 gitignore（探针/模型脚本不入库）；本文档与 `run_native_elf.py`、`docs/spec/*.md` 为受控入库工件。
- 每完成一刀解禁，应在本文对应行标注「已交付 + commit」并从缺口表移入 §〇 天花板，保持台账与门禁实况同步。
