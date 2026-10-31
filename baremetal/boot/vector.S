/* boot/vector.S — RV32 机器模式陷阱向量入口（P5 第 3 步：接管中断）。
 *
 * 由 mtvec（Direct 模式）指向 trap_vector。进入后：
 *   1. 在栈上保存被中断上下文（ra + t0..t6 + a0..a7，足以支撑一次 C 调用且不破坏现场）；
 *   2. 读 mcause/mepc/mtval 到 a0/a1/a2 作实参，call hal_trap_handler；
 *   3. 恢复上下文并 mret 返回被中断处。
 *
 * 说明：这是纯汇编，宿主 gcc 无法执行，故行为逻辑放在 C 层 hal_trap_handler 并由
 * tools/sim 逐条验证；本文件正确性由交叉编译进 RV32 ELF（riscv-none-elf-gcc 汇编）证明。
 */
    .section .text
    .globl trap_vector
    .type  trap_vector, @function
    .align 2
trap_vector:
    /* 16 槽 trapframe：ra, t0..t6(7), a0..a7(8) 共 16 个 4 字节寄存器。 */
    addi  sp, sp, -64
    sw    ra,  0*4(sp)
    sw    t0,  1*4(sp)
    sw    t1,  2*4(sp)
    sw    t2,  3*4(sp)
    sw    a0,  4*4(sp)
    sw    a1,  5*4(sp)
    sw    a2,  6*4(sp)
    sw    a3,  7*4(sp)
    sw    a4,  8*4(sp)
    sw    a5,  9*4(sp)
    sw    a6, 10*4(sp)
    sw    a7, 11*4(sp)
    sw    t3, 12*4(sp)
    sw    t4, 13*4(sp)
    sw    t5, 14*4(sp)
    sw    t6, 15*4(sp)

    /* 2. 陷入原因入参：hal_trap_handler(mcause, mepc, mtval)。 */
    csrr  a0, mcause
    csrr  a1, mepc
    csrr  a2, mtval
    call  hal_trap_handler

    /* 3. 恢复上下文并返回被中断处。 */
    lw    ra,  0*4(sp)
    lw    t0,  1*4(sp)
    lw    t1,  2*4(sp)
    lw    t2,  3*4(sp)
    lw    a0,  4*4(sp)
    lw    a1,  5*4(sp)
    lw    a2,  6*4(sp)
    lw    a3,  7*4(sp)
    lw    a4,  8*4(sp)
    lw    a5,  9*4(sp)
    lw    a6, 10*4(sp)
    lw    a7, 11*4(sp)
    lw    t3, 12*4(sp)
    lw    t4, 13*4(sp)
    lw    t5, 14*4(sp)
    lw    t6, 15*4(sp)
    addi  sp, sp, 64
    mret
    .size trap_vector, .-trap_vector
