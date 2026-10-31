/* tools/sim/uart_sim_main.c — 在宿主上驱动真实 hal/drivers/uart.c 的寄存器级测试。
 *
 * 与裸机固件用【同一份】uart.c，只是把 MMIO 接到 hal_mmio_sim.c 的模拟寄存器堆，
 * 从而在没有真 FE310 硬件、也不依赖交叉 QEMU 的情况下，逐字节证明：
 *   1) 分频校准（纯函数 + init 落库的分频值）；
 *   2) 发送使能（txctrl/rxctrl 被正确清零）；
 *   3) TX：putc/puts/write 把正确的字节写入 txdata；
 *   4) RX：getc/read 从 rxdata 按序取回正确的字节。
 */
#include <stdio.h>
#include <string.h>

#define HAL_MMIO_SIM 1
#include <hal/hal.h>

/* 模拟后端接口（见 hal_mmio_sim.c）。 */
extern void sim_reset(void);
extern void sim_tx_clear(void);
extern size_t sim_tx_len(void);
extern const unsigned char *sim_tx_bytes(void);
extern void sim_rx_feed(const void *buf, size_t n);
extern uint32_t sim_get_txctrl(void);
extern uint32_t sim_get_rxctrl(void);

static int g_fails;

static void eq_u32(const char *name, uint32_t got, uint32_t exp)
{
    if (got == exp) {
        printf("  [ok]   %s = %u\n", name, got);
    } else {
        printf("  [FAIL] %s = %u (期望 %u)\n", name, got, exp);
        g_fails++;
    }
}

static void eq_bytes(const char *name, const void *got, size_t gl, const void *exp, size_t el)
{
    if (gl == el && memcmp(got, exp, el) == 0) {
        printf("  [ok]   %s（%lu 字节一致）\n", name, (unsigned long)gl);
    } else {
        printf("  [FAIL] %s（得到 %lu 字节，期望 %lu 字节）\n",
               name, (unsigned long)gl, (unsigned long)el);
        g_fails++;
    }
}

int main(void)
{
    printf("=== FE310 UART 宿主寄存器级模拟 ===\n");

    /* 1) 分频校准：uart_clk = baud × 16，round-to-nearest。 */
    eq_u32("divider(9.216MHz,115200)", hal_uart_baud_divider(9216000u, 115200u), 5u);
    eq_u32("divider(1.8432MHz,115200)", hal_uart_baud_divider(1843200u, 115200u), 1u);
    eq_u32("divider(CPU_FREQ_HZ,115200)", hal_uart_baud_divider(CPU_FREQ_HZ, 115200u), 90u);

    /* FE310 名义频率下的实际波特率误差须 <2%。 */
    {
        uint32_t d = hal_uart_baud_divider(CPU_FREQ_HZ, 115200u);
        double achieved = (double)CPU_FREQ_HZ / ((double)d * (double)UART_OVERSAMPLE);
        double err = (achieved - 115200.0) / 115200.0;
        if (err < 0.0) { err = -err; }
        if (err < 0.02) {
            printf("  [ok]   实际波特率≈%.0f，误差 %.2f%% (<2%%)\n", achieved, err * 100.0);
        } else {
            printf("  [FAIL] 实际波特率≈%.0f，误差 %.2f%% 过大\n", achieved, err * 100.0);
            g_fails++;
        }
    }

    /* 2) 初始化落库与使能寄存器。 */
    sim_reset();
    uart_init(115200u);
    eq_u32("g_uart_baud_divider", g_uart_baud_divider, 90u);
    eq_u32("txctrl（TXSTOP 已清）", sim_get_txctrl(), 0u);
    eq_u32("rxctrl（RXMARK=0）", sim_get_rxctrl(), 0u);

    /* 3) 发送：puts / write。 */
    sim_reset(); uart_init(115200u); sim_tx_clear();
    uart_puts("HELLO\r\n");
    eq_bytes("uart_puts(\"HELLO\\r\\n\")", sim_tx_bytes(), sim_tx_len(), "HELLO\r\n", 7u);

    sim_tx_clear();
    {
        const char bin[3] = {0x01, 0x02, 0x03};
        uart_write(bin, 3u);
        eq_bytes("uart_write(3B)", sim_tx_bytes(), sim_tx_len(), bin, 3u);
    }

    /* 4) 接收：getc / read 按序取回。 */
    sim_reset(); uart_init(115200u);
    sim_rx_feed("ABCD", 4u);
    eq_u32("uart_getc #1", (uint32_t)uart_getc(), (uint32_t)'A');
    eq_u32("uart_getc #2", (uint32_t)uart_getc(), (uint32_t)'B');
    {
        char rb[2] = {0, 0};
        uart_read(rb, 2u);
        eq_bytes("uart_read(2B)", rb, 2u, "CD", 2u);
    }

    if (g_fails == 0) {
        printf("结果：UART 寄存器级模拟全部通过（真实 uart.c，未上真硬件）\n");
        return 0;
    }
    printf("结果：UART 模拟失败 %d 项\n", g_fails);
    return 1;
}
