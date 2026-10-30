/* hal/mem/allocator.c — 裸机分配器骨架（第 3 步「接管内存」的落点）。
 *
 * 第 1 步（本文件）：接通 hal/mem.h API 契约，提供一个最简 bump 分配器，
 *   直接消费链接脚本给出的 [_heap_start, _heap_end)。
 * 第 3 步：换成带 free 合并 / 对齐 / 元数据校验的分配器，并接管 .data/.bss
 *   之外的堆治理。
 */
#include <hal/hal.h>

static char   *g_heap_cur;    /* 下一个可分配地址 */
static char   *g_heap_limit;  /* 堆上界（不含） */
static bool    g_heap_ready;

void hal_mem_init(void)
{
    g_heap_cur   = _heap_start;
    g_heap_limit = _heap_end;
    g_heap_ready = true;
}

void *hal_malloc(hal_size_t size)
{
    if (!g_heap_ready) {
        hal_mem_init();
    }
    /* 8 字节对齐向上取整。 */
    hal_size_t need = (size + 7u) & ~(hal_size_t)7u;
    if ((hal_size_t)(g_heap_limit - g_heap_cur) < need) {
        return NULL;              /* 耗尽：裸机无 OOM 处理，交由上层判 NULL */
    }
    void *p = (void *)g_heap_cur;
    g_heap_cur += need;
    return p;
}

void hal_free(void *ptr)
{
    /* bump 分配器不支持释放；保留契约，第 3 步替换实现。 */
    (void)ptr;
}
