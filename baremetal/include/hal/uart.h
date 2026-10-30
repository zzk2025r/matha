/* hal/uart.h — 控制台串口输出 API（第 2 步「实现最基础输出」的落点）。 */
#ifndef HAL_UART_H
#define HAL_UART_H

#include <hal/types.h>

/* 初始化 UART0。baud 为期望波特率（如 115200）；分频依 CPU_FREQ_HZ 计算。 */
void uart_init(uint32_t baud);

/* 发送单个字节（阻塞直到 TX FIFO 可写）。返回写入的字符。 */
int uart_putc(int c);

/* 发送以 NUL 结尾的字符串。 */
void uart_puts(const char *s);

#endif /* HAL_UART_H */
