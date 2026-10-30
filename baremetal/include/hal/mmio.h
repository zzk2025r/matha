/* hal/mmio.h — 内存映射 I/O 访问原语（volatile + 地址整型转换）。 */
#ifndef HAL_MMIO_H
#define HAL_MMIO_H

#include <hal/types.h>

/* 把常量物理地址当作易失 32 位寄存器读写。裸机上这是所有外设访问的地基。 */
#define HAL_REG32(addr) (*(volatile uint32_t *)(hal_addr_t)(addr))

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

#endif /* HAL_MMIO_H */
