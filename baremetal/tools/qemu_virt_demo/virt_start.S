# tools/qemu_virt_demo/virt_start.S — QEMU virt 演示的极简入口：设栈顶 → call main。
# 直接从 RAM(0x80000000) 执行，无 flash→ram 数据拷贝需求，故不清 .data/.bss。
# （生产固件的完整启动在 boot/crt0.S；此处为 board-matched 演示的最简变体。）
    .section .text
    .global _start
_start:
    la   sp, _estack
    call main
1:  j    1b
