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

/* SiFive UART 寄存器偏移与关键位。
   注意：SiFive UART 块内【没有】波特率 divisor 寄存器——波特率由喂给它的
   参考时钟 uart_clk 决定，块内固定 16× 过采样（uart_clk = baud × 16），
   该 uart_clk 由片内 PRCI 时钟分频器产生。故「分频校准」是求 PRCI 分频值，
   而非往 UART 块写一个不存在的 divisor。 */
#define UART_TXDATA   0x00u             /* 写：发送；读 bit31=1 表示 TX 满 */
#define UART_RXDATA   0x04u             /* 读：接收；bit31=1 表示 RX 空 */
#define UART_TXCTRL   0x08u             /* bit10=TXSTOP(1 停发)；bit19:16=TXMARK */
#define UART_RXCTRL   0x0Cu             /* bit19:16=RXMARK（FE310-G000 接收无需使能位） */
#define UART_IE       0x10u
#define UART_IP       0x14u
#define UART_STATUS   0x18u
#define UART_FULL     0x80000000u       /* txdata 读 bit31：TX FIFO 满 */
#define UART_EMPTY    0x80000000u       /* rxdata 读 bit31：RX FIFO 空 */
#define UART_TXSTOP   0x00000400u       /* txctrl bit10：置 1 停止发送 */
#define UART_TXMARK_SHIFT 16u           /* txctrl bit19:16 发送水位 */
#define UART_RXMARK_SHIFT 16u           /* rxctrl bit19:16 接收水位 */

/* SiFive UART 内部过采样倍率（波特率时钟 = uart_clk / 16）。 */
#define UART_OVERSAMPLE   16u

/* PRCI（片内时钟/复位）基址：uart_clk 的分频器由此产生，板级 bring-up
   据 uart_init 校准出的分频值配置此处。FE310 具体字段偏移随 SoC 修订版
   而定，故此处只固化基址，实际写入留待真板核对（骨架内不做臆测写）。 */
#define FE310_PRCI_BASE   0x10000000u

/* CLINT 内相对偏移（第 3 步接管软件中断/定时器时用）。 */
#define CLINT_MSIP0      0x0000u
#define CLINT_MTIMECMP0  0x4000u    /* 低 32 位；+0x4004 为高 32 位 */
#define CLINT_MTIMECMP0_HI 0x4004u
#define CLINT_MTIME      0xBFF8u    /* 低 32 位；+0xBFFC 为高 32 位 */
#define CLINT_MTIME_HI   0xBFFCu

/* SiFive PLIC 内相对偏移（context 0 = hart0 M 模式）。标准 SiFive PLIC 布局。 */
#define PLIC_PRIO_BASE   0x000000u  /* 每个中断源 4 字节优先级：base+4*src */
#define PLIC_PENDING     0x00001000u /* 等待位图 */
#define PLIC_ENABLE0     0x00002000u /* context0 使能位图（base+0x80*ctx） */
#define PLIC_THRESH0     0x200000u  /* context0 优先级阈值（base+0x1000*ctx） */
#define PLIC_CLAIM0      0x200004u  /* context0 claim/complete（base+0x1000*ctx+4） */

/* 核频率：名义值，实际由 PLL 配置决定；第 2 步串口分频会据此校准。 */
#define CPU_FREQ_HZ      165350964u

#endif /* HAL_ARCH_H */
