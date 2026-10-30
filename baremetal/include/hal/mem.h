/* hal/mem.h — 裸机内存分配 API（P5 第 3 步「接管内存」的落点）。 */
#ifndef HAL_MEM_H
#define HAL_MEM_H

#include <hal/types.h>

/* 用链接脚本给出的 [_heap_start, _heap_end) 区间初始化分配器。 */
void hal_mem_init(void);

/* 用显式区间 [base, base+size) 初始化——裸机走 hal_mem_init，宿主寄存器级
   模拟据此直接指定一块静态堆，无需链接符号（见 tools/sim）。 */
void hal_mem_init_region(void *base, hal_size_t size);

/* 分配 size 字节（8 字节对齐）；失败返回 NULL。first-fit + 可分裂。 */
void *hal_malloc(hal_size_t size);

/* 释放此前 hal_malloc 返回的指针；相邻空闲块自动合并（可回收分配器）。 */
void hal_free(void *ptr);

/* 当前最大连续空闲块字节数（供分配器行为验证/观测）。 */
hal_size_t hal_mem_avail(void);

#endif /* HAL_MEM_H */
