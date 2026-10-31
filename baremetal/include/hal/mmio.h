/* hal/mmio.h — 内存映射 I/O 访问原语（volatile + 地址整型转换）。 */
#ifndef HAL_MMIO_H
#define HAL_MMIO_H

#include <hal/types.h>

/* 把常量物理地址当作易失 32 位寄存器读写。裸机上这是所有外设访问的地基。 */
#define HAL_REG32(addr) (*(volatile uint32_t *)(hal_addr_t)(addr))

#ifdef HAL_MMIO_SIM
/* 宿主「寄存器级模拟」接缝：驱动 uart.c 仍照常调用下面四个原语，但此处只声明
   extern 原型，由测试后端（tools/sim/hal_mmio_sim.c）把它们接到一个模拟寄存器堆
   上——从而在没有真硬件/交叉 QEMU FE310 的情况下，用宿主 gcc 直接跑通并验证
   收发逻辑。裸机构建【不定义】HAL_MMIO_SIM，走下面的 volatile 直解引用路径。 */
void     hal_writel(uint32_t val, hal_addr_t addr);
uint32_t hal_readl(hal_addr_t addr);
void     hal_setbits(hal_addr_t addr, uint32_t mask);
void     hal_clrbits(hal_addr_t addr, uint32_t mask);
#else
static inline void hal_writel(uint32_t val, hal_addr_t addr) {
    HAL_REG32(addr) = val;
}

static inline uint32_t hal_readl(hal_addr_t addr) {
    return HAL_REG32(addr);
}

/* 读-改-写：置/清若干位（中断屏蔽、外设使能等会反复用到）。 */
static inline void hal_setbits(hal_addr_t addr, uint32_t mask) {
    HAL_REG32(addr) |= mask;
}

static inline void hal_clrbits(hal_addr_t addr, uint32_t mask) {
    HAL_REG32(addr) &= ~mask;
}
#endif /* HAL_MMIO_SIM */

#endif /* HAL_MMIO_H */
