/* tools/qemu_virt_demo/uart.h — QEMU virt (rv32) 控制台串口驱动 API。
 *
 * 由 hal/drivers/uart.c（FE310 SiFive UART）改写而来，改成适配 QEMU virt 机
 * **实际搭载的 ns16550（8250/16550 UART）**：
 *   - riscv virt 的 UART 是 ns16550 兼容芯片，内存映射基址 0x10000000；
 *   - 注意：QEMU **riscv** virt 既不用 SiFive UART（那是 FE310/sifive_e/u），
 *     也不用 PL011（那是 ARM virt 的 UART）。要让演示真跑进 stock QEMU，
 *     必须按 virt 的 ns16550 来驱动。
 *
 * 对外接口与 FE310 版保持一致的语义（init/putc/puts/getc），便于两版对照。
 */
#ifndef QEMU_VIRT_DEMO_UART_H
#define QEMU_VIRT_DEMO_UART_H

#include <stdint.h>

/* 初始化 UART。baud 为期望波特率：QEMU 对 ns16550 的行为建模不依赖真实
   波特率，仍按标准序列写 DLAB/DLL/DLM/FCR/LCR/MCR，真板上即生效。 */
void uart_init(uint32_t baud);

/* 发送单个字节（阻塞直到 THR 空）。返回写入的字符。 */
int uart_putc(int c);

/* 发送以 NUL 结尾的字符串。 */
void uart_puts(const char *s);

/* 阻塞接收单个字节，返回低 8 位。 */
int uart_getc(void);

/* 发送 / 接收定长缓冲区各 n 字节（阻塞）。 */
void uart_write(const char *buf, uint32_t n);
void uart_read(char *buf, uint32_t n);

#endif /* QEMU_VIRT_DEMO_UART_H */
