/* tools/qemu_virt_demo/main.c — QEMU virt (rv32) 上的「中断接管 + UART 打印」演示。
 *
 * 演示链路（与生产 HAL 同构，只是 UART/内存映射 board-match 到 virt）：
 *   uart_init() 初始化 ns16550 → 装 mtvec → 开 MTIE + MSTATUS.MIE →
 *   CLINT mtimecmp 定时器中断 → trap 入口判 mcause=0x80000007 → 调 C ISR →
 *   ISR 里每隔一段时间用 uart 打印 "Hello RISC-V! tick=N" → 重装 mtimecmp → mret。
 *
 * 这是真 RV32 指令执行（QEMU 软件模拟 CPU），不是宿主 C 模拟。诚实口径：证明中断
 * 路径可被真指令集在 QEMU 上执行，仍不等于在真 FE310 板实测。
 *
 * 运行：python run_qemu_virt_demo.py（同目录；工具链/QEMU 可配，缺失如实 SKIP）。
 */
#include <stdint.h>
#include "uart.h"

/* virt 的 CLINT 基址与 FE310 一致：mtimecmp@+0x4000，mtime@+0xBFF8。 */
#define CLINT    0x02000000u
#define MTIMECMP (*(volatile uint64_t *)(CLINT + 0x4000u))
#define MTIME    (*(volatile uint64_t *)(CLINT + 0xBFF8u))

/* 每次定时器中断 +1；ISR 打印它，主循环之外由中断驱动。 */
volatile uint32_t g_ticks;

/* 十六进制打印（供 mie/mip 诊断）。 */
static void puthex(uint32_t x)
{
    for (int i = 28; i >= 0; i -= 4) {
        uart_putc("0123456789abcdef"[(x >> i) & 0xF]);
    }
}

/* 十进制打印（供 tick 计数）。 */
static void putdec(uint32_t x)
{
    char buf[10];
    int i = 0;
    if (x == 0u) { uart_putc('0'); return; }
    while (x) { buf[i++] = (char)('0' + (x % 10u)); x /= 10u; }
    while (i) { uart_putc(buf[--i]); }
}

/* CSR 访问一律用符号名（数值 + "i" 约束在本工具链上会静默不生效）。 */
static inline uint32_t rd_mie(void) { uint32_t v; __asm__ volatile("csrr %0, mie" : "=r"(v)); return v; }
static inline uint32_t rd_mip(void) { uint32_t v; __asm__ volatile("csrr %0, mip" : "=r"(v)); return v; }

/* C 侧定时器中断体：由 trap_vector（汇编）在确认 mcause=定时器后调用。
   每触发一次就通过 uart 打印一句 "Hello RISC-V! tick=N"，再重装 mtimecmp 周期化。 */
void hal_on_timer(void)
{
    g_ticks++;
    uart_puts("Hello RISC-V! tick=");
    putdec(g_ticks);
    uart_puts("\n");
    MTIMECMP = MTIME + 300000ull;   /* 下次中断：约 30 万 ticks 后，肉眼可见的节奏 */
}

/* 直接模式陷阱入口：保存现场 → 判 mcause=0x80000007 → 调 C ISR → 恢复 → mret。
   与生产 boot/vector.S 骨架同构（此处精简为定时器一条路径便于演示）。 */
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

int main(void)
{
    extern void trap_vector(void);

    uart_init(115200u);
    g_ticks = 0u;
    uart_puts("matha QEMU virt demo boot\n");

    /* 装向量 + 使能定时器中断源（先不开全局 MIE）。 */
    __asm__ volatile("csrw mtvec, %0" :: "r"((uint32_t)(uintptr_t)&trap_vector));
    __asm__ volatile("csrs mie, %0" :: "r"(1u << 7 /*MTIE*/));
    uart_puts("mie="); puthex(rd_mie()); uart_puts("\n");

    /* 阶段1：轮询确认 CLINT 会把 mip.MTIP(bit7) 置起（证明定时器本身在工作）。 */
    MTIMECMP = MTIME + 100000ull;
    uint32_t mip = 0u;
    for (long i = 0; i < 50000000L; i++) {
        mip = rd_mip();
        if (mip & (1u << 7)) { break; }
    }
    uart_puts("mip="); puthex(mip); uart_puts(" MTIP?");
    uart_putc((mip & (1u << 7)) ? 'Y' : 'N'); uart_puts("\n");

    /* 阶段2：开全局 MIE → 定时器中断应投递，ISR 持续打印 "Hello RISC-V! tick=N"。 */
    MTIMECMP = MTIME + 300000ull;
    __asm__ volatile("csrs mstatus, %0" :: "r"(1u << 3 /*MSTATUS.MIE*/));
    uart_puts("armed, waiting IRQ\n");
    for (;;) {
        __asm__ volatile("wfi");
    }
}
