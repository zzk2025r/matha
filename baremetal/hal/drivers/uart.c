/* hal/drivers/uart.c — FE310 SiFive UART0 控制台驱动（P5 第 2 步：完整收发）。
 *
 * 分层：arch（基址/偏移/位）→ mmio（hal_readl/writel/setbits/clrbits）→ uart。
 * 一切 freestanding：只用易失寄存器访问，不链接任何 libc/OS 运行时。
 *
 * 关于「分频校准」的诚实口径：SiFive UART 块内没有 divisor 寄存器，波特率
 * 由 uart_clk = baud × 16 的参考时钟决定（PRCI 产生）。本驱动据 CPU_FREQ_HZ
 * 校准出整数分频值存入 g_uart_baud_divider，供真板 bring-up 写入 PRCI；不臆测
 * PRCI 字段偏移去写硬件。收发数据路径（txdata/rxdata 轮询）是标准 SiFive 语义，
 * 已在 tools/sim 的宿主寄存器级模拟中逐字节验证。
 */
#include <hal/hal.h>

uint32_t g_uart_baud_divider;

void uart_init(uint32_t baud)
{
    /* 1) 分频校准：算出达到 baud 所需的 PRCI 整数分频值（供板级配置/观测）。 */
    g_uart_baud_divider = hal_uart_baud_divider(CPU_FREQ_HZ, baud);

    /* 2) 使能发送：清 txctrl.TXSTOP(bit10)，TXMARK=0（发送 FIFO 一空即可写）。 */
    hal_writel(0u, FE310_UART0_BASE + UART_TXCTRL);

    /* 3) 接收：FE310-G000 无需使能位，RXMARK=0（收到一字节即置非空）。 */
    hal_writel(0u, FE310_UART0_BASE + UART_RXCTRL);

    (void)baud;
}

int uart_putc(int c)
{
    /* 自旋等待 TX FIFO 可写（txdata bit31=1 表示满），再写入低 8 位。 */
    while (hal_readl(FE310_UART0_BASE + UART_TXDATA) & UART_FULL) {
        /* busy-wait */
    }
    hal_writel((uint32_t)(c & 0xFF), FE310_UART0_BASE + UART_TXDATA);
    return c;
}

void uart_puts(const char *s)
{
    while (s && *s) {
        uart_putc((int)(unsigned char)*s++);
    }
}

int uart_getc(void)
{
    /* 自旋等待 RX FIFO 非空（rxdata bit31=1 表示空），再取低 8 位。 */
    uint32_t v;
    do {
        v = hal_readl(FE310_UART0_BASE + UART_RXDATA);
    } while (v & UART_EMPTY);
    return (int)(v & 0xFFu);
}

void uart_write(const char *buf, hal_size_t n)
{
    for (hal_size_t i = 0; i < n; ++i) {
        uart_putc((int)(unsigned char)buf[i]);
    }
}

void uart_read(char *buf, hal_size_t n)
{
    for (hal_size_t i = 0; i < n; ++i) {
        buf[i] = (char)uart_getc();
    }
}
