/* tools/sim/hal_platform_sim.c — 宿主「寄存器级」CSR + CLINT/PLIC 模拟后端。
 *
 * 同时实现两个接缝（供第 3 步 trap 模拟）：
 *   - csr.h（HAL_CSR_SIM）：hal_csr_read/write/set/clr → 一个按 CSR 编号索引的模拟 CSR 堆；
 *   - mmio.h（HAL_MMIO_SIM）：hal_readl/writel/set/clrbits → CLINT(0x02000000) 与
 *     PLIC(0x0C000000) 窗口模型（mtime/mtimecmp、claim/complete）。
 *
 * 这是宿主测试代码（用 <stdio.h>），不在 check_skeleton 的 freestanding C_SOURCES
 * 扫描范围内，也不参与裸机固件构建。
 */
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#define HAL_MMIO_SIM 1
#define HAL_CSR_SIM  1
#include <hal/hal.h>

/* ── CSR 模型 ──────────────────────────────────────────────── */
#define CSR_FILE_N 0x400u
static uint32_t g_csr[CSR_FILE_N];

uint32_t hal_csr_read(uint16_t csr)
{
    return (csr < CSR_FILE_N) ? g_csr[csr] : 0u;
}
void hal_csr_write(uint16_t csr, uint32_t val)
{
    if (csr < CSR_FILE_N) { g_csr[csr] = val; }
}
void hal_csr_set(uint16_t csr, uint32_t mask)
{
    if (csr < CSR_FILE_N) { g_csr[csr] |= mask; }
}
void hal_csr_clr(uint16_t csr, uint32_t mask)
{
    if (csr < CSR_FILE_N) { g_csr[csr] &= ~mask; }
}

/* ── CLINT / PLIC 模型 ─────────────────────────────────────── */
static uint32_t g_msip0, g_mtime_lo, g_mtime_hi, g_mtimecmp_lo, g_mtimecmp_hi;
static uint32_t g_thresh0, g_enable0;
static uint32_t g_claim_q[16];
static int      g_claim_head, g_claim_tail;
static uint32_t g_last_complete;

static int in_region(hal_addr_t a, hal_addr_t base, hal_addr_t size)
{
    return (a >= base) && (a < (base + size));
}

/* SiFive PLIC 的 context0 阈值/claim 在偏移 0x200000 区，故窗口需覆盖到 0x200010+。 */
#define CLINT_WIN 0x100000u
#define PLIC_WIN  0x200010u

void hal_writel(uint32_t val, hal_addr_t addr)
{
    if (in_region(addr, (hal_addr_t)FE310_CLINT_BASE, CLINT_WIN)) {
        uint32_t off = (uint32_t)(addr - (hal_addr_t)FE310_CLINT_BASE);
        switch (off) {
        case CLINT_MSIP0:        g_msip0 = val; break;
        case CLINT_MTIMECMP0:    g_mtimecmp_lo = val; break;
        case CLINT_MTIMECMP0_HI: g_mtimecmp_hi = val; break;
        case CLINT_MTIME:        g_mtime_lo = val; break;
        case CLINT_MTIME_HI:     g_mtime_hi = val; break;
        default: break;
        }
    } else if (in_region(addr, (hal_addr_t)FE310_PLIC_BASE, PLIC_WIN)) {
        uint32_t off = (uint32_t)(addr - (hal_addr_t)FE310_PLIC_BASE);
        switch (off) {
        case PLIC_CLAIM0:  g_last_complete = val; break;   /* 写 claim = complete */
        case PLIC_THRESH0: g_thresh0 = val; break;
        case PLIC_ENABLE0: g_enable0 = val; break;
        default: break;
        }
    }
}

uint32_t hal_readl(hal_addr_t addr)
{
    if (in_region(addr, (hal_addr_t)FE310_CLINT_BASE, CLINT_WIN)) {
        uint32_t off = (uint32_t)(addr - (hal_addr_t)FE310_CLINT_BASE);
        switch (off) {
        case CLINT_MSIP0:        return g_msip0;
        case CLINT_MTIMECMP0:    return g_mtimecmp_lo;
        case CLINT_MTIMECMP0_HI: return g_mtimecmp_hi;
        case CLINT_MTIME:        return g_mtime_lo;
        case CLINT_MTIME_HI:     return g_mtime_hi;
        default: return 0u;
        }
    } else if (in_region(addr, (hal_addr_t)FE310_PLIC_BASE, PLIC_WIN)) {
        uint32_t off = (uint32_t)(addr - (hal_addr_t)FE310_PLIC_BASE);
        if (off == PLIC_CLAIM0) {
            if (g_claim_head != g_claim_tail) {
                uint32_t src = g_claim_q[g_claim_head];
                g_claim_head = (uint32_t)((g_claim_head + 1) % 16);
                return src;
            }
            return 0u;
        }
        if (off == PLIC_THRESH0) { return g_thresh0; }
        if (off == PLIC_ENABLE0) { return g_enable0; }
        return 0u;
    }
    return 0u;
}

void hal_setbits(hal_addr_t addr, uint32_t mask) { hal_writel(hal_readl(addr) | mask, addr); }
void hal_clrbits(hal_addr_t addr, uint32_t mask) { hal_writel(hal_readl(addr) & ~mask, addr); }

/* ── 供 trap 测试驱动使用的模型接口 ────────────────────────── */
void sim_platform_reset(void)
{
    memset(g_csr, 0, sizeof g_csr);
    g_msip0 = g_mtime_lo = g_mtime_hi = g_mtimecmp_lo = g_mtimecmp_hi = 0u;
    g_thresh0 = g_enable0 = g_last_complete = 0u;
    g_claim_head = g_claim_tail = 0;
}
uint32_t sim_csr_get(uint16_t csr)          { return csr < CSR_FILE_N ? g_csr[csr] : 0u; }
void     sim_mtime_set(uint32_t lo)         { g_mtime_lo = lo; }
uint32_t sim_get_mtimecmp(void)             { return g_mtimecmp_lo; }
void     sim_plic_push_claim(uint32_t src)
{
    g_claim_q[g_claim_tail] = src;
    g_claim_tail = (uint32_t)((g_claim_tail + 1) % 16);
}
uint32_t sim_plic_last_complete(void)       { return g_last_complete; }
