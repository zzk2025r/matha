/* tools/sim/trap_sim_main.c — 宿主上驱动真实 hal/trap/trap.c 的寄存器级测试。
 *
 * 与裸机固件用【同一份】trap.c，只是把 CSR（mtvec/mie/mstatus）与 MMIO
 * （CLINT mtimecmp、PLIC claim/complete）接到 hal_platform_sim.c 的模型上，
 * 从而在没有真硬件、也不执行 vector.S 的情况下，验证陷入分派逻辑：
 *   1) hal_irq_init 装 mtvec、开 mie.MTIE|MEIE、mstatus.MIE；
 *   2) 定时器中断重装 mtimecmp = mtime + ticks（清 MTIP）；
 *   3) 外部中断经 PLIC claim 路由已注册处理函数并 complete 写回；
 *   4) 未知源/软件中断不崩溃。
 *
 * vector.S 本身是纯汇编不在此执行，其正确性由交叉编译进 RV32 ELF 证明。
 */
#include <stdio.h>
#include <stdint.h>

#define HAL_MMIO_SIM 1
#define HAL_CSR_SIM  1
#include <hal/hal.h>

/* trap.c 引用的汇编陷入入口——宿主测试用桩替代（真固件由 vector.S 提供）。 */
void trap_vector(void) { }

/* 模拟后端接口（见 hal_platform_sim.c）。 */
extern void     sim_platform_reset(void);
extern uint32_t sim_csr_get(uint16_t csr);
extern void     sim_mtime_set(uint32_t lo);
extern uint32_t sim_get_mtimecmp(void);
extern void     sim_plic_push_claim(uint32_t src);
extern uint32_t sim_plic_last_complete(void);

static int g_fails;

static void ok(const char *n)                      { printf("  [ok]   %s\n", n); }
static void fail(const char *n)                   { printf("  [FAIL] %s\n", n); g_fails++; }
static void eq_u32(const char *n, uint32_t got, uint32_t exp)
{
    if (got == exp) { printf("  [ok]   %s = 0x%x\n", n, got); }
    else            { printf("  [FAIL] %s = 0x%x (期望 0x%x)\n", n, got, exp); g_fails++; }
}
static void cond(const char *n, int c)             { c ? ok(n) : fail(n); }

/* PLIC 源处理函数：记录被调用次数与传入 ctx。 */
static int  g_isr_calls;
static void *g_isr_ctx;
static void test_isr(void *ctx) { g_isr_calls++; g_isr_ctx = ctx; }

/* 定时器中断回调：记录被调用次数与传入 ctx（验证 hal_timer_attach 接缝）。 */
static int  g_tick_calls;
static void *g_tick_ctx;
static void test_timer_cb(void *ctx) { g_tick_calls++; g_tick_ctx = ctx; }

int main(void)
{
    printf("=== FE310 中断接管 宿主寄存器级模拟 ===\n");

    /* 1) hal_irq_init：装 mtvec + 开中断使能。 */
    sim_platform_reset();
    hal_irq_init();
    uint32_t mtvec = sim_csr_get(HAL_CSR_MTVEC);
    cond("mtvec 已指向 trap_vector（非空）", mtvec != 0u);
    cond("mtvec Direct 模式（低两位=0）", (mtvec & 3u) == 0u);
    eq_u32("mie = MTIE|MEIE", sim_csr_get(HAL_CSR_MIE), MIE_MTIE | MIE_MEIE);
    cond("mstatus.MIE 已置", (sim_csr_get(HAL_CSR_MSTATUS) & MSTATUS_MIE) != 0u);

    /* 关/开全局中断。 */
    hal_irq_disable();
    cond("hal_irq_disable 清 mstatus.MIE", (sim_csr_get(HAL_CSR_MSTATUS) & MSTATUS_MIE) == 0u);
    hal_irq_enable();
    cond("hal_irq_enable 置 mstatus.MIE", (sim_csr_get(HAL_CSR_MSTATUS) & MSTATUS_MIE) != 0u);

    /* 2) 定时器中断：arm 后重装 mtimecmp = mtime + ticks。 */
    sim_platform_reset();
    hal_timer_arm(50u);
    eq_u32("首次 hal_timer_arm(50) → mtimecmp", sim_get_mtimecmp(), 50u);
    sim_mtime_set(2000u);
    hal_trap_handler(HAL_MCAUSE_INTERRUPT | HAL_IRQ_M_TIMER, 0u, 0u);
    eq_u32("定时器中断重装 → mtimecmp(=2000+50)", sim_get_mtimecmp(), 2050u);

    /* 3) 外部中断：PLIC claim → 路由处理函数 → complete 写回。 */
    sim_platform_reset();
    int sentinel = 0x5a5a;
    hal_irq_attach(5u, test_isr, &sentinel);
    g_isr_calls = 0; g_isr_ctx = NULL;
    sim_plic_push_claim(5u);
    hal_trap_handler(HAL_MCAUSE_INTERRUPT | HAL_IRQ_M_EXTERNAL, 0u, 0u);
    eq_u32("外部中断：已注册源 5 的 ISR 调用次数", (uint32_t)g_isr_calls, 1u);
    cond("ISR 收到注册时的 ctx", g_isr_ctx == (void *)&sentinel);
    eq_u32("PLIC complete 写回源号", sim_plic_last_complete(), 5u);

    /* 4) 未知源（无处理函数）不崩溃，仍 complete 写回。 */
    sim_platform_reset();
    sim_plic_push_claim(9u);
    hal_trap_handler(HAL_MCAUSE_INTERRUPT | HAL_IRQ_M_EXTERNAL, 0u, 0u);
    eq_u32("未知源 9 无 ISR 仍 complete", sim_plic_last_complete(), 9u);

    /* 5) 软件中断：无副作用，正常返回（若卡死则测试超时）。 */
    sim_platform_reset();
    hal_trap_handler(HAL_MCAUSE_INTERRUPT | HAL_IRQ_M_SOFTWARE, 0u, 0u);
    ok("软件中断正常返回");

    /* 6) 定时器回调接缝 hal_timer_attach：定时器中断先跑回调再自动重装。 */
    sim_platform_reset();
    int tctx = 0x77;
    g_tick_calls = 0; g_tick_ctx = NULL;
    hal_timer_attach(test_timer_cb, &tctx);
    hal_timer_arm(60u);
    sim_mtime_set(3000u);
    hal_trap_handler(HAL_MCAUSE_INTERRUPT | HAL_IRQ_M_TIMER, 0u, 0u);
    eq_u32("定时器回调调用次数", (uint32_t)g_tick_calls, 1u);
    cond("定时器回调收到注册时的 ctx", g_tick_ctx == (void *)&tctx);
    eq_u32("回调后仍自动重装 mtimecmp(=3000+60)", sim_get_mtimecmp(), 3060u);

    /* 7) 卸载回调（attach NULL）：定时器中断不再跑回调，但仍重装。 */
    hal_timer_attach(NULL, NULL);
    g_tick_calls = 0;
    sim_mtime_set(5000u);
    hal_trap_handler(HAL_MCAUSE_INTERRUPT | HAL_IRQ_M_TIMER, 0u, 0u);
    eq_u32("卸载后回调不再被调用", (uint32_t)g_tick_calls, 0u);
    eq_u32("卸载后仍重装 mtimecmp(=5000+60)", sim_get_mtimecmp(), 5060u);

    if (g_fails == 0) {
        printf("结果：中断接管寄存器级模拟全部通过（真实 trap.c，未执行 vector.S）\n");
        return 0;
    }
    printf("结果：中断模拟失败 %d 项\n", g_fails);
    return 1;
}
