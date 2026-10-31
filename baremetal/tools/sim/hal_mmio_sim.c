/* tools/sim/hal_mmio_sim.c — 宿主「寄存器级」MMIO 模拟后端（非裸机、非门禁 C 源）。
 *
 * 实现 mmio.h 在 HAL_MMIO_SIM 下声明的四个原语，把 uart.c 发出的绝对物理地址
 * 访问重定向到一个 FE310 SiFive UART 寄存器堆模型：
 *   - 写 txdata → 追加到发送捕获缓冲（模拟发送器即时排空）；
 *   - 读 txdata → 恒返回 0（永不“满”），使 uart_putc 不会自旋卡死；
 *   - 读 rxdata → 有输入则弹出下一字节（清 EMPTY 位），否则返回 UART_EMPTY；
 *   - txctrl/rxctrl/ie/ip/status → 存寄存器值供断言。
 *
 * 这是宿主测试代码，有意使用 <stdio.h>/<string.h>；它不在 check_skeleton 的
 * freestanding C_SOURCES 扫描范围内，也不参与裸机固件构建。
 */
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#define HAL_MMIO_SIM 1
#include <hal/hal.h>

#define SIM_TXCAP 8192
#define SIM_RXQ   8192

static uint32_t       r_txctrl, r_rxctrl, r_ie, r_ip, r_status;
static unsigned char  txcap[SIM_TXCAP];
static size_t         txlen;
static unsigned char  rxq[SIM_RXQ];
static size_t         rxhead, rxtail;

/* ── 供测试驱动使用的模型操作接口 ───────────────────────────── */
void sim_reset(void)          { r_txctrl = r_rxctrl = r_ie = r_ip = r_status = 0u; txlen = 0u; rxhead = rxtail = 0u; }
void sim_tx_clear(void)       { txlen = 0u; }
size_t sim_tx_len(void)       { return txlen; }
const unsigned char *sim_tx_bytes(void) { return txcap; }
uint32_t sim_get_txctrl(void) { return r_txctrl; }
uint32_t sim_get_rxctrl(void) { return r_rxctrl; }

void sim_rx_feed(const void *buf, size_t n)
{
    const unsigned char *p = (const unsigned char *)buf;
    for (size_t i = 0u; i < n && rxtail < SIM_RXQ; ++i) {
        rxq[rxtail++] = p[i];
    }
}

/* ── mmio.h（HAL_MMIO_SIM）声明的四原语实现 ──────────────────── */
static int in_uart0(hal_addr_t a)
{
    return (a >= (hal_addr_t)FE310_UART0_BASE) &&
           (a <  (hal_addr_t)(FE310_UART0_BASE + 0x1000u));
}

void hal_writel(uint32_t val, hal_addr_t addr)
{
    if (!in_uart0(addr)) {
        return;
    }
    switch ((unsigned)(addr - (hal_addr_t)FE310_UART0_BASE)) {
    case UART_TXDATA: if (txlen < SIM_TXCAP) { txcap[txlen++] = (unsigned char)(val & 0xFFu); } break;
    case UART_TXCTRL: r_txctrl = val; break;
    case UART_RXCTRL: r_rxctrl = val; break;
    case UART_IE:     r_ie = val; break;
    case UART_IP:     r_ip = val; break;
    case UART_STATUS: r_status = val; break;
    default: break;
    }
}

uint32_t hal_readl(hal_addr_t addr)
{
    if (!in_uart0(addr)) {
        return 0u;
    }
    switch ((unsigned)(addr - (hal_addr_t)FE310_UART0_BASE)) {
    case UART_TXDATA: return 0u;                       /* 永不“满”：putc 不阻塞 */
    case UART_RXDATA: return (rxhead < rxtail) ? (uint32_t)rxq[rxhead++] : UART_EMPTY;
    case UART_TXCTRL: return r_txctrl;
    case UART_RXCTRL: return r_rxctrl;
    case UART_IE:     return r_ie;
    case UART_IP:     return r_ip;
    case UART_STATUS: return r_status;
    default: return 0u;
    }
}

void hal_setbits(hal_addr_t addr, uint32_t mask)
{
    hal_writel(hal_readl(addr) | mask, addr);
}

void hal_clrbits(hal_addr_t addr, uint32_t mask)
{
    hal_writel(hal_readl(addr) & ~mask, addr);
}
