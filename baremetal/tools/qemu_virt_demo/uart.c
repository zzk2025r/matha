/* tools/qemu_virt_demo/uart.c — 适配 QEMU virt (rv32) 的 ns16550 UART 控制台驱动。
 *
 * 由 hal/drivers/uart.c（FE310 SiFive UART）改写：设备从「SiFive UART
 * (txdata/rxdata 32 位 + PRCI 分频)」换成「QEMU riscv virt 机实际搭载的
 * ns16550（8250/16550）兼容 UART，基址 0x10000000，寄存器按字节偏移」。
 * （riscv virt 不用 SiFive UART，也不用 ARM 的 PL011——见 uart.h 说明。）
 *
 * 一切 freestanding：只用易失 MMIO，不链接任何 libc/OS 运行时。
 * 发送路径以 LSR.THEM(bit5) 轮询、接收路径以 LSR.DR(bit0) 轮询，是标准 16550 语义。
 */
#include <stdint.h>
#include "uart.h"

/* ns16550 寄存器（相对基址的字节偏移）。 */
#define UART_BASE   0x10000000u
#define REG_RBR     0u   /* Receive Buffer Register（读，DLAB=0） */
#define REG_THR     0u   /* Transmit Holding Register（写，DLAB=0） */
#define REG_DLL     0u   /* Divisor Latch Low（DLAB=1） */
#define REG_IER     1u   /* Interrupt Enable Register（DLAB=0） */
#define REG_DLM     1u   /* Divisor Latch High（DLAB=1） */
#define REG_FCR     2u   /* FIFO Control Register（写） */
#define REG_LCR     3u   /* Line Control Register */
#define REG_MCR     4u   /* Modem Control Register */
#define REG_LSR     5u   /* Line Status Register（读） */

/* LCR 位。 */
#define LCR_DLAB    0x80u   /* Divisor Latch Access Bit */
#define LCR_8N1     0x03u   /* 8 数据位 / 无校验 / 1 停止位 */
/* FCR 位。 */
#define FCR_FIFOEN  0x01u   /* FIFO 使能 */
#define FCR_RXCLR   0x02u   /* 清 RX FIFO */
#define FCR_TXCLR   0x04u   /* 清 TX FIFO */
/* MCR 位。 */
#define MCR_DTR     0x01u
#define MCR_RTS     0x02u
#define MCR_OUT2    0x08u   /* 使能芯片侧中断线（QEMU/真板都要求） */
/* LSR 位。 */
#define LSR_DR      0x01u   /* Data Ready（RX 非空） */
#define LSR_THRE    0x20u   /* TX Holding Register Empty（可写） */

/* virt 上 ns16550 以字节访问：基址 + 偏移直接映射到各 8 位寄存器。 */
static volatile uint8_t *const uart = (volatile uint8_t *)UART_BASE;

void uart_init(uint32_t baud)
{
    uint16_t div;

    uart[REG_IER] = 0x00u;                 /* 先关 UART 内部中断（本演示用轮询） */

    /* QEMU 建模不依赖波特率，但仍按标准序列写分频锁存：div = 基准时钟/(16*baud)。
       这里以经典 115200 基准时钟 1.8432MHz×... 简化为按 baud 直算整数分频，baud=0 兜底 1。 */
    div = (baud != 0u) ? (uint16_t)(115200u / baud) : 1u;
    if (div == 0u) { div = 1u; }

    uart[REG_LCR] = LCR_DLAB;              /* DLAB=1，开放分频锁存 */
    uart[REG_DLL] = (uint8_t)(div & 0xFFu);
    uart[REG_DLM] = (uint8_t)((div >> 8) & 0xFFu);

    uart[REG_LCR] = LCR_8N1;               /* DLAB=0，8N1 */
    uart[REG_FCR] = FCR_FIFOEN | FCR_RXCLR | FCR_TXCLR;  /* 使能并清空 FIFO */
    uart[REG_MCR] = MCR_DTR | MCR_RTS | MCR_OUT2;        /* 拉高控制线 */
}

int uart_putc(int c)
{
    /* 自旋等待 THR 空（LSR.THEM=1）再写入发送保持寄存器。 */
    while ((uart[REG_LSR] & LSR_THRE) == 0u) {
        /* busy-wait */
    }
    uart[REG_THR] = (uint8_t)(c & 0xFF);
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
    /* 自旋等待 RX 非空（LSR.DR=1）再读接收缓冲寄存器。 */
    while ((uart[REG_LSR] & LSR_DR) == 0u) {
        /* busy-wait */
    }
    return (int)(uart[REG_RBR] & 0xFFu);
}

void uart_write(const char *buf, uint32_t n)
{
    for (uint32_t i = 0; i < n; ++i) {
        uart_putc((int)(unsigned char)buf[i]);
    }
}

void uart_read(char *buf, uint32_t n)
{
    for (uint32_t i = 0; i < n; ++i) {
        buf[i] = (char)uart_getc();
    }
}
