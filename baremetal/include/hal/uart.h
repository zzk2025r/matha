/* hal/uart.h — 控制台串口收发 API（P5 第 2 步「实现最基础输出」的落点）。 */
#ifndef HAL_UART_H
#define HAL_UART_H

#include <hal/types.h>
#include <hal/arch.h>

/* uart_init 依据 baud 校准得到的 PRCI 整数分频值（供板级 bring-up / 观测）。 */
extern uint32_t g_uart_baud_divider;

/* 分频校准（纯函数，可在宿主上逐值单测）：
   SiFive UART 块内固定 16× 过采样，故期望 uart_clk = baud × UART_OVERSAMPLE；
   给定喂给 UART 的参考时钟 ref_clk_hz，返回四舍五入后的整数分频器。 */
static inline uint32_t hal_uart_baud_divider(uint32_t ref_clk_hz, uint32_t baud) {
    uint32_t denom = baud * UART_OVERSAMPLE;      /* 期望 uart_clk */
    if (denom == 0u) {
        return 0u;
    }
    return (ref_clk_hz + denom / 2u) / denom;      /* round-to-nearest */
}

/* 初始化 UART0。baud 为期望波特率（如 115200）：
   先按 CPU_FREQ_HZ 与 baud 校准分频值，再清 TXSTOP 使能发送、复位水位。 */
void uart_init(uint32_t baud);

/* 发送单个字节（阻塞直到 TX FIFO 可写）。返回写入的字符。 */
int uart_putc(int c);

/* 发送以 NUL 结尾的字符串。 */
void uart_puts(const char *s);

/* 阻塞接收单个字节。返回收到的字符（低 8 位）。 */
int uart_getc(void);

/* 发送 / 接收定长缓冲区各 n 字节（阻塞）。 */
void uart_write(const char *buf, hal_size_t n);
void uart_read(char *buf, hal_size_t n);

#endif /* HAL_UART_H */
