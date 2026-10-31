/* hal/stack_vm.h — 裸机栈式引擎（极简契约优先）接口。
 *
 * 命名口径：与主线 Python 侧 src/features.py 的灰度开关 STACK_ENGINE 是两回事
 * （那是宿主解释器的帧栈绞杀中间态）；本文件是 baremetal 域的 RV32 C 栈式 VM，
 * 前缀统一 hal_vm_，符号/段布局只受 link.ld + tools/check_skeleton.py 约束。
 *
 * 极简契约（刻意窄，不追求通用优雅）：
 *   - 指令集 17 条：PUSH/POP/ADD/SUB/MUL/DIV/DUP/SWAP/JMP/JZ/JNZ/CALL/RET
 *     十三枚核心 + LOAD/STORE（mem 字段无 operand 就碰不到，刚需）
 *     + OUT/HALT（观测与停机是最小可运行版的刚需）。
 *   - 上下文四字段：pc / sp / stack / mem，与任务契约逐字一致；
 *     代码与区大小走全局常量区 + init 注入（模拟缝），不进结构体。
 *   - 指令编码：定宽 2 字（op + operand 各一字）；pc 按字计数；
 *     无操作数指令 operand 位写 0；PUSH 的 operand 按 u16 直推不符号扩展。
 *   - 分发：单 switch-case；栈溢出/栈空/除零/越界/非法 op 一律 panic，不静默。
 *   - 内存布局：stack/mem 为 .bss 静态区（见 hal/vm/stack_vm.c），落在
 *     link.ld 的 .bss 与 .heap 契约之内，crt0 启动即清零，无需搬移。
 */
#ifndef HAL_STACK_VM_H
#define HAL_STACK_VM_H

#include <hal/types.h>

/* ── 指令集（u16 op 编码值，与 code 流中的字一一对应）──────────────────── */
typedef enum {
    HAL_VM_PUSH  = 0x01,  /* 把 operand（u16 无符号）压栈        */
    HAL_VM_POP   = 0x02,  /* 弹掉栈顶（operand 位写 0）          */
    HAL_VM_ADD   = 0x03,  /* b a OP -> (a+b)              */
    HAL_VM_SUB   = 0x04,  /* b a OP -> (a-b)              */
    HAL_VM_MUL   = 0x05,  /* b a OP -> (a*b)              */
    HAL_VM_DIV   = 0x06,  /* b a OP -> (a/b)，除零 panic  */
    HAL_VM_DUP   = 0x07,  /* a -> a a                     */
    HAL_VM_SWAP  = 0x08,  /* b a -> a b                   */
    HAL_VM_JMP   = 0x09,  /* -> jmp operand（字地址）     */
    HAL_VM_JZ    = 0x0a,  /* 栈顶==0 则跳（peek 不弹）    */
    HAL_VM_JNZ   = 0x0b,  /* 栈顶!=0 则跳（peek 不弹）    */
    HAL_VM_CALL  = 0x0c,  /* 压入返回地址 -> operand      */
    HAL_VM_RET   = 0x0d,  /* pc = pop（返回地址）         */
    HAL_VM_OUT   = 0x0e,  /* 把栈顶写入输出环（不弹）     */
    HAL_VM_HALT  = 0x0f,  /* 停机，正常退出点             */
    HAL_VM_LOAD  = 0x10,  /* 推 mem[operand]（越界 panic）   */
    HAL_VM_STORE = 0x11   /* 弹栈顶写入 mem[operand]        */
} hal_vm_op_t;

/* ── 区域容量（RAM 预算内刻意取小；FE310 16K SRAM 也放得下）────────────── */
#define HAL_VM_STACK_WORDS 256u            /* 操作数栈深度（字）*/
#define HAL_VM_MEM_WORDS   512u            /* 平坦数据区（字）  */
#define HAL_VM_OUT_RING    16u             /* OUT 观测环（字）  */

/* VM 上下文：只保留 pc/sp/stack/mem 四个字段（任务契约钉死）。
   指针前置、整型尾随：RV32 上无 padding 恰 16 字；宿主 64 位对齐下尾部 pad
   不插入中间，stack/mem 仍在偏移 0/8（即 2*PTR/2*PTR+4）——契约锁只锚字段数
   与两整型相邻，不依赖宿主具体 padding。 */
typedef struct {
    int32_t  *stack;   /* 操作数栈底                        */
    int32_t  *mem;     /* 平坦数据区（PUSH/POP 间接寻址）   */
    uint32_t  pc;      /* 程序计数器：code 流中的字下标     */
    uint32_t  sp;      /* 栈指针：下一个空槽下标（空 = 0）  */
} hal_vm_ctx_t;
/* 四字段契约字宽锁：RV32 目标恰 16 字（任务口径）；宿主 64 位含尾 pad=24。 */
#if UINTPTR_MAX == 0xFFFFFFFFu
HAL_STATIC_ASSERT(sizeof(hal_vm_ctx_t) == 16u, "hal_vm_ctx_must_be_four_words");
#else
HAL_STATIC_ASSERT(sizeof(hal_vm_ctx_t) == 24u, "hal_vm_ctx_four_fields_host_padded");
#endif

#ifdef HAL_VM_SIM
/* 模拟缝：panic 由宿主驱动（sim main）以同名宏接管为 setjmp 捕获；
   声明供 stack_vm.c 的 sim 分支可见，定义在 sim main（只经宏调用）。 */
void sim_panic(const char *why, uint32_t pcval, const char *tag);
#endif

/* 裸机默认入口：静态区直连，code 指向 .rodata 字节码镜像（words 由调用方
   对定长数组 sizeof 求得；取显式参数而非指针，避免维度丢失）。 */
void      hal_vm_init(const uint16_t *code, uint32_t words);
/* 模拟缝：宿主测试注入静态区（对齐 HAL_MEM_SIM_HEAP 先例，不引用链接符号）。 */
void      hal_vm_init_region(const uint16_t *code, uint32_t words,
                             int32_t *stack, int32_t *mem, uint32_t mem_words);
/* 执行至 HALT/panic；返回执行步数，超 cap 强制停机并返回 cap（供看门狗断言）。 */
uint32_t  hal_vm_run(uint32_t cap);
/* 读取 OUT 观测环第 i 个值（i < hal_vm_out_count()）；越界返回 0。 */
int32_t   hal_vm_out_get(uint32_t i);
uint32_t  hal_vm_out_count(void);
#ifndef HAL_VM_SIM
/* 裸机实体落位核验（用 boot.h 的链接符号传入）：返回 0 = stack/mem 三区均在
   link.ld RAM 窗口内且不吃进堆区；非 0 = 布局违约（调用方应显式报 FAIL）。 */
int       hal_vm_layout_ok(const char *bss_start, const char *bss_end,
                           const char *heap_start);
#endif

#endif /* HAL_STACK_VM_H */
