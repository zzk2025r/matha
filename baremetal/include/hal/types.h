/* hal/types.h — 裸机基本类型（freestanding：只用 C 标准的 freestanding 头）。 */
#ifndef HAL_TYPES_H
#define HAL_TYPES_H

#include <stddef.h>   /* size_t / ptrdiff_t / NULL（freestanding 提供） */
#include <stdint.h>   /* uintN_t / intN_t（freestanding 提供） */
#include <stdbool.h>  /* bool / true / false */

typedef uintptr_t hal_addr_t;   /* 物理地址一律用无符号整型指针宽度承载 */
typedef size_t    hal_size_t;

#ifndef NULL
#define NULL ((void *)0)
#endif

/* 编译期断言：骨架阶段用于固化寄存器/结构体布局契约。 */
#define HAL_STATIC_ASSERT(cond, tag) _Static_assert(cond, tag)

#endif /* HAL_TYPES_H */
