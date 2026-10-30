/* hal/trap/trap.c — 机器模式陷阱/中断接管骨架（第 3 步落点）。
 *
 * 第 1 步（本文件）：只提供 hal/irq.h 契约的实现占位，确保头文件地基可编译。
 * 第 3 步：
 *   - hal_irq_enable() 用 csrw mtvec 把 mtvec 指向 boot/vector.S:trap_vector；
 *   - hal_trap_handler() 解析 mcause，分派 PLIC/CLINT 外设中断与同步异常；
 *   - 接管 mstatus.MIE、mtimecmp 定时中断等。
 */
#include <hal/hal.h>

/* boot/vector.S 中的汇编陷入入口。第 3 步由 hal_irq_enable 装入 mtvec。 */
extern void trap_vector(void);

void hal_irq_enable(void)
{
    /* TODO(第 3 步)：csrw mtvec, trap_vector; csrs mstatus, MIE。
       骨架阶段不启用陷入，避免在向量未接管时误捕。 */
    (void)trap_vector;
}

void hal_irq_disable(void)
{
    /* TODO(第 3 步)：csrc mstatus, MIE。 */
}

void hal_trap_handler(uint32_t mcause, uint32_t mepc, uint32_t mtval)
{
    /* 骨架：不做实际分派。第 3 步在此按 mcause 处理异常/中断。
       引用参数以消除 -Wunused，并固化签名。 */
    (void)mcause;
    (void)mepc;
    (void)mtval;
    for (;;) {
        /* 占位：接管前陷入不应到达此处。 */
    }
}
