/* tools/qemu_virt_demo/virt_demo.c — 可在 stock QEMU 上实跑的「中断接管」常驻样例。
 *
 * 目的：标准 QEMU 没有 FE310 机器（-machine virt 的 UART 是 ns16550@0x10000000、
 * RAM 在 0x80000000，与本 HAL 的 SiFive UART0@0x10013000 / FLASH@0x20000000 不匹配），
 * 故真实固件 matha_hal.elf 跑不进 stock QEMU。但 virt 的 **CLINT 在 0x02000000，
 * 与 FE310 一致**，于是这里做一个 board-matched 变体：仅把 UART 换成 ns16550、
 * 把内存映射换成 virt 的 RAM，其余「装 mtvec → 开 MTIE/MSTATUS.MIE → CLINT
 * mtimecmp 定时器中断 → ISR 打印 → 重装 → mret」的中断接管链路与生产 HAL 同构。
 *
 * 这是真 RV32 指令执行（QEMU 软件模拟 CPU），不是宿主 C 模拟；用于在 QEMU 上
 * 直观演示中断投递与 mret 返回。诚实口径：证明中断路径可被真指令集执行，
 * 仍不等于在真 FE310 板上实测。
 *
 * 运行：python run_qemu_virt_demo.py（同目录；工具链/QEMU 路径可配置，缺失如实 SKIP）。
 */
#include <stdint.h>

/* virt 机器：ns16550 UART（THr@0x10000000，LSR@0x10000005，bit5=THR 空）。 */
#define UART_THR (*(volatile uint8_t *)0x10000000u)
#define UART_LSR (*(volatile uint8_t *)0x10000005u)

/* CLINT 与 FE310 同基址 0x02000000：mtimecmp@+0x4000，mtime@+0xBFF8。 */
#define CLINT    0x02000000u
#define MTIMECMP (*(volatile uint64_t *)(CLINT + 0x4000u))
#define MTIME    (*(volatile uint64_t *)(CLINT + 0xBFF8u))

volatile int g_ticks;

static void putc_(char c) { while ((UART_LSR & 0x20u) == 0u) {} UART_THR = (uint8_t)c; }
static void puts_(const char *s) { while (*s) putc_(*s++); }
static void puthex(uint32_t x) {
    for (int i = 28; i >= 0; i -= 4) putc_("0123456789abcdef"[(x >> i) & 0xF]);
}

/* CSR 访问一律用符号名（数值 + "i" 约束在本工具链上会静默不生效）。 */
static inline uint32_t rd_mie(void) { uint32_t v; __asm__ volatile("csrr %0, mie":"=r"(v)); return v; }
static inline uint32_t rd_mip(void) { uint32_t v; __asm__ volatile("csrr %0, mip":"=r"(v)); return v; }

/* C 侧中断体：由 trap_vector（汇编）在确认 mcause=定时器后调用。 */
void hal_on_timer(void) {
    g_ticks++;
    puts_("tick ");
    putc_((char)('0' + (g_ticks % 10)));
    putc_('\n');
    MTIMECMP = MTIME + 300000ull;                 /* 重装，周期性再触发 */
}

/* 直接模式陷阱入口：保存现场 → 判 mcause=0x80000007 → 调 C → 恢复 → mret。
 * 与生产 boot/vector.S 的骨架同构（此处精简为定时器一条路径便于演示）。 */
__asm__(
".global trap_vector\n"
"trap_vector:\n"
"  addi sp,sp,-16\n"
"  sw ra,0(sp)\n  sw a0,4(sp)\n  sw a1,8(sp)\n  sw a2,12(sp)\n"
"  csrr a0,mcause\n"
"  li   t0,0x80000007\n"
"  bne  a0,t0,2f\n"
"  call hal_on_timer\n"
"2:\n"
"  lw ra,0(sp)\n  lw a0,4(sp)\n  lw a1,8(sp)\n  lw a2,12(sp)\n"
"  addi sp,sp,16\n"
"  mret\n");

int main(void) {
    extern void trap_vector(void);
    g_ticks = 0;
    __asm__ volatile("csrw mtvec, %0" :: "r"((uint32_t)(uintptr_t)&trap_vector));
    __asm__ volatile("csrs mie, %0" :: "r"(1u << 7 /*MTIE*/));

    puts_("demo boot\n");
    puts_("mie="); puthex(rd_mie()); puts_("\n");

    /* 阶段1：先不开全局 MIE，轮询确认 CLINT 会把 mip.MTIP(bit7) 置起。 */
    MTIMECMP = MTIME + 100000ull;
    uint32_t mip = 0;
    for (long i = 0; i < 50000000L; i++) {
        mip = rd_mip();
        if (mip & (1u << 7)) break;
    }
    puts_("mip="); puthex(mip); puts_(" MTIP?");
    putc_((mip & (1u << 7)) ? 'Y' : 'N'); puts_("\n");

    /* 阶段2：开全局 MIE → 定时器中断应投递，ISR 打印 tick 并重装。 */
    MTIMECMP = MTIME + 300000ull;
    __asm__ volatile("csrs mstatus, %0" :: "r"(1u << 3 /*MIE*/));
    puts_("armed, waiting IRQ\n");
    for (;;) { __asm__ volatile("wfi"); }
}
