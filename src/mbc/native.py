# -*- coding: utf-8 -*-
"""M3V 字节码 → x86-64 原生机器码（Windows PE64 可执行文件）。

不经过 C 中转：Matha 源码 → AST → M3V 字节码（src.mbc.compiler）
→ 本模块直接发射 x86-64 机器码 → 手写 PE64 链接为 .exe。

运行时模型（Win64 Microsoft ABI）：
  - R12 为操作数栈指针（栈体在数据段，向上增长；push: [r12]=v; add r12,8）
  - 局部变量在原生 RBP 帧上：local i ↔ [rbp - 8*(nlocals-i)]
  - 函数参数经操作数栈传递，callee 序言搬入局部槽
  - call 前 RSP 16 字节对齐，callee 至少保留 32 字节影子空间

运行时对象模型：
  - 堆为静态数据段中的 8MB 分配区（保守式非移动 mark-sweep GC，见砖块 18），
    对象头 = [type][len][payload]。
  - 类型标签：NEG_INF 0=NULL 1=BOOL 2=INT 3=STR 4=LIST 5=DICT 6=ENV 7=CLOSURE
    8=BOX 9=PARTIAL。指针是否落在 [heap_base, heap_free) 区间用于区分
    「堆对象」与「函数地址」。

已支持（按砖块推进，每块均有 tests/test_native*.py 覆盖）：
  砖块 0 基线：int/bool 常量、PUSH_TRUE/FALSE/NULL、LOAD/STORE_LOCAL、
    LOAD/STORE_GLOBAL（含全局函数地址）、CALL/RET（单参函数/递归）、
    JMP/JZ/JNZ、DUP、POP、OUTPUT（十进制整数+换行）、HALT。
  砖块 1 多参数：序言按 arity 搬移 N 个入参，CALL 栈帧平衡，上限
    MAX_NATIVE_ARITY=8。
  砖块 2 偏应用/柯里化：apply_rt 运行时按 TYPE_PARTIAL 记录累积实参。
  砖块 3 堆与字符串：bump alloc、str_concat/str_eq/print_repr、静态串对象。
  砖块 4 列表：BUILD_LIST、INDEX_GET、print_list、len。
  砖块 5 字典：BUILD_DICT、dict_get、GET_ATTR、print_dict。
  砖块 6 整数幂 '**'（负指数返回 0，避免死循环）。
  砖块 7 闭包/盒/外域：MAKE_CLOSURE、LOAD_OUTER(_BOX)、MAKE/STORE/LOAD_BOX。
  砖块 8 切片 BUILD_SLICE：y[1:3] / y[2:] / y[:2]，语义对齐 vm.py 的
    宿主 Python 切片（负下标相对 len 归一化后钳到 [0, len]；列表浅拷贝、
    字符串按字节切；非序列容器返回 null_obj，VM 侧抛异常属既有偏差）。
  砖块 9 解构 UNPACK_SEQ：let (a, b) = … 与 for (i, j) in …。
  砖块 10 异常：raise / 错误(msg) / try-catch-finally。raise 经 raise_rt 查
     处理器链（.data 的 hstack）恢复 rsp/rbp/r12/r13 后长跳转回 调用捕获:land；
     无处理器时把 str(值) 写 stderr 并以退出码 1 结束。调用捕获 以柯里化内建
     暴露（arity 2），返回 ["__正常__", 值] / ["__异常__", 消息]。
  砖块 11 浮点：真除 '/' 恒返回 float，浮点 + - * / // % **、比较、一元
     neg。装箱 24 字节 [TYPE_FLOAT][8][double@+16]；打印与 CPython repr 逐位
     一致（CRT _ecvt + 最短往返）。
  砖块 12 成员判断 'in' / ∈：seq_contains 运行时按对象类型分派
     （列表线性扫描、字符串子串匹配、字典键存在性）。
  砖块 13 位移 '<<' '>>'：整数移位。
  砖块 14 一元开方 'sqrt'（前缀 ^ / **）：f_sqrt 用 CRT pow(x,0.5) 与 VM
     `a ** 0.5` 逐位一致；整数完全平方回退整数（^9→3），否则装箱浮点。
  砖块 15 浮点常量：mathlib 的 CONSTANTS（pi/e/tau/phi）与
     PHYSICAL_CONSTANTS（G/c/g/h_planck/N_A/R）作为静态 TYPE_FLOAT 对象发射
     （int 值如 c 走裸整数），LOAD_GLOBAL 解析；单字母常量不再静默读成 0。
  砖块 16 阶段一 数值 + 转换核心：
     - 一元数学 sin/cos/tan/asin/acos/atan/sinh/cosh/tanh/exp/log/ln/log10/
       log2/sqrt（恒浮点，对齐 mathlib 的 math.*；注意可调用 sqrt 恒浮点，
       与一元 ^ 的整数完全平方回退不同）；
     - 取整 floor/ceil/trunc/round（round 用 CRT rint 对齐 Python 半偶舍入）；
     - abs/sign/deg2rad/rad2deg、二元柯里化 pow/atan2/hypot；
     - 转换 int/_to_int/float/_to_float/str/bool；
     - 类型 type_of（英文名）/typeof（中文名）；修 typeof 关键字此前读 0 崩溃。
  砖块 16 阶段二 序列 + 字典原语（不可变语义，浅拷贝）：
      - slice(容器)(start)(stop)：复用 build_slice（越界钳制、负下标归一）；
      - append(xs)(elem)：新列表（浅拷贝 + 追加；非列表视作空列表 [elem]）；
      - mut_set_at(lst)(idx)(val)：原地改列表，越界/类型错返回 null（无异常）；
      - _dict_keys/_dict_values：新列表，按 VM 逻辑顺序（物理 pair 逆序）；
      - _dict_has(d)(k)：布尔对象；_dict_put(d)(k)(v)：新字典（已有键原位更新，
        新键物理首位 ↔ VM 逻辑末尾）；_dict_remove(d)(k)：过滤生成新字典；
      - _empty_dict：静态空字典对象（值而非可调用）。
   砖块 16 阶段三 基础原语 / 序列构造 / 文件 I/O / 进制编解码：
       - ord（UTF-8 首码点）/chr（码点→UTF-8），与 VM 的 Unicode 码点语义一致；
       - list：列表浅拷贝 / 文本→按 Unicode 码点切分的文本列表 / 字典→键列表 / 其余→null；
       - range(start)(end)：stdlib 2 参闭开区间；注意 VM 纯源码 2 参调用报错，
         故只能做原生端定点断言，无法与 VM 对拍；
       - 文件 I/O：_read_file/_write_file/_append_file（CRT fopen/fread/fwrite/
         fseek/ftell/fclose，字节 utf-8，失败静默返回 null）；
       - 进制编解码：encode_/decode_binary·ternary·decimal（逐 Unicode 码点，
         空格连接 / 空白切分）。
   砖块 17 阶段一 mathlib 数论 / 聚合：
       - 数论：阶乘（i64，n>20 溢出；n<0→0）、最大公约数(a)(b)、最小公倍数(a)(b)、
         排列数(n)(r)、组合数(n)(r)（n<r→0）、素数判定(n)、素数筛(n)（素数字列表）、
         杨辉三角(n)（前 max(n,1) 行，n<=1→[[1]]）；
        - 聚合：max/min(lst)（列表→极值元素并保留类型；非列表→原值）、
          sum(lst)（整数累加保持整数，出现浮点则整体浮点，对齐 Python sum）。
    砖块 17 阶段二 mathlib 逻辑 / 集合：
        - 逻辑：逻辑非(p)→bool；逻辑与/或(a)(b)（短路返回操作数，对齐 Python）、
          逻辑蕴含(p)(q)=(not p) or q、逻辑异或(p)(q)=(p or q) and not(p and q)、
          逻辑双蕴含(p)(q)=(p==q)（val_eq，混合整数/布尔时在 Python 的
          True==1 语义上有偏差，测试按纯布尔覆盖）；
        - 集合：集合并/交/差/补(a)(b)（ml_setify 去重 + 有符号整数升序，
          对齐 set()+sorted；集合补=集合差(全集)(子集)）、集合子集(a)(b)→bool、
          集合基数(s)=len(set(s))、集合幂集(s)（第 k 项含元素 i 当且仅当
                     k 的第 i 位为 1，对齐 _power_set）。元素判等用 val_eq；排序按有符号
          整数，非整数元素的次序未定义（既有偏差）。
     砖块 17 阶段三 mathlib 统计 / 随机：
        - 统计（确定性，与 VM 对拍）：平均值(lst)（空→int 0，否则 float）、
          中位数(lst)（ml_sort_numeric 按 double 数值插入排序，奇数→原元素、
          偶数→(a+b)/2 float，空→0）、方差(lst)（空→int 0）、
          标准差(lst)（恒 float，空→0.0）、协方差(a)(b)（长度不等/空→int 0）、
          相关系数(a)(b)（sx==0 或 sy==0→int 0）、正态密度(x)(mu)(sigma)
          （sigma<=0→int 0；1/(sigma√(2π))·e^{-(x−μ)²/(2σ²)}，CRT sqrt/exp）。
          连续求和用 ml_neumaier_add 复刻 CPython 3.12+ sum() 的补偿求和，
          与 VM 浮点结果逐位一致；
        - 随机（非确定性，仅原生定点断言）：均匀随机(a)(b)=a+(b−a)·rand、
          正态随机(mu)(sigma)=mu+sigma·z（Box-Muller）。ml_rand 为 xorshift64，
          首次以 rdtsc 播种（CRT 无 rand/srand，故不依赖外部 API）。VM 侧数值
          不可复现，无法逐行对拍，测试只断言范围/类型/多次不同。
    砖块 18 堆 GC（保守式非移动 mark-sweep）：
        - 触发：alloc 快路径发现空闲表非空或 bump 越界时跳 alloc_slow；冷路径
          「查空闲表 → 回收 → 再查 → bump」。快/冷路径维持 alloc 调用契约。
        - start_bits/mark_bits：1 bit/8 字节（各 128KB）；mark_stack：1M 槽显式
          工作栈。对象尺寸按类型标签精确推导，对象体 [obj+8,obj+size) 逐字保守扫描。
        - 根集：操作数栈 [vstack,r12)、CPU 栈 [rsp,stack_top)（含 alloc_slow 保存的
          全部 GP 寄存器）、raise_msg、全局变量单元 [cells_begin,cells_end)、
          异常处理器栈 [hstack,hstack_ptr)；stack_top 于 _start 记录。
        - sweep_start 在 main_entry 内建闭包初始化后设置：bclo:* 与堆内静态对象
          （字符串/浮点/布尔/空字典）永不回收。sweep 只扫 [sweep_start,heap_ptr)，
          未标记者回收；地址连续的死亡对象合并为单块挂入空闲表（块头 [size][next]，
          first-fit），分配时块大于请求 ≥16 字节则切出剩余部分，降低外碎片。
        - 堆耗尽（GC 后仍无可用块且 bump 越界）时经 print_uncaught 写 stderr
          诊断「内存不足」，并以退出码 1 终止；绝不越过 heap_limit（旧行为会
          覆写 start_bits/mark_bits 造成静默损坏）。
    砖块 19 嵌套文本 repr 对齐 CPython：
        - 新增 str_repr_body(rax=STR 对象)：按 CPython repr 打印引号包裹字符串，
          引号选择（含 ' 且不含 " → "，否则 '）、转义（引号/反斜杠前加反斜杠；
          \\n \\r \\t 转义序列；<0x20 或 0x7F 转 \\xNN 小写十六进制；≥0x80 原样透传）。
        - print_list 元素与 print_dict 值改经 print_repr；顶层字符串仍走
          print_value（= str()，无引号）。新增 write_span(rdx=ptr,r8=len) 低层
          写原语（保留 r10/r11 供 repr 暂存转义字节）。
        - str(列表/字典)：两遍渲染（out_mode=1 计数、=2 填充到精确分配的 STR），
          对齐 CPython 的 str==repr；容器与结果对象存帧局部作 GC 根。
        - list(文本)：按 Unicode 码点（UTF-8 前导字节定宽）切分，对齐 VM。
        - 集合字面量 {} / {1,2,3}：新增 arity-3 内建 构造集合 与 list_dedup 运行时
          （按 val_eq 去重、保序，忽略 form/variables），对齐 VM _builtin_make_set。
    BINOP 已实现：+ - * // % ** == != < > <= >= in << >>
     （编译器 _BIN_OPS 另有 '/'，其中 and/or
       已被改写为 JZ/JNZ 短路，'/' 见砖块 11）
   UNARYOP 已实现：neg not sqrt
   sqrt 前缀 '√' 解析器未产出（VM 侧同样 KeyError），仅 ^ / ** 生效。
     内建函数：NATIVE_BUILTINS（len/输出/get/错误/调用捕获 + 砖块 15/16 阶段
      一/二/三 + 砖块 17 阶段一/二/三全部内建），mathlib 全部函数已实现。

 明确不支持（抛 NativeNotSupported）：
   MathaIOError 等非原生名字，及未作为值处理的 mathlib 常量
     （调用未注册内建会在
    apply_rt 走到 ar_plain 的空地址分支，见 _dispatch）
  其余结构性限制：实参数上限 8；操作数栈固定 64KB（无溢出检查）；
    堆总量固定 8MB（保守式 mark-sweep，回收块可切分/相邻合并）；索引越界
    静默返回 0；仅生成 Windows PE64（无 ELF64/Mach-O）。

已知与 VM 的显式语义偏差（tests/test_native_heap.py 中登记）：
  缺失字典键 → 原生返回 None（VM 抛 KeyError）；
  非字典属性访问 → 原生返回 None（VM 抛 TypeError）。
闭包运行模型：
  - 环境寄存器 R13 承载「当前调用环境记录」；每个函数序言把它存入
    [rbp - 8*(nlocals+1)]（env 槽），MAKE_CLOSURE/LOAD_OUTER 均从该槽复载。
  - env 记录 = [TYPE_ENV][parent][ncap][cap0..]（MAKE_CLOSURE 时对定义帧的快照，
    盒捕获复制 Box 指针即获活语义）；closure 记录 = [TYPE_CLOSURE][fn_addr][env]。
  - _emit_call 按候选值是否落在堆区间分派：普通函数地址直接 call，
    闭包记录先载 R13=env 再 call fn_addr。
"""
from __future__ import annotations

import math
import struct
from pathlib import Path

from src.mbc import opcodes as OP

# ---- 节区布局常量 ----
TEXT_RVA = 0x1000             # .text 节 RVA（代码）
# .data 节 RVA 不再是常量：按 .text 实际大小对齐到 SectionAlignment 后确定
# （见 _emit_data_section / _build_pe）。固定值会在代码超过 4KB 时与 .text 重叠。
HEADERS_SIZE = 0x200
IMAGE_BASE = 0x140000000

# 运行时自行解析的 kernel32 API（经 PEB 遍历 + 导出表，不依赖 PE 导入表）
_APIS = ["GetStdHandle", "WriteFile", "ExitProcess",
         "LoadLibraryA", "GetProcAddress"]

# 浮点运行时经 LoadLibraryA/GetProcAddress 从 C 运行时解析的函数。
# _ecvt/_strtod 用于「Python repr 精确」浮点格式化（先取足够精确的十进制
# 展开，再由本模块按 round-half-even 自行舍入到最短可往返位数；经 30 万随机
# double 验证与 CPython repr 完全一致）。math 函数供后续数学内建使用。
_CRT_FUNCS = ["_ecvt", "strtod", "sqrt", "pow", "floor", "fmod",
              "sin", "cos", "tan", "log", "exp", "ceil",
              # 砖块 16 阶段一：数学内建所需的 CRT 数学函数
              "asin", "acos", "atan", "atan2", "sinh", "cosh", "tanh",
              "log10", "log2", "rint", "trunc", "hypot",
              # 砖块 16 阶段三：文件 I/O
              "fopen", "fread", "fwrite", "fseek", "ftell", "fclose"]

VSTACK_SIZE = 0x10000         # 64KB 操作数栈
NUMBUF_SIZE = 64              # 整数输出缓冲
HEAP_SIZE = 0x800000          # 8MB 静态堆（data 段 BSS，bump 分配）
HSTACK_SIZE = 0x10000         # 64KB 异常处理器栈（每个记录 40 字节）
HSTACK_REC = 40               # 处理器记录：[prev][rsp][rbp][r12][r13]

# 堆对象类型标签（对象头 [0]=type，[8]=len，[16..]=payload）
TYPE_STR = 1
TYPE_LIST = 2
TYPE_DICT = 3
TYPE_CLOSURE = 4
TYPE_BOX = 5
TYPE_BOOL = 6
TYPE_NULL = 7
TYPE_ENV = 8
TYPE_PARTIAL = 9
TYPE_FLOAT = 10

# 浮点对象：24 字节 [TYPE_FLOAT][len=8][double]（double 在 +16）。
FLOAT_OBJ_SIZE = 24

# 砖块 18：堆 GC（保守式非移动 mark-sweep）。
#   - start_bits：1 bit / 8 字节，标记「该地址是动态堆块起点」（GC 用）。
#   - mark_bits ：1 bit / 8 字节，标记「本轮 GC 存活」。
#   - mark_stack：显式标记工作栈（每对象至多入栈一次，容量 ≥ 最大对象数）。
GC_BITMAP_BYTES = HEAP_SIZE // 64        # 8MB / (8 字节 * 8 bit) = 128KB
GC_MARK_STACK_ENTRIES = 1 << 20          # 最多约 52 万对象，1M 槽不会溢出

# 指针区间判定：值 v 是指针 ⟺ (v - heap_base) 无符号 < HEAP_SIZE。
# 堆对象（静态串对象 + 动态分配）全部落在 [heap_base, heap_base+HEAP_SIZE)，
# 整数（含负数）不在此区间，故原地保留既有整数算术，零改造成本。


class NativeNotSupported(Exception):
    """原生后端暂不支持的字节码/数据类型。"""


# ---------------------------------------------------------------- 发射工具

class _Emitter:
    """在节区载荷中发射机器码并管理重定位。"""

    def __init__(self, base_rva: int, labels: dict | None = None):
        self.buf = bytearray()
        self.base_rva = base_rva
        self.labels: dict[str, int] = labels if labels is not None else {}
        # (载荷偏移, 标签)：RIP 相对 rel32（代码用）
        self.rip_relocs: list[tuple[int, str]] = []
        # (载荷偏移, 标签)：rel8 短跳
        self.rel8_relocs: list[tuple[int, str]] = []
        # (载荷偏移, 标签)：绝对 RVA dword（数据结构用：ILT/描述符）
        self.abs_relocs: list[tuple[int, str]] = []

    @property
    def off(self) -> int:
        return len(self.buf)

    @property
    def rva(self) -> int:
        return self.base_rva + len(self.buf)

    def label_here(self, name: str):
        if name in self.labels:
            raise AssertionError(f"标签重复: {name}")
        self.labels[name] = self.rva

    def emit(self, data: bytes):
        self.buf.extend(data)

    def align(self, n: int):
        while len(self.buf) % n:
            self.buf.append(0)

    def rel32_to(self, label: str):
        """RIP 相对：补 4 字节占位，patch 阶段填 (target - next_rva)。"""
        self.rip_relocs.append((len(self.buf), label))
        self.buf.extend(b"\x00\x00\x00\x00")

    def rel8_to(self, label: str):
        """短跳：补 1 字节占位，patch 阶段填 (target - next_off)。"""
        self.rel8_relocs.append((len(self.buf), label))
        self.buf.append(0)

    def abs_dword(self, label: str):
        """绝对 RVA 槽（导入表数据用）：补 4 字节占位。"""
        self.abs_relocs.append((len(self.buf), label))
        self.buf.extend(b"\x00\x00\x00\x00")

    def patch(self):
        for off, label in self.rip_relocs:
            disp = self.labels[label] - (self.base_rva + off + 4)
            self.buf[off:off + 4] = struct.pack("<i", disp)
        for off, label in self.rel8_relocs:
            disp = self.labels[label] - (self.base_rva + off + 1)
            if not -128 <= disp <= 127:
                raise AssertionError(f"rel8 越界: {label} disp={disp}")
            self.buf[off] = disp & 0xFF
        for off, label in self.abs_relocs:
            self.buf[off:off + 4] = struct.pack("<I", self.labels[label])

    # ---- 操作数栈（R12）----
    def push_rax(self):
        self.emit(b"\x49\x89\x04\x24")               # mov [r12], rax
        self.emit(b"\x49\x83\xC4\x08")               # add r12, 8

    def pop_to(self, reg: int):
        self.emit(b"\x49\x83\xEC\x08")               # sub r12, 8
        self.emit(bytes([0x49, 0x8B, 0x04 | (reg << 3), 0x24]))  # mov reg,[r12]

    def read_top_to(self, reg: int):
        # push 后 r12 指向栈顶之上：读 [r12-8]
        self.emit(bytes([0x49, 0x8B, 0x44 | ((reg & 7) << 3), 0x24, 0xF8]))  # mov reg,[r12-8]

    def discard(self):
        self.emit(b"\x49\x83\xEC\x08")               # sub r12, 8

    # ---- 寻址片段 ----
    def mov_rax_imm64(self, v: int):
        self.emit(b"\x48\xB8" + struct.pack("<Q", v & 0xFFFFFFFFFFFFFFFF))

    def mov_r_imm64(self, reg: int, v: int):
        rex = 0x48 | (0x01 if reg >= 8 else 0)
        self.emit(bytes([rex, 0xB8 | (reg & 7)])
                  + struct.pack("<Q", v & 0xFFFFFFFFFFFFFFFF))

    def load_local(self, slot: int, nlocals: int):
        disp = -8 * (nlocals - slot)
        self.emit(b"\x48\x8B\x85" + struct.pack("<i", disp))  # mov rax,[rbp+disp]
        self.push_rax()

    def store_local(self, slot: int, nlocals: int):
        self.pop_to(0)
        disp = -8 * (nlocals - slot)
        self.emit(b"\x48\x89\x85" + struct.pack("<i", disp))  # mov [rbp+disp],rax

    def lea_rip(self, reg: int, label: str):
        rex = 0x48 | (0x04 if reg >= 8 else 0)       # lea r64,[rip+disp]
        self.emit(bytes([rex, 0x8D, 0x05 | ((reg & 7) << 3)]))
        self.rel32_to(label)

    def load_global(self, label: str):
        self.emit(b"\x48\x8B\x05")                   # mov rax,[rip+disp]
        self.rel32_to(label)
        self.push_rax()

    def store_global(self, label: str):
        self.pop_to(0)
        self.emit(b"\x48\x89\x05")                   # mov [rip+disp],rax
        self.rel32_to(label)

    def call_rip_indirect(self, label: str):
        self.emit(b"\xFF\x15")                       # call [rip+disp]
        self.rel32_to(label)

    def call_rel32(self, label: str):
        self.emit(b"\xE8")                           # call rel32
        self.rel32_to(label)

    def jcc_rel32(self, cc: int | None, label: str):
        if cc is None:
            self.emit(b"\xE9")                       # jmp rel32
        else:
            self.emit(bytes([0x0F, cc]))             # Jcc rel32
        self.rel32_to(label)

    # ---- 通用寄存器/内存片段（异常运行时使用；统一 64 位操作）----
    @staticmethod
    def _scale_bits(scale: int) -> int:
        return {1: 0, 2: 1, 4: 2, 8: 3}[scale]

    def _emit_rm(self, reg_field: int, base: int, disp: int,
                 index: int | None = None, scale: int = 1):
        """发射 ModRM(+SIB+disp)，寻址 [base + index*scale + disp]。"""
        low_base = base & 7
        if index is None:
            if disp == 0 and low_base not in (4, 5):
                mod = 0
            elif -128 <= disp <= 127:
                mod = 1
            else:
                mod = 2
            if low_base == 4:  # rsp/r12：必须走 SIB，且不能用 mod=0
                if mod == 0:
                    mod = 1
                modrm = (mod << 6) | ((reg_field & 7) << 3) | 4
                sib = (self._scale_bits(scale) << 6) | (4 << 3) | low_base
                self.emit(bytes([modrm, sib]))
            else:
                modrm = (mod << 6) | ((reg_field & 7) << 3) | low_base
                self.emit(bytes([modrm]))
            if mod == 1:
                self.emit(bytes([disp & 0xFF]))
            elif mod == 2:
                self.emit(struct.pack("<i", disp))
        else:
            mod = 0 if disp == 0 else (1 if -128 <= disp <= 127 else 2)
            modrm = (mod << 6) | ((reg_field & 7) << 3) | 4
            sib = (self._scale_bits(scale) << 6) | ((index & 7) << 3) | low_base
            self.emit(bytes([modrm, sib]))
            if mod == 1:
                self.emit(bytes([disp & 0xFF]))
            elif mod == 2:
                self.emit(struct.pack("<i", disp))

    def mov_rr(self, dst: int, src: int):
        rex = 0x48 | (0x04 if src >= 8 else 0) | (0x01 if dst >= 8 else 0)
        self.emit(bytes([rex, 0x89, 0xC0 | ((src & 7) << 3) | (dst & 7)]))

    def mov_rd_mem(self, dst: int, base: int, disp: int = 0,
                   index: int | None = None, scale: int = 1):
        rex = (0x48 | (0x04 if dst >= 8 else 0) | (0x01 if base >= 8 else 0)
               | (0x02 if (index is not None and index >= 8) else 0))
        self.emit(bytes([rex, 0x8B]))
        self._emit_rm(dst, base, disp, index, scale)

    def movsxd_rd_mem(self, dst: int, base: int, disp: int = 0):
        """movsxd r64, dword [base+disp]（读 32 位有符号并符号扩展）。"""
        rex = 0x48 | (0x04 if dst >= 8 else 0) | (0x01 if base >= 8 else 0)
        self.emit(bytes([rex, 0x63]))
        self._emit_rm(dst, base, disp)

    def movzx_r_m8(self, dst: int, base: int, disp: int = 0):
        """movzx r32, byte [base+disp]（零扩展字节）。"""
        rex = 0x40 | (0x04 if dst >= 8 else 0) | (0x01 if base >= 8 else 0)
        self.emit(bytes([rex, 0x0F, 0xB6]))
        self._emit_rm(dst, base, disp)

    def mov_m8_ri(self, base: int, disp: int, imm: int):
        """mov byte [base+disp], imm8。"""
        rex = 0x40 | (0x01 if base >= 8 else 0)
        self.emit(bytes([rex, 0xC6]))
        self._emit_rm(0, base, disp)
        self.emit(bytes([imm & 0xFF]))

    def mov_m8_r(self, base: int, disp: int, src: int):
        """mov byte [base+disp], src8（取 src 的低 8 位）。"""
        rex = 0x40 | (0x04 if src >= 8 else 0) | (0x01 if base >= 8 else 0)
        self.emit(bytes([rex, 0x88]))
        self._emit_rm(src, base, disp)

    def mov_mem_r(self, base: int, disp: int, src: int):
        rex = 0x48 | (0x04 if src >= 8 else 0) | (0x01 if base >= 8 else 0)
        self.emit(bytes([rex, 0x89]))
        self._emit_rm(src, base, disp)

    def mov_mem_r_idx(self, base: int, src: int, disp: int = 0,
                      index: int | None = None, scale: int = 1):
        """mov [base + index*scale + disp], src（带 SIB 索引的存储）。"""
        rex = (0x48 | (0x04 if src >= 8 else 0) | (0x01 if base >= 8 else 0)
               | (0x02 if (index is not None and index >= 8) else 0))
        self.emit(bytes([rex, 0x89]))
        self._emit_rm(src, base, disp, index, scale)

    def lea_mem(self, dst: int, base: int, disp: int = 0):
        rex = 0x48 | (0x04 if dst >= 8 else 0) | (0x01 if base >= 8 else 0)
        self.emit(bytes([rex, 0x8D]))
        self._emit_rm(dst, base, disp)

    def test_rr(self, a: int, b: int):
        rex = 0x48 | (0x04 if b >= 8 else 0) | (0x01 if a >= 8 else 0)
        self.emit(bytes([rex, 0x85, 0xC0 | ((b & 7) << 3) | (a & 7)]))

    def cmp_rr(self, a: int, b: int):
        rex = 0x48 | (0x04 if b >= 8 else 0) | (0x01 if a >= 8 else 0)
        self.emit(bytes([rex, 0x39, 0xC0 | ((b & 7) << 3) | (a & 7)]))

    def xor_rr32(self, dst: int, src: int):
        rex = 0x40 | (0x04 if src >= 8 else 0) | (0x01 if dst >= 8 else 0)
        self.emit(bytes([rex, 0x31, 0xC0 | ((src & 7) << 3) | (dst & 7)]))

    def sub_rr(self, dst: int, src: int):
        rex = 0x48 | (0x04 if src >= 8 else 0) | (0x01 if dst >= 8 else 0)
        self.emit(bytes([rex, 0x29, 0xC0 | ((src & 7) << 3) | (dst & 7)]))

    def shl_ri(self, reg: int, imm: int):
        rex = 0x48 | (0x01 if reg >= 8 else 0)
        self.emit(bytes([rex, 0xC1, 0xE0 | (reg & 7), imm & 0xFF]))

    def inc_r(self, reg: int):
        rex = 0x48 | (0x01 if reg >= 8 else 0)
        self.emit(bytes([rex, 0xFF, 0xC0 | (reg & 7)]))

    def dec_r(self, reg: int):
        rex = 0x48 | (0x01 if reg >= 8 else 0)
        self.emit(bytes([rex, 0xFF, 0xC8 | (reg & 7)]))

    def mov_r_imm32(self, reg: int, imm: int):
        rex = 0x40 | (0x01 if reg >= 8 else 0)
        self.emit(bytes([rex, 0xB8 | (reg & 7)]) + struct.pack("<I", imm & 0xFFFFFFFF))

    def load_rip_to(self, reg: int, label: str):
        rex = 0x48 | (0x04 if reg >= 8 else 0)
        self.emit(bytes([rex, 0x8B, 0x05 | ((reg & 7) << 3)]))
        self.rel32_to(label)

    def store_rip_from(self, label: str, reg: int):
        rex = 0x48 | (0x04 if reg >= 8 else 0)
        self.emit(bytes([rex, 0x89, 0x05 | ((reg & 7) << 3)]))
        self.rel32_to(label)

    def and_ri(self, reg: int, imm32: int):
        """and r64, imm32（符号扩展 imm32）。"""
        rex = 0x48 | (0x01 if reg >= 8 else 0)
        self.emit(bytes([rex, 0x81, 0xE0 | (reg & 7)])
                  + struct.pack("<i", imm32))

    def add_ri(self, reg: int, imm32: int):
        """add r64, imm32（符号扩展）。"""
        rex = 0x48 | (0x01 if reg >= 8 else 0)
        self.emit(bytes([rex, 0x81, 0xC0 | (reg & 7)])
                  + struct.pack("<i", imm32))

    def cmp_ri(self, reg: int, imm32: int):
        """cmp r64, imm32（符号扩展）。"""
        rex = 0x48 | (0x01 if reg >= 8 else 0)
        self.emit(bytes([rex, 0x81, 0xF8 | (reg & 7)])
                  + struct.pack("<i", imm32))

    def shr_ri(self, reg: int, imm: int):
        rex = 0x48 | (0x01 if reg >= 8 else 0)
        self.emit(bytes([rex, 0xC1, 0xE8 | (reg & 7), imm & 0xFF]))

    def add_rr(self, dst: int, src: int):
        rex = 0x48 | (0x04 if src >= 8 else 0) | (0x01 if dst >= 8 else 0)
        self.emit(bytes([rex, 0x01, 0xC0 | ((src & 7) << 3) | (dst & 7)]))

    # ---- SSE2 双精度 ----
    def _sse_rm(self, opcode: bytes, xmm: int, base: int, disp: int):
        rex = 0x40 | (0x04 if xmm >= 8 else 0) | (0x01 if base >= 8 else 0)
        self.emit(rex.to_bytes(1, "little") + opcode)
        self._emit_rm(xmm, base, disp)

    def movsd_load(self, xmm: int, base: int, disp: int = 0):
        self._sse_rm(b"\xF2\x0F\x10", xmm, base, disp)   # movsd xmm,[base+disp]

    def movsd_store(self, base: int, disp: int, xmm: int):
        self._sse_rm(b"\xF2\x0F\x11", xmm, base, disp)   # movsd [base+disp],xmm

    def movq_xmm_r(self, xmm: int, reg: int):
        rex = 0x48 | (0x04 if xmm >= 8 else 0) | (0x01 if reg >= 8 else 0)
        self.emit(bytes([0x66, rex, 0x0F, 0x6E,
                         0xC0 | ((xmm & 7) << 3) | (reg & 7)]))

    def movq_r_xmm(self, reg: int, xmm: int):
        rex = 0x48 | (0x04 if xmm >= 8 else 0) | (0x01 if reg >= 8 else 0)
        self.emit(bytes([0x66, rex, 0x0F, 0x7E,
                         0xC0 | ((xmm & 7) << 3) | (reg & 7)]))

    def cvtsi2sd(self, xmm: int, reg: int):
        rex = 0x48 | (0x04 if xmm >= 8 else 0) | (0x01 if reg >= 8 else 0)
        self.emit(bytes([0xF2, rex, 0x0F, 0x2A,
                         0xC0 | ((xmm & 7) << 3) | (reg & 7)]))

    def cvttsd2si(self, reg: int, xmm: int):
        """cvttsd2si r64, xmm（截断向零取整；NaN/越界 → 0x8000...0000）。"""
        rex = 0x48 | (0x04 if xmm >= 8 else 0) | (0x01 if reg >= 8 else 0)
        self.emit(bytes([0xF2, rex, 0x0F, 0x2C,
                         0xC0 | ((reg & 7) << 3) | (xmm & 7)]))

    def addsd(self, dst: int, src: int):
        self.emit(b"\xF2" + bytes([0x0F, 0x58,
                    0xC0 | ((dst & 7) << 3) | (src & 7)]))

    def subsd(self, dst: int, src: int):
        self.emit(b"\xF2" + bytes([0x0F, 0x5C,
                    0xC0 | ((dst & 7) << 3) | (src & 7)]))

    def mulsd(self, dst: int, src: int):
        self.emit(b"\xF2" + bytes([0x0F, 0x59,
                    0xC0 | ((dst & 7) << 3) | (src & 7)]))

    def divsd(self, dst: int, src: int):
        self.emit(b"\xF2" + bytes([0x0F, 0x5E,
                    0xC0 | ((dst & 7) << 3) | (src & 7)]))

    def ucomisd(self, a: int, b: int):
        # UCOMISD xmm_a, xmm_b：比较 a 与 b（a 在 ModRM.reg，b 在 ModRM.rm）。
        self.emit(bytes([0x66, 0x0F, 0x2E,
                    0xC0 | ((a & 7) << 3) | (b & 7)]))

    def setcc(self, cc: int):
        self.emit(bytes([0x0F, cc, 0xC0]))          # setcc al

    def movzx_eax_al(self):
        self.emit(b"\x0F\xB6\xC0")


# ---------------------------------------------------------------- 指令发射

_CC = {"==": 0x94, "!=": 0x95, "<": 0x9C,
       ">": 0x9F, "<=": 0x9E, ">=": 0x9D}

# 浮点比较用 ucomisd 的无符号标志：a<b→CF、a==b→ZF、NaN→PF。
_FLOAT_CC = {"==": 0x94, "!=": 0x95, "<": 0x92,
             ">": 0x97, "<=": 0x96, ">=": 0x93}

_FLOAT_BINOPS = {"+": "f_add", "-": "f_sub", "*": "f_mul", "/": "f_div",
                 "//": "f_floordiv", "%": "f_mod", "**": "f_pow"}


def _emit_prologue(em: _Emitter, arity: int, nlocals: int):
    em.emit(b"\x55")                                # push rbp
    em.emit(b"\x48\x89\xE5")                        # mov rbp,rsp
    # 帧多留一个 env 槽（[rbp - 8*(nlocals+1)]），保存调用方传入的 R13 环境
    frame = max(0x20, ((nlocals + 1) * 8 + 15) & ~15)
    if frame < 128:
        em.emit(b"\x48\x83\xEC" + bytes([frame]))   # sub rsp,imm8
    else:
        em.emit(b"\x48\x81\xEC" + struct.pack("<i", frame))
    for i in range(arity):
        # M3V 栈上探（push 写 [r12] 后 add r12,8）：最后压入的 aN 在 [r12-8]，
        # a1 在 [r12-8*arity]。故第 i 个形参从 [r12-8*(arity-i)] 搬入局部槽 i。
        src_disp = -8 * (arity - i)
        dst_disp = -8 * (nlocals - i)
        em.emit(bytes([0x4D, 0x8B, 0x54, 0x24, src_disp & 0xFF]))  # mov r10,[r12+d8]（REX=WRB=0x4D：r10 目标、r12 基址、无索引）
        em.emit(b"\x4C\x89\x95" + struct.pack("<i", dst_disp))      # mov [rbp+d32],r10
    if arity:
        em.emit(b"\x49\x83\xEC" + bytes([arity * 8]))  # sub r12, arity*8
    # 保存环境寄存器到本帧 env 槽（无捕获时 R13=0，写入无害）
    env_disp = -8 * (nlocals + 1)
    em.emit(b"\x4C\x89\xAD" + struct.pack("<i", env_disp))  # mov [rbp+d32],r13


def _emit_epilogue(em: _Emitter):
    em.emit(b"\x48\x89\xEC")                        # mov rsp,rbp (ModRM EC: rsp<-rbp)
    em.emit(b"\x5D")                                # pop rbp
    em.emit(b"\xC3")                                # ret


MAX_NATIVE_ARITY = 8


def _emit_call(em: _Emitter, argc: int, tag: str, idx: int):
    """M3V CALL N：操作数栈布局 [函数, a1, …, aN]（上探，r12 指向栈顶之上）。

    a_{i+1} 位于 [r12-8*(N-i+1)]，函数块位于 [r12-8*(N+1)]。

    本实现委托运行时子程序 apply_rt(rdi=函数值, rsi=实参基址, rdx=实参数) 完成
    与 VM 相同的分派：普通函数地址直接 tail-jmp；闭包按 arity 决定直接调用、
    偏应用或重建调用；Partial 记录累积实参。apply_rt 保证返回（或 callee
    返回）时 r12 恒为「函数槽+8」，故尾序列统一。
    """
    if argc < 0:
        raise NativeNotSupported(f"原生后端收到负实参数 {argc}")
    if argc > MAX_NATIVE_ARITY:
        raise NativeNotSupported(
            f"原生后端实参数上限 {MAX_NATIVE_ARITY}：收到 {argc}")
    em.emit(bytes([0x49, 0x8B, 0x44, 0x24, (-8 * (argc + 1)) & 0xFF]))
    em.emit(b"\x4C\x89\xE6")                            # mov rsi,r12
    em.emit(b"\x48\x81\xEE" + struct.pack("<i", 8 * argc))  # sub rsi,8*argc
    em.emit(b"\x48\x89\xC7")                            # mov rdi,rax
    em.emit(b"\x48\xC7\xC2" + struct.pack("<i", argc))  # mov rdx,argc
    em.call_rel32("apply_rt")
    em.emit(b"\x49\x89\x44\x24\xF0")                    # mov [r12-16],rax
    em.emit(b"\x49\x83\xEC\x08")                        # sub r12,8


def _closure_captures(functions: dict) -> dict[str, list]:
    """静态分析各闭包目标的捕获集。

    返回 {目标函数名: [(slot, boxed), ...]}。给定 MAKE_CLOSURE 目标 G 的捕获集
    = 子树（G 及其实例化的后代）中所有落在「G 的定义帧」上的读取槽位：
    读取 (depth, slot) 沿 creator 链上溯 (depth-1) 层即得该记录所属目标。
    boxed=True 表示该槽以 LOAD_OUTER_BOX 读取（捕获时复制 Box 指针即可获活语义）。
    """
    creator: dict[str, str] = {}
    reads: dict[str, list] = {}
    for name, fn in functions.items():
        reads[name] = []
        for ins in fn.code:
            op = ins[0]
            if op == OP.MAKE_CLOSURE:
                creator[ins[1]] = name
            elif op in (OP.LOAD_OUTER, OP.LOAD_OUTER_BOX):
                reads[name].append((ins[1], ins[2], op == OP.LOAD_OUTER_BOX))
    caps: dict[str, dict[int, bool]] = {}
    for name, rds in reads.items():
        for depth, slot, boxed in rds:
            y = name
            for _ in range(depth - 1):
                y = creator.get(y)
                if y is None:
                    break
            if y is None:
                continue
            c = caps.setdefault(y, {})
            if slot not in c:
                c[slot] = boxed
            else:
                c[slot] = c[slot] or boxed
    return {y: sorted([(s, b) for s, b in c.items()]) for y, c in caps.items()}


def _emit_make_closure(em: _Emitter, target: str, capt: list,
                       tag: str, nlocals: int, arity: int):
    """MAKE_CLOSURE：分配 env 记录 + closure 记录并压入操作数栈。

    env = [TYPE_ENV][parent][ncap][cap0..]（parent=本帧 env 槽，main 为 null）；
    closure = [TYPE_CLOSURE][fn_addr][env][arity]。
    """
    nc = len(capt)
    env_size = 8 * (3 + nc)
    em.emit(b"\x48\xC7\xC7" + struct.pack("<i", env_size))  # mov rdi,env_size
    em.call_rel32("alloc")
    em.emit(b"\x48\xC7\x00" + struct.pack("<I", TYPE_ENV))  # mov [rax],TYPE_ENV
    if tag == "main":
        em.emit(b"\x31\xD2")                                # xor edx,edx（main 无 env）
    else:
        em.emit(b"\x48\x8B\x95" + struct.pack("<i", -8 * (nlocals + 1)))
    em.emit(b"\x48\x89\x50\x08")                            # mov [rax+8],rdx（parent）
    em.emit(b"\x48\xC7\x40\x10" + struct.pack("<i", nc))    # mov [rax+16],nc
    for i, (slot, _boxed) in enumerate(capt):
        src_disp = -8 * (nlocals - slot)         # 定义帧槽（本函数帧）
        em.emit(b"\x48\x8B\x95" + struct.pack("<i", src_disp))  # mov rdx,[rbp+d32]
        off = 24 + 8 * i
        if off <= 127:
            em.emit(b"\x48\x89\x50" + bytes([off]))             # mov [rax+o8],rdx
        else:
            em.emit(b"\x48\x89\x90" + struct.pack("<i", off))   # mov [rax+d32],rdx
    em.emit(b"\x49\x89\xC0")                                # mov r8,rax（env）
    em.emit(b"\x48\xC7\xC7\x20\x00\x00\x00")                # mov rdi,32
    em.call_rel32("alloc")
    em.emit(b"\x48\xC7\x00" + struct.pack("<I", TYPE_CLOSURE))
    em.lea_rip(2, f"fn:{target}")                           # lea rdx,[fn:target]
    em.emit(b"\x48\x89\x50\x08")                            # mov [rax+8],rdx
    em.emit(b"\x4C\x89\x40\x10")                            # mov [rax+16],r8
    em.emit(b"\x48\xC7\x40\x18" + struct.pack("<i", arity))  # mov [rax+24],arity
    em.push_rax()


def _emit_load_outer(em: _Emitter, depth: int, slot: int, boxed: bool,
                     tag: str, nlocals: int):
    """LOAD_OUTER(_BOX)：沿环境链 depth 层取槽；boxed 时再解 Box.value。"""
    if tag == "main":
        em.emit(b"\x4C\x89\xE8")                            # mov rax,r13
    else:
        em.emit(b"\x48\x8B\x85" + struct.pack("<i", -8 * (nlocals + 1)))
    for _ in range(depth - 1):
        em.emit(b"\x48\x8B\x40\x08")                        # mov rax,[rax+8] parent
    off = 24 + 8 * slot
    if off <= 127:
        em.emit(b"\x48\x8B\x40" + bytes([off]))             # mov rax,[rax+o8]
    else:
        em.emit(b"\x48\x8B\x80" + struct.pack("<i", off))
    if boxed:
        em.emit(b"\x48\x8B\x40\x08")                        # mov rax,[rax+8] box.value
    em.push_rax()


def _emit_apply_runtime(em: _Emitter):
    """apply_rt(rdi=函数值, rsi=实参基址 a1, rdx=实参数 N)：VM _invoke 等价物。

    操作数栈在调用点布局 [函数, a1..aN]，r12 = rsi + 8*N（函数槽 = rsi-8）。
    达成不变式：本子程序返回（或经 tail-jmp 由 callee 返回）时
    r12 = 函数槽+8，rax = 返回值（或新构造的 Partial），供 _emit_call 统一尾序列。

    分派：
      text 地址 → r13=0 后直接 jmp（普通函数/内建，恒满元调用）；
      闭包记录 [CLOSURE][fn][env][arity]：N==arity 直调；N>arity 截断直调；
        N<arity 构造 Partial（记录 n=N 个新实参）。
      Partial 记录 [PARTIAL][target][n][carried..]：total=n+N <arity → 新 Partial；
        否则重建前 arity 个实参并调用 target。
    寄存器：r13=实参数缓存；r14=实参基址；r11=当前 fn 值；rbx/r15 临时。
    """
    em.label_here("apply_rt")
    em.emit(b"\x49\x89\xF6")                            # mov r14,rsi
    em.emit(b"\x49\x89\xD5")                            # mov r13,rdx
    em.emit(b"\x48\x89\xF8")                            # mov rax,rdi
    em.lea_rip(1, "heap_base")                          # lea rcx,[heap_base]
    em.emit(b"\x48\x39\xC8")                            # cmp rax,rcx
    em.jcc_rel32(0x82, "ar_plain")                      # jb → text 函数地址
    em.emit(b"\x48\x8B\x08")                            # mov rcx,[rax] 类型
    em.emit(b"\x48\x83\xF9" + bytes([TYPE_CLOSURE]))
    em.jcc_rel32(0x84, "ar_close")
    em.emit(b"\x48\x83\xF9" + bytes([TYPE_PARTIAL]))
    em.jcc_rel32(0x84, "ar_part")
    em.emit(b"\x0F\x0B")                                # ud2（非函数值被调用）

    # ---- 普通函数：无环境，直接 jmp ----
    em.label_here("ar_plain")
    em.emit(b"\x45\x31\xED")                            # xor r13d,r13d（无外层环境）
    em.emit(b"\xFF\xE0")                                # jmp rax

    # ---- 闭包记录 ----
    em.label_here("ar_close")
    em.emit(b"\x49\x89\xC3")                            # mov r11,rax（closure 记录指针）
    em.emit(b"\x4C\x8B\x40\x08")                        # mov r8,[rax+8]  fn
    em.emit(b"\x4C\x8B\x48\x10")                        # mov r9,[rax+16] env
    em.emit(b"\x4C\x8B\x50\x18")                        # mov r10,[rax+24] arity
    em.emit(b"\x4D\x39\xD5")                            # cmp r13,r10（N vs arity）
    em.jcc_rel32(0x84, "ar_invoke")                     # je 直调
    em.jcc_rel32(0x87, "ar_excess")                     # ja 截断直调
    # N < arity：构造 Partial([closure], N 个实参)
    em.emit(b"\x4D\x89\xEF")                            # mov r15,r13
    em.emit(b"\x49\xC1\xE7\x03")                        # shl r15,3
    em.emit(b"\x49\x83\xC7\x18")                        # add r15,24
    em.emit(b"\x4C\x89\xFF")                            # mov rdi,r15
    em.call_rel32("alloc")
    em.emit(b"\x48\xC7\x00" + struct.pack("<I", TYPE_PARTIAL))
    em.emit(b"\x4C\x89\x58\x08")                        # mov [rax+8],r11（target=closure）
    em.emit(b"\x4C\x89\x68\x10")                        # mov [rax+16],r13
    em.emit(b"\x4C\x89\xE9")                            # mov rcx,r13
    em.emit(b"\x4C\x89\xF6")                            # mov rsi,r14
    em.emit(b"\x48\x8D\x78\x18")                        # lea rdi,[rax+24]
    em.emit(b"\xF3\x48\xA5")                            # rep movsq
    em.emit(b"\x49\xC1\xE5\x03")                        # shl r13,3
    em.emit(b"\x4D\x29\xEC")                            # sub r12,r13（r12=实参基址）
    em.emit(b"\x49\x89\x04\x24")                        # mov [r12],rax（Partial 压入）
    em.emit(b"\x49\x83\xC4\x08")                        # add r12,8
    em.emit(b"\xC3")                                    # ret

    em.label_here("ar_invoke")                          # N == arity
    em.emit(b"\x4D\x89\xCD")                            # mov r13,r9
    em.emit(b"\x4C\x89\xC0")                            # mov rax,r8
    em.emit(b"\xFF\xE0")                                # jmp rax（tail-call）

    em.label_here("ar_excess")                          # N > arity：取前 arity 实参
    em.emit(b"\x4C\x89\xF0")                            # mov rax,r14
    em.emit(b"\x4D\x89\xD3")                            # mov r11,r10
    em.emit(b"\x49\xC1\xE3\x03")                        # shl r11,3
    em.emit(b"\x4C\x01\xD8")                            # add rax,r11
    em.emit(b"\x49\x89\xC4")                            # mov r12,rax
    em.emit(b"\x4D\x89\xCD")                            # mov r13,r9
    em.emit(b"\x4C\x89\xC0")                            # mov rax,r8
    em.emit(b"\xFF\xE0")                                # jmp rax

    # ---- Partial 记录 [PARTIAL][target][n][carried...] ----
    em.label_here("ar_part")
    em.emit(b"\x49\x89\xC3")                            # mov r11,rax（old partial）
    em.emit(b"\x4D\x8B\x43\x08")                        # mov r8,[r11+8]  target
    em.emit(b"\x4D\x8B\x4B\x10")                        # mov r9,[r11+16] n（carried）
    em.emit(b"\x4D\x8B\x50\x18")                        # mov r10,[r8+24] arity
    em.emit(b"\x4C\x89\xCB")                            # mov rbx,r9
    em.emit(b"\x4C\x01\xEB")                            # add rbx,r13（total = n+N）
    em.emit(b"\x49\x39\xDA")                            # cmp r10,rbx（arity vs total）
    em.jcc_rel32(0x86, "ar_rebuild")                    # jbe → 重建直调
    # total < arity：构造新 Partial（carried+new）
    em.emit(b"\x48\x89\xDF")                            # mov rdi,rbx
    em.emit(b"\x48\xC1\xE7\x03")                        # shl rdi,3
    em.emit(b"\x48\x83\xC7\x18")                        # add rdi,24
    em.call_rel32("alloc")
    em.emit(b"\x48\xC7\x00" + struct.pack("<I", TYPE_PARTIAL))
    em.emit(b"\x4C\x89\x40\x08")                        # mov [rax+8],r8
    em.emit(b"\x48\x89\x58\x10")                        # mov [rax+16],rbx
    em.emit(b"\x4C\x89\xC9")                            # mov rcx,r9
    em.emit(b"\x49\x8D\x73\x18")                        # lea rsi,[r11+24]
    em.emit(b"\x48\x8D\x78\x18")                        # lea rdi,[rax+24]
    em.emit(b"\xF3\x48\xA5")                            # rep movsq（carried）
    em.emit(b"\x4C\x89\xE9")                            # mov rcx,r13
    em.emit(b"\x4C\x89\xF6")                            # mov rsi,r14
    em.emit(b"\xF3\x48\xA5")                            # rep movsq（new）
    em.emit(b"\x49\xC1\xE5\x03")                        # shl r13,3
    em.emit(b"\x4D\x29\xEC")                            # sub r12,r13
    em.emit(b"\x49\x89\x04\x24")                        # mov [r12],rax
    em.emit(b"\x49\x83\xC4\x08")                        # add r12,8
    em.emit(b"\xC3")                                    # ret

    # ---- 重建并调用（total >= arity）----
    em.label_here("ar_rebuild")
    em.emit(b"\x4D\x39\xD1")                            # cmp r9,r10（n vs arity）
    em.jcc_rel32(0x83, "ar_rb_carry")                   # jae → 仅 carried
    # n < arity：把前 take_n=(arity-n) 个 new 实参倒序上移 8n。
    # 覆盖：dst 区间 [r14+8n, r14+8*arity) 与 src 区间 [r14, r14+8*take_n) 重叠，
    # 故自高端向低端搬移。
    em.emit(b"\x4C\x89\xD1")                            # mov rcx,r10（arity）
    em.emit(b"\x4C\x29\xC9")                            # sub rcx,r9（take_n=arity-n）
    em.emit(b"\x49\x89\xCF")                            # mov r15,rcx
    em.emit(b"\x49\xC1\xE7\x03")                        # shl r15,3
    em.emit(b"\x4D\x01\xF7")                            # add r15,r14（src 高端）
    em.emit(b"\x4C\x89\xFE")                            # mov rsi,r15
    em.emit(b"\x4D\x89\xD7")                            # mov r15,r10
    em.emit(b"\x49\xC1\xE7\x03")                        # shl r15,3
    em.emit(b"\x4D\x01\xF7")                            # add r15,r14（dst 高端）
    em.emit(b"\x4C\x89\xFF")                            # mov rdi,r15
    em.label_here("ar_rb_loop")
    em.emit(b"\x48\x83\xEE\x08")                        # sub rsi,8
    em.emit(b"\x48\x83\xEF\x08")                        # sub rdi,8
    em.emit(b"\x48\x8B\x06")                            # mov rax,[rsi]
    em.emit(b"\x48\x89\x07")                            # mov [rdi],rax
    em.emit(b"\x48\xFF\xC9")                            # dec rcx
    em.jcc_rel32(0x85, "ar_rb_loop")                    # jnz
    em.label_here("ar_rb_carry")
    # rcx = min(n, arity)，把 carried 拷到 [r14..]
    em.emit(b"\x4C\x89\xC9")                            # mov rcx,r9（n）
    em.emit(b"\x4D\x39\xD1")                            # cmp r9,r10
    em.jcc_rel32(0x86, "ar_rb_skip")                    # jbe skip（n<=arity）
    em.emit(b"\x4C\x89\xD1")                            # mov rcx,r10（arity）
    em.label_here("ar_rb_skip")
    em.emit(b"\x49\x8D\x73\x18")                        # lea rsi,[r11+24]（carried 区）
    em.emit(b"\x4C\x89\xF7")                            # mov rdi,r14
    em.emit(b"\xF3\x48\xA5")                            # rep movsq
    # r12 = r14 + 8*arity；环境 = [target+16]；调用
    em.emit(b"\x4C\x89\xF0")                            # mov rax,r14
    em.emit(b"\x4C\x89\xD1")                            # mov rcx,r10
    em.emit(b"\x48\xC1\xE1\x03")                        # shl rcx,3
    em.emit(b"\x48\x01\xC8")                            # add rax,rcx
    em.emit(b"\x49\x89\xC4")                            # mov r12,rax
    em.emit(b"\x4D\x8B\x68\x10")                        # mov r13,[r8+16]
    em.emit(b"\x49\x8B\x40\x08")                        # mov rax,[r8+8]
    em.emit(b"\xFF\xE0")                                # jmp rax


def _emit_resolve_apis(em: _Emitter):
    """引导：PEB 遍历找 kernel32 基址，解析导出表，填充 api_* 槽。

    不依赖 PE 导入表（手写 PE 的数据目录导入在部分加载器上被静默忽略，
    故采用运行时自解析）。寄存器约定：rbx=k32 基址，r9=名称表，
    r10=序号表，r11=函数地址表，rcx=倒计数，rax/rdx/rdi/rsi 临时。
    """
    em.emit(b"\x65\x48\x8B\x04\x25\x60\x00\x00\x00")   # mov rax, gs:[0x60] PEB
    em.emit(b"\x48\x8B\x40\x18")                        # mov rax,[rax+0x18] Ldr
    em.emit(b"\x48\x8D\x50\x20")                        # lea rdx,[rax+0x20] 链表头
    em.label_here("rs_mod")
    em.emit(b"\x48\x8B\x12")                            # mov rdx,[rdx]（→条目+0x10）
    em.emit(b"\x48\x8D\x48\x20")                        # lea rcx,[rax+0x20] 表头
    em.emit(b"\x48\x39\xCA")                            # cmp rdx,rcx
    em.jcc_rel32(0x84, "rs_fail")                       # 回到表头=未找到
    # rdx 指向条目.InMemoryOrderLinks（条目基址+0x10）：
    # DllBase = 条目+0x30 = rdx+0x20；BaseDllName.Length = rdx+0x48；Buffer = rdx+0x50
    em.emit(b"\x66\x81\x7A\x48\x18\x00")                # cmp word[rdx+0x48],24
    em.jcc_rel32(0x85, "rs_mod")
    em.emit(b"\x48\x8B\x7A\x50")                        # mov rdi,[rdx+0x50] 名称缓冲
    for i, dw in enumerate([0x0045004B, 0x004E0052, 0x004C0045,
                            0x00320033, 0x0044002E, 0x004C004C]):
        em.emit(b"\x81\x3F" + struct.pack("<I", dw))    # cmp dword[rdi],"KE"..
        em.jcc_rel32(0x85, "rs_mod")
        if i < 5:
            em.emit(b"\x48\x83\xC7\x04")                # add rdi,4
    em.emit(b"\x48\x8B\x5A\x20")                        # mov rbx,[rdx+0x20] DllBase

    # 定位导出表（r8=导出目录 VA）
    em.emit(b"\x8B\x43\x3C")                            # mov eax,[rbx+0x3C]
    em.emit(b"\x48\x8D\x04\x03")                        # lea rax,[rbx+rax] NT头
    em.emit(b"\x8B\x80\x88\x00\x00\x00")                # mov eax,[rax+0x88] 导出目录RVA
    em.emit(b"\x4C\x8D\x04\x03")                        # lea r8,[rbx+rax]
    em.emit(b"\x45\x8B\x48\x20")                        # mov r9d,[r8+0x20] 名称表RVA
    em.emit(b"\x45\x8B\x50\x24")                        # mov r10d,[r8+0x24] 序号表RVA
    em.emit(b"\x45\x8B\x58\x1C")                        # mov r11d,[r8+0x1C] 函数表RVA
    em.emit(b"\x41\x8B\x48\x18")                        # mov ecx,[r8+0x18] 名称数
    em.emit(b"\x49\x01\xD9")                            # add r9,rbx
    em.emit(b"\x49\x01\xDA")                            # add r10,rbx
    em.emit(b"\x49\x01\xDB")                            # add r11,rbx

    def resolve_common(slot: str):
        """当前 rcx=名称下标：取序号 → 取函数地址 → 存 api 槽。"""
        em.emit(b"\x41\x0F\xB7\x04\x4A")                # movzx eax,word[r10+rcx*2]
        em.emit(b"\x41\x8B\x04\x83")                    # mov eax,[r11+rax*4]
        em.emit(b"\x48\x8D\x04\x03")                    # lea rax,[rbx+rax]
        em.emit(b"\x48\x89\x05")                        # mov [rip+slot],rax
        em.rel32_to(slot)

    em.label_here("rs_exp")
    em.emit(b"\xFF\xC9")                                # dec ecx
    em.emit(b"\x41\x8B\x14\x89")                        # mov edx,[r9+rcx*4] 名称RVA(32位)
    em.emit(b"\x48\x8D\x14\x13")                        # lea rdx,[rbx+rdx]
    em.emit(b"\x8B\x02")                                # mov eax,[rdx]
    em.emit(b"\x3D" + struct.pack("<I", 0x53746547))    # cmp eax,"GetS"
    em.jcc_rel32(0x85, "rs_writ")
    em.emit(b"\x48\x8B\x7A\x04")                        # mov rdi,[rdx+4]
    em.emit(b"\x48\xBE" + struct.pack("<Q", 0x656C646E61486474))  # "tdHandle"
    em.emit(b"\x48\x39\xF7")                            # cmp rdi,rsi
    em.jcc_rel32(0x85, "rs_next")
    em.emit(b"\x80\x7A\x0C\x00")                        # cmp byte[rdx+12],0
    em.jcc_rel32(0x85, "rs_next")
    resolve_common("api_GetStdHandle")
    em.jcc_rel32(None, "rs_next")

    em.label_here("rs_writ")
    em.emit(b"\x3D" + struct.pack("<I", 0x74697257))    # cmp eax,"Writ"
    em.jcc_rel32(0x85, "rs_exit")
    em.emit(b"\x48\x8B\x3A")                            # mov rdi,[rdx]
    em.emit(b"\x48\xBE" + struct.pack("<Q", 0x6C69466574697257))  # "WriteFil"
    em.emit(b"\x48\x39\xF7")                            # cmp rdi,rsi
    em.jcc_rel32(0x85, "rs_next")
    em.emit(b"\x80\x7A\x08\x65")                        # cmp byte[rdx+8],'e'
    em.jcc_rel32(0x85, "rs_next")
    em.emit(b"\x80\x7A\x09\x00")                        # cmp byte[rdx+9],0
    em.jcc_rel32(0x85, "rs_next")
    resolve_common("api_WriteFile")
    em.jcc_rel32(None, "rs_next")

    em.label_here("rs_exit")
    em.emit(b"\x3D" + struct.pack("<I", 0x74697845))    # cmp eax,"Exit"
    em.jcc_rel32(0x85, "rs_load")
    em.emit(b"\x48\x8B\x3A")                            # mov rdi,[rdx]
    em.emit(b"\x48\xBE" + struct.pack("<Q", 0x636F725074697845))  # "ExitProc"
    em.emit(b"\x48\x39\xF7")                            # cmp rdi,rsi
    em.jcc_rel32(0x85, "rs_next")
    em.emit(b"\x81\x7A\x08" + struct.pack("<I", 0x00737365))  # cmp dword[rdx+8],"ess\0"
    em.jcc_rel32(0x85, "rs_next")
    resolve_common("api_ExitProcess")

    # LoadLibraryA（"LoadLibr" + "aryA\0"）
    em.label_here("rs_load")
    em.emit(b"\x3D" + struct.pack("<I", 0x64616F4C))    # cmp eax,"Load"
    em.jcc_rel32(0x85, "rs_getp")
    em.emit(b"\x48\x8B\x3A")                            # mov rdi,[rdx]
    em.mov_r_imm64(6, 0x7262694C64616F4C)               # rsi="LoadLibr"
    em.emit(b"\x48\x39\xF7")                            # cmp rdi,rsi
    em.jcc_rel32(0x85, "rs_next")
    em.emit(b"\x81\x7A\x08" + struct.pack("<I", 0x41797261))  # cmp dword[rdx+8],"aryA"
    em.jcc_rel32(0x85, "rs_next")
    em.emit(b"\x80\x7A\x0C\x00")                        # cmp byte[rdx+12],0
    em.jcc_rel32(0x85, "rs_next")
    resolve_common("api_LoadLibraryA")
    em.jcc_rel32(None, "rs_next")

    # GetProcAddress（首 dword "GetP"；+4..+11 "rocAddre"；+12 's'；+13 0）
    em.label_here("rs_getp")
    em.emit(b"\x3D" + struct.pack("<I", 0x50746547))    # cmp eax,"GetP"
    em.jcc_rel32(0x85, "rs_next")
    em.emit(b"\x48\x8B\x7A\x04")                        # mov rdi,[rdx+4]
    em.mov_r_imm64(6, 0x6572646441636F72)               # rsi="rocAddre"
    em.emit(b"\x48\x39\xF7")                            # cmp rdi,rsi
    em.jcc_rel32(0x85, "rs_next")
    em.emit(b"\x80\x7A\x0C\x73")                        # cmp byte[rdx+12],'s'
    em.jcc_rel32(0x85, "rs_next")
    em.emit(b"\x80\x7A\x0D\x73")                        # cmp byte[rdx+13],'s'
    em.jcc_rel32(0x85, "rs_next")
    em.emit(b"\x80\x7A\x0E\x00")                        # cmp byte[rdx+14],0
    em.jcc_rel32(0x85, "rs_next")
    resolve_common("api_GetProcAddress")

    em.label_here("rs_next")
    em.emit(b"\x85\xC9")                                # test ecx,ecx
    em.jcc_rel32(0x85, "rs_exp")
    em.jcc_rel32(None, "rs_done")                       # 遍历结束 → 主代码
    em.label_here("rs_fail")
    em.emit(b"\x0F\x0B")                                # ud2（未找到 kernel32）
    em.label_here("rs_done")


def _emit_print_int(em: _Emitter):
    """print_int：打印 rax 中的整数（十进制+CRLF）；不触碰操作数栈。"""
    em.label_here("print_int")
    em.emit(b"\x55")                                # push rbp
    em.emit(b"\x48\x89\xE5")                        # mov rbp,rsp
    em.emit(b"\x48\x83\xEC\x40")                    # sub rsp,0x40
    em.emit(b"\x45\x31\xD2")                        # xor r10d,r10d（符号标志）
    em.emit(b"\x48\x85\xC0")                        # test rax,rax
    em.jcc_rel32(0x89, "pi_nonneg")                 # jns nonneg
    em.emit(b"\x41\xBA\x01\x00\x00\x00")            # mov r10d,1
    em.emit(b"\x48\xF7\xD8")                        # neg rax
    em.label_here("pi_nonneg")
    em.lea_rip(6, "numbuf")                         # lea rsi,[numbuf]
    em.emit(b"\x48\x8D\x7E\x3E")                    # lea rdi,[rsi+62]（数字区上界）
    em.label_here("pi_loop")
    em.emit(b"\x31\xD2")                            # xor edx,edx
    em.emit(b"\xB9\x0A\x00\x00\x00")                # mov ecx,10
    em.emit(b"\x48\xF7\xF1")                        # div rcx
    em.emit(b"\x80\xC2\x30")                        # add dl,'0'
    em.emit(b"\x48\xFF\xCF")                        # dec rdi
    em.emit(b"\x88\x17")                            # mov [rdi],dl
    em.emit(b"\x48\x85\xC0")                        # test rax,rax
    em.jcc_rel32(0x85, "pi_loop")                   # jnz loop
    em.emit(b"\x45\x85\xD2")                        # test r10d,r10d
    em.jcc_rel32(0x84, "pi_nosign")                 # jz nosign
    em.emit(b"\x48\xFF\xCF")                        # dec rdi
    em.emit(b"\xC6\x07\x2D")                        # mov byte[rdi],'-'
    em.label_here("pi_nosign")
    em.emit(b"\x48\x89\xFA")                        # mov rdx,rdi（缓冲区起点）
    em.emit(b"\x4C\x8D\x46\x3E")                    # lea r8,[rsi+62]（数字区上界）
    em.emit(b"\x49\x29\xF8")                        # sub r8,rdi（长度=上界-起点）
    em.call_rel32("write_span")                     # 经输出汇（stdout/计数/缓冲）
    _emit_epilogue(em)


def _emit_heap_runtime(em: _Emitter):
    """堆 + 字符串运行时子程序。约定：所有子程序遵循 Win64 ABI。

    alloc(rdi=size) → rax=ptr            堆 bump 分配（8 字节对齐）
    str_concat(rax=l,rcx=r) → rax        字符串拼接（新分配）
    seq_repeat(rax=seq,rcx=n) → rax       字符串/列表重复（`s * n` / `n * s`）
    str_eq(rax=l,rcx=r) → rax=1/0        字符串内容相等
    print_raw(rax=ptr)                   写字符串字节（无换行）
    print_value(rax=value)               按类型分派打印（无尾随换行）
    """
    # ---- alloc ----
    # 热路径：bump 分配。契约不变——仅破坏 rax/rdx（rcx 用 push/pop 保护）。
    # 在对象头置 start bit（1 bit/8 字节）。当 free list 非空或越界时转 alloc_slow。
    em.label_here("alloc")
    em.emit(b"\x48\x8B\x05")                        # mov rax,[rip+heap_ptr]
    em.rel32_to("heap_ptr")
    em.emit(b"\x48\x89\xC2")                        # mov rdx,rax
    em.emit(b"\x48\x01\xFA")                        # add rdx,rdi
    em.emit(b"\x48\x83\xC2\x07")                    # add rdx,7
    em.emit(b"\x48\x83\xE2\xF8")                    # and rdx,-8
    em.emit(b"\x48\x83\x3D")                        # cmp qword [rip+free_head],0
    em.rel32_to("free_head")
    em.emit(b"\x00")
    em.jcc_rel32(0x85, "alloc_slow")                # jne slow（有回收块可用）
    em.emit(b"\x48\x3B\x15")                        # cmp rdx,[rip+heap_limit]
    em.rel32_to("heap_limit")
    em.jcc_rel32(0x87, "alloc_slow")                # ja slow（越界）
    em.emit(b"\x48\x89\x15")                        # mov [rip+heap_ptr],rdx
    em.rel32_to("heap_ptr")
    em.emit(b"\x51")                                # push rcx
    em.emit(b"\x48\x89\xC1")                        # mov rcx,rax
    em.lea_rip(2, "heap_base")                      # lea rdx,[heap_base]
    em.emit(b"\x48\x29\xD1")                        # sub rcx,rdx
    em.emit(b"\x48\xC1\xE9\x03")                    # shr rcx,3
    em.emit(b"\x48\x0F\xAB\x0D")                    # bts qword [rip+start_bits],rcx
    em.rel32_to("start_bits")
    em.emit(b"\x59")                                # pop rcx
    em.emit(b"\xC3")                                # ret

    # ---- str_concat ----
    em.label_here("str_concat")
    em.emit(b"\x41\x55")                            # push r13
    em.emit(b"\x41\x56")                            # push r14
    em.emit(b"\x41\x57")                            # push r15
    em.emit(b"\x49\x89\xC5")                        # mov r13,rax
    em.emit(b"\x49\x89\xCE")                        # mov r14,rcx
    em.emit(b"\x4D\x8B\x7D\x08")                    # mov r15,[r13+8]  len_l
    em.emit(b"\x49\x8B\x7E\x08")                    # mov rdi,[r14+8]  len_r
    em.emit(b"\x4C\x01\xFF")                        # add rdi,r15
    em.emit(b"\x48\x83\xC7\x10")                    # add rdi,16
    em.call_rel32("alloc")
    em.emit(b"\x48\xC7\x00" + struct.pack("<I", TYPE_STR))  # mov [rax],TYPE_STR
    em.emit(b"\x4C\x89\xFA")                        # mov rdx,r15
    em.emit(b"\x49\x03\x56\x08")                    # add rdx,[r14+8]
    em.emit(b"\x48\x89\x50\x08")                    # mov [rax+8],rdx
    em.emit(b"\x48\x8D\x78\x10")                    # lea rdi,[rax+16]
    em.emit(b"\x49\x8D\x75\x10")                    # lea rsi,[r13+16]
    em.emit(b"\x4C\x89\xF9")                        # mov rcx,r15
    em.emit(b"\xF3\xA4")                            # rep movsb
    em.emit(b"\x49\x8D\x76\x10")                    # lea rsi,[r14+16]
    em.emit(b"\x49\x8B\x4E\x08")                    # mov rcx,[r14+8]
    em.emit(b"\xF3\xA4")                            # rep movsb
    em.emit(b"\x41\x5F")                            # pop r15
    em.emit(b"\x41\x5E")                            # pop r14
    em.emit(b"\x41\x5D")                            # pop r13
    em.emit(b"\xC3")                                # ret

    # ---- seq_repeat：rax=序列, rcx=次数 → rax ----
    # 支撑 `s * n` / `n * s`，与 vm._BINOPS 的 Python `a * b` 对齐。
    # 旧实现对 `*` 直接 imul：字符串/列表的堆地址被当整数相乘，返回裸指针
    # 422100834892608（静默出错，比崩溃更难查）。
    # 这里不自己算总长度、也不手写 rep movsb/movsq 拷贝循环，而是复用已经过
    # 字节级校验的 str_concat/list_concat 走「倍增」：逐位看次数，当前位为 1
    # 就把单元接到结果后面，然后把单元自身加倍、次数右移。循环只有 O(log n)
    # 轮，且每轮都是现成的拼接实现，避免了自造拷贝循环算错对象头/写越界。
    # 次数 <= 0 或单元为空时给同型空对象（Python 亦如此）；字典等非序列返回
    # None，与本后端 +/str() 一致；次数大到必然装不下堆时也返回 None，不去
    # 撞分配器的越界分支。
    # 寄存器：r13=单元，r14=剩余次数，r15=结果。
    em.label_here("seq_repeat")
    em.emit(b"\x41\x56")                            # push r14
    em.emit(b"\x41\x57")                            # push r15
    em.emit(b"\x53")                                # push rbx
    em.emit(b"\x41\x55")                            # push r13
    em.mov_rr(13, 0)                                # mov r13,rax  序列=单元
    em.mov_rr(14, 1)                                # mov r14,rcx  次数
    em.mov_rr(1, 13)                                # mov rcx,r13
    em.lea_rip(2, "heap_base")                      # lea rdx,[heap_base]
    em.sub_rr(1, 2)                                 # sub rcx,rdx
    em.cmp_ri(1, HEAP_SIZE)
    em.jcc_rel32(0x83, "sqr_none")                  # jae 非堆指针
    em.emit(b"\x41\x8B\x7D\x00")                 # mov edi,[r13+0]  类型标签
    em.emit(b"\x83\xFF" + bytes([TYPE_STR]))       # cmp edi,TYPE_STR
    em.jcc_rel32(0x84, "sqr_str")
    em.emit(b"\x83\xFF" + bytes([TYPE_LIST]))      # cmp edi,TYPE_LIST
    em.jcc_rel32(0x84, "sqr_list")
    em.jcc_rel32(None, "sqr_none")                  # 字典等非序列
    # ---- 字符串倍增 ----
    em.label_here("sqr_str")
    em.emit(b"\x4D\x85\xF6")                      # test r14,r14
    em.jcc_rel32(0x8E, "sqr_str_empty")             # jle  次数 <= 0
    em.emit(b"\x49\x81\xFE" + struct.pack("<I", HEAP_SIZE - 64))
    em.jcc_rel32(0x83, "sqr_none")                  # jae 次数必然装不下
    em.emit(b"\x45\x31\xFF")                      # xor r15d,r15d  结果=尚无
    em.label_here("sqr_str_loop")
    em.emit(b"\x4D\x85\xF6")                      # test r14,r14
    em.jcc_rel32(0x84, "sqr_str_done")
    em.emit(b"\x49\xF7\xC6\x01\x00\x00\x00")    # test r14,1
    em.jcc_rel32(0x84, "sqr_str_even")
    em.emit(b"\x4D\x85\xFF")                      # test r15,r15
    em.jcc_rel32(0x84, "sqr_str_first")             # 还没有结果，直接拿单元
    em.mov_rr(0, 15)                                # mov rax,结果
    em.mov_rr(1, 13)                                # mov rcx,单元
    em.call_rel32("str_concat")
    em.mov_rr(15, 0)                                # mov r15,rax  结果=拼接后
    em.jcc_rel32(None, "sqr_str_even")
    em.label_here("sqr_str_first")
    em.emit(b"\x4D\x89\xEF")                      # mov r15,r13  结果=单元
    em.label_here("sqr_str_even")
    em.emit(b"\x49\xC1\xEE\x01")                 # shr r14,1
    em.emit(b"\x4D\x85\xF6")
    em.jcc_rel32(0x84, "sqr_str_done")              # 计数已耗尽
    em.mov_rr(0, 13)                                # 单元与自身拼接 = 加倍
    em.mov_rr(1, 13)
    em.call_rel32("str_concat")
    em.mov_rr(13, 0)                                # mov r13,rax  单元=加倍后
    em.jcc_rel32(None, "sqr_str_loop")
    em.label_here("sqr_str_done")
    em.mov_rr(0, 15)                                # mov rax,结果
    em.jcc_rel32(None, "sqr_done")
    em.label_here("sqr_str_empty")
    em.emit(b"\x48\xC7\xC7\x10\x00\x00\x00")   # mov rdi,16
    em.call_rel32("alloc")
    em.emit(b"\x48\xC7\x00" + struct.pack("<I", TYPE_STR))
    em.emit(b"\x48\xC7\x40\x08\x00\x00\x00\x00")  # mov qword [rax+8],0
    em.jcc_rel32(None, "sqr_done")
    # ---- 列表倍增 ----
    em.label_here("sqr_list")
    em.emit(b"\x4D\x85\xF6")
    em.jcc_rel32(0x8E, "sqr_list_empty")            # jle  次数 <= 0
    em.emit(b"\x49\x81\xFE" + struct.pack("<I", HEAP_SIZE - 64))
    em.jcc_rel32(0x83, "sqr_none")
    em.emit(b"\x45\x31\xFF")                      # xor r15d,r15d
    em.label_here("sqr_list_loop")
    em.emit(b"\x4D\x85\xF6")
    em.jcc_rel32(0x84, "sqr_list_done")
    em.emit(b"\x49\xF7\xC6\x01\x00\x00\x00")    # test r14,1
    em.jcc_rel32(0x84, "sqr_list_even")
    em.emit(b"\x4D\x85\xFF")
    em.jcc_rel32(0x84, "sqr_list_first")
    em.mov_rr(0, 15)
    em.mov_rr(1, 13)
    em.call_rel32("list_concat")
    em.mov_rr(15, 0)
    em.jcc_rel32(None, "sqr_list_even")
    em.label_here("sqr_list_first")
    em.emit(b"\x4D\x89\xEF")                      # mov r15,r13
    em.label_here("sqr_list_even")
    em.emit(b"\x49\xC1\xEE\x01")
    em.emit(b"\x4D\x85\xF6")
    em.jcc_rel32(0x84, "sqr_list_done")
    em.mov_rr(0, 13)
    em.mov_rr(1, 13)
    em.call_rel32("list_concat")
    em.mov_rr(13, 0)
    em.jcc_rel32(None, "sqr_list_loop")
    em.label_here("sqr_list_done")
    em.mov_rr(0, 15)
    em.jcc_rel32(None, "sqr_done")
    em.label_here("sqr_list_empty")
    em.emit(b"\x48\xC7\xC7\x10\x00\x00\x00")
    em.call_rel32("alloc")
    em.emit(b"\x48\xC7\x00" + struct.pack("<I", TYPE_LIST))
    em.emit(b"\x48\xC7\x40\x08\x00\x00\x00\x00")
    em.jcc_rel32(None, "sqr_done")
    # ---- 非序列 / 次数过大 → None ----
    em.label_here("sqr_none")
    em.lea_rip(0, "null_obj")
    em.label_here("sqr_done")
    em.emit(b"\x41\x5D")                            # pop r13
    em.emit(b"\x5B")                                # pop rbx
    em.emit(b"\x41\x5F")                            # pop r15
    em.emit(b"\x41\x5E")                            # pop r14
    em.emit(b"\xC3")                                # ret

    # ---- str_eq ----
    em.label_here("str_eq")
    em.emit(b"\x4C\x8B\x40\x08")                    # mov r8,[rax+8]   len_l
    em.emit(b"\x4C\x3B\x41\x08")                    # cmp r8,[rcx+8]   len_r
    em.jcc_rel32(0x85, "se_ne")                     # jne ne
    em.emit(b"\x48\x8D\x70\x10")                    # lea rsi,[rax+16]
    em.emit(b"\x48\x8D\x79\x10")                    # lea rdi,[rcx+16]
    em.emit(b"\x4D\x89\xC1")                        # mov r9,r8
    em.label_here("se_loop")
    em.emit(b"\x4D\x85\xC9")                        # test r9,r9
    em.jcc_rel32(0x84, "se_eq")                     # jz eq
    em.emit(b"\x8A\x06")                            # mov al,[rsi]
    em.emit(b"\x3A\x07")                            # cmp al,[rdi]
    em.jcc_rel32(0x85, "se_ne")                     # jne ne
    em.emit(b"\x48\xFF\xC6")                        # inc rsi
    em.emit(b"\x48\xFF\xC7")                        # inc rdi
    em.emit(b"\x49\xFF\xC9")                        # dec r9
    em.jcc_rel32(None, "se_loop")                   # jmp loop
    em.label_here("se_eq")
    em.emit(b"\xB8\x01\x00\x00\x00")                # mov eax,1
    em.emit(b"\xC3")                                # ret
    em.label_here("se_ne")
    em.emit(b"\x31\xC0")                            # xor eax,eax
    em.emit(b"\xC3")                                # ret

    # ---- is_container(rax) → eax=1/0 ----
    # 只认字符串/列表/字典三种真容器。用于把「是堆指针」细化到「是哪种容器」：
    # 单靠「左值落在堆区间」无法区分整数与容器，会让 [1]+[2] 误走字符串拼接。
    em.label_here("is_container")
    em.mov_rr(1, 0)                                 # mov rcx,rax
    em.lea_rip(2, "heap_base")                      # lea rdx,[heap_base]
    em.sub_rr(1, 2)                                 # sub rcx,rdx
    em.cmp_ri(1, HEAP_SIZE)                         # cmp rcx,HEAP_SIZE
    em.jcc_rel32(0x83, "isc_no")                    # jae 非堆指针
    em.emit(b"\x8B\x08")                            # mov ecx,[rax]  类型标签
    em.emit(b"\x83\xF9" + bytes([TYPE_STR]))        # cmp ecx,TYPE_STR
    em.jcc_rel32(0x84, "isc_yes")
    em.emit(b"\x83\xF9" + bytes([TYPE_LIST]))       # cmp ecx,TYPE_LIST
    em.jcc_rel32(0x84, "isc_yes")
    em.emit(b"\x83\xF9" + bytes([TYPE_DICT]))       # cmp ecx,TYPE_DICT
    em.jcc_rel32(0x84, "isc_yes")
    em.label_here("isc_no")
    em.emit(b"\x31\xC0\xC3")                        # xor eax,eax; ret
    em.label_here("isc_yes")
    em.emit(b"\xB8\x01\x00\x00\x00\xC3")            # mov eax,1; ret

    # ---- list_concat：rax=l, rcx=r → rax（元素是 8 字节指针，按序拼接）----
    # 对象布局 [TYPE_LIST][n][n 个元素指针]，故大小是 16+8n、载荷从 +16 起。
    em.label_here("list_concat")
    em.emit(b"\x41\x55")                            # push r13
    em.emit(b"\x41\x56")                            # push r14
    em.emit(b"\x41\x57")                            # push r15
    em.mov_rr(13, 0)                                # mov r13,rax   左
    em.mov_rr(14, 1)                                # mov r14,rcx   右
    em.mov_rd_mem(15, 13, 8)                        # mov r15,[r13+8]  n_l
    em.mov_rd_mem(7, 14, 8)                         # mov rdi,[r14+8]  n_r
    em.emit(b"\x4C\x01\xFF")                        # add rdi,r15       n_l+n_r
    em.emit(b"\x48\xC1\xE7\x03")                    # shl rdi,3        *8
    em.add_ri(7, 16)                                # add rdi,16       +头
    em.call_rel32("alloc")
    em.emit(b"\x48\xC7\x00" + struct.pack("<I", TYPE_LIST))  # mov [rax],TYPE_LIST
    em.mov_rr(2, 15)                                # mov rdx,r15
    em.emit(b"\x49\x03\x56\x08")                    # add rdx,[r14+8]  总元素数
    em.mov_mem_r(0, 8, 2)                           # mov [rax+8],rdx
    em.lea_mem(7, 0, 16)                            # lea rdi,[rax+16]
    em.lea_mem(6, 13, 16)                           # lea rsi,[r13+16]
    em.mov_rr(1, 15)                                # mov rcx,r15
    em.emit(b"\xF3\x48\xA5")                        # rep movsq  拷左
    # rep movsq 会走完 rsi/rcx，右侧源与计数必须重算（不能沿用上一轮的值）
    em.lea_mem(6, 14, 16)                           # lea rsi,[r14+16]
    em.mov_rd_mem(1, 14, 8)                         # mov rcx,[r14+8]  n_r
    em.emit(b"\xF3\x48\xA5")                        # rep movsq  拷右
    em.emit(b"\x41\x5F")                            # pop r15
    em.emit(b"\x41\x5E")                            # pop r14
    em.emit(b"\x41\x5D")                            # pop r13
    em.emit(b"\xC3")                                # ret

    # ---- truthy：ZF=1 ⟺ 假值（Python 语义：0/null/False/空串/空表/空字典）----
    em.label_here("truthy")
    em.emit(b"\x48\x89\xC1")                        # mov rcx,rax
    em.lea_rip(2, "heap_base")                      # lea rdx,[heap_base]
    em.emit(b"\x48\x29\xD1")                        # sub rcx,rdx
    em.emit(b"\x48\x81\xF9" + struct.pack("<I", HEAP_SIZE))
    em.jcc_rel32(0x82, "ty_ptr")                    # jb ptr
    em.emit(b"\x48\x85\xC0")                        # test rax,rax（整数）
    em.emit(b"\xC3")                                # ret
    em.label_here("ty_ptr")
    em.emit(b"\x48\x8B\x08")                        # mov rcx,[rax]
    em.emit(b"\x48\x83\xF9" + bytes([TYPE_BOOL]))   # cmp rcx,TYPE_BOOL
    em.jcc_rel32(0x84, "ty_bool")                   # je bool
    em.emit(b"\x48\x83\xF9" + bytes([TYPE_NULL]))   # cmp rcx,TYPE_NULL
    em.jcc_rel32(0x84, "ty_false")                  # je false
    em.emit(b"\x48\x83\xF9" + bytes([TYPE_STR]))    # cmp rcx,TYPE_STR
    em.jcc_rel32(0x84, "ty_len")                    # je len
    em.emit(b"\x48\x83\xF9" + bytes([TYPE_LIST]))   # cmp rcx,TYPE_LIST
    em.jcc_rel32(0x84, "ty_len")                    # je len
    em.emit(b"\x48\x83\xF9" + bytes([TYPE_DICT]))   # cmp rcx,TYPE_DICT
    em.jcc_rel32(0x84, "ty_len")                    # je len
    em.emit(b"\x48\x83\xF9" + bytes([TYPE_FLOAT]))  # cmp rcx,TYPE_FLOAT
    em.jcc_rel32(0x84, "ty_float")                  # je float
    em.emit(b"\x48\x85\xC0")                        # test rax,rax（未知→真）
    em.emit(b"\xC3")                                # ret
    em.label_here("ty_float")
    em.movsd_load(0, 0, 16)                         # movsd xmm0,[rax+16]
    em.emit(b"\x66\x0F\xEF\xC9")                    # pxor xmm1,xmm1
    em.ucomisd(0, 1)                                # 与 0.0 比较
    em.jcc_rel32(0x8A, "ty_true")                   # jp：NaN → 真
    em.emit(b"\xC3")                                # ret（ZF=1 ⟺ 0.0 → 假）
    em.label_here("ty_true")
    em.emit(b"\x48\x85\xC0")                        # test rax,rax（ZF=0）
    em.emit(b"\xC3")
    em.label_here("ty_bool")
    em.lea_rip(2, "bool_false")                     # lea rdx,[bool_false]
    em.emit(b"\x48\x39\xD0")                        # cmp rax,rdx
    em.emit(b"\xC3")                                # ret
    em.label_here("ty_false")
    em.emit(b"\x48\x39\xC9")                        # cmp rcx,rcx（ZF=1）
    em.emit(b"\xC3")                                # ret
    em.label_here("ty_len")
    em.emit(b"\x48\x8B\x48\x08")                    # mov rcx,[rax+8]
    em.emit(b"\x48\x85\xC9")                        # test rcx,rcx
    em.emit(b"\xC3")                                # ret

    # ---- print_raw（写 STR 对象字节，无 CRLF）——经输出汇 ----
    em.label_here("print_raw")
    em.emit(b"\x48\x8D\x50\x10")                    # lea rdx,[rax+16]（payload）
    em.emit(b"\x4C\x8B\x40\x08")                    # mov r8,[rax+8]（len）
    em.jcc_rel32(None, "write_span")                # tail-call 输出汇

    # ---- print_str（写字节 + CRLF）----
    em.label_here("print_str")
    em.emit(b"\x55")                                # push rbp
    em.emit(b"\x48\x89\xE5")                        # mov rbp,rsp
    em.emit(b"\x48\x83\xEC\x40")                    # sub rsp,0x40
    em.emit(b"\x48\x8B\x70\x08")                    # mov rsi,[rax+8]  len
    em.emit(b"\x48\x8D\x50\x10")                    # lea rdx,[rax+16] buf
    em.emit(b"\x52")                                # push rdx
    em.emit(b"\x56")                                # push rsi
    em.emit(b"\xB9\xF5\xFF\xFF\xFF")                # mov ecx,-11
    em.call_rip_indirect("api_GetStdHandle")
    em.emit(b"\x48\x89\xC1")                        # mov rcx,rax
    em.emit(b"\x5E")                                # pop rsi
    em.emit(b"\x5A")                                # pop rdx
    em.emit(b"\x49\x89\xF0")                        # mov r8,rsi
    em.lea_rip(9, "written")                        # lea r9,[written]
    em.emit(b"\x48\xC7\x44\x24\x20\x00\x00\x00\x00")  # mov qword[rsp+0x20],0
    em.call_rip_indirect("api_WriteFile")
    em.emit(b"\xB9\xF5\xFF\xFF\xFF")                # mov ecx,-11
    em.call_rip_indirect("api_GetStdHandle")
    em.emit(b"\x48\x89\xC1")                        # mov rcx,rax
    em.lea_rip(2, "crlf")                           # lea rdx,[crlf]
    em.emit(b"\x41\xB8\x02\x00\x00\x00")            # mov r8d,2
    em.lea_rip(9, "written")                        # lea r9,[written]
    em.emit(b"\x48\xC7\x44\x24\x20\x00\x00\x00\x00")  # mov qword[rsp+0x20],0
    em.call_rip_indirect("api_WriteFile")
    _emit_epilogue(em)

    # ---- print_value ----
    em.label_here("print_value")
    em.emit(b"\x48\x89\xC1")                        # mov rcx,rax
    em.lea_rip(2, "heap_base")                      # lea rdx,[heap_base]
    em.emit(b"\x48\x29\xD1")                        # sub rcx,rdx
    em.emit(b"\x48\x81\xF9" + struct.pack("<I", HEAP_SIZE))  # cmp rcx,HEAP_SIZE
    em.jcc_rel32(0x82, "pv_ptr")                    # jb ptr
    em.call_rel32("print_int")
    em.emit(b"\xC3")                                # ret
    em.label_here("pv_ptr")
    em.emit(b"\x48\x8B\x08")                        # mov rcx,[rax]
    em.emit(b"\x48\x83\xF9" + bytes([TYPE_STR]))    # cmp rcx,TYPE_STR
    em.jcc_rel32(0x84, "pv_str")                    # je str
    em.emit(b"\x48\x83\xF9" + bytes([TYPE_BOOL]))   # cmp rcx,TYPE_BOOL
    em.jcc_rel32(0x84, "pv_str")                    # je str（True/False 载荷）
    em.emit(b"\x48\x83\xF9" + bytes([TYPE_NULL]))   # cmp rcx,TYPE_NULL
    em.jcc_rel32(0x84, "pv_str")                    # je str（None 载荷）
    em.emit(b"\x48\x83\xF9" + bytes([TYPE_LIST]))   # cmp rcx,TYPE_LIST
    em.jcc_rel32(0x84, "pv_list")                   # je list
    em.emit(b"\x48\x83\xF9" + bytes([TYPE_DICT]))   # cmp rcx,TYPE_DICT
    em.jcc_rel32(0x84, "pv_dict")                   # je dict
    em.emit(b"\x48\x83\xF9" + bytes([TYPE_FLOAT]))  # cmp rcx,TYPE_FLOAT
    em.jcc_rel32(0x84, "pv_float")                  # je float
    em.emit(b"\xC3")                                # ret（其他类型待实现）
    em.label_here("pv_float")
    em.call_rel32("str_float")
    em.call_rel32("print_raw")
    em.emit(b"\xC3")
    em.label_here("pv_str")
    em.call_rel32("print_raw")
    em.emit(b"\xC3")                                # ret
    em.label_here("pv_list")
    em.call_rel32("print_list")
    em.emit(b"\xC3")                                # ret
    em.label_here("pv_dict")
    em.call_rel32("print_dict")
    em.emit(b"\xC3")                                # ret

    # ---- print_nl（仅写 CRLF）----
    em.label_here("print_nl")
    em.emit(b"\x55")                                # push rbp
    em.emit(b"\x48\x89\xE5")                        # mov rbp,rsp
    em.emit(b"\x48\x83\xEC\x40")                    # sub rsp,0x40
    em.emit(b"\xB9\xF5\xFF\xFF\xFF")                # mov ecx,-11
    em.call_rip_indirect("api_GetStdHandle")
    em.emit(b"\x48\x89\xC1")                        # mov rcx,rax
    em.lea_rip(2, "crlf")                           # lea rdx,[crlf]
    em.emit(b"\x41\xB8\x02\x00\x00\x00")            # mov r8d,2
    em.lea_rip(9, "written")                        # lea r9,[written]
    em.emit(b"\x48\xC7\x44\x24\x20\x00\x00\x00\x00")  # mov qword[rsp+0x20],0
    em.call_rip_indirect("api_WriteFile")
    _emit_epilogue(em)

    # ---- print_list（[e1, e2, ...] + CRLF）----
    em.label_here("print_list")
    em.emit(b"\x55")                                # push rbp
    em.emit(b"\x48\x89\xE5")                        # mov rbp,rsp
    em.emit(b"\x48\x83\xEC\x40")                    # sub rsp,0x40
    em.emit(b"\x48\x89\x44\x24\x28")                # mov [rsp+0x28],rax
    em.lea_rip(0, "rb_lb")                          # lea rax,[rb_lb]
    em.call_rel32("print_raw")
    em.emit(b"\x48\xC7\x44\x24\x30\x00\x00\x00\x00")  # mov qword[rsp+0x30],0
    em.label_here("pl_loop")
    em.emit(b"\x48\x8B\x54\x24\x28")                # mov rdx,[rsp+0x28]
    em.emit(b"\x48\x8B\x4C\x24\x30")                # mov rcx,[rsp+0x30]
    em.emit(b"\x48\x3B\x4A\x08")                    # cmp rcx,[rdx+8]
    em.jcc_rel32(0x8D, "pl_done")                   # jge done
    em.emit(b"\x48\x85\xC9")                        # test rcx,rcx
    em.jcc_rel32(0x84, "pl_nosep")                  # jz nosep
    em.lea_rip(0, "rb_sep")                         # lea rax,[rb_sep]
    em.call_rel32("print_raw")
    em.label_here("pl_nosep")
    em.emit(b"\x48\x8B\x54\x24\x28")                # mov rdx,[rsp+0x28]
    em.emit(b"\x48\x8B\x4C\x24\x30")                # mov rcx,[rsp+0x30]
    em.emit(b"\x48\x8B\x44\xCA\x10")                # mov rax,[rdx+rcx*8+16]
    em.call_rel32("print_repr")
    em.emit(b"\x48\xFF\x44\x24\x30")                # inc qword [rsp+0x30]
    em.jcc_rel32(None, "pl_loop")                   # jmp loop
    em.label_here("pl_done")
    em.lea_rip(0, "rb_rb")                          # lea rax,[rb_rb]
    em.call_rel32("print_raw")
    _emit_epilogue(em)

    # ---- val_eq：对象内容相等（作为字典键比较）----
    # val_eq(rax=l, rcx=r) → rax=1/0。整数直接比较；指针对象比 type+len+bytes。
    em.label_here("val_eq")
    em.emit(b"\x49\x89\xC0")                        # mov r8,rax
    em.lea_rip(9, "heap_base")                      # lea r9,[heap_base]
    em.emit(b"\x4D\x29\xC8")                        # sub r8,r9
    em.emit(b"\x49\x81\xF8" + struct.pack("<I", HEAP_SIZE))  # cmp r8,HEAP_SIZE
    em.jcc_rel32(0x82, "ve_lptr")                   # jb：l 为指针
    em.emit(b"\x49\x89\xC8")                        # mov r8,rcx
    em.lea_rip(9, "heap_base")                      # lea r9,[heap_base]
    em.emit(b"\x4D\x29\xC8")                        # sub r8,r9
    em.emit(b"\x49\x81\xF8" + struct.pack("<I", HEAP_SIZE))  # cmp r8,HEAP_SIZE
    em.jcc_rel32(0x83, "ve_intcmp")                 # jae：r 也非指针 → 整数比较
    em.emit(b"\x31\xC0")                            # xor eax,eax（l 非指针 r 指针）
    em.emit(b"\xC3")                                # ret
    em.label_here("ve_lptr")
    em.emit(b"\x49\x89\xC8")                        # mov r8,rcx
    em.lea_rip(9, "heap_base")                      # lea r9,[heap_base]
    em.emit(b"\x4D\x29\xC8")                        # sub r8,r9
    em.emit(b"\x49\x81\xF8" + struct.pack("<I", HEAP_SIZE))  # cmp r8,HEAP_SIZE
    em.jcc_rel32(0x83, "ve_false")                  # jae：r 非指针 → 不等
    em.emit(b"\x4C\x8B\x00")                        # mov r8,[rax]（l 类型）
    em.emit(b"\x4C\x3B\x01")                        # cmp r8,[rcx]（r 类型）
    em.jcc_rel32(0x85, "ve_false")                  # jne
    em.emit(b"\x4C\x8B\x40\x08")                    # mov r8,[rax+8]（l 长度）
    em.emit(b"\x4C\x3B\x41\x08")                    # cmp r8,[rcx+8]（r 长度）
    em.jcc_rel32(0x85, "ve_false")                  # jne
    em.emit(b"\x48\x8D\x70\x10")                    # lea rsi,[rax+16]
    em.emit(b"\x48\x8D\x79\x10")                    # lea rdi,[rcx+16]
    em.emit(b"\x4C\x89\xC1")                        # mov rcx,r8（字节数）
    em.emit(b"\xF3\xA6")                            # rep cmpsb
    em.jcc_rel32(0x85, "ve_false")                  # jne
    em.emit(b"\xB8\x01\x00\x00\x00")                # mov eax,1
    em.emit(b"\xC3")                                # ret
    em.label_here("ve_false")
    em.emit(b"\x31\xC0")                            # xor eax,eax
    em.emit(b"\xC3")                                # ret
    em.label_here("ve_intcmp")
    em.emit(b"\x48\x39\xC8")                        # cmp rax,rcx
    em.emit(b"\x0F\x94\xC0")                        # sete al
    em.emit(b"\x0F\xB6\xC0")                        # movzx eax,al
    em.emit(b"\xC3")                                # ret

    # ---- dict_get：字典键查找（线性扫描）----
    # dict_get(rax=dict, rcx=key) → rax=value；缺失 → null_obj。
    em.label_here("dict_get")
    em.emit(b"\x41\x55")                            # push r13
    em.emit(b"\x41\x56")                            # push r14
    em.emit(b"\x41\x57")                            # push r15
    em.emit(b"\x4C\x8B\x68\x08")                    # mov r13,[rax+8]（count）
    em.emit(b"\x4C\x8D\x70\x10")                    # lea r14,[rax+16]（pairs）
    em.emit(b"\x49\x89\xCF")                        # mov r15,rcx（key）
    em.label_here("dg_loop")
    em.emit(b"\x4D\x85\xED")                        # test r13,r13
    em.jcc_rel32(0x84, "dg_miss")                   # jz miss
    em.emit(b"\x49\x8B\x06")                        # mov rax,[r14]（键）
    em.emit(b"\x49\x8B\xCF")                        # mov rcx,r15
    em.call_rel32("val_eq")
    em.emit(b"\x48\x85\xC0")                        # test rax,rax
    em.jcc_rel32(0x85, "dg_found")                  # jnz found
    em.emit(b"\x49\x83\xC6\x10")                    # add r14,16
    em.emit(b"\x49\xFF\xCD")                        # dec r13
    em.jcc_rel32(None, "dg_loop")                   # jmp loop
    em.label_here("dg_miss")
    em.lea_rip(0, "null_obj")                       # lea rax,[null_obj]
    em.jcc_rel32(None, "dg_done")
    em.label_here("dg_found")
    em.emit(b"\x49\x8B\x46\x08")                    # mov rax,[r14+8]（值）
    em.label_here("dg_done")
    em.emit(b"\x41\x5F")                            # pop r15
    em.emit(b"\x41\x5E")                            # pop r14
    em.emit(b"\x41\x5D")                            # pop r13
    em.emit(b"\xC3")                                # ret

    # ---- print_repr：Python repr（字符串加引号并转义，其余同 print_value）----
    em.label_here("print_repr")
    em.emit(b"\x55")                                # push rbp
    em.emit(b"\x48\x89\xE5")                        # mov rbp,rsp
    em.emit(b"\x48\x83\xEC\x20")                    # sub rsp,0x20
    em.emit(b"\x48\x89\x44\x24\x18")                # mov [rsp+0x18],rax
    em.emit(b"\x48\x89\xC1")                        # mov rcx,rax
    em.lea_rip(2, "heap_base")                      # lea rdx,[heap_base]
    em.emit(b"\x48\x29\xD1")                        # sub rcx,rdx
    em.emit(b"\x48\x81\xF9" + struct.pack("<I", HEAP_SIZE))  # cmp rcx,HEAP_SIZE
    em.jcc_rel32(0x83, "pr_v")                      # jae：非指针 → print_value
    em.emit(b"\x48\x8B\x08")                        # mov rcx,[rax]
    em.emit(b"\x48\x83\xF9" + bytes([TYPE_STR]))    # cmp rcx,TYPE_STR
    em.jcc_rel32(0x85, "pr_v")                      # jne：非字符串
    em.emit(b"\x48\x8B\x44\x24\x18")                # mov rax,[rsp+0x18]（字符串）
    em.call_rel32("str_repr_body")                  # 打印 '…'（CPython 转义）
    em.jcc_rel32(None, "pr_done")
    em.label_here("pr_v")
    em.emit(b"\x48\x8B\x44\x24\x18")                # mov rax,[rsp+0x18]
    em.call_rel32("print_value")
    em.label_here("pr_done")
    _emit_epilogue(em)

    # ---- print_dict：Python repr（{k: v, ...}，键值均 repr）----
    em.label_here("print_dict")
    em.emit(b"\x55")                                # push rbp
    em.emit(b"\x48\x89\xE5")                        # mov rbp,rsp
    em.emit(b"\x48\x83\xEC\x40")                    # sub rsp,0x40
    em.emit(b"\x48\x89\x44\x24\x28")                # mov [rsp+0x28],rax
    em.emit(b"\x48\xC7\x44\x24\x30\x00\x00\x00\x00")  # mov qword[rsp+0x30],0
    em.lea_rip(0, "dk_lb")                          # lea rax,[dk_lb]
    em.call_rel32("print_raw")
    em.emit(b"\x48\x8B\x44\x24\x28")                # mov rax,[rsp+0x28]
    em.emit(b"\x48\x8B\x40\x08")                    # mov rax,[rax+8]（count）
    em.emit(b"\x48\xFF\xC8")                        # dec rax → i=count-1
    em.emit(b"\x48\x89\x44\x24\x30")                # mov [rsp+0x30],rax
    em.label_here("pd_loop")
    em.emit(b"\x48\x8B\x54\x24\x28")                # mov rdx,[rsp+0x28]
    em.emit(b"\x48\x8B\x4C\x24\x30")                # mov rcx,[rsp+0x30]
    em.emit(b"\x48\x85\xC9")                        # test rcx,rcx
    em.jcc_rel32(0x88, "pd_done")                   # js done（i<0）
    em.emit(b"\x48\x8B\x42\x08")                    # mov rax,[rdx+8]
    em.emit(b"\x48\xFF\xC8")                        # dec rax（n-1）
    em.emit(b"\x48\x39\xC1")                        # cmp rcx,rax
    em.jcc_rel32(0x84, "pd_nosep")                  # je nosep（首元素无分隔）
    em.lea_rip(0, "rb_sep")                         # lea rax,[rb_sep]
    em.call_rel32("print_raw")
    em.label_here("pd_nosep")
    em.emit(b"\x48\x8B\x54\x24\x28")                # mov rdx,[rsp+0x28]
    em.emit(b"\x48\x8B\x4C\x24\x30")                # mov rcx,[rsp+0x30]
    em.emit(b"\x49\x89\xCA")                        # mov r10,rcx
    em.emit(b"\x49\xC1\xE2\x04")                    # shl r10,4（i*16）
    em.emit(b"\x49\x01\xD2")                        # add r10,rdx（obj+i*16）
    em.emit(b"\x49\x8B\x42\x10")                    # mov rax,[r10+16]（键）
    em.call_rel32("print_repr")
    em.lea_rip(0, "dk_col")                         # lea rax,[dk_col]
    em.call_rel32("print_raw")
    em.emit(b"\x48\x8B\x54\x24\x28")                # mov rdx,[rsp+0x28]
    em.emit(b"\x48\x8B\x4C\x24\x30")                # mov rcx,[rsp+0x30]
    em.emit(b"\x49\x89\xCA")                        # mov r10,rcx
    em.emit(b"\x49\xC1\xE2\x04")                    # shl r10,4
    em.emit(b"\x49\x01\xD2")                        # add r10,rdx
    em.emit(b"\x49\x8B\x42\x18")                    # mov rax,[r10+24]（值）
    em.call_rel32("print_repr")
    em.emit(b"\x48\xFF\x4C\x24\x30")                # dec qword [rsp+0x30]
    em.jcc_rel32(None, "pd_loop")                   # jmp loop
    em.label_here("pd_done")
    em.lea_rip(0, "dk_rb")                          # lea rax,[dk_rb]
    em.call_rel32("print_raw")
    _emit_epilogue(em)

    # ---- write_span(rdx=ptr, r8=len)：经输出汇写任意字节（不追加 CRLF）----
    # out_mode: 0=stdout（默认）、1=仅计数（str 预演）、2=写入 [out_buf_ptr]（str 填充）。
    # 保留 r10/r11（str_repr_body 借其暂存转义字节，跨本调用的 CRT 调用须存活）。
    em.label_here("write_span")
    em.load_rip_to(0, "out_mode")
    em.test_rr(0, 0)
    em.jcc_rel32(0x85, "ws_redirect")               # jnz：非 stdout
    em.emit(b"\x55")                                # push rbp
    em.emit(b"\x48\x89\xE5")                        # mov rbp,rsp
    em.emit(b"\x41\x52")                            # push r10
    em.emit(b"\x41\x53")                            # push r11
    em.emit(b"\x48\x83\xEC\x40")                    # sub rsp,0x40
    em.emit(b"\x48\x89\x54\x24\x28")                # mov [rsp+0x28],rdx
    em.emit(b"\x4C\x89\x44\x24\x30")                # mov [rsp+0x30],r8
    em.emit(b"\xB9\xF5\xFF\xFF\xFF")                # mov ecx,-11（STD_OUTPUT_HANDLE）
    em.call_rip_indirect("api_GetStdHandle")
    em.emit(b"\x48\x89\xC1")                        # mov rcx,rax
    em.emit(b"\x48\x8B\x54\x24\x28")                # mov rdx,[rsp+0x28]
    em.emit(b"\x4C\x8B\x44\x24\x30")                # mov r8,[rsp+0x30]
    em.lea_rip(9, "written")                        # lea r9,[written]
    em.emit(b"\x48\xC7\x44\x24\x20\x00\x00\x00\x00")  # mov qword[rsp+0x20],0
    em.call_rip_indirect("api_WriteFile")
    em.emit(b"\x48\x83\xC4\x40")                    # add rsp,0x40
    em.emit(b"\x41\x5B")                            # pop r11
    em.emit(b"\x41\x5A")                            # pop r10
    em.emit(b"\x5D")                                # pop rbp
    em.emit(b"\xC3")                                # ret
    em.label_here("ws_redirect")
    em.cmp_ri(0, 1)
    em.jcc_rel32(0x85, "ws_buf")                    # jne：模式 2
    em.load_rip_to(0, "out_count")                  # rax=已输出字节数
    em.add_rr(0, 8)                                 # add rax,r8
    em.store_rip_from("out_count", 0)
    em.emit(b"\xC3")                                # ret
    em.label_here("ws_buf")
    em.emit(b"\x55\x48\x89\xE5")                    # push rbp; mov rbp,rsp
    em.emit(b"\x57")                                # push rdi
    em.emit(b"\x56")                                # push rsi
    em.load_rip_to(0, "out_buf_ptr")                # rax=缓冲游标
    em.mov_rr(7, 0)                                 # mov rdi,rax
    em.mov_rr(6, 2)                                 # mov rsi,rdx
    em.mov_rr(1, 8)                                 # mov rcx,r8
    em.emit(b"\xF3\xA4")                            # rep movsb
    em.store_rip_from("out_buf_ptr", 7)             # [out_buf_ptr]=rdi（推进）
    em.emit(b"\x5E")                                # pop rsi
    em.emit(b"\x5F")                                # pop rdi
    em.emit(b"\x5D")                                # pop rbp
    em.emit(b"\xC3")                                # ret

    # ---- str_repr_body(rax=STR 对象)：按 CPython repr 规则打印 '…'（无换行）----
    # 引号选择：串内出现 ' 且不含 " → 用 "，否则用 '。转义：引号/反斜杠前加 \；
    # \n \r \t → \\n \\r \\t；其余 <0x20 或 ==0x7F 字节 → \xNN（小写十六进制）；
    # U+0080..U+00A0（UTF-8 为 C2 80..C2 A0）→ \xNN，同 CPython isprintable 规则；
    # 其余 ≥0x80 字节原样透传（覆盖 UTF-8 多字节/CJK/emoji）。普通字节按 run 批量写出。
    em.label_here("str_repr_body")
    em.emit(b"\x55")                                # push rbp
    em.emit(b"\x48\x89\xE5")                        # mov rbp,rsp
    em.emit(b"\x53\x41\x54\x41\x55\x41\x56\x41\x57")  # push rbx,r12,r13,r14,r15
    em.emit(b"\x48\x83\xEC\x38")                    # sub rsp,0x38（scratch+shadow，对齐）
    em.lea_mem(3, 0, 16)                            # lea rbx,[rax+16]（buf）
    em.mov_rd_mem(12, 0, 8)                         # mov r12,[rax+8]（len）
    em.add_rr(12, 3)                                # add r12,rbx（end）
    em.mov_rr(11, 3)                                # mov r11,rbx
    em.xor_rr32(14, 14)                             # xor r14d,r14d（bits：1=有', 2=有"）
    em.label_here("srb_scan")
    em.cmp_rr(11, 12)                               # cmp r11,r12
    em.jcc_rel32(0x83, "srb_scandone")              # jae done
    em.movzx_r_m8(0, 11, 0)                         # movzx eax,byte [r11]
    em.emit(b"\x3D\x27\x00\x00\x00")                # cmp eax,0x27（'）
    em.jcc_rel32(0x85, "srb_ns")                    # jne
    em.emit(b"\x41\x83\xCE\x01")                    # or r14d,1
    em.label_here("srb_ns")
    em.emit(b"\x3D\x22\x00\x00\x00")                # cmp eax,0x22（"）
    em.jcc_rel32(0x85, "srb_nd")                    # jne
    em.emit(b"\x41\x83\xCE\x02")                    # or r14d,2
    em.label_here("srb_nd")
    em.inc_r(11)                                    # inc r11
    em.jcc_rel32(None, "srb_scan")
    em.label_here("srb_scandone")
    em.emit(b"\xB0\x27")                            # mov al,0x27
    em.emit(b"\x41\x83\xFE\x01")                    # cmp r14d,1
    em.jcc_rel32(0x85, "srb_qdone")                 # jne：保留 '
    em.emit(b"\xB0\x22")                            # mov al,0x22
    em.label_here("srb_qdone")
    em.emit(b"\x41\x88\xC6")                        # mov r14b,al（引号字符）
    em.mov_m8_r(4, 16, 14)                          # mov [rsp+16],r14b
    em.lea_mem(2, 4, 16)                            # lea rdx,[rsp+16]
    em.mov_r_imm32(8, 1)                            # mov r8d,1
    em.call_rel32("write_span")                     # 打印开引号
    em.mov_rr(15, 3)                                # mov r15,rbx
    em.mov_rr(13, 3)                                # mov r13,rbx（run_start）
    em.label_here("srb_loop")
    em.cmp_rr(15, 12)                               # cmp r15,r12
    em.jcc_rel32(0x83, "srb_final")                 # jae final
    em.movzx_r_m8(0, 15, 0)                         # movzx eax,byte [r15]
    em.emit(b"\x3C\x5C")                            # cmp al,0x5C
    em.jcc_rel32(0x84, "srb_esc_bs")                # je 反斜杠
    em.emit(b"\x44\x38\xF0")                        # cmp al,r14b
    em.jcc_rel32(0x84, "srb_esc_q")                 # je 引号
    em.emit(b"\x3C\x0A")                            # cmp al,0x0A
    em.jcc_rel32(0x84, "srb_esc_n")                 # je \n
    em.emit(b"\x3C\x0D")                            # cmp al,0x0D
    em.jcc_rel32(0x84, "srb_esc_r")                 # je \r
    em.emit(b"\x3C\x09")                            # cmp al,0x09
    em.jcc_rel32(0x84, "srb_esc_t")                 # je \t
    em.emit(b"\x3C\x20")                            # cmp al,0x20
    em.jcc_rel32(0x82, "srb_esc_x")                 # jb \xNN
    em.emit(b"\x3C\x7F")                            # cmp al,0x7F
    em.jcc_rel32(0x84, "srb_esc_x")                 # je \xNN
    # U+0080..U+00A0（UTF-8 恒为 C2 80..C2 A0）：CPython 的 str.isprintable()
    # 对 Unicode 类别 Zs（U+00A0 NBSP）与 Cc 一律为 False，故 repr 转义为
    # \xNN；而「≥0x80 原样透传」会吐出裸 0x80..0xA0 字节（非法 UTF-8 输出）。
    # U+00A1（¡，Po）起可打印，0xC3..0xDF 一律原样透传。
    em.emit(b"\x3C\xC2")                            # cmp al,0xC2
    em.jcc_rel32(0x84, "srb_maybe_c1")               # je 可能是 C1 控制码
    em.label_here("srb_plain")
    em.inc_r(15)                                    # 普通字节：扩展当前 run
    em.jcc_rel32(None, "srb_loop")
    em.label_here("srb_maybe_c1")
    em.lea_mem(1, 15, 1)                         # lea rcx,[r15+1]
    em.cmp_rr(1, 12)                                # cmp rcx,r12
    em.jcc_rel32(0x83, "srb_plain")                 # jae：无后继字节 → 透传
    em.emit(b"\x41\x0F\xB6\x4C\x27\x01")            # movzx ecx,byte [r15+1]（ModRM rm=100→SIB；
                                                 #   SIB=0x27：index=100 表示「无索引」，
                                                 #   base=111+REX.B=r15。用 0x07 会让 index=000
                                                 #   真取 RAX 当索引，读到 [r15+rax+1] 垃圾）
    em.emit(b"\x80\xF9\x80")                        # cmp cl,0x80（rm=001 → rcx）
    em.jcc_rel32(0x82, "srb_plain")                 # jb <0x80 → 透传
    em.emit(b"\x80\xF9\xA1")                        # cmp cl,0xA1（U+00A1 ¡ 起可打印，原样透传）
    em.jcc_rel32(0x83, "srb_plain")                 # jae ≥0xA1 → 透传
    # 码点 = cl（C2 80..C2 A0 → U+0080..U+00A0），按 \xNN 小写十六进制输出
    em.emit(b"\x89\xC8")                            # mov eax,ecx
    em.emit(b"\xC1\xE9\x04")                        # shr ecx,4
    em.emit(b"\x83\xE1\x0F")                        # and ecx,15（高半字节）
    em.emit(b"\x89\xC2")                            # mov edx,eax
    em.emit(b"\x83\xE2\x0F")                        # and edx,15（低半字节）
    em.emit(b"\x80\xF9\x0A")                        # cmp cl,10
    em.jcc_rel32(0x82, "srb_c1h1d")                 # jb digit
    em.emit(b"\x80\xC1\x57")                        # add cl,0x57（'a'-10）
    em.jcc_rel32(None, "srb_c1h1e")
    em.label_here("srb_c1h1d")
    em.emit(b"\x80\xC1\x30")                        # add cl,0x30
    em.label_here("srb_c1h1e")
    em.emit(b"\x80\xFA\x0A")                        # cmp dl,10
    em.jcc_rel32(0x82, "srb_c1h2d")                 # jb digit
    em.emit(b"\x80\xC2\x57")                        # add dl,0x57
    em.jcc_rel32(None, "srb_c1h2e")
    em.label_here("srb_c1h2d")
    em.emit(b"\x80\xC2\x30")                        # add dl,0x30
    em.label_here("srb_c1h2e")
    em.mov_m8_ri(4, 16, 0x5C)                       # [rsp+16] = '\'
    em.mov_m8_ri(4, 17, 0x78)                       # [rsp+17] = 'x'
    em.mov_m8_r(4, 18, 1)                           # [rsp+18] = 高半字节（cl）
    em.mov_m8_r(4, 19, 2)                           # [rsp+19] = 低半字节（dl）
    em.cmp_rr(13, 15)                               # 先冲刷前置 run（同 srb_esc_x）
    em.jcc_rel32(0x83, "srb_c1nf")                  # jae：无前置 run
    em.mov_rr(2, 13)                                # mov rdx,r13
    em.mov_rr(8, 15)                                # mov r8,r15
    em.sub_rr(8, 13)                                # sub r8,r13
    em.call_rel32("write_span")                     # 打印前置 run
    em.label_here("srb_c1nf")
    em.lea_mem(2, 4, 16)                            # lea rdx,[rsp+16]
    em.mov_r_imm32(8, 4)                            # mov r8d,4
    em.call_rel32("write_span")                     # 打印 \xNN
    em.emit(b"\x49\x83\xC7\x02")                    # add r15,2（整对字节）
    em.mov_rr(13, 15)                               # r13 = r15
    em.jcc_rel32(None, "srb_loop")
    em.label_here("srb_esc_bs")
    em.mov_r_imm32(11, 0x5C5C)                      # r11d = "\\" 两字节
    em.mov_r_imm32(10, 2)                           # r10d = 2
    em.jcc_rel32(None, "srb_esc_common")
    em.label_here("srb_esc_q")
    em.emit(b"\x45\x0F\xB6\xDE")                    # movzx r11d,r14b
    em.emit(b"\x41\xC1\xE3\x08")                    # shl r11d,8
    em.emit(b"\x41\x83\xCB\x5C")                    # or r11d,0x5C
    em.mov_r_imm32(10, 2)
    em.jcc_rel32(None, "srb_esc_common")
    em.label_here("srb_esc_n")
    em.mov_r_imm32(11, 0x6E5C)                      # "\\n"
    em.mov_r_imm32(10, 2)
    em.jcc_rel32(None, "srb_esc_common")
    em.label_here("srb_esc_r")
    em.mov_r_imm32(11, 0x725C)                      # "\\r"
    em.mov_r_imm32(10, 2)
    em.jcc_rel32(None, "srb_esc_common")
    em.label_here("srb_esc_t")
    em.mov_r_imm32(11, 0x745C)                      # "\\t"
    em.mov_r_imm32(10, 2)
    em.jcc_rel32(None, "srb_esc_common")
    em.label_here("srb_esc_x")
    em.mov_rr(1, 0)                                 # mov ecx,eax
    em.shr_ri(1, 4)                                 # shr ecx,4
    em.and_ri(1, 15)                                # and ecx,15（高半字节）
    em.mov_rr(2, 0)                                 # mov edx,eax
    em.and_ri(2, 15)                                # and edx,15（低半字节）
    em.emit(b"\x80\xF9\x0A")                        # cmp cl,10
    em.jcc_rel32(0x82, "srb_hx1d")                  # jb digit
    em.emit(b"\x80\xC1\x57")                        # add cl,0x57（'a'-10）
    em.jcc_rel32(None, "srb_hx1e")
    em.label_here("srb_hx1d")
    em.emit(b"\x80\xC1\x30")                        # add cl,0x30
    em.label_here("srb_hx1e")
    em.emit(b"\x80\xFA\x0A")                        # cmp dl,10
    em.jcc_rel32(0x82, "srb_hx2d")                  # jb digit
    em.emit(b"\x80\xC2\x57")                        # add dl,0x57
    em.jcc_rel32(None, "srb_hx2e")
    em.label_here("srb_hx2d")
    em.emit(b"\x80\xC2\x30")                        # add dl,0x30
    em.label_here("srb_hx2e")
    em.mov_m8_ri(4, 16, 0x5C)                       # [rsp+16] = '\'
    em.mov_m8_ri(4, 17, 0x78)                       # [rsp+17] = 'x'
    em.mov_m8_r(4, 18, 1)                           # [rsp+18] = 高半字节 ASCII（cl）
    em.mov_m8_r(4, 19, 2)                           # [rsp+19] = 低半字节 ASCII（dl）
    # 必须先 flush 前置 run（同 srb_esc_common）。此前 \xNN 分支直接写 4 字节
    # 就跳过 run 冲刷，累积在 [r13,r15) 的普通字节被静默丢弃：
    # "a\x01b" 打成 "\x01b"（少首字符）、"ab\x01cd" 打成 "\x01cd"。
    # 既有 test_repr_hex_escapes_from_bytes 的字节串以控制字节开头，
    # 首个 \xNN 之前没有 run，故未暴露此缺陷。
    em.cmp_rr(13, 15)                               # cmp r13,r15
    em.jcc_rel32(0x83, "srb_xnf")                   # jae：无前置 run
    em.mov_rr(2, 13)                                # mov rdx,r13
    em.mov_rr(8, 15)                                # mov r8,r15
    em.sub_rr(8, 13)                                # sub r8,r13
    em.call_rel32("write_span")                     # 打印前置 run
    em.label_here("srb_xnf")
    em.lea_mem(2, 4, 16)                            # lea rdx,[rsp+16]
    em.mov_r_imm32(8, 4)                            # mov r8d,4
    em.call_rel32("write_span")                     # 打印 \xNN
    em.inc_r(15)                                    # inc r15
    em.mov_rr(13, 15)                               # r13 = r15
    em.jcc_rel32(None, "srb_loop")
    em.label_here("srb_esc_common")
    em.cmp_rr(13, 15)                               # cmp r13,r15
    em.jcc_rel32(0x83, "srb_esc_nf")                # jae：无前置 run
    em.mov_rr(2, 13)                                # mov rdx,r13
    em.mov_rr(8, 15)                                # mov r8,r15
    em.sub_rr(8, 13)                                # sub r8,r13
    em.call_rel32("write_span")                     # 打印前置 run
    em.label_here("srb_esc_nf")
    em.mov_mem_r(4, 16, 11)                         # mov [rsp+16],r11d（转义字节 2/4）
    em.lea_mem(2, 4, 16)                            # lea rdx,[rsp+16]
    em.mov_rr(8, 10)                                # mov r8,r10
    em.call_rel32("write_span")
    em.inc_r(15)                                    # inc r15
    em.mov_rr(13, 15)                               # r13 = r15
    em.jcc_rel32(None, "srb_loop")
    em.label_here("srb_final")
    em.cmp_rr(13, 12)                               # cmp r13,r12
    em.jcc_rel32(0x83, "srb_close")                 # jae
    em.mov_rr(2, 13)                                # mov rdx,r13
    em.mov_rr(8, 12)                                # mov r8,r12
    em.sub_rr(8, 13)                                # sub r8,r13
    em.call_rel32("write_span")                     # 打印尾 run
    em.label_here("srb_close")
    em.mov_m8_r(4, 16, 14)                          # mov [rsp+16],r14b
    em.lea_mem(2, 4, 16)                            # lea rdx,[rsp+16]
    em.mov_r_imm32(8, 1)                            # mov r8d,1
    em.call_rel32("write_span")                     # 打印闭引号
    em.emit(b"\x48\x83\xC4\x38")                    # add rsp,0x38
    em.emit(b"\x41\x5F\x41\x5E\x41\x5D\x41\x5C\x5B")  # pop r15,r14,r13,r12,rbx
    em.emit(b"\x5D")                                # pop rbp
    em.emit(b"\xC3")                                # ret


def _emit_gc_runtime(em: _Emitter):
    """砖块 18：保守式非移动 mark-sweep 垃圾回收运行时。

    触发：alloc 快路径发现 free list 非空或 bump 越界时跳 alloc_slow。
    根集：操作数栈 [vstack,r12)、CPU 栈 [rsp,stack_top)、全部 GP 寄存器
          （alloc_slow/gc 均 push 保存，故调用者活跃指针都在栈上）、raise_msg。
    对象尺寸由类型标签精确推导；对象体 [obj+8,obj+size) 逐字保守扫描。
    start_bits/mark_bits：1 bit/8 字节；mark_stack 为显式工作栈。
    sweep 只回收 [sweep_start,heap_ptr)（sweep_start 之下为永久内建闭包/静态对象）。

    空闲块管理：free_alloc 首次适配；块比请求大 ≥16 字节时切出剩余部分留在表中，
    否则整块给出（避免产生放不下自身表头 [size][next] 的碎片）。空闲表始终按
    地址升序排列。gc_sweep 线性扫描时把地址连续的死亡对象合并为单个空闲块，并借
    单调游标把新块与前/后相邻空闲块按地址合并——回收整片对象后只剩一个大块，可被
    后续任意大小的分配（配合切分）复用，显著降低外碎片。合并代价 O(既有块+run 数)。
    """

    def btf(op: int, reg: int):
        """bt/bts/btr qword [rip+LABEL], reg（RIP 相对 + 寄存器位偏移）。"""
        return bytes([0x48, 0x0F, op, 0x05 | ((reg & 7) << 3)])

    # ================= alloc_slow（冷路径）=================
    em.label_here("alloc_slow")
    em.emit(b"\x55")                                # push rbp
    em.emit(b"\x48\x89\xE5")                        # mov rbp,rsp
    em.emit(b"\x53\x51\x52\x56\x57")                # push rbx,rcx,rdx,rsi,rdi
    em.emit(b"\x41\x50\x41\x51\x41\x52\x41\x53")    # push r8,r9,r10,r11
    em.emit(b"\x41\x54\x41\x55\x41\x56\x41\x57")    # push r12,r13,r14,r15
    em.emit(b"\x48\x83\xEC\x20")                    # sub rsp,0x20
    em.emit(b"\x48\x89\x3C\x24")                    # mov [rsp],rdi（保存 size）
    em.call_rel32("free_alloc")                     # rax=空闲块 或 0
    em.emit(b"\x48\x85\xC0")                        # test rax,rax
    em.jcc_rel32(0x85, "as_done")                   # jnz done
    em.call_rel32("gc")                             # 回收
    em.emit(b"\x48\x8B\x3C\x24")                    # mov rdi,[rsp]
    em.call_rel32("free_alloc")
    em.emit(b"\x48\x85\xC0")                        # test rax,rax
    em.jcc_rel32(0x85, "as_done")                   # jnz done
    em.emit(b"\x48\x8B\x3C\x24")                    # mov rdi,[rsp]
    em.emit(b"\x48\x8B\x05")                        # mov rax,[rip+heap_ptr]
    em.rel32_to("heap_ptr")
    em.emit(b"\x48\x89\xC2")                        # mov rdx,rax
    em.emit(b"\x48\x01\xFA")                        # add rdx,rdi
    em.emit(b"\x48\x83\xC2\x07")                    # add rdx,7
    em.emit(b"\x48\x83\xE2\xF8")                    # and rdx,-8
    em.emit(b"\x48\x3B\x15")                        # cmp rdx,[rip+heap_limit]
    em.rel32_to("heap_limit")
    em.jcc_rel32(0x87, "as_oom")                    # ja（回收后仍越界 → 内存不足）
    em.emit(b"\x48\x89\x15")                        # mov [rip+heap_ptr],rdx
    em.rel32_to("heap_ptr")
    em.emit(b"\x48\x89\xC1")                        # mov rcx,rax
    em.lea_rip(2, "heap_base")                      # lea rdx,[heap_base]
    em.emit(b"\x48\x29\xD1")                        # sub rcx,rdx
    em.emit(b"\x48\xC1\xE9\x03")                    # shr rcx,3
    em.emit(btf(0xAB, 1))                           # bts qword [rip+start_bits],rcx
    em.rel32_to("start_bits")
    em.label_here("as_done")
    em.emit(b"\x48\x83\xC4\x20")                    # add rsp,0x20
    em.emit(b"\x41\x5F\x41\x5E\x41\x5D\x41\x5C")    # pop r15,r14,r13,r12
    em.emit(b"\x41\x5B\x41\x5A\x41\x59\x41\x58")    # pop r11,r10,r9,r8
    em.emit(b"\x5F\x5E\x5A\x59\x5B")                # pop rdi,rsi,rdx,rcx,rbx
    em.emit(b"\x5D")                                # pop rbp
    em.emit(b"\xC3")                                # ret
    # ---- 内存不足：GC 后仍无可用空间。写诊断到 stderr 并以退出码 1 终止，
    #      不再越过 heap_limit（旧行为会覆写 start_bits/mark_bits 造成静默损坏）。
    em.label_here("as_oom")
    em.emit(b"\x48\x83\xE4\xF0")                    # and rsp,-16（强制 16 字节对齐）
    em.emit(b"\x48\x83\xEC\x20")                    # sub rsp,0x20（影子空间）
    em.lea_rip(0, "oom_msg")                        # lea rax,[oom_msg]（STR 对象）
    em.call_rel32("print_uncaught")                 # 消息 + CRLF 写 stderr
    em.mov_r_imm32(1, 1)                            # mov ecx,1
    em.call_rip_indirect("api_ExitProcess")
    em.emit(b"\x0F\x0B")                            # ud2（不可达）

    # ================= free_alloc(rdi=size) → rax =================
    # 首次适配；块大于请求时切出剩余部分留在空闲表（剩余 < 16 则整块给出，避免
    # 生成无法容纳自身表头的碎片）。请求大小先向上对齐到 8。
    em.label_here("free_alloc")
    em.emit(b"\x48\x83\xC7\x07")                    # add rdi,7
    em.emit(b"\x48\x83\xE7\xF8")                    # and rdi,-8（请求大小对齐 8）
    em.emit(b"\x4C\x8B\x05")                        # mov r8,[rip+free_head]
    em.rel32_to("free_head")
    em.emit(b"\x45\x31\xC9")                        # xor r9d,r9d（prev=0）
    em.label_here("fa_loop")
    em.emit(b"\x4D\x85\xC0")                        # test r8,r8
    em.jcc_rel32(0x84, "fa_miss")                   # jz miss
    em.emit(b"\x49\x8B\x00")                        # mov rax,[r8]
    em.emit(b"\x48\x25\xF8\xFF\xFF\xFF")            # and rax,-8（块大小）
    em.emit(b"\x48\x39\xF8")                        # cmp rax,rdi
    em.jcc_rel32(0x82, "fa_next")                   # jb next
    em.emit(b"\x49\x8B\x48\x08")                    # mov rcx,[r8+8]（next）
    em.mov_rr(2, 0)                                 # mov rdx,rax
    em.sub_rr(2, 7)                                 # sub rdx,rdi（剩余）
    em.emit(b"\x48\x83\xFA\x10")                    # cmp rdx,16
    em.jcc_rel32(0x82, "fa_nosplit")                # jb nosplit
    # ---- 切分：剩余块置于 [r8+rdi] ----
    em.mov_rr(6, 8)                                 # mov rsi,r8
    em.add_rr(6, 7)                                 # add rsi,rdi
    em.mov_mem_r(6, 0, 2)                           # mov [rsi],rdx（剩余大小）
    em.mov_mem_r(6, 8, 1)                           # mov [rsi+8],rcx（继承 next）
    em.test_rr(9, 9)                                # test r9,r9
    em.jcc_rel32(0x84, "fa_head_split")             # jz head_split
    em.mov_mem_r(9, 8, 6)                           # mov [r9+8],rsi
    em.jcc_rel32(None, "fa_linked_split")           # jmp linked_split
    em.label_here("fa_head_split")
    em.store_rip_from("free_head", 6)               # mov [rip+free_head],rsi
    em.label_here("fa_linked_split")
    em.mov_rr(0, 8)                                 # mov rax,r8
    em.jcc_rel32(None, "fa_mark")                   # jmp mark
    # ---- 不切分：整块摘链 ----
    em.label_here("fa_nosplit")
    em.test_rr(9, 9)                                # test r9,r9
    em.jcc_rel32(0x84, "fa_head_whole")             # jz head_whole
    em.mov_mem_r(9, 8, 1)                           # mov [r9+8],rcx
    em.jcc_rel32(None, "fa_linked_whole")           # jmp linked_whole
    em.label_here("fa_head_whole")
    em.store_rip_from("free_head", 1)               # mov [rip+free_head],rcx
    em.label_here("fa_linked_whole")
    em.mov_rr(0, 8)                                 # mov rax,r8
    em.label_here("fa_mark")                        # rax=返回块地址
    em.mov_rr(1, 0)                                 # mov rcx,rax
    em.lea_rip(2, "heap_base")                      # lea rdx,[heap_base]
    em.sub_rr(1, 2)                                 # sub rcx,rdx
    em.shr_ri(1, 3)                                 # shr rcx,3
    em.emit(btf(0xAB, 1))                           # bts qword [rip+start_bits],rcx
    em.rel32_to("start_bits")
    em.emit(b"\xC3")                                # ret
    em.label_here("fa_next")
    em.mov_rr(9, 8)                                 # mov r9,r8
    em.mov_rd_mem(8, 8, 8)                          # mov r8,[r8+8]
    em.jcc_rel32(None, "fa_loop")                   # jmp loop
    em.label_here("fa_miss")
    em.emit(b"\x31\xC0")                            # xor eax,eax
    em.emit(b"\xC3")                                # ret

    # ================= gc =================
    em.label_here("gc")
    em.emit(b"\x55")                                # push rbp
    em.emit(b"\x48\x89\xE5")                        # mov rbp,rsp
    em.emit(b"\x53\x51\x52\x56\x57")                # push rbx,rcx,rdx,rsi,rdi
    em.emit(b"\x41\x50\x41\x51\x41\x52\x41\x53")    # push r8,r9,r10,r11
    em.emit(b"\x41\x54\x41\x55\x41\x56\x41\x57")    # push r12,r13,r14,r15
    em.emit(b"\x48\x83\xEC\x20")                    # sub rsp,0x20
    em.lea_rip(0, "mark_stack")                     # lea rax,[mark_stack]
    em.emit(b"\x48\x89\x05")                        # mov [rip+mark_top],rax
    em.rel32_to("mark_top")
    em.call_rel32("gc_clear_marks")
    em.lea_rip(7, "vstack")                         # lea rdi,[vstack]
    em.emit(b"\x4C\x89\xE6")                        # mov rsi,r12（操作数栈顶）
    em.call_rel32("gc_scan_range")
    em.emit(b"\x48\x89\xE7")                        # mov rdi,rsp
    em.emit(b"\x48\x8B\x35")                        # mov rsi,[rip+stack_top]
    em.rel32_to("stack_top")
    em.call_rel32("gc_scan_range")
    em.emit(b"\x48\x8B\x05")                        # mov rax,[rip+raise_msg]
    em.rel32_to("raise_msg")
    em.call_rel32("gc_mark_candidate")
    em.lea_rip(7, "cells_begin")                    # 全局变量单元 [cells_begin,cells_end)
    em.emit(b"\x48\x8B\x35")
    em.rel32_to("cells_end")
    em.call_rel32("gc_scan_range")
    em.lea_rip(7, "hstack")                         # 异常处理器栈 [hstack,hstack_ptr)
    em.emit(b"\x48\x8B\x35")
    em.rel32_to("hstack_ptr")
    em.call_rel32("gc_scan_range")
    em.call_rel32("gc_trace")
    em.call_rel32("gc_sweep")
    em.emit(b"\x48\x83\xC4\x20")                    # add rsp,0x20
    em.emit(b"\x41\x5F\x41\x5E\x41\x5D\x41\x5C")    # pop r15,r14,r13,r12
    em.emit(b"\x41\x5B\x41\x5A\x41\x59\x41\x58")    # pop r11,r10,r9,r8
    em.emit(b"\x5F\x5E\x5A\x59\x5B")                # pop rdi,rsi,rdx,rcx,rbx
    em.emit(b"\x5D")                                # pop rbp
    em.emit(b"\xC3")                                # ret

    # ============ gc_clear_marks：清空 [sweep_start,heap_ptr) 的 mark 位 ============
    em.label_here("gc_clear_marks")
    em.emit(b"\x48\x8B\x05")                        # mov rax,[rip+sweep_start]
    em.rel32_to("sweep_start")
    em.emit(b"\x48\x8B\x35")                        # mov rsi,[rip+heap_ptr]
    em.rel32_to("heap_ptr")
    em.lea_rip(8, "heap_base")
    em.lea_rip(9, "start_bits")
    em.lea_rip(10, "mark_bits")
    em.label_here("gcm_loop")
    em.emit(b"\x48\x39\xF0")                        # cmp rax,rsi
    em.jcc_rel32(0x83, "gcm_done")                  # jae done
    em.emit(b"\x48\x89\xC1")                        # mov rcx,rax
    em.emit(b"\x4C\x29\xC1")                        # sub rcx,r8
    em.emit(b"\x48\xC1\xE9\x03")                    # shr rcx,3
    em.emit(b"\x49\x0F\xA3\x09")                    # bt qword [r9],rcx
    em.jcc_rel32(0x83, "gcm_next")                  # jnc next（非起点）
    em.emit(b"\x49\x0F\xB3\x0A")                    # btr qword [r10],rcx
    em.label_here("gcm_next")
    em.emit(b"\x48\x83\xC0\x08")                    # add rax,8
    em.jcc_rel32(None, "gcm_loop")
    em.label_here("gcm_done")
    em.emit(b"\xC3")

    # ============ gc_scan_range(rdi=start, rsi=end) ============
    em.label_here("gc_scan_range")
    em.label_here("gsr_loop")
    em.emit(b"\x48\x39\xF7")                        # cmp rdi,rsi
    em.jcc_rel32(0x83, "gsr_done")                  # jae done
    em.emit(b"\x48\x8B\x07")                        # mov rax,[rdi]
    em.emit(b"\x48\x83\xC7\x08")                    # add rdi,8
    em.call_rel32("gc_mark_candidate")
    em.jcc_rel32(None, "gsr_loop")
    em.label_here("gsr_done")
    em.emit(b"\xC3")

    # ===== gc_mark_candidate(rax=v)：登记候选指针并入标记栈（幂等）=====
    # 仅破坏 rax/rcx/r8，保护 rdi/rsi/rdx/r9-r15。
    em.label_here("gc_mark_candidate")
    em.emit(b"\x48\x3B\x05")                        # cmp rax,[rip+sweep_start]
    em.rel32_to("sweep_start")
    em.jcc_rel32(0x82, "gmc_ret")                   # jb ret
    em.emit(b"\x48\x3B\x05")                        # cmp rax,[rip+heap_ptr]
    em.rel32_to("heap_ptr")
    em.jcc_rel32(0x83, "gmc_ret")                   # jae ret
    em.emit(b"\xA8\x07")                            # test al,7
    em.jcc_rel32(0x85, "gmc_ret")                   # jnz ret（未 8 对齐）
    em.emit(b"\x48\x89\xC1")                        # mov rcx,rax
    em.lea_rip(8, "heap_base")                      # lea r8,[heap_base]
    em.emit(b"\x4C\x29\xC1")                        # sub rcx,r8
    em.emit(b"\x48\xC1\xE9\x03")                    # shr rcx,3
    em.lea_rip(8, "start_bits")
    em.emit(b"\x49\x0F\xA3\x08")                    # bt qword [r8],rcx
    em.jcc_rel32(0x83, "gmc_ret")                   # jnc ret（非对象起点）
    em.lea_rip(8, "mark_bits")
    em.emit(b"\x49\x0F\xA3\x08")                    # bt qword [r8],rcx
    em.jcc_rel32(0x82, "gmc_ret")                   # jc ret（已标记）
    em.emit(b"\x49\x0F\xAB\x08")                    # bts qword [r8],rcx
    em.emit(b"\x48\x8B\x0D")                        # mov rcx,[rip+mark_top]
    em.rel32_to("mark_top")
    em.emit(b"\x48\x89\x01")                        # mov [rcx],rax
    em.emit(b"\x48\x83\xC1\x08")                    # add rcx,8
    em.emit(b"\x48\x89\x0D")                        # mov [rip+mark_top],rcx
    em.rel32_to("mark_top")
    em.label_here("gmc_ret")
    em.emit(b"\xC3")

    # ============ gc_trace：弹出标记栈逐对象扫描 ============
    em.label_here("gc_trace")
    em.label_here("gt_loop")
    em.emit(b"\x48\x8B\x0D")                        # mov rcx,[rip+mark_top]
    em.rel32_to("mark_top")
    em.lea_rip(8, "mark_stack")
    em.cmp_rr(1, 8)                                 # cmp rcx,r8
    em.jcc_rel32(0x86, "gt_done")                   # jbe done（空）
    em.emit(b"\x48\x83\xE9\x08")                    # sub rcx,8
    em.emit(b"\x48\x89\x0D")                        # mov [rip+mark_top],rcx
    em.rel32_to("mark_top")
    em.emit(b"\x48\x8B\x01")                        # mov rax,[rcx]
    em.call_rel32("gc_scan_object")
    em.jcc_rel32(None, "gt_loop")
    em.label_here("gt_done")
    em.emit(b"\xC3")

    # ============ gc_scan_object(rax=obj)：精确尺寸 + 体扫描 ============
    em.label_here("gc_scan_object")
    em.emit(b"\x48\x89\xC7")                        # mov rdi,rax
    em.call_rel32("gc_obj_size")                    # rax=size
    em.emit(b"\x48\x89\xFE")                        # mov rsi,rdi
    em.emit(b"\x48\x83\xC6\x08")                    # add rsi,8
    em.emit(b"\x48\x8D\x14\x07")                    # lea rdx,[rdi+rax]
    em.label_here("gso_loop")
    em.emit(b"\x48\x39\xD6")                        # cmp rsi,rdx
    em.jcc_rel32(0x83, "gso_done")                  # jae done
    em.emit(b"\x48\x8B\x06")                        # mov rax,[rsi]
    em.emit(b"\x48\x83\xC6\x08")                    # add rsi,8
    em.call_rel32("gc_mark_candidate")
    em.jcc_rel32(None, "gso_loop")
    em.label_here("gso_done")
    em.emit(b"\xC3")

    # ============ gc_obj_size(rdi=obj) → rax（按类型推导尺寸）============
    em.label_here("gc_obj_size")
    em.emit(b"\x48\x8B\x0F")                        # mov rcx,[rdi]
    em.emit(b"\x48\x83\xF9" + bytes([TYPE_STR]))
    em.jcc_rel32(0x84, "gos_str")
    em.emit(b"\x48\x83\xF9" + bytes([TYPE_LIST]))
    em.jcc_rel32(0x84, "gos_list")
    em.emit(b"\x48\x83\xF9" + bytes([TYPE_DICT]))
    em.jcc_rel32(0x84, "gos_dict")
    em.emit(b"\x48\x83\xF9" + bytes([TYPE_FLOAT]))
    em.jcc_rel32(0x84, "gos_float")
    em.emit(b"\x48\x83\xF9" + bytes([TYPE_ENV]))
    em.jcc_rel32(0x84, "gos_env")
    em.emit(b"\x48\x83\xF9" + bytes([TYPE_CLOSURE]))
    em.jcc_rel32(0x84, "gos_clos")
    em.emit(b"\x48\x83\xF9" + bytes([TYPE_PARTIAL]))
    em.jcc_rel32(0x84, "gos_part")
    em.emit(b"\xB8\x10\x00\x00\x00")                # mov eax,16（默认：BOX）
    em.emit(b"\xC3")
    em.label_here("gos_str")
    em.emit(b"\x48\x8B\x47\x08")                    # mov rax,[rdi+8]
    em.emit(b"\x48\x83\xC0\x10")                    # add rax,16
    em.jcc_rel32(None, "gos_align")
    em.label_here("gos_list")
    em.emit(b"\x48\x8B\x47\x08")                    # mov rax,[rdi+8]
    em.emit(b"\x48\xC1\xE0\x03")                    # shl rax,3
    em.emit(b"\x48\x83\xC0\x10")                    # add rax,16
    em.jcc_rel32(None, "gos_align")
    em.label_here("gos_dict")
    em.emit(b"\x48\x8B\x47\x08")                    # mov rax,[rdi+8]
    em.emit(b"\x48\xC1\xE0\x04")                    # shl rax,4
    em.emit(b"\x48\x83\xC0\x10")                    # add rax,16
    em.jcc_rel32(None, "gos_align")
    em.label_here("gos_float")
    em.emit(b"\xB8\x18\x00\x00\x00")                # mov eax,24
    em.emit(b"\xC3")
    em.label_here("gos_env")
    em.emit(b"\x48\x8B\x47\x10")                    # mov rax,[rdi+16]（ncap）
    em.emit(b"\x48\x83\xC0\x03")                    # add rax,3
    em.emit(b"\x48\xC1\xE0\x03")                    # shl rax,3
    em.emit(b"\xC3")
    em.label_here("gos_clos")
    em.emit(b"\xB8\x20\x00\x00\x00")                # mov eax,32
    em.emit(b"\xC3")
    em.label_here("gos_part")
    em.emit(b"\x48\x8B\x47\x10")                    # mov rax,[rdi+16]（n）
    em.emit(b"\x48\xC1\xE0\x03")                    # shl rax,3
    em.emit(b"\x48\x83\xC0\x18")                    # add rax,24
    em.emit(b"\xC3")
    em.label_here("gos_align")
    em.emit(b"\x48\x83\xC0\x07")                    # add rax,7
    em.emit(b"\x48\x83\xE0\xF8")                    # and rax,-8
    em.emit(b"\xC3")

    # ============ gc_sweep：回收 [sweep_start,heap_ptr) 中未标记对象 ============
    # 线性扫描，把地址连续的死亡对象合并为一个空闲块后挂入空闲表。空闲表保持
    # 地址升序；sweep 产出的 run 地址递增，故维护单调游标 r13=prev、r14=cur，插链
    # 时顺带与前后相邻空闲块做地址级合并（分配/回收两侧共同消除外碎片）。
    # r11=run_start(0=无)，rbx=run_end；均跨 gc_obj_size 调用保持；r13/r14=插入游标。
    em.label_here("gc_sweep")
    em.emit(b"\x53")                                # push rbx（run_end）
    em.emit(b"\x45\x31\xDB")                        # xor r11d,r11d（run_start=0）
    em.emit(b"\x45\x31\xED")                        # xor r13d,r13d（合并游标 prev=0）
    em.load_rip_to(14, "free_head")                 # mov r14,[rip+free_head]（游标 cur）
    em.emit(b"\x48\x8B\x3D")                        # mov rdi,[rip+sweep_start]
    em.rel32_to("sweep_start")
    em.emit(b"\x48\x8B\x35")                        # mov rsi,[rip+heap_ptr]
    em.rel32_to("heap_ptr")
    em.lea_rip(8, "heap_base")
    em.lea_rip(9, "start_bits")
    em.lea_rip(10, "mark_bits")
    em.label_here("gsw_loop")
    em.emit(b"\x48\x39\xF7")                        # cmp rdi,rsi
    em.jcc_rel32(0x83, "gsw_flush_end")             # jae flush_end
    em.emit(b"\x48\x89\xF8")                        # mov rax,rdi
    em.emit(b"\x4C\x29\xC0")                        # sub rax,r8
    em.emit(b"\x48\xC1\xE8\x03")                    # shr rax,3
    em.emit(b"\x49\x0F\xA3\x01")                    # bt qword [r9],rax
    em.jcc_rel32(0x83, "gsw_next")                  # jnc next（非起点）
    em.emit(b"\x49\x0F\xA3\x02")                    # bt qword [r10],rax
    em.jcc_rel32(0x82, "gsw_live")                  # jc live（存活）
    # ---- 死亡对象：清 start 位，并入/开启合并 run ----
    em.call_rel32("gc_obj_size")                    # rax=size（rdi 保护）
    em.emit(b"\x48\x89\xF9")                        # mov rcx,rdi
    em.emit(b"\x4C\x29\xC1")                        # sub rcx,r8
    em.emit(b"\x48\xC1\xE9\x03")                    # shr rcx,3
    em.emit(b"\x49\x0F\xB3\x09")                    # btr qword [r9],rcx（清 start）
    em.test_rr(11, 11)                              # test r11,r11
    em.jcc_rel32(0x84, "gsw_newrun")                # jz newrun
    em.emit(b"\x48\x39\xDF")                        # cmp rdi,rbx
    em.jcc_rel32(0x85, "gsw_flush_newrun")          # jne flush_newrun
    em.add_rr(3, 0)                                 # add rbx,rax（延续 run）
    em.jcc_rel32(None, "gsw_next")                  # jmp next
    em.label_here("gsw_flush_newrun")
    em.mov_rr(15, 0)                                # mov r15,rax（暂存对象大小）
    em.call_rel32("gsw_flush")                      # 吐出旧 run（破坏 rax/rcx/rdx）
    em.mov_rr(0, 15)                                # mov rax,r15（恢复对象大小）
    em.label_here("gsw_newrun")
    em.mov_rr(11, 7)                                # mov r11,rdi
    em.mov_rr(3, 7)                                 # mov rbx,rdi
    em.add_rr(3, 0)                                 # add rbx,rax
    em.jcc_rel32(None, "gsw_next")                  # jmp next
    # ---- 存活对象：若有悬挂 run 则先吐出 ----
    em.label_here("gsw_live")
    em.test_rr(11, 11)                              # test r11,r11
    em.jcc_rel32(0x84, "gsw_next")                  # jz next
    em.call_rel32("gsw_flush")
    em.emit(b"\x45\x31\xDB")                        # xor r11d,r11d
    em.label_here("gsw_next")
    em.emit(b"\x48\x83\xC7\x08")                    # add rdi,8
    em.jcc_rel32(None, "gsw_loop")                  # jmp loop
    em.label_here("gsw_flush_end")
    em.test_rr(11, 11)                              # test r11,r11
    em.jcc_rel32(0x84, "gsw_done")                  # jz done
    em.call_rel32("gsw_flush")
    em.label_here("gsw_done")
    em.emit(b"\x5B")                                # pop rbx
    em.emit(b"\xC3")                                # ret

    # ---- gsw_flush：把 [r11,rbx) 按地址升序插入空闲表并与相邻空闲块合并 ----
    # 破坏 rax/rcx/rdx，维护游标 r13(prev)/r14(cur)，保留 rbx/r11/r15。
    em.label_here("gsw_flush")
    em.mov_rr(2, 3)                                 # mov rdx,rbx
    em.sub_rr(2, 11)                                # sub rdx,r11（run 大小）
    # ---- 推进游标：while (r14 && r14 < r11) { r13=r14; r14=[r14+8]; } ----
    em.label_here("gswf_adv")
    em.test_rr(14, 14)                              # test r14,r14
    em.jcc_rel32(0x84, "gswf_adv_done")             # jz adv_done
    em.cmp_rr(14, 11)                               # cmp r14,r11
    em.jcc_rel32(0x83, "gswf_adv_done")             # jae adv_done（cur>=run）
    em.mov_rr(13, 14)                               # mov r13,r14（prev=cur）
    em.mov_rd_mem(14, 14, 8)                        # mov r14,[r14+8]（cur=cur.next）
    em.jcc_rel32(None, "gswf_adv")                  # jmp adv
    em.label_here("gswf_adv_done")
    # ---- 前向合并判定：r14!=0 且 rbx==r14 ----
    em.test_rr(14, 14)                              # test r14,r14
    em.jcc_rel32(0x84, "gswf_nofwd")                # jz nofwd
    em.cmp_rr(3, 14)                                # cmp rbx,r14
    em.jcc_rel32(0x85, "gswf_nofwd")                # jne nofwd
    # cur 紧邻 run 末尾：先把 cur 尺寸并入 rdx，暂存 cur.next 到 r14
    em.mov_rd_mem(0, 14, 0)                         # mov rax,[r14]（cur 大小）
    em.and_ri(0, -8)                                # and rax,-8
    em.add_rr(2, 0)                                 # add rdx,rax
    em.mov_rd_mem(0, 14, 8)                         # mov rax,[r14+8]（cur.next）
    em.mov_rr(14, 0)                                # mov r14,rax（游标前移）
    em.test_rr(13, 13)                              # test r13,r13
    em.jcc_rel32(0x84, "gswf_fwd_run")              # jz fwd_run（无 prev）
    # 有 prev：再判后向合并（prev_end == r11）
    em.mov_rd_mem(0, 13, 0)                         # mov rax,[r13]（prev 大小）
    em.and_ri(0, -8)                                # and rax,-8
    em.mov_rr(1, 13)                                # mov rcx,r13
    em.add_rr(1, 0)                                 # add rcx,rax（prev_end）
    em.cmp_rr(1, 11)                                # cmp rcx,r11
    em.jcc_rel32(0x85, "gswf_fwd_run")              # jne fwd_run
    # prev 同时吸收 run 与 cur（三方合并）
    em.add_rr(2, 0)                                 # add rdx,rax（+prev 大小）
    em.mov_mem_r(13, 0, 2)                          # mov [r13],rdx
    em.mov_mem_r(13, 8, 14)                         # mov [r13+8],r14（cur.next）
    em.emit(b"\xC3")                                # ret
    em.label_here("gswf_fwd_run")
    # 合并块落在 r11（run 起点）
    em.mov_mem_r(11, 0, 2)                          # mov [r11],rdx
    em.mov_mem_r(11, 8, 14)                         # mov [r11+8],r14
    em.test_rr(13, 13)                              # test r13,r13
    em.jcc_rel32(0x84, "gswf_fwd_head")             # jz fwd_head
    em.mov_mem_r(13, 8, 11)                         # mov [r13+8],r11
    em.jcc_rel32(None, "gswf_fwd_done")             # jmp fwd_done
    em.label_here("gswf_fwd_head")
    em.store_rip_from("free_head", 11)              # mov [rip+free_head],r11
    em.label_here("gswf_fwd_done")
    em.mov_rr(13, 11)                               # mov r13,r11（游标 prev）
    em.emit(b"\xC3")                                # ret
    # ---- 无前向合并 ----
    em.label_here("gswf_nofwd")
    em.test_rr(13, 13)                              # test r13,r13
    em.jcc_rel32(0x84, "gswf_insert")               # jz insert（无 prev）
    em.mov_rd_mem(0, 13, 0)                         # mov rax,[r13]（prev 大小）
    em.and_ri(0, -8)                                # and rax,-8
    em.mov_rr(1, 13)                                # mov rcx,r13
    em.add_rr(1, 0)                                 # add rcx,rax（prev_end）
    em.cmp_rr(1, 11)                                # cmp rcx,r11
    em.jcc_rel32(0x85, "gswf_insert")               # jne insert
    # 后向合并：prev 吸收整个 run
    em.add_rr(0, 2)                                 # add rax,rdx（prev+run）
    em.mov_mem_r(13, 0, 0)                          # mov [r13],rax
    em.emit(b"\xC3")                                # ret
    em.label_here("gswf_insert")
    em.mov_mem_r(11, 0, 2)                          # mov [r11],rdx（size）
    em.mov_mem_r(11, 8, 14)                         # mov [r11+8],r14（next）
    em.test_rr(13, 13)                              # test r13,r13
    em.jcc_rel32(0x84, "gswf_ins_head")             # jz ins_head
    em.mov_mem_r(13, 8, 11)                         # mov [r13+8],r11
    em.jcc_rel32(None, "gswf_ins_done")             # jmp ins_done
    em.label_here("gswf_ins_head")
    em.store_rip_from("free_head", 11)              # mov [rip+free_head],r11
    em.label_here("gswf_ins_done")
    em.mov_rr(13, 11)                               # mov r13,r11（游标 prev）
    em.emit(b"\xC3")                                # ret


def _emit_seq_dict_runtime(em: _Emitter):
    """砖块 16 阶段二：序列/字典原语运行时子程序（Win64 ABI）。

      dict_find(rax=dict, rcx=key) → rax=pair 指针；未命中 0
      dict_has(rax=dict, rcx=key) → eax=1/0
      dict_keys(rax=dict) / dict_values(rax=dict) → rax=新列表（VM 顺序）
      dict_put(rax=dict, rcx=key, rdx=val) → rax=新字典（不可变更新）
      dict_remove(rax=dict, rcx=key) → rax=新字典
      list_append(rax=xs, rcx=elem) → rax=新列表（xs 为列表则浅拷贝追加，
        否则按 VM 语义视作空列表 [elem]；字符串展开等未覆盖）

    字典物理布局： [TYPE_DICT][count][ (key,value) × count ]，每项 16 字节。
    VM 侧 BUILD_DICT 逆序插入，故 VM 逻辑顺序 = 物理 pair 的逆序；本模块的
    keys/values/print 均按物理逆序输出以对齐 VM。
    """
    # ---- dict_find ----
    em.label_here("dict_find")
    em.emit(b"\x41\x55\x41\x56\x41\x57")            # push r13;push r14;push r15
    em.emit(b"\x4C\x8B\x68\x08")                    # mov r13,[rax+8]（count）
    em.emit(b"\x4C\x8D\x70\x10")                    # lea r14,[rax+16]（pairs）
    em.emit(b"\x49\x89\xCF")                        # mov r15,rcx（key）
    em.emit(b"\x4D\x85\xED")                        # test r13,r13
    em.jcc_rel32(0x84, "df_miss")                   # jz miss
    em.label_here("df_loop")
    em.emit(b"\x49\x8B\x06")                        # mov rax,[r14]（键）
    em.emit(b"\x49\x8B\xCF")                        # mov rcx,r15
    em.call_rel32("val_eq")
    em.emit(b"\x48\x85\xC0")                        # test rax,rax
    em.jcc_rel32(0x85, "df_found")                  # jnz found
    em.emit(b"\x49\x83\xC6\x10")                    # add r14,16
    em.emit(b"\x49\xFF\xCD")                        # dec r13
    em.jcc_rel32(0x85, "df_loop")                   # jnz loop
    em.label_here("df_miss")
    em.emit(b"\x31\xC0")                            # xor eax,eax（未命中 → 0）
    em.jcc_rel32(None, "df_done")
    em.label_here("df_found")
    em.emit(b"\x4C\x89\xF0")                        # mov rax,r14（pair 指针）
    em.label_here("df_done")
    em.emit(b"\x41\x5F\x41\x5E\x41\x5D")            # pop r15;pop r14;pop r13
    em.emit(b"\xC3")                                # ret

    # ---- dict_has ----
    em.label_here("dict_has")
    em.emit(b"\x48\x83\xEC\x08")                    # sub rsp,8（对齐）
    em.call_rel32("dict_find")
    em.emit(b"\x48\x83\xC4\x08")                    # add rsp,8
    em.emit(b"\x48\x85\xC0")                        # test rax,rax
    em.emit(b"\x0F\x95\xC0")                        # setne al
    em.emit(b"\x0F\xB6\xC0")                        # movzx eax,al
    em.emit(b"\xC3")                                # ret

    # ---- dict_keys：[pair[n-1].key, …, pair[0].key] ----
    em.label_here("dict_keys")
    em.emit(b"\x41\x55\x41\x56\x41\x57")            # push r13;r14;r15
    em.emit(b"\x49\x89\xC5")                        # mov r13,rax（dict）
    em.emit(b"\x4D\x8B\x75\x08")                    # mov r14,[r13+8]（n）
    em.emit(b"\x4C\x89\xF7")                        # mov rdi,r14
    em.emit(b"\x48\xC1\xE7\x03")                    # shl rdi,3
    em.emit(b"\x48\x83\xC7\x10")                    # add rdi,16
    em.call_rel32("alloc")
    em.emit(b"\xC7\x00" + struct.pack("<I", TYPE_LIST))
    em.emit(b"\x4C\x89\x70\x08")                    # mov [rax+8],r14
    em.emit(b"\x4C\x8D\x48\x10")                    # lea r9,[rax+16]（输出指针）
    em.mov_rr(15, 14)                               # mov r15,r14
    em.shl_ri(15, 4)                                # n*16
    em.add_rr(15, 13)                               # +dict
    em.add_ri(15, 16)                               # +16 → 末项之后
    em.label_here("dk_loop")
    em.emit(b"\x4D\x85\xF6")                        # test r14,r14
    em.jcc_rel32(0x84, "dk_done")                   # jz done
    em.emit(b"\x49\x83\xEF\x10")                    # sub r15,16
    em.mov_rd_mem(2, 15, 0)                         # mov rdx,[r15]（键）
    em.mov_mem_r(9, 0, 2)                           # mov [r9],rdx
    em.emit(b"\x49\x83\xC1\x08")                    # add r9,8
    em.emit(b"\x49\xFF\xCE")                        # dec r14
    em.jcc_rel32(None, "dk_loop")
    em.label_here("dk_done")
    em.emit(b"\x41\x5F\x41\x5E\x41\x5D")            # pop r15;r14;r13
    em.emit(b"\xC3")                                # ret

    # ---- dict_values ----
    em.label_here("dict_values")
    em.emit(b"\x41\x55\x41\x56\x41\x57")            # push r13;r14;r15
    em.emit(b"\x49\x89\xC5")                        # mov r13,rax
    em.emit(b"\x4D\x8B\x75\x08")                    # mov r14,[r13+8]
    em.emit(b"\x4C\x89\xF7")                        # mov rdi,r14
    em.emit(b"\x48\xC1\xE7\x03")                    # shl rdi,3
    em.emit(b"\x48\x83\xC7\x10")                    # add rdi,16
    em.call_rel32("alloc")
    em.emit(b"\xC7\x00" + struct.pack("<I", TYPE_LIST))
    em.emit(b"\x4C\x89\x70\x08")                    # mov [rax+8],r14
    em.emit(b"\x4C\x8D\x48\x10")                    # lea r9,[rax+16]
    em.mov_rr(15, 14)
    em.shl_ri(15, 4)
    em.add_rr(15, 13)
    em.add_ri(15, 16)
    em.label_here("dv_loop")
    em.emit(b"\x4D\x85\xF6")                        # test r14,r14
    em.jcc_rel32(0x84, "dv_done")
    em.emit(b"\x49\x83\xEF\x10")                    # sub r15,16
    em.mov_rd_mem(2, 15, 8)                         # mov rdx,[r15+8]（值）
    em.mov_mem_r(9, 0, 2)                           # mov [r9],rdx
    em.emit(b"\x49\x83\xC1\x08")                    # add r9,8
    em.emit(b"\x49\xFF\xCE")                        # dec r14
    em.jcc_rel32(None, "dv_loop")
    em.label_here("dv_done")
    em.emit(b"\x41\x5F\x41\x5E\x41\x5D")
    em.emit(b"\xC3")                                # ret

    # ---- dict_put（不可变更新；新键插到物理首位以对齐 VM 逻辑末尾）----
    em.label_here("dict_put")
    em.emit(b"\x55\x48\x89\xE5")                    # push rbp;mov rbp,rsp
    em.emit(b"\x48\x83\xEC\x60")                    # sub rsp,0x60
    em.mov_mem_r(5, -8, 0)                          # [rbp-8]=dict
    em.mov_mem_r(5, -16, 1)                         # [rbp-16]=key
    em.mov_mem_r(5, -24, 2)                         # [rbp-24]=val
    em.call_rel32("dict_find")                      # rax=ptr/0
    em.mov_mem_r(5, -32, 0)                         # [rbp-32]=ptr
    em.mov_rd_mem(2, 5, -8)                         # rdx=dict
    em.mov_rd_mem(1, 2, 8)                          # rcx=n
    em.mov_mem_r(5, -40, 1)                         # [rbp-40]=n
    em.mov_rr(8, 1)                                 # r8=n
    em.emit(b"\x48\x85\xC0")                        # test rax,rax（ptr）
    em.jcc_rel32(0x85, "dp_newn_done")              # jnz 已有键
    em.inc_r(8)                                     # 新键 → n+1
    em.label_here("dp_newn_done")
    em.mov_mem_r(5, -48, 8)                         # [rbp-48]=newn
    em.mov_rr(7, 8)                                 # rdi=newn
    em.shl_ri(7, 4)                                 # ×16
    em.add_ri(7, 16)
    em.call_rel32("alloc")
    em.mov_mem_r(5, -56, 0)                         # [rbp-56]=newobj
    em.emit(b"\xC7\x00" + struct.pack("<I", TYPE_DICT))
    em.mov_rd_mem(1, 5, -48)                        # rcx=newn
    em.mov_mem_r(0, 8, 1)                           # [newobj+8]=newn
    em.mov_rd_mem(8, 5, -32)                        # r8=ptr
    em.emit(b"\x4D\x85\xC0")                        # test r8,r8
    em.jcc_rel32(0x84, "dp_isnew")                  # jz 新键
    # 已有键：整表拷贝，再就地改值
    em.mov_rd_mem(7, 5, -56)
    em.add_ri(7, 16)                                # rdi=newobj+16
    em.mov_rd_mem(6, 5, -8)
    em.add_ri(6, 16)                                # rsi=dict+16
    em.mov_rd_mem(1, 5, -40)
    em.shl_ri(1, 1)                                 # rcx=2n
    em.emit(b"\xF3\x48\xA5")                        # rep movsq
    em.mov_rd_mem(7, 5, -56)                        # rdi=newobj
    em.mov_rd_mem(0, 5, -32)                        # rax=ptr
    em.mov_rd_mem(8, 5, -8)                         # r8=dict
    em.sub_rr(0, 8)                                 # ptr-dict
    em.add_rr(7, 0)                                 # rdi += (ptr-dict)
    em.mov_rd_mem(0, 5, -24)                        # rax=val
    em.mov_mem_r(7, 8, 0)                           # [rdi+8]=val
    em.jcc_rel32(None, "dp_ret")
    em.label_here("dp_isnew")
    # 新键：旧表拷到 +16（pair1 起），pair0=(key,val)
    em.mov_rd_mem(7, 5, -56)
    em.add_ri(7, 32)                                # rdi=newobj+32
    em.mov_rd_mem(6, 5, -8)
    em.add_ri(6, 16)                                # rsi=dict+16
    em.mov_rd_mem(1, 5, -40)
    em.shl_ri(1, 1)                                 # rcx=2n
    em.emit(b"\xF3\x48\xA5")                        # rep movsq
    em.mov_rd_mem(7, 5, -56)
    em.mov_rd_mem(0, 5, -16)                        # rax=key
    em.mov_mem_r(7, 16, 0)                          # [newobj+16]=key
    em.mov_rd_mem(0, 5, -24)                        # rax=val
    em.mov_mem_r(7, 24, 0)                          # [newobj+24]=val
    em.label_here("dp_ret")
    em.mov_rd_mem(0, 5, -56)                        # rax=newobj
    em.emit(b"\xC9\xC3")                            # leave;ret

    # ---- dict_remove（过滤指定键；保留物理顺序）----
    em.label_here("dict_remove")
    em.emit(b"\x55\x48\x89\xE5")                    # push rbp;mov rbp,rsp
    em.emit(b"\x48\x83\xEC\x60")                    # sub rsp,0x60
    em.mov_mem_r(5, -8, 0)                          # [rbp-8]=dict
    em.mov_mem_r(5, -16, 1)                         # [rbp-16]=key
    em.call_rel32("dict_find")
    em.mov_mem_r(5, -24, 0)                         # [rbp-24]=ptr
    em.mov_rd_mem(2, 5, -8)
    em.mov_rd_mem(1, 2, 8)                          # rcx=n
    em.mov_mem_r(5, -32, 1)                         # [rbp-32]=n
    em.mov_rr(8, 1)
    em.emit(b"\x48\x85\xC0")                        # test rax,rax
    em.jcc_rel32(0x84, "dr_newn_done")              # jz 未命中 → n
    em.dec_r(8)                                     # 命中 → n-1
    em.label_here("dr_newn_done")
    em.mov_mem_r(5, -40, 8)                         # [rbp-40]=newn
    em.mov_rr(7, 8)
    em.shl_ri(7, 4)
    em.add_ri(7, 16)
    em.call_rel32("alloc")
    em.mov_mem_r(5, -48, 0)                         # [rbp-48]=newobj
    em.emit(b"\xC7\x00" + struct.pack("<I", TYPE_DICT))
    em.mov_rd_mem(1, 5, -40)
    em.mov_mem_r(0, 8, 1)                           # [newobj+8]=newn
    em.mov_rd_mem(8, 5, -24)                        # r8=ptr
    em.emit(b"\x4D\x85\xC0")                        # test r8,r8
    em.jcc_rel32(0x85, "dr_filtered")               # jnz 命中
    # 未命中：整表拷贝
    em.mov_rd_mem(7, 5, -48)
    em.add_ri(7, 16)
    em.mov_rd_mem(6, 5, -8)
    em.add_ri(6, 16)
    em.mov_rd_mem(1, 5, -32)
    em.shl_ri(1, 1)
    em.emit(b"\xF3\x48\xA5")
    em.jcc_rel32(None, "dr_ret")
    em.label_here("dr_filtered")
    em.mov_rd_mem(1, 5, -24)                        # rcx=ptr
    em.mov_rd_mem(0, 5, -8)
    em.sub_rr(1, 0)                                 # ptr-dict
    em.emit(b"\x48\x83\xE9\x10")                    # sub rcx,16
    em.shr_ri(1, 4)                                 # idx
    em.mov_mem_r(5, -56, 1)                         # [rbp-56]=idx
    em.mov_rd_mem(7, 5, -48)
    em.add_ri(7, 16)                                # rdi=newobj+16
    em.mov_rd_mem(6, 5, -8)
    em.add_ri(6, 16)                                # rsi=dict+16
    em.shl_ri(1, 1)                                 # rcx=2*idx（前段）
    em.emit(b"\xF3\x48\xA5")                        # 拷贝 idx 项
    em.emit(b"\x48\x83\xC6\x10")                    # add rsi,16（跳过被删项）
    em.mov_rd_mem(1, 5, -32)                        # rcx=n
    em.mov_rd_mem(0, 5, -56)
    em.sub_rr(1, 0)                                 # n-idx
    em.dec_r(1)                                     # n-idx-1
    em.shl_ri(1, 1)                                 # ×2
    em.emit(b"\xF3\x48\xA5")                        # 拷贝后段
    em.label_here("dr_ret")
    em.mov_rd_mem(0, 5, -48)
    em.emit(b"\xC9\xC3")                            # leave;ret

    # ---- list_append ----
    em.label_here("list_append")
    em.emit(b"\x41\x55\x41\x56\x41\x57")            # push r13;r14;r15
    em.mov_rr(13, 0)                                # r13=xs
    em.mov_rr(14, 1)                                # r14=elem
    em.mov_rr(0, 13)
    em.mov_rr(1, 0)
    em.lea_rip(2, "heap_base")
    em.sub_rr(1, 2)
    em.cmp_ri(1, HEAP_SIZE)
    em.jcc_rel32(0x83, "la_notptr")                 # jae 非指针
    em.mov_rd_mem(1, 0, 0)                          # rcx=[rax]（类型）
    em.cmp_ri(1, TYPE_LIST)
    em.jcc_rel32(0x85, "la_notptr")                 # jne 非列表
    em.mov_rd_mem(15, 13, 8)                        # r15=n
    em.mov_rr(7, 15)
    em.shl_ri(7, 3)
    em.add_ri(7, 24)                                # (n+1)*8+16
    em.call_rel32("alloc")
    em.emit(b"\xC7\x00" + struct.pack("<I", TYPE_LIST))
    em.mov_rr(1, 15)
    em.inc_r(1)
    em.mov_mem_r(0, 8, 1)                           # [rax+8]=n+1
    em.mov_rr(7, 0)
    em.add_ri(7, 16)                                # rdi=dst
    em.mov_rr(6, 13)
    em.add_ri(6, 16)                                # rsi=src
    em.mov_rr(1, 15)                                # rcx=n
    em.emit(b"\xF3\x48\xA5")                        # rep movsq（rdi 落到追加槽）
    em.mov_mem_r(7, 0, 14)                          # [rdi]=elem
    em.jcc_rel32(None, "la_done")
    em.label_here("la_notptr")
    em.emit(b"\x48\xC7\xC7\x18\x00\x00\x00")        # mov rdi,24
    em.call_rel32("alloc")
    em.emit(b"\xC7\x00" + struct.pack("<I", TYPE_LIST))
    em.emit(b"\x48\xC7\x40\x08\x01\x00\x00\x00")    # mov qword[rax+8],1
    em.mov_mem_r(0, 16, 14)                         # [rax+16]=elem
    em.label_here("la_done")
    em.emit(b"\x41\x5F\x41\x5E\x41\x5D")            # pop r15;r14;r13
    em.emit(b"\xC3")                                # ret

    # ---- list_dedup(rax=xs) → rax=新列表（按 val_eq 去重、保序）----
    # 对齐 vm.py _builtin_make_set 的 seen 语义：元素保序，重复者只留首次出现。
    # 非列表输入 → 空列表：原生运行时无语言级异常机制（仅 OOM abort），内建一律降级，
    # 同 len/append；VM 侧同一输入会抛 TypeError（编译器恒传列表，故不可达）。
    em.label_here("list_dedup")
    em.emit(b"\x53\x41\x54\x41\x55\x41\x56\x41\x57")  # push rbx;r12;r13;r14;r15
    em.mov_rr(1, 0)
    em.lea_rip(2, "heap_base")
    em.sub_rr(1, 2)
    em.cmp_ri(1, HEAP_SIZE)
    em.jcc_rel32(0x83, "ld_empty")                   # 非指针 → 空表
    em.mov_rd_mem(1, 0, 0)                            # rcx=[rax]（类型）
    em.cmp_ri(1, TYPE_LIST)
    em.jcc_rel32(0x85, "ld_empty")                   # 非列表 → 空表
    em.mov_rr(3, 0)                                   # rbx=src
    em.mov_rd_mem(12, 3, 8)                           # r12=n
    em.mov_rr(7, 12)
    em.shl_ri(7, 3)
    em.add_ri(7, 16)                                  # size=16+8n（最坏情况全保留）
    em.call_rel32("alloc")
    em.mov_rr(13, 0)                                  # r13=dst
    em.emit(b"\xC7\x00" + struct.pack("<I", TYPE_LIST))
    em.emit(b"\x48\xC7\x40\x08\x00\x00\x00\x00")      # [dst+8]=0（实际长度后填）
    em.xor_rr32(14, 14)                               # r14=i=0
    em.xor_rr32(15, 15)                               # r15=count=0
    em.label_here("ld_outer")
    em.cmp_rr(14, 12)                                 # cmp i,n
    em.jcc_rel32(0x83, "ld_done")                     # jae：扫描完
    # 寄存器约定：候选走 rcx（val_eq 的第二形参），内层下标走 rdx
    # （val_eq 只写 rax/rcx/rsi/rdi/r8/r9/r10，rdx 得以存活）。
    em.mov_rd_mem(1, 3, 16, 14, 8)                    # rcx=cand=[src+i*8+16]
    em.xor_rr32(2, 2)                                 # rdx=j=0
    em.label_here("ld_inner")
    em.cmp_rr(2, 15)                                  # cmp j,count
    em.jcc_rel32(0x83, "ld_keep")                     # jae：已保留者都不等 → 保留
    em.mov_rd_mem(0, 13, 16, 2, 8)                    # rax=kept=[dst+j*8+16]
    em.call_rel32("val_eq")                           # (kept, cand)
    em.test_rr(0, 0)
    em.jcc_rel32(0x85, "ld_next")                     # 相等 → 丢弃候选
    em.inc_r(2)                                       # j++
    em.jcc_rel32(None, "ld_inner")
    em.label_here("ld_keep")
    em.mov_rd_mem(1, 3, 16, 14, 8)                    # rcx=cand 重取（val_eq 会破坏 rcx）
    em.mov_mem_r_idx(13, 1, 16, 15, 8)                # [dst+count*8+16]=cand
    em.inc_r(15)                                      # count++
    em.label_here("ld_next")
    em.inc_r(14)                                      # i++
    em.jcc_rel32(None, "ld_outer")
    em.label_here("ld_done")
    em.mov_mem_r(13, 8, 15)                           # [dst+8]=count
    em.mov_rr(0, 13)
    em.jcc_rel32(None, "ld_ret")
    em.label_here("ld_empty")
    em.mov_r_imm32(7, 16)
    em.call_rel32("alloc")
    em.emit(b"\xC7\x00" + struct.pack("<I", TYPE_LIST))
    em.emit(b"\x48\xC7\x40\x08\x00\x00\x00\x00")
    em.label_here("ld_ret")
    em.emit(b"\x41\x5F\x41\x5E\x41\x5D\x41\x5C\x5B")  # pop r15;r14;r13;r12;rbx
    em.emit(b"\xC3")                                  # ret


# ---- 砖块 16 阶段三：文件 I/O 运行时 ----

def _emit_fs_runtime(em: _Emitter):
    # fs_pathbuf(rax=str 对象) → rax=堆上 NUL 结尾副本。alloc 破坏 rax/rdx，故
    # 长度先落 [rbp-16]；rep movsb 后 rdi=buf+len，直接写结尾 0。
    em.label_here("fs_pathbuf")
    em.emit(b"\x55")                                # push rbp
    em.emit(b"\x48\x89\xE5")                        # mov rbp,rsp
    em.emit(b"\x48\x83\xEC\x20")                    # sub rsp,0x20
    em.mov_mem_r(5, -8, 0)                          # [rbp-8]=str
    em.mov_rd_mem(2, 0, 8)                          # rdx=len
    em.mov_mem_r(5, -16, 2)                         # [rbp-16]=len
    em.mov_rr(7, 2)                                 # rdi=len
    em.add_ri(7, 1)
    em.call_rel32("alloc")
    em.mov_mem_r(5, -24, 0)                         # [rbp-24]=buf
    em.mov_rr(7, 0)                                 # rdi=buf
    em.mov_rd_mem(6, 5, -8)                         # rsi=str
    em.add_ri(6, 16)
    em.mov_rd_mem(1, 5, -16)                        # rcx=len
    em.emit(b"\xF3\xA4")                            # rep movsb
    em.emit(b"\xC6\x07\x00")                        # mov byte [rdi],0
    em.mov_rd_mem(0, 5, -24)                        # rax=buf
    em.emit(b"\x48\x89\xEC")                        # mov rsp,rbp
    em.emit(b"\x5D\xC3")                            # pop rbp; ret

    # fs_write(rax=path, rcx=content, rdx=mode) → rax=null_obj。失败静默返回 null。
    em.label_here("fs_write")
    em.emit(b"\x55")
    em.emit(b"\x48\x89\xE5")
    em.emit(b"\x48\x83\xEC\x30")                    # sub rsp,0x30
    em.mov_mem_r(5, -8, 1)                          # [rbp-8]=content
    em.mov_mem_r(5, -16, 2)                         # [rbp-16]=mode
    em.call_rel32("fs_pathbuf")                     # rax=buf
    em.mov_mem_r(5, -24, 0)                         # [rbp-24]=buf
    em.emit(b"\x48\x83\xE4\xF0")                    # and rsp,-16
    em.emit(b"\x48\x83\xEC\x40")                    # sub rsp,0x40 (shadow)
    em.mov_rd_mem(1, 5, -24)                        # rcx=buf
    em.mov_rd_mem(2, 5, -16)                        # rdx=mode
    em.call_rip_indirect("crt_fopen")
    em.emit(b"\x48\x85\xC0")                        # test rax,rax
    em.jcc_rel32(0x84, "fw_done")                   # je done（打开失败）
    em.mov_mem_r(5, -32, 0)                         # [rbp-32]=file
    em.mov_rd_mem(1, 5, -8)                         # rcx=content
    em.add_ri(1, 16)
    em.emit(b"\xBA\x01\x00\x00\x00")                # mov edx,1
    em.mov_rd_mem(8, 5, -8)
    em.mov_rd_mem(8, 8, 8)                          # r8=[content+8]=len
    em.mov_rd_mem(9, 5, -32)                        # r9=file
    em.call_rip_indirect("crt_fwrite")
    em.mov_rd_mem(1, 5, -32)                        # rcx=file
    em.call_rip_indirect("crt_fclose")
    em.label_here("fw_done")
    em.lea_rip(0, "null_obj")
    em.emit(b"\x48\x89\xEC")                        # mov rsp,rbp
    em.emit(b"\x5D\xC3")                            # pop rbp; ret


# ---- 砖块 16 阶段三：进制编解码运行时 ----

def _emit_encoding_runtime(em: _Emitter):
    # enc_decode_cp(rsi=src) → rax=Unicode 码点（UTF-8 解码）, rsi=下一字节。
    # 破坏 rdx。与 _emit_builtin_ord 的解码逻辑同源，但支持连续多码点。
    em.label_here("enc_decode_cp")
    em.emit(b"\x0F\xB6\x06")                        # movzx eax,byte [rsi]
    em.emit(b"\x48\xFF\xC6")                        # inc rsi
    em.cmp_ri(0, 0x80)
    em.jcc_rel32(0x82, "edc_done")                  # jb 单字节
    em.cmp_ri(0, 0xE0)
    em.jcc_rel32(0x82, "edc_b2")
    em.cmp_ri(0, 0xF0)
    em.jcc_rel32(0x82, "edc_b3")
    em.and_ri(0, 0x07)
    em.shl_ri(0, 18)
    em.emit(b"\x0F\xB6\x16")                        # movzx edx,byte [rsi]
    em.and_ri(2, 0x3F); em.shl_ri(2, 12); em.add_rr(0, 2); em.emit(b"\x48\xFF\xC6")
    em.emit(b"\x0F\xB6\x16")
    em.and_ri(2, 0x3F); em.shl_ri(2, 6); em.add_rr(0, 2); em.emit(b"\x48\xFF\xC6")
    em.emit(b"\x0F\xB6\x16")
    em.and_ri(2, 0x3F); em.add_rr(0, 2); em.emit(b"\x48\xFF\xC6")
    em.jcc_rel32(None, "edc_done")
    em.label_here("edc_b3")
    em.and_ri(0, 0x0F)
    em.shl_ri(0, 12)
    em.emit(b"\x0F\xB6\x16")
    em.and_ri(2, 0x3F); em.shl_ri(2, 6); em.add_rr(0, 2); em.emit(b"\x48\xFF\xC6")
    em.emit(b"\x0F\xB6\x16")
    em.and_ri(2, 0x3F); em.add_rr(0, 2); em.emit(b"\x48\xFF\xC6")
    em.jcc_rel32(None, "edc_done")
    em.label_here("edc_b2")
    em.and_ri(0, 0x1F)
    em.shl_ri(0, 6)
    em.emit(b"\x0F\xB6\x16")
    em.and_ri(2, 0x3F); em.add_rr(0, 2); em.emit(b"\x48\xFF\xC6")
    em.label_here("edc_done")
    em.emit(b"\xC3")                                # ret

    # enc_emit_int(rax=n, rcx=base, rdi=out) → rax=out'（写入 n 的 base 进制）。
    # 数字从缓冲末位向前写入，再正序拷出。破坏 rdx/r8/r11/rsi。
    em.label_here("enc_emit_int")
    em.emit(b"\x55")                                # push rbp
    em.emit(b"\x48\x89\xE5")                        # mov rbp,rsp
    em.emit(b"\x48\x83\xEC\x20")                    # sub rsp,0x20
    em.emit(b"\x48\x85\xC0")                        # test rax,rax
    em.jcc_rel32(0x85, "eei_nz")
    em.emit(b"\xC6\x07\x30")                        # mov byte [rdi],0x30
    em.emit(b"\x48\x8D\x47\x01")                    # lea rax,[rdi+1]
    em.emit(b"\x48\x89\xEC\x5D\xC3")                # mov rsp,rbp; pop rbp; ret
    em.label_here("eei_nz")
    em.emit(b"\x49\x89\xEB")                        # mov r11,rbp
    em.label_here("eei_loop")
    em.emit(b"\x31\xD2")                            # xor edx,edx
    em.emit(b"\x48\xF7\xF1")                        # div rcx
    em.emit(b"\x80\xC2\x30")                        # add dl,0x30
    em.emit(b"\x49\xFF\xCB")                        # dec r11
    em.emit(b"\x41\x88\x13")                        # mov [r11],dl
    em.emit(b"\x48\x85\xC0")                        # test rax,rax
    em.jcc_rel32(0x85, "eei_loop")
    em.emit(b"\x4C\x89\xDE")                        # mov rsi,r11
    em.emit(b"\x49\x89\xE8")                        # mov r8,rbp
    em.emit(b"\x4C\x2B\xC6")                        # sub r8,rsi（计数=位数）
    em.label_here("eei_copy")
    em.emit(b"\x8A\x06")                            # mov al,[rsi]
    em.emit(b"\x88\x07")                            # mov [rdi],al
    em.emit(b"\x48\xFF\xC6")                        # inc rsi
    em.emit(b"\x48\xFF\xC7")                        # inc rdi
    em.emit(b"\x49\xFF\xC8")                        # dec r8
    em.jcc_rel32(0x85, "eei_copy")
    em.emit(b"\x48\x89\xF8")                        # mov rax,rdi
    em.emit(b"\x48\x89\xEC\x5D\xC3")                # mov rsp,rbp; pop rbp; ret

    # enc_utf8_out(rax=码点, rdi=out) → rax=out'（写入 UTF-8 字节）。破坏 rdx。
    em.label_here("enc_utf8_out")
    em.cmp_ri(0, 0x80)
    em.jcc_rel32(0x82, "eu1")
    em.cmp_ri(0, 0x800)
    em.jcc_rel32(0x82, "eu2")
    em.cmp_ri(0, 0x10000)
    em.jcc_rel32(0x82, "eu3")
    em.mov_rr(2, 0); em.shr_ri(2, 18); em.emit(b"\x80\xCA\xF0")
    em.emit(b"\x88\x17"); em.emit(b"\x48\xFF\xC7")
    em.mov_rr(2, 0); em.shr_ri(2, 12); em.emit(b"\x80\xE2\x3F\x80\xCA\x80")
    em.emit(b"\x88\x17"); em.emit(b"\x48\xFF\xC7")
    em.mov_rr(2, 0); em.shr_ri(2, 6); em.emit(b"\x80\xE2\x3F\x80\xCA\x80")
    em.emit(b"\x88\x17"); em.emit(b"\x48\xFF\xC7")
    em.mov_rr(2, 0); em.emit(b"\x80\xE2\x3F\x80\xCA\x80")
    em.emit(b"\x88\x17"); em.emit(b"\x48\xFF\xC7")
    em.mov_rr(0, 7); em.emit(b"\xC3")
    em.label_here("eu3")
    em.mov_rr(2, 0); em.shr_ri(2, 12); em.emit(b"\x80\xCA\xE0")
    em.emit(b"\x88\x17"); em.emit(b"\x48\xFF\xC7")
    em.mov_rr(2, 0); em.shr_ri(2, 6); em.emit(b"\x80\xE2\x3F\x80\xCA\x80")
    em.emit(b"\x88\x17"); em.emit(b"\x48\xFF\xC7")
    em.mov_rr(2, 0); em.emit(b"\x80\xE2\x3F\x80\xCA\x80")
    em.emit(b"\x88\x17"); em.emit(b"\x48\xFF\xC7")
    em.mov_rr(0, 7); em.emit(b"\xC3")
    em.label_here("eu2")
    em.mov_rr(2, 0); em.shr_ri(2, 6); em.emit(b"\x80\xCA\xC0")
    em.emit(b"\x88\x17"); em.emit(b"\x48\xFF\xC7")
    em.mov_rr(2, 0); em.emit(b"\x80\xE2\x3F\x80\xCA\x80")
    em.emit(b"\x88\x17"); em.emit(b"\x48\xFF\xC7")
    em.mov_rr(0, 7); em.emit(b"\xC3")
    em.label_here("eu1")
    em.emit(b"\x88\x07")                            # mov [rdi],al
    em.emit(b"\x48\x8D\x47\x01")                    # lea rax,[rdi+1]
    em.emit(b"\xC3")                                # ret


def _emit_mathlib_runtime(em: _Emitter):
    """砖块 17：mathlib 数论 / 聚合 / 集合 / 统计 / 随机运行时子程序。

    数论/聚合：ml_gcd、ml_prime；集合：ml_setify；
    统计：ml_sum_double、ml_neumaier_add（CPython 补偿求和）、ml_mean、
    ml_sort_numeric、ml_variance_double、ml_covariance_double；
    随机：ml_rand（xorshift64，rdtsc 播种）。
    """
    # ml_gcd：rax=a，rcx=b → rax=gcd(|a|,|b|)。破坏 rcx/rdx。gcd(0,0)=0。
    em.label_here("ml_gcd")
    em.emit(b"\x48\x85\xC0")                        # test rax,rax
    em.jcc_rel32(0x89, "ml_gcd_a_ok")
    em.emit(b"\x48\xF7\xD8")                        # neg rax
    em.label_here("ml_gcd_a_ok")
    em.emit(b"\x48\x85\xC9")                        # test rcx,rcx
    em.jcc_rel32(0x89, "ml_gcd_b_ok")
    em.emit(b"\x48\xF7\xD9")                        # neg rcx
    em.label_here("ml_gcd_b_ok")
    em.label_here("ml_gcd_loop")
    em.emit(b"\x48\x85\xC9")                        # test rcx,rcx
    em.jcc_rel32(0x84, "ml_gcd_done")
    em.emit(b"\x48\x99")                            # cqo
    em.emit(b"\x48\xF7\xF9")                        # idiv rcx
    em.emit(b"\x48\x89\xC8")                        # mov rax,rcx
    em.emit(b"\x48\x89\xD1")                        # mov rcx,rdx
    em.jcc_rel32(None, "ml_gcd_loop")
    em.label_here("ml_gcd_done")
    em.emit(b"\xC3")                                # ret

    # ml_prime：rax=n → eax=1/0（试除，奇偶剪枝）。破坏 rax/rcx/rdx/r8/r9。
    em.label_here("ml_prime")
    em.emit(b"\x48\x83\xF8\x02")                    # cmp rax,2
    em.jcc_rel32(0x8C, "mlp_no")                    # jl  no
    em.jcc_rel32(0x84, "mlp_yes")                   # je  yes
    em.emit(b"\xA8\x01")                            # test al,1
    em.jcc_rel32(0x84, "mlp_no")                    # jz  no（偶数）
    em.mov_rr(9, 0)                                 # r9=n
    em.mov_r_imm32(8, 3)                            # r8=i=3
    em.label_here("mlp_loop")
    em.mov_rr(1, 8)
    em.emit(b"\x49\x0F\xAF\xC8")                    # imul rcx,r8（i*i）
    em.cmp_rr(1, 9)
    em.jcc_rel32(0x8F, "mlp_yes")                   # jg  yes（i*i>n）
    em.mov_rr(0, 9)                                 # rax=n
    em.emit(b"\x48\x99")                            # cqo
    em.emit(b"\x49\xF7\xF8")                        # idiv r8（rdx=n%i）
    em.test_rr(2, 2)
    em.jcc_rel32(0x84, "mlp_no")                    # jz  no（整除）
    em.add_ri(8, 2)                                 # i+=2
    em.jcc_rel32(None, "mlp_loop")
    em.label_here("mlp_yes")
    em.emit(b"\xB8\x01\x00\x00\x00\xC3")            # mov eax,1; ret
    em.label_here("mlp_no")
    em.emit(b"\x31\xC0\xC3")                        # xor eax,eax; ret

    # ml_setify：rax=列表 → rax=去重升序的新列表（整数集合语义，对齐 set()+sorted）。
    # 元素按 val_eq 判等；排序用有符号整数比较（非整数元素的次序未定义）。
    # 不保存调用方寄存器（用尽栈槽），内部仅调用 alloc/val_eq。
    em.label_here("ml_setify")
    em.emit(b"\x55")                                # push rbp
    em.emit(b"\x48\x89\xE5")                        # mov rbp,rsp
    em.emit(b"\x48\x83\xEC\x40")                    # sub rsp,0x40
    # 槽：[rbp-8]=清单 [rbp-16]=n [rbp-24]=结果 [rbp-32]=m
    #     [rbp-40]=i [rbp-48]=j [rbp-56]=elem
    em.mov_mem_r(5, -8, 0)                          # [rbp-8]=list
    em.mov_rd_mem(0, 5, -8)                         # rax=list
    em.mov_rd_mem(1, 0, 8)                          # rcx=n
    em.mov_mem_r(5, -16, 1)                         # [rbp-16]=n
    em.mov_rr(7, 1)                                 # rdi=n
    em.shl_ri(7, 3)
    em.add_ri(7, 16)                                # 16+8*n
    em.call_rel32("alloc")
    em.emit(b"\xC7\x00" + struct.pack("<I", TYPE_LIST))
    em.mov_mem_r(5, -24, 0)                         # [rbp-24]=result
    em.emit(b"\x48\xC7\x45\xE0\x00\x00\x00\x00")    # [rbp-32]=m=0
    em.emit(b"\x48\xC7\x45\xD8\x00\x00\x00\x00")    # [rbp-40]=i=0
    em.label_here("mlset_outer")
    em.mov_rd_mem(0, 5, -40)                        # i
    em.mov_rd_mem(1, 5, -16)                        # n
    em.cmp_rr(0, 1)
    em.jcc_rel32(0x8D, "mlset_sort")                # jge sort
    em.mov_rd_mem(0, 5, -8)                         # list
    em.mov_rd_mem(2, 5, -40)                        # i
    em.mov_rd_mem(8, 0, 16, index=2, scale=8)       # r8=elem
    em.mov_mem_r(5, -56, 8)                         # [rbp-56]=elem
    em.emit(b"\x48\xC7\x45\xD0\x00\x00\x00\x00")    # [rbp-48]=j=0
    em.label_here("mlset_inner")
    em.mov_rd_mem(0, 5, -48)                        # j
    em.mov_rd_mem(1, 5, -32)                        # m
    em.cmp_rr(0, 1)
    em.jcc_rel32(0x8D, "mlset_add")                 # jge add
    em.mov_rd_mem(0, 5, -24)                        # result
    em.mov_rd_mem(2, 5, -48)                        # j
    em.mov_rd_mem(0, 0, 16, index=2, scale=8)       # rax=result[j]
    em.mov_rd_mem(1, 5, -56)                        # rcx=elem
    em.call_rel32("val_eq")                         # eax=1/0
    em.emit(b"\x85\xC0")                            # test eax,eax
    em.jcc_rel32(0x85, "mlset_skip")                # jnz skip（重复）
    em.mov_rd_mem(0, 5, -48)
    em.inc_r(0)
    em.mov_mem_r(5, -48, 0)                         # j++
    em.jcc_rel32(None, "mlset_inner")
    em.label_here("mlset_add")
    em.mov_rd_mem(0, 5, -24)                        # result
    em.mov_rd_mem(1, 5, -32)                        # m
    em.mov_rd_mem(2, 5, -56)                        # elem
    em.mov_mem_r_idx(0, 2, 16, index=1, scale=8)    # result[m]=elem
    em.mov_rd_mem(0, 5, -32)
    em.inc_r(0)
    em.mov_mem_r(5, -32, 0)                         # m++
    em.label_here("mlset_skip")
    em.mov_rd_mem(0, 5, -40)
    em.inc_r(0)
    em.mov_mem_r(5, -40, 0)                         # i++
    em.jcc_rel32(None, "mlset_outer")
    em.label_here("mlset_sort")
    # 插入排序 result[0..m)
    em.mov_rd_mem(8, 5, -24)                        # r8=result
    em.mov_rd_mem(10, 5, -32)                       # r10=m
    em.mov_r_imm32(9, 1)                            # i=1
    em.label_here("mlset_souter")
    em.cmp_rr(9, 10)
    em.jcc_rel32(0x8D, "mlset_sdone")               # jge done
    em.mov_rd_mem(11, 8, 16, index=9, scale=8)      # r11=key=result[i]
    em.lea_mem(1, 9, -1)                            # rcx=j=i-1
    em.label_here("mlset_sinner")
    em.cmp_ri(1, 0)
    em.jcc_rel32(0x8C, "mlset_splace")              # jl place
    em.mov_rd_mem(0, 8, 16, index=1, scale=8)       # rax=result[j]
    em.cmp_rr(0, 11)
    em.jcc_rel32(0x8E, "mlset_splace")              # jle place（有序）
    em.lea_mem(2, 1, 1)                             # rdx=j+1
    em.mov_mem_r_idx(8, 0, 16, index=2, scale=8)    # result[j+1]=result[j]
    em.dec_r(1)
    em.jcc_rel32(None, "mlset_sinner")
    em.label_here("mlset_splace")
    em.lea_mem(2, 1, 1)                             # rdx=j+1
    em.mov_mem_r_idx(8, 11, 16, index=2, scale=8)   # result[j+1]=key
    em.inc_r(9)
    em.jcc_rel32(None, "mlset_souter")
    em.label_here("mlset_sdone")
    em.mov_mem_r(8, 8, 10)                          # [result+8]=m
    em.mov_rr(0, 8)                                 # rax=result
    em.emit(b"\x48\x89\xEC\x5D\xC3")                # mov rsp,rbp; pop rbp; ret

    # ---- 砖块 17 阶段三：统计 / 随机运行时 ----

    # ml_neumaier_add：CPython sum() 的补偿求和单步。xmm2=f、xmm3=c、xmm0=x。
    # 对齐 CPython 3.12+ float sum：t=f+x; |f|>=|x| ? c+=(f-t)+x : c+=(x-t)+f; f=t。
    em.label_here("ml_neumaier_add")
    em.emit(b"\xF2\x0F\x10\xF0")                    # movsd xmm6,xmm0（x）
    em.emit(b"\xF2\x0F\x10\xCA")                    # movsd xmm1,xmm2（f）
    em.addsd(1, 0)                                  # t=f+x
    em.movq_r_xmm(0, 2)                             # rax=f 位
    em.mov_r_imm64(2, 0x7FFFFFFFFFFFFFFF)
    em.emit(b"\x48\x21\xD0")                        # and rax,rdx
    em.movq_xmm_r(4, 0)                             # xmm4=|f|
    em.movq_r_xmm(0, 6)                             # rax=x 位
    em.mov_r_imm64(2, 0x7FFFFFFFFFFFFFFF)
    em.emit(b"\x48\x21\xD0")
    em.movq_xmm_r(5, 0)                             # xmm5=|x|
    em.ucomisd(4, 5)
    em.jcc_rel32(0x83, "mlnz_af")                   # |f|>=|x|
    em.emit(b"\xF2\x0F\x10\xC6")                    # movsd xmm0,xmm6（x）
    em.subsd(0, 1)                                  # x-t
    em.addsd(0, 2)                                  # +f
    em.addsd(3, 0)                                  # c+=
    em.jcc_rel32(None, "mlnz_done")
    em.label_here("mlnz_af")
    em.emit(b"\xF2\x0F\x10\xC2")                    # movsd xmm0,xmm2（f）
    em.subsd(0, 1)                                  # f-t
    em.addsd(0, 6)                                  # +x
    em.addsd(3, 0)                                  # c+=
    em.label_here("mlnz_done")
    em.emit(b"\xF2\x0F\x10\xD1")                    # movsd xmm2,xmm1（f=t）
    em.emit(b"\xC3")                                # ret

    # ml_sum_double：rax=列表 → xmm0=CPython 风格补偿求和（空表→0.0）。
    em.label_here("ml_sum_double")
    em.emit(b"\x55\x48\x89\xE5")                    # push rbp; mov rbp,rsp
    em.emit(b"\x48\x83\xEC\x40")                    # sub rsp,0x40
    em.mov_mem_r(5, -8, 0)                          # [rbp-8]=list
    em.mov_rd_mem(1, 0, 8)                          # rcx=n
    em.mov_mem_r(5, -16, 1)                         # [rbp-16]=n
    em.lea_mem(2, 0, 16)
    em.mov_mem_r(5, -32, 2)                         # [rbp-32]=base
    em.emit(b"\x48\xC7\x45\xE8\x00\x00\x00\x00")    # [rbp-24]=i=0
    em.emit(b"\x66\x0F\xEF\xD2")                    # pxor xmm2,xmm2（f=0）
    em.emit(b"\x66\x0F\xEF\xDB")                    # pxor xmm3,xmm3（c=0）
    em.label_here("mlsum_loop")
    em.mov_rd_mem(0, 5, -24)
    em.mov_rd_mem(1, 5, -16)
    em.cmp_rr(0, 1)
    em.jcc_rel32(0x8D, "mlsum_done")
    em.mov_rd_mem(0, 5, -32)                        # rax=base
    em.mov_rd_mem(1, 5, -24)                        # rcx=i
    em.mov_rd_mem(0, 0, 0, index=1, scale=8)        # rax=base[i]
    em.call_rel32("as_double")                      # xmm0=x
    em.call_rel32("ml_neumaier_add")
    em.mov_rd_mem(0, 5, -24)
    em.inc_r(0)
    em.mov_mem_r(5, -24, 0)
    em.jcc_rel32(None, "mlsum_loop")
    em.label_here("mlsum_done")
    em.addsd(2, 3)                                  # f+c
    em.emit(b"\xF2\x0F\x10\xC2")                    # movsd xmm0,xmm2
    em.emit(b"\x48\x89\xEC\x5D\xC3")

    # ml_mean：rax=列表 → xmm0=sum/len（空表→0.0）。
    em.label_here("ml_mean")
    em.emit(b"\x55\x48\x89\xE5")
    em.emit(b"\x48\x83\xEC\x40")
    em.mov_mem_r(5, -8, 0)
    em.call_rel32("ml_sum_double")
    em.movsd_store(5, -16, 0)                       # [rbp-16]=sum
    em.mov_rd_mem(0, 5, -8)
    em.mov_rd_mem(1, 0, 8)                          # n
    em.test_rr(1, 1)
    em.jcc_rel32(0x84, "mlmean_zero")
    em.cvtsi2sd(1, 1)                               # xmm1=(double)n
    em.movsd_load(0, 5, -16)
    em.divsd(0, 1)
    em.emit(b"\x48\x89\xEC\x5D\xC3")
    em.label_here("mlmean_zero")
    em.emit(b"\x66\x0F\xEF\xC0")                    # pxor xmm0,xmm0
    em.emit(b"\x48\x89\xEC\x5D\xC3")

    # ml_sort_numeric：rax=列表 → rax=按数值升序的新列表（复用 float_cmp2，
    # 故整数/浮点混排亦可；非可比元素未定义）。
    em.label_here("ml_sort_numeric")
    em.emit(b"\x55\x48\x89\xE5")
    em.emit(b"\x48\x83\xEC\x60")
    em.mov_mem_r(5, -8, 0)                          # [rbp-8]=list
    em.mov_rd_mem(1, 0, 8)                          # n
    em.mov_mem_r(5, -16, 1)                         # [rbp-16]=n
    em.mov_rr(7, 1)
    em.shl_ri(7, 3)
    em.add_ri(7, 16)
    em.call_rel32("alloc")
    em.emit(b"\xC7\x00" + struct.pack("<I", TYPE_LIST))
    em.mov_rd_mem(1, 5, -16)
    em.mov_mem_r(0, 8, 1)                           # [res+8]=n
    em.mov_mem_r(5, -24, 0)                         # [rbp-24]=res
    em.emit(b"\x48\xC7\x45\xD8\x00\x00\x00\x00")    # [rbp-40]=i=0（拷贝）
    em.label_here("mlsort_copy")
    em.mov_rd_mem(0, 5, -40)
    em.mov_rd_mem(1, 5, -16)
    em.cmp_rr(0, 1)
    em.jcc_rel32(0x8D, "mlsort_sort")
    em.mov_rd_mem(2, 5, -8)                         # list
    em.mov_rd_mem(1, 5, -40)
    em.mov_rd_mem(2, 2, 16, index=1, scale=8)       # elem
    em.mov_rd_mem(0, 5, -24)                        # res
    em.mov_mem_r_idx(0, 2, 16, index=1, scale=8)
    em.mov_rd_mem(0, 5, -40)
    em.inc_r(0)
    em.mov_mem_r(5, -40, 0)
    em.jcc_rel32(None, "mlsort_copy")
    em.label_here("mlsort_sort")
    em.emit(b"\x48\xC7\x45\xD8\x00\x00\x00\x00")    # [rbp-40]=i=1
    em.label_here("mlsort_outer")
    em.mov_rd_mem(0, 5, -40)                        # i
    em.mov_rd_mem(1, 5, -16)                        # n
    em.cmp_rr(0, 1)
    em.jcc_rel32(0x8D, "mlsort_done")               # i>=n
    em.mov_rd_mem(0, 5, -24)                        # res
    em.mov_rd_mem(1, 5, -40)                        # i
    em.mov_rd_mem(2, 0, 16, index=1, scale=8)       # key=res[i]
    em.mov_mem_r(5, -48, 2)                         # [rbp-48]=key
    em.mov_rd_mem(1, 5, -40)
    em.dec_r(1)                                     # j=i-1
    em.mov_mem_r(5, -32, 1)                         # [rbp-32]=j
    em.label_here("mlsort_inner")
    em.mov_rd_mem(1, 5, -32)
    em.cmp_ri(1, 0)
    em.jcc_rel32(0x8C, "mlsort_place")              # j<0
    em.mov_rd_mem(0, 5, -24)
    em.mov_rd_mem(1, 5, -32)
    em.mov_rd_mem(0, 0, 16, index=1, scale=8)       # res[j]
    em.call_rel32("as_double")                      # xmm0=res[j]
    em.movsd_store(5, -56, 0)
    em.mov_rd_mem(0, 5, -48)                        # key
    em.call_rel32("as_double")                      # xmm0=key
    em.movsd_load(1, 5, -56)                        # xmm1=res[j]
    em.ucomisd(1, 0)
    em.jcc_rel32(0x86, "mlsort_place")              # res[j]<=key（UCOMISD→jbe）
    em.mov_rd_mem(0, 5, -24)
    em.mov_rd_mem(1, 5, -32)
    em.mov_rd_mem(2, 0, 16, index=1, scale=8)       # rdx=res[j]
    em.lea_mem(1, 1, 1)                             # j+1
    em.mov_mem_r_idx(0, 2, 16, index=1, scale=8)    # res[j+1]=res[j]
    em.mov_rd_mem(1, 5, -32)
    em.dec_r(1)
    em.mov_mem_r(5, -32, 1)
    em.jcc_rel32(None, "mlsort_inner")
    em.label_here("mlsort_place")
    em.mov_rd_mem(0, 5, -24)
    em.mov_rd_mem(1, 5, -32)
    em.lea_mem(1, 1, 1)                             # j+1
    em.mov_rd_mem(2, 5, -48)                        # key
    em.mov_mem_r_idx(0, 2, 16, index=1, scale=8)    # res[j+1]=key
    em.mov_rd_mem(0, 5, -40)
    em.inc_r(0)
    em.mov_mem_r(5, -40, 0)
    em.jcc_rel32(None, "mlsort_outer")
    em.label_here("mlsort_done")
    em.mov_rd_mem(0, 5, -24)
    em.emit(b"\x48\x89\xEC\x5D\xC3")

    # ml_variance_double：rax=列表 → xmm0=总体方差（空表→0.0）。
    em.label_here("ml_variance_double")
    em.emit(b"\x55\x48\x89\xE5")
    em.emit(b"\x48\x83\xEC\x60")
    em.mov_mem_r(5, -8, 0)                          # [rbp-8]=list
    em.mov_rd_mem(1, 0, 8)
    em.mov_mem_r(5, -16, 1)                         # n
    em.test_rr(1, 1)
    em.jcc_rel32(0x84, "mlvar_zero")
    em.lea_mem(2, 0, 16)
    em.mov_mem_r(5, -32, 2)                         # base
    em.mov_rd_mem(0, 5, -8)
    em.call_rel32("ml_mean")
    em.movsd_store(5, -40, 0)                       # mean
    em.emit(b"\x48\xC7\x45\xE8\x00\x00\x00\x00")    # i=0
    em.emit(b"\x66\x0F\xEF\xD2")                    # pxor xmm2,xmm2（f=0）
    em.emit(b"\x66\x0F\xEF\xDB")                    # pxor xmm3,xmm3（c=0）
    em.label_here("mlvar_loop")
    em.mov_rd_mem(0, 5, -24)
    em.mov_rd_mem(1, 5, -16)
    em.cmp_rr(0, 1)
    em.jcc_rel32(0x8D, "mlvar_done")
    em.mov_rd_mem(0, 5, -32)
    em.mov_rd_mem(1, 5, -24)
    em.mov_rd_mem(0, 0, 0, index=1, scale=8)
    em.call_rel32("as_double")
    em.movsd_load(1, 5, -40)
    em.subsd(0, 1)                                  # x-mean
    em.mulsd(0, 0)                                  # (x-mean)^2
    em.call_rel32("ml_neumaier_add")
    em.mov_rd_mem(0, 5, -24)
    em.inc_r(0)
    em.mov_mem_r(5, -24, 0)
    em.jcc_rel32(None, "mlvar_loop")
    em.label_here("mlvar_done")
    em.addsd(2, 3)                                  # f+c
    em.emit(b"\xF2\x0F\x10\xC2")                    # movsd xmm0,xmm2
    em.mov_rd_mem(1, 5, -16)
    em.cvtsi2sd(1, 1)
    em.divsd(0, 1)
    em.emit(b"\x48\x89\xEC\x5D\xC3")
    em.label_here("mlvar_zero")
    em.emit(b"\x66\x0F\xEF\xC0")
    em.emit(b"\x48\x89\xEC\x5D\xC3")

    # ml_covariance_double：rax=x，rcx=y → xmm0=协方差（长度不等/空→0.0）。
    em.label_here("ml_covariance_double")
    em.emit(b"\x55\x48\x89\xE5")
    em.emit(b"\x48\x81\xEC\x80\x00\x00\x00")        # sub rsp,0x80（imm32，勿用 imm8）
    em.mov_mem_r(5, -8, 0)                          # x
    em.mov_mem_r(5, -16, 1)                         # y
    em.mov_rd_mem(0, 5, -8)
    em.mov_rd_mem(1, 0, 8)
    em.mov_mem_r(5, -24, 1)                         # n=len(x)
    em.mov_rd_mem(0, 5, -16)
    em.mov_rd_mem(2, 0, 8)                          # len(y)
    em.cmp_rr(1, 2)
    em.jcc_rel32(0x85, "mlcov_zero")                # 长度不等
    em.test_rr(1, 1)
    em.jcc_rel32(0x84, "mlcov_zero")                # 空
    em.mov_rd_mem(0, 5, -8)
    em.lea_mem(2, 0, 16)
    em.mov_mem_r(5, -64, 2)                         # bx
    em.mov_rd_mem(0, 5, -16)
    em.lea_mem(2, 0, 16)
    em.mov_mem_r(5, -72, 2)                         # by
    em.mov_rd_mem(0, 5, -8)
    em.call_rel32("ml_mean")
    em.movsd_store(5, -40, 0)                       # mx
    em.mov_rd_mem(0, 5, -16)
    em.call_rel32("ml_mean")
    em.movsd_store(5, -48, 0)                       # my
    em.emit(b"\x48\xC7\x45\xE0\x00\x00\x00\x00")    # [rbp-32]=i=0
    em.emit(b"\x66\x0F\xEF\xD2")                    # pxor xmm2,xmm2（f=0）
    em.emit(b"\x66\x0F\xEF\xDB")                    # pxor xmm3,xmm3（c=0）
    em.label_here("mlcov_loop")
    em.mov_rd_mem(0, 5, -32)
    em.mov_rd_mem(1, 5, -24)
    em.cmp_rr(0, 1)
    em.jcc_rel32(0x8D, "mlcov_done")
    em.mov_rd_mem(0, 5, -64)
    em.mov_rd_mem(1, 5, -32)
    em.mov_rd_mem(0, 0, 0, index=1, scale=8)
    em.call_rel32("as_double")
    em.movsd_load(1, 5, -40)
    em.subsd(0, 1)
    em.movsd_store(5, -80, 0)                       # dx
    em.mov_rd_mem(0, 5, -72)
    em.mov_rd_mem(1, 5, -32)
    em.mov_rd_mem(0, 0, 0, index=1, scale=8)
    em.call_rel32("as_double")
    em.movsd_load(1, 5, -48)
    em.subsd(0, 1)
    em.movsd_store(5, -88, 0)                       # dy
    em.movsd_load(0, 5, -80)
    em.movsd_load(1, 5, -88)
    em.mulsd(0, 1)                                  # dx*dy
    em.call_rel32("ml_neumaier_add")
    em.mov_rd_mem(0, 5, -32)
    em.inc_r(0)
    em.mov_mem_r(5, -32, 0)
    em.jcc_rel32(None, "mlcov_loop")
    em.label_here("mlcov_done")
    em.addsd(2, 3)                                  # f+c
    em.emit(b"\xF2\x0F\x10\xC2")                    # movsd xmm0,xmm2
    em.mov_rd_mem(1, 5, -24)
    em.cvtsi2sd(1, 1)
    em.divsd(0, 1)
    em.emit(b"\x48\x89\xEC\x5D\xC3")
    em.label_here("mlcov_zero")
    em.emit(b"\x66\x0F\xEF\xC0")
    em.emit(b"\x48\x89\xEC\x5D\xC3")

    # ml_rand：xmm0 ∈ [0,1)（xorshift64，首次以 CRT time() 播种）。
    em.label_here("ml_rand")
    em.emit(b"\x48\x8B\x05")
    em.rel32_to("rand_state")                       # mov rax,[rip+rand_state]
    em.emit(b"\x48\x85\xC0")                        # test rax,rax
    em.jcc_rel32(0x85, "mlrand_have")
    em.emit(b"\x0F\x31")                            # rdtsc → edx:eax
    em.emit(b"\x48\xC1\xE2\x20")                    # shl rdx,32
    em.emit(b"\x48\x09\xD0")                        # or rax,rdx
    em.mov_r_imm64(2, 0x9E3779B97F4A7C15)
    em.emit(b"\x48\x31\xD0")                        # xor rax,rdx
    em.emit(b"\x48\x85\xC0")                        # test rax,rax
    em.jcc_rel32(0x85, "mlrand_have")
    em.emit(b"\xB8\x01\x00\x00\x00")                # mov eax,1（避免全零态）
    em.label_here("mlrand_have")
    em.mov_rr(1, 0)
    em.shl_ri(1, 13)
    em.emit(b"\x48\x31\xC8")                        # xor rax,rcx
    em.mov_rr(1, 0)
    em.shr_ri(1, 7)
    em.emit(b"\x48\x31\xC8")
    em.mov_rr(1, 0)
    em.shl_ri(1, 17)
    em.emit(b"\x48\x31\xC8")
    em.store_rip_from("rand_state", 0)
    em.mov_rr(1, 0)
    em.shr_ri(1, 11)                                # 高 53 位
    em.cvtsi2sd(0, 1)
    em.mov_r_imm64(2, _dbl_bits(2.0 ** -53))
    em.movq_xmm_r(1, 2)
    em.mulsd(0, 1)
    em.emit(b"\xC3")                                # ret


def _emit_unpack_seq(em: _Emitter, n: int, tag: str, idx: int):
    """UNPACK_SEQ n：弹出序列，依次压入第 0..n-1 个元素。

    栈效果对齐 vm.py:515（None 视为空序列；越界项补 None；字符串按字节取）。
    输入 [.., seq]（seq 在栈顶）→ 输出 [.., e0, e1, ..., e(n-1)]，
    e(n-1) 位于栈顶。vm.py:488 的注释说明 BUILD_LIST 压入顺序即书写顺序，
    故 e0 必须位于 e(n-1) 之下，编译器的 `for nm in reversed(names)` 依赖这一点。

    寄存器：R13=序列基址，R14=长度。循环内不调用任何子程序，因此无需
    保存被调用者保存寄存器（R13/R14）。
    """
    em.pop_to(0)                                    # rax = 序列
    lnull = f"unpk_null_{tag}_{idx}"
    ldone = f"unpk_done_{tag}_{idx}"
    lst = f"unpk_list_{tag}_{idx}"
    lstr = f"unpk_str_{tag}_{idx}"
    em.emit(b"\x49\x89\xC5")                        # mov r13,rax（r13=序列）
    em.lea_rip(2, "heap_base")                      # lea rdx,[heap_base]
    em.emit(b"\x4C\x89\xC5")                        # mov rax,r13
    em.emit(b"\x48\x29\xD0")                        # sub rax,rdx
    em.emit(b"\x48\x81\xF8" + struct.pack("<I", HEAP_SIZE))
    em.jcc_rel32(0x83, lnull)                       # jae：非堆指针 → 全 None
    em.emit(b"\x41\x8B\x7D\x00")                    # mov edi,[r13]（类型）
    em.emit(bytes([0x83, 0xFF, TYPE_LIST]))          # cmp edi,TYPE_LIST
    em.jcc_rel32(0x85, lstr)                        # jne → 字符串分支
    em.emit(b"\x4D\x8B\x75\x08")                    # mov r14,[r13+8] → r14=len
    for i in range(n):
        lnil = f"unpk_n_{tag}_{idx}_{i}"
        lok = f"unpk_k_{tag}_{idx}_{i}"
        em.emit(b"\x49\x83\xFE" + bytes([i & 0xFF]))  # cmp r14d,i
        em.jcc_rel32(0x86, lnil)                    # jbe i>=len → None
        # 偏移 16+8i 为编译期常量，用 lea+mov 避免 SIB 手工编码
        em.emit(b"\x49\x8D\x45")                    # lea rax,[r13+disp8]
        em.emit(bytes([16 + 8 * i]))
        em.emit(b"\x48\x8B\x00")                    # mov rax,[rax]
        em.jcc_rel32(None, lok)
        em.label_here(lnil)
        em.lea_rip(0, "null_obj")
        em.label_here(lok)
        em.push_rax()
    em.jcc_rel32(None, ldone)
    em.label_here(lstr)
    em.emit(bytes([0x83, 0xFF, TYPE_STR]))           # cmp edi,TYPE_STR
    em.jcc_rel32(0x85, lnull)                        # jne：非序列 → 全 None
    em.emit(b"\x4D\x8B\x75\x08")                    # mov r14,[r13+8] → r14=len
    for i in range(n):
        lnil = f"unpk_sn_{tag}_{idx}_{i}"
        lok = f"unpk_sk_{tag}_{idx}_{i}"
        em.emit(b"\x49\x83\xFE" + bytes([i & 0xFF]))  # cmp r14d,i
        em.jcc_rel32(0x86, lnil)                    # jbe i>=len → None
        # 字符串按字节取，与 vm 的 seq[i] 一致（VM 得到单字符 str）；
        # 原生端构造 1 字节 str 对象，保证 输出 / == 语义一致。
        em.emit(b"\x48\xC7\xC7\x11\x00\x00\x00")    # mov rdi,17
        em.call_rel32("alloc")                        # alloc 不触碰 r13/r14
        em.emit(b"\x4D\x8D\x5D")                    # lea r11,[r13+disp8]（16+i）
        em.emit(bytes([16 + i]))
        em.emit(b"\x45\x0F\xB6\x1B")                # movzx r11d,byte [r11]
        em.emit(b"\x48\xC7\x00" + struct.pack("<I", TYPE_STR))
        em.emit(b"\x48\xC7\x40\x08\x01\x00\x00\x00")  # mov [rax+8],1
        em.emit(b"\x4C\x88\x58\x10")                # mov [rax+16],r11b
        em.jcc_rel32(None, lok)
        em.label_here(lnil)
        em.lea_rip(0, "null_obj")
        em.label_here(lok)
        em.push_rax()
    em.jcc_rel32(None, ldone)
    em.label_here(lnull)
    for _ in range(n):
        em.lea_rip(0, "null_obj")
        em.push_rax()
    em.label_here(ldone)


def _emit_builtin_len(em: _Emitter):
    """内建 len(x) → 长度；按 M3V 调用约定（1 参函数）。

    砖块 19：文本长度按**码点**计，与 VM/解释器（Python len 语义）对齐。
    原生端 STR 的 [obj+8] 是 UTF-8 **字节**数，直接返回会让 len("你好") 得 6
    （而非 2）、len("a😀b") 得 6（而非 3）。此处对 TYPE_STR 改为统计非
    0x80..0xBF 的续位字节，即码点数；其余容器仍返回 [obj+8]（元素个数）。
    """
    em.label_here("fn:len")
    _emit_prologue(em, 1, 1)
    em.emit(b"\x48\x8B\x85\xF8\xFF\xFF\xFF")        # mov rax,[rbp-8]（局部0=实参）
    em.emit(b"\x48\x89\xC1")                        # mov rcx,rax
    em.lea_rip(2, "heap_base")                      # lea rdx,[heap_base]
    em.emit(b"\x48\x29\xD1")                        # sub rcx,rdx
    em.emit(b"\x48\x81\xF9" + struct.pack("<I", HEAP_SIZE))
    em.jcc_rel32(0x82, "len_isptr")                 # jb isptr
    em.emit(b"\x31\xC0")                            # xor eax,eax
    em.jcc_rel32(None, "len_done")                  # jmp done
    em.label_here("len_isptr")
    em.emit(b"\x4C\x8B\x00")                        # mov r8,[rax]（类型标签）
    em.emit(b"\x49\x83\xF8" + bytes([TYPE_STR]))    # cmp r8,TYPE_STR
    em.jcc_rel32(0x85, "len_notstr")                # jne：容器 → 元素数
    # --- 文本：统计码点（非续位字节）个数 ---
    em.emit(b"\x48\x8B\x48\x08")                    # mov rcx,[rax+8]（字节长度）
    em.lea_mem(9, 0, 16)                            # lea r9,[rax+16]（buf）
    em.emit(b"\x31\xD2")                            # xor edx,edx（i=0）
    em.emit(b"\x45\x31\xC0")                        # xor r8d,r8d（count=0）
    em.label_here("len_cp_loop")
    em.cmp_rr(2, 1)                                 # cmp rdx,rcx
    em.jcc_rel32(0x83, "len_cp_done")               # jae done
    em.emit(b"\x41\x0F\xB6\x44\x11\x00")            # movzx eax,byte [r9+rdx]
    em.emit(b"\x3C\x80")                            # cmp al,0x80
    em.jcc_rel32(0x82, "len_cp_count")              # jb <0x80 → 首字节
    em.emit(b"\x3C\xC0")                            # cmp al,0xC0
    em.jcc_rel32(0x83, "len_cp_count")              # jae >=0xC0 → 首字节
    em.jcc_rel32(None, "len_cp_next")               # 0x80..0xBF 续位 → 跳过
    em.label_here("len_cp_count")
    em.emit(b"\x41\x83\xC0\x01")                    # inc r8d
    em.label_here("len_cp_next")
    em.emit(b"\x48\xFF\xC2")                        # inc rdx
    em.jcc_rel32(None, "len_cp_loop")
    em.label_here("len_cp_done")
    em.mov_rr(0, 8)                                 # mov rax,r8（码点数）
    em.jcc_rel32(None, "len_done")
    em.label_here("len_notstr")
    em.emit(b"\x48\x8B\x40\x08")                    # mov rax,[rax+8]（容器元素数）
    em.label_here("len_done")
    em.push_rax()
    _emit_epilogue(em)


def _emit_utf8_width(em: _Emitter, out: int, tag: str):
    """rax = UTF-8 前导字节 → out = 该码点字节宽（1..4）。

    与 fn:list 的 ls_s_loop（按码点切分 list(文本)）同一套定宽规则，
    供字符串按码点下标复用。
    """
    ldone = f"u8w_{tag}"
    em.mov_r_imm32(out, 1)                            # 宽度=1（ASCII 默认）
    em.cmp_ri(0, 0xC0)
    em.jcc_rel32(0x82, ldone)                         # jb：单位元
    em.mov_r_imm32(out, 2)
    em.cmp_ri(0, 0xE0)
    em.jcc_rel32(0x82, ldone)
    em.mov_r_imm32(out, 3)
    em.cmp_ri(0, 0xF0)
    em.jcc_rel32(0x82, ldone)
    em.mov_r_imm32(out, 4)
    em.label_here(ldone)


def _emit_getitem(em: _Emitter, pfx: str):
    """下标读取核心：入参 rax=容器、rcx=下标，出参 rax=元素。

    与 vm.py:501 的 `c[idx]` 对齐：列表按下标、字符串按 **Unicode 码点**
    （砖块 19：此前按字节取单字节，"你好"[1] 返回半个汉字）、字典按键；
    其余类型返回 null。索引越界不做检查（沿用原生端既有的「越界静默」
    限制，返回 null 而非抛 IndexError）。
    """
    lstr = f"gi_str_{pfx}"
    ldict = f"gi_dict_{pfx}"
    ldone = f"gi_done_{pfx}"
    lscan = f"gi_cp_scan_{pfx}"
    lcont = f"gi_cp_cont_{pfx}"
    lhit = f"gi_cp_hit_{pfx}"
    loob = f"gi_cp_oob_{pfx}"
    em.emit(b"\x4C\x8B\x00")                        # mov r8,[rax]
    em.emit(b"\x49\x83\xF8" + bytes([TYPE_LIST]))  # cmp r8,TYPE_LIST
    em.jcc_rel32(0x84, f"gi_list_{pfx}")
    em.emit(b"\x49\x83\xF8" + bytes([TYPE_STR]))   # cmp r8,TYPE_STR
    em.jcc_rel32(0x84, lstr)
    em.emit(b"\x49\x83\xF8" + bytes([TYPE_DICT]))  # cmp r8,TYPE_DICT
    em.jcc_rel32(0x84, ldict)
    em.lea_rip(0, "null_obj")                      # 其他类型 → null
    em.jcc_rel32(None, ldone)
    em.label_here(f"gi_list_{pfx}")
    # 列表下标必须查界：此前直接 `mov rax,[rax+rcx*8+16]`，越界时读到的是
    # 对象头之后的相邻堆字节（[1,2][9] 静默返回 0），与文本/字典路径
    # 「越界返回 null」的既定约定不一致。同时要保留 Python 的负下标
    # （[1,2,3][-1] == 3），故先判符号再查界。
    loob_l = f"gi_list_oob_{pfx}"
    lneg_l = f"gi_list_neg_{pfx}"
    lok_l = f"gi_list_ok_{pfx}"
    em.emit(b"\x4C\x8B\x40\x08")                    # mov r8,[rax+8]（n）
    em.test_rr(1, 1)                                # test rcx,rcx
    em.jcc_rel32(0x88, lneg_l)                      # js   负下标
    em.cmp_rr(1, 8)                                 # cmp rcx,r8
    em.jcc_rel32(0x83, loob_l)                      # jae  rcx >= n → null
    em.emit(b"\x48\x8B\x44\xC8\x10")                # mov rax,[rax+rcx*8+16]
    em.jcc_rel32(None, ldone)
    # 负下标：rcx = -rcx 后改取 [n + rcx]，仍越界才返回 null
    em.label_here(lneg_l)
    em.emit(b"\x48\xF7\xD9")                        # neg rcx
    em.cmp_rr(1, 8)                                 # cmp rcx,r8
    em.jcc_rel32(0x86, lok_l)                       # jbe  合法（含 rcx == n，
    em.jcc_rel32(None, loob_l)                      #      即 a[-n] == a[0]）
    em.label_here(lok_l)
    em.mov_rr(9, 0)                                # mov r9,rax（基址）
    em.emit(b"\x4C\x89\xC0")                        # mov rax,r8（n）
    em.sub_rr(0, 1)                                 # sub rax,rcx → n-idx
    em.emit(b"\x48\xC1\xE0\x03")                    # shl rax,3
    em.emit(b"\x4C\x01\xC8")                        # add rax,r9
    em.emit(b"\x48\x8B\x40\x10")                    # mov rax,[rax+16]
    em.jcc_rel32(None, ldone)
    em.label_here(loob_l)
    em.lea_rip(0, "null_obj")
    em.jcc_rel32(None, ldone)
    em.label_here(lstr)
    # 砖块 19：文本下标按 **Unicode 码点**（此前按字节取单字节："你好"[1]
    # 会返回半个汉字、emoji 返回残字节）。扫到第 rcx 个 UTF-8 前导字节，按
    # 其宽度切出整个码点，复用 buf_to_str 建 str；定宽规则与 list(文本)
    # （fn:list 的 ls_str）一致。
    em.emit(b"\x48\x8D\x50\x10")                    # lea rdx,[rax+16]（buf）
    em.emit(b"\x4C\x8B\x48\x08")                    # mov r9,[rax+8]（字节长度）
    em.xor_rr32(10, 10)                      # xor r10d,r10d（i=0）
    em.xor_rr32(11, 11)                      # xor r11d,r11d（cp=0）
    em.label_here(lscan)
    em.cmp_rr(10, 9)                                # cmp r10,r9
    em.jcc_rel32(0x83, loob)                        # jae：扫过末尾 → 越界
    em.emit(b"\x41\x0F\xB6\x04\x12")                # movzx eax,byte [rdx+r10]
    em.and_ri(0, 0xC0)
    em.cmp_ri(0, 0x80)
    em.jcc_rel32(0x84, lcont)                       # je：续位字节 → 不计码点
    em.cmp_rr(1, 11)                                # cmp rcx,r11（目标码点序）
    em.jcc_rel32(0x84, lhit)                        # je：命中
    em.emit(b"\x41\xFF\xC3")                        # inc r11d（cp++）
    em.emit(b"\x41\x0F\xB6\x04\x12")                # movzx eax,byte [rdx+r10]
    _emit_utf8_width(em, 8, f"{pfx}_skip")
    em.add_rr(10, 8)                                # i += width
    em.jcc_rel32(None, lscan)
    em.label_here(lcont)
    em.emit(b"\x41\xFF\xC2")                        # inc r10d
    em.jcc_rel32(None, lscan)
    em.label_here(lhit)
    em.emit(b"\x41\x0F\xB6\x04\x12")                # movzx eax,byte [rdx+r10]
    _emit_utf8_width(em, 8, f"{pfx}_hit")
    em.emit(b"\x48\x89\xD7")                        # mov rdi,rdx
    em.add_rr(7, 10)                                # rdi = buf + i
    em.mov_rr(1, 8)                                 # rcx = width
    em.call_rel32("buf_to_str")                     # → rax=该码点 str
    em.jcc_rel32(None, ldone)
    em.label_here(loob)
    em.lea_rip(0, "null_obj")                       # 越界 → null（沿用静默限制）
    em.jcc_rel32(None, ldone)
    em.label_here(ldict)
    em.call_rel32("dict_get")                       # rax=字典,rcx=键
    em.label_here(ldone)


def _emit_slice(em: _Emitter):
    """build_slice 子程序：rax=容器、rcx=start、rdx=stop → rax=新对象。

    语义对齐 vm.py:504 的 `c[start:end]`（宿主 Python 切片）：
      - start/stop 为 null_obj（编译器对 `y[2:]` 省略的边界）时分别取 0/len；
      - 负下标相对 len 归一化，再钳到 [0, len]；
      - stop < start 时结果为空；
      - 容器为列表 → 新列表（浅拷贝元素）；字符串 → 新字符串（按字节切，
        与原生端既有的字符串按字节语义一致）；其他类型 → null_obj。
    只用栈帧槽位，不占用 r13/r14/r15，避免破坏调用者的被调用者保存寄存器。
    """
    em.label_here("build_slice")
    em.emit(b"\x55")                                # push rbp
    em.emit(b"\x48\x89\xE5")                        # mov rbp,rsp
    em.emit(b"\x48\x83\xEC\x40")                    # sub rsp,0x40
    em.emit(b"\x48\x89\x45\xF8")                    # mov [rbp-0x08],rax（容器）
    em.emit(b"\x48\x89\x4D\xF0")                    # mov [rbp-0x10],rcx（start）
    em.emit(b"\x48\x89\x55\xE8")                    # mov [rbp-0x18],rdx（stop）
    em.emit(b"\x48\x89\xC1")                        # mov rcx,rax
    em.lea_rip(2, "heap_base")                      # lea rdx,[heap_base]
    em.emit(b"\x48\x29\xD1")                        # sub rcx,rdx
    em.emit(b"\x48\x81\xF9" + struct.pack("<I", HEAP_SIZE))
    em.jcc_rel32(0x83, "bs_null")                   # jae：非堆指针 → null
    em.emit(b"\x48\x8B\x45\xF8")                    # mov rax,[rbp-0x08]
    em.emit(b"\x8B\x10")                            # mov edx,[rax]（类型）
    em.emit(b"\x83\xFA" + bytes([TYPE_LIST]))        # cmp edx,TYPE_LIST
    em.jcc_rel32(0x84, "bs_common")
    em.emit(b"\x83\xFA" + bytes([TYPE_STR]))         # cmp edx,TYPE_STR
    em.jcc_rel32(0x85, "bs_null")                   # 非序列类型 → null
    em.label_here("bs_common")
    em.emit(b"\x48\x8B\x45\xF8")                    # mov rax,[rbp-0x08]
    em.emit(b"\x48\x8B\x48\x08")                    # mov rcx,[rax+8]（len）
    em.emit(b"\x48\x89\x4D\xD8")                    # mov [rbp-0x28],rcx
    # ---- start 归一化 ----
    em.emit(b"\x48\x8B\x4D\xF0")                    # mov rcx,[rbp-0x10]
    em.lea_rip(0, "null_obj")                       # lea rax,[null_obj]
    em.emit(b"\x48\x39\xC8")                        # cmp rcx,rax
    em.jcc_rel32(0x84, "bs_s_null")                 # je：缺省 start
    em.emit(b"\x48\x85\xC9")                        # test rcx,rcx
    em.jcc_rel32(0x89, "bs_s_pos")                  # jns 非负
    em.emit(b"\x48\x03\x4D\xD8")                    # add rcx,[rbp-0x28]（+len）
    em.emit(b"\x48\x89\x4D\xF0")                    # mov [rbp-0x10],rcx
    em.jcc_rel32(None, "bs_s_clamp")
    em.label_here("bs_s_null")
    em.emit(b"\x31\xC9")                            # xor ecx,ecx
    em.emit(b"\x48\x89\x4D\xF0")                    # mov [rbp-0x10],rcx
    em.jcc_rel32(None, "bs_s_clamp")
    em.label_here("bs_s_pos")
    em.label_here("bs_s_clamp")
    em.emit(b"\x48\x8B\x4D\xF0")                    # mov rcx,[rbp-0x10]
    em.emit(b"\x48\x85\xC9")                        # test rcx,rcx
    em.jcc_rel32(0x89, "bs_s_chk")                  # jns ≥0
    em.emit(b"\x31\xC9")                            # xor ecx,ecx
    em.emit(b"\x48\x89\x4D\xF0")                    # mov [rbp-0x10],rcx
    em.label_here("bs_s_chk")
    em.emit(b"\x48\x8B\x4D\xF0")                    # mov rcx,[rbp-0x10]
    em.emit(b"\x48\x8B\x45\xD8")                    # mov rax,[rbp-0x28]（len）
    em.emit(b"\x48\x39\xC1")                        # cmp rcx,rax（ModRM reg=rax,rm=rcx → rcx-rax）
    em.jcc_rel32(0x8E, "bs_s_ok")                   # jle start ≤ len
    em.emit(b"\x48\x89\x45\xF0")                    # mov [rbp-0x10],rax（钳到 len）
    em.label_here("bs_s_ok")
    # ---- stop 归一化 ----
    em.emit(b"\x48\x8B\x4D\xE8")                    # mov rcx,[rbp-0x18]
    em.lea_rip(0, "null_obj")                       # lea rax,[null_obj]
    em.emit(b"\x48\x39\xC8")                        # cmp rcx,rax
    em.jcc_rel32(0x84, "bs_e_null")                 # je：缺省 stop = len
    em.emit(b"\x48\x85\xC9")                        # test rcx,rcx
    em.jcc_rel32(0x89, "bs_e_pos")                  # jns 非负
    em.emit(b"\x48\x03\x4D\xD8")                    # add rcx,[rbp-0x28]（+len）
    em.emit(b"\x48\x89\x4D\xE8")                    # mov [rbp-0x18],rcx
    em.jcc_rel32(None, "bs_e_clamp")
    em.label_here("bs_e_null")
    em.emit(b"\x48\x8B\x45\xD8")                    # mov rax,[rbp-0x28]
    em.emit(b"\x48\x89\x45\xE8")                    # mov [rbp-0x18],rax
    em.jcc_rel32(None, "bs_e_clamp")
    em.label_here("bs_e_pos")
    em.label_here("bs_e_clamp")
    em.emit(b"\x48\x8B\x4D\xE8")                    # mov rcx,[rbp-0x18]
    em.emit(b"\x48\x85\xC9")                        # test rcx,rcx
    em.jcc_rel32(0x89, "bs_e_chk")                  # jns ≥0
    em.emit(b"\x31\xC9")                            # xor ecx,ecx
    em.emit(b"\x48\x89\x4D\xE8")                    # mov [rbp-0x18],rcx
    em.label_here("bs_e_chk")
    em.emit(b"\x48\x8B\x4D\xE8")                    # mov rcx,[rbp-0x18]
    em.emit(b"\x48\x8B\x45\xD8")                    # mov rax,[rbp-0x28]
    em.emit(b"\x48\x39\xC1")                        # cmp rcx,rax（ModRM reg=rax,rm=rcx → rcx-rax）
    em.jcc_rel32(0x8E, "bs_e_ok")                   # jle stop ≤ len
    em.emit(b"\x48\x89\x45\xE8")                    # mov [rbp-0x18],rax（钳到 len）
    em.label_here("bs_e_ok")
    # ---- 长度 = stop - start（负数归零）----
    em.emit(b"\x48\x8B\x45\xE8")                    # mov rax,[rbp-0x18]
    em.emit(b"\x48\x2B\x45\xF0")                    # sub rax,[rbp-0x10]
    em.jcc_rel32(0x89, "bs_cnt")                    # jns 非负
    em.emit(b"\x31\xC0")                            # xor eax,eax
    em.label_here("bs_cnt")
    em.emit(b"\x48\x89\x45\xE0")                    # mov [rbp-0x20],rax（n）
    em.emit(b"\x48\x8B\x45\xF8")                    # mov rax,[rbp-0x08]
    em.emit(b"\x83\x38" + bytes([TYPE_LIST]))        # cmp dword [rax],TYPE_LIST
    em.jcc_rel32(0x84, "bs_list")                   # je 列表分支
    # ---- 字符串：按字节拷贝 ----
    em.emit(b"\x48\x8B\x7D\xE0")                    # mov rdi,[rbp-0x20]（n）
    em.emit(b"\x48\x83\xC7\x10")                    # add rdi,16
    em.call_rel32("alloc")
    em.emit(b"\xC7\x00" + struct.pack("<I", TYPE_STR))
    em.emit(b"\x48\x8B\x4D\xE0")                    # mov rcx,[rbp-0x20]
    em.emit(b"\x48\x89\x48\x08")                    # mov [rax+8],rcx
    em.emit(b"\x48\x8D\x78\x10")                    # lea rdi,[rax+16]
    em.emit(b"\x48\x8B\x75\xF8")                    # mov rsi,[rbp-0x08]
    em.emit(b"\x48\x8B\x55\xF0")                    # mov rdx,[rbp-0x10]
    em.emit(b"\x48\x01\xD6")                        # add rsi,rdx（+start）
    em.emit(b"\x48\x83\xC6\x10")                    # add rsi,16（+头部）
    em.emit(b"\x48\x8B\x4D\xE0")                    # mov rcx,[rbp-0x20]
    em.emit(b"\xF3\xA4")                            # rep movsb
    em.jcc_rel32(None, "bs_done")
    # ---- 列表：逐元素浅拷贝 ----
    em.label_here("bs_list")
    em.emit(b"\x48\x8B\x7D\xE0")                    # mov rdi,[rbp-0x20]（n）
    em.emit(b"\x48\xC1\xE7\x03")                    # shl rdi,3（n×8）
    em.emit(b"\x48\x83\xC7\x10")                    # add rdi,16
    em.call_rel32("alloc")
    em.emit(b"\xC7\x00" + struct.pack("<I", TYPE_LIST))
    em.emit(b"\x48\x8B\x4D\xE0")                    # mov rcx,[rbp-0x20]
    em.emit(b"\x48\x89\x48\x08")                    # mov [rax+8],rcx
    em.emit(b"\x48\x8D\x78\x10")                    # lea rdi,[rax+16]
    em.emit(b"\x48\x8B\x75\xF8")                    # mov rsi,[rbp-0x08]
    em.emit(b"\x48\x8B\x55\xF0")                    # mov rdx,[rbp-0x10]
    em.emit(b"\x48\xC1\xE2\x03")                    # shl rdx,3（start×8）
    em.emit(b"\x48\x01\xD6")                        # add rsi,rdx
    em.emit(b"\x48\x83\xC6\x10")                    # add rsi,16
    em.emit(b"\x48\x8B\x4D\xE0")                    # mov rcx,[rbp-0x20]
    em.emit(b"\xF3\x48\xA5")                        # rep movsq
    em.label_here("bs_done")
    em.jcc_rel32(None, "bs_ret")
    em.label_here("bs_null")
    em.lea_rip(0, "null_obj")                       # lea rax,[null_obj]
    em.label_here("bs_ret")
    em.emit(b"\xC9")                                # leave
    em.emit(b"\xC3")                                # ret


def _emit_in_rt(em: _Emitter):
    """seq_contains 子程序：rax=needle、rcx=container -> eax=1/0。

    对齐 vm._BINOPS 的 `a in b`（宿主 Python 成员判断）：
      - 容器为列表 → 逐元素 val_eq（整数比值、字符串比内容）；
      - 容器为字典 → 按键 val_eq（与 dict_get 的线性扫描同一形态）；
      - 容器为字符串 → 字节子串查找。原生端字符串本就按字节存，故
        needle 也必须是字符串对象；空串恒命中，与 Python 一致。
      - 其他容器类型 → 0（VM 侧会抛 TypeError，属既有偏差）。

    寄存器纪律：val_eq 会破坏 rax/rcx/r8/r9/rsi/rdi，故循环游标与剩余
    计数一律落栈帧槽位；不用 rbx/r12-r15，保持被调用者保存约定。
    """
    em.label_here("seq_contains")
    em.emit(b"\x55")                                # push rbp
    em.emit(b"\x48\x89\xE5")                        # mov rbp,rsp
    em.emit(b"\x48\x83\xEC\x50")                    # sub rsp,0x50（局部槽用到 [rbp-0x40]）
    em.emit(b"\x48\x89\x45\xF8")                    # mov [rbp-0x08],rax（needle）
    em.emit(b"\x48\x89\x4D\xF0")                    # mov [rbp-0x10],rcx（容器）
    em.emit(b"\x48\x89\xC8")                        # mov rax,rcx
    em.lea_rip(2, "heap_base")                      # lea rdx,[heap_base]
    em.emit(b"\x48\x29\xD0")                        # sub rax,rdx
    em.emit(b"\x48\x81\xF8" + struct.pack("<I", HEAP_SIZE))
    em.jcc_rel32(0x83, "sc_false")                  # jae：非堆指针 → 假
    em.emit(b"\x48\x8B\x4D\xF0")                    # mov rcx,[rbp-0x10]
    em.emit(b"\x8B\x11")                            # mov edx,[rcx]（类型）
    em.emit(b"\x83\xFA" + bytes([TYPE_LIST]))       # cmp edx,TYPE_LIST
    em.jcc_rel32(0x84, "sc_list")
    em.emit(b"\x83\xFA" + bytes([TYPE_DICT]))       # cmp edx,TYPE_DICT
    em.jcc_rel32(0x84, "sc_dict")
    em.emit(b"\x83\xFA" + bytes([TYPE_STR]))        # cmp edx,TYPE_STR
    em.jcc_rel32(0x84, "sc_str")
    em.jcc_rel32(None, "sc_false")                  # 其他类型 → 假

    # ---- 列表：线性扫描 ----
    em.label_here("sc_list")
    em.emit(b"\x48\x8B\x51\x08")                    # mov rdx,[rcx+8]（count）
    em.emit(b"\x48\x8D\x41\x10")                    # lea rax,[rcx+16]（首元素）
    em.emit(b"\x48\x89\x45\xE8")                    # mov [rbp-0x18],rax（游标）
    em.emit(b"\x48\x89\x55\xE0")                    # mov [rbp-0x20],rdx（剩余）
    em.label_here("sc_ll")
    em.emit(b"\x48\x8B\x55\xE0")                    # mov rdx,[rbp-0x20]
    em.emit(b"\x48\x85\xD2")                        # test rdx,rdx
    em.jcc_rel32(0x84, "sc_false")                  # jz：扫完未命中
    em.emit(b"\x48\x8B\x45\xE8")                    # mov rax,[rbp-0x18]
    em.emit(b"\x48\x8B\x08")                        # mov rcx,[rax]（元素）
    em.emit(b"\x48\x8B\x45\xF8")                    # mov rax,[rbp-0x08]（needle）
    em.call_rel32("val_eq")
    em.emit(b"\x48\x85\xC0")                        # test rax,rax
    em.jcc_rel32(0x85, "sc_true")                   # jnz：命中
    em.emit(b"\x48\x83\x45\xE8\x08")                # add qword [rbp-0x18],8（元素步长 8）
    em.emit(b"\x48\xFF\x4D\xE0")                    # dec qword [rbp-0x20]
    em.jcc_rel32(None, "sc_ll")

    # ---- 字典：按 key 扫描 ----
    em.label_here("sc_dict")
    em.emit(b"\x48\x8B\x51\x08")                    # mov rdx,[rcx+8]（count）
    em.emit(b"\x48\x8D\x41\x10")                    # lea rax,[rcx+16]（首 pair）
    em.emit(b"\x48\x89\x45\xE8")                    # mov [rbp-0x18],rax（游标）
    em.emit(b"\x48\x89\x55\xE0")                    # mov [rbp-0x20],rdx（剩余）
    em.label_here("sc_dl")
    em.emit(b"\x48\x8B\x55\xE0")                    # mov rdx,[rbp-0x20]
    em.emit(b"\x48\x85\xD2")                        # test rdx,rdx
    em.jcc_rel32(0x84, "sc_false")                  # jz：扫完未命中
    em.emit(b"\x48\x8B\x45\xE8")                    # mov rax,[rbp-0x18]
    em.emit(b"\x48\x8B\x08")                        # mov rcx,[rax]（key）
    em.emit(b"\x48\x8B\x45\xF8")                    # mov rax,[rbp-0x08]（needle）
    em.call_rel32("val_eq")
    em.emit(b"\x48\x85\xC0")                        # test rax,rax
    em.jcc_rel32(0x85, "sc_true")                   # jnz：命中
    em.emit(b"\x48\x83\x45\xE8\x10")                # add qword [rbp-0x18],16
    em.emit(b"\x48\xFF\x4D\xE0")                    # dec qword [rbp-0x20]
    em.jcc_rel32(None, "sc_dl")

    # ---- 字符串：字节子串查找 ----
    em.label_here("sc_str")
    em.emit(b"\x48\x8B\x45\xF8")                    # mov rax,[rbp-0x08]（needle）
    em.lea_rip(2, "heap_base")                      # lea rdx,[heap_base]
    em.emit(b"\x48\x29\xD0")                        # sub rax,rdx
    em.emit(b"\x48\x81\xF8" + struct.pack("<I", HEAP_SIZE))
    em.jcc_rel32(0x83, "sc_false")                  # jae：整数 needle → 假
    em.emit(b"\x48\x8B\x45\xF8")                    # mov rax,[rbp-0x08]
    em.emit(b"\x83\x38" + bytes([TYPE_STR]))        # cmp dword [rax],TYPE_STR
    em.jcc_rel32(0x85, "sc_false")                  # jne：非字符串 needle
    em.emit(b"\x48\x8B\x50\x08")                    # mov rdx,[rax+8]（nlen）
    em.emit(b"\x48\x89\x55\xC0")                    # mov [rbp-0x40],rdx
    em.emit(b"\x48\x8D\x40\x10")                    # lea rax,[rax+16]
    em.emit(b"\x48\x89\x45\xC8")                    # mov [rbp-0x38],rax（needle 字节）
    em.emit(b"\x48\x8B\x4D\xF0")                    # mov rcx,[rbp-0x10]
    em.emit(b"\x48\x8B\x51\x08")                    # mov rdx,[rcx+8]（hlen）
    em.emit(b"\x48\x89\x55\xD0")                    # mov [rbp-0x30],rdx
    em.emit(b"\x48\x8D\x41\x10")                    # lea rax,[rcx+16]
    em.emit(b"\x48\x89\x45\xD8")                    # mov [rbp-0x28],rax（hay 字节）
    em.emit(b"\x48\x8B\x55\xC0")                    # mov rdx,[rbp-0x40]（nlen）
    em.emit(b"\x48\x85\xD2")                        # test rdx,rdx
    em.jcc_rel32(0x84, "sc_true")                   # jz：空串恒命中
    em.emit(b"\x48\x3B\x55\xD0")                    # cmp rdx,[rbp-0x30]（nlen vs hlen）
    em.jcc_rel32(0x87, "sc_false")                  # ja：needle 更长 → 假
    # 最后一个合法起点 limit = hlen - nlen 放在易失寄存器 r10，游标 i 放 r11：
    # 两者都是 Win64 易失寄存器，无需保存，也不占用栈帧槽（避免与调用方
    # shadow space 及 val_eq 的栈使用冲突）。
    em.emit(b"\x48\x8B\x45\xD0")                    # mov rax,[rbp-0x30]（hlen）
    em.emit(b"\x48\x2B\x45\xC0")                    # sub rax,[rbp-0x40]（-nlen）
    em.emit(b"\x49\x89\xC2")                        # mov r10,rax（limit）
    em.emit(b"\x31\xD2")                            # xor edx,edx（i=0）
    em.emit(b"\x49\x89\xD3")                        # mov r11,rdx（i）
    em.label_here("sc_sl")
    em.emit(b"\x4D\x39\xD3")                        # cmp r11,r10（i vs limit）
    em.jcc_rel32(0x87, "sc_false")                  # ja：起点用尽 → 假
    em.emit(b"\x48\x8B\x75\xC8")                    # mov rsi,[rbp-0x38]（needle）
    em.emit(b"\x48\x8B\x7D\xD8")                    # mov rdi,[rbp-0x28]（hay）
    em.emit(b"\x4C\x01\xDF")                        # add rdi,r11（hay+i）
    # 逐字节比较剩余长度。用与 str_eq 相同的显式循环，而不用 rep cmpsb：
    # 后者同时依赖 DF 必须为 0 与 rcx 取值，且是本文件里唯一从未成功执行过
    # 的指令；显式循环与之保持一致，也便于 se_loop 式地逐字节推进。
    em.emit(b"\x48\x8B\x4D\xC0")                    # mov rcx,[rbp-0x40]（nlen）
    em.emit(b"\x49\x89\xC9")                        # mov r9,rcx（剩余字节数）
    em.label_here("sc_scmp")
    em.emit(b"\x4D\x85\xC9")                        # test r9,r9
    em.jcc_rel32(0x84, "sc_true")                   # jz：全部字节相等 → 命中
    em.emit(b"\x8A\x06")                            # mov al,[rsi]
    em.emit(b"\x3A\x07")                            # cmp al,[rdi]
    em.jcc_rel32(0x85, "sc_snext")                  # jne：不匹配，换起点
    em.emit(b"\x48\xFF\xC6")                        # inc rsi
    em.emit(b"\x48\xFF\xC7")                        # inc rdi
    em.emit(b"\x49\xFF\xC9")                        # dec r9
    em.jcc_rel32(None, "sc_scmp")
    em.label_here("sc_snext")
    em.emit(b"\x49\xFF\xC3")                        # inc r11（i++）
    em.jcc_rel32(None, "sc_sl")

    em.label_here("sc_true")
    em.emit(b"\xB8\x01\x00\x00\x00")               # mov eax,1
    em.emit(b"\xC9")                                # leave
    em.emit(b"\xC3")                                # ret
    em.label_here("sc_false")
    em.emit(b"\x31\xC0")                            # xor eax,eax
    em.emit(b"\xC9")                                # leave
    em.emit(b"\xC3")                                # ret


def _emit_builtin_closure_init(em: _Emitter, names: list):
    """为 arity>1 的内建各分配一条闭包记录，指针写入数据槽 bclo:{name}。

    必须在 main_entry 之前、heap_ptr 初始化之后执行（依赖 alloc）。
    """
    for nm in names:
        em.emit(b"\x48\xC7\xC7\x20\x00\x00\x00")       # mov rdi,32
        em.call_rel32("alloc")
        em.emit(b"\x48\xC7\x00" + struct.pack("<I", TYPE_CLOSURE))
        em.lea_rip(2, f"fn:{nm}")                      # lea rdx,[fn:{nm}]
        em.emit(b"\x48\x89\x50\x08")                    # mov [rax+8],rdx（fn）
        em.emit(b"\x31\xD2")                            # xor edx,edx（env=null）
        em.emit(b"\x48\x89\x50\x10")                    # mov [rax+16],rdx
        em.emit(b"\x48\xC7\x40\x18" + struct.pack("<i", _BUILTIN_ARITY[nm]))
        em.emit(b"\x48\x89\x05")                        # mov [rip+bclo:...],rax
        em.rel32_to(f"bclo:{nm}")


def _emit_builtin_get(em: _Emitter):
    """内建 get(xs)(i) → xs[i]：2 参柯里化函数，编译器以两次 CALL 1 驱动。

    `for … in …` 的元素读取正是 `get(xs)(i)`（compiler.py:605），因此原生端
    必须提供 get，否则任何 for 循环都无法编译。
    """
    em.label_here("fn:get")
    _emit_prologue(em, 2, 2)
    em.emit(b"\x48\x8B\x85\xF0\xFF\xFF\xFF")        # mov rax,[rbp-16]（局部0=容器）
    em.emit(b"\x48\x8B\x8D\xF8\xFF\xFF\xFF")        # mov rcx,[rbp-8]（局部1=下标）
    _emit_getitem(em, "get")
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_error(em: _Emitter):
    """内建 错误(msg)：抛出 msg（等价 VM 的 OP.RAISE(str(msg))）。"""
    em.label_here("fn:错误")
    _emit_prologue(em, 1, 1)
    em.mov_rd_mem(0, 5, -8)                         # mov rax,[rbp-8]（arg0）
    em.call_rel32("raise_rt")                       # 不返回
    em.emit(b"\x0F\x0B")                            # ud2


def _emit_builtin_guard(em: _Emitter):
    """内建 调用捕获(thunk)(args)：try/catch 脱糖所用的受保护调用。

    入栈一条处理器记录后调用 thunk(*args)；正常返回 ["__正常__", 值]，
    异常由 raise_rt 恢复现场后跳到 调用捕获:land 返回 ["__异常__", 消息]。
    记录布局 [prev][rsp][rbp][r12][r13]（40 字节），存于 .data 的处理器栈。
    """
    em.label_here("fn:调用捕获")
    _emit_prologue(em, 2, 8)
    # 推入处理器记录
    em.load_rip_to(0, "hstack_ptr")                 # mov rax,[rip+hstack_ptr]
    em.load_rip_to(1, "handler_top")                # mov rcx,[rip+handler_top]
    em.mov_mem_r(0, 0, 1)                           # mov [rax+0],rcx（prev）
    em.lea_mem(1, 0, HSTACK_REC)                    # lea rcx,[rax+40]
    em.store_rip_from("hstack_ptr", 1)              # mov [rip+hstack_ptr],rcx
    em.store_rip_from("handler_top", 0)             # mov [rip+handler_top],rax
    em.mov_mem_r(0, 8, 4)                           # mov [rax+8],rsp
    em.mov_mem_r(0, 16, 5)                          # mov [rax+16],rbp
    em.mov_mem_r(0, 24, 12)                         # mov [rax+24],r12
    em.mov_mem_r(0, 32, 13)                         # mov [rax+32],r13
    # 操作数栈：[thunk, args...]
    em.mov_rd_mem(0, 5, -64)                        # mov rax,[rbp-64]（thunk）
    em.push_rax()
    em.mov_rd_mem(10, 5, -56)                       # mov r10,[rbp-56]（args）
    em.xor_rr32(9, 9)                               # xor r9d,r9d（n=0）
    em.test_rr(10, 10)                              # test r10,r10
    em.jcc_rel32(0x84, "cg_done")                   # jz done
    em.lea_rip(2, "heap_base")                      # lea rdx,[heap_base]
    em.mov_rr(1, 10)                                # mov rcx,r10
    em.sub_rr(1, 2)                                 # sub rcx,rdx
    em.emit(b"\x48\x81\xF9" + struct.pack("<I", HEAP_SIZE))
    em.jcc_rel32(0x83, "cg_done")                   # jae done（非堆指针）
    em.emit(b"\x49\x83\x3A" + bytes([TYPE_LIST]))   # cmp qword [r10],TYPE_LIST
    em.jcc_rel32(0x85, "cg_done")                   # jne done
    em.mov_rd_mem(9, 10, 8)                         # mov r9,[r10+8]（n）
    em.xor_rr32(8, 8)                               # xor r8d,r8d
    em.label_here("cg_loop")
    em.cmp_rr(8, 9)                                 # cmp r8,r9
    em.jcc_rel32(0x83, "cg_done")                   # jae done
    em.mov_rd_mem(0, 10, 16, index=8, scale=8)      # mov rax,[r10+r8*8+16]
    em.push_rax()
    em.inc_r(8)                                     # inc r8
    em.jcc_rel32(None, "cg_loop")
    em.label_here("cg_done")
    # apply_rt(rdi=函数, rsi=实参基址, rdx=N)
    em.mov_rr(6, 12)                                # mov rsi,r12
    em.mov_rr(0, 9)                                 # mov rax,r9
    em.shl_ri(0, 3)                                 # shl rax,3
    em.sub_rr(6, 0)                                 # sub rsi,rax
    em.mov_rd_mem(7, 6, -8)                         # mov rdi,[rsi-8]（函数值）
    em.mov_rr(2, 9)                                 # mov rdx,r9
    em.call_rel32("apply_rt")
    em.emit(b"\x49\x89\x44\x24\xF0")                # mov [r12-16],rax
    em.emit(b"\x49\x83\xEC\x08")                    # sub r12,8
    # 正常返回：弹出处理器并标记 ["__正常__", 值]
    em.load_rip_to(1, "handler_top")                # mov rcx,[rip+handler_top]
    em.mov_rd_mem(2, 1, 0)                          # mov rdx,[rcx+0]
    em.store_rip_from("handler_top", 2)             # mov [rip+handler_top],rdx
    em.mov_rr(2, 1)                                 # mov rdx,rcx（释放本记录：栈顶回到 record）
    em.store_rip_from("hstack_ptr", 2)              # mov [rip+hstack_ptr],rdx
    em.call_rel32("rt_tag_normal")
    em.push_rax()
    _emit_epilogue(em)
    # 异常落地点：raise_rt 已恢复 rsp/rbp/r12/r13 并弹栈
    em.label_here("调用捕获:land")
    em.load_rip_to(0, "raise_msg")                  # mov rax,[rip+raise_msg]
    em.call_rel32("rt_tag_error")
    em.push_rax()
    _emit_epilogue(em)


def _emit_exception_runtime(em: _Emitter, guard: bool):
    """异常运行时：value_to_str / int_to_str / 标签构造 / raise_rt。

    raise_rt(rax=值) 永不返回：有处理器则长跳转回 调用捕获:land；否则把
    str(值) 写到标准输出并以退出码 1 结束进程（未捕获异常）。
    """
    # ---- int_to_str（rax=整数 → rax=字符串对象）----
    em.label_here("int_to_str")
    em.emit(b"\x55")                                # push rbp
    em.emit(b"\x48\x89\xE5")                        # mov rbp,rsp
    em.emit(b"\x48\x83\xEC\x40")                    # sub rsp,0x40
    em.xor_rr32(10, 10)                             # xor r10d,r10d（符号）
    em.test_rr(0, 0)                                # test rax,rax
    em.jcc_rel32(0x89, "its_nonneg")                # jns
    em.mov_r_imm32(10, 1)                           # mov r10d,1
    em.emit(b"\x48\xF7\xD8")                        # neg rax
    em.label_here("its_nonneg")
    em.lea_rip(6, "numbuf")                         # lea rsi,[numbuf]
    em.emit(b"\x48\x8D\x7E\x3E")                    # lea rdi,[rsi+62]
    em.label_here("its_loop")
    em.emit(b"\x31\xD2")                            # xor edx,edx
    em.emit(b"\xB9\x0A\x00\x00\x00")                # mov ecx,10
    em.emit(b"\x48\xF7\xF1")                        # div rcx
    em.emit(b"\x80\xC2\x30")                        # add dl,'0'
    em.emit(b"\x48\xFF\xCF")                        # dec rdi
    em.emit(b"\x88\x17")                            # mov [rdi],dl
    em.test_rr(0, 0)
    em.jcc_rel32(0x85, "its_loop")                  # jnz
    em.test_rr(10, 10)                              # test r10d,r10d
    em.jcc_rel32(0x84, "its_nosign")                # jz
    em.emit(b"\x48\xFF\xCF")                        # dec rdi
    em.emit(b"\xC6\x07\x2D")                        # mov byte[rdi],'-'
    em.label_here("its_nosign")
    em.lea_mem(8, 6, 62)                            # lea r8,[rsi+62]
    em.sub_rr(8, 7)                                 # sub r8,rdi（长度）
    em.emit(b"\x57")                                # push rdi（起点）
    em.emit(b"\x41\x50")                            # push r8（长度）
    em.mov_rr(7, 8)                                 # mov rdi,r8
    em.emit(b"\x48\x83\xC7\x10")                    # add rdi,16
    em.call_rel32("alloc")
    em.emit(b"\x48\xC7\x00" + struct.pack("<I", TYPE_STR))
    em.emit(b"\x41\x58")                            # pop r8（长度）
    em.emit(b"\x4C\x89\x40\x08")                    # mov [rax+8],r8
    em.emit(b"\x5E")                                # pop rsi（起点）
    em.lea_mem(7, 0, 16)                            # lea rdi,[rax+16]
    em.mov_rr(1, 8)                                 # mov rcx,r8
    em.emit(b"\xF3\xA4")                            # rep movsb
    em.emit(b"\x48\x89\xEC")                        # mov rsp,rbp
    em.emit(b"\x5D")                                # pop rbp
    em.emit(b"\xC3")                                # ret

    # ---- value_to_str（rax=值 → rax=字符串对象）----
    em.label_here("value_to_str")
    em.mov_rr(1, 0)                                 # mov rcx,rax
    em.lea_rip(2, "heap_base")                      # lea rdx,[heap_base]
    em.sub_rr(1, 2)                                 # sub rcx,rdx
    em.emit(b"\x48\x81\xF9" + struct.pack("<I", HEAP_SIZE))
    em.jcc_rel32(0x82, "vvs_ptr")                   # jb ptr
    em.jcc_rel32(None, "int_to_str")                # 整数 → 十进制串
    em.label_here("vvs_ptr")
    em.mov_rd_mem(1, 0, 0)                          # mov rcx,[rax]
    em.emit(b"\x48\x83\xF9" + bytes([TYPE_STR]))    # cmp rcx,TYPE_STR
    em.jcc_rel32(0x84, "vvs_ret")
    em.emit(b"\x48\x83\xF9" + bytes([TYPE_BOOL]))   # cmp rcx,TYPE_BOOL
    em.jcc_rel32(0x84, "vvs_ret")                   # True/False 载荷即字符串
    em.emit(b"\x48\x83\xF9" + bytes([TYPE_NULL]))   # cmp rcx,TYPE_NULL
    em.jcc_rel32(0x84, "vvs_ret")                   # None 载荷即字符串
    em.emit(b"\x48\x83\xF9" + bytes([TYPE_FLOAT]))  # cmp rcx,TYPE_FLOAT
    em.jcc_rel32(0x84, "vvs_float")                 # je float
    em.label_here("vvs_ret")
    em.emit(b"\xC3")                                # ret（其他类型原样返回）
    em.label_here("vvs_float")
    em.emit(b"\xE9")                                # jmp str_float
    em.rel32_to("str_float")

    # ---- rt_tag_normal / rt_tag_error：构造 2 元列表 ----
    for lbl, tag in (("rt_tag_normal", "tag_normal"),
                     ("rt_tag_error", "tag_error")):
        em.label_here(lbl)
        em.mov_rr(1, 0)                             # mov rcx,rax（值）
        em.mov_r_imm32(7, 32)                       # mov edi,32
        em.call_rel32("alloc")
        em.emit(b"\x48\xC7\x00" + struct.pack("<I", TYPE_LIST))
        em.emit(b"\x48\xC7\x40\x08\x02\x00\x00\x00")  # mov qword[rax+8],2
        em.lea_rip(2, tag)                          # lea rdx,[tag]
        em.emit(b"\x48\x89\x50\x10")                # mov [rax+16],rdx
        em.emit(b"\x48\x89\x48\x18")                # mov [rax+24],rcx
        em.emit(b"\xC3")                            # ret

    # ---- raise_rt（rax=值；永不返回）----
    em.label_here("raise_rt")
    em.emit(b"\x48\x83\xEC\x08")                    # sub rsp,8（入口 rsp≡8）
    em.call_rel32("value_to_str")                   # rax = 消息串
    em.store_rip_from("raise_msg", 0)               # mov [rip+raise_msg],rax
    em.load_rip_to(0, "handler_top")                # mov rax,[rip+handler_top]
    em.test_rr(0, 0)
    em.jcc_rel32(0x84, "ra_uncaught")               # jz 无处理器
    if guard:
        em.mov_rr(1, 0)                             # mov rcx,rax（记录）
        em.mov_rd_mem(2, 1, 0)                      # mov rdx,[rcx+0]（prev）
        em.store_rip_from("handler_top", 2)         # mov [rip+handler_top],rdx
        em.mov_rr(2, 1)                             # mov rdx,rcx（释放本记录）
        em.store_rip_from("hstack_ptr", 2)          # mov [rip+hstack_ptr],rdx
        em.mov_rd_mem(4, 1, 8)                      # mov rsp,[rcx+8]
        em.mov_rd_mem(5, 1, 16)                     # mov rbp,[rcx+16]
        em.mov_rd_mem(12, 1, 24)                    # mov r12,[rcx+24]
        em.mov_rd_mem(13, 1, 32)                    # mov r13,[rcx+32]
        em.jcc_rel32(None, "调用捕获:land")
    else:
        em.emit(b"\x0F\x0B")                        # ud2（无 调用捕获 时不可达）
    em.label_here("ra_uncaught")
    em.load_rip_to(0, "raise_msg")                  # mov rax,[rip+raise_msg]
    em.call_rel32("print_uncaught")                 # 消息 + CRLF 写 stderr
    em.mov_r_imm32(1, 1)                            # mov ecx,1
    em.call_rip_indirect("api_ExitProcess")
    em.emit(b"\x0F\x0B")                            # ud2

    # ---- print_uncaught（rax=消息串 → 写 STDERR + CRLF，不返回值）----
    em.label_here("print_uncaught")
    em.emit(b"\x55")                                # push rbp
    em.emit(b"\x48\x89\xE5")                        # mov rbp,rsp
    em.emit(b"\x48\x83\xEC\x40")                    # sub rsp,0x40
    em.emit(b"\x48\x89\x44\x24\x28")                # mov [rsp+0x28],rax
    em.emit(b"\xB9\xF4\xFF\xFF\xFF")                # mov ecx,-12 (STD_ERROR_HANDLE)
    em.call_rip_indirect("api_GetStdHandle")
    em.emit(b"\x48\x89\xC1")                        # mov rcx,rax
    em.emit(b"\x4C\x8B\x54\x24\x28")                # mov r10,[rsp+0x28]
    em.emit(b"\x49\x8D\x52\x10")                    # lea rdx,[r10+16]
    em.emit(b"\x4D\x8B\x42\x08")                    # mov r8,[r10+8]
    em.lea_rip(9, "written")                        # lea r9,[written]
    em.emit(b"\x48\xC7\x44\x24\x20\x00\x00\x00\x00")  # mov qword[rsp+0x20],0
    em.call_rip_indirect("api_WriteFile")
    em.emit(b"\xB9\xF4\xFF\xFF\xFF")                # mov ecx,-12
    em.call_rip_indirect("api_GetStdHandle")
    em.emit(b"\x48\x89\xC1")                        # mov rcx,rax
    em.lea_rip(2, "crlf")                           # lea rdx,[crlf]
    em.emit(b"\x41\xB8\x02\x00\x00\x00")            # mov r8d,2
    em.lea_rip(9, "written")                        # lea r9,[written]
    em.emit(b"\x48\xC7\x44\x24\x20\x00\x00\x00\x00")  # mov qword[rsp+0x20],0
    em.call_rip_indirect("api_WriteFile")
    em.emit(b"\x48\x89\xEC")                        # mov rsp,rbp
    em.emit(b"\x5D")                                # pop rbp
    em.emit(b"\xC3")                                # ret


def _emit_rax_to_bool(em: _Emitter, tag, idx):
    """把 rax 中的 0/1 变为布尔对象（宿主语义：比较/not 结果是真值对象）。"""
    lf = f"b2f_{tag}_{idx}"
    ld = f"b2d_{tag}_{idx}"
    em.emit(b"\x48\x85\xC0")                        # test rax,rax
    em.jcc_rel32(0x84, lf)                          # jz → False
    em.lea_rip(0, "bool_true")
    em.jcc_rel32(None, ld)
    em.label_here(lf)
    em.lea_rip(0, "bool_false")
    em.label_here(ld)


def _emit_builtin_print(em: _Emitter):
    """内建 输出(x)：按类型打印并换行，返回原值（宿主 vm._make_output，可链式）。"""
    em.label_here("fn:输出")
    _emit_prologue(em, 1, 2)                         # nlocals=2 → 实参落在 [rbp-16]
    em.emit(b"\x48\x8B\x85\xF0\xFF\xFF\xFF")        # mov rax,[rbp-16]（局部1=实参）
    em.call_rel32("print_value")
    em.call_rel32("print_nl")
    em.emit(b"\x48\x8B\x85\xF0\xFF\xFF\xFF")        # mov rax,[rbp-16]（返回原值）
    em.push_rax()
    _emit_epilogue(em)


# ---------------------------------------------------------------- 砖块 16
# 阶段一：数值 + 转换核心（数学函数 / 类型名 / int·float·str·bool）。
#
# 调用约定沿用 M3V：arity=1 的内建以纯文本地址（fn:name）暴露，apply_rt 的
# ar_plain 分支直接 tail-jmp；arity>1 的内建以闭包记录暴露并按 arity 柯里化。
# 函数体经 _emit_prologue 把栈上实参搬到局部槽：1 参 → [rbp-8]，
# 2 参 → [rbp-16]（第 0 个）/[rbp-8]（第 1 个）。结果 push_rax 回操作数栈。
#
# 语义对齐 vm.py / mathlib.py：数学函数取自 CRT（与宿主 Python 底层同为
# libm，逐位一致）；round 用 rint 以复刻 Python 的 round-half-even；取整类
# 与 int() 返回裸整数（Python Int），abs 保持入参类型。


def _dbl_bits(x: float) -> int:
    return struct.unpack("<Q", struct.pack("<d", x))[0]


# 一元数学函数（double→double，结果恒浮点）：name → CRT 入口名。
_CRT_FLOAT_UNARY = {
    "sin": "sin", "cos": "cos", "tan": "tan",
    "asin": "asin", "acos": "acos", "atan": "atan",
    "sinh": "sinh", "cosh": "cosh", "tanh": "tanh",
    "exp": "exp", "log": "log", "ln": "log", "log10": "log10", "log2": "log2",
    # sqrt 作为可调用内建对齐 mathlib 的 math.sqrt（恒浮点），与一元 ^ 的
    # _builtin_sqrt（整数完全平方回退整数）不同。
    "sqrt": "sqrt",
}

# 取整类（float→int；int 输入原样返回）：name → CRT 入口名。
# round 用 rint（默认 round-half-even）以对齐 Python round，而非 CRT round。
_CRT_INT_ROUND = {"floor": "floor", "ceil": "ceil", "trunc": "trunc",
                  "round": "rint"}

# type_of（英文）/ typeof（中文）→ 类型名静态字符串标签。
_TYPEOF_EN = {
    "bool": "tname_Bool", "int": "tname_Int", "float": "tname_Float",
    "str": "tname_String", "list": "tname_List", "dict": "tname_Dict",
    "func": "tname_Function", "null": "tname_Null", "unknown": "tname_Unknown",
}
_TYPEOF_ZH = {
    "bool": "tz_布尔", "int": "tz_整数", "float": "tz_浮点",
    "str": "tz_文本", "list": "tz_列表", "dict": "tz_字典",
    "func": "tz_函数", "null": "tz_空", "unknown": "tz_函数",
}
# 类型名/字面量文本静态串：[标签] → 内容。
_TYPE_NAME_STRINGS = {
    "tname_Bool": "Bool", "tname_Int": "Int", "tname_Float": "Float",
    "tname_String": "String", "tname_List": "List", "tname_Dict": "Dict",
    "tname_Function": "Function", "tname_Null": "Null",
    "tname_Unknown": "Unknown",
    "tz_布尔": "布尔", "tz_整数": "整数", "tz_浮点": "浮点", "tz_文本": "文本",
    "tz_列表": "列表", "tz_字典": "字典", "tz_函数": "函数", "tz_空": "空",
    "sob_True": "True", "sob_False": "False", "sob_None": "None",
}


def _emit_builtin_math_float(em: _Emitter, name: str, crt: str):
    """一元数学内建 name(x) → 浮点：CRT double(x) 装箱。"""
    em.label_here(f"fn:{name}")
    _emit_prologue(em, 1, 1)
    em.mov_rd_mem(0, 5, -8)                         # mov rax,[rbp-8]（实参）
    em.call_rel32("as_double")                      # xmm0=arg（int 亦转 double）
    em.call_rip_indirect(f"crt_{crt}")              # 外部 CRT 数学函数
    em.call_rel32("box_float")
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_math_round(em: _Emitter, name: str, crt: str):
    """取整内建 name(x)：浮点 → CRT 取整后截断为裸整数；整数原样返回。"""
    l_int = f"mr_{name}_int"
    em.label_here(f"fn:{name}")
    _emit_prologue(em, 1, 1)
    em.mov_rd_mem(0, 5, -8)
    em.call_rel32("is_float")
    em.emit(b"\x85\xC0")                            # test eax,eax
    em.jcc_rel32(0x84, l_int)                       # jz：整数原样
    em.mov_rd_mem(0, 5, -8)
    em.movsd_load(0, 0, 16)                         # movsd xmm0,[rax+16]
    em.call_rip_indirect(f"crt_{crt}")
    em.cvttsd2si(0, 0)                              # rax=截断取整
    em.push_rax()
    _emit_epilogue(em)
    em.label_here(l_int)
    em.mov_rd_mem(0, 5, -8)
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_math_scale(em: _Emitter, name: str, factor: float):
    """角度换算 name(x) = x * factor（math.radians/degrees），结果恒浮点。"""
    em.label_here(f"fn:{name}")
    _emit_prologue(em, 1, 1)
    em.mov_rd_mem(0, 5, -8)
    em.call_rel32("as_double")
    em.mov_r_imm64(2, _dbl_bits(factor))
    em.movq_xmm_r(1, 2)
    em.mulsd(0, 1)
    em.call_rel32("box_float")
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_abs(em: _Emitter):
    """abs(x)：整数取绝对值（裸整数）；浮点清符号位（保持浮点类型）。"""
    l_int, l_done = "abs_int", "abs_done"
    em.label_here("fn:abs")
    _emit_prologue(em, 1, 1)
    em.mov_rd_mem(0, 5, -8)
    em.call_rel32("is_float")
    em.emit(b"\x85\xC0")
    em.jcc_rel32(0x84, l_int)
    em.mov_rd_mem(0, 5, -8)
    em.movsd_load(0, 0, 16)
    em.movq_r_xmm(0, 0)                             # rax=bits
    em.shl_ri(0, 1)
    em.shr_ri(0, 1)                                 # 清符号位
    em.movq_xmm_r(0, 0)
    em.call_rel32("box_float")
    em.push_rax()
    _emit_epilogue(em)
    em.label_here(l_int)
    em.mov_rd_mem(0, 5, -8)
    em.emit(b"\x48\x85\xC0")                        # test rax,rax
    em.jcc_rel32(0x89, l_done)                      # jns：已非负
    em.emit(b"\x48\xF7\xD8")                        # neg rax
    em.label_here(l_done)
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_sign(em: _Emitter):
    """sign(x)：x>0→1，x<0→-1，x==0 或 NaN→0（对齐 mathlib._sign）。"""
    l_int = "sgn_int"
    l_zero, l_pos, l_neg, l_done = "sgn_zero", "sgn_pos", "sgn_neg", "sgn_done"
    em.label_here("fn:sign")
    _emit_prologue(em, 1, 1)
    em.mov_rd_mem(0, 5, -8)
    em.call_rel32("is_float")
    em.emit(b"\x85\xC0")
    em.jcc_rel32(0x84, l_int)
    em.mov_rd_mem(0, 5, -8)
    em.movsd_load(0, 0, 16)
    em.emit(b"\x66\x0F\xEF\xC9")                    # pxor xmm1,xmm1（0.0）
    em.ucomisd(0, 1)
    em.jcc_rel32(0x8A, l_zero)                      # jp：NaN → 0
    em.jcc_rel32(0x87, l_pos)                       # ja：> 0
    em.jcc_rel32(0x82, l_neg)                       # jb：< 0
    em.jcc_rel32(None, l_zero)
    em.label_here(l_int)
    em.mov_rd_mem(0, 5, -8)
    em.emit(b"\x48\x85\xC0")                        # test rax,rax
    em.jcc_rel32(0x8F, l_pos)                       # jg
    em.jcc_rel32(0x8C, l_neg)                       # jl
    em.label_here(l_zero)
    em.xor_rr32(0, 0)
    em.jcc_rel32(None, l_done)
    em.label_here(l_pos)
    em.mov_r_imm32(0, 1)
    em.jcc_rel32(None, l_done)
    em.label_here(l_neg)
    em.mov_rax_imm64(-1)
    em.label_here(l_done)
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_int(em: _Emitter, name: str):
    """int(x)/_to_int(x)：浮点向零截断；整数原样；Bool→1/0。其余→null。"""
    l_other = f"toint_{name}_other"
    l_false = f"toint_{name}_false"
    l_unsup = f"toint_{name}_unsup"
    l_done = f"toint_{name}_done"
    em.label_here(f"fn:{name}")
    _emit_prologue(em, 1, 1)
    em.mov_rd_mem(0, 5, -8)
    em.call_rel32("is_float")
    em.emit(b"\x85\xC0")
    em.jcc_rel32(0x84, l_other)
    em.mov_rd_mem(0, 5, -8)
    em.movsd_load(0, 0, 16)
    em.cvttsd2si(0, 0)                              # 截断向零（Python int(float)）
    em.jcc_rel32(None, l_done)
    em.label_here(l_other)
    em.mov_rd_mem(0, 5, -8)
    em.mov_rr(2, 0)
    em.lea_rip(1, "heap_base")
    em.sub_rr(2, 1)
    em.cmp_ri(2, HEAP_SIZE)
    em.jcc_rel32(0x83, l_done)                      # jae：裸整数 → 原样
    em.mov_rd_mem(2, 0, 0)                          # rdx=[rax]（类型）
    em.cmp_ri(2, TYPE_BOOL)
    em.jcc_rel32(0x85, l_unsup)                     # jne：非 Bool 指针 → 暂不支持
    em.lea_rip(1, "bool_true")
    em.cmp_rr(0, 1)
    em.jcc_rel32(0x85, l_false)
    em.mov_r_imm32(0, 1)
    em.jcc_rel32(None, l_done)
    em.label_here(l_false)
    em.xor_rr32(0, 0)
    em.jcc_rel32(None, l_done)
    em.label_here(l_unsup)
    em.lea_rip(0, "null_obj")
    em.label_here(l_done)
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_float(em: _Emitter, name: str):
    """float(x)/_to_float(x)：浮点原样；整数/布尔转 double；其余→null。"""
    l_other = f"toflt_{name}_other"
    l_int = f"toflt_{name}_int"
    l_zero = f"toflt_{name}_zero"
    l_unsup = f"toflt_{name}_unsup"
    l_done = f"toflt_{name}_done"
    em.label_here(f"fn:{name}")
    _emit_prologue(em, 1, 1)
    em.mov_rd_mem(0, 5, -8)
    em.call_rel32("is_float")
    em.emit(b"\x85\xC0")
    em.jcc_rel32(0x84, l_other)
    em.mov_rd_mem(0, 5, -8)                         # 已浮点 → 原样返回
    em.jcc_rel32(None, l_done)
    em.label_here(l_other)
    em.mov_rd_mem(0, 5, -8)
    em.mov_rr(2, 0)
    em.lea_rip(1, "heap_base")
    em.sub_rr(2, 1)
    em.cmp_ri(2, HEAP_SIZE)
    em.jcc_rel32(0x83, l_int)                       # jae：裸整数
    em.mov_rd_mem(2, 0, 0)
    em.cmp_ri(2, TYPE_BOOL)
    em.jcc_rel32(0x85, l_unsup)                     # jne：非 Bool 指针 → 暂不支持
    em.lea_rip(1, "bool_true")
    em.cmp_rr(0, 1)
    em.jcc_rel32(0x85, l_zero)
    em.mov_r_imm32(0, 1)
    em.jcc_rel32(None, l_int)
    em.label_here(l_zero)
    em.xor_rr32(0, 0)
    em.label_here(l_int)
    em.cvtsi2sd(0, 0)                               # xmm0=(double)rax
    em.call_rel32("box_float")
    em.jcc_rel32(None, l_done)
    em.label_here(l_unsup)
    em.lea_rip(0, "null_obj")
    em.label_here(l_done)
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_bool(em: _Emitter):
    """bool(x)：按 Python 真值语义返回布尔对象（复用 truthy）。"""
    l_false = "boolobj_false"
    l_done = "boolobj_done"
    em.label_here("fn:bool")
    _emit_prologue(em, 1, 1)
    em.mov_rd_mem(0, 5, -8)
    em.call_rel32("truthy")                         # ZF=1 ⟺ 假值
    em.jcc_rel32(0x84, l_false)
    em.lea_rip(0, "bool_true")
    em.jcc_rel32(None, l_done)
    em.label_here(l_false)
    em.lea_rip(0, "bool_false")
    em.label_here(l_done)
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_str(em: _Emitter):
    """str(x)：文本原样；整数→int_to_str；浮点→str_float；Bool/Null→常量串；
    列表/字典→按 repr 规则两遍渲染到新分配的 STR（对齐 CPython / VM）。
    """
    l_int = "tostr_int"
    l_float = "tostr_float"
    l_bool = "tostr_bool"
    l_bool_false = "tostr_bool_false"
    l_null = "tostr_null"
    l_container = "tostr_container"
    l_unsup = "tostr_unsup"
    l_done = "tostr_done"
    em.label_here("fn:str")
    _emit_prologue(em, 1, 1)
    em.mov_rd_mem(0, 5, -8)
    em.mov_rr(2, 0)
    em.lea_rip(1, "heap_base")
    em.sub_rr(2, 1)
    em.cmp_ri(2, HEAP_SIZE)
    em.jcc_rel32(0x83, l_int)                       # jae：裸整数
    em.mov_rd_mem(2, 0, 0)                          # rdx=类型
    em.cmp_ri(2, TYPE_STR)
    em.jcc_rel32(0x84, l_done)                      # 文本 → 原样
    em.cmp_ri(2, TYPE_FLOAT)
    em.jcc_rel32(0x84, l_float)
    em.cmp_ri(2, TYPE_BOOL)
    em.jcc_rel32(0x84, l_bool)
    em.cmp_ri(2, TYPE_NULL)
    em.jcc_rel32(0x84, l_null)
    em.cmp_ri(2, TYPE_LIST)
    em.jcc_rel32(0x84, l_container)
    em.cmp_ri(2, TYPE_DICT)
    em.jcc_rel32(0x84, l_container)
    em.jcc_rel32(None, l_unsup)
    em.label_here(l_float)
    em.call_rel32("str_float")                      # rax=float obj → str
    em.jcc_rel32(None, l_done)
    em.label_here(l_bool)
    em.lea_rip(1, "bool_true")
    em.cmp_rr(0, 1)
    em.jcc_rel32(0x85, l_bool_false)
    em.lea_rip(0, "sob_True")
    em.jcc_rel32(None, l_done)
    em.label_here(l_bool_false)
    em.lea_rip(0, "sob_False")
    em.jcc_rel32(None, l_done)
    em.label_here(l_null)
    em.lea_rip(0, "sob_None")
    em.jcc_rel32(None, l_done)
    em.label_here(l_int)
    em.call_rel32("int_to_str")                     # rax=裸整数 → str
    em.jcc_rel32(None, l_done)
    em.label_here(l_container)
    # 两遍渲染：先 out_mode=1 计数，分配精确 STR，再 out_mode=2 填充。
    # 容器与结果对象存入帧局部（被 GC 保守扫描为根）；非移动 GC 下 out_buf_ptr 稳定。
    em.mov_mem_r(5, -8, 0)                          # [rbp-8]=容器对象
    em.mov_r_imm32(1, 1)
    em.store_rip_from("out_mode", 1)
    em.xor_rr32(1, 1)
    em.store_rip_from("out_count", 1)
    em.mov_rd_mem(0, 5, -8)
    em.call_rel32("print_value")                    # 计数遍
    em.load_rip_to(1, "out_count")
    em.emit(b"\x48\x83\xC1\x10")                    # add rcx,16（对象总大小）
    em.mov_rr(7, 1)                                 # rdi=size
    em.call_rel32("alloc")
    em.emit(b"\x48\xC7\x00" + struct.pack("<I", TYPE_STR))
    em.load_rip_to(1, "out_count")
    em.mov_mem_r(0, 8, 1)                           # [rax+8]=len
    em.lea_mem(2, 0, 16)                            # rdx=payload
    em.store_rip_from("out_buf_ptr", 2)
    em.mov_mem_r(5, -24, 0)                         # [rbp-24]=结果对象
    em.mov_r_imm32(1, 2)
    em.store_rip_from("out_mode", 1)
    em.mov_rd_mem(0, 5, -8)
    em.call_rel32("print_value")                    # 填充遍
    em.xor_rr32(1, 1)
    em.store_rip_from("out_mode", 1)                # 恢复 stdout
    em.mov_rd_mem(0, 5, -24)
    em.jcc_rel32(None, l_done)
    em.label_here(l_unsup)
    em.lea_rip(0, "null_obj")
    em.label_here(l_done)
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_type_name(em: _Emitter, name: str, m: dict):
    """type_of/typeof：按对象类型标签返回对应名称字符串。"""
    l_int = f"tn_{name}_int"
    l_done = f"tn_{name}_done"
    em.label_here(f"fn:{name}")
    _emit_prologue(em, 1, 1)
    em.mov_rd_mem(0, 5, -8)
    em.mov_rr(2, 0)
    em.lea_rip(1, "heap_base")
    em.sub_rr(2, 1)
    em.cmp_ri(2, HEAP_SIZE)
    em.jcc_rel32(0x83, l_int)                       # jae：裸整数
    em.mov_rd_mem(2, 0, 0)                          # rdx=类型
    for ty, lab in ((TYPE_FLOAT, m["float"]), (TYPE_BOOL, m["bool"]),
                    (TYPE_NULL, m["null"]), (TYPE_STR, m["str"]),
                    (TYPE_LIST, m["list"]), (TYPE_DICT, m["dict"]),
                    (TYPE_CLOSURE, m["func"]), (TYPE_PARTIAL, m["func"])):
        l_skip = f"tn_{name}_s{ty}"
        em.cmp_ri(2, ty)
        em.jcc_rel32(0x85, l_skip)                  # jne skip
        em.lea_rip(0, lab)
        em.jcc_rel32(None, l_done)
        em.label_here(l_skip)
    em.lea_rip(0, m["unknown"])
    em.jcc_rel32(None, l_done)
    em.label_here(l_int)
    em.lea_rip(0, m["int"])
    em.label_here(l_done)
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_pow(em: _Emitter):
    """pow(base)(exp) → math.pow（恒浮点，复用 f_pow）。"""
    em.label_here("fn:pow")
    _emit_prologue(em, 2, 2)
    em.mov_rd_mem(0, 5, -16)                        # base
    em.mov_rd_mem(1, 5, -8)                         # exp
    em.call_rel32("f_pow")
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_bin2_crt(em: _Emitter, name: str, crt: str):
    """二元数学内建 name(a)(b) → CRT double(a,b)（atan2/hypot，恒浮点）。"""
    em.label_here(f"fn:{name}")
    _emit_prologue(em, 2, 2)
    em.mov_rd_mem(0, 5, -16)                        # 第 0 个实参
    em.mov_rd_mem(1, 5, -8)                         # 第 1 个实参
    em.call_rel32("bin_to_xmm2")                    # xmm0=a, xmm1=b
    em.call_rip_indirect(f"crt_{crt}")
    em.call_rel32("box_float")
    em.push_rax()
    _emit_epilogue(em)


# ---- 砖块 16 阶段二：序列 / 字典原语 ----

def _emit_builtin_slice(em: _Emitter):
    """slice(container)(start)(stop) → build_slice（越界钳制）。"""
    em.label_here("fn:slice")
    _emit_prologue(em, 3, 3)
    em.mov_rd_mem(0, 5, -24)                        # container
    em.mov_rd_mem(1, 5, -16)                        # start
    em.mov_rd_mem(2, 5, -8)                         # stop
    em.call_rel32("build_slice")
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_append(em: _Emitter):
    """append(xs)(elem) → 新列表（浅拷贝 + 追加）。"""
    em.label_here("fn:append")
    _emit_prologue(em, 2, 2)
    em.mov_rd_mem(0, 5, -16)                        # xs
    em.mov_rd_mem(1, 5, -8)                         # elem
    em.call_rel32("list_append")
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_mut_set_at(em: _Emitter):
    """mut_set_at(lst)(idx)(val)：原地改列表；越界/类型错 → null。"""
    l_bad = "msa_bad"
    l_done = "msa_done"
    em.label_here("fn:mut_set_at")
    _emit_prologue(em, 3, 3)
    em.mov_rd_mem(0, 5, -24)                        # lst
    em.mov_rr(1, 0)
    em.lea_rip(2, "heap_base")
    em.sub_rr(1, 2)
    em.cmp_ri(1, HEAP_SIZE)
    em.jcc_rel32(0x83, l_bad)                       # 非指针
    em.mov_rd_mem(1, 0, 0)                          # 类型
    em.cmp_ri(1, TYPE_LIST)
    em.jcc_rel32(0x85, l_bad)                       # 非列表
    em.mov_rd_mem(1, 5, -16)                        # idx
    em.emit(b"\x48\x85\xC9")                        # test rcx,rcx
    em.jcc_rel32(0x88, l_bad)                       # idx < 0
    em.mov_rd_mem(2, 0, 8)                          # len
    em.cmp_rr(1, 2)                                 # cmp idx,len
    em.jcc_rel32(0x8D, l_bad)                       # idx >= len
    em.mov_rd_mem(2, 5, -8)                         # val
    em.emit(b"\x48\x89\x54\xC8\x10")                # mov [rax+rcx*8+16],rdx
    em.jcc_rel32(None, l_done)
    em.label_here(l_bad)
    em.lea_rip(0, "null_obj")
    em.label_here(l_done)
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_dict_keys(em: _Emitter):
    em.label_here("fn:_dict_keys")
    _emit_prologue(em, 1, 1)
    em.mov_rd_mem(0, 5, -8)
    em.call_rel32("dict_keys")
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_dict_values(em: _Emitter):
    em.label_here("fn:_dict_values")
    _emit_prologue(em, 1, 1)
    em.mov_rd_mem(0, 5, -8)
    em.call_rel32("dict_values")
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_dict_has(em: _Emitter):
    """_dict_has(d)(k) → 布尔对象。"""
    l_false = "dhas_false"
    l_done = "dhas_done"
    em.label_here("fn:_dict_has")
    _emit_prologue(em, 2, 2)
    em.mov_rd_mem(0, 5, -16)                        # dict
    em.mov_rd_mem(1, 5, -8)                         # key
    em.call_rel32("dict_has")
    em.emit(b"\x85\xC0")                            # test eax,eax
    em.jcc_rel32(0x84, l_false)
    em.lea_rip(0, "bool_true")
    em.jcc_rel32(None, l_done)
    em.label_here(l_false)
    em.lea_rip(0, "bool_false")
    em.label_here(l_done)
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_make_set(em: _Emitter):
    """构造集合(form)(variables)(elements) → 去重保序列表。

    对齐 vm.py _builtin_make_set：elements 去重且保序；form 与 variables 不参与
    结果（VM 侧「集合/set」两分支返回同一 seen）。语法糖 {} / {1,2,3} / {x | cond}
    均由编译器归约到本内建。
    """
    em.label_here("fn:构造集合")
    _emit_prologue(em, 3, 3)
    em.mov_rd_mem(0, 5, -8)                          # elements
    em.call_rel32("list_dedup")
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_dict_put(em: _Emitter):
    em.label_here("fn:_dict_put")
    _emit_prologue(em, 3, 3)
    em.mov_rd_mem(0, 5, -24)                        # dict
    em.mov_rd_mem(1, 5, -16)                        # key
    em.mov_rd_mem(2, 5, -8)                         # val
    em.call_rel32("dict_put")
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_dict_remove(em: _Emitter):
    em.label_here("fn:_dict_remove")
    _emit_prologue(em, 2, 2)
    em.mov_rd_mem(0, 5, -16)                        # dict
    em.mov_rd_mem(1, 5, -8)                         # key
    em.call_rel32("dict_remove")
    em.push_rax()
    _emit_epilogue(em)


# ---- 砖块 16 阶段三：基础原语 / 序列构造 ----

def _emit_builtin_ord(em: _Emitter):
    """ord(s) → 首个 Unicode 码点（按 UTF-8 解码）；非文本/空串 → null。"""
    em.label_here("fn:ord")
    _emit_prologue(em, 1, 1)
    em.mov_rd_mem(0, 5, -8)                         # rax=s
    em.mov_rr(1, 0)
    em.lea_rip(2, "heap_base")
    em.sub_rr(1, 2)
    em.cmp_ri(1, HEAP_SIZE)
    em.jcc_rel32(0x83, "ord_fail")                  # 非指针
    em.mov_rd_mem(1, 0, 0)
    em.cmp_ri(1, TYPE_STR)
    em.jcc_rel32(0x85, "ord_fail")                  # 非文本
    em.mov_rd_mem(2, 0, 8)
    em.emit(b"\x48\x85\xD2")                        # test rdx,rdx（len==0）
    em.jcc_rel32(0x84, "ord_fail")
    em.emit(b"\x0F\xB6\x48\x10")                    # movzx ecx,byte [rax+16] b0
    em.cmp_ri(1, 0x80)
    em.jcc_rel32(0x82, "ord_b1")                    # jb → 单字节
    em.cmp_ri(1, 0xE0)
    em.jcc_rel32(0x82, "ord_b2")
    em.cmp_ri(1, 0xF0)
    em.jcc_rel32(0x82, "ord_b3")
    # 4 字节
    em.mov_rr(8, 1)
    em.and_ri(8, 0x07)
    em.shl_ri(8, 18)
    em.emit(b"\x0F\xB6\x50\x11")                    # movzx edx,byte [rax+17]
    em.emit(b"\x83\xE2\x3F")                        # and edx,0x3F
    em.shl_ri(2, 12)
    em.add_rr(8, 2)
    em.emit(b"\x0F\xB6\x50\x12")
    em.emit(b"\x83\xE2\x3F")
    em.shl_ri(2, 6)
    em.add_rr(8, 2)
    em.emit(b"\x0F\xB6\x50\x13")
    em.emit(b"\x83\xE2\x3F")
    em.add_rr(8, 2)
    em.mov_rr(0, 8)
    em.jcc_rel32(None, "ord_ret")
    em.label_here("ord_b3")
    em.mov_rr(8, 1)
    em.and_ri(8, 0x0F)
    em.shl_ri(8, 12)
    em.emit(b"\x0F\xB6\x50\x11")
    em.emit(b"\x83\xE2\x3F")
    em.shl_ri(2, 6)
    em.add_rr(8, 2)
    em.emit(b"\x0F\xB6\x50\x12")
    em.emit(b"\x83\xE2\x3F")
    em.add_rr(8, 2)
    em.mov_rr(0, 8)
    em.jcc_rel32(None, "ord_ret")
    em.label_here("ord_b2")
    em.mov_rr(8, 1)
    em.and_ri(8, 0x1F)
    em.shl_ri(8, 6)
    em.emit(b"\x0F\xB6\x50\x11")
    em.emit(b"\x83\xE2\x3F")
    em.add_rr(8, 2)
    em.mov_rr(0, 8)
    em.jcc_rel32(None, "ord_ret")
    em.label_here("ord_b1")
    em.mov_rr(0, 1)
    em.jcc_rel32(None, "ord_ret")
    em.label_here("ord_fail")
    em.lea_rip(0, "null_obj")
    em.label_here("ord_ret")
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_chr(em: _Emitter):
    """chr(n) → 码点 n 的 UTF-8 文本（负值视为 0）。"""
    em.label_here("fn:chr")
    _emit_prologue(em, 1, 2)                        # 参数[rbp-16]，缓冲[rbp-8]
    em.mov_rd_mem(0, 5, -16)                        # rax=n
    em.emit(b"\x48\x85\xC0")                        # test rax,rax
    em.jcc_rel32(0x89, "chr_nn")                    # jns
    em.emit(b"\x31\xC0")                            # xor eax,eax
    em.label_here("chr_nn")
    em.cmp_ri(0, 0x80)
    em.jcc_rel32(0x82, "chr_1")                     # jb 单字节
    em.cmp_ri(0, 0x800)
    em.jcc_rel32(0x82, "chr_2")
    em.cmp_ri(0, 0x10000)
    em.jcc_rel32(0x82, "chr_3")
    # 4 字节：11110xxx 10xxxxxx 10xxxxxx 10xxxxxx
    em.mov_rr(1, 0)
    em.shr_ri(1, 18)
    em.emit(b"\x80\xC9\xF0")                        # or cl,0xF0
    em.emit(b"\x88\x4D\xF8")                        # mov [rbp-8],cl
    em.mov_rr(1, 0)
    em.shr_ri(1, 12)
    em.emit(b"\x80\xE1\x3F\x80\xC9\x80")            # and cl,0x3F; or cl,0x80
    em.emit(b"\x88\x4D\xF9")                        # [rbp-7],cl
    em.mov_rr(1, 0)
    em.shr_ri(1, 6)
    em.emit(b"\x80\xE1\x3F\x80\xC9\x80")
    em.emit(b"\x88\x4D\xFA")                        # [rbp-6],cl
    em.mov_rr(1, 0)
    em.emit(b"\x80\xE1\x3F\x80\xC9\x80")
    em.emit(b"\x88\x4D\xFB")                        # [rbp-5],cl
    em.emit(b"\x48\x8D\x7D\xF8")                    # lea rdi,[rbp-8]
    em.emit(b"\xB9\x04\x00\x00\x00")                # mov ecx,4
    em.jcc_rel32(None, "chr_go")
    em.label_here("chr_3")
    em.mov_rr(1, 0)
    em.shr_ri(1, 12)
    em.emit(b"\x80\xC9\xE0")                        # or cl,0xE0
    em.emit(b"\x88\x4D\xF8")
    em.mov_rr(1, 0)
    em.shr_ri(1, 6)
    em.emit(b"\x80\xE1\x3F\x80\xC9\x80")
    em.emit(b"\x88\x4D\xF9")
    em.mov_rr(1, 0)
    em.emit(b"\x80\xE1\x3F\x80\xC9\x80")
    em.emit(b"\x88\x4D\xFA")
    em.emit(b"\x48\x8D\x7D\xF8")
    em.emit(b"\xB9\x03\x00\x00\x00")
    em.jcc_rel32(None, "chr_go")
    em.label_here("chr_2")
    em.mov_rr(1, 0)
    em.shr_ri(1, 6)
    em.emit(b"\x80\xC9\xC0")                        # or cl,0xC0
    em.emit(b"\x88\x4D\xF8")
    em.mov_rr(1, 0)
    em.emit(b"\x80\xE1\x3F\x80\xC9\x80")
    em.emit(b"\x88\x4D\xF9")
    em.emit(b"\x48\x8D\x7D\xF8")
    em.emit(b"\xB9\x02\x00\x00\x00")
    em.jcc_rel32(None, "chr_go")
    em.label_here("chr_1")
    em.emit(b"\x88\x45\xF8")                        # mov [rbp-8],al
    em.emit(b"\x48\x8D\x7D\xF8")
    em.emit(b"\xB9\x01\x00\x00\x00")
    em.label_here("chr_go")
    em.call_rel32("buf_to_str")
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_list(em: _Emitter):
    """list(x)：文本→按 Unicode 码点切分的文本列表；列表→浅拷贝；字典→键列表；其余→null。"""
    em.label_here("fn:list")
    _emit_prologue(em, 1, 5)                        # 参数[rbp-40]
    em.mov_rd_mem(0, 5, -40)                        # rax=x
    em.mov_rr(1, 0)
    em.lea_rip(2, "heap_base")
    em.sub_rr(1, 2)
    em.cmp_ri(1, HEAP_SIZE)
    em.jcc_rel32(0x83, "ls_fail")                   # 非指针
    em.mov_rd_mem(1, 0, 0)                          # 类型
    em.cmp_ri(1, TYPE_LIST)
    em.jcc_rel32(0x84, "ls_copy")
    em.cmp_ri(1, TYPE_STR)
    em.jcc_rel32(0x84, "ls_str")
    em.cmp_ri(1, TYPE_DICT)
    em.jcc_rel32(0x84, "ls_dict")
    em.label_here("ls_fail")
    em.lea_rip(0, "null_obj")
    em.push_rax()
    _emit_epilogue(em)
    # ---- 列表浅拷贝 ----
    em.label_here("ls_copy")
    em.mov_rd_mem(1, 0, 8)                          # n
    em.mov_mem_r(5, -24, 1)                         # [rbp-24]=n
    em.mov_rr(7, 1)
    em.shl_ri(7, 3)
    em.add_ri(7, 16)
    em.call_rel32("alloc")
    em.mov_mem_r(5, -32, 0)                         # [rbp-32]=base
    em.emit(b"\xC7\x00" + struct.pack("<I", TYPE_LIST))
    em.mov_rd_mem(1, 5, -24)
    em.mov_mem_r(0, 8, 1)                           # [base+8]=n
    em.mov_rd_mem(7, 5, -32)
    em.add_ri(7, 16)                                # rdi=dst
    em.mov_rd_mem(6, 5, -40)
    em.add_ri(6, 16)                                # rsi=src
    em.mov_rd_mem(1, 5, -24)                        # rcx=n
    em.emit(b"\xF3\x48\xA5")                        # rep movsq
    em.mov_rd_mem(0, 5, -32)
    em.push_rax()
    _emit_epilogue(em)
    # ---- 文本 → 按 Unicode 码点切分的文本列表（对齐 VM：UTF-8 前导字节定宽）----
    em.label_here("ls_str")
    em.emit(b"\x48\xC7\x45\xF0\x00\x00\x00\x00")    # [rbp-16]=i=0
    em.emit(b"\x48\xC7\x45\xE8\x00\x00\x00\x00")    # [rbp-24]=n_cp=0
    em.label_here("ls_count_loop")
    em.mov_rd_mem(1, 5, -16)                        # rcx=i
    em.mov_rd_mem(2, 5, -40)                        # rdx=s
    em.mov_rd_mem(9, 2, 8)                          # r9=len=[s+8]
    em.cmp_rr(1, 9)
    em.jcc_rel32(0x83, "ls_count_done")             # jae：扫描完
    em.emit(b"\x0F\xB6\x44\x0A\x10")                # movzx eax,byte [rdx+rcx+16]
    em.and_ri(0, 0xC0)
    em.cmp_ri(0, 0x80)
    em.jcc_rel32(0x84, "ls_count_skip")             # ZF：续接字节，不计码点
    em.emit(b"\x48\xFF\x45\xE8")                    # inc qword [rbp-24]
    em.label_here("ls_count_skip")
    em.emit(b"\x48\xFF\x45\xF0")                    # inc qword [rbp-16]
    em.jcc_rel32(None, "ls_count_loop")
    em.label_here("ls_count_done")
    em.mov_rd_mem(1, 5, -24)                        # n_cp
    em.mov_rr(7, 1)
    em.shl_ri(7, 3)
    em.add_ri(7, 16)
    em.call_rel32("alloc")
    em.mov_mem_r(5, -32, 0)                         # base
    em.emit(b"\xC7\x00" + struct.pack("<I", TYPE_LIST))
    em.mov_rd_mem(1, 5, -24)
    em.mov_mem_r(0, 8, 1)                           # [base+8]=n_cp
    em.emit(b"\x48\xC7\x45\xF0\x00\x00\x00\x00")    # [rbp-16]=i=0
    em.emit(b"\x48\xC7\x45\xF8\x00\x00\x00\x00")    # [rbp-8]=j=0
    em.label_here("ls_s_loop")
    em.mov_rd_mem(1, 5, -16)                        # rcx=i
    em.mov_rd_mem(2, 5, -40)                        # rdx=s
    em.mov_rd_mem(9, 2, 8)                          # r9=len
    em.cmp_rr(1, 9)
    em.jcc_rel32(0x83, "ls_s_done")                 # jae：完成
    em.emit(b"\x0F\xB6\x44\x0A\x10")                # movzx eax,byte [rdx+rcx+16]
    em.mov_r_imm32(8, 1)                            # 宽度=1（ASCII 默认）
    em.cmp_ri(0, 0xC0)
    em.jcc_rel32(0x82, "ls_w_ready")                # jb：单位元
    em.mov_r_imm32(8, 2)
    em.cmp_ri(0, 0xE0)
    em.jcc_rel32(0x82, "ls_w_ready")
    em.mov_r_imm32(8, 3)
    em.cmp_ri(0, 0xF0)
    em.jcc_rel32(0x82, "ls_w_ready")
    em.mov_r_imm32(8, 4)
    em.label_here("ls_w_ready")
    em.mov_mem_r(5, -24, 8)                         # [rbp-24]=width（跨 buf_to_str 存活）
    em.mov_rd_mem(7, 5, -40)                        # rdi=s
    em.add_ri(7, 16)
    em.mov_rd_mem(1, 5, -16)                        # rcx=i
    em.add_rr(7, 1)                                 # rdi=s+16+i
    em.mov_rd_mem(1, 5, -24)                        # rcx=width
    em.call_rel32("buf_to_str")
    em.mov_rd_mem(2, 5, -32)                        # rdx=base
    em.mov_rd_mem(1, 5, -8)                         # rcx=j
    em.emit(b"\x48\x89\x44\xCA\x10")                # mov [rdx+rcx*8+16],rax
    em.mov_rd_mem(1, 5, -16)                        # rcx=i
    em.mov_rd_mem(8, 5, -24)                        # r8=width
    em.add_rr(1, 8)                                 # i += width
    em.mov_mem_r(5, -16, 1)                         # [rbp-16]=i
    em.emit(b"\x48\xFF\x45\xF8")                    # inc qword [rbp-8]
    em.jcc_rel32(None, "ls_s_loop")
    em.label_here("ls_s_done")
    em.mov_rd_mem(0, 5, -32)
    em.push_rax()
    _emit_epilogue(em)
    # ---- 字典 → 键列表 ----
    em.label_here("ls_dict")
    em.mov_rd_mem(0, 5, -40)
    em.call_rel32("dict_keys")
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_range(em: _Emitter):
    """range(start, end) → [start, start+1, …, end-1]（对齐 stdlib 的两参 range）。"""
    em.label_here("fn:range")
    _emit_prologue(em, 2, 4)                        # 参数: [rbp-32]=start [rbp-24]=end
    em.mov_rd_mem(2, 5, -24)                        # rdx=end
    em.mov_rd_mem(1, 5, -32)                        # rcx=start
    em.sub_rr(2, 1)                                 # n=end-start
    em.mov_mem_r(5, -16, 2)                         # [rbp-16]=n
    em.emit(b"\x48\x85\xD2")                        # test rdx,rdx
    em.jcc_rel32(0x8E, "rg_empty")                  # jle empty
    em.mov_rr(7, 2)
    em.shl_ri(7, 3)
    em.add_ri(7, 16)
    em.call_rel32("alloc")
    em.emit(b"\xC7\x00" + struct.pack("<I", TYPE_LIST))
    em.mov_rd_mem(1, 5, -16)
    em.mov_mem_r(0, 8, 1)                           # [base+8]=n
    em.emit(b"\x31\xC9")                            # xor ecx,ecx  i
    em.mov_rd_mem(8, 5, -32)                        # r8=start
    em.label_here("rg_loop")
    em.mov_rr(2, 8)
    em.add_rr(2, 1)                                 # rdx=start+i
    em.emit(b"\x48\x89\x54\xC8\x10")                # mov [rax+rcx*8+16],rdx
    em.inc_r(1)
    em.mov_rd_mem(9, 5, -16)                        # n
    em.cmp_rr(1, 9)
    em.jcc_rel32(0x82, "rg_loop")                   # jb loop
    em.push_rax()
    _emit_epilogue(em)
    em.label_here("rg_empty")
    em.emit(b"\x48\xC7\xC7\x10\x00\x00\x00")        # mov rdi,16
    em.call_rel32("alloc")
    em.emit(b"\xC7\x00" + struct.pack("<I", TYPE_LIST))
    em.emit(b"\x48\xC7\x40\x08\x00\x00\x00\x00")    # [rax+8]=0
    em.push_rax()
    _emit_epilogue(em)


# ---- 砖块 17 阶段一：mathlib 数论 ----

def _emit_builtin_factorial(em: _Emitter):
    """阶乘(n)：n<0 → 0（VM 会抛错，此处不崩溃优先）；否则 n!（i64，n>20 溢出）。"""
    l_neg, l_done, l_loop = "fac_neg", "fac_done", "fac_loop"
    em.label_here("fn:阶乘")
    _emit_prologue(em, 1, 1)
    em.mov_rd_mem(0, 5, -8)                         # rax=n
    em.emit(b"\x48\x85\xC0")                        # test rax,rax
    em.jcc_rel32(0x88, l_neg)                       # js  neg
    em.mov_r_imm32(2, 1)                            # rdx=acc=1
    em.emit(b"\x48\x83\xF8\x01")                    # cmp rax,1
    em.jcc_rel32(0x8E, l_done)                      # jle done
    em.label_here(l_loop)
    em.emit(b"\x48\x0F\xAF\xD0")                    # imul rdx,rax
    em.emit(b"\x48\xFF\xC8")                        # dec rax
    em.emit(b"\x48\x83\xF8\x01")                    # cmp rax,1
    em.jcc_rel32(0x8F, l_loop)                      # jg  loop
    em.label_here(l_done)
    em.mov_rr(0, 2)
    em.push_rax()
    _emit_epilogue(em)
    em.label_here(l_neg)
    em.xor_rr32(0, 0)
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_gcd(em: _Emitter):
    """最大公约数(a)(b) → math.gcd（非负，gcd(0,0)=0）。"""
    em.label_here("fn:最大公约数")
    _emit_prologue(em, 2, 2)
    em.mov_rd_mem(0, 5, -16)                        # a
    em.mov_rd_mem(1, 5, -8)                         # b
    em.call_rel32("ml_gcd")
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_lcm(em: _Emitter):
    """最小公倍数(a)(b) → abs(a*b)//gcd(a,b)；任一为 0 则 0。"""
    l_zero, l_pos, l_done = "lcm_zero", "lcm_pos", "lcm_done"
    em.label_here("fn:最小公倍数")
    _emit_prologue(em, 2, 2)
    em.mov_rd_mem(8, 5, -16)                        # r8=a
    em.mov_rd_mem(9, 5, -8)                         # r9=b
    em.test_rr(8, 8)
    em.jcc_rel32(0x84, l_zero)
    em.test_rr(9, 9)
    em.jcc_rel32(0x84, l_zero)
    em.mov_rr(0, 8)
    em.mov_rr(1, 9)
    em.call_rel32("ml_gcd")                         # rax=g
    em.mov_rr(1, 0)                                 # rcx=g
    em.mov_rr(0, 8)
    em.emit(b"\x49\x0F\xAF\xC1")                    # imul rax,r9（a*b）
    em.test_rr(0, 0)
    em.jcc_rel32(0x89, l_pos)                       # jns pos
    em.emit(b"\x48\xF7\xD8")                        # neg rax
    em.label_here(l_pos)
    em.emit(b"\x48\x99")                            # cqo
    em.emit(b"\x48\xF7\xF9")                        # idiv rcx
    em.jcc_rel32(None, l_done)
    em.label_here(l_zero)
    em.xor_rr32(0, 0)
    em.label_here(l_done)
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_perm(em: _Emitter):
    """排列数(n)(r) → math.perm(n,r)（n>=r，否则 0）。"""
    l_zero, l_done, l_loop = "perm_zero", "perm_done", "perm_loop"
    em.label_here("fn:排列数")
    _emit_prologue(em, 2, 2)
    em.mov_rd_mem(0, 5, -16)                        # rax=n
    em.mov_rd_mem(1, 5, -8)                         # rcx=r
    em.cmp_rr(0, 1)
    em.jcc_rel32(0x8C, l_zero)                      # jl  zero（n<r）
    em.mov_r_imm32(2, 1)                            # rdx=acc=1
    em.test_rr(1, 1)
    em.jcc_rel32(0x8E, l_done)                      # jle done（r<=0）
    em.label_here(l_loop)
    em.emit(b"\x48\x0F\xAF\xD0")                    # imul rdx,rax
    em.emit(b"\x48\xFF\xC8")                        # dec rax
    em.emit(b"\x48\xFF\xC9")                        # dec rcx
    em.test_rr(1, 1)
    em.jcc_rel32(0x8F, l_loop)                      # jg  loop
    em.label_here(l_done)
    em.mov_rr(0, 2)
    em.push_rax()
    _emit_epilogue(em)
    em.label_here(l_zero)
    em.xor_rr32(0, 0)
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_comb(em: _Emitter):
    """组合数(n)(r) → math.comb(n,r)（n>=r，否则 0）。逐步整除保持精确。"""
    l_zero, l_done, l_loop = "comb_zero", "comb_done", "comb_loop"
    em.label_here("fn:组合数")
    _emit_prologue(em, 2, 2)
    em.mov_rd_mem(8, 5, -16)                        # r8=n
    em.mov_rd_mem(9, 5, -8)                         # r9=r
    em.cmp_rr(8, 9)
    em.jcc_rel32(0x8C, l_zero)                      # jl  zero（n<r）
    em.mov_r_imm32(0, 1)                            # rax=acc=1
    em.mov_r_imm32(1, 1)                            # rcx=i=1
    em.test_rr(9, 9)
    em.jcc_rel32(0x8E, l_done)                      # jle done（r<=0）
    em.label_here(l_loop)
    em.mov_rr(10, 8)
    em.sub_rr(10, 9)                                # r10=n-r
    em.add_rr(10, 1)                                # r10=n-r+i
    em.emit(b"\x49\x0F\xAF\xC2")                    # imul rax,r10
    em.emit(b"\x48\x99")                            # cqo
    em.emit(b"\x48\xF7\xF9")                        # idiv rcx
    em.inc_r(1)                                     # i++
    em.cmp_rr(1, 9)
    em.jcc_rel32(0x8E, l_loop)                      # jle loop
    em.label_here(l_done)
    em.push_rax()
    _emit_epilogue(em)
    em.label_here(l_zero)
    em.xor_rr32(0, 0)
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_is_prime(em: _Emitter):
    """素数判定(n) → bool。"""
    l_false, l_true, l_loop = "isp_false", "isp_true", "isp_loop"
    em.label_here("fn:素数判定")
    _emit_prologue(em, 1, 1)
    em.mov_rd_mem(9, 5, -8)                         # r9=n
    em.cmp_ri(9, 2)
    em.jcc_rel32(0x8C, l_false)                     # jl  false
    em.jcc_rel32(0x84, l_true)                      # je  true（n==2）
    em.mov_rr(0, 9)
    em.emit(b"\xA8\x01")                            # test al,1
    em.jcc_rel32(0x84, l_false)                     # jz  false（偶数）
    em.mov_r_imm32(8, 3)                            # r8=i=3
    em.label_here(l_loop)
    em.emit(b"\x49\x0F\xAF\xC0")                    # imul rax,r8（i*i）
    em.cmp_rr(0, 9)
    em.jcc_rel32(0x8F, l_true)                      # jg  true（i*i>n）
    em.mov_rr(0, 9)
    em.emit(b"\x48\x99")                            # cqo
    em.emit(b"\x49\xF7\xF8")                        # idiv r8
    em.test_rr(2, 2)
    em.jcc_rel32(0x84, l_false)                     # jz  false（整除）
    em.add_ri(8, 2)                                 # i+=2
    em.jcc_rel32(None, l_loop)
    em.label_here(l_true)
    em.lea_rip(0, "bool_true")
    em.push_rax()
    _emit_epilogue(em)
    em.label_here(l_false)
    em.lea_rip(0, "bool_false")
    em.push_rax()
    _emit_epilogue(em)


# ---- 砖块 17 阶段一：mathlib 聚合 ----

def _emit_builtin_sum(em: _Emitter):
    """sum(lst)：整数累加保持整数；出现浮点则整体转浮点（对齐 Python sum）。"""
    l_notlist, l_loop = "sum_notlist", "sum_loop"
    l_fadd, l_next, l_done = "sum_fadd", "sum_next", "sum_done"
    em.label_here("fn:sum")
    _emit_prologue(em, 1, 1)
    em.mov_rd_mem(0, 5, -8)                         # rax=arg
    em.mov_rr(2, 0)
    em.lea_rip(1, "heap_base")
    em.sub_rr(2, 1)
    em.cmp_ri(2, HEAP_SIZE)
    em.jcc_rel32(0x83, l_notlist)                   # 非指针 → 0
    em.emit(b"\x48\x83\x38" + bytes([TYPE_LIST]))   # cmp qword[rax],TYPE_LIST
    em.jcc_rel32(0x85, l_notlist)
    em.lea_mem(9, 0, 16)                            # r9=base（首个元素）
    em.mov_rd_mem(10, 0, 8)                         # r10=n
    em.xor_rr32(8, 8)                               # r8=acc=0（整数）
    em.xor_rr32(11, 11)                             # r11=i=0
    em.test_rr(10, 10)
    em.jcc_rel32(0x84, l_done)
    em.label_here(l_loop)
    em.mov_rd_mem(0, 9, 0, index=11, scale=8)       # rax=elem
    em.mov_rr(7, 0)                                 # rdi=elem
    em.mov_rr(0, 8)
    em.call_rel32("is_float")
    em.emit(b"\x85\xC0")
    em.jcc_rel32(0x85, l_fadd)                      # 累加器是浮点 → 浮点加
    em.mov_rr(0, 7)
    em.call_rel32("is_float")
    em.emit(b"\x85\xC0")
    em.jcc_rel32(0x85, l_fadd)                      # 元素是浮点 → 浮点加
    em.add_rr(8, 7)                                 # 双整数：acc += elem
    em.jcc_rel32(None, l_next)
    em.label_here(l_fadd)
    em.mov_rr(0, 8)
    em.mov_rr(1, 7)
    em.call_rel32("f_add")
    em.mov_rr(8, 0)                                 # acc=浮点结果
    em.label_here(l_next)
    em.inc_r(11)
    em.cmp_rr(11, 10)
    em.jcc_rel32(0x82, l_loop)
    em.label_here(l_done)
    em.mov_rr(0, 8)
    em.push_rax()
    _emit_epilogue(em)
    em.label_here(l_notlist)
    em.xor_rr32(0, 0)
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_extremum(em: _Emitter, name: str, want_max: bool):
    """max/min(lst)：列表→极值元素（保留原类型）；非列表→原值。"""
    l_nonlist, l_loop = f"ex_{name}_nonlist", f"ex_{name}_loop"
    l_fc, l_assign, l_next, l_done = (
        f"ex_{name}_fc", f"ex_{name}_assign", f"ex_{name}_next", f"ex_{name}_done")
    em.label_here(f"fn:{name}")
    _emit_prologue(em, 1, 1)
    em.mov_rd_mem(0, 5, -8)                         # rax=arg
    em.mov_rr(2, 0)
    em.lea_rip(1, "heap_base")
    em.sub_rr(2, 1)
    em.cmp_ri(2, HEAP_SIZE)
    em.jcc_rel32(0x83, l_nonlist)
    em.emit(b"\x48\x83\x38" + bytes([TYPE_LIST]))
    em.jcc_rel32(0x85, l_nonlist)
    em.lea_mem(9, 0, 16)                            # r9=base
    em.mov_rd_mem(10, 0, 8)                         # r10=n
    em.test_rr(10, 10)
    em.jcc_rel32(0x84, l_nonlist)                   # 空表 → 原值
    em.mov_rd_mem(8, 9, 0)                          # r8=best=首个元素
    em.mov_r_imm32(11, 1)                           # i=1
    em.label_here(l_loop)
    em.cmp_rr(11, 10)
    em.jcc_rel32(0x83, l_done)                      # jae done
    em.mov_rd_mem(0, 9, 0, index=11, scale=8)       # elem
    em.mov_rr(7, 0)                                 # rdi=elem
    em.mov_rr(0, 8)
    em.call_rel32("is_float")
    em.emit(b"\x85\xC0")
    em.jcc_rel32(0x85, l_fc)
    em.mov_rr(0, 7)
    em.call_rel32("is_float")
    em.emit(b"\x85\xC0")
    em.jcc_rel32(0x85, l_fc)
    em.mov_rr(0, 7)                                 # 双整数：elem ? best
    em.cmp_rr(0, 8)
    em.jcc_rel32(0x8F if want_max else 0x8C, l_assign)
    em.jcc_rel32(None, l_next)
    em.label_here(l_fc)
    em.mov_rr(0, 7)                                 # l=elem
    em.mov_rr(1, 8)                                 # r=best
    em.call_rel32("float_cmp2")
    em.jcc_rel32(0x87 if want_max else 0x82, l_assign)
    em.label_here(l_next)
    em.inc_r(11)
    em.jcc_rel32(None, l_loop)
    em.label_here(l_assign)
    em.mov_rr(8, 7)                                 # best=elem
    em.jcc_rel32(None, l_next)
    em.label_here(l_done)
    em.mov_rr(0, 8)
    em.push_rax()
    _emit_epilogue(em)
    em.label_here(l_nonlist)
    em.mov_rd_mem(0, 5, -8)
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_sieve(em: _Emitter):
    """素数筛(n)：返回 n 以内全部素数构成的列表（n<2 → []）。"""
    l_empty, l_loop, l_skip, l_done = "sv_empty", "sv_loop", "sv_skip", "sv_done"
    em.label_here("fn:素数筛")
    _emit_prologue(em, 1, 5)                        # arg @ [rbp-40]
    em.mov_rd_mem(9, 5, -40)                        # r9=n
    em.mov_mem_r(5, -16, 9)                         # [rbp-16]=n
    em.cmp_ri(9, 2)
    em.jcc_rel32(0x8C, l_empty)                     # jl empty
    em.mov_rr(7, 9)
    em.shl_ri(7, 3)
    em.add_ri(7, 16)                                # 16 + 8*n
    em.call_rel32("alloc")
    em.emit(b"\xC7\x00" + struct.pack("<I", TYPE_LIST))
    em.emit(b"\x48\xC7\x40\x08\x00\x00\x00\x00")    # [rax+8]=0（先置计数 0）
    em.mov_mem_r(5, -24, 0)                         # [rbp-24]=result
    em.mov_r_imm32(1, 2)                            # rcx=k=2
    em.mov_mem_r(5, -8, 1)                          # [rbp-8]=k
    em.emit(b"\x48\xC7\x45\xE0\x00\x00\x00\x00")    # [rbp-32]=0（count）
    em.label_here(l_loop)
    em.mov_rd_mem(0, 5, -8)                         # rax=k
    em.mov_rd_mem(1, 5, -16)                        # rcx=n
    em.cmp_rr(0, 1)
    em.jcc_rel32(0x8F, l_done)                      # jg  done（k>n）
    em.call_rel32("ml_prime")                       # eax=1/0
    em.emit(b"\x85\xC0")
    em.jcc_rel32(0x84, l_skip)                      # jz  skip（非素数）
    em.mov_rd_mem(0, 5, -24)                        # rax=result
    em.mov_rd_mem(1, 5, -32)                        # rcx=count
    em.mov_rd_mem(2, 5, -8)                         # rdx=k
    em.emit(b"\x48\x89\x54\xC8\x10")                # mov [rax+rcx*8+16],rdx
    em.inc_r(1)
    em.mov_mem_r(5, -32, 1)                         # count++
    em.label_here(l_skip)
    em.mov_rd_mem(0, 5, -8)
    em.inc_r(0)
    em.mov_mem_r(5, -8, 0)                          # k++
    em.jcc_rel32(None, l_loop)
    em.label_here(l_done)
    em.mov_rd_mem(0, 5, -24)                        # rax=result
    em.mov_rd_mem(1, 5, -32)                        # count
    em.mov_mem_r(0, 8, 1)                           # [result+8]=count
    em.push_rax()
    _emit_epilogue(em)
    em.label_here(l_empty)
    em.emit(b"\x48\xC7\xC7\x10\x00\x00\x00")        # mov rdi,16
    em.call_rel32("alloc")
    em.emit(b"\xC7\x00" + struct.pack("<I", TYPE_LIST))
    em.emit(b"\x48\xC7\x40\x08\x00\x00\x00\x00")    # [rax+8]=0
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_pascal(em: _Emitter):
    """杨辉三角(n)：前 max(n,1) 行（对齐 _pascal_triangle；n<=1 → [[1]]）。"""
    l_use_n, l_outer, l_inner, l_rowend = (
        "yh_use_n", "yh_outer", "yh_inner", "yh_rowend")
    l_done = "yh_done"
    em.label_here("fn:杨辉三角")
    _emit_prologue(em, 1, 8)                        # arg @ [rbp-64]
    em.mov_rd_mem(9, 5, -64)                        # r9=n
    em.cmp_ri(9, 1)
    em.jcc_rel32(0x8F, l_use_n)                     # jg  use n
    em.mov_r_imm32(9, 1)
    em.label_here(l_use_n)
    em.mov_mem_r(5, -8, 9)                          # [rbp-8]=rows
    # row = [1]
    em.xor_rr32(0, 0)
    em.mov_r_imm32(1, 1)
    em.call_rel32("list_append")
    em.mov_mem_r(5, -24, 0)                         # [rbp-24]=row
    # result = [row]
    em.xor_rr32(0, 0)
    em.mov_rd_mem(1, 5, -24)
    em.call_rel32("list_append")
    em.mov_mem_r(5, -32, 0)                         # [rbp-32]=result
    em.mov_r_imm32(1, 1)
    em.mov_mem_r(5, -16, 1)                         # [rbp-16]=r=1
    em.label_here(l_outer)
    em.mov_rd_mem(0, 5, -16)                        # r
    em.mov_rd_mem(1, 5, -8)                         # rows
    em.cmp_rr(0, 1)
    em.jcc_rel32(0x8D, l_done)                      # jge done（r>=rows）
    # newlen = len(row)+1
    em.mov_rd_mem(0, 5, -24)
    em.mov_rd_mem(0, 0, 8)                          # rax=len(row)
    em.add_ri(0, 1)
    em.mov_mem_r(5, -56, 0)                         # [rbp-56]=newlen
    em.mov_rr(7, 0)
    em.shl_ri(7, 3)
    em.add_ri(7, 16)
    em.call_rel32("alloc")
    em.emit(b"\xC7\x00" + struct.pack("<I", TYPE_LIST))
    em.mov_rd_mem(1, 5, -56)
    em.mov_mem_r(0, 8, 1)                           # [rax+8]=newlen
    em.emit(b"\x48\xC7\x40\x10\x01\x00\x00\x00")    # [rax+16]=1
    em.mov_mem_r(5, -40, 0)                         # [rbp-40]=newrow
    em.emit(b"\x48\xC7\x45\xD0\x00\x00\x00\x00")    # [rbp-48]=0（i）
    em.label_here(l_inner)
    em.mov_rd_mem(0, 5, -24)                        # rax=row
    em.mov_rd_mem(1, 0, 8)                          # rcx=len(row)
    em.emit(b"\x48\xFF\xC9")                        # dec rcx（limit=len-1）
    em.mov_rd_mem(2, 5, -48)                        # rdx=i
    em.cmp_rr(2, 1)
    em.jcc_rel32(0x8D, l_rowend)                    # jge rowend（i>=len-1）
    em.mov_rd_mem(9, 0, 16, index=2, scale=8)       # r9=row[i]
    em.mov_rd_mem(10, 0, 24, index=2, scale=8)      # r10=row[i+1]
    em.add_rr(9, 10)
    em.mov_rd_mem(11, 5, -40)                       # r11=newrow
    em.emit(b"\x4D\x89\x4C\xD3\x18")                # mov [r11+rdx*8+24],r9
    em.inc_r(2)
    em.mov_mem_r(5, -48, 2)                         # i++
    em.jcc_rel32(None, l_inner)
    em.label_here(l_rowend)
    em.mov_rd_mem(0, 5, -40)                        # rax=newrow
    em.mov_rd_mem(1, 5, -56)                        # rcx=newlen
    em.emit(b"\x48\xC7\x44\xC8\x08\x01\x00\x00\x00")  # [rax+rcx*8+8]=1
    # result = list_append(result, newrow)
    em.mov_rd_mem(0, 5, -32)
    em.mov_rd_mem(1, 5, -40)
    em.call_rel32("list_append")
    em.mov_mem_r(5, -32, 0)
    # row = newrow
    em.mov_rd_mem(0, 5, -40)
    em.mov_mem_r(5, -24, 0)
    # r++
    em.mov_rd_mem(0, 5, -16)
    em.inc_r(0)
    em.mov_mem_r(5, -16, 0)
    em.jcc_rel32(None, l_outer)
    em.label_here(l_done)
    em.mov_rd_mem(0, 5, -32)
    em.push_rax()
    _emit_epilogue(em)


# ---- 砖块 17 阶段二：mathlib 逻辑运算 ----

def _emit_builtin_logic_not(em: _Emitter):
    """逻辑非(p) → bool（Python `not p`）。"""
    l_true, l_done = "lnot_true", "lnot_done"
    em.label_here("fn:逻辑非")
    _emit_prologue(em, 1, 1)
    em.mov_rd_mem(0, 5, -8)
    em.call_rel32("truthy")                         # ZF=1 ⟺ 假值
    em.jcc_rel32(0x84, l_true)                      # 假 → not p 为真
    em.lea_rip(0, "bool_false")
    em.jcc_rel32(None, l_done)
    em.label_here(l_true)
    em.lea_rip(0, "bool_true")
    em.label_here(l_done)
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_logic_and(em: _Emitter):
    """逻辑与(a)(b) → a and b（短路返回操作数，对齐 Python）。"""
    l_ret_a, l_done = "land_ret_a", "land_done"
    em.label_here("fn:逻辑与")
    _emit_prologue(em, 2, 2)                        # a@-16 b@-8
    em.mov_rd_mem(0, 5, -16)
    em.call_rel32("truthy")
    em.jcc_rel32(0x84, l_ret_a)                     # a 假 → 返回 a
    em.mov_rd_mem(0, 5, -8)                         # a 真 → 返回 b
    em.jcc_rel32(None, l_done)
    em.label_here(l_ret_a)
    em.mov_rd_mem(0, 5, -16)
    em.label_here(l_done)
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_logic_or(em: _Emitter):
    """逻辑或(a)(b) → a or b（短路返回操作数，对齐 Python）。"""
    l_ret_a, l_done = "lor_ret_a", "lor_done"
    em.label_here("fn:逻辑或")
    _emit_prologue(em, 2, 2)
    em.mov_rd_mem(0, 5, -16)
    em.call_rel32("truthy")
    em.jcc_rel32(0x85, l_ret_a)                     # a 真 → 返回 a
    em.mov_rd_mem(0, 5, -8)                         # a 假 → 返回 b
    em.jcc_rel32(None, l_done)
    em.label_here(l_ret_a)
    em.mov_rd_mem(0, 5, -16)
    em.label_here(l_done)
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_logic_implies(em: _Emitter):
    """逻辑蕴含(p)(q) → (not p) or q。"""
    l_ret_q, l_done = "limp_ret_q", "limp_done"
    em.label_here("fn:逻辑蕴含")
    _emit_prologue(em, 2, 2)                        # p@-16 q@-8
    em.mov_rd_mem(0, 5, -16)
    em.call_rel32("truthy")
    em.jcc_rel32(0x85, l_ret_q)                     # p 真 → 返回 q
    em.lea_rip(0, "bool_true")                      # p 假 → True
    em.jcc_rel32(None, l_done)
    em.label_here(l_ret_q)
    em.mov_rd_mem(0, 5, -8)
    em.label_here(l_done)
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_logic_iff(em: _Emitter):
    """逻辑双蕴含(p)(q) → (p == q)（val_eq + bool）。"""
    l_false, l_done = "liff_false", "liff_done"
    em.label_here("fn:逻辑双蕴含")
    _emit_prologue(em, 2, 2)
    em.mov_rd_mem(0, 5, -16)
    em.mov_rd_mem(1, 5, -8)
    em.call_rel32("val_eq")                         # rax=1/0
    em.emit(b"\x48\x85\xC0")                        # test rax,rax
    em.jcc_rel32(0x84, l_false)
    em.lea_rip(0, "bool_true")
    em.jcc_rel32(None, l_done)
    em.label_here(l_false)
    em.lea_rip(0, "bool_false")
    em.label_here(l_done)
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_logic_xor(em: _Emitter):
    """逻辑异或(p)(q) → (p or q) and not (p and q)（对齐 Python 返回原值）。"""
    l_aq, l_have, l_ret_a, l_true, l_false, l_done = (
        "lx_aq", "lx_have", "lx_ret_a", "lx_true", "lx_false", "lx_done")
    em.label_here("fn:逻辑异或")
    _emit_prologue(em, 2, 3)                        # p@-24 q@-16 A@-8
    em.mov_rd_mem(0, 5, -24)
    em.call_rel32("truthy")
    em.jcc_rel32(0x84, l_aq)                        # p 假 → A=q
    em.mov_rd_mem(0, 5, -24)                        # A=p
    em.mov_mem_r(5, -8, 0)
    em.jcc_rel32(None, l_have)
    em.label_here(l_aq)
    em.mov_rd_mem(0, 5, -16)
    em.mov_mem_r(5, -8, 0)
    em.label_here(l_have)
    em.mov_rd_mem(0, 5, -8)                         # A
    em.call_rel32("truthy")
    em.jcc_rel32(0x84, l_ret_a)                     # A 假 → 返回 A
    em.mov_rd_mem(0, 5, -24)
    em.call_rel32("truthy")
    em.jcc_rel32(0x84, l_true)                      # p 假 → not(假)=真
    em.mov_rd_mem(0, 5, -16)
    em.call_rel32("truthy")
    em.jcc_rel32(0x84, l_true)                      # q 假 → 真
    em.jcc_rel32(None, l_false)
    em.label_here(l_ret_a)
    em.mov_rd_mem(0, 5, -8)
    em.jcc_rel32(None, l_done)
    em.label_here(l_true)
    em.lea_rip(0, "bool_true")
    em.jcc_rel32(None, l_done)
    em.label_here(l_false)
    em.lea_rip(0, "bool_false")
    em.label_here(l_done)
    em.push_rax()
    _emit_epilogue(em)


# ---- 砖块 17 阶段二：mathlib 集合运算 ----

def _emit_alloc_empty_list(em: _Emitter):
    """发射「alloc 一个空列表到 rax」。破坏 rax/rdx。"""
    em.mov_r_imm32(7, 16)
    em.call_rel32("alloc")
    em.emit(b"\xC7\x00" + struct.pack("<I", TYPE_LIST))
    em.emit(b"\x48\xC7\x40\x08\x00\x00\x00\x00")    # [rax+8]=0


def _emit_append_all(em: _Emitter, tag: str, src: int, raw: int,
                     i_disp: int, n_disp: int, elem_disp: int):
    """raw = raw ++ [src 的每个元素]（原地更新 [rbp+raw]）。"""
    l_loop, l_done = f"aa_{tag}_loop", f"aa_{tag}_done"
    em.mov_rd_mem(0, 5, src)
    em.mov_rd_mem(1, 0, 8)                          # rcx=len(src)
    em.mov_mem_r(5, n_disp, 1)
    em.xor_rr32(0, 0)
    em.mov_mem_r(5, i_disp, 0)                      # i=0
    em.label_here(l_loop)
    em.mov_rd_mem(0, 5, i_disp)
    em.mov_rd_mem(1, 5, n_disp)
    em.cmp_rr(0, 1)
    em.jcc_rel32(0x8D, l_done)                      # i>=n
    em.mov_rd_mem(0, 5, src)
    em.mov_rd_mem(2, 5, i_disp)
    em.mov_rd_mem(8, 0, 16, index=2, scale=8)       # r8=elem
    em.mov_rd_mem(0, 5, raw)
    em.mov_rr(1, 8)
    em.call_rel32("list_append")
    em.mov_mem_r(5, raw, 0)                         # raw=结果
    em.mov_rd_mem(0, 5, i_disp)
    em.inc_r(0)
    em.mov_mem_r(5, i_disp, 0)
    em.jcc_rel32(None, l_loop)
    em.label_here(l_done)


def _emit_append_filtered(em: _Emitter, tag: str, src: int, cont: int, raw: int,
                          i_disp: int, n_disp: int, elem_disp: int,
                          keep_on_found: bool):
    """raw = raw ++ [x for x in src if (x in cont) == keep_on_found]。"""
    l_loop, l_skip, l_done = (f"af_{tag}_loop", f"af_{tag}_skip",
                              f"af_{tag}_done")
    em.mov_rd_mem(0, 5, src)
    em.mov_rd_mem(1, 0, 8)
    em.mov_mem_r(5, n_disp, 1)
    em.xor_rr32(0, 0)
    em.mov_mem_r(5, i_disp, 0)
    em.label_here(l_loop)
    em.mov_rd_mem(0, 5, i_disp)
    em.mov_rd_mem(1, 5, n_disp)
    em.cmp_rr(0, 1)
    em.jcc_rel32(0x8D, l_done)
    em.mov_rd_mem(0, 5, src)
    em.mov_rd_mem(2, 5, i_disp)
    em.mov_rd_mem(8, 0, 16, index=2, scale=8)       # r8=elem
    em.mov_mem_r(5, elem_disp, 8)
    em.mov_rr(0, 8)                                 # rax=needle
    em.mov_rd_mem(1, 5, cont)                       # rcx=容器
    em.call_rel32("seq_contains")                   # eax=1/0
    em.emit(b"\x85\xC0")
    em.jcc_rel32(0x84 if keep_on_found else 0x85, l_skip)
    em.mov_rd_mem(0, 5, raw)
    em.mov_rd_mem(1, 5, elem_disp)
    em.call_rel32("list_append")
    em.mov_mem_r(5, raw, 0)
    em.label_here(l_skip)
    em.mov_rd_mem(0, 5, i_disp)
    em.inc_r(0)
    em.mov_mem_r(5, i_disp, 0)
    em.jcc_rel32(None, l_loop)
    em.label_here(l_done)


def _emit_builtin_setop2(em: _Emitter, name: str, mode: str):
    """集合并/交/差/补（mode: union/inter/diff）。结果去重升序。"""
    em.label_here(f"fn:{name}")
    _emit_prologue(em, 2, 8)                        # a@-64 b@-56
    # A = setify(a) → [rbp-8]
    em.mov_rd_mem(0, 5, -64)
    em.call_rel32("ml_setify")
    em.mov_mem_r(5, -8, 0)
    # b → [rbp-32]
    em.mov_rd_mem(0, 5, -56)
    em.mov_mem_r(5, -32, 0)
    # raw = 空表 → [rbp-40]
    _emit_alloc_empty_list(em)
    em.mov_mem_r(5, -40, 0)
    if mode == "union":
        # 追加 A 的全部元素，再追加 setify(b) 的全部元素
        _emit_append_all(em, f"{name}_a", -8, -40, -16, -24, -48)
        em.mov_rd_mem(0, 5, -32)
        em.call_rel32("ml_setify")
        em.mov_mem_r(5, -48, 0)                     # [rbp-48]=setify(b)
        _emit_append_all(em, f"{name}_b", -48, -40, -16, -24, -56)
    else:
        _emit_append_filtered(
            em, name, -8, -32, -40, -16, -24, -48,
            keep_on_found=(mode == "inter"))
    em.mov_rd_mem(0, 5, -40)
    em.call_rel32("ml_setify")                      # 去重 + 升序
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_subset(em: _Emitter):
    """集合子集(a)(b) → set(a) ⊆ set(b)。"""
    l_loop, l_false, l_true, l_done = (
        "sbs_loop", "sbs_false", "sbs_true", "sbs_done")
    em.label_here("fn:集合子集")
    _emit_prologue(em, 2, 8)                        # a@-64 b@-56
    em.mov_rd_mem(0, 5, -64)
    em.call_rel32("ml_setify")
    em.mov_mem_r(5, -8, 0)                          # [rbp-8]=A
    em.mov_rd_mem(0, 5, -56)
    em.mov_mem_r(5, -32, 0)                         # [rbp-32]=b
    em.mov_rd_mem(1, 5, -8)
    em.mov_rd_mem(1, 1, 8)                          # rcx=len(A)
    em.mov_mem_r(5, -24, 1)                         # n
    em.xor_rr32(0, 0)
    em.mov_mem_r(5, -16, 0)                         # i=0
    em.label_here(l_loop)
    em.mov_rd_mem(0, 5, -16)
    em.mov_rd_mem(1, 5, -24)
    em.cmp_rr(0, 1)
    em.jcc_rel32(0x8D, l_true)                      # i>=n
    em.mov_rd_mem(0, 5, -8)
    em.mov_rd_mem(2, 5, -16)
    em.mov_rd_mem(0, 0, 16, index=2, scale=8)       # rax=elem
    em.mov_rd_mem(1, 5, -32)                        # rcx=b
    em.call_rel32("seq_contains")
    em.emit(b"\x85\xC0")
    em.jcc_rel32(0x84, l_false)                     # 未命中 → 非子集
    em.mov_rd_mem(0, 5, -16)
    em.inc_r(0)
    em.mov_mem_r(5, -16, 0)
    em.jcc_rel32(None, l_loop)
    em.label_here(l_true)
    em.lea_rip(0, "bool_true")
    em.jcc_rel32(None, l_done)
    em.label_here(l_false)
    em.lea_rip(0, "bool_false")
    em.label_here(l_done)
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_cardinality(em: _Emitter):
    """集合基数(s) → len(set(s))。"""
    em.label_here("fn:集合基数")
    _emit_prologue(em, 1, 1)
    em.mov_rd_mem(0, 5, -8)
    em.call_rel32("ml_setify")
    em.mov_rd_mem(1, 0, 8)                          # rcx=[result+8]
    em.mov_rr(0, 1)
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_powerset(em: _Emitter):
    """集合幂集(s) → 全部子集列表（对齐 _power_set：第 k 项含元素 i 当且仅当 k 的第 i 位为 1）。"""
    l_kloop, l_bit, l_bitdone, l_iloop, l_iskip, l_idone = (
        "ps_kloop", "ps_bit", "ps_bitdone", "ps_iloop", "ps_iskip", "ps_idone")
    l_kdone = "ps_kdone"
    em.label_here("fn:集合幂集")
    _emit_prologue(em, 1, 10)                       # arg @ [rbp-80]
    em.mov_rd_mem(0, 5, -80)
    em.mov_mem_r(5, -8, 0)                          # [rbp-8]=L
    em.mov_rd_mem(1, 0, 8)                          # rcx=n
    em.mov_mem_r(5, -16, 1)                         # [rbp-16]=n
    em.mov_r_imm32(0, 1)
    em.emit(b"\x48\xD3\xE0")                        # shl rax,cl（total=1<<n）
    em.mov_mem_r(5, -24, 0)                         # [rbp-24]=total
    em.mov_rr(7, 0)                                 # rdi=total
    em.shl_ri(7, 3)
    em.add_ri(7, 16)                                # 16+8*total
    em.call_rel32("alloc")
    em.emit(b"\xC7\x00" + struct.pack("<I", TYPE_LIST))
    em.mov_rd_mem(1, 5, -24)
    em.mov_mem_r(0, 8, 1)                           # [result+8]=total
    em.mov_mem_r(5, -32, 0)                         # [rbp-32]=result
    em.emit(b"\x48\xC7\x45\xD8\x00\x00\x00\x00")    # [rbp-40]=k=0
    em.label_here(l_kloop)
    em.mov_rd_mem(0, 5, -40)
    em.mov_rd_mem(1, 5, -24)
    em.cmp_rr(0, 1)
    em.jcc_rel32(0x8D, l_kdone)                     # k>=total
    # count = popcount(k)
    em.mov_rd_mem(0, 5, -40)
    em.xor_rr32(8, 8)                               # r8=count=0
    em.label_here(l_bit)
    em.emit(b"\x48\x85\xC0")                        # test rax,rax
    em.jcc_rel32(0x84, l_bitdone)
    em.mov_rr(9, 0)
    em.and_ri(9, 1)
    em.add_rr(8, 9)
    em.shr_ri(0, 1)
    em.jcc_rel32(None, l_bit)
    em.label_here(l_bitdone)
    # sub = alloc 16+8*count ; [sub+8]=count
    em.mov_mem_r(5, -64, 8)                         # [rbp-64]=count
    em.mov_rr(7, 8)
    em.shl_ri(7, 3)
    em.add_ri(7, 16)
    em.call_rel32("alloc")
    em.emit(b"\xC7\x00" + struct.pack("<I", TYPE_LIST))
    em.mov_rd_mem(1, 5, -64)
    em.mov_mem_r(0, 8, 1)
    em.mov_mem_r(5, -48, 0)                         # [rbp-48]=sub
    em.emit(b"\x48\xC7\x45\xC8\x00\x00\x00\x00")    # [rbp-56]=i=0
    em.emit(b"\x48\xC7\x45\xC0\x00\x00\x00\x00")    # [rbp-64]=idx=0
    em.label_here(l_iloop)
    em.mov_rd_mem(0, 5, -56)
    em.mov_rd_mem(1, 5, -16)
    em.cmp_rr(0, 1)
    em.jcc_rel32(0x8D, l_idone)                     # i>=n
    em.mov_rd_mem(0, 5, -40)                        # k
    em.mov_rd_mem(1, 5, -56)                        # i
    em.emit(b"\x48\xD3\xE8")                        # shr rax,cl
    em.emit(b"\xA8\x01")                            # test al,1
    em.jcc_rel32(0x84, l_iskip)
    em.mov_rd_mem(2, 5, -8)                         # L
    em.mov_rd_mem(1, 5, -56)                        # i
    em.mov_rd_mem(2, 2, 16, index=1, scale=8)       # rdx=elem=L[i]
    em.mov_rd_mem(0, 5, -48)                        # sub
    em.mov_rd_mem(1, 5, -64)                        # idx
    em.mov_mem_r_idx(0, 2, 16, index=1, scale=8)    # sub[idx]=elem
    em.mov_rd_mem(0, 5, -64)
    em.inc_r(0)
    em.mov_mem_r(5, -64, 0)                         # idx++
    em.label_here(l_iskip)
    em.mov_rd_mem(0, 5, -56)
    em.inc_r(0)
    em.mov_mem_r(5, -56, 0)                         # i++
    em.jcc_rel32(None, l_iloop)
    em.label_here(l_idone)
    em.mov_rd_mem(0, 5, -32)                        # result
    em.mov_rd_mem(1, 5, -40)                        # k
    em.mov_rd_mem(2, 5, -48)                        # sub
    em.mov_mem_r_idx(0, 2, 16, index=1, scale=8)    # result[k]=sub
    em.mov_rd_mem(0, 5, -40)
    em.inc_r(0)
    em.mov_mem_r(5, -40, 0)                         # k++
    em.jcc_rel32(None, l_kloop)
    em.label_here(l_kdone)
    em.mov_rd_mem(0, 5, -32)
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_mean(em: _Emitter):
    """平均值(lst) = sum(lst)/len(lst) if lst else 0（空表→int 0，否则 float）。"""
    l_empty, l_done = "mean_empty", "mean_done"
    em.label_here("fn:平均值")
    _emit_prologue(em, 1, 2)                        # arg @ [rbp-16]
    em.mov_rd_mem(0, 5, -16)
    em.mov_rd_mem(1, 0, 8)
    em.test_rr(1, 1)
    em.jcc_rel32(0x84, l_empty)
    em.mov_rd_mem(0, 5, -16)
    em.call_rel32("ml_mean")
    em.call_rel32("box_float")
    em.jcc_rel32(None, l_done)
    em.label_here(l_empty)
    em.xor_rr32(0, 0)
    em.label_here(l_done)
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_median(em: _Emitter):
    """中位数(lst) = _median(list(lst))；奇数→原元素，偶数→(a+b)/2（float），空→0。"""
    l_empty, l_even, l_done = "median_empty", "median_even", "median_done"
    em.label_here("fn:中位数")
    _emit_prologue(em, 1, 8)                        # arg @ [rbp-64]
    em.mov_rd_mem(0, 5, -64)
    em.call_rel32("ml_sort_numeric")
    em.mov_mem_r(5, -8, 0)                          # [rbp-8]=sorted
    em.mov_rd_mem(1, 0, 8)
    em.mov_mem_r(5, -16, 1)                         # [rbp-16]=n
    em.test_rr(1, 1)
    em.jcc_rel32(0x84, l_empty)
    em.shr_ri(1, 1)                                 # mid=n>>1
    em.mov_mem_r(5, -24, 1)                         # [rbp-24]=mid
    em.mov_rd_mem(0, 5, -16)
    em.emit(b"\xA8\x01")                            # test al,1
    em.jcc_rel32(0x84, l_even)
    em.mov_rd_mem(0, 5, -8)                         # 奇数：sorted[mid]
    em.mov_rd_mem(1, 5, -24)
    em.mov_rd_mem(0, 0, 16, index=1, scale=8)
    em.jcc_rel32(None, l_done)
    em.label_here(l_even)
    em.mov_rd_mem(0, 5, -8)                         # a=sorted[mid-1]
    em.mov_rd_mem(1, 5, -24)
    em.dec_r(1)
    em.mov_rd_mem(0, 0, 16, index=1, scale=8)
    em.call_rel32("as_double")
    em.movsd_store(5, -32, 0)
    em.mov_rd_mem(0, 5, -8)                         # b=sorted[mid]
    em.mov_rd_mem(1, 5, -24)
    em.mov_rd_mem(0, 0, 16, index=1, scale=8)
    em.call_rel32("as_double")
    em.movsd_load(1, 5, -32)
    em.addsd(1, 0)                                  # a+b
    em.mov_r_imm64(2, _dbl_bits(2.0))
    em.movq_xmm_r(0, 2)
    em.divsd(1, 0)                                  # (a+b)/2
    em.emit(b"\xF2\x0F\x10\xC1")                    # movsd xmm0,xmm1
    em.call_rel32("box_float")
    em.jcc_rel32(None, l_done)
    em.label_here(l_empty)
    em.xor_rr32(0, 0)
    em.label_here(l_done)
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_variance(em: _Emitter):
    """方差(lst) = _variance(list(lst))；空→int 0，否则 float。"""
    l_empty, l_done = "var_empty", "var_done"
    em.label_here("fn:方差")
    _emit_prologue(em, 1, 2)
    em.mov_rd_mem(0, 5, -16)
    em.mov_rd_mem(1, 0, 8)
    em.test_rr(1, 1)
    em.jcc_rel32(0x84, l_empty)
    em.mov_rd_mem(0, 5, -16)
    em.call_rel32("ml_variance_double")
    em.call_rel32("box_float")
    em.jcc_rel32(None, l_done)
    em.label_here(l_empty)
    em.xor_rr32(0, 0)
    em.label_here(l_done)
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_stddev(em: _Emitter):
    """标准差(lst) = math.sqrt(_variance(list(lst)))（空→float 0.0）。"""
    em.label_here("fn:标准差")
    _emit_prologue(em, 1, 1)                        # arg @ [rbp-8]
    em.mov_rd_mem(0, 5, -8)
    em.call_rel32("ml_variance_double")
    em.call_rip_indirect("crt_sqrt")
    em.call_rel32("box_float")
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_covariance(em: _Emitter):
    """协方差(x)(y) = _covariance(x,y)；长度不等/空→int 0，否则 float。"""
    l_empty, l_done = "cov_empty", "cov_done"
    em.label_here("fn:协方差")
    _emit_prologue(em, 2, 2)                        # x @ [rbp-16], y @ [rbp-8]
    em.mov_rd_mem(0, 5, -16)
    em.mov_rd_mem(1, 5, -8)
    em.mov_rd_mem(2, 0, 8)                          # nx
    em.mov_rd_mem(8, 1, 8)                          # ny
    em.cmp_rr(2, 8)
    em.jcc_rel32(0x85, l_empty)
    em.test_rr(2, 2)
    em.jcc_rel32(0x84, l_empty)
    em.mov_rd_mem(0, 5, -16)
    em.mov_rd_mem(1, 5, -8)
    em.call_rel32("ml_covariance_double")
    em.call_rel32("box_float")
    em.jcc_rel32(None, l_done)
    em.label_here(l_empty)
    em.xor_rr32(0, 0)
    em.label_here(l_done)
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_correlation(em: _Emitter):
    """相关系数(x)(y) = cx/(sx*sy)；sx==0 或 sy==0 → int 0，否则 float。"""
    l_zero, l_done = "corr_zero", "corr_done"
    em.label_here("fn:相关系数")
    _emit_prologue(em, 2, 8)                        # x @ [rbp-64], y @ [rbp-56]
    em.mov_rd_mem(0, 5, -64)
    em.mov_rd_mem(1, 5, -56)
    em.call_rel32("ml_covariance_double")
    em.movsd_store(5, -8, 0)                        # cx
    em.mov_rd_mem(0, 5, -64)
    em.call_rel32("ml_variance_double")
    em.movsd_store(5, -16, 0)                       # vx
    em.mov_rd_mem(0, 5, -56)
    em.call_rel32("ml_variance_double")
    em.movsd_store(5, -24, 0)                       # vy
    em.movsd_load(0, 5, -16)
    em.call_rip_indirect("crt_sqrt")
    em.movsd_store(5, -32, 0)                       # sx
    em.movsd_load(0, 5, -24)
    em.call_rip_indirect("crt_sqrt")
    em.movsd_store(5, -40, 0)                       # sy
    em.emit(b"\x66\x0F\xEF\xC9")                    # pxor xmm1,xmm1
    em.movsd_load(0, 5, -32)
    em.ucomisd(0, 1)
    em.jcc_rel32(0x84, l_zero)
    em.movsd_load(0, 5, -40)
    em.ucomisd(0, 1)
    em.jcc_rel32(0x84, l_zero)
    em.movsd_load(0, 5, -32)                        # sx*sy
    em.movsd_load(1, 5, -40)
    em.mulsd(0, 1)
    em.movsd_load(1, 5, -8)                         # cx
    em.divsd(1, 0)
    em.emit(b"\xF2\x0F\x10\xC1")                    # movsd xmm0,xmm1
    em.call_rel32("box_float")
    em.jcc_rel32(None, l_done)
    em.label_here(l_zero)
    em.xor_rr32(0, 0)
    em.label_here(l_done)
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_norm_pdf(em: _Emitter):
    """正态密度(x)(mu)(sigma)；sigma<=0 → int 0，否则 float。"""
    l_zero, l_done = "npdf_zero", "npdf_done"
    em.label_here("fn:正态密度")
    _emit_prologue(em, 3, 8)                        # x@-64, mu@-56, sigma@-48
    em.mov_rd_mem(0, 5, -48)
    em.call_rel32("as_double")
    em.movsd_store(5, -24, 0)                       # sigma
    em.emit(b"\x66\x0F\xEF\xC9")                    # pxor xmm1,xmm1
    em.movsd_load(0, 5, -24)
    em.ucomisd(0, 1)
    em.jcc_rel32(0x86, l_zero)                      # sigma<=0
    em.mov_rd_mem(0, 5, -64)
    em.call_rel32("as_double")
    em.movsd_store(5, -8, 0)                        # x
    em.mov_rd_mem(0, 5, -56)
    em.call_rel32("as_double")
    em.movsd_store(5, -16, 0)                       # mu
    # part1 = 1/(sigma*sqrt(2*pi))
    em.mov_r_imm64(2, _dbl_bits(2.0 * math.pi))
    em.movq_xmm_r(0, 2)
    em.call_rip_indirect("crt_sqrt")
    em.movsd_load(1, 5, -24)
    em.mulsd(0, 1)
    em.mov_r_imm64(2, _dbl_bits(1.0))
    em.movq_xmm_r(1, 2)
    em.divsd(1, 0)
    em.emit(b"\xF2\x0F\x10\xC1")
    em.movsd_store(5, -32, 0)                       # part1
    # sq=(x-mu)^2，取负 → [rbp-40]
    em.movsd_load(0, 5, -8)
    em.movsd_load(1, 5, -16)
    em.subsd(0, 1)
    em.mulsd(0, 0)
    em.movq_r_xmm(0, 0)
    em.mov_r_imm64(2, 0x8000000000000000)
    em.emit(b"\x48\x31\xD0")                        # xor rax,rdx
    em.movq_xmm_r(0, 0)
    em.movsd_store(5, -40, 0)
    # denom = 2*sigma^2
    em.movsd_load(0, 5, -24)
    em.mulsd(0, 0)
    em.mov_r_imm64(2, _dbl_bits(2.0))
    em.movq_xmm_r(1, 2)
    em.mulsd(0, 1)
    # ratio = exparg/denom ; exp
    em.movsd_load(1, 5, -40)
    em.divsd(1, 0)
    em.emit(b"\xF2\x0F\x10\xC1")
    em.call_rip_indirect("crt_exp")
    em.movsd_load(1, 5, -32)
    em.mulsd(0, 1)
    em.call_rel32("box_float")
    em.jcc_rel32(None, l_done)
    em.label_here(l_zero)
    em.xor_rr32(0, 0)
    em.label_here(l_done)
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_uniform(em: _Emitter):
    """均匀随机(a)(b) = a+(b-a)*random()（非确定性，仅原生定点断言）。"""
    em.label_here("fn:均匀随机")
    _emit_prologue(em, 2, 4)                        # a @ [rbp-32], b @ [rbp-24]
    em.mov_rd_mem(0, 5, -32)
    em.call_rel32("as_double")
    em.movsd_store(5, -8, 0)                        # a
    em.mov_rd_mem(0, 5, -24)
    em.call_rel32("as_double")
    em.movsd_store(5, -16, 0)                       # b
    em.call_rel32("ml_rand")                        # xmm0=r
    em.movsd_load(2, 5, -8)                         # a
    em.movsd_load(1, 5, -16)                        # b
    em.subsd(1, 2)                                  # b-a
    em.mulsd(1, 0)                                  # (b-a)*r
    em.addsd(1, 2)                                  # +a
    em.emit(b"\xF2\x0F\x10\xC1")                    # movsd xmm0,xmm1
    em.call_rel32("box_float")
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_gauss(em: _Emitter):
    """正态随机(mu)(sigma) = mu+sigma*z（Box-Muller；非确定性，仅原生定点断言）。"""
    l_u1ok = "gauss_u1ok"
    em.label_here("fn:正态随机")
    _emit_prologue(em, 2, 8)                        # mu@-64, sigma@-56
    em.mov_rd_mem(0, 5, -64)
    em.call_rel32("as_double")
    em.movsd_store(5, -8, 0)                        # mu
    em.mov_rd_mem(0, 5, -56)
    em.call_rel32("as_double")
    em.movsd_store(5, -16, 0)                       # sigma
    em.call_rel32("ml_rand")
    em.movsd_store(5, -24, 0)                       # u1
    em.emit(b"\x66\x0F\xEF\xC9")                    # pxor xmm1,xmm1
    em.movsd_load(0, 5, -24)
    em.ucomisd(0, 1)
    em.jcc_rel32(0x85, l_u1ok)
    em.mov_r_imm64(2, _dbl_bits(0.5))
    em.movq_xmm_r(0, 2)
    em.movsd_store(5, -24, 0)
    em.label_here(l_u1ok)
    em.call_rel32("ml_rand")
    em.movsd_store(5, -32, 0)                       # u2
    em.movsd_load(0, 5, -24)
    em.call_rip_indirect("crt_log")
    em.mov_r_imm64(2, _dbl_bits(-2.0))
    em.movq_xmm_r(1, 2)
    em.mulsd(0, 1)
    em.call_rip_indirect("crt_sqrt")
    em.movsd_store(5, -40, 0)                       # sqrt(-2 ln u1)
    em.movsd_load(0, 5, -32)
    em.mov_r_imm64(2, _dbl_bits(2.0 * math.pi))
    em.movq_xmm_r(1, 2)
    em.mulsd(0, 1)
    em.call_rip_indirect("crt_cos")
    em.movsd_load(1, 5, -40)
    em.mulsd(0, 1)                                  # z
    em.movsd_load(1, 5, -16)
    em.mulsd(1, 0)                                  # sigma*z
    em.movsd_load(2, 5, -8)
    em.addsd(1, 2)                                  # +mu
    em.emit(b"\xF2\x0F\x10\xC1")                    # movsd xmm0,xmm1
    em.call_rel32("box_float")
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_read_file(em: _Emitter):
    """_read_file(path) → 该文件全部字节构成的文本；失败 → null。"""
    em.label_here("fn:_read_file")
    _emit_prologue(em, 1, 8)                        # 参数 [rbp-64]
    em.mov_rd_mem(0, 5, -64)
    em.mov_rr(1, 0)
    em.lea_rip(2, "heap_base")
    em.sub_rr(1, 2)
    em.cmp_ri(1, HEAP_SIZE)
    em.jcc_rel32(0x83, "rf_fail")
    em.mov_rd_mem(1, 0, 0)
    em.cmp_ri(1, TYPE_STR)
    em.jcc_rel32(0x85, "rf_fail")
    em.call_rel32("fs_pathbuf")                     # rax=buf
    em.emit(b"\x48\x83\xE4\xF0")                    # and rsp,-16
    em.emit(b"\x48\x83\xEC\x40")                    # sub rsp,0x40
    em.mov_rr(1, 0)                                 # rcx=buf
    em.lea_rip(2, "mode_rb")
    em.call_rip_indirect("crt_fopen")
    em.mov_mem_r(5, -48, 0)                         # [rbp-48]=file
    em.emit(b"\x48\x85\xC0")                        # test rax,rax
    em.jcc_rel32(0x84, "rf_fail")
    em.mov_rd_mem(1, 5, -48)                        # rcx=file
    em.emit(b"\x31\xD2")                            # xor edx,edx
    em.emit(b"\x41\xB8\x02\x00\x00\x00")            # mov r8d,2 (SEEK_END)
    em.call_rip_indirect("crt_fseek")
    em.mov_rd_mem(1, 5, -48)
    em.call_rip_indirect("crt_ftell")
    em.mov_mem_r(5, -40, 0)                         # [rbp-40]=size
    em.mov_rd_mem(1, 5, -48)
    em.emit(b"\x31\xD2")                            # xor edx,edx
    em.emit(b"\x45\x31\xC0")                        # xor r8d,r8d (SEEK_SET)
    em.call_rip_indirect("crt_fseek")
    em.mov_rd_mem(7, 5, -40)                        # rdi=size
    em.add_ri(7, 16)
    em.call_rel32("alloc")
    em.mov_mem_r(5, -32, 0)                         # [rbp-32]=base
    em.mov_rr(1, 0)                                 # rcx=base
    em.add_ri(1, 16)
    em.emit(b"\xBA\x01\x00\x00\x00")                # mov edx,1
    em.mov_rd_mem(8, 5, -40)                        # r8=size
    em.mov_rd_mem(9, 5, -48)                        # r9=file
    em.call_rip_indirect("crt_fread")
    em.mov_rd_mem(1, 5, -48)
    em.call_rip_indirect("crt_fclose")
    em.mov_rd_mem(0, 5, -32)
    em.emit(b"\xC7\x00" + struct.pack("<I", TYPE_STR))
    em.mov_rd_mem(1, 5, -40)
    em.mov_mem_r(0, 8, 1)                           # [base+8]=size
    em.push_rax()
    _emit_epilogue(em)
    em.label_here("rf_fail")
    em.lea_rip(0, "null_obj")
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_write_like(em: _Emitter, name: str, mode_label: str):
    """_write_file/_append_file(path, content) → null。失败静默返回 null。"""
    em.label_here("fn:" + name)
    _emit_prologue(em, 2, 6)                        # 参数 [rbp-48]=path [rbp-40]=content
    fail = "wf_fail_" + name
    # path 校验
    em.mov_rd_mem(0, 5, -48)
    em.mov_rr(1, 0)
    em.lea_rip(2, "heap_base")
    em.sub_rr(1, 2)
    em.cmp_ri(1, HEAP_SIZE)
    em.jcc_rel32(0x83, fail)
    em.mov_rd_mem(1, 0, 0)
    em.cmp_ri(1, TYPE_STR)
    em.jcc_rel32(0x85, fail)
    # content 校验
    em.mov_rd_mem(0, 5, -40)
    em.mov_rr(1, 0)
    em.lea_rip(2, "heap_base")
    em.sub_rr(1, 2)
    em.cmp_ri(1, HEAP_SIZE)
    em.jcc_rel32(0x83, fail)
    em.mov_rd_mem(1, 0, 0)
    em.cmp_ri(1, TYPE_STR)
    em.jcc_rel32(0x85, fail)
    em.mov_rd_mem(0, 5, -48)                        # rax=path
    em.mov_rd_mem(1, 5, -40)                        # rcx=content
    em.lea_rip(2, mode_label)                       # rdx=mode
    em.call_rel32("fs_write")
    em.push_rax()
    _emit_epilogue(em)
    em.label_here(fail)
    em.lea_rip(0, "null_obj")
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_write_file(em: _Emitter):
    _emit_builtin_write_like(em, "_write_file", "mode_wb")


def _emit_builtin_append_file(em: _Emitter):
    _emit_builtin_write_like(em, "_append_file", "mode_ab")


def _emit_builtin_encode_like(em: _Emitter, name: str, base: int):
    """encode_binary/ternary/decimal(text)：UTF-8 解码逐码点 → base 进制，空格连接。"""
    t = "enc_" + name
    em.label_here("fn:" + name)
    _emit_prologue(em, 1, 8)                        # 参数 [rbp-64]=text
    em.mov_rd_mem(0, 5, -64)
    em.mov_rr(1, 0)
    em.lea_rip(2, "heap_base")
    em.sub_rr(1, 2)
    em.cmp_ri(1, HEAP_SIZE)
    em.jcc_rel32(0x83, t + "_fail")
    em.mov_rd_mem(1, 0, 0)
    em.cmp_ri(1, TYPE_STR)
    em.jcc_rel32(0x85, t + "_fail")
    # alloc(16 + 22*len + 2)
    em.mov_rd_mem(2, 0, 8)                          # rdx=len
    em.emit(b"\x48\x6B\xFA\x16")                    # imul rdi,rdx,22
    em.add_ri(7, 18)
    em.call_rel32("alloc")
    em.mov_mem_r(5, -56, 0)                         # obj
    em.emit(b"\x48\x8D\x78\x10")                    # lea rdi,[rax+16]
    em.mov_mem_r(5, -48, 7)                         # cursor=rdi
    em.mov_rd_mem(6, 5, -64)                        # rsi=src
    em.add_ri(6, 16)
    em.mov_mem_r(5, -40, 6)                         # [rbp-40]=src
    em.mov_rd_mem(2, 5, -64)
    em.mov_rd_mem(2, 2, 8)
    em.add_rr(2, 6)
    em.mov_mem_r(5, -24, 2)                         # [rbp-24]=end
    em.emit(b"\x48\xC7\x45\xF8\x01\x00\x00\x00")    # [rbp-8]=first=1
    em.label_here(t + "_loop")
    em.mov_rd_mem(6, 5, -40)
    em.mov_rd_mem(2, 5, -24)
    em.cmp_rr(6, 2)
    em.jcc_rel32(0x83, t + "_done")                 # jae
    em.call_rel32("enc_decode_cp")                  # rax=cp, rsi=next
    em.mov_mem_r(5, -40, 6)                         # save src
    em.emit(b"\x48\x83\x7D\xF8\x00")                # cmp qword [rbp-8],0
    em.jcc_rel32(0x85, t + "_nospace")              # 非首码点 → 先发空格
    em.mov_rd_mem(7, 5, -48)
    em.emit(b"\xC6\x07\x20")                        # mov byte [rdi],0x20
    em.emit(b"\x48\xFF\xC7")                        # inc rdi
    em.mov_mem_r(5, -48, 7)
    em.label_here(t + "_nospace")
    em.emit(b"\x48\xC7\x45\xF8\x00\x00\x00\x00")    # first=0
    em.emit(b"\xB9" + struct.pack("<I", base))      # mov ecx,base
    em.mov_rd_mem(7, 5, -48)
    em.call_rel32("enc_emit_int")
    em.mov_mem_r(5, -48, 0)                         # cursor=rax
    em.jcc_rel32(None, t + "_loop")
    em.label_here(t + "_done")
    em.mov_rd_mem(0, 5, -56)
    em.mov_rd_mem(1, 5, -48)
    em.sub_rr(1, 0)
    em.add_ri(1, -16)                               # len = cursor-(obj+16)
    em.mov_mem_r(0, 8, 1)
    em.emit(b"\xC7\x00" + struct.pack("<I", TYPE_STR))
    em.push_rax()
    _emit_epilogue(em)
    em.label_here(t + "_fail")
    em.lea_rip(0, "null_obj")
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_decode_like(em: _Emitter, name: str, base: int):
    """decode_binary/ternary/decimal(encoded)：空格分隔的 base 数字 → UTF-8 文本。"""
    t = "dec_" + name
    em.label_here("fn:" + name)
    _emit_prologue(em, 1, 8)                        # 参数 [rbp-64]=encoded
    em.mov_rd_mem(0, 5, -64)
    em.mov_rr(1, 0)
    em.lea_rip(2, "heap_base")
    em.sub_rr(1, 2)
    em.cmp_ri(1, HEAP_SIZE)
    em.jcc_rel32(0x83, t + "_fail")
    em.mov_rd_mem(1, 0, 0)
    em.cmp_ri(1, TYPE_STR)
    em.jcc_rel32(0x85, t + "_fail")
    # alloc(16 + 4*len + 1)
    em.mov_rd_mem(2, 0, 8)
    em.mov_rr(7, 2)
    em.shl_ri(7, 2)
    em.add_ri(7, 17)
    em.call_rel32("alloc")
    em.mov_mem_r(5, -56, 0)                         # obj
    em.emit(b"\x48\x8D\x78\x10")                    # lea rdi,[rax+16]
    em.mov_mem_r(5, -48, 7)                         # out cursor=rdi
    em.mov_rd_mem(6, 5, -64)
    em.add_ri(6, 16)
    em.mov_mem_r(5, -40, 6)                         # src cursor
    em.mov_rd_mem(2, 5, -64)
    em.mov_rd_mem(2, 2, 8)
    em.add_rr(2, 6)
    em.mov_mem_r(5, -24, 2)                         # end
    em.emit(b"\x48\xC7\x45\xF0\x00\x00\x00\x00")    # value=0
    em.emit(b"\x48\xC7\x45\xF8\x00\x00\x00\x00")    # in_token=0
    em.label_here(t + "_loop")
    em.mov_rd_mem(6, 5, -40)
    em.mov_rd_mem(2, 5, -24)
    em.cmp_rr(6, 2)
    em.jcc_rel32(0x83, t + "_end")                  # jae
    em.emit(b"\x0F\xB6\x06")                        # movzx eax,byte [rsi]
    em.emit(b"\x48\xFF\xC6")                        # inc rsi
    em.mov_mem_r(5, -40, 6)
    em.cmp_ri(0, 0x20)
    em.jcc_rel32(0x87, t + "_digit")                # ja 非空白
    em.emit(b"\x48\x83\x7D\xF8\x00")                # cmp qword [rbp-8],0
    em.jcc_rel32(0x84, t + "_loop")                 # 无待发令牌
    em.mov_rd_mem(0, 5, -16)
    em.mov_rd_mem(7, 5, -48)
    em.call_rel32("enc_utf8_out")
    em.mov_mem_r(5, -48, 0)
    em.emit(b"\x48\xC7\x45\xF0\x00\x00\x00\x00")    # value=0
    em.emit(b"\x48\xC7\x45\xF8\x00\x00\x00\x00")    # in_token=0
    em.jcc_rel32(None, t + "_loop")
    em.label_here(t + "_digit")
    em.emit(b"\x83\xE8\x30")                        # sub eax,0x30
    em.mov_rd_mem(1, 5, -16)
    em.emit(b"\x48\x6B\xC9" + bytes([base]))        # imul rcx,rcx,base
    em.add_rr(1, 0)
    em.mov_mem_r(5, -16, 1)
    em.emit(b"\x48\xC7\x45\xF8\x01\x00\x00\x00")    # in_token=1
    em.jcc_rel32(None, t + "_loop")
    em.label_here(t + "_end")
    em.emit(b"\x48\x83\x7D\xF8\x00")                # cmp qword [rbp-8],0
    em.jcc_rel32(0x84, t + "_finish")
    em.mov_rd_mem(0, 5, -16)
    em.mov_rd_mem(7, 5, -48)
    em.call_rel32("enc_utf8_out")
    em.mov_mem_r(5, -48, 0)
    em.label_here(t + "_finish")
    em.mov_rd_mem(0, 5, -56)
    em.mov_rd_mem(1, 5, -48)
    em.sub_rr(1, 0)
    em.add_ri(1, -16)
    em.mov_mem_r(0, 8, 1)
    em.emit(b"\xC7\x00" + struct.pack("<I", TYPE_STR))
    em.push_rax()
    _emit_epilogue(em)
    em.label_here(t + "_fail")
    em.lea_rip(0, "null_obj")
    em.push_rax()
    _emit_epilogue(em)


def _emit_builtin_encode_binary(em: _Emitter):
    _emit_builtin_encode_like(em, "encode_binary", 2)


def _emit_builtin_encode_ternary(em: _Emitter):
    _emit_builtin_encode_like(em, "encode_ternary", 3)


def _emit_builtin_encode_decimal(em: _Emitter):
    _emit_builtin_encode_like(em, "encode_decimal", 10)


def _emit_builtin_decode_binary(em: _Emitter):
    _emit_builtin_decode_like(em, "decode_binary", 2)


def _emit_builtin_decode_ternary(em: _Emitter):
    _emit_builtin_decode_like(em, "decode_ternary", 3)


def _emit_builtin_decode_decimal(em: _Emitter):
    _emit_builtin_decode_like(em, "decode_decimal", 10)


NATIVE_BUILTINS = (
    "len", "输出", "get", "错误", "调用捕获",
    # 砖块 16 阶段一：数值 + 转换核心
    "abs", "sign",
    "sin", "cos", "tan", "asin", "acos", "atan",
    "sinh", "cosh", "tanh",
    "exp", "log", "ln", "log10", "log2",
    "sqrt", "floor", "ceil", "trunc", "round",
    "deg2rad", "rad2deg",
    "int", "_to_int", "float", "_to_float", "str", "bool",
    "type_of", "typeof",
    "pow", "atan2", "hypot",
    # 砖块 16 阶段二：序列 + 字典原语
    "slice", "append", "mut_set_at",
    "_dict_keys", "_dict_values", "_dict_has", "_dict_put", "_dict_remove",
    # 集合字面量语法糖 {} / {1,2,3} / {x | cond} 的归约目标
    "构造集合",
    # 砖块 16 阶段三：基础原语 / 序列构造
    "ord", "chr", "list", "range",
    # 砖块 16 阶段三：文件 I/O
    "_read_file", "_write_file", "_append_file",
    # 砖块 16 阶段三：进制编解码
    "encode_binary", "decode_binary",
    "encode_ternary", "decode_ternary",
    "encode_decimal", "decode_decimal",
    # 砖块 17 阶段一：mathlib 数论
    "阶乘", "最大公约数", "最小公倍数", "排列数", "组合数",
    "素数判定", "素数筛", "杨辉三角",
    # 砖块 17 阶段一：mathlib 聚合
    "max", "min", "sum",
    # 砖块 17 阶段二：mathlib 逻辑运算
    "逻辑非", "逻辑与", "逻辑或", "逻辑蕴含", "逻辑异或", "逻辑双蕴含",
    # 砖块 17 阶段二：mathlib 集合运算
    "集合并", "集合交", "集合差", "集合补", "集合子集", "集合幂集", "集合基数",
    # 砖块 17 阶段三：mathlib 统计 / 随机
    "平均值", "中位数", "方差", "标准差", "协方差", "相关系数", "正态密度",
    "均匀随机", "正态随机",
)

# 需要按 arity 参与柯里化的内建。apply_rt 的 ar_plain 分支对纯文本地址直接
# tail-jmp，不看实参数，故 arity>1 的内建必须以闭包记录暴露，调用才会走
# ar_close 分支并按 arity 决定「偏应用 / 重建调用」。启动时在 _start 中各
# 分配一条 [TYPE_CLOSURE][fn][env=0][arity] 记录，指针存入数据槽 bclo:{name}。
_BUILTIN_ARITY = {
    "len": 1, "输出": 1, "get": 2, "错误": 1, "调用捕获": 2,
    # 砖块 16 阶段一
    "abs": 1, "sign": 1,
    "sin": 1, "cos": 1, "tan": 1, "asin": 1, "acos": 1, "atan": 1,
    "sinh": 1, "cosh": 1, "tanh": 1,
    "exp": 1, "log": 1, "ln": 1, "log10": 1, "log2": 1,
    "sqrt": 1, "floor": 1, "ceil": 1, "trunc": 1, "round": 1,
    "deg2rad": 1, "rad2deg": 1,
    "int": 1, "_to_int": 1, "float": 1, "_to_float": 1, "str": 1, "bool": 1,
    "type_of": 1, "typeof": 1,
    "pow": 2, "atan2": 2, "hypot": 2,
    # 砖块 16 阶段二
    "slice": 3, "append": 2, "mut_set_at": 3,
    "_dict_keys": 1, "_dict_values": 1, "_dict_has": 2,
    "_dict_put": 3, "_dict_remove": 2,
    "构造集合": 3,
    # 砖块 16 阶段三
    "ord": 1, "chr": 1, "list": 1, "range": 2,
    "_read_file": 1, "_write_file": 2, "_append_file": 2,
    "encode_binary": 1, "decode_binary": 1,
    "encode_ternary": 1, "decode_ternary": 1,
    "encode_decimal": 1, "decode_decimal": 1,
    # 砖块 17 阶段一
    "阶乘": 1, "最大公约数": 2, "最小公倍数": 2,
    "排列数": 2, "组合数": 2, "素数判定": 1, "素数筛": 1, "杨辉三角": 1,
    "max": 1, "min": 1, "sum": 1,
    # 砖块 17 阶段二
    "逻辑非": 1, "逻辑与": 2, "逻辑或": 2,
    "逻辑蕴含": 2, "逻辑异或": 2, "逻辑双蕴含": 2,
    "集合并": 2, "集合交": 2, "集合差": 2, "集合补": 2,
    "集合子集": 2, "集合幂集": 1, "集合基数": 1,
    # 砖块 17 阶段三
    "平均值": 1, "中位数": 1, "方差": 1, "标准差": 1,
    "协方差": 2, "相关系数": 2, "正态密度": 3,
    "均匀随机": 2, "正态随机": 2,
}
_CURRIED_BUILTINS = tuple(n for n, a in _BUILTIN_ARITY.items() if a > 1)

# name → 发射器（em 唯一参数）。数学类以默认参绑定避免闭包晚绑定。
_BUILTIN_EMITTERS: dict = {
    "len": _emit_builtin_len,
    "输出": _emit_builtin_print,
    "get": _emit_builtin_get,
    "错误": _emit_builtin_error,
    "调用捕获": _emit_builtin_guard,
    "abs": _emit_builtin_abs,
    "sign": _emit_builtin_sign,
    "int": lambda em: _emit_builtin_int(em, "int"),
    "_to_int": lambda em: _emit_builtin_int(em, "_to_int"),
    "float": lambda em: _emit_builtin_float(em, "float"),
    "_to_float": lambda em: _emit_builtin_float(em, "_to_float"),
    "str": _emit_builtin_str,
    "bool": _emit_builtin_bool,
    "pow": _emit_builtin_pow,
    "atan2": lambda em: _emit_builtin_bin2_crt(em, "atan2", "atan2"),
    "hypot": lambda em: _emit_builtin_bin2_crt(em, "hypot", "hypot"),
    "deg2rad": lambda em: _emit_builtin_math_scale(
        em, "deg2rad", 0.017453292519943295),
    "rad2deg": lambda em: _emit_builtin_math_scale(
        em, "rad2deg", 57.29577951308232),
    "type_of": lambda em: _emit_builtin_type_name(em, "type_of", _TYPEOF_EN),
    "typeof": lambda em: _emit_builtin_type_name(em, "typeof", _TYPEOF_ZH),
    # 砖块 16 阶段二
    "slice": _emit_builtin_slice,
    "append": _emit_builtin_append,
    "mut_set_at": _emit_builtin_mut_set_at,
    "_dict_keys": _emit_builtin_dict_keys,
    "_dict_values": _emit_builtin_dict_values,
    "_dict_has": _emit_builtin_dict_has,
    "_dict_put": _emit_builtin_dict_put,
    "_dict_remove": _emit_builtin_dict_remove,
    "构造集合": _emit_builtin_make_set,
    # 砖块 16 阶段三
    "ord": _emit_builtin_ord,
    "chr": _emit_builtin_chr,
    "list": _emit_builtin_list,
    "range": _emit_builtin_range,
    "_read_file": _emit_builtin_read_file,
    "_write_file": _emit_builtin_write_file,
    "_append_file": _emit_builtin_append_file,
    "encode_binary": _emit_builtin_encode_binary,
    "decode_binary": _emit_builtin_decode_binary,
    "encode_ternary": _emit_builtin_encode_ternary,
    "decode_ternary": _emit_builtin_decode_ternary,
    "encode_decimal": _emit_builtin_encode_decimal,
    "decode_decimal": _emit_builtin_decode_decimal,
    # 砖块 17 阶段一
    "阶乘": _emit_builtin_factorial,
    "最大公约数": _emit_builtin_gcd,
    "最小公倍数": _emit_builtin_lcm,
    "排列数": _emit_builtin_perm,
    "组合数": _emit_builtin_comb,
    "素数判定": _emit_builtin_is_prime,
    "素数筛": _emit_builtin_sieve,
    "杨辉三角": _emit_builtin_pascal,
    "max": lambda em: _emit_builtin_extremum(em, "max", True),
    "min": lambda em: _emit_builtin_extremum(em, "min", False),
    "sum": _emit_builtin_sum,
    # 砖块 17 阶段二
    "逻辑非": _emit_builtin_logic_not,
    "逻辑与": _emit_builtin_logic_and,
    "逻辑或": _emit_builtin_logic_or,
    "逻辑蕴含": _emit_builtin_logic_implies,
    "逻辑异或": _emit_builtin_logic_xor,
    "逻辑双蕴含": _emit_builtin_logic_iff,
    "集合并": lambda em: _emit_builtin_setop2(em, "集合并", "union"),
    "集合交": lambda em: _emit_builtin_setop2(em, "集合交", "inter"),
    "集合差": lambda em: _emit_builtin_setop2(em, "集合差", "diff"),
    "集合补": lambda em: _emit_builtin_setop2(em, "集合补", "diff"),
    "集合子集": _emit_builtin_subset,
    "集合幂集": _emit_builtin_powerset,
    "集合基数": _emit_builtin_cardinality,
    # 砖块 17 阶段三
    "平均值": _emit_builtin_mean,
    "中位数": _emit_builtin_median,
    "方差": _emit_builtin_variance,
    "标准差": _emit_builtin_stddev,
    "协方差": _emit_builtin_covariance,
    "相关系数": _emit_builtin_correlation,
    "正态密度": _emit_builtin_norm_pdf,
    "均匀随机": _emit_builtin_uniform,
    "正态随机": _emit_builtin_gauss,
}
for _n, _c in _CRT_FLOAT_UNARY.items():
    _BUILTIN_EMITTERS[_n] = (
        lambda em, n=_n, c=_c: _emit_builtin_math_float(em, n, c))
for _n, _c in _CRT_INT_ROUND.items():
    _BUILTIN_EMITTERS[_n] = (
        lambda em, n=_n, c=_c: _emit_builtin_math_round(em, n, c))

# VM 侧注册但原生后端尚未实现的名字。
# 用途：编译期对「本模块无定义、VM 却能解析」的全局给出明确错误，
# 避免运行期退化成「0 值被调用」（apply_rt → ar_plain → jmp rax=0）
# 那种无提示的访问违例。
# 与 vm.py 的 _vm_builtins() 保持对应：那里能 setdefault 到的名字。
_UNRESOLVED_GLOBALS = frozenset({
    # 基础原语
    "abs", "int", "_to_int", "float", "_to_float", "str", "bool", "list",
    "ord", "chr", "range", "type_of",
    # 序列/字典原语（get 已实现，见 NATIVE_BUILTINS）
    "slice", "append", "mut_set_at",
    "_dict_keys", "_dict_values", "_dict_has", "_dict_put", "_dict_remove",
    "_empty_dict",
    # 文件 I/O 与编码
    "_read_file", "_write_file", "_append_file",
    "encode_binary", "decode_binary",
    "encode_ternary", "decode_ternary",
    "encode_decimal", "decode_decimal",
    # 常量（异常原语 错误/调用捕获 已实现，见 NATIVE_BUILTINS）
    "MathaIOError", "真", "假", "null", "None",
})

# 宿主 mathlib 通过 _register_math_builtins 注册的数学/工具函数。
# 过滤掉单字母常量（G/c/g/R/e/pi…）：这些是数学常量而非函数，
# 本模块若真用到会在 VM 侧同样解析失败，误报只会掩盖真正的问题。
def _unresolved_mathlib_names() -> set:
    try:
        from src.mathlib import _register_math_builtins
    except Exception:
        return set()
    b: dict = {}
    try:
        _register_math_builtins(b)
    except Exception:
        return set()
    return set(k for k in b if isinstance(k, str) and len(k) > 1)


_UNRESOLVED_GLOBALS = ((_UNRESOLVED_GLOBALS | _unresolved_mathlib_names())
                       - set(NATIVE_BUILTINS))


# 砖块 15 浮点常量：宿主 mathlib 的 CONSTANTS（pi/e/tau/phi）与
# PHYSICAL_CONSTANTS（G/c/g/h_planck/N_A/R）。原生后端将它们作为静态
# TYPE_FLOAT 对象发射，LOAD_GLOBAL 据此解析（此前单字母常量会静默读成 0）。
def _math_constants() -> dict:
    try:
        from src.mathlib import CONSTANTS, PHYSICAL_CONSTANTS
    except Exception:
        return {}
    out = {}
    out.update(CONSTANTS)
    out.update(PHYSICAL_CONSTANTS)
    return out


_MATH_CONSTANTS = _math_constants()


def _emit_one(em: _Emitter, ins: tuple, consts: list, fn_names: set[str],
              tag: str, nlocals: int, idx: int = 0,
              capmap: dict | None = None, arity: dict | None = None,
              declared_globals: set | None = None, guard: bool = False):
    op = ins[0]
    if op == OP.PUSH_CONST:
        v = consts[ins[1]]
        if isinstance(v, bool):
            em.lea_rip(0, "bool_true" if v else "bool_false")
            em.push_rax()
        elif isinstance(v, int):
            em.mov_rax_imm64(v)
            em.push_rax()
        elif isinstance(v, str):
            em.lea_rip(0, f"sob:{ins[1]}")          # 静态字符串对象地址
            em.push_rax()
        elif isinstance(v, float):
            em.lea_rip(0, f"fob:{ins[1]}")          # 静态浮点对象地址
            em.push_rax()
        else:
            raise NativeNotSupported(
                f"原生后端暂不支持常量 {type(v).__name__}: {v!r}")
    elif op == OP.PUSH_TRUE:
        em.lea_rip(0, "bool_true")
        em.push_rax()
    elif op == OP.PUSH_FALSE:
        em.lea_rip(0, "bool_false")
        em.push_rax()
    elif op == OP.PUSH_NULL:
        em.lea_rip(0, "null_obj")
        em.push_rax()
    elif op == OP.LOAD_LOCAL:
        em.load_local(ins[1], nlocals)
    elif op == OP.STORE_LOCAL:
        em.store_local(ins[1], nlocals)
    elif op == OP.LOAD_BOX:
        slot = ins[1]
        em.emit(b"\x48\x8B\x85" + struct.pack("<i", -8 * (nlocals - slot)))
        em.emit(b"\x48\x8B\x40\x08")                # mov rax,[rax+8] box.value
        em.push_rax()
    elif op == OP.MAKE_BOX:
        slot = ins[1]
        em.emit(b"\x48\xC7\xC7\x10\x00\x00\x00")    # mov rdi,16
        em.call_rel32("alloc")
        em.emit(b"\x48\xC7\x00" + struct.pack("<I", TYPE_BOX))
        em.lea_rip(2, "null_obj")                   # lea rdx,[null_obj]
        em.emit(b"\x48\x89\x50\x08")                # mov [rax+8],rdx
        em.emit(b"\x48\x89\x85" + struct.pack("<i", -8 * (nlocals - slot)))
    elif op == OP.STORE_BOX:
        slot = ins[1]
        em.pop_to(0)                                # rax = 值
        em.emit(b"\x48\x8B\x95" + struct.pack("<i", -8 * (nlocals - slot)))
        em.emit(b"\x48\x89\x42\x08")                # mov [rdx+8],rax → box.value
    elif op == OP.LOAD_OUTER:
        _emit_load_outer(em, ins[1], ins[2], False, tag, nlocals)
    elif op == OP.LOAD_OUTER_BOX:
        _emit_load_outer(em, ins[1], ins[2], True, tag, nlocals)
    elif op == OP.LOAD_GLOBAL:
        name = consts[ins[1]]
        # 本模块 STORE_GLOBAL 定义过同名变量时优先读全局单元（如 `let get = 5`），
        # 否则读内建/函数。顺序很重要：内建名也会出现在 fn_names 里。
        # user_names（= arity 的键集）优先于同名内建：`func get` 是用户函数，
        # 不能去读内建 get 的闭包记录（该槽此时未初始化）。
        user_names = set(arity or ())
        shadowed = (declared_globals is not None and name in declared_globals
                    and name in NATIVE_BUILTINS)
        if name in fn_names and not shadowed:
            if name in _CURRIED_BUILTINS and name not in user_names:
                # arity>1 的内建：读启动期建好的闭包记录，使其调用走
                # ar_close 分支（否则 ar_plain 直接 tail-jmp，忽略实参数）
                em.load_global(f"bclo:{name}")
            else:
                em.lea_rip(0, f"fn:{name}")         # 函数代码地址
                em.push_rax()
        elif name in declared_globals and name not in fn_names:
            # 本模块 STORE_GLOBAL 定义过的名字，优先当作普通全局变量读取
            # （如 `let sqrt = 7`）。走这条路径不会退化为「0 值被调用」。
            em.load_global(f"cell:{name}")
        elif name in _MATH_CONSTANTS:
            # 砖块 15：数学/物理常量。浮点常量作为静态浮点对象发射（位于堆
            # 区间内，可被 is_float / str_float / 浮点算术正常处理）；整数
            # 常量（如光速 c = 299792458）按原生裸整数压栈。
            cv = _MATH_CONSTANTS[name]
            if isinstance(cv, bool) or not isinstance(cv, (int, float)):
                em.load_global(f"cell:{name}")
            elif isinstance(cv, int):
                em.mov_rax_imm64(cv)
                em.push_rax()
            else:
                em.lea_rip(0, f"const:{name}")
                em.push_rax()
        elif name == "_empty_dict":
            # 静态空字典对象：值而非可调用（不进 NATIVE_BUILTINS，故无 fn: 标签）。
            # 置于 _UNRESOLVED_GLOBALS 检查之前，避免误报「未实现全局」。
            em.lea_rip(0, "empty_dict")
            em.push_rax()
        elif name in ("真", "假", "null", "None"):
            # 值常量（非可调用）：True/False/None 静态对象。
            lbl = {"真": "bool_true", "假": "bool_false"}.get(name, "null_obj")
            em.lea_rip(0, lbl)
            em.push_rax()
        elif name in _UNRESOLVED_GLOBALS:
            # 名字在 VM 侧可解析为内建/函数，但原生后端未实现，且本模块没有
            # 把它定义成普通变量。直接发射会得到 0 值，调用时经
            # apply_rt → ar_plain 跳到 rax=0，表现为无提示的访问违例，
            # 比编译期报错难定位得多，故在此显式拒绝。
            raise NativeNotSupported(
                f"原生后端未实现全局 {name!r}：VM 侧的内建/函数在此模块中"
                f"无原生实现（已实现内建：{'、'.join(NATIVE_BUILTINS)}）。"
                f"若这是普通变量，请用与内建不冲突的名字，"
                f"或在本模块内先以 STORE_GLOBAL 定义。 @ {tag}[{idx}]")
        else:
            em.load_global(f"cell:{name}")
    elif op == OP.STORE_GLOBAL:
        em.store_global(f"cell:{consts[ins[1]]}")
    elif op == OP.MAKE_CLOSURE:
        _emit_make_closure(em, ins[1], (capmap or {}).get(ins[1], []),
                           tag, nlocals, (arity or {}).get(ins[1], 0))
    elif op == OP.CALL:
        _emit_call(em, ins[1], tag, idx)
    elif op == OP.RET:
        _emit_epilogue(em)
    elif op == OP.JMP:
        em.jcc_rel32(None, f"{tag}:{ins[1]}")
    elif op == OP.JZ:
        em.pop_to(0)
        em.call_rel32("truthy")                     # ZF=1 ⟺ 假值
        em.jcc_rel32(0x84, f"{tag}:{ins[1]}")      # jz
    elif op == OP.JNZ:
        em.pop_to(0)
        em.call_rel32("truthy")
        em.jcc_rel32(0x85, f"{tag}:{ins[1]}")      # jnz
    elif op == OP.BINOP:
        sym = consts[ins[1]]
        em.pop_to(1)                                # rcx = 右
        em.pop_to(0)                                # rax = 左
        # 浮点分派：任一操作数为浮点对象（或 `/` 恒真除）→ 走 SSE 路径。
        float_ok = (sym in _FLOAT_BINOPS or sym in _FLOAT_CC)
        if float_ok:
            fp = f"bo_fp_{tag}_{idx}"
            fdone = f"bo_fd_{tag}_{idx}"
            if sym == "/":
                em.jcc_rel32(None, fp)              # 真除恒浮点
            else:
                em.call_rel32("is_float2")
                em.emit(b"\x85\xD2")                # test edx,edx（保留 rax/rcx）
                em.jcc_rel32(0x85, fp)              # jnz → 浮点
        if sym == "+":
            # 按**两侧的类型标签**分派：字符串拼接 / 列表拼接 / 整数加。
            # 旧实现只判「左值是否落在堆区间」，于是 [1]+[2] 也走 str_concat，
            # 把两个列表对象的原始字节粘成一个假字符串输出（静默出错）。
            # 两侧都要校验，否则 [1] + {"k":1} 会把字典的键值对当元素拷进来。
            # is_float2 已排除容器，走到这里时两侧都不是浮点。
            lstr = f"bo_add_str_{tag}_{idx}"
            llist = f"bo_add_list_{tag}_{idx}"
            lchk = f"bo_add_chk_{tag}_{idx}"
            lints = f"bo_add_int_{tag}_{idx}"
            ldone = f"bo_add_done_{tag}_{idx}"
            lunsup = f"bo_add_unsup_{tag}_{idx}"
            em.mov_rr(8, 0)                         # r8=左
            em.mov_rr(9, 1)                         # r9=右
            em.mov_rr(2, 8)                         # mov rdx,r8
            em.lea_rip(10, "heap_base")             # lea r10,[heap_base]
            em.sub_rr(2, 10)                        # sub rdx,r10
            em.cmp_ri(2, HEAP_SIZE)                 # cmp rdx,HEAP_SIZE
            em.jcc_rel32(0x83, lchk)                # jae 左值非堆对象 → 只能是整数
            em.mov_rr(0, 8)                         # mov rax,r8
            em.emit(b"\x8B\x38")                    # mov edi,[rax]  左值类型
            em.emit(b"\x83\xFF" + bytes([TYPE_STR]))    # cmp edi,TYPE_STR
            em.jcc_rel32(0x84, lstr)
            em.emit(b"\x83\xFF" + bytes([TYPE_LIST]))   # cmp edi,TYPE_LIST
            em.jcc_rel32(0x84, llist)
            em.jcc_rel32(None, lunsup)              # 字典等容器 → 不支持
            # ---- 左值是裸整数 ----
            em.label_here(lchk)
            em.mov_rr(2, 9)                         # mov rdx,r9
            em.sub_rr(2, 10)                        # 复用 rdx-r10 判右值是否堆对象
            em.cmp_ri(2, HEAP_SIZE)
            em.jcc_rel32(0x83, lints)               # jae 两侧都是整数
            em.jcc_rel32(None, lunsup)              # 右值是容器但左侧不是 → 不支持
            em.label_here(lints)
            em.mov_rr(0, 8)                         # mov rax,左
            em.emit(b"\x4C\x01\xC8")                # add rax,r9
            em.jcc_rel32(None, ldone)
            # ---- 字符串拼接：右值也必须是字符串 ----
            em.label_here(lstr)
            em.mov_rr(2, 9)
            em.sub_rr(2, 10)
            em.cmp_ri(2, HEAP_SIZE)
            em.jcc_rel32(0x83, lunsup)
            em.mov_rr(0, 9)
            em.emit(b"\x8B\x30")                    # mov esi,[rax]  右值类型
            em.emit(b"\x83\xFE" + bytes([TYPE_STR]))    # cmp esi,TYPE_STR
            em.jcc_rel32(0x85, lunsup)
            em.mov_rr(0, 8)
            em.mov_rr(1, 9)
            em.call_rel32("str_concat")
            em.jcc_rel32(None, ldone)
            # ---- 列表拼接：右值也必须是列表 ----
            em.label_here(llist)
            em.mov_rr(2, 9)
            em.sub_rr(2, 10)
            em.cmp_ri(2, HEAP_SIZE)
            em.jcc_rel32(0x83, lunsup)
            em.mov_rr(0, 9)
            em.emit(b"\x8B\x30")                    # mov esi,[rax]  右值类型
            em.emit(b"\x83\xFE" + bytes([TYPE_LIST]))   # cmp esi,TYPE_LIST
            em.jcc_rel32(0x85, lunsup)
            em.mov_rr(0, 8)
            em.mov_rr(1, 9)
            em.call_rel32("list_concat")
            em.jcc_rel32(None, ldone)
            # 字典等不支持类型：与本后端 str()/not 的既有约定一致，返回 None，
            # 而不是静默吐出对象字节或崩在访问违例上。
            em.label_here(lunsup)
            em.lea_rip(0, "null_obj")
            em.label_here(ldone)
        elif sym == "-":
            em.emit(b"\x48\x29\xC8")                # sub rax,rcx
        elif sym == "*":
            # 类型分派：序列重复（字符串/列表 × 整数）与整数乘法。
            # 旧实现无条件 imul，于是 "ab" * 3 把堆地址当整数相乘，输出裸指针
            # 422100834892608（静默出错）。浮点已由前面的 is_float2 分流到 f_mul。
            lm = f"bo_mul_str_{tag}_{idx}"
            ll = f"bo_mul_list_{tag}_{idx}"
            lchk = f"bo_mul_chk_{tag}_{idx}"
            lints = f"bo_mul_int_{tag}_{idx}"
            ldone = f"bo_mul_done_{tag}_{idx}"
            lunsup = f"bo_mul_unsup_{tag}_{idx}"
            lswap = f"bo_mul_swap_{tag}_{idx}"
            lseq = f"bo_mul_seq_{tag}_{idx}"
            em.mov_rr(8, 0)                         # r8=左
            em.mov_rr(9, 1)                         # r9=右
            em.mov_rr(2, 8)                         # mov rdx,r8
            em.lea_rip(10, "heap_base")             # lea r10,[heap_base]
            em.sub_rr(2, 10)                        # sub rdx,r10
            em.cmp_ri(2, HEAP_SIZE)
            em.jcc_rel32(0x83, lchk)                # jae 左侧非序列 → 只能是整数
            em.mov_rr(0, 8)
            em.emit(b"\x8B\x38")                    # mov edi,[rax]  左侧类型
            em.emit(b"\x83\xFF" + bytes([TYPE_STR]))
            em.jcc_rel32(0x84, lm)
            em.emit(b"\x83\xFF" + bytes([TYPE_LIST]))
            em.jcc_rel32(0x84, ll)
            em.jcc_rel32(None, lunsup)              # 字典等 → 不支持
            # ---- 左侧是整数：检查右侧 ----
            em.label_here(lchk)
            em.mov_rr(2, 9)
            em.sub_rr(2, 10)
            em.cmp_ri(2, HEAP_SIZE)
            em.jcc_rel32(0x83, lints)               # 两侧都是整数
            # 右序列 × 左整数：交换成 (序列, 次数) 交给 seq_repeat
            # 此处左侧已确认不是堆指针（是整数），绝不能解引用它：必须读右侧类型。
            em.mov_rr(0, 9)                         # mov rax,右
            em.emit(b"\x8B\x30")                    # mov esi,[rax]  右侧类型
            em.emit(b"\x83\xFE" + bytes([TYPE_STR]))
            em.jcc_rel32(0x85, lswap)
            em.emit(b"\x83\xFE" + bytes([TYPE_LIST]))
            em.jcc_rel32(0x85, lswap)
            em.jcc_rel32(None, lunsup)              # 两侧都是容器且左非序列
            em.label_here(lswap)
            em.mov_rr(1, 8)                         # mov rcx,左（次数）
            em.mov_rr(0, 9)                         # mov rax,右（序列）
            em.call_rel32("seq_repeat")
            em.jcc_rel32(None, ldone)
            # ---- 整数 × 整数 ----
            em.label_here(lints)
            em.mov_rr(0, 8)                         # mov rax,左
            em.emit(b"\x48\x0F\xAF\xC1")            # imul rax,rcx
            em.jcc_rel32(None, ldone)
            # ---- 序列 × 整数（左侧为字符串或列表）----
            em.label_here(lm)
            em.jcc_rel32(None, lseq)
            em.label_here(ll)
            em.label_here(lseq)
            em.mov_rr(2, 9)
            em.sub_rr(2, 10)
            em.cmp_ri(2, HEAP_SIZE)
            # jb ⟺ 右值也是堆对象 ⟹ 序列 × 序列 不支持。
            # 注意与 `+` 的分支相反：这里「右值不是堆对象」才是被支持的情形
            # （字符串/列表 × 整数），早期把 jae 当成不支持，导致 "ab" * 3
            # 一路走到 lunsup 返回 None。
            em.jcc_rel32(0x82, lunsup)              # jb   右值是容器 → 不支持
            em.mov_rr(0, 8)                         # mov rax,左（序列）
            em.mov_rr(1, 9)                         # mov rcx,右（次数）
            em.call_rel32("seq_repeat")
            em.jcc_rel32(None, ldone)
            em.label_here(lunsup)
            em.lea_rip(0, "null_obj")
            em.label_here(ldone)
        elif sym == "//":
            # Python 的 `//` 是**向下取整**，x86 的 idiv 是**向零截断**：
            # -7 // 2 应为 -4 而非 -3。符号修正与除零检查都在 int_floordiv 里。
            em.call_rel32("int_floordiv")
        elif sym == "%":
            # Python 的 `%` 取**除数**的符号（-7 % 2 == 1，7 % -2 == -1），
            # 与 idiv 余数取被除数符号的约定相反，故同样要在 int_mod 里修正。
            em.call_rel32("int_mod")
        elif sym == "**":
            # 整数幂：rax=底，rcx=指数。
            # 负指数在 Python 里提升为浮点（2 ** -1 == 0.5），不是整数 0；
            # 整数幂的连乘循环遇到负指数只能给出 0，故此处转交 f_pow
            # （crt_pow 与 VM 的 float.__pow__ 逐位一致）。
            # 但 0 的负幂 VM 抛 ZeroDivisionError，pow(0.0,-1.0) 只会给 inf。
            top = f"pow_{tag}_{idx}_top"
            end = f"pow_{tag}_{idx}_end"
            fin = f"pow_{tag}_{idx}_fin"
            lz = f"pow_{tag}_{idx}_zero"
            # mov rdx,1 须用 C7 /0 的 imm32 形式：
            # B8+rd 配 REX.W 是 imm64（10 字节），只发 4 字节会错位指令流
            em.emit(b"\x48\xC7\xC2\x01\x00\x00\x00")  # mov rdx,1  累乘器
            em.emit(b"\x48\x85\xC9")                # test rcx,rcx
            em.jcc_rel32(0x89, top)                 # jns  top（指数非负）
            em.emit(b"\x48\x85\xC0")                # test rax,rax
            em.jcc_rel32(0x84, lz)                  # jz   0 的负幂 → 抛错
            em.call_rel32("f_pow")                  # 负指数 → 浮点幂（rax=boxed float）
            em.jcc_rel32(None, end)
            em.label_here(lz)
            em.lea_rip(0, "err_powzero")
            em.call_rel32("raise_rt")               # 不返回
            em.emit(b"\x0F\x0B")                    # ud2
            em.label_here(top)
            em.emit(b"\x48\x85\xC9")                # test rcx,rcx
            em.jcc_rel32(0x84, fin)                 # jz   fin
            em.emit(b"\x48\x0F\xAF\xD0")            # imul rdx,rax（rdx*=rax）
            em.emit(b"\x48\xFF\xC9")                # dec rcx
            em.jcc_rel32(None, top)
            em.label_here(fin)
            em.emit(b"\x48\x89\xD0")                # mov rax,rdx
            em.label_here(end)
        elif sym == "in":
            em.call_rel32("seq_contains")              # rax=左元素 rcx=右容器
            _emit_rax_to_bool(em, tag, f"{idx}m")
        elif sym in ("<<", ">>"):
            # 与 vm._BINOPS 的 Python `a << b` / `a >> b` 对齐。两处易错点：
            # 1. `>>` 必须用 SAR（算术），用 SHR 会把 -8>>1 算成 +4。
            # 2. x86「按 cl 移位」只取计数低 6 位（0..63），Python 则对
            #    b >= 64 直接给结果，故超范围必须单独处理，不能交给硬件。
            # 负移位数 Python 抛 ValueError，这里按 0 处理（不崩溃优先）。
            sar = (sym == ">>")
            lneg = f"sh_neg_{tag}_{idx}"
            lbig = f"sh_big_{tag}_{idx}"
            lzero = f"sh_zero_{tag}_{idx}"
            lend = f"sh_end_{tag}_{idx}"
            em.emit(b"\x48\x85\xC9")                    # test rcx,rcx
            em.jcc_rel32(0x88, lneg)                    # js   负移位
            em.emit(b"\x48\x83\xF9\x40")                # cmp rcx,64
            em.jcc_rel32(0x83, lbig)                    # jae  超范围（注意无符号）
            em.emit(b"\x48\xD3\xF8" if sar else b"\x48\xD3\xE0")  # sar/shl rax,cl
            em.jcc_rel32(None, lend)
            em.label_here(lbig)
            if sar:
                # >> 移出全部有效位后是符号填充：负数恒为 -1。
                # 必须在清零之前判断符号，否则测的已是零值。
                em.emit(b"\x48\x85\xC0")                # test rax,rax
                em.jcc_rel32(0x89, lzero)               # jns  非负 → 0
                em.emit(b"\x48\xC7\xC0\xFF\xFF\xFF\xFF")  # mov rax,-1
                em.jcc_rel32(None, lend)
                em.label_here(lzero)
            em.emit(b"\x48\x31\xC0")                    # xor eax,eax
            em.jcc_rel32(None, lend)
            em.label_here(lneg)
            em.emit(b"\x48\x31\xC0")                    # xor eax,eax（负移位 → 0）
            em.label_here(lend)
        elif sym in _CC:
            if sym in ("==", "!="):
                # 字符串内容比较（左值为堆指针）；否则整数比较。
                lstr = f"bo_cmp_str_{tag}_{idx}"
                ldone = f"bo_cmp_done_{tag}_{idx}"
                em.emit(b"\x48\x89\xC2")            # mov rdx,rax
                em.lea_rip(8, "heap_base")          # lea r8,[heap_base]
                em.emit(b"\x4C\x29\xC2")            # sub rdx,r8
                em.emit(b"\x48\x81\xFA" + struct.pack("<I", HEAP_SIZE))
                em.jcc_rel32(0x82, lstr)            # jb str
                em.emit(b"\x48\x39\xC8")            # cmp rax,rcx
                em.emit(bytes([0x0F, _CC[sym], 0xC0]))  # setCC al
                em.emit(b"\x0F\xB6\xC0")            # movzx eax,al
                _emit_rax_to_bool(em, tag, f"{idx}i")
                em.jcc_rel32(None, ldone)           # jmp done
                em.label_here(lstr)
                em.call_rel32("str_eq")
                if sym == "!=":
                    em.emit(b"\x48\x83\xF0\x01")    # xor rax,1
                _emit_rax_to_bool(em, tag, f"{idx}s")
                em.label_here(ldone)
            else:
                em.emit(b"\x48\x39\xC8")            # cmp rax,rcx
                em.emit(bytes([0x0F, _CC[sym], 0xC0]))  # setCC al
                em.emit(b"\x0F\xB6\xC0")            # movzx eax,al
                _emit_rax_to_bool(em, tag, idx)
        elif sym == "/":
            pass                                    # 恒浮点，已跳 fp
        else:
            raise NativeNotSupported(f"原生后端暂不支持二元运算 {sym!r}")
        if float_ok:
            em.jcc_rel32(None, fdone)
            em.label_here(fp)
            if sym in _CC:
                em.call_rel32("float_cmp2")
                em.emit(bytes([0x0F, _FLOAT_CC[sym], 0xC0]))  # setCC al
                em.emit(b"\x0F\xB6\xC0")            # movzx eax,al
                _emit_rax_to_bool(em, tag, f"{idx}fl")
            else:
                em.call_rel32(_FLOAT_BINOPS[sym])
            em.label_here(fdone)
        em.push_rax()
    elif op == OP.UNARYOP:
        sym = consts[ins[1]]
        if sym == "neg":
            lf = f"neg_f_{tag}_{idx}"
            ld = f"neg_d_{tag}_{idx}"
            em.read_top_to(0)                       # rax=栈顶
            em.call_rel32("is_float")
            em.emit(b"\x85\xC0")                    # test eax,eax
            em.jcc_rel32(0x85, lf)                  # 浮点 → f_neg
            em.emit(b"\x49\xF7\x5C\x24\xF8")        # neg qword [r12-8]（整数）
            em.jcc_rel32(None, ld)
            em.label_here(lf)
            em.call_rel32("f_neg")                  # rax 为浮点对象 → 取反
            em.emit(b"\x49\x89\x44\x24\xF8")        # mov [r12-8],rax
            em.label_here(ld)
        elif sym == "not":
            lf = f"not_f_{tag}_{idx}"
            ld = f"not_d_{tag}_{idx}"
            em.pop_to(0)
            em.call_rel32("truthy")                 # ZF=1 ⟺ 假值
            em.jcc_rel32(0x85, lf)                  # 真 → not 为 False
            em.lea_rip(0, "bool_true")
            em.jcc_rel32(None, ld)
            em.label_here(lf)
            em.lea_rip(0, "bool_false")
            em.label_here(ld)
            em.push_rax()
        elif sym == "sqrt":
            em.read_top_to(0)                       # rax=栈顶（不弹出）
            em.call_rel32("f_sqrt")                 # 完全平方→整数，否则→浮点对象
            em.emit(b"\x49\x89\x44\x24\xF8")        # mov [r12-8],rax（就地替换）
        else:
            raise NativeNotSupported(f"原生后端暂不支持一元运算 {sym!r}")
    elif op == OP.DUP:
        em.read_top_to(0)
        em.push_rax()
    elif op == OP.POP:
        em.discard()
    elif op == OP.OUTPUT:
        em.pop_to(0)                                # rax = 栈顶值
        em.call_rel32("print_value")
        em.call_rel32("print_nl")
    elif op == OP.BUILD_LIST:
        n = ins[1]
        em.emit(b"\x48\xC7\xC7" + struct.pack("<i", 16 + 8 * n))  # mov rdi,16+8n
        em.call_rel32("alloc")
        em.emit(b"\x48\xC7\x00" + struct.pack("<I", TYPE_LIST))   # mov [rax],TYPE_LIST
        em.emit(b"\x48\xC7\x40\x08" + struct.pack("<i", n))       # mov [rax+8],n
        em.emit(b"\x4C\x89\xE6")                                  # mov rsi,r12
        em.emit(b"\x48\x81\xEE" + struct.pack("<i", 8 * n))       # sub rsi,8n
        em.emit(b"\x48\x8D\x78\x10")                              # lea rdi,[rax+16]
        em.emit(b"\x48\xC7\xC1" + struct.pack("<i", n))           # mov rcx,n
        em.emit(b"\xF3\x48\xA5")                                  # rep movsq
        em.emit(b"\x49\x81\xEC" + struct.pack("<i", 8 * n))       # sub r12,8n
        em.push_rax()
    elif op == OP.BUILD_DICT:
        n = ins[1]
        bl = f"bd_loop_{tag}_{idx}"
        be = f"bd_end_{tag}_{idx}"

        em.emit(b"\x48\xC7\xC7" + struct.pack("<i", 16 + 16 * n))  # mov rdi,16+16n
        em.call_rel32("alloc")
        em.emit(b"\x48\xC7\x00" + struct.pack("<I", TYPE_DICT))   # mov [rax],TYPE_DICT
        em.emit(b"\x48\xC7\x40\x08" + struct.pack("<i", n))       # mov [rax+8],n
        em.emit(b"\x48\x8D\x78\x10")                              # lea rdi,[rax+16]（pair 数组）
        em.emit(b"\x4C\x89\xE6")                                  # mov rsi,r12
        em.emit(b"\x48\x81\xEE" + struct.pack("<i", 16 * n))      # sub rsi,16n（起始 pair）
        em.emit(b"\x48\xC7\xC1" + struct.pack("<i", 2 * n))       # mov rcx,2n（qwords）
        em.emit(b"\xF3\x48\xA5")                                  # rep movsq
        em.emit(b"\x49\x81\xEC" + struct.pack("<i", 16 * n))      # sub r12,16n
        em.push_rax()
    elif op == OP.GET_ATTR:
        em.pop_to(0)                                # rax = 对象
        lmiss = f"ga_miss_{tag}_{idx}"
        ldone = f"ga_done_{tag}_{idx}"
        em.emit(b"\x48\x89\xC1")                    # mov rcx,rax
        em.lea_rip(2, "heap_base")                  # lea rdx,[heap_base]
        em.emit(b"\x48\x29\xD1")                    # sub rcx,rdx
        em.emit(b"\x48\x81\xF9" + struct.pack("<I", HEAP_SIZE))
        em.jcc_rel32(0x83, lmiss)                   # jae：非指针对象
        em.emit(b"\x4C\x8B\x00")                    # mov r8,[rax]
        em.emit(b"\x49\x83\xF8" + bytes([TYPE_DICT]))
        em.jcc_rel32(0x85, lmiss)                   # jne：非 dict
        em.lea_rip(8, f"sob:{ins[1]}")              # lea r8,[sob:键]
        em.emit(b"\x4C\x89\xC1")                    # mov rcx,r8（键）
        em.call_rel32("dict_get")
        em.jcc_rel32(None, ldone)
        em.label_here(lmiss)
        em.lea_rip(0, "null_obj")
        em.label_here(ldone)
        em.push_rax()
    elif op == OP.UNPACK_SEQ:
        # 弹出序列，依次压入第 0..n-1 个元素（缺项压 null_obj）。
        # 语义对齐 vm.py:515（seq 为 None 视为空序列，越界补 None）。
        _emit_unpack_seq(em, ins[1], tag, idx)
    elif op == OP.BUILD_SLICE:
        em.pop_to(2)                                # rdx = stop
        em.pop_to(1)                                # rcx = start
        em.pop_to(0)                                # rax = 容器
        em.call_rel32("build_slice")
        em.push_rax()
    elif op == OP.INDEX_GET:
        em.pop_to(1)                                # rcx = 下标
        em.pop_to(0)                                # rax = 容器
        _emit_getitem(em, f"ix_{tag}_{idx}")
        em.push_rax()
    elif op == OP.RAISE:
        em.pop_to(0)                                # rax = 抛出值
        em.call_rel32("raise_rt")                   # 不返回（展开或终止）
        em.emit(b"\x0F\x0B")                        # ud2
    elif op == OP.HALT:
        em.emit(b"\x31\xC9")                        # xor ecx,ecx
        em.call_rip_indirect("api_ExitProcess")
        em.emit(b"\x0F\x0B")                        # ud2
    else:
        raise NativeNotSupported(
            f"原生后端暂不支持操作码 0x{op:02X}（{OP.name(op)}）@ {tag}")


def _declared_globals(mod) -> set:
    """本模块中经 STORE_GLOBAL 定义过的名字集合。

    用于区分「普通全局变量」与「未实现的 VM 内建」：若 `let get = 5`
    在本模块内定义过 get，则 LOAD_GLOBAL get 应读全局单元而非报错。
    """
    names: set = set()
    all_code = [mod.main_code] + [f.code for f in mod.functions.values()]
    for code in all_code:
        for ins in code:
            if len(ins) > 1 and ins[0] == OP.STORE_GLOBAL:
                names.add(mod.constants[ins[1]])
    return names


def _emit_code(em: _Emitter, code: list, consts: list, fn_names: set[str],
               tag: str, nlocals: int, capmap: dict | None = None,
               arity: dict | None = None, declared_globals: set | None = None,
               guard: bool = False):
    for i, ins in enumerate(code):
        em.label_here(f"{tag}:{i}")
        _emit_one(em, ins, consts, fn_names, tag, nlocals, i,
                  capmap=capmap, arity=arity, declared_globals=declared_globals,
                  guard=guard)


# ---------------------------------------------------------------- 载荷

def _build_emitters(mod) -> tuple["_Emitter", "_Emitter", dict]:
    """构建代码/数据发射器（未 patch），供 _build_payload 与调试工具复用。"""
    labels: dict[str, int] = {}
    user_names = set(mod.functions.keys())
    builtin_names = [b for b in NATIVE_BUILTINS if b not in user_names]
    fn_names = user_names | set(builtin_names)
    # 只有当 调用捕获 未被用户函数遮蔽时才具备异常落地点；否则 raise 恒走
    # 「未捕获」终止路径（raise_rt 不可引用不存在的 调用捕获:land）。
    guard = "调用捕获" in builtin_names
    capmap = _closure_captures(mod.functions)
    arities = {n: f.arity for n, f in mod.functions.items()}
    declared_globals = _declared_globals(mod)

    for name, fn in mod.functions.items():
        if fn.arity > MAX_NATIVE_ARITY:
            raise NativeNotSupported(
                f"原生后端函数参数上限 {MAX_NATIVE_ARITY}：{name} 有 {fn.arity} 个参数")

    # ---- 代码：_start（模块初始化）----
    ec = _Emitter(TEXT_RVA, labels)    # 代码节
    ec.label_here("_start")
    ec.store_rip_from("stack_top", 4)               # mov [rip+stack_top],rsp（GC 根界）
    ec.lea_rip(12, "vstack")                        # lea r12,[vstack]
    # 入口 RSP=16n+8；sub rsp,0x28 使 CALL 时 RSP 16 字节对齐并留影子空间
    ec.emit(b"\x48\x83\xEC\x28")
    ec.emit(b"\x45\x31\xED")                        # xor r13d,r13d（main 环境=null）
    _emit_resolve_apis(ec)                          # PEB 遍历解析 kernel32 API
    ec.call_rel32("load_crt")                       # 加载 CRT（浮点格式化）
    # 初始化堆指针 = 静态对象区之后；heap_limit = heap_base + HEAP_SIZE
    ec.lea_rip(0, "heap_free")                      # lea rax,[heap_free]
    ec.emit(b"\x48\x89\x05")                        # mov [rip+heap_ptr],rax
    ec.rel32_to("heap_ptr")
    ec.lea_rip(0, "heap_base")                      # lea rax,[heap_base]
    ec.add_ri(0, HEAP_SIZE)                         # add rax,HEAP_SIZE
    ec.store_rip_from("heap_limit", 0)
    # 初始化异常处理器栈：hstack_ptr = hstack，handler_top = 0（空），raise_msg = 0
    ec.lea_rip(0, "hstack")                         # lea rax,[hstack]
    ec.store_rip_from("hstack_ptr", 0)
    ec.xor_rr32(0, 0)                               # xor eax,eax
    ec.store_rip_from("handler_top", 0)
    ec.store_rip_from("raise_msg", 0)
    ec.label_here("main_entry")
    _emit_builtin_closure_init(ec, [b for b in builtin_names
                                    if b in _CURRIED_BUILTINS])
    # GC 只回收此点之后分配的堆；内建闭包（bclo:*）视为永久根，不移动/不回收。
    ec.emit(b"\x48\x8B\x05")                        # mov rax,[rip+heap_ptr]
    ec.rel32_to("heap_ptr")
    ec.store_rip_from("sweep_start", 0)
    _emit_code(ec, mod.main_code, mod.constants, fn_names, "main", 0,
               capmap=capmap, arity=arities, declared_globals=declared_globals,
               guard=guard)

    # ---- 代码：各用户函数 ----
    for name, fn in mod.functions.items():
        ec.label_here(f"fn:{name}")
        _emit_prologue(ec, fn.arity, fn.nlocals)
        _emit_code(ec, fn.code, mod.constants, fn_names, f"fn:{name}",
                   fn.nlocals, capmap=capmap, arity=arities,
                   declared_globals=declared_globals, guard=guard)
        ec.emit(b"\x0F\x0B")                        # 保险（RET 后不可达）

    # ---- 代码：内建函数 ----
    for _bn in builtin_names:
        _emitter = _BUILTIN_EMITTERS.get(_bn)
        if _emitter is not None:
            _emitter(ec)

    # ---- 代码：print_int + 堆/字符串运行时 ----
    _emit_print_int(ec)
    _emit_heap_runtime(ec)
    _emit_gc_runtime(ec)                           # 堆 GC 运行时
    _emit_seq_dict_runtime(ec)                     # 序列/字典原语运行时
    _emit_fs_runtime(ec)                           # 文件 I/O 运行时
    _emit_encoding_runtime(ec)                     # 进制编解码运行时
    _emit_mathlib_runtime(ec)                      # mathlib 数论/集合运行时
    _emit_slice(ec)                                # 切片运行时（BUILD_SLICE）
    _emit_in_rt(ec)                                # 成员判断运行时（BINOP 'in'）
    _emit_apply_runtime(ec)                     # 函数值分派（闭包/偏应用）
    _emit_exception_runtime(ec, guard)          # 异常运行时（raise/错误/调用捕获）
    _emit_load_crt(ec)                          # CRT 加载（浮点格式化）
    _emit_float_runtime(ec)                     # 浮点运行时
    return _emit_data_section(mod, labels, ec, user_names)


def _emit_load_crt(em: _Emitter):
    """load_crt：LoadLibraryA("ucrtbase.dll"/"msvcrt.dll") + GetProcAddress 填充
    crt_<fn> 槽。ucrtbase 优先（其 _ecvt 提供精确十进制展开）。"""
    em.label_here("load_crt")
    em.emit(b"\x55\x48\x89\xE5")                    # push rbp; mov rbp,rsp
    em.emit(b"\x48\x83\xE4\xF0")                    # and rsp,-16
    em.emit(b"\x48\x83\xEC\x30")                    # sub rsp,0x30
    em.lea_rip(1, "crt_dll_ucrt")                   # rcx="ucrtbase.dll"
    em.call_rip_indirect("api_LoadLibraryA")
    em.test_rr(0, 0)
    em.jcc_rel32(0x85, "lc_got")                    # jnz got
    em.lea_rip(1, "crt_dll_msvcrt")                 # rcx="msvcrt.dll"
    em.call_rip_indirect("api_LoadLibraryA")
    em.label_here("lc_got")
    em.store_rip_from("crt_module", 0)
    for fn in _CRT_FUNCS:
        em.load_rip_to(1, "crt_module")             # rcx=hmodule
        em.lea_rip(2, f"crtname_{fn}")              # rdx=name
        em.call_rip_indirect("api_GetProcAddress")
        em.store_rip_from(f"crt_{fn}", 0)
    em.emit(b"\x48\x89\xEC\x5D\xC3")                # mov rsp,rbp; pop rbp; ret


def _emit_float_runtime(em: _Emitter):
    """浮点运行时：装箱 double（TYPE_FLOAT 对象）+ SSE 算术 + CRT 精确 repr。"""
    # ---- is_float(rax) → eax=1/0 ----
    em.label_here("is_float")
    em.mov_rr(2, 0)                                 # mov rdx,rax
    em.lea_rip(1, "heap_base")                      # lea rcx,[heap_base]
    em.sub_rr(2, 1)                                 # sub rdx,rcx
    em.cmp_ri(2, HEAP_SIZE)
    em.jcc_rel32(0x83, "isf_no")                    # jae：非堆指针
    em.emit(b"\x48\x83\x38" + bytes([TYPE_FLOAT]))  # cmp qword[rax],TYPE_FLOAT
    em.jcc_rel32(0x85, "isf_no")
    em.emit(b"\xB8\x01\x00\x00\x00")                # mov eax,1
    em.emit(b"\xC3")
    em.label_here("isf_no")
    em.emit(b"\x31\xC0\xC3")                        # xor eax,eax; ret

    # ---- is_float2(rax,rcx) → edx=1/0（完整保留 rax/rcx）----
    # 返回值放 edx 而非 eax：eax 是 rax 低 32 位，用 eax 返回 0 会把左操作数清零。
    # 容器（字符串/列表/字典）永远不是浮点，必须先排除：否则 [1]+1.5 会因为
    # 右操作数是浮点而走 SSE 路径，把列表指针当浮点对象读出垃圾。
    em.label_here("is_float2")
    em.mov_rr(8, 0)                                 # mov r8,rax
    em.mov_rr(9, 1)                                 # mov r9,rcx
    em.call_rel32("is_container")
    em.emit(b"\x85\xC0")                            # test eax,eax
    em.jcc_rel32(0x85, "isf2_no")
    em.mov_rr(0, 9)                                 # mov rax,r9
    em.call_rel32("is_container")
    em.emit(b"\x85\xC0")
    em.jcc_rel32(0x85, "isf2_no")
    # 上面把 rax 改成了右操作数；判左操作数是否浮点前必须改回 r8，
    # 否则 `1.5 + 2`（左浮右整）会拿右值判两次而误判为非浮点，
    # 走整数路径把堆指针当整数相加/相乘。
    em.mov_rr(0, 8)                                 # mov rax,r8
    em.call_rel32("is_float")
    em.emit(b"\x85\xC0")                            # test eax,eax
    em.jcc_rel32(0x85, "isf2_yes")
    em.mov_rr(0, 9)                                 # mov rax,r9
    em.call_rel32("is_float")
    em.emit(b"\x85\xC0")
    em.jcc_rel32(0x85, "isf2_yes")
    em.label_here("isf2_no")
    em.mov_rr(0, 8)                                 # mov rax,r8
    em.mov_rr(1, 9)                                 # mov rcx,r9
    em.emit(b"\x31\xD2\xC3")                        # xor edx,edx; ret
    em.label_here("isf2_yes")
    em.mov_rr(0, 8)                                 # mov rax,r8
    em.mov_rr(1, 9)                                 # mov rcx,r9
    em.emit(b"\xBA\x01\x00\x00\x00\xC3")            # mov edx,1; ret

    # ---- int_floordiv / int_mod：Python 整除语义（rax=a, rcx=b → rax）----
    # 两处必须纠正 x86 idiv 的默认行为：
    # 1. idiv 向**零**截断，Python 的 `//` 向下取整：`//` 在余数非零且
    #    被除数与除数异号时商要再减 1（-7 // 2 应为 -4，idiv 给 -3）。
    # 2. idiv 的余数取**被除数**的符号，而 Python 的 `%` 取**除数**的符号：
    #    异号时余数要加上除数（-7 % 2 应为 1，idiv 给 -1）。
    #    余数非零时 sign(余数)=sign(被除数)，故两条都用「余数与除数异号」判定。
    # 除数为 0 抛 "division by zero"，对齐 VM 的 ZeroDivisionError；不拦的话
    # idiv 直接触发 #DE（退出码 0xC0000094），是硬崩溃而非可捕获异常。
    # 除数为 -1 单独短路：既省一次除法，也避开 INT64_MIN / -1 的 #DE 溢出。
    for lbl, is_mod in (("int_floordiv", False), ("int_mod", True)):
        em.label_here(lbl)
        em.emit(b"\x55\x48\x89\xE5")                # push rbp; mov rbp,rsp
        em.emit(b"\x48\x83\xE4\xF0")                # and rsp,-16
        em.emit(b"\x48\x83\xEC\x40")                # sub rsp,0x40
        em.test_rr(1, 1)                            # test rcx,rcx
        em.jcc_rel32(0x85, lbl + "_ok")             # jnz 非零
        em.lea_rip(0, "err_divzero")
        em.call_rel32("raise_rt")                   # 不返回
        em.emit(b"\x0F\x0B")                        # ud2
        em.label_here(lbl + "_ok")
        em.cmp_ri(1, -1)
        em.jcc_rel32(0x85, lbl + "_div")            # jnz 常规 idiv
        em.emit(b"\x31\xC0" if is_mod else b"\x48\xF7\xD8")
        # is_mod: a % -1 == 0；否则 a // -1 == -a
        em.emit(b"\x48\x89\xEC\x5D\xC3")            # mov rsp,rbp; pop rbp; ret
        em.label_here(lbl + "_div")
        em.emit(b"\x48\x99")                        # cqo
        em.emit(b"\x48\xF7\xF9")                    # idiv rcx
        em.test_rr(2, 2)                            # test rdx,rdx
        em.jcc_rel32(0x84, lbl + "_fin")            # jz 整除，无需修正
        em.mov_rr(10, 2)                            # mov r10,rdx（余数）
        em.emit(b"\x49\x31\xCA")                    # xor r10,rcx（异号 ⟹ 符号位 1）
        em.emit(b"\x4D\x85\xD2")                    # test r10,r10
        em.jcc_rel32(0x89, lbl + "_fin")            # jns 同号
        if is_mod:
            em.add_rr(2, 1)                         # add rdx,rcx（余数 += 除数）
        else:
            em.emit(b"\x48\xFF\xC8")                # dec rax（商 -1）
        em.label_here(lbl + "_fin")
        if is_mod:
            em.emit(b"\x48\x89\xD0")                # mov rax,rdx
        em.emit(b"\x48\x89\xEC\x5D\xC3")            # mov rsp,rbp; pop rbp; ret

    # ---- as_double(rax) → xmm0 ----
    em.label_here("as_double")
    em.mov_rr(1, 0)
    em.lea_rip(2, "heap_base")
    em.sub_rr(1, 2)
    em.cmp_ri(1, HEAP_SIZE)
    em.jcc_rel32(0x83, "asd_int")
    em.movsd_load(0, 0, 16)                         # movsd xmm0,[rax+16]
    em.emit(b"\xC3")
    em.label_here("asd_int")
    em.cvtsi2sd(0, 0)                               # cvtsi2sd xmm0,rax
    em.emit(b"\xC3")

    # ---- box_float(xmm0) → rax ----
    em.label_here("box_float")
    em.emit(b"\x55\x48\x89\xE5")
    em.emit(b"\x48\x83\xEC\x40")
    em.movsd_store(4, 0x20, 0)                      # [rsp+0x20]=xmm0
    em.mov_r_imm32(7, FLOAT_OBJ_SIZE)
    em.call_rel32("alloc")
    em.emit(b"\x48\xC7\x00" + struct.pack("<I", TYPE_FLOAT))
    em.emit(b"\x48\xC7\x40\x08\x08\x00\x00\x00")    # mov qword[rax+8],8
    em.movsd_load(0, 4, 0x20)
    em.movsd_store(0, 16, 0)                        # movsd [rax+16],xmm0
    em.emit(b"\x48\x89\xEC\x5D\xC3")

    # ---- bin_to_xmm2(rax=l,rcx=r) → xmm0=l, xmm1=r ----
    em.label_here("bin_to_xmm2")
    em.emit(b"\x55\x48\x89\xE5")
    em.emit(b"\x48\x83\xEC\x40")
    em.mov_mem_r(4, 0x20, 1)                        # [rsp+0x20]=rcx
    em.call_rel32("as_double")                      # xmm0=l
    em.movsd_store(4, 0x28, 0)
    em.mov_rd_mem(0, 4, 0x20)                       # rax=r
    em.call_rel32("as_double")                      # xmm0=r
    em.emit(b"\xF2\x0F\x10\xC8")                    # movsd xmm1,xmm0
    em.movsd_load(0, 4, 0x28)                       # xmm0=l
    em.emit(b"\x48\x89\xEC\x5D\xC3")

    # ---- 基本算术 ----
    for lbl, ins in (("f_add", em.addsd), ("f_sub", em.subsd),
                     ("f_mul", em.mulsd), ("f_div", em.divsd)):
        em.label_here(lbl)
        em.emit(b"\x55\x48\x89\xE5")
        em.emit(b"\x48\x83\xEC\x20")
        em.call_rel32("bin_to_xmm2")
        ins(0, 1)
        em.call_rel32("box_float")
        em.emit(b"\x48\x89\xEC\x5D\xC3")

    # ---- f_floordiv：floor(a/b) ----
    # 除数为 0（含 -0.0）抛 "division by zero"，对齐 VM 的 ZeroDivisionError。
    # 不拦则 divsd 得 ±inf、f_mod 得 NaN，静默输出错误结果。
    # 判零须与**全零寄存器**比（ucomisd xmm1,xmm1 恒等，只反映自比较）；
    # NaN 对 ucomisd 也置 ZF=1，故先 JP 排除再 JZ 判零。
    em.label_here("f_floordiv")
    em.emit(b"\x55\x48\x89\xE5")
    em.emit(b"\x48\x83\xE4\xF0")
    em.emit(b"\x48\x83\xEC\x20")
    em.call_rel32("bin_to_xmm2")
    em.emit(b"\x66\x0F\xEF\xD2")                    # xorpd xmm2,xmm2
    em.ucomisd(1, 2)                                # ucomisd xmm1,xmm2
    em.jcc_rel32(0x8A, "fdivz_go")                  # jp   NaN → 视作非零
    em.jcc_rel32(0x84, "fdivz")                     # jz   除数为 ±0.0
    em.jcc_rel32(None, "fdivz_go")
    em.label_here("fdivz_go")
    em.divsd(0, 1)
    em.call_rip_indirect("crt_floor")
    em.call_rel32("box_float")
    em.emit(b"\x48\x89\xEC\x5D\xC3")

    # ---- f_mod：a - floor(a/b)*b ----
    em.label_here("f_mod")
    em.emit(b"\x55\x48\x89\xE5")
    em.emit(b"\x48\x83\xE4\xF0")
    em.emit(b"\x48\x83\xEC\x30")
    em.call_rel32("bin_to_xmm2")
    em.emit(b"\x66\x0F\xEF\xD2")                    # xorpd xmm2,xmm2
    em.ucomisd(1, 2)                                # ucomisd xmm1,xmm2
    em.jcc_rel32(0x8A, "fdivz_go")                  # jp   NaN → 视作非零
    em.jcc_rel32(0x84, "fdivz")                     # jz   除数为 ±0.0
    em.movsd_store(4, 0x20, 0)                      # l
    em.movsd_store(4, 0x28, 1)                      # r
    em.divsd(0, 1)                                  # l/r
    em.call_rip_indirect("crt_floor")
    em.movsd_load(1, 4, 0x28)                       # r
    em.mulsd(0, 1)
    em.movsd_load(1, 4, 0x20)                       # l
    em.subsd(1, 0)
    em.emit(b"\xF2\x0F\x10\xC1")                    # movsd xmm0,xmm1
    em.call_rel32("box_float")
    em.emit(b"\x48\x89\xEC\x5D\xC3")

    # ---- fdivz：浮点除零的抛出点（f_floordiv / f_mod 共用）----
    em.label_here("fdivz")
    em.lea_rip(0, "err_divzero")
    em.call_rel32("raise_rt")                       # 不返回
    em.emit(b"\x0F\x0B")                            # ud2

    # ---- f_pow：pow(a,b) ----
    em.label_here("f_pow")
    em.emit(b"\x55\x48\x89\xE5")
    em.emit(b"\x48\x83\xE4\xF0")
    em.emit(b"\x48\x83\xEC\x20")
    em.call_rel32("bin_to_xmm2")
    em.call_rip_indirect("crt_pow")
    em.call_rel32("box_float")
    em.emit(b"\x48\x89\xEC\x5D\xC3")

    # ---- f_sqrt(rax) → rax（对齐 vm._builtin_sqrt：整数完全平方回退整数）----
    # 用 CRT pow(x,0.5) 而非 SSE sqrtsd，确保与 VM 的 `a ** 0.5` 逐位一致。
    em.label_here("f_sqrt")
    em.emit(b"\x55\x48\x89\xE5")                    # push rbp; mov rbp,rsp
    em.emit(b"\x48\x83\xE4\xF0")                    # and rsp,-16
    em.emit(b"\x48\x83\xEC\x40")                    # sub rsp,0x40
    em.mov_mem_r(4, 0x20, 0)                        # [rsp+0x20]=原值
    em.call_rel32("is_float")
    em.mov_mem_r(4, 0x28, 0)                        # [rsp+0x28]=是否浮点(0/1)
    em.mov_rd_mem(0, 4, 0x20)                       # rax=原值
    em.call_rel32("as_double")                      # xmm0=x
    em.mov_r_imm64(2, 0x3FE0000000000000)           # 0.5 的位模式
    em.movq_xmm_r(1, 2)                             # xmm1=0.5
    em.call_rip_indirect("crt_pow")                 # xmm0=x**0.5
    em.mov_rd_mem(2, 4, 0x28)                       # 原值是浮点？
    em.test_rr(2, 2)
    em.jcc_rel32(0x85, "f_sqrt_box")                # 浮点 → 结果恒浮点
    em.cvttsd2si(0, 0)                              # rax=截断取整
    em.cvtsi2sd(1, 0)                               # xmm1=(double)rax
    em.ucomisd(0, 1)                                # r == int(r) ?
    em.jcc_rel32(0x8A, "f_sqrt_box")                # jp：NaN → 装箱
    em.jcc_rel32(0x85, "f_sqrt_box")                # jne：非完全平方 → 装箱
    em.emit(b"\x48\x89\xEC\x5D\xC3")                # 返回整数（rax）
    em.label_here("f_sqrt_box")
    em.call_rel32("box_float")
    em.emit(b"\x48\x89\xEC\x5D\xC3")

    # ---- f_neg(rax) → rax ----
    em.label_here("f_neg")
    em.emit(b"\x55\x48\x89\xE5")
    em.emit(b"\x48\x83\xEC\x20")
    em.call_rel32("as_double")
    em.movq_r_xmm(0, 0)
    em.mov_r_imm64(2, 0x8000000000000000)
    em.emit(b"\x48\x31\xD0")                        # xor rax,rdx
    em.movq_xmm_r(0, 0)
    em.call_rel32("box_float")
    em.emit(b"\x48\x89\xEC\x5D\xC3")

    # ---- float_cmp2(rax,rcx)：ucomisd(l,r) 设置标志后返回 ----
    em.label_here("float_cmp2")
    em.emit(b"\x55\x48\x89\xE5")
    em.emit(b"\x48\x83\xEC\x20")
    em.call_rel32("bin_to_xmm2")
    em.ucomisd(0, 1)
    em.emit(b"\x48\x89\xEC\x5D\xC3")

    # ---- buf_to_str(rdi=buf, rcx=len) → rax=str ----
    em.label_here("buf_to_str")
    em.emit(b"\x55\x48\x89\xE5")
    em.emit(b"\x48\x83\xEC\x40")
    em.mov_mem_r(4, 0x20, 7)                        # [rsp+0x20]=buf
    em.mov_mem_r(4, 0x28, 1)                        # [rsp+0x28]=len
    em.mov_rr(7, 1)
    em.emit(b"\x48\x83\xC7\x10")                    # add rdi,16
    em.call_rel32("alloc")
    em.emit(b"\x48\xC7\x00" + struct.pack("<I", TYPE_STR))
    em.mov_rd_mem(1, 4, 0x28)
    em.mov_mem_r(0, 8, 1)                           # mov [rax+8],rcx
    em.lea_mem(7, 0, 16)                            # lea rdi,[rax+16]
    em.mov_rd_mem(6, 4, 0x20)                       # rsi=buf
    em.emit(b"\xF3\xA4")                            # rep movsb
    em.emit(b"\x48\x89\xEC\x5D\xC3")

    # ---- str_float(rax=float obj) → rax=str（Python repr 对齐）----
    em.label_here("str_float")
    em.emit(b"\x55\x48\x89\xE5")
    em.emit(b"\x48\x83\xE4\xF0")                    # and rsp,-16
    em.emit(b"\x48\x81\xEC\x00\x01\x00\x00")        # sub rsp,0x100
    em.movsd_load(0, 0, 16)
    em.movq_r_xmm(0, 0)                             # rax=bits
    em.mov_rr(1, 0)
    em.shr_ri(1, 52)
    em.and_ri(1, 0x7FF)
    em.cmp_ri(1, 0x7FF)
    em.jcc_rel32(0x84, "sf_special")
    em.mov_rr(2, 0)
    em.shr_ri(2, 63)
    em.mov_mem_r(4, 0x28, 2)                        # sign
    em.mov_r_imm64(1, 0x7FFFFFFFFFFFFFFF)
    em.emit(b"\x48\x21\xC8")                        # and rax,rcx
    em.mov_mem_r(4, 0x30, 0)                        # abs bits
    em.test_rr(0, 0)
    em.jcc_rel32(0x84, "sf_zero")
    em.movq_xmm_r(0, 0)                             # xmm0=abs double
    em.mov_r_imm32(2, 24)                           # edx=24
    em.lea_mem(8, 4, 0x38)                          # r8=&decpt
    em.lea_mem(9, 4, 0x40)                          # r9=&sign2
    em.call_rip_indirect("crt__ecvt")
    # _ecvt 只写 4 字节 int decpt；把高 32 位归一为符号扩展，避免读到栈垃圾。
    # 用 rdx 暂存，不能用 rax（它保存着 digits 指针）。
    em.movsxd_rd_mem(2, 4, 0x38)                    # movsxd rdx,[rsp+0x38]
    em.mov_mem_r(4, 0x38, 2)                        # [rsp+0x38]=rdx
    em.mov_mem_r(4, 0x80, 2)                        # [rsp+0x80]=原始 decpt（每次迭代恢复）
    em.mov_rr(6, 0)                                 # rsi=digits
    em.lea_mem(7, 4, 0x48)                          # rdi=[rsp+0x48]
    em.mov_r_imm32(1, 24)
    em.emit(b"\xF3\xA4")                            # rep movsb
    em.mov_r_imm32(10, 1)
    em.mov_mem_r(4, 0xB0, 10)                       # p=1
    em.label_here("sf_sweep")
    em.mov_rd_mem(0, 4, 0x80)                       # 恢复原始 decpt
    em.mov_mem_r(4, 0x38, 0)
    em.mov_rd_mem(1, 4, 0xB0)                       # rcx=p
    em.cmp_ri(1, 17)
    em.jcc_rel32(0x8F, "sf_after")
    em.mov_rr(2, 1)
    em.lea_mem(6, 4, 0x48)
    em.lea_mem(7, 4, 0x60)
    em.label_here("sf_copy")
    em.emit(b"\x8A\x06")
    em.emit(b"\x88\x07")
    em.emit(b"\x48\xFF\xC6")
    em.emit(b"\x48\xFF\xC7")
    em.emit(b"\x48\xFF\xCA")
    em.jcc_rel32(0x85, "sf_copy")
    em.lea_mem(6, 4, 0x48)
    em.mov_rr(2, 1)
    em.emit(b"\x0F\xB6\x04\x16")                    # movzx eax,[rsi+rdx]
    em.cmp_ri(0, 0x35)                              # '5'
    em.jcc_rel32(0x82, "sf_noup")
    em.jcc_rel32(0x87, "sf_up")
    em.mov_rr(8, 1)
    em.inc_r(8)
    em.label_here("sf_rest")
    em.cmp_ri(8, 24)
    em.jcc_rel32(0x8D, "sf_tie")
    em.emit(b"\x42\x0F\xB6\x04\x06")                # movzx eax,[rsi+r8]
    em.cmp_ri(0, 0x30)                              # '0'
    em.jcc_rel32(0x85, "sf_up")
    em.inc_r(8)
    em.jcc_rel32(None, "sf_rest")
    em.label_here("sf_tie")
    em.mov_rr(8, 1)
    em.emit(b"\x49\xFF\xC8")                        # dec r8
    em.lea_mem(7, 4, 0x60)
    em.emit(b"\x42\x0F\xB6\x04\x07")                # movzx eax,[rdi+r8]
    em.emit(b"\x2C\x30")                            # sub al,'0'
    em.emit(b"\xA8\x01")                            # test al,1
    em.jcc_rel32(0x85, "sf_up")
    em.jcc_rel32(None, "sf_noup")
    em.label_here("sf_up")
    em.mov_rr(8, 1)
    em.emit(b"\x49\xFF\xC8")                        # dec r8
    em.lea_mem(7, 4, 0x60)
    em.label_here("sf_inc")
    em.emit(b"\x49\x83\xF8\x00")                    # cmp r8,0
    em.jcc_rel32(0x8C, "sf_carry")
    em.emit(b"\x42\x0F\xB6\x04\x07")                # movzx eax,[rdi+r8]
    em.emit(b"\x3C\x39")                            # cmp al,'9'
    em.jcc_rel32(0x85, "sf_incd")
    em.emit(b"\x42\xC6\x04\x07\x30")                # mov byte[rdi+r8],'0'
    em.emit(b"\x49\xFF\xC8")                        # dec r8
    em.jcc_rel32(None, "sf_inc")
    em.label_here("sf_incd")
    em.emit(b"\x04\x01")                            # add al,1
    em.emit(b"\x42\x88\x04\x07")                    # mov [rdi+r8],al
    em.jcc_rel32(None, "sf_noup")
    em.label_here("sf_carry")
    em.emit(b"\xC6\x07\x31")                        # mov byte[rdi],'1'
    em.mov_r_imm32(8, 1)
    em.label_here("sf_zl")
    em.cmp_rr(8, 1)
    em.jcc_rel32(0x8D, "sf_zld")
    em.emit(b"\x42\xC6\x04\x07\x30")                # mov byte[rdi+r8],'0'
    em.inc_r(8)
    em.jcc_rel32(None, "sf_zl")
    em.label_here("sf_zld")
    em.emit(b"\x48\x83\x44\x24\x38\x01")            # add qword[rsp+0x38],1
    em.label_here("sf_noup")
    # 构造科学计数候选串
    em.lea_mem(7, 4, 0xC0)
    em.mov_mem_r(4, 0xB8, 7)                        # 保存 start
    em.lea_mem(6, 4, 0x60)
    em.emit(b"\x8A\x06")
    em.emit(b"\x88\x07")
    em.emit(b"\x48\xFF\xC7")                        # inc rdi（rsi 保持指向 temp[0]）
    em.cmp_ri(1, 1)
    em.jcc_rel32(0x8E, "sf_nd")
    em.emit(b"\xC6\x07\x2E")                        # '.'
    em.emit(b"\x48\xFF\xC7")
    em.mov_r_imm32(8, 1)
    em.label_here("sf_dl")
    em.cmp_rr(8, 1)
    em.jcc_rel32(0x8D, "sf_nd")
    em.emit(b"\x42\x8A\x04\x06")                    # mov al,[rsi+r8]
    em.emit(b"\x88\x07")
    em.emit(b"\x48\xFF\xC7")
    em.inc_r(8)
    em.jcc_rel32(None, "sf_dl")
    em.label_here("sf_nd")
    em.emit(b"\xC6\x07\x65")                        # 'e'
    em.emit(b"\x48\xFF\xC7")
    em.mov_rd_mem(0, 4, 0x38)
    em.emit(b"\x48\x83\xE8\x01")                    # sub rax,1
    em.test_rr(0, 0)
    em.jcc_rel32(0x89, "sf_ep")
    em.emit(b"\xC6\x07\x2D")                        # '-'
    em.emit(b"\x48\xFF\xC7")
    em.emit(b"\x48\xF7\xD8")                        # neg rax
    em.label_here("sf_ep")
    em.lea_mem(6, 4, 0xE8)                          # 指数临时区
    em.emit(b"\x4C\x8D\x4E\x0C")                    # lea r9,[rsi+12]
    em.mov_rr(10, 9)
    em.mov_r_imm32(11, 10)
    em.label_here("sf_ed")
    em.emit(b"\x31\xD2")                            # xor edx,edx
    em.emit(b"\x49\xF7\xF3")                        # div r11
    em.emit(b"\x80\xC2\x30")                        # add dl,'0'
    em.emit(b"\x49\xFF\xC9")                        # dec r9
    em.emit(b"\x41\x88\x11")                        # mov [r9],dl
    em.test_rr(0, 0)
    em.jcc_rel32(0x85, "sf_ed")
    em.mov_rr(1, 10)
    em.sub_rr(1, 9)
    em.cmp_ri(1, 2)
    em.jcc_rel32(0x8D, "sf_ec")
    em.emit(b"\x49\xFF\xC9")
    em.emit(b"\x41\xC6\x01\x30")                    # mov byte[r9],'0'
    em.label_here("sf_ec")
    em.cmp_rr(9, 10)
    em.jcc_rel32(0x83, "sf_ecd")
    em.emit(b"\x41\x8A\x01")                        # mov al,[r9]
    em.emit(b"\x88\x07")
    em.emit(b"\x48\xFF\xC7")
    em.emit(b"\x49\xFF\xC1")                        # inc r9
    em.jcc_rel32(None, "sf_ec")
    em.label_here("sf_ecd")
    em.emit(b"\xC6\x07\x00")                        # NUL 结尾（strtod 需要）
    # 往返比较
    em.lea_mem(1, 4, 0xC0)
    em.emit(b"\x31\xD2")                            # xor edx,edx
    em.call_rip_indirect("crt_strtod")
    em.movq_r_xmm(0, 0)
    em.mov_rd_mem(1, 4, 0x30)
    em.emit(b"\x48\x39\xC8")                        # cmp rax,rcx
    em.jcc_rel32(0x84, "sf_match")
    em.mov_rd_mem(1, 4, 0xB0)
    em.inc_r(1)
    em.mov_mem_r(4, 0xB0, 1)
    em.jcc_rel32(None, "sf_sweep")
    em.label_here("sf_match")
    em.jcc_rel32(None, "sf_format")
    em.label_here("sf_after")
    em.label_here("sf_format")
    em.mov_rd_mem(6, 4, 0xB8)                       # rsi=start
    em.mov_rr(7, 6)                                 # rdi=start
    em.mov_rd_mem(0, 4, 0x28)                       # sign
    em.test_rr(0, 0)
    em.jcc_rel32(0x84, "sf_nosign")
    em.emit(b"\xC6\x07\x2D")
    em.emit(b"\x48\xFF\xC7")
    em.label_here("sf_nosign")
    em.mov_rd_mem(8, 4, 0xB0)                       # n=p
    em.mov_rd_mem(9, 4, 0x38)                       # decpt
    em.cmp_ri(9, -4)
    em.jcc_rel32(0x8E, "sf_fe")
    em.cmp_ri(9, 16)
    em.jcc_rel32(0x8F, "sf_fe")
    em.test_rr(9, 9)
    em.jcc_rel32(0x8E, "sf_fl")
    em.cmp_rr(9, 8)
    em.jcc_rel32(0x8D, "sf_fi")
    # decpt 在中间：digits[0:decpt] + '.' + digits[decpt:]
    em.lea_mem(10, 4, 0x60)
    em.emit(b"\x31\xC9")                            # xor ecx,ecx
    em.label_here("sf_fm1")
    em.cmp_rr(1, 9)
    em.jcc_rel32(0x8D, "sf_fmd")
    em.emit(b"\x41\x8A\x04\x0A")                    # mov al,[r10+rcx]
    em.emit(b"\x88\x07")
    em.emit(b"\x48\xFF\xC7")
    em.emit(b"\x48\xFF\xC1")
    em.jcc_rel32(None, "sf_fm1")
    em.label_here("sf_fmd")
    em.emit(b"\xC6\x07\x2E")
    em.emit(b"\x48\xFF\xC7")
    em.label_here("sf_fm2")
    em.cmp_rr(1, 8)
    em.jcc_rel32(0x8D, "sf_fdone")
    em.emit(b"\x41\x8A\x04\x0A")
    em.emit(b"\x88\x07")
    em.emit(b"\x48\xFF\xC7")
    em.emit(b"\x48\xFF\xC1")
    em.jcc_rel32(None, "sf_fm2")
    # decpt >= n：digits + zeros + ".0"
    em.label_here("sf_fi")
    em.lea_mem(10, 4, 0x60)
    em.emit(b"\x31\xC9")
    em.label_here("sf_fi1")
    em.cmp_rr(1, 8)
    em.jcc_rel32(0x8D, "sf_fiz")
    em.emit(b"\x41\x8A\x04\x0A")
    em.emit(b"\x88\x07")
    em.emit(b"\x48\xFF\xC7")
    em.emit(b"\x48\xFF\xC1")
    em.jcc_rel32(None, "sf_fi1")
    em.label_here("sf_fiz")
    em.mov_rr(11, 9)
    em.sub_rr(11, 8)                                # zeros=decpt-n
    em.label_here("sf_fi2")
    em.test_rr(11, 11)
    em.jcc_rel32(0x8E, "sf_fid")
    em.emit(b"\xC6\x07\x30")
    em.emit(b"\x48\xFF\xC7")
    em.emit(b"\x49\xFF\xCB")
    em.jcc_rel32(None, "sf_fi2")
    em.label_here("sf_fid")
    em.emit(b"\xC6\x07\x2E")
    em.emit(b"\x48\xFF\xC7")
    em.emit(b"\xC6\x07\x30")
    em.emit(b"\x48\xFF\xC7")
    em.jcc_rel32(None, "sf_fdone")
    # decpt <= 0："0." + zeros + digits
    em.label_here("sf_fl")
    em.emit(b"\xC6\x07\x30")
    em.emit(b"\x48\xFF\xC7")
    em.emit(b"\xC6\x07\x2E")
    em.emit(b"\x48\xFF\xC7")
    em.mov_rr(11, 9)
    em.emit(b"\x49\xF7\xDB")                        # neg r11
    em.label_here("sf_fl1")
    em.test_rr(11, 11)
    em.jcc_rel32(0x8E, "sf_fld")
    em.emit(b"\xC6\x07\x30")
    em.emit(b"\x48\xFF\xC7")
    em.emit(b"\x49\xFF\xCB")
    em.jcc_rel32(None, "sf_fl1")
    em.label_here("sf_fld")
    em.lea_mem(10, 4, 0x60)
    em.emit(b"\x31\xC9")
    em.label_here("sf_fl2")
    em.cmp_rr(1, 8)
    em.jcc_rel32(0x8D, "sf_fdone")
    em.emit(b"\x41\x8A\x04\x0A")
    em.emit(b"\x88\x07")
    em.emit(b"\x48\xFF\xC7")
    em.emit(b"\x48\xFF\xC1")
    em.jcc_rel32(None, "sf_fl2")
    # 科学计数：d0[.d1..]e±exp
    em.label_here("sf_fe")
    em.lea_mem(10, 4, 0x60)
    em.emit(b"\x41\x8A\x02")                        # mov al,[r10]
    em.emit(b"\x88\x07")
    em.emit(b"\x48\xFF\xC7")
    em.cmp_ri(8, 1)
    em.jcc_rel32(0x8E, "sf_fend")
    em.emit(b"\xC6\x07\x2E")
    em.emit(b"\x48\xFF\xC7")
    em.mov_r_imm32(1, 1)
    em.label_here("sf_fed")
    em.cmp_rr(1, 8)
    em.jcc_rel32(0x8D, "sf_fend")
    em.emit(b"\x41\x8A\x04\x0A")
    em.emit(b"\x88\x07")
    em.emit(b"\x48\xFF\xC7")
    em.emit(b"\x48\xFF\xC1")
    em.jcc_rel32(None, "sf_fed")
    em.label_here("sf_fend")
    em.emit(b"\xC6\x07\x65")                        # 'e'
    em.emit(b"\x48\xFF\xC7")
    em.mov_rr(0, 9)
    em.emit(b"\x48\x83\xE8\x01")                    # exp=decpt-1
    em.test_rr(0, 0)
    em.jcc_rel32(0x88, "sf_fneg")                   # js：负指数
    em.emit(b"\xC6\x07\x2B")                        # '+'（CPython 始终带符号）
    em.emit(b"\x48\xFF\xC7")
    em.jcc_rel32(None, "sf_fep")
    em.label_here("sf_fneg")
    em.emit(b"\xC6\x07\x2D")                        # '-'
    em.emit(b"\x48\xFF\xC7")
    em.emit(b"\x48\xF7\xD8")                        # neg rax
    em.label_here("sf_fep")
    em.lea_mem(6, 4, 0xE8)
    em.emit(b"\x4C\x8D\x4E\x0C")
    em.mov_rr(10, 9)
    em.mov_r_imm32(11, 10)
    em.label_here("sf_fediv")
    em.emit(b"\x31\xD2")
    em.emit(b"\x49\xF7\xF3")
    em.emit(b"\x80\xC2\x30")
    em.emit(b"\x49\xFF\xC9")
    em.emit(b"\x41\x88\x11")
    em.test_rr(0, 0)
    em.jcc_rel32(0x85, "sf_fediv")
    em.mov_rr(1, 10)
    em.sub_rr(1, 9)
    em.cmp_ri(1, 2)
    em.jcc_rel32(0x8D, "sf_fecopy")
    em.emit(b"\x49\xFF\xC9")
    em.emit(b"\x41\xC6\x01\x30")
    em.label_here("sf_fecopy")
    em.cmp_rr(9, 10)
    em.jcc_rel32(0x83, "sf_fdone")
    em.emit(b"\x41\x8A\x01")
    em.emit(b"\x88\x07")
    em.emit(b"\x48\xFF\xC7")
    em.emit(b"\x49\xFF\xC1")
    em.jcc_rel32(None, "sf_fecopy")
    em.label_here("sf_fdone")
    em.mov_rd_mem(6, 4, 0xB8)                       # rsi=start（sf_fe 分支会改写 rsi）
    em.mov_rr(1, 7)
    em.sub_rr(1, 6)
    em.mov_rr(7, 6)
    em.call_rel32("buf_to_str")
    em.emit(b"\x48\x89\xEC\x5D\xC3")
    # 特殊值
    em.label_here("sf_special")
    em.mov_rr(1, 0)
    em.mov_r_imm64(2, 0x000FFFFFFFFFFFFF)
    em.emit(b"\x48\x21\xD1")                        # and rcx,rdx
    em.test_rr(1, 1)
    em.jcc_rel32(0x85, "sf_nan")
    em.test_rr(0, 0)
    em.jcc_rel32(0x89, "sf_inf")
    em.lea_rip(0, "fstr_ninf")
    em.jcc_rel32(None, "sf_ret")
    em.label_here("sf_inf")
    em.lea_rip(0, "fstr_inf")
    em.jcc_rel32(None, "sf_ret")
    em.label_here("sf_nan")
    em.lea_rip(0, "fstr_nan")
    em.jcc_rel32(None, "sf_ret")
    em.label_here("sf_zero")
    em.emit(b"\x48\x83\x7C\x24\x28\x00")            # cmp qword[rsp+0x28],0
    em.jcc_rel32(0x84, "sf_z0")
    em.lea_rip(0, "fstr_n0")
    em.jcc_rel32(None, "sf_ret")
    em.label_here("sf_z0")
    em.lea_rip(0, "fstr_0")
    em.label_here("sf_ret")
    em.emit(b"\x48\x89\xEC\x5D\xC3")


def _emit_data_section(mod, labels: dict, ec: "_Emitter", user_names: set):
    """按实际 .text 大小确定 .data 起始 RVA 后发射数据节。

    .data 的 RVA 必须落在 .text 之后并按 SectionAlignment(0x1000) 对齐。
    原先 DATA_RVA 是固定常量 0x2000，当代码增长到 4KB 以上时 .text 会与
    .data 重叠，Windows 拒绝加载该映像（WinError 193）。

    注意：此处不调用 patch()，因为代码节的 RIP 相对重定位会引用尚未
    发射的数据标签（如 vstack）；两节均发射完毕后由调用方统一 patch。
    """
    text_size = len(ec.buf)     # 代码趟已发射完毕，其大小已确定
    data_rva = TEXT_RVA + ((text_size + 0xFFF) & ~0xFFF)
    ed = _Emitter(data_rva, labels)             # 数据节
    builtin_names = [b for b in NATIVE_BUILTINS if b not in user_names]
    fn_names = user_names | set(builtin_names)

    # ---- 数据：运行时解析出的 API 地址槽（PEB 引导填充）----
    ed.align(8)
    for fn in _APIS:
        ed.label_here(f"api_{fn}")
        ed.emit(b"\x00" * 8)

    # ---- 数据：CRT 模块与函数槽（load_crt 填充）----
    for s_lbl, s in (("crt_dll_ucrt", "ucrtbase.dll\x00"),
                     ("crt_dll_msvcrt", "msvcrt.dll\x00")):
        ed.label_here(s_lbl)
        ed.emit(s.encode("ascii"))
    ed.align(8)
    ed.label_here("crt_module")
    ed.emit(b"\x00" * 8)
    for fn in _CRT_FUNCS:
        ed.label_here(f"crt_{fn}")
        ed.emit(b"\x00" * 8)
    for fn in _CRT_FUNCS:
        ed.label_here(f"crtname_{fn}")
        ed.emit(fn.encode("ascii") + b"\x00")

    # ---- 数据：全局变量单元 ----
    # 注意：被同名变量遮蔽的内建名（如 `let get = 5`）也必须有 cell，
    # 否则 LOAD_GLOBAL 走 cell 路径时找不到标签（patch 阶段 KeyError）。
    cell_names = set()
    declared = _declared_globals(mod)
    all_code = [("main", mod.main_code)] + \
        [(f"fn:{n}", f.code) for n, f in mod.functions.items()]
    for _tag, code in all_code:
        for ins in code:
            if ins[0] in (OP.LOAD_GLOBAL, OP.STORE_GLOBAL):
                nm = mod.constants[ins[1]]
                if nm not in fn_names or nm in declared:
                    cell_names.add(nm)
    ed.align(8)
    ed.label_here("cells_begin")                    # GC 根：全局变量单元区间起点
    for nm in sorted(cell_names):
        ed.label_here(f"cell:{nm}")
        ed.emit(b"\x00" * 8)
    ed.label_here("cells_end")

    # ---- 数据：柯里化内建的闭包记录指针（启动期填充）----
    ed.align(8)
    for nm in NATIVE_BUILTINS:
        if nm in _CURRIED_BUILTINS and nm not in user_names:
            ed.label_here(f"bclo:{nm}")
            ed.emit(b"\x00" * 8)

    # ---- 数据：操作数栈 / 输出缓冲 / 写字数 ----
    ed.align(16)
    ed.label_here("vstack")
    ed.emit(b"\x00" * VSTACK_SIZE)
    ed.label_here("numbuf")
    ed.emit(b"\x00" * NUMBUF_SIZE)
    ed.label_here("written")
    ed.emit(b"\x00" * 8)
    ed.label_here("rand_state")
    ed.emit(b"\x00" * 8)
    ed.label_here("crlf")
    ed.emit(b"\x0D\x0A")
    ed.label_here("heap_ptr")
    ed.emit(b"\x00" * 8)
    ed.label_here("hstack_ptr")
    ed.emit(b"\x00" * 8)
    ed.label_here("handler_top")
    ed.emit(b"\x00" * 8)
    ed.label_here("raise_msg")
    ed.emit(b"\x00" * 8)
    # 砖块 18：GC 标量槽（零初始即正确：free_head/mark_top 空）。
    ed.label_here("stack_top")
    ed.emit(b"\x00" * 8)
    ed.label_here("heap_limit")
    ed.emit(b"\x00" * 8)
    ed.label_here("sweep_start")
    ed.emit(b"\x00" * 8)
    ed.label_here("free_head")
    ed.emit(b"\x00" * 8)
    ed.label_here("mark_top")
    ed.emit(b"\x00" * 8)
    # 砖块 19：输出汇（str(容器) 两遍渲染：先计数、再填充到目标 STR）。
    ed.label_here("out_mode")
    ed.emit(b"\x00" * 8)
    ed.label_here("out_count")
    ed.emit(b"\x00" * 8)
    ed.label_here("out_buf_ptr")
    ed.emit(b"\x00" * 8)

    # ---- 数据：堆区 = [静态对象区][自由空间] ----
    ed.align(8)
    ed.label_here("heap_base")
    for i, c in enumerate(mod.constants):
        if isinstance(c, str):
            raw = c.encode("utf-8")
            ed.align(8)
            ed.label_here(f"sob:{i}")
            ed.emit(struct.pack("<Q", TYPE_STR))
            ed.emit(struct.pack("<Q", len(raw)))
            ed.emit(raw)
            ed.align(8)
        elif isinstance(c, float):
            ed.align(8)
            ed.label_here(f"fob:{i}")
            ed.emit(struct.pack("<Q", TYPE_FLOAT))
            ed.emit(struct.pack("<Q", 8))
            ed.emit(struct.pack("<d", c))
            ed.align(8)
    # 砖块 15：数学/物理常量静态浮点对象（LOAD_GLOBAL 经 const:{名} 引用）。
    # 整数常量（如光速 c）走裸整数路径，无需静态对象。
    for cname in sorted(_MATH_CONSTANTS):
        cval = _MATH_CONSTANTS[cname]
        if not isinstance(cval, float):
            continue
        ed.align(8)
        ed.label_here(f"const:{cname}")
        ed.emit(struct.pack("<Q", TYPE_FLOAT))
        ed.emit(struct.pack("<Q", 8))
        ed.emit(struct.pack("<d", cval))
        ed.align(8)
    for lbl, s in (("rb_lb", "["), ("rb_rb", "]"), ("rb_sep", ", "),
                   ("dk_lb", "{"), ("dk_rb", "}"), ("dk_q", "'"),
                   ("dk_col", ": "),
("tag_normal", "__正常__"), ("tag_error", "__异常__"),
                    ("err_divzero", "division by zero"),
                    ("err_powzero", "zero to a negative power")):
        raw = s.encode("utf-8")
        ed.align(8)
        ed.label_here(lbl)
        ed.emit(struct.pack("<Q", TYPE_STR))
        ed.emit(struct.pack("<Q", len(raw)))
        ed.emit(raw)
        ed.align(8)
    for lbl, ty, s in (("bool_true", TYPE_BOOL, "True"),
                       ("bool_false", TYPE_BOOL, "False"),
                       ("null_obj", TYPE_NULL, "None"),
                       ("fstr_0", TYPE_STR, "0.0"),
                       ("fstr_n0", TYPE_STR, "-0.0"),
                       ("fstr_inf", TYPE_STR, "inf"),
                       ("fstr_ninf", TYPE_STR, "-inf"),
                       ("fstr_nan", TYPE_STR, "nan")):
        raw = s.encode("utf-8")
        ed.align(8)
        ed.label_here(lbl)
        ed.emit(struct.pack("<Q", ty))
        ed.emit(struct.pack("<Q", len(raw)))
        ed.emit(raw)
        ed.align(8)
    # 砖块 16 阶段一：type_of/typeof 名称串 + str(Bool/None) 常量串。
    for _lbl, _s in _TYPE_NAME_STRINGS.items():
        raw = _s.encode("utf-8")
        ed.align(8)
        ed.label_here(_lbl)
        ed.emit(struct.pack("<Q", TYPE_STR))
        ed.emit(struct.pack("<Q", len(raw)))
        ed.emit(raw)
        ed.align(8)
    # 砖块 16 阶段三：文件打开模式串（NUL 结尾）。
    for _lbl, _s in (("mode_rb", b"rb"), ("mode_wb", b"wb"),
                     ("mode_ab", b"ab")):
        ed.align(8)
        ed.label_here(_lbl)
        ed.emit(_s + b"\x00")
    # 砖块 18：内存不足诊断串（静态 STR 对象，供 alloc_slow 的 OOM 路径打印）。
    _oom_text = "内存不足：原生堆（8MB）已耗尽".encode("utf-8")
    ed.align(8)
    ed.label_here("oom_msg")
    ed.emit(struct.pack("<Q", TYPE_STR))
    ed.emit(struct.pack("<Q", len(_oom_text)))
    ed.emit(_oom_text)
    ed.align(8)
    # 砖块 16 阶段二：静态空字典对象（_empty_dict）。
    ed.align(8)
    ed.label_here("empty_dict")
    ed.emit(struct.pack("<Q", TYPE_DICT))
    ed.emit(struct.pack("<Q", 0))
    ed.label_here("heap_free")
    ed.emit(b"\x00" * HEAP_SIZE)
    # ---- 数据：异常处理器栈（记录从低地址向高地址推进）----
    ed.align(8)
    ed.label_here("hstack")
    ed.emit(b"\x00" * HSTACK_SIZE)

    # ---- 数据：GC 位图与标记栈（1 bit/8 字节；位于堆区间之外）----
    ed.align(64)
    ed.label_here("start_bits")
    ed.emit(b"\x00" * GC_BITMAP_BYTES)
    ed.label_here("mark_bits")
    ed.emit(b"\x00" * GC_BITMAP_BYTES)
    ed.align(64)
    ed.label_here("mark_stack")
    ed.emit(b"\x00" * (GC_MARK_STACK_ENTRIES * 8))
    return ec, ed, labels


def label_rvas(mod) -> dict[str, int]:
    """返回各静态标签 RVA（调试/测试锚点用）。"""
    _ec, _ed, labels = _build_emitters(mod)
    return dict(labels)


def _build_payload(mod) -> tuple[bytes, bytes]:
    """发射代码节与数据节，返回 (text_bytes, data_bytes)。"""
    ec, ed, _labels = _build_emitters(mod)
    ec.patch()
    ed.patch()
    return bytes(ec.buf), bytes(ed.buf)


# ---------------------------------------------------------------- PE64 链接

def _build_pe(text: bytes, data: bytes) -> bytes:
    def align(v: int, n: int) -> int:
        return (v + n - 1) & ~(n - 1)

    # 节表（RVA 顺序）：name, rva, 内容, chars
    # .data 的 RVA 由发射器按 .text 实际大小确定并对齐到 0x1000，
    # 不可用固定常量：代码超过 4KB 时固定值会与 .text 重叠。
    data_rva = TEXT_RVA + align(len(text), 0x1000)
    secs = [
        (b".text\x00\x00\x00", TEXT_RVA, text, 0x60000020),   # CODE|EXEC|READ
        (b".data\x00\x00\x00", data_rva, data, 0xC0000040),   # INIT_DATA|READ|WRITE
    ]

    data_va_end = data_rva + align(len(data), 0x1000)
    size_of_image = data_va_end

    # .data 尾部是恒为零的运行时状态（8MB 堆 free 区、64KB 异常栈、两片 128KB
    # GC 位图、8MB 标记栈），合计约 16.6MB。此前这些零字节被当作已初始化数据
    # 写进文件，使每个 exe 膨胀到 17MB（`.text` 仅 29KB），启动要为整段做文件
    # 映射。改为「VirtualSize 覆盖全长、SizeOfRawData 只覆盖到首个尾零之前」：
    # 加载器按规范把 raw 尾部零填充，RVA 布局逐字节不变，代码无需改动。
    data_raw_len = len(data)
    while data_raw_len and data[data_raw_len - 1] == 0:
        data_raw_len -= 1

    hdr = bytearray(HEADERS_SIZE)
    hdr[0:2] = b"MZ"
    struct.pack_into("<I", hdr, 0x3C, 0x80)         # e_lfanew
    hdr[0x80:0x84] = b"PE\x00\x00"
    # COFF 头 @0x84
    hdr[0x84:0x98] = struct.pack(
        "<HHIIIHH",
        0x8664,                                     # Machine: AMD64
        len(secs),                                  # NumberOfSections
        0, 0, 0,
        0xF0,                                       # SizeOfOptionalHeader
        0x0226)                                     # EXEC|LARGE_ADDR|LINE_NUMS|DEBUG_STRIPPED
    # 可选头 PE32+ @0x98（无导入表/无异常目录：API 由 PEB 引导自解析）
    opt = bytearray(0xF0)
    struct.pack_into("<H", opt, 0, 0x020B)          # Magic
    opt[2] = 14                                     # Linker 版本
    struct.pack_into("<I", opt, 4, align(len(text), 0x200))   # SizeOfCode
    struct.pack_into("<I", opt, 8, align(data_raw_len, 0x200))   # SizeOfInitializedData
    struct.pack_into("<I", opt, 16, TEXT_RVA)       # AddressOfEntryPoint
    struct.pack_into("<I", opt, 20, TEXT_RVA)       # BaseOfCode
    struct.pack_into("<Q", opt, 24, IMAGE_BASE)
    struct.pack_into("<I", opt, 32, 0x1000)         # SectionAlignment
    struct.pack_into("<I", opt, 36, 0x200)          # FileAlignment
    struct.pack_into("<H", opt, 40, 6)              # MajorOSVersion
    struct.pack_into("<H", opt, 48, 6)              # MajorSubsystemVersion
    struct.pack_into("<I", opt, 52, 0)              # Win32VersionValue
    struct.pack_into("<I", opt, 56, size_of_image)
    struct.pack_into("<I", opt, 60, HEADERS_SIZE)
    struct.pack_into("<I", opt, 64, 0)              # CheckSum
    struct.pack_into("<H", opt, 68, 3)              # Subsystem: WINDOWS_CUI
    struct.pack_into("<H", opt, 70, 0x0160)         # DYNAMIC_BASE|HIGH_ENTROPY|NX_COMPAT
    struct.pack_into("<Q", opt, 72, 0x100000)       # StackReserve
    struct.pack_into("<Q", opt, 80, 0x1000)         # StackCommit
    struct.pack_into("<Q", opt, 88, 0x100000)       # HeapReserve
    struct.pack_into("<Q", opt, 96, 0x1000)         # HeapCommit
    struct.pack_into("<I", opt, 104, 0)             # LoaderFlags
    struct.pack_into("<I", opt, 108, 16)            # NumberOfRvaAndSizes
    hdr[0x98:0x188] = opt
    # 节表 @0x188
    raw_off = HEADERS_SIZE
    parts = [bytes(hdr)]
    raw_sizes = [align(len(text), 0x200), align(data_raw_len, 0x200)]
    for i, (name, rva, content, chars) in enumerate(secs):
        content = content if i == 0 else data[:data_raw_len]
        raw_size = raw_sizes[i]
        sh = name
        sh += struct.pack("<I", len(secs[i][2]))          # VirtualSize（未初始化尾段仍计入）
        sh += struct.pack("<I", rva)                # VirtualAddress
        sh += struct.pack("<I", raw_size)           # SizeOfRawData
        sh += struct.pack("<I", raw_off if raw_size else 0)  # PointerToRawData
        sh += struct.pack("<IIHH", 0, 0, 0, 0)
        sh += struct.pack("<I", chars)
        hdr[0x188 + i * 40:0x188 + (i + 1) * 40] = sh
        parts.append(content + b"\x00" * (raw_size - len(content)))
        raw_off += raw_size
    parts[0] = bytes(hdr)                           # 回填含节表的 hdr
    return b"".join(parts)


# ---------------------------------------------------------------- 入口

def emit_exe(mod) -> bytes:
    """MModule → PE64 exe 字节串。"""
    text, data = _build_payload(mod)
    return _build_pe(text, data)


def compile_to_exe(source: str) -> bytes:
    from src.mbc.compiler import compile_source
    return emit_exe(compile_source(source))


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(prog="mbc-native",
                                     description="M3V → x86-64 PE64 原生编译器")
    parser.add_argument("source", help=".matha 源文件")
    parser.add_argument("-o", "--output", help="输出 .exe 路径")
    args = parser.parse_args(argv)

    from src.mbc.compiler import compile_source
    src = Path(args.source).read_text(encoding="utf-8")
    exe = emit_exe(compile_source(src))
    out = args.output or str(Path(args.source).with_suffix(".exe"))
    Path(out).write_bytes(exe)
    print(f"原生编译 {args.source} → {out}（{len(exe)} 字节）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
