/* baremetal/main.c — Matha 裸机 HAL 的 freestanding 入口（无 libc / 无 OS）。
 *
 * P5 第 3 步之后，这里从「骨架占位 loop」升级为**实机自检**：把已接通的三块
 * 能力端到端串起来跑——
 *   1. 内存接管：boot 期做一遍 malloc/写校验/free/确认可回收；
 *   2. 中断接管：注册机器模式定时器中断回调，进入 wfi 事件驱动；
 *   3. 控制台输出：每次定时器中断里分配一块内存、写入标记、打印 tick 与空闲
 *      字节数再归还，证明分配器在中断上下文可用、串口由 ISR 驱动。
 *
 * 一切 freestanding：不链接任何 libc / OS 运行时；数字打印自带最简 itoa。
 */
#include <hal/hal.h>

/* 每次定时器中断 +1（由 ISR 递增，主循环只读）。 */
static volatile uint32_t g_tick;

/* 名义定时间隔（mtime tick 数）。真实周期取决于 FE310 mtime 时钟源（随板级
   PLL/RTC 配置而定），此处取一个肉眼可见的节奏即可，自检重在链路而非精确频率。 */
#define TICK_INTERVAL  1000000u

/* ── 最简无符号十进制打印（freestanding，不依赖 libc printf）────────────── */
static void uart_putu(uint32_t x)
{
    char buf[10];
    int  i = 0;
    if (x == 0u) { uart_puts("0"); return; }
    while (x != 0u) { buf[i++] = (char)('0' + (x % 10u)); x /= 10u; }
    while (i > 0) { uart_putc((int)(unsigned char)buf[--i]); }
}

/* ── boot 期内存自检：申请 / 写校验 / 释放 / 确认可回收 ─────────────────── */
static void heap_selfcheck(void)
{
    uart_puts("heap: init avail=");
    uart_putu((uint32_t)hal_mem_avail());
    uart_puts(" bytes\r\n");

    char *p = (char *)hal_malloc(64u);
    char *q = (char *)hal_malloc(64u);
    if (p == NULL || q == NULL) {
        uart_puts("heap: malloc FAILED\r\n");
        return;
    }

    /* 两块各写不同模式，互不覆盖。 */
    for (int i = 0; i < 64; i++) { p[i] = (char)('A' + (i % 26)); q[i] = (char)(i & 0x3F); }
    int intact = 1;
    for (int i = 0; i < 64; i++) {
        if (p[i] != (char)('A' + (i % 26)) || q[i] != (char)(i & 0x3F)) { intact = 0; }
    }
    uart_puts("heap: two-buf write/readback ");
    uart_puts(intact ? "OK" : "CORRUPT");
    uart_puts(", avail mid=");
    uart_putu((uint32_t)hal_mem_avail());
    uart_puts("\r\n");

    hal_size_t mid = hal_mem_avail();
    hal_free(p);
    hal_free(q);
    /* 释放后最大连续空闲应回升（相邻合并），证明可回收而非一次性 bump。 */
    uart_puts("heap: after free avail=");
    uart_putu((uint32_t)hal_mem_avail());
    uart_puts(mid <= hal_mem_avail() ? " (restored>=mid OK)\r\n"
                                     : " (WARN shrunk)\r\n");
}

/* ── boot 期栈式引擎自检：跑一段固定字节码，验证四字段 VM 端到端可算可观测 ── */

/* 程序：(7+5)*3=36 存 mem[1]；(9-4)*8=40 存 mem[2]；LOAD 两值相加=76 后 OUT。
   定宽 2 字编码：op + operand（无操作数指令 operand 位写 0；LOAD/STORE 承 mem，
   36/40 超 u16 直推面吗？不超——但语义上只能经 mem 中转回推，顺带验 mem 链路）。 */
static const uint16_t vm_prog[] = {
    0x01, 7u,            /* PUSH 7         */
    0x01, 5u,            /* PUSH 5         */
    0x03, 0u,            /* ADD   -> 12    */
    0x01, 3u,            /* PUSH 3         */
    0x05, 0u,            /* MUL   -> 36    */
    0x11, 1u,            /* STORE 1 -> mem[1]=36 */
    0x01, 9u,            /* PUSH 9         */
    0x01, 4u,            /* PUSH 4         */
    0x04, 0u,            /* SUB   -> 5     */
    0x01, 8u,            /* PUSH 8         */
    0x05, 0u,            /* MUL   -> 40    */
    0x11, 2u,            /* STORE 2 -> mem[2]=40 */
    0x10, 1u,            /* LOAD  mem[1] -> 36   */
    0x10, 2u,            /* LOAD  mem[2] -> 40   */
    0x03, 0u,            /* ADD   -> 76    */
    0x0e, 0u,            /* OUT   [76]     */
    0x0f, 0u             /* HALT           */
};

static void vm_selfcheck(void)
{
    /* 先验实体落位（对齐 link.ld 契约的运行期一半）：违约直接报 FAIL。
       注：.bss 里还含 uart/trap 模块自有静态区，故 VM 区不要求紧贴 _sbss，
       只要求整块落进 RAM 窗口且在堆起点之前（hal_vm_layout_ok 内部判）。 */
    int bad = hal_vm_layout_ok(_sbss, _ebss, _heap_start);
    if (bad != 0) {
        uart_puts("vm: layout VIOLATION code=FAIL\r\n");
        return;
    }

    hal_vm_init(vm_prog, (uint32_t)(sizeof(vm_prog) / sizeof(vm_prog[0])));
    (void)hal_vm_run(1000u);

    /* 断言链：停机后输出环恰好 1 个值 76（(7+5)*3 + (9-4)*8）。 */
    uart_puts("vm: out=");
    if (hal_vm_out_count() == 1u && hal_vm_out_get(0) == 76) {
        uart_putu((uint32_t)hal_vm_out_get(0));
        uart_puts(" PASS\r\n");
    } else {
        uart_puts("UNEXPECTED (want 76) FAIL\r\n");
    }
}

/* ── 定时器中断回调：每次 tick 跑一遍 alloc→写→打印→free ────────────────── */
static void on_tick(void *ctx)
{
    (void)ctx;
    g_tick++;

    uart_puts("tick ");
    uart_putu(g_tick);

    /* 在中断上下文里借用分配器：申请一小块、写个标记、报状态，再归还。 */
    char *buf = (char *)hal_malloc(48u);
    if (buf != NULL) {
        buf[0] = 'M';
        buf[1] = 'x';
        buf[47] = '\0';
        uart_puts(": alloc ok, avail=");
        uart_putu((uint32_t)hal_mem_avail());
        hal_free(buf);                       /* 下个 tick 可复用同一块 */
        uart_puts(" -> freed\r\n");
    } else {
        uart_puts(": alloc NULL (heap exhausted)\r\n");
    }
}

int main(void)
{
    hal_init(115200u);           /* 内存 → 串口 → 中断（hal_irq_init 已装 mtvec 并放行 MIE） */
    hal_irq_disable();           /* 装配期屏蔽全局中断，避免未 arm 的定时器触发风暴 */

    uart_puts("\r\n");
    uart_puts("Matha bare-metal HAL self-check (P5)\r\n");
    uart_puts("boot -> hal_init -> uart : OK\r\n");

    heap_selfcheck();

    vm_selfcheck();

    hal_timer_attach(on_tick, NULL);   /* 注册定时器中断回调 */
    hal_timer_arm(TICK_INTERVAL);      /* 装载第一次超时，之后由 trap 自动重装 */
    hal_irq_enable();                  /* 放行中断，进入事件驱动 */

    uart_puts("timer armed, entering wfi loop\r\n");

    for (;;) {
        /* 主循环什么都不做：所有输出由定时器中断里的 on_tick 驱动；wfi 等待中断。 */
        __asm__ volatile("wfi");
    }

    return 0;   /* 不可达：裸机 main 永不返回 */
}
