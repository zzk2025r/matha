/* hal/hal.h — Matha 裸机 HAL 伞头（P5「脱离宿主 OS」的地基）。
 *
 * 分层（自底向上）：
 *   arch   架构/内存映射常量（hal/arch.h）
 *   boot   crt0 + 链接符号契约（hal/boot.h, boot/*.S）
 *   mmio   寄存器访问原语（hal/mmio.h）
 *   uart   控制台输出（hal/uart.h，第 2 步）
 *   mem    内存接管（hal/mem.h，第 3 步）
 *   irq    中断接管（hal/irq.h，第 3 步）
 *
 * 一切 freestanding：不链接任何 libc / OS 运行时。
 */
#ifndef HAL_H
#define HAL_H

#include <hal/types.h>
#include <hal/arch.h>
#include <hal/mmio.h>
#include <hal/boot.h>
#include <hal/uart.h>
#include <hal/mem.h>
#include <hal/irq.h>

/* 骨架版本标记（非发布版本号，仅标识 HAL 契约代际）。 */
#define HAL_SKELETON_ABI 1

/* 一站式底层初始化：内存 → 串口 → （第 3 步）中断。 */
static inline void hal_init(uint32_t baud) {
    hal_mem_init();
    uart_init(baud);
    /* hal_irq_enable() 在第 3 步接管中断后于此打开。 */
}

#endif /* HAL_H */
