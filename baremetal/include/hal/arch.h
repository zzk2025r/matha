/* hal/arch.h — RISC-V / SiFive FE310 架构与内存映射常量（骨架，逐步接管）。 */
#ifndef HAL_ARCH_H
#define HAL_ARCH_H

#include <hal/types.h>

#define ARCH_RISCV        1
#define ARCH_XLEN         32
#define ARCH_MABI_ILP32   1

/* ── FE310 外设基址（片内存储映射）─────────────────────────────
   第 2 步（串口输出）与第 3 步（内存/中断接管）分别消费 UART0 / CLINT+PLIC。 */
#define FE310_CLINT_BASE  0x02000000u   /* core-local interruptor：mtime/msip */
#define FE310_PLIC_BASE   0x0C000000u   /* platform-level interrupt controller */
#define FE310_UART0_BASE  0x10013000u   /* SiFive UART，控制台输出（第 2 步） */

/* SiFive UART 寄存器偏移与关键位。 */
#define UART_TXDATA   0x00u             /* 写：发送；bit31=1 表示 FIFO 满 */
#define UART_RXDATA   0x04u             /* 读：接收；bit31=1 表示 FIFO 空 */
#define UART_TXCTRL   0x08u             /* bit10=1 停发（nTXREADY） */
#define UART_RXCTRL   0x0Cu
#define UART_IE       0x10u
#define UART_IP       0x14u
#define UART_STATUS   0x18u
#define UART_FULL     0x80000000u       /* txdata bit31 */
#define UART_TXSTOP   0x00000400u       /* txctrl bit10 */

/* CLINT 内相对偏移（第 3 步接管软件中断/定时器时用）。 */
#define CLINT_MSIP0      0x0000u
#define CLINT_MTIMECMP0  0x4000u
#define CLINT_MTIME      0xBFF8u

/* 核频率：名义值，实际由 PLL 配置决定；第 2 步串口分频会据此校准。 */
#define CPU_FREQ_HZ      165350964u

#endif /* HAL_ARCH_H */
