/* boot/crt0.S — RV32 裸机最小启动（SiFive FE310）。
 *
 * 职责（与 baremetal/link.ld 的符号契约逐一对应）：
 *   1. 把 sp 装到 _estack（RAM 末端）。
 *   2. 复位 gp（链接器相对全局指针 __global_pointer$）。
 *   3. 从 FLASH 的 _sidata 拷贝 .data 初值到 RAM 的 [_sdata,_edata)。
 *   4. 清零 .bss [_sbss,_ebss)。
 *   5. 调用 main()；返回则进入 wfi 死循环。
 *
 * 陷阱向量在第 3 步接管前保持默认（mtvec 未设 = 直通），
 * 见 boot/vector.S。
 */
    .section .text.entry
    .globl _start
    .type  _start, @function
_start:
    /* 1. 栈顶 */
    la   sp, _estack

    /* 2. 全局指针（ relaxation 用） */
    .option push
    .option norelax
    la   gp, __global_pointer$
    .option pop

    /* 3. .data: 从加载镜像拷到运行区（逐 4 字节） */
    la   t0, _sdata           /* 目标游标 */
    la   t1, _edata           /* 目标末（不含） */
    la   t2, _sidata          /* 源游标（FLASH LMA） */
1:  bgeu t0, t1, 2f
    lw   t3, 0(t2)
    sw   t3, 0(t0)
    addi t0, t0, 4
    addi t2, t2, 4
    j    1b

    /* 4. .bss 清零 */
2:  la   t0, _sbss
    la   t1, _ebss
3:  bgeu t0, t1, 4f
    sw   zero, 0(t0)
    addi t0, t0, 4
    j    3b

    /* 5. 进入 C 世界 */
4:  call main

    /* main 不应返回；安全兜底：wfi 死循环 */
5:  wfi
    j    5b
    .size _start, .-_start
