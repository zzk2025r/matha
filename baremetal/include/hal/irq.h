/* hal/irq.h — 陷阱/中断接管契约（P5 第 3 步「接管中断」的落点）。 */
#ifndef HAL_IRQ_H
#define HAL_IRQ_H

#include <hal/types.h>

/* RISC-V 机器模式同步异常号（mcause 高位的 interrupt=0 时的低码）。 */
#define HAL_EXC_INST_MISALIGNED 0
#define HAL_EXC_ILLEGAL_INST    2
#define HAL_EXC_BREAKPOINT      3
#define HAL_EXC_LOAD_MISALIGNED 4
#define HAL_EXC_STORE_MISALIGNED 6
#define HAL_EXC_ECALL_FROM_M    11

/* mcause 高位：置 1 表示这是一次中断（而非同步异常）。 */
#define HAL_MCAUSE_INTERRUPT    0x80000000u
/* 机器模式中断码（mcause 低位）。 */
#define HAL_IRQ_M_SOFTWARE      3u      /* CLINT msip */
#define HAL_IRQ_M_TIMER         7u      /* CLINT mtimecmp */
#define HAL_IRQ_M_EXTERNAL      11u     /* PLIC 外设中断 */

/* 可注册外设中断源的处理函数。 */
typedef void (*hal_irq_fn)(void *ctx);

/* 初始化中断：装 mtvec=trap_vector（Direct），开 mie.MTIE|MEIE 与 mstatus.MIE。 */
void hal_irq_init(void);

/* 安装/卸载全局机器模式中断总开关（mstatus.MIE）。 */
void hal_irq_enable(void);
void hal_irq_disable(void);

/* 注册某个 PLIC 中断源的处理函数（source 为 claim 返回的中断源号）。 */
void hal_irq_attach(uint32_t source, hal_irq_fn fn, void *ctx);

/* 装载下一次机器模式定时器：mtimecmp0 = mtime + ticks（写 mtimecmp 亦清除 MTIP）。 */
void hal_timer_arm(uint32_t ticks);

/* 由 boot/vector.S 在每次陷入时调用的 C 处理入口。 */
void hal_trap_handler(uint32_t mcause, uint32_t mepc, uint32_t mtval);

#endif /* HAL_IRQ_H */
