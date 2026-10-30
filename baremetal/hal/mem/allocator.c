/* hal/mem/allocator.c — 可回收裸机分配器（P5 第 3 步：接管内存）。
 *
 * first-fit + 块分裂 + 相邻空闲块双向合并。所有块按地址序挂在一条双向链表上
 * （已分配块也在链上），故 free 时可直接用 prev/next 找物理邻居合并，无需块尾
 * 边界标记。块头大小向上取整到 8 字节，保证 payload 天然 8 字节对齐。
 *
 * 堆区间来源：裸机 hal_mem_init() 读链接符号 [_heap_start,_heap_end)；
 * 宿主寄存器级模拟用 hal_mem_init_region() 指定静态堆（编译期 -DHAL_MEM_SIM_HEAP
 * 使 hal_mem_init 走模拟全局，不引用不存在的链接符号）。
 */
#include <hal/hal.h>

#define BLK_MIN_ALIGN 8u
#define BLK_MIN_PAYLOAD BLK_MIN_ALIGN   /* 分裂出的空闲块至少可再容纳一次最小分配 */

typedef struct blk {
    struct blk *next;
    struct blk *prev;
    hal_size_t  size;    /* 含块头的整块字节数 */
    bool        inuse;
} blk_t;

static hal_size_t g_hdr;     /* align_up(sizeof(blk_t), 8) */
static blk_t     *g_head;    /* 地址序链表头 */
static bool       g_ready;

static hal_size_t align_up(hal_size_t x, hal_size_t a)
{
    return (x + (a - 1u)) & ~(a - 1u);
}

void hal_mem_init_region(void *base, hal_size_t size)
{
    g_hdr = align_up(sizeof(blk_t), BLK_MIN_ALIGN);

    uintptr_t a       = (uintptr_t)base;
    uintptr_t aligned = align_up(a, BLK_MIN_ALIGN);
    uintptr_t lost    = aligned - a;
    size = (size > lost) ? (size - lost) : 0u;

    /* 至少要能放下两个块头（一个可用单元 + 分裂余量），否则视为无堆。 */
    if (size < (g_hdr + BLK_MIN_ALIGN + g_hdr)) {
        g_head = NULL;
        g_ready = false;
        return;
    }

    blk_t *first = (blk_t *)aligned;
    first->size  = size;
    first->inuse = false;
    first->prev  = NULL;
    first->next  = NULL;
    g_head  = first;
    g_ready = true;
}

#ifndef HAL_MEM_SIM_HEAP
void hal_mem_init(void)
{
    hal_mem_init_region((void *)_heap_start,
                        (hal_size_t)((char *)_heap_end - (char *)_heap_start));
}
#else
void hal_mem_init(void)
{
    extern char      *g_hal_sim_heap_base;
    extern hal_size_t g_hal_sim_heap_size;
    hal_mem_init_region(g_hal_sim_heap_base, g_hal_sim_heap_size);
}
#endif

void *hal_malloc(hal_size_t size)
{
    if (!g_ready) {
        return NULL;
    }
    hal_size_t payload = align_up(size, BLK_MIN_ALIGN);
    if (payload == 0u) {
        payload = BLK_MIN_ALIGN;
    }
    hal_size_t need = g_hdr + payload;

    for (blk_t *b = g_head; b != NULL; b = b->next) {
        if (!b->inuse && b->size >= need) {
            /* 若切出 need 后剩余仍可自成一块，则分裂回堆。 */
            if (b->size >= need + g_hdr + BLK_MIN_PAYLOAD) {
                blk_t *nb = (blk_t *)((char *)b + need);
                nb->size  = b->size - need;
                nb->inuse = false;
                nb->prev  = b;
                nb->next  = b->next;
                if (b->next != NULL) {
                    b->next->prev = nb;
                }
                b->next = nb;                    /* 关键：把当前块的后继接上新块 */
                b->size = need;
            }
            b->inuse = true;
            return (void *)((char *)b + g_hdr);
        }
    }
    return NULL;                        /* 耗尽：返回 NULL，由上层判定 */
}

void hal_free(void *ptr)
{
    if (ptr == NULL || !g_ready) {
        return;
    }
    blk_t *b = (blk_t *)((char *)ptr - g_hdr);
    b->inuse = false;

    /* 先并后继空闲块。 */
    if (b->next != NULL && !b->next->inuse) {
        blk_t *n = b->next;
        b->size += n->size;
        b->next  = n->next;
        if (n->next != NULL) {
            n->next->prev = b;
        }
    }
    /* 再并前驱空闲块。 */
    if (b->prev != NULL && !b->prev->inuse) {
        blk_t *p = b->prev;
        p->size += b->size;
        p->next  = b->next;
        if (b->next != NULL) {
            b->next->prev = p;
        }
    }
}

hal_size_t hal_mem_avail(void)
{
    hal_size_t best = 0u;
    if (g_ready) {
        for (blk_t *b = g_head; b != NULL; b = b->next) {
            if (!b->inuse && b->size > best) {
                best = b->size;
            }
        }
    }
    return best;
}
