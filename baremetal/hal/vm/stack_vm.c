/* hal/vm/stack_vm.c — 裸机栈式引擎（极简契约优先）实现。
 *
 * 契约（与 include/hal/stack_vm.h 逐条对应，此处只登记实现口径）：
 *   - 分发：单 switch-case，无函数表、无线程跳转（刻意直白）。
 *   - panic：栈溢出/栈空/除零/代码越界/非法 op/输出环满 → 串口报因后 wfi 停机，
 *     绝不静默产错值（对齐主线 native 1a/1c 红线在裸机侧的同一纪律）。
 *   - 区来源：裸机 = .bss 静态区（crt0 启动清零，落 link.ld 的 .bss/.heap 契约
 *     之内，不碰分配器堆）；宿主模拟 = hal_vm_init_region 注入（HAL_VM_SIM 缝，
 *     对齐 allocator.c 的 HAL_MEM_SIM_HEAP 先例）。
 *   - LOAD/STORE 与 OUT/HALT 为最小可运行版的刚需扩展：没有 mem 指令则 ctx 的
 *     mem 字段无从访问；没有停机就无法定义「跑完」，没有输出环宿主断言与
 *     boot 自检都无从观测；共四条，不扩语法糖。
 *   - 指令定宽 2 字（op + operand 各一字）：每轮循环固定取两字，pc 恒指向
 *     指令起点（偶字下标）；无操作数指令 operand 位写 0 并被统一取走。
 *     上一版「按需取 operand」的变长分发会让算术/栈指令的操作数位被当作
 *     下一条 op，导致 pc 错位（宿主模拟实跑复现过），故此处不做妥协。
 */
#include <hal/hal.h>

/* ── .bss 静态区：落 link.ld 的 RAM 窗口，crt0 已清零，不占分配器堆 ────── */
static int32_t g_stack[HAL_VM_STACK_WORDS];
static int32_t g_mem[HAL_VM_MEM_WORDS];
static int32_t g_out[HAL_VM_OUT_RING];

static hal_vm_ctx_t g_ctx;          /* 唯一实例：极简契约，不做多 VM        */
static const uint16_t *g_code;      /* 字节码镜像（裸机放 .rodata，XIP）    */
static uint32_t g_code_words;       /* 代码区字数上界（越界即 panic）       */
static uint32_t g_mem_words;        /* 数据区字数上界（sim 注入可缩容）     */
static uint32_t g_out_count;

/* 默认 panic（裸机）：报因 → 经 UART 打印当前 PC + 触发值（非法 op 时即
   OpCode，跳转类时即目标址）→ wfi 死循环。模拟构建改由 sim main 提供
   sim_panic（setjmp 捕获，需要「断言 panic 确实发生」的能力），本 TU 经同名宏接上。 */
#ifdef HAL_VM_SIM
#define hal_vm_panic(why, pcval) sim_panic((why), (pcval), "sim")
#else
static void vm_put_hex32(uint32_t v)
{
    static const char hexd[] = "0123456789abcdef";
    char buf[9];
    int i = 0;
    for (int s = 28; s >= 0; s -= 4) {
        buf[i++] = hexd[(v >> s) & 0xFu];
    }
    buf[i] = '\0';
    uart_puts(buf);
}

static void vm_panic_bare(const char *why, uint32_t whyval)
{
    /* 极简调试接口：只经 UART 打印 PC 指针与触发值两个字段，不引入复杂报错系统。 */
    uart_puts("VM PANIC: ");
    uart_puts(why);
    uart_puts(" pc=0x");
    vm_put_hex32(g_ctx.pc);
    uart_puts(" val=0x");
    vm_put_hex32(whyval);
    uart_puts("\r\n");
    for (;;) {
        __asm__ volatile("wfi");
    }
}
#define hal_vm_panic vm_panic_bare   /* 裸机分支：同名直调 */
#endif

/* 编译期预算守卫（纯常量求值，不引用实体地址）：VM 三区总字节必须装得下
   link.ld 的 128K RAM 窗口（另要让给 .data/.bss 其余成员与分配器堆）。
   实体落位核验改由裸机 vm_selfcheck 运行期用 _sbss/_ebss/_heap_start 符号断言
   （见 main.c），两者合起来钉住「对齐现有 link.ld」契约。 */
#define HAL_VM_TOTAL_BYTES \
    ((uint32_t)sizeof(g_stack) + (uint32_t)sizeof(g_mem) + (uint32_t)sizeof(g_out))
HAL_STATIC_ASSERT(HAL_VM_TOTAL_BYTES <= HAL_RAM_BYTES / 2u,
                  "hal_vm_regions_exceed_ram_window_budget");

/* ── 栈原语：溢出/栈空都在写入之前 panic（不产生半更新状态）────────────── */
static void vm_push(int32_t v)
{
    if (g_ctx.sp >= HAL_VM_STACK_WORDS) {
        hal_vm_panic("stack overflow", g_ctx.pc);
    }
    g_ctx.stack[g_ctx.sp++] = v;
}

static int32_t vm_pop(void)
{
    if (g_ctx.sp == 0u) {
        hal_vm_panic("stack underflow", g_ctx.pc);
    }
    return g_ctx.stack[--g_ctx.sp];
}

static int32_t vm_peek(void)
{
    if (g_ctx.sp == 0u) {
        hal_vm_panic("stack underflow", g_ctx.pc);
    }
    return g_ctx.stack[g_ctx.sp - 1u];
}

/* 定宽取字：越界即 panic（调用方保证每轮恰好取两字）。 */
static uint16_t vm_fetch(void)
{
    if (g_ctx.pc >= g_code_words) {
        hal_vm_panic("code overrun", g_ctx.pc);
    }
    return g_code[g_ctx.pc++];
}

void hal_vm_init(const uint16_t *code, uint32_t words)
{
    hal_vm_init_region(code, words, g_stack, g_mem, HAL_VM_MEM_WORDS);
}

void hal_vm_init_region(const uint16_t *code, uint32_t words,
                        int32_t *stack, int32_t *mem, uint32_t mem_words)
{
    g_code       = code;
    g_code_words = words;      /* 调用方对定长数组 sizeof 求得，越界访问均 panic */
    g_mem_words  = mem_words;
    g_out_count  = 0u;
    g_ctx.pc = 0u;
    g_ctx.sp = 0u;
    g_ctx.stack = stack;
    g_ctx.mem = mem;
}

uint32_t hal_vm_run(uint32_t cap)
{
    uint32_t steps = 0u;
    int running = 1;

    while (running && steps < cap) {
        /* 定宽 2 字：先取 op，再统一取 operand（不需要的指令其位写 0）。 */
        const uint16_t op = vm_fetch();
        const uint16_t w  = vm_fetch();
        int32_t a, b;
        uint32_t target = w;

        switch (op) {
        case HAL_VM_PUSH:
            vm_push((int32_t)w);                 /* operand 按 u16 直推 */
            break;
        case HAL_VM_POP:
            (void)vm_pop();
            break;
        case HAL_VM_LOAD:
            if (target >= g_mem_words) {
                hal_vm_panic("mem index OOB", target);
            }
            vm_push(g_ctx.mem[target]);
            break;
        case HAL_VM_STORE:
            a = vm_pop();
            if (target >= g_mem_words) {
                hal_vm_panic("mem index OOB", target);
            }
            g_ctx.mem[target] = a;
            break;
        case HAL_VM_ADD:
            b = vm_pop(); a = vm_pop();
            vm_push(a + b);
            break;
        case HAL_VM_SUB:
            b = vm_pop(); a = vm_pop();
            vm_push(a - b);
            break;
        case HAL_VM_MUL:
            b = vm_pop(); a = vm_pop();
            vm_push(a * b);
            break;
        case HAL_VM_DIV:
            b = vm_pop(); a = vm_pop();
            if (b == 0) {
                hal_vm_panic("divide by zero", g_ctx.pc);
            }
            if (a == INT32_MIN && b == -1) {
                /* RV32IM 硬件对 -2^31/-1 静默回绕产出 -2^31（错误值）；
                   VM 层显式拒绝，与主线 SPIKE 后端同一纪律。 */
                hal_vm_panic("division overflow", g_ctx.pc);
            }
            vm_push(a / b);                      /* C99 截断向零，对齐 RV32IM */
            break;
        case HAL_VM_DUP:
            vm_push(vm_peek());
            break;
        case HAL_VM_SWAP:
            /* 先 peek 做深度检查，再手动还原 pop/push 保证原序交换：
               [a,b] -> [b,a]（b 为栈顶；不用异或交换——栈里可能同址）。 */
            (void)vm_peek();
            b = vm_pop(); a = vm_pop();
            vm_push(b); vm_push(a);
            break;
        case HAL_VM_JMP:
            if (target >= g_code_words) {
                hal_vm_panic("jump out of code", target);
            }
            g_ctx.pc = target;
            break;
        case HAL_VM_JZ:
            if (vm_peek() == 0) {
                if (target >= g_code_words) {
                    hal_vm_panic("jump out of code", target);
                }
                g_ctx.pc = target;
            }
            break;
        case HAL_VM_JNZ:
            if (vm_peek() != 0) {
                if (target >= g_code_words) {
                    hal_vm_panic("jump out of code", target);
                }
                g_ctx.pc = target;
            }
            break;
        case HAL_VM_CALL:
            if (target >= g_code_words) {
                hal_vm_panic("call out of code", target);
            }
            /* 定宽 2 字：此时 pc 已指向下一条指令起点，即返回地址 */
            vm_push((int32_t)g_ctx.pc);
            g_ctx.pc = target;
            break;
        case HAL_VM_RET:
            g_ctx.pc = (uint32_t)vm_pop();
            if (g_ctx.pc >= (g_code_words - 1u)) {
                /* 返回址必须落在某条指令的 op 位（偶下标）且后面还有 operand 可取 */
                hal_vm_panic("ret out of code", g_ctx.pc);
            }
            break;
        case HAL_VM_OUT:
            if (g_out_count >= HAL_VM_OUT_RING) {
                hal_vm_panic("out ring full", g_out_count);
            }
            g_out[g_out_count++] = vm_peek();
            break;
        case HAL_VM_HALT:
            running = 0;
            break;
        default:
            hal_vm_panic("illegal opcode", op);
            break;
        }
        steps++;
    }
    return steps;
}

int32_t hal_vm_out_get(uint32_t i)
{
    return (i < g_out_count) ? g_out[i] : 0;
}

uint32_t hal_vm_out_count(void)
{
    return g_out_count;
}

/* 裸机实体落位核验（仅非模拟构建提供；调用方在 main 里用链接符号断言）：
   返回 0 = 三区均在 [HAL_RAM_ORIGIN, HAL_RAM_END) 内且位于堆区起点之前。 */
#ifndef HAL_VM_SIM
int hal_vm_layout_ok(const char *bss_start, const char *bss_end, const char *heap_start)
{
    const hal_addr_t lo = HAL_RAM_ORIGIN, hi = HAL_RAM_END;
    hal_addr_t s0 = (hal_addr_t)(uintptr_t)g_stack;
    hal_addr_t s1 = (hal_addr_t)(uintptr_t)&g_stack[HAL_VM_STACK_WORDS];
    hal_addr_t m0 = (hal_addr_t)(uintptr_t)g_mem;
    hal_addr_t m1 = (hal_addr_t)(uintptr_t)&g_mem[HAL_VM_MEM_WORDS];
    (void)bss_start; (void)bss_end;
    if (s0 < lo || s1 > hi) { return 1; }
    if (m0 < lo || m1 > hi) { return 2; }
    if (m1 > (hal_addr_t)(uintptr_t)heap_start) { return 3; }  /* 吃进堆区 */
    return 0;
}
#endif
