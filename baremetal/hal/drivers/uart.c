/* hal/drivers/uart.c — FE310 SiFive UART0 控制台驱动骨架。
 *
 * 第 1 步（本文件）：接通 API 契约 + MMIO 访问骨架，确保整条
 *   arch → mmio → uart 的头文件地基可编译。
 * 第 2 步：校准分频 / 收发 FIFO 语义，并在实板或 QEMU 上验证「最基础输出」。
 */
#include <hal/hal.h>

void uart_init(uint32_t baud)
{
    /* 清除 txctrl 的 TXSTOP(bit10)，使能发送。
       TODO(第 2 步)：依 CPU_FREQ_HZ 与 baud 计算分频并配置 rxctrl/ie。 */
    (void)baud;
    hal_clrbits(FE310_UART0_BASE + UART_TXCTRL, UART_TXSTOP);
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
