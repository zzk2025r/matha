/* hal/trap/trap.c — 机器模式陷阱/中断接管（P5 第 3 步）。
 *
 * 通过 csr.h（mtvec/mie/mstatus）+ mmio.h（CLINT mtimecmp、PLIC claim/complete）
 * 接管陷入：
 *   - hal_irq_init()：mtvec←trap_vector（Direct），mie←MTIE|MEIE，mstatus.MIE←1；
 *   - hal_trap_handler()：按 mcause 分派——定时器中断重装 mtimecmp（清 MTIP）、
 *     外部中断经 PLIC claim 取源号→路由已注册处理函数→complete 写回；
 *     同步异常无安全恢复路径则停机。
 *
 * 全部经由 csr.h/mmio.h 抽象，故可在 tools/sim 的宿主寄存器级模拟中逐条验证
 * （HAL_CSR_SIM + HAL_MMIO_SIM）。
 */
#include <hal/hal.h>

#define HAL_MAX_IRQ_SOURCES 32u

/* boot/vector.S 中的汇编陷入入口（由 mtvec 指向）。 */
extern void trap_vector(void);

static hal_irq_fn g_irq_fn[HAL_MAX_IRQ_SOURCES];
static void      *g_irq_ctx[HAL_MAX_IRQ_SOURCES];
static uint32_t   g_timer_ticks;   /* 上次装载的定时间隔，用于周期性重装 */

void hal_irq_init(void)
{
    /* mtvec 低两位为模式：00=Direct。trap_vector 至少 4 字节对齐，低两位为 0。 */
    hal_csr_write(HAL_CSR_MTVEC, (uint32_t)(hal_addr_t)&trap_vector);
    hal_csr_set(HAL_CSR_MIE, MIE_MTIE | MIE_MEIE);
    hal_csr_set(HAL_CSR_MSTATUS, MSTATUS_MIE);
}

void hal_irq_enable(void)
{
    hal_csr_set(HAL_CSR_MSTATUS, MSTATUS_MIE);
}

void hal_irq_disable(void)
{
    hal_csr_clr(HAL_CSR_MSTATUS, MSTATUS_MIE);
}

void hal_irq_attach(uint32_t source, hal_irq_fn fn, void *ctx)
{
    if (source < HAL_MAX_IRQ_SOURCES) {
        g_irq_fn[source]  = fn;
        g_irq_ctx[source] = ctx;
    }
}

void hal_timer_arm(uint32_t ticks)
{
    /* 读 CLINT mtime 低 32 位，置 mtimecmp0 = mtime + ticks；写 mtimecmp 清 MTIP。 */
    uint32_t now = hal_readl(FE310_CLINT_BASE + CLINT_MTIME);
    hal_writel(now + ticks, FE310_CLINT_BASE + CLINT_MTIMECMP0);
    g_timer_ticks = ticks;
}

void hal_trap_handler(uint32_t mcause, uint32_t mepc, uint32_t mtval)
{
    (void)mepc;
    (void)mtval;

    if ((mcause & HAL_MCAUSE_INTERRUPT) != 0u) {
        uint32_t code = mcause & ~HAL_MCAUSE_INTERRUPT;
        if (code == HAL_IRQ_M_TIMER) {
            /* 重装下一次超时，退出后 MTIP 保持清除。 */
            hal_timer_arm(g_timer_ticks);
        } else if (code == HAL_IRQ_M_EXTERNAL) {
            /* claim 取当前最高优先级源；处理完把源号写回 claim 寄存器即 complete。 */
            uint32_t src = hal_readl(FE310_PLIC_BASE + PLIC_CLAIM0);
            if (src != 0u && src < HAL_MAX_IRQ_SOURCES && g_irq_fn[src] != NULL) {
                g_irq_fn[src](g_irq_ctx[src]);
            }
            hal_writel(src, FE310_PLIC_BASE + PLIC_CLAIM0);
        }
        /* code == HAL_IRQ_M_SOFTWARE：无副作用，交回调用方清 msip。 */
    } else {
        /* 同步异常：骨架阶段无安全恢复路径，停机以避免破坏状态继续跑飞。 */
        for (;;) {
            /* halt */
        }
    }
}
