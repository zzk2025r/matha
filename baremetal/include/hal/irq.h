/* hal/irq.h — 陷阱/中断接管契约（第 3 步「接管中断」的落点）。 */
#ifndef HAL_IRQ_H
#define HAL_IRQ_H

#include <hal/types.h>

/* RISC-V 机器模式异常号（mcause 的低 4 位，中断位为高 bit）。 */
#define HAL_EXC_INST_MISALIGNED 0
#define HAL_EXC_ILLEGAL_INST    2
#define HAL_EXC_BREAKPOINT      3
#define HAL_EXC_LOAD_MISALIGNED 4
#define HAL_EXC_STORE_MISALIGNED 6
#define HAL_EXC_ECALL_FROM_M    11

/* 由 boot/vector.S 在每次陷入时调用的 C 处理入口。 */
void hal_trap_handler(uint32_t mcause, uint32_t mepc, uint32_t mtval);

/* 安装/卸载全局陷阱向量（把 mtvec 指向 vector.S 的入口）。 */
void hal_irq_enable(void);
void hal_irq_disable(void);

#endif /* HAL_IRQ_H */
