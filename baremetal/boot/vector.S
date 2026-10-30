/* boot/vector.S — 机器模式陷阱向量（第 3 步「接管中断」的挂点）。
 *
 * 骨架阶段只提供入口约定，不做上下文保存；真正接管时在此：
 *   - 保存被调用者保存寄存器 / 栈上构建 trapframe
 *   - 读 mcause/mepc/mtval 传入 C 处理入口 hal_trap_handler
 *   - 处理结束 mret 返回
 *
 * 由 hal/irq.h:hal_irq_enable() 把 mtvec 指到 trap_vector（Direct 模式）。
 */
    .section .text
    .globl trap_vector
    .type  trap_vector, @function
    .align 2
trap_vector:
    /* TODO(第 3 步)：保存上下文 → csrr a0=mcause, a1=mepc, a2=mtval
     *                 → call hal_trap_handler → 恢复上下文 → mret
     * 骨架：先直接 mret，保证安装 mtvec 后不误吞陷入。 */
    mret
    .size trap_vector, .-trap_vector
