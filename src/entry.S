/*
 * Matha RISC-V 嵌入式项目 — 入口点
 * 目标: SiFive FE310
 */

.section .entry
.global _start

_start:
    /* 初始化栈指针 */
    la sp, _stack_end

    /* 初始化 .data 段 (从 FLASH 复制到 RAM) */
    la a0, _sdata
    la a1, _edata
    la a2, _sdata
    bgeu a0, a1, 2f
1:
    lw t0, 0(a2)
    sw t0, 0(a0)
    addi a0, a0, 4
    addi a2, a2, 4
    bltu a0, a1, 1b
2:
    /* 清零 .bss 段 */
    la a0, _sbss
    la a1, _ebss
    bgeu a0, a1, 2f
1:
    sw zero, 0(a0)
    addi a0, a0, 4
    bltu a0, a1, 1b
2:
    /* 调用 main */
    call main

    /* 死循环 (不应到达) */
1:
    wfi
    j 1b
