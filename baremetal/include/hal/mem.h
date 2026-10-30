/* hal/mem.h — 裸机内存分配 API（第 3 步「接管内存」的落点）。 */
#ifndef HAL_MEM_H
#define HAL_MEM_H

#include <hal/types.h>

/* 用链接脚本给出的 [_heap_start, _heap_end) 区间初始化分配器。 */
void hal_mem_init(void);

/* 分配 size 字节（8 字节对齐）；失败返回 NULL。 */
void *hal_malloc(hal_size_t size);

/* 释放（骨架阶段为 bump 分配器，释放是空操作，仅保留 API 契约）。 */
void hal_free(void *ptr);

#endif /* HAL_MEM_H */
